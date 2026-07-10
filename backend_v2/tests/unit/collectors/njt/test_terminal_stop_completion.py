"""
Tests for NJT terminal stop journey completion fix.

Verifies that journeys are correctly completed when the terminal stop
(e.g., NY Penn) is the destination. Terminal stops never get DEPARTED="YES"
from the NJT API, so completion requires the penultimate stop to be explicitly
departed and the terminal arrival time to be due.

Also tests the last-chance completion-on-expiry path for trains that
disappear from the API before normal completion runs.

Uses an in-memory SQLite database to avoid requiring PostgreSQL.
"""

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.models.database import Base, JourneyStop, TrainJourney
from trackrat.utils.time import ET, now_et

from tests.fixtures.njt_api_responses import NJT_TIME_FORMAT, StopBuilder

# ---------------------------------------------------------------------------
# SQLite in-memory fixtures (same pattern as test_journey_data_quality.py)
# ---------------------------------------------------------------------------


@pytest.fixture
async def sqlite_engine():
    """Create an in-memory SQLite engine with timezone-aware datetime handling."""
    import itertools
    import pytz

    _ET = pytz.timezone("America/New_York")

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    from sqlalchemy import TypeDecorator, DateTime as SADateTime

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

    # JourneyStop.id is Identity()-backed for Postgres' composite-PK
    # partitioning (id, journey_date). SQLite doesn't support server-side
    # identity generation, and since id is no longer a lone rowid-alias
    # column, SQLAlchemy's client-side Identity() postfetch reuses the same
    # value for every row in a batched insert. Assign sequential ids
    # ourselves for the lifetime of this engine.
    _next_stop_id = itertools.count(1)

    def _assign_journey_stop_id(mapper, connection, target):
        target.id = next(_next_stop_id)

    event.listen(JourneyStop, "before_insert", _assign_journey_stop_id)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    event.remove(JourneyStop, "before_insert", _assign_journey_stop_id)

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
def mock_njt_client():
    client = AsyncMock(spec=NJTransitClient)
    return client


@pytest.fixture
def journey_collector(mock_njt_client):
    return JourneyCollector(mock_njt_client)


def _make_stop(
    builder,
    station_code,
    station_name,
    dep_time,
    arr_time=None,
    departed=False,
    track=None,
    sched_arr_date=None,
    sched_dep_date=None,
):
    """Build a stop mock with explicit SCHED_ARR_DATE / SCHED_DEP_DATE."""
    stop = builder.build_stop(
        station_code,
        station_name,
        dep_time,
        arr_time=arr_time,
        departed=departed,
        track=track,
    )
    stop.SCHED_ARR_DATE = sched_arr_date
    stop.SCHED_DEP_DATE = sched_dep_date
    return stop


# ---------------------------------------------------------------------------
# Helper to create a TR -> NY journey with stops in the DB
# ---------------------------------------------------------------------------


