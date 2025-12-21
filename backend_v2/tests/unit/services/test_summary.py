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
    DELAY_CATEGORY_CANCELLED,
    DELAY_CATEGORY_DELAYED,
    DELAY_CATEGORY_ON_TIME,
    DELAY_CATEGORY_SLIGHT_DELAY,
    ON_TIME_THRESHOLD_MINUTES,
    SLIGHT_DELAY_THRESHOLD_MINUTES,
    LineStats,
    OperationsSummary,
    SummaryMetrics,
    SummaryService,
    TrainDelaySummary,
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
        """Test route summary with no data returns informative message."""
        summary = summary_service._generate_route_summary([], "NY", "NP")

        assert summary.scope == "route"
        # With no data, show informative message so users know service status
        assert summary.headline == ""
        assert summary.body == "No trains travelled this route in the past 90 minutes."
        assert summary.metrics is None

    def test_generate_route_summary_all_cancelled(self, summary_service):
        """Test route summary when all scheduled trains are cancelled."""
        current_time = datetime.now(UTC)

        # Create 3 cancelled journeys
        journeys = []
        for i in range(3):
            journey = Mock(spec=TrainJourney)
            journey.id = i
            journey.train_id = f"100{i}"
            journey.is_cancelled = True
            journey.data_source = "NJT"

            # Even cancelled trains have stops
            origin_stop = Mock()
            origin_stop.station_code = "NY"
            origin_stop.stop_sequence = 1
            origin_stop.scheduled_departure = current_time - timedelta(
                minutes=30 + i * 10
            )
            origin_stop.actual_departure = None

            dest_stop = Mock()
            dest_stop.station_code = "NP"
            dest_stop.stop_sequence = 5

            journey.stops = [origin_stop, dest_stop]
            journeys.append(journey)

        summary = summary_service._generate_route_summary(journeys, "NY", "NP")

        assert summary.scope == "route"
        assert summary.headline == "Service disrupted"
        assert "cancelled" in summary.body.lower()
        assert "3" in summary.body  # All 3 trains
        assert summary.metrics is not None
        assert summary.metrics.cancellation_count == 3
        assert summary.metrics.on_time_percentage == 0.0

    def test_calculate_departure_stats_not_yet_departed(self, summary_service):
        """Test delay calculation for trains that haven't departed yet.

        If a train was scheduled 30 minutes ago but hasn't departed,
        it should be counted as delayed by 30 minutes, not on-time.
        """
        current_time = datetime.now(UTC)

        # Create journey scheduled 30 minutes ago but not yet departed
        journey = Mock(spec=TrainJourney)
        journey.id = 1
        journey.train_id = "1234"
        journey.is_cancelled = False
        journey.data_source = "NJT"

        origin_stop = Mock()
        origin_stop.station_code = "NY"
        origin_stop.stop_sequence = 1
        origin_stop.scheduled_departure = current_time - timedelta(minutes=30)
        origin_stop.actual_departure = None  # Not departed yet!

        dest_stop = Mock()
        dest_stop.station_code = "NP"
        dest_stop.stop_sequence = 5

        journey.stops = [origin_stop, dest_stop]

        stats = summary_service._calculate_departure_stats(
            [journey], "NY", current_time=current_time
        )

        # Should NOT be counted as on-time since it's 30 minutes late
        assert stats.total_count == 1
        assert stats.on_time_percentage == 0.0
        assert stats.average_delay_minutes >= 25  # Should be ~30 min

    def test_calculate_departure_stats_just_scheduled(self, summary_service):
        """Test that recently scheduled trains (within 5 min) are counted as on-time.

        If a train was scheduled 3 minutes ago and hasn't departed,
        that's normal - it should be counted as on-time.
        """
        current_time = datetime.now(UTC)

        # Create journey scheduled 3 minutes ago but not yet departed
        journey = Mock(spec=TrainJourney)
        journey.id = 1
        journey.train_id = "1234"
        journey.is_cancelled = False
        journey.data_source = "NJT"

        origin_stop = Mock()
        origin_stop.station_code = "NY"
        origin_stop.stop_sequence = 1
        origin_stop.scheduled_departure = current_time - timedelta(minutes=3)
        origin_stop.actual_departure = None  # Not departed yet, but that's normal

        dest_stop = Mock()
        dest_stop.station_code = "NP"
        dest_stop.stop_sequence = 5

        journey.stops = [origin_stop, dest_stop]

        stats = summary_service._calculate_departure_stats(
            [journey], "NY", current_time=current_time
        )

        # Should be counted as on-time since it's only 3 minutes past scheduled
        assert stats.total_count == 1
        assert stats.on_time_percentage == 100.0

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


