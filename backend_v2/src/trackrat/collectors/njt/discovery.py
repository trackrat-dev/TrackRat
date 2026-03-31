"""
Train discovery collector for TrackRat V2.

Discovers active trains by polling station departure boards.
"""

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, exists, func, literal, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.base import BaseDiscoveryCollector
from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.schedule import parse_njt_line_code
from trackrat.config.stations import DISCOVERY_STATIONS
from trackrat.db.engine import get_session
from trackrat.models.database import DiscoveryRun, JourneyStop, TrainJourney
from trackrat.utils.sanitize import sanitize_track
from trackrat.utils.time import now_et, parse_njt_time
from trackrat.utils.train import is_amtrak_train

logger = get_logger(__name__)


class TrainDiscoveryCollector(BaseDiscoveryCollector):
    """Discovers active trains from station schedules."""

    def __init__(self, njt_client: NJTransitClient) -> None:
        """Initialize the discovery collector.

        Args:
            njt_client: NJ Transit API client
        """
        self.njt_client = njt_client

    async def discover_trains(self) -> list[str]:
        """Discover active train IDs from all stations.

        Returns:
            List of discovered train IDs
        """
        discovered_ids = []
        for station_code in DISCOVERY_STATIONS:
            try:
                schedule_response = await self.njt_client.get_train_schedule_with_stops(
                    station_code
                )
                trains_data = schedule_response.get("ITEMS") or []
                for train_data in trains_data:
                    train_id = train_data.get("TRAIN_ID", "").strip()
                    if train_id and train_id not in discovered_ids:
                        discovered_ids.append(train_id)
            except Exception as e:
                logger.error(
                    "failed_to_discover_from_station",
                    station=station_code,
                    error=str(e),
                )
                continue

        return discovered_ids

    async def run(self) -> dict[str, Any]:
        """Run the collector.

        Returns:
            Collection results
        """
        return await self.collect()

    async def collect(self) -> dict[str, Any]:
        """Run discovery for all configured stations.

        Uses a separate database session per station to minimize lock hold time
        and prevent deadlocks with concurrent journey collection.

        Returns:
            Discovery results summary
        """
        logger.info("discovery.njt.started", stations=DISCOVERY_STATIONS)

        total_discovered = 0
        total_new = 0
        station_results = {}

        for station_code in DISCOVERY_STATIONS:
            async with get_session() as session:
                result = await self.discover_station_trains(session, station_code)
            station_results[station_code] = result
            total_discovered += result["trains_discovered"]
            total_new += result["new_trains"]

        logger.info(
            "discovery.njt.completed",
            total_discovered=total_discovered,
            total_new=total_new,
            stations_processed=len(DISCOVERY_STATIONS),
        )

        return {
            "stations_processed": len(DISCOVERY_STATIONS),
            "total_discovered": total_discovered,
            "total_new": total_new,
            "station_results": station_results,
        }

    async def discover_station_trains(
        self, session: AsyncSession, station_code: str
    ) -> dict[str, Any]:
        """Discover trains from a single station.

        Args:
            session: Database session
            station_code: Two-character station code

        Returns:
            Discovery results for this station
        """
        start_time = now_et()
        discovery_run = DiscoveryRun(station_code=station_code, run_at=start_time)

        try:
            # Get train schedule data with embedded stops
            schedule_response = await self.njt_client.get_train_schedule_with_stops(
                station_code
            )
            trains_data = schedule_response.get("ITEMS") or []

            # Track ALL train IDs for batch collection
            all_train_ids = []
            amtrak_train_ids = []
            for train_data in trains_data:
                train_id = train_data.get("TRAIN_ID", "").strip()
                if train_id:
                    all_train_ids.append(train_id)
                    if is_amtrak_train(train_id):
                        track = train_data.get("TRACK", "")
                        amtrak_train_ids.append(f"{train_id}[track={track or 'none'}]")

            # Process discovered trains (creates/updates journey records)
            new_train_ids = await self.process_discovered_trains(
                session, station_code, trains_data
            )

            # Update discovery run
            duration_ms = int((now_et() - start_time).total_seconds() * 1000)
            discovery_run.trains_discovered = len(trains_data)
            discovery_run.new_trains = len(new_train_ids)
            discovery_run.duration_ms = duration_ms
            discovery_run.success = True

            session.add(discovery_run)
            await session.flush()

            logger.info(
                "station_discovery_complete",
                station_code=station_code,
                trains_discovered=len(trains_data),
                new_trains=len(new_train_ids),
                amtrak_trains=len(amtrak_train_ids),
                amtrak_detail=amtrak_train_ids if amtrak_train_ids else None,
                duration_ms=duration_ms,
            )

            return {
                "trains_discovered": len(trains_data),
                "new_trains": len(new_train_ids),
                "new_train_ids": list(new_train_ids),
                "all_train_ids": all_train_ids,  # Return ALL discovered train IDs
            }

        except Exception as e:
            # Track failure
            logger.error(
                "station_discovery_failed",
                station_code=station_code,
                error=str(e),
                error_type=type(e).__name__,
            )

            discovery_run.success = False
            discovery_run.error_details = str(e)
            session.add(discovery_run)
            await session.flush()

            return {"trains_discovered": 0, "new_trains": 0, "error": str(e)}

    async def _update_stop_track_if_needed(
        self,
        session: AsyncSession,
        journey: TrainJourney,
        station_code: str,
        track: str,
    ) -> None:
        """Update track for a specific journey stop, creating the stop if needed.

        Args:
            session: Database session
            journey: The journey to update
            station_code: Station code where track was discovered
            track: Track number to assign
        """
        # Find the stop for this station
        stmt = select(JourneyStop).where(
            and_(
                JourneyStop.journey_id == journey.id,
                JourneyStop.station_code == station_code,
            )
        )
        stop = await session.scalar(stmt)

        if stop:
            # Stop exists - update track if not already set
            if not stop.track:
                sanitized_track = sanitize_track(track)
                if sanitized_track:
                    stop.track = sanitized_track
                    stop.track_assigned_at = now_et()
                    logger.info(
                        "updated_existing_stop_track_during_discovery",
                        train_id=journey.train_id,
                        station_code=station_code,
                        track=sanitized_track,
                    )
        else:
            # Stop doesn't exist - create it with the track
            # Use savepoint to handle race with journey collector creating the same stop
            from trackrat.config.stations import get_station_name

            sanitized_track = sanitize_track(track)
            if sanitized_track:
                try:
                    async with session.begin_nested():
                        stop = JourneyStop(
                            journey_id=journey.id,
                            station_code=station_code,
                            station_name=get_station_name(station_code),
                            # Don't set stop_sequence - let journey collector handle it exclusively
                            track=sanitized_track,
                            track_assigned_at=now_et(),
                        )
                        session.add(stop)
                        await session.flush()
                    logger.info(
                        "created_stop_with_track_during_discovery",
                        train_id=journey.train_id,
                        station_code=station_code,
                        track=sanitized_track,
                    )
                except IntegrityError:
                    # Race: journey collector created this stop concurrently
                    # Re-query and update track on the existing stop
                    stop = await session.scalar(stmt)
                    if stop and not stop.track:
                        stop.track = sanitized_track
                        stop.track_assigned_at = now_et()
                    logger.info(
                        "stop_created_by_concurrent_process_updating_track",
                        train_id=journey.train_id,
                        station_code=station_code,
                        track=sanitized_track,
                    )

    async def _find_matching_scheduled_train(
        self,
        session: AsyncSession,
        station_code: str,
        destination: str,
        scheduled_departure: datetime,
        journey_date: date,
        time_tolerance_minutes: int = 5,
    ) -> TrainJourney | None:
        """Find a SCHEDULED NJT train that matches by route and time.

        Used when a real-time train ID doesn't match any existing record.
        NJT sometimes assigns different train numbers in the published schedule
        vs the real-time feed for the same physical train.

        Matches via JourneyStop at the discovery station (not TrainJourney.scheduled_departure)
        because the journey's origin may differ from the discovery station.

        Follows the same pattern as PATH's _find_matching_journey().

        Args:
            session: Database session
            station_code: Discovery station code
            destination: Train destination from real-time API
            scheduled_departure: Departure time at discovery station
            journey_date: Date of the journey
            time_tolerance_minutes: Max minutes difference for time matching

        Returns:
            Matching SCHEDULED TrainJourney if found, None otherwise
        """
        time_window = timedelta(minutes=time_tolerance_minutes)
        time_min = scheduled_departure - time_window
        time_max = scheduled_departure + time_window

        stmt = (
            select(TrainJourney)
            .join(JourneyStop, JourneyStop.journey_id == TrainJourney.id)
            .where(
                and_(
                    TrainJourney.data_source == "NJT",
                    TrainJourney.journey_date == journey_date,
                    TrainJourney.observation_type == "SCHEDULED",
                    TrainJourney.is_cancelled.is_(False),
                    func.lower(func.trim(TrainJourney.destination))
                    == func.lower(destination.strip()),
                    JourneyStop.station_code == station_code,
                    JourneyStop.scheduled_departure.is_not(None),
                    JourneyStop.scheduled_departure >= time_min,
                    JourneyStop.scheduled_departure <= time_max,
                )
            )
            .order_by(
                func.abs(
                    func.extract("epoch", JourneyStop.scheduled_departure)
                    - func.extract("epoch", literal(scheduled_departure))
                )
            )
            .with_for_update(skip_locked=True)
            .limit(1)
        )

        result: TrainJourney | None = await session.scalar(stmt)
        return result

    async def process_discovered_trains(
        self,
        session: AsyncSession,
        station_code: str,
        trains_data: list[dict[str, Any]],
    ) -> set[str]:
        """Process discovered trains and create journey records.

        Args:
            session: Database session
            station_code: Station where trains were discovered
            trains_data: Raw train data from API

        Returns:
            Set of newly discovered train IDs
        """
        new_train_ids = set()

        # Process each train inside a savepoint so one failure
        # doesn't poison the session for subsequent trains.
        for train_data in trains_data:
            try:
                # Extract key fields (no DB access - safe outside savepoint)
                train_id = train_data.get("TRAIN_ID", "").strip()
                if not train_id:
                    continue

                # Skip Amtrak trains (format: A + digits)
                if is_amtrak_train(train_id):
                    continue

                # Parse scheduled departure time
                sched_dep_str = train_data.get("SCHED_DEP_DATE", "")
                if not sched_dep_str:
                    continue

                scheduled_departure = parse_njt_time(sched_dep_str)
                journey_date = scheduled_departure.date()

                # Disable autoflush inside savepoint to prevent implicit
                # lock acquisition during SELECTs that can deadlock with
                # concurrent journey collection. Explicit flush() still works.
                async with session.begin_nested():
                    with session.no_autoflush:
                        # Check if journey already exists.
                        # FOR UPDATE SKIP LOCKED prevents deadlocks with
                        # concurrent journey collection by skipping rows
                        # that are locked by another process, matching the
                        # pattern used by PATH and Amtrak collectors.
                        stmt = (
                            select(TrainJourney)
                            .where(
                                TrainJourney.train_id == train_id,
                                TrainJourney.journey_date == journey_date,
                                TrainJourney.data_source == "NJT",
                            )
                            .order_by(TrainJourney.id)
                            .with_for_update(skip_locked=True)
                        )
                        existing = await session.scalar(stmt)

                        if existing is None:
                            # Distinguish "row doesn't exist" from "row is
                            # locked by another process" (skip_locked).
                            # A non-locking existence check avoids inserting
                            # a duplicate that would violate unique_train_journey.
                            row_exists = await session.scalar(
                                select(
                                    exists().where(
                                        TrainJourney.train_id == train_id,
                                        TrainJourney.journey_date == journey_date,
                                        TrainJourney.data_source == "NJT",
                                    )
                                )
                            )
                            if row_exists:
                                # Row is locked by concurrent collection — skip
                                logger.debug(
                                    "discovery_skipped_locked_row",
                                    train_id=train_id,
                                    journey_date=journey_date,
                                )
                                continue

                        if existing:
                            # Re-activate expired trains that reappear in discovery
                            if existing.is_expired:
                                existing.is_expired = False
                                existing.api_error_count = 0
                                logger.info(
                                    "reactivated_expired_train",
                                    train_id=train_id,
                                    journey_date=journey_date,
                                )

                            # Update last seen time
                            existing.last_updated_at = now_et()

                            # Mark as observed if it was previously scheduled
                            if existing.observation_type == "SCHEDULED":
                                existing.observation_type = "OBSERVED"
                                # Fix line_code: schedule collector may have
                                # stored a truncated full name (e.g., "No"
                                # from "Northeast Corridor" instead of "NE")
                                rt_line = train_data.get("LINE", "").strip()
                                if rt_line:
                                    existing.line_code = parse_njt_line_code(rt_line)
                                    existing.line_name = (
                                        train_data.get("LINE_NAME", "")
                                        or existing.line_name
                                    )
                                logger.info(
                                    "upgraded_scheduled_to_observed",
                                    train_id=train_id,
                                    journey_date=journey_date,
                                )

                            # Update track directly in journey stop
                            track = train_data.get("TRACK")
                            if track and station_code:
                                await self._update_stop_track_if_needed(
                                    session, existing, station_code, track
                                )

                            continue

                        # Before creating a new record, check if a SCHEDULED
                        # train matches by destination and departure time.
                        # NJT sometimes uses different train numbers in the
                        # published schedule vs the real-time feed.
                        destination = train_data.get("DESTINATION", "").strip()
                        scheduled_match = (
                            await self._find_matching_scheduled_train(
                                session,
                                station_code,
                                destination,
                                scheduled_departure,
                                journey_date,
                            )
                            if destination
                            else None
                        )

                        if scheduled_match:
                            try:
                                async with session.begin_nested():
                                    old_train_id = scheduled_match.train_id
                                    scheduled_match.train_id = train_id
                                    scheduled_match.observation_type = "OBSERVED"
                                    scheduled_match.last_updated_at = now_et()
                                    # Fix line_code from real-time API
                                    rt_line = train_data.get("LINE", "").strip()
                                    if rt_line:
                                        scheduled_match.line_code = parse_njt_line_code(
                                            rt_line
                                        )
                                        scheduled_match.line_name = (
                                            train_data.get("LINE_NAME", "")
                                            or scheduled_match.line_name
                                        )

                                    track = train_data.get("TRACK")
                                    if track and station_code:
                                        await self._update_stop_track_if_needed(
                                            session,
                                            scheduled_match,
                                            station_code,
                                            track,
                                        )

                                logger.info(
                                    "fuzzy_matched_scheduled_to_observed",
                                    old_train_id=old_train_id,
                                    new_train_id=train_id,
                                    destination=destination,
                                    station_code=station_code,
                                    journey_date=journey_date,
                                )
                            except IntegrityError:
                                # Race: another process already created a journey
                                # with this train_id — skip the fuzzy match
                                logger.info(
                                    "fuzzy_match_skipped_duplicate_train_id",
                                    train_id=train_id,
                                    scheduled_train_id=scheduled_match.train_id,
                                    journey_date=journey_date,
                                )
                            continue

                        # Create new journey
                        # NOTE: We temporarily use the discovery station as origin,
                        # but this might be an intermediate stop. The journey
                        # collector will correct this when it fetches full details.
                        journey = TrainJourney(
                            train_id=train_id,
                            journey_date=journey_date,
                            line_code=parse_njt_line_code(
                                train_data.get("LINE", "").strip()
                            ),
                            line_name=train_data.get("LINE_NAME", ""),
                            destination=train_data.get("DESTINATION", "").strip(),
                            origin_station_code=station_code,
                            terminal_station_code=station_code,
                            scheduled_departure=scheduled_departure,
                            data_source="NJT",
                            observation_type="OBSERVED",
                            first_seen_at=now_et(),
                            last_updated_at=now_et(),
                            has_complete_journey=False,
                            update_count=1,
                        )

                        # Extract line color if available
                        if "BACKCOLOR" in train_data:
                            journey.line_color = train_data["BACKCOLOR"].strip()

                        session.add(journey)
                        await session.flush()  # Ensure journey has ID
                        new_train_ids.add(train_id)

                        # Update track directly in journey stop
                        track = train_data.get("TRACK")
                        if track and station_code:
                            await self._update_stop_track_if_needed(
                                session, journey, station_code, track
                            )

                        logger.debug(
                            "new_journey_discovered",
                            train_id=train_id,
                            journey_date=journey_date,
                            line=journey.line_code,
                            destination=journey.destination,
                            departure=scheduled_departure.isoformat(),
                            track=track,
                        )

            except Exception as e:
                logger.error(
                    "failed_to_process_train", train_data=train_data, error=str(e)
                )
                continue

        return new_train_ids
