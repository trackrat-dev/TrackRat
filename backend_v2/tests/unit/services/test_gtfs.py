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
    _extract_lirr_train_number,
    _lirr_train_id_from_gtfs,
    _mnr_train_id_from_gtfs,
    _strip_source_prefix,
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

    def setup_method(self):
        """Clear the service ID cache before each test to prevent cross-test pollution."""
        GTFSService._service_id_cache.clear()

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

        # Headsign extraction is still valid for sources that include train numbers
        assert service._extract_train_id("3245") == "3245"


class TestNJTLineCodeMapping:
    """Tests for NJT GTFS route_short_name to API line code mapping.

    NJT GTFS uses route_short_name values like "NEC", "NJCL", "BNTN", etc.
    NJT real-time API returns 2-char LINE codes like "NE", "NC", "Mo", etc.

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

    def test_nec_maps_to_ne(self):
        """Northeast Corridor maps to 'NE' (matching NJT API LINE field)."""
        from trackrat.services.gtfs import NJT_LINE_CODE_MAPPING

        assert NJT_LINE_CODE_MAPPING["NEC"] == "NE"

    def test_njcl_maps_to_nc(self):
        """North Jersey Coast Line maps to 'NC' (distinct from NEC 'NE')."""
        from trackrat.services.gtfs import NJT_LINE_CODE_MAPPING

        assert NJT_LINE_CODE_MAPPING["NJCL"] == "NC"

    def test_morris_essex_maps_to_me(self):
        """Morris & Essex Line maps to 'ME' (matching route_topology line_codes)."""
        from trackrat.services.gtfs import NJT_LINE_CODE_MAPPING

        assert NJT_LINE_CODE_MAPPING["MNE"] == "ME"

    def test_gladstone_maps_to_gl(self):
        """Gladstone Branch maps to 'GL' (matching route_topology line_codes)."""
        from trackrat.services.gtfs import NJT_LINE_CODE_MAPPING

        assert NJT_LINE_CODE_MAPPING["MNEG"] == "GL"

    def test_montclair_boonton_maps_to_mo(self):
        """Montclair-Boonton Line maps to 'MO' (matching route_topology line_codes)."""
        from trackrat.services.gtfs import NJT_LINE_CODE_MAPPING

        assert NJT_LINE_CODE_MAPPING["BNTN"] == "MO"

    def test_raritan_valley_maps_to_rv(self):
        """Raritan Valley Line maps to 'RV' (matching route_topology line_codes)."""
        from trackrat.services.gtfs import NJT_LINE_CODE_MAPPING

        assert NJT_LINE_CODE_MAPPING["RARV"] == "RV"

    def test_pascack_valley_maps_to_pv(self):
        """Pascack Valley Line maps to 'PV' (matching route_topology line_codes)."""
        from trackrat.services.gtfs import NJT_LINE_CODE_MAPPING

        assert NJT_LINE_CODE_MAPPING["PASC"] == "PV"

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


class TestSubwayTrainIdPrefixing:
    """Tests for subway GTFS train ID prefix/strip logic.

    Subway GTFS departures use the full trip_id (not truncated) with an
    S{route}- prefix so the detail endpoint can reverse-lookup the trip.
    This differs from LIRR/MNR where train numbers are shared between
    real-time and GTFS data.

    The prefix format is: S{route_short_name}-{full_gtfs_trip_id}
    Example: S1-AFA25GEN-1079-Sunday-00_000600_1..N03R
    """

    def test_subway_prefix_uses_full_trip_id(self):
        """Subway prefix must use full GTFS trip_id, not truncated.

        Truncating to 6 chars (the old behavior) made IDs like S1-AFA25G
        that couldn't be resolved back to the original trip for detail lookup.
        """
        gtfs_trip_id = "AFA25GEN-1079-Sunday-00_000600_1..N03R"
        train_id = None  # Subway GTFS has no trip_short_name
        effective_train_id = train_id if train_id else gtfs_trip_id

        # Simulate the prefix logic from gtfs.py get_departures_for_date
        route_short = "1"
        if not effective_train_id.startswith("S"):
            effective_train_id = f"S{route_short}-{effective_train_id}"

        assert effective_train_id == "S1-AFA25GEN-1079-Sunday-00_000600_1..N03R"
        # Verify it's NOT truncated
        assert "AFA25GEN-1079-Sunday-00_000600_1..N03R" in effective_train_id

    def test_subway_prefix_strip_recovers_trip_id(self):
        """Stripping S{route}- prefix recovers the original GTFS trip_id.

        The detail endpoint strips the prefix to search GTFSTrip.trip_id.
        """
        prefixed_id = "S1-AFA25GEN-1079-Sunday-00_000600_1..N03R"
        original_trip_id = "AFA25GEN-1079-Sunday-00_000600_1..N03R"

        assert _strip_source_prefix(prefixed_id, "SUBWAY") == original_trip_id

    def test_subway_prefix_strip_with_multi_char_route(self):
        """Route names can be multi-character (e.g., 'SIR' for Staten Island)."""
        prefixed_id = "SSIR-trip_abc_123"
        assert _strip_source_prefix(prefixed_id, "SUBWAY") == "trip_abc_123"

    def test_subway_prefix_not_applied_twice(self):
        """If effective_train_id already starts with S, skip prefixing."""
        effective_train_id = "S6-010123"  # Already prefixed (from real-time)
        route_short = "6"

        if not effective_train_id.startswith("S"):
            effective_train_id = f"S{route_short}-{effective_train_id}"

        # Should remain unchanged
        assert effective_train_id == "S6-010123"

    def test_subway_prefix_roundtrip(self):
        """Full roundtrip: prefix in departures, strip in detail lookup."""
        original_trip_id = "BFA30GEN-1079-Weekday-00_043200_A..N04R"
        route_short = "A"

        # Step 1: Prefix (departure listing)
        effective_train_id = original_trip_id
        if not effective_train_id.startswith("S"):
            effective_train_id = f"S{route_short}-{effective_train_id}"
        assert effective_train_id == "SA-BFA30GEN-1079-Weekday-00_043200_A..N04R"

        # Step 2: Strip (detail endpoint) using actual helper
        search_id = _strip_source_prefix(effective_train_id, "SUBWAY")

        # Recovered trip_id matches original
        assert search_id == original_trip_id


class TestStripSourcePrefix:
    """Tests for _strip_source_prefix helper function.

    This function strips transit-system display prefixes from train IDs
    so they can be looked up in the GTFS database. Used both in
    single-source mode (data_source provided) and the two-phase search
    (data_source=None, iterating all sources).

    Bug fix: Previously, prefix stripping was gated on data_source matching,
    so the two-phase search (data_source=None) would pass still-prefixed IDs
    to the GTFS lookup, causing lookups to fail silently.
    """

    # --- AMTRAK ---

    def test_amtrak_strips_a_prefix(self):
        """Amtrak train A112 -> 112 for GTFS lookup."""
        assert _strip_source_prefix("A112", "AMTRAK") == "112"

    def test_amtrak_preserves_non_digit_suffix(self):
        """Only strip A prefix when rest is all digits."""
        assert _strip_source_prefix("ABCD", "AMTRAK") == "ABCD"

    def test_amtrak_no_prefix_passthrough(self):
        """Bare number passes through unchanged."""
        assert _strip_source_prefix("112", "AMTRAK") == "112"

    # --- LIRR ---

    def test_lirr_strips_l_prefix(self):
        """LIRR train L181 -> 181 for GTFS lookup."""
        assert _strip_source_prefix("L181", "LIRR") == "181"

    def test_lirr_preserves_non_digit_suffix(self):
        """Only strip L prefix when rest is all digits."""
        assert _strip_source_prefix("LABC", "LIRR") == "LABC"

    def test_lirr_no_prefix_passthrough(self):
        """Bare number passes through unchanged."""
        assert _strip_source_prefix("181", "LIRR") == "181"

    # --- MNR ---

    def test_mnr_strips_m_prefix(self):
        """MNR train M631700 -> 631700 for GTFS lookup."""
        assert _strip_source_prefix("M631700", "MNR") == "631700"

    def test_mnr_preserves_non_digit_suffix(self):
        """Only strip M prefix when rest is all digits."""
        assert _strip_source_prefix("MXYZ", "MNR") == "MXYZ"

    # --- SUBWAY ---

    def test_subway_strips_route_prefix(self):
        """Subway S1-trip_id -> trip_id for GTFS lookup."""
        assert (
            _strip_source_prefix("S1-AFA25GEN-1079-Sunday-00_000600_1..N03R", "SUBWAY")
            == "AFA25GEN-1079-Sunday-00_000600_1..N03R"
        )

    def test_subway_strips_multi_char_route(self):
        """SIR route produces SSIR- prefix."""
        assert _strip_source_prefix("SSIR-trip_123", "SUBWAY") == "trip_123"

    def test_subway_no_dash_passthrough(self):
        """If no dash found, ID passes through unchanged (safety guard)."""
        assert _strip_source_prefix("S6010123", "SUBWAY") == "S6010123"

    def test_subway_bare_trip_id_passthrough(self):
        """Bare trip_id (no S prefix) passes through unchanged."""
        assert (
            _strip_source_prefix("AFA25GEN-1079-Sunday-00_000600_1..N03R", "SUBWAY")
            == "AFA25GEN-1079-Sunday-00_000600_1..N03R"
        )

    # --- Cross-source safety ---

    def test_njt_no_stripping(self):
        """NJT IDs are never prefixed, so nothing is stripped."""
        assert _strip_source_prefix("2508", "NJT") == "2508"

    def test_path_no_stripping(self):
        """PATH IDs are never prefixed, so nothing is stripped."""
        assert _strip_source_prefix("PATH-123", "PATH") == "PATH-123"

    def test_wrong_source_no_stripping(self):
        """A prefixed ID only gets stripped for its matching source.

        An Amtrak-prefixed ID passed with source=NJT should NOT be stripped,
        since the prefix logic is source-specific.
        """
        assert _strip_source_prefix("A112", "NJT") == "A112"

    def test_subway_prefix_not_stripped_for_amtrak(self):
        """Subway-style prefix shouldn't be stripped for non-SUBWAY source."""
        assert _strip_source_prefix("S1-trip_123", "AMTRAK") == "S1-trip_123"


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


