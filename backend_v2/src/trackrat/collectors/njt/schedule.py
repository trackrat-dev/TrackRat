"""
NJ Transit schedule collector for TrackRat V2.

Fetches 27-hour schedule data once daily and creates SCHEDULED journey records.
"""

import asyncio
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.journey import STALE_PRIOR_RUN_THRESHOLD_SECONDS
from trackrat.db.engine import get_session
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.locks import acquire_njt_journey_lock
from trackrat.utils.sanitize import sanitize_track
from trackrat.utils.time import now_et, parse_njt_time, validate_journey_date

logger = get_logger(__name__)

# NJT schedule API LINE field prefixes → canonical 2-char codes.
# The schedule API returns full line names (e.g., "Northeast Corridor")
# unlike the real-time discovery API which returns short codes (e.g., "NEC").
_NJT_LINE_NAME_PREFIXES: list[tuple[str, str]] = [
    ("northeast", "NE"),
    ("north jersey", "NC"),
    ("gladstone", "GL"),
    ("montclair", "MO"),
    ("boonton", "MO"),
    ("morris", "ME"),
    ("raritan", "RV"),
    ("pascack", "PV"),
    ("bergen", "BE"),
    ("main", "MA"),
    ("atlantic", "AC"),
    ("princeton", "PR"),
]


def parse_njt_line_code(line: str) -> str:
    """Extract canonical 2-char NJT line code from the LINE field.

    The NJT schedule API returns full line names (e.g., "Northeast Corridor")
    while the real-time discovery API returns short codes (e.g., "NEC").
    This function handles both formats.
    """
    if not line:
        return ""
    # Short codes (≤3 chars) from real-time API — truncate to 2
    if len(line) <= 3:
        return line[:2]
    # Full names from schedule API — match by known prefix
    lower = line.lower()
    for prefix, code in _NJT_LINE_NAME_PREFIXES:
        if lower.startswith(prefix):
            return code
    # Unknown — log for investigation, fall back to truncation
    logger.warning("unknown_njt_line_name", line=line, fallback=line[:2])
    return line[:2]


