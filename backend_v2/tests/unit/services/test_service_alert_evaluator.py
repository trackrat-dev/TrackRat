"""
Tests for service alert (planned work) evaluation in alert_evaluator.py.

Tests GTFS route ID mapping, alert matching, message building,
and end-to-end evaluation with real PostgreSQL via db_session fixture.
APNS send calls are mocked since we cannot hit Apple's servers.
"""

import json
import time
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.collectors.service_alerts import _SEPTA_ROUTE_TO_LINE_CODE
from trackrat.config.route_topology import ALL_ROUTES
from trackrat.models.database import (
    DeviceToken,
    RouteAlertSubscription,
    ServiceAlert,
)
from trackrat.services.alert_evaluator import (
    APNS_PAYLOAD_LIMIT_BYTES,
    _build_service_alert_message,
    _find_matching_alerts,
    _get_gtfs_route_ids_for_subscription,
    _get_route_name_for_subscription,
    _line_codes_to_gtfs_ids,
    evaluate_service_alerts,
)


def _make_apns(send_returns: bool = True) -> AsyncMock:
    """Create a mock APNS service that records calls."""
    apns = AsyncMock()
    apns.send_alert_notification = AsyncMock(return_value=send_returns)
    return apns


def _make_subscription(
    db: AsyncSession,
    *,
    device_id: str = "test-device-sa",
    apns_token: str = "fake-token-sa",
    data_source: str = "SUBWAY",
    line_id: str | None = "subway-g",
    direction: str | None = None,
    include_planned_work: bool = True,
    active_days: int = 127,
    active_start_minutes: int | None = None,
    active_end_minutes: int | None = None,
    timezone: str | None = None,
) -> tuple[DeviceToken, RouteAlertSubscription]:
    """Create a DeviceToken + RouteAlertSubscription pair for service alert testing."""
    device = DeviceToken(device_id=device_id, apns_token=apns_token)
    db.add(device)

    sub = RouteAlertSubscription(
        device_id=device_id,
        data_source=data_source,
        line_id=line_id,
        direction=direction,
        include_planned_work=include_planned_work,
        active_days=active_days,
        active_start_minutes=active_start_minutes,
        active_end_minutes=active_end_minutes,
        timezone=timezone,
    )
    db.add(sub)
    return device, sub


def _make_service_alert(
    db: AsyncSession,
    *,
    alert_id: str = "lmm:planned_work:100",
    data_source: str = "SUBWAY",
    alert_type: str = "planned_work",
    route_ids: list[str] | None = None,
    header: str = "G train: No service this weekend",
    active_start: int | None = None,
    active_end: int | None = None,
) -> ServiceAlert:
    """Create a ServiceAlert record for testing."""
    now_epoch = int(time.time())
    if active_start is None:
        # Default: currently active (started 1 hour ago)
        active_start = now_epoch - 3600
    if active_end is None:
        active_end = active_start + 86400  # 24h duration

    alert = ServiceAlert(
        alert_id=alert_id,
        data_source=data_source,
        alert_type=alert_type,
        affected_route_ids=route_ids or ["G"],
        header_text=header,
        description_text="Detailed description here",
        active_periods=[{"start": active_start, "end": active_end}],
    )
    db.add(alert)
    return alert


class TestGetGtfsRouteIdsForSubscription:
    """Tests for _get_gtfs_route_ids_for_subscription()."""

    def test_subway_line_maps_directly(self):
        """Subway line codes ARE the GTFS route IDs."""
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="SUBWAY",
            line_id="subway-g",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        assert "G" in result

    def test_subway_single_line_route(self):
        """Individual subway line returns its GTFS route ID."""
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="SUBWAY",
            line_id="subway-4",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        assert "4" in result

    def test_lirr_maps_via_routes_dict(self):
        """LIRR line codes map to GTFS route IDs via LIRR_ROUTES."""
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="LIRR",
            line_id="lirr-babylon",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        # Should return at least one GTFS ID
        assert len(result) > 0

    def test_mnr_maps_via_routes_dict(self):
        """MNR line codes map to GTFS route IDs via MNR_ROUTES."""
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="MNR",
            line_id="mnr-hudson",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        assert len(result) > 0

    def test_station_pair_returns_matching_route_ids(self):
        """Station-pair subs return GTFS IDs for routes covering that segment."""
        # NY and JAM are both on LIRR Babylon Branch
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="LIRR",
            from_station_code="NY",
            to_station_code="JAM",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        # Should find at least the Babylon branch GTFS ID
        assert len(result) > 0

    def test_station_pair_uses_equivalent_codes(self):
        """Station-pair route inference should honor station equivalence groups."""
        # SD19 (14 St/6 Av) is equivalent to S132, which is on the 1 line —
        # NY is no longer equivalent to a subway platform code (#1355).
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="SUBWAY",
            from_station_code="SD19",
            to_station_code="S116",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        assert "1" in result

    def test_station_pair_no_matching_route_returns_empty(self):
        """Station-pair with stations not on any shared route returns empty."""
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="SUBWAY",
            from_station_code="FAKE1",
            to_station_code="FAKE2",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        assert result == set()

    def test_train_specific_sub_returns_empty(self):
        """Train-specific subs (no line_id, no station pair) return empty."""
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="SUBWAY",
            train_id="3254",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        assert result == set()

    def test_unknown_line_id_returns_empty(self):
        """Unknown line_id returns empty set."""
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="SUBWAY",
            line_id="subway-FAKE",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        assert result == set()

    def test_njt_line_maps_to_line_codes(self):
        """NJT line IDs map to their 2-letter line codes."""
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="NJT",
            line_id="njt-nec",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        assert "NE" in result

    def test_njt_station_pair_finds_matching_routes(self):
        """NJT station-pair subs find routes covering that segment."""
        # NY and NP are both on the Northeast Corridor
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="NJT",
            from_station_code="NY",
            to_station_code="NP",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        assert "NE" in result

    def test_unsupported_source_returns_empty(self):
        """Data sources without alert support return empty."""
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="AMTRAK",
            line_id="amtrak-nec",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        assert result == set()

    def test_septa_rr_line_maps_to_line_code(self):
        """SEPTA Regional Rail line IDs resolve to their canonical line code."""
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="SEPTA_RR",
            line_id="septa-rr-tre",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        # Exact: the collector stores this literal string on Trenton Line
        # alerts, and a prefix slip would silently match nothing.
        assert result == {"SEPTA-TRE"}

    def test_septa_metro_line_maps_to_line_code(self):
        """SEPTA Metro line IDs resolve to their canonical line code."""
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="SEPTA_METRO",
            line_id="septa-metro-l1",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        assert result == {"SEPTA-L1"}

    def test_septa_rr_station_pair_finds_matching_route(self):
        """SEPTA RR station-pair subs derive the route covering the segment."""
        # Trenton Transit Center -> Levittown is Trenton Line only; the
        # West Trenton Line shares neither stop, so it must not appear.
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="SEPTA_RR",
            from_station_code="SEPR90701",
            to_station_code="SEPR90702",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        assert result == {"SEPTA-TRE"}

    def test_septa_metro_station_pair_finds_matching_route(self):
        """SEPTA Metro station-pair subs derive the route covering the segment."""
        # Fern Rock Transit Center -> Olney Transit Center is Broad St local.
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="SEPTA_METRO",
            from_station_code="SEPM20965",
            to_station_code="SEPM33027",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        assert result == {"SEPTA-B1"}

    def test_septa_unknown_line_id_returns_empty(self):
        """An unknown SEPTA line_id resolves to nothing, not to everything."""
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="SEPTA_RR",
            line_id="septa-rr-bogus",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        assert result == set()


