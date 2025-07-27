"""
Train API endpoints for TrackRat V2.

Implements the V2 API design documented in backend_v2/CLAUDE.md.
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
    DataFreshness,
    DeparturesResponse,
    HistoricalJourney,
    LineInfo,
    OccupiedTracksResponse,
    RawStopStatus,
    RouteInfo,
    SimpleStationInfo,
    StopDetails,
    TrainDetails,
    TrainDetailsResponse,
    TrainHistoryResponse,
    TrainPosition,
)
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.departure import DepartureService
from trackrat.services.jit import JustInTimeUpdateService
from trackrat.utils.time import now_et, safe_datetime_subtract
from trackrat.utils.train import is_amtrak_train

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2/trains", tags=["trains"])


@router.get("/departures", response_model=DeparturesResponse)
@handle_errors
async def get_departures(
    from_station: str = Query(
        ...,
        alias="from",
        min_length=2,
        max_length=3,
        description="Departure station code",
    ),
    to_station: str | None = Query(
        None, alias="to", min_length=2, max_length=3, description="Arrival station code"
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
    # For Amtrak trains, we don't need an NJT client
    njt_client = None
    if not is_amtrak_train(train_id):
        njt_client = NJTransitClient()

    try:
        async with JustInTimeUpdateService(njt_client) as jit_service:
            journey = await jit_service.get_fresh_train(
                db, train_id, date, force_refresh=refresh
            )
    finally:
        if njt_client:
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
            stop_sequence=stop.stop_sequence or 0,
            scheduled_arrival=stop.scheduled_arrival,
            scheduled_departure=stop.scheduled_departure,
            updated_arrival=stop.updated_arrival,
            updated_departure=stop.updated_departure,
            actual_arrival=stop.actual_arrival,
            actual_departure=stop.actual_departure,
            track=stop.track,
            track_assigned_at=stop.track_assigned_at,
            raw_status=RawStopStatus(
                amtrak_status=stop.raw_amtrak_status,
                njt_departed_flag=stop.raw_njt_departed_flag,
            ),
            has_departed_station=stop.has_departed_station,
        )
        stops.append(stop_detail)

    # Calculate train position
    train_position = calculate_train_position(journey)

    # Build response
    train_details = TrainDetails(
        train_id=journey.train_id,
        journey_date=journey.journey_date,
        line=LineInfo(
            code=journey.line_code,
            name=journey.line_name or journey.line_code,
            color=(journey.line_color or "#000000").strip(),
        ),
        route=RouteInfo(
            origin=get_first_stop_name(journey),
            destination=journey.destination,
            origin_code=journey.origin_station_code,
            destination_code=journey.terminal_station_code,
        ),
        train_position=train_position,
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
        raw_train_state="Active" if journey.data_source == "AMTRAK" else None,
        is_cancelled=journey.is_cancelled,
        is_completed=journey.is_completed,
    )

    return TrainDetailsResponse(train=train_details)


@router.get("/{train_id}/history", response_model=TrainHistoryResponse)
@handle_errors
async def get_train_history(
    train_id: str = Path(..., description="Train ID"),
    days: int = Query(30, ge=1, description="Number of days of history"),
    from_station: str | None = Query(
        None, description="Filter to journeys containing this origin station"
    ),
    to_station: str | None = Query(
        None, description="Filter to journeys containing this destination station"
    ),
    include_route_trains: bool = Query(
        False, description="Include statistics for all trains on the same route"
    ),
    db: AsyncSession = Depends(get_db),
) -> TrainHistoryResponse:
    """Get historical data for a train."""
    logger.info(
        "get_train_history_request",
        train_id=train_id,
        days=days,
        from_station=from_station,
        to_station=to_station,
        include_route_trains=include_route_trains,
    )

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

    # Query route-wide data if requested
    route_journeys = []
    train_data_source = None
    if include_route_trains and from_station and to_station and journeys:
        # Get the data source from the first journey
        train_data_source = journeys[0].data_source

        # Query all trains with same data source on this route
        route_stmt = (
            select(TrainJourney)
            .where(
                and_(
                    TrainJourney.journey_date >= start_date,
                    TrainJourney.journey_date <= end_date,
                    TrainJourney.data_source == train_data_source,
                )
            )
            .options(selectinload(TrainJourney.stops))
        )

        route_result = await db.execute(route_stmt)
        all_route_journeys = list(route_result.scalars().all())

        # Filter to only journeys that contain both stations in correct order
        for journey in all_route_journeys:
            from_stop = None
            to_stop = None

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

    # Build historical data
    historical_journeys = []
    total_delay = 0
    on_time_count = 0
    cancelled_count = 0

    # New statistics for delay breakdown
    delay_categories = {
        "on_time": 0,  # 0-5 minutes
        "slight": 0,  # 6-15 minutes
        "significant": 0,  # 16-30 minutes
        "major": 0,  # >30 minutes
    }

    # Track usage statistics
    track_usage_counts = {}

    for journey in journeys:
        # Filter by station route if specified
        if from_station and to_station:
            # Find the stops for from_station and to_station
            from_stop = None
            to_stop = None

            for stop in journey.stops:
                if stop.station_code == from_station:
                    from_stop = stop
                elif stop.station_code == to_station:
                    to_stop = stop

            # Skip if either station is not found, or if they're in wrong order
            if not from_stop or not to_stop:
                continue
            if (from_stop.stop_sequence or 0) >= (to_stop.stop_sequence or 0):
                continue

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

        # Calculate delays (simple calculation for historical data)
        departure_delay = (
            int(
                (
                    first_stop.actual_departure - first_stop.scheduled_departure
                ).total_seconds()
                / 60
            )
            if first_stop.actual_departure and first_stop.scheduled_departure
            else 0
        )

        arrival_delay = (
            int(
                (last_stop.actual_arrival - last_stop.scheduled_arrival).total_seconds()
                / 60
            )
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

            total_delay += arrival_delay

        # Count track usage for each station
        for _, track in track_assignments.items():
            if track:  # Only count if track is assigned
                if track not in track_usage_counts:
                    track_usage_counts[track] = 0
                track_usage_counts[track] += 1

    # Calculate statistics
    total_journeys = len(historical_journeys)
    non_cancelled_journeys = total_journeys - cancelled_count

    # Calculate delay breakdown percentages
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

    # Calculate track usage percentages
    track_usage = {}
    total_track_assignments = sum(track_usage_counts.values())
    if total_track_assignments > 0:
        track_usage = {
            track: round(count / total_track_assignments * 100)
            for track, count in track_usage_counts.items()
        }

    statistics = {
        "total_journeys": total_journeys,
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

    # Calculate route statistics if requested
    route_statistics = None
    if route_journeys:
        route_total_delay = 0
        route_on_time_count = 0
        route_cancelled_count = 0
        route_delay_categories = {
            "on_time": 0,
            "slight": 0,
            "significant": 0,
            "major": 0,
        }
        route_track_usage_counts = {}
        route_historical_journeys = []

        # Process route journeys (similar to train-specific logic)
        for journey in route_journeys:
            # Apply same filtering logic as train-specific
            if from_station and to_station:
                from_stop = None
                to_stop = None

                for stop in journey.stops:
                    if stop.station_code == from_station:
                        from_stop = stop
                    elif stop.station_code == to_station:
                        to_stop = stop

                if not from_stop or not to_stop:
                    continue
                if (from_stop.stop_sequence or 0) >= (to_stop.stop_sequence or 0):
                    continue

            # Get key stops (same logic)
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
            arrival_delay = (
                int(
                    (
                        last_stop.actual_arrival - last_stop.scheduled_arrival
                    ).total_seconds()
                    / 60
                )
                if last_stop.actual_arrival and last_stop.scheduled_arrival
                else 0
            )

            # Track assignments
            track_assignments = {
                stop.station_code: stop.track for stop in journey.stops if stop.track
            }

            route_historical_journeys.append(
                {
                    "journey_date": journey.journey_date,
                    "scheduled_departure": journey.scheduled_departure,
                    "actual_departure": journey.actual_departure,
                    "scheduled_arrival": journey.scheduled_arrival,
                    "actual_arrival": journey.actual_arrival,
                    "delay_minutes": max(0, arrival_delay),
                    "was_cancelled": journey.is_cancelled,
                    "track_assignments": track_assignments,
                }
            )

            if journey.is_cancelled:
                route_cancelled_count += 1
            else:
                # Categorize delay
                if arrival_delay <= 5:
                    route_on_time_count += 1
                    route_delay_categories["on_time"] += 1
                elif arrival_delay <= 15:
                    route_delay_categories["slight"] += 1
                elif arrival_delay <= 30:
                    route_delay_categories["significant"] += 1
                else:
                    route_delay_categories["major"] += 1

                route_total_delay += arrival_delay

            # Count track usage
            for _, track in track_assignments.items():
                if track:
                    if track not in route_track_usage_counts:
                        route_track_usage_counts[track] = 0
                    route_track_usage_counts[track] += 1

        # Calculate route statistics
        route_total_journeys = len(route_historical_journeys)
        route_non_cancelled_journeys = route_total_journeys - route_cancelled_count

        # Calculate route delay breakdown percentages
        route_delay_breakdown = {}
        if route_non_cancelled_journeys > 0:
            route_delay_breakdown = {
                "on_time": round(
                    route_delay_categories["on_time"]
                    / route_non_cancelled_journeys
                    * 100
                ),
                "slight": round(
                    route_delay_categories["slight"]
                    / route_non_cancelled_journeys
                    * 100
                ),
                "significant": round(
                    route_delay_categories["significant"]
                    / route_non_cancelled_journeys
                    * 100
                ),
                "major": round(
                    route_delay_categories["major"] / route_non_cancelled_journeys * 100
                ),
            }
        else:
            route_delay_breakdown = {
                "on_time": 0,
                "slight": 0,
                "significant": 0,
                "major": 0,
            }

        # Calculate route track usage percentages
        route_track_usage = {}
        route_total_track_assignments = sum(route_track_usage_counts.values())
        if route_total_track_assignments > 0:
            route_track_usage = {
                track: round(count / route_total_track_assignments * 100)
                for track, count in route_track_usage_counts.items()
            }

        route_statistics = {
            "total_journeys": route_total_journeys,
            "on_time_percentage": (
                (route_on_time_count / route_total_journeys * 100)
                if route_total_journeys > 0
                else 0
            ),
            "average_delay_minutes": (
                (route_total_delay / route_non_cancelled_journeys)
                if route_non_cancelled_journeys > 0
                else 0
            ),
            "cancellation_rate": (
                (route_cancelled_count / route_total_journeys * 100)
                if route_total_journeys > 0
                else 0
            ),
            "delay_breakdown": route_delay_breakdown,
            "track_usage": route_track_usage,
        }

    return TrainHistoryResponse(
        train_id=train_id,
        journeys=historical_journeys,
        statistics=statistics,
        route_statistics=route_statistics,
        data_source=train_data_source,
    )


@router.get(
    "/stations/{station_code}/tracks/occupied", response_model=OccupiedTracksResponse
)
@handle_errors
async def get_occupied_tracks(
    station_code: str = Path(
        ..., min_length=2, max_length=3, description="Station code"
    ),
    db: AsyncSession = Depends(get_db),
) -> OccupiedTracksResponse:
    """Get occupied tracks at a station."""
    logger.info("get_occupied_tracks_request", station_code=station_code)

    from trackrat.services.track_occupancy import track_occupancy_service

    return await track_occupancy_service.get_occupied_tracks(station_code)


# Helper functions


# Utility functions for journey calculations


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


# Removed old delay and estimated time calculations - iOS app will calculate these based on journey context


def calculate_train_position(journey: TrainJourney) -> TrainPosition:
    """Calculate current train position based on stops data."""
    if not journey.stops:
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
        between_stations=bool(
            last_departed_station_code and next_station_code and not at_station_code
        ),
    )


def get_first_stop_name(journey: TrainJourney) -> str:
    """Get the name of the first stop."""
    if journey.stops:
        first_stop = min(journey.stops, key=lambda s: s.stop_sequence or 0)
        return first_stop.station_name or journey.origin_station_code or "Unknown"
    return journey.origin_station_code or "Unknown"
