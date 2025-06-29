"""API endpoints for push notification management.

Note: @trace_operation decorators are temporarily disabled on async endpoints
due to OpenTelemetry compatibility issues with request body parsing.
This allows notification endpoints to function correctly while maintaining
telemetry for other parts of the application.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from trackcast.db.connection import get_db
from trackcast.db.models import DeviceToken, LiveActivityToken
from trackcast.telemetry import trace_operation
from trackcast.utils import get_eastern_now

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/test", tags=["notifications"])
async def test_notifications_system(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Test endpoint to verify notification system is working.
    """
    logger.info("📝 Testing notification system...")
    try:
        # Test database connection
        db.execute(text("SELECT 1"))

        # Test model imports
        from trackcast.db.models import DeviceToken, LiveActivityToken

        # Test table queries
        device_count = db.query(DeviceToken).count()
        activity_count = db.query(LiveActivityToken).count()

        logger.info(
            f"📝 Notification system test successful: {device_count} devices, {activity_count} activities"
        )

        return {
            "status": "healthy",
            "message": "Notification system is working",
            "database_connected": True,
            "models_imported": True,
            "device_tokens_count": device_count,
            "live_activity_tokens_count": activity_count,
        }

    except Exception as e:
        logger.error(f"📝 Notification system test failed: {str(e)}")
        import traceback

        logger.error(f"📝 Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Notification system test failed: {str(e)}")


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
    user_origin_station_code: Optional[str] = Field(
        None, description="User's origin station code for the journey"
    )
    user_destination_station_code: Optional[str] = Field(
        None, description="User's destination station code for the journey"
    )


class LiveActivityTokenResponse(BaseModel):
    """Response model for Live Activity token registration."""

    id: int
    train_id: str
    push_token: str
    is_active: bool
    created_at: str
    message: str


@router.post("/device-tokens", response_model=DeviceTokenResponse, tags=["notifications"])
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
    logger.info(
        f"📱 Device token registration request received: platform={request.platform}, token_preview={request.device_token[:8]}..."
    )
    try:
        # Log database session info
        logger.info(f"📱 Database session active: {db is not None}")

        # Test database connection
        try:
            db.execute(text("SELECT 1"))
            logger.info("📱 Database connection test successful")
        except Exception as db_test_error:
            logger.error(f"📱 Database connection test failed: {str(db_test_error)}")
            raise HTTPException(
                status_code=500, detail=f"Database connection failed: {str(db_test_error)}"
            )
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
                logger.info(f"📱 Reactivated existing device token {existing_token.id}")
            else:
                logger.info(f"📱 Device token {existing_token.id} already exists and is active")

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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"📱 CRITICAL ERROR in register_device_token: {str(e)}")
        logger.error(f"📱 Error type: {type(e).__name__}")
        logger.error(f"📱 Error details: {repr(e)}")
        import traceback

        logger.error(f"📱 Full traceback: {traceback.format_exc()}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to register device token: {str(e)}")


