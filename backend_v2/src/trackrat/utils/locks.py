"""
Locking utilities for TrackRat V2.

Provides application-level locking to prevent concurrent processing of the same train.
"""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any
from weakref import WeakSet

from structlog import get_logger

logger = get_logger(__name__)


class LockManager:
    """Manages per-train locks to prevent concurrent processing."""

    def __init__(self) -> None:
        """Initialize the lock manager."""
        self._locks: dict[str, asyncio.Lock] = {}
        self._lock_creation_lock = asyncio.Lock()
        self._active_locks: WeakSet[asyncio.Lock] = WeakSet()

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
                    self._active_locks.add(new_lock)
                    logger.debug("created_train_lock", lock_key=lock_key)

        return self._locks[lock_key]

    async def cleanup_unused_locks(self) -> None:
        """Clean up locks that are no longer in use."""
        async with self._lock_creation_lock:
            # Remove locks that are no longer referenced
            to_remove = []
            for lock_key, lock in self._locks.items():
                if lock not in self._active_locks:
                    to_remove.append(lock_key)

            for lock_key in to_remove:
                del self._locks[lock_key]
                logger.debug("cleaned_up_lock", lock_key=lock_key)

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