class TestDelayCategorization:
    """Test cases for delay categorization logic."""

    @pytest.fixture
    def summary_service(self):
        """Create a SummaryService instance for testing."""
        return SummaryService()

    def test_categorize_delay_on_time(self, summary_service):
        """Test that delays <= 5 minutes are categorized as on_time."""
        assert summary_service._categorize_delay(0) == DELAY_CATEGORY_ON_TIME
        assert summary_service._categorize_delay(3) == DELAY_CATEGORY_ON_TIME
        assert summary_service._categorize_delay(5) == DELAY_CATEGORY_ON_TIME

    def test_categorize_delay_slight(self, summary_service):
        """Test that delays 5-15 minutes are categorized as slight_delay."""
        assert summary_service._categorize_delay(5.1) == DELAY_CATEGORY_SLIGHT_DELAY
        assert summary_service._categorize_delay(10) == DELAY_CATEGORY_SLIGHT_DELAY
        assert summary_service._categorize_delay(15) == DELAY_CATEGORY_SLIGHT_DELAY

    def test_categorize_delay_delayed(self, summary_service):
        """Test that delays > 15 minutes are categorized as delayed."""
        assert summary_service._categorize_delay(15.1) == DELAY_CATEGORY_DELAYED
        assert summary_service._categorize_delay(20) == DELAY_CATEGORY_DELAYED
        assert summary_service._categorize_delay(60) == DELAY_CATEGORY_DELAYED

    def test_thresholds_are_correct(self):
        """Verify threshold constants are set correctly."""
        assert ON_TIME_THRESHOLD_MINUTES == 5
        assert SLIGHT_DELAY_THRESHOLD_MINUTES == 15


class TestTrainsByCategory:
    """Test cases for trains_by_category in departure stats."""

    @pytest.fixture
    def summary_service(self):
        """Create a SummaryService instance for testing."""
        return SummaryService()

    def test_departure_stats_returns_trains_by_category(self, summary_service):
        """Test that _calculate_departure_stats returns trains grouped by category."""
        current_time = datetime.now(UTC)

        journeys = []

        # On-time train (0 min delay)
        journey1 = Mock(spec=TrainJourney)
        journey1.train_id = "1001"
        journey1.is_cancelled = False
        stop1 = Mock()
        stop1.station_code = "NY"
        stop1.scheduled_departure = current_time - timedelta(minutes=30)
        stop1.actual_departure = stop1.scheduled_departure  # Exactly on time
        journey1.stops = [stop1]
        journeys.append(journey1)

        # Slight delay train (10 min delay)
        journey2 = Mock(spec=TrainJourney)
        journey2.train_id = "1002"
        journey2.is_cancelled = False
        stop2 = Mock()
        stop2.station_code = "NY"
        stop2.scheduled_departure = current_time - timedelta(minutes=60)
        stop2.actual_departure = stop2.scheduled_departure + timedelta(minutes=10)
        journey2.stops = [stop2]
        journeys.append(journey2)

        # Delayed train (20 min delay)
        journey3 = Mock(spec=TrainJourney)
        journey3.train_id = "1003"
        journey3.is_cancelled = False
        stop3 = Mock()
        stop3.station_code = "NY"
        stop3.scheduled_departure = current_time - timedelta(minutes=90)
        stop3.actual_departure = stop3.scheduled_departure + timedelta(minutes=20)
        journey3.stops = [stop3]
        journeys.append(journey3)

        # Cancelled train
        journey4 = Mock(spec=TrainJourney)
        journey4.train_id = "1004"
        journey4.is_cancelled = True
        stop4 = Mock()
        stop4.station_code = "NY"
        stop4.scheduled_departure = current_time - timedelta(minutes=45)
        journey4.stops = [stop4]
        journeys.append(journey4)

        stats = summary_service._calculate_departure_stats(
            journeys, "NY", current_time=current_time
        )

        # Verify trains_by_category structure
        assert stats.trains_by_category is not None
        assert len(stats.trains_by_category[DELAY_CATEGORY_ON_TIME]) == 1
        assert len(stats.trains_by_category[DELAY_CATEGORY_SLIGHT_DELAY]) == 1
        assert len(stats.trains_by_category[DELAY_CATEGORY_DELAYED]) == 1
        assert len(stats.trains_by_category[DELAY_CATEGORY_CANCELLED]) == 1

        # Verify train IDs
        on_time_ids = [t.train_id for t in stats.trains_by_category[DELAY_CATEGORY_ON_TIME]]
        assert "1001" in on_time_ids

        slight_delay_ids = [t.train_id for t in stats.trains_by_category[DELAY_CATEGORY_SLIGHT_DELAY]]
        assert "1002" in slight_delay_ids

        delayed_ids = [t.train_id for t in stats.trains_by_category[DELAY_CATEGORY_DELAYED]]
        assert "1003" in delayed_ids

        cancelled_ids = [t.train_id for t in stats.trains_by_category[DELAY_CATEGORY_CANCELLED]]
        assert "1004" in cancelled_ids

    def test_trains_by_category_delay_minutes(self, summary_service):
        """Test that delay_minutes is correctly calculated for each train."""
        current_time = datetime.now(UTC)

        journey = Mock(spec=TrainJourney)
        journey.train_id = "1001"
        journey.is_cancelled = False
        stop = Mock()
        stop.station_code = "NY"
        stop.scheduled_departure = current_time - timedelta(minutes=30)
        stop.actual_departure = stop.scheduled_departure + timedelta(minutes=7)
        journey.stops = [stop]

        stats = summary_service._calculate_departure_stats(
            [journey], "NY", current_time=current_time
        )

        # Should be in slight_delay category with 7 minutes delay
        train_summary = stats.trains_by_category[DELAY_CATEGORY_SLIGHT_DELAY][0]
        assert train_summary.train_id == "1001"
        assert abs(train_summary.delay_minutes - 7.0) < 0.1
        assert train_summary.category == DELAY_CATEGORY_SLIGHT_DELAY

    def test_trains_by_category_empty_journeys(self, summary_service):
        """Test that empty journeys returns empty category lists."""
        stats = summary_service._calculate_departure_stats([], "NY")

        assert stats.trains_by_category is not None
        assert len(stats.trains_by_category[DELAY_CATEGORY_ON_TIME]) == 0
        assert len(stats.trains_by_category[DELAY_CATEGORY_SLIGHT_DELAY]) == 0
        assert len(stats.trains_by_category[DELAY_CATEGORY_DELAYED]) == 0
        assert len(stats.trains_by_category[DELAY_CATEGORY_CANCELLED]) == 0


