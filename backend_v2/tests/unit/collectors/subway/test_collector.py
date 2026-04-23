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
from trackrat.collectors.subway.client import (
    SubwayArrival,
    SubwayClient,
    _ROUTE_TO_FEED,
)
from trackrat.models.database import JourneyStop, TrainJourney

# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestGenerateTrainId:
    """Tests for the subway train ID generation function.

    _generate_train_id accepts (trip_id, route_id) and produces a stable
    hash-based ID from the trip_id to avoid ID changes during is_assigned transition.
    """

    def test_produces_hash_based_id(self):
        """Trip ID is hashed to 8-char hex with route prefix."""
        result = _generate_train_id("131800_1..S03R", "1")
        assert result.startswith("S1-")
        assert len(result) == len("S1-") + 8

    def test_route_included_in_prefix(self):
        """Route is included in the prefix: 'SA-...'."""
        result = _generate_train_id("trip_abc", "A")
        assert result.startswith("SA-")
        assert len(result) == len("SA-") + 8

    def test_hash_is_deterministic(self):
        """Same trip_id always produces same ID."""
        r1 = _generate_train_id("trip_xyz", "6")
        r2 = _generate_train_id("trip_xyz", "6")
        assert r1 == r2

    def test_different_trip_ids_produce_different_ids(self):
        """Different trip_ids produce different IDs."""
        r1 = _generate_train_id("trip_aaa", "6")
        r2 = _generate_train_id("trip_bbb", "6")
        assert r1 != r2

    def test_same_trip_different_routes_produce_different_ids(self):
        """Same trip_id with different routes produces different prefixes."""
        r1 = _generate_train_id("trip_abc", "1")
        r2 = _generate_train_id("trip_abc", "A")
        assert r1 != r2
        assert r1.startswith("S1-")
        assert r2.startswith("SA-")


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
        client.get_all_arrivals = AsyncMock(return_value=([], set()))
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
        # All feeds succeeded — route "1" -> "1234567S", route "A" -> "ACE"
        mock_client.get_all_arrivals.return_value = (arrivals, {"1234567S", "ACE"})

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

        result, journey = await collector._process_trip(
            mock_session, "131800_1..S03R", sample_arrivals
        )

        assert result == "discovered"
        assert journey is not None
        assert mock_session.add.call_count >= 1
        mock_session.flush.assert_called()

    @pytest.mark.asyncio
    async def test_process_trip_updates_existing_journey(
        self, collector, mock_session, sample_arrivals
    ):
        """Test _process_trip updates existing journey and returns ('updated', id)."""
        existing_journey = MagicMock(spec=TrainJourney)
        existing_journey.id = 42
        # Use a hash-based train_id matching the trip_id "131800_1..S03R"
        existing_journey.train_id = _generate_train_id("131800_1..S03R", "1")
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

        result, journey = await collector._process_trip(
            mock_session, "131800_1..S03R", sample_arrivals
        )

        assert result == "updated"
        assert journey is existing_journey

    @pytest.mark.asyncio
    async def test_process_trip_returns_none_for_empty_arrivals(
        self, collector, mock_session
    ):
        """Test _process_trip returns (None, None) for empty arrivals list."""
        result, journey = await collector._process_trip(mock_session, "trip_123", [])

        assert result is None
        assert journey is None

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

        result, journey = await collector._process_trip(mock_session, "trip_1", arrivals)

        assert result == "discovered"
        assert journey is not None


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
        client.get_all_arrivals = AsyncMock(return_value=([], set()))
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
        journey.train_id = "S1-abc123"
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

    @pytest.mark.asyncio
    async def test_exact_match_picks_correct_trip_on_non_branching_line(
        self, collector, mock_client, mock_session
    ):
        """Regression test: on non-branching lines like the L, all trips share
        identical station sets. The fuzzy matcher would pick the wrong train
        based on time proximity. The exact match (re-hashing candidate trip_ids)
        must pick the correct one regardless of timing.

        Scenario: Journey was created from trip_correct. The feed has two L trips
        with identical stations. trip_wrong has a closer departure time (simulating
        a newer train closer to origin), but trip_correct is the actual train.
        The JIT must pick trip_correct via exact hash match.
        """
        now = datetime.now(timezone.utc)
        trip_correct = "074850_L..S"
        trip_wrong = "075200_L..S"

        # Build the train_id the same way the collector would
        correct_train_id = _generate_train_id(trip_correct, "L")

        journey = MagicMock(spec=TrainJourney)
        journey.id = 1
        journey.train_id = correct_train_id
        journey.data_source = "SUBWAY"
        journey.line_code = "L"
        # Scheduled departure is 10 minutes ago (train is mid-route)
        journey.scheduled_departure = now - timedelta(minutes=10)
        journey.is_completed = False
        journey.update_count = 0

        # Both trips visit the same stations (L line has no branches)
        stop1 = MagicMock(spec=JourneyStop)
        stop1.station_code = "SL01"
        stop1.stop_sequence = 1
        stop1.actual_departure = now - timedelta(minutes=10)
        stop1.actual_arrival = now - timedelta(minutes=10)
        stop1.scheduled_arrival = now - timedelta(minutes=10)
        stop1.scheduled_departure = now - timedelta(minutes=10)
        stop1.has_departed_station = True
        stop1.departure_source = None

        stop2 = MagicMock(spec=JourneyStop)
        stop2.station_code = "SL02"
        stop2.stop_sequence = 2
        stop2.actual_departure = None
        stop2.actual_arrival = None
        stop2.scheduled_arrival = now + timedelta(minutes=5)
        stop2.scheduled_departure = now + timedelta(minutes=5)
        stop2.has_departed_station = False
        stop2.departure_source = None

        journey.stops = [stop1, stop2]

        correct_time = now + timedelta(minutes=3)
        wrong_time = now - timedelta(minutes=8)

        arrivals = [
            # trip_wrong: closer to scheduled_departure (fuzzy would pick this)
            SubwayArrival(
                station_code="SL01",
                gtfs_stop_id="L01S",
                trip_id=trip_wrong,
                route_id="L",
                direction_id=1,
                headsign=None,
                arrival_time=wrong_time,
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id=None,
                is_assigned=True,
            ),
            SubwayArrival(
                station_code="SL02",
                gtfs_stop_id="L02S",
                trip_id=trip_wrong,
                route_id="L",
                direction_id=1,
                headsign=None,
                arrival_time=wrong_time + timedelta(minutes=10),
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id=None,
                is_assigned=True,
            ),
            # trip_correct: further from scheduled_departure but the actual train
            SubwayArrival(
                station_code="SL01",
                gtfs_stop_id="L01S",
                trip_id=trip_correct,
                route_id="L",
                direction_id=1,
                headsign=None,
                arrival_time=correct_time,
                departure_time=None,
                delay_seconds=0,
                track="2",
                nyct_train_id=None,
                is_assigned=True,
            ),
            SubwayArrival(
                station_code="SL02",
                gtfs_stop_id="L02S",
                trip_id=trip_correct,
                route_id="L",
                direction_id=1,
                headsign=None,
                arrival_time=correct_time + timedelta(minutes=10),
                departure_time=None,
                delay_seconds=0,
                track=None,
                nyct_train_id=None,
                is_assigned=True,
            ),
        ]
        mock_client.get_feed_arrivals.return_value = arrivals

        mock_stop_result = MagicMock()
        mock_stop_result.scalar_one_or_none.side_effect = [stop1, stop2]
        mock_stops_list = MagicMock()
        mock_stops_list.scalars.return_value.all.return_value = [stop1, stop2]
        mock_session.execute.side_effect = [
            mock_stop_result,  # SL01 stop lookup
            mock_stop_result,  # SL02 stop lookup
            mock_stops_list,  # Get all stops for update
        ]

        await collector.collect_journey_details(mock_session, journey)

        # Must use trip_correct (track "2" at SL01), NOT trip_wrong
        assert journey.actual_departure == correct_time
        assert journey.actual_arrival == correct_time + timedelta(minutes=10)

    @pytest.mark.asyncio
    async def test_fuzzy_fallback_when_trip_id_changed(
        self, collector, mock_client, mock_session
    ):
        """When the original trip_id is no longer in the feed (rare: MTA
        reassignment), the JIT falls back to fuzzy matching by station overlap
        and time proximity."""
        now = datetime.now(timezone.utc)

        # Journey has a hash from a trip_id that's no longer in the feed
        journey = MagicMock(spec=TrainJourney)
        journey.id = 1
        journey.train_id = _generate_train_id("old_trip_gone", "L")
        journey.data_source = "SUBWAY"
        journey.line_code = "L"
        journey.scheduled_departure = now
        journey.is_completed = False
        journey.update_count = 0

        stop1 = MagicMock(spec=JourneyStop)
        stop1.station_code = "SL01"
        stop1.stop_sequence = 1
        stop1.actual_departure = now
        stop1.actual_arrival = now
        stop1.scheduled_arrival = now
        stop1.scheduled_departure = now
        stop1.has_departed_station = False
        stop1.departure_source = None

        journey.stops = [stop1]

        # Feed only has a new trip_id (no hash match possible)
        arrivals = [
            SubwayArrival(
                station_code="SL01",
                gtfs_stop_id="L01S",
                trip_id="new_trip_reassigned",
                route_id="L",
                direction_id=1,
                headsign=None,
                arrival_time=now + timedelta(seconds=30),
                departure_time=None,
                delay_seconds=0,
                track="1",
                nyct_train_id=None,
                is_assigned=True,
            ),
        ]
        mock_client.get_feed_arrivals.return_value = arrivals

        mock_stop_result = MagicMock()
        mock_stop_result.scalar_one_or_none.return_value = stop1
        mock_stops_list = MagicMock()
        mock_stops_list.scalars.return_value.all.return_value = [stop1]
        mock_session.execute.side_effect = [
            mock_stop_result,  # SL01 stop lookup
            mock_stops_list,  # Get all stops for update
        ]

        await collector.collect_journey_details(mock_session, journey)

        # Fuzzy fallback should still update the journey
        assert journey.actual_departure == now + timedelta(seconds=30)