async def _create_tr_to_ny_journey(
    session: AsyncSession,
    base_time: datetime,
    penultimate_departed: bool = False,
    terminal_departed: bool = False,
) -> TrainJourney:
    """Create a TR -> NP -> NY journey with 3 stops.

    Args:
        session: DB session
        base_time: Base time for scheduled departures. Terminal arrival is
            base_time + 60 minutes.
        penultimate_departed: Whether NP (penultimate) has_departed_station
        terminal_departed: Whether NY (terminal) has_departed_station
    """
    journey = TrainJourney(
        train_id="3828",
        journey_date=date.today(),
        line_code="NE",
        line_name="Northeast Corridor",
        destination="New York",
        origin_station_code="TR",
        terminal_station_code="NY",
        data_source="NJT",
        observation_type="OBSERVED",
        scheduled_departure=base_time,
        is_cancelled=False,
        is_completed=False,
    )
    session.add(journey)
    await session.flush()

    stops = [
        ("TR", "Trenton", 0, True, base_time, base_time),
        (
            "NP",
            "Newark Penn",
            1,
            penultimate_departed,
            base_time + timedelta(minutes=40),
            base_time + timedelta(minutes=42),
        ),
        (
            "NY",
            "New York Penn",
            2,
            terminal_departed,
            base_time + timedelta(minutes=60),
            base_time + timedelta(minutes=60),
        ),
    ]

    for code, name, seq, departed, sched_arr, sched_dep in stops:
        # Terminals never get DEPARTED=YES from NJT, so simulate them with
        # departure_source=None when not departed; intermediate stops with
        # has_departed_station=True are realistically `api_explicit` (NJT
        # reported DEPARTED=YES). Penultimate completion now requires
        # api_explicit specifically.
        if not departed:
            source = None
        elif code == "NY":
            source = "time_inference"
        else:
            source = "api_explicit"
        stop = JourneyStop(
            journey_id=journey.id,
            journey_date=journey.journey_date,
            station_code=code,
            station_name=name,
            stop_sequence=seq,
            has_departed_station=departed,
            departure_source=source,
            scheduled_arrival=sched_arr,
            scheduled_departure=(
                sched_dep if code != "NY" else None
            ),  # Terminal has no departure
        )
        session.add(stop)

    await session.flush()
    return journey


# ---------------------------------------------------------------------------
# Tests: check_journey_completion with penultimate stop logic
# ---------------------------------------------------------------------------


