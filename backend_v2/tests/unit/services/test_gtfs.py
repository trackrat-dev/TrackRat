"""
Unit tests for GTFS static schedule service.
"""

from datetime import date, datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from trackrat.services.gtfs import (
    GTFSService,
    GTFS_DOWNLOAD_INTERVAL_HOURS,
    NJT_LINE_CODE_MAPPING,
)
from trackrat.models.database import (
    GTFSCalendar,
    GTFSCalendarDate,
    GTFSFeedInfo,
)
from trackrat.utils.time import ET


class TestGTFSTimeParsing:
    """Tests for GTFS time parsing helper."""

    def setup_method(self):
        self.service = GTFSService()

    def test_parse_normal_time(self):
        """Test parsing normal HH:MM:SS time."""
        target_date = date(2026, 1, 20)
        result = self.service._parse_gtfs_time("14:30:00", target_date)

        assert result is not None
        assert result.hour == 14
        assert result.minute == 30
        assert result.second == 0
        assert result.date() == target_date

    def test_parse_overnight_time(self):
        """Test parsing times >= 24:00 for overnight trips."""
        target_date = date(2026, 1, 20)
        result = self.service._parse_gtfs_time("25:30:00", target_date)

        assert result is not None
        assert result.hour == 1
        assert result.minute == 30
        # Should be next day
        assert result.date() == date(2026, 1, 21)

    def test_parse_late_overnight_time(self):
        """Test parsing times like 26:15 (2:15 AM next day)."""
        target_date = date(2026, 1, 20)
        result = self.service._parse_gtfs_time("26:15:00", target_date)

        assert result is not None
        assert result.hour == 2
        assert result.minute == 15
        assert result.date() == date(2026, 1, 21)

    def test_parse_empty_time(self):
        """Test parsing empty time string returns None."""
        result = self.service._parse_gtfs_time("", date(2026, 1, 20))
        assert result is None

    def test_parse_invalid_time(self):
        """Test parsing invalid time string returns None."""
        result = self.service._parse_gtfs_time("invalid", date(2026, 1, 20))
        assert result is None

    def test_parse_time_without_seconds(self):
        """Test parsing HH:MM format (no seconds)."""
        result = self.service._parse_gtfs_time("14:30", date(2026, 1, 20))

        assert result is not None
        assert result.hour == 14
        assert result.minute == 30
        assert result.second == 0


class TestGTFSDateParsing:
    """Tests for GTFS date parsing helper."""

    def setup_method(self):
        self.service = GTFSService()

    def test_parse_valid_date(self):
        """Test parsing YYYYMMDD format."""
        result = self.service._parse_gtfs_date("20260120")

        assert result == date(2026, 1, 20)

    def test_parse_empty_date(self):
        """Test parsing empty date returns today."""
        result = self.service._parse_gtfs_date("")

        assert result == date.today()

    def test_parse_invalid_date(self):
        """Test parsing invalid date returns today."""
        result = self.service._parse_gtfs_date("invalid")

        assert result == date.today()

    def test_parse_malformed_date_with_correct_length(self):
        """Test parsing date with correct length but invalid values (e.g., month=13)."""
        # This would have crashed before the ValueError handling was added
        result = self.service._parse_gtfs_date("20261340")

        # Should return today instead of crashing
        assert result == date.today()


class TestTrainIdExtraction:
    """Tests for train ID extraction from headsign."""

    def setup_method(self):
        self.service = GTFSService()

    def test_extract_train_id_with_number(self):
        """Test extracting train number from headsign."""
        result = self.service._extract_train_id("Train 3245 to Trenton")
        assert result == "3245"

    def test_extract_train_id_number_only(self):
        """Test extracting when headsign is just a number."""
        result = self.service._extract_train_id("3840")
        assert result == "3840"

    def test_extract_train_id_no_number(self):
        """Test returns None when no train number in headsign."""
        result = self.service._extract_train_id("To Trenton")
        assert result is None

    def test_extract_train_id_empty(self):
        """Test returns None for empty headsign."""
        result = self.service._extract_train_id("")
        assert result is None


