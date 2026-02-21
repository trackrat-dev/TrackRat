"""
Unit tests for the delay forecaster service.

Tests the DelayForecaster which predicts delays and cancellations
using hierarchical historical data, including stop-level predictions.
"""

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.services.delay_forecaster import (
    DelayForecaster,
    DelayStats,
    MIN_TRAIN_ID_SAMPLES,
    MIN_LINE_CODE_SAMPLES,
    MIN_DATA_SOURCE_SAMPLES,
)


@pytest.fixture
def forecaster():
    """Create a DelayForecaster instance."""
    return DelayForecaster()


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def sample_train_stats():
    """Create sample delay stats for a specific train."""
    return DelayStats(
        sample_count=50,
        cancellation_count=2,
        on_time_count=35,
        slight_delay_count=10,
        significant_delay_count=2,
        major_delay_count=1,
        total_delay_minutes=150,
        level="train_id",
    )


@pytest.fixture
def sample_line_stats():
    """Create sample delay stats for a line code."""
    return DelayStats(
        sample_count=500,
        cancellation_count=15,
        on_time_count=350,
        slight_delay_count=100,
        significant_delay_count=25,
        major_delay_count=10,
        total_delay_minutes=2000,
        level="line_code",
    )


class TestDelayForecaster:
    """Test class for DelayForecaster."""

    def test_calculate_probabilities_with_train_stats(
        self, forecaster, sample_train_stats
    ):
        """Test probability calculation from train-level stats."""
        forecast = forecaster._calculate_probabilities(sample_train_stats)

        # Check cancellation probability
        assert forecast.cancellation_probability == pytest.approx(2 / 50, rel=0.01)

        # Check delay probabilities sum to ~1.0
        total_delay_prob = (
            forecast.on_time_probability
            + forecast.slight_delay_probability
            + forecast.significant_delay_probability
            + forecast.major_delay_probability
        )
        assert total_delay_prob == pytest.approx(1.0, rel=0.01)

        # Check expected delay
        non_cancelled = 50 - 2
        expected = 150 // non_cancelled
        assert forecast.expected_delay_minutes == expected

        # High confidence for train_id level
        assert forecast.confidence == "high"

    def test_calculate_probabilities_with_line_stats(
        self, forecaster, sample_line_stats
    ):
        """Test probability calculation from line-level stats."""
        forecast = forecaster._calculate_probabilities(sample_line_stats)

        # Check cancellation probability
        assert forecast.cancellation_probability == pytest.approx(15 / 500, rel=0.01)

        # Medium confidence for line_code level
        assert forecast.confidence == "medium"

    def test_apply_adjustment_increases_delay_probability(self, forecaster):
        """Test that adjustment multiplier shifts probability toward delays."""
        # Create a baseline forecast
        base_stats = DelayStats(
            sample_count=100,
            cancellation_count=5,
            on_time_count=70,
            slight_delay_count=15,
            significant_delay_count=7,
            major_delay_count=3,
            total_delay_minutes=400,
            level="train_id",
        )
        base_forecast = forecaster._calculate_probabilities(base_stats)

        # Apply 1.5x multiplier
        adjusted = forecaster._apply_adjustment(base_forecast, 1.5)

        # On-time probability should decrease
        assert adjusted.on_time_probability < base_forecast.on_time_probability

        # Delay probabilities should increase
        assert (
            adjusted.slight_delay_probability >= base_forecast.slight_delay_probability
        )

        # Expected delay should increase
        assert adjusted.expected_delay_minutes > base_forecast.expected_delay_minutes

        # Probabilities should still sum to 1.0
        total = (
            adjusted.on_time_probability
            + adjusted.slight_delay_probability
            + adjusted.significant_delay_probability
            + adjusted.major_delay_probability
        )
        assert total == pytest.approx(1.0, rel=0.01)

    def test_apply_adjustment_no_change_for_multiplier_1(self, forecaster):
        """Test that multiplier of 1.0 doesn't change probabilities."""
        base_stats = DelayStats(
            sample_count=100,
            cancellation_count=5,
            on_time_count=70,
            slight_delay_count=15,
            significant_delay_count=7,
            major_delay_count=3,
            total_delay_minutes=400,
            level="train_id",
        )
        base_forecast = forecaster._calculate_probabilities(base_stats)

        adjusted = forecaster._apply_adjustment(base_forecast, 1.0)

        assert adjusted.on_time_probability == base_forecast.on_time_probability
        assert adjusted.expected_delay_minutes == base_forecast.expected_delay_minutes

    def test_static_fallback_njt(self, forecaster):
        """Test static fallback for NJT."""
        fallback = forecaster._create_static_fallback("NJT")

        assert fallback.confidence == "low"
        assert fallback.sample_count == 0
        assert "static_fallback" in fallback.factors

        # Check reasonable defaults
        assert 0.01 <= fallback.cancellation_probability <= 0.10
        assert 0.50 <= fallback.on_time_probability <= 0.90

        # Probabilities should sum to 1.0
        total = (
            fallback.on_time_probability
            + fallback.slight_delay_probability
            + fallback.significant_delay_probability
            + fallback.major_delay_probability
        )
        assert total == pytest.approx(1.0, rel=0.01)

    def test_static_fallback_amtrak(self, forecaster):
        """Test static fallback for AMTRAK."""
        fallback = forecaster._create_static_fallback("AMTRAK")

        assert fallback.confidence == "low"

        # Amtrak should have slightly different defaults than NJT
        # (historically higher delay rates)
        assert fallback.expected_delay_minutes >= 5

    @pytest.mark.asyncio
    async def test_forecast_uses_train_id_when_sufficient_samples(
        self, forecaster, mock_db
    ):
        """Test that forecast uses train_id stats when sufficient samples exist."""
        # Mock the stats methods
        with (
            patch.object(
                forecaster,
                "_get_train_id_stats",
                return_value=DelayStats(
                    sample_count=50,  # Above MIN_TRAIN_ID_SAMPLES (10)
                    cancellation_count=2,
                    on_time_count=40,
                    slight_delay_count=5,
                    significant_delay_count=2,
                    major_delay_count=1,
                    total_delay_minutes=100,
                    level="train_id",
                ),
            ) as mock_train,
            patch.object(
                forecaster, "_get_line_code_stats", return_value=None
            ) as mock_line,
            patch.object(
                forecaster, "_get_data_source_stats", return_value=None
            ) as mock_ds,
            patch.object(forecaster, "_get_hour_day_adjustment", return_value=1.0),
            patch.object(forecaster, "_get_congestion_multiplier", return_value=1.0),
        ):
            forecast = await forecaster.forecast(
                train_id="TEST123",
                station_code="NY",
                origin_station_code="NY",
                line_code="NE",
                data_source="NJT",
                journey_date=date.today(),
                scheduled_departure=datetime.now(),
                db=mock_db,
            )

            assert "train_history" in forecast.factors
            assert forecast.confidence == "high"
            mock_train.assert_called_once()

    @pytest.mark.asyncio
    async def test_forecast_falls_back_to_line_code(self, forecaster, mock_db):
        """Test fallback to line_code when train_id has insufficient samples."""
        with (
            patch.object(
                forecaster,
                "_get_train_id_stats",
                return_value=DelayStats(
                    sample_count=5,  # Below MIN_TRAIN_ID_SAMPLES
                    cancellation_count=0,
                    on_time_count=4,
                    slight_delay_count=1,
                    significant_delay_count=0,
                    major_delay_count=0,
                    total_delay_minutes=10,
                    level="train_id",
                ),
            ),
            patch.object(
                forecaster,
                "_get_line_code_stats",
                return_value=DelayStats(
                    sample_count=100,  # Above MIN_LINE_CODE_SAMPLES (25)
                    cancellation_count=5,
                    on_time_count=70,
                    slight_delay_count=15,
                    significant_delay_count=7,
                    major_delay_count=3,
                    total_delay_minutes=500,
                    level="line_code",
                ),
            ),
            patch.object(forecaster, "_get_data_source_stats", return_value=None),
            patch.object(forecaster, "_get_hour_day_adjustment", return_value=1.0),
            patch.object(forecaster, "_get_congestion_multiplier", return_value=1.0),
        ):
            forecast = await forecaster.forecast(
                train_id="TEST123",
                station_code="NY",
                origin_station_code="NY",
                line_code="NE",
                data_source="NJT",
                journey_date=date.today(),
                scheduled_departure=datetime.now(),
                db=mock_db,
            )

            assert "line_pattern" in forecast.factors
            assert "train_history" not in forecast.factors
            assert forecast.confidence == "medium"

    @pytest.mark.asyncio
    async def test_forecast_falls_back_to_static(self, forecaster, mock_db):
        """Test fallback to static when all historical data is insufficient."""
        with (
            patch.object(
                forecaster,
                "_get_train_id_stats",
                return_value=None,
            ),
            patch.object(
                forecaster,
                "_get_line_code_stats",
                return_value=None,
            ),
            patch.object(
                forecaster,
                "_get_data_source_stats",
                return_value=DelayStats(
                    sample_count=30,  # Below MIN_DATA_SOURCE_SAMPLES (50)
                    cancellation_count=5,
                    on_time_count=70,
                    slight_delay_count=15,
                    significant_delay_count=7,
                    major_delay_count=3,
                    total_delay_minutes=500,
                    level="data_source",
                ),
            ),
        ):
            forecast = await forecaster.forecast(
                train_id="TEST123",
                station_code="NY",
                origin_station_code="NY",
                line_code="NE",
                data_source="NJT",
                journey_date=date.today(),
                scheduled_departure=datetime.now(),
                db=mock_db,
            )

            assert "static_fallback" in forecast.factors
            assert forecast.confidence == "low"

    @pytest.mark.asyncio
    async def test_forecast_applies_congestion_multiplier(self, forecaster, mock_db):
        """Test that live congestion affects forecast."""
        with (
            patch.object(
                forecaster,
                "_get_train_id_stats",
                return_value=DelayStats(
                    sample_count=50,
                    cancellation_count=2,
                    on_time_count=40,
                    slight_delay_count=5,
                    significant_delay_count=2,
                    major_delay_count=1,
                    total_delay_minutes=100,
                    level="train_id",
                ),
            ),
            patch.object(forecaster, "_get_line_code_stats", return_value=None),
            patch.object(forecaster, "_get_data_source_stats", return_value=None),
            patch.object(forecaster, "_get_hour_day_adjustment", return_value=1.0),
            patch.object(forecaster, "_get_congestion_multiplier", return_value=1.5),
        ):
            forecast = await forecaster.forecast(
                train_id="TEST123",
                station_code="NY",
                origin_station_code="NY",
                line_code="NE",
                data_source="NJT",
                journey_date=date.today(),
                scheduled_departure=datetime.now(),
                db=mock_db,
            )

            assert "live_congestion" in forecast.factors

    @pytest.mark.asyncio
    async def test_forecast_applies_time_pattern(self, forecaster, mock_db):
        """Test that hour/day pattern affects forecast."""
        with (
            patch.object(
                forecaster,
                "_get_train_id_stats",
                return_value=DelayStats(
                    sample_count=50,
                    cancellation_count=2,
                    on_time_count=40,
                    slight_delay_count=5,
                    significant_delay_count=2,
                    major_delay_count=1,
                    total_delay_minutes=100,
                    level="train_id",
                ),
            ),
            patch.object(forecaster, "_get_line_code_stats", return_value=None),
            patch.object(forecaster, "_get_data_source_stats", return_value=None),
            patch.object(forecaster, "_get_hour_day_adjustment", return_value=1.3),
            patch.object(forecaster, "_get_congestion_multiplier", return_value=1.0),
        ):
            forecast = await forecaster.forecast(
                train_id="TEST123",
                station_code="NY",
                origin_station_code="NY",
                line_code="NE",
                data_source="NJT",
                journey_date=date.today(),
                scheduled_departure=datetime.now(),
                db=mock_db,
            )

            assert "time_pattern" in forecast.factors


