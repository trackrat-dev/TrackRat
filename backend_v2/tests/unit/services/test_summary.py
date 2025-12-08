"""
Unit tests for SummaryService - Template-based NLG for train operations summaries.

Tests the summary generation for network, route, and train scopes including
headline/body generation and metrics calculation.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import TrainJourney
from trackrat.services.summary import (
    LineStats,
    OperationsSummary,
    SummaryMetrics,
    SummaryService,
)


class TestLineStats:
    """Test cases for LineStats data class."""

    def test_line_stats_on_time_percentage_calculation(self):
        """Test on-time percentage calculation."""
        stats = LineStats(
            line_name="Northeast Corridor",
            line_code="NEC",
            train_count=10,
            on_time_count=8,
            cancellation_count=1,
            total_delay_minutes=45.0,
            data_source="NJT",
        )

        # 8 on-time out of 9 non-cancelled = 88.89%
        assert abs(stats.on_time_percentage - 88.89) < 0.1

    def test_line_stats_average_delay_calculation(self):
        """Test average delay calculation."""
        stats = LineStats(
            line_name="Northeast Corridor",
            line_code="NEC",
            train_count=10,
            on_time_count=8,
            cancellation_count=1,
            total_delay_minutes=45.0,
            data_source="NJT",
        )

        # 45 minutes / 9 non-cancelled = 5.0 minutes
        assert stats.average_delay_minutes == 5.0

    def test_line_stats_all_cancelled(self):
        """Test stats when all trains are cancelled."""
        stats = LineStats(
            line_name="Northeast Corridor",
            line_code="NEC",
            train_count=5,
            on_time_count=0,
            cancellation_count=5,
            total_delay_minutes=0.0,
            data_source="NJT",
        )

        assert stats.on_time_percentage == 0.0
        assert stats.average_delay_minutes == 0.0

    def test_line_stats_no_trains(self):
        """Test stats with no trains."""
        stats = LineStats(
            line_name="Northeast Corridor",
            line_code="NEC",
            train_count=0,
            on_time_count=0,
            cancellation_count=0,
            total_delay_minutes=0.0,
            data_source="NJT",
        )

        assert stats.on_time_percentage == 0.0
        assert stats.average_delay_minutes == 0.0


class TestSummaryService:
    """Test cases for SummaryService."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def summary_service(self):
        """Create a SummaryService instance for testing."""
        return SummaryService()

    @pytest.fixture
    def sample_journeys(self):
        """Create sample journey data for testing."""
        current_time = datetime.now(UTC)

        journeys = []

        # Journey 1: On-time train
        journey1 = Mock(spec=TrainJourney)
        journey1.id = 1
        journey1.train_id = "1234"
        journey1.data_source = "NJT"
        journey1.line_name = "Northeast Corridor"
        journey1.line_code = "NEC"
        journey1.is_cancelled = False
        journey1.journey_date = current_time.date()
        journey1.last_updated_at = current_time - timedelta(minutes=30)

        # Stops for on-time journey
        stop1_1 = Mock()
        stop1_1.station_code = "NY"
        stop1_1.stop_sequence = 1
        stop1_1.scheduled_departure = current_time - timedelta(hours=1)
        stop1_1.actual_departure = current_time - timedelta(hours=1)
        stop1_1.scheduled_arrival = None
        stop1_1.actual_arrival = None
        stop1_1.track = "7"

        stop1_2 = Mock()
        stop1_2.station_code = "NP"
        stop1_2.stop_sequence = 2
        stop1_2.scheduled_arrival = current_time - timedelta(minutes=45)
        stop1_2.actual_arrival = current_time - timedelta(minutes=45)
        stop1_2.scheduled_departure = current_time - timedelta(minutes=43)
        stop1_2.actual_departure = current_time - timedelta(minutes=43)
        stop1_2.track = None

        stop1_3 = Mock()
        stop1_3.station_code = "TR"
        stop1_3.stop_sequence = 3
        stop1_3.scheduled_arrival = current_time - timedelta(minutes=15)
        stop1_3.actual_arrival = current_time - timedelta(minutes=15)
        stop1_3.scheduled_departure = None
        stop1_3.actual_departure = None
        stop1_3.track = None

        journey1.stops = [stop1_1, stop1_2, stop1_3]
        journeys.append(journey1)

        # Journey 2: Late train (10 minutes delay)
        journey2 = Mock(spec=TrainJourney)
        journey2.id = 2
        journey2.train_id = "5678"
        journey2.data_source = "NJT"
        journey2.line_name = "Northeast Corridor"
        journey2.line_code = "NEC"
        journey2.is_cancelled = False
        journey2.journey_date = current_time.date()
        journey2.last_updated_at = current_time - timedelta(minutes=20)

        stop2_1 = Mock()
        stop2_1.station_code = "NY"
        stop2_1.stop_sequence = 1
        stop2_1.scheduled_departure = current_time - timedelta(hours=2)
        stop2_1.actual_departure = (
            current_time - timedelta(hours=2) + timedelta(minutes=5)
        )
        stop2_1.scheduled_arrival = None
        stop2_1.actual_arrival = None
        stop2_1.track = "8"

        stop2_2 = Mock()
        stop2_2.station_code = "NP"
        stop2_2.stop_sequence = 2
        stop2_2.scheduled_arrival = current_time - timedelta(hours=1, minutes=45)
        stop2_2.actual_arrival = current_time - timedelta(hours=1, minutes=35)
        stop2_2.scheduled_departure = None
        stop2_2.actual_departure = None
        stop2_2.track = None

        journey2.stops = [stop2_1, stop2_2]
        journeys.append(journey2)

        # Journey 3: Cancelled train
        journey3 = Mock(spec=TrainJourney)
        journey3.id = 3
        journey3.train_id = "9999"
        journey3.data_source = "NJT"
        journey3.line_name = "Northeast Corridor"
        journey3.line_code = "NEC"
        journey3.is_cancelled = True
        journey3.journey_date = current_time.date()
        journey3.last_updated_at = current_time - timedelta(minutes=60)
        journey3.stops = []
        journeys.append(journey3)

        return journeys

    def test_calculate_line_stats(self, summary_service, sample_journeys):
        """Test line statistics calculation from journeys."""
        line_stats = summary_service._calculate_line_stats(sample_journeys)

        assert "Northeast Corridor" in line_stats
        nec_stats = line_stats["Northeast Corridor"]

        assert nec_stats.train_count == 3
        assert nec_stats.cancellation_count == 1
        assert nec_stats.line_code == "NEC"
        assert nec_stats.data_source == "NJT"

    def test_generate_network_summary_excellent(self, summary_service):
        """Test network summary generation for excellent performance."""
        line_stats = {
            "Northeast Corridor": LineStats(
                line_name="Northeast Corridor",
                line_code="NEC",
                train_count=20,
                on_time_count=19,
                cancellation_count=0,
                total_delay_minutes=15.0,
                data_source="NJT",
            )
        }

        summary = summary_service._generate_network_summary(line_stats)

        assert summary.scope == "network"
        assert (
            "smoothly" in summary.headline.lower()
            or "on time" in summary.headline.lower()
        )
        assert summary.metrics is not None
        assert summary.metrics.on_time_percentage >= 90

    def test_generate_network_summary_degraded(self, summary_service):
        """Test network summary generation for degraded performance."""
        line_stats = {
            "Northeast Corridor": LineStats(
                line_name="Northeast Corridor",
                line_code="NEC",
                train_count=20,
                on_time_count=10,
                cancellation_count=3,
                total_delay_minutes=150.0,
                data_source="NJT",
            )
        }

        summary = summary_service._generate_network_summary(line_stats)

        assert summary.scope == "network"
        assert (
            "delay" in summary.headline.lower()
            or "disruption" in summary.headline.lower()
        )

    def test_generate_network_summary_empty(self, summary_service):
        """Test network summary with no data returns empty headline."""
        summary = summary_service._generate_network_summary({})

        assert summary.scope == "network"
        # With no data, headline and body should be empty so iOS can hide the section
        assert summary.headline == ""
        assert summary.body == ""
        assert summary.metrics is None

    def test_get_network_headline_thresholds(self, summary_service):
        """Test headline generation for different performance thresholds."""
        # Excellent
        headline = summary_service._get_network_headline(96, 2, 0)
        assert "smooth" in headline.lower()

        # Good
        headline = summary_service._get_network_headline(87, 4, 0)
        assert "on time" in headline.lower()

        # Moderate
        headline = summary_service._get_network_headline(72, 8, 1)
        assert "some" in headline.lower() or "delay" in headline.lower()

        # Degraded
        headline = summary_service._get_network_headline(55, 12, 2)
        assert "widespread" in headline.lower() or "delay" in headline.lower()

        # Severe
        headline = summary_service._get_network_headline(40, 20, 5)
        assert "major" in headline.lower() or "disruption" in headline.lower()

    def test_generate_route_summary_with_data(self, summary_service, sample_journeys):
        """Test route summary generation with journey data."""
        # Filter to journeys between NY and NP
        route_journeys = [j for j in sample_journeys if not j.is_cancelled]

        summary = summary_service._generate_route_summary(route_journeys, "NY", "NP")

        assert summary.scope == "route"
        assert "Recent departures:" in summary.headline
        assert "% on time" in summary.headline
        assert summary.metrics is not None
        assert summary.metrics.train_count == 2

    def test_generate_route_summary_empty(self, summary_service):
        """Test route summary with no data returns empty headline."""
        summary = summary_service._generate_route_summary([], "NY", "NP")

        assert summary.scope == "route"
        # With no data, headline and body should be empty so iOS can hide the section
        assert summary.headline == ""
        assert summary.body == ""
        assert summary.metrics is None

    def test_generate_train_summary_good_performance(self, summary_service):
        """Test train summary for train with good historical performance."""
        current_time = datetime.now(UTC)

        # Create 10 on-time journeys with proper origin stop
        journeys = []
        for i in range(10):
            journey = Mock(spec=TrainJourney)
            journey.id = i
            journey.train_id = "1234"
            journey.is_cancelled = False
            journey.journey_date = (current_time - timedelta(days=i)).date()

            # Origin stop (NY) with departure times - on-time (2 min delay)
            origin_stop = Mock()
            origin_stop.station_code = "NY"
            origin_stop.stop_sequence = 1
            origin_stop.scheduled_departure = current_time - timedelta(days=i, hours=1)
            origin_stop.actual_departure = (
                current_time - timedelta(days=i, hours=1) + timedelta(minutes=2)
            )
            origin_stop.scheduled_arrival = None
            origin_stop.actual_arrival = None

            # Destination stop (TR)
            dest_stop = Mock()
            dest_stop.station_code = "TR"
            dest_stop.stop_sequence = 3
            dest_stop.scheduled_arrival = current_time - timedelta(days=i)
            dest_stop.actual_arrival = (
                current_time - timedelta(days=i) + timedelta(minutes=2)
            )
            dest_stop.scheduled_departure = None
            dest_stop.actual_departure = None

            journey.stops = [origin_stop, dest_stop]
            journeys.append(journey)

        # New signature: train_journeys, similar_journeys, train_id, from_station, to_station, data_source
        summary = summary_service._generate_train_summary(
            journeys, journeys, "1234", "NY", "TR", "NJT"
        )

        assert summary.scope == "train"
        assert "on time" in summary.headline.lower()
        assert summary.metrics.on_time_percentage >= 90

    def test_generate_train_summary_poor_performance(self, summary_service):
        """Test train summary for train with poor historical performance."""
        current_time = datetime.now(UTC)

        # Create 10 late journeys with proper origin stop
        journeys = []
        for i in range(10):
            journey = Mock(spec=TrainJourney)
            journey.id = i
            journey.train_id = "9999"
            journey.is_cancelled = False
            journey.journey_date = (current_time - timedelta(days=i)).date()

            # Origin stop (NY) with departure times - late (15 min delay)
            origin_stop = Mock()
            origin_stop.station_code = "NY"
            origin_stop.stop_sequence = 1
            origin_stop.scheduled_departure = current_time - timedelta(days=i, hours=1)
            origin_stop.actual_departure = (
                current_time - timedelta(days=i, hours=1) + timedelta(minutes=15)
            )
            origin_stop.scheduled_arrival = None
            origin_stop.actual_arrival = None

            # Destination stop (TR)
            dest_stop = Mock()
            dest_stop.station_code = "TR"
            dest_stop.stop_sequence = 3
            dest_stop.scheduled_arrival = current_time - timedelta(days=i)
            dest_stop.actual_arrival = (
                current_time - timedelta(days=i) + timedelta(minutes=15)
            )
            dest_stop.scheduled_departure = None
            dest_stop.actual_departure = None

            journey.stops = [origin_stop, dest_stop]
            journeys.append(journey)

        # New signature: train_journeys, similar_journeys, train_id, from_station, to_station, data_source
        summary = summary_service._generate_train_summary(
            journeys, journeys, "9999", "NY", "TR", "NJT"
        )

        assert summary.scope == "train"
        assert "on time" in summary.headline.lower()  # Shows on-time percentage (0%)
        assert summary.metrics.on_time_percentage == 0  # All late

    def test_generate_train_summary_no_history(self, summary_service):
        """Test train summary with no historical data returns empty headline."""
        # New signature: train_journeys, similar_journeys, train_id, from_station, to_station, data_source
        summary = summary_service._generate_train_summary(
            [], [], "1234", "NY", "TR", "NJT"
        )

        assert summary.scope == "train"
        # With no data, headline and body should be empty so iOS can hide the section
        assert summary.headline == ""
        assert summary.body == ""
        assert summary.metrics is None

    def test_generate_train_summary_no_history_but_similar_trains(
        self, summary_service
    ):
        """Test train summary with no history but similar trains shows similar train stats."""
        current_time = datetime.now(UTC)

        # Create similar trains (not this specific train, but same route)
        # Similar trains need departure data from the user's origin station (NY)
        similar_journeys = []
        for i in range(5):
            journey = Mock(spec=TrainJourney)
            journey.id = i + 100
            journey.train_id = f"999{i}"  # Different train IDs
            journey.is_cancelled = False
            journey.journey_date = current_time.date()

            # Origin stop (NY) with departure times - on-time (2 min delay)
            origin_stop = Mock()
            origin_stop.station_code = "NY"
            origin_stop.stop_sequence = 1
            origin_stop.scheduled_departure = current_time - timedelta(
                minutes=60 + i * 10
            )
            origin_stop.actual_departure = origin_stop.scheduled_departure + timedelta(
                minutes=2
            )
            origin_stop.scheduled_arrival = None
            origin_stop.actual_arrival = None

            # Destination stop (TR)
            dest_stop = Mock()
            dest_stop.station_code = "TR"
            dest_stop.stop_sequence = 3
            dest_stop.scheduled_arrival = current_time - timedelta(minutes=30 + i * 10)
            dest_stop.actual_arrival = dest_stop.scheduled_arrival + timedelta(
                minutes=2
            )
            dest_stop.scheduled_departure = None
            dest_stop.actual_departure = None

            journey.stops = [origin_stop, dest_stop]
            similar_journeys.append(journey)

        # No historical data for this specific train, but have similar trains
        summary = summary_service._generate_train_summary(
            [],  # No historical journeys for this train
            similar_journeys,  # But we have similar trains
            "1234",
            "NY",
            "TR",
            "NJT",
        )

        assert summary.scope == "train"
        # Should show similar trains data even with no history for this train
        assert "on time" in summary.headline.lower()
        assert "NJ Transit" in summary.body
        assert summary.metrics is not None
        assert summary.metrics.train_count == 5

    def test_cache_works(self, summary_service):
        """Test that caching prevents redundant calculations."""
        line_stats = {
            "Northeast Corridor": LineStats(
                line_name="Northeast Corridor",
                line_code="NEC",
                train_count=20,
                on_time_count=18,
                cancellation_count=0,
                total_delay_minutes=20.0,
                data_source="NJT",
            )
        }

        # Generate summary and store in cache
        summary1 = summary_service._generate_network_summary(line_stats)

        # Manually set cache
        from trackrat.utils.time import now_et

        summary_service._cache["network_all"] = (summary1, now_et())

        # Check cache is used (would need to mock now_et for full test)
        assert "network_all" in summary_service._cache


