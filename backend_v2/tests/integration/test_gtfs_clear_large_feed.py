"""Regression: GTFS refresh must survive feeds with >32,767 trips.

``GTFSService._clear_existing_data`` used to delete a source's stop_times with
a single ``trip_id IN (<every trip id>)`` — one bind parameter per trip.
asyncpg hard-caps a statement at 32,767 parameters, so for SUBWAY (~82k trips)
and MNR (~35k) the DELETE raised ``InterfaceError: the number of query
arguments cannot exceed 32767`` on every refresh after the initial load (the
initial load succeeds because the tables are empty and there is nothing to
clear). The served static schedule froze until its calendar expired, at which
point ``get_active_service_ids`` returned an empty set and the source
contributed zero scheduled departures anywhere — which is what broke long
intra-subway transfers in trip search (issue #1588).

The failure was also invisible: ``str(exc)`` for the statement error embeds
the full SQL text (~650 KB), and the resulting oversized log entry was dropped
by the logging pipeline instead of ingested. ``_record_refresh_failure`` now
bounds everything it logs or persists.

These tests run against real PostgreSQL, so the parameter limit is genuinely
reachable — without the chunked delete, the first test raises.
"""

from datetime import date

from sqlalchemy import func, insert, select

from trackrat.models.database import (
    GTFSCalendar,
    GTFSCalendarDate,
    GTFSFeedInfo,
    GTFSRoute,
    GTFSStopTime,
    GTFSTrip,
)
from trackrat.services.gtfs import GTFS_ERROR_MESSAGE_MAX_CHARS, GTFSService

# asyncpg's per-statement bind parameter cap; seed comfortably past it.
ASYNCPG_MAX_PARAMS = 32_767
LARGE_TRIP_COUNT = ASYNCPG_MAX_PARAMS + 233  # 33,000


async def _seed_source(
    db, data_source: str, route_pk: int, first_trip_pk: int, trip_count: int
) -> None:
    """Bulk-seed one route, ``trip_count`` trips (one stop_time each), and
    calendar rows for a source, with explicit PKs so the two bulk inserts can
    reference each other without round-trips."""
    await db.execute(
        insert(GTFSRoute).values(
            id=route_pk,
            data_source=data_source,
            route_id=f"{data_source}-R1",
            route_short_name="R1",
            route_long_name=f"{data_source} Test Route",
            route_color="A7A9AC",
        )
    )
    await db.execute(
        insert(GTFSTrip),
        [
            {
                "id": first_trip_pk + i,
                "data_source": data_source,
                "trip_id": f"{data_source}-T{i}",
                "route_id": route_pk,
                "service_id": "WKD",
            }
            for i in range(trip_count)
        ],
    )
    await db.execute(
        insert(GTFSStopTime),
        [
            {
                "trip_id": first_trip_pk + i,
                "stop_sequence": 1,
                "gtfs_stop_id": "X01",
                "station_code": "SL03",
                "arrival_time": "10:00:00",
                "departure_time": "10:00:00",
            }
            for i in range(trip_count)
        ],
    )
    await db.execute(
        insert(GTFSCalendar).values(
            data_source=data_source,
            service_id="WKD",
            monday=True,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
    )
    await db.execute(
        insert(GTFSCalendarDate).values(
            data_source=data_source,
            service_id="WKD",
            date=date(2026, 7, 4),
            exception_type=2,
        )
    )
    await db.commit()


async def _count(db, model, data_source: str) -> int:
    result = await db.execute(
        select(func.count()).select_from(model).where(model.data_source == data_source)
    )
    return result.scalar_one()


async def _count_stop_times(db, data_source: str) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(GTFSStopTime)
        .join(GTFSTrip, GTFSStopTime.trip_id == GTFSTrip.id)
        .where(GTFSTrip.data_source == data_source)
    )
    return result.scalar_one()


async def test_clear_existing_data_handles_over_32767_trips(db_session):
    """Clearing a source with more trips than asyncpg's bind-param cap must
    succeed, and must not touch other sources' rows."""
    await _seed_source(
        db_session, "SUBWAY", route_pk=1, first_trip_pk=1, trip_count=LARGE_TRIP_COUNT
    )
    # A small bystander source proves the clear is scoped by data_source.
    await _seed_source(
        db_session, "LIRR", route_pk=2, first_trip_pk=500_000, trip_count=5
    )

    service = GTFSService()
    # Raises InterfaceError ("cannot exceed 32767") without the chunked delete.
    await service._clear_existing_data(db_session, "SUBWAY")
    await db_session.commit()

    assert await _count(db_session, GTFSTrip, "SUBWAY") == 0
    assert await _count_stop_times(db_session, "SUBWAY") == 0
    assert await _count(db_session, GTFSRoute, "SUBWAY") == 0
    assert await _count(db_session, GTFSCalendar, "SUBWAY") == 0
    assert await _count(db_session, GTFSCalendarDate, "SUBWAY") == 0

    # Bystander source untouched
    assert await _count(db_session, GTFSTrip, "LIRR") == 5
    assert await _count_stop_times(db_session, "LIRR") == 5
    assert await _count(db_session, GTFSRoute, "LIRR") == 1


async def test_record_refresh_failure_bounds_persisted_error(db_session):
    """A giant exception message (the SQL-embedding failure mode) must be
    truncated before it is persisted to feed_info, and the call must report
    failure to refresh_feed."""
    service = GTFSService()
    giant = Exception(
        "the number of query arguments cannot exceed 32767 " + "x" * 700_000
    )

    result = await service._record_refresh_failure(
        db_session, "SUBWAY", "process", giant
    )

    assert result is False
    feed_info = (
        await db_session.execute(
            select(GTFSFeedInfo).where(GTFSFeedInfo.data_source == "SUBWAY")
        )
    ).scalar_one()
    assert feed_info.error_message.startswith("process: the number of query arguments")
    assert "truncated" in feed_info.error_message
    # Bounded well under any log-ingestion entry cap
    assert len(feed_info.error_message) < GTFS_ERROR_MESSAGE_MAX_CHARS + 100
