"""
Tests for route alert evaluation service.

Uses real PostgreSQL via db_session fixture. APNS send calls are mocked
since we cannot hit Apple's servers in tests.
"""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackrat.models.database import (
    DeviceToken,
    RouteAlertSubscription,
    TrainJourney,
)
from trackrat.services.alert_evaluator import (
    COOLDOWN_MINUTES,
    DELAY_THRESHOLD_MINUTES,
    evaluate_route_alerts,
)
from trackrat.utils.time import now_et


def _make_apns(send_returns: bool = True) -> AsyncMock:
    """Create a mock APNS service that records calls."""
    apns = AsyncMock()
    apns.send_alert_notification = AsyncMock(return_value=send_returns)
    return apns


def _make_journey(
    db: AsyncSession,
    *,
    train_id: str,
    data_source: str = "NJT",
    line_code: str = "NE",
    origin: str = "NY",
    terminal: str = "TR",
    delay_minutes: int = 0,
    is_cancelled: bool = False,
    minutes_ago: int = 30,
) -> TrainJourney:
    """Create a TrainJourney record in the past hour window."""
    now = now_et()
    sched = now - timedelta(minutes=minutes_ago)
    actual = sched + timedelta(minutes=delay_minutes) if delay_minutes else sched

    journey = TrainJourney(
        train_id=train_id,
        journey_date=now.date(),
        line_code=line_code,
        line_name="Northeast Corridor",
        destination="Trenton",
        origin_station_code=origin,
        terminal_station_code=terminal,
        data_source=data_source,
        scheduled_departure=sched,
        actual_departure=actual if not is_cancelled else None,
        is_cancelled=is_cancelled,
        has_complete_journey=True,
    )
    db.add(journey)
    return journey


def _make_device_and_sub(
    db: AsyncSession,
    *,
    device_id: str = "test-device-1",
    apns_token: str = "fake-token-abc",
    data_source: str = "NJT",
    line_id: str | None = None,
    from_station: str | None = None,
    to_station: str | None = None,
) -> tuple[DeviceToken, RouteAlertSubscription]:
    """Create a DeviceToken + RouteAlertSubscription pair."""
    device = DeviceToken(device_id=device_id, apns_token=apns_token)
    db.add(device)

    sub = RouteAlertSubscription(
        device_id=device_id,
        data_source=data_source,
        line_id=line_id,
        from_station_code=from_station,
        to_station_code=to_station,
    )
    db.add(sub)
    return device, sub


