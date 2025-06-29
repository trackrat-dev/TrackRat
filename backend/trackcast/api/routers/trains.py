"""API endpoints for train data and predictions."""

import logging
from datetime import datetime, timedelta
from typing import Any, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query

from trackcast.api.models import (
    ConsolidatedTrainListResponse,
    ConsolidatedTrainResponse,
    Metadata,
    TrainListResponse,
    TrainResponse,
)
from trackcast.config import settings
from trackcast.db.connection import get_db
from trackcast.db.repository import TrainRepository, TrainStopRepository
from trackcast.services.train_consolidation import TrainConsolidationService
from trackcast.telemetry import trace_operation
from trackcast.utils import get_eastern_now


def get_train_repository() -> TrainRepository:
    """Get a train repository instance with a DB session."""
    db = next(get_db())
    return TrainRepository(db)


def get_train_stop_repository() -> TrainStopRepository:
    """Get a train stop repository instance with a DB session."""
    db = next(get_db())
    return TrainStopRepository(db)


router = APIRouter()
logger = logging.getLogger(__name__)


def _matches_target_station(
    stop: Any,
    stops_at_station: Optional[str],
    stops_at_station_code: Optional[str],
    stops_at_station_name: Optional[str],
) -> bool:
    """Check if a stop matches any of the target station filters."""
    if stops_at_station:
        # Search both station code and station name
        return bool(
            stop.station_code == stops_at_station
            or (stop.station_name and stops_at_station.lower() in stop.station_name.lower())
        )
    elif stops_at_station_code:
        # Exact station code match
        return bool(stop.station_code == stops_at_station_code)
    elif stops_at_station_name:
        # Station name partial match
        return bool(
            stop.station_name and stops_at_station_name.lower() in stop.station_name.lower()
        )
    return False


def _filter_trains_by_stop_order(
    trains: List[Any],
    origin_station_code: Optional[str],
    stops_at_station: Optional[str],
    stops_at_station_code: Optional[str],
    stops_at_station_name: Optional[str],
) -> List[Any]:
    """Filter trains where origin station comes before target station in route and both stops haven't departed."""
    if not origin_station_code or not any(
        [stops_at_station, stops_at_station_code, stops_at_station_name]
    ):
        return trains

    filtered_trains = []
    for train in trains:
        if not hasattr(train, "stops") or not train.stops:
            continue

        # Find positions of origin and target stations (only consider non-departed stops)
        origin_index = None
        target_index = None

        for i, stop in enumerate(train.stops):
            # Skip departed stops
            if stop.departed:
                continue

            # Check for origin station
            if stop.station_code == origin_station_code:
                origin_index = i

            # Check for target station
            if _matches_target_station(
                stop, stops_at_station, stops_at_station_code, stops_at_station_name
            ):
                target_index = i

        # Only include if both stations found and origin comes before target
        if origin_index is not None and target_index is not None and origin_index < target_index:
            filtered_trains.append(train)

    return filtered_trains


def _enrich_train_with_stops(train: Any, stop_repo: TrainStopRepository) -> Any:
    """Add stop data to a train object."""
    try:
        stops = stop_repo.get_stops_for_train(train.train_id, train.departure_time)
        # Convert SQLAlchemy objects to API models
        from trackcast.api.models import TrainStop

        stop_models = []
        for stop in stops:
            stop_models.append(
                TrainStop(
                    station_code=getattr(stop, "station_code", None),
                    station_name=getattr(stop, "station_name", ""),
                    scheduled_arrival=getattr(stop, "scheduled_arrival", None),
                    scheduled_departure=getattr(stop, "scheduled_departure", None),
                    actual_arrival=getattr(stop, "actual_arrival", None),
                    actual_departure=getattr(stop, "actual_departure", None),
                    pickup_only=bool(getattr(stop, "pickup_only", False)),
                    dropoff_only=bool(getattr(stop, "dropoff_only", False)),
                    departed=bool(getattr(stop, "departed", False)),
                    stop_status=getattr(stop, "stop_status", None),
                )
            )
        # Add stops to the train object
        train.stops = stop_models
    except Exception as e:
        logger.warning(f"Failed to load stops for train {train.train_id}: {str(e)}")
        train.stops = []
    return train


