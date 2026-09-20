"""
Client telemetry API endpoint.

Records how iOS setup finished so the onboarding funnel — which system was
chosen, whether home/work stations were set, whether the location shortcut was
used, whether setup was skipped — can be measured instead of guessed at.

Log-only, like the feedback endpoint. Filter with:
jsonPayload.logger="trackrat.api.telemetry"

Deliberately carries no station codes (a home station says where someone lives)
and no client IP: this is an aggregate metric, not a report anyone follows up on.
``ONBOARDING_PATH`` is excluded from ``request_stats_middleware`` in ``main.py``
for the same reason — that middleware retains a client IP per request, which
would re-attach one to every setup completion the log event leaves out.
"""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator
from structlog import get_logger

from trackrat.services.departure import ALL_DATA_SOURCES

# Use a dedicated logger name for easy filtering in GCP Logs Explorer
# Filter with: jsonPayload.logger="trackrat.api.telemetry"
logger = get_logger("trackrat.api.telemetry")

router = APIRouter(prefix="/api/v2/telemetry", tags=["telemetry"])

# Route path of the onboarding beacon, single-sourced here so main.py can
# exclude it from request statistics without restating the prefix.
ONBOARDING_PATH = f"{router.prefix}/onboarding"


class OnboardingCompletedRequest(BaseModel):
    """Shape of a finished onboarding run."""

    systems: str = Field(default="", max_length=200)
    home_station_set: bool = False
    work_station_set: bool = False
    favorites_count: int = Field(default=0, ge=0, le=100)
    used_location: bool = False
    skipped: bool = False
    app_version: str | None = Field(default=None, max_length=50)

    @field_validator("systems")
    @classmethod
    def keep_known_sources(cls, value: str) -> str:
        """Drop anything that isn't a real data source.

        The endpoint is unauthenticated, so without this an arbitrary string
        would land in the structured logs the funnel is read from.
        """
        known = {source for source in value.split(",") if source in ALL_DATA_SOURCES}
        return ",".join(sorted(known))


class TelemetryResponse(BaseModel):
    """Response from a telemetry submission."""

    status: str = "received"


@router.post("/onboarding", response_model=TelemetryResponse)
async def report_onboarding_completed(
    request: OnboardingCompletedRequest,
) -> TelemetryResponse:
    """Record how an onboarding run finished."""
    logger.info(
        "onboarding_completed",
        systems=request.systems,
        home_station_set=request.home_station_set,
        work_station_set=request.work_station_set,
        favorites_count=request.favorites_count,
        used_location=request.used_location,
        skipped=request.skipped,
        app_version=request.app_version,
        timestamp=datetime.now(UTC).isoformat(),
    )

    return TelemetryResponse()
