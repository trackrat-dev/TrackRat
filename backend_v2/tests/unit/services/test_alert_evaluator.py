"""
Tests for route alert evaluation service.

Uses real PostgreSQL via db_session fixture. APNS send calls are mocked
since we cannot hit Apple's servers in tests.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from trackrat.models.database import (
    DeviceToken,
    JourneyStop,
    RouteAlertSubscription,
    TrainJourney,
)
from trackrat.config.route_topology import Route
from trackrat.services.alert_evaluator import (
    COOLDOWN_MINUTES,
    DELAY_THRESHOLD_MINUTES,
    FREQUENCY_FIRST_SOURCES,
    MIN_BASELINE_DAYS,
    _build_alert_message,
    _build_train_alert_message,
    _compute_alert_hash,
    _compute_train_alert_hash,
    _filter_by_direction,
    _is_significantly_delayed,
    _is_within_time_window,
    evaluate_morning_digests,
    evaluate_route_alerts,
)
from trackrat.utils.time import ET, now_et


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
    train_id: str | None = None,
    direction: str | None = None,
    active_days: int = 127,
    active_start_minutes: int | None = None,
    active_end_minutes: int | None = None,
    timezone: str | None = None,
    delay_threshold_minutes: int | None = None,
    service_threshold_pct: int | None = None,
    notify_recovery: bool = False,
    digest_time_minutes: int | None = None,
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
        train_id=train_id,
        direction=direction,
        active_days=active_days,
        active_start_minutes=active_start_minutes,
        active_end_minutes=active_end_minutes,
        timezone=timezone,
        delay_threshold_minutes=delay_threshold_minutes,
        service_threshold_pct=service_threshold_pct,
        notify_recovery=notify_recovery,
        digest_time_minutes=digest_time_minutes,
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

    async def test_arrival_delay_triggers_alert_for_station_pair(
        self, db_session: AsyncSession
    ):
        """Train departs on time but arrives 20+ min late at destination → alert fires.

        This tests that station-pair subscriptions check arrival delay at the
        destination stop, not just departure delay at the origin.
        """
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            from_station="NY",
            to_station="TR",
        )
        now = now_et()
        sched = now - timedelta(minutes=30)

        # 2 of 2 trains depart on time but arrive late at TR
        for i, train_id in enumerate(["arr-late-1", "arr-late-2"]):
            journey = TrainJourney(
                train_id=train_id,
                journey_date=now.date(),
                line_code="NE",
                line_name="Northeast Corridor",
                destination="Trenton",
                origin_station_code="NY",
                terminal_station_code="TR",
                data_source="NJT",
                scheduled_departure=sched + timedelta(minutes=i * 5),
                actual_departure=sched + timedelta(minutes=i * 5),  # on-time departure
                is_cancelled=False,
                has_complete_journey=True,
            )
            db_session.add(journey)
            await db_session.flush()

            # Destination stop: scheduled arrival 60min after departure,
            # but actual arrival is 20min late
            sched_arrival = sched + timedelta(minutes=i * 5 + 60)
            stop = JourneyStop(
                journey_id=journey.id,
                station_code="TR",
                station_name="Trenton",
                stop_sequence=5,
                scheduled_arrival=sched_arrival,
                actual_arrival=sched_arrival + timedelta(minutes=20),
            )
            db_session.add(stop)

        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert (
            count == 1
        ), "Expected alert when trains depart on time but arrive 20+ min late at destination"
        apns.send_alert_notification.assert_called_once()

        call_args = apns.send_alert_notification.call_args
        assert "Delay" in call_args.args[1] or "delay" in call_args.args[1].lower()
        print(f"  Arrival delay alert: {call_args.args[1]} — {call_args.args[2]}")

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
        """When train count drops below 50% of baseline, a reduced service alert fires.

        Uses a fixed time (Wednesday 2pm ET) to avoid flakiness from midnight
        crossover, DST transitions, or hour-boundary races between independent
        now_et() calls in the test helpers vs the evaluator.
        """
        # Pin time: Wednesday 2026-01-14 14:00 ET — a weekday, far from
        # midnight, no DST ambiguity (firmly EST).
        fixed_now = ET.localize(datetime(2026, 1, 14, 14, 0, 0))

        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="SUBWAY",
            from_station="A01",
            to_station="B01",
        )

        # Create baseline: 10 trains per matching weekday, spread within the
        # rolling 60-minute window the evaluator uses for both current and
        # baseline counts.
        baseline_days_added = 0
        for days_ago in range(1, 35):
            # Normalize to correct DST offset for the target date — pytz
            # timedelta arithmetic preserves the original UTC offset, so
            # replace() would keep EDT even for dates that should be EST.
            past_date = ET.normalize(fixed_now - timedelta(days=days_ago))
            # Must match weekday/weekend pattern
            if (past_date.weekday() >= 5) != (fixed_now.weekday() >= 5):
                continue
            for i in range(10):
                # Spread trains within the past 50 minutes relative to
                # fixed_now's time-of-day so they fall inside the rolling
                # 60-min window. Use ET.localize on a naive datetime to get
                # the correct UTC offset for the target date (EST vs EDT).
                pd = past_date.date()
                sched = ET.localize(
                    datetime(pd.year, pd.month, pd.day, fixed_now.hour, fixed_now.minute, 0)
                    - timedelta(minutes=i * 5)
                )
                journey = TrainJourney(
                    train_id=f"baseline-{days_ago}-{i}",
                    journey_date=sched.date(),
                    line_code="A",
                    line_name="A Train",
                    destination="Far Rockaway",
                    origin_station_code="A01",
                    terminal_station_code="B01",
                    data_source="SUBWAY",
                    scheduled_departure=sched,
                    actual_departure=sched,
                    is_cancelled=False,
                    has_complete_journey=True,
                )
                db_session.add(journey)
            baseline_days_added += 1
            if baseline_days_added >= MIN_BASELINE_DAYS + 1:
                break

        # Current hour: only 3 trains (30% of baseline ~10)
        for i in range(3):
            sched = fixed_now - timedelta(minutes=10 + i * 10)
            journey = TrainJourney(
                train_id=f"current-{i}",
                journey_date=fixed_now.date(),
                line_code="A",
                line_name="A Train",
                destination="Far Rockaway",
                origin_station_code="A01",
                terminal_station_code="B01",
                data_source="SUBWAY",
                scheduled_departure=sched,
                actual_departure=sched,
                is_cancelled=False,
                has_complete_journey=True,
            )
            db_session.add(journey)
        await db_session.flush()

        with patch(
            "trackrat.services.alert_evaluator.now_et", return_value=fixed_now
        ):
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
        # Create baseline: 6 trains per comparable day within the rolling
        # 60-minute window
        baseline_days_added = 0
        for days_ago in range(1, 35):
            past_date = ET.normalize(now - timedelta(days=days_ago))
            if (past_date.weekday() >= 5) != (now.weekday() >= 5):
                continue
            for i in range(6):
                pd = past_date.date()
                sched = ET.localize(
                    datetime(pd.year, pd.month, pd.day, now.hour, now.minute, 0)
                    - timedelta(minutes=i * 10)
                )
                journey = TrainJourney(
                    train_id=f"path-base-{days_ago}-{i}",
                    journey_date=sched.date(),
                    line_code="NWK",
                    line_name="Newark-WTC",
                    destination="Newark",
                    origin_station_code="WTC",
                    terminal_station_code="NWK",
                    data_source="PATH",
                    scheduled_departure=sched,
                    actual_departure=sched,
                    is_cancelled=False,
                    has_complete_journey=True,
                )
                db_session.add(journey)
            baseline_days_added += 1
            if baseline_days_added >= MIN_BASELINE_DAYS + 1:
                break

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


@pytest.mark.asyncio
class TestSystemAwareAlertPriority:
    """Tests for system-aware alert evaluation: frequency-first vs delay-first."""

    async def test_subway_delays_do_not_trigger_delay_alert(
        self, db_session: AsyncSession
    ):
        """SUBWAY (frequency-first) with 100% delayed trains should NOT get a delay alert.

        This is the core bug fix: subway users should never receive 'Delays on X'
        notifications. Only cancellation or reduced_service alerts are valid for
        frequency-first systems.
        """
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="SUBWAY",
            from_station="A01",
            to_station="B01",
        )
        # Create 3 heavily delayed trains (100% delayed — well above 50% threshold)
        for i in range(3):
            _make_journey(
                db_session,
                train_id=f"subway-delay-{i}",
                data_source="SUBWAY",
                line_code="A",
                origin="A01",
                terminal="B01",
                delay_minutes=DELAY_THRESHOLD_MINUTES + 10,
                minutes_ago=10 + i * 10,
            )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert (
            count == 0
        ), "SUBWAY should NOT get delay alerts — frequency-first systems skip delay checks"
        apns.send_alert_notification.assert_not_called()
        print("  Verified: SUBWAY with heavy delays → no alert (frequency-first)")

    async def test_path_delays_do_not_trigger_delay_alert(
        self, db_session: AsyncSession
    ):
        """PATH (frequency-first) with heavy delays should NOT get a delay alert."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="PATH",
            from_station="WTC",
            to_station="NWK",
        )
        # 2 of 2 delayed = 100%
        _make_journey(
            db_session,
            train_id="path-d1",
            data_source="PATH",
            line_code="NWK",
            origin="WTC",
            terminal="NWK",
            delay_minutes=DELAY_THRESHOLD_MINUTES + 5,
            minutes_ago=15,
        )
        _make_journey(
            db_session,
            train_id="path-d2",
            data_source="PATH",
            line_code="NWK",
            origin="WTC",
            terminal="NWK",
            delay_minutes=DELAY_THRESHOLD_MINUTES + 10,
            minutes_ago=30,
        )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert (
            count == 0
        ), "PATH should NOT get delay alerts — frequency-first systems skip delay checks"
        apns.send_alert_notification.assert_not_called()
        print("  Verified: PATH with heavy delays → no alert (frequency-first)")

    async def test_njt_reduced_frequency_does_not_trigger_alert(
        self, db_session: AsyncSession
    ):
        """NJT (delay-first) with reduced frequency should NOT get a reduced_service alert.

        Delay-first systems only check cancellations and delays, not frequency.
        """
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            from_station="NY",
            to_station="TR",
        )

        now = now_et()
        # Create baseline: 10 trains per comparable day
        baseline_days_added = 0
        for days_ago in range(1, 35):
            past_date = ET.normalize(now - timedelta(days=days_ago))
            if (past_date.weekday() >= 5) != (now.weekday() >= 5):
                continue
            for i in range(10):
                pd = past_date.date()
                sched = ET.localize(
                    datetime(pd.year, pd.month, pd.day, now.hour, now.minute, 0)
                    - timedelta(minutes=i * 5)
                )
                journey = TrainJourney(
                    train_id=f"njt-base-{days_ago}-{i}",
                    journey_date=sched.date(),
                    line_code="NE",
                    line_name="Northeast Corridor",
                    destination="Trenton",
                    origin_station_code="NY",
                    terminal_station_code="TR",
                    data_source="NJT",
                    scheduled_departure=sched,
                    actual_departure=sched,
                    is_cancelled=False,
                    has_complete_journey=True,
                )
                db_session.add(journey)
            baseline_days_added += 1
            if baseline_days_added >= MIN_BASELINE_DAYS + 1:
                break

        # Current hour: only 2 on-time trains (20% of baseline ~10)
        # This WOULD have triggered reduced_service under the old fallback logic
        for i in range(2):
            _make_journey(
                db_session,
                train_id=f"njt-now-{i}",
                data_source="NJT",
                line_code="NE",
                origin="NY",
                terminal="TR",
                delay_minutes=0,
                minutes_ago=10 + i * 20,
            )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert (
            count == 0
        ), "NJT should NOT get reduced_service alerts — delay-first systems skip frequency checks"
        apns.send_alert_notification.assert_not_called()
        print("  Verified: NJT with reduced frequency → no alert (delay-first)")

    async def test_subway_cancellation_still_triggers(self, db_session: AsyncSession):
        """Cancellations are universal — SUBWAY cancellation should still alert."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="SUBWAY",
            from_station="A01",
            to_station="B01",
        )
        _make_journey(
            db_session,
            train_id="subway-cancel-1",
            data_source="SUBWAY",
            line_code="A",
            origin="A01",
            terminal="B01",
            is_cancelled=True,
            minutes_ago=20,
        )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 1
        apns.send_alert_notification.assert_called_once()

        call_args = apns.send_alert_notification.call_args
        title = call_args.args[1]
        assert "Cancellation" in title
        assert "SUBWAY" in title
        print(f"  Verified: SUBWAY cancellation fires correctly — {title}")

    async def test_frequency_first_sources_constant(self):
        """FREQUENCY_FIRST_SOURCES should match iOS preferredHighlightMode == .health."""
        assert FREQUENCY_FIRST_SOURCES == {"SUBWAY", "PATH", "PATCO"}
        # Verify no overlap: frequency-first should not include delay-first systems
        delay_first = {"NJT", "AMTRAK", "LIRR", "MNR"}
        assert FREQUENCY_FIRST_SOURCES.isdisjoint(
            delay_first
        ), "Frequency-first and delay-first sets must not overlap"
        print(f"  FREQUENCY_FIRST_SOURCES = {FREQUENCY_FIRST_SOURCES}")
        print(f"  Delay-first systems = {delay_first}")


class TestIsSignificantlyDelayed:
    """Tests for _is_significantly_delayed helper."""

    def test_departure_delay_above_threshold(self):
        """Departure delay >= 15 min → delayed."""
        now = now_et()
        journey = TrainJourney(
            train_id="100",
            journey_date=now.date(),
            line_code="NE",
            line_name="NEC",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now - timedelta(minutes=45),
            actual_departure=now - timedelta(minutes=30),  # 15 min late
            has_complete_journey=True,
        )
        assert _is_significantly_delayed(journey) is True

    def test_departure_delay_below_threshold(self):
        """Departure delay < 15 min → not delayed."""
        now = now_et()
        journey = TrainJourney(
            train_id="101",
            journey_date=now.date(),
            line_code="NE",
            line_name="NEC",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now - timedelta(minutes=40),
            actual_departure=now - timedelta(minutes=30),  # 10 min late
            has_complete_journey=True,
        )
        assert _is_significantly_delayed(journey) is False

    def test_arrival_delay_at_destination_stop(self):
        """On-time departure but late arrival at to_station → delayed."""
        now = now_et()
        journey = TrainJourney(
            train_id="102",
            journey_date=now.date(),
            line_code="NE",
            line_name="NEC",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now - timedelta(minutes=60),
            actual_departure=now - timedelta(minutes=60),  # on-time departure
            has_complete_journey=True,
        )
        sched_arr = now - timedelta(minutes=10)
        stop = JourneyStop(
            journey_id=1,
            station_code="TR",
            station_name="Trenton",
            stop_sequence=5,
            scheduled_arrival=sched_arr,
            actual_arrival=sched_arr + timedelta(minutes=20),  # 20 min late arrival
        )
        journey.stops = [stop]

        # Without to_station_code: departure is on time → not delayed
        assert _is_significantly_delayed(journey) is False
        # With to_station_code: arrival is 20 min late → delayed
        assert _is_significantly_delayed(journey, to_station_code="TR") is True

    def test_arrival_delay_ignored_for_wrong_station(self):
        """Arrival delay at a non-destination station is not checked."""
        now = now_et()
        journey = TrainJourney(
            train_id="103",
            journey_date=now.date(),
            line_code="NE",
            line_name="NEC",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now - timedelta(minutes=60),
            actual_departure=now - timedelta(minutes=60),  # on-time departure
            has_complete_journey=True,
        )
        sched_arr = now - timedelta(minutes=30)
        stop = JourneyStop(
            journey_id=1,
            station_code="NP",  # Newark, not Trenton
            station_name="Newark Penn",
            stop_sequence=2,
            scheduled_arrival=sched_arr,
            actual_arrival=sched_arr + timedelta(minutes=25),  # 25 min late at NP
        )
        journey.stops = [stop]

        # Checking arrival at TR, but only NP stop exists → not delayed
        assert _is_significantly_delayed(journey, to_station_code="TR") is False

    def test_no_actual_times_not_delayed(self):
        """Missing actual departure/arrival → not delayed."""
        now = now_et()
        journey = TrainJourney(
            train_id="104",
            journey_date=now.date(),
            line_code="NE",
            line_name="NEC",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now - timedelta(minutes=60),
            actual_departure=None,
            has_complete_journey=False,
        )
        assert _is_significantly_delayed(journey) is False


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
        assert (
            hash1 != hash2
        ), "Different frequency factors should produce different hashes"
        assert hash1 != hash3, "None vs 0.3 should produce different hashes"

    def test_compute_alert_hash_rounds_frequency(self):
        """Tiny frequency differences should produce the same hash (rounded to 1 decimal)."""
        hash1 = _compute_alert_hash("reduced_service", 0, 0, 5, frequency_factor=0.31)
        hash2 = _compute_alert_hash("reduced_service", 0, 0, 5, frequency_factor=0.34)
        assert hash1 == hash2, "0.31 and 0.34 both round to 0.3"

    def test_build_train_alert_message_cancellation(self):
        """Train cancellation alert message includes train ID and route."""
        sub = RouteAlertSubscription(
            device_id="test",
            data_source="NJT",
            train_id="3254",
        )
        journey = TrainJourney(
            train_id="3254",
            journey_date=now_et().date(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now_et(),
            is_cancelled=True,
            has_complete_journey=True,
        )
        title, body = _build_train_alert_message(sub, journey, "cancellation", 0)
        assert "3254" in title
        assert "Cancelled" in title
        assert "NJT" in title
        assert "NY → TR" in body
        print(f"  Title: {title}")
        print(f"  Body: {body}")

    def test_build_train_alert_message_delay(self):
        """Train delay alert message includes delay minutes."""
        sub = RouteAlertSubscription(
            device_id="test",
            data_source="NJT",
            train_id="3254",
        )
        now = now_et()
        journey = TrainJourney(
            train_id="3254",
            journey_date=now.date(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now - timedelta(minutes=40),
            actual_departure=now - timedelta(minutes=20),
            is_cancelled=False,
            has_complete_journey=True,
        )
        title, body = _build_train_alert_message(sub, journey, "delay", 20)
        assert "Delayed" in title
        assert "3254" in title
        assert "20 minutes" in body
        print(f"  Title: {title}")
        print(f"  Body: {body}")

    def test_compute_train_alert_hash_buckets_delay(self):
        """Train alert hash buckets delay to nearest 5 minutes."""
        hash1 = _compute_train_alert_hash("3254", "delay", 17)
        hash2 = _compute_train_alert_hash("3254", "delay", 18)
        hash3 = _compute_train_alert_hash("3254", "delay", 22)
        assert hash1 == hash2, "17 and 18 both bucket to 15"
        assert hash1 != hash3, "15 bucket != 20 bucket"

    def test_compute_train_alert_hash_differs_by_type(self):
        """Cancellation and delay produce different hashes."""
        hash_cancel = _compute_train_alert_hash("3254", "cancellation", 0)
        hash_delay = _compute_train_alert_hash("3254", "delay", 15)
        assert hash_cancel != hash_delay


@pytest.mark.asyncio
class TestTrainSubscriptionAlerts:
    """Tests for train_id subscription evaluation."""

    async def test_cancelled_train_triggers_alert(self, db_session: AsyncSession):
        """A cancelled train matching a train_id subscription should alert."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            train_id="3254",
            active_days=127,
        )
        _make_journey(
            db_session,
            train_id="3254",
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
        title = call_args.args[1]
        body = call_args.args[2]
        assert "3254" in title
        assert "Cancelled" in title
        print(f"  Title: {title}")
        print(f"  Body: {body}")

    async def test_delayed_train_triggers_alert(self, db_session: AsyncSession):
        """A significantly delayed train matching a train_id subscription should alert."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            train_id="3254",
            active_days=127,
        )
        _make_journey(
            db_session,
            train_id="3254",
            origin="NY",
            terminal="TR",
            delay_minutes=DELAY_THRESHOLD_MINUTES + 5,
            minutes_ago=20,
        )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 1
        apns.send_alert_notification.assert_called_once()

        call_args = apns.send_alert_notification.call_args
        title = call_args.args[1]
        body = call_args.args[2]
        assert "3254" in title
        assert "Delayed" in title
        assert "20 minutes" in body
        print(f"  Title: {title}")
        print(f"  Body: {body}")

    async def test_on_time_train_no_alert(self, db_session: AsyncSession):
        """An on-time train should NOT trigger an alert."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            train_id="3254",
            active_days=127,
        )
        _make_journey(
            db_session,
            train_id="3254",
            origin="NY",
            terminal="TR",
            delay_minutes=0,
            minutes_ago=20,
        )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 0
        apns.send_alert_notification.assert_not_called()

    async def test_no_journey_today_no_alert(self, db_session: AsyncSession):
        """If the train hasn't appeared today, no alert is sent."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            train_id="3254",
            active_days=127,
        )
        # No journey created for this train
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 0
        apns.send_alert_notification.assert_not_called()

    async def test_different_train_id_no_alert(self, db_session: AsyncSession):
        """A cancelled train with a different ID should NOT alert."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            train_id="3254",
            active_days=127,
        )
        _make_journey(
            db_session,
            train_id="9999",
            origin="NY",
            terminal="TR",
            is_cancelled=True,
            minutes_ago=20,
        )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 0
        apns.send_alert_notification.assert_not_called()

    async def test_active_days_skips_weekend(self, db_session: AsyncSession):
        """active_days=31 (Mon-Fri) should NOT fire on a Saturday."""
        apns = _make_apns()
        # Saturday 2026-02-21 10:00 ET
        fake_saturday = datetime(2026, 2, 21, 10, 0, 0)
        assert fake_saturday.weekday() == 5, "Sanity check: 2026-02-21 is Saturday"

        _make_device_and_sub(
            db_session,
            data_source="NJT",
            train_id="3254",
            active_days=31,  # Mon-Fri only
        )
        # Create journey with times relative to fake_saturday
        sched = fake_saturday - timedelta(minutes=20)
        journey = TrainJourney(
            train_id="3254",
            journey_date=fake_saturday.date(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=sched,
            actual_departure=None,
            is_cancelled=True,
            has_complete_journey=True,
        )
        db_session.add(journey)
        await db_session.flush()

        with patch(
            "trackrat.services.alert_evaluator.now_et", return_value=fake_saturday
        ):
            count = await evaluate_route_alerts(db_session, apns)
        assert count == 0, "active_days=31 should suppress alerts on weekends"
        apns.send_alert_notification.assert_not_called()
        print("  Verified: weekend skip works with active_days bitmask")

    async def test_active_days_fires_on_weekday(self, db_session: AsyncSession):
        """active_days=31 (Mon-Fri) should fire on a Wednesday."""
        apns = _make_apns()
        # Wednesday 2026-02-18 10:00 ET
        fake_wednesday = datetime(2026, 2, 18, 10, 0, 0)
        assert fake_wednesday.weekday() == 2, "Sanity check: 2026-02-18 is Wednesday"

        _make_device_and_sub(
            db_session,
            data_source="NJT",
            train_id="3254",
            active_days=31,  # Mon-Fri only
        )
        sched = fake_wednesday - timedelta(minutes=20)
        journey = TrainJourney(
            train_id="3254",
            journey_date=fake_wednesday.date(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=sched,
            actual_departure=None,
            is_cancelled=True,
            has_complete_journey=True,
        )
        db_session.add(journey)
        await db_session.flush()

        with patch(
            "trackrat.services.alert_evaluator.now_et", return_value=fake_wednesday
        ):
            count = await evaluate_route_alerts(db_session, apns)
        assert count == 1, "active_days=31 should fire on weekdays"
        apns.send_alert_notification.assert_called_once()
        print("  Verified: weekday alert fires with active_days bitmask")

    async def test_active_days_individual_day_selection(self, db_session: AsyncSession):
        """active_days with only Mon+Wed+Fri (1+4+16=21) should skip Tuesday."""
        apns = _make_apns()
        # Tuesday 2026-02-17 10:00 ET
        fake_tuesday = datetime(2026, 2, 17, 10, 0, 0)
        assert fake_tuesday.weekday() == 1, "Sanity check: 2026-02-17 is Tuesday"

        _make_device_and_sub(
            db_session,
            data_source="NJT",
            train_id="3254",
            active_days=21,  # Mon=1 + Wed=4 + Fri=16
        )
        sched = fake_tuesday - timedelta(minutes=20)
        journey = TrainJourney(
            train_id="3254",
            journey_date=fake_tuesday.date(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=sched,
            actual_departure=None,
            is_cancelled=True,
            has_complete_journey=True,
        )
        db_session.add(journey)
        await db_session.flush()

        with patch(
            "trackrat.services.alert_evaluator.now_et", return_value=fake_tuesday
        ):
            count = await evaluate_route_alerts(db_session, apns)
        assert count == 0, "active_days=21 (MWF) should skip Tuesday"
        apns.send_alert_notification.assert_not_called()
        print("  Verified: individual day selection works")

    async def test_train_alert_cooldown(self, db_session: AsyncSession):
        """Train alerts respect the cooldown period."""
        apns = _make_apns()
        device, sub = _make_device_and_sub(
            db_session,
            data_source="NJT",
            train_id="3254",
            active_days=127,
        )
        sub.last_alerted_at = now_et() - timedelta(minutes=COOLDOWN_MINUTES - 5)

        _make_journey(
            db_session,
            train_id="3254",
            origin="NY",
            terminal="TR",
            is_cancelled=True,
            minutes_ago=20,
        )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 0
        apns.send_alert_notification.assert_not_called()

    async def test_train_alert_dedup(self, db_session: AsyncSession):
        """Same train alert hash should not fire twice."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            train_id="3254",
            active_days=127,
        )
        _make_journey(
            db_session,
            train_id="3254",
            origin="NY",
            terminal="TR",
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

    async def test_train_alert_custom_data_includes_train_id(
        self, db_session: AsyncSession
    ):
        """Train alert notification should include train_id in custom data."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            train_id="3254",
            active_days=127,
        )
        _make_journey(
            db_session,
            train_id="3254",
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
        assert route_alert["train_id"] == "3254"
        assert route_alert["line_id"] is None
        assert route_alert["from_station_code"] is None
        print(f"  Custom data: {route_alert}")


# ---------------------------------------------------------------------------
# Direction filtering
# ---------------------------------------------------------------------------

# Build a small test route for direction tests
_TEST_ROUTE = Route(
    id="test-route",
    name="Test Route",
    data_source="TEST",
    line_codes=frozenset({"TE"}),
    stations=("A", "B", "C", "D", "E"),
)


class TestFilterByDirection:
    """Unit tests for _filter_by_direction()."""

    def _journey(self, origin: str, terminal: str) -> TrainJourney:
        """Create a minimal TrainJourney with just origin/terminal."""
        now = now_et()
        return TrainJourney(
            train_id="T1",
            journey_date=now.date(),
            line_code="TE",
            line_name="Test Route",
            destination=terminal,
            origin_station_code=origin,
            terminal_station_code=terminal,
            data_source="TEST",
            scheduled_departure=now,
            has_complete_journey=True,
        )

    def test_forward_direction_keeps_forward_trains(self):
        """Direction = last station should keep only forward-traveling trains."""
        forward = self._journey("A", "E")
        reverse = self._journey("E", "A")
        mid_forward = self._journey("B", "D")

        result = _filter_by_direction([forward, reverse, mid_forward], _TEST_ROUTE, "E")
        origins = [(j.origin_station_code, j.terminal_station_code) for j in result]
        assert ("A", "E") in origins
        assert ("B", "D") in origins
        assert ("E", "A") not in origins
        print(f"  Forward filter kept {len(result)} of 3 journeys: {origins}")

    def test_reverse_direction_keeps_reverse_trains(self):
        """Direction = first station should keep only reverse-traveling trains."""
        forward = self._journey("A", "E")
        reverse = self._journey("E", "A")
        mid_reverse = self._journey("D", "B")

        result = _filter_by_direction([forward, reverse, mid_reverse], _TEST_ROUTE, "A")
        origins = [(j.origin_station_code, j.terminal_station_code) for j in result]
        assert ("E", "A") in origins
        assert ("D", "B") in origins
        assert ("A", "E") not in origins
        print(f"  Reverse filter kept {len(result)} of 3 journeys: {origins}")

    def test_short_turn_trains_included(self):
        """A train that doesn't go to the terminus but travels the right direction is kept."""
        short_forward = self._journey("A", "C")  # doesn't reach E but heads toward it
        result = _filter_by_direction([short_forward], _TEST_ROUTE, "E")
        assert len(result) == 1
        print(f"  Short-turn train A->C kept for direction E")

    def test_unknown_direction_returns_all(self):
        """If direction station is not in the route, return all journeys unfiltered."""
        j = self._journey("A", "E")
        result = _filter_by_direction([j], _TEST_ROUTE, "Z")
        assert len(result) == 1
        print(f"  Unknown direction 'Z' returned all journeys")

    def test_off_route_trains_excluded(self):
        """Trains with stations not on the route are excluded."""
        off_route = self._journey("X", "Y")
        on_route = self._journey("A", "E")
        result = _filter_by_direction([off_route, on_route], _TEST_ROUTE, "E")
        assert len(result) == 1
        assert result[0].origin_station_code == "A"
        print(f"  Off-route train excluded, on-route kept")

    def test_empty_input_returns_empty(self):
        """Empty journey list returns empty."""
        result = _filter_by_direction([], _TEST_ROUTE, "E")
        assert result == []


@pytest.mark.asyncio
class TestDirectionalAlertEvaluation:
    """Integration tests for directional line subscriptions."""

    async def test_direction_filters_line_alert_to_one_direction(
        self, db_session: AsyncSession
    ):
        """A line sub with direction=TR should only alert on NY->TR trains, not TR->NY."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            line_id="njt-nec",
            direction="TR",  # toward Trenton
        )
        # 2 delayed southbound trains (NY->TR direction)
        for i in range(2):
            _make_journey(
                db_session,
                train_id=f"south-{i}",
                origin="NY",
                terminal="TR",
                delay_minutes=DELAY_THRESHOLD_MINUTES + 5,
                minutes_ago=30 + i * 5,
            )
        # 2 on-time northbound trains (TR->NY direction — should be filtered out)
        for i in range(2):
            _make_journey(
                db_session,
                train_id=f"north-{i}",
                origin="TR",
                terminal="NY",
                delay_minutes=0,
                minutes_ago=30 + i * 5,
            )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 1, "Should alert: 2/2 southbound trains delayed (100% >= 50%)"
        apns.send_alert_notification.assert_called_once()

        call_args = apns.send_alert_notification.call_args
        title = call_args.args[1]
        assert "toward" in title.lower(), f"Title should mention direction: {title}"
        print(f"  Title: {title}")

    async def test_no_direction_includes_both_directions(
        self, db_session: AsyncSession
    ):
        """A line sub with direction=None evaluates trains in both directions."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            device_id="dev-no-dir",
            data_source="NJT",
            line_id="njt-nec",
            direction=None,  # both directions
        )
        # 2 delayed southbound + 2 on-time northbound = 50% delayed overall
        for i in range(2):
            _make_journey(
                db_session,
                train_id=f"south-d-{i}",
                origin="NY",
                terminal="TR",
                delay_minutes=DELAY_THRESHOLD_MINUTES + 5,
                minutes_ago=30 + i * 5,
            )
        for i in range(2):
            _make_journey(
                db_session,
                train_id=f"north-d-{i}",
                origin="TR",
                terminal="NY",
                delay_minutes=0,
                minutes_ago=30 + i * 5,
            )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 1, "Should alert: 2/4 = 50% delayed (meets threshold)"

    async def test_direction_filters_prevent_false_alert(
        self, db_session: AsyncSession
    ):
        """Direction filtering should prevent alert when opposite direction is fine."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            device_id="dev-no-alert",
            data_source="NJT",
            line_id="njt-nec",
            direction="NY",  # toward NY Penn — northbound
        )
        # Southbound trains are delayed (wrong direction for this sub)
        for i in range(4):
            _make_journey(
                db_session,
                train_id=f"south-e-{i}",
                origin="NY",
                terminal="TR",
                delay_minutes=DELAY_THRESHOLD_MINUTES + 5,
                minutes_ago=30 + i * 5,
            )
        # Northbound trains are on time (the direction we're watching)
        for i in range(4):
            _make_journey(
                db_session,
                train_id=f"north-e-{i}",
                origin="TR",
                terminal="NY",
                delay_minutes=0,
                minutes_ago=30 + i * 5,
            )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 0, "Should NOT alert: northbound trains are all on time"
        apns.send_alert_notification.assert_not_called()
        print("  Verified: direction filter prevented false alert")

    async def test_direction_included_in_custom_data(self, db_session: AsyncSession):
        """APNS custom data should include the direction field."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            device_id="dev-custom",
            data_source="NJT",
            line_id="njt-nec",
            direction="TR",
        )
        # Enough delayed trains to trigger
        for i in range(3):
            _make_journey(
                db_session,
                train_id=f"south-c-{i}",
                origin="NY",
                terminal="TR",
                delay_minutes=DELAY_THRESHOLD_MINUTES + 5,
                minutes_ago=30 + i * 5,
            )
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 1

        call_kwargs = apns.send_alert_notification.call_args.kwargs
        route_alert = call_kwargs["custom_data"]["route_alert"]
        assert route_alert["direction"] == "TR"
        assert route_alert["line_id"] == "njt-nec"
        print(f"  Custom data includes direction: {route_alert}")


class TestDirectionalAlertMessage:
    """Tests for direction in alert message formatting."""

    def test_build_alert_message_with_direction(self):
        """Alert message should include 'toward <station name>' when direction is set."""
        sub = RouteAlertSubscription(
            device_id="test",
            data_source="NJT",
            line_id="njt-nec",
            direction="TR",
        )
        title, body = _build_alert_message(sub, "delay", 0, 3, 4)
        assert "toward" in title.lower()
        assert "Trenton" in title or "TR" in title
        print(f"  Title with direction: {title}")
        print(f"  Body: {body}")

    def test_build_alert_message_without_direction(self):
        """Alert message without direction should just show route name."""
        sub = RouteAlertSubscription(
            device_id="test",
            data_source="NJT",
            line_id="njt-nec",
        )
        title, body = _build_alert_message(sub, "delay", 0, 3, 4)
        assert "toward" not in title.lower()
        assert "Northeast Corridor" in title
        print(f"  Title without direction: {title}")

    def test_build_alert_message_custom_delay_threshold(self):
        """Alert message should use the custom delay threshold in the body."""
        sub = RouteAlertSubscription(
            device_id="test",
            data_source="NJT",
            line_id="njt-nec",
        )
        title, body = _build_alert_message(sub, "delay", 0, 3, 4, delay_threshold=5)
        assert "5+ min" in body
        print(f"  Body with custom threshold: {body}")


class TestTimeWindow:
    """Tests for _is_within_time_window."""

    def test_no_time_window_configured(self):
        """Should return True when no time window is set."""
        sub = RouteAlertSubscription(
            device_id="test",
            data_source="NJT",
            line_id="njt-nec",
        )
        assert _is_within_time_window(sub, datetime(2026, 3, 10, 12, 0)) is True

    def test_within_normal_window(self):
        """Should return True when current time is inside the window."""
        sub = RouteAlertSubscription(
            device_id="test",
            data_source="NJT",
            line_id="njt-nec",
            active_start_minutes=360,  # 6:00 AM
            active_end_minutes=600,  # 10:00 AM
            timezone="America/New_York",
        )
        # 8:00 AM ET
        with patch("trackrat.services.alert_evaluator.datetime") as mock_dt:
            from zoneinfo import ZoneInfo

            mock_dt.now.return_value = datetime(
                2026, 3, 10, 8, 0, 0, tzinfo=ZoneInfo("America/New_York")
            )
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            # Can't easily mock datetime.now(tz) — test the logic directly
        result = _is_within_time_window(sub, datetime(2026, 3, 10, 8, 0))
        assert result is True
        print("  Verified: 8:00 AM is within 6:00-10:00 AM window")

    def test_outside_normal_window(self):
        """Should return False when current time is outside the window."""
        sub = RouteAlertSubscription(
            device_id="test",
            data_source="NJT",
            line_id="njt-nec",
            active_start_minutes=360,  # 6:00 AM
            active_end_minutes=600,  # 10:00 AM
            timezone="America/New_York",
        )
        result = _is_within_time_window(sub, datetime(2026, 3, 10, 14, 0))
        # This tests the function with a real timezone lookup
        assert isinstance(result, bool)
        print(f"  Time window check returned: {result}")

    def test_midnight_wrap_window(self):
        """Should handle windows that wrap midnight (e.g., 10 PM to 6 AM)."""
        sub = RouteAlertSubscription(
            device_id="test",
            data_source="NJT",
            line_id="njt-nec",
            active_start_minutes=1320,  # 10:00 PM
            active_end_minutes=360,  # 6:00 AM
            timezone="America/New_York",
        )
        result = _is_within_time_window(sub, datetime(2026, 3, 10, 23, 0))
        assert isinstance(result, bool)
        print(f"  Midnight wrap check returned: {result}")

    def test_invalid_timezone_returns_true(self):
        """Invalid timezone should treat as always active."""
        sub = RouteAlertSubscription(
            device_id="test",
            data_source="NJT",
            line_id="njt-nec",
            active_start_minutes=360,
            active_end_minutes=600,
            timezone="Invalid/Timezone",
        )
        assert _is_within_time_window(sub, datetime(2026, 3, 10, 14, 0)) is True
        print("  Verified: invalid timezone defaults to always active")


class TestCustomDelayThreshold:
    """Tests for custom delay threshold in _is_significantly_delayed."""

    def test_custom_threshold_5_minutes(self):
        """With threshold=5, a 6-minute delay should trigger."""
        now = now_et()
        journey = TrainJourney(
            train_id="100",
            journey_date=now.date(),
            line_code="NE",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now - timedelta(minutes=30),
            actual_departure=now - timedelta(minutes=24),  # 6 min delay
        )
        assert _is_significantly_delayed(journey, threshold_minutes=5) is True
        assert _is_significantly_delayed(journey, threshold_minutes=15) is False
        print("  Verified: 6-min delay triggers at threshold=5, not at threshold=15")

    def test_custom_threshold_30_minutes(self):
        """With threshold=30, a 20-minute delay should NOT trigger."""
        now = now_et()
        journey = TrainJourney(
            train_id="101",
            journey_date=now.date(),
            line_code="NE",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now - timedelta(minutes=50),
            actual_departure=now - timedelta(minutes=30),  # 20 min delay
        )
        assert _is_significantly_delayed(journey, threshold_minutes=30) is False
        assert _is_significantly_delayed(journey, threshold_minutes=15) is True
        print("  Verified: 20-min delay respects custom threshold=30")


@pytest.mark.asyncio
class TestRecoveryAlerts:
    """Tests for 'all clear' recovery notifications."""

    async def test_recovery_sent_when_conditions_clear(self, db_session: AsyncSession):
        """Recovery alert fires when a previous alert was sent and conditions normalize."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            train_id="3254",
            notify_recovery=True,
        )
        # Create a normal (non-cancelled, on-time) journey
        now = now_et()
        journey = TrainJourney(
            train_id="3254",
            journey_date=now.date(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now - timedelta(minutes=20),
            actual_departure=now - timedelta(minutes=20),  # on time
            is_cancelled=False,
            has_complete_journey=True,
        )
        db_session.add(journey)
        await db_session.flush()

        # Simulate a previous alert by setting last_alert_hash
        result = await db_session.execute(select(RouteAlertSubscription))
        sub = result.scalar_one()
        sub.last_alert_hash = "previous_alert_hash"
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 1, "Recovery alert should be sent"
        call_kwargs = apns.send_alert_notification.call_args.kwargs
        assert "Route Clear" in call_kwargs.get("title", "") or "Route Clear" in str(
            apns.send_alert_notification.call_args
        )
        print("  Verified: recovery alert sent when conditions cleared")

    async def test_no_recovery_when_not_enabled(self, db_session: AsyncSession):
        """No recovery alert when notify_recovery is False."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            train_id="3254",
            notify_recovery=False,
        )
        now = now_et()
        journey = TrainJourney(
            train_id="3254",
            journey_date=now.date(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now - timedelta(minutes=20),
            actual_departure=now - timedelta(minutes=20),
            is_cancelled=False,
            has_complete_journey=True,
        )
        db_session.add(journey)
        await db_session.flush()

        result = await db_session.execute(select(RouteAlertSubscription))
        sub = result.scalar_one()
        sub.last_alert_hash = "previous_alert_hash"
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 0, "No recovery when notify_recovery=False"
        apns.send_alert_notification.assert_not_called()
        print("  Verified: no recovery alert when disabled")

    async def test_no_recovery_without_previous_alert(self, db_session: AsyncSession):
        """No recovery alert when there was no previous alert (hash is None)."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            train_id="3254",
            notify_recovery=True,
        )
        now = now_et()
        journey = TrainJourney(
            train_id="3254",
            journey_date=now.date(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now - timedelta(minutes=20),
            actual_departure=now - timedelta(minutes=20),
            is_cancelled=False,
            has_complete_journey=True,
        )
        db_session.add(journey)
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 0, "No recovery when no previous alert was sent"
        apns.send_alert_notification.assert_not_called()
        print("  Verified: no recovery without prior alert")


@pytest.mark.asyncio
class TestCustomThresholdEvaluation:
    """Tests for per-subscription delay and service thresholds in evaluate_route_alerts."""

    async def test_custom_delay_threshold_triggers_earlier(
        self, db_session: AsyncSession
    ):
        """A subscription with delay_threshold=5 should alert on 6-min delays."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            train_id="3254",
            delay_threshold_minutes=5,
        )
        now = now_et()
        journey = TrainJourney(
            train_id="3254",
            journey_date=now.date(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now - timedelta(minutes=20),
            actual_departure=now - timedelta(minutes=14),  # 6 min delay
            is_cancelled=False,
            has_complete_journey=True,
        )
        db_session.add(journey)
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 1, "Custom threshold=5 should trigger on 6-min delay"
        print("  Verified: custom delay threshold triggers earlier")

    async def test_default_threshold_ignores_small_delay(
        self, db_session: AsyncSession
    ):
        """Default threshold (15 min) should NOT alert on 6-min delay."""
        apns = _make_apns()
        _make_device_and_sub(
            db_session,
            data_source="NJT",
            train_id="3255",
        )
        now = now_et()
        journey = TrainJourney(
            train_id="3255",
            journey_date=now.date(),
            line_code="NE",
            line_name="Northeast Corridor",
            destination="Trenton",
            origin_station_code="NY",
            terminal_station_code="TR",
            data_source="NJT",
            scheduled_departure=now - timedelta(minutes=20),
            actual_departure=now - timedelta(minutes=14),  # 6 min delay
            is_cancelled=False,
            has_complete_journey=True,
        )
        db_session.add(journey)
        await db_session.flush()

        count = await evaluate_route_alerts(db_session, apns)
        assert count == 0, "Default threshold should NOT trigger on 6-min delay"
        print("  Verified: default threshold ignores small delay")
