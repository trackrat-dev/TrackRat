"""
API utilities for error handling and common operations.
"""

import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any

from fastapi import HTTPException
from sqlalchemy.exc import DatabaseError, OperationalError
from structlog import get_logger

from trackrat.collectors.njt_client import NJTransitAPIError

logger = get_logger(__name__)


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
        except asyncio.TimeoutError as e:
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
