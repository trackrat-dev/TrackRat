"""
Unit tests for SubwayCollector.

Tests unified NYC Subway train discovery, journey updates,
full-replacement expiration logic, and JIT updates.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.subway.collector import (
    SubwayCollector,
    _generate_train_id,
)
from trackrat.collectors.subway.client import SubwayArrival, SubwayClient
from trackrat.models.database import JourneyStop, TrainJourney

# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestGenerateTrainId:
    """Tests for the subway train ID generation function.

    _generate_train_id accepts (trip_id, nyct_train_id, route_id).
    Prefers NYCT train_id digits, falls back to MD5 hash of trip_id.
    """

    def test_nyct_train_id_extracts_all_digits(self):
        """NYCT train_id '01 0123+ PEL/BBR' -> all digits '010123' -> 'S6-010123'."""
        result = _generate_train_id("some_trip", "01 0123+ PEL/BBR", "6")
        assert result == "S6-010123"

    def test_nyct_train_id_with_different_route(self):
        """Route is included in the prefix: 'SA-...'."""
        result = _generate_train_id("some_trip", "05 0456 FAR", "A")
        assert result == "SA-050456"

    def test_nyct_train_id_no_digits_falls_back_to_hash(self):
        """NYCT train_id with no digits falls back to hash."""
        result = _generate_train_id("trip_abc", "NO DIGITS HERE", "1")
        assert result.startswith("S1-")
        assert len(result) == len("S1-") + 6  # 6-char hex hash

    def test_no_nyct_train_id_uses_hash(self):
        """None nyct_train_id falls back to MD5 hash."""
        result = _generate_train_id("trip_123", None, "A")
        assert result.startswith("SA-")
        assert len(result) == len("SA-") + 6

    def test_hash_is_deterministic(self):
        """Same trip_id always produces same hash fallback."""
        r1 = _generate_train_id("trip_xyz", None, "6")
        r2 = _generate_train_id("trip_xyz", None, "6")
        assert r1 == r2

    def test_different_trip_ids_produce_different_hashes(self):
        """Different trip_ids produce different hash fallbacks."""
        r1 = _generate_train_id("trip_aaa", None, "6")
        r2 = _generate_train_id("trip_bbb", None, "6")
        assert r1 != r2

    def test_different_nyct_ids_produce_different_train_ids(self):
        """Different NYCT train_ids produce different train IDs."""
        r1 = _generate_train_id("trip", "01 0100+ SFR", "1")
        r2 = _generate_train_id("trip", "02 0200+ BBR", "1")
        assert r1 != r2
        assert r1 == "S1-010100"
        assert r2 == "S1-020200"


# =============================================================================
# COLLECTOR INIT TESTS
# =============================================================================


class TestSubwayCollectorInit:
    """Tests for SubwayCollector initialization."""

    def test_creates_client_if_not_provided(self):
        """Test collector creates its own client if none provided."""
        with patch("trackrat.collectors.subway.collector.GTFSService"):
            collector = SubwayCollector()

        assert collector.client is not None
        assert isinstance(collector.client, SubwayClient)
        assert collector._owns_client is True

    def test_uses_provided_client(self):
        """Test collector uses provided client."""
        client = SubwayClient()
        with patch("trackrat.collectors.subway.collector.GTFSService"):
            collector = SubwayCollector(client=client)

        assert collector.client is client
        assert collector._owns_client is False

    @pytest.mark.asyncio
    async def test_close_closes_owned_client(self):
        """Test close() closes client when collector owns it."""
        with patch("trackrat.collectors.subway.collector.GTFSService"):
            collector = SubwayCollector()
        collector.client = AsyncMock(spec=SubwayClient)
        collector._owns_client = True

        await collector.close()

        collector.client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_does_not_close_external_client(self):
        """Test close() does not close externally provided client."""
        client = AsyncMock(spec=SubwayClient)
        with patch("trackrat.collectors.subway.collector.GTFSService"):
            collector = SubwayCollector(client=client)

        await collector.close()

        client.close.assert_not_called()


# =============================================================================
# COLLECTOR COLLECT TESTS
# =============================================================================


class TestSubwayCollectorCollect:
    """Tests for SubwayCollector.collect() method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.scalar = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        # Mock begin_nested as async context manager
        nested = AsyncMock()
        nested.__aenter__ = AsyncMock()
        nested.__aexit__ = AsyncMock(return_value=False)
        session.begin_nested = MagicMock(return_value=nested)
        return session

    @pytest.fixture
    def mock_client(self):
        """Create a mock Subway client."""
        client = AsyncMock(spec=SubwayClient)
        client.get_all_arrivals = AsyncMock(return_value=[])
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def collector(self, mock_client):
        """Create a collector with mock client."""
        with patch("trackrat.collectors.subway.collector.GTFSService"):
            collector = SubwayCollector(client=mock_client)
        return collector

    @pytest.mark.asyncio
    async def test_collect_returns_stats_on_empty_arrivals(
        self, collector, mock_session
    ):
        """Test collect returns correct stats when no arrivals."""
        result = await collector.collect(mock_session)

        assert result["discovered"] == 0
        assert result["updated"] == 0
        assert result["expired"] == 0
        assert result["errors"] == 0
        assert result["total_arrivals"] == 0

    @pytest.mark.asyncio
    async def test_collect_stats_include_expired_key(self, collector, mock_session):
        """Test that subway stats include 'expired' key (unique vs LIRR/MNR)."""
        result = await collector.collect(mock_session)

        assert "expired" in result, "Subway stats should include 'expired' key"

    @pytest.mark.asyncio
    async def test_collect_groups_arrivals_by_trip_id(
        self, collector, mock_client, mock_session
    ):
        """Test arrivals are grouped by trip_id for processing."""
        now = datetime.now(timezone.utc)
        arrivals = [
            SubwayArrival(
                station_code="S127",
                gtfs_stop_id="127S",
                trip_id="trip_1",
                route_id="1",
                direction_id=1,
                headsign=None,
                arrival_time=now,
                departure_time=now + timedelta(seconds=30),
                delay_seconds=0,
                track=None,
                nyct_train_id="01 0100+ SFR",
                is_assigned=True,
            ),
            SubwayArrival(
                station_code="S101",
                gtfs_stop_id="101S",
                trip_id="trip_1",
                route_id="1",
                direction_id=1,
                headsign=None,
                arrival_time=now + timedelta(minutes=15),
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id="01 0100+ SFR",
                is_assigned=True,
            ),
            SubwayArrival(
                station_code="SA41",
                gtfs_stop_id="A41S",
                trip_id="trip_2",
                route_id="A",
                direction_id=1,
                headsign=None,
                arrival_time=now,
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id="05 0500+ FAR",
                is_assigned=True,
            ),
        ]
        mock_client.get_all_arrivals.return_value = arrivals

        # Mock _process_trip to track calls without hitting DB
        process_calls = []

        async def mock_process_trip(session, trip_id, trip_arrivals):
            process_calls.append((trip_id, len(trip_arrivals)))
            return "discovered", len(process_calls)

        collector._process_trip = mock_process_trip

        # Mock stale journey query (for expiration logic)
        mock_stale_result = MagicMock()
        mock_stale_result.scalars.return_value = iter([])
        mock_session.execute.return_value = mock_stale_result

        result = await collector.collect(mock_session)

        assert result["total_arrivals"] == 3
        assert (
            len(process_calls) == 2
        ), f"Expected 2 trips processed, got {len(process_calls)}"
        # trip_1 has 2 arrivals, trip_2 has 1
        trip_ids = [c[0] for c in process_calls]
        assert "trip_1" in trip_ids
        assert "trip_2" in trip_ids
        mock_session.commit.assert_called_once()


