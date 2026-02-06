"""
Unit tests for the direct arrival forecaster.

Tests the DirectArrivalForecaster which calculates segment times directly
from recent journeys without intermediate storage.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.api import SimpleStationInfo, StopDetails, RawStopStatus
from trackrat.models.database import TrainJourney
from trackrat.services.direct_forecaster import DirectArrivalForecaster
from trackrat.utils.time import now_et


@pytest.fixture
def forecaster():
    """Create a DirectArrivalForecaster instance."""
    return DirectArrivalForecaster()


@pytest.fixture
def mock_journey():
    """Create a mock journey for testing."""
    journey = MagicMock(spec=TrainJourney)
    journey.train_id = "TEST123"
    journey.journey_date = datetime.now().date()
    journey.data_source = "NJT"
    journey.line_code = "NEC"
    return journey


@pytest.fixture
def sample_stops():
    """Create sample stops for testing."""
    base_time = now_et()

    # Create stops with proper StopDetails objects
    stops = [
        StopDetails(
            station=SimpleStationInfo(code="NY", name="New York Penn Station"),
            stop_sequence=0,
            scheduled_departure=base_time - timedelta(minutes=30),
            has_departed_station=True,
            actual_departure=base_time - timedelta(minutes=28),  # 2 min late
            raw_status=RawStopStatus(),
        ),
        StopDetails(
            station=SimpleStationInfo(code="NP", name="Newark Penn Station"),
            stop_sequence=1,
            scheduled_arrival=base_time - timedelta(minutes=20),
            scheduled_departure=base_time - timedelta(minutes=18),
            has_departed_station=True,
            actual_departure=base_time - timedelta(minutes=16),  # 2 min late
            raw_status=RawStopStatus(),
        ),
        StopDetails(
            station=SimpleStationInfo(code="TR", name="Trenton"),
            stop_sequence=2,
            scheduled_arrival=base_time + timedelta(minutes=30),
            scheduled_departure=base_time + timedelta(minutes=32),
            has_departed_station=False,
            raw_status=RawStopStatus(),
        ),
        StopDetails(
            station=SimpleStationInfo(code="PH", name="Philadelphia"),
            stop_sequence=3,
            scheduled_arrival=base_time + timedelta(minutes=60),
            has_departed_station=False,
            raw_status=RawStopStatus(),
        ),
    ]

    return stops


@pytest.fixture
def mock_db_with_segments():
    """Create a mock database session with per-stop row data.

    The batch query in _get_all_segment_transit_times fetches raw per-stop rows
    (journey_id, station_code, stop_sequence, departure_time, arrival_time)
    and computes segment transit times in Python.
    """
    mock_db = AsyncMock(spec=AsyncSession)

    base_time = now_et()

    # Raw per-stop rows: each journey has a departure from NP and arrival at TR.
    # Arrival times must be within LOOKBACK_HOURS (1h) since the batch method
    # applies the cutoff check in Python rather than SQL.
    mock_rows = [
        # Journey 1: NP departure, then TR arrival (45 min transit)
        MagicMock(
            journey_id=1,
            station_code="NP",
            stop_sequence=1,
            departure_time=base_time - timedelta(minutes=55),
            arrival_time=base_time - timedelta(minutes=57),
        ),
        MagicMock(
            journey_id=1,
            station_code="TR",
            stop_sequence=2,
            departure_time=base_time - timedelta(minutes=8),
            arrival_time=base_time - timedelta(minutes=10),
        ),
        # Journey 2: NP departure, then TR arrival (46 min transit)
        MagicMock(
            journey_id=2,
            station_code="NP",
            stop_sequence=1,
            departure_time=base_time - timedelta(minutes=56),
            arrival_time=base_time - timedelta(minutes=58),
        ),
        MagicMock(
            journey_id=2,
            station_code="TR",
            stop_sequence=2,
            departure_time=base_time - timedelta(minutes=8),
            arrival_time=base_time - timedelta(minutes=10),
        ),
        # Journey 3: NP departure, then TR arrival (45 min transit)
        MagicMock(
            journey_id=3,
            station_code="NP",
            stop_sequence=1,
            departure_time=base_time - timedelta(minutes=55),
            arrival_time=base_time - timedelta(minutes=57),
        ),
        MagicMock(
            journey_id=3,
            station_code="TR",
            stop_sequence=2,
            departure_time=base_time - timedelta(minutes=8),
            arrival_time=base_time - timedelta(minutes=10),
        ),
    ]

    mock_db.execute.return_value = mock_rows
    return mock_db


class TestDirectArrivalForecaster:
    """Test class for DirectArrivalForecaster."""

    @pytest.mark.asyncio
    async def test_get_segment_transit_time(self, forecaster, mock_db_with_segments):
        """Test calculating segment transit time from recent journeys."""
        # Calculate transit time for NP->TR segment
        result = await forecaster._get_segment_transit_time(
            mock_db_with_segments, "NP", "TR", "NJT", "NEC"
        )

        assert result is not None
        assert "avg" in result
        assert "samples" in result
        assert result["samples"] == 3  # Should have 3 journey samples
        assert 40 <= result["avg"] <= 50  # Should be around 45 minutes

    @pytest.mark.asyncio
    async def test_insufficient_samples(self, forecaster):
        """Test that insufficient samples returns None."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock empty result (no journeys found)
        mock_db.execute.return_value = []

        result = await forecaster._get_segment_transit_time(
            mock_db, "XX", "YY", "NJT", None
        )

        assert result is None  # Should return None when insufficient samples

    def test_determine_starting_point_with_user_origin(self, forecaster, sample_stops):
        """Test determining starting point with user origin."""
        # User boards at NP
        start_index, start_time = forecaster._determine_starting_point(
            sample_stops, user_origin="NP"
        )

        assert start_index == 1  # Should start from Newark Penn
        assert start_time is not None

    def test_determine_starting_point_with_departed_stops(
        self, forecaster, sample_stops
    ):
        """Test determining starting point based on departed stops."""
        # No user origin, should find last departed stop
        start_index, start_time = forecaster._determine_starting_point(
            sample_stops, user_origin=None
        )

        assert start_index == 1  # NP is the last departed stop
        assert start_time is not None

    def test_determine_starting_point_no_departures(self, forecaster, sample_stops):
        """Test determining starting point when no stops have departed."""
        # Mark all stops as not departed
        for stop in sample_stops:
            stop.has_departed_station = False

        start_index, start_time = forecaster._determine_starting_point(
            sample_stops, user_origin=None
        )

        # With our simplified logic, we return None when no stops have departed
        # and no user origin is specified, since we can't make meaningful predictions
        assert start_index is None
        assert start_time is None

    def test_validate_prediction_time(self, forecaster):
        """Test prediction time validation."""
        stop = MagicMock()
        stop.station = MagicMock()
        stop.station.code = "TR"

        now = now_et()
        stop.scheduled_departure = now + timedelta(minutes=30)

        with patch("trackrat.services.direct_forecaster.now_et", return_value=now):
            # Test future time (valid)
            future_time = now + timedelta(minutes=10)
            validated = forecaster._validate_prediction_time(future_time, stop)
            assert validated == future_time

            # Test slightly stale time (use current time)
            stale_time = now - timedelta(minutes=5)
            validated = forecaster._validate_prediction_time(stale_time, stop)
            assert validated == now  # Should use current time

            # Test very stale time (reset to scheduled)
            very_stale = now - timedelta(minutes=15)
            validated = forecaster._validate_prediction_time(very_stale, stop)
            assert validated == stop.scheduled_departure

    def test_calculate_next_departure(self, forecaster):
        """Test calculating next departure time."""
        stop = MagicMock()
        arrival_time = now_et() + timedelta(minutes=10)

        # Test with scheduled departure after arrival (includes dwell)
        stop.scheduled_departure = now_et() + timedelta(minutes=12)
        departure = forecaster._calculate_next_departure(stop, arrival_time)
        assert departure == stop.scheduled_departure

        # Test with scheduled departure before arrival (use arrival)
        stop.scheduled_departure = now_et() + timedelta(minutes=8)
        departure = forecaster._calculate_next_departure(stop, arrival_time)
        assert departure == arrival_time

    @pytest.mark.asyncio
    async def test_add_predictions_to_stops_integration(
        self, forecaster, mock_journey, sample_stops, mock_db_with_segments
    ):
        """Integration test for adding predictions to stops."""
        # Run the prediction process
        await forecaster.add_predictions_to_stops(
            mock_db_with_segments, mock_journey, sample_stops
        )

        # Check that departed stops don't have predictions
        assert (
            not hasattr(sample_stops[0], "predicted_arrival")
            or sample_stops[0].predicted_arrival is None
        )
        assert (
            not hasattr(sample_stops[1], "predicted_arrival")
            or sample_stops[1].predicted_arrival is None
        )

        # Check that future stops have predictions
        assert hasattr(sample_stops[2], "predicted_arrival")
        assert sample_stops[2].predicted_arrival is not None
        assert hasattr(sample_stops[2], "predicted_arrival_samples")
        assert sample_stops[2].predicted_arrival_samples > 0

    @pytest.mark.asyncio
    async def test_add_predictions_with_user_origin(
        self, forecaster, mock_journey, sample_stops, mock_db_with_segments
    ):
        """Test predictions with user origin specified."""
        # User boards at TR (future stop)
        await forecaster.add_predictions_to_stops(
            mock_db_with_segments, mock_journey, sample_stops, user_origin="TR"
        )

        # TR is the user's origin, shouldn't have prediction
        assert (
            not hasattr(sample_stops[2], "predicted_arrival")
            or sample_stops[2].predicted_arrival is None
        )

        # PH should have prediction (after user's origin)
        assert hasattr(sample_stops[3], "predicted_arrival")

    @pytest.mark.asyncio
    async def test_error_handling_missing_attributes(self, forecaster, mock_journey):
        """Test graceful handling of stops with missing attributes."""
        # Create stops with missing attributes
        bad_stops = [
            MagicMock(spec=["stop_sequence"]),  # Missing station
            MagicMock(spec=["station"]),  # Missing stop_sequence
        ]

        mock_db = AsyncMock(spec=AsyncSession)

        # Should not raise exception
        await forecaster.add_predictions_to_stops(mock_db, mock_journey, bad_stops)

    @pytest.mark.asyncio
    async def test_error_handling_database_failure(
        self, forecaster, mock_journey, sample_stops
    ):
        """Test handling of database query failures."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute.side_effect = Exception("Database connection error")

        # Should not raise exception, but handle gracefully
        await forecaster.add_predictions_to_stops(mock_db, mock_journey, sample_stops)

        # Stops should not have predictions due to database error
        for stop in sample_stops[2:]:
            assert (
                not hasattr(stop, "predicted_arrival") or stop.predicted_arrival is None
            )

    def test_get_departure_buffer(self, forecaster):
        """Test departure buffer calculation based on inference source."""
        stop = MagicMock()

        # Test api_explicit
        stop.departure_source = "api_explicit"
        buffer = forecaster._get_departure_buffer(stop)
        assert buffer == timedelta(minutes=1)

        # Test sequential_inference
        stop.departure_source = "sequential_inference"
        buffer = forecaster._get_departure_buffer(stop)
        assert buffer == timedelta(minutes=2)

        # Test time_inference
        stop.departure_source = "time_inference"
        buffer = forecaster._get_departure_buffer(stop)
        assert buffer == timedelta(minutes=5)

        # Test unknown/missing source
        stop.departure_source = None
        buffer = forecaster._get_departure_buffer(stop)
        assert buffer == timedelta(minutes=0)

    @pytest.mark.asyncio
    async def test_coalesce_logic(self, forecaster):
        """Test COALESCE logic (actual times preferred over scheduled).

        The batch query uses COALESCE(actual, scheduled) at the SQL level.
        Mock rows represent the coalesced values as raw per-stop data.
        """
        mock_db = AsyncMock(spec=AsyncSession)
        base_time = now_et()

        # Per-stop rows with coalesced departure/arrival times (30 min transit each).
        # Arrival times within LOOKBACK_HOURS (1h) for the cutoff check.
        mock_rows = [
            # Journey 1: A departure, B arrival (30 min)
            MagicMock(journey_id=1, station_code="A", stop_sequence=0,
                      departure_time=base_time - timedelta(minutes=40),
                      arrival_time=None),
            MagicMock(journey_id=1, station_code="B", stop_sequence=1,
                      departure_time=None,
                      arrival_time=base_time - timedelta(minutes=10)),
            # Journey 2: A departure, B arrival (30 min)
            MagicMock(journey_id=2, station_code="A", stop_sequence=0,
                      departure_time=base_time - timedelta(minutes=50),
                      arrival_time=None),
            MagicMock(journey_id=2, station_code="B", stop_sequence=1,
                      departure_time=None,
                      arrival_time=base_time - timedelta(minutes=20)),
            # Journey 3: A departure, B arrival (30 min)
            MagicMock(journey_id=3, station_code="A", stop_sequence=0,
                      departure_time=base_time - timedelta(minutes=55),
                      arrival_time=None),
            MagicMock(journey_id=3, station_code="B", stop_sequence=1,
                      departure_time=None,
                      arrival_time=base_time - timedelta(minutes=25)),
        ]

        mock_db.execute.return_value = mock_rows

        result = await forecaster._get_segment_transit_time(
            mock_db, "A", "B", "NJT", None
        )

        assert result is not None
        assert result["samples"] == 3
        assert result["avg"] == pytest.approx(30.0)

    @pytest.mark.asyncio
    async def test_max_segment_minutes_filtering(self, forecaster):
        """Test that segments over MAX_SEGMENT_MINUTES are filtered out."""
        mock_db = AsyncMock(spec=AsyncSession)
        base_time = now_et()

        # Per-stop rows with unreasonable transit time (2 hours = 120 minutes)
        # This exceeds MAX_SEGMENT_MINUTES (60 minutes)
        # B arrival within lookback window so it passes the cutoff check
        mock_rows = [
            MagicMock(journey_id=1, station_code="A", stop_sequence=0,
                      departure_time=base_time - timedelta(minutes=150),
                      arrival_time=None),
            MagicMock(journey_id=1, station_code="B", stop_sequence=1,
                      departure_time=None,
                      arrival_time=base_time - timedelta(minutes=30)),  # 120 min transit!
        ]

        mock_db.execute.return_value = mock_rows

        result = await forecaster._get_segment_transit_time(
            mock_db, "A", "B", "NJT", None
        )

        # Should return None as the single sample exceeds MAX_SEGMENT_MINUTES
        assert result is None
