"""Integration test for issue #1752: one PATH train must yield one journey.

Runs the real GTFS segment-time loader and the real PATH collector against a
live PostgreSQL session.

Each sighting of a train back-calculates its origin departure as the RidePATH
arrival minus the GTFS travel time from the origin, and sightings whose
estimates differ by ``SAME_TRAIN_TOLERANCE_MINUTES`` or more become separate
journeys. Every existing test fed the uniform 3 min/segment fallback against
sightings spaced exactly 3 minutes apart, i.e. zero back-calculation spread, so
none could see what real segment times do. Two defects made one train into two
here:

- Segment times were stored in ``PATH_ROUTE_STOPS`` order (Newark -> WTC) and
  looked up in the train's direction, so every WTC -> Newark lookup missed and
  fell back to 3 min/segment — Journal Square -> Harrison is 11.
- The loader took one arbitrary GTFS trip per route, and PATH's feed lists
  construction variants with multi-minute holds ahead of the regular timetable.

The train below is Newark-bound, off its timetable, and seen at three stations
in one cycle. Under either defect some of its sightings land minutes from the
rest and a second journey is created.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.path.collector import PathCollector
from trackrat.collectors.path.ridepath_client import PathArrival
from trackrat.collectors.path.segment_times import _load_segment_times_from_gtfs
from trackrat.models.database import GTFSRoute, GTFSStopTime, GTFSTrip, TrainJourney
from trackrat.utils.time import normalize_to_et, now_et

NWK_WTC_COLOR = "D93A30"

# Real weekday NWK-WTC trips from PATH's GTFS (service c_71142_b_84435_d_31).
WEEKDAY_TO_NEWARK = [
    ("PWC", "08:04:00"),
    ("PEX", "08:08:00"),
    ("PGR", "08:11:00"),
    ("PJS", "08:15:00"),
    ("PHR", "08:26:00"),
    ("PNK", "08:29:00"),
]
WEEKDAY_TO_WTC = [
    ("PNK", "08:01:00"),
    ("PHR", "08:03:00"),
    ("PJS", "08:14:00"),
    ("PGR", "08:18:00"),
    ("PEX", "08:21:00"),
    ("PWC", "08:26:00"),
]
# Shaped like PATH's "Weekend Construction - 10-min JSQ Holds" service.
CONSTRUCTION_TO_NEWARK = [
    ("PWC", "07:04:00"),
    ("PEX", "07:08:00"),
    ("PGR", "07:11:00"),
    ("PJS", "07:25:00"),
    ("PHR", "07:36:00"),
    ("PNK", "07:39:00"),
]


async def _store_nwk_wtc_gtfs(db_session: AsyncSession) -> None:
    """Store route 862 with the construction trip first, as the feed orders it."""
    route = GTFSRoute(
        data_source="PATH",
        route_id="862",
        route_long_name="Newark - World Trade Center",
    )
    db_session.add(route)
    await db_session.flush()

    trips = [
        ("construction", "JSQ_HOLDS", CONSTRUCTION_TO_NEWARK),
        ("weekday-to-newark", "WEEKDAY", WEEKDAY_TO_NEWARK),
        ("weekday-to-wtc", "WEEKDAY", WEEKDAY_TO_WTC),
        ("weekday-to-newark-2", "WEEKDAY", WEEKDAY_TO_NEWARK),
    ]
    for trip_id, service_id, stop_times in trips:
        trip = GTFSTrip(
            data_source="PATH",
            trip_id=trip_id,
            route_id=route.id,
            service_id=service_id,
        )
        db_session.add(trip)
        await db_session.flush()
        db_session.add_all(
            GTFSStopTime(
                trip_id=trip.id,
                stop_sequence=sequence,
                gtfs_stop_id=station_code,
                station_code=station_code,
                arrival_time=time_str,
                departure_time=time_str,
            )
            for sequence, (station_code, time_str) in enumerate(stop_times, start=1)
        )
    await db_session.flush()


def _newark_bound(station_code: str, arrival_time: datetime) -> PathArrival:
    """A RidePATH prediction for a Newark-bound NWK-WTC train."""
    return PathArrival(
        station_code=station_code,
        headsign="Newark",
        direction="ToNJ",
        minutes_away=max(0, round((arrival_time - now_et()).total_seconds() / 60)),
        arrival_time=arrival_time,
        line_color=NWK_WTC_COLOR,
        last_updated=None,
    )


@pytest.mark.asyncio
async def test_off_schedule_train_seen_at_three_stations_is_one_journey(
    db_session: AsyncSession,
):
    """WTC -> Newark train seen at Grove, JSQ and Harrison creates one journey.

    It left WTC 6.5 minutes ago — between timetable slots, as a delayed train
    does — and runs the real segment times (WTC 4 EXP 3 GRV 4 JSQ 11 HAR), so
    RidePATH predicts it at Grove in 0.5 min, JSQ in 4.5 and Harrison in 15.5.
    Under the 3 min/segment fallback those back-calculate to WTC+1, +2 and +10;
    under the construction trip's 14-minute Grove -> JSQ (a 10-minute hold),
    JSQ and Harrison land at WTC-10. Either way a second journey is created.
    """
    await _store_nwk_wtc_gtfs(db_session)
    segment_times = await _load_segment_times_from_gtfs(db_session)
    print(f"Loaded 862 segment times: {segment_times['862']}")

    left_wtc = now_et() - timedelta(minutes=6, seconds=30)
    arrivals = [
        _newark_bound("PGR", left_wtc + timedelta(minutes=7, seconds=12)),
        _newark_bound("PJS", left_wtc + timedelta(minutes=11, seconds=-20)),
        _newark_bound("PHR", left_wtc + timedelta(minutes=22, seconds=35)),
    ]

    stats = await PathCollector()._discover_trains(db_session, arrivals, segment_times)
    await db_session.commit()

    journeys = list(
        (
            await db_session.scalars(
                select(TrainJourney).where(TrainJourney.data_source == "PATH")
            )
        ).all()
    )
    for journey in journeys:
        print(
            f"journey {journey.train_id}: {journey.origin_station_code} -> "
            f"{journey.terminal_station_code} departs {journey.scheduled_departure}"
        )

    assert stats["new_journeys"] == 1 and len(journeys) == 1, (
        f"One physical train must be one journey; got {len(journeys)} "
        f"({[journey.train_id for journey in journeys]})"
    )
    journey = journeys[0]
    assert (journey.origin_station_code, journey.terminal_station_code) == (
        "PWC",
        "PNK",
    )
    # The Grove sighting is closest to the origin, so it supplies the journey.
    error = (
        normalize_to_et(journey.scheduled_departure) - normalize_to_et(left_wtc)
    ).total_seconds()
    assert abs(error) <= 15, (
        f"Origin departure should be the WTC departure ({left_wtc}), "
        f"got {journey.scheduled_departure} ({error:+.0f}s)"
    )
