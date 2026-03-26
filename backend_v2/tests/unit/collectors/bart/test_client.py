"""
Unit tests for BARTClient.

Tests GTFS-RT API communication, protobuf parsing, and caching.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from google.transit import gtfs_realtime_pb2

from trackrat.collectors.bart.client import (
    BARTClient,
    BartArrival,
)


class TestBartArrival:
    """Tests for BartArrival model."""

    def test_creation_with_all_fields(self):
        """Test creating BartArrival with all fields."""
        arrival = BartArrival(
            station_code="BART_EMBR",
            gtfs_stop_id="M16-1",
            trip_id="1842090",
            route_id="1",
            direction_id=0,
            arrival_time=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
            departure_time=datetime(2024, 1, 15, 10, 31, tzinfo=timezone.utc),
            delay_seconds=60,
            track=None,
        )

        assert arrival.station_code == "BART_EMBR"
        assert arrival.gtfs_stop_id == "M16-1"
        assert arrival.trip_id == "1842090"
        assert arrival.route_id == "1"
        assert arrival.direction_id == 0
        assert arrival.delay_seconds == 60
        assert arrival.track is None  # BART always None

    def test_creation_with_optional_fields_none(self):
        """Test creating BartArrival with optional fields as None."""
        arrival = BartArrival(
            station_code="BART_MCAR",
            gtfs_stop_id="K30-2",
            trip_id="1842091",
            route_id="7",
            direction_id=1,
            arrival_time=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
            departure_time=None,
            delay_seconds=0,
            track=None,
        )

        assert arrival.departure_time is None
        assert arrival.delay_seconds == 0
        assert arrival.track is None


class TestBARTClient:
    """Tests for BARTClient."""

    def test_initialization(self):
        """Test client initialization with defaults."""
        client = BARTClient()
        assert client.timeout == 30.0
        assert client._cache is None
        assert client._cache_time is None
        assert client._cache_ttl == 30

    def test_initialization_custom_timeout(self):
        """Test client initialization with custom timeout."""
        client = BARTClient(timeout=60.0)
        assert client.timeout == 60.0

    def test_cache_invalid_when_empty(self):
        """Test cache is invalid when empty."""
        client = BARTClient()
        assert not client._is_cache_valid()

    def test_cache_valid_within_ttl(self):
        """Test cache is valid within TTL window."""
        client = BARTClient()
        client._cache = [
            BartArrival(
                station_code="BART_EMBR",
                gtfs_stop_id="M16-1",
                trip_id="1",
                route_id="1",
                direction_id=0,
                arrival_time=datetime.now(timezone.utc),
                departure_time=None,
                delay_seconds=0,
                track=None,
            )
        ]
        client._cache_time = datetime.now(timezone.utc)
        assert client._is_cache_valid()

    def test_cache_invalid_after_ttl(self):
        """Test cache is invalid after TTL expires."""
        client = BARTClient()
        client._cache = []
        client._cache_time = datetime.now(timezone.utc) - timedelta(seconds=60)
        assert not client._is_cache_valid()

    def test_map_stop_id_platform_level(self):
        """Test mapping platform-level stop_id to internal code."""
        client = BARTClient()
        assert client._map_stop_id("M16-1") == "BART_EMBR"
        assert client._map_stop_id("A40-2") == "BART_SANL"
        assert client._map_stop_id("K30-1") == "BART_MCAR"

    def test_map_stop_id_parent_station(self):
        """Test mapping parent station code to internal code."""
        client = BARTClient()
        assert client._map_stop_id("EMBR") == "BART_EMBR"
        assert client._map_stop_id("SANL") == "BART_SANL"
        assert client._map_stop_id("MCAR") == "BART_MCAR"

    def test_map_stop_id_unknown(self):
        """Test mapping unknown stop_id returns None."""
        client = BARTClient()
        assert client._map_stop_id("UNKNOWN") is None
        assert client._map_stop_id("ZZ99-9") is None

    def test_get_route_info(self):
        """Test route info lookup."""
        client = BARTClient()
        info = client._get_route_info("1")
        assert info is not None
        assert info[0] == "BART-YEL"
        assert "Antioch" in info[1]

        info = client._get_route_info("7")
        assert info is not None
        assert info[0] == "BART-RED"

        assert client._get_route_info("999") is None

    def test_clear_cache(self):
        """Test cache clearing."""
        client = BARTClient()
        client._cache = []
        client._cache_time = datetime.now(timezone.utc)

        client.clear_cache()

        assert client._cache is None
        assert client._cache_time is None

    @pytest.mark.asyncio
    async def test_get_all_arrivals_with_protobuf(self):
        """Test parsing a real GTFS-RT protobuf response."""
        # Build a minimal GTFS-RT feed
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.timestamp = int(datetime.now(timezone.utc).timestamp())

        entity = feed.entity.add()
        entity.id = "trip1"
        tu = entity.trip_update
        tu.trip.trip_id = "1842090"
        tu.trip.route_id = "1"
        tu.trip.direction_id = 0

        # Add two stops
        now_ts = int(datetime.now(timezone.utc).timestamp())

        stu1 = tu.stop_time_update.add()
        stu1.stop_id = "M16-1"  # Embarcadero platform 1
        stu1.arrival.time = now_ts
        stu1.arrival.delay = 30
        stu1.departure.time = now_ts + 30

        stu2 = tu.stop_time_update.add()
        stu2.stop_id = "M20-1"  # Montgomery platform 1
        stu2.arrival.time = now_ts + 120
        stu2.arrival.delay = 30

        protobuf_bytes = feed.SerializeToString()

        client = BARTClient()
        mock_response = MagicMock()
        mock_response.content = protobuf_bytes
        mock_response.raise_for_status = MagicMock()

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        arrivals = await client.get_all_arrivals()

        assert len(arrivals) == 2
        assert arrivals[0].station_code == "BART_EMBR"
        assert arrivals[0].trip_id == "1842090"
        assert arrivals[0].route_id == "1"
        assert arrivals[0].delay_seconds == 30
        assert arrivals[0].track is None  # BART never has track
        assert arrivals[0].departure_time is not None

        assert arrivals[1].station_code == "BART_MONT"
        assert arrivals[1].departure_time is None

    @pytest.mark.asyncio
    async def test_get_all_arrivals_returns_cached(self):
        """Test that cached data is returned within TTL."""
        client = BARTClient()
        cached_arrival = BartArrival(
            station_code="BART_EMBR",
            gtfs_stop_id="M16-1",
            trip_id="cached_trip",
            route_id="1",
            direction_id=0,
            arrival_time=datetime.now(timezone.utc),
            departure_time=None,
            delay_seconds=0,
            track=None,
        )
        client._cache = [cached_arrival]
        client._cache_time = datetime.now(timezone.utc)

        arrivals = await client.get_all_arrivals()
        assert len(arrivals) == 1
        assert arrivals[0].trip_id == "cached_trip"

    @pytest.mark.asyncio
    async def test_get_all_arrivals_http_error_returns_stale_cache(self):
        """Test that stale cache is returned on HTTP error."""
        client = BARTClient()
        stale_arrival = BartArrival(
            station_code="BART_EMBR",
            gtfs_stop_id="M16-1",
            trip_id="stale_trip",
            route_id="1",
            direction_id=0,
            arrival_time=datetime.now(timezone.utc),
            departure_time=None,
            delay_seconds=0,
            track=None,
        )
        client._cache = [stale_arrival]
        client._cache_time = datetime.now(timezone.utc) - timedelta(seconds=120)

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))
        client._session = mock_session

        arrivals = await client.get_all_arrivals()

        assert len(arrivals) == 1
        assert arrivals[0].trip_id == "stale_trip"

    @pytest.mark.asyncio
    async def test_get_all_arrivals_skips_unmapped_stops(self):
        """Test that stops with unknown stop_ids are skipped."""
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.timestamp = int(datetime.now(timezone.utc).timestamp())

        entity = feed.entity.add()
        entity.id = "trip1"
        tu = entity.trip_update
        tu.trip.trip_id = "123"
        tu.trip.route_id = "1"

        now_ts = int(datetime.now(timezone.utc).timestamp())

        # Known stop
        stu1 = tu.stop_time_update.add()
        stu1.stop_id = "M16-1"  # Embarcadero
        stu1.arrival.time = now_ts

        # Unknown stop
        stu2 = tu.stop_time_update.add()
        stu2.stop_id = "UNKNOWN-99"
        stu2.arrival.time = now_ts + 60

        protobuf_bytes = feed.SerializeToString()

        client = BARTClient()
        mock_response = MagicMock()
        mock_response.content = protobuf_bytes
        mock_response.raise_for_status = MagicMock()

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        arrivals = await client.get_all_arrivals()

        assert len(arrivals) == 1
        assert arrivals[0].station_code == "BART_EMBR"

    @pytest.mark.asyncio
    async def test_get_trip_stops_sorted(self):
        """Test that trip stops are returned sorted by arrival time."""
        now = datetime.now(timezone.utc)
        later = now + timedelta(minutes=5)

        client = BARTClient()
        client._cache = [
            BartArrival(
                station_code="BART_MONT",
                gtfs_stop_id="M20-1",
                trip_id="trip_A",
                route_id="1",
                direction_id=0,
                arrival_time=later,
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
            BartArrival(
                station_code="BART_EMBR",
                gtfs_stop_id="M16-1",
                trip_id="trip_A",
                route_id="1",
                direction_id=0,
                arrival_time=now,
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
            BartArrival(
                station_code="BART_MCAR",
                gtfs_stop_id="K30-1",
                trip_id="trip_B",
                route_id="3",
                direction_id=1,
                arrival_time=now,
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
        ]
        client._cache_time = datetime.now(timezone.utc)

        stops = await client.get_trip_stops("trip_A")
        assert len(stops) == 2
        assert stops[0].station_code == "BART_EMBR"
        assert stops[1].station_code == "BART_MONT"

    @pytest.mark.asyncio
    async def test_close_session(self):
        """Test closing the HTTP session."""
        client = BARTClient()
        # Access session to create it
        _ = client.session
        assert client._session is not None

        await client.close()
        assert client._session is None

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        async with BARTClient() as client:
            _ = client.session
            assert client._session is not None
        assert client._session is None
