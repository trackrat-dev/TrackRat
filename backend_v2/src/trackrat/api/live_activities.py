"""
Minimal Live Activities API endpoints.

Simple registration and unregistration for iOS Live Activity tokens.
"""

from datetime import datetime, timedelta
from typing import cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from trackrat.db.engine import get_db
from trackrat.models.database import LiveActivityToken
from trackrat.utils.time import now_et

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2/live-activities", tags=["live-activities"])


class RegisterRequest(BaseModel):
    """Request to register a Live Activity."""

    push_token: str
    activity_id: str
    train_number: str
    origin_code: str
    destination_code: str


class RegisterResponse(BaseModel):
    """Response from registration."""

    status: str = "registered"
    expires_at: datetime


@router.post("/register", response_model=RegisterResponse)
async def register_live_activity(
    request: RegisterRequest, db: AsyncSession = Depends(get_db)
) -> RegisterResponse:
    """Register or update an iOS Live Activity for push notifications.

    If a token already exists, updates the associated train and stations.
    Registrations expire after 6 hours.
    """
    # Simple expiration: 6 hours from now
    expires_at = now_et() + timedelta(hours=6)

    # Check if token already exists
    existing = await db.execute(
        select(LiveActivityToken).where(
            LiveActivityToken.push_token == request.push_token
        )
    )
    token = existing.scalar_one_or_none()

    if token:
        # Update existing token
        token.train_number = request.train_number
        token.origin_code = request.origin_code
        token.destination_code = request.destination_code
        token.expires_at = expires_at
        token.is_active = True
    else:
        # Create new token
        token = LiveActivityToken(
            push_token=request.push_token,
            activity_id=request.activity_id,
            train_number=request.train_number,
            origin_code=request.origin_code,
            destination_code=request.destination_code,
            expires_at=expires_at,
            is_active=True,
        )
        db.add(token)

    await db.commit()

    logger.info(
        "live_activity_registered",
        train_number=request.train_number,
        origin=request.origin_code,
        destination=request.destination_code,
    )

    return RegisterResponse(expires_at=expires_at)


@router.delete("/{push_token}")
async def unregister_live_activity(
    push_token: str, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    """Unregister a Live Activity by push token. Returns 404 if token not found."""
    result = cast(
        CursorResult[tuple[()]],
        await db.execute(
            delete(LiveActivityToken).where(LiveActivityToken.push_token == push_token)
        ),
    )
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Token not found")

    logger.info("live_activity_unregistered", push_token=push_token)

    return {"status": "unregistered"}
