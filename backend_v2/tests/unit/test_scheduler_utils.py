"""
Comprehensive unit tests for scheduler_utils.py.

Tests the distributed task execution system that prevents duplicate
task runs across multiple Cloud Run replicas.
"""

import asyncio

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.utils.scheduler_utils import (
    calculate_safe_interval,
    calculate_task_timeout,
    run_with_freshness_check,
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
        mock.flush = AsyncMock()
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

        # execute() is called twice: upsert (result unused), then SELECT FOR UPDATE
        upsert_result = Mock()
        select_result = Mock()
        select_result.scalar_one_or_none.return_value = mock_task_run
        mock_db.execute.side_effect = [upsert_result, select_result]

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

        # execute() is called twice: upsert (result unused), then SELECT FOR UPDATE
        upsert_result = Mock()
        select_result = Mock()
        select_result.scalar_one_or_none.return_value = mock_task_run
        mock_db.execute.side_effect = [upsert_result, select_result]

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
        # Upsert succeeds (row already exists, ON CONFLICT DO NOTHING),
        # but SELECT FOR UPDATE SKIP LOCKED returns None (locked by another replica)
        upsert_result = Mock()
        select_result = Mock()
        select_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [upsert_result, select_result]

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

        # execute() is called twice: upsert (result unused), then SELECT FOR UPDATE
        upsert_result = Mock()
        select_result = Mock()
        select_result.scalar_one_or_none.return_value = mock_task_run
        mock_db.execute.side_effect = [upsert_result, select_result]

        # Make task function fail
        mock_task_func.side_effect = RuntimeError("Task failed!")

        with patch("trackrat.utils.scheduler_utils.datetime") as mock_datetime:
            from datetime import timezone

            current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = current_time
            mock_datetime.min.replace.return_value = datetime.min.replace(
                tzinfo=timezone.utc
            )

            # Task function fails, function returns False
            result = await run_with_freshness_check(
                db=mock_db,
                task_name="test_task",
                minimum_interval_seconds=1800,
                task_func=mock_task_func,
            )

            assert result is False

        # Verify task was attempted
        mock_task_func.assert_called_once()

        # Verify database was rolled back exactly once (task execution failure)
        assert mock_db.rollback.call_count == 1
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

        # execute() is called twice: upsert (result unused), then SELECT FOR UPDATE
        upsert_result = Mock()
        select_result = Mock()
        select_result.scalar_one_or_none.return_value = mock_task_run
        mock_db.execute.side_effect = [upsert_result, select_result]

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

        # execute() is called twice: upsert (result unused), then SELECT FOR UPDATE
        upsert_result = Mock()
        select_result = Mock()
        select_result.scalar_one_or_none.return_value = mock_task_run
        mock_db.execute.side_effect = [upsert_result, select_result]

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


class TestCalculateTaskTimeout:
    """Test cases for calculate_task_timeout function."""

    def test_four_minute_collector(self):
        """4-minute collector (e.g., subway) should get 480s timeout."""
        result = calculate_task_timeout(4)
        assert result == 480  # 4 * 60 * 2

    def test_three_minute_collector(self):
        """3-minute collector (e.g., WMATA) should get 360s timeout."""
        result = calculate_task_timeout(3)
        assert result == 360  # 3 * 60 * 2

    def test_thirty_minute_discovery(self):
        """30-minute discovery task should get 3600s timeout."""
        result = calculate_task_timeout(30)
        assert result == 3600  # 30 * 60 * 2

    def test_fifteen_minute_task(self):
        """15-minute task (e.g., service alerts) should get 1800s timeout."""
        result = calculate_task_timeout(15)
        assert result == 1800  # 15 * 60 * 2


class TestRunWithFreshnessCheckTimeout:
    """Test timeout behavior in run_with_freshness_check."""

    @pytest.fixture
    def mock_db(self):
        """Mock AsyncSession database."""
        mock = AsyncMock(spec=AsyncSession)
        mock.execute = AsyncMock()
        mock.flush = AsyncMock()
        mock.commit = AsyncMock()
        mock.rollback = AsyncMock()
        mock.add = Mock()
        return mock

    def _setup_stale_task(self, mock_db):
        """Set up a mock task that needs to run (last ran long ago)."""
        from datetime import timezone

        old_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        mock_task_run = Mock(spec=SchedulerTaskRun)
        mock_task_run.task_name = "test_task"
        mock_task_run.last_successful_run = old_time
        mock_task_run.run_count = 1
        mock_task_run.average_duration_ms = 5000

        upsert_result = Mock()
        select_result = Mock()
        select_result.scalar_one_or_none.return_value = mock_task_run
        mock_db.execute.side_effect = [upsert_result, select_result]
        return mock_task_run

    @pytest.mark.asyncio
    async def test_timeout_cancels_slow_task(self, mock_db):
        """Verify that a task exceeding timeout_seconds is cancelled.

        Simulates a collector that takes 5 seconds when only 1 second
        is allowed. The task should be cancelled and the DB rolled back.
        """
        import asyncio

        self._setup_stale_task(mock_db)

        async def slow_task():
            await asyncio.sleep(10)  # Would take 10 seconds

        with patch("trackrat.utils.scheduler_utils.datetime") as mock_datetime:
            from datetime import timezone

            current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = current_time
            mock_datetime.min.replace.return_value = datetime.min.replace(
                tzinfo=timezone.utc
            )

            # TimeoutError is caught and converted to return False.
            result = await run_with_freshness_check(
                db=mock_db,
                task_name="test_task",
                minimum_interval_seconds=60,
                task_func=slow_task,
                timeout_seconds=1,  # 1 second timeout
            )

        # Task should not succeed
        assert result is False
        # DB should be rolled back exactly once (timeout handler)
        assert mock_db.rollback.call_count == 1
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_timeout_allows_completion(self, mock_db):
        """Verify that timeout_seconds=None allows tasks to complete normally."""
        mock_task_run = self._setup_stale_task(mock_db)
        task_func = AsyncMock()

        with patch("trackrat.utils.scheduler_utils.datetime") as mock_datetime:
            from datetime import timezone

            current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = current_time
            mock_datetime.min.replace.return_value = datetime.min.replace(
                tzinfo=timezone.utc
            )

            with patch("trackrat.utils.scheduler_utils.time") as mock_time:
                mock_time.time.side_effect = [1000.0, 1003.0]

                result = await run_with_freshness_check(
                    db=mock_db,
                    task_name="test_task",
                    minimum_interval_seconds=60,
                    task_func=task_func,
                    timeout_seconds=None,  # No timeout
                )

        assert result is True
        task_func.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_fast_task_completes_within_timeout(self, mock_db):
        """Verify that a fast task completes normally even with a timeout set."""
        mock_task_run = self._setup_stale_task(mock_db)
        task_func = AsyncMock()

        with patch("trackrat.utils.scheduler_utils.datetime") as mock_datetime:
            from datetime import timezone

            current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = current_time
            mock_datetime.min.replace.return_value = datetime.min.replace(
                tzinfo=timezone.utc
            )

            with patch("trackrat.utils.scheduler_utils.time") as mock_time:
                mock_time.time.side_effect = [1000.0, 1001.0]

                result = await run_with_freshness_check(
                    db=mock_db,
                    task_name="test_task",
                    minimum_interval_seconds=60,
                    task_func=task_func,
                    timeout_seconds=480,  # Generous timeout
                )

        assert result is True
        task_func.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout_does_not_double_log_as_freshness_error(self, mock_db):
        """A timed-out task must log task_execution_timed_out exactly once
        and must NOT also log task_freshness_check_error.

        Regression guard for issue #1040: previously the inner TimeoutError
        handler logged + raised, and the outer Exception handler caught the
        re-raised TimeoutError and logged a misleading second event.
        """
        import asyncio

        self._setup_stale_task(mock_db)

        async def slow_task():
            await asyncio.sleep(10)

        with patch("trackrat.utils.scheduler_utils.datetime") as mock_datetime:
            from datetime import timezone

            current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = current_time
            mock_datetime.min.replace.return_value = datetime.min.replace(
                tzinfo=timezone.utc
            )

            with patch("trackrat.utils.scheduler_utils.logger") as mock_logger:
                await run_with_freshness_check(
                    db=mock_db,
                    task_name="test_task",
                    minimum_interval_seconds=60,
                    task_func=slow_task,
                    timeout_seconds=1,
                )

                logged_events = [
                    call.args[0] for call in mock_logger.error.call_args_list
                ]
                assert logged_events.count("task_execution_timed_out") == 1
                assert "task_freshness_check_error" not in logged_events

    @pytest.mark.asyncio
    async def test_task_failure_does_not_double_log_as_freshness_error(self, mock_db):
        """A failing task must log task_execution_failed exactly once and
        must NOT also log task_freshness_check_error.

        Regression guard for issue #1040.
        """
        self._setup_stale_task(mock_db)

        async def failing_task():
            raise RuntimeError("boom")

        with patch("trackrat.utils.scheduler_utils.datetime") as mock_datetime:
            from datetime import timezone

            current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = current_time
            mock_datetime.min.replace.return_value = datetime.min.replace(
                tzinfo=timezone.utc
            )

            with patch("trackrat.utils.scheduler_utils.logger") as mock_logger:
                result = await run_with_freshness_check(
                    db=mock_db,
                    task_name="test_task",
                    minimum_interval_seconds=60,
                    task_func=failing_task,
                )

                assert result is False
                logged_events = [
                    call.args[0] for call in mock_logger.error.call_args_list
                ]
                assert logged_events.count("task_execution_failed") == 1
                assert "task_freshness_check_error" not in logged_events

    @pytest.mark.asyncio
    async def test_timeout_logs_duration(self, mock_db):
        """Verify that a timed-out task logs its actual duration."""
        import asyncio

        self._setup_stale_task(mock_db)

        async def slow_task():
            await asyncio.sleep(10)

        with patch("trackrat.utils.scheduler_utils.datetime") as mock_datetime:
            from datetime import timezone

            current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = current_time
            mock_datetime.min.replace.return_value = datetime.min.replace(
                tzinfo=timezone.utc
            )

            with patch("trackrat.utils.scheduler_utils.logger") as mock_logger:
                await run_with_freshness_check(
                    db=mock_db,
                    task_name="slow_collector",
                    minimum_interval_seconds=60,
                    task_func=slow_task,
                    timeout_seconds=1,
                )

                # Verify the timeout was logged with task name
                timeout_calls = [
                    call
                    for call in mock_logger.error.call_args_list
                    if call.args[0] == "task_execution_timed_out"
                ]
                assert len(timeout_calls) == 1
                assert timeout_calls[0].kwargs["task"] == "slow_collector"
                assert timeout_calls[0].kwargs["timeout_seconds"] == 1


class TestRunWithFreshnessCheckCancelledError:
    """Test that CancelledError (BaseException) is handled correctly.

    CancelledError inherits from BaseException, not Exception, so it
    bypasses except Exception handlers. Before the fix, this would leave
    the AsyncSession with an open transaction holding a FOR UPDATE lock.
    """

    @pytest.fixture
    def mock_db(self):
        """Mock AsyncSession database."""
        mock = AsyncMock(spec=AsyncSession)
        mock.execute = AsyncMock()
        mock.flush = AsyncMock()
        mock.commit = AsyncMock()
        mock.rollback = AsyncMock()
        mock.add = Mock()
        return mock

    def _setup_stale_task(self, mock_db):
        """Set up a mock task that needs to run (last ran long ago)."""
        from datetime import timezone

        old_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        mock_task_run = Mock(spec=SchedulerTaskRun)
        mock_task_run.task_name = "test_task"
        mock_task_run.last_successful_run = old_time
        mock_task_run.run_count = 1
        mock_task_run.average_duration_ms = 5000

        upsert_result = Mock()
        select_result = Mock()
        select_result.scalar_one_or_none.return_value = mock_task_run
        mock_db.execute.side_effect = [upsert_result, select_result]
        return mock_task_run

    @pytest.mark.asyncio
    async def test_cancelled_error_during_task_rolls_back(self, mock_db):
        """CancelledError during task execution must rollback the transaction.

        This is the core bug from issue #984: CancelledError bypasses
        except Exception, leaving the FOR UPDATE lock held indefinitely.
        """
        self._setup_stale_task(mock_db)

        async def cancelled_task():
            raise asyncio.CancelledError()

        with patch("trackrat.utils.scheduler_utils.datetime") as mock_datetime:
            from datetime import timezone

            current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = current_time
            mock_datetime.min.replace.return_value = datetime.min.replace(
                tzinfo=timezone.utc
            )

            with pytest.raises(asyncio.CancelledError):
                await run_with_freshness_check(
                    db=mock_db,
                    task_name="test_task",
                    minimum_interval_seconds=60,
                    task_func=cancelled_task,
                )

        # The critical assertion: rollback MUST have been called
        mock_db.rollback.assert_called()
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates(self, mock_db):
        """CancelledError must propagate after rollback, not be swallowed."""
        self._setup_stale_task(mock_db)

        async def cancelled_task():
            raise asyncio.CancelledError()

        with patch("trackrat.utils.scheduler_utils.datetime") as mock_datetime:
            from datetime import timezone

            current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = current_time
            mock_datetime.min.replace.return_value = datetime.min.replace(
                tzinfo=timezone.utc
            )

            with pytest.raises(asyncio.CancelledError):
                await run_with_freshness_check(
                    db=mock_db,
                    task_name="test_task",
                    minimum_interval_seconds=60,
                    task_func=cancelled_task,
                )

    @pytest.mark.asyncio
    async def test_cancelled_error_during_db_setup_rolls_back(self, mock_db):
        """CancelledError during the upsert/lock phase must also rollback."""
        mock_db.execute.side_effect = asyncio.CancelledError()
        task_func = AsyncMock()

        with pytest.raises(asyncio.CancelledError):
            await run_with_freshness_check(
                db=mock_db,
                task_name="test_task",
                minimum_interval_seconds=60,
                task_func=task_func,
            )

        mock_db.rollback.assert_called()
        task_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_rolls_back(self, mock_db):
        """KeyboardInterrupt (also BaseException) must rollback."""
        self._setup_stale_task(mock_db)

        async def interrupted_task():
            raise KeyboardInterrupt()

        with patch("trackrat.utils.scheduler_utils.datetime") as mock_datetime:
            from datetime import timezone

            current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = current_time
            mock_datetime.min.replace.return_value = datetime.min.replace(
                tzinfo=timezone.utc
            )

            with pytest.raises(KeyboardInterrupt):
                await run_with_freshness_check(
                    db=mock_db,
                    task_name="test_task",
                    minimum_interval_seconds=60,
                    task_func=interrupted_task,
                )

        mock_db.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_rollback_failure_during_cancellation_still_propagates(self, mock_db):
        """If rollback itself fails during CancelledError, the error still propagates."""
        self._setup_stale_task(mock_db)
        mock_db.rollback.side_effect = RuntimeError("connection lost")

        async def cancelled_task():
            raise asyncio.CancelledError()

        with patch("trackrat.utils.scheduler_utils.datetime") as mock_datetime:
            from datetime import timezone

            current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = current_time
            mock_datetime.min.replace.return_value = datetime.min.replace(
                tzinfo=timezone.utc
            )

            # CancelledError should propagate even if rollback fails
            with pytest.raises(asyncio.CancelledError):
                await run_with_freshness_check(
                    db=mock_db,
                    task_name="test_task",
                    minimum_interval_seconds=60,
                    task_func=cancelled_task,
                )

    @pytest.mark.asyncio
    async def test_normal_exception_still_returns_false(self, mock_db):
        """Verify existing behavior is preserved: Exception returns False."""
        self._setup_stale_task(mock_db)

        async def failing_task():
            raise ValueError("something broke")

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
                minimum_interval_seconds=60,
                task_func=failing_task,
            )

        # Exception subclasses are caught and return False (existing behavior)
        assert result is False
        mock_db.rollback.assert_called()