class TestDelayStatsQueries:
    """Test the database query methods."""

    @pytest.mark.asyncio
    async def test_get_train_id_stats_returns_none_for_no_data(self, forecaster):
        """Test that missing data returns None."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock empty result
        mock_result = MagicMock()
        mock_result.one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        stats = await forecaster._get_train_id_stats(
            mock_db, "NONEXISTENT", "XX", "NJT"
        )

        assert stats is None

    @pytest.mark.asyncio
    async def test_get_train_id_stats_returns_stats_for_valid_data(self, forecaster):
        """Test that valid data returns DelayStats."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock result with data
        mock_row = MagicMock()
        mock_row.total = 50
        mock_row.cancelled = 2
        mock_row.on_time = 40
        mock_row.slight = 5
        mock_row.significant = 2
        mock_row.major = 1
        mock_row.total_delay = 100

        mock_result = MagicMock()
        mock_result.one_or_none.return_value = mock_row
        mock_db.execute.return_value = mock_result

        stats = await forecaster._get_train_id_stats(mock_db, "TEST123", "NY", "NJT")

        assert stats is not None
        assert stats.sample_count == 50
        assert stats.cancellation_count == 2
        assert stats.level == "train_id"

    @pytest.mark.asyncio
    async def test_get_hour_day_adjustment_returns_1_for_insufficient_data(
        self, forecaster
    ):
        """Test that insufficient data returns neutral adjustment."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock insufficient overall data
        mock_row = MagicMock()
        mock_row.total = 50  # Below 100 threshold
        mock_row.delayed = 10

        mock_result = MagicMock()
        mock_result.one_or_none.return_value = mock_row
        mock_db.execute.return_value = mock_result

        adjustment = await forecaster._get_hour_day_adjustment(
            mock_db, "NY", "NJT", hour=8, day_of_week=1
        )

        assert adjustment == 1.0

    @pytest.mark.asyncio
    async def test_get_congestion_multiplier_handles_errors(self, forecaster):
        """Test graceful handling of congestion service errors."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock congestion analyzer to raise exception
        with patch.object(
            forecaster.congestion_analyzer,
            "get_network_congestion_optimized",
            side_effect=Exception("Database error"),
        ):
            multiplier = await forecaster._get_congestion_multiplier(
                mock_db, "NY", "NJT"
            )

            # Should return neutral multiplier on error
            assert multiplier == 1.0

    @pytest.mark.asyncio
    async def test_get_congestion_multiplier_returns_average_factor(self, forecaster):
        """Test congestion multiplier calculation."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Create mock congestion segments
        mock_segment_1 = MagicMock()
        mock_segment_1.from_station = "NY"
        mock_segment_1.congestion_factor = 1.3

        mock_segment_2 = MagicMock()
        mock_segment_2.from_station = "NY"
        mock_segment_2.congestion_factor = 1.5

        mock_segment_3 = MagicMock()
        mock_segment_3.from_station = "NP"  # Different station
        mock_segment_3.congestion_factor = 2.0

        with patch.object(
            forecaster.congestion_analyzer,
            "get_network_congestion_optimized",
            return_value=[mock_segment_1, mock_segment_2, mock_segment_3],
        ):
            multiplier = await forecaster._get_congestion_multiplier(
                mock_db, "NY", "NJT"
            )

            # Should average only NY segments (1.3 + 1.5) / 2 = 1.4
            assert multiplier == pytest.approx(1.4, rel=0.01)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_non_cancelled_journeys(self, forecaster):
        """Test handling when all journeys are cancelled."""
        stats = DelayStats(
            sample_count=10,
            cancellation_count=10,  # All cancelled
            on_time_count=0,
            slight_delay_count=0,
            significant_delay_count=0,
            major_delay_count=0,
            total_delay_minutes=0,
            level="train_id",
        )

        forecast = forecaster._calculate_probabilities(stats)

        # Should use defaults for delay breakdown
        assert forecast.cancellation_probability == 1.0
        assert forecast.on_time_probability > 0  # Default values
        assert forecast.expected_delay_minutes == 0

    def test_high_cancellation_rate(self, forecaster):
        """Test handling of high cancellation rates."""
        stats = DelayStats(
            sample_count=100,
            cancellation_count=50,  # 50% cancelled
            on_time_count=40,
            slight_delay_count=7,
            significant_delay_count=2,
            major_delay_count=1,
            total_delay_minutes=200,
            level="train_id",
        )

        forecast = forecaster._calculate_probabilities(stats)

        assert forecast.cancellation_probability == pytest.approx(0.5, rel=0.01)

    def test_adjustment_capped_at_maximum(self, forecaster):
        """Test that on_time probability doesn't go below minimum."""
        stats = DelayStats(
            sample_count=100,
            cancellation_count=5,
            on_time_count=70,
            slight_delay_count=15,
            significant_delay_count=7,
            major_delay_count=3,
            total_delay_minutes=400,
            level="train_id",
        )
        base_forecast = forecaster._calculate_probabilities(stats)

        # Apply very high multiplier
        adjusted = forecaster._apply_adjustment(base_forecast, 10.0)

        # On-time should not go below 0.1
        assert adjusted.on_time_probability >= 0.1

        # Total should still sum to 1.0
        total = (
            adjusted.on_time_probability
            + adjusted.slight_delay_probability
            + adjusted.significant_delay_probability
            + adjusted.major_delay_probability
        )
        assert total == pytest.approx(1.0, rel=0.01)


