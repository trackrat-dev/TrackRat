"""
Journey collection service for TrackRat V2.

Collects complete journey details using the getTrainStopList API.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.base import BaseJourneyCollector
from trackrat.collectors.njt.client import NJTransitClient, TrainNotFoundError
from trackrat.config.stations import get_station_name
from trackrat.db.engine import get_session
from trackrat.models.api import NJTransitStopData, NJTransitTrainData
from trackrat.models.database import JourneySnapshot, JourneyStop, TrainJourney
from trackrat.utils.sanitize import sanitize_track
from trackrat.utils.time import ET, now_et, parse_njt_time

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
            return await self.collect_journey_with_session(
                session, train_id, skip_enhancement
            )

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
            logger.info(
                "found_historical_trains_for_backfill", count=len(historical_trains)
            )

            for journey in historical_trains:
                try:
                    await self.collect_journey_details(
                        session, journey, skip_enhancement=True
                    )
                    results["successful"] += 1
                    results["historical_backfilled"] += 1

                    if results["historical_backfilled"] % 10 == 0:
                        logger.info(
                            "backfill_progress",
                            processed=results["historical_backfilled"],
                        )

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
                        {
                            "train_id": journey.train_id,
                            "error": str(e),
                            "type": "historical",
                        }
                    )

                results["trains_processed"] += 1

        # Clean up old journeys to prevent database clutter
        await self._expire_old_journeys(session)

        logger.info("journey_collection_complete", **results)
        return results

    async def _expire_old_journeys(self, session: AsyncSession) -> None:
        """Mark yesterday's incomplete journeys as expired to clean up database."""
        cutoff_date = now_et().date()

        stmt = (
            update(TrainJourney)
            .where(
                and_(
                    TrainJourney.journey_date < cutoff_date,
                    TrainJourney.is_completed.is_not(True),
                    TrainJourney.is_expired.is_not(True),
                    TrainJourney.data_source == "NJT",
                )
            )
            .values(is_expired=True)
        )

        result = await session.execute(stmt)

        if result.rowcount > 0:
            logger.info(
                "expired_old_journeys",
                count=result.rowcount,
                cutoff_date=cutoff_date.isoformat(),
            )

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
                    # Only today's trains (prevent updating old journeys)
                    TrainJourney.journey_date >= now_et().date(),
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
                    # Only recent trains (last 2 days max)
                    TrainJourney.journey_date >= now_et().date() - timedelta(days=2),
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

    async def _has_stops_with_actual_times(
        self, session: AsyncSession, journey_id: int
    ) -> bool:
        """Check if this journey has any stops with actual arrival or departure times."""
        stmt = (
            select(JourneyStop.id)
            .where(
                and_(
                    JourneyStop.journey_id == journey_id,
                    or_(
                        JourneyStop.actual_departure.is_not(None),
                        JourneyStop.actual_arrival.is_not(None),
                    ),
                )
            )
            .limit(1)
        )

        result = await session.execute(stmt)
        has_actual_times = result.scalar() is not None

        logger.info(
            "checked_stops_for_actual_times",
            journey_id=journey_id,
            has_actual_times=has_actual_times,
        )

        return has_actual_times

    def _normalize_destination(self, destination: str) -> str:
        """Normalize destination name for comparison.

        Handles variations like:
        - "New York -SEC &#9992" -> "new york"
        - "Penn Station New York" -> "new york"
        - "Trenton" -> "trenton"
        """
        if not destination:
            return ""

        # Convert to lowercase and remove special characters
        normalized = destination.lower()

        # Handle New York variations
        if any(variant in normalized for variant in ["new york", "penn station"]):
            return "new york"

        # Remove common suffixes and prefixes
        normalized = normalized.replace(" -sec", "").replace("&#9992", "")
        normalized = normalized.replace("penn station ", "")

        # Remove extra whitespace
        normalized = " ".join(normalized.split())

        return normalized.strip()

    def _normalize_line_code(self, line_code: str) -> str:
        """Normalize line code for comparison.

        Handles variations like:
        - "No" -> "ne" (Northeast Corridor)
        - "NE" -> "ne" (Northeast Corridor)
        - "M&E" -> "me" (Morris & Essex)
        """
        if not line_code:
            return ""

        normalized = line_code.lower().strip()

        # Handle Northeast Corridor variations
        if normalized in ["no", "ne"]:
            return "ne"

        return normalized

    async def _is_same_journey(
        self, stored_journey: TrainJourney, api_train_data: NJTransitTrainData
    ) -> bool:
        """
        Verify if API data represents the same journey as our stored record.

        Uses key signals to detect journey changes:
        - Destination must match (after normalization)
        - First stop departure time should be similar (±10 min tolerance)

        NOTE: Line code validation removed as it's unreliable across different API calls
        """
        # Signal 1: Destination must match (after normalization)
        stored_dest_normalized = self._normalize_destination(
            stored_journey.destination or ""
        )
        api_dest_normalized = self._normalize_destination(
            api_train_data.DESTINATION or ""
        )

        if stored_dest_normalized != api_dest_normalized:
            logger.warning(
                "journey_mismatch_destination",
                journey_id=stored_journey.id,
                train_id=stored_journey.train_id,
                stored_destination=stored_journey.destination,
                api_destination=api_train_data.DESTINATION,
                stored_normalized=stored_dest_normalized,
                api_normalized=api_dest_normalized,
                # Additional context
                stored_origin=stored_journey.origin_station_code,
                stored_line=stored_journey.line_code,
                api_line=api_train_data.LINECODE,
                journey_date=(
                    stored_journey.journey_date.isoformat()
                    if stored_journey.journey_date
                    else None
                ),
                has_complete_journey=stored_journey.has_complete_journey,
            )
            return False

        # NOTE: Line code check removed - NJT API returns inconsistent line codes
        # between discovery (e.g., "No") and journey details (e.g., "NC")
        # The destination and departure time are sufficient to identify the journey

        # Update line code if API provides a different one (likely more accurate)
        if (
            api_train_data.LINECODE
            and api_train_data.LINECODE != stored_journey.line_code
        ):
            logger.info(
                "updating_line_code",
                journey_id=stored_journey.id,
                train_id=stored_journey.train_id,
                old_line_code=stored_journey.line_code,
                new_line_code=api_train_data.LINECODE,
            )
            stored_journey.line_code = api_train_data.LINECODE

        # Signal 2: First stop departure time should match (with tolerance)
        # IMPORTANT: If the journey doesn't have complete data yet, skip this check
        # because discovery might have recorded the wrong origin/departure time
        if stored_journey.has_complete_journey:
            if api_train_data.STOPS and api_train_data.STOPS[0].DEP_TIME:
                first_stop = api_train_data.STOPS[0]
                dep_time = first_stop.DEP_TIME
                if dep_time is not None:
                    api_departure = parse_njt_time(dep_time)
                    if stored_journey.scheduled_departure is not None:
                        # Ensure stored departure is timezone-aware for comparison
                        stored_departure = stored_journey.scheduled_departure
                        if stored_departure.tzinfo is None:
                            # If naive, assume it's already in Eastern time
                            stored_departure = ET.localize(stored_departure)

                        time_diff = abs(
                            (api_departure - stored_departure).total_seconds()
                        )
                    else:
                        time_diff = 0  # If no stored departure, consider it a match

                # Allow 10 minute tolerance for schedule adjustments
                if time_diff > 600:
                    # Before rejecting, check if stored origin appears as an intermediate stop
                    # This happens when discovery finds a train at an intermediate station
                    stored_origin_found_in_stops = False

                    if stored_journey.origin_station_code:
                        for stop in api_train_data.STOPS:
                            if stop.STATION_2CHAR == stored_journey.origin_station_code:
                                # Found the stored origin as an intermediate stop
                                # Check if its departure time matches what we have stored
                                if stop.DEP_TIME:
                                    intermediate_departure = parse_njt_time(
                                        stop.DEP_TIME
                                    )
                                    intermediate_time_diff = abs(
                                        (
                                            intermediate_departure - stored_departure
                                        ).total_seconds()
                                    )

                                    if (
                                        intermediate_time_diff <= 600
                                    ):  # Within 10-minute tolerance
                                        # This is the same journey, just discovered at wrong station
                                        logger.info(
                                            "journey_discovered_at_intermediate_station",
                                            journey_id=stored_journey.id,
                                            train_id=stored_journey.train_id,
                                            stored_origin=stored_journey.origin_station_code,
                                            actual_origin=first_stop.STATION_2CHAR,
                                            stored_departure=stored_departure.isoformat(),
                                            intermediate_stop_departure=intermediate_departure.isoformat(),
                                            actual_first_departure=api_departure.isoformat(),
                                            time_diff_minutes=int(
                                                intermediate_time_diff / 60
                                            ),
                                        )
                                        stored_origin_found_in_stops = True
                                        # Reset has_complete_journey so correction can happen
                                        stored_journey.has_complete_journey = False
                                        break

                    # If we found the stored origin as an intermediate stop, continue processing
                    # so the journey correction logic can fix the origin
                    if stored_origin_found_in_stops:
                        # Don't return False - let the journey continue to be processed
                        pass
                    else:
                        # This is actually a different journey
                        logger.warning(
                            "journey_mismatch_departure_time",
                            journey_id=stored_journey.id,
                            train_id=stored_journey.train_id,
                            stored_departure=(
                                stored_journey.scheduled_departure.isoformat()
                                if stored_journey.scheduled_departure
                                else None
                            ),
                            api_departure=api_departure.isoformat(),
                            difference_minutes=int(time_diff / 60),
                            # Additional debugging context
                            stored_origin=stored_journey.origin_station_code,
                            api_first_station=first_stop.STATION_2CHAR,
                            api_first_station_name=first_stop.STATIONNAME,
                            stored_destination=stored_journey.destination,
                            api_destination=api_train_data.DESTINATION,
                            stored_line_code=stored_journey.line_code,
                            api_line_code=api_train_data.LINECODE,
                            journey_date=(
                                stored_journey.journey_date.isoformat()
                                if stored_journey.journey_date
                                else None
                            ),
                            has_complete_journey=stored_journey.has_complete_journey,
                            stored_departure_tz_info=str(stored_departure.tzinfo),
                            api_departure_tz_info=str(api_departure.tzinfo),
                            raw_api_dep_time=dep_time,
                        )
                        return False
        else:
            # Journey doesn't have complete data yet - likely discovered at an intermediate station
            # The journey collector will fix the origin and departure time
            logger.info(
                "skipping_departure_time_check_for_incomplete_journey",
                journey_id=stored_journey.id,
                train_id=stored_journey.train_id,
                has_complete_journey=stored_journey.has_complete_journey,
            )

        # Log successful validation for debugging patterns
        logger.debug(
            "journey_validation_successful",
            journey_id=stored_journey.id,
            train_id=stored_journey.train_id,
            destinations_matched=f"{stored_dest_normalized} == {api_dest_normalized}",
            departure_time_check_skipped=not stored_journey.has_complete_journey,
            line_code_updated=(
                (api_train_data.LINECODE != stored_journey.line_code)
                if api_train_data.LINECODE
                else False
            ),
        )

        return True

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

        # Debug: Log journey validation inputs
        logger.debug(
            "validating_journey_match",
            journey_id=journey.id,
            train_id=journey.train_id,
            stored_destination=journey.destination,
            api_destination=train_data.DESTINATION,
            stored_line_code=journey.line_code,
            api_line_code=train_data.LINECODE,
            stored_departure=(
                journey.scheduled_departure.isoformat()
                if journey.scheduled_departure
                else None
            ),
            api_first_departure=(
                train_data.STOPS[0].DEP_TIME if train_data.STOPS else None
            ),
            has_complete_journey=journey.has_complete_journey,
            api_stops_count=len(train_data.STOPS),
        )

        # Verify this API data matches our stored journey
        if not await self._is_same_journey(journey, train_data):
            # API returned data for a different journey - mark this one as expired
            journey.is_expired = True
            journey.api_error_count = 99  # High value to prevent retry

            logger.warning(
                "journey_expired_due_to_mismatch",
                journey_id=journey.id,
                train_id=journey.train_id,
                journey_date=(
                    journey.journey_date.isoformat() if journey.journey_date else None
                ),
                reason="API returned data for different journey",
                # Additional context about what mismatched
                stored_destination=journey.destination,
                api_destination=train_data.DESTINATION,
                stored_origin=journey.origin_station_code,
                api_first_station=(
                    train_data.STOPS[0].STATION_2CHAR if train_data.STOPS else None
                ),
                stored_departure=(
                    journey.scheduled_departure.isoformat()
                    if journey.scheduled_departure
                    else None
                ),
                api_first_departure=(
                    train_data.STOPS[0].DEP_TIME if train_data.STOPS else None
                ),
                stored_line=journey.line_code,
                api_line=train_data.LINECODE,
                has_complete_journey=journey.has_complete_journey,
                update_count=journey.update_count,
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

        # Commit changes to make sure all updates are persisted
        await session.flush()

        # Analyze transit times and dwell times if any stops have actual times
        # Transit time analysis is now done on-the-fly in API endpoints

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

        # Update origin and terminal stations from actual journey data
        if train_data.STOPS:
            first_stop = train_data.STOPS[0]
            last_stop = train_data.STOPS[-1]

            # CRITICAL FIX: Always update origin from actual first stop
            # This corrects discovery errors where train was found at intermediate station
            old_origin = journey.origin_station_code
            journey.origin_station_code = first_stop.STATION_2CHAR

            if old_origin != journey.origin_station_code:
                logger.info(
                    "corrected_journey_origin",
                    train_id=journey.train_id,
                    journey_id=journey.id,
                    old_origin=old_origin,
                    new_origin=journey.origin_station_code,
                )
                # Reset complete journey flag so future validations are more lenient
                journey.has_complete_journey = False

            # CRITICAL FIX: Always update scheduled departure from actual first stop
            # This corrects discovery departure time errors
            if first_stop.DEP_TIME:
                old_departure = journey.scheduled_departure
                journey.scheduled_departure = parse_njt_time(first_stop.DEP_TIME)

                if old_departure and old_departure != journey.scheduled_departure:
                    logger.info(
                        "corrected_journey_departure_time",
                        train_id=journey.train_id,
                        journey_id=journey.id,
                        old_departure=(
                            old_departure.isoformat() if old_departure else None
                        ),
                        new_departure=journey.scheduled_departure.isoformat(),
                    )
                    # Reset complete journey flag so future validations are more lenient
                    journey.has_complete_journey = False

            # Update terminal station (last stop)
            journey.terminal_station_code = last_stop.STATION_2CHAR

            # Always update scheduled arrival from actual last stop
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
        """Update journey stops with immutable scheduled times and intelligent actual time inference.

        Args:
            session: Database session
            journey: Journey record
            stops_data: List of stop data from API
        """
        # First, validate the API response for duplicate stations
        station_codes = [
            stop.STATION_2CHAR for stop in stops_data if stop.STATION_2CHAR
        ]
        duplicate_stations = {
            code for code in station_codes if station_codes.count(code) > 1
        }

        if duplicate_stations:
            logger.warning(
                "api_response_contains_duplicate_stations",
                train_id=journey.train_id,
                journey_id=journey.id,
                duplicates=list(duplicate_stations),
                total_stops=len(stops_data),
            )
            # Filter out duplicates, keeping only the first occurrence
            seen_stations = set()
            filtered_stops = []
            for stop_data in stops_data:
                if stop_data.STATION_2CHAR not in seen_stations:
                    seen_stations.add(stop_data.STATION_2CHAR)
                    filtered_stops.append(stop_data)
            stops_data = filtered_stops

        # First pass: Find the furthest departed stop for sequential inference
        max_departed_sequence = -1
        for sequence, stop_data in enumerate(stops_data):
            if stop_data.DEPARTED == "YES":
                max_departed_sequence = max(max_departed_sequence, sequence)

        # Second pass: Process each stop
        for sequence, stop_data in enumerate(stops_data):
            # Parse current API times (might be adjusted from original schedule)
            api_arrival_time = parse_njt_time(stop_data.TIME) if stop_data.TIME else None
            api_departure_time = parse_njt_time(stop_data.DEP_TIME) if stop_data.DEP_TIME else None
            
            # Fix swapped times if needed (NJT API sometimes has arrival > departure)
            if api_arrival_time and api_departure_time and api_arrival_time > api_departure_time:
                # Swap them - NJT API has them backwards for intermediate stops
                api_arrival_time, api_departure_time = api_departure_time, api_arrival_time
                logger.warning(
                    "swapped_njt_times",
                    train_id=journey.train_id,
                    station=stop_data.STATION_2CHAR,
                    api_time=stop_data.TIME,
                    api_dep_time=stop_data.DEP_TIME
                )
            
            # Find existing stop or create new
            stmt = select(JourneyStop).where(
                and_(
                    JourneyStop.journey_id == journey.id,
                    JourneyStop.station_code == stop_data.STATION_2CHAR,
                )
            )
            stop = await session.scalar(stmt)

            if not stop:
                # NEW STOP - Set scheduled times (immutable)
                stop = JourneyStop(
                    journey_id=journey.id,
                    station_code=stop_data.STATION_2CHAR,
                    station_name=stop_data.STATIONNAME
                    or get_station_name(stop_data.STATION_2CHAR or ""),
                    stop_sequence=sequence,
                    # Set scheduled times ONLY on creation
                    scheduled_arrival=api_arrival_time,
                    scheduled_departure=api_departure_time,
                )
                session.add(stop)
                logger.debug(
                    "created_stop_with_scheduled_times",
                    train_id=journey.train_id,
                    station=stop_data.STATION_2CHAR,
                    scheduled_arrival=api_arrival_time.isoformat() if api_arrival_time else None,
                    scheduled_departure=api_departure_time.isoformat() if api_departure_time else None
                )
            else:
                # EXISTING STOP - Never update scheduled times unless they're NULL
                if stop.scheduled_arrival is None and api_arrival_time:
                    stop.scheduled_arrival = api_arrival_time
                    logger.info("recovered_missing_scheduled_arrival", 
                               train_id=journey.train_id, 
                               station=stop_data.STATION_2CHAR)
                
                if stop.scheduled_departure is None and api_departure_time:
                    stop.scheduled_departure = api_departure_time
                    logger.info("recovered_missing_scheduled_departure",
                               train_id=journey.train_id,
                               station=stop_data.STATION_2CHAR)
                
                # Update sequence if more accurate
                current_seq = stop.stop_sequence or 0
                if current_seq == 0 and sequence > 0:
                    # Upgrade from discovery placeholder (0) to real sequence
                    logger.debug(
                        "upgrading_stop_sequence_from_placeholder",
                        train_id=journey.train_id,
                        station_code=stop.station_code,
                        old_sequence=current_seq,
                        new_sequence=sequence,
                    )
                    stop.stop_sequence = sequence
                elif sequence > current_seq:
                    # Update to higher sequence (more accurate position in journey)
                    logger.debug(
                        "updating_stop_sequence_to_higher_value",
                        train_id=journey.train_id,
                        station_code=stop.station_code,
                        old_sequence=current_seq,
                        new_sequence=sequence,
                    )
                    stop.stop_sequence = sequence

            # Update "updated" times (these CAN change - they might be estimates/actuals)
            stop.updated_arrival = api_arrival_time
            stop.updated_departure = api_departure_time
            
            # Three-tier actual time inference using LATEST API data
            # Tier 1: Explicit DEPARTED flag from API (most reliable)
            if stop_data.DEPARTED == "YES":
                stop.actual_arrival = api_arrival_time or stop.scheduled_arrival
                stop.actual_departure = api_departure_time or stop.scheduled_departure
                stop.has_departed_station = True
                stop.departure_source = "api_explicit"
                
            # Tier 2: Sequential inference (very reliable)
            elif sequence < max_departed_sequence:
                # If a later stop has departed, this one must have too
                stop.actual_arrival = api_arrival_time or stop.scheduled_arrival
                stop.actual_departure = api_departure_time or stop.scheduled_departure
                stop.has_departed_station = True
                stop.departure_source = "sequential_inference"
                
            # Tier 3: Time-based inference (moderately reliable)
            elif stop.scheduled_departure and stop.scheduled_departure < now_et() - timedelta(minutes=5):
                # Train should have departed by now (5-minute grace period)
                stop.actual_arrival = api_arrival_time or stop.scheduled_arrival
                stop.actual_departure = api_departure_time or stop.scheduled_departure
                stop.has_departed_station = True
                stop.departure_source = "time_inference"
                
            else:
                # Not yet departed
                stop.has_departed_station = False
                stop.departure_source = None
                # Clear any previously inferred actual times
                stop.actual_arrival = None
                stop.actual_departure = None

            # Update raw status information
            stop.raw_njt_departed_flag = stop_data.DEPARTED

            # Update track if available - but don't overwrite existing track from discovery
            if stop_data.TRACK:
                sanitized_track = sanitize_track(stop_data.TRACK)
                if sanitized_track:
                    stop.track = sanitized_track
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

        # Validate that we don't have duplicate sequences after processing
        await self._validate_stop_sequences(session, journey)

    async def _validate_stop_sequences(
        self, session: AsyncSession, journey: TrainJourney
    ) -> None:
        """Validate that no duplicate stop sequences exist for this journey.

        Args:
            session: Database session
            journey: Journey to validate
        """
        # Simple validation using in-memory journey.stops to avoid async mock issues
        if not journey.stops:
            return

        sequences = [
            stop.stop_sequence
            for stop in journey.stops
            if stop.stop_sequence is not None
        ]

        # Find duplicates
        duplicate_sequences = {seq for seq in sequences if sequences.count(seq) > 1}

        if duplicate_sequences:
            logger.error(
                "duplicate_stop_sequences_detected",
                train_id=journey.train_id,
                journey_id=journey.id,
                duplicate_sequences=list(duplicate_sequences),
                total_sequences=len(sequences),
            )
            # This shouldn't happen with our fix, but if it does, mark journey for review
            journey.api_error_count = (journey.api_error_count or 0) + 1
        else:
            logger.debug(
                "stop_sequence_validation_passed",
                train_id=journey.train_id,
                journey_id=journey.id,
                total_stops=len(sequences),
            )

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
            sanitized_track = sanitize_track(train_entry["TRACK"])
            if sanitized_track:
                stop.TRACK = sanitized_track
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
