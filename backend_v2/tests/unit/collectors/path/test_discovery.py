"""
Unit tests for PathDiscoveryCollector.

Tests train discovery logic, station polling, and journey creation.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trackrat.collectors.path.client import PathStopTime
from trackrat.collectors.path.discovery import (
    PathDiscoveryCollector,
    _generate_path_train_id,
)


class TestGeneratePathTrainId:
    """Tests for the train ID generation function."""

    def test_generates_correct_format(self):
        """Test train ID has correct format: PATH_<route>_<trip_prefix>."""
        result = _generate_path_train_id("859", "abc123xyz456")

        assert result.startswith("PATH_859_")
        assert "abc123xyz456" in result

    def test_truncates_long_trip_ids(self):
        """Test long trip IDs are truncated to 12 characters."""
        long_trip_id = "abcdefghijklmnopqrstuvwxyz"
        result = _generate_path_train_id("860", long_trip_id)

        assert result == "PATH_860_abcdefghijkl"

    def test_short_trip_ids_unchanged(self):
        """Test short trip IDs are not modified."""
        result = _generate_path_train_id("861", "short")

        assert result == "PATH_861_short"

    def test_different_routes_produce_different_ids(self):
        """Test same trip ID on different routes produces different train IDs."""
        id1 = _generate_path_train_id("859", "trip123")
        id2 = _generate_path_train_id("860", "trip123")

        assert id1 != id2
        assert id1 == "PATH_859_trip123"
        assert id2 == "PATH_860_trip123"


class TestPathDiscoveryCollector:
    """Tests for PathDiscoveryCollector."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock PathClient."""
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
            "trackrat.collectors.path.discovery.PathClient"
        ) as MockClient:
            collector = PathDiscoveryCollector()
            MockClient.assert_called_once()
            assert collector._owns_client is True

    async def test_discover_trains_returns_train_ids(self, collector, mock_client):
        """Test discover_trains returns list of train IDs from arrivals."""
        mock_client.get_station_arrivals.return_value = [
            PathStopTime(
                trip_id="trip_1",
                route_id="859",
                departure_time=datetime.now(),
                headsign="33rd St",
            ),
            PathStopTime(
                trip_id="trip_2",
                route_id="860",
                departure_time=datetime.now(),
                headsign="WTC",
            ),
        ]

        result = await collector.discover_trains()

        assert isinstance(result, list)
        # Should discover trains from the mock arrivals
        assert len(result) > 0

    async def test_discover_trains_deduplicates(self, collector, mock_client):
        """Test discover_trains removes duplicate train IDs."""
        # Same trip appearing at multiple stations
        mock_client.get_station_arrivals.return_value = [
            PathStopTime(
                trip_id="same_trip",
                route_id="859",
                departure_time=datetime.now(),
            ),
        ]

        result = await collector.discover_trains()

        # Should only have unique IDs (all stations return same trip)
        train_ids = set(result)
        assert len(train_ids) == len(result)

    async def test_discover_trains_handles_station_errors(
        self, collector, mock_client
    ):
        """Test discover_trains continues after station errors."""
        # First station succeeds, second fails
        call_count = 0

        async def mock_arrivals(stop_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [
                    PathStopTime(
                        trip_id="trip_1",
                        route_id="859",
                        departure_time=datetime.now(),
                    )
                ]
            else:
                raise Exception("Station error")

        mock_client.get_station_arrivals = mock_arrivals

        result = await collector.discover_trains()

        # Should still return trains from successful stations
        assert len(result) >= 1

    async def test_discover_trains_empty_on_no_arrivals(
        self, collector, mock_client
    ):
        """Test discover_trains returns empty list when no arrivals."""
        mock_client.get_station_arrivals.return_value = []

        result = await collector.discover_trains()

        assert result == []

    async def test_run_returns_summary(self, collector, mock_client):
        """Test run method returns proper summary structure."""
        mock_client.get_station_arrivals.return_value = [
            PathStopTime(
                trip_id="trip_1",
                route_id="859",
                departure_time=datetime.now() + timedelta(minutes=5),
                headsign="33rd St",
            ),
        ]

        # Mock the database session
        with patch(
            "trackrat.collectors.path.discovery.get_session"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.scalar = AsyncMock(return_value=None)  # No existing journey
            mock_session.add = MagicMock()
            mock_session.flush = AsyncMock()
            mock_session.commit = AsyncMock()

            mock_get_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

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
        mock_client.get_station_arrivals.return_value = []

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
        mock_client.get_station_arrivals.return_value = []

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
        """Create a mock PathClient."""
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

    async def test_process_arrival_creates_journey(
        self, collector, mock_session
    ):
        """Test _process_arrival creates new journey for new train."""
        arrival = PathStopTime(
            trip_id="new_trip",
            route_id="859",
            departure_time=datetime.now() + timedelta(minutes=10),
            headsign="33rd Street",
        )

        created = await collector._process_arrival(
            mock_session, "PHO", arrival
        )

        assert created is True
        mock_session.add.assert_called()  # Journey was added

    async def test_process_arrival_skips_existing_journey(
        self, collector, mock_session
    ):
        """Test _process_arrival does not create duplicate journeys."""
        # Mock existing journey
        existing_journey = MagicMock()
        existing_journey.last_updated_at = datetime.now()
        mock_session.scalar = AsyncMock(return_value=existing_journey)

        arrival = PathStopTime(
            trip_id="existing_trip",
            route_id="859",
            departure_time=datetime.now() + timedelta(minutes=10),
            headsign="33rd Street",
        )

        created = await collector._process_arrival(
            mock_session, "PHO", arrival
        )

        assert created is False

    async def test_process_arrival_skips_no_time(self, collector, mock_session):
        """Test _process_arrival skips arrivals without departure time."""
        arrival = PathStopTime(
            trip_id="no_time_trip",
            route_id="859",
            departure_time=None,
            arrival_time=None,
        )

        created = await collector._process_arrival(
            mock_session, "PHO", arrival
        )

        assert created is False
        mock_session.add.assert_not_called()

    async def test_process_arrival_uses_route_info(
        self, collector, mock_session
    ):
        """Test _process_arrival uses route info for line code and color."""
        arrival = PathStopTime(
            trip_id="route_test_trip",
            route_id="860",  # HOB-WTC route
            departure_time=datetime.now() + timedelta(minutes=10),
            headsign="World Trade Center",
        )

        await collector._process_arrival(mock_session, "PHO", arrival)

        # Verify journey was created with correct route info
        add_call = mock_session.add.call_args_list[0]
        journey = add_call[0][0]
        assert journey.line_code == "HOB-WTC"
        assert journey.line_color == "#65c100"

    async def test_process_arrival_handles_unknown_route(
        self, collector, mock_session
    ):
        """Test _process_arrival handles unknown route gracefully."""
        arrival = PathStopTime(
            trip_id="unknown_route_trip",
            route_id="99999",  # Unknown route
            departure_time=datetime.now() + timedelta(minutes=10),
            headsign="Mystery Destination",
        )

        created = await collector._process_arrival(
            mock_session, "PHO", arrival
        )

        assert created is True
        # Should still create journey with fallback line code
        add_call = mock_session.add.call_args_list[0]
        journey = add_call[0][0]
        assert journey.line_code == "99999"  # Falls back to route_id[:6]

    async def test_process_arrival_creates_journey_stop(
        self, collector, mock_session
    ):
        """Test _process_arrival creates journey stop for discovery station."""
        arrival = PathStopTime(
            trip_id="stop_test_trip",
            route_id="859",
            departure_time=datetime.now() + timedelta(minutes=10),
            headsign="33rd Street",
        )

        await collector._process_arrival(mock_session, "PJS", arrival)

        # Should add journey AND journey stop
        assert mock_session.add.call_count == 2
        # Second add should be the JourneyStop
        stop_call = mock_session.add.call_args_list[1]
        stop = stop_call[0][0]
        assert stop.station_code == "PJS"
