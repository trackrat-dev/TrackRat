"""PATH journeys in flight at midnight must stay reachable (issue #1752).

Two interacting defects stranded them, and fixing either alone leaves the other
firing — so both are pinned here.

**The date came from the wrong end of the trip.** ``_build_train_candidate``
set ``journey_date`` from the *discovering arrival* while ``scheduled_departure``
held the origin departure. The discovering arrival is a prediction at whichever
station happened to see the train, so one physical trip got a different
``journey_date`` depending on where it was sighted, and the date flipped to
tomorrow up to ~20 minutes before midnight because the prediction runs ahead of
the clock. ``journey_date`` is in ``group_key``, in ``_find_active_journeys``'
filter, and in the ``(train_id, journey_date, data_source)`` unique constraint,
so a train sighted either side of that flip landed in a different group *and*
could not see the row already created for it. A duplicate journey every night,
independent of any clustering tolerance.

**Nothing could reach the row afterwards.** ``_update_journeys`` filtered
``journey_date == today``, and it is the *only* sweep that touches a PATH
journey: ``_expire_old_journeys`` and ``schedule_periodic_updates`` are both
NJT-only, and ``retention_cleanup`` does not delete anything for 60 days. Once
the date rolled over, yesterday's in-flight journeys were never updated, never
completed and never expired — production showed one still on record 21.5 hours
after its origin departure. The Live Activity push job derives status from
``is_completed``, so it kept pushing "EN ROUTE" for trains that had arrived
hours earlier.

These tests run against real Postgres, so the unique constraint and the date
filters are the production ones rather than a mock's opinion of them.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from trackrat.collectors.path.collector import (
    PathCollector,
    _build_train_candidate,
)
from trackrat.collectors.path.ridepath_client import PathArrival
from trackrat.models.database import TrainJourney
from trackrat.utils.time import normalize_to_et, now_et

# PJS -> PGR is 3 minutes and PJS -> PNP is 6 on the JSQ-33 line, per the GTFS
# segment times these tests fall back from (uniform 3.0 min/segment with an
# empty map). Both therefore imply the same origin departure, which is what
# makes them two sightings of one train.
_PGR_MINUTES_FROM_ORIGIN = 3
_PNP_MINUTES_FROM_ORIGIN = 6


def _jsq_arrival(
    station_code: str,
    minutes_away: int,
    base: datetime,
    headsign: str = "33rd Street",
) -> PathArrival:
    """A RidePATH prediction on the JSQ-33 line, arriving ``minutes_away``
    after ``base`` implies an origin departure at ``base``."""
    return PathArrival(
        station_code=station_code,
        headsign=headsign,
        direction="ToNY",
        minutes_away=minutes_away,
        arrival_time=base + timedelta(minutes=minutes_away),
        line_color="FF9900",
        last_updated=None,
    )


def _late_night_departure(reference: datetime) -> datetime:
    """An origin departure at 23:56 — before midnight, arriving after it.

    Anchored to a recent real day rather than a fixed calendar date so the
    journey stays inside the collector's active window.
    """
    yesterday = normalize_to_et(reference).date() - timedelta(days=1)
    return normalize_to_et(
        datetime.combine(yesterday, datetime.min.time()).replace(hour=23, minute=56)
    )


class TestJourneyDateIsDerivedFromTheOriginDeparture:
    """The date must describe the trip, not the sighting that found it."""

    def test_mid_route_sighting_dates_by_the_origin_not_the_arrival(self):
        """The case that produced ``PATH_PWC_newark_1785729360``.

        A train departing at 23:56 is still running at 00:02, when a station six
        minutes down the line predicts its arrival. Dating by that prediction
        files the trip under *tomorrow* while its ``scheduled_departure`` says
        yesterday — the two halves of one row disagreeing about which day it is.
        """
        origin_departure = _late_night_departure(now_et())
        arrival = _jsq_arrival("PNP", _PNP_MINUTES_FROM_ORIGIN, origin_departure)

        candidate = _build_train_candidate(arrival, {})

        assert candidate is not None
        assert normalize_to_et(candidate.origin_departure).date() == (
            origin_departure.date()
        )
        assert candidate.journey_date == origin_departure.date(), (
            f"journey_date is {candidate.journey_date} but the train departed "
            f"on {origin_departure.date()}; the row is filed under the date of "
            "the arrival that discovered it, which is a different day for the "
            "same physical trip"
        )
        assert candidate.journey_date != normalize_to_et(arrival.arrival_time).date(), (
            "this test is not exercising the midnight crossing — the arrival "
            "and the departure fall on the same day"
        )

    def test_two_stations_across_midnight_agree_on_the_date(self):
        """One train, two sightings, one date — so one ``group_key``.

        Before the fix the PGR sighting (arriving 23:59) dated to yesterday and
        the PNP sighting (arriving 00:02) dated to today. Different groups,
        different ``_find_active_journeys`` filters, and a unique constraint
        that permits both rows: a guaranteed duplicate, nightly.
        """
        origin_departure = _late_night_departure(now_et())

        near = _build_train_candidate(
            _jsq_arrival("PGR", _PGR_MINUTES_FROM_ORIGIN, origin_departure), {}
        )
        far = _build_train_candidate(
            _jsq_arrival("PNP", _PNP_MINUTES_FROM_ORIGIN, origin_departure), {}
        )

        assert near is not None and far is not None
        # Precondition: the sightings really do straddle midnight.
        assert (
            normalize_to_et(near.arrival.arrival_time).date()
            != normalize_to_et(far.arrival.arrival_time).date()
        ), "the two arrivals land on the same day; midnight is not being crossed"

        assert near.journey_date == far.journey_date
        assert near.group_key == far.group_key, (
            "the two sightings of one train land in different groups, so the "
            "second cannot see the journey the first created"
        )
        assert near.train_id == far.train_id, (
            "the train_id is built from the origin departure, so it should "
            "already agree; if it does not, the back-calculation itself differs"
        )

    def test_a_daytime_trip_is_unaffected(self):
        """The overwhelmingly common case must not move.

        Away from midnight the arrival and the origin fall on the same day, so
        this change is a no-op — which is what makes it safe to apply
        unconditionally rather than only near the rollover.
        """
        base = normalize_to_et(now_et()).replace(hour=14, minute=0, second=0)
        candidate = _build_train_candidate(
            _jsq_arrival("PNP", _PNP_MINUTES_FROM_ORIGIN, base), {}
        )

        assert candidate is not None
        assert candidate.journey_date == base.date()
        assert (
            candidate.journey_date
            == normalize_to_et(candidate.arrival.arrival_time).date()
        )


async def _persist_path_journey(
    db_session,
    *,
    train_id: str,
    journey_date,
    scheduled_departure: datetime,
    api_error_count: int = 0,
) -> TrainJourney:
    journey = TrainJourney(
        train_id=train_id,
        journey_date=journey_date,
        line_code="JSQ-33",
        line_name="Journal Square-33rd Street",
        line_color="#FF9900",
        destination="33rd Street",
        origin_station_code="PJS",
        terminal_station_code="P33",
        data_source="PATH",
        observation_type="OBSERVED",
        scheduled_departure=scheduled_departure,
        has_complete_journey=True,
        stops_count=9,
        api_error_count=api_error_count,
        is_completed=False,
        is_expired=False,
        is_cancelled=False,
    )
    db_session.add(journey)
    await db_session.commit()
    return journey


async def _reload(db_session, train_id: str) -> TrainJourney:
    db_session.expire_all()
    result = await db_session.execute(
        select(TrainJourney).where(TrainJourney.train_id == train_id)
    )
    return result.scalar_one()


class TestUpdateWindowReachesYesterday:
    """The sweep must still see a trip that departed before midnight."""

    @pytest.mark.asyncio
    async def test_yesterdays_in_flight_journey_is_selected(self, db_session):
        """The orphaning half of the bug, directly.

        ``_update_journeys`` is the only thing that ever updates, completes or
        expires a PATH journey. A ``journey_date == today`` filter meant a trip
        that crossed midnight fell out of every sweep for good.
        """
        yesterday = now_et().date() - timedelta(days=1)
        await _persist_path_journey(
            db_session,
            train_id="PATH_PJS_33rd_xmid",
            journey_date=yesterday,
            scheduled_departure=_late_night_departure(now_et()),
        )

        collector = PathCollector()
        result = await collector._update_journeys(db_session, [], {})
        await db_session.commit()

        assert result["updated"] + result["completed"] >= 1, (
            "the cross-midnight journey was not selected by the update sweep; "
            "nothing else in the codebase will ever touch it again — "
            "_expire_old_journeys and schedule_periodic_updates are NJT-only, "
            "and retention_cleanup waits 60 days"
        )

    @pytest.mark.asyncio
    async def test_a_stranded_journey_reaches_expiry(self, db_session):
        """Reachable is not enough — it has to actually finish.

        With no arrivals matching and the origin departure in the past, the
        existing 3-dry-cycle rule expires it. Production had one of these still
        on record 21.5 hours after departure precisely because that rule was
        never reached.
        """
        yesterday = now_et().date() - timedelta(days=1)
        train_id = "PATH_PJS_33rd_strand"
        await _persist_path_journey(
            db_session,
            train_id=train_id,
            journey_date=yesterday,
            scheduled_departure=_late_night_departure(now_et()),
        )

        # A non-empty arrivals list that simply does not contain this train:
        # the strike counter is meant to count cycles where RidePATH answered
        # and the train was absent, not cycles where the fetch failed. (The
        # no-data case is short-circuited a level up, in ``collect``.)
        other_trains = [
            _jsq_arrival("PGR", _PGR_MINUTES_FROM_ORIGIN, now_et(), headsign="Hoboken")
        ]

        collector = PathCollector()
        for _ in range(3):
            # _update_journeys leaves the commit to its caller (``collect``),
            # so the strike only persists if we do the same here.
            await collector._update_journeys(db_session, other_trains, {})
            await db_session.commit()

        journey = await _reload(db_session, train_id)
        assert journey.is_expired is True, (
            f"api_error_count reached {journey.api_error_count} but the journey "
            "is still active; it will sit in the table unresolved, and the "
            "Live Activity push job will keep reporting it EN ROUTE"
        )

    @pytest.mark.asyncio
    async def test_the_window_stops_at_yesterday(self, db_session):
        """Two days back is out of scope, deliberately.

        The longest PATH route is well under an hour, so nothing dated before
        yesterday can still be moving. Including it would only re-open rows the
        expiry has already finished with — and re-running the sweep over an
        unbounded history is how this table gets expensive.
        """
        long_ago = now_et().date() - timedelta(days=2)
        train_id = "PATH_PJS_33rd_old"
        await _persist_path_journey(
            db_session,
            train_id=train_id,
            journey_date=long_ago,
            scheduled_departure=normalize_to_et(
                datetime.combine(long_ago, datetime.min.time()).replace(hour=23)
            ),
        )

        before = (await _reload(db_session, train_id)).update_count

        collector = PathCollector()
        result = await collector._update_journeys(db_session, [], {})
        await db_session.commit()

        journey = await _reload(db_session, train_id)
        assert result["updated"] == 0 and result["completed"] == 0
        assert journey.update_count == before, (
            f"update_count moved {before} -> {journey.update_count}: a "
            "two-day-old journey was picked up by the sweep, so the window is "
            "wider than a PATH trip can possibly be"
        )


class TestNoDuplicateAcrossMidnight:
    """The unique constraint cannot catch this, so the date derivation must."""

    @pytest.mark.asyncio
    async def test_second_sighting_finds_the_first_sightings_row(self, db_session):
        """Discovery twice over one train, either side of midnight.

        The second pass must find the row the first created rather than mint a
        second one. This is the end-to-end form of the ``group_key`` assertion
        above, through the real unique constraint — which permits both rows
        when the dates differ, so it offers no protection here.
        """
        origin_departure = _late_night_departure(now_et())
        collector = PathCollector()

        # Sighting 1: PGR, arriving 23:59 — before the rollover.
        first = await collector._discover_trains(
            db_session,
            [_jsq_arrival("PGR", _PGR_MINUTES_FROM_ORIGIN, origin_departure)],
            {},
        )
        await db_session.commit()
        assert first["new_journeys"] == 1

        # Sighting 2: PNP, arriving 00:02 — after it. Same physical train.
        second = await collector._discover_trains(
            db_session,
            [_jsq_arrival("PNP", _PNP_MINUTES_FROM_ORIGIN, origin_departure)],
            {},
        )
        await db_session.commit()

        rows = (
            (
                await db_session.execute(
                    select(TrainJourney).where(TrainJourney.data_source == "PATH")
                )
            )
            .scalars()
            .all()
        )
        assert second["new_journeys"] == 0, (
            "the post-midnight sighting created a second journey for a train "
            "already on record"
        )
        assert len(rows) == 1, (
            f"{len(rows)} journeys exist for one physical train: "
            f"{[(r.train_id, r.journey_date) for r in rows]}"
        )
