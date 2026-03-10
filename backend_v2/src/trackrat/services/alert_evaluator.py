"""
Route alert evaluation service.

Checks active subscriptions against recent departure data and sends
push notifications when significant delays or cancellations are detected,
or when train frequency drops significantly below normal levels.
"""

import hashlib
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from trackrat.services.summary import SummaryService

from sqlalchemy import Time, and_, cast, extract, or_, select
from sqlalchemy import func as sqla_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from trackrat.config.route_topology import ALL_ROUTES, Route
from trackrat.config.stations import get_station_name
from trackrat.config.stations.lirr import LIRR_ROUTES
from trackrat.config.stations.mnr import MNR_ROUTES
from trackrat.models.database import (
    DeviceToken,
    JourneyStop,
    RouteAlertSubscription,
    ServiceAlert,
    TrainJourney,
)
from trackrat.services.apns import SimpleAPNSService
from trackrat.services.congestion_types import (
    FREQ_THRESHOLD_REDUCED,
    FREQUENCY_FIRST_SOURCES,
)
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

# Data sources that support service alerts (MTA systems only)
SERVICE_ALERT_SOURCES = {"SUBWAY", "LIRR", "MNR"}

# Build route-ID lookup once at import time
_ROUTES_BY_ID = {route.id: route for route in ALL_ROUTES}

# Build reverse maps from line_code to GTFS route_id for LIRR/MNR
# LIRR: line_code "LIRR-BB" -> GTFS route_id "1"
_LIRR_LINE_CODE_TO_GTFS: dict[str, str] = {
    info[0]: gtfs_id for gtfs_id, info in LIRR_ROUTES.items()
}
# MNR: line_code "MNR-HUD" -> GTFS route_id "1"
_MNR_LINE_CODE_TO_GTFS: dict[str, str] = {
    info[0]: gtfs_id for gtfs_id, info in MNR_ROUTES.items()
}


