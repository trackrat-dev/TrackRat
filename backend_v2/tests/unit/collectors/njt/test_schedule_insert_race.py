"""
Unit tests for NJT schedule collector insert race condition handling.

Addresses issue #1123: IntegrityError from concurrent discovery/schedule
INSERT should be caught and treated as a skip, not logged as an error.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from trackrat.collectors.njt.schedule import NJTScheduleCollector


@pytest.fixture
def mock_njt_client():
    client = AsyncMock()
    return client


@pytest.fixture
def schedule_collector(mock_njt_client):
    return NJTScheduleCollector(mock_njt_client)


class TestScheduleInsertRace:
    """Test that IntegrityError during schedule INSERT is treated as a skip."""

    @pytest.mark.asyncio
    async def test_integrity_error_counted_as_skip_not_error(
        self, schedule_collector
    ):
        """When the savepoint commit raises IntegrityError (concurrent
        discovery already created the journey), it should increment
        skipped_observed, not errors."""
        mock_session = AsyncMock()

        # Make begin_nested() raise IntegrityError on __aexit__ (savepoint commit)
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=None)
        mock_cm.__aexit__ = AsyncMock(
            side_effect=IntegrityError(
                "duplicate key", params=None, orig=Exception("unique_train_journey")
            )
        )
        mock_session.begin_nested = MagicMock(return_value=mock_cm)
        mock_session.commit = AsyncMock()

        schedule_data = [
            {
                "STATION_2CHAR": "TR",
                "STATIONNAME": "Trenton",
                "ITEMS": [
                    {
                        "TRAIN_ID": "3737",
                        "SCHED_DEP_DATE": "01-Jan-2025 10:00:00 AM",
                        "DESTINATION": "New York Penn Station",
                        "LINE": "NEC",
                    },
                ],
            }
        ]

        with patch("trackrat.collectors.njt.schedule.logger") as mock_logger:
            stats = await schedule_collector._process_schedule_data(
                mock_session, schedule_data
            )

        # IntegrityError should be counted as skip, not error
        assert stats["skipped_observed"] == 1
        assert stats["errors"] == 0

        # Should log at info level, not error
        mock_logger.info.assert_any_call(
            "schedule_insert_race_skipped",
            station_code="TR",
            train_id="3737",
        )

    @pytest.mark.asyncio
    async def test_integrity_error_does_not_block_other_items(
        self, schedule_collector
    ):
        """An IntegrityError on one schedule item should not prevent
        processing subsequent items in the same station."""
        mock_session = AsyncMock()

        call_count = 0

        async def aexit_side_effect(exc_type, exc_val, exc_tb):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise IntegrityError(
                    "duplicate key",
                    params=None,
                    orig=Exception("unique_train_journey"),
                )
            return False

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=None)
        mock_cm.__aexit__ = AsyncMock(side_effect=aexit_side_effect)
        mock_session.begin_nested = MagicMock(return_value=mock_cm)
        mock_session.commit = AsyncMock()

        # Mock _process_schedule_item to return "new" for both items
        with patch.object(
            schedule_collector,
            "_process_schedule_item",
            return_value="new",
        ):
            schedule_data = [
                {
                    "STATION_2CHAR": "TR",
                    "STATIONNAME": "Trenton",
                    "ITEMS": [
                        {
                            "TRAIN_ID": "3737",
                            "SCHED_DEP_DATE": "01-Jan-2025 10:00:00 AM",
                            "DESTINATION": "New York Penn Station",
                            "LINE": "NEC",
                        },
                        {
                            "TRAIN_ID": "5126",
                            "SCHED_DEP_DATE": "01-Jan-2025 10:30:00 AM",
                            "DESTINATION": "Princeton Junction",
                            "LINE": "NEC",
                        },
                    ],
                }
            ]

            stats = await schedule_collector._process_schedule_data(
                mock_session, schedule_data
            )

        # First item hit IntegrityError (skip), second succeeded
        assert stats["skipped_observed"] == 1
        assert stats["new_schedules"] == 1
        assert stats["errors"] == 0
