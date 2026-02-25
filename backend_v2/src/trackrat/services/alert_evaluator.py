"""
Route alert evaluation service.

Checks active subscriptions against recent departure data and sends
push notifications when significant delays or cancellations are detected,
or when train frequency drops significantly below normal levels.
"""

import hashlib
from datetime import date, datetime, timedelta

from sqlalchemy import Time, and_, cast, extract, or_, select
from sqlalchemy import func as sqla_func
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
from trackrat.services.congestion_types import FREQ_THRESHOLD_REDUCED
from trackrat.utils.time import now_et

logger = get_logger(__name__)

# Thresholds
DELAY_THRESHOLD_MINUTES = 15
DELAY_PERCENT_THRESHOLD = 0.50
COOLDOWN_MINUTES = 30
BASELINE_LOOKBACK_DAYS = 30
MIN_BASELINE_DAYS = 3  # Need at least 3 comparable days for a reliable baseline

# Data sources with real-time data (frequency alerts only apply to these)
REALTIME_SOURCES = {"NJT", "AMTRAK", "PATH", "LIRR", "MNR", "SUBWAY"}

# Data sources where train_id is stable and represents the same daily service
STABLE_TRAIN_ID_SOURCES = {"NJT", "AMTRAK", "LIRR", "MNR"}

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

    is_weekend = now.weekday() >= 5

    for device in devices:
        for sub in device.subscriptions:
            # Skip weekdays-only subscriptions on weekends
            if sub.weekdays_only and is_weekend:
                continue

            # Cooldown check
            if sub.last_alerted_at and sub.last_alerted_at >= cooldown_cutoff:
                continue

            # Train-ID subscriptions: single-train alert logic
            if sub.train_id:
                sent = await _evaluate_train_subscription(
                    db, sub, device, today, now, apns_service
                )
                if sent:
                    alerts_sent += 1
                continue

            # Build query for relevant journeys (line / station-pair modes)
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
            frequency_factor: float | None = None

            if cancelled_count > 0:
                should_alert = True
                alert_type = "cancellation"
            elif (
                total_count > 0
                and (delayed_count / total_count) >= DELAY_PERCENT_THRESHOLD
            ):
                should_alert = True
                alert_type = "delay"

            # Check frequency reduction for real-time sources
            if not should_alert and sub.data_source in REALTIME_SOURCES:
                active_count = total_count - cancelled_count
                baseline = await _query_baseline_train_count(db, sub, now)
                if baseline is not None and baseline > 0:
                    frequency_factor = active_count / baseline
                    if frequency_factor < FREQ_THRESHOLD_REDUCED:
                        should_alert = True
                        alert_type = "reduced_service"

            if not should_alert:
                continue

            # Dedup via hash
            alert_hash = _compute_alert_hash(
                alert_type,
                cancelled_count,
                delayed_count,
                total_count,
                frequency_factor=frequency_factor,
            )
            if sub.last_alert_hash == alert_hash:
                continue

            # Build notification
            title, body = _build_alert_message(
                sub,
                alert_type,
                cancelled_count,
                delayed_count,
                total_count,
                frequency_factor=frequency_factor,
            )

            # Send
            if not device.apns_token:
                continue
            custom_data = {
                "route_alert": {
                    "data_source": sub.data_source,
                    "line_id": sub.line_id,
                    "from_station_code": sub.from_station_code,
                    "to_station_code": sub.to_station_code,
                    "train_id": sub.train_id,
                }
            }
            sent = await apns_service.send_alert_notification(
                device.apns_token, title, body, custom_data=custom_data
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
                    train_id=sub.train_id,
                    alert_type=alert_type,
                    cancelled=cancelled_count,
                    delayed=delayed_count,
                    total=total_count,
                    frequency_factor=frequency_factor,
                )

    if alerts_sent > 0:
        await db.commit()

    logger.info("route_alert_evaluation_complete", alerts_sent=alerts_sent)
    return alerts_sent