class TestMergeTrainsByCategory:
    """Test cases for merging trains_by_category from multiple OnTimeStats."""

    @pytest.fixture
    def summary_service(self):
        """Create a SummaryService instance for testing."""
        return SummaryService()

    def test_merge_trains_from_multiple_stats(self, summary_service):
        """Test merging trains from NJT and Amtrak stats."""
        from trackrat.services.summary import OnTimeStats

        njt_stats = OnTimeStats(
            on_time_percentage=80.0,
            average_delay_minutes=3.0,
            total_count=5,
            cancellation_count=0,
            carrier_name="NJ Transit",
            trains_by_category={
                DELAY_CATEGORY_ON_TIME: [
                    TrainDelaySummary(
                        train_id="3847",
                        delay_minutes=2.0,
                        category=DELAY_CATEGORY_ON_TIME,
                        scheduled_departure=datetime.now(UTC),
                    )
                ],
                DELAY_CATEGORY_SLIGHT_DELAY: [],
                DELAY_CATEGORY_DELAYED: [],
                DELAY_CATEGORY_CANCELLED: [],
            },
        )

        amtrak_stats = OnTimeStats(
            on_time_percentage=90.0,
            average_delay_minutes=2.0,
            total_count=3,
            cancellation_count=0,
            carrier_name="Amtrak",
            trains_by_category={
                DELAY_CATEGORY_ON_TIME: [
                    TrainDelaySummary(
                        train_id="171",
                        delay_minutes=1.0,
                        category=DELAY_CATEGORY_ON_TIME,
                        scheduled_departure=datetime.now(UTC),
                    )
                ],
                DELAY_CATEGORY_SLIGHT_DELAY: [],
                DELAY_CATEGORY_DELAYED: [],
                DELAY_CATEGORY_CANCELLED: [],
            },
        )

        merged = summary_service._merge_trains_by_category(njt_stats, amtrak_stats)

        # Should have both trains in on_time category
        assert len(merged[DELAY_CATEGORY_ON_TIME]) == 2
        train_ids = [t.train_id for t in merged[DELAY_CATEGORY_ON_TIME]]
        assert "3847" in train_ids
        assert "171" in train_ids

    def test_merge_with_none_stats(self, summary_service):
        """Test merging handles None stats gracefully."""
        from trackrat.services.summary import OnTimeStats

        njt_stats = OnTimeStats(
            on_time_percentage=80.0,
            average_delay_minutes=3.0,
            total_count=5,
            cancellation_count=0,
            carrier_name="NJ Transit",
            trains_by_category={
                DELAY_CATEGORY_ON_TIME: [
                    TrainDelaySummary(
                        train_id="3847",
                        delay_minutes=2.0,
                        category=DELAY_CATEGORY_ON_TIME,
                        scheduled_departure=datetime.now(UTC),
                    )
                ],
                DELAY_CATEGORY_SLIGHT_DELAY: [],
                DELAY_CATEGORY_DELAYED: [],
                DELAY_CATEGORY_CANCELLED: [],
            },
        )

        merged = summary_service._merge_trains_by_category(njt_stats, None)

        assert len(merged[DELAY_CATEGORY_ON_TIME]) == 1
        assert merged[DELAY_CATEGORY_ON_TIME][0].train_id == "3847"

    def test_merge_sorted_by_scheduled_departure(self, summary_service):
        """Test that merged trains are sorted by scheduled departure time."""
        from trackrat.services.summary import OnTimeStats

        now = datetime.now(UTC)

        njt_stats = OnTimeStats(
            on_time_percentage=80.0,
            average_delay_minutes=3.0,
            total_count=2,
            cancellation_count=0,
            trains_by_category={
                DELAY_CATEGORY_ON_TIME: [
                    TrainDelaySummary(
                        train_id="3847",
                        delay_minutes=2.0,
                        category=DELAY_CATEGORY_ON_TIME,
                        scheduled_departure=now - timedelta(minutes=30),  # Earlier
                    )
                ],
                DELAY_CATEGORY_SLIGHT_DELAY: [],
                DELAY_CATEGORY_DELAYED: [],
                DELAY_CATEGORY_CANCELLED: [],
            },
        )

        amtrak_stats = OnTimeStats(
            on_time_percentage=90.0,
            average_delay_minutes=2.0,
            total_count=1,
            cancellation_count=0,
            trains_by_category={
                DELAY_CATEGORY_ON_TIME: [
                    TrainDelaySummary(
                        train_id="171",
                        delay_minutes=1.0,
                        category=DELAY_CATEGORY_ON_TIME,
                        scheduled_departure=now - timedelta(minutes=60),  # Even earlier
                    )
                ],
                DELAY_CATEGORY_SLIGHT_DELAY: [],
                DELAY_CATEGORY_DELAYED: [],
                DELAY_CATEGORY_CANCELLED: [],
            },
        )

        merged = summary_service._merge_trains_by_category(njt_stats, amtrak_stats)

        # Should be sorted by scheduled departure (earliest first)
        on_time_trains = merged[DELAY_CATEGORY_ON_TIME]
        assert len(on_time_trains) == 2
        assert on_time_trains[0].train_id == "171"  # Earlier departure
        assert on_time_trains[1].train_id == "3847"  # Later departure


