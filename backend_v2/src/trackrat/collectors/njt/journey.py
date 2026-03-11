"""
Journey collection service for TrackRat V2.

Collects complete journey details using the getTrainStopList API.
"""

from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.base import BaseJourneyCollector
from trackrat.collectors.njt.client import (
    NJTransitClient,
    NJTransitNullDataError,
    TrainNotFoundError,
)
from trackrat.config.stations import get_station_name
from trackrat.db.engine import get_session
from trackrat.models.api import NJTransitStopData, NJTransitTrainData
from trackrat.models.database import JourneySnapshot, JourneyStop, TrainJourney
from trackrat.services.transit_analyzer import TransitAnalyzer
from trackrat.utils.sanitize import sanitize_track
from trackrat.utils.time import (
    DATETIME_MAX_ET,
    DATETIME_MIN_ET,
    ET,
    now_et,
    parse_njt_time,
)

logger = get_logger(__name__)


def normalize_njt_stop_times(
    time_field: datetime | None,
    dep_time_field: datetime | None,
    is_origin_station: bool,
    has_departed: bool,
) -> dict[str, datetime | None]:
    """
    Normalize NJT API TIME and DEP_TIME fields based on stop type.

    NJT API field semantics differ between origin and intermediate stops:

    At ORIGIN station:
    - TIME = Original scheduled departure time (immutable)
    - DEP_TIME = Actual/updated departure time (changes with delays)

    At INTERMEDIATE stops:
    - TIME = Actual/estimated arrival time (live updating)
    - DEP_TIME = Original scheduled departure time (immutable)

    This semantic inversion was discovered through direct NJT API testing:
    - Delayed trains from NY Penn show TIME < DEP_TIME at origin
    - On-time trains show TIME == DEP_TIME at origin
    - Intermediate stops always show TIME > DEP_TIME when delayed

    Args:
        time_field: Parsed TIME field from NJT API
        dep_time_field: Parsed DEP_TIME field from NJT API
        is_origin_station: Whether this stop is the journey's origin
        has_departed: Whether the train has departed this stop (DEPARTED="YES")

    Returns:
        Dict with normalized times:
        - scheduled_arrival: None (caller uses SCHED_ARR_DATE for immutable schedule)
        - scheduled_departure: Original scheduled departure time
        - actual_arrival: Live arrival estimate at intermediate stops (None at origin)
        - actual_departure: Actual departure time (only set when departed)
    """
    if is_origin_station:
        # At origin: TIME = original schedule, DEP_TIME = actual departure
        return {
            "scheduled_arrival": None,  # No arrival at origin
            "scheduled_departure": time_field,  # TIME = original schedule at origin
            "actual_arrival": None,  # No arrival at origin
            "actual_departure": dep_time_field if has_departed else None,
        }
    else:
        # At intermediate: TIME = actual/estimate, DEP_TIME = original schedule
        # Don't use TIME as scheduled_arrival — it's a live estimate that drifts
        # with delays, causing inversions with scheduled_departure (DEP_TIME).
        # The caller uses SCHED_ARR_DATE for immutable scheduled arrival instead.
        return {
            "scheduled_arrival": None,
            "scheduled_departure": dep_time_field,
            "actual_arrival": time_field,
            "actual_departure": time_field if has_departed else None,
        }


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
                TrainJourney.journey_date == now_et().date(),
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

        # Mark SCHEDULED trains that were never observed as likely cancelled
        await self._reconcile_unobserved_trains(session)

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

        result = cast(CursorResult[tuple[()]], await session.execute(stmt))

        if result.rowcount and result.rowcount > 0:
            logger.info(
                "expired_old_journeys",
                count=result.rowcount,
                cutoff_date=cutoff_date.isoformat(),
            )

    async def _reconcile_unobserved_trains(self, session: AsyncSession) -> None:
        """Mark SCHEDULED trains as cancelled if they were never observed.

        If a train from the NJT schedule was never upgraded to OBSERVED by
        discovery and its origin departure time is more than 50 minutes ago,
        it almost certainly did not run. Discovery polls 7+ stations every
        30 minutes, so 50 minutes gives at least one full discovery cycle
        with margin.

        This fills a gap where NJT silently cancels trains by removing them
        from the real-time feed rather than explicitly flagging stops as
        "Cancelled".
        """
        now = now_et()
        cutoff_time = now - timedelta(minutes=50)

        stmt = (
            update(TrainJourney)
            .where(
                and_(
                    TrainJourney.data_source == "NJT",
                    TrainJourney.journey_date == now.date(),
                    TrainJourney.observation_type == "SCHEDULED",
                    TrainJourney.is_cancelled.is_(False),
                    TrainJourney.is_expired.is_(False),
                    TrainJourney.is_completed.is_(False),
                    TrainJourney.scheduled_departure < cutoff_time,
                )
            )
            .values(
                is_cancelled=True,
                cancellation_reason="Not observed in real-time feed",
            )
        )

        result = cast(CursorResult[tuple[()]], await session.execute(stmt))

        if result.rowcount and result.rowcount > 0:
            logger.info(
                "reconciled_unobserved_trains",
                count=result.rowcount,
                cutoff_time=cutoff_time.isoformat(),
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

    async def _is_same_journey(
        self,
        session: AsyncSession,
        stored_journey: TrainJourney,
        api_train_data: NJTransitTrainData,
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

                    # Get stored departure, but check if journey metadata is stale
                    # If origin_station_code doesn't match first stop in our stops table,
                    # the journey was discovered at an intermediate station and metadata
                    # was never properly corrected. Use stops table as source of truth.
                    stored_departure = stored_journey.scheduled_departure

                    if (
                        stored_journey.origin_station_code
                        and stored_journey.origin_station_code
                        != first_stop.STATION_2CHAR
                    ):
                        # Query stops explicitly to avoid lazy-load greenlet error
                        stops_stmt = (
                            select(JourneyStop)
                            .where(JourneyStop.journey_id == stored_journey.id)
                            .order_by(JourneyStop.stop_sequence.asc().nulls_last())
                        )
                        stops_result = await session.execute(stops_stmt)
                        db_stops_sorted = list(stops_result.scalars().all())

                        # Check if our stored stops have a different first station
                        if db_stops_sorted:
                            first_db_stop = db_stops_sorted[0]
                            if (
                                first_db_stop.station_code
                                != stored_journey.origin_station_code
                                and first_db_stop.scheduled_departure
                            ):
                                # Stops table has correct origin, journey record is stale
                                # Use the first stop's departure for comparison
                                stored_departure = first_db_stop.scheduled_departure
                                logger.info(
                                    "using_stops_table_departure_for_comparison",
                                    journey_id=stored_journey.id,
                                    train_id=stored_journey.train_id,
                                    stale_origin=stored_journey.origin_station_code,
                                    correct_origin=first_db_stop.station_code,
                                    stale_departure=(
                                        stored_journey.scheduled_departure.isoformat()
                                        if stored_journey.scheduled_departure
                                        else None
                                    ),
                                    corrected_departure=stored_departure.isoformat(),
                                )

                    if stored_departure is not None:
                        # Ensure stored departure is timezone-aware for comparison
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
                    # time_diff > 600 implies stored_departure is not None (otherwise time_diff would be 0)
                    assert stored_departure is not None

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
        except NJTransitNullDataError:
            # NJT API returned a response with all key fields null — transient
            # API issue. The train likely still appears on departure boards.
            # Do NOT increment api_error_count; keep last known data.
            logger.info(
                "train_null_data_skipped",
                train_id=journey.train_id,
                journey_id=journey.id,
                api_error_count=journey.api_error_count,
            )
            return
        except TrainNotFoundError:
            # Train is genuinely not available (empty/None response) —
            # increment error count toward expiry threshold.
            journey.api_error_count = (journey.api_error_count or 0) + 1
            journey.last_updated_at = now_et()
            journey.update_count = (journey.update_count or 0) + 1

            # After 3 failed attempts, attempt last-chance completion then expire
            if journey.api_error_count >= 3:
                # Train disappeared from API — likely completed its run.
                # Check if penultimate stop departed, which means the train
                # reached its terminal. We can't set terminal actual_arrival
                # (no API data), but marking the journey completed is still
                # valuable for analytics that only need completion status.
                if not journey.is_completed:
                    await self._attempt_completion_on_expiry(session, journey)

                if not journey.is_completed:
                    journey.is_expired = True
                logger.warning(
                    (
                        "train_marked_expired"
                        if journey.is_expired
                        else "train_completed_on_expiry"
                    ),
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
        if not await self._is_same_journey(session, journey, train_data):
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

        # Analyze any newly completed segments (for real-time predictions)
        # This runs immediately without waiting for journey completion
        transit_analyzer = TransitAnalyzer()
        segments_created = await transit_analyzer.analyze_new_segments(session, journey)

        if segments_created > 0:
            logger.info(
                "realtime_segments_analyzed",
                train_id=journey.train_id,
                journey_id=journey.id,
                segments_created=segments_created,
            )

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
                if "LATE" in (stop.STOP_STATUS or ""):
                    # Extract delay if in format "X MINUTES LATE" or "X MINS LATE"
                    try:
                        parts = stop.STOP_STATUS.split()
                        if "MINUTES" in parts:
                            idx = parts.index("MINUTES")
                            if idx > 0:
                                delay_minutes = int(parts[idx - 1])
                        elif "MINS" in parts:
                            idx = parts.index("MINS")
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

        # Sort stops by time to ensure geographic order for sequential inference.
        # The NJT API may return stops in non-geographic order when times are corrupted
        # (e.g., scheduled_departure < scheduled_arrival). This sort ensures that
        # enumerate() indices match the actual journey order, which is critical for
        # the Tier 2 sequential inference logic below.
        # Uses same min(arrival, departure) logic as _resequence_stops().
        def get_stop_sort_time(stop_data: NJTransitStopData) -> datetime:
            """Get sort time for a stop, using min(arrival, departure) for robustness."""
            arr_time = parse_njt_time(stop_data.TIME) if stop_data.TIME else None
            dep_time = (
                parse_njt_time(stop_data.DEP_TIME) if stop_data.DEP_TIME else None
            )

            if arr_time and dep_time:
                return min(arr_time, dep_time)
            elif arr_time:
                return arr_time
            elif dep_time:
                return dep_time
            else:
                # No times available - place at end (won't affect departure inference)
                # Use timezone-aware constant for safe comparison with ET-localized times
                return DATETIME_MAX_ET

        stops_data = sorted(stops_data, key=get_stop_sort_time)

        # Load existing departed stops from DB so Tier 2 inference accounts for
        # stops that were confirmed departed in previous collection cycles —
        # even if the NJT API flips DEPARTED back to NO (known inconsistency).
        db_departed_codes: set[str] = set()
        departed_stmt = select(JourneyStop.station_code).where(
            and_(
                JourneyStop.journey_id == journey.id,
                JourneyStop.has_departed_station.is_(True),
            )
        )
        db_departed_result = await session.execute(departed_stmt)
        db_departed_codes = {
            c for c in db_departed_result.scalars().all() if c is not None
        }

        # First pass: Find the furthest departed stop for sequential inference.
        # Combines current API flags with DB state to handle NJT's inconsistent
        # DEPARTED flag (can flip between YES/NO across collection cycles).
        max_departed_sequence = -1
        for sequence, stop_data in enumerate(stops_data):
            if (
                stop_data.DEPARTED == "YES"
                or stop_data.STATION_2CHAR in db_departed_codes
            ):
                max_departed_sequence = max(max_departed_sequence, sequence)

        # Second pass: Process each stop
        for sequence, stop_data in enumerate(stops_data):
            # Parse raw time fields from NJT API
            time_field = parse_njt_time(stop_data.TIME) if stop_data.TIME else None
            dep_time_field = (
                parse_njt_time(stop_data.DEP_TIME) if stop_data.DEP_TIME else None
            )

            # Parse immutable schedule fields if available.
            # SCHED_ARR_DATE / SCHED_DEP_DATE are the true original schedule
            # times, unlike TIME/DEP_TIME which have inverted semantics and
            # live-updating behavior.
            sched_arr = (
                parse_njt_time(stop_data.SCHED_ARR_DATE)
                if stop_data.SCHED_ARR_DATE
                else None
            )
            sched_dep = (
                parse_njt_time(stop_data.SCHED_DEP_DATE)
                if stop_data.SCHED_DEP_DATE
                else None
            )

            # Determine if this is the origin station
            # Use journey's origin_station_code for reliable detection
            is_origin = stop_data.STATION_2CHAR == journey.origin_station_code
            has_departed = stop_data.DEPARTED == "YES"

            # Normalize times based on stop type (origin vs intermediate)
            # NJT API has inverted semantics at origin stations
            normalized = normalize_njt_stop_times(
                time_field, dep_time_field, is_origin, has_departed
            )

            # For scheduled times, prefer the immutable SCHED_*_DATE fields
            # over the normalized values derived from TIME/DEP_TIME. The
            # normalized values are live estimates at intermediate stops,
            # which drift as NJT revises predictions.
            best_scheduled_arrival = sched_arr or normalized["scheduled_arrival"]
            best_scheduled_departure = sched_dep or normalized["scheduled_departure"]

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
                # Use savepoint to handle race with discovery creating the same stop
                try:
                    async with session.begin_nested():
                        stop = JourneyStop(
                            journey_id=journey.id,
                            station_code=stop_data.STATION_2CHAR,
                            station_name=stop_data.STATIONNAME
                            or get_station_name(stop_data.STATION_2CHAR or ""),
                            stop_sequence=sequence,
                            scheduled_arrival=best_scheduled_arrival,
                            scheduled_departure=best_scheduled_departure,
                        )
                        session.add(stop)
                        await session.flush()
                    logger.debug(
                        "created_stop_with_scheduled_times",
                        train_id=journey.train_id,
                        station=stop_data.STATION_2CHAR,
                        is_origin=is_origin,
                        scheduled_arrival=(
                            normalized["scheduled_arrival"].isoformat()
                            if normalized["scheduled_arrival"]
                            else None
                        ),
                        scheduled_departure=(
                            normalized["scheduled_departure"].isoformat()
                            if normalized["scheduled_departure"]
                            else None
                        ),
                    )
                except IntegrityError:
                    # Race condition: discovery created this stop concurrently
                    stop = await session.scalar(stmt)
                    if not stop:
                        raise  # Should not happen — re-raise if stop truly missing
                    logger.info(
                        "stop_created_by_concurrent_process",
                        train_id=journey.train_id,
                        station=stop_data.STATION_2CHAR,
                    )
            else:
                # EXISTING STOP - Never update scheduled times unless they're NULL
                if stop.scheduled_arrival is None and best_scheduled_arrival:
                    stop.scheduled_arrival = best_scheduled_arrival
                    logger.info(
                        "recovered_missing_scheduled_arrival",
                        train_id=journey.train_id,
                        station=stop_data.STATION_2CHAR,
                        is_origin=is_origin,
                    )

                if stop.scheduled_departure is None and best_scheduled_departure:
                    stop.scheduled_departure = best_scheduled_departure
                    logger.info(
                        "recovered_missing_scheduled_departure",
                        train_id=journey.train_id,
                        station=stop_data.STATION_2CHAR,
                        is_origin=is_origin,
                    )

                # Update sequence to match API order (fixes schedule-generated stops)
                if stop.stop_sequence != sequence:
                    logger.info(
                        "correcting_stop_sequence",
                        train_id=journey.train_id,
                        station=stop_data.STATION_2CHAR,
                        old_sequence=stop.stop_sequence,
                        new_sequence=sequence,
                    )
                stop.stop_sequence = sequence

            # Update "updated" times for backward compatibility (deprecated fields)
            # These use raw API fields for legacy compatibility
            stop.updated_arrival = time_field
            stop.updated_departure = dep_time_field

            # Three-tier actual DEPARTURE inference
            # Cancelled stops never physically departed — skip all inference
            is_stop_cancelled = (stop_data.STOP_STATUS or "") == "CANCELLED"

            # Tier 1: Explicit DEPARTED flag from API (most reliable)
            if is_stop_cancelled:
                if not stop.has_departed_station:
                    stop.has_departed_station = False
                    stop.departure_source = None
            elif stop_data.DEPARTED == "YES":
                # Use normalized actual_departure which handles origin vs intermediate
                # At origin: DEP_TIME (actual departure), at intermediate: TIME (actual)
                stop.actual_departure = (
                    normalized["actual_departure"] or stop.scheduled_departure
                )
                stop.has_departed_station = True
                stop.departure_source = "api_explicit"

            # Tier 2: Sequential inference (very reliable)
            elif sequence < max_departed_sequence:
                # If a later stop has departed, this one must have too.
                # Only set actual_departure if not already recorded, to avoid
                # overwriting a value captured when the train was at this stop
                # with a stale NJT timestamp from a later collection cycle.
                if not stop.actual_departure:
                    if is_origin:
                        stop.actual_departure = (
                            dep_time_field or stop.scheduled_departure
                        )
                    else:
                        stop.actual_departure = time_field or stop.scheduled_departure
                stop.has_departed_station = True
                stop.departure_source = stop.departure_source or "sequential_inference"

            # Tier 3: Time-based inference (moderately reliable)
            elif (
                stop.scheduled_departure
                and stop.scheduled_departure < now_et() - timedelta(minutes=5)
            ):
                # Train should have departed by now (5-minute grace period).
                # Mark as departed for position tracking, but do NOT set
                # actual_departure — we have no real data for the actual time,
                # and using the schedule creates false "on time" status.
                stop.has_departed_station = True
                stop.departure_source = stop.departure_source or "time_inference"

            else:
                # Not yet departed — but never revert a stop that was
                # previously marked as departed (API data can be inconsistent)
                if not stop.has_departed_station:
                    stop.has_departed_station = False
                    stop.departure_source = None

            # Update actual_arrival — only for stops the train has reached.
            # After the three-tier departure inference above, has_departed_station
            # reflects whether the train has passed this stop. We only write
            # actual_arrival for confirmed stops to prevent future stops from
            # showing arrival times the train hasn't achieved yet.
            # Once set, actual_arrival is frozen to preserve the value captured
            # when the train was at/near the station.
            if stop.has_departed_station:
                if (
                    stop.actual_arrival is None
                    and stop.departure_source != "time_inference"
                ):
                    stop.actual_arrival = normalized["actual_arrival"]
                    stop.arrival_source = "api_observed"
            else:
                # Clear any stale actual_arrival from legacy code that wrote
                # it unconditionally. Non-departed stops shouldn't show arrival.
                if stop.actual_arrival is not None:
                    logger.info(
                        "clearing_stale_actual_arrival",
                        train_id=journey.train_id,
                        station=stop_data.STATION_2CHAR,
                        stale_value=stop.actual_arrival.isoformat(),
                    )
                    stop.actual_arrival = None

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

        # Flush changes so newly created/updated stops are visible in the database
        await session.flush()

        # Delete phantom stops that don't appear in API response
        # This removes schedule-generated placeholder stops that don't match reality
        api_station_codes = {stop_data.STATION_2CHAR for stop_data in stops_data}
        stmt = select(JourneyStop).where(JourneyStop.journey_id == journey.id)
        result = await session.execute(stmt)
        all_stops = list(result.scalars().all())

        for stop in all_stops:
            if stop.station_code not in api_station_codes:
                logger.warning(
                    "deleting_phantom_stop",
                    journey_id=journey.id,
                    train_id=journey.train_id,
                    station_code=stop.station_code,
                    stop_sequence=stop.stop_sequence,
                    had_scheduled_times=bool(
                        stop.scheduled_arrival or stop.scheduled_departure
                    ),
                    had_actual_times=bool(stop.actual_departure or stop.actual_arrival),
                )
                await session.delete(stop)

        # Re-sequence all stops for this journey to ensure consistency
        await self._resequence_stops(session, journey)

        # Critical: Flush changes to database to ensure resequencing is persisted
        await session.flush()

        # Validate that we don't have duplicate sequences after processing
        await self._validate_stop_sequences(session, journey)

    async def _resequence_stops(
        self, session: AsyncSession, journey: TrainJourney
    ) -> None:
        """Resequence all stops for a journey based on scheduled times.

        Uses min(scheduled_arrival, scheduled_departure) when both are available,
        which handles corrupted NJT data where departure < arrival (physically
        impossible). Falls back to whichever time is available for origin stations
        (departure only) or terminal stations (arrival only).
        """
        logger.debug("resequencing_stops", journey_id=journey.id)

        # Get all stops for the journey
        stmt = select(JourneyStop).where(JourneyStop.journey_id == journey.id)
        result = await session.execute(stmt)
        stops = list(result.scalars().all())

        # Track stops with missing times for logging
        stops_without_times: list[str] = []
        # Track stops with corrupted times (departure before arrival - physically impossible)
        stops_with_corrupted_times: list[dict[str, str]] = []

        # Sort stops by scheduled times, but preserve sequence for stops without times
        # This prevents stops with null times from being incorrectly placed at position 0
        def get_sort_key(
            stop: JourneyStop,
        ) -> (
            tuple[int, datetime] | tuple[int, datetime, int] | tuple[int, datetime, str]
        ):
            # If stop has a valid time, sort by that time
            if stop.scheduled_arrival or stop.scheduled_departure:
                # Use the EARLIEST available time for sorting.
                # This handles corrupted NJT data where scheduled_departure < scheduled_arrival
                # (physically impossible - train can't depart before arriving).
                # Using min() ensures we pick the correct time for route ordering.
                if stop.scheduled_arrival and stop.scheduled_departure:
                    if stop.scheduled_departure < stop.scheduled_arrival:
                        # Track this anomaly for logging
                        stops_with_corrupted_times.append(
                            {
                                "station": stop.station_code or "unknown",
                                "scheduled_arrival": stop.scheduled_arrival.isoformat(),
                                "scheduled_departure": stop.scheduled_departure.isoformat(),
                            }
                        )
                    time = min(stop.scheduled_arrival, stop.scheduled_departure)
                elif stop.scheduled_arrival is not None:
                    time = stop.scheduled_arrival
                else:
                    # Only scheduled_departure available (origin station case)
                    # Also consider updated_departure (raw DEP_TIME from API) to handle
                    # corrupted origin data where scheduled_departure (from TIME) is wrong.
                    # This matches the min() logic in update_journey_stops().
                    assert (
                        stop.scheduled_departure is not None
                    )  # Guaranteed by outer if
                    if stop.updated_departure is not None:
                        time = min(stop.scheduled_departure, stop.updated_departure)
                    else:
                        time = stop.scheduled_departure
                return (0, time)

            # Stop has no times - track it for logging
            stops_without_times.append(stop.station_code or "unknown")

            # Use timezone-aware max to place after all timed stops,
            # but preserve relative order using existing sequence
            if stop.stop_sequence is not None:
                # Place after timed stops but maintain relative order
                # Use stop_sequence directly as secondary sort key
                return (1, DATETIME_MAX_ET, stop.stop_sequence)
            else:
                # Last resort: use station code for stable ordering
                assert (
                    stop.station_code is not None
                )  # station_code is not nullable in database
                return (2, DATETIME_MAX_ET, stop.station_code)

        stops.sort(key=get_sort_key)

        # Log if we found stops without times
        if stops_without_times:
            logger.warning(
                "stops_missing_scheduled_times",
                journey_id=journey.id,
                train_id=journey.train_id,
                stations_without_times=stops_without_times,
                count=len(stops_without_times),
            )

        # Log if we found stops with corrupted times (departure before arrival)
        if stops_with_corrupted_times:
            logger.warning(
                "stops_with_corrupted_times",
                journey_id=journey.id,
                train_id=journey.train_id,
                corrupted_stops=stops_with_corrupted_times,
                count=len(stops_with_corrupted_times),
                message="NJT API returned stops where scheduled_departure < scheduled_arrival",
            )

        # Update the stop_sequence for each stop
        # CRITICAL FIX (Issue #256): Always assign sequences to ensure they persist
        # This fixes duplicate sequence bugs where stops from schedule generation
        # conflict with journey collection (e.g., both Trenton and Hamilton with seq=0)
        changes_made = False
        for i, stop in enumerate(stops):
            if stop.stop_sequence != i:
                logger.info(
                    "updating_stop_sequence",
                    journey_id=journey.id,
                    station_code=stop.station_code,
                    old_sequence=stop.stop_sequence,
                    new_sequence=i,
                    scheduled_arrival=(
                        stop.scheduled_arrival.isoformat()
                        if stop.scheduled_arrival
                        else None
                    ),
                    scheduled_departure=(
                        stop.scheduled_departure.isoformat()
                        if stop.scheduled_departure
                        else None
                    ),
                )
                changes_made = True

            # Always assign the sequence (SQLAlchemy automatically tracks changes to scalar fields)
            stop.stop_sequence = i

        if changes_made:
            logger.info(
                "stop_sequences_updated",
                journey_id=journey.id,
                train_id=journey.train_id,
                total_stops=len(stops),
            )

        # Phase 2: Verify sequences were actually assigned in the session
        # This helps detect if SQLAlchemy isn't tracking changes properly
        sequence_mismatches = []
        for i, stop in enumerate(stops):
            if stop.stop_sequence != i:
                sequence_mismatches.append(
                    {
                        "station": stop.station_code,
                        "expected": i,
                        "actual": stop.stop_sequence,
                    }
                )

        if sequence_mismatches:
            logger.error(
                "sequence_assignment_verification_failed",
                journey_id=journey.id,
                train_id=journey.train_id,
                mismatches=sequence_mismatches,
                message="Sequences not properly assigned in session - this indicates a deeper SQLAlchemy issue",
            )

        # Validation: Check for anomalies in the final sequence
        # The first stop (sequence 0) should be the origin station
        if stops and len(stops) > 1:
            first_stop = stops[0]
            # Check if any non-first stop has sequence 0 (shouldn't happen after our fix)
            anomalies = [stop for stop in stops[1:] if stop.stop_sequence == 0]
            if anomalies:
                logger.error(
                    "invalid_stop_sequences_after_resequencing",
                    journey_id=journey.id,
                    train_id=journey.train_id,
                    first_stop_station=first_stop.station_code,
                    anomalous_stations=[s.station_code for s in anomalies],
                )

            # Also check if the origin station is not at position 0
            if (
                journey.origin_station_code
                and first_stop.station_code != journey.origin_station_code
            ):
                logger.warning(
                    "origin_station_not_first",
                    journey_id=journey.id,
                    train_id=journey.train_id,
                    expected_origin=journey.origin_station_code,
                    actual_first=first_stop.station_code,
                    first_stop_sequence=first_stop.stop_sequence,
                )

    async def _validate_stop_sequences(
        self, session: AsyncSession, journey: TrainJourney
    ) -> None:
        """Validate that no duplicate stop sequences exist for this journey.
        If duplicates are found, automatically fix them.

        Args:
            session: Database session
            journey: Journey to validate
        """
        # Query stops directly to avoid lazy loading issues
        stops_stmt = select(JourneyStop.stop_sequence, JourneyStop.station_code).where(
            JourneyStop.journey_id == journey.id
        )
        result = await session.execute(stops_stmt)
        stop_data = [(row[0], row[1]) for row in result.fetchall()]
        sequences = [seq for seq, _ in stop_data if seq is not None]

        # Find duplicates
        duplicate_sequences = {seq for seq in sequences if sequences.count(seq) > 1}

        if duplicate_sequences:
            logger.warning(
                "duplicate_stop_sequences_detected_attempting_fix",
                train_id=journey.train_id,
                journey_id=journey.id,
                duplicate_sequences=list(duplicate_sequences),
                total_sequences=len(sequences),
                stop_details=stop_data,
            )

            # Self-healing: Force re-sequence based on scheduled times
            logger.info(
                "forcing_stop_resequence_due_to_duplicates",
                train_id=journey.train_id,
                journey_id=journey.id,
            )

            # Get all stops with their scheduled arrival times
            full_stops_stmt = select(JourneyStop).where(
                JourneyStop.journey_id == journey.id
            )
            full_result = await session.execute(full_stops_stmt)
            stops = list(full_result.scalars().all())

            # Sort by scheduled arrival time, using scheduled departure for origin station
            # Use timezone-aware constant for safe comparison with DB times
            stops.sort(
                key=lambda s: s.scheduled_arrival
                or s.scheduled_departure
                or DATETIME_MIN_ET
            )

            # Force update all sequences
            for i, stop in enumerate(stops):
                stop.stop_sequence = i
                logger.info(
                    "force_updated_stop_sequence",
                    journey_id=journey.id,
                    station_code=stop.station_code,
                    new_sequence=i,
                )

            # Force flush to database
            await session.flush()

            # Verify fix worked
            verify_stmt = select(JourneyStop.stop_sequence).where(
                JourneyStop.journey_id == journey.id
            )
            verify_result = await session.execute(verify_stmt)
            verify_sequences = [
                row[0] for row in verify_result.fetchall() if row[0] is not None
            ]
            verify_duplicates = {
                seq for seq in verify_sequences if verify_sequences.count(seq) > 1
            }

            if verify_duplicates:
                logger.error(
                    "duplicate_sequences_persist_after_fix",
                    train_id=journey.train_id,
                    journey_id=journey.id,
                    duplicate_sequences=list(verify_duplicates),
                )
                # Mark journey for manual review
                journey.api_error_count = (journey.api_error_count or 0) + 1
            else:
                logger.info(
                    "duplicate_sequences_fixed_successfully",
                    train_id=journey.train_id,
                    journey_id=journey.id,
                )
        else:
            logger.debug(
                "stop_sequence_validation_passed",
                train_id=journey.train_id,
                journey_id=journey.id,
                total_stops=len(sequences),
            )

    async def _attempt_completion_on_expiry(
        self,
        session: AsyncSession,
        journey: TrainJourney,
    ) -> None:
        """Last-chance completion when a train disappears from the NJT API.

        If the penultimate stop has departed, the train reached its terminal.
        We can't set terminal actual_arrival (no API data available), but we
        mark the journey completed and use scheduled_arrival as a fallback
        so route history stats aren't N/A.
        """
        # Get last two stops by sequence
        last_two_stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence.desc())
            .limit(2)
        )
        result = await session.execute(last_two_stmt)
        last_two = result.scalars().all()

        if len(last_two) < 2:
            return

        terminal_stop = last_two[0]
        penultimate_stop = last_two[1]

        if not penultimate_stop.has_departed_station:
            return

        # Penultimate stop departed — train reached its terminal
        journey.is_completed = True

        # Use scheduled_arrival as fallback for the terminal stop if we have it
        if terminal_stop.actual_arrival is None and terminal_stop.scheduled_arrival:
            terminal_stop.actual_arrival = terminal_stop.scheduled_arrival
            terminal_stop.arrival_source = "scheduled_fallback"
            journey.actual_arrival = terminal_stop.scheduled_arrival

        logger.info(
            "journey_completed_on_expiry",
            train_id=journey.train_id,
            journey_id=journey.id,
            terminal_arrival_source=terminal_stop.arrival_source,
        )

        # Run full analysis on completed journey
        transit_analyzer = TransitAnalyzer()
        await transit_analyzer.analyze_journey(session, journey)

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

        # Check if journey is completed by examining stop departure status.
        # Uses the inferred departure status from the three-tier logic:
        # 1. api_explicit: DEPARTED="YES" from API
        # 2. sequential_inference: earlier stops have departed
        # 3. time_inference: >5 minutes past scheduled time
        #
        # Terminal stops (e.g., NY Penn) never get DEPARTED="YES" from the
        # NJT API, and sequential_inference can't fire (nothing after them).
        # So we also check if the penultimate stop has departed — if it has,
        # the train has necessarily reached the terminal.

        # Get the last stop from the database (by max stop_sequence, not len)
        last_stop_stmt = (
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence.desc())
            .limit(1)
        )
        result = await session.execute(last_stop_stmt)
        last_stop_db = result.scalar_one_or_none()

        if not last_stop_db:
            return

        # Terminal stop departed directly (rare for NJT terminals, but possible)
        terminal_reached = last_stop_db.has_departed_station

        # If not, check if the penultimate stop has departed.
        # Use ORDER BY desc with offset to handle non-contiguous sequences
        # (e.g., after phantom stop deletion: 0, 1, 3).
        if (
            not terminal_reached
            and last_stop_db.stop_sequence is not None
            and last_stop_db.stop_sequence > 0
        ):
            penultimate_stmt = (
                select(JourneyStop)
                .where(
                    and_(
                        JourneyStop.journey_id == journey.id,
                        JourneyStop.stop_sequence < last_stop_db.stop_sequence,
                    )
                )
                .order_by(JourneyStop.stop_sequence.desc())
                .limit(1)
            )
            result = await session.execute(penultimate_stmt)
            penultimate_stop = result.scalar_one_or_none()
            if penultimate_stop and penultimate_stop.has_departed_station:
                terminal_reached = True

        if terminal_reached:
            journey.is_completed = True

            # Set actual arrival from the last stop's data
            last_stop_api = stops_data[-1]
            if last_stop_api.TIME:
                arrival_time = parse_njt_time(last_stop_api.TIME)
                journey.actual_arrival = arrival_time

                # Also set actual_arrival on the terminal stop itself.
                # Terminal stops never get DEPARTED="YES" from the NJT API,
                # so their departure_source is always "time_inference", which
                # prevents the normal actual_arrival logic from writing it.
                # Setting it here ensures route history stats can compute
                # on-time percentage at terminal destinations.
                if last_stop_db.actual_arrival is None:
                    last_stop_db.actual_arrival = arrival_time
                    last_stop_db.arrival_source = "api_observed"

            logger.info(
                "journey_completed",
                train_id=journey.train_id,
                arrival_time=(
                    journey.actual_arrival.isoformat()
                    if journey.actual_arrival
                    else "unknown"
                ),
                departure_source=last_stop_db.departure_source,  # Log how we determined completion
            )

            # Run full analysis on completed journey (dwell times, progress, etc.)
            transit_analyzer = TransitAnalyzer()
            await transit_analyzer.analyze_journey(session, journey)
            logger.info(
                "completed_journey_analyzed",
                train_id=journey.train_id,
                journey_id=journey.id,
            )

        # Check for cancellation (all stops cancelled)
        cancelled_stops = sum(
            1 for stop in stops_data if (stop.STOP_STATUS or "") == "CANCELLED"
        )

        if cancelled_stops == len(stops_data):
            journey.is_cancelled = True
            journey.cancellation_reason = "All stops cancelled by NJT"
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
            departure_board = schedule_response.get("ITEMS") or []

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
        if all((stop.STOP_STATUS or "") == "CANCELLED" for stop in stops_data):
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
            stmt = select(TrainJourney).where(
                and_(
                    TrainJourney.train_id == train_id,
                    TrainJourney.data_source == "NJT",
                )
            )

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
