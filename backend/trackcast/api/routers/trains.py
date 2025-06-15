"""API endpoints for train data and predictions."""

import logging
from datetime import datetime, timedelta
from typing import Any, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query

from trackcast.api.models import (
    ConsolidatedTrainListResponse,
    PredictionResponse,
    TrainListResponse,
    TrainResponse,
)
from trackcast.config import settings
from trackcast.db.connection import get_db
from trackcast.db.repository import TrainRepository, TrainStopRepository
from trackcast.services.train_consolidation import TrainConsolidationService


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
    stops_at_station_name: Optional[str]
) -> bool:
    """Check if a stop matches any of the target station filters."""
    if stops_at_station:
        # Search both station code and station name
        return stop.station_code == stops_at_station or (
            stop.station_name and stops_at_station.lower() in stop.station_name.lower()
        )
    elif stops_at_station_code:
        # Exact station code match
        return stop.station_code == stops_at_station_code
    elif stops_at_station_name:
        # Station name partial match
        return stop.station_name and stops_at_station_name.lower() in stop.station_name.lower()
    return False


def _filter_trains_by_stop_order(
    trains: List[Any], 
    origin_station_code: Optional[str], 
    stops_at_station: Optional[str], 
    stops_at_station_code: Optional[str], 
    stops_at_station_name: Optional[str]
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
                    station_code=stop.station_code,
                    station_name=stop.station_name,
                    scheduled_time=stop.scheduled_time,
                    departure_time=stop.departure_time,
                    pickup_only=stop.pickup_only,
                    dropoff_only=stop.dropoff_only,
                    departed=stop.departed,
                    stop_status=stop.stop_status,
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
        if (from_station_code is None) != (to_station_code is None):
            raise HTTPException(
                status_code=400,
                detail="Both from_station_code and to_station_code must be provided together, or neither should be provided",
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

        # Enrich trains with stop data
        enriched_trains = []
        for train in trains:
            enriched_train = _enrich_train_with_stops(train, stop_repo)
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
            for i, train in enumerate(enriched_trains):
                logger.info(
                    f"  Train {i+1}: {train.train_id} from {train.origin_station_code} ({train.data_source}) - {len(getattr(train, 'stops', []))} stops"
                )

            consolidation_service = TrainConsolidationService()
            consolidated_trains = consolidation_service.consolidate_trains(
                enriched_trains, from_station_code
            )

            logger.info(f"Consolidation complete: {len(consolidated_trains)} consolidated journeys")
            for i, journey in enumerate(consolidated_trains):
                logger.info(
                    f"  Journey {i+1}: {journey['train_id']} with {len(journey['data_sources'])} sources"
                )

            return ConsolidatedTrainListResponse(
                metadata={
                    "timestamp": datetime.now().isoformat(),
                    "model_version": settings.model.version,
                    "train_count": len(consolidated_trains),
                    "page": 1,  # Consolidation affects pagination
                    "total_pages": 1,
                },
                trains=consolidated_trains,
            )
        else:
            return {
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "model_version": settings.model.version,
                    "train_count": filtered_count,
                    "page": offset // limit + 1,
                    "total_pages": (filtered_count + limit - 1) // limit if limit > 0 else 1,
                },
                "trains": enriched_trains,
            }
    except Exception as e:
        logger.exception(f"Error fetching trains: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{train_id}", response_model=TrainResponse)
async def get_train(
    train_id: str,
    from_station_code: Optional[str] = Query(
        None, description="Context station for journey-specific data (predictions, times)"
    ),
    train_repo: TrainRepository = Depends(get_train_repository),
    stop_repo: TrainStopRepository = Depends(get_train_stop_repository),
):
    """
    Get a specific train by its ID.

    If train_id is numeric, it's treated as a database ID (primary key).
    If train_id is not numeric, it's treated as an external train identifier.

    When from_station_code is provided:
    - Track predictions use the boarding station model
    - Departure times show boarding station context
    """
    try:
        # Validate from_station_code if provided
        if from_station_code:
            from trackcast.services.station_mapping import StationMapper

            station_mapper = StationMapper()
            if not station_mapper.is_valid_code(from_station_code):
                raise HTTPException(
                    status_code=400, detail=f"Invalid from_station_code: '{from_station_code}'"
                )
            from_station_code = station_mapper.translate_frontend_to_db_code(from_station_code)

        # Check if train_id is a numeric database ID
        if train_id.isdigit():
            db_id = int(train_id)
            train = train_repo.get_train_by_db_id(db_id)
            if not train:
                raise HTTPException(
                    status_code=404, detail=f"Train with database ID {db_id} not found"
                )
        else:
            # Use original lookup by train_id
            train = train_repo.get_train_by_id(train_id)
            if not train:
                raise HTTPException(status_code=404, detail=f"Train with ID {train_id} not found")

        # Enrich train with stop data
        enriched_train = _enrich_train_with_stops(train, stop_repo)

        # Generate context-aware prediction if from_station_code provided
        if from_station_code:
            enriched_train = _enrich_with_context_prediction(enriched_train, from_station_code)

        return enriched_train
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching train {train_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{train_id}/prediction", response_model=PredictionResponse)
async def get_train_prediction(
    train_id: str,
    from_station_code: Optional[str] = Query(
        None, description="Context station for journey-specific data (predictions, times)"
    ),
    train_repo: TrainRepository = Depends(get_train_repository),
):
    """
    Get prediction data for a specific train by ID.

    If train_id is numeric, it's treated as a database ID (primary key).
    If train_id is not numeric, it's treated as an external train identifier.

    When from_station_code is provided, generates context-aware prediction using the boarding station model.
    """
    try:
        # Validate from_station_code if provided
        if from_station_code:
            from trackcast.services.station_mapping import StationMapper

            station_mapper = StationMapper()
            if not station_mapper.is_valid_code(from_station_code):
                raise HTTPException(
                    status_code=400, detail=f"Invalid from_station_code: '{from_station_code}'"
                )
            from_station_code = station_mapper.translate_frontend_to_db_code(from_station_code)

        # Check if train_id is a numeric database ID
        if train_id.isdigit():
            db_id = int(train_id)
            train = train_repo.get_train_by_db_id(db_id)
            if not train:
                raise HTTPException(
                    status_code=404, detail=f"Train with database ID {db_id} not found"
                )
        else:
            # Use original lookup by train_id
            train = train_repo.get_train_by_id(train_id)
            if not train:
                raise HTTPException(status_code=404, detail=f"Train with ID {train_id} not found")

        # If context-aware prediction requested, generate it
        if from_station_code:
            context_prediction = _generate_context_prediction(train, from_station_code)
            if context_prediction:
                return context_prediction

        # Fallback to existing prediction
        if not train.prediction_data:
            raise HTTPException(
                status_code=404,
                detail=f"No prediction data available for train ID {train.train_id} (DB ID: {train.id})",
            )

        return train.prediction_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching prediction for train {train_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


def _train_stops_at_station(train, station_code: str) -> bool:
    """Check if train stops at the specified station."""
    if not hasattr(train, "stops") or not train.stops:
        return False
    return any(stop.station_code == station_code for stop in train.stops)


def _enrich_with_context_prediction(train, boarding_station_code: str):
    """Enrich train with context-aware prediction data."""
    try:
        # Verify train stops at boarding station
        if not _train_stops_at_station(train, boarding_station_code):
            logger.warning(
                f"Train {train.train_id} doesn't stop at {boarding_station_code}, using original prediction"
            )
            return train

        # Generate context prediction
        context_prediction = _generate_context_prediction(train, boarding_station_code)
        if context_prediction:
            # Replace the prediction data with context-aware version
            train.prediction_data = context_prediction

        return train
    except Exception as e:
        logger.error(f"Error generating context prediction for train {train.train_id}: {str(e)}")
        return train


def _generate_context_prediction(train, boarding_station_code: str):
    """Generate a context-aware prediction using the boarding station's model."""
    try:
        # Verify train stops at boarding station
        if not _train_stops_at_station(train, boarding_station_code):
            logger.warning(f"Train {train.train_id} doesn't stop at {boarding_station_code}")
            return None

        # Check if train has features
        if not train.model_data:
            logger.warning(f"Train {train.train_id} has no features for context prediction")
            return None

        # Import prediction service
        from trackcast.db.connection import get_db
        from trackcast.services.prediction import PredictionService

        # Create prediction service with database session
        db_session = next(get_db())
        prediction_service = PredictionService(db_session)

        # Generate context-aware prediction
        success, result = prediction_service.predict_train_with_context(
            train.train_id, boarding_station_code
        )

        if success and result.get("prediction_data"):
            logger.info(
                f"Generated context prediction for train {train.train_id} from {boarding_station_code}"
            )
            return result["prediction_data"]
        else:
            logger.warning(
                f"Failed to generate context prediction for train {train.train_id}: {result.get('error', 'Unknown error')}"
            )
            return None

    except Exception as e:
        logger.error(f"Error generating context prediction for train {train.train_id}: {str(e)}")
        return None
