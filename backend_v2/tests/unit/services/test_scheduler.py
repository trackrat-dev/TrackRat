"""
Comprehensive unit tests for SchedulerService.

Tests the main scheduler service that orchestrates all background tasks
including train discovery, journey updates, and horizontal scaling coordination.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import ANY, AsyncMock, Mock, call, patch

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trackrat.services.scheduler import SchedulerService
from trackrat.settings import Settings


class TestSchedulerService:
    """Test cases for the SchedulerService class."""

    @pytest.fixture
    def test_settings(self):
        """Create test settings."""
        return Settings(
            njt_api_token="test_token",
            discovery_interval_minutes=30,
            journey_update_interval_minutes=15,
            data_staleness_seconds=60,
            environment="testing",
        )

    @pytest.fixture
    def mock_njt_client(self):
        """Create a mock NJ Transit client."""
        client = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def mock_apns_service(self):
        """Create a mock APNS service."""
        service = AsyncMock()
        service.send_update = AsyncMock()
        return service

    @pytest.fixture
    def scheduler_service(self, test_settings, mock_apns_service):
        """Create a SchedulerService instance for testing."""
        with patch("trackrat.services.scheduler.NJTransitClient"):
            return SchedulerService(
                settings=test_settings, apns_service=mock_apns_service
            )

    @pytest.mark.asyncio
    async def test_scheduler_initialization(self, scheduler_service, test_settings):
        """Test that scheduler initializes with correct settings."""
        assert scheduler_service.settings == test_settings
        assert scheduler_service.njt_client is None
        assert scheduler_service.jit_service is None
        assert isinstance(scheduler_service.scheduler, AsyncIOScheduler)
        assert scheduler_service._running_tasks == {}

        # Verify scheduler configuration - ZoneInfo uses 'key' not 'zone'
        assert str(scheduler_service.scheduler.timezone) == "America/New_York"

    @pytest.mark.asyncio
    async def test_scheduler_start_creates_all_jobs(self, scheduler_service):
        """Test that starting the scheduler creates all required jobs."""
        with patch("trackrat.services.scheduler.NJTransitClient") as MockNJTClient:
            mock_client = AsyncMock()
            MockNJTClient.return_value = mock_client

            with patch.object(scheduler_service.scheduler, "start") as mock_start:
                with patch.object(
                    scheduler_service.scheduler, "add_job"
                ) as mock_add_job:
                    with patch("asyncio.create_task"):
                        await scheduler_service.start()

            # Verify NJT client was initialized
            MockNJTClient.assert_called_once_with(scheduler_service.settings)
            assert scheduler_service.njt_client == mock_client

            # Verify all jobs were added
            expected_jobs = [
                ("njt_train_discovery", IntervalTrigger, {"minutes": 30}),
                ("amtrak_train_discovery", IntervalTrigger, {"minutes": 30}),
                ("journey_update_check", IntervalTrigger, {"minutes": 5}),
                ("live_activity_updates", IntervalTrigger, {"minutes": 1}),
                ("live_activity_token_cleanup", IntervalTrigger, {"hours": 1}),
                ("congestion_cache_precompute", IntervalTrigger, {"minutes": 15}),
                ("departure_cache_precompute", IntervalTrigger, {"seconds": 90}),
                ("train_validation", IntervalTrigger, {"hours": 1}),
                ("njt_schedule_collection", CronTrigger, {"hour": 0, "minute": 30}),
                ("amtrak_schedule_generation", CronTrigger, {"hour": 0, "minute": 45}),
                ("lock_manager_cleanup", CronTrigger, {"hour": 1, "minute": 0}),
                ("gtfs_feed_refresh", CronTrigger, {"hour": 3, "minute": 0}),
            ]

            assert mock_add_job.call_count == len(expected_jobs)

            # Verify specific job configurations
            for call_obj in mock_add_job.call_args_list:
                job_id = call_obj.kwargs["id"]
                assert any(job_id == expected[0] for expected in expected_jobs)

                # Verify common job settings
                assert call_obj.kwargs["replace_existing"] is True
                assert call_obj.kwargs["max_instances"] == 1

    @pytest.mark.asyncio
    async def test_scheduler_stop_cancels_running_tasks(self, scheduler_service):
        """Test that stopping the scheduler cancels all running tasks."""
        # Create mock running tasks
        task1 = AsyncMock(spec=asyncio.Task)
        task1.done.return_value = False
        task1.cancel = Mock()

        task2 = AsyncMock(spec=asyncio.Task)
        task2.done.return_value = True  # Already completed
        task2.cancel = Mock()

        scheduler_service._running_tasks = {
            "task1": task1,
            "task2": task2,
        }

        # Mock NJT client
        scheduler_service.njt_client = AsyncMock()

        with patch.object(scheduler_service.scheduler, "shutdown") as mock_shutdown:
            await scheduler_service.stop()

        # Verify only non-completed task was cancelled
        task1.cancel.assert_called_once()
        task2.cancel.assert_not_called()

        # Verify scheduler was shut down
        mock_shutdown.assert_called_once_with(wait=True)

        # Verify NJT client was closed
        scheduler_service.njt_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_njt_discovery_with_freshness_check(self, scheduler_service):
        """Test NJT discovery runs with freshness checking."""
        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            with patch(
                "trackrat.services.scheduler.TrainDiscoveryCollector"
            ) as MockCollector:
                mock_collector = AsyncMock()
                mock_collector.run.return_value = {
                    "total_discovered": 50,
                    "total_new": 10,
                }
                MockCollector.return_value = mock_collector

                # Mock NJT client
                scheduler_service.njt_client = AsyncMock()

                with patch(
                    "trackrat.services.scheduler.run_with_freshness_check"
                ) as mock_freshness_check:
                    # Make freshness check actually call the task function
                    async def execute_task_func(
                        db, task_name, minimum_interval_seconds, task_func
                    ):
                        await task_func()
                        return True

                    mock_freshness_check.side_effect = execute_task_func

                    await scheduler_service.run_njt_discovery()

                # Verify freshness check was called with correct parameters
                mock_freshness_check.assert_called_once()
                call_args = mock_freshness_check.call_args
                assert call_args.kwargs["task_name"] == "njt_discovery"
                assert call_args.kwargs["minimum_interval_seconds"] == 1620  # (30-3)*60

                # Verify discovery collector was used
                MockCollector.assert_called_once_with(scheduler_service.njt_client)
                mock_collector.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_njt_discovery_skipped_when_fresh(self, scheduler_service):
        """Test NJT discovery is skipped when task is still fresh."""
        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            with patch(
                "trackrat.services.scheduler.run_with_freshness_check"
            ) as mock_freshness_check:
                # Task is still fresh, should not execute
                mock_freshness_check.return_value = False

                with patch(
                    "trackrat.collectors.njt.discovery.TrainDiscoveryCollector"
                ) as MockCollector:
                    await scheduler_service.run_njt_discovery()

                # Verify discovery collector was NOT created
                MockCollector.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_journey_updates_processes_all_trains(self, scheduler_service):
        """Test journey update check processes trains correctly."""
        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            # Mock the schedule methods
            with patch.object(
                scheduler_service, "schedule_departure_collections"
            ) as mock_dep_coll:
                with patch.object(
                    scheduler_service, "schedule_periodic_updates"
                ) as mock_periodic:

                    with patch(
                        "trackrat.services.scheduler.run_with_freshness_check"
                    ) as mock_freshness_check:
                        # Make freshness check actually call the task function
                        async def execute_task_func(
                            db, task_name, minimum_interval_seconds, task_func
                        ):
                            await task_func()
                            return True

                        mock_freshness_check.side_effect = execute_task_func

                        await scheduler_service.check_journey_updates()

                        # Verify scheduling methods were called
                        mock_dep_coll.assert_called_once()
                        mock_periodic.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_live_activities_sends_notifications(
        self, scheduler_service, mock_apns_service
    ):
        """Test live activity updates send push notifications."""
        scheduler_service.apns_service = mock_apns_service

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            # Need to patch the synchronous database access used in update_live_activities
            # These are imported inside the function, so we patch at the sqlalchemy level
            with patch("sqlalchemy.create_engine") as mock_create_engine:
                with patch("sqlalchemy.orm.sessionmaker") as mock_sessionmaker:
                    # Mock sync session and engine
                    mock_sync_session = Mock()
                    mock_sync_engine = Mock()
                    mock_create_engine.return_value = mock_sync_engine
                    mock_sessionmaker.return_value = Mock(
                        return_value=mock_sync_session
                    )

                    # Mock active tokens
                    mock_token = Mock(
                        push_token="token1",
                        activity_id="activity1",
                        train_number="1234",
                        origin_code="NY",
                        destination_code="TR",
                        expires_at=datetime.now(UTC) + timedelta(hours=1),
                        is_active=True,
                    )

                    mock_tokens_result = Mock()
                    mock_tokens_result.scalars.return_value = [mock_token]

                    # Mock journey
                    mock_journey = Mock(
                        train_id="1234",
                        observation_type="OBSERVED",
                        is_cancelled=False,
                        is_completed=False,
                        last_updated_at=datetime.now(UTC),
                        stops=[],
                    )

                    # Setup sync session execute and scalar methods
                    mock_sync_session.execute.return_value = mock_tokens_result
                    mock_sync_session.scalar.return_value = mock_journey
                    mock_sync_session.__enter__ = Mock(return_value=mock_sync_session)
                    mock_sync_session.__exit__ = Mock(return_value=None)

                    # Mock the content state calculation
                    with patch.object(
                        scheduler_service, "_calculate_live_activity_content_state"
                    ) as mock_calc_content:
                        mock_calc_content.return_value = {"test": "content"}

                        with patch(
                            "trackrat.services.scheduler.run_with_freshness_check"
                        ) as mock_freshness_check:
                            # Make freshness check actually call the task function
                            async def execute_task_func(
                                db, task_name, minimum_interval_seconds, task_func
                            ):
                                await task_func()
                                return True

                            mock_freshness_check.side_effect = execute_task_func

                            await scheduler_service.update_live_activities()

                            # Verify APNS service was called
                            mock_apns_service.send_live_activity_update.assert_called_once_with(
                                "token1", {"test": "content"}
                            )

    @pytest.mark.asyncio
    async def test_precompute_congestion_cache(self, scheduler_service):
        """Test congestion cache pre-computation."""
        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            with patch(
                "trackrat.services.api_cache.ApiCacheService"
            ) as MockCacheService:
                mock_cache = AsyncMock()
                mock_cache.precompute_congestion_responses.return_value = None
                mock_cache.cleanup_expired_cache.return_value = 5
                MockCacheService.return_value = mock_cache

                with patch(
                    "trackrat.services.scheduler.run_with_freshness_check"
                ) as mock_freshness_check:
                    # Make freshness check actually call the task function
                    async def execute_task_func(
                        db, task_name, minimum_interval_seconds, task_func
                    ):
                        await task_func()
                        return True

                    mock_freshness_check.side_effect = execute_task_func

                    await scheduler_service.precompute_congestion_cache()

                    # Verify cache service was used
                    MockCacheService.assert_called_once()
                    mock_cache.precompute_congestion_responses.assert_called_once()
                    mock_cache.cleanup_expired_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_train_validation(self, scheduler_service):
        """Test train validation execution."""
        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            with patch(
                "trackrat.services.validation.TrainValidationService"
            ) as MockValidationService:
                mock_validation = AsyncMock()
                mock_validation.run_validation.return_value = [
                    Mock(missing_trains=[], route="NY-TR"),
                    Mock(missing_trains=["123"], route="NY-PJ"),
                ]
                MockValidationService.return_value = mock_validation

                # Mock context manager
                MockValidationService.return_value.__aenter__ = AsyncMock(
                    return_value=mock_validation
                )
                MockValidationService.return_value.__aexit__ = AsyncMock(
                    return_value=None
                )

                with patch(
                    "trackrat.services.scheduler.run_with_freshness_check"
                ) as mock_freshness_check:
                    # Make freshness check actually call the task function
                    async def execute_task_func(
                        db, task_name, minimum_interval_seconds, task_func
                    ):
                        await task_func()
                        return True

                    mock_freshness_check.side_effect = execute_task_func

                    await scheduler_service.run_train_validation()

                    # Verify validation service was used
                    MockValidationService.assert_called_once_with(
                        scheduler_service.settings
                    )
                    mock_validation.run_validation.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_njt_schedules(self, scheduler_service):
        """Test NJT schedule collection."""
        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            with patch(
                "trackrat.services.scheduler.NJTScheduleCollector"
            ) as MockScheduleCollector:
                mock_collector = AsyncMock()
                mock_collector.collect_all_schedules.return_value = {
                    "total_schedules": 500,
                    "new_schedules": 450,
                }
                MockScheduleCollector.return_value = mock_collector

                # Mock NJT client
                scheduler_service.njt_client = AsyncMock()

                with patch(
                    "trackrat.services.scheduler.run_with_freshness_check"
                ) as mock_freshness_check:
                    # Make freshness check actually call the task function
                    async def execute_task_func(
                        db, task_name, minimum_interval_seconds, task_func
                    ):
                        await task_func()
                        return True

                    mock_freshness_check.side_effect = execute_task_func

                    await scheduler_service.collect_njt_schedules()

                    # Verify schedule collector was used
                    MockScheduleCollector.assert_called_once_with(
                        scheduler_service.njt_client
                    )
                    mock_collector.collect_all_schedules.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_amtrak_schedules(self, scheduler_service):
        """Test Amtrak pattern-based schedule generation."""
        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            with patch(
                "trackrat.services.scheduler.AmtrakPatternScheduler"
            ) as MockPatternScheduler:
                mock_scheduler = AsyncMock()
                mock_scheduler.generate_daily_schedules.return_value = {
                    "created": 100,
                    "updated": 10,
                    "skipped": 5,
                    "errors": 0,
                }
                mock_scheduler.cleanup_old_scheduled_records.return_value = 20
                MockPatternScheduler.return_value = mock_scheduler

                with patch(
                    "trackrat.services.scheduler.run_with_freshness_check"
                ) as mock_freshness_check:
                    # Make freshness check actually call the task function
                    async def execute_task_func(
                        db, task_name, minimum_interval_seconds, task_func
                    ):
                        await task_func()
                        return True

                    mock_freshness_check.side_effect = execute_task_func

                    await scheduler_service.generate_amtrak_schedules()

                    # Verify pattern scheduler was used
                    MockPatternScheduler.assert_called_once()
                    # Should be called twice (today and tomorrow)
                    assert mock_scheduler.generate_daily_schedules.call_count == 2
                    mock_scheduler.cleanup_old_scheduled_records.assert_called_once()

    @pytest.mark.asyncio
    async def test_scheduler_handles_task_exceptions(self, scheduler_service):
        """Test that scheduler handles exceptions in tasks gracefully."""
        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            with patch(
                "trackrat.services.scheduler.TrainDiscoveryCollector"
            ) as MockCollector:
                # Make the collector raise an exception
                mock_collector = AsyncMock()
                mock_collector.run.side_effect = RuntimeError("Task failed!")
                MockCollector.return_value = mock_collector

                # Mock NJT client
                scheduler_service.njt_client = AsyncMock()

                with patch(
                    "trackrat.services.scheduler.run_with_freshness_check"
                ) as mock_freshness_check:
                    # Make freshness check actually call the task function
                    async def execute_task_func(
                        db, task_name, minimum_interval_seconds, task_func
                    ):
                        # The task func should handle the exception internally
                        await task_func()
                        return True

                    mock_freshness_check.side_effect = execute_task_func

                    # The task will re-raise the exception
                    with pytest.raises(RuntimeError, match="Task failed!"):
                        await scheduler_service.run_njt_discovery()

                    # Verify freshness check was still attempted
                    mock_freshness_check.assert_called_once()
                    # Verify collector was called and raised the exception
                    MockCollector.assert_called_once()

    @pytest.mark.asyncio
    async def test_scheduler_status_method(self, scheduler_service):
        """Test get_status method returns correct scheduler information."""
        # Add some mock jobs
        with patch.object(scheduler_service.scheduler, "get_jobs") as mock_get_jobs:
            mock_job1 = Mock()
            mock_job1.id = "njt_discovery"
            mock_job1.name = "NJT Discovery"
            mock_job1.next_run_time = datetime.now(UTC) + timedelta(minutes=10)

            mock_job2 = Mock()
            mock_job2.id = "journey_updates"
            mock_job2.name = "Journey Updates"
            mock_job2.next_run_time = datetime.now(UTC) + timedelta(minutes=5)

            mock_get_jobs.return_value = [mock_job1, mock_job2]

            # Mock running state - use property mock
            with patch.object(
                type(scheduler_service.scheduler),
                "running",
                new_callable=lambda: property(lambda self: True),
            ):
                status = scheduler_service.get_status()

            assert status["running"] is True
            assert status["jobs_count"] == 2
            assert len(status["active_tasks"]) == 0  # No running tasks

            # Add a running task
            mock_task = Mock(spec=asyncio.Task)
            mock_task.done.return_value = False
            scheduler_service._running_tasks["test_task"] = mock_task

            status = scheduler_service.get_status()
            assert len(status["active_tasks"]) == 1
            assert "test_task" in status["active_tasks"]


class TestSchedulerHorizontalScaling:
    """Test cases for horizontal scaling coordination."""

    @pytest.mark.asyncio
    async def test_multiple_replicas_coordinate(self):
        """Test that multiple scheduler replicas coordinate properly."""
        settings = Settings(
            njt_api_token="test",
            discovery_interval_minutes=30,
        )

        # Create two scheduler instances (simulating two replicas)
        scheduler1 = SchedulerService(settings)
        scheduler2 = SchedulerService(settings)

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db1 = AsyncMock()
            mock_db2 = AsyncMock()

            # Simulate first replica getting the lock
            mock_get_session.side_effect = [
                AsyncMock(__aenter__=AsyncMock(return_value=mock_db1)),
                AsyncMock(__aenter__=AsyncMock(return_value=mock_db2)),
            ]

            with patch(
                "trackrat.services.scheduler.run_with_freshness_check"
            ) as mock_freshness:
                # First replica executes, second is blocked
                mock_freshness.side_effect = [True, False]

                # Both try to run discovery
                result1 = await scheduler1.run_njt_discovery()
                result2 = await scheduler2.run_njt_discovery()

                # Verify freshness check was called twice
                assert mock_freshness.call_count == 2

    @pytest.mark.asyncio
    async def test_safe_interval_calculation_prevents_overlap(self):
        """Test that safe interval calculation prevents task overlap."""
        from trackrat.utils.scheduler_utils import calculate_safe_interval

        # 30-minute task should have ~27-minute safe interval
        interval = calculate_safe_interval(30)
        assert interval == 1620  # (30 - 3) * 60

        # 5-minute task should have 3-minute safe interval
        interval = calculate_safe_interval(5)
        assert interval == 180  # (5 - 2) * 60

        # 60-minute task should have 54-minute safe interval
        interval = calculate_safe_interval(60)
        assert interval == 3240  # (60 - 6) * 60
