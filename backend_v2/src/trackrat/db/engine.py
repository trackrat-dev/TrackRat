"""
Database connection management for TrackRat V2.

Uses PostgreSQL with asyncpg for scalable, concurrent database access.
"""

import asyncio
import functools
from collections.abc import AsyncGenerator, Awaitable, Callable
import contextlib
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from structlog import get_logger

from trackrat.settings import get_settings

logger = get_logger(__name__)

# Type for decorated functions
F = TypeVar("F", bound=Callable[..., Any])

# Global engine and session maker
_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _is_postgresql_concurrency_error(error: Exception) -> bool:
    """Check if an error is a PostgreSQL concurrency issue that should be retried."""
    error_msg = str(error).lower()

    # PostgreSQL-specific error conditions that warrant retry
    postgresql_retry_conditions = [
        # Connection issues
        "connection reset by peer",
        "server closed the connection unexpectedly",
        "connection to server was lost",
        "could not receive data from server",
        # Concurrency/locking issues
        "deadlock detected",
        "serialization failure",
        "could not serialize access due to concurrent update",
        "could not serialize access due to read/write dependencies",
        # Statement cancellation (e.g., asyncpg command_timeout)
        "canceling statement due to user request",
        # Temporary resource issues
        "too many connections",
        "connection pool exhausted",
        "temporary failure in name resolution",
    ]

    return any(condition in error_msg for condition in postgresql_retry_conditions)


def with_db_retry(max_attempts: int = 3, base_delay: float = 0.5) -> Callable[[F], F]:
    """Decorator for PostgreSQL operations with retry logic for transient errors."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if (
                        _is_postgresql_concurrency_error(e)
                        and attempt < max_attempts - 1
                    ):
                        # Wait with exponential backoff
                        wait_time = base_delay * (2**attempt)
                        logger.debug(
                            "postgresql_retry",
                            function=func.__name__,
                            attempt=attempt + 1,
                            wait_time=wait_time,
                            error=str(e),
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        # Re-raise if not a PostgreSQL retry condition or max attempts reached
                        raise
            return None  # This shouldn't be reached

        return wrapper  # type: ignore[return-value]

    return decorator


T = TypeVar("T")


async def retry_on_deadlock(
    session: AsyncSession,
    operation: Callable[[], Awaitable[T]],
    max_attempts: int = 3,
    base_delay: float = 0.1,
) -> T:
    """Retry an operation on deadlock, rolling back between attempts.

    Use this when an operation may encounter deadlocks due to concurrent updates.
    The session is rolled back between attempts to clear the failed transaction state.

    Args:
        session: The database session (will be rolled back on retry)
        operation: Async callable to execute
        max_attempts: Maximum retry attempts (default: 3)
        base_delay: Base delay in seconds between retries (exponential backoff)

    Returns:
        Result of the operation

    Raises:
        Exception: Re-raises the last exception if all retries fail
    """
    last_error: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return await operation()
        except Exception as e:
            last_error = e
            if _is_postgresql_concurrency_error(e) and attempt < max_attempts - 1:
                wait_time = base_delay * (2**attempt)
                logger.warning(
                    "deadlock_retry",
                    attempt=attempt + 1,
                    max_attempts=max_attempts,
                    wait_time=wait_time,
                    error=str(e)[:200],
                )
                await session.rollback()
                await asyncio.sleep(wait_time)
                continue
            raise

    # Should not reach here, but satisfy type checker
    if last_error:
        raise last_error
    raise RuntimeError("retry_on_deadlock: unexpected state")


def get_engine() -> AsyncEngine:
    """Get or create the async engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        db_url = str(settings.database_url)

        # PostgreSQL configuration for optimal performance
        engine_kwargs = {
            "pool_size": 10,  # Connection pool size
            "max_overflow": 20,  # Additional connections beyond pool_size
            "pool_timeout": 30,  # Timeout when getting connection from pool
            "pool_recycle": 3600,  # Recycle connections after 1 hour
            "pool_pre_ping": True,  # Validate connections before use
            "echo": settings.enable_sql_logging,
            "connect_args": {
                "command_timeout": 60,  # Query timeout in seconds
                "server_settings": {
                    "application_name": "trackrat-v2",  # For monitoring
                    "jit": "off",  # Disable JIT for faster connections
                    "timezone": "America/New_York",  # Match app timezone
                },
            },
        }

        _engine = create_async_engine(db_url, **engine_kwargs)

    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Get or create the session factory."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _sessionmaker


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        except BaseException:
            with contextlib.suppress(Exception):
                await session.rollback()
            raise
        finally:
            await session.close()


async def close_engine() -> None:
    """Close the database engine."""
    global _engine, _sessionmaker
    if _engine:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to get database sessions."""
    async with get_session() as session:
        yield session


async def health_check() -> dict[str, str]:
    """Database health check with PostgreSQL connection status."""
    try:
        async with get_session() as session:
            # Test basic connectivity
            result = await session.execute(text("SELECT 1"))
            result.fetchone()

            # Get PostgreSQL version
            version_result = await session.execute(text("SELECT version()"))
            version = version_result.scalar()

            return {
                "status": "healthy",
                "database_type": "postgresql",
                "version": version or "unknown",
            }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "error_type": type(e).__name__}