class TestFindMatchingAlerts:
    """Tests for _find_matching_alerts() filtering."""

    def _make_alert(
        self,
        db: AsyncSession | None = None,
        *,
        alert_id: str = "lmm:planned_work:200",
        data_source: str = "SUBWAY",
        route_ids: list[str] | None = None,
        active_start: int | None = None,
        active_end: int | None = None,
    ) -> ServiceAlert:
        """Create a ServiceAlert object (not persisted to DB)."""
        now_epoch = int(time.time())
        if active_start is None:
            active_start = now_epoch - 3600  # started 1h ago
        if active_end is None:
            active_end = active_start + 86400

        return ServiceAlert(
            alert_id=alert_id,
            data_source=data_source,
            alert_type="planned_work",
            affected_route_ids=route_ids or ["G"],
            header_text="Planned work on G",
            active_periods=[{"start": active_start, "end": active_end}],
            is_active=True,
        )

    def test_matches_by_route_overlap(self):
        """Alert matching routes in subscription is returned."""
        now_epoch = int(time.time())
        alert = self._make_alert(route_ids=["G", "F"])
        result = _find_matching_alerts([alert], "SUBWAY", {"G"}, now_epoch)
        assert len(result) == 1

    def test_no_match_different_routes(self):
        """Alert not matching any subscription routes is excluded."""
        now_epoch = int(time.time())
        alert = self._make_alert(route_ids=["4", "5"])
        result = _find_matching_alerts([alert], "SUBWAY", {"G"}, now_epoch)
        assert len(result) == 0

    def test_no_match_different_data_source(self):
        """Alert from different data source is excluded."""
        now_epoch = int(time.time())
        alert = self._make_alert(data_source="LIRR", route_ids=["1"])
        result = _find_matching_alerts([alert], "SUBWAY", {"G"}, now_epoch)
        assert len(result) == 0

    def test_matches_currently_active_alert(self):
        """Alert currently in an active period is returned."""
        now_epoch = int(time.time())
        alert = self._make_alert(
            active_start=now_epoch - 3600,  # started 1h ago
            active_end=now_epoch + 3600,  # ends in 1h
        )
        result = _find_matching_alerts([alert], "SUBWAY", {"G"}, now_epoch)
        assert len(result) == 1

    def test_excludes_past_alert(self):
        """Alert whose active period already ended is excluded."""
        now_epoch = int(time.time())
        alert = self._make_alert(
            active_start=now_epoch - 86400,  # started 24h ago
            active_end=now_epoch - 3600,  # ended 1h ago
        )
        result = _find_matching_alerts([alert], "SUBWAY", {"G"}, now_epoch)
        assert len(result) == 0

    def test_excludes_future_not_yet_active_alert(self):
        """Alert starting in the future (not yet active) is excluded."""
        now_epoch = int(time.time())
        alert = self._make_alert(active_start=now_epoch + 7200)  # 2h from now
        result = _find_matching_alerts([alert], "SUBWAY", {"G"}, now_epoch)
        assert len(result) == 0


class TestLineCodesToGtfsIds:
    """Tests for _line_codes_to_gtfs_ids() helper."""

    def test_subway_line_codes_are_gtfs_ids(self):
        """Subway line codes map directly to GTFS route IDs."""
        result = _line_codes_to_gtfs_ids("SUBWAY", frozenset({"G", "F"}))
        assert result == {"G", "F"}

    def test_lirr_maps_via_reverse_dict(self):
        """LIRR line codes map to GTFS IDs via LIRR_ROUTES reverse map."""
        result = _line_codes_to_gtfs_ids("LIRR", frozenset({"LIRR-BB"}))
        assert len(result) > 0

    def test_mnr_maps_via_reverse_dict(self):
        """MNR line codes map to GTFS IDs via MNR_ROUTES reverse map."""
        result = _line_codes_to_gtfs_ids("MNR", frozenset({"MNR-HUD"}))
        assert len(result) > 0

    def test_njt_line_codes_pass_through(self):
        """NJT line codes pass through directly (same format as alert route IDs)."""
        result = _line_codes_to_gtfs_ids("NJT", frozenset({"NE", "NC"}))
        assert result == {"NE", "NC"}

    def test_unknown_source_returns_empty(self):
        """Unsupported data source returns empty set."""
        result = _line_codes_to_gtfs_ids("AMTRAK", frozenset({"NEC"}))
        assert result == set()

    def test_empty_line_codes_returns_empty(self):
        """Empty line_codes input returns empty set."""
        result = _line_codes_to_gtfs_ids("SUBWAY", frozenset())
        assert result == set()

    def test_septa_rr_line_codes_pass_through(self):
        """SEPTA RR line codes are the alert route IDs (collector normalizes)."""
        result = _line_codes_to_gtfs_ids(
            "SEPTA_RR", frozenset({"SEPTA-TRE", "SEPTA-WTR"})
        )
        assert result == {"SEPTA-TRE", "SEPTA-WTR"}

    def test_septa_metro_line_codes_pass_through(self):
        """SEPTA Metro line codes are the alert route IDs."""
        result = _line_codes_to_gtfs_ids(
            "SEPTA_METRO", frozenset({"SEPTA-L1", "SEPTA-T1"})
        )
        assert result == {"SEPTA-L1", "SEPTA-T1"}

    def test_septa_unknown_code_is_dropped(self):
        """An obsolete SEPTA code narrows to nothing rather than passing through."""
        result = _line_codes_to_gtfs_ids(
            "SEPTA_RR", frozenset({"SEPTA-TRE", "SEPTA-RETIRED"})
        )
        assert result == {"SEPTA-TRE"}

    def test_septa_cross_system_code_is_dropped(self):
        """A Metro code offered under SEPTA_RR does not resolve, and vice versa."""
        assert _line_codes_to_gtfs_ids("SEPTA_RR", frozenset({"SEPTA-L1"})) == set()
        assert _line_codes_to_gtfs_ids("SEPTA_METRO", frozenset({"SEPTA-TRE"})) == set()

    def test_septa_accepted_codes_match_what_the_collector_emits(self):
        """The evaluator accepts exactly the codes the collector can store.

        Both sides derive from SEPTA_{RR,METRO}_ROUTES, but through separate
        module-level constants. This asserts the shared contract directly so
        the two cannot drift apart the way they did before #1631 — a code the
        collector can emit but the evaluator rejects means silent non-delivery.
        """
        for data_source, code_map in _SEPTA_ROUTE_TO_LINE_CODE.items():
            emitted = set(code_map.values())
            accepted = {
                code
                for code in emitted
                if _line_codes_to_gtfs_ids(data_source, frozenset({code}))
            }
            assert accepted == emitted, f"{data_source} rejects {emitted - accepted}"

    def test_septa_topology_line_codes_are_all_accepted(self):
        """Every SEPTA route in the topology resolves to a non-empty route ID set.

        A subscription can name any of these routes, so any route the evaluator
        cannot resolve is a subscription that can never be notified.
        """
        septa_routes = [
            r for r in ALL_ROUTES if r.data_source in ("SEPTA_RR", "SEPTA_METRO")
        ]
        assert len(septa_routes) == 26  # 13 Regional Rail + 13 Metro
        for route in septa_routes:
            resolved = _line_codes_to_gtfs_ids(route.data_source, route.line_codes)
            assert resolved == set(route.line_codes), route.id


