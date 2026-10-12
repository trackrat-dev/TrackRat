"""
Regression tests for issue #1882: station boards listed trains that terminate
at the station as departures.

``/trains/departures`` and ``/trains/recent-departures`` called with only
``from`` (both clients' Station Details screens) returned every journey with a
stop at the station, including journeys whose stop there is their last one.
Staging showed 37/100 NY Penn rows, 55/100 Hoboken and 48/100 GCT were trains
arriving and ending there, each listed with the station itself as its
destination. SEPTA Regional Rail was worse: a through-routed train is two GTFS
trips handing over at Suburban Station (the inbound trip ends there, the
outbound trip starts there), so the same physical train appeared twice on
that board at the same minute.

These tests run the real departure queries against a live database:
- the SEPTA handover produces exactly one row on the handover board, on both
  the upcoming and the recent board, while the inbound trip still appears on
  the boards of stations it actually departs from;
- route searches (``from`` + ``to``) are unchanged, including one ending at
  the terminal;
- an NJT journey not yet fully sequenced keeps its row (positional terminal
  detection can't be trusted there — terminal_stop_index's safe default);
- static GTFS terminating trips are excluded in SQL, before the per-source row
  cap, so a terminal's arrivals can't crowd its departures off the board.
"""

from datetime import date, datetime, time, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import (
    GTFSCalendar,
    GTFSRoute,
    GTFSStopTime,
    GTFSTrip,
    JourneyStop,
    TrainJourney,
)
from trackrat.services.departure import DepartureService
from trackrat.services.gtfs import GTFSService
from trackrat.utils.time import ET, now_et

# SEPTA Regional Rail Center City stations, in inbound order (issue #1882's
# AIR4252/NOR4252 pair): 30th St, Suburban Station (the handover), Jefferson.
THIRTIETH_ST = "SEPR90004"
SUBURBAN = "SEPR90005"
JEFFERSON = "SEPR90006"


def _journey(
    *,
    train_id: str,
    data_source: str,
    stops: list[tuple[str, int | None, datetime]],
    terminal: str,
    destination: str,
    departed_through: int = -1,
) -> TrainJourney:
    """Build a journey from (station_code, stop_sequence, time) tuples.

    Stops at index <= ``departed_through`` are marked departed, which the
    recent-departures board requires.
    """
    now = now_et()
    journey = TrainJourney(
        train_id=train_id,
        journey_date=stops[0][2].date(),
        data_source=data_source,
        observation_type="OBSERVED",
        line_code="AIR" if data_source == "SEPTA_RR" else "NE",
        line_name="Test Line",
        line_color="#91456C",
        destination=destination,
        origin_station_code=stops[0][0],
        terminal_station_code=terminal,
        scheduled_departure=stops[0][2],
        first_seen_at=now - timedelta(hours=1),
        last_updated_at=now,
        has_complete_journey=True,
        stops_count=len(stops),
        update_count=3,
        is_cancelled=False,
        is_completed=False,
        is_expired=False,
    )
    journey.stops = [
        JourneyStop(
            station_code=code,
            station_name=code,
            stop_sequence=sequence,
            # Terminal stops carry a departure time too (AIR4252 at
            # SEPR90005: arr 18:05 / dep 18:05) — which is why the
            # scheduled_departure window let them onto the board.
            scheduled_arrival=at,
            scheduled_departure=at,
            has_departed_station=index <= departed_through,
        )
        for index, (code, sequence, at) in enumerate(stops)
    ]
    return journey


def _septa_through_train(base: datetime, departed_through: int = -1):
    """Train 4252 as SEPTA publishes it: AIR4252 inbound ends at Suburban
    Station, NOR4252 outbound starts there at the same minute."""
    inbound = _journey(
        train_id="AIR4252",
        data_source="SEPTA_RR",
        stops=[
            ("SEPR90406", 1, base - timedelta(minutes=10)),
            (THIRTIETH_ST, 2, base - timedelta(minutes=4)),
            (SUBURBAN, 3, base),
        ],
        terminal=SUBURBAN,
        destination="Suburban Station",
        departed_through=departed_through,
    )
    outbound = _journey(
        train_id="NOR4252",
        data_source="SEPTA_RR",
        stops=[
            (SUBURBAN, 1, base),
            (JEFFERSON, 2, base + timedelta(minutes=3)),
            ("SEPR90007", 3, base + timedelta(minutes=30)),
        ],
        terminal="SEPR90007",
        destination="Conshohocken",
        departed_through=departed_through,
    )
    return inbound, outbound


