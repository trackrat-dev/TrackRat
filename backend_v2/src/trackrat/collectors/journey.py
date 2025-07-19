"""
Journey collection service for TrackRat V2.

Collects complete journey details using the getTrainStopList API.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.db.engine import get_session
from trackrat.models.api import NJTransitStopData, NJTransitTrainData
from trackrat.models.database import JourneySnapshot, JourneyStop, TrainJourney
from trackrat.utils.time import now_et, parse_njt_time

logger = get_logger(__name__)


class JourneyCollector:
    """Collects complete journey data for trains."""

    def __init__(self, njt_client: NJTransitClient) -> None:
        """Initialize the journey collector.

        Args:
            njt_client: NJ Transit API client
        """
        self.njt_client = njt_client

    async def run(self) -> dict[str, Any]:
        """Run the collector with a database session.

        Returns:
            Collection results
        """
        async with get_session() as session:
            return await self.collect(session)

    async def collect(self, session: AsyncSession) -> dict[str, Any]:
        """Collect journey data for trains that need updates.

        This method finds trains that:
        1. Don't have complete journey data yet
        2. Are active (not completed/cancelled) and need periodic updates

        Args:
            session: Database session

        Returns:
            Collection results summary
        """
        logger.info("starting_journey_collection")

        # Find trains that need collection
        trains_to_collect = await self.find_trains_needing_collection(session)

        logger.info("found_trains_for_collection", count=len(trains_to_collect))

        results: dict[str, Any] = {
            "trains_processed": 0,
            "successful": 0,
            "failed": 0,
            "errors": [],
        }

        for journey in trains_to_collect:
            try:
                await self.collect_journey_details(session, journey)
                results["successful"] += 1
            except Exception as e:
                logger.error(
                    "failed_to_collect_journey",
                    train_id=journey.train_id,
                    journey_id=journey.id,
                    error=str(e),
                )
                results["failed"] += 1
                results["errors"].append(
                    {"train_id": journey.train_id, "error": str(e)}
                )

            results["trains_processed"] += 1

        logger.info("journey_collection_complete", **results)
        return results

    async def find_trains_needing_collection(
        self, session: AsyncSession, limit: int = 50
    ) -> list[TrainJourney]:
        """Find trains that need journey collection.

        Args:
            session: Database session
            limit: Maximum number of trains to process

        Returns:
            List of journeys needing collection
        """
        cutoff_time = now_et() - timedelta(minutes=15)

        # Query for trains needing updates
        stmt = (
            select(TrainJourney)
            .where(
                and_(
                    # Not cancelled or completed
                    TrainJourney.is_cancelled.is_not(True),
                    TrainJourney.is_completed.is_not(True),
                    # Either no complete journey or stale data
                    or_(
                        TrainJourney.has_complete_journey.is_not(True),
                        TrainJourney.last_updated_at < cutoff_time,
                    ),
                )
            )
            .order_by(
                # Prioritize trains without any data
                TrainJourney.has_complete_journey,
                # Then by oldest update
                TrainJourney.last_updated_at,
            )
            .limit(limit)
        )

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def collect_journey_details(
        self, session: AsyncSession, journey: TrainJourney
    ) -> None:
        """Collect complete journey details for a train.

        Args:
            session: Database session
            journey: Journey to collect data for
        """
        now_et()

        logger.info(
            "collecting_journey_details",
            train_id=journey.train_id,
            journey_id=journey.id,
            last_updated=(
                journey.last_updated_at.isoformat() if journey.last_updated_at else None
            ),
        )

        # Get train stop list
        if not journey.train_id:
            raise ValueError(f"Journey {journey.id} has no train_id")
        train_data = await self.njt_client.get_train_stop_list(journey.train_id)

        # Create snapshot for historical analysis
        await self.create_journey_snapshot(session, journey, train_data)

        # Update journey metadata
        await self.update_journey_metadata(session, journey, train_data)

        # Update stops
        await self.update_journey_stops(session, journey, train_data.STOPS)

        # Check if journey is complete
        await self.check_journey_completion(session, journey, train_data.STOPS)

        # Commit changes
        await session.flush()

        logger.info(
            "journey_details_collected",
            train_id=journey.train_id,
            stops_count=len(train_data.STOPS),
            is_completed=journey.is_completed,
            is_cancelled=journey.is_cancelled,
        )

    async def create_journey_snapshot(
        self,
        session: AsyncSession,
        journey: TrainJourney,
        train_data: NJTransitTrainData,
    ) -> JourneySnapshot:
        """Create a historical snapshot of the journey data.

        Args:
            session: Database session
            journey: Journey record
            train_data: Raw API response data

        Returns:
            Created snapshot
        """
        # Extract metrics
        completed_stops = sum(1 for stop in train_data.STOPS if stop.DEPARTED == "YES")

        # Extract track assignments
        track_assignments = {
            stop.STATION_2CHAR: stop.TRACK for stop in train_data.STOPS if stop.TRACK
        }

        # Calculate overall delay (from last departed stop)
        delay_minutes = 0
        for stop in reversed(train_data.STOPS):
            if stop.DEPARTED == "YES" and stop.STOP_STATUS:
                # Parse delay from status if available
                if "Late" in stop.STOP_STATUS:
                    # Extract delay if in format "X minutes late"
                    try:
                        parts = stop.STOP_STATUS.split()
                        if "minutes" in parts:
                            idx = parts.index("minutes")
                            if idx > 0:
                                delay_minutes = int(parts[idx - 1])
                    except (ValueError, IndexError):
                        pass
                break

        snapshot = JourneySnapshot(
            journey_id=journey.id,
            captured_at=now_et(),
            raw_stop_list_data=train_data.dict(),
            train_status=self.determine_train_status(train_data.STOPS),
            delay_minutes=delay_minutes,
            completed_stops=completed_stops,
            total_stops=len(train_data.STOPS),
            track_assignments=track_assignments,
        )

        session.add(snapshot)
        return snapshot

    async def update_journey_metadata(
        self,
        session: AsyncSession,
        journey: TrainJourney,
        train_data: NJTransitTrainData,
    ) -> None:
        """Update journey metadata from train data.

        Args:
            session: Database session
            journey: Journey to update
            train_data: Train data from API
        """
        # Update basic info
        journey.destination = train_data.DESTINATION
        journey.line_color = train_data.BACKCOLOR.strip()

        # Update terminal station (last stop)
        if train_data.STOPS:
            journey.terminal_station_code = train_data.STOPS[-1].STATION_2CHAR

            # Update scheduled arrival if not set
            if not journey.scheduled_arrival:
                last_stop = train_data.STOPS[-1]
                if last_stop.TIME:
                    journey.scheduled_arrival = parse_njt_time(last_stop.TIME)

        # Mark as having complete journey data
        journey.has_complete_journey = True
        journey.stops_count = len(train_data.STOPS)
        journey.last_updated_at = now_et()
        journey.update_count = (journey.update_count or 0) + 1

    async def update_journey_stops(
        self,
        session: AsyncSession,
        journey: TrainJourney,
        stops_data: list[NJTransitStopData],
    ) -> None:
        """Update journey stops from API data.

        Args:
            session: Database session
            journey: Journey record
            stops_data: List of stop data from API
        """
        for sequence, stop_data in enumerate(stops_data):
            # Find existing stop or create new
            stmt = select(JourneyStop).where(
                and_(
                    JourneyStop.journey_id == journey.id,
                    JourneyStop.station_code == stop_data.STATION_2CHAR,
                )
            )
            stop = await session.scalar(stmt)

            if not stop:
                stop = JourneyStop(
                    journey_id=journey.id,
                    station_code=stop_data.STATION_2CHAR,
                    station_name=stop_data.STATIONNAME,
                    stop_sequence=sequence,
                )
                session.add(stop)

            # Update times
            if stop_data.TIME:
                stop.scheduled_arrival = parse_njt_time(stop_data.TIME)
            if stop_data.DEP_TIME:
                stop.scheduled_departure = parse_njt_time(stop_data.DEP_TIME)

            # Update actual times (for now, same as scheduled + delay)
            if stop_data.DEPARTED == "YES":
                stop.actual_arrival = stop.scheduled_arrival
                stop.actual_departure = stop.scheduled_departure

            # Update status
            stop.has_departed_station = stop_data.DEPARTED == "YES"

            # Update track if available
            if stop_data.TRACK:
                stop.track = stop_data.TRACK
                if not stop.track_assigned_at:
                    stop.track_assigned_at = now_et()

            # Update stop characteristics
            stop.pickup_only = bool(stop_data.PICKUP)
            stop.dropoff_only = bool(stop_data.DROPOFF)

    async def check_journey_completion(
        self,
        session: AsyncSession,
        journey: TrainJourney,
        stops_data: list[NJTransitStopData],
    ) -> None:
        """Check if journey is completed or cancelled.

        Args:
            session: Database session
            journey: Journey record
            stops_data: List of stop data
        """
        if not stops_data:
            return

        # Check if last stop is departed
        last_stop = stops_data[-1]
        if last_stop.DEPARTED == "YES":
            journey.is_completed = True
            if last_stop.TIME:
                journey.actual_arrival = parse_njt_time(last_stop.TIME)
            logger.info(
                "journey_completed",
                train_id=journey.train_id,
                arrival_time=(
                    journey.actual_arrival.isoformat()
                    if journey.actual_arrival
                    else "unknown"
                ),
            )

        # Check for cancellation (all stops cancelled)
        cancelled_stops = sum(
            1 for stop in stops_data if stop.STOP_STATUS == "Cancelled"
        )

        if cancelled_stops == len(stops_data):
            journey.is_cancelled = True
            logger.info("journey_cancelled", train_id=journey.train_id)

    def determine_train_status(self, stops_data: list[NJTransitStopData]) -> str:
        """Determine overall train status from stops.

        Args:
            stops_data: List of stop data

        Returns:
            Overall status string
        """
        if not stops_data:
            return "UNKNOWN"

        # Check if all stops are cancelled
        if all(stop.STOP_STATUS == "Cancelled" for stop in stops_data):
            return "CANCELLED"

        # Find current position
        for i, stop in enumerate(stops_data):
            if stop.DEPARTED != "YES":
                # This is the next stop
                if i == 0:
                    return "NOT_DEPARTED"
                elif stop.TRACK:
                    return "BOARDING"
                else:
                    return "IN_TRANSIT"

        # All stops departed
        return "COMPLETED"

    async def collect_single_journey(
        self, train_id: str, journey_date: datetime | None = None
    ) -> dict[str, Any]:
        """Collect journey data for a specific train.

        This is useful for just-in-time updates.

        Args:
            train_id: Train ID to collect
            journey_date: Optional journey date (defaults to today)

        Returns:
            Collection result
        """
        async with get_session() as session:
            # Find the journey
            stmt = select(TrainJourney).where(TrainJourney.train_id == train_id)

            if journey_date:
                stmt = stmt.where(TrainJourney.journey_date == journey_date)

            stmt = stmt.order_by(TrainJourney.journey_date.desc()).limit(1)

            journey = await session.scalar(stmt)

            if not journey:
                return {
                    "success": False,
                    "error": f"Journey not found for train {train_id}",
                }

            try:
                await self.collect_journey_details(session, journey)
                await session.commit()

                return {
                    "success": True,
                    "train_id": train_id,
                    "journey_id": journey.id,
                    "stops_count": journey.stops_count,
                    "is_completed": journey.is_completed,
                }
            except Exception as e:
                await session.rollback()
                return {"success": False, "error": str(e)}