class TestHelperMethods:
    """Test the extracted helper methods."""

    def test_row_to_delay_stats_returns_none_for_none_row(self, forecaster):
        """Test that None row returns None."""
        assert forecaster._row_to_delay_stats(None, "train_id") is None

    def test_row_to_delay_stats_returns_none_for_zero_total(self, forecaster):
        """Test that row with total=0 returns None."""
        mock_row = MagicMock()
        mock_row.total = 0
        assert forecaster._row_to_delay_stats(mock_row, "train_id") is None

    def test_row_to_delay_stats_converts_valid_row(self, forecaster):
        """Test that valid row is converted to DelayStats correctly."""
        mock_row = MagicMock()
        mock_row.total = 100
        mock_row.cancelled = 5
        mock_row.on_time = 70
        mock_row.slight = 15
        mock_row.significant = 7
        mock_row.major = 3
        mock_row.total_delay = 400

        stats = forecaster._row_to_delay_stats(mock_row, "line_code")

        assert stats is not None
        assert stats.sample_count == 100
        assert stats.cancellation_count == 5
        assert stats.on_time_count == 70
        assert stats.slight_delay_count == 15
        assert stats.significant_delay_count == 7
        assert stats.major_delay_count == 3
        assert stats.total_delay_minutes == 400
        assert stats.level == "line_code"

    def test_row_to_delay_stats_handles_none_values(self, forecaster):
        """Test that None values in row columns default to 0."""
        mock_row = MagicMock()
        mock_row.total = 10
        mock_row.cancelled = None
        mock_row.on_time = None
        mock_row.slight = None
        mock_row.significant = None
        mock_row.major = None
        mock_row.total_delay = None

        stats = forecaster._row_to_delay_stats(mock_row, "data_source")

        assert stats is not None
        assert stats.cancellation_count == 0
        assert stats.on_time_count == 0
        assert stats.total_delay_minutes == 0