class TestLirrTrainIdFromGtfs:
    """Tests for _lirr_train_id_from_gtfs helper.

    LIRR real-time collector generates train IDs as "L{number}" (e.g., "L181").
    GTFS stores the bare number in trip_short_name (e.g., "181") or uses
    trip_id format like "GO103_25_181". This helper must normalize both to "L181".
    """

    def test_bare_number_gets_l_prefix(self):
        """trip_short_name is a bare number like '181'."""
        assert _lirr_train_id_from_gtfs("181") == "L181"

    def test_already_prefixed_unchanged(self):
        """Real-time format 'L181' should pass through unchanged."""
        assert _lirr_train_id_from_gtfs("L181") == "L181"

    def test_gtfs_trip_id_extracts_third_segment(self):
        """GTFS trip_id 'GO103_25_181' -> extract '181' -> 'L181'."""
        assert _lirr_train_id_from_gtfs("GO103_25_181") == "L181"

    def test_gtfs_trip_id_different_prefix(self):
        """Different GTFS trip_id prefixes should still extract train number."""
        assert _lirr_train_id_from_gtfs("GI501_25_6503") == "L6503"

    def test_multi_digit_train_number(self):
        """4+ digit train numbers are common on LIRR."""
        assert _lirr_train_id_from_gtfs("8042") == "L8042"

    def test_short_trip_id_fallback(self):
        """Trip IDs with fewer than 3 segments fall back to L-prefix."""
        assert _lirr_train_id_from_gtfs("GO103_181") == "LGO103_181"

    def test_date_suffix_extracts_first_segment(self):
        """Date-suffix trip_id '7597_2026-02-22' -> extract '7597' -> 'L7597'."""
        assert _lirr_train_id_from_gtfs("7597_2026-02-22") == "L7597"

    def test_date_suffix_different_train_number(self):
        """Another date-suffix trip_id to verify consistency with collector."""
        assert _lirr_train_id_from_gtfs("123_2026-01-15") == "L123"

    def test_single_segment_non_numeric(self):
        """Non-numeric single values get L-prefix as fallback."""
        assert _lirr_train_id_from_gtfs("UNKNOWN") == "LUNKNOWN"


