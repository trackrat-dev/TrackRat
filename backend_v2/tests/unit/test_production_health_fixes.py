"""
Tests for production health fixes:

1. Amtrak SCHEDULED→OBSERVED promotion in scheduler (schedule_amtrak_journey_collections)
2. Amtrak SCHEDULED→OBSERVED promotion in JIT refresh (collect_journey_details)
3. Live activity session scope fix (update_live_activities uses session within context)

These tests validate that:
- SCHEDULED trains are collected (not skipped) by the discovery→batch pipeline
- OBSERVED trains are correctly skipped to avoid redundant collection
- New trains (no existing record) are always collected
- The JIT refresh path promotes SCHEDULED→OBSERVED when real-time data is found
- The JIT refresh path does NOT downgrade OBSERVED trains
- Live activity updates properly scope all DB operations within the session context
"""

import asyncio
from datetime import UTC, datetime, date, timedelta
from unittest.mock import ANY, AsyncMock, Mock, MagicMock, patch, call

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.amtrak.journey import AmtrakJourneyCollector
from trackrat.models.database import TrainJourney
from trackrat.services.scheduler import SchedulerService
from trackrat.settings import Settings
from trackrat.utils.time import ET
from tests.factories.amtrak import (
    create_amtrak_train_data,
    create_amtrak_station_data,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_settings():
    """Create test settings for scheduler."""
    return Settings(
        njt_api_token="test_token",
        discovery_interval_minutes=30,
        journey_update_interval_minutes=15,
        data_staleness_seconds=60,
        environment="testing",
    )


@pytest.fixture
def scheduler_service(test_settings):
    """Create a SchedulerService instance for testing."""
    with patch("trackrat.services.scheduler.NJTransitClient"):
        return SchedulerService(settings=test_settings)


@pytest.fixture
def journey_collector():
    """Create an AmtrakJourneyCollector instance."""
    return AmtrakJourneyCollector()


@pytest.fixture
def mock_db_session():
    """Create a mock async database session."""
    session = AsyncMock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def sample_train_data():
    """Create sample Amtrak train data for testing."""
    return create_amtrak_train_data(
        train_id="2150-4",
        train_num="2150",
        route="Northeast Regional",
        train_state="Active",
        stations=[
            create_amtrak_station_data(
                code="NYP",
                name="New York Penn Station",
                sch_dep="2025-07-05T14:30:00-05:00",
                status="Departed",
                platform="15",
            ),
            create_amtrak_station_data(
                code="NWK",
                name="Newark Penn Station",
                sch_arr="2025-07-05T14:45:00-05:00",
                sch_dep="2025-07-05T14:47:00-05:00",
                status="Enroute",
            ),
            create_amtrak_station_data(
                code="PHL",
                name="Philadelphia",
                sch_arr="2025-07-05T15:45:00-05:00",
                sch_dep="2025-07-05T15:50:00-05:00",
                status="Enroute",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# 1. Tests for schedule_amtrak_journey_collections — SCHEDULED promotion fix
# ---------------------------------------------------------------------------


class TestScheduleAmtrakJourneyCollections:
    """Tests for the fix where SCHEDULED trains were skipped by discovery.

    The bug: schedule_amtrak_journey_collections() checked if a journey already
    existed and skipped it entirely. Since AmtrakPatternScheduler creates
    SCHEDULED records daily, discovery found trains but never triggered batch
    collection to promote them to OBSERVED.

    The fix: trains with observation_type == "SCHEDULED" are now also collected.
    """

    @pytest.mark.asyncio
    async def test_scheduled_trains_are_collected_not_skipped(self, scheduler_service):
        """SCHEDULED trains must be included in batch collection.

        This is the core regression test for the bug: previously, any train
        with an existing journey record was skipped, even if it was still
        SCHEDULED. Now SCHEDULED trains go through collection so _convert_to_journey
        can promote them to OBSERVED.
        """
        # Simulate discovery finding two trains
        train_ids = ["2150-4", "141-4"]

        # Mock existing SCHEDULED journey for train A2150
        mock_scheduled_journey = Mock(spec=TrainJourney)
        mock_scheduled_journey.observation_type = "SCHEDULED"

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_session = AsyncMock()

            # First call: A2150 has SCHEDULED record; second: A141 has no record
            mock_session.scalar.side_effect = [mock_scheduled_journey, None]

            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Mock the scheduler to capture what gets scheduled
            mock_scheduler = Mock()
            mock_scheduler.get_job.return_value = None  # No existing batch job
            scheduler_service.scheduler = mock_scheduler

            with patch("trackrat.services.scheduler.now_et") as mock_now:
                mock_now.return_value = ET.localize(datetime(2025, 7, 5, 14, 0, 0))

                await scheduler_service.schedule_amtrak_journey_collections(train_ids)

            # Verify batch job was scheduled with BOTH trains (not just the new one)
            mock_scheduler.add_job.assert_called_once()
            # trains_to_collect is passed via kwargs['args'] to add_job
            batch_trains = mock_scheduler.add_job.call_args.kwargs["args"][0]
            assert len(batch_trains) == 2, (
                f"Expected 2 trains (1 SCHEDULED + 1 new), got {len(batch_trains)}: "
                f"{batch_trains}"
            )
            assert "2150-4" in batch_trains, "SCHEDULED train should be collected"
            assert "141-4" in batch_trains, "New train should be collected"

    @pytest.mark.asyncio
    async def test_observed_trains_are_skipped(self, scheduler_service):
        """OBSERVED trains should NOT be re-collected — they're already promoted."""
        train_ids = ["2150-4"]

        mock_observed_journey = Mock(spec=TrainJourney)
        mock_observed_journey.observation_type = "OBSERVED"

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_session.scalar.return_value = mock_observed_journey
            mock_get_session.return_value.__aenter__.return_value = mock_session

            mock_scheduler = Mock()
            scheduler_service.scheduler = mock_scheduler

            with patch("trackrat.services.scheduler.now_et") as mock_now:
                mock_now.return_value = ET.localize(datetime(2025, 7, 5, 14, 0, 0))

                await scheduler_service.schedule_amtrak_journey_collections(train_ids)

            # No batch job should be scheduled for already-OBSERVED trains
            mock_scheduler.add_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_trains_without_existing_records_are_collected(
        self, scheduler_service
    ):
        """Trains with no existing journey record should always be collected."""
        train_ids = ["999-4"]

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_session.scalar.return_value = None  # No existing record
            mock_get_session.return_value.__aenter__.return_value = mock_session

            mock_scheduler = Mock()
            mock_scheduler.get_job.return_value = None
            scheduler_service.scheduler = mock_scheduler

            with patch("trackrat.services.scheduler.now_et") as mock_now:
                mock_now.return_value = ET.localize(datetime(2025, 7, 5, 14, 0, 0))

                await scheduler_service.schedule_amtrak_journey_collections(train_ids)

            mock_scheduler.add_job.assert_called_once()
            batch_trains = mock_scheduler.add_job.call_args.kwargs["args"][0]
            assert "999-4" in batch_trains

    @pytest.mark.asyncio
    async def test_mixed_observation_types_filters_correctly(self, scheduler_service):
        """With a mix of SCHEDULED, OBSERVED, and new trains, only non-OBSERVED
        trains should be collected."""
        train_ids = ["100-4", "200-4", "300-4"]

        mock_scheduled = Mock(spec=TrainJourney)
        mock_scheduled.observation_type = "SCHEDULED"

        mock_observed = Mock(spec=TrainJourney)
        mock_observed.observation_type = "OBSERVED"

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_session = AsyncMock()
            # A100: SCHEDULED, A200: OBSERVED, A300: new (None)
            mock_session.scalar.side_effect = [mock_scheduled, mock_observed, None]
            mock_get_session.return_value.__aenter__.return_value = mock_session

            mock_scheduler = Mock()
            mock_scheduler.get_job.return_value = None
            scheduler_service.scheduler = mock_scheduler

            with patch("trackrat.services.scheduler.now_et") as mock_now:
                mock_now.return_value = ET.localize(datetime(2025, 7, 5, 14, 0, 0))

                await scheduler_service.schedule_amtrak_journey_collections(train_ids)

            mock_scheduler.add_job.assert_called_once()
            batch_trains = mock_scheduler.add_job.call_args.kwargs["args"][0]
            assert (
                len(batch_trains) == 2
            ), f"Expected SCHEDULED + new = 2, got {len(batch_trains)}"
            assert "100-4" in batch_trains, "SCHEDULED train A100 should be collected"
            assert "300-4" in batch_trains, "New train A300 should be collected"
            assert "200-4" not in batch_trains, "OBSERVED train A200 should be skipped"

    @pytest.mark.asyncio
    async def test_empty_train_ids_does_nothing(self, scheduler_service):
        """Empty train_ids list should return without scheduling anything."""
        mock_scheduler = Mock()
        scheduler_service.scheduler = mock_scheduler

        await scheduler_service.schedule_amtrak_journey_collections([])

        mock_scheduler.add_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_deduplication_by_train_number(self, scheduler_service):
        """Multiple API entries for the same train number should be deduplicated.

        Amtrak API returns trainID like "2150-4" where -4 is the day suffix.
        The scheduler converts to internal ID "A2150" and deduplicates.
        """
        # Same train number, different day suffixes
        train_ids = ["2150-4", "2150-5"]

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_session.scalar.return_value = None  # No existing record
            mock_get_session.return_value.__aenter__.return_value = mock_session

            mock_scheduler = Mock()
            mock_scheduler.get_job.return_value = None
            scheduler_service.scheduler = mock_scheduler

            with patch("trackrat.services.scheduler.now_et") as mock_now:
                mock_now.return_value = ET.localize(datetime(2025, 7, 5, 14, 0, 0))

                await scheduler_service.schedule_amtrak_journey_collections(train_ids)

            # Should only have 1 train after deduplication (first occurrence kept)
            mock_scheduler.add_job.assert_called_once()
            batch_trains = mock_scheduler.add_job.call_args.kwargs["args"][0]
            assert len(batch_trains) == 1
            assert batch_trains[0] == "2150-4"


# ---------------------------------------------------------------------------
# 2. Tests for collect_journey_details — JIT SCHEDULED→OBSERVED promotion
# ---------------------------------------------------------------------------


class TestCollectJourneyDetailsPromotion:
    """Tests for the JIT refresh path promoting SCHEDULED→OBSERVED.

    The bug: collect_journey_details() updated stops, times, completion status,
    and snapshots — but never set observation_type to OBSERVED. This meant the
    one code path that DOES execute for existing SCHEDULED journeys (user-triggered
    JIT refresh) omitted the promotion.

    The fix: when collect_journey_details() successfully fetches real-time data,
    it promotes SCHEDULED to OBSERVED.
    """

    @pytest.mark.asyncio
    async def test_scheduled_promoted_to_observed_on_jit_refresh(
        self, journey_collector, mock_db_session, sample_train_data
    ):
        """A SCHEDULED journey should become OBSERVED when JIT refresh finds
        real-time data from the Amtrak API."""
        # Create a SCHEDULED journey
        journey = TrainJourney(
            id=42,
            train_id="A2150",
            journey_date=date(2025, 7, 5),
            data_source="AMTRAK",
            observation_type="SCHEDULED",
            line_code="AM",
            line_name="Amtrak",
            origin_station_code="NY",
            terminal_station_code="NY",
            scheduled_departure=ET.localize(datetime(2025, 7, 5, 14, 30, 0)),
            has_complete_journey=False,
            stops_count=0,
            update_count=0,
            api_error_count=0,
        )

        # Mock the client to return real-time data
        mock_client = AsyncMock()
        mock_client.get_all_trains.return_value = {
            "station1": [sample_train_data],
        }

        with patch.object(journey_collector, "client", mock_client):
            with patch("trackrat.collectors.amtrak.journey.now_et") as mock_now:
                mock_now.return_value = ET.localize(datetime(2025, 7, 5, 15, 0, 0))

                with patch(
                    "trackrat.collectors.amtrak.journey.TransitAnalyzer"
                ) as mock_ta:
                    mock_ta.return_value.analyze_new_segments = AsyncMock(
                        return_value=0
                    )

                    await journey_collector.collect_journey_details(
                        mock_db_session, journey
                    )

        # The key assertion: observation_type must be promoted
        assert journey.observation_type == "OBSERVED", (
            "Journey should be promoted from SCHEDULED to OBSERVED after "
            "JIT refresh fetches real-time API data"
        )
        assert (
            journey.first_seen_at is not None
        ), "first_seen_at should be set when promoting to OBSERVED"
        assert journey.update_count == 1, "update_count should be incremented"

    @pytest.mark.asyncio
    async def test_observed_stays_observed_on_jit_refresh(
        self, journey_collector, mock_db_session, sample_train_data
    ):
        """An already-OBSERVED journey should remain OBSERVED (not downgraded)."""
        journey = TrainJourney(
            id=42,
            train_id="A2150",
            journey_date=date(2025, 7, 5),
            data_source="AMTRAK",
            observation_type="OBSERVED",
            line_code="AM",
            line_name="Amtrak",
            origin_station_code="NY",
            terminal_station_code="NY",
            scheduled_departure=ET.localize(datetime(2025, 7, 5, 14, 30, 0)),
            has_complete_journey=True,
            stops_count=3,
            update_count=5,
            api_error_count=0,
            first_seen_at=ET.localize(datetime(2025, 7, 5, 12, 0, 0)),
        )
        original_first_observed = journey.first_seen_at

        mock_client = AsyncMock()
        mock_client.get_all_trains.return_value = {
            "station1": [sample_train_data],
        }

        with patch.object(journey_collector, "client", mock_client):
            with patch("trackrat.collectors.amtrak.journey.now_et") as mock_now:
                mock_now.return_value = ET.localize(datetime(2025, 7, 5, 15, 0, 0))

                with patch(
                    "trackrat.collectors.amtrak.journey.TransitAnalyzer"
                ) as mock_ta:
                    mock_ta.return_value.analyze_new_segments = AsyncMock(
                        return_value=0
                    )

                    await journey_collector.collect_journey_details(
                        mock_db_session, journey
                    )

        assert journey.observation_type == "OBSERVED"
        assert (
            journey.first_seen_at == original_first_observed
        ), "first_seen_at should NOT be overwritten for already-OBSERVED journeys"
        assert journey.update_count == 6

    @pytest.mark.asyncio
    async def test_scheduled_not_promoted_when_api_returns_no_data(
        self, journey_collector, mock_db_session
    ):
        """If the Amtrak API doesn't find the train, observation_type should
        NOT be changed and api_error_count should increment."""
        journey = TrainJourney(
            id=42,
            train_id="A2150",
            journey_date=date(2025, 7, 5),
            data_source="AMTRAK",
            observation_type="SCHEDULED",
            line_code="AM",
            line_name="Amtrak",
            origin_station_code="NY",
            terminal_station_code="NY",
            scheduled_departure=ET.localize(datetime(2025, 7, 5, 14, 30, 0)),
            has_complete_journey=False,
            stops_count=0,
            update_count=0,
            api_error_count=0,
        )

        # API returns empty data (train not found)
        mock_client = AsyncMock()
        mock_client.get_all_trains.return_value = {}

        with patch.object(journey_collector, "client", mock_client):
            with patch("trackrat.collectors.amtrak.journey.now_et") as mock_now:
                mock_now.return_value = ET.localize(datetime(2025, 7, 5, 15, 0, 0))

                with patch(
                    "trackrat.collectors.amtrak.journey.TransitAnalyzer"
                ) as mock_ta:
                    mock_ta.return_value.analyze_new_segments = AsyncMock(
                        return_value=0
                    )

                    await journey_collector.collect_journey_details(
                        mock_db_session, journey
                    )

        assert (
            journey.observation_type == "SCHEDULED"
        ), "Should remain SCHEDULED when API returns no data"
        assert (
            journey.api_error_count == 1
        ), "api_error_count should increment when train not found"


# ---------------------------------------------------------------------------
# 3. Tests for update_live_activities — session scope fix
# ---------------------------------------------------------------------------


class TestLiveActivitySessionScope:
    """Tests for the session scope fix in update_live_activities.

    The bug: `with SyncSession() as session:` only contained the stmt
    construction. All session.execute(), session.scalar(), and session.commit()
    calls ran outside the `with` block on a closed session.

    The fix: all session-using code is now indented inside the `with` block.

    These tests verify that the session is used properly for all DB operations.
    """

    @pytest.mark.asyncio
    async def test_session_execute_called_within_context(self, scheduler_service):
        """Verify that session.execute is called (proving it's within the
        context manager scope — a closed session would raise)."""
        scheduler_service.apns_service = AsyncMock()

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            with patch("sqlalchemy.create_engine") as mock_create_engine:
                with patch("sqlalchemy.orm.sessionmaker") as mock_sessionmaker:
                    mock_sync_session = Mock()
                    mock_sync_engine = Mock()
                    mock_create_engine.return_value = mock_sync_engine
                    mock_sessionmaker.return_value = Mock(
                        return_value=mock_sync_session
                    )

                    # Return no active tokens — this exercises the session.execute path
                    mock_empty_result = Mock()
                    mock_empty_result.scalars.return_value = []
                    mock_sync_session.execute.return_value = mock_empty_result
                    mock_sync_session.__enter__ = Mock(return_value=mock_sync_session)
                    mock_sync_session.__exit__ = Mock(return_value=None)

                    with patch(
                        "trackrat.services.scheduler.run_with_freshness_check"
                    ) as mock_freshness_check:

                        async def execute_task_func(
                            db, task_name, minimum_interval_seconds, task_func
                        ):
                            await task_func()
                            return True

                        mock_freshness_check.side_effect = execute_task_func

                        await scheduler_service.update_live_activities()

                    # Verify execute was called within the session context
                    mock_sync_session.execute.assert_called_once()
                    # Verify __enter__ and __exit__ were called (context manager used)
                    mock_sync_session.__enter__.assert_called_once()
                    mock_sync_session.__exit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_scalar_called_for_journey_lookup(self, scheduler_service):
        """Verify that session.scalar (journey lookup) runs within the session
        context — this was one of the DB ops outside the `with` block."""
        scheduler_service.apns_service = AsyncMock()
        scheduler_service.apns_service.send_live_activity_update = AsyncMock(
            return_value=True
        )

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            with patch("sqlalchemy.create_engine") as mock_create_engine:
                with patch("sqlalchemy.orm.sessionmaker") as mock_sessionmaker:
                    mock_sync_session = Mock()
                    mock_sync_engine = Mock()
                    mock_create_engine.return_value = mock_sync_engine
                    mock_sessionmaker.return_value = Mock(
                        return_value=mock_sync_session
                    )

                    # Create a mock token
                    mock_token = Mock(
                        push_token="token1",
                        activity_id="activity1",
                        train_number="1234",
                        origin_code="NY",
                        destination_code="TR",
                        expires_at=datetime.now(UTC) + timedelta(hours=1),
                        is_active=True,
                    )
                    mock_tokens_result = Mock()
                    mock_tokens_result.scalars.return_value = [mock_token]

                    # Mock journey
                    mock_journey = Mock(
                        train_id="1234",
                        observation_type="OBSERVED",
                        is_cancelled=False,
                        is_completed=False,
                        is_expired=False,
                        last_updated_at=datetime.now(UTC),
                        stops=[],
                    )

                    mock_sync_session.execute.return_value = mock_tokens_result
                    mock_sync_session.scalar.return_value = mock_journey
                    mock_sync_session.__enter__ = Mock(return_value=mock_sync_session)
                    mock_sync_session.__exit__ = Mock(return_value=None)

                    with patch.object(
                        scheduler_service, "_calculate_live_activity_content_state"
                    ) as mock_calc:
                        mock_calc.return_value = {"test": "content"}

                        with patch(
                            "trackrat.services.scheduler.run_with_freshness_check"
                        ) as mock_freshness_check:

                            async def execute_task_func(
                                db,
                                task_name,
                                minimum_interval_seconds,
                                task_func,
                            ):
                                await task_func()
                                return True

                            mock_freshness_check.side_effect = execute_task_func

                            await scheduler_service.update_live_activities()

                    # Verify session.scalar was called (journey lookup) within context
                    mock_sync_session.scalar.assert_called_once()
                    # Verify APNS was called (proving execution reached the end)
                    scheduler_service.apns_service.send_live_activity_update.assert_called_once_with(
                        "token1", {"test": "content"}
                    )

    @pytest.mark.asyncio
    async def test_session_commit_called_within_context_on_token_deactivation(
        self, scheduler_service
    ):
        """When a Live Activity update fails (410), the token is deactivated
        and session.commit() is called. This must happen within the session context."""
        mock_apns = AsyncMock()
        mock_apns.send_live_activity_update = AsyncMock(return_value=False)  # 410
        scheduler_service.apns_service = mock_apns

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            with patch("sqlalchemy.create_engine") as mock_create_engine:
                with patch("sqlalchemy.orm.sessionmaker") as mock_sessionmaker:
                    mock_sync_session = Mock()
                    mock_sync_engine = Mock()
                    mock_create_engine.return_value = mock_sync_engine
                    mock_sessionmaker.return_value = Mock(
                        return_value=mock_sync_session
                    )

                    mock_token = Mock(
                        push_token="token1",
                        activity_id="activity1",
                        train_number="1234",
                        origin_code="NY",
                        destination_code="TR",
                        expires_at=datetime.now(UTC) + timedelta(hours=1),
                        is_active=True,
                    )
                    mock_tokens_result = Mock()
                    mock_tokens_result.scalars.return_value = [mock_token]

                    mock_journey = Mock(
                        train_id="1234",
                        observation_type="OBSERVED",
                        is_cancelled=False,
                        is_completed=False,
                        is_expired=False,
                        last_updated_at=datetime.now(UTC),
                        stops=[],
                    )

                    mock_sync_session.execute.return_value = mock_tokens_result
                    mock_sync_session.scalar.return_value = mock_journey
                    mock_sync_session.__enter__ = Mock(return_value=mock_sync_session)
                    mock_sync_session.__exit__ = Mock(return_value=None)

                    with patch.object(
                        scheduler_service, "_calculate_live_activity_content_state"
                    ) as mock_calc:
                        mock_calc.return_value = {"test": "content"}

                        with patch(
                            "trackrat.services.scheduler.run_with_freshness_check"
                        ) as mock_freshness_check:

                            async def execute_task_func(
                                db,
                                task_name,
                                minimum_interval_seconds,
                                task_func,
                            ):
                                await task_func()
                                return True

                            mock_freshness_check.side_effect = execute_task_func

                            await scheduler_service.update_live_activities()

                    # Token should be marked inactive
                    assert (
                        mock_token.is_active is False
                    ), "Token should be deactivated on 410 response"
                    # session.commit() should have been called within context
                    mock_sync_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_engine_disposed_after_session_closes(self, scheduler_service):
        """sync_engine.dispose() should be called after the session context
        manager exits, to clean up the connection pool.

        Note: dispose() is called after the `with SyncSession()` block ends.
        When there are active tokens, the full code path runs and dispose()
        is called. With no tokens, early return skips dispose().
        """
        mock_apns = AsyncMock()
        mock_apns.send_live_activity_update = AsyncMock(return_value=True)
        scheduler_service.apns_service = mock_apns

        with patch("trackrat.services.scheduler.get_session") as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db

            with patch("sqlalchemy.create_engine") as mock_create_engine:
                with patch("sqlalchemy.orm.sessionmaker") as mock_sessionmaker:
                    mock_sync_session = Mock()
                    mock_sync_engine = Mock()
                    mock_create_engine.return_value = mock_sync_engine
                    mock_sessionmaker.return_value = Mock(
                        return_value=mock_sync_session
                    )

                    # Provide an active token so the code doesn't early-return
                    mock_token = Mock(
                        push_token="token1",
                        activity_id="activity1",
                        train_number="1234",
                        origin_code="NY",
                        destination_code="TR",
                        expires_at=datetime.now(UTC) + timedelta(hours=1),
                        is_active=True,
                    )
                    mock_tokens_result = Mock()
                    mock_tokens_result.scalars.return_value = [mock_token]

                    mock_journey = Mock(
                        train_id="1234",
                        observation_type="OBSERVED",
                        is_cancelled=False,
                        is_completed=False,
                        is_expired=False,
                        last_updated_at=datetime.now(UTC),
                        stops=[],
                    )

                    mock_sync_session.execute.return_value = mock_tokens_result
                    mock_sync_session.scalar.return_value = mock_journey
                    mock_sync_session.__enter__ = Mock(return_value=mock_sync_session)
                    mock_sync_session.__exit__ = Mock(return_value=None)

                    with patch.object(
                        scheduler_service, "_calculate_live_activity_content_state"
                    ) as mock_calc:
                        mock_calc.return_value = {"test": "content"}

                        with patch(
                            "trackrat.services.scheduler.run_with_freshness_check"
                        ) as mock_freshness_check:

                            async def execute_task_func(
                                db, task_name, minimum_interval_seconds, task_func
                            ):
                                await task_func()
                                return True

                            mock_freshness_check.side_effect = execute_task_func

                            await scheduler_service.update_live_activities()

                    # Engine should be disposed after use
                    mock_sync_engine.dispose.assert_called_once()
