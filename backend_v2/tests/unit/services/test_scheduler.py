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

from trackrat.services.apns import ApnsSendResult
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
                ("path_collection", IntervalTrigger, {"minutes": 4}),
                ("lirr_collection", IntervalTrigger, {"minutes": 4}),
                ("mnr_collection", IntervalTrigger, {"minutes": 4}),
                ("subway_collection", IntervalTrigger, {"minutes": 4}),
                ("metra_collection", IntervalTrigger, {"minutes": 4}),
                ("wmata_collection", IntervalTrigger, {"minutes": 3}),
                ("bart_collection", IntervalTrigger, {"minutes": 4}),
                ("mbta_collection", IntervalTrigger, {"minutes": 4}),
                ("septa_rr_collection", IntervalTrigger, {"minutes": 4}),
                ("septa_metro_collection", IntervalTrigger, {"minutes": 4}),
                ("journey_update_check", IntervalTrigger, {"minutes": 5}),
                ("njt_journey_maintenance", IntervalTrigger, {"minutes": 15}),
                ("live_activity_updates", IntervalTrigger, {"minutes": 1}),
                ("live_activity_token_cleanup", IntervalTrigger, {"hours": 1}),
                ("congestion_cache_precompute", IntervalTrigger, {"minutes": 15}),
                ("resource_usage_check", IntervalTrigger, {"minutes": 15}),
                ("departure_cache_precompute", IntervalTrigger, {"seconds": 90}),
                ("route_history_cache_precompute", IntervalTrigger, {"minutes": 5}),
                ("train_validation", IntervalTrigger, {"hours": 1}),
                ("njt_schedule_collection", CronTrigger, {"hour": 0, "minute": 30}),
                ("amtrak_schedule_generation", CronTrigger, {"hour": 0, "minute": 45}),
                ("lock_manager_cleanup", CronTrigger, {"hour": 1, "minute": 0}),
                ("gtfs_feed_refresh", CronTrigger, {"hour": 3, "minute": 0}),
                ("route_alert_evaluation", IntervalTrigger, {"minutes": 5}),
                ("morning_digest_evaluation", IntervalTrigger, {"minutes": 5}),
                ("service_alerts_collection", IntervalTrigger, {"minutes": 15}),
                ("retention_cleanup", CronTrigger, {"hour": 3, "minute": 30}),
                ("legacy_partition_backfill", IntervalTrigger, {"minutes": 2}),
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
    async def test_stagger_and_jitter_configuration(self, scheduler_service):
        """Verify that interval jobs are staggered to prevent thundering herd.

        The 4-minute collectors (PATH/LIRR/MNR/Subway) must be staggered apart
        so they don't all fire simultaneously and spike CPU/network. This test
        catches regressions to the stagger offsets and jitter values.
        """
        with patch("trackrat.services.scheduler.NJTransitClient") as MockNJTClient:
            MockNJTClient.return_value = AsyncMock()

            # Let real add_job execute so we can inspect triggers;
            # only mock start() so the scheduler doesn't fire
            with patch.object(scheduler_service.scheduler, "start"):
                with patch("asyncio.create_task"):
                    await scheduler_service.start()

        jobs = {job.id: job for job in scheduler_service.scheduler.get_jobs()}

        # --- 4-minute collector stagger group ---
        # PATH has no start_date offset (fires at T+0)
        # LIRR, MNR, Subway, MBTA, SEPTA_RR, SEPTA_METRO are staggered from PATH
        four_min_jobs = [
            "path_collection",
            "lirr_collection",
            "mnr_collection",
            "subway_collection",
            "metra_collection",
            "bart_collection",
            "mbta_collection",
            "septa_rr_collection",
            "septa_metro_collection",
        ]
        for job_id in four_min_jobs:
            trigger = jobs[job_id].trigger
            assert trigger.interval == timedelta(
                minutes=4
            ), f"{job_id}: expected 4-min interval, got {trigger.interval}"
            assert (
                trigger.jitter == 30
            ), f"{job_id}: expected jitter=30, got {trigger.jitter}"

        # Verify stagger offsets between explicitly staggered collectors.
        # PATH has no explicit start_date (APScheduler auto-assigns), so we
        # verify the 1-minute spacing between LIRR, MNR, and Subway which
        # all use now + offset.
        lirr_start = jobs["lirr_collection"].trigger.start_date
        mnr_start = jobs["mnr_collection"].trigger.start_date
        subway_start = jobs["subway_collection"].trigger.start_date
        metra_start = jobs["metra_collection"].trigger.start_date
        bart_start = jobs["bart_collection"].trigger.start_date

        assert (mnr_start - lirr_start).total_seconds() == pytest.approx(60, abs=1)
        assert (subway_start - mnr_start).total_seconds() == pytest.approx(60, abs=1)
        assert (metra_start - subway_start).total_seconds() == pytest.approx(30, abs=1)
        assert (bart_start - metra_start).total_seconds() == pytest.approx(15, abs=1)

        # --- Discovery stagger group ---
        njt_disc = jobs["njt_train_discovery"].trigger
        amtrak_disc = jobs["amtrak_train_discovery"].trigger
        assert njt_disc.interval == timedelta(minutes=30)
        assert amtrak_disc.interval == timedelta(minutes=30)
        assert njt_disc.jitter == 60
        assert amtrak_disc.jitter == 60

        # Amtrak has explicit start_date of now+5min; verify the offset
        # is 5 minutes relative to LIRR's now+1min (i.e., 4 min apart)
        # to confirm both use the same `now` reference
        amtrak_start = amtrak_disc.start_date
        assert (amtrak_start - lirr_start).total_seconds() == pytest.approx(240, abs=1)

        # --- Verify all interval jobs have jitter > 0 ---
        for job_id, job in jobs.items():
            if isinstance(job.trigger, IntervalTrigger):
                assert (
                    job.trigger.jitter is not None and job.trigger.jitter > 0
                ), f"{job_id}: interval job missing jitter"

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
                        db, task_name, minimum_interval_seconds, task_func, **kwargs
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
                            db, task_name, minimum_interval_seconds, task_func, **kwargs
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
                        is_expired=False,
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
    async def test_update_live_activities_groups_by_data_source(
        self, scheduler_service, mock_apns_service
    ):
        """Issue #1050: tokens with the same train_number but different
        data_source must each get their own journey lookup. Otherwise the
        unfiltered journey query returns whichever row sorts first and both
        users get push updates for the wrong train."""
        scheduler_service.apns_service = mock_apns_service

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            with (
                patch("sqlalchemy.create_engine") as mock_create_engine,
                patch("sqlalchemy.orm.sessionmaker") as mock_sessionmaker,
            ):
                mock_sync_session = Mock()
                mock_create_engine.return_value = Mock()
                mock_sessionmaker.return_value = Mock(return_value=mock_sync_session)

                # Two tokens, same train_number, different transit systems.
                njt_token = Mock(
                    push_token="njt-tok",
                    activity_id="njt-act",
                    train_number="1989",
                    origin_code="NY",
                    destination_code="MP",
                    data_source="NJT",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    is_active=True,
                    track_notified_at=None,
                )
                amtrak_token = Mock(
                    push_token="amtrak-tok",
                    activity_id="amtrak-act",
                    train_number="1989",
                    origin_code="NYP",
                    destination_code="WAS",
                    data_source="AMTRAK",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    is_active=True,
                    track_notified_at=None,
                )

                mock_tokens_result = Mock()
                mock_tokens_result.scalars.return_value = [njt_token, amtrak_token]

                # Each scalar() call returns a journey shaped to the matching
                # data_source, so we can verify the right token gets the right
                # journey (verifying grouping AND filtering both worked).
                njt_journey = Mock(
                    train_id="1989",
                    data_source="NJT",
                    observation_type="OBSERVED",
                    is_cancelled=False,
                    is_completed=False,
                    is_expired=False,
                    last_updated_at=datetime.now(UTC),
                    stops=[],
                )
                amtrak_journey = Mock(
                    train_id="1989",
                    data_source="AMTRAK",
                    observation_type="OBSERVED",
                    is_cancelled=False,
                    is_completed=False,
                    is_expired=False,
                    last_updated_at=datetime.now(UTC),
                    stops=[],
                )

                mock_sync_session.execute.return_value = mock_tokens_result
                # First call (NJT group) returns NJT journey, second (AMTRAK) returns AMTRAK
                mock_sync_session.scalar.side_effect = [njt_journey, amtrak_journey]
                mock_sync_session.__enter__ = Mock(return_value=mock_sync_session)
                mock_sync_session.__exit__ = Mock(return_value=None)

                # Capture which (token, journey) pair the content-state calc sees.
                captured_pairs = []

                def capture_pair(journey, token, _session):
                    captured_pairs.append((token.data_source, journey.data_source))
                    return {"test": "content"}

                with patch.object(
                    scheduler_service,
                    "_calculate_live_activity_content_state",
                    side_effect=capture_pair,
                ):
                    with patch(
                        "trackrat.services.scheduler.run_with_freshness_check"
                    ) as mock_freshness_check:

                        async def execute_task_func(
                            db, task_name, minimum_interval_seconds, task_func
                        ):
                            await task_func()
                            return True

                        mock_freshness_check.side_effect = execute_task_func

                        await scheduler_service.update_live_activities()

                # Two groups => two journey lookups (the bug was a single lookup).
                assert mock_sync_session.scalar.call_count == 2

                # NJT token paired with NJT journey, AMTRAK with AMTRAK.
                # If grouping by data_source had been removed, both tokens
                # would share whichever journey was returned first.
                assert ("NJT", "NJT") in captured_pairs
                assert ("AMTRAK", "AMTRAK") in captured_pairs

    @pytest.mark.asyncio
    async def test_update_live_activities_does_not_end_on_is_expired_alone(
        self, scheduler_service, mock_apns_service
    ):
        """Regression: ``is_expired`` is a collector-side bookkeeping flag
        (e.g., NJT journey-mismatch validator false positives, MTA missing-
        from-feed timeouts) and can flip while the user's trip is still in
        progress. It must NOT cause an end push — only ``is_completed`` /
        ``is_cancelled`` should terminate a Live Activity."""
        scheduler_service.apns_service = mock_apns_service

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            with (
                patch("sqlalchemy.create_engine"),
                patch("sqlalchemy.orm.sessionmaker") as mock_sessionmaker,
            ):
                mock_sync_session = Mock()
                mock_sessionmaker.return_value = Mock(return_value=mock_sync_session)

                mock_token = Mock(
                    push_token="token-expired",
                    activity_id="activity-expired",
                    train_number="3943",
                    origin_code="NY",
                    destination_code="HL",
                    data_source="AMTRAK",  # bypass NJT track-assignment branch
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    is_active=True,
                    track_notified_at=datetime.now(UTC),
                )

                mock_tokens_result = Mock()
                mock_tokens_result.scalars.return_value = [mock_token]

                # Journey is flagged is_expired (e.g., by validator false
                # positive) but the trip itself is still in progress.
                mock_journey = Mock(
                    train_id="3943",
                    data_source="AMTRAK",
                    observation_type="OBSERVED",
                    is_cancelled=False,
                    is_completed=False,
                    is_expired=True,
                    last_updated_at=datetime.now(UTC),
                    stops=[],
                )

                mock_sync_session.execute.return_value = mock_tokens_result
                mock_sync_session.scalar.return_value = mock_journey
                mock_sync_session.__enter__ = Mock(return_value=mock_sync_session)
                mock_sync_session.__exit__ = Mock(return_value=None)

                with patch.object(
                    scheduler_service,
                    "_calculate_live_activity_content_state",
                    return_value={"test": "content"},
                ):
                    with patch(
                        "trackrat.services.scheduler.run_with_freshness_check"
                    ) as mock_freshness_check:

                        async def execute_task_func(
                            db, task_name, minimum_interval_seconds, task_func
                        ):
                            await task_func()
                            return True

                        mock_freshness_check.side_effect = execute_task_func

                        await scheduler_service.update_live_activities()

                # Update was sent; end was NOT sent.
                mock_apns_service.send_live_activity_update.assert_called_once_with(
                    "token-expired", {"test": "content"}
                )
                mock_apns_service.send_live_activity_end.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_live_activities_finds_journey_from_previous_day(
        self, scheduler_service, mock_apns_service
    ):
        """Issue #1211: PATH late-night journeys stamp ``journey_date`` from
        the *origin* departure, which sits on the previous ET calendar day
        for trains that begin in the late evening. The journey lookup used
        to filter ``journey_date == now_et().date()``, so once midnight ET
        rolled by the scheduler missed the still-active journey, logged
        ``journey_not_found_for_live_activity``, and silently stopped push
        updates. iOS's ``staleDate`` then expired and the Live Activity
        froze until the user opened the train details page (which forces a
        JIT refresh and locally re-arms the activity).

        The fix: search a 2-day window (yesterday + today) and take the
        most recently updated row, ``ORDER BY journey_date DESC,
        last_updated_at DESC LIMIT 1``. This catches yesterday's PATH
        journey while ``journey_date <= today`` keeps tomorrow's
        pre-generated SCHEDULED rows from outranking today's OBSERVED one.

        This test captures the SQLAlchemy statement passed to
        ``scalar()``, compiles it, and asserts the WHERE clause shape and
        ORDER BY / LIMIT so a regression to an equality filter would
        fail loudly.
        """
        scheduler_service.apns_service = mock_apns_service

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            with (
                patch("sqlalchemy.create_engine"),
                patch("sqlalchemy.orm.sessionmaker") as mock_sessionmaker,
            ):
                mock_sync_session = Mock()
                mock_sessionmaker.return_value = Mock(return_value=mock_sync_session)

                # Token for a PATH trip that started before midnight.
                mock_token = Mock(
                    push_token="path-token",
                    activity_id="path-act",
                    train_number="PATH_PNK_worldtrad_1778979000",
                    origin_code="PNK",
                    destination_code="PWC",
                    data_source="PATH",
                    expires_at=datetime.now(UTC) + timedelta(hours=4),
                    is_active=True,
                    track_notified_at=None,
                )

                mock_tokens_result = Mock()
                mock_tokens_result.scalars.return_value = [mock_token]

                # Mocked journey row with journey_date = yesterday — the
                # bug condition. Before the fix, the lookup's equality
                # filter on today's date would miss this entirely and the
                # scalar() result would be None.
                mock_journey = Mock(
                    train_id="PATH_PNK_worldtrad_1778979000",
                    data_source="PATH",
                    observation_type="OBSERVED",
                    is_cancelled=False,
                    is_completed=False,
                    is_expired=False,
                    last_updated_at=datetime.now(UTC),
                    stops=[],
                )

                captured_statements: list = []

                def capture_stmt(stmt):
                    captured_statements.append(stmt)
                    return mock_journey

                mock_sync_session.execute.return_value = mock_tokens_result
                mock_sync_session.scalar.side_effect = capture_stmt
                mock_sync_session.__enter__ = Mock(return_value=mock_sync_session)
                mock_sync_session.__exit__ = Mock(return_value=None)

                with patch.object(
                    scheduler_service,
                    "_calculate_live_activity_content_state",
                    return_value={"test": "content"},
                ):
                    with patch(
                        "trackrat.services.scheduler.run_with_freshness_check"
                    ) as mock_freshness_check:

                        async def execute_task_func(
                            db, task_name, minimum_interval_seconds, task_func
                        ):
                            await task_func()
                            return True

                        mock_freshness_check.side_effect = execute_task_func

                        await scheduler_service.update_live_activities()

                # Exactly one journey lookup happened, and it received an
                # update push (not an end push, because is_completed is False).
                assert len(captured_statements) == 1
                mock_apns_service.send_live_activity_update.assert_called_once()
                mock_apns_service.send_live_activity_end.assert_not_called()

                # Compile the captured SELECT and assert its shape:
                # - WHERE clause uses ``>=`` AND ``<=`` on journey_date,
                #   spanning at least two distinct dates (i.e. a range, not
                #   an equality)
                # - ORDER BY includes journey_date DESC and
                #   last_updated_at DESC
                # - LIMIT 1
                compiled = str(
                    captured_statements[0].compile(
                        compile_kwargs={"literal_binds": True}
                    )
                ).lower()

                assert "journey_date >=" in compiled, (
                    "Expected a lower-bound on journey_date; the bug was a "
                    "strict equality filter that missed previous-day rows. "
                    f"Compiled SQL: {compiled}"
                )
                assert "journey_date <=" in compiled, (
                    "Expected an upper-bound on journey_date to keep "
                    "tomorrow's pre-generated SCHEDULED rows out. "
                    f"Compiled SQL: {compiled}"
                )
                # No exact-equality on journey_date.
                assert "journey_date = " not in compiled, (
                    "Regression: lookup is back to a single-date equality. "
                    f"Compiled SQL: {compiled}"
                )
                # Most-recent-first ordering with LIMIT 1.
                assert "order by" in compiled
                assert "journey_date desc" in compiled
                assert "last_updated_at desc" in compiled
                assert "limit 1" in compiled

    @pytest.mark.asyncio
    async def test_update_live_activities_ends_on_is_completed(
        self, scheduler_service, mock_apns_service
    ):
        """``is_completed`` must still terminate a Live Activity."""
        scheduler_service.apns_service = mock_apns_service

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            with (
                patch("sqlalchemy.create_engine"),
                patch("sqlalchemy.orm.sessionmaker") as mock_sessionmaker,
            ):
                mock_sync_session = Mock()
                mock_sessionmaker.return_value = Mock(return_value=mock_sync_session)

                mock_token = Mock(
                    push_token="token-done",
                    activity_id="activity-done",
                    train_number="3943",
                    origin_code="NY",
                    destination_code="HL",
                    data_source="AMTRAK",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    is_active=True,
                    track_notified_at=datetime.now(UTC),
                )

                mock_tokens_result = Mock()
                mock_tokens_result.scalars.return_value = [mock_token]

                mock_journey = Mock(
                    train_id="3943",
                    data_source="AMTRAK",
                    observation_type="OBSERVED",
                    is_cancelled=False,
                    is_completed=True,
                    is_expired=False,
                    last_updated_at=datetime.now(UTC),
                    stops=[],
                )

                mock_sync_session.execute.return_value = mock_tokens_result
                mock_sync_session.scalar.return_value = mock_journey
                mock_sync_session.__enter__ = Mock(return_value=mock_sync_session)
                mock_sync_session.__exit__ = Mock(return_value=None)

                with patch.object(
                    scheduler_service,
                    "_calculate_live_activity_content_state",
                    return_value={"test": "content"},
                ):
                    with patch(
                        "trackrat.services.scheduler.run_with_freshness_check"
                    ) as mock_freshness_check:

                        async def execute_task_func(
                            db, task_name, minimum_interval_seconds, task_func
                        ):
                            await task_func()
                            return True

                        mock_freshness_check.side_effect = execute_task_func

                        await scheduler_service.update_live_activities()

                mock_apns_service.send_live_activity_end.assert_called_once()
                mock_apns_service.send_live_activity_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_transient_apns_failure_does_not_deactivate_token(
        self, scheduler_service, mock_apns_service
    ):
        """Transient APNS failures (5xx, timeouts, network) must NOT deactivate
        the Live Activity token. Only a 410 BadDeviceToken response should.

        Regression: production was permanently killing Live Activities on every
        transient APNS hiccup because the scheduler treated any non-success
        return as 410.
        """
        scheduler_service.apns_service = mock_apns_service
        mock_apns_service.send_live_activity_update = AsyncMock(
            return_value=ApnsSendResult.TRANSIENT_FAILURE
        )

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            with (
                patch("sqlalchemy.create_engine"),
                patch("sqlalchemy.orm.sessionmaker") as mock_sessionmaker,
            ):
                mock_sync_session = Mock()
                mock_sessionmaker.return_value = Mock(return_value=mock_sync_session)

                mock_token = Mock(
                    push_token="token-transient",
                    activity_id="activity-transient",
                    train_number="1234",
                    origin_code="NY",
                    destination_code="TR",
                    data_source="AMTRAK",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    is_active=True,
                    track_notified_at=datetime.now(UTC),
                )

                mock_tokens_result = Mock()
                mock_tokens_result.scalars.return_value = [mock_token]

                mock_journey = Mock(
                    train_id="1234",
                    data_source="AMTRAK",
                    observation_type="OBSERVED",
                    is_cancelled=False,
                    is_completed=False,
                    is_expired=False,
                    last_updated_at=datetime.now(UTC),
                    stops=[],
                )

                mock_sync_session.execute.return_value = mock_tokens_result
                mock_sync_session.scalar.return_value = mock_journey
                mock_sync_session.__enter__ = Mock(return_value=mock_sync_session)
                mock_sync_session.__exit__ = Mock(return_value=None)

                with patch.object(
                    scheduler_service,
                    "_calculate_live_activity_content_state",
                    return_value={"test": "content"},
                ):
                    with patch(
                        "trackrat.services.scheduler.run_with_freshness_check"
                    ) as mock_freshness_check:

                        async def execute_task_func(
                            db, task_name, minimum_interval_seconds, task_func
                        ):
                            await task_func()
                            return True

                        mock_freshness_check.side_effect = execute_task_func

                        await scheduler_service.update_live_activities()

                mock_apns_service.send_live_activity_update.assert_called_once_with(
                    "token-transient", {"test": "content"}
                )
                # Token must remain active so the next scheduler tick retries.
                assert mock_token.is_active is True

    @pytest.mark.asyncio
    async def test_invalid_token_response_deactivates_token(
        self, scheduler_service, mock_apns_service
    ):
        """A 410 BadDeviceToken response must deactivate the token so the
        scheduler stops trying to push to it."""
        scheduler_service.apns_service = mock_apns_service
        mock_apns_service.send_live_activity_update = AsyncMock(
            return_value=ApnsSendResult.INVALID_TOKEN
        )

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            with (
                patch("sqlalchemy.create_engine"),
                patch("sqlalchemy.orm.sessionmaker") as mock_sessionmaker,
            ):
                mock_sync_session = Mock()
                mock_sessionmaker.return_value = Mock(return_value=mock_sync_session)

                mock_token = Mock(
                    push_token="token-invalid",
                    activity_id="activity-invalid",
                    train_number="1234",
                    origin_code="NY",
                    destination_code="TR",
                    data_source="AMTRAK",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    is_active=True,
                    track_notified_at=datetime.now(UTC),
                )

                mock_tokens_result = Mock()
                mock_tokens_result.scalars.return_value = [mock_token]

                mock_journey = Mock(
                    train_id="1234",
                    data_source="AMTRAK",
                    observation_type="OBSERVED",
                    is_cancelled=False,
                    is_completed=False,
                    is_expired=False,
                    last_updated_at=datetime.now(UTC),
                    stops=[],
                )

                mock_sync_session.execute.return_value = mock_tokens_result
                mock_sync_session.scalar.return_value = mock_journey
                mock_sync_session.__enter__ = Mock(return_value=mock_sync_session)
                mock_sync_session.__exit__ = Mock(return_value=None)

                with patch.object(
                    scheduler_service,
                    "_calculate_live_activity_content_state",
                    return_value={"test": "content"},
                ):
                    with patch(
                        "trackrat.services.scheduler.run_with_freshness_check"
                    ) as mock_freshness_check:

                        async def execute_task_func(
                            db, task_name, minimum_interval_seconds, task_func
                        ):
                            await task_func()
                            return True

                        mock_freshness_check.side_effect = execute_task_func

                        await scheduler_service.update_live_activities()

                assert mock_token.is_active is False

    @pytest.mark.asyncio
    async def test_transient_apns_failure_on_end_does_not_deactivate_token(
        self, scheduler_service, mock_apns_service
    ):
        """End-path symmetry with the update path: a transient APNS failure
        on the END push must NOT flip is_active=False, otherwise the next
        scheduler tick won't retry and the user's Live Activity stays on the
        lock screen until iOS auto-expires it (8–12h). Only SUCCESS or
        INVALID_TOKEN should retire the token.
        """
        scheduler_service.apns_service = mock_apns_service
        mock_apns_service.send_live_activity_end = AsyncMock(
            return_value=ApnsSendResult.TRANSIENT_FAILURE
        )

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            with (
                patch("sqlalchemy.create_engine"),
                patch("sqlalchemy.orm.sessionmaker") as mock_sessionmaker,
            ):
                mock_sync_session = Mock()
                mock_sessionmaker.return_value = Mock(return_value=mock_sync_session)

                mock_token = Mock(
                    push_token="token-end-transient",
                    activity_id="activity-end-transient",
                    train_number="3943",
                    origin_code="NY",
                    destination_code="HL",
                    data_source="AMTRAK",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    is_active=True,
                    track_notified_at=datetime.now(UTC),
                )

                mock_tokens_result = Mock()
                mock_tokens_result.scalars.return_value = [mock_token]

                # is_completed=True triggers the end path
                mock_journey = Mock(
                    train_id="3943",
                    data_source="AMTRAK",
                    observation_type="OBSERVED",
                    is_cancelled=False,
                    is_completed=True,
                    is_expired=False,
                    last_updated_at=datetime.now(UTC),
                    stops=[],
                )

                mock_sync_session.execute.return_value = mock_tokens_result
                mock_sync_session.scalar.return_value = mock_journey
                mock_sync_session.__enter__ = Mock(return_value=mock_sync_session)
                mock_sync_session.__exit__ = Mock(return_value=None)

                with patch.object(
                    scheduler_service,
                    "_calculate_live_activity_content_state",
                    return_value={"test": "content"},
                ):
                    with patch(
                        "trackrat.services.scheduler.run_with_freshness_check"
                    ) as mock_freshness_check:

                        async def execute_task_func(
                            db, task_name, minimum_interval_seconds, task_func
                        ):
                            await task_func()
                            return True

                        mock_freshness_check.side_effect = execute_task_func

                        await scheduler_service.update_live_activities()

                mock_apns_service.send_live_activity_end.assert_called_once()
                # Token must remain active so the next scheduler tick retries
                # the end push instead of leaving the activity dangling on the
                # lock screen.
                assert mock_token.is_active is True

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
                        db, task_name, minimum_interval_seconds, task_func, **kwargs
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
                        db, task_name, minimum_interval_seconds, task_func, **kwargs
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
                        db, task_name, minimum_interval_seconds, task_func, **kwargs
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
                        db, task_name, minimum_interval_seconds, task_func, **kwargs
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
                        db, task_name, minimum_interval_seconds, task_func, **kwargs
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


