"""
Trip search API endpoint for TrackRat V2.

Provides unified trip search that handles both direct service
and transfer-based connections transparently.
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.api.utils import handle_errors
from trackrat.db.engine import get_db
from trackrat.models.api import TripSearchResponse
from trackrat.services.trip_search import search_trips

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2/trips", tags=["trips"])


@router.get("/search", response_model=TripSearchResponse)
@handle_errors
async def search_trips_endpoint(
    from_station: str = Query(
        ...,
        alias="from",
        min_length=2,
        max_length=10,
        description="Departure station code",
    ),
    to_station: str = Query(
        ...,
        alias="to",
        min_length=2,
        max_length=10,
        description="Arrival station code",
    ),
    search_date: date | None = Query(
        None,
        alias="date",
        description="Journey date (YYYY-MM-DD). Defaults to today.",
    ),
    time_from: datetime | None = Query(
        None,
        description="Start of time window (ISO 8601)",
    ),
    time_to: datetime | None = Query(
        None,
        description="End of time window (ISO 8601)",
    ),
    hide_departed: bool = Query(
        False,
        description="Hide trains that have already departed",
    ),
    data_sources: str | None = Query(
        None,
        description="Comma-separated data sources (e.g., 'NJT,AMTRAK,PATH')",
    ),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of trip options"),
    db: AsyncSession = Depends(get_db),
) -> TripSearchResponse:
    """Search for trips between two stations.

    Returns direct service when available. When no direct service exists,
    automatically finds 1-transfer connections via nearby stations in
    other transit systems.
    """
    from_station = from_station.upper()
    to_station = to_station.upper()

    if from_station == to_station:
        raise HTTPException(
            status_code=400, detail="Origin and destination cannot be the same station"
        )

    # Parse data_sources the same way as departures endpoint
    source_list: list[str] | None = None
    if data_sources:
        source_list = [s.strip().upper() for s in data_sources.split(",") if s.strip()]

    return await search_trips(
        db=db,
        from_station=from_station,
        to_station=to_station,
        search_date=search_date,
        time_from=time_from,
        time_to=time_to,
        hide_departed=hide_departed,
        data_sources=source_list,
        limit=limit,
    )
