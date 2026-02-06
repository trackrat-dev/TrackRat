"""
Comprehensive unit tests for JustInTimeUpdateService.

Tests the on-demand data refresh system that ensures train data freshness
when users request information.
"""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import ANY, AsyncMock, Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.models.database import TrainJourney
from trackrat.services.jit import JustInTimeUpdateService
from trackrat.settings import Settings


class TestJustInTimeUpdateService:
    """Test cases for JustInTimeUpdateService class."""

    @pytest.fixture
    def test_settings(self):
        """Create test settings."""
        return Settings(
            njt_api_token="test_token",
            data_staleness_seconds=60,
            environment="testing",
        )

    @pytest.fixture
    def mock_njt_client(self):
        """Create a mock NJ Transit client."""
        return AsyncMock(spec=NJTransitClient)

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock(spec=AsyncSession)
        db.scalar = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def jit_service(self, mock_njt_client, test_settings):
        """Create a JIT service instance for testing."""
        with patch("trackrat.services.jit.get_settings") as mock_get_settings:
            mock_get_settings.return_value = test_settings
            return JustInTimeUpdateService(njt_client=mock_njt_client)

    @pytest.fixture
    def sample_journey(self):
        """Create a sample journey for testing."""
        journey = Mock(spec=TrainJourney)
        journey.id = 1
        journey.train_id = "1234"
        journey.journey_date = date.today()
        journey.data_source = "NJT"
        journey.observation_type = "OBSERVED"
        journey.is_cancelled = False
        journey.is_completed = False
        journey.has_complete_journey = True
        journey.scheduled_departure = datetime.now(UTC) + timedelta(hours=2)
        journey.last_updated_at = datetime.now(UTC) - timedelta(minutes=5)
        journey.api_error_count = 0
        journey.stops = []
        journey.progress_snapshots = []
        return journey

    @pytest.mark.asyncio
    async def test_context_manager(self, jit_service):
        """Test that JIT service works as a context manager."""
        async with jit_service as service:
            assert service == jit_service

    def test_njt_collector_property(self, jit_service):
        """Test lazy initialization of NJT collector."""
        # Collector should not be created initially
        assert jit_service._njt_collector is None

        # Accessing property should create it
        collector = jit_service.njt_collector
        assert collector is not None
        assert jit_service._njt_collector == collector

        # Subsequent access should return same instance
        collector2 = jit_service.njt_collector
        assert collector2 == collector

    def test_njt_collector_without_client_raises_error(self):
        """Test that accessing NJT collector without client raises error."""
        service = JustInTimeUpdateService(njt_client=None)

        with pytest.raises(ValueError, match="NJT client required"):
            _ = service.njt_collector

    def test_amtrak_collector_property(self, jit_service):
        """Test lazy initialization of Amtrak collector."""
        assert jit_service._amtrak_collector is None

        collector = jit_service.amtrak_collector
        assert collector is not None
        assert jit_service._amtrak_collector == collector

        # Subsequent access should return same instance
        collector2 = jit_service.amtrak_collector
        assert collector2 == collector

    @pytest.mark.asyncio
    async def test_get_collector_for_njt_journey(self, jit_service, sample_journey):
        """Test getting correct collector for NJT journey."""
        sample_journey.data_source = "NJT"

        collector = await jit_service.get_collector_for_journey(sample_journey)

        assert collector == jit_service.njt_collector

    @pytest.mark.asyncio
    async def test_get_collector_for_amtrak_journey(self, jit_service, sample_journey):
        """Test getting correct collector for Amtrak journey."""
        sample_journey.data_source = "AMTRAK"

        collector = await jit_service.get_collector_for_journey(sample_journey)

        assert collector == jit_service.amtrak_collector

    @pytest.mark.asyncio
    async def test_get_collector_for_unknown_source(self, jit_service, sample_journey):
        """Test that unknown data source raises error."""
        sample_journey.data_source = "UNKNOWN"

        with pytest.raises(ValueError, match="Unknown data source: UNKNOWN"):
            await jit_service.get_collector_for_journey(sample_journey)

    def test_needs_refresh_when_stale(self, jit_service, sample_journey):
        """Test that stale data is identified for refresh."""
        # Make journey stale (>60 seconds old)
        sample_journey.last_updated_at = datetime.now(UTC) - timedelta(seconds=120)

        assert jit_service.needs_refresh(sample_journey) is True

    def test_needs_refresh_when_fresh(self, jit_service, sample_journey):
        """Test that fresh data doesn't need refresh."""
        # Make journey fresh (<60 seconds old)
        sample_journey.last_updated_at = datetime.now(UTC) - timedelta(seconds=30)

        assert jit_service.needs_refresh(sample_journey) is False

    def test_needs_refresh_for_incomplete_journey(self, jit_service, sample_journey):
        """Test that incomplete journeys always need refresh."""
        sample_journey.has_complete_journey = False
        sample_journey.last_updated_at = datetime.now(UTC)  # Even if fresh

        assert jit_service.needs_refresh(sample_journey) is True

    def test_needs_refresh_for_completed_journey(self, jit_service, sample_journey):
        """Test that completed journeys don't need refresh."""
        sample_journey.is_completed = True
        sample_journey.last_updated_at = datetime.now(UTC) - timedelta(hours=1)  # Old

        assert jit_service.needs_refresh(sample_journey) is False

    def test_needs_refresh_for_cancelled_journey(self, jit_service, sample_journey):
        """Test that cancelled journeys don't need refresh."""
        sample_journey.is_cancelled = True
        sample_journey.last_updated_at = datetime.now(UTC) - timedelta(hours=1)

        assert jit_service.needs_refresh(sample_journey) is False

    def test_needs_refresh_with_no_updated_time(self, jit_service, sample_journey):
        """Test that journeys without updated time need refresh."""
        sample_journey.last_updated_at = None

        assert jit_service.needs_refresh(sample_journey) is True

    def test_needs_refresh_boundary_conditions(self, jit_service, sample_journey):
        """Test staleness boundary conditions."""
        # Exactly at staleness threshold (60 seconds)
        sample_journey.last_updated_at = datetime.now(UTC) - timedelta(seconds=60)
        assert jit_service.needs_refresh(sample_journey) is True

        # Just under threshold (59 seconds)
        sample_journey.last_updated_at = datetime.now(UTC) - timedelta(seconds=59)
        assert jit_service.needs_refresh(sample_journey) is False

    def test_needs_refresh_hot_train_uses_tighter_staleness(self, jit_service, sample_journey):
        """Test that trains departing soon use hot_data_staleness_seconds (20s default)."""
        # Train departing in 5 minutes — should use hot staleness (20s)
        sample_journey.scheduled_departure = datetime.now(UTC) + timedelta(minutes=5)

        # 30 seconds old — stale under hot threshold (20s) but fresh under normal (60s)
        sample_journey.last_updated_at = datetime.now(UTC) - timedelta(seconds=30)
        assert jit_service.needs_refresh(sample_journey) is True

        # 15 seconds old — fresh under hot threshold (20s)
        sample_journey.last_updated_at = datetime.now(UTC) - timedelta(seconds=15)
        assert jit_service.needs_refresh(sample_journey) is False

    def test_needs_refresh_non_hot_train_uses_normal_staleness(self, jit_service, sample_journey):
        """Test that trains departing far in the future use normal data_staleness_seconds (60s)."""
        # Train departing in 2 hours — should use normal staleness (60s)
        sample_journey.scheduled_departure = datetime.now(UTC) + timedelta(hours=2)

        # 30 seconds old — fresh under normal threshold (60s)
        sample_journey.last_updated_at = datetime.now(UTC) - timedelta(seconds=30)
        assert jit_service.needs_refresh(sample_journey) is False

        # 65 seconds old — stale under normal threshold (60s)
        sample_journey.last_updated_at = datetime.now(UTC) - timedelta(seconds=65)
        assert jit_service.needs_refresh(sample_journey) is True

    def test_needs_refresh_departed_train_uses_normal_staleness(self, jit_service, sample_journey):
        """Test that already-departed trains (negative time to departure) use normal staleness."""
        # Train departed 10 minutes ago
        sample_journey.scheduled_departure = datetime.now(UTC) - timedelta(minutes=10)

        # 30 seconds old — fresh under normal threshold (60s)
        sample_journey.last_updated_at = datetime.now(UTC) - timedelta(seconds=30)
        assert jit_service.needs_refresh(sample_journey) is False

    @pytest.mark.asyncio
    async def test_ensure_fresh_data_journey_not_found(self, jit_service, mock_db):
        """Test behavior when journey is not found."""
        mock_db.scalar.return_value = None

        with patch("trackrat.services.jit.now_et") as mock_now:
            mock_now.return_value.date.return_value = date.today()

            result = await jit_service.ensure_fresh_data(mock_db, "9999", date.today())

        assert result is None
        mock_db.scalar.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_fresh_data_no_refresh_needed(
        self, jit_service, mock_db, sample_journey
    ):
        """Test when data is fresh and doesn't need refresh."""
        # Make journey fresh
        sample_journey.last_updated_at = datetime.now(UTC) - timedelta(seconds=30)
        mock_db.scalar.return_value = sample_journey

        result = await jit_service.ensure_fresh_data(mock_db, "1234", date.today())

        assert result == sample_journey
        # Should not attempt to refresh
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_fresh_data_refresh_success(
        self, jit_service, mock_db, sample_journey
    ):
        """Test successful data refresh when stale."""
        # Make journey stale
        sample_journey.last_updated_at = datetime.now(UTC) - timedelta(minutes=5)
        mock_db.scalar.return_value = sample_journey

        # Mock the collector
        mock_collector = AsyncMock()
        mock_collector.collect_journey_details.return_value = None

        with patch.object(jit_service, "_njt_collector", mock_collector):
            result = await jit_service.ensure_fresh_data(mock_db, "1234", date.today())

        assert result == sample_journey
        mock_collector.collect_journey_details.assert_called_once_with(
            mock_db, sample_journey
        )

    @pytest.mark.asyncio
    async def test_ensure_fresh_data_force_refresh(
        self, jit_service, mock_db, sample_journey
    ):
        """Test force refresh even when data is fresh."""
        # Make journey fresh
        sample_journey.last_updated_at = datetime.now(UTC) - timedelta(seconds=10)
        mock_db.scalar.return_value = sample_journey

        mock_collector = AsyncMock()
        mock_collector.collect_journey_details.return_value = None

        with patch.object(jit_service, "_njt_collector", mock_collector):
            result = await jit_service.ensure_fresh_data(
                mock_db, "1234", date.today(), force_refresh=True
            )

        # Should refresh despite being fresh
        mock_collector.collect_journey_details.assert_called_once()
        assert result == sample_journey

    @pytest.mark.asyncio
    async def test_ensure_fresh_data_refresh_failure(
        self, jit_service, mock_db, sample_journey
    ):
        """Test handling of refresh failure."""
        sample_journey.last_updated_at = datetime.now(UTC) - timedelta(minutes=5)
        mock_db.scalar.return_value = sample_journey

        mock_collector = AsyncMock()
        mock_collector.collect_journey_details.side_effect = Exception("API Error")

        with patch.object(jit_service, "_njt_collector", mock_collector):
            # Should handle error and return original journey
            result = await jit_service.ensure_fresh_data(mock_db, "1234", date.today())

        assert result == sample_journey  # Returns original despite error

    @pytest.mark.asyncio
    async def test_ensure_fresh_data_amtrak_journey(self, jit_service, mock_db):
        """Test refresh for Amtrak journey."""
        amtrak_journey = Mock(spec=TrainJourney)
        amtrak_journey.id = 2
        amtrak_journey.train_id = "A123"
        amtrak_journey.data_source = "AMTRAK"
        amtrak_journey.observation_type = "OBSERVED"
        amtrak_journey.is_completed = False
        amtrak_journey.is_cancelled = False
        amtrak_journey.has_complete_journey = False
        amtrak_journey.last_updated_at = datetime.now(UTC) - timedelta(minutes=5)
        amtrak_journey.api_error_count = 0

        mock_db.scalar.return_value = amtrak_journey

        mock_collector = AsyncMock()
        mock_collector.collect_journey_details.return_value = None

        with patch.object(jit_service, "_amtrak_collector", mock_collector):
            result = await jit_service.ensure_fresh_data(mock_db, "A123", date.today())

        mock_collector.collect_journey_details.assert_called_once_with(
            mock_db, amtrak_journey
        )
        assert result == amtrak_journey

    @pytest.mark.asyncio
    async def test_ensure_fresh_data_default_date(self, jit_service, mock_db):
        """Test that default date is today when not specified."""
        mock_db.scalar.return_value = None

        with patch("trackrat.services.jit.now_et") as mock_now:
            mock_date = date(2025, 1, 15)
            mock_now.return_value.date.return_value = mock_date

            await jit_service.ensure_fresh_data(mock_db, "1234")

            # Verify query used today's date
            query_call = mock_db.scalar.call_args
            # The query would include the date in the WHERE clause
            assert query_call is not None

    @pytest.mark.asyncio
    async def test_concurrent_refresh_handling(self, jit_service, mock_db):
        """Test that concurrent refresh requests are handled properly."""
        sample_journey = Mock(spec=TrainJourney)
        sample_journey.id = 1
        sample_journey.train_id = "1234"
        sample_journey.data_source = "NJT"
        sample_journey.observation_type = "OBSERVED"
        sample_journey.is_completed = False
        sample_journey.last_updated_at = datetime.now(UTC) - timedelta(minutes=5)
        sample_journey.api_error_count = 0

        mock_db.scalar.return_value = sample_journey

        mock_collector = AsyncMock()

        # Simulate slow API call
        async def slow_update(db, journey):
            await asyncio.sleep(0.1)
            return None

        mock_collector.collect_journey_details = slow_update

        with patch.object(jit_service, "_njt_collector", mock_collector):
            # Simulate concurrent requests
            import asyncio

            tasks = [jit_service.ensure_fresh_data(mock_db, "1234") for _ in range(3)]
            results = await asyncio.gather(*tasks)

        # All should return the journey
        assert all(r == sample_journey for r in results)


