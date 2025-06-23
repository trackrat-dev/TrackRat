"""API endpoints for push notification management."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from trackcast.db.connection import get_db
from trackcast.db.models import DeviceToken, LiveActivityToken
from trackcast.telemetry import trace_operation
from trackcast.utils import get_eastern_now

logger = logging.getLogger(__name__)
router = APIRouter()


# Request/Response Models
class DeviceTokenRequest(BaseModel):
    """Request model for device token registration."""

    device_token: str = Field(..., description="Device push notification token")
    platform: str = Field(..., description="Platform: 'ios' or 'android'")
    timestamp: Optional[str] = Field(None, description="Registration timestamp")


class DeviceTokenResponse(BaseModel):
    """Response model for device token registration."""

    id: int
    device_token: str
    platform: str
    is_active: bool
    created_at: str
    message: str


class LiveActivityTokenRequest(BaseModel):
    """Request model for Live Activity token registration."""

    train_id: str = Field(..., description="Train ID for the Live Activity")
    push_token: str = Field(..., description="Live Activity push token")
    device_token: Optional[str] = Field(None, description="Device token for regular notifications")
    platform: str = Field(default="ios", description="Platform")
    timestamp: Optional[str] = Field(None, description="Registration timestamp")


class LiveActivityTokenResponse(BaseModel):
    """Response model for Live Activity token registration."""

    id: int
    train_id: str
    push_token: str
    is_active: bool
    created_at: str
    message: str


@router.post("/device-tokens/", response_model=DeviceTokenResponse, tags=["notifications"])
@trace_operation("register_device_token")
async def register_device_token(
    request: DeviceTokenRequest, db: Session = Depends(get_db)
) -> DeviceTokenResponse:
    """
    Register a device token for push notifications.

    This endpoint registers a device token that can be used to send push notifications
    to the device. The token is stored with platform information and activation status.

    Args:
        request: Device token registration data
        db: Database session

    Returns:
        DeviceTokenResponse with registration details

    Raises:
        HTTPException: If registration fails or token is invalid
    """
    try:
        # Validate platform
        if request.platform not in ["ios", "android"]:
            raise HTTPException(status_code=400, detail="Platform must be 'ios' or 'android'")

        # Check if device token already exists
        existing_token = (
            db.query(DeviceToken).filter(DeviceToken.device_token == request.device_token).first()
        )

        if existing_token:
            # Update existing token to active if inactive
            if not existing_token.is_active:
                existing_token.is_active = True
                existing_token.updated_at = get_eastern_now()
                db.commit()
                logger.info(f"Reactivated existing device token {existing_token.id}")

            return DeviceTokenResponse(
                id=existing_token.id,
                device_token=existing_token.device_token,
                platform=existing_token.platform,
                is_active=existing_token.is_active,
                created_at=existing_token.created_at.isoformat(),
                message="Device token updated successfully",
            )

        # Create new device token
        device_token = DeviceToken(
            device_token=request.device_token, platform=request.platform, is_active=True
        )

        db.add(device_token)
        db.commit()
        db.refresh(device_token)

        logger.info(
            f"Registered new device token {device_token.id} for platform {request.platform}"
        )

        return DeviceTokenResponse(
            id=device_token.id,
            device_token=device_token.device_token,
            platform=device_token.platform,
            is_active=device_token.is_active,
            created_at=device_token.created_at.isoformat(),
            message="Device token registered successfully",
        )

    except Exception as e:
        logger.error(f"Failed to register device token: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to register device token: {str(e)}")


@router.post(
    "/live-activities/register", response_model=LiveActivityTokenResponse, tags=["notifications"]
)
@trace_operation("register_live_activity_token")
async def register_live_activity_token(
    request: LiveActivityTokenRequest, db: Session = Depends(get_db)
) -> LiveActivityTokenResponse:
    """
    Register a Live Activity push token for a specific train.

    This endpoint registers a push token that can be used to send updates to a specific
    Live Activity on iOS devices. The token is associated with a train ID.

    Args:
        request: Live Activity token registration data
        db: Database session

    Returns:
        LiveActivityTokenResponse with registration details

    Raises:
        HTTPException: If registration fails or token is invalid
    """
    try:
        # Check if token already exists for this train
        existing_token = (
            db.query(LiveActivityToken)
            .filter(
                LiveActivityToken.push_token == request.push_token,
                LiveActivityToken.train_id == request.train_id,
            )
            .first()
        )

        if existing_token:
            # Update existing token to active if inactive
            if not existing_token.is_active:
                existing_token.is_active = True
                existing_token.updated_at = get_eastern_now()
                existing_token.activity_started_at = get_eastern_now()
                db.commit()
                logger.info(f"Reactivated existing Live Activity token {existing_token.id}")

            return LiveActivityTokenResponse(
                id=existing_token.id,
                train_id=existing_token.train_id,
                push_token=existing_token.push_token,
                is_active=existing_token.is_active,
                created_at=existing_token.created_at.isoformat(),
                message="Live Activity token updated successfully",
            )

        # Find associated device token if provided
        device_token_id = None
        if request.device_token:
            device_token = (
                db.query(DeviceToken)
                .filter(
                    DeviceToken.device_token == request.device_token, DeviceToken.is_active == True
                )
                .first()
            )

            if device_token:
                device_token_id = device_token.id
                device_token.last_used = get_eastern_now()
                logger.info(f"Linked Live Activity to device token {device_token.id}")
            else:
                logger.warning(f"Device token not found: {request.device_token[:8]}...")

        # Create new Live Activity token
        live_activity_token = LiveActivityToken(
            push_token=request.push_token,
            train_id=request.train_id,
            device_token_id=device_token_id,
            is_active=True,
            activity_started_at=get_eastern_now(),
        )

        db.add(live_activity_token)
        db.commit()
        db.refresh(live_activity_token)

        logger.info(
            f"Registered new Live Activity token {live_activity_token.id} for train {request.train_id}"
        )

        return LiveActivityTokenResponse(
            id=live_activity_token.id,
            train_id=live_activity_token.train_id,
            push_token=live_activity_token.push_token,
            is_active=live_activity_token.is_active,
            created_at=live_activity_token.created_at.isoformat(),
            message="Live Activity token registered successfully",
        )

    except Exception as e:
        logger.error(f"Failed to register Live Activity token: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to register Live Activity token: {str(e)}"
        )


@router.get("/live-activities/active", tags=["notifications"])
@trace_operation("get_active_live_activities")
async def get_active_live_activities(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    Get all active Live Activity tokens.

    This endpoint returns all currently active Live Activity tokens that can receive
    push notification updates.

    Args:
        db: Database session

    Returns:
        List of active Live Activity tokens with metadata
    """
    try:
        active_tokens = (
            db.query(LiveActivityToken).filter(LiveActivityToken.is_active == True).all()
        )

        result = []
        for token in active_tokens:
            result.append(
                {
                    "id": token.id,
                    "train_id": token.train_id,
                    "push_token": token.push_token[:8] + "...",  # Truncated for security
                    "activity_started_at": (
                        token.activity_started_at.isoformat() if token.activity_started_at else None
                    ),
                    "last_update_sent": (
                        token.last_update_sent.isoformat() if token.last_update_sent else None
                    ),
                    "created_at": token.created_at.isoformat(),
                }
            )

        logger.info(f"Retrieved {len(active_tokens)} active Live Activity tokens")
        return result

    except Exception as e:
        logger.error(f"Failed to get active Live Activity tokens: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get active Live Activity tokens: {str(e)}"
        )


@router.delete("/live-activities/{token_id}", tags=["notifications"])
@trace_operation("deactivate_live_activity_token")
async def deactivate_live_activity_token(
    token_id: int, db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Deactivate a Live Activity token.

    This endpoint deactivates a Live Activity token, marking it as inactive and
    setting the activity end time. The token will no longer receive push updates.

    Args:
        token_id: ID of the Live Activity token to deactivate
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If token not found or deactivation fails
    """
    try:
        token = db.query(LiveActivityToken).filter(LiveActivityToken.id == token_id).first()

        if not token:
            raise HTTPException(status_code=404, detail=f"Live Activity token {token_id} not found")

        token.is_active = False
        token.activity_ended_at = get_eastern_now()
        token.updated_at = get_eastern_now()

        db.commit()

        logger.info(f"Deactivated Live Activity token {token_id} for train {token.train_id}")

        return {"message": f"Live Activity token {token_id} deactivated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deactivate Live Activity token {token_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to deactivate Live Activity token: {str(e)}"
        )
