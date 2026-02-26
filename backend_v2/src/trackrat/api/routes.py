"""
Route API endpoints for TrackRat V2.

Provides route-based historical analysis independent of specific trains.
"""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, exists, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload
from structlog import get_logger

from trackrat.api.utils import handle_errors
from trackrat.config.stations import expand_station_codes, get_station_name
from trackrat.db.engine import get_db
from trackrat.models.api import (
    AggregateStats,
    CongestionMapResponse,
    DelayBreakdown,
    HighlightedTrain,
    HistoricalRouteInfo,
    OperationsSummaryResponse,
    RouteHistoryResponse,
    SegmentTrainDetail,
    SegmentTrainDetailsResponse,
    SummaryMetricsResponse,
    TrainDelaySummaryResponse,
    TrainLocationData,
)
from trackrat.models.api import (
    SegmentCongestion as SegmentCongestionModel,
)
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.api_cache import ApiCacheService
from trackrat.services.congestion import CongestionAnalyzer
from trackrat.services.departure import DepartureService
from trackrat.utils.time import ensure_timezone_aware, now_et

logger = get_logger()

router = APIRouter(prefix="/api/v2/routes", tags=["routes"])


@router.get("/history", response_model=RouteHistoryResponse)
@handle_errors
async def get_route_history(
    from_station: str = Query(
        ..., min_length=1, max_length=10, description="Origin station code"
    ),
    to_station: str = Query(
        ..., min_length=1, max_length=10, description="Destination station code"
    ),
    data_source: str = Query(
        ..., description="Data source (NJT, AMTRAK, PATH, PATCO, LIRR, MNR, SUBWAY)"
    ),
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    hours: int | None = Query(
        None,
        ge=1,
        le=168,
        description="Hours lookback (overrides days when provided)",
    ),
    highlight_train: str | None = Query(None, description="Train ID to highlight"),
    db: AsyncSession = Depends(get_db),
) -> RouteHistoryResponse:
    """Get aggregate historical performance for all trains on a route.

    Returns on-time percentage, delay breakdown, cancellation rate, and track usage
    at the origin station. Optionally highlights a specific train for comparison
    against the route-wide statistics.

    When `hours` is provided, filters by actual departure time at the origin station
    instead of journey date, enabling sub-day time windows (e.g. past hour).
    """
    logger.info(
        "get_route_history_request",
        from_station=from_station,
        to_station=to_station,
        data_source=data_source,
        days=days,
        hours=hours,
        highlight_train=highlight_train,
    )

    # Validate data_source
    valid_sources = ["NJT", "AMTRAK", "PATH", "PATCO", "LIRR", "MNR", "SUBWAY"]
    if data_source not in valid_sources:
        raise HTTPException(
            status_code=400,
            detail=f"data_source must be one of: {', '.join(valid_sources)}",
        )

    # Check cache first (skip when highlight_train is provided - uncommon, user-specific)
    cache_service = ApiCacheService()
    if not highlight_train:
        cache_params = {
            "from_station": from_station,
            "to_station": to_station,
            "data_source": data_source,
            "days": days,
            "hours": hours,
        }
        cached_response = await cache_service.get_cached_response(
            db=db,
            endpoint="/api/v2/routes/history",
            params=cache_params,
        )
        if cached_response:
            try:
                return RouteHistoryResponse(**cached_response)
            except (TypeError, ValueError) as e:
                logger.warning(
                    "route_history_cache_deserialization_failed",
                    error=str(e),
                )
                await cache_service.invalidate_cache_entry(
                    db, "/api/v2/routes/history", cache_params
                )

    # Calculate date range
    now = now_et()
    cutoff_time = None
    if hours:
        # Hours-based filtering: use timestamp on origin stop departure
        cutoff_time = now - timedelta(hours=hours)
        start_date = cutoff_time.date()
    else:
        start_date = now.date() - timedelta(days=days)
    end_date = now.date()

    from_codes = expand_station_codes(from_station)
    to_codes = expand_station_codes(to_station)

    # Compute aggregate stats via SQL
    aggregate_stats = await _calculate_route_stats_sql(
        db, data_source, start_date, end_date, from_codes, to_codes, cutoff_time, now
    )

    # Compute highlighted train stats if specified
    highlighted_train_data = None
    if highlight_train:
        highlighted_stats = await _calculate_route_stats_sql(
            db,
            data_source,
            start_date,
            end_date,
            from_codes,
            to_codes,
            cutoff_time,
            now,
            train_id_filter=highlight_train,
        )
        if highlighted_stats["total_journeys"] > 0:
            highlighted_train_data = HighlightedTrain(
                train_id=highlight_train,
                on_time_percentage=highlighted_stats["on_time_percentage"],
                average_delay_minutes=highlighted_stats["average_delay_minutes"],
                average_departure_delay_minutes=highlighted_stats[
                    "average_departure_delay_minutes"
                ],
                delay_breakdown=DelayBreakdown(**highlighted_stats["delay_breakdown"]),
                track_usage_at_origin=highlighted_stats["track_usage"],
            )

    # Calculate baseline train count for frequency comparison
    baseline_train_count = await _calculate_baseline_train_count(
        db, data_source, from_codes, to_codes, hours, now
    )

    response = RouteHistoryResponse(
        route=HistoricalRouteInfo(
            from_station=from_station,
            to_station=to_station,
            total_trains=aggregate_stats["total_journeys"],
            data_source=data_source,
            baseline_train_count=baseline_train_count,
        ),
        aggregate_stats=AggregateStats(
            on_time_percentage=aggregate_stats["on_time_percentage"],
            average_delay_minutes=aggregate_stats["average_delay_minutes"],
            average_departure_delay_minutes=aggregate_stats[
                "average_departure_delay_minutes"
            ],
            cancellation_rate=aggregate_stats["cancellation_rate"],
            delay_breakdown=DelayBreakdown(**aggregate_stats["delay_breakdown"]),
            track_usage_at_origin=aggregate_stats["track_usage"],
        ),
        highlighted_train=highlighted_train_data,
    )

    # Store in cache (skip when highlight_train is provided)
    if not highlight_train:
        try:
            await cache_service.store_cached_response(
                db=db,
                endpoint="/api/v2/routes/history",
                params=cache_params,
                response=response.model_dump(mode="json"),
                ttl_seconds=120,
            )
        except Exception as e:
            logger.warning("route_history_cache_storage_failed", error=str(e))

    return response


