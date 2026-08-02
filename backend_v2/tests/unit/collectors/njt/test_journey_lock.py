"""
Tests for the cross-replica NJT journey lock (issue #1369).

Three writers can mutate the same journey's `journey_stops` concurrently
across replicas: JIT refresh (`services/departure.py`), scheduled collection
(`services/scheduler.py`), and the nightly schedule rebuild
(`collectors/njt/schedule.py`). All three now call
`acquire_njt_journey_lock` before touching stops. These tests exercise the
lock itself against a real PostgreSQL database (two independent sessions,
standing in for two replicas) rather than mocking it away, since the whole
point is verifying real cross-connection blocking behavior.
"""

import asyncio
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trackrat.utils.locks import JourneyLockTimeout, acquire_njt_journey_lock


@pytest.fixture
def session_factory(db_engine):
    """Factory for independent sessions bound to the same engine.

    Each session pulls its own pooled connection, so two sessions from this
    factory behave like two separate replicas for advisory-lock purposes.
    """
    return async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)


class TestAcquireNjtJourneyLock:
    """Real-Postgres tests for the transaction-scoped advisory lock."""

    @pytest.mark.asyncio
    async def test_blocks_second_session_for_same_train_and_date(self, session_factory):
        """A second replica must wait for the first to finish before it can
        acquire the lock for the same train_id + journey_date."""
        train_id = "3924"
        journey_date = date.today()

        session_a = session_factory()
        session_b = session_factory()
        try:
            await acquire_njt_journey_lock(session_a, train_id, journey_date)

            waiter = asyncio.create_task(
                acquire_njt_journey_lock(session_b, train_id, journey_date)
            )

            # Give session_b's query time to reach Postgres and start
            # waiting, then confirm it's genuinely stuck behind session_a.
            await asyncio.sleep(0.3)
            assert (
                not waiter.done()
            ), "second session acquired the lock while the first still held it"

            # Ending session_a's transaction must release the lock and
            # unblock session_b.
            await session_a.commit()
            await asyncio.wait_for(waiter, timeout=5)
            assert waiter.exception() is None

            await session_b.commit()
        finally:
            await session_a.close()
            await session_b.close()

    @pytest.mark.asyncio
    async def test_does_not_block_different_train_ids(self, session_factory):
        """Different lock keys must not serialize each other, or every
        journey in a batch collection run would contend on one lock."""
        journey_date = date.today()

        session_a = session_factory()
        session_b = session_factory()
        try:
            await acquire_njt_journey_lock(session_a, "3924", journey_date)

            # Must complete promptly; a bug that ignores train_id in the
            # lock key would make this hang until session_a commits.
            await asyncio.wait_for(
                acquire_njt_journey_lock(session_b, "3925", journey_date),
                timeout=2,
            )

            await session_a.commit()
            await session_b.commit()
        finally:
            await session_a.close()
            await session_b.close()

    @pytest.mark.asyncio
    async def test_released_on_rollback(self, session_factory):
        """A rolled-back transaction must release the lock too, not just a
        commit -- collect_journey_details rolls back on several early-return
        error paths."""
        train_id = "3926"
        journey_date = date.today()

        session_a = session_factory()
        session_b = session_factory()
        try:
            await acquire_njt_journey_lock(session_a, train_id, journey_date)
            await session_a.rollback()

            await asyncio.wait_for(
                acquire_njt_journey_lock(session_b, train_id, journey_date),
                timeout=2,
            )
            await session_b.commit()
        finally:
            await session_a.close()
            await session_b.close()

    @pytest.mark.asyncio
    async def test_raises_without_train_id(self, db_session):
        with pytest.raises(ValueError):
            await acquire_njt_journey_lock(db_session, None, date.today())

    @pytest.mark.asyncio
    async def test_raises_without_journey_date(self, db_session):
        with pytest.raises(ValueError):
            await acquire_njt_journey_lock(db_session, "3924", None)


class TestJourneyLockWaitBudget:
    """The wait for a contended lock is bounded (issue #1672).

    It used to block indefinitely, so a contended journey sat there until the
    engine's 55s `statement_timeout` cancelled the query -- and the resulting
    QueryCanceledError looks exactly like a genuinely slow query, so it could
    not be retried without also retrying every runaway statement in the app.
    """

    @pytest.mark.asyncio
    async def test_times_out_instead_of_waiting_forever(self, session_factory):
        train_id = "4105"
        journey_date = date.today()

        session_a = session_factory()
        session_b = session_factory()
        try:
            await acquire_njt_journey_lock(session_a, train_id, journey_date)

            started = asyncio.get_running_loop().time()
            with pytest.raises(JourneyLockTimeout):
                await acquire_njt_journey_lock(
                    session_b, train_id, journey_date, timeout_seconds=0.3
                )
            elapsed = asyncio.get_running_loop().time() - started

            # Must give up on its own budget, nowhere near the 55s
            # statement_timeout that used to end these waits.
            assert 0.3 <= elapsed < 5, f"gave up after {elapsed:.2f}s"

            await session_a.commit()
        finally:
            await session_a.close()
            await session_b.close()

    @pytest.mark.asyncio
    async def test_acquires_within_budget_once_the_holder_commits(
        self, session_factory
    ):
        """The budget is a ceiling, not a fixed delay: a lock released partway
        through must be picked up promptly rather than after the full wait."""
        train_id = "4106"
        journey_date = date.today()

        session_a = session_factory()
        session_b = session_factory()
        try:
            await acquire_njt_journey_lock(session_a, train_id, journey_date)

            async def release_shortly() -> None:
                await asyncio.sleep(0.2)
                await session_a.commit()

            releaser = asyncio.create_task(release_shortly())

            started = asyncio.get_running_loop().time()
            await acquire_njt_journey_lock(
                session_b, train_id, journey_date, timeout_seconds=5
            )
            elapsed = asyncio.get_running_loop().time() - started

            await releaser
            assert elapsed < 2, f"took {elapsed:.2f}s to notice the release"

            await session_b.commit()
        finally:
            await session_a.close()
            await session_b.close()

    @pytest.mark.asyncio
    async def test_uncontended_acquire_is_immediate(self, session_factory):
        """The common case must not pay for the polling loop."""
        session = session_factory()
        try:
            started = asyncio.get_running_loop().time()
            await acquire_njt_journey_lock(session, "4107", date.today())
            elapsed = asyncio.get_running_loop().time() - started

            assert elapsed < 1, f"uncontended acquire took {elapsed:.2f}s"
            await session.commit()
        finally:
            await session.close()
