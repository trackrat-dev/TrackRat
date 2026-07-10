"""
Integration tests: retention_cleanup executes its SQL against real Postgres.

The unit tests in tests/unit/test_retention_cleanup.py drive retention_cleanup
with MagicMock sessions, so the DELETE statements are never sent to Postgres and
a malformed statement passes silently. Two real bugs shipped through that gap:

1. The per-source cutoff SQL. ``make_interval(days => CASE ... END)`` over
   untyped bind params first resolved to ``make_interval(days => text)`` (does
   not exist); a later "fix" rewrote it to ``:subway_days::int``, which is worse
   — SQLAlchemy's ``text()`` bind-param parser refuses to substitute a ``:name``
   immediately followed by ``::``, so the literal ``:subway_days`` reaches
   Postgres and it raises a syntax error. Both forms made every nightly run
   abort. The working form is ``CAST(:name AS int)``.

2. do_retention_work swallowed its own exception and returned normally, so
   ``run_with_freshness_check`` recorded every failed run as a success (it only
   updates ``last_successful_run`` when task_func returns without raising). That
   masked the failure in ``scheduler_task_runs`` and skipped the next scheduled
   run as "still fresh" for ~21h.

These tests run the whole job against the real schema so a SQL error in any
phase fails here, and assert the freshness bookkeeping reflects reality.
"""

import contextlib
from datetime import UTC, date, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trackrat.models.database import (
    DiscoveryRun,
    SchedulerTaskRun,
    ServiceAlert,
    TrainJourney,
    ValidationResult,
)
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


def _sessionmaker(db_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)


def _patched_get_session(sessionmaker):
    """A get_session replacement that mirrors the production commit/rollback
    contract, so each phase's DELETE is committed exactly as it would be in prod."""

    @contextlib.asynccontextmanager
    async def fake_get_session():
        async with sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return fake_get_session


async def _passthrough_freshness(
    db=None, task_name=None, minimum_interval_seconds=None, task_func=None
):
    """Stand-in for run_with_freshness_check that always runs the task (bypasses
    the freshness gate) and propagates any exception, so a broken phase surfaces
    as a test failure rather than being hidden by the gate."""
    await task_func()
    return True


