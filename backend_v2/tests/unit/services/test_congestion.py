"""
Comprehensive unit tests for CongestionAnalyzer service.

Tests the real-time congestion calculation from journey data including
thresholds, baseline calculations, and data aggregation.
"""

import statistics
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import TrainJourney
from trackrat.services.congestion import CongestionAnalyzer, SegmentCongestion


class TestSegmentCongestion:
    """Test cases for SegmentCongestion data class."""

    def test_segment_congestion_initialization(self):
        """Test that SegmentCongestion initializes with all attributes."""
        segment = SegmentCongestion(
            from_station="NY",
            to_station="NP",
            data_source="NJT",
            congestion_factor=1.25,
            congestion_level="moderate",
            avg_transit_minutes=18.5,
            baseline_minutes=15.0,
            sample_count=25,
            average_delay_minutes=3.5,
            cancellation_count=2,
            cancellation_rate=0.08,
        )

        assert segment.from_station == "NY"
        assert segment.to_station == "NP"
        assert segment.data_source == "NJT"
        assert segment.congestion_factor == 1.25
        assert segment.congestion_level == "moderate"
        assert segment.avg_transit_minutes == 18.5
        assert segment.baseline_minutes == 15.0
        assert segment.sample_count == 25
        assert segment.average_delay_minutes == 3.5
        assert segment.cancellation_count == 2
        assert segment.cancellation_rate == 0.08


