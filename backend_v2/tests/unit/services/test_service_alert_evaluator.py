"""
Tests for service alert (planned work) evaluation in alert_evaluator.py.

Tests GTFS route ID mapping, alert matching, message building,
and end-to-end evaluation with real PostgreSQL via db_session fixture.
APNS send calls are mocked since we cannot hit Apple's servers.
"""

import time
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import (
    DeviceToken,
    RouteAlertSubscription,
    ServiceAlert,
)
from trackrat.services.alert_evaluator import (
    PLANNED_WORK_LOOKAHEAD_HOURS,
    _build_service_alert_message,
    _find_matching_alerts,
    _get_gtfs_route_ids_for_subscription,
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
    line_id: str = "subway-G",
    direction: str | None = None,
    include_planned_work: bool = True,
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
        # Default: starting in 12 hours (within 48h lookahead)
        active_start = now_epoch + 43200
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
            line_id="subway-G",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        assert "G" in result

    def test_subway_multi_line_route(self):
        """Subway routes with multiple lines return all line codes."""
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="SUBWAY",
            line_id="subway-456",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        # subway-456 should map to "4", "5", "6" line codes
        assert "4" in result or "5" in result or "6" in result

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

    def test_no_line_id_returns_empty(self):
        """Subscriptions without line_id return empty set."""
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="SUBWAY",
            from_station_code="A42",
            to_station_code="A36",
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

    def test_non_mta_source_returns_empty(self):
        """Non-MTA data sources return empty (no GTFS mapping for NJT/Amtrak)."""
        sub = RouteAlertSubscription(
            device_id="dev1",
            data_source="NJT",
            line_id="njt-nec",
        )
        result = _get_gtfs_route_ids_for_subscription(sub)
        # NJT line codes won't match SUBWAY/LIRR/MNR branches
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
            active_start = now_epoch + 3600  # 1h from now
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
        result = _find_matching_alerts(
            [alert], "SUBWAY", {"G"}, now_epoch, now_epoch + 172800
        )
        assert len(result) == 1

    def test_no_match_different_routes(self):
        """Alert not matching any subscription routes is excluded."""
        now_epoch = int(time.time())
        alert = self._make_alert(route_ids=["4", "5"])
        result = _find_matching_alerts(
            [alert], "SUBWAY", {"G"}, now_epoch, now_epoch + 172800
        )
        assert len(result) == 0

    def test_no_match_different_data_source(self):
        """Alert from different data source is excluded."""
        now_epoch = int(time.time())
        alert = self._make_alert(data_source="LIRR", route_ids=["1"])
        result = _find_matching_alerts(
            [alert], "SUBWAY", {"G"}, now_epoch, now_epoch + 172800
        )
        assert len(result) == 0

    def test_matches_currently_active_alert(self):
        """Alert currently in an active period is returned."""
        now_epoch = int(time.time())
        alert = self._make_alert(
            active_start=now_epoch - 3600,  # started 1h ago
            active_end=now_epoch + 3600,  # ends in 1h
        )
        result = _find_matching_alerts(
            [alert], "SUBWAY", {"G"}, now_epoch, now_epoch + 172800
        )
        assert len(result) == 1

    def test_excludes_past_alert(self):
        """Alert whose active period already ended is excluded."""
        now_epoch = int(time.time())
        alert = self._make_alert(
            active_start=now_epoch - 86400,  # started 24h ago
            active_end=now_epoch - 3600,  # ended 1h ago
        )
        result = _find_matching_alerts(
            [alert], "SUBWAY", {"G"}, now_epoch, now_epoch + 172800
        )
        assert len(result) == 0

    def test_excludes_far_future_alert(self):
        """Alert starting beyond the lookahead window is excluded."""
        now_epoch = int(time.time())
        far_future = now_epoch + (PLANNED_WORK_LOOKAHEAD_HOURS * 3600) + 7200
        alert = self._make_alert(active_start=far_future)
        result = _find_matching_alerts(
            [alert],
            "SUBWAY",
            {"G"},
            now_epoch,
            now_epoch + (PLANNED_WORK_LOOKAHEAD_HOURS * 3600),
        )
        assert len(result) == 0

    def test_matches_upcoming_within_lookahead(self):
        """Alert starting within lookahead window is returned."""
        now_epoch = int(time.time())
        alert = self._make_alert(active_start=now_epoch + 7200)  # 2h from now
        result = _find_matching_alerts(
            [alert], "SUBWAY", {"G"}, now_epoch, now_epoch + 172800
        )
        assert len(result) == 1


class TestBuildServiceAlertMessage:
    """Tests for _build_service_alert_message() formatting."""

    def _make_sub(self, data_source="SUBWAY", line_id="subway-G"):
        return RouteAlertSubscription(
            device_id="dev1",
            data_source=data_source,
            line_id=line_id,
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
            line_id="subway-G",
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
            line_id="subway-G",
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

    async def test_skips_non_mta_data_source(self, db_session: AsyncSession):
        """Subscriptions for non-MTA systems are skipped even with planned work opt-in."""
        _make_subscription(
            db_session,
            data_source="NJT",
            line_id="njt-nec",
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
            line_id="subway-G",
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
            line_id="subway-G",
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
        device = DeviceToken(device_id="no-token-dev", apns_token=None)
        db_session.add(device)
        sub = RouteAlertSubscription(
            device_id="no-token-dev",
            data_source="SUBWAY",
            line_id="subway-G",
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

    async def test_station_pair_subscription_skipped(self, db_session: AsyncSession):
        """Station-pair subscriptions (no line_id) are skipped for service alerts."""
        device = DeviceToken(device_id="station-dev", apns_token="token-sp")
        db_session.add(device)
        sub = RouteAlertSubscription(
            device_id="station-dev",
            data_source="SUBWAY",
            from_station_code="A42",
            to_station_code="A36",
            include_planned_work=True,
        )
        db_session.add(sub)
        _make_service_alert(
            db_session,
            data_source="SUBWAY",
            route_ids=["A", "C", "E"],
        )
        await db_session.flush()

        apns = _make_apns()
        count = await evaluate_service_alerts(db_session, apns)
        assert count == 0
