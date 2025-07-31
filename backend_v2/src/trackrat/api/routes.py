"""
Route API endpoints for TrackRat V2.

Provides route-based historical analysis independent of specific trains.
"""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from trackrat.api.utils import handle_errors
from trackrat.config.stations import get_station_coordinates
from trackrat.db.engine import get_db
from trackrat.models.api import (
    AggregateStats,
    CongestionMapResponse,
    DelayBreakdown,
    HighlightedTrain,
    HistoricalRouteInfo,
    RouteHistoryResponse,
    SegmentCongestion as SegmentCongestionModel,
)
from trackrat.models.database import TrainJourney
from trackrat.services.congestion import CongestionAnalyzer
from trackrat.utils.time import now_et

logger = get_logger()

router = APIRouter(prefix="/api/v2/routes", tags=["routes"])


@router.get("/history", response_model=RouteHistoryResponse)
@handle_errors
async def get_route_history(
    from_station: str = Query(
        ..., min_length=1, max_length=3, description="Origin station code"
    ),
    to_station: str = Query(
        ..., min_length=1, max_length=3, description="Destination station code"
    ),
    data_source: str = Query(..., description="Data source (NJT or AMTRAK)"),
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    highlight_train: str | None = Query(None, description="Train ID to highlight"),
    db: AsyncSession = Depends(get_db),
) -> RouteHistoryResponse:
    """Get historical data for all trains on a route."""
    logger.info(
        "get_route_history_request",
        from_station=from_station,
        to_station=to_station,
        data_source=data_source,
        days=days,
        highlight_train=highlight_train,
    )

    # Validate data_source
    if data_source not in ["NJT", "AMTRAK"]:
        raise HTTPException(
            status_code=400, detail="data_source must be 'NJT' or 'AMTRAK'"
        )

    # Calculate date range
    end_date = now_et().date()
    start_date = end_date - timedelta(days=days)

    # Query all journeys for this data source and date range
    stmt = (
        select(TrainJourney)
        .where(
            and_(
                TrainJourney.data_source == data_source,
                TrainJourney.journey_date >= start_date,
                TrainJourney.journey_date <= end_date,
            )
        )
        .options(selectinload(TrainJourney.stops))
    )

    result = await db.execute(stmt)
    all_journeys = list(result.scalars().all())

    # Filter to only journeys that travel from origin to destination
    route_journeys = []
    highlighted_train_journeys = []

    for journey in all_journeys:
        from_stop = None
        to_stop = None

        # Find the origin and destination stops
        for stop in journey.stops:
            if stop.station_code == from_station:
                from_stop = stop
            elif stop.station_code == to_station:
                to_stop = stop

        # Include if both stations found and in correct order
        if (
            from_stop
            and to_stop
            and (from_stop.stop_sequence or 0) < (to_stop.stop_sequence or 0)
        ):
            route_journeys.append(journey)

            # Also collect for highlighted train if specified
            if highlight_train and journey.train_id == highlight_train:
                highlighted_train_journeys.append(journey)

    # Calculate aggregate statistics for all route journeys
    aggregate_stats = _calculate_route_stats(route_journeys, from_station)

    # Calculate highlighted train statistics if specified
    highlighted_train_data = None
    if highlight_train and highlighted_train_journeys:
        highlighted_stats = _calculate_route_stats(
            highlighted_train_journeys, from_station
        )
        highlighted_train_data = HighlightedTrain(
            train_id=highlight_train,
            on_time_percentage=highlighted_stats["on_time_percentage"],
            average_delay_minutes=highlighted_stats["average_delay_minutes"],
            delay_breakdown=DelayBreakdown(**highlighted_stats["delay_breakdown"]),
            track_usage_at_origin=highlighted_stats["track_usage"],
        )

    return RouteHistoryResponse(
        route=HistoricalRouteInfo(
            from_station=from_station,
            to_station=to_station,
            total_trains=len(route_journeys),
            data_source=data_source,
        ),
        aggregate_stats=AggregateStats(
            on_time_percentage=aggregate_stats["on_time_percentage"],
            average_delay_minutes=aggregate_stats["average_delay_minutes"],
            cancellation_rate=aggregate_stats["cancellation_rate"],
            delay_breakdown=DelayBreakdown(**aggregate_stats["delay_breakdown"]),
            track_usage_at_origin=aggregate_stats["track_usage"],
        ),
        highlighted_train=highlighted_train_data,
    )