class TestGetRouteNameForSubscription:
    """Tests for _get_route_name_for_subscription()."""

    def test_line_based_sub_returns_route_name(self):
        """Line-based subscription returns the route's display name."""
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="SUBWAY",
            line_id="subway-g",
        )
        name = _get_route_name_for_subscription(sub)
        assert name  # Should be a non-empty string
        assert name != "SUBWAY"  # Should be the route name, not fallback

    def test_station_pair_sub_returns_route_name(self):
        """Station-pair subscription returns the name of a matching route."""
        # NY and JAM are on LIRR Babylon Branch
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="LIRR",
            from_station_code="NY",
            to_station_code="JAM",
        )
        name = _get_route_name_for_subscription(sub)
        assert name  # Should find a route name
        assert name != "LIRR"  # Should not be the fallback

    def test_station_pair_route_name_uses_equivalent_codes(self):
        """Station-pair route names should resolve through station equivalences."""
        # SD19 (14 St/6 Av) is equivalent to S132, which is on the 1 line —
        # NY is no longer equivalent to a subway platform code (#1355).
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="SUBWAY",
            from_station_code="SD19",
            to_station_code="S116",
        )
        name = _get_route_name_for_subscription(sub)
        assert name == "1 Broadway - 7 Avenue Local"

    def test_station_pair_no_match_returns_data_source(self):
        """Station-pair with no matching route falls back to data_source."""
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="SUBWAY",
            from_station_code="FAKE1",
            to_station_code="FAKE2",
        )
        name = _get_route_name_for_subscription(sub)
        assert name == "SUBWAY"

    def test_train_specific_sub_returns_data_source(self):
        """Train-specific sub (no line_id, no stations) falls back to data_source."""
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="SUBWAY",
            train_id="3254",
        )
        name = _get_route_name_for_subscription(sub)
        assert name == "SUBWAY"


class TestBuildServiceAlertMessage:
    """Tests for _build_service_alert_message() formatting."""

    def _make_sub(
        self,
        data_source="SUBWAY",
        line_id="subway-g",
        from_station_code=None,
        to_station_code=None,
    ):
        return RouteAlertSubscription(
            device_id="dev1",
            data_source=data_source,
            line_id=line_id,
            from_station_code=from_station_code,
            to_station_code=to_station_code,
            include_planned_work=True,
        )

    def _make_alert_obj(
        self, alert_id="lmm:planned_work:1", header="G train: No weekend service"
    ):
        return ServiceAlert(
            alert_id=alert_id,
            data_source="SUBWAY",
            alert_type="planned_work",
            affected_route_ids=["G"],
            header_text=header,
            active_periods=[{"start": 1710100000, "end": 1710200000}],
            is_active=True,
        )

    def test_single_alert_message(self):
        """Single alert produces title with route name and body with header text."""
        sub = self._make_sub()
        alert = self._make_alert_obj()
        title, body = _build_service_alert_message(sub, [alert])

        assert "SUBWAY" in title
        assert "Planned work" in title or "planned work" in title.lower()
        assert body == "G train: No weekend service"

    def test_multiple_alerts_message(self):
        """Multiple alerts produce title with count and body with first header + count."""
        sub = self._make_sub()
        alerts = [
            self._make_alert_obj(alert_id="a1", header="G: No service Saturday"),
            self._make_alert_obj(alert_id="a2", header="G: Shuttle bus Sunday"),
        ]
        title, body = _build_service_alert_message(sub, alerts)

        assert "2" in title
        assert "+1 more" in body

    def test_station_pair_sub_uses_route_name(self):
        """Station-pair sub message uses the matched route name, not station codes."""
        # SH11 and SH06 are on the A train
        sub = self._make_sub(
            data_source="SUBWAY",
            line_id=None,
            from_station_code="SH11",
            to_station_code="SH06",
        )
        alert = self._make_alert_obj(header="A train: Weekend changes")
        title, body = _build_service_alert_message(sub, [alert])

        assert "SUBWAY" in title
        assert "planned work" in title.lower()
        # Should use a route name, not "Unknown" or raw station codes
        assert "Unknown" not in title
        assert "SH11" not in title
        assert body == "A train: Weekend changes"