@router.get("/", response_model=Union[TrainListResponse, ConsolidatedTrainListResponse])
async def list_trains(
    train_id: Optional[str] = None,
    line: Optional[str] = None,
    destination: Optional[str] = None,
    departure_time_after: Optional[datetime] = None,
    departure_time_before: Optional[datetime] = None,
    track: Optional[str] = None,
    status: Optional[str] = None,
    has_prediction: Optional[bool] = None,
    has_track: Optional[bool] = None,
    train_split: Optional[str] = Query(
        None, description="Filter by data split (train, validation, test)"
    ),
    exclude_train_split: Optional[str] = Query(
        None, description="Exclude trains with this data split"
    ),
    sort_by: Optional[str] = Query(
        None, description="Field to sort by (e.g., departure_time, line, destination, status)"
    ),
    sort_order: str = Query("asc", description="Sort order: 'asc' or 'desc'"),
    limit: int = Query(20, ge=-1, le=1000),
    offset: int = Query(0, ge=0),
    no_pagination: bool = Query(False, description="Set to true to disable pagination"),
    stops_at_station: Optional[str] = Query(
        None, description="Filter trains that stop at this station (searches both code and name)"
    ),
    stops_at_station_code: Optional[str] = Query(
        None, description="Filter trains that stop at this station code exactly"
    ),
    stops_at_station_name: Optional[str] = Query(
        None, description="Filter trains that stop at this station name (partial match)"
    ),
    origin_station_code: Optional[str] = Query(
        None, description="Filter by origin station code (e.g., 'NY', 'TR')"
    ),
    origin_station_name: Optional[str] = Query(
        None, description="Filter by origin station name (partial match)"
    ),
    from_station_code: Optional[str] = Query(
        None, description="Filter trains that stop at this station code (boarding station)"
    ),
    to_station_code: Optional[str] = Query(
        None,
        description="Filter trains that stop at this station code after from_station_code (alighting station)",
    ),
    data_source: Optional[str] = Query(
        None, description="Filter by data source ('njtransit' or 'amtrak')"
    ),
    consolidate: bool = Query(
        False,
        description="Consolidate duplicate trains from multiple sources into unified journeys",
    ),
    train_repo: TrainRepository = Depends(get_train_repository),
    stop_repo: TrainStopRepository = Depends(get_train_stop_repository),
):
    """
    Get a list of trains with optional filtering and sorting parameters.

    When no filters are specified, all trains in the system will be retrieved,
    subject to pagination limits (default 20 per page).

    Parameters:
    - train_id: Filter by specific train ID
    - line: Filter by train line
    - destination: Filter by destination
    - departure_time_after: Filter trains departing after this time in Eastern timezone (uses from_station_code departure time if provided, otherwise origin departure time)
    - departure_time_before: Filter trains departing before this time in Eastern timezone (uses from_station_code departure time if provided, otherwise origin departure time)
    - track: Filter by assigned track
    - status: Filter by train status
    - has_prediction: Filter to only include trains with predictions
    - has_track: Filter to only include trains with assigned tracks
    - train_split: Filter by model training dataset split (train, validation, test)
    - exclude_train_split: Exclude trains with this data split value (e.g., "training")
    - sort_by: Field to sort results by (e.g., "departure_time", "line", "destination", "status", "track")
    - sort_order: Sort direction, either "asc" (ascending) or "desc" (descending)
    - limit: Maximum number of trains to return (set to -1 for a high limit)
    - offset: Pagination offset
    - no_pagination: Set to true to return all matching trains (ignores limit/offset)
    - stops_at_station: Filter trains that stop at this station (searches both code and name)
    - stops_at_station_code: Filter trains that stop at this exact station code
    - stops_at_station_name: Filter trains that stop at this station name (partial match supported)
    - origin_station_code: Filter by origin station code (e.g., 'NY' for Penn Station, 'TR' for Trenton)
    - origin_station_name: Filter by origin station name (partial match supported)
    - from_station_code: Filter trains that stop at this station code (boarding station)
    - to_station_code: Filter trains that stop at this station code after from_station_code (alighting station)
    - data_source: Filter by data source ('njtransit' or 'amtrak')
    - consolidate: Consolidate duplicate trains from multiple sources into unified journeys (default: false)
    """
    try:
        # Import StationMapper for validation
        from trackcast.services.station_mapping import StationMapper

        station_mapper = StationMapper()

        # Validate from/to station parameters
        # to_station_code requires from_station_code (destination needs origin)
        # but from_station_code can be used alone (for context predictions)
        if to_station_code and not from_station_code:
            raise HTTPException(
                status_code=400,
                detail="to_station_code requires from_station_code to be provided",
            )

        if from_station_code and to_station_code and from_station_code == to_station_code:
            raise HTTPException(
                status_code=400, detail="from_station_code and to_station_code cannot be the same"
            )

        # Validate and translate station codes if provided
        if from_station_code:
            if not station_mapper.is_valid_code(from_station_code):
                raise HTTPException(
                    status_code=400, detail=f"Invalid from_station_code: '{from_station_code}'"
                )
            # Translate frontend code to database code for query
            from_station_code = station_mapper.translate_frontend_to_db_code(from_station_code)

        if to_station_code:
            if not station_mapper.is_valid_code(to_station_code):
                raise HTTPException(
                    status_code=400, detail=f"Invalid to_station_code: '{to_station_code}'"
                )
            # Translate frontend code to database code for query
            to_station_code = station_mapper.translate_frontend_to_db_code(to_station_code)

        if origin_station_code:
            if not station_mapper.is_valid_code(origin_station_code):
                raise HTTPException(
                    status_code=400, detail=f"Invalid origin_station_code: '{origin_station_code}'"
                )
            # Translate frontend code to database code for query
            origin_station_code = station_mapper.translate_frontend_to_db_code(origin_station_code)

        if stops_at_station_code:
            if not station_mapper.is_valid_code(stops_at_station_code):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid stops_at_station_code: '{stops_at_station_code}'",
                )
            # Translate frontend code to database code for query
            stops_at_station_code = station_mapper.translate_frontend_to_db_code(
                stops_at_station_code
            )

        # No default time filter - if no time parameters are supplied, all trains will be retrieved

        # Debug log to check the value of no_pagination
        logger.info(f"no_pagination parameter: {no_pagination} (type: {type(no_pagination)})")

        if no_pagination:
            logger.info("No pagination requested - retrieving all trains")
            trains, total_count = train_repo.get_trains(
                train_id=train_id,
                line=line,
                destination=destination,
                departure_time_after=departure_time_after,
                departure_time_before=departure_time_before,
                track=track,
                status=status,
                has_prediction=has_prediction,
                has_track=has_track,
                train_split=train_split,
                exclude_train_split=exclude_train_split,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=None,  # No limit
                offset=0,
                stops_at_station=stops_at_station,
                stops_at_station_code=stops_at_station_code,
                stops_at_station_name=stops_at_station_name,
                origin_station_code=origin_station_code,
                origin_station_name=origin_station_name,
                from_station_code=from_station_code,
                to_station_code=to_station_code,
                data_source=data_source,
            )
        else:
            logger.info(f"Using pagination with limit={limit}, offset={offset}")
            trains, total_count = train_repo.get_trains(
                train_id=train_id,
                line=line,
                destination=destination,
                departure_time_after=departure_time_after,
                departure_time_before=departure_time_before,
                track=track,
                status=status,
                has_prediction=has_prediction,
                has_track=has_track,
                train_split=train_split,
                exclude_train_split=exclude_train_split,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
                offset=offset,
                stops_at_station=stops_at_station,
                stops_at_station_code=stops_at_station_code,
                stops_at_station_name=stops_at_station_name,
                origin_station_code=origin_station_code,
                origin_station_name=origin_station_name,
                from_station_code=from_station_code,
                to_station_code=to_station_code,
                data_source=data_source,
            )

        # Check if we should fetch fresh stop data for a specific NJ Transit train
        if train_id:
            # Find NJ Transit trains that need stop updates
            nj_trains_to_update = [t for t in trains if t.data_source == "njtransit"]

            if nj_trains_to_update:
                from trackcast.data.collectors import NJTransitCollector
                from trackcast.services.train_stop_updater import TrainStopUpdater

                # Group trains by train_id for efficient API calls (train stop API is not station-specific)
                trains_by_id = {}
                for train in nj_trains_to_update:
                    if train.train_id not in trains_by_id:
                        trains_by_id[train.train_id] = []
                    trains_by_id[train.train_id].append(train)

                # Update stops for each train_id's trains using batch processing
                for train_id_key, trains_with_same_id in trains_by_id.items():
                    # Find trains that need updating
                    updater = TrainStopUpdater(train_repo, stop_repo)
                    trains_needing_update = [
                        train
                        for train in trains_with_same_id
                        if updater.should_refresh_stops(train)
                    ]

                    if trains_needing_update:
                        try:
                            # Use any available station config for authentication (train stop API doesn't need specific station)
                            station_config = next(
                                (s for s in settings.njtransit_api.stations if s.enabled),
                                None,
                            )

                            if station_config:
                                nj_collector = NJTransitCollector(
                                    station_code=station_config.code,
                                    station_name=station_config.name,
                                )
                                updater.nj_collector = nj_collector

                                # Update stops for all trains with single API call
                                completion_results = updater.update_multiple_trains_stops(
                                    trains_needing_update
                                )

                                # Update completion status for trains that are complete
                                for train_db_id, is_complete in completion_results.items():
                                    if is_complete:
                                        # Find the train object by database ID
                                        train_to_complete = next(
                                            (
                                                t
                                                for t in trains_needing_update
                                                if str(t.id) == train_db_id
                                            ),
                                            None,
                                        )
                                        if (
                                            train_to_complete
                                            and train_to_complete.journey_completion_status
                                            != "completed"
                                        ):
                                            train_to_complete.journey_completion_status = (
                                                "completed"
                                            )
                                            train_to_complete.journey_validated_at = (
                                                get_eastern_now()
                                            )
                                            train_repo.update(train_to_complete)

                                logger.info(
                                    f"Updated stops for {len(trains_needing_update)} trains with train_id {train_id_key}"
                                )

                        except Exception as e:
                            logger.warning(f"Failed to refresh stops for train {train_id_key}: {e}")

        # Enrich trains with stop data
        enriched_trains = []
        for train in trains:
            enriched_train = _enrich_train_with_stops(train, stop_repo)
            # Filter predictions by station context if from_station_code provided
            if from_station_code:
                enriched_train = _filter_prediction_by_station_context(
                    enriched_train, from_station_code
                )
            enriched_trains.append(enriched_train)

        # Filter by stop order if both origin and target station filters are specified
        enriched_trains = _filter_trains_by_stop_order(
            enriched_trains,
            origin_station_code,
            stops_at_station,
            stops_at_station_code,
            stops_at_station_name,
        )

        # Update train count to reflect actual filtered results
        filtered_count = len(enriched_trains)

        # Apply consolidation if requested
        if consolidate:
            logger.info(f"Starting consolidation for {len(enriched_trains)} trains")

            with trace_operation(
                "api.consolidate_trains",
                input_train_count=len(enriched_trains),
                from_station_code=from_station_code,
            ) as span:
                consolidation_service = TrainConsolidationService()
                consolidated_trains = consolidation_service.consolidate_trains(
                    enriched_trains, from_station_code or ""
                )

                # Add consolidation results to span
                span.set_attribute("consolidation.output_count", len(consolidated_trains))
                span.set_attribute(
                    "consolidation.reduction_ratio",
                    len(consolidated_trains) / len(enriched_trains) if enriched_trains else 0,
                )

            logger.info(f"Consolidation complete: {len(consolidated_trains)} consolidated journeys")
            for i, journey in enumerate(consolidated_trains):
                logger.info(
                    f"  Journey {i + 1}: {journey['train_id']} with {len(journey['data_sources'])} sources"
                )

            return ConsolidatedTrainListResponse(
                metadata=Metadata(
                    timestamp=get_eastern_now().isoformat(),
                    model_version=settings.model.version,
                    train_count=len(consolidated_trains),
                    page=1,  # Consolidation affects pagination
                    total_pages=1,
                ),
                trains=[ConsolidatedTrainResponse(**train) for train in consolidated_trains],
            )
        else:
            return {
                "metadata": {
                    "timestamp": get_eastern_now().isoformat(),
                    "model_version": settings.model.version,
                    "train_count": filtered_count,
                    "page": offset // limit + 1,
                    "total_pages": (filtered_count + limit - 1) // limit if limit > 0 else 1,
                },
                "trains": enriched_trains,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching trains: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


def _train_stops_at_station(train, station_code: str) -> bool:
    """Check if train stops at the specified station."""
    if not hasattr(train, "stops") or not train.stops:
        return False
    return any(stop.station_code == station_code for stop in train.stops)


def _filter_prediction_by_station_context(train, from_station_code: str):
    """Only show predictions if they match the boarding station context."""
    try:
        # Verify train stops at boarding station
        if not _train_stops_at_station(train, from_station_code):
            logger.warning(
                f"Train {train.train_id} doesn't stop at {from_station_code}, removing predictions"
            )
            train.prediction_data = None
            return train

        # Only show predictions if they match the context station
        if train.origin_station_code == from_station_code:
            # Predictions are relevant - keep them
            logger.debug(
                f"Train {train.train_id}: showing {train.origin_station_code} predictions for {from_station_code} context"
            )
            return train
        else:
            # Predictions are for a different station - hide them
            logger.debug(
                f"Train {train.train_id}: hiding {train.origin_station_code} predictions for {from_station_code} context"
            )
            train.prediction_data = None
            return train

    except Exception as e:
        logger.error(f"Error filtering predictions for train {train.train_id}: {str(e)}")
        train.prediction_data = None
        return train
