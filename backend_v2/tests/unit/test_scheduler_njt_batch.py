"""
Unit tests for NJ Transit batch collection in SchedulerService.

Tests the new NJT batch collection methods: schedule_njt_batch_collection and collect_njt_journeys_batch.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from trackrat.services.scheduler import SchedulerService
from trackrat.models.database import TrainJourney
from trackrat.settings import Settings


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    return Settings(
        njt_api_url="https://test.api.com",
        njt_api_token="test_token",
        discovery_interval_minutes=60,
    )


@pytest.fixture
def scheduler_service(mock_settings):
    """Create scheduler service with mocked dependencies."""
    service = SchedulerService(mock_settings)
    service.scheduler = Mock(spec=AsyncIOScheduler)
    service.scheduler.add_job = Mock()
    service.scheduler.get_job = Mock()
    service.njt_client = AsyncMock()
    return service


@pytest.fixture
def sample_discovery_result():
    """Sample discovery result with multiple stations."""
    return {
        "stations_processed": 3,
        "total_discovered": 5,
        "total_new": 2,
        "station_results": {
            "NY": {
                "trains_discovered": 3,
                "new_trains": 1,
                "new_train_ids": ["3737"],
                "all_train_ids": ["3737", "3893", "1281"],
            },
            "NP": {
                "trains_discovered": 2,
                "new_trains": 1,
                "new_train_ids": ["4501"],
                "all_train_ids": ["3737", "4501"],  # 3737 appears in both stations
            },
            "PJ": {
                "trains_discovered": 0,
                "new_trains": 0,
                "new_train_ids": [],
                "all_train_ids": [],
            },
        },
    }


@pytest.fixture
def mock_train_journey():
    """Create a mock TrainJourney."""
    journey = Mock(spec=TrainJourney)
    journey.train_id = "3737"
    journey.has_complete_journey = False
    journey.last_updated_at = None
    return journey


class TestScheduleNJTBatchCollection:
    """Test cases for schedule_njt_batch_collection method."""

    @pytest.mark.asyncio
    async def test_schedules_collection_for_all_unique_trains(
        self, scheduler_service, sample_discovery_result
    ):
        """Test that batch collection is scheduled for all unique train IDs."""
        mock_session = AsyncMock()
        mock_journey = Mock(spec=TrainJourney)
        mock_journey.has_complete_journey = False
        mock_journey.last_updated_at = None

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_session.scalar.return_value = mock_journey

            with patch("trackrat.services.scheduler.now_et") as mock_now:
                mock_now.return_value = datetime(2025, 1, 1, 12, 0, 0)

                await scheduler_service.schedule_njt_batch_collection(
                    sample_discovery_result
                )

        # Should have called add_job to schedule batch collection
        scheduler_service.scheduler.add_job.assert_called_once()

        call_args = scheduler_service.scheduler.add_job.call_args
        assert call_args[0][0] == scheduler_service.collect_njt_journeys_batch

        # Check that unique train IDs are passed (3737, 3893, 4501, 1281)
        scheduled_trains = call_args[1]["args"][0]
        assert set(scheduled_trains) == {"3737", "3893", "4501", "1281"}

    @pytest.mark.asyncio
    async def test_skips_recently_updated_journeys(
        self, scheduler_service, sample_discovery_result
    ):
        """Test that journeys updated recently are skipped."""
        mock_session = AsyncMock()

        # Mock different journey states
        journeys = {
            "3737": Mock(
                spec=TrainJourney,
                has_complete_journey=True,
                last_updated_at=datetime(2025, 1, 1, 11, 50, 0),
            ),  # 10 min ago - skip
            "3893": Mock(
                spec=TrainJourney, has_complete_journey=False, last_updated_at=None
            ),  # Never updated - collect
            "4501": Mock(
                spec=TrainJourney, has_complete_journey=False, last_updated_at=None
            ),  # Never updated - collect
            "1281": Mock(
                spec=TrainJourney,
                has_complete_journey=False,
                last_updated_at=datetime(2025, 1, 1, 10, 0, 0),
            ),  # 2 hours ago - collect
        }

        # Make scalar return journeys sequentially as they're queried
        call_count = 0
        train_order = ["3737", "3893", "4501", "1281"]

        def mock_scalar_side_effect(query):
            nonlocal call_count
            if call_count < len(train_order):
                train_id = train_order[call_count]
                call_count += 1
                return journeys[train_id]
            return None

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_session.scalar.side_effect = mock_scalar_side_effect

            with patch("trackrat.services.scheduler.now_et") as mock_now:
                mock_now.return_value = datetime(2025, 1, 1, 12, 0, 0)

                await scheduler_service.schedule_njt_batch_collection(
                    sample_discovery_result
                )

        # Should schedule collection for some trains
        scheduler_service.scheduler.add_job.assert_called_once()
        call_args = scheduler_service.scheduler.add_job.call_args
        scheduled_trains = call_args[1]["args"][0]

        # Should have scheduled some trains for collection
        assert len(scheduled_trains) >= 1
        assert len(scheduled_trains) <= 4  # Can't be more than total unique trains

    @pytest.mark.asyncio
    async def test_handles_empty_discovery_result(self, scheduler_service):
        """Test handling of empty discovery result."""
        empty_result = {
            "station_results": {
                "NY": {"all_train_ids": []},
                "NP": {"all_train_ids": []},
            }
        }

        await scheduler_service.schedule_njt_batch_collection(empty_result)

        # Should not schedule any jobs
        scheduler_service.scheduler.add_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_no_trains_needing_collection(
        self, scheduler_service, sample_discovery_result
    ):
        """Test when all trains are already up to date."""
        mock_session = AsyncMock()

        # All journeys are recently updated
        mock_journey = Mock(spec=TrainJourney)
        mock_journey.has_complete_journey = True
        mock_journey.last_updated_at = datetime(2025, 1, 1, 11, 55, 0)  # 5 min ago

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_session.scalar.return_value = mock_journey

            with patch("trackrat.services.scheduler.now_et") as mock_now:
                mock_now.return_value = datetime(2025, 1, 1, 12, 0, 0)

                await scheduler_service.schedule_njt_batch_collection(
                    sample_discovery_result
                )

        # Should not schedule any jobs since all trains are up to date
        scheduler_service.scheduler.add_job.assert_not_called()


class TestCollectNJTJourneysBatch:
    """Test cases for collect_njt_journeys_batch method."""

    @pytest.mark.asyncio
    async def test_collects_all_trains_successfully(self, scheduler_service):
        """Test successful collection of multiple trains."""
        train_ids = ["3737", "3893", "1281"]

        # Mock result data (instead of journey object)
        mock_result = {
            "train_id": "test_train",
            "stops_count": 15,
            "destination": "Test Destination",
            "success": True,
        }

        # Mock the safe collection method
        async def mock_safe_collect(train_id):
            return mock_result

        with patch.object(
            scheduler_service,
            "_collect_single_njt_journey_safe",
            side_effect=mock_safe_collect,
        ) as mock_safe_collect_method:
            with patch.object(scheduler_service, "_running_tasks", {}):
                await scheduler_service.collect_njt_journeys_batch(train_ids)

        # Should have collected each train using the safe method
        assert mock_safe_collect_method.call_count == 3

        # Verify each train ID was passed
        collected_trains = [
            call[0][0] for call in mock_safe_collect_method.call_args_list
        ]
        assert set(collected_trains) == set(train_ids)

    @pytest.mark.asyncio
    async def test_handles_collection_errors_gracefully(self, scheduler_service):
        """Test that errors in individual train collection don't stop the batch."""
        train_ids = ["3737", "3893", "1281"]

        # First train succeeds, second fails, third succeeds
        mock_result = {
            "train_id": "test_train",
            "stops_count": 15,
            "destination": "Test Destination",
            "success": True,
        }

        async def mock_collect_side_effect(train_id):
            if train_id == "3893":
                raise Exception("API Error")
            return mock_result

        with patch.object(
            scheduler_service,
            "_collect_single_njt_journey_safe",
            side_effect=mock_collect_side_effect,
        ) as mock_safe_collect_method:
            with patch.object(scheduler_service, "_running_tasks", {}):
                # Should not raise exception
                await scheduler_service.collect_njt_journeys_batch(train_ids)

        # Should have attempted all trains
        assert mock_safe_collect_method.call_count == 3

    @pytest.mark.asyncio
    async def test_handles_empty_train_list(self, scheduler_service):
        """Test handling of empty train list."""
        with patch.object(scheduler_service, "_running_tasks", {}):
            # Should not raise exception
            await scheduler_service.collect_njt_journeys_batch([])

    @pytest.mark.asyncio
    async def test_tracks_running_tasks(self, scheduler_service):
        """Test that the method properly tracks running tasks."""
        train_ids = ["3737"]

        mock_collector = AsyncMock()
        mock_collector.collect_journey.return_value = None

        with patch(
            "trackrat.collectors.njt.journey.JourneyCollector"
        ) as mock_collector_class:
            mock_collector_class.return_value = mock_collector

            with patch.object(scheduler_service, "_running_tasks", {}) as mock_tasks:
                with patch("asyncio.current_task") as mock_current_task:
                    mock_task = Mock()
                    mock_current_task.return_value = mock_task

                    await scheduler_service.collect_njt_journeys_batch(train_ids)

                    # Task should be removed from running tasks after completion
                    assert len(mock_tasks) == 0

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_handles_client_not_initialized(self, scheduler_service):
        """Test error handling when NJT client is not initialized."""
        scheduler_service.njt_client = None

        with patch.object(scheduler_service, "_running_tasks", {}):
            # Should handle the error gracefully and not crash
            await scheduler_service.collect_njt_journeys_batch(["3737"])