async def _board(
    db: AsyncSession, from_station: str, data_source: str, to_station=None
) -> list[str]:
    now = now_et()
    response = await DepartureService().get_departures(
        db=db,
        from_station=from_station,
        to_station=to_station,
        time_from=now - timedelta(minutes=30),
        time_to=now + timedelta(hours=2),
        data_sources=[data_source],
        skip_gtfs_merge=True,
        skip_individual_refresh=True,
    )
    return [d.train_id for d in response.departures]


@pytest.mark.asyncio
class TestRealtimeBoardsExcludeTerminatingTrains:
    async def test_septa_through_train_listed_once_at_handover(
        self, db_session: AsyncSession
    ):
        inbound, outbound = _septa_through_train(now_et() + timedelta(minutes=10))
        db_session.add_all([inbound, outbound])
        await db_session.commit()

        board = await _board(db_session, SUBURBAN, "SEPTA_RR")
        assert board == ["NOR4252"], (
            "Suburban Station must list train 4252 once, as the outbound "
            "NOR4252 that departs there; AIR4252 ends there and is an "
            f"arrival (issue #1882). Board: {board}"
        )

    async def test_terminating_trip_still_listed_where_it_departs(
        self, db_session: AsyncSession
    ):
        inbound, outbound = _septa_through_train(now_et() + timedelta(minutes=10))
        db_session.add_all([inbound, outbound])
        await db_session.commit()

        board = await _board(db_session, THIRTIETH_ST, "SEPTA_RR")
        assert board == ["AIR4252"], (
            "30th St is an intermediate stop of AIR4252, so the inbound trip "
            f"must stay on that board. Board: {board}"
        )

    async def test_route_search_to_terminal_unchanged(self, db_session: AsyncSession):
        inbound, outbound = _septa_through_train(now_et() + timedelta(minutes=10))
        db_session.add_all([inbound, outbound])
        await db_session.commit()

        board = await _board(db_session, THIRTIETH_ST, "SEPTA_RR", to_station=SUBURBAN)
        assert board == ["AIR4252"], (
            "A from+to search ending at the inbound trip's terminal must still "
            f"return it — only a terminal from-stop is filtered. Board: {board}"
        )

    async def test_recent_departures_exclude_arrivals(self, db_session: AsyncSession):
        # Both trips have run through Suburban Station 20 minutes ago; every
        # stop is flagged departed, as the collectors latch it on arrival too.
        inbound, outbound = _septa_through_train(
            now_et() - timedelta(minutes=20), departed_through=2
        )
        db_session.add_all([inbound, outbound])
        await db_session.commit()

        response = await DepartureService().get_recent_departures(
            db=db_session, from_station=SUBURBAN, data_sources=["SEPTA_RR"]
        )
        board = [d.train_id for d in response.departures]
        assert board == ["NOR4252"], (
            "Recently-departed board at Suburban Station must not list "
            f"AIR4252, which arrived and ended there (issue #1882). Board: {board}"
        )

    async def test_unsequenced_njt_terminating_row_kept(self, db_session: AsyncSession):
        """NJT discovery/schedule rows carry NULL stop_sequence, so their stop
        list can't prove the board station is the last stop — they stay listed
        (terminal_stop_index's deliberate safe default), while the same train
        once fully sequenced is filtered."""
        base = now_et() + timedelta(minutes=10)
        unsequenced = _journey(
            train_id="7256",
            data_source="NJT",
            stops=[
                ("TR", None, base - timedelta(minutes=60)),
                ("NY", None, base),
            ],
            terminal="NY",
            destination="New York Penn Station",
        )
        sequenced = _journey(
            train_id="7258",
            data_source="NJT",
            stops=[
                ("TR", 1, base - timedelta(minutes=50)),
                ("NY", 2, base + timedelta(minutes=10)),
            ],
            terminal="NY",
            destination="New York Penn Station",
        )
        db_session.add_all([unsequenced, sequenced])
        await db_session.commit()

        board = await _board(db_session, "NY", "NJT")
        assert board == ["7256"], (
            "Unsequenced 7256 must stay (unprovable terminal); fully sequenced "
            f"7258 terminates at NY and must be dropped. Board: {board}"
        )


# --- Static GTFS ----------------------------------------------------------

GTFS_TERMINAL = "SEPR90005"
GTFS_NEXT = "SEPR90006"
GTFS_PREVIOUS = "SEPR90004"
# More terminating trips than _query_departures_for_source's 250-row cap, all
# earlier than the departing ones: unfiltered in SQL they would fill the cap.
TERMINATING_TRIPS = 260
DEPARTING_TRIPS = 3


