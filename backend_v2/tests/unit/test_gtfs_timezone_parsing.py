"""
Tests for issue #920: GTFS static time parsing must use provider-specific timezones.

_parse_gtfs_time previously hardcoded Eastern Time for all providers, causing
Metra (Central) stops to be 1 hour early and BART (Pacific) stops 3 hours early.
"""

from datetime import date, time, datetime

import pytz

from trackrat.services.gtfs import GTFSService
from trackrat.utils.time import CT, ET, PT, PROVIDER_TIMEZONE


class TestParseGtfsTimeTimezones:
    """Verify _parse_gtfs_time respects provider timezones."""

    def setup_method(self):
        self.gtfs = GTFSService()
        self.target_date = date(2026, 4, 9)

    def test_eastern_time_default_when_no_data_source(self):
        """Without data_source, should default to Eastern Time."""
        result = self.gtfs._parse_gtfs_time("14:30:00", self.target_date)
        assert result is not None
        assert result.tzinfo is not None
        assert result.tzname() in ("EDT", "EST")
        assert result.hour == 14
        assert result.minute == 30

    def test_eastern_time_for_njt(self):
        """NJT should use Eastern Time."""
        result = self.gtfs._parse_gtfs_time("14:30:00", self.target_date, "NJT")
        assert result is not None
        assert result.tzname() in ("EDT", "EST")
        assert result.hour == 14

    def test_central_time_for_metra(self):
        """Metra should use Central Time, not Eastern."""
        result = self.gtfs._parse_gtfs_time("08:00:00", self.target_date, "METRA")
        assert result is not None
        # Verify timezone is Central
        assert result.tzname() in ("CDT", "CST")
        assert result.hour == 8
        assert result.minute == 0
        # This is 8:00 AM CT, which is 9:00 AM ET
        et_result = result.astimezone(ET)
        assert et_result.hour == 9, (
            f"8:00 AM CT should be 9:00 AM ET, but got {et_result.hour}:00 AM ET. "
            f"This means Metra times are still being parsed as ET instead of CT."
        )

    def test_pacific_time_for_bart(self):
        """BART should use Pacific Time, not Eastern."""
        result = self.gtfs._parse_gtfs_time("08:00:00", self.target_date, "BART")
        assert result is not None
        # Verify timezone is Pacific
        assert result.tzname() in ("PDT", "PST")
        assert result.hour == 8
        assert result.minute == 0
        # This is 8:00 AM PT, which is 11:00 AM ET
        et_result = result.astimezone(ET)
        assert et_result.hour == 11, (
            f"8:00 AM PT should be 11:00 AM ET, but got {et_result.hour}:00 AM ET. "
            f"This means BART times are still being parsed as ET instead of PT."
        )

    def test_eastern_time_for_lirr(self):
        """LIRR should use Eastern Time."""
        result = self.gtfs._parse_gtfs_time("14:30:00", self.target_date, "LIRR")
        assert result is not None
        assert result.tzname() in ("EDT", "EST")
        assert result.hour == 14

    def test_eastern_time_for_mbta(self):
        """MBTA should use Eastern Time."""
        result = self.gtfs._parse_gtfs_time("14:30:00", self.target_date, "MBTA")
        assert result is not None
        assert result.tzname() in ("EDT", "EST")

    def test_eastern_time_for_wmata(self):
        """WMATA should use Eastern Time."""
        result = self.gtfs._parse_gtfs_time("14:30:00", self.target_date, "WMATA")
        assert result is not None
        assert result.tzname() in ("EDT", "EST")

    def test_eastern_time_for_unknown_provider(self):
        """Unknown providers should default to Eastern Time."""
        result = self.gtfs._parse_gtfs_time("14:30:00", self.target_date, "UNKNOWN")
        assert result is not None
        assert result.tzname() in ("EDT", "EST")

    def test_overnight_trip_metra(self):
        """Overnight GTFS times (>= 24:00) should still use correct timezone."""
        result = self.gtfs._parse_gtfs_time("25:30:00", self.target_date, "METRA")
        assert result is not None
        assert result.tzname() in ("CDT", "CST")
        # 25:30 = next day 01:30 CT
        assert result.day == self.target_date.day + 1
        assert result.hour == 1
        assert result.minute == 30

    def test_empty_string_returns_none(self):
        """Empty string should return None regardless of provider."""
        assert self.gtfs._parse_gtfs_time("", self.target_date, "METRA") is None

    def test_none_string_returns_none(self):
        """None-ish input should return None."""
        assert self.gtfs._parse_gtfs_time("", self.target_date) is None

    def test_invalid_time_returns_none(self):
        """Invalid time strings should return None."""
        assert self.gtfs._parse_gtfs_time("abc", self.target_date, "METRA") is None
        assert self.gtfs._parse_gtfs_time(":", self.target_date, "BART") is None


class TestProviderTimezoneCompleteness:
    """Verify PROVIDER_TIMEZONE covers all GTFS feed providers."""

    def test_all_gtfs_feed_providers_have_timezone(self):
        """Every provider with a GTFS feed URL should have a timezone mapping."""
        from trackrat.services.gtfs import GTFS_FEED_URLS

        missing = set(GTFS_FEED_URLS.keys()) - set(PROVIDER_TIMEZONE.keys())
        assert not missing, (
            f"Providers with GTFS feeds but no timezone mapping: {missing}. "
            f"Add entries to PROVIDER_TIMEZONE in utils/time.py."
        )

    def test_metra_is_central_time(self):
        """Metra must be mapped to Central Time."""
        assert PROVIDER_TIMEZONE["METRA"] == CT

    def test_bart_is_pacific_time(self):
        """BART must be mapped to Pacific Time."""
        assert PROVIDER_TIMEZONE["BART"] == PT

    def test_eastern_providers(self):
        """Eastern Time providers should be mapped to ET."""
        for provider in ("NJT", "AMTRAK", "PATH", "PATCO", "LIRR", "MNR",
                         "SUBWAY", "MBTA", "WMATA"):
            assert PROVIDER_TIMEZONE[provider] == ET, (
                f"{provider} should be Eastern Time but is mapped to "
                f"{PROVIDER_TIMEZONE[provider]}"
            )

    def test_pt_timezone_constant_exists(self):
        """PT timezone constant should be available for BART."""
        assert PT == pytz.timezone("America/Los_Angeles")
