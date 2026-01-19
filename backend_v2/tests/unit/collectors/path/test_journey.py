"""
Unit tests for PathJourneyCollector.

Tests real-time journey updates from the RidePATH API.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trackrat.collectors.path.journey import (
    PathJourneyCollector,
    normalize_headsign,
)
from trackrat.collectors.path.ridepath_client import PathArrival
from trackrat.models.database import JourneyStop, TrainJourney


class TestNormalizeHeadsign:
    """Tests for headsign normalization."""

    def test_world_trade_center_variations(self):
        """Test WTC headsign normalization."""
        assert normalize_headsign("World Trade Center") == "world_trade_center"
        assert normalize_headsign("world trade center") == "world_trade_center"
        assert normalize_headsign("WTC") == "world_trade_center"
        assert normalize_headsign("wtc") == "world_trade_center"

    def test_33rd_street_variations(self):
        """Test 33rd Street headsign normalization."""
        assert normalize_headsign("33rd Street") == "33rd_street"
        assert normalize_headsign("33rd Street via Hoboken") == "33rd_street"
        assert normalize_headsign("33 St") == "33rd_street"

    def test_terminal_stations(self):
        """Test terminal station headsign normalization."""
        assert normalize_headsign("Hoboken") == "hoboken"
        assert normalize_headsign("Newark") == "newark"
        assert normalize_headsign("Journal Square") == "journal_square"

    def test_empty_headsign(self):
        """Test empty headsign handling."""
        assert normalize_headsign("") == ""
        assert normalize_headsign(None) == ""

    def test_unknown_headsign(self):
        """Test unknown headsign passes through normalized."""
        assert normalize_headsign("Some Unknown Destination") == "some_unknown_destination"


class TestPathJourneyCollector:
    """Tests for PathJourneyCollector."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock RidePathClient."""
        client = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def collector(self, mock_client):
        """Create a PathJourneyCollector with mock client."""
        return PathJourneyCollector(client=mock_client)

    @pytest.fixture
    def sample_journey(self):
        """Create a sample TrainJourney."""
        journey = MagicMock(spec=TrainJourney)
        journey.id = 1
        journey.train_id = "PATH_862_abc123"
        journey.destination = "World Trade Center"
        journey.data_source = "PATH"
        journey.journey_date = datetime.now().date()
        journey.is_completed = False
        journey.is_cancelled = False
        journey.is_expired = False
        journey.api_error_count = 0
        journey.update_count = 0
        journey.last_updated_at = None
        journey.stops_count = 5
        return journey

    @pytest.fixture
    def sample_stops(self):
        """Create sample JourneyStops for a NWK-WTC journey."""
        stops = []
        stations = [
            ("PNK", "Newark", 1),
            ("PHR", "Harrison", 2),
            ("PJS", "Journal Square", 3),
            ("PGR", "Grove Street", 4),
            ("PEX", "Exchange Place", 5),
            ("PWC", "World Trade Center", 6),
        ]

        base_time = datetime.now()
        for code, name, seq in stations:
            stop = MagicMock(spec=JourneyStop)
            stop.station_code = code
            stop.station_name = name
            stop.stop_sequence = seq
            stop.scheduled_arrival = base_time + timedelta(minutes=seq * 3)
            stop.scheduled_departure = base_time + timedelta(minutes=seq * 3 + 1)
            stop.actual_arrival = None
            stop.actual_departure = None
            stop.updated_arrival = None
            stop.updated_departure = None
            stop.has_departed_station = False
            stop.departure_source = None
            stop.updated_at = None
            stops.append(stop)

        return stops

    @pytest.fixture
    def sample_arrivals(self):
        """Create sample PathArrivals for a WTC-bound train."""
        now = datetime.now()
        return [
            PathArrival(
                station_code="PJS",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=4,
                arrival_time=now + timedelta(minutes=4),
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PGR",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=7,
                arrival_time=now + timedelta(minutes=7),
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PEX",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=9,
                arrival_time=now + timedelta(minutes=9),
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PWC",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=12,
                arrival_time=now + timedelta(minutes=12),
                line_color="D93A30",
                last_updated=now,
            ),
        ]

    @pytest.mark.asyncio
    async def test_collect_journey_details_updates_stops(
        self, collector, mock_client, sample_journey, sample_stops, sample_arrivals
    ):
        """Test that collect_journey_details updates stop arrival times."""
        mock_client.get_all_arrivals.return_value = sample_arrivals

        # Mock scalars result - scalars() is awaited, then .all() is called sync
        mock_scalars_result = MagicMock()
        mock_scalars_result.all.return_value = sample_stops

        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)
        mock_session.flush = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.add = MagicMock()

        # Create mock TransitAnalyzer with async methods
        mock_analyzer_instance = MagicMock()
        mock_analyzer_instance.analyze_new_segments = AsyncMock(return_value=0)
        mock_analyzer_instance.analyze_journey = AsyncMock()

        with patch("trackrat.collectors.path.journey.now_et") as mock_now:
            mock_now.return_value = datetime.now()
            with patch("trackrat.collectors.path.journey.TransitAnalyzer", return_value=mock_analyzer_instance):
                await collector.collect_journey_details(mock_session, sample_journey)

        # Verify arrivals were fetched
        mock_client.get_all_arrivals.assert_called_once()

        # Verify journey was updated
        assert sample_journey.update_count == 1
        assert sample_journey.api_error_count == 0

    @pytest.mark.asyncio
    async def test_collect_journey_details_skips_completed(
        self, collector, mock_client, sample_journey
    ):
        """Test that completed journeys are skipped."""
        sample_journey.is_completed = True

        mock_session = AsyncMock()

        await collector.collect_journey_details(mock_session, sample_journey)

        # Should not fetch arrivals for completed journey
        mock_client.get_all_arrivals.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_journey_details_skips_cancelled(
        self, collector, mock_client, sample_journey
    ):
        """Test that cancelled journeys are skipped."""
        sample_journey.is_cancelled = True

        mock_session = AsyncMock()

        await collector.collect_journey_details(mock_session, sample_journey)

        # Should not fetch arrivals for cancelled journey
        mock_client.get_all_arrivals.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_journey_details_skips_expired(
        self, collector, mock_client, sample_journey
    ):
        """Test that expired journeys are skipped."""
        sample_journey.is_expired = True

        mock_session = AsyncMock()

        await collector.collect_journey_details(mock_session, sample_journey)

        # Should not fetch arrivals for expired journey
        mock_client.get_all_arrivals.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_journey_details_handles_api_error(
        self, collector, mock_client, sample_journey, sample_stops
    ):
        """Test API error handling increments error count."""
        mock_client.get_all_arrivals.side_effect = Exception("API Error")

        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()

        await collector.collect_journey_details(mock_session, sample_journey)

        assert sample_journey.api_error_count == 1
        assert not sample_journey.is_expired

    @pytest.mark.asyncio
    async def test_collect_journey_details_marks_expired_after_errors(
        self, collector, mock_client, sample_journey, sample_stops
    ):
        """Test journey is marked expired after 2 API errors."""
        sample_journey.api_error_count = 1  # Already had one error
        mock_client.get_all_arrivals.side_effect = Exception("API Error")

        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()

        await collector.collect_journey_details(mock_session, sample_journey)

        assert sample_journey.api_error_count == 2
        assert sample_journey.is_expired

    @pytest.mark.asyncio
    async def test_collect_active_journeys_batch_update(
        self, collector, mock_client, sample_arrivals
    ):
        """Test batch update of multiple journeys."""
        mock_client.get_all_arrivals.return_value = sample_arrivals

        # Create mock journeys
        journey1 = MagicMock(spec=TrainJourney)
        journey1.id = 1
        journey1.train_id = "PATH_862_abc"
        journey1.destination = "World Trade Center"
        journey1.is_completed = False
        journey1.is_cancelled = False
        journey1.update_count = 0
        journey1.api_error_count = 0

        journey2 = MagicMock(spec=TrainJourney)
        journey2.id = 2
        journey2.train_id = "PATH_862_def"
        journey2.destination = "Newark"
        journey2.is_completed = False
        journey2.is_cancelled = False
        journey2.update_count = 0
        journey2.api_error_count = 0

        # Create mock scalars results for multiple calls
        mock_journeys_result = MagicMock()
        mock_journeys_result.all.return_value = [journey1, journey2]

        mock_stops_result = MagicMock()
        mock_stops_result.all.return_value = []

        mock_session = AsyncMock()
        # First call returns journeys, subsequent calls return empty stops
        mock_session.scalars = AsyncMock(
            side_effect=[mock_journeys_result, mock_stops_result, mock_stops_result]
        )
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.add = MagicMock()

        # Create a mock datetime that supports .date()
        mock_datetime = MagicMock()
        mock_datetime.date.return_value = datetime.now().date()

        with patch("trackrat.collectors.path.journey.now_et") as mock_now:
            mock_now.return_value = mock_datetime
            with patch("trackrat.collectors.path.journey.TransitAnalyzer"):
                result = await collector.collect_active_journeys(mock_session)

        assert result["data_source"] == "PATH"
        assert result["journeys_processed"] == 2
        assert result["arrivals_fetched"] == len(sample_arrivals)

    @pytest.mark.asyncio
    async def test_collect_active_journeys_no_active(self, collector, mock_client):
        """Test batch update with no active journeys."""
        # Mock scalars result
        mock_scalars_result = MagicMock()
        mock_scalars_result.all.return_value = []

        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

        # Create a mock datetime that supports .date()
        mock_datetime = MagicMock()
        mock_datetime.date.return_value = datetime.now().date()

        with patch("trackrat.collectors.path.journey.now_et") as mock_now:
            mock_now.return_value = mock_datetime
            result = await collector.collect_active_journeys(mock_session)

        assert result["journeys_processed"] == 0
        mock_client.get_all_arrivals.assert_not_called()

    @pytest.mark.asyncio
    async def test_close(self, collector, mock_client):
        """Test that close calls client close."""
        collector._owns_client = True
        await collector.close()
        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_not_owned(self, collector, mock_client):
        """Test that close doesn't close externally provided client."""
        collector._owns_client = False
        await collector.close()
        mock_client.close.assert_not_called()


