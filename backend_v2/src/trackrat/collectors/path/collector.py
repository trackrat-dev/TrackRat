"""
Unified PATH train collector for TrackRat V2.

Combines discovery and journey tracking into a single task that:
1. Discovers new trains at terminus stations (PHO, PWC, P33, PNK)
2. Updates existing journeys with real-time arrival data

Runs every 4 minutes for responsive tracking with single API call.
"""

from collections import defaultdict
from datetime import timedelta
from typing import Any

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.path.ridepath_client import PathArrival, RidePathClient
from trackrat.config.stations import (
    PATH_DISCOVERY_STATIONS,
    get_path_stops_by_origin_destination,
    get_station_name,
)
from trackrat.db.engine import get_session
from trackrat.models.database import JourneySnapshot, JourneyStop, TrainJourney
from trackrat.services.transit_analyzer import TransitAnalyzer
from trackrat.utils.time import now_et

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
    if "hoboken" in h:
        return "hoboken"
    if "newark" in h:
        return "newark"
    if "journal" in h:
        return "journal_square"
    if "grove" in h:
        return "grove_street"
    if "harrison" in h:
        return "harrison"

    return h.replace(" ", "_")


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

        # === PHASE 1: DISCOVERY ===
        discovery_stats = await self._discover_trains(session, arrivals)

        # === PHASE 2: UPDATES ===
        update_stats = await self._update_journeys(session, arrivals)

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
        self, session: AsyncSession, arrivals: list[PathArrival]
    ) -> dict[str, Any]:
        """Discovery phase - create journeys for new trains.

        Only processes arrivals at discovery stations (terminus stations).
        Skips trains that are arriving at their destination.

        Args:
            session: Database session
            arrivals: All arrivals from API

        Returns:
            Discovery statistics
        """
        total_arrivals = 0
        new_journeys = 0
        station_results: dict[str, dict[str, Any]] = {
            station: {"arrivals_found": 0, "new_journeys": 0}
            for station in PATH_DISCOVERY_STATIONS
        }

        for arrival in arrivals:
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
            created = await self._process_arrival_for_discovery(session, arrival)
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
    ) -> bool:
        """Process a single arrival and create journey record if new.

        Args:
            session: Database session
            arrival: Arrival data from RidePATH

        Returns:
            True if a new journey was created, False if existing/skipped
        """
        origin_station = arrival.station_code
        destination = arrival.headsign
        departure_time = arrival.arrival_time

        if not departure_time:
            return False

        journey_date = departure_time.date()

        # Get line info from headsign
        line_code, line_name, line_color = _get_line_info_from_headsign(destination)

        # Use line color from API if available
        if arrival.line_color:
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
            return False

        # Get destination station code from headsign
        destination_station = _get_destination_station_from_headsign(destination)

        # Get route stops from hardcoded PATH routes
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
            terminal_station = destination_station or origin_station
            terminal_arrival = departure_time + timedelta(minutes=20)
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
        await self._create_journey_stops(
            session, journey, route_stops, departure_time, destination_station
        )

        logger.debug(
            "path_journey_created",
            train_id=train_id,
            line=line_code,
            origin=origin_station,
            destination=destination,
            stops=stops_count,
        )

        return True

    async def _create_journey_stops(
        self,
        session: AsyncSession,
        journey: TrainJourney,
        route_stops: list[str] | None,
        departure_time: Any,
        destination_station: str | None,
    ) -> None:
        """Create journey stop records.

        Args:
            session: Database session
            journey: Parent journey
            route_stops: List of station codes in order, or None
            departure_time: Departure time from origin
            destination_station: Destination station code
        """
        minutes_per_segment = 3

        if route_stops and len(route_stops) >= 2:
            for sequence, station_code in enumerate(route_stops, start=1):
                is_origin = sequence == 1
                is_terminus = sequence == len(route_stops)
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
                station_code=journey.origin_station_code,
                station_name=get_station_name(journey.origin_station_code),
                stop_sequence=1,
                scheduled_departure=departure_time,
                updated_departure=departure_time,
            )
            session.add(origin_stop)

            if destination_station and destination_station != journey.origin_station_code:
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

    # =========================================================================
    # PHASE 2: UPDATES
    # =========================================================================

    async def _update_journeys(
        self, session: AsyncSession, arrivals: list[PathArrival]
    ) -> dict[str, Any]:
        """Update phase - refresh active journeys with arrival data.

        Args:
            session: Database session
            arrivals: All arrivals from API

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

        # Group arrivals by normalized headsign
        arrivals_by_headsign: dict[str, list[PathArrival]] = defaultdict(list)
        for arrival in arrivals:
            key = _normalize_headsign(arrival.headsign)
            arrivals_by_headsign[key].append(arrival)

        updated = 0
        completed = 0
        errors = 0

        for journey in journeys:
            try:
                journey_headsign = _normalize_headsign(journey.destination)
                matching = arrivals_by_headsign.get(journey_headsign, [])

                stops = await self._get_journey_stops(session, journey)
                await self._update_stops_from_arrivals(session, journey, stops, matching)

                journey.last_updated_at = now_et()
                journey.update_count = (journey.update_count or 0) + 1
                journey.api_error_count = 0

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
        tolerance_minutes: int = 10,
    ) -> PathArrival | None:
        """Find the best matching arrival for a stop based on scheduled time.

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
                diff = abs((arrival.arrival_time - stop.scheduled_arrival).total_seconds())
                diff_minutes = diff / 60

                if diff_minutes <= tolerance_minutes and diff < best_diff:
                    best_diff = diff
                    best_match = arrival

            if best_match:
                return best_match

        # Fallback: return the soonest arrival at this station
        return min(station_arrivals, key=lambda a: a.minutes_away)

    async def _update_stops_from_arrivals(
        self,
        session: AsyncSession,
        journey: TrainJourney,
        stops: list[JourneyStop],
        arrivals: list[PathArrival],
    ) -> None:
        """Match arrivals to stops and update actual times.

        Args:
            session: Database session
            journey: Journey being updated
            stops: List of journey stops
            arrivals: List of matching arrivals from API
        """
        if not stops:
            return

        now = now_et()

        # Group arrivals by station
        arrivals_by_station: dict[str, list[PathArrival]] = defaultdict(list)
        for arrival in arrivals:
            arrivals_by_station[arrival.station_code].append(arrival)

        max_departed_sequence = 0

        for stop in stops:
            station_arrivals = arrivals_by_station.get(stop.station_code, [])
            arrival = self._find_best_matching_arrival(stop, station_arrivals)

            if arrival:
                stop.actual_arrival = arrival.arrival_time
                stop.updated_arrival = arrival.arrival_time

                if arrival.arrival_time <= now:
                    stop.has_departed_station = True
                    stop.actual_departure = arrival.arrival_time
                    stop.departure_source = "time_inference"
                    if stop.stop_sequence:
                        max_departed_sequence = max(max_departed_sequence, stop.stop_sequence)
                else:
                    stop.has_departed_station = False
                    stop.actual_departure = None
                    stop.departure_source = None

            elif stop.stop_sequence and stop.stop_sequence < max_departed_sequence:
                if not stop.has_departed_station:
                    stop.has_departed_station = True
                    stop.actual_departure = stop.actual_arrival or stop.scheduled_arrival
                    stop.departure_source = "sequential_inference"

            elif not arrival and stop.scheduled_arrival:
                grace_period = timedelta(minutes=2)
                if stop.scheduled_arrival + grace_period < now:
                    if not stop.has_departed_station:
                        stop.has_departed_station = True
                        stop.actual_departure = stop.scheduled_arrival
                        stop.departure_source = "time_inference"
                        if stop.stop_sequence:
                            max_departed_sequence = max(max_departed_sequence, stop.stop_sequence)

            stop.updated_at = now

        # Check journey completion
        terminal_stop = stops[-1] if stops else None
        if terminal_stop and terminal_stop.has_departed_station:
            journey.is_completed = True
            journey.actual_arrival = terminal_stop.actual_arrival or terminal_stop.scheduled_arrival
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

    async def collect_journey_details(
        self, session: AsyncSession, journey: TrainJourney
    ) -> None:
        """Update a single journey with real-time arrival data.

        Used by the JIT service to refresh data for an existing journey.

        Args:
            session: Database session
            journey: Journey to update
        """
        if journey.is_completed or journey.is_cancelled or journey.is_expired:
            return

        try:
            # Fetch all arrivals
            all_arrivals = await self.client.get_all_arrivals()

            # Filter to this journey's destination
            journey_headsign = _normalize_headsign(journey.destination)
            matching = [
                a for a in all_arrivals
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

            if journey.api_error_count >= 2:
                journey.is_expired = True

        await session.flush()

    async def close(self) -> None:
        """Close the client if we own it."""
        if self._owns_client:
            await self.client.close()
