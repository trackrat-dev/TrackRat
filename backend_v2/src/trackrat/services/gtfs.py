"""
GTFS Static Schedule Service for TrackRat.

Handles downloading, parsing, and querying GTFS static schedule data
for displaying train schedules on future days.
"""

import csv
import io
import zipfile
from datetime import date, datetime, time, timedelta
from typing import Any

import httpx
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.config.stations import (
    expand_station_codes,
    get_patco_route_info,
    get_path_route_info,
    get_station_name,
    map_gtfs_stop_to_station_code,
)
from trackrat.models.api import (
    DataFreshness,
    DeparturesResponse,
    LineInfo,
    RawStopStatus,
    RouteInfo,
    SimpleStationInfo,
    StationInfo,
    StopDetails,
    TrainDeparture,
    TrainDetails,
    TrainPosition,
)
from trackrat.models.database import (
    GTFSCalendar,
    GTFSCalendarDate,
    GTFSFeedInfo,
    GTFSRoute,
    GTFSStopTime,
    GTFSTrip,
)
from trackrat.utils.time import DATETIME_MAX_ET, ET, now_et

logger = get_logger(__name__)

# GTFS Feed URLs
GTFS_FEED_URLS = {
    "NJT": "https://content.njtransit.com/public/developers-resources/rail_data.zip",
    "AMTRAK": "https://content.amtrak.com/content/gtfs/GTFS.zip",
    "PATH": "http://data.trilliumtransit.com/gtfs/path-nj-us/path-nj-us.zip",
    "PATCO": "https://rapid.nationalrtap.org/GTFSFileManagement/UserUploadFiles/13562/PATCO_GTFS.zip",
    "LIRR": "http://web.mta.info/developers/data/lirr/google_transit.zip",
    "MNR": "http://web.mta.info/developers/data/mnr/google_transit.zip",
    "SUBWAY": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_supplemented.zip",
    "BART": "https://www.bart.gov/dev/schedules/google_transit.zip",
}

# Minimum hours between feed downloads (rate limiting)
GTFS_DOWNLOAD_INTERVAL_HOURS = 24

# Default line colors when not provided in GTFS
DEFAULT_LINE_COLORS = {
    "NJT": "#003DA5",  # NJ Transit blue
    "AMTRAK": "#004B87",  # Amtrak blue
    "PATH": "#0039A6",  # PATH blue
    "PATCO": "#BC0035",  # PATCO red
    "LIRR": "#0039A6",  # LIRR blue (MTA blue)
    "MNR": "#0039A6",  # Metro-North blue (MTA blue)
    "SUBWAY": "#0039A6",  # NYC Subway blue (MTA blue)
}

# NJT GTFS route_short_name to line code mapping
# Maps GTFS route abbreviations to the 2-char codes used by the NJT real-time API
# (the API's LINE field) and route_topology.py.
NJT_LINE_CODE_MAPPING = {
    # Northeast Corridor
    "NEC": "NE",
    # North Jersey Coast Line
    "NJCL": "NC",
    "NJCLL": "NC",
    # Morris & Essex Line (Morristown, Dover) — distinct from Montclair-Boonton "MO"
    "MNE": "ME",
    # Gladstone Branch (part of Morris & Essex)
    "MNEG": "GL",
    # Montclair-Boonton Line
    "BNTN": "MO",
    "BNTNM": "MO",
    # Main/Bergen County Line
    "MNBN": "MA",
    "MNBNP": "MA",
    # Pascack Valley Line
    "PASC": "PV",
    # Raritan Valley Line
    "RARV": "RV",
    # Atlantic City Rail Line
    "ATLC": "AC",
    # Princeton Shuttle (Dinky)
    "PRIN": "PR",
}


def _lirr_train_id_from_gtfs(train_id_or_trip_id: str) -> str:
    """Convert LIRR GTFS train number or trip_id to the L-prefixed real-time format.

    LIRR real-time collector generates train IDs as "L{number}" (e.g., "L181").
    GTFS stores the bare number in trip_short_name (e.g., "181") or uses
    trip_id formats:
    - GO-prefix:    "GO103_25_181"       -> 3rd segment is train number
    - Date-suffix:  "7597_2026-02-22"    -> 1st segment is train number

    Args:
        train_id_or_trip_id: Either a bare number ("181") or GTFS trip_id.

    Returns:
        L-prefixed train ID (e.g., "L181").
    """
    if train_id_or_trip_id.startswith("L"):
        return train_id_or_trip_id
    if train_id_or_trip_id.isdigit():
        return f"L{train_id_or_trip_id}"
    parts = train_id_or_trip_id.split("_")
    # Date-suffix format: "7597_2026-02-22" -> train number is 1st segment
    if len(parts) == 2 and "-" in parts[1]:
        return f"L{parts[0]}"
    # GO-prefix format: "GO103_25_181" -> train number is 3rd segment
    if len(parts) >= 3:
        return f"L{parts[2]}"
    # Fallback: prefix as-is
    return f"L{train_id_or_trip_id}"


def _mnr_train_id_from_gtfs(train_id_or_trip_id: str) -> str:
    """Convert MNR GTFS train number or trip_id to the M-prefixed real-time format.

    MNR real-time collector generates train IDs as "M{digits}" where digits are
    the last 6 characters of the trip_id filtered to digits only (e.g., "M631700").
    GTFS stores the bare number in trip_short_name (e.g., "631700").

    Args:
        train_id_or_trip_id: Either a bare number ("631700") or GTFS trip_id.

    Returns:
        M-prefixed train ID (e.g., "M631700").
    """
    if train_id_or_trip_id.startswith("M") and train_id_or_trip_id[1:].isdigit():
        return train_id_or_trip_id
    if train_id_or_trip_id.isdigit():
        return f"M{train_id_or_trip_id}"
    # Mirror MNR collector logic: last 6 chars, digits only
    suffix = (
        train_id_or_trip_id[-6:]
        if len(train_id_or_trip_id) > 6
        else train_id_or_trip_id
    )
    digits = "".join(c for c in suffix if c.isdigit())
    if digits:
        return f"M{digits}"
    # Fallback: prefix as-is
    return f"M{train_id_or_trip_id[:6]}"


def _strip_source_prefix(train_id: str, source: str) -> str:
    """Strip transit-system display prefix from train_id for GTFS lookup.

    Display prefixes are added in departure listings to avoid ID collisions
    between systems. This reverses that for GTFS database lookup.

    Examples:
        ("A112", "AMTRAK") -> "112"
        ("L181", "LIRR") -> "181"
        ("M631700", "MNR") -> "631700"
        ("S1-AFA25GEN-...", "SUBWAY") -> "AFA25GEN-..."
    """
    if source == "AMTRAK" and train_id.startswith("A") and train_id[1:].isdigit():
        return train_id[1:]
    if source == "LIRR" and train_id.startswith("L") and train_id[1:].isdigit():
        return train_id[1:]
    if source == "MNR" and train_id.startswith("M") and train_id[1:].isdigit():
        return train_id[1:]
    if source == "SUBWAY" and train_id.startswith("S"):
        dash_idx = train_id.find("-")
        if dash_idx != -1:
            return train_id[dash_idx + 1 :]
    return train_id


def _extract_lirr_train_number(gtfs_trip_id: str) -> str | None:
    """Extract LIRR train number from a date-suffix GTFS-RT trip_id.

    LIRR GTFS-RT uses trip_ids like "6817_2026-02-24" for trains not matching
    the current GTFS static schedule's trip_ids (which use "GO103_25_6817").
    The train number (first segment) matches trip_short_name in GTFS static.

    Args:
        gtfs_trip_id: GTFS-RT trip_id string.

    Returns:
        Train number string (e.g., "6817") if date-suffix format detected,
        None otherwise.
    """
    parts = gtfs_trip_id.split("_")
    if len(parts) == 2 and "-" in parts[1] and parts[0].isdigit():
        return parts[0]
    return None


