"""
Unit tests for the direct arrival forecaster.

Tests the DirectArrivalForecaster which calculates segment times directly
from recent journeys without intermediate storage.
"""

import asyncio
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

            # Test very stale time (uses current time to preserve delay)
            very_stale = now - timedelta(minutes=15)
            validated = forecaster._validate_prediction_time(very_stale, stop)
            assert validated == now  # Should use current time, not reset to schedule

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
            MagicMock(
                journey_id=1,
                station_code="A",
                stop_sequence=0,
                departure_time=base_time - timedelta(minutes=40),
                arrival_time=None,
            ),
            MagicMock(
                journey_id=1,
                station_code="B",
                stop_sequence=1,
                departure_time=None,
                arrival_time=base_time - timedelta(minutes=10),
            ),
            # Journey 2: A departure, B arrival (30 min)
            MagicMock(
                journey_id=2,
                station_code="A",
                stop_sequence=0,
                departure_time=base_time - timedelta(minutes=50),
                arrival_time=None,
            ),
            MagicMock(
                journey_id=2,
                station_code="B",
                stop_sequence=1,
                departure_time=None,
                arrival_time=base_time - timedelta(minutes=20),
            ),
            # Journey 3: A departure, B arrival (30 min)
            MagicMock(
                journey_id=3,
                station_code="A",
                stop_sequence=0,
                departure_time=base_time - timedelta(minutes=55),
                arrival_time=None,
            ),
            MagicMock(
                journey_id=3,
                station_code="B",
                stop_sequence=1,
                departure_time=None,
                arrival_time=base_time - timedelta(minutes=25),
            ),
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
            MagicMock(
                journey_id=1,
                station_code="A",
                stop_sequence=0,
                departure_time=base_time - timedelta(minutes=150),
                arrival_time=None,
            ),
            MagicMock(
                journey_id=1,
                station_code="B",
                stop_sequence=1,
                departure_time=None,
                arrival_time=base_time - timedelta(minutes=30),
            ),  # 120 min transit!
        ]

        mock_db.execute.return_value = mock_rows

        result = await forecaster._get_segment_transit_time(
            mock_db, "A", "B", "NJT", None
        )

        # Should return None as the single sample exceeds MAX_SEGMENT_MINUTES
        assert result is None

    def test_get_scheduled_segment_duration(self, forecaster, sample_stops):
        """Test scheduled segment duration calculation between two stops."""
        # sample_stops[1] (NP) has scheduled_departure, sample_stops[2] (TR) has scheduled_arrival
        duration = forecaster._get_scheduled_segment_duration(
            sample_stops[1], sample_stops[2]
        )
        assert duration is not None
        assert duration.total_seconds() > 0

    def test_get_scheduled_segment_duration_missing_times(self, forecaster):
        """Test scheduled segment duration when times are missing."""
        from_stop = StopDetails(
            station=SimpleStationInfo(code="A", name="Station A"),
            stop_sequence=0,
            has_departed_station=False,
            raw_status=RawStopStatus(),
        )
        to_stop = StopDetails(
            station=SimpleStationInfo(code="B", name="Station B"),
            stop_sequence=1,
            has_departed_station=False,
            raw_status=RawStopStatus(),
        )
        duration = forecaster._get_scheduled_segment_duration(from_stop, to_stop)
        assert duration is None

    @pytest.mark.asyncio
    async def test_chain_preserves_delay_through_missing_segment(
        self, forecaster, mock_journey
    ):
        """Test that accumulated delay is preserved when a segment lacks transit data.

        When empirical data is missing for one segment, the chain should use the
        scheduled segment duration to carry forward the delay, rather than resetting
        to scheduled departure (which would lose the accumulated delay).

        Scenario: Train departs NY 15 min late. NY→NP has no empirical data.
        NP→TR has empirical data matching scheduled duration (~38 min).
        The 15 min delay should propagate through the gap to TR.

        Schedule:
          NY depart: base-30  |  NP arrive: base-10, depart: base-8
          TR arrive: base+30  |  PH arrive: base+60
        Actual: NY depart: base-15 (15 min late)
        """
        base_time = now_et()

        stops = [
            StopDetails(
                station=SimpleStationInfo(code="NY", name="New York"),
                stop_sequence=0,
                scheduled_departure=base_time - timedelta(minutes=30),
                has_departed_station=True,
                actual_departure=base_time - timedelta(minutes=15),  # 15 min late
                raw_status=RawStopStatus(),
            ),
            StopDetails(
                station=SimpleStationInfo(code="NP", name="Newark"),
                stop_sequence=1,
                scheduled_arrival=base_time - timedelta(minutes=10),
                scheduled_departure=base_time - timedelta(minutes=8),
                has_departed_station=False,
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

        mock_db = AsyncMock(spec=AsyncSession)

        # _get_all_segment_transit_times makes a single batch query returning
        # per-stop rows (journey_id, station_code, stop_sequence, departure_time,
        # arrival_time). We provide NO rows for NY (so NY→NP has no data), and
        # rows for NP, TR, PH across 3 journeys so those segments have data.
        # Arrival times must be within LOOKBACK_HOURS (1h) of now for the cutoff.
        #
        # Segment NP→TR: ~38 min transit (matches scheduled NP dep→TR arr)
        # Segment TR→PH: ~28 min transit (matches scheduled TR dep→PH arr)
        batch_rows = []
        for j_id, offset_min in [(1, 5), (2, 20), (3, 40)]:
            # NP stop: departure used for NP→TR segment
            batch_rows.append(
                MagicMock(
                    journey_id=j_id,
                    station_code="NP",
                    stop_sequence=1,
                    departure_time=base_time - timedelta(minutes=offset_min + 38),
                    arrival_time=base_time - timedelta(minutes=offset_min + 40),
                )
            )
            # TR stop: arrival used for NP→TR, departure used for TR→PH
            batch_rows.append(
                MagicMock(
                    journey_id=j_id,
                    station_code="TR",
                    stop_sequence=2,
                    departure_time=base_time - timedelta(minutes=offset_min + 0),
                    arrival_time=base_time - timedelta(minutes=offset_min),
                )
            )
            # PH stop: arrival used for TR→PH segment
            batch_rows.append(
                MagicMock(
                    journey_id=j_id,
                    station_code="PH",
                    stop_sequence=3,
                    departure_time=None,
                    arrival_time=base_time
                    - timedelta(minutes=offset_min)
                    + timedelta(minutes=28),
                )
            )

        mock_db.execute = AsyncMock(return_value=batch_rows)

        await forecaster.add_predictions_to_stops(
            mock_db, mock_journey, stops, user_origin="NY"
        )

        # NP has no empirical data, so no prediction shown for it
        assert stops[1].predicted_arrival is None

        # TR should have a prediction reflecting the propagated delay.
        # Chain: actual_dep(NY)=base-15, gap NY→NP uses scheduled 20min → base+5,
        # _calculate_next_departure at NP: max(sched_dep=base-8, base+5) = base+5,
        # empirical NP→TR = 38min → predicted_arr(TR) = base+43
        # scheduled_arr(TR) = base+30 → delay = 13min
        assert stops[2].predicted_arrival is not None, "TR should have a prediction"
        scheduled_arrival_tr = base_time + timedelta(minutes=30)
        predicted_delay_tr = (
            stops[2].predicted_arrival - scheduled_arrival_tr
        ).total_seconds() / 60
        assert predicted_delay_tr > 10, (
            f"Expected ~13 min delay at TR (from 15min late departure) but got "
            f"{predicted_delay_tr:.1f}min. Chain may have reset to schedule."
        )

        # PH should also have a prediction with similar delay
        assert stops[3].predicted_arrival is not None, "PH should have a prediction"
        scheduled_arrival_ph = base_time + timedelta(minutes=60)
        predicted_delay_ph = (
            stops[3].predicted_arrival - scheduled_arrival_ph
        ).total_seconds() / 60
        assert predicted_delay_ph > 10, (
            f"Expected ~13 min delay at PH but got {predicted_delay_ph:.1f}min. "
            f"Delay not propagated through chain."
        )

    @pytest.mark.asyncio
    async def test_forecaster_timeout_degrades_gracefully(
        self, mock_journey, sample_stops
    ):
        """Test that asyncio.wait_for timeout skips predictions without error.

        The trains.py endpoint wraps the forecaster in asyncio.wait_for(timeout=5.0).
        When the forecaster DB query hangs, the TimeoutError should be caught and
        the response should still return without predictions. This test verifies
        the timeout pattern works correctly with the forecaster's async interface.
        """
        slow_forecaster = DirectArrivalForecaster()

        # Simulate a slow DB query by making add_predictions_to_stops hang
        original_method = slow_forecaster.add_predictions_to_stops

        async def slow_predictions(*args, **kwargs):
            await asyncio.sleep(10)  # Simulate 10s DB hang
            return await original_method(*args, **kwargs)

        slow_forecaster.add_predictions_to_stops = slow_predictions

        # Verify the timeout fires and raises TimeoutError
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                slow_forecaster.add_predictions_to_stops(
                    AsyncMock(spec=AsyncSession), mock_journey, sample_stops
                ),
                timeout=0.1,  # 100ms timeout for fast test
            )

        # Verify stops were NOT modified (predictions not added)
        for stop in sample_stops:
            assert (
                stop.predicted_arrival is None
            ), f"Stop {stop.station.code} should not have predictions after timeout"
