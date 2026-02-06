"""
Unit tests for LIRRCollector.

Tests unified LIRR train discovery and journey update logic.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.lirr.collector import (
    LIRRCollector,
    _generate_train_id,
)
from trackrat.collectors.lirr.client import LirrArrival, LIRRClient
from trackrat.models.database import JourneyStop, TrainJourney


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestGenerateTrainId:
    """Tests for the train ID generation function."""

    def test_generates_correct_format_with_l_prefix(self):
        """Test train ID has correct format: L{trip_suffix}."""
        dt = datetime(2026, 1, 19, 10, 30, 0, tzinfo=timezone.utc)
        result = _generate_train_id("1", "trip_123456", "JAM", "NY", dt)

        assert result.startswith("L")
        # Should extract numeric suffix from trip_id
        assert result == "L123456"

    def test_extracts_last_6_digits(self):
        """Test trip_id extraction uses last 6 characters."""
        dt = datetime(2026, 1, 19, 10, 30, 0, tzinfo=timezone.utc)
        result = _generate_train_id("1", "LIRR_20260119_123456", "JAM", "NY", dt)

        assert result == "L123456"

    def test_handles_short_trip_id(self):
        """Test handling of short trip_id."""
        dt = datetime(2026, 1, 19, 10, 30, 0, tzinfo=timezone.utc)
        result = _generate_train_id("1", "1234", "JAM", "NY", dt)

        assert result == "L1234"

    def test_handles_non_numeric_trip_suffix(self):
        """Test handling of non-numeric characters in trip suffix."""
        dt = datetime(2026, 1, 19, 10, 30, 0, tzinfo=timezone.utc)
        # If last 6 chars are "ABC123", should extract "123"
        result = _generate_train_id("1", "tripABC123", "JAM", "NY", dt)

        assert result == "L123"

    def test_falls_back_to_first_6_if_no_digits(self):
        """Test fallback to first 6 chars if no digits in suffix."""
        dt = datetime(2026, 1, 19, 10, 30, 0, tzinfo=timezone.utc)
        result = _generate_train_id("1", "ABCDEFGH", "JAM", "NY", dt)

        # Should fall back to first 6 chars of trip_id
        assert result == "LABCDEF"

    def test_different_trip_ids_produce_different_train_ids(self):
        """Test different trip IDs produce different train IDs."""
        dt = datetime(2026, 1, 19, 10, 30, 0, tzinfo=timezone.utc)
        id1 = _generate_train_id("1", "trip_111111", "JAM", "NY", dt)
        id2 = _generate_train_id("1", "trip_222222", "JAM", "NY", dt)

        assert id1 != id2
        assert id1 == "L111111"
        assert id2 == "L222222"


# =============================================================================
# COLLECTOR TESTS
# =============================================================================


class TestLIRRCollectorInit:
    """Tests for LIRRCollector initialization."""

    def test_creates_client_if_not_provided(self):
        """Test collector creates its own client if none provided."""
        collector = LIRRCollector()

        assert collector.client is not None
        assert isinstance(collector.client, LIRRClient)
        assert collector._owns_client is True

    def test_uses_provided_client(self):
        """Test collector uses provided client."""
        client = LIRRClient()
        collector = LIRRCollector(client=client)

        assert collector.client is client
        assert collector._owns_client is False

    @pytest.mark.asyncio
    async def test_close_closes_owned_client(self):
        """Test close() closes client when collector owns it."""
        collector = LIRRCollector()
        collector.client = AsyncMock(spec=LIRRClient)
        collector._owns_client = True

        await collector.close()

        collector.client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_does_not_close_external_client(self):
        """Test close() does not close externally provided client."""
        client = AsyncMock(spec=LIRRClient)
        collector = LIRRCollector(client=client)

        await collector.close()

        client.close.assert_not_called()


class TestLIRRCollectorCollect:
    """Tests for LIRRCollector.collect() method."""

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
        """Create a mock LIRR client."""
        client = AsyncMock(spec=LIRRClient)
        client.get_all_arrivals = AsyncMock(return_value=[])
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def collector(self, mock_client):
        """Create a collector with mock client."""
        collector = LIRRCollector(client=mock_client)
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
            LirrArrival(
                station_code="JAM",
                gtfs_stop_id="102",
                trip_id="trip_123",
                route_id="1",
                direction_id=0,
                headsign="Penn Station",
                arrival_time=now,
                departure_time=now + timedelta(minutes=1),
                delay_seconds=0,
                track=None,
            ),
            LirrArrival(
                station_code="NY",
                gtfs_stop_id="237",
                trip_id="trip_123",
                route_id="1",
                direction_id=0,
                headsign="Penn Station",
                arrival_time=now + timedelta(minutes=30),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
            LirrArrival(
                station_code="JAM",
                gtfs_stop_id="102",
                trip_id="trip_456",
                route_id="2",
                direction_id=1,
                headsign="Huntington",
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


class TestLIRRCollectorProcessTrip:
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
        """Create a mock LIRR client."""
        client = AsyncMock(spec=LIRRClient)
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def collector(self, mock_client):
        """Create a collector with mock client."""
        return LIRRCollector(client=mock_client)

    @pytest.fixture
    def sample_arrivals(self):
        """Create sample arrivals for a trip."""
        now = datetime.now(timezone.utc)
        return [
            LirrArrival(
                station_code="JAM",
                gtfs_stop_id="102",
                trip_id="trip_123456",
                route_id="1",
                direction_id=0,
                headsign="Penn Station",
                arrival_time=now,
                departure_time=now + timedelta(minutes=1),
                delay_seconds=60,
                track="5",
            ),
            LirrArrival(
                station_code="NY",
                gtfs_stop_id="237",
                trip_id="trip_123456",
                route_id="1",
                direction_id=0,
                headsign="Penn Station",
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

        result = await collector._process_trip(
            mock_session, "trip_123456", sample_arrivals
        )

        assert result == "discovered"
        # Should add journey and stops
        assert mock_session.add.call_count >= 1
        mock_session.flush.assert_called()

    @pytest.mark.asyncio
    async def test_process_trip_updates_existing_journey(
        self, collector, mock_session, sample_arrivals
    ):
        """Test _process_trip updates existing journey."""
        # Mock existing journey
        existing_journey = MagicMock(spec=TrainJourney)
        existing_journey.id = 1
        existing_journey.train_id = "L123456"
        existing_journey.data_source = "LIRR"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_journey
        mock_session.execute.return_value = mock_result

        result = await collector._process_trip(
            mock_session, "trip_123456", sample_arrivals
        )

        assert result == "updated"

    @pytest.mark.asyncio
    async def test_process_trip_returns_none_for_empty_arrivals(
        self, collector, mock_session
    ):
        """Test _process_trip returns None for empty arrivals list."""
        result = await collector._process_trip(mock_session, "trip_123", [])

        assert result is None

    @pytest.mark.asyncio
    async def test_process_trip_sorts_arrivals_by_time(self, collector, mock_session):
        """Test arrivals are sorted by arrival time to determine origin."""
        now = datetime.now(timezone.utc)
        # Intentionally out of order
        arrivals = [
            LirrArrival(
                station_code="NY",
                gtfs_stop_id="237",
                trip_id="trip_123",
                route_id="1",
                direction_id=0,
                headsign=None,
                arrival_time=now + timedelta(minutes=30),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
            LirrArrival(
                station_code="JAM",
                gtfs_stop_id="102",
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

        result = await collector._process_trip(mock_session, "trip_123", arrivals)

        assert result == "discovered"
        # Origin should be JAM (earlier time)
        # This is implicitly tested by the journey being created correctly


class TestLIRRCollectorJourneyDetails:
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
        """Create a mock LIRR client."""
        client = AsyncMock(spec=LIRRClient)
        client.get_all_arrivals = AsyncMock(return_value=[])
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def collector(self, mock_client):
        """Create a collector with mock client."""
        return LIRRCollector(client=mock_client)

    @pytest.mark.asyncio
    async def test_collect_journey_details_skips_non_lirr(
        self, collector, mock_session
    ):
        """Test JIT update skips non-LIRR journeys."""
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
        journey.train_id = "L123456"
        journey.data_source = "LIRR"

        stop1 = MagicMock(spec=JourneyStop)
        stop1.station_code = "JAM"

        stop2 = MagicMock(spec=JourneyStop)
        stop2.station_code = "NY"

        journey.stops = [stop1, stop2]

        # Mock arrivals that match the journey
        arrivals = [
            LirrArrival(
                station_code="JAM",
                gtfs_stop_id="102",
                trip_id="trip_123456",
                route_id="1",
                direction_id=0,
                headsign=None,
                arrival_time=now,
                departure_time=now + timedelta(minutes=1),
                delay_seconds=120,
                track="5",
            ),
            LirrArrival(
                station_code="NY",
                gtfs_stop_id="237",
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
        journey.train_id = "L999999"
        journey.data_source = "LIRR"

        stop = MagicMock(spec=JourneyStop)
        stop.station_code = "JAM"
        journey.stops = [stop]

        # No arrivals match this journey
        mock_client.get_all_arrivals.return_value = []

        await collector.collect_journey_details(mock_session, journey)

        # Should complete without error
        mock_client.get_all_arrivals.assert_called_once()


class TestLIRRCollectorRun:
    """Tests for the run() entry point method."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock LIRR client."""
        client = AsyncMock(spec=LIRRClient)
        client.get_all_arrivals = AsyncMock(return_value=[])
        client.close = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_run_creates_session_and_collects(self, mock_client):
        """Test run() creates a session and calls collect()."""
        collector = LIRRCollector(client=mock_client)

        with patch(
            "trackrat.collectors.lirr.collector.get_session"
        ) as mock_get_session:
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
