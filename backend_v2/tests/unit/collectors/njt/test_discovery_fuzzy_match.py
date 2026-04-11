"""
Unit tests for NJT discovery fuzzy matching.

Tests the fallback matching logic that connects scheduled trains with
real-time trains when NJT uses different train numbers.
"""

import pytest
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, Mock, MagicMock, patch

from trackrat.collectors.njt.discovery import TrainDiscoveryCollector
from trackrat.models.database import TrainJourney, JourneyStop
from trackrat.utils.time import ET


@asynccontextmanager
async def _mock_savepoint():
    """Mock async context manager for session.begin_nested()."""
    yield


def _make_session_mock():
    """Create an AsyncMock session that supports begin_nested() as async CM."""
    mock_session = AsyncMock()
    mock_session.add = Mock()
    mock_session.begin_nested = lambda: _mock_savepoint()
    return mock_session


def _make_scheduled_journey(
    train_id: str,
    destination: str,
    scheduled_departure: datetime,
    journey_date: date | None = None,
) -> TrainJourney:
    """Create a mock SCHEDULED TrainJourney for testing."""
    journey = Mock(spec=TrainJourney)
    journey.id = 100
    journey.train_id = train_id
    journey.destination = destination
    journey.scheduled_departure = scheduled_departure
    journey.journey_date = journey_date or scheduled_departure.date()
    journey.data_source = "NJT"
    journey.observation_type = "SCHEDULED"
    journey.is_cancelled = False
    journey.is_expired = False
    journey.last_updated_at = None
    return journey


