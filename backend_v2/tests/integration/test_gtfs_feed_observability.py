"""Integration tests: a stuck GTFS feed is detectable without reading logs.

Issue #1646 — SUBWAY and MNR served a frozen static schedule every night for
thirteen days and nothing in the system said so. The refresh reported
``subway_refreshed: false``, which is exactly what a healthy, rate-limited
source reports, and the one durable record of the failure
(``gtfs_feed_info.error_message``) was written by ``_record_refresh_failure``
and then read by nothing at all.

These run against real PostgreSQL rather than mock sessions on purpose: the
whole defect was that the persisted state and the reported state disagreed, and
a mocked session cannot disagree with itself.
"""

import contextlib
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trackrat.models.database import GTFSFeedInfo
from trackrat.services.gtfs import (
    GTFS_STALE_FEED_HOURS,
    GTFSRefreshOutcome,
    GTFSService,
)
from trackrat.services.scheduler import SchedulerService
from trackrat.utils.time import now_et


async def _seed_feed(
    db: AsyncSession,
    data_source: str,
    *,
    parsed_hours_ago: float | None,
    trip_count: int | None = None,
    error_message: str | None = None,
) -> None:
    """Insert a gtfs_feed_info row in a given freshness state.

    ``parsed_hours_ago=None`` models a source that has a row but has never
    completed a parse — the state SUBWAY was actually in.
    """
    db.add(
        GTFSFeedInfo(
            data_source=data_source,
            feed_url=f"https://example.invalid/{data_source}.zip",
            last_downloaded_at=now_et(),
            last_successful_parse_at=(
                now_et() - timedelta(hours=parsed_hours_ago)
                if parsed_hours_ago is not None
                else None
            ),
            trip_count=trip_count,
            error_message=error_message,
        )
    )
    await db.commit()


def _patched_get_session(sessionmaker):
    """A get_session replacement mirroring the production commit/rollback
    contract, so the refresh job's writes land exactly as they would in prod."""

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
    """Stand-in for run_with_freshness_check that always runs the task."""
    await task_func()
    return True


async def _run_refresh_job(db_engine, outcomes: dict[str, GTFSRefreshOutcome]):
    """Drive `refresh_gtfs_feeds` end to end, returning the captured log events.

    Only the network-facing `refresh_feed` is stubbed — the staleness sweep it
    feeds runs against the real `gtfs_feed_info` rows, which is the whole point:
    the job's alarm must come from persisted state, not from the outcome the
    same run just reported.
    """
    sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)

    settings = Mock()
    settings.is_data_source_disabled = lambda source: source not in outcomes
    service = SchedulerService.__new__(SchedulerService)
    service.settings = settings
    service._running_tasks = {}

    async def fake_refresh_feed(self, db, source, force=False):
        return outcomes[source]

    with (
        patch(
            "trackrat.services.scheduler.get_session",
            _patched_get_session(sessionmaker),
        ),
        patch(
            "trackrat.services.scheduler.run_with_freshness_check",
            side_effect=_passthrough_freshness,
        ),
        patch.object(GTFSService, "refresh_feed", fake_refresh_feed),
        structlog.testing.capture_logs() as captured,
    ):
        await service.refresh_gtfs_feeds()

    return captured


def _completion_event(captured) -> dict:
    (event,) = [e for e in captured if e["event"] == "gtfs_feed_refresh_complete"]
    return event


