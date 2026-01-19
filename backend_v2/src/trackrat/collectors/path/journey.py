"""
PATH journey collection for TrackRat V2.

Updates PATH journeys with real-time arrival data from the native
RidePATH API, which provides predictions at all 13 stations.
"""

from collections import defaultdict
from datetime import timedelta
from typing import Any

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.base import BaseJourneyCollector
from trackrat.collectors.path.ridepath_client import PathArrival, RidePathClient
from trackrat.db.engine import get_session
from trackrat.models.database import JourneySnapshot, JourneyStop, TrainJourney
from trackrat.services.transit_analyzer import TransitAnalyzer
from trackrat.utils.time import now_et

logger = get_logger(__name__)


def normalize_headsign(headsign: str) -> str:
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

    # Normalize common variations
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


class PathJourneyCollector(BaseJourneyCollector):
    """Updates PATH journeys with real-time data from RidePATH API."""

    def __init__(self, client: RidePathClient | None = None) -> None:
        """Initialize the PATH journey collector.

        Args:
            client: Optional RidePATH client (creates one if not provided)
        """
        self.client = client or RidePathClient()
        self._owns_client = client is None

    async def collect_journey(self, train_id: str) -> TrainJourney | None:
        """Collect journey details for a specific PATH train.

        Args:
            train_id: The PATH train ID (e.g., "PATH_862_abc123")

        Returns:
            TrainJourney object if found and updated, None otherwise
        """
        async with get_session() as session:
            # Find the journey
            journey = await session.scalar(
                select(TrainJourney).where(
                    TrainJourney.train_id == train_id,
                    TrainJourney.data_source == "PATH",
                    TrainJourney.journey_date == now_et().date(),
                )
            )

            if not journey:
                logger.warning("path_journey_not_found", train_id=train_id)
                return None

            await self.collect_journey_details(session, journey)
            await session.commit()
            return journey

    async def run(self) -> dict[str, Any]:
        """Run batch collection for all active PATH journeys.

        Returns:
            Collection results summary
        """
        async with get_session() as session:
            return await self.collect_active_journeys(session)

    async def collect_journey_details(
        self, session: AsyncSession, journey: TrainJourney
    ) -> None:
        """Update a single journey with real-time arrival data.

        This method is used by the JIT service to refresh data for an existing journey.

        Strategy:
        1. Fetch all arrivals from RidePATH API
        2. Find arrivals matching this journey's destination
        3. Match arrivals to journey stops by station
        4. Update actual_arrival times

        Args:
            session: Database session
            journey: Journey to update
        """
        if journey.is_completed or journey.is_cancelled or journey.is_expired:
            return

        try:
            # Get all current arrivals
            all_arrivals = await self.client.get_all_arrivals()

            # Filter to this journey's destination
            journey_headsign = normalize_headsign(journey.destination)
            matching = [
                a for a in all_arrivals
                if normalize_headsign(a.headsign) == journey_headsign
            ]

            # Get journey stops
            stops = await self._get_journey_stops(session, journey)

            # Match arrivals to stops and update
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
                logger.warning(
                    "path_journey_marked_expired",
                    train_id=journey.train_id,
                    api_error_count=journey.api_error_count,
                )

        await session.flush()

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

        Matching strategy:
        1. If stop has scheduled_arrival, find arrival closest to it (within tolerance)
        2. If no scheduled time or no match within tolerance, return soonest arrival
        3. If no arrivals at all, return None

        Args:
            stop: The journey stop to match
            station_arrivals: All arrivals at this stop's station
            tolerance_minutes: Max minutes difference to consider a "good" match

        Returns:
            Best matching PathArrival, or None if no arrivals
        """
        if not station_arrivals:
            return None

        # If stop has a scheduled arrival time, try to match by time
        if stop.scheduled_arrival:
            best_match: PathArrival | None = None
            best_diff: float = float("inf")

            for arrival in station_arrivals:
                # Calculate time difference between scheduled and predicted arrival
                diff = abs((arrival.arrival_time - stop.scheduled_arrival).total_seconds())
                diff_minutes = diff / 60

                # Track the closest match within tolerance
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

        Matching strategy:
        1. For each stop, find arrivals at that station with matching headsign
        2. If stop has scheduled time, match to arrival closest to that time
        3. Otherwise fall back to soonest arrival at that station
        4. Update actual_arrival with predicted time
        5. Mark departed if arrival time has passed

        Args:
            session: Database session
            journey: Journey being updated
            stops: List of journey stops
            arrivals: List of matching arrivals from API
        """
        if not stops:
            return

        now = now_et()

        # Group arrivals by station, keeping ALL arrivals for time-based matching
        arrivals_by_station: dict[str, list[PathArrival]] = defaultdict(list)
        for arrival in arrivals:
            arrivals_by_station[arrival.station_code].append(arrival)

        # Track furthest departed stop for sequential inference
        max_departed_sequence = 0

        for stop in stops:
            station_arrivals = arrivals_by_station.get(stop.station_code, [])
            arrival = self._find_best_matching_arrival(stop, station_arrivals)

            if arrival:
                # Update arrival time with real-time prediction
                stop.actual_arrival = arrival.arrival_time
                stop.updated_arrival = arrival.arrival_time

                # Check if train has passed this stop (arrival time in the past)
                if arrival.arrival_time <= now:
                    stop.has_departed_station = True
                    stop.actual_departure = arrival.arrival_time
                    stop.departure_source = "time_inference"
                    if stop.stop_sequence:
                        max_departed_sequence = max(max_departed_sequence, stop.stop_sequence)
                else:
                    # Train hasn't arrived yet - clear departure flags
                    stop.has_departed_station = False
                    stop.actual_departure = None
                    stop.departure_source = None

            elif stop.stop_sequence and stop.stop_sequence < max_departed_sequence:
                # Sequential inference: if a later stop is departed, this one must be too
                if not stop.has_departed_station:
                    stop.has_departed_station = True
                    stop.actual_departure = stop.actual_arrival or stop.scheduled_arrival
                    stop.departure_source = "sequential_inference"

            # Time-based inference for stops not in API (train may have passed)
            elif not arrival and stop.scheduled_arrival:
                # If scheduled arrival was > 2 min ago and no API data, assume departed
                grace_period = timedelta(minutes=2)
                if stop.scheduled_arrival + grace_period < now:
                    if not stop.has_departed_station:
                        stop.has_departed_station = True
                        stop.actual_departure = stop.scheduled_arrival
                        stop.departure_source = "time_inference"
                        if stop.stop_sequence:
                            max_departed_sequence = max(max_departed_sequence, stop.stop_sequence)

            stop.updated_at = now

        # Check journey completion - terminal stop departed
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
            raw_stop_list_data={},  # Deactivated to reduce database size
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

        # For completed journeys, run full analysis
        if journey.is_completed:
            await transit_analyzer.analyze_journey(session, journey)

    async def collect_active_journeys(
        self, session: AsyncSession
    ) -> dict[str, Any]:
        """Batch update all active PATH journeys.

        More efficient than individual updates since we fetch
        all arrivals once and match to multiple journeys.

        Args:
            session: Database session

        Returns:
            Collection results summary
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
            logger.debug("path_no_active_journeys")
            return {"data_source": "PATH", "journeys_processed": 0}

        # Fetch all arrivals once
        try:
            all_arrivals = await self.client.get_all_arrivals()
        except Exception as e:
            logger.error("path_batch_fetch_failed", error=str(e))
            return {"data_source": "PATH", "error": str(e), "journeys_processed": 0}

        # Group arrivals by normalized headsign
        arrivals_by_headsign: dict[str, list[PathArrival]] = defaultdict(list)
        for arrival in all_arrivals:
            key = normalize_headsign(arrival.headsign)
            arrivals_by_headsign[key].append(arrival)

        # Update each journey
        updated = 0
        completed = 0
        errors = 0

        for journey in journeys:
            try:
                journey_headsign = normalize_headsign(journey.destination)
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
                    "path_journey_batch_update_failed",
                    train_id=journey.train_id,
                    error=str(e),
                )
                journey.api_error_count = (journey.api_error_count or 0) + 1
                errors += 1

        await session.commit()

        logger.info(
            "path_batch_collection_completed",
            journeys_processed=len(journeys),
            updated=updated,
            completed=completed,
            errors=errors,
            arrivals_fetched=len(all_arrivals),
        )

        return {
            "data_source": "PATH",
            "journeys_processed": len(journeys),
            "updated": updated,
            "completed": completed,
            "errors": errors,
            "arrivals_fetched": len(all_arrivals),
        }

    async def close(self) -> None:
        """Close the client if we own it."""
        if self._owns_client:
            await self.client.close()