class TestBlockIdExtraction:
    """Tests for train ID extraction from GTFS block_id.

    IMPORTANT: block_id is NOT a train number - it's an equipment/vehicle identifier.
    The same block_id can be assigned to multiple trips throughout the day.
    Therefore, _extract_train_id_from_block_id should ALWAYS return None.

    These tests verify the function correctly rejects block_id as a train identifier.
    """

    def setup_method(self):
        self.service = GTFSService()

    def test_numeric_block_id_returns_none(self):
        """Numeric block_id should NOT be used as train_id - returns None.

        block_id like "4608" is an equipment identifier, not a train number.
        Using it as train_id causes wrong train numbers to be displayed.
        """
        result = self.service._extract_train_id_from_block_id("4608")
        assert result is None

    def test_block_id_with_leading_zeros_returns_none(self):
        """block_id with leading zeros should NOT be used as train_id.

        block_id like "0301" becomes "301" when stripped, but this is
        an equipment identifier, not a real train number (NEC trains are 4-digit).
        """
        result = self.service._extract_train_id_from_block_id("0301")
        assert result is None

    def test_single_zero_block_id_returns_none(self):
        """Even single '0' block_id should return None."""
        result = self.service._extract_train_id_from_block_id("0")
        assert result is None

    def test_quoted_block_id_returns_none(self):
        """Quoted block_id should NOT be used as train_id."""
        result = self.service._extract_train_id_from_block_id('"4662"')
        assert result is None

    def test_alphanumeric_block_id_returns_none(self):
        """Alphanumeric block_id (light rail) returns None."""
        result = self.service._extract_train_id_from_block_id("342JC001")
        assert result is None

    def test_empty_block_id_returns_none(self):
        """Empty block_id returns None."""
        result = self.service._extract_train_id_from_block_id("")
        assert result is None

    def test_none_block_id_returns_none(self):
        """None block_id returns None."""
        result = self.service._extract_train_id_from_block_id(None)
        assert result is None