async def _evaluate_train_subscription(
    db: AsyncSession,
    sub: RouteAlertSubscription,
    device: DeviceToken,
    today: date,
    now: datetime,
    apns_service: SimpleAPNSService,
) -> bool:
    """
    Evaluate a train_id subscription and send notification if warranted.

    For a specific train, alert on:
    - Cancellation
    - Delay >= DELAY_THRESHOLD_MINUTES

    Returns True if an alert was sent.
    """
    # Find today's journey for this specific train
    result = await db.execute(
        select(TrainJourney).where(
            and_(
                TrainJourney.train_id == sub.train_id,
                TrainJourney.data_source == sub.data_source,
                TrainJourney.journey_date == today,
            )
        )
    )
    journey = result.scalar_one_or_none()

    if not journey:
        return False

    # Determine alert type
    alert_type = ""
    if journey.is_cancelled:
        alert_type = "cancellation"
    elif _is_significantly_delayed(journey):
        alert_type = "delay"

    if not alert_type:
        return False

    # Compute delay for message
    delay_minutes = 0
    if (
        alert_type == "delay"
        and journey.actual_departure
        and journey.scheduled_departure
    ):
        delay_minutes = int(
            (journey.actual_departure - journey.scheduled_departure).total_seconds()
            / 60
        )

    # Dedup via hash
    alert_hash = _compute_train_alert_hash(
        sub.train_id or "", alert_type, delay_minutes
    )
    if sub.last_alert_hash == alert_hash:
        return False

    # Build notification
    title, body = _build_train_alert_message(sub, journey, alert_type, delay_minutes)

    if not device.apns_token:
        return False

    custom_data = {
        "route_alert": {
            "data_source": sub.data_source,
            "train_id": sub.train_id,
            "line_id": None,
            "from_station_code": None,
            "to_station_code": None,
        }
    }
    sent = await apns_service.send_alert_notification(
        device.apns_token, title, body, custom_data=custom_data
    )

    if sent:
        sub.last_alerted_at = now
        sub.last_alert_hash = alert_hash

        logger.info(
            "train_alert_sent",
            device_id=device.device_id,
            data_source=sub.data_source,
            train_id=sub.train_id,
            alert_type=alert_type,
            delay_minutes=delay_minutes,
        )

    return sent