class TestTerminalStopCompletion:
    """Test journey completion through terminal-arrival checks."""

    @pytest.mark.asyncio
    async def test_penultimate_departed_triggers_completion(
        self, sqlite_session, journey_collector
    ):
        """When the penultimate stop (NP) has departed, the journey should
        be marked completed once the terminal arrival time is due, even though
        the terminal stop (NY) has not departed (the normal NJT case)."""
        base_time = now_et().replace(second=0, microsecond=0) - timedelta(minutes=70)
        journey = await _create_tr_to_ny_journey(
            sqlite_session, base_time, penultimate_departed=True
        )

        # Build API stop data for check_journey_completion
        builder = StopBuilder()
        ny_arrival_time = base_time + timedelta(minutes=58)
        stops_data = [
            _make_stop(
                builder,
                "TR",
                "Trenton",
                base_time.strftime(NJT_TIME_FORMAT),
                departed=True,
            ),
            _make_stop(
                builder,
                "NP",
                "Newark Penn",
                (base_time + timedelta(minutes=42)).strftime(NJT_TIME_FORMAT),
                arr_time=(base_time + timedelta(minutes=40)).strftime(NJT_TIME_FORMAT),
                departed=True,
            ),
            _make_stop(
                builder,
                "NY",
                "New York Penn",
                None,  # No DEP_TIME for terminal
                arr_time=ny_arrival_time.strftime(NJT_TIME_FORMAT),
                departed=False,
            ),  # Terminal never gets DEPARTED=YES
        ]
        # Terminal stop has no DEP_TIME
        stops_data[2].DEP_TIME = None

        await journey_collector.check_journey_completion(
            sqlite_session, journey, stops_data
        )

        # Journey should be marked completed
        assert (
            journey.is_completed is True
        ), "Journey should be completed when penultimate stop has departed"

        # Terminal stop should have actual_arrival set from API TIME field
        ny_stop = await sqlite_session.scalar(
            select(JourneyStop).where(
                JourneyStop.journey_id == journey.id,
                JourneyStop.station_code == "NY",
            )
        )
        assert (
            ny_stop.actual_arrival is not None
        ), "Terminal stop actual_arrival should be set from API"
        assert (
            ny_stop.arrival_source == "api_observed"
        ), f"Terminal arrival_source should be 'api_observed', got '{ny_stop.arrival_source}'"
        print(f"  Terminal actual_arrival: {ny_stop.actual_arrival}")
        print(f"  Terminal arrival_source: {ny_stop.arrival_source}")
        print(f"  Journey is_completed: {journey.is_completed}")

    @pytest.mark.asyncio
    async def test_penultimate_departed_does_not_complete_before_terminal_arrival(
        self, sqlite_session, journey_collector
    ):
        """An on-time train that just left the penultimate stop should remain
        active until the terminal arrival time is due."""
        now = now_et().replace(second=0, microsecond=0)
        base_time = now - timedelta(minutes=50)
        journey = await _create_tr_to_ny_journey(
            sqlite_session, base_time, penultimate_departed=True
        )

        builder = StopBuilder()
        ny_arrival_time = now + timedelta(minutes=8)
        stops_data = [
            _make_stop(
                builder,
                "TR",
                "Trenton",
                base_time.strftime(NJT_TIME_FORMAT),
                departed=True,
            ),
            _make_stop(
                builder,
                "NP",
                "Newark Penn",
                (base_time + timedelta(minutes=42)).strftime(NJT_TIME_FORMAT),
                arr_time=(base_time + timedelta(minutes=40)).strftime(NJT_TIME_FORMAT),
                departed=True,
            ),
            _make_stop(
                builder,
                "NY",
                "New York Penn",
                None,
                arr_time=ny_arrival_time.strftime(NJT_TIME_FORMAT),
                departed=False,
            ),
        ]
        stops_data[2].DEP_TIME = None

        await journey_collector.check_journey_completion(
            sqlite_session, journey, stops_data
        )

        assert journey.is_completed is not True, (
            "Journey should not complete merely because the train left the "
            "penultimate stop while terminal arrival is still in the future"
        )
        ny_stop = await sqlite_session.scalar(
            select(JourneyStop).where(
                JourneyStop.journey_id == journey.id,
                JourneyStop.station_code == "NY",
            )
        )
        assert ny_stop.actual_arrival is None

    @pytest.mark.asyncio
    async def test_misordered_api_stops_use_terminal_row_for_arrival_due(
        self, sqlite_session, journey_collector
    ):
        """Completion should match the terminal API row by station code, not
        raw list position."""
        now = now_et().replace(second=0, microsecond=0)
        base_time = now - timedelta(minutes=70)
        journey = await _create_tr_to_ny_journey(
            sqlite_session, base_time, penultimate_departed=True
        )

        builder = StopBuilder()
        terminal_arrival_time = now - timedelta(minutes=1)
        future_intermediate_time = now + timedelta(minutes=8)
        stops_data = [
            _make_stop(
                builder,
                "TR",
                "Trenton",
                base_time.strftime(NJT_TIME_FORMAT),
                departed=True,
            ),
            _make_stop(
                builder,
                "NY",
                "New York Penn",
                None,
                arr_time=terminal_arrival_time.strftime(NJT_TIME_FORMAT),
                departed=False,
            ),
            _make_stop(
                builder,
                "NP",
                "Newark Penn",
                future_intermediate_time.strftime(NJT_TIME_FORMAT),
                arr_time=future_intermediate_time.strftime(NJT_TIME_FORMAT),
                departed=True,
            ),
        ]
        stops_data[1].DEP_TIME = None

        await journey_collector.check_journey_completion(
            sqlite_session, journey, stops_data
        )

        assert journey.is_completed is True, (
            "Journey should complete using the NY terminal row even when NJT "
            "returns a non-terminal stop last"
        )
        ny_stop = await sqlite_session.scalar(
            select(JourneyStop).where(
                JourneyStop.journey_id == journey.id,
                JourneyStop.station_code == "NY",
            )
        )
        assert ny_stop.actual_arrival == terminal_arrival_time
        assert ny_stop.arrival_source == "api_observed"

    @pytest.mark.asyncio
    async def test_no_completion_when_penultimate_not_departed(
        self, sqlite_session, journey_collector
    ):
        """Journey should NOT be completed when neither terminal nor
        penultimate stop has departed."""
        base_time = now_et().replace(second=0, microsecond=0) - timedelta(minutes=70)
        journey = await _create_tr_to_ny_journey(
            sqlite_session, base_time, penultimate_departed=False
        )

        builder = StopBuilder()
        stops_data = [
            _make_stop(
                builder,
                "TR",
                "Trenton",
                base_time.strftime(NJT_TIME_FORMAT),
                departed=True,
            ),
            _make_stop(
                builder,
                "NP",
                "Newark Penn",
                (base_time + timedelta(minutes=42)).strftime(NJT_TIME_FORMAT),
                departed=False,
            ),
            _make_stop(builder, "NY", "New York Penn", None, departed=False),
        ]
        stops_data[2].DEP_TIME = None

        await journey_collector.check_journey_completion(
            sqlite_session, journey, stops_data
        )

        assert (
            journey.is_completed is not True
        ), "Journey should NOT be completed when penultimate stop hasn't departed"
        print(f"  Journey is_completed: {journey.is_completed}")

    @pytest.mark.asyncio
    async def test_terminal_departed_still_works(
        self, sqlite_session, journey_collector
    ):
        """The original logic (terminal stop departed) should still work
        for edge cases where it does fire."""
        base_time = now_et().replace(second=0, microsecond=0) - timedelta(minutes=70)
        journey = await _create_tr_to_ny_journey(
            sqlite_session,
            base_time,
            penultimate_departed=True,
            terminal_departed=True,
        )

        builder = StopBuilder()
        ny_arrival_time = base_time + timedelta(minutes=58)
        stops_data = [
            _make_stop(
                builder,
                "TR",
                "Trenton",
                base_time.strftime(NJT_TIME_FORMAT),
                departed=True,
            ),
            _make_stop(
                builder,
                "NP",
                "Newark Penn",
                (base_time + timedelta(minutes=42)).strftime(NJT_TIME_FORMAT),
                departed=True,
            ),
            _make_stop(
                builder,
                "NY",
                "New York Penn",
                None,
                arr_time=ny_arrival_time.strftime(NJT_TIME_FORMAT),
                departed=True,
            ),
        ]
        stops_data[2].DEP_TIME = None

        await journey_collector.check_journey_completion(
            sqlite_session, journey, stops_data
        )

        assert (
            journey.is_completed is True
        ), "Journey should be completed when terminal stop has departed"
        print(f"  Journey is_completed: {journey.is_completed}")