class TestCollectJourneyLogging:
    """Test that collect_journey logs at appropriate levels based on
    _collect_single_njt_journey_safe return values.

    Addresses issue #1122: benign expired/missing journeys were logged
    as journey.collection.failed (ERROR) instead of being skipped quietly.
    """

    @pytest.fixture
    def test_settings(self):
        return Settings(
            njt_api_token="test_token",
            discovery_interval_minutes=30,
            journey_update_interval_minutes=15,
            data_staleness_seconds=60,
            environment="testing",
        )

    @pytest.fixture
    def mock_apns_service(self):
        service = AsyncMock()
        service.send_update = AsyncMock()
        return service

    @pytest.fixture
    def scheduler_service(self, test_settings, mock_apns_service):
        with patch("trackrat.services.scheduler.NJTransitClient"):
            svc = SchedulerService(
                settings=test_settings, apns_service=mock_apns_service
            )
            svc.njt_client = AsyncMock()
            return svc

    @pytest.mark.asyncio
    async def test_collect_journey_logs_debug_on_success(self, scheduler_service):
        """Successful collection should log at DEBUG level."""
        result = {
            "train_id": "1234",
            "success": True,
            "is_completed": False,
            "stops_count": 5,
        }
        with patch.object(
            scheduler_service,
            "_collect_single_njt_journey_safe",
            return_value=result,
        ):
            with patch("trackrat.services.scheduler.logger") as mock_logger:
                await scheduler_service.collect_journey("1234", datetime(2026, 5, 7))
                mock_logger.debug.assert_any_call(
                    "journey.collection.completed",
                    train_id="1234",
                    is_completed=False,
                    stops_count=5,
                )
                mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_journey_logs_debug_on_skipped_expired(
        self, scheduler_service
    ):
        """Skipped (already expired) should log at DEBUG, not ERROR."""
        result = {
            "train_id": "47",
            "success": False,
            "skipped": True,
            "reason": "already_expired",
        }
        with patch.object(
            scheduler_service,
            "_collect_single_njt_journey_safe",
            return_value=result,
        ):
            with patch("trackrat.services.scheduler.logger") as mock_logger:
                await scheduler_service.collect_journey("47", datetime(2026, 5, 7))
                mock_logger.debug.assert_any_call(
                    "journey.collection.skipped",
                    train_id="47",
                    reason="already_expired",
                )
                mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_journey_logs_debug_on_skipped_not_found(
        self, scheduler_service
    ):
        """Skipped (journey not found) should log at DEBUG, not ERROR."""
        result = {
            "train_id": "49",
            "success": False,
            "skipped": True,
            "reason": "journey_not_found",
        }
        with patch.object(
            scheduler_service,
            "_collect_single_njt_journey_safe",
            return_value=result,
        ):
            with patch("trackrat.services.scheduler.logger") as mock_logger:
                await scheduler_service.collect_journey("49", datetime(2026, 5, 7))
                mock_logger.debug.assert_any_call(
                    "journey.collection.skipped",
                    train_id="49",
                    reason="journey_not_found",
                )
                mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_journey_logs_debug_on_skipped_disappeared(
        self, scheduler_service
    ):
        """Skipped (journey disappeared between phases) should log at DEBUG."""
        result = {
            "train_id": "535",
            "success": False,
            "skipped": True,
            "reason": "journey_disappeared",
        }
        with patch.object(
            scheduler_service,
            "_collect_single_njt_journey_safe",
            return_value=result,
        ):
            with patch("trackrat.services.scheduler.logger") as mock_logger:
                await scheduler_service.collect_journey("535", datetime(2026, 5, 7))
                mock_logger.debug.assert_any_call(
                    "journey.collection.skipped",
                    train_id="535",
                    reason="journey_disappeared",
                )
                mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_journey_logs_info_on_unsuccessful(self, scheduler_service):
        """Non-skipped unsuccessful result (e.g. TrainNotFoundError) logs INFO."""
        result = {
            "train_id": "5530",
            "success": False,
            "error": "Train not found",
            "expired": True,
        }
        with patch.object(
            scheduler_service,
            "_collect_single_njt_journey_safe",
            return_value=result,
        ):
            with patch("trackrat.services.scheduler.logger") as mock_logger:
                await scheduler_service.collect_journey("5530", datetime(2026, 5, 7))
                mock_logger.info.assert_any_call(
                    "journey.collection.unsuccessful",
                    train_id="5530",
                    error="Train not found",
                )
                mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_journey_logs_error_on_none(self, scheduler_service):
        """Genuine failure (None) should still log ERROR."""
        with patch.object(
            scheduler_service,
            "_collect_single_njt_journey_safe",
            return_value=None,
        ):
            with patch("trackrat.services.scheduler.logger") as mock_logger:
                await scheduler_service.collect_journey("9999", datetime(2026, 5, 7))
                mock_logger.error.assert_any_call(
                    "journey.collection.failed",
                    train_id="9999",
                    error="No result returned from collection",
                )


