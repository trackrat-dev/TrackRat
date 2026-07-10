"""
Tests for the data retention cleanup system (issue #987).

Verifies that the retention cleanup job is registered in the scheduler,
that the batch delete logic works correctly for train_journeys,
discovery_runs, and validation_results, and that the retention_days
setting is properly configured.
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from trackrat.settings import Settings


def make_empty_partition_drop_session() -> AsyncMock:
    """Session stub for retention_cleanup's phase 5 (drop_old_partitions).

    `drop_old_partitions` issues a SELECT against pg_inherits per managed
    table and iterates the result; returning an empty iterable means no
    partitions are found droppable, so no further DROP TABLE calls happen.
    """
    session = AsyncMock()
    empty_result = MagicMock()
    empty_result.__iter__ = Mock(return_value=iter([]))
    session.execute = AsyncMock(return_value=empty_result)
    return session


def make_ctx(session: AsyncMock) -> AsyncMock:
    """Wrap a session mock in an async context manager, as returned by
    `get_session()`."""
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


class TestRetentionSettings:
    """Test retention_days setting configuration."""

    def test_default_retention_days(self):
        """Default retention_days should be 60."""
        settings = Settings(database_url="postgresql+asyncpg://x:x@localhost/x")
        assert settings.retention_days == 60

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

    def test_default_subway_retention_days(self):
        """Default subway_retention_days should be 14."""
        settings = Settings(database_url="postgresql+asyncpg://x:x@localhost/x")
        assert settings.subway_retention_days == 14

    def test_custom_subway_retention_days(self):
        """subway_retention_days should be configurable via environment."""
        with patch.dict("os.environ", {"TRACKRAT_SUBWAY_RETENTION_DAYS": "21"}):
            settings = Settings(database_url="postgresql+asyncpg://x:x@localhost/x")
            assert settings.subway_retention_days == 21

    def test_subway_retention_days_below_general_minimum_allowed(self):
        """subway_retention_days may be below the 30-day general floor.

        Subway is pruned more aggressively than other providers, so its floor is
        only 1 (it does not share retention_days' ge=30 constraint).
        """
        settings = Settings(
            database_url="postgresql+asyncpg://x:x@localhost/x",
            subway_retention_days=14,
        )
        assert settings.subway_retention_days == 14

    def test_subway_retention_days_zero_rejected(self):
        """subway_retention_days below 1 should be rejected."""
        with pytest.raises(Exception):
            Settings(
                database_url="postgresql+asyncpg://x:x@localhost/x",
                subway_retention_days=0,
            )


class TestRetentionCleanupSchedulerRegistration:
    """Test that retention_cleanup is registered as a scheduler job."""

    def test_retention_cleanup_method_exists(self):
        """SchedulerService should have a retention_cleanup method."""
        from trackrat.services.scheduler import SchedulerService

        assert hasattr(SchedulerService, "retention_cleanup")
        assert callable(SchedulerService.retention_cleanup)

    def test_retention_cleanup_job_registered_in_schedule_jobs(self):
        """The _schedule_jobs method should register retention_cleanup."""
        import inspect

        from trackrat.services.scheduler import SchedulerService

        source = inspect.getsource(SchedulerService)
        assert 'id="retention_cleanup"' in source
        assert "self.retention_cleanup" in source

    def test_retention_cleanup_uses_cron_trigger(self):
        """retention_cleanup should use CronTrigger at 3:30 AM ET."""
        import inspect

        from trackrat.services.scheduler import SchedulerService

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
        """Mock settings with retention_days=120, subway_retention_days=14."""
        settings = Mock()
        settings.retention_days = 120
        settings.subway_retention_days = 14
        return settings

    @pytest.mark.asyncio
    async def test_single_batch_deletes_all(self, mock_settings):
        """When fewer rows than batch_size exist, a single batch suffices."""
        from trackrat.services.scheduler import SchedulerService

        service = SchedulerService.__new__(SchedulerService)

        execute_results = [
            Mock(rowcount=500),  # journey batch
            Mock(rowcount=100),  # discovery batch
            Mock(rowcount=50),  # validation batch
            Mock(rowcount=25),  # service_alerts batch
        ]

        freshness_session = AsyncMock()

        with (
            patch(
                "trackrat.services.scheduler.get_settings", return_value=mock_settings
            ),
            patch("trackrat.services.scheduler.get_session") as mock_get_session,
            patch(
                "trackrat.services.scheduler.run_with_freshness_check"
            ) as mock_freshness,
        ):

            async def execute_task_func(
                db, task_name, minimum_interval_seconds, task_func
            ):
                await task_func()
                return True

            mock_freshness.side_effect = execute_task_func

            # Sessions in call order: freshness, phase-0 partition bootstrap,
            # 4 batch deletes (journey/discovery/validation/service_alerts),
            # phase-5 partition drop.
            ctxs = []
            ctx_fresh = AsyncMock()
            ctx_fresh.__aenter__ = AsyncMock(return_value=freshness_session)
            ctx_fresh.__aexit__ = AsyncMock(return_value=False)
            ctxs.append(ctx_fresh)

            phase0_session = AsyncMock()
            phase0_session.execute = AsyncMock(return_value=Mock(rowcount=0))
            ctxs.append(make_ctx(phase0_session))  # phase 0

            for result in execute_results:
                s = AsyncMock()
                s.execute = AsyncMock(return_value=result)
                ctxs.append(make_ctx(s))

            ctxs.append(make_ctx(make_empty_partition_drop_session()))  # phase 5

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

        # Simulate: first journey batch returns 1000 (full), second returns 500 (partial)
        execute_results = [
            Mock(rowcount=1000),  # journey batch 1
            Mock(rowcount=500),  # journey batch 2
            Mock(rowcount=0),  # discovery batch
            Mock(rowcount=0),  # validation batch
            Mock(rowcount=0),  # service_alerts batch
        ]

        freshness_session = AsyncMock()

        with (
            patch(
                "trackrat.services.scheduler.get_settings", return_value=mock_settings
            ),
            patch("trackrat.services.scheduler.get_session") as mock_get_session,
            patch(
                "trackrat.services.scheduler.run_with_freshness_check"
            ) as mock_freshness,
        ):

            async def execute_task_func(
                db, task_name, minimum_interval_seconds, task_func
            ):
                await task_func()
                return True

            mock_freshness.side_effect = execute_task_func

            # First call = freshness session, then partition-bootstrap (phase 0),
            # then 4 batch sessions, then partition-drop (phase 5)
            ctxs = []
            # Freshness session (opened first)
            ctx_fresh = AsyncMock()
            ctx_fresh.__aenter__ = AsyncMock(return_value=freshness_session)
            ctx_fresh.__aexit__ = AsyncMock(return_value=False)
            ctxs.append(ctx_fresh)

            def _make_batch_ctx(result):
                s = AsyncMock()
                s.execute = AsyncMock(return_value=result)
                return make_ctx(s)

            ctxs.append(
                _make_batch_ctx(Mock(rowcount=0))
            )  # phase 0: ensure_future_partitions

            # Batch sessions
            for result in execute_results:
                ctxs.append(_make_batch_ctx(result))

            ctxs.append(make_ctx(make_empty_partition_drop_session()))  # phase 5

            mock_get_session.side_effect = ctxs

            await service.retention_cleanup()

            # 1 freshness + 1 partition-bootstrap + 2 journey batches
            # + 1 discovery + 1 validation + 1 service_alerts
            # + 1 partition-drop = 8 sessions
            assert mock_get_session.call_count == 8

    @pytest.mark.asyncio
    async def test_cleanup_skipped_when_still_fresh(self, mock_settings):
        """When freshness check fails, cleanup should be skipped."""
        from trackrat.services.scheduler import SchedulerService

        service = SchedulerService.__new__(SchedulerService)

        freshness_session = AsyncMock()

        with (
            patch(
                "trackrat.services.scheduler.get_settings", return_value=mock_settings
            ),
            patch("trackrat.services.scheduler.get_session") as mock_get_session,
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
        mock_settings.subway_retention_days = 14

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
            patch(
                "trackrat.services.scheduler.get_settings", return_value=mock_settings
            ),
            patch("trackrat.services.scheduler.get_session") as mock_get_session,
            patch(
                "trackrat.services.scheduler.run_with_freshness_check"
            ) as mock_freshness,
        ):

            async def execute_task_func(
                db, task_name, minimum_interval_seconds, task_func
            ):
                await task_func()
                return True

            mock_freshness.side_effect = execute_task_func

            # First call = freshness, then partition-bootstrap (phase 0),
            # then 4 batch sessions (one per table), then partition-drop (phase 5)
            ctxs = []
            ctx_fresh = AsyncMock()
            ctx_fresh.__aenter__ = AsyncMock(return_value=freshness_session)
            ctx_fresh.__aexit__ = AsyncMock(return_value=False)
            ctxs.append(ctx_fresh)

            ctxs.append(make_ctx(make_capture_session()))  # phase 0

            for _ in range(4):
                ctx = AsyncMock()
                ctx.__aenter__ = AsyncMock(return_value=make_capture_session())
                ctx.__aexit__ = AsyncMock(return_value=False)
                ctxs.append(ctx)

            ctxs.append(make_ctx(make_empty_partition_drop_session()))  # phase 5

            mock_get_session.side_effect = ctxs

            await service.retention_cleanup()

            # All four DELETE calls should use days=90 (partition-bootstrap
            # and partition-drop pass no params, so they aren't captured)
            assert len(executed_params) == 4
            for params in executed_params:
                assert params["days"] == 90
                assert params["batch_size"] == 1000

    @pytest.mark.asyncio
    async def test_subway_uses_shorter_retention_window(self):
        """The train_journeys DELETE carries both the default and subway cutoffs.

        Subway is pruned on a shorter window via a CASE in the train_journeys
        DELETE; the other phases (discovery_runs, validation_results,
        service_alerts) only ever use the default cutoff.
        """
        from trackrat.services.scheduler import SchedulerService

        service = SchedulerService.__new__(SchedulerService)

        mock_settings = Mock()
        mock_settings.retention_days = 120
        mock_settings.subway_retention_days = 14

        empty_result = Mock(rowcount=0)
        captured: list[tuple[str, dict]] = []

        def make_capture_session():
            session = AsyncMock()

            async def capture_execute(stmt, params=None):
                captured.append((str(stmt), dict(params) if params else {}))
                return empty_result

            session.execute = AsyncMock(side_effect=capture_execute)
            return session

        freshness_session = AsyncMock()

        with (
            patch(
                "trackrat.services.scheduler.get_settings", return_value=mock_settings
            ),
            patch("trackrat.services.scheduler.get_session") as mock_get_session,
            patch(
                "trackrat.services.scheduler.run_with_freshness_check"
            ) as mock_freshness,
        ):

            async def execute_task_func(
                db, task_name, minimum_interval_seconds, task_func
            ):
                await task_func()
                return True

            mock_freshness.side_effect = execute_task_func

            ctxs = []
            ctx_fresh = AsyncMock()
            ctx_fresh.__aenter__ = AsyncMock(return_value=freshness_session)
            ctx_fresh.__aexit__ = AsyncMock(return_value=False)
            ctxs.append(ctx_fresh)

            # Phase 0 (ensure_future_partitions) passes no params, so it
            # would only pollute `captured` with noise — use a plain
            # non-capturing session instead.
            plain_session = AsyncMock()
            plain_session.execute = AsyncMock(return_value=empty_result)
            ctxs.append(make_ctx(plain_session))

            for _ in range(4):
                ctx = AsyncMock()
                ctx.__aenter__ = AsyncMock(return_value=make_capture_session())
                ctx.__aexit__ = AsyncMock(return_value=False)
                ctxs.append(ctx)

            ctxs.append(make_ctx(make_empty_partition_drop_session()))  # phase 5

            mock_get_session.side_effect = ctxs

            await service.retention_cleanup()

        # One DELETE per phase (each returns rowcount 0 -> single batch).
        assert len(captured) == 4

        journey_stmt, journey_params = captured[0]
        assert "DELETE FROM train_journeys" in journey_stmt
        assert journey_params["days"] == 120
        assert journey_params["subway_days"] == 14
        assert journey_params["batch_size"] == 1000

        # Remaining phases only carry the default cutoff, never subway_days.
        for stmt, params in captured[1:]:
            assert "train_journeys" not in stmt
            assert params["days"] == 120
            assert "subway_days" not in params

    @pytest.mark.asyncio
    async def test_cleanup_handles_exception_gracefully(self, mock_settings):
        """If a DELETE fails, do_retention_work logs and re-raises; the freshness
        wrapper catches it so the public method does not crash.

        The re-raise is deliberate: run_with_freshness_check only records a run
        as successful when task_func returns without raising, so swallowing the
        error here would falsely mark the failed run fresh. This mock emulates
        the real wrapper's catch.
        """
        from trackrat.services.scheduler import SchedulerService

        service = SchedulerService.__new__(SchedulerService)

        error_session = AsyncMock()
        error_session.execute = AsyncMock(side_effect=RuntimeError("connection lost"))

        freshness_session = AsyncMock()

        with (
            patch(
                "trackrat.services.scheduler.get_settings", return_value=mock_settings
            ),
            patch("trackrat.services.scheduler.get_session") as mock_get_session,
            patch(
                "trackrat.services.scheduler.run_with_freshness_check"
            ) as mock_freshness,
            patch("trackrat.services.scheduler.logger") as mock_logger,
        ):

            async def execute_task_func(
                db, task_name, minimum_interval_seconds, task_func
            ):
                # Mirror run_with_freshness_check: a raising task_func is caught
                # and reported as a failed (not successful) run.
                try:
                    await task_func()
                    return True
                except Exception:
                    return False

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
        import inspect

        from trackrat.services.scheduler import SchedulerService

        source = inspect.getsource(SchedulerService.retention_cleanup)
        assert "DELETE FROM train_journeys" in source
        assert "journey_date < CURRENT_DATE" in source

    def test_cleanup_applies_subway_case_in_journey_delete(self):
        """The train_journeys DELETE should branch SUBWAY onto its own cutoff."""
        import inspect

        from trackrat.services.scheduler import SchedulerService

        source = inspect.getsource(SchedulerService.retention_cleanup)
        assert "data_source = 'SUBWAY'" in source
        assert ":subway_days" in source
        # The CASE belongs only to the train_journeys phase; the other three
        # DELETEs stay on the single default cutoff (:days).
        assert source.count(":subway_days") == 1

    def test_cleanup_targets_discovery_runs_run_at(self):
        """The discovery_runs DELETE should filter on run_at."""
        import inspect

        from trackrat.services.scheduler import SchedulerService

        source = inspect.getsource(SchedulerService.retention_cleanup)
        assert "DELETE FROM discovery_runs" in source
        assert "run_at < NOW()" in source

    def test_cleanup_targets_validation_results_run_at(self):
        """The validation_results DELETE should filter on run_at."""
        import inspect

        from trackrat.services.scheduler import SchedulerService

        source = inspect.getsource(SchedulerService.retention_cleanup)
        assert "DELETE FROM validation_results" in source

    def test_cleanup_targets_inactive_service_alerts(self):
        """The service_alerts DELETE should only prune inactive rows by updated_at."""
        import inspect

        from trackrat.services.scheduler import SchedulerService

        source = inspect.getsource(SchedulerService.retention_cleanup)
        assert "DELETE FROM service_alerts" in source
        # Must gate on is_active=false so currently active alerts are preserved
        assert "is_active = false" in source
        # Must filter on updated_at so collector-refreshed alerts stay
        assert "updated_at < NOW()" in source

    def test_cleanup_uses_batch_limit(self):
        """All DELETE statements should use LIMIT for batching."""
        import inspect

        from trackrat.services.scheduler import SchedulerService

        source = inspect.getsource(SchedulerService.retention_cleanup)
        # Should have 4 LIMIT clauses (one per table)
        assert source.count("LIMIT :batch_size") == 4

    def test_cleanup_uses_subquery_pattern(self):
        """DELETEs should use id IN (SELECT id ... LIMIT) for efficient batching."""
        import inspect

        from trackrat.services.scheduler import SchedulerService

        source = inspect.getsource(SchedulerService.retention_cleanup)
        assert source.count("WHERE id IN (") == 4

    def test_make_interval_day_args_are_cast_to_int(self):
        """Every make_interval(days => ...) must cast its arg to int via CAST().

        asyncpg sends bound parameters untyped, so a bare
        ``make_interval(days => CASE ... END)`` over untyped params resolves to
        the nonexistent ``make_interval(days => text)`` overload and raises
        ``UndefinedFunctionError``. The cast must be spelled ``CAST(:name AS
        int)`` and NOT ``:name::int``: SQLAlchemy's ``text()`` bind-param parser
        refuses to substitute a ``:name`` immediately followed by ``::``, so the
        literal ``:name`` reaches Postgres and it raises a syntax error. Guards
        against regression of both forms across all four DELETE phases.
        """
        import inspect
        import re

        from trackrat.services.scheduler import SchedulerService

        source = inspect.getsource(SchedulerService.retention_cleanup)
        # Collapse Python string-concatenation boundaries ("..." "...") and
        # surrounding whitespace so the CASE expression reads as one line.
        collapsed = re.sub(r'"\s*"', "", source)
        collapsed = re.sub(r"\s+", " ", collapsed)

        # One make_interval per phase (train_journeys, discovery_runs,
        # validation_results, service_alerts).
        assert collapsed.count("make_interval(days =>") == 4
        # The ``::int`` cast operator is broken inside SQLAlchemy text() — it
        # must never appear.
        assert "::int" not in collapsed
        # The three simple phases must use the CAST() form.
        assert collapsed.count("make_interval(days => CAST(:days AS int))") == 3
        # The train_journeys CASE must CAST() both branches to int.
        assert "THEN CAST(:subway_days AS int) ELSE CAST(:days AS int) END" in collapsed

    def test_cascade_covers_all_dependent_tables(self):
        """All TrainJourney child tables should have ON DELETE CASCADE FKs."""
        from trackrat.models.database import (
            JourneyProgress,
            JourneyStop,
            SegmentTransitTime,
            StationDwellTime,
        )

        child_models = [
            JourneyStop,
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
            assert (
                journey_fk is not None
            ), f"{model.__tablename__} missing FK to train_journeys"
            assert (
                journey_fk.ondelete == "CASCADE"
            ), f"{model.__tablename__} FK to train_journeys missing ON DELETE CASCADE"


class TestRetentionCleanupFreshnessCheck:
    """Test freshness check integration."""

    def test_uses_24_hour_safe_interval(self):
        """retention_cleanup should use calculate_safe_interval(24 * 60)."""
        import inspect

        from trackrat.services.scheduler import SchedulerService
        from trackrat.utils.scheduler_utils import calculate_safe_interval

        source = inspect.getsource(SchedulerService.retention_cleanup)
        assert "calculate_safe_interval(24 * 60)" in source

        expected = calculate_safe_interval(24 * 60)
        # ~23 hours in seconds (90% of 24h minus buffer)
        assert 20 * 3600 < expected < 24 * 3600

    def test_task_name_is_retention_cleanup(self):
        """The task should be registered as 'retention_cleanup' in freshness check."""
        import inspect

        from trackrat.services.scheduler import SchedulerService

        source = inspect.getsource(SchedulerService.retention_cleanup)
        assert 'task_name="retention_cleanup"' in source


class TestServiceAlertsRetention:
    """Test that the new service_alerts retention phase behaves correctly."""

    @pytest.fixture
    def mock_settings(self):
        settings = Mock()
        settings.retention_days = 120
        settings.subway_retention_days = 14
        return settings

    @pytest.mark.asyncio
    async def test_service_alerts_batch_runs_to_completion(self, mock_settings):
        """service_alerts deletion should loop until a partial batch returns."""
        from trackrat.services.scheduler import SchedulerService

        service = SchedulerService.__new__(SchedulerService)

        # journey/discovery/validation each return empty in one batch.
        # service_alerts: 1000 then 1000 then 200 (partial, stops loop).
        execute_results = [
            Mock(rowcount=0),  # journey
            Mock(rowcount=0),  # discovery
            Mock(rowcount=0),  # validation
            Mock(rowcount=1000),  # service_alerts batch 1 (full)
            Mock(rowcount=1000),  # service_alerts batch 2 (full)
            Mock(rowcount=200),  # service_alerts batch 3 (partial)
        ]

        freshness_session = AsyncMock()

        with (
            patch(
                "trackrat.services.scheduler.get_settings", return_value=mock_settings
            ),
            patch("trackrat.services.scheduler.get_session") as mock_get_session,
            patch(
                "trackrat.services.scheduler.run_with_freshness_check"
            ) as mock_freshness,
        ):

            async def execute_task_func(
                db, task_name, minimum_interval_seconds, task_func
            ):
                await task_func()
                return True

            mock_freshness.side_effect = execute_task_func

            ctxs = []
            ctx_fresh = AsyncMock()
            ctx_fresh.__aenter__ = AsyncMock(return_value=freshness_session)
            ctx_fresh.__aexit__ = AsyncMock(return_value=False)
            ctxs.append(ctx_fresh)

            plain_session = AsyncMock()
            plain_session.execute = AsyncMock(return_value=Mock(rowcount=0))
            ctxs.append(make_ctx(plain_session))  # phase 0

            for result in execute_results:
                s = AsyncMock()
                s.execute = AsyncMock(return_value=result)
                ctx = AsyncMock()
                ctx.__aenter__ = AsyncMock(return_value=s)
                ctx.__aexit__ = AsyncMock(return_value=False)
                ctxs.append(ctx)

            ctxs.append(make_ctx(make_empty_partition_drop_session()))  # phase 5

            mock_get_session.side_effect = ctxs

            await service.retention_cleanup()

            # 1 freshness + 1 partition-bootstrap + 1 journey + 1 discovery
            # + 1 validation + 3 service_alerts + 1 partition-drop = 9 sessions
            assert mock_get_session.call_count == 9

    @pytest.mark.asyncio
    async def test_service_alerts_delete_passes_correct_params(self, mock_settings):
        """The service_alerts DELETE should receive the same days/batch_size args."""
        from trackrat.services.scheduler import SchedulerService

        service = SchedulerService.__new__(SchedulerService)

        executed_statements: list[str] = []
        executed_params: list[dict] = []

        empty_result = Mock(rowcount=0)

        def make_capture_session():
            session = AsyncMock()

            async def capture_execute(stmt, params=None):
                executed_statements.append(str(stmt))
                if params:
                    executed_params.append(dict(params))
                return empty_result

            session.execute = AsyncMock(side_effect=capture_execute)
            return session

        freshness_session = AsyncMock()

        with (
            patch(
                "trackrat.services.scheduler.get_settings", return_value=mock_settings
            ),
            patch("trackrat.services.scheduler.get_session") as mock_get_session,
            patch(
                "trackrat.services.scheduler.run_with_freshness_check"
            ) as mock_freshness,
        ):

            async def execute_task_func(
                db, task_name, minimum_interval_seconds, task_func
            ):
                await task_func()
                return True

            mock_freshness.side_effect = execute_task_func

            ctxs = []
            ctx_fresh = AsyncMock()
            ctx_fresh.__aenter__ = AsyncMock(return_value=freshness_session)
            ctx_fresh.__aexit__ = AsyncMock(return_value=False)
            ctxs.append(ctx_fresh)

            # Phases 0 and 5 (partition bootstrap/drop) issue their own SQL
            # unrelated to the four per-table DELETEs under test — route them
            # through non-capturing sessions so they don't pollute the
            # executed_statements/executed_params assertions below.
            plain_session = AsyncMock()
            plain_session.execute = AsyncMock(return_value=empty_result)
            ctxs.append(make_ctx(plain_session))  # phase 0

            for _ in range(4):
                ctx = AsyncMock()
                ctx.__aenter__ = AsyncMock(return_value=make_capture_session())
                ctx.__aexit__ = AsyncMock(return_value=False)
                ctxs.append(ctx)

            ctxs.append(make_ctx(make_empty_partition_drop_session()))  # phase 5

            mock_get_session.side_effect = ctxs

            await service.retention_cleanup()

            # 4 statements expected, one per table — service_alerts is last.
            assert len(executed_statements) == 4
            assert "service_alerts" in executed_statements[-1]
            assert "is_active = false" in executed_statements[-1]
            assert "updated_at < NOW()" in executed_statements[-1]

            # Every DELETE shares the same days + batch_size parameters.
            assert len(executed_params) == 4
            for params in executed_params:
                assert params["days"] == 120
                assert params["batch_size"] == 1000

    @pytest.mark.asyncio
    async def test_completion_log_includes_service_alerts_count(self, mock_settings):
        """The success log should report service_alerts_deleted."""
        from trackrat.services.scheduler import SchedulerService

        service = SchedulerService.__new__(SchedulerService)

        execute_results = [
            Mock(rowcount=0),  # journey
            Mock(rowcount=0),  # discovery
            Mock(rowcount=0),  # validation
            Mock(rowcount=42),  # service_alerts (partial in single batch)
        ]

        freshness_session = AsyncMock()

        with (
            patch(
                "trackrat.services.scheduler.get_settings", return_value=mock_settings
            ),
            patch("trackrat.services.scheduler.get_session") as mock_get_session,
            patch(
                "trackrat.services.scheduler.run_with_freshness_check"
            ) as mock_freshness,
            patch("trackrat.services.scheduler.logger") as mock_logger,
        ):

            async def execute_task_func(
                db, task_name, minimum_interval_seconds, task_func
            ):
                await task_func()
                return True

            mock_freshness.side_effect = execute_task_func

            ctxs = []
            ctx_fresh = AsyncMock()
            ctx_fresh.__aenter__ = AsyncMock(return_value=freshness_session)
            ctx_fresh.__aexit__ = AsyncMock(return_value=False)
            ctxs.append(ctx_fresh)

            plain_session = AsyncMock()
            plain_session.execute = AsyncMock(return_value=Mock(rowcount=0))
            ctxs.append(make_ctx(plain_session))  # phase 0

            for result in execute_results:
                s = AsyncMock()
                s.execute = AsyncMock(return_value=result)
                ctx = AsyncMock()
                ctx.__aenter__ = AsyncMock(return_value=s)
                ctx.__aexit__ = AsyncMock(return_value=False)
                ctxs.append(ctx)

            ctxs.append(make_ctx(make_empty_partition_drop_session()))  # phase 5

            mock_get_session.side_effect = ctxs

            await service.retention_cleanup()

            completion_calls = [
                c
                for c in mock_logger.info.call_args_list
                if c.args and c.args[0] == "retention_cleanup_completed"
            ]
            assert len(completion_calls) == 1
            kwargs = completion_calls[0].kwargs
            assert kwargs["service_alerts_deleted"] == 42
            assert kwargs["journeys_deleted"] == 0
            assert kwargs["discovery_runs_deleted"] == 0
            assert kwargs["validation_results_deleted"] == 0

    @pytest.mark.asyncio
    async def test_failure_log_includes_service_alerts_so_far(self, mock_settings):
        """If service_alerts DELETE raises, the partial count should be logged."""
        from trackrat.services.scheduler import SchedulerService

        service = SchedulerService.__new__(SchedulerService)

        # journey + discovery + validation succeed empty; service_alerts errors.
        ok_result = Mock(rowcount=0)

        call_idx = {"n": 0}

        def make_session():
            session = AsyncMock()

            async def execute(stmt, params=None):
                call_idx["n"] += 1
                if call_idx["n"] == 4:  # 4th call is service_alerts
                    raise RuntimeError("connection lost")
                return ok_result

            session.execute = AsyncMock(side_effect=execute)
            return session

        freshness_session = AsyncMock()

        with (
            patch(
                "trackrat.services.scheduler.get_settings", return_value=mock_settings
            ),
            patch("trackrat.services.scheduler.get_session") as mock_get_session,
            patch(
                "trackrat.services.scheduler.run_with_freshness_check"
            ) as mock_freshness,
            patch("trackrat.services.scheduler.logger") as mock_logger,
        ):

            async def execute_task_func(
                db, task_name, minimum_interval_seconds, task_func
            ):
                # Mirror run_with_freshness_check: catch the re-raised failure so
                # the run is reported as failed (not successful).
                try:
                    await task_func()
                    return True
                except Exception:
                    return False

            mock_freshness.side_effect = execute_task_func

            ctxs = []
            ctx_fresh = AsyncMock()
            ctx_fresh.__aenter__ = AsyncMock(return_value=freshness_session)
            ctx_fresh.__aexit__ = AsyncMock(return_value=False)
            ctxs.append(ctx_fresh)

            for _ in range(4):
                ctx = AsyncMock()
                ctx.__aenter__ = AsyncMock(return_value=make_session())
                ctx.__aexit__ = AsyncMock(return_value=False)
                ctxs.append(ctx)

            mock_get_session.side_effect = ctxs

            await service.retention_cleanup()

            failure_calls = [
                c
                for c in mock_logger.error.call_args_list
                if c.args and c.args[0] == "retention_cleanup_failed"
            ]
            assert len(failure_calls) == 1
            kwargs = failure_calls[0].kwargs
            assert "service_alerts_deleted_so_far" in kwargs
            assert kwargs["service_alerts_deleted_so_far"] == 0
