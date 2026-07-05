"""
Regression tests for issue #1422: hide_departed hiding upcoming terminal-origin trains.

For subway routes whose origin is a terminal (e.g. S101 Van Cortlandt Park-242 St
on the 1), the origin JourneyStop can carry ``has_departed_station=True`` while its
departure is still in the future. The flag is set monotonically (never reset), so a
train dwelling at its origin terminal keeps it even after the feed revises the
departure forward. The ``hide_departed`` filter used to drop such trains outright,
producing an empty departures board (0 upcoming trains) for the iOS app even though
trains were scheduled minutes away.

These tests exercise the real SQL WHERE clause against a live database:
1. A future-departure origin with the stale flag set MUST still be returned.
2. A train that actually left the origin early (actual_departure in the past) MUST
   stay hidden, proving the fix keys off the effective departure, not just the flag.
"""

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.departure import DepartureService
from trackrat.utils.time import now_et


def _make_subway_journey(
    train_id: str,
    origin_scheduled_departure,
    origin_actual_departure,
    origin_has_departed: bool,
    terminal_arrival,
) -> TrainJourney:
    """Build a minimal S101 -> S142 SUBWAY journey with an origin-terminal stop.

    Only the origin (S101) and terminal (S142) stops are needed to exercise the
    departures query; the real journey has 27 stops but the filter and response
    building only touch the from-stop and to-stop.
    """
    now = now_et()
    journey = TrainJourney(
        train_id=train_id,
        journey_date=now.date(),
        data_source="SUBWAY",
        observation_type="OBSERVED",
        line_code="1",
        line_name="1",
        line_color="#EE352E",
        destination="South Ferry",
        origin_station_code="S101",
        terminal_station_code="S142",
        scheduled_departure=origin_scheduled_departure,
        first_seen_at=now,
        last_updated_at=now,
        has_complete_journey=True,
        stops_count=2,
        is_cancelled=False,
        is_completed=False,
        is_expired=False,
        update_count=3,
    )

    origin_stop = JourneyStop(
        station_code="S101",
        station_name="Van Cortlandt Park-242 St",
        stop_sequence=1,
        scheduled_departure=origin_scheduled_departure,
        scheduled_arrival=origin_scheduled_departure,
        updated_departure=origin_actual_departure,
        updated_arrival=origin_actual_departure,
        actual_departure=origin_actual_departure,
        actual_arrival=origin_actual_departure,
        track=None,
        has_departed_station=origin_has_departed,
    )
    terminal_stop = JourneyStop(
        station_code="S142",
        station_name="South Ferry",
        stop_sequence=2,
        scheduled_arrival=terminal_arrival,
        scheduled_departure=terminal_arrival,
        updated_arrival=terminal_arrival,
        updated_departure=terminal_arrival,
        actual_arrival=None,
        actual_departure=None,
        track=None,
        has_departed_station=False,
    )
    journey.stops = [origin_stop, terminal_stop]
    return journey


@pytest.mark.asyncio
class TestHideDepartedTerminalOrigin:
    """Terminal-origin trains with a stale has_departed_station flag (issue #1422)."""

    async def test_future_departure_origin_shown_despite_departed_flag(
        self, db_session: AsyncSession
    ):
        """A future S101 departure must appear under hide_departed even if flagged departed.

        This is the exact bug: origin scheduled/actual departure is 3 minutes in the
        future but has_departed_station=True. Before the fix the hide_departed filter
        dropped it, leaving the iOS board empty.
        """
        now = now_et()
        future_departure = now + timedelta(minutes=3)

        journey = _make_subway_journey(
            train_id="S1-FUTURE-ORIGIN",
            origin_scheduled_departure=future_departure,
            origin_actual_departure=future_departure,  # == scheduled, still in the future
            origin_has_departed=True,  # stale latched flag — the bug trigger
            terminal_arrival=now + timedelta(minutes=45),
        )
        db_session.add(journey)
        await db_session.commit()

        service = DepartureService()
        response = await service.get_departures(
            db=db_session,
            from_station="S101",
            to_station="S142",
            time_from=now,
            time_to=now + timedelta(hours=3),
            hide_departed=True,
            data_sources=["SUBWAY"],
        )

        train_ids = {d.train_id for d in response.departures}
        assert "S1-FUTURE-ORIGIN" in train_ids, (
            "Terminal-origin train departing in 3 minutes was hidden by hide_departed "
            "despite a future departure — this is the #1422 regression. "
            f"Returned train_ids: {train_ids}"
        )

    async def test_early_departed_origin_stays_hidden(self, db_session: AsyncSession):
        """A train that already left the origin must stay hidden under hide_departed.

        Guards against the fix over-showing: the origin's scheduled departure is still
        in the future (within the query window) but its actual_departure is in the past
        and the flag is set. The effective departure (actual, preferred over scheduled)
        is past, so the train should not appear on the board.
        """
        now = now_et()

        journey = _make_subway_journey(
            train_id="S1-LEFT-EARLY",
            origin_scheduled_departure=now + timedelta(minutes=3),  # future, in window
            origin_actual_departure=now - timedelta(minutes=3),  # actually left already
            origin_has_departed=True,
            terminal_arrival=now + timedelta(minutes=45),
        )
        db_session.add(journey)
        await db_session.commit()

        service = DepartureService()
        response = await service.get_departures(
            db=db_session,
            from_station="S101",
            to_station="S142",
            time_from=now,
            time_to=now + timedelta(hours=3),
            hide_departed=True,
            data_sources=["SUBWAY"],
        )

        train_ids = {d.train_id for d in response.departures}
        assert "S1-LEFT-EARLY" not in train_ids, (
            "Train that already departed the origin (actual_departure in the past) "
            "must stay hidden under hide_departed. "
            f"Returned train_ids: {train_ids}"
        )
