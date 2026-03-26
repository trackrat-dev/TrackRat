"""
Unit tests for MBTAClient.

Tests GTFS-RT API communication, protobuf parsing, caching, and CR filtering.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from google.transit import gtfs_realtime_pb2

from trackrat.collectors.mbta.client import (
    MBTAClient,
    MbtaArrival,
)


class TestMbtaArrival:
    """Tests for MbtaArrival model."""

    def test_creation_with_all_fields(self):
        """Test creating MbtaArrival with all fields."""
        arrival = MbtaArrival(
            station_code="BOS",
            gtfs_stop_id="NEC-2287",
            trip_id="Base-772221-5208",
            route_id="CR-Providence",
            direction_id=0,
            headsign="Providence",
            arrival_time=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
            departure_time=datetime(2024, 1, 15, 10, 31, tzinfo=timezone.utc),
            delay_seconds=60,
            track=None,
        )

        assert arrival.station_code == "BOS"
        assert arrival.gtfs_stop_id == "NEC-2287"
        assert arrival.trip_id == "Base-772221-5208"
        assert arrival.route_id == "CR-Providence"
        assert arrival.direction_id == 0
        assert arrival.headsign == "Providence"
        assert arrival.delay_seconds == 60
        assert arrival.track is None

    def test_creation_with_optional_fields_none(self):
        """Test creating MbtaArrival with optional fields as None."""
        arrival = MbtaArrival(
            station_code="BOS",
            gtfs_stop_id="NEC-2287",
            trip_id="Base-772221-5208",
            route_id="CR-Providence",
            direction_id=0,
            headsign=None,
            arrival_time=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
            departure_time=None,
            delay_seconds=0,
            track=None,
        )

        assert arrival.headsign is None
        assert arrival.departure_time is None
        assert arrival.track is None
        assert arrival.delay_seconds == 0


class TestMBTAClient:
    """Tests for MBTAClient."""

    @pytest.fixture
    def client(self):
        """Create a MBTAClient instance for testing."""
        return MBTAClient(timeout=10.0)

    def test_initialization(self, client):
        """Test client initializes with correct defaults."""
        assert client.timeout == 10.0
        assert client._session is None
        assert client._cache is None
        assert client._cache_time is None
        assert client._cache_ttl == 30

    def test_session_creation(self, client):
        """Test session is created lazily."""
        assert client._session is None
        session = client.session
        assert session is not None
        assert isinstance(session, httpx.AsyncClient)

    def test_session_reuse(self, client):
        """Test same session is returned on subsequent access."""
        session1 = client.session
        session2 = client.session
        assert session1 is session2

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test closing the client."""
        _ = client.session  # Create session
        await client.close()
        assert client._session is None

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test async context manager protocol."""
        async with MBTAClient(timeout=5.0) as client:
            assert client is not None
        assert client._session is None

    def test_cache_validation_empty(self, client):
        """Test cache is invalid when empty."""
        assert not client._is_cache_valid()

    def test_cache_validation_valid(self, client):
        """Test cache is valid within TTL."""
        client._cache = []
        client._cache_time = datetime.now(timezone.utc)
        assert client._is_cache_valid()

    def test_cache_validation_expired(self, client):
        """Test cache is invalid when expired."""
        client._cache = []
        client._cache_time = datetime.now(timezone.utc) - timedelta(seconds=60)
        assert not client._is_cache_valid()

    def test_clear_cache(self, client):
        """Test clearing the cache."""
        client._cache = []
        client._cache_time = datetime.now(timezone.utc)
        client.clear_cache()
        assert client._cache is None
        assert client._cache_time is None

    @pytest.mark.asyncio
    async def test_get_all_arrivals_returns_cached(self, client):
        """Test get_all_arrivals returns cached data when valid."""
        cached_arrival = MbtaArrival(
            station_code="BOS",
            gtfs_stop_id="NEC-2287",
            trip_id="trip_1",
            route_id="CR-Providence",
            direction_id=0,
            headsign=None,
            arrival_time=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
            departure_time=None,
            delay_seconds=0,
            track=None,
        )
        client._cache = [cached_arrival]
        client._cache_time = datetime.now(timezone.utc)

        arrivals = await client.get_all_arrivals()
        assert len(arrivals) == 1
        assert arrivals[0].station_code == "BOS"

    @pytest.mark.asyncio
    async def test_get_station_arrivals(self, client):
        """Test filtering arrivals by station."""
        arrivals = [
            MbtaArrival(
                station_code="BOS",
                gtfs_stop_id="NEC-2287",
                trip_id="trip_1",
                route_id="CR-Providence",
                direction_id=0,
                headsign=None,
                arrival_time=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
            MbtaArrival(
                station_code="BNST",
                gtfs_stop_id="BNT-0000",
                trip_id="trip_2",
                route_id="CR-Lowell",
                direction_id=0,
                headsign=None,
                arrival_time=datetime(2024, 1, 15, 10, 35, tzinfo=timezone.utc),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
        ]
        client._cache = arrivals
        client._cache_time = datetime.now(timezone.utc)

        bos_arrivals = await client.get_station_arrivals("BOS")
        assert len(bos_arrivals) == 1
        assert bos_arrivals[0].station_code == "BOS"

    @pytest.mark.asyncio
    async def test_get_trip_stops_sorted(self, client):
        """Test trip stops are returned sorted by arrival time."""
        later = datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc)
        earlier = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)

        arrivals = [
            MbtaArrival(
                station_code="PVD",
                gtfs_stop_id="NEC-1851-03",
                trip_id="trip_1",
                route_id="CR-Providence",
                direction_id=0,
                headsign=None,
                arrival_time=later,
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
            MbtaArrival(
                station_code="BOS",
                gtfs_stop_id="NEC-2287",
                trip_id="trip_1",
                route_id="CR-Providence",
                direction_id=0,
                headsign=None,
                arrival_time=earlier,
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
        ]
        client._cache = arrivals
        client._cache_time = datetime.now(timezone.utc)

        stops = await client.get_trip_stops("trip_1")
        assert len(stops) == 2
        assert stops[0].station_code == "BOS"
        assert stops[1].station_code == "PVD"

    def test_map_stop_id_known(self, client):
        """Test mapping a known GTFS stop_id to internal code."""
        result = client._map_stop_id("NEC-2287")
        assert result == "BOS"

    def test_map_stop_id_unknown(self, client):
        """Test mapping an unknown GTFS stop_id returns None."""
        result = client._map_stop_id("UNKNOWN-STOP")
        assert result is None

    def test_get_route_info_known(self, client):
        """Test getting route info for a known route."""
        result = client._get_route_info("CR-Providence")
        assert result is not None
        line_code, name, color = result
        assert line_code == "MBTA-PV"
        assert "Providence" in name

    def test_get_route_info_unknown(self, client):
        """Test getting route info for an unknown route."""
        result = client._get_route_info("CR-Unknown")
        assert result is None

    def test_is_commuter_rail(self):
        """Test CR route identification."""
        assert MBTAClient._is_commuter_rail("CR-Providence") is True
        assert MBTAClient._is_commuter_rail("CR-Worcester") is True
        assert MBTAClient._is_commuter_rail("CapeFlyer") is True
        assert MBTAClient._is_commuter_rail("Red") is False
        assert MBTAClient._is_commuter_rail("Orange") is False
        assert MBTAClient._is_commuter_rail("Green-B") is False
        assert MBTAClient._is_commuter_rail("1") is False

    @pytest.mark.asyncio
    async def test_get_all_arrivals_http_error(self, client):
        """Test HTTP error returns empty list."""
        mock_session = AsyncMock(spec=httpx.AsyncClient)
        mock_session.get.side_effect = httpx.HTTPError("Connection failed")
        client._session = mock_session

        arrivals = await client.get_all_arrivals()
        assert arrivals == []

    @pytest.mark.asyncio
    async def test_get_all_arrivals_http_error_returns_stale_cache(self, client):
        """Test HTTP error returns stale cached data if available."""
        cached = [
            MbtaArrival(
                station_code="BOS",
                gtfs_stop_id="NEC-2287",
                trip_id="trip_1",
                route_id="CR-Providence",
                direction_id=0,
                headsign=None,
                arrival_time=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
        ]
        client._cache = cached
        client._cache_time = datetime.now(timezone.utc) - timedelta(seconds=120)

        mock_session = AsyncMock(spec=httpx.AsyncClient)
        mock_session.get.side_effect = httpx.HTTPError("Connection failed")
        client._session = mock_session

        arrivals = await client.get_all_arrivals()
        assert len(arrivals) == 1
        assert arrivals[0].station_code == "BOS"

    @pytest.mark.asyncio
    async def test_get_all_arrivals_parses_protobuf(self, client):
        """Test parsing a real GTFS-RT protobuf with CR and non-CR trips."""
        # Build a GTFS-RT feed with one CR trip and one subway trip
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.timestamp = int(datetime.now(timezone.utc).timestamp())

        # CR trip (should be processed)
        entity1 = feed.entity.add()
        entity1.id = "cr_trip_1"
        trip1 = entity1.trip_update.trip
        trip1.trip_id = "Base-772221-5208"
        trip1.route_id = "CR-Providence"
        trip1.direction_id = 0

        stu1 = entity1.trip_update.stop_time_update.add()
        stu1.stop_id = "NEC-2287"  # South Station
        stu1.arrival.time = int(
            datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc).timestamp()
        )
        stu1.arrival.delay = 60
        stu1.departure.time = int(
            datetime(2024, 1, 15, 10, 31, tzinfo=timezone.utc).timestamp()
        )

        # Subway trip (should be filtered out)
        entity2 = feed.entity.add()
        entity2.id = "subway_trip_1"
        trip2 = entity2.trip_update.trip
        trip2.trip_id = "subway_123"
        trip2.route_id = "Red"
        trip2.direction_id = 0

        stu2 = entity2.trip_update.stop_time_update.add()
        stu2.stop_id = "70061"
        stu2.arrival.time = int(
            datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc).timestamp()
        )

        # Mock HTTP response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.content = feed.SerializeToString()
        mock_response.raise_for_status = MagicMock()

        mock_session = AsyncMock(spec=httpx.AsyncClient)
        mock_session.get.return_value = mock_response
        client._session = mock_session

        arrivals = await client.get_all_arrivals()

        # Should only have the CR arrival, not the subway one
        assert len(arrivals) == 1
        assert arrivals[0].station_code == "BOS"
        assert arrivals[0].trip_id == "Base-772221-5208"
        assert arrivals[0].route_id == "CR-Providence"
        assert arrivals[0].delay_seconds == 60
        # MBTA doesn't use MTA track extensions
        assert arrivals[0].track is None

    @pytest.mark.asyncio
    async def test_get_all_arrivals_skips_unmapped_stops(self, client):
        """Test that stops with unknown stop_ids are skipped."""
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.timestamp = int(datetime.now(timezone.utc).timestamp())

        entity = feed.entity.add()
        entity.id = "trip_1"
        trip = entity.trip_update.trip
        trip.trip_id = "Base-772221-5208"
        trip.route_id = "CR-Providence"
        trip.direction_id = 0

        # Known stop
        stu1 = entity.trip_update.stop_time_update.add()
        stu1.stop_id = "NEC-2287"  # South Station -> BOS
        stu1.arrival.time = int(
            datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc).timestamp()
        )

        # Unknown stop
        stu2 = entity.trip_update.stop_time_update.add()
        stu2.stop_id = "UNKNOWN-STOP-99"
        stu2.arrival.time = int(
            datetime(2024, 1, 15, 10, 45, tzinfo=timezone.utc).timestamp()
        )

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.content = feed.SerializeToString()
        mock_response.raise_for_status = MagicMock()

        mock_session = AsyncMock(spec=httpx.AsyncClient)
        mock_session.get.return_value = mock_response
        client._session = mock_session

        arrivals = await client.get_all_arrivals()
        assert len(arrivals) == 1
        assert arrivals[0].station_code == "BOS"

    @pytest.mark.asyncio
    async def test_get_all_arrivals_departure_fallback(self, client):
        """Test that departure_time is used when arrival_time is missing."""
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.timestamp = int(datetime.now(timezone.utc).timestamp())

        entity = feed.entity.add()
        entity.id = "trip_1"
        trip = entity.trip_update.trip
        trip.trip_id = "Base-772221-5208"
        trip.route_id = "CR-Worcester"
        trip.direction_id = 0

        stu = entity.trip_update.stop_time_update.add()
        stu.stop_id = "NEC-2287"  # South Station
        # No arrival time, only departure
        stu.departure.time = int(
            datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc).timestamp()
        )

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.content = feed.SerializeToString()
        mock_response.raise_for_status = MagicMock()

        mock_session = AsyncMock(spec=httpx.AsyncClient)
        mock_session.get.return_value = mock_response
        client._session = mock_session

        arrivals = await client.get_all_arrivals()
        assert len(arrivals) == 1
        # arrival_time should be set from departure_time
        assert arrivals[0].arrival_time == datetime(
            2024, 1, 15, 10, 30, tzinfo=timezone.utc
        )
