"""
Tests for journey_date validation to prevent data corruption.

Triggered by production incident where NJT date parsing produced
journey_date=3025-06-22 (year 3025) and 4 rows in December 2026.
The root cause is dateutil.parser.parse accepting malformed date strings
from the NJT API without error.

Tests cover:
- validate_journey_date() boundary conditions
- NJT discovery collector rejecting invalid dates
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trackrat.utils.time import (
    MAX_FUTURE_DAYS,
    MIN_VALID_DATE,
    now_et,
    validate_journey_date,
)


class TestValidateJourneyDate:
    """Tests for the validate_journey_date utility function."""

    def test_today_is_valid(self):
        """Today's date should always be valid."""
        today = now_et().date()
        assert validate_journey_date(today) is True

    def test_yesterday_is_valid(self):
        """Yesterday should be valid."""
        yesterday = now_et().date() - timedelta(days=1)
        assert validate_journey_date(yesterday) is True

    def test_30_days_in_future_is_valid(self):
        """30 days in the future should be valid (within 60-day window)."""
        future = now_et().date() + timedelta(days=30)
        assert validate_journey_date(future) is True

    def test_60_days_in_future_is_valid(self):
        """Exactly MAX_FUTURE_DAYS in the future should be valid (boundary)."""
        future = now_et().date() + timedelta(days=MAX_FUTURE_DAYS)
        assert validate_journey_date(future) is True

    def test_61_days_in_future_is_invalid(self):
        """One day beyond MAX_FUTURE_DAYS should be rejected."""
        future = now_et().date() + timedelta(days=MAX_FUTURE_DAYS + 1)
        assert validate_journey_date(future) is False

    def test_year_3025_is_invalid(self):
        """The exact production corruption case: year 3025."""
        assert validate_journey_date(date(3025, 6, 22)) is False

    def test_december_2026_from_april_2026_is_invalid(self):
        """8 months in the future exceeds 60-day window."""
        assert validate_journey_date(date(2026, 12, 1)) is False

    def test_min_valid_date_is_valid(self):
        """The minimum valid date boundary should pass."""
        assert validate_journey_date(MIN_VALID_DATE) is True

    def test_day_before_min_valid_date_is_invalid(self):
        """One day before MIN_VALID_DATE should be rejected."""
        assert validate_journey_date(MIN_VALID_DATE - timedelta(days=1)) is False

    def test_year_2019_is_invalid(self):
        """Any date before 2020 should be rejected."""
        assert validate_journey_date(date(2019, 12, 31)) is False

    def test_year_1970_is_invalid(self):
        """Unix epoch date should be rejected."""
        assert validate_journey_date(date(1970, 1, 1)) is False

    def test_historical_valid_date(self):
        """A date from 2023 (past but after MIN_VALID_DATE) should be valid."""
        assert validate_journey_date(date(2023, 6, 15)) is True


class TestDiscoveryDateValidation:
    """Tests that the NJT discovery collector rejects invalid dates."""

    @pytest.mark.asyncio
    async def test_discovery_skips_far_future_date(self):
        """Discovery collector should skip trains with far-future journey dates."""
        from trackrat.collectors.njt.discovery import TrainDiscoveryCollector

        mock_client = MagicMock()
        collector = TrainDiscoveryCollector(njt_client=mock_client)

        mock_session = AsyncMock()
        mock_session.bind = MagicMock()
        mock_session.bind.dialect.name = "postgresql"

        trains_data = [
            {
                "TRAIN_ID": "9999",
                "SCHED_DEP_DATE": "22-Jun-3025 10:00:00 AM",
                "LINE": "NEC",
                "LINE_NAME": "Northeast Corridor",
                "DESTINATION": "Trenton",
                "TRACK": "5",
            },
        ]

        new_train_ids = await collector.process_discovered_trains(
            mock_session, "NY", trains_data
        )

        assert "9999" not in new_train_ids
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_discovery_accepts_valid_date(self):
        """Discovery collector should process trains with valid dates."""
        from trackrat.collectors.njt.discovery import TrainDiscoveryCollector

        mock_client = MagicMock()
        collector = TrainDiscoveryCollector(njt_client=mock_client)

        today = now_et()
        today_str = today.strftime("%d-%b-%Y %I:%M:%S %p")

        mock_session = AsyncMock()
        mock_session.bind = MagicMock()
        mock_session.bind.dialect.name = "postgresql"

        mock_result = AsyncMock()
        mock_result.scalar = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.scalar = AsyncMock(return_value=None)
        mock_session.begin_nested = MagicMock()

        trains_data = [
            {
                "TRAIN_ID": "1234",
                "SCHED_DEP_DATE": today_str,
                "LINE": "NEC",
                "LINE_NAME": "Northeast Corridor",
                "DESTINATION": "Trenton",
                "TRACK": "5",
                "STOPS": [],
            },
        ]

        # The train has a valid date so it should get past the validation.
        # It may still fail on DB operations (mocked), but the important
        # thing is it wasn't rejected by the date validation.
        with patch(
            "trackrat.collectors.njt.discovery.is_amtrak_train", return_value=False
        ):
            # We expect the code to attempt DB operations for valid dates.
            # It will enter the savepoint context and try to query/insert.
            # The exact outcome depends on mock setup, but the key assertion
            # is that the code progressed past the date validation.
            try:
                await collector.process_discovered_trains(
                    mock_session, "NY", trains_data
                )
            except (AttributeError, TypeError):
                # Expected: mocks may not fully support async context managers
                pass

        # Verify parse_njt_time was called (date was valid, so code proceeded)
        # We can verify by checking the mock_session was used (begin_nested called)
        # If date was invalid, begin_nested would never be called
        assert mock_session.begin_nested.called or mock_session.scalar.called