# =============================================================================
# PROCESS TRIP TESTS
# =============================================================================


class TestSubwayCollectorProcessTrip:
    """Tests for _process_trip method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.scalar = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_client(self):
        """Create a mock Subway client."""
        client = AsyncMock(spec=SubwayClient)
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def collector(self, mock_client):
        """Create a collector with mock client."""
        with patch("trackrat.collectors.subway.collector.GTFSService"):
            collector = SubwayCollector(client=mock_client)
        # Mock the transit analyzer to avoid DB calls
        collector._gtfs_service = MagicMock()
        collector._gtfs_service.get_static_stop_times = AsyncMock(return_value=None)
        return collector

    @pytest.fixture
    def sample_arrivals(self):
        """Create sample arrivals for a subway trip."""
        now = datetime.now(timezone.utc)
        return [
            SubwayArrival(
                station_code="S127",
                gtfs_stop_id="127S",
                trip_id="131800_1..S03R",
                route_id="1",
                direction_id=1,
                headsign=None,
                arrival_time=now,
                departure_time=now + timedelta(seconds=30),
                delay_seconds=60,
                track="1",
                nyct_train_id="01 0100+ SFR",
                is_assigned=True,
            ),
            SubwayArrival(
                station_code="S137",
                gtfs_stop_id="137S",
                trip_id="131800_1..S03R",
                route_id="1",
                direction_id=1,
                headsign=None,
                arrival_time=now + timedelta(minutes=15),
                departure_time=None,
                delay_seconds=120,
                track="2",
                nyct_train_id="01 0100+ SFR",
                is_assigned=True,
            ),
        ]

    @pytest.mark.asyncio
    async def test_process_trip_creates_new_journey(
        self, collector, mock_session, sample_arrivals
    ):
        """Test _process_trip creates new journey and returns ('discovered', id)."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("trackrat.collectors.subway.collector.TransitAnalyzer") as mock_ta:
            mock_ta.return_value.analyze_new_segments = AsyncMock()
            result, journey_id = await collector._process_trip(
                mock_session, "131800_1..S03R", sample_arrivals
            )

        assert result == "discovered"
        assert mock_session.add.call_count >= 1
        mock_session.flush.assert_called()

    @pytest.mark.asyncio
    async def test_process_trip_updates_existing_journey(
        self, collector, mock_session, sample_arrivals
    ):
        """Test _process_trip updates existing journey and returns ('updated', id)."""
        existing_journey = MagicMock(spec=TrainJourney)
        existing_journey.id = 42
        existing_journey.train_id = "S1-010100"
        existing_journey.data_source = "SUBWAY"
        existing_journey.stops = []

        # First execute returns existing journey, subsequent ones return stops
        mock_result_journey = MagicMock()
        mock_result_journey.scalar_one_or_none.return_value = existing_journey
        mock_result_stop = MagicMock()
        mock_result_stop.scalar_one_or_none.return_value = None
        mock_result_stops_list = MagicMock()
        mock_result_stops_list.scalars.return_value.all.return_value = []
        mock_session.execute.side_effect = [
            mock_result_journey,  # Journey lookup
            mock_result_stop,  # Stop 1 lookup
            mock_result_stop,  # Stop 2 lookup
            mock_result_stops_list,  # Get all stops for update
        ]

        with patch("trackrat.collectors.subway.collector.TransitAnalyzer") as mock_ta:
            mock_ta.return_value.analyze_new_segments = AsyncMock()
            result, journey_id = await collector._process_trip(
                mock_session, "131800_1..S03R", sample_arrivals
            )

        assert result == "updated"
        assert journey_id == 42

    @pytest.mark.asyncio
    async def test_process_trip_returns_none_for_empty_arrivals(
        self, collector, mock_session
    ):
        """Test _process_trip returns (None, None) for empty arrivals list."""
        result, journey_id = await collector._process_trip(mock_session, "trip_123", [])

        assert result is None
        assert journey_id is None

    @pytest.mark.asyncio
    async def test_process_trip_sorts_arrivals_by_time(self, collector, mock_session):
        """Test arrivals are sorted by arrival time to determine origin."""
        now = datetime.now(timezone.utc)
        # Intentionally out of order
        arrivals = [
            SubwayArrival(
                station_code="S137",
                gtfs_stop_id="137S",
                trip_id="trip_1",
                route_id="1",
                direction_id=1,
                headsign=None,
                arrival_time=now + timedelta(minutes=15),
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id="01 0100+ SFR",
                is_assigned=True,
            ),
            SubwayArrival(
                station_code="S127",
                gtfs_stop_id="127S",
                trip_id="trip_1",
                route_id="1",
                direction_id=1,
                headsign=None,
                arrival_time=now,
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id="01 0100+ SFR",
                is_assigned=True,
            ),
        ]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("trackrat.collectors.subway.collector.TransitAnalyzer") as mock_ta:
            mock_ta.return_value.analyze_new_segments = AsyncMock()
            result, _ = await collector._process_trip(mock_session, "trip_1", arrivals)

        assert result == "discovered"


