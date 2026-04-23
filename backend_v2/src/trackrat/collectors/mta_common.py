"""
Shared utilities for MTA GTFS-RT based collectors (LIRR, Metro-North, and NYC Subway).

Provides time-based departure inference, journey metadata tracking,
and completion detection — logic that both collectors need but that
the MTA GTFS-RT feed doesn't provide explicitly.

Follows the patterns established in the PATH collector.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import noload, selectinload

from trackrat.models.database import JourneyStop, TrainJourney
from trackrat.utils.time import normalize_to_et

logger = logging.getLogger(__name__)

# Loader options for GTFS-RT collector update queries (subway, LIRR, MNR,
# BART, MBTA, Metra). TrainJourney has 5 delete-orphan child collections
# (snapshots, segment_times, dwell_times, progress, progress_snapshots)
# that SQLAlchemy would lazy-load during flush orphan checks, triggering
# greenlet_spawn errors in async context. These collectors never modify
# any of them — they only read/merge journey.stops — so noload() skips
# the check without the per-journey round-trips that selectinload costs.
JOURNEY_UPDATE_LOAD_OPTIONS = (
    selectinload(TrainJourney.stops),
    noload(TrainJourney.snapshots),
    noload(TrainJourney.segment_times),
    noload(TrainJourney.dwell_times),
    noload(TrainJourney.progress),
    noload(TrainJourney.progress_snapshots),
)

# Terminal stations where outbound trains originate (direction_id=0).
# Used as a fallback when GTFS static backfill is unavailable.
LIRR_ORIGIN_TERMINALS = frozenset({"NY", "LAT", "GCT", "HPA"})
MNR_ORIGIN_TERMINALS = frozenset({"GCT"})
METRA_ORIGIN_TERMINALS = frozenset({"CUS", "OTC", "LSS", "MILLENNIUM"})
MBTA_ORIGIN_TERMINALS = frozenset({"BOS", "BNST"})

_ORIGIN_TERMINAL_CONFIG: dict[str, tuple[frozenset[str], str | None]] = {
    "LIRR": (LIRR_ORIGIN_TERMINALS, "NY"),  # Penn Station is most common
    "MNR": (MNR_ORIGIN_TERMINALS, "GCT"),  # Grand Central is the only terminal
    "MBTA": (MBTA_ORIGIN_TERMINALS, "BOS"),  # South Station is most common
    # Subway has too many terminals for a single default; origin inference
    # is best-effort since GTFS-RT usually includes all stops for subway trips.
    "SUBWAY": (frozenset(), None),
    # Metra has 4 downtown Chicago terminals; default to CUS (most lines)
    "METRA": (METRA_ORIGIN_TERMINALS, "CUS"),
}

# Rough estimate of travel time from origin terminal to first visible RT stop.
# Used when synthesizing a departed origin stop without GTFS static data.
ORIGIN_TRAVEL_BUFFER = timedelta(minutes=10)


def infer_missing_origin(
    first_arrival_station: str,
    direction_id: int,
    data_source: str,
) -> str | None:
    """Infer the origin terminal when GTFS-RT drops it for outbound trains.

    GTFS-RT feeds omit stops the train has already passed. For outbound trains
    (direction_id=0), the origin terminal is the first stop dropped. This function
    detects that case and returns the most likely origin station code.

    Args:
        first_arrival_station: Station code of the first visible RT stop.
        direction_id: 0 = outbound (from terminal), 1 = inbound (to terminal).
        data_source: "LIRR", "MNR", or "SUBWAY".

    Returns:
        Inferred origin station code, or None if no inference needed
        (inbound train or first stop is already a terminal).
    """
    if direction_id != 0:
        return None

    config = _ORIGIN_TERMINAL_CONFIG.get(data_source)
    if not config:
        return None

    terminals, default_origin = config

    # If the first RT stop is already a terminal, the origin wasn't dropped
    if first_arrival_station in terminals:
        return None

    return default_origin


def infer_subway_origin(
    line_code: str,
    terminal_station: str,
    first_arrival_station: str,
) -> str | None:
    """Infer the origin terminal for a subway trip using route topology.

    Unlike LIRR/MNR which have a single main terminal, each subway route has
    two terminals (one per direction). We determine the origin by looking at the
    train's destination (last visible stop in the feed): the origin is the
    opposite terminal. This is direction-agnostic — it works regardless of how
    the topology stations are ordered.

    Args:
        line_code: GTFS route_id (e.g., "7", "A", "FS").
        terminal_station: Station code of the train's destination (last RT stop).
        first_arrival_station: Station code of the first visible RT stop.

    Returns:
        Inferred origin station code, or None if inference is not possible.
    """
    from trackrat.config.route_topology import get_route_by_line_code

    route = get_route_by_line_code("SUBWAY", line_code)
    if not route or len(route.stations) < 2:
        return None

    # If first visible stop is already a terminal, no inference needed
    if first_arrival_station in (route.stations[0], route.stations[-1]):
        return None

    # The origin is the opposite terminal from the destination
    if terminal_station == route.stations[-1]:
        return route.stations[0]
    elif terminal_station == route.stations[0]:
        return route.stations[-1]

    # Terminal is mid-route (express shortline, etc.) — can't determine
    return None


def infer_direction_from_terminals(
    last_stop_code: str,
    data_source: str,
) -> int:
    """Infer direction_id from stop order when the feed doesn't provide it.

    MNR GTFS-RT never sets direction_id (defaults to 0), so all trips look
    outbound. This function checks whether the last stop is a known terminal
    to determine the actual direction.

    Args:
        last_stop_code: Station code of the last stop by arrival time.
        data_source: "LIRR", "MNR", or "SUBWAY".

    Returns:
        1 if inbound (last stop is a terminal), 0 otherwise.
    """
    config = _ORIGIN_TERMINAL_CONFIG.get(data_source)
    if not config:
        return 0

    terminals, _ = config
    return 1 if last_stop_code in terminals else 0


def build_complete_stops(
    realtime_arrivals: list[Any],
    static_stops: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str, str]:
    """Merge GTFS-RT arrivals with GTFS static stops to produce a complete stop list.

    GTFS-RT feeds may omit already-passed stops (e.g., LIRR drops the origin
    terminal from outbound trips). This function backfills those missing stops
    from the static schedule.

    Args:
        realtime_arrivals: LirrArrival or MnrArrival objects (sorted by arrival_time).
            Expected attributes: station_code, arrival_time, departure_time,
            delay_seconds, track.
        static_stops: Dicts from GTFSService.get_static_stop_times(), ordered by
            stop_sequence. Keys: station_code, stop_sequence, arrival_time,
            departure_time.

    Returns:
        Tuple of (stops, origin_code, terminal_code) where stops is a list of dicts:
            station_code, stop_sequence, scheduled_arrival, scheduled_departure,
            actual_arrival, actual_departure, track, has_departed.
        origin_code and terminal_code are from the full static schedule.
    """
    # Filter out static stops with no internal station_code mapping.
    # GTFS feeds can contain stops not in our station map (event-only platforms,
    # recently added stations, etc.).  Their station_code is NULL in the DB.
    static_stops = [s for s in static_stops if s.get("station_code")]

    if not static_stops:
        # All stops were unmapped — fall back to RT-only path
        return [], realtime_arrivals[0].station_code, realtime_arrivals[-1].station_code

    # Index RT arrivals by station_code for O(1) lookup
    rt_by_station: dict[str, Any] = {}
    for arr in realtime_arrivals:
        rt_by_station[arr.station_code] = arr

    # Find the static stop_sequence of the earliest RT arrival to identify
    # which static stops the train has already passed
    first_rt_static_seq = None
    for static_stop in static_stops:
        if static_stop["station_code"] in rt_by_station:
            first_rt_static_seq = static_stop["stop_sequence"]
            break

    origin_code = static_stops[0]["station_code"]
    terminal_code = static_stops[-1]["station_code"]

    merged: list[dict[str, Any]] = []
    for static_stop in static_stops:
        code = static_stop["station_code"]
        seq = static_stop["stop_sequence"]
        arr = rt_by_station.pop(code, None)

        if arr is not None:
            # RT data available — use real-time times with static as scheduled.
            # GTFS-RT `time` is the predicted (actual) time; delay is the
            # offset from schedule.  Do NOT add delay to arrival_time.
            merged.append(
                {
                    "station_code": code,
                    "stop_sequence": seq,
                    "scheduled_arrival": static_stop["arrival_time"],
                    "scheduled_departure": static_stop["departure_time"],
                    "actual_arrival": arr.arrival_time,
                    "actual_departure": arr.departure_time,
                    "updated_arrival": arr.arrival_time,
                    "updated_departure": arr.departure_time,
                    "track": arr.track,
                    "has_departed": False,
                }
            )
        else:
            # No RT data — backfill from static schedule
            already_passed = (
                first_rt_static_seq is not None and seq < first_rt_static_seq
            )
            merged.append(
                {
                    "station_code": code,
                    "stop_sequence": seq,
                    "scheduled_arrival": static_stop["arrival_time"],
                    "scheduled_departure": static_stop["departure_time"],
                    "actual_arrival": None,
                    "actual_departure": None,
                    "updated_arrival": None,
                    "updated_departure": None,
                    "track": None,
                    "has_departed": already_passed,
                }
            )

    # Safety fallback: RT arrivals not in static (unmapped stops).
    # Append at end to avoid losing data.
    # GTFS-RT `time` is the predicted time; derive scheduled by subtracting delay.
    for code, arr in rt_by_station.items():
        delay = timedelta(seconds=arr.delay_seconds)
        merged.append(
            {
                "station_code": code,
                "stop_sequence": len(merged) + 1,
                "scheduled_arrival": arr.arrival_time - delay,
                "scheduled_departure": (arr.departure_time or arr.arrival_time) - delay,
                "actual_arrival": arr.arrival_time,
                "actual_departure": arr.departure_time,
                "updated_arrival": arr.arrival_time,
                "updated_departure": arr.departure_time,
                "track": arr.track,
                "has_departed": False,
            }
        )
        logger.warning(
            "mta_rt_stop_not_in_static",
            extra={"station_code": code, "trip_arrivals": len(realtime_arrivals)},
        )

    # Deduplicate by station_code — the unique_journey_stop constraint
    # requires one stop per station per journey. Static schedules can map
    # multiple GTFS stops to the same internal station_code.
    # Keep the entry with real-time data when there's a conflict.
    seen: dict[str, int] = {}
    deduped: list[dict[str, Any]] = []
    for stop in merged:
        code = stop["station_code"]
        if code in seen:
            idx = seen[code]
            if (
                deduped[idx]["actual_arrival"] is None
                and stop["actual_arrival"] is not None
            ):
                deduped[idx] = stop
            continue
        seen[code] = len(deduped)
        deduped.append(stop)

    return deduped, origin_code, terminal_code


def set_stop_track(
    stop: JourneyStop,
    new_track: str | None,
    data_source: str,
    train_id: str | None,
    now: datetime,
) -> None:
    """Assign a new track to a stop, updating ``track_assigned_at`` and logging.

    No-op when ``new_track`` is falsy or equal to the existing value. Emits a
    structured ``journey_stop_track_changed`` INFO log on every real transition
    (None → value, or value → value). Callers must validate ``new_track`` before
    calling (see :func:`trackrat.utils.sanitize.validate_track`).

    Args:
        stop: The JourneyStop to mutate.
        new_track: Track value from the upstream feed.
        data_source: Collector identifier for logging (e.g., "LIRR", "MNR").
        train_id: Train identifier for log correlation.
        now: Current time (used to stamp ``track_assigned_at`` on first assignment).
    """
    if not new_track or new_track == stop.track:
        return
    old = stop.track
    if not old:
        stop.track_assigned_at = now
    stop.track = new_track
    logger.info(
        "journey_stop_track_changed",
        extra={
            "train_id": train_id,
            "station_code": stop.station_code,
            "old_track": old,
            "new_track": new_track,
            "data_source": data_source,
        },
    )


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
                    stop.arrival_source = "scheduled_fallback"
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
