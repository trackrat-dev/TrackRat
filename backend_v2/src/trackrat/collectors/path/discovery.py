"""
PATH train discovery collector for TrackRat V2.

Discovers active PATH trains using the RidePATH API (official PATH API).
This provides real-time predictions at all 13 stations for reliable discovery.
"""

from datetime import timedelta
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.base import BaseDiscoveryCollector
from trackrat.collectors.path.ridepath_client import PathArrival, RidePathClient
from trackrat.config.stations import (
    PATH_DISCOVERY_STATIONS,
    get_path_stops_by_origin_destination,
    get_station_name,
)
from trackrat.db.engine import get_session
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import now_et

logger = get_logger(__name__)


# Mapping from headsign keywords to station codes
# These are SUBSTRINGS that will be matched against the headsign
HEADSIGN_TO_STATION_MAP: dict[str, str] = {
    "world trade": "PWC",
    "wtc": "PWC",
    "hoboken": "PHO",
    "newark": "PNK",
    "journal square": "PJS",
    "jsq": "PJS",
    "33rd": "P33",
    "33 st": "P33",
    "grove": "PGR",
    "harrison": "PHR",
    "exchange": "PEX",
    "newport": "PNP",
    "christopher": "PCH",
    "9th": "P9S",
    "14th": "P14",
    "23rd": "P23",
}

# Mapping from headsign to line info (line_code, line_name, line_color)
# Based on PATH route patterns
HEADSIGN_TO_LINE_INFO: dict[str, tuple[str, str, str]] = {
    "hoboken": ("HOB-33", "Hoboken - 33rd Street", "#4d92fb"),
    "33rd street": ("HOB-33", "Hoboken - 33rd Street", "#4d92fb"),
    "33rd st": ("HOB-33", "Hoboken - 33rd Street", "#4d92fb"),
    "world trade center": ("NWK-WTC", "Newark - World Trade Center", "#d93a30"),
    "wtc": ("NWK-WTC", "Newark - World Trade Center", "#d93a30"),
    "newark": ("NWK-WTC", "Newark - World Trade Center", "#d93a30"),
    "journal square": ("JSQ-33", "Journal Square - 33rd Street", "#ff9900"),
    "jsq": ("JSQ-33", "Journal Square - 33rd Street", "#ff9900"),
}


def _headsign_matches_station(headsign: str, station_code: str) -> bool:
    """Check if a headsign indicates the train's destination is this station.

    Used to detect trains that have ARRIVED at their destination (skip these).

    Args:
        headsign: Train headsign (e.g., "33rd Street", "World Trade Center")
        station_code: Internal station code (e.g., "P33", "PWC")

    Returns:
        True if the headsign indicates the train is going TO this station
    """
    if not headsign:
        return False

    headsign_lower = headsign.lower().strip()

    for keyword, mapped_station in HEADSIGN_TO_STATION_MAP.items():
        if keyword in headsign_lower and mapped_station == station_code:
            return True

    return False


def _get_destination_station_from_headsign(headsign: str) -> str | None:
    """Get destination station code from headsign using substring matching.

    Finds the keyword that appears EARLIEST in the headsign string.
    This correctly handles "Journal Square via Hoboken" → PJS (not PHO).

    Args:
        headsign: Train headsign (e.g., "Journal Square via Hoboken")

    Returns:
        Station code if matched, None otherwise
    """
    if not headsign:
        return None

    headsign_lower = headsign.lower().strip()

    # Find all matching keywords and their positions
    matches: list[tuple[int, str]] = []
    for keyword, station_code in HEADSIGN_TO_STATION_MAP.items():
        pos = headsign_lower.find(keyword)
        if pos >= 0:
            matches.append((pos, station_code))

    if not matches:
        return None

    # Return station code for the keyword that appears first in the headsign
    matches.sort(key=lambda x: x[0])
    return matches[0][1]


