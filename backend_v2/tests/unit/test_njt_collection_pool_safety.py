"""
Tests for NJT journey collection connection pool safety.

Verifies that _collect_single_njt_journey_safe does NOT hold a database connection
open while waiting for external NJT API responses, and that concurrent collections
are capped by a semaphore.
"""

import asyncio
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

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


def _make_journey_orm(journey_id=1, api_error_count=0, update_count=0):
    """Create a mock ORM TrainJourney for Phase 3 writes."""
    journey = Mock(spec=TrainJourney)
    journey.id = journey_id
    journey.api_error_count = api_error_count
    journey.update_count = update_count
    journey.is_completed = False
    journey.is_cancelled = False
    journey.cancellation_reason = None
    return journey


def _make_train_data():
    """Create realistic NJT train stop list response."""
    builder = StopBuilder()
    stops = [
        builder.build_stop("NY", "New York Penn", "11-Mar-2026 08:00:00 AM", departed=True, track="5"),
        builder.build_stop("NP", "Newark Penn", "11-Mar-2026 08:20:00 AM", departed=True),
        builder.build_stop("TR", "Trenton", "11-Mar-2026 09:00:00 AM", departed=False),
    ]
    return create_stop_list_response("1234", stops=stops)


class TestSessionSplitting:
    """Verify DB sessions are NOT held during NJT API calls."""

    @pytest.mark.asyncio
    async def test_session_closed_before_api_call(self, scheduler_service):
        """The sync DB session opened for Phase 1 (read) must be closed
        BEFORE the NJT API call in Phase 2.  This is the core fix for
        connection pool exhaustion."""

        session_open_during_api_call = False
        session_context_active = False

        class TrackingSession:
            """Session that tracks whether it's open during the API call."""

            def __init__(self):
                self._execute_result = Mock()
                self._execute_result.first.return_value = _make_journey_row()

            def __enter__(self):
                nonlocal session_context_active
                session_context_active = True
                return self

            def __exit__(self, *args):
                nonlocal session_context_active
                session_context_active = False

            def execute(self, stmt):
                return self._execute_result

            def get(self, model, pk):
                return _make_journey_orm()

            def add(self, obj):
                pass

            # no_autoflush context manager
            @property
            def no_autoflush(self):
                return MagicMock()

        call_count = [0]

        class TrackingSessionMaker:
            def __call__(self):
                call_count[0] += 1
                return TrackingSession()

        async def mock_api_call(train_id):
            """Capture whether any sync session is active during API call."""
            nonlocal session_open_during_api_call
            if session_context_active:
                session_open_during_api_call = True
            return _make_train_data()

        scheduler_service.njt_client.get_train_stop_list = mock_api_call

        with patch("trackrat.services.scheduler.commit_with_retry"):
            # Patch sessionmaker to return our tracking sessions
            with patch("sqlalchemy.orm.sessionmaker", return_value=TrackingSessionMaker()):
                result = await scheduler_service._collect_single_njt_journey_safe(
                    "1234", date(2026, 3, 11)
                )

        assert result is not None, "Collection should succeed"
        assert result["success"] is True
        assert not session_open_during_api_call, (
            "DB session was still open during NJT API call! "
            "This causes connection pool exhaustion under concurrent load."
        )
        # Phase 1 read + Phase 3 write = 2 separate sessions
        assert call_count[0] == 2, (
            f"Expected 2 separate session opens (read + write), got {call_count[0]}"
        )

    @pytest.mark.asyncio
    async def test_two_sessions_for_train_not_found(self, scheduler_service):
        """TrainNotFoundError path should also use split sessions:
        Phase 1 (read) then Phase 3 (write error count)."""

        from trackrat.collectors.njt.client import TrainNotFoundError

        session_open_during_api_call = False
        session_context_active = False
        call_count = [0]

        class TrackingSession:
            def __init__(self):
                self._execute_result = Mock()
                self._execute_result.first.return_value = _make_journey_row(api_error_count=0)

            def __enter__(self):
                nonlocal session_context_active
                session_context_active = True
                return self

            def __exit__(self, *args):
                nonlocal session_context_active
                session_context_active = False

            def execute(self, stmt):
                return self._execute_result

            def get(self, model, pk):
                return _make_journey_orm()

            @property
            def no_autoflush(self):
                return MagicMock()

        class TrackingSessionMaker:
            def __call__(self):
                nonlocal call_count
                call_count[0] += 1
                return TrackingSession()

        async def mock_api_call(train_id):
            nonlocal session_open_during_api_call
            if session_context_active:
                session_open_during_api_call = True
            raise TrainNotFoundError(f"Train {train_id} not found")

        scheduler_service.njt_client.get_train_stop_list = mock_api_call

        with patch("trackrat.services.scheduler.commit_with_retry"):
            with patch("sqlalchemy.orm.sessionmaker", return_value=TrackingSessionMaker()):
                result = await scheduler_service._collect_single_njt_journey_safe(
                    "1234", date(2026, 3, 11)
                )

        assert result is not None
        assert result["success"] is False
        assert result["error"] == "Train not found"
        assert not session_open_during_api_call, (
            "DB session was open during API call on TrainNotFoundError path"
        )
        # Phase 1 read + error write = 2 sessions
        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_one_session_for_null_data(self, scheduler_service):
        """NJTransitNullDataError path should only open one session (Phase 1 read).
        No DB write is needed — just return immediately."""

        from trackrat.collectors.njt.client import NJTransitNullDataError

        call_count = [0]

        class TrackingSession:
            def __init__(self):
                self._execute_result = Mock()
                self._execute_result.first.return_value = _make_journey_row()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def execute(self, stmt):
                return self._execute_result

        class TrackingSessionMaker:
            def __call__(self):
                nonlocal call_count
                call_count[0] += 1
                return TrackingSession()

        async def mock_api_call(train_id):
            raise NJTransitNullDataError("Null data")

        scheduler_service.njt_client.get_train_stop_list = mock_api_call

        with patch("sqlalchemy.orm.sessionmaker", return_value=TrackingSessionMaker()):
            result = await scheduler_service._collect_single_njt_journey_safe(
                "1234", date(2026, 3, 11)
            )

        assert result is not None
        assert result["success"] is False
        assert result["error"] == "Transient null data"
        # Only Phase 1 read — no write needed
        assert call_count[0] == 1, (
            f"NullDataError should only open 1 session (read), got {call_count[0]}"
        )


