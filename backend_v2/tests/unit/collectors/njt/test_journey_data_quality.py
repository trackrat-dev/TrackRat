"""
Unit tests for NJT journey data quality improvements.

Tests three categories of fixes:
1. Ghost-train reconciliation: SCHEDULED trains that never became OBSERVED
   should be marked as cancelled after 60 minutes past their departure.
2. Arrival time freezing: actual_arrival should not be overwritten after
   a train has departed a stop.
3. Schedule-based scheduled_arrival: Prefer SCHED_ARR_DATE over the
   live-updating TIME field for scheduled_arrival at intermediate stops.
4. Bulk inference guard: Tier 2/3 inference should not overwrite existing
   actual_departure values.

Uses an in-memory SQLite database to avoid requiring PostgreSQL for unit tests.
"""

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.journey import JourneyCollector, normalize_njt_stop_times
from trackrat.models.database import Base, JourneyStop, TrainJourney
from trackrat.utils.time import ET, now_et

from tests.fixtures.njt_api_responses import NJT_TIME_FORMAT, StopBuilder

# ---------------------------------------------------------------------------
# SQLite in-memory fixtures (avoids PostgreSQL requirement)
# ---------------------------------------------------------------------------


@pytest.fixture
async def sqlite_engine():
    """Create an in-memory SQLite engine for testing.

    Uses a connection-level event listener to convert timezone-aware datetimes
    to UTC-naive on write and back to ET on read. This is more robust than
    monkey-patching column types, which breaks when SQLAlchemy caches type
    references on AnnotatedColumn objects during ORM class mapping.
    """
    import pytz

    _ET = pytz.timezone("America/New_York")

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # SQLite DateTime handling strategy:
    #
    # The pysqlite dialect's bind_processor converts datetimes to strings
    # by extracting naive components (year, month, day, hour, minute, second),
    # IGNORING timezone info entirely. This happens BEFORE any event listeners
    # fire, so before_cursor_execute cannot intercept datetime values.
    #
    # Since all input datetimes are in ET (from now_et() / parse_njt_time()),
    # they are stored as ET-naive strings (e.g., "2026-02-09 08:20:00").
    # On read, we re-attach the ET timezone. No UTC conversion needed.
    #
    # This approach is consistent regardless of whether a column uses our
    # patched TZDateTime type or the original DateTime type (AnnotatedColumn
    # caching means some columns bypass the patch).
    from sqlalchemy import TypeDecorator, DateTime as SADateTime

    class TZDateTime(TypeDecorator):
        impl = SADateTime
        cache_ok = True

        def process_bind_param(self, value, dialect):
            # No conversion needed: the dialect's bind_processor extracts
            # naive components from the datetime, so timezone is irrelevant.
            return value

        def process_result_value(self, value, dialect):
            if value is not None:
                # Stored values are ET-naive; re-attach ET timezone
                return _ET.localize(value)
            return value

    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, SADateTime) and column.type.timezone:
                column.type = TZDateTime()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Restore original DateTime types to avoid leaking into other test modules
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
def mock_njt_client():
    """Mock NJ Transit client."""
    client = AsyncMock(spec=NJTransitClient)
    return client


@pytest.fixture
def journey_collector(mock_njt_client):
    """Create journey collector with mocked client."""
    return JourneyCollector(mock_njt_client)


def _make_stop_with_sched_fields(
    builder,
    station_code,
    station_name,
    dep_time,
    arr_time=None,
    departed=False,
    track=None,
    cancelled=False,
    sched_arr_date=None,
    sched_dep_date=None,
):
    """Build a stop mock and explicitly set SCHED_ARR_DATE / SCHED_DEP_DATE.

    MagicMock auto-generates attributes as Mock objects on access, which
    confuses truthiness checks.  Setting them to None explicitly when not
    provided ensures `if stop_data.SCHED_ARR_DATE` evaluates correctly.
    """
    stop = builder.build_stop(
        station_code,
        station_name,
        dep_time,
        arr_time=arr_time,
        departed=departed,
        track=track,
        cancelled=cancelled,
    )
    stop.SCHED_ARR_DATE = sched_arr_date
    stop.SCHED_DEP_DATE = sched_dep_date
    return stop


# ---------------------------------------------------------------------------
# 1. Ghost-train reconciliation
# ---------------------------------------------------------------------------


