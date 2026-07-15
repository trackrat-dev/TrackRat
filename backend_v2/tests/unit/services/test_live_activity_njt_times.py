"""
Unit tests for Live Activity content-state NJT time semantics (issue #1504).

At NJT intermediate stops the raw JourneyStop.updated_departure is the
immutable schedule (DEP_TIME passthrough) while the live delayed estimate is
in updated_arrival (TIME). _calculate_live_activity_content_state read
updated_departure directly, so a rider boarding at an intermediate stop
(Newark Penn, Secaucus — the common case) got the schedule pushed to their
lock screen: a 20-minute-late train rendered as on time.

Compounding it, has_train_departed flipped to true when wall-clock passed
the raw *scheduled* departure, so the same late train also showed
"departed" while physically still at the platform.

The fix routes the origin-stop times through the canonical
effective_njt_updated_times helper (the boarding stop is never the journey
terminal in this context — the rider boards to travel onward) and bases the
departed inference on the delay-aware estimate. has_departed_station stays
authoritative when set.
"""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

from trackrat.models.database import JourneyStop, LiveActivityToken, TrainJourney
from trackrat.services.scheduler import SchedulerService
from trackrat.settings import Settings
from trackrat.utils.time import now_et


@pytest.fixture
def scheduler_service():
    settings = Settings(
        njt_api_token="test_token",
        environment="testing",
    )
    with patch("trackrat.services.scheduler.NJTransitClient"):
        return SchedulerService(settings=settings, apns_service=AsyncMock())


def _njt_journey_with_boarding_stop(
    scheduled_departure,
    live_estimate,
    has_departed_station=False,
    data_source="NJT",
):
    """Journey where the user boards at intermediate stop NP.

    NP carries NJT's raw inverted fields: updated_departure = schedule,
    updated_arrival = live delayed estimate.
    """
    journey = TrainJourney(
        train_id="3855",
        journey_date=now_et().date(),
        line_code="NE",
        line_name="Northeast Corridor",
        destination="Trenton",
        origin_station_code="NY",
        terminal_station_code="TR",
        data_source=data_source,
        observation_type="OBSERVED",
        scheduled_departure=scheduled_departure - timedelta(minutes=18),
        has_complete_journey=True,
        is_cancelled=False,
        is_completed=False,
    )
    journey.stops = [
        JourneyStop(
            station_code="NY",
            station_name="New York Penn Station",
            stop_sequence=0,
            scheduled_departure=scheduled_departure - timedelta(minutes=18),
            has_departed_station=True,
        ),
        JourneyStop(
            station_code="NP",
            station_name="Newark Penn Station",
            stop_sequence=1,
            scheduled_departure=scheduled_departure,
            # NJT raw semantics at intermediate stops:
            updated_departure=scheduled_departure,  # DEP_TIME = schedule
            updated_arrival=live_estimate,  # TIME = live estimate
            has_departed_station=has_departed_station,
        ),
        JourneyStop(
            station_code="TR",
            station_name="Trenton",
            stop_sequence=5,
            scheduled_arrival=scheduled_departure + timedelta(minutes=45),
            updated_arrival=live_estimate + timedelta(minutes=45),
            has_departed_station=False,
        ),
    ]
    return journey


def _token():
    return LiveActivityToken(
        push_token="test-push-token",
        activity_id="test-activity",
        train_number="3855",
        origin_code="NP",
        destination_code="TR",
        is_active=True,
    )


class TestLiveActivityNjtTimes:
    def test_delayed_njt_departure_pushes_live_estimate_not_schedule(
        self, scheduler_service
    ):
        """The pushed departure time must be the live delayed estimate
        (updated_arrival at an NJT intermediate stop), not the schedule
        sitting in updated_departure.
        """
        scheduled = (now_et() + timedelta(minutes=10)).replace(microsecond=0)
        live = scheduled + timedelta(minutes=20)

        journey = _njt_journey_with_boarding_stop(scheduled, live)
        state = scheduler_service._calculate_live_activity_content_state(
            journey, _token(), None
        )

        assert state["scheduledDepartureTime"] == live.isoformat(), (
            "Lock screen must show the delay-aware estimate; the raw "
            "updated_departure is NJT's immutable schedule (issue #1504)"
        )

    def test_delayed_train_past_schedule_not_marked_departed(self, scheduler_service):
        """A late train whose *scheduled* time has passed but whose live
        estimate is in the future must NOT be flagged departed. Before the
        fix, wall-clock passing the schedule flipped hasTrainDeparted, so a
        20-min-late train showed 'departed on time' while still boarding.
        """
        scheduled = (now_et() - timedelta(minutes=5)).replace(microsecond=0)
        live = now_et() + timedelta(minutes=15)

        journey = _njt_journey_with_boarding_stop(scheduled, live)
        state = scheduler_service._calculate_live_activity_content_state(
            journey, _token(), None
        )

        assert state["hasTrainDeparted"] is False, (
            "Departure inference must use the delay-aware estimate, not the "
            "raw schedule"
        )
        assert state["scheduledDepartureTime"] == live.isoformat()
        assert state["status"] == "NOT_DEPARTED"

    def test_has_departed_station_remains_authoritative(self, scheduler_service):
        """An explicit DEPARTED=YES flag wins regardless of estimates."""
        scheduled = (now_et() + timedelta(minutes=10)).replace(microsecond=0)
        live = scheduled + timedelta(minutes=20)

        journey = _njt_journey_with_boarding_stop(
            scheduled, live, has_departed_station=True
        )
        state = scheduler_service._calculate_live_activity_content_state(
            journey, _token(), None
        )

        assert state["hasTrainDeparted"] is True

    def test_departed_inferred_when_live_estimate_passed(self, scheduler_service):
        """When the delay-aware estimate itself has passed (and no explicit
        flag arrived), departure is still inferred — the pre-existing
        inference is preserved, just on the better estimate.
        """
        scheduled = (now_et() - timedelta(minutes=30)).replace(microsecond=0)
        live = now_et() - timedelta(minutes=2)

        journey = _njt_journey_with_boarding_stop(scheduled, live)
        state = scheduler_service._calculate_live_activity_content_state(
            journey, _token(), None
        )

        assert state["hasTrainDeparted"] is True

    def test_non_njt_provider_times_pass_through_raw(self, scheduler_service):
        """For non-NJT providers both updated_* fields are genuine live
        estimates; the departure slot must pass through unmodified (no NJT
        max() applied).
        """
        scheduled = (now_et() + timedelta(minutes=10)).replace(microsecond=0)
        live_departure = scheduled + timedelta(minutes=3)

        journey = _njt_journey_with_boarding_stop(
            scheduled,
            # For LIRR this field is a real arrival estimate; make it LATER
            # than the departure estimate to prove no max() is applied.
            live_departure + timedelta(minutes=6),
            data_source="LIRR",
        )
        # Overwrite NP's updated_departure with the live departure estimate
        journey.stops[1].updated_departure = live_departure

        state = scheduler_service._calculate_live_activity_content_state(
            journey, _token(), None
        )

        assert state["scheduledDepartureTime"] == live_departure.isoformat(), (
            "Non-NJT providers must keep their genuine updated_departure "
            "estimate untouched"
        )
