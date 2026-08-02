"""
Tests for the NJT nightly schedule job's transaction scope (issue #1672).

`_collect_stop_lists_for_scheduled_trains` takes a transaction-scoped advisory
lock per journey (`acquire_njt_journey_lock`, inside `_update_journey_with_stops`)
while looping over every SCHEDULED NJT train for today and tomorrow. It used to
commit once, after the loop, so a single transaction accumulated the lock for
every journey it had already processed and held them for the whole run --
3-5 minutes across ~530-760 trains on production. JIT and station-board
refreshes then blocked on `pg_advisory_xact_lock` until the 55s
`statement_timeout` killed them, reproducibly in the 04:30-04:35 UTC window
(confirmed against production logs: the job's `stop_collection_completed`
timestamp matched the last error of each nightly cluster to the second).

These tests run against a real PostgreSQL database because the behavior under
test *is* cross-connection lock visibility -- `acquire_njt_journey_lock` is a
documented no-op on SQLite, so a SQLite-backed test would pass against the
broken code.

The scan these tests drive has no ORDER BY, so nothing here may assume which
train is processed first: the fixtures park the run on a *call number* and read
the train ids back out of the stub.
"""

import asyncio
from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trackrat.collectors.njt.schedule import NJTScheduleCollector
from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.locks import acquire_njt_journey_lock
from trackrat.utils.time import now_et

from tests.fixtures.njt_api_responses import NJT_TIME_FORMAT, StopBuilder


@pytest.fixture
def session_factory(db_engine):
    """Factory for independent sessions bound to the same engine.

    Each session pulls its own pooled connection, so a session from this
    factory stands in for a second replica (or a concurrent JIT refresh)
    competing for the same advisory lock.
    """
    return async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)


class _TrainData:
    """Minimal stand-in for the getTrainStopList response envelope."""

    def __init__(self, stops: list[Any]):
        self.STOPS = stops


class _StubNJTClient:
    """Stands in for the NJT HTTP client.

    Only the outbound HTTP call is stubbed -- the database, the advisory lock
    and the collector logic under test are all real.

    `park_at_call` blocks the Nth call until `resume` is set, which is the only
    way to observe what locks are held *while* a run is still in flight.
    Failures are keyed by call number as well as train id so a test can force a
    rollback without knowing the scan order.
    """

    def __init__(
        self,
        stops_by_train: dict[str, list[Any]],
        park_at_call: int | None = None,
        fail_at_calls: set[int] | None = None,
        fail_trains: set[str] | None = None,
    ):
        self.stops_by_train = stops_by_train
        self.park_at_call = park_at_call
        self.fail_at_calls = fail_at_calls or set()
        self.fail_trains = fail_trains or set()
        self.resume = asyncio.Event()
        self.calls: list[str] = []

    async def get_train_stop_list(self, train_id: str) -> Any:
        self.calls.append(train_id)
        call_number = len(self.calls)

        if self.park_at_call is not None and call_number == self.park_at_call:
            await self.resume.wait()

        if call_number in self.fail_at_calls or train_id in self.fail_trains:
            raise RuntimeError(f"NJT API returned null data for train {train_id}")

        return _TrainData(self.stops_by_train[train_id])


async def _wait_for_call_count(client: _StubNJTClient, count: int) -> None:
    """Block until the collector has issued `count` API calls."""
    for _ in range(200):
        if len(client.calls) >= count:
            return
        await asyncio.sleep(0.05)
    raise AssertionError(
        f"collector issued {len(client.calls)} calls, expected at least {count}"
    )


def _build_stops(builder: StopBuilder, base_hour: int) -> list[Any]:
    """Two-stop NJT stop list, shaped like a real getTrainStopList payload.

    `_update_journey_with_stops` reads SCHED_ARR_DATE / SCHED_DEP_DATE (not
    TIME / DEP_TIME), so the origin carries a parseable SCHED_DEP_DATE.
    """
    origin_sched = (
        now_et()
        .replace(hour=base_hour, minute=0, second=0, microsecond=0)
        .strftime(NJT_TIME_FORMAT)
    )
    return [
        builder.build_stop(
            station_code="NY",
            station_name="New York Penn",
            dep_time=f"{base_hour:02d}:00:00 AM",
            sched_dep_date=origin_sched,
        ),
        builder.build_stop(
            station_code="TR",
            station_name="Trenton",
            dep_time=f"{base_hour:02d}:55:00 AM",
        ),
    ]


async def _seed_scheduled_journey(
    session: AsyncSession, train_id: str, journey_date: date
) -> int:
    """Insert one SCHEDULED NJT journey the way the nightly job's first pass does."""
    journey = TrainJourney(
        train_id=train_id,
        journey_date=journey_date,
        line_code="NE",
        line_name="Northeast Corridor",
        destination="Trenton",
        origin_station_code="NY",
        terminal_station_code="TR",
        data_source="NJT",
        observation_type="SCHEDULED",
        has_complete_journey=False,
        first_seen_at=now_et(),
        last_updated_at=now_et(),
    )
    session.add(journey)
    await session.commit()
    return int(journey.id)


