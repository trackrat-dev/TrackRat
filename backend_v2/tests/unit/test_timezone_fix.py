"""
Focused test for the timezone comparison fix.

This test specifically reproduces and verifies the fix for the
"can't compare offset-naive and offset-aware datetimes" error.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from trackrat.utils.time import now_et, ensure_timezone_aware


class TestTimezoneComparisonFix:
    """Test the specific timezone comparison fix."""

    def test_reproduces_original_error(self):
        """Reproduce the original TypeError that was occurring."""
        # Simulate SQLite returning a naive datetime
        naive_dt = datetime(2025, 7, 11, 14, 30, 0)  # No timezone

        # Simulate now_et() returning timezone-aware datetime
        aware_dt = now_et()

        # This would cause the original error
        with pytest.raises(TypeError, match="offset-naive and offset-aware"):
            naive_dt > aware_dt

    def test_fix_prevents_error(self):
        """Test that the fix prevents the TypeError."""
        # Simulate SQLite returning a naive datetime
        naive_dt = datetime(2025, 7, 11, 14, 30, 0)  # No timezone

        # Simulate now_et() returning timezone-aware datetime
        aware_dt = now_et()

        # Apply the fix: use ensure_timezone_aware
        fixed_dt = ensure_timezone_aware(naive_dt)

        # This should not raise TypeError
        try:
            comparison_result = fixed_dt > aware_dt
            assert isinstance(comparison_result, bool)
        except TypeError as e:
            pytest.fail(f"Fix failed to prevent TypeError: {e}")

    def test_ensure_timezone_aware_function(self):
        """Test the ensure_timezone_aware utility function."""
        # Test with naive datetime
        naive_dt = datetime(2025, 7, 11, 14, 30, 0)
        aware_dt = ensure_timezone_aware(naive_dt)

        assert aware_dt.tzinfo is not None
        assert aware_dt.tzinfo.zone == "America/New_York"

        # Test with already aware datetime
        already_aware = now_et()
        result = ensure_timezone_aware(already_aware)
        assert result == already_aware
        assert result.tzinfo is not None

    def test_real_world_scenario_simulation(self):
        """Simulate the real scenario where the error occurred."""
        # Simulate a journey's scheduled_departure from SQLite (naive)
        journey_scheduled_departure = datetime(2025, 7, 11, 15, 30, 0)

        # Simulate the current time from now_et() (aware)
        current_time = now_et()

        # Simulate the original problematic code
        def original_problematic_code():
            return journey_scheduled_departure > current_time

        # This should raise TypeError
        with pytest.raises(TypeError):
            original_problematic_code()

        # Simulate the fixed code
        def fixed_code():
            return ensure_timezone_aware(journey_scheduled_departure) > current_time

        # This should work without error
        try:
            result = fixed_code()
            assert isinstance(result, bool)
        except TypeError as e:
            pytest.fail(f"Fixed code still raises TypeError: {e}")

    @patch("trackrat.utils.time.now_et")
    def test_comparison_with_future_datetime(self, mock_now_et):
        """Test comparison with a future datetime."""
        # Set current time
        mock_current_time = datetime(2025, 7, 11, 14, 0, 0)
        mock_now_et.return_value = ensure_timezone_aware(mock_current_time)

        # Future naive datetime (as would come from SQLite)
        future_naive = datetime(2025, 7, 11, 15, 0, 0)  # 1 hour later

        # Apply fix and compare
        future_aware = ensure_timezone_aware(future_naive)
        current_aware = mock_now_et.return_value

        # Should correctly identify as future
        assert future_aware > current_aware

    @patch("trackrat.utils.time.now_et")
    def test_comparison_with_past_datetime(self, mock_now_et):
        """Test comparison with a past datetime."""
        # Set current time
        mock_current_time = datetime(2025, 7, 11, 14, 0, 0)
        mock_now_et.return_value = ensure_timezone_aware(mock_current_time)

        # Past naive datetime (as would come from SQLite)
        past_naive = datetime(2025, 7, 11, 13, 0, 0)  # 1 hour earlier

        # Apply fix and compare
        past_aware = ensure_timezone_aware(past_naive)
        current_aware = mock_now_et.return_value

        # Should correctly identify as past
        assert past_aware < current_aware
