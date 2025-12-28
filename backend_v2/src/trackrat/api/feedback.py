"""
User feedback API endpoint.

Simple endpoint to collect user feedback about data issues.
Feedback is logged with structured data for easy filtering in GCP Logs Explorer.
"""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel
from structlog import get_logger

# Use a dedicated logger name for easy filtering in GCP Logs Explorer
# Filter with: jsonPayload.logger="trackrat.api.feedback"
logger = get_logger("trackrat.api.feedback")

router = APIRouter(prefix="/api/v2/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    """User feedback submission."""

    message: str
    screen: str  # e.g., "train_list", "train_details"
    train_id: str | None = None
    origin_code: str | None = None
    destination_code: str | None = None
    app_version: str | None = None
    device_model: str | None = None


class FeedbackResponse(BaseModel):
    """Response from feedback submission."""

    status: str = "received"
    message: str = "Thank you for your feedback!"


@router.post("", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """
    Submit user feedback about data issues.

    Feedback is logged with structured data for easy filtering:
    - In GCP Logs Explorer, filter by: jsonPayload.event="user_feedback_submitted"
    - Or filter by logger: jsonPayload.logger="trackrat.api.feedback"
    """
    logger.info(
        "user_feedback_submitted",
        message=request.message,
        screen=request.screen,
        train_id=request.train_id,
        origin_code=request.origin_code,
        destination_code=request.destination_code,
        app_version=request.app_version,
        device_model=request.device_model,
        timestamp=datetime.utcnow().isoformat(),
    )

    return FeedbackResponse()
