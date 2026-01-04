"""
Unit tests for scheduler timezone handling.

Tests the fix for timezone comparison errors that occur when SQLite
returns naive datetimes but the scheduler needs to compare with 
timezone-aware datetimes.
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import Mock, AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from trackrat.services.scheduler import SchedulerService
from trackrat.models.database import TrainJourney
from trackrat.utils.time import now_et, ensure_timezone_aware
from trackrat.config import Settings


class TestSchedulerTimezoneHandling:
    """Test timezone handling in scheduler operations."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for scheduler."""
        settings = Mock(spec=Settings)
        settings.discovery_interval_minutes = 60
        settings.journey_update_interval_minutes = 15
        settings.hot_train_window_minutes = 15
        settings.hot_train_update_interval_seconds = 120
        return settings

    @pytest.fixture
    def scheduler_service(self, mock_settings):
        """Create scheduler service with mocked settings."""
        return SchedulerService(settings=mock_settings)

    @pytest.mark.asyncio
    async def test_timezone_aware_datetime_comparison(self):
        """Test that timezone-aware comparisons work correctly."""
        # Create a naive datetime (as would come from SQLite)
        naive_dt = datetime(2025, 7, 11, 14, 30, 0)  # No timezone

        # Create timezone-aware datetime (as from now_et())
        aware_dt = now_et()

        # Test the fix: ensure_timezone_aware should make comparison possible
        made_aware = ensure_timezone_aware(naive_dt)

        # These should not raise TypeError
        assert isinstance(made_aware, datetime)
        assert made_aware.tzinfo is not None

        # Should be able to compare without error
        try:
            comparison_result = made_aware > aware_dt
            assert isinstance(comparison_result, bool)
        except TypeError as e:
            pytest.fail(f"Timezone comparison failed: {e}")

    @pytest.mark.asyncio
    async def test_schedule_departure_collections_timezone_handling(
        self, db_session: AsyncSession, scheduler_service
    ):
        """Test that schedule_departure_collections properly handles timezone comparisons."""
        # Create journey with naive scheduled_departure in the near future (simulating SQLite)
        from datetime import timedelta

        future_departure = now_et() + timedelta(
            minutes=5
        )  # Future timezone-aware datetime

        journey = TrainJourney(
            train_id="5678",
            journey_date=future_departure.date(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="New York",
            origin_station_code="TR",
            terminal_station_code="NY",
            scheduled_departure=future_departure,  # Naive datetime from SQLite
            first_seen_at=now_et(),
            last_updated_at=now_et(),
            has_complete_journey=False,
            update_count=1,
            data_source="NJT",
        )

        db_session.add(journey)
        await db_session.commit()

        # Mock scheduler
        scheduler_service.scheduler = Mock()
        scheduler_service.scheduler.add_job = Mock()
        scheduler_service.scheduler.get_job = Mock(return_value=None)  # No existing job

        # This should not raise timezone comparison error
        try:
            await scheduler_service.schedule_departure_collections(db_session)

            # Should have scheduled a job for the future departure
            assert scheduler_service.scheduler.add_job.called

        except TypeError as e:
            if "offset-naive and offset-aware" in str(e):
                pytest.fail(
                    f"Timezone comparison error in schedule_departure_collections: {e}"
                )
            else:
                raise

    def test_ensure_timezone_aware_with_naive_datetime(self):
        """Test ensure_timezone_aware function with naive datetime."""
        naive_dt = datetime(2025, 7, 11, 14, 30, 0)

        # Should convert to timezone-aware
        aware_dt = ensure_timezone_aware(naive_dt)

        assert aware_dt.tzinfo is not None
        assert aware_dt.tzinfo.zone == "America/New_York"

        # Time should be the same, just with timezone added
        assert aware_dt.replace(tzinfo=None) == naive_dt

    def test_ensure_timezone_aware_with_aware_datetime(self):
        """Test ensure_timezone_aware function with already timezone-aware datetime."""
        aware_dt = now_et()

        # Should return the same datetime
        result = ensure_timezone_aware(aware_dt)

        assert result == aware_dt
        assert result.tzinfo is not None

    @pytest.mark.asyncio
    async def test_datetime_comparison_in_where_clause_simulation(
        self, db_session: AsyncSession
    ):
        """Test that database queries with datetime comparisons work properly."""
        # Create journey with timezone-aware datetime (actual database behavior)
        future_time = now_et() + timedelta(days=365)  # Timezone-aware

        journey = TrainJourney(
            train_id="TEST123",
            journey_date=date(2025, 12, 31),
            line_code="NE",
            line_name="Test Line",
            destination="Test Destination",
            origin_station_code="NY",
            terminal_station_code="TR",
            scheduled_departure=future_time,
            first_seen_at=now_et(),
            last_updated_at=now_et(),
            has_complete_journey=False,
            update_count=1,
            data_source="NJT",
        )

        db_session.add(journey)
        await db_session.commit()

        # Query the journey back from database
        stmt = select(TrainJourney).where(TrainJourney.train_id == "TEST123")
        retrieved_journey = await db_session.scalar(stmt)

        assert retrieved_journey is not None

        # With DateTime(timezone=True), the scheduled_departure will be timezone-aware
        assert retrieved_journey.scheduled_departure.tzinfo is not None

        # Test the fix: use ensure_timezone_aware before comparison
        scheduled_tz = ensure_timezone_aware(retrieved_journey.scheduled_departure)
        current_time = now_et()

        # This should not raise TypeError
        try:
            is_future = scheduled_tz > current_time
            assert isinstance(is_future, bool)
        except TypeError as e:
            pytest.fail(f"Timezone comparison failed: {e}")
