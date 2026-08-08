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
import io
import zipfile
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trackrat.models.database import GTFSFeedInfo, GTFSStopTime, GTFSTrip
from trackrat.services.gtfs import (
    GTFS_EXPIRY_EXEMPT_SOURCES,
    GTFS_FEED_URLS,
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
    feed_ends_in_days: int | None = None,
    feed_starts_in_days: int | None = None,
) -> None:
    """Insert a gtfs_feed_info row in a given freshness state.

    ``parsed_hours_ago=None`` models a source that has a row but has never
    completed a parse — the state SUBWAY was actually in.

    ``feed_ends_in_days`` sets ``feed_end_date`` relative to today; negative
    values model a bundle whose calendar has already expired. Left ``None``
    (the default) the column stays NULL, which is what a feed publishing only
    ``calendar_dates.txt`` produces.

    ``feed_starts_in_days`` does the same for ``feed_start_date``; *positive*
    values model the mirror-image failure — a bundle published early and
    adopted before it takes effect, so the source serves nothing at all
    (issue #1770).
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
            feed_end_date=(
                now_et().date() + timedelta(days=feed_ends_in_days)
                if feed_ends_in_days is not None
                else None
            ),
            feed_start_date=(
                now_et().date() + timedelta(days=feed_starts_in_days)
                if feed_starts_in_days is not None
                else None
            ),
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


def _gtfs_zip(*, trips: int = 2, service_id: str = "WKDY") -> bytes:
    """Build a small but genuinely valid GTFS static feed.

    Real enough that `_parse_and_store_gtfs` walks its whole pipeline —
    routes → calendar → stops → trips → stop_times — and reports non-zero
    counts, so a test can assert on what the parse actually persisted rather
    than on a stubbed stats dict.
    """
    trip_rows = "\n".join(
        f"T{n},{service_id},R1,Test Terminal,{n % 2}" for n in range(1, trips + 1)
    )
    stop_time_rows = "\n".join(
        f"T{n},{(5 + n) % 24:02d}:00:00,{(5 + n) % 24:02d}:00:00,S1,1\n"
        f"T{n},{(5 + n) % 24:02d}:30:00,{(5 + n) % 24:02d}:30:00,S2,2"
        for n in range(1, trips + 1)
    )
    files = {
        "routes.txt": (
            "route_id,route_short_name,route_long_name,route_type,route_color\n"
            "R1,TL,Test Line,2,ff0000\n"
        ),
        "calendar.txt": (
            "service_id,monday,tuesday,wednesday,thursday,friday,"
            "saturday,sunday,start_date,end_date\n"
            f"{service_id},1,1,1,1,1,0,0,20260101,20261231\n"
        ),
        "stops.txt": (
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "S1,Test Origin,40.7,-74.0\n"
            "S2,Test Terminal,40.8,-74.1\n"
        ),
        "trips.txt": (
            "trip_id,service_id,route_id,trip_headsign,direction_id\n"
            + trip_rows
            + "\n"
        ),
        "stop_times.txt": (
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            + stop_time_rows
            + "\n"
        ),
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, body in files.items():
            zf.writestr(name, body)
    return buffer.getvalue()


@contextlib.contextmanager
def _stub_download(bodies: bytes | dict[str, bytes]):
    """Serve `bodies` in place of the real GTFS download, per source.

    Only the HTTP transport is replaced: the rate-limit check, the parse, the
    feed_info writes and the exception handling that classifies the outcome all
    run for real. Tests must never reach a live transit feed, so this is the one
    boundary that has to be stubbed to exercise the rest.

    Passing a dict keys the response on the requested URL's data source, so a
    single run can give one source a good feed and another a corrupt one.
    """
    by_url = (
        {GTFS_FEED_URLS[source]: body for source, body in bodies.items()}
        if isinstance(bodies, dict)
        else None
    )

    async def fake_get(url, **kwargs):
        response = Mock()
        response.content = bodies if by_url is None else by_url[url]
        response.raise_for_status = Mock(return_value=None)
        return response

    client = AsyncMock()
    client.get = AsyncMock(side_effect=fake_get)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=client):
        yield


async def _run_refresh_job(
    db_engine,
    outcomes: dict[str, GTFSRefreshOutcome] | None = None,
    *,
    enabled: dict[str, bytes] | None = None,
):
    """Drive `refresh_gtfs_feeds` end to end, returning the captured log events.

    Two modes, because the job has two independent halves to pin:

    ``outcomes`` stubs `refresh_feed` per source, isolating the escalation
    logic so every combination of outcomes can be enumerated cheaply. The
    staleness sweep still runs against the real `gtfs_feed_info` rows, which is
    the point: the job's alarm must come from persisted state, not from the
    outcome the same run just reported.

    ``enabled`` instead maps each active source to the zip bytes its download
    should return, and the **real** `refresh_feed` runs — so the outcome the
    job branches on is one the service genuinely produced, and the rows the
    sweep reads are ones the service genuinely wrote. Only the network
    transport is stubbed; a test must never fetch a live transit feed.
    """
    if (outcomes is None) == (enabled is None):
        raise ValueError("pass exactly one of `outcomes` or `enabled`")

    active = outcomes if outcomes is not None else enabled
    assert active is not None
    sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)

    settings = Mock()
    settings.is_data_source_disabled = lambda source: source not in active
    service = SchedulerService.__new__(SchedulerService)
    service.settings = settings
    service._running_tasks = {}

    async def fake_refresh_feed(self, db, source, force=False):
        assert outcomes is not None
        return outcomes[source]

    with contextlib.ExitStack() as stack:
        stack.enter_context(
            patch(
                "trackrat.services.scheduler.get_session",
                _patched_get_session(sessionmaker),
            )
        )
        stack.enter_context(
            patch(
                "trackrat.services.scheduler.run_with_freshness_check",
                side_effect=_passthrough_freshness,
            )
        )
        if outcomes is not None:
            stack.enter_context(
                patch.object(GTFSService, "refresh_feed", fake_refresh_feed)
            )
        else:
            stack.enter_context(_stub_download(enabled or {}))
        captured = stack.enter_context(structlog.testing.capture_logs())
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

    async def test_a_nightly_refreshed_feed_with_an_expired_calendar_is_lapsed(
        self, db_session: AsyncSession
    ):
        """`feed_end_date` round-trips from Postgres into the lapse signal.

        The column has been written by every successful parse since the table
        was created and read by nothing, so this is the first test that proves
        the value survives the trip back out (issue #1634).

        SEPTA_METRO is the motivating source: served schedule-first, so an
        expired bundle is not a degraded fallback, it is the entire departure
        board being generated from a timetable that no longer applies.
        """
        await _seed_feed(
            db_session,
            "SEPTA_METRO",
            parsed_hours_ago=6,
            trip_count=14203,
            feed_ends_in_days=-7,
        )

        (status,) = await GTFSService().get_feed_statuses(db_session, ["SEPTA_METRO"])

        assert status.is_lapsed is True
        assert status.days_until_feed_end == -7
        assert status.feed_end_date == (now_et().date() - timedelta(days=7))
        # The point of the check: every pre-existing signal reads healthy.
        assert status.is_stale is False
        assert status.error_message is None
        assert status.trip_count == 14203

    async def test_a_current_bundle_reports_its_remaining_life(
        self, db_session: AsyncSession
    ):
        """Operators need the runway, not just a boolean — a bundle expiring in
        two days is actionable, one expiring in six months is not."""
        await _seed_feed(db_session, "PATCO", parsed_hours_ago=3, feed_ends_in_days=2)

        (status,) = await GTFSService().get_feed_statuses(db_session, ["PATCO"])

        assert status.is_lapsed is False
        assert status.days_until_feed_end == 2

    async def test_a_feed_with_no_calendar_end_date_reports_unknown(
        self, db_session: AsyncSession
    ):
        """calendar_dates-only feeds leave the column NULL. That must read as
        unknown, not expired, or the source carries a warning forever."""
        await _seed_feed(db_session, "NJT", parsed_hours_ago=3)

        (status,) = await GTFSService().get_feed_statuses(db_session, ["NJT"])

        assert status.feed_end_date is None
        assert status.days_until_feed_end is None
        assert status.is_lapsed is False

    async def test_a_freshly_parsed_bundle_starting_tomorrow_is_not_yet_active(
        self, db_session: AsyncSession
    ):
        """The production state of SEPTA_RR on 2026-08-08 (issue #1770).

        Reproduces the real bundle: `v202608090`, downloaded and parsed
        successfully, 1340 trips loaded, three weeks from expiry — and every
        `calendar.txt` row starting tomorrow, so there is no schedule for today
        and the source serves nothing.

        The assertions on the *other* signals are the substance of the test.
        Each one reads green, which is precisely why this went unnoticed for a
        day and a half behind a `healthy` status page.
        """
        await _seed_feed(
            db_session,
            "SEPTA_RR",
            parsed_hours_ago=1,
            trip_count=1340,
            feed_starts_in_days=1,
            feed_ends_in_days=21,
        )

        (status,) = await GTFSService().get_feed_statuses(db_session, ["SEPTA_RR"])

        assert status.is_not_yet_active is True
        assert status.days_until_feed_start == 1
        assert status.feed_start_date == (now_et().date() + timedelta(days=1))
        # Every pre-existing signal reads healthy — the whole point of #1770.
        assert status.is_stale is False
        assert status.is_lapsed is False
        assert status.error_message is None
        assert status.trip_count == 1340
        assert status.days_until_feed_end == 21

    async def test_a_bundle_starting_today_is_active(self, db_session: AsyncSession):
        """GTFS start dates are inclusive, so the first valid day must be
        active. Off-by-one here would fire on every bundle's opening day —
        including the morning SEPTA's feed finally takes effect."""
        await _seed_feed(
            db_session, "SEPTA_RR", parsed_hours_ago=1, feed_starts_in_days=0
        )

        (status,) = await GTFSService().get_feed_statuses(db_session, ["SEPTA_RR"])

        assert status.is_not_yet_active is False
        assert status.days_until_feed_start == 0

    async def test_a_bundle_that_started_in_the_past_is_active(
        self, db_session: AsyncSession
    ):
        """Ordinary operation: a bundle in force for a fortnight. Negative
        `days_until_feed_start` must not read as pending."""
        await _seed_feed(
            db_session, "PATCO", parsed_hours_ago=3, feed_starts_in_days=-14
        )

        (status,) = await GTFSService().get_feed_statuses(db_session, ["PATCO"])

        assert status.is_not_yet_active is False
        assert status.days_until_feed_start == -14

    async def test_a_feed_with_no_calendar_start_date_reports_unknown(
        self, db_session: AsyncSession
    ):
        """calendar_dates-only feeds leave the column NULL, exactly as they do
        for the end date. Unknown is not pending — treating it as pending would
        park a permanent warning on NJT, which publishes no calendar.txt."""
        await _seed_feed(db_session, "NJT", parsed_hours_ago=3)

        (status,) = await GTFSService().get_feed_statuses(db_session, ["NJT"])

        assert status.feed_start_date is None
        assert status.days_until_feed_start is None
        assert status.is_not_yet_active is False

    async def test_an_expiry_exempt_source_is_still_checked_for_a_future_start(
        self, db_session: AsyncSession
    ):
        """`GTFS_EXPIRY_EXEMPT_SOURCES` must not carry over to this check.

        PATH is exempt from the *lapse* verdict because its Trillium feed
        expired in 2026 and is knowingly still served (issue #1419). That
        carve-out says nothing about start dates, and extending it would mean a
        future-dated PATH bundle — a genuine regression — could never be seen.
        In practice PATH's start date is far in the past, so this asserts the
        exemption is scoped rather than describing a live state.
        """
        assert "PATH" in GTFS_EXPIRY_EXEMPT_SOURCES
        await _seed_feed(
            db_session,
            "PATH",
            parsed_hours_ago=1,
            feed_starts_in_days=3,
            feed_ends_in_days=-60,
        )

        (status,) = await GTFSService().get_feed_statuses(db_session, ["PATH"])

        # Exempt from the lapse verdict, as designed...
        assert status.is_lapsed is False
        # ...but a future start date is still reported.
        assert status.is_not_yet_active is True
        assert status.days_until_feed_start == 3


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
class TestRealRefreshPathWritesWhatTheSweepReads:
    """The outcome and the persisted row are two halves of one contract.

    Everywhere else in this file one half is supplied by the test: the sweep
    tests seed `gtfs_feed_info` by hand, and the nightly-job tests hand the job
    a chosen `GTFSRefreshOutcome`. Neither notices if the real `refresh_feed`
    stops writing `last_successful_parse_at` on success, or starts writing it on
    failure — and either would silently disarm the #1646 alarm while every other
    test stayed green. These drive the real service with a controlled feed so
    the outcome and the row are both produced by production code.
    """

    async def test_successful_refresh_stamps_the_parse_the_sweep_reads(
        self, db_session: AsyncSession
    ):
        """A real parse must leave the feed reporting healthy, with counts.

        `last_successful_parse_at` is the single field the staleness sweep and
        `/health` both read. If the success path stopped writing it, the sweep
        would alarm nightly on a perfectly healthy source.
        """
        service = GTFSService()

        with _stub_download(_gtfs_zip(trips=3)):
            outcome = await service.refresh_feed(db_session, "PATCO")

        assert outcome is GTFSRefreshOutcome.REFRESHED
        assert outcome.refreshed is True
        assert outcome.is_failure is False

        feed_info = (
            await db_session.execute(
                select(GTFSFeedInfo).where(GTFSFeedInfo.data_source == "PATCO")
            )
        ).scalar_one()
        assert feed_info.last_successful_parse_at is not None
        assert feed_info.error_message is None
        assert feed_info.trip_count == 3
        assert feed_info.route_count == 1
        assert feed_info.stop_time_count == 6

        # The rows really landed — the counts are not a stats dict talking to
        # itself. Six stop_times across three trips is the fixture's shape.
        stored_trips = await db_session.scalar(
            select(func.count())
            .select_from(GTFSTrip)
            .where(GTFSTrip.data_source == "PATCO")
        )
        stored_stop_times = await db_session.scalar(
            select(func.count())
            .select_from(GTFSStopTime)
            .join(GTFSTrip, GTFSStopTime.trip_id == GTFSTrip.id)
            .where(GTFSTrip.data_source == "PATCO")
        )
        assert stored_trips == 3
        assert stored_stop_times == 6

        (status,) = await service.get_feed_statuses(db_session, ["PATCO"])
        assert status.is_stale is False
        assert status.trip_count == 3
        assert status.error_message is None

    async def test_a_real_refresh_clears_the_1646_state(self, db_session: AsyncSession):
        """Recovery must be visible, not just failure.

        This is the state SUBWAY sat in for thirteen days — a stale row
        carrying the asyncpg bind-parameter error — followed by the fix landing.
        The alarm has to switch off by itself when a real parse succeeds, or
        operators learn to ignore it.
        """
        await _seed_feed(
            db_session,
            "SUBWAY",
            parsed_hours_ago=13 * 24,
            trip_count=83821,
            error_message="process: the number of query arguments cannot exceed 32767",
        )
        service = GTFSService()
        (before,) = await service.get_feed_statuses(db_session, ["SUBWAY"])
        assert before.is_stale is True

        with _stub_download(_gtfs_zip(trips=2)):
            outcome = await service.refresh_feed(db_session, "SUBWAY", force=True)

        assert outcome is GTFSRefreshOutcome.REFRESHED
        (after,) = await service.get_feed_statuses(db_session, ["SUBWAY"])
        assert after.is_stale is False
        assert after.age_hours == pytest.approx(0.0, abs=0.2)
        # The stale error text must not outlive the failure it described.
        assert after.error_message is None
        assert after.trip_count == 2

    async def test_a_real_parse_failure_leaves_the_feed_stale(
        self, db_session: AsyncSession
    ):
        """A corrupt feed must fail *through the real handler* and stay stale.

        `test_failure_outcome_and_persisted_error_agree` calls
        `_record_refresh_failure` directly, so it cannot see whether
        `refresh_feed` actually routes a parse crash there — nor whether the
        parse's own partial writes get rolled back rather than stamping a
        success. Here the exception comes from the real parse.
        """
        await _seed_feed(db_session, "MNR", parsed_hours_ago=None)
        service = GTFSService()

        with _stub_download(b"this is not a zip file"):
            outcome = await service.refresh_feed(db_session, "MNR", force=True)

        assert outcome is GTFSRefreshOutcome.FAILED_PROCESS
        assert outcome.is_failure is True
        assert outcome.refreshed is False

        feed_info = (
            await db_session.execute(
                select(GTFSFeedInfo).where(GTFSFeedInfo.data_source == "MNR")
            )
        ).scalar_one()
        # The failure must not be able to satisfy the staleness check.
        assert feed_info.last_successful_parse_at is None
        assert feed_info.error_message.startswith("process: ")

        (status,) = await service.get_feed_statuses(db_session, ["MNR"])
        assert status.is_stale is True

    async def test_a_real_refresh_after_failure_does_not_inherit_stale_trips(
        self, db_session: AsyncSession
    ):
        """The parse replaces the served schedule; it must not append to it.

        #1646's damage was a *frozen* schedule still being served. A refresh
        that left the previous feed's trips in place alongside the new ones
        would report a healthy parse age while still serving stale trips.
        """
        service = GTFSService()

        with _stub_download(_gtfs_zip(trips=4, service_id="OLD")):
            assert await service.refresh_feed(db_session, "PATH", force=True) is (
                GTFSRefreshOutcome.REFRESHED
            )
        with _stub_download(_gtfs_zip(trips=2, service_id="NEW")):
            assert await service.refresh_feed(db_session, "PATH", force=True) is (
                GTFSRefreshOutcome.REFRESHED
            )

        stored = (
            (
                await db_session.execute(
                    select(GTFSTrip.service_id).where(GTFSTrip.data_source == "PATH")
                )
            )
            .scalars()
            .all()
        )
        assert sorted(stored) == ["NEW", "NEW"]

        (status,) = await service.get_feed_statuses(db_session, ["PATH"])
        assert status.trip_count == 2


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

    async def test_real_service_drives_the_escalation_end_to_end(
        self, db_engine, db_session: AsyncSession
    ):
        """The whole chain, with nothing between the feed and the alarm.

        Every other case in this class hands the job a chosen outcome, so all of
        them would stay green if `refresh_feed` classified a parse crash as a
        success. Here SUBWAY is served a corrupt feed and PATCO a good one, and
        the ERROR has to be produced by what the real service returned and
        wrote. Only the HTTP download is stubbed.
        """
        captured = await _run_refresh_job(
            db_engine,
            enabled={
                "PATCO": _gtfs_zip(trips=2),
                "SUBWAY": b"not a zip",
            },
        )

        event = _completion_event(captured)
        assert event["log_level"] == "error"
        assert event["failed_sources"] == {"SUBWAY": "failed_process"}
        assert event["patco_refreshed"] is True
        assert event["subway_refreshed"] is False

        # The healthy source parsed for real, so it is not swept up as stale;
        # the failed one has no successful parse and is.
        assert set(event["stale_sources"]) == {"SUBWAY"}
        assert event["stale_sources"]["SUBWAY"] is None

        feeds = {
            f.data_source: f
            for f in (await db_session.execute(select(GTFSFeedInfo))).scalars().all()
        }
        assert feeds["PATCO"].last_successful_parse_at is not None
        assert feeds["PATCO"].trip_count == 2
        assert feeds["SUBWAY"].last_successful_parse_at is None
        assert feeds["SUBWAY"].error_message.startswith("process: ")


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

    async def test_lapsed_feed_degrades_health_even_though_it_is_not_stale(
        self, db_session: AsyncSession
    ):
        """An expired timetable has to reach `/health` on its own merits.

        Every other signal on this source is green — parsed three hours ago, no
        error, trips loaded — so if the lapse did not degrade health nothing
        would, and SEPTA Metro would keep serving a dead schedule indefinitely
        with a healthy status page above it (issue #1634).
        """
        # Every source seeded current, so the deployment is unambiguously
        # healthy apart from the one lapsed bundle. Without this the check
        # would already be warning over unseeded sources and the test would
        # prove nothing about the lapse.
        for source in GTFS_FEED_URLS:
            await _seed_feed(
                db_session,
                source,
                parsed_hours_ago=3 if source == "SEPTA_METRO" else 1,
                trip_count=14203 if source == "SEPTA_METRO" else None,
                feed_ends_in_days=-5 if source == "SEPTA_METRO" else 45,
            )

        health = await self._gtfs_check(db_session)
        check = health["checks"]["gtfs_feeds"]

        # Nothing is stale, so the lapse is the sole cause of the degrade.
        assert check["stale_sources"] == []
        assert check["status"] == "warning"
        assert check["lapsed_sources"] == ["SEPTA_METRO"]
        assert check["feeds"]["SEPTA_METRO"]["days_until_feed_end"] == -5
        assert (
            check["feeds"]["SEPTA_METRO"]["feed_end_date"]
            == (now_et().date() - timedelta(days=5)).isoformat()
        )
        assert health["status"] == "degraded"

    async def test_current_feeds_report_their_end_date_without_alarming(
        self, db_session: AsyncSession
    ):
        """The companion baseline: identical setup, valid end dates, healthy.

        Pins that the lapse check does not alarm on ordinary operation — the
        way a check earns being trusted when it does fire.
        """
        for source in GTFS_FEED_URLS:
            await _seed_feed(
                db_session, source, parsed_hours_ago=1, feed_ends_in_days=45
            )

        check = (await self._gtfs_check(db_session))["checks"]["gtfs_feeds"]

        # Scoped to the gtfs_feeds check, not overall health: this fixture has
        # no discovery runs, so the deployment reports degraded for reasons
        # that have nothing to do with feeds.
        assert check["status"] == "healthy"
        assert check["lapsed_sources"] == []
        assert check["stale_sources"] == []
        assert check["feeds"]["PATCO"]["days_until_feed_end"] == 45

    async def test_not_yet_active_feed_degrades_health_though_nothing_else_is_wrong(
        self, db_session: AsyncSession
    ):
        """The #1770 regression test, end to end through `/health`.

        Models production on 2026-08-08: SEPTA_RR freshly parsed, trips loaded,
        three weeks of runway, and a calendar that starts tomorrow. Before this
        check the endpoint returned `healthy` with empty `stale_sources` and
        `lapsed_sources` while the source served zero departures at every
        station — the reading that was quoted as evidence SEPTA was fine.
        """
        for source in GTFS_FEED_URLS:
            await _seed_feed(
                db_session,
                source,
                parsed_hours_ago=1,
                trip_count=1340 if source == "SEPTA_RR" else None,
                feed_starts_in_days=1 if source == "SEPTA_RR" else -14,
                feed_ends_in_days=21 if source == "SEPTA_RR" else 45,
            )

        health = await self._gtfs_check(db_session)
        check = health["checks"]["gtfs_feeds"]

        # Neither pre-existing signal fires, so the future start date is the
        # sole cause of the degrade — that is the regression being pinned.
        assert check["stale_sources"] == []
        assert check["lapsed_sources"] == []
        assert check["not_yet_active_sources"] == ["SEPTA_RR"]
        assert check["status"] == "warning"
        assert check["feeds"]["SEPTA_RR"]["days_until_feed_start"] == 1
        assert (
            check["feeds"]["SEPTA_RR"]["feed_start_date"]
            == (now_et().date() + timedelta(days=1)).isoformat()
        )
        assert health["status"] == "degraded"

    async def test_in_force_feeds_report_their_start_date_without_alarming(
        self, db_session: AsyncSession
    ):
        """The companion baseline: identical setup, bundles already in force,
        healthy. Pins that the new check does not alarm on ordinary
        operation — the way a check earns being trusted when it does fire."""
        for source in GTFS_FEED_URLS:
            await _seed_feed(
                db_session,
                source,
                parsed_hours_ago=1,
                feed_starts_in_days=-14,
                feed_ends_in_days=45,
            )

        check = (await self._gtfs_check(db_session))["checks"]["gtfs_feeds"]

        assert check["status"] == "healthy"
        assert check["not_yet_active_sources"] == []
        assert check["feeds"]["PATCO"]["days_until_feed_start"] == -14

    async def test_a_bundle_starting_today_does_not_alarm_through_health(
        self, db_session: AsyncSession
    ):
        """GTFS start dates are inclusive. The morning a correctly-timed bundle
        takes effect must be healthy, or every agency's changeover day fires."""
        for source in GTFS_FEED_URLS:
            await _seed_feed(
                db_session,
                source,
                parsed_hours_ago=1,
                feed_starts_in_days=0 if source == "SEPTA_RR" else -14,
                feed_ends_in_days=45,
            )

        check = (await self._gtfs_check(db_session))["checks"]["gtfs_feeds"]

        assert check["not_yet_active_sources"] == []
        assert check["status"] == "healthy"
        assert check["feeds"]["SEPTA_RR"]["days_until_feed_start"] == 0

    async def test_a_bundle_expiring_today_does_not_alarm(
        self, db_session: AsyncSession
    ):
        """GTFS end dates are inclusive, so the last valid day must stay
        healthy. Off-by-one here would fire on every bundle's final day."""
        for source in GTFS_FEED_URLS:
            await _seed_feed(
                db_session,
                source,
                parsed_hours_ago=1,
                feed_ends_in_days=0 if source == "PATCO" else 45,
            )

        check = (await self._gtfs_check(db_session))["checks"]["gtfs_feeds"]

        assert check["lapsed_sources"] == []
        assert check["status"] == "healthy"
        assert check["feeds"]["PATCO"]["days_until_feed_end"] == 0

    async def test_paths_deliberately_expired_bundle_does_not_degrade_health(
        self, db_session: AsyncSession
    ):
        """The production state this check must not alarm on.

        PATH's upstream Trillium feed expired 2026-06-01 and is knowingly still
        served — `GTFS_EXPIRY_EXEMPT_SOURCES` drops the `end_date` bound for it
        so the frozen weekly pattern keeps producing departures (issue #1419).
        Without the exemption every deployment reports `degraded` forever and
        `verify-deployment.sh` exits non-zero on every staging and production
        deploy, which would retire the check before it ever caught a real
        SEPTA/PATCO lapse (issue #1634).

        The expiry is still *reported* — withholding the verdict is not the
        same as hiding the date.
        """
        for source in GTFS_FEED_URLS:
            await _seed_feed(
                db_session,
                source,
                parsed_hours_ago=1,
                feed_ends_in_days=-62 if source == "PATH" else 45,
            )

        check = (await self._gtfs_check(db_session))["checks"]["gtfs_feeds"]

        assert "PATH" in GTFS_EXPIRY_EXEMPT_SOURCES, "precondition"
        assert check["lapsed_sources"] == []
        assert check["status"] == "healthy"
        assert check["feeds"]["PATH"]["days_until_feed_end"] == -62

    async def test_a_non_exempt_source_expiring_alongside_path_still_alarms(
        self, db_session: AsyncSession
    ):
        """The exemption must not swallow the case the check exists for.

        PATH sits two months past its calendar and stays quiet; SEPTA Metro
        with the identical offset is reported, so a real lapse is still caught
        on a deployment that permanently carries PATH's expired bundle.
        """
        for source in GTFS_FEED_URLS:
            await _seed_feed(
                db_session,
                source,
                parsed_hours_ago=1,
                feed_ends_in_days=-62 if source in ("PATH", "SEPTA_METRO") else 45,
            )

        health = await self._gtfs_check(db_session)
        check = health["checks"]["gtfs_feeds"]

        assert check["lapsed_sources"] == ["SEPTA_METRO"]
        assert check["status"] == "warning"
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
        assert check["lapsed_sources"] == []
        assert not disabled & set(check["feeds"])
