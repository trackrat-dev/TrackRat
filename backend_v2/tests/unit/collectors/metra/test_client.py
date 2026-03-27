"""
Unit tests for MetraClient.

Tests GTFS-RT API communication, protobuf parsing, caching, and
authentication token handling.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from google.transit import gtfs_realtime_pb2

from trackrat.collectors.metra.client import (
    MetraArrival,
    MetraClient,
)


class TestMetraArrival:
    """Tests for MetraArrival model."""

    def test_creation_with_all_fields(self):
        """Test creating MetraArrival with all fields populated."""
        arrival = MetraArrival(
            station_code="CUS",
            gtfs_stop_id="CUS",
            trip_id="ME_ME2012_V1_B",
            route_id="ME",
            direction_id=1,
            headsign="Chicago Union Station",
            arrival_time=datetime(2026, 3, 25, 10, 30, tzinfo=UTC),
            departure_time=datetime(2026, 3, 25, 10, 31, tzinfo=UTC),
            delay_seconds=120,
            track=None,
        )

        assert arrival.station_code == "CUS"
        assert arrival.gtfs_stop_id == "CUS"
        assert arrival.trip_id == "ME_ME2012_V1_B"
        assert arrival.route_id == "ME"
        assert arrival.direction_id == 1
        assert arrival.headsign == "Chicago Union Station"
        assert arrival.delay_seconds == 120
        assert arrival.track is None  # Metra doesn't publish track info

    def test_creation_with_optional_fields_none(self):
        """Test creating MetraArrival with optional fields as None."""
        arrival = MetraArrival(
            station_code="AURORA",
            gtfs_stop_id="AURORA",
            trip_id="BNSF_BNSF1234_V1_A",
            route_id="BNSF",
            direction_id=0,
            headsign=None,
            arrival_time=datetime(2026, 3, 25, 10, 30, tzinfo=UTC),
            departure_time=None,
            delay_seconds=0,
            track=None,
        )

        assert arrival.headsign is None
        assert arrival.departure_time is None
        assert arrival.track is None
        assert arrival.delay_seconds == 0

    def test_station_code_matches_gtfs_stop_id(self):
        """Metra uses identity mapping: station_code == gtfs_stop_id."""
        arrival = MetraArrival(
            station_code="GENEVA",
            gtfs_stop_id="GENEVA",
            trip_id="UP-W_UPW1234_V1_A",
            route_id="UP-W",
            direction_id=0,
            headsign=None,
            arrival_time=datetime(2026, 3, 25, 10, 30, tzinfo=UTC),
            departure_time=None,
            delay_seconds=0,
            track=None,
        )
        assert arrival.station_code == arrival.gtfs_stop_id


class TestMetraClient:
    """Tests for MetraClient."""

    @pytest.fixture
    def client(self):
        """Create a MetraClient instance with a test token."""
        with patch.dict("os.environ", {"TRACKRAT_METRA_API_TOKEN": "test_token"}):
            return MetraClient(timeout=10.0)

    @pytest.fixture
    def client_no_token(self):
        """Create a MetraClient instance without an API token."""
        with patch.dict("os.environ", {}, clear=True):
            return MetraClient(timeout=10.0)

    def test_initialization_with_token(self, client):
        """Test client initializes with correct defaults when token is set."""
        assert client.timeout == 10.0
        assert client._session is None
        assert client._api_token == "test_token"
        assert client._cache is None
        assert client._cache_time is None
        assert client._cache_ttl == 30

    def test_initialization_without_token(self, client_no_token):
        """Test client initializes gracefully without API token."""
        assert client_no_token._api_token == ""

    @pytest.mark.asyncio
    async def test_get_all_arrivals_returns_empty_without_token(self, client_no_token):
        """Client should return empty list when no API token is configured."""
        result = await client_no_token.get_all_arrivals()
        assert result == []

    def test_cache_validity_when_empty(self, client):
        """Cache should be invalid when empty."""
        assert client._is_cache_valid() is False

    def test_cache_validity_when_fresh(self, client):
        """Cache should be valid when recently populated."""
        client._cache = []
        client._cache_time = datetime.now(UTC)
        assert client._is_cache_valid() is True

    def test_cache_validity_when_expired(self, client):
        """Cache should be invalid when expired."""
        client._cache = []
        client._cache_time = datetime.now(UTC) - timedelta(seconds=60)
        assert client._is_cache_valid() is False

    def test_map_stop_id_known_station(self, client):
        """Known Metra station should map correctly."""
        # Metra uses identity mapping
        assert client._map_stop_id("CUS") == "CUS"
        assert client._map_stop_id("AURORA") == "AURORA"
        assert client._map_stop_id("GENEVA") == "GENEVA"

    def test_map_stop_id_unknown_station(self, client):
        """Unknown stop_id should return None."""
        assert client._map_stop_id("NONEXISTENT_STATION") is None

    def test_get_route_info_valid_route(self, client):
        """Known routes should return (line_code, name, color) tuples."""
        route_info = client._get_route_info("BNSF")
        assert route_info is not None
        line_code, name, color = route_info
        assert line_code == "METRA-BNSF"
        assert "Burlington" in name
        assert color.startswith("#")

    def test_get_route_info_invalid_route(self, client):
        """Unknown routes should return None."""
        assert client._get_route_info("UNKNOWN") is None

    @pytest.mark.asyncio
    async def test_session_property_creates_client(self, client):
        """Accessing session property should create an httpx client."""
        session = client.session
        assert session is not None
        assert isinstance(session, httpx.AsyncClient)
        await client.close()

    @pytest.mark.asyncio
    async def test_close_clears_session(self, client):
        """Closing should clear the session."""
        _ = client.session  # Create session
        await client.close()
        assert client._session is None

    def test_clear_cache(self, client):
        """clear_cache should reset cache state."""
        client._cache = [MagicMock()]
        client._cache_time = datetime.now(UTC)
        client.clear_cache()
        assert client._cache is None
        assert client._cache_time is None

    @pytest.mark.asyncio
    async def test_get_all_arrivals_uses_cache(self, client):
        """Should return cached data when cache is valid."""
        cached_arrival = MetraArrival(
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
        client._cache = [cached_arrival]
        client._cache_time = datetime.now(UTC)

        result = await client.get_all_arrivals()
        assert len(result) == 1
        assert result[0].station_code == "CUS"

    @pytest.mark.asyncio
    async def test_get_all_arrivals_parses_protobuf(self, client):
        """Should parse GTFS-RT protobuf response correctly."""
        # Build a minimal GTFS-RT feed
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.timestamp = int(datetime.now(UTC).timestamp())

        entity = feed.entity.add()
        entity.id = "test_entity"
        tu = entity.trip_update
        tu.trip.trip_id = "ME_ME2012_V1_B"
        tu.trip.route_id = "ME"
        tu.trip.direction_id = 1

        # Add a stop time update for CUS
        stu = tu.stop_time_update.add()
        stu.stop_id = "CUS"
        now_ts = int(datetime.now(UTC).timestamp())
        stu.arrival.time = now_ts
        stu.arrival.delay = 60
        stu.departure.time = now_ts + 60

        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.content = feed.SerializeToString()
        mock_response.raise_for_status = MagicMock()

        client._session = AsyncMock()
        client._session.get = AsyncMock(return_value=mock_response)

        result = await client.get_all_arrivals()

        assert len(result) == 1
        assert result[0].station_code == "CUS"
        assert result[0].trip_id == "ME_ME2012_V1_B"
        assert result[0].route_id == "ME"
        assert result[0].direction_id == 1
        assert result[0].delay_seconds == 60

    @pytest.mark.asyncio
    async def test_get_all_arrivals_skips_unknown_stops(self, client):
        """Should skip stop_time_updates for unknown station codes."""
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.timestamp = int(datetime.now(UTC).timestamp())

        entity = feed.entity.add()
        entity.id = "test_entity"
        tu = entity.trip_update
        tu.trip.trip_id = "ME_ME2012_V1_B"
        tu.trip.route_id = "ME"
        tu.trip.direction_id = 0

        # Unknown stop
        stu = tu.stop_time_update.add()
        stu.stop_id = "DOES_NOT_EXIST"
        stu.arrival.time = int(datetime.now(UTC).timestamp())

        mock_response = MagicMock()
        mock_response.content = feed.SerializeToString()
        mock_response.raise_for_status = MagicMock()

        client._session = AsyncMock()
        client._session.get = AsyncMock(return_value=mock_response)

        result = await client.get_all_arrivals()
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_all_arrivals_handles_departure_only_stops(self, client):
        """Stops with only departure time (no arrival) should use departure as arrival."""
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.timestamp = int(datetime.now(UTC).timestamp())

        entity = feed.entity.add()
        entity.id = "test_entity"
        tu = entity.trip_update
        tu.trip.trip_id = "BNSF_BNSF1200_V1_A"
        tu.trip.route_id = "BNSF"
        tu.trip.direction_id = 0

        # Origin stop: departure only, no arrival
        stu = tu.stop_time_update.add()
        stu.stop_id = "CUS"
        dep_ts = int(datetime.now(UTC).timestamp())
        stu.departure.time = dep_ts

        mock_response = MagicMock()
        mock_response.content = feed.SerializeToString()
        mock_response.raise_for_status = MagicMock()

        client._session = AsyncMock()
        client._session.get = AsyncMock(return_value=mock_response)

        result = await client.get_all_arrivals()
        assert len(result) == 1
        # arrival_time should equal departure_time when arrival is missing
        assert result[0].arrival_time == result[0].departure_time

    @pytest.mark.asyncio
    async def test_get_all_arrivals_http_error_returns_cache(self, client):
        """HTTP errors should return cached data if available."""
        cached_arrival = MetraArrival(
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
        client._cache = [cached_arrival]
        client._cache_time = datetime.now(UTC) - timedelta(seconds=60)  # Expired

        client._session = AsyncMock()
        client._session.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "500", request=MagicMock(), response=MagicMock()
            )
        )

        result = await client.get_all_arrivals()
        assert len(result) == 1  # Returns stale cache

    @pytest.mark.asyncio
    async def test_get_station_arrivals_filters_by_station(self, client):
        """get_station_arrivals should filter by station code."""
        client._cache = [
            MetraArrival(
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
            ),
            MetraArrival(
                station_code="AURORA",
                gtfs_stop_id="AURORA",
                trip_id="BNSF_BNSF1200_V1_A",
                route_id="BNSF",
                direction_id=0,
                headsign=None,
                arrival_time=datetime(2026, 3, 25, 11, 0, tzinfo=UTC),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
        ]
        client._cache_time = datetime.now(UTC)

        result = await client.get_station_arrivals("CUS")
        assert len(result) == 1
        assert result[0].station_code == "CUS"

    @pytest.mark.asyncio
    async def test_get_trip_stops_filters_and_sorts(self, client):
        """get_trip_stops should filter by trip_id and sort by arrival time."""
        client._cache = [
            MetraArrival(
                station_code="AURORA",
                gtfs_stop_id="AURORA",
                trip_id="BNSF_BNSF1200_V1_A",
                route_id="BNSF",
                direction_id=0,
                headsign=None,
                arrival_time=datetime(2026, 3, 25, 10, 0, tzinfo=UTC),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
            MetraArrival(
                station_code="NAPERVILLE",
                gtfs_stop_id="NAPERVILLE",
                trip_id="BNSF_BNSF1200_V1_A",
                route_id="BNSF",
                direction_id=0,
                headsign=None,
                arrival_time=datetime(2026, 3, 25, 10, 20, tzinfo=UTC),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
            MetraArrival(
                station_code="CUS",
                gtfs_stop_id="CUS",
                trip_id="BNSF_BNSF1200_V1_A",
                route_id="BNSF",
                direction_id=0,
                headsign=None,
                arrival_time=datetime(2026, 3, 25, 10, 50, tzinfo=UTC),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
            MetraArrival(
                station_code="CUS",
                gtfs_stop_id="CUS",
                trip_id="ME_ME2012_V1_B",
                route_id="ME",
                direction_id=1,
                headsign=None,
                arrival_time=datetime(2026, 3, 25, 11, 0, tzinfo=UTC),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
        ]
        client._cache_time = datetime.now(UTC)

        result = await client.get_trip_stops("BNSF_BNSF1200_V1_A")
        assert len(result) == 3
        assert result[0].station_code == "AURORA"
        assert result[1].station_code == "NAPERVILLE"
        assert result[2].station_code == "CUS"

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager opens and closes properly."""
        with patch.dict("os.environ", {"TRACKRAT_METRA_API_TOKEN": "test"}):
            async with MetraClient() as client:
                assert client is not None