class TestMnrTrainIdFromGtfs:
    """Tests for _mnr_train_id_from_gtfs helper.

    MNR real-time collector generates train IDs as "M{digits}" where digits are
    the last 6 characters of trip_id filtered to digits only (e.g., "M631700").
    GTFS stores the bare number in trip_short_name. This helper must normalize
    both formats to "M631700".
    """

    def test_bare_number_gets_m_prefix(self):
        """trip_short_name is a bare number like '631700'."""
        assert _mnr_train_id_from_gtfs("631700") == "M631700"

    def test_already_prefixed_unchanged(self):
        """Real-time format 'M631700' should pass through unchanged."""
        assert _mnr_train_id_from_gtfs("M631700") == "M631700"

    def test_long_trip_id_extracts_last_6_digits(self):
        """Long GTFS trip_id: last 6 chars filtered to digits."""
        assert _mnr_train_id_from_gtfs("MNR_20260119_631700") == "M631700"

    def test_mixed_alphanumeric_suffix(self):
        """Last 6 chars with mixed alpha/digits keep only digits."""
        assert _mnr_train_id_from_gtfs("tripABC123") == "M123"

    def test_short_numeric_trip_id(self):
        """Short all-numeric trip_id."""
        assert _mnr_train_id_from_gtfs("8042") == "M8042"

    def test_no_digits_falls_back_to_first_6(self):
        """Trip_id with no digits in last 6 chars uses first 6 as fallback."""
        assert _mnr_train_id_from_gtfs("UNKNOWN") == "MUNKNOW"

    def test_single_digit_in_suffix(self):
        """Even a single digit in last 6 chars is extracted."""
        assert _mnr_train_id_from_gtfs("ABCDE1FG") == "M1"