@pytest.mark.asyncio
class TestFeedStatusesAgainstRealPostgres:
    async def test_reports_fresh_stale_never_parsed_and_absent(
        self, db_session: AsyncSession
    ):
        """The four states a source can be in must be distinguishable.

        The two that matter for #1646 are `never parsed` and `parsed long ago` —
        both were invisible before, and both mean the served schedule is not
        backed by a current feed.
        """
        await _seed_feed(db_session, "NJT", parsed_hours_ago=2, trip_count=1234)
        await _seed_feed(
            db_session,
            "SUBWAY",
            parsed_hours_ago=13 * 24,
            trip_count=83821,
            error_message="process: the number of query arguments cannot exceed 32767",
        )
        await _seed_feed(db_session, "MNR", parsed_hours_ago=None)

        statuses = {
            s.data_source: s
            for s in await GTFSService().get_feed_statuses(
                db_session, ["NJT", "SUBWAY", "MNR", "PATCO"]
            )
        }

        # Healthy source: recent parse, not stale, no error carried.
        assert statuses["NJT"].is_stale is False
        assert statuses["NJT"].age_hours == pytest.approx(2.0, abs=0.2)
        assert statuses["NJT"].trip_count == 1234
        assert statuses["NJT"].error_message is None

        # The #1646 shape: parsed once, frozen for thirteen days, and the
        # persisted error is now reachable instead of DB-only.
        assert statuses["SUBWAY"].is_stale is True
        assert statuses["SUBWAY"].age_hours == pytest.approx(312.0, abs=1.0)
        assert "32767" in statuses["SUBWAY"].error_message

        # Row exists but no parse ever completed — worse than stale, not unknown.
        assert statuses["MNR"].is_stale is True
        assert statuses["MNR"].age_hours is None
        assert statuses["MNR"].last_successful_parse_at is None

        # No row at all must not be silently dropped from the report.
        assert "PATCO" in statuses
        assert statuses["PATCO"].is_stale is True
        assert statuses["PATCO"].age_hours is None

    async def test_preserves_requested_order_and_reports_every_source(
        self, db_session: AsyncSession
    ):
        """Callers index the result positionally against their source list.

        A DB-order result would silently mislabel sources, which is a worse
        failure than the one being fixed.
        """
        await _seed_feed(db_session, "SUBWAY", parsed_hours_ago=1)
        await _seed_feed(db_session, "NJT", parsed_hours_ago=1)

        requested = ["MNR", "NJT", "PATCO", "SUBWAY"]
        statuses = await GTFSService().get_feed_statuses(db_session, requested)

        assert [s.data_source for s in statuses] == requested

    async def test_a_source_refreshed_last_night_is_not_stale(
        self, db_session: AsyncSession
    ):
        """Guards the threshold against alarming on normal operation.

        If a source that refreshed 23 hours ago read as stale, the nightly ERROR
        would fire for every source every night and be tuned out — recreating
        #1646's real problem (a signal nobody can act on) in a new place.
        """
        await _seed_feed(db_session, "LIRR", parsed_hours_ago=23)

        (status,) = await GTFSService().get_feed_statuses(db_session, ["LIRR"])

        assert status.is_stale is False
        assert GTFS_STALE_FEED_HOURS > 23


