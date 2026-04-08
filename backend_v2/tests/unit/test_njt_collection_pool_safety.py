"""
Tests for NJT journey collection connection pool safety.

Verifies that _collect_single_njt_journey_safe:
- Does not hold a DB connection while waiting for external NJT API responses
- Caps concurrent API calls via semaphore
- Uses the shared async collect_journey_details() path
- Properly classifies transient DB errors for retry
"""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, Mock, patch

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from tests.fixtures.njt_api_responses import StopBuilder, create_stop_list_response
from trackrat.models.database import TrainJourney
from trackrat.services.scheduler import SchedulerService
from trackrat.settings import Settings


@pytest.fixture
def mock_settings():
    return Settings(
        njt_api_url="https://test.api.com",
        njt_api_token="test_token",
        discovery_interval_minutes=60,
    )


@pytest.fixture
def scheduler_service(mock_settings):
    service = SchedulerService(mock_settings)
    service.scheduler = Mock(spec=AsyncIOScheduler)
    service.njt_client = AsyncMock()
    return service


def _make_journey_row(journey_id=1, is_expired=False, api_error_count=0):
    """Create a mock row matching the Phase 1 column query."""
    row = Mock()
    row.id = journey_id
    row.is_expired = is_expired
    row.api_error_count = api_error_count
    return row


def _make_train_data():
    """Create realistic NJT train stop list response."""
    builder = StopBuilder()
    stops = [
        builder.build_stop(
            "NY", "New York Penn", "11-Mar-2026 08:00:00 AM", departed=True, track="5"
        ),
        builder.build_stop(
            "NP", "Newark Penn", "11-Mar-2026 08:20:00 AM", departed=True
        ),
        builder.build_stop("TR", "Trenton", "11-Mar-2026 09:00:00 AM", departed=False),
    ]
    return create_stop_list_response("1234", stops=stops)


class TestSessionSplitting:
    """Verify DB sessions are NOT held during NJT API calls."""

    @pytest.mark.asyncio
    async def test_session_closed_before_api_call(self, scheduler_service):
        """Phase 1 (sync read) must complete and release its session BEFORE
        the NJT API call in Phase 2.  Phase 3 uses a separate async session."""

        session_open_during_api_call = False
        sync_session_active = False

        class TrackingSession:
            def __init__(self):
                self._execute_result = Mock()
                self._execute_result.first.return_value = _make_journey_row()

            def __enter__(self):
                nonlocal sync_session_active
                sync_session_active = True
                return self

            def __exit__(self, *args):
                nonlocal sync_session_active
                sync_session_active = False

            def execute(self, stmt):
                return self._execute_result

        class SessionMaker:
            def __call__(self):
                return TrackingSession()

        async def tracking_api_call(train_id):
            nonlocal session_open_during_api_call
            if sync_session_active:
                session_open_during_api_call = True
            return _make_train_data()

        scheduler_service.njt_client.get_train_stop_list = AsyncMock(
            side_effect=tracking_api_call
        )

        # Mock the async Phase 3 (get_session + collect_journey_details)
        mock_journey = Mock(spec=TrainJourney)
        mock_journey.is_completed = False
        mock_journey.stops_count = 3

        mock_async_session = AsyncMock()
        mock_async_session.scalar = AsyncMock(return_value=mock_journey)
        mock_async_session.commit = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_async_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("sqlalchemy.orm.sessionmaker", return_value=SessionMaker()),
            patch(
                "trackrat.services.scheduler.get_session", return_value=mock_ctx
            ),
            patch(
                "trackrat.collectors.njt.journey.JourneyCollector.collect_journey_details",
                new_callable=AsyncMock,
            ),
        ):
            result = await scheduler_service._collect_single_njt_journey_safe(
                "1234", date(2026, 3, 11)
            )

        assert result is not None, "Collection should succeed"
        assert not session_open_during_api_call, (
            "Sync session must be closed before NJT API call"
        )


