"""Unit tests for SeptaMetroClient.

The Metro feed (``septa-pa-us``) carries the whole surface network — buses,
trolleys and subway. ``parse_feed`` must keep ONLY the rail routes in
``SEPTA_METRO_ROUTES`` (subway + trolley) and drop every bus route, mapping each
``stop_id`` through ``SEPTA_METRO_GTFS_STOP_TO_INTERNAL_MAP`` (unmapped stops are
skipped). Unlike Regional Rail, times here are absolute (``arrival.time``), like
MBTA.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from google.transit import gtfs_realtime_pb2

from trackrat.collectors.septa_common import SeptaFeedFetchError
from trackrat.collectors.septa_metro.client import (
    SeptaMetroArrival,
    SeptaMetroClient,
)

# GTFS stop_ids that ARE mapped in SEPTA_METRO_GTFS_STOP_TO_INTERNAL_MAP.
_STOP_A = ("1272", "SEPM1272")
_STOP_B = ("1273", "SEPM1273")
_STOP_C = ("1392", "SEPM1392")
_UNMAPPED_STOP = "99999999"  # deliberately absent from the map


def _ts(dt: datetime) -> int:
    return int(dt.timestamp())


def _add_metro_trip(
    feed,
    *,
    entity_id: str,
    trip_id: str,
    route_id: str,
    direction_id: int = 0,
    stops: list[tuple[str, datetime | None, datetime | None, int | None]],
):
    """Append an absolute-time TripUpdate for the Metro feed.

    ``stops`` is a list of ``(stop_id, arrival_dt, departure_dt, arrival_delay)``.
    Any of the datetimes may be None to model a departure-only or arrival-only stop.
    """
    entity = feed.entity.add()
    entity.id = entity_id
    tu = entity.trip_update
    tu.trip.trip_id = trip_id
    tu.trip.route_id = route_id
    tu.trip.direction_id = direction_id
    for stop_id, arr_dt, dep_dt, arr_delay in stops:
        stu = tu.stop_time_update.add()
        stu.stop_id = stop_id
        if arr_dt is not None:
            stu.arrival.time = _ts(arr_dt)
        if arr_delay is not None:
            stu.arrival.delay = arr_delay
        if dep_dt is not None:
            stu.departure.time = _ts(dep_dt)
    return entity


def _serialize(feed) -> bytes:
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = int(datetime.now(UTC).timestamp())
    return feed.SerializeToString()


_T = datetime(2026, 7, 18, 15, 0, 0, tzinfo=UTC)


class TestSeptaMetroModel:
    def test_creation_all_fields(self):
        arr = SeptaMetroArrival(
            station_code="SEPM1272",
            gtfs_stop_id="1272",
            trip_id="trip_1",
            route_id="M1",
            direction_id=0,
            headsign=None,
            arrival_time=_T,
            departure_time=_T + timedelta(minutes=1),
            delay_seconds=30,
            track=None,
        )
        assert arr.station_code == "SEPM1272"
        assert arr.gtfs_stop_id == "1272"
        assert arr.route_id == "M1"
        assert arr.delay_seconds == 30
        assert arr.headsign is None
        assert arr.track is None

    def test_creation_optional_none(self):
        arr = SeptaMetroArrival(
            station_code="SEPM1272",
            gtfs_stop_id="1272",
            trip_id="trip_1",
            route_id="L1",
            direction_id=1,
            headsign=None,
            arrival_time=_T,
            departure_time=None,
            delay_seconds=0,
            track=None,
        )
        assert arr.departure_time is None
        assert arr.delay_seconds == 0


class TestSeptaMetroClientBasics:
    @pytest.fixture
    def client(self):
        return SeptaMetroClient(timeout=10.0)

    def test_initialization(self, client):
        assert client.timeout == 10.0
        assert client._session is None
        assert client._cache is None
        assert client._cache_time is None
        assert client._cache_ttl == 30

    def test_session_created_lazily(self, client):
        assert client._session is None
        assert isinstance(client.session, httpx.AsyncClient)

    def test_session_reused(self, client):
        assert client.session is client.session

    @pytest.mark.asyncio
    async def test_close(self, client):
        _ = client.session
        await client.close()
        assert client._session is None

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        async with SeptaMetroClient(timeout=5.0) as client:
            assert client is not None
        assert client._session is None

    def test_cache_invalid_when_empty(self, client):
        assert not client._is_cache_valid()

    def test_cache_valid_within_ttl(self, client):
        client._cache = []
        client._cache_time = datetime.now(UTC)
        assert client._is_cache_valid()

    def test_cache_invalid_when_expired(self, client):
        client._cache = []
        client._cache_time = datetime.now(UTC) - timedelta(seconds=60)
        assert not client._is_cache_valid()

    def test_clear_cache(self, client):
        client._cache = []
        client._cache_time = datetime.now(UTC)
        client.clear_cache()
        assert client._cache is None
        assert client._cache_time is None


class TestSeptaMetroParseFeed:
    """Route filtering (rail only), stop mapping, and absolute-time parsing."""

    def test_keeps_metro_routes_and_drops_bus(self):
        """A mixed feed with a bus route (17) and metro routes (L1, M1, T3) yields
        arrivals only for the metro routes."""
        feed = gtfs_realtime_pb2.FeedMessage()
        _add_metro_trip(
            feed,
            entity_id="bus",
            trip_id="bus_trip",
            route_id="17",  # a bus route — must be dropped entirely
            stops=[(_STOP_A[0], _T, None, 0)],
        )
        _add_metro_trip(
            feed,
            entity_id="l1",
            trip_id="mfl_trip",
            route_id="L1",  # Market-Frankford Line (subway)
            stops=[(_STOP_A[0], _T, _T + timedelta(minutes=1), 30)],
        )
        _add_metro_trip(
            feed,
            entity_id="m1",
            trip_id="nhsl_trip",
            route_id="M1",  # Norristown High Speed Line
            stops=[(_STOP_B[0], _T + timedelta(minutes=2), None, 0)],
        )
        _add_metro_trip(
            feed,
            entity_id="t3",
            trip_id="trolley_trip",
            route_id="T3",  # Route 13 trolley
            stops=[(_STOP_C[0], _T + timedelta(minutes=3), None, 0)],
        )

        arrivals = SeptaMetroClient.parse_feed(_serialize(feed))

        routes = {a.route_id for a in arrivals}
        assert routes == {"L1", "M1", "T3"}
        assert "17" not in routes
        assert len(arrivals) == 3

    def test_maps_stop_id_to_internal_code(self):
        feed = gtfs_realtime_pb2.FeedMessage()
        _add_metro_trip(
            feed,
            entity_id="m1",
            trip_id="trip_1",
            route_id="M1",
            stops=[(_STOP_A[0], _T, None, 0)],
        )
        arrivals = SeptaMetroClient.parse_feed(_serialize(feed))
        assert len(arrivals) == 1
        assert arrivals[0].gtfs_stop_id == _STOP_A[0]
        assert arrivals[0].station_code == _STOP_A[1]

    def test_skips_unmapped_stop_id(self):
        """A metro trip stopping at a stop_id absent from the map skips that stop."""
        feed = gtfs_realtime_pb2.FeedMessage()
        _add_metro_trip(
            feed,
            entity_id="m1",
            trip_id="trip_1",
            route_id="M1",
            stops=[
                (_STOP_A[0], _T, None, 0),  # mapped → kept
                (_UNMAPPED_STOP, _T + timedelta(minutes=2), None, 0),  # dropped
            ],
        )
        arrivals = SeptaMetroClient.parse_feed(_serialize(feed))
        assert len(arrivals) == 1
        assert arrivals[0].station_code == _STOP_A[1]

    def test_parses_absolute_arrival_time_and_delay(self):
        feed = gtfs_realtime_pb2.FeedMessage()
        _add_metro_trip(
            feed,
            entity_id="l1",
            trip_id="trip_1",
            route_id="L1",
            direction_id=1,
            stops=[(_STOP_A[0], _T, _T + timedelta(minutes=1), 45)],
        )
        arrivals = SeptaMetroClient.parse_feed(_serialize(feed))
        arr = arrivals[0]
        assert arr.arrival_time == _T
        assert arr.departure_time == _T + timedelta(minutes=1)
        assert arr.delay_seconds == 45
        assert arr.direction_id == 1
        assert arr.trip_id == "trip_1"
        assert arr.track is None
        assert arr.headsign is None

    def test_departure_time_used_when_arrival_absent(self):
        """A stop with only a departure time falls back to it for arrival_time."""
        feed = gtfs_realtime_pb2.FeedMessage()
        _add_metro_trip(
            feed,
            entity_id="m1",
            trip_id="trip_1",
            route_id="M1",
            stops=[(_STOP_A[0], None, _T + timedelta(minutes=5), None)],
        )
        arrivals = SeptaMetroClient.parse_feed(_serialize(feed))
        assert len(arrivals) == 1
        assert arrivals[0].arrival_time == _T + timedelta(minutes=5)
        assert arrivals[0].departure_time == _T + timedelta(minutes=5)

    def test_stop_with_neither_time_is_skipped(self):
        """A stop with no arrival AND no departure time cannot be placed → skipped."""
        feed = gtfs_realtime_pb2.FeedMessage()
        _add_metro_trip(
            feed,
            entity_id="m1",
            trip_id="trip_1",
            route_id="M1",
            stops=[
                (_STOP_A[0], _T, None, 0),  # kept
                (_STOP_B[0], None, None, None),  # no times → dropped
            ],
        )
        arrivals = SeptaMetroClient.parse_feed(_serialize(feed))
        assert len(arrivals) == 1
        assert arrivals[0].station_code == _STOP_A[1]

    def test_ignores_non_trip_update_entities(self):
        feed = gtfs_realtime_pb2.FeedMessage()
        entity = feed.entity.add()
        entity.id = "vehicle_only"
        entity.vehicle.vehicle.id = "car42"
        _add_metro_trip(
            feed,
            entity_id="m1",
            trip_id="trip_1",
            route_id="M1",
            stops=[(_STOP_A[0], _T, None, 0)],
        )
        arrivals = SeptaMetroClient.parse_feed(_serialize(feed))
        assert len(arrivals) == 1


class TestSeptaMetroGetAllArrivals:
    @pytest.fixture
    def client(self):
        return SeptaMetroClient(timeout=10.0)

    @pytest.mark.asyncio
    async def test_returns_cached_within_ttl(self, client):
        cached = [
            SeptaMetroArrival(
                station_code="SEPM1272",
                gtfs_stop_id="1272",
                trip_id="trip_1",
                route_id="M1",
                direction_id=0,
                headsign=None,
                arrival_time=_T,
                departure_time=None,
                delay_seconds=0,
                track=None,
            )
        ]
        client._cache = cached
        client._cache_time = datetime.now(UTC)
        assert await client.get_all_arrivals() is cached

    @pytest.mark.asyncio
    async def test_batch_fetch_bypasses_valid_cache(self, client):
        client._cache = [
            SeptaMetroArrival(
                station_code="SEPM1272",
                gtfs_stop_id="1272",
                trip_id="cached_trip",
                route_id="M1",
                direction_id=0,
                headsign=None,
                arrival_time=_T,
                departure_time=None,
                delay_seconds=0,
                track=None,
            )
        ]
        client._cache_time = datetime.now(UTC)
        feed = gtfs_realtime_pb2.FeedMessage()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.content = _serialize(feed)
        mock_response.raise_for_status = MagicMock()
        client._session = AsyncMock(spec=httpx.AsyncClient)
        client._session.get.return_value = mock_response

        assert await client.get_all_arrivals(use_cache=False) == []
        client._session.get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_http_error_raises_fetch_error(self, client):
        mock_session = AsyncMock(spec=httpx.AsyncClient)
        mock_session.get.side_effect = httpx.HTTPError("boom")
        client._session = mock_session
        with pytest.raises(SeptaFeedFetchError):
            await client.get_all_arrivals()

    @pytest.mark.asyncio
    async def test_http_error_does_not_return_stale_cache(self, client):
        cached = [
            SeptaMetroArrival(
                station_code="SEPM1273",
                gtfs_stop_id="1273",
                trip_id="trip_1",
                route_id="L1",
                direction_id=0,
                headsign=None,
                arrival_time=_T,
                departure_time=None,
                delay_seconds=0,
                track=None,
            )
        ]
        client._cache = cached
        client._cache_time = datetime.now(UTC) - timedelta(seconds=120)
        mock_session = AsyncMock(spec=httpx.AsyncClient)
        mock_session.get.side_effect = httpx.HTTPError("boom")
        client._session = mock_session
        with pytest.raises(SeptaFeedFetchError):
            await client.get_all_arrivals()

    @pytest.mark.asyncio
    async def test_fetches_and_parses_protobuf(self, client):
        feed = gtfs_realtime_pb2.FeedMessage()
        _add_metro_trip(
            feed,
            entity_id="bus",
            trip_id="bus_trip",
            route_id="17",
            stops=[(_STOP_A[0], _T, None, 0)],
        )
        _add_metro_trip(
            feed,
            entity_id="m1",
            trip_id="metro_trip",
            route_id="M1",
            stops=[(_STOP_A[0], _T, _T + timedelta(minutes=1), 30)],
        )

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.content = _serialize(feed)
        mock_response.raise_for_status = MagicMock()

        mock_session = AsyncMock(spec=httpx.AsyncClient)
        mock_session.get.return_value = mock_response
        client._session = mock_session

        arrivals = await client.get_all_arrivals()
        assert len(arrivals) == 1  # bus dropped
        assert arrivals[0].route_id == "M1"
        assert arrivals[0].station_code == _STOP_A[1]
        assert client._is_cache_valid()
