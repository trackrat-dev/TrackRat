"""
Unit tests for PathDiscoveryCollector.

Tests train discovery logic using RidePATH API.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trackrat.collectors.path.ridepath_client import PathArrival
from trackrat.collectors.path.discovery import (
    PathDiscoveryCollector,
    _generate_path_train_id,
    _get_line_info_from_headsign,
    _headsign_matches_station,
)


class TestGeneratePathTrainId:
    """Tests for the train ID generation function."""

    def test_generates_correct_format(self):
        """Test train ID has correct format: PATH_<origin>_<dest>_<timestamp>."""
        dt = datetime(2026, 1, 19, 10, 30, 0)
        result = _generate_path_train_id("PHO", "33rd Street", dt)

        assert result.startswith("PATH_PHO_")
        # "33rd Street"[:10] = "33rd Stree" -> "33rdstree" after space removal and lowercase
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

        # "World Trade..."[:10] = "World Trad" -> "worldtrad" after space removal and lowercase
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

    def test_matches_newark(self):
        """Test headsign matching for Newark station."""
        assert _headsign_matches_station("Newark", "PNK") is True

    def test_matches_journal_square(self):
        """Test headsign matching for Journal Square station."""
        assert _headsign_matches_station("Journal Square", "PJS") is True
        assert _headsign_matches_station("JSQ", "PJS") is True

    def test_no_match_different_destination(self):
        """Test headsign does not match wrong station."""
        assert _headsign_matches_station("Hoboken", "P33") is False
        assert _headsign_matches_station("33rd Street", "PHO") is False
        assert _headsign_matches_station("Newark", "PWC") is False

    def test_no_match_empty_headsign(self):
        """Test empty headsign returns False."""
        assert _headsign_matches_station("", "P33") is False
        assert _headsign_matches_station(None, "P33") is False


class TestPathDiscoveryCollector:
    """Tests for PathDiscoveryCollector."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock RidePathClient."""
        client = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def collector(self, mock_client):
        """Create a PathDiscoveryCollector with mock client."""
        collector = PathDiscoveryCollector(client=mock_client)
        return collector

    def test_initialization_with_client(self, mock_client):
        """Test collector initializes with provided client."""
        collector = PathDiscoveryCollector(client=mock_client)
        assert collector.client is mock_client
        assert collector._owns_client is False

    def test_initialization_without_client(self):
        """Test collector creates its own client when none provided."""
        with patch(
            "trackrat.collectors.path.discovery.RidePathClient"
        ) as MockClient:
            collector = PathDiscoveryCollector()
            MockClient.assert_called_once()
            assert collector._owns_client is True

    async def test_discover_trains_returns_train_ids(self, collector, mock_client):
        """Test discover_trains returns list of train IDs from arrivals."""
        mock_client.get_all_arrivals.return_value = [
            PathArrival(
                station_code="PHO",
                headsign="33rd Street",
                direction="ToNY",
                minutes_away=5,
                arrival_time=datetime.now() + timedelta(minutes=5),
                line_color="4D92FB", last_updated=None,
            ),
            PathArrival(
                station_code="PWC",
                headsign="Newark",
                direction="ToNJ",
                minutes_away=3,
                arrival_time=datetime.now() + timedelta(minutes=3),
                line_color="D93A30", last_updated=None,
            ),
        ]

        result = await collector.discover_trains()

        assert isinstance(result, list)
        assert len(result) == 2

    async def test_discover_trains_filters_non_discovery_stations(
        self, collector, mock_client
    ):
        """Test discover_trains filters out non-discovery stations."""
        mock_client.get_all_arrivals.return_value = [
            PathArrival(
                station_code="PHO",  # Discovery station
                headsign="33rd Street",
                direction="ToNY",
                minutes_away=5,
                arrival_time=datetime.now() + timedelta(minutes=5),
                line_color="4D92FB", last_updated=None,
            ),
            PathArrival(
                station_code="PGR",  # NOT a discovery station
                headsign="33rd Street",
                direction="ToNY",
                minutes_away=3,
                arrival_time=datetime.now() + timedelta(minutes=3),
                line_color="4D92FB", last_updated=None,
            ),
        ]

        result = await collector.discover_trains()

        # Only PHO arrival should be discovered
        assert len(result) == 1

    async def test_discover_trains_skips_arriving_trains(
        self, collector, mock_client
    ):
        """Test discover_trains skips trains arriving at their destination."""
        mock_client.get_all_arrivals.return_value = [
            PathArrival(
                station_code="PHO",  # At Hoboken
                headsign="Hoboken",  # Going TO Hoboken = arriving
                direction="ToNJ",
                minutes_away=2,
                arrival_time=datetime.now() + timedelta(minutes=2),
                line_color="4D92FB", last_updated=None,
            ),
            PathArrival(
                station_code="PHO",  # At Hoboken
                headsign="33rd Street",  # Going TO 33rd = departing
                direction="ToNY",
                minutes_away=5,
                arrival_time=datetime.now() + timedelta(minutes=5),
                line_color="4D92FB", last_updated=None,
            ),
        ]

        result = await collector.discover_trains()

        # Only departing train (to 33rd) should be discovered
        assert len(result) == 1

    async def test_discover_trains_handles_api_error(self, collector, mock_client):
        """Test discover_trains handles API errors gracefully."""
        mock_client.get_all_arrivals.side_effect = Exception("API Error")

        result = await collector.discover_trains()

        assert result == []

    async def test_run_returns_summary(self, collector, mock_client):
        """Test run method returns proper summary structure."""
        mock_client.get_all_arrivals.return_value = [
            PathArrival(
                station_code="PHO",
                headsign="33rd Street",
                direction="ToNY",
                minutes_away=5,
                arrival_time=datetime.now() + timedelta(minutes=5),
                line_color="4D92FB", last_updated=None,
            ),
        ]

        with patch(
            "trackrat.collectors.path.discovery.get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.scalar = AsyncMock(return_value=None)
            mock_session.add = MagicMock()
            mock_session.flush = AsyncMock()
            mock_session.commit = AsyncMock()

            mock_get_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock GTFS service
            with patch(
                "trackrat.collectors.path.discovery.GTFSService"
            ) as mock_gtfs:
                mock_gtfs_instance = MagicMock()
                mock_gtfs_instance.get_path_route_stop_times_from_origin = AsyncMock(
                    return_value=None
                )
                mock_gtfs.return_value = mock_gtfs_instance

                result = await collector.run()

        assert isinstance(result, dict)
        assert result["data_source"] == "PATH"
        assert "stations_processed" in result
        assert "total_arrivals" in result
        assert "total_new" in result
        assert "station_results" in result

    async def test_run_closes_owned_client(self, mock_client):
        """Test run method closes client when collector owns it."""
        collector = PathDiscoveryCollector(client=mock_client)
        collector._owns_client = True
        mock_client.get_all_arrivals.return_value = []

        with patch(
            "trackrat.collectors.path.discovery.get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            await collector.run()

        mock_client.close.assert_called_once()

    async def test_run_does_not_close_external_client(self, collector, mock_client):
        """Test run method does not close externally provided client."""
        mock_client.get_all_arrivals.return_value = []

        with patch(
            "trackrat.collectors.path.discovery.get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            await collector.run()

        mock_client.close.assert_not_called()


class TestPathDiscoveryProcessArrival:
    """Tests for the _process_arrival method."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock RidePathClient."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def collector(self, mock_client):
        """Create a PathDiscoveryCollector with mock client."""
        return PathDiscoveryCollector(client=mock_client)

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.scalar = AsyncMock(return_value=None)
        session.add = MagicMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def mock_gtfs_service(self):
        """Create a mock for GTFSService that returns None (no GTFS data)."""
        with patch(
            "trackrat.collectors.path.discovery.GTFSService"
        ) as mock_class:
            mock_instance = MagicMock()
            mock_instance.get_path_route_stop_times_from_origin = AsyncMock(
                return_value=None
            )
            mock_class.return_value = mock_instance
            yield mock_instance

    @pytest.mark.usefixtures("mock_gtfs_service")
    async def test_process_arrival_creates_journey(self, collector, mock_session):
        """Test _process_arrival creates new journey for new train."""
        arrival = PathArrival(
            station_code="PHO",
            headsign="33rd Street",
            direction="ToNY",
            minutes_away=10,
            arrival_time=datetime.now() + timedelta(minutes=10),
            line_color="4D92FB", last_updated=None,
        )

        created = await collector._process_arrival(mock_session, arrival)

        assert created is True
        mock_session.add.assert_called()

    async def test_process_arrival_skips_existing_journey(
        self, collector, mock_session
    ):
        """Test _process_arrival does not create duplicate journeys."""
        existing_journey = MagicMock()
        existing_journey.last_updated_at = datetime.now()
        mock_session.scalar = AsyncMock(return_value=existing_journey)

        arrival = PathArrival(
            station_code="PHO",
            headsign="33rd Street",
            direction="ToNY",
            minutes_away=10,
            arrival_time=datetime.now() + timedelta(minutes=10),
            line_color="4D92FB", last_updated=None,
        )

        created = await collector._process_arrival(mock_session, arrival)

        assert created is False

    async def test_process_arrival_matches_existing_by_schedule(
        self, collector, mock_session
    ):
        """Test _process_arrival skips when matching existing journey by schedule."""
        # First call returns None (no exact match), second returns existing journey
        existing_journey = MagicMock()
        existing_journey.last_updated_at = datetime.now()
        mock_session.scalar = AsyncMock(side_effect=[None, existing_journey])

        arrival = PathArrival(
            station_code="PHO",
            headsign="33rd Street",
            direction="ToNY",
            minutes_away=10,
            arrival_time=datetime.now() + timedelta(minutes=10),
            line_color="4D92FB",
            last_updated=None,
        )

        created = await collector._process_arrival(mock_session, arrival)

        assert created is False

    @pytest.mark.usefixtures("mock_gtfs_service")
    async def test_process_arrival_uses_line_color_from_api(
        self, collector, mock_session
    ):
        """Test _process_arrival uses line color from API when available."""
        arrival = PathArrival(
            station_code="PHO",
            headsign="33rd Street",
            direction="ToNY",
            minutes_away=10,
            arrival_time=datetime.now() + timedelta(minutes=10),
            line_color="FF0000",  # Custom color
            last_updated=None,
        )

        await collector._process_arrival(mock_session, arrival)

        # Verify journey was created with API color
        add_call = mock_session.add.call_args_list[0]
        journey = add_call[0][0]
        assert journey.line_color == "#FF0000"

    @pytest.mark.usefixtures("mock_gtfs_service")
    async def test_process_arrival_creates_origin_stop(
        self, collector, mock_session
    ):
        """Test _process_arrival creates journey stop for origin station."""
        arrival = PathArrival(
            station_code="PHO",
            headsign="33rd Street",
            direction="ToNY",
            minutes_away=10,
            arrival_time=datetime.now() + timedelta(minutes=10),
            line_color="4D92FB", last_updated=None,
        )

        await collector._process_arrival(mock_session, arrival)

        # Should add journey AND at least one stop
        assert mock_session.add.call_count >= 2

    @pytest.mark.usefixtures("mock_gtfs_service")
    async def test_process_arrival_departing_train_creates_journey(
        self, collector, mock_session
    ):
        """Test _process_arrival creates journey for departing trains.

        When a train at PHO (Hoboken) is heading to 33rd Street,
        it's departing and should create a new journey.
        """
        arrival = PathArrival(
            station_code="PHO",
            headsign="33rd Street",
            direction="ToNY",
            minutes_away=5,
            arrival_time=datetime.now() + timedelta(minutes=5),
            line_color="4D92FB", last_updated=None,
        )

        created = await collector._process_arrival(mock_session, arrival)

        assert created is True
        mock_session.add.assert_called()
