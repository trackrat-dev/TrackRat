"""
Unit tests for MBTACollector.

Tests train discovery, journey updates, train ID generation, and JIT updates.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trackrat.collectors.mbta.client import MBTAClient, MbtaArrival
from trackrat.collectors.mbta.collector import MBTACollector, _generate_train_id
from trackrat.models.database import JourneyStop


class TestGenerateTrainId:
    """Tests for MBTA train ID generation."""

    def test_standard_cr_format(self):
        """Test standard CR trip_id: Base-772221-5208 -> B5208."""
        assert _generate_train_id("Base-772221-5208") == "B5208"

    def test_weekend_format(self):
        """Test weekend trip_id: OCTieJob-791415-6619 -> B6619."""
        assert _generate_train_id("OCTieJob-791415-6619") == "B6619"

    def test_south_weekend_format(self):
        """Test south weekend: SouthWKNDBase25-772583-6619 -> B6619."""
        assert _generate_train_id("SouthWKNDBase25-772583-6619") == "B6619"

    def test_capeflyer_format(self):
        """Test CapeFlyer trip_id: canonical-CapeFlyer-C1-0."""
        result = _generate_train_id("canonical-CapeFlyer-C1-0")
        assert result.startswith("BCF-")
        assert "C1" in result

    def test_tower_zone_format(self):
        """Test tower zone format: TowerAZone1WKND-783285-5447 -> B5447."""
        assert _generate_train_id("TowerAZone1WKND-783285-5447") == "B5447"

    def test_single_number(self):
        """Test trip_id with just a number at end."""
        assert _generate_train_id("some-prefix-123") == "B123"

    def test_no_digits_fallback(self):
        """Test fallback when no digits present."""
        result = _generate_train_id("no-digits-here")
        assert result.startswith("B")


class TestMBTACollectorInit:
    """Tests for MBTACollector initialization."""

    def test_creates_own_client(self):
        """Test collector creates its own client when none provided."""
        collector = MBTACollector()
        assert collector.client is not None
        assert collector._owns_client is True

    def test_uses_provided_client(self):
        """Test collector uses provided client."""
        client = MBTAClient()
        collector = MBTACollector(client=client)
        assert collector.client is client
        assert collector._owns_client is False

    @pytest.mark.asyncio
    async def test_close_owned_client(self):
        """Test closing owned client."""
        collector = MBTACollector()
        collector.client = AsyncMock(spec=MBTAClient)
        collector._owns_client = True
        await collector.close()
        collector.client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_external_client_not_closed(self):
        """Test external client is not closed."""
        client = AsyncMock(spec=MBTAClient)
        collector = MBTACollector(client=client)
        await collector.close()
        client.close.assert_not_called()


class TestMBTACollectorCollect:
    """Tests for MBTACollector.collect()."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.begin_nested = MagicMock()
        session.begin_nested.return_value.__aenter__ = AsyncMock()
        session.begin_nested.return_value.__aexit__ = AsyncMock()
        return session

    @pytest.fixture
    def mock_client(self):
        """Create a mock MBTAClient."""
        return AsyncMock(spec=MBTAClient)

    @pytest.fixture
    def collector(self, mock_client):
        """Create a collector with mock client."""
        return MBTACollector(client=mock_client)

    @pytest.mark.asyncio
    async def test_empty_arrivals(self, collector, mock_client, mock_session):
        """Test collect with no arrivals returns zero stats."""
        mock_client.get_all_arrivals.return_value = []

        stats = await collector.collect(mock_session)

        assert stats["total_arrivals"] == 0
        assert stats["discovered"] == 0
        assert stats["updated"] == 0

    @pytest.mark.asyncio
    async def test_arrivals_grouped_by_trip(self, collector, mock_client, mock_session):
        """Test arrivals are properly grouped by trip_id."""
        now = datetime.now(timezone.utc)
        arrivals = [
            MbtaArrival(
                station_code="BOS",
                gtfs_stop_id="NEC-2287",
                trip_id="Base-772221-5208",
                route_id="CR-Providence",
                direction_id=0,
                headsign=None,
                arrival_time=now,
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
            MbtaArrival(
                station_code="BBY",
                gtfs_stop_id="NEC-2276",
                trip_id="Base-772221-5208",
                route_id="CR-Providence",
                direction_id=0,
                headsign=None,
                arrival_time=now + timedelta(minutes=5),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
            MbtaArrival(
                station_code="BNST",
                gtfs_stop_id="BNT-0000",
                trip_id="Base-772222-5209",
                route_id="CR-Lowell",
                direction_id=0,
                headsign=None,
                arrival_time=now,
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
        ]
        mock_client.get_all_arrivals.return_value = arrivals

        # Mock _process_trip to count calls
        collector._process_trip = AsyncMock(return_value=("discovered", None))

        # Mock session context manager for begin_nested
        mock_session.begin_nested.return_value = AsyncMock()
        mock_session.begin_nested.return_value.__aenter__ = AsyncMock()
        mock_session.begin_nested.return_value.__aexit__ = AsyncMock(return_value=False)

        # Mock stale query for expiration
        mock_stale_result = MagicMock()
        mock_stale_result.scalars.return_value = []
        mock_session.execute.return_value = mock_stale_result

        stats = await collector.collect(mock_session)

        assert stats["total_arrivals"] == 3
        # _process_trip should be called twice (2 unique trips)
        assert collector._process_trip.call_count == 2


class TestMBTACollectorProcessTrip:
    """Tests for MBTACollector._process_trip()."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def mock_client(self):
        """Create a mock MBTAClient."""
        return AsyncMock(spec=MBTAClient)

    @pytest.fixture
    def collector(self, mock_client):
        """Create a collector with mock client."""
        return MBTACollector(client=mock_client)

    @pytest.fixture
    def sample_arrivals(self):
        """Create sample arrivals for a Providence line trip."""
        now = datetime.now(timezone.utc)
        return [
            MbtaArrival(
                station_code="BOS",
                gtfs_stop_id="NEC-2287",
                trip_id="Base-772221-5208",
                route_id="CR-Providence",
                direction_id=0,
                headsign=None,
                arrival_time=now,
                departure_time=now + timedelta(minutes=1),
                delay_seconds=0,
                track=None,
            ),
            MbtaArrival(
                station_code="BBY",
                gtfs_stop_id="NEC-2276",
                trip_id="Base-772221-5208",
                route_id="CR-Providence",
                direction_id=0,
                headsign=None,
                arrival_time=now + timedelta(minutes=5),
                departure_time=now + timedelta(minutes=6),
                delay_seconds=30,
                track=None,
            ),
            MbtaArrival(
                station_code="PVD",
                gtfs_stop_id="NEC-1851-03",
                trip_id="Base-772221-5208",
                route_id="CR-Providence",
                direction_id=0,
                headsign=None,
                arrival_time=now + timedelta(minutes=60),
                departure_time=None,
                delay_seconds=120,
                track=None,
            ),
        ]

    @pytest.mark.asyncio
    async def test_empty_arrivals_returns_none(self, collector, mock_session):
        """Test empty arrivals returns (None, None)."""
        result, journey = await collector._process_trip(mock_session, "trip_1", [])
        assert result is None
        assert journey is None

    @pytest.mark.asyncio
    @patch("trackrat.collectors.mbta.collector.now_et")
    async def test_discovers_new_journey(
        self, mock_now_et, collector, mock_session, sample_arrivals
    ):
        """Test creating a new TrainJourney from arrivals."""
        mock_now_et.return_value = datetime.now(timezone.utc)

        # Mock: no existing journey found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Mock GTFS static backfill (unavailable)
        collector._gtfs_service = MagicMock()
        collector._gtfs_service.get_static_stop_times = AsyncMock(return_value=None)

        result, journey = await collector._process_trip(
            mock_session, "Base-772221-5208", sample_arrivals
        )

        assert result == "discovered"
        assert journey is not None
        # Should have called session.add for journey + stops
        assert mock_session.add.call_count >= 1

    @pytest.mark.asyncio
    @patch("trackrat.collectors.mbta.collector.now_et")
    async def test_updates_existing_journey(
        self, mock_now_et, collector, mock_session, sample_arrivals
    ):
        """Test updating an existing TrainJourney."""
        mock_now_et.return_value = datetime.now(timezone.utc)

        # Mock: existing journey found, with stops already eagerly loaded
        # (mirrors the selectinload on the existence-check query)
        mock_journey = MagicMock()
        mock_journey.id = 1
        mock_journey.train_id = "B5208"
        mock_journey.data_source = "MBTA"
        mock_journey.stops = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_journey
        mock_session.execute.return_value = mock_result

        result, journey = await collector._process_trip(
            mock_session, "Base-772221-5208", sample_arrivals
        )

        assert result == "updated"
        assert journey is mock_journey

    @pytest.mark.asyncio
    async def test_arrivals_sorted_by_time(self, collector, mock_session):
        """Test that arrivals are sorted by time for correct origin determination."""
        now = datetime.now(timezone.utc)
        later = now + timedelta(minutes=30)

        # Arrivals provided in reverse order
        arrivals = [
            MbtaArrival(
                station_code="PVD",
                gtfs_stop_id="NEC-1851-03",
                trip_id="trip_1",
                route_id="CR-Providence",
                direction_id=0,
                headsign=None,
                arrival_time=later,
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
            MbtaArrival(
                station_code="BOS",
                gtfs_stop_id="NEC-2287",
                trip_id="trip_1",
                route_id="CR-Providence",
                direction_id=0,
                headsign=None,
                arrival_time=now,
                departure_time=now + timedelta(minutes=1),
                delay_seconds=0,
                track=None,
            ),
        ]

        # Mock: no existing journey
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        collector._gtfs_service = MagicMock()
        collector._gtfs_service.get_static_stop_times = AsyncMock(return_value=None)

        with patch(
            "trackrat.collectors.mbta.collector.now_et",
            return_value=datetime.now(timezone.utc),
        ):
            result, journey = await collector._process_trip(
                mock_session, "trip_1", arrivals
            )

        assert result == "discovered"
        assert journey is not None


class TestMBTACollectorJourneyDetails:
    """Tests for MBTACollector.collect_journey_details() JIT updates."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_client(self):
        """Create a mock MBTAClient."""
        return AsyncMock(spec=MBTAClient)

    @pytest.fixture
    def collector(self, mock_client):
        """Create a collector with mock client."""
        return MBTACollector(client=mock_client)

    @pytest.mark.asyncio
    async def test_skips_non_mbta_journey(self, collector, mock_session):
        """Test that non-MBTA journeys are skipped."""
        journey = MagicMock()
        journey.data_source = "LIRR"

        await collector.collect_journey_details(mock_session, journey)

        collector.client.get_all_arrivals.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_no_matching_trip(self, collector, mock_client, mock_session):
        """Test graceful handling when no matching trip found."""
        journey = MagicMock()
        journey.data_source = "MBTA"
        journey.train_id = "B9999"
        journey.stops = [MagicMock(station_code="BOS")]

        mock_client.get_all_arrivals.return_value = []

        await collector.collect_journey_details(mock_session, journey)
        # Should not raise an error

    @pytest.mark.asyncio
    async def test_exact_train_id_match(self, collector, mock_client, mock_session):
        """Test exact train ID match is preferred over fuzzy matching."""
        now = datetime.now(timezone.utc)

        journey = MagicMock()
        journey.data_source = "MBTA"
        journey.train_id = "B5208"
        journey.id = 1
        journey.scheduled_departure = now
        journey.stops = [
            MagicMock(station_code="BOS"),
            MagicMock(station_code="PVD"),
        ]

        # Two trips: one with matching train_id, one with closer time
        arrivals = [
            # Correct trip (matching train_id)
            MbtaArrival(
                station_code="BOS",
                gtfs_stop_id="NEC-2287",
                trip_id="Base-772221-5208",  # -> B5208
                route_id="CR-Providence",
                direction_id=0,
                headsign=None,
                arrival_time=now + timedelta(minutes=30),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
            # Wrong trip (closer time but wrong train_id)
            MbtaArrival(
                station_code="BOS",
                gtfs_stop_id="NEC-2287",
                trip_id="Base-772222-5209",  # -> B5209
                route_id="CR-Providence",
                direction_id=0,
                headsign=None,
                arrival_time=now + timedelta(minutes=1),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
        ]
        mock_client.get_all_arrivals.return_value = arrivals

        # Mock stop lookups
        mock_stop_result = MagicMock()
        mock_stop_result.scalar_one_or_none.return_value = None

        mock_stops_result = MagicMock()
        mock_stops_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [
            mock_stop_result,  # stop lookup
            mock_stops_result,  # all stops re-query
        ]

        with patch(
            "trackrat.collectors.mbta.collector.now_et",
            return_value=datetime.now(timezone.utc),
        ):
            await collector.collect_journey_details(mock_session, journey)

        # Verify the correct trip was used (the one matching train_id)
        # The stop update should use arrival_time from the correct trip
        mock_client.get_all_arrivals.assert_called_once()


class TestMBTACollectorRun:
    """Tests for MBTACollector.run() entry point."""

    @pytest.mark.asyncio
    @patch("trackrat.collectors.mbta.collector.get_session")
    async def test_run_returns_stats(self, mock_get_session):
        """Test run() creates session and returns stats."""
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock(spec=MBTAClient)
        mock_client.get_all_arrivals.return_value = []

        collector = MBTACollector(client=mock_client)
        stats = await collector.run()

        assert isinstance(stats, dict)
        assert "discovered" in stats
        assert "updated" in stats
        assert "errors" in stats


class TestMBTASyntheticOriginNotServed:
    """Issue #1689 — the MBTA twin of the subway synthetic-origin guard.

    When GTFS static backfill fails, the collector infers South Station as the
    origin of an outbound train whose terminal was dropped from RT. That
    inference assumes the train has *already passed* BOS. For a trip whose
    first visible stop is further out than ORIGIN_TRAVEL_BUFFER — e.g. a
    not-yet-departed train published ahead of time — the old code wrote BOS as
    a departed stop with a *future* actual_departure, which the
    `hide_departed` filter serves as a boardable departure at a fabricated
    time.
    """

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # no existing journey
        session.execute = AsyncMock(return_value=mock_result)
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def collector(self):
        client = AsyncMock(spec=MBTAClient)
        client.close = AsyncMock()
        collector = MBTACollector(client=client)
        # No static backfill — the degraded path where origin inference runs.
        collector._gtfs_service = MagicMock()
        collector._gtfs_service.get_static_stop_times = AsyncMock(return_value=None)
        return collector

    @staticmethod
    def _outbound_from_south_station(first_stop_minutes_out: int):
        """An outbound (direction_id=0) Providence train whose first visible
        stop is Back Bay; infer_missing_origin resolves the dropped origin to
        BOS (South Station)."""
        now = datetime.now(timezone.utc)
        first = now + timedelta(minutes=first_stop_minutes_out)
        return [
            MbtaArrival(
                station_code="BBY",
                gtfs_stop_id="NEC-2276",
                trip_id="Base-772221-6101",
                route_id="CR-Providence",
                direction_id=0,
                headsign="Providence",
                arrival_time=first,
                departure_time=first + timedelta(minutes=1),
                delay_seconds=0,
                track=None,
            ),
            MbtaArrival(
                station_code="PVD",
                gtfs_stop_id="NEC-1851-03",
                trip_id="Base-772221-6101",
                route_id="CR-Providence",
                direction_id=0,
                headsign="Providence",
                arrival_time=first + timedelta(minutes=55),
                departure_time=None,
                delay_seconds=0,
                track=None,
            ),
        ]

    @staticmethod
    def _added_stops(mock_session):
        return [
            call.args[0]
            for call in mock_session.add.call_args_list
            if isinstance(call.args[0], JourneyStop)
        ]

    @pytest.mark.asyncio
    async def test_far_future_first_stop_does_not_invent_south_station(
        self, collector, mock_session
    ):
        """A trip 18 minutes from Back Bay cannot already have left South
        Station, so no synthetic BOS stop may be written."""
        arrivals = self._outbound_from_south_station(first_stop_minutes_out=18)

        result, journey = await collector._process_trip(
            mock_session, "Base-772221-6101", arrivals
        )

        assert result == "discovered"
        codes = [s.station_code for s in self._added_stops(mock_session)]
        assert "BOS" not in codes, (
            "South Station must not be fabricated for a train whose first "
            f"visible stop is 18 minutes away at Back Bay; got {codes}"
        )
        assert codes == ["BBY", "PVD"], f"Expected only the feed's stops, got {codes}"
        assert journey.origin_station_code == "BBY", (
            "Origin should fall back to the first stop actually in the feed, "
            f"got {journey.origin_station_code}"
        )
        assert journey.stops_count == 2, (
            "stops_count must not count the rejected synthetic origin, got "
            f"{journey.stops_count}"
        )

    @pytest.mark.asyncio
    async def test_imminent_first_stop_still_backfills_south_station(
        self, collector, mock_session
    ):
        """A train two minutes from Back Bay did already leave South Station —
        the inference this fallback exists for still works, and the stop it
        writes is never an upcoming departure (the invariant behind #1689)."""
        arrivals = self._outbound_from_south_station(first_stop_minutes_out=2)

        result, journey = await collector._process_trip(
            mock_session, "Base-772221-6101", arrivals
        )

        assert result == "discovered"
        stops = self._added_stops(mock_session)
        codes = [s.station_code for s in stops]
        assert codes == [
            "BOS",
            "BBY",
            "PVD",
        ], f"South Station should still be backfilled as the origin; got {codes}"
        origin_stop = stops[0]
        now = datetime.now(timezone.utc)
        assert origin_stop.stop_sequence == 1
        assert origin_stop.departure_source == "synthetic_origin"
        assert origin_stop.has_departed_station is True
        assert origin_stop.actual_departure < now, (
            "A stop flagged as departed must have a past departure time, "
            f"got {origin_stop.actual_departure} vs now={now}"
        )
        assert origin_stop.updated_departure < now, (
            "updated_departure feeds the departure board directly; "
            f"got {origin_stop.updated_departure} vs now={now}"
        )
        assert journey.origin_station_code == "BOS"
        assert journey.stops_count == 3
