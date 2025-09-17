"""
Comprehensive unit tests for scheduler_utils.py.

Tests the distributed task execution system that prevents duplicate
task runs across multiple Cloud Run replicas.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.utils.scheduler_utils import (
    calculate_safe_interval,
    run_with_freshness_check,
    _task_exists,
)
from trackrat.models.database import SchedulerTaskRun


class TestRunWithFreshnessCheckSimplified:
    """Test cases for run_with_freshness_check function with simplified mocking."""

    @pytest.fixture
    def mock_db(self):
        """Mock AsyncSession database."""
        mock = AsyncMock(spec=AsyncSession)
        # The execute() method returns an awaitable Result object
        # which has scalar_one_or_none() method
        mock.execute = AsyncMock()
        mock.commit = AsyncMock()
        mock.rollback = AsyncMock()
        mock.add = Mock()
        return mock

    @pytest.fixture
    def mock_task_func(self):
        """Mock async task function."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_calculate_safe_interval_success(self):
        """Test successful calculation of safe intervals."""
        # Test normal case
        result = calculate_safe_interval(30)
        expected = int((30 - 3) * 60)  # 30 - 3 minutes buffer = 1620 seconds
        assert result == expected

        # Test short interval
        result = calculate_safe_interval(5)
        expected = int((5 - 2) * 60)  # 5 - 2 minutes buffer = 180 seconds
        assert result == expected

    @pytest.mark.asyncio
    async def test_task_still_fresh_skips_execution(self, mock_db, mock_task_func):
        """Test that task is skipped when it ran recently."""
        # Create a mock task that ran 10 minutes ago
        from datetime import timezone

        recent_time = datetime(2025, 1, 1, 11, 50, 0, tzinfo=timezone.utc)
        mock_task_run = Mock(spec=SchedulerTaskRun)
        mock_task_run.task_name = "test_task"
        mock_task_run.last_successful_run = recent_time
        mock_task_run.run_count = 5

        # Fix: The execute() method is async and returns a Result object
        mock_result = Mock()  # Not AsyncMock, as scalar_one_or_none() is sync
        mock_result.scalar_one_or_none.return_value = mock_task_run
        mock_db.execute.return_value = mock_result

        with patch("trackrat.utils.scheduler_utils.datetime") as mock_datetime:
            from datetime import timezone

            current_time = datetime(
                2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc
            )  # 10 minutes later
            mock_datetime.now.return_value = current_time
            mock_datetime.min.replace.return_value = datetime.min.replace(
                tzinfo=timezone.utc
            )

            result = await run_with_freshness_check(
                db=mock_db,
                task_name="test_task",
                minimum_interval_seconds=1800,  # 30 minutes (more than 10 min elapsed)
                task_func=mock_task_func,
            )

        # Verify task was NOT executed
        assert result is False
        mock_task_func.assert_not_called()

        # Verify database was rolled back
        mock_db.rollback.assert_called_once()
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_task_stale_runs_successfully(self, mock_db, mock_task_func):
        """Test that task runs when enough time has passed."""
        # Create a mock task that ran 2 hours ago
        from datetime import timezone

        old_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        mock_task_run = Mock(spec=SchedulerTaskRun)
        mock_task_run.task_name = "test_task"
        mock_task_run.last_successful_run = old_time
        mock_task_run.run_count = 3
        mock_task_run.average_duration_ms = 5000

        # Fix: The execute() method is async and returns a Result object
        mock_result = Mock()  # Not AsyncMock, as scalar_one_or_none() is sync
        mock_result.scalar_one_or_none.return_value = mock_task_run
        mock_db.execute.return_value = mock_result

        with patch("trackrat.utils.scheduler_utils.datetime") as mock_datetime:
            from datetime import timezone

            current_time = datetime(
                2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc
            )  # 2 hours later, with timezone
            mock_datetime.now.return_value = current_time
            mock_datetime.min.replace.return_value = datetime.min.replace(
                tzinfo=timezone.utc
            )

            with patch("trackrat.utils.scheduler_utils.time") as mock_time:
                mock_time.time.side_effect = [1000.0, 1002.5]  # Task takes 2.5 seconds

                result = await run_with_freshness_check(
                    db=mock_db,
                    task_name="test_task",
                    minimum_interval_seconds=1800,  # 30 minutes
                    task_func=mock_task_func,
                )

        # Verify task was executed
        assert result is True
        mock_task_func.assert_called_once()

        # Verify metrics were updated
        assert mock_task_run.last_successful_run == current_time
        assert mock_task_run.run_count == 4  # Incremented from 3
        assert mock_task_run.last_duration_ms == 2500  # 2.5 seconds in ms

        # Verify rolling average calculation (90% old + 10% new)
        expected_avg = int(5000 * 0.9 + 2500 * 0.1)
        assert mock_task_run.average_duration_ms == expected_avg

        # Verify transaction committed
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_locked_by_another_replica_skips(self, mock_db, mock_task_func):
        """Test that task is skipped when another replica has the lock."""
        # Mock that SELECT FOR UPDATE returns None (locked by another instance)
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("trackrat.utils.scheduler_utils._task_exists") as mock_exists:
            mock_exists.return_value = True  # Task exists but is locked

            result = await run_with_freshness_check(
                db=mock_db,
                task_name="test_task",
                minimum_interval_seconds=1800,
                task_func=mock_task_func,
            )

        # Verify task was NOT executed
        assert result is False
        mock_task_func.assert_not_called()

        # Verify database was rolled back
        mock_db.rollback.assert_called_once()
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_task_execution_failure_rolls_back(self, mock_db, mock_task_func):
        """Test that database is rolled back when task execution fails."""
        # Set up task that needs to run
        from datetime import timezone

        old_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        mock_task_run = Mock(spec=SchedulerTaskRun)
        mock_task_run.task_name = "test_task"
        mock_task_run.last_successful_run = old_time
        mock_task_run.run_count = 1
        mock_task_run.average_duration_ms = 4000  # Real number needed for arithmetic

        # Fix: The execute() method is async and returns a Result object
        mock_result = Mock()  # Not AsyncMock, as scalar_one_or_none() is sync
        mock_result.scalar_one_or_none.return_value = mock_task_run
        mock_db.execute.return_value = mock_result

        # Make task function fail
        mock_task_func.side_effect = RuntimeError("Task failed!")

        with patch("trackrat.utils.scheduler_utils.datetime") as mock_datetime:
            from datetime import timezone

            current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = current_time
            mock_datetime.min.replace.return_value = datetime.min.replace(
                tzinfo=timezone.utc
            )

            # Task function fails, but function should return False (current behavior)
            result = await run_with_freshness_check(
                db=mock_db,
                task_name="test_task",
                minimum_interval_seconds=1800,
                task_func=mock_task_func,
            )

            # Current implementation returns False on task failures
            assert result is False

        # Verify task was attempted
        mock_task_func.assert_called_once()

        # Verify database was rolled back due to failure
        # Note: Current implementation calls rollback twice:
        # 1. Inner handler (task execution failure)
        # 2. Outer handler (re-raised as freshness check error)
        assert mock_db.rollback.call_count == 2
        mock_db.commit.assert_not_called()

        # Verify success metrics were NOT updated
        assert mock_task_run.last_successful_run == old_time  # Unchanged
        assert mock_task_run.run_count == 1  # Unchanged

    @pytest.mark.asyncio
    async def test_database_error_fails_safely(self, mock_db, mock_task_func):
        """Test that database errors are handled gracefully."""
        # Make database operations fail
        mock_db.execute.side_effect = Exception("Database connection lost!")

        result = await run_with_freshness_check(
            db=mock_db,
            task_name="test_task",
            minimum_interval_seconds=1800,
            task_func=mock_task_func,
        )

        # Should fail safely and not execute task
        assert result is False
        mock_task_func.assert_not_called()

        # Verify rollback was called
        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_timezone_handling_naive_datetime(self, mock_db, mock_task_func):
        """Test proper handling of naive datetimes from database."""
        # Create a naive datetime (as might come from SQLite)
        naive_time = datetime(2025, 1, 1, 10, 0, 0)  # No timezone
        mock_task_run = Mock(spec=SchedulerTaskRun)
        mock_task_run.task_name = "test_task"
        mock_task_run.last_successful_run = naive_time
        mock_task_run.run_count = 1
        mock_task_run.average_duration_ms = 3000  # Real number needed for arithmetic

        # Fix: The execute() method is async and returns a Result object
        mock_result = Mock()  # Not AsyncMock, as scalar_one_or_none() is sync
        mock_result.scalar_one_or_none.return_value = mock_task_run
        mock_db.execute.return_value = mock_result

        with patch("trackrat.utils.scheduler_utils.datetime") as mock_datetime:
            # Current time with timezone
            from datetime import timezone

            current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = current_time
            mock_datetime.min.replace.return_value = datetime.min.replace(
                tzinfo=timezone.utc
            )

            result = await run_with_freshness_check(
                db=mock_db,
                task_name="test_task",
                minimum_interval_seconds=1800,  # 30 minutes
                task_func=mock_task_func,
            )

        # Should handle timezone conversion and run successfully
        assert result is True
        mock_task_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_instance_id_tracking(self, mock_db, mock_task_func):
        """Test that Cloud Run instance ID is properly tracked."""
        mock_task_run = Mock(spec=SchedulerTaskRun)
        mock_task_run.task_name = "test_task"
        from datetime import timezone

        mock_task_run.last_successful_run = datetime.min.replace(tzinfo=timezone.utc)
        mock_task_run.run_count = 0
        mock_task_run.average_duration_ms = 2000  # Real number needed for arithmetic

        # Fix: The execute() method is async and returns a Result object
        mock_result = Mock()  # Not AsyncMock, as scalar_one_or_none() is sync
        mock_result.scalar_one_or_none.return_value = mock_task_run
        mock_db.execute.return_value = mock_result

        with patch("trackrat.utils.scheduler_utils.os.getenv") as mock_getenv:
            mock_getenv.return_value = "test-revision-123"

            with patch("trackrat.utils.scheduler_utils.datetime") as mock_datetime:
                from datetime import timezone

                current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
                mock_datetime.now.return_value = current_time
                mock_datetime.min.replace.return_value = datetime.min.replace(
                    tzinfo=timezone.utc
                )

                result = await run_with_freshness_check(
                    db=mock_db,
                    task_name="test_task",
                    minimum_interval_seconds=1800,
                    task_func=mock_task_func,
                )

        # Verify instance ID was set
        assert result is True
        assert mock_task_run.last_instance_id == "test-revision-123"


