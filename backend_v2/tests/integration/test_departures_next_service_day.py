"""Regression for issue #1997: tonight's trips filed under tomorrow's service.

LIRR's static GTFS files its after-midnight eastbound Penn Station trips under
the *next* service date with times like ``00:24:00``, not under today as
``24:24:00`` (confirmed against the live feed: today's service ends Penn →
Jamaica at 23:57, tomorrow's begins 00:10). The same-day GTFS merge in
``DepartureService.get_departures`` only queried today's active services, so
the board — and trip-search leg 2, which reuses it — stopped at the last
pre-midnight train even though the window runs to 02:00 tomorrow.

The merge now also reads the next service day, up to
``NEXT_SERVICE_DAY_OVERLAP`` past midnight (and never beyond ``time_to``).
"""

from datetime import date, datetime, time, timedelta
from unittest.mock import patch

import pytest

from trackrat.models.database import (
    GTFSCalendar,
    GTFSRoute,
    GTFSStopTime,
    GTFSTrip,
)
from trackrat.services.departure import DepartureService
from trackrat.services.gtfs import GTFSService
from trackrat.utils.time import ET

TODAY = date(2026, 11, 24)
TOMORROW = TODAY + timedelta(days=1)
FROM_CODE = "NY"
TO_CODE = "JAM"

# (train number, service id, GTFS departure time at Penn)
SCHEDULE = [
    ("1001", "TODAY", "22:30:00"),  # tonight, filed under today
    ("1002", "TOMORROW", "00:24:00"),  # tonight after midnight, filed under tomorrow
    ("1003", "TOMORROW", "01:52:00"),  # last train inside the 02:00 overlap
    ("1004", "TOMORROW", "02:30:00"),  # past the overlap: tomorrow's service
    ("1005", "TOMORROW", "06:00:00"),  # tomorrow morning: must stay off tonight
]


def _plus_minutes(gtfs_time: str, minutes: int) -> str:
    h, m, s = (int(part) for part in gtfs_time.split(":"))
    total = h * 60 + m + minutes
    return f"{total // 60:02d}:{total % 60:02d}:{s:02d}"


async def _seed(db) -> None:
    route = GTFSRoute(
        data_source="LIRR",
        route_id="1",
        route_short_name="",
        route_long_name="Babylon Branch",
        route_color="00985F",
    )
    db.add(route)
    for service_id, day in (("TODAY", TODAY), ("TOMORROW", TOMORROW)):
        db.add(
            GTFSCalendar(
                data_source="LIRR",
                service_id=service_id,
                monday=True,
                tuesday=True,
                wednesday=True,
                thursday=True,
                friday=True,
                saturday=True,
                sunday=True,
                start_date=day,
                end_date=day,
            )
        )
    await db.flush()

    for train_number, service_id, dep in SCHEDULE:
        trip = GTFSTrip(
            data_source="LIRR",
            trip_id=f"GO103_26_{train_number}",
            route_id=route.id,
            service_id=service_id,
            trip_headsign="Babylon",
            train_id=train_number,
            direction_id=0,
        )
        db.add(trip)
        await db.flush()
        for seq, code, stop_time in (
            (1, FROM_CODE, dep),
            (2, TO_CODE, _plus_minutes(dep, 20)),
        ):
            db.add(
                GTFSStopTime(
                    trip_id=trip.id,
                    stop_sequence=seq,
                    gtfs_stop_id=code,
                    station_code=code,
                    arrival_time=stop_time,
                    departure_time=stop_time,
                )
            )
    await db.flush()


async def _board(db, now: datetime, time_to: datetime | None = None):
    GTFSService._service_id_cache.clear()
    with patch("trackrat.services.departure.now_et", return_value=now):
        response = await DepartureService().get_departures(
            db,
            from_station=FROM_CODE,
            to_station=TO_CODE,
            time_to=time_to,
            data_sources=["LIRR"],
            limit=50,
        )
    rows = [
        (d.train_id, d.journey_date, d.departure.scheduled_time)
        for d in response.departures
    ]
    print(f"now={now.isoformat()} time_to={time_to} rows={rows}")
    return response.departures


@pytest.mark.asyncio
async def test_tonight_board_includes_trips_filed_under_tomorrow(db_session):
    await _seed(db_session)
    departures = await _board(
        db_session, ET.localize(datetime.combine(TODAY, time(22, 0)))
    )

    assert [d.train_id for d in departures] == ["L1001", "L1002", "L1003"], (
        "Tonight's board must continue past midnight into trips filed under "
        "tomorrow's service, and stop at the 02:00 overlap end"
    )
    after_midnight = departures[1]
    assert after_midnight.journey_date == TOMORROW
    assert after_midnight.departure.scheduled_time == ET.localize(
        datetime.combine(TOMORROW, time(0, 24))
    )
    assert after_midnight.arrival is not None
    assert after_midnight.arrival.scheduled_time == ET.localize(
        datetime.combine(TOMORROW, time(0, 44))
    )


@pytest.mark.asyncio
async def test_next_service_day_respects_shorter_time_to(db_session):
    await _seed(db_session)
    departures = await _board(
        db_session,
        ET.localize(datetime.combine(TODAY, time(22, 0))),
        time_to=ET.localize(datetime.combine(TOMORROW, time(1, 0))),
    )

    assert [d.train_id for d in departures] == [
        "L1001",
        "L1002",
    ], "Next-service-day trips past the caller's time_to must not be merged"


@pytest.mark.asyncio
async def test_board_after_todays_last_trip_is_not_empty(db_session):
    """The issue's symptom: once today's service has run out (22:30 departed),
    the board was empty until morning. It must show the after-midnight trips,
    and still not tomorrow's 02:30 / 06:00 service."""
    await _seed(db_session)
    departures = await _board(
        db_session, ET.localize(datetime.combine(TODAY, time(23, 0)))
    )

    assert [d.train_id for d in departures] == ["L1002", "L1003"]
    assert all(d.journey_date == TOMORROW for d in departures)