class TestReconcileUnobservedTrains:
    """Test that SCHEDULED trains past their departure are marked cancelled."""

    @pytest.mark.asyncio
    async def test_marks_old_scheduled_trains_as_cancelled(
        self, sqlite_session: AsyncSession, journey_collector
    ):
        """A SCHEDULED train whose origin departure was >60 minutes ago
        should be marked is_cancelled=True with a reason."""
        two_hours_ago = now_et() - timedelta(hours=2)

        journey = TrainJourney(
            train_id="2532",
            journey_date=now_et().date(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="NEW YORK PENN STATION",
            origin_station_code="TR",
            terminal_station_code="NY",
            data_source="NJT",
            observation_type="SCHEDULED",
            scheduled_departure=two_hours_ago,
            is_cancelled=False,
            is_expired=False,
            is_completed=False,
        )
        sqlite_session.add(journey)
        await sqlite_session.flush()

        await journey_collector._reconcile_unobserved_trains(sqlite_session)
        await sqlite_session.refresh(journey)

        assert journey.is_cancelled is True, (
            f"Expected is_cancelled=True for SCHEDULED train 2h past departure, "
            f"got {journey.is_cancelled}"
        )
        assert journey.cancellation_reason == "Not observed in real-time feed", (
            f"Expected cancellation_reason to explain why, "
            f"got {journey.cancellation_reason!r}"
        )

    @pytest.mark.asyncio
    async def test_does_not_cancel_recent_scheduled_trains(
        self, sqlite_session: AsyncSession, journey_collector
    ):
        """A SCHEDULED train whose departure is <60 minutes ago should
        NOT be cancelled -- discovery may still find it."""
        twenty_min_ago = now_et() - timedelta(minutes=20)

        journey = TrainJourney(
            train_id="2534",
            journey_date=now_et().date(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="NEW YORK PENN STATION",
            origin_station_code="TR",
            terminal_station_code="NY",
            data_source="NJT",
            observation_type="SCHEDULED",
            scheduled_departure=twenty_min_ago,
            is_cancelled=False,
            is_expired=False,
            is_completed=False,
        )
        sqlite_session.add(journey)
        await sqlite_session.flush()

        await journey_collector._reconcile_unobserved_trains(sqlite_session)
        await sqlite_session.refresh(journey)

        assert journey.is_cancelled is False, (
            f"SCHEDULED train only 20min past departure should NOT be cancelled, "
            f"got is_cancelled={journey.is_cancelled}"
        )

    @pytest.mark.asyncio
    async def test_does_not_cancel_observed_trains(
        self, sqlite_session: AsyncSession, journey_collector
    ):
        """An OBSERVED train should never be affected by reconciliation,
        even if it's old and not completed."""
        two_hours_ago = now_et() - timedelta(hours=2)

        journey = TrainJourney(
            train_id="3920",
            journey_date=now_et().date(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="New York",
            origin_station_code="TR",
            terminal_station_code="NY",
            data_source="NJT",
            observation_type="OBSERVED",
            scheduled_departure=two_hours_ago,
            is_cancelled=False,
            is_expired=False,
            is_completed=False,
        )
        sqlite_session.add(journey)
        await sqlite_session.flush()

        await journey_collector._reconcile_unobserved_trains(sqlite_session)
        await sqlite_session.refresh(journey)

        assert (
            journey.is_cancelled is False
        ), "OBSERVED trains should never be cancelled by reconciliation"

    @pytest.mark.asyncio
    async def test_does_not_cancel_future_scheduled_trains(
        self, sqlite_session: AsyncSession, journey_collector
    ):
        """A SCHEDULED train that hasn't departed yet should not be cancelled."""
        in_one_hour = now_et() + timedelta(hours=1)

        journey = TrainJourney(
            train_id="2536",
            journey_date=now_et().date(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="NEW YORK PENN STATION",
            origin_station_code="TR",
            terminal_station_code="NY",
            data_source="NJT",
            observation_type="SCHEDULED",
            scheduled_departure=in_one_hour,
            is_cancelled=False,
            is_expired=False,
            is_completed=False,
        )
        sqlite_session.add(journey)
        await sqlite_session.flush()

        await journey_collector._reconcile_unobserved_trains(sqlite_session)
        await sqlite_session.refresh(journey)

        assert (
            journey.is_cancelled is False
        ), "Future SCHEDULED trains should not be cancelled"

    @pytest.mark.asyncio
    async def test_does_not_re_cancel_already_cancelled(
        self, sqlite_session: AsyncSession, journey_collector
    ):
        """Already-cancelled trains should not be touched by reconciliation."""
        two_hours_ago = now_et() - timedelta(hours=2)

        journey = TrainJourney(
            train_id="2538",
            journey_date=now_et().date(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="NEW YORK PENN STATION",
            origin_station_code="TR",
            terminal_station_code="NY",
            data_source="NJT",
            observation_type="SCHEDULED",
            scheduled_departure=two_hours_ago,
            is_cancelled=True,
            cancellation_reason="All stops cancelled by NJT",
            is_expired=False,
            is_completed=False,
        )
        sqlite_session.add(journey)
        await sqlite_session.flush()

        await journey_collector._reconcile_unobserved_trains(sqlite_session)
        await sqlite_session.refresh(journey)

        # Should keep original reason, not overwrite
        assert journey.cancellation_reason == "All stops cancelled by NJT", (
            f"Should preserve original cancellation_reason, "
            f"got {journey.cancellation_reason!r}"
        )


# ---------------------------------------------------------------------------
# 2. Arrival time freezing
# ---------------------------------------------------------------------------


class TestArrivalTimeFreezing:
    """Test that actual_arrival is not overwritten after departure."""

    @pytest.mark.asyncio
    async def test_actual_arrival_frozen_after_departure(
        self, sqlite_session: AsyncSession, journey_collector
    ):
        """Once a train departs a stop, the arrival time at that stop should
        not change on subsequent collection cycles.

        This prevents the anomaly where NJT revises TIME values for past stops,
        producing erroneous delay readings (e.g., +99m or -13m)."""
        base_time = now_et().replace(hour=8, minute=0, second=0, microsecond=0)

        # Create a journey
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
        sqlite_session.add(journey)
        await sqlite_session.flush()

        # First collection: train at NP, NP has arrived and departed
        np_arr_time_1 = base_time + timedelta(minutes=20)
        builder = StopBuilder()
        stops_cycle_1 = [
            _make_stop_with_sched_fields(
                builder,
                "TR",
                "Trenton",
                dep_time=base_time.strftime(NJT_TIME_FORMAT),
                departed=True,
                track="2",
            ),
            _make_stop_with_sched_fields(
                builder,
                "NP",
                "Newark Penn",
                dep_time=(base_time + timedelta(minutes=22)).strftime(NJT_TIME_FORMAT),
                arr_time=np_arr_time_1.strftime(NJT_TIME_FORMAT),
                departed=True,
                track="1",
            ),
            _make_stop_with_sched_fields(
                builder,
                "NY",
                "New York Penn",
                dep_time=(base_time + timedelta(minutes=40)).strftime(NJT_TIME_FORMAT),
                arr_time=(base_time + timedelta(minutes=38)).strftime(NJT_TIME_FORMAT),
                departed=False,
            ),
        ]
        await journey_collector.update_journey_stops(
            sqlite_session, journey, stops_cycle_1
        )
        await sqlite_session.flush()

        # Verify NP arrival was set
        np_stop = await sqlite_session.scalar(
            select(JourneyStop).where(
                JourneyStop.journey_id == journey.id,
                JourneyStop.station_code == "NP",
            )
        )
        assert np_stop is not None
        assert np_stop.actual_arrival == np_arr_time_1, (
            f"First cycle should set actual_arrival to {np_arr_time_1}, "
            f"got {np_stop.actual_arrival}"
        )
        assert np_stop.has_departed_station is True

        # Second collection: NJT revises NP's TIME to a different value
        np_arr_time_2 = base_time + timedelta(minutes=25)  # revised by NJT
        stops_cycle_2 = [
            _make_stop_with_sched_fields(
                builder,
                "TR",
                "Trenton",
                dep_time=base_time.strftime(NJT_TIME_FORMAT),
                departed=True,
                track="2",
            ),
            _make_stop_with_sched_fields(
                builder,
                "NP",
                "Newark Penn",
                dep_time=(base_time + timedelta(minutes=22)).strftime(NJT_TIME_FORMAT),
                arr_time=np_arr_time_2.strftime(NJT_TIME_FORMAT),  # revised!
                departed=True,
                track="1",
            ),
            _make_stop_with_sched_fields(
                builder,
                "NY",
                "New York Penn",
                dep_time=(base_time + timedelta(minutes=40)).strftime(NJT_TIME_FORMAT),
                arr_time=(base_time + timedelta(minutes=38)).strftime(NJT_TIME_FORMAT),
                departed=False,
            ),
        ]
        await journey_collector.update_journey_stops(
            sqlite_session, journey, stops_cycle_2
        )
        await sqlite_session.flush()

        # Refresh and verify NP arrival was NOT overwritten
        await sqlite_session.refresh(np_stop)
        assert np_stop.actual_arrival == np_arr_time_1, (
            f"actual_arrival should be frozen at {np_arr_time_1} after departure, "
            f"but was overwritten to {np_stop.actual_arrival}"
        )


# ---------------------------------------------------------------------------
# 3. Schedule-based scheduled_arrival (SCHED_ARR_DATE preference)
# ---------------------------------------------------------------------------


class TestScheduleBasedArrival:
    """Test that SCHED_ARR_DATE is preferred over TIME for scheduled_arrival."""

    @pytest.mark.asyncio
    async def test_prefers_sched_arr_date_for_new_stops(
        self, sqlite_session: AsyncSession, journey_collector
    ):
        """When creating a new stop, scheduled_arrival should come from
        SCHED_ARR_DATE (immutable schedule) rather than TIME (live estimate)."""
        base_time = now_et().replace(hour=8, minute=0, second=0, microsecond=0)

        journey = TrainJourney(
            train_id="3922",
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

        # Build stop with BOTH TIME (live estimate) and SCHED_ARR_DATE (schedule)
        sched_arr = base_time + timedelta(minutes=20)  # True schedule
        live_arr = base_time + timedelta(minutes=35)  # Delayed live estimate
        builder = StopBuilder()

        tr_stop = _make_stop_with_sched_fields(
            builder,
            "TR",
            "Trenton",
            dep_time=base_time.strftime(NJT_TIME_FORMAT),
            departed=False,
            track="1",
            sched_dep_date=base_time.strftime(NJT_TIME_FORMAT),
        )
        np_stop_data = _make_stop_with_sched_fields(
            builder,
            "NP",
            "Newark Penn",
            dep_time=(base_time + timedelta(minutes=22)).strftime(NJT_TIME_FORMAT),
            arr_time=live_arr.strftime(NJT_TIME_FORMAT),  # TIME = delayed estimate
            departed=False,
            sched_arr_date=sched_arr.strftime(NJT_TIME_FORMAT),
            sched_dep_date=(base_time + timedelta(minutes=22)).strftime(
                NJT_TIME_FORMAT
            ),
        )

        stops = [tr_stop, np_stop_data]
        await journey_collector.update_journey_stops(sqlite_session, journey, stops)
        await sqlite_session.flush()

        np_stop = await sqlite_session.scalar(
            select(JourneyStop).where(
                JourneyStop.journey_id == journey.id,
                JourneyStop.station_code == "NP",
            )
        )
        assert np_stop is not None
        assert np_stop.scheduled_arrival == sched_arr, (
            f"scheduled_arrival should use SCHED_ARR_DATE ({sched_arr}), "
            f"not TIME ({live_arr}), got {np_stop.scheduled_arrival}"
        )

    @pytest.mark.asyncio
    async def test_falls_back_to_time_when_no_sched_arr_date(
        self, sqlite_session: AsyncSession, journey_collector
    ):
        """When SCHED_ARR_DATE is absent, scheduled_arrival should use the
        normalized TIME field as before (backward compatibility)."""
        base_time = now_et().replace(hour=8, minute=0, second=0, microsecond=0)

        journey = TrainJourney(
            train_id="3924",
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

        live_arr = base_time + timedelta(minutes=20)
        builder = StopBuilder()
        tr_stop = _make_stop_with_sched_fields(
            builder,
            "TR",
            "Trenton",
            dep_time=base_time.strftime(NJT_TIME_FORMAT),
            departed=False,
        )
        np_stop_data = _make_stop_with_sched_fields(
            builder,
            "NP",
            "Newark Penn",
            dep_time=(base_time + timedelta(minutes=22)).strftime(NJT_TIME_FORMAT),
            arr_time=live_arr.strftime(NJT_TIME_FORMAT),
            departed=False,
        )
        # No SCHED_ARR_DATE -- should use TIME

        stops = [tr_stop, np_stop_data]
        await journey_collector.update_journey_stops(sqlite_session, journey, stops)
        await sqlite_session.flush()

        np_stop = await sqlite_session.scalar(
            select(JourneyStop).where(
                JourneyStop.journey_id == journey.id,
                JourneyStop.station_code == "NP",
            )
        )
        assert np_stop is not None
        assert np_stop.scheduled_arrival == live_arr, (
            f"Without SCHED_ARR_DATE, scheduled_arrival should fall back to "
            f"TIME ({live_arr}), got {np_stop.scheduled_arrival}"
        )


# ---------------------------------------------------------------------------
# 4. Bulk inference guard
# ---------------------------------------------------------------------------


class TestBulkInferenceGuard:
    """Test that Tier 2/3 don't overwrite existing actual_departure or departure_source."""

    @pytest.mark.asyncio
    async def test_tier3_does_not_overwrite_departure_source(
        self, sqlite_session: AsyncSession, journey_collector
    ):
        """When time-based inference (Tier 3) runs on a stop that already has
        departure_source='api_explicit' from a previous cycle, it should preserve
        the original source.

        This prevents departure_source downgrades that corrupt arrival forecast
        buffers in DirectArrivalForecaster (api_explicit=1min vs time_inference=5min).
        """
        # Use a time 2 hours in the past so Tier 3's 5-minute threshold is
        # always exceeded regardless of when the test suite runs.
        base_time = (now_et() - timedelta(hours=2)).replace(second=0, microsecond=0)

        journey = TrainJourney(
            train_id="3922C",
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

        builder = StopBuilder()

        # First cycle: NP explicitly departed, gets api_explicit source
        np_dep_time = base_time + timedelta(minutes=20)
        stops_cycle_1 = [
            _make_stop_with_sched_fields(
                builder,
                "TR",
                "Trenton",
                dep_time=base_time.strftime(NJT_TIME_FORMAT),
                departed=True,
                track="2",
            ),
            _make_stop_with_sched_fields(
                builder,
                "NP",
                "Newark Penn",
                dep_time=np_dep_time.strftime(NJT_TIME_FORMAT),
                arr_time=np_dep_time.strftime(NJT_TIME_FORMAT),
                departed=True,
                track="1",
            ),
            _make_stop_with_sched_fields(
                builder,
                "NY",
                "New York Penn",
                dep_time=(base_time + timedelta(minutes=40)).strftime(NJT_TIME_FORMAT),
                arr_time=(base_time + timedelta(minutes=38)).strftime(NJT_TIME_FORMAT),
                departed=False,
            ),
        ]
        await journey_collector.update_journey_stops(
            sqlite_session, journey, stops_cycle_1
        )
        await sqlite_session.flush()

        np_stop = await sqlite_session.scalar(
            select(JourneyStop).where(
                JourneyStop.journey_id == journey.id,
                JourneyStop.station_code == "NP",
            )
        )
        assert np_stop is not None
        assert np_stop.departure_source == "api_explicit", (
            f"First cycle should set departure_source to api_explicit, "
            f"got {np_stop.departure_source!r}"
        )

        # Second cycle: NJT no longer reports DEPARTED=YES for NP, and NY
        # is also not departed. NP's scheduled_departure is >5min ago, so
        # Tier 3 (time_inference) fires. departure_source must be preserved.
        stops_cycle_2 = [
            _make_stop_with_sched_fields(
                builder,
                "TR",
                "Trenton",
                dep_time=base_time.strftime(NJT_TIME_FORMAT),
                departed=True,
                track="2",
            ),
            _make_stop_with_sched_fields(
                builder,
                "NP",
                "Newark Penn",
                dep_time=np_dep_time.strftime(NJT_TIME_FORMAT),
                arr_time=np_dep_time.strftime(NJT_TIME_FORMAT),
                departed=False,  # NJT stopped reporting DEPARTED=YES
            ),
            _make_stop_with_sched_fields(
                builder,
                "NY",
                "New York Penn",
                dep_time=(base_time + timedelta(minutes=40)).strftime(NJT_TIME_FORMAT),
                arr_time=(base_time + timedelta(minutes=38)).strftime(NJT_TIME_FORMAT),
                departed=False,  # NY also not departed -> no Tier 2
            ),
        ]
        await journey_collector.update_journey_stops(
            sqlite_session, journey, stops_cycle_2
        )
        await sqlite_session.flush()

        await sqlite_session.refresh(np_stop)
        assert np_stop.departure_source == "api_explicit", (
            f"Tier 3 should not downgrade departure_source from 'api_explicit', "
            f"got {np_stop.departure_source!r}"
        )
        assert np_stop.actual_departure == np_dep_time, (
            f"Tier 3 should not overwrite actual_departure either, "
            f"got {np_stop.actual_departure}"
        )

    @pytest.mark.asyncio
    async def test_has_departed_not_reverted_to_false(
        self, sqlite_session: AsyncSession, journey_collector
    ):
        """Once a stop has has_departed_station=True, it should never revert
        to False even if the API temporarily stops reporting departure data.

        This prevents a previously-departed stop from appearing as not-departed
        when NJT data is transiently inconsistent."""
        base_time = now_et().replace(hour=8, minute=0, second=0, microsecond=0)

        journey = TrainJourney(
            train_id="3922D",
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

        builder = StopBuilder()

        # First cycle: TR explicitly departed
        stops_cycle_1 = [
            _make_stop_with_sched_fields(
                builder,
                "TR",
                "Trenton",
                dep_time=base_time.strftime(NJT_TIME_FORMAT),
                departed=True,
                track="2",
            ),
            _make_stop_with_sched_fields(
                builder,
                "NP",
                "Newark Penn",
                dep_time=(base_time + timedelta(minutes=20)).strftime(NJT_TIME_FORMAT),
                arr_time=(base_time + timedelta(minutes=18)).strftime(NJT_TIME_FORMAT),
                departed=False,
            ),
        ]
        await journey_collector.update_journey_stops(
            sqlite_session, journey, stops_cycle_1
        )
        await sqlite_session.flush()

        tr_stop = await sqlite_session.scalar(
            select(JourneyStop).where(
                JourneyStop.journey_id == journey.id,
                JourneyStop.station_code == "TR",
            )
        )
        assert tr_stop is not None
        assert tr_stop.has_departed_station is True
        assert tr_stop.departure_source == "api_explicit"

        # Second cycle: NJT glitch — TR no longer reported as DEPARTED,
        # and no other stop is departed either. The else branch fires.
        # TR's scheduled_departure is in the future (to avoid Tier 3).
        future_dep = now_et() + timedelta(hours=1)
        stops_cycle_2 = [
            _make_stop_with_sched_fields(
                builder,
                "TR",
                "Trenton",
                dep_time=future_dep.strftime(NJT_TIME_FORMAT),
                departed=False,  # NJT glitch
                track="2",
            ),
            _make_stop_with_sched_fields(
                builder,
                "NP",
                "Newark Penn",
                dep_time=(future_dep + timedelta(minutes=20)).strftime(NJT_TIME_FORMAT),
                arr_time=(future_dep + timedelta(minutes=18)).strftime(NJT_TIME_FORMAT),
                departed=False,
            ),
        ]
        await journey_collector.update_journey_stops(
            sqlite_session, journey, stops_cycle_2
        )
        await sqlite_session.flush()

        await sqlite_session.refresh(tr_stop)
        assert tr_stop.has_departed_station is True, (
            f"has_departed_station should never revert from True to False, "
            f"got {tr_stop.has_departed_station}"
        )
        assert tr_stop.departure_source == "api_explicit", (
            f"departure_source should be preserved when has_departed is not reverted, "
            f"got {tr_stop.departure_source!r}"
        )

    @pytest.mark.asyncio
    async def test_tier2_does_not_overwrite_existing_departure(
        self, sqlite_session: AsyncSession, journey_collector
    ):
        """When sequential inference (Tier 2) runs on a stop that already has
        an actual_departure from a previous cycle, it should NOT overwrite it.

        This prevents the bulk-stamp anomaly where multiple stops get identical
        timestamps from a stale NJT data refresh."""
        base_time = now_et().replace(hour=8, minute=0, second=0, microsecond=0)

        journey = TrainJourney(
            train_id="3922B",
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

        builder = StopBuilder()

        # First cycle: Train at NP, NP explicitly departed
        np_dep_time_1 = base_time + timedelta(minutes=20)
        stops_cycle_1 = [
            _make_stop_with_sched_fields(
                builder,
                "TR",
                "Trenton",
                dep_time=base_time.strftime(NJT_TIME_FORMAT),
                departed=True,
                track="2",
            ),
            _make_stop_with_sched_fields(
                builder,
                "NP",
                "Newark Penn",
                dep_time=np_dep_time_1.strftime(NJT_TIME_FORMAT),
                arr_time=np_dep_time_1.strftime(NJT_TIME_FORMAT),
                departed=True,
                track="1",
            ),
            _make_stop_with_sched_fields(
                builder,
                "NY",
                "New York Penn",
                dep_time=(base_time + timedelta(minutes=40)).strftime(NJT_TIME_FORMAT),
                arr_time=(base_time + timedelta(minutes=38)).strftime(NJT_TIME_FORMAT),
                departed=False,
            ),
        ]
        await journey_collector.update_journey_stops(
            sqlite_session, journey, stops_cycle_1
        )
        await sqlite_session.flush()

        # Verify NP actual_departure was set from Tier 1 (api_explicit)
        np_stop = await sqlite_session.scalar(
            select(JourneyStop).where(
                JourneyStop.journey_id == journey.id,
                JourneyStop.station_code == "NP",
            )
        )
        assert np_stop is not None
        assert np_stop.actual_departure == np_dep_time_1
        assert np_stop.departure_source == "api_explicit"

        # Second cycle: NJT no longer reports DEPARTED=YES for NP,
        # but NY is departed. NP falls into Tier 2 (sequential inference).
        # NJT has also changed the TIME for NP to a different (stale) value.
        stale_np_time = base_time + timedelta(minutes=50)  # wrong stale value
        stops_cycle_2 = [
            _make_stop_with_sched_fields(
                builder,
                "TR",
                "Trenton",
                dep_time=base_time.strftime(NJT_TIME_FORMAT),
                departed=True,
                track="2",
            ),
            _make_stop_with_sched_fields(
                builder,
                "NP",
                "Newark Penn",
                dep_time=np_dep_time_1.strftime(NJT_TIME_FORMAT),
                arr_time=stale_np_time.strftime(NJT_TIME_FORMAT),  # stale!
                departed=False,  # NJT no longer says YES
            ),
            _make_stop_with_sched_fields(
                builder,
                "NY",
                "New York Penn",
                dep_time=(base_time + timedelta(minutes=40)).strftime(NJT_TIME_FORMAT),
                arr_time=(base_time + timedelta(minutes=38)).strftime(NJT_TIME_FORMAT),
                departed=True,  # NY departed -> triggers Tier 2 for NP
            ),
        ]
        await journey_collector.update_journey_stops(
            sqlite_session, journey, stops_cycle_2
        )
        await sqlite_session.flush()

        # Verify NP actual_departure was NOT overwritten by Tier 2
        await sqlite_session.refresh(np_stop)
        assert np_stop.actual_departure == np_dep_time_1, (
            f"Tier 2 should not overwrite existing actual_departure "
            f"({np_dep_time_1}), but got {np_stop.actual_departure}"
        )


# ---------------------------------------------------------------------------
# 5. get_effective_observation_type changes
# ---------------------------------------------------------------------------


class TestEffectiveObservationType:
    """Test that SCHEDULED NJT trains are no longer promoted to OBSERVED."""

    def test_njt_scheduled_not_promoted(self):
        """A SCHEDULED NJT train should stay SCHEDULED even if departure
        time has passed, since it was never observed in real-time."""
        from trackrat.utils.train import get_effective_observation_type

        journey = MagicMock()
        journey.observation_type = "SCHEDULED"
        journey.data_source = "NJT"

        result = get_effective_observation_type(journey)
        assert (
            result == "SCHEDULED"
        ), f"NJT SCHEDULED train should not be promoted, got {result}"

    def test_observed_train_stays_observed(self):
        """An OBSERVED train should always return OBSERVED."""
        from trackrat.utils.train import get_effective_observation_type

        journey = MagicMock()
        journey.observation_type = "OBSERVED"
        journey.data_source = "NJT"

        result = get_effective_observation_type(journey)
        assert result == "OBSERVED"

    def test_amtrak_scheduled_still_promoted(self):
        """An Amtrak SCHEDULED train should still be promoted to OBSERVED
        after departure time passes. Amtrak uses pattern-based scheduling
        and relies on auto-promotion for trains that haven't been discovered
        yet. Unlike NJT, Amtrak has no reconciliation job."""
        from trackrat.utils.train import get_effective_observation_type

        past_time = now_et() - timedelta(hours=1)

        journey = MagicMock()
        journey.observation_type = "SCHEDULED"
        journey.data_source = "AMTRAK"

        stop = MagicMock()
        stop.stop_sequence = 0
        stop.scheduled_departure = past_time
        stop.scheduled_arrival = None
        journey.stops = [stop]

        result = get_effective_observation_type(journey)
        assert result == "OBSERVED", (
            f"Amtrak SCHEDULED train should still be promoted after departure, "
            f"got {result}"
        )

    def test_patco_scheduled_promoted_after_departure(self):
        """A PATCO SCHEDULED train (no real-time API) should still be promoted
        to OBSERVED when departure time passes."""
        from trackrat.utils.train import get_effective_observation_type

        past_time = now_et() - timedelta(hours=1)

        journey = MagicMock()
        journey.observation_type = "SCHEDULED"
        journey.data_source = "PATCO"

        stop = MagicMock()
        stop.stop_sequence = 0
        stop.scheduled_departure = past_time
        stop.scheduled_arrival = None
        journey.stops = [stop]

        result = get_effective_observation_type(journey)
        assert (
            result == "OBSERVED"
        ), f"PATCO SCHEDULED train should be promoted after departure, got {result}"


# ---------------------------------------------------------------------------
# 6. Explicit cancellation reason
# ---------------------------------------------------------------------------


class TestExplicitCancellationReason:
    """Test that explicit NJT cancellations now set cancellation_reason."""

    @pytest.mark.asyncio
    async def test_all_stops_cancelled_sets_reason(
        self, sqlite_session: AsyncSession, journey_collector
    ):
        """When NJT API returns all stops as Cancelled, the journey should
        have both is_cancelled=True and a descriptive cancellation_reason."""
        base_time = now_et().replace(hour=8, minute=0, second=0, microsecond=0)

        journey = TrainJourney(
            train_id="CANCEL_TEST",
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

        # Create stops in DB first (check_journey_completion queries the DB)
        for i, (code, name) in enumerate([("TR", "Trenton"), ("NY", "New York")]):
            stop = JourneyStop(
                journey_id=journey.id,
                station_code=code,
                station_name=name,
                stop_sequence=i,
                scheduled_departure=base_time + timedelta(minutes=i * 30),
            )
            sqlite_session.add(stop)
        await sqlite_session.flush()

        # NJT says all stops cancelled
        builder = StopBuilder()
        stops_data = [
            _make_stop_with_sched_fields(
                builder,
                "TR",
                "Trenton",
                dep_time=base_time.strftime(NJT_TIME_FORMAT),
                cancelled=True,
            ),
            _make_stop_with_sched_fields(
                builder,
                "NY",
                "New York",
                dep_time=(base_time + timedelta(minutes=30)).strftime(NJT_TIME_FORMAT),
                arr_time=(base_time + timedelta(minutes=30)).strftime(NJT_TIME_FORMAT),
                cancelled=True,
            ),
        ]

        await journey_collector.check_journey_completion(
            sqlite_session, journey, stops_data
        )

        assert journey.is_cancelled is True
        assert journey.cancellation_reason == "All stops cancelled by NJT", (
            f"Expected reason 'All stops cancelled by NJT', "
            f"got {journey.cancellation_reason!r}"
        )

    @pytest.mark.asyncio
    async def test_uppercase_cancelled_detected(
        self, sqlite_session: AsyncSession, journey_collector
    ):
        """STOP_STATUS='CANCELLED' (uppercase) is the normalized form after
        the Pydantic field_validator on NJTransitStopData.

        Since tests use MagicMock (bypassing Pydantic), we set STOP_STATUS
        to uppercase directly to simulate the post-normalization state."""
        base_time = now_et().replace(hour=8, minute=0, second=0, microsecond=0)

        journey = TrainJourney(
            train_id="3883",
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

        # Create stops in DB first (check_journey_completion queries the DB)
        for i, (code, name) in enumerate([("TR", "Trenton"), ("NY", "New York")]):
            stop = JourneyStop(
                journey_id=journey.id,
                station_code=code,
                station_name=name,
                stop_sequence=i,
                scheduled_departure=base_time + timedelta(minutes=i * 30),
            )
            sqlite_session.add(stop)
        await sqlite_session.flush()

        # NJT returns UPPERCASE 'CANCELLED' for all stops
        builder = StopBuilder()
        stops_data = [
            _make_stop_with_sched_fields(
                builder,
                "TR",
                "Trenton",
                dep_time=base_time.strftime(NJT_TIME_FORMAT),
                cancelled=True,
            ),
            _make_stop_with_sched_fields(
                builder,
                "NY",
                "New York",
                dep_time=(base_time + timedelta(minutes=30)).strftime(NJT_TIME_FORMAT),
                arr_time=(base_time + timedelta(minutes=30)).strftime(NJT_TIME_FORMAT),
                cancelled=True,
            ),
        ]
        # Override STOP_STATUS to uppercase (simulating real NJT API behavior)
        for stop in stops_data:
            stop.STOP_STATUS = "CANCELLED"

        await journey_collector.check_journey_completion(
            sqlite_session, journey, stops_data
        )

        assert journey.is_cancelled is True, (
            f"Expected is_cancelled=True for uppercase 'CANCELLED' stops, "
            f"got {journey.is_cancelled}"
        )
        assert journey.cancellation_reason == "All stops cancelled by NJT", (
            f"Expected reason 'All stops cancelled by NJT', "
            f"got {journey.cancellation_reason!r}"
        )

    @pytest.mark.asyncio
    async def test_mixed_case_cancelled_detected(
        self, sqlite_session: AsyncSession, journey_collector
    ):
        """All stops with STOP_STATUS='CANCELLED' after Pydantic normalization.
        In production, NJT mixed casing (e.g., 'Cancelled', 'CANCELLED') is
        normalized to uppercase by NJTransitStopData.normalize_stop_status."""
        base_time = now_et().replace(hour=8, minute=0, second=0, microsecond=0)

        journey = TrainJourney(
            train_id="3885",
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

        for i, (code, name) in enumerate([("TR", "Trenton"), ("NP", "Newark"), ("NY", "New York")]):
            stop = JourneyStop(
                journey_id=journey.id,
                station_code=code,
                station_name=name,
                stop_sequence=i,
                scheduled_departure=base_time + timedelta(minutes=i * 15),
            )
            sqlite_session.add(stop)
        await sqlite_session.flush()

        builder = StopBuilder()
        stops_data = [
            _make_stop_with_sched_fields(
                builder,
                "TR",
                "Trenton",
                dep_time=base_time.strftime(NJT_TIME_FORMAT),
                cancelled=True,
            ),
            _make_stop_with_sched_fields(
                builder,
                "NP",
                "Newark",
                dep_time=(base_time + timedelta(minutes=15)).strftime(NJT_TIME_FORMAT),
                arr_time=(base_time + timedelta(minutes=15)).strftime(NJT_TIME_FORMAT),
                cancelled=True,
            ),
            _make_stop_with_sched_fields(
                builder,
                "NY",
                "New York",
                dep_time=(base_time + timedelta(minutes=30)).strftime(NJT_TIME_FORMAT),
                arr_time=(base_time + timedelta(minutes=30)).strftime(NJT_TIME_FORMAT),
                cancelled=True,
            ),
        ]
        # All stops uppercase (post-normalization state)
        # StopBuilder already uses "CANCELLED"; explicit override for clarity
        for stop in stops_data:
            stop.STOP_STATUS = "CANCELLED"

        await journey_collector.check_journey_completion(
            sqlite_session, journey, stops_data
        )

        assert journey.is_cancelled is True, (
            f"Expected is_cancelled=True for mixed-case cancelled stops, "
            f"got {journey.is_cancelled}"
        )

    @pytest.mark.asyncio
    async def test_null_stop_status_not_treated_as_cancelled(
        self, sqlite_session: AsyncSession, journey_collector
    ):
        """A stop with STOP_STATUS=None should not be counted as cancelled.
        The Pydantic validator passes None through unchanged; the
        (stop.STOP_STATUS or '') guard handles it safely downstream."""
        base_time = now_et().replace(hour=8, minute=0, second=0, microsecond=0)

        journey = TrainJourney(
            train_id="NULL_STATUS",
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

        for i, (code, name) in enumerate([("TR", "Trenton"), ("NY", "New York")]):
            stop = JourneyStop(
                journey_id=journey.id,
                station_code=code,
                station_name=name,
                stop_sequence=i,
                scheduled_departure=base_time + timedelta(minutes=i * 30),
            )
            sqlite_session.add(stop)
        await sqlite_session.flush()

        builder = StopBuilder()
        stops_data = [
            _make_stop_with_sched_fields(
                builder,
                "TR",
                "Trenton",
                dep_time=base_time.strftime(NJT_TIME_FORMAT),
                cancelled=True,
            ),
            _make_stop_with_sched_fields(
                builder,
                "NY",
                "New York",
                dep_time=(base_time + timedelta(minutes=30)).strftime(NJT_TIME_FORMAT),
                arr_time=(base_time + timedelta(minutes=30)).strftime(NJT_TIME_FORMAT),
                departed=False,
            ),
        ]
        # First stop cancelled, second has None STOP_STATUS
        stops_data[0].STOP_STATUS = "CANCELLED"
        stops_data[1].STOP_STATUS = None

        await journey_collector.check_journey_completion(
            sqlite_session, journey, stops_data
        )

        assert journey.is_cancelled is False, (
            f"Journey should NOT be cancelled when only some stops are cancelled, "
            f"got is_cancelled={journey.is_cancelled}"
        )


# ---------------------------------------------------------------------------
# 7. Pydantic field validators normalize NJT API values
# ---------------------------------------------------------------------------


class TestNJTransitStopDataNormalization:
    """Test that NJTransitStopData normalizes DEPARTED and STOP_STATUS to uppercase."""

    def test_departed_normalized_to_uppercase(self):
        """DEPARTED field should be normalized to uppercase on parse."""
        from trackrat.models.api import NJTransitStopData

        stop = NJTransitStopData(DEPARTED="yes")
        assert stop.DEPARTED == "YES", (
            f"Expected DEPARTED='YES' after normalization, got {stop.DEPARTED!r}"
        )

    def test_stop_status_normalized_to_uppercase(self):
        """STOP_STATUS field should be normalized to uppercase on parse."""
        from trackrat.models.api import NJTransitStopData

        stop = NJTransitStopData(STOP_STATUS="Cancelled")
        assert stop.STOP_STATUS == "CANCELLED", (
            f"Expected STOP_STATUS='CANCELLED' after normalization, "
            f"got {stop.STOP_STATUS!r}"
        )

    def test_none_values_pass_through(self):
        """None values should not be modified by validators."""
        from trackrat.models.api import NJTransitStopData

        stop = NJTransitStopData(DEPARTED=None, STOP_STATUS=None)
        assert stop.DEPARTED is None
        assert stop.STOP_STATUS is None

    def test_mixed_case_stop_status_normalized(self):
        """Mixed case like '5 Minutes Late' should become '5 MINUTES LATE'."""
        from trackrat.models.api import NJTransitStopData

        stop = NJTransitStopData(STOP_STATUS="5 Minutes Late")
        assert stop.STOP_STATUS == "5 MINUTES LATE", (
            f"Expected '5 MINUTES LATE', got {stop.STOP_STATUS!r}"
        )