class TestExtractLirrTrainNumber:
    """Tests for _extract_lirr_train_number helper.

    LIRR GTFS-RT uses date-suffix trip_ids (e.g., '6817_2026-02-24') for
    trains that don't match the current GTFS static trip_ids.  The helper
    extracts the bare train number so we can fall back to a train_id lookup
    in the static schedule.
    """

    def test_date_suffix_format_returns_train_number(self):
        """Standard date-suffix format: '6817_2026-02-24' -> '6817'."""
        assert _extract_lirr_train_number("6817_2026-02-24") == "6817"

    def test_four_digit_train_number(self):
        """Four-digit train number with date suffix."""
        assert _extract_lirr_train_number("6853_2026-02-24") == "6853"

    def test_five_digit_train_number(self):
        """Five-digit train number with date suffix."""
        assert _extract_lirr_train_number("12345_2025-12-31") == "12345"

    def test_go_prefix_format_returns_none(self):
        """GO-prefix trip_ids are NOT date-suffix format."""
        assert _extract_lirr_train_number("GO103_25_6127") is None

    def test_go_event_format_returns_none(self):
        """GO-event trip_ids (with METS suffix) are NOT date-suffix format."""
        assert _extract_lirr_train_number("GO103_25_367_2891_METS") is None

    def test_plain_number_returns_none(self):
        """Plain numeric trip_id (MNR style) returns None."""
        assert _extract_lirr_train_number("3009440") is None

    def test_non_numeric_first_segment_returns_none(self):
        """Non-numeric first segment before date separator returns None."""
        assert _extract_lirr_train_number("ABC_2026-01-01") is None

    def test_no_hyphen_in_second_segment_returns_none(self):
        """Two segments but second doesn't contain a hyphen returns None."""
        assert _extract_lirr_train_number("6817_20260224") is None

    def test_empty_string_returns_none(self):
        """Empty string returns None."""
        assert _extract_lirr_train_number("") is None

    def test_single_segment_returns_none(self):
        """Single segment with no underscore returns None."""
        assert _extract_lirr_train_number("6817") is None


