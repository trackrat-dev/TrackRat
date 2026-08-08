"""Unit tests for SeptaMetroCollector.

Metro trip_ids are already unique per service day, so ``_generate_train_id`` is
the identity function. The collector otherwise mirrors the MBTA absolute-time
flow: group arrivals by trip, back-fill from GTFS static when available, else
build the journey directly from the real-time arrivals.
"""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trackrat.collectors.septa_common import SeptaFeedFetchError
from trackrat.collectors.septa_metro.client import SeptaMetroArrival, SeptaMetroClient
from trackrat.collectors.septa_metro.collector import (
    SeptaMetroCollector,
    _feed_service_date,
    _generate_train_id,
)
from trackrat.utils.time import ET

_T = datetime(2026, 7, 18, 15, 0, 0, tzinfo=UTC)


def _arrival(
    station_code: str,
    trip_id: str,
    route_id: str,
    arrival_time: datetime,
    *,
    departure_time: datetime | None = None,
    delay_seconds: int = 0,
) -> SeptaMetroArrival:
    return SeptaMetroArrival(
        station_code=station_code,
        gtfs_stop_id=station_code.replace("SEPM", ""),
        trip_id=trip_id,
        route_id=route_id,
        direction_id=0,
        headsign=None,
        arrival_time=arrival_time,
        departure_time=departure_time,
        delay_seconds=delay_seconds,
        track=None,
    )


class TestGenerateTrainId:
    """Metro trip_ids are used verbatim as the train id."""

    def test_returns_trip_id_unchanged(self):
        assert _generate_train_id("12345") == "12345"

    def test_returns_complex_trip_id_unchanged(self):
        assert _generate_train_id("M1_weekday_007") == "M1_weekday_007"

    def test_empty_string(self):
        assert _generate_train_id("") == ""


class TestFeedServiceDate:
    """The feed-derived day is only a starting guess.

    It reads the earliest arrival *still in the feed*, so it is stable only while
    no stop has been pruned. ``_resolve_service_dates`` is what turns it into the
    day a journey is actually filed under (issue #1749); these cases pin the
    reading itself.
    """

    def test_uses_earliest_arrival_regardless_of_input_order(self):
        late = _T + timedelta(hours=2)
        arrivals = [
            _arrival("SEPM1273", "trip_A", "M1", late),
            _arrival("SEPM1272", "trip_A", "M1", _T),
        ]
        assert _feed_service_date(arrivals) == _T.astimezone(ET).date()

    def test_uses_eastern_calendar_day_not_utc(self):
        """03:30 UTC is still the previous day in ET — the day the trip belongs to."""
        after_utc_midnight = datetime(2026, 7, 19, 3, 30, 0, tzinfo=UTC)
        arrivals = [_arrival("SEPM1272", "trip_A", "M1", after_utc_midnight)]
        assert _feed_service_date(arrivals) == date(2026, 7, 18)

    def test_drifts_forward_when_the_feed_prunes_pre_midnight_stops(self):
        """The defect this whole mechanism exists to absorb.

        Same physical trip, two successive snapshots. The second is what the feed
        looks like after midnight once the 23:5x stops have been served and
        dropped — and the raw reading flips to the next calendar day, which is
        why nothing may key a journey off it directly.
        """
        before_midnight = ET.localize(datetime(2026, 7, 20, 23, 50, 0))
        after_midnight = ET.localize(datetime(2026, 7, 21, 0, 20, 0))

        full = [
            _arrival("SEPM1272", "trip_A", "M1", before_midnight),
            _arrival("SEPM1273", "trip_A", "M1", after_midnight),
        ]
        pruned = [_arrival("SEPM1273", "trip_A", "M1", after_midnight)]

        assert _feed_service_date(full) == date(2026, 7, 20)
        assert _feed_service_date(pruned) == date(2026, 7, 21), (
            "the raw feed reading is expected to drift across midnight — if this "
            "ever stops being true the resolver's reason for existing changed"
        )


