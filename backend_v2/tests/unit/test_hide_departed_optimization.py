"""
Unit tests for the hide_departed optimization in the departure service.

Tests verify that when hide_departed=True, the second pass (individual train refresh)
is skipped since past trains won't be shown in the response anyway.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from trackrat.services.departure import DepartureService
from trackrat.models.database import TrainJourney, JourneyStop
from trackrat.utils.time import now_et


class TestHideDepartedOptimization:
    """Test the hide_departed optimization that skips refreshing past trains."""

    @pytest.fixture
    def mock_session(self):
        """Create a properly mocked AsyncSession."""
        session = AsyncMock()

        # Mock the result object that SQLAlchemy returns
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
        session.begin_nested = MagicMock(return_value=AsyncMock())

        return session

    @pytest.fixture
    def service(self):
        """Create a DepartureService instance."""
        return DepartureService()

    @pytest.mark.asyncio
    async def test_hide_departed_skips_second_pass(self, service, mock_session):
        """Test that hide_departed=True skips the individual train refresh pass.

        When hide_departed=True, past trains won't be shown in the response anyway,
        so there's no point refreshing them. This optimization significantly reduces
        API calls and improves response time.
        """
        # Mock needs_refresh to return a train ID (indicating stale data exists)
        mock_session.scalar = AsyncMock(return_value=1)  # Stale data exists

        # Mock NJT client for bulk refresh (Pass 1)
        with patch("trackrat.services.departure.NJTransitClient") as mock_njt:
            mock_client = AsyncMock()
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": []}  # Empty - no trains in bulk refresh
            )
            mock_client.close = AsyncMock()
            mock_njt.return_value = mock_client

            # Mock JourneyCollector to verify it's NOT called
            with patch(
                "trackrat.services.departure.NJTJourneyCollector"
            ) as mock_collector_class:
                mock_collector = AsyncMock()
                mock_collector.collect_journey_details = AsyncMock()
                mock_collector_class.return_value = mock_collector

                # Call with hide_departed=True
                await service._ensure_fresh_station_data(
                    mock_session,
                    "NY",
                    now_et().date(),
                    skip_individual_refresh=False,
                    hide_departed=True,
                )

                # Verify bulk refresh was called (Pass 1)
                mock_client.get_train_schedule_with_stops.assert_called_once_with("NY")

                # Verify JourneyCollector was NOT instantiated (Pass 2 skipped)
                mock_collector_class.assert_not_called()

    @pytest.mark.asyncio
    async def test_hide_departed_false_runs_second_pass(self, service, mock_session):
        """Test that hide_departed=False (default) runs individual refreshes.

        When hide_departed=False, past trains will be shown, so they need to be
        refreshed to show accurate arrival times and completion status.
        """
        # Mock needs_refresh to return a train ID (indicating stale data exists)
        mock_session.scalar = AsyncMock(return_value=1)

        # Create a mock stale journey that would be found by the second pass query
        stale_journey = MagicMock(spec=TrainJourney)
        stale_journey.train_id = "3840"
        stale_journey.id = 1

        # Mock the second pass query to return the stale journey
        mock_result = Mock()
        mock_scalars = Mock()
        mock_scalars.unique.return_value.all.return_value = [stale_journey]
        mock_result.scalars.return_value = mock_scalars

        # First call returns stale data indicator, subsequent calls return query results
        call_count = [0]

        async def mock_scalar_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return 1  # Stale data exists
            return None

        mock_session.scalar = AsyncMock(side_effect=mock_scalar_side_effect)
        mock_session.execute = AsyncMock(return_value=mock_result)
        # Mock session.get() for the retry_on_deadlock re-query
        mock_session.get = AsyncMock(return_value=stale_journey)

        with patch("trackrat.services.departure.NJTransitClient") as mock_njt:
            mock_client = AsyncMock()
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": []}
            )
            mock_client.close = AsyncMock()
            mock_njt.return_value = mock_client

            with patch(
                "trackrat.services.departure.NJTJourneyCollector"
            ) as mock_collector_class:
                mock_collector = AsyncMock()
                mock_collector.collect_journey_details = AsyncMock()
                mock_collector_class.return_value = mock_collector

                # Call with hide_departed=False (default)
                await service._ensure_fresh_station_data(
                    mock_session,
                    "NY",
                    now_et().date(),
                    skip_individual_refresh=False,
                    hide_departed=False,
                )

                # Verify JourneyCollector WAS instantiated (Pass 2 ran)
                mock_collector_class.assert_called_once()
                # Verify collect_journey_details was called for the stale journey
                mock_collector.collect_journey_details.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_departures_passes_hide_departed_to_station_refresh(
        self, service, mock_session
    ):
        """Test that get_departures passes hide_departed to station refresh."""
        # Mock _maybe_trigger_background_refresh to verify parameters
        with patch.object(
            service, "_maybe_trigger_background_refresh", new_callable=AsyncMock
        ) as mock_refresh:
            # Mock the query to return empty results
            mock_result = Mock()
            mock_scalars = Mock()
            mock_scalars.unique.return_value.all.return_value = []
            mock_result.scalars.return_value = mock_scalars
            mock_session.execute = AsyncMock(return_value=mock_result)

            await service.get_departures(
                db=mock_session,
                from_station="NY",
                time_from=now_et(),
                time_to=now_et() + timedelta(hours=3),
                hide_departed=True,
            )

            # Verify _maybe_trigger_background_refresh was called with hide_departed=True
            mock_refresh.assert_called_once()
            call_args = mock_refresh.call_args
            # Args: db, from_station, target_date, skip_individual_refresh, hide_departed
            assert call_args[0][4] is True  # 5th positional arg is hide_departed

    @pytest.mark.asyncio
    async def test_get_departures_default_hide_departed_false(
        self, service, mock_session
    ):
        """Test that get_departures defaults hide_departed to False."""
        with patch.object(
            service, "_maybe_trigger_background_refresh", new_callable=AsyncMock
        ) as mock_refresh:
            mock_result = Mock()
            mock_scalars = Mock()
            mock_scalars.unique.return_value.all.return_value = []
            mock_result.scalars.return_value = mock_scalars
            mock_session.execute = AsyncMock(return_value=mock_result)

            await service.get_departures(
                db=mock_session,
                from_station="NY",
                time_from=now_et(),
                time_to=now_et() + timedelta(hours=3),
                # Note: not passing hide_departed, should default to False
            )

            # Verify _maybe_trigger_background_refresh was called with hide_departed=False
            mock_refresh.assert_called_once()
            call_args = mock_refresh.call_args
            assert call_args[0][4] is False  # 5th positional arg is hide_departed

    @pytest.mark.asyncio
    async def test_skip_individual_refresh_takes_precedence(
        self, service, mock_session
    ):
        """Test that skip_individual_refresh=True also skips second pass."""
        mock_session.scalar = AsyncMock(return_value=1)  # Stale data exists

        with patch("trackrat.services.departure.NJTransitClient") as mock_njt:
            mock_client = AsyncMock()
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": []}
            )
            mock_client.close = AsyncMock()
            mock_njt.return_value = mock_client

            with patch(
                "trackrat.services.departure.NJTJourneyCollector"
            ) as mock_collector_class:
                mock_collector = AsyncMock()
                mock_collector_class.return_value = mock_collector

                # Call with skip_individual_refresh=True but hide_departed=False
                await service._ensure_fresh_station_data(
                    mock_session,
                    "NY",
                    now_et().date(),
                    skip_individual_refresh=True,
                    hide_departed=False,
                )

                # Verify JourneyCollector was NOT instantiated
                mock_collector_class.assert_not_called()

    @pytest.mark.asyncio
    async def test_both_flags_skip_second_pass(self, service, mock_session):
        """Test that both flags together also skip second pass."""
        mock_session.scalar = AsyncMock(return_value=1)  # Stale data exists

        with patch("trackrat.services.departure.NJTransitClient") as mock_njt:
            mock_client = AsyncMock()
            mock_client.get_train_schedule_with_stops = AsyncMock(
                return_value={"ITEMS": []}
            )
            mock_client.close = AsyncMock()
            mock_njt.return_value = mock_client

            with patch(
                "trackrat.services.departure.NJTJourneyCollector"
            ) as mock_collector_class:
                mock_collector = AsyncMock()
                mock_collector_class.return_value = mock_collector

                # Call with both flags True
                await service._ensure_fresh_station_data(
                    mock_session,
                    "NY",
                    now_et().date(),
                    skip_individual_refresh=True,
                    hide_departed=True,
                )

                # Verify JourneyCollector was NOT instantiated
                mock_collector_class.assert_not_called()