class TestFuzzyMatchScheduledTrain:
    """Tests for _find_matching_scheduled_train and its integration."""

    @pytest.fixture
    def collector(self):
        """Create discovery collector with mocked client."""
        client = AsyncMock()
        return TrainDiscoveryCollector(client)

    @pytest.mark.asyncio
    async def test_fuzzy_match_upgrades_scheduled_train(self, collector):
        """When a real-time train matches a SCHEDULED train by destination and time,
        the SCHEDULED record should be updated with the new train_id and promoted
        to OBSERVED. No new record should be created.

        Scenario: Schedule has train 3237 to Hamilton departing NY Penn at 10:15.
        Real-time shows train 3965 to Hamilton departing NY Penn at 10:15.
        """
        mock_session = _make_session_mock()

        dep_time = datetime(2025, 7, 5, 10, 15, 0)
        scheduled_journey = _make_scheduled_journey(
            train_id="3237",
            destination="Hamilton",
            scheduled_departure=dep_time,
        )

        # session.scalar calls in order:
        # 1. Exact match by train_id "3965" → None (no existing record)
        # 2. Row exists check for "3965" → False (not locked)
        # 3. Fuzzy match query → the SCHEDULED journey
        mock_session.scalar = AsyncMock(side_effect=[None, False, scheduled_journey])

        train_data = [
            {
                "TRAIN_ID": "3965",
                "LINE": "NEC",
                "LINE_NAME": "Northeast Corridor",
                "DESTINATION": "Hamilton",
                "SCHED_DEP_DATE": "05-Jul-2025 10:15:00 AM",
                "BACKCOLOR": "#FF6600",
            }
        ]

        with patch(
            "trackrat.collectors.njt.discovery.parse_njt_time"
        ) as mock_parse_time:
            mock_parse_time.return_value = dep_time

            with patch("trackrat.collectors.njt.discovery.now_et") as mock_now:
                mock_now.return_value = datetime(2025, 7, 5, 9, 0, 0)

                result = await collector.process_discovered_trains(
                    mock_session, "NY", train_data
                )

        # Should NOT create a new record (empty set = no new train IDs)
        assert result == set()

        # The SCHEDULED journey should have been updated
        assert scheduled_journey.train_id == "3965"
        assert scheduled_journey.observation_type == "OBSERVED"
        assert scheduled_journey.last_updated_at is not None

        # session.add should NOT have been called (no new journey created)
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_fuzzy_match_different_destination(self, collector):
        """When destination doesn't match, fuzzy match should not fire.
        A new OBSERVED record should be created instead.

        Scenario: Schedule has train 3237 to Trenton. Real-time shows train 3965
        to Hamilton. Different destinations → no match.
        """
        mock_session = _make_session_mock()

        dep_time = datetime(2025, 7, 5, 10, 15, 0)

        # session.scalar calls:
        # 1. Exact match → None
        # 2. Row exists → False
        # 3. Fuzzy match → None (no match because destination differs)
        mock_session.scalar = AsyncMock(side_effect=[None, False, None])

        train_data = [
            {
                "TRAIN_ID": "3965",
                "LINE": "NEC",
                "LINE_NAME": "Northeast Corridor",
                "DESTINATION": "Hamilton",
                "SCHED_DEP_DATE": "05-Jul-2025 10:15:00 AM",
                "BACKCOLOR": "#FF6600",
            }
        ]

        with patch(
            "trackrat.collectors.njt.discovery.parse_njt_time"
        ) as mock_parse_time:
            mock_parse_time.return_value = dep_time

            with patch("trackrat.collectors.njt.discovery.now_et") as mock_now:
                mock_now.return_value = datetime(2025, 7, 5, 9, 0, 0)

                result = await collector.process_discovered_trains(
                    mock_session, "NY", train_data
                )

        # New record should be created
        assert result == {"3965"}
        assert mock_session.add.call_count == 1

    @pytest.mark.asyncio
    async def test_no_fuzzy_match_time_out_of_tolerance(self, collector):
        """When departure time is outside ±5 min tolerance, no match should occur.

        Scenario: Schedule has train 3237 departing at 10:00. Real-time shows
        train 3965 departing at 10:10. 10 minutes apart > 5 min tolerance.
        """
        mock_session = _make_session_mock()

        dep_time = datetime(2025, 7, 5, 10, 10, 0)

        # All scalar calls return None (no matches at all)
        mock_session.scalar = AsyncMock(side_effect=[None, False, None])

        train_data = [
            {
                "TRAIN_ID": "3965",
                "LINE": "NEC",
                "LINE_NAME": "Northeast Corridor",
                "DESTINATION": "Hamilton",
                "SCHED_DEP_DATE": "05-Jul-2025 10:10:00 AM",
                "BACKCOLOR": "#FF6600",
            }
        ]

        with patch(
            "trackrat.collectors.njt.discovery.parse_njt_time"
        ) as mock_parse_time:
            mock_parse_time.return_value = dep_time

            with patch("trackrat.collectors.njt.discovery.now_et") as mock_now:
                mock_now.return_value = datetime(2025, 7, 5, 9, 0, 0)

                result = await collector.process_discovered_trains(
                    mock_session, "NY", train_data
                )

        # New record should be created (fuzzy match returned None)
        assert result == {"3965"}
        assert mock_session.add.call_count == 1

    @pytest.mark.asyncio
    async def test_exact_match_takes_priority_over_fuzzy(self, collector):
        """When an exact train_id match exists, the fuzzy match should never run.

        Scenario: Existing OBSERVED record for train 3965 already exists.
        Discovery finds train 3965 again. Exact match handles it; fuzzy never called.
        """
        mock_session = _make_session_mock()

        dep_time = datetime(2025, 7, 5, 10, 15, 0)
        existing_journey = Mock(spec=TrainJourney)
        existing_journey.train_id = "3965"
        existing_journey.observation_type = "OBSERVED"
        existing_journey.is_expired = False
        existing_journey.last_updated_at = None

        # session.scalar calls:
        # 1. Exact match → existing journey (found!)
        # No further calls needed
        mock_session.scalar = AsyncMock(return_value=existing_journey)

        train_data = [
            {
                "TRAIN_ID": "3965",
                "LINE": "NEC",
                "DESTINATION": "Hamilton",
                "SCHED_DEP_DATE": "05-Jul-2025 10:15:00 AM",
            }
        ]

        with patch(
            "trackrat.collectors.njt.discovery.parse_njt_time"
        ) as mock_parse_time:
            mock_parse_time.return_value = dep_time

            with patch("trackrat.collectors.njt.discovery.now_et") as mock_now:
                mock_now.return_value = datetime(2025, 7, 5, 9, 0, 0)

                result = await collector.process_discovered_trains(
                    mock_session, "NY", train_data
                )

        # No new records created
        assert result == set()
        mock_session.add.assert_not_called()

        # Existing journey was matched (observation_type unchanged)
        assert existing_journey.observation_type == "OBSERVED"

    @pytest.mark.asyncio
    async def test_already_observed_not_matched(self, collector):
        """Fuzzy match should only match SCHEDULED trains, not OBSERVED.

        The WHERE clause in _find_matching_scheduled_train requires
        observation_type == 'SCHEDULED'. OBSERVED trains are excluded.
        """
        mock_session = _make_session_mock()

        dep_time = datetime(2025, 7, 5, 10, 15, 0)

        # session.scalar calls:
        # 1. Exact match → None
        # 2. Row exists → False
        # 3. Fuzzy match → None (only SCHEDULED trains are candidates)
        mock_session.scalar = AsyncMock(side_effect=[None, False, None])

        train_data = [
            {
                "TRAIN_ID": "3965",
                "LINE": "NEC",
                "DESTINATION": "Hamilton",
                "SCHED_DEP_DATE": "05-Jul-2025 10:15:00 AM",
            }
        ]

        with patch(
            "trackrat.collectors.njt.discovery.parse_njt_time"
        ) as mock_parse_time:
            mock_parse_time.return_value = dep_time

            with patch("trackrat.collectors.njt.discovery.now_et") as mock_now:
                mock_now.return_value = datetime(2025, 7, 5, 9, 0, 0)

                result = await collector.process_discovered_trains(
                    mock_session, "NY", train_data
                )

        # New record created because no SCHEDULED match found
        assert result == {"3965"}
        assert mock_session.add.call_count == 1

    @pytest.mark.asyncio
    async def test_fuzzy_match_empty_destination_skips_query(self, collector):
        """When the real-time train has an empty destination, fuzzy match
        should be skipped entirely to avoid nonsensical matches.
        """
        mock_session = _make_session_mock()

        dep_time = datetime(2025, 7, 5, 10, 15, 0)

        # session.scalar calls:
        # 1. Exact match → None
        # 2. Row exists → False
        # No fuzzy match call (skipped due to empty destination)
        mock_session.scalar = AsyncMock(side_effect=[None, False])

        train_data = [
            {
                "TRAIN_ID": "3965",
                "LINE": "NEC",
                "DESTINATION": "",  # Empty destination
                "SCHED_DEP_DATE": "05-Jul-2025 10:15:00 AM",
            }
        ]

        with patch(
            "trackrat.collectors.njt.discovery.parse_njt_time"
        ) as mock_parse_time:
            mock_parse_time.return_value = dep_time

            with patch("trackrat.collectors.njt.discovery.now_et") as mock_now:
                mock_now.return_value = datetime(2025, 7, 5, 9, 0, 0)

                result = await collector.process_discovered_trains(
                    mock_session, "NY", train_data
                )

        # New record created
        assert result == {"3965"}

    @pytest.mark.asyncio
    async def test_fuzzy_match_updates_track(self, collector):
        """When fuzzy match succeeds, the track should be updated on the
        matched journey's stop at the discovery station.
        """
        mock_session = _make_session_mock()

        dep_time = datetime(2025, 7, 5, 10, 15, 0)
        scheduled_journey = _make_scheduled_journey(
            train_id="3237",
            destination="Hamilton",
            scheduled_departure=dep_time,
        )

        # Mock the stop at the discovery station
        existing_stop = Mock(spec=JourneyStop)
        existing_stop.track = None

        # session.scalar calls:
        # 1. Exact match → None
        # 2. Row exists → False
        # 3. Fuzzy match → SCHEDULED journey
        # 4. _update_stop_track_if_needed: find stop → existing_stop
        mock_session.scalar = AsyncMock(
            side_effect=[None, False, scheduled_journey, existing_stop]
        )

        train_data = [
            {
                "TRAIN_ID": "3965",
                "LINE": "NEC",
                "DESTINATION": "Hamilton",
                "SCHED_DEP_DATE": "05-Jul-2025 10:15:00 AM",
                "TRACK": "5",
            }
        ]

        with patch(
            "trackrat.collectors.njt.discovery.parse_njt_time"
        ) as mock_parse_time:
            mock_parse_time.return_value = dep_time

            with patch("trackrat.collectors.njt.discovery.now_et") as mock_now:
                mock_now.return_value = datetime(2025, 7, 5, 9, 0, 0)

                result = await collector.process_discovered_trains(
                    mock_session, "NY", train_data
                )

        # Should match, not create new
        assert result == set()
        assert scheduled_journey.train_id == "3965"
        assert scheduled_journey.observation_type == "OBSERVED"

        # Track should have been updated on the existing stop
        assert existing_stop.track == "5"

    @pytest.mark.asyncio
    async def test_fuzzy_match_with_multiple_trains(self, collector):
        """When processing multiple trains in one batch, fuzzy match should
        work independently for each train.

        Scenario: Two trains discovered. First matches a SCHEDULED record,
        second has no match and creates a new record.
        """
        mock_session = _make_session_mock()

        dep_time_1 = datetime(2025, 7, 5, 10, 15, 0)
        dep_time_2 = datetime(2025, 7, 5, 11, 30, 0)

        scheduled_journey = _make_scheduled_journey(
            train_id="3237",
            destination="Hamilton",
            scheduled_departure=dep_time_1,
        )

        # session.scalar calls for train 1 (3965):
        # 1. Exact match → None
        # 2. Row exists → False
        # 3. Fuzzy match → SCHEDULED journey
        # session.scalar calls for train 2 (4100):
        # 4. Exact match → None
        # 5. Row exists → False
        # 6. Fuzzy match → None (no match)
        mock_session.scalar = AsyncMock(
            side_effect=[
                None,
                False,
                scheduled_journey,  # Train 3965: fuzzy match
                None,
                False,
                None,  # Train 4100: no match
            ]
        )

        train_data = [
            {
                "TRAIN_ID": "3965",
                "LINE": "NEC",
                "DESTINATION": "Hamilton",
                "SCHED_DEP_DATE": "05-Jul-2025 10:15:00 AM",
            },
            {
                "TRAIN_ID": "4100",
                "LINE": "NEC",
                "DESTINATION": "Trenton",
                "SCHED_DEP_DATE": "05-Jul-2025 11:30:00 AM",
            },
        ]

        with patch(
            "trackrat.collectors.njt.discovery.parse_njt_time"
        ) as mock_parse_time:
            mock_parse_time.side_effect = [dep_time_1, dep_time_2]

            with patch("trackrat.collectors.njt.discovery.now_et") as mock_now:
                mock_now.return_value = datetime(2025, 7, 5, 9, 0, 0)

                result = await collector.process_discovered_trains(
                    mock_session, "NY", train_data
                )

        # Only train 4100 should be new (3965 matched existing)
        assert result == {"4100"}
        assert scheduled_journey.train_id == "3965"
        assert scheduled_journey.observation_type == "OBSERVED"

        # session.add called once for the new train 4100
        assert mock_session.add.call_count == 1


