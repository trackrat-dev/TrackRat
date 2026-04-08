"""
Tests for the fix where NJT OBSERVED departures permanently show null real-time
times because last_updated_at is bumped even when the NJT API returns empty STOPS.

The core invariant: if getTrainSchedule returns a train without STOPS data,
the journey must NOT be marked "fresh" — so the second-pass individual refresh
(getTrainStopList) can still pick it up.
"""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from trackrat.models.database import TrainJourney
from trackrat.services.departure import DepartureService
from trackrat.utils.time import now_et


class TestBulkRefreshEmptyStops:
    """Verify that bulk refresh with empty STOPS leaves trains eligible
    for the second-pass individual refresh."""

    @pytest.fixture
    def mock_session(self):
        """Create a properly mocked AsyncSession."""
        session = AsyncMock()
        mock_result = Mock()
        mock_scalars = Mock()
        mock_scalars.unique.return_value.all.return_value = []
        mock_scalars.all.return_value = []
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_result.scalar.return_value = None
        session.execute = AsyncMock(return_value=mock_result)
        session.scalar = AsyncMock(return_value=None)
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        session.rollback = AsyncMock()
        session.add = Mock()
        session.refresh = AsyncMock()
        session.get = AsyncMock(return_value=None)
        return session

    @pytest.fixture
    def service(self):
        return DepartureService()

    @pytest.mark.asyncio
    async def test_empty_stops_does_not_suppress_second_pass(
        self, service, mock_session
    ):
        """When bulk getTrainSchedule returns a train with STOPS=[], the train
        must remain stale so the second-pass getTrainStopList refresh picks it up.

        This prevents the infinite loop where every 60s JIT fires, marks the train
        fresh without data, and the fallback never kicks in.
        """
        stale_time = now_et() - timedelta(minutes=5)

        # Create a journey that is stale (last_updated_at 5 minutes ago)
        journey = TrainJourney()
        journey.id = 1
        journey.train_id = "3893"
        journey.data_source = "NJT"
        journey.journey_date = now_et().date()
        journey.last_updated_at = stale_time
        journey.update_count = 0
        journey.has_complete_journey = False
        journey.is_expired = False
        journey.is_completed = False
        journey.is_cancelled = False

        # Bulk refresh returns this train WITHOUT STOPS data
        train_items = [
            {
                "TRAIN_ID": "3893",
                "DESTINATION": "Trenton",
                "BACKCOLOR": "#FF6600 ",
                # No STOPS key — NJT API intermittency
            }
        ]

        # Mock needs_refresh scalar to return a stale journey id
        mock_session.scalar = AsyncMock(return_value=1)

        # Set up bulk query to return our journey
        journey_result = Mock()
        journey_scalars = Mock()
        journey_scalars.all.return_value = [journey]
        journey_result.scalars.return_value = journey_scalars

        # Second-pass stale query should also return our journey
        # (because it's still stale after bulk refresh with empty STOPS)
        stale_result = Mock()
        stale_scalars = Mock()
        stale_scalars.unique.return_value.all.return_value = [journey]
        stale_result.scalars.return_value = stale_scalars

        # Track which execute calls return which results
        execute_call_count = 0

        async def mock_execute(stmt, *args, **kwargs):
            nonlocal execute_call_count
            execute_call_count += 1
            # First execute: stale check query
            # Second execute: bulk journey query
            if execute_call_count == 2:
                return journey_result
            # Third execute: second-pass stale query
            if execute_call_count == 3:
                return stale_result
            # Default: empty result
            empty_result = Mock()
            empty_scalars = Mock()
            empty_scalars.unique.return_value.all.return_value = []
            empty_scalars.all.return_value = []
            empty_result.scalars.return_value = empty_scalars
            empty_result.scalar.return_value = None
            return empty_result

        mock_session.execute = AsyncMock(side_effect=mock_execute)

        with (
            patch("trackrat.services.departure.NJTransitClient") as mock_njt,
            patch(
                "trackrat.services.departure.NJTJourneyCollector"
            ) as mock_collector_class,
            patch("trackrat.services.departure.retry_on_deadlock") as mock_retry,
        ):
            mock_client = AsyncMock()
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": train_items}
            )
            mock_client.close = AsyncMock()
            mock_njt.return_value = mock_client

            # retry_on_deadlock should call the function directly
            mock_retry.side_effect = lambda db, func: func()

            mock_collector = AsyncMock()
            mock_collector.collect_journey_details = AsyncMock()
            mock_collector_class.return_value = mock_collector

            await service._ensure_fresh_station_data(
                mock_session,
                "NY",
                now_et().date(),
                skip_individual_refresh=False,
                hide_departed=False,
            )

            # Key assertion: last_updated_at should NOT have been bumped
            assert journey.last_updated_at == stale_time, (
                f"last_updated_at should remain at {stale_time} when STOPS is empty, "
                f"but was bumped to {journey.last_updated_at}"
            )

            # update_count SHOULD be incremented (tracks refresh attempts)
            assert journey.update_count == 1, (
                f"update_count should be 1 (attempt counted), got {journey.update_count}"
            )

            # has_complete_journey should NOT be set
            assert not journey.has_complete_journey, (
                "has_complete_journey should remain False when STOPS is empty"
            )

    @pytest.mark.asyncio
    async def test_nonempty_stops_marks_fresh(self, service, mock_session):
        """When bulk getTrainSchedule returns a train WITH STOPS data, the train
        should be marked fresh (last_updated_at bumped) so the second pass skips it.
        """
        stale_time = now_et() - timedelta(minutes=5)

        journey = TrainJourney()
        journey.id = 1
        journey.train_id = "3893"
        journey.data_source = "NJT"
        journey.journey_date = now_et().date()
        journey.last_updated_at = stale_time
        journey.update_count = 0
        journey.has_complete_journey = False
        journey.is_expired = False
        journey.is_completed = False
        journey.is_cancelled = False
        journey.scheduled_arrival = None

        train_items = [
            {
                "TRAIN_ID": "3893",
                "DESTINATION": "Trenton",
                "BACKCOLOR": "#FF6600 ",
                "STOPS": [
                    {
                        "STATION_2CHAR": "NY",
                        "SCHED_DEP_DATE": "2025-01-01 10:00:00",
                        "TIME": "10:00 AM",
                    },
                    {
                        "STATION_2CHAR": "TR",
                        "SCHED_DEP_DATE": "2025-01-01 11:00:00",
                        "TIME": "11:00 AM",
                    },
                ],
            }
        ]

        mock_session.scalar = AsyncMock(return_value=1)

        journey_result = Mock()
        journey_scalars = Mock()
        journey_scalars.all.return_value = [journey]
        journey_result.scalars.return_value = journey_scalars

        execute_call_count = 0

        async def mock_execute(stmt, *args, **kwargs):
            nonlocal execute_call_count
            execute_call_count += 1
            if execute_call_count == 2:
                return journey_result
            empty_result = Mock()
            empty_scalars = Mock()
            empty_scalars.unique.return_value.all.return_value = []
            empty_scalars.all.return_value = []
            empty_result.scalars.return_value = empty_scalars
            empty_result.scalar.return_value = None
            return empty_result

        mock_session.execute = AsyncMock(side_effect=mock_execute)

        with (
            patch("trackrat.services.departure.NJTransitClient") as mock_njt,
            patch(
                "trackrat.services.departure.NJTJourneyCollector"
            ) as mock_collector_class,
            patch("trackrat.services.departure.retry_on_deadlock") as mock_retry,
            patch.object(
                service,
                "_update_stops_from_embedded_data",
                new_callable=AsyncMock,
            ),
        ):
            mock_client = AsyncMock()
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": train_items}
            )
            mock_client.close = AsyncMock()
            mock_njt.return_value = mock_client

            mock_retry.side_effect = lambda db, func: func()

            await service._ensure_fresh_station_data(
                mock_session,
                "NY",
                now_et().date(),
                skip_individual_refresh=True,
                hide_departed=False,
            )

            # Key assertion: last_updated_at SHOULD have been bumped
            assert journey.last_updated_at > stale_time, (
                f"last_updated_at should be bumped when STOPS are present, "
                f"but remained at {journey.last_updated_at}"
            )

            assert journey.has_complete_journey is True, (
                "has_complete_journey should be True when STOPS are present"
            )