def _get_gtfs_route_ids_for_subscription(
    sub: RouteAlertSubscription,
) -> set[str]:
    """Get GTFS route_ids that an alert subscription covers.

    Maps our internal route topology (line_id -> line_codes) to the
    GTFS route_ids used in MTA service alert feeds.

    For subway: line_codes ARE the GTFS route_ids (e.g. "G", "4")
    For LIRR: line_codes like "LIRR-BB" map back to GTFS "1" via LIRR_ROUTES
    For MNR: line_codes like "MNR-HUD" map back to GTFS "1" via MNR_ROUTES
    """
    if not sub.line_id:
        return set()

    route = _ROUTES_BY_ID.get(sub.line_id)
    if not route:
        return set()

    gtfs_ids: set[str] = set()
    for line_code in route.line_codes:
        if sub.data_source == "SUBWAY":
            gtfs_ids.add(line_code)
        elif sub.data_source == "LIRR":
            gtfs_id = _LIRR_LINE_CODE_TO_GTFS.get(line_code)
            if gtfs_id:
                gtfs_ids.add(gtfs_id)
        elif sub.data_source == "MNR":
            gtfs_id = _MNR_LINE_CODE_TO_GTFS.get(line_code)
            if gtfs_id:
                gtfs_ids.add(gtfs_id)

    return gtfs_ids


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
    state_changed = False

    for device in devices:
        for sub in device.subscriptions:
            # Day-of-week check (bitmask: Mon=1, Tue=2, ..., Sun=64)
            day_bit = 1 << now.weekday()
            if not ((sub.active_days or 0) & day_bit):
                continue

            # Time window check
            if not _is_within_time_window(sub, now):
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
                # Recovery check: if we previously alerted and now there are
                # no journeys to evaluate, skip (don't send recovery when we
                # simply have no data).
                continue

            # Per-subscription delay threshold (or system default)
            delay_threshold = sub.delay_threshold_minutes or DELAY_THRESHOLD_MINUTES

            # Count cancellations and delays
            cancelled_count = 0
            delayed_count = 0
            total_count = len(journeys)

            # For station-pair subs, check arrival delay at the destination
            dest_station = sub.to_station_code if not sub.line_id else None

            for journey in journeys:
                if journey.is_cancelled:
                    cancelled_count += 1
                elif _is_significantly_delayed(
                    journey,
                    to_station_code=dest_station,
                    threshold_minutes=delay_threshold,
                ):
                    delayed_count += 1

            # Per-subscription service threshold (or system default)
            freq_threshold = (
                (sub.service_threshold_pct / 100.0)
                if sub.service_threshold_pct is not None
                else FREQ_THRESHOLD_REDUCED
            )

            # Determine if alert is warranted
            should_alert = False
            alert_type = ""
            frequency_factor: float | None = None

            if cancelled_count > 0:
                should_alert = True
                alert_type = "cancellation"
            elif sub.data_source in FREQUENCY_FIRST_SOURCES:
                # Frequency-first systems (subway, PATH, PATCO): check
                # reduced service instead of delays
                if sub.data_source in REALTIME_SOURCES:
                    active_count = total_count - cancelled_count
                    baseline = await _query_baseline_train_count(db, sub, now)
                    # Halve baseline for directional subs since baseline covers both directions
                    if baseline is not None and sub.direction:
                        baseline *= 0.5
                    if baseline is not None and baseline > 0:
                        frequency_factor = active_count / baseline
                        if frequency_factor < freq_threshold:
                            should_alert = True
                            alert_type = "reduced_service"
            elif (
                total_count > 0
                and (delayed_count / total_count) >= DELAY_PERCENT_THRESHOLD
            ):
                # Delay-first systems (NJT, Amtrak, LIRR, MNR): check delays
                should_alert = True
                alert_type = "delay"

            if not should_alert:
                # Recovery: conditions cleared after a previous alert
                if sub.notify_recovery and sub.last_alert_hash:
                    sent = await _send_recovery_notification(
                        sub, device, now, apns_service
                    )
                    if sent:
                        sub.last_alert_hash = None
                        sub.last_alerted_at = now
                        alerts_sent += 1
                        state_changed = True
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
                delay_threshold=delay_threshold,
            )

            # Send
            if not device.apns_token:
                continue
            custom_data = {
                "route_alert": {
                    "data_source": sub.data_source,
                    "line_id": sub.line_id,
                    "direction": sub.direction,
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
                state_changed = True

                logger.info(
                    "route_alert_sent",
                    device_id=device.device_id,
                    data_source=sub.data_source,
                    line_id=sub.line_id,
                    direction=sub.direction,
                    from_station=sub.from_station_code,
                    to_station=sub.to_station_code,
                    train_id=sub.train_id,
                    alert_type=alert_type,
                    cancelled=cancelled_count,
                    delayed=delayed_count,
                    total=total_count,
                    frequency_factor=frequency_factor,
                )

    if state_changed:
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

    # Per-subscription delay threshold (or system default)
    delay_threshold = sub.delay_threshold_minutes or DELAY_THRESHOLD_MINUTES

    # Determine alert type
    alert_type = ""
    if journey.is_cancelled:
        alert_type = "cancellation"
    elif _is_significantly_delayed(journey, threshold_minutes=delay_threshold):
        alert_type = "delay"

    if not alert_type:
        # Recovery: conditions cleared after a previous alert
        if sub.notify_recovery and sub.last_alert_hash:
            sent = await _send_recovery_notification(sub, device, now, apns_service)
            if sent:
                sub.last_alert_hash = None
                sub.last_alerted_at = now
            return sent
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
        journeys = list(result.scalars().all())

        # Filter by direction if specified
        if sub.direction:
            journeys = _filter_by_direction(journeys, route, sub.direction)

        return journeys

    else:
        # Station-pair mode: match origin/destination or journey stops
        # Eagerly load stops so _is_significantly_delayed can check
        # arrival delay at the destination station.
        eager_opts = [selectinload(TrainJourney.stops)]

        # First try direct origin/destination match
        direct_conditions = base_conditions + [
            TrainJourney.origin_station_code == sub.from_station_code,
            TrainJourney.terminal_station_code == sub.to_station_code,
        ]
        result = await db.execute(
            select(TrainJourney).options(*eager_opts).where(and_(*direct_conditions))
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
            select(TrainJourney)
            .options(*eager_opts)
            .where(
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


def _filter_by_direction(
    journeys: list[TrainJourney],
    route: Route,
    direction: str,
) -> list[TrainJourney]:
    """Keep only journeys traveling toward the given terminus station.

    Direction is determined by comparing station indices in the route's
    ordered stations tuple.  If direction equals the last station,
    keep trains where terminal_idx > origin_idx (forward).  If it
    equals the first station, keep trains where terminal_idx < origin_idx
    (reverse).
    """
    station_list = route.stations
    station_set = route._station_set

    if direction not in station_set:
        logger.warning(
            "unknown_alert_direction",
            direction=direction,
            route=route.name,
            route_id=route.id,
        )
        return journeys

    toward_end = direction == station_list[-1]

    filtered = []
    for j in journeys:
        if (
            j.origin_station_code not in station_set
            or j.terminal_station_code not in station_set
        ):
            continue
        o_idx = station_list.index(j.origin_station_code)
        t_idx = station_list.index(j.terminal_station_code)
        if toward_end and t_idx > o_idx:
            filtered.append(j)
        elif not toward_end and t_idx < o_idx:
            filtered.append(j)
    return filtered


def _is_within_time_window(sub: RouteAlertSubscription, now: datetime) -> bool:
    """Check if the current time falls within the subscription's active time window.

    Returns True if no time window is configured (always active).
    """
    if sub.active_start_minutes is None or sub.active_end_minutes is None:
        return True
    if not sub.timezone:
        return True

    try:
        tz = ZoneInfo(sub.timezone)
        local_now = now.astimezone(tz)
    except (KeyError, ValueError):
        # Invalid timezone — treat as always active
        return True

    current_minutes = local_now.hour * 60 + local_now.minute
    start = sub.active_start_minutes
    end = sub.active_end_minutes

    if start <= end:
        # Normal range: e.g., 6:00 AM (360) to 10:00 AM (600)
        return start <= current_minutes <= end
    else:
        # Wraps midnight: e.g., 10:00 PM (1320) to 6:00 AM (360)
        return current_minutes >= start or current_minutes <= end


async def _send_recovery_notification(
    sub: RouteAlertSubscription,
    device: DeviceToken,
    now: datetime,
    apns_service: SimpleAPNSService,
) -> bool:
    """Send an 'all clear' recovery notification when conditions normalize."""
    if not device.apns_token:
        return False

    route_name = _get_route_name(sub)
    title = f"Route Clear: {route_name}"
    body = f"Conditions have returned to normal on {route_name}."

    custom_data = {
        "route_alert": {
            "data_source": sub.data_source,
            "line_id": sub.line_id,
            "direction": sub.direction,
            "from_station_code": sub.from_station_code,
            "to_station_code": sub.to_station_code,
            "train_id": sub.train_id,
            "alert_type": "recovery",
        }
    }
    sent = await apns_service.send_alert_notification(
        device.apns_token, title, body, custom_data=custom_data
    )

    if sent:
        logger.info(
            "recovery_alert_sent",
            device_id=device.device_id,
            data_source=sub.data_source,
            line_id=sub.line_id,
            direction=sub.direction,
        )

    return sent


def _get_route_name(sub: RouteAlertSubscription) -> str:
    """Build a human-readable route name for a subscription."""
    if sub.line_id:
        route = _ROUTES_BY_ID.get(sub.line_id)
        route_name = route.name if route else sub.line_id
        if sub.direction:
            direction_name = get_station_name(sub.direction)
            route_name = f"{route_name} toward {direction_name}"
        return route_name
    elif sub.train_id:
        return f"Train {sub.train_id}"
    else:
        from_name = get_station_name(sub.from_station_code or "")
        to_name = get_station_name(sub.to_station_code or "")
        return f"{from_name} → {to_name}"


def _is_significantly_delayed(
    journey: TrainJourney,
    to_station_code: str | None = None,
    threshold_minutes: int = DELAY_THRESHOLD_MINUTES,
) -> bool:
    """Check if a journey has a delay >= threshold_minutes.

    When *to_station_code* is provided (station-pair subscriptions), also
    checks arrival delay at the destination stop — a train may depart on time
    but arrive late due to en-route delays.
    """
    # Check departure delay (always available for delay-first sources)
    departure_delayed = False
    if journey.actual_departure and journey.scheduled_departure:
        dep_delay = (
            journey.actual_departure - journey.scheduled_departure
        ).total_seconds() / 60
        departure_delayed = dep_delay >= threshold_minutes

    if departure_delayed:
        return True

    # For station-pair subs, also check arrival delay at the destination stop
    if to_station_code and hasattr(journey, "stops") and journey.stops:
        for stop in journey.stops:
            if (
                stop.station_code == to_station_code
                and stop.actual_arrival
                and stop.scheduled_arrival
            ):
                arr_delay = (
                    stop.actual_arrival - stop.scheduled_arrival
                ).total_seconds() / 60
                return arr_delay >= threshold_minutes

    return False


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
    delay_threshold: int = DELAY_THRESHOLD_MINUTES,
) -> tuple[str, str]:
    """Build notification title and body for an alert."""
    route_name = _get_route_name(sub)

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
            f"{delayed_count} of {total_count} trains delayed {delay_threshold}+ min "
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


# ---------------------------------------------------------------------------
# Morning digest evaluation
# ---------------------------------------------------------------------------


async def evaluate_morning_digests(
    db: AsyncSession, apns_service: SimpleAPNSService
) -> int:
    """
    Send morning digest notifications for subscriptions whose digest time
    falls within the current 5-minute evaluation window.

    Returns the number of digests sent.
    """
    from trackrat.services.summary import SummaryService

    result = await db.execute(
        select(DeviceToken).options(selectinload(DeviceToken.subscriptions))
    )
    devices = result.scalars().all()

    summary_service = SummaryService()
    digests_sent = 0

    for device in devices:
        for sub in device.subscriptions:
            if sub.digest_time_minutes is None or not sub.timezone:
                continue

            try:
                local_now = datetime.now(ZoneInfo(sub.timezone))
            except (KeyError, ValueError):
                continue

            # Check if within ±2 min window of digest time
            current_minutes = local_now.hour * 60 + local_now.minute
            diff = abs(current_minutes - sub.digest_time_minutes)
            # Handle midnight wrap (e.g., current=1438, digest=2 → diff should be 4)
            if diff > 720:
                diff = 1440 - diff
            if diff > 2:
                continue

            # Day-of-week check
            day_bit = 1 << local_now.weekday()
            if not ((sub.active_days or 0) & day_bit):
                continue

            # Already sent today?
            if sub.last_digest_at:
                last_digest_local = sub.last_digest_at.astimezone(
                    ZoneInfo(sub.timezone)
                )
                if last_digest_local.date() == local_now.date():
                    continue

            # Generate summary
            route_name = _get_route_name(sub)
            summary = await _generate_digest_summary(db, sub, summary_service)

            if not summary or not device.apns_token:
                continue

            title = f"Morning Update: {route_name}"
            custom_data = {
                "route_alert": {
                    "data_source": sub.data_source,
                    "line_id": sub.line_id,
                    "direction": sub.direction,
                    "from_station_code": sub.from_station_code,
                    "to_station_code": sub.to_station_code,
                    "train_id": sub.train_id,
                    "alert_type": "digest",
                }
            }
            sent = await apns_service.send_alert_notification(
                device.apns_token, title, summary, custom_data=custom_data
            )

            if sent:
                sub.last_digest_at = datetime.now(UTC)
                digests_sent += 1

                logger.info(
                    "morning_digest_sent",
                    device_id=device.device_id,
                    data_source=sub.data_source,
                    line_id=sub.line_id,
                    route_name=route_name,
                )

    if digests_sent > 0:
        await db.commit()

    logger.info("morning_digest_evaluation_complete", digests_sent=digests_sent)
    return digests_sent


async def _generate_digest_summary(
    db: AsyncSession,
    sub: RouteAlertSubscription,
    summary_service: "SummaryService",
) -> str | None:
    """Generate digest text for a subscription using SummaryService."""
    try:
        if sub.line_id:
            route = _ROUTES_BY_ID.get(sub.line_id)
            if not route:
                return None
            stations = route.stations
            from_station = (
                stations[0] if sub.direction == stations[-1] else stations[-1]
            )
            to_station = sub.direction or stations[-1]
            result = await summary_service.get_route_summary(
                db,
                from_station=from_station,
                to_station=to_station,
                data_source=sub.data_source,
            )
        elif sub.from_station_code and sub.to_station_code:
            result = await summary_service.get_route_summary(
                db,
                from_station=sub.from_station_code,
                to_station=sub.to_station_code,
                data_source=sub.data_source,
            )
        elif sub.train_id:
            result = await summary_service.get_train_summary(
                db,
                train_id=sub.train_id,
            )
        else:
            return None

        # Combine headline and body for a concise push notification
        parts = []
        if result.headline:
            parts.append(result.headline)
        if result.body:
            parts.append(result.body)
        return " ".join(parts) if parts else None
    except Exception:
        logger.warning(
            "digest_summary_generation_failed",
            data_source=sub.data_source,
            line_id=sub.line_id,
            exc_info=True,
        )
        return None


# ---------------------------------------------------------------------------
# Service alert (planned work) evaluation
# ---------------------------------------------------------------------------

# Notify about planned work starting within this window
PLANNED_WORK_LOOKAHEAD_HOURS = 48


async def evaluate_service_alerts(
    db: AsyncSession, apns_service: SimpleAPNSService
) -> int:
    """Evaluate planned work alerts for subscriptions with include_planned_work=True.

    Checks active service alerts against user subscriptions and sends
    push notifications for new planned work affecting subscribed routes.

    Returns the number of alerts sent.
    """
    now = now_et()
    now_epoch = int(now.timestamp())
    lookahead_epoch = int(
        (now + timedelta(hours=PLANNED_WORK_LOOKAHEAD_HOURS)).timestamp()
    )

    # Load devices with subscriptions that opt into planned work
    result = await db.execute(
        select(DeviceToken).options(selectinload(DeviceToken.subscriptions))
    )
    devices = result.scalars().all()

    # Load all active planned_work alerts for MTA systems
    alert_result = await db.execute(
        select(ServiceAlert).where(
            ServiceAlert.is_active.is_(True),
            ServiceAlert.alert_type == "planned_work",
            ServiceAlert.data_source.in_(SERVICE_ALERT_SOURCES),
        )
    )
    all_alerts = list(alert_result.scalars().all())

    if not all_alerts:
        return 0

    alerts_sent = 0

    for device in devices:
        if not device.apns_token:
            continue

        for sub in device.subscriptions:
            if not sub.include_planned_work:
                continue

            if sub.data_source not in SERVICE_ALERT_SOURCES:
                continue

            # Only line-based subscriptions support planned work alerts
            if not sub.line_id:
                continue

            # Get GTFS route_ids this subscription covers
            gtfs_route_ids = _get_gtfs_route_ids_for_subscription(sub)
            if not gtfs_route_ids:
                continue

            # Find alerts affecting this subscription's routes
            matching_alerts = _find_matching_alerts(
                all_alerts,
                sub.data_source,
                gtfs_route_ids,
                now_epoch,
                lookahead_epoch,
            )

            if not matching_alerts:
                continue

            # Check which alerts are new (not already notified)
            already_notified = set(sub.last_service_alert_ids or [])
            new_alerts = [
                a for a in matching_alerts if a.alert_id not in already_notified
            ]

            if not new_alerts:
                continue

            # Build and send notification for new alerts
            title, body = _build_service_alert_message(sub, new_alerts)

            custom_data = {
                "service_alert": {
                    "data_source": sub.data_source,
                    "line_id": sub.line_id,
                    "alert_count": len(new_alerts),
                    "alert_ids": [a.alert_id for a in new_alerts],
                }
            }
            sent = await apns_service.send_alert_notification(
                device.apns_token, title, body, custom_data=custom_data
            )

            if sent:
                # Track notified alert IDs (keep last 50 to prevent unbounded growth)
                notified_ids = list(already_notified | {a.alert_id for a in new_alerts})
                sub.last_service_alert_ids = notified_ids[-50:]
                alerts_sent += 1

                logger.info(
                    "service_alert_sent",
                    device_id=device.device_id,
                    data_source=sub.data_source,
                    line_id=sub.line_id,
                    new_alert_count=len(new_alerts),
                    alert_ids=[a.alert_id for a in new_alerts],
                )

    if alerts_sent > 0:
        await db.commit()

    logger.info("service_alert_evaluation_complete", alerts_sent=alerts_sent)
    return alerts_sent


def _find_matching_alerts(
    alerts: list[ServiceAlert],
    data_source: str,
    gtfs_route_ids: set[str],
    now_epoch: int,
    lookahead_epoch: int,
) -> list[ServiceAlert]:
    """Find service alerts that match a subscription and have upcoming active periods.

    Returns alerts that:
    1. Are for the same data source
    2. Affect at least one of the subscription's routes
    3. Have at least one active period starting within the lookahead window,
       or are currently active
    """
    matching: list[ServiceAlert] = []

    for alert in alerts:
        if alert.data_source != data_source:
            continue

        # Check route overlap
        alert_routes = set(alert.affected_route_ids or [])
        if not alert_routes & gtfs_route_ids:
            continue

        # Check if any active period is current or upcoming
        has_relevant_period = False
        for period in alert.active_periods or []:
            start = period.get("start")
            end = period.get("end")

            if start is None:
                continue

            # Currently active (started and not yet ended)
            if start <= now_epoch and (end is None or end > now_epoch):
                has_relevant_period = True
                break

            # Starting within lookahead window
            if now_epoch < start <= lookahead_epoch:
                has_relevant_period = True
                break

        if has_relevant_period:
            matching.append(alert)

    return matching


def _build_service_alert_message(
    sub: RouteAlertSubscription,
    alerts: list[ServiceAlert],
) -> tuple[str, str]:
    """Build notification title and body for service alert(s)."""
    route = _ROUTES_BY_ID.get(sub.line_id or "")
    route_name = route.name if route else (sub.line_id or "Unknown")

    if len(alerts) == 1:
        alert = alerts[0]
        title = f"{sub.data_source}: Planned work on {route_name}"
        body = alert.header_text or ""
    else:
        title = f"{sub.data_source}: {len(alerts)} planned work alerts for {route_name}"
        # Show first alert's header with count
        body = alerts[0].header_text or ""
        if len(alerts) > 1:
            body += f" (+{len(alerts) - 1} more)"

    return title, body