@pytest.mark.asyncio
class TestEvaluateServiceAlerts:
    """End-to-end tests for evaluate_service_alerts()."""

    async def test_no_alerts_sends_nothing(self, db_session: AsyncSession):
        """With no service alerts in DB, zero notifications are sent."""
        _make_subscription(db_session)
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)
        assert count == 0
        apns.send_alert_notification.assert_not_called()

    async def test_matching_alert_sends_notification(self, db_session: AsyncSession):
        """A planned work alert matching a subscription triggers a notification."""
        _make_subscription(
            db_session,
            data_source="SUBWAY",
            line_id="subway-g",
            include_planned_work=True,
        )
        _make_service_alert(
            db_session,
            data_source="SUBWAY",
            route_ids=["G"],
            header="G: No service this weekend",
        )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)

        assert count == 1
        apns.send_alert_notification.assert_called_once()

        call_args = apns.send_alert_notification.call_args
        title = call_args.args[1]
        body = call_args.args[2]
        assert "SUBWAY" in title
        assert "G: No service this weekend" in body

    async def test_skips_subscription_without_planned_work_opt_in(
        self, db_session: AsyncSession
    ):
        """Subscriptions with include_planned_work=False are skipped."""
        _make_subscription(
            db_session,
            data_source="SUBWAY",
            line_id="subway-g",
            include_planned_work=False,
        )
        _make_service_alert(
            db_session,
            data_source="SUBWAY",
            route_ids=["G"],
        )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)
        assert count == 0

    async def test_njt_planned_work_sends_notification(self, db_session: AsyncSession):
        """NJT planned work alert matching a subscription triggers a notification."""
        _make_subscription(
            db_session,
            device_id="njt-dev",
            apns_token="njt-token",
            data_source="NJT",
            line_id="njt-nec",
            include_planned_work=True,
        )
        _make_service_alert(
            db_session,
            alert_id="njt-msg-abc123",
            data_source="NJT",
            alert_type="planned_work",
            route_ids=["NE"],
            header="NEC: Weekend track work between Newark and New York",
        )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)

        assert count == 1
        apns.send_alert_notification.assert_called_once()

        call_args = apns.send_alert_notification.call_args
        body = call_args.args[2]
        assert "NEC: Weekend track work" in body

    async def test_njt_realtime_alert_sends_notification(
        self, db_session: AsyncSession
    ):
        """NJT real-time alert (RSS) matching a subscription triggers a notification."""
        _make_subscription(
            db_session,
            device_id="njt-rt-dev",
            apns_token="njt-rt-token",
            data_source="NJT",
            line_id="njt-nec",
            include_planned_work=True,
        )
        _make_service_alert(
            db_session,
            alert_id="njt-rss-999",
            data_source="NJT",
            alert_type="alert",
            route_ids=["NE"],
            header="NEC train #3837 is up to 15 min. late.",
        )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)

        assert count == 1

    async def test_septa_rr_line_alert_sends_notification(
        self, db_session: AsyncSession
    ):
        """A SEPTA Regional Rail line subscription receives its route's alert."""
        _make_subscription(
            db_session,
            device_id="septa-rr-dev",
            apns_token="septa-rr-token",
            data_source="SEPTA_RR",
            line_id="septa-rr-tre",
            include_planned_work=True,
        )
        _make_service_alert(
            db_session,
            alert_id="septa-rr-1",
            data_source="SEPTA_RR",
            route_ids=["SEPTA-TRE"],
            header="Trenton Line: Weekend track work",
        )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)

        assert count == 1
        body = apns.send_alert_notification.call_args.args[2]
        assert "Trenton Line: Weekend track work" in body

    async def test_septa_metro_line_alert_sends_notification(
        self, db_session: AsyncSession
    ):
        """A SEPTA Metro line subscription receives its route's alert."""
        _make_subscription(
            db_session,
            device_id="septa-metro-dev",
            apns_token="septa-metro-token",
            data_source="SEPTA_METRO",
            line_id="septa-metro-l1",
            include_planned_work=True,
        )
        _make_service_alert(
            db_session,
            alert_id="septa-metro-1",
            data_source="SEPTA_METRO",
            alert_type="alert",
            route_ids=["SEPTA-L1"],
            header="Market-Frankford Line: Delays due to a disabled train",
        )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)

        assert count == 1
        body = apns.send_alert_notification.call_args.args[2]
        assert "Market-Frankford Line" in body

    async def test_septa_sibling_route_alert_sends_nothing(
        self, db_session: AsyncSession
    ):
        """An alert for a different SEPTA route does not reach the subscriber."""
        _make_subscription(
            db_session,
            device_id="septa-sib-dev",
            apns_token="septa-sib-token",
            data_source="SEPTA_RR",
            line_id="septa-rr-tre",
            include_planned_work=True,
        )
        _make_service_alert(
            db_session,
            alert_id="septa-rr-2",
            data_source="SEPTA_RR",
            route_ids=["SEPTA-WTR"],
            header="West Trenton Line: Weekend track work",
        )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)
        assert count == 0
        apns.send_alert_notification.assert_not_called()

    async def test_septa_cross_system_alert_sends_nothing(
        self, db_session: AsyncSession
    ):
        """A Metro alert does not reach a Regional Rail subscriber."""
        _make_subscription(
            db_session,
            device_id="septa-cross-dev",
            apns_token="septa-cross-token",
            data_source="SEPTA_RR",
            line_id="septa-rr-tre",
            include_planned_work=True,
        )
        _make_service_alert(
            db_session,
            alert_id="septa-metro-2",
            data_source="SEPTA_METRO",
            route_ids=["SEPTA-L1"],
            header="Market-Frankford Line: Delays",
        )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)
        assert count == 0

    async def test_septa_system_wide_subscription_still_matches(
        self, db_session: AsyncSession
    ):
        """System-wide SEPTA subscriptions keep matching every route's alert."""
        _make_subscription(
            db_session,
            device_id="septa-sw-dev",
            apns_token="septa-sw-token",
            data_source="SEPTA_RR",
            line_id=None,
            include_planned_work=True,
        )
        _make_service_alert(
            db_session,
            alert_id="septa-rr-3",
            data_source="SEPTA_RR",
            route_ids=["SEPTA-WTR"],
            header="West Trenton Line: Weekend track work",
        )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)
        assert count == 1

    async def test_septa_station_pair_subscription_sends_notification(
        self, db_session: AsyncSession
    ):
        """A SEPTA station-pair commute subscription receives its route's alert."""
        device = DeviceToken(device_id="septa-sp-dev", apns_token="septa-sp-token")
        db_session.add(device)
        # Trenton Transit Center -> Levittown, both on the Trenton Line only.
        sub = RouteAlertSubscription(
            device_id="septa-sp-dev",
            data_source="SEPTA_RR",
            from_station_code="SEPR90701",
            to_station_code="SEPR90702",
            include_planned_work=True,
        )
        db_session.add(sub)
        _make_service_alert(
            db_session,
            alert_id="septa-rr-4",
            data_source="SEPTA_RR",
            route_ids=["SEPTA-TRE"],
            header="Trenton Line: Weekend track work",
        )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)

        assert count == 1
        call_args = apns.send_alert_notification.call_args
        custom_data = call_args.kwargs.get("custom_data") or call_args.args[3]
        sa_payload = custom_data["service_alert"]
        assert sa_payload["from_station_code"] == "SEPR90701"
        assert sa_payload["to_station_code"] == "SEPR90702"

    async def test_septa_station_pair_ignores_sibling_route_alert(
        self, db_session: AsyncSession
    ):
        """A station-pair sub does not receive alerts for routes it doesn't ride."""
        device = DeviceToken(device_id="septa-sp2-dev", apns_token="septa-sp2-token")
        db_session.add(device)
        sub = RouteAlertSubscription(
            device_id="septa-sp2-dev",
            data_source="SEPTA_RR",
            from_station_code="SEPR90701",
            to_station_code="SEPR90702",
            include_planned_work=True,
        )
        db_session.add(sub)
        _make_service_alert(
            db_session,
            alert_id="septa-rr-5",
            data_source="SEPTA_RR",
            route_ids=["SEPTA-WTR"],
            header="West Trenton Line: Weekend track work",
        )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)
        assert count == 0

    async def test_skips_unsupported_data_source(self, db_session: AsyncSession):
        """Subscriptions for unsupported systems are skipped even with planned work opt-in."""
        _make_subscription(
            db_session,
            data_source="AMTRAK",
            line_id="amtrak-nec",
            include_planned_work=True,
        )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)
        assert count == 0

    async def test_dedup_prevents_resend(self, db_session: AsyncSession):
        """Same alert is not sent twice to the same subscription."""
        _make_subscription(
            db_session,
            data_source="SUBWAY",
            line_id="subway-g",
            include_planned_work=True,
        )
        _make_service_alert(
            db_session,
            alert_id="lmm:planned_work:500",
            data_source="SUBWAY",
            route_ids=["G"],
        )
        await db_session.flush()

        apns = _make_apns()

        # First evaluation sends the notification
        count1 = await evaluate_service_alerts(db_session, apns)
        assert count1 == 1

        # Second evaluation should not resend
        count2 = await evaluate_service_alerts(db_session, apns)
        assert count2 == 0

    async def test_new_alert_after_dedup_triggers_notification(
        self, db_session: AsyncSession
    ):
        """A new alert triggers a notification even after previous dedup."""
        _make_subscription(
            db_session,
            data_source="SUBWAY",
            line_id="subway-g",
            include_planned_work=True,
        )
        _make_service_alert(
            db_session,
            alert_id="lmm:planned_work:600",
            data_source="SUBWAY",
            route_ids=["G"],
            header="First planned work",
        )
        await db_session.flush()

        apns = _make_apns()
        count1 = await evaluate_service_alerts(db_session, apns)
        assert count1 == 1

        # Add a new alert
        _make_service_alert(
            db_session,
            alert_id="lmm:planned_work:601",
            data_source="SUBWAY",
            route_ids=["G"],
            header="Second planned work",
        )
        await db_session.flush()

        count2 = await evaluate_service_alerts(db_session, apns)
        assert count2 == 1

    async def test_no_device_token_skips_send(self, db_session: AsyncSession):
        """Subscriptions on devices without APNS token are skipped."""
        device = DeviceToken(device_id="no-token-dev", apns_token="")
        db_session.add(device)
        sub = RouteAlertSubscription(
            device_id="no-token-dev",
            data_source="SUBWAY",
            line_id="subway-g",
            include_planned_work=True,
        )
        db_session.add(sub)
        _make_service_alert(
            db_session,
            data_source="SUBWAY",
            route_ids=["G"],
        )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)
        assert count == 0

    async def test_station_pair_subscription_sends_notification(
        self, db_session: AsyncSession
    ):
        """Station-pair subscriptions receive planned work alerts for matching routes."""
        device = DeviceToken(device_id="station-dev", apns_token="token-sp")
        db_session.add(device)
        # SH11 and SH06 are both on the A train route
        sub = RouteAlertSubscription(
            device_id="station-dev",
            data_source="SUBWAY",
            from_station_code="SH11",
            to_station_code="SH06",
            include_planned_work=True,
        )
        db_session.add(sub)
        _make_service_alert(
            db_session,
            data_source="SUBWAY",
            route_ids=["A"],
            header="A train: No service this weekend",
        )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)
        assert count == 1

        call_args = apns.send_alert_notification.call_args
        title = call_args.args[1]
        body = call_args.args[2]
        assert "SUBWAY" in title
        assert "A train: No service this weekend" in body

        # custom_data should include station pair info
        custom_data = call_args.kwargs.get("custom_data") or call_args.args[3]
        sa_payload = custom_data["service_alert"]
        assert sa_payload["from_station_code"] == "SH11"
        assert sa_payload["to_station_code"] == "SH06"
        assert "line_id" not in sa_payload

    async def test_station_pair_no_match_sends_nothing(self, db_session: AsyncSession):
        """Station-pair sub with no matching route for the alert sends nothing."""
        device = DeviceToken(device_id="station-dev2", apns_token="token-sp2")
        db_session.add(device)
        # SH11 and SH06 are on the A train, but alert is for G
        sub = RouteAlertSubscription(
            device_id="station-dev2",
            data_source="SUBWAY",
            from_station_code="SH11",
            to_station_code="SH06",
            include_planned_work=True,
        )
        db_session.add(sub)
        _make_service_alert(
            db_session,
            data_source="SUBWAY",
            route_ids=["G"],
            header="G train: No service this weekend",
        )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)
        assert count == 0

    async def test_bidirectional_subs_same_device_sends_once(
        self, db_session: AsyncSession
    ):
        """Two subscriptions on the same device for opposite directions of the same
        route should only produce one push notification per service alert.

        This is the exact scenario: user subscribes to Hamilton->NYP and NYP->Hamilton,
        and a service alert affects the Northeast Corridor. Both subscriptions match
        the same alert, but the device should only receive one notification.
        """
        device = DeviceToken(device_id="bidir-dev", apns_token="bidir-token")
        db_session.add(device)

        # Hamilton (HL) -> NY (NJT Northeast Corridor)
        sub_forward = RouteAlertSubscription(
            device_id="bidir-dev",
            data_source="NJT",
            from_station_code="HL",
            to_station_code="NY",
            include_planned_work=True,
        )
        db_session.add(sub_forward)

        # NY -> Hamilton (reverse direction, same route)
        sub_reverse = RouteAlertSubscription(
            device_id="bidir-dev",
            data_source="NJT",
            from_station_code="NY",
            to_station_code="HL",
            include_planned_work=True,
        )
        db_session.add(sub_reverse)

        _make_service_alert(
            db_session,
            alert_id="njt-msg-nec-weekend",
            data_source="NJT",
            alert_type="planned_work",
            route_ids=["NE"],
            header="NEC: Weekend track work between Newark and New York",
        )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)

        # Only ONE notification should be sent despite two matching subscriptions
        assert count == 1
        assert apns.send_alert_notification.call_count == 1

        # Both subscriptions should have the alert tracked in last_service_alert_ids
        # so neither retries on the next cycle
        assert "njt-msg-nec-weekend" in (sub_forward.last_service_alert_ids or [])
        assert "njt-msg-nec-weekend" in (sub_reverse.last_service_alert_ids or [])

    async def test_bidirectional_subs_different_devices_sends_both(
        self, db_session: AsyncSession
    ):
        """Two subscriptions on DIFFERENT devices for opposite directions should
        each receive a notification — dedup is per-device, not global.
        """
        device_a = DeviceToken(device_id="dev-a", apns_token="token-a")
        device_b = DeviceToken(device_id="dev-b", apns_token="token-b")
        db_session.add(device_a)
        db_session.add(device_b)

        sub_a = RouteAlertSubscription(
            device_id="dev-a",
            data_source="NJT",
            from_station_code="HL",
            to_station_code="NY",
            include_planned_work=True,
        )
        sub_b = RouteAlertSubscription(
            device_id="dev-b",
            data_source="NJT",
            from_station_code="NY",
            to_station_code="HL",
            include_planned_work=True,
        )
        db_session.add(sub_a)
        db_session.add(sub_b)

        _make_service_alert(
            db_session,
            alert_id="njt-msg-nec-both",
            data_source="NJT",
            alert_type="planned_work",
            route_ids=["NE"],
            header="NEC: Service change",
        )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)

        # Both devices should get a notification
        assert count == 2
        assert apns.send_alert_notification.call_count == 2

    async def test_bidirectional_dedup_does_not_block_different_alerts(
        self, db_session: AsyncSession
    ):
        """Dedup only suppresses the same alert_id. Different alerts on the same
        device with overlapping subscriptions should all be sent.
        """
        device = DeviceToken(device_id="multi-alert-dev", apns_token="multi-token")
        db_session.add(device)

        sub_forward = RouteAlertSubscription(
            device_id="multi-alert-dev",
            data_source="SUBWAY",
            line_id="subway-g",
            include_planned_work=True,
        )
        sub_reverse = RouteAlertSubscription(
            device_id="multi-alert-dev",
            data_source="SUBWAY",
            line_id="subway-g",
            include_planned_work=True,
        )
        db_session.add(sub_forward)
        db_session.add(sub_reverse)

        # Two different alerts on the same route
        _make_service_alert(
            db_session,
            alert_id="lmm:planned_work:alpha",
            data_source="SUBWAY",
            route_ids=["G"],
            header="G: No service Saturday",
        )
        _make_service_alert(
            db_session,
            alert_id="lmm:planned_work:beta",
            data_source="SUBWAY",
            route_ids=["G"],
            header="G: Shuttle bus Sunday",
        )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)

        # Only 1 notification should be sent (both alerts bundled via first sub,
        # second sub deduplicated)
        assert count == 1
        assert apns.send_alert_notification.call_count == 1

        # Both subs should track both alert IDs
        assert "lmm:planned_work:alpha" in (sub_forward.last_service_alert_ids or [])
        assert "lmm:planned_work:beta" in (sub_forward.last_service_alert_ids or [])
        assert "lmm:planned_work:alpha" in (sub_reverse.last_service_alert_ids or [])
        assert "lmm:planned_work:beta" in (sub_reverse.last_service_alert_ids or [])

    async def test_bidirectional_dedup_next_cycle_stays_quiet(
        self, db_session: AsyncSession
    ):
        """After dedup suppresses a duplicate, the next evaluation cycle should
        not re-send the suppressed alert. Verifies that last_service_alert_ids
        is updated even when the notification was deduplicated.
        """
        device = DeviceToken(device_id="cycle-dev", apns_token="cycle-token")
        db_session.add(device)

        sub1 = RouteAlertSubscription(
            device_id="cycle-dev",
            data_source="NJT",
            from_station_code="HL",
            to_station_code="NY",
            include_planned_work=True,
        )
        sub2 = RouteAlertSubscription(
            device_id="cycle-dev",
            data_source="NJT",
            from_station_code="NY",
            to_station_code="HL",
            include_planned_work=True,
        )
        db_session.add(sub1)
        db_session.add(sub2)

        _make_service_alert(
            db_session,
            alert_id="njt-msg-cycle-test",
            data_source="NJT",
            alert_type="planned_work",
            route_ids=["NE"],
            header="NEC: Track work",
        )
        await db_session.flush()

        apns = _make_apns()

        # First cycle: 1 notification
        count1 = await evaluate_service_alerts(db_session, apns)
        assert count1 == 1

        # Second cycle: 0 notifications (both subs already tracked the alert)
        count2 = await evaluate_service_alerts(db_session, apns)
        assert count2 == 0
        # Total calls should still be 1
        assert apns.send_alert_notification.call_count == 1

    async def test_dedup_state_prunes_ids_whose_alerts_left_the_feed(
        self, db_session: AsyncSession
    ):
        """The notified set is pruned to alerts still active, not capped at 50.

        Replaces an earlier test that asserted a fixed 50-id FIFO. That cap was
        the #1747 defect: it could not cover a matched set larger than itself,
        so still-active ids fell off the tail and were re-pushed forever. The
        bound is now the feed itself — ids for alerts that have gone are
        dropped, so the list can never exceed the active set.
        """
        device, sub = _make_subscription(
            db_session,
            device_id="dedup-prune-dev",
            apns_token="token-prune",
            data_source="SUBWAY",
            line_id="subway-g",
            include_planned_work=True,
        )
        # 49 ids from alerts that are no longer in the feed (no ServiceAlert row)
        stale_ids = [f"lmm:planned_work:old-{i}" for i in range(49)]
        sub.last_service_alert_ids = list(stale_ids)

        for i in range(3):
            _make_service_alert(
                db_session,
                alert_id=f"lmm:planned_work:new-{i}",
                data_source="SUBWAY",
                route_ids=["G"],
                header=f"New planned work #{i}",
            )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)
        assert count == 1, f"Expected one bundled push, got {count}"

        retained = set(sub.last_service_alert_ids)
        expected = {f"lmm:planned_work:new-{i}" for i in range(3)}
        assert retained == expected, (
            "Retained set must be exactly the still-active alerts. Extra: "
            f"{sorted(retained - expected)}, missing: {sorted(expected - retained)}"
        )
        assert not (retained & set(stale_ids)), (
            "Ids whose alerts left the feed must be pruned, but these survived: "
            f"{sorted(retained & set(stale_ids))}"
        )