def _get_line_info_from_headsign(headsign: str) -> tuple[str, str, str]:
    """Get line code, name, and color from headsign.

    Args:
        headsign: Train headsign (e.g., "33rd Street", "Hoboken")

    Returns:
        Tuple of (line_code, line_name, line_color)
    """
    if not headsign:
        return ("PATH", "PATH", "#4d92fb")

    headsign_lower = headsign.lower().strip()

    for key, info in HEADSIGN_TO_LINE_INFO.items():
        if key in headsign_lower:
            return info

    # Default fallback
    return ("PATH", f"PATH to {headsign}", "#4d92fb")


def _generate_path_train_id(
    origin_station: str, headsign: str, departure_time: Any
) -> str:
    """Generate a stable train ID for PATH trains.

    Uses origin station, destination, and departure time to create a unique ID.
    This approach works without Transiter's trip_id.

    Args:
        origin_station: Station code where train departs (e.g., 'PHO')
        headsign: Train destination (e.g., '33rd Street')
        departure_time: Scheduled departure datetime

    Returns:
        Generated train ID (e.g., 'PATH_PHO_33rd_1705500000')
    """
    # Normalize headsign for ID
    dest_short = headsign[:10].replace(" ", "").lower() if headsign else "unk"

    # Use unix timestamp for uniqueness
    ts = int(departure_time.timestamp()) if departure_time else 0

    return f"PATH_{origin_station}_{dest_short}_{ts}"