class TestSemaphoreConcurrencyLimit:
    """Verify the semaphore caps concurrent NJT API calls."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrent_api_calls(self, scheduler_service):
        """When 20 collections run concurrently, at most 10 should be
        making API calls simultaneously (semaphore limit)."""

        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        class SimpleSession:
            def __init__(self):
                self._execute_result = Mock()
                self._execute_result.first.return_value = _make_journey_row()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def execute(self, stmt):
                return self._execute_result

            def get(self, model, pk):
                return _make_journey_orm()

            def add(self, obj):
                pass

            @property
            def no_autoflush(self):
                return MagicMock()

        class SimpleSessionMaker:
            def __call__(self):
                return SimpleSession()

        async def slow_api_call(train_id):
            """Simulate a slow API call while tracking concurrency."""
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
            # Simulate API latency
            await asyncio.sleep(0.05)
            async with lock:
                current_concurrent -= 1
            return _make_train_data()

        scheduler_service.njt_client.get_train_stop_list = slow_api_call

        with patch("trackrat.services.scheduler.commit_with_retry"):
            with patch("sqlalchemy.orm.sessionmaker", return_value=SimpleSessionMaker()):
                # Fire 20 concurrent collections
                tasks = [
                    asyncio.create_task(
                        scheduler_service._collect_single_njt_journey_safe(
                            str(i), date(2026, 3, 11)
                        )
                    )
                    for i in range(20)
                ]
                results = await asyncio.gather(*tasks)

        # All should succeed
        successful = [r for r in results if r and r.get("success")]
        assert len(successful) == 20, f"Expected 20 successes, got {len(successful)}"

        # Concurrency should be capped at semaphore limit (10)
        assert max_concurrent <= 10, (
            f"Max concurrent API calls was {max_concurrent}, expected <= 10. "
            "Semaphore is not limiting concurrency properly."
        )
        # Should actually hit the limit (all 20 tasks compete for 10 slots)
        assert max_concurrent >= 5, (
            f"Max concurrent was only {max_concurrent} — semaphore may not be needed, "
            "but this is unexpectedly low for 20 tasks."
        )

    @pytest.mark.asyncio
    async def test_semaphore_does_not_block_reads(self, scheduler_service):
        """Phase 1 (DB read) should happen OUTSIDE the semaphore,
        so even if the semaphore is full, new tasks can still check
        if the journey exists/is expired without waiting."""

        # Set semaphore to 1 to make contention obvious
        scheduler_service._njt_collection_semaphore = asyncio.Semaphore(1)

        phase1_completed = asyncio.Event()
        api_started = asyncio.Event()
        api_can_finish = asyncio.Event()

        class SimpleSession:
            def __init__(self):
                self._execute_result = Mock()
                # Return expired journey for task 2 so it exits early
                self._execute_result.first.return_value = _make_journey_row(is_expired=True)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def execute(self, stmt):
                return self._execute_result

        first_call = [True]

        class SimpleSessionMaker:
            def __call__(self):
                s = SimpleSession()
                # First call returns non-expired, second returns expired
                if first_call[0]:
                    first_call[0] = False
                    row = _make_journey_row(is_expired=False)
                else:
                    row = _make_journey_row(is_expired=True)
                s._execute_result.first.return_value = row
                return s

        async def blocking_api_call(train_id):
            api_started.set()
            await api_can_finish.wait()
            return _make_train_data()

        scheduler_service.njt_client.get_train_stop_list = blocking_api_call

        async def task1():
            """Holds the semaphore during a long API call."""
            with patch("trackrat.services.scheduler.commit_with_retry"):
                with patch("sqlalchemy.orm.sessionmaker", return_value=SimpleSessionMaker()):
                    return await scheduler_service._collect_single_njt_journey_safe(
                        "1111", date(2026, 3, 11)
                    )

        async def task2():
            """Should be able to read DB and exit early (expired journey)
            even while task1 holds the semaphore."""
            await api_started.wait()  # Ensure task1 has the semaphore
            with patch("sqlalchemy.orm.sessionmaker", return_value=SimpleSessionMaker()):
                return await scheduler_service._collect_single_njt_journey_safe(
                    "2222", date(2026, 3, 11)
                )

        t1 = asyncio.create_task(task1())
        t2 = asyncio.create_task(task2())

        # Task 2 should complete quickly (expired journey, no API call needed)
        result2 = await asyncio.wait_for(t2, timeout=2.0)
        assert result2 is None, "Expired journey should return None without waiting for semaphore"

        # Let task 1 finish
        api_can_finish.set()
        await t1


class TestCodePaths:
    """Verify all code paths in the refactored method produce correct results."""

    @pytest.mark.asyncio
    async def test_journey_not_found_returns_none(self, scheduler_service):
        """When no journey exists in DB, return None immediately."""

        class EmptySession:
            def __init__(self):
                self._execute_result = Mock()
                self._execute_result.first.return_value = None

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def execute(self, stmt):
                return self._execute_result

        class SessionMaker:
            def __call__(self):
                return EmptySession()

        with patch("sqlalchemy.orm.sessionmaker", return_value=SessionMaker()):
            result = await scheduler_service._collect_single_njt_journey_safe(
                "9999", date(2026, 3, 11)
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_expired_journey_returns_none(self, scheduler_service):
        """Expired journeys should be skipped without an API call."""

        api_called = False

        class ExpiredSession:
            def __init__(self):
                self._execute_result = Mock()
                self._execute_result.first.return_value = _make_journey_row(is_expired=True)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def execute(self, stmt):
                return self._execute_result

        class SessionMaker:
            def __call__(self):
                return ExpiredSession()

        async def should_not_be_called(train_id):
            nonlocal api_called
            api_called = True

        scheduler_service.njt_client.get_train_stop_list = should_not_be_called

        with patch("sqlalchemy.orm.sessionmaker", return_value=SessionMaker()):
            result = await scheduler_service._collect_single_njt_journey_safe(
                "1234", date(2026, 3, 11)
            )

        assert result is None
        assert not api_called, "API should not be called for expired journeys"

    @pytest.mark.asyncio
    async def test_train_not_found_increments_error_count(self, scheduler_service):
        """TrainNotFoundError should increment api_error_count and mark expired after 3."""

        from trackrat.collectors.njt.client import TrainNotFoundError

        written_journey = None

        class WriteSession:
            def __init__(self):
                self._execute_result = Mock()
                self._execute_result.first.return_value = _make_journey_row(api_error_count=2)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def execute(self, stmt):
                return self._execute_result

            def get(self, model, pk):
                nonlocal written_journey
                written_journey = _make_journey_orm(api_error_count=2, update_count=5)
                return written_journey

        class SessionMaker:
            def __call__(self):
                return WriteSession()

        async def raise_not_found(train_id):
            raise TrainNotFoundError(f"Train {train_id} not found")

        scheduler_service.njt_client.get_train_stop_list = raise_not_found

        with patch("trackrat.services.scheduler.commit_with_retry"):
            with patch("sqlalchemy.orm.sessionmaker", return_value=SessionMaker()):
                result = await scheduler_service._collect_single_njt_journey_safe(
                    "1234", date(2026, 3, 11)
                )

        assert result["success"] is False
        assert result["error"] == "Train not found"
        assert result["expired"] is True  # 2 + 1 = 3 >= 3
        assert written_journey is not None
        assert written_journey.api_error_count == 3
        assert written_journey.is_expired is True

    @pytest.mark.asyncio
    async def test_njt_client_not_initialized_returns_none(self, scheduler_service):
        """Missing NJT client should return None without attempting API call."""

        scheduler_service.njt_client = None

        class ReadSession:
            def __init__(self):
                self._execute_result = Mock()
                self._execute_result.first.return_value = _make_journey_row()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def execute(self, stmt):
                return self._execute_result

        class SessionMaker:
            def __call__(self):
                return ReadSession()

        with patch("sqlalchemy.orm.sessionmaker", return_value=SessionMaker()):
            result = await scheduler_service._collect_single_njt_journey_safe(
                "1234", date(2026, 3, 11)
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_successful_collection_returns_correct_data(self, scheduler_service):
        """Successful API call should write to DB and return result dict."""

        written_objects = []

        class WriteSession:
            def __init__(self):
                self._execute_result = Mock()
                self._execute_result.first.return_value = _make_journey_row()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def execute(self, stmt):
                return self._execute_result

            def get(self, model, pk):
                return _make_journey_orm()

            def add(self, obj):
                written_objects.append(obj)

            @property
            def no_autoflush(self):
                return MagicMock()

        class SessionMaker:
            def __call__(self):
                return WriteSession()

        train_data = _make_train_data()
        scheduler_service.njt_client.get_train_stop_list = AsyncMock(return_value=train_data)

        with patch("trackrat.services.scheduler.commit_with_retry"):
            with patch("sqlalchemy.orm.sessionmaker", return_value=SessionMaker()):
                result = await scheduler_service._collect_single_njt_journey_safe(
                    "1234", date(2026, 3, 11)
                )

        assert result is not None
        assert result["success"] is True
        assert result["train_id"] == "1234"
        assert result["stops_count"] == 3
        assert result["destination"] == "Test Destination"
        # Should have written stops + snapshot
        assert len(written_objects) >= 3, (
            f"Expected at least 3 written objects (3 stops + snapshot), got {len(written_objects)}"
        )

    @pytest.mark.asyncio
    async def test_journey_disappeared_between_phases(self, scheduler_service):
        """If the journey is deleted between Phase 1 and Phase 3, handle gracefully."""

        call_count = [0]

        class DisappearingSession:
            def __init__(self):
                self._execute_result = Mock()
                self._execute_result.first.return_value = _make_journey_row()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def execute(self, stmt):
                return self._execute_result

            def get(self, model, pk):
                # Journey was deleted between Phase 1 and Phase 3
                return None

            @property
            def no_autoflush(self):
                return MagicMock()

        class SessionMaker:
            def __call__(self):
                nonlocal call_count
                call_count[0] += 1
                return DisappearingSession()

        scheduler_service.njt_client.get_train_stop_list = AsyncMock(
            return_value=_make_train_data()
        )

        with patch("sqlalchemy.orm.sessionmaker", return_value=SessionMaker()):
            result = await scheduler_service._collect_single_njt_journey_safe(
                "1234", date(2026, 3, 11)
            )

        assert result is None, "Should return None when journey disappears between phases"

    @pytest.mark.asyncio
    async def test_transient_db_error_returns_retry_needed(self, scheduler_service):
        """Serialization failures should be flagged as transient with retry_needed."""

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

        assert result is not None
        assert result["success"] is False
        assert result["retry_needed"] is True
