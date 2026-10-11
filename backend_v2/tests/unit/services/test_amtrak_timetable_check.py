"""Phantom Amtrak pattern trains after a timetable change (issue #1881).

On 2026-10-10 the pattern scheduler projected 18 Saturday trains Amtrak had
dropped in its 2026-10-04 timetable change, and departures served them as live.
Two fixes, both exercised here against a real database:

A. ``AmtrakPatternScheduler.drop_patterns_not_in_timetable`` drops patterns for
   train numbers the stored Amtrak GTFS knows but doesn't run on the target
   date, deletes an already-projected SCHEDULED row for them, and fails open
   for numbers the feed doesn't know and for dates the feed doesn't cover.
B. ``get_effective_observation_type`` no longer promotes an Amtrak SCHEDULED
   row to OBSERVED, so departures' stale-SCHEDULED filter hides an unseen
   pattern row near its departure time.
"""

from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select

from trackrat.models.database import (
    GTFSCalendar,
    GTFSRoute,
    GTFSTrip,
    JourneyStop,
    TrainJourney,
)
from trackrat.services.amtrak_pattern_scheduler import AmtrakPatternScheduler
from trackrat.services.departure import DepartureService
from trackrat.services.gtfs import GTFSService
from trackrat.utils.time import ET, now_et

SATURDAY = date(2026, 10, 10)
# Outside both seeded calendars: the stored feed says nothing about this date.
UNCOVERED_DATE = date(2027, 3, 6)


@pytest.fixture(autouse=True)
def _clear_service_id_cache():
    GTFSService._service_id_cache.clear()
    yield
    GTFSService._service_id_cache.clear()


async def _seed_amtrak_gtfs(db) -> None:
    """Mirror the post-2026-10-04 timetable for the trains in the issue.

    - 2260 (Acela): weekday-only now; its Saturday run was dropped.
    - 2150 (Acela): still runs Saturdays.
    - 2 (Sunset Limited): Friday service day only. It leaves LA Fri 22:00 PT,
      which Amtrak lists as Fri "1:00:00" (Eastern, wrapped) and TrackRat
      dates Saturday.
    - 702 (San Joaquins) is deliberately absent: the national GTFS omits it.
    """
    route = GTFSRoute(
        data_source="AMTRAK",
        route_id="40751",
        route_short_name="Acela",
        route_long_name="Acela",
        route_color="004B87",
    )
    db.add(route)
    await db.flush()

    window = {"start_date": date(2026, 10, 4), "end_date": date(2027, 1, 31)}
    db.add_all(
        [
            GTFSCalendar(
                data_source="AMTRAK",
                service_id="WKDY",
                monday=True,
                tuesday=True,
                wednesday=True,
                thursday=True,
                friday=True,
                saturday=False,
                sunday=False,
                **window,
            ),
            GTFSCalendar(
                data_source="AMTRAK",
                service_id="DAILY",
                monday=True,
                tuesday=True,
                wednesday=True,
                thursday=True,
                friday=True,
                saturday=True,
                sunday=True,
                **window,
            ),
            GTFSCalendar(
                data_source="AMTRAK",
                service_id="FRI",
                monday=False,
                tuesday=False,
                wednesday=False,
                thursday=False,
                friday=True,
                saturday=False,
                sunday=False,
                **window,
            ),
            GTFSTrip(
                data_source="AMTRAK",
                trip_id="t-2",
                route_id=route.id,
                service_id="FRI",
                trip_headsign="New Orleans",
                train_id="2",
            ),
            GTFSTrip(
                data_source="AMTRAK",
                trip_id="t-2260",
                route_id=route.id,
                service_id="WKDY",
                trip_headsign="Boston",
                train_id="2260",
            ),
            GTFSTrip(
                data_source="AMTRAK",
                trip_id="t-2150",
                route_id=route.id,
                service_id="DAILY",
                trip_headsign="Boston",
                train_id="2150",
            ),
        ]
    )
    await db.flush()


def _pattern(train_number: str, median_departure: time = time(16, 0)) -> dict:
    return {
        "train_number": train_number,
        "median_departure": median_departure,
        "occurrence_count": 3,
        "origin": "WS",
        "destination": "Boston",
        "terminal": "BOS",
        "line_name": "Acela",
        "time_variance": 1.0,
        "sample_dates": [],
    }