@pytest.mark.asyncio
class TestRetentionCleanupRealPostgres:
    async def test_prunes_every_phase_on_real_postgres(
        self, db_engine, db_session: AsyncSession
    ):
        """All four DELETE phases must execute against real Postgres and prune
        the right rows: SUBWAY past its 14-day window and other sources past the
        60-day window (train_journeys), plus aged discovery_runs /
        validation_results / inactive service_alerts — while leaving in-window
        journeys and still-active alerts.

        Guards against both the ``:name::int`` / ``make_interval(days => text)``
        SQL regressions (any of which makes a phase raise) and any per-source
        CASE mistake.
        """
        sessionmaker = _sessionmaker(db_engine)
        old = datetime.now(UTC) - timedelta(days=90)

        journeys = [
            _make_journey("SUB_OLD", "SUBWAY", days_ago=20),  # > 14d -> deleted
            _make_journey("SUB_NEW", "SUBWAY", days_ago=5),  # <= 14d -> kept
            _make_journey("NJT_MID", "NJT", days_ago=30),  # <= 60d -> kept
            _make_journey("NJT_OLD", "NJT", days_ago=90),  # > 60d -> deleted
        ]
        for journey in journeys:
            db_session.add(journey)
        # Phase 2/3/4 fixtures: one aged row per table (should be deleted) plus a
        # still-active alert that must survive regardless of age.
        db_session.add(DiscoveryRun(station_code="NY", run_at=old))
        db_session.add(
            ValidationResult(
                route="NY-TR",
                source="NJT",
                transit_train_count=0,
                api_train_count=0,
                coverage_percent=0.0,
                run_at=old,
            )
        )
        db_session.add(
            ServiceAlert(
                alert_id="resolved-1",
                data_source="SUBWAY",
                alert_type="alert",
                affected_route_ids=[],
                header_text="resolved",
                active_periods=[],
                is_active=False,
                updated_at=old,
            )
        )
        db_session.add(
            ServiceAlert(
                alert_id="active-1",
                data_source="SUBWAY",
                alert_type="alert",
                affected_route_ids=[],
                header_text="still active",
                active_periods=[],
                is_active=True,
                updated_at=old,
            )
        )
        await db_session.commit()

        mock_settings = Mock()
        mock_settings.retention_days = 60
        mock_settings.subway_retention_days = 14
        service = SchedulerService.__new__(SchedulerService)

        with (
            patch(
                "trackrat.services.scheduler.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "trackrat.services.scheduler.get_session",
                _patched_get_session(sessionmaker),
            ),
            patch(
                "trackrat.services.scheduler.run_with_freshness_check",
                side_effect=_passthrough_freshness,
            ),
        ):
            await service.retention_cleanup()

        async with sessionmaker() as verify:
            journeys_left = (
                (
                    await verify.execute(
                        select(TrainJourney.train_id).order_by(TrainJourney.train_id)
                    )
                )
                .scalars()
                .all()
            )
            discovery_left = (
                (await verify.execute(select(DiscoveryRun.id))).scalars().all()
            )
            validation_left = (
                (await verify.execute(select(ValidationResult.id))).scalars().all()
            )
            alerts_left = (
                (await verify.execute(select(ServiceAlert.alert_id))).scalars().all()
            )

        assert journeys_left == ["NJT_MID", "SUB_NEW"], (
            "phase 1 should keep only in-window journeys; got "
            f"{journeys_left!r}. All four surviving means the DELETE failed to "
            "execute (a make_interval / bind-param SQL regression)."
        )
        assert discovery_left == [], "phase 2 should delete the aged discovery_run"
        assert validation_left == [], "phase 3 should delete the aged validation_result"
        # Only the still-active alert survives; the aged inactive one is pruned.
        assert alerts_left == [
            "active-1"
        ], f"phase 4 should delete only the aged inactive alert; got {alerts_left!r}"

    async def test_failed_run_is_not_recorded_as_successful(
        self, db_engine, db_session: AsyncSession
    ):
        """A retention run that raises must NOT advance
        scheduler_task_runs.last_successful_run.

        Regression test for the swallow-exception bug: do_retention_work used to
        catch its own error and return normally, so run_with_freshness_check
        recorded the failed run as a success and bumped last_successful_run —
        masking the failure and gating the next run behind the freshness window.
        Uses the REAL run_with_freshness_check.
        """
        sessionmaker = _sessionmaker(db_engine)

        seeded = datetime(2020, 1, 1, tzinfo=UTC)
        db_session.add(
            SchedulerTaskRun(
                task_name="retention_cleanup",
                last_successful_run=seeded,
                run_count=5,
            )
        )
        await db_session.commit()

        mock_settings = Mock()
        mock_settings.retention_days = 60
        mock_settings.subway_retention_days = 14
        service = SchedulerService.__new__(SchedulerService)

        boom = RuntimeError("phase 0 blew up")

        async def _raise(*_a, **_k):
            raise boom

        with (
            patch(
                "trackrat.services.scheduler.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "trackrat.services.scheduler.get_session",
                _patched_get_session(sessionmaker),
            ),
            # Make do_retention_work fail at phase 0 (inside its try block).
            patch(
                "trackrat.services.scheduler.ensure_future_partitions",
                side_effect=_raise,
            ),
        ):
            # The real freshness wrapper catches the propagated exception, so the
            # public method does not raise.
            await service.retention_cleanup()

        async with sessionmaker() as verify:
            row = (
                await verify.execute(
                    select(SchedulerTaskRun).where(
                        SchedulerTaskRun.task_name == "retention_cleanup"
                    )
                )
            ).scalar_one()

        assert row.last_successful_run == seeded, (
            "a failed retention run must not advance last_successful_run "
            f"(got {row.last_successful_run!r}, expected {seeded!r}) — otherwise "
            "the failure is masked and the next scheduled run is skipped as fresh."
        )
        assert row.run_count == 5, "run_count must not increment on a failed run"
