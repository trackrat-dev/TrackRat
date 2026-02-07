"""
Shared utilities for MTA GTFS-RT based collectors (LIRR and Metro-North).

Provides time-based departure inference, journey metadata tracking,
and completion detection — logic that both collectors need but that
the MTA GTFS-RT feed doesn't provide explicitly.

Follows the patterns established in the PATH collector.
"""

import logging
from datetime import datetime, timedelta

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import normalize_to_et

logger = logging.getLogger(__name__)


def update_stop_departure_status(stops: list[JourneyStop], now: datetime) -> None:
    """Infer departure status for MTA stops based on actual/scheduled times.

    Three inference paths:
    1. Stop has actual_departure (or actual_arrival) in the past -> departed
    2. Stop has no actuals but scheduled_arrival + grace period < now -> departed
    3. Sequential consistency: if stop N departed, all stops before N must have too

    Args:
        stops: Journey stops sorted by stop_sequence (or creation order).
        now: Current time (timezone-aware, Eastern).
    """
    now_et_normalized = normalize_to_et(now)
    max_departed_sequence = 0

    for stop in stops:
        # Path A: actual times available and in the past
        effective_departure = stop.actual_departure or stop.actual_arrival
        if effective_departure:
            dep_et = normalize_to_et(effective_departure)
            if dep_et <= now_et_normalized:
                stop.has_departed_station = True
                if not stop.departure_source:
                    stop.departure_source = "time_inference"
                if stop.stop_sequence:
                    max_departed_sequence = max(
                        max_departed_sequence, stop.stop_sequence
                    )
                continue

        # Path B: no actual times, but scheduled time + grace period has passed
        if not stop.has_departed_station and stop.scheduled_arrival:
            grace_period = timedelta(minutes=2)
            scheduled_et = normalize_to_et(stop.scheduled_arrival)
            if scheduled_et + grace_period < now_et_normalized:
                stop.has_departed_station = True
                stop.departure_source = "time_inference"
                if stop.stop_sequence:
                    max_departed_sequence = max(
                        max_departed_sequence, stop.stop_sequence
                    )

    # Path C: sequential consistency
    departed_sequences = [
        s.stop_sequence for s in stops if s.has_departed_station and s.stop_sequence
    ]
    if departed_sequences:
        max_departed = max(departed_sequences)
        for stop in stops:
            if (
                stop.stop_sequence
                and stop.stop_sequence < max_departed
                and not stop.has_departed_station
            ):
                stop.has_departed_station = True
                if not stop.actual_departure:
                    stop.actual_departure = stop.scheduled_arrival
                if not stop.actual_arrival:
                    stop.actual_arrival = stop.scheduled_arrival
                stop.departure_source = "sequential_consistency"
                logger.debug(
                    "mta_sequential_consistency_fix",
                    extra={
                        "station_code": stop.station_code,
                        "stop_sequence": stop.stop_sequence,
                        "max_departed_sequence": max_departed,
                    },
                )


def update_journey_metadata(journey: TrainJourney, now: datetime) -> None:
    """Update journey freshness tracking fields.

    Args:
        journey: The journey to update.
        now: Current time (timezone-aware, Eastern).
    """
    journey.last_updated_at = now
    journey.update_count = (journey.update_count or 0) + 1


def check_journey_completed(journey: TrainJourney, stops: list[JourneyStop]) -> None:
    """Mark journey as completed if the terminal stop has departed.

    Args:
        journey: The journey to check.
        stops: Journey stops (must include terminal stop).
    """
    if not stops:
        return

    # Find terminal stop by max stop_sequence
    terminal_stop = max(
        (s for s in stops if s.stop_sequence is not None),
        key=lambda s: s.stop_sequence,  # type: ignore[arg-type,return-value]
        default=None,
    )
    if (
        terminal_stop
        and terminal_stop.has_departed_station
        and not journey.is_completed
    ):
        journey.is_completed = True
        journey.actual_arrival = (
            terminal_stop.actual_arrival or terminal_stop.scheduled_arrival
        )
        logger.info(
            "mta_journey_completed",
            extra={
                "train_id": journey.train_id,
                "data_source": journey.data_source,
                "actual_arrival": str(journey.actual_arrival),
            },
        )
