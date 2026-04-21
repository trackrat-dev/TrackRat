"""
Integration tests for recently-departed trains (DepartureService.get_recent_departures).

The recent-departures endpoint is a sibling to /departures that intentionally
relaxes the filters (no hide_departed cutoff, no is_expired/is_completed
exclusion) so that already-departed, completed, and cancelled trains remain
visible for a short window after they left the origin station.
"""

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.services.departure import DepartureService
from trackrat.utils.time import now_et


def _make_njt_journey(
    *,
    train_id: str,
    scheduled_departure,
    origin: str = "NY",
    destination_code: str = "TR",
    is_cancelled: bool = False,
    is_completed: bool = False,
    is_expired: bool = False,
    has_departed_station: bool = True,
    stop_sequence: int = 0,
) -> TrainJourney:
    """Build an NJT journey with a single origin stop for concise setup."""
    journey = TrainJourney(
        train_id=train_id,
        journey_date=scheduled_departure.date(),
        data_source="NJT",
        line_code="NE",
        line_name="Northeast Corridor",
        line_color="#F7505E",
        destination="Trenton",
        origin_station_code=origin,
        terminal_station_code=destination_code,
        scheduled_departure=scheduled_departure,
        first_seen_at=now_et() - timedelta(hours=1),
        last_updated_at=now_et() - timedelta(minutes=5),
        has_complete_journey=True,
        update_count=1,
        is_cancelled=is_cancelled,
        is_completed=is_completed,
        is_expired=is_expired,
    )
    origin_stop = JourneyStop(
        station_code=origin,
        station_name="New York Penn Station",
        scheduled_departure=scheduled_departure,
        updated_departure=scheduled_departure,
        stop_sequence=stop_sequence,
        track="7",
        has_departed_station=has_departed_station,
        actual_departure=scheduled_departure if has_departed_station else None,
    )
    journey.stops = [origin_stop]
    return journey


