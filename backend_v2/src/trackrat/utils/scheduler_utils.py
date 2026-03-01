"""
Utilities for distributed scheduler task management.

Ensures scheduled tasks only run once across multiple Cloud Run replicas.
"""

import os
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from structlog import get_logger

from trackrat.models.database import SchedulerTaskRun

logger = get_logger(__name__)


def commit_with_retry(
    session: Session,
    max_retries: int = 3,
    log_context: dict[str, Any] | None = None,
) -> None:
    """
    Commit a synchronous database session with retry logic for SQLite locks.

    SQLite can raise "database is locked" errors when multiple processes
    access the database simultaneously. This function retries with exponential
    backoff to handle transient lock contention.

    Args:
        session: Synchronous SQLAlchemy session to commit
        max_retries: Maximum number of retry attempts (default: 3)
        log_context: Optional dict with context for log messages (e.g., train_id)

    Raises:
        Exception: Re-raises the last exception if all retries fail
    """
    context = log_context or {}

    for retry in range(max_retries):
        try:
            session.commit()
            return
        except Exception as e:
            is_lock_error = "database is locked" in str(e) or "database is busy" in str(
                e
            )
            if is_lock_error and retry < max_retries - 1:
                logger.warning(
                    "database_locked_retrying",
                    retry=retry + 1,
                    error=str(e),
                    **context,
                )
                time.sleep(0.5 * (retry + 1))
            else:
                raise


async def run_with_freshness_check(
    db: AsyncSession,
    task_name: str,
    minimum_interval_seconds: int,
    task_func: Callable[[], Awaitable[Any]],
) -> bool:
    """
    Execute a scheduled task only if it hasn't run recently.

    This function ensures that a scheduled task only executes once across
    multiple replicas by holding a database lock throughout task execution.

    Args:
        db: Database session
        task_name: Unique identifier for the task (e.g., "njt_discovery")
        minimum_interval_seconds: Don't run if task ran within this many seconds
        task_func: The async function to execute if freshness check passes

    Returns:
        True if the task was executed, False if it was skipped due to freshness
    """
    now = datetime.now(UTC)
    instance_id = os.getenv("K_REVISION", "local")  # Cloud Run revision ID

    try:
        # Ensure the task record exists atomically (idempotent upsert).
        # This prevents UniqueViolationError when multiple replicas
        # first-run the same task concurrently — INSERT ... ON CONFLICT
        # DO NOTHING is atomic, unlike SELECT-then-INSERT.
        insert_stmt = (
            pg_insert(SchedulerTaskRun)
            .values(
                task_name=task_name,
                last_successful_run=datetime.min.replace(tzinfo=UTC),
                run_count=0,
            )
            .on_conflict_do_nothing(index_elements=["task_name"])
        )
        await db.execute(insert_stmt)
        await db.flush()

        # Now lock the existing row (guaranteed to exist after upsert)
        stmt = (
            select(SchedulerTaskRun)
            .where(SchedulerTaskRun.task_name == task_name)
            .with_for_update(skip_locked=True)
        )

        result = await db.execute(stmt)
        task_run = result.scalar_one_or_none()

        # If another replica has the lock, skip this execution
        if task_run is None:
            logger.info(
                "task_locked_by_another_replica",
                task=task_name,
                instance=instance_id,
            )
            await db.rollback()
            return False

        # Check if enough time has passed since last successful run
        last_run_time = task_run.last_successful_run
        assert last_run_time is not None  # Database constraint ensures this

        # Ensure timezone compatibility - add UTC if naive
        if last_run_time.tzinfo is None:
            last_run_time = last_run_time.replace(tzinfo=UTC)

        if last_run_time == datetime.min.replace(tzinfo=UTC):
            seconds_since_last_run = float("inf")  # Force first run
        else:
            seconds_since_last_run = (now - last_run_time).total_seconds()

        if seconds_since_last_run < minimum_interval_seconds:
            # Task is still fresh, skip execution
            logger.debug(
                "task_skipped_still_fresh",
                task=task_name,
                last_run=(
                    "never"
                    if last_run_time == datetime.min.replace(tzinfo=UTC)
                    else last_run_time.isoformat()
                ),
                seconds_since=(
                    int(seconds_since_last_run)
                    if seconds_since_last_run != float("inf")
                    else "infinity"
                ),
                minimum_interval=minimum_interval_seconds,
                instance=instance_id,
            )
            await db.rollback()
            return False

        # Task needs to run - update last_attempt to claim it
        # Keep the lock throughout execution to prevent race conditions
        logger.info(
            "task_starting",
            task=task_name,
            last_run=(
                "never"
                if last_run_time == datetime.min.replace(tzinfo=UTC)
                else last_run_time.isoformat()
            ),
            seconds_since=(
                int(seconds_since_last_run)
                if seconds_since_last_run != float("inf")
                else "infinity"
            ),
            instance=instance_id,
        )

        task_run.last_attempt = now
        task_run.last_instance_id = instance_id

        # Execute the task while holding the database lock
        # This prevents other replicas from running the same task simultaneously
        start_time = time.time()
        try:
            await task_func()
            duration_ms = int((time.time() - start_time) * 1000)

            # Update success metrics in the same transaction
            task_run.last_successful_run = now
            current_count = task_run.run_count or 0  # Handle None case gracefully
            task_run.run_count = current_count + 1
            task_run.last_duration_ms = duration_ms

            # Update rolling average (90% old, 10% new)
            if task_run.average_duration_ms:
                task_run.average_duration_ms = int(
                    task_run.average_duration_ms * 0.9 + duration_ms * 0.1
                )
            else:
                task_run.average_duration_ms = duration_ms

            # Commit the entire transaction (releases the lock)
            await db.commit()

            logger.info(
                "task_completed_successfully",
                task=task_name,
                duration_ms=duration_ms,
                instance=instance_id,
            )
            return True

        except Exception as e:
            await db.rollback()
            logger.error(
                "task_execution_failed",
                task=task_name,
                error=str(e),
                instance=instance_id,
                exc_info=True,
            )
            # Re-raise so the scheduler knows the task failed
            raise

    except Exception as e:
        # Catch any database-level errors
        await db.rollback()
        logger.error(
            "task_freshness_check_error",
            task=task_name,
            error=str(e),
            instance=instance_id,
        )
        # If we can't check freshness, don't run the task (fail safe)
        return False


def calculate_safe_interval(scheduled_minutes: int) -> int:
    """
    Calculate a safe minimum interval based on the scheduled frequency.

    We use scheduled_minutes - 2 minutes as a buffer to ensure:
    1. Tasks don't miss their schedule due to minor delays
    2. There's tolerance for clock drift or scheduler jitter
    3. We never run more frequently than originally scheduled

    Args:
        scheduled_minutes: How often the task is scheduled to run

    Returns:
        Safe minimum interval in seconds
    """
    # Use 90% of scheduled interval, with a minimum 2-minute buffer
    buffer_minutes = max(2, scheduled_minutes * 0.1)
    safe_minutes = scheduled_minutes - buffer_minutes

    # Never go below 1 minute for safety
    safe_minutes = max(1, safe_minutes)

    return int(safe_minutes * 60)
