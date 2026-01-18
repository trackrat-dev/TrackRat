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
    get_station_name,
    map_gtfs_stop_to_station_code,
)
from trackrat.models.api import (
    DataFreshness,
    DeparturesResponse,
    LineInfo,
    StationInfo,
    TrainDeparture,
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
from trackrat.utils.time import ET, now_et

logger = get_logger(__name__)

# GTFS Feed URLs
GTFS_FEED_URLS = {
    "NJT": "https://content.njtransit.com/public/developers-resources/rail_data.zip",
    "AMTRAK": "https://content.amtrak.com/content/gtfs/GTFS.zip",
}

# Minimum hours between feed downloads (rate limiting)
GTFS_DOWNLOAD_INTERVAL_HOURS = 24

# Default line colors when not provided in GTFS
DEFAULT_LINE_COLORS = {
    "NJT": "#003DA5",  # NJ Transit blue
    "AMTRAK": "#004B87",  # Amtrak blue
}


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
            feed_info.error_message = error_msg
            await db.commit()
            return False

        except Exception as e:
            error_msg = f"Error processing GTFS: {e}"
            logger.error(error_msg, data_source=data_source, exc_info=True)
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
                route = GTFSRoute(
                    data_source=data_source,
                    route_id=row.get("route_id", ""),
                    route_short_name=row.get("route_short_name"),
                    route_long_name=row.get("route_long_name"),
                    route_color=row.get("route_color"),
                )
                db.add(route)
                await db.flush()
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
                if not service_id:
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

        with zf.open("calendar_dates.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            for row in reader:
                service_id = row.get("service_id", "")
                date_str = row.get("date", "")
                exception_type = row.get("exception_type", "")

                if not service_id or not date_str or not exception_type:
                    continue

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
                trip_id = row.get("trip_id", "")
                route_id = row.get("route_id", "")

                if not trip_id or route_id not in routes:
                    continue

                # Try to extract train_id from trip_headsign or trip_short_name
                headsign = row.get("trip_headsign", "")
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
                        trips[batch_trip_ids[i]] = t.id
                    batch = []
                    batch_trip_ids = []

        # Add remaining
        if batch:
            db.add_all(batch)
            await db.flush()
            for i, t in enumerate(batch):
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
                trip_id = row.get("trip_id", "")
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

    async def get_scheduled_departures(
        self,
        db: AsyncSession,
        from_station: str,
        to_station: str | None,
        target_date: date,
        limit: int = 50,
    ) -> DeparturesResponse:
        """Get scheduled departures from GTFS data for a future date.

        Args:
            db: Database session
            from_station: Departure station code
            to_station: Destination station code (optional)
            target_date: The date to get schedules for
            limit: Maximum number of results

        Returns:
            DeparturesResponse with scheduled trains
        """
        departures: list[TrainDeparture] = []

        # Get active service IDs for both sources
        njt_services = await self.get_active_service_ids(db, "NJT", target_date)
        amtrak_services = await self.get_active_service_ids(db, "AMTRAK", target_date)

        all_services = {
            "NJT": njt_services,
            "AMTRAK": amtrak_services,
        }

        for data_source, service_ids in all_services.items():
            if not service_ids:
                continue

            source_departures = await self._query_departures_for_source(
                db, data_source, service_ids, from_station, to_station, target_date
            )
            departures.extend(source_departures)

        # Sort by departure time
        # Use timezone-aware datetime for comparison (scheduled_time is ET-localized)
        max_dt = ET.localize(datetime.max.replace(year=9999, month=12, day=31, hour=23, minute=59))
        departures.sort(key=lambda d: d.departure.scheduled_time or max_dt)

        # Apply limit
        departures = departures[:limit]

        return DeparturesResponse(
            departures=departures,
            metadata={
                "from_station": {
                    "code": from_station,
                    "name": get_station_name(from_station),
                },
                "to_station": {
                    "code": to_station,
                    "name": get_station_name(to_station),
                }
                if to_station
                else None,
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
                GTFSTrip.train_id,
                GTFSTrip.trip_headsign,
                GTFSTrip.service_id,
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
                    GTFSStopTime.station_code == from_station,
                )
            )
            .order_by(GTFSStopTime.departure_time)
        )

        trips_data = result.all()

        # Pre-fetch destination station data in one query to avoid N+1 problem
        to_station_data: dict[int, tuple[str, int]] = {}  # trip_id -> (arrival_time, sequence)
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
                        GTFSStopTime.station_code == to_station,
                    )
                )
            )
            for dest_row in dest_result.all():
                to_station_data[dest_row[0]] = (dest_row[1], dest_row[2])

        for row in trips_data:
            (
                trip_id,
                train_id,
                headsign,
                service_id,
                route_short,
                route_long,
                route_color,
                dep_time_str,
                dep_sequence,
            ) = row

            # If to_station specified, verify this trip also stops there after from_station
            arrival_time_str = None
            if to_station:
                dest_info = to_station_data.get(trip_id)
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
            line_code = route_short or data_source[:2]
            line_name = route_long or route_short or data_source
            line_color = f"#{route_color}" if route_color else DEFAULT_LINE_COLORS.get(
                data_source, "#666666"
            )

            departure = TrainDeparture(
                train_id=train_id or headsign or "Unknown",
                journey_date=target_date,
                line=LineInfo(
                    code=line_code[:3],
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
                arrival=StationInfo(
                    code=to_station,
                    name=get_station_name(to_station),
                    scheduled_time=arrival_dt,
                    updated_time=None,
                    actual_time=None,
                    track=None,
                )
                if to_station and arrival_dt
                else None,
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
