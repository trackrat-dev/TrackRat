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
            "NEC",  # Northeast Corridor
            "NJCL",  # North Jersey Coast Line
            "NJCLL",  # North Jersey Coast Line (variation)
            "MNE",  # Morris & Essex Line
            "MNEG",  # Gladstone Branch
            "BNTN",  # Montclair-Boonton Line
            "BNTNM",  # Montclair-Boonton Line (variation)
            "MNBN",  # Main/Bergen County Line
            "MNBNP",  # Port Jervis Line
            "PASC",  # Pascack Valley Line
            "RARV",  # Raritan Valley Line
            "ATLC",  # Atlantic City Rail Line
            "PRIN",  # Princeton Shuttle
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


class TestDataSourceFiltering:
    """Tests for data_source filtering in train details lookup.

    The data_source parameter allows iOS to specify exactly which transit system
    a train belongs to, avoiding ambiguity when train IDs collide between systems.

    Key scenarios:
    1. With data_source: Only search that source (train_id first, then trip_id)
    2. Without data_source: Two-phase search across all sources
       - Phase 1: Search all sources for train_id match
       - Phase 2: Fall back to trip_id match
    """

    def test_concept_data_source_limits_search_scope(self):
        """When data_source is provided, only that source is searched.

        Example: iOS shows Amtrak train 174. When user clicks it, iOS passes
        data_source='AMTRAK'. Backend searches only AMTRAK data, avoiding
        collision with NJT trip_id=174.
        """
        # Simulating the search scope decision
        data_source = "AMTRAK"
        all_sources = ["NJT", "AMTRAK", "PATH", "PATCO"]

        sources_to_search = [data_source] if data_source else all_sources

        assert sources_to_search == ["AMTRAK"]
        assert "NJT" not in sources_to_search

    def test_concept_no_data_source_searches_all(self):
        """Without data_source, all sources are searched.

        This is the fallback for backward compatibility and cases where
        the data_source is not known.
        """
        data_source = None
        all_sources = ["NJT", "AMTRAK", "PATH", "PATCO"]

        sources_to_search = [data_source] if data_source else all_sources

        assert sources_to_search == all_sources

    def test_concept_two_phase_search_priority(self):
        """Two-phase search prioritizes train_id over trip_id.

        Problem scenario:
        - User searches for train "174"
        - NJT has trip_id=174 (GTFS internal ID)
        - Amtrak has train_id=174 (actual train number)

        Solution: Phase 1 checks train_id across all sources first.
        If Amtrak has train_id=174, it wins over NJT's trip_id=174.
        """
        # Simulating the two-phase search decision
        search_value = "174"

        # Mock data representing what might be found
        njt_train_id_match = None  # NJT has no train 174
        njt_trip_id_match = {"trip_id": "174", "source": "NJT"}
        amtrak_train_id_match = {"train_id": "174", "source": "AMTRAK"}

        # Phase 1: Check train_id matches first
        phase1_matches = [m for m in [njt_train_id_match, amtrak_train_id_match] if m]
        if phase1_matches:
            result = phase1_matches[0]
        else:
            # Phase 2: Fall back to trip_id
            phase2_matches = [m for m in [njt_trip_id_match] if m]
            result = phase2_matches[0] if phase2_matches else None

        assert result is not None
        assert result["source"] == "AMTRAK"  # Real train number wins

    def test_concept_train_id_collision_resolution(self):
        """Documents the train ID collision scenario this feature solves.

        Real-world bug: User sees Amtrak train 174 (Northeast Regional).
        Backend returns NJT trip with trip_id=174 instead because NJT
        is checked first in the iteration order.

        Fix: Two-phase search ensures train_id (real numbers) are checked
        before trip_id (GTFS internal IDs), and data_source parameter
        allows explicit filtering when the source is known.
        """
        # Before fix: NJT trip_id=174 wins because NJT checked first
        # After fix: Amtrak train_id=174 wins because train_id checked first

        # The key insight: GTFS trip_id is an internal identifier,
        # while train_id (from trip_short_name) is the real train number.
        # Real train numbers should always take priority.
        pass