# =============================================================================
# RUN ENTRY POINT TESTS
# =============================================================================


class TestSubwayCollectorRun:
    """Tests for the run() entry point method."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Subway client."""
        client = AsyncMock(spec=SubwayClient)
        client.get_all_arrivals = AsyncMock(return_value=([], set()))
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


# =============================================================================
# FEED RESILIENCE TESTS
# =============================================================================


class TestSubwayFeedResilience:
    """Tests for per-feed failure tracking and expiration gating.

    When a GTFS-RT feed fails transiently, trains from that feed's routes
    should NOT be expired. Only trains whose feed succeeded and are missing
    from the feed should be expired.
    """

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        nested = AsyncMock()
        nested.__aenter__ = AsyncMock()
        nested.__aexit__ = AsyncMock(return_value=False)
        session.begin_nested = MagicMock(return_value=nested)
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
        return collector

    @pytest.mark.asyncio
    async def test_expiration_skipped_for_failed_feed(
        self, collector, mock_client, mock_session
    ):
        """Trains from a failed feed should NOT be expired.

        Scenario: NQRW feed fails, an N train journey exists and is not in
        the current arrivals. It should be preserved (not expired) because
        we can't distinguish 'train gone' from 'feed unavailable'.
        """
        now = datetime.now(timezone.utc)

        # Return arrivals only from 1234567S feed (NQRW failed)
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
        ]
        # Only 1234567S succeeded; NQRW is NOT in succeeded_feeds
        mock_client.get_all_arrivals.return_value = (arrivals, {"1234567S"})

        # Mock _process_trip to return a discovered journey
        async def mock_process_trip(session, trip_id, trip_arrivals):
            return "discovered", 100

        collector._process_trip = mock_process_trip

        # Create a stale N train journey (route "N" -> feed "NQRW")
        stale_journey = MagicMock(spec=TrainJourney)
        stale_journey.id = 200
        stale_journey.line_code = "N"
        stale_journey.is_expired = False
        stale_journey.is_completed = False
        stale_journey.is_cancelled = False
        stale_journey.api_error_count = 0
        stale_journey.last_updated_at = now - timedelta(minutes=2)

        mock_stale_result = MagicMock()
        mock_stale_result.scalars.return_value = iter([stale_journey])
        mock_session.execute.return_value = mock_stale_result

        result = await collector.collect(mock_session)

        # The N train should NOT be expired since NQRW feed failed
        assert (
            stale_journey.is_expired is False
        ), "Journey from failed feed should NOT be expired"
        assert result["expired"] == 0

    @pytest.mark.asyncio
    async def test_expiration_applied_for_succeeded_feed(
        self, collector, mock_client, mock_session
    ):
        """Trains from a succeeded feed that are missing SHOULD be expired.

        Scenario: 1234567S feed succeeds, a route 1 train is not in the
        current arrivals and was recently active. It should be expired
        (full-replacement semantics).
        """
        now = datetime.now(timezone.utc)

        arrivals = [
            SubwayArrival(
                station_code="SA41",
                gtfs_stop_id="A41S",
                trip_id="trip_A",
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
        # Both feeds succeeded
        mock_client.get_all_arrivals.return_value = (
            arrivals,
            {"1234567S", "ACE"},
        )

        async def mock_process_trip(session, trip_id, trip_arrivals):
            return "discovered", 300

        collector._process_trip = mock_process_trip

        # Create a stale route-1 journey (feed "1234567S" succeeded)
        # last_updated_at is recent (within _REPLACEMENT_WINDOW)
        stale_journey = MagicMock(spec=TrainJourney)
        stale_journey.id = 400
        stale_journey.line_code = "1"
        stale_journey.is_expired = False
        stale_journey.is_completed = False
        stale_journey.is_cancelled = False
        stale_journey.api_error_count = 0
        # Recently active: 2 minutes ago (within 30-min replacement window)
        stale_journey.last_updated_at = now - timedelta(minutes=2)

        mock_stale_result = MagicMock()
        mock_stale_result.scalars.return_value = iter([stale_journey])
        mock_session.execute.return_value = mock_stale_result

        result = await collector.collect(mock_session)

        # The route-1 train SHOULD be expired since 1234567S feed succeeded
        assert (
            stale_journey.is_expired is True
        ), "Journey from succeeded feed should be expired when missing from feed"
        assert result["expired"] == 1

    def test_route_to_feed_mapping_coverage(self):
        """Verify _ROUTE_TO_FEED covers all commonly used subway routes."""
        expected_routes = [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "A",
            "C",
            "E",
            "B",
            "D",
            "F",
            "M",
            "G",
            "J",
            "Z",
            "L",
            "N",
            "Q",
            "R",
            "W",
            "SI",
        ]
        for route in expected_routes:
            assert (
                route in _ROUTE_TO_FEED
            ), f"Route {route} missing from _ROUTE_TO_FEED mapping"

    def test_shuttle_routes_in_ace_feed(self):
        """FS (Franklin Ave Shuttle) and H (Rockaway Park Shuttle) are in the ACE feed.

        Both shuttles operate on IND infrastructure shared with the A/C/E lines.
        They must map to the ACE feed for correct JIT updates.
        """
        assert (
            _ROUTE_TO_FEED["FS"] == "ACE"
        ), f"FS should map to ACE feed, got {_ROUTE_TO_FEED['FS']}"
        assert (
            _ROUTE_TO_FEED["H"] == "ACE"
        ), f"H should map to ACE feed, got {_ROUTE_TO_FEED['H']}"

    def test_gs_shuttle_in_numbered_feed(self):
        """GS (42 St Shuttle) remains in the 1234567S feed."""
        assert (
            _ROUTE_TO_FEED["GS"] == "1234567S"
        ), f"GS should map to 1234567S feed, got {_ROUTE_TO_FEED['GS']}"


# =============================================================================
# GTFS FEED URL TESTS
# =============================================================================


class TestGtfsFeedUrl:
    """Verify GTFS static feed URL uses supplemented version."""

    def test_subway_gtfs_url_is_supplemented(self):
        """GTFS_FEED_URLS['SUBWAY'] should use the supplemented feed
        so planned work (weekend service changes) is reflected."""
        from trackrat.services.gtfs import GTFS_FEED_URLS

        assert (
            "supplemented" in GTFS_FEED_URLS["SUBWAY"]
        ), f"Expected supplemented feed URL, got: {GTFS_FEED_URLS['SUBWAY']}"

    def test_subway_static_url_is_supplemented(self):
        """SUBWAY_GTFS_STATIC_URL constant should match the supplemented feed."""
        from trackrat.config.stations.subway import SUBWAY_GTFS_STATIC_URL

        assert (
            "supplemented" in SUBWAY_GTFS_STATIC_URL
        ), f"Expected supplemented feed URL, got: {SUBWAY_GTFS_STATIC_URL}"


class TestSubwayCollectorFailFast:
    """Tests for subway fail-fast on upstream 5xx / hang (#960)."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_collect_bails_when_feed_fetch_hangs_past_timeout(
        self, mock_session
    ):
        """If the upstream feeds hang indefinitely, the collector must bail
        quickly via asyncio.wait_for. Subway is hit hardest by hangs because
        it fans out to 8 feeds — any one stalled feed can hold the whole
        gather() until each per-feed timeout expires.
        """
        import asyncio as _asyncio

        hang_event = _asyncio.Event()

        async def hang_forever():
            await hang_event.wait()
            return ([], set())

        hung_client = AsyncMock(spec=SubwayClient)
        hung_client.get_all_arrivals = hang_forever
        hung_client.close = AsyncMock()

        with patch("trackrat.collectors.subway.collector.GTFSService"):
            collector = SubwayCollector(client=hung_client)

        with patch(
            "trackrat.collectors.subway.collector._FEED_FETCH_TIMEOUT_SECONDS",
            0.05,
        ):
            import time
            t0 = time.monotonic()
            result = await collector.collect(mock_session)
            elapsed = time.monotonic() - t0

        assert elapsed < 1.0, f"collect() took {elapsed:.2f}s — fail-fast broken"
        assert result["total_arrivals"] == 0
        assert result["discovered"] == 0
        assert result["updated"] == 0
        mock_session.commit.assert_not_called()
