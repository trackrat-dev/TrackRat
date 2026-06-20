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