@pytest.mark.asyncio
class TestRefreshOutcomesAgainstRealPostgres:
    async def test_download_and_process_failures_report_distinct_outcomes(
        self, db_session: AsyncSession
    ):
        """The stage must survive into the outcome, not collapse to False.

        Telling a network failure apart from a parse crash is what would have
        pointed at the asyncpg bind-parameter cap immediately.
        """
        service = GTFSService()

        download = await service._record_refresh_failure(
            db_session, "SUBWAY", "download", OSError("connection reset")
        )
        process = await service._record_refresh_failure(
            db_session, "MNR", "process", ValueError("bad zip")
        )

        assert download is GTFSRefreshOutcome.FAILED_DOWNLOAD
        assert process is GTFSRefreshOutcome.FAILED_PROCESS
        assert download.is_failure and process.is_failure
        assert not download.refreshed and not process.refreshed

    async def test_failure_outcome_and_persisted_error_agree(
        self, db_session: AsyncSession
    ):
        """The returned outcome and the durable row must tell the same story.

        These are the two independent channels a reader has; #1646 happened
        because only one of them existed and it was never consulted.
        """
        service = GTFSService()

        outcome = await service._record_refresh_failure(
            db_session, "SUBWAY", "process", ValueError("cannot exceed 32767")
        )

        feed_info = (
            await db_session.execute(
                select(GTFSFeedInfo).where(GTFSFeedInfo.data_source == "SUBWAY")
            )
        ).scalar_one()

        assert outcome is GTFSRefreshOutcome.FAILED_PROCESS
        assert feed_info.error_message.startswith("process: cannot exceed 32767")
        # A failure must never look like a successful parse to the staleness check.
        assert feed_info.last_successful_parse_at is None
        (status,) = await service.get_feed_statuses(db_session, ["SUBWAY"])
        assert status.is_stale is True

    async def test_unknown_source_is_a_failure_not_a_skip(
        self, db_session: AsyncSession
    ):
        """A typo'd source name must alarm rather than pass as rate limited."""
        outcome = await GTFSService().refresh_feed(db_session, "NOT_A_SOURCE")

        assert outcome is GTFSRefreshOutcome.FAILED_UNKNOWN_SOURCE
        assert outcome.is_failure is True

    async def test_rate_limited_skip_is_not_a_failure(self, db_session: AsyncSession):
        """The routine nightly skip must stay distinguishable from breakage.

        This is the exact pair that was indistinguishable before: this test and
        `test_download_and_process_failures_report_distinct_outcomes` both
        produced `False` on the old signature.
        """
        await _seed_feed(db_session, "NJT", parsed_hours_ago=1)

        outcome = await GTFSService().refresh_feed(db_session, "NJT")

        assert outcome is GTFSRefreshOutcome.SKIPPED_RATE_LIMITED
        assert outcome.is_failure is False
        assert outcome.refreshed is False

    async def test_daily_cadence_is_not_self_skipped(self, db_session: AsyncSession):
        """A source downloaded 23h ago must still refresh tonight.

        The refresh cron fires daily, so under the old 24h limit a source
        stamped at 03:00:0N measured 23.99h the next night and skipped itself —
        every source alternated refreshed/skipped in production, which is the
        noise the real SUBWAY/MNR failures hid inside. Reaching the download
        attempt (here: a failed download against an unroutable host) proves the
        rate limit let it through: the download is stubbed to fail, so reaching
        FAILED_DOWNLOAD proves the request was attempted rather than skipped.
        """
        await _seed_feed(db_session, "PATCO", parsed_hours_ago=23)
        feed_info = (
            await db_session.execute(
                select(GTFSFeedInfo).where(GTFSFeedInfo.data_source == "PATCO")
            )
        ).scalar_one()
        feed_info.last_downloaded_at = now_et() - timedelta(hours=23)
        await db_session.commit()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("stubbed: no network in tests")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            outcome = await GTFSService().refresh_feed(db_session, "PATCO")

        assert outcome is not GTFSRefreshOutcome.SKIPPED_RATE_LIMITED
        assert outcome is GTFSRefreshOutcome.FAILED_DOWNLOAD


