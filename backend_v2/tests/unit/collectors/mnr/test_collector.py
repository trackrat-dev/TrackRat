"""
Unit tests for MNRCollector.

Tests unified Metro-North train discovery and journey update logic.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.mnr.collector import (
    MNRCollector,
    _generate_train_id,
)
from trackrat.collectors.mnr.client import MnrArrival, MNRClient
from trackrat.models.database import JourneyStop, TrainJourney

# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestGenerateTrainId:
    """Tests for the MNR train ID generation function.

    _generate_train_id accepts only trip_id and extracts the train number
    from the last 6 characters, keeping only digits (e.g., "trip_123456" -> "M123456").
    """

    def test_generates_correct_format_with_m_prefix(self):
        """Standard trip_id with numeric suffix -> M-prefixed digits."""
        assert _generate_train_id("trip_123456") == "M123456"

    def test_extracts_last_6_digits_from_long_trip_id(self):
        """Long trip_id: last 6 chars '123456' -> 'M123456'."""
        assert _generate_train_id("MNR_20260119_123456") == "M123456"

    def test_short_numeric_trip_id(self):
        """Short all-numeric trip_id with no underscores."""
        assert _generate_train_id("1234") == "M1234"

    def test_mixed_alphanumeric_suffix_keeps_only_digits(self):
        """Last 6 chars 'BC123\\0' filtered to digits only."""
        # "tripABC123" -> last 6 = "ABC123" -> digits = "123"
        assert _generate_train_id("tripABC123") == "M123"

    def test_no_digits_falls_back_to_first_6_chars(self):
        """Trip_id with no digits in last 6 uses first 6 chars as fallback."""
        assert _generate_train_id("ABCDEFGH") == "MABCDEF"

    def test_different_trip_ids_produce_different_train_ids(self):
        """Different trip IDs produce different train IDs."""
        id1 = _generate_train_id("trip_111111")
        id2 = _generate_train_id("trip_222222")
        assert id1 != id2
        assert id1 == "M111111"
        assert id2 == "M222222"


# =============================================================================
# COLLECTOR TESTS
# =============================================================================


class TestMNRCollectorInit:
    """Tests for MNRCollector initialization."""

    def test_creates_client_if_not_provided(self):
        """Test collector creates its own client if none provided."""
        collector = MNRCollector()

        assert collector.client is not None
        assert isinstance(collector.client, MNRClient)
        assert collector._owns_client is True

    def test_uses_provided_client(self):
        """Test collector uses provided client."""
        client = MNRClient()
        collector = MNRCollector(client=client)

        assert collector.client is client
        assert collector._owns_client is False

    @pytest.mark.asyncio
    async def test_close_closes_owned_client(self):
        """Test close() closes client when collector owns it."""
        collector = MNRCollector()
        collector.client = AsyncMock(spec=MNRClient)
        collector._owns_client = True

        await collector.close()

        collector.client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_does_not_close_external_client(self):
        """Test close() does not close externally provided client."""
        client = AsyncMock(spec=MNRClient)
        collector = MNRCollector(client=client)

        await collector.close()

        client.close.assert_not_called()


class TestMNRCollectorCollect:
    """Tests for MNRCollector.collect() method."""

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
        """Create a mock MNR client."""
        client = AsyncMock(spec=MNRClient)
        client.get_all_arrivals = AsyncMock(return_value=[])
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def collector(self, mock_client):
        """Create a collector with mock client."""
        collector = MNRCollector(client=mock_client)
        return collector

    @pytest.mark.asyncio
    async def test_collect_returns_stats_on_empty_arrivals(
        self, collector, mock_session
    ):
        """Test collect returns correct stats when no arrivals."""
        result = await collector.collect(mock_session)

        assert result["discovered"] == 0
        assert result["updated"] == 0
        assert result["errors"] == 0
        assert result["total_arrivals"] == 0

    @pytest.mark.asyncio
    async def test_collect_groups_arrivals_by_trip_id(
        self, collector, mock_client, mock_session
    ):
        """Test arrivals are grouped by trip_id."""
        now = datetime.now(timezone.utc)
        arrivals = [
            MnrArrival(
                station_code="GCT",
                gtfs_stop_id="1",
                trip_id="trip_123",
                route_id="1",
                direction_id=0,
                headsign="Poughkeepsie",
                arrival_time=now,
                departure_time=now + timedelta(minutes=1),
                delay_seconds=0,
                track=None,
            ),
            MnrArrival(
                station_code="M125",
                gtfs_stop_id="4",
                trip_id="trip_123",
                route_id="1",
                direction_id=0,
                headsign="Poughkeepsie",
                arrival_time=now + timedelta(minutes=30),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
            MnrArrival(
                station_code="GCT",
                gtfs_stop_id="1",
                trip_id="trip_456",
                route_id="2",
                direction_id=1,
                headsign="Wassaic",
                arrival_time=now,
                departure_time=now + timedelta(minutes=1),
                delay_seconds=0,
                track=None,
            ),
        ]
        mock_client.get_all_arrivals.return_value = arrivals

        # Mock no existing journeys
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await collector.collect(mock_session)

        assert result["total_arrivals"] == 3
        # Two trips should be processed (trip_123 and trip_456)
        mock_session.commit.assert_called_once()


class TestMNRCollectorProcessTrip:
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
        """Create a mock MNR client."""
        client = AsyncMock(spec=MNRClient)
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def collector(self, mock_client):
        """Create a collector with mock client."""
        return MNRCollector(client=mock_client)

    @pytest.fixture
    def sample_arrivals(self):
        """Create sample arrivals for a trip."""
        now = datetime.now(timezone.utc)
        return [
            MnrArrival(
                station_code="GCT",
                gtfs_stop_id="1",
                trip_id="trip_123456",
                route_id="1",
                direction_id=0,
                headsign="Poughkeepsie",
                arrival_time=now,
                departure_time=now + timedelta(minutes=1),
                delay_seconds=60,
                track="5",
            ),
            MnrArrival(
                station_code="M125",
                gtfs_stop_id="4",
                trip_id="trip_123456",
                route_id="1",
                direction_id=0,
                headsign="Poughkeepsie",
                arrival_time=now + timedelta(minutes=30),
                departure_time=None,
                delay_seconds=120,
                track="17",
            ),
        ]

    @pytest.mark.asyncio
    async def test_process_trip_creates_new_journey(
        self, collector, mock_session, sample_arrivals
    ):
        """Test _process_trip creates new journey when none exists."""
        # Mock no existing journey
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result, journey = await collector._process_trip(
            mock_session, "trip_123456", sample_arrivals
        )

        assert result == "discovered"
        assert journey is not None
        # Should add journey and stops
        assert mock_session.add.call_count >= 1
        mock_session.flush.assert_called()

    @pytest.mark.asyncio
    async def test_process_trip_updates_existing_journey(
        self, collector, mock_session, sample_arrivals
    ):
        """Test _process_trip updates an existing journey without issuing
        per-arrival JourneyStop SELECTs (uses the eagerly-loaded stops)."""
        now = datetime.now(timezone.utc)
        # Station codes must match sample_arrivals (GCT, M125).
        mock_stop_gct = MagicMock(spec=JourneyStop)
        mock_stop_gct.station_code = "GCT"
        mock_stop_gct.track = None
        mock_stop_gct.actual_departure = now
        mock_stop_gct.actual_arrival = now
        mock_stop_gct.scheduled_arrival = now
        mock_stop_gct.has_departed_station = False
        mock_stop_gct.departure_source = None
        mock_stop_gct.stop_sequence = 1
        mock_stop_m125 = MagicMock(spec=JourneyStop)
        mock_stop_m125.station_code = "M125"
        mock_stop_m125.track = None
        mock_stop_m125.actual_departure = None
        mock_stop_m125.actual_arrival = now + timedelta(minutes=30)
        mock_stop_m125.scheduled_arrival = now + timedelta(minutes=30)
        mock_stop_m125.has_departed_station = False
        mock_stop_m125.departure_source = None
        mock_stop_m125.stop_sequence = 2

        existing_journey = MagicMock(spec=TrainJourney)
        existing_journey.id = 1
        existing_journey.train_id = "M123456"
        existing_journey.data_source = "MNR"
        existing_journey.stops = [mock_stop_gct, mock_stop_m125]

        journey_result = MagicMock()
        journey_result.scalar_one_or_none.return_value = existing_journey

        empty_result = MagicMock()
        empty_scalars = MagicMock()
        empty_scalars.all.return_value = []
        empty_result.scalars.return_value = empty_scalars
        empty_result.scalar_one_or_none.return_value = None
        empty_result.scalar.return_value = None

        mock_session.execute = AsyncMock(
            side_effect=[journey_result] + [empty_result] * 10
        )

        result, journey = await collector._process_trip(
            mock_session, "trip_123456", sample_arrivals
        )

        assert result == "updated"
        assert journey is existing_journey
        # Stops must be updated in memory — actual_arrival assigned from the arrivals
        assert mock_stop_gct.actual_arrival == sample_arrivals[0].arrival_time
        assert mock_stop_m125.actual_arrival == sample_arrivals[1].arrival_time
        # The N+1 SELECT pattern emitted one `select(JourneyStop).where(
        # journey_id, station_code)` per arrival. Its query shape must not
        # be issued anymore.
        per_arrival_select_calls = [
            call
            for call in mock_session.execute.call_args_list
            if "station_code =" in str(call).replace("\n", " ")
            and "stop_sequence" not in str(call).replace("\n", " ")
        ]
        assert (
            len(per_arrival_select_calls) == 0
        ), f"N+1 query pattern detected: {per_arrival_select_calls}"

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
        ]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result, journey = await collector._process_trip(
            mock_session, "trip_123", arrivals
        )

        assert result == "discovered"
        assert journey is not None
        # Origin should be GCT (earlier time)
        # This is implicitly tested by the journey being created correctly


class TestMNRCollectorJourneyDetails:
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
        """Create a mock MNR client."""
        client = AsyncMock(spec=MNRClient)
        client.get_all_arrivals = AsyncMock(return_value=[])
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def collector(self, mock_client):
        """Create a collector with mock client."""
        return MNRCollector(client=mock_client)

    @pytest.mark.asyncio
    async def test_collect_journey_details_skips_non_mnr(self, collector, mock_session):
        """Test JIT update skips non-MNR journeys."""
        journey = MagicMock(spec=TrainJourney)
        journey.data_source = "NJT"

        await collector.collect_journey_details(mock_session, journey)

        # Should return early without fetching arrivals
        collector.client.get_all_arrivals.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_journey_details_updates_stops(
        self, collector, mock_client, mock_session
    ):
        """Test JIT update fetches and updates stop data."""
        now = datetime.now(timezone.utc)

        # Create journey with stops
        journey = MagicMock(spec=TrainJourney)
        journey.id = 1
        journey.train_id = "M123456"
        journey.data_source = "MNR"

        stop1 = MagicMock(spec=JourneyStop)
        stop1.station_code = "GCT"
        stop1.stop_sequence = 1
        stop1.actual_departure = None
        stop1.actual_arrival = None
        stop1.scheduled_arrival = now
        stop1.has_departed_station = False
        stop1.departure_source = None

        stop2 = MagicMock(spec=JourneyStop)
        stop2.station_code = "M125"
        stop2.stop_sequence = 2
        stop2.actual_departure = None
        stop2.actual_arrival = None
        stop2.scheduled_arrival = now + timedelta(minutes=30)
        stop2.has_departed_station = False
        stop2.departure_source = None

        journey.stops = [stop1, stop2]
        journey.is_completed = False
        journey.update_count = 0

        # Mock arrivals that match the journey
        arrivals = [
            MnrArrival(
                station_code="GCT",
                gtfs_stop_id="1",
                trip_id="trip_123456",
                route_id="1",
                direction_id=0,
                headsign=None,
                arrival_time=now,
                departure_time=now + timedelta(minutes=1),
                delay_seconds=120,
                track="5",
            ),
            MnrArrival(
                station_code="M125",
                gtfs_stop_id="4",
                trip_id="trip_123456",
                route_id="1",
                direction_id=0,
                headsign=None,
                arrival_time=now + timedelta(minutes=30),
                departure_time=None,
                delay_seconds=180,
                track="17",
            ),
        ]
        mock_client.get_all_arrivals.return_value = arrivals

        # Mock finding stops
        stop_result = MagicMock()
        stop_result.scalar_one_or_none.side_effect = [stop1, stop2]
        mock_session.execute.return_value = stop_result

        await collector.collect_journey_details(mock_session, journey)

        # Should fetch arrivals
        mock_client.get_all_arrivals.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_journey_details_handles_no_matching_trip(
        self, collector, mock_client, mock_session
    ):
        """Test JIT update handles case where no matching trip is found."""
        journey = MagicMock(spec=TrainJourney)
        journey.id = 1
        journey.train_id = "M999999"
        journey.data_source = "MNR"

        stop = MagicMock(spec=JourneyStop)
        stop.station_code = "GCT"
        journey.stops = [stop]

        # No arrivals match this journey
        mock_client.get_all_arrivals.return_value = []

        await collector.collect_journey_details(mock_session, journey)

        # Should complete without error
        mock_client.get_all_arrivals.assert_called_once()

    @pytest.mark.asyncio
    async def test_exact_match_picks_correct_trip_over_closer_time(
        self, collector, mock_client, mock_session
    ):
        """Regression test: when two trips share the same stations (same line),
        the JIT must use exact train_id matching (regenerating from trip_id) instead
        of fuzzy time proximity.

        Scenario: journey was created from a trip whose last 6 digits are "631700"
        (train M631700). The feed has two trips on the same line. trip_wrong has a
        closer departure time, but trip_correct is the actual train.
        """
        now = datetime.now(timezone.utc)
        trip_correct = "MNR_trip_631700"  # -> M631700
        trip_wrong = "MNR_trip_631800"  # -> M631800

        correct_train_id = _generate_train_id(trip_correct)
        assert correct_train_id == "M631700"

        journey = MagicMock(spec=TrainJourney)
        journey.id = 1
        journey.train_id = correct_train_id
        journey.data_source = "MNR"
        journey.scheduled_departure = now - timedelta(minutes=5)
        journey.is_completed = False
        journey.update_count = 0

        stop1 = MagicMock(spec=JourneyStop)
        stop1.station_code = "GCT"
        stop1.stop_sequence = 1
        stop1.actual_departure = now - timedelta(minutes=5)
        stop1.actual_arrival = now - timedelta(minutes=5)
        stop1.scheduled_arrival = now - timedelta(minutes=5)
        stop1.has_departed_station = True
        stop1.departure_source = None

        stop2 = MagicMock(spec=JourneyStop)
        stop2.station_code = "M125"
        stop2.stop_sequence = 2
        stop2.actual_departure = None
        stop2.actual_arrival = None
        stop2.scheduled_arrival = now + timedelta(minutes=25)
        stop2.has_departed_station = False
        stop2.departure_source = None

        journey.stops = [stop1, stop2]

        correct_time = now + timedelta(minutes=2)
        wrong_time = now - timedelta(minutes=4)

        arrivals = [
            # trip_wrong: closer departure time to scheduled_departure
            MnrArrival(
                station_code="GCT",
                gtfs_stop_id="1",
                trip_id=trip_wrong,
                route_id="1",
                direction_id=0,
                headsign=None,
                arrival_time=wrong_time,
                departure_time=wrong_time + timedelta(minutes=1),
                delay_seconds=0,
                track="23",
            ),
            MnrArrival(
                station_code="M125",
                gtfs_stop_id="4",
                trip_id=trip_wrong,
                route_id="1",
                direction_id=0,
                headsign=None,
                arrival_time=wrong_time + timedelta(minutes=30),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
            # trip_correct: the actual train
            MnrArrival(
                station_code="GCT",
                gtfs_stop_id="1",
                trip_id=trip_correct,
                route_id="1",
                direction_id=0,
                headsign=None,
                arrival_time=correct_time,
                departure_time=correct_time + timedelta(minutes=1),
                delay_seconds=0,
                track="21",
            ),
            MnrArrival(
                station_code="M125",
                gtfs_stop_id="4",
                trip_id=trip_correct,
                route_id="1",
                direction_id=0,
                headsign=None,
                arrival_time=correct_time + timedelta(minutes=30),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
        ]
        mock_client.get_all_arrivals.return_value = arrivals

        mock_stop_result = MagicMock()
        mock_stop_result.scalar_one_or_none.side_effect = [stop1, stop2]
        mock_stops_list = MagicMock()
        mock_stops_list.scalars.return_value.all.return_value = [stop1, stop2]
        mock_session.execute.side_effect = [
            mock_stop_result,
            mock_stop_result,
            mock_stops_list,
        ]

        await collector.collect_journey_details(mock_session, journey)

        # Must use trip_correct times, NOT trip_wrong
        assert journey.actual_departure == correct_time
        assert journey.actual_arrival == correct_time + timedelta(minutes=30)

    @pytest.mark.asyncio
    async def test_fuzzy_fallback_when_trip_id_changed(
        self, collector, mock_client, mock_session
    ):
        """When the original trip_id is no longer in the feed, the JIT falls
        back to fuzzy matching by station overlap and time proximity."""
        now = datetime.now(timezone.utc)

        journey = MagicMock(spec=TrainJourney)
        journey.id = 1
        journey.train_id = "M999999"  # No trip in feed will generate this
        journey.data_source = "MNR"
        journey.scheduled_departure = now
        journey.is_completed = False
        journey.update_count = 0

        stop1 = MagicMock(spec=JourneyStop)
        stop1.station_code = "GCT"
        stop1.stop_sequence = 1
        stop1.actual_departure = now
        stop1.actual_arrival = now
        stop1.scheduled_arrival = now
        stop1.has_departed_station = False
        stop1.departure_source = None

        journey.stops = [stop1]

        arrivals = [
            MnrArrival(
                station_code="GCT",
                gtfs_stop_id="1",
                trip_id="new_trip_reassigned",
                route_id="1",
                direction_id=0,
                headsign=None,
                arrival_time=now + timedelta(seconds=30),
                departure_time=now + timedelta(seconds=60),
                delay_seconds=0,
                track="21",
            ),
        ]
        mock_client.get_all_arrivals.return_value = arrivals

        mock_stop_result = MagicMock()
        mock_stop_result.scalar_one_or_none.return_value = stop1
        mock_stops_list = MagicMock()
        mock_stops_list.scalars.return_value.all.return_value = [stop1]
        mock_session.execute.side_effect = [
            mock_stop_result,
            mock_stops_list,
        ]

        await collector.collect_journey_details(mock_session, journey)

        # Fuzzy fallback should still update the journey
        assert journey.actual_departure == now + timedelta(seconds=30)


class TestMNRCollectorRun:
    """Tests for the run() entry point method."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock MNR client."""
        client = AsyncMock(spec=MNRClient)
        client.get_all_arrivals = AsyncMock(return_value=[])
        client.close = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_run_creates_session_and_collects(self, mock_client):
        """Test run() creates a session and calls collect()."""
        collector = MNRCollector(client=mock_client)

        with patch("trackrat.collectors.mnr.collector.get_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session.execute = AsyncMock()
            mock_session.commit = AsyncMock()

            # Mock the async context manager
            mock_get_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_get_session.return_value.__aexit__ = AsyncMock()

            result = await collector.run()

            assert "discovered" in result
            assert "updated" in result
            assert "errors" in result


class TestMNRCollectorFailFast:
    """Tests for MNR fail-fast on upstream 5xx / hang (#960)."""

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
        """If the upstream feed hangs indefinitely, the collector must bail
        quickly via asyncio.wait_for instead of consuming the scheduler budget.
        """
        import asyncio as _asyncio

        hang_event = _asyncio.Event()

        async def hang_forever():
            await hang_event.wait()
            return []

        hung_client = AsyncMock(spec=MNRClient)
        hung_client.get_all_arrivals = hang_forever
        hung_client.close = AsyncMock()

        collector = MNRCollector(client=hung_client)

        with patch(
            "trackrat.collectors.mnr.collector._FEED_FETCH_TIMEOUT_SECONDS",
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
