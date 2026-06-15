"""Tests for GTFSService.materialize_scheduled_journey (issue #1298).

A Live Activity can be started for a SCHEDULED train that exists only in GTFS
static schedule data (no ``train_journeys`` row until discovery observes it).
The Live Activity push job queries ``train_journeys`` exclusively and has no
GTFS fallback, so without a row it logs ``journey_not_found_for_live_activity``
every cycle and never pushes — the on-device countdown freezes. Materializing a
SCHEDULED row from GTFS at registration lets the push job deliver updates
immediately; discovery later upgrades the same row to OBSERVED in place.
"""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from trackrat.models.database import (
    GTFSCalendar,
    GTFSRoute,
    GTFSStopTime,
    GTFSTrip,
    JourneyStop,
    TrainJourney,
)
from trackrat.services.gtfs import GTFSService

# A weekday with NJT service. Seeded calendar runs every day to stay robust.
TARGET_DATE = date(2026, 6, 15)


async def _seed_njt_gtfs_trip(db, *, train_id: str = "3096") -> GTFSTrip:
    """Seed one NJT GTFS trip (NY -> Trenton) active on TARGET_DATE."""
    route = GTFSRoute(
        data_source="NJT",
        route_id="NEC",
        route_short_name="NEC",
        route_long_name="Northeast Corridor",
        route_color="DD3439",
    )
    db.add(route)
    await db.flush()

    db.add(
        GTFSCalendar(
            data_source="NJT",
            service_id="WKDY",
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

    trip = GTFSTrip(
        data_source="NJT",
        trip_id=f"trip-{train_id}",
        route_id=route.id,
        service_id="WKDY",
        trip_headsign="Trenton",
        train_id=train_id,
        direction_id=0,
    )
    db.add(trip)
    await db.flush()

    for code, seq, clock in [
        ("NY", 1, "15:30:00"),
        ("NP", 2, "15:55:00"),
        ("ED", 3, "16:08:00"),
        ("TR", 4, "16:35:00"),
    ]:
        db.add(
            GTFSStopTime(
                trip_id=trip.id,
                stop_sequence=seq,
                gtfs_stop_id=code,
                station_code=code,
                arrival_time=clock,
                departure_time=clock,
            )
        )
    await db.flush()
    return trip


@pytest.mark.asyncio
async def test_materialize_creates_scheduled_journey_from_gtfs(db_session):
    """A GTFS-only SCHEDULED train gets a real train_journeys row + stops."""
    GTFSService._service_id_cache.clear()
    await _seed_njt_gtfs_trip(db_session)

    journey = await GTFSService().materialize_scheduled_journey(
        db_session, "3096", TARGET_DATE, data_source="NJT"
    )

    assert journey is not None, "expected a journey to be materialized from GTFS"
    assert journey.train_id == "3096"
    assert journey.journey_date == TARGET_DATE
    assert journey.data_source == "NJT"
    assert journey.observation_type == "SCHEDULED"
    # NJT route_short "NEC" maps to API line code "NE".
    assert journey.line_code == "NE"
    assert journey.origin_station_code == "NY"
    assert journey.terminal_station_code == "TR"
    assert journey.scheduled_departure is not None
    assert journey.stops_count == 4

    stops = (
        await db_session.scalars(
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .order_by(JourneyStop.stop_sequence)
        )
    ).all()
    assert [s.station_code for s in stops] == ["NY", "NP", "ED", "TR"]
    assert stops[0].scheduled_departure is not None


@pytest.mark.asyncio
async def test_materialize_is_idempotent(db_session):
    """Calling twice must not create a duplicate row (unique_train_journey)."""
    GTFSService._service_id_cache.clear()
    await _seed_njt_gtfs_trip(db_session)
    service = GTFSService()

    first = await service.materialize_scheduled_journey(
        db_session, "3096", TARGET_DATE, data_source="NJT"
    )
    await db_session.commit()
    second = await service.materialize_scheduled_journey(
        db_session, "3096", TARGET_DATE, data_source="NJT"
    )

    assert first is not None and second is not None
    assert first.id == second.id

    rows = (
        await db_session.scalars(
            select(TrainJourney).where(TrainJourney.train_id == "3096")
        )
    ).all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_materialize_returns_existing_observed_row_without_duplicating(
    db_session,
):
    """If discovery already created a row, return it and do not materialize."""
    GTFSService._service_id_cache.clear()
    await _seed_njt_gtfs_trip(db_session)

    observed = TrainJourney(
        train_id="3096",
        journey_date=TARGET_DATE,
        line_code="NE",
        line_name="Northeast Corridor",
        destination="TRENTON TRANSIT CENTER",
        origin_station_code="NY",
        terminal_station_code="TR",
        data_source="NJT",
        observation_type="OBSERVED",
        scheduled_departure=datetime(2026, 6, 15, 19, 30, tzinfo=UTC),
    )
    db_session.add(observed)
    await db_session.flush()

    result = await GTFSService().materialize_scheduled_journey(
        db_session, "3096", TARGET_DATE, data_source="NJT"
    )

    assert result is not None
    assert result.id == observed.id
    assert result.observation_type == "OBSERVED"

    rows = (
        await db_session.scalars(
            select(TrainJourney).where(TrainJourney.train_id == "3096")
        )
    ).all()
    assert len(rows) == 1
    # No stops should have been added for the GTFS path since the row existed.
    stop_count = len(
        (
            await db_session.scalars(
                select(JourneyStop).where(JourneyStop.journey_id == observed.id)
            )
        ).all()
    )
    assert stop_count == 0


@pytest.mark.asyncio
async def test_materialize_returns_none_when_train_absent_from_gtfs(db_session):
    """A train with no GTFS trip cannot be materialized; returns None gracefully."""
    GTFSService._service_id_cache.clear()
    await _seed_njt_gtfs_trip(db_session)

    journey = await GTFSService().materialize_scheduled_journey(
        db_session, "9999", TARGET_DATE, data_source="NJT"
    )
    assert journey is None