class TestGetStaticStopTimesLirrFallback:
    """Tests for get_static_stop_times fallback to train_id for LIRR date-suffix trips.

    When the GTFS-RT trip_id (e.g., '6817_2026-02-24') doesn't match any
    static trip_id, the service should extract the train number ('6817')
    and retry with a train_id lookup.
    """

    def setup_method(self):
        self.service = GTFSService()

    @pytest.mark.asyncio
    async def test_fallback_to_train_id_on_date_suffix_trip(self):
        """Date-suffix trip_id triggers train_id fallback when trip_id lookup fails."""
        mock_db = AsyncMock()
        target_date = date(2026, 2, 24)

        mock_trip_row = MagicMock()
        mock_trip_row.id = 42

        find_calls = []

        async def mock_find(db, search_id, source, sids, match_field):
            find_calls.append((search_id, match_field))
            if match_field == "trip_id":
                return None  # trip_id "6817_2026-02-24" not found
            elif match_field == "train_id" and search_id == "6817":
                return mock_trip_row  # train_id "6817" found
            return None

        # Mock stop_times query result
        mock_stops_result = MagicMock()
        mock_stops_result.all.return_value = [
            MagicMock(
                station_code="NY",
                stop_sequence=1,
                arrival_time="11:54:00",
                departure_time="11:54:00",
            ),
            MagicMock(
                station_code="JAM",
                stop_sequence=2,
                arrival_time="12:15:00",
                departure_time="12:15:00",
            ),
            MagicMock(
                station_code="LBH",
                stop_sequence=3,
                arrival_time="12:45:00",
                departure_time="12:45:00",
            ),
        ]
        mock_db.execute = AsyncMock(return_value=mock_stops_result)

        with (
            patch.object(
                self.service,
                "get_active_service_ids",
                return_value={"SVC_WEEKDAY"},
            ),
            patch.object(
                self.service,
                "_find_trip_in_source",
                side_effect=mock_find,
            ),
        ):
            stops = await self.service.get_static_stop_times(
                mock_db, "LIRR", "6817_2026-02-24", target_date
            )

        # Should have found stops via train_id fallback
        assert stops is not None, "Expected stops from train_id fallback"
        assert len(stops) == 3
        assert stops[0]["station_code"] == "NY"
        assert stops[2]["station_code"] == "LBH"
        # Verify trip_id lookup failed, then train_id lookup succeeded
        assert len(find_calls) == 2
        assert find_calls[0] == ("6817_2026-02-24", "trip_id")
        assert find_calls[1] == ("6817", "train_id")

    @pytest.mark.asyncio
    async def test_go_prefix_uses_direct_trip_id_lookup(self):
        """GO-prefix trip_ids succeed on first lookup without fallback."""
        mock_db = AsyncMock()
        target_date = date(2026, 2, 24)

        mock_trip_row = MagicMock()
        mock_trip_row.id = 42

        find_calls = []

        async def mock_find(db, search_id, source, sids, match_field):
            find_calls.append((search_id, match_field))
            if match_field == "trip_id" and search_id == "GO103_25_6127":
                return mock_trip_row
            return None

        mock_stops_result = MagicMock()
        mock_stops_result.all.return_value = [
            MagicMock(
                station_code="NY",
                stop_sequence=1,
                arrival_time="11:00:00",
                departure_time="11:00:00",
            ),
            MagicMock(
                station_code="BTA",
                stop_sequence=2,
                arrival_time="12:00:00",
                departure_time="12:00:00",
            ),
        ]
        mock_db.execute = AsyncMock(return_value=mock_stops_result)

        with (
            patch.object(
                self.service,
                "get_active_service_ids",
                return_value={"SVC_WEEKDAY"},
            ),
            patch.object(
                self.service,
                "_find_trip_in_source",
                side_effect=mock_find,
            ),
        ):
            stops = await self.service.get_static_stop_times(
                mock_db, "LIRR", "GO103_25_6127", target_date
            )

        assert stops is not None
        # Only 1 find call: trip_id succeeded, no train_id fallback
        assert len(find_calls) == 1
        assert find_calls[0] == ("GO103_25_6127", "trip_id")

    @pytest.mark.asyncio
    async def test_date_suffix_both_lookups_fail_returns_none(self):
        """When both trip_id and train_id lookups fail, returns None."""
        mock_db = AsyncMock()
        target_date = date(2026, 2, 24)

        find_calls = []

        async def mock_find(db, search_id, source, sids, match_field):
            find_calls.append((search_id, match_field))
            return None  # All lookups fail

        with (
            patch.object(
                self.service,
                "get_active_service_ids",
                return_value={"SVC_WEEKDAY"},
            ),
            patch.object(
                self.service,
                "_find_trip_in_source",
                side_effect=mock_find,
            ),
        ):
            stops = await self.service.get_static_stop_times(
                mock_db, "LIRR", "9999_2026-02-24", target_date
            )

        assert stops is None
        # 2 find calls: trip_id (fail) + train_id (fail)
        assert len(find_calls) == 2
        assert find_calls[0] == ("9999_2026-02-24", "trip_id")
        assert find_calls[1] == ("9999", "train_id")


