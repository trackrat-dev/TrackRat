"""
Departure service for handling train departure queries.
"""

import asyncio
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
from trackrat.collectors.njt.schedule import parse_njt_line_code
from trackrat.config.route_topology import find_route_for_segment
from trackrat.config.stations import expand_station_codes, get_station_name
from trackrat.db.engine import get_session, retry_on_deadlock
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
from trackrat.utils.train import (
    get_effective_observation_type,
    is_amtrak_train,
    is_njt_stop_cancelled,
)

logger = get_logger(__name__)

# Tracks station codes currently being refreshed in background tasks.
# Prevents duplicate concurrent JIT refreshes for the same station.
_refreshing_stations: set[str] = set()

# Strong references to background tasks to prevent GC before completion.
# asyncio.create_task only holds a weak reference; without this set, tasks
# can be silently garbage collected. See: https://docs.python.org/3/library/asyncio-task.html#creating-tasks
_background_tasks: set[asyncio.Task[None]] = set()

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
    {"NJT", "AMTRAK", "PATH", "LIRR", "MNR", "SUBWAY", "METRA", "WMATA", "BART", "MBTA"}
)

# Minutes before departure to hide SCHEDULED trains that weren't discovered.
# If a train hasn't been OBSERVED by this point, it's likely not running
# or we can't provide reliable information about it.
# Must be less than the discovery interval (30min) so SCHEDULED trains remain
# visible for at least one discovery cycle before being filtered out.
SCHEDULED_VISIBILITY_THRESHOLD_MINUTES: int = 15

# All supported data sources for departure queries.
ALL_DATA_SOURCES: list[str] = [
    "NJT",
    "AMTRAK",
    "PATH",
    "PATCO",
    "LIRR",
    "MNR",
    "SUBWAY",
    "METRA",
    "WMATA",
    "BART",
    "MBTA",
]


def _has_direct_route(
    from_station: str,
    to_station: str,
    data_sources: list[str],
) -> bool:
    """Check if any data source has a direct route between two stations.

    Also checks expanded station codes (equivalences) so that e.g. Amtrak's NRO
    and Metro-North's MNRC for New Rochelle are both considered.
    """
    from_codes = expand_station_codes(from_station)
    to_codes = expand_station_codes(to_station)
    for source in data_sources:
        for fc in from_codes:
            for tc in to_codes:
                if find_route_for_segment(source, fc, tc) is not None:
                    return True
    return False