class TestFindMatchingScheduledTrainMethod:
    """Direct tests for the _find_matching_scheduled_train method."""

    @pytest.fixture
    def collector(self):
        """Create discovery collector with mocked client."""
        client = AsyncMock()
        return TrainDiscoveryCollector(client)

    @pytest.mark.asyncio
    async def test_returns_none_when_no_candidates(self, collector):
        """When no SCHEDULED trains match, should return None."""
        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=None)

        result = await collector._find_matching_scheduled_train(
            session=mock_session,
            station_code="NY",
            destination="Hamilton",
            scheduled_departure=datetime(2025, 7, 5, 10, 15, 0),
            journey_date=date(2025, 7, 5),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_matching_journey(self, collector):
        """When a matching SCHEDULED train exists, should return it."""
        mock_session = AsyncMock()
        scheduled = _make_scheduled_journey(
            train_id="3237",
            destination="Hamilton",
            scheduled_departure=datetime(2025, 7, 5, 10, 15, 0),
        )
        mock_session.scalar = AsyncMock(return_value=scheduled)

        result = await collector._find_matching_scheduled_train(
            session=mock_session,
            station_code="NY",
            destination="Hamilton",
            scheduled_departure=datetime(2025, 7, 5, 10, 15, 0),
            journey_date=date(2025, 7, 5),
        )

        assert result is scheduled
        assert result.train_id == "3237"

    @pytest.mark.asyncio
    async def test_custom_time_tolerance(self, collector):
        """Should accept a custom time tolerance parameter."""
        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=None)

        # Call with a 10-minute tolerance
        result = await collector._find_matching_scheduled_train(
            session=mock_session,
            station_code="NY",
            destination="Hamilton",
            scheduled_departure=datetime(2025, 7, 5, 10, 15, 0),
            journey_date=date(2025, 7, 5),
            time_tolerance_minutes=10,
        )

        assert result is None

        # Verify the query was executed (scalar was called)
        mock_session.scalar.assert_called_once()
