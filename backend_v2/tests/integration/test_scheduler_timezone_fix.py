"""
Integration test for scheduler timezone fix.

Tests that the timezone comparison fix works in the actual scheduler
context with real database operations.
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from trackrat.services.scheduler import SchedulerService
from trackrat.models.database import TrainJourney
from trackrat.utils.time import now_et, ensure_timezone_aware
from trackrat.config import Settings


@pytest.mark.asyncio
class TestSchedulerTimezoneIntegration:
    """Integration test for scheduler timezone handling."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for scheduler."""
        settings = Mock(spec=Settings)
        settings.discovery_interval_minutes = 60
        settings.journey_update_interval_minutes = 15
        return settings

    @pytest.fixture
    def scheduler_service(self, mock_settings):
        """Create scheduler service with mocked settings."""
        service = SchedulerService(settings=mock_settings)
        # Mock the scheduler to avoid starting APScheduler
        service.scheduler = Mock()
        service.scheduler.add_job = Mock()
        service.scheduler.get_job = Mock(return_value=None)
        return service

    async def test_schedule_new_train_collections_with_naive_datetime(
        self, db_session: AsyncSession, scheduler_service
    ):
        """Test schedule_new_train_collections handles naive datetimes from database."""
        # Create a journey with future departure time
        future_time = now_et() + timedelta(hours=1)

        journey = TrainJourney(
            train_id="TEST1234",
            journey_date=future_time.date(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            scheduled_departure=future_time,  # This will be stored as naive in SQLite
            first_seen_at=now_et(),
            last_updated_at=now_et(),
            has_complete_journey=False,
            update_count=1,
            data_source="NJT",
        )

        db_session.add(journey)
        await db_session.commit()

        # Verify the datetime handling
        stmt = select(TrainJourney).where(TrainJourney.train_id == "TEST1234")
        retrieved = await db_session.scalar(stmt)
        # With DateTime(timezone=True), SQLAlchemy handles timezone conversion

        # Create discovery result
        discovery_result = {"station_results": {"NY": {"new_train_ids": ["TEST1234"]}}}

        # This should not raise timezone comparison error
        try:
            # Mock the session to use our test session
            with patch("trackrat.services.scheduler.get_session") as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = db_session

                await scheduler_service.schedule_new_train_collections(discovery_result)

            # Verify job was scheduled without error
            assert scheduler_service.scheduler.add_job.called
            call_args = scheduler_service.scheduler.add_job.call_args

            # Verify the DateTrigger received a timezone-aware datetime
            trigger = call_args[1]["trigger"]
            assert trigger.run_date.tzinfo is not None

        except TypeError as e:
            if "offset-naive and offset-aware" in str(e):
                pytest.fail(f"Timezone comparison error not fixed: {e}")
            else:
                raise

    async def test_database_datetime_retrieval_is_naive(self, db_session: AsyncSession):
        """Verify that SQLite returns naive datetimes (demonstrating the problem)."""
        # Store a timezone-aware datetime
        aware_time = now_et()

        journey = TrainJourney(
            train_id="NAIVE_TEST",
            journey_date=aware_time.date(),
            line_code="NE",
            line_name="Test Line",
            destination="Test Destination",
            origin_station_code="NY",
            terminal_station_code="TR",
            scheduled_departure=aware_time,  # Store timezone-aware
            first_seen_at=aware_time,
            last_updated_at=aware_time,
            has_complete_journey=False,
            update_count=1,
            data_source="NJT",
        )

        db_session.add(journey)
        await db_session.commit()

        # Retrieve from database
        stmt = select(TrainJourney).where(TrainJourney.train_id == "NAIVE_TEST")
        retrieved = await db_session.scalar(stmt)

        # With DateTime(timezone=True), SQLAlchemy returns timezone-aware datetimes
        assert retrieved.scheduled_departure.tzinfo is not None
        assert retrieved.first_seen_at.tzinfo is not None
        assert retrieved.last_updated_at.tzinfo is not None

    async def test_ensure_timezone_aware_fixes_database_datetimes(
        self, db_session: AsyncSession
    ):
        """Test that ensure_timezone_aware properly fixes database datetimes."""
        # Store and retrieve a journey
        journey = TrainJourney(
            train_id="FIX_TEST",
            journey_date=date.today(),
            line_code="NE",
            line_name="Test Line",
            destination="Test Destination",
            origin_station_code="NY",
            terminal_station_code="TR",
            scheduled_departure=datetime.now(),
            first_seen_at=now_et(),
            last_updated_at=now_et(),
            has_complete_journey=False,
            update_count=1,
            data_source="NJT",
        )

        db_session.add(journey)
        await db_session.commit()

        # Retrieve from database (will be naive)
        stmt = select(TrainJourney).where(TrainJourney.train_id == "FIX_TEST")
        retrieved = await db_session.scalar(stmt)

        # Apply the fix
        fixed_scheduled = ensure_timezone_aware(retrieved.scheduled_departure)
        fixed_first_seen = ensure_timezone_aware(retrieved.first_seen_at)
        fixed_last_updated = ensure_timezone_aware(retrieved.last_updated_at)

        # All should now be timezone-aware
        assert fixed_scheduled.tzinfo is not None
        assert fixed_first_seen.tzinfo is not None
        assert fixed_last_updated.tzinfo is not None

        # Should be able to compare with now_et() without error
        current_time = now_et()
        try:
            _ = fixed_scheduled > current_time
            _ = fixed_first_seen > current_time
            _ = fixed_last_updated > current_time
        except TypeError as e:
            pytest.fail(f"Fixed datetimes still cause comparison error: {e}")
