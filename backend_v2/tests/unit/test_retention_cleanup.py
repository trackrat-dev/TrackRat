"""
Tests for the data retention cleanup system (issue #987).

Verifies that the retention cleanup job is registered in the scheduler,
that the batch delete logic works correctly for train_journeys,
discovery_runs, and validation_results, and that the retention_days
setting is properly configured.
"""

import pytest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch, call, MagicMock

from trackrat.settings import Settings


class TestRetentionSettings:
    """Test retention_days setting configuration."""

    def test_default_retention_days(self):
        """Default retention_days should be 120."""
        settings = Settings(database_url="postgresql+asyncpg://x:x@localhost/x")
        assert settings.retention_days == 120

    def test_custom_retention_days(self):
        """retention_days should be configurable via environment."""
        with patch.dict("os.environ", {"TRACKRAT_RETENTION_DAYS": "90"}):
            settings = Settings(database_url="postgresql+asyncpg://x:x@localhost/x")
            assert settings.retention_days == 90

    def test_retention_days_minimum_enforced(self):
        """retention_days below 30 should be rejected."""
        with pytest.raises(Exception):
            Settings(
                database_url="postgresql+asyncpg://x:x@localhost/x",
                retention_days=10,
            )

    def test_retention_days_at_minimum(self):
        """retention_days of exactly 30 should be accepted."""
        settings = Settings(
            database_url="postgresql+asyncpg://x:x@localhost/x",
            retention_days=30,
        )
        assert settings.retention_days == 30

    def test_retention_days_large_value(self):
        """Large retention_days (e.g., 365) should be accepted."""
        settings = Settings(
            database_url="postgresql+asyncpg://x:x@localhost/x",
            retention_days=365,
        )
        assert settings.retention_days == 365


class TestRetentionCleanupSchedulerRegistration:
    """Test that retention_cleanup is registered as a scheduler job."""

    def test_retention_cleanup_method_exists(self):
        """SchedulerService should have a retention_cleanup method."""
        from trackrat.services.scheduler import SchedulerService

        assert hasattr(SchedulerService, "retention_cleanup")
        assert callable(getattr(SchedulerService, "retention_cleanup"))

    def test_retention_cleanup_job_registered_in_schedule_jobs(self):
        """The _schedule_jobs method should register retention_cleanup."""
        from trackrat.services.scheduler import SchedulerService

        import inspect

        source = inspect.getsource(SchedulerService)
        assert 'id="retention_cleanup"' in source
        assert "self.retention_cleanup" in source

    def test_retention_cleanup_uses_cron_trigger(self):
        """retention_cleanup should use CronTrigger at 3:30 AM ET."""
        from trackrat.services.scheduler import SchedulerService

        import inspect

        source = inspect.getsource(SchedulerService)
        # Find the retention_cleanup job registration block
        idx = source.index('id="retention_cleanup"')
        block = source[max(0, idx - 300) : idx + 100]
        assert "CronTrigger" in block
        assert "hour=3" in block
        assert "minute=30" in block
        assert '"America/New_York"' in block


