"""
Route alert evaluation service.

Checks active subscriptions against recent departure data and sends
push notifications when significant delays or cancellations are detected.
"""

import hashlib
from datetime import timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from trackrat.config.route_topology import ALL_ROUTES
from trackrat.models.database import (
    DeviceToken,
    JourneyStop,
    RouteAlertSubscription,
    TrainJourney,
)
from trackrat.services.apns import SimpleAPNSService
from trackrat.utils.time import now_et

logger = get_logger(__name__)

# Thresholds
DELAY_THRESHOLD_MINUTES = 15
DELAY_PERCENT_THRESHOLD = 0.50
COOLDOWN_MINUTES = 30

# Build route-ID lookup once at import time
_ROUTES_BY_ID = {route.id: route for route in ALL_ROUTES}


async def evaluate_route_alerts(
    db: AsyncSession, apns_service: SimpleAPNSService
) -> int:
    """
    Evaluate all active route alert subscriptions and send notifications.

    Returns the number of alerts sent.
    """
    now = now_et()
    today = now.date()
    one_hour_ago = now - timedelta(hours=1)
    cooldown_cutoff = now - timedelta(minutes=COOLDOWN_MINUTES)

    # Load all devices with their subscriptions
    result = await db.execute(
        select(DeviceToken).options(selectinload(DeviceToken.subscriptions))
    )
    devices = result.scalars().all()

    alerts_sent = 0

    for device in devices:
        for sub in device.subscriptions:
            # Cooldown check
            if sub.last_alerted_at and sub.last_alerted_at >= cooldown_cutoff:
                continue

            # Build query for relevant journeys
            journeys = await _query_journeys_for_subscription(
                db, sub, today, one_hour_ago, now
            )

            if not journeys:
                continue

            # Count cancellations and delays
            cancelled_count = 0
            delayed_count = 0
            total_count = len(journeys)

            for journey in journeys:
                if journey.is_cancelled:
                    cancelled_count += 1
                elif _is_significantly_delayed(journey):
                    delayed_count += 1

            # Determine if alert is warranted
            should_alert = False
            alert_type = ""

            if cancelled_count > 0:
                should_alert = True
                alert_type = "cancellation"
            elif total_count > 0 and (delayed_count / total_count) >= DELAY_PERCENT_THRESHOLD:
                should_alert = True
                alert_type = "delay"

            if not should_alert:
                continue

            # Dedup via hash
            alert_hash = _compute_alert_hash(
                alert_type, cancelled_count, delayed_count, total_count
            )
            if sub.last_alert_hash == alert_hash:
                continue

            # Build notification
            title, body = _build_alert_message(
                sub, alert_type, cancelled_count, delayed_count, total_count
            )

            # Send
            sent = await apns_service.send_alert_notification(
                device.apns_token, title, body
            )

            if sent:
                sub.last_alerted_at = now
                sub.last_alert_hash = alert_hash
                alerts_sent += 1

                logger.info(
                    "route_alert_sent",
                    device_id=device.device_id,
                    data_source=sub.data_source,
                    line_id=sub.line_id,
                    from_station=sub.from_station_code,
                    to_station=sub.to_station_code,
                    alert_type=alert_type,
                    cancelled=cancelled_count,
                    delayed=delayed_count,
                    total=total_count,
                )

    if alerts_sent > 0:
        await db.commit()

    logger.info("route_alert_evaluation_complete", alerts_sent=alerts_sent)
    return alerts_sent


async def _query_journeys_for_subscription(
    db: AsyncSession,
    sub: RouteAlertSubscription,
    today,
    window_start,
    window_end,
) -> list[TrainJourney]:
    """Query TrainJourney records matching a subscription's filter criteria."""
    base_conditions = [
        TrainJourney.data_source == sub.data_source,
        TrainJourney.journey_date == today,
        TrainJourney.scheduled_departure >= window_start,
        TrainJourney.scheduled_departure <= window_end,
    ]

    if sub.line_id:
        # Line mode: resolve line_id to line_codes via route topology
        route = _ROUTES_BY_ID.get(sub.line_id)
        if not route:
            logger.warning(
                "alert_unknown_line_id",
                line_id=sub.line_id,
                data_source=sub.data_source,
            )
            return []

        line_codes = list(route.line_codes)
        base_conditions.append(TrainJourney.line_code.in_(line_codes))

        result = await db.execute(
            select(TrainJourney).where(and_(*base_conditions))
        )
        return list(result.scalars().all())

    else:
        # Station-pair mode: match origin/destination or journey stops
        # First try direct origin/destination match
        direct_conditions = base_conditions + [
            TrainJourney.origin_station_code == sub.from_station_code,
            TrainJourney.terminal_station_code == sub.to_station_code,
        ]
        result = await db.execute(
            select(TrainJourney).where(and_(*direct_conditions))
        )
        direct_matches = list(result.scalars().all())

        if direct_matches:
            return direct_matches

        # Fall back: journeys that pass through both stations in order
        from_stop = JourneyStop.__table__.alias("from_stop")
        to_stop = JourneyStop.__table__.alias("to_stop")

        subq = (
            select(from_stop.c.journey_id)
            .join(
                to_stop,
                and_(
                    from_stop.c.journey_id == to_stop.c.journey_id,
                    from_stop.c.stop_sequence < to_stop.c.stop_sequence,
                ),
            )
            .where(
                and_(
                    from_stop.c.station_code == sub.from_station_code,
                    to_stop.c.station_code == sub.to_station_code,
                    from_stop.c.stop_sequence.isnot(None),
                    to_stop.c.stop_sequence.isnot(None),
                )
            )
            .scalar_subquery()
        )

        result = await db.execute(
            select(TrainJourney).where(
                and_(
                    *base_conditions,
                    TrainJourney.id.in_(subq),
                )
            )
        )
        return list(result.scalars().all())


def _is_significantly_delayed(journey: TrainJourney) -> bool:
    """Check if a journey has a delay >= DELAY_THRESHOLD_MINUTES."""
    if not journey.actual_departure or not journey.scheduled_departure:
        return False

    delay = (journey.actual_departure - journey.scheduled_departure).total_seconds() / 60
    return delay >= DELAY_THRESHOLD_MINUTES


def _compute_alert_hash(
    alert_type: str,
    cancelled_count: int,
    delayed_count: int,
    total_count: int,
) -> str:
    """Generate a deduplication hash for an alert."""
    raw = f"{alert_type}:{cancelled_count}:{delayed_count}:{total_count}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _build_alert_message(
    sub: RouteAlertSubscription,
    alert_type: str,
    cancelled_count: int,
    delayed_count: int,
    total_count: int,
) -> tuple[str, str]:
    """Build notification title and body for an alert."""
    # Describe the route
    if sub.line_id:
        route = _ROUTES_BY_ID.get(sub.line_id)
        route_name = route.name if route else sub.line_id
    else:
        route_name = f"{sub.from_station_code} → {sub.to_station_code}"

    if alert_type == "cancellation":
        title = f"{sub.data_source}: Cancellations on {route_name}"
        if cancelled_count == 1:
            body = f"1 train cancelled in the past hour ({total_count} total)."
        else:
            body = f"{cancelled_count} trains cancelled in the past hour ({total_count} total)."
    else:
        title = f"{sub.data_source}: Delays on {route_name}"
        body = (
            f"{delayed_count} of {total_count} trains delayed {DELAY_THRESHOLD_MINUTES}+ min "
            f"in the past hour."
        )

    return title, body
