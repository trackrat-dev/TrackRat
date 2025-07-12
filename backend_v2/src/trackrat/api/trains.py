"""
Train API endpoints for TrackRat V2.

Implements the API design from V2_BACKEND_API.md.
"""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from trackrat.api.utils import handle_errors
from trackrat.collectors.njt.client import NJTransitClient
from trackrat.db.engine import get_db
from trackrat.models.api import (
    CurrentStatus,
    DataFreshness,
    DeparturesResponse,
    HistoricalJourney,
    JourneyProgress,
    LineInfo,
    RouteInfo,
    SimpleStationInfo,
    StopDetails,
    TrainDetails,
    TrainDetailsResponse,
    TrainHistoryResponse,
    TrainStatus,
)
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.departure import DepartureService
from trackrat.services.jit import JustInTimeUpdateService
from trackrat.utils.time import calculate_delay, now_et, safe_datetime_subtract

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2/trains", tags=["trains"])


@router.get("/departures", response_model=DeparturesResponse)
@handle_errors
async def get_departures(
    from_station: str = Query(
        ...,
        alias="from",
        min_length=2,
        max_length=2,
        description="Departure station code",
    ),
    to_station: str | None = Query(
        None, alias="to", min_length=2, max_length=2, description="Arrival station code"
    ),
    time_from: datetime | None = Query(
        None, description="Start time (defaults to now)"
    ),
    time_to: datetime | None = Query(
        None, description="End time (defaults to +6 hours)"
    ),
    limit: int = Query(50, le=100, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
) -> DeparturesResponse:
    """Get train departures between stations."""
    logger.info(
        "get_departures_request",
        from_station=from_station,
        to_station=to_station,
        time_from=time_from,
        time_to=time_to,
    )

    service = DepartureService()
    return await service.get_departures(
        db, from_station, to_station, time_from, time_to, limit
    )


@router.get("/{train_id}", response_model=TrainDetailsResponse)
@handle_errors
async def get_train_details(
    train_id: str = Path(..., description="Train ID"),
    date: date | None = Query(None, description="Journey date (YYYY-MM-DD)"),
    refresh: bool = Query(False, description="Force data refresh"),
    db: AsyncSession = Depends(get_db),
) -> TrainDetailsResponse:
    """Get detailed information for a specific train."""
    logger.info(
        "get_train_details_request", train_id=train_id, date=date, refresh=refresh
    )

    # Default to today
    if date is None:
        date = now_et().date()

    # Get fresh train data
    njt_client = NJTransitClient()
    try:
        async with JustInTimeUpdateService(njt_client) as jit_service:
            journey = await jit_service.get_fresh_train(
                db, train_id, date, force_refresh=refresh
            )
    finally:
        await njt_client.close()

    if not journey:
        raise HTTPException(
            status_code=404, detail=f"Train {train_id} not found for date {date}"
        )

    # Build stop details
    stops = []
    for stop in sorted(journey.stops, key=lambda s: s.stop_sequence or 0):
        stop_detail = StopDetails(
            station=SimpleStationInfo(
                code=stop.station_code,
                name=stop.station_name,
            ),
            sequence=stop.stop_sequence,
            scheduled_arrival=stop.scheduled_arrival,
            scheduled_departure=stop.scheduled_departure,
            actual_arrival=stop.actual_arrival,
            actual_departure=stop.actual_departure,
            estimated_arrival=calculate_estimated_times(stop, journey)[0],
            estimated_departure=calculate_estimated_times(stop, journey)[1],
            track=stop.track,
            status=determine_stop_status(stop).value,
            delay_minutes=calculate_stop_delay(stop),
            departed=stop.departed,
        )
        stops.append(stop_detail)

    # Determine current status
    current_status = determine_current_status(journey)

    # Build response
    train_details = TrainDetails(
        train_id=journey.train_id,
        journey_date=journey.journey_date,
        line=LineInfo(
            code=journey.line_code,
            name=journey.line_name or journey.line_code,
            color=journey.line_color or "#000000",
        ),
        route=RouteInfo(
            origin=get_first_stop_name(journey),
            destination=journey.destination,
            origin_code=journey.origin_station_code,
            destination_code=journey.terminal_station_code,
        ),
        current_status=current_status,
        stops=stops,
        data_freshness=DataFreshness(
            last_updated=journey.last_updated_at or journey.first_seen_at or now_et(),
            age_seconds=int(
                safe_datetime_subtract(
                    now_et(),
                    journey.last_updated_at or journey.first_seen_at or now_et(),
                ).total_seconds()
            ),
            update_count=journey.update_count,
            collection_method="just_in_time" if refresh else "scheduled",
        ),
        data_source=journey.data_source or "NJT",
    )

    return TrainDetailsResponse(train=train_details)


@router.get("/{train_id}/history", response_model=TrainHistoryResponse)
@handle_errors
async def get_train_history(
    train_id: str = Path(..., description="Train ID"),
    days: int = Query(30, ge=1, le=90, description="Number of days of history"),
    db: AsyncSession = Depends(get_db),
) -> TrainHistoryResponse:
    """Get historical data for a train."""
    logger.info("get_train_history_request", train_id=train_id, days=days)

    # Calculate date range
    end_date = now_et().date()
    start_date = end_date - timedelta(days=days)

    # Query historical journeys
    stmt = (
        select(TrainJourney)
        .where(
            and_(
                TrainJourney.train_id == train_id,
                TrainJourney.journey_date >= start_date,
                TrainJourney.journey_date <= end_date,
            )
        )
        .options(selectinload(TrainJourney.stops))
        .order_by(TrainJourney.journey_date.desc())
    )

    result = await db.execute(stmt)
    journeys = list(result.scalars().all())

    # Build historical data
    historical_journeys = []
    total_delay = 0
    on_time_count = 0
    cancelled_count = 0

    for journey in journeys:
        # Get key stops
        first_stop = (
            min(journey.stops, key=lambda s: s.stop_sequence or 0)
            if journey.stops
            else None
        )
        last_stop = (
            max(journey.stops, key=lambda s: s.stop_sequence or 0)
            if journey.stops
            else None
        )

        if not first_stop or not last_stop:
            continue

        # Calculate delays
        departure_delay = (
            calculate_delay(first_stop.scheduled_departure, first_stop.actual_departure)
            if first_stop.actual_departure and first_stop.scheduled_departure
            else 0
        )

        arrival_delay = (
            calculate_delay(last_stop.scheduled_arrival, last_stop.actual_arrival)
            if last_stop.actual_arrival and last_stop.scheduled_arrival
            else 0
        )

        # Track assignments
        track_assignments = {
            stop.station_code: stop.track for stop in journey.stops if stop.track
        }

        historical_journey = HistoricalJourney(
            journey_date=journey.journey_date,
            scheduled_departure=journey.scheduled_departure,
            actual_departure=journey.actual_departure,
            scheduled_arrival=journey.scheduled_arrival,
            actual_arrival=journey.actual_arrival,
            delay_minutes=max(departure_delay, arrival_delay),
            was_cancelled=journey.is_cancelled,
            track_assignments=track_assignments,
        )

        historical_journeys.append(historical_journey)

        # Update statistics
        if journey.is_cancelled:
            cancelled_count += 1
        elif arrival_delay <= 5:  # Consider on-time if <= 5 minutes late
            on_time_count += 1

        total_delay += arrival_delay

    # Calculate statistics
    total_journeys = len(historical_journeys)
    statistics = {
        "total_journeys": total_journeys,
        "on_time_percentage": (
            (on_time_count / total_journeys * 100) if total_journeys > 0 else 0
        ),
        "average_delay_minutes": (
            (total_delay / total_journeys) if total_journeys > 0 else 0
        ),
        "cancellation_rate": (
            (cancelled_count / total_journeys * 100) if total_journeys > 0 else 0
        ),
    }

    return TrainHistoryResponse(
        train_id=train_id, journeys=historical_journeys, statistics=statistics
    )


# Helper functions


def calculate_journey_progress(
    journey: TrainJourney, from_stop: JourneyStop
) -> JourneyProgress:
    """Calculate journey progress information."""
    stops = sorted(journey.stops, key=lambda s: s.stop_sequence or 0)

    # Find completed stops
    completed = sum(
        1
        for s in stops
        if s.departed and (s.stop_sequence or 0) <= (from_stop.stop_sequence or 0)
    )
    total = len(stops)

    # Find current location
    current_location = journey.origin_station_code
    next_stop = None

    for i, stop in enumerate(stops):
        if stop.departed:
            current_location = stop.station_code
        else:
            if i > 0:
                current_location = (
                    f"Between {stops[i-1].station_code} and {stop.station_code}"
                )
            next_stop = stop.station_code
            break

    return JourneyProgress(
        completed_stops=completed,
        total_stops=total,
        percentage=int((completed / total) * 100) if total > 0 else 0,
        current_location=current_location,
        next_stop=next_stop,
    )


def determine_stop_status(stop: JourneyStop) -> TrainStatus:
    """Determine the status for a stop."""
    if stop.departed:
        return TrainStatus.DEPARTED
    elif stop.track:
        return TrainStatus.BOARDING
    elif stop.status == "Cancelled":
        return TrainStatus.CANCELLED
    elif stop.status == "Late":
        return TrainStatus.LATE
    else:
        return TrainStatus.ON_TIME


def determine_current_status(journey: TrainJourney) -> CurrentStatus:
    """Determine current status of a journey."""
    if journey.is_cancelled:
        status = TrainStatus.CANCELLED
        location = "Cancelled"
    elif journey.is_completed:
        status = TrainStatus.ARRIVED
        location = journey.destination or "Unknown"
    else:
        # Find current position
        status = TrainStatus.IN_TRANSIT
        location = "Unknown"

        stops = sorted(journey.stops, key=lambda s: s.stop_sequence or 0)
        for i, stop in enumerate(stops):
            if not stop.departed:
                if stop.track:
                    status = TrainStatus.BOARDING
                    location = f"At {stop.station_name}"
                else:
                    status = TrainStatus.IN_TRANSIT
                    if i > 0:
                        location = f"Approaching {stop.station_name}"
                    else:
                        status = TrainStatus.ON_TIME
                        location = stop.station_name or "Unknown"
                break
            else:
                location = f"Departed {stop.station_name}"

    # Calculate overall delay
    delay = 0
    for stop in journey.stops:
        if stop.departed and stop.actual_departure and stop.scheduled_departure:
            delay = calculate_delay(stop.scheduled_departure, stop.actual_departure)

    return CurrentStatus(
        status=status,
        location=location,
        delay_minutes=delay,
        is_cancelled=journey.is_cancelled,
        is_completed=journey.is_completed,
        last_update=journey.last_updated_at,
    )


def calculate_duration(from_stop: JourneyStop, to_stop: JourneyStop | None) -> int:
    """Calculate duration in minutes between stops."""
    if not to_stop:
        return 0

    if from_stop.scheduled_departure and to_stop.scheduled_arrival:
        delta = to_stop.scheduled_arrival - from_stop.scheduled_departure
        return int(delta.total_seconds() / 60)

    return 0


def count_stops_between(
    journey: TrainJourney, from_stop: JourneyStop, to_stop: JourneyStop
) -> int:
    """Count stops between two stops."""
    count = 0
    for stop in journey.stops:
        if (
            (from_stop.stop_sequence or 0)
            < (stop.stop_sequence or 0)
            < (to_stop.stop_sequence or 0)
        ):
            count += 1
    return count


def calculate_stop_delay(stop: JourneyStop) -> int:
    """Calculate delay for a stop."""
    if stop.departed and stop.actual_departure and stop.scheduled_departure:
        return calculate_delay(stop.scheduled_departure, stop.actual_departure)
    elif stop.departed and stop.actual_arrival and stop.scheduled_arrival:
        return calculate_delay(stop.scheduled_arrival, stop.actual_arrival)
    return 0


def calculate_estimated_times(
    stop: JourneyStop, journey: TrainJourney
) -> tuple[datetime | None, datetime | None]:
    """Calculate estimated times for future stops based on current delay.

    Returns:
        Tuple of (estimated_arrival, estimated_departure)
    """
    if stop.departed or journey.is_cancelled:
        return (None, None)

    # Find the current delay from last departed stop
    current_delay = 0
    for s in sorted(journey.stops, key=lambda x: x.stop_sequence or 0, reverse=True):
        if s.departed and s.actual_departure and s.scheduled_departure:
            current_delay = calculate_delay(s.scheduled_departure, s.actual_departure)
            break

    if current_delay > 0:
        estimated_arrival = (
            stop.scheduled_arrival + timedelta(minutes=current_delay)
            if stop.scheduled_arrival
            else None
        )
        estimated_departure = (
            stop.scheduled_departure + timedelta(minutes=current_delay)
            if stop.scheduled_departure
            else None
        )
        return (estimated_arrival, estimated_departure)

    return (None, None)


def get_first_stop_name(journey: TrainJourney) -> str:
    """Get the name of the first stop."""
    if journey.stops:
        first_stop = min(journey.stops, key=lambda s: s.stop_sequence or 0)
        return first_stop.station_name or journey.origin_station_code or "Unknown"
    return journey.origin_station_code or "Unknown"
