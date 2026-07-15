"""
Amtrak journey collection for TrackRat V2.

Collects complete journey details for Amtrak trains.
"""

import re
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.amtrak.client import AmtrakClient
from trackrat.collectors.base import BaseJourneyCollector
from trackrat.config.stations import AMTRAK_TO_INTERNAL_STATION_MAP, get_station_name
from trackrat.db.engine import get_session, with_db_retry
from trackrat.models.api import AmtrakTrainData
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.transit_analyzer import TransitAnalyzer
from trackrat.utils.locks import with_train_lock
from trackrat.utils.time import normalize_to_et, now_et

logger = get_logger(__name__)


class AmtrakJourneyCollector(BaseJourneyCollector):
    """Collects detailed journey information for Amtrak trains."""

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
            existing_track = getattr(existing_stop, "track", None)
            for field, value in stop_data.items():
                # Preserve existing track when API returns None
                if field == "track" and value is None and existing_track:
                    logger.debug(
                        "preserving_existing_track",
                        journey_id=journey_id,
                        station_code=station_code,
                        track=existing_track,
                    )
                    continue
                # Log track changes for diagnostics
                if field == "track" and value != existing_track:
                    logger.info(
                        "track_changed",
                        journey_id=journey_id,
                        station_code=station_code,
                        old_track=existing_track,
                        new_track=value,
                    )
                    if value and not getattr(existing_stop, "track_assigned_at", None):
                        existing_stop.track_assigned_at = now_et()
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
            api_station_codes: set[str] = set()
            time_corrections = 0

            for amtrak_stop in train_data.stations:
                internal_code = AMTRAK_TO_INTERNAL_STATION_MAP.get(amtrak_stop.code)
                if not internal_code:
                    continue  # Skip non-tracked stations

                # Update terminal station
                last_tracked_code = internal_code
                api_station_codes.add(internal_code)

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

                # Clamp actual times to scheduled if earlier (timezone normalization artifacts)
                if actual_dep and sched_dep and actual_dep < sched_dep:
                    actual_dep = sched_dep
                    time_corrections += 1

                if actual_arr and sched_arr and actual_arr < sched_arr:
                    actual_arr = sched_arr
                    time_corrections += 1

                # Prepare stop data for upsert
                # Apply time validation to prevent future trains being marked as departed
                has_departed = amtrak_stop.status == "Departed" and (
                    not sched_dep or sched_dep <= now_et()
                )

                stop_data = {
                    "journey_date": journey.journey_date,
                    "station_name": get_station_name(internal_code),
                    "stop_sequence": stop_sequence,
                    "scheduled_arrival": sched_arr,
                    "scheduled_departure": sched_dep,
                    "updated_arrival": self._compute_estimated_time(
                        sched_arr, amtrak_stop.arrCmnt
                    ),
                    "updated_departure": self._compute_estimated_time(
                        sched_dep, amtrak_stop.depCmnt
                    ),
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

            if time_corrections > 0:
                logger.info(
                    "amtrak_stop_times_corrected",
                    train_id=train_id,
                    corrections=time_corrections,
                )

            # Remove stops that are no longer in the Amtrak API response.
            # SCHEDULED journeys created by the pattern scheduler copy stops from
            # the most recent OBSERVED journey, which may include stations the
            # train doesn't actually stop at on this run. Without this cleanup
            # those stale stops persist with incorrect times. Guarded to rows
            # with no recorded reality (issue #1502): the feed trims already-
            # passed stations, and passed stops' actuals must survive.
            if journey.id and api_station_codes:
                deleted = cast(
                    CursorResult[tuple[()]],
                    await session.execute(
                        delete(JourneyStop).where(
                            and_(
                                JourneyStop.journey_id == journey.id,
                                JourneyStop.station_code.notin_(api_station_codes),
                                JourneyStop.has_departed_station.is_(False),
                                JourneyStop.actual_arrival.is_(None),
                                JourneyStop.actual_departure.is_(None),
                            )
                        )
                    ),
                )
                stale_count = deleted.rowcount or 0
                if stale_count:
                    logger.info(
                        "amtrak_stale_stops_removed",
                        train_id=train_id,
                        count=stale_count,
                    )

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

    @staticmethod
    def _compute_estimated_time(
        scheduled: datetime | None, comment: str
    ) -> datetime | None:
        """Compute estimated time from scheduled time and Amtrak delay comment.

        The Amtrak API provides delay info in depCmnt/arrCmnt fields as strings
        like "5 Min Late", "64 Min Late", "On Time", "Cancelled", or "".

        Returns scheduled + delay if a delay is parsed, otherwise returns scheduled.
        """
        if not scheduled or not comment:
            return scheduled

        match = re.match(r"(\d+)\s*min\s*late", comment, re.IGNORECASE)
        if match:
            return scheduled + timedelta(minutes=int(match.group(1)))

        match = re.match(r"(\d+)\s*min\s*early", comment, re.IGNORECASE)
        if match:
            return scheduled - timedelta(minutes=int(match.group(1)))

        # "On Time", "Cancelled", or unrecognized — return scheduled as-is
        return scheduled

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

            # After 3 failed attempts, attempt last-chance completion before
            # giving up. Without this backstop, a train that finishes its run
            # and drops off the API mid-Live-Activity stays is_expired-only —
            # which the scheduler intentionally ignores for end-of-activity
            # pushes (see PR #1114), leaving the user's Live Activity hanging
            # until token TTL.
            if journey.api_error_count >= 3:
                if not journey.is_completed:
                    await self._attempt_completion_on_expiry(session, journey)

                # Only expire a train that has actually started its run. A
                # train still at or before its origin is missing from the feed
                # only because of the normal pre-departure gap (the feed drops
                # trains before they go active), so expiring it would be wrong:
                # it permanently blocks JIT refreshes (see
                # JustInTimeUpdateService.needs_refresh), and the row would
                # never capture its real departure once it reappears.
                if not journey.is_completed and await self._has_departed_origin(
                    session, journey
                ):
                    journey.is_expired = True

                if journey.is_expired:
                    logger.warning(
                        "amtrak_train_marked_expired",
                        train_id=journey.train_id,
                        api_error_count=journey.api_error_count,
                    )
                elif journey.is_completed:
                    logger.warning(
                        "amtrak_train_completed_on_expiry",
                        train_id=journey.train_id,
                        api_error_count=journey.api_error_count,
                    )
                else:
                    logger.debug(
                        "amtrak_train_missing_before_departure",
                        train_id=journey.train_id,
                        api_error_count=journey.api_error_count,
                    )
            await session.flush()
            return

        # Reset error count on successful fetch
        if journey.api_error_count and journey.api_error_count > 0:
            logger.info(
                "resetting_api_error_count",
                train_id=journey.train_id,
                previous_count=journey.api_error_count,
            )
            journey.api_error_count = 0

        # Seeing the train in the feed again clears any prior expiry. A
        # transient feed gap must not leave a still-running journey stranded
        # as expired, which would block every future JIT refresh.
        if journey.is_expired:
            logger.info(
                "amtrak_train_unexpired_on_reobservation",
                train_id=journey.train_id,
            )
            journey.is_expired = False

        # Update journey with latest data
        journey.last_updated_at = now_et()
        journey.update_count = (journey.update_count or 0) + 1
        # Promote SCHEDULED → OBSERVED when we have real-time API data
        if journey.observation_type == "SCHEDULED":
            journey.observation_type = "OBSERVED"
            journey.first_seen_at = now_et()
            logger.info(
                "upgraded_amtrak_scheduled_to_observed_via_jit",
                train_id=journey.train_id,
                journey_date=str(journey.journey_date),
            )
        journey.destination = train_data.destName
        journey.is_cancelled = train_data.trainState == "Cancelled"
        journey.is_completed = train_data.trainState == "Terminated"
        journey.has_complete_journey = True

        # Update stops
        tracked_stops = []
        time_corrections = 0

        # Build the feed's station set up front: it drives the stale-stop
        # deletion below AND the stop_sequence base for this refresh. The
        # Amtraker feed trims already-passed stations, and the deletion guard
        # below preserves trimmed stops that carry recorded actuals — so the
        # surviving feed stops must be numbered AFTER the preserved ones.
        # Renumbering the feed from 0 would collide with the preserved
        # origin's sequence and scramble stop ordering (issue #1502).
        api_station_codes: set[str] = {
            code
            for amtrak_stop in train_data.stations
            if (code := AMTRAK_TO_INTERNAL_STATION_MAP.get(amtrak_stop.code))
        }

        stop_sequence = 0
        if api_station_codes:
            preserved_max_seq = await session.scalar(
                select(func.max(JourneyStop.stop_sequence)).where(
                    and_(
                        JourneyStop.journey_id == journey.id,
                        JourneyStop.station_code.notin_(api_station_codes),
                        or_(
                            JourneyStop.has_departed_station.is_(True),
                            JourneyStop.actual_arrival.is_not(None),
                            JourneyStop.actual_departure.is_not(None),
                        ),
                    )
                )
            )
            if preserved_max_seq is not None:
                stop_sequence = preserved_max_seq + 1

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

            # Clamp actual times to scheduled if earlier (timezone normalization artifacts)
            if (
                actual_departure
                and scheduled_departure
                and actual_departure < scheduled_departure
            ):
                actual_departure = scheduled_departure
                time_corrections += 1

            if (
                actual_arrival
                and scheduled_arrival
                and actual_arrival < scheduled_arrival
            ):
                actual_arrival = scheduled_arrival
                time_corrections += 1

            # Validate against scheduled time to prevent stale data issues
            departed: bool = amtrak_stop.status == "Departed" and (
                not scheduled_departure or scheduled_departure <= now_et()
            )
            track: str | None = amtrak_stop.platform if amtrak_stop.platform else None
            pickup_only: bool = False
            dropoff_only: bool = False

            stop_data = {
                "station_name": station_name,
                "stop_sequence": stop_sequence,
                "scheduled_arrival": scheduled_arrival,
                "scheduled_departure": scheduled_departure,
                "updated_arrival": self._compute_estimated_time(
                    scheduled_arrival, amtrak_stop.arrCmnt
                ),
                "updated_departure": self._compute_estimated_time(
                    scheduled_departure, amtrak_stop.depCmnt
                ),
                "actual_arrival": actual_arrival,
                "actual_departure": actual_departure,
                "arrival_source": "api_observed" if actual_arrival else None,
                "raw_amtrak_status": amtrak_stop.status,
                "has_departed_station": departed,  # Now using validated flag
                "track": track,
                "pickup_only": pickup_only,
                "dropoff_only": dropoff_only,
            }

            if existing_stop:
                # Update existing stop
                for field, value in stop_data.items():
                    # Preserve existing track when API returns None
                    if field == "track" and value is None and existing_stop.track:
                        logger.debug(
                            "preserving_existing_track",
                            train_id=journey.train_id,
                            station_code=internal_code,
                            track=existing_stop.track,
                        )
                        continue
                    # Log track changes for diagnostics
                    if field == "track" and value != getattr(
                        existing_stop, "track", None
                    ):
                        logger.info(
                            "track_changed",
                            train_id=journey.train_id,
                            station_code=internal_code,
                            old_track=existing_stop.track,
                            new_track=value,
                        )
                        if value and not existing_stop.track_assigned_at:
                            existing_stop.track_assigned_at = now_et()
                    setattr(existing_stop, field, value)
                existing_stop.updated_at = now_et()
                tracked_stops.append(existing_stop)
            else:
                # Create new stop
                new_stop = JourneyStop(
                    journey_id=journey.id,
                    journey_date=journey.journey_date,
                    station_code=internal_code,
                    station_name=station_name,
                    stop_sequence=stop_sequence,
                    scheduled_arrival=scheduled_arrival,
                    scheduled_departure=scheduled_departure,
                    actual_arrival=actual_arrival,
                    actual_departure=actual_departure,
                    arrival_source="api_observed" if actual_arrival else None,
                    has_departed_station=departed,
                    raw_amtrak_status=amtrak_stop.status,
                    track=track,
                    pickup_only=pickup_only,
                    dropoff_only=dropoff_only,
                )
                session.add(new_stop)
                tracked_stops.append(new_stop)

            stop_sequence += 1

        if time_corrections > 0:
            logger.info(
                "amtrak_stop_times_corrected",
                train_id=journey.train_id,
                corrections=time_corrections,
            )

        # Remove stops that are no longer in the Amtrak API response — but
        # only rows with no recorded reality. The feed TRIMS already-passed
        # stations, so an unguarded delete destroyed passed stops' actual
        # times and tracks on every refresh (issue #1502): origin-keyed
        # queries stopped matching mid-run, completed journeys kept only tail
        # stops, and the pattern scheduler's required-origin consensus check
        # starved. Pattern-scheduler template stops the train doesn't serve
        # never acquire actuals or a departed flag, so they are still cleaned
        # up as intended.
        if api_station_codes:
            deleted = cast(
                CursorResult[tuple[()]],
                await session.execute(
                    delete(JourneyStop).where(
                        and_(
                            JourneyStop.journey_id == journey.id,
                            JourneyStop.station_code.notin_(api_station_codes),
                            JourneyStop.has_departed_station.is_(False),
                            JourneyStop.actual_arrival.is_(None),
                            JourneyStop.actual_departure.is_(None),
                        )
                    )
                ),
            )
            stale_count = deleted.rowcount or 0
            if stale_count:
                logger.info(
                    "amtrak_stale_stops_removed",
                    train_id=journey.train_id,
                    count=stale_count,
                )

        # Durable origin-departure signal (issue #1501): the only other
        # writer of journey.actual_departure is _convert_to_journey, which
        # never re-runs once a row is OBSERVED (batch collection skips
        # OBSERVED rows) — so the #1490 expiry gate degraded to its fragile
        # surviving-stop fallback on the JIT-only lifecycle. Record it
        # write-once from the origin stop while that stop still exists.
        await session.flush()
        if journey.actual_departure is None and journey.origin_station_code:
            origin_actual = await session.scalar(
                select(JourneyStop.actual_departure).where(
                    and_(
                        JourneyStop.journey_id == journey.id,
                        JourneyStop.station_code == journey.origin_station_code,
                        JourneyStop.actual_departure.is_not(None),
                    )
                )
            )
            if origin_actual is not None:
                journey.actual_departure = origin_actual

        # Update journey metadata. stops_count is recounted from the DB
        # because preserved trimmed stops (see deletion guard above) are not
        # in tracked_stops; the terminal is still the feed's last stop (the
        # feed trims from the front, never the end).
        journey.stops_count = (
            await session.scalar(
                select(func.count())
                .select_from(JourneyStop)
                .where(JourneyStop.journey_id == journey.id)
            )
            or 0
        )
        if tracked_stops:
            journey.terminal_station_code = tracked_stops[-1].station_code
            journey.scheduled_arrival = tracked_stops[-1].scheduled_arrival
            if journey.is_completed and tracked_stops[-1].actual_arrival:
                journey.actual_arrival = tracked_stops[-1].actual_arrival

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

    async def _has_departed_origin(
        self, session: AsyncSession, journey: TrainJourney
    ) -> bool:
        """Return True if the journey has genuinely started its run.

        Distinguishes a train that has departed its origin (safe to expire
        once it vanishes from the feed) from one still waiting at or before its
        origin, whose absence is just the normal pre-departure feed gap and
        must stay refreshable.

        Uses durable signals rather than the lowest-``stop_sequence`` stop: the
        Amtraker feed trims already-passed stations and this collector deletes
        stops no longer in the feed (``amtrak_stale_stops_removed``), so once a
        mid-run train's origin is trimmed the lowest remaining stop is a
        *future* stop whose ``has_departed_station`` is ``False``. That would
        make a genuinely-departed, now-lost train look pre-departure and leave
        it unexpired forever. ``journey.actual_departure`` (recorded
        write-once by ``_convert_to_journey`` and ``collect_journey_details``
        when the origin stop reports departure, issue #1501) persists on the
        row regardless of stop trimming; the surviving-departed-stop check is
        a fallback for rows that never captured it.
        """
        if journey.actual_departure is not None:
            return True
        departed_stop = await session.scalar(
            select(JourneyStop)
            .where(
                and_(
                    JourneyStop.journey_id == journey.id,
                    JourneyStop.has_departed_station.is_(True),
                )
            )
            .limit(1)
        )
        return departed_stop is not None

    async def _attempt_completion_on_expiry(
        self,
        session: AsyncSession,
        journey: TrainJourney,
    ) -> None:
        """Last-chance completion when an Amtrak train disappears from the API.

        Mirrors NJTJourneyCollector._attempt_completion_on_expiry: if the
        penultimate stop has departed, the train reached its terminal. We
        can't pull terminal actual_arrival from the API (the train is gone),
        but marking the journey completed lets the scheduler end the user's
        Live Activity rather than orphaning it on is_expired alone.
        """
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

        journey.is_completed = True

        if terminal_stop.actual_arrival is None and terminal_stop.scheduled_arrival:
            terminal_stop.actual_arrival = terminal_stop.scheduled_arrival
            terminal_stop.arrival_source = "scheduled_fallback"
            journey.actual_arrival = terminal_stop.scheduled_arrival

        logger.info(
            "amtrak_journey_completed_on_expiry",
            train_id=journey.train_id,
            journey_id=journey.id,
            terminal_arrival_source=terminal_stop.arrival_source,
        )

        transit_analyzer = TransitAnalyzer()
        await transit_analyzer.analyze_journey(session, journey)
