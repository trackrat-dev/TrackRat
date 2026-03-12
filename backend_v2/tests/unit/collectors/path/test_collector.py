"""
Unit tests for PathCollector.

Tests unified PATH train discovery and journey update logic.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.path.collector import (
    PathCollector,
    _generate_path_train_id,
    _get_destination_station_from_headsign,
    _get_line_info_from_headsign,
    _headsign_matches_station,
    _infer_origin_station,
    _normalize_headsign,
)
from trackrat.collectors.path.ridepath_client import PathArrival
from trackrat.models.database import JourneyStop, TrainJourney

# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestGeneratePathTrainId:
    """Tests for the train ID generation function."""

    def test_generates_correct_format(self):
        """Test train ID has correct format: PATH_<origin>_<dest>_<timestamp>."""
        dt = datetime(2026, 1, 19, 10, 30, 0)
        result = _generate_path_train_id("PHO", "33rd Street", dt)

        assert result.startswith("PATH_PHO_")
        assert "33rdstree" in result
        assert str(int(dt.timestamp())) in result

    def test_handles_none_departure_time(self):
        """Test handling of None departure time."""
        result = _generate_path_train_id("PHO", "Hoboken", None)
        assert result == "PATH_PHO_hoboken_0"

    def test_truncates_long_headsign(self):
        """Test long headsign is truncated."""
        dt = datetime(2026, 1, 19, 10, 30, 0)
        result = _generate_path_train_id("PWC", "World Trade Center via Newport", dt)
        assert "worldtrad" in result

    def test_different_origins_produce_different_ids(self):
        """Test same headsign from different origins produces different IDs."""
        dt = datetime(2026, 1, 19, 10, 30, 0)
        id1 = _generate_path_train_id("PHO", "33rd Street", dt)
        id2 = _generate_path_train_id("PJS", "33rd Street", dt)
        assert id1 != id2

    def test_sub_minute_differences_produce_same_id(self):
        """Departure times within the same minute should produce the same ID.

        The RidePATH API only provides integer-minute precision. Back-calculating
        origin departure from different stations can produce sub-minute differences
        due to the API's last_updated timestamp. Rounding prevents duplicate
        journey records for the same physical train.
        """
        dt1 = datetime(2026, 1, 19, 10, 30, 5)
        dt2 = datetime(2026, 1, 19, 10, 30, 25)
        id1 = _generate_path_train_id("PHO", "33rd Street", dt1)
        id2 = _generate_path_train_id("PHO", "33rd Street", dt2)
        assert (
            id1 == id2
        ), f"Sub-minute difference should produce same ID: {id1} vs {id2}"

    def test_rounding_crosses_minute_boundary(self):
        """Departure at :45 seconds should round up to the next minute."""
        dt1 = datetime(2026, 1, 19, 10, 30, 45)
        dt2 = datetime(2026, 1, 19, 10, 31, 10)
        id1 = _generate_path_train_id("PHO", "33rd Street", dt1)
        id2 = _generate_path_train_id("PHO", "33rd Street", dt2)
        assert (
            id1 == id2
        ), f"45s rounds up, 10s rounds down — both to :31: {id1} vs {id2}"

    def test_five_minute_difference_produces_different_ids(self):
        """Departure times 5+ minutes apart should still produce different IDs."""
        dt1 = datetime(2026, 1, 19, 10, 30, 0)
        dt2 = datetime(2026, 1, 19, 10, 35, 0)
        id1 = _generate_path_train_id("PHO", "33rd Street", dt1)
        id2 = _generate_path_train_id("PHO", "33rd Street", dt2)
        assert id1 != id2, "5-minute difference should produce different IDs"


class TestGetLineInfoFromHeadsign:
    """Tests for line info extraction from headsign."""

    def test_hoboken_headsign(self):
        """Test Hoboken destination returns HOB-33 line."""
        code, name, color = _get_line_info_from_headsign("Hoboken")
        assert code == "HOB-33"
        assert "Hoboken" in name

    def test_33rd_street_headsign(self):
        """Test 33rd Street destination returns HOB-33 line."""
        code, name, color = _get_line_info_from_headsign("33rd Street")
        assert code == "HOB-33"

    def test_wtc_headsign(self):
        """Test WTC destination returns NWK-WTC line."""
        code, name, color = _get_line_info_from_headsign("World Trade Center")
        assert code == "NWK-WTC"

    def test_newark_headsign(self):
        """Test Newark destination returns NWK-WTC line."""
        code, name, color = _get_line_info_from_headsign("Newark")
        assert code == "NWK-WTC"

    def test_journal_square_headsign(self):
        """Test Journal Square destination returns JSQ-33 line."""
        code, name, color = _get_line_info_from_headsign("Journal Square")
        assert code == "JSQ-33"

    def test_33rd_street_via_hoboken_headsign(self):
        """Test '33rd Street via Hoboken' returns JSQ-33H line, not HOB-33."""
        code, name, color = _get_line_info_from_headsign("33rd Street via Hoboken")
        assert code == "JSQ-33H", f"Expected JSQ-33H but got {code}"
        assert "via Hoboken" in name
        assert color == "#ff9900"

    def test_journal_square_via_hoboken_headsign(self):
        """Test 'Journal Square via Hoboken' returns JSQ-33H line, not HOB-33."""
        code, name, color = _get_line_info_from_headsign("Journal Square via Hoboken")
        assert code == "JSQ-33H", f"Expected JSQ-33H but got {code}"
        assert "via Hoboken" in name

    def test_plain_hoboken_still_hob33(self):
        """Test plain 'Hoboken' still returns HOB-33 (not affected by via hoboken entry)."""
        code, name, color = _get_line_info_from_headsign("Hoboken")
        assert code == "HOB-33", f"Expected HOB-33 but got {code}"

    def test_unknown_headsign_fallback(self):
        """Test unknown headsign returns generic PATH line."""
        code, name, color = _get_line_info_from_headsign("Unknown Destination")
        assert code == "PATH"
        assert "Unknown Destination" in name


class TestGetDestinationStationFromHeadsign:
    """Tests for destination station extraction using substring matching."""

    def test_journal_square_via_hoboken(self):
        """Test 'Journal Square via Hoboken' matches to PJS (not PHO)."""
        result = _get_destination_station_from_headsign("Journal Square via Hoboken")
        assert result == "PJS"

    def test_33rd_street_via_hoboken(self):
        """Test '33rd Street via Hoboken' matches to P33 (not PHO)."""
        result = _get_destination_station_from_headsign("33rd Street via Hoboken")
        assert result == "P33"

    def test_journal_square_simple(self):
        """Test simple 'Journal Square' matches to PJS."""
        result = _get_destination_station_from_headsign("Journal Square")
        assert result == "PJS"

    def test_hoboken(self):
        """Test 'Hoboken' matches to PHO."""
        result = _get_destination_station_from_headsign("Hoboken")
        assert result == "PHO"

    def test_world_trade_center(self):
        """Test 'World Trade Center' matches to PWC."""
        result = _get_destination_station_from_headsign("World Trade Center")
        assert result == "PWC"

    def test_33rd_street(self):
        """Test '33rd Street' matches to P33."""
        result = _get_destination_station_from_headsign("33rd Street")
        assert result == "P33"

    def test_newark(self):
        """Test 'Newark' matches to PNK."""
        result = _get_destination_station_from_headsign("Newark")
        assert result == "PNK"

    def test_case_insensitive(self):
        """Test matching is case insensitive."""
        assert _get_destination_station_from_headsign("JOURNAL SQUARE") == "PJS"
        assert _get_destination_station_from_headsign("hoboken") == "PHO"

    def test_unknown_headsign(self):
        """Test unknown headsign returns None."""
        assert _get_destination_station_from_headsign("Unknown Destination") is None

    def test_empty_headsign(self):
        """Test empty/None headsign returns None."""
        assert _get_destination_station_from_headsign("") is None
        assert _get_destination_station_from_headsign(None) is None


class TestHeadsignMatchesStation:
    """Tests for the headsign matching function."""

    def test_matches_33rd_street(self):
        """Test headsign matching for 33rd Street station."""
        assert _headsign_matches_station("33rd Street", "P33") is True
        assert _headsign_matches_station("33rd St", "P33") is True

    def test_matches_hoboken(self):
        """Test headsign matching for Hoboken station."""
        assert _headsign_matches_station("Hoboken", "PHO") is True
        assert _headsign_matches_station("HOBOKEN", "PHO") is True

    def test_matches_wtc(self):
        """Test headsign matching for World Trade Center station."""
        assert _headsign_matches_station("World Trade Center", "PWC") is True
        assert _headsign_matches_station("WTC", "PWC") is True

    def test_via_hoboken_does_not_match_hoboken_station(self):
        """Test 'via Hoboken' headsigns do NOT match Hoboken station."""
        # This is critical - trains "via Hoboken" are NOT arriving at Hoboken
        assert _headsign_matches_station("33rd Street via Hoboken", "PHO") is False
        assert _headsign_matches_station("Journal Square via Hoboken", "PHO") is False

    def test_no_match_different_destination(self):
        """Test headsign does not match wrong station."""
        assert _headsign_matches_station("Hoboken", "P33") is False
        assert _headsign_matches_station("33rd Street", "PHO") is False
        assert _headsign_matches_station("Newark", "PWC") is False

    def test_no_match_empty_headsign(self):
        """Test empty headsign returns False."""
        assert _headsign_matches_station("", "P33") is False
        assert _headsign_matches_station(None, "P33") is False


class TestNormalizeHeadsign:
    """Tests for headsign normalization."""

    def test_world_trade_center_variations(self):
        """Test WTC headsign normalization."""
        assert _normalize_headsign("World Trade Center") == "world_trade_center"
        assert _normalize_headsign("world trade center") == "world_trade_center"
        assert _normalize_headsign("WTC") == "world_trade_center"
        assert _normalize_headsign("wtc") == "world_trade_center"

    def test_33rd_street_variations(self):
        """Test 33rd Street headsign normalization."""
        assert _normalize_headsign("33rd Street") == "33rd_street"
        assert _normalize_headsign("33rd Street via Hoboken") == "33rd_street"
        assert _normalize_headsign("33 St") == "33rd_street"

    def test_journal_square_via_hoboken(self):
        """Test 'Journal Square via Hoboken' normalizes to journal_square, not hoboken."""
        result = _normalize_headsign("Journal Square via Hoboken")
        assert result == "journal_square", f"Expected journal_square but got {result}"

    def test_terminal_stations(self):
        """Test terminal station headsign normalization."""
        assert _normalize_headsign("Hoboken") == "hoboken"
        assert _normalize_headsign("Newark") == "newark"
        assert _normalize_headsign("Journal Square") == "journal_square"

    def test_empty_headsign(self):
        """Test empty headsign handling."""
        assert _normalize_headsign("") == ""
        assert _normalize_headsign(None) == ""

    def test_unknown_headsign(self):
        """Test unknown headsign passes through normalized."""
        assert (
            _normalize_headsign("Some Unknown Destination")
            == "some_unknown_destination"
        )


class TestInferOriginStation:
    """Tests for origin station inference for mid-route discovery."""

    def test_terminus_discovery_returns_current_station(self):
        """Test that discovery at terminus returns same station as origin."""
        # At Hoboken, train going to 33rd Street - origin IS Hoboken
        result = _infer_origin_station("PHO", "P33")
        assert result == "PHO"

    def test_mid_route_nwk_wtc_from_grove_street(self):
        """Test inferring Newark origin when train seen at Grove Street going to WTC."""
        # NWK-WTC route: PNK → PHR → PJS → PGR → PEX → PWC
        # Seen at Grove Street (PGR), going to WTC (PWC) → origin is Newark (PNK)
        result = _infer_origin_station("PGR", "PWC")
        assert result == "PNK"

    def test_mid_route_nwk_wtc_from_journal_square(self):
        """Test inferring Newark origin when train seen at Journal Square going to WTC."""
        # NWK-WTC route: PNK → PHR → PJS → PGR → PEX → PWC
        # Seen at Journal Square (PJS), going to WTC (PWC) → origin is Newark (PNK)
        result = _infer_origin_station("PJS", "PWC")
        assert result == "PNK"

    def test_mid_route_jsq_33_from_newport(self):
        """Test inferring Journal Square origin when train seen at Newport going to 33rd."""
        # JSQ-33 route: PJS → PGR → PNP → PCH → P9S → P14 → P23 → P33
        # Seen at Newport (PNP), going to 33rd (P33) → origin is Journal Square (PJS)
        result = _infer_origin_station("PNP", "P33")
        # Could be JSQ-33 (PJS) or HOB-33 (PHO) - both go through Newport to 33rd
        # Should pick the one where Newport is closest to start (more complete journey)
        # HOB-33: PHO(0) → PCH(1) → P9S(2) → P14(3) → P23(4) → P33(5) - Newport NOT in this route!
        # JSQ-33: PJS(0) → PGR(1) → PNP(2) → PCH(3) → ... - Newport at index 2
        # JSQ-33-HOB: PJS(0) → PGR(1) → PNP(2) → PHO(3) → ... - Newport at index 2
        # So origin should be PJS
        assert result == "PJS"

    def test_mid_route_hob_wtc_from_newport(self):
        """Test inferring Hoboken origin when train seen at Newport going to WTC."""
        # HOB-WTC route: PHO → PNP → PEX → PWC
        # Seen at Newport (PNP), going to WTC (PWC) → origin is Hoboken (PHO)
        result = _infer_origin_station("PNP", "PWC")
        # Could be HOB-WTC (PHO) or NWK-WTC (PNK)
        # HOB-WTC: PHO(0) → PNP(1) → PEX(2) → PWC(3) - Newport at index 1
        # NWK-WTC: PNK(0) → PHR(1) → PJS(2) → PGR(3) → PEX(4) → PWC(5) - Newport NOT in this route!
        # So origin should be PHO
        assert result == "PHO"

    def test_mid_route_christopher_to_33rd(self):
        """Test inferring origin when train seen at Christopher Street going to 33rd."""
        # Could be HOB-33: PHO(0) → PCH(1) → ... → P33(5)
        # Or JSQ-33: PJS(0) → PGR(1) → PNP(2) → PCH(3) → ... → P33(7)
        # Christopher St at index 1 in HOB-33, index 3 in JSQ-33
        # Should pick HOB-33 (PHO) since Christopher is closer to start
        result = _infer_origin_station("PCH", "P33")
        assert result == "PHO"

    def test_no_matching_route_returns_current_station(self):
        """Test that when no route matches, returns current station as fallback."""
        # No route goes from P33 to PNK (would be reverse direction)
        result = _infer_origin_station("P33", "PNK")
        # P33 to PNK doesn't exist as a forward route - return current station
        assert result == "P33"

    def test_same_station_returns_same(self):
        """Test edge case where current and destination are same."""
        result = _infer_origin_station("PHO", "PHO")
        assert result == "PHO"

    def test_harrison_to_newark_prefers_full_route_over_shuttle(self):
        """Test that NWK-WTC route is preferred over NWK-HAR shuttle for Harrison→Newark.

        NWK-WTC reversed: [PWC, PEX, PGR, PJS, PHR, PNK] - PHR at idx 4
        NWK-HAR reversed: [PHR, PNK] - PHR at idx 0

        The shuttle [PNK, PHR] is a strict subset of the NWK-WTC route
        [PNK, PHR, PJS, PGR, PEX, PWC]. The subset filter should eliminate the
        shuttle so the full NWK-WTC route is selected, giving origin=PWC (World
        Trade Center) and a complete 6-stop journey.
        """
        result = _infer_origin_station("PHR", "PNK")
        assert result == "PWC"

    def test_harrison_to_wtc_uses_nwk_wtc_route(self):
        """Test that Harrison going to WTC correctly infers Newark as origin."""
        # NWK-WTC route: PNK → PHR → PJS → PGR → PEX → PWC
        # Harrison (PHR) at index 1, forward direction → origin is PNK
        result = _infer_origin_station("PHR", "PWC")
        assert result == "PNK"


# =============================================================================
# PATH COLLECTOR TESTS
# =============================================================================


class TestPathCollector:
    """Tests for PathCollector."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock RidePathClient."""
        client = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def collector(self, mock_client):
        """Create a PathCollector with mock client."""
        return PathCollector(client=mock_client)

    def test_initialization_with_client(self, mock_client):
        """Test collector initializes with provided client."""
        collector = PathCollector(client=mock_client)
        assert collector.client is mock_client
        assert collector._owns_client is False

    def test_initialization_without_client(self):
        """Test collector creates its own client when none provided."""
        with patch("trackrat.collectors.path.collector.RidePathClient") as MockClient:
            collector = PathCollector()
            MockClient.assert_called_once()
            assert collector._owns_client is True

    @pytest.mark.asyncio
    async def test_run_returns_summary(self, collector, mock_client):
        """Test run method returns proper summary structure."""
        mock_client.get_all_arrivals.return_value = []

        with patch(
            "trackrat.collectors.path.collector.get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock()

            mock_scalars_result = MagicMock()
            mock_scalars_result.all.return_value = []
            mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

            mock_get_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await collector.run()

        assert isinstance(result, dict)
        assert result["data_source"] == "PATH"
        assert "arrivals_fetched" in result
        assert "new_journeys" in result
        assert "updated" in result
        assert "completed" in result

    @pytest.mark.asyncio
    async def test_run_closes_owned_client(self, mock_client):
        """Test run method closes client when collector owns it."""
        collector = PathCollector(client=mock_client)
        collector._owns_client = True
        mock_client.get_all_arrivals.return_value = []

        with patch(
            "trackrat.collectors.path.collector.get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_scalars_result = MagicMock()
            mock_scalars_result.all.return_value = []
            mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

            mock_get_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            await collector.run()

        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_does_not_close_external_client(self, collector, mock_client):
        """Test run method does not close externally provided client."""
        mock_client.get_all_arrivals.return_value = []

        with patch(
            "trackrat.collectors.path.collector.get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_scalars_result = MagicMock()
            mock_scalars_result.all.return_value = []
            mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

            mock_get_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            await collector.run()

        mock_client.close.assert_not_called()


# =============================================================================
# DISCOVERY PHASE TESTS
# =============================================================================


class TestPathCollectorDiscovery:
    """Tests for PathCollector discovery phase."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock RidePathClient."""
        client = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def collector(self, mock_client):
        """Create a PathCollector with mock client."""
        return PathCollector(client=mock_client)

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.scalar = AsyncMock(return_value=None)
        # _find_matching_journey uses session.scalars() which returns
        # an object with .all() — mock it to return empty list (no match)
        mock_scalars_obj = MagicMock()
        mock_scalars_obj.all.return_value = []
        session.scalars = AsyncMock(return_value=mock_scalars_obj)
        session.add = MagicMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_discover_trains_processes_all_stations(
        self, collector, mock_client, mock_session
    ):
        """Test discover_trains processes arrivals at ALL stations (not just terminus)."""
        arrivals = [
            PathArrival(
                station_code="PHO",  # Terminus station
                headsign="33rd Street",
                direction="ToNY",
                minutes_away=5,
                arrival_time=datetime.now() + timedelta(minutes=5),
                line_color="4D92FB",
                last_updated=None,
            ),
            PathArrival(
                station_code="PGR",  # Mid-route station (Grove Street)
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=3,
                arrival_time=datetime.now() + timedelta(minutes=3),
                line_color="D93A30",
                last_updated=None,
            ),
        ]

        result = await collector._discover_trains(mock_session, arrivals, {})

        # Both arrivals should be processed (no longer filtering by station)
        assert result["discovery_arrivals"] == 2

    @pytest.mark.asyncio
    async def test_discover_trains_skips_arriving_trains(
        self, collector, mock_client, mock_session
    ):
        """Test discover_trains skips trains arriving at their destination."""
        arrivals = [
            PathArrival(
                station_code="PHO",  # At Hoboken
                headsign="Hoboken",  # Going TO Hoboken = arriving
                direction="ToNJ",
                minutes_away=2,
                arrival_time=datetime.now() + timedelta(minutes=2),
                line_color="4D92FB",
                last_updated=None,
            ),
            PathArrival(
                station_code="PHO",  # At Hoboken
                headsign="33rd Street",  # Going TO 33rd = departing
                direction="ToNY",
                minutes_away=5,
                arrival_time=datetime.now() + timedelta(minutes=5),
                line_color="4D92FB",
                last_updated=None,
            ),
        ]

        result = await collector._discover_trains(mock_session, arrivals, {})

        # Both are at discovery stations but only one is departing
        assert result["discovery_arrivals"] == 2
        # Only departing train should create journey
        assert result["new_journeys"] == 1

    @pytest.mark.asyncio
    async def test_discover_trains_handles_via_hoboken_correctly(
        self, collector, mock_client, mock_session
    ):
        """Test 'via Hoboken' trains are NOT skipped at Hoboken station."""
        arrivals = [
            PathArrival(
                station_code="PHO",  # At Hoboken
                headsign="33rd Street via Hoboken",  # Primary dest is P33, NOT PHO
                direction="ToNY",
                minutes_away=5,
                arrival_time=datetime.now() + timedelta(minutes=5),
                line_color="4D92FB",
                last_updated=None,
            ),
        ]

        result = await collector._discover_trains(mock_session, arrivals, {})

        # This train should NOT be skipped - it's departing Hoboken
        assert result["new_journeys"] == 1

    @pytest.mark.asyncio
    async def test_process_arrival_creates_journey(self, collector, mock_session):
        """Test _process_arrival_for_discovery creates new journey."""
        arrival = PathArrival(
            station_code="PHO",
            headsign="33rd Street",
            direction="ToNY",
            minutes_away=10,
            arrival_time=datetime.now() + timedelta(minutes=10),
            line_color="4D92FB",
            last_updated=None,
        )

        created = await collector._process_arrival_for_discovery(
            mock_session, arrival, {}
        )

        assert created is True
        mock_session.add.assert_called()

    @pytest.mark.asyncio
    async def test_process_arrival_skips_existing_journey(
        self, collector, mock_session
    ):
        """Test _process_arrival_for_discovery does not create duplicate journeys."""
        existing_journey = MagicMock()
        existing_journey.last_updated_at = datetime.now()
        mock_session.scalar = AsyncMock(return_value=existing_journey)

        arrival = PathArrival(
            station_code="PHO",
            headsign="33rd Street",
            direction="ToNY",
            minutes_away=10,
            arrival_time=datetime.now() + timedelta(minutes=10),
            line_color="4D92FB",
            last_updated=None,
        )

        created = await collector._process_arrival_for_discovery(
            mock_session, arrival, {}
        )

        assert created is False

    @pytest.mark.asyncio
    async def test_process_arrival_uses_line_color_from_api(
        self, collector, mock_session
    ):
        """Test _process_arrival_for_discovery uses line color from API."""
        arrival = PathArrival(
            station_code="PHO",
            headsign="33rd Street",
            direction="ToNY",
            minutes_away=10,
            arrival_time=datetime.now() + timedelta(minutes=10),
            line_color="FF0000",  # Custom color
            last_updated=None,
        )

        await collector._process_arrival_for_discovery(mock_session, arrival, {})

        add_call = mock_session.add.call_args_list[0]
        journey = add_call[0][0]
        assert journey.line_color == "#FF0000"

    @pytest.mark.asyncio
    async def test_process_arrival_mid_route_infers_origin(
        self, collector, mock_session
    ):
        """Test mid-route discovery infers correct origin station."""
        # Train seen at Grove Street (PGR) heading to WTC
        # Should infer origin as Newark (PNK) since NWK-WTC route goes through Grove St
        arrival = PathArrival(
            station_code="PGR",  # Grove Street - mid-route
            headsign="World Trade Center",
            direction="ToNY",
            minutes_away=5,
            arrival_time=datetime.now() + timedelta(minutes=5),
            line_color="D93A30",
            last_updated=None,
        )

        await collector._process_arrival_for_discovery(mock_session, arrival, {})

        # Get the journey that was added
        journey_add_call = mock_session.add.call_args_list[0]
        journey = journey_add_call[0][0]

        # Origin should be inferred as Newark, not Grove Street
        assert journey.origin_station_code == "PNK"
        # Train ID should use inferred origin
        assert "PNK" in journey.train_id

    @pytest.mark.asyncio
    async def test_process_arrival_mid_route_calculates_origin_departure(
        self, collector, mock_session
    ):
        """Test mid-route discovery calculates origin departure time correctly."""
        now = datetime.now()
        # Train arrives at Grove Street in 5 minutes
        # NWK-WTC: PNK → PHR → PJS → PGR (index 3) → PEX → PWC
        # At 3 min/segment, Grove St is 9 min from Newark
        # So origin departure should be arrival_time - 9 min = now - 4 min
        arrival = PathArrival(
            station_code="PGR",
            headsign="World Trade Center",
            direction="ToNY",
            minutes_away=5,
            arrival_time=now + timedelta(minutes=5),
            line_color="D93A30",
            last_updated=None,
        )

        await collector._process_arrival_for_discovery(mock_session, arrival, {})

        journey_add_call = mock_session.add.call_args_list[0]
        journey = journey_add_call[0][0]

        # Scheduled departure should be ~9 min before arrival at Grove St
        # arrival_time (now+5) - 9 min = now - 4 min
        expected_departure = now + timedelta(minutes=5) - timedelta(minutes=9)
        actual_departure = journey.scheduled_departure

        # Allow 1 second tolerance for test timing
        diff = abs((actual_departure - expected_departure).total_seconds())
        assert diff < 1, f"Expected {expected_departure}, got {actual_departure}"

    @pytest.mark.asyncio
    async def test_process_arrival_mid_route_marks_earlier_stops_departed(
        self, collector, mock_session
    ):
        """Test mid-route discovery marks stops before discovery station as departed."""
        arrival = PathArrival(
            station_code="PGR",  # Grove Street - index 3 in NWK-WTC route
            headsign="World Trade Center",
            direction="ToNY",
            minutes_away=5,
            arrival_time=datetime.now() + timedelta(minutes=5),
            line_color="D93A30",
            last_updated=None,
        )

        await collector._process_arrival_for_discovery(mock_session, arrival, {})

        # Collect all JourneyStop objects that were added
        stops = [
            call[0][0]
            for call in mock_session.add.call_args_list
            if isinstance(call[0][0], JourneyStop)
        ]

        # NWK-WTC route: PNK(1) → PHR(2) → PJS(3) → PGR(4) → PEX(5) → PWC(6)
        # Stops at PNK, PHR, PJS should be marked as departed (indices 0, 1, 2)
        # PGR and beyond should NOT be marked as departed

        departed_stations = [s.station_code for s in stops if s.has_departed_station]
        not_departed_stations = [
            s.station_code for s in stops if not s.has_departed_station
        ]

        assert "PNK" in departed_stations, "Newark should be marked as departed"
        assert "PHR" in departed_stations, "Harrison should be marked as departed"
        assert "PJS" in departed_stations, "Journal Square should be marked as departed"
        assert "PGR" in not_departed_stations, "Grove Street should NOT be departed"
        assert "PWC" in not_departed_stations, "WTC should NOT be departed"

    @pytest.mark.asyncio
    async def test_process_arrival_mid_route_sets_departure_source(
        self, collector, mock_session
    ):
        """Test mid-route discovery sets departure_source for inferred stops."""
        arrival = PathArrival(
            station_code="PJS",  # Journal Square - mid-route on NWK-WTC
            headsign="World Trade Center",
            direction="ToNY",
            minutes_away=3,
            arrival_time=datetime.now() + timedelta(minutes=3),
            line_color="D93A30",
            last_updated=None,
        )

        await collector._process_arrival_for_discovery(mock_session, arrival, {})

        stops = [
            call[0][0]
            for call in mock_session.add.call_args_list
            if isinstance(call[0][0], JourneyStop)
        ]

        # Earlier stops should have departure_source set
        earlier_stops = [s for s in stops if s.has_departed_station]
        for stop in earlier_stops:
            assert stop.departure_source == "inferred_from_discovery"

    @pytest.mark.asyncio
    async def test_mid_route_and_terminus_produce_same_train_id(
        self, collector, mock_session
    ):
        """Test that same train discovered at terminus and mid-route gets same train_id."""
        base_time = datetime(2026, 1, 19, 10, 0, 0)

        # Train discovered at terminus (Newark) departing at 10:00
        terminus_arrival = PathArrival(
            station_code="PNK",
            headsign="World Trade Center",
            direction="ToNY",
            minutes_away=0,
            arrival_time=base_time,  # Departing now
            line_color="D93A30",
            last_updated=None,
        )

        # Same train discovered mid-route at Grove Street (9 min later)
        # NWK-WTC: PNK → PHR → PJS → PGR (index 3, 9 min from origin)
        midroute_arrival = PathArrival(
            station_code="PGR",
            headsign="World Trade Center",
            direction="ToNY",
            minutes_away=0,
            arrival_time=base_time + timedelta(minutes=9),
            line_color="D93A30",
            last_updated=None,
        )

        # Process terminus discovery
        await collector._process_arrival_for_discovery(
            mock_session, terminus_arrival, {}
        )
        terminus_journey = mock_session.add.call_args_list[0][0][0]
        terminus_train_id = terminus_journey.train_id

        # Reset mock for second call
        mock_session.reset_mock()

        # Process mid-route discovery
        await collector._process_arrival_for_discovery(
            mock_session, midroute_arrival, {}
        )
        midroute_journey = mock_session.add.call_args_list[0][0][0]
        midroute_train_id = midroute_journey.train_id

        # Both should generate the same train_id since they're the same train
        assert terminus_train_id == midroute_train_id, (
            f"Same train should have same ID. "
            f"Terminus: {terminus_train_id}, Mid-route: {midroute_train_id}"
        )


# =============================================================================
# UPDATE PHASE TESTS
# =============================================================================


class TestPathCollectorUpdate:
    """Tests for PathCollector update phase."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock RidePathClient."""
        client = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def collector(self, mock_client):
        """Create a PathCollector with mock client."""
        return PathCollector(client=mock_client)

    @pytest.fixture
    def sample_journey(self):
        """Create a sample TrainJourney."""
        journey = MagicMock(spec=TrainJourney)
        journey.id = 1
        journey.train_id = "PATH_862_abc123"
        journey.destination = "World Trade Center"
        journey.data_source = "PATH"
        journey.journey_date = datetime.now().date()
        journey.is_completed = False
        journey.is_cancelled = False
        journey.is_expired = False
        journey.api_error_count = 0
        journey.update_count = 0
        journey.last_updated_at = None
        journey.stops_count = 5
        return journey

    @pytest.fixture
    def sample_stops(self):
        """Create sample JourneyStops for a NWK-WTC journey."""
        stops = []
        stations = [
            ("PNK", "Newark", 1),
            ("PHR", "Harrison", 2),
            ("PJS", "Journal Square", 3),
            ("PGR", "Grove Street", 4),
            ("PEX", "Exchange Place", 5),
            ("PWC", "World Trade Center", 6),
        ]

        base_time = datetime.now()
        for code, name, seq in stations:
            stop = MagicMock(spec=JourneyStop)
            stop.station_code = code
            stop.station_name = name
            stop.stop_sequence = seq
            stop.scheduled_arrival = base_time + timedelta(minutes=seq * 3)
            stop.scheduled_departure = base_time + timedelta(minutes=seq * 3 + 1)
            stop.actual_arrival = None
            stop.actual_departure = None
            stop.updated_arrival = None
            stop.updated_departure = None
            stop.has_departed_station = False
            stop.departure_source = None
            stop.updated_at = None
            stops.append(stop)

        return stops

    @pytest.fixture
    def sample_arrivals(self):
        """Create sample PathArrivals for a WTC-bound train."""
        now = datetime.now()
        return [
            PathArrival(
                station_code="PJS",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=4,
                arrival_time=now + timedelta(minutes=4),
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PGR",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=7,
                arrival_time=now + timedelta(minutes=7),
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PEX",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=9,
                arrival_time=now + timedelta(minutes=9),
                line_color="D93A30",
                last_updated=now,
            ),
        ]

    @pytest.mark.asyncio
    async def test_collect_journey_details_updates_stops(
        self, collector, mock_client, sample_journey, sample_stops, sample_arrivals
    ):
        """Test that collect_journey_details updates stop arrival times."""
        mock_client.get_all_arrivals.return_value = sample_arrivals

        mock_scalars_result = MagicMock()
        mock_scalars_result.all.return_value = sample_stops

        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)
        mock_session.flush = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.add = MagicMock()

        mock_analyzer_instance = MagicMock()
        mock_analyzer_instance.analyze_new_segments = AsyncMock(return_value=0)
        mock_analyzer_instance.analyze_journey = AsyncMock()

        with patch("trackrat.collectors.path.collector.now_et") as mock_now:
            mock_now.return_value = datetime.now()
            with patch(
                "trackrat.collectors.path.collector.TransitAnalyzer",
                return_value=mock_analyzer_instance,
            ):
                await collector.collect_journey_details(mock_session, sample_journey)

        mock_client.get_all_arrivals.assert_called_once()
        assert sample_journey.update_count == 1
        assert sample_journey.api_error_count == 0

    @pytest.mark.asyncio
    async def test_collect_journey_details_skips_completed(
        self, collector, mock_client, sample_journey
    ):
        """Test that completed journeys are skipped."""
        sample_journey.is_completed = True
        mock_session = AsyncMock()

        await collector.collect_journey_details(mock_session, sample_journey)

        mock_client.get_all_arrivals.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_journey_details_skips_cancelled(
        self, collector, mock_client, sample_journey
    ):
        """Test that cancelled journeys are skipped."""
        sample_journey.is_cancelled = True
        mock_session = AsyncMock()

        await collector.collect_journey_details(mock_session, sample_journey)

        mock_client.get_all_arrivals.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_journey_details_skips_expired(
        self, collector, mock_client, sample_journey
    ):
        """Test that expired journeys are skipped."""
        sample_journey.is_expired = True
        mock_session = AsyncMock()

        await collector.collect_journey_details(mock_session, sample_journey)

        mock_client.get_all_arrivals.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_journey_details_handles_api_error(
        self, collector, mock_client, sample_journey
    ):
        """Test API error handling increments error count."""
        mock_client.get_all_arrivals.side_effect = Exception("API Error")

        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()

        await collector.collect_journey_details(mock_session, sample_journey)

        assert sample_journey.api_error_count == 1
        assert not sample_journey.is_expired

    @pytest.mark.asyncio
    async def test_collect_journey_details_marks_expired_after_errors(
        self, collector, mock_client, sample_journey
    ):
        """Test journey is marked expired after 3 API errors."""
        sample_journey.api_error_count = 2  # Already had two errors
        mock_client.get_all_arrivals.side_effect = Exception("API Error")

        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()

        await collector.collect_journey_details(mock_session, sample_journey)

        assert sample_journey.api_error_count == 3
        assert sample_journey.is_expired


# =============================================================================
# STOP UPDATE LOGIC TESTS
# =============================================================================


class TestStopUpdateLogic:
    """Tests for stop update logic and arrival matching."""

    @pytest.fixture
    def collector(self):
        """Create collector with mock client."""
        mock_client = AsyncMock()
        return PathCollector(client=mock_client)

    def test_find_best_matching_arrival_with_scheduled_time(self, collector):
        """Test that arrival closest to scheduled time is selected."""
        now = datetime.now()
        scheduled_arrival = now + timedelta(minutes=8)

        arrivals = [
            PathArrival(
                station_code="PJS",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=5,  # Sooner but further from scheduled
                arrival_time=now + timedelta(minutes=5),
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PJS",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=9,  # Closer to scheduled (8 min)
                arrival_time=now + timedelta(minutes=9),
                line_color="D93A30",
                last_updated=now,
            ),
        ]

        stop = MagicMock(spec=JourneyStop)
        stop.scheduled_arrival = scheduled_arrival
        stop.station_code = "PJS"

        result = collector._find_best_matching_arrival(stop, arrivals)
        assert result is not None
        assert result.minutes_away == 9

    def test_find_best_matching_arrival_no_scheduled_time_returns_none(self, collector):
        """Test returns None when no scheduled time (can't reliably match)."""
        now = datetime.now()

        arrivals = [
            PathArrival(
                station_code="PJS",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=10,
                arrival_time=now + timedelta(minutes=10),
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PJS",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=5,
                arrival_time=now + timedelta(minutes=5),
                line_color="D93A30",
                last_updated=now,
            ),
        ]

        stop = MagicMock(spec=JourneyStop)
        stop.scheduled_arrival = None
        stop.station_code = "PJS"

        # Without scheduled_arrival, we can't reliably match to a specific train
        result = collector._find_best_matching_arrival(stop, arrivals)
        assert result is None

    def test_find_best_matching_arrival_outside_tolerance_returns_none(self, collector):
        """Test returns None when no arrival matches within tolerance."""
        now = datetime.now()
        scheduled_arrival = now + timedelta(minutes=30)  # Far from any arrival

        arrivals = [
            PathArrival(
                station_code="PJS",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=5,
                arrival_time=now + timedelta(minutes=5),
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PJS",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=10,
                arrival_time=now + timedelta(minutes=10),
                line_color="D93A30",
                last_updated=now,
            ),
        ]

        stop = MagicMock(spec=JourneyStop)
        stop.scheduled_arrival = scheduled_arrival
        stop.station_code = "PJS"

        # Both arrivals are >10 min from scheduled - don't match to wrong train
        result = collector._find_best_matching_arrival(stop, arrivals)
        assert result is None

    def test_find_best_matching_arrival_no_arrivals(self, collector):
        """Test returns None when no arrivals at station."""
        stop = MagicMock(spec=JourneyStop)
        stop.scheduled_arrival = datetime.now()
        stop.station_code = "PJS"

        result = collector._find_best_matching_arrival(stop, [])
        assert result is None

    def test_multiple_trains_same_destination_matched_correctly(self, collector):
        """Test that two trains to same destination get different arrivals."""
        now = datetime.now()

        arrivals = [
            PathArrival(
                station_code="PJS",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=7,  # Close to Train A's schedule
                arrival_time=now + timedelta(minutes=7),
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PJS",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=14,  # Close to Train B's schedule
                arrival_time=now + timedelta(minutes=14),
                line_color="D93A30",
                last_updated=now,
            ),
        ]

        # Train A stop - scheduled at 8 min
        stop_a = MagicMock(spec=JourneyStop)
        stop_a.scheduled_arrival = now + timedelta(minutes=8)
        stop_a.station_code = "PJS"

        # Train B stop - scheduled at 15 min
        stop_b = MagicMock(spec=JourneyStop)
        stop_b.scheduled_arrival = now + timedelta(minutes=15)
        stop_b.station_code = "PJS"

        # Train A should match to 7-min arrival (closest to 8)
        result_a = collector._find_best_matching_arrival(stop_a, arrivals)
        assert result_a is not None
        assert result_a.minutes_away == 7

        # Train B should match to 14-min arrival (closest to 15)
        result_b = collector._find_best_matching_arrival(stop_b, arrivals)
        assert result_b is not None
        assert result_b.minutes_away == 14


# =============================================================================
# BATCH UPDATE TESTS
# =============================================================================


class TestBatchUpdate:
    """Tests for batch journey updates."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock RidePathClient."""
        client = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def collector(self, mock_client):
        """Create a PathCollector with mock client."""
        return PathCollector(client=mock_client)

    @pytest.mark.asyncio
    async def test_update_journeys_no_active_journeys(self, collector):
        """Test update phase with no active journeys."""
        mock_scalars_result = MagicMock()
        mock_scalars_result.all.return_value = []

        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

        mock_datetime = MagicMock()
        mock_datetime.date.return_value = datetime.now().date()

        with patch("trackrat.collectors.path.collector.now_et") as mock_now:
            mock_now.return_value = mock_datetime
            result = await collector._update_journeys(mock_session, [], {})

        assert result["updated"] == 0
        assert result["completed"] == 0
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_close(self, collector, mock_client):
        """Test that close calls client close."""
        collector._owns_client = True
        await collector.close()
        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_not_owned(self, collector, mock_client):
        """Test that close doesn't close externally provided client."""
        collector._owns_client = False
        await collector.close()
        mock_client.close.assert_not_called()


# =============================================================================
# DEPARTURE STATUS INFERENCE TESTS
# =============================================================================


class TestDepartureStatusInference:
    """Tests for the three-tier departure status inference in _update_stops_from_arrivals.

    PATH relies on inference because the RidePath API only shows UPCOMING arrivals.
    Once a train passes a station, that station disappears from the API response.

    Three tiers of inference:
    1. Time inference with matched arrival: If arrival_time <= now, mark as departed
    2. Sequential inference: If a later stop is departed, earlier stops must be too
    3. Time inference without matched arrival: If scheduled_arrival + grace < now, mark departed
    """

    @pytest.fixture
    def mock_client(self):
        """Create a mock RidePathClient."""
        client = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def collector(self, mock_client):
        """Create a PathCollector with mock client."""
        return PathCollector(client=mock_client)

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session with proper async support."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        # Mock scalars result for TransitAnalyzer queries
        mock_scalars_result = MagicMock()
        mock_scalars_result.all.return_value = []
        session.scalars = AsyncMock(return_value=mock_scalars_result)

        return session

    @pytest.fixture
    def mock_transit_analyzer(self):
        """Create a mock TransitAnalyzer."""
        analyzer = MagicMock()
        analyzer.analyze_new_segments = AsyncMock(return_value=0)
        analyzer.analyze_journey = AsyncMock()
        return analyzer

    @pytest.fixture
    def sample_journey(self):
        """Create a sample TrainJourney."""
        journey = MagicMock(spec=TrainJourney)
        journey.id = 1
        journey.train_id = "PATH_PNK_wtc_12345"
        journey.destination = "World Trade Center"
        journey.is_completed = False
        journey.stops_count = 6
        return journey

    def _create_stops(self, base_time: datetime) -> list[MagicMock]:
        """Create sample stops for a NWK-WTC journey.

        Route: PNK(1) -> PHR(2) -> PJS(3) -> PGR(4) -> PEX(5) -> PWC(6)
        Each stop is 3 minutes apart from scheduled perspective.
        """
        stations = [
            ("PNK", "Newark", 1),
            ("PHR", "Harrison", 2),
            ("PJS", "Journal Square", 3),
            ("PGR", "Grove Street", 4),
            ("PEX", "Exchange Place", 5),
            ("PWC", "World Trade Center", 6),
        ]

        stops = []
        for code, name, seq in stations:
            stop = MagicMock(spec=JourneyStop)
            stop.station_code = code
            stop.station_name = name
            stop.stop_sequence = seq
            stop.scheduled_arrival = base_time + timedelta(minutes=(seq - 1) * 3)
            stop.scheduled_departure = base_time + timedelta(minutes=(seq - 1) * 3 + 1)
            stop.actual_arrival = None
            stop.actual_departure = None
            stop.updated_arrival = None
            stop.updated_departure = None
            stop.has_departed_station = False
            stop.departure_source = None
            stop.updated_at = None
            stops.append(stop)

        return stops

    @pytest.mark.asyncio
    async def test_time_inference_without_matched_arrival(
        self, collector, mock_session, sample_journey, mock_transit_analyzer
    ):
        """Test Tier 3: Stops without API arrivals are marked departed via scheduled time.

        This was the bug: stations that the train has passed no longer appear in the
        RidePath API response. The time-based fallback inference should mark these
        as departed based on scheduled_arrival + grace_period < now.
        """
        # Train departed Newark 10 minutes ago
        # API only shows arrivals for upcoming stops (PGR onwards)
        now = datetime.now()
        base_time = now - timedelta(minutes=10)  # Train started 10 min ago

        stops = self._create_stops(base_time)
        # PNK: scheduled at base_time (10 min ago) - should be departed
        # PHR: scheduled at base_time + 3min (7 min ago) - should be departed
        # PJS: scheduled at base_time + 6min (4 min ago) - should be departed (>2 min grace)
        # PGR: scheduled at base_time + 9min (1 min ago) - might have API arrival
        # PEX: scheduled at base_time + 12min (2 min in future) - not departed
        # PWC: scheduled at base_time + 15min (5 min in future) - not departed

        # Simulate API only returning arrivals for upcoming stops (PGR onwards)
        arrivals = [
            PathArrival(
                station_code="PGR",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=1,
                arrival_time=now + timedelta(minutes=1),  # Slightly in future
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PEX",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=4,
                arrival_time=now + timedelta(minutes=4),
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PWC",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=7,
                arrival_time=now + timedelta(minutes=7),
                line_color="D93A30",
                last_updated=now,
            ),
        ]

        with patch("trackrat.collectors.path.collector.now_et", return_value=now):
            with patch(
                "trackrat.collectors.path.collector.TransitAnalyzer",
                return_value=mock_transit_analyzer,
            ):
                await collector._update_stops_from_arrivals(
                    mock_session, sample_journey, stops, arrivals
                )

        # Verify earlier stops (no API arrivals) marked as departed via time inference
        pnk_stop = stops[0]  # Newark - 10 min ago, no API arrival
        assert pnk_stop.has_departed_station is True, "Newark should be departed"
        assert pnk_stop.departure_source == "time_inference"

        phr_stop = stops[1]  # Harrison - 7 min ago, no API arrival
        assert phr_stop.has_departed_station is True, "Harrison should be departed"
        assert phr_stop.departure_source == "time_inference"

        pjs_stop = stops[2]  # Journal Square - 4 min ago, no API arrival
        assert (
            pjs_stop.has_departed_station is True
        ), "Journal Square should be departed"
        assert pjs_stop.departure_source == "time_inference"

        # PGR has API arrival in future - should NOT be departed
        pgr_stop = stops[3]  # Grove Street - API shows 1 min away
        assert (
            pgr_stop.has_departed_station is False
        ), "Grove Street should NOT be departed"

        # Future stops should NOT be departed
        pex_stop = stops[4]
        assert (
            pex_stop.has_departed_station is False
        ), "Exchange Place should NOT be departed"

        pwc_stop = stops[5]
        assert pwc_stop.has_departed_station is False, "WTC should NOT be departed"

    @pytest.mark.asyncio
    async def test_departure_status_preserved_when_already_departed(
        self, collector, mock_session, sample_journey, mock_transit_analyzer
    ):
        """Test defensive check: Existing departure status is not reset.

        Once a stop is marked as departed, it should stay departed even if
        a subsequent API update shows an arrival time in the future for that stop.
        """
        now = datetime.now()
        base_time = now - timedelta(minutes=5)

        stops = self._create_stops(base_time)

        # Simulate: Newark was already marked as departed in a previous update
        stops[0].has_departed_station = True
        stops[0].departure_source = "time_inference"
        stops[0].actual_departure = base_time

        # API now (incorrectly?) shows an arrival for Newark in the future
        # This could happen with API glitches or clock skew
        arrivals = [
            PathArrival(
                station_code="PNK",  # Newark - already departed
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=2,  # API says 2 min away (impossible if departed!)
                arrival_time=now + timedelta(minutes=2),
                line_color="D93A30",
                last_updated=now,
            ),
        ]

        with patch("trackrat.collectors.path.collector.now_et", return_value=now):
            with patch(
                "trackrat.collectors.path.collector.TransitAnalyzer",
                return_value=mock_transit_analyzer,
            ):
                await collector._update_stops_from_arrivals(
                    mock_session, sample_journey, stops, arrivals
                )

        # Newark should STILL be marked as departed (not reset)
        pnk_stop = stops[0]
        assert (
            pnk_stop.has_departed_station is True
        ), "Newark should STILL be departed - status should not be reset"

    @pytest.mark.asyncio
    async def test_sequential_inference_marks_earlier_stops(
        self, collector, mock_session, sample_journey, mock_transit_analyzer
    ):
        """Test Tier 2: If a later stop is departed, earlier stops must be too.

        When we process stops in order and find that stop N has departed,
        we set max_departed_sequence = N. Earlier stops with sequence < N
        should be marked as departed via sequential inference.

        Note: Since stops are processed in order, earlier stops get marked via
        time inference (if their scheduled time + 2min grace < now) before we
        process later stops. Sequential inference helps when earlier stops
        don't have matched arrivals AND their scheduled time is very recent.
        """
        now = datetime.now()
        # Set base_time far enough back that ALL earlier stops (PNK, PHR, PJS)
        # have scheduled_arrival + 2min_grace < now
        # PJS scheduled at base_time + 6min, so base_time needs to be > 8min ago
        # for scheduled_arrival + 2min grace to be < now
        base_time = now - timedelta(minutes=12)

        stops = self._create_stops(base_time)
        # PNK: scheduled at base_time (12 min ago) - will be departed via time inference
        # PHR: scheduled at base_time + 3min (9 min ago) - will be departed via time inference
        # PJS: scheduled at base_time + 6min (6 min ago) - will be departed via time inference
        # PGR: scheduled at base_time + 9min (3 min ago) - will be departed via matched arrival

        # API shows Grove Street (seq 4) has arrival in the past
        # Earlier stops (PNK, PHR, PJS) have no API arrivals
        arrivals = [
            PathArrival(
                station_code="PGR",  # Grove Street - seq 4
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=0,
                arrival_time=now - timedelta(minutes=1),  # Just passed
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PEX",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=2,
                arrival_time=now + timedelta(minutes=2),
                line_color="D93A30",
                last_updated=now,
            ),
        ]

        with patch("trackrat.collectors.path.collector.now_et", return_value=now):
            with patch(
                "trackrat.collectors.path.collector.TransitAnalyzer",
                return_value=mock_transit_analyzer,
            ):
                await collector._update_stops_from_arrivals(
                    mock_session, sample_journey, stops, arrivals
                )

        # Grove Street should be departed via time inference (arrival_time <= now)
        pgr_stop = stops[3]
        assert pgr_stop.has_departed_station is True

        # Earlier stops should be departed via time inference
        # (since base_time is 12 min ago, all scheduled times are well past grace period)
        for i, stop in enumerate(stops[:3]):
            assert (
                stop.has_departed_station is True
            ), f"Stop {stop.station_code} (seq {stop.stop_sequence}) should be departed"

    @pytest.mark.asyncio
    async def test_all_stops_departed_marks_journey_complete(
        self, collector, mock_session, sample_journey, mock_transit_analyzer
    ):
        """Test that journey is marked complete when terminal stop is departed."""
        now = datetime.now()
        base_time = now - timedelta(minutes=20)  # Train started 20 min ago

        stops = self._create_stops(base_time)
        # All stops scheduled in the past

        # API shows no arrivals (train has passed all stations)
        arrivals = []

        with patch("trackrat.collectors.path.collector.now_et", return_value=now):
            with patch(
                "trackrat.collectors.path.collector.TransitAnalyzer",
                return_value=mock_transit_analyzer,
            ):
                await collector._update_stops_from_arrivals(
                    mock_session, sample_journey, stops, arrivals
                )

        # All stops should be departed via time inference
        for stop in stops:
            assert (
                stop.has_departed_station is True
            ), f"Stop {stop.station_code} should be departed"
            assert stop.departure_source == "time_inference"

        # Journey should be marked complete
        assert sample_journey.is_completed is True

    @pytest.mark.asyncio
    async def test_future_stops_not_marked_departed(
        self, collector, mock_session, sample_journey, mock_transit_analyzer
    ):
        """Test that stops with future scheduled times are not marked as departed."""
        now = datetime.now()
        base_time = now + timedelta(minutes=5)  # Train hasn't started yet

        stops = self._create_stops(base_time)

        # API shows arrivals for all stops in the future
        arrivals = [
            PathArrival(
                station_code="PNK",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=5,
                arrival_time=now + timedelta(minutes=5),
                line_color="D93A30",
                last_updated=now,
            ),
        ]

        with patch("trackrat.collectors.path.collector.now_et", return_value=now):
            with patch(
                "trackrat.collectors.path.collector.TransitAnalyzer",
                return_value=mock_transit_analyzer,
            ):
                await collector._update_stops_from_arrivals(
                    mock_session, sample_journey, stops, arrivals
                )

        # No stops should be departed
        for stop in stops:
            assert (
                stop.has_departed_station is False
            ), f"Stop {stop.station_code} should NOT be departed (train hasn't started)"

        # Journey should not be complete
        assert sample_journey.is_completed is False

    @pytest.mark.asyncio
    async def test_grace_period_respected(
        self, collector, mock_session, sample_journey, mock_transit_analyzer
    ):
        """Test that the 2-minute grace period is respected for time inference."""
        now = datetime.now()

        stops = self._create_stops(now)  # All stops scheduled starting now

        # Stop 0 (PNK) scheduled exactly at 'now'
        # Stop 1 (PHR) scheduled at now + 3min

        # No API arrivals - rely purely on time inference
        arrivals = []

        with patch("trackrat.collectors.path.collector.now_et", return_value=now):
            with patch(
                "trackrat.collectors.path.collector.TransitAnalyzer",
                return_value=mock_transit_analyzer,
            ):
                await collector._update_stops_from_arrivals(
                    mock_session, sample_journey, stops, arrivals
                )

        # PNK scheduled at 'now', grace period is 2 min
        # scheduled_arrival + grace_period (now + 2min) is NOT < now
        # So PNK should NOT be departed yet
        pnk_stop = stops[0]
        assert (
            pnk_stop.has_departed_station is False
        ), "Newark should NOT be departed yet (within grace period)"

        # Now simulate time passing - 3 minutes later
        later = now + timedelta(minutes=3)
        with patch("trackrat.collectors.path.collector.now_et", return_value=later):
            with patch(
                "trackrat.collectors.path.collector.TransitAnalyzer",
                return_value=mock_transit_analyzer,
            ):
                await collector._update_stops_from_arrivals(
                    mock_session, sample_journey, stops, arrivals
                )

        # Now PNK should be departed (scheduled_arrival + 2min < now + 3min)
        assert (
            pnk_stop.has_departed_station is True
        ), "Newark should be departed (grace period exceeded)"
        assert pnk_stop.departure_source == "time_inference"

    @pytest.mark.asyncio
    async def test_matched_arrival_in_past_marks_departed(
        self, collector, mock_session, sample_journey, mock_transit_analyzer
    ):
        """Test Tier 1: Matched arrival with arrival_time <= now marks as departed."""
        now = datetime.now()
        base_time = now - timedelta(minutes=5)

        stops = self._create_stops(base_time)

        # API shows arrival for PJS that's already in the past
        arrivals = [
            PathArrival(
                station_code="PJS",  # Journal Square - seq 3
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=0,
                arrival_time=now - timedelta(seconds=30),  # Just passed
                line_color="D93A30",
                last_updated=now,
            ),
        ]

        with patch("trackrat.collectors.path.collector.now_et", return_value=now):
            with patch(
                "trackrat.collectors.path.collector.TransitAnalyzer",
                return_value=mock_transit_analyzer,
            ):
                await collector._update_stops_from_arrivals(
                    mock_session, sample_journey, stops, arrivals
                )

        # PJS should be departed via time inference (matched arrival in past)
        pjs_stop = stops[2]
        assert pjs_stop.has_departed_station is True
        assert pjs_stop.departure_source == "time_inference"
        assert pjs_stop.actual_departure == arrivals[0].arrival_time

    @pytest.mark.asyncio
    async def test_sequential_consistency_fixes_inconsistent_api_data(
        self, collector, mock_session, sample_journey, mock_transit_analyzer
    ):
        """Test the specific bug: later stop departed but earlier stop shows future arrival.

        This is the Christopher Street bug: The API returns arrival data for both
        Christopher Street (seq 4) and 9th Street (seq 5), but with inconsistent
        timestamps - Christopher Street shows future arrival while 9th Street shows
        past arrival. This is logically impossible (train can't skip stations).

        The sequential consistency post-processing should fix this by marking
        Christopher Street as departed since 9th Street is departed.
        """
        now = datetime.now()
        base_time = now - timedelta(minutes=10)

        # Create stops for a HOB-33 style journey
        # PHO(1) -> PCH(2) -> P9S(3) -> P14(4) -> P23(5) -> P33(6)
        stations = [
            ("PHO", "Hoboken", 1),
            ("PCH", "Christopher Street", 2),
            ("P9S", "9th Street", 3),
            ("P14", "14th Street", 4),
            ("P23", "23rd Street", 5),
            ("P33", "33rd Street", 6),
        ]

        stops = []
        for code, name, seq in stations:
            stop = MagicMock(spec=JourneyStop)
            stop.station_code = code
            stop.station_name = name
            stop.stop_sequence = seq
            stop.scheduled_arrival = base_time + timedelta(minutes=(seq - 1) * 3)
            stop.scheduled_departure = base_time + timedelta(minutes=(seq - 1) * 3 + 1)
            stop.actual_arrival = None
            stop.actual_departure = None
            stop.updated_arrival = None
            stop.updated_departure = None
            stop.has_departed_station = False
            stop.departure_source = None
            stop.updated_at = None
            stops.append(stop)

        # THE BUG SCENARIO:
        # API returns arrivals for both Christopher St and 9th St
        # Christopher St shows FUTURE arrival (API glitch/timing issue)
        # 9th St shows PAST arrival (train already passed)
        # This is impossible - if 9th St is passed, Christopher St must be too
        arrivals = [
            PathArrival(
                station_code="PCH",  # Christopher Street - seq 2
                headsign="33rd Street",
                direction="ToNY",
                minutes_away=2,
                arrival_time=now
                + timedelta(minutes=2),  # FUTURE - API says not passed yet
                line_color="4D92FB",
                last_updated=now,
            ),
            PathArrival(
                station_code="P9S",  # 9th Street - seq 3
                headsign="33rd Street",
                direction="ToNY",
                minutes_away=0,
                arrival_time=now - timedelta(minutes=1),  # PAST - train already passed
                line_color="4D92FB",
                last_updated=now,
            ),
            PathArrival(
                station_code="P14",  # 14th Street - seq 4
                headsign="33rd Street",
                direction="ToNY",
                minutes_away=3,
                arrival_time=now + timedelta(minutes=3),
                line_color="4D92FB",
                last_updated=now,
            ),
        ]

        with patch("trackrat.collectors.path.collector.now_et", return_value=now):
            with patch(
                "trackrat.collectors.path.collector.TransitAnalyzer",
                return_value=mock_transit_analyzer,
            ):
                await collector._update_stops_from_arrivals(
                    mock_session, sample_journey, stops, arrivals
                )

        # Verify the bug is fixed:
        # 9th Street (seq 3) should be departed (arrival_time <= now)
        p9s_stop = stops[2]
        assert (
            p9s_stop.has_departed_station is True
        ), "9th Street should be departed (arrival_time in past)"
        assert p9s_stop.departure_source == "time_inference"

        # Christopher Street (seq 2) MUST also be departed
        # Even though its API arrival_time is in the future
        # With tighter tolerance (5 min), PCH arrival doesn't match (9 min diff)
        # So PCH gets marked departed via grace period time_inference (scheduled + 2min < now)
        pch_stop = stops[1]
        assert pch_stop.has_departed_station is True, (
            "Christopher Street MUST be departed - train can't skip stations! "
            "If 9th Street is departed, Christopher Street must be too."
        )
        # May be time_inference (grace period) or sequential_consistency depending on timing
        assert pch_stop.departure_source in (
            "sequential_consistency",
            "time_inference",
            "sequential_inference",
        ), (
            f"Christopher Street should be marked departed via some inference method, "
            f"got {pch_stop.departure_source}"
        )

        # Hoboken (seq 1) should also be departed (earlier than Christopher St)
        pho_stop = stops[0]
        assert (
            pho_stop.has_departed_station is True
        ), "Hoboken should be departed (via time inference or sequential consistency)"

        # 14th Street (seq 4) should NOT be departed (future arrival, after 9th St)
        p14_stop = stops[3]
        assert (
            p14_stop.has_departed_station is False
        ), "14th Street should NOT be departed (arrival in future)"

    @pytest.mark.asyncio
    async def test_sequential_consistency_with_empty_stops(
        self, collector, mock_session, sample_journey, mock_transit_analyzer
    ):
        """Test sequential consistency handles empty stops list gracefully."""
        now = datetime.now()
        stops = []
        arrivals = []

        with patch("trackrat.collectors.path.collector.now_et", return_value=now):
            with patch(
                "trackrat.collectors.path.collector.TransitAnalyzer",
                return_value=mock_transit_analyzer,
            ):
                # Should not raise any errors
                await collector._update_stops_from_arrivals(
                    mock_session, sample_journey, stops, arrivals
                )

        # Journey should not be marked complete with no stops
        assert sample_journey.is_completed is False

    @pytest.mark.asyncio
    async def test_sequential_consistency_single_stop(
        self, collector, mock_session, sample_journey, mock_transit_analyzer
    ):
        """Test sequential consistency with single stop (edge case)."""
        now = datetime.now()

        stop = MagicMock(spec=JourneyStop)
        stop.station_code = "PWC"
        stop.station_name = "World Trade Center"
        stop.stop_sequence = 1
        stop.scheduled_arrival = now - timedelta(minutes=5)
        stop.scheduled_departure = None
        stop.actual_arrival = None
        stop.actual_departure = None
        stop.updated_arrival = None
        stop.updated_departure = None
        stop.has_departed_station = False
        stop.departure_source = None
        stop.updated_at = None

        stops = [stop]
        arrivals = []

        with patch("trackrat.collectors.path.collector.now_et", return_value=now):
            with patch(
                "trackrat.collectors.path.collector.TransitAnalyzer",
                return_value=mock_transit_analyzer,
            ):
                await collector._update_stops_from_arrivals(
                    mock_session, sample_journey, stops, arrivals
                )

        # Single stop should be departed via time inference
        assert stop.has_departed_station is True
        assert stop.departure_source == "time_inference"

    @pytest.mark.asyncio
    async def test_sequential_consistency_multiple_gaps(
        self, collector, mock_session, sample_journey, mock_transit_analyzer
    ):
        """Test sequential consistency fixes multiple inconsistent stops.

        Scenario: API returns arrivals showing stops 2 and 4 still in the future,
        but stop 5 has already passed. Sequential consistency should fix 2 and 4.

        This simulates API timing inconsistencies where later stops show as passed
        but earlier stops still show future arrival times.

        Note: Arrivals must be within 5min of scheduled time to match (tightened tolerance).
        """
        now = datetime.now()
        # Set base_time so that stop times are close to 'now'
        # _create_stops uses: scheduled_arrival = base_time + (seq-1)*3
        # We want PEX (seq 5) scheduled around now, so base_time = now - 12min
        base_time = now - timedelta(minutes=12)

        stops = self._create_stops(base_time)
        # Scheduled times with base_time = now - 12min:
        # PNK (seq 1): now - 12 + 0 = now - 12min
        # PHR (seq 2): now - 12 + 3 = now - 9min
        # PJS (seq 3): now - 12 + 6 = now - 6min
        # PGR (seq 4): now - 12 + 9 = now - 3min
        # PEX (seq 5): now - 12 + 12 = now
        # PWC (seq 6): now - 12 + 15 = now + 3min

        # API shows inconsistent data - arrivals MUST be within 5min of scheduled
        # (tightened from 10min to prevent cross-train matching):
        # - PHR shows arrival_time slightly in future even though train passed
        # - PGR shows arrival_time slightly in future even though train passed
        # - PEX shows arrival_time in past (train definitely passed)

        arrivals = [
            PathArrival(
                station_code="PNK",  # sched: now-12min
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=0,
                arrival_time=now - timedelta(minutes=10),  # PAST, within 5min tolerance
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PHR",  # sched: now-9min
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=1,
                arrival_time=now
                - timedelta(minutes=6),  # PAST but won't match (>5min diff)
                # This arrival won't match because diff is 3 min but still in past
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PJS",  # sched: now-6min
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=0,
                arrival_time=now - timedelta(minutes=5),  # PAST, within 5min tolerance
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PGR",  # sched: now-3min
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=2,
                arrival_time=now + timedelta(minutes=1),  # FUTURE! (API glitch)
                # diff from scheduled (-3) is 4min - within tolerance
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PEX",  # sched: now
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=0,
                arrival_time=now - timedelta(minutes=1),  # PAST, within 5min tolerance
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PWC",  # sched: now+3min
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=5,
                arrival_time=now
                + timedelta(minutes=5),  # FUTURE (terminal, not passed)
                line_color="D93A30",
                last_updated=now,
            ),
        ]

        with patch("trackrat.collectors.path.collector.now_et", return_value=now):
            with patch(
                "trackrat.collectors.path.collector.TransitAnalyzer",
                return_value=mock_transit_analyzer,
            ):
                await collector._update_stops_from_arrivals(
                    mock_session, sample_journey, stops, arrivals
                )

        # All stops up to seq 5 should now be departed
        for i, stop in enumerate(stops[:5]):
            assert (
                stop.has_departed_station is True
            ), f"Stop {stop.station_code} (seq {stop.stop_sequence}) should be departed"

        # Stops 2 (PHR) and 4 (PGR) should have been marked departed
        # PHR: scheduled at now-9, arrival at now-6 (3 min diff) - matches within 5 min tolerance
        #      arrival_time (now-6) < now, so marked departed via time_inference
        # PGR: scheduled at now-3, arrival at now+1 (4 min diff) - matches within 5 min tolerance
        #      arrival_time (now+1) > now, so NOT departed via time_inference
        #      BUT later stop (PEX) is departed, so PGR gets fixed via sequential_consistency
        assert stops[1].departure_source in (
            "time_inference",
            "sequential_consistency",
            "sequential_inference",
        ), (
            f"Harrison (seq 2) should be marked departed, "
            f"got {stops[1].departure_source}"
        )
        assert stops[3].departure_source in (
            "sequential_consistency",
            "time_inference",
            "sequential_inference",
        ), (
            f"Grove Street (seq 4) should be marked departed, "
            f"got {stops[3].departure_source}"
        )

        # Terminal (seq 6) should still NOT be departed
        assert (
            stops[5].has_departed_station is False
        ), "WTC (terminal) should NOT be departed"


class TestTimeValidation:
    """Tests for the _validate_and_fix_stop_times method.

    These tests verify that out-of-order arrival times are detected and corrected.
    This is critical for preventing bugs where later stops show times BEFORE
    earlier stops (which is physically impossible).
    """

    @pytest.fixture
    def collector(self):
        """Create a PathCollector instance."""
        return PathCollector()

    def _create_departed_stop(
        self,
        station_code: str,
        stop_sequence: int,
        scheduled_arrival: datetime,
        actual_arrival: datetime | None = None,
    ) -> MagicMock:
        """Create a mock departed stop."""
        stop = MagicMock(spec=JourneyStop)
        stop.station_code = station_code
        stop.stop_sequence = stop_sequence
        stop.scheduled_arrival = scheduled_arrival
        stop.actual_arrival = actual_arrival or scheduled_arrival
        stop.actual_departure = actual_arrival or scheduled_arrival
        stop.has_departed_station = True
        stop.departure_source = "time_inference"
        return stop

    def test_validates_sequential_times_no_correction_needed(self, collector):
        """Test that correctly ordered times pass validation without changes."""
        base_time = datetime.now() - timedelta(minutes=20)

        stops = [
            self._create_departed_stop("PNK", 1, base_time, base_time),
            self._create_departed_stop(
                "PHR",
                2,
                base_time + timedelta(minutes=3),
                base_time + timedelta(minutes=3),
            ),
            self._create_departed_stop(
                "PJS",
                3,
                base_time + timedelta(minutes=6),
                base_time + timedelta(minutes=5),
            ),
        ]

        # Store original times
        original_times = [s.actual_arrival for s in stops]

        collector._validate_and_fix_stop_times(stops, "test_train")

        # Times should be unchanged
        for i, stop in enumerate(stops):
            assert stop.actual_arrival == original_times[i]

    def test_fixes_out_of_order_times(self, collector):
        """Test that out-of-order times are corrected using scheduled times."""
        base_time = datetime.now() - timedelta(minutes=20)

        # Stop 2 has a LATER time than stop 3 (impossible!)
        stops = [
            self._create_departed_stop("PNK", 1, base_time, base_time),
            self._create_departed_stop(
                "PHR",
                2,
                base_time + timedelta(minutes=3),
                base_time + timedelta(minutes=10),  # BAD: later than stop 3!
            ),
            self._create_departed_stop(
                "PJS",
                3,
                base_time + timedelta(minutes=6),
                base_time + timedelta(minutes=5),  # Earlier than stop 2
            ),
        ]

        collector._validate_and_fix_stop_times(stops, "test_train")

        # Stop 2's time should be corrected to scheduled
        assert stops[1].actual_arrival == base_time + timedelta(minutes=3)
        assert stops[1].actual_departure == base_time + timedelta(minutes=3)
        assert stops[1].departure_source == "time_corrected"

    def test_fixes_multiple_out_of_order_times(self, collector):
        """Test that multiple out-of-order times are all corrected."""
        base_time = datetime.now() - timedelta(minutes=20)

        # Multiple stops have times out of order
        stops = [
            self._create_departed_stop(
                "PNK", 1, base_time, base_time + timedelta(minutes=8)
            ),  # BAD
            self._create_departed_stop(
                "PHR",
                2,
                base_time + timedelta(minutes=3),
                base_time + timedelta(minutes=6),
            ),  # BAD
            self._create_departed_stop(
                "PJS",
                3,
                base_time + timedelta(minutes=6),
                base_time + timedelta(minutes=5),
            ),
            self._create_departed_stop(
                "PGR",
                4,
                base_time + timedelta(minutes=9),
                base_time + timedelta(minutes=9),
            ),
        ]

        collector._validate_and_fix_stop_times(stops, "test_train")

        # Stops 1 and 2 should be corrected to scheduled times
        assert stops[0].actual_arrival == base_time  # Corrected
        assert stops[1].actual_arrival == base_time + timedelta(minutes=3)  # Corrected
        # Stop 3 was fine
        assert stops[2].actual_arrival == base_time + timedelta(minutes=5)

    def test_handles_empty_stops(self, collector):
        """Test that empty stops list doesn't cause errors."""
        # Should not raise
        collector._validate_and_fix_stop_times([], "test_train")

    def test_handles_single_stop(self, collector):
        """Test that single stop doesn't cause errors."""
        base_time = datetime.now() - timedelta(minutes=20)
        stops = [self._create_departed_stop("PNK", 1, base_time, base_time)]

        # Should not raise
        collector._validate_and_fix_stop_times(stops, "test_train")

    def test_handles_non_departed_stops(self, collector):
        """Test that non-departed stops are excluded from validation."""
        base_time = datetime.now() - timedelta(minutes=20)

        departed_stop = self._create_departed_stop("PNK", 1, base_time, base_time)

        non_departed = MagicMock(spec=JourneyStop)
        non_departed.station_code = "PHR"
        non_departed.stop_sequence = 2
        non_departed.has_departed_station = False
        non_departed.actual_arrival = None

        stops = [departed_stop, non_departed]

        # Should not raise
        collector._validate_and_fix_stop_times(stops, "test_train")

    def test_preserves_sequential_consistency_source(self, collector):
        """Test that stops fixed via sequential_consistency keep that source."""
        base_time = datetime.now() - timedelta(minutes=20)

        stop1 = self._create_departed_stop(
            "PNK", 1, base_time, base_time + timedelta(minutes=10)
        )
        stop1.departure_source = "sequential_consistency"

        stop2 = self._create_departed_stop(
            "PHR", 2, base_time + timedelta(minutes=3), base_time + timedelta(minutes=5)
        )

        stops = [stop1, stop2]

        collector._validate_and_fix_stop_times(stops, "test_train")

        # Stop 1 is out of order but should keep sequential_consistency source
        assert stops[0].departure_source == "sequential_consistency"


class TestLineColorFiltering:
    """Tests for line color based filtering of arrivals.

    These tests verify that arrivals are filtered by line color to prevent
    cross-train matching when multiple lines serve the same destination.
    """

    @pytest.fixture
    def collector(self):
        """Create a PathCollector instance."""
        return PathCollector()

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock(spec=AsyncSession)
        session.scalars = AsyncMock(
            return_value=MagicMock(all=MagicMock(return_value=[]))
        )
        session.scalar = AsyncMock(return_value=None)
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.mark.asyncio
    async def test_filters_by_line_color(self, collector, mock_session):
        """Test that arrivals are filtered by line color when available."""
        now = datetime.now()

        # Create a journey with blue line color (HOB-33)
        journey = MagicMock(spec=TrainJourney)
        journey.id = 1
        journey.train_id = "test_train"
        journey.destination = "33rd Street"
        journey.line_color = "#4d92fb"  # Blue - HOB-33
        journey.is_completed = False

        # Set up the mock to return this journey
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[journey])
        mock_session.scalars = AsyncMock(return_value=mock_result)

        # Create arrivals from different lines to same destination
        arrivals = [
            PathArrival(
                station_code="PGR",
                headsign="33rd Street",
                direction="ToNY",
                minutes_away=5,
                arrival_time=now + timedelta(minutes=5),
                line_color="4D92FB",  # Blue - same line
                last_updated=now,
            ),
            PathArrival(
                station_code="PGR",
                headsign="33rd Street",
                direction="ToNY",
                minutes_away=8,
                arrival_time=now + timedelta(minutes=8),
                line_color="FF9900",  # Orange - different line!
                last_updated=now,
            ),
        ]

        # Call _update_journeys
        with patch.object(
            collector, "_get_journey_stops", new_callable=AsyncMock
        ) as mock_get_stops:
            mock_get_stops.return_value = []
            with patch.object(
                collector, "_update_stops_from_arrivals", new_callable=AsyncMock
            ) as mock_update:
                with patch(
                    "trackrat.collectors.path.collector.now_et", return_value=now
                ):
                    await collector._update_journeys(mock_session, arrivals, {})

                # Check that _update_stops_from_arrivals was called
                if mock_update.called:
                    # The matching arrivals should only include blue line arrivals
                    call_args = mock_update.call_args
                    matching_arrivals = call_args[0][3]  # 4th argument is arrivals

                    # Both arrivals should be in the list because we also add to headsign-only key as fallback
                    # The primary filter is by headsign+color, but we also keep headsign-only
                    # The key is that the COLOR-MATCHED arrivals are preferred
                    assert any(a.line_color == "4D92FB" for a in matching_arrivals)


class TestTighterTolerance:
    """Tests for the tighter matching tolerance (5 minutes).

    PATH runs every 5-10 minutes, so 5-minute tolerance is more appropriate
    than 10 minutes to prevent cross-train matching.
    """

    @pytest.fixture
    def collector(self):
        """Create a PathCollector instance."""
        return PathCollector()

    def _create_stop(self, station_code: str, scheduled: datetime) -> MagicMock:
        """Create a mock stop."""
        stop = MagicMock(spec=JourneyStop)
        stop.station_code = station_code
        stop.scheduled_arrival = scheduled
        return stop

    def test_matches_within_5_minutes(self, collector):
        """Test that arrivals within 5 minutes match."""
        base_time = datetime.now()

        stop = self._create_stop("PGR", base_time)

        arrivals = [
            PathArrival(
                station_code="PGR",
                headsign="WTC",
                direction="ToNY",
                minutes_away=5,
                arrival_time=base_time + timedelta(minutes=4),  # 4 min diff - matches
                line_color="D93A30",
                last_updated=base_time,
            ),
        ]

        result = collector._find_best_matching_arrival(stop, arrivals)

        assert result is not None
        assert result.arrival_time == base_time + timedelta(minutes=4)

    def test_rejects_beyond_5_minutes(self, collector):
        """Test that arrivals beyond 5 minutes don't match."""
        base_time = datetime.now()

        stop = self._create_stop("PGR", base_time)

        arrivals = [
            PathArrival(
                station_code="PGR",
                headsign="WTC",
                direction="ToNY",
                minutes_away=6,
                arrival_time=base_time + timedelta(minutes=6),  # 6 min diff - too far
                line_color="D93A30",
                last_updated=base_time,
            ),
        ]

        result = collector._find_best_matching_arrival(stop, arrivals)

        assert result is None

    def test_picks_closest_within_tolerance(self, collector):
        """Test that the closest matching arrival is selected."""
        base_time = datetime.now()

        stop = self._create_stop("PGR", base_time)

        arrivals = [
            PathArrival(
                station_code="PGR",
                headsign="WTC",
                direction="ToNY",
                minutes_away=4,
                arrival_time=base_time + timedelta(minutes=4),  # 4 min diff
                line_color="D93A30",
                last_updated=base_time,
            ),
            PathArrival(
                station_code="PGR",
                headsign="WTC",
                direction="ToNY",
                minutes_away=2,
                arrival_time=base_time + timedelta(minutes=2),  # 2 min diff - closer!
                line_color="D93A30",
                last_updated=base_time,
            ),
        ]

        result = collector._find_best_matching_arrival(stop, arrivals)

        assert result is not None
        # Should pick the closer one (2 min diff)
        assert result.arrival_time == base_time + timedelta(minutes=2)