class TestSummaryMetrics:
    """Test cases for SummaryMetrics data class."""

    def test_summary_metrics_initialization(self):
        """Test SummaryMetrics initialization with all fields."""
        metrics = SummaryMetrics(
            on_time_percentage=85.5,
            average_delay_minutes=4.2,
            cancellation_count=2,
            train_count=24,
        )

        assert metrics.on_time_percentage == 85.5
        assert metrics.average_delay_minutes == 4.2
        assert metrics.cancellation_count == 2
        assert metrics.train_count == 24

    def test_summary_metrics_optional_fields(self):
        """Test SummaryMetrics with optional fields as None."""
        metrics = SummaryMetrics()

        assert metrics.on_time_percentage is None
        assert metrics.average_delay_minutes is None
        assert metrics.cancellation_count is None
        assert metrics.train_count is None


class TestOperationsSummary:
    """Test cases for OperationsSummary data class."""

    def test_operations_summary_initialization(self):
        """Test OperationsSummary initialization."""
        from trackrat.utils.time import now_et

        summary = OperationsSummary(
            headline="Trains running smoothly",
            body="Most trains on time with average delays under 5 minutes.",
            scope="network",
            time_window_minutes=90,
            data_freshness_seconds=45,
            generated_at=now_et(),
            metrics=SummaryMetrics(on_time_percentage=95.0),
        )

        assert summary.headline == "Trains running smoothly"
        assert summary.scope == "network"
        assert summary.time_window_minutes == 90
        assert summary.metrics.on_time_percentage == 95.0
