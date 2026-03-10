"""
Route alert subscription API endpoints.

Allows iOS devices to register for push notifications and manage
alert subscriptions for delay/cancellation events on specific routes.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from trackrat.db.engine import get_db
from trackrat.models.database import DeviceToken, RouteAlertSubscription

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2", tags=["alerts"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class DeviceRegisterRequest(BaseModel):
    """Register or update an APNS device token."""

    device_id: str
    apns_token: str


class DeviceRegisterResponse(BaseModel):
    status: str = "registered"


class SubscriptionItem(BaseModel):
    data_source: str
    line_id: str | None = None
    from_station_code: str | None = None
    to_station_code: str | None = None
    train_id: str | None = None
    direction: str | None = None
    active_days: int = 127  # Bitmask: Mon=1..Sun=64, 127=all
    active_start_minutes: int | None = None  # Minutes from midnight
    active_end_minutes: int | None = None  # Minutes from midnight
    timezone: str | None = None  # IANA timezone
    delay_threshold_minutes: int | None = None  # NULL = system default
    service_threshold_pct: int | None = None  # NULL = system default
    notify_recovery: bool = False
    digest_time_minutes: int | None = None  # Minutes from midnight

    @model_validator(mode="after")
    def check_subscription_type(self) -> "SubscriptionItem":
        """Require exactly one of: line_id, both station codes, or train_id."""
        has_line = bool(self.line_id)
        has_stations = bool(self.from_station_code and self.to_station_code)
        has_train = bool(self.train_id)
        modes = sum([has_line, has_stations, has_train])
        if modes != 1:
            raise ValueError(
                "Must provide exactly one of: line_id, both from_station_code "
                "and to_station_code, or train_id"
            )
        return self


class SyncSubscriptionsRequest(BaseModel):
    """Full-replace subscription list for a device."""

    device_id: str
    subscriptions: list[SubscriptionItem]


class SubscriptionResponse(BaseModel):
    id: int
    data_source: str
    line_id: str | None = None
    from_station_code: str | None = None
    to_station_code: str | None = None
    train_id: str | None = None
    direction: str | None = None
    active_days: int = 127
    active_start_minutes: int | None = None
    active_end_minutes: int | None = None
    timezone: str | None = None
    delay_threshold_minutes: int | None = None
    service_threshold_pct: int | None = None
    notify_recovery: bool = False
    digest_time_minutes: int | None = None


class SyncSubscriptionsResponse(BaseModel):
    status: str = "synced"
    count: int


class GetSubscriptionsResponse(BaseModel):
    device_id: str
    subscriptions: list[SubscriptionResponse]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/devices/register", response_model=DeviceRegisterResponse)
async def register_device(
    request: DeviceRegisterRequest, db: AsyncSession = Depends(get_db)
) -> DeviceRegisterResponse:
    """Register or update a device's APNS token."""
    existing = await db.execute(
        select(DeviceToken).where(DeviceToken.device_id == request.device_id)
    )
    token = existing.scalar_one_or_none()

    if token:
        token.apns_token = request.apns_token
    else:
        token = DeviceToken(
            device_id=request.device_id,
            apns_token=request.apns_token,
        )
        db.add(token)

    await db.commit()

    logger.info("device_registered", device_id=request.device_id)
    return DeviceRegisterResponse()


@router.put("/alerts/subscriptions", response_model=SyncSubscriptionsResponse)
async def sync_subscriptions(
    request: SyncSubscriptionsRequest, db: AsyncSession = Depends(get_db)
) -> SyncSubscriptionsResponse:
    """Full-replace all alert subscriptions for a device."""
    # Verify device exists
    existing = await db.execute(
        select(DeviceToken).where(DeviceToken.device_id == request.device_id)
    )
    if not existing.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Device not registered")

    # Delete existing subscriptions
    await db.execute(
        delete(RouteAlertSubscription).where(
            RouteAlertSubscription.device_id == request.device_id
        )
    )

    # Insert new subscriptions
    for item in request.subscriptions:
        sub = RouteAlertSubscription(
            device_id=request.device_id,
            data_source=item.data_source,
            line_id=item.line_id,
            from_station_code=item.from_station_code,
            to_station_code=item.to_station_code,
            train_id=item.train_id,
            direction=item.direction,
            active_days=item.active_days,
            active_start_minutes=item.active_start_minutes,
            active_end_minutes=item.active_end_minutes,
            timezone=item.timezone,
            delay_threshold_minutes=item.delay_threshold_minutes,
            service_threshold_pct=item.service_threshold_pct,
            notify_recovery=item.notify_recovery,
            digest_time_minutes=item.digest_time_minutes,
        )
        db.add(sub)

    await db.commit()

    logger.info(
        "subscriptions_synced",
        device_id=request.device_id,
        count=len(request.subscriptions),
    )
    return SyncSubscriptionsResponse(count=len(request.subscriptions))


@router.get(
    "/alerts/subscriptions/{device_id}",
    response_model=GetSubscriptionsResponse,
)
async def get_subscriptions(
    device_id: str, db: AsyncSession = Depends(get_db)
) -> GetSubscriptionsResponse:
    """Get all alert subscriptions for a device."""
    existing = await db.execute(
        select(DeviceToken)
        .where(DeviceToken.device_id == device_id)
        .options(selectinload(DeviceToken.subscriptions))
    )
    device = existing.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not registered")

    return GetSubscriptionsResponse(
        device_id=device_id,
        subscriptions=[
            SubscriptionResponse(
                id=sub.id,
                data_source=sub.data_source,
                line_id=sub.line_id,
                from_station_code=sub.from_station_code,
                to_station_code=sub.to_station_code,
                train_id=sub.train_id,
                direction=sub.direction,
                active_days=sub.active_days,
                active_start_minutes=sub.active_start_minutes,
                active_end_minutes=sub.active_end_minutes,
                timezone=sub.timezone,
                delay_threshold_minutes=sub.delay_threshold_minutes,
                service_threshold_pct=sub.service_threshold_pct,
                notify_recovery=sub.notify_recovery,
                digest_time_minutes=sub.digest_time_minutes,
            )
            for sub in device.subscriptions
        ],
    )