class TestJITIntegrationScenarios:
    """Integration test scenarios for JIT updates."""

    @pytest.mark.asyncio
    async def test_user_request_flow(self):
        """Test complete user request flow with JIT update."""
        # Simulate user requesting train data
        mock_db = AsyncMock(spec=AsyncSession)
        mock_njt_client = AsyncMock(spec=NJTransitClient)

        service = JustInTimeUpdateService(njt_client=mock_njt_client)

        # Journey exists but is stale
        journey = Mock(spec=TrainJourney)
        journey.train_id = "1234"
        journey.data_source = "NJT"
        journey.observation_type = "OBSERVED"
        journey.is_completed = False
        journey.is_cancelled = False
        journey.has_complete_journey = True
        journey.scheduled_departure = datetime.now(UTC) + timedelta(hours=2)
        journey.last_updated_at = datetime.now(UTC) - timedelta(minutes=10)
        journey.api_error_count = 0

        mock_db.scalar.return_value = journey

        # Mock successful refresh
        mock_collector = AsyncMock()
        mock_collector.collect_journey_details.return_value = None

        with patch.object(service, "_njt_collector", mock_collector):
            result = await service.ensure_fresh_data(mock_db, "1234")

        assert result == journey
        mock_collector.collect_journey_details.assert_called_once()

    @pytest.mark.asyncio
    async def test_scheduled_to_observed_transition(self):
        """Test transition from SCHEDULED to OBSERVED journey."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_njt_client = AsyncMock(spec=NJTransitClient)

        service = JustInTimeUpdateService(njt_client=mock_njt_client)

        # Start with incomplete journey (which always needs refresh)
        journey = Mock(spec=TrainJourney)
        journey.train_id = "1234"
        journey.data_source = "NJT"
        journey.observation_type = "SCHEDULED"
        journey.has_complete_journey = False
        journey.is_completed = False
        journey.is_cancelled = False
        journey.last_updated_at = datetime.now(UTC)  # Fresh but incomplete
        journey.api_error_count = 0

        mock_db.scalar.return_value = journey

        # Mock collector that will update the journey
        mock_collector = AsyncMock()

        def update_observation_type(db, j):
            # Simulate updating journey to OBSERVED
            j.observation_type = "OBSERVED"
            return None

        mock_collector.collect_journey_details.side_effect = update_observation_type

        with patch.object(service, "_njt_collector", mock_collector):
            result = await service.ensure_fresh_data(mock_db, "1234")

        # Should have refreshed because has_complete_journey was False
        mock_collector.collect_journey_details.assert_called_once()
        assert result == journey  # Same journey object, but updated
