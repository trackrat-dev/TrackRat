"""
Unit tests for NJT schedule collector's scheduled_departure handling.

Validates that _process_schedule_item() does not overwrite an existing
journey's scheduled_departure with a later time when the same train appears
in multiple stations' schedules.

NJT lists the same train in every stop-station's schedule. Without the
earliest-wins guard, whichever station was processed last (often the
terminus, with arrival-time-as-SCHED_DEP_DATE) would clobber the actual
origin departure, leaving the journey row inconsistent with stops[0] and
breaking _is_same_journey() in the journey collector — observable as
~550 NJT trains/day stuck in is_expired flap loops.
"""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.schedule import NJTScheduleCollector
from trackrat.models.database import Base, TrainJourney
from trackrat.utils.time import now_et


# Reuses the same SQLite-in-memory pattern as test_schedule_duplicate_stops.py
@pytest.fixture
async def sqlite_engine():
    """Create an in-memory SQLite engine for testing."""
    import pytz
    from sqlalchemy import DateTime as SADateTime, TypeDecorator

    _ET = pytz.timezone("America/New_York")

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    class TZDateTime(TypeDecorator):
        impl = SADateTime
        cache_ok = True

        def process_bind_param(self, value, dialect):
            return value

        def process_result_value(self, value, dialect):
            if value is not None:
                return _ET.localize(value)
            return value

    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, SADateTime) and column.type.timezone:
                column.type = TZDateTime()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, TZDateTime):
                column.type = SADateTime(timezone=True)

    await engine.dispose()


@pytest.fixture
async def sqlite_session(sqlite_engine) -> AsyncSession:
    session_factory = async_sessionmaker(
        sqlite_engine, expire_on_commit=False, class_=AsyncSession
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
def schedule_collector():
    client = AsyncMock(spec=NJTransitClient)
    return NJTScheduleCollector(client)


def _make_item(train_id: str, dep_str: str, destination: str = "Trenton") -> dict:
    """Build a minimal NJT schedule API item."""
    return {
        "TRAIN_ID": train_id,
        "SCHED_DEP_DATE": dep_str,
        "DESTINATION": destination,
        "LINE": "Northeast Corridor",
        "TRACK": None,
    }


class TestEarliestDepartureWins:
    """Once a SCHEDULED journey exists, only earlier scheduled_departure values overwrite it."""

    @pytest.mark.asyncio
    async def test_later_station_does_not_overwrite_earlier_origin(
        self, sqlite_session: AsyncSession, schedule_collector
    ):
        """
        Process the same train at NY (origin, 21:35) then at TR (terminus, 23:05).
        After both passes the journey's scheduled_departure must still be 21:35.
        Today, without the guard, TR would clobber NY because it's processed
        later in the schedule_data iteration — exactly the production bug.
        """
        journey_date = now_et().date()
        ny_dep = now_et().replace(hour=21, minute=35, second=0, microsecond=0)
        tr_dep = ny_dep + timedelta(minutes=90)  # 23:05 — TR-side time

        ny_item = _make_item("3889", ny_dep.strftime("%d-%b-%Y %I:%M:%S %p"))
        tr_item = _make_item("3889", tr_dep.strftime("%d-%b-%Y %I:%M:%S %p"))

        # First pass: NY's schedule creates the journey
        result = await schedule_collector._process_schedule_item(
            sqlite_session, ny_item, "NY", "New York Penn Station", journey_date
        )
        assert result == "new"
        await sqlite_session.flush()

        # Second pass: TR's schedule sees the existing journey
        result = await schedule_collector._process_schedule_item(
            sqlite_session, tr_item, "TR", "Trenton", journey_date
        )
        assert result == "updated"
        await sqlite_session.flush()

        # Origin departure must survive
        journey = await sqlite_session.scalar(
            select(TrainJourney).where(TrainJourney.train_id == "3889")
        )
        assert journey is not None
        assert journey.scheduled_departure == ny_dep, (
            f"scheduled_departure was clobbered by the later station: "
            f"got {journey.scheduled_departure}, expected {ny_dep}"
        )

    @pytest.mark.asyncio
    async def test_earlier_station_does_overwrite_later(
        self, sqlite_session: AsyncSession, schedule_collector
    ):
        """
        Inverse of the above: if a journey was first seen at TR (terminus
        time stored), and NY's schedule is processed afterwards, the earlier
        NY time must replace it. Without this, journeys accidentally created
        from a non-origin station would never converge to the real origin.
        """
        journey_date = now_et().date()
        ny_dep = now_et().replace(hour=21, minute=35, second=0, microsecond=0)
        tr_dep = ny_dep + timedelta(minutes=90)

        tr_item = _make_item("3889", tr_dep.strftime("%d-%b-%Y %I:%M:%S %p"))
        ny_item = _make_item("3889", ny_dep.strftime("%d-%b-%Y %I:%M:%S %p"))

        # TR processed first (creates journey with tr_dep)
        await schedule_collector._process_schedule_item(
            sqlite_session, tr_item, "TR", "Trenton", journey_date
        )
        await sqlite_session.flush()

        # NY processed second (should overwrite to earlier time)
        await schedule_collector._process_schedule_item(
            sqlite_session, ny_item, "NY", "New York Penn Station", journey_date
        )
        await sqlite_session.flush()

        journey = await sqlite_session.scalar(
            select(TrainJourney).where(TrainJourney.train_id == "3889")
        )
        assert journey is not None
        assert journey.scheduled_departure == ny_dep, (
            f"Earlier station's time should overwrite the later one: "
            f"got {journey.scheduled_departure}, expected {ny_dep}"
        )

    @pytest.mark.asyncio
    async def test_observed_journey_not_touched(
        self, sqlite_session: AsyncSession, schedule_collector
    ):
        """
        Once a journey is OBSERVED, schedule processing must not touch
        scheduled_departure regardless of the new value. This pre-existing
        behaviour is preserved by the early `return "skipped"` and is asserted
        here so the earliest-wins guard does not accidentally subvert it.
        """
        journey_date = now_et().date()
        observed_dep = now_et().replace(hour=21, minute=35, second=0, microsecond=0)
        earlier_dep = observed_dep - timedelta(minutes=30)

        # Pre-create an OBSERVED journey
        journey = TrainJourney(
            train_id="3889",
            journey_date=journey_date,
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            observation_type="OBSERVED",
            scheduled_departure=observed_dep,
            is_cancelled=False,
            is_expired=False,
            is_completed=False,
            has_complete_journey=False,
            stops_count=0,
            update_count=1,
        )
        sqlite_session.add(journey)
        await sqlite_session.flush()

        item = _make_item("3889", earlier_dep.strftime("%d-%b-%Y %I:%M:%S %p"))
        result = await schedule_collector._process_schedule_item(
            sqlite_session, item, "NY", "New York Penn Station", journey_date
        )
        assert result == "skipped"

        refreshed = await sqlite_session.scalar(
            select(TrainJourney).where(TrainJourney.train_id == "3889")
        )
        assert (
            refreshed.scheduled_departure == observed_dep
        ), "OBSERVED journey's scheduled_departure must be left alone"
