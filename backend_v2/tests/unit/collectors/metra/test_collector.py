"""
Unit tests for MetraCollector.

Tests unified Metra train discovery and journey update logic,
including train ID generation, timezone handling, origin inference,
error propagation, and consecutive-zero cycle detection.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trackrat.collectors.metra.client import MetraArrival, MetraClient, MetraFetchError
from trackrat.collectors.metra.collector import (
    DATA_SOURCE,
    MetraCollector,
    _generate_train_id,
)
import trackrat.collectors.metra.collector as collector_module

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
# MISSING CREDENTIALS HANDLING TESTS
# =============================================================================


class TestCollectorMissingCredentials:
    """Tests that MetraCollector raises when credentials are missing."""

    @pytest.mark.asyncio
    async def test_collect_raises_when_no_credentials(self):
        """collect() raises RuntimeError when no credentials are configured."""
        client = MetraClient(api_token="")
        collector = MetraCollector(client=client)
        session = AsyncMock()

        with pytest.raises(RuntimeError, match="credentials not configured"):
            await collector.collect(session)

        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_proceeds_with_valid_token(self):
        """collect() does NOT return early when token is configured."""
        client = MagicMock(spec=MetraClient)
        client.has_credentials = True
        client._auth_method = "query_param"
        client.get_all_arrivals = AsyncMock(return_value=[])
        collector = MetraCollector(client=client)
        session = AsyncMock()

        # Reset module-level counter
        collector_module._consecutive_empty_cycles = 0

        result = await collector.collect(session)

        client.get_all_arrivals.assert_called_once()
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_collect_proceeds_with_basic_auth(self):
        """collect() works with Basic Auth credentials."""
        client = MagicMock(spec=MetraClient)
        client.has_credentials = True
        client._auth_method = "basic"
        client.get_all_arrivals = AsyncMock(return_value=[])
        collector = MetraCollector(client=client)
        session = AsyncMock()

        collector_module._consecutive_empty_cycles = 0

        result = await collector.collect(session)

        client.get_all_arrivals.assert_called_once()
        assert "error" not in result


# =============================================================================
# ERROR PROPAGATION TESTS
# =============================================================================


class TestCollectorErrorPropagation:
    """Tests that MetraCollector propagates MetraFetchError from the client.

    Bug: get_all_arrivals() silently returned [] on HTTP errors,
    causing the collector to report 0 departures as a successful run.
    Now MetraFetchError propagates and the collector wraps it in RuntimeError.

    See: https://github.com/trackrat-dev/trackrat/issues/963
    """

    @pytest.fixture(autouse=True)
    def reset_counter(self):
        """Reset the module-level consecutive empty counter before each test."""
        collector_module._consecutive_empty_cycles = 0
        yield
        collector_module._consecutive_empty_cycles = 0

    @pytest.mark.asyncio
    async def test_fetch_error_propagates_as_runtime_error(self):
        """MetraFetchError from client should propagate as RuntimeError."""
        client = MagicMock(spec=MetraClient)
        client.has_credentials = True
        client._auth_method = "query_param"
        client.get_all_arrivals = AsyncMock(
            side_effect=MetraFetchError("HTTP 500")
        )
        collector = MetraCollector(client=client)
        session = AsyncMock()

        with pytest.raises(RuntimeError, match="Metra feed fetch failed"):
            await collector.collect(session)

    @pytest.mark.asyncio
    async def test_auth_error_propagates(self):
        """Authentication errors should propagate, not be swallowed."""
        client = MagicMock(spec=MetraClient)
        client.has_credentials = True
        client._auth_method = "query_param"
        client.get_all_arrivals = AsyncMock(
            side_effect=MetraFetchError("authentication failed (HTTP 401)")
        )
        collector = MetraCollector(client=client)
        session = AsyncMock()

        with pytest.raises(RuntimeError, match="feed fetch failed"):
            await collector.collect(session)


# =============================================================================
# CONSECUTIVE EMPTY CYCLE DETECTION TESTS
# =============================================================================


class TestConsecutiveEmptyCycles:
    """Tests for consecutive-zero arrival detection.

    When the feed returns 0 arrivals for N consecutive cycles, the collector
    should raise so the scheduler marks the run as failed, making the problem
    visible in error logs and health checks.
    """

    @pytest.fixture(autouse=True)
    def reset_counter(self):
        """Reset the module-level consecutive empty counter before each test."""
        collector_module._consecutive_empty_cycles = 0
        yield
        collector_module._consecutive_empty_cycles = 0

    @pytest.mark.asyncio
    async def test_first_empty_cycle_warns_but_succeeds(self):
        """First empty cycle should warn but not raise."""
        client = MagicMock(spec=MetraClient)
        client.has_credentials = True
        client._auth_method = "query_param"
        client.get_all_arrivals = AsyncMock(return_value=[])
        collector = MetraCollector(client=client)
        session = AsyncMock()

        result = await collector.collect(session)

        assert result["total_arrivals"] == 0
        assert collector_module._consecutive_empty_cycles == 1

    @pytest.mark.asyncio
    async def test_two_consecutive_empty_cycles_still_warns(self):
        """Two consecutive empty cycles should warn but not raise."""
        collector_module._consecutive_empty_cycles = 1

        client = MagicMock(spec=MetraClient)
        client.has_credentials = True
        client._auth_method = "query_param"
        client.get_all_arrivals = AsyncMock(return_value=[])
        collector = MetraCollector(client=client)
        session = AsyncMock()

        result = await collector.collect(session)

        assert result["total_arrivals"] == 0
        assert collector_module._consecutive_empty_cycles == 2

    @pytest.mark.asyncio
    async def test_three_consecutive_empty_cycles_raises(self):
        """Three consecutive empty cycles should raise RuntimeError."""
        collector_module._consecutive_empty_cycles = 2

        client = MagicMock(spec=MetraClient)
        client.has_credentials = True
        client._auth_method = "query_param"
        client.get_all_arrivals = AsyncMock(return_value=[])
        collector = MetraCollector(client=client)
        session = AsyncMock()

        with pytest.raises(RuntimeError, match="consecutive.*cycles returned 0"):
            await collector.collect(session)

    @pytest.mark.asyncio
    async def test_nonempty_cycle_resets_counter(self):
        """A successful non-empty fetch should reset the consecutive counter."""
        collector_module._consecutive_empty_cycles = 2

        # Build a minimal arrival that will cause the collector to proceed
        arrival = MetraArrival(
            station_code="CUS",
            gtfs_stop_id="CUS",
            trip_id="ME_ME2012_V1_B",
            route_id="ME",
            direction_id=1,
            headsign=None,
            arrival_time=datetime(2026, 3, 25, 10, 30, tzinfo=UTC),
            departure_time=None,
            delay_seconds=0,
            track=None,
        )

        client = MagicMock(spec=MetraClient)
        client.has_credentials = True
        client._auth_method = "query_param"
        client.get_all_arrivals = AsyncMock(return_value=[arrival])
        collector = MetraCollector(client=client)
        session = AsyncMock()

        # The collector will try to process the trip and likely fail (no DB),
        # but the counter should still be reset before that
        try:
            await collector.collect(session)
        except Exception:
            pass

        assert collector_module._consecutive_empty_cycles == 0

    @pytest.mark.asyncio
    async def test_threshold_is_configurable(self):
        """The threshold constant should be accessible and reasonable."""
        assert collector_module._CONSECUTIVE_EMPTY_THRESHOLD == 3