@pytest.mark.asyncio
class TestRecentDepartures:
    """DepartureService.get_recent_departures behavioral coverage."""

    async def test_returns_train_that_departed_within_window(
        self, db_session: AsyncSession
    ):
        """A train scheduled 20 min ago with has_departed=True is returned."""
        service = DepartureService()
        twenty_min_ago = now_et() - timedelta(minutes=20)

        journey = _make_njt_journey(
            train_id="3840",
            scheduled_departure=twenty_min_ago,
            has_departed_station=True,
        )
        db_session.add(journey)
        await db_session.commit()

        response = await service.get_recent_departures(
            db_session, from_station="NY", window_minutes=120
        )

        assert len(response.departures) == 1
        assert response.departures[0].train_id == "3840"
        assert response.metadata["window_minutes"] == 120
        assert response.metadata["count"] == 1

    async def test_excludes_trains_outside_window(self, db_session: AsyncSession):
        """A train scheduled 3 hours ago is excluded from a 120-min window."""
        service = DepartureService()

        old = _make_njt_journey(
            train_id="3000",
            scheduled_departure=now_et() - timedelta(hours=3),
            has_departed_station=True,
        )
        recent = _make_njt_journey(
            train_id="3100",
            scheduled_departure=now_et() - timedelta(minutes=15),
            has_departed_station=True,
        )
        db_session.add_all([old, recent])
        await db_session.commit()

        response = await service.get_recent_departures(
            db_session, from_station="NY", window_minutes=120
        )

        train_ids = {d.train_id for d in response.departures}
        assert train_ids == {"3100"}

    async def test_excludes_future_trains(self, db_session: AsyncSession):
        """Upcoming trains (scheduled in the future) are never returned here."""
        service = DepartureService()

        future = _make_njt_journey(
            train_id="FUTURE1",
            scheduled_departure=now_et() + timedelta(minutes=30),
            has_departed_station=False,
        )
        db_session.add(future)
        await db_session.commit()

        response = await service.get_recent_departures(
            db_session, from_station="NY", window_minutes=120
        )

        assert response.departures == []

    async def test_includes_cancelled_train_even_without_has_departed(
        self, db_session: AsyncSession
    ):
        """A cancelled train within the window is returned even if it never departed."""
        service = DepartureService()

        cancelled = _make_njt_journey(
            train_id="CXL1",
            scheduled_departure=now_et() - timedelta(minutes=10),
            has_departed_station=False,
            is_cancelled=True,
        )
        db_session.add(cancelled)
        await db_session.commit()

        response = await service.get_recent_departures(
            db_session, from_station="NY", window_minutes=120
        )

        assert len(response.departures) == 1
        assert response.departures[0].train_id == "CXL1"
        assert response.departures[0].is_cancelled is True

    async def test_includes_completed_and_expired_trains(
        self, db_session: AsyncSession
    ):
        """is_completed / is_expired journeys remain visible in the recent window.

        This is the key behavioral difference vs /departures, which filters
        these out. Without it, any train that reached its terminal disappears
        from the recent list.
        """
        service = DepartureService()

        completed = _make_njt_journey(
            train_id="DONE1",
            scheduled_departure=now_et() - timedelta(minutes=30),
            has_departed_station=True,
            is_completed=True,
        )
        expired = _make_njt_journey(
            train_id="EXP1",
            scheduled_departure=now_et() - timedelta(minutes=45),
            has_departed_station=True,
            is_expired=True,
        )
        db_session.add_all([completed, expired])
        await db_session.commit()

        response = await service.get_recent_departures(
            db_session, from_station="NY", window_minutes=120
        )

        train_ids = {d.train_id for d in response.departures}
        assert train_ids == {"DONE1", "EXP1"}

    async def test_excludes_scheduled_train_that_never_departed_and_not_cancelled(
        self, db_session: AsyncSession
    ):
        """A past-scheduled train with has_departed=False and not cancelled
        carries no useful signal (the user can't tell if it ran). Exclude it."""
        service = DepartureService()

        ghost = _make_njt_journey(
            train_id="GHOST1",
            scheduled_departure=now_et() - timedelta(minutes=30),
            has_departed_station=False,
            is_cancelled=False,
        )
        db_session.add(ghost)
        await db_session.commit()

        response = await service.get_recent_departures(
            db_session, from_station="NY", window_minutes=120
        )

        assert response.departures == []

    async def test_results_sorted_most_recent_first(self, db_session: AsyncSession):
        """Results are ordered by scheduled_departure DESC (newest first)."""
        service = DepartureService()

        oldest = _make_njt_journey(
            train_id="T_OLDEST",
            scheduled_departure=now_et() - timedelta(minutes=90),
            has_departed_station=True,
        )
        middle = _make_njt_journey(
            train_id="T_MIDDLE",
            scheduled_departure=now_et() - timedelta(minutes=45),
            has_departed_station=True,
        )
        newest = _make_njt_journey(
            train_id="T_NEWEST",
            scheduled_departure=now_et() - timedelta(minutes=10),
            has_departed_station=True,
        )
        db_session.add_all([oldest, middle, newest])
        await db_session.commit()

        response = await service.get_recent_departures(
            db_session, from_station="NY", window_minutes=120
        )

        returned_ids = [d.train_id for d in response.departures]
        assert returned_ids == ["T_NEWEST", "T_MIDDLE", "T_OLDEST"]

    async def test_respects_limit(self, db_session: AsyncSession):
        """``limit`` truncates the result set after sorting."""
        service = DepartureService()

        for i in range(5):
            db_session.add(
                _make_njt_journey(
                    train_id=f"LIM{i}",
                    scheduled_departure=now_et() - timedelta(minutes=10 + i * 5),
                    has_departed_station=True,
                )
            )
        await db_session.commit()

        response = await service.get_recent_departures(
            db_session, from_station="NY", window_minutes=120, limit=3
        )

        assert len(response.departures) == 3
        # Most-recent three: LIM0 (10m), LIM1 (15m), LIM2 (20m)
        assert [d.train_id for d in response.departures] == ["LIM0", "LIM1", "LIM2"]

    async def test_data_source_filter(self, db_session: AsyncSession):
        """``data_sources`` restricts results to the requested providers."""
        service = DepartureService()

        njt = _make_njt_journey(
            train_id="NJT_A",
            scheduled_departure=now_et() - timedelta(minutes=15),
            has_departed_station=True,
        )
        # Minimal AMTRAK journey reusing the NJT-style helper but switching source
        amtrak = _make_njt_journey(
            train_id="A2150",
            scheduled_departure=now_et() - timedelta(minutes=20),
            has_departed_station=True,
        )
        amtrak.data_source = "AMTRAK"
        amtrak.line_code = "AM"
        db_session.add_all([njt, amtrak])
        await db_session.commit()

        njt_only = await service.get_recent_departures(
            db_session, from_station="NY", data_sources=["NJT"]
        )
        assert {d.train_id for d in njt_only.departures} == {"NJT_A"}

        amtrak_only = await service.get_recent_departures(
            db_session, from_station="NY", data_sources=["AMTRAK"]
        )
        assert {d.train_id for d in amtrak_only.departures} == {"A2150"}

    async def test_destination_filter_requires_forward_sequence(
        self, db_session: AsyncSession
    ):
        """With ``to_station`` set, the stop must come after the origin in the journey."""
        service = DepartureService()

        journey = _make_njt_journey(
            train_id="3840",
            scheduled_departure=now_et() - timedelta(minutes=15),
            has_departed_station=True,
        )
        # Add a downstream stop (Trenton)
        tr_stop = JourneyStop(
            station_code="TR",
            station_name="Trenton",
            scheduled_arrival=now_et() - timedelta(minutes=15) + timedelta(minutes=60),
            stop_sequence=1,
            has_departed_station=False,
        )
        journey.stops = journey.stops + [tr_stop]
        db_session.add(journey)
        await db_session.commit()

        # NY → TR: should return the train with arrival info populated
        forward = await service.get_recent_departures(
            db_session, from_station="NY", to_station="TR"
        )
        assert len(forward.departures) == 1
        assert forward.departures[0].arrival is not None
        assert forward.departures[0].arrival.code == "TR"

        # TR → NY: NY has sequence 0, TR has sequence 1, so NY can't follow TR
        reverse = await service.get_recent_departures(
            db_session, from_station="TR", to_station="NY"
        )
        assert reverse.departures == []