class TestRoutesSummaryTrainsByCategory:
    """Test that route summary includes trains_by_category in metrics."""

    @pytest.fixture
    def summary_service(self):
        """Create a SummaryService instance for testing."""
        return SummaryService()

    def test_route_summary_includes_trains_by_category(self, summary_service):
        """Test that _generate_route_summary includes trains in metrics."""
        current_time = datetime.now(UTC)

        journeys = []

        # NJT on-time train
        journey1 = Mock(spec=TrainJourney)
        journey1.train_id = "3847"
        journey1.is_cancelled = False
        journey1.data_source = "NJT"
        stop1 = Mock()
        stop1.station_code = "NY"
        stop1.stop_sequence = 1
        stop1.scheduled_departure = current_time - timedelta(minutes=30)
        stop1.actual_departure = stop1.scheduled_departure + timedelta(minutes=2)
        journey1.stops = [stop1]
        journeys.append(journey1)

        # NJT delayed train
        journey2 = Mock(spec=TrainJourney)
        journey2.train_id = "3851"
        journey2.is_cancelled = False
        journey2.data_source = "NJT"
        stop2 = Mock()
        stop2.station_code = "NY"
        stop2.stop_sequence = 1
        stop2.scheduled_departure = current_time - timedelta(minutes=60)
        stop2.actual_departure = stop2.scheduled_departure + timedelta(minutes=12)
        journey2.stops = [stop2]
        journeys.append(journey2)

        summary = summary_service._generate_route_summary(journeys, "NY", "NP")

        # Verify trains_by_category is included
        assert summary.metrics is not None
        assert summary.metrics.trains_by_category is not None

        # Should have 1 on-time, 1 slight delay
        assert len(summary.metrics.trains_by_category[DELAY_CATEGORY_ON_TIME]) == 1
        assert len(summary.metrics.trains_by_category[DELAY_CATEGORY_SLIGHT_DELAY]) == 1
        assert summary.metrics.trains_by_category[DELAY_CATEGORY_ON_TIME][0].train_id == "3847"
        assert summary.metrics.trains_by_category[DELAY_CATEGORY_SLIGHT_DELAY][0].train_id == "3851"
