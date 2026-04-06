"""
Train API endpoints for TrackRat V2.

Implements the V2 API design documented in backend_v2/CLAUDE.md.
"""

import asyncio
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload
from structlog import get_logger

from trackrat.api.utils import handle_errors
from trackrat.collectors.njt.client import NJTransitClient
from trackrat.config.stations import canonical_station_code, expand_station_codes
from trackrat.db.engine import get_db, get_session
from trackrat.models.api import (
    DataFreshness,
    DeparturesResponse,
    HistoricalJourney,
    JourneyProgress,
    LineInfo,
    OccupiedTracksResponse,
    RawStopStatus,
    RouteInfo,
    SimpleStationInfo,
    StopDetails,
    TrackPrediction,
    TrainDetails,
    TrainDetailsResponse,
    TrainHistoryResponse,
    TrainPosition,
)
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.api_cache import ApiCacheService
from trackrat.services.departure import DepartureService, _detect_at_station
from trackrat.services.direct_forecaster import DirectArrivalForecaster
from trackrat.services.gtfs import GTFSService
from trackrat.services.jit import JustInTimeUpdateService
from trackrat.utils.request_stats import get_request_stats
from trackrat.utils.time import DATETIME_MIN_ET, now_et, safe_datetime_subtract
from trackrat.utils.train import get_effective_observation_type, is_amtrak_train

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2/trains", tags=["trains"])


