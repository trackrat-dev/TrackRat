"""Test datetime handling in live activity updates."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from trackrat.services.scheduler import SchedulerService
from trackrat.utils.time import ensure_timezone_aware, now_et, safe_datetime_subtract


@pytest.fixture
def mock_apns_service():
    """Mock APNS service."""
    service = MagicMock()
    service.send_live_activity_update = MagicMock(return_value=True)
    return service


@pytest.fixture
def scheduler_service(mock_apns_service):
    """Create scheduler service with mocked APNS."""
    return SchedulerService(apns_service=mock_apns_service)


def test_datetime_functions_handle_naive_datetimes():
    """Test that datetime utility functions handle naive datetimes correctly."""
    # Test ensure_timezone_aware
    naive_dt = datetime(2025, 1, 12, 14, 30, 0)
    aware_dt = ensure_timezone_aware(naive_dt)

    assert naive_dt.tzinfo is None
    assert aware_dt.tzinfo is not None
    assert str(aware_dt.tzinfo) == "America/New_York"

    # Test safe_datetime_subtract with mixed timezones
    current_time = now_et()

    # Should not raise exception
    diff = safe_datetime_subtract(current_time, naive_dt)
    assert isinstance(diff, timedelta)

    # Test comparing naive datetime with aware datetime
    # This would normally fail with: "can't subtract offset-naive and offset-aware datetimes"
    try:
        # This would fail
        direct_diff = current_time - naive_dt
        assert False, "Should have raised TypeError"
    except TypeError as e:
        assert "can't subtract offset-naive and offset-aware datetimes" in str(e)


@pytest.mark.asyncio
async def test_is_stale_handles_naive_datetime(scheduler_service: SchedulerService):
    """Test that _is_stale method handles naive datetime correctly."""
    # Test with naive datetime
    naive_dt = datetime.now()  # Naive datetime

    # This should not raise an exception
    is_stale = scheduler_service._is_stale(naive_dt, threshold_seconds=60)

    # Should be stale since it's a current time being compared
    assert not is_stale  # Just created, so not stale

    # Test with old naive datetime
    old_naive_dt = datetime.now() - timedelta(minutes=5)
    is_stale = scheduler_service._is_stale(old_naive_dt, threshold_seconds=60)
    assert is_stale  # 5 minutes old, so stale


def test_schedule_departure_time_comparison():
    """Test the logic used in live activity for departure time comparison."""
    # Simulate the scenario from the live activity update
    naive_scheduled_departure = datetime(2025, 1, 12, 14, 30, 0)  # Naive datetime

    # This is what the code does now
    scheduled_dep = ensure_timezone_aware(naive_scheduled_departure)
    current_time = now_et()

    # This should not raise an exception
    is_in_past = scheduled_dep < current_time
    assert isinstance(is_in_past, bool)

    # Test with a future time
    future_naive = datetime.now() + timedelta(hours=2)
    future_aware = ensure_timezone_aware(future_naive)
    is_future = future_aware > now_et()
    assert isinstance(is_future, bool)
