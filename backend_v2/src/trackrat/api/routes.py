"""
Route API endpoints for TrackRat V2.

Provides route-based historical analysis independent of specific trains.
"""

import asyncio
import json as json_mod
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import and_, exists, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload
from structlog import get_logger

from trackrat.api.utils import handle_errors
from trackrat.config.stations import expand_station_codes, get_station_name
from trackrat.db.engine import get_db, get_session
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
from trackrat.services.summary import TrainDelaySummary
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
        ...,
        description="Data source (NJT, AMTRAK, PATH, PATCO, LIRR, MNR, SUBWAY, METRA, WMATA, MBTA)",
    ),
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    hours: int | None = Query(
        None,
        ge=1,
        le=168,
        description="Hours lookback (overrides days when provided)",
    ),
    highlight_train: str | None = Query(None, description="Train ID to highlight"),
    lines: str | None = Query(
        None,
        description="Comma-separated line codes to filter (e.g. 'A,1,7')",
    ),
    db: AsyncSession = Depends(get_db),
) -> RouteHistoryResponse:
    """Get aggregate historical performance for all trains on a route.

    Returns on-time percentage, delay breakdown, cancellation rate, and track usage
    at the origin station. Optionally highlights a specific train for comparison
    against the route-wide statistics.

    When `hours` is provided, filters by actual departure time at the origin station
    instead of journey date, enabling sub-day time windows (e.g. past hour).
    """
    # Parse line codes filter
    line_codes = (
        [lc.strip() for lc in lines.split(",") if lc.strip()] if lines else None
    )

    logger.info(
        "get_route_history_request",
        from_station=from_station,
        to_station=to_station,
        data_source=data_source,
        days=days,
        hours=hours,
        highlight_train=highlight_train,
        lines=line_codes,
    )

    # Validate data_source
    valid_sources = [
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
            "lines": lines,
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

    # Compute route history in a dedicated session with a timeout.
    # Uses a separate session so that if the query exceeds the timeout,
    # the resulting transaction corruption doesn't poison the request's
    # main session (which caused HTTP 500 via "Can't reconnect until
    # invalid transaction is rolled back" for BART/MBTA).
    # The 45s timeout fires before the 60s command_timeout in engine.py,
    # giving clean cancellation instead of DB-level abort.
    async with get_session() as history_db:
        response = await asyncio.wait_for(
            compute_route_history(
                history_db,
                from_station,
                to_station,
                data_source,
                days,
                hours,
                lines,
                highlight_train=highlight_train,
            ),
            timeout=45.0,
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


async def compute_route_history(
    db: AsyncSession,
    from_station: str,
    to_station: str,
    data_source: str,
    days: int = 30,
    hours: int | None = None,
    lines: str | None = None,
    highlight_train: str | None = None,
) -> RouteHistoryResponse:
    """Compute route history response. Used by both the API endpoint and cache pre-warming."""
    line_codes = (
        [lc.strip() for lc in lines.split(",") if lc.strip()] if lines else None
    )
    now = now_et()
    cutoff_time = None
    if hours:
        cutoff_time = now - timedelta(hours=hours)
        start_date = cutoff_time.date()
    else:
        start_date = now.date() - timedelta(days=days)
    end_date = now.date()

    from_codes = expand_station_codes(from_station)
    to_codes = expand_station_codes(to_station)

    aggregate_stats = await _calculate_route_stats_sql(
        db,
        data_source,
        start_date,
        end_date,
        from_codes,
        to_codes,
        cutoff_time,
        now,
        line_codes=line_codes,
    )

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
            line_codes=line_codes,
        )
        if highlighted_stats["total_journeys"] > 0:
            hl_breakdown = highlighted_stats["delay_breakdown"]
            highlighted_train_data = HighlightedTrain(
                train_id=highlight_train,
                on_time_percentage=highlighted_stats["on_time_percentage"],
                on_time_source=highlighted_stats["on_time_source"],
                average_delay_minutes=highlighted_stats["average_delay_minutes"],
                average_departure_delay_minutes=highlighted_stats[
                    "average_departure_delay_minutes"
                ],
                delay_breakdown=(
                    DelayBreakdown(**hl_breakdown) if hl_breakdown else None
                ),
                track_usage_at_origin=highlighted_stats["track_usage"],
            )

    baseline_train_count = await _calculate_baseline_train_count(
        db,
        data_source,
        from_codes,
        to_codes,
        hours,
        now,
        line_codes=line_codes,
    )

    return RouteHistoryResponse(
        route=HistoricalRouteInfo(
            from_station=from_station,
            to_station=to_station,
            total_trains=aggregate_stats["total_journeys"],
            data_source=data_source,
            baseline_train_count=baseline_train_count,
        ),
        aggregate_stats=AggregateStats(
            on_time_percentage=aggregate_stats["on_time_percentage"],
            on_time_source=aggregate_stats["on_time_source"],
            average_delay_minutes=aggregate_stats["average_delay_minutes"],
            average_departure_delay_minutes=aggregate_stats[
                "average_departure_delay_minutes"
            ],
            cancellation_rate=aggregate_stats["cancellation_rate"],
            delay_breakdown=(
                DelayBreakdown(**aggregate_stats["delay_breakdown"])
                if aggregate_stats["delay_breakdown"]
                else None
            ),
            track_usage_at_origin=aggregate_stats["track_usage"],
        ),
        highlighted_train=highlighted_train_data,
    )


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
    line_codes: list[str] | None = None,
) -> dict[str, Any]:
    """Calculate route statistics using SQL aggregation instead of loading ORM objects."""

    empty_stats: dict[str, Any] = {
        "total_journeys": 0,
        "on_time_percentage": None,
        "on_time_source": None,
        "average_delay_minutes": None,
        "average_departure_delay_minutes": 0.0,
        "cancellation_rate": 0.0,
        "delay_breakdown": None,
        "track_usage": {},
    }

    # Sub-day windows (hours parameter) filter by ORIGIN DEPARTURE time.
    # "Trains in the past hour" means "trains that departed origin in the
    # past hour" — captures recently-departed in-transit trains and is
    # robust to NJT's NULL scheduled_arrival at intermediate stops (NJT
    # puts the schedule in DEP_TIME at non-terminal stops, so a destination-
    # arrival filter silently drops every NJT route ending mid-line).
    # Stats automatically fall back from arrival-based to departure-based
    # metrics when arrival data is unavailable (see destination_stops vs
    # origin_stops CTEs and the on_time_source selection below).
    origin_time_filter = ""
    if cutoff_time:
        origin_time_filter = """
            AND COALESCE(fs.actual_departure, fs.scheduled_departure) >= :cutoff_time
            AND COALESCE(fs.actual_departure, fs.scheduled_departure) <= :now_time
        """

    train_filter = ""
    if train_id_filter:
        train_filter = "AND tj.train_id = :train_id"

    line_filter = ""
    if line_codes:
        line_filter = "AND tj.line_code = ANY(:line_codes)"

    # Build the route_journeys CTE SQL (reused by stats and track queries).
    # Require an origin stop within the time window plus either a downstream
    # destination stop (the normal case) or a cancelled journey whose stop
    # list never finished backfilling (origin-only allowed so disruptions
    # still register in cancellation_rate).
    route_journeys_cte = f"""
        SELECT tj.id AS journey_id, tj.is_cancelled
        FROM train_journeys tj
        WHERE tj.data_source = :data_source
          AND tj.journey_date >= :start_date
          AND tj.journey_date <= :end_date
          {train_filter}
          {line_filter}
          AND EXISTS (
              SELECT 1 FROM journey_stops fs
              WHERE fs.journey_id = tj.id
                AND fs.station_code = ANY(:from_codes)
                {origin_time_filter}
                AND (
                    EXISTS (
                        SELECT 1 FROM journey_stops ts
                        WHERE ts.journey_id = tj.id
                          AND ts.station_code = ANY(:to_codes)
                          AND ts.stop_sequence > fs.stop_sequence
                    )
                    OR (tj.is_cancelled AND NOT tj.has_complete_journey)
                )
          )
        ORDER BY tj.journey_date DESC
        LIMIT 5000
    """

    # Single SQL query with CTEs for all aggregation.
    # Stats and track usage are combined into one query so the expensive
    # route_journeys CTE only executes once (previously ran twice).
    sql = text(f"""
        WITH route_journeys AS (
            {route_journeys_cte}
        ),
        destination_stops AS (
            SELECT DISTINCT ON (js.journey_id)
                js.journey_id,
                EXTRACT(EPOCH FROM (js.actual_arrival - js.scheduled_arrival)) / 60.0
                    AS arrival_delay_minutes
            FROM journey_stops js
            INNER JOIN route_journeys rj ON rj.journey_id = js.journey_id
            INNER JOIN train_journeys tj ON tj.id = rj.journey_id
            WHERE js.station_code = ANY(:to_codes)
              AND js.actual_arrival IS NOT NULL
              AND js.scheduled_arrival IS NOT NULL
              -- Exclude scheduled_fallback arrivals — they always show 0 delay
              -- (actual == scheduled) and inflate on-time percentages.
              -- Allow NULL arrival_source (historical stops before ~March 2026)
              -- to contribute, consistent with trains.py and summary.py.
              AND COALESCE(js.arrival_source, 'unknown') != 'scheduled_fallback'
            ORDER BY js.journey_id, js.stop_sequence ASC
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
                -- Count of non-cancelled trains with arrival data (proper denominator)
                COUNT(*) FILTER (WHERE NOT rj.is_cancelled
                    AND ds.arrival_delay_minutes IS NOT NULL)
                    AS with_arrival_data_count,
                -- Arrival delay aggregates (non-cancelled only)
                AVG(GREATEST(ds.arrival_delay_minutes, 0))
                    FILTER (WHERE NOT rj.is_cancelled AND ds.arrival_delay_minutes IS NOT NULL)
                    AS avg_arrival_delay,
                COUNT(*) FILTER (WHERE NOT rj.is_cancelled
                    AND ds.arrival_delay_minutes IS NOT NULL
                    AND ds.arrival_delay_minutes <= 5)
                    AS on_time_count,
                COUNT(*) FILTER (WHERE NOT rj.is_cancelled
                    AND ds.arrival_delay_minutes IS NOT NULL
                    AND ds.arrival_delay_minutes > 5 AND ds.arrival_delay_minutes <= 15)
                    AS slight_count,
                COUNT(*) FILTER (WHERE NOT rj.is_cancelled
                    AND ds.arrival_delay_minutes IS NOT NULL
                    AND ds.arrival_delay_minutes > 15 AND ds.arrival_delay_minutes <= 30)
                    AS significant_count,
                COUNT(*) FILTER (WHERE NOT rj.is_cancelled
                    AND ds.arrival_delay_minutes IS NOT NULL
                    AND ds.arrival_delay_minutes > 30)
                    AS major_count,
                -- Departure delay aggregates (non-cancelled with actual departure)
                AVG(GREATEST(os.departure_delay_minutes, 0))
                    FILTER (WHERE NOT rj.is_cancelled
                            AND os.departure_delay_minutes IS NOT NULL)
                    AS avg_departure_delay,
                -- Departure-based on-time (fallback when arrival data unavailable)
                COUNT(*) FILTER (WHERE NOT rj.is_cancelled
                    AND os.departure_delay_minutes IS NOT NULL)
                    AS with_departure_data_count,
                COUNT(*) FILTER (WHERE NOT rj.is_cancelled
                    AND os.departure_delay_minutes IS NOT NULL
                    AND os.departure_delay_minutes <= 5)
                    AS dep_on_time_count,
                COUNT(*) FILTER (WHERE NOT rj.is_cancelled
                    AND os.departure_delay_minutes IS NOT NULL
                    AND os.departure_delay_minutes > 5 AND os.departure_delay_minutes <= 15)
                    AS dep_slight_count,
                COUNT(*) FILTER (WHERE NOT rj.is_cancelled
                    AND os.departure_delay_minutes IS NOT NULL
                    AND os.departure_delay_minutes > 15 AND os.departure_delay_minutes <= 30)
                    AS dep_significant_count,
                COUNT(*) FILTER (WHERE NOT rj.is_cancelled
                    AND os.departure_delay_minutes IS NOT NULL
                    AND os.departure_delay_minutes > 30)
                    AS dep_major_count
            FROM route_journeys rj
            LEFT JOIN destination_stops ds ON ds.journey_id = rj.journey_id
            LEFT JOIN origin_stops os ON os.journey_id = rj.journey_id
        ),
        track_counts AS (
            SELECT js.track, COUNT(*) AS cnt
            FROM journey_stops js
            INNER JOIN route_journeys rj ON rj.journey_id = js.journey_id
            WHERE js.station_code = ANY(:from_codes)
              AND js.track IS NOT NULL
            GROUP BY js.track
        )
        SELECT s.*,
               COALESCE(
                   (SELECT json_object_agg(tc.track, tc.cnt) FROM track_counts tc),
                   '{{}}'::json
               ) AS track_json
        FROM stats s
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
    if line_codes:
        params["line_codes"] = line_codes

    result = await db.execute(sql, params)
    row = result.mappings().first()

    if not row or row["total_journeys"] == 0:
        return empty_stats

    total_journeys = row["total_journeys"]
    cancelled_count = row["cancelled_count"]
    with_arrival_data = row["with_arrival_data_count"]
    on_time_count = row["on_time_count"]
    with_departure_data = row["with_departure_data_count"]
    dep_on_time_count = row["dep_on_time_count"]
    avg_arrival = (
        float(row["avg_arrival_delay"])
        if row["avg_arrival_delay"] is not None
        else None
    )
    avg_departure = float(row["avg_departure_delay"] or 0)

    # Determine on-time percentage and source.
    # Prefer arrival-based (more accurate), fall back to departure-based when
    # arrival data is unavailable (common during disruptions when trains haven't
    # completed their journey or arrivals used scheduled_fallback).
    if with_arrival_data > 0:
        on_time_percentage: float | None = on_time_count / with_arrival_data * 100
        on_time_source = "arrival"
        delay_breakdown: dict[str, int] | None = {
            "on_time": round(on_time_count / with_arrival_data * 100),
            "slight": round(row["slight_count"] / with_arrival_data * 100),
            "significant": round(row["significant_count"] / with_arrival_data * 100),
            "major": round(row["major_count"] / with_arrival_data * 100),
        }
    elif with_departure_data > 0:
        on_time_percentage = dep_on_time_count / with_departure_data * 100
        on_time_source = "departure"
        delay_breakdown = {
            "on_time": round(dep_on_time_count / with_departure_data * 100),
            "slight": round(row["dep_slight_count"] / with_departure_data * 100),
            "significant": round(
                row["dep_significant_count"] / with_departure_data * 100
            ),
            "major": round(row["dep_major_count"] / with_departure_data * 100),
        }
    else:
        on_time_percentage = None
        on_time_source = None
        delay_breakdown = None

    # Extract track usage from the JSON aggregate in the combined query
    track_raw = row["track_json"]
    track_counts_dict: dict[str, int] = (
        json_mod.loads(track_raw) if isinstance(track_raw, str) else (track_raw or {})
    )
    track_usage: dict[str, int] = {}
    total_track_assignments = sum(track_counts_dict.values())
    if total_track_assignments > 0:
        track_usage = {
            track: round(cnt / total_track_assignments * 100)
            for track, cnt in track_counts_dict.items()
        }

    return {
        "total_journeys": total_journeys,
        "on_time_percentage": on_time_percentage,
        "on_time_source": on_time_source,
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
    line_codes: list[str] | None = None,
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
    baseline_line_filter = ""
    if line_codes:
        baseline_line_filter = "AND stt.line_code = ANY(:line_codes)"

    hour_filter = ""
    day_filter = ""

    if hours is not None and hours <= 1:
        # 1-hour window: match same hour-of-day and weekday/weekend
        hour_filter = "AND stt.hour_of_day = :current_hour"
        day_filter = """AND (
            (:is_weekend AND stt.day_of_week IN (5, 6))
            OR (NOT :is_weekend AND stt.day_of_week NOT IN (5, 6))
        )"""
    elif hours is not None and hours <= 24:
        # 24-hour window: match weekday/weekend only
        day_filter = """AND (
            (:is_weekend AND stt.day_of_week IN (5, 6))
            OR (NOT :is_weekend AND stt.day_of_week NOT IN (5, 6))
        )"""
    else:
        # 7+ day window: no time/day filter
        pass

    # Use per-day averaging: count trains per day, then average across days.
    # For weekly+ windows, multiply by 7 to get per-week baseline.
    sql = text(f"""
        WITH matching_journeys AS (
            SELECT DISTINCT stt.journey_id, stt.departure_time::date AS journey_day
            FROM segment_transit_times stt
            WHERE stt.departure_time >= :baseline_start
              AND stt.from_station_code = ANY(:from_codes)
              AND stt.data_source = :data_source
              {baseline_line_filter}
              {hour_filter}
              {day_filter}
              AND EXISTS (
                  SELECT 1 FROM segment_transit_times stt2
                  WHERE stt2.journey_id = stt.journey_id
                    AND stt2.to_station_code = ANY(:to_codes)
                    AND stt2.departure_time > stt.departure_time
              )
        ),
        daily_counts AS (
            SELECT journey_day, COUNT(*) AS day_count
            FROM matching_journeys
            GROUP BY journey_day
        )
        SELECT AVG(day_count) AS avg_per_day,
               COUNT(*) AS num_days
        FROM daily_counts
    """)

    params: dict[str, Any] = {
        "baseline_start": now - timedelta(days=30),
        "from_codes": from_codes,
        "to_codes": to_codes,
        "data_source": data_source,
    }
    if hour_filter:
        params["current_hour"] = current_hour
    if day_filter:
        params["is_weekend"] = is_weekend
    if line_codes:
        params["line_codes"] = line_codes

    try:
        result = await db.execute(sql, params)
        row = result.mappings().first()
        if not row or row["num_days"] is None or row["num_days"] < 3:
            return None

        avg_per_day = float(row["avg_per_day"])
        if hours is not None and hours >= 168:
            # Scale daily average to weekly for 7+ day windows
            avg_per_day *= 7.0
        elif hours is None:
            avg_per_day *= 7.0

        return round(avg_per_day, 1) if avg_per_day > 0 else None
    except Exception as e:
        logger.warning("baseline_train_count_query_failed", error=str(e))
        return None


async def _compute_and_cache_single_provider(
    db: AsyncSession,
    data_source: str,
    time_window_hours: int,
    max_per_segment: int,
) -> None:
    """Compute congestion for a single provider and store it in the cache.

    Used by the multi-provider cache miss path to populate per-provider cache
    entries so the merge path can assemble them on retry.
    """
    analyzer = CongestionAnalyzer()
    aggregated_segments, journeys, individual_segments = (
        await analyzer.get_network_congestion_with_trains(
            db, time_window_hours, max_per_segment, data_source
        )
    )

    # Filter out SAN station code collision
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

    # Build train positions, deduplicating by (train_id, data_source) and
    # skipping entries with no position data (e.g. trains not yet departed).
    departure_service = DepartureService()
    train_positions = []
    seen_trains: set[tuple[str, str]] = set()
    for journey in journeys:
        if journey.is_cancelled:
            continue
        if not journey.train_id or not journey.data_source:
            continue
        key = (journey.train_id, journey.data_source)
        if key in seen_trains:
            continue
        position = departure_service._calculate_train_position(journey)
        # Skip trains with no position data at all
        if (
            not position.last_departed_station_code
            and not position.at_station_code
            and not position.next_station_code
        ):
            continue
        seen_trains.add(key)
        journey_percent = None
        if journey.progress:
            journey_percent = journey.progress.journey_percent
        train_positions.append(
            TrainLocationData(
                train_id=journey.train_id,
                line=journey.line_code,
                data_source=journey.data_source,
                last_departed_station=position.last_departed_station_code,
                at_station=position.at_station_code,
                next_station=position.next_station_code,
                between_stations=position.between_stations,
                journey_percent=journey_percent,
            )
        )

    # Build API segment models
    aggregated_api_segments = [
        SegmentCongestionModel(
            from_station=s.from_station,
            to_station=s.to_station,
            from_station_name=get_station_name(s.from_station),
            to_station_name=get_station_name(s.to_station),
            data_source=s.data_source,
            congestion_level=s.congestion_level,
            congestion_factor=s.congestion_factor,
            average_delay_minutes=s.average_delay_minutes,
            sample_count=s.sample_count,
            baseline_minutes=s.baseline_minutes,
            current_average_minutes=s.avg_transit_minutes,
            cancellation_count=s.cancellation_count,
            cancellation_rate=s.cancellation_rate,
            train_count=s.train_count,
            baseline_train_count=s.baseline_train_count,
            frequency_factor=s.frequency_factor,
            frequency_level=s.frequency_level,
        )
        for s in aggregated_segments
    ]

    response = CongestionMapResponse(
        individual_segments=individual_segments,
        aggregated_segments=aggregated_api_segments,
        train_positions=train_positions,
        generated_at=now_et(),
        time_window_hours=time_window_hours,
        max_per_segment=max_per_segment,
        metadata={
            "total_individual_segments": len(individual_segments),
            "total_aggregated_segments": len(aggregated_api_segments),
            "congestion_levels": {
                level: sum(
                    1 for s in aggregated_api_segments if s.congestion_level == level
                )
                for level in ("normal", "moderate", "heavy", "severe")
            },
            "total_trains": len(train_positions),
        },
    )
    response_dict = response.model_dump(mode="json")

    cache_service = ApiCacheService()
    cache_params = {
        "time_window_hours": time_window_hours,
        "max_per_segment": max_per_segment,
        "data_source": data_source,
    }
    try:
        await cache_service.store_cached_response(
            db=db,
            endpoint="/api/v2/routes/congestion",
            params=cache_params,
            response=response_dict,
            ttl_seconds=600,
        )
    except Exception as e:
        logger.warning("cache_storage_failed", data_source=data_source, error=str(e))


@router.get("/congestion")
@handle_errors
async def get_route_congestion(
    time_window_hours: int = Query(
        2,
        ge=1,
        le=3,
        description=(
            "Hours to look back. Only 2 (default, all systems) and 3 (NJT extended)"
            " are pre-computed; larger windows are rejected because live aggregation"
            " exceeds the query timeout for high-volume providers."
        ),
    ),
    max_per_segment: int = Query(
        100,
        ge=0,
        le=500,
        description="Max individual journeys per segment (0 = unlimited)",
    ),
    data_source: str | None = Query(
        None,
        description="Filter by single data source (NJT, AMTRAK, PATH, etc). Mutually exclusive with systems.",
    ),
    systems: str | None = Query(
        None,
        description="Comma-separated list of systems to include (e.g. NJT,PATH,AMTRAK). "
        "Omit for all systems. Mutually exclusive with data_source.",
    ),
    force_refresh: bool = Query(False, description="Force bypass cache and recompute"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Get network congestion levels based on recent train performance.

    Analyzes train journeys within a lookback window (minimum 2 hours) and returns
    per-segment congestion factors, aggregated congestion levels, and live train
    positions. Results are cached for 10 minutes.

    Use ``systems`` to request a subset of providers (e.g. ``systems=NJT,PATH``).
    When omitted, all systems are returned by merging per-provider caches.
    The legacy ``data_source`` parameter still works for single-provider requests.
    """

    # Enforce minimum 2-hour window for meaningful congestion data across all systems
    effective_time_window = max(time_window_hours, 2)

    # Parse systems parameter
    requested_systems: list[str] | None = None
    if systems:
        requested_systems = [s.strip().upper() for s in systems.split(",") if s.strip()]
    elif data_source:
        # Legacy single data_source is equivalent to systems=<data_source>
        requested_systems = [data_source.upper()]

    # --- Cache lookup ---
    if not force_refresh:
        cache_service = ApiCacheService()

        if requested_systems and len(requested_systems) == 1:
            # Single-provider: direct cache lookup (fast path)
            cache_params = {
                "time_window_hours": effective_time_window,
                "max_per_segment": max_per_segment,
                "data_source": requested_systems[0],
            }
            cached = await cache_service.get_cached_response(
                db, "/api/v2/routes/congestion", cache_params
            )
            if cached:
                return Response(
                    content=json_mod.dumps(cached),
                    media_type="application/json",
                )

        else:
            # Multi-provider or all: merge per-provider caches
            from trackrat.services.api_cache import CONGESTION_PROVIDERS

            merge_systems = requested_systems or CONGESTION_PROVIDERS
            merged = await cache_service.merge_congestion_from_provider_caches(
                db, merge_systems, effective_time_window, max_per_segment
            )
            if merged:
                return Response(
                    content=json_mod.dumps(merged),
                    media_type="application/json",
                )

    # --- Cache miss: compute directly ---
    # For single-provider requests, query that provider.
    # For multi/all, query each provider individually so each gets cached.
    if requested_systems and len(requested_systems) > 1:
        # Multi-provider miss: compute each provider individually so each gets
        # cached, then re-merge.  This avoids the expensive all-provider query
        # and ensures the cache is populated for future requests.
        cache_service = ApiCacheService()
        for system in requested_systems:
            try:
                # Use a fresh session per provider so a timeout in one
                # doesn't poison the connection for subsequent iterations.
                async with get_session() as provider_db:
                    await _compute_and_cache_single_provider(
                        provider_db, system, effective_time_window, max_per_segment
                    )
            except Exception as e:
                error_name = type(e).__name__
                if (
                    "QueryCanceled" in error_name
                    or "statement timeout" in str(e).lower()
                ):
                    logger.warning(
                        "congestion_query_timeout",
                        data_source=system,
                        time_window_hours=effective_time_window,
                    )
                    continue  # Skip this provider, try others
                raise

        # Re-merge from the freshly-populated caches (fresh session in case
        # the request db was never used or was poisoned by an earlier path).
        async with get_session() as merge_db:
            merged = await cache_service.merge_congestion_from_provider_caches(
                merge_db, requested_systems, effective_time_window, max_per_segment
            )
        if merged:
            return Response(
                content=json_mod.dumps(merged),
                media_type="application/json",
            )
        # All providers failed — return 503
        raise HTTPException(
            status_code=503,
            detail="Congestion data is temporarily unavailable. Please retry shortly.",
            headers={"Retry-After": "60"},
        )

    query_data_source = (
        requested_systems[0]
        if (requested_systems and len(requested_systems) == 1)
        else None
    )

    analyzer = CongestionAnalyzer()
    try:
        aggregated_segments, journeys, individual_segments = (
            await analyzer.get_network_congestion_with_trains(
                db, effective_time_window, max_per_segment, query_data_source
            )
        )
    except Exception as e:
        error_name = type(e).__name__
        if "QueryCanceled" in error_name or "statement timeout" in str(e).lower():
            logger.warning(
                "congestion_query_timeout",
                data_source=query_data_source,
                time_window_hours=effective_time_window,
            )
            raise HTTPException(
                status_code=503,
                detail="Congestion data is temporarily unavailable. Please retry shortly.",
                headers={"Retry-After": "60"},
            ) from None
        raise

    # Filter out SAN station code collision (Amtrak disambiguation TODO)
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

    # Extract train positions from journeys, deduplicating by (train_id, data_source)
    # and skipping entries with no position data.
    departure_service = DepartureService()
    train_positions = []
    seen_trains: set[tuple[str, str]] = set()

    for journey in journeys:
        if journey.is_cancelled:
            continue
        if not journey.train_id or not journey.data_source:
            continue
        key = (journey.train_id, journey.data_source)
        if key in seen_trains:
            continue

        position = departure_service._calculate_train_position(journey)

        # Skip trains with no position data at all
        if (
            not position.last_departed_station_code
            and not position.at_station_code
            and not position.next_station_code
        ):
            continue
        seen_trains.add(key)

        journey_percent = None
        if journey.progress:
            journey_percent = journey.progress.journey_percent

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
    response_dict = response.model_dump(mode="json")

    # Store in cache for future requests (skip for multi-provider;
    # those are assembled from per-provider caches by the merge path)
    if query_data_source is not None:
        try:
            cache_params = {
                "time_window_hours": effective_time_window,
                "max_per_segment": max_per_segment,
                "data_source": query_data_source,
            }
            cache_service = ApiCacheService()
            await cache_service.store_cached_response(
                db=db,
                endpoint="/api/v2/routes/congestion",
                params=cache_params,
                response=response_dict,
                ttl_seconds=600,
            )
        except Exception as e:
            logger.warning("cache_storage_failed", error=str(e))

    return Response(
        content=json_mod.dumps(response_dict), media_type="application/json"
    )


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
        description="Filter by data source (NJT, AMTRAK, PATH, PATCO, LIRR, MNR, SUBWAY, METRA, WMATA, MBTA)",
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
    journeys = list(result.scalars().unique().all())

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
        description="Filter by data source (NJT, AMTRAK, PATH, PATCO, LIRR, MNR, SUBWAY, METRA, WMATA, MBTA)",
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

    # Check cache first (train scope is user-specific, skip caching)
    cache_service = ApiCacheService()
    cache_params = {
        "scope": scope,
        "from_station": from_station,
        "to_station": to_station,
        "train_id": train_id,
        "data_source": data_source,
    }
    if scope != "train":
        cached_response = await cache_service.get_cached_response(
            db=db,
            endpoint="/api/v2/routes/summary",
            params=cache_params,
        )
        if cached_response:
            try:
                return OperationsSummaryResponse(**cached_response)
            except (TypeError, ValueError) as e:
                logger.warning(
                    "route_summary_cache_deserialization_failed",
                    error=str(e),
                )
                await cache_service.invalidate_cache_entry(
                    db=db,
                    endpoint="/api/v2/routes/summary",
                    params=cache_params,
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

        def _convert_train_dict(
            source: dict[str, list[TrainDelaySummary]] | None,
        ) -> dict[str, list[TrainDelaySummaryResponse]] | None:
            if not source:
                return None
            return {
                key: [
                    TrainDelaySummaryResponse(
                        train_id=t.train_id,
                        delay_minutes=t.delay_minutes,
                        category=t.category,  # type: ignore[arg-type]
                        scheduled_departure=t.scheduled_departure,
                    )
                    for t in trains
                ]
                for key, trains in source.items()
            }

        metrics = SummaryMetricsResponse(
            on_time_percentage=summary.metrics.on_time_percentage,
            average_delay_minutes=summary.metrics.average_delay_minutes,
            cancellation_count=summary.metrics.cancellation_count,
            train_count=summary.metrics.train_count,
            trains_by_category=_convert_train_dict(summary.metrics.trains_by_category),
            trains_by_headway=_convert_train_dict(summary.metrics.trains_by_headway),
        )

    response = OperationsSummaryResponse(
        headline=summary.headline,
        body=summary.body,
        scope=summary.scope,
        time_window_minutes=summary.time_window_minutes,
        data_freshness_seconds=summary.data_freshness_seconds,
        generated_at=summary.generated_at,
        metrics=metrics,
    )

    # Store in cache (skip train scope - user-specific)
    if scope != "train":
        try:
            await cache_service.store_cached_response(
                db=db,
                endpoint="/api/v2/routes/summary",
                params=cache_params,
                response=response.model_dump(mode="json"),
                ttl_seconds=120,
            )
        except Exception as e:
            logger.warning("route_summary_cache_storage_failed", error=str(e))

    return response