def _clock(total_minutes: int) -> str:
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}:00"


async def _seed_terminal_station(db: AsyncSession, service_date: date) -> None:
    route = GTFSRoute(
        data_source="SEPTA_RR",
        route_id="AIR",
        route_short_name="AIR",
        route_long_name="Airport",
        route_color="91456C",
    )
    db.add(route)
    await db.flush()
    db.add(
        GTFSCalendar(
            data_source="SEPTA_RR",
            service_id="EVERYDAY",
            monday=True,
            tuesday=True,
            wednesday=True,
            thursday=True,
            friday=True,
            saturday=True,
            sunday=True,
            start_date=service_date - timedelta(days=1),
            end_date=service_date + timedelta(days=1),
        )
    )

    # (trip, first stop, second stop, minute at the board station)
    trips: list[tuple[GTFSTrip, str, str, int]] = []
    for index in range(TERMINATING_TRIPS):
        trips.append(
            (
                GTFSTrip(
                    data_source="SEPTA_RR",
                    trip_id=f"IN-{index}",
                    route_id=route.id,
                    service_id="EVERYDAY",
                    trip_headsign="Center City Philadelphia",
                    train_id=f"IN{index}",
                    direction_id=1,
                ),
                GTFS_PREVIOUS,
                GTFS_TERMINAL,
                5 * 60 + index * 2,
            )
        )
    for index in range(DEPARTING_TRIPS):
        trips.append(
            (
                GTFSTrip(
                    data_source="SEPTA_RR",
                    trip_id=f"OUT-{index}",
                    route_id=route.id,
                    service_id="EVERYDAY",
                    trip_headsign="Conshohocken",
                    train_id=f"OUT{index}",
                    direction_id=0,
                ),
                GTFS_TERMINAL,
                GTFS_NEXT,
                20 * 60 + index * 10,
            )
        )
    db.add_all(trip for trip, *_ in trips)
    await db.flush()

    stop_times: list[GTFSStopTime] = []
    for trip, first, second, board_minute in trips:
        # The board station is the second stop of an inbound trip and the
        # first of an outbound one; the other stop is 3 minutes away.
        if second == GTFS_TERMINAL:
            first_minute, second_minute = board_minute - 3, board_minute
        else:
            first_minute, second_minute = board_minute, board_minute + 3
        for sequence, (code, minute) in enumerate(
            [(first, first_minute), (second, second_minute)], start=1
        ):
            stop_times.append(
                GTFSStopTime(
                    trip_id=trip.id,
                    stop_sequence=sequence,
                    gtfs_stop_id=code,
                    station_code=code,
                    arrival_time=_clock(minute),
                    departure_time=_clock(minute),
                )
            )
    db.add_all(stop_times)
    await db.flush()


@pytest.mark.asyncio
async def test_gtfs_board_excludes_terminating_trips_before_cap(
    db_session: AsyncSession,
) -> None:
    service_date = date(2026, 7, 23)
    fixed_now = ET.localize(datetime.combine(service_date - timedelta(days=1), time(9)))
    GTFSService._service_id_cache.clear()
    await _seed_terminal_station(db_session, service_date)

    service = DepartureService()
    with patch("trackrat.services.departure.now_et", return_value=fixed_now):
        board = await service.get_departures(
            db_session,
            GTFS_TERMINAL,
            None,
            date=service_date,
            limit=50,
            data_sources=["SEPTA_RR"],
        )
        upstream = await service.get_departures(
            db_session,
            GTFS_PREVIOUS,
            GTFS_TERMINAL,
            date=service_date,
            limit=2,
            data_sources=["SEPTA_RR"],
        )

    train_ids = [d.train_id for d in board.departures]
    assert train_ids == ["OUT0", "OUT1", "OUT2"], (
        f"{TERMINATING_TRIPS} trips end at {GTFS_TERMINAL} before any departs; "
        "the board must list only the departing trips — not the arrivals, and "
        "not an empty board because arrivals filled the 250-row cap "
        f"(issue #1882). Board ({len(train_ids)} rows): {train_ids[:10]}"
    )
    assert [d.train_id for d in upstream.departures] == ["IN0", "IN1"], (
        "A from+to GTFS search ending at the terminating trips' last stop must "
        f"still return them; got {[d.train_id for d in upstream.departures]}"
    )