class TestRetentionCleanupBatchLogic:
    """Test the batch delete logic in retention_cleanup."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with retention_days=120."""
        settings = Mock()
        settings.retention_days = 120
        return settings

    @pytest.mark.asyncio
    async def test_single_batch_deletes_all(self, mock_settings):
        """When fewer rows than batch_size exist, a single batch suffices."""
        from trackrat.services.scheduler import SchedulerService

        service = SchedulerService.__new__(SchedulerService)

        execute_results = [
            Mock(rowcount=500),   # journey batch
            Mock(rowcount=100),   # discovery batch
            Mock(rowcount=50),    # validation batch
        ]

        freshness_session = AsyncMock()

        with (
            patch("trackrat.services.scheduler.get_settings", return_value=mock_settings),
            patch(
                "trackrat.services.scheduler.get_session"
            ) as mock_get_session,
            patch(
                "trackrat.services.scheduler.run_with_freshness_check"
            ) as mock_freshness,
        ):
            async def execute_task_func(db, task_name, minimum_interval_seconds, task_func):
                await task_func()
                return True

            mock_freshness.side_effect = execute_task_func

            # First call = freshness session, then 3 batch sessions
            ctxs = []
            ctx_fresh = AsyncMock()
            ctx_fresh.__aenter__ = AsyncMock(return_value=freshness_session)
            ctx_fresh.__aexit__ = AsyncMock(return_value=False)
            ctxs.append(ctx_fresh)

            for result in execute_results:
                s = AsyncMock()
                s.execute = AsyncMock(return_value=result)
                ctx = AsyncMock()
                ctx.__aenter__ = AsyncMock(return_value=s)
                ctx.__aexit__ = AsyncMock(return_value=False)
                ctxs.append(ctx)

            mock_get_session.side_effect = ctxs

            await service.retention_cleanup()

            # Verify freshness check was called with correct task name
            assert mock_freshness.called
            call_kwargs = mock_freshness.call_args.kwargs
            assert call_kwargs["task_name"] == "retention_cleanup"

    @pytest.mark.asyncio
    async def test_multiple_batches_for_large_table(self, mock_settings):
        """When more rows than batch_size exist, multiple batches run."""
        from trackrat.services.scheduler import SchedulerService

        service = SchedulerService.__new__(SchedulerService)

        # Simulate: first journey batch returns 10000 (full), second returns 5000 (partial)
        execute_results = [
            Mock(rowcount=10000),  # journey batch 1
            Mock(rowcount=5000),   # journey batch 2
            Mock(rowcount=0),      # discovery batch
            Mock(rowcount=0),      # validation batch
        ]

        freshness_session = AsyncMock()

        with (
            patch("trackrat.services.scheduler.get_settings", return_value=mock_settings),
            patch(
                "trackrat.services.scheduler.get_session"
            ) as mock_get_session,
            patch(
                "trackrat.services.scheduler.run_with_freshness_check"
            ) as mock_freshness,
        ):
            async def execute_task_func(db, task_name, minimum_interval_seconds, task_func):
                await task_func()
                return True

            mock_freshness.side_effect = execute_task_func

            # First call = freshness session, then 4 batch sessions
            ctxs = []
            # Freshness session (opened first)
            ctx_fresh = AsyncMock()
            ctx_fresh.__aenter__ = AsyncMock(return_value=freshness_session)
            ctx_fresh.__aexit__ = AsyncMock(return_value=False)
            ctxs.append(ctx_fresh)

            # Batch sessions
            for result in execute_results:
                s = AsyncMock()
                s.execute = AsyncMock(return_value=result)
                ctx = AsyncMock()
                ctx.__aenter__ = AsyncMock(return_value=s)
                ctx.__aexit__ = AsyncMock(return_value=False)
                ctxs.append(ctx)

            mock_get_session.side_effect = ctxs

            await service.retention_cleanup()

            # 1 freshness + 2 journey batches + 1 discovery + 1 validation = 5 sessions
            assert mock_get_session.call_count == 5

    @pytest.mark.asyncio
    async def test_cleanup_skipped_when_still_fresh(self, mock_settings):
        """When freshness check fails, cleanup should be skipped."""
        from trackrat.services.scheduler import SchedulerService

        service = SchedulerService.__new__(SchedulerService)

        freshness_session = AsyncMock()

        with (
            patch("trackrat.services.scheduler.get_settings", return_value=mock_settings),
            patch(
                "trackrat.services.scheduler.get_session"
            ) as mock_get_session,
            patch(
                "trackrat.services.scheduler.run_with_freshness_check",
                return_value=False,
            ) as mock_freshness,
        ):
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=freshness_session)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_get_session.return_value = ctx

            await service.retention_cleanup()

            # Freshness check called but task was not executed
            assert mock_freshness.called
            # Only 1 session opened (for freshness check), no batch sessions
            assert mock_get_session.call_count == 1

    @pytest.mark.asyncio
    async def test_cleanup_uses_configured_retention_days(self):
        """The cleanup should use retention_days from settings."""
        from trackrat.services.scheduler import SchedulerService

        service = SchedulerService.__new__(SchedulerService)

        mock_settings = Mock()
        mock_settings.retention_days = 90

        empty_result = Mock()
        empty_result.rowcount = 0

        freshness_session = AsyncMock()
        executed_params = []

        def make_capture_session():
            session = AsyncMock()

            async def capture_execute(stmt, params=None):
                if params:
                    executed_params.append(dict(params))
                return empty_result

            session.execute = AsyncMock(side_effect=capture_execute)
            return session

        with (
            patch("trackrat.services.scheduler.get_settings", return_value=mock_settings),
            patch(
                "trackrat.services.scheduler.get_session"
            ) as mock_get_session,
            patch(
                "trackrat.services.scheduler.run_with_freshness_check"
            ) as mock_freshness,
        ):
            async def execute_task_func(db, task_name, minimum_interval_seconds, task_func):
                await task_func()
                return True

            mock_freshness.side_effect = execute_task_func

            # First call = freshness, then 3 batch sessions (one per table)
            ctxs = []
            ctx_fresh = AsyncMock()
            ctx_fresh.__aenter__ = AsyncMock(return_value=freshness_session)
            ctx_fresh.__aexit__ = AsyncMock(return_value=False)
            ctxs.append(ctx_fresh)

            for _ in range(3):
                ctx = AsyncMock()
                ctx.__aenter__ = AsyncMock(return_value=make_capture_session())
                ctx.__aexit__ = AsyncMock(return_value=False)
                ctxs.append(ctx)

            mock_get_session.side_effect = ctxs

            await service.retention_cleanup()

            # All three DELETE calls should use days=90
            assert len(executed_params) == 3
            for params in executed_params:
                assert params["days"] == 90
                assert params["batch_size"] == 10000

    @pytest.mark.asyncio
    async def test_cleanup_handles_exception_gracefully(self, mock_settings):
        """If a DELETE fails, the error should be logged but not crash."""
        from trackrat.services.scheduler import SchedulerService

        service = SchedulerService.__new__(SchedulerService)

        error_session = AsyncMock()
        error_session.execute = AsyncMock(side_effect=RuntimeError("connection lost"))

        freshness_session = AsyncMock()

        with (
            patch("trackrat.services.scheduler.get_settings", return_value=mock_settings),
            patch(
                "trackrat.services.scheduler.get_session"
            ) as mock_get_session,
            patch(
                "trackrat.services.scheduler.run_with_freshness_check"
            ) as mock_freshness,
            patch("trackrat.services.scheduler.logger") as mock_logger,
        ):
            async def execute_task_func(db, task_name, minimum_interval_seconds, task_func):
                await task_func()
                return True

            mock_freshness.side_effect = execute_task_func

            # First call = freshness session, second = batch session that errors
            ctx_fresh = AsyncMock()
            ctx_fresh.__aenter__ = AsyncMock(return_value=freshness_session)
            ctx_fresh.__aexit__ = AsyncMock(return_value=False)

            ctx_batch = AsyncMock()
            ctx_batch.__aenter__ = AsyncMock(return_value=error_session)
            ctx_batch.__aexit__ = AsyncMock(return_value=False)

            mock_get_session.side_effect = [ctx_fresh, ctx_batch]

            # Should not raise
            await service.retention_cleanup()

            # Error should be logged
            mock_logger.error.assert_called()
            error_call = mock_logger.error.call_args
            assert "retention_cleanup_failed" in str(error_call)


