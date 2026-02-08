"""
Amtrak journey collection for TrackRat V2.

Collects complete journey details for Amtrak trains.
"""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.amtrak.client import AmtrakClient
from trackrat.collectors.base import BaseJourneyCollector
from trackrat.config.stations import AMTRAK_TO_INTERNAL_STATION_MAP, get_station_name
from trackrat.db.engine import get_session, with_db_retry
from trackrat.models.api import AmtrakTrainData
from trackrat.models.database import JourneySnapshot, JourneyStop, TrainJourney
from trackrat.services.transit_analyzer import TransitAnalyzer
from trackrat.utils.locks import with_train_lock
from trackrat.utils.time import normalize_to_et, now_et

logger = get_logger(__name__)


class AmtrakJourneyCollector(BaseJourneyCollector):
    """Collects detailed journey information for Amtrak trains."""

    # Map Amtrak status values to our internal status values
    STATUS_MAP = {
        "Departed": "DEPARTED",
        "Station": "BOARDING",
        "Enroute": "EN ROUTE",
        "Cancelled": "CANCELLED",
        "Terminated": "DEPARTED",
        "Predeparture": "BOARDING",
    }

    # Map Amtrak train state to our status
    TRAIN_STATE_MAP = {
        "Active": "EN ROUTE",
        "Predeparture": "BOARDING",
        "Terminated": "DEPARTED",
    }

    def __init__(self) -> None:
        """Initialize the Amtrak journey collector."""
        self.client = AmtrakClient()

    async def collect_journey(self, train_id: str) -> TrainJourney | None:
        """Collect journey details for a specific Amtrak train.

        Args:
            train_id: The Amtrak train ID (e.g., "2150-4")

        Returns:
            TrainJourney object if successful, None if failed
        """
        # Extract train number for internal ID and journey date
        train_num = train_id.split("-")[0] if "-" in train_id else train_id
        internal_train_id = f"A{train_num}"
        journey_date = now_et().date().isoformat()

        # Use train-specific locking to prevent concurrent processing
        result = await with_train_lock(
            internal_train_id, journey_date, self._collect_journey_locked, train_id
        )
        return cast("TrainJourney | None", result)

    @with_db_retry(max_attempts=3, base_delay=0.5)
    async def _collect_journey_locked(self, train_id: str) -> TrainJourney | None:
        """Collect journey details with train-specific locking applied.

        Args:
            train_id: The Amtrak train ID (e.g., "2150-4")

        Returns:
            TrainJourney object if successful, None if failed
        """
        async with get_session() as session:
            # Get train data from API (will use cache)
            train_data = await self._get_train_data(train_id)
            if not train_data:
                logger.warning("amtrak_train_not_found", train_id=train_id)
                return None

            # Convert to our internal format
            journey = await self._convert_to_journey(session, train_data)
            if journey:
                logger.info(
                    "amtrak_journey_collected",
                    train_id=journey.train_id,
                    stops_count=journey.stops_count,
                )

            return journey

    async def _upsert_journey_stop(
        self,
        session: AsyncSession,
        journey_id: int,
        station_code: str,
        stop_data: dict[str, Any],
    ) -> JourneyStop:
        """Upsert a journey stop (create or update if exists).

        Args:
            session: Database session
            journey_id: The journey ID
            station_code: The station code
            stop_data: Dictionary with stop data fields

        Returns:
            The created or updated JourneyStop
        """
        # Try to find existing stop
        existing_stop = await session.scalar(
            select(JourneyStop).where(
                and_(
                    JourneyStop.journey_id == journey_id,
                    JourneyStop.station_code == station_code,
                )
            )
        )

        if existing_stop:
            # Update existing stop with new data
            for field, value in stop_data.items():
                setattr(existing_stop, field, value)
            existing_stop.updated_at = now_et()
            return existing_stop
        else:
            # Create new stop
            new_stop = JourneyStop(
                journey_id=journey_id, station_code=station_code, **stop_data
            )
            session.add(new_stop)
            return new_stop

    async def run(self) -> dict[str, Any]:
        """Run the journey collector for all discovered Amtrak trains.

        Returns:
            Collection results summary
        """
        # This will be called by the scheduler to collect multiple trains
        # For now, return empty results as the scheduler will call collect_journey directly
        return {
            "trains_processed": 0,
            "successful": 0,
            "failed": 0,
            "data_source": "AMTRAK",
        }

    async def _get_train_data(self, train_id: str) -> AmtrakTrainData | None:
        """Get train data from the API.

        Args:
            train_id: Amtrak train ID

        Returns:
            Train data if found
        """
        async with self.client:
            # Get all trains (from cache if available)
            all_trains = await self.client.get_all_trains()

            # Find the specific train by ID
            for train_list in all_trains.values():
                for train in train_list:
                    if train.trainID == train_id:
                        return train  # type: ignore[no-any-return]

        return None

    async def _convert_to_journey(
        self, session: AsyncSession, train_data: AmtrakTrainData
    ) -> TrainJourney | None:
        """Convert Amtrak data to our internal TrainJourney format.

        Args:
            session: Database session
            train_data: Raw Amtrak train data

        Returns:
            TrainJourney object or None if conversion fails
        """
        try:
            # Prefix train number with 'A' to distinguish from NJT
            train_id = f"A{train_data.trainNum}"

            # Find the first tracked station for origin and scheduled departure
            origin_code = None
            scheduled_departure = None

            for stop in train_data.stations:
                internal_code = AMTRAK_TO_INTERNAL_STATION_MAP.get(stop.code)
                if internal_code and stop.schDep:
                    origin_code = internal_code
                    scheduled_departure = self._parse_amtrak_time(stop.schDep)
                    break

            if not origin_code or not scheduled_departure:
                logger.warning(
                    "no_tracked_origin_found",
                    train_id=train_id,
                    route=train_data.routeName,
                )
                return None

            journey_date = scheduled_departure.date()

            # Check if journey already exists with SELECT FOR UPDATE SKIP LOCKED
            existing = await session.scalar(
                select(TrainJourney)
                .where(
                    and_(
                        TrainJourney.train_id == train_id,
                        TrainJourney.journey_date == journey_date,
                        TrainJourney.data_source == "AMTRAK",
                    )
                )
                .with_for_update(skip_locked=True)
            )

            if existing:
                # Update existing journey
                journey = existing
                journey.last_updated_at = now_et()
                journey.update_count = (journey.update_count or 0) + 1
                # Mark as observed if it was previously scheduled
                if journey.observation_type == "SCHEDULED":
                    journey.observation_type = "OBSERVED"
                    logger.info(
                        "upgraded_amtrak_scheduled_to_observed",
                        train_id=train_id,
                        journey_date=journey_date,
                    )
            else:
                # Create new journey
                journey = TrainJourney(
                    train_id=train_id,
                    journey_date=journey_date,
                    data_source="AMTRAK",
                    observation_type="OBSERVED",  # Real-time Amtrak data
                    line_code="AM",  # Standard code for Amtrak
                    line_name="Amtrak",
                    line_color="#003366",  # Amtrak blue
                    destination=train_data.destName,
                    origin_station_code=origin_code,
                    terminal_station_code=origin_code,  # Will update when we find the last tracked stop
                    scheduled_departure=scheduled_departure,
                    first_seen_at=now_et(),
                    last_updated_at=now_et(),
                    has_complete_journey=True,  # We always get complete data from Amtrak
                    update_count=1,
                )

            # For new journeys, add to session and flush to get ID
            if not existing:
                session.add(journey)
                await session.flush()  # This assigns the ID

            # Process stops - only include our tracked stations
            # Use upsert logic to avoid delete+insert race conditions
            stop_sequence = 0
            last_tracked_code = origin_code
            new_stops = []  # Track processed stops for metadata updates

            for amtrak_stop in train_data.stations:
                internal_code = AMTRAK_TO_INTERNAL_STATION_MAP.get(amtrak_stop.code)
                if not internal_code:
                    continue  # Skip non-tracked stations

                # Update terminal station
                last_tracked_code = internal_code

                # Parse times
                sched_arr = (
                    self._parse_amtrak_time(amtrak_stop.schArr)
                    if amtrak_stop.schArr
                    else None
                )
                sched_dep = (
                    self._parse_amtrak_time(amtrak_stop.schDep)
                    if amtrak_stop.schDep
                    else None
                )
                actual_arr = (
                    self._parse_amtrak_time(amtrak_stop.arr)
                    if amtrak_stop.arr
                    else None
                )
                actual_dep = (
                    self._parse_amtrak_time(amtrak_stop.dep)
                    if amtrak_stop.dep
                    else None
                )

                # Safety check: trains never depart before scheduled time
                if actual_dep and sched_dep and actual_dep < sched_dep:
                    logger.warning(
                        "amtrak_early_departure_corrected",
                        train_id=train_id,
                        station=amtrak_stop.code,
                        scheduled=sched_dep.isoformat(),
                        actual=actual_dep.isoformat(),
                        status=amtrak_stop.status,
                    )
                    actual_dep = sched_dep

                # Safety check: trains never arrive before scheduled time
                if actual_arr and sched_arr and actual_arr < sched_arr:
                    logger.warning(
                        "amtrak_early_arrival_corrected",
                        train_id=train_id,
                        station=amtrak_stop.code,
                        scheduled=sched_arr.isoformat(),
                        actual=actual_arr.isoformat(),
                        status=amtrak_stop.status,
                    )
                    actual_arr = sched_arr

                # Prepare stop data for upsert
                # Apply time validation to prevent future trains being marked as departed
                has_departed = amtrak_stop.status == "Departed" and (
                    not sched_dep or sched_dep <= now_et()
                )

                stop_data = {
                    "station_name": get_station_name(internal_code),
                    "stop_sequence": stop_sequence,
                    "scheduled_arrival": sched_arr,
                    "scheduled_departure": sched_dep,
                    "updated_arrival": sched_arr,  # For Amtrak, use scheduled since no estimates
                    "updated_departure": sched_dep,
                    "actual_arrival": actual_arr,
                    "actual_departure": actual_dep,
                    "raw_amtrak_status": amtrak_stop.status,
                    "has_departed_station": has_departed,
                    "track": amtrak_stop.platform if amtrak_stop.platform else None,
                    "pickup_only": False,
                    "dropoff_only": False,
                }

                # Upsert the stop (create or update)
                journey_stop = await self._upsert_journey_stop(
                    session, journey.id or 0, internal_code, stop_data
                )
                new_stops.append(journey_stop)

                stop_sequence += 1

            # Update terminal station and other fields using our local data
            journey.terminal_station_code = last_tracked_code
            journey.stops_count = len(new_stops)
            journey.scheduled_arrival = (
                new_stops[-1].scheduled_arrival if new_stops else None
            )

            # Determine overall status
            journey.is_cancelled = train_data.trainState == "Cancelled"
            journey.is_completed = train_data.trainState == "Terminated"

            # Set actual departure and arrival times from stops
            if new_stops:
                # Set actual departure from first stop
                if new_stops[0].actual_departure:
                    journey.actual_departure = new_stops[0].actual_departure

                # Set actual arrival from last stop
                if new_stops[-1].actual_arrival:
                    journey.actual_arrival = new_stops[-1].actual_arrival

            # Create snapshot for all journeys (both new and existing)
            # Journey now has a valid ID after flush/creation
            # NOTE: Only keeps one snapshot per journey to prevent database growth
            await session.execute(
                delete(JourneySnapshot).where(JourneySnapshot.journey_id == journey.id)
            )

            completed_stops_count = sum(
                1 for stop in new_stops if stop.has_departed_station
            )
            snapshot = JourneySnapshot(
                journey_id=journey.id,
                captured_at=now_et(),
                raw_stop_list_data={},  # Deactivated to reduce database size - full data is in journey_stops
                train_status=self.TRAIN_STATE_MAP.get(train_data.trainState, "UNKNOWN"),
                completed_stops=completed_stops_count,
                total_stops=len(new_stops),
            )
            session.add(snapshot)

            # Flush to ensure all data is persisted before analysis
            await session.flush()

            # Refresh journey to load relationships properly
            await session.refresh(journey, ["stops"])

            # Transit time analysis is now done on-the-fly in API endpoints

            return journey

        except Exception as e:
            logger.error(
                "journey_conversion_failed",
                train_id=train_data.trainID,
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

    def _parse_amtrak_time(self, time_str: str) -> datetime | None:
        """Parse Amtrak ISO format time string to datetime and normalize to Eastern Time.

        Args:
            time_str: ISO format time string with timezone

        Returns:
            Parsed datetime normalized to Eastern Time or None if parsing fails
        """
        try:
            # Amtrak provides times in ISO format with timezone offset
            # Example: "2025-07-04T22:00:00-07:00"
            if "Z" in time_str:
                time_str = time_str.replace("Z", "+00:00")

            # Parse the datetime
            dt = datetime.fromisoformat(time_str)

            # Normalize to Eastern Time for consistency with NJT data
            return normalize_to_et(dt)

        except Exception as e:
            logger.warning("amtrak_time_parse_failed", time_str=time_str, error=str(e))
            return None

    async def collect_journey_details(
        self, session: AsyncSession, journey: TrainJourney
    ) -> None:
        """Collect complete journey details for an existing train journey.

        This method is used by the JIT service to refresh data for an existing journey.

        Args:
            session: Database session
            journey: Journey to collect data for
        """
        if not journey.train_id:
            raise ValueError(f"Journey {journey.id} has no train_id")

        # Remove the 'A' prefix to get the Amtrak train number
        train_num = (
            journey.train_id[1:]
            if journey.train_id.startswith("A")
            else journey.train_id
        )

        # Get the train data from Amtrak API
        train_data = None
        async with self.client:
            # Get all trains (from cache if available)
            all_trains = await self.client.get_all_trains()

            # Find train by train number (Amtrak uses train number not train ID)
            for train_list in all_trains.values():
                for train in train_list:
                    if train.trainNum == train_num:
                        train_data = train
                        break
                if train_data:
                    break

        if not train_data:
            logger.warning(
                "amtrak_train_not_found_for_refresh",
                train_id=journey.train_id,
                train_num=train_num,
            )
            journey.api_error_count = (journey.api_error_count or 0) + 1
            journey.last_updated_at = now_et()

            # After 3 failed attempts, mark as expired
            if journey.api_error_count >= 3:
                journey.is_expired = True
                logger.warning(
                    "amtrak_train_marked_expired",
                    train_id=journey.train_id,
                    api_error_count=journey.api_error_count,
                )
            return

        # Reset error count on successful fetch
        if journey.api_error_count and journey.api_error_count > 0:
            logger.info(
                "resetting_api_error_count",
                train_id=journey.train_id,
                previous_count=journey.api_error_count,
            )
            journey.api_error_count = 0

        # Update journey with latest data
        journey.last_updated_at = now_et()
        journey.update_count = (journey.update_count or 0) + 1
        journey.destination = train_data.destName
        journey.is_cancelled = train_data.trainState == "Cancelled"
        journey.is_completed = train_data.trainState == "Terminated"
        journey.has_complete_journey = True

        # Update stops
        stop_sequence = 0
        tracked_stops = []

        for amtrak_stop in train_data.stations:
            internal_code = AMTRAK_TO_INTERNAL_STATION_MAP.get(amtrak_stop.code)
            if not internal_code:
                continue

            # Find existing stop or create new
            existing_stop = await session.scalar(
                select(JourneyStop).where(
                    and_(
                        JourneyStop.journey_id == journey.id,
                        JourneyStop.station_code == internal_code,
                    )
                )
            )

            # Explicitly type the variables to help mypy
            station_name: str = get_station_name(internal_code)
            scheduled_arrival: datetime | None = (
                self._parse_amtrak_time(amtrak_stop.schArr)
                if amtrak_stop.schArr
                else None
            )
            scheduled_departure: datetime | None = (
                self._parse_amtrak_time(amtrak_stop.schDep)
                if amtrak_stop.schDep
                else None
            )
            actual_arrival: datetime | None = (
                self._parse_amtrak_time(amtrak_stop.arr) if amtrak_stop.arr else None
            )
            actual_departure: datetime | None = (
                self._parse_amtrak_time(amtrak_stop.dep) if amtrak_stop.dep else None
            )

            # Safety check: trains never depart before scheduled time
            if (
                actual_departure
                and scheduled_departure
                and actual_departure < scheduled_departure
            ):
                logger.warning(
                    "amtrak_early_departure_corrected_refresh",
                    train_id=journey.train_id,
                    station=amtrak_stop.code,
                    scheduled=scheduled_departure.isoformat(),
                    actual=actual_departure.isoformat(),
                    status=amtrak_stop.status,
                )
                actual_departure = scheduled_departure

            # Safety check: trains never arrive before scheduled time
            if (
                actual_arrival
                and scheduled_arrival
                and actual_arrival < scheduled_arrival
            ):
                logger.warning(
                    "amtrak_early_arrival_corrected_refresh",
                    train_id=journey.train_id,
                    station=amtrak_stop.code,
                    scheduled=scheduled_arrival.isoformat(),
                    actual=actual_arrival.isoformat(),
                    status=amtrak_stop.status,
                )
                actual_arrival = scheduled_arrival
            # Validate against scheduled time to prevent stale data issues
            departed: bool = amtrak_stop.status == "Departed" and (
                not scheduled_departure or scheduled_departure <= now_et()
            )
            # status: str = self.STATUS_MAP.get(amtrak_stop.status, amtrak_stop.status)
            track: str | None = amtrak_stop.platform if amtrak_stop.platform else None
            pickup_only: bool = False
            dropoff_only: bool = False

            stop_data = {
                "station_name": station_name,
                "stop_sequence": stop_sequence,
                "scheduled_arrival": scheduled_arrival,
                "scheduled_departure": scheduled_departure,
                "updated_arrival": scheduled_arrival,  # For Amtrak, use scheduled since no estimates
                "updated_departure": scheduled_departure,
                "actual_arrival": actual_arrival,
                "actual_departure": actual_departure,
                "raw_amtrak_status": amtrak_stop.status,
                "has_departed_station": departed,  # Now using validated flag
                "track": track,
                "pickup_only": pickup_only,
                "dropoff_only": dropoff_only,
            }

            if existing_stop:
                # Update existing stop
                for field, value in stop_data.items():
                    setattr(existing_stop, field, value)
                existing_stop.updated_at = now_et()
                tracked_stops.append(existing_stop)
            else:
                # Create new stop
                new_stop = JourneyStop(
                    journey_id=journey.id,
                    station_code=internal_code,
                    station_name=station_name,
                    stop_sequence=stop_sequence,
                    scheduled_arrival=scheduled_arrival,
                    scheduled_departure=scheduled_departure,
                    actual_arrival=actual_arrival,
                    actual_departure=actual_departure,
                    has_departed_station=departed,
                    raw_amtrak_status=amtrak_stop.status,
                    track=track,
                    pickup_only=pickup_only,
                    dropoff_only=dropoff_only,
                )
                session.add(new_stop)
                tracked_stops.append(new_stop)

            stop_sequence += 1

        # Update journey metadata
        journey.stops_count = len(tracked_stops)
        if tracked_stops:
            journey.terminal_station_code = tracked_stops[-1].station_code
            journey.scheduled_arrival = tracked_stops[-1].scheduled_arrival
            if journey.is_completed and tracked_stops[-1].actual_arrival:
                journey.actual_arrival = tracked_stops[-1].actual_arrival

        # Create snapshot - replace existing to maintain single snapshot per journey
        await session.execute(
            delete(JourneySnapshot).where(JourneySnapshot.journey_id == journey.id)
        )

        completed_stops_count = sum(
            1 for stop in tracked_stops if stop.has_departed_station
        )
        snapshot = JourneySnapshot(
            journey_id=journey.id,
            captured_at=now_et(),
            raw_stop_list_data={},  # Deactivated to reduce database size - full data is in journey_stops
            train_status=self.TRAIN_STATE_MAP.get(train_data.trainState, "UNKNOWN"),
            completed_stops=completed_stops_count,
            total_stops=len(tracked_stops),
        )
        session.add(snapshot)

        logger.info(
            "amtrak_journey_refreshed",
            train_id=journey.train_id,
            stops_count=journey.stops_count,
            is_completed=journey.is_completed,
            is_cancelled=journey.is_cancelled,
        )

        # Analyze any newly completed segments (for real-time predictions)
        # This runs immediately without waiting for journey completion
        transit_analyzer = TransitAnalyzer()
        segments_created = await transit_analyzer.analyze_new_segments(session, journey)

        if segments_created > 0:
            logger.info(
                "amtrak_segments_created",
                train_id=journey.train_id,
                segments_count=segments_created,
            )

        # For completed journeys, run full analysis (dwell times, progress, etc.)
        if journey.is_completed:
            logger.info(
                "amtrak_journey_completed_analyzing",
                train_id=journey.train_id,
                journey_id=journey.id,
            )

            # Run full analysis on completed journey (dwell times, progress, etc.)
            await transit_analyzer.analyze_journey(session, journey)
            logger.info(
                "amtrak_completed_journey_analyzed",
                train_id=journey.train_id,
                journey_id=journey.id,
            )