def _journey(
    train_id: str,
    journey_date: date,
    observation_type: str,
    stops: list[tuple[str, datetime]],
) -> TrainJourney:
    """A minimal Amtrak journey; ``stops`` is [(station_code, scheduled_time)]."""
    journey = TrainJourney(
        train_id=train_id,
        journey_date=journey_date,
        data_source="AMTRAK",
        observation_type=observation_type,
        line_code="AM",
        line_name="Acela",
        destination="Boston",
        origin_station_code=stops[0][0],
        terminal_station_code=stops[-1][0],
        scheduled_departure=stops[0][1],
        first_seen_at=now_et(),
        last_updated_at=now_et(),
        has_complete_journey=False,
        stops_count=len(stops),
        is_cancelled=False,
        is_completed=False,
        is_expired=False,
        api_error_count=0,
        update_count=1,
    )
    for seq, (code, when) in enumerate(stops):
        JourneyStop(
            journey=journey,
            station_code=code,
            station_name=code,
            stop_sequence=seq,
            scheduled_departure=when,
            scheduled_arrival=when,
            has_departed_station=False,
        )
    return journey


def datetime_at(day: date) -> datetime:
    return datetime.combine(day, time(16, 0))


def _session_factory(db):
    """Route the scheduler's get_session() to the test session, committing on
    exit like the real one."""

    @asynccontextmanager
    async def _session():
        yield db
        await db.commit()

    return _session


# ---------------------------------------------------------------------------
# A. GTFSService.get_train_ids_not_running
# ---------------------------------------------------------------------------


class TestGetTrainIdsNotRunning:
    @pytest.mark.asyncio
    async def test_known_but_not_scheduled_is_returned(self, db_session):
        """2260 is in the feed but has no Saturday trip -> reported, with both
        the production 'A'-prefixed id and a bare id."""
        await _seed_amtrak_gtfs(db_session)

        result = await GTFSService().get_train_ids_not_running(
            db_session, "AMTRAK", ["A2260", "2260", "A2150", "A702"], SATURDAY
        )

        print(f"not running on {SATURDAY}: {result}")
        assert result == {"A2260", "2260"}, (
            "expected only 2260 (known, weekday-only) to be reported; 2150 runs "
            f"Saturdays and 702 is unknown to the feed. Got {result}"
        )

    @pytest.mark.asyncio
    async def test_runs_on_weekday(self, db_session):
        """On a weekday 2260 runs, so nothing is reported."""
        await _seed_amtrak_gtfs(db_session)
        monday = SATURDAY + timedelta(days=2)

        result = await GTFSService().get_train_ids_not_running(
            db_session, "AMTRAK", ["A2260", "A2150"], monday
        )

        assert result == set(), f"both trains run on {monday}, got {result}"

    @pytest.mark.asyncio
    async def test_date_outside_feed_is_unknown(self, db_session):
        """No service on the date (feed lapsed / not covering it) -> None, so
        callers fail open instead of reading it as 'nothing runs'."""
        await _seed_amtrak_gtfs(db_session)

        result = await GTFSService().get_train_ids_not_running(
            db_session, "AMTRAK", ["A2260", "A2150"], UNCOVERED_DATE
        )

        assert result is None, f"expected None for {UNCOVERED_DATE}, got {result}"

    @pytest.mark.asyncio
    async def test_no_feed_stored_is_unknown(self, db_session):
        result = await GTFSService().get_train_ids_not_running(
            db_session, "AMTRAK", ["A2260"], SATURDAY
        )

        assert result is None, f"expected None with no feed stored, got {result}"


# ---------------------------------------------------------------------------
# A. AmtrakPatternScheduler.drop_patterns_not_in_timetable
# ---------------------------------------------------------------------------