@pytest.mark.asyncio
class TestServiceAlertTimeWindow:
    """Tests that service alerts respect active_days and time window settings.

    Regression tests for bug where evaluate_service_alerts bypassed
    day-of-week and time window checks that evaluate_route_alerts
    correctly applied, causing users to receive service alert
    notifications outside their configured schedule.
    """

    async def test_active_days_skips_weekend(self, db_session: AsyncSession):
        """active_days=31 (Mon-Fri) should NOT send service alerts on Saturday."""
        # Saturday 2026-02-21 10:00 ET
        fake_saturday = datetime(2026, 2, 21, 10, 0, 0)
        assert fake_saturday.weekday() == 5, "Sanity check: 2026-02-21 is Saturday"

        _make_subscription(
            db_session,
            device_id="sa-weekend-dev",
            apns_token="sa-weekend-token",
            data_source="SUBWAY",
            line_id="subway-g",
            include_planned_work=True,
            active_days=31,  # Mon-Fri only
        )
        _make_service_alert(
            db_session,
            data_source="SUBWAY",
            route_ids=["G"],
            header="G: No service this weekend",
        )
        await db_session.flush()

        apns = _make_apns()
        with patch(
            "trackrat.services.alert_evaluator.now_et", return_value=fake_saturday
        ):
            count = await evaluate_service_alerts(db_session, apns)

        assert count == 0, "active_days=31 should suppress service alerts on weekends"
        apns.send_alert_notification.assert_not_called()
        print("  Verified: service alert weekend skip works with active_days bitmask")

    async def test_active_days_fires_on_weekday(self, db_session: AsyncSession):
        """active_days=31 (Mon-Fri) should send service alerts on Wednesday."""
        # Wednesday 2026-02-18 10:00 ET
        fake_wednesday = datetime(2026, 2, 18, 10, 0, 0)
        assert fake_wednesday.weekday() == 2, "Sanity check: 2026-02-18 is Wednesday"
        fake_epoch = int(fake_wednesday.timestamp())

        _make_subscription(
            db_session,
            device_id="sa-weekday-dev",
            apns_token="sa-weekday-token",
            data_source="SUBWAY",
            line_id="subway-g",
            include_planned_work=True,
            active_days=31,  # Mon-Fri only
        )
        _make_service_alert(
            db_session,
            alert_id="lmm:planned_work:weekday-test",
            data_source="SUBWAY",
            route_ids=["G"],
            header="G: Planned track work",
            active_start=fake_epoch - 3600,
            active_end=fake_epoch + 86400,
        )
        await db_session.flush()

        apns = _make_apns()
        with patch(
            "trackrat.services.alert_evaluator.now_et", return_value=fake_wednesday
        ):
            count = await evaluate_service_alerts(db_session, apns)

        assert count == 1, "active_days=31 should fire service alerts on weekdays"
        apns.send_alert_notification.assert_called_once()
        print("  Verified: service alert fires on weekday with active_days bitmask")

    async def test_time_window_outside_range_suppresses(self, db_session: AsyncSession):
        """Service alerts outside the configured time window should be suppressed."""
        # Wednesday 2026-02-18 23:30 ET (11:30 PM, outside 6AM-8PM window)
        fake_late_night = datetime(2026, 2, 18, 23, 30, 0)
        assert fake_late_night.weekday() == 2, "Sanity check: Wednesday"

        _make_subscription(
            db_session,
            device_id="sa-timewin-dev",
            apns_token="sa-timewin-token",
            data_source="SUBWAY",
            line_id="subway-g",
            include_planned_work=True,
            active_days=127,  # All days
            active_start_minutes=360,  # 6:00 AM
            active_end_minutes=1200,  # 8:00 PM
            timezone="America/New_York",
        )
        _make_service_alert(
            db_session,
            alert_id="lmm:planned_work:late-night",
            data_source="SUBWAY",
            route_ids=["G"],
            header="G: Late night service change",
        )
        await db_session.flush()

        apns = _make_apns()
        with patch(
            "trackrat.services.alert_evaluator.now_et", return_value=fake_late_night
        ):
            count = await evaluate_service_alerts(db_session, apns)

        assert count == 0, "Service alerts outside time window should be suppressed"
        apns.send_alert_notification.assert_not_called()
        print("  Verified: service alert suppressed outside time window")

    async def test_time_window_inside_range_fires(self, db_session: AsyncSession):
        """Service alerts inside the configured time window should fire."""
        # Wednesday 2026-02-18 12:00 ET (noon, inside 6AM-8PM window)
        fake_noon = datetime(2026, 2, 18, 12, 0, 0)
        assert fake_noon.weekday() == 2, "Sanity check: Wednesday"
        fake_epoch = int(fake_noon.timestamp())

        _make_subscription(
            db_session,
            device_id="sa-timewin-ok-dev",
            apns_token="sa-timewin-ok-token",
            data_source="SUBWAY",
            line_id="subway-g",
            include_planned_work=True,
            active_days=127,  # All days
            active_start_minutes=360,  # 6:00 AM
            active_end_minutes=1200,  # 8:00 PM
            timezone="America/New_York",
        )
        _make_service_alert(
            db_session,
            alert_id="lmm:planned_work:noon-test",
            data_source="SUBWAY",
            route_ids=["G"],
            header="G: Midday service change",
            active_start=fake_epoch - 3600,
            active_end=fake_epoch + 86400,
        )
        await db_session.flush()

        apns = _make_apns()
        with patch("trackrat.services.alert_evaluator.now_et", return_value=fake_noon):
            count = await evaluate_service_alerts(db_session, apns)

        assert count == 1, "Service alerts inside time window should fire"
        apns.send_alert_notification.assert_called_once()
        print("  Verified: service alert fires inside time window")

    async def test_no_time_window_always_fires(self, db_session: AsyncSession):
        """Subscriptions without time window configured should always fire."""
        # Wednesday 2026-02-18 03:00 ET (3 AM)
        fake_3am = datetime(2026, 2, 18, 3, 0, 0)
        fake_epoch = int(fake_3am.timestamp())

        _make_subscription(
            db_session,
            device_id="sa-nowin-dev",
            apns_token="sa-nowin-token",
            data_source="SUBWAY",
            line_id="subway-g",
            include_planned_work=True,
            active_days=127,  # All days
            # No time window set (active_start_minutes=None, active_end_minutes=None)
        )
        _make_service_alert(
            db_session,
            alert_id="lmm:planned_work:nowin-test",
            data_source="SUBWAY",
            route_ids=["G"],
            header="G: Early morning service change",
            active_start=fake_epoch - 3600,
            active_end=fake_epoch + 86400,
        )
        await db_session.flush()

        apns = _make_apns()
        with patch("trackrat.services.alert_evaluator.now_et", return_value=fake_3am):
            count = await evaluate_service_alerts(db_session, apns)

        assert count == 1, "No time window = always fire"
        apns.send_alert_notification.assert_called_once()
        print("  Verified: service alert fires when no time window configured")