@pytest.mark.asyncio
class TestAlertEvaluator:
    """Tests for evaluate_route_alerts()."""

    async def test_no_subscriptions_sends_no_alerts(self, db_session: AsyncSession):
        """With zero subscriptions, zero alerts are sent."""
        apns = _make_apns()
        count = await evaluate_route_alerts(db_session, apns)
        assert count == 0
        apns.send_alert_notification.assert_not_called()

    async def test_cancellation_triggers_alert(self, db_session: AsyncSession):
        """A single cancellation should trigger an alert."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            from_station="NY",
            to_station="TR",
        )
        _make_journey(
            db_session,
            train_id="1001",
            origin="NY",
            terminal="TR",
            is_cancelled=True,
            minutes_ago=20,
        )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 1
        apns.send_alert_notification.assert_called_once()

        call_args = apns.send_alert_notification.call_args
        assert (
            "Cancellation" in call_args.args[1]
            or "cancellation" in call_args.args[1].lower()
        )

    async def test_delay_above_threshold_triggers_alert(self, db_session: AsyncSession):
        """When >=50% of trains are delayed 15+ min, an alert fires."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            from_station="NY",
            to_station="TR",
        )
        # 2 of 2 delayed = 100% > 50%
        _make_journey(
            db_session,
            train_id="2001",
            delay_minutes=DELAY_THRESHOLD_MINUTES,
            minutes_ago=30,
        )
        _make_journey(
            db_session,
            train_id="2002",
            delay_minutes=DELAY_THRESHOLD_MINUTES + 5,
            minutes_ago=15,
        )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 1
        apns.send_alert_notification.assert_called_once()

        call_args = apns.send_alert_notification.call_args
        assert "Delay" in call_args.args[1] or "delay" in call_args.args[1].lower()

    async def test_delay_below_threshold_no_alert(self, db_session: AsyncSession):
        """When <50% of trains are delayed, no alert fires."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            from_station="NY",
            to_station="TR",
        )
        # 1 of 3 delayed = 33% < 50%
        _make_journey(
            db_session,
            train_id="3001",
            delay_minutes=DELAY_THRESHOLD_MINUTES + 5,
            minutes_ago=40,
        )
        _make_journey(db_session, train_id="3002", delay_minutes=0, minutes_ago=30)
        _make_journey(db_session, train_id="3003", delay_minutes=0, minutes_ago=20)
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 0
        apns.send_alert_notification.assert_not_called()

    async def test_cooldown_prevents_duplicate_alert(self, db_session: AsyncSession):
        """If last_alerted_at is within 30 min, no alert fires."""
        apns = _make_apns()
        device, sub = _make_device_and_sub(
            db_session,
            data_source="NJT",
            from_station="NY",
            to_station="TR",
        )
        # Mark as recently alerted
        sub.last_alerted_at = now_et() - timedelta(minutes=COOLDOWN_MINUTES - 5)

        _make_journey(
            db_session,
            train_id="4001",
            is_cancelled=True,
            minutes_ago=20,
        )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 0
        apns.send_alert_notification.assert_not_called()

    async def test_hash_dedup_prevents_repeat(self, db_session: AsyncSession):
        """Same alert hash should not fire again."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            from_station="NY",
            to_station="TR",
        )
        _make_journey(
            db_session,
            train_id="5001",
            is_cancelled=True,
            minutes_ago=20,
        )
        await db_session.flush()

        # First call should send
        count1 = await evaluate_route_alerts(db_session, apns)
        assert count1 == 1

        # Reset cooldown but keep hash
        result = await db_session.execute(select(RouteAlertSubscription))
        sub = result.scalar_one()
        sub.last_alerted_at = now_et() - timedelta(minutes=COOLDOWN_MINUTES + 1)
        await db_session.flush()

        apns.send_alert_notification.reset_mock()

        # Second call should be deduped
        count2 = await evaluate_route_alerts(db_session, apns)
        assert count2 == 0
        apns.send_alert_notification.assert_not_called()

    async def test_line_mode_filters_by_line_code(self, db_session: AsyncSession):
        """Line-mode subscription should only match journeys with matching line_code."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            line_id="njt-nec",  # NEC line
        )
        # NEC journey (should match)
        _make_journey(
            db_session,
            train_id="6001",
            line_code="NE",
            is_cancelled=True,
            minutes_ago=20,
        )
        # Different line (should NOT match)
        _make_journey(
            db_session,
            train_id="6002",
            line_code="RV",
            is_cancelled=True,
            minutes_ago=20,
        )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 1

        call_args = apns.send_alert_notification.call_args
        body = call_args.args[2]
        # Should mention 1 cancelled, not 2
        assert "1 train cancelled" in body

    async def test_station_pair_matches_origin_destination(
        self, db_session: AsyncSession
    ):
        """Station-pair subscription should match origin/destination."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            from_station="NY",
            to_station="TR",
        )
        # Matching journey
        _make_journey(
            db_session,
            train_id="7001",
            origin="NY",
            terminal="TR",
            is_cancelled=True,
            minutes_ago=20,
        )
        # Different route (should NOT match)
        _make_journey(
            db_session,
            train_id="7002",
            origin="NP",
            terminal="AB",
            is_cancelled=True,
            minutes_ago=20,
        )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 1

    async def test_apns_failure_does_not_update_state(self, db_session: AsyncSession):
        """If APNS send fails, last_alerted_at should NOT be updated."""
        apns = _make_apns(send_returns=False)
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            from_station="NY",
            to_station="TR",
        )
        _make_journey(
            db_session,
            train_id="8001",
            is_cancelled=True,
            minutes_ago=20,
        )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 0

        result = await db_session.execute(select(RouteAlertSubscription))
        sub = result.scalar_one()
        assert sub.last_alerted_at is None