class TestDropPatternsNotInTimetable:
    @pytest.mark.asyncio
    async def test_drops_pattern_and_deletes_projected_row(self, db_session):
        """The phantom pattern is dropped and its SCHEDULED row (projected the
        night before, with stops) is deleted; the San Joaquins pattern (unknown
        to GTFS) and the still-running 2150 are kept."""
        await _seed_amtrak_gtfs(db_session)
        t = ET.localize(datetime_at(SATURDAY))
        db_session.add(_journey("A2260", SATURDAY, "SCHEDULED", [("WS", t)]))
        db_session.add(_journey("A2150", SATURDAY, "SCHEDULED", [("WS", t)]))
        await db_session.commit()

        patterns = [_pattern("A2260"), _pattern("A2150"), _pattern("A702")]
        with patch(
            "trackrat.services.amtrak_pattern_scheduler.get_session",
            _session_factory(db_session),
        ):
            kept = await AmtrakPatternScheduler().drop_patterns_not_in_timetable(
                patterns, SATURDAY
            )

        kept_numbers = [p["train_number"] for p in kept]
        remaining = (
            (await db_session.execute(select(TrainJourney.train_id))).scalars().all()
        )
        stop_owners = (
            (await db_session.execute(select(JourneyStop.journey_id))).scalars().all()
        )
        print(f"kept={kept_numbers} remaining_rows={remaining} stops={stop_owners}")

        assert kept_numbers == ["A2150", "A702"]
        assert sorted(remaining) == ["A2150"], (
            "the phantom A2260 SCHEDULED row should be deleted, A2150 kept; "
            f"got {remaining}"
        )
        assert len(stop_owners) == 1, f"A2260's stop should cascade, got {stop_owners}"

    @pytest.mark.asyncio
    async def test_observed_row_is_never_deleted(self, db_session):
        """A train GTFS says doesn't run but which discovery actually saw (the
        issue's A343/A551 ran despite GTFS) keeps its OBSERVED row."""
        await _seed_amtrak_gtfs(db_session)
        t = ET.localize(datetime_at(SATURDAY))
        db_session.add(_journey("A2260", SATURDAY, "OBSERVED", [("WS", t)]))
        await db_session.commit()

        with patch(
            "trackrat.services.amtrak_pattern_scheduler.get_session",
            _session_factory(db_session),
        ):
            kept = await AmtrakPatternScheduler().drop_patterns_not_in_timetable(
                [_pattern("A2260")], SATURDAY
            )

        rows = (
            await db_session.execute(
                select(TrainJourney.train_id, TrainJourney.observation_type)
            )
        ).all()
        print(f"kept={kept} rows={rows}")
        assert kept == []
        assert [tuple(r) for r in rows] == [("A2260", "OBSERVED")]

    @pytest.mark.asyncio
    async def test_fails_open_when_feed_does_not_cover_date(self, db_session):
        """With no GTFS service on the date every pattern is kept and no row is
        touched."""
        await _seed_amtrak_gtfs(db_session)
        t = ET.localize(datetime_at(UNCOVERED_DATE))
        db_session.add(_journey("A2260", UNCOVERED_DATE, "SCHEDULED", [("WS", t)]))
        await db_session.commit()

        patterns = [_pattern("A2260"), _pattern("A2150")]
        with patch(
            "trackrat.services.amtrak_pattern_scheduler.get_session",
            _session_factory(db_session),
        ):
            kept = await AmtrakPatternScheduler().drop_patterns_not_in_timetable(
                patterns, UNCOVERED_DATE
            )

        remaining = (
            (await db_session.execute(select(TrainJourney.train_id))).scalars().all()
        )
        assert kept == patterns, f"expected fail-open, got {kept}"
        assert remaining == ["A2260"], f"no row should be deleted, got {remaining}"

    @pytest.mark.asyncio
    async def test_after_midnight_train_matches_previous_service_day(self, db_session):
        """A2 departs Saturday 01:00 Eastern, but GTFS files it under Friday.
        It must be kept (production history: A2 runs Mon/Thu/Sat Eastern while
        GTFS lists Sun/Wed/Fri). The same train at a mid-day time has no such
        excuse and is dropped."""
        await _seed_amtrak_gtfs(db_session)

        with patch(
            "trackrat.services.amtrak_pattern_scheduler.get_session",
            _session_factory(db_session),
        ):
            scheduler = AmtrakPatternScheduler()
            after_midnight = await scheduler.drop_patterns_not_in_timetable(
                [_pattern("A2", time(1, 0))], SATURDAY
            )
            midday = await scheduler.drop_patterns_not_in_timetable(
                [_pattern("A2", time(10, 0))], SATURDAY
            )

        print(f"01:00 kept={after_midnight} 10:00 kept={midday}")
        assert [p["train_number"] for p in after_midnight] == ["A2"], (
            "A2 at 01:00 Eastern runs on GTFS's previous service day and must be "
            f"kept, got {after_midnight}"
        )
        assert midday == [], f"A2 at 10:00 has no Saturday trip, got {midday}"

    @pytest.mark.asyncio
    async def test_after_midnight_train_kept_when_previous_day_unknown(
        self, db_session
    ):
        """The day before the feed starts is unknown, so an after-midnight
        pattern is kept rather than dropped on missing evidence."""
        await _seed_amtrak_gtfs(db_session)
        first_feed_day = date(2026, 10, 4)  # Sunday; Saturday 10-03 not covered

        with patch(
            "trackrat.services.amtrak_pattern_scheduler.get_session",
            _session_factory(db_session),
        ):
            kept = await AmtrakPatternScheduler().drop_patterns_not_in_timetable(
                [_pattern("A2", time(1, 0))], first_feed_day
            )

        assert [p["train_number"] for p in kept] == [
            "A2"
        ], f"expected fail-open for an unknown previous day, got {kept}"

    @pytest.mark.asyncio
    async def test_other_dates_untouched(self, db_session):
        """Only the target date's SCHEDULED row is deleted."""
        await _seed_amtrak_gtfs(db_session)
        next_sat = SATURDAY + timedelta(days=7)
        for day in (SATURDAY, next_sat):
            t = ET.localize(datetime_at(day))
            db_session.add(_journey("A2260", day, "SCHEDULED", [("WS", t)]))
        await db_session.commit()

        with patch(
            "trackrat.services.amtrak_pattern_scheduler.get_session",
            _session_factory(db_session),
        ):
            await AmtrakPatternScheduler().drop_patterns_not_in_timetable(
                [_pattern("A2260")], SATURDAY
            )

        dates = (
            (await db_session.execute(select(TrainJourney.journey_date)))
            .scalars()
            .all()
        )
        assert dates == [next_sat], f"only {SATURDAY} should be deleted, got {dates}"