class TestCollectorInit:
    def test_creates_own_client(self):
        collector = SeptaMetroCollector()
        assert collector.client is not None
        assert collector._owns_client is True

    def test_uses_provided_client(self):
        client = SeptaMetroClient()
        collector = SeptaMetroCollector(client=client)
        assert collector.client is client
        assert collector._owns_client is False

    @pytest.mark.asyncio
    async def test_close_owned_client(self):
        collector = SeptaMetroCollector()
        collector.client = AsyncMock(spec=SeptaMetroClient)
        collector._owns_client = True
        await collector.close()
        collector.client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_external_client_not_closed(self):
        client = AsyncMock(spec=SeptaMetroClient)
        collector = SeptaMetroCollector(client=client)
        await collector.close()
        client.close.assert_not_called()


class TestCollect:
    @pytest.fixture
    def mock_client(self):
        return AsyncMock(spec=SeptaMetroClient)

    @pytest.fixture
    def collector(self, mock_client):
        return SeptaMetroCollector(client=mock_client)

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.begin_nested = MagicMock()
        session.begin_nested.return_value.__aenter__ = AsyncMock()
        session.begin_nested.return_value.__aexit__ = AsyncMock(return_value=False)
        # Default: no journey rows on record, so _resolve_service_dates keeps
        # every trip on the day its feed reading gives.
        empty = MagicMock()
        empty.all.return_value = []
        empty.scalars.return_value = []
        session.execute.return_value = empty
        return session

    @pytest.mark.asyncio
    async def test_empty_arrivals_returns_zero_stats(
        self, collector, mock_client, mock_session
    ):
        mock_client.get_all_arrivals.return_value = []
        stats = await collector.collect(mock_session)
        assert stats["total_arrivals"] == 0
        assert stats["discovered"] == 0
        assert stats["updated"] == 0
        mock_client.get_all_arrivals.assert_awaited_once_with(use_cache=False)

    @pytest.mark.asyncio
    async def test_groups_arrivals_by_trip(self, collector, mock_client, mock_session):
        """Arrivals are grouped by trip_id → _process_trip called once per unique trip."""
        arrivals = [
            _arrival("SEPM1272", "trip_A", "M1", _T),
            _arrival("SEPM1273", "trip_A", "M1", _T + timedelta(minutes=5)),
            _arrival("SEPM1392", "trip_B", "L1", _T),
        ]
        mock_client.get_all_arrivals.return_value = arrivals
        collector._process_trip = AsyncMock(return_value=("discovered", None))

        mock_stale = MagicMock()
        mock_stale.all.return_value = []
        mock_stale.scalars.return_value = []
        mock_session.execute.return_value = mock_stale

        stats = await collector.collect(mock_session)

        assert stats["total_arrivals"] == 3
        assert collector._process_trip.call_count == 2  # two unique trips

    @pytest.mark.asyncio
    async def test_present_trip_is_reconciled_when_local_processing_skips_it(
        self, collector, mock_client, mock_session
    ):
        mock_client.get_all_arrivals.return_value = [
            _arrival("SEPM1272", "present_trip", "M1", _T)
        ]
        collector._process_trip = AsyncMock(return_value=(None, None))

        with (
            patch(
                "trackrat.collectors.septa_metro.collector."
                "TransitAnalyzer.analyze_new_segments_bulk",
                new_callable=AsyncMock,
            ),
            patch(
                "trackrat.collectors.septa_metro.collector."
                "reconcile_journey_omissions",
                new_callable=AsyncMock,
                return_value=2,
            ) as reconcile,
        ):
            stats = await collector.collect(mock_session)

        assert stats["expired"] == 2
        assert reconcile.await_args.args[3] == {("present_trip", _T.date())}

    @pytest.mark.asyncio
    async def test_fetch_error_propagates_and_never_reconciles_omissions(
        self, collector, mock_client, mock_session
    ):
        """A failed fetch must reach the scheduler so the run is not stamped
        successful, and must never touch omission state (PR #1640 follow-up 2)."""
        mock_client.get_all_arrivals.side_effect = SeptaFeedFetchError("unavailable")

        with patch(
            "trackrat.collectors.septa_metro.collector.reconcile_journey_omissions",
            new_callable=AsyncMock,
        ) as reconcile:
            with pytest.raises(SeptaFeedFetchError):
                await collector.collect(mock_session)

        reconcile.assert_not_awaited()
        mock_session.rollback.assert_awaited()

    @pytest.mark.asyncio
    async def test_fetch_timeout_propagates_as_feed_fetch_error(
        self, collector, mock_client, mock_session
    ):
        """A hung feed is as much a missing snapshot as an HTTP failure."""
        mock_client.get_all_arrivals.side_effect = TimeoutError()

        with patch(
            "trackrat.collectors.septa_metro.collector.reconcile_journey_omissions",
            new_callable=AsyncMock,
        ) as reconcile:
            with pytest.raises(SeptaFeedFetchError):
                await collector.collect(mock_session)

        reconcile.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_all_trip_failures_never_reconcile_omissions(
        self, collector, mock_client, mock_session
    ):
        mock_client.get_all_arrivals.return_value = [
            _arrival("SEPM1272", "broken_trip", "M1", _T)
        ]
        collector._process_trip = AsyncMock(side_effect=ValueError("bad trip"))

        with patch(
            "trackrat.collectors.septa_metro.collector.reconcile_journey_omissions",
            new_callable=AsyncMock,
        ) as reconcile:
            stats = await collector.collect(mock_session)

        assert stats["errors"] == 2
        reconcile.assert_not_awaited()