class GTFSService:
    """Service for managing GTFS static schedule data."""

    def __init__(self, timeout: float = 120.0):
        """Initialize the GTFS service.

        Args:
            timeout: HTTP request timeout in seconds (GTFS files can be large)
        """
        self.timeout = timeout

    async def refresh_feed(
        self,
        db: AsyncSession,
        data_source: str,
        force: bool = False,
    ) -> bool:
        """Download and parse GTFS feed for a data source.

        Args:
            db: Database session
            data_source: "NJT" or "AMTRAK"
            force: If True, skip the 24hr rate limit check

        Returns:
            True if feed was refreshed, False if skipped due to rate limit
        """
        if data_source not in GTFS_FEED_URLS:
            logger.error("Unknown GTFS data source", data_source=data_source)
            return False

        # Check rate limit
        feed_info = await self._get_or_create_feed_info(db, data_source)

        if not force and feed_info.last_downloaded_at:
            hours_since_download = (
                now_et() - feed_info.last_downloaded_at
            ).total_seconds() / 3600
            if hours_since_download < GTFS_DOWNLOAD_INTERVAL_HOURS:
                logger.info(
                    "Skipping GTFS download - rate limited",
                    data_source=data_source,
                    hours_since_download=round(hours_since_download, 1),
                    next_allowed_in_hours=round(
                        GTFS_DOWNLOAD_INTERVAL_HOURS - hours_since_download, 1
                    ),
                )
                return False

        url = GTFS_FEED_URLS[data_source]
        logger.info("Downloading GTFS feed", data_source=data_source, url=url)

        try:
            # Download the GTFS zip file
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                zip_data = response.content

            # Update download timestamp
            feed_info.last_downloaded_at = now_et()
            await db.flush()

            # Parse and store the data
            stats = await self._parse_and_store_gtfs(db, data_source, zip_data)

            # Update feed info with stats
            feed_info.last_successful_parse_at = now_et()
            feed_info.route_count = stats.get("routes", 0)
            feed_info.trip_count = stats.get("trips", 0)
            feed_info.stop_time_count = stats.get("stop_times", 0)
            feed_info.feed_start_date = stats.get("start_date")
            feed_info.feed_end_date = stats.get("end_date")
            feed_info.error_message = None

            await db.commit()

            logger.info(
                "GTFS feed refreshed successfully",
                data_source=data_source,
                routes=stats.get("routes"),
                trips=stats.get("trips"),
                stop_times=stats.get("stop_times"),
            )
            return True

        except httpx.HTTPError as e:
            error_msg = f"HTTP error downloading GTFS: {e}"
            logger.error(error_msg, data_source=data_source)
            await db.rollback()
            feed_info = await self._get_or_create_feed_info(db, data_source)
            feed_info.error_message = error_msg
            await db.commit()
            return False

        except Exception as e:
            error_msg = f"Error processing GTFS: {e}"
            logger.error(error_msg, data_source=data_source, exc_info=True)
            await db.rollback()
            feed_info = await self._get_or_create_feed_info(db, data_source)
            feed_info.error_message = error_msg
            await db.commit()
            return False

    async def _get_or_create_feed_info(
        self, db: AsyncSession, data_source: str
    ) -> GTFSFeedInfo:
        """Get or create feed info record for a data source."""
        result = await db.execute(
            select(GTFSFeedInfo).where(GTFSFeedInfo.data_source == data_source)
        )
        feed_info = result.scalar_one_or_none()

        if not feed_info:
            feed_info = GTFSFeedInfo(
                data_source=data_source,
                feed_url=GTFS_FEED_URLS[data_source],
            )
            db.add(feed_info)
            await db.flush()

        return feed_info

    async def _parse_and_store_gtfs(
        self, db: AsyncSession, data_source: str, zip_data: bytes
    ) -> dict[str, Any]:
        """Parse GTFS zip and store in database.

        Returns stats about what was parsed.
        """
        # Clear existing data for this source
        await self._clear_existing_data(db, data_source)

        stats: dict[str, Any] = {}

        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            file_list = zf.namelist()
            logger.debug("GTFS zip contents", files=file_list)

            # Parse routes first (needed for FK)
            if "routes.txt" in file_list:
                routes = await self._parse_routes(db, data_source, zf)
                stats["routes"] = len(routes)
            else:
                logger.warning("No routes.txt in GTFS", data_source=data_source)
                routes = {}

            # Parse calendar
            calendar_services: set[str] = set()
            if "calendar.txt" in file_list:
                calendar_services = await self._parse_calendar(db, data_source, zf)
                stats["calendar_entries"] = len(calendar_services)

            # Parse calendar_dates (exceptions)
            if "calendar_dates.txt" in file_list:
                exceptions = await self._parse_calendar_dates(db, data_source, zf)
                stats["calendar_exceptions"] = exceptions

            # Parse stops to build stop_id -> name mapping
            stops: dict[str, str] = {}
            if "stops.txt" in file_list:
                stops = self._parse_stops(zf)
                stats["stops"] = len(stops)

            # Parse trips
            if "trips.txt" in file_list:
                trips = await self._parse_trips(db, data_source, zf, routes)
                stats["trips"] = len(trips)
            else:
                logger.warning("No trips.txt in GTFS", data_source=data_source)
                trips = {}

            # Parse stop_times
            if "stop_times.txt" in file_list:
                stop_times_count = await self._parse_stop_times(
                    db, data_source, zf, trips, stops
                )
                stats["stop_times"] = stop_times_count

            # Get date range from calendar
            if calendar_services:
                result = await db.execute(
                    select(
                        GTFSCalendar.start_date,
                        GTFSCalendar.end_date,
                    )
                    .where(GTFSCalendar.data_source == data_source)
                    .order_by(GTFSCalendar.start_date)
                )
                dates = result.all()
                if dates:
                    stats["start_date"] = min(d[0] for d in dates)
                    stats["end_date"] = max(d[1] for d in dates)

        await db.flush()
        return stats

    async def _clear_existing_data(self, db: AsyncSession, data_source: str) -> None:
        """Clear existing GTFS data for a source before refresh."""
        # Delete in reverse FK order
        # First, get all trip IDs for this source
        result = await db.execute(
            select(GTFSTrip.id).where(GTFSTrip.data_source == data_source)
        )
        trip_ids = [row[0] for row in result.all()]

        if trip_ids:
            await db.execute(
                delete(GTFSStopTime).where(GTFSStopTime.trip_id.in_(trip_ids))
            )

        await db.execute(delete(GTFSTrip).where(GTFSTrip.data_source == data_source))
        await db.execute(delete(GTFSRoute).where(GTFSRoute.data_source == data_source))
        await db.execute(
            delete(GTFSCalendar).where(GTFSCalendar.data_source == data_source)
        )
        await db.execute(
            delete(GTFSCalendarDate).where(GTFSCalendarDate.data_source == data_source)
        )

        await db.flush()

    async def _parse_routes(
        self, db: AsyncSession, data_source: str, zf: zipfile.ZipFile
    ) -> dict[str, int]:
        """Parse routes.txt and store in database. Returns route_id -> db_id mapping."""
        routes: dict[str, int] = {}

        with zf.open("routes.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            for row in reader:
                route_id = row.get("route_id", "")
                if route_id in routes:
                    continue

                route = GTFSRoute(
                    data_source=data_source,
                    route_id=route_id,
                    route_short_name=row.get("route_short_name"),
                    route_long_name=row.get("route_long_name"),
                    route_color=row.get("route_color"),
                )
                db.add(route)
                await db.flush()
                if route.route_id and route.id is not None:
                    routes[route.route_id] = route.id

        return routes

    async def _parse_calendar(
        self, db: AsyncSession, data_source: str, zf: zipfile.ZipFile
    ) -> set[str]:
        """Parse calendar.txt and store in database. Returns set of service_ids."""
        services: set[str] = set()

        with zf.open("calendar.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            for row in reader:
                service_id = row.get("service_id", "")
                if not service_id or service_id in services:
                    continue

                calendar = GTFSCalendar(
                    data_source=data_source,
                    service_id=service_id,
                    monday=row.get("monday") == "1",
                    tuesday=row.get("tuesday") == "1",
                    wednesday=row.get("wednesday") == "1",
                    thursday=row.get("thursday") == "1",
                    friday=row.get("friday") == "1",
                    saturday=row.get("saturday") == "1",
                    sunday=row.get("sunday") == "1",
                    start_date=self._parse_gtfs_date(row.get("start_date", "")),
                    end_date=self._parse_gtfs_date(row.get("end_date", "")),
                )
                db.add(calendar)
                services.add(service_id)

        await db.flush()
        return services

    async def _parse_calendar_dates(
        self, db: AsyncSession, data_source: str, zf: zipfile.ZipFile
    ) -> int:
        """Parse calendar_dates.txt and store in database. Returns count."""
        count = 0
        seen_keys: set[tuple[str, str]] = set()

        with zf.open("calendar_dates.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            for row in reader:
                service_id = row.get("service_id", "")
                date_str = row.get("date", "")
                exception_type = row.get("exception_type", "")

                if not service_id or not date_str or not exception_type:
                    continue

                key = (service_id, date_str)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                calendar_date = GTFSCalendarDate(
                    data_source=data_source,
                    service_id=service_id,
                    date=self._parse_gtfs_date(date_str),
                    exception_type=int(exception_type),
                )
                db.add(calendar_date)
                count += 1

        await db.flush()
        return count

    def _parse_stops(self, zf: zipfile.ZipFile) -> dict[str, str]:
        """Parse stops.txt and return stop_id -> stop_name mapping."""
        stops: dict[str, str] = {}

        with zf.open("stops.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            for row in reader:
                stop_id = row.get("stop_id", "")
                stop_name = row.get("stop_name", "")
                if stop_id and stop_name:
                    stops[stop_id] = stop_name

        return stops

    async def _parse_trips(
        self,
        db: AsyncSession,
        data_source: str,
        zf: zipfile.ZipFile,
        routes: dict[str, int],
    ) -> dict[str, int]:
        """Parse trips.txt and store in database. Returns trip_id -> db_id mapping."""
        trips: dict[str, int] = {}
        batch: list[GTFSTrip] = []
        batch_trip_ids: list[str] = []  # Track trip_ids in current batch
        batch_size = 500

        with zf.open("trips.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            for row in reader:
                # Sanitize trip_id: replace spaces with underscores for URL safety.
                # PATCO GTFS uses trip_ids like "Sunday Westbound_T25" which break
                # HTTP requests when used as path parameters.
                trip_id = row.get("trip_id", "").replace(" ", "_")
                route_id = row.get("route_id", "")

                if not trip_id or route_id not in routes:
                    continue

                if trip_id in trips or trip_id in batch_trip_ids:
                    continue

                headsign = row.get("trip_headsign", "")

                # Extract train_id from trip_short_name or headsign
                short_name = row.get("trip_short_name", "")
                train_id = short_name or self._extract_train_id(headsign)

                direction_str = row.get("direction_id", "")
                direction_id = int(direction_str) if direction_str.isdigit() else None

                trip = GTFSTrip(
                    data_source=data_source,
                    trip_id=trip_id,
                    route_id=routes[route_id],
                    service_id=row.get("service_id", ""),
                    trip_headsign=headsign,
                    train_id=train_id,
                    direction_id=direction_id,
                )
                batch.append(trip)
                batch_trip_ids.append(trip_id)

                if len(batch) >= batch_size:
                    db.add_all(batch)
                    await db.flush()
                    # Map trip_ids to db ids after flush
                    for i, t in enumerate(batch):
                        if t.id is not None:
                            trips[batch_trip_ids[i]] = t.id
                    batch = []
                    batch_trip_ids = []

        # Add remaining
        if batch:
            db.add_all(batch)
            await db.flush()
            for i, t in enumerate(batch):
                if t.id is not None:
                    trips[batch_trip_ids[i]] = t.id

        return trips

    async def _parse_stop_times(
        self,
        db: AsyncSession,
        data_source: str,
        zf: zipfile.ZipFile,
        trips: dict[str, int],
        stops: dict[str, str],
    ) -> int:
        """Parse stop_times.txt and store in database. Returns count."""
        count = 0
        batch: list[GTFSStopTime] = []
        batch_size = 1000

        with zf.open("stop_times.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            for row in reader:
                # Must match the sanitization applied in _parse_trips
                trip_id = row.get("trip_id", "").replace(" ", "_")
                if trip_id not in trips:
                    continue

                gtfs_stop_id = row.get("stop_id", "")
                stop_name = stops.get(gtfs_stop_id, "")

                # Map to our internal station code
                station_code = map_gtfs_stop_to_station_code(
                    gtfs_stop_id, stop_name, data_source
                )

                seq_str = row.get("stop_sequence", "")
                pickup_str = row.get("pickup_type", "0")
                dropoff_str = row.get("drop_off_type", "0")

                stop_time = GTFSStopTime(
                    trip_id=trips[trip_id],
                    stop_sequence=int(seq_str) if seq_str.isdigit() else 0,
                    gtfs_stop_id=gtfs_stop_id,
                    station_code=station_code,
                    arrival_time=row.get("arrival_time"),
                    departure_time=row.get("departure_time"),
                    pickup_type=int(pickup_str) if pickup_str.isdigit() else 0,
                    drop_off_type=int(dropoff_str) if dropoff_str.isdigit() else 0,
                )
                batch.append(stop_time)
                count += 1

                if len(batch) >= batch_size:
                    db.add_all(batch)
                    await db.flush()
                    batch = []

        # Add remaining
        if batch:
            db.add_all(batch)
            await db.flush()

        return count

    def _parse_gtfs_date(self, date_str: str) -> date:
        """Parse GTFS date format (YYYYMMDD)."""
        if not date_str or len(date_str) != 8:
            return date.today()
        try:
            return date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
        except ValueError:
            logger.warning("Invalid GTFS date", date_str=date_str)
            return date.today()

    def _extract_train_id(self, headsign: str) -> str | None:
        """Try to extract train number from headsign."""
        if not headsign:
            return None
        # Look for a number at the start or end
        import re

        match = re.search(r"\b(\d{2,4})\b", headsign)
        return match.group(1) if match else None

    def _parse_gtfs_time(self, time_str: str, target_date: date) -> datetime | None:
        """Parse GTFS time string (HH:MM:SS, can be >24:00) to datetime.

        Args:
            time_str: Time string like "14:30:00" or "25:30:00"
            target_date: The service date

        Returns:
            Datetime in Eastern time, handling overnight trips
        """
        if not time_str:
            return None

        parts = time_str.split(":")
        if len(parts) < 2:
            return None

        try:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2]) if len(parts) > 2 else 0
        except ValueError:
            return None

        # Handle times >= 24:00 (overnight trips)
        days_offset = hours // 24
        hours = hours % 24

        base_dt = datetime.combine(target_date, time(hours, minutes, seconds))
        if days_offset > 0:
            base_dt += timedelta(days=days_offset)

        # Localize to Eastern time
        return ET.localize(base_dt)

    async def get_active_service_ids(
        self, db: AsyncSession, data_source: str, target_date: date
    ) -> set[str]:
        """Get service IDs that are active on a given date.

        Considers both calendar.txt (weekly patterns) and
        calendar_dates.txt (exceptions/additions).
        """
        active_services: set[str] = set()
        removed_services: set[str] = set()

        # Day of week (0=Monday, 6=Sunday)
        dow = target_date.weekday()
        dow_columns = [
            GTFSCalendar.monday,
            GTFSCalendar.tuesday,
            GTFSCalendar.wednesday,
            GTFSCalendar.thursday,
            GTFSCalendar.friday,
            GTFSCalendar.saturday,
            GTFSCalendar.sunday,
        ]

        # Get services from calendar that run on this day of week
        result = await db.execute(
            select(GTFSCalendar.service_id).where(
                and_(
                    GTFSCalendar.data_source == data_source,
                    GTFSCalendar.start_date <= target_date,
                    GTFSCalendar.end_date >= target_date,
                    dow_columns[dow] == True,  # noqa: E712
                )
            )
        )
        for row in result.all():
            active_services.add(row[0])

        # Check calendar_dates for exceptions
        result = await db.execute(
            select(GTFSCalendarDate.service_id, GTFSCalendarDate.exception_type).where(
                and_(
                    GTFSCalendarDate.data_source == data_source,
                    GTFSCalendarDate.date == target_date,
                )
            )
        )
        for row in result.all():
            service_id, exception_type = row
            if exception_type == 1:  # Service added
                active_services.add(service_id)
            elif exception_type == 2:  # Service removed
                removed_services.add(service_id)

        # Remove services that are explicitly removed on this date
        active_services -= removed_services

        return active_services

    async def get_path_route_stop_times(
        self,
        db: AsyncSession,
        route_id: str,
        terminus_station: str,
        observed_terminus_time: datetime,
    ) -> list[tuple[str, datetime | None, datetime | None]] | None:
        """Get stop times for a PATH route going TO the terminus station.

        Finds a GTFS trip on the specified route where the LAST stop matches
        the terminus_station. This ensures we get the correct direction for
        bidirectional PATH routes (e.g., HOB-33 goes both Hoboken→33rd and
        33rd→Hoboken).

        Args:
            db: Database session
            route_id: Transiter/GTFS route ID (e.g., "859" for HOB-33)
            terminus_station: Internal station code of the terminus (e.g., "P33")
            observed_terminus_time: When the train will arrive at terminus

        Returns:
            List of (station_code, arrival_time, departure_time) tuples,
            ordered from origin to terminus. Times may be None for origin/terminus.
            Returns None if no GTFS data available or no trip in correct direction.
        """
        target_date = observed_terminus_time.date()

        # Get active service IDs for PATH on this date
        service_ids = await self.get_active_service_ids(db, "PATH", target_date)
        if not service_ids:
            logger.warning(
                "path_no_active_services",
                route_id=route_id,
                target_date=str(target_date),
            )
            return None

        # Find the GTFSRoute by route_id
        route_result = await db.execute(
            select(GTFSRoute.id).where(
                and_(
                    GTFSRoute.data_source == "PATH",
                    GTFSRoute.route_id == route_id,
                )
            )
        )
        route_row = route_result.first()
        if not route_row:
            logger.warning(
                "path_route_not_found",
                route_id=route_id,
            )
            return None

        gtfs_route_db_id = route_row[0]

        # Find a trip going TO the terminus (last stop = terminus_station)
        # We use a subquery to find the max stop_sequence per trip, then filter
        # for trips where that last stop is the terminus_station
        gtfs_trip_id = await self._find_trip_ending_at_station(
            db, gtfs_route_db_id, terminus_station, service_ids
        )

        if not gtfs_trip_id:
            logger.warning(
                "path_no_trip_to_terminus",
                route_id=route_id,
                terminus_station=terminus_station,
                service_ids=list(service_ids)[:5],
            )
            return None

        # Get all stop times for this trip, ordered by sequence
        stops_result = await db.execute(
            select(
                GTFSStopTime.station_code,
                GTFSStopTime.stop_sequence,
                GTFSStopTime.arrival_time,
                GTFSStopTime.departure_time,
            )
            .where(GTFSStopTime.trip_id == gtfs_trip_id)
            .order_by(GTFSStopTime.stop_sequence)
        )
        stop_rows = stops_result.all()

        if not stop_rows:
            logger.warning(
                "path_no_stop_times",
                route_id=route_id,
                trip_id=gtfs_trip_id,
            )
            return None

        # Parse stop times
        parsed_stops: list[tuple[str, datetime | None, datetime | None]] = []
        terminus_scheduled_time: datetime | None = None

        for station_code, _sequence, arrival_str, departure_str in stop_rows:
            if not station_code:
                continue

            arrival_dt = self._parse_gtfs_time(arrival_str, target_date)
            departure_dt = self._parse_gtfs_time(departure_str, target_date)

            parsed_stops.append((station_code, arrival_dt, departure_dt))

            # The last stop should be the terminus
            if station_code == terminus_station and arrival_dt:
                terminus_scheduled_time = arrival_dt

        if not parsed_stops:
            return None

        # Verify the last stop is indeed the terminus
        if parsed_stops[-1][0] != terminus_station:
            logger.warning(
                "path_trip_wrong_direction",
                route_id=route_id,
                terminus_station=terminus_station,
                actual_last_stop=parsed_stops[-1][0],
            )
            return None

        # Use the last stop's arrival time as terminus time
        if terminus_scheduled_time is None:
            terminus_scheduled_time = parsed_stops[-1][1]

        if terminus_scheduled_time is None:
            logger.warning(
                "path_no_terminus_time",
                route_id=route_id,
                terminus_station=terminus_station,
            )
            return None

        # Calculate time delta: how much to adjust all times
        time_delta = observed_terminus_time - terminus_scheduled_time

        # Apply delta to all stop times
        adjusted_stops: list[tuple[str, datetime | None, datetime | None]] = []
        for station_code, arrival_dt, departure_dt in parsed_stops:
            adjusted_arrival = arrival_dt + time_delta if arrival_dt else None
            adjusted_departure = departure_dt + time_delta if departure_dt else None
            adjusted_stops.append((station_code, adjusted_arrival, adjusted_departure))

        logger.debug(
            "path_stop_times_from_gtfs",
            route_id=route_id,
            terminus_station=terminus_station,
            stop_count=len(adjusted_stops),
            origin_station=adjusted_stops[0][0] if adjusted_stops else None,
            time_delta_minutes=time_delta.total_seconds() / 60,
        )

        return adjusted_stops

    async def _find_trip_ending_at_station(
        self,
        db: AsyncSession,
        route_db_id: int,
        terminus_station: str,
        service_ids: set[str],
    ) -> int | None:
        """Find a GTFS trip that ends at the specified station.

        Args:
            db: Database session
            route_db_id: Database ID of the GTFSRoute
            terminus_station: Station code where trip should end
            service_ids: Active service IDs

        Returns:
            Database ID of a matching GTFSTrip, or None if not found
        """
        from sqlalchemy import func

        # Subquery to find the max stop_sequence for each trip
        max_seq_subq = (
            select(
                GTFSStopTime.trip_id,
                func.max(GTFSStopTime.stop_sequence).label("max_seq"),
            )
            .group_by(GTFSStopTime.trip_id)
            .subquery()
        )

        # Find trips where the last stop is the terminus_station
        result = await db.execute(
            select(GTFSTrip.id)
            .join(max_seq_subq, GTFSTrip.id == max_seq_subq.c.trip_id)
            .join(
                GTFSStopTime,
                and_(
                    GTFSStopTime.trip_id == GTFSTrip.id,
                    GTFSStopTime.stop_sequence == max_seq_subq.c.max_seq,
                ),
            )
            .where(
                and_(
                    GTFSTrip.route_id == route_db_id,
                    GTFSTrip.service_id.in_(service_ids),
                    GTFSStopTime.station_code == terminus_station,
                )
            )
            .limit(1)
        )
        row = result.first()
        return row[0] if row else None

    async def get_path_route_stop_times_from_origin(
        self,
        db: AsyncSession,
        origin_station: str,
        destination_station: str,
        departure_time: datetime,
    ) -> list[tuple[str, datetime | None, datetime | None]] | None:
        """Get stop times for a PATH route from origin to destination.

        Finds a GTFS trip that starts at origin_station and ends at destination_station,
        then returns all stop times along the route, adjusted to match the observed
        departure time.

        Args:
            db: Database session
            origin_station: Internal station code of the origin (e.g., "PHO")
            destination_station: Internal station code of destination (e.g., "P33")
            departure_time: Observed departure time from origin

        Returns:
            List of (station_code, arrival_time, departure_time) tuples,
            ordered from origin to destination. Returns None if no GTFS data.
        """
        target_date = departure_time.date()

        # Get active service IDs for PATH
        service_ids = await self.get_active_service_ids(db, "PATH", target_date)
        if not service_ids:
            logger.warning(
                "path_no_active_services_origin",
                origin=origin_station,
                destination=destination_station,
                target_date=str(target_date),
            )
            return None

        # Find a trip that goes from origin to destination
        trip_id = await self._find_trip_from_origin_to_destination(
            db, origin_station, destination_station, service_ids
        )

        if not trip_id:
            logger.debug(
                "path_no_trip_origin_to_dest",
                origin=origin_station,
                destination=destination_station,
            )
            return None

        # Get all stop times for this trip
        stops_result = await db.execute(
            select(
                GTFSStopTime.station_code,
                GTFSStopTime.stop_sequence,
                GTFSStopTime.arrival_time,
                GTFSStopTime.departure_time,
            )
            .where(GTFSStopTime.trip_id == trip_id)
            .order_by(GTFSStopTime.stop_sequence)
        )
        stop_rows = stops_result.all()

        if not stop_rows:
            return None

        # Parse stop times
        parsed_stops: list[tuple[str, datetime | None, datetime | None]] = []
        origin_scheduled_time: datetime | None = None

        for station_code, _sequence, arrival_str, departure_str in stop_rows:
            if not station_code:
                continue

            arrival_dt = self._parse_gtfs_time(arrival_str, target_date)
            departure_dt = self._parse_gtfs_time(departure_str, target_date)

            parsed_stops.append((station_code, arrival_dt, departure_dt))

            # Record origin departure time for adjustment
            if station_code == origin_station and departure_dt:
                origin_scheduled_time = departure_dt

        if not parsed_stops or origin_scheduled_time is None:
            return None

        # Verify the route goes origin -> destination
        if (
            parsed_stops[0][0] != origin_station
            or parsed_stops[-1][0] != destination_station
        ):
            logger.debug(
                "path_trip_wrong_route",
                expected_origin=origin_station,
                expected_dest=destination_station,
                actual_origin=parsed_stops[0][0],
                actual_dest=parsed_stops[-1][0],
            )
            return None

        # Calculate time delta and adjust all stop times
        time_delta = departure_time - origin_scheduled_time

        adjusted_stops: list[tuple[str, datetime | None, datetime | None]] = []
        for station_code, arrival_dt, departure_dt in parsed_stops:
            adjusted_arrival = arrival_dt + time_delta if arrival_dt else None
            adjusted_departure = departure_dt + time_delta if departure_dt else None
            adjusted_stops.append((station_code, adjusted_arrival, adjusted_departure))

        logger.debug(
            "path_stop_times_from_origin",
            origin=origin_station,
            destination=destination_station,
            stop_count=len(adjusted_stops),
            time_delta_minutes=time_delta.total_seconds() / 60,
        )

        return adjusted_stops

    async def _find_trip_from_origin_to_destination(
        self,
        db: AsyncSession,
        origin_station: str,
        destination_station: str,
        service_ids: set[str],
    ) -> int | None:
        """Find a GTFS trip that goes from origin to destination.

        Args:
            db: Database session
            origin_station: Station code where trip should start
            destination_station: Station code where trip should end
            service_ids: Active service IDs

        Returns:
            Database ID of a matching GTFSTrip, or None if not found
        """
        from sqlalchemy import func

        # Find trips where first stop is origin and last stop is destination
        # Subquery for min stop_sequence (origin)
        min_seq_subq = (
            select(
                GTFSStopTime.trip_id,
                func.min(GTFSStopTime.stop_sequence).label("min_seq"),
            )
            .group_by(GTFSStopTime.trip_id)
            .subquery()
        )

        # Subquery for max stop_sequence (destination)
        max_seq_subq = (
            select(
                GTFSStopTime.trip_id,
                func.max(GTFSStopTime.stop_sequence).label("max_seq"),
            )
            .group_by(GTFSStopTime.trip_id)
            .subquery()
        )

        # Find trips that match both criteria
        # First, find trips where origin is the first stop
        origin_trips = (
            select(GTFSTrip.id)
            .join(min_seq_subq, GTFSTrip.id == min_seq_subq.c.trip_id)
            .join(
                GTFSStopTime,
                and_(
                    GTFSStopTime.trip_id == GTFSTrip.id,
                    GTFSStopTime.stop_sequence == min_seq_subq.c.min_seq,
                ),
            )
            .where(
                and_(
                    GTFSTrip.data_source == "PATH",
                    GTFSTrip.service_id.in_(service_ids),
                    GTFSStopTime.station_code == origin_station,
                )
            )
        ).subquery()

        # Then find trips where destination is the last stop
        result = await db.execute(
            select(GTFSTrip.id)
            .join(max_seq_subq, GTFSTrip.id == max_seq_subq.c.trip_id)
            .join(
                GTFSStopTime,
                and_(
                    GTFSStopTime.trip_id == GTFSTrip.id,
                    GTFSStopTime.stop_sequence == max_seq_subq.c.max_seq,
                ),
            )
            .where(
                and_(
                    GTFSTrip.id.in_(select(origin_trips.c.id)),
                    GTFSStopTime.station_code == destination_station,
                )
            )
            .limit(1)
        )
        row = result.first()
        return row[0] if row else None

    async def get_scheduled_departures(
        self,
        db: AsyncSession,
        from_station: str,
        to_station: str | None,
        target_date: date,
        limit: int = 50,
        data_sources: list[str] | None = None,
    ) -> DeparturesResponse:
        """Get scheduled departures from GTFS data for a future date.

        Args:
            db: Database session
            from_station: Departure station code
            to_station: Destination station code (optional)
            target_date: The date to get schedules for
            limit: Maximum number of results
            data_sources: If provided, only query these data sources

        Returns:
            DeparturesResponse with scheduled trains
        """
        departures: list[TrainDeparture] = []

        # All known GTFS data sources
        all_source_names = ["NJT", "AMTRAK", "PATH", "PATCO", "LIRR", "MNR", "SUBWAY"]

        # Filter to requested sources if specified
        sources_to_query = (
            [s for s in all_source_names if s in data_sources]
            if data_sources
            else all_source_names
        )

        # Get active service IDs only for requested sources
        all_services: dict[str, set[str]] = {}
        for source in sources_to_query:
            service_ids = await self.get_active_service_ids(db, source, target_date)
            if service_ids:
                all_services[source] = service_ids

        for data_source, service_ids in all_services.items():
            source_departures = await self._query_departures_for_source(
                db, data_source, service_ids, from_station, to_station, target_date
            )
            departures.extend(source_departures)

        # Sort by departure time
        # Use timezone-aware constant for safe comparison with ET-localized times
        departures.sort(key=lambda d: d.departure.scheduled_time or DATETIME_MAX_ET)

        # Apply limit
        departures = departures[:limit]

        return DeparturesResponse(
            departures=departures,
            metadata={
                "from_station": {
                    "code": from_station,
                    "name": get_station_name(from_station),
                },
                "to_station": (
                    {
                        "code": to_station,
                        "name": get_station_name(to_station),
                    }
                    if to_station
                    else None
                ),
                "count": len(departures),
                "generated_at": now_et().isoformat(),
            },
        )

    async def _query_departures_for_source(
        self,
        db: AsyncSession,
        data_source: str,
        service_ids: set[str],
        from_station: str,
        to_station: str | None,
        target_date: date,
    ) -> list[TrainDeparture]:
        """Query GTFS tables for departures from a specific data source."""
        departures: list[TrainDeparture] = []

        # Find trips that have the from_station
        # We need to join trips -> stop_times to find matching trips
        result = await db.execute(
            select(
                GTFSTrip.id,
                GTFSTrip.trip_id,  # GTFS trip_id string for unique identification
                GTFSTrip.train_id,
                GTFSTrip.trip_headsign,
                GTFSTrip.service_id,
                GTFSRoute.route_id,  # GTFS route_id string (e.g., "859")
                GTFSRoute.route_short_name,
                GTFSRoute.route_long_name,
                GTFSRoute.route_color,
                GTFSStopTime.departure_time,
                GTFSStopTime.stop_sequence,
            )
            .join(GTFSRoute, GTFSTrip.route_id == GTFSRoute.id)
            .join(GTFSStopTime, GTFSTrip.id == GTFSStopTime.trip_id)
            .where(
                and_(
                    GTFSTrip.data_source == data_source,
                    GTFSTrip.service_id.in_(service_ids),
                    GTFSStopTime.station_code.in_(expand_station_codes(from_station)),
                )
            )
            .order_by(GTFSStopTime.departure_time)
        )

        trips_data = result.all()

        # Pre-fetch destination station data in one query to avoid N+1 problem
        to_station_data: dict[int, tuple[str, int]] = (
            {}
        )  # trip_id -> (arrival_time, sequence)
        if to_station and trips_data:
            trip_ids = [row[0] for row in trips_data]
            dest_result = await db.execute(
                select(
                    GTFSStopTime.trip_id,
                    GTFSStopTime.arrival_time,
                    GTFSStopTime.stop_sequence,
                ).where(
                    and_(
                        GTFSStopTime.trip_id.in_(trip_ids),
                        GTFSStopTime.station_code.in_(expand_station_codes(to_station)),
                    )
                )
            )
            for dest_row in dest_result.all():
                to_station_data[dest_row[0]] = (dest_row[1], dest_row[2])

        for row in trips_data:
            (
                db_trip_id,
                gtfs_trip_id,  # GTFS trip_id string for unique identification
                train_id,
                headsign,
                service_id,
                gtfs_route_id,  # GTFS route_id string (e.g., "859")
                route_short,
                route_long,
                route_color,
                dep_time_str,
                dep_sequence,
            ) = row

            # If to_station specified, verify this trip also stops there after from_station
            arrival_time_str = None
            if to_station:
                dest_info = to_station_data.get(db_trip_id)
                if not dest_info or dest_info[1] <= dep_sequence:
                    # Trip doesn't stop at destination, or stops before origin
                    continue
                arrival_time_str = dest_info[0]

            # Parse times
            departure_dt = self._parse_gtfs_time(dep_time_str, target_date)
            arrival_dt = (
                self._parse_gtfs_time(arrival_time_str, target_date)
                if arrival_time_str
                else None
            )

            if not departure_dt:
                continue

            # Build the departure response
            # PATH and PATCO routes need special handling for proper line codes/colors
            if data_source == "PATH":
                path_route_info = get_path_route_info(gtfs_route_id)
                if path_route_info:
                    line_code, line_name, line_color = path_route_info
                    # Ensure color has # prefix
                    if not line_color.startswith("#"):
                        line_color = f"#{line_color}"
                else:
                    # Fallback for unknown PATH routes
                    line_code = route_short or "PATH"
                    line_name = route_long or route_short or "PATH"
                    line_color = (
                        f"#{route_color}"
                        if route_color
                        else DEFAULT_LINE_COLORS.get(data_source, "#666666")
                    )
            elif data_source == "PATCO":
                patco_route_info = get_patco_route_info(gtfs_route_id)
                if patco_route_info:
                    line_code, line_name, line_color = patco_route_info
                    # Ensure color has # prefix
                    if not line_color.startswith("#"):
                        line_color = f"#{line_color}"
                else:
                    # Fallback for unknown PATCO routes
                    line_code = route_short or "PATCO"
                    line_name = route_long or route_short or "PATCO Speedline"
                    line_color = (
                        f"#{route_color}"
                        if route_color
                        else DEFAULT_LINE_COLORS.get(data_source, "#BC0035")
                    )
            elif data_source == "LIRR":
                from trackrat.config.stations import get_lirr_route_info

                lirr_route_info = get_lirr_route_info(gtfs_route_id)
                if lirr_route_info:
                    line_code, line_name, line_color = lirr_route_info
                    if not line_color.startswith("#"):
                        line_color = f"#{line_color}"
                else:
                    line_code = route_short or "LIRR"
                    line_name = route_long or route_short or "LIRR"
                    line_color = (
                        f"#{route_color}"
                        if route_color
                        else DEFAULT_LINE_COLORS.get(data_source, "#0039A6")
                    )
            elif data_source == "MNR":
                from trackrat.config.stations import get_mnr_route_info

                mnr_route_info = get_mnr_route_info(gtfs_route_id)
                if mnr_route_info:
                    line_code, line_name, line_color = mnr_route_info
                    if not line_color.startswith("#"):
                        line_color = f"#{line_color}"
                else:
                    line_code = route_short or "MNR"
                    line_name = route_long or route_short or "Metro-North"
                    line_color = (
                        f"#{route_color}"
                        if route_color
                        else DEFAULT_LINE_COLORS.get(data_source, "#0039A6")
                    )
            elif data_source == "SUBWAY":
                from trackrat.config.stations import get_subway_route_info

                subway_route_info = get_subway_route_info(gtfs_route_id)
                if subway_route_info:
                    line_code, line_name, line_color = subway_route_info
                    if not line_color.startswith("#"):
                        line_color = f"#{line_color}"
                else:
                    line_code = route_short or f"SUBWAY-{gtfs_route_id}"
                    line_name = route_long or route_short or f"Subway {gtfs_route_id}"
                    line_color = (
                        f"#{route_color}"
                        if route_color
                        else DEFAULT_LINE_COLORS.get(data_source, "#0039A6")
                    )
            else:
                # For NJT, map GTFS route_short_name to API line codes for deduplication
                if data_source == "NJT" and route_short:
                    line_code = NJT_LINE_CODE_MAPPING.get(route_short, route_short)
                else:
                    line_code = route_short or data_source[:2]
                line_name = route_long or route_short or data_source
                line_color = (
                    f"#{route_color}"
                    if route_color
                    else DEFAULT_LINE_COLORS.get(data_source, "#666666")
                )

            # Determine effective train_id:
            # - If train_id is set (from trip_short_name, e.g., Amtrak/NJT), use it
            # - Otherwise fall back to gtfs_trip_id for lookup purposes
            # For Amtrak, train_id will be the actual train number (e.g., "112")
            # NJT GTFS has trip_short_name but uses different train numbers
            # than the real-time API, so primary-key dedup won't match —
            # fallback dedup (line + time) handles NJT matching instead.
            effective_train_id = train_id if train_id else gtfs_trip_id

            # Add "A" prefix for Amtrak to match real-time format (e.g., "112" -> "A112")
            if (
                data_source == "AMTRAK"
                and effective_train_id
                and not effective_train_id.startswith("A")
            ):
                effective_train_id = f"A{effective_train_id}"

            # Add "L" prefix for LIRR to match real-time format (e.g., "181" -> "L181")
            if data_source == "LIRR" and effective_train_id:
                effective_train_id = _lirr_train_id_from_gtfs(effective_train_id)

            # Add "M" prefix for MNR to match real-time format (e.g., "631700" -> "M631700")
            if data_source == "MNR" and effective_train_id:
                effective_train_id = _mnr_train_id_from_gtfs(effective_train_id)

            # Add "S{route}-" prefix for SUBWAY to distinguish from other systems.
            # Use full GTFS trip_id (not truncated) so detail endpoint can
            # reverse-lookup the trip by stripping the prefix.
            if (
                data_source == "SUBWAY"
                and effective_train_id
                and not effective_train_id.startswith("S")
            ):
                route_prefix = route_short or "X"
                effective_train_id = f"S{route_prefix}-{effective_train_id}"

            departure = TrainDeparture(
                train_id=effective_train_id,
                journey_date=target_date,
                line=LineInfo(
                    code=line_code[:10],
                    name=line_name,
                    color=line_color,
                ),
                destination=headsign or "Unknown",
                departure=StationInfo(
                    code=from_station,
                    name=get_station_name(from_station),
                    scheduled_time=departure_dt,
                    updated_time=None,
                    actual_time=None,
                    track=None,
                ),
                arrival=(
                    StationInfo(
                        code=to_station,
                        name=get_station_name(to_station),
                        scheduled_time=arrival_dt,
                        updated_time=None,
                        actual_time=None,
                        track=None,
                    )
                    if to_station and arrival_dt
                    else None
                ),
                train_position=TrainPosition(
                    last_departed_station_code=None,
                    at_station_code=None,
                    next_station_code=None,
                    between_stations=False,
                ),
                data_freshness=DataFreshness(
                    last_updated=now_et(),
                    age_seconds=0,
                    update_count=None,
                    collection_method=None,
                ),
                data_source=data_source,
                observation_type="SCHEDULED",
                is_cancelled=False,
            )
            departures.append(departure)

        return departures

    async def is_feed_available(self, db: AsyncSession, data_source: str) -> bool:
        """Check if GTFS data is available for a data source."""
        result = await db.execute(
            select(GTFSFeedInfo.last_successful_parse_at).where(
                GTFSFeedInfo.data_source == data_source
            )
        )
        row = result.first()
        return row is not None and row[0] is not None

    async def get_feed_info(
        self, db: AsyncSession, data_source: str
    ) -> GTFSFeedInfo | None:
        """Get feed info for a data source."""
        result = await db.execute(
            select(GTFSFeedInfo).where(GTFSFeedInfo.data_source == data_source)
        )
        return result.scalar_one_or_none()

    async def _find_trip_in_source(
        self,
        db: AsyncSession,
        train_id: str,
        source: str,
        service_ids: set[str],
        match_field: str,
    ) -> Any:
        """Find a trip in a specific source by train_id or trip_id.

        Args:
            db: Database session
            train_id: The ID to search for
            source: Data source (NJT, AMTRAK, PATH, PATCO)
            service_ids: Active service IDs for the target date
            match_field: "train_id" or "trip_id"

        Returns:
            Trip row tuple or None if not found
        """
        field = GTFSTrip.train_id if match_field == "train_id" else GTFSTrip.trip_id
        result = await db.execute(
            select(
                GTFSTrip.id,
                GTFSTrip.trip_id,
                GTFSTrip.train_id,
                GTFSTrip.trip_headsign,
                GTFSRoute.route_id,
                GTFSRoute.route_short_name,
                GTFSRoute.route_long_name,
                GTFSRoute.route_color,
            )
            .join(GTFSRoute, GTFSTrip.route_id == GTFSRoute.id)
            .where(
                and_(
                    GTFSTrip.data_source == source,
                    GTFSTrip.service_id.in_(service_ids),
                    field == train_id,
                )
            )
        )
        return result.first()

    async def get_train_details(
        self,
        db: AsyncSession,
        train_id: str,
        target_date: date,
        data_source: str | None = None,
    ) -> TrainDetails | None:
        """Get train details from GTFS data for future dates.

        Args:
            db: Database session
            train_id: Train ID or GTFS trip_id to look up
            target_date: The date to get schedule for
            data_source: Optional data source filter (NJT, AMTRAK, PATH, PATCO).
                        If provided, only searches that source.
                        If not provided, uses two-phase search:
                        1. Search all sources for train_id (real train numbers)
                        2. Fall back to trip_id (GTFS internal IDs)

        Returns:
            TrainDetails if the train is found in GTFS, None otherwise.
        """
        logger.info(
            "gtfs_get_train_details",
            train_id=train_id,
            target_date=str(target_date),
            data_source=data_source,
        )

        # Normalize prefixed train IDs: strip prefix for lookup since GTFS stores without it
        # (We add prefixes for display consistency with real-time data)
        search_train_id = (
            _strip_source_prefix(train_id, data_source) if data_source else train_id
        )

        all_sources = ["NJT", "AMTRAK", "PATH", "PATCO", "LIRR", "MNR", "SUBWAY"]
        sources_to_search = [data_source] if data_source else all_sources

        # Cache service_ids per source to avoid repeated queries
        source_service_ids: dict[str, set[str]] = {}
        for source in sources_to_search:
            service_ids = await self.get_active_service_ids(db, source, target_date)
            if service_ids:
                source_service_ids[source] = service_ids

        trip_row = None
        matched_source = None

        if data_source:
            # Single source mode: try train_id first, then trip_id
            if data_source in source_service_ids:
                service_ids = source_service_ids[data_source]
                trip_row = await self._find_trip_in_source(
                    db, search_train_id, data_source, service_ids, "train_id"
                )
                if not trip_row:
                    trip_row = await self._find_trip_in_source(
                        db, search_train_id, data_source, service_ids, "trip_id"
                    )
                if trip_row:
                    matched_source = data_source
        else:
            # Two-phase search: prioritize train_id (real numbers) over trip_id (GTFS IDs)
            # Phase 1: Search all sources for train_id match
            for source, service_ids in source_service_ids.items():
                # Strip source-specific prefix (e.g., A112->112, S1-trip->trip)
                lookup_id = _strip_source_prefix(train_id, source)
                trip_row = await self._find_trip_in_source(
                    db, lookup_id, source, service_ids, "train_id"
                )
                if trip_row:
                    matched_source = source
                    break

            # Phase 2: Fall back to trip_id match
            if not trip_row:
                for source, service_ids in source_service_ids.items():
                    lookup_id = _strip_source_prefix(train_id, source)
                    trip_row = await self._find_trip_in_source(
                        db, lookup_id, source, service_ids, "trip_id"
                    )
                    if trip_row:
                        matched_source = source
                        break

        if not trip_row or not matched_source:
            logger.info(
                "gtfs_train_details_not_found",
                train_id=train_id,
                target_date=str(target_date),
                data_source=data_source,
            )
            return None

        (
            db_trip_id,
            gtfs_trip_id,  # GTFS trip_id string
            stored_train_id,  # train_id from trip_short_name (e.g., Amtrak "112")
            headsign,
            gtfs_route_id,  # GTFS route_id string
            route_short,
            route_long,
            route_color,
        ) = trip_row

        # Get all stops for this trip
        stops_result = await db.execute(
            select(
                GTFSStopTime.station_code,
                GTFSStopTime.stop_sequence,
                GTFSStopTime.arrival_time,
                GTFSStopTime.departure_time,
            )
            .where(GTFSStopTime.trip_id == db_trip_id)
            .order_by(GTFSStopTime.stop_sequence)
        )
        stop_rows = stops_result.all()

        if not stop_rows:
            logger.info(
                "gtfs_train_details_no_stops",
                train_id=train_id,
                target_date=str(target_date),
                data_source=matched_source,
            )
            return None

        # Build stops list (skip stops without mapped station codes)
        stops: list[StopDetails] = []
        for station_code, stop_sequence, arrival_time, departure_time in stop_rows:
            if not station_code:
                continue

            arrival_dt = self._parse_gtfs_time(arrival_time, target_date)
            departure_dt = self._parse_gtfs_time(departure_time, target_date)

            stops.append(
                StopDetails(
                    station=SimpleStationInfo(
                        code=station_code,
                        name=get_station_name(station_code),
                    ),
                    stop_sequence=stop_sequence or 0,
                    scheduled_arrival=arrival_dt,
                    scheduled_departure=departure_dt,
                    updated_arrival=None,
                    updated_departure=None,
                    actual_arrival=None,
                    actual_departure=None,
                    track=None,
                    track_assigned_at=None,
                    raw_status=RawStopStatus(
                        amtrak_status=None,
                        njt_departed_flag=None,
                    ),
                    has_departed_station=False,
                    predicted_arrival=None,
                    predicted_arrival_samples=None,
                )
            )

        if not stops:
            logger.info(
                "gtfs_train_details_no_mapped_stops",
                train_id=train_id,
                target_date=str(target_date),
                data_source=matched_source,
            )
            return None

        # Use stored_train_id (from trip_short_name) if available (e.g., Amtrak "112", NJT "3243")
        # Otherwise use gtfs_trip_id as fallback
        effective_train_id = stored_train_id if stored_train_id else gtfs_trip_id

        # Add "A" prefix for Amtrak to match real-time format (e.g., "112" -> "A112")
        if (
            matched_source == "AMTRAK"
            and effective_train_id
            and not effective_train_id.startswith("A")
        ):
            effective_train_id = f"A{effective_train_id}"

        # Add "L" prefix for LIRR to match real-time format (e.g., "181" -> "L181")
        if matched_source == "LIRR" and effective_train_id:
            effective_train_id = _lirr_train_id_from_gtfs(effective_train_id)

        # Add "M" prefix for MNR to match real-time format (e.g., "631700" -> "M631700")
        if matched_source == "MNR" and effective_train_id:
            effective_train_id = _mnr_train_id_from_gtfs(effective_train_id)

        # Add "S{route}-" prefix for SUBWAY (full trip_id, not truncated)
        if (
            matched_source == "SUBWAY"
            and effective_train_id
            and not effective_train_id.startswith("S")
        ):
            effective_train_id = f"S{route_short or 'X'}-{effective_train_id}"

        # Build line info
        # PATH and PATCO routes need special handling for proper line codes/colors
        if matched_source == "PATH":
            path_route_info = get_path_route_info(gtfs_route_id)
            if path_route_info:
                line_code, line_name, line_color = path_route_info
                # Ensure color has # prefix
                if not line_color.startswith("#"):
                    line_color = f"#{line_color}"
            else:
                # Fallback for unknown PATH routes
                line_code = route_short or "PATH"
                line_name = route_long or route_short or "PATH"
                line_color = f"#{route_color}" if route_color else "#666666"
        elif matched_source == "PATCO":
            patco_route_info = get_patco_route_info(gtfs_route_id)
            if patco_route_info:
                line_code, line_name, line_color = patco_route_info
                # Ensure color has # prefix
                if not line_color.startswith("#"):
                    line_color = f"#{line_color}"
            else:
                # Fallback for unknown PATCO routes
                line_code = route_short or "PATCO"
                line_name = route_long or route_short or "PATCO Speedline"
                line_color = f"#{route_color}" if route_color else "#BC0035"
        elif matched_source == "LIRR":
            from trackrat.config.stations import get_lirr_route_info

            lirr_route_info = get_lirr_route_info(gtfs_route_id)
            if lirr_route_info:
                line_code, line_name, line_color = lirr_route_info
                if not line_color.startswith("#"):
                    line_color = f"#{line_color}"
            else:
                line_code = route_short or "LIRR"
                line_name = route_long or route_short or "LIRR"
                line_color = f"#{route_color}" if route_color else "#0039A6"
        elif matched_source == "MNR":
            from trackrat.config.stations import get_mnr_route_info

            mnr_route_info = get_mnr_route_info(gtfs_route_id)
            if mnr_route_info:
                line_code, line_name, line_color = mnr_route_info
                if not line_color.startswith("#"):
                    line_color = f"#{line_color}"
            else:
                line_code = route_short or "MNR"
                line_name = route_long or route_short or "Metro-North"
                line_color = f"#{route_color}" if route_color else "#0039A6"
        else:
            # For NJT, map GTFS route_short_name to API line codes for consistency
            if matched_source == "NJT" and route_short:
                line_code = NJT_LINE_CODE_MAPPING.get(route_short, route_short)
            else:
                line_code = route_short or matched_source[:2]
            line_name = route_long or route_short or matched_source
            line_color = f"#{route_color}" if route_color else "#666666"

        # Get origin and destination from stops
        origin_stop = stops[0]
        dest_stop = stops[-1]

        # Get feed info for last_updated time
        feed_info = await self.get_feed_info(db, matched_source)
        last_updated = feed_info.last_successful_parse_at if feed_info else now_et()

        logger.info(
            "gtfs_train_details_found",
            train_id=effective_train_id,
            data_source=matched_source,
            stops_count=len(stops),
        )

        return TrainDetails(
            train_id=effective_train_id,
            journey_date=target_date,
            line=LineInfo(
                code=line_code[:10],
                name=line_name,
                color=line_color,
            ),
            route=RouteInfo(
                origin=origin_stop.station.name,
                destination=headsign or dest_stop.station.name,
                origin_code=origin_stop.station.code,
                destination_code=dest_stop.station.code,
            ),
            train_position=TrainPosition(
                last_departed_station_code=None,
                at_station_code=None,
                next_station_code=None,
                between_stations=False,
            ),
            stops=stops,
            data_freshness=DataFreshness(
                last_updated=last_updated or now_et(),
                age_seconds=int(
                    (now_et() - (last_updated or now_et())).total_seconds()
                ),
                update_count=None,
                collection_method="scheduled",
            ),
            data_source=matched_source,
            observation_type="SCHEDULED",
            raw_train_state=None,
            is_cancelled=False,
            is_completed=False,
            progress=None,
            predicted_arrival=None,
        )

    async def get_static_stop_times(
        self,
        db: AsyncSession,
        data_source: str,
        gtfs_trip_id: str,
        target_date: date,
    ) -> list[dict[str, Any]] | None:
        """Get all stops for a GTFS trip from static schedule data.

        Used by MTA collectors to backfill origin/passed stops that are
        missing from GTFS-RT feeds (e.g., LIRR drops origin terminal
        from outbound trips).

        Args:
            db: Database session
            data_source: "LIRR" or "MNR"
            gtfs_trip_id: The GTFS trip_id string from the RT feed
            target_date: Service date for time parsing and service_id lookup

        Returns:
            Ordered list of stop dicts with keys: station_code, stop_sequence,
            arrival_time (datetime), departure_time (datetime).
            None if trip not found in static data.
        """
        service_ids = await self.get_active_service_ids(db, data_source, target_date)
        if not service_ids:
            logger.warning(
                "gtfs_static_no_active_services",
                data_source=data_source,
                target_date=str(target_date),
            )
            return None

        trip_row = await self._find_trip_in_source(
            db, gtfs_trip_id, data_source, service_ids, "trip_id"
        )
        if not trip_row:
            # LIRR GTFS-RT uses date-suffix trip_ids (e.g., "6817_2026-02-24")
            # that don't exist in GTFS static. Extract the train number and
            # try matching by train_id (trip_short_name in GTFS static).
            train_number = _extract_lirr_train_number(gtfs_trip_id)
            if train_number:
                trip_row = await self._find_trip_in_source(
                    db, train_number, data_source, service_ids, "train_id"
                )
            if not trip_row:
                logger.debug(
                    "gtfs_static_trip_not_found",
                    data_source=data_source,
                    trip_id=gtfs_trip_id,
                    target_date=str(target_date),
                    service_id_count=len(service_ids),
                )
                return None

        db_trip_id = trip_row.id

        stops_result = await db.execute(
            select(
                GTFSStopTime.station_code,
                GTFSStopTime.stop_sequence,
                GTFSStopTime.arrival_time,
                GTFSStopTime.departure_time,
            )
            .where(GTFSStopTime.trip_id == db_trip_id)
            .order_by(GTFSStopTime.stop_sequence)
        )

        stop_rows = stops_result.all()
        if not stop_rows:
            return None

        stops = []
        for row in stop_rows:
            arrival_dt = self._parse_gtfs_time(row.arrival_time, target_date)
            departure_dt = self._parse_gtfs_time(row.departure_time, target_date)
            if not arrival_dt:
                continue
            stops.append(
                {
                    "station_code": row.station_code,
                    "stop_sequence": row.stop_sequence,
                    "arrival_time": arrival_dt,
                    "departure_time": departure_dt or arrival_dt,
                }
            )

        return stops if stops else None