class TestSemaphoreConcurrencyLimit:
    """Verify that concurrent NJT API calls are capped by a semaphore."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrent_api_calls(self, scheduler_service):
        """Max concurrent API calls should be limited by the semaphore."""
        max_concurrent = 0
        current_concurrent = 0

        async def slow_api_call(train_id):
            nonlocal max_concurrent, current_concurrent
            current_concurrent += 1
            max_concurrent = max(max_concurrent, current_concurrent)
            await asyncio.sleep(0.01)
            current_concurrent -= 1
            return _make_train_data()

        scheduler_service.njt_client.get_train_stop_list = AsyncMock(
            side_effect=slow_api_call
        )

        mock_journey = Mock(spec=TrainJourney)
        mock_journey.is_completed = False
        mock_journey.stops_count = 3

        mock_async_session = AsyncMock()
        mock_async_session.scalar = AsyncMock(return_value=mock_journey)
        mock_async_session.commit = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_async_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        # Phase 1 sync session
        phase1_result = Mock()
        phase1_result.first.return_value = _make_journey_row()

        class SimpleSession:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def execute(self, stmt):
                return phase1_result

        class SessionMaker:
            def __call__(self):
                return SimpleSession()

        with (
            patch("sqlalchemy.orm.sessionmaker", return_value=SessionMaker()),
            patch(
                "trackrat.services.scheduler.get_session", return_value=mock_ctx
            ),
            patch(
                "trackrat.collectors.njt.journey.JourneyCollector.collect_journey_details",
                new_callable=AsyncMock,
            ),
        ):
            tasks = [
                scheduler_service._collect_single_njt_journey_safe(
                    str(i), date(2026, 3, 11)
                )
                for i in range(20)
            ]
            results = await asyncio.gather(*tasks)

        successes = [r for r in results if r is not None and r.get("success")]
        assert len(successes) == 20, f"Expected 20 successes, got {len(successes)}"
        assert max_concurrent <= 10, (
            f"Max concurrent API calls was {max_concurrent}, should be <= 10"
        )


class TestCodePaths:
    """Test various code paths through _collect_single_njt_journey_safe."""

    @pytest.mark.asyncio
    async def test_successful_collection_returns_correct_data(
        self, scheduler_service
    ):
        """Successful collection should return result dict with expected fields."""
        train_data = _make_train_data()
        scheduler_service.njt_client.get_train_stop_list = AsyncMock(
            return_value=train_data
        )

        mock_journey = Mock(spec=TrainJourney)
        mock_journey.is_completed = False
        mock_journey.stops_count = 3

        mock_async_session = AsyncMock()
        mock_async_session.scalar = AsyncMock(return_value=mock_journey)
        mock_async_session.commit = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_async_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        phase1_result = Mock()
        phase1_result.first.return_value = _make_journey_row()

        class SimpleSession:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def execute(self, stmt):
                return phase1_result

        class SessionMaker:
            def __call__(self):
                return SimpleSession()

        with (
            patch("sqlalchemy.orm.sessionmaker", return_value=SessionMaker()),
            patch(
                "trackrat.services.scheduler.get_session", return_value=mock_ctx
            ),
            patch(
                "trackrat.collectors.njt.journey.JourneyCollector.collect_journey_details",
                new_callable=AsyncMock,
            ),
        ):
            result = await scheduler_service._collect_single_njt_journey_safe(
                "1234", date(2026, 3, 11)
            )

        assert result is not None
        assert result["success"] is True
        assert result["train_id"] == "1234"
        assert result["stops_count"] == 3
        assert result["destination"] == "Test Destination"

    @pytest.mark.asyncio
    async def test_transient_db_error_returns_retry_needed(self, scheduler_service):
        """Transient DB errors (e.g., serialization failure) should be flagged
        for retry via _is_postgresql_concurrency_error."""
        scheduler_service.njt_client.get_train_stop_list = AsyncMock(
            return_value=_make_train_data()
        )

        # Phase 1 sync session raises a serialization failure
        class FailSession:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def execute(self, stmt):
                raise Exception("serialization failure")

        class SessionMaker:
            def __call__(self):
                return FailSession()

        with patch("sqlalchemy.orm.sessionmaker", return_value=SessionMaker()):
            result = await scheduler_service._collect_single_njt_journey_safe(
                "1234", date(2026, 3, 11)
            )

        assert result is not None, (
            "Transient errors should return a result dict, not None"
        )
        assert result["retry_needed"] is True
        assert result["success"] is False
