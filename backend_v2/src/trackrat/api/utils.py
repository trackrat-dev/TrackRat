"""
API utilities for error handling and common operations.
"""

from collections.abc import Callable
from functools import wraps
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy.exc import DatabaseError, OperationalError
from structlog import get_logger

from trackrat.collectors.njt.client import NJTransitAPIError
from trackrat.settings import get_settings

logger = get_logger(__name__)


def ensure_source_enabled(data_source: str | None) -> None:
    """Raise 404 if ``data_source`` is globally disabled.

    Guards the train_id/source-scoped endpoints (train detail, train history,
    track/delay predictions, route history) so residual rows from a source in
    ``TRACKRAT_DISABLED_DATA_SOURCES`` — still present within the retention
    window after the source was turned off — are never served, even to a caller
    that already holds a disabled-source train_id. List/aggregate endpoints
    resolve the active set via ``active_data_sources()`` instead; this guard is
    for the paths that look a record up directly and so can't filter by list.

    A ``None`` data_source is a no-op: the caller didn't scope to a source, so
    there is nothing to reject here.
    """
    if data_source and get_settings().is_data_source_disabled(data_source):
        raise HTTPException(
            status_code=404,
            detail=f"Data source '{data_source}' is not available",
        )


def get_client_ip(request: Request) -> str:
    """Return the originating client IP for a request.

    Behind GCP's external HTTP(S) load balancer the LB appends
    ``"<client-ip>,<lb-ip>"`` to any existing ``X-Forwarded-For`` header rather
    than overwriting it, so the trusted client IP is the second-to-last entry.
    Earlier entries can be forged by the client. When the header is missing or
    has only one entry (e.g. local dev — the LB would always have added its own
    pair in production), fall back to the direct peer.

    See https://cloud.google.com/load-balancing/docs/https#x-forwarded-for_header
    """
    forwarded = [
        part.strip()
        for part in request.headers.get("x-forwarded-for", "").split(",")
        if part.strip()
    ]
    if len(forwarded) >= 2:
        return forwarded[-2]
    return request.client.host if request.client else "unknown"


def handle_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to handle common API errors with appropriate responses."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            # Re-raise FastAPI exceptions as-is
            raise
        except (DatabaseError, OperationalError) as e:
            logger.error(f"database_error_{func.__name__}", error=str(e))
            raise HTTPException(503, "Service temporarily unavailable") from e
        except TimeoutError as e:
            logger.error(f"timeout_{func.__name__}")
            raise HTTPException(504, "Request timeout") from e
        except NJTransitAPIError as e:
            logger.error(f"njt_api_error_{func.__name__}", error=str(e))
            raise HTTPException(502, "External service error") from e
        except Exception as e:
            logger.error(
                f"unexpected_error_{func.__name__}",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise HTTPException(500, "Internal server error") from e

    return wrapper
