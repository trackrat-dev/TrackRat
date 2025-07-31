"""
Journey collection service for TrackRat V2.

Collects complete journey details using the getTrainStopList API.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.base import BaseJourneyCollector
from trackrat.collectors.njt.client import NJTransitClient, TrainNotFoundError
from trackrat.config.stations import get_station_name
from trackrat.db.engine import get_session
from trackrat.models.api import NJTransitStopData, NJTransitTrainData
from trackrat.models.database import JourneySnapshot, JourneyStop, TrainJourney
from trackrat.services.transit_analyzer import TransitAnalyzer
from trackrat.utils.time import now_et, parse_njt_time

logger = get_logger(__name__)


class JourneyCollector(BaseJourneyCollector):
    """Collects complete journey data for trains."""

    def __init__(self, njt_client: NJTransitClient) -> None:
        """Initialize the journey collector.

        Args:
            njt_client: NJ Transit API client
        """
        self.njt_client = njt_client

    async def collect_journey(
        self, train_id: str, skip_enhancement: bool = False
    ) -> TrainJourney | None:
        """Collect journey details for a specific train.

        Args:
            train_id: The train ID to collect journey details for
            skip_enhancement: If True, skip departure board enhancement (for scheduled batch collection)

        Returns:
            TrainJourney object if successful, None if failed
        """
        async with get_session() as session:
            return await self.collect_journey_with_session(session, train_id, skip_enhancement)

    async def collect_journey_with_session(
        self, session: AsyncSession, train_id: str, skip_enhancement: bool = False
    ) -> TrainJourney | None:
        """Collect journey details for a specific train using provided session.

        Args:
            session: Database session to use
            train_id: The train ID to collect journey details for
            skip_enhancement: If True, skip departure board enhancement (for scheduled batch collection)

        Returns:
            TrainJourney object if successful, None if failed
        """
        # Find the journey for this train
        stmt = select(TrainJourney).where(
            and_(
                TrainJourney.train_id == train_id,
                TrainJourney.data_source == "NJT",
            )
        )
        journey = await session.scalar(stmt)

        if not journey:
            logger.warning("journey_not_found", train_id=train_id)
            return None

        try:
            await self.collect_journey_details(session, journey, skip_enhancement)
            return journey
        except TrainNotFoundError as e:
            # Train no longer available - this is handled gracefully in collect_journey_details
            logger.info(
                "collect_journey_train_not_found", train_id=train_id, error=str(e)
            )
            return journey
        except Exception as e:
            logger.error("collect_journey_failed", train_id=train_id, error=str(e))
            raise  # Re-raise to let caller handle transaction

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
        3. Historical trains that need transit time analysis

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
            "historical_backfilled": 0,
        }

        # Process current trains
        for journey in trains_to_collect:
            try:
                await self.collect_journey_details(session, journey)
                results["successful"] += 1
            except TrainNotFoundError as e:
                # Train no longer available - this is expected and handled
                logger.info(
                    "train_not_found_during_collection",
                    train_id=journey.train_id,
                    journey_id=journey.id,
                    error=str(e),
                )
                results[
                    "successful"
                ] += 1  # Count as successful since it's handled properly
            except Exception as e:
                logger.error(
                    "failed_to_collect_journey",
                    train_id=journey.train_id,
                    journey_id=journey.id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                results["failed"] += 1
                results["errors"].append(
                    {"train_id": journey.train_id, "error": str(e)}
                )

            results["trains_processed"] += 1

        # Process historical trains for backfill
        historical_trains = await self.find_historical_trains_for_backfill(session)
        
        if historical_trains:
            logger.info("found_historical_trains_for_backfill", count=len(historical_trains))
            
            for journey in historical_trains:
                try:
                    await self.collect_journey_details(session, journey, skip_enhancement=True)
                    results["successful"] += 1
                    results["historical_backfilled"] += 1
                    
                    if results["historical_backfilled"] % 10 == 0:
                        logger.info("backfill_progress", processed=results["historical_backfilled"])
                        
                except Exception as e:
                    logger.error(
                        "failed_to_backfill_historical_journey",
                        train_id=journey.train_id,
                        journey_id=journey.id,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    results["failed"] += 1
                    results["errors"].append(
                        {"train_id": journey.train_id, "error": str(e), "type": "historical"}
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
                    # Only NJT trains
                    TrainJourney.data_source == "NJT",
                    # Not cancelled, completed, or expired
                    TrainJourney.is_cancelled.is_not(True),
                    TrainJourney.is_completed.is_not(True),
                    TrainJourney.is_expired.is_not(True),
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

    async def find_historical_trains_for_backfill(
        self, session: AsyncSession
    ) -> list[TrainJourney]:
        """Find historical trains that need transit time analysis.

        These are completed NJT journeys that have stop data but haven't 
        had the 30-minute inference logic applied yet.

        Args:
            session: Database session

        Returns:
            List of historical journeys needing analysis
        """
        # Query for historical journeys that haven't been analyzed
        stmt = (
            select(TrainJourney)
            .where(
                and_(
                    # Only NJT trains
                    TrainJourney.data_source == "NJT",
                    # Have complete journey data with stops
                    TrainJourney.has_complete_journey.is_(True),
                    TrainJourney.stops_count > 0,
                    # No actual departure time set (haven't been analyzed)
                    TrainJourney.actual_departure.is_(None),
                    # Completed or older journeys (not active)
                    or_(
                        TrainJourney.is_completed.is_(True),
                        TrainJourney.is_cancelled.is_(True),
                        TrainJourney.is_expired.is_(True),
                    ),
                )
            )
            .order_by(TrainJourney.journey_date.desc())
        )

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def collect_journey_details(
        self,
        session: AsyncSession,
        journey: TrainJourney,
        skip_enhancement: bool = False,
    ) -> None:
        """Collect complete journey details for a train.

        Args:
            session: Database session
            journey: Journey to collect data for
            skip_enhancement: If True, skip departure board enhancement (for scheduled batch collection)
        """
        now_et()

        # Track start time for performance measurement
        start_time = now_et()

        logger.debug(
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

        try:
            train_data = await self.njt_client.get_train_stop_list(journey.train_id)
        except TrainNotFoundError:
            # Train is no longer available - increment error count
            journey.api_error_count = (journey.api_error_count or 0) + 1
            journey.last_updated_at = now_et()
            journey.update_count = (journey.update_count or 0) + 1

            # After 2 failed attempts, mark as expired
            if journey.api_error_count >= 2:
                journey.is_expired = True
                logger.warning(
                    "train_marked_expired",
                    train_id=journey.train_id,
                    journey_id=journey.id,
                    api_error_count=journey.api_error_count,
                )
            else:
                logger.warning(
                    "train_not_found_error_incremented",
                    train_id=journey.train_id,
                    journey_id=journey.id,
                    api_error_count=journey.api_error_count,
                )

            await session.flush()
            return

        # Enhance with real-time departure board data if applicable
        if not skip_enhancement:
            await self.enhance_with_departure_board_data(journey, train_data)

        # Create snapshot for historical analysis
        await self.create_journey_snapshot(session, journey, train_data)

        # Update journey metadata
        await self.update_journey_metadata(session, journey, train_data)

        # Update stops
        await self.update_journey_stops(session, journey, train_data.STOPS)

        # Check if journey is complete
        await self.check_journey_completion(session, journey, train_data.STOPS)

        # Analyze transit times and dwell times if journey has actual times
        if journey.actual_departure:
            transit_analyzer = TransitAnalyzer()
            await transit_analyzer.analyze_journey(session, journey)

        # Commit changes
        await session.flush()

        # Calculate processing time
        end_time = now_et()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

        logger.info(
            "journey_collected",
            train_id=journey.train_id,
            journey_id=journey.id,
            stops_count=len(train_data.STOPS),
            is_completed=journey.is_completed,
            is_cancelled=journey.is_cancelled,
            processing_time_ms=processing_time_ms,
            destination=train_data.DESTINATION,
            update_count=journey.update_count,
        )

    async def create_journey_snapshot(
        self,
        session: AsyncSession,
        journey: TrainJourney,
        train_data: NJTransitTrainData,
    ) -> JourneySnapshot:
        """Create a historical snapshot of the journey data.

        NOTE: Only keeps one snapshot per journey to prevent database growth.
        Replaces any existing snapshots for this journey.

        Args:
            session: Database session
            journey: Journey record
            train_data: Raw API response data

        Returns:
            Created snapshot
        """
        # Delete existing snapshots for this journey to maintain single snapshot per journey
        await session.execute(
            delete(JourneySnapshot).where(JourneySnapshot.journey_id == journey.id)
        )

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
            raw_stop_list_data={},  # Deactivated to reduce database size - full data is in journey_stops
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

        # Reset error count on successful update
        if journey.api_error_count and journey.api_error_count > 0:
            logger.info(
                "resetting_api_error_count",
                train_id=journey.train_id,
                previous_count=journey.api_error_count,
            )
            journey.api_error_count = 0

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
                    station_name=stop_data.STATIONNAME
                    or get_station_name(stop_data.STATION_2CHAR or ""),
                    stop_sequence=sequence,
                )
                session.add(stop)

            # Update scheduled times
            if stop_data.TIME:
                stop.scheduled_arrival = parse_njt_time(stop_data.TIME)
            if stop_data.DEP_TIME:
                stop.scheduled_departure = parse_njt_time(stop_data.DEP_TIME)

            # Update updated times (for NJT, same as scheduled since no estimates provided)
            stop.updated_arrival = stop.scheduled_arrival
            stop.updated_departure = stop.scheduled_departure

            # Update actual times only if train has departed
            if stop_data.DEPARTED == "YES":
                stop.actual_arrival = stop.scheduled_arrival
                stop.actual_departure = stop.scheduled_departure
                stop.has_departed_station = True
            elif stop.scheduled_departure and now_et() > stop.scheduled_departure + timedelta(minutes=30):
                # Infer departure after 30 minutes past scheduled time
                stop.actual_arrival = stop.scheduled_arrival
                stop.actual_departure = stop.scheduled_departure
                stop.has_departed_station = True
                logger.debug(
                    "inferred_departure_after_delay",
                    train_id=journey.train_id,
                    station_code=stop.station_code,
                    scheduled_departure=stop.scheduled_departure.isoformat(),
                    current_time=now_et().isoformat(),
                )
            else:
                stop.has_departed_station = False

            # Update raw status information
            stop.raw_njt_departed_flag = stop_data.DEPARTED

            # Update track if available - but don't overwrite existing track from discovery
            if stop_data.TRACK:
                stop.track = stop_data.TRACK
                if not stop.track_assigned_at:
                    stop.track_assigned_at = now_et()
            elif not stop_data.TRACK and stop.track:
                # Preserve track from discovery if API doesn't provide it
                logger.debug(
                    "preserving_track_from_discovery",
                    train_id=journey.train_id,
                    station_code=stop.station_code,
                    track=stop.track,
                )

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

        # Set journey actual_departure from first departed stop (if not already set)
        if not journey.actual_departure:
            # Find the first stop that has departed by querying directly
            first_departed_stmt = (
                select(JourneyStop)
                .where(
                    and_(
                        JourneyStop.journey_id == journey.id,
                        JourneyStop.has_departed_station.is_(True),
                    )
                )
                .order_by(JourneyStop.stop_sequence)
                .limit(1)
            )
            first_departed_stop = await session.scalar(first_departed_stmt)
            
            if first_departed_stop and first_departed_stop.actual_departure:
                journey.actual_departure = first_departed_stop.actual_departure
                logger.debug(
                    "set_journey_actual_departure",
                    train_id=journey.train_id,
                    departure_time=journey.actual_departure.isoformat(),
                    station_code=first_departed_stop.station_code,
                )

    def _is_monitored_station(self, station_code: str) -> bool:
        """Check if station is monitored for departure board data.

        Args:
            station_code: Two-character station code

        Returns:
            True if station is in our monitored stations list
        """
        return station_code in ["NY", "NP", "TR", "LB", "PL", "DN", "JA", "HB", "RA"]

    def _is_departing_within_minutes(
        self, scheduled_departure_str: str, minutes: int
    ) -> bool:
        """Check if train departs within specified minutes from now.

        Args:
            scheduled_departure_str: Scheduled departure time in NJT format
            minutes: Number of minutes to check within

        Returns:
            True if train departs within the specified time window
        """
        try:
            scheduled_time = parse_njt_time(scheduled_departure_str)
            now = now_et()
            time_until_departure = (scheduled_time - now).total_seconds() / 60
            return 0 <= time_until_departure <= minutes
        except Exception:
            # If we can't parse the time, skip enhancement for safety
            return False

    def _apply_departure_board_data(
        self, stop: NJTransitStopData, train_entry: dict[str, Any]
    ) -> None:
        """Apply real-time departure board data to a stop.

        Args:
            stop: Stop data to enhance
            train_entry: Train entry from departure board
        """
        # Update track if available in departure board
        if "TRACK" in train_entry and train_entry["TRACK"]:
            stop.TRACK = str(train_entry["TRACK"])
            logger.debug(
                "enhanced_stop_with_departure_board_track",
                station=stop.STATION_2CHAR,
                track=stop.TRACK,
            )

        # Could add other fields here if needed in the future
        # e.g., real-time status, departure time updates, etc.

    async def enhance_with_departure_board_data(
        self, journey: TrainJourney, train_data: NJTransitTrainData
    ) -> None:
        """Enhance train data with real-time departure board info for origin station.

        Args:
            journey: Journey record
            train_data: Train data from getTrainStopList to enhance
        """
        # Only proceed if origin is monitored and train hasn't departed
        if not journey.origin_station_code or not self._is_monitored_station(
            journey.origin_station_code
        ):
            return

        if train_data.STOPS and train_data.STOPS[0].DEPARTED == "YES":
            return  # Already departed from origin

        # Only enhance if train is departing within 15 minutes
        if train_data.STOPS and train_data.STOPS[0].DEP_TIME:
            if not self._is_departing_within_minutes(train_data.STOPS[0].DEP_TIME, 15):
                return  # Not departing soon enough to need real-time data

        try:
            # Get departure board for origin station
            schedule_response = await self.njt_client.get_train_schedule_with_stops(
                journey.origin_station_code or ""
            )
            departure_board = schedule_response.get("ITEMS", [])

            # Find our train in the departure board
            for train_entry in departure_board:
                if train_entry.get("TRAIN_ID") == journey.train_id:
                    # Enhance origin stop with real-time data
                    self._apply_departure_board_data(train_data.STOPS[0], train_entry)
                    logger.debug(
                        "enhanced_train_with_departure_board_data",
                        train_id=journey.train_id,
                        origin_station=journey.origin_station_code,
                    )
                    break

        except Exception as e:
            # Log but don't fail - departure board enhancement is optional
            logger.debug(
                "departure_board_enhancement_failed",
                train_id=journey.train_id,
                origin_station=journey.origin_station_code,
                error=str(e),
            )

    async def check_journey_completion_v2(
        self,
        session: AsyncSession,
        journey: TrainJourney,
        stops_data: list[NJTransitStopData],
    ) -> None:
        """Check if journey is complete and update status accordingly.

        Args:
            session: Database session
            journey: Journey to check
            stops_data: List of stop data
        """
        if not stops_data:
            return

        # Check if cancelled
        if all(stop.STOP_STATUS == "Cancelled" for stop in stops_data):
            journey.is_cancelled = True
            journey.is_completed = True
            return

        # Check if all stops have been departed
        all_departed = all(stop.DEPARTED == "YES" for stop in stops_data)
        if all_departed:
            journey.is_completed = True

            # Set actual arrival time from last stop
            last_stop = stops_data[-1]
            if last_stop.TIME:
                journey.actual_arrival = parse_njt_time(last_stop.TIME)

            # Set actual departure time from first stop
            first_stop = stops_data[0]
            if first_stop.DEP_TIME:
                journey.actual_departure = parse_njt_time(first_stop.DEP_TIME)

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