async def _query_journeys_for_subscription(
    db: AsyncSession,
    sub: RouteAlertSubscription,
    today: date,
    window_start: datetime,
    window_end: datetime,
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

        result = await db.execute(select(TrainJourney).where(and_(*base_conditions)))
        return list(result.scalars().all())

    else:
        # Station-pair mode: match origin/destination or journey stops
        # First try direct origin/destination match
        direct_conditions = base_conditions + [
            TrainJourney.origin_station_code == sub.from_station_code,
            TrainJourney.terminal_station_code == sub.to_station_code,
        ]
        result = await db.execute(select(TrainJourney).where(and_(*direct_conditions)))
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


async def _query_baseline_train_count(
    db: AsyncSession,
    sub: RouteAlertSubscription,
    now: datetime,
) -> float | None:
    """
    Compute the average number of trains matching this subscription's scope
    in the same 60-minute time-of-day window and weekday/weekend pattern
    over the last 30 days.

    Uses the same rolling 60-minute window as the current count query
    (scheduled_departure within [now - 1h, now] by time of day) to avoid
    systematic bias from clock-hour boundaries.

    Returns None if insufficient historical data.
    """
    is_weekend = now.weekday() >= 5  # Saturday=5, Sunday=6

    lookback_start = (now - timedelta(days=BASELINE_LOOKBACK_DAYS)).date()
    lookback_end = (now - timedelta(days=1)).date()

    # Use time-of-day window matching the current 60-minute rolling window
    window_start_time = (now - timedelta(hours=1)).time()
    window_end_time = now.time()

    # Extract time of day from scheduled_departure in ET
    departure_time_et = cast(
        sqla_func.timezone("America/New_York", TrainJourney.scheduled_departure),
        Time,
    )

    # Build base conditions: same data source, same time-of-day window, same day type
    # Exclude cancelled trains to match the active_count calculation in evaluate_route_alerts
    base_conditions = [
        TrainJourney.data_source == sub.data_source,
        TrainJourney.journey_date >= lookback_start,
        TrainJourney.journey_date <= lookback_end,
        TrainJourney.is_cancelled.is_not(True),
    ]

    # Time-of-day filter: handle midnight crossover
    if window_start_time <= window_end_time:
        # Normal case: e.g., 09:30 to 10:30
        base_conditions.extend(
            [
                departure_time_et >= window_start_time,
                departure_time_et <= window_end_time,
            ]
        )
    else:
        # Midnight crossover: e.g., 23:30 to 00:30
        base_conditions.append(
            or_(
                departure_time_et >= window_start_time,
                departure_time_et <= window_end_time,
            )
        )

    # Filter weekday/weekend pattern
    if is_weekend:
        base_conditions.append(extract("dow", TrainJourney.journey_date).in_([0, 6]))
    else:
        base_conditions.append(
            extract("dow", TrainJourney.journey_date).in_([1, 2, 3, 4, 5])
        )

    if sub.line_id:
        route = _ROUTES_BY_ID.get(sub.line_id)
        if not route:
            return None
        base_conditions.append(TrainJourney.line_code.in_(list(route.line_codes)))
    else:
        base_conditions.extend(
            [
                TrainJourney.origin_station_code == sub.from_station_code,
                TrainJourney.terminal_station_code == sub.to_station_code,
            ]
        )

    # Count trains per day, then average across days
    per_day = (
        select(
            TrainJourney.journey_date,
            sqla_func.count(TrainJourney.id).label("day_count"),
        )
        .where(and_(*base_conditions))
        .group_by(TrainJourney.journey_date)
        .subquery()
    )

    result = await db.execute(
        select(
            sqla_func.avg(per_day.c.day_count),
            sqla_func.count(per_day.c.journey_date),
        )
    )
    row = result.one()
    avg_count, num_days = row[0], row[1]

    if num_days < MIN_BASELINE_DAYS or avg_count is None:
        return None

    return float(avg_count)


def _is_significantly_delayed(journey: TrainJourney) -> bool:
    """Check if a journey has a delay >= DELAY_THRESHOLD_MINUTES."""
    if not journey.actual_departure or not journey.scheduled_departure:
        return False

    delay = (
        journey.actual_departure - journey.scheduled_departure
    ).total_seconds() / 60
    return delay >= DELAY_THRESHOLD_MINUTES


def _compute_alert_hash(
    alert_type: str,
    cancelled_count: int,
    delayed_count: int,
    total_count: int,
    *,
    frequency_factor: float | None = None,
) -> str:
    """Generate a deduplication hash for an alert."""
    # Round frequency_factor to 1 decimal to avoid hash churn from tiny float changes
    freq_str = f"{frequency_factor:.1f}" if frequency_factor is not None else "none"
    raw = f"{alert_type}:{cancelled_count}:{delayed_count}:{total_count}:{freq_str}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _build_alert_message(
    sub: RouteAlertSubscription,
    alert_type: str,
    cancelled_count: int,
    delayed_count: int,
    total_count: int,
    *,
    frequency_factor: float | None = None,
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
    elif alert_type == "reduced_service":
        pct = int((frequency_factor or 0) * 100)
        title = f"{sub.data_source}: Reduced service on {route_name}"
        active = total_count - cancelled_count
        body = (
            f"Only {active} trains running in the past hour "
            f"({pct}% of normal). Expect longer waits."
        )
    else:
        title = f"{sub.data_source}: Delays on {route_name}"
        body = (
            f"{delayed_count} of {total_count} trains delayed {DELAY_THRESHOLD_MINUTES}+ min "
            f"in the past hour."
        )

    return title, body


def _compute_train_alert_hash(
    train_id: str, alert_type: str, delay_minutes: int
) -> str:
    """Generate a deduplication hash for a train-specific alert."""
    # Round delay to nearest 5 minutes to avoid hash churn from minor timing changes
    delay_bucket = (delay_minutes // 5) * 5
    raw = f"train:{train_id}:{alert_type}:{delay_bucket}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _build_train_alert_message(
    sub: RouteAlertSubscription,
    journey: TrainJourney,
    alert_type: str,
    delay_minutes: int,
) -> tuple[str, str]:
    """Build notification title and body for a train-specific alert."""
    route_desc = f"{journey.origin_station_code} → {journey.terminal_station_code}"

    if alert_type == "cancellation":
        title = f"{sub.data_source}: Train {sub.train_id} Cancelled"
        body = f"Train {sub.train_id} ({route_desc}) has been cancelled."
    else:
        title = f"{sub.data_source}: Train {sub.train_id} Delayed"
        body = (
            f"Train {sub.train_id} ({route_desc}) is delayed "
            f"{delay_minutes} minutes."
        )

    return title, body
