"""Null-data accounting in the nightly NJT stop-list sweep (issue #1725).

`_collect_stop_lists_for_scheduled_trains` caught everything with one broad
`except Exception`, so a train NJT simply has no stop list for was recorded
identically to a genuine failure: `stop_collections_failed` incremented, a
warning emitted, and a full traceback attached via `exc_info=True`.

That is not a cosmetic distinction. Production ran at a ~20% "failure" rate
every night and 80% on 2026-08-01, which reads as a broken job; in fact every
one of those 304 entries on 08-01 was `NJTransitNullDataError`. The real
failures that night — the handful of deadlocks on the advisory lock — were
buried under 300 tracebacks for a condition nobody can act on.

The upstream condition is also persistent rather than transient: the same
train numbers come back null night after night (116 trains failed on all five
nights of 2026-07-27..07-31), so these tests additionally pin that the
collector does not retry.

Uses a real in-memory SQLite session (same pattern as
test_schedule_stop_collection_expired_attribute.py) so the savepoint and
counter behaviour are genuine rather than asserted against a mock.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
import structlog
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from structlog.testing import LogCapture

from trackrat.collectors.njt.client import NJTransitClient, NJTransitNullDataError
from trackrat.collectors.njt.schedule import NJTScheduleCollector
from trackrat.models.database import Base, TrainJourney
from trackrat.utils.time import now_et


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
    """Create schedule collector with a mocked NJT client."""
    client = AsyncMock(spec=NJTransitClient)
    return NJTScheduleCollector(client)


@pytest.fixture
def log_output():
    """Capture structlog entries, restoring the global config afterwards."""
    captured = LogCapture()
    original = structlog.get_config()
    structlog.configure(processors=[captured])
    yield captured
    structlog.configure(**original)


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
    """train_data whose stop violates station_name NOT NULL, failing flush."""
    bad_stop = MagicMock()
    bad_stop.STATION_2CHAR = "TR"
    bad_stop.STATIONNAME = None
    bad_stop.SCHED_ARR_DATE = None
    bad_stop.SCHED_DEP_DATE = None
    bad_stop.TRACK = None

    train_data = MagicMock()
    train_data.STOPS = [bad_stop]
    return train_data


def _make_train_data_with_valid_stop() -> MagicMock:
    """train_data with one well-formed stop that persists successfully."""
    from tests.fixtures.njt_api_responses import NJT_TIME_FORMAT, StopBuilder

    base = now_et().replace(hour=8, minute=0, second=0, microsecond=0)
    stop = StopBuilder().build_stop(
        station_code="TR",
        station_name="Trenton",
        dep_time=base.strftime(NJT_TIME_FORMAT),
    )
    stop.SCHED_ARR_DATE = None
    stop.SCHED_DEP_DATE = base.strftime(NJT_TIME_FORMAT)
    stop.TRACK = None

    train_data = MagicMock()
    train_data.STOPS = [stop]
    return train_data


def _events(log_output) -> list[str]:
    return [e.get("event") for e in log_output.entries]


class TestNullDataIsCountedSeparately:
    """A train NJT has no data for is not a failure of ours."""

    @pytest.mark.asyncio
    async def test_null_data_does_not_increment_the_failure_counter(
        self, sqlite_session: AsyncSession, schedule_collector
    ):
        """The 80% "failure rate" on 2026-08-01 was entirely this condition."""
        _create_scheduled_journey(sqlite_session, train_id="4687")
        await sqlite_session.flush()

        schedule_collector.client.get_train_stop_list.side_effect = (
            NJTransitNullDataError("Train 4687 - API returned null data")
        )

        stats = await schedule_collector._collect_stop_lists_for_scheduled_trains(
            sqlite_session
        )

        assert stats["stop_collections_attempted"] == 1
        assert (
            stats["stop_collections_no_upstream_data"] == 1
        ), f"null data needs its own counter, got: {stats}"
        assert stats["stop_collections_failed"] == 0, (
            "counting upstream's missing coverage as our failure is what made "
            f"a healthy run look 20-80% broken: {stats}"
        )
        assert stats["stop_collections_successful"] == 0

    @pytest.mark.asyncio
    async def test_null_data_is_logged_without_a_traceback(
        self, sqlite_session: AsyncSession, schedule_collector, log_output
    ):
        """300 tracebacks per night for a non-actionable condition buried the
        genuine errors that occurred alongside them."""
        _create_scheduled_journey(sqlite_session, train_id="4687")
        await sqlite_session.flush()

        schedule_collector.client.get_train_stop_list.side_effect = (
            NJTransitNullDataError("Train 4687 - API returned null data")
        )

        await schedule_collector._collect_stop_lists_for_scheduled_trains(
            sqlite_session
        )

        assert "failed_to_collect_stops_for_scheduled_train" not in _events(
            log_output
        ), f"null data must not be logged as a failure: {_events(log_output)}"
        entries = [
            e
            for e in log_output.entries
            if e.get("event") == "no_upstream_stop_list_for_scheduled_train"
        ]
        assert len(entries) == 1, f"expected one entry, got {_events(log_output)}"
        assert entries[0]["train_id"] == "4687"
        assert (
            entries[0]["log_level"] == "info"
        ), f"not a warning — nobody can act on it: {entries[0]!r}"
        assert (
            "exc_info" not in entries[0]
        ), f"no traceback for a condition with no stack to blame: {entries[0]!r}"

    @pytest.mark.asyncio
    async def test_null_data_train_is_not_retried(
        self, sqlite_session: AsyncSession, schedule_collector
    ):
        """The condition is persistent — the same train numbers return null
        every night — so a retry re-asks a question NJT has no answer to."""
        _create_scheduled_journey(sqlite_session, train_id="4687")
        await sqlite_session.flush()

        schedule_collector.client.get_train_stop_list.side_effect = (
            NJTransitNullDataError("Train 4687 - API returned null data")
        )

        await schedule_collector._collect_stop_lists_for_scheduled_trains(
            sqlite_session
        )

        assert (
            schedule_collector.client.get_train_stop_list.call_count == 1
        ), "one train must cost exactly one upstream call"


class TestGenuineFailuresAreStillReported:
    """The split must not silence real errors — that is the whole point."""

    @pytest.mark.asyncio
    async def test_flush_failure_still_counts_as_a_failure(
        self, sqlite_session: AsyncSession, schedule_collector, log_output
    ):
        """A database error is actionable and must stay a warning with a
        traceback (the #1367 behaviour)."""
        _create_scheduled_journey(sqlite_session, train_id="1234")
        await sqlite_session.flush()

        schedule_collector.client.get_train_stop_list.return_value = (
            _make_train_data_with_invalid_stop()
        )

        stats = await schedule_collector._collect_stop_lists_for_scheduled_trains(
            sqlite_session
        )

        assert (
            stats["stop_collections_failed"] == 1
        ), f"a real failure must still be counted: {stats}"
        assert stats["stop_collections_no_upstream_data"] == 0
        assert "failed_to_collect_stops_for_scheduled_train" in _events(log_output)

    @pytest.mark.asyncio
    async def test_failure_log_never_has_an_empty_error_field(
        self, sqlite_session: AsyncSession, schedule_collector, log_output
    ):
        """An argless exception used to log `error=` with nothing after it."""
        _create_scheduled_journey(sqlite_session, train_id="1234")
        await sqlite_session.flush()

        import httpx

        argless = httpx.ReadTimeout("")
        assert str(argless) == "", "precondition: stringifies empty"
        schedule_collector.client.get_train_stop_list.side_effect = argless

        await schedule_collector._collect_stop_lists_for_scheduled_trains(
            sqlite_session
        )

        entries = [
            e
            for e in log_output.entries
            if e.get("event") == "failed_to_collect_stops_for_scheduled_train"
        ]
        assert len(entries) == 1, f"expected one failure entry: {_events(log_output)}"
        assert entries[0]["error"], f"error field must never be empty: {entries[0]!r}"
        assert "ReadTimeout" in entries[0]["error"]
        assert entries[0]["error_type"] == "ReadTimeout"

    @pytest.mark.asyncio
    async def test_mixed_batch_splits_the_counters_and_keeps_collecting(
        self, sqlite_session: AsyncSession, schedule_collector, log_output
    ):
        """The realistic nightly shape: mostly null data, one real error, and
        the rest fine. Every train must still be attempted."""
        from sqlalchemy import select

        from trackrat.models.database import JourneyStop

        for train_id in ("1000", "2000", "3000"):
            _create_scheduled_journey(sqlite_session, train_id=train_id)
        await sqlite_session.flush()

        # A response with real stops, not an empty one: _update_journey_with_stops
        # early-outs on an empty STOPS list, so an empty "good" response would
        # increment the success counter without ever writing a stop — the very
        # path this test claims to cover.
        good = _make_train_data_with_valid_stop()

        def _respond(train_id):
            if train_id == "1000":
                raise NJTransitNullDataError("Train 1000 - API returned null data")
            if train_id == "2000":
                return _make_train_data_with_invalid_stop()
            return good

        schedule_collector.client.get_train_stop_list.side_effect = _respond

        stats = await schedule_collector._collect_stop_lists_for_scheduled_trains(
            sqlite_session
        )

        assert (
            stats["stop_collections_attempted"] == 3
        ), f"every train must be attempted: {stats}"
        assert stats["stop_collections_no_upstream_data"] == 1, stats
        assert stats["stop_collections_failed"] == 1, stats
        assert stats["stop_collections_successful"] == 1, stats
        # The genuine error is now visible instead of being one warning among
        # hundreds of identical null-data warnings.
        failures = [
            e
            for e in log_output.entries
            if e.get("event") == "failed_to_collect_stops_for_scheduled_train"
        ]
        assert len(failures) == 1, f"exactly one real failure: {_events(log_output)}"
        assert failures[0]["train_id"] == "2000"

        # The healthy train really did get its stop list — otherwise "successful"
        # would only mean "raised no exception".
        stops = (await sqlite_session.execute(select(JourneyStop))).scalars().all()
        assert [s.station_code for s in stops] == ["TR"], (
            "only the healthy train may have persisted a stop, and it must "
            f"actually have one: {[(s.journey_id, s.station_code) for s in stops]}"
        )
