"""
Test for timezone-aware datetime constants and their usage.

These constants (DATETIME_MIN_ET, DATETIME_MAX_ET) prevent TypeError when
comparing timezone-aware datetimes from the database/API with fallback values.

The bug: Using naive datetime.min/datetime.max as fallbacks when sorting
timezone-aware datetimes causes TypeError: can't compare offset-naive and
offset-aware datetimes.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

import pytz

from trackrat.utils.time import (
    DATETIME_MIN_ET,
    DATETIME_MAX_ET,
    ET,
    parse_njt_time,
)


class TestDatetimeConstants:
    """Test that datetime constants are properly defined."""

    def test_datetime_max_et_is_timezone_aware(self):
        """DATETIME_MAX_ET must be timezone-aware."""
        assert DATETIME_MAX_ET.tzinfo is not None
        assert DATETIME_MAX_ET.tzinfo.zone == "America/New_York"

    def test_datetime_min_et_is_timezone_aware(self):
        """DATETIME_MIN_ET must be timezone-aware."""
        assert DATETIME_MIN_ET.tzinfo is not None
        assert DATETIME_MIN_ET.tzinfo.zone == "America/New_York"

    def test_datetime_max_et_is_far_future(self):
        """DATETIME_MAX_ET should be far in the future (2099)."""
        assert DATETIME_MAX_ET.year == 2099
        assert DATETIME_MAX_ET.month == 12
        assert DATETIME_MAX_ET.day == 31

    def test_datetime_min_et_is_far_past(self):
        """DATETIME_MIN_ET should be far in the past (1900)."""
        assert DATETIME_MIN_ET.year == 1900
        assert DATETIME_MIN_ET.month == 1
        assert DATETIME_MIN_ET.day == 1

    def test_datetime_max_greater_than_any_real_time(self):
        """DATETIME_MAX_ET should be greater than any realistic train time."""
        # Any train scheduled in 2025-2050 should be less than DATETIME_MAX_ET
        train_time = ET.localize(datetime(2050, 12, 31, 23, 59, 59))
        assert train_time < DATETIME_MAX_ET

    def test_datetime_min_less_than_any_real_time(self):
        """DATETIME_MIN_ET should be less than any realistic train time."""
        # Any train scheduled in 2000+ should be greater than DATETIME_MIN_ET
        train_time = ET.localize(datetime(2000, 1, 1, 0, 0, 0))
        assert train_time > DATETIME_MIN_ET


class TestDatetimeComparisonSafety:
    """Test that constants can be safely compared with timezone-aware datetimes."""

    def test_compare_with_et_localized_datetime(self):
        """Constants should compare safely with ET-localized datetimes."""
        et_time = ET.localize(datetime(2025, 6, 15, 12, 0, 0))

        # These comparisons should not raise TypeError
        assert et_time < DATETIME_MAX_ET
        assert et_time > DATETIME_MIN_ET
        assert DATETIME_MAX_ET > et_time
        assert DATETIME_MIN_ET < et_time

    def test_compare_with_utc_datetime(self):
        """Constants should compare safely with UTC datetimes."""
        utc_time = pytz.UTC.localize(datetime(2025, 6, 15, 12, 0, 0))

        # Timezone-aware datetimes can be compared across timezones
        assert utc_time < DATETIME_MAX_ET
        assert utc_time > DATETIME_MIN_ET

    def test_compare_with_parse_njt_time_result(self):
        """Constants should compare safely with parse_njt_time results."""
        # parse_njt_time returns ET-localized datetime
        njt_time = parse_njt_time("15-Jun-2025 02:30:00 PM")

        assert njt_time.tzinfo is not None  # Verify it's timezone-aware
        assert njt_time < DATETIME_MAX_ET
        assert njt_time > DATETIME_MIN_ET

    def test_naive_datetime_max_would_fail(self):
        """Demonstrate that naive datetime.max would raise TypeError."""
        et_time = ET.localize(datetime(2025, 6, 15, 12, 0, 0))

        # This is what would happen with the old code
        with pytest.raises(TypeError, match="can't compare"):
            _ = et_time < datetime.max

    def test_naive_datetime_min_would_fail(self):
        """Demonstrate that naive datetime.min would raise TypeError."""
        et_time = ET.localize(datetime(2025, 6, 15, 12, 0, 0))

        # This is what would happen with the old code
        with pytest.raises(TypeError, match="can't compare"):
            _ = et_time > datetime.min


class TestSortingWithConstants:
    """Test that sorting works correctly with the constants as fallbacks."""

    def test_sort_with_none_values_and_max_fallback(self):
        """Test sorting a list with None values using DATETIME_MAX_ET fallback."""
        times = [
            ET.localize(datetime(2025, 6, 15, 14, 0, 0)),
            None,
            ET.localize(datetime(2025, 6, 15, 10, 0, 0)),
            None,
            ET.localize(datetime(2025, 6, 15, 12, 0, 0)),
        ]

        # This is the pattern used in departure.py, journey.py, gtfs.py
        sorted_times = sorted(times, key=lambda t: t or DATETIME_MAX_ET)

        # None values should sort to the end
        assert sorted_times[0] == ET.localize(datetime(2025, 6, 15, 10, 0, 0))
        assert sorted_times[1] == ET.localize(datetime(2025, 6, 15, 12, 0, 0))
        assert sorted_times[2] == ET.localize(datetime(2025, 6, 15, 14, 0, 0))
        assert sorted_times[3] is None
        assert sorted_times[4] is None

    def test_sort_with_none_values_and_min_fallback(self):
        """Test sorting a list with None values using DATETIME_MIN_ET fallback."""
        times = [
            ET.localize(datetime(2025, 6, 15, 14, 0, 0)),
            None,
            ET.localize(datetime(2025, 6, 15, 10, 0, 0)),
        ]

        # This pattern puts None values at the beginning
        sorted_times = sorted(times, key=lambda t: t or DATETIME_MIN_ET)

        # None values should sort to the beginning
        assert sorted_times[0] is None
        assert sorted_times[1] == ET.localize(datetime(2025, 6, 15, 10, 0, 0))
        assert sorted_times[2] == ET.localize(datetime(2025, 6, 15, 14, 0, 0))

    def test_max_with_none_values_and_min_fallback(self):
        """Test finding max with None values using DATETIME_MIN_ET fallback."""
        times = [
            ET.localize(datetime(2025, 6, 15, 14, 0, 0)),
            None,
            ET.localize(datetime(2025, 6, 15, 10, 0, 0)),
        ]

        # This pattern is used in trains.py for finding latest progress snapshot
        latest = max(times, key=lambda t: t or DATETIME_MIN_ET)

        # Should find the actual max, not None
        assert latest == ET.localize(datetime(2025, 6, 15, 14, 0, 0))

    def test_tuple_sorting_with_priority_and_max(self):
        """Test tuple sorting with priority levels and DATETIME_MAX_ET."""
        # This pattern is used in journey.py for sorting stops
        items = [
            (0, ET.localize(datetime(2025, 6, 15, 14, 0, 0))),
            (1, DATETIME_MAX_ET, 2),  # No time, sequence 2
            (0, ET.localize(datetime(2025, 6, 15, 10, 0, 0))),
            (1, DATETIME_MAX_ET, 1),  # No time, sequence 1
        ]

        sorted_items = sorted(items)

        # Priority 0 items come first, sorted by time
        assert sorted_items[0] == (0, ET.localize(datetime(2025, 6, 15, 10, 0, 0)))
        assert sorted_items[1] == (0, ET.localize(datetime(2025, 6, 15, 14, 0, 0)))
        # Priority 1 items come next, sorted by sequence
        assert sorted_items[2] == (1, DATETIME_MAX_ET, 1)
        assert sorted_items[3] == (1, DATETIME_MAX_ET, 2)


class TestDepartureMergeScenario:
    """Test the specific scenario that was fixed in departure.py."""

    def test_merge_departures_sort_with_none_scheduled_time(self):
        """Reproduce the bug scenario from departure.py:957."""
        # Simulate TrainDeparture-like objects with scheduled_time
        class MockDeparture:
            def __init__(self, scheduled_time):
                self.scheduled_time = scheduled_time

        class MockTrainDeparture:
            def __init__(self, scheduled_time):
                self.departure = MockDeparture(scheduled_time)

        departures = [
            MockTrainDeparture(ET.localize(datetime(2025, 6, 15, 14, 0, 0))),
            MockTrainDeparture(None),  # This would cause TypeError with datetime.max
            MockTrainDeparture(ET.localize(datetime(2025, 6, 15, 10, 0, 0))),
        ]

        # Old code would fail:
        # merged.sort(key=lambda d: d.departure.scheduled_time or datetime.max)

        # New code works:
        departures.sort(key=lambda d: d.departure.scheduled_time or DATETIME_MAX_ET)

        assert departures[0].departure.scheduled_time == ET.localize(
            datetime(2025, 6, 15, 10, 0, 0)
        )
        assert departures[1].departure.scheduled_time == ET.localize(
            datetime(2025, 6, 15, 14, 0, 0)
        )
        assert departures[2].departure.scheduled_time is None


class TestJourneyStopSortScenario:
    """Test the specific scenario that was fixed in journey.py."""

    def test_stop_sort_with_missing_times(self):
        """Reproduce the bug scenario from journey.py:1058."""
        # Simulate NJT API response with some stops missing times
        class MockStopData:
            def __init__(self, time_str, dep_time_str):
                self.TIME = time_str
                self.DEP_TIME = dep_time_str

        stops = [
            MockStopData("15-Jun-2025 02:30:00 PM", "15-Jun-2025 02:31:00 PM"),
            MockStopData(None, None),  # No times - would cause TypeError
            MockStopData("15-Jun-2025 01:00:00 PM", "15-Jun-2025 01:01:00 PM"),
        ]

        def get_sort_time(stop_data):
            arr_time = parse_njt_time(stop_data.TIME) if stop_data.TIME else None
            dep_time = (
                parse_njt_time(stop_data.DEP_TIME) if stop_data.DEP_TIME else None
            )

            if arr_time and dep_time:
                return min(arr_time, dep_time)
            elif arr_time:
                return arr_time
            elif dep_time:
                return dep_time
            else:
                # Fixed: use timezone-aware constant
                return DATETIME_MAX_ET

        # This would fail with datetime.max
        sorted_stops = sorted(stops, key=get_sort_time)

        # Verify sorting works correctly
        assert sorted_stops[0].TIME == "15-Jun-2025 01:00:00 PM"
        assert sorted_stops[1].TIME == "15-Jun-2025 02:30:00 PM"
        assert sorted_stops[2].TIME is None  # None times at end


class TestProgressSnapshotScenario:
    """Test the specific scenario that was fixed in trains.py."""

    def test_max_progress_snapshot_with_none_captured_at(self):
        """Reproduce the bug scenario from trains.py:299."""
        # Simulate progress snapshots with captured_at
        class MockSnapshot:
            def __init__(self, captured_at):
                self.captured_at = captured_at

        # Note: In the real code, None captured_at are filtered out first
        # But we test the fallback pattern for safety
        snapshots = [
            MockSnapshot(ET.localize(datetime(2025, 6, 15, 14, 0, 0))),
            MockSnapshot(ET.localize(datetime(2025, 6, 15, 10, 0, 0))),
        ]

        # This is the fixed pattern
        latest = max(snapshots, key=lambda p: p.captured_at or DATETIME_MIN_ET)

        assert latest.captured_at == ET.localize(datetime(2025, 6, 15, 14, 0, 0))
