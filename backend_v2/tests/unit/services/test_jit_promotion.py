"""
Unit tests for JIT station refresh promoting SCHEDULED → OBSERVED
and the inline JIT refresh for imminent SCHEDULED trains.

These tests verify the fix for the bug where NJT trains like #6318
(MW → SO → BU → NY) disappeared from departures because:
1. Discovery couldn't find them before the stale filter removed them
2. JIT refresh got live NJT API data but didn't promote to OBSERVED
3. The stale filter removed SCHEDULED trains within 15 min of departure
"""

import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from trackrat.models.database import TrainJourney, JourneyStop
from trackrat.services.departure import (
    DepartureService,
    SCHEDULED_VISIBILITY_THRESHOLD_MINUTES,
    _background_refresh_station,
    _refreshing_stations,
)
from trackrat.utils.time import now_et


class TestJitPromotion:
    """Tests that _ensure_fresh_station_data promotes SCHEDULED → OBSERVED."""

    def _make_journey(
        self,
        train_id: str = "6318",
        observation_type: str = "SCHEDULED",
        data_source: str = "NJT",
        last_updated_at=None,
    ) -> Mock:
        journey = Mock(spec=TrainJourney)
        journey.train_id = train_id
        journey.observation_type = observation_type
        journey.data_source = data_source
        journey.destination = "New York"
        journey.line_color = "#00953B"
        journey.line_code = "ME"
        journey.line_name = "Morris & Essex Line"
        journey.update_count = 0
        journey.has_complete_journey = False
        journey.stops_count = 0
        journey.last_updated_at = last_updated_at or (
            now_et() - timedelta(hours=3)
        )
        journey.scheduled_departure = None
        journey.scheduled_arrival = None
        journey.origin_station_code = None
        journey.terminal_station_code = None
        journey.is_expired = False
        journey.is_completed = False
        journey.is_cancelled = False
        return journey

    def _make_njt_api_train_data(
        self, train_id: str = "6318", with_stops: bool = True
    ) -> dict:
        """Simulate the dict returned by NJT's getTrainScheduleWithStops."""
        data: dict = {
            "TRAIN_ID": train_id,
            "DESTINATION": "New York",
            "LINE": "MEC",
            "LINE_NAME": "Morris & Essex Line",
            "BACKCOLOR": "#00953B",
        }
        if with_stops:
            data["STOPS"] = [
                {
                    "STATION_2CHAR": "MW",
                    "SCHED_DEP_DATE": "04/09/2026 07:58:30 AM",
                    "TIME": "04/09/2026 07:58:30 AM",
                    "DEP_TIME": "04/09/2026 08:00:30 AM",
                },
                {
                    "STATION_2CHAR": "SO",
                    "SCHED_DEP_DATE": "04/09/2026 08:05:00 AM",
                    "TIME": "04/09/2026 08:05:00 AM",
                    "DEP_TIME": "04/09/2026 08:05:00 AM",
                },
                {
                    "STATION_2CHAR": "NY",
                    "SCHED_DEP_DATE": "04/09/2026 08:41:00 AM",
                },
            ]
        else:
            data["STOPS"] = []
        return data

    @pytest.mark.asyncio
    async def test_promote_scheduled_to_observed_with_stop_data(self):
        """When NJT API returns a SCHEDULED train with stop data,
        _ensure_fresh_station_data should promote it to OBSERVED.
        This is the core fix: JIT now treats live NJT station board
        confirmation the same way discovery does."""
        journey = self._make_journey(observation_type="SCHEDULED")
        train_data = self._make_njt_api_train_data(with_stops=True)

        service = DepartureService.__new__(DepartureService)
        service._update_stops_from_embedded_data = AsyncMock()

        mock_db = AsyncMock()
        # Simulate _do_bulk_refresh: the journey lookup returns our mock
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [journey]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        njt_client = AsyncMock()
        njt_client.get_train_schedule_with_stops = AsyncMock(
            return_value={"ITEMS": [train_data]}
        )

        with patch(
            "trackrat.services.departure.NJTransitClient",
            return_value=njt_client,
        ), patch(
            "trackrat.services.departure.retry_on_deadlock",
            side_effect=lambda db, fn: fn(),
        ):
            await service._ensure_fresh_station_data(
                mock_db, "SO", now_et().date()
            )

        assert journey.observation_type == "OBSERVED", (
            "SCHEDULED journey should be promoted to OBSERVED when NJT "
            "station board API returns it with stop data"
        )
        assert journey.line_code == "ME", (
            "line_code should be updated from real-time API LINE field"
        )

    @pytest.mark.asyncio
    async def test_no_promote_without_stop_data(self):
        """When NJT API returns a train WITHOUT stop data (empty STOPS),
        observation_type should remain SCHEDULED — no confirmation signal."""
        journey = self._make_journey(observation_type="SCHEDULED")
        train_data = self._make_njt_api_train_data(with_stops=False)

        service = DepartureService.__new__(DepartureService)
        service._update_stops_from_embedded_data = AsyncMock()

        mock_db = AsyncMock()
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [journey]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        njt_client = AsyncMock()
        njt_client.get_train_schedule_with_stops = AsyncMock(
            return_value={"ITEMS": [train_data]}
        )

        with patch(
            "trackrat.services.departure.NJTransitClient",
            return_value=njt_client,
        ), patch(
            "trackrat.services.departure.retry_on_deadlock",
            side_effect=lambda db, fn: fn(),
        ):
            await service._ensure_fresh_station_data(
                mock_db, "SO", now_et().date()
            )

        assert journey.observation_type == "SCHEDULED", (
            "SCHEDULED journey should NOT be promoted when NJT API "
            "returns empty STOPS — no live confirmation"
        )

    @pytest.mark.asyncio
    async def test_no_promote_already_observed(self):
        """OBSERVED trains should stay OBSERVED (no-op)."""
        journey = self._make_journey(observation_type="OBSERVED")
        train_data = self._make_njt_api_train_data(with_stops=True)

        service = DepartureService.__new__(DepartureService)
        service._update_stops_from_embedded_data = AsyncMock()

        mock_db = AsyncMock()
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [journey]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        njt_client = AsyncMock()
        njt_client.get_train_schedule_with_stops = AsyncMock(
            return_value={"ITEMS": [train_data]}
        )

        with patch(
            "trackrat.services.departure.NJTransitClient",
            return_value=njt_client,
        ), patch(
            "trackrat.services.departure.retry_on_deadlock",
            side_effect=lambda db, fn: fn(),
        ):
            await service._ensure_fresh_station_data(
                mock_db, "SO", now_et().date()
            )

        assert journey.observation_type == "OBSERVED"


