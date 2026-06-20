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

logger = get_logger(__name__)


def get_client_ip(request: Request) -> str:
    """Return the originating client IP for a request.

    Behind GCP's HTTP(S) load balancer the direct peer is the load balancer, so
    the real client IP is the first entry of the ``X-Forwarded-For`` header. Fall
    back to the direct peer address, then ``"unknown"`` when neither is present.
    """
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
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
