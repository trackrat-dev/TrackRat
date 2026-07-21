"""Regression: same-day board for a high-frequency, schedule-only source.

SEPTA Broad St / Market-Frankford publish no real-time trip updates, so their
departure board comes entirely from the GTFS-static merge in
``DepartureService.get_departures``. That merge used to pass the query's
default ``time_from`` — today's midnight — straight into
``GTFSService.get_scheduled_departures``. ``_gtfs_time_cutoff`` treats midnight
as "no cutoff", so the per-source query's 250-row ascending cap
(``ORDER BY departure_time ... LIMIT 250``) returned only the earliest trips of
the day. For a line running a train every few minutes those 250 rows are all
morning trips, and the post-merge ``> now`` filter then dropped every one — the
board went empty by mid-afternoon. Real-time lines were masked by OBSERVED
rows; PATCO is low-frequency enough that 250 rows still span the whole day; so
only high-frequency schedule-only lines (SEPTA MFL/BSL) broke.

The fix passes ``max(now, time_from)`` as the SQL floor so the cap lands on
trips around/after "now". This test seeds >250 morning trips plus a handful of
evening trips for a schedule-only source and asserts the evening board is
non-empty (and contains only upcoming trips) at an evening "now". Before the
fix it returns zero departures.
"""

from datetime import date, datetime, time
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

# The seeded "now" and the service's today() both land on this date.
SERVICE_DATE = date(2026, 6, 15)
FROM_CODE = "SEPM416"  # 69th St Transit Center (Market-Frankford west terminal)
TO_CODE = "SEPM2457"  # 8th-Market (downstream on the same line)

# The per-source GTFS query caps at 250 stop_times (gtfs._query_departures_for_
# source). Seed comfortably past the cap with morning trips so, without the SQL
# floor, the cap is exhausted before "now" and no evening trip is fetched.
MORNING_TRIPS = 260
EVENING_TRIPS = 5


def _clock(total_minutes: int) -> str:
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}:00"


async def _seed_high_frequency_schedule_only(db) -> None:
    """Seed a schedule-only SEPTA_METRO line: many morning trips + a few evening.

    Every trip stops at FROM_CODE (seq 1) then TO_CODE (seq 2) so the route
    query returns it. Morning trips run 05:00 onward at 2-minute headways and
    all fall before the evening block, so the 250-row ascending cap is filled
    entirely by morning trips.
    """
    route = GTFSRoute(
        data_source="SEPTA_METRO",
        route_id="L1",
        route_short_name="MFL",
        route_long_name="Market-Frankford Line",
        route_color="0097D6",
    )
    db.add(route)
    await db.flush()

    db.add(
        GTFSCalendar(
            data_source="SEPTA_METRO",
            service_id="EVERYDAY",
            monday=True,
            tuesday=True,
            wednesday=True,
            thursday=True,
            friday=True,
            saturday=True,
            sunday=True,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
    )
    await db.flush()

    schedule: list[tuple[str, int]] = []
    for i in range(MORNING_TRIPS):
        schedule.append((f"m{i}", 5 * 60 + i * 2))  # 05:00 .. 13:38
    for i in range(EVENING_TRIPS):
        schedule.append((f"e{i}", 20 * 60 + i * 10))  # 20:00 .. 20:40

    trips: list[tuple[GTFSTrip, int]] = []
    for tag, dep_minutes in schedule:
        trip = GTFSTrip(
            data_source="SEPTA_METRO",
            trip_id=f"L1-{tag}",
            route_id=route.id,
            service_id="EVERYDAY",
            trip_headsign="Frankford",
            train_id=f"L1-{tag}",
            direction_id=0,
        )
        db.add(trip)
        trips.append((trip, dep_minutes))
    await db.flush()

    for trip, dep_minutes in trips:
        dep = _clock(dep_minutes)
        arr = _clock(dep_minutes + 20)
        db.add(
            GTFSStopTime(
                trip_id=trip.id,
                stop_sequence=1,
                gtfs_stop_id=FROM_CODE,
                station_code=FROM_CODE,
                arrival_time=dep,
                departure_time=dep,
            )
        )
        db.add(
            GTFSStopTime(
                trip_id=trip.id,
                stop_sequence=2,
                gtfs_stop_id=TO_CODE,
                station_code=TO_CODE,
                arrival_time=arr,
                departure_time=arr,
            )
        )
    await db.flush()


@pytest.mark.asyncio
async def test_schedule_only_high_frequency_board_not_truncated(db_session):
    """Evening board for a schedule-only high-frequency line must not be empty."""
    GTFSService._service_id_cache.clear()
    await _seed_high_frequency_schedule_only(db_session)

    fixed_now = ET.localize(datetime.combine(SERVICE_DATE, time(19, 30)))
    service = DepartureService()
    with patch("trackrat.services.departure.now_et", return_value=fixed_now):
        response = await service.get_departures(
            db_session,
            from_station=FROM_CODE,
            to_station=TO_CODE,
            data_sources=["SEPTA_METRO"],
            limit=50,
        )

    scheduled_times = sorted(
        d.departure.scheduled_time
        for d in response.departures
        if d.departure.scheduled_time
    )

    assert response.departures, (
        "schedule-only high-frequency board is empty at 19:30 — the 250-row "
        "GTFS cap truncated to morning trips and the > now filter dropped them"
    )
    # Only upcoming (evening) trips should survive — no morning leftovers.
    assert all(
        t > fixed_now for t in scheduled_times
    ), f"expected only post-19:30 departures, got {[t.isoformat() for t in scheduled_times]}"
    # All EVENING_TRIPS (20:00–20:40) are returned; the cap no longer hides them.
    assert (
        len(response.departures) == EVENING_TRIPS
    ), f"expected {EVENING_TRIPS} evening departures, got {len(response.departures)}"
    assert scheduled_times[0].hour == 20