class TestGetStaticStopTimes:
    """Tests for GTFSService.get_static_stop_times().

    Used by MTA collectors to backfill origin stops missing from GTFS-RT."""

    def setup_method(self):
        self.service = GTFSService()

    @pytest.mark.asyncio
    async def test_returns_stops_for_valid_trip(self):
        """Should return all stops ordered by stop_sequence with parsed times."""
        mock_db = AsyncMock()
        target_date = date(2026, 2, 6)

        # Mock get_active_service_ids
        with patch.object(
            self.service, "get_active_service_ids", return_value={"WD_26"}
        ):
            # Mock _find_trip_in_source to return a trip row
            mock_trip_row = MagicMock()
            mock_trip_row.id = 42
            with patch.object(
                self.service, "_find_trip_in_source", return_value=mock_trip_row
            ):
                # Mock the stop_times query
                mock_stop1 = MagicMock()
                mock_stop1.station_code = "GCT"
                mock_stop1.stop_sequence = 1
                mock_stop1.arrival_time = "08:00:00"
                mock_stop1.departure_time = "08:01:00"

                mock_stop2 = MagicMock()
                mock_stop2.station_code = "WDD"
                mock_stop2.stop_sequence = 2
                mock_stop2.arrival_time = "08:10:00"
                mock_stop2.departure_time = "08:11:00"

                mock_stop3 = MagicMock()
                mock_stop3.station_code = "JAM"
                mock_stop3.stop_sequence = 3
                mock_stop3.arrival_time = "08:20:00"
                mock_stop3.departure_time = None

                mock_result = MagicMock()
                mock_result.all.return_value = [mock_stop1, mock_stop2, mock_stop3]
                mock_db.execute = AsyncMock(return_value=mock_result)

                result = await self.service.get_static_stop_times(
                    mock_db, "LIRR", "GO103_25_181", target_date
                )

        assert result is not None
        assert len(result) == 3

        assert result[0]["station_code"] == "GCT"
        assert result[0]["stop_sequence"] == 1
        assert result[0]["arrival_time"].hour == 8
        assert result[0]["arrival_time"].minute == 0
        assert result[0]["departure_time"].hour == 8
        assert result[0]["departure_time"].minute == 1

        assert result[1]["station_code"] == "WDD"
        assert result[2]["station_code"] == "JAM"
        # JAM has no departure_time, should fallback to arrival_time
        assert result[2]["departure_time"] == result[2]["arrival_time"]

    @pytest.mark.asyncio
    async def test_returns_none_when_no_active_services(self):
        """Should return None when no service IDs are active for the date."""
        mock_db = AsyncMock()

        with patch.object(self.service, "get_active_service_ids", return_value=set()):
            result = await self.service.get_static_stop_times(
                mock_db, "LIRR", "GO103_25_181", date(2026, 2, 6)
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_trip_not_found(self):
        """Should return None when the GTFS trip_id doesn't match any trip."""
        mock_db = AsyncMock()

        with patch.object(
            self.service, "get_active_service_ids", return_value={"WD_26"}
        ):
            with patch.object(self.service, "_find_trip_in_source", return_value=None):
                result = await self.service.get_static_stop_times(
                    mock_db, "LIRR", "NONEXISTENT_TRIP", date(2026, 2, 6)
                )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_stop_times(self):
        """Should return None when trip exists but has no stop_times."""
        mock_db = AsyncMock()

        with patch.object(
            self.service, "get_active_service_ids", return_value={"WD_26"}
        ):
            mock_trip_row = MagicMock()
            mock_trip_row.id = 42
            with patch.object(
                self.service, "_find_trip_in_source", return_value=mock_trip_row
            ):
                mock_result = MagicMock()
                mock_result.all.return_value = []
                mock_db.execute = AsyncMock(return_value=mock_result)

                result = await self.service.get_static_stop_times(
                    mock_db, "LIRR", "GO103_25_181", date(2026, 2, 6)
                )

        assert result is None

    @pytest.mark.asyncio
    async def test_skips_stops_with_unparseable_arrival_time(self):
        """Should skip stops where arrival_time cannot be parsed."""
        mock_db = AsyncMock()

        with patch.object(
            self.service, "get_active_service_ids", return_value={"WD_26"}
        ):
            mock_trip_row = MagicMock()
            mock_trip_row.id = 42
            with patch.object(
                self.service, "_find_trip_in_source", return_value=mock_trip_row
            ):
                mock_good_stop = MagicMock()
                mock_good_stop.station_code = "GCT"
                mock_good_stop.stop_sequence = 1
                mock_good_stop.arrival_time = "08:00:00"
                mock_good_stop.departure_time = "08:01:00"

                mock_bad_stop = MagicMock()
                mock_bad_stop.station_code = "WDD"
                mock_bad_stop.stop_sequence = 2
                mock_bad_stop.arrival_time = ""  # Unparseable
                mock_bad_stop.departure_time = "08:10:00"

                mock_result = MagicMock()
                mock_result.all.return_value = [mock_good_stop, mock_bad_stop]
                mock_db.execute = AsyncMock(return_value=mock_result)

                result = await self.service.get_static_stop_times(
                    mock_db, "LIRR", "GO103_25_181", date(2026, 2, 6)
                )

        assert result is not None
        assert len(result) == 1
        assert result[0]["station_code"] == "GCT"
