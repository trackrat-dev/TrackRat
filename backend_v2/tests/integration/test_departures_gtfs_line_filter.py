"""Regression coverage for line filters across static GTFS result caps."""

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
from trackrat.utils.time import ET

FROM_CODE = "SEPM416"
TO_CODE = "SEPM2457"
SIBLING_TRIPS = 260
MATCHING_TRIPS = 3


def _clock(total_minutes: int) -> str:
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}:00"


async def _seed_shared_station_schedules(db: AsyncSession, service_date: date) -> None:
    """Seed an early sibling line past the cap, then two requested lines."""
    routes = {
        "B1": GTFSRoute(
            data_source="SEPTA_METRO",
            route_id="B1",
            route_short_name="BSL",
            route_long_name="Broad Street Line",
            route_color="F26100",
        ),
        "L1": GTFSRoute(
            data_source="SEPTA_METRO",
            route_id="L1",
            route_short_name="MFL",
            route_long_name="Market-Frankford Line",
            route_color="0097D6",
        ),
        "B2": GTFSRoute(
            data_source="SEPTA_METRO",
            route_id="B2",
            route_short_name="BSX",
            route_long_name="Broad Street Express",
            route_color="F26100",
        ),
    }
    db.add_all(routes.values())
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
            start_date=service_date - timedelta(days=1),
            end_date=service_date + timedelta(days=1),
        )
    )

    scheduled_trips: list[tuple[GTFSTrip, int]] = []
    for index in range(SIBLING_TRIPS):
        scheduled_trips.append(
            (
                GTFSTrip(
                    data_source="SEPTA_METRO",
                    trip_id=f"B1-sibling-{index}",
                    route_id=routes["B1"].id,
                    service_id="EVERYDAY",
                    trip_headsign="Fern Rock",
                    train_id=f"B1-sibling-{index}",
                    direction_id=0,
                ),
                5 * 60 + index * 2,
            )
        )
    for index in range(MATCHING_TRIPS):
        scheduled_trips.append(
            (
                GTFSTrip(
                    data_source="SEPTA_METRO",
                    trip_id=f"L1-match-{index}",
                    route_id=routes["L1"].id,
                    service_id="EVERYDAY",
                    trip_headsign="Frankford",
                    train_id=f"L1-match-{index}",
                    direction_id=0,
                ),
                20 * 60 + index * 10,
            )
        )
    scheduled_trips.append(
        (
            GTFSTrip(
                data_source="SEPTA_METRO",
                trip_id="B2-match-0",
                route_id=routes["B2"].id,
                service_id="EVERYDAY",
                trip_headsign="Walnut-Locust",
                train_id="B2-match-0",
                direction_id=0,
            ),
            20 * 60 + 5,
        )
    )

    db.add_all(trip for trip, _ in scheduled_trips)
    await db.flush()

    stop_times: list[GTFSStopTime] = []
    for trip, departure_minutes in scheduled_trips:
        departure = _clock(departure_minutes)
        arrival = _clock(departure_minutes + 20)
        stop_times.extend(
            [
                GTFSStopTime(
                    trip_id=trip.id,
                    stop_sequence=1,
                    gtfs_stop_id=FROM_CODE,
                    station_code=FROM_CODE,
                    arrival_time=departure,
                    departure_time=departure,
                ),
                GTFSStopTime(
                    trip_id=trip.id,
                    stop_sequence=2,
                    gtfs_stop_id=TO_CODE,
                    station_code=TO_CODE,
                    arrival_time=arrival,
                    departure_time=arrival,
                ),
            ]
        )
    db.add_all(stop_times)
    await db.flush()


