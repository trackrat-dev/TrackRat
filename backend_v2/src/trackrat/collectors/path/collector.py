"""
Unified PATH train collector for TrackRat V2.

Combines discovery and journey tracking into a single task that:
1. Discovers new trains at ALL stations (including mid-route)
2. Updates existing journeys with real-time arrival data

Runs every 4 minutes for responsive tracking with single API call.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.path.ridepath_client import PathArrival, RidePathClient
from trackrat.collectors.path.segment_times import (
    SegmentTimesMap,
    get_cumulative_time,
    get_segment_times,
)
from trackrat.config.stations import (
    PATH_ROUTE_STOPS,
    get_path_route_and_stops,
    get_station_name,
)
from trackrat.db.engine import get_session
from trackrat.models.database import JourneySnapshot, JourneyStop, TrainJourney
from trackrat.services.transit_analyzer import TransitAnalyzer
from trackrat.utils.locks import with_train_lock
from trackrat.utils.time import normalize_to_et, now_et

logger = get_logger(__name__)


# =============================================================================
# HEADSIGN MAPPING CONSTANTS
# =============================================================================

# Mapping from headsign keywords to station codes (SUBSTRINGS matched against headsign)
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
HEADSIGN_TO_LINE_INFO: dict[str, tuple[str, str, str]] = {
    "via hoboken": ("JSQ-33H", "Journal Square - 33rd Street via Hoboken", "#ff9900"),
    "hoboken": ("HOB-33", "Hoboken - 33rd Street", "#4d92fb"),
    "33rd street": ("HOB-33", "Hoboken - 33rd Street", "#4d92fb"),
    "33rd st": ("HOB-33", "Hoboken - 33rd Street", "#4d92fb"),
    "world trade center": ("NWK-WTC", "Newark - World Trade Center", "#d93a30"),
    "wtc": ("NWK-WTC", "Newark - World Trade Center", "#d93a30"),
    "newark": ("NWK-WTC", "Newark - World Trade Center", "#d93a30"),
    "journal square": ("JSQ-33", "Journal Square - 33rd Street", "#ff9900"),
    "jsq": ("JSQ-33", "Journal Square - 33rd Street", "#ff9900"),
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


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


def _headsign_matches_station(headsign: str, station_code: str) -> bool:
    """Check if a headsign indicates the train's PRIMARY destination is this station.

    Used to detect trains that have ARRIVED at their destination (skip these).

    For headsigns like "33rd Street via Hoboken", only P33 (33rd Street) is the
    destination. PHO (Hoboken) is just an intermediate stop and should NOT match.

    Args:
        headsign: Train headsign (e.g., "33rd Street", "Journal Square via Hoboken")
        station_code: Internal station code (e.g., "P33", "PWC")

    Returns:
        True if the headsign's PRIMARY destination matches this station
    """
    primary_destination = _get_destination_station_from_headsign(headsign)
    return primary_destination == station_code


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

    Args:
        origin_station: Station code where train departs (e.g., 'PHO')
        headsign: Train destination (e.g., '33rd Street')
        departure_time: Scheduled departure datetime

    Returns:
        Generated train ID (e.g., 'PATH_PHO_33rd_1705500000')
    """
    dest_short = headsign[:10].replace(" ", "").lower() if headsign else "unk"
    ts = int(departure_time.timestamp()) if departure_time else 0
    return f"PATH_{origin_station}_{dest_short}_{ts}"


def _normalize_headsign(headsign: str) -> str:
    """Normalize headsign for matching between journey and API data.

    Handles variations like:
    - "World Trade Center" vs "WTC"
    - "33rd Street" vs "33rd Street via Hoboken"

    Args:
        headsign: Raw headsign string

    Returns:
        Normalized headsign for comparison
    """
    if not headsign:
        return ""

    h = headsign.lower().strip()

    if "world trade" in h or h == "wtc":
        return "world_trade_center"
    if "33rd" in h or "33 st" in h or "33s" in h:
        return "33rd_street"
    if "journal" in h:
        return "journal_square"
    if "hoboken" in h:
        return "hoboken"
    if "newark" in h:
        return "newark"
    if "grove" in h:
        return "grove_street"
    if "harrison" in h:
        return "harrison"

    return h.replace(" ", "_")