async def _calculate_route_stats_sql(
    db: AsyncSession,
    data_source: str,
    start_date: Any,
    end_date: Any,
    from_codes: list[str],
    to_codes: list[str],
    cutoff_time: datetime | None,
    now: datetime,
    train_id_filter: str | None = None,
) -> dict[str, Any]:
    """Calculate route statistics using SQL aggregation instead of loading ORM objects."""

    empty_stats = {
        "total_journeys": 0,
        "on_time_percentage": 0.0,
        "average_delay_minutes": 0.0,
        "average_departure_delay_minutes": 0.0,
        "cancellation_rate": 0.0,
        "delay_breakdown": {
            "on_time": 0,
            "slight": 0,
            "significant": 0,
            "major": 0,
        },
        "track_usage": {},
    }

    # Build the time filter clause for origin stop
    time_filter = ""
    if cutoff_time:
        time_filter = """
            AND fs.scheduled_departure >= :cutoff_time
            AND fs.scheduled_departure <= :now_time
        """

    train_filter = ""
    if train_id_filter:
        train_filter = "AND tj.train_id = :train_id"

    # Build the route_journeys CTE SQL (reused by stats and track queries)
    route_journeys_cte = f"""
        SELECT tj.id AS journey_id, tj.is_cancelled
        FROM train_journeys tj
        WHERE tj.data_source = :data_source
          AND tj.journey_date >= :start_date
          AND tj.journey_date <= :end_date
          {train_filter}
          AND EXISTS (
              SELECT 1 FROM journey_stops fs
              WHERE fs.journey_id = tj.id
                AND fs.station_code = ANY(:from_codes)
                {time_filter}
                AND EXISTS (
                    SELECT 1 FROM journey_stops ts
                    WHERE ts.journey_id = tj.id
                      AND ts.station_code = ANY(:to_codes)
                      AND ts.stop_sequence > fs.stop_sequence
                )
          )
        ORDER BY tj.journey_date DESC
        LIMIT 5000
    """

    # Single SQL query with CTEs for all aggregation
    sql = text(f"""
        WITH route_journeys AS (
            {route_journeys_cte}
        ),
        last_stops AS (
            SELECT DISTINCT ON (js.journey_id)
                js.journey_id,
                EXTRACT(EPOCH FROM (js.actual_arrival - js.scheduled_arrival)) / 60.0
                    AS arrival_delay_minutes
            FROM journey_stops js
            INNER JOIN route_journeys rj ON rj.journey_id = js.journey_id
            WHERE js.actual_arrival IS NOT NULL
              AND js.scheduled_arrival IS NOT NULL
            ORDER BY js.journey_id, js.stop_sequence DESC
        ),
        origin_stops AS (
            SELECT DISTINCT ON (js.journey_id)
                js.journey_id,
                EXTRACT(EPOCH FROM (js.actual_departure - js.scheduled_departure)) / 60.0
                    AS departure_delay_minutes
            FROM journey_stops js
            INNER JOIN route_journeys rj ON rj.journey_id = js.journey_id
            WHERE js.station_code = ANY(:from_codes)
              AND js.actual_departure IS NOT NULL
              AND js.scheduled_departure IS NOT NULL
            ORDER BY js.journey_id, js.stop_sequence ASC
        ),
        stats AS (
            SELECT
                COUNT(*) AS total_journeys,
                COUNT(*) FILTER (WHERE rj.is_cancelled) AS cancelled_count,
                COUNT(*) FILTER (WHERE NOT rj.is_cancelled) AS non_cancelled_count,
                -- Arrival delay aggregates (non-cancelled only)
                AVG(GREATEST(ls.arrival_delay_minutes, 0))
                    FILTER (WHERE NOT rj.is_cancelled AND ls.arrival_delay_minutes IS NOT NULL)
                    AS avg_arrival_delay,
                COUNT(*) FILTER (WHERE NOT rj.is_cancelled
                    AND ls.arrival_delay_minutes IS NOT NULL
                    AND ls.arrival_delay_minutes <= 5)
                    AS on_time_count,
                COUNT(*) FILTER (WHERE NOT rj.is_cancelled
                    AND ls.arrival_delay_minutes IS NOT NULL
                    AND ls.arrival_delay_minutes > 5 AND ls.arrival_delay_minutes <= 15)
                    AS slight_count,
                COUNT(*) FILTER (WHERE NOT rj.is_cancelled
                    AND ls.arrival_delay_minutes IS NOT NULL
                    AND ls.arrival_delay_minutes > 15 AND ls.arrival_delay_minutes <= 30)
                    AS significant_count,
                COUNT(*) FILTER (WHERE NOT rj.is_cancelled
                    AND ls.arrival_delay_minutes IS NOT NULL
                    AND ls.arrival_delay_minutes > 30)
                    AS major_count,
                -- Departure delay aggregates (non-cancelled with actual departure)
                AVG(GREATEST(os.departure_delay_minutes, 0))
                    FILTER (WHERE NOT rj.is_cancelled
                            AND os.departure_delay_minutes IS NOT NULL)
                    AS avg_departure_delay
            FROM route_journeys rj
            LEFT JOIN last_stops ls ON ls.journey_id = rj.journey_id
            LEFT JOIN origin_stops os ON os.journey_id = rj.journey_id
        )
        SELECT * FROM stats
    """)

    # Build params — use lists for ANY() array comparison
    params: dict[str, Any] = {
        "data_source": data_source,
        "start_date": start_date,
        "end_date": end_date,
        "from_codes": from_codes,
        "to_codes": to_codes,
    }
    if cutoff_time:
        params["cutoff_time"] = cutoff_time
        params["now_time"] = now
    if train_id_filter:
        params["train_id"] = train_id_filter

    result = await db.execute(sql, params)
    row = result.mappings().first()

    if not row or row["total_journeys"] == 0:
        return empty_stats

    total_journeys = row["total_journeys"]
    cancelled_count = row["cancelled_count"]
    non_cancelled = row["non_cancelled_count"]
    on_time_count = row["on_time_count"]
    avg_arrival = float(row["avg_arrival_delay"] or 0)
    avg_departure = float(row["avg_departure_delay"] or 0)

    # Calculate delay breakdown percentages
    if non_cancelled > 0:
        delay_breakdown = {
            "on_time": round(on_time_count / non_cancelled * 100),
            "slight": round(row["slight_count"] / non_cancelled * 100),
            "significant": round(row["significant_count"] / non_cancelled * 100),
            "major": round(row["major_count"] / non_cancelled * 100),
        }
    else:
        delay_breakdown = {"on_time": 0, "slight": 0, "significant": 0, "major": 0}

    # Track usage query (separate for clarity)
    track_sql = text(f"""
        WITH route_journeys AS (
            {route_journeys_cte}
        )
        SELECT js.track, COUNT(*) AS cnt
        FROM journey_stops js
        INNER JOIN route_journeys rj ON rj.journey_id = js.journey_id
        WHERE js.station_code = ANY(:from_codes)
          AND js.track IS NOT NULL
        GROUP BY js.track
    """)

    track_result = await db.execute(track_sql, params)
    track_rows = track_result.mappings().all()

    track_usage: dict[str, int] = {}
    total_track_assignments = sum(r["cnt"] for r in track_rows)
    if total_track_assignments > 0:
        track_usage = {
            r["track"]: round(r["cnt"] / total_track_assignments * 100)
            for r in track_rows
        }

    return {
        "total_journeys": total_journeys,
        "on_time_percentage": (
            (on_time_count / non_cancelled * 100) if non_cancelled > 0 else 0
        ),
        "average_delay_minutes": avg_arrival,
        "average_departure_delay_minutes": avg_departure,
        "cancellation_rate": (
            (cancelled_count / total_journeys * 100) if total_journeys > 0 else 0
        ),
        "delay_breakdown": delay_breakdown,
        "track_usage": track_usage,
    }