def _observed_journey(
    *, train_id: str, line_code: str, departure: datetime, observed_at: datetime
) -> TrainJourney:
    journey = TrainJourney(
        train_id=train_id,
        journey_date=departure.date(),
        data_source="SEPTA_METRO",
        line_code=line_code,
        line_name=line_code,
        line_color="#0097D6",
        destination="Frankford",
        origin_station_code=FROM_CODE,
        terminal_station_code=TO_CODE,
        scheduled_departure=departure,
        first_seen_at=observed_at - timedelta(minutes=30),
        last_updated_at=observed_at - timedelta(minutes=1),
        has_complete_journey=True,
        update_count=1,
        is_cancelled=False,
        is_completed=False,
        is_expired=False,
    )
    journey.stops = [
        JourneyStop(
            station_code=FROM_CODE,
            station_name=FROM_CODE,
            scheduled_departure=departure,
            stop_sequence=0,
            has_departed_station=False,
        ),
        JourneyStop(
            station_code=TO_CODE,
            station_name=TO_CODE,
            scheduled_arrival=departure + timedelta(minutes=20),
            stop_sequence=1,
            has_departed_station=False,
        ),
    ]
    return journey


@pytest.mark.asyncio
async def test_future_gtfs_line_filter_precedes_source_and_public_limits(
    db_session: AsyncSession,
) -> None:
    service_date = date(2026, 7, 23)
    fixed_now = ET.localize(datetime.combine(service_date - timedelta(days=1), time(9)))
    GTFSService._service_id_cache.clear()
    await _seed_shared_station_schedules(db_session, service_date)

    service = DepartureService()
    with patch("trackrat.services.departure.now_et", return_value=fixed_now):
        requested = await service.get_departures(
            db_session,
            FROM_CODE,
            TO_CODE,
            date=service_date,
            limit=2,
            data_sources=["SEPTA_METRO"],
            line_codes=["SEPTA-L1"],
        )
        multiple = await service.get_departures(
            db_session,
            FROM_CODE,
            TO_CODE,
            date=service_date,
            limit=10,
            data_sources=["SEPTA_METRO"],
            line_codes=["SEPTA-L1", "SEPTA-B2"],
        )
        unfiltered = await service.get_departures(
            db_session,
            FROM_CODE,
            TO_CODE,
            date=service_date,
            limit=2,
            data_sources=["SEPTA_METRO"],
        )

    assert [departure.train_id for departure in requested.departures] == [
        "L1-match-0",
        "L1-match-1",
    ]
    assert [departure.train_id for departure in multiple.departures] == [
        "L1-match-0",
        "B2-match-0",
        "L1-match-1",
        "L1-match-2",
    ]
    assert [departure.line.code for departure in multiple.departures] == [
        "SEPTA-L1",
        "SEPTA-B2",
        "SEPTA-L1",
        "SEPTA-L1",
    ]
    assert [departure.train_id for departure in unfiltered.departures] == [
        "B1-sibling-0",
        "B1-sibling-1",
    ]


@pytest.mark.asyncio
async def test_same_day_line_filter_precedes_merge_cap_and_live_wins_dedup(
    db_session: AsyncSession,
) -> None:
    service_date = date(2026, 7, 22)
    fixed_now = ET.localize(datetime.combine(service_date, time(4, 30)))
    GTFSService._service_id_cache.clear()
    await _seed_shared_station_schedules(db_session, service_date)
    db_session.add_all(
        [
            _observed_journey(
                train_id="L1-match-0",
                line_code="SEPTA-L1",
                departure=ET.localize(datetime.combine(service_date, time(20))),
                observed_at=fixed_now,
            ),
            _observed_journey(
                train_id="B1-live-sibling",
                line_code="SEPTA-B1",
                departure=ET.localize(datetime.combine(service_date, time(5, 1))),
                observed_at=fixed_now,
            ),
        ]
    )
    await db_session.flush()

    service = DepartureService()
    with patch("trackrat.services.departure.now_et", return_value=fixed_now):
        response = await service.get_departures(
            db_session,
            FROM_CODE,
            TO_CODE,
            limit=2,
            data_sources=["SEPTA_METRO"],
            line_codes=["SEPTA-L1"],
        )

    assert [departure.train_id for departure in response.departures] == [
        "L1-match-0",
        "L1-match-1",
    ]
    assert [departure.line.code for departure in response.departures] == [
        "SEPTA-L1",
        "SEPTA-L1",
    ]
    assert response.departures[0].observation_type == "OBSERVED"
    assert response.departures[1].observation_type == "SCHEDULED"