# ---------------------------------------------------------------------------
# B. Departures: an unseen pattern row is no longer served as live
# ---------------------------------------------------------------------------


class TestPatternRowOnDepartures:
    async def _departures(self, db_session, train_id: str, minutes_to_ny: int):
        now = now_et()
        db_session.add(
            _journey(
                train_id,
                now.date(),
                "SCHEDULED",
                [
                    ("WS", now - timedelta(hours=2)),
                    ("NY", now + timedelta(minutes=minutes_to_ny)),
                    ("BOS", now + timedelta(minutes=minutes_to_ny + 200)),
                ],
            )
        )
        await db_session.commit()
        response = await DepartureService().get_departures(
            db=db_session,
            from_station="NY",
            to_station="BOS",
            time_from=now - timedelta(hours=1),
            time_to=now + timedelta(hours=6),
            hide_departed=False,
            data_sources=["AMTRAK"],
        )
        return {d.train_id: d.observation_type for d in response.departures}

    @pytest.mark.asyncio
    async def test_unseen_row_near_departure_is_hidden(self, db_session):
        """Past its origin time and 5 minutes from New York with no sighting:
        before the fix this was relabelled OBSERVED and shown as live."""
        served = await self._departures(db_session, "A2260", minutes_to_ny=5)
        print(f"served={served}")
        assert (
            "A2260" not in served
        ), f"unseen pattern row near departure should be hidden, got {served}"

    @pytest.mark.asyncio
    async def test_unseen_row_later_shows_as_scheduled(self, db_session):
        """Further out it still shows, but as SCHEDULED, not live."""
        served = await self._departures(db_session, "A2260", minutes_to_ny=90)
        print(f"served={served}")
        assert (
            served.get("A2260") == "SCHEDULED"
        ), f"expected A2260 served as SCHEDULED, got {served}"
