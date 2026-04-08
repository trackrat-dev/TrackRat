"""
Unit tests for MetraCollector.

Tests unified Metra train discovery and journey update logic,
including train ID generation, timezone handling, and origin inference.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trackrat.collectors.metra.client import MetraArrival, MetraClient
from trackrat.collectors.metra.collector import (
    DATA_SOURCE,
    MetraCollector,
    _generate_train_id,
)

# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestGenerateTrainId:
    """Tests for the train ID generation function.

    Metra trip_ids follow patterns like "ME_ME2012_V1_B" or "BNSF_BNSF1234_V1_A".
    The function extracts the train number from the second segment and prefixes with "MT".
    """

    def test_standard_metra_electric_trip_id(self):
        """ME_ME2012_V1_B -> MT2012 (strips duplicate ME prefix)."""
        assert _generate_train_id("ME_ME2012_V1_B") == "MT2012"

    def test_standard_bnsf_trip_id(self):
        """BNSF_BNSF1234_V1_A -> MT1234 (strips duplicate BNSF prefix)."""
        assert _generate_train_id("BNSF_BNSF1234_V1_A") == "MT1234"

    def test_up_north_trip_id(self):
        """UP-N_UP-N301_V1_B -> MT301 (strips duplicate UP-N prefix)."""
        assert _generate_train_id("UP-N_UP-N301_V1_B") == "MT301"

    def test_up_northwest_trip_id(self):
        """UP-NW_UP-NW4105_V1_A -> MT4105."""
        assert _generate_train_id("UP-NW_UP-NW4105_V1_A") == "MT4105"

    def test_up_west_trip_id(self):
        """UP-W_UP-W43_V1_B -> MT43."""
        assert _generate_train_id("UP-W_UP-W43_V1_B") == "MT43"

    def test_rock_island_trip_id(self):
        """RI_RI401_V1_A -> MT401."""
        assert _generate_train_id("RI_RI401_V1_A") == "MT401"

    def test_southwest_service_trip_id(self):
        """SWS_SWS801_V1_A -> MT801."""
        assert _generate_train_id("SWS_SWS801_V1_A") == "MT801"

    def test_heritage_corridor_trip_id(self):
        """HC_HC101_V1_B -> MT101."""
        assert _generate_train_id("HC_HC101_V1_B") == "MT101"

    def test_milw_district_north_trip_id(self):
        """MD-N_MD-N2101_V1_A -> MT2101."""
        assert _generate_train_id("MD-N_MD-N2101_V1_A") == "MT2101"

    def test_milw_district_west_trip_id(self):
        """MD-W_MD-W2201_V1_B -> MT2201."""
        assert _generate_train_id("MD-W_MD-W2201_V1_B") == "MT2201"

    def test_north_central_service_trip_id(self):
        """NCS_NCS101_V1_A -> MT101."""
        assert _generate_train_id("NCS_NCS101_V1_A") == "MT101"

    def test_different_trip_ids_produce_different_train_ids(self):
        """Different trips should produce different train IDs."""
        id1 = _generate_train_id("ME_ME2012_V1_B")
        id2 = _generate_train_id("ME_ME2014_V1_B")
        assert id1 != id2
        assert id1 == "MT2012"
        assert id2 == "MT2014"

    def test_all_train_ids_start_with_mt_prefix(self):
        """All generated train IDs should start with MT prefix."""
        test_cases = [
            "ME_ME2012_V1_B",
            "BNSF_BNSF1234_V1_A",
            "UP-N_UP-N301_V1_B",
            "RI_RI401_V1_A",
            "SWS_SWS801_V1_A",
        ]
        for trip_id in test_cases:
            result = _generate_train_id(trip_id)
            assert result.startswith(
                "MT"
            ), f"Expected MT prefix for {trip_id}, got {result}"

    def test_fallback_for_unexpected_format(self):
        """Unexpected formats should still produce a valid train ID."""
        result = _generate_train_id("ABCDEFGH")
        assert result.startswith("MT")

    def test_single_segment_numeric(self):
        """Single numeric segment uses digit extraction fallback."""
        result = _generate_train_id("12345")
        assert result.startswith("MT")

    def test_non_duplicate_prefix(self):
        """When second segment doesn't start with route prefix, use full second segment."""
        result = _generate_train_id("XX_1234_V1_A")
        assert result == "MT1234"