class TestScheduleStopCollectionLockScope:
    """The advisory lock must not outlive the train that took it."""

    @pytest.mark.asyncio
    async def test_lock_released_before_next_train_is_fetched(self, session_factory):
        """The regression.

        With the loop parked on its second train, the *first* train's advisory
        lock must already be free. Under the old single-commit shape it stayed
        held until the whole batch committed, which is what starved the
        overnight JIT and station-board refreshes into statement timeouts.
        """
        journey_date = now_et().date()
        builder = StopBuilder()

        setup = session_factory()
        try:
            await _seed_scheduled_journey(setup, "3901", journey_date)
            await _seed_scheduled_journey(setup, "3902", journey_date)
        finally:
            await setup.close()

        client = _StubNJTClient(
            stops_by_train={
                "3901": _build_stops(builder, 6),
                "3902": _build_stops(builder, 7),
            },
            park_at_call=2,
        )
        collector = NJTScheduleCollector(client=client)

        run_session = session_factory()
        contender = session_factory()
        try:
            run = asyncio.create_task(
                collector._collect_stop_lists_for_scheduled_trains(run_session)
            )

            # Parked inside the second train's fetch => the first train has
            # been fully processed and its transaction should have ended.
            await _wait_for_call_count(client, 2)
            assert not run.done()
            first_train = client.calls[0]

            # The decisive assertion. Before the fix this blocked until the
            # final commit and wait_for raised TimeoutError.
            await asyncio.wait_for(
                acquire_njt_journey_lock(contender, first_train, journey_date),
                timeout=5,
            )
            await contender.rollback()

            client.resume.set()
            stats = await asyncio.wait_for(run, timeout=15)
            assert stats["stop_collections_successful"] == 2
            assert stats["stop_collections_failed"] == 0
        finally:
            client.resume.set()
            await contender.close()
            await run_session.close()

    @pytest.mark.asyncio
    async def test_first_train_is_committed_before_batch_completes(
        self, session_factory
    ):
        """Per-train commit, observed from an independent connection.

        Lock release and durability are two views of the same property: the
        lock is transaction-scoped, so it can only have been released if the
        transaction ended -- and only a commit (not a rollback) also makes the
        first train's stops visible to another connection mid-run.
        """
        journey_date = now_et().date()
        builder = StopBuilder()

        setup = session_factory()
        try:
            await _seed_scheduled_journey(setup, "3911", journey_date)
            await _seed_scheduled_journey(setup, "3912", journey_date)
        finally:
            await setup.close()

        client = _StubNJTClient(
            stops_by_train={
                "3911": _build_stops(builder, 6),
                "3912": _build_stops(builder, 7),
            },
            park_at_call=2,
        )
        collector = NJTScheduleCollector(client=client)

        run_session = session_factory()
        observer = session_factory()
        try:
            run = asyncio.create_task(
                collector._collect_stop_lists_for_scheduled_trains(run_session)
            )

            await _wait_for_call_count(client, 2)
            first_train = client.calls[0]

            stops = (
                await observer.scalars(
                    select(JourneyStop)
                    .join(TrainJourney, JourneyStop.journey_id == TrainJourney.id)
                    .where(TrainJourney.train_id == first_train)
                    .order_by(JourneyStop.stop_sequence)
                )
            ).all()
            assert [s.station_code for s in stops] == ["NY", "TR"], (
                f"train {first_train}'s stops are not visible from another "
                "connection while the batch is still running -- the run is "
                "still batching every train into one transaction"
            )

            client.resume.set()
            await asyncio.wait_for(run, timeout=15)
        finally:
            client.resume.set()
            await observer.close()
            await run_session.close()

    @pytest.mark.asyncio
    async def test_failed_train_rolls_back_without_losing_earlier_trains(
        self, session_factory
    ):
        """A mid-batch failure must not undo already-committed trains.

        This is what the removed `begin_nested()` savepoint bought, and the
        replacement (a `session.rollback()` per failure) has to preserve it.
        The rollback also expires every instance in the session, so this
        doubles as the guard against the MissingGreenlet trap that made the
        original loop snapshot `train_id` before its try block: the next
        iteration re-materializes its journey through an awaited `session.get`.
        """
        journey_date = now_et().date()
        builder = StopBuilder()

        setup = session_factory()
        try:
            for train_id in ("3921", "3922", "3923"):
                await _seed_scheduled_journey(setup, train_id, journey_date)
        finally:
            await setup.close()

        client = _StubNJTClient(
            stops_by_train={
                "3921": _build_stops(builder, 6),
                "3922": _build_stops(builder, 7),
                "3923": _build_stops(builder, 8),
            },
            fail_trains={"3922"},
        )
        collector = NJTScheduleCollector(client=client)

        run_session = session_factory()
        observer = session_factory()
        try:
            stats = await collector._collect_stop_lists_for_scheduled_trains(run_session)

            assert stats["stop_collections_attempted"] == 3
            assert stats["stop_collections_successful"] == 2
            assert stats["stop_collections_failed"] == 1

            # The loop kept going after the rollback and reached every train.
            assert sorted(client.calls) == ["3921", "3922", "3923"]

            journeys = {
                j.train_id: j
                for j in (
                    await observer.scalars(
                        select(TrainJourney).where(TrainJourney.data_source == "NJT")
                    )
                ).all()
            }
            assert journeys["3921"].has_complete_journey is True
            assert journeys["3923"].has_complete_journey is True
            assert (
                journeys["3922"].has_complete_journey is False
            ), "the failed train's partial write survived its rollback"

            failed_stops = (
                await observer.scalars(
                    select(JourneyStop)
                    .join(TrainJourney, JourneyStop.journey_id == TrainJourney.id)
                    .where(TrainJourney.train_id == "3922")
                )
            ).all()
            assert failed_stops == []
        finally:
            await observer.close()
            await run_session.close()

    @pytest.mark.asyncio
    async def test_journey_deleted_mid_batch_does_not_abandon_the_run(
        self, session_factory
    ):
        """Rows can vanish between the up-front scan and a journey's turn.

        The loop now snapshots ids rather than carrying ORM instances across
        transaction boundaries, so a journey it re-reads may be gone. That has
        to cost one train, not the rest of the batch. Failing the first two
        calls forces the rollbacks that expire the session, so the third
        iteration genuinely re-reads from the database instead of being served
        a stale instance out of the identity map.
        """
        journey_date = now_et().date()
        builder = StopBuilder()
        seeded = ("3931", "3932", "3933")

        setup = session_factory()
        try:
            for train_id in seeded:
                await _seed_scheduled_journey(setup, train_id, journey_date)
        finally:
            await setup.close()

        client = _StubNJTClient(
            stops_by_train={
                "3931": _build_stops(builder, 6),
                "3932": _build_stops(builder, 7),
                "3933": _build_stops(builder, 8),
            },
            park_at_call=2,
            fail_at_calls={1, 2},
        )
        collector = NJTScheduleCollector(client=client)

        run_session = session_factory()
        deleter = session_factory()
        try:
            run = asyncio.create_task(
                collector._collect_stop_lists_for_scheduled_trains(run_session)
            )

            await _wait_for_call_count(client, 2)

            # Whichever train has not been fetched yet is the one still to
            # come; delete it out from under the run.
            remaining = set(seeded) - set(client.calls[:2])
            assert len(remaining) == 1
            doomed_train = remaining.pop()

            doomed = await deleter.scalar(
                select(TrainJourney).where(TrainJourney.train_id == doomed_train)
            )
            assert doomed is not None
            await deleter.delete(doomed)
            await deleter.commit()

            client.resume.set()
            stats = await asyncio.wait_for(run, timeout=15)

            # Two API failures plus one vanished row -- and the run still
            # returned its stats rather than raising out of the loop.
            assert stats["stop_collections_attempted"] == 3
            assert stats["stop_collections_successful"] == 0
            assert stats["stop_collections_failed"] == 3
        finally:
            client.resume.set()
            await deleter.close()
            await run_session.close()

    @pytest.mark.asyncio
    async def test_scan_window_still_covers_today_and_tomorrow_only(
        self, session_factory
    ):
        """The commit-scope rewrite must not have moved the selection window.

        NJT's 27-hour schedule window produces rows dated today *and* tomorrow
        (issue #1499); anything outside that pair must stay untouched.
        """
        today = now_et().date()
        builder = StopBuilder()

        setup = session_factory()
        try:
            await _seed_scheduled_journey(setup, "3941", today)
            await _seed_scheduled_journey(setup, "3942", today + timedelta(days=1))
            await _seed_scheduled_journey(setup, "3943", today + timedelta(days=2))
            await _seed_scheduled_journey(setup, "3944", today - timedelta(days=1))
        finally:
            await setup.close()

        # Out-of-window trains have no stub payload, so if the scan picked
        # them up they would raise KeyError and show up in `calls`.
        client = _StubNJTClient(
            stops_by_train={
                "3941": _build_stops(builder, 6),
                "3942": _build_stops(builder, 7),
            }
        )
        collector = NJTScheduleCollector(client=client)

        run_session = session_factory()
        try:
            stats = await collector._collect_stop_lists_for_scheduled_trains(run_session)
            assert sorted(client.calls) == ["3941", "3942"]
            assert stats["stop_collections_successful"] == 2
            assert stats["stop_collections_failed"] == 0
        finally:
            await run_session.close()
