"""
Tests for utility functions.
"""

import pytest
from datetime import datetime, date, timedelta
import pytz

from trackrat.utils.time import (
    now_et,
    parse_njt_time,
    parse_date,
    combine_date_time,
    format_iso,
    calculate_delay,
    is_stale,
    ensure_timezone_aware,
    normalize_to_et,
    safe_datetime_subtract,
    ET,
)
from trackrat.utils.sanitize import sanitize_track


def test_now_et():
    """Test getting current time in Eastern Time."""
    result = now_et()
    # Check timezone name instead of object equality
    assert result.tzinfo.zone == "America/New_York"
    assert isinstance(result, datetime)


def test_parse_njt_time():
    """Test parsing NJ Transit time format."""
    # Test standard format
    result = parse_njt_time("30-May-2024 10:52:30 AM")
    assert result.year == 2024
    assert result.month == 5
    assert result.day == 30
    assert result.hour == 10
    assert result.minute == 52
    assert result.second == 30
    assert result.tzinfo.zone == "America/New_York"

    # Test PM time
    result = parse_njt_time("15-Jan-2024 02:30:00 PM")
    assert result.hour == 14
    assert result.minute == 30


def test_parse_date():
    """Test parsing date strings."""
    # Test ISO format
    result = parse_date("2024-07-04")
    assert result == date(2024, 7, 4)

    # Test date object passthrough
    test_date = date(2024, 7, 4)
    result = parse_date(test_date)
    assert result == test_date

    # Test other formats
    result = parse_date("July 4, 2024")
    assert result == date(2024, 7, 4)


def test_combine_date_time():
    """Test combining date and time."""
    test_date = date(2024, 7, 4)

    # Test with HH:MM:SS format
    result = combine_date_time(test_date, "14:30:00")
    assert result.date() == test_date
    assert result.hour == 14
    assert result.minute == 30
    assert result.second == 0
    assert result.tzinfo.zone == "America/New_York"

    # Test with AM/PM format
    result = combine_date_time(test_date, "2:30 PM")
    assert result.hour == 14
    assert result.minute == 30


def test_format_iso():
    """Test ISO formatting."""
    dt = ET.localize(datetime(2024, 7, 4, 14, 30, 0))
    result = format_iso(dt)
    assert "2024-07-04T14:30:00" in result
    assert "-04:00" in result or "-05:00" in result  # Depends on DST

    # Test None handling
    assert format_iso(None) is None


def test_calculate_delay():
    """Test delay calculation."""
    scheduled = ET.localize(datetime(2024, 7, 4, 14, 30, 0))

    # On time
    actual = scheduled
    assert calculate_delay(scheduled, actual) == 0

    # 5 minutes late
    actual = scheduled + timedelta(minutes=5)
    assert calculate_delay(scheduled, actual) == 5

    # Early arrival (should be 0, not negative)
    actual = scheduled - timedelta(minutes=5)
    assert calculate_delay(scheduled, actual) == 0

    # None actual time
    assert calculate_delay(scheduled, None) == 0


def test_is_stale():
    """Test staleness check."""
    from trackrat.utils.time import now_et

    # Use a fixed reference time for consistent testing
    base_time = now_et()

    # Fresh data
    last_updated = base_time - timedelta(seconds=30)
    assert is_stale(last_updated, 60) is False

    # Stale data
    last_updated = base_time - timedelta(seconds=90)
    assert is_stale(last_updated, 60) is True

    # Exactly at threshold - should NOT be stale
    last_updated = base_time - timedelta(seconds=60)
    # Override now_et for this test
    from unittest.mock import patch

    with patch("trackrat.utils.time.now_et", return_value=base_time):
        assert is_stale(last_updated, 60) is False

    # Just over threshold - should be stale
    last_updated = base_time - timedelta(seconds=61)
    with patch("trackrat.utils.time.now_et", return_value=base_time):
        assert is_stale(last_updated, 60) is True