def _detect_at_station(journey: TrainJourney) -> str | None:
    """
    Detect if a train is currently at a station based on provider-specific signals.

    For NJT: a track assignment on an undeparted stop means the train is at that station.
    For Amtrak: raw_amtrak_status == "Station" means the train is at that station.
    For completed journeys: the train is at its final stop.

    Returns the station code if the train is at a station, else None.
    """
    if not journey.stops:
        return None

    sorted_stops = sorted(journey.stops, key=lambda s: s.stop_sequence or 0)

    next_station_found = False
    for stop in sorted_stops:
        if stop.has_departed_station:
            continue

        # This is the first undeparted stop (next station)
        next_station_found = True

        if journey.data_source == "AMTRAK":
            if stop.raw_amtrak_status == "Station":
                return stop.station_code
        elif journey.data_source == "NJT":
            if stop.track and not stop.has_departed_station:
                return stop.station_code
        # PATH/LIRR/MNR/Subway/BART/MBTA/Metra/WMATA: no at-station signal
        break

    # If no undeparted stops, train may have completed its journey
    if not next_station_found and sorted_stops:
        last_stop = sorted_stops[-1]
        if last_stop.has_departed_station:
            return last_stop.station_code

    return None


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
        skip_gtfs_merge: bool = False,
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
            from trackrat.utils.time import ensure_timezone_aware

            gtfs_service = GTFSService()
            logger.info(
                "Using GTFS for future date",
                target_date=str(target_date),
                from_station=from_station,
                to_station=to_station,
            )
            # Normalize time_from to ET-aware so comparisons with parsed
            # GTFS times (always ET-aware) don't raise TypeError.
            aware_time_from = (
                ensure_timezone_aware(time_from) if time_from is not None else None
            )
            response = await gtfs_service.get_scheduled_departures(
                db=db,
                from_station=from_station,
                to_station=to_station,
                target_date=target_date,
                limit=limit,
                data_sources=data_sources,
                time_from=aware_time_from,
            )
            if data_sources:
                response.departures = [
                    d for d in response.departures if d.data_source in data_sources
                ]
                response.metadata["count"] = len(response.departures)
            if to_station:
                all_sources = data_sources or ALL_DATA_SOURCES
                response.has_direct_route = _has_direct_route(
                    from_station, to_station, all_sources
                )
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
        allowed_sources = data_sources if data_sources else ALL_DATA_SOURCES

        departure_filters = [
            JourneyStop.scheduled_departure >= time_from,
            JourneyStop.scheduled_departure <= time_to,
            journey_date_filter,
            # Filter by selected data sources
            TrainJourney.data_source.in_(allowed_sources),
            # Filter out expired trains (no longer in real-time feed),
            # but keep cancelled trains even if expired — they must remain
            # visible to match what the congestion endpoint counts.
            or_(
                TrainJourney.is_expired.is_not(True),
                TrainJourney.is_cancelled.is_(True),
            ),
            # Filter out completed trains (journey finished)
            TrainJourney.is_completed.is_not(True),
            # Filter out stale cancelled trains regardless of hide_departed.
            # Users need to see recent cancellations but not ones from hours ago.
            or_(
                TrainJourney.is_cancelled.is_not(True),
                JourneyStop.scheduled_departure >= now_et() - timedelta(hours=2),
            ),
        ]

        # PERFORMANCE: Filter out trains that have already departed from origin station
        # This reduces payload size significantly when using hide_departed=true.
        # Uses two strategies:
        # 1. has_departed_station flag (set by collectors via API/sequential/time inference)
        # 2. Time-based fallback: scheduled departure > 5 minutes ago
        #    This catches trains where has_departed_station wasn't updated (e.g.,
        #    JIT refresh skips the second pass, or collector hasn't run yet).
        # Cancelled trains are always shown (they have their own 2-hour window).
        if hide_departed:
            past_cutoff = now_et() - timedelta(minutes=5)
            departure_filters.append(
                or_(
                    # Train hasn't departed (normal case)
                    and_(
                        JourneyStop.has_departed_station.is_(False),
                        # Time-based fallback: even if flag isn't set, exclude
                        # trains whose scheduled departure is well past
                        or_(
                            JourneyStop.scheduled_departure.is_(None),
                            JourneyStop.scheduled_departure > past_cutoff,
                        ),
                    ),
                    # Always show cancelled trains
                    TrainJourney.is_cancelled.is_(True),
                )
            )

        # PERFORMANCE: Track timing for observability
        perf_start = time.perf_counter()

        # JIT refresh for NJT trains.  Normally non-blocking (background task),
        # but when SCHEDULED NJT trains are about to be hidden by the stale
        # filter, we run the refresh inline so the user sees them immediately.
        jit_start = time.perf_counter()
        jit_ran_inline = False
        if "NJT" in allowed_sources:
            if (
                target_date == today
                and from_station not in _refreshing_stations
                and await self._has_imminent_scheduled_njt(
                    db, from_station, target_date
                )
            ):
                jit_ran_inline = await self._run_inline_jit_refresh(
                    from_station,
                    target_date,
                    skip_individual_refresh,
                    hide_departed,
                )
            if not jit_ran_inline:
                await self._maybe_trigger_background_refresh(
                    db,
                    from_station,
                    target_date,
                    skip_individual_refresh,
                    hide_departed,
                )
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
                    # IMPORTANT: max() is required here due to NJT's inverted semantics.
                    # At NJT intermediate stops, updated_departure = original schedule
                    # (DEP_TIME) while updated_arrival = live delayed estimate (TIME).
                    # The schedule is typically earlier, so plain `or` would return it
                    # and hide delays. max() ensures we surface the delayed time.
                    # For non-NJT providers, both fields are live estimates so max()
                    # is harmless. See database.py JourneyStop model for full docs.
                    updated_time=(
                        max(from_stop.updated_departure, from_stop.updated_arrival)
                        if from_stop.updated_departure and from_stop.updated_arrival
                        else from_stop.updated_departure or from_stop.updated_arrival
                    ),
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
        # This shows trains that haven't entered the real-time feed yet.
        # Skip for transfer leg queries where GTFS backfill isn't needed.
        if target_date == today and not skip_gtfs_merge:
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
                if "PATH" in allowed_sources:
                    path_cutoff_time = await self._get_path_cutoff_time(
                        db, from_station, current_time, target_date
                    )
                else:
                    path_cutoff_time = current_time
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

        # Check if a direct route exists between the two stations
        has_direct_route = True
        if to_station:
            has_direct_route = _has_direct_route(
                from_station, to_station, allowed_sources
            )

        return DeparturesResponse(
            departures=limited_departures,
            has_direct_route=has_direct_route,
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

    async def get_recent_departures(
        self,
        db: AsyncSession,
        from_station: str,
        to_station: str | None = None,
        window_minutes: int = 120,
        limit: int = 50,
        data_sources: list[str] | None = None,
    ) -> DeparturesResponse:
        """Get recently-departed trains from a station.

        Returns trains whose scheduled departure from the origin station was
        within the last ``window_minutes``, including cancellations and
        completed journeys. Sorted by scheduled departure, most recent first.

        Unlike ``get_departures``, this intentionally bypasses the
        ``is_expired`` / ``is_completed`` / ``hide_departed`` filters so that
        finished trips remain visible. No JIT refresh or GTFS merge — the
        data is historical.
        """
        now = now_et()
        window_start = now - timedelta(minutes=window_minutes)

        # journey_date range spans yesterday→today to handle overnight journeys
        # scheduled before midnight for trains observed past midnight.
        journey_date_filter = and_(
            TrainJourney.journey_date >= (window_start.date() - timedelta(days=1)),
            TrainJourney.journey_date <= now.date(),
        )

        allowed_sources = data_sources if data_sources else ALL_DATA_SOURCES
        from_codes = expand_station_codes(from_station)
        to_codes = expand_station_codes(to_station) if to_station else []

        recent_filters = [
            JourneyStop.scheduled_departure >= window_start,
            JourneyStop.scheduled_departure < now,
            journey_date_filter,
            TrainJourney.data_source.in_(allowed_sources),
            # A train counts as "recent" if it actually left the origin or
            # was cancelled. Excludes SCHEDULED trains that never ran and
            # weren't marked as cancelled (no useful signal for the user).
            or_(
                JourneyStop.has_departed_station.is_(True),
                TrainJourney.is_cancelled.is_(True),
            ),
        ]

        stmt = (
            select(TrainJourney)
            .join(
                JourneyStop,
                and_(
                    JourneyStop.journey_id == TrainJourney.id,
                    JourneyStop.station_code.in_(from_codes),
                ),
            )
            .where(and_(*recent_filters))
            .options(selectinload(TrainJourney.stops))
            .order_by(JourneyStop.scheduled_departure.desc())
        )

        result = await db.execute(stmt)
        journeys = list(result.scalars().unique().all())

        # Deduplicate by train_id (same logic as get_departures): keeps the
        # first (most-recent) occurrence per train_id.
        seen_train_ids: set[str] = set()
        unique_journeys: list[TrainJourney] = []
        for journey in journeys:
            train_id = journey.train_id
            if train_id and train_id not in seen_train_ids:
                seen_train_ids.add(train_id)
                unique_journeys.append(journey)

        departures: list[TrainDeparture] = []
        for journey in unique_journeys:
            from_stop = None
            to_stop = None
            for stop in sorted(journey.stops, key=lambda s: s.stop_sequence or 0):
                if stop.station_code in from_codes and not from_stop:
                    from_stop = stop
                elif to_station and stop.station_code in to_codes and from_stop:
                    if (stop.stop_sequence or 0) > (from_stop.stop_sequence or 0):
                        to_stop = stop
                        break

            if not from_stop or (to_station and not to_stop):
                continue

            train_position = self._calculate_train_position(journey)
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
                    # See get_departures for max() rationale re: NJT semantics.
                    updated_time=(
                        max(from_stop.updated_departure, from_stop.updated_arrival)
                        if from_stop.updated_departure and from_stop.updated_arrival
                        else from_stop.updated_departure or from_stop.updated_arrival
                    ),
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

        limited_departures = departures[:limit]

        has_direct_route = True
        if to_station:
            has_direct_route = _has_direct_route(
                from_station, to_station, allowed_sources
            )

        return DeparturesResponse(
            departures=limited_departures,
            has_direct_route=has_direct_route,
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
                "window_minutes": window_minutes,
                "generated_at": now.isoformat(),
            },
        )

    def _calculate_train_position(self, journey: TrainJourney) -> TrainPosition:
        """
        Calculate current train position.

        Always computes at_station_code from stops via _detect_at_station
        (provider-specific signals: NJT track, Amtrak status, completed journey).

        OPTIMIZATION: Uses journey_progress table when available for
        last_departed / next_station to avoid iterating through stops.
        Falls back to stops-based calculation when progress is not available.
        """
        from sqlalchemy import inspect
        from sqlalchemy.orm.base import NO_VALUE

        from trackrat.models.database import JourneyProgress

        # Use inspect to check if relationships are loaded without triggering lazy load
        state = inspect(journey)

        # Guard against lazy-load in sync context — if stops weren't eagerly
        # loaded, return empty position rather than triggering MissingGreenlet.
        stops_value = state.attrs.stops.loaded_value if state else NO_VALUE
        stops_available = stops_value is not NO_VALUE and bool(journey.stops)

        # Always compute at_station_code from stops (provider-specific signals)
        at_station_code = _detect_at_station(journey) if stops_available else None

        # Check if progress relationship is loaded and get its value
        progress_value = state.attrs.progress.loaded_value if state else NO_VALUE

        # OPTIMIZATION: Use pre-computed journey_progress if available
        if (
            progress_value is not NO_VALUE
            and progress_value is not None
            and isinstance(progress_value, JourneyProgress)
        ):
            if at_station_code:
                logger.debug(
                    "at_station_detected_via_progress_path",
                    train_id=journey.train_id,
                    at_station_code=at_station_code,
                    data_source=journey.data_source,
                )
            return TrainPosition(
                last_departed_station_code=progress_value.last_departed_station,
                at_station_code=at_station_code,
                next_station_code=progress_value.next_station,
                between_stations=(
                    progress_value.last_departed_station is not None
                    and progress_value.next_station is not None
                    and at_station_code is None
                ),
            )

        # Fallback: Calculate from stops if progress not available.
        if not stops_available:
            return TrainPosition()

        sorted_stops = sorted(journey.stops, key=lambda s: s.stop_sequence or 0)

        last_departed_station_code = None
        next_station_code = None

        for stop in sorted_stops:
            if stop.has_departed_station:
                last_departed_station_code = stop.station_code
            else:
                next_station_code = stop.station_code
                break

        if at_station_code:
            logger.debug(
                "at_station_detected_via_stops_path",
                train_id=journey.train_id,
                at_station_code=at_station_code,
                data_source=journey.data_source,
            )

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

    async def _has_imminent_scheduled_njt(
        self,
        db: AsyncSession,
        from_station: str,
        target_date: date,
    ) -> bool:
        """Check if stale SCHEDULED NJT trains exist that the stale filter would hide.

        Returns True when an inline JIT refresh is worthwhile: there is at
        least one SCHEDULED NJT train within the stale-filter threshold whose
        data hasn't been refreshed in the last 60 seconds.
        """
        current_time = now_et()
        threshold = current_time + timedelta(
            minutes=SCHEDULED_VISIBILITY_THRESHOLD_MINUTES
        )
        cutoff_time = current_time - timedelta(seconds=60)
        from_codes = expand_station_codes(from_station)

        result = await db.scalar(
            select(TrainJourney.id)
            .join(JourneyStop, JourneyStop.journey_id == TrainJourney.id)
            .where(
                and_(
                    JourneyStop.station_code.in_(from_codes),
                    TrainJourney.data_source == "NJT",
                    TrainJourney.journey_date == target_date,
                    TrainJourney.observation_type == "SCHEDULED",
                    TrainJourney.last_updated_at < cutoff_time,
                    TrainJourney.is_expired.is_not(True),
                    TrainJourney.is_completed.is_not(True),
                    TrainJourney.is_cancelled.is_not(True),
                    JourneyStop.scheduled_departure.isnot(None),
                    JourneyStop.scheduled_departure < threshold,
                    JourneyStop.scheduled_departure > current_time,
                )
            )
            .limit(1)
        )
        return result is not None

    async def _run_inline_jit_refresh(
        self,
        from_station: str,
        target_date: date,
        skip_individual_refresh: bool,
        hide_departed: bool,
    ) -> bool:
        """Run JIT station refresh inline, waiting up to 10 seconds.

        Unlike the background path, this blocks the request so the subsequent
        query sees promoted trains.  If the refresh doesn't finish in time the
        task keeps running in the background and the request proceeds with
        whatever data is in the DB.

        Returns True if the refresh completed (caller can skip the background
        trigger), False otherwise.
        """
        _refreshing_stations.add(from_station)
        task = asyncio.create_task(
            _background_refresh_station(
                self,
                from_station,
                target_date,
                skip_individual_refresh,
                hide_departed,
            ),
            name=f"inline_jit_{from_station}",
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        task.add_done_callback(lambda _t: _refreshing_stations.discard(from_station))

        done, _ = await asyncio.wait({task}, timeout=10.0)
        if done:
            logger.info("inline_jit_refresh_complete", station_code=from_station)
            return True

        logger.warning("inline_jit_refresh_timed_out", station_code=from_station)
        return False

    async def _maybe_trigger_background_refresh(
        self,
        db: AsyncSession,
        station_code: str,
        target_date: date,
        skip_individual_refresh: bool,
        hide_departed: bool,
    ) -> None:
        """Check staleness and fire a background JIT refresh if needed.

        Uses an in-memory set to debounce: if a refresh is already in-flight
        for this station, we skip. The staleness check runs on the caller's
        DB session (cheap read-only query); only the background refresh task
        creates its own session.
        """
        if station_code in _refreshing_stations:
            logger.debug("jit_refresh_already_in_flight", station_code=station_code)
            return

        # Quick staleness check on the caller's session (read-only, no commit needed)
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
            return

        _refreshing_stations.add(station_code)
        task = asyncio.create_task(
            _background_refresh_station(
                self,
                station_code,
                target_date,
                skip_individual_refresh,
                hide_departed,
            ),
            name=f"jit_refresh_{station_code}",
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        task.add_done_callback(lambda _t: _refreshing_stations.discard(station_code))

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
                        .options(
                            selectinload(TrainJourney.stops),
                            # Load all delete-orphan collections to prevent
                            # greenlet_spawn errors during flush orphan checks
                            selectinload(TrainJourney.snapshots),
                            selectinload(TrainJourney.segment_times),
                            selectinload(TrainJourney.dwell_times),
                            selectinload(TrainJourney.progress),
                            selectinload(TrainJourney.progress_snapshots),
                        )
                        .order_by(TrainJourney.id)
                    )
                    result = await db.execute(stmt)
                    journeys_by_id = {j.train_id: j for j in result.scalars().all()}

                    count = 0
                    empty_stops_count = 0
                    promoted_count = 0
                    for train_data in train_items:
                        train_id = train_data.get("TRAIN_ID")
                        if not train_id:
                            continue

                        journey = journeys_by_id.get(train_id)
                        if not journey:
                            if not is_amtrak_train(train_id):
                                logger.debug(
                                    "journey_not_found_during_station_refresh",
                                    train_id=train_id,
                                    station_code=station_code,
                                )
                            continue

                        # Update journey metadata
                        journey.destination = train_data.get(
                            "DESTINATION", journey.destination
                        )

                        # Clean color value (remove trailing spaces)
                        if backcolor := train_data.get("BACKCOLOR"):
                            journey.line_color = backcolor.strip()
                        journey.update_count = (journey.update_count or 0) + 1

                        # Update stops from embedded STOPS data.
                        # Only mark fresh (last_updated_at) when STOPS are
                        # actually populated — otherwise the second-pass
                        # individual refresh (getTrainStopList) is suppressed
                        # and the train permanently shows null real-time times.
                        stops_data = train_data.get("STOPS") or []
                        if stops_data:
                            await self._update_stops_from_embedded_data(
                                db, journey, stops_data
                            )
                            journey.has_complete_journey = True
                            journey.stops_count = len(stops_data)
                            journey.last_updated_at = now_et()

                            # Promote SCHEDULED → OBSERVED: the NJT station
                            # board API returned this train with stop data,
                            # confirming it is running. Same signal discovery
                            # uses at discovery.py:526.
                            if journey.observation_type == "SCHEDULED":
                                journey.observation_type = "OBSERVED"
                                rt_line = train_data.get("LINE", "").strip()
                                if rt_line:
                                    journey.line_code = parse_njt_line_code(rt_line)
                                    journey.line_name = (
                                        train_data.get("LINE_NAME", "")
                                        or journey.line_name
                                    )
                                promoted_count += 1

                            # Update origin/terminal/scheduled times from stops.
                            # Use immutable schedule fields (SCHED_*_DATE) over
                            # TIME/DEP_TIME which have inverted semantics and
                            # live-updating behavior at intermediate stops.
                            first_stop = stops_data[0]
                            last_stop = stops_data[-1]

                            if first_station := first_stop.get("STATION_2CHAR"):
                                journey.origin_station_code = first_station
                            if last_station := last_stop.get("STATION_2CHAR"):
                                journey.terminal_station_code = last_station

                            # At origin: SCHED_DEP_DATE or TIME (schedule)
                            sched_dep = first_stop.get(
                                "SCHED_DEP_DATE"
                            ) or first_stop.get("TIME")
                            if sched_dep:
                                journey.scheduled_departure = parse_njt_time(sched_dep)

                            # At terminal: SCHED_DEP_DATE (immutable), only if not already set
                            if journey.scheduled_arrival is None:
                                sched_arr = last_stop.get(
                                    "SCHED_DEP_DATE"
                                ) or last_stop.get("SCHED_ARR_DATE")
                                if sched_arr:
                                    journey.scheduled_arrival = parse_njt_time(
                                        sched_arr
                                    )

                        if not stops_data:
                            empty_stops_count += 1

                        logger.debug(
                            "journey_updated_from_schedule",
                            train_id=train_id,
                            stops_count=len(stops_data),
                        )
                        count += 1

                    if empty_stops_count:
                        logger.info(
                            "bulk_refresh_empty_stops",
                            station_code=station_code,
                            empty_stops_trains=empty_stops_count,
                            total_trains=count,
                        )

                    if promoted_count:
                        logger.info(
                            "jit_promoted_scheduled_to_observed",
                            station_code=station_code,
                            promoted_count=promoted_count,
                            total_trains=count,
                        )

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
                # Eagerly load all delete-orphan collections to prevent
                # greenlet_spawn errors during flush/commit orphan checks.
                # Must match the selectinloads in refresh_journey below.
                .options(
                    selectinload(TrainJourney.stops),
                    selectinload(TrainJourney.snapshots),
                    selectinload(TrainJourney.segment_times),
                    selectinload(TrainJourney.dwell_times),
                    selectinload(TrainJourney.progress),
                    selectinload(TrainJourney.progress_snapshots),
                )
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
                            .options(
                                selectinload(TrainJourney.stops),
                                # Load all delete-orphan collections to prevent
                                # greenlet_spawn errors during flush orphan checks
                                selectinload(TrainJourney.snapshots),
                                selectinload(TrainJourney.segment_times),
                                selectinload(TrainJourney.dwell_times),
                                selectinload(TrainJourney.progress),
                                selectinload(TrainJourney.progress_snapshots),
                            )
                            .execution_options(populate_existing=True)
                        )
                        fresh = result.scalar_one_or_none()
                        if fresh:
                            await njt_collector.collect_journey_details(db, fresh)

                    try:
                        async with db.begin_nested():
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
                            error=str(e) or repr(e),
                            error_type=type(e).__name__,
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
                "station_refresh_failed",
                station_code=station_code,
                error=str(e) or repr(e),
                error_type=type(e).__name__,
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

        # Build lookup from eagerly-loaded stops to avoid N+1 queries and
        # prevent greenlet_spawn errors from fetching stops outside the ORM
        # collection (session.get() after pg_insert creates objects not tracked
        # in journey.stops, causing orphan-check lazy loads during flush).
        stops_by_code: dict[str, JourneyStop] = {
            s.station_code: s for s in journey.stops if s.station_code is not None
        }

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

            stop = stops_by_code.get(station_code)
            if stop is None:
                # Not in eagerly-loaded collection — insert via raw SQL for
                # concurrent-update safety, then re-fetch.
                stmt = (
                    pg_insert(JourneyStop)
                    .values(
                        journey_id=journey.id,
                        station_code=station_code,
                        station_name=stop_data.get("STATIONNAME", ""),
                        stop_sequence=i,
                    )
                    .on_conflict_do_nothing(constraint="unique_journey_stop")
                )
                await session.execute(stmt)

                result = await session.execute(
                    select(JourneyStop).where(
                        JourneyStop.journey_id == journey.id,
                        JourneyStop.station_code == station_code,
                    )
                )
                stop = result.scalar_one()
                journey.stops.append(stop)
                stops_by_code[station_code] = stop

            assert stop is not None

            # Update scheduled times from immutable SCHED_*_DATE fields.
            # Only set if not already populated (preserves schedule-collector values).
            # TIME/DEP_TIME have inverted semantics at origin vs intermediate and
            # TIME is a live estimate at intermediate stops — not suitable for scheduled.
            if stop.scheduled_arrival is None:
                sched_arr_str = stop_data.get("SCHED_ARR_DATE")
                sched_dep_str = stop_data.get("SCHED_DEP_DATE")
                sched_arr = parse_njt_time(sched_arr_str) if sched_arr_str else None
                sched_dep = parse_njt_time(sched_dep_str) if sched_dep_str else None
                # Validate: arrival must be <= departure (reject NJT delay corruption)
                if sched_arr and sched_dep and sched_arr > sched_dep:
                    sched_arr = None
                if sched_arr:
                    stop.scheduled_arrival = sched_arr

            if stop.scheduled_departure is None:
                sched_dep_str = stop_data.get("SCHED_DEP_DATE")
                if sched_dep_str:
                    stop.scheduled_departure = parse_njt_time(sched_dep_str)
                elif dep_time_str := stop_data.get("DEP_TIME"):
                    stop.scheduled_departure = parse_njt_time(dep_time_str)

            # Populate real-time estimates from TIME/DEP_TIME fields.
            # These have inverted semantics by stop type (see journey.py:1320-1332),
            # but consumers use max(updated_departure, updated_arrival) which handles it.
            time_str = stop_data.get("TIME")
            if time_str:
                parsed_time = parse_njt_time(time_str)
                if parsed_time:
                    stop.updated_arrival = parsed_time
            dep_time_rt_str = stop_data.get("DEP_TIME")
            if dep_time_rt_str:
                parsed_dep = parse_njt_time(dep_time_rt_str)
                if parsed_dep:
                    stop.updated_departure = parsed_dep

            # Update departure status with time validation
            departed = (stop_data.get("DEPARTED") or "").upper() or None
            stop.raw_njt_departed_flag = departed

            # Cancelled stops never physically departed
            is_stop_cancelled = is_njt_stop_cancelled(stop_data.get("STOP_STATUS"))

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


async def _background_refresh_station(
    service: "DepartureService",
    station_code: str,
    target_date: date,
    skip_individual_refresh: bool,
    hide_departed: bool,
) -> None:
    """Run NJT station JIT refresh in the background with its own DB session.

    Errors are logged but never propagated — the caller already served
    whatever data was in the DB, matching the existing graceful-degradation
    behavior when JIT fails.
    """
    try:
        async with get_session() as db:
            await service._ensure_fresh_station_data(
                db,
                station_code,
                target_date,
                skip_individual_refresh,
                hide_departed,
            )
        logger.info("background_jit_refresh_complete", station_code=station_code)
    except Exception as e:
        logger.warning(
            "background_jit_refresh_failed",
            station_code=station_code,
            error=str(e) or repr(e),
            error_type=type(e).__name__,
        )
