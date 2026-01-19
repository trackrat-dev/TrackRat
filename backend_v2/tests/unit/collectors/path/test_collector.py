"""
Unit tests for PathCollector.

Tests unified PATH train discovery and journey update logic.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trackrat.collectors.path.collector import (
    PathCollector,
    _generate_path_train_id,
    _get_destination_station_from_headsign,
    _get_line_info_from_headsign,
    _headsign_matches_station,
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
        assert _normalize_headsign("Some Unknown Destination") == "some_unknown_destination"


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

        with patch("trackrat.collectors.path.collector.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock()

            mock_scalars_result = MagicMock()
            mock_scalars_result.all.return_value = []
            mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
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

        with patch("trackrat.collectors.path.collector.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_scalars_result = MagicMock()
            mock_scalars_result.all.return_value = []
            mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            await collector.run()

        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_does_not_close_external_client(self, collector, mock_client):
        """Test run method does not close externally provided client."""
        mock_client.get_all_arrivals.return_value = []

        with patch("trackrat.collectors.path.collector.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_scalars_result = MagicMock()
            mock_scalars_result.all.return_value = []
            mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
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
        session.add = MagicMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_discover_trains_filters_non_discovery_stations(
        self, collector, mock_client, mock_session
    ):
        """Test discover_trains filters out non-discovery stations."""
        arrivals = [
            PathArrival(
                station_code="PHO",  # Discovery station
                headsign="33rd Street",
                direction="ToNY",
                minutes_away=5,
                arrival_time=datetime.now() + timedelta(minutes=5),
                line_color="4D92FB",
                last_updated=None,
            ),
            PathArrival(
                station_code="PGR",  # NOT a discovery station
                headsign="33rd Street",
                direction="ToNY",
                minutes_away=3,
                arrival_time=datetime.now() + timedelta(minutes=3),
                line_color="4D92FB",
                last_updated=None,
            ),
        ]

        result = await collector._discover_trains(mock_session, arrivals)

        # Only PHO arrival should be processed
        assert result["discovery_arrivals"] == 1

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

        result = await collector._discover_trains(mock_session, arrivals)

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

        result = await collector._discover_trains(mock_session, arrivals)

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

        created = await collector._process_arrival_for_discovery(mock_session, arrival)

        assert created is True
        mock_session.add.assert_called()

    @pytest.mark.asyncio
    async def test_process_arrival_skips_existing_journey(self, collector, mock_session):
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

        created = await collector._process_arrival_for_discovery(mock_session, arrival)

        assert created is False

    @pytest.mark.asyncio
    async def test_process_arrival_uses_line_color_from_api(self, collector, mock_session):
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

        await collector._process_arrival_for_discovery(mock_session, arrival)

        add_call = mock_session.add.call_args_list[0]
        journey = add_call[0][0]
        assert journey.line_color == "#FF0000"


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
                return_value=mock_analyzer_instance
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
        """Test journey is marked expired after 2 API errors."""
        sample_journey.api_error_count = 1  # Already had one error
        mock_client.get_all_arrivals.side_effect = Exception("API Error")

        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()

        await collector.collect_journey_details(mock_session, sample_journey)

        assert sample_journey.api_error_count == 2
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
            result = await collector._update_journeys(mock_session, [])

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