class TestRateLimiting:
    """Tests for GTFS download rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limit_prevents_recent_download(self):
        """Test that download is skipped if recently downloaded."""
        service = GTFSService()

        # Create a mock feed info that was downloaded 1 hour ago
        mock_feed_info = MagicMock(spec=GTFSFeedInfo)
        mock_feed_info.last_downloaded_at = datetime.now(ET) - timedelta(hours=1)

        mock_db = AsyncMock()

        with patch.object(
            service, "_get_or_create_feed_info", return_value=mock_feed_info
        ):
            result = await service.refresh_feed(mock_db, "NJT", force=False)

        # Should return False (skipped due to rate limit)
        assert result is False

    @pytest.mark.asyncio
    async def test_rate_limit_allows_old_download(self):
        """Test that download is allowed if last download was long ago."""
        service = GTFSService()

        # Create a mock feed info that was downloaded 25 hours ago
        mock_feed_info = MagicMock(spec=GTFSFeedInfo)
        mock_feed_info.last_downloaded_at = datetime.now(ET) - timedelta(hours=25)

        mock_db = AsyncMock()

        # We need to mock the actual HTTP download and parsing
        with (
            patch.object(
                service, "_get_or_create_feed_info", return_value=mock_feed_info
            ),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(service, "_parse_and_store_gtfs", return_value={}),
        ):
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = b"mock zip content"
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            mock_db.flush = AsyncMock()
            mock_db.commit = AsyncMock()

            result = await service.refresh_feed(mock_db, "NJT", force=False)

        # Should return True (download was performed)
        assert result is True

    @pytest.mark.asyncio
    async def test_force_bypasses_rate_limit(self):
        """Test that force=True bypasses rate limiting."""
        service = GTFSService()

        # Create a mock feed info that was downloaded 1 minute ago
        mock_feed_info = MagicMock(spec=GTFSFeedInfo)
        mock_feed_info.last_downloaded_at = datetime.now(ET) - timedelta(minutes=1)

        mock_db = AsyncMock()

        with (
            patch.object(
                service, "_get_or_create_feed_info", return_value=mock_feed_info
            ),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(service, "_parse_and_store_gtfs", return_value={}),
        ):
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = b"mock zip content"
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            mock_db.flush = AsyncMock()
            mock_db.commit = AsyncMock()

            result = await service.refresh_feed(mock_db, "NJT", force=True)

        # Should return True despite recent download because force=True
        assert result is True


class TestActiveServiceIds:
    """Tests for determining active service IDs on a given date."""

    @pytest.mark.asyncio
    async def test_weekday_service(self):
        """Test getting active services for a weekday."""
        service = GTFSService()

        # Monday = 0
        target_date = date(2026, 1, 19)  # This is a Monday

        mock_db = AsyncMock()

        # Mock calendar query result
        mock_result = MagicMock()
        mock_result.all.return_value = [("SERVICE_WEEKDAY",)]
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Second call for calendar_dates should return empty
        async def mock_execute(query):
            result = MagicMock()
            # First call is calendar, second is calendar_dates
            if "gtfs_calendar_dates" in str(query):
                result.all.return_value = []
            else:
                result.all.return_value = [("SERVICE_WEEKDAY",)]
            return result

        mock_db.execute = mock_execute

        result = await service.get_active_service_ids(mock_db, "NJT", target_date)

        assert "SERVICE_WEEKDAY" in result

    @pytest.mark.asyncio
    async def test_service_exception_added(self):
        """Test that calendar_dates additions are included."""
        service = GTFSService()
        target_date = date(2026, 1, 20)

        mock_db = AsyncMock()

        call_count = [0]

        async def mock_execute(query):
            result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                # Calendar query - no regular service
                result.all.return_value = []
            else:
                # Calendar dates query - service added for this date
                result.all.return_value = [
                    ("SPECIAL_SERVICE", 1)
                ]  # exception_type=1 means added
            return result

        mock_db.execute = mock_execute

        result = await service.get_active_service_ids(mock_db, "NJT", target_date)

        assert "SPECIAL_SERVICE" in result

    @pytest.mark.asyncio
    async def test_service_exception_removed(self):
        """Test that calendar_dates removals are excluded."""
        service = GTFSService()
        target_date = date(2026, 1, 20)

        mock_db = AsyncMock()

        call_count = [0]

        async def mock_execute(query):
            result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                # Calendar query - regular service
                result.all.return_value = [("REGULAR_SERVICE",)]
            else:
                # Calendar dates query - service removed for this date
                result.all.return_value = [
                    ("REGULAR_SERVICE", 2)
                ]  # exception_type=2 means removed
            return result

        mock_db.execute = mock_execute

        result = await service.get_active_service_ids(mock_db, "NJT", target_date)

        # Service should be removed
        assert "REGULAR_SERVICE" not in result


class TestStationMapping:
    """Tests for GTFS station mapping functions."""

    def test_amtrak_station_mapping(self):
        """Test mapping Amtrak GTFS stop_id to internal code."""
        from trackrat.config.stations import map_gtfs_stop_to_station_code

        # Amtrak uses their standard codes as stop_id
        result = map_gtfs_stop_to_station_code("NYP", "New York Penn Station", "AMTRAK")
        assert result == "NY"

        result = map_gtfs_stop_to_station_code("TRE", "Trenton", "AMTRAK")
        assert result == "TR"

    def test_njt_station_mapping_by_name(self):
        """Test mapping NJT GTFS stop by name."""
        from trackrat.config.stations import map_gtfs_stop_to_station_code

        # NJT uses numeric IDs, so we match by name
        result = map_gtfs_stop_to_station_code("12345", "New York Penn Station", "NJT")
        assert result == "NY"

        result = map_gtfs_stop_to_station_code("67890", "Trenton", "NJT")
        assert result == "TR"

    def test_unmapped_station_returns_none(self):
        """Test that unmapped stations return None."""
        from trackrat.config.stations import map_gtfs_stop_to_station_code

        result = map_gtfs_stop_to_station_code("99999", "Unknown Station XYZ", "NJT")
        assert result is None


class TestDownloadIntervalConstant:
    """Test the download interval constant is reasonable."""

    def test_download_interval_is_24_hours(self):
        """Verify download interval is 24 hours as specified."""
        assert GTFS_DOWNLOAD_INTERVAL_HOURS == 24


class TestGTFSTripIdentifiers:
    """Tests verifying GTFS trip identifier behavior.

    These tests ensure that:
    1. block_id is NOT used as train_id (it's an equipment identifier)
    2. gtfs_trip_id is used as the unique identifier for lookups
    3. Train details can be correctly retrieved using gtfs_trip_id

    Background:
    - GTFS block_id represents equipment/vehicle, not train number
    - Same block_id can appear on multiple trips throughout the day
    - Using block_id as train_id caused wrong trains to be displayed
    - gtfs_trip_id is guaranteed unique per trip within a data source
    """

    def setup_method(self):
        self.service = GTFSService()

    def test_block_id_is_not_train_id(self):
        """Verify that block_id values are NOT treated as train IDs.

        Real example from NJT GTFS:
        - trip_id=174 has block_id="6222" (Montclair-Boonton Line)
        - trip_id=2420 has block_id="3800" (Northeast Corridor)

        Block IDs are equipment identifiers, NOT train numbers.
        The same block_id can be assigned to completely different trips.
        """
        # All these should return None - block_id is not a valid train identifier
        assert self.service._extract_train_id_from_block_id("6222") is None
        assert self.service._extract_train_id_from_block_id("3800") is None
        assert self.service._extract_train_id_from_block_id("0657") is None

    def test_block_id_documentation_is_accurate(self):
        """Verify the function documents WHY it returns None.

        The function should have clear documentation explaining that
        block_id is an equipment identifier, not a train number.
        """
        docstring = self.service._extract_train_id_from_block_id.__doc__
        assert docstring is not None
        assert "equipment" in docstring.lower() or "vehicle" in docstring.lower()
        assert "None" in docstring or "not" in docstring.lower()

    def test_extract_train_id_from_headsign_handles_numbers(self):
        """Test headsign extraction still works for train numbers in headsign.

        Some GTFS feeds include train numbers in headsign (e.g., "Train 3245 to Trenton").
        This is the valid way to extract train IDs from GTFS data.
        """
        # Number in headsign text
        result = self.service._extract_train_id("Train 3245 to Trenton")
        assert result == "3245"

        # Just the number
        result = self.service._extract_train_id("3840")
        assert result == "3840"

        # No number in headsign
        result = self.service._extract_train_id("To New York Penn Station")
        assert result is None


class TestTrainSearchConsistency:
    """Tests verifying train search and details are consistent.

    These tests document the expected behavior:
    1. Departure listing shows gtfs_trip_id as the train identifier
    2. Clicking a train uses the same gtfs_trip_id for lookup
    3. Train details page shows the same identifier

    This prevents the bug where clicking "Train 174" showed details
    for "Train 6222" (a completely different route).
    """

    def test_gtfs_trip_id_is_unique_identifier_concept(self):
        """Document that gtfs_trip_id should be used as the unique identifier.

        GTFS trip_id is:
        - Unique per trip within a data source
        - Stable across GTFS feed updates (usually)
        - The correct key for looking up trip details

        block_id (previously used incorrectly) is:
        - An equipment/vehicle identifier
        - Reused across multiple trips per day
        - NOT unique and NOT suitable for lookups
        """
        # This test documents the design decision
        # The actual implementation ensures gtfs_trip_id is used
        service = GTFSService()

        # Verify block_id extraction returns None (not used as train_id)
        assert service._extract_train_id_from_block_id("any_value") is None

        # Headsign extraction is still valid for sources that include train numbers
        assert service._extract_train_id("3245") == "3245"


class TestNJTLineCodeMapping:
    """Tests for NJT GTFS route_short_name to API line code mapping.

    NJT GTFS uses route_short_name values like "NEC", "NJCL", "BNTN", etc.
    NJT real-time API returns full line names like "Northeast Corridor" which
    get truncated to 2 characters ("No").

    This mapping is critical for deduplication between GTFS scheduled data
    and real-time API data - if line codes don't match, the fallback
    deduplication key (line:source:time) won't match and duplicates appear.
    """

    def test_mapping_contains_actual_gtfs_routes(self):
        """Test that actual NJT GTFS route_short_name values are mapped."""
        from trackrat.services.gtfs import NJT_LINE_CODE_MAPPING

        # Actual NJT GTFS route_short_name values (from GTFS feed)
        expected_routes = {
            "NEC",    # Northeast Corridor
            "NJCL",   # North Jersey Coast Line
            "NJCLL",  # North Jersey Coast Line (variation)
            "MNE",    # Morris & Essex Line
            "MNEG",   # Gladstone Branch
            "BNTN",   # Montclair-Boonton Line
            "BNTNM",  # Montclair-Boonton Line (variation)
            "MNBN",   # Main/Bergen County Line
            "MNBNP",  # Port Jervis Line
            "PASC",   # Pascack Valley Line
            "RARV",   # Raritan Valley Line
            "ATLC",   # Atlantic City Rail Line
            "PRIN",   # Princeton Shuttle
        }

        for route in expected_routes:
            assert route in NJT_LINE_CODE_MAPPING, f"Missing mapping for {route}"

    def test_nec_maps_to_no(self):
        """Northeast Corridor maps to 'No' (from 'Northeast Corridor' truncated)."""
        from trackrat.services.gtfs import NJT_LINE_CODE_MAPPING

        assert NJT_LINE_CODE_MAPPING["NEC"] == "No"

    def test_njcl_maps_to_no(self):
        """North Jersey Coast Line maps to 'No' (from 'North Jersey...' truncated)."""
        from trackrat.services.gtfs import NJT_LINE_CODE_MAPPING

        assert NJT_LINE_CODE_MAPPING["NJCL"] == "No"

    def test_morris_essex_maps_to_mo(self):
        """Morris & Essex Line maps to 'Mo' (from 'Morris and Essex' truncated)."""
        from trackrat.services.gtfs import NJT_LINE_CODE_MAPPING

        assert NJT_LINE_CODE_MAPPING["MNE"] == "Mo"

    def test_gladstone_maps_to_gl(self):
        """Gladstone Branch maps to 'Gl' (from 'Gladstone Branch' truncated)."""
        from trackrat.services.gtfs import NJT_LINE_CODE_MAPPING

        assert NJT_LINE_CODE_MAPPING["MNEG"] == "Gl"

    def test_montclair_boonton_maps_to_mo(self):
        """Montclair-Boonton Line maps to 'Mo' (from 'Montclair-Boonton' truncated)."""
        from trackrat.services.gtfs import NJT_LINE_CODE_MAPPING

        assert NJT_LINE_CODE_MAPPING["BNTN"] == "Mo"

    def test_raritan_valley_maps_to_ra(self):
        """Raritan Valley Line maps to 'Ra'."""
        from trackrat.services.gtfs import NJT_LINE_CODE_MAPPING

        assert NJT_LINE_CODE_MAPPING["RARV"] == "Ra"

    def test_pascack_valley_maps_to_pa(self):
        """Pascack Valley Line maps to 'Pa'."""
        from trackrat.services.gtfs import NJT_LINE_CODE_MAPPING

        assert NJT_LINE_CODE_MAPPING["PASC"] == "Pa"

    def test_line_codes_are_two_chars(self):
        """Verify all mapped line codes are 2 characters for consistency with API."""
        from trackrat.services.gtfs import NJT_LINE_CODE_MAPPING

        for gtfs_code, api_code in NJT_LINE_CODE_MAPPING.items():
            assert len(api_code) == 2, f"{gtfs_code} -> {api_code} should be 2 chars"


class TestEffectiveTrainId:
    """Tests for effective_train_id logic in GTFS departures.

    The effective_train_id determines what train ID is displayed to users:
    - For Amtrak: Use train_id from trip_short_name (e.g., "112")
    - For NJT: Use gtfs_trip_id (NJT GTFS has no trip_short_name)

    This ensures:
    1. Amtrak trains show real train numbers (112, 188, etc.)
    2. NJT trains use consistent GTFS trip_id for lookup
    3. Train details lookup works correctly for both
    """

    def test_concept_use_train_id_when_available(self):
        """Document the effective_train_id selection logic.

        When a trip has a train_id (from trip_short_name, e.g., Amtrak "112"),
        that should be used as effective_train_id because it's the real
        train number passengers see on boards and schedules.
        """
        # This documents the expected behavior
        # The actual logic: effective_train_id = train_id if train_id else gtfs_trip_id

        # Simulating Amtrak with trip_short_name
        train_id = "112"  # From trip_short_name
        gtfs_trip_id = "123456789"  # GTFS internal ID
        effective_train_id = train_id if train_id else gtfs_trip_id
        assert effective_train_id == "112"

    def test_concept_fallback_to_trip_id_when_no_train_id(self):
        """Document fallback to gtfs_trip_id when train_id is not available.

        NJT GTFS does not have trip_short_name, so train_id is None.
        In this case, gtfs_trip_id is used as the identifier.
        """
        # Simulating NJT without trip_short_name
        train_id = None  # NJT has no trip_short_name
        gtfs_trip_id = "2508"  # GTFS trip_id
        effective_train_id = train_id if train_id else gtfs_trip_id
        assert effective_train_id == "2508"

    def test_empty_train_id_uses_trip_id(self):
        """Empty string train_id should use gtfs_trip_id."""
        train_id = ""  # Empty but not None
        gtfs_trip_id = "2508"
        effective_train_id = train_id if train_id else gtfs_trip_id
        assert effective_train_id == "2508"
