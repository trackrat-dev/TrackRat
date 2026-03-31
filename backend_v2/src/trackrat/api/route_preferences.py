"""Route filter preference API endpoints.

Allows devices to persist per-route system/line filter preferences
so the Route Status view remembers which transit systems are enabled.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.db.engine import get_db
from trackrat.models.database import DeviceToken, RoutePreference

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2", tags=["route_preferences"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class RoutePreferenceRequest(BaseModel):
    """Upsert a route filter preference."""

    device_id: str
    from_station_code: str
    to_station_code: str
    enabled_systems: dict[str, list[str]]  # e.g. {"NJT": ["NE"], "AMTRAK": []}


class RoutePreferenceResponse(BaseModel):
    from_station_code: str
    to_station_code: str
    enabled_systems: dict[str, list[str]]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/routes/preferences", response_model=RoutePreferenceResponse)
async def get_route_preference(
    device_id: str = Query(..., description="Device identifier"),
    from_station: str = Query(..., alias="from", description="Origin station code"),
    to_station: str = Query(..., alias="to", description="Destination station code"),
    db: AsyncSession = Depends(get_db),
) -> RoutePreferenceResponse:
    """Get saved route filter preference for a device + station pair."""
    result = await db.execute(
        select(RoutePreference).where(
            RoutePreference.device_id == device_id,
            RoutePreference.from_station_code == from_station,
            RoutePreference.to_station_code == to_station,
        )
    )
    pref = result.scalar_one_or_none()

    if not pref:
        raise HTTPException(status_code=404, detail="No preference saved")

    return RoutePreferenceResponse(
        from_station_code=pref.from_station_code,
        to_station_code=pref.to_station_code,
        enabled_systems=pref.enabled_systems or {},
    )


@router.put("/routes/preferences", response_model=RoutePreferenceResponse)
async def upsert_route_preference(
    request: RoutePreferenceRequest,
    db: AsyncSession = Depends(get_db),
) -> RoutePreferenceResponse:
    """Create or update a route filter preference for a device + station pair."""
    # Verify device exists
    existing_device = await db.execute(
        select(DeviceToken).where(DeviceToken.device_id == request.device_id)
    )
    if not existing_device.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Device not registered")

    # Atomic upsert via ON CONFLICT DO UPDATE
    stmt = (
        pg_insert(RoutePreference)
        .values(
            device_id=request.device_id,
            from_station_code=request.from_station_code,
            to_station_code=request.to_station_code,
            enabled_systems=request.enabled_systems,
        )
        .on_conflict_do_update(
            constraint="uq_route_pref_device_stations",
            set_={"enabled_systems": request.enabled_systems},
        )
    )
    await db.execute(stmt)
    await db.commit()

    logger.info(
        "route_preference_saved",
        device_id=request.device_id[:8] + "...",
        from_station=request.from_station_code,
        to_station=request.to_station_code,
        systems=list(request.enabled_systems.keys()),
    )

    return RoutePreferenceResponse(
        from_station_code=request.from_station_code,
        to_station_code=request.to_station_code,
        enabled_systems=request.enabled_systems,
    )
