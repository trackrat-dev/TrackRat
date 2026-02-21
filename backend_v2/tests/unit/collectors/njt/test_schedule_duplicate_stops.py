"""
Unit tests for NJT schedule collector duplicate station deduplication.

Validates that _update_journey_with_stops() correctly handles the NJT API
returning duplicate station codes in a train's stop list. Without dedup,
the unique_journey_stop constraint on (journey_id, station_code) causes
an IntegrityError.

Uses an in-memory SQLite database (same pattern as test_journey_data_quality.py).
"""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.schedule import NJTScheduleCollector
from trackrat.models.database import Base, JourneyStop, TrainJourney
from trackrat.utils.time import now_et

from tests.fixtures.njt_api_responses import NJT_TIME_FORMAT, StopBuilder

# ---------------------------------------------------------------------------
# SQLite in-memory fixtures (same pattern as test_journey_data_quality.py)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_train_data_with_stops(stops: list[MagicMock]) -> MagicMock:
    """Build a mock train_data object matching NJT API schedule response."""
    train_data = MagicMock()
    train_data.STOPS = stops
    return train_data


def _build_stop_with_sched_times(
    station_code: str,
    station_name: str,
    dep_time_str: str,
    arr_time_str: str | None = None,
) -> MagicMock:
    """Build a stop mock with SCHED_ARR_DATE and SCHED_DEP_DATE set."""
    builder = StopBuilder()
    stop = builder.build_stop(
        station_code=station_code,
        station_name=station_name,
        dep_time=dep_time_str,
        arr_time=arr_time_str,
    )
    stop.SCHED_ARR_DATE = arr_time_str
    stop.SCHED_DEP_DATE = dep_time_str
    stop.TRACK = None
    return stop