@router.post(
    "/live-activities/register", response_model=LiveActivityTokenResponse, tags=["notifications"]
)
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
    logger.info(
        f"🚆 Live Activity registration request received: train_id={request.train_id}, token_preview={request.push_token[:8]}..., device_token_provided={request.device_token is not None}"
    )
    try:
        # Log database session info
        logger.info(f"🚆 Database session active: {db is not None}")

        # Test database connection
        try:
            db.execute(text("SELECT 1"))
            logger.info("🚆 Database connection test successful")
        except Exception as db_test_error:
            logger.error(f"🚆 Database connection test failed: {str(db_test_error)}")
            raise HTTPException(
                status_code=500, detail=f"Database connection failed: {str(db_test_error)}"
            )

        # Test table access
        try:
            from trackcast.db.models import DeviceToken, LiveActivityToken

            logger.info("🚆 Model imports successful")

            # Test if tables exist
            result = db.query(LiveActivityToken).limit(1).all()
            logger.info(
                f"🚆 LiveActivityToken table access successful, found {len(result)} records"
            )

            result = db.query(DeviceToken).limit(1).all()
            logger.info(f"🚆 DeviceToken table access successful, found {len(result)} records")

        except Exception as table_test_error:
            logger.error(f"🚆 Table access test failed: {str(table_test_error)}")
            raise HTTPException(
                status_code=500, detail=f"Database table access failed: {str(table_test_error)}"
            )
        # Check if the Live Activity token already exists
        existing_token = (
            db.query(LiveActivityToken)
            .filter(LiveActivityToken.push_token == request.push_token)
            .first()
        )

        if existing_token:
            # Update existing token if needed
            if not existing_token.is_active:
                existing_token.is_active = True
                existing_token.updated_at = get_eastern_now()
                message = "Live Activity token reactivated successfully"
            else:
                message = "Live Activity token already exists and is active"

            # Update user journey info if provided
            if request.user_origin_station_code:
                existing_token.user_origin_station_code = request.user_origin_station_code
            if request.user_destination_station_code:
                existing_token.user_destination_station_code = request.user_destination_station_code

            db.commit()
            logger.info(
                f"Updated Live Activity token {existing_token.id} for train {request.train_id}"
            )
            return LiveActivityTokenResponse(
                id=existing_token.id,
                train_id=existing_token.train_id,
                push_token=existing_token.push_token,
                is_active=existing_token.is_active,
                created_at=existing_token.created_at.isoformat(),
                message=message,
            )

        # Find or create the associated device token
        device = None
        if request.device_token:
            device = (
                db.query(DeviceToken)
                .filter(
                    DeviceToken.device_token == request.device_token, DeviceToken.is_active == True
                )
                .first()
            )

            if device:
                device.last_used = get_eastern_now()
                logger.info(f"Linked Live Activity to device token {device.id}")
            else:
                logger.warning(f"Device token not found: {request.device_token[:8]}...")

        # Create new Live Activity token
        live_activity_token = LiveActivityToken(
            train_id=request.train_id,
            push_token=request.push_token,
            device_token_id=device.id if device else None,
            is_active=True,
            activity_started_at=get_eastern_now(),
            user_origin_station_code=request.user_origin_station_code,
            user_destination_station_code=request.user_destination_station_code,
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"🚆 CRITICAL ERROR in register_live_activity_token: {str(e)}")
        logger.error(f"🚆 Error type: {type(e).__name__}")
        logger.error(f"🚆 Error details: {repr(e)}")
        import traceback

        logger.error(f"🚆 Full traceback: {traceback.format_exc()}")
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to register Live Activity token: {str(e)}"
        )


@router.get("/live-activities/active", tags=["notifications"])
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
    logger.info("📱 GET /live-activities/active request received")
    try:
        # Log database session info
        logger.info(f"📱 Database session active: {db is not None}")

        # Test database connection
        try:
            db.execute(text("SELECT 1"))
            logger.info("📱 Database connection test successful")
        except Exception as db_test_error:
            logger.error(f"📱 Database connection test failed: {str(db_test_error)}")
            raise HTTPException(
                status_code=500, detail=f"Database connection failed: {str(db_test_error)}"
            )

        # Test table import and access
        try:
            from trackcast.db.models import LiveActivityToken

            logger.info("📱 LiveActivityToken model import successful")
        except Exception as import_error:
            logger.error(f"📱 Model import failed: {str(import_error)}")
            raise HTTPException(status_code=500, detail=f"Model import failed: {str(import_error)}")
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"📱 CRITICAL ERROR in get_active_live_activities: {str(e)}")
        logger.error(f"📱 Error type: {type(e).__name__}")
        logger.error(f"📱 Error details: {repr(e)}")
        import traceback

        logger.error(f"📱 Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get active Live Activity tokens: {str(e)}"
        )


@router.delete("/live-activities/{token_id}", tags=["notifications"])
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
