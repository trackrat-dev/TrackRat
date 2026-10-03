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
from datetime import date, timedelta
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.fixtures.gtfs_bundles import build_gtfs_zip
from trackrat.models.database import GTFSFeedInfo, GTFSStopTime, GTFSTrip
from trackrat.services.gtfs import (
    GTFS_EXPIRY_EXEMPT_SOURCES,
    GTFS_FEED_URLS,
    GTFS_ROUTE_TYPE_FILTER,
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
    (the default) the column stays NULL — what a row written before the
    bounds derivation existed carries, or a bundle with no calendar data for
    its retained trips.

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


def _split_route_type_zip(
    *,
    rail_start: str,
    rail_end: str,
    bus_start: str,
    bus_end: str,
) -> bytes:
    """A SEPTA-shaped bundle carrying both rail and bus, on separate calendars.

    SEPTA publishes Metro inside `google_bus.zip`, so the real bundle mixes
    route types and `GTFS_ROUTE_TYPE_FILTER` keeps only 0/1. This models the
    case that matters: the two modes run on *different* service ids with
    different windows, so whichever rows are used to date the bundle changes
    the answer. Dates are in GTFS's own `YYYYMMDD` form.
    """
    return build_gtfs_zip(
        trips=1,
        service_id="RAIL",
        route_type="1",
        start_date=rail_start,
        end_date=rail_end,
        extra_route_rows=["R_BUS,17,Bus Route 17,3,336699"],
        extra_calendar_rows=[f"BUS,1,1,1,1,1,1,1,{bus_start},{bus_end}"],
        extra_trip_rows=["T_BUS,BUS,R_BUS,Test Terminal,0"],
        extra_stop_time_rows=[
            "T_BUS,09:00:00,09:00:00,S1,1",
            "T_BUS,09:30:00,09:30:00,S2,2",
        ],
    )


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
        """A NULL end date — a row written before the bounds derivation
        existed, or a bundle with no calendar data for its retained trips —
        must read as unknown, not expired, or the source carries a warning
        forever."""
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
        """A NULL start date must read as unknown, exactly as a NULL end date
        does. Unknown is not pending — treating it as pending would park a
        permanent warning on any row written before the bounds derivation
        existed."""
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


def _gtfs_date(days_from_today: int) -> str:
    """A GTFS `YYYYMMDD` date relative to today."""
    return (now_et().date() + timedelta(days=days_from_today)).strftime("%Y%m%d")


async def _stored_trip_ids(db: AsyncSession, data_source: str) -> set[str]:
    """The trip ids currently persisted for a source.

    The load-bearing assertion for issue #1769: `_parse_and_store_gtfs` clears
    a source's rows before writing, so "did we adopt this bundle" is really
    "did the previously stored timetable survive". A test that only checked the
    returned outcome would pass against an implementation that declined the
    bundle *after* deleting the old one — the exact outage being prevented.
    """
    rows = await db.execute(
        select(GTFSTrip.trip_id).where(GTFSTrip.data_source == data_source)
    )
    return set(rows.scalars().all())


@pytest.mark.asyncio
class TestFutureDatedBundlesAreDeclined:
    """Issue #1769: adopting a bundle that has not taken effect takes the
    source dark, because storing one destroys the bundle still in force."""

    async def test_a_bundle_starting_tomorrow_is_declined_and_the_stored_one_survives(
        self, db_session: AsyncSession
    ):
        """The core guard, reproducing SEPTA's 2026-08-08 publication.

        A bundle in force is stored, then the agency publishes next week's
        early. Adopting it would delete today's timetable and replace it with
        one describing no service until tomorrow.
        """
        service = GTFSService()

        with _stub_download(
            build_gtfs_zip(trips=3, start_date=_gtfs_date(-7), end_date=_gtfs_date(7))
        ):
            first = await service.refresh_feed(db_session, "SEPTA_RR", force=True)
        assert first is GTFSRefreshOutcome.REFRESHED
        in_force = await _stored_trip_ids(db_session, "SEPTA_RR")
        assert in_force == {"T1", "T2", "T3"}

        feed_info = await service._get_or_create_feed_info(db_session, "SEPTA_RR")
        parsed_at_before = feed_info.last_successful_parse_at
        downloaded_at_before = feed_info.last_downloaded_at

        with _stub_download(
            build_gtfs_zip(
                trips=5,
                service_id="NEXTWK",
                start_date=_gtfs_date(1),
                end_date=_gtfs_date(21),
            )
        ):
            second = await service.refresh_feed(db_session, "SEPTA_RR", force=True)

        assert second is GTFSRefreshOutcome.SKIPPED_NOT_YET_ACTIVE
        # The whole point: the timetable serving today is still there.
        assert await _stored_trip_ids(db_session, "SEPTA_RR") == in_force

        await db_session.refresh(feed_info)
        # Not a parse, so the parse timestamp must not move — `age_hours` has to
        # keep climbing, because the deployment really is on an older bundle.
        assert feed_info.last_successful_parse_at == parsed_at_before
        # The download did happen and must be stamped as one, so the rate limit
        # holds and this does not re-download in a tight loop.
        assert feed_info.last_downloaded_at > downloaded_at_before

    async def test_declining_is_a_skip_not_a_failure(self, db_session: AsyncSession):
        """An agency publishing early is expected operation, not a fault.

        Classifying it as a failure would page on a normal weekly changeover
        and, worse, teach readers to ignore `failed_sources`.
        """
        outcome = GTFSRefreshOutcome.SKIPPED_NOT_YET_ACTIVE

        assert outcome.is_failure is False
        assert outcome.refreshed is False

    async def test_a_future_bundle_is_adopted_when_nothing_is_stored(
        self, db_session: AsyncSession
    ):
        """Production's actual situation on 2026-08-08: SEPTA's first-ever
        download. There is no bundle to protect, and refusing would leave the
        source with nothing at all — including after the start date arrives."""
        service = GTFSService()

        with _stub_download(
            build_gtfs_zip(trips=4, start_date=_gtfs_date(1), end_date=_gtfs_date(21))
        ):
            outcome = await service.refresh_feed(db_session, "SEPTA_RR", force=True)

        assert outcome is GTFSRefreshOutcome.REFRESHED
        assert await _stored_trip_ids(db_session, "SEPTA_RR") == {
            "T1",
            "T2",
            "T3",
            "T4",
        }

    async def test_a_bundle_starting_today_is_adopted(self, db_session: AsyncSession):
        """GTFS start dates are inclusive. Declining on the changeover morning
        would freeze every source on the previous week's timetable for a day."""
        service = GTFSService()

        with _stub_download(build_gtfs_zip(trips=2, start_date=_gtfs_date(-7))):
            await service.refresh_feed(db_session, "SEPTA_RR", force=True)

        with _stub_download(
            build_gtfs_zip(
                trips=6,
                service_id="TODAY",
                start_date=_gtfs_date(0),
                end_date=_gtfs_date(14),
            )
        ):
            outcome = await service.refresh_feed(db_session, "SEPTA_RR", force=True)

        assert outcome is GTFSRefreshOutcome.REFRESHED
        assert len(await _stored_trip_ids(db_session, "SEPTA_RR")) == 6

    async def test_an_ordinary_in_force_bundle_is_adopted(
        self, db_session: AsyncSession
    ):
        """The baseline that keeps the guard honest: normal weekly refreshes
        must still replace the stored bundle, or the feed never updates."""
        service = GTFSService()

        with _stub_download(build_gtfs_zip(trips=2, start_date=_gtfs_date(-14))):
            await service.refresh_feed(db_session, "SEPTA_RR", force=True)

        with _stub_download(
            build_gtfs_zip(trips=7, service_id="CURRENT", start_date=_gtfs_date(-1))
        ):
            outcome = await service.refresh_feed(db_session, "SEPTA_RR", force=True)

        assert outcome is GTFSRefreshOutcome.REFRESHED
        assert len(await _stored_trip_ids(db_session, "SEPTA_RR")) == 7

    async def test_a_bundle_without_calendar_txt_is_adopted(
        self, db_session: AsyncSession
    ):
        """NJT publishes no calendar.txt, so its start date is unknowable.

        Unknown must fail *open*. The guard can only decline, so treating an
        unreadable window as future-dated would pin such a source to its first
        bundle permanently — a worse outage than the one being prevented.
        """
        service = GTFSService()

        with _stub_download(build_gtfs_zip(trips=2, start_date=_gtfs_date(-14))):
            await service.refresh_feed(db_session, "NJT", force=True)

        with _stub_download(
            build_gtfs_zip(trips=9, service_id="NOCAL", include_calendar=False)
        ):
            outcome = await service.refresh_feed(db_session, "NJT", force=True)

        assert outcome is GTFSRefreshOutcome.REFRESHED
        assert len(await _stored_trip_ids(db_session, "NJT")) == 9

    async def test_the_service_window_is_read_without_touching_stored_data(
        self, db_session: AsyncSession
    ):
        """The helper must be genuinely read-only.

        It runs before `_parse_and_store_gtfs`, whose first act is deleting the
        source's rows — so if reading the start date had any storage side
        effect, the guard would destroy the bundle it exists to protect.
        """
        service = GTFSService()

        with _stub_download(build_gtfs_zip(trips=3, start_date=_gtfs_date(-7))):
            await service.refresh_feed(db_session, "SEPTA_RR", force=True)
        before = await _stored_trip_ids(db_session, "SEPTA_RR")

        status = service._bundle_service_status(
            build_gtfs_zip(trips=5, service_id="OTHER", start_date=_gtfs_date(3)),
            "SEPTA_RR",
            now_et().date(),
        )

        assert status.in_force is False
        assert status.service_begins_on == now_et().date() + timedelta(days=3)
        assert await _stored_trip_ids(db_session, "SEPTA_RR") == before

    async def test_an_unreadable_archive_reports_an_unknown_window(self):
        """A corrupt download must not be surfaced *by the guard*.

        It still fails in `_parse_and_store_gtfs` and reports FAILED_PROCESS,
        which is the outcome that carries the stage and the error text. Raising
        here would relabel a download problem as a calendar problem.
        """
        status = GTFSService()._bundle_service_status(
            b"not a zip file", "SEPTA_RR", now_et().date()
        )
        assert status.in_force is None
        assert status.service_begins_on is None

    async def test_a_calendar_with_no_usable_start_dates_is_adopted(
        self, db_session: AsyncSession
    ):
        """`calendar.txt` present but yielding nothing is still unknown.

        Distinct from the missing-file case above: the file exists and parses,
        it just carries no start date (header only, or every row blank). Both
        have to fail open for the same reason — the guard can only decline, so
        an unknown read as future-dated would pin the source permanently.
        """
        service = GTFSService()

        header_only = build_gtfs_zip(trips=2, start_date=_gtfs_date(-14))
        rebuilt = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(header_only)) as src:
            with zipfile.ZipFile(rebuilt, "w", zipfile.ZIP_DEFLATED) as dst:
                for name in src.namelist():
                    body = src.read(name)
                    if name == "calendar.txt":
                        body = (
                            b"service_id,monday,tuesday,wednesday,thursday,"
                            b"friday,saturday,sunday,start_date,end_date\n"
                        )
                    dst.writestr(name, body)
        no_dates = rebuilt.getvalue()

        assert (
            service._bundle_service_status(
                no_dates, "SEPTA_RR", now_et().date()
            ).in_force
            is None
        )

        with _stub_download(build_gtfs_zip(trips=2, start_date=_gtfs_date(-14))):
            await service.refresh_feed(db_session, "SEPTA_RR", force=True)
        with _stub_download(no_dates):
            outcome = await service.refresh_feed(db_session, "SEPTA_RR", force=True)

        assert outcome is GTFSRefreshOutcome.REFRESHED

    async def test_a_retired_calendar_row_cannot_smuggle_in_a_future_bundle(
        self, db_session: AsyncSession
    ):
        """An expired row must not vouch for a bundle that has not started.

        Agencies commonly ship the outgoing rating's calendar alongside the
        incoming one. Judging the bundle by the earliest start date across
        every row lets that closed window answer "this has already started"
        while the only service the bundle actually describes begins next week.
        Adopting on that basis deletes the in-force timetable, and
        `get_active_service_ids` then drops the retired row on its `end_date`
        and the replacement on its `start_date` — the source serves nothing,
        which is the outage the guard exists to prevent.
        """
        service = GTFSService()

        with _stub_download(
            build_gtfs_zip(trips=3, start_date=_gtfs_date(-7), end_date=_gtfs_date(7))
        ):
            first = await service.refresh_feed(db_session, "SEPTA_RR", force=True)
        assert first is GTFSRefreshOutcome.REFRESHED
        in_force = await _stored_trip_ids(db_session, "SEPTA_RR")
        assert in_force == {"T1", "T2", "T3"}

        with _stub_download(
            build_gtfs_zip(
                trips=5,
                service_id="NEXTWK",
                start_date=_gtfs_date(1),
                end_date=_gtfs_date(21),
                extra_calendar_rows=[
                    f"RETIRED,1,1,1,1,1,0,0,{_gtfs_date(-60)},{_gtfs_date(-1)}"
                ],
            )
        ):
            second = await service.refresh_feed(db_session, "SEPTA_RR", force=True)

        assert second is GTFSRefreshOutcome.SKIPPED_NOT_YET_ACTIVE, (
            "A bundle whose only live service starts tomorrow was adopted "
            "because a retired calendar row reported a start date in the past "
            f"(outcome={second})"
        )
        assert await _stored_trip_ids(db_session, "SEPTA_RR") == in_force, (
            "The in-force timetable was cleared for a bundle that describes no "
            "service today"
        )

    async def test_a_bundle_whose_every_row_has_expired_is_still_adopted(
        self, db_session: AsyncSession
    ):
        """Ignoring closed windows must not turn into declining a lapsed feed.

        A bundle that names no future service at all is a lapse problem — the
        lapse detection's to report — not an early publication. Declining it
        would loop forever: PATH's permanently-expired exempt feed would be
        pinned to its first stored copy, unable to pick up corrections.
        """
        service = GTFSService()

        with _stub_download(
            build_gtfs_zip(trips=3, start_date=_gtfs_date(-30), end_date=_gtfs_date(7))
        ):
            await service.refresh_feed(db_session, "SEPTA_RR", force=True)

        with _stub_download(
            build_gtfs_zip(
                trips=4,
                service_id="LAPSED",
                start_date=_gtfs_date(-60),
                end_date=_gtfs_date(-1),
            )
        ):
            outcome = await service.refresh_feed(db_session, "SEPTA_RR", force=True)

        assert outcome is GTFSRefreshOutcome.REFRESHED
        assert await _stored_trip_ids(db_session, "SEPTA_RR") == {
            "T1",
            "T2",
            "T3",
            "T4",
        }

    async def test_a_calendar_dates_bridged_bundle_is_adopted(
        self, db_session: AsyncSession
    ):
        """A future calendar window bridged by date additions serves today.

        Agencies bridge a rating changeover with explicit calendar_dates
        additions before the new calendar.txt window opens, and the serving
        path (`get_active_service_ids`) honors those additions with no
        start-date constraint. Declining such a bundle would wrongly pin the
        source to the outgoing timetable — the wrongful-decline mirror of the
        min(start_date) bypass.
        """
        service = GTFSService()

        with _stub_download(
            build_gtfs_zip(trips=3, start_date=_gtfs_date(-7), end_date=_gtfs_date(7))
        ):
            await service.refresh_feed(db_session, "SEPTA_RR", force=True)

        with _stub_download(
            build_gtfs_zip(
                trips=4,
                service_id="NEXTWK",
                start_date=_gtfs_date(3),
                end_date=_gtfs_date(30),
                calendar_dates_rows=[f"NEXTWK,{_gtfs_date(0)},1"],
            )
        ):
            outcome = await service.refresh_feed(db_session, "SEPTA_RR", force=True)

        assert outcome is GTFSRefreshOutcome.REFRESHED
        assert await _stored_trip_ids(db_session, "SEPTA_RR") == {
            "T1",
            "T2",
            "T3",
            "T4",
        }

    async def test_a_future_bundle_replaces_a_lapsed_stored_bundle(
        self, db_session: AsyncSession
    ):
        """Declining requires the stored bundle to be worth keeping.

        "A parse once succeeded" is not that: a lapsed stored bundle serves
        nothing, so declining its replacement keeps the source dark AND makes
        recovery depend on the start-date morning's download succeeding. Both
        bundles serve nothing today; the future one at least starts serving by
        itself the day its window opens, so it is adopted.
        """
        service = GTFSService()

        # First-ever download: an already-expired bundle. Nothing is stored,
        # so the first-bundle path adopts it; the source now holds a lapsed
        # timetable (feed_end_date in the past).
        with _stub_download(
            build_gtfs_zip(trips=2, start_date=_gtfs_date(-30), end_date=_gtfs_date(-1))
        ):
            first = await service.refresh_feed(db_session, "SEPTA_RR", force=True)
        assert first is GTFSRefreshOutcome.REFRESHED

        feed_info = await service._get_or_create_feed_info(db_session, "SEPTA_RR")
        assert feed_info.feed_end_date is not None
        assert feed_info.feed_end_date < now_et().date()

        with _stub_download(
            build_gtfs_zip(
                trips=6,
                service_id="NEXTWK",
                start_date=_gtfs_date(2),
                end_date=_gtfs_date(40),
            )
        ):
            outcome = await service.refresh_feed(db_session, "SEPTA_RR", force=True)

        assert outcome is GTFSRefreshOutcome.REFRESHED
        assert len(await _stored_trip_ids(db_session, "SEPTA_RR")) == 6

    async def test_septa_metros_bus_calendar_cannot_vouch_for_its_rail_services(
        self, db_session: AsyncSession
    ):
        """The verdict honors GTFS_ROUTE_TYPE_FILTER (review on #1775).

        SEPTA_METRO ingests route types 0/1 out of a shared bundle whose bus
        network dwarfs the rail lines. A bus service running today proves
        nothing about the Metro timetable that would actually be served — if
        it counted, a bundle whose every retained rail service is future would
        be adopted and Metro would go dark while the buses vouched for it.
        """
        service = GTFSService()

        with _stub_download(
            build_gtfs_zip(
                trips=3,
                route_type="1",
                start_date=_gtfs_date(-7),
                end_date=_gtfs_date(7),
            )
        ):
            first = await service.refresh_feed(db_session, "SEPTA_METRO", force=True)
        assert first is GTFSRefreshOutcome.REFRESHED
        in_force = await _stored_trip_ids(db_session, "SEPTA_METRO")
        assert in_force == {"T1", "T2", "T3"}

        with _stub_download(
            build_gtfs_zip(
                trips=4,
                route_type="1",
                service_id="RAILNEXT",
                start_date=_gtfs_date(2),
                end_date=_gtfs_date(30),
                extra_route_rows=["RBUS,44,A Bus Route,3,00ff00"],
                extra_calendar_rows=[
                    f"BUSNOW,1,1,1,1,1,1,1,{_gtfs_date(-30)},{_gtfs_date(30)}"
                ],
                extra_trip_rows=["TB1,BUSNOW,RBUS,Bus Terminal,0"],
            )
        ):
            outcome = await service.refresh_feed(db_session, "SEPTA_METRO", force=True)

        assert outcome is GTFSRefreshOutcome.SKIPPED_NOT_YET_ACTIVE
        assert await _stored_trip_ids(db_session, "SEPTA_METRO") == in_force


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

    async def test_parse_dates_the_bundle_only_by_service_it_actually_ingests(
        self, db_session: AsyncSession
    ):
        """SEPTA_METRO's bundle is the shared bus feed; bus rows must not date it.

        `GTFS_ROUTE_TYPE_FILTER` keeps only route types 0/1 for SEPTA_METRO, so
        the ~131 bus routes' trips are dropped — but `_parse_calendar` stores
        every `calendar.txt` row regardless. Taking `min(start_date)` across all
        of them lets a bus calendar that has already started vouch for a Metro
        calendar that has not, and `is_not_yet_active` (which reads exactly this
        column) then reports the source healthy while Metro serves nothing:
        #1770's detection gap reopened one level down.
        """
        service = GTFSService()
        today = now_et().date()
        metro_start = today + timedelta(days=3)

        with _stub_download(
            _split_route_type_zip(
                rail_start=metro_start.strftime("%Y%m%d"),
                rail_end=(today + timedelta(days=60)).strftime("%Y%m%d"),
                bus_start=(today - timedelta(days=14)).strftime("%Y%m%d"),
                bus_end=(today + timedelta(days=60)).strftime("%Y%m%d"),
            )
        ):
            outcome = await service.refresh_feed(db_session, "SEPTA_METRO")

        assert outcome is GTFSRefreshOutcome.REFRESHED

        (status,) = await service.get_feed_statuses(db_session, ["SEPTA_METRO"])

        assert status.feed_start_date == metro_start, (
            "The bundle was dated from a bus calendar that is never ingested "
            f"(feed_start_date={status.feed_start_date}, "
            f"Metro service starts {metro_start})"
        )
        assert status.is_not_yet_active is True, (
            "A bundle whose only ingested service starts in three days read as "
            "active, so /health and verify-deployment.sh both pass while Metro "
            "serves nothing"
        )

    async def test_parse_dates_the_bundle_end_only_by_service_it_ingests(
        self, db_session: AsyncSession
    ):
        """The mirror bound: a running bus calendar must not mask a lapsed Metro one.

        `max(end_date)` has the same blind spot as `min(start_date)`, and it
        feeds `is_lapsed` — the check `verify-deployment.sh` has been gating on
        since #1419.
        """
        service = GTFSService()
        today = now_et().date()
        metro_end = today - timedelta(days=2)

        with _stub_download(
            _split_route_type_zip(
                rail_start=(today - timedelta(days=60)).strftime("%Y%m%d"),
                rail_end=metro_end.strftime("%Y%m%d"),
                bus_start=(today - timedelta(days=60)).strftime("%Y%m%d"),
                bus_end=(today + timedelta(days=60)).strftime("%Y%m%d"),
            )
        ):
            outcome = await service.refresh_feed(db_session, "SEPTA_METRO")

        assert outcome is GTFSRefreshOutcome.REFRESHED

        (status,) = await service.get_feed_statuses(db_session, ["SEPTA_METRO"])

        assert status.feed_end_date == metro_end, (
            "The bundle's expiry was taken from a bus calendar that is never "
            f"ingested (feed_end_date={status.feed_end_date}, Metro service "
            f"ended {metro_end})"
        )
        assert status.is_lapsed is True, (
            "A bundle whose ingested service expired two days ago read as "
            "in-force because an excluded bus calendar is still running"
        )

    async def test_successful_refresh_stamps_the_parse_the_sweep_reads(
        self, db_session: AsyncSession
    ):
        """A real parse must leave the feed reporting healthy, with counts.

        `last_successful_parse_at` is the single field the staleness sweep and
        `/health` both read. If the success path stopped writing it, the sweep
        would alarm nightly on a perfectly healthy source.
        """
        service = GTFSService()

        with _stub_download(build_gtfs_zip(trips=3)):
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
        # The calendar-derived service window landed too — the write half of
        # the #1770 detection chain. If the parse stopped producing these stats
        # the columns would quietly stay NULL, and NULL reads as unknown, so
        # `is_not_yet_active` / `is_lapsed` would never fire again while every
        # status-level test (which seeds the columns by hand) stayed green.
        assert feed_info.feed_start_date == date(2026, 1, 1)
        assert feed_info.feed_end_date == date(2026, 12, 31)

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

        with _stub_download(build_gtfs_zip(trips=2)):
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

        with _stub_download(build_gtfs_zip(trips=4, service_id="OLD")):
            assert await service.refresh_feed(db_session, "PATH", force=True) is (
                GTFSRefreshOutcome.REFRESHED
            )
        with _stub_download(build_gtfs_zip(trips=2, service_id="NEW")):
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

    async def test_calendar_dates_additions_bridge_a_future_calendar_window(
        self, db_session: AsyncSession
    ):
        """A bundle bridged by date additions before its calendar opens is
        serving, and must not read as pending.

        `get_active_service_ids` activates an addition-dated service with no
        start-date constraint, so a feed whose calendar.txt window opens
        tomorrow but which carries a calendar_dates.txt addition for today
        genuinely serves today. If `feed_start_date` were derived from
        calendar.txt alone, /health would report the source pending — and
        verify-deployment.sh would fail the deploy — while its departure board
        was full.
        """
        today = now_et().date()
        service = GTFSService()

        with _stub_download(
            build_gtfs_zip(
                trips=2,
                start_date=(today + timedelta(days=1)).strftime("%Y%m%d"),
                end_date=(today + timedelta(days=21)).strftime("%Y%m%d"),
                calendar_dates_rows=[f"WKDY,{today.strftime('%Y%m%d')},1"],
            )
        ):
            outcome = await service.refresh_feed(db_session, "PATCO", force=True)
        assert outcome is GTFSRefreshOutcome.REFRESHED

        # Serving really does start today — the fact the bounds must agree with.
        active = await service.get_active_service_ids(db_session, "PATCO", today)
        assert active == {"WKDY"}

        feed_info = (
            await db_session.execute(
                select(GTFSFeedInfo).where(GTFSFeedInfo.data_source == "PATCO")
            )
        ).scalar_one()
        assert feed_info.feed_start_date == today
        assert feed_info.feed_end_date == today + timedelta(days=21)

        (status,) = await service.get_feed_statuses(db_session, ["PATCO"])
        assert status.is_not_yet_active is False
        assert status.days_until_feed_start == 0

    async def test_shared_bundle_bounds_come_from_retained_routes_only(
        self, db_session: AsyncSession
    ):
        """Calendar rows of routes we do not ingest must not set the bounds.

        SEPTA_METRO parses the shared google_bus.zip, keeping only the rail
        route types; the ~131 bus routes ride along in calendar.txt. A bus
        calendar in force today would drag min(start_date) into the past and
        mask a rail network that has no service until tomorrow — the exact
        #1770 blackout, reading as active because of a network this source
        never serves. The bus calendar's later end date would overstate the
        runway the same way.
        """
        assert GTFS_ROUTE_TYPE_FILTER.get("SEPTA_METRO") == frozenset({"0", "1"})
        today = now_et().date()
        service = GTFSService()

        with _stub_download(
            build_gtfs_zip(
                trips=2,
                route_type="0",  # trolley — retained by the filter
                start_date=(today + timedelta(days=1)).strftime("%Y%m%d"),
                end_date=(today + timedelta(days=21)).strftime("%Y%m%d"),
                extra_route_rows=["RBUS,TB,Test Bus,3,0000ff"],
                extra_calendar_rows=[
                    "BUSWKDY,1,1,1,1,1,1,1,"
                    f"{(today - timedelta(days=30)).strftime('%Y%m%d')},"
                    f"{(today + timedelta(days=60)).strftime('%Y%m%d')}"
                ],
                extra_trip_rows=["TBUS1,BUSWKDY,RBUS,Test Bus Terminal,0"],
                extra_stop_time_rows=[
                    "TBUS1,06:00:00,06:00:00,S1,1",
                    "TBUS1,06:30:00,06:30:00,S2,2",
                ],
            )
        ):
            outcome = await service.refresh_feed(db_session, "SEPTA_METRO", force=True)
        assert outcome is GTFSRefreshOutcome.REFRESHED

        feed_info = (
            await db_session.execute(
                select(GTFSFeedInfo).where(GTFSFeedInfo.data_source == "SEPTA_METRO")
            )
        ).scalar_one()
        # The bus route and its trip were dropped by the filter...
        assert feed_info.route_count == 1
        assert feed_info.trip_count == 2
        # ...so the bounds are the rail service's window, not the bus row that
        # would otherwise dominate both min() and max().
        assert feed_info.feed_start_date == today + timedelta(days=1)
        assert feed_info.feed_end_date == today + timedelta(days=21)

        (status,) = await service.get_feed_statuses(db_session, ["SEPTA_METRO"])
        assert status.is_not_yet_active is True
        assert status.days_until_feed_start == 1

    async def test_a_retained_expired_row_cannot_hide_an_all_future_timetable(
        self, db_session: AsyncSession
    ):
        """Issue #1799: `feed_start_date` was a bare `min()` over start dates.

        Real bundles keep expired historical calendar rows. One of them, on a
        service some retained trip still references, drags that minimum into
        the past — so `days_until_feed_start` goes negative and
        `is_not_yet_active` reports False for a bundle that describes no
        service today. That is #1770's original symptom reached through the
        very check built to catch it.

        The route-type scoping fixed one level of this (a *bus* calendar
        vouching for rail); this is the level below, where both services are
        ingested and the aggregate itself is the wrong shape.

        Driven through the first-ever-download path deliberately. #1769's guard
        declines a not-yet-active bundle only when a usable one is stored, so
        the two paths that adopt one anyway are the only ones where this
        detection is the entire defence — and a freshly published bundle is
        exactly where retained historical rows show up.
        """
        service = GTFSService()
        today = now_et().date()
        real_start = today + timedelta(days=5)

        # Nothing stored: `gtfs_first_bundle_not_yet_active` adopts this.
        assert await _stored_trip_ids(db_session, "SEPTA_RR") == set()

        with _stub_download(
            build_gtfs_zip(
                trips=2,
                start_date=real_start.strftime("%Y%m%d"),
                end_date=(today + timedelta(days=90)).strftime("%Y%m%d"),
                # A retained historical row: expired, but its service is
                # referenced by a trip below, so it survives the retained-trips
                # scoping and reaches the aggregate.
                extra_calendar_rows=["HIST,1,1,1,1,1,0,0,20250106,20250301"],
                extra_trip_rows=["TH1,HIST,R1,Test Terminal,0"],
                extra_stop_time_rows=[
                    "TH1,06:00:00,06:00:00,S1,1",
                    "TH1,06:30:00,06:30:00,S2,2",
                ],
            )
        ):
            outcome = await service.refresh_feed(db_session, "SEPTA_RR", force=True)

        assert outcome is GTFSRefreshOutcome.REFRESHED
        # Both services really were ingested — otherwise the historical row
        # never reaches the derivation and this test proves nothing.
        assert await _stored_trip_ids(db_session, "SEPTA_RR") == {"T1", "T2", "TH1"}

        # The ground truth the bounds have to agree with: the source is dark.
        assert await service.get_active_service_ids(db_session, "SEPTA_RR", today) == (
            set()
        )

        feed_info = (
            await db_session.execute(
                select(GTFSFeedInfo).where(GTFSFeedInfo.data_source == "SEPTA_RR")
            )
        ).scalar_one()
        assert feed_info.feed_start_date == real_start, (
            "feed_start_date was taken from an expired historical calendar row "
            f"(got {feed_info.feed_start_date}, real service starts "
            f"{real_start}), so /health reports the source active while it "
            "serves nothing"
        )

        (status,) = await service.get_feed_statuses(db_session, ["SEPTA_RR"])
        assert status.is_not_yet_active is True, (
            "A bundle serving no trains today read as active: "
            "not_yet_active_sources stays empty, verify-deployment.sh passes, "
            "and the source is dark until the start date arrives"
        )
        assert status.days_until_feed_start == 5
        # The end bound is a separate max() and must be untouched by this.
        assert status.is_lapsed is False

    async def test_a_retained_expired_row_does_not_make_a_live_bundle_pending(
        self, db_session: AsyncSession
    ):
        """The companion no-false-pending case, and the reason the derivation
        is not simply "the earliest *future* start".

        Almost every real bundle carries historical rows next to the service
        that is actually running. If the fix above reported the earliest future
        start unconditionally, a perfectly healthy source with next season's
        calendar already shipped would read as pending — degrading /health and
        failing `verify-deployment.sh` on every deploy, forever. Service having
        begun is what decides, and then the past minimum is the honest answer.
        """
        service = GTFSService()
        today = now_et().date()

        with _stub_download(
            build_gtfs_zip(
                trips=2,
                start_date=(today - timedelta(days=7)).strftime("%Y%m%d"),
                end_date=(today + timedelta(days=30)).strftime("%Y%m%d"),
                extra_calendar_rows=[
                    # Expired historical row...
                    "HIST,1,1,1,1,1,0,0,20250106,20250301",
                    # ...and next season's, shipped early. Neither may unseat
                    # the window covering today.
                    f"NEXT,1,1,1,1,1,0,0,{(today + timedelta(days=31)).strftime('%Y%m%d')},"
                    f"{(today + timedelta(days=120)).strftime('%Y%m%d')}",
                    # Runs all seven days, so "this bundle serves today" is
                    # true whatever weekday CI runs on. The fixture's default
                    # WKDY row is weekday-only, which would make the ground
                    # truth below pass Mon-Fri and fail at the weekend.
                    f"DAILY,1,1,1,1,1,1,1,{(today - timedelta(days=7)).strftime('%Y%m%d')},"
                    f"{(today + timedelta(days=30)).strftime('%Y%m%d')}",
                ],
                extra_trip_rows=[
                    "TH1,HIST,R1,Test Terminal,0",
                    "TN1,NEXT,R1,Test Terminal,0",
                    "TD1,DAILY,R1,Test Terminal,0",
                ],
                extra_stop_time_rows=[
                    "TH1,06:00:00,06:00:00,S1,1",
                    "TH1,06:30:00,06:30:00,S2,2",
                    "TN1,07:00:00,07:00:00,S1,1",
                    "TN1,07:30:00,07:30:00,S2,2",
                    "TD1,08:00:00,08:00:00,S1,1",
                    "TD1,08:30:00,08:30:00,S2,2",
                ],
            )
        ):
            outcome = await service.refresh_feed(db_session, "PATCO", force=True)

        assert outcome is GTFSRefreshOutcome.REFRESHED
        # The bundle genuinely runs trains today.
        assert "DAILY" in await service.get_active_service_ids(
            db_session, "PATCO", today
        )

        (status,) = await service.get_feed_statuses(db_session, ["PATCO"])
        assert status.is_not_yet_active is False, (
            "A source serving trains right now read as pending, which degrades "
            "/health and fails verify-deployment.sh on a correct deployment"
        )
        assert status.feed_start_date == date(2025, 1, 6)
        assert status.days_until_feed_start is not None
        assert status.days_until_feed_start < 0


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

    async def test_declined_source_is_named_and_alone_stays_below_error(
        self, db_engine, db_session: AsyncSession
    ):
        """The PR's headline property: a decline must not page.

        An agency publishing next week's bundle early is expected operation —
        the stored bundle is still the correct thing to serve — but it must not
        read as an ordinary skip either: `{source}_refreshed: false` alone is
        the indistinguishable-from-routine state that hid #1646.
        """
        await _seed_feed(db_session, "NJT", parsed_hours_ago=1)
        await _seed_feed(db_session, "SEPTA_RR", parsed_hours_ago=20)

        captured = await _run_refresh_job(
            db_engine,
            {
                "NJT": GTFSRefreshOutcome.REFRESHED,
                "SEPTA_RR": GTFSRefreshOutcome.SKIPPED_NOT_YET_ACTIVE,
            },
        )

        event = _completion_event(captured)
        assert event["log_level"] == "info"
        assert event["declined_sources"] == {"SEPTA_RR": "skipped_not_yet_active"}

    async def test_a_long_decline_stretch_still_escalates_via_staleness(
        self, db_engine, db_session: AsyncSession
    ):
        """Declines don't advance the parse timestamp — deliberately.

        An agency publishing 3+ days early crosses GTFS_STALE_FEED_HOURS
        mid-wait: the deployment really is pinned to an aging bundle it cannot
        replace yet, so the nightly summary escalates via `stale_sources` while
        `declined_sources` on the same line says why. An operator paged on day
        three of an expected decline stretch finds both names together.
        """
        await _seed_feed(db_session, "NJT", parsed_hours_ago=1)
        await _seed_feed(db_session, "SEPTA_RR", parsed_hours_ago=72)

        captured = await _run_refresh_job(
            db_engine,
            {
                "NJT": GTFSRefreshOutcome.REFRESHED,
                "SEPTA_RR": GTFSRefreshOutcome.SKIPPED_NOT_YET_ACTIVE,
            },
        )

        event = _completion_event(captured)
        assert event["log_level"] == "error"
        assert not event["failed_sources"]
        assert set(event["stale_sources"]) == {"SEPTA_RR"}
        assert event["declined_sources"] == {"SEPTA_RR": "skipped_not_yet_active"}

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
                "PATCO": build_gtfs_zip(trips=2),
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