async def _calculate_baseline_train_count(
    db: AsyncSession,
    data_source: str,
    from_codes: list[str],
    to_codes: list[str],
    hours: int | None,
    now: datetime,
) -> float | None:
    """Calculate expected train count for frequency baseline comparison.

    Uses segment_transit_times from the past 30 days to estimate how many
    trains typically run on this route during an equivalent time window.

    Matching strategy (mirrors congestion service):
    - hours=1: same hour-of-day + weekday/weekend pattern
    - hours=24: weekday/weekend pattern only (all hours)
    - hours=None (days-based) or hours>=168: no time/day filter (weekly average)

    Returns None if no historical data exists.
    """
    from trackrat.utils.time import normalize_to_et

    now_eastern = normalize_to_et(now)
    current_hour = now_eastern.hour
    is_weekend = now_eastern.weekday() >= 5  # Saturday=5, Sunday=6

    # Build filters based on time window
    hour_filter = ""
    day_filter = ""

    if hours is not None and hours <= 1:
        # 1-hour window: match same hour-of-day and weekday/weekend
        hour_filter = "AND stt.hour_of_day = :current_hour"
        day_filter = """AND (
            (:is_weekend AND stt.day_of_week IN (0, 6))
            OR (NOT :is_weekend AND stt.day_of_week NOT IN (0, 6))
        )"""
        divisor = 30.0
    elif hours is not None and hours <= 24:
        # 24-hour window: match weekday/weekend only
        day_filter = """AND (
            (:is_weekend AND stt.day_of_week IN (0, 6))
            OR (NOT :is_weekend AND stt.day_of_week NOT IN (0, 6))
        )"""
        divisor = 30.0
    else:
        # 7+ day window: no time/day filter, scale to weekly average
        divisor = 30.0 / 7.0

    sql = text(f"""
        SELECT COUNT(DISTINCT stt.journey_id) AS baseline_count
        FROM segment_transit_times stt
        WHERE stt.departure_time >= :baseline_start
          AND stt.from_station_code = ANY(:from_codes)
          AND stt.data_source = :data_source
          {hour_filter}
          {day_filter}
          AND EXISTS (
              SELECT 1 FROM segment_transit_times stt2
              WHERE stt2.journey_id = stt.journey_id
                AND stt2.to_station_code = ANY(:to_codes)
          )
    """)

    params: dict[str, Any] = {
        "baseline_start": now - timedelta(days=30),
        "from_codes": from_codes,
        "to_codes": to_codes,
        "data_source": data_source,
        "current_hour": current_hour,
        "is_weekend": is_weekend,
    }

    try:
        result = await db.execute(sql, params)
        row = result.mappings().first()
        if not row or row["baseline_count"] == 0:
            return None

        baseline = float(row["baseline_count"]) / divisor
        return round(baseline, 1) if baseline > 0 else None
    except Exception as e:
        logger.warning("baseline_train_count_query_failed", error=str(e))
        return None