class TestStopUpdateLogic:
    """Tests for stop update logic and arrival matching."""

    @pytest.fixture
    def collector(self):
        """Create collector with mock client."""
        mock_client = AsyncMock()
        return PathJourneyCollector(client=mock_client)

    def test_find_best_matching_arrival_with_scheduled_time(self, collector):
        """Test that arrival closest to scheduled time is selected."""
        now = datetime.now()
        scheduled_arrival = now + timedelta(minutes=8)

        arrivals = [
            PathArrival(
                station_code="PJS",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=5,  # Sooner but further from scheduled
                arrival_time=now + timedelta(minutes=5),
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PJS",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=9,  # Closer to scheduled (8 min)
                arrival_time=now + timedelta(minutes=9),
                line_color="D93A30",
                last_updated=now,
            ),
        ]

        # Create mock stop with scheduled arrival
        stop = MagicMock(spec=JourneyStop)
        stop.scheduled_arrival = scheduled_arrival
        stop.station_code = "PJS"

        # Should select the 9-min arrival (closer to 8-min scheduled)
        result = collector._find_best_matching_arrival(stop, arrivals)
        assert result is not None
        assert result.minutes_away == 9

    def test_find_best_matching_arrival_fallback_to_soonest(self, collector):
        """Test fallback to soonest arrival when no scheduled time."""
        now = datetime.now()

        arrivals = [
            PathArrival(
                station_code="PJS",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=10,
                arrival_time=now + timedelta(minutes=10),
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PJS",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=5,  # Soonest
                arrival_time=now + timedelta(minutes=5),
                line_color="D93A30",
                last_updated=now,
            ),
        ]

        # Create mock stop without scheduled arrival
        stop = MagicMock(spec=JourneyStop)
        stop.scheduled_arrival = None
        stop.station_code = "PJS"

        # Should select soonest (5 min)
        result = collector._find_best_matching_arrival(stop, arrivals)
        assert result is not None
        assert result.minutes_away == 5

    def test_find_best_matching_arrival_outside_tolerance(self, collector):
        """Test fallback when scheduled time match is outside tolerance."""
        now = datetime.now()
        scheduled_arrival = now + timedelta(minutes=30)  # Far from any arrival

        arrivals = [
            PathArrival(
                station_code="PJS",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=5,
                arrival_time=now + timedelta(minutes=5),
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PJS",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=10,
                arrival_time=now + timedelta(minutes=10),
                line_color="D93A30",
                last_updated=now,
            ),
        ]

        # Create mock stop with scheduled time far from all arrivals
        stop = MagicMock(spec=JourneyStop)
        stop.scheduled_arrival = scheduled_arrival
        stop.station_code = "PJS"

        # Both arrivals are >10 min from scheduled, so fallback to soonest
        result = collector._find_best_matching_arrival(stop, arrivals)
        assert result is not None
        assert result.minutes_away == 5

    def test_find_best_matching_arrival_no_arrivals(self, collector):
        """Test returns None when no arrivals at station."""
        stop = MagicMock(spec=JourneyStop)
        stop.scheduled_arrival = datetime.now()
        stop.station_code = "PJS"

        result = collector._find_best_matching_arrival(stop, [])
        assert result is None

    def test_multiple_trains_same_destination_matched_correctly(self, collector):
        """Test that two trains to same destination get different arrivals."""
        now = datetime.now()

        # Train A scheduled at 8 min, Train B scheduled at 15 min
        arrivals = [
            PathArrival(
                station_code="PJS",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=7,  # Close to Train A's schedule
                arrival_time=now + timedelta(minutes=7),
                line_color="D93A30",
                last_updated=now,
            ),
            PathArrival(
                station_code="PJS",
                headsign="World Trade Center",
                direction="ToNY",
                minutes_away=14,  # Close to Train B's schedule
                arrival_time=now + timedelta(minutes=14),
                line_color="D93A30",
                last_updated=now,
            ),
        ]

        # Train A stop - scheduled at 8 min
        stop_a = MagicMock(spec=JourneyStop)
        stop_a.scheduled_arrival = now + timedelta(minutes=8)
        stop_a.station_code = "PJS"

        # Train B stop - scheduled at 15 min
        stop_b = MagicMock(spec=JourneyStop)
        stop_b.scheduled_arrival = now + timedelta(minutes=15)
        stop_b.station_code = "PJS"

        # Train A should match to 7-min arrival (closest to 8)
        result_a = collector._find_best_matching_arrival(stop_a, arrivals)
        assert result_a is not None
        assert result_a.minutes_away == 7

        # Train B should match to 14-min arrival (closest to 15)
        result_b = collector._find_best_matching_arrival(stop_b, arrivals)
        assert result_b is not None
        assert result_b.minutes_away == 14