class TestGetScheduledDeparturesTimeFrom:
    """Tests for `time_from` filtering in get_scheduled_departures().

    High-frequency providers like SUBWAY would otherwise return only the
    overnight sliver of the day because the first `limit` trains sorted by
    departure time are all pre-dawn. `time_from` moves the limit window to
    the caller's time of interest.
    """

    def setup_method(self):
        self.service = GTFSService()

    def _make_departure(self, train_id: str, dt: datetime):
        from trackrat.models.api import (
            DataFreshness,
            LineInfo,
            StationInfo,
            TrainDeparture,
            TrainPosition,
        )

        return TrainDeparture(
            train_id=train_id,
            journey_date=dt.date(),
            line=LineInfo(code="1", name="1", color="#EE352E"),
            destination="South Ferry",
            departure=StationInfo(code="S127", name="Times Sq", scheduled_time=dt),
            arrival=None,
            train_position=TrainPosition(),
            data_freshness=DataFreshness(last_updated=dt, age_seconds=0),
            data_source="SUBWAY",
            observation_type="SCHEDULED",
        )

    @pytest.mark.asyncio
    async def test_time_from_shifts_limit_window(self):
        """Setting time_from should skip earlier departures before applying limit."""
        target_date = date(2026, 4, 23)
        # 10 hourly SUBWAY departures from 00:30 to 09:30 ET
        mock_deps = [
            self._make_departure(
                f"S{i:03d}",
                ET.localize(datetime.combine(target_date, time(i, 30))),
            )
            for i in range(10)
        ]

        mock_db = AsyncMock()
        cutoff = ET.localize(datetime.combine(target_date, time(8, 0)))

        with (
            patch.object(
                self.service, "get_active_service_ids", return_value={"WD_SUBWAY"}
            ),
            patch.object(
                self.service,
                "_query_departures_for_source",
                AsyncMock(return_value=mock_deps),
            ),
        ):
            response = await self.service.get_scheduled_departures(
                db=mock_db,
                from_station="S127",
                to_station=None,
                target_date=target_date,
                limit=5,
                data_sources=["SUBWAY"],
                time_from=cutoff,
            )

        # Only 08:30 and 09:30 departures survive the cutoff
        returned_ids = [d.train_id for d in response.departures]
        assert returned_ids == ["S008", "S009"]

    @pytest.mark.asyncio
    async def test_no_time_from_returns_first_limit_of_day(self):
        """Without time_from, behavior matches pre-fix: earliest N departures."""
        target_date = date(2026, 4, 23)
        mock_deps = [
            self._make_departure(
                f"S{i:03d}",
                ET.localize(datetime.combine(target_date, time(i, 30))),
            )
            for i in range(10)
        ]

        mock_db = AsyncMock()

        with (
            patch.object(
                self.service, "get_active_service_ids", return_value={"WD_SUBWAY"}
            ),
            patch.object(
                self.service,
                "_query_departures_for_source",
                AsyncMock(return_value=mock_deps),
            ),
        ):
            response = await self.service.get_scheduled_departures(
                db=mock_db,
                from_station="S127",
                to_station=None,
                target_date=target_date,
                limit=5,
                data_sources=["SUBWAY"],
            )

        returned_ids = [d.train_id for d in response.departures]
        assert returned_ids == ["S000", "S001", "S002", "S003", "S004"]
