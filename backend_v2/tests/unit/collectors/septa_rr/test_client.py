"""Unit tests for SeptaRailClient.

Covers the delay-based GTFS-RT parsing (``parse_feed``), the model surface,
caching/TTL behaviour, and network-error handling. The Regional Rail feed is
unusual: each stop_time_update carries a *delay* (seconds) keyed by
``stop_sequence`` and has NO ``stop_id`` and NO absolute times, so these tests
assert on ``arrival_delay`` / ``departure_delay`` rather than timestamps.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from google.transit import gtfs_realtime_pb2

from trackrat.collectors.septa_rr.client import (
    SeptaRailArrival,
    SeptaRailClient,
    SeptaRailStopUpdate,
    SeptaRailTripUpdate,
)


def _add_rr_trip(
    feed,
    *,
    entity_id: str,
    trip_id: str,
    route_id: str,
    direction_id: int = 0,
    vehicle_id: str | None = None,
    stop_updates: list[tuple[int, int | None, int | None]],
):
    """Append a delay-based TripUpdate entity to a GTFS-RT feed.

    ``stop_updates`` is a list of ``(stop_sequence, arrival_delay,
    departure_delay)``. A ``None`` delay is simply not set on the protobuf, which
    is how the real feed represents "no estimate for this side of the stop".
    """
    entity = feed.entity.add()
    entity.id = entity_id
    tu = entity.trip_update
    tu.trip.trip_id = trip_id
    tu.trip.route_id = route_id
    tu.trip.direction_id = direction_id
    if vehicle_id is not None:
        tu.vehicle.id = vehicle_id
    for seq, arr_delay, dep_delay in stop_updates:
        stu = tu.stop_time_update.add()
        stu.stop_sequence = seq
        if arr_delay is not None:
            stu.arrival.delay = arr_delay
        if dep_delay is not None:
            stu.departure.delay = dep_delay
    return entity


def _serialize(feed) -> bytes:
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = int(datetime.now(timezone.utc).timestamp())
    return feed.SerializeToString()


class TestSeptaRailModels:
    """Model-surface sanity checks (pydantic construction/validation)."""

    def test_stop_update_creation(self):
        upd = SeptaRailStopUpdate(
            stop_sequence=7, arrival_delay=120, departure_delay=90
        )
        assert upd.stop_sequence == 7
        assert upd.arrival_delay == 120
        assert upd.departure_delay == 90

    def test_stop_update_allows_none_delays(self):
        upd = SeptaRailStopUpdate(
            stop_sequence=1, arrival_delay=None, departure_delay=None
        )
        assert upd.arrival_delay is None
        assert upd.departure_delay is None

    def test_trip_update_creation(self):
        trip = SeptaRailTripUpdate(
            trip_id="CHW8312_20260718_SID189411",
            route_id="CHW",
            direction_id=1,
            vehicle_label="805",
            stop_updates=[
                SeptaRailStopUpdate(
                    stop_sequence=3, arrival_delay=60, departure_delay=60
                )
            ],
        )
        assert trip.trip_id == "CHW8312_20260718_SID189411"
        assert trip.route_id == "CHW"
        assert trip.direction_id == 1
        assert trip.vehicle_label == "805"
        assert len(trip.stop_updates) == 1

    def test_arrival_creation(self):
        arr = SeptaRailArrival(
            station_code="SEPR90801",
            trip_id="CHW8312_20260718_SID189411",
            route_id="CHW",
            direction_id=0,
            arrival_time=datetime(2026, 7, 18, 10, 30, tzinfo=timezone.utc),
            departure_time=datetime(2026, 7, 18, 10, 31, tzinfo=timezone.utc),
            delay_seconds=120,
            track=None,
        )
        assert arr.station_code == "SEPR90801"
        assert arr.delay_seconds == 120
        assert arr.track is None


class TestSeptaRailClientBasics:
    """Init, lazy session, caching TTL — mirrors the other GTFS-RT clients."""

    @pytest.fixture
    def client(self):
        return SeptaRailClient(timeout=10.0)

    def test_initialization(self, client):
        assert client.timeout == 10.0
        assert client._session is None
        assert client._cache is None
        assert client._cache_time is None
        assert client._cache_ttl == 30

    def test_session_created_lazily(self, client):
        assert client._session is None
        session = client.session
        assert isinstance(session, httpx.AsyncClient)

    def test_session_reused(self, client):
        assert client.session is client.session

    @pytest.mark.asyncio
    async def test_close(self, client):
        _ = client.session
        await client.close()
        assert client._session is None

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        async with SeptaRailClient(timeout=5.0) as client:
            assert client is not None
        assert client._session is None

    def test_cache_invalid_when_empty(self, client):
        assert not client._is_cache_valid()

    def test_cache_valid_within_ttl(self, client):
        client._cache = []
        client._cache_time = datetime.now(timezone.utc)
        assert client._is_cache_valid()

    def test_cache_invalid_when_expired(self, client):
        client._cache = []
        client._cache_time = datetime.now(timezone.utc) - timedelta(seconds=60)
        assert not client._is_cache_valid()

    def test_clear_cache(self, client):
        client._cache = []
        client._cache_time = datetime.now(timezone.utc)
        client.clear_cache()
        assert client._cache is None
        assert client._cache_time is None


class TestSeptaRailParseFeed:
    """The core delay-based parsing logic."""

    def test_parses_trip_fields_and_delays(self):
        """A CHW trip is parsed into a SeptaRailTripUpdate with all fields intact."""
        feed = gtfs_realtime_pb2.FeedMessage()
        _add_rr_trip(
            feed,
            entity_id="e1",
            trip_id="CHW8312_20260718_SID189411",
            route_id="CHW",
            direction_id=1,
            vehicle_id="805",
            stop_updates=[(3, 120, 130), (5, 200, None)],
        )

        result = SeptaRailClient.parse_feed(_serialize(feed))

        assert len(result) == 1
        trip = result[0]
        assert trip.trip_id == "CHW8312_20260718_SID189411"
        assert trip.route_id == "CHW"
        assert trip.direction_id == 1
        assert trip.vehicle_label == "805"
        assert len(trip.stop_updates) == 2

        first, second = trip.stop_updates
        assert first.stop_sequence == 3
        assert first.arrival_delay == 120
        assert first.departure_delay == 130
        assert second.stop_sequence == 5
        assert second.arrival_delay == 200
        # departure delay was not set on the second stop → None
        assert second.departure_delay is None

    def test_filters_out_non_regional_rail_route(self):
        """A bus/non-RR route_id must be dropped; only RR routes survive."""
        feed = gtfs_realtime_pb2.FeedMessage()
        _add_rr_trip(
            feed,
            entity_id="rr",
            trip_id="TRE1000_20260718_SID1",
            route_id="TRE",
            stop_updates=[(1, 30, 30)],
        )
        _add_rr_trip(
            feed,
            entity_id="bus",
            trip_id="BUS17_20260718_SID2",
            route_id="17",  # not a Regional Rail route
            stop_updates=[(1, 45, 45)],
        )

        result = SeptaRailClient.parse_feed(_serialize(feed))

        assert len(result) == 1
        assert result[0].route_id == "TRE"
        assert "17" not in {t.route_id for t in result}

    def test_drops_stop_update_without_any_delay(self):
        """A stop_time_update carrying neither arrival nor departure delay is dropped,
        while the surrounding trip (with valid updates) survives."""
        feed = gtfs_realtime_pb2.FeedMessage()
        _add_rr_trip(
            feed,
            entity_id="e1",
            trip_id="CHW8312_20260718_SID189411",
            route_id="CHW",
            stop_updates=[
                (3, 120, None),  # kept (arrival delay)
                (4, None, None),  # dropped (no delay at all)
                (5, None, 90),  # kept (departure delay only)
            ],
        )

        result = SeptaRailClient.parse_feed(_serialize(feed))

        assert len(result) == 1
        seqs = {u.stop_sequence for u in result[0].stop_updates}
        assert seqs == {3, 5}, "seq 4 (no delay) must be dropped"
        by_seq = {u.stop_sequence: u for u in result[0].stop_updates}
        assert by_seq[3].arrival_delay == 120
        assert by_seq[3].departure_delay is None
        assert by_seq[5].arrival_delay is None
        assert by_seq[5].departure_delay == 90

    def test_drops_trip_with_no_valid_stop_updates(self):
        """An RR trip whose every stop_time_update lacks a delay yields no trip."""
        feed = gtfs_realtime_pb2.FeedMessage()
        _add_rr_trip(
            feed,
            entity_id="empty",
            trip_id="AIR100_20260718_SID3",
            route_id="AIR",
            stop_updates=[(1, None, None), (2, None, None)],
        )
        _add_rr_trip(
            feed,
            entity_id="valid",
            trip_id="AIR200_20260718_SID4",
            route_id="AIR",
            stop_updates=[(1, 60, 60)],
        )

        result = SeptaRailClient.parse_feed(_serialize(feed))

        assert len(result) == 1
        assert result[0].trip_id == "AIR200_20260718_SID4"

    def test_vehicle_label_none_when_absent(self):
        """No vehicle on the trip_update → vehicle_label is None."""
        feed = gtfs_realtime_pb2.FeedMessage()
        _add_rr_trip(
            feed,
            entity_id="e1",
            trip_id="PAO1_20260718_SID5",
            route_id="PAO",
            vehicle_id=None,
            stop_updates=[(1, 10, 10)],
        )

        result = SeptaRailClient.parse_feed(_serialize(feed))
        assert result[0].vehicle_label is None

    def test_zero_delay_is_preserved_not_dropped(self):
        """A genuine 0-second delay (on-time) must be kept — it is a real estimate,
        not a missing field."""
        feed = gtfs_realtime_pb2.FeedMessage()
        _add_rr_trip(
            feed,
            entity_id="e1",
            trip_id="MED1_20260718_SID6",
            route_id="MED",
            stop_updates=[(2, 0, 0)],
        )

        result = SeptaRailClient.parse_feed(_serialize(feed))
        assert len(result) == 1
        assert result[0].stop_updates[0].arrival_delay == 0
        assert result[0].stop_updates[0].departure_delay == 0

    def test_ignores_non_trip_update_entities(self):
        """Entities without a trip_update (e.g. vehicle-only) are ignored."""
        feed = gtfs_realtime_pb2.FeedMessage()
        entity = feed.entity.add()
        entity.id = "vehicle_only"
        entity.vehicle.vehicle.id = "999"  # VehiclePosition, not a TripUpdate
        _add_rr_trip(
            feed,
            entity_id="rr",
            trip_id="WAR1_20260718_SID7",
            route_id="WAR",
            stop_updates=[(1, 15, 15)],
        )

        result = SeptaRailClient.parse_feed(_serialize(feed))
        assert len(result) == 1
        assert result[0].route_id == "WAR"


class TestSeptaRailGetTripUpdates:
    """Fetch path: caching, network errors, end-to-end protobuf parse."""

    @pytest.fixture
    def client(self):
        return SeptaRailClient(timeout=10.0)

    @pytest.mark.asyncio
    async def test_returns_cached_within_ttl(self, client):
        cached = [
            SeptaRailTripUpdate(
                trip_id="CHW8312_20260718_SID1",
                route_id="CHW",
                direction_id=0,
                vehicle_label=None,
                stop_updates=[
                    SeptaRailStopUpdate(
                        stop_sequence=1, arrival_delay=0, departure_delay=0
                    )
                ],
            )
        ]
        client._cache = cached
        client._cache_time = datetime.now(timezone.utc)

        result = await client.get_trip_updates()
        assert result is cached

    @pytest.mark.asyncio
    async def test_http_error_returns_empty(self, client):
        mock_session = AsyncMock(spec=httpx.AsyncClient)
        mock_session.get.side_effect = httpx.HTTPError("boom")
        client._session = mock_session

        result = await client.get_trip_updates()
        assert result == []

    @pytest.mark.asyncio
    async def test_http_error_returns_stale_cache(self, client):
        cached = [
            SeptaRailTripUpdate(
                trip_id="TRE1_20260718_SID1",
                route_id="TRE",
                direction_id=0,
                vehicle_label=None,
                stop_updates=[
                    SeptaRailStopUpdate(
                        stop_sequence=1, arrival_delay=30, departure_delay=30
                    )
                ],
            )
        ]
        client._cache = cached
        client._cache_time = datetime.now(timezone.utc) - timedelta(seconds=120)

        mock_session = AsyncMock(spec=httpx.AsyncClient)
        mock_session.get.side_effect = httpx.HTTPError("boom")
        client._session = mock_session

        result = await client.get_trip_updates()
        assert result == cached

    @pytest.mark.asyncio
    async def test_fetches_and_parses_protobuf(self, client):
        feed = gtfs_realtime_pb2.FeedMessage()
        _add_rr_trip(
            feed,
            entity_id="e1",
            trip_id="CHW8312_20260718_SID189411",
            route_id="CHW",
            direction_id=1,
            vehicle_id="805",
            stop_updates=[(3, 120, 120)],
        )

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.content = _serialize(feed)
        mock_response.raise_for_status = MagicMock()

        mock_session = AsyncMock(spec=httpx.AsyncClient)
        mock_session.get.return_value = mock_response
        client._session = mock_session

        result = await client.get_trip_updates()
        assert len(result) == 1
        assert result[0].trip_id == "CHW8312_20260718_SID189411"
        assert result[0].stop_updates[0].arrival_delay == 120
        # Successful fetch should populate the cache.
        assert client._cache is not None
        assert client._is_cache_valid()