# =============================================================================
# COLLECTOR INITIALIZATION TESTS
# =============================================================================


class TestMetraCollectorInit:
    """Tests for MetraCollector initialization."""

    def test_default_init_creates_client(self):
        """Default init should create its own MetraClient."""
        with patch.dict("os.environ", {"TRACKRAT_METRA_API_TOKEN": "test"}):
            collector = MetraCollector()
            assert collector.client is not None
            assert collector._owns_client is True

    def test_init_with_custom_client(self):
        """Should accept an externally-provided client."""
        with patch.dict("os.environ", {"TRACKRAT_METRA_API_TOKEN": "test"}):
            mock_client = MetraClient()
            collector = MetraCollector(client=mock_client)
            assert collector.client is mock_client
            assert collector._owns_client is False

    def test_data_source_constant(self):
        """DATA_SOURCE should be 'METRA'."""
        assert DATA_SOURCE == "METRA"


# =============================================================================
# STATION & TIMEZONE TESTS
# =============================================================================


class TestMetraTimezone:
    """Tests for Metra timezone handling."""

    def test_provider_timezone_is_central(self):
        """Metra should use Central Time."""
        from trackrat.utils.time import PROVIDER_TIMEZONE

        ct = PROVIDER_TIMEZONE["METRA"]
        assert "Central" in str(ct) or "Chicago" in str(ct)

    def test_now_for_provider_returns_central_time(self):
        """now_for_provider('METRA') should return a datetime in Central Time."""
        from trackrat.utils.time import PROVIDER_TIMEZONE, now_for_provider

        now = now_for_provider("METRA")
        assert now.tzinfo is not None

        # The timezone should be Central
        ct = PROVIDER_TIMEZONE["METRA"]
        # Compare by checking the UTC offset matches Central Time
        expected_offset = datetime.now(ct).utcoffset()
        actual_offset = now.utcoffset()
        assert expected_offset == actual_offset

    def test_now_for_provider_njt_is_eastern(self):
        """NJT provider should still use Eastern Time (no regression)."""
        from trackrat.utils.time import PROVIDER_TIMEZONE, now_for_provider

        now = now_for_provider("NJT")
        et = PROVIDER_TIMEZONE["NJT"]
        expected_offset = datetime.now(et).utcoffset()
        actual_offset = now.utcoffset()
        assert expected_offset == actual_offset

    def test_unknown_provider_defaults_to_eastern(self):
        """Unknown providers should default to Eastern Time."""
        from trackrat.utils.time import ET, now_for_provider

        now = now_for_provider("UNKNOWN_PROVIDER")
        expected_offset = datetime.now(ET).utcoffset()
        actual_offset = now.utcoffset()
        assert expected_offset == actual_offset


# =============================================================================
# STATION CONFIG TESTS
# =============================================================================


