"""
Unit tests for MNRClient.

Tests GTFS-RT API communication, protobuf parsing, and caching.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from google.transit import gtfs_realtime_pb2

from trackrat.collectors.mnr.client import (
    MNRClient,
    MnrArrival,
    MNR_GTFS_RT_FEED_URL,
)


class TestMnrArrival:
    """Tests for MnrArrival model."""

    def test_creation_with_all_fields(self):
        """Test creating MnrArrival with all fields."""
        arrival = MnrArrival(
            station_code="GCT",
            gtfs_stop_id="1",
            trip_id="trip_123",
            route_id="1",
            direction_id=0,
            headsign="Poughkeepsie",
            arrival_time=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
            departure_time=datetime(2024, 1, 15, 10, 31, tzinfo=timezone.utc),
            delay_seconds=60,
            track="12",
        )

        assert arrival.station_code == "GCT"
        assert arrival.gtfs_stop_id == "1"
        assert arrival.trip_id == "trip_123"
        assert arrival.route_id == "1"
        assert arrival.direction_id == 0
        assert arrival.headsign == "Poughkeepsie"
        assert arrival.delay_seconds == 60
        assert arrival.track == "12"

    def test_creation_with_optional_fields_none(self):
        """Test creating MnrArrival with optional fields as None."""
        arrival = MnrArrival(
            station_code="GCT",
            gtfs_stop_id="1",
            trip_id="trip_123",
            route_id="1",
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


class TestMNRClient:
    """Tests for MNRClient."""

    @pytest.fixture
    def client(self):
        """Create a MNRClient instance for testing."""
        return MNRClient(timeout=10.0)

    def test_initialization(self, client):
        """Test client initializes with correct defaults."""
        assert client.timeout == 10.0
        assert client._session is None
        assert client._cache is None
        assert client._cache_time is None
        assert client._cache_ttl == 30

    def test_session_property_creates_session(self, client):
        """Test session property lazily creates httpx client."""
        assert client._session is None
        session = client.session
        assert session is not None
        assert isinstance(session, httpx.AsyncClient)

    def test_session_property_reuses_session(self, client):
        """Test session property returns same session on repeated calls."""
        session1 = client.session
        session2 = client.session
        assert session1 is session2

    @pytest.mark.asyncio
    async def test_close_clears_session(self, client):
        """Test close method clears the session."""
        _ = client.session  # Create session
        assert client._session is not None
        await client.close()
        assert client._session is None

    @pytest.mark.asyncio
    async def test_context_manager(self, client):
        """Test async context manager entry and exit."""
        async with client as c:
            assert c is client
        assert client._session is None

    def test_cache_validation_empty(self, client):
        """Test cache is invalid when empty."""
        assert not client._is_cache_valid()

    def test_cache_validation_valid(self, client):
        """Test cache is valid when recently populated."""
        client._cache = [
            MnrArrival(
                station_code="GCT",
                gtfs_stop_id="1",
                trip_id="t1",
                route_id="1",
                direction_id=0,
                headsign=None,
                arrival_time=datetime.now(timezone.utc),
                departure_time=None,
                delay_seconds=0,
                track=None,
            )
        ]
        client._cache_time = datetime.now(timezone.utc)
        assert client._is_cache_valid()

    def test_cache_validation_expired(self, client):
        """Test cache is invalid when expired."""
        client._cache = [
            MnrArrival(
                station_code="GCT",
                gtfs_stop_id="1",
                trip_id="t1",
                route_id="1",
                direction_id=0,
                headsign=None,
                arrival_time=datetime.now(timezone.utc),
                departure_time=None,
                delay_seconds=0,
                track=None,
            )
        ]
        client._cache_time = datetime.now(timezone.utc) - timedelta(seconds=60)
        assert not client._is_cache_valid()

    def test_clear_cache(self, client):
        """Test clear_cache empties all cache data."""
        client._cache = [
            MnrArrival(
                station_code="GCT",
                gtfs_stop_id="1",
                trip_id="t1",
                route_id="1",
                direction_id=0,
                headsign=None,
                arrival_time=datetime.now(timezone.utc),
                departure_time=None,
                delay_seconds=0,
                track=None,
            )
        ]
        client._cache_time = datetime.now(timezone.utc)

        client.clear_cache()

        assert client._cache is None
        assert client._cache_time is None

    @pytest.mark.asyncio
    async def test_get_all_arrivals_returns_cached(self, client):
        """Test get_all_arrivals returns cached data when valid."""
        expected = [
            MnrArrival(
                station_code="GCT",
                gtfs_stop_id="1",
                trip_id="t1",
                route_id="1",
                direction_id=0,
                headsign=None,
                arrival_time=datetime.now(timezone.utc),
                departure_time=None,
                delay_seconds=0,
                track=None,
            )
        ]
        client._cache = expected
        client._cache_time = datetime.now(timezone.utc)

        result = await client.get_all_arrivals()

        assert result == expected

    @pytest.mark.asyncio
    async def test_get_station_arrivals_filters_by_station(self, client):
        """Test get_station_arrivals filters arrivals by station code."""
        client._cache = [
            MnrArrival(
                station_code="GCT",
                gtfs_stop_id="1",
                trip_id="t1",
                route_id="1",
                direction_id=0,
                headsign=None,
                arrival_time=datetime.now(timezone.utc),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
            MnrArrival(
                station_code="M125",
                gtfs_stop_id="4",
                trip_id="t2",
                route_id="1",
                direction_id=1,
                headsign=None,
                arrival_time=datetime.now(timezone.utc),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
        ]
        client._cache_time = datetime.now(timezone.utc)

        result = await client.get_station_arrivals("GCT")

        assert len(result) == 1
        assert result[0].station_code == "GCT"

    @pytest.mark.asyncio
    async def test_get_trip_stops_filters_by_trip(self, client):
        """Test get_trip_stops filters arrivals by trip_id and sorts by time."""
        now = datetime.now(timezone.utc)
        client._cache = [
            MnrArrival(
                station_code="GCT",
                gtfs_stop_id="1",
                trip_id="trip_123",
                route_id="1",
                direction_id=0,
                headsign=None,
                arrival_time=now,
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
            MnrArrival(
                station_code="M125",
                gtfs_stop_id="4",
                trip_id="trip_123",
                route_id="1",
                direction_id=0,
                headsign=None,
                arrival_time=now + timedelta(minutes=30),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
            MnrArrival(
                station_code="MYON",
                gtfs_stop_id="18",
                trip_id="trip_other",
                route_id="1",
                direction_id=0,
                headsign=None,
                arrival_time=now,
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
        ]
        client._cache_time = datetime.now(timezone.utc)

        result = await client.get_trip_stops("trip_123")

        assert len(result) == 2
        assert result[0].station_code == "GCT"
        assert result[1].station_code == "M125"
        # Verify sorted by arrival time
        assert result[0].arrival_time < result[1].arrival_time

    @pytest.mark.asyncio
    async def test_get_all_arrivals_handles_http_error(self, client):
        """Test get_all_arrivals returns cached/empty list on HTTP error."""
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))
        client._session = mock_session
        client._cache = None

        result = await client.get_all_arrivals()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_arrivals_returns_stale_cache_on_error(self, client):
        """Test get_all_arrivals returns stale cache on HTTP error."""
        stale_data = [
            MnrArrival(
                station_code="GCT",
                gtfs_stop_id="1",
                trip_id="t1",
                route_id="1",
                direction_id=0,
                headsign=None,
                arrival_time=datetime.now(timezone.utc),
                departure_time=None,
                delay_seconds=0,
                track=None,
            )
        ]
        client._cache = stale_data
        client._cache_time = datetime.now(timezone.utc) - timedelta(seconds=120)

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))
        client._session = mock_session

        result = await client.get_all_arrivals()

        # Should return stale cache
        assert result == stale_data

    def test_map_stop_id_valid(self, client):
        """Test _map_stop_id returns correct internal code for known stop."""
        # Grand Central Terminal should map to GCT
        result = client._map_stop_id("1")
        assert result == "GCT"

    def test_map_stop_id_unknown(self, client):
        """Test _map_stop_id returns None for unknown stop."""
        result = client._map_stop_id("unknown_stop_id")
        assert result is None

    def test_get_route_info_valid(self, client):
        """Test _get_route_info returns correct info for known route."""
        # Route 1 is Hudson Line
        result = client._get_route_info("1")
        assert result is not None
        assert result[0] == "MNR-HUD"  # line_code
        assert result[1] == "Hudson Line"  # name

    def test_get_route_info_unknown(self, client):
        """Test _get_route_info returns None for unknown route."""
        result = client._get_route_info("999")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_arrivals_parses_track_from_mta_extension(self, client):
        """Test that track is extracted from MTA Railroad extension (field 1005)."""
        now_ts = int(datetime.now(timezone.utc).timestamp()) + 3600

        # Build a GTFS-RT StopTimeUpdate with MTA extension containing track "42"
        stu = gtfs_realtime_pb2.TripUpdate.StopTimeUpdate()
        stu.stop_id = "1"  # Grand Central Terminal
        stu.arrival.time = now_ts
        stu.arrival.delay = 0
        stu_bytes = stu.SerializeToString()

        # MTA Railroad extension: field 1005 with sub-message field 1 = "42"
        track_str = b"42"
        sub_msg = b"\x0a" + bytes([len(track_str)]) + track_str
        ext_bytes = b"\xea\x3e" + bytes([len(sub_msg)]) + sub_msg

        # Re-parse STU with extension bytes appended (preserved as unknown fields)
        stu_with_ext = gtfs_realtime_pb2.TripUpdate.StopTimeUpdate()
        stu_with_ext.ParseFromString(stu_bytes + ext_bytes)

        # Build complete feed with this STU
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.timestamp = int(datetime.now(timezone.utc).timestamp())

        entity = feed.entity.add()
        entity.id = "1"
        trip = entity.trip_update.trip
        trip.trip_id = "test_trip_1"
        trip.route_id = "1"
        trip.direction_id = 0

        new_stu = entity.trip_update.stop_time_update.add()
        new_stu.ParseFromString(stu_with_ext.SerializeToString())

        feed_bytes = feed.SerializeToString()

        # Mock HTTP response to return our constructed feed
        mock_response = MagicMock()
        mock_response.content = feed_bytes
        mock_response.raise_for_status = MagicMock()

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        result = await client.get_all_arrivals()

        assert len(result) == 1
        assert result[0].station_code == "GCT"
        assert result[0].trip_id == "test_trip_1"
        assert (
            result[0].track == "42"
        ), f"Expected track '42' from MTA extension, got '{result[0].track}'"

    @pytest.mark.asyncio
    async def test_get_all_arrivals_handles_missing_extension(self, client):
        """Test that track is None when MTA extension is absent."""
        now_ts = int(datetime.now(timezone.utc).timestamp()) + 3600

        # Build a standard GTFS-RT feed with no MTA extension
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.timestamp = int(datetime.now(timezone.utc).timestamp())

        entity = feed.entity.add()
        entity.id = "1"
        trip = entity.trip_update.trip
        trip.trip_id = "test_trip_2"
        trip.route_id = "1"
        trip.direction_id = 0

        stu = entity.trip_update.stop_time_update.add()
        stu.stop_id = "1"  # Grand Central Terminal
        stu.arrival.time = now_ts
        stu.arrival.delay = 0

        feed_bytes = feed.SerializeToString()

        mock_response = MagicMock()
        mock_response.content = feed_bytes
        mock_response.raise_for_status = MagicMock()

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        result = await client.get_all_arrivals()

        assert len(result) == 1
        assert result[0].track is None