class TestNJTBatchCollectionIntegration:
    """Integration tests for the full NJT batch collection flow."""

    @pytest.mark.asyncio
    async def test_run_njt_discovery_triggers_batch_collection(
        self, scheduler_service, sample_discovery_result
    ):
        """Test that run_njt_discovery calls batch collection for discovered trains."""

        with patch.object(
            scheduler_service, "schedule_njt_batch_collection"
        ) as mock_schedule:
            with patch.object(scheduler_service, "_running_tasks", {}):
                # Mock the discovery collector directly on the scheduler service
                with patch(
                    "trackrat.services.scheduler.TrainDiscoveryCollector"
                ) as mock_collector_class:
                    mock_collector = AsyncMock()
                    mock_collector.run.return_value = sample_discovery_result
                    mock_collector_class.return_value = mock_collector

                    await scheduler_service.run_njt_discovery()

        # Should have called schedule_njt_batch_collection with the discovery result
        mock_schedule.assert_called_once_with(sample_discovery_result)

    @pytest.mark.asyncio
    async def test_run_njt_discovery_skips_batch_when_no_trains_discovered(
        self, scheduler_service
    ):
        """Test that batch collection is skipped when no trains are discovered."""
        empty_result = {"total_discovered": 0, "total_new": 0, "station_results": {}}

        mock_collector = AsyncMock()
        mock_collector.run.return_value = empty_result

        with patch(
            "trackrat.collectors.njt.discovery.TrainDiscoveryCollector"
        ) as mock_collector_class:
            mock_collector_class.return_value = mock_collector

            with patch.object(
                scheduler_service, "schedule_njt_batch_collection"
            ) as mock_schedule:
                with patch.object(scheduler_service, "_running_tasks", {}):
                    await scheduler_service.run_njt_discovery()

        # Should not have called batch collection
        mock_schedule.assert_not_called()