def test_ensure_timezone_aware():
    """Test ensuring datetime objects are timezone-aware."""
    # Test with naive datetime
    naive_dt = datetime(2024, 7, 4, 14, 30, 0)
    result = ensure_timezone_aware(naive_dt)
    assert result.tzinfo is not None
    assert result.tzinfo.zone == "America/New_York"
    assert result.year == 2024
    assert result.month == 7
    assert result.day == 4
    assert result.hour == 14
    assert result.minute == 30

    # Test with already timezone-aware datetime
    aware_dt = ET.localize(datetime(2024, 7, 4, 14, 30, 0))
    result = ensure_timezone_aware(aware_dt)
    assert result == aware_dt
    assert result.tzinfo.zone == "America/New_York"

    # Test with different timezone
    utc = pytz.UTC
    utc_dt = utc.localize(datetime(2024, 7, 4, 14, 30, 0))
    result = ensure_timezone_aware(utc_dt)
    assert result == utc_dt
    assert result.tzinfo.zone == "UTC"

    # Test with custom default timezone
    pacific = pytz.timezone("America/Los_Angeles")
    result = ensure_timezone_aware(naive_dt, default_tz=pacific)
    assert result.tzinfo.zone == "America/Los_Angeles"


def test_normalize_to_et():
    """Test normalizing datetime objects to Eastern Time."""
    # Test with UTC datetime
    utc = pytz.UTC
    utc_dt = utc.localize(datetime(2024, 7, 4, 18, 30, 0))  # 6:30 PM UTC
    result = normalize_to_et(utc_dt)
    assert result.tzinfo.zone == "America/New_York"
    # In July, ET is UTC-4, so 6:30 PM UTC = 2:30 PM ET
    assert result.hour == 14
    assert result.minute == 30

    # Test with Pacific Time
    pacific = pytz.timezone("America/Los_Angeles")
    pacific_dt = pacific.localize(datetime(2024, 7, 4, 11, 30, 0))  # 11:30 AM PT
    result = normalize_to_et(pacific_dt)
    assert result.tzinfo.zone == "America/New_York"
    # In July, PT is UTC-7, ET is UTC-4, so 11:30 AM PT = 2:30 PM ET
    assert result.hour == 14
    assert result.minute == 30

    # Test with already Eastern Time
    et_dt = ET.localize(datetime(2024, 7, 4, 14, 30, 0))
    result = normalize_to_et(et_dt)
    assert result.tzinfo.zone == "America/New_York"
    assert result.hour == 14
    assert result.minute == 30

    # Test with naive datetime (should be localized to ET first)
    naive_dt = datetime(2024, 7, 4, 14, 30, 0)
    result = normalize_to_et(naive_dt)
    assert result.tzinfo.zone == "America/New_York"
    assert result.hour == 14
    assert result.minute == 30


def test_safe_datetime_subtract():
    """Test safe datetime subtraction with timezone handling."""
    # Test with same timezone
    dt1 = ET.localize(datetime(2024, 7, 4, 15, 30, 0))
    dt2 = ET.localize(datetime(2024, 7, 4, 14, 30, 0))
    result = safe_datetime_subtract(dt1, dt2)
    assert result == timedelta(hours=1)

    # Test with different timezones
    utc = pytz.UTC
    pacific = pytz.timezone("America/Los_Angeles")

    # 6:30 PM UTC = 2:30 PM ET
    utc_dt = utc.localize(datetime(2024, 7, 4, 18, 30, 0))
    # 11:30 AM PT = 2:30 PM ET
    pacific_dt = pacific.localize(datetime(2024, 7, 4, 11, 30, 0))

    result = safe_datetime_subtract(utc_dt, pacific_dt)
    assert result == timedelta(0)  # Same time in ET

    # Test with mixed timezone and naive
    naive_dt = datetime(2024, 7, 4, 14, 30, 0)  # Will be treated as ET
    et_dt = ET.localize(datetime(2024, 7, 4, 15, 30, 0))

    result = safe_datetime_subtract(et_dt, naive_dt)
    assert result == timedelta(hours=1)

    # Test negative result
    result = safe_datetime_subtract(naive_dt, et_dt)
    assert result == timedelta(hours=-1)


