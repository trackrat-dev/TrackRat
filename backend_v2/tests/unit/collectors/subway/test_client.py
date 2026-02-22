"""
Unit tests for SubwayClient.

Tests GTFS-RT API communication, NYCT protobuf extension parsing,
per-feed caching, and multi-feed concurrent fetching.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from google.transit import gtfs_realtime_pb2

from trackrat.collectors.subway.client import (
    SubwayArrival,
    SubwayClient,
    _nyct_direction_to_direction_id,
)

# =============================================================================
# MODEL TESTS
# =============================================================================


class TestSubwayArrival:
    """Tests for SubwayArrival model."""

    def test_creation_with_all_fields(self):
        """Test creating SubwayArrival with all fields."""
        arrival = SubwayArrival(
            station_code="S127",
            gtfs_stop_id="127S",
            trip_id="131800_1..S03R",
            route_id="1",
            direction_id=1,
            headsign="South Ferry",
            arrival_time=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
            departure_time=datetime(2024, 1, 15, 10, 31, tzinfo=timezone.utc),
            delay_seconds=60,
            track="1",
            nyct_train_id="01 0123+ SFR/242",
            is_assigned=True,
        )

        assert arrival.station_code == "S127"
        assert arrival.gtfs_stop_id == "127S"
        assert arrival.trip_id == "131800_1..S03R"
        assert arrival.route_id == "1"
        assert arrival.direction_id == 1
        assert arrival.headsign == "South Ferry"
        assert arrival.delay_seconds == 60
        assert arrival.track == "1"
        assert arrival.nyct_train_id == "01 0123+ SFR/242"
        assert arrival.is_assigned is True

    def test_creation_with_optional_fields_none(self):
        """Test creating SubwayArrival with optional fields as None."""
        arrival = SubwayArrival(
            station_code="S127",
            gtfs_stop_id="127S",
            trip_id="trip_1",
            route_id="1",
            direction_id=0,
            headsign=None,
            arrival_time=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
            departure_time=None,
            delay_seconds=0,
            track=None,
            nyct_train_id=None,
            is_assigned=False,
        )

        assert arrival.headsign is None
        assert arrival.departure_time is None
        assert arrival.track is None
        assert arrival.nyct_train_id is None
        assert arrival.is_assigned is False
        assert arrival.delay_seconds == 0


# =============================================================================
# DIRECTION HELPER TESTS
# =============================================================================


class TestNyctDirectionToDirectionId:
    """Tests for the NYCT direction conversion function."""

    def test_north_maps_to_0(self):
        """NORTH (1) should map to direction_id 0."""
        assert _nyct_direction_to_direction_id(1) == 0

    def test_east_maps_to_0(self):
        """EAST (2) should map to direction_id 0."""
        assert _nyct_direction_to_direction_id(2) == 0

    def test_south_maps_to_1(self):
        """SOUTH (3) should map to direction_id 1."""
        assert _nyct_direction_to_direction_id(3) == 1

    def test_west_maps_to_1(self):
        """WEST (4) should map to direction_id 1."""
        assert _nyct_direction_to_direction_id(4) == 1

    def test_none_defaults_to_0(self):
        """None should default to direction_id 0."""
        assert _nyct_direction_to_direction_id(None) == 0


# =============================================================================
# CLIENT TESTS
# =============================================================================


class TestSubwayClient:
    """Tests for SubwayClient."""

    @pytest.fixture
    def client(self):
        """Create a SubwayClient instance for testing."""
        return SubwayClient(timeout=10.0)

    def test_initialization(self, client):
        """Test client initializes with correct defaults."""
        assert client.timeout == 10.0
        assert client._session is None
        assert client._cache == {}
        assert client._cache_times == {}
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

    def test_feed_cache_validation_empty(self, client):
        """Test per-feed cache is invalid when empty."""
        assert not client._is_feed_cache_valid("ACE")

    def test_feed_cache_validation_valid(self, client):
        """Test per-feed cache is valid when recently populated."""
        client._cache["ACE"] = [
            SubwayArrival(
                station_code="SA41",
                gtfs_stop_id="A41S",
                trip_id="t1",
                route_id="A",
                direction_id=1,
                headsign=None,
                arrival_time=datetime.now(timezone.utc),
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id=None,
                is_assigned=False,
            )
        ]
        client._cache_times["ACE"] = datetime.now(timezone.utc)
        assert client._is_feed_cache_valid("ACE")

    def test_feed_cache_validation_expired(self, client):
        """Test per-feed cache is invalid when expired."""
        client._cache["ACE"] = [
            SubwayArrival(
                station_code="SA41",
                gtfs_stop_id="A41S",
                trip_id="t1",
                route_id="A",
                direction_id=1,
                headsign=None,
                arrival_time=datetime.now(timezone.utc),
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id=None,
                is_assigned=False,
            )
        ]
        client._cache_times["ACE"] = datetime.now(timezone.utc) - timedelta(seconds=60)
        assert not client._is_feed_cache_valid("ACE")

    def test_feed_cache_validation_one_feed_valid_another_not(self, client):
        """Test that per-feed cache validates independently per feed key."""
        client._cache["ACE"] = []
        client._cache_times["ACE"] = datetime.now(timezone.utc)
        client._cache["BDFM"] = []
        client._cache_times["BDFM"] = datetime.now(timezone.utc) - timedelta(seconds=60)

        assert client._is_feed_cache_valid("ACE")
        assert not client._is_feed_cache_valid("BDFM")

    def test_clear_cache(self, client):
        """Test clear_cache empties all per-feed cache data."""
        client._cache["ACE"] = []
        client._cache_times["ACE"] = datetime.now(timezone.utc)
        client._cache["BDFM"] = []
        client._cache_times["BDFM"] = datetime.now(timezone.utc)

        client.clear_cache()

        assert client._cache == {}
        assert client._cache_times == {}

    @pytest.mark.asyncio
    async def test_fetch_feed_returns_cached(self, client):
        """Test _fetch_feed returns cached data when valid."""
        expected = [
            SubwayArrival(
                station_code="S127",
                gtfs_stop_id="127S",
                trip_id="t1",
                route_id="1",
                direction_id=1,
                headsign=None,
                arrival_time=datetime.now(timezone.utc),
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id=None,
                is_assigned=False,
            )
        ]
        client._cache["1234567S"] = expected
        client._cache_times["1234567S"] = datetime.now(timezone.utc)

        result = await client._fetch_feed("1234567S", "https://example.com/feed")

        assert result == expected

    @pytest.mark.asyncio
    async def test_get_station_arrivals_filters_by_station(self, client):
        """Test get_station_arrivals filters arrivals by station code."""
        client._cache["1234567S"] = [
            SubwayArrival(
                station_code="S127",
                gtfs_stop_id="127S",
                trip_id="t1",
                route_id="1",
                direction_id=1,
                headsign=None,
                arrival_time=datetime.now(timezone.utc),
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id=None,
                is_assigned=False,
            ),
            SubwayArrival(
                station_code="S101",
                gtfs_stop_id="101S",
                trip_id="t2",
                route_id="1",
                direction_id=0,
                headsign=None,
                arrival_time=datetime.now(timezone.utc),
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id=None,
                is_assigned=False,
            ),
        ]
        client._cache_times["1234567S"] = datetime.now(timezone.utc)

        # Patch SUBWAY_GTFS_RT_FEED_URLS to only use the feed we cached
        with patch(
            "trackrat.collectors.subway.client.SUBWAY_GTFS_RT_FEED_URLS",
            {"1234567S": "https://example.com/1234567S"},
        ):
            result = await client.get_station_arrivals("S127")

        assert len(result) == 1
        assert result[0].station_code == "S127"

    @pytest.mark.asyncio
    async def test_get_trip_stops_filters_and_sorts(self, client):
        """Test get_trip_stops filters by trip_id and sorts by arrival time."""
        now = datetime.now(timezone.utc)
        client._cache["1234567S"] = [
            SubwayArrival(
                station_code="S127",
                gtfs_stop_id="127S",
                trip_id="trip_A",
                route_id="1",
                direction_id=1,
                headsign=None,
                arrival_time=now + timedelta(minutes=10),
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id=None,
                is_assigned=False,
            ),
            SubwayArrival(
                station_code="S101",
                gtfs_stop_id="101S",
                trip_id="trip_A",
                route_id="1",
                direction_id=1,
                headsign=None,
                arrival_time=now,
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id=None,
                is_assigned=False,
            ),
            SubwayArrival(
                station_code="SA41",
                gtfs_stop_id="A41S",
                trip_id="trip_B",
                route_id="A",
                direction_id=1,
                headsign=None,
                arrival_time=now,
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id=None,
                is_assigned=False,
            ),
        ]
        client._cache_times["1234567S"] = datetime.now(timezone.utc)

        with patch(
            "trackrat.collectors.subway.client.SUBWAY_GTFS_RT_FEED_URLS",
            {"1234567S": "https://example.com/1234567S"},
        ):
            result = await client.get_trip_stops("trip_A")

        assert len(result) == 2
        assert result[0].station_code == "S101"  # Earlier time first
        assert result[1].station_code == "S127"
        assert result[0].arrival_time < result[1].arrival_time

    @pytest.mark.asyncio
    async def test_fetch_feed_handles_http_error(self, client):
        """Test _fetch_feed returns empty list on HTTP error with no cache."""
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))
        client._session = mock_session

        result = await client._fetch_feed("ACE", "https://example.com/ace")

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_feed_returns_stale_cache_on_error(self, client):
        """Test _fetch_feed returns stale cache on HTTP error."""
        stale_data = [
            SubwayArrival(
                station_code="SA41",
                gtfs_stop_id="A41S",
                trip_id="t1",
                route_id="A",
                direction_id=1,
                headsign=None,
                arrival_time=datetime.now(timezone.utc),
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id=None,
                is_assigned=False,
            )
        ]
        client._cache["ACE"] = stale_data
        client._cache_times["ACE"] = datetime.now(timezone.utc) - timedelta(seconds=120)

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))
        client._session = mock_session

        result = await client._fetch_feed("ACE", "https://example.com/ace")

        assert result == stale_data

    @pytest.mark.asyncio
    async def test_get_all_arrivals_gathers_multiple_feeds(self, client):
        """Test get_all_arrivals fetches all feeds concurrently and merges results."""
        now = datetime.now(timezone.utc)
        # Pre-populate two feed caches
        client._cache["1234567S"] = [
            SubwayArrival(
                station_code="S127",
                gtfs_stop_id="127S",
                trip_id="t1",
                route_id="1",
                direction_id=1,
                headsign=None,
                arrival_time=now + timedelta(minutes=5),
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id=None,
                is_assigned=True,
            ),
        ]
        client._cache_times["1234567S"] = datetime.now(timezone.utc)

        client._cache["ACE"] = [
            SubwayArrival(
                station_code="SA41",
                gtfs_stop_id="A41S",
                trip_id="t2",
                route_id="A",
                direction_id=1,
                headsign=None,
                arrival_time=now,
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id=None,
                is_assigned=True,
            ),
        ]
        client._cache_times["ACE"] = datetime.now(timezone.utc)

        # Patch to only use these two feeds
        with patch(
            "trackrat.collectors.subway.client.SUBWAY_GTFS_RT_FEED_URLS",
            {
                "1234567S": "https://example.com/1234567S",
                "ACE": "https://example.com/ace",
            },
        ):
            result, succeeded_feeds = await client.get_all_arrivals()

        assert len(result) == 2
        # Results should be sorted by arrival time
        assert result[0].station_code == "SA41"  # Earlier time
        assert result[1].station_code == "S127"
        # Both feeds had cached data, so both should be in succeeded_feeds
        assert succeeded_feeds == {"1234567S", "ACE"}

    @pytest.mark.asyncio
    async def test_fetch_feed_parses_nyct_extensions(self, client):
        """Test that NYCT extensions are used when parsing feeds.

        Uses mocked extension extractors since protobuf3 drops TripUpdate-level
        unknown fields when re-serializing through FeedMessage (a known limitation).
        The actual wire-format parsing is tested in test_mta_extensions.py.
        """
        now_ts = int(datetime.now(timezone.utc).timestamp()) + 3600

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.timestamp = int(datetime.now(timezone.utc).timestamp())

        entity = feed.entity.add()
        entity.id = "1"
        trip = entity.trip_update.trip
        trip.trip_id = "131800_1..S03R"
        trip.route_id = "1"

        stu = entity.trip_update.stop_time_update.add()
        stu.stop_id = "127S"
        stu.arrival.time = now_ts
        stu.arrival.delay = 30

        feed_bytes = feed.SerializeToString()

        mock_response = MagicMock()
        mock_response.content = feed_bytes
        mock_response.raise_for_status = MagicMock()

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        with (
            patch(
                "trackrat.collectors.subway.client.extract_nyct_trip_descriptor",
                return_value={
                    "train_id": "01 0123+ SFR/242",
                    "is_assigned": True,
                    "direction": 3,
                },
            ),
            patch(
                "trackrat.collectors.subway.client.extract_nyct_stop_time_update",
                return_value={"scheduled_track": None, "actual_track": "M1"},
            ),
        ):
            result = await client._fetch_feed("1234567S", "https://example.com/feed")

        assert len(result) == 1, f"Expected 1 arrival, got {len(result)}"
        arrival = result[0]
        assert arrival.station_code == "S127"
        assert arrival.trip_id == "131800_1..S03R"
        assert arrival.nyct_train_id == "01 0123+ SFR/242"
        assert arrival.is_assigned is True
        assert (
            arrival.direction_id == 1
        ), f"Expected 1 (SOUTH), got {arrival.direction_id}"
        assert arrival.track == "M1"

    @pytest.mark.asyncio
    async def test_fetch_feed_handles_missing_extensions(self, client):
        """Test that arrivals work without NYCT extensions (defaults)."""
        now_ts = int(datetime.now(timezone.utc).timestamp()) + 3600

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.timestamp = int(datetime.now(timezone.utc).timestamp())

        entity = feed.entity.add()
        entity.id = "1"
        trip = entity.trip_update.trip
        trip.trip_id = "test_trip_no_ext"
        trip.route_id = "1"
        trip.direction_id = 0

        stu = entity.trip_update.stop_time_update.add()
        stu.stop_id = "127S"  # Times Sq southbound
        stu.arrival.time = now_ts
        stu.arrival.delay = 0

        feed_bytes = feed.SerializeToString()

        mock_response = MagicMock()
        mock_response.content = feed_bytes
        mock_response.raise_for_status = MagicMock()

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        client._session = mock_session

        result = await client._fetch_feed("1234567S", "https://example.com/feed")

        assert len(result) == 1
        arrival = result[0]
        assert arrival.nyct_train_id is None
        assert arrival.is_assigned is False
        assert arrival.track is None
        assert arrival.direction_id == 0

    @pytest.mark.asyncio
    async def test_get_all_arrivals_tracks_failed_feeds(self, client):
        """Test that succeeded_feeds excludes feeds that raised exceptions.

        When a feed fetch raises an exception, it should not appear in
        the succeeded_feeds set. Stale cache data is still returned for
        arrivals but the feed is not counted as successfully fetched.
        """
        now = datetime.now(timezone.utc)

        # Cache data for ACE feed (will fail on refresh)
        client._cache["ACE"] = [
            SubwayArrival(
                station_code="SA41",
                gtfs_stop_id="A41S",
                trip_id="t_stale",
                route_id="A",
                direction_id=1,
                headsign=None,
                arrival_time=now,
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id=None,
                is_assigned=False,
            )
        ]
        # Expired cache so it will attempt to refetch
        client._cache_times["ACE"] = now - timedelta(seconds=120)

        # 1234567S has valid cache
        client._cache["1234567S"] = [
            SubwayArrival(
                station_code="S127",
                gtfs_stop_id="127S",
                trip_id="t_fresh",
                route_id="1",
                direction_id=1,
                headsign=None,
                arrival_time=now + timedelta(minutes=5),
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id=None,
                is_assigned=True,
            )
        ]
        client._cache_times["1234567S"] = now  # Valid cache

        # Mock session: ACE will fail on fetch
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(
            side_effect=httpx.HTTPError("ACE feed unavailable")
        )
        client._session = mock_session

        with patch(
            "trackrat.collectors.subway.client.SUBWAY_GTFS_RT_FEED_URLS",
            {
                "1234567S": "https://example.com/1234567S",
                "ACE": "https://example.com/ace",
            },
        ):
            arrivals, succeeded_feeds = await client.get_all_arrivals()

        # 1234567S served from valid cache, ACE failed
        assert "1234567S" in succeeded_feeds, (
            "1234567S had valid cache and should be in succeeded_feeds"
        )
        assert "ACE" not in succeeded_feeds, (
            "ACE feed failed and should NOT be in succeeded_feeds"
        )
        # Stale ACE data is still included in arrivals
        assert len(arrivals) == 2, (
            f"Expected 2 arrivals (1 fresh + 1 stale), got {len(arrivals)}"
        )

    @pytest.mark.asyncio
    async def test_get_all_arrivals_empty_feed_not_counted_as_success(self, client):
        """Test that a feed returning empty results is not in succeeded_feeds.

        An empty response might indicate a feed issue rather than no trains.
        """
        now = datetime.now(timezone.utc)

        client._cache["1234567S"] = [
            SubwayArrival(
                station_code="S127",
                gtfs_stop_id="127S",
                trip_id="t1",
                route_id="1",
                direction_id=1,
                headsign=None,
                arrival_time=now,
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id=None,
                is_assigned=True,
            )
        ]
        client._cache_times["1234567S"] = now  # Valid cache

        # ACE returns empty (not an error, but empty)
        client._cache["ACE"] = []
        client._cache_times["ACE"] = now  # Valid cache

        with patch(
            "trackrat.collectors.subway.client.SUBWAY_GTFS_RT_FEED_URLS",
            {
                "1234567S": "https://example.com/1234567S",
                "ACE": "https://example.com/ace",
            },
        ):
            arrivals, succeeded_feeds = await client.get_all_arrivals()

        assert "1234567S" in succeeded_feeds
        assert "ACE" not in succeeded_feeds, (
            "Empty feed should not count as success"
        )
