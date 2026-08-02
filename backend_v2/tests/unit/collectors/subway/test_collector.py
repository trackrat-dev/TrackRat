"""
Unit tests for SubwayCollector.

Tests unified NYC Subway train discovery, journey updates,
full-replacement expiration logic, and JIT updates.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.mta_common import JOURNEY_UPDATE_LOAD_OPTIONS
from trackrat.collectors.subway.client import (
    _ROUTE_TO_FEED,
    SubwayArrival,
    SubwayClient,
)
from trackrat.collectors.subway.collector import (
    SubwayCollector,
    _generate_train_id,
)
from trackrat.models.database import (
    GTFSCalendar,
    GTFSRoute,
    GTFSStopTime,
    GTFSTrip,
    JourneyStop,
    TrainJourney,
)
from trackrat.services.gtfs import GTFSService
from trackrat.utils.time import ET

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
        now = datetime.now(UTC)
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

        async def mock_process_trip(session, trip_id, trip_arrivals, existing):
            process_calls.append((trip_id, len(trip_arrivals)))
            return "discovered", len(process_calls)

        collector._process_trip = mock_process_trip

        # Mock both the bulk-load query and the stale-expiration query
        # (both call session.execute and iterate .scalars()).
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
        collector._gtfs_service.clear_subway_realtime_trip_cache.assert_called_once_with()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_bulk_loads_existing_journeys_once(
        self, collector, mock_client, mock_session
    ):
        """collect() must bulk-load existing journeys in a single query
        BEFORE the per-trip loop, and pass the resolved journey (or None)
        into _process_trip. Regression guard for the per-trip SELECT
        pattern that was a primary driver of subway_collection timeouts.
        """
        now = datetime.now(UTC)
        arrivals = [
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
                nyct_train_id="01 0100+ SFR",
                is_assigned=True,
            ),
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
                nyct_train_id="05 0500+ FAR",
                is_assigned=True,
            ),
        ]
        mock_client.get_all_arrivals.return_value = (arrivals, {"1234567S", "ACE"})

        # Pre-existing journey for t1 (train_id matches _generate_train_id("t1", "1"))
        existing = MagicMock(spec=TrainJourney)
        existing.train_id = _generate_train_id("t1", "1")
        existing.journey_date = now.astimezone(ET).date()

        mock_result = MagicMock()
        mock_result.scalars.return_value = [existing]
        mock_session.execute.return_value = mock_result

        process_calls: list[tuple[str, TrainJourney | None]] = []

        async def mock_process_trip(session, trip_id, trip_arrivals, existing_journey):
            process_calls.append((trip_id, existing_journey))
            return "discovered", None

        collector._process_trip = mock_process_trip

        await collector.collect(mock_session)

        by_trip = dict(process_calls)
        assert by_trip["t1"] is existing, "pre-existing journey should be passed in"
        assert by_trip["t2"] is None, "unseen trip should get None"
        # Exactly one SELECT for the bulk journey lookup (the second call
        # is the stale-expiration query); both hit mock_session.execute.
        assert mock_session.execute.call_count == 2


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
        now = datetime.now(UTC)
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
        result, journey = await collector._process_trip(
            mock_session, "131800_1..S03R", sample_arrivals, None
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

        result, journey = await collector._process_trip(
            mock_session, "131800_1..S03R", sample_arrivals, existing_journey
        )

        assert result == "updated"
        assert journey is existing_journey

    @pytest.mark.asyncio
    async def test_process_trip_returns_none_for_empty_arrivals(
        self, collector, mock_session
    ):
        """Test _process_trip returns (None, None) for empty arrivals list."""
        result, journey = await collector._process_trip(
            mock_session, "trip_123", [], None
        )

        assert result is None
        assert journey is None

    @pytest.mark.asyncio
    async def test_process_trip_sorts_arrivals_by_time(self, collector, mock_session):
        """Test arrivals are sorted by arrival time to determine origin."""
        now = datetime.now(UTC)
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

        result, journey = await collector._process_trip(
            mock_session, "trip_1", arrivals, None
        )

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
        now = datetime.now(UTC)

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
        now = datetime.now(UTC)
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

        # Must use trip_correct (track "2" at SL01), NOT trip_wrong. Asserted on
        # the times the selected trip actually wrote: the journey's departure is
        # no longer a proxy for trip selection, because it now comes from the
        # origin stop rather than from whichever stop the feed lists first.
        assert stop1.actual_arrival == correct_time
        assert stop2.actual_arrival == correct_time + timedelta(minutes=10)
        assert journey.actual_arrival == correct_time + timedelta(minutes=10)
        # SL01 is the origin and the feed sent no departure time for it, so the
        # departure already recorded there stands. Before, each poll rewrote the
        # journey's departure to the feed's current estimate for its earliest
        # visible stop — here, three minutes into the future.
        assert journey.actual_departure == now - timedelta(minutes=10)

    @pytest.mark.asyncio
    async def test_fuzzy_fallback_when_trip_id_changed(
        self, collector, mock_client, mock_session
    ):
        """When the original trip_id is no longer in the feed (rare: MTA
        reassignment), the JIT falls back to fuzzy matching by station overlap
        and time proximity."""
        now = datetime.now(UTC)

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
        assert stop1.actual_arrival == now + timedelta(seconds=30)
        assert journey.actual_arrival == now + timedelta(seconds=30)
        # SL01 is the origin and the reassigned trip sent no departure time for
        # it, so the journey keeps the departure already recorded there.
        assert journey.actual_departure == now


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
        now = datetime.now(UTC)

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
        async def mock_process_trip(session, trip_id, trip_arrivals, existing):
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

        # Use a list so both session.execute queries (bulk-load + stale
        # expiration) can iterate .scalars() independently.
        mock_stale_result = MagicMock()
        mock_stale_result.scalars.return_value = [stale_journey]
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
        now = datetime.now(UTC)

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

        async def mock_process_trip(session, trip_id, trip_arrivals, existing):
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

        # collect() now runs two session.execute queries that iterate
        # .scalars(): a bulk-load for existing journeys (new in A.1 perf
        # fix) and the stale-expiration query. Use a list so each call
        # gets a fresh iterator.
        mock_stale_result = MagicMock()
        mock_stale_result.scalars.return_value = [stale_journey]
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
    async def test_collect_bails_when_feed_fetch_hangs_past_timeout(self, mock_session):
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


def _northbound_1_train(
    first_stop_minutes_out: int,
    origin_lead_minutes: float | None = None,
) -> list[SubwayArrival]:
    """A northbound 1 train whose first visible stop is 14 St.

    Terminal is S101 (Van Cortlandt Park, last in topology), so
    infer_subway_origin resolves the origin to S142 (South Ferry, first in
    topology). `first_stop_minutes_out` controls whether the train has
    plausibly already left South Ferry.

    `origin_lead_minutes` sets how far the trip_id's encoded origin precedes
    14 St: 0 means the trip starts there (a short turn), a larger value means
    it started somewhere the feed no longer shows. None leaves the encoding
    absent, as it is when the feed omits start_date.
    """
    now = datetime.now(UTC)
    first = now + timedelta(minutes=first_stop_minutes_out)
    trip_origin_time = (
        None
        if origin_lead_minutes is None
        else first - timedelta(minutes=origin_lead_minutes)
    )
    service_date = trip_origin_time.astimezone(ET).date() if trip_origin_time else None
    return [
        SubwayArrival(
            station_code="S132",  # 14 St
            gtfs_stop_id="132N",
            trip_id="091150_1..N03R",
            route_id="1",
            direction_id=0,
            headsign=None,
            arrival_time=first,
            departure_time=first + timedelta(seconds=30),
            delay_seconds=0,
            track="1",
            nyct_train_id="01 1200+ SFR/VCP",
            is_assigned=True,
            trip_origin_time=trip_origin_time,
            service_date=service_date,
        ),
        SubwayArrival(
            station_code="S101",  # Van Cortlandt Park-242 St
            gtfs_stop_id="101N",
            trip_id="091150_1..N03R",
            route_id="1",
            direction_id=0,
            headsign=None,
            arrival_time=first + timedelta(minutes=45),
            departure_time=None,
            delay_seconds=0,
            track="1",
            nyct_train_id="01 1200+ SFR/VCP",
            is_assigned=True,
            trip_origin_time=trip_origin_time,
            service_date=service_date,
        ),
    ]


def _static_northbound_1_stops(
    arrivals: list[SubwayArrival], *, include_south_ferry: bool
) -> list[dict[str, Any]]:
    """Build the matching static extent for the short-turn regression cases."""
    first, last = arrivals[0], arrivals[-1]
    first_scheduled = first.trip_origin_time or first.arrival_time
    stops: list[dict[str, Any]] = []
    sequence = 1
    if include_south_ferry:
        stops.append(
            {
                "station_code": "S142",
                "stop_sequence": sequence,
                "arrival_time": first.trip_origin_time,
                "departure_time": first.trip_origin_time,
            }
        )
        sequence += 1
        first_scheduled = first.arrival_time - timedelta(seconds=first.delay_seconds)
    stops.extend(
        [
            {
                "station_code": "S132",
                "stop_sequence": sequence,
                "arrival_time": first_scheduled,
                "departure_time": first_scheduled,
            },
            {
                "station_code": "S101",
                "stop_sequence": sequence + 1,
                "arrival_time": last.arrival_time,
                "departure_time": last.arrival_time,
            },
        ]
    )
    return stops


class TestSubwaySyntheticOriginNotServed:
    """Issue #1689 — a truncated feed must not fabricate a boardable terminal.

    When GTFS static backfill is unavailable (the normal case for SUBWAY, since
    NYCT real-time trip_ids don't match the static ones), the collector infers
    the origin as the opposite topology terminal. That inference assumes the
    feed dropped stops the train already passed. During a service change the
    feed is truncated instead — the train genuinely starts mid-route — and the
    old code wrote the far terminal as a real JourneyStop with a departure time
    10 minutes before the first visible arrival.

    Because that time could be in the *future*, the stop survived the
    `hide_departed` filter's "departure still upcoming" branch and was served
    as a boardable departure at a station the train never calls at. Production
    on 2026-08-01: the 1 was not running below 14 St, yet South Ferry → Van
    Cortlandt Park returned trains whose real first stop was 14 St.
    """

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.scalar = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def collector(self):
        client = AsyncMock(spec=SubwayClient)
        client.close = AsyncMock()
        with patch("trackrat.collectors.subway.collector.GTFSService"):
            collector = SubwayCollector(client=client)
        collector._gtfs_service = MagicMock()
        # No static backfill — this is what makes origin inference the normal
        # path for SUBWAY rather than an exception.
        collector._gtfs_service.get_static_stop_times = AsyncMock(return_value=None)
        return collector

    @staticmethod
    def _added_stops(mock_session):
        return [
            call.args[0]
            for call in mock_session.add.call_args_list
            if isinstance(call.args[0], JourneyStop)
        ]

    @pytest.mark.asyncio
    async def test_truncated_feed_does_not_invent_south_ferry(
        self, collector, mock_session
    ):
        """The #1689 case: first visible stop is 18 minutes out, so the train
        cannot already have left South Ferry."""
        arrivals = _northbound_1_train(first_stop_minutes_out=18)

        result, journey = await collector._process_trip(
            mock_session, "091150_1..N03R", arrivals, None
        )

        assert result == "discovered"
        stops = self._added_stops(mock_session)
        codes = [s.station_code for s in stops]
        assert "S142" not in codes, (
            "South Ferry must not be written as a stop for a train whose first "
            f"visible stop is 18 minutes away at 14 St; got {codes}"
        )
        assert codes == ["S132", "S101"], f"Expected only the feed's stops, got {codes}"
        assert journey.origin_station_code == "S132", (
            "Origin should fall back to the first stop actually in the feed, "
            f"got {journey.origin_station_code}"
        )
        assert journey.stops_count == 2, (
            "stops_count must not count the rejected synthetic origin, got "
            f"{journey.stops_count}"
        )

    @pytest.mark.asyncio
    async def test_legitimate_inference_still_creates_the_origin(
        self, collector, mock_session
    ):
        """The inference this feature exists for is unchanged: a train two
        minutes from 14 St did already leave South Ferry."""
        arrivals = _northbound_1_train(first_stop_minutes_out=2)

        result, journey = await collector._process_trip(
            mock_session, "091150_1..N03R", arrivals, None
        )

        assert result == "discovered"
        stops = self._added_stops(mock_session)
        codes = [s.station_code for s in stops]
        assert codes == ["S142", "S132", "S101"], (
            "South Ferry should still be backfilled as the origin when the "
            f"train has plausibly already left it; got {codes}"
        )
        origin_stop = stops[0]
        assert origin_stop.stop_sequence == 1
        assert origin_stop.departure_source == "synthetic_origin"
        assert journey.origin_station_code == "S142"
        assert journey.stops_count == 3

    @pytest.mark.asyncio
    async def test_synthesized_origin_is_never_an_upcoming_departure(
        self, collector, mock_session
    ):
        """The regression that made #1689 rider-visible.

        `hide_departed` keeps any stop whose coalesce(actual, scheduled)
        departure is still in the future, so a synthetic origin stamped with a
        future time is served as boardable despite has_departed_station=True.
        Every synthetic origin the collector writes must be in the past.
        """
        arrivals = _northbound_1_train(first_stop_minutes_out=2)

        await collector._process_trip(mock_session, "091150_1..N03R", arrivals, None)

        origin_stop = self._added_stops(mock_session)[0]
        now = datetime.now(UTC)
        assert origin_stop.station_code == "S142"
        assert origin_stop.has_departed_station is True
        assert origin_stop.actual_departure < now, (
            "A stop flagged as departed must have a past departure time, "
            f"got {origin_stop.actual_departure} vs now={now}"
        )
        assert origin_stop.updated_departure < now, (
            "updated_departure feeds the departure board directly; "
            f"got {origin_stop.updated_departure} vs now={now}"
        )

    @pytest.mark.asyncio
    async def test_rejection_applies_to_the_opposite_terminal_too(
        self, collector, mock_session
    ):
        """The mirror of #1689, so the guard isn't accidentally one-sided.

        A southbound 1 terminating at South Ferry (S142, first in topology)
        infers Van Cortlandt Park (S101, last in topology) as its origin. With
        the first visible stop 18 minutes out that inference is equally
        unfounded and must be rejected the same way.
        """
        now = datetime.now(UTC)
        first = now + timedelta(minutes=18)
        arrivals = [
            SubwayArrival(
                station_code="S132",  # 14 St — mid-route, so inference applies
                gtfs_stop_id="132S",
                trip_id="091151_1..S03R",
                route_id="1",
                direction_id=1,
                headsign=None,
                arrival_time=first,
                departure_time=first + timedelta(seconds=30),
                delay_seconds=0,
                track="1",
                nyct_train_id="01 1200+ VCP/SFR",
                is_assigned=True,
            ),
            SubwayArrival(
                station_code="S142",  # South Ferry — the southbound terminal
                gtfs_stop_id="142S",
                trip_id="091151_1..S03R",
                route_id="1",
                direction_id=1,
                headsign=None,
                arrival_time=first + timedelta(minutes=12),
                departure_time=None,
                delay_seconds=0,
                track="1",
                nyct_train_id="01 1200+ VCP/SFR",
                is_assigned=True,
            ),
        ]

        _, journey = await collector._process_trip(
            mock_session, "091151_1..S03R", arrivals, None
        )

        codes = [s.station_code for s in self._added_stops(mock_session)]
        assert "S101" not in codes, (
            "Van Cortlandt Park must not be invented as the origin of a "
            f"southbound train 18 minutes from 14 St; got {codes}"
        )
        assert codes == ["S132", "S142"], f"Expected only feed stops, got {codes}"
        assert journey.origin_station_code == "S132"


class TestSubwayShortTurnKeepsItsOwnOrigin:
    """Issue #1704 — the residual #1690 left behind.

    The temporal guard is one-dimensional: it accepts an inferred origin
    whenever the synthesized departure lands in the past. A short-turn trip
    first seen a few minutes before its real, mid-route first stop lands there
    too, so the collector still wrote the opposite topology terminal as a real
    stop — now stamped in the past instead of the future.

    That is quieter than #1689 (departure boards hide departed stops) but the
    journey's origin and stop count are wrong, and the phantom stop shows on
    the train's stop list and on `hide_departed=false` queries.

    The NYCT trip_id carries the trip's *own* origin departure, which resolves
    the ambiguity the clock cannot. The captured-feed validation for that
    encoding lives in `test_trip_id_encoding.py`; these cases pin the
    collector's use of it.
    """

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.scalar = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def collector(self):
        client = AsyncMock(spec=SubwayClient)
        client.close = AsyncMock()
        with patch("trackrat.collectors.subway.collector.GTFSService"):
            collector = SubwayCollector(client=client)
        collector._gtfs_service = MagicMock()
        collector._gtfs_service.get_static_stop_times = AsyncMock(return_value=None)
        return collector

    @staticmethod
    def _added_stops(mock_session):
        return [
            call.args[0]
            for call in mock_session.add.call_args_list
            if isinstance(call.args[0], JourneyStop)
        ]

    @pytest.mark.asyncio
    async def test_short_turn_seen_just_before_its_first_stop(
        self, collector, mock_session
    ):
        """The #1704 case, and the shape the captured sample confirms: the 1 is
        short-turning at 14 St, the trip is first seen 2 minutes before it gets
        there, and its trip_id says 14 St is where the trip begins."""
        arrivals = _northbound_1_train(first_stop_minutes_out=2, origin_lead_minutes=0)

        result, journey = await collector._process_trip(
            mock_session, "091150_1..N03X053", arrivals, None
        )

        assert result == "discovered"
        codes = [s.station_code for s in self._added_stops(mock_session)]
        assert "S142" not in codes, (
            "South Ferry must not be written as a stop for a trip whose own "
            f"trip_id says it starts at 14 St; got {codes}"
        )
        assert codes == ["S132", "S101"], f"Expected only the feed's stops, got {codes}"
        assert journey.origin_station_code == "S132", (
            "origin_station_code must reflect the trip's actual extent, got "
            f"{journey.origin_station_code}"
        )
        assert (
            journey.stops_count == 2
        ), f"stops_count must not count a rejected origin, got {journey.stops_count}"

    @pytest.mark.asyncio
    async def test_dropped_origin_is_still_backfilled(self, collector, mock_session):
        """The mirror case the gate must not break: same 2-minute lead time,
        but the trip_id places the trip's origin 8 minutes earlier, which is
        what a train that already left South Ferry looks like."""
        arrivals = _northbound_1_train(first_stop_minutes_out=2, origin_lead_minutes=8)
        collector._gtfs_service.get_static_stop_times.return_value = (
            _static_northbound_1_stops(arrivals, include_south_ferry=True)
        )

        _, journey = await collector._process_trip(
            mock_session, "091150_1..N03R", arrivals, None
        )

        codes = [s.station_code for s in self._added_stops(mock_session)]
        assert codes == ["S142", "S132", "S101"], (
            "A trip whose encoded origin precedes its first visible stop by a "
            f"full travel segment still gets its origin backfilled; got {codes}"
        )
        assert journey.origin_station_code == "S142"
        assert journey.stops_count == 3

    @pytest.mark.asyncio
    async def test_delayed_short_turn_uses_static_mid_route_origin(
        self, collector, mock_session
    ):
        """Reopened #1704: a two-minute unpublished delay must not make the
        encoded origin look like an earlier, omitted terminal."""
        arrivals = _northbound_1_train(first_stop_minutes_out=3, origin_lead_minutes=2)
        collector._gtfs_service.get_static_stop_times.return_value = (
            _static_northbound_1_stops(arrivals, include_south_ferry=False)
        )

        _, journey = await collector._process_trip(
            mock_session, "091150_1..N03X053", arrivals, None
        )

        codes = [s.station_code for s in self._added_stops(mock_session)]
        assert codes == ["S132", "S101"]
        assert journey.origin_station_code == "S132"
        assert journey.stops_count == 2

    @pytest.mark.asyncio
    async def test_encoded_trip_without_static_match_fails_closed(
        self, collector, mock_session
    ):
        arrivals = _northbound_1_train(first_stop_minutes_out=2, origin_lead_minutes=8)

        _, journey = await collector._process_trip(
            mock_session, "091150_1..N03R", arrivals, None
        )

        codes = [s.station_code for s in self._added_stops(mock_session)]
        assert codes == ["S132", "S101"]
        assert journey.origin_station_code == "S132"
        assert journey.stops_count == 2

    @pytest.mark.asyncio
    async def test_after_midnight_uses_service_date_for_static_lookup(
        self, collector, mock_session
    ):
        service_date = date(2026, 8, 2)
        first_arrival = ET.localize(datetime(2026, 8, 3, 1, 3))
        trip_origin = ET.localize(datetime(2026, 8, 3, 1, 1))
        arrivals = _northbound_1_train(first_stop_minutes_out=3, origin_lead_minutes=2)
        for index, arrival in enumerate(arrivals):
            arrival.service_date = service_date
            arrival.trip_origin_time = trip_origin
            arrival.arrival_time = first_arrival + timedelta(minutes=45 * index)
            arrival.departure_time = (
                arrival.arrival_time + timedelta(seconds=30) if index == 0 else None
            )

        _, journey = await collector._process_trip(
            mock_session, "006100_1..N03X053", arrivals, None
        )

        collector._gtfs_service.get_static_stop_times.assert_awaited_once_with(
            mock_session,
            "SUBWAY",
            "006100_1..N03X053",
            service_date,
        )
        assert journey.journey_date == date(2026, 8, 3)

    @pytest.mark.asyncio
    async def test_trip_without_the_encoding_falls_back_to_the_temporal_guard(
        self, collector, mock_session
    ):
        """The gate only ever adds a reason to decline. With no usable trip_id
        (the feed omitted start_date), behaviour is exactly what #1690 left."""
        arrivals = _northbound_1_train(
            first_stop_minutes_out=2, origin_lead_minutes=None
        )

        _, journey = await collector._process_trip(
            mock_session, "091150_1..N03R", arrivals, None
        )

        codes = [s.station_code for s in self._added_stops(mock_session)]
        assert codes == [
            "S142",
            "S132",
            "S101",
        ], f"Without the encoding the temporal guard decides alone; got {codes}"
        assert journey.origin_station_code == "S142"

    @pytest.mark.asyncio
    async def test_both_guards_must_pass(self, collector, mock_session):
        """The two conditions are independent: an encoded origin that clears
        the gate does not resurrect an inference the temporal guard rejects."""
        arrivals = _northbound_1_train(first_stop_minutes_out=18, origin_lead_minutes=8)

        _, journey = await collector._process_trip(
            mock_session, "091150_1..N03R", arrivals, None
        )

        codes = [s.station_code for s in self._added_stops(mock_session)]
        assert codes == ["S132", "S101"], (
            "A train 18 minutes from its first visible stop has not left any "
            f"terminal, whatever its trip_id says; got {codes}"
        )
        assert journey.origin_station_code == "S132"


class TestSubwaySyntheticOriginRealDatabase:
    """Issue #1689 end-to-end against real PostgreSQL — nothing stubbed.

    The cases above pin branch selection cheaply, but they program the
    "no static backfill" condition into a fixture and read the stops back
    out of `session.add` calls. These two use a real `AsyncSession`, the
    real `GTFSService`, and a real `SubwayCollector`, then read the rows
    back out of the database:

    - the static-backfill lookup is the production query, and it finds
      nothing for its own reason (NYCT real-time trip_ids have no static
      counterpart), so origin inference is reached the way it is in
      production rather than because a mock said so;
    - the assertions are on persisted rows, so a break in the write path
      (or in the guard) cannot leave them green.
    """

    @pytest.fixture
    def collector(self):
        # Real client and real GTFSService. _process_trip takes its arrivals
        # as an argument and never calls the client, and SubwayClient opens
        # its HTTP session lazily, so nothing here reaches the network.
        return SubwayCollector()

    @staticmethod
    async def _persisted(db_session, train_id):
        """Re-read the journey and its stops from the database."""
        db_session.expunge_all()
        journey = (
            await db_session.execute(
                select(TrainJourney).where(TrainJourney.train_id == train_id)
            )
        ).scalar_one()
        stops = list(
            (
                await db_session.execute(
                    select(JourneyStop)
                    .where(JourneyStop.journey_id == journey.id)
                    .order_by(JourneyStop.stop_sequence)
                )
            )
            .scalars()
            .all()
        )
        return journey, stops

    @staticmethod
    def _gtfs_time(value: datetime, service_date: date) -> str:
        local = value.astimezone(ET)
        day_offset = (local.date() - service_date).days
        hour = local.hour + day_offset * 24
        return f"{hour:02d}:{local.minute:02d}:{local.second:02d}"

    async def _insert_static_trip(
        self,
        db_session,
        realtime_trip_id: str,
        arrivals: list[SubwayArrival],
        *,
        include_south_ferry: bool,
    ) -> None:
        service_date = arrivals[0].service_date
        assert service_date is not None
        service_id = f"TEST-{realtime_trip_id}"
        route = GTFSRoute(
            data_source="SUBWAY",
            route_id=f"route-{realtime_trip_id}",
            route_short_name="1",
            route_long_name="Broadway-7 Avenue",
            route_color="EE352E",
        )
        db_session.add(route)
        await db_session.flush()
        trip = GTFSTrip(
            data_source="SUBWAY",
            trip_id=f"TEST-SERVICE_{realtime_trip_id}",
            route_id=route.id,
            service_id=service_id,
            trip_headsign="Van Cortlandt Park-242 St",
            direction_id=0,
        )
        db_session.add_all(
            [
                trip,
                GTFSCalendar(
                    data_source="SUBWAY",
                    service_id=service_id,
                    monday=True,
                    tuesday=True,
                    wednesday=True,
                    thursday=True,
                    friday=True,
                    saturday=True,
                    sunday=True,
                    start_date=service_date - timedelta(days=1),
                    end_date=service_date + timedelta(days=1),
                ),
            ]
        )
        await db_session.flush()
        static_stops = _static_northbound_1_stops(
            arrivals, include_south_ferry=include_south_ferry
        )
        db_session.add_all(
            [
                GTFSStopTime(
                    trip_id=trip.id,
                    stop_sequence=stop["stop_sequence"],
                    gtfs_stop_id=f"{stop['station_code']}N",
                    station_code=stop["station_code"],
                    arrival_time=self._gtfs_time(stop["arrival_time"], service_date),
                    departure_time=self._gtfs_time(
                        stop["departure_time"], service_date
                    ),
                )
                for stop in static_stops
            ]
        )
        await db_session.flush()
        GTFSService._service_id_cache.clear()

    @pytest.mark.asyncio
    async def test_truncated_feed_persists_no_south_ferry_stop(
        self, collector, db_session
    ):
        """The #1689 case, all the way to the table: a first visible stop 18
        minutes out means the train cannot already have left South Ferry, so
        no South Ferry row may exist."""
        arrivals = _northbound_1_train(first_stop_minutes_out=18)

        result, journey = await collector._process_trip(
            db_session, "091150_1..N03R", arrivals, None
        )
        await db_session.commit()
        train_id = journey.train_id

        assert result == "discovered"

        journey, stops = await self._persisted(db_session, train_id)
        codes = [s.station_code for s in stops]
        assert "S142" not in codes, (
            "South Ferry must not be persisted for a train whose first visible "
            f"stop is 18 minutes away at 14 St; database holds {codes}"
        )
        assert codes == ["S132", "S101"], f"Expected only the feed's stops, got {codes}"
        assert journey.origin_station_code == "S132", (
            "Persisted origin should be the first stop actually in the feed, "
            f"got {journey.origin_station_code}"
        )
        assert (
            journey.stops_count == 2
        ), f"stops_count must match the persisted rows, got {journey.stops_count}"

    @pytest.mark.asyncio
    async def test_legitimate_inference_persists_a_departed_origin(
        self, collector, db_session
    ):
        """The inference the feature exists for still reaches the database: a
        train two minutes from 14 St did already leave South Ferry, and the
        row it writes is departed and in the past — never boardable."""
        arrivals = _northbound_1_train(first_stop_minutes_out=2)

        result, journey = await collector._process_trip(
            db_session, "091150_1..N03R", arrivals, None
        )
        await db_session.commit()
        train_id = journey.train_id

        assert result == "discovered"

        journey, stops = await self._persisted(db_session, train_id)
        codes = [s.station_code for s in stops]
        assert codes == [
            "S142",
            "S132",
            "S101",
        ], f"Expected the inferred origin ahead of the feed's stops, got {codes}"

        origin = stops[0]
        assert journey.origin_station_code == "S142"
        assert journey.stops_count == 3
        assert origin.departure_source == "synthetic_origin", (
            "The inferred origin must stay labelled as synthetic, got "
            f"{origin.departure_source}"
        )
        assert origin.has_departed_station is True
        # The guard's whole premise: a synthesized origin describes a stop the
        # train has already made, so its times cannot be in the future — that
        # is what kept it out of the hide_departed "still upcoming" branch.
        now = datetime.now(UTC)
        assert origin.actual_departure < now, (
            f"Synthetic origin departure {origin.actual_departure} is not in "
            f"the past relative to {now}"
        )
        assert origin.updated_departure < now
        assert origin.actual_departure == origin.actual_arrival

    @pytest.mark.asyncio
    async def test_short_turn_persists_its_own_origin(self, collector, db_session):
        """Issue #1704, all the way to the table. Same two-minute lead time as
        the case above — so the temporal guard accepts — but the trip_id says
        the trip begins at 14 St. The persisted journey must describe the trip
        that actually exists: no South Ferry row, and an origin and stop count
        matching its real extent."""
        arrivals = _northbound_1_train(first_stop_minutes_out=2, origin_lead_minutes=0)

        result, journey = await collector._process_trip(
            db_session, "091150_1..N03X053", arrivals, None
        )
        await db_session.commit()
        train_id = journey.train_id

        assert result == "discovered"

        journey, stops = await self._persisted(db_session, train_id)
        codes = [s.station_code for s in stops]
        assert "S142" not in codes, (
            "South Ferry must not be persisted for a trip whose own trip_id "
            f"places its origin at 14 St; database holds {codes}"
        )
        assert codes == ["S132", "S101"], f"Expected only the feed's stops, got {codes}"
        assert journey.origin_station_code == "S132"
        assert journey.stops_count == 2

    @pytest.mark.asyncio
    async def test_delayed_short_turn_persists_static_mid_route_origin(
        self, collector, db_session
    ):
        arrivals = _northbound_1_train(first_stop_minutes_out=3, origin_lead_minutes=2)
        await self._insert_static_trip(
            db_session,
            "091150_1..N03X053",
            arrivals,
            include_south_ferry=False,
        )

        _, journey = await collector._process_trip(
            db_session, "091150_1..N03X053", arrivals, None
        )
        await db_session.commit()
        journey, stops = await self._persisted(db_session, journey.train_id)

        assert [stop.station_code for stop in stops] == ["S132", "S101"]
        assert journey.origin_station_code == "S132"
        assert journey.stops_count == 2

    @pytest.mark.asyncio
    async def test_dropped_origin_still_persists_with_an_encoded_origin(
        self, collector, db_session
    ):
        """The other side of the #1704 gate, against the same real services.

        The case above proves a decodable trip_id can decline an inference;
        this proves it does not decline every one. Same feed shape, but the
        encoded origin sits a travel segment earlier — a train that really did
        leave South Ferry — so the origin must still be backfilled and
        persisted. Without this, a gate that always declined would look
        correct from the database's side.
        """
        arrivals = _northbound_1_train(first_stop_minutes_out=2, origin_lead_minutes=8)
        await self._insert_static_trip(
            db_session,
            "091150_1..N03R",
            arrivals,
            include_south_ferry=True,
        )

        result, journey = await collector._process_trip(
            db_session, "091150_1..N03R", arrivals, None
        )
        await db_session.commit()
        train_id = journey.train_id

        assert result == "discovered"

        journey, stops = await self._persisted(db_session, train_id)
        codes = [s.station_code for s in stops]
        assert codes == ["S142", "S132", "S101"], (
            "A trip whose encoded origin precedes its first visible stop by a "
            f"full travel segment still gets South Ferry persisted; got {codes}"
        )
        assert journey.origin_station_code == "S142"
        assert journey.stops_count == 3
        assert stops[0].departure_source != "synthetic_origin"
        assert stops[0].has_departed_station is True
        assert stops[0].actual_departure is None

    @pytest.mark.asyncio
    async def test_backfilled_origin_is_not_recorded_as_a_departure_delay(
        self, collector, db_session
    ):
        """A trip discovered after it left its origin must not be stored as
        departing late by its own running time.

        Backfilling South Ferry moves `scheduled_departure` to the real origin.
        Pairing that with the first *visible* stop's live arrival — the only
        stop the feed still lists — invents a delay equal to the running time
        between them. `alert_evaluator._is_significantly_delayed` subtracts
        exactly those two fields, so a train-following subscriber is pushed a
        delay alert for a train that is on time. Every collector restart
        rediscovers every in-flight train mid-route, so this is the common
        case, not an edge one.
        """
        arrivals = _northbound_1_train(first_stop_minutes_out=2, origin_lead_minutes=8)
        await self._insert_static_trip(
            db_session,
            "091150_1..N03R",
            arrivals,
            include_south_ferry=True,
        )

        _, journey = await collector._process_trip(
            db_session, "091150_1..N03R", arrivals, None
        )
        await db_session.commit()
        journey, stops = await self._persisted(db_session, journey.train_id)

        # The scheduled side is the backfilled origin's — that pairing is
        # precisely what made substituting a downstream actual wrong.
        assert stops[0].station_code == "S142"
        assert journey.scheduled_departure == stops[0].scheduled_departure

        substituted = arrivals[0].arrival_time - journey.scheduled_departure
        assert journey.actual_departure is None, (
            "South Ferry was never observed, so the departure is unknown. "
            "Using the first visible stop instead would report this on-time "
            f"train as {substituted.total_seconds() / 60:.0f} minutes late."
        )

    @pytest.mark.asyncio
    async def test_update_cycle_keeps_a_backfilled_origin_departure_unknown(
        self, collector, db_session
    ):
        """Fixing only the discovery path would last four minutes.

        `_process_trip` re-runs against the existing journey on every
        collection cycle, and that branch set the same first-visible-arrival
        value. The journey is re-read with its stops eagerly loaded, the way
        the collector's own update query loads them.
        """
        arrivals = _northbound_1_train(first_stop_minutes_out=2, origin_lead_minutes=8)
        await self._insert_static_trip(
            db_session,
            "091150_1..N03R",
            arrivals,
            include_south_ferry=True,
        )

        _, created = await collector._process_trip(
            db_session, "091150_1..N03R", arrivals, None
        )
        await db_session.commit()
        train_id = created.train_id

        db_session.expunge_all()
        existing = (
            await db_session.execute(
                select(TrainJourney)
                .where(TrainJourney.train_id == train_id)
                .options(*JOURNEY_UPDATE_LOAD_OPTIONS)
            )
        ).scalar_one()

        result, _ = await collector._process_trip(
            db_session, "091150_1..N03R", arrivals, existing
        )
        await db_session.commit()
        journey, _ = await self._persisted(db_session, train_id)

        assert result == "updated"
        assert journey.actual_departure is None, (
            "The update branch must derive the departure from the origin stop "
            "too, or the next collection cycle reinstates the fabricated delay"
        )