class TestResolveServiceDates:
    """The service-day rollover guard (issue #1749).

    ``_feed_service_date`` rolls forward mid-trip once GTFS-RT prunes the stops a
    train has passed. Left uncorrected that duplicates the journey, resolves the
    static schedule ~24h into the future, and — because the original key drops
    out of ``present_journey_keys`` — lets ``reconcile_journey_omissions`` expire
    the real, still-running train. These cases pin the correction and, just as
    importantly, its limits: it must not swallow the *next* day's run of a
    recurring trip id into yesterday's row.
    """

    _MON = date(2026, 7, 20)
    _TUE = date(2026, 7, 21)

    @pytest.fixture
    def collector(self):
        return SeptaMetroCollector(client=AsyncMock(spec=SeptaMetroClient))

    def _session_with_live(self, rows):
        """A session whose live-journey query returns ``rows`` of (train_id, date)."""
        result = MagicMock()
        result.all.return_value = rows
        session = AsyncMock()
        session.execute.return_value = result
        return session

    @pytest.mark.asyncio
    async def test_rolled_over_trip_is_pinned_to_the_running_journeys_day(
        self, collector
    ):
        """The bug, directly: feed says Tuesday, the live row says Monday."""
        session = self._session_with_live([("trip_A", self._MON)])

        resolved = await collector._resolve_service_dates(
            session, {"trip_A": self._TUE}
        )

        assert resolved == {"trip_A": self._MON}, (
            "a trip whose feed date rolled past midnight must stay on the service "
            "day its in-flight journey already uses, or the lookup misses and "
            "mints a duplicate while the real row is struck as omitted"
        )

    @pytest.mark.asyncio
    async def test_exact_match_wins_over_the_previous_day(self, collector):
        """A live row on both days must not drag the trip backwards.

        Two consecutive days of the same recurring trip id can legitimately both
        be live for a few minutes around the rollover. The feed's own day is the
        truth whenever it has a row.
        """
        session = self._session_with_live(
            [("trip_A", self._MON), ("trip_A", self._TUE)]
        )

        resolved = await collector._resolve_service_dates(
            session, {"trip_A": self._TUE}
        )

        assert resolved == {"trip_A": self._TUE}

    @pytest.mark.asyncio
    async def test_unknown_trip_keeps_its_feed_date(self, collector):
        """A brand-new trip has nothing to be pinned to."""
        session = self._session_with_live([])

        resolved = await collector._resolve_service_dates(
            session, {"trip_A": self._TUE}
        )

        assert resolved == {"trip_A": self._TUE}

    @pytest.mark.asyncio
    async def test_only_the_immediately_preceding_day_is_considered(self, collector):
        """A two-day-old live row is not a continuation of anything.

        Guards against a stuck row silently adopting every future run of its trip
        id. Only ``feed_date - 1`` can be a midnight continuation.
        """
        session = self._session_with_live([("trip_A", self._MON - timedelta(days=1))])

        resolved = await collector._resolve_service_dates(
            session, {"trip_A": self._TUE}
        )

        assert resolved == {"trip_A": self._TUE}

    @pytest.mark.asyncio
    async def test_finished_and_struck_runs_are_excluded_by_the_query(self, collector):
        """Liveness is enforced in SQL, so assert the SQL actually says so.

        This is what replaces ``septa_rr``'s rollover hour: the next day's run of
        a recurring trip id cannot be mistaken for a continuation because the
        earlier run is by then completed or expired. If these predicates were
        ever dropped, that protection would vanish silently — the happy-path
        tests above would all still pass.
        """
        session = self._session_with_live([])

        await collector._resolve_service_dates(session, {"trip_A": self._TUE})

        rendered = str(session.execute.await_args.args[0]).lower()
        for column in ("is_completed", "is_cancelled", "is_expired"):
            assert f"{column} is not true" in rendered, (
                f"{column} must be excluded from the live-journey lookup, "
                f"otherwise tomorrow's run of trip_A merges into today's row; "
                f"query was: {rendered}"
            )

    @pytest.mark.asyncio
    async def test_no_trips_issues_no_query(self, collector):
        session = self._session_with_live([])
        assert await collector._resolve_service_dates(session, {}) == {}
        session.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_trips_are_resolved_independently(self, collector):
        """One trip rolling over must not move a different trip's day."""
        session = self._session_with_live([("trip_A", self._MON)])

        resolved = await collector._resolve_service_dates(
            session, {"trip_A": self._TUE, "trip_B": self._TUE}
        )

        assert resolved == {"trip_A": self._MON, "trip_B": self._TUE}


