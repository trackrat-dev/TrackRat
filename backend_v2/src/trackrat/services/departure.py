"""
Departure service for handling train departure queries.
"""

import time
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from trackrat.collectors.njt.client import NJTransitClient, TrainNotFoundError
from trackrat.collectors.njt.journey import JourneyCollector as NJTJourneyCollector
from trackrat.config.stations import expand_station_codes, get_station_name
from trackrat.db.engine import retry_on_deadlock
from trackrat.models.api import (
    DataFreshness,
    DeparturesResponse,
    LineInfo,
    StationInfo,
    TrainDeparture,
    TrainPosition,
)
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.sanitize import sanitize_track
from trackrat.utils.time import (
    DATETIME_MAX_ET,
    normalize_to_et,
    now_et,
    parse_njt_time,
    safe_datetime_subtract,
)
from trackrat.utils.train import get_effective_observation_type

logger = get_logger(__name__)

# NJT line code normalization for deduplication.
# Canonical codes are uppercase (NE, NC, GL, MO, MA, etc.) matching route_topology.py.
# This map handles old mixed-case codes from pre-2026-03 collectors and DB records.
NJT_LINE_CANONICALIZATION: dict[str, str] = {
    "Ra": "RV",
    "Gl": "GL",
    "Mo": "MO",
    "Ma": "MA",
    "Be": "BE",
    "Pa": "PV",
    "At": "AC",
    "Pr": "PR",
    "No": "NE",  # Legacy truncation artifact
}

# Data sources that have real-time discovery systems.
# SCHEDULED trains from these sources should be hidden when close to departure
# if they haven't been upgraded to OBSERVED by discovery.
REAL_TIME_DATA_SOURCES: frozenset[str] = frozenset(
    {"NJT", "AMTRAK", "PATH", "LIRR", "MNR", "SUBWAY"}
)

# Minutes before departure to hide SCHEDULED trains that weren't discovered.
# If a train hasn't been OBSERVED by this point, it's likely not running
# or we can't provide reliable information about it.
# Must be less than the discovery interval (30min) so SCHEDULED trains remain
# visible for at least one discovery cycle before being filtered out.
SCHEDULED_VISIBILITY_THRESHOLD_MINUTES: int = 15


