"""
Unit tests for the simple arrival forecaster.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.api import SimpleStationInfo, StopDetails, RawStopStatus
from trackrat.models.database import TrainJourney
from trackrat.services.simple_forecaster import SimpleArrivalForecaster
from trackrat.utils.time import now_et


@pytest.fixture
def mock_journey():
    """Create a mock journey for testing."""
    journey = MagicMock(spec=TrainJourney)
    journey.train_id = "TEST123"
    journey.data_source = "NJT"
    journey.line_code = "NEC"
    return journey


@pytest.fixture
def sample_stops():
    """Create sample stops for testing."""
    base_time = now_et()

    stops = [
        StopDetails(
            station=SimpleStationInfo(code="NY", name="New York Penn Station"),
            stop_sequence=0,
            scheduled_departure=base_time - timedelta(minutes=30),
            has_departed_station=True,
            raw_status=RawStopStatus(),
        ),
        StopDetails(
            station=SimpleStationInfo(code="NP", name="Newark Penn Station"),
            stop_sequence=1,
            scheduled_arrival=base_time - timedelta(minutes=20),
            scheduled_departure=base_time - timedelta(minutes=18),
            has_departed_station=True,
            raw_status=RawStopStatus(),
        ),
        StopDetails(
            station=SimpleStationInfo(code="TR", name="Trenton"),
            stop_sequence=2,
            scheduled_arrival=base_time + timedelta(minutes=30),  # Changed to be more in future
            scheduled_departure=base_time + timedelta(minutes=32),
            has_departed_station=False,
            raw_status=RawStopStatus(),
        ),
        StopDetails(
            station=SimpleStationInfo(code="PH", name="Philadelphia"),
            stop_sequence=3,
            scheduled_arrival=base_time + timedelta(minutes=60),  # Changed to be more in future
            has_departed_station=False,
            raw_status=RawStopStatus(),
        ),
    ]

    return stops


@pytest.mark.asyncio
async def test_find_current_position(sample_stops):
    """Test finding the current position in the journey."""
    forecaster = SimpleArrivalForecaster()

    # Should find NP as the last departed stop (index 1)
    current_index = forecaster._find_current_position(sample_stops)
    assert current_index == 1

    # Test with no departed stops
    for stop in sample_stops:
        stop.has_departed_station = False
    current_index = forecaster._find_current_position(sample_stops)
    assert current_index == 0


@pytest.mark.asyncio
async def test_calculate_segment_time():
    """Test segment time calculation logic."""
    forecaster = SimpleArrivalForecaster()

    # Create mock stops
    from_stop = MagicMock()
    from_stop.station.code = "NY"
    from_stop.scheduled_departure = now_et()

    to_stop = MagicMock()
    to_stop.station.code = "NP"
    to_stop.scheduled_arrival = now_et() + timedelta(minutes=20)

    # Test with sufficient samples (should use median)
    segment_times = [18.0, 19.0, 20.0, 21.0, 22.0]
    transit_time = forecaster._calculate_segment_time(segment_times, from_stop, to_stop)
    assert transit_time == 20.0  # Median

    # Test with insufficient samples (should return None - honest predictions)
    segment_times = [19.0, 21.0]  # Less than MIN_SAMPLES
    transit_time = forecaster._calculate_segment_time(segment_times, from_stop, to_stop)
    assert transit_time is None  # Honest predictions - no fallback

    # Test with no samples (should return None - honest predictions)
    segment_times = []
    transit_time = forecaster._calculate_segment_time(segment_times, from_stop, to_stop)
    assert transit_time is None  # Honest predictions - no fallback


@pytest.mark.asyncio
async def test_add_predictions_to_stops(mock_journey, sample_stops):
    """Test adding predictions to stops."""
    forecaster = SimpleArrivalForecaster()

    # Mock the database session
    mock_db = AsyncMock(spec=AsyncSession)

    # Mock both database queries - first for total_segments, then for actual segments
    mock_total_result = MagicMock()
    mock_total_result.fetchall.return_value = (
        []
    )  # Empty total segments to avoid complex object access

    mock_actual_result = MagicMock()
    mock_actual_result.fetchall.return_value = [
        (15.0,),  # 15 minutes for NP->TR
        (14.0,),
        (16.0,),
        (15.5,),
    ]

    # Configure execute to return different results for different queries
    mock_db.execute.side_effect = [
        mock_total_result,
        mock_actual_result,
        mock_total_result,
        mock_actual_result,
    ]

    # Run the forecaster
    await forecaster.add_predictions_to_stops(mock_db, mock_journey, sample_stops)

    # Check that predictions were added to future stops
    assert sample_stops[0].predicted_arrival is None  # Already departed
    assert sample_stops[1].predicted_arrival is None  # Already departed
    assert sample_stops[2].predicted_arrival is not None  # Future stop
    assert sample_stops[3].predicted_arrival is not None  # Future stop

    # Check sample counts
    assert sample_stops[2].predicted_arrival_samples >= 0

    # Verify predictions are logically consistent
    if sample_stops[2].predicted_arrival and sample_stops[3].predicted_arrival:
        # Philadelphia should be after Trenton
        assert sample_stops[3].predicted_arrival > sample_stops[2].predicted_arrival


@pytest.mark.asyncio
async def test_max_segment_minutes_check(mock_journey, sample_stops):
    """Test that segments over 60 minutes are rejected."""
    forecaster = SimpleArrivalForecaster()

    # Mock the database session
    mock_db = AsyncMock(spec=AsyncSession)

    # Mock both database queries - first for total_segments, then for actual segments
    mock_total_result = MagicMock()
    mock_total_result.fetchall.return_value = (
        []
    )  # Empty total segments to avoid complex object access

    mock_actual_result = MagicMock()
    mock_actual_result.fetchall.return_value = [
        (65.0,),  # Over 60 minutes - should be rejected
        (70.0,),
        (80.0,),
    ]

    # Configure execute to return different results for different queries
    mock_db.execute.side_effect = [
        mock_total_result,
        mock_actual_result,
        mock_total_result,
        mock_actual_result,
    ]

    # Run the forecaster
    await forecaster.add_predictions_to_stops(mock_db, mock_journey, sample_stops)

    # TR stop should have 0 samples when data is rejected
    tr_stop = sample_stops[2]
    if tr_stop.predicted_arrival:
        assert (
            tr_stop.predicted_arrival_samples == 0
        )  # No valid samples due to >60 min times


@pytest.mark.asyncio
async def test_empty_stops_list(mock_journey):
    """Test that empty stops list is handled gracefully."""
    forecaster = SimpleArrivalForecaster()
    mock_db = AsyncMock(spec=AsyncSession)

    empty_stops = []

    # Should not raise an exception
    await forecaster.add_predictions_to_stops(mock_db, mock_journey, empty_stops)

    # Nothing should have been added
    assert len(empty_stops) == 0
