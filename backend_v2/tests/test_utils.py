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
from trackrat.utils import sanitize as sanitize_module
from trackrat.utils.sanitize import sanitize_track, validate_track
from trackrat.config.station_configs import get_valid_tracks

# NOTE: the once-per-process rejection memo these tests depend on
# (``sanitize._implausible_track_warned``, issue #1792) is cleared around every
# test by the suite-wide ``clear_implausible_track_memo`` fixture in
# ``tests/conftest.py``, so the assertions below are order-independent.


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


# ---------------------------------------------------------------------------
# get_valid_tracks (station_configs)
# ---------------------------------------------------------------------------


def test_get_valid_tracks_configured_pair_returns_frozenset():
    """Configured (station, data_source) pairs return a frozenset of tracks."""
    tracks = get_valid_tracks("GCT", "LIRR")
    assert isinstance(tracks, frozenset)
    # All 12 LIRR Madison tracks (3 levels x 4 tracks)
    assert tracks == frozenset(
        {
            "201",
            "202",
            "203",
            "204",
            "301",
            "302",
            "303",
            "304",
            "401",
            "402",
            "403",
            "404",
        }
    )


def test_get_valid_tracks_unconfigured_pair_returns_none():
    """Unconfigured (station, data_source) pairs return None (no validation)."""
    # GCT MNR is not in VALIDATED_TRACKS (our prediction list is partial)
    assert get_valid_tracks("GCT", "MNR") is None
    # Random station
    assert get_valid_tracks("NOT_A_STATION", "LIRR") is None
    # Right station, wrong data source
    assert get_valid_tracks("GCT", "NJT") is None


# ---------------------------------------------------------------------------
# validate_track
# ---------------------------------------------------------------------------


def test_validate_track_none_or_empty_returns_none():
    """Empty input is always dropped (no warning emitted)."""
    assert validate_track("GCT", None, "LIRR") is None
    assert validate_track("GCT", "", "LIRR") is None


def test_validate_track_accepts_known_valid_track():
    """Track in the configured set passes through unchanged."""
    assert validate_track("GCT", "301", "LIRR") == "301"
    assert validate_track("GCT", "204", "LIRR") == "204"
    assert validate_track("GCT", "404", "LIRR") == "404"


def test_validate_track_rejects_implausible_track_at_validated_pair():
    """The reported bug: LIRR reporting track '1' at GCT must be rejected."""
    assert validate_track("GCT", "1", "LIRR", train_id="L1664") is None
    # Also rejects other values not in the set
    assert validate_track("GCT", "13", "LIRR") is None  # that's an MNR track
    assert validate_track("GCT", "205", "LIRR") is None  # not a real GCM track


def test_validate_track_passes_through_unconfigured_pair():
    """Without a configured validation set, values pass through unchanged."""
    # GCT MNR: we haven't enumerated all MNR tracks, so no validation fires
    assert validate_track("GCT", "13", "MNR") == "13"
    assert validate_track("GCT", "41", "MNR") == "41"  # would be rejected by MNR list
    # Random station
    assert validate_track("XYZ", "99", "NJT") == "99"
    # Subway (no validation configured)
    assert validate_track("S631", "1", "SUBWAY") == "1"


def test_validate_track_rejection_emits_warning(caplog):
    """Rejections log a structured warning so feed quality is observable."""
    import logging

    caplog.set_level(logging.WARNING)
    result = validate_track("GCT", "1", "LIRR", train_id="L1664")
    assert result is None
    # Find our warning (structlog routes through stdlib logging in tests)
    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "track_value_implausible" in m for m in messages
    ), f"Expected 'track_value_implausible' warning; got: {messages}"


def test_validate_track_accepts_every_track_in_each_validated_set():
    """Every track we've enumerated for validation must pass its own check.

    Guards against typos in VALIDATED_TRACKS that would silently reject
    legitimate tracks.
    """
    from trackrat.config.station_configs import VALIDATED_TRACKS

    assert VALIDATED_TRACKS, "Expected at least one (station, data_source) entry"
    for (station, data_source), tracks in VALIDATED_TRACKS.items():
        assert tracks, f"Empty track set for {station}/{data_source}"
        for track in tracks:
            assert validate_track(station, track, data_source) == track


# ---------------------------------------------------------------------------
# validate_track — warning volume (issue #1792)
#
# LIRR reports tracks "1"-"4" at Grand Central Madison on every poll, for every
# train, and the feed is re-parsed once per collection cycle *and* once per JIT
# API request. Warning per rejection made this 46% of all production warning
# volume. These pin the dedup without letting it hide genuinely new information.
# ---------------------------------------------------------------------------


def _implausible_warnings(caplog):
    """The track_value_implausible records captured so far."""
    return [r for r in caplog.records if "track_value_implausible" in r.getMessage()]


