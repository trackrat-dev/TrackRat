"""
Route API endpoints for TrackRat V2.

Provides route-based historical analysis independent of specific trains.
"""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from trackrat.api.utils import handle_errors
from trackrat.config.stations import get_station_name
from trackrat.db.engine import get_db
from trackrat.models.api import (
    AggregateStats,
    CongestionMapResponse,
    DelayBreakdown,
    HighlightedTrain,
    HistoricalRouteInfo,
    RouteHistoryResponse,
    SegmentTrainDetail,
    SegmentTrainDetailsResponse,
    TrainLocationData,
)
from trackrat.models.api import (
    SegmentCongestion as SegmentCongestionModel,
)
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.congestion import CongestionAnalyzer
from trackrat.services.departure import DepartureService
from trackrat.utils.time import ensure_timezone_aware, now_et

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
    track_usage_counts: dict[str, int] = {}

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
    delay_breakdown: dict[str, int] = {}
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
    track_usage: dict[str, int] = {}
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
    data_source: str | None = Query(
        None, description="Filter by data source (NJT or AMTRAK)"
    ),
    db: AsyncSession = Depends(get_db),
) -> CongestionMapResponse:
    """Get current congestion levels for all route segments."""

    analyzer = CongestionAnalyzer()
    congestion_data, journeys = await analyzer.get_network_congestion_with_trains(
        db, time_window_hours
    )

    # Filter by data source if specified
    if data_source:
        congestion_data = [c for c in congestion_data if c.data_source == data_source]
        journeys = [j for j in journeys if j.data_source == data_source]

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

    # Convert to API models and add station names
    segments = []
    for segment in congestion_data:
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
        )
        segments.append(segment_model)

    return CongestionMapResponse(
        segments=segments,
        train_positions=train_positions,
        generated_at=now_et(),
        time_window_hours=time_window_hours,
        metadata={
            "total_segments": len(segments),
            "congestion_levels": {
                "normal": len([s for s in segments if s.congestion_level == "normal"]),
                "moderate": len(
                    [s for s in segments if s.congestion_level == "moderate"]
                ),
                "heavy": len([s for s in segments if s.congestion_level == "heavy"]),
                "severe": len([s for s in segments if s.congestion_level == "severe"]),
            },
            "total_trains": len(train_positions),
        },
    )


@router.get(
    "/segments/{from_station}/{to_station}/trains",
    response_model=SegmentTrainDetailsResponse,
)
@handle_errors
async def get_segment_train_details(
    from_station: str,
    to_station: str,
    data_source: str | None = Query(None, description="Filter by NJT or AMTRAK"),
    start_time: datetime | None = Query(None, description="Start time (ISO format)"),
    end_time: datetime | None = Query(None, description="End time (ISO format)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum trains to return"),
    status: str | None = Query(
        None,
        description="Filter by delay status: on_time, delayed, significantly_delayed",
        regex="^(on_time|delayed|significantly_delayed)$",
    ),
    db: AsyncSession = Depends(get_db),
) -> SegmentTrainDetailsResponse:
    """Get detailed train records for a specific route segment using on-the-fly calculation."""

    # Default time window to 3 hours ago if not specified
    if not end_time:
        end_time = now_et()
    if not start_time:
        start_time = end_time - timedelta(hours=3)

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

    # Query journeys that include both stations and are within time window
    stmt = (
        select(TrainJourney)
        .join(
            JourneyStop,
            and_(
                JourneyStop.journey_id == TrainJourney.id,
                JourneyStop.station_code.in_([from_station, to_station]),
            ),
        )
        .where(
            and_(
                TrainJourney.scheduled_departure >= start_time,
                TrainJourney.scheduled_departure <= end_time,
                # TrainJourney.has_complete_journey == True,
            )
        )
        .group_by(TrainJourney.id)
        .having(func.count(distinct(JourneyStop.station_code)) == 2)
        .options(selectinload(TrainJourney.stops))
        .order_by(TrainJourney.last_updated_at.desc())
    )

    # Apply data source filter if specified
    if data_source:
        stmt = stmt.where(TrainJourney.data_source == data_source)

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

    for stop in journey.stops:
        if stop.station_code == from_station:
            from_stop = stop
        elif stop.station_code == to_station:
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