def _infer_origin_station(
    current_station: str,
    destination_station: str,
) -> str:
    """Infer the origin station for a train seen mid-route.

    Finds all routes containing both current_station and destination_station
    (in either direction), then picks the one where current_station is closest
    to the start (giving us the most complete journey).

    Args:
        current_station: Station code where the train was seen
        destination_station: Train's destination station code

    Returns:
        Origin station code (first stop of the best matching route),
        or current_station if no route found
    """
    matching_routes: list[tuple[str, list[str], int]] = []

    for route_id, stops in PATH_ROUTE_STOPS.items():
        if current_station not in stops or destination_station not in stops:
            continue

        current_idx = stops.index(current_station)
        dest_idx = stops.index(destination_station)

        if current_idx < dest_idx:
            # Forward direction
            matching_routes.append((route_id, stops, current_idx))
        elif current_idx > dest_idx:
            # Reverse direction - flip the stops so origin is first
            reversed_stops = list(reversed(stops))
            rev_current_idx = reversed_stops.index(current_station)
            matching_routes.append((route_id, reversed_stops, rev_current_idx))

    if not matching_routes:
        # No matching route - use current station as origin
        return current_station

    if len(matching_routes) == 1:
        # Unambiguous - return first stop of this route
        return matching_routes[0][1][0]

    # Multiple routes possible - pick the one where current_station
    # is closest to the start (most complete journey to track)
    best_route = min(matching_routes, key=lambda r: r[2])
    return best_route[1][0]


# =============================================================================
# UNIFIED PATH COLLECTOR
# =============================================================================