def test_repeated_identical_rejection_warns_only_once(caplog):
    """The production case: the same bad value on every poll is one fact.

    Simulates 50 stops reporting track "1" at GCT across several polls. Before
    the fix this produced 50 warnings; it must now produce exactly one.
    """
    import logging

    caplog.set_level(logging.WARNING)

    for i in range(50):
        assert validate_track("GCT", "1", "LIRR", train_id=f"L{1000 + i}") is None

    warnings = _implausible_warnings(caplog)
    assert len(warnings) == 1, (
        f"Expected exactly 1 warning for 50 identical rejections, got "
        f"{len(warnings)}: {[w.getMessage() for w in warnings]}"
    )


def test_each_distinct_bad_value_warns_once(caplog):
    """Dedup must not hide a value we have not seen before.

    "1"-"4" are four distinct facts about the feed, so all four are reported —
    but each only once, even though every one repeats.
    """
    import logging

    caplog.set_level(logging.WARNING)

    for _poll in range(3):
        for track in ("1", "2", "3", "4"):
            assert validate_track("GCT", track, "LIRR") is None

    warnings = _implausible_warnings(caplog)
    assert len(warnings) == 4, (
        f"Expected 1 warning per distinct value (4 total) across 3 polls, got "
        f"{len(warnings)}: {[w.getMessage() for w in warnings]}"
    )


def test_dedup_is_keyed_per_station_and_data_source(caplog, monkeypatch):
    """The same bad value at a new station, or from a new feed, is new information.

    Guards against keying the memo on the track value alone, which would let the
    first rejection anywhere silence every other station and source. GCT/LIRR is
    the only configured pair today, so two more are added for the duration of
    this test to give the key something real to distinguish.
    """
    import logging

    from trackrat.config import station_configs

    caplog.set_level(logging.WARNING)

    monkeypatch.setitem(
        station_configs.VALIDATED_TRACKS, ("GCT", "MNR"), frozenset({"101"})
    )
    monkeypatch.setitem(
        station_configs.VALIDATED_TRACKS, ("ZZZ", "LIRR"), frozenset({"101"})
    )

    # Identical track value across three distinct (station, source) pairs.
    for _repeat in range(3):
        assert validate_track("GCT", "1", "LIRR") is None
        assert validate_track("GCT", "1", "MNR") is None
        assert validate_track("ZZZ", "1", "LIRR") is None

    warnings = _implausible_warnings(caplog)
    assert len(warnings) == 3, (
        "Each (station, source) pair must warn once for the same value — "
        f"keying on the track alone would give 1; got {len(warnings)}: "
        f"{[w.getMessage() for w in warnings]}"
    )
    assert sanitize_module._implausible_track_warned == {
        ("GCT", "LIRR", "1"),
        ("GCT", "MNR", "1"),
        ("ZZZ", "LIRR", "1"),
    }


def test_memo_is_bounded_and_keeps_warning_after_overflow(caplog):
    """A feed emitting unbounded distinct junk must not grow the memo forever.

    Memory stays fixed, and — importantly — rejections keep being reported
    after the reset rather than going silent.
    """
    import logging

    caplog.set_level(logging.WARNING)

    cap = sanitize_module._MAX_IMPLAUSIBLE_TRACK_KEYS
    for i in range(cap + 10):
        assert validate_track("GCT", f"J{i}", "LIRR") is None

    assert len(sanitize_module._implausible_track_warned) <= cap, (
        f"Memo grew past its {cap}-key ceiling: "
        f"{len(sanitize_module._implausible_track_warned)}"
    )
    # Every value was distinct, so every one is genuinely new and must be logged.
    warnings = _implausible_warnings(caplog)
    assert len(warnings) == cap + 10, (
        f"Distinct values must always warn, including after the memo reset; "
        f"expected {cap + 10}, got {len(warnings)}"
    )


def test_valid_track_never_populates_the_memo():
    """Accepted values must not consume memo space (or suppress later warnings)."""
    for track in ("201", "302", "404"):
        assert validate_track("GCT", track, "LIRR") == track
    assert sanitize_module._implausible_track_warned == set()


def test_unconfigured_pair_never_populates_the_memo():
    """Pass-through pairs skip validation entirely, so they cannot fill the memo."""
    assert validate_track("GCT", "13", "MNR") == "13"
    assert validate_track("S631", "1", "SUBWAY") == "1"
    assert sanitize_module._implausible_track_warned == set()


def test_rejection_still_returns_none_when_warning_is_suppressed(caplog):
    """Dedup is a logging concern only — it must never change what is served.

    The rider-visible behaviour (no track rather than a bogus one) has to be
    identical on the first rejection and the thousandth, and the suppression
    has to be real while that holds.
    """
    import logging

    caplog.set_level(logging.WARNING)

    for _ in range(1000):
        assert validate_track("GCT", "1", "LIRR") is None

    assert len(_implausible_warnings(caplog)) == 1, (
        "999 of the 1000 rejections must be suppressed while every one still "
        "returns None"
    )