# =============================================================================
# JIT UPDATE TESTS
# =============================================================================


class TestSubwayCollectorJourneyDetails:
    """Tests for collect_journey_details (JIT update) method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def mock_client(self):
        """Create a mock Subway client."""
        client = AsyncMock(spec=SubwayClient)
        client.get_all_arrivals = AsyncMock(return_value=[])
        client.get_feed_arrivals = AsyncMock(return_value=[])
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def collector(self, mock_client):
        """Create a collector with mock client."""
        with patch("trackrat.collectors.subway.collector.GTFSService"):
            collector = SubwayCollector(client=mock_client)
        return collector

    @pytest.mark.asyncio
    async def test_collect_journey_details_skips_non_subway(
        self, collector, mock_session
    ):
        """Test JIT update skips non-SUBWAY journeys."""
        journey = MagicMock(spec=TrainJourney)
        journey.data_source = "LIRR"

        await collector.collect_journey_details(mock_session, journey)

        collector.client.get_feed_arrivals.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_journey_details_handles_no_matching_trip(
        self, collector, mock_client, mock_session
    ):
        """Test JIT update handles case where no matching trip is found."""
        journey = MagicMock(spec=TrainJourney)
        journey.id = 1
        journey.train_id = "S1-999999"
        journey.data_source = "SUBWAY"
        journey.line_code = "1"

        stop = MagicMock(spec=JourneyStop)
        stop.station_code = "S127"
        journey.stops = [stop]

        mock_client.get_feed_arrivals.return_value = []

        await collector.collect_journey_details(mock_session, journey)

        mock_client.get_feed_arrivals.assert_called_once_with("1")

    @pytest.mark.asyncio
    async def test_collect_journey_details_best_match_selects_highest_overlap(
        self, collector, mock_client, mock_session
    ):
        """Test JIT update selects the trip with highest station overlap."""
        now = datetime.now(timezone.utc)

        journey = MagicMock(spec=TrainJourney)
        journey.id = 1
        journey.train_id = "S1-010100"
        journey.data_source = "SUBWAY"
        journey.line_code = "1"
        journey.scheduled_departure = now
        journey.is_completed = False
        journey.update_count = 0

        # Journey has stops at S127 and S137 with proper datetime attributes
        stop1 = MagicMock(spec=JourneyStop)
        stop1.station_code = "S127"
        stop1.stop_sequence = 1
        stop1.actual_departure = now
        stop1.actual_arrival = now
        stop1.scheduled_arrival = now
        stop1.scheduled_departure = now
        stop1.has_departed_station = False
        stop1.departure_source = None

        stop2 = MagicMock(spec=JourneyStop)
        stop2.station_code = "S137"
        stop2.stop_sequence = 2
        stop2.actual_departure = None
        stop2.actual_arrival = now + timedelta(minutes=10)
        stop2.scheduled_arrival = now + timedelta(minutes=10)
        stop2.scheduled_departure = now + timedelta(minutes=10)
        stop2.has_departed_station = False
        stop2.departure_source = None

        journey.stops = [stop1, stop2]

        # Trip A: matches 1 station (S127)
        # Trip B: matches 2 stations (S127, S137) - should be selected
        arrivals = [
            SubwayArrival(
                station_code="S127",
                gtfs_stop_id="127S",
                trip_id="trip_A",
                route_id="1",
                direction_id=1,
                headsign=None,
                arrival_time=now + timedelta(hours=1),
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id=None,
                is_assigned=True,
            ),
            SubwayArrival(
                station_code="S127",
                gtfs_stop_id="127S",
                trip_id="trip_B",
                route_id="1",
                direction_id=1,
                headsign=None,
                arrival_time=now,
                departure_time=None,
                delay_seconds=0,
                track="1",
                nyct_train_id=None,
                is_assigned=True,
            ),
            SubwayArrival(
                station_code="S137",
                gtfs_stop_id="137S",
                trip_id="trip_B",
                route_id="1",
                direction_id=1,
                headsign=None,
                arrival_time=now + timedelta(minutes=10),
                departure_time=None,
                delay_seconds=0,
                track="2",
                nyct_train_id=None,
                is_assigned=True,
            ),
        ]
        mock_client.get_feed_arrivals.return_value = arrivals

        # Mock stop lookups: return mock stops for trip_B arrivals
        mock_stop_result = MagicMock()
        mock_stop_result.scalar_one_or_none.return_value = stop1
        mock_stops_list = MagicMock()
        mock_stops_list.scalars.return_value.all.return_value = [stop1, stop2]
        mock_session.execute.side_effect = [
            mock_stop_result,  # S127 stop lookup
            mock_stop_result,  # S137 stop lookup
            mock_stops_list,  # Get all stops for update
        ]

        await collector.collect_journey_details(mock_session, journey)

        # Verify trip_B was used (2 stops updated, journey times set from trip_B)
        mock_client.get_feed_arrivals.assert_called_once_with("1")
        assert journey.actual_departure == now
        assert journey.actual_arrival == now + timedelta(minutes=10)


# =============================================================================
# RUN ENTRY POINT TESTS
# =============================================================================


class TestSubwayCollectorRun:
    """Tests for the run() entry point method."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Subway client."""
        client = AsyncMock(spec=SubwayClient)
        client.get_all_arrivals = AsyncMock(return_value=[])
        client.get_feed_arrivals = AsyncMock(return_value=[])
        client.close = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_run_creates_session_and_collects(self, mock_client):
        """Test run() creates a session and calls collect()."""
        with patch("trackrat.collectors.subway.collector.GTFSService"):
            collector = SubwayCollector(client=mock_client)

        with patch(
            "trackrat.collectors.subway.collector.get_session"
        ) as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session.execute = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session.rollback = AsyncMock()

            mock_get_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_get_session.return_value.__aexit__ = AsyncMock()

            result = await collector.run()

            assert "discovered" in result
            assert "updated" in result
            assert "expired" in result
            assert "errors" in result