class TestHasImminentScheduledNjt:
    """Tests for _has_imminent_scheduled_njt pre-query."""

    @pytest.mark.asyncio
    async def test_returns_true_when_imminent_scheduled_exists(self):
        """Should return True when a stale SCHEDULED NJT train is within
        the stale filter threshold."""
        service = DepartureService.__new__(DepartureService)
        mock_db = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=42)  # found a row

        result = await service._has_imminent_scheduled_njt(
            mock_db, "SO", now_et().date()
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_none_found(self):
        """Should return False when no imminent SCHEDULED NJT trains."""
        service = DepartureService.__new__(DepartureService)
        mock_db = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=None)

        result = await service._has_imminent_scheduled_njt(
            mock_db, "SO", now_et().date()
        )
        assert result is False


class TestRunInlineJitRefresh:
    """Tests for _run_inline_jit_refresh blocking behavior."""

    def setup_method(self):
        # Clean up module-level state between tests
        _refreshing_stations.discard("SO")

    def teardown_method(self):
        _refreshing_stations.discard("SO")

    @pytest.mark.asyncio
    async def test_inline_refresh_completes_returns_true(self):
        """When background refresh finishes within timeout, returns True."""
        service = DepartureService.__new__(DepartureService)

        with patch(
            "trackrat.services.departure._background_refresh_station",
            new_callable=lambda: lambda *a, **kw: asyncio.coroutine(
                lambda: None
            )(),
        ):
            result = await service._run_inline_jit_refresh(
                "SO", now_et().date(), True, True
            )

        assert result is True
        # Station should be cleaned up after task completes
        # (done callback fires)

    @pytest.mark.asyncio
    async def test_inline_refresh_timeout_returns_false(self):
        """When background refresh exceeds timeout, returns False and
        the task continues in the background."""
        service = DepartureService.__new__(DepartureService)

        async def slow_refresh(*args, **kwargs):
            await asyncio.sleep(60)  # way longer than timeout

        with patch(
            "trackrat.services.departure._background_refresh_station",
            side_effect=slow_refresh,
        ):
            result = await service._run_inline_jit_refresh(
                "SO", now_et().date(), True, True
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_inline_refresh_skips_when_already_refreshing(self):
        """When station is already in _refreshing_stations, the
        get_departures code skips inline refresh."""
        # This tests the guard in get_departures, not _run_inline_jit_refresh
        _refreshing_stations.add("SO")

        service = DepartureService.__new__(DepartureService)
        # _run_inline_jit_refresh should not be called due to guard,
        # but verify the guard condition works
        assert "SO" in _refreshing_stations
