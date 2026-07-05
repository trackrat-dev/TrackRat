"""
Integration test: retention_cleanup executes its SQL against real Postgres.

The existing unit tests in tests/unit/test_retention_cleanup.py drive
retention_cleanup with MagicMock sessions, so the DELETE statements are never
sent to Postgres and a malformed statement passes silently. That is exactly how
the phase-1 bug shipped: ``make_interval(days => CASE ... END)`` over untyped
bind params resolved to ``make_interval(days => text)``, which does not exist,
so every nightly run aborted with ``retention_cleanup_failed`` and nothing was
pruned.

This regression test runs the whole job against the real partitioned schema
(see conftest.py's ``db_engine`` fixture) with journeys spanning both retention
windows, so a type/planner error in the SQL fails the test here instead of only
surfacing in production logs.
"""

import contextlib
from datetime import UTC, date, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trackrat.models.database import TrainJourney
from trackrat.services.scheduler import SchedulerService


def _make_journey(train_id: str, data_source: str, days_ago: int) -> TrainJourney:
    """A minimal OBSERVED journey dated ``days_ago`` days in the past."""
    journey_date = date.today() - timedelta(days=days_ago)
    return TrainJourney(
        train_id=train_id,
        journey_date=journey_date,
        line_code="X",
        destination="DEST",
        origin_station_code="AAA",
        terminal_station_code="BBB",
        data_source=data_source,
        observation_type="OBSERVED",
        scheduled_departure=datetime(
            journey_date.year, journey_date.month, journey_date.day, 12, 0, tzinfo=UTC
        ),
    )


@pytest.mark.asyncio
class TestRetentionCleanupRealPostgres:
    async def test_prunes_each_source_on_its_own_window(
        self, db_engine, db_session: AsyncSession
    ):
        """retention_cleanup must delete SUBWAY past its 14-day window and other
        sources past the 60-day window, while leaving in-window rows — running
        the real DELETE SQL against Postgres, not a mock.

        Guards against the ``make_interval(days => text)`` regression: if the
        phase-1 statement fails to plan, the job aborts, nothing is deleted, and
        all four rows survive — which this test asserts against.
        """
        sessionmaker = async_sessionmaker(
            db_engine, expire_on_commit=False, class_=AsyncSession
        )

        @contextlib.asynccontextmanager
        async def fake_get_session():
            """Mirror the production get_session commit/rollback contract so
            each phase's DELETE is committed exactly as it would be in prod."""
            async with sessionmaker() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        # Two SUBWAY rows straddling the 14-day subway window and two non-SUBWAY
        # rows straddling the 60-day general window. Note NJT_MID (30 days) is
        # past the subway window but must survive because it is NOT subway —
        # this is what the per-source CASE has to get right.
        seed = [
            _make_journey("SUB_OLD", "SUBWAY", days_ago=20),  # > 14d -> deleted
            _make_journey("SUB_NEW", "SUBWAY", days_ago=5),  # <= 14d -> kept
            _make_journey("NJT_MID", "NJT", days_ago=30),  # <= 60d -> kept
            _make_journey("NJT_OLD", "NJT", days_ago=90),  # > 60d -> deleted
        ]
        for journey in seed:
            db_session.add(journey)
        await db_session.commit()

        mock_settings = Mock()
        mock_settings.retention_days = 60
        mock_settings.subway_retention_days = 14

        service = SchedulerService.__new__(SchedulerService)

        async def run_task(
            db=None, task_name=None, minimum_interval_seconds=None, task_func=None
        ):
            await task_func()
            return True

        with (
            patch(
                "trackrat.services.scheduler.get_settings",
                return_value=mock_settings,
            ),
            patch("trackrat.services.scheduler.get_session", fake_get_session),
            patch(
                "trackrat.services.scheduler.run_with_freshness_check",
                side_effect=run_task,
            ),
        ):
            await service.retention_cleanup()

        async with sessionmaker() as verify:
            survivors = (
                (
                    await verify.execute(
                        select(TrainJourney.train_id).order_by(TrainJourney.train_id)
                    )
                )
                .scalars()
                .all()
            )

        assert survivors == ["NJT_MID", "SUB_NEW"], (
            "retention_cleanup should keep only the in-window rows; "
            f"got {survivors!r}. If all four survived, the phase-1 DELETE "
            "failed to execute (e.g. the make_interval type regression)."
        )