def _calculate_route_stats(
    journeys: list[TrainJourney], origin_station: str
) -> dict[str, Any]:
    """Calculate statistics for a list of journeys, focusing on origin station tracks."""
    if not journeys:
        return {
            "on_time_percentage": 0.0,
            "average_delay_minutes": 0.0,
            "cancellation_rate": 0.0,
            "delay_breakdown": {
                "on_time": 0,
                "slight": 0,
                "significant": 0,
                "major": 0,
            },
            "track_usage": {},
        }

    total_delay = 0
    on_time_count = 0
    cancelled_count = 0
    delay_categories = {"on_time": 0, "slight": 0, "significant": 0, "major": 0}
    track_usage_counts = {}

    for journey in journeys:
        # Get last stop for delay calculation
        if journey.stops:
            last_stop = max(journey.stops, key=lambda s: s.stop_sequence or 0)

            # Calculate arrival delay
            arrival_delay = 0
            if last_stop.actual_arrival and last_stop.scheduled_arrival:
                arrival_delay = int(
                    (
                        last_stop.actual_arrival - last_stop.scheduled_arrival
                    ).total_seconds()
                    / 60
                )

            if journey.is_cancelled:
                cancelled_count += 1
            else:
                # Categorize delay
                if arrival_delay <= 5:
                    on_time_count += 1
                    delay_categories["on_time"] += 1
                elif arrival_delay <= 15:
                    delay_categories["slight"] += 1
                elif arrival_delay <= 30:
                    delay_categories["significant"] += 1
                else:
                    delay_categories["major"] += 1

                total_delay += max(0, arrival_delay)

        # Count track usage ONLY at origin station
        for stop in journey.stops:
            if stop.station_code == origin_station and stop.track:
                if stop.track not in track_usage_counts:
                    track_usage_counts[stop.track] = 0
                track_usage_counts[stop.track] += 1

    # Calculate percentages
    total_journeys = len(journeys)
    non_cancelled_journeys = total_journeys - cancelled_count

    # Delay breakdown percentages
    delay_breakdown = {}
    if non_cancelled_journeys > 0:
        delay_breakdown = {
            "on_time": round(
                delay_categories["on_time"] / non_cancelled_journeys * 100
            ),
            "slight": round(delay_categories["slight"] / non_cancelled_journeys * 100),
            "significant": round(
                delay_categories["significant"] / non_cancelled_journeys * 100
            ),
            "major": round(delay_categories["major"] / non_cancelled_journeys * 100),
        }
    else:
        delay_breakdown = {"on_time": 0, "slight": 0, "significant": 0, "major": 0}

    # Track usage percentages
    track_usage = {}
    total_track_assignments = sum(track_usage_counts.values())
    if total_track_assignments > 0:
        track_usage = {
            track: round(count / total_track_assignments * 100)
            for track, count in track_usage_counts.items()
        }

    return {
        "on_time_percentage": (
            (on_time_count / total_journeys * 100) if total_journeys > 0 else 0
        ),
        "average_delay_minutes": (
            (total_delay / non_cancelled_journeys) if non_cancelled_journeys > 0 else 0
        ),
        "cancellation_rate": (
            (cancelled_count / total_journeys * 100) if total_journeys > 0 else 0
        ),
        "delay_breakdown": delay_breakdown,
        "track_usage": track_usage,
    }


@router.get("/congestion", response_model=CongestionMapResponse)
@handle_errors
async def get_route_congestion(
    time_window_hours: int = Query(3, ge=1, le=24, description="Hours to look back"),
    data_source: str | None = Query(None, description="Filter by data source (NJT or AMTRAK)"),
    db: AsyncSession = Depends(get_db),
) -> CongestionMapResponse:
    """Get current congestion levels for all route segments."""
    
    analyzer = CongestionAnalyzer()
    congestion_data = await analyzer.get_network_congestion(db, time_window_hours)
    
    # Filter by data source if specified
    if data_source:
        congestion_data = [c for c in congestion_data if c.data_source == data_source]
    
    # Convert to API models and add station coordinates
    segments = []
    for segment in congestion_data:
        segment_model = SegmentCongestionModel(
            from_station=segment.from_station,
            to_station=segment.to_station,
            data_source=segment.data_source,
            congestion_factor=segment.congestion_factor,
            congestion_level=segment.congestion_level,
            color=segment.color,
            avg_transit_minutes=segment.avg_transit_minutes,
            baseline_minutes=segment.baseline_minutes,
            sample_count=segment.sample_count,
            last_updated=segment.last_updated,
            from_station_coords=get_station_coordinates(segment.from_station),
            to_station_coords=get_station_coordinates(segment.to_station),
        )
        segments.append(segment_model)
    
    return CongestionMapResponse(
        segments=segments,
        generated_at=now_et(),
        time_window_hours=time_window_hours,
        metadata={
            "total_segments": len(segments),
            "congestion_levels": {
                "normal": len([s for s in segments if s.congestion_level == "normal"]),
                "moderate": len([s for s in segments if s.congestion_level == "moderate"]),
                "heavy": len([s for s in segments if s.congestion_level == "heavy"]),
                "severe": len([s for s in segments if s.congestion_level == "severe"]),
            },
        },
    )