class TestCheckResourceUsage:
    """Tests for SchedulerService.check_resource_usage (issue #1344).

    Verifies the disk-usage and database-size structured log events that
    infra_v2/terraform/metrics.tf + monitoring.tf turn into Cloud Monitoring
    alerts, since the production data disk previously filled to 86% with
    no automated warning.
    """

    @pytest.fixture
    def test_settings(self):
        return Settings(
            njt_api_token="test_token",
            discovery_interval_minutes=30,
            journey_update_interval_minutes=15,
            data_staleness_seconds=60,
            environment="testing",
            data_disk_path="/mnt/disks/data",
        )

    @pytest.fixture
    def mock_apns_service(self):
        service = AsyncMock()
        service.send_update = AsyncMock()
        return service

    @pytest.fixture
    def scheduler_service(self, test_settings, mock_apns_service):
        with patch("trackrat.services.scheduler.NJTransitClient"):
            return SchedulerService(
                settings=test_settings, apns_service=mock_apns_service
            )

    @staticmethod
    def _session_context(session):
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    @staticmethod
    async def _run_task_func(db, task_name, minimum_interval_seconds, task_func):
        await task_func()
        return True

    @staticmethod
    def _empty_vacuum_result():
        """A pg_stat_user_tables query result with no monitored tables found."""
        result = Mock()
        result.mappings.return_value = []
        return result

    @pytest.mark.asyncio
    async def test_logs_disk_usage_and_database_size(self, scheduler_service):
        """A healthy check logs both the disk usage and DB size events."""
        freshness_session = AsyncMock()
        work_session = AsyncMock()
        db_size_result = Mock()
        db_size_result.scalar.return_value = 5368709120  # 5 GiB
        work_session.execute = AsyncMock(
            side_effect=[db_size_result, self._empty_vacuum_result()]
        )

        with (
            patch("trackrat.services.scheduler.get_session") as mock_get_session,
            patch("trackrat.services.scheduler.get_disk_usage") as mock_get_disk_usage,
            patch("trackrat.services.scheduler.logger") as mock_logger,
            patch(
                "trackrat.services.scheduler.run_with_freshness_check",
                side_effect=self._run_task_func,
            ) as mock_freshness,
        ):
            mock_get_session.side_effect = [
                self._session_context(freshness_session),
                self._session_context(work_session),
            ]
            mock_get_disk_usage.return_value = {
                "usage_percent": 86.2,
                "used_gb": 49.0,
                "total_gb": 59.0,
                "free_gb": 10.0,
            }

            await scheduler_service.check_resource_usage()

            mock_get_disk_usage.assert_called_once_with("/mnt/disks/data")
            mock_logger.info.assert_any_call(
                "data_disk_usage_check",
                usage_percent=86.2,
                used_gb=49.0,
                total_gb=59.0,
            )
            mock_logger.info.assert_any_call("database_size_check", size_gb=5.0)

            call_kwargs = mock_freshness.call_args.kwargs
            assert call_kwargs["task_name"] == "resource_usage_check"
            assert call_kwargs["minimum_interval_seconds"] == 780  # (15-2)*60

    @pytest.mark.asyncio
    async def test_warns_when_disk_path_unavailable(self, scheduler_service):
        """If the data disk mount isn't visible, warn instead of failing silently."""
        freshness_session = AsyncMock()
        work_session = AsyncMock()
        db_size_result = Mock()
        db_size_result.scalar.return_value = 0
        work_session.execute = AsyncMock(
            side_effect=[db_size_result, self._empty_vacuum_result()]
        )

        with (
            patch("trackrat.services.scheduler.get_session") as mock_get_session,
            patch("trackrat.services.scheduler.get_disk_usage", return_value={}),
            patch("trackrat.services.scheduler.logger") as mock_logger,
            patch(
                "trackrat.services.scheduler.run_with_freshness_check",
                side_effect=self._run_task_func,
            ),
        ):
            mock_get_session.side_effect = [
                self._session_context(freshness_session),
                self._session_context(work_session),
            ]

            await scheduler_service.check_resource_usage()

            mock_logger.warning.assert_any_call(
                "data_disk_usage_check_unavailable", path="/mnt/disks/data"
            )

    @pytest.mark.asyncio
    async def test_skipped_when_fresh(self, scheduler_service):
        """No disk/db work should happen when the freshness check says skip."""
        with (
            patch("trackrat.services.scheduler.get_session") as mock_get_session,
            patch("trackrat.services.scheduler.get_disk_usage") as mock_get_disk_usage,
            patch(
                "trackrat.services.scheduler.run_with_freshness_check",
                return_value=False,
            ),
        ):
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            await scheduler_service.check_resource_usage()

            mock_get_disk_usage.assert_not_called()

    @pytest.mark.asyncio
    async def test_logs_vacuum_health_for_monitored_tables(self, scheduler_service):
        """Logs per-table dead-tuple ratio and vacuum/analyze timestamps for
        the high-churn tables (issue #1359: journey_stops went its entire
        lifetime with zero completed vacuum/analyze passes, causing a stale
        visibility map that surfaced as production query timeouts).
        """
        freshness_session = AsyncMock()
        work_session = AsyncMock()
        db_size_result = Mock()
        db_size_result.scalar.return_value = 5368709120

        vacuum_result = Mock()
        vacuum_result.mappings.return_value = [
            {
                "table_name": "journey_stops",
                "n_live_tup": 71725,
                "n_dead_tup": 410613,
                "last_vacuum": None,
                "last_autovacuum": None,
                "last_analyze": None,
                "last_autoanalyze": None,
            },
            {
                "table_name": "train_journeys",
                "n_live_tup": 1614076,
                "n_dead_tup": 17666,
                "last_vacuum": None,
                "last_autovacuum": datetime(2026, 7, 3, 16, 34, 13, tzinfo=UTC),
                "last_analyze": None,
                "last_autoanalyze": datetime(2026, 7, 3, 16, 28, 12, tzinfo=UTC),
            },
        ]
        work_session.execute = AsyncMock(side_effect=[db_size_result, vacuum_result])

        with (
            patch("trackrat.services.scheduler.get_session") as mock_get_session,
            patch(
                "trackrat.services.scheduler.get_disk_usage",
                return_value={"usage_percent": 10.0, "used_gb": 1.0, "total_gb": 10.0},
            ),
            patch("trackrat.services.scheduler.logger") as mock_logger,
            patch(
                "trackrat.services.scheduler.run_with_freshness_check",
                side_effect=self._run_task_func,
            ),
        ):
            mock_get_session.side_effect = [
                self._session_context(freshness_session),
                self._session_context(work_session),
            ]

            await scheduler_service.check_resource_usage()

            # Bloated table: ~85% dead tuples, never vacuumed/analyzed.
            mock_logger.info.assert_any_call(
                "table_vacuum_health_check",
                table_name="journey_stops",
                dead_tuple_ratio_pct=85.13,
                live_tup=71725,
                dead_tup=410613,
                last_vacuum=None,
                last_autovacuum=None,
                last_analyze=None,
                last_autoanalyze=None,
            )
            # Healthy table: low dead ratio, autovacuum/autoanalyze current.
            mock_logger.info.assert_any_call(
                "table_vacuum_health_check",
                table_name="train_journeys",
                dead_tuple_ratio_pct=1.08,
                live_tup=1614076,
                dead_tup=17666,
                last_vacuum=None,
                last_autovacuum="2026-07-03T16:34:13+00:00",
                last_analyze=None,
                last_autoanalyze="2026-07-03T16:28:12+00:00",
            )

            call_kwargs = work_session.execute.call_args_list[1]
            assert call_kwargs.args[1] == {
                "table_names": list(SchedulerService.VACUUM_MONITORED_TABLES)
            }