@pytest.mark.asyncio
class TestNightlyRefreshJobSurfacesFailures:
    """The nightly job is the only thing that looks at every source. Before
    #1646 its summary said `{source}_refreshed: false` for a broken source and
    for a healthy rate-limited one alike, at INFO, and stopped there."""

    async def test_all_healthy_run_stays_at_info(
        self, db_engine, db_session: AsyncSession
    ):
        """A quiet night must stay quiet, or the ERROR means nothing.

        Both a real refresh and a rate-limited skip are healthy outcomes; only
        the combination of neither-failed and nothing-stale is silent.
        """
        await _seed_feed(db_session, "NJT", parsed_hours_ago=1)
        await _seed_feed(db_session, "SUBWAY", parsed_hours_ago=25)

        captured = await _run_refresh_job(
            db_engine,
            {
                "NJT": GTFSRefreshOutcome.REFRESHED,
                "SUBWAY": GTFSRefreshOutcome.SKIPPED_RATE_LIMITED,
            },
        )

        event = _completion_event(captured)
        assert event["log_level"] == "info"
        assert event["njt_refreshed"] is True
        assert event["subway_refreshed"] is False
        assert "failed_sources" not in event

    async def test_parse_failure_escalates_to_error_and_names_the_source(
        self, db_engine, db_session: AsyncSession
    ):
        """The exact #1646 scenario, at the moment it first happened.

        SUBWAY's parse crashes while every other source is fine. The old code
        logged this at INFO, identically to a healthy skip. It must now be an
        ERROR that names SUBWAY and says how it failed.
        """
        await _seed_feed(db_session, "NJT", parsed_hours_ago=1)
        await _seed_feed(db_session, "SUBWAY", parsed_hours_ago=1)

        captured = await _run_refresh_job(
            db_engine,
            {
                "NJT": GTFSRefreshOutcome.REFRESHED,
                "SUBWAY": GTFSRefreshOutcome.FAILED_PROCESS,
            },
        )

        event = _completion_event(captured)
        assert event["log_level"] == "error"
        assert event["failed_sources"] == {"SUBWAY": "failed_process"}
        # The healthy source is still reported, so the ERROR carries the
        # contrast that makes it actionable rather than just an alarm.
        assert event["njt_refreshed"] is True
        assert event["subway_refreshed"] is False

    async def test_rate_limited_skip_alone_never_escalates(
        self, db_engine, db_session: AsyncSession
    ):
        """The false-positive guard, and the reason the old signal was useless.

        Every healthy source reports a skip on a rate-limited night. If that
        escalated, the ERROR would fire nightly for everything and be ignored —
        which is functionally where #1646 started.
        """
        await _seed_feed(db_session, "NJT", parsed_hours_ago=20)
        await _seed_feed(db_session, "SUBWAY", parsed_hours_ago=20)

        captured = await _run_refresh_job(
            db_engine,
            {
                "NJT": GTFSRefreshOutcome.SKIPPED_RATE_LIMITED,
                "SUBWAY": GTFSRefreshOutcome.SKIPPED_RATE_LIMITED,
            },
        )

        assert _completion_event(captured)["log_level"] == "info"

    async def test_stale_feed_alarms_even_when_the_run_reports_no_failure(
        self, db_engine, db_session: AsyncSession
    ):
        """The check a well-behaved failure cannot satisfy.

        This is #1646 as it actually presented after day one: the nightly run
        looks unremarkable — SUBWAY reports the same skip as everyone else — yet
        its last successful parse is thirteen days old and the served schedule
        is frozen. Only the persisted parse age catches this, which is why the
        sweep reads the table rather than trusting the run's own outcomes.
        """
        await _seed_feed(db_session, "NJT", parsed_hours_ago=1)
        await _seed_feed(db_session, "SUBWAY", parsed_hours_ago=13 * 24)

        captured = await _run_refresh_job(
            db_engine,
            {
                "NJT": GTFSRefreshOutcome.REFRESHED,
                "SUBWAY": GTFSRefreshOutcome.SKIPPED_RATE_LIMITED,
            },
        )

        event = _completion_event(captured)
        assert event["log_level"] == "error"
        assert not event["failed_sources"]
        assert set(event["stale_sources"]) == {"SUBWAY"}
        assert event["stale_sources"]["SUBWAY"] == pytest.approx(312.0, abs=1.0)
        assert event["stale_after_hours"] == GTFS_STALE_FEED_HOURS

    async def test_never_parsed_source_alarms(
        self, db_engine, db_session: AsyncSession
    ):
        """A source with no successful parse at all must not read as healthy.

        MNR sat in exactly this state: refresh reported nothing alarming and
        there was no feed behind it, so every static backfill silently fell
        through to real-time-only stops.
        """
        await _seed_feed(db_session, "MNR", parsed_hours_ago=None)

        captured = await _run_refresh_job(
            db_engine, {"MNR": GTFSRefreshOutcome.SKIPPED_RATE_LIMITED}
        )

        event = _completion_event(captured)
        assert event["log_level"] == "error"
        assert event["stale_sources"] == {"MNR": None}

    async def test_disabled_sources_are_not_swept(
        self, db_engine, db_session: AsyncSession
    ):
        """A deliberately disabled system must not produce a nightly ERROR.

        BART/WMATA/MBTA/METRA/SEPTA are disabled in production and have no feed
        by design; alarming on them would bury the sources that matter.
        """
        await _seed_feed(db_session, "NJT", parsed_hours_ago=1)
        await _seed_feed(db_session, "BART", parsed_hours_ago=13 * 24)

        # `outcomes` doubles as the enabled set in the harness, so BART is
        # disabled here exactly as TRACKRAT_DISABLED_DATA_SOURCES disables it.
        captured = await _run_refresh_job(
            db_engine, {"NJT": GTFSRefreshOutcome.REFRESHED}
        )

        event = _completion_event(captured)
        assert event["log_level"] == "info"
        assert "bart_refreshed" not in event

    async def test_per_source_line_records_the_outcome_not_just_a_bool(
        self, db_engine, db_session: AsyncSession
    ):
        """Per-source lines must say *why*, so a log search can find failures.

        `gtfs_refresh_failed` is emitted deep inside the service and was the
        only place the reason existed; the job's own per-source line said
        `refreshed=false` and nothing more.
        """
        await _seed_feed(db_session, "SUBWAY", parsed_hours_ago=1)

        captured = await _run_refresh_job(
            db_engine, {"SUBWAY": GTFSRefreshOutcome.FAILED_PROCESS}
        )

        (line,) = [e for e in captured if e["event"] == "gtfs_subway_refresh_complete"]
        assert line["refreshed"] is False
        assert line["outcome"] == "failed_process"