class DepartureService:
    """Service for handling departure queries and processing."""

    async def get_departures(
        self,
        db: AsyncSession,
        from_station: str,
        to_station: str | None = None,
        date: date | None = None,
        time_from: datetime | None = None,
        time_to: datetime | None = None,
        limit: int = 50,
        hide_departed: bool = False,
        data_sources: list[str] | None = None,
        skip_individual_refresh: bool = False,
    ) -> DeparturesResponse:
        """Get train departures between stations.

        For future dates (> today), queries GTFS static schedule data.
        For today or past dates, uses real-time TrainJourney data.
        """
        today = now_et().date()
        target_date = date or today

        # For future dates, use GTFS static schedule data
        if target_date > today:
            from trackrat.services.gtfs import GTFSService

            gtfs_service = GTFSService()
            logger.info(
                "Using GTFS for future date",
                target_date=str(target_date),
                from_station=from_station,
                to_station=to_station,
            )
            response = await gtfs_service.get_scheduled_departures(
                db=db,
                from_station=from_station,
                to_station=to_station,
                target_date=target_date,
                limit=limit,
                data_sources=data_sources,
            )
            if data_sources:
                response.departures = [
                    d for d in response.departures if d.data_source in data_sources
                ]
                response.metadata["count"] = len(response.departures)
            return response

        # For today or past dates, use real-time data
        # Set default time range
        if time_from is None:
            query_date = date or now_et().date()
            # Fix timezone bug: ensure time_from is timezone-aware in ET
            from trackrat.utils.time import ET

            time_from = ET.localize(datetime.combine(query_date, datetime.min.time()))
        else:
            # Ensure provided time_from is timezone-aware
            from trackrat.utils.time import ensure_timezone_aware

            time_from = ensure_timezone_aware(time_from)

        if time_to is None:
            # Extend window to 26 hours to handle edge cases:
            # - Tests that create data up to 2 hours in the future
            # - Overnight journeys that cross date boundaries
            time_to = time_from + timedelta(hours=26)
        else:
            # Ensure provided time_to is timezone-aware
            from trackrat.utils.time import ensure_timezone_aware

            time_to = ensure_timezone_aware(time_to)

        # Query journeys from both NJT and Amtrak data sources
        # Determine journey_date filter based on whether a specific date was provided
        if date:
            # If a specific date was provided, use it exactly
            journey_date_filter = TrainJourney.journey_date == date
        else:
            # For time-based queries, include a range to handle:
            # - Overnight journeys that cross date boundaries
            # - Multi-day Amtrak journeys
            # - Tests that create data slightly in the future
            journey_date_filter = and_(
                TrainJourney.journey_date >= (time_from.date() - timedelta(days=2)),
                TrainJourney.journey_date <= (time_to.date() + timedelta(days=1)),
            )

        # Determine the target date for prioritization
        target_date = date if date else now_et().date()

        # Build additional filters for hide_departed and data_sources
        # Default to all data sources if not specified
        allowed_sources = (
            data_sources
            if data_sources
            else ["NJT", "AMTRAK", "PATH", "PATCO", "LIRR", "MNR", "SUBWAY"]
        )

        departure_filters = [
            JourneyStop.scheduled_departure >= time_from,
            JourneyStop.scheduled_departure <= time_to,
            journey_date_filter,
            # Filter by selected data sources
            TrainJourney.data_source.in_(allowed_sources),
            # Filter out expired trains (no longer in real-time feed)
            TrainJourney.is_expired.is_not(True),
            # Filter out completed trains (journey finished)
            TrainJourney.is_completed.is_not(True),
        ]

        # PERFORMANCE: Filter out trains that have already departed from origin station
        # This reduces payload size significantly when using hide_departed=true
        # Show cancelled trains for up to 2 hours past their scheduled departure —
        # users need to see recent cancellations, but not stale ones from hours ago
        if hide_departed:
            departure_filters.append(
                or_(
                    JourneyStop.has_departed_station.is_(False),
                    and_(
                        TrainJourney.is_cancelled.is_(True),
                        JourneyStop.scheduled_departure >= now_et() - timedelta(hours=2),
                    ),
                )
            )

        # PERFORMANCE: Track timing for observability
        perf_start = time.perf_counter()

        # Ensure fresh data for NJT trains BEFORE querying, so the query returns
        # up-to-date departure times. This prevents stale data from causing
        # incorrect delay calculations in the response.
        # Skip when NJT is not in the requested data sources — the NJT JIT
        # refresh makes an external API call that's irrelevant for other providers.
        jit_start = time.perf_counter()
        if "NJT" in allowed_sources:
            try:
                await self._ensure_fresh_station_data(
                    db,
                    from_station,
                    target_date,
                    skip_individual_refresh,
                    hide_departed,
                )
            except Exception as e:
                logger.warning(
                    "jit_refresh_failed_serving_stale",
                    station_code=from_station,
                    error=str(e),
                )
                try:
                    await db.rollback()
                except Exception:
                    pass
        jit_duration_ms = (time.perf_counter() - jit_start) * 1000

        query_start = time.perf_counter()
        from_codes = expand_station_codes(from_station)
        to_codes = expand_station_codes(to_station) if to_station else []

        stmt = (
            select(TrainJourney)
            .join(
                JourneyStop,
                and_(
                    JourneyStop.journey_id == TrainJourney.id,
                    JourneyStop.station_code.in_(from_codes),
                ),
            )
            .where(and_(*departure_filters))
            .options(selectinload(TrainJourney.stops))
            .order_by(
                # Prioritize trains with the target journey_date
                case((TrainJourney.journey_date == target_date, 0), else_=1),
                # Then order by scheduled departure time
                JourneyStop.scheduled_departure,
            )
            # Don't limit the SQL query - we need all trains to filter properly
            # We'll apply the limit after filtering for valid routes
        )

        result = await db.execute(stmt)
        journeys = list(result.scalars().unique().all())
        query_duration_ms = (time.perf_counter() - query_start) * 1000
        journeys_loaded = len(journeys)

        # Deduplicate by train_id to handle cases where the same train appears
        # with different journey_dates (e.g., stale records from previous days).
        # The SQL query already orders by target_date priority, so keeping the
        # first occurrence of each train_id gives us the most relevant record.
        seen_train_ids: set[str] = set()
        unique_journeys = []
        for journey in journeys:
            train_id = journey.train_id
            if train_id and train_id not in seen_train_ids:
                seen_train_ids.add(train_id)
                unique_journeys.append(journey)
        journeys = unique_journeys

        # Build departures list
        departures = []
        for journey in journeys:
            # Find from and to stops
            from_stop = None
            to_stop = None
            for stop in sorted(journey.stops, key=lambda s: s.stop_sequence or 0):
                if stop.station_code in from_codes and not from_stop:
                    from_stop = stop
                elif to_station and stop.station_code in to_codes and from_stop:
                    # Ensure to_stop comes AFTER from_stop in the journey sequence
                    if (stop.stop_sequence or 0) > (from_stop.stop_sequence or 0):
                        to_stop = stop
                        break

            # Skip if stops not found
            if not from_stop or (to_station and not to_stop):
                continue

            # Calculate train position
            train_position = self._calculate_train_position(journey)

            # Build departure
            departure = TrainDeparture(
                train_id=journey.train_id,
                journey_date=journey.journey_date,
                line=LineInfo(
                    code=journey.line_code or "UNK",
                    name=journey.line_name or journey.line_code or "Unknown",
                    color=(journey.line_color or "#000000").strip(),
                ),
                destination=journey.destination,
                departure=StationInfo(
                    code=from_station,
                    name=get_station_name(from_station),
                    scheduled_time=from_stop.scheduled_departure
                    or from_stop.scheduled_arrival,
                    updated_time=from_stop.updated_departure
                    or from_stop.updated_arrival,
                    actual_time=from_stop.actual_departure or from_stop.actual_arrival,
                    track=from_stop.track,
                ),
                arrival=(
                    StationInfo(
                        code=to_station,
                        name=get_station_name(to_station),
                        scheduled_time=to_stop.scheduled_arrival
                        or to_stop.scheduled_departure,
                        updated_time=to_stop.updated_arrival
                        or to_stop.updated_departure,
                        actual_time=to_stop.actual_arrival or to_stop.actual_departure,
                        track=to_stop.track,
                    )
                    if to_stop and to_station
                    else None
                ),
                train_position=train_position,
                data_freshness=DataFreshness(
                    last_updated=journey.last_updated_at or journey.first_seen_at,
                    age_seconds=int(
                        safe_datetime_subtract(
                            now_et(),
                            journey.last_updated_at
                            or journey.first_seen_at
                            or now_et(),
                        ).total_seconds()
                    ),
                    update_count=journey.update_count,
                ),
                data_source=journey.data_source,
                observation_type=get_effective_observation_type(journey),
                is_cancelled=journey.is_cancelled,
                cancellation_reason=journey.cancellation_reason,
                is_expired=journey.is_expired or False,
            )
            departures.append(departure)

        # PERFORMANCE: Log timing and result set metrics for observability
        total_duration_ms = (time.perf_counter() - perf_start) * 1000
        logger.info(
            "departures_query_complete",
            from_station=from_station,
            to_station=to_station,
            hide_departed=hide_departed,
            jit_refresh_ms=round(jit_duration_ms, 1),
            query_ms=round(query_duration_ms, 1),
            total_ms=round(total_duration_ms, 1),
            journeys_loaded=journeys_loaded,
            journeys_returned=len(departures),
            skip_individual_refresh=skip_individual_refresh,
        )

        # For TODAY: merge real-time departures with GTFS schedule for rest of day
        # This shows trains that haven't entered the real-time feed yet
        if target_date == today:
            current_time = now_et()
            try:
                from trackrat.services.gtfs import GTFSService

                gtfs_service = GTFSService()

                gtfs_response = await gtfs_service.get_scheduled_departures(
                    db=db,
                    from_station=from_station,
                    to_station=to_station,
                    target_date=target_date,
                    limit=200,  # Fetch more, we'll filter after merge
                    data_sources=allowed_sources,
                )

                # Filter GTFS departures:
                # 1. Must be in the future (after current time)
                # 2. PATH trains: Only include if beyond dynamic cutoff window.
                #    Cutoff = max(now + 20min, last_observed_departure + 2min).
                #    This prevents duplicates while showing schedules until realtime
                #    data reliably covers them.
                path_cutoff_time = await self._get_path_cutoff_time(
                    db, from_station, current_time, target_date
                )
                gtfs_future = [
                    dep
                    for dep in gtfs_response.departures
                    if dep.departure.scheduled_time
                    and dep.departure.scheduled_time > current_time
                    and dep.data_source in allowed_sources
                    and (
                        # Non-PATH: include all future departures
                        dep.data_source != "PATH"
                        # PATH: only include if beyond cutoff window
                        or dep.departure.scheduled_time > path_cutoff_time
                    )
                ]

                departures = self._merge_departures(
                    realtime=departures,
                    gtfs=gtfs_future,
                )
            except Exception as e:
                # GTFS merge failed - log warning but return real-time results
                logger.warning(
                    "gtfs_merge_failed",
                    from_station=from_station,
                    to_station=to_station,
                    error=str(e),
                )

            # Filter out SCHEDULED trains that are close to departure but weren't
            # discovered by the real-time system. Only applies to systems with
            # real-time data (NJT, Amtrak, PATH) - not PATCO which is schedule-only.
            departures = self._filter_stale_scheduled_trains(departures, current_time)

        # Apply limit to departures
        limited_departures = departures[:limit]

        return DeparturesResponse(
            departures=limited_departures,
            metadata={
                "from_station": {
                    "code": from_station,
                    "name": get_station_name(from_station),
                },
                "to_station": (
                    {"code": to_station, "name": get_station_name(to_station)}
                    if to_station
                    else None
                ),
                "count": len(limited_departures),
                "generated_at": now_et().isoformat(),
            },
        )

    def _calculate_train_position(self, journey: TrainJourney) -> TrainPosition:
        """
        Calculate current train position.

        OPTIMIZATION: Uses journey_progress table when available to avoid
        iterating through stops. Falls back to stops-based calculation only
        when progress data is not available.
        """
        from sqlalchemy import inspect
        from sqlalchemy.orm.base import NO_VALUE

        from trackrat.models.database import JourneyProgress

        # OPTIMIZATION: Use pre-computed journey_progress if available
        # Use inspect to check if relationship is loaded without triggering lazy load
        state = inspect(journey)

        # Check if progress relationship is loaded and get its value
        progress_value = state.attrs.progress.loaded_value if state else NO_VALUE

        # If progress is loaded and not None, use it (with type guard)
        if (
            progress_value is not NO_VALUE
            and progress_value is not None
            and isinstance(progress_value, JourneyProgress)
        ):
            # Journey progress table has the position already computed
            return TrainPosition(
                last_departed_station_code=progress_value.last_departed_station,
                at_station_code=None,  # Progress doesn't track "at station" state
                next_station_code=progress_value.next_station,
                between_stations=(
                    progress_value.last_departed_station is not None
                    and progress_value.next_station is not None
                ),
            )

        # Fallback: Calculate from stops if progress not available.
        # Guard against lazy-load in sync context — if stops weren't eagerly
        # loaded, return empty position rather than triggering MissingGreenlet.
        stops_value = state.attrs.stops.loaded_value if state else NO_VALUE
        if stops_value is NO_VALUE or not journey.stops:
            return TrainPosition()

        # Sort stops by sequence
        sorted_stops = sorted(journey.stops, key=lambda s: s.stop_sequence or 0)

        # Find last departed station and next station
        last_departed_station_code = None
        at_station_code = None
        next_station_code = None

        for stop in sorted_stops:
            if stop.has_departed_station:
                last_departed_station_code = stop.station_code
            else:
                # This is the next station
                next_station_code = stop.station_code

                # Check if currently at this station (based on raw status)
                if journey.data_source == "AMTRAK":
                    # For Amtrak, "Station" means at the station
                    if stop.raw_amtrak_status == "Station":
                        at_station_code = stop.station_code
                elif journey.data_source == "NJT":
                    # For NJT, having a track assignment suggests at station
                    if stop.track and not stop.has_departed_station:
                        at_station_code = stop.station_code
                # PATH/LIRR/MNR: GTFS-RT API doesn't provide at-station status,
                # so we rely on has_departed_station only

                break

        # If no undeparted stops found, train may have completed journey
        if not next_station_code and sorted_stops:
            last_stop = sorted_stops[-1]
            if last_stop.has_departed_station:
                at_station_code = last_stop.station_code

        return TrainPosition(
            last_departed_station_code=last_departed_station_code,
            at_station_code=at_station_code,
            next_station_code=next_station_code,
            between_stations=(
                last_departed_station_code is not None
                and at_station_code is None
                and next_station_code is not None
            ),
        )

    async def _get_path_cutoff_time(
        self,
        db: AsyncSession,
        station_code: str,
        current_time: datetime,
        journey_date: date,
    ) -> datetime:
        """Calculate dynamic cutoff for PATH scheduled trains.

        Returns max(now + 20min, last_observed_departure + 2min).
        This ensures we show scheduled trains until realtime data
        reliably covers them, while avoiding duplicates once realtime
        trains are observed.
        """
        min_cutoff = current_time + timedelta(minutes=20)

        # Find the latest scheduled departure among observed PATH trains at this station
        result = await db.execute(
            select(func.max(JourneyStop.scheduled_departure))
            .join(TrainJourney, JourneyStop.journey_id == TrainJourney.id)
            .where(
                TrainJourney.data_source == "PATH",
                TrainJourney.observation_type == "OBSERVED",
                TrainJourney.journey_date == journey_date,
                JourneyStop.station_code.in_(expand_station_codes(station_code)),
                JourneyStop.scheduled_departure > current_time,
            )
        )
        last_observed = result.scalar()

        if last_observed is None:
            return min_cutoff

        observed_cutoff = last_observed + timedelta(minutes=2)
        return max(min_cutoff, observed_cutoff)

    async def _ensure_fresh_station_data(
        self,
        db: AsyncSession,
        station_code: str,
        target_date: date,
        skip_individual_refresh: bool = False,
        hide_departed: bool = False,
    ) -> None:
        """Ensure station departure data is fresh using getTrainSchedule with embedded stops.

        Args:
            db: Database session
            station_code: Station to refresh
            target_date: Date to filter journeys
            skip_individual_refresh: If True, skip the second pass that individually
                refreshes stale trains. Used during cache precomputation to avoid
                excessive API calls.
            hide_departed: If True, skip refreshing past trains since they won't be
                shown in the response anyway.
        """

        # Check if station data needs refresh (60 second staleness)
        cutoff_time = now_et() - timedelta(seconds=60)

        needs_refresh = await db.scalar(
            select(TrainJourney.id)
            .join(JourneyStop, JourneyStop.journey_id == TrainJourney.id)
            .where(
                and_(
                    JourneyStop.station_code.in_(expand_station_codes(station_code)),
                    TrainJourney.data_source == "NJT",
                    TrainJourney.journey_date == target_date,
                    TrainJourney.last_updated_at < cutoff_time,
                    TrainJourney.is_expired.is_not(True),
                    TrainJourney.is_completed.is_not(True),
                    TrainJourney.is_cancelled.is_not(True),
                )
            )
            .limit(1)
        )

        if not needs_refresh:
            logger.debug("station_data_fresh", station_code=station_code)
            return

        logger.info("refreshing_station_data", station_code=station_code)

        # Refresh entire station using getTrainSchedule (with embedded STOPS)
        njt_client = NJTransitClient()
        try:
            schedule_data = await njt_client.get_train_schedule_with_stops(station_code)

            train_items = schedule_data.get("ITEMS") or []
            logger.info(
                "station_refresh_retrieved",
                station_code=station_code,
                train_count=len(train_items),
            )

            # Extract all train IDs for bulk loading
            train_ids = []
            for train_data in train_items:
                if train_id := train_data.get("TRAIN_ID"):
                    train_ids.append(train_id)

            if not train_ids:
                logger.info(
                    "station_refresh_complete",
                    station_code=station_code,
                    updated_trains=0,
                )
                # Don't return early - still need to check for stale journeys
                # that weren't in the bulk refresh (second pass)
            else:

                async def _do_bulk_refresh() -> int:
                    """Bulk refresh journeys, retryable on deadlock.

                    Re-queries fresh state on each attempt since rollback
                    clears the session.
                    """
                    stmt = (
                        select(TrainJourney)
                        .where(
                            and_(
                                TrainJourney.train_id.in_(train_ids),
                                TrainJourney.journey_date == now_et().date(),
                                TrainJourney.data_source == "NJT",
                            )
                        )
                        .options(selectinload(TrainJourney.stops))
                        .order_by(TrainJourney.id)
                    )
                    result = await db.execute(stmt)
                    journeys_by_id = {j.train_id: j for j in result.scalars().all()}

                    count = 0
                    for train_data in train_items:
                        train_id = train_data.get("TRAIN_ID")
                        if not train_id:
                            continue

                        # Check if this is an Amtrak train appearing in NJT station data
                        is_amtrak = train_id.startswith("A") and train_id[1:].isdigit()

                        journey = journeys_by_id.get(train_id)
                        if not journey:
                            # Train in NJT schedule API without a journey record —
                            # expected for undiscovered or cancelled trains
                            if not is_amtrak:
                                logger.debug(
                                    "journey_not_found_during_station_refresh",
                                    train_id=train_id,
                                    station_code=station_code,
                                )
                            else:
                                logger.debug(
                                    "amtrak_train_in_njt_station",
                                    train_id=train_id,
                                    station_code=station_code,
                                    reason="Amtrak trains appear in NJT stations but are tracked separately",
                                )
                            continue

                        # Update journey metadata
                        journey.destination = train_data.get(
                            "DESTINATION", journey.destination
                        )

                        # Clean color value (remove trailing spaces)
                        if backcolor := train_data.get("BACKCOLOR"):
                            journey.line_color = backcolor.strip()
                        journey.last_updated_at = now_et()
                        journey.update_count = (journey.update_count or 0) + 1

                        # Update stops from embedded STOPS data
                        stops_data = train_data.get("STOPS") or []
                        if stops_data:
                            await self._update_stops_from_embedded_data(
                                db, journey, stops_data
                            )
                            journey.has_complete_journey = True
                            journey.stops_count = len(stops_data)

                            # Update origin/terminal/scheduled_departure from stops
                            # This fixes journeys discovered at intermediate stations
                            first_stop = stops_data[0]
                            last_stop = stops_data[-1]

                            if first_station := first_stop.get("STATION_2CHAR"):
                                journey.origin_station_code = first_station
                            if last_station := last_stop.get("STATION_2CHAR"):
                                journey.terminal_station_code = last_station
                            if first_dep := first_stop.get("DEP_TIME"):
                                journey.scheduled_departure = parse_njt_time(first_dep)
                            if last_arr := last_stop.get("TIME"):
                                journey.scheduled_arrival = parse_njt_time(last_arr)

                        logger.debug(
                            "journey_updated_from_schedule",
                            train_id=train_id,
                            stops_count=len(stops_data),
                        )
                        count += 1

                    await db.commit()
                    return count

                updated_count = await retry_on_deadlock(db, _do_bulk_refresh)
                logger.info(
                    "station_refresh_complete",
                    station_code=station_code,
                    updated_trains=updated_count,
                )

            # Skip second pass if requested (e.g., during cache precomputation)
            # or if hiding departed trains (past trains won't be shown anyway)
            # This prevents excessive API calls when bulk refresh is sufficient
            if skip_individual_refresh or hide_departed:
                logger.debug(
                    "skipping_individual_refresh",
                    station_code=station_code,
                    reason=(
                        "skip_individual_refresh=True"
                        if skip_individual_refresh
                        else "hide_departed=True"
                    ),
                )
                return

            # Second pass: Refresh any remaining stale journeys individually.
            # getTrainSchedule only returns upcoming trains, so trains past their
            # scheduled departure time won't be refreshed by the bulk update above.
            # For these, we use getTrainStopList which works for any train.
            #
            # CRITICAL: Filter by target_date to avoid loading historical data.
            # Without this, we'd load all stale journeys going back days/weeks,
            # causing OOM at busy stations like NY Penn.
            remaining_stale_result = await db.execute(
                select(TrainJourney)
                .join(JourneyStop, JourneyStop.journey_id == TrainJourney.id)
                .where(
                    and_(
                        JourneyStop.station_code.in_(
                            expand_station_codes(station_code)
                        ),
                        TrainJourney.data_source == "NJT",
                        TrainJourney.journey_date == target_date,
                        TrainJourney.last_updated_at < cutoff_time,
                        TrainJourney.is_expired.is_not(True),
                        TrainJourney.is_completed.is_not(True),
                        TrainJourney.is_cancelled.is_not(True),
                    )
                )
                # Eagerly load stops to prevent greenlet errors during
                # commit's cascade="all, delete-orphan" orphan check
                .options(selectinload(TrainJourney.stops))
                .limit(50)
            )
            remaining_stale = list(remaining_stale_result.scalars().unique().all())

            if remaining_stale:
                logger.info(
                    "refreshing_stale_past_trains",
                    station_code=station_code,
                    count=len(remaining_stale),
                    train_ids=[j.train_id for j in remaining_stale],
                )

                # Use the journey collector for individual train refresh
                njt_collector = NJTJourneyCollector(njt_client)
                individual_updated = 0

                for journey in remaining_stale:
                    if journey.id is None:
                        continue
                    journey_id = journey.id

                    async def refresh_journey(jid: int = journey_id) -> None:
                        # Re-query to get fresh state after potential rollback.
                        # Default param captures journey_id at definition time.
                        # Use explicit query instead of db.get() because get()
                        # returns from identity map without applying selectinload
                        # when the object was already loaded by the query above.
                        result = await db.execute(
                            select(TrainJourney)
                            .where(TrainJourney.id == jid)
                            .options(selectinload(TrainJourney.stops))
                            .execution_options(populate_existing=True)
                        )
                        fresh = result.scalar_one_or_none()
                        if fresh:
                            await njt_collector.collect_journey_details(db, fresh)

                    try:
                        await retry_on_deadlock(db, refresh_journey)
                        individual_updated += 1
                        logger.debug(
                            "stale_train_refreshed",
                            train_id=journey.train_id,
                        )
                    except TrainNotFoundError:
                        # Train no longer in NJT system - this is expected for
                        # trains that completed their journey
                        logger.debug(
                            "stale_train_not_found",
                            train_id=journey.train_id,
                        )
                    except Exception as e:
                        logger.warning(
                            "stale_train_refresh_failed",
                            train_id=journey.train_id,
                            error=str(e),
                        )

                await db.commit()
                logger.info(
                    "stale_past_trains_refresh_complete",
                    station_code=station_code,
                    updated=individual_updated,
                    total=len(remaining_stale),
                )

        except Exception as e:
            logger.error(
                "station_refresh_failed", station_code=station_code, error=str(e)
            )
            try:
                await db.rollback()
            except Exception:
                pass
            raise
        finally:
            await njt_client.close()

    async def _update_stops_from_embedded_data(
        self,
        session: AsyncSession,
        journey: TrainJourney,
        stops_data: list[dict[str, Any]],
    ) -> None:
        """Update journey stops from embedded STOPS data in getTrainSchedule response.

        Uses PostgreSQL ON CONFLICT to safely handle concurrent updates from
        multiple sessions (e.g., cache precomputation vs user request).
        """

        # First pass: find the furthest departed stop for sequential inference.
        # NJT's DEPARTED flag is inconsistent across API calls — a later stop
        # can show DEPARTED=YES while an earlier one shows NO, even though the
        # train must have passed the earlier stop.
        max_departed_idx = -1
        for idx, sd in enumerate(stops_data):
            if (sd.get("DEPARTED") or "").upper() == "YES":
                max_departed_idx = max(max_departed_idx, idx)

        for i, stop_data in enumerate(stops_data):
            station_code = stop_data.get("STATION_2CHAR")
            if not station_code:
                continue

            # Upsert: insert or fetch existing stop (race-safe)
            stmt = (
                pg_insert(JourneyStop)
                .values(
                    journey_id=journey.id,
                    station_code=station_code,
                    station_name=stop_data.get("STATIONNAME", ""),
                    stop_sequence=i,
                )
                .on_conflict_do_nothing(constraint="unique_journey_stop")
                .returning(JourneyStop.id)
            )
            result = await session.execute(stmt)
            inserted_id = result.scalar_one_or_none()

            if inserted_id:
                # New row inserted — fetch the ORM object
                stop = await session.get(JourneyStop, inserted_id)
            else:
                # Already existed — fetch by unique key
                existing = await session.execute(
                    select(JourneyStop).where(
                        JourneyStop.journey_id == journey.id,
                        JourneyStop.station_code == station_code,
                    )
                )
                stop = existing.scalar_one()

            assert stop is not None  # Just inserted or fetched by unique key

            # Update stop data from schedule
            if arrival_time_str := stop_data.get("TIME"):
                stop.scheduled_arrival = parse_njt_time(arrival_time_str)

            if departure_time_str := stop_data.get("DEP_TIME"):
                stop.scheduled_departure = parse_njt_time(departure_time_str)

            # Update departure status with time validation
            departed = (stop_data.get("DEPARTED") or "").upper() or None
            stop.raw_njt_departed_flag = departed

            # Cancelled stops never physically departed
            stop_status = (stop_data.get("STOP_STATUS") or "").upper()
            is_stop_cancelled = stop_status == "CANCELLED"

            if is_stop_cancelled:
                if not stop.has_departed_station:
                    stop.has_departed_station = False
            # Never mark as departed if scheduled departure is in the future
            # This prevents stale NJT data from incorrectly marking future trains as departed
            elif stop.scheduled_departure and stop.scheduled_departure > now_et():
                stop.has_departed_station = False
                if departed == "YES":
                    logger.debug(
                        "overriding_future_departure_flag",
                        station_code=station_code,
                        train_id=journey.train_id,
                        scheduled_departure=stop.scheduled_departure.isoformat(),
                        njt_flag=departed,
                    )
            elif departed == "YES":
                stop.has_departed_station = True
                # Set actual_departure if not already set
                # Use arrival time (live estimate from TIME field) or scheduled departure
                if stop.actual_departure is None:
                    stop.actual_departure = (
                        stop.scheduled_arrival or stop.scheduled_departure
                    )
            elif i < max_departed_idx:
                # Sequential inference: a later stop has DEPARTED=YES,
                # so this earlier stop must have departed too.
                stop.has_departed_station = True
                if stop.actual_departure is None:
                    stop.actual_departure = (
                        stop.scheduled_arrival or stop.scheduled_departure
                    )
            else:
                # Not departed — but never revert a stop previously marked
                # as departed (NJT API DEPARTED flag is inconsistent)
                if not stop.has_departed_station:
                    stop.has_departed_station = False

            # Update stop sequence if not set
            if stop.stop_sequence is None:
                stop.stop_sequence = i

            # Update track if available in embedded data
            track = stop_data.get("TRACK")
            if track:
                sanitized_track = sanitize_track(track)
                if sanitized_track and sanitized_track != stop.track:
                    old_track = stop.track
                    stop.track = sanitized_track
                    if not stop.track_assigned_at:
                        stop.track_assigned_at = now_et()
                    logger.debug(
                        "station_refresh_track_update",
                        train_id=journey.train_id,
                        station_code=station_code,
                        old_track=old_track,
                        new_track=sanitized_track,
                    )

    def _normalize_line_code(self, line_code: str, data_source: str) -> str:
        """Normalize line code to canonical form for deduplication.

        NJT line codes can vary between real-time API and GTFS:
        - Schedule API full names truncated to "No" (fixed at source, safety net here)
        - API "Raritan Valley" -> "RV", but GTFS maps RARV -> "Ra"
        """
        if data_source == "NJT":
            return NJT_LINE_CANONICALIZATION.get(line_code, line_code)
        return line_code

    def _make_dedup_keys(self, dep: TrainDeparture) -> tuple[str | None, list[str]]:
        """Create primary (train_id) and fallback (line+time) dedup keys.

        Returns:
            Tuple of (primary_key, fallback_keys) where:
            - primary_key may be None if train_id is missing or unreliable
            - fallback_keys is a list of keys for the current time ±1 minute
              to handle minor schedule differences between sources
        """
        # Primary: normalized train_id
        primary_key = None
        if dep.train_id and dep.train_id not in ("Unknown", ""):
            train_id = dep.train_id
            # Normalize Amtrak IDs: "A2205" → "2205" for matching with GTFS
            if dep.data_source == "AMTRAK":
                train_id = train_id.lstrip("A")
            primary_key = f"{train_id}:{dep.journey_date}:{dep.data_source}"

        # Fallback: line + scheduled time with tolerance
        # - Normalize line codes to handle NJT API inconsistencies
        # - Generate keys for ±1 minute to handle minor time differences
        # - Normalize to ET to handle timezone differences between data sources
        line_code = self._normalize_line_code(dep.line.code, dep.data_source)
        scheduled = dep.departure.scheduled_time

        if scheduled:
            scheduled_et = normalize_to_et(scheduled)
            # Generate keys for current minute and adjacent minutes
            fallback_keys = []
            for minute_offset in [-1, 0, 1]:
                adj_time = scheduled_et + timedelta(minutes=minute_offset)
                time_str = adj_time.strftime("%H:%M")
                fallback_keys.append(f"{line_code}:{dep.data_source}:{time_str}")
        else:
            fallback_keys = [f"{line_code}:{dep.data_source}:unknown"]

        return primary_key, fallback_keys

    def _merge_departures(
        self,
        realtime: list[TrainDeparture],
        gtfs: list[TrainDeparture],
    ) -> list[TrainDeparture]:
        """Merge real-time and GTFS departures, preferring real-time.

        Deduplication uses two keys:
        1. Primary: normalized train_id (handles Amtrak A-prefix mismatch)
        2. Fallback: normalized line + time with ±1 minute tolerance

        Cancelled real-time trains suppress their GTFS counterparts.
        """
        # Build indexes from real-time departures
        primary_keys: set[str] = set()
        fallback_keys: set[str] = set()
        cancelled_primary: set[str] = set()
        cancelled_fallback: set[str] = set()

        for dep in realtime:
            primary, fallbacks = self._make_dedup_keys(dep)
            if primary:
                primary_keys.add(primary)
                if dep.is_cancelled:
                    cancelled_primary.add(primary)
            # Add all fallback keys (includes ±1 minute tolerance)
            fallback_keys.update(fallbacks)
            if dep.is_cancelled:
                cancelled_fallback.update(fallbacks)

        # Start with all real-time trains
        merged = list(realtime)
        gtfs_added = 0

        # Add GTFS trains not matched in real-time
        for gtfs_dep in gtfs:
            primary, fallbacks = self._make_dedup_keys(gtfs_dep)

            # Check primary key match
            if primary and primary in primary_keys:
                continue
            if primary and primary in cancelled_primary:
                continue

            # Check fallback key match - any of the fallback keys matching is sufficient
            if any(fb in fallback_keys for fb in fallbacks):
                continue
            if any(fb in cancelled_fallback for fb in fallbacks):
                continue

            # No match found - add GTFS train
            merged.append(gtfs_dep)
            gtfs_added += 1

        # Sort by scheduled departure time
        # Use timezone-aware constant for safe comparison with ET-localized times
        merged.sort(key=lambda d: d.departure.scheduled_time or DATETIME_MAX_ET)

        logger.info(
            "departures_merged",
            realtime_count=len(realtime),
            gtfs_added=gtfs_added,
            total=len(merged),
        )

        return merged

    def _filter_stale_scheduled_trains(
        self,
        departures: list[TrainDeparture],
        current_time: datetime,
    ) -> list[TrainDeparture]:
        """Remove SCHEDULED trains close to departure for real-time systems.

        If a train from a system with real-time discovery (NJT, Amtrak, PATH)
        hasn't been OBSERVED by the time it's about to depart, we don't have
        reliable data to show the user. The train is likely:
        - Not running (cancelled or schedule changed)
        - Not being reported by the real-time API
        - Based on stale/incorrect schedule data

        PATCO is excluded because it has no real-time API - schedule data is
        all we have.

        Args:
            departures: List of departures to filter
            current_time: Current time for threshold calculation

        Returns:
            Filtered list with stale SCHEDULED trains removed
        """
        threshold = current_time + timedelta(
            minutes=SCHEDULED_VISIBILITY_THRESHOLD_MINUTES
        )

        result = []
        filtered_count = 0

        for dep in departures:
            # Always show OBSERVED trains - we have real-time data
            if dep.observation_type == "OBSERVED":
                result.append(dep)
                continue

            # Always show SCHEDULED trains from systems without real-time data
            if dep.data_source not in REAL_TIME_DATA_SOURCES:
                result.append(dep)
                continue

            # For real-time systems: hide SCHEDULED trains if departure is imminent
            scheduled_time = dep.departure.scheduled_time
            if scheduled_time and scheduled_time < threshold:
                filtered_count += 1
                logger.debug(
                    "filtering_stale_scheduled_train",
                    train_id=dep.train_id,
                    data_source=dep.data_source,
                    scheduled_time=scheduled_time.isoformat(),
                    threshold=threshold.isoformat(),
                )
                continue

            result.append(dep)

        if filtered_count > 0:
            logger.info(
                "filtered_stale_scheduled_trains",
                count=filtered_count,
                threshold_minutes=SCHEDULED_VISIBILITY_THRESHOLD_MINUTES,
            )

        return result