class TestStopLevelForecasting:
    """Test the stop-level forecasting hierarchy."""

    @pytest.mark.asyncio
    async def test_mid_route_station_uses_stop_level_stats(self, forecaster, mock_db):
        """Test that a mid-route station tries stop-level stats first."""
        stop_stats = DelayStats(
            sample_count=30,  # Above MIN_TRAIN_ID_SAMPLES
            cancellation_count=1,
            on_time_count=20,
            slight_delay_count=6,
            significant_delay_count=2,
            major_delay_count=1,
            total_delay_minutes=80,
            level="train_id",
        )

        with (
            patch.object(
                forecaster, "_get_stop_train_id_stats", return_value=stop_stats
            ) as mock_stop,
            # Origin-level methods should NOT be called
            patch.object(
                forecaster, "_get_train_id_stats", return_value=None
            ) as mock_origin,
            patch.object(forecaster, "_get_line_code_stats", return_value=None),
            patch.object(forecaster, "_get_data_source_stats", return_value=None),
            patch.object(forecaster, "_get_hour_day_adjustment", return_value=1.0),
            patch.object(forecaster, "_get_congestion_multiplier", return_value=1.0),
        ):
            forecast = await forecaster.forecast(
                train_id="TEST123",
                station_code="NP",  # Newark Penn (mid-route)
                origin_station_code="NY",  # NY Penn (origin)
                line_code="NE",
                data_source="NJT",
                journey_date=date.today(),
                scheduled_departure=datetime.now(),
                db=mock_db,
            )

            # Should use stop-level stats
            assert "train_history" in forecast.factors
            assert "stop_level" in forecast.factors
            assert forecast.confidence == "high"
            mock_stop.assert_called_once()
            # Origin-level should not be called since stop-level succeeded
            mock_origin.assert_not_called()

    @pytest.mark.asyncio
    async def test_mid_route_falls_back_to_stop_line_code(self, forecaster, mock_db):
        """Test fallback from stop train_id to stop line_code."""
        stop_line_stats = DelayStats(
            sample_count=100,  # Above MIN_LINE_CODE_SAMPLES
            cancellation_count=5,
            on_time_count=70,
            slight_delay_count=15,
            significant_delay_count=7,
            major_delay_count=3,
            total_delay_minutes=500,
            level="line_code",
        )

        with (
            patch.object(forecaster, "_get_stop_train_id_stats", return_value=None),
            patch.object(
                forecaster, "_get_stop_line_code_stats", return_value=stop_line_stats
            ) as mock_stop_line,
            patch.object(forecaster, "_get_train_id_stats", return_value=None),
            patch.object(forecaster, "_get_line_code_stats", return_value=None),
            patch.object(forecaster, "_get_data_source_stats", return_value=None),
            patch.object(forecaster, "_get_hour_day_adjustment", return_value=1.0),
            patch.object(forecaster, "_get_congestion_multiplier", return_value=1.0),
        ):
            forecast = await forecaster.forecast(
                train_id="TEST123",
                station_code="NP",
                origin_station_code="NY",
                line_code="NE",
                data_source="NJT",
                journey_date=date.today(),
                scheduled_departure=datetime.now(),
                db=mock_db,
            )

            assert "line_pattern" in forecast.factors
            assert "stop_level" in forecast.factors
            assert forecast.confidence == "medium"
            mock_stop_line.assert_called_once()

    @pytest.mark.asyncio
    async def test_mid_route_falls_back_to_origin_level(self, forecaster, mock_db):
        """Test that insufficient stop-level data falls back to origin-level."""
        origin_stats = DelayStats(
            sample_count=50,  # Above MIN_TRAIN_ID_SAMPLES
            cancellation_count=2,
            on_time_count=40,
            slight_delay_count=5,
            significant_delay_count=2,
            major_delay_count=1,
            total_delay_minutes=100,
            level="train_id",
        )

        with (
            # All stop-level methods return insufficient data
            patch.object(forecaster, "_get_stop_train_id_stats", return_value=None),
            patch.object(forecaster, "_get_stop_line_code_stats", return_value=None),
            patch.object(forecaster, "_get_stop_data_source_stats", return_value=None),
            # Origin-level succeeds
            patch.object(
                forecaster, "_get_train_id_stats", return_value=origin_stats
            ) as mock_origin,
            patch.object(forecaster, "_get_line_code_stats", return_value=None),
            patch.object(forecaster, "_get_data_source_stats", return_value=None),
            patch.object(forecaster, "_get_hour_day_adjustment", return_value=1.0),
            patch.object(forecaster, "_get_congestion_multiplier", return_value=1.0),
        ):
            forecast = await forecaster.forecast(
                train_id="TEST123",
                station_code="NP",
                origin_station_code="NY",
                line_code="NE",
                data_source="NJT",
                journey_date=date.today(),
                scheduled_departure=datetime.now(),
                db=mock_db,
            )

            # Should use origin-level, NOT stop-level
            assert "train_history" in forecast.factors
            assert "stop_level" not in forecast.factors
            assert forecast.confidence == "high"
            mock_origin.assert_called_once()

    @pytest.mark.asyncio
    async def test_origin_station_skips_stop_level(self, forecaster, mock_db):
        """Test that when station == origin, stop-level queries are skipped entirely."""
        origin_stats = DelayStats(
            sample_count=50,
            cancellation_count=2,
            on_time_count=40,
            slight_delay_count=5,
            significant_delay_count=2,
            major_delay_count=1,
            total_delay_minutes=100,
            level="train_id",
        )

        with (
            # Stop-level methods should NOT be called
            patch.object(
                forecaster, "_get_stop_train_id_stats", return_value=None
            ) as mock_stop_train,
            patch.object(
                forecaster, "_get_stop_line_code_stats", return_value=None
            ) as mock_stop_line,
            patch.object(
                forecaster, "_get_stop_data_source_stats", return_value=None
            ) as mock_stop_ds,
            # Origin-level succeeds
            patch.object(forecaster, "_get_train_id_stats", return_value=origin_stats),
            patch.object(forecaster, "_get_line_code_stats", return_value=None),
            patch.object(forecaster, "_get_data_source_stats", return_value=None),
            patch.object(forecaster, "_get_hour_day_adjustment", return_value=1.0),
            patch.object(forecaster, "_get_congestion_multiplier", return_value=1.0),
        ):
            forecast = await forecaster.forecast(
                train_id="TEST123",
                station_code="NY",  # Same as origin
                origin_station_code="NY",
                line_code="NE",
                data_source="NJT",
                journey_date=date.today(),
                scheduled_departure=datetime.now(),
                db=mock_db,
            )

            # Stop-level should never be called
            mock_stop_train.assert_not_called()
            mock_stop_line.assert_not_called()
            mock_stop_ds.assert_not_called()

            # Should use origin-level without stop_level factor
            assert "train_history" in forecast.factors
            assert "stop_level" not in forecast.factors

    @pytest.mark.asyncio
    async def test_mid_route_uses_stop_data_source_stats(self, forecaster, mock_db):
        """Test fallback to stop-level data_source stats."""
        stop_ds_stats = DelayStats(
            sample_count=500,  # Above MIN_DATA_SOURCE_SAMPLES
            cancellation_count=15,
            on_time_count=350,
            slight_delay_count=100,
            significant_delay_count=25,
            major_delay_count=10,
            total_delay_minutes=2000,
            level="data_source",
        )

        with (
            patch.object(forecaster, "_get_stop_train_id_stats", return_value=None),
            patch.object(forecaster, "_get_stop_line_code_stats", return_value=None),
            patch.object(
                forecaster, "_get_stop_data_source_stats", return_value=stop_ds_stats
            ),
            patch.object(forecaster, "_get_train_id_stats", return_value=None),
            patch.object(forecaster, "_get_line_code_stats", return_value=None),
            patch.object(forecaster, "_get_data_source_stats", return_value=None),
            patch.object(forecaster, "_get_hour_day_adjustment", return_value=1.0),
            patch.object(forecaster, "_get_congestion_multiplier", return_value=1.0),
        ):
            forecast = await forecaster.forecast(
                train_id="TEST123",
                station_code="JAM",
                origin_station_code="NY",
                line_code="OyBay",
                data_source="LIRR",
                journey_date=date.today(),
                scheduled_departure=datetime.now(),
                db=mock_db,
            )

            assert "service_pattern" in forecast.factors
            assert "stop_level" in forecast.factors
            assert forecast.confidence == "low"

    @pytest.mark.asyncio
    async def test_congestion_uses_boarding_station(self, forecaster, mock_db):
        """Test that congestion multiplier uses the user's boarding station, not origin."""
        origin_stats = DelayStats(
            sample_count=50,
            cancellation_count=2,
            on_time_count=40,
            slight_delay_count=5,
            significant_delay_count=2,
            major_delay_count=1,
            total_delay_minutes=100,
            level="train_id",
        )

        with (
            patch.object(forecaster, "_get_stop_train_id_stats", return_value=None),
            patch.object(forecaster, "_get_stop_line_code_stats", return_value=None),
            patch.object(forecaster, "_get_stop_data_source_stats", return_value=None),
            patch.object(forecaster, "_get_train_id_stats", return_value=origin_stats),
            patch.object(forecaster, "_get_line_code_stats", return_value=None),
            patch.object(forecaster, "_get_data_source_stats", return_value=None),
            patch.object(forecaster, "_get_hour_day_adjustment", return_value=1.0),
            patch.object(
                forecaster, "_get_congestion_multiplier", return_value=1.3
            ) as mock_congestion,
        ):
            forecast = await forecaster.forecast(
                train_id="TEST123",
                station_code="NP",  # User boards at Newark
                origin_station_code="NY",  # Train origin is NY Penn
                line_code="NE",
                data_source="NJT",
                journey_date=date.today(),
                scheduled_departure=datetime.now(),
                db=mock_db,
            )

            # Congestion should be called with NP (user's station), not NY (origin)
            mock_congestion.assert_called_once_with(mock_db, "NP", "NJT")
            assert "live_congestion" in forecast.factors

    @pytest.mark.asyncio
    async def test_hour_day_uses_origin_station(self, forecaster, mock_db):
        """Test that hour/day adjustment uses the origin station for time patterns."""
        origin_stats = DelayStats(
            sample_count=50,
            cancellation_count=2,
            on_time_count=40,
            slight_delay_count=5,
            significant_delay_count=2,
            major_delay_count=1,
            total_delay_minutes=100,
            level="train_id",
        )

        with (
            patch.object(forecaster, "_get_stop_train_id_stats", return_value=None),
            patch.object(forecaster, "_get_stop_line_code_stats", return_value=None),
            patch.object(forecaster, "_get_stop_data_source_stats", return_value=None),
            patch.object(forecaster, "_get_train_id_stats", return_value=origin_stats),
            patch.object(forecaster, "_get_line_code_stats", return_value=None),
            patch.object(forecaster, "_get_data_source_stats", return_value=None),
            patch.object(
                forecaster, "_get_hour_day_adjustment", return_value=1.2
            ) as mock_hour_day,
            patch.object(forecaster, "_get_congestion_multiplier", return_value=1.0),
        ):
            sched_dep = datetime(2026, 2, 8, 8, 30)  # 8:30 AM on a Sunday (dow=6)

            forecast = await forecaster.forecast(
                train_id="TEST123",
                station_code="NP",
                origin_station_code="NY",
                line_code="NE",
                data_source="NJT",
                journey_date=date.today(),
                scheduled_departure=sched_dep,
                db=mock_db,
            )

            # Hour/day should be called with NY (origin), not NP (user's station)
            mock_hour_day.assert_called_once_with(
                mock_db, "NY", "NJT", sched_dep.hour, sched_dep.weekday()
            )
            assert "time_pattern" in forecast.factors

    @pytest.mark.asyncio
    async def test_stop_level_insufficient_falls_through_entire_chain(
        self, forecaster, mock_db
    ):
        """Test that insufficient stop AND origin data falls to static."""
        with (
            patch.object(forecaster, "_get_stop_train_id_stats", return_value=None),
            patch.object(forecaster, "_get_stop_line_code_stats", return_value=None),
            patch.object(forecaster, "_get_stop_data_source_stats", return_value=None),
            patch.object(forecaster, "_get_train_id_stats", return_value=None),
            patch.object(forecaster, "_get_line_code_stats", return_value=None),
            patch.object(forecaster, "_get_data_source_stats", return_value=None),
        ):
            forecast = await forecaster.forecast(
                train_id="TEST123",
                station_code="NP",
                origin_station_code="NY",
                line_code="NE",
                data_source="NJT",
                journey_date=date.today(),
                scheduled_departure=datetime.now(),
                db=mock_db,
            )

            assert "static_fallback" in forecast.factors
            assert forecast.confidence == "low"
            assert forecast.sample_count == 0


