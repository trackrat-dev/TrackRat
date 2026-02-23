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
    MIN_BASELINE_DAYS,
    REALTIME_SOURCES,
    _build_alert_message,
    _compute_alert_hash,
    _query_baseline_train_count,
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

    async def test_custom_data_includes_route_alert_metadata(
        self, db_session: AsyncSession
    ):
        """Alert notification should include route_alert custom data with subscription metadata."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            from_station="NY",
            to_station="TR",
        )
        _make_journey(
            db_session,
            train_id="9001",
            origin="NY",
            terminal="TR",
            is_cancelled=True,
            minutes_ago=20,
        )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 1

        call_kwargs = apns.send_alert_notification.call_args.kwargs
        assert "custom_data" in call_kwargs
        route_alert = call_kwargs["custom_data"]["route_alert"]
        assert route_alert["data_source"] == "NJT"
        assert route_alert["from_station_code"] == "NY"
        assert route_alert["to_station_code"] == "TR"
        assert route_alert["line_id"] is None

    async def test_custom_data_includes_line_id_for_line_mode(
        self, db_session: AsyncSession
    ):
        """Line-mode subscription should include line_id in custom data."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            line_id="njt-nec",
        )
        _make_journey(
            db_session,
            train_id="9002",
            line_code="NE",
            is_cancelled=True,
            minutes_ago=20,
        )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 1

        call_kwargs = apns.send_alert_notification.call_args.kwargs
        route_alert = call_kwargs["custom_data"]["route_alert"]
        assert route_alert["data_source"] == "NJT"
        assert route_alert["line_id"] == "njt-nec"
        assert route_alert["from_station_code"] is None
        assert route_alert["to_station_code"] is None

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

    async def test_reduced_service_triggers_alert_for_realtime_source(
        self, db_session: AsyncSession
    ):
        """When train count drops below 50% of baseline, a reduced service alert fires."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="SUBWAY",
            from_station="A01",
            to_station="B01",
        )

        now = now_et()
        # Create baseline: 10 trains per day for the last 5 comparable days
        for days_ago in range(1, 6):
            past_date = now - timedelta(days=days_ago)
            # Skip if weekday/weekend doesn't match
            if past_date.weekday() >= 5 != (now.weekday() >= 5):
                # Add extra days to ensure we get enough matching days
                continue
            for i in range(10):
                journey = TrainJourney(
                    train_id=f"baseline-{days_ago}-{i}",
                    journey_date=past_date.date(),
                    line_code="A",
                    line_name="A Train",
                    destination="Far Rockaway",
                    origin_station_code="A01",
                    terminal_station_code="B01",
                    data_source="SUBWAY",
                    scheduled_departure=past_date.replace(hour=now.hour, minute=i * 5),
                    actual_departure=past_date.replace(hour=now.hour, minute=i * 5),
                    is_cancelled=False,
                    has_complete_journey=True,
                )
                db_session.add(journey)

        # Create baseline for enough weekday/weekend matching days
        # Ensure we have at least MIN_BASELINE_DAYS matching days
        for extra in range(7, 35, 7):
            past_date = now - timedelta(days=extra)
            if (past_date.weekday() >= 5) == (now.weekday() >= 5):
                for i in range(10):
                    journey = TrainJourney(
                        train_id=f"baseline-extra-{extra}-{i}",
                        journey_date=past_date.date(),
                        line_code="A",
                        line_name="A Train",
                        destination="Far Rockaway",
                        origin_station_code="A01",
                        terminal_station_code="B01",
                        data_source="SUBWAY",
                        scheduled_departure=past_date.replace(hour=now.hour, minute=i * 5),
                        actual_departure=past_date.replace(hour=now.hour, minute=i * 5),
                        is_cancelled=False,
                        has_complete_journey=True,
                    )
                    db_session.add(journey)

        # Current hour: only 3 trains running (30% of baseline ~10)
        for i in range(3):
            _make_journey(
                db_session,
                train_id=f"current-{i}",
                data_source="SUBWAY",
                line_code="A",
                origin="A01",
                terminal="B01",
                delay_minutes=0,
                minutes_ago=10 + i * 10,
            )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 1
        apns.send_alert_notification.assert_called_once()

        call_args = apns.send_alert_notification.call_args
        title = call_args.args[1]
        body = call_args.args[2]
        assert "Reduced service" in title or "reduced service" in title.lower()
        assert "trains running" in body.lower()
        print(f"  Alert title: {title}")
        print(f"  Alert body: {body}")

    async def test_no_reduced_service_alert_for_schedule_only_source(
        self, db_session: AsyncSession
    ):
        """PATCO (schedule-only) should not get reduced service alerts."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="PATCO",
            from_station="PA1",
            to_station="PA2",
        )
        # Only 1 train running, no baseline data
        _make_journey(
            db_session,
            train_id="patco-1",
            data_source="PATCO",
            line_code="PATCO",
            origin="PA1",
            terminal="PA2",
            delay_minutes=0,
            minutes_ago=20,
        )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 0
        apns.send_alert_notification.assert_not_called()

    async def test_no_reduced_service_when_frequency_above_threshold(
        self, db_session: AsyncSession
    ):
        """When train count is above 50% of baseline, no reduced service alert fires."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="PATH",
            from_station="WTC",
            to_station="NWK",
        )

        now = now_et()
        # Create baseline: 6 trains per comparable day
        for extra in range(7, 35, 7):
            past_date = now - timedelta(days=extra)
            if (past_date.weekday() >= 5) == (now.weekday() >= 5):
                for i in range(6):
                    journey = TrainJourney(
                        train_id=f"path-base-{extra}-{i}",
                        journey_date=past_date.date(),
                        line_code="NWK",
                        line_name="Newark-WTC",
                        destination="Newark",
                        origin_station_code="WTC",
                        terminal_station_code="NWK",
                        data_source="PATH",
                        scheduled_departure=past_date.replace(hour=now.hour, minute=i * 10),
                        actual_departure=past_date.replace(hour=now.hour, minute=i * 10),
                        is_cancelled=False,
                        has_complete_journey=True,
                    )
                    db_session.add(journey)

        # Current hour: 4 trains running (67% of baseline ~6) — above 50% threshold
        for i in range(4):
            _make_journey(
                db_session,
                train_id=f"path-now-{i}",
                data_source="PATH",
                line_code="NWK",
                origin="WTC",
                terminal="NWK",
                delay_minutes=0,
                minutes_ago=10 + i * 10,
            )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 0
        apns.send_alert_notification.assert_not_called()


class TestAlertHelpers:
    """Tests for alert evaluator helper functions."""

    def test_build_alert_message_reduced_service(self):
        """reduced_service alert message includes train count and frequency info."""
        sub = RouteAlertSubscription(
            device_id="test",
            data_source="SUBWAY",
            from_station_code="A01",
            to_station_code="B01",
        )
        title, body = _build_alert_message(
            sub, "reduced_service", 0, 0, 5, frequency_factor=0.3
        )
        assert "Reduced service" in title
        assert "SUBWAY" in title
        assert "trains running" in body
        assert "30%" in body
        print(f"  Title: {title}")
        print(f"  Body: {body}")

    def test_build_alert_message_cancellation(self):
        """Cancellation alerts still work correctly with frequency_factor."""
        sub = RouteAlertSubscription(
            device_id="test",
            data_source="NJT",
            line_id="njt-nec",
        )
        title, body = _build_alert_message(
            sub, "cancellation", 2, 0, 10, frequency_factor=None
        )
        assert "Cancellation" in title
        assert "2 trains cancelled" in body
        print(f"  Title: {title}")
        print(f"  Body: {body}")

    def test_compute_alert_hash_includes_frequency(self):
        """Hash should differ based on frequency_factor."""
        hash1 = _compute_alert_hash("reduced_service", 0, 0, 5, frequency_factor=0.3)
        hash2 = _compute_alert_hash("reduced_service", 0, 0, 5, frequency_factor=0.4)
        hash3 = _compute_alert_hash("reduced_service", 0, 0, 5, frequency_factor=None)
        assert hash1 != hash2, "Different frequency factors should produce different hashes"
        assert hash1 != hash3, "None vs 0.3 should produce different hashes"

    def test_compute_alert_hash_rounds_frequency(self):
        """Tiny frequency differences should produce the same hash (rounded to 1 decimal)."""
        hash1 = _compute_alert_hash("reduced_service", 0, 0, 5, frequency_factor=0.31)
        hash2 = _compute_alert_hash("reduced_service", 0, 0, 5, frequency_factor=0.34)
        assert hash1 == hash2, "0.31 and 0.34 both round to 0.3"