class TestCrossMidnightCollection:
    """End-to-end over two successive snapshots, which is what #1749 asks for.

    The first snapshot is the trip before midnight; the second is the same trip
    after midnight with its pre-midnight stops pruned, exactly as GTFS-RT serves
    it. The collector must file both under one service day.
    """

    _MON = date(2026, 7, 20)

    @pytest.fixture
    def collector(self):
        return SeptaMetroCollector(client=AsyncMock(spec=SeptaMetroClient))

    @pytest.mark.asyncio
    async def test_pruned_second_snapshot_keeps_one_journey_and_one_key(
        self, collector
    ):
        before_midnight = ET.localize(datetime(2026, 7, 20, 23, 50, 0))
        after_midnight = ET.localize(datetime(2026, 7, 21, 0, 20, 0))

        collector.client.get_all_arrivals = AsyncMock(
            return_value=[_arrival("SEPM1273", "trip_A", "M1", after_midnight)]
        )
        collector._process_trip = AsyncMock(return_value=("updated", None))

        # The row the first (pre-midnight) snapshot created: still running, so
        # still live.
        live_row = MagicMock()
        live_row.all.return_value = [("trip_A", self._MON)]
        session = AsyncMock()
        session.begin_nested = MagicMock()
        session.begin_nested.return_value.__aenter__ = AsyncMock()
        session.begin_nested.return_value.__aexit__ = AsyncMock(return_value=False)
        session.execute.return_value = live_row

        with (
            patch(
                "trackrat.collectors.septa_metro.collector."
                "TransitAnalyzer.analyze_new_segments_bulk",
                new_callable=AsyncMock,
            ),
            patch(
                "trackrat.collectors.septa_metro.collector."
                "reconcile_journey_omissions",
                new_callable=AsyncMock,
                return_value=0,
            ) as reconcile,
        ):
            stats = await collector.collect(session)

        assert _feed_service_date(
            [_arrival("SEPM1273", "trip_A", "M1", after_midnight)]
        ) == date(2026, 7, 21), "precondition: the raw feed reading has drifted"

        assert collector._process_trip.await_args.args[3] == self._MON, (
            "the journey lookup must use Monday, or _process_trip finds no row "
            "and creates a duplicate whose static schedule resolves ~24h out"
        )
        assert reconcile.await_args.args[3] == {("trip_A", self._MON)}, (
            "the presence key must be Monday too — under the Tuesday key the "
            "Monday row counts as omitted and is expired mid-journey"
        )
        assert stats["updated"] == 1
        assert stats["discovered"] == 0, "no second journey may be created"
        assert before_midnight.date() == self._MON