@pytest.mark.asyncio
class TestServiceAlertDedupConvergence:
    """Issue #1747: a large matched set must converge instead of re-pushing.

    The old dedupe kept only the last 50 notified ids. A subscription matching
    more than 50 active alerts could never record its whole matched set, so the
    overflow was "new" again on the next 5-minute cycle and was pushed to the
    device forever. These tests pin the convergence, the retry-on-failure
    behavior, and the payload bound that the fix depends on.
    """

    @staticmethod
    def _seed_alerts(db_session: AsyncSession, count: int, prefix: str) -> list[str]:
        """Create `count` currently-active SUBWAY alerts on the G route.

        Args:
            db_session: Test database session
            count: How many alerts to create
            prefix: Alert-id prefix, unique per test

        Returns:
            The alert ids created
        """
        ids = []
        for i in range(count):
            alert_id = f"lmm:planned_work:{prefix}-{i:03d}"
            _make_service_alert(
                db_session,
                alert_id=alert_id,
                data_source="SUBWAY",
                route_ids=["G"],
                header=f"G train: planned work item {i}",
            )
            ids.append(alert_id)
        return ids

    @staticmethod
    def _pushed_alert_ids(apns: AsyncMock) -> list[str]:
        """Collect every alert id carried by every push made to the mock.

        Args:
            apns: The mocked APNS service

        Returns:
            All alert ids pushed, in call order, including any duplicates
        """
        pushed: list[str] = []
        for call in apns.send_alert_notification.call_args_list:
            payload = call.kwargs["custom_data"]["service_alert"]
            pushed.extend(payload["alert_ids"])
        return pushed

    async def test_system_wide_sub_over_fifty_alerts_goes_quiet_on_cycle_two(
        self, db_session: AsyncSession
    ):
        """60 active alerts: one burst, then silence while the feed is unchanged.

        This is the exact production signature from #1747 — a system-wide
        SUBWAY subscription against a matched set larger than the old 50-id
        buffer. Under the old code cycle 2 re-pushed the 10 that fell off the
        tail, and did so every 5 minutes indefinitely.
        """
        device, sub = _make_subscription(
            db_session,
            device_id="conv-sw-dev",
            apns_token="token-conv-sw",
            data_source="SUBWAY",
            line_id=None,  # system-wide: matches every SUBWAY alert
            include_planned_work=True,
        )
        alert_ids = self._seed_alerts(db_session, 60, "conv-sw")
        await db_session.flush()

        apns = _make_apns()

        first = await evaluate_service_alerts(db_session, apns)
        assert first == 1, f"Expected one bundled push on cycle 1, got {first}"

        retained = set(sub.last_service_alert_ids or [])
        assert retained == set(alert_ids), (
            "All 60 matched alerts must be recorded as notified; missing "
            f"{sorted(set(alert_ids) - retained)}"
        )
        assert len(retained) == 60, (
            "The notified set must not be capped at 50 — that cap is what made "
            f"this loop forever. Got {len(retained)} ids."
        )

        second = await evaluate_service_alerts(db_session, apns)
        assert second == 0, (
            "With the active set unchanged, cycle 2 must send nothing, but it "
            f"sent {second} push(es)"
        )
        assert apns.send_alert_notification.call_count == 1, (
            "Cycle 2 must not reach APNS at all, but total call count is "
            f"{apns.send_alert_notification.call_count}"
        )

        third = await evaluate_service_alerts(db_session, apns)
        assert third == 0, f"Cycle 3 must also stay silent, sent {third}"

    async def test_line_scoped_sub_over_fifty_alerts_also_converges(
        self, db_session: AsyncSession
    ):
        """The defect was never specific to system-wide subscriptions.

        Any subscription whose matched set exceeds 50 hit the same tail
        eviction; system-wide on SUBWAY merely makes it near-certain. A
        line-scoped subscription with 55 matching alerts must converge too.
        """
        device, sub = _make_subscription(
            db_session,
            device_id="conv-line-dev",
            apns_token="token-conv-line",
            data_source="SUBWAY",
            line_id="subway-g",
            include_planned_work=True,
        )
        alert_ids = self._seed_alerts(db_session, 55, "conv-line")
        await db_session.flush()

        apns = _make_apns()

        assert await evaluate_service_alerts(db_session, apns) == 1
        assert set(sub.last_service_alert_ids or []) == set(alert_ids)

        second = await evaluate_service_alerts(db_session, apns)
        assert second == 0, (
            "A line-scoped subscription with 55 matched alerts must also go "
            f"quiet on cycle 2, but it sent {second}"
        )

    async def test_failed_send_leaves_alerts_unnotified_for_retry(
        self, db_session: AsyncSession
    ):
        """A rejected push must not mark its alerts as delivered.

        The old code wrote last_service_alert_ids before awaiting APNS, so a
        rejection (dead token, oversized payload) silently lost those alerts
        for good — turning a notification storm into total silence.
        """
        device, sub = _make_subscription(
            db_session,
            device_id="fail-retry-dev",
            apns_token="token-fail-retry",
            data_source="SUBWAY",
            line_id="subway-g",
            include_planned_work=True,
        )
        alert_ids = self._seed_alerts(db_session, 3, "fail-retry")
        await db_session.flush()

        failing = _make_apns(send_returns=False)
        count = await evaluate_service_alerts(db_session, failing)

        assert count == 0, f"A failed send must count zero alerts sent, got {count}"
        failing.send_alert_notification.assert_called_once()
        assert not sub.last_service_alert_ids, (
            "A failed send must leave the alerts un-notified so the next cycle "
            f"retries them, but state was recorded as {sub.last_service_alert_ids}"
        )

        recovered = _make_apns(send_returns=True)
        count = await evaluate_service_alerts(db_session, recovered)

        assert count == 1, (
            "Once APNS recovers, the previously-failed alerts must be retried, "
            f"but the cycle sent {count}"
        )
        assert set(sub.last_service_alert_ids or []) == set(alert_ids), (
            "After a successful retry all three alerts must be recorded, got "
            f"{sub.last_service_alert_ids}"
        )

    async def test_large_matched_set_stays_under_the_apns_payload_limit(
        self, db_session: AsyncSession
    ):
        """No push may exceed APNS' 4 KB limit, however many alerts match.

        200 alerts' worth of ids is comfortably over the limit in one document,
        so this fails if the payload is not bounded.
        """
        device, sub = _make_subscription(
            db_session,
            device_id="payload-dev",
            apns_token="token-payload",
            data_source="SUBWAY",
            line_id=None,
            include_planned_work=True,
        )
        self._seed_alerts(db_session, 200, "payload")
        await db_session.flush()

        apns = _make_apns()
        await evaluate_service_alerts(db_session, apns)

        apns.send_alert_notification.assert_called_once()
        call = apns.send_alert_notification.call_args
        _token, title, body = call.args
        document = {
            "aps": {"alert": {"title": title, "body": body}, "sound": "default"},
            **call.kwargs["custom_data"],
        }
        size = len(json.dumps(document).encode("utf-8"))
        assert size <= APNS_PAYLOAD_LIMIT_BYTES, (
            f"Push payload is {size} bytes, over the "
            f"{APNS_PAYLOAD_LIMIT_BYTES}-byte APNS limit; APNS would reject it"
        )

        payload = call.kwargs["custom_data"]["service_alert"]
        assert payload["alert_count"] == len(payload["alert_ids"]), (
            "alert_count must describe the ids actually sent, got "
            f"{payload['alert_count']} vs {len(payload['alert_ids'])} ids"
        )
        assert len(payload["alert_ids"]) < 200, (
            "A 200-alert match must have been capped to fit the payload, but "
            f"{len(payload['alert_ids'])} ids went out"
        )

    async def test_capped_remainder_drains_over_cycles_without_repeating(
        self, db_session: AsyncSession
    ):
        """Alerts deferred by the payload cap are delivered later, exactly once.

        Capping must defer, not drop: every matched alert eventually reaches
        the device, no alert is pushed twice, and the loop terminates.
        """
        device, sub = _make_subscription(
            db_session,
            device_id="drain-dev",
            apns_token="token-drain",
            data_source="SUBWAY",
            line_id=None,
            include_planned_work=True,
        )
        alert_ids = self._seed_alerts(db_session, 200, "drain")
        await db_session.flush()

        apns = _make_apns()

        cycles = 0
        while await evaluate_service_alerts(db_session, apns):
            cycles += 1
            assert cycles <= 20, (
                "Draining 200 alerts should take a handful of cycles; 20+ "
                "means the remainder is not converging"
            )

        pushed = self._pushed_alert_ids(apns)
        assert len(pushed) == len(set(pushed)), "An alert was pushed more than once"
        assert set(pushed) == set(alert_ids), (
            "Every matched alert must be delivered eventually; never sent: "
            f"{sorted(set(alert_ids) - set(pushed))}"
        )
        assert cycles > 1, (
            "200 alerts cannot fit one push, so this must have taken multiple "
            f"cycles, but it took {cycles}"
        )

    async def test_notified_state_cannot_grow_beyond_the_active_set(
        self, db_session: AsyncSession
    ):
        """Under churn, stored ids stay bounded by the alerts that still exist.

        Simulates a feed whose alerts turn over: each round deactivates the
        previous batch and adds a new one. The old FIFO grew to its 50-id cap
        and held ids for long-gone alerts; the pruned set tracks the live feed.
        """
        device, sub = _make_subscription(
            db_session,
            device_id="churn-dev",
            apns_token="token-churn",
            data_source="SUBWAY",
            line_id=None,
            include_planned_work=True,
        )
        apns = _make_apns()
        previous: list[ServiceAlert] = []

        for round_index in range(5):
            for alert in previous:
                alert.is_active = False

            current = []
            for i in range(10):
                current.append(
                    _make_service_alert(
                        db_session,
                        alert_id=f"lmm:planned_work:churn-{round_index}-{i}",
                        data_source="SUBWAY",
                        route_ids=["G"],
                        header=f"G train: round {round_index} item {i}",
                    )
                )
            await db_session.flush()

            await evaluate_service_alerts(db_session, apns)

            retained = set(sub.last_service_alert_ids or [])
            expected = {str(a.alert_id) for a in current}
            assert retained == expected, (
                f"After round {round_index} the notified set must track only "
                f"the 10 live alerts. Extra: {sorted(retained - expected)}, "
                f"missing: {sorted(expected - retained)}"
            )
            assert len(retained) <= 10, (
                f"Notified set grew to {len(retained)} ids while only 10 alerts "
                "are active — it is not bounded by the feed"
            )
            previous = current

    async def test_deactivated_alert_that_returns_is_notified_again(
        self, db_session: AsyncSession
    ):
        """Pruning is what lets a recurring alert fire on its next occurrence.

        An alert that leaves the feed and comes back is a new occurrence. If
        its id were retained forever, the return would be silently suppressed.
        """
        device, sub = _make_subscription(
            db_session,
            device_id="return-dev",
            apns_token="token-return",
            data_source="SUBWAY",
            line_id="subway-g",
            include_planned_work=True,
        )
        alert = _make_service_alert(
            db_session,
            alert_id="lmm:planned_work:returning",
            data_source="SUBWAY",
            route_ids=["G"],
            header="G train: weekend service change",
        )
        await db_session.flush()

        apns = _make_apns()
        assert await evaluate_service_alerts(db_session, apns) == 1
        assert set(sub.last_service_alert_ids or []) == {"lmm:planned_work:returning"}

        # Alert leaves the feed; the collector deactivates it.
        alert.is_active = False
        await db_session.flush()
        assert await evaluate_service_alerts(db_session, apns) == 0
        assert not sub.last_service_alert_ids, (
            "Once the alert left the feed its id must be pruned, but state is "
            f"{sub.last_service_alert_ids}"
        )

        # Next occurrence of the same recurring alert.
        alert.is_active = True
        await db_session.flush()
        assert await evaluate_service_alerts(db_session, apns) == 1, (
            "A recurring alert returning to the feed is a new occurrence and "
            "must notify again"
        )