@router.get("/departures", response_model=DeparturesResponse)
@handle_errors
async def get_departures(
    from_station: str = Query(
        ...,
        alias="from",
        min_length=2,
        max_length=10,
        description="Departure station code",
    ),
    to_station: str | None = Query(
        None,
        alias="to",
        min_length=2,
        max_length=10,
        description="Arrival station code",
    ),
    date: date | None = Query(
        None, description="Journey date (YYYY-MM-DD, defaults to today)"
    ),
    time_from: datetime | None = Query(
        None, description="Start time (defaults to now)"
    ),
    time_to: datetime | None = Query(
        None, description="End time (defaults to +24 hours)"
    ),
    hide_departed: bool = Query(
        False,
        description="Hide trains that have already departed from the origin station",
    ),
    data_sources: str | None = Query(
        None,
        description="Comma-separated list of data sources to include: NJT,AMTRAK,PATH,PATCO,LIRR,MNR,SUBWAY,BART,MBTA,METRA,WMATA. Default: all",
    ),
    limit: int = Query(50, le=1000, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
) -> DeparturesResponse:
    """Get upcoming train departures from a station, optionally filtered by destination.

    Returns cached results for default time parameters. For future dates, falls back
    to GTFS static schedule data. Supports filtering by data source (NJT, AMTRAK, PATH, PATCO, LIRR, MNR, SUBWAY, BART, MBTA, METRA, WMATA).
    """
    logger.info(
        "get_departures_request",
        from_station=from_station,
        to_station=to_station,
        date=date,
        time_from=time_from,
        time_to=time_to,
        hide_departed=hide_departed,
        data_sources=data_sources,
    )

    cache_service = ApiCacheService()

    # Parse data_sources into a list
    source_list: list[str] | None = None
    if data_sources:
        source_list = [s.strip().upper() for s in data_sources.split(",") if s.strip()]

    # Use cache when using default time parameters (date, time_from, time_to are None)
    # Cache supports both hide_departed=true and hide_departed=false
    use_cache = date is None and time_from is None and time_to is None

    if use_cache:
        cache_params = {
            "from_station": canonical_station_code(from_station),
            "to_station": canonical_station_code(to_station) if to_station else None,
            "date": None,
            "limit": limit,
            "hide_departed": hide_departed,
            "data_sources": ",".join(sorted(source_list)) if source_list else None,
        }

        cached_response = await cache_service.get_cached_response(
            db, "/api/v2/trains/departures", cache_params
        )
        if cached_response:
            try:
                return DeparturesResponse(**cached_response)
            except (TypeError, ValueError) as e:
                logger.warning(
                    "cache_deserialization_failed",
                    endpoint="/api/v2/trains/departures",
                    params=cache_params,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                # Invalidate corrupted cache entry
                await cache_service.invalidate_cache_entry(
                    db, "/api/v2/trains/departures", cache_params
                )
        elif source_list:
            # System-specific cache miss — try superset cache (data_sources=None)
            # and filter in-memory, since the all-systems cache is a superset
            superset_params = {**cache_params, "data_sources": None}
            superset_response = await cache_service.get_cached_response(
                db, "/api/v2/trains/departures", superset_params
            )
            if superset_response:
                source_set = set(source_list)
                superset_response["departures"] = [
                    d
                    for d in superset_response.get("departures", [])
                    if d.get("data_source") in source_set
                ]
                superset_response["metadata"]["count"] = len(
                    superset_response["departures"]
                )
                try:
                    return DeparturesResponse(**superset_response)
                except (TypeError, ValueError):
                    pass  # Fall through to fresh computation
            else:
                logger.info(
                    "cache_miss",
                    endpoint="/api/v2/trains/departures",
                    from_station=from_station,
                    to_station=to_station,
                    hide_departed=hide_departed,
                    data_sources=source_list,
                )
        else:
            # Cache miss - log for observability
            logger.info(
                "cache_miss",
                endpoint="/api/v2/trains/departures",
                from_station=from_station,
                to_station=to_station,
                hide_departed=hide_departed,
            )

    service = DepartureService()
    response = await service.get_departures(
        db,
        from_station,
        to_station,
        date,
        time_from,
        time_to,
        limit,
        hide_departed,
        source_list,
    )

    if use_cache:
        try:
            await cache_service.store_cached_response(
                db,
                "/api/v2/trains/departures",
                cache_params,
                response.model_dump(mode="json"),
                ttl_seconds=120,
            )
        except Exception as e:
            logger.warning("departure_cache_storage_failed", error=str(e))

    # Record result count for admin stats
    if to_station:
        get_request_stats().record_departure_results(
            from_station, to_station, len(response.departures)
        )

    return response


@router.get("/{train_id}", response_model=TrainDetailsResponse)
@handle_errors
async def get_train_details(
    train_id: str = Path(..., description="Train ID"),
    date: date | None = Query(None, description="Journey date (YYYY-MM-DD)"),
    refresh: bool = Query(False, description="Force data refresh"),
    include_predictions: bool = Query(True, description="Include arrival predictions"),
    from_station: str | None = Query(
        None, description="User's origin station code (filters predictions)"
    ),
    data_source: str | None = Query(
        None,
        description="Data source filter (NJT, AMTRAK, PATH, PATCO, LIRR, MNR, SUBWAY, MBTA)",
    ),
    db: AsyncSession = Depends(get_db),
) -> TrainDetailsResponse:
    """Get full journey details for a specific train including all stops and times.

    For future dates, returns GTFS static schedule data. For today, refreshes stale
    data on demand via JIT updates. Optionally includes per-stop arrival predictions
    and inline track predictions when the boarding station track is unassigned.
    """
    logger.info(
        "get_train_details_request",
        train_id=train_id,
        date=date,
        refresh=refresh,
        from_station=from_station,
        data_source=data_source,
    )

    # Default to today
    if date is None:
        date = now_et().date()

    # For future dates, use GTFS static schedule data
    today = now_et().date()
    if date > today:
        gtfs_service = GTFSService()
        gtfs_details = await gtfs_service.get_train_details(
            db, train_id, date, data_source=data_source
        )
        if gtfs_details:
            return TrainDetailsResponse(train=gtfs_details)
        # If not found in GTFS, fall through to 404
        raise HTTPException(
            status_code=404,
            detail=f"Train {train_id} not found in schedule for date {date}",
        )

    # Get fresh train data
    # NJT client is only needed for NJ Transit trains
    njt_client = None
    if data_source in (None, "NJT") and not is_amtrak_train(train_id):
        njt_client = NJTransitClient()

    # Pre-fetch existing journey so we can fall back to stale data on timeout
    stale_conditions = [
        TrainJourney.train_id == train_id,
        TrainJourney.journey_date == date,
    ]
    if data_source:
        stale_conditions.append(TrainJourney.data_source == data_source)
    stale_journey = await db.scalar(
        select(TrainJourney)
        .where(and_(*stale_conditions))
        .options(selectinload(TrainJourney.stops))
    )

    try:
        async with JustInTimeUpdateService(njt_client) as jit_service:
            try:
                journey = await asyncio.wait_for(
                    jit_service.get_fresh_train(
                        db, train_id, date, force_refresh=refresh, data_source=data_source
                    ),
                    timeout=15.0,
                )
            except TimeoutError:
                logger.warning(
                    "jit_refresh_timeout",
                    train_id=train_id,
                    data_source=data_source,
                    has_stale_data=stale_journey is not None,
                )
                await db.rollback()
                # Re-query after rollback: rollback expires all ORM objects,
                # and async SQLAlchemy can't lazy-load (MissingGreenlet).
                if stale_journey is not None:
                    stmt = (
                        select(TrainJourney)
                        .where(
                            TrainJourney.train_id == train_id,
                            TrainJourney.journey_date == date,
                        )
                        .options(selectinload(TrainJourney.stops))
                    )
                    if data_source:
                        stmt = stmt.where(TrainJourney.data_source == data_source)
                    journey = await db.scalar(stmt)
                else:
                    journey = None
    finally:
        if njt_client:
            await njt_client.close()

    if not journey:
        # For today's trains: try GTFS fallback for scheduled-only trains
        # (trains that appear in departure listing but haven't been discovered yet).
        # Guard with try/except: the session may be in a dirty state if JIT
        # refresh failed and rollback couldn't fully recover it.
        try:
            gtfs_service = GTFSService()
            gtfs_details = await gtfs_service.get_train_details(
                db, train_id, date, data_source=data_source
            )
            if gtfs_details:
                return TrainDetailsResponse(train=gtfs_details)
        except Exception:
            pass
        raise HTTPException(
            status_code=404, detail=f"Train {train_id} not found for date {date}"
        )

    # Flush JIT changes now to prevent surprise auto-flush failures during
    # predictions (which do SELECTs that trigger SQLAlchemy auto-flush).
    # A concurrent collector modifying the same journey can cause flush conflicts;
    # catching here prevents the session from entering PendingRollbackError state.
    try:
        await db.flush()
    except Exception:
        await db.rollback()
        # Re-query journey since rollback expires all ORM objects
        stmt = (
            select(TrainJourney)
            .where(
                TrainJourney.train_id == train_id,
                TrainJourney.journey_date == date,
            )
            .options(selectinload(TrainJourney.stops))
        )
        if data_source:
            stmt = stmt.where(TrainJourney.data_source == data_source)
        journey = await db.scalar(stmt)
        if not journey:
            raise HTTPException(
                status_code=404,
                detail=f"Train {train_id} not found for date {date}",
            ) from None

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

    # Add arrival predictions to each stop if requested.
    # Uses a separate DB session so that timeout/cancellation doesn't poison
    # the main request session (which caused HTTP 500 via SQLAlchemy 7s2a error
    # when the prediction query exceeded the timeout and left db in failed state).
    if include_predictions:
        try:
            forecaster = DirectArrivalForecaster()
            async with get_session() as pred_db:
                await asyncio.wait_for(
                    forecaster.add_predictions_to_stops(
                        pred_db, journey, stops, user_origin=from_station
                    ),
                    timeout=5.0,
                )

            logger.info(
                "added_arrival_predictions",
                train_id=journey.train_id,
                stops_with_predictions=sum(
                    1 for s in stops if s.predicted_arrival is not None
                ),
            )
        except TimeoutError:
            logger.warning(
                "prediction_timeout",
                train_id=journey.train_id,
                data_source=journey.data_source,
            )
        except Exception as e:
            # Log error but don't fail the request
            logger.error("prediction_failed", train_id=journey.train_id, error=str(e))

    # Calculate train position
    train_position = calculate_train_position(journey)

    # Calculate journey progress
    progress = None
    if journey.progress_snapshots:
        # Get the latest progress snapshot (filter out None captured_at)
        valid_snapshots = [
            p for p in journey.progress_snapshots if p.captured_at is not None
        ]
        if valid_snapshots:
            # Use timezone-aware constant for safe comparison with DB times
            latest_progress = max(
                valid_snapshots, key=lambda p: p.captured_at or DATETIME_MIN_ET
            )
            progress = JourneyProgress(
                stops_completed=latest_progress.stops_completed,
                stops_total=latest_progress.stops_total,
                journey_percent=latest_progress.journey_percent,
                minutes_to_arrival=None,  # Will be calculated from prediction
                last_departed=latest_progress.last_departed_station,
                next_arrival=latest_progress.next_station,
            )

    # Get final destination prediction from our per-stop predictions
    predicted_arrival = None
    if include_predictions and journey.terminal_station_code:
        # Find the terminal station in our stops list
        terminal_stop = next(
            (s for s in stops if s.station.code == journey.terminal_station_code), None
        )
        if terminal_stop and terminal_stop.predicted_arrival:
            predicted_arrival = terminal_stop.predicted_arrival

            # Update minutes to arrival in progress
            if progress and predicted_arrival:
                minutes_to_arrival = int(
                    (predicted_arrival - now_et()).total_seconds() / 60
                )
                progress.minutes_to_arrival = max(0, minutes_to_arrival)

    # Build response
    train_details = TrainDetails(
        train_id=journey.train_id,
        journey_date=journey.journey_date,
        line=LineInfo(
            code=journey.line_code or "UNK",
            name=journey.line_name or journey.line_code or "Unknown",
            color=(journey.line_color or "#000000").strip(),
        ),
        route=RouteInfo(
            origin=get_first_stop_name(journey),
            destination=journey.destination,
            origin_code=get_first_stop_code(journey),
            destination_code=get_last_stop_code(journey),
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
        observation_type=get_effective_observation_type(journey),
        raw_train_state="Active" if journey.data_source == "AMTRAK" else None,
        is_cancelled=journey.is_cancelled,
        cancellation_reason=journey.cancellation_reason,
        is_completed=journey.is_completed,
        progress=progress,
        predicted_arrival=predicted_arrival,
    )

    # Compute inline track prediction when track is unassigned at the user's origin
    track_prediction = None
    if include_predictions and from_station:
        from trackrat.config.station_configs import station_has_predictions

        from_station_codes = set(expand_station_codes(from_station))
        if station_has_predictions(from_station):
            # Check if the origin stop has a track assigned
            origin_stop = next(
                (s for s in stops if s.station.code in from_station_codes), None
            )
            if origin_stop and origin_stop.track is None and journey.train_id:
                try:
                    from trackrat.services.historical_track_predictor import (
                        historical_track_predictor,
                    )

                    # Use stop-level departure at from_station for better
                    # time-of-day matching, falling back to journey-level.
                    stop_departure = None
                    if origin_stop and origin_stop.scheduled_departure:
                        stop_departure = origin_stop.scheduled_departure

                    scheduled_departure = (
                        stop_departure or journey.scheduled_departure or now_et()
                    )
                    data_source = journey.data_source or "NJT"

                    # Separate session to avoid poisoning the main request
                    # session if the query fails or is slow.
                    async with get_session() as track_db:
                        prediction = await historical_track_predictor.predict_track(
                            station_code=from_station,
                            train_id=journey.train_id,
                            line_code=journey.line_code,
                            data_source=data_source,
                            scheduled_departure=scheduled_departure,
                            db=track_db,
                        )

                    if prediction:
                        track_prediction = TrackPrediction(
                            platform_probabilities=prediction["platform_probabilities"],
                            primary_prediction=prediction["primary_prediction"],
                            confidence=prediction["confidence"],
                            top_3=prediction["top_3"],
                            station_code=from_station,
                        )
                except Exception as e:
                    logger.warning(
                        "inline_track_prediction_failed",
                        train_id=journey.train_id,
                        station=from_station,
                        error=str(e),
                    )

    # Record train detail view for admin stats
    if from_station and journey.train_id:
        get_request_stats().record_train_detail_view(
            journey.train_id,
            from_station,
            journey.terminal_station_code or journey.destination or "",
        )

    return TrainDetailsResponse(train=train_details, track_prediction=track_prediction)


@router.get("/{train_id}/history", response_model=TrainHistoryResponse)
@handle_errors
async def get_train_history(
    train_id: str = Path(..., description="Train ID"),
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
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
    """Get historical performance data for a specific train over a date range.

    Returns per-journey details, delay breakdown, track usage, and cancellation rates.
    Optionally includes aggregate statistics for all trains on the same route when
    from_station, to_station, and include_route_trains are provided.
    """
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

        # PERFORMANCE FIX: Use database-level filtering with EXISTS subqueries
        # to avoid loading all journeys into memory then filtering in Python.
        from_stop_alias = aliased(JourneyStop, name="from_stop")
        to_stop_alias = aliased(JourneyStop, name="to_stop")

        from_codes = expand_station_codes(from_station)
        to_codes = expand_station_codes(to_station)

        # Subquery: journey has from_station with stop_sequence < to_station's sequence
        route_filter = exists(
            select(from_stop_alias.id).where(
                and_(
                    from_stop_alias.journey_id == TrainJourney.id,
                    from_stop_alias.station_code.in_(from_codes),
                    exists(
                        select(to_stop_alias.id).where(
                            and_(
                                to_stop_alias.journey_id == TrainJourney.id,
                                to_stop_alias.station_code.in_(to_codes),
                                to_stop_alias.stop_sequence
                                > from_stop_alias.stop_sequence,
                            )
                        )
                    ),
                )
            )
        )

        route_stmt = (
            select(TrainJourney)
            .where(
                and_(
                    TrainJourney.journey_date >= start_date,
                    TrainJourney.journey_date <= end_date,
                    TrainJourney.data_source == train_data_source,
                    route_filter,
                )
            )
            .options(selectinload(TrainJourney.stops))
            .limit(5000)  # Safety limit to prevent memory issues
        )

        route_result = await db.execute(route_stmt)
        route_journeys = list(route_result.scalars().all())

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

    # Precompute expanded code sets for Python-level filtering
    from_code_set = set(expand_station_codes(from_station)) if from_station else set()
    to_code_set = set(expand_station_codes(to_station)) if to_station else set()

    for journey in journeys:
        # Filter by station route if specified
        if from_station and to_station:
            # Find the stops for from_station and to_station
            from_stop = None
            to_stop = None

            for stop in journey.stops:
                if stop.station_code in from_code_set:
                    from_stop = stop
                elif stop.station_code in to_code_set:
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

        # Exclude scheduled_fallback arrivals — they always show 0 delay
        # (actual == scheduled) and inflate on-time percentages
        # NOTE: Historical stops (before ~March 2026) may have NULL
        # arrival_source (partial backfill — migration f7a8b9c0d1e2 removed).
        # NULL arrival_source stops still contribute to delay here since we
        # only exclude "scheduled_fallback", not NULL.
        arrival_delay = (
            int(
                (last_stop.actual_arrival - last_stop.scheduled_arrival).total_seconds()
                / 60
            )
            if last_stop.actual_arrival
            and last_stop.scheduled_arrival
            and last_stop.arrival_source != "scheduled_fallback"
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
            (on_time_count / non_cancelled_journeys * 100)
            if non_cancelled_journeys > 0
            else 0
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
                    if stop.station_code in from_code_set:
                        from_stop = stop
                    elif stop.station_code in to_code_set:
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

            # Exclude scheduled_fallback arrivals — inflates OTP
            # See note above re: historical NULL arrival_source
            arrival_delay = (
                int(
                    (
                        last_stop.actual_arrival - last_stop.scheduled_arrival
                    ).total_seconds()
                    / 60
                )
                if last_stop.actual_arrival
                and last_stop.scheduled_arrival
                and last_stop.arrival_source != "scheduled_fallback"
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
                (route_on_time_count / route_non_cancelled_journeys * 100)
                if route_non_cancelled_journeys > 0
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
        ..., min_length=2, max_length=10, description="Station code"
    ),
    db: AsyncSession = Depends(get_db),
) -> OccupiedTracksResponse:
    """Get currently occupied tracks at a station based on recent train activity."""
    logger.info("get_occupied_tracks_request", station_code=station_code)

    from trackrat.services.track_occupancy import get_track_occupancy_service

    return await get_track_occupancy_service().get_occupied_tracks(station_code)


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

    sorted_stops = sorted(journey.stops, key=lambda s: s.stop_sequence or 0)

    last_departed_station_code = None
    next_station_code = None

    for stop in sorted_stops:
        if stop.has_departed_station:
            last_departed_station_code = stop.station_code
        else:
            next_station_code = stop.station_code
            break

    # Use shared at-station detection logic (NJT track, Amtrak status, etc.)
    at_station_code = _detect_at_station(journey)

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


def get_first_stop_code(journey: TrainJourney) -> str:
    """Get the station code of the first stop from actual stops data.

    This always reflects the true origin, even if discovery data was wrong.
    """
    if journey.stops:
        first_stop = min(journey.stops, key=lambda s: s.stop_sequence or 0)
        return first_stop.station_code or journey.origin_station_code or "Unknown"
    return journey.origin_station_code or "Unknown"


def get_last_stop_code(journey: TrainJourney) -> str:
    """Get the station code of the last stop from actual stops data.

    This always reflects the true destination, even if discovery data was wrong.
    """
    if journey.stops:
        last_stop = max(journey.stops, key=lambda s: s.stop_sequence or 0)
        return last_stop.station_code or journey.terminal_station_code or "Unknown"
    return journey.terminal_station_code or "Unknown"