@pytest.mark.asyncio
class TestHealthExposesFeedFreshness:
    """`/health` is where an operator looks first. Before this it reported
    scheduler, database, disk and discovery — and said nothing about whether
    the static schedules behind trip search and stop backfill were current."""

    @staticmethod
    async def _gtfs_check(db: AsyncSession, disabled: set[str] | None = None) -> dict:
        from trackrat.api.health import health_check

        settings = Mock()
        settings.environment = "testing"
        settings.data_disk_path = "/"
        settings.disabled_data_source_set = disabled or set()
        settings.is_data_source_disabled = lambda s: s in (disabled or set())

        with patch("trackrat.api.health.get_scheduler") as get_scheduler:
            scheduler = Mock()
            scheduler.get_status = Mock(
                return_value={"running": True, "jobs_count": 30, "active_tasks": []}
            )
            get_scheduler.return_value = scheduler
            result = await health_check(db=db, settings=settings)

        return result

    async def test_reports_every_feed_with_its_age(self, db_session: AsyncSession):
        await _seed_feed(db_session, "NJT", parsed_hours_ago=2, trip_count=1234)

        check = (await self._gtfs_check(db_session))["checks"]["gtfs_feeds"]

        assert check["feeds"]["NJT"]["age_hours"] == pytest.approx(2.0, abs=0.2)
        assert check["feeds"]["NJT"]["trip_count"] == 1234
        assert check["feeds"]["NJT"]["last_successful_parse_at"] is not None
        assert check["stale_after_hours"] == GTFS_STALE_FEED_HOURS

    async def test_stale_feed_degrades_health_and_surfaces_the_stored_error(
        self, db_session: AsyncSession
    ):
        """The diagnosis #1646 needed, made reachable over HTTP.

        `error_message` had been faithfully persisted through every failed night
        and was unreadable without direct database access, which is why the
        issue had to be argued from log *timing* instead.
        """
        for source in ("NJT", "PATH", "PATCO", "LIRR"):
            await _seed_feed(db_session, source, parsed_hours_ago=1)
        await _seed_feed(
            db_session,
            "SUBWAY",
            parsed_hours_ago=13 * 24,
            error_message="process: the number of query arguments cannot exceed 32767",
        )

        health = await self._gtfs_check(db_session)
        check = health["checks"]["gtfs_feeds"]

        assert check["status"] == "warning"
        assert "SUBWAY" in check["stale_sources"]
        assert "NJT" not in check["stale_sources"]
        assert "32767" in check["feeds"]["SUBWAY"]["error_message"]
        # A stale schedule degrades the deployment; it does not make it
        # unservable, and the container probes must not start failing over it.
        assert health["status"] == "degraded"

    async def test_disabled_sources_are_excluded(self, db_session: AsyncSession):
        """BART and friends are off by design and have no feed to be stale."""
        for source in (
            "NJT",
            "AMTRAK",
            "PATH",
            "PATCO",
            "LIRR",
            "MNR",
            "SUBWAY",
        ):
            await _seed_feed(db_session, source, parsed_hours_ago=1)

        disabled = {"BART", "WMATA", "MBTA", "METRA", "SEPTA_RR", "SEPTA_METRO"}
        check = (await self._gtfs_check(db_session, disabled))["checks"]["gtfs_feeds"]

        assert check["status"] == "healthy"
        assert check["stale_sources"] == []
        assert not disabled & set(check["feeds"])