def test_timezone_handling_edge_cases():
    """Test edge cases for timezone handling."""
    # Test with DST boundary
    # Spring forward: 2024-03-10 02:00 -> 03:00
    naive_dt = datetime(2024, 3, 10, 2, 30, 0)

    # This should handle the DST transition gracefully
    result = ensure_timezone_aware(naive_dt)
    assert result.tzinfo.zone == "America/New_York"

    # Test with UTC offset changes
    winter_dt = datetime(2024, 1, 4, 14, 30, 0)
    summer_dt = datetime(2024, 7, 4, 14, 30, 0)

    winter_et = ensure_timezone_aware(winter_dt)
    summer_et = ensure_timezone_aware(summer_dt)

    # Both should be in ET but with different UTC offsets
    assert winter_et.tzinfo.zone == "America/New_York"
    assert summer_et.tzinfo.zone == "America/New_York"

    # Winter is EST (UTC-5), Summer is EDT (UTC-4)
    # So they should have different UTC offsets
    winter_utc = winter_et.astimezone(pytz.UTC)
    summer_utc = summer_et.astimezone(pytz.UTC)

    assert winter_utc.hour == 19  # 2:30 PM EST = 7:30 PM UTC
    assert summer_utc.hour == 18  # 2:30 PM EDT = 6:30 PM UTC


def test_calculate_delay_with_mixed_timezones():
    """Test delay calculation with mixed timezone scenarios."""
    # Test with different timezone inputs
    utc = pytz.UTC
    pacific = pytz.timezone("America/Los_Angeles")

    # Scheduled in ET, actual in UTC (same moment)
    scheduled = ET.localize(datetime(2024, 7, 4, 14, 30, 0))  # 2:30 PM ET
    actual = utc.localize(datetime(2024, 7, 4, 18, 30, 0))  # 6:30 PM UTC = 2:30 PM ET

    delay = calculate_delay(scheduled, actual)
    assert delay == 0  # Same time, no delay

    # Test with actual delay across timezones
    actual_late = utc.localize(
        datetime(2024, 7, 4, 18, 35, 0)
    )  # 6:35 PM UTC = 2:35 PM ET
    delay = calculate_delay(scheduled, actual_late)
    assert delay == 5  # 5 minutes late


def test_is_stale_with_mixed_timezones():
    """Test staleness check with mixed timezone scenarios."""
    from trackrat.utils.time import now_et

    # Test with different timezone inputs
    utc = pytz.UTC

    # Create a UTC time that's 1 minute ago in ET
    now_utc = now_et().astimezone(utc)
    last_updated_utc = now_utc - timedelta(minutes=1)

    # Should handle timezone conversion properly
    assert is_stale(last_updated_utc, 120) is False  # Not stale


def test_sanitize_track_none_or_empty():
    """Test sanitize_track with None or empty values."""
    assert sanitize_track(None) is None
    assert sanitize_track("") is None
    assert sanitize_track("   ") is None


def test_sanitize_track_fits_already():
    """Test sanitize_track with values that already fit."""
    assert sanitize_track("1") == "1"
    assert sanitize_track("2A") == "2A"
    assert sanitize_track("12") == "12"
    assert sanitize_track("Track") == "Track"
    assert sanitize_track("  3  ") == "3"  # Should strip whitespace


def test_sanitize_track_extract_number():
    """Test sanitize_track extracting track numbers from longer strings."""
    # Common patterns
    assert sanitize_track("Track 1") == "1"
    assert sanitize_track("Track 2A") == "2A"
    assert sanitize_track("Platform 3") == "3"
    assert sanitize_track("1 Running") == "1"
    assert sanitize_track("Track 12") == "12"

    # Edge cases with numbers
    assert sanitize_track("On Track 5") == "5"
    assert sanitize_track("Track A1") == "A1"


def test_sanitize_track_truncation():
    """Test sanitize_track truncation for unusual values."""
    # Long strings without clear track numbers
    assert sanitize_track("Millstone Running") == "Mill+"
    assert sanitize_track("Platform Seven") == "Plat+"
    assert sanitize_track("Extended Track Name") == "Exte+"

    # Ensure truncation indicator is added
    assert sanitize_track("LongTrackName").endswith("+")
    assert len(sanitize_track("VeryLongTrackName")) == 5


def test_sanitize_track_real_world_cases():
    """Test sanitize_track with real-world problematic values."""
    # The actual case that caused the bug
    assert sanitize_track("Millstone Running") == "Mill+"

    # Other potential edge cases
    assert sanitize_track("Track") == "Track"  # Exactly 5 chars
    assert sanitize_track("Tracks") == "Trac+"  # 6 chars

    # Numbers at various positions
    assert sanitize_track("Running on 4") == "4"
    assert sanitize_track("Goes to 2B") == "2B"