# ---------------------------------------------------------------------------
# Tests: stop_sequence robustness (MAX vs len-1)
# ---------------------------------------------------------------------------


class TestStopSequenceRobustness:
    """Test that completion works with non-contiguous stop sequences."""

    @pytest.mark.asyncio
    async def test_gap_in_stop_sequences(self, sqlite_session, journey_collector):
        """If a phantom stop was deleted leaving a gap in sequences
        (e.g., 0, 1, 3 instead of 0, 1, 2), completion should still find
        the correct terminal stop via ORDER BY desc, not len(stops_data)-1."""
        base_time = now_et().replace(second=0, microsecond=0) - timedelta(minutes=70)

        journey = TrainJourney(
            train_id="3830",
            journey_date=date.today(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="New York",
            origin_station_code="TR",
            terminal_station_code="NY",
            data_source="NJT",
            observation_type="OBSERVED",
            scheduled_departure=base_time,
            is_cancelled=False,
            is_completed=False,
        )
        sqlite_session.add(journey)
        await sqlite_session.flush()

        # Create stops with a gap: sequences 0, 1, 3 (stop 2 was deleted)
        stops_db = [
            JourneyStop(
                journey_id=journey.id,
                journey_date=journey.journey_date,
                station_code="TR",
                station_name="Trenton",
                stop_sequence=0,
                has_departed_station=True,
                scheduled_arrival=base_time,
            ),
            JourneyStop(
                journey_id=journey.id,
                journey_date=journey.journey_date,
                station_code="NP",
                station_name="Newark Penn",
                stop_sequence=1,
                has_departed_station=True,
                departure_source="api_explicit",
                scheduled_arrival=base_time + timedelta(minutes=40),
            ),
            # stop_sequence=2 was deleted (phantom stop)
            JourneyStop(
                journey_id=journey.id,
                journey_date=journey.journey_date,
                station_code="NY",
                station_name="New York Penn",
                stop_sequence=3,
                has_departed_station=False,
                scheduled_arrival=base_time + timedelta(minutes=60),
            ),
        ]
        for s in stops_db:
            sqlite_session.add(s)
        await sqlite_session.flush()

        # API data has 3 stops (matching current state)
        builder = StopBuilder()
        ny_arrival_time = base_time + timedelta(minutes=58)
        stops_data = [
            _make_stop(
                builder,
                "TR",
                "Trenton",
                base_time.strftime(NJT_TIME_FORMAT),
                departed=True,
            ),
            _make_stop(
                builder,
                "NP",
                "Newark Penn",
                (base_time + timedelta(minutes=42)).strftime(NJT_TIME_FORMAT),
                departed=True,
            ),
            _make_stop(
                builder,
                "NY",
                "New York Penn",
                None,
                arr_time=ny_arrival_time.strftime(NJT_TIME_FORMAT),
                departed=False,
            ),
        ]
        stops_data[2].DEP_TIME = None

        await journey_collector.check_journey_completion(
            sqlite_session, journey, stops_data
        )

        # With the old code (stop_sequence == len(stops_data) - 1 == 2),
        # this would fail because there's no stop with sequence 2.
        # With the new code (ORDER BY desc), it correctly finds sequence 3.
        assert journey.is_completed is True, (
            "Journey should be completed even with non-contiguous stop sequences. "
            f"The old code would look for stop_sequence=={len(stops_data) - 1}==2 "
            "which doesn't exist. The new code uses ORDER BY desc to find sequence 3."
        )

        ny_stop = await sqlite_session.scalar(
            select(JourneyStop).where(
                JourneyStop.journey_id == journey.id,
                JourneyStop.station_code == "NY",
            )
        )
        assert (
            ny_stop.arrival_source == "api_observed"
        ), f"Expected 'api_observed', got '{ny_stop.arrival_source}'"
        print(f"  Gap test: journey completed with stop_sequences [0, 1, 3]")


# ---------------------------------------------------------------------------
# Tests: completion-on-expiry
# ---------------------------------------------------------------------------


class TestCompletionOnExpiry:
    """Test last-chance completion when train disappears from API."""

    @pytest.mark.asyncio
    async def test_expiry_completes_when_penultimate_departed(
        self, sqlite_session, journey_collector
    ):
        """When a train disappears from the API after terminal arrival time,
        the journey should be marked completed (not expired)."""
        base_time = now_et().replace(second=0, microsecond=0) - timedelta(minutes=70)
        journey = await _create_tr_to_ny_journey(
            sqlite_session, base_time, penultimate_departed=True
        )

        await journey_collector._attempt_completion_on_expiry(sqlite_session, journey)

        assert (
            journey.is_completed is True
        ), "Journey should be completed on expiry when penultimate stop departed"
        # Since we don't have API data, terminal uses scheduled_fallback
        ny_stop = await sqlite_session.scalar(
            select(JourneyStop).where(
                JourneyStop.journey_id == journey.id,
                JourneyStop.station_code == "NY",
            )
        )
        assert (
            ny_stop.actual_arrival is not None
        ), "Terminal actual_arrival should be set from scheduled_arrival fallback"
        assert (
            ny_stop.arrival_source == "scheduled_fallback"
        ), f"Expected 'scheduled_fallback', got '{ny_stop.arrival_source}'"
        print(f"  Expiry completion: actual_arrival={ny_stop.actual_arrival}")
        print(f"  Expiry completion: arrival_source={ny_stop.arrival_source}")

    @pytest.mark.asyncio
    async def test_expiry_does_not_complete_before_terminal_arrival(
        self, sqlite_session, journey_collector
    ):
        """Expiry fallback should not complete a train that left the
        penultimate stop but is still scheduled to arrive at the terminal."""
        base_time = now_et().replace(second=0, microsecond=0) - timedelta(minutes=50)
        journey = await _create_tr_to_ny_journey(
            sqlite_session, base_time, penultimate_departed=True
        )

        await journey_collector._attempt_completion_on_expiry(sqlite_session, journey)

        assert (
            journey.is_completed is not True
        ), "Expiry completion should wait until the terminal arrival time is due"

    @pytest.mark.asyncio
    async def test_expiry_uses_latest_terminal_estimate_before_schedule_fallback(
        self, sqlite_session, journey_collector
    ):
        """A stale static schedule should not complete a delayed train when the
        latest terminal estimate is still in the future."""
        now = now_et().replace(second=0, microsecond=0)
        base_time = now - timedelta(minutes=70)
        journey = await _create_tr_to_ny_journey(
            sqlite_session, base_time, penultimate_departed=True
        )
        ny_stop = await sqlite_session.scalar(
            select(JourneyStop).where(
                JourneyStop.journey_id == journey.id,
                JourneyStop.station_code == "NY",
            )
        )
        ny_stop.updated_arrival = now + timedelta(minutes=8)
        await sqlite_session.flush()

        await journey_collector._attempt_completion_on_expiry(sqlite_session, journey)

        assert journey.is_completed is not True, (
            "Expiry completion should honor the latest terminal estimate before "
            "falling back to schedule"
        )
        assert ny_stop.actual_arrival is None

    @pytest.mark.asyncio
    async def test_expiry_does_not_complete_when_penultimate_not_departed(
        self, sqlite_session, journey_collector
    ):
        """When the penultimate stop hasn't departed, expiry should NOT
        mark the journey as completed."""
        base_time = now_et().replace(hour=8, minute=0, second=0, microsecond=0)
        journey = await _create_tr_to_ny_journey(
            sqlite_session, base_time, penultimate_departed=False
        )

        await journey_collector._attempt_completion_on_expiry(sqlite_session, journey)

        assert journey.is_completed is not True, (
            "Journey should NOT be completed on expiry when penultimate stop "
            "hasn't departed"
        )
        print(f"  No expiry completion: is_completed={journey.is_completed}")

    @pytest.mark.asyncio
    async def test_expiry_does_not_overwrite_existing_completion(
        self, sqlite_session, journey_collector
    ):
        """If journey is already completed, expiry handler should not
        run (guarded by the caller)."""
        base_time = now_et().replace(second=0, microsecond=0) - timedelta(minutes=70)
        journey = await _create_tr_to_ny_journey(
            sqlite_session, base_time, penultimate_departed=True
        )
        journey.is_completed = True

        # Set terminal stop with api_observed arrival
        ny_stop = await sqlite_session.scalar(
            select(JourneyStop).where(
                JourneyStop.journey_id == journey.id,
                JourneyStop.station_code == "NY",
            )
        )
        ny_stop.actual_arrival = base_time + timedelta(minutes=58)
        ny_stop.arrival_source = "api_observed"
        await sqlite_session.flush()

        # This should be a no-op since the caller guards with `not journey.is_completed`
        # But test the method directly to ensure it doesn't corrupt data
        await journey_collector._attempt_completion_on_expiry(sqlite_session, journey)

        await sqlite_session.refresh(ny_stop)
        assert (
            ny_stop.arrival_source == "api_observed"
        ), "Existing api_observed arrival should not be overwritten by expiry"
        print(f"  Preserved arrival_source: {ny_stop.arrival_source}")