class TestRetentionCleanupSQLStatements:
    """Test that the SQL statements target the correct tables and columns."""

    def test_cleanup_targets_journey_date_column(self):
        """The train_journeys DELETE should filter on journey_date."""
        from trackrat.services.scheduler import SchedulerService
        import inspect

        source = inspect.getsource(SchedulerService.retention_cleanup)
        assert "DELETE FROM train_journeys" in source
        assert "journey_date < CURRENT_DATE" in source

    def test_cleanup_targets_discovery_runs_run_at(self):
        """The discovery_runs DELETE should filter on run_at."""
        from trackrat.services.scheduler import SchedulerService
        import inspect

        source = inspect.getsource(SchedulerService.retention_cleanup)
        assert "DELETE FROM discovery_runs" in source
        assert "run_at < NOW()" in source

    def test_cleanup_targets_validation_results_run_at(self):
        """The validation_results DELETE should filter on run_at."""
        from trackrat.services.scheduler import SchedulerService
        import inspect

        source = inspect.getsource(SchedulerService.retention_cleanup)
        assert "DELETE FROM validation_results" in source

    def test_cleanup_uses_batch_limit(self):
        """All DELETE statements should use LIMIT for batching."""
        from trackrat.services.scheduler import SchedulerService
        import inspect

        source = inspect.getsource(SchedulerService.retention_cleanup)
        # Should have 3 LIMIT clauses (one per table)
        assert source.count("LIMIT :batch_size") == 3

    def test_cleanup_uses_subquery_pattern(self):
        """DELETEs should use id IN (SELECT id ... LIMIT) for efficient batching."""
        from trackrat.services.scheduler import SchedulerService
        import inspect

        source = inspect.getsource(SchedulerService.retention_cleanup)
        assert source.count("WHERE id IN (") == 3

    def test_cascade_covers_all_dependent_tables(self):
        """All TrainJourney child tables should have ON DELETE CASCADE FKs."""
        from trackrat.models.database import (
            JourneyStop,
            JourneySnapshot,
            JourneyProgress,
            SegmentTransitTime,
            StationDwellTime,
        )

        child_models = [
            JourneyStop,
            JourneySnapshot,
            JourneyProgress,
            SegmentTransitTime,
            StationDwellTime,
        ]

        for model in child_models:
            table = model.__table__
            journey_fk = None
            for fk in table.foreign_keys:
                if fk.column.table.name == "train_journeys":
                    journey_fk = fk
                    break
            assert journey_fk is not None, (
                f"{model.__tablename__} missing FK to train_journeys"
            )
            assert journey_fk.ondelete == "CASCADE", (
                f"{model.__tablename__} FK to train_journeys missing ON DELETE CASCADE"
            )


class TestRetentionCleanupFreshnessCheck:
    """Test freshness check integration."""

    def test_uses_24_hour_safe_interval(self):
        """retention_cleanup should use calculate_safe_interval(24 * 60)."""
        from trackrat.services.scheduler import SchedulerService
        from trackrat.utils.scheduler_utils import calculate_safe_interval
        import inspect

        source = inspect.getsource(SchedulerService.retention_cleanup)
        assert "calculate_safe_interval(24 * 60)" in source

        expected = calculate_safe_interval(24 * 60)
        # ~23 hours in seconds (90% of 24h minus buffer)
        assert 20 * 3600 < expected < 24 * 3600

    def test_task_name_is_retention_cleanup(self):
        """The task should be registered as 'retention_cleanup' in freshness check."""
        from trackrat.services.scheduler import SchedulerService
        import inspect

        source = inspect.getsource(SchedulerService.retention_cleanup)
        assert 'task_name="retention_cleanup"' in source