def _create_journey(session: AsyncSession) -> TrainJourney:
    """Create a minimal journey record for testing."""
    journey = TrainJourney(
        train_id="1061",
        journey_date=now_et().date(),
        line_code="ME",
        line_name="Morris & Essex",
        destination="MOUNT OLIVE",
        origin_station_code="NY",
        terminal_station_code="OL",
        data_source="NJT",
        observation_type="SCHEDULED",
        scheduled_departure=now_et().replace(hour=8, minute=0, second=0, microsecond=0),
        is_cancelled=False,
        is_expired=False,
        is_completed=False,
    )
    session.add(journey)
    return journey


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestScheduleCollectorDuplicateStops:
    """Verify _update_journey_with_stops deduplicates station codes."""

    @pytest.mark.asyncio
    async def test_duplicate_station_code_does_not_raise(
        self, sqlite_session: AsyncSession, schedule_collector
    ):
        """When NJT API returns the same station code twice, the schedule
        collector should deduplicate before inserting, avoiding
        IntegrityError on the unique_journey_stop constraint.

        This reproduces the production bug: train 1061 with station OL
        appearing twice in the stop list."""
        journey = _create_journey(sqlite_session)
        await sqlite_session.flush()

        base = now_et().replace(hour=8, minute=0, second=0, microsecond=0)

        stops = [
            _build_stop_with_sched_times(
                "NY", "New York", (base).strftime(NJT_TIME_FORMAT)
            ),
            _build_stop_with_sched_times(
                "NP",
                "Newark Penn",
                (base + timedelta(minutes=15)).strftime(NJT_TIME_FORMAT),
                arr_time_str=(base + timedelta(minutes=14)).strftime(NJT_TIME_FORMAT),
            ),
            _build_stop_with_sched_times(
                "OL",
                "Mount Olive",
                (base + timedelta(minutes=60)).strftime(NJT_TIME_FORMAT),
                arr_time_str=(base + timedelta(minutes=59)).strftime(NJT_TIME_FORMAT),
            ),
            # Duplicate OL -- this is what NJT API sometimes returns
            _build_stop_with_sched_times(
                "OL",
                "Mount Olive",
                (base + timedelta(minutes=62)).strftime(NJT_TIME_FORMAT),
                arr_time_str=(base + timedelta(minutes=61)).strftime(NJT_TIME_FORMAT),
            ),
        ]

        train_data = _make_train_data_with_stops(stops)

        # Before the fix, this would raise IntegrityError
        await schedule_collector._update_journey_with_stops(
            sqlite_session, journey, train_data
        )
        await sqlite_session.flush()

        # Verify only 3 stops inserted (duplicate OL filtered out)
        result = await sqlite_session.execute(
            select(JourneyStop).where(JourneyStop.journey_id == journey.id)
        )
        inserted_stops = result.scalars().all()

        assert len(inserted_stops) == 3, (
            f"Expected 3 stops after dedup (NY, NP, OL), got {len(inserted_stops)}: "
            f"{[s.station_code for s in inserted_stops]}"
        )

        station_codes = [s.station_code for s in inserted_stops]
        assert (
            station_codes.count("OL") == 1
        ), f"Expected exactly 1 OL stop after dedup, got {station_codes.count('OL')}"

    @pytest.mark.asyncio
    async def test_duplicate_dedup_keeps_first_occurrence(
        self, sqlite_session: AsyncSession, schedule_collector
    ):
        """When deduplicating, the first occurrence's data should be kept
        (matching journey.py behavior)."""
        journey = _create_journey(sqlite_session)
        await sqlite_session.flush()

        base = now_et().replace(hour=8, minute=0, second=0, microsecond=0)
        first_time = (base + timedelta(minutes=60)).strftime(NJT_TIME_FORMAT)
        second_time = (base + timedelta(minutes=62)).strftime(NJT_TIME_FORMAT)

        stops = [
            _build_stop_with_sched_times(
                "NY", "New York", base.strftime(NJT_TIME_FORMAT)
            ),
            _build_stop_with_sched_times(
                "OL", "Mount Olive", first_time, arr_time_str=first_time
            ),
            _build_stop_with_sched_times(
                "OL", "Mount Olive", second_time, arr_time_str=second_time
            ),
        ]

        train_data = _make_train_data_with_stops(stops)

        await schedule_collector._update_journey_with_stops(
            sqlite_session, journey, train_data
        )
        await sqlite_session.flush()

        result = await sqlite_session.execute(
            select(JourneyStop)
            .where(JourneyStop.journey_id == journey.id)
            .where(JourneyStop.station_code == "OL")
        )
        ol_stop = result.scalar_one()

        from trackrat.utils.time import parse_njt_time

        expected_dep = parse_njt_time(first_time)
        assert ol_stop.scheduled_departure == expected_dep, (
            f"Expected first occurrence's departure time {expected_dep}, "
            f"got {ol_stop.scheduled_departure} -- dedup should keep the first stop"
        )

    @pytest.mark.asyncio
    async def test_no_duplicates_works_normally(
        self, sqlite_session: AsyncSession, schedule_collector
    ):
        """Normal case with no duplicate stations should work unchanged."""
        journey = _create_journey(sqlite_session)
        await sqlite_session.flush()

        base = now_et().replace(hour=8, minute=0, second=0, microsecond=0)

        stops = [
            _build_stop_with_sched_times(
                "NY", "New York", base.strftime(NJT_TIME_FORMAT)
            ),
            _build_stop_with_sched_times(
                "NP",
                "Newark Penn",
                (base + timedelta(minutes=15)).strftime(NJT_TIME_FORMAT),
                arr_time_str=(base + timedelta(minutes=14)).strftime(NJT_TIME_FORMAT),
            ),
            _build_stop_with_sched_times(
                "OL",
                "Mount Olive",
                (base + timedelta(minutes=60)).strftime(NJT_TIME_FORMAT),
                arr_time_str=(base + timedelta(minutes=59)).strftime(NJT_TIME_FORMAT),
            ),
        ]

        train_data = _make_train_data_with_stops(stops)

        await schedule_collector._update_journey_with_stops(
            sqlite_session, journey, train_data
        )
        await sqlite_session.flush()

        result = await sqlite_session.execute(
            select(JourneyStop).where(JourneyStop.journey_id == journey.id)
        )
        inserted_stops = result.scalars().all()

        assert (
            len(inserted_stops) == 3
        ), f"Expected 3 stops (no dedup needed), got {len(inserted_stops)}"

        # Verify journey metadata was updated correctly
        assert journey.has_complete_journey is True
        assert journey.stops_count == 3
        assert journey.origin_station_code == "NY"
        assert journey.terminal_station_code == "OL"

    @pytest.mark.asyncio
    async def test_journey_metadata_correct_after_dedup(
        self, sqlite_session: AsyncSession, schedule_collector
    ):
        """Journey metadata (stops_count, origin, terminal) should reflect
        the deduplicated stop list, not the raw API response."""
        journey = _create_journey(sqlite_session)
        await sqlite_session.flush()

        base = now_et().replace(hour=8, minute=0, second=0, microsecond=0)

        stops = [
            _build_stop_with_sched_times(
                "NY", "New York", base.strftime(NJT_TIME_FORMAT)
            ),
            _build_stop_with_sched_times(
                "NP",
                "Newark Penn",
                (base + timedelta(minutes=15)).strftime(NJT_TIME_FORMAT),
                arr_time_str=(base + timedelta(minutes=14)).strftime(NJT_TIME_FORMAT),
            ),
            _build_stop_with_sched_times(
                "OL",
                "Mount Olive",
                (base + timedelta(minutes=60)).strftime(NJT_TIME_FORMAT),
                arr_time_str=(base + timedelta(minutes=59)).strftime(NJT_TIME_FORMAT),
            ),
            # Duplicate OL
            _build_stop_with_sched_times(
                "OL",
                "Mount Olive",
                (base + timedelta(minutes=62)).strftime(NJT_TIME_FORMAT),
                arr_time_str=(base + timedelta(minutes=61)).strftime(NJT_TIME_FORMAT),
            ),
        ]

        train_data = _make_train_data_with_stops(stops)

        await schedule_collector._update_journey_with_stops(
            sqlite_session, journey, train_data
        )
        await sqlite_session.flush()

        assert (
            journey.stops_count == 3
        ), f"Expected stops_count=3 after dedup, got {journey.stops_count}"
        assert (
            journey.origin_station_code == "NY"
        ), f"Expected origin=NY, got {journey.origin_station_code}"
        assert (
            journey.terminal_station_code == "OL"
        ), f"Expected terminal=OL, got {journey.terminal_station_code}"
        assert journey.has_complete_journey is True
