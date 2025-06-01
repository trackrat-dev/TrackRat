"""API endpoints for train stop data."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from trackcast.db.connection import get_db
from trackcast.db.repository import TrainStopRepository, TrainRepository
from trackcast.api.models import TrainListResponse, TrainResponse


def get_train_stop_repository():
    """Get a train stop repository instance with a DB session."""
    db = next(get_db())
    return TrainStopRepository(db)


def get_train_repository():
    """Get a train repository instance with a DB session."""
    db = next(get_db())
    return TrainRepository(db)


router = APIRouter()
logger = logging.getLogger(__name__)


class Station(BaseModel):
    """A train station."""
    station_code: Optional[str] = None
    station_name: str


class StationListResponse(BaseModel):
    """Response model for listing stations."""
    stations: List[Station]
    total_count: int


@router.get("/", response_model=StationListResponse)
async def list_stations(
    search: Optional[str] = Query(None, description="Search stations by name or code"),
    stop_repo: TrainStopRepository = Depends(get_train_stop_repository),
):
    """
    Get a list of all train stations.
    
    Parameters:
    - search: Optional search query to filter stations by name or code
    """
    try:
        if search:
            stations_data = stop_repo.search_stations(search)
        else:
            stations_data = stop_repo.get_all_stations()
        
        stations = [Station(**station) for station in stations_data]
        
        return {
            "stations": stations,
            "total_count": len(stations)
        }
    except Exception as e:
        logger.error(f"Error fetching stations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{station_identifier}/trains", response_model=TrainListResponse)
async def get_trains_for_station(
    station_identifier: str,
    limit: int = Query(20, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    train_repo: TrainRepository = Depends(get_train_repository),
    stop_repo: TrainStopRepository = Depends(get_train_stop_repository),
):
    """
    Get all trains that stop at a specific station.
    
    Parameters:
    - station_identifier: Station code (e.g., "PH") or station name (e.g., "Philadelphia")
    - limit: Maximum number of trains to return
    - offset: Pagination offset
    """
    try:
        # Determine if identifier is a station code or name by checking if it's all uppercase and short
        if len(station_identifier) <= 3 and station_identifier.isupper():
            # Likely a station code
            trains, total_count = train_repo.get_trains(
                stops_at_station_code=station_identifier,
                limit=limit,
                offset=offset,
                sort_by="departure_time",
                sort_order="asc"
            )
        else:
            # Likely a station name
            trains, total_count = train_repo.get_trains(
                stops_at_station_name=station_identifier,
                limit=limit,
                offset=offset,
                sort_by="departure_time", 
                sort_order="asc"
            )
        
        # Enrich trains with stop data
        from trackcast.api.routers.trains import _enrich_train_with_stops
        enriched_trains = []
        for train in trains:
            enriched_train = _enrich_train_with_stops(train, stop_repo)
            enriched_trains.append(enriched_train)
        
        return {
            "metadata": {
                "timestamp": "2024-01-01T00:00:00",  # Will be set by actual timestamp
                "model_version": None,
                "train_count": total_count,
                "page": offset // limit + 1,
                "total_pages": (total_count + limit - 1) // limit,
            },
            "trains": enriched_trains,
        }
    except Exception as e:
        logger.error(f"Error fetching trains for station {station_identifier}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")