class TestStopLevelQueries:
    """Test the stop-level database query methods."""

    @pytest.mark.asyncio
    async def test_get_stop_train_id_stats_returns_none_for_no_data(self, forecaster):
        """Test that missing stop-level data returns None."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_result = MagicMock()
        mock_result.one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        stats = await forecaster._get_stop_train_id_stats(
            mock_db, "NONEXISTENT", "XX", "NJT"
        )

        assert stats is None

    @pytest.mark.asyncio
    async def test_get_stop_train_id_stats_returns_stats_for_valid_data(
        self, forecaster
    ):
        """Test that valid stop-level data returns DelayStats."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_row = MagicMock()
        mock_row.total = 30
        mock_row.cancelled = 1
        mock_row.on_time = 20
        mock_row.slight = 6
        mock_row.significant = 2
        mock_row.major = 1
        mock_row.total_delay = 80

        mock_result = MagicMock()
        mock_result.one_or_none.return_value = mock_row
        mock_db.execute.return_value = mock_result

        stats = await forecaster._get_stop_train_id_stats(
            mock_db, "TEST123", "NP", "NJT"
        )

        assert stats is not None
        assert stats.sample_count == 30
        assert stats.cancellation_count == 1
        assert stats.level == "train_id"

    @pytest.mark.asyncio
    async def test_get_stop_line_code_stats_returns_none_for_no_data(self, forecaster):
        """Test that missing stop-level line data returns None."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_result = MagicMock()
        mock_result.one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        stats = await forecaster._get_stop_line_code_stats(mock_db, "NE", "XX", "NJT")

        assert stats is None

    @pytest.mark.asyncio
    async def test_get_stop_data_source_stats_returns_stats(self, forecaster):
        """Test that stop-level data source stats work correctly."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_row = MagicMock()
        mock_row.total = 500
        mock_row.cancelled = 15
        mock_row.on_time = 350
        mock_row.slight = 100
        mock_row.significant = 25
        mock_row.major = 10
        mock_row.total_delay = 2000

        mock_result = MagicMock()
        mock_result.one_or_none.return_value = mock_row
        mock_db.execute.return_value = mock_result

        stats = await forecaster._get_stop_data_source_stats(mock_db, "JAM", "LIRR")

        assert stats is not None
        assert stats.sample_count == 500
        assert stats.level == "data_source"
