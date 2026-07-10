"""
Unit tests for issue #1367: expired ORM attribute read in the exception
handler of _collect_stop_lists_for_scheduled_trains aborts the entire
stop-list collection loop.

When _update_journey_with_stops() fails inside the per-train
session.begin_nested() savepoint, the savepoint rollback expires the
`journey` ORM object's attributes. Reading journey.train_id afterward
in the except handler forces a synchronous lazy-refresh on the async
session, raising MissingGreenlet -- which escapes the per-train except
and kills every subsequent train in the batch.

Uses a real in-memory SQLite session (not a mocked one) so the savepoint
rollback and attribute expiration are genuine, reproducing the actual
failure mode instead of just asserting mocked call arguments.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.schedule import NJTScheduleCollector
from trackrat.models.database import Base, TrainJourney
from trackrat.utils.time import now_et

# ---------------------------------------------------------------------------
# SQLite in-memory fixtures (same pattern as test_schedule_duplicate_stops.py)
# ---------------------------------------------------------------------------


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
    """Create an async session bound to the in-memory SQLite engine."""
    session_factory = async_sessionmaker(
        sqlite_engine, expire_on_commit=False, class_=AsyncSession
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
def schedule_collector():
    """Create schedule collector with mocked client."""
    client = AsyncMock(spec=NJTransitClient)
    return NJTScheduleCollector(client)


def _create_scheduled_journey(session: AsyncSession, train_id: str) -> TrainJourney:
    """Create a minimal SCHEDULED journey needing stop-list collection."""
    journey = TrainJourney(
        train_id=train_id,
        journey_date=now_et().date(),
        line_code="NE",
        line_name="Northeast Corridor",
        destination="TRENTON",
        origin_station_code="NY",
        terminal_station_code="TR",
        data_source="NJT",
        observation_type="SCHEDULED",
        scheduled_departure=now_et().replace(hour=8, minute=0, second=0, microsecond=0),
        has_complete_journey=False,
        is_cancelled=False,
        is_expired=False,
        is_completed=False,
    )
    session.add(journey)
    return journey


def _make_train_data_with_invalid_stop() -> MagicMock:
    """Build train_data whose stop list violates the station_name NOT NULL
    constraint, forcing session.flush() to fail inside the savepoint."""
    bad_stop = MagicMock()
    bad_stop.STATION_2CHAR = "TR"
    bad_stop.STATIONNAME = None  # journey_stops.station_name is NOT NULL
    bad_stop.SCHED_ARR_DATE = None
    bad_stop.SCHED_DEP_DATE = None
    bad_stop.TRACK = None

    train_data = MagicMock()
    train_data.STOPS = [bad_stop]
    return train_data


class TestStopCollectionSurvivesFlushFailure:
    """Verify a per-train flush failure doesn't kill the whole batch."""

    @pytest.mark.asyncio
    async def test_flush_failure_is_logged_and_loop_continues(
        self, sqlite_session: AsyncSession, schedule_collector
    ):
        """Reproduces issue #1367: a flush failure inside the per-train
        savepoint used to raise MissingGreenlet from the except handler
        (reading the now-expired journey.train_id), aborting the entire
        collection loop instead of being recorded as a single failure."""
        _create_scheduled_journey(sqlite_session, train_id="1234")
        await sqlite_session.flush()

        schedule_collector.client.get_train_stop_list.return_value = (
            _make_train_data_with_invalid_stop()
        )

        stats = await schedule_collector._collect_stop_lists_for_scheduled_trains(
            sqlite_session
        )

        assert stats["stop_collections_attempted"] == 1
        assert stats["stop_collections_failed"] == 1
        assert stats["stop_collections_successful"] == 0

    @pytest.mark.asyncio
    async def test_later_trains_still_collected_after_earlier_failure(
        self, sqlite_session: AsyncSession, schedule_collector
    ):
        """A flush failure on one train must not prevent the next train
        in the same batch from being collected successfully."""
        _create_scheduled_journey(sqlite_session, train_id="1234")
        _create_scheduled_journey(sqlite_session, train_id="5678")
        await sqlite_session.flush()

        from tests.fixtures.njt_api_responses import NJT_TIME_FORMAT, StopBuilder

        base = now_et().replace(hour=8, minute=0, second=0, microsecond=0)
        builder = StopBuilder()
        good_stop = builder.build_stop(
            station_code="TR",
            station_name="Trenton",
            dep_time=base.strftime(NJT_TIME_FORMAT),
        )
        good_stop.SCHED_ARR_DATE = None
        good_stop.SCHED_DEP_DATE = base.strftime(NJT_TIME_FORMAT)
        good_stop.TRACK = None
        good_train_data = MagicMock()
        good_train_data.STOPS = [good_stop]

        # First call (train 1234) returns bad data and fails; second call
        # (train 5678) returns good data and should still succeed.
        schedule_collector.client.get_train_stop_list.side_effect = [
            _make_train_data_with_invalid_stop(),
            good_train_data,
        ]

        stats = await schedule_collector._collect_stop_lists_for_scheduled_trains(
            sqlite_session
        )

        assert stats["stop_collections_attempted"] == 2
        assert stats["stop_collections_failed"] == 1
        assert stats["stop_collections_successful"] == 1