class PathDiscoveryCollector(BaseDiscoveryCollector):
    """Discovers active PATH trains from RidePATH API."""

    def __init__(self, client: RidePathClient | None = None) -> None:
        """Initialize the PATH discovery collector.

        Args:
            client: Optional RidePATH client (creates one if not provided)
        """
        self.client = client or RidePathClient()
        self._owns_client = client is None

    async def discover_trains(self) -> list[str]:
        """Discover active PATH train IDs from all discovery stations.

        Returns:
            List of discovered train IDs
        """
        discovered_ids: set[str] = set()

        try:
            # Get all arrivals from RidePATH API (single call for all stations)
            all_arrivals = await self.client.get_all_arrivals()

            # Filter for discovery stations and departing trains
            for arrival in all_arrivals:
                if arrival.station_code not in PATH_DISCOVERY_STATIONS:
                    continue

                # Skip trains arriving at this station (destination matches station)
                if _headsign_matches_station(arrival.headsign, arrival.station_code):
                    continue

                train_id = _generate_path_train_id(
                    arrival.station_code, arrival.headsign, arrival.arrival_time
                )
                discovered_ids.add(train_id)

        except Exception as e:
            logger.error("path_discovery_failed", error=str(e))

        return list(discovered_ids)

    async def run(self) -> dict[str, Any]:
        """Run the discovery collector with a database session.

        Returns:
            Collection results summary
        """
        try:
            async with get_session() as session:
                return await self.collect(session)
        finally:
            if self._owns_client:
                await self.client.close()

    async def collect(self, session: AsyncSession) -> dict[str, Any]:
        """Run discovery using RidePATH API.

        Args:
            session: Database session

        Returns:
            Discovery results summary
        """
        logger.info("discovery.path.started", stations=PATH_DISCOVERY_STATIONS)

        try:
            # Single API call gets all arrivals
            all_arrivals = await self.client.get_all_arrivals()
        except Exception as e:
            logger.error("path_ridepath_api_failed", error=str(e))
            return {
                "data_source": "PATH",
                "stations_processed": 0,
                "total_arrivals": 0,
                "total_new": 0,
                "error": str(e),
            }

        total_arrivals = 0
        total_new = 0
        station_results: dict[str, dict[str, Any]] = {
            station: {"arrivals_found": 0, "new_journeys": 0}
            for station in PATH_DISCOVERY_STATIONS
        }

        # Group arrivals by station
        for arrival in all_arrivals:
            if arrival.station_code not in PATH_DISCOVERY_STATIONS:
                continue

            station_results[arrival.station_code]["arrivals_found"] += 1
            total_arrivals += 1

            # Skip trains arriving at their destination
            if _headsign_matches_station(arrival.headsign, arrival.station_code):
                logger.debug(
                    "path_skip_arriving_train",
                    station=arrival.station_code,
                    headsign=arrival.headsign,
                )
                continue

            # Process this departure
            created = await self._process_arrival(session, arrival)
            if created:
                station_results[arrival.station_code]["new_journeys"] += 1
                total_new += 1

        await session.commit()

        logger.info(
            "discovery.path.completed",
            total_arrivals=total_arrivals,
            total_new=total_new,
            stations_processed=len(PATH_DISCOVERY_STATIONS),
        )

        return {
            "data_source": "PATH",
            "stations_processed": len(PATH_DISCOVERY_STATIONS),
            "total_arrivals": total_arrivals,
            "total_new": total_new,
            "station_results": station_results,
        }

    async def _process_arrival(
        self,
        session: AsyncSession,
        arrival: PathArrival,
    ) -> bool:
        """Process a single arrival and create/update journey record.

        With RidePATH, we discover trains at their ORIGIN station (departing).
        The discovery station IS the origin, and headsign IS the destination.

        Args:
            session: Database session
            arrival: Arrival data from RidePATH

        Returns:
            True if a new journey was created, False if existing/skipped
        """
        origin_station = arrival.station_code
        destination = arrival.headsign
        departure_time = arrival.arrival_time  # When train departs this station

        if not departure_time:
            logger.debug("path_arrival_no_time", station=origin_station)
            return False

        journey_date = departure_time.date()

        # Get line info from headsign
        line_code, line_name, line_color = _get_line_info_from_headsign(destination)

        # Use line color from API if available
        if arrival.line_color:
            # RidePATH may return multiple colors separated by comma
            color = arrival.line_color.split(",")[0]
            if not color.startswith("#"):
                color = f"#{color}"
            line_color = color

        # Generate train_id
        train_id = _generate_path_train_id(origin_station, destination, departure_time)

        # Check if journey already exists by exact train_id
        stmt = select(TrainJourney).where(
            TrainJourney.train_id == train_id,
            TrainJourney.journey_date == journey_date,
            TrainJourney.data_source == "PATH",
        )
        existing = await session.scalar(stmt)

        if existing:
            existing.last_updated_at = now_et()
            return False

        # Secondary deduplication: Check for existing journey with same characteristics
        existing_by_schedule = await self._find_matching_journey(
            session,
            journey_date=journey_date,
            line_code=line_code,
            origin_station=origin_station,
            scheduled_departure=departure_time,
            destination=destination,
        )

        if existing_by_schedule:
            existing_by_schedule.last_updated_at = now_et()
            logger.debug(
                "path_matched_existing_journey",
                new_train_id=train_id,
                existing_train_id=existing_by_schedule.train_id,
                line_code=line_code,
                origin=origin_station,
            )
            return False

        # Get destination station code from headsign (substring matching)
        destination_station = _get_destination_station_from_headsign(destination)

        # Get route stops from hardcoded PATH routes (no GTFS dependency)
        route_stops = None
        if destination_station:
            route_stops = get_path_stops_by_origin_destination(
                origin_station, destination_station
            )

        # PATH average travel time: ~3 minutes per segment
        minutes_per_segment = 3

        if route_stops and len(route_stops) >= 2:
            terminal_station = route_stops[-1]
            total_travel_minutes = (len(route_stops) - 1) * minutes_per_segment
            terminal_arrival = departure_time + timedelta(minutes=total_travel_minutes)
            has_complete_journey = True
            stops_count = len(route_stops)
        else:
            # No route found - create journey with origin and destination only
            terminal_station = destination_station or origin_station
            terminal_arrival = departure_time + timedelta(minutes=20)  # Estimate
            has_complete_journey = False
            stops_count = 2 if destination_station else 1

        # Create new journey
        journey = TrainJourney(
            train_id=train_id,
            journey_date=journey_date,
            line_code=line_code,
            line_name=line_name,
            line_color=line_color,
            destination=destination,
            origin_station_code=origin_station,
            terminal_station_code=terminal_station,
            scheduled_departure=departure_time,
            scheduled_arrival=terminal_arrival,
            data_source="PATH",
            observation_type="OBSERVED",
            first_seen_at=now_et(),
            last_updated_at=now_et(),
            has_complete_journey=has_complete_journey,
            stops_count=stops_count,
            update_count=1,
        )

        session.add(journey)
        await session.flush()

        # Create stops
        if route_stops and len(route_stops) >= 2:
            for sequence, station_code in enumerate(route_stops, start=1):
                is_origin = sequence == 1
                is_terminus = sequence == len(route_stops)

                # Calculate estimated times based on position in route
                # Each segment takes ~3 minutes
                minutes_from_origin = (sequence - 1) * minutes_per_segment
                stop_time = departure_time + timedelta(minutes=minutes_from_origin)

                stop = JourneyStop(
                    journey_id=journey.id,
                    station_code=station_code,
                    station_name=get_station_name(station_code),
                    stop_sequence=sequence,
                    scheduled_arrival=stop_time if not is_origin else None,
                    scheduled_departure=stop_time if not is_terminus else None,
                    updated_arrival=stop_time if not is_origin else None,
                    updated_departure=stop_time if not is_terminus else None,
                )
                session.add(stop)
        else:
            # Create minimal stops: origin and destination
            origin_stop = JourneyStop(
                journey_id=journey.id,
                station_code=origin_station,
                station_name=get_station_name(origin_station),
                stop_sequence=1,
                scheduled_departure=departure_time,
                updated_departure=departure_time,
            )
            session.add(origin_stop)

            if destination_station and destination_station != origin_station:
                dest_stop = JourneyStop(
                    journey_id=journey.id,
                    station_code=destination_station,
                    station_name=get_station_name(destination_station),
                    stop_sequence=2,
                    scheduled_arrival=terminal_arrival,
                    updated_arrival=terminal_arrival,
                )
                session.add(dest_stop)

        logger.debug(
            "path_journey_created",
            train_id=train_id,
            journey_date=journey_date,
            line=line_code,
            origin=origin_station,
            destination=destination,
            departure=departure_time.isoformat(),
            stops=stops_count,
            has_complete_route=route_stops is not None,
        )

        return True

    async def _find_matching_journey(
        self,
        session: AsyncSession,
        journey_date: Any,
        line_code: str,
        origin_station: str,
        scheduled_departure: Any,
        destination: str,
        time_tolerance_minutes: int = 5,
    ) -> TrainJourney | None:
        """Find an existing journey that matches the given characteristics.

        Matching criteria:
        - Same journey_date
        - Same line_code
        - Same origin_station
        - Same destination (headsign)
        - Scheduled departure within ±time_tolerance_minutes

        Args:
            session: Database session
            journey_date: Date of the journey
            line_code: PATH line code (e.g., "HOB-33")
            origin_station: Origin station code
            scheduled_departure: Scheduled departure datetime
            destination: Destination headsign
            time_tolerance_minutes: Max minutes difference for time matching

        Returns:
            Matching TrainJourney if found, None otherwise
        """
        if not scheduled_departure:
            return None

        time_window = timedelta(minutes=time_tolerance_minutes)
        time_min = scheduled_departure - time_window
        time_max = scheduled_departure + time_window

        stmt = select(TrainJourney).where(
            and_(
                TrainJourney.data_source == "PATH",
                TrainJourney.journey_date == journey_date,
                TrainJourney.line_code == line_code,
                TrainJourney.origin_station_code == origin_station,
                TrainJourney.destination == destination,
                TrainJourney.scheduled_departure >= time_min,
                TrainJourney.scheduled_departure <= time_max,
            )
        )

        return await session.scalar(stmt)
