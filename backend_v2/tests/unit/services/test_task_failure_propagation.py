"""
Unit tests for scheduler task failure propagation (issue #1507).

retention_cleanup was fixed (c2a1406) to re-raise failures so
run_with_freshness_check records a failed run; five other freshness-wrapped
tasks kept the catch-log-continue anti-pattern. A swallowed failure made the
wrapper stamp last_successful_run: the task was skipped as "still fresh"
until its next window, and staleness-based monitoring stayed green. For the
two nightly schedule tasks that meant a full day of empty future departure
boards while scheduler_task_runs read healthy.

These tests replace run_with_freshness_check with a passthrough that invokes
the task function directly and assert the forced inner failure PROPAGATES
out — which is exactly what the wrapper needs to see to record a failure.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from trackrat.services.scheduler import SchedulerService
from trackrat.settings import Settings


@pytest.fixture
def scheduler_service():
    settings = Settings(
        njt_api_token="test_token",
        environment="testing",
    )
    with patch("trackrat.services.scheduler.NJTransitClient"):
        return SchedulerService(settings=settings, apns_service=AsyncMock())


@asynccontextmanager
async def _fake_session():
    yield AsyncMock()


async def _passthrough_freshness(**kwargs):
    """Stand-in for run_with_freshness_check: run the task, propagate errors.

    The real wrapper catches the exception, rolls back, and skips the
    last_successful_run update — so 'the exception reaches the wrapper' is
    the exact contract these tests pin.
    """
    await kwargs["task_func"]()
    return True


def _patched(scheduler_module_attr="run_with_freshness_check"):
    return patch(
        f"trackrat.services.scheduler.{scheduler_module_attr}",
        side_effect=_passthrough_freshness,
    )


class TestTaskFailurePropagation:
    @pytest.mark.asyncio
    async def test_njt_schedule_collection_failure_propagates(self, scheduler_service):
        """A failed nightly NJT schedule run must surface as a failed run —
        not stamp last_successful_run and leave empty boards all day."""
        scheduler_service.njt_client = None  # forces RuntimeError in the task

        with (
            _patched(),
            patch("trackrat.services.scheduler.get_session", _fake_session),
            pytest.raises(RuntimeError),
        ):
            await scheduler_service.collect_njt_schedules()

    @pytest.mark.asyncio
    async def test_amtrak_schedule_generation_failure_propagates(
        self, scheduler_service
    ):
        with (
            _patched(),
            patch("trackrat.services.scheduler.get_session", _fake_session),
            patch(
                "trackrat.services.scheduler.AmtrakPatternScheduler",
                side_effect=RuntimeError("pattern scheduler down"),
            ),
            pytest.raises(RuntimeError),
        ):
            await scheduler_service.generate_amtrak_schedules()

    @pytest.mark.asyncio
    async def test_gtfs_refresh_failure_propagates(self, scheduler_service):
        with (
            _patched(),
            patch("trackrat.services.scheduler.get_session", _fake_session),
            patch(
                "trackrat.services.gtfs.GTFSService",
                side_effect=RuntimeError("gtfs download hung"),
            ),
            pytest.raises(RuntimeError),
        ):
            await scheduler_service.refresh_gtfs_feeds()

    @pytest.mark.asyncio
    async def test_validation_failure_propagates(self, scheduler_service):
        with (
            _patched(),
            patch("trackrat.services.scheduler.get_session", _fake_session),
            patch(
                "trackrat.services.validation.TrainValidationService",
                side_effect=RuntimeError("validation exploded"),
            ),
            pytest.raises(RuntimeError),
        ):
            await scheduler_service.run_train_validation()

    @pytest.mark.asyncio
    async def test_live_activity_cleanup_failure_propagates(self, scheduler_service):
        with (
            _patched(),
            patch("trackrat.services.scheduler.get_session", _fake_session),
            patch.object(
                scheduler_service,
                "_get_sync_engine",
                side_effect=RuntimeError("sync engine unavailable"),
            ),
            pytest.raises(RuntimeError),
        ):
            await scheduler_service.cleanup_expired_live_activity_tokens()

    @pytest.mark.asyncio
    async def test_njt_journey_maintenance_failure_propagates(self, scheduler_service):
        """A failed NJT maintenance sweep (issue #1497) must surface as a
        failed run — not stamp last_successful_run while the reconcile /
        expiry sweeps silently stop running."""
        scheduler_service.njt_client = AsyncMock()  # get past the no-client guard
        with (
            _patched(),
            patch("trackrat.services.scheduler.get_session", _fake_session),
            patch(
                "trackrat.collectors.njt.journey.JourneyCollector",
                side_effect=RuntimeError("maintenance sweep exploded"),
            ),
            pytest.raises(RuntimeError),
        ):
            await scheduler_service.run_njt_journey_maintenance()