class TestTaskExists:
    """Test cases for _task_exists helper function."""

    @pytest.mark.asyncio
    async def test_task_exists_returns_true(self):
        """Test that _task_exists returns True when task record exists."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = Mock()  # Not AsyncMock since scalar_one_or_none() is sync
        mock_result.scalar_one_or_none.return_value = "test_task"
        mock_db.execute.return_value = mock_result

        result = await _task_exists(mock_db, "test_task")

        assert result is True

    @pytest.mark.asyncio
    async def test_task_exists_returns_false(self):
        """Test that _task_exists returns False when task record doesn't exist."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = Mock()  # Not AsyncMock since scalar_one_or_none() is sync
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await _task_exists(mock_db, "nonexistent_task")

        assert result is False


class TestCalculateSafeInterval:
    """Test cases for calculate_safe_interval function."""

    def test_calculate_safe_interval_normal_case(self):
        """Test safe interval calculation for normal scheduling intervals."""
        # 30 minute interval should have ~2 minute buffer
        result = calculate_safe_interval(30)
        expected = int((30 - max(2, 30 * 0.1)) * 60)  # (30 - 3) * 60 = 1620 seconds
        assert result == expected

    def test_calculate_safe_interval_short_interval(self):
        """Test safe interval calculation for short intervals."""
        # 5 minute interval should have 2 minute minimum buffer
        result = calculate_safe_interval(5)
        expected = int((5 - 2) * 60)  # 3 minutes = 180 seconds
        assert result == expected

    def test_calculate_safe_interval_very_short_interval(self):
        """Test safe interval calculation for very short intervals."""
        # 1 minute interval should still have minimum 1 minute safety
        result = calculate_safe_interval(1)
        expected = int(1 * 60)  # 1 minute = 60 seconds
        assert result == expected

    def test_calculate_safe_interval_long_interval(self):
        """Test safe interval calculation for long intervals."""
        # 120 minute interval should have 12 minute buffer (10%)
        result = calculate_safe_interval(120)
        expected = int((120 - 12) * 60)  # 108 minutes = 6480 seconds
        assert result == expected