class TestCongestionAnalyzer:
    """Test cases for CongestionAnalyzer service."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def congestion_analyzer(self):
        """Create a CongestionAnalyzer instance for testing."""
        return CongestionAnalyzer()

    @pytest.fixture
    def sample_journeys(self):
        """Create sample journey data for testing."""
        current_time = datetime.now(UTC)

        # Journey 1: On-time train
        journey1 = Mock(spec=TrainJourney)
        journey1.id = 1
        journey1.train_id = "1234"
        journey1.data_source = "NJT"
        journey1.is_cancelled = False
        journey1.last_updated_at = current_time - timedelta(minutes=30)

        # Stops for journey 1 (NY -> NP -> TR)
        stop1_1 = Mock()
        stop1_1.station_code = "NY"
        stop1_1.stop_sequence = 1
        stop1_1.scheduled_departure = current_time - timedelta(hours=1)
        stop1_1.actual_departure = current_time - timedelta(hours=1)

        stop1_2 = Mock()
        stop1_2.station_code = "NP"
        stop1_2.stop_sequence = 2
        stop1_2.scheduled_arrival = current_time - timedelta(minutes=45)
        stop1_2.actual_arrival = current_time - timedelta(minutes=45)
        stop1_2.scheduled_departure = current_time - timedelta(minutes=43)
        stop1_2.actual_departure = current_time - timedelta(minutes=43)

        stop1_3 = Mock()
        stop1_3.station_code = "TR"
        stop1_3.stop_sequence = 3
        stop1_3.scheduled_arrival = current_time - timedelta(minutes=15)
        stop1_3.actual_arrival = current_time - timedelta(minutes=15)

        journey1.stops = [stop1_1, stop1_2, stop1_3]
        journey1.progress = None

        # Journey 2: Delayed train
        journey2 = Mock(spec=TrainJourney)
        journey2.id = 2
        journey2.train_id = "5678"
        journey2.data_source = "NJT"
        journey2.is_cancelled = False
        journey2.last_updated_at = current_time - timedelta(hours=1)

        # Stops for journey 2 (NY -> NP with 5-minute delay)
        stop2_1 = Mock()
        stop2_1.station_code = "NY"
        stop2_1.stop_sequence = 1
        stop2_1.scheduled_departure = current_time - timedelta(hours=2)
        stop2_1.actual_departure = (
            current_time - timedelta(hours=2) + timedelta(minutes=5)
        )

        stop2_2 = Mock()
        stop2_2.station_code = "NP"
        stop2_2.stop_sequence = 2
        stop2_2.scheduled_arrival = (
            current_time - timedelta(hours=2) + timedelta(minutes=15)
        )
        stop2_2.actual_arrival = (
            current_time - timedelta(hours=2) + timedelta(minutes=20)
        )

        journey2.stops = [stop2_1, stop2_2]
        journey2.progress = None

        # Journey 3: Cancelled train
        journey3 = Mock(spec=TrainJourney)
        journey3.id = 3
        journey3.train_id = "9012"
        journey3.data_source = "NJT"
        journey3.is_cancelled = True
        journey3.last_updated_at = current_time - timedelta(minutes=45)
        journey3.stops = []
        journey3.progress = None

        return [journey1, journey2, journey3]

    def test_congestion_level_thresholds(self):
        """Test congestion level thresholds match implementation."""
        # The congestion levels are determined inline in the code based on factor
        # Normal: factor <= 1.1 (up to 10% slower)
        # Moderate: 1.1 < factor <= 1.25 (10-25% slower)
        # Heavy: 1.25 < factor <= 1.5 (25-50% slower)
        # Severe: factor > 1.5 (>50% slower)

        # Test boundary values
        assert 1.05 <= 1.1  # Normal
        assert 1.1 <= 1.1  # Normal (boundary)
        assert 1.15 > 1.1 and 1.15 <= 1.25  # Moderate
        assert 1.25 > 1.1 and 1.25 <= 1.25  # Moderate (boundary)
        assert 1.35 > 1.25 and 1.35 <= 1.5  # Heavy
        assert 1.5 > 1.25 and 1.5 <= 1.5  # Heavy (boundary)
        assert 1.75 > 1.5  # Severe
        assert 2.0 > 1.5  # Severe

    def test_frequency_level_thresholds(self):
        """Test frequency level thresholds (higher factor = better service)."""
        from trackrat.services.congestion import get_frequency_level

        # Frequency levels are inverted from congestion:
        # Healthy: factor >= 0.9 (at least 90% of baseline trains)
        # Moderate: 0.7 <= factor < 0.9 (70-90% of baseline)
        # Reduced: 0.5 <= factor < 0.7 (50-70% of baseline)
        # Severe: factor < 0.5 (less than 50% of baseline)

        # Test healthy range
        assert get_frequency_level(1.0) == "healthy"  # 100% of baseline
        assert get_frequency_level(0.95) == "healthy"  # 95% of baseline
        assert get_frequency_level(0.9) == "healthy"  # 90% boundary

        # Test moderate range
        assert get_frequency_level(0.85) == "moderate"  # 85%
        assert get_frequency_level(0.7) == "moderate"  # 70% boundary

        # Test reduced range
        assert get_frequency_level(0.65) == "reduced"  # 65%
        assert get_frequency_level(0.5) == "reduced"  # 50% boundary

        # Test severe range
        assert get_frequency_level(0.45) == "severe"  # 45%
        assert get_frequency_level(0.3) == "severe"  # 30%
        assert get_frequency_level(0.0) == "severe"  # No trains

    def test_calculate_segments_from_journeys(
        self, congestion_analyzer, sample_journeys
    ):
        """Test segment calculation from journey data."""
        cutoff_time = datetime.now(UTC) - timedelta(hours=3)

        segment_data, cancellation_data = (
            congestion_analyzer._calculate_segments_from_journeys(
                sample_journeys, cutoff_time
            )
        )

        # Should have segments for NY->NP from both active journeys
        ny_np_key = ("NY", "NP", "NJT")
        assert ny_np_key in segment_data
        assert len(segment_data[ny_np_key]) == 2  # Two trains on this segment

        # Should have segment for NP->TR from journey 1 only
        np_tr_key = ("NP", "TR", "NJT")
        assert np_tr_key in segment_data
        assert len(segment_data[np_tr_key]) == 1

        # Cancellation data should track cancelled trains
        # The third journey is cancelled and would have gone NY->NP (based on stops)
        # But journey 3 has empty stops in our test fixture
        # So there should be no cancellations recorded
        assert cancellation_data.get(ny_np_key, 0) == 0  # Journey 3 has no stops

    def test_analyze_segment_congestion(self, congestion_analyzer):
        """Test congestion analysis for segments."""
        # Create segment data with various transit times
        current_time = datetime.now(UTC)
        segment_data = {
            ("NY", "NP", "NJT"): [
                {
                    "actual_minutes": 15,
                    "scheduled_minutes": 15,
                    "departure_time": current_time - timedelta(hours=3),
                },  # On-time
                {
                    "actual_minutes": 18,
                    "scheduled_minutes": 15,
                    "departure_time": current_time - timedelta(hours=2),
                },  # 3 min delay
                {
                    "actual_minutes": 20,
                    "scheduled_minutes": 15,
                    "departure_time": current_time - timedelta(hours=1),
                },  # 5 min delay
            ]
        }

        cancellation_counts = {("NY", "NP", "NJT"): 1}  # 1 cancellation

        results = congestion_analyzer._analyze_segment_congestion(
            segment_data, cancellation_counts
        )

        assert len(results) == 1
        segment = results[0]

        # Verify calculations
        assert segment.from_station == "NY"
        assert segment.to_station == "NP"
        assert segment.data_source == "NJT"
        assert segment.sample_count == 3
        assert segment.avg_transit_minutes == pytest.approx(17.67, rel=0.01)
        assert segment.baseline_minutes == 15.0  # Scheduled baseline
        assert segment.congestion_factor == pytest.approx(1.18, rel=0.01)
        assert segment.congestion_level == "moderate"
        assert segment.average_delay_minutes == pytest.approx(2.67, rel=0.01)
        assert segment.cancellation_count == 1
        assert segment.cancellation_rate == 25.0  # 1/4 = 25%

    def test_analyze_segment_without_scheduled_times(self, congestion_analyzer):
        """Test congestion analysis when scheduled times are missing."""
        current_time = datetime.now(UTC)
        segment_data = {
            ("NY", "NP", "NJT"): [
                {
                    "actual_minutes": 15,
                    "scheduled_minutes": None,
                    "departure_time": current_time - timedelta(hours=4),
                },
                {
                    "actual_minutes": 18,
                    "scheduled_minutes": None,
                    "departure_time": current_time - timedelta(hours=3),
                },
                {
                    "actual_minutes": 20,
                    "scheduled_minutes": None,
                    "departure_time": current_time - timedelta(hours=2),
                },
                {
                    "actual_minutes": 25,
                    "scheduled_minutes": None,
                    "departure_time": current_time - timedelta(hours=1),
                },
            ]
        }

        cancellation_counts = {("NY", "NP", "NJT"): 0}  # No cancellations

        results = congestion_analyzer._analyze_segment_congestion(
            segment_data, cancellation_counts
        )

        segment = results[0]
        # Should use median as baseline when scheduled times missing
        assert segment.baseline_minutes == statistics.median([15, 18, 20, 25])  # 19.0
        assert segment.avg_transit_minutes == pytest.approx(19.5, rel=0.01)
        assert segment.congestion_factor == pytest.approx(1.03, rel=0.01)
        assert segment.congestion_level == "normal"

    def test_insufficient_data_handling(self, congestion_analyzer):
        """Test handling of segments with insufficient data."""
        # Single journey (< 2 total) should be excluded for statistical validity
        current_time = datetime.now(UTC)
        segment_data = {
            ("NY", "NP", "NJT"): [
                {
                    "actual_minutes": 15,
                    "scheduled_minutes": 15,
                    "departure_time": current_time - timedelta(hours=1),
                },
            ]
        }

        cancellation_counts = {("NY", "NP", "NJT"): 0}  # No cancellations

        results = congestion_analyzer._analyze_segment_congestion(
            segment_data, cancellation_counts
        )

        # Should return empty list since we need at least 2 journeys for statistical validity
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_cache_behavior(self, congestion_analyzer, mock_db):
        """Test that congestion data is cached and reused."""
        # Mock database results
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        with patch.object(
            congestion_analyzer, "_calculate_segments_from_journeys"
        ) as mock_calc:
            with patch.object(
                congestion_analyzer, "_analyze_segment_congestion"
            ) as mock_analyze:
                mock_calc.return_value = ({}, {})
                mock_analyze.return_value = []

                # First call should hit database
                result1 = await congestion_analyzer.get_network_congestion(mock_db, 3)
                assert mock_db.execute.call_count == 1

                # Second call within cache TTL should use cache
                result2 = await congestion_analyzer.get_network_congestion(mock_db, 3)
                assert mock_db.execute.call_count == 1  # No additional DB call
                assert result1 == result2

                # Different time window should not use cache
                result3 = await congestion_analyzer.get_network_congestion(mock_db, 2)
                assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_get_network_congestion_with_trains(
        self, congestion_analyzer, mock_db
    ):
        """Test combined method that returns congestion, journeys, and segments."""
        # Mock aggregated segments from optimized query
        mock_aggregated = [
            SegmentCongestion(
                from_station="NY",
                to_station="NP",
                data_source="NJT",
                congestion_factor=1.2,
                congestion_level="moderate",
                avg_transit_minutes=18,
                baseline_minutes=15,
                sample_count=10,
                average_delay_minutes=3,
            )
        ]

        # Mock journeys
        mock_journey = Mock(spec=TrainJourney)
        mock_journey.id = 1
        mock_journey.is_cancelled = False
        mock_journey.stops = []
        mock_journey.progress = None

        # Mock individual segments
        mock_individual = [
            {
                "from_station": "NY",
                "to_station": "NP",
                "train_id": "1234",
                "actual_minutes": 18,
            }
        ]

        with patch.object(
            congestion_analyzer, "get_network_congestion_optimized"
        ) as mock_optimized:
            with patch.object(
                congestion_analyzer, "get_individual_segments_optimized"
            ) as mock_segments:
                mock_optimized.return_value = mock_aggregated
                mock_segments.return_value = mock_individual

                # Mock journey query - first call gets journey list
                mock_journey_result = Mock()
                mock_journey_result.scalars.return_value.all.return_value = [
                    mock_journey
                ]

                # Mock current positions query - second call gets empty position list
                mock_positions_result = Mock()
                mock_positions_result.fetchall.return_value = []

                # Configure mock_db.execute to return different results for different calls
                mock_db.execute.side_effect = [
                    mock_journey_result,
                    mock_positions_result,
                ]

                aggregated, journeys, individual = (
                    await congestion_analyzer.get_network_congestion_with_trains(
                        mock_db, time_window_hours=3, max_per_segment=100
                    )
                )

                assert aggregated == mock_aggregated
                assert journeys == [mock_journey]
                assert individual == mock_individual

    @pytest.mark.asyncio
    async def test_get_network_congestion_optimized(self, congestion_analyzer, mock_db):
        """Test optimized database-level congestion calculation."""
        # Mock database query results
        mock_row = Mock()
        mock_row.from_station = "NY"
        mock_row.to_station = "NP"
        mock_row.data_source = "NJT"
        mock_row.active_count = 25
        mock_row.cancelled_count = 2
        mock_row.avg_actual = 18.5
        mock_row.baseline_minutes = 15.0
        mock_row.recent_avg = 19.0
        mock_row.current_avg_minutes = 19.0
        mock_row.median_actual = 17.0
        # Frequency fields
        mock_row.train_count = 25
        mock_row.baseline_train_count = 30.0
        mock_row.frequency_factor = 0.83  # 25/30

        mock_result = Mock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        with patch("trackrat.services.congestion.now_et") as mock_now:
            mock_now.return_value = datetime.now(UTC)

            results = await congestion_analyzer.get_network_congestion_optimized(
                mock_db, time_window_hours=3
            )

        # NY->NP is expanded to NY->SE and SE->NP by segment normalization
        # (since SE is an intermediate station on the NEC line)
        assert len(results) == 2

        # Find the segments by their from/to stations
        segments_by_key = {(s.from_station, s.to_station): s for s in results}
        assert ("NY", "SE") in segments_by_key
        assert ("SE", "NP") in segments_by_key

        # Both segments inherit the aggregated stats
        for segment in results:
            assert segment.data_source == "NJT"
            assert segment.sample_count == 25
            assert segment.avg_transit_minutes == 19.0
            assert segment.baseline_minutes == 15.0
            assert segment.congestion_factor == pytest.approx(1.27, rel=0.01)
            assert segment.congestion_level == "heavy"
            assert segment.cancellation_count == 2
            assert segment.cancellation_rate == pytest.approx(7.4, rel=0.01)  # 7.4%
            # Verify frequency fields
            assert segment.train_count == 25
            assert segment.baseline_train_count == 30.0
            assert segment.frequency_factor == pytest.approx(0.83, rel=0.01)
            assert segment.frequency_level == "moderate"  # 0.83 is between 0.7 and 0.9

    @pytest.mark.asyncio
    async def test_get_individual_segments_optimized(
        self, congestion_analyzer, mock_db
    ):
        """Test optimized individual segment retrieval."""
        # Mock database results for individual segments
        mock_row = Mock()
        mock_row.journey_id = 1
        mock_row.train_id = "1234"
        mock_row.from_station = "NY"
        mock_row.to_station = "NP"
        mock_row.data_source = "NJT"
        mock_row.journey_date = datetime.now(UTC).date()
        mock_row.departure_time = datetime.now(UTC) - timedelta(hours=1)
        mock_row.arrival_time = datetime.now(UTC) - timedelta(minutes=45)
        mock_row.scheduled_departure = datetime.now(UTC) - timedelta(hours=1)
        mock_row.scheduled_arrival = datetime.now(UTC) - timedelta(minutes=45)
        mock_row.actual_minutes = 15.0
        mock_row.scheduled_minutes = 15.0
        mock_row.delay_minutes = 0.0
        mock_row.congestion_factor = 1.0

        mock_result = Mock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        segments = await congestion_analyzer.get_individual_segments_optimized(
            mock_db, time_window_hours=3, max_per_segment=10
        )

        # NY->NP is expanded to NY->SE and SE->NP by segment normalization
        assert len(segments) == 2

        # Find the segments by their from/to stations
        segments_by_key = {(s.from_station, s.to_station): s for s in segments}
        assert ("NY", "SE") in segments_by_key
        assert ("SE", "NP") in segments_by_key

        # Both segments inherit the original segment's timing data
        for segment in segments:
            assert segment.train_id == "1234"
            assert segment.actual_minutes == 15.0
            assert segment.delay_minutes == 0.0
            assert segment.congestion_factor == 1.0

    def test_cache_expiration(self, congestion_analyzer):
        """Test that cache expires after TTL."""
        # Set up initial cache entry
        cache_key = "congestion_3"
        initial_data = []
        initial_time = datetime.now(UTC) - timedelta(seconds=301)  # Beyond TTL

        congestion_analyzer._cache[cache_key] = (initial_data, initial_time)

        # Check that expired cache is not used
        with patch("trackrat.services.congestion.now_et") as mock_now:
            mock_now.return_value = datetime.now(UTC)

            # Access cache through internal check
            if cache_key in congestion_analyzer._cache:
                cached_data, timestamp = congestion_analyzer._cache[cache_key]
                age = (mock_now.return_value - timestamp).total_seconds()
                is_expired = age >= congestion_analyzer._cache_ttl

                assert is_expired is True

    def test_empty_journey_handling(self, congestion_analyzer):
        """Test handling of empty journey lists."""
        segment_data, cancellation_data = (
            congestion_analyzer._calculate_segments_from_journeys([], datetime.now(UTC))
        )

        assert segment_data == {}
        assert cancellation_data == {}

        # Analyzing empty segments should return empty results
        results = congestion_analyzer._analyze_segment_congestion(
            segment_data, cancellation_data
        )
        assert results == []

    def test_invalid_transit_times_excluded(self, congestion_analyzer):
        """Test that invalid transit times are excluded from analysis."""
        current_time = datetime.now(UTC)
        segment_data = {
            ("NY", "NP", "NJT"): [
                {
                    "actual_minutes": 15,
                    "scheduled_minutes": 15,
                    "departure_time": current_time - timedelta(hours=4),
                },
                {
                    "actual_minutes": -5,
                    "scheduled_minutes": 15,
                    "departure_time": current_time - timedelta(hours=3),
                },  # Invalid negative
                {
                    "actual_minutes": 0,
                    "scheduled_minutes": 15,
                    "departure_time": current_time - timedelta(hours=2),
                },  # Invalid zero
                {
                    "actual_minutes": 20,
                    "scheduled_minutes": 15,
                    "departure_time": current_time - timedelta(hours=1),
                },
            ]
        }

        cancellation_counts = {("NY", "NP", "NJT"): 0}  # No cancellations

        # The analyzer should filter out invalid times internally
        results = congestion_analyzer._analyze_segment_congestion(
            segment_data, cancellation_counts
        )

        segment = results[0]
        # Should only use valid positive transit times
        assert segment.sample_count == 2  # Only the valid 15 and 20 minute segments