class TestProcessTrip:
    @pytest.fixture
    def collector(self):
        return SeptaMetroCollector(client=AsyncMock(spec=SeptaMetroClient))

    @pytest.mark.asyncio
    async def test_empty_arrivals_returns_none(self, collector):
        session = AsyncMock()
        result, journey = await collector._process_trip(
            session, "trip_1", [], _T.date()
        )
        assert result is None
        assert journey is None

    @pytest.mark.asyncio
    @patch("trackrat.collectors.septa_metro.collector.now_et")
    async def test_discovers_new_journey_without_static(self, mock_now, collector):
        """No GTFS static schedule → build the journey directly from RT arrivals."""
        mock_now.return_value = _T

        collector._gtfs_service = MagicMock()
        collector._gtfs_service.get_static_stop_times = AsyncMock(return_value=None)

        no_existing = MagicMock()
        no_existing.scalar_one_or_none.return_value = None
        session = AsyncMock()
        session.execute.return_value = no_existing

        arrivals = [
            _arrival(
                "SEPM1272", "trip_1", "M1", _T, departure_time=_T + timedelta(minutes=1)
            ),
            _arrival("SEPM1273", "trip_1", "M1", _T + timedelta(minutes=5)),
            _arrival("SEPM1392", "trip_1", "M1", _T + timedelta(minutes=10)),
        ]

        result, journey = await collector._process_trip(
            session, "trip_1", arrivals, _T.date()
        )

        assert result == "discovered"
        assert journey is not None
        assert journey.data_source == "SEPTA_METRO"
        assert journey.train_id == "trip_1"
        assert journey.line_code == "SEPTA-M1"
        assert session.add.call_count >= 1

    @pytest.mark.asyncio
    @patch("trackrat.collectors.septa_metro.collector.now_et")
    async def test_updates_existing_journey(self, mock_now, collector):
        """An existing journey for the same train/day is updated, not recreated."""
        mock_now.return_value = _T

        existing_journey = MagicMock()
        existing_journey.id = 1
        existing_journey.train_id = "trip_1"
        existing_journey.data_source = "SEPTA_METRO"
        existing_journey.stops = []
        existing_journey.is_completed = False
        existing_journey.is_cancelled = False
        existing_journey.is_expired = True
        existing_journey.api_error_count = 3

        found = MagicMock()
        found.scalar_one_or_none.return_value = existing_journey
        session = AsyncMock()
        session.execute.return_value = found

        arrivals = [
            _arrival("SEPM1272", "trip_1", "M1", _T),
            _arrival("SEPM1273", "trip_1", "M1", _T + timedelta(minutes=5)),
        ]

        result, journey = await collector._process_trip(
            session, "trip_1", arrivals, _T.date()
        )

        assert result == "updated"
        assert journey is existing_journey
        assert journey.api_error_count == 0
        assert journey.is_expired is False


class TestJourneyDetails:
    @pytest.fixture
    def collector(self):
        return SeptaMetroCollector(client=AsyncMock(spec=SeptaMetroClient))

    @pytest.mark.asyncio
    async def test_skips_non_metro_journey(self, collector):
        """A journey from another data source must not touch the Metro feed."""
        journey = MagicMock()
        journey.data_source = "LIRR"
        session = AsyncMock()

        await collector.collect_journey_details(session, journey)
        collector.client.get_all_arrivals.assert_not_called()


class TestRun:
    @pytest.mark.asyncio
    @patch("trackrat.collectors.septa_metro.collector.get_session")
    async def test_run_returns_stats(self, mock_get_session):
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock(spec=SeptaMetroClient)
        mock_client.get_all_arrivals.return_value = []

        collector = SeptaMetroCollector(client=mock_client)
        stats = await collector.run()

        assert isinstance(stats, dict)
        assert "discovered" in stats
        assert "updated" in stats
        assert "errors" in stats