class NJTScheduleCollector:
    """Collects NJ Transit schedule data once daily."""

    def __init__(self, client: NJTransitClient) -> None:
        """Initialize the schedule collector.

        Args:
            client: NJ Transit API client instance
        """
        self.client = client

    async def collect_all_schedules(self) -> dict[str, Any]:
        """Collect 27-hour schedule data for all stations.

        This method:
        1. Fetches schedule data from NJ Transit API (single call)
        2. Parses schedule items into train journeys
        3. Creates SCHEDULED records for trains not already OBSERVED
        4. Updates existing SCHEDULED records with latest data

        Returns:
            Dictionary with collection statistics
        """
        logger.info("starting_njt_schedule_collection")

        try:
            # Get schedule for all stations (empty string = all)
            # Only fetch NJT trains - Amtrak has its own discovery pipeline
            schedule_data = await self.client.get_station_schedule(
                station_code=None, njt_only=True  # All stations, NJT trains only
            )

            logger.info(
                "schedule_data_retrieved",
                station_count=len(schedule_data),
                total_items=sum(
                    len(station.get("ITEMS") or []) for station in schedule_data
                ),
            )

            # Process the schedule data
            async with get_session() as session:
                stats = await self._process_schedule_data(session, schedule_data)

            # Collect full stop lists for new NJT trains in a new session
            # (needs to be separate so we can query the committed schedule data)
            async with get_session() as session:
                stop_stats = await self._collect_stop_lists_for_scheduled_trains(
                    session
                )
                stats.update(stop_stats)

            logger.info("njt_schedule_collection_completed", **stats)

            return stats

        except Exception as e:
            logger.error(
                "njt_schedule_collection_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    async def _process_schedule_data(
        self, session: AsyncSession, schedule_data: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Process schedule data and create/update journey records.

        Args:
            session: Database session
            schedule_data: Raw schedule data from API

        Returns:
            Processing statistics
        """
        stats = {
            "total_schedules": 0,
            "new_schedules": 0,
            "skipped_observed": 0,
            "updated_schedules": 0,
            "errors": 0,
        }

        # Derive each item's journey_date from its RUN's origin departure,
        # NOT from the nightly run date. The schedule window spans ~27 hours,
        # so a train departing after the next midnight belongs to the NEXT
        # service date; stamping it with the run date made discovery — which
        # derives journey_date from SCHED_DEP_DATE (see discovery.py) — miss
        # the row on both its exact and fuzzy matches and create a duplicate
        # OBSERVED journey, leaving the run-dated SCHEDULED row as a
        # permanent zombie on departure boards (issue #1499).
        #
        # Each train's departures are clustered into runs because the 27h
        # window can contain BOTH service days' occurrence of an overnight
        # train (~00:30-03:30 departures): a single earliest-per-train date
        # would collapse the two runs onto the earlier date, costing the
        # next day's run its SCHEDULED visibility (PR #1510 review).
        # Departures within STALE_PRIOR_RUN_THRESHOLD_SECONDS of the
        # previous one chain into the same run — which keeps a cross-midnight
        # run (origin before midnight, later stops minutes after) on a
        # single row dated by its origin — while a larger gap (~24h for a
        # daily train) starts a new run. The mapping is keyed by the item's
        # raw SCHED_DEP_DATE string so the item loop needs no re-parse and
        # the lookup is exact.
        departures_by_train: dict[str, list[tuple[datetime, str]]] = {}
        for station_data in schedule_data:
            for item in station_data.get("ITEMS") or []:
                item_train_id = item.get("TRAIN_ID")
                item_dep_str = item.get("SCHED_DEP_DATE")
                if not item_train_id or not item_dep_str:
                    continue
                try:
                    item_departure = parse_njt_time(item_dep_str)
                except Exception:
                    # _process_schedule_item re-parses and reports the error
                    # for this item; the train may still get dates from its
                    # parseable items at other stations.
                    continue
                if not item_departure:
                    continue
                departures_by_train.setdefault(item_train_id, []).append(
                    (item_departure, item_dep_str)
                )

        origin_date_by_departure: dict[str, dict[str, date]] = {}
        for train_id, departures in departures_by_train.items():
            departures.sort(key=lambda pair: pair[0])
            mapping: dict[str, date] = {}
            run_origin = previous = departures[0][0]
            for item_departure, item_dep_str in departures:
                gap_seconds = (item_departure - previous).total_seconds()
                if gap_seconds > STALE_PRIOR_RUN_THRESHOLD_SECONDS:
                    run_origin = item_departure
                mapping[item_dep_str] = run_origin.date()
                previous = item_departure
            origin_date_by_departure[train_id] = mapping

        # Fallback only for items whose own SCHED_DEP_DATE is missing or
        # unparseable — _process_schedule_item skips or errors those before
        # journey_date is ever persisted.
        run_date = now_et().date()

        # Process each station's schedule items
        for station_data in schedule_data:
            station_code = station_data.get("STATION_2CHAR")
            station_name = station_data.get("STATIONNAME")
            items = station_data.get("ITEMS") or []

            if not station_code:
                logger.warning("station_missing_code", station_data=station_data)
                continue

            logger.debug(
                "processing_station_schedule",
                station_code=station_code,
                station_name=station_name,
                item_count=len(items),
            )

            for item in items:
                stats["total_schedules"] += 1

                try:
                    item_train_id = item.get("TRAIN_ID")
                    item_dep_str = item.get("SCHED_DEP_DATE")
                    run_origin_date = (
                        origin_date_by_departure.get(item_train_id, {}).get(
                            item_dep_str
                        )
                        if item_train_id and item_dep_str
                        else None
                    )
                    journey_date = run_origin_date or run_date

                    # Mirror discovery.py's guard: never persist a schedule row
                    # on an implausible date. parse_njt_time is lenient, so a
                    # malformed SCHED_DEP_DATE can parse to a far-future date;
                    # journey_date has no DB CHECK and the partition default
                    # accepts any date, so without this a bad provider timestamp
                    # would create a far-future zombie SCHEDULED row. Discovery
                    # will pick the train up with its own validation if/when it
                    # actually appears in the real-time feed.
                    if not validate_journey_date(journey_date):
                        stats["errors"] += 1
                        logger.warning(
                            "rejecting_invalid_schedule_journey_date",
                            station_code=station_code,
                            train_id=item_train_id,
                            journey_date=journey_date.isoformat(),
                        )
                        continue

                    # Use savepoint so a single item failure (e.g. unique
                    # constraint violation) doesn't poison the session for
                    # all subsequent items in this batch.
                    async with session.begin_nested():
                        result = await self._process_schedule_item(
                            session,
                            item,
                            station_code,
                            station_name or "",
                            journey_date,
                        )

                    if result == "new":
                        stats["new_schedules"] += 1
                    elif result == "updated":
                        stats["updated_schedules"] += 1
                    elif result == "skipped":
                        stats["skipped_observed"] += 1

                except IntegrityError:
                    # Race: discovery or another collector already created
                    # this journey concurrently. Treat as a skip.
                    stats["skipped_observed"] += 1
                    logger.info(
                        "schedule_insert_race_skipped",
                        station_code=station_code,
                        train_id=item.get("TRAIN_ID"),
                    )
                except Exception as e:
                    stats["errors"] += 1
                    logger.error(
                        "schedule_item_processing_failed",
                        station_code=station_code,
                        train_id=item.get("TRAIN_ID"),
                        error=str(e),
                        error_type=type(e).__name__,
                    )

        # Commit all changes
        await session.commit()

        return stats

    async def _process_schedule_item(
        self,
        session: AsyncSession,
        item: dict[str, Any],
        station_code: str,
        station_name: str,
        journey_date: date,
    ) -> str:
        """Process a single schedule item.

        Args:
            session: Database session
            item: Schedule item data
            station_code: Station code where train departs
            station_name: Station name
            journey_date: Date of the journey

        Returns:
            "new", "updated", or "skipped"
        """
        train_id = item.get("TRAIN_ID")
        if not train_id:
            logger.warning("schedule_item_missing_train_id", item=item)
            return "skipped"

        # Parse scheduled departure time
        sched_dep_str = item.get("SCHED_DEP_DATE")
        if not sched_dep_str:
            logger.warning(
                "schedule_item_missing_departure",
                train_id=train_id,
                item=item,
            )
            return "skipped"

        # Parse the scheduled departure time
        scheduled_departure = parse_njt_time(sched_dep_str)
        if not scheduled_departure:
            logger.warning(
                "schedule_item_invalid_departure",
                train_id=train_id,
                departure_str=sched_dep_str,
            )
            return "skipped"

        # Extract other fields
        destination = item.get("DESTINATION", "Unknown")
        line = item.get("LINE", "")
        track = item.get("TRACK")  # May be line name for schedule data

        # Validate train ID format - NJT trains should be numeric
        # Non-numeric IDs are typically Amtrak trains
        if not train_id.isdigit():
            # This shouldn't happen with njt_only=True, but log if it does
            logger.warning(
                "unexpected_non_numeric_train_id_in_njt_schedule",
                train_id=train_id,
                destination=destination,
                line=line,
                scheduled_departure=sched_dep_str,
            )
            return "skipped"

        # All NJT trains use NJT data source
        data_source = "NJT"

        # Check if this journey already exists
        stmt = select(TrainJourney).where(
            and_(
                TrainJourney.train_id == train_id,
                TrainJourney.journey_date == journey_date,
                TrainJourney.data_source == data_source,
            )
        )
        result = await session.execute(stmt)
        existing_journey = result.scalar_one_or_none()

        if existing_journey:
            # If it's already OBSERVED, skip updating it
            if existing_journey.observation_type == "OBSERVED":
                logger.debug(
                    "skipping_observed_journey",
                    train_id=train_id,
                    journey_date=journey_date,
                )
                return "skipped"

            # Update the scheduled journey with latest schedule data.
            # NJT lists the same train in every stop-station's schedule (origin,
            # intermediates, terminus). Without the earliest-wins guard below,
            # whichever station is processed last would overwrite the journey's
            # scheduled_departure with an intermediate/terminal time, leaving
            # the journey row inconsistent with stops[0]. Guarantee that
            # scheduled_departure converges on the train's actual origin time.
            if (
                existing_journey.scheduled_departure is None
                or scheduled_departure < existing_journey.scheduled_departure
            ):
                existing_journey.scheduled_departure = scheduled_departure
            existing_journey.destination = destination
            existing_journey.line_code = parse_njt_line_code(line)
            existing_journey.line_name = line
            existing_journey.last_updated_at = now_et()

            logger.debug(
                "updated_scheduled_journey",
                train_id=train_id,
                journey_date=journey_date,
            )
            return "updated"

        # The schedule API sometimes returns the line name (or another >5-char
        # string) in TRACK; sanitize it like journey.py/discovery.py do —
        # writing it raw overflows the String(5) column and aborts the whole
        # item under StringDataRightTruncation (issue #1508).
        sanitized_track = sanitize_track(track) if track and track != line else None

        # Create new SCHEDULED journey
        new_journey = TrainJourney(
            train_id=train_id,
            journey_date=journey_date,
            line_code=parse_njt_line_code(line),
            line_name=line,
            destination=destination,
            origin_station_code=station_code,
            terminal_station_code=station_code,  # Will be updated if we get full route
            data_source=data_source,
            observation_type="SCHEDULED",
            scheduled_departure=scheduled_departure,
            discovery_station_code=station_code,
            discovery_track=sanitized_track,
            has_complete_journey=False,  # Schedule doesn't include stop details
            stops_count=0,
            is_cancelled=False,
            is_completed=False,
            is_expired=False,
            api_error_count=0,
            update_count=1,
        )

        session.add(new_journey)

        # Create a single stop for the departure station
        # (Schedule API doesn't provide full stop list)
        # Note: stop_sequence=None because we don't know where this station falls
        # in the actual journey until we get the full stop list from the API
        departure_stop = JourneyStop(
            journey=new_journey,
            station_code=station_code,
            station_name=station_name,
            stop_sequence=None,  # Will be set during journey collection
            scheduled_departure=scheduled_departure,
            scheduled_arrival=scheduled_departure,  # Same as departure for origin
            track=sanitized_track,
            track_assigned_at=now_et() if sanitized_track else None,
            has_departed_station=False,
        )

        session.add(departure_stop)

        logger.debug(
            "created_scheduled_journey",
            train_id=train_id,
            journey_date=journey_date,
            station_code=station_code,
            destination=destination,
        )

        return "new"

    async def _collect_stop_lists_for_scheduled_trains(
        self, session: AsyncSession
    ) -> dict[str, Any]:
        """Collect full stop lists for NJT scheduled trains.

        This method fetches the complete route information for each NJT
        scheduled train, allowing them to appear in route searches.

        Args:
            session: Database session

        Returns:
            Dictionary with collection statistics
        """
        stats = {
            "stop_collections_attempted": 0,
            "stop_collections_successful": 0,
            "stop_collections_failed": 0,
        }

        # Get all NJT scheduled trains from tonight's run that need stop
        # lists. The 27-hour schedule window produces rows dated today AND
        # tomorrow (after-midnight departures carry the next service date,
        # issue #1499), so cover both dates — a run-date-only filter would
        # leave next-date rows without stop lists until observed.
        today = now_et().date()
        stmt = select(TrainJourney).where(
            and_(
                TrainJourney.observation_type == "SCHEDULED",
                TrainJourney.data_source == "NJT",
                TrainJourney.journey_date >= today,
                TrainJourney.journey_date <= today + timedelta(days=1),
                TrainJourney.has_complete_journey.is_(
                    False
                ),  # Only trains without stops
            )
        )

        result = await session.execute(stmt)
        scheduled_journeys = result.scalars().all()

        logger.info(
            "collecting_stop_lists_for_scheduled_trains",
            journey_count=len(scheduled_journeys),
        )

        for journey in scheduled_journeys:
            stats["stop_collections_attempted"] += 1
            # Snapshot before the try: a savepoint rollback below expires
            # journey's ORM attributes, and re-reading them from the async
            # session in the except handler raises MissingGreenlet.
            train_id = journey.train_id

            try:
                # Small delay to be nice to the API
                await asyncio.sleep(0.25)

                # Fetch the train stop list
                train_data = await self.client.get_train_stop_list(train_id)

                # Use savepoint so a single train failure doesn't poison the
                # session for all subsequent trains in this batch.
                async with session.begin_nested():
                    await self._update_journey_with_stops(session, journey, train_data)

                stats["stop_collections_successful"] += 1

                logger.debug(
                    "collected_stops_for_scheduled_train",
                    train_id=train_id,
                    stop_count=len(train_data.STOPS) if train_data.STOPS else 0,
                )

            except Exception as e:
                stats["stop_collections_failed"] += 1
                logger.warning(
                    "failed_to_collect_stops_for_scheduled_train",
                    train_id=train_id,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )
                # Continue with next train instead of failing entire collection
                continue

        # Commit all the stop updates
        await session.commit()

        logger.info(
            "stop_collection_completed",
            **stats,
        )

        return stats

    async def _update_journey_with_stops(
        self,
        session: AsyncSession,
        journey: TrainJourney,
        train_data: Any,
    ) -> None:
        """Update a scheduled journey with full stop information.

        Args:
            session: Database session
            journey: The scheduled journey to update
            train_data: API response with stop list
        """
        if not train_data or not train_data.STOPS:
            logger.warning(
                "no_stops_in_api_response",
                train_id=journey.train_id,
            )
            return

        # Serialize this journey's writers across replicas (issue #1369):
        # this delete+recreate can otherwise race the JIT/scheduled
        # collection paths' phantom-stop delete and stop updates.
        await acquire_njt_journey_lock(session, journey.train_id, journey.journey_date)

        # Delete the single placeholder stop we created during schedule collection
        from sqlalchemy import delete

        await session.execute(
            delete(JourneyStop).where(JourneyStop.journey_id == journey.id)
        )

        # Deduplicate stops by station code (NJT API sometimes returns duplicates)
        api_stops = train_data.STOPS
        station_codes = [s.STATION_2CHAR for s in api_stops if s.STATION_2CHAR]
        duplicate_stations = {c for c in station_codes if station_codes.count(c) > 1}
        if duplicate_stations:
            logger.warning(
                "api_response_contains_duplicate_stations",
                train_id=journey.train_id,
                journey_id=journey.id,
                duplicates=list(duplicate_stations),
                total_stops=len(api_stops),
            )
            seen: set[str] = set()
            filtered = []
            for s in api_stops:
                if s.STATION_2CHAR not in seen:
                    seen.add(s.STATION_2CHAR)
                    filtered.append(s)
            api_stops = filtered

        # Add all the stops from the API
        stops = []
        for idx, stop in enumerate(api_stops):
            # Parse times
            scheduled_arrival = (
                parse_njt_time(stop.SCHED_ARR_DATE) if stop.SCHED_ARR_DATE else None
            )
            scheduled_departure = (
                parse_njt_time(stop.SCHED_DEP_DATE) if stop.SCHED_DEP_DATE else None
            )

            # Create stop record. TRACK must be sanitized — NJT serves
            # >5-char values (e.g. "Millstone Running") and a raw write
            # overflows the String(5) column, failing this train's whole
            # stop list once daily (issue #1508).
            sanitized_track = sanitize_track(stop.TRACK)
            journey_stop = JourneyStop(
                journey=journey,
                station_code=stop.STATION_2CHAR,
                station_name=stop.STATIONNAME,
                stop_sequence=idx,
                scheduled_arrival=scheduled_arrival,
                scheduled_departure=scheduled_departure,
                track=sanitized_track,
                track_assigned_at=now_et() if sanitized_track else None,
                has_departed_station=False,
            )

            stops.append(journey_stop)
            session.add(journey_stop)

        # Update journey metadata
        if stops:
            journey.has_complete_journey = True
            journey.stops_count = len(stops)
            journey.origin_station_code = stops[0].station_code
            journey.terminal_station_code = stops[-1].station_code

            # Update scheduled times from first/last stops
            if stops[0].scheduled_departure:
                journey.scheduled_departure = stops[0].scheduled_departure
            if stops[-1].scheduled_arrival:
                journey.scheduled_arrival = stops[-1].scheduled_arrival

            journey.last_updated_at = now_et()
            journey.update_count = (journey.update_count or 0) + 1

        await session.flush()
