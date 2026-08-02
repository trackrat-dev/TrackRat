"""
Locking utilities for TrackRat V2.

Provides application-level locking to prevent concurrent processing of the same train.
"""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

logger = get_logger(__name__)


class LockManager:
    """Manages per-train locks to prevent concurrent processing."""

    def __init__(self) -> None:
        """Initialize the lock manager."""
        self._locks: dict[str, asyncio.Lock] = {}
        self._lock_creation_lock = asyncio.Lock()

    async def get_lock(self, train_id: str, journey_date: str) -> asyncio.Lock:
        """Get or create a lock for a specific train journey.

        Args:
            train_id: The train ID (e.g., "A181")
            journey_date: The journey date (e.g., "2025-07-08")

        Returns:
            An asyncio.Lock for the specific train journey
        """
        lock_key = f"{train_id}_{journey_date}"

        # Double-checked locking pattern for thread safety
        if lock_key not in self._locks:
            async with self._lock_creation_lock:
                if lock_key not in self._locks:
                    new_lock = asyncio.Lock()
                    self._locks[lock_key] = new_lock
                    logger.debug("created_train_lock", lock_key=lock_key)

        return self._locks[lock_key]

    async def cleanup_old_locks(self, keep_date: date | None = None) -> int:
        """Clean up locks for dates older than the specified date.

        Since lock keys are formatted as '{train_id}_{journey_date}', we can
        identify and remove locks for old journey dates that are no longer needed.

        Args:
            keep_date: Keep locks for this date and newer. Defaults to today.

        Returns:
            Number of locks removed
        """
        if keep_date is None:
            keep_date = date.today()

        async with self._lock_creation_lock:
            to_remove = []
            for lock_key, lock in self._locks.items():
                # Extract date from key (format: trainid_YYYY-MM-DD)
                try:
                    date_str = lock_key.rsplit("_", 1)[-1]
                    lock_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    if lock_date < keep_date:
                        # Only remove if lock is not currently held
                        if not lock.locked():
                            to_remove.append(lock_key)
                except (ValueError, IndexError):
                    # Invalid date format - skip this key
                    continue

            for lock_key in to_remove:
                del self._locks[lock_key]
                logger.debug("cleaned_up_old_lock", lock_key=lock_key)

            if to_remove:
                logger.info(
                    "lock_cleanup_completed",
                    removed_count=len(to_remove),
                    remaining_count=len(self._locks),
                )

            return len(to_remove)

    def get_status(self) -> dict[str, Any]:
        """Get current lock manager status."""
        return {"active_locks": len(self._locks), "lock_keys": list(self._locks.keys())}


# Global lock manager instance
_lock_manager: LockManager | None = None


def get_lock_manager() -> LockManager:
    """Get the global lock manager instance."""
    global _lock_manager
    if _lock_manager is None:
        _lock_manager = LockManager()
    return _lock_manager


async def with_train_lock(
    train_id: str,
    journey_date: str,
    coro_func: Callable[..., Coroutine[Any, Any, Any]],
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Execute a coroutine function with a train-specific lock.

    Args:
        train_id: The train ID
        journey_date: The journey date
        coro_func: The coroutine function to execute
        *args: Arguments to pass to the coroutine function
        **kwargs: Keyword arguments to pass to the coroutine function

    Returns:
        The result of the coroutine function
    """
    lock_manager = get_lock_manager()
    lock = await lock_manager.get_lock(train_id, journey_date)

    async with lock:
        logger.debug(
            "acquired_train_lock", train_id=train_id, journey_date=journey_date
        )
        try:
            return await coro_func(*args, **kwargs)
        finally:
            logger.debug(
                "released_train_lock", train_id=train_id, journey_date=journey_date
            )


# How long a writer waits for another writer's journey lock before giving up.
# Well under the engine's 55s statement_timeout, so contention surfaces as a
# retryable JourneyLockTimeout rather than a query cancellation.
JOURNEY_LOCK_TIMEOUT_SECONDS = 5.0

# Gap between attempts. Short enough that an uncontended handoff (the common
# case) is not perceptibly slower than a blocking acquire.
_JOURNEY_LOCK_POLL_SECONDS = 0.05


class JourneyLockTimeout(Exception):
    """A journey's advisory lock was still held after the wait budget.

    Distinct from every other failure mode on these paths, so callers can
    retry contention specifically instead of pattern-matching Postgres error
    text. See `db/engine.retry_on_deadlock`.
    """


async def acquire_njt_journey_lock(
    session: AsyncSession,
    train_id: str | None,
    journey_date: date | None,
    timeout_seconds: float = JOURNEY_LOCK_TIMEOUT_SECONDS,
) -> None:
    """Take a transaction-scoped Postgres advisory lock for one NJT journey.

    Unlike `with_train_lock`, this is a database lock, so it serializes NJT's
    three writers of `journey_stops` (JIT refresh, scheduled collection, and
    the nightly schedule rebuild) across replicas, not just within one
    process. It is released automatically when the current transaction
    commits or rolls back.

    Bounded with `pg_try_advisory_xact_lock` in a polling loop rather than a
    blocking `pg_advisory_xact_lock`. Blocking meant a contended journey sat
    on the lock until the engine's 55s `statement_timeout` cancelled it, and
    the resulting QueryCanceledError is indistinguishable from a genuinely
    slow query -- so it could not be retried without also retrying every
    runaway statement in the app (issue #1672). Giving up after
    `timeout_seconds` with a dedicated `JourneyLockTimeout` costs one train
    instead of a whole station board, and `retry_on_deadlock` can act on it.

    The trade-off is that pollers are not queued fairly the way blocked
    waiters are, so a permanently contended key could starve one. Acceptable
    because the writer that used to hold this lock for minutes at a time --
    the nightly schedule rebuild -- now commits per train.

    Raises:
        JourneyLockTimeout: the lock was still held after `timeout_seconds`.

    No-op on non-PostgreSQL dialects (e.g. the SQLite engine some unit tests
    use): advisory locks are PostgreSQL-specific, and those tests run
    single-threaded with no cross-replica writer to guard against.
    """
    if not train_id or not journey_date:
        raise ValueError(
            "train_id and journey_date are required to acquire journey lock"
        )

    # getattr, not session.bind directly: AsyncSession.bind is proxied via
    # __getattr__ to the underlying sync session rather than being a real
    # class attribute, so Mock(spec=AsyncSession) in tests raises
    # AttributeError on access instead of returning None.
    bind = getattr(session, "bind", None)
    dialect_name = bind.dialect.name if bind else "postgresql"
    if dialect_name != "postgresql":
        return

    key = f"NJT_{train_id}_{journey_date.isoformat()}"
    deadline = asyncio.get_running_loop().time() + timeout_seconds

    while True:
        acquired = await session.scalar(
            text("SELECT pg_try_advisory_xact_lock(hashtext(:key))"), {"key": key}
        )
        if acquired:
            return

        if asyncio.get_running_loop().time() >= deadline:
            logger.warning(
                "journey_lock_timeout",
                train_id=train_id,
                journey_date=journey_date,
                timeout_seconds=timeout_seconds,
            )
            raise JourneyLockTimeout(
                f"could not acquire journey lock for {key} "
                f"within {timeout_seconds}s"
            )

        await asyncio.sleep(_JOURNEY_LOCK_POLL_SECONDS)
