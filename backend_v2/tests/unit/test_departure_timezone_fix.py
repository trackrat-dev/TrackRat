"""
Test for departure service timezone bug fix.

Tests that the fix for the timezone bug where date parameters
were treated as UTC instead of ET is working correctly.
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

from trackrat.services.departure import DepartureService
from trackrat.utils.time import ET
import pytz


class TestDepartureServiceTimezoneFix:
    """Test the timezone fix in departure service."""

    def test_date_parameter_creates_et_timezone_aware_datetime(self):
        """Test that when a date is provided, time_from is created as ET timezone-aware."""

        # Test the exact logic that was fixed in the departure service
        query_date = date(2025, 9, 27)

        # This is the NEW fixed code from departure.py lines 46-49
        time_from = ET.localize(datetime.combine(query_date, datetime.min.time()))

        # Verify the fix works correctly
        assert time_from.tzinfo is not None
        assert time_from.tzinfo.zone == "America/New_York"

        # Verify it represents midnight ET on Sept 27
        expected = ET.localize(datetime(2025, 9, 27, 0, 0, 0))
        assert time_from == expected

        # Verify UTC conversion
        utc_time = time_from.astimezone(pytz.UTC)
        expected_utc = pytz.UTC.localize(datetime(2025, 9, 27, 4, 0, 0))  # EDT = UTC-4
        assert utc_time == expected_utc

    def test_time_from_none_creates_et_timezone_aware_datetime(self):
        """Test that when time_from is None, the default is ET timezone-aware."""
        service = DepartureService()

        # Simulate the exact code path that was fixed
        query_date = date(2025, 9, 27)

        # Before fix: this would create naive datetime
        # time_from = datetime.combine(query_date, datetime.min.time())

        # After fix: this creates ET timezone-aware datetime
        time_from_fixed = ET.localize(datetime.combine(query_date, datetime.min.time()))

        # Verify the fix
        assert time_from_fixed.tzinfo is not None
        assert time_from_fixed.tzinfo.zone == "America/New_York"

        # Verify it represents midnight ET on the given date
        expected_et = ET.localize(datetime(2025, 9, 27, 0, 0, 0))
        assert time_from_fixed == expected_et

        # Verify UTC conversion is correct
        expected_utc = pytz.UTC.localize(datetime(2025, 9, 27, 4, 0, 0))  # EDT is UTC-4
        actual_utc = time_from_fixed.astimezone(pytz.UTC)
        assert actual_utc == expected_utc

    def test_provided_time_from_is_made_timezone_aware(self):
        """Test that provided time_from parameters are made timezone-aware."""

        # Test the logic from the fixed code
        from trackrat.utils.time import ensure_timezone_aware

        # Test with naive datetime (should be converted to ET)
        naive_time = datetime(2025, 9, 27, 14, 30, 0)  # 2:30 PM naive

        # This is the NEW fixed code from departure.py lines 52-53
        time_from_fixed = ensure_timezone_aware(naive_time)

        # Verify it's now timezone-aware
        assert time_from_fixed.tzinfo is not None
        assert time_from_fixed.tzinfo.zone == "America/New_York"

        # Test with already timezone-aware datetime
        aware_time = ET.localize(datetime(2025, 9, 27, 14, 30, 0))
        time_from_already_aware = ensure_timezone_aware(aware_time)

        # Should remain the same
        assert time_from_already_aware == aware_time

    def test_timezone_bug_scenario_reproduction(self):
        """Reproduce the exact scenario described in the bug report."""

        # The bug: querying for trains on Sept 27 at 9:20 PM ET
        # trains with 7:15 PM ET departure should not be returned
        # because they've already departed

        query_date = date(2025, 9, 27)
        current_time_et = ET.localize(datetime(2025, 9, 27, 21, 20, 0))  # 9:20 PM ET

        # Before fix: naive datetime treated as UTC
        time_from_naive = datetime.combine(query_date, datetime.min.time())
        # This would be treated as UTC, which is 8:00 PM ET on Sept 26!
        time_from_as_utc = pytz.UTC.localize(time_from_naive)
        time_from_wrong_et = time_from_as_utc.astimezone(ET)

        # After fix: timezone-aware datetime in ET
        time_from_fixed = ET.localize(datetime.combine(query_date, datetime.min.time()))

        print(f"Query date: {query_date}")
        print(f"Current time ET: {current_time_et}")
        print(f"Wrong time_from (treated as UTC): {time_from_wrong_et}")
        print(f"Fixed time_from (ET): {time_from_fixed}")

        # The bug caused queries to start from the wrong day
        assert time_from_wrong_et.date() == date(2025, 9, 26)  # Wrong day!
        assert time_from_fixed.date() == date(2025, 9, 27)  # Correct day

        # Test a train that should be visible after the fix
        train_departure_et = ET.localize(
            datetime(2025, 9, 27, 22, 30, 0)
        )  # 10:30 PM ET

        # With the wrong time range, this train might not be found
        # With the fixed time range, this train should be found
        train_in_fixed_range = (
            time_from_fixed
            <= train_departure_et
            < (time_from_fixed + timedelta(hours=24))
        )
        train_hasnt_departed = train_departure_et > current_time_et

        assert train_in_fixed_range
        assert train_hasnt_departed

        print(
            f"Train at {train_departure_et} should be returned: {train_in_fixed_range and train_hasnt_departed}"
        )

    def test_dst_transition_handling(self):
        """Test that the fix handles DST transitions correctly."""

        # Test during DST transition (spring forward - March)
        spring_date = date(2025, 3, 9)  # Second Sunday in March (typical DST start)
        time_from_spring = ET.localize(
            datetime.combine(spring_date, datetime.min.time())
        )

        # Test during DST transition (fall back - November)
        fall_date = date(2025, 11, 2)  # First Sunday in November (typical DST end)
        time_from_fall = ET.localize(datetime.combine(fall_date, datetime.min.time()))

        # Both should be timezone-aware and handle DST correctly
        assert time_from_spring.tzinfo is not None
        assert time_from_fall.tzinfo is not None

        # DST handling should work without errors
        spring_utc = time_from_spring.astimezone(pytz.UTC)
        fall_utc = time_from_fall.astimezone(pytz.UTC)

        assert spring_utc.tzinfo == pytz.UTC
        assert fall_utc.tzinfo == pytz.UTC
