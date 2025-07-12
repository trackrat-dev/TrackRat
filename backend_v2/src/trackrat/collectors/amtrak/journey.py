"""
Amtrak journey collection for TrackRat V2.

Collects complete journey details for Amtrak trains.
"""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.amtrak.client import AmtrakClient
from trackrat.collectors.base import BaseJourneyCollector
from trackrat.config.stations import AMTRAK_TO_INTERNAL_STATION_MAP, get_station_name
from trackrat.db.engine import get_session, with_db_retry
from trackrat.models.api import AmtrakTrainData
from trackrat.models.database import JourneySnapshot, JourneyStop, TrainJourney
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
                        return train

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
            else:
                # Create new journey
                journey = TrainJourney(
                    train_id=train_id,
                    journey_date=journey_date,
                    data_source="AMTRAK",
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

                # Prepare stop data for upsert
                stop_data = {
                    "station_name": get_station_name(internal_code),
                    "stop_sequence": stop_sequence,
                    "scheduled_arrival": sched_arr,
                    "scheduled_departure": sched_dep,
                    "actual_arrival": actual_arr,
                    "actual_departure": actual_dep,
                    "departed": (amtrak_stop.status == "Departed"),
                    "status": self.STATUS_MAP.get(
                        amtrak_stop.status, amtrak_stop.status
                    ),
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

            # Create snapshot for all journeys (both new and existing)
            # Journey now has a valid ID after flush/creation
            completed_stops_count = sum(1 for stop in new_stops if stop.departed)
            snapshot = JourneySnapshot(
                journey_id=journey.id,
                captured_at=now_et(),
                raw_stop_list_data={
                    "train_data": train_data.model_dump(),
                    "data_source": "AMTRAK",
                },
                train_status=self.TRAIN_STATE_MAP.get(train_data.trainState, "UNKNOWN"),
                completed_stops=completed_stops_count,
                total_stops=len(new_stops),
            )
            session.add(snapshot)

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