@router.get("/congestion", response_model=CongestionMapResponse)
@handle_errors
async def get_route_congestion(
    time_window_hours: int = Query(1, ge=1, le=24, description="Hours to look back"),
    max_per_segment: int = Query(
        100,
        ge=0,
        le=500,
        description="Max individual journeys per segment (0 = unlimited)",
    ),
    data_source: str | None = Query(
        None,
        description="Filter by data source (NJT, AMTRAK, PATH, PATCO, LIRR, MNR, SUBWAY)",
    ),
    force_refresh: bool = Query(False, description="Force bypass cache and recompute"),
    db: AsyncSession = Depends(get_db),
) -> CongestionMapResponse:
    """Get network congestion levels based on recent train performance.

    Analyzes train journeys within a lookback window (minimum 2 hours) and returns
    per-segment congestion factors, aggregated congestion levels, and live train
    positions. Results are cached for 10 minutes.
    """

    # Enforce minimum 2-hour window for meaningful congestion data across all systems
    effective_time_window = max(time_window_hours, 2)

    # Cache key uses effective values so precomputed entries match
    cache_params = {
        "time_window_hours": effective_time_window,
        "max_per_segment": max_per_segment,
        "data_source": data_source,
    }

    # Try to serve from cache first (unless force_refresh is requested)
    if not force_refresh:
        from trackrat.services.api_cache import ApiCacheService

        cache_service = ApiCacheService()
        cached_response = await cache_service.get_cached_response(
            db=db,
            endpoint="/api/v2/routes/congestion",
            params=cache_params,
        )

        if cached_response:
            try:
                # Return cached response directly - it's already in the correct format
                return CongestionMapResponse(**cached_response)
            except (TypeError, ValueError) as e:
                logger.warning(
                    "cache_deserialization_failed",
                    endpoint="/api/v2/routes/congestion",
                    params=cache_params,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                # Invalidate corrupted cache entry
                await cache_service.invalidate_cache_entry(
                    db,
                    "/api/v2/routes/congestion",
                    cache_params,
                )

    analyzer = CongestionAnalyzer()
    aggregated_segments, journeys, individual_segments = (
        await analyzer.get_network_congestion_with_trains(
            db, effective_time_window, max_per_segment, data_source
        )
    )

    # Filter out segments containing "SAN" station code - collision between
    # San Diego Santa Fe Depot (Pacific Surfliner) and Sanford, FL (Silver Service)
    # causes cross-country lines on the map. TODO: Proper disambiguation in Amtrak collector.
    aggregated_segments = [
        s
        for s in aggregated_segments
        if s.from_station != "SAN" and s.to_station != "SAN"
    ]
    individual_segments = [
        s
        for s in individual_segments
        if s.from_station != "SAN" and s.to_station != "SAN"
    ]

    # Extract train positions from journeys
    departure_service = DepartureService()
    train_positions = []

    for journey in journeys:
        # Skip cancelled trains
        if journey.is_cancelled:
            continue

        # Calculate train position
        position = departure_service._calculate_train_position(journey)

        # Get journey progress if available
        journey_percent = None
        if journey.progress:
            journey_percent = journey.progress.journey_percent

        # Create train location data
        location_data = TrainLocationData(
            train_id=journey.train_id,
            line=journey.line_code,
            data_source=journey.data_source,
            last_departed_station=position.last_departed_station_code,
            at_station=position.at_station_code,
            next_station=position.next_station_code,
            between_stations=position.between_stations,
            journey_percent=journey_percent,
        )

        # Add GPS data for Amtrak trains if available
        # TODO: This will need to be fetched from Amtrak API snapshot data
        # For now, we'll just include the station-based position

        train_positions.append(location_data)

    # Convert aggregated segments to API models
    aggregated_api_segments = []
    for segment in aggregated_segments:
        segment_model = SegmentCongestionModel(
            from_station=segment.from_station,
            to_station=segment.to_station,
            from_station_name=get_station_name(segment.from_station),
            to_station_name=get_station_name(segment.to_station),
            data_source=segment.data_source,
            congestion_level=segment.congestion_level,
            congestion_factor=segment.congestion_factor,
            average_delay_minutes=segment.average_delay_minutes,
            sample_count=segment.sample_count,
            baseline_minutes=segment.baseline_minutes,
            current_average_minutes=segment.avg_transit_minutes,
            cancellation_count=segment.cancellation_count,
            cancellation_rate=segment.cancellation_rate,
            # Frequency/health metrics
            train_count=segment.train_count,
            baseline_train_count=segment.baseline_train_count,
            frequency_factor=segment.frequency_factor,
            frequency_level=segment.frequency_level,
        )
        aggregated_api_segments.append(segment_model)

    # Build the response
    response = CongestionMapResponse(
        individual_segments=individual_segments,
        aggregated_segments=aggregated_api_segments,
        train_positions=train_positions,
        generated_at=now_et(),
        time_window_hours=effective_time_window,
        max_per_segment=max_per_segment,
        metadata={
            "total_individual_segments": len(individual_segments),
            "total_aggregated_segments": len(aggregated_api_segments),
            "congestion_levels": {
                "normal": len(
                    [
                        s
                        for s in aggregated_api_segments
                        if s.congestion_level == "normal"
                    ]
                ),
                "moderate": len(
                    [
                        s
                        for s in aggregated_api_segments
                        if s.congestion_level == "moderate"
                    ]
                ),
                "heavy": len(
                    [
                        s
                        for s in aggregated_api_segments
                        if s.congestion_level == "heavy"
                    ]
                ),
                "severe": len(
                    [
                        s
                        for s in aggregated_api_segments
                        if s.congestion_level == "severe"
                    ]
                ),
            },
            "total_trains": len(train_positions),
        },
    )

    # Store in cache for future requests (also update cache on force_refresh)
    try:
        from trackrat.services.api_cache import ApiCacheService

        cache_service = ApiCacheService()
        await cache_service.store_cached_response(
            db=db,
            endpoint="/api/v2/routes/congestion",
            params=cache_params,
            response=response.model_dump(mode="json"),
            ttl_seconds=600,  # 10 minutes (longer than 15-min refresh to avoid gaps)
        )
    except Exception as e:
        # Don't let cache storage failure affect the API response
        logger.warning("cache_storage_failed", error=str(e))

    return response


@router.get(
    "/segments/{from_station}/{to_station}/trains",
    response_model=SegmentTrainDetailsResponse,
)
@handle_errors
async def get_segment_train_details(
    from_station: str,
    to_station: str,
    data_source: str | None = Query(
        None,
        description="Filter by data source (NJT, AMTRAK, PATH, PATCO, LIRR, MNR, SUBWAY)",
    ),
    start_time: datetime | None = Query(None, description="Start time (ISO format)"),
    end_time: datetime | None = Query(None, description="End time (ISO format)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum trains to return"),
    status: str | None = Query(
        None,
        description="Filter by delay status: on_time, delayed, significantly_delayed",
        pattern="^(on_time|delayed|significantly_delayed)$",
    ),
    db: AsyncSession = Depends(get_db),
) -> SegmentTrainDetailsResponse:
    """Get individual train records for a specific route segment.

    Returns per-train departure/arrival times, delays, and congestion factors
    for trains that traversed the segment within the specified time window
    (defaults to the last 2 hours). Filterable by delay status.
    """

    # Default time window to 2 hours ago (longer window for Amtrak long-haul trains)
    if not end_time:
        end_time = now_et()
    if not start_time:
        start_time = end_time - timedelta(hours=2)

    # Ensure timezone awareness
    start_time = ensure_timezone_aware(start_time)
    end_time = ensure_timezone_aware(end_time)

    logger.info(
        "get_segment_train_details_request",
        from_station=from_station,
        to_station=to_station,
        data_source=data_source,
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        limit=limit,
        status=status,
    )

    # Query journeys where the train passes through from_station within the time window
    # and continues to to_station (with higher stop_sequence)
    from_stop = aliased(JourneyStop, name="from_stop")
    to_stop = aliased(JourneyStop, name="to_stop")

    seg_from_codes = expand_station_codes(from_station)
    seg_to_codes = expand_station_codes(to_station)

    # Build base conditions
    conditions = [
        # Filter by when the train departs from_station (not journey origin)
        from_stop.scheduled_departure >= start_time,
        from_stop.scheduled_departure <= end_time,
        # Verify to_station exists with higher stop_sequence
        exists(
            select(to_stop.id).where(
                and_(
                    to_stop.journey_id == TrainJourney.id,
                    to_stop.station_code.in_(seg_to_codes),
                    to_stop.stop_sequence > from_stop.stop_sequence,
                )
            )
        ),
    ]

    # Apply data source filter if specified
    if data_source:
        conditions.append(TrainJourney.data_source == data_source)

    stmt = (
        select(TrainJourney)
        .join(
            from_stop,
            and_(
                from_stop.journey_id == TrainJourney.id,
                from_stop.station_code.in_(seg_from_codes),
            ),
        )
        .where(and_(*conditions))
        .options(selectinload(TrainJourney.stops))
        .order_by(from_stop.scheduled_departure.desc())
    )

    result = await db.execute(stmt)
    journeys = list(result.scalars().all())

    # Process journeys to extract segment details
    train_details = []
    for journey in journeys:
        segment_detail = await _extract_segment_detail(
            journey, from_station, to_station
        )

        if segment_detail:
            # Apply status filter if specified
            if status:
                if not _matches_status_filter(segment_detail, status):
                    continue

            train_details.append(segment_detail)

            # Stop when we reach the limit
            if len(train_details) >= limit:
                break

    # Calculate summary statistics
    summary = _calculate_segment_summary(train_details, len(journeys))

    return SegmentTrainDetailsResponse(
        segment={
            "from_station": from_station,
            "to_station": to_station,
            "from_station_name": get_station_name(from_station),
            "to_station_name": get_station_name(to_station),
        },
        trains=train_details,
        summary=summary,
    )


async def _extract_segment_detail(
    journey: TrainJourney, from_station: str, to_station: str
) -> SegmentTrainDetail | None:
    """Extract segment details from a journey."""

    # Find the from and to stops
    from_stop = None
    to_stop = None
    seg_from_codes = set(expand_station_codes(from_station))
    seg_to_codes = set(expand_station_codes(to_station))

    for stop in journey.stops:
        if stop.station_code in seg_from_codes:
            from_stop = stop
        elif stop.station_code in seg_to_codes:
            to_stop = stop

    # Verify stops exist and are in correct order
    if not from_stop or not to_stop:
        return None

    if (from_stop.stop_sequence or 0) >= (to_stop.stop_sequence or 0):
        return None

    # Calculate times and delays
    if (
        not from_stop.scheduled_departure
        or not (from_stop.actual_departure or from_stop.scheduled_departure)
        or not to_stop.scheduled_arrival
        or not (to_stop.actual_arrival or to_stop.scheduled_arrival)
    ):
        return None
    scheduled_departure = ensure_timezone_aware(from_stop.scheduled_departure)
    actual_departure = ensure_timezone_aware(
        from_stop.actual_departure or from_stop.scheduled_departure
    )
    scheduled_arrival = ensure_timezone_aware(to_stop.scheduled_arrival)
    actual_arrival = ensure_timezone_aware(
        to_stop.actual_arrival or to_stop.scheduled_arrival
    )

    # Calculate delays
    departure_delay = (actual_departure - scheduled_departure).total_seconds() / 60
    arrival_delay = (actual_arrival - scheduled_arrival).total_seconds() / 60

    # Calculate transit times
    scheduled_minutes = (scheduled_arrival - scheduled_departure).total_seconds() / 60
    actual_minutes = (actual_arrival - actual_departure).total_seconds() / 60

    # Calculate congestion factor
    congestion_factor = (
        actual_minutes / scheduled_minutes if scheduled_minutes > 0 else 1.0
    )

    # Determine delay category
    if arrival_delay <= 2:
        delay_category = "on_time"
    elif arrival_delay <= 10:
        delay_category = "slight_delay"
    elif arrival_delay <= 30:
        delay_category = "delayed"
    else:
        delay_category = "significantly_delayed"

    return SegmentTrainDetail(
        train_id=journey.train_id,
        line=journey.line_name or journey.line_code or "Unknown",
        scheduled_departure=scheduled_departure,
        actual_departure=actual_departure,
        scheduled_arrival=scheduled_arrival,
        actual_arrival=actual_arrival,
        departure_delay_minutes=departure_delay,
        arrival_delay_minutes=arrival_delay,
        congestion_factor=congestion_factor,
        delay_category=delay_category,
        data_source=journey.data_source,
    )


def _matches_status_filter(detail: SegmentTrainDetail, status: str) -> bool:
    """Check if train detail matches status filter."""
    if status == "on_time":
        return detail.delay_category == "on_time"
    elif status == "delayed":
        return detail.delay_category in ["delayed", "significantly_delayed"]
    elif status == "significantly_delayed":
        return detail.delay_category == "significantly_delayed"
    return True


def _calculate_segment_summary(
    train_details: list[SegmentTrainDetail], total_journeys: int
) -> dict[str, Any]:
    """Calculate summary statistics for segment."""
    if not train_details:
        return {
            "total_trains": total_journeys,
            "returned_trains": 0,
            "average_departure_delay": 0.0,
            "average_arrival_delay": 0.0,
            "average_congestion_factor": 1.0,
            "on_time_percentage": 0.0,
        }

    avg_departure_delay = sum(t.departure_delay_minutes for t in train_details) / len(
        train_details
    )
    avg_arrival_delay = sum(t.arrival_delay_minutes for t in train_details) / len(
        train_details
    )
    avg_congestion_factor = sum(t.congestion_factor for t in train_details) / len(
        train_details
    )
    on_time_count = sum(1 for t in train_details if t.delay_category == "on_time")
    on_time_percentage = (on_time_count / len(train_details)) * 100

    return {
        "total_trains": total_journeys,
        "returned_trains": len(train_details),
        "average_departure_delay": round(avg_departure_delay, 1),
        "average_arrival_delay": round(avg_arrival_delay, 1),
        "average_congestion_factor": round(avg_congestion_factor, 2),
        "on_time_percentage": round(on_time_percentage, 1),
    }


@router.get("/summary", response_model=OperationsSummaryResponse)
@handle_errors
async def get_operations_summary(
    scope: str = Query(
        ...,
        description="Summary scope: 'network', 'route', or 'train'",
        pattern="^(network|route|train)$",
    ),
    from_station: str | None = Query(
        None,
        min_length=1,
        max_length=10,
        description="Origin station code (for route/train)",
    ),
    to_station: str | None = Query(
        None,
        min_length=1,
        max_length=10,
        description="Destination station code (for route)",
    ),
    train_id: str | None = Query(None, description="Train ID (for train scope)"),
    data_source: str | None = Query(
        None,
        description="Filter by data source (NJT, AMTRAK, PATH, PATCO, LIRR, MNR, SUBWAY)",
    ),
    db: AsyncSession = Depends(get_db),
) -> OperationsSummaryResponse:
    """
    Get a natural language summary of recent train operations.

    Three scopes are available:
    - network: Overall system status across all lines (past 90 minutes)
    - route: Performance between origin and destination (past 90 minutes)
    - train: Historical performance of a specific train (past 30 days)

    The response includes:
    - headline: Short summary (max 50 chars) for collapsed view
    - body: Detailed summary (2-4 sentences) for expanded view
    - metrics: Raw statistics for optional UI display
    """
    from trackrat.services.summary import summary_service

    logger.info(
        "get_operations_summary_request",
        scope=scope,
        from_station=from_station,
        to_station=to_station,
        train_id=train_id,
        data_source=data_source,
    )

    # Validate parameters based on scope
    if scope == "route":
        if not from_station or not to_station:
            raise HTTPException(
                status_code=400,
                detail="from_station and to_station are required for route scope",
            )
    elif scope == "train":
        if not train_id:
            raise HTTPException(
                status_code=400,
                detail="train_id is required for train scope",
            )

    if scope == "network":
        summary = await summary_service.get_network_summary(db, data_source)
    elif scope == "route":
        summary = await summary_service.get_route_summary(
            db, from_station, to_station, data_source  # type: ignore[arg-type]
        )
    else:  # train
        summary = await summary_service.get_train_summary(
            db, train_id, from_station, to_station  # type: ignore[arg-type]
        )

    # Convert to response model
    metrics = None
    if summary.metrics:
        # Convert trains_by_category to API response format
        trains_by_category = None
        if summary.metrics.trains_by_category:
            trains_by_category = {
                category: [
                    TrainDelaySummaryResponse(
                        train_id=train.train_id,
                        delay_minutes=train.delay_minutes,
                        category=train.category,  # type: ignore[arg-type]
                        scheduled_departure=train.scheduled_departure,
                    )
                    for train in trains
                ]
                for category, trains in summary.metrics.trains_by_category.items()
            }
        metrics = SummaryMetricsResponse(
            on_time_percentage=summary.metrics.on_time_percentage,
            average_delay_minutes=summary.metrics.average_delay_minutes,
            cancellation_count=summary.metrics.cancellation_count,
            train_count=summary.metrics.train_count,
            trains_by_category=trains_by_category,
        )

    return OperationsSummaryResponse(
        headline=summary.headline,
        body=summary.body,
        scope=summary.scope,
        time_window_minutes=summary.time_window_minutes,
        data_freshness_seconds=summary.data_freshness_seconds,
        generated_at=summary.generated_at,
        metrics=metrics,
    )
