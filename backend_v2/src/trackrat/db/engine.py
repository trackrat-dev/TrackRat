"""
Database connection management for TrackRat V2.

Uses SQLite with aiosqlite for simple, zero-configuration database access.
"""

import asyncio
import functools
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from structlog import get_logger

from trackrat.settings import get_settings

logger = get_logger(__name__)

# Type for decorated functions
F = TypeVar("F", bound=Callable[..., Any])

# Global engine and session maker
_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _is_concurrency_error(error: Exception) -> bool:
    """Check if an error is related to SQLite concurrency issues."""
    error_msg = str(error).lower()
    return any(
        msg in error_msg
        for msg in [
            "database is locked",
            "database is busy",
            "resource temporarily unavailable",
            "could not obtain lock",
            "unique constraint failed",
            "cannot commit transaction",
        ]
    )


def with_db_retry(max_attempts: int = 3, base_delay: float = 0.5) -> Callable[[F], F]:
    """Decorator for database operations with retry logic for concurrency errors."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if _is_concurrency_error(e) and attempt < max_attempts - 1:
                        # Wait with exponential backoff
                        wait_time = base_delay * (2**attempt)
                        logger.debug(
                            "database_retry",
                            function=func.__name__,
                            attempt=attempt + 1,
                            wait_time=wait_time,
                            error=str(e),
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        # Re-raise if not a concurrency error or max attempts reached
                        raise
            return None  # This shouldn't be reached

        return wrapper  # type: ignore[return-value]

    return decorator


def get_engine() -> AsyncEngine:
    """Get or create the async engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        db_url = str(settings.database_url)

        # SQLite configuration for better concurrency
        connect_args = {
            "check_same_thread": False,
            "timeout": 30,  # 30 second timeout for busy database
        }
        engine_kwargs = {
            "connect_args": connect_args,
            "poolclass": StaticPool,
            "echo": settings.enable_sql_logging,
        }

        _engine = create_async_engine(db_url, **engine_kwargs)

        # Enable SQLite optimizations on new connections
        @event.listens_for(_engine.sync_engine, "connect")
        def enable_sqlite_optimizations(
            dbapi_connection: Any, connection_record: Any
        ) -> None:
            """Enable WAL mode and other SQLite optimizations."""
            cursor = dbapi_connection.cursor()

            # Enable WAL mode for better concurrent performance
            cursor.execute("PRAGMA journal_mode=WAL")

            # Performance optimizations
            cursor.execute("PRAGMA synchronous=NORMAL")  # Faster than FULL, still safe
            cursor.execute("PRAGMA cache_size=10000")  # 10MB cache (negative = KB)
            cursor.execute("PRAGMA temp_store=MEMORY")  # Store temp tables in memory
            cursor.execute("PRAGMA mmap_size=268435456")  # 256MB memory-mapped I/O

            cursor.close()

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
    """Database health check with SQLite optimization status."""
    try:
        async with get_session() as session:
            # Test basic connectivity
            result = await session.execute(text("SELECT 1"))
            result.fetchone()

            # Check if WAL mode is enabled
            wal_result = await session.execute(text("PRAGMA journal_mode"))
            journal_mode = wal_result.scalar()

            return {
                "status": "healthy",
                "journal_mode": journal_mode or "unknown",
                "wal_enabled": str(journal_mode == "wal").lower(),
            }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "error_type": type(e).__name__}