class TestMetraStationConfig:
    """Tests for Metra station configuration."""

    def test_station_names_populated(self):
        """METRA_STATION_NAMES should have 241 stations."""
        from trackrat.config.stations.metra import METRA_STATION_NAMES

        assert len(METRA_STATION_NAMES) == 241

    def test_key_stations_exist(self):
        """Key stations should be present in the mapping."""
        from trackrat.config.stations.metra import METRA_STATION_NAMES

        key_stations = [
            "CUS",
            "OTC",
            "LSS",
            "MILLENNIUM",
            "AURORA",
            "JOLIET",
            "KENOSHA",
        ]
        for code in key_stations:
            assert code in METRA_STATION_NAMES, f"Missing key station: {code}"

    def test_routes_populated(self):
        """METRA_ROUTES should have 11 routes."""
        from trackrat.config.stations.metra import METRA_ROUTES

        assert len(METRA_ROUTES) == 11

    def test_route_info_structure(self):
        """Each route should have (line_code, name, color) tuple."""
        from trackrat.config.stations.metra import METRA_ROUTES

        for route_id, route_info in METRA_ROUTES.items():
            assert len(route_info) == 3, f"Route {route_id} should have 3 elements"
            line_code, name, color = route_info
            assert isinstance(line_code, str)
            assert isinstance(name, str)
            assert color.startswith("#"), f"Route {route_id} color should be hex"

    def test_downtown_terminals(self):
        """METRA_DOWNTOWN_TERMINALS should contain the 4 Chicago terminals."""
        from trackrat.config.stations.metra import METRA_DOWNTOWN_TERMINALS

        assert "CUS" in METRA_DOWNTOWN_TERMINALS  # Chicago Union Station
        assert "OTC" in METRA_DOWNTOWN_TERMINALS  # Ogilvie Transportation Center
        assert "LSS" in METRA_DOWNTOWN_TERMINALS  # LaSalle Street Station
        assert "MILLENNIUM" in METRA_DOWNTOWN_TERMINALS  # Millennium Station
        assert len(METRA_DOWNTOWN_TERMINALS) == 4

    def test_line_terminal_mapping(self):
        """Each route should map to its correct downtown terminal."""
        from trackrat.config.stations.metra import METRA_LINE_TERMINAL

        # Union Station lines
        assert METRA_LINE_TERMINAL["BNSF"] == "CUS"
        assert METRA_LINE_TERMINAL["HC"] == "CUS"
        assert METRA_LINE_TERMINAL["SWS"] == "CUS"
        # Ogilvie lines
        assert METRA_LINE_TERMINAL["UP-N"] == "OTC"
        assert METRA_LINE_TERMINAL["UP-NW"] == "OTC"
        assert METRA_LINE_TERMINAL["UP-W"] == "OTC"
        # LaSalle
        assert METRA_LINE_TERMINAL["RI"] == "LSS"
        # Millennium
        assert METRA_LINE_TERMINAL["ME"] == "MILLENNIUM"

    def test_identity_mapping(self):
        """GTFS stop_id to internal code should be identity for Metra."""
        from trackrat.config.stations.metra import (
            METRA_GTFS_STOP_TO_INTERNAL_MAP,
            METRA_STATION_NAMES,
        )

        for code in METRA_STATION_NAMES:
            assert METRA_GTFS_STOP_TO_INTERNAL_MAP[code] == code

    def test_no_station_code_collisions(self):
        """Metra station codes should not collide with other providers."""
        from trackrat.config.stations.common import STATION_NAMES
        from trackrat.config.stations.metra import METRA_STATION_NAMES

        # All Metra stations should be in the unified STATION_NAMES
        for code in METRA_STATION_NAMES:
            assert (
                code in STATION_NAMES
            ), f"Metra station {code} missing from STATION_NAMES"

    def test_coordinates_populated(self):
        """Most Metra stations should have coordinates."""
        from trackrat.config.stations.metra import (
            METRA_STATION_COORDINATES,
            METRA_STATION_NAMES,
        )

        # All stations should have coordinates
        assert len(METRA_STATION_COORDINATES) == len(METRA_STATION_NAMES)
        for code, coords in METRA_STATION_COORDINATES.items():
            assert "lat" in coords, f"Station {code} missing lat"
            assert "lon" in coords, f"Station {code} missing lon"
            # Chicago area: roughly 41-43 lat, -87 to -89 lon
            assert (
                40.5 < coords["lat"] < 43.5
            ), f"Station {code} lat {coords['lat']} out of range"
            assert (
                -90 < coords["lon"] < -86
            ), f"Station {code} lon {coords['lon']} out of range"


# =============================================================================
# INTEGRATION WITH COMMON MODULES
# =============================================================================