class PathCollector:
    """Unified PATH collector - discovers and updates in one pass."""

    def __init__(self, client: RidePathClient | None = None) -> None:
        """Initialize the PATH collector.

        Args:
            client: Optional RidePATH client (creates one if not provided)
        """
        self.client = client or RidePathClient()
        self._owns_client = client is None

    async def run(self) -> dict[str, Any]:
        """Main entry point with session management.

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
        """Run unified PATH collection.

        Single API call serves both discovery and updates.

        Args:
            session: Database session

        Returns:
            Collection results summary
        """
        logger.info("path_collection_started")

        # === SINGLE API CALL ===
        try:
            arrivals = await self.client.get_all_arrivals()
        except Exception as e:
            logger.error("path_api_failed", error=str(e))
            return {
                "data_source": "PATH",
                "error": str(e),
                "arrivals_fetched": 0,
                "new_journeys": 0,
                "updated": 0,
                "completed": 0,
            }

        # === LOAD GTFS SEGMENT TIMES ===
        segment_times = await get_segment_times(session)

        # === PHASE 1: DISCOVERY ===
        discovery_stats = await self._discover_trains(session, arrivals, segment_times)

        # === PHASE 2: UPDATES ===
        update_stats = await self._update_journeys(session, arrivals, segment_times)

        await session.commit()

        logger.info(
            "path_collection_completed",
            arrivals_fetched=len(arrivals),
            new_journeys=discovery_stats["new_journeys"],
            journeys_updated=update_stats["updated"],
            journeys_completed=update_stats["completed"],
        )

        return {
            "data_source": "PATH",
            "arrivals_fetched": len(arrivals),
            **discovery_stats,
            **update_stats,
        }

    # =========================================================================
    # PHASE 1: DISCOVERY
    # =========================================================================

    async def _discover_trains(
        self,
        session: AsyncSession,
        arrivals: list[PathArrival],
        segment_times: SegmentTimesMap,
    ) -> dict[str, Any]:
        """Discovery phase - create journeys for new trains.

        Processes arrivals at ALL stations, not just terminus stations.
        Skips trains that are arriving at their destination.

        Args:
            session: Database session
            arrivals: All arrivals from API
            segment_times: GTFS-based segment travel times

        Returns:
            Discovery statistics
        """
        total_arrivals = 0
        new_journeys = 0
        station_results: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"arrivals_found": 0, "new_journeys": 0}
        )

        for arrival in arrivals:
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

            # Process this departure (may be at terminus or mid-route)
            created = await self._process_arrival_for_discovery(
                session, arrival, segment_times
            )
            if created:
                station_results[arrival.station_code]["new_journeys"] += 1
                new_journeys += 1

        return {
            "discovery_arrivals": total_arrivals,
            "new_journeys": new_journeys,
            "station_results": station_results,
        }

    async def _process_arrival_for_discovery(
        self,
        session: AsyncSession,
        arrival: PathArrival,
        segment_times: SegmentTimesMap,
    ) -> bool:
        """Process a single arrival and create journey record if new.

        Handles both terminus discovery (train starting its journey) and
        mid-route discovery (train already in progress). For mid-route,
        infers the true origin and marks earlier stops as departed.

        Args:
            session: Database session
            arrival: Arrival data from RidePATH
            segment_times: GTFS-based segment travel times

        Returns:
            True if a new journey was created, False if existing/skipped
        """
        discovered_at_station = arrival.station_code
        destination_headsign = arrival.headsign
        discovered_arrival_time = arrival.arrival_time

        if not discovered_arrival_time:
            return False

        journey_date = discovered_arrival_time.date()

        # Get destination station code from headsign
        destination_station = _get_destination_station_from_headsign(
            destination_headsign
        )
        if not destination_station:
            logger.debug(
                "path_skip_unknown_destination",
                station=discovered_at_station,
                headsign=destination_headsign,
            )
            return False

        # Infer the true origin station (may be different if discovered mid-route)
        origin_station = _infer_origin_station(
            discovered_at_station, destination_station
        )

        # Get full route (with route_id) from origin to destination
        route_result = get_path_route_and_stops(origin_station, destination_station)

        if not route_result or len(route_result[1]) < 2:
            logger.debug(
                "path_skip_no_route",
                origin=origin_station,
                destination=destination_station,
            )
            return False

        route_id, route_stops = route_result

        # Calculate origin departure time by working backwards from discovery station
        if discovered_at_station in route_stops:
            stops_from_origin = route_stops.index(discovered_at_station)
            minutes_from_origin = get_cumulative_time(
                segment_times, route_stops, 0, stops_from_origin, route_id
            )
            origin_departure_time = discovered_arrival_time - timedelta(
                minutes=minutes_from_origin
            )
        else:
            # Discovery station not in route (shouldn't happen) - use arrival time
            origin_departure_time = discovered_arrival_time

        # Get line info from headsign
        line_code, line_name, line_color = _get_line_info_from_headsign(
            destination_headsign
        )

        # Use line color from API if available
        if arrival.line_color:
            color = arrival.line_color.split(",")[0]
            if not color.startswith("#"):
                color = f"#{color}"
            line_color = color

        # Generate train_id using ORIGIN station and origin departure time
        # This ensures consistent deduplication regardless of where train is discovered
        train_id = _generate_path_train_id(
            origin_station, destination_headsign, origin_departure_time
        )

        # Check if journey already exists by exact train_id
        # Use FOR UPDATE SKIP LOCKED to prevent duplicate creation during concurrent discovery
        stmt = (
            select(TrainJourney)
            .where(
                TrainJourney.train_id == train_id,
                TrainJourney.journey_date == journey_date,
                TrainJourney.data_source == "PATH",
            )
            .with_for_update(skip_locked=True)
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
            scheduled_departure=origin_departure_time,
            destination=destination_headsign,
        )

        if existing_by_schedule:
            existing_by_schedule.last_updated_at = now_et()
            return False

        # Calculate terminal arrival time using GTFS segment times
        terminal_station = route_stops[-1]
        total_travel_minutes = get_cumulative_time(
            segment_times, route_stops, 0, len(route_stops) - 1, route_id
        )
        terminal_arrival = origin_departure_time + timedelta(
            minutes=total_travel_minutes
        )

        # Create new journey
        journey = TrainJourney(
            train_id=train_id,
            journey_date=journey_date,
            line_code=line_code,
            line_name=line_name,
            line_color=line_color,
            destination=destination_headsign,
            origin_station_code=origin_station,
            terminal_station_code=terminal_station,
            scheduled_departure=origin_departure_time,
            scheduled_arrival=terminal_arrival,
            data_source="PATH",
            observation_type="OBSERVED",
            first_seen_at=now_et(),
            last_updated_at=now_et(),
            has_complete_journey=True,
            stops_count=len(route_stops),
            update_count=1,
        )

        session.add(journey)
        await session.flush()

        # Create stops (marking earlier ones as departed if mid-route discovery)
        await self._create_journey_stops(
            session,
            journey,
            route_stops,
            origin_departure_time,
            destination_station,
            discovered_at_station=discovered_at_station,
            segment_times=segment_times,
            route_id=route_id,
        )

        is_mid_route = origin_station != discovered_at_station
        logger.debug(
            "path_journey_created",
            train_id=train_id,
            line=line_code,
            origin=origin_station,
            destination=destination_headsign,
            stops=len(route_stops),
            discovered_at=discovered_at_station,
            mid_route=is_mid_route,
        )

        return True

    async def _create_journey_stops(
        self,
        session: AsyncSession,
        journey: TrainJourney,
        route_stops: list[str] | None,
        departure_time: Any,
        destination_station: str | None,
        discovered_at_station: str | None = None,
        segment_times: SegmentTimesMap | None = None,
        route_id: str | None = None,
    ) -> None:
        """Create journey stop records.

        For mid-route discoveries, marks stops before the discovery station
        as already departed with inferred times.

        Args:
            session: Database session
            journey: Parent journey
            route_stops: List of station codes in order, or None
            departure_time: Departure time from origin
            destination_station: Destination station code
            discovered_at_station: Station where train was discovered (for mid-route)
            segment_times: GTFS-based segment travel times
            route_id: GTFS route ID for segment time lookup
        """
        if segment_times is None:
            segment_times = {}

        if route_stops and len(route_stops) >= 2:
            # Find the index of the discovery station for mid-route handling
            discovered_idx = None
            if discovered_at_station and discovered_at_station in route_stops:
                discovered_idx = route_stops.index(discovered_at_station)

            for sequence, station_code in enumerate(route_stops, start=1):
                is_origin = sequence == 1
                is_terminus = sequence == len(route_stops)
                stop_idx = sequence - 1  # 0-based index
                minutes_from_origin = get_cumulative_time(
                    segment_times, route_stops, 0, stop_idx, route_id
                )
                stop_time = departure_time + timedelta(minutes=minutes_from_origin)

                # Determine if this stop is before the discovery station (already passed)
                is_before_discovery = (
                    discovered_idx is not None and stop_idx < discovered_idx
                )

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

                # Mark stops before discovery as already departed
                if is_before_discovery:
                    stop.has_departed_station = True
                    stop.actual_arrival = stop.scheduled_arrival
                    stop.actual_departure = stop.scheduled_departure
                    stop.departure_source = "inferred_from_discovery"

                session.add(stop)
        else:
            # Create minimal stops: origin and destination
            origin_code = journey.origin_station_code or ""
            origin_stop = JourneyStop(
                journey_id=journey.id,
                station_code=origin_code,
                station_name=get_station_name(origin_code) if origin_code else "",
                stop_sequence=1,
                scheduled_departure=departure_time,
                updated_departure=departure_time,
            )
            session.add(origin_stop)

            if (
                destination_station
                and destination_station != journey.origin_station_code
            ):
                terminal_arrival = departure_time + timedelta(minutes=20)
                dest_stop = JourneyStop(
                    journey_id=journey.id,
                    station_code=destination_station,
                    station_name=get_station_name(destination_station),
                    stop_sequence=2,
                    scheduled_arrival=terminal_arrival,
                    updated_arrival=terminal_arrival,
                )
                session.add(dest_stop)

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

        Args:
            session: Database session
            journey_date: Date of the journey
            line_code: PATH line code
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

        stmt = (
            select(TrainJourney)
            .where(
                and_(
                    TrainJourney.data_source == "PATH",
                    TrainJourney.journey_date == journey_date,
                    TrainJourney.line_code == line_code,
                    TrainJourney.origin_station_code == origin_station,
                    TrainJourney.scheduled_departure >= time_min,
                    TrainJourney.scheduled_departure <= time_max,
                )
            )
            .with_for_update(skip_locked=True)
        )

        candidates = (await session.scalars(stmt)).all()

        # Filter by normalized destination to handle headsign variants
        normalized_dest = _normalize_headsign(destination)
        for candidate in candidates:
            if _normalize_headsign(candidate.destination) == normalized_dest:
                return candidate

        return None

    # =========================================================================
    # PHASE 2: UPDATES
    # =========================================================================

    async def _update_journeys(
        self,
        session: AsyncSession,
        arrivals: list[PathArrival],
        segment_times: SegmentTimesMap,
    ) -> dict[str, Any]:
        """Update phase - refresh active journeys with arrival data.

        Args:
            session: Database session
            arrivals: All arrivals from API
            segment_times: GTFS-based segment travel times

        Returns:
            Update statistics
        """
        today = now_et().date()

        # Get all active PATH journeys
        result = await session.scalars(
            select(TrainJourney).where(
                TrainJourney.data_source == "PATH",
                TrainJourney.journey_date == today,
                TrainJourney.is_completed == False,  # noqa: E712
                TrainJourney.is_expired == False,  # noqa: E712
                TrainJourney.is_cancelled == False,  # noqa: E712
            )
        )
        journeys = list(result.all())

        if not journeys:
            return {"updated": 0, "completed": 0, "errors": 0}

        # Group arrivals by normalized headsign AND line color
        # This prevents cross-train matching when multiple lines serve same destination
        arrivals_by_headsign_color: dict[str, list[PathArrival]] = defaultdict(list)
        for arrival in arrivals:
            headsign_key = _normalize_headsign(arrival.headsign)
            # Normalize line color: remove # prefix and lowercase
            color = (arrival.line_color or "").split(",")[0].lstrip("#").lower()
            key = f"{headsign_key}:{color}"
            arrivals_by_headsign_color[key].append(arrival)
            # Also add to headsign-only key as fallback
            arrivals_by_headsign_color[headsign_key].append(arrival)

        updated = 0
        completed = 0
        errors = 0

        for journey in journeys:
            try:
                journey_headsign = _normalize_headsign(journey.destination or "")
                # Normalize journey's line color
                journey_color = (journey.line_color or "").lstrip("#").lower()

                # Try to match by headsign + line color first (more precise)
                color_key = f"{journey_headsign}:{journey_color}"
                matching = arrivals_by_headsign_color.get(color_key, [])

                # Fall back to headsign-only if no color match
                if not matching:
                    matching = arrivals_by_headsign_color.get(journey_headsign, [])

                stops = await self._get_journey_stops(session, journey)
                had_matching_arrivals = await self._update_stops_from_arrivals(
                    session, journey, stops, matching, segment_times
                )

                journey.last_updated_at = now_et()
                journey.update_count = (journey.update_count or 0) + 1

                if had_matching_arrivals:
                    # Train is still visible in API - reset error count
                    journey.api_error_count = 0
                else:
                    # No arrivals matched - but don't penalize trains that
                    # haven't departed yet. Trains with long ETAs (e.g. HOB-33
                    # at 8-18 min) can't match intermediate station arrivals
                    # until they actually start moving.
                    now = now_et()
                    origin_departed = (
                        journey.scheduled_departure
                        and journey.scheduled_departure <= now
                    )
                    if origin_departed:
                        journey.api_error_count = (journey.api_error_count or 0) + 1
                        if journey.api_error_count >= 3:
                            journey.is_expired = True
                            logger.info(
                                "path_journey_expired_no_arrivals",
                                train_id=journey.train_id,
                                error_count=journey.api_error_count,
                            )

                if journey.is_completed:
                    completed += 1
                else:
                    updated += 1

            except Exception as e:
                logger.error(
                    "path_journey_update_failed",
                    train_id=journey.train_id,
                    error=str(e),
                )
                journey.api_error_count = (journey.api_error_count or 0) + 1
                errors += 1

        return {"updated": updated, "completed": completed, "errors": errors}

    async def _get_journey_stops(
        self, session: AsyncSession, journey: TrainJourney
    ) -> list[JourneyStop]:
        """Get all stops for a journey, ordered by sequence.

        Args:
            session: Database session
            journey: Journey to get stops for

        Returns:
            List of JourneyStop objects ordered by stop_sequence
        """
        result = await session.scalars(
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
        return list(result.all())

    def _find_best_matching_arrival(
        self,
        stop: JourneyStop,
        station_arrivals: list[PathArrival],
        tolerance_minutes: int = 5,
    ) -> PathArrival | None:
        """Find the best matching arrival for a stop based on scheduled time.

        Uses a tighter tolerance (5 min) to prevent cross-train matching on
        PATH's frequent service (trains every 5-10 minutes).

        Args:
            stop: The journey stop to match
            station_arrivals: All arrivals at this stop's station
            tolerance_minutes: Max minutes difference to consider a "good" match

        Returns:
            Best matching PathArrival, or None if no arrivals
        """
        if not station_arrivals:
            return None

        if stop.scheduled_arrival:
            best_match: PathArrival | None = None
            best_diff: float = float("inf")

            for arrival in station_arrivals:
                diff = abs(
                    (arrival.arrival_time - stop.scheduled_arrival).total_seconds()
                )
                diff_minutes = diff / 60

                if diff_minutes <= tolerance_minutes and diff < best_diff:
                    best_diff = diff
                    best_match = arrival

            # Only return if we found a match within tolerance
            # Don't fall back to soonest - that could be a different train
            return best_match

        # No scheduled arrival time to match against - can't reliably match
        return None

    def _validate_and_fix_stop_times(
        self, stops: list[JourneyStop], train_id: str
    ) -> None:
        """Validate that stop times are sequential and fix any inconsistencies.

        After matching arrivals from API, times may be out of order due to:
        - API returning stale/incorrect data for some stations
        - Cross-train matching (despite our filters)
        - Timing inconsistencies in the PATH API

        This method ensures all departed stops have times in ascending order.
        If a stop has an arrival time LATER than a subsequent stop's arrival,
        it's corrected to use the scheduled time.

        Args:
            stops: List of journey stops (will be modified in place)
            train_id: Train ID for logging
        """
        if len(stops) < 2:
            return

        # Get departed stops with their times
        departed_stops = [s for s in stops if s.has_departed_station]
        if len(departed_stops) < 2:
            return

        # Sort by stop_sequence to ensure we process in order
        departed_stops.sort(key=lambda s: s.stop_sequence or 0)

        # Find the latest valid arrival time seen so far
        # (the "high water mark" for sequential validation)
        corrections_made = 0

        for i in range(len(departed_stops) - 1):
            current = departed_stops[i]
            next_stop = departed_stops[i + 1]

            current_time = current.actual_arrival or current.actual_departure
            next_time = next_stop.actual_arrival or next_stop.actual_departure

            # Normalize both times to ET before comparing to avoid timezone issues
            # (DB may return UTC, API returns ET)
            if (
                current_time
                and next_time
                and normalize_to_et(current_time) > normalize_to_et(next_time)
            ):
                # Current stop has a later time than next stop - impossible!
                # Fix by using scheduled time for current stop
                logger.warning(
                    "path_fixing_out_of_order_time",
                    train_id=train_id,
                    station_code=current.station_code,
                    stop_sequence=current.stop_sequence,
                    bad_time=current_time.isoformat() if current_time else None,
                    next_station=next_stop.station_code,
                    next_time=next_time.isoformat() if next_time else None,
                    using_scheduled=(
                        current.scheduled_arrival.isoformat()
                        if current.scheduled_arrival
                        else None
                    ),
                )

                # Use scheduled time instead
                current.actual_arrival = current.scheduled_arrival
                current.actual_departure = current.scheduled_arrival
                if current.departure_source not in ("sequential_consistency",):
                    current.departure_source = "time_corrected"
                corrections_made += 1

        if corrections_made > 0:
            logger.info(
                "path_stop_times_corrected",
                train_id=train_id,
                corrections=corrections_made,
            )

    async def _update_stops_from_arrivals(
        self,
        session: AsyncSession,
        journey: TrainJourney,
        stops: list[JourneyStop],
        arrivals: list[PathArrival],
        segment_times: SegmentTimesMap | None = None,
    ) -> bool:
        """Match arrivals to stops and update actual times.

        After matching arrivals, computes a weighted-average implied origin
        departure from all observed stops (closer = higher weight) and
        recomputes updated_arrival/updated_departure for non-departed stops.

        Args:
            session: Database session
            journey: Journey being updated
            stops: List of journey stops
            arrivals: List of matching arrivals from API
            segment_times: GTFS-based segment travel times

        Returns:
            True if any arrivals matched stops, False otherwise.
            Used to determine if train is still visible in API.
        """
        if segment_times is None:
            segment_times = {}
        if not stops:
            return False

        now = now_et()

        # Group arrivals by station
        arrivals_by_station: dict[str, list[PathArrival]] = defaultdict(list)
        for arrival in arrivals:
            arrivals_by_station[arrival.station_code].append(arrival)

        max_departed_sequence = 0
        matched_arrival_count = 0

        for stop in stops:
            station_code = stop.station_code or ""
            station_arrivals = arrivals_by_station.get(station_code, [])
            matched_arrival = self._find_best_matching_arrival(stop, station_arrivals)

            if matched_arrival:
                matched_arrival_count += 1
                stop.actual_arrival = matched_arrival.arrival_time
                stop.updated_arrival = matched_arrival.arrival_time

                if matched_arrival.arrival_time <= now:
                    stop.has_departed_station = True
                    stop.actual_departure = matched_arrival.arrival_time
                    stop.departure_source = "time_inference"
                    if stop.stop_sequence:
                        max_departed_sequence = max(
                            max_departed_sequence, stop.stop_sequence
                        )
                else:
                    # Don't reset departure status if already departed
                    # (train may have passed even if API shows future arrival)
                    if not stop.has_departed_station:
                        stop.actual_departure = None
                        stop.departure_source = None

            elif stop.stop_sequence and stop.stop_sequence < max_departed_sequence:
                if not stop.has_departed_station:
                    stop.has_departed_station = True
                    # Use scheduled time - we don't have a reliable actual time
                    # and actual_arrival might be from a stale/wrong API response
                    stop.actual_arrival = stop.scheduled_arrival
                    stop.actual_departure = stop.scheduled_arrival
                    stop.departure_source = "sequential_inference"

            elif not matched_arrival and stop.scheduled_arrival:
                grace_period = timedelta(minutes=2)
                # Normalize both to ET for consistent comparison (handles naive datetimes)
                scheduled_et = normalize_to_et(stop.scheduled_arrival)
                now_et_normalized = normalize_to_et(now)
                if scheduled_et + grace_period < now_et_normalized:
                    if not stop.has_departed_station:
                        stop.has_departed_station = True
                        stop.actual_departure = stop.scheduled_arrival
                        stop.departure_source = "time_inference"
                        if stop.stop_sequence:
                            max_departed_sequence = max(
                                max_departed_sequence, stop.stop_sequence
                            )

            stop.updated_at = now

        # Multi-observation averaging: compute weighted-average origin departure
        # from all observed stops, then recompute updated times for non-departed stops
        if matched_arrival_count > 0:
            route_result = get_path_route_and_stops(
                journey.origin_station_code or "",
                journey.terminal_station_code or "",
            )
            if route_result:
                avg_route_id, route_stops = route_result
                averaged_origin = self._compute_averaged_origin_departure(
                    stops, route_stops, segment_times, avg_route_id
                )
                if averaged_origin:
                    self._recompute_stop_times(
                        stops, route_stops, averaged_origin, segment_times, avg_route_id
                    )

        # Enforce sequential consistency: if a later stop is departed,
        # all earlier stops must also be departed (train can't skip stations)
        departed_sequences = [
            s.stop_sequence for s in stops if s.has_departed_station and s.stop_sequence
        ]
        if departed_sequences:
            max_departed = max(departed_sequences)
            for stop in stops:
                if (
                    stop.stop_sequence
                    and stop.stop_sequence < max_departed
                    and not stop.has_departed_station
                ):
                    stop.has_departed_station = True
                    # Use scheduled_arrival, not actual_arrival which may be wrong
                    # (API can return future times for stations already passed)
                    stop.actual_arrival = stop.scheduled_arrival
                    stop.actual_departure = stop.scheduled_arrival
                    stop.departure_source = "sequential_consistency"
                    logger.debug(
                        "path_sequential_consistency_fix",
                        station_code=stop.station_code,
                        stop_sequence=stop.stop_sequence,
                        max_departed_sequence=max_departed,
                    )

        # Validate and fix out-of-order arrival times
        # This handles cases where API returned inconsistent times
        self._validate_and_fix_stop_times(stops, journey.train_id or "")

        # Check journey completion
        terminal_stop = stops[-1] if stops else None
        if terminal_stop and terminal_stop.has_departed_station:
            journey.is_completed = True
            journey.actual_arrival = (
                terminal_stop.actual_arrival or terminal_stop.scheduled_arrival
            )
            logger.info(
                "path_journey_completed",
                train_id=journey.train_id,
                actual_arrival=journey.actual_arrival,
            )

        # Update journey metadata
        completed_stops = sum(1 for s in stops if s.has_departed_station)
        journey.stops_count = len(stops)

        # Create/update snapshot
        await session.execute(
            delete(JourneySnapshot).where(JourneySnapshot.journey_id == journey.id)
        )

        snapshot = JourneySnapshot(
            journey_id=journey.id,
            captured_at=now,
            raw_stop_list_data={},
            train_status="COMPLETED" if journey.is_completed else "EN ROUTE",
            completed_stops=completed_stops,
            total_stops=len(stops),
        )
        session.add(snapshot)

        # Analyze segments for congestion data
        transit_analyzer = TransitAnalyzer()
        segments_created = await transit_analyzer.analyze_new_segments(session, journey)

        if segments_created > 0:
            logger.debug(
                "path_segments_created",
                train_id=journey.train_id,
                segments_count=segments_created,
            )

        if journey.is_completed:
            await transit_analyzer.analyze_journey(session, journey)

        # Return whether any arrivals matched - used to detect train disappearance
        return matched_arrival_count > 0

    def _compute_averaged_origin_departure(
        self,
        stops: list[JourneyStop],
        route_stops: list[str],
        segment_times: SegmentTimesMap,
        route_id: str,
    ) -> Any:
        """Compute weighted-average implied origin departure from observed stops.

        Each stop with an actual_arrival implies an origin departure time:
          implied_origin = actual_arrival - cumulative_time(origin, stop)

        Closer stops get higher weight (1/cumulative_minutes) since their
        countdown is shorter and thus more precise.

        Args:
            stops: Journey stops with actual times
            route_stops: Ordered station codes for this route
            segment_times: GTFS segment time data
            route_id: GTFS route ID

        Returns:
            Averaged origin departure datetime, or None if no observations
        """
        weighted_sum = 0.0
        total_weight = 0.0

        for stop in stops:
            observed_time = stop.actual_arrival or stop.actual_departure
            if not observed_time:
                continue

            station_code = stop.station_code or ""
            if station_code not in route_stops:
                continue

            stop_idx = route_stops.index(station_code)
            if stop_idx == 0:
                # Origin stop — direct observation of departure
                cumulative_min = 0.0
                weight = 10.0  # Highest weight for direct origin observation
            else:
                cumulative_min = get_cumulative_time(
                    segment_times, route_stops, 0, stop_idx, route_id
                )
                weight = 1.0 / max(cumulative_min, 1.0)

            implied_origin = observed_time - timedelta(minutes=cumulative_min)
            weighted_sum += implied_origin.timestamp() * weight
            total_weight += weight

        if total_weight == 0:
            return None

        avg_timestamp = weighted_sum / total_weight
        # Reconstruct datetime with same tzinfo as the first observed time
        reference_time = None
        for stop in stops:
            reference_time = stop.actual_arrival or stop.actual_departure
            if reference_time:
                break

        if reference_time is None:
            return None

        return datetime.fromtimestamp(avg_timestamp, tz=reference_time.tzinfo)

    def _recompute_stop_times(
        self,
        stops: list[JourneyStop],
        route_stops: list[str],
        origin_departure: Any,
        segment_times: SegmentTimesMap,
        route_id: str,
    ) -> None:
        """Recompute updated_arrival/updated_departure for non-departed stops.

        Uses the averaged origin departure and GTFS segment times to set
        more precise predicted times for stops the train hasn't reached yet.

        Args:
            stops: Journey stops (modified in place)
            route_stops: Ordered station codes for this route
            origin_departure: Averaged origin departure time
            segment_times: GTFS segment time data
            route_id: GTFS route ID
        """
        for stop in stops:
            if stop.has_departed_station:
                continue

            station_code = stop.station_code or ""
            if station_code not in route_stops:
                continue

            stop_idx = route_stops.index(station_code)
            is_origin = stop_idx == 0
            is_terminus = stop_idx == len(route_stops) - 1

            cumulative_min = get_cumulative_time(
                segment_times, route_stops, 0, stop_idx, route_id
            )
            predicted_time = origin_departure + timedelta(minutes=cumulative_min)

            if not is_origin:
                stop.updated_arrival = predicted_time
            if not is_terminus:
                stop.updated_departure = predicted_time

    async def collect_journey_details(
        self, session: AsyncSession, journey: TrainJourney
    ) -> None:
        """Update a single journey with real-time arrival data.

        Used by the JIT service to refresh data for an existing journey.
        Uses train-level locking to prevent concurrent updates to the same journey.

        Args:
            session: Database session
            journey: Journey to update
        """
        if journey.is_completed or journey.is_cancelled or journey.is_expired:
            return

        # Use train-level locking to prevent deadlocks from concurrent updates
        train_id = journey.train_id or ""
        journey_date = (
            journey.journey_date.isoformat()
            if journey.journey_date
            else now_et().date().isoformat()
        )
        await with_train_lock(
            train_id,
            journey_date,
            self._collect_journey_details_impl,
            session,
            journey,
        )

    async def _collect_journey_details_impl(
        self, session: AsyncSession, journey: TrainJourney
    ) -> None:
        """Implementation of journey details collection (called under lock)."""
        try:
            # Fetch all arrivals
            all_arrivals = await self.client.get_all_arrivals()

            # Filter to this journey's destination
            journey_headsign = _normalize_headsign(journey.destination or "")
            matching = [
                a
                for a in all_arrivals
                if _normalize_headsign(a.headsign) == journey_headsign
            ]

            # Get journey stops and update
            stops = await self._get_journey_stops(session, journey)
            await self._update_stops_from_arrivals(session, journey, stops, matching)

            journey.last_updated_at = now_et()
            journey.update_count = (journey.update_count or 0) + 1
            journey.api_error_count = 0

            logger.debug(
                "path_journey_updated",
                train_id=journey.train_id,
                matching_arrivals=len(matching),
                stops=len(stops),
            )

        except Exception as e:
            logger.error(
                "path_journey_update_failed",
                train_id=journey.train_id,
                error=str(e),
            )
            journey.api_error_count = (journey.api_error_count or 0) + 1
            journey.last_updated_at = now_et()

            if journey.api_error_count >= 3:
                journey.is_expired = True

        await session.flush()

    async def close(self) -> None:
        """Close the client if we own it."""
        if self._owns_client:
            await self.client.close()
