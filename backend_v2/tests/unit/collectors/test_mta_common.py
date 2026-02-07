"""Tests for MTA common utilities (departure inference, journey metadata, completion)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from trackrat.collectors.mta_common import (
    check_journey_completed,
    update_journey_metadata,
    update_stop_departure_status,
)
from trackrat.models.database import JourneyStop, TrainJourney


def _make_stop(
    station_code: str,
    stop_sequence: int,
    scheduled_arrival: datetime,
    actual_departure: datetime | None = None,
    actual_arrival: datetime | None = None,
    has_departed_station: bool = False,
    departure_source: str | None = None,
) -> MagicMock:
    """Create a mock JourneyStop with all required fields."""
    stop = MagicMock(spec=JourneyStop)
    stop.station_code = station_code
    stop.stop_sequence = stop_sequence
    stop.scheduled_arrival = scheduled_arrival
    stop.actual_departure = actual_departure
    stop.actual_arrival = actual_arrival
    stop.has_departed_station = has_departed_station
    stop.departure_source = departure_source
    return stop


class TestUpdateStopDepartureStatus:
    """Tests for update_stop_departure_status()."""

    def test_stop_with_actual_departure_in_past_is_marked_departed(self):
        """Path A: stop has actual_departure in the past -> departed."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=10)

        stop = _make_stop("GCT", 1, past, actual_departure=past)
        update_stop_departure_status([stop], now)

        assert stop.has_departed_station is True
        assert stop.departure_source == "time_inference"

    def test_stop_with_actual_arrival_in_past_is_marked_departed(self):
        """Path A fallback: stop has actual_arrival (no departure) in the past."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=10)

        stop = _make_stop("GCT", 1, past, actual_arrival=past)
        update_stop_departure_status([stop], now)

        assert stop.has_departed_station is True

    def test_stop_with_actual_departure_in_future_is_not_departed(self):
        """Path A: stop with actual_departure in the future is not departed."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(minutes=30)

        stop = _make_stop("GCT", 1, future, actual_departure=future)
        update_stop_departure_status([stop], now)

        assert stop.has_departed_station is False

    def test_stop_with_scheduled_time_past_grace_period_is_departed(self):
        """Path B: no actuals, scheduled time + 2min grace < now -> departed."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=10)

        stop = _make_stop("GCT", 1, scheduled_arrival=past)
        update_stop_departure_status([stop], now)

        assert stop.has_departed_station is True
        assert stop.departure_source == "time_inference"

    def test_stop_with_scheduled_time_within_grace_period_is_not_departed(self):
        """Path B: scheduled time + grace < now is false -> not departed."""
        now = datetime.now(timezone.utc)
        recent = now - timedelta(seconds=30)

        stop = _make_stop("GCT", 1, scheduled_arrival=recent)
        update_stop_departure_status([stop], now)

        assert stop.has_departed_station is False

    def test_sequential_consistency_fills_earlier_stops(self):
        """Path C: if stop 3 is departed, stops 1 and 2 must be too."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=30)

        stop1 = _make_stop("A", 1, scheduled_arrival=past)
        stop2 = _make_stop("B", 2, scheduled_arrival=past)
        stop3 = _make_stop("C", 3, scheduled_arrival=past, actual_departure=past)

        # Stop 3 has actual_departure in the past, but stops 1 and 2 have no actuals.
        # However, stops 1 and 2 also have scheduled_arrival in the past,
        # so Path B should mark them as departed directly.
        # For a purer test, set scheduled_arrival in the future for stops 1 and 2.
        stop1.scheduled_arrival = now + timedelta(minutes=10)
        stop1.actual_departure = None
        stop1.actual_arrival = None
        stop2.scheduled_arrival = now + timedelta(minutes=10)
        stop2.actual_departure = None
        stop2.actual_arrival = None

        update_stop_departure_status([stop1, stop2, stop3], now)

        assert stop3.has_departed_station is True  # Path A
        assert stop1.has_departed_station is True  # Path C (sequential consistency)
        assert stop2.has_departed_station is True  # Path C (sequential consistency)
        assert stop1.departure_source == "sequential_consistency"
        assert stop2.departure_source == "sequential_consistency"

    def test_sequential_consistency_sets_actual_times_from_schedule(self):
        """Path C: sequential fill uses scheduled_arrival for missing actual times."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=30)
        scheduled = now - timedelta(minutes=20)

        stop1 = _make_stop("A", 1, scheduled_arrival=scheduled)
        stop1.actual_departure = None
        stop1.actual_arrival = None
        stop1.scheduled_arrival = now + timedelta(
            minutes=10
        )  # Future, so Path B won't trigger

        stop2 = _make_stop("B", 2, scheduled_arrival=past, actual_departure=past)

        update_stop_departure_status([stop1, stop2], now)

        assert stop1.has_departed_station is True
        assert stop1.actual_departure == stop1.scheduled_arrival
        assert stop1.actual_arrival == stop1.scheduled_arrival

    def test_empty_stops_list_does_not_raise(self):
        """Empty list should be handled gracefully."""
        now = datetime.now(timezone.utc)
        update_stop_departure_status([], now)  # Should not raise

    def test_stops_without_stop_sequence_are_handled(self):
        """Stops with stop_sequence=None should not break the function."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=10)

        stop = _make_stop("GCT", 1, past, actual_departure=past)
        stop.stop_sequence = None

        update_stop_departure_status([stop], now)

        assert stop.has_departed_station is True

    def test_preserves_existing_departure_source(self):
        """Should not overwrite departure_source if already set."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=10)

        stop = _make_stop("GCT", 1, past, actual_departure=past)
        stop.departure_source = "api_explicit"

        update_stop_departure_status([stop], now)

        assert stop.has_departed_station is True
        assert stop.departure_source == "api_explicit"

    def test_multi_stop_journey_realistic(self):
        """Realistic MNR journey: GCT -> 125th -> Croton with mixed states."""
        now = datetime.now(timezone.utc)

        stop_gct = _make_stop(
            "GCT",
            1,
            scheduled_arrival=now - timedelta(minutes=60),
            actual_departure=now - timedelta(minutes=58),
        )
        stop_125 = _make_stop(
            "M125",
            2,
            scheduled_arrival=now - timedelta(minutes=50),
            actual_arrival=now - timedelta(minutes=48),
        )
        stop_croton = _make_stop(
            "MCRH",
            3,
            scheduled_arrival=now + timedelta(minutes=20),
        )

        update_stop_departure_status([stop_gct, stop_125, stop_croton], now)

        assert stop_gct.has_departed_station is True  # Path A: actual_departure in past
        assert stop_125.has_departed_station is True  # Path A: actual_arrival in past
        assert stop_croton.has_departed_station is False  # Future scheduled, no actuals


class TestUpdateJourneyMetadata:
    """Tests for update_journey_metadata()."""

    def test_sets_last_updated_at(self):
        """Should set last_updated_at to now."""
        now = datetime.now(timezone.utc)
        journey = MagicMock(spec=TrainJourney)
        journey.update_count = 0

        update_journey_metadata(journey, now)

        assert journey.last_updated_at == now

    def test_increments_update_count(self):
        """Should increment update_count."""
        now = datetime.now(timezone.utc)
        journey = MagicMock(spec=TrainJourney)
        journey.update_count = 5

        update_journey_metadata(journey, now)

        assert journey.update_count == 6

    def test_initializes_update_count_from_none(self):
        """Should handle None update_count (first update)."""
        now = datetime.now(timezone.utc)
        journey = MagicMock(spec=TrainJourney)
        journey.update_count = None

        update_journey_metadata(journey, now)

        assert journey.update_count == 1


class TestCheckJourneyCompleted:
    """Tests for check_journey_completed()."""

    def test_marks_completed_when_terminal_stop_departed(self):
        """Journey is completed when terminal stop has departed."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=10)

        journey = MagicMock(spec=TrainJourney)
        journey.is_completed = False

        stop1 = _make_stop("GCT", 1, past, actual_departure=past)
        stop1.has_departed_station = True
        stop2 = _make_stop("MPOK", 2, past, actual_arrival=past)
        stop2.has_departed_station = True

        check_journey_completed(journey, [stop1, stop2])

        assert journey.is_completed is True
        assert journey.actual_arrival == past

    def test_not_completed_when_terminal_stop_not_departed(self):
        """Journey is not completed when terminal stop hasn't departed."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=10)
        future = now + timedelta(minutes=20)

        journey = MagicMock(spec=TrainJourney)
        journey.is_completed = False

        stop1 = _make_stop("GCT", 1, past)
        stop1.has_departed_station = True
        stop2 = _make_stop("MPOK", 2, future)
        stop2.has_departed_station = False

        check_journey_completed(journey, [stop1, stop2])

        assert journey.is_completed is False

    def test_empty_stops_does_not_raise(self):
        """Empty stops list should be handled gracefully."""
        journey = MagicMock(spec=TrainJourney)
        journey.is_completed = False

        check_journey_completed(journey, [])

        assert journey.is_completed is False

    def test_does_not_revert_completed_journey(self):
        """Should not change is_completed if already True."""
        now = datetime.now(timezone.utc)

        journey = MagicMock(spec=TrainJourney)
        journey.is_completed = True

        stop = _make_stop("GCT", 1, now)
        stop.has_departed_station = False

        check_journey_completed(journey, [stop])

        # Should still be True (not reverted)
        assert journey.is_completed is True

    def test_uses_scheduled_arrival_as_fallback(self):
        """Should use scheduled_arrival when actual_arrival is None."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=10)

        journey = MagicMock(spec=TrainJourney)
        journey.is_completed = False

        stop = _make_stop("MPOK", 1, scheduled_arrival=past)
        stop.has_departed_station = True
        stop.actual_arrival = None

        check_journey_completed(journey, [stop])

        assert journey.is_completed is True
        assert journey.actual_arrival == past

    def test_finds_terminal_by_max_stop_sequence(self):
        """Terminal stop is the one with highest stop_sequence, not last in list."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=10)

        journey = MagicMock(spec=TrainJourney)
        journey.is_completed = False

        # Stops out of order in list
        stop_terminal = _make_stop("MPOK", 5, past, actual_arrival=past)
        stop_terminal.has_departed_station = True
        stop_mid = _make_stop("MCRH", 3, past)
        stop_mid.has_departed_station = True

        check_journey_completed(journey, [stop_mid, stop_terminal])

        assert journey.is_completed is True