class TestMetraCommonIntegration:
    """Tests for Metra integration with mta_common and station config."""

    def test_metra_in_origin_terminal_config(self):
        """Metra should be registered in mta_common origin terminal config."""
        from trackrat.collectors.mta_common import _ORIGIN_TERMINAL_CONFIG

        assert "METRA" in _ORIGIN_TERMINAL_CONFIG

        terminals, default = _ORIGIN_TERMINAL_CONFIG["METRA"]
        assert "CUS" in terminals
        assert "OTC" in terminals
        assert "LSS" in terminals
        assert "MILLENNIUM" in terminals
        assert default == "CUS"

    def test_metra_in_station_equivalence(self):
        """CUS and CHI should be in the same equivalence group (Amtrak overlap)."""
        from trackrat.config.stations.common import STATION_EQUIVALENCE_GROUPS

        found = False
        for group in STATION_EQUIVALENCE_GROUPS:
            if "CUS" in group and "CHI" in group:
                found = True
                break
        assert found, "CUS and CHI should be in the same equivalence group"

    def test_metra_in_api_data_source_literals(self):
        """METRA should be a valid data_source in API models."""
        import trackrat.models.api as api_module
        import inspect

        # Verify METRA appears in the module source (Literal types)
        source = inspect.getsource(api_module)
        assert "METRA" in source, "METRA should appear in api models source"

    def test_metra_in_summary_display_names(self):
        """METRA should have a display name in summary service."""
        from trackrat.services.summary import CARRIER_DISPLAY_NAMES

        assert "METRA" in CARRIER_DISPLAY_NAMES
        assert CARRIER_DISPLAY_NAMES["METRA"] == "Metra"

    def test_metra_in_high_freq_jit_sources(self):
        """METRA should be in JIT high-frequency collector sources."""
        from trackrat.services.jit import JustInTimeUpdateService

        assert "METRA" in JustInTimeUpdateService._HIGH_FREQ_COLLECTOR_SOURCES

    def test_metra_in_realtime_sources(self):
        """METRA should be registered as a real-time data source everywhere."""
        from trackrat.services.departure import REAL_TIME_DATA_SOURCES
        from trackrat.services.alert_evaluator import REALTIME_SOURCES as ALERT_RT
        from trackrat.services.congestion import REALTIME_SOURCES as CONG_RT

        assert (
            "METRA" in REAL_TIME_DATA_SOURCES
        ), "Missing from departure REAL_TIME_DATA_SOURCES"
        assert "METRA" in ALERT_RT, "Missing from alert_evaluator REALTIME_SOURCES"
        assert "METRA" in CONG_RT, "Missing from congestion REALTIME_SOURCES"

    def test_metra_in_gtfs_feed_urls(self):
        """METRA should have a GTFS feed URL registered."""
        from trackrat.services.gtfs import GTFS_FEED_URLS, DEFAULT_LINE_COLORS

        assert "METRA" in GTFS_FEED_URLS, "Missing from GTFS_FEED_URLS"
        assert "METRA" in DEFAULT_LINE_COLORS, "Missing from DEFAULT_LINE_COLORS"

    def test_metra_in_gtfs_source_lists(self):
        """METRA should appear in GTFS source enumeration lists."""
        from trackrat.services.scheduler import SchedulerService

        assert "METRA" in SchedulerService.GTFS_SOURCES


# =============================================================================
# MISSING TOKEN HANDLING TESTS
# =============================================================================


class TestCollectorMissingToken:
    """Tests that MetraCollector returns error stats when API token is missing.

    Bug: collector received empty list from client, logged "No Metra arrivals
    found", and returned stats with zeros — indistinguishable from success.
    Scheduler marked this as a completed run, preventing retries.

    See: https://github.com/trackrat-dev/trackrat/issues/901
    """

    @pytest.mark.asyncio
    async def test_collect_raises_when_no_token(self):
        """collect() raises RuntimeError when API token is empty so the scheduler records a failure."""
        client = MetraClient(api_token="")
        collector = MetraCollector(client=client)
        session = AsyncMock()

        with pytest.raises(RuntimeError, match="TRACKRAT_METRA_API_TOKEN not configured"):
            await collector.collect(session)

        # Session should not have been touched
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_proceeds_with_valid_token(self):
        """collect() does NOT return early when token is configured."""
        client = MagicMock(spec=MetraClient)
        client._api_token = "valid-token"
        client.get_all_arrivals = AsyncMock(return_value=[])
        collector = MetraCollector(client=client)
        session = AsyncMock()

        result = await collector.collect(session)

        # Should have called get_all_arrivals (not returned early)
        client.get_all_arrivals.assert_called_once()
        assert "error" not in result
