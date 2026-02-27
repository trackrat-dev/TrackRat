#!/usr/bin/env python3
"""Ground truth validation: compare TrackRat departures against raw transit provider data.

Run from the repo root using the backend poetry environment:
    cd backend_v2 && poetry run python3 ../scripts/ground-truth-validate.py [base_url] [--provider PATH] [--tolerance 1.5]
"""

import argparse
import asyncio
import sys
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

# Add backend src to path so trackrat package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend_v2", "src"))

from trackrat.collectors.path.collector import (  # noqa: E402
    _get_destination_station_from_headsign,
)
from trackrat.collectors.path.ridepath_client import RIDEPATH_API_URL  # noqa: E402
from trackrat.config.route_topology import get_routes_for_data_source  # noqa: E402
from trackrat.config.stations import (  # noqa: E402
    DISCOVERY_STATIONS,
    AMTRAK_TO_INTERNAL_STATION_MAP,
    PATH_RIDEPATH_API_TO_INTERNAL_MAP,
    get_station_code_by_name,
    get_station_name,
    map_amtrak_station_code,
)
from trackrat.utils.time import parse_njt_time  # noqa: E402

# --- ANSI colors (matching e2e-api-test.sh) ---
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BOLD = "\033[1m"
NC = "\033[0m"

# --- Counters ---
PASS_COUNT = 0
FAIL_COUNT = 0
WARN_COUNT = 0
SKIP_COUNT = 0


def log_pass(msg: str) -> None:
    global PASS_COUNT
    print(f"  {GREEN}PASS{NC} {msg}")
    PASS_COUNT += 1


def log_fail(msg: str, detail: str = "") -> None:
    global FAIL_COUNT
    print(f"  {RED}FAIL{NC} {msg}")
    if detail:
        print(f"       {detail}")
    FAIL_COUNT += 1


def log_warn(msg: str) -> None:
    global WARN_COUNT
    print(f"  {YELLOW}WARN{NC} {msg}")
    WARN_COUNT += 1


def log_skip(msg: str) -> None:
    global SKIP_COUNT
    print(f"  {YELLOW}SKIP{NC} {msg}")
    SKIP_COUNT += 1


# --- Data structures ---


@dataclass
class GroundTruthArrival:
    station_code: str  # Internal code (PJS, PHO, etc.)
    destination_code: str  # Internal code of destination
    expected_time: datetime
    line_color: str
    headsign: str
    minutes_away: int
    train_id: str = ""  # Provider train ID for cross-validation (NJT, Amtrak, LIRR, MNR)
    track: str | None = None  # Track/platform assignment from provider
    delay_seconds: int | None = None  # GTFS-RT delay (LIRR/MNR); None for other providers


@dataclass
class TrackRatDeparture:
    train_id: str
    destination_code: str
    destination_name: str
    departure_time: datetime  # Best available: actual > updated > scheduled
    line_code: str
    line_color: str
    observation_type: str
    track: str | None = None  # Track/platform from TrackRat API
    is_cancelled: bool = False  # Whether TrackRat reports this train as cancelled
    scheduled_time: datetime | None = None  # Original timetable time
    updated_time: datetime | None = None  # Real-time estimate
    actual_time: datetime | None = None  # Observed departure


@dataclass
class MatchResult:
    gt: GroundTruthArrival
    tr: TrackRatDeparture
    delta_seconds: int
    track_mismatch: bool = False  # True if both have track and they differ
    line_color_mismatch: bool = False  # True if both have line_color and they differ
    stale_scheduled: bool = False  # True if TR is OBSERVED but only has scheduled_time (no RT update)
    delay_mismatch_seconds: int | None = None  # Difference between GT and TR delay estimates (LIRR/MNR)


@dataclass
class ComparisonResult:
    route_name: str
    origin: str
    destination: str
    matches: list[MatchResult] = field(default_factory=list)
    missing: list[GroundTruthArrival] = field(default_factory=list)
    phantoms: list[TrackRatDeparture] = field(default_factory=list)
    arriving_unmatched: list[GroundTruthArrival] = field(default_factory=list)
    cancelled_in_tr: list[TrackRatDeparture] = field(default_factory=list)  # Cancelled in TR but not in GT


# --- RidePATH parsing (copied from RidePathClient._parse_minutes) ---


def parse_arrival_minutes(msg: str) -> int | None:
    """Parse RidePATH arrivalTimeMessage into minutes. e.g. '14 min' -> 14, 'Arriving' -> 0."""
    if not msg:
        return None
    lower = msg.strip().lower()
    if "arriving" in lower or "now" in lower:
        return 0
    if "min" in lower:
        try:
            return int(lower.replace("min", "").strip())
        except ValueError:
            return None
    return None


# --- Fetch ground truth from RidePATH ---


def fetch_ridepath_arrivals(client: httpx.Client) -> tuple[list[GroundTruthArrival], datetime | None]:
    """Fetch all arrivals from RidePATH API. Returns (arrivals, oldest_last_updated)."""
    try:
        resp = client.get(RIDEPATH_API_URL, timeout=15)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        log_fail(f"RidePATH API request failed: {e}")
        return [], None

    data = resp.json()
    results = data.get("results", [])
    now = datetime.now(timezone.utc)
    arrivals: list[GroundTruthArrival] = []
    oldest_updated: datetime | None = None

    for station_data in results:
        api_code = station_data.get("consideredStation", "")
        internal_code = PATH_RIDEPATH_API_TO_INTERNAL_MAP.get(api_code)
        if not internal_code:
            continue

        for dest_group in station_data.get("destinations", []):
            for msg in dest_group.get("messages", []):
                headsign = msg.get("headSign", "")
                minutes = parse_arrival_minutes(msg.get("arrivalTimeMessage", ""))
                if minutes is None:
                    continue

                dest_code = _get_destination_station_from_headsign(headsign)
                if not dest_code:
                    continue

                line_color = msg.get("lineColor", "")

                # Use lastUpdated as the baseline for computing expected_time.
                # The API's "X min" countdown is relative to when the prediction
                # was generated (lastUpdated), not when we fetch it.
                baseline = now
                last_updated_str = msg.get("lastUpdated")
                if last_updated_str:
                    try:
                        lu = datetime.fromisoformat(last_updated_str)
                        staleness = (now - lu).total_seconds()
                        if 0 <= staleness <= 300:
                            baseline = lu
                        if oldest_updated is None or lu < oldest_updated:
                            oldest_updated = lu
                    except ValueError:
                        pass

                expected_time = baseline + timedelta(minutes=minutes)

                arrivals.append(
                    GroundTruthArrival(
                        station_code=internal_code,
                        destination_code=dest_code,
                        expected_time=expected_time,
                        line_color=line_color,
                        headsign=headsign,
                        minutes_away=minutes,
                    )
                )

    return arrivals, oldest_updated


# --- Fetch ground truth from NJ Transit ---


def _create_njt_client():
    """Create NJTransitClient without requiring full backend Settings."""
    from trackrat.collectors.njt.client import NJTransitClient

    token = os.environ.get("TRACKRAT_NJT_API_TOKEN") or os.environ.get("NJT_TOKEN", "")
    if not token:
        raise KeyError("TRACKRAT_NJT_API_TOKEN or NJT_TOKEN must be set")
    return NJTransitClient.from_token(token)


def fetch_njt_ground_truth() -> list[GroundTruthArrival]:
    """Fetch ground truth departures from NJ Transit API.

    Polls DISCOVERY_STATIONS using NJTransitClient.get_train_schedule_with_stops().
    Requires TRACKRAT_NJT_API_TOKEN env var.
    """
    arrivals: list[GroundTruthArrival] = []
    seen: set[tuple[str, str]] = set()  # (train_id, station_code) dedup

    async def _fetch() -> list[GroundTruthArrival]:
        async with _create_njt_client() as client:
            for station_code in DISCOVERY_STATIONS:
                try:
                    data = await client.get_train_schedule_with_stops(station_code)
                except Exception as e:
                    log_warn(f"NJT API failed for station {station_code}: {e}")
                    continue

                items = data.get("ITEMS") or []
                for item in items:
                    train_id = item.get("TRAIN_ID", "").strip()
                    if not train_id:
                        continue

                    # Skip Amtrak trains (format: A + digits)
                    if train_id.startswith("A") and len(train_id) > 1 and train_id[1:].isdigit():
                        continue

                    # Dedup by train_id + station
                    if (train_id, station_code) in seen:
                        continue
                    seen.add((train_id, station_code))

                    # Parse scheduled departure time
                    sched_dep_str = item.get("SCHED_DEP_DATE", "")
                    if not sched_dep_str:
                        continue
                    try:
                        expected_time = parse_njt_time(sched_dep_str)
                    except Exception:
                        continue

                    # Resolve destination from STOPS (last stop's STATION_2CHAR)
                    stops = item.get("STOPS") or []
                    dest_code = None
                    if stops:
                        # Last stop with a station code is the terminal
                        for stop in reversed(stops):
                            code = stop.get("STATION_2CHAR", "").strip()
                            if code:
                                dest_code = code
                                break

                    # Fallback: try resolving DESTINATION name to code
                    if not dest_code:
                        dest_name = item.get("DESTINATION", "").strip()
                        if dest_name:
                            dest_code = get_station_code_by_name(dest_name)

                    if not dest_code:
                        continue

                    line_color = item.get("BACKCOLOR", "").strip()
                    destination_name = item.get("DESTINATION", "").strip()
                    headsign = f"{train_id} to {destination_name}"
                    track = item.get("TRACK", "").strip() or None

                    # Compute minutes_away from now
                    now = datetime.now(expected_time.tzinfo)
                    minutes_away = max(0, int((expected_time - now).total_seconds() / 60))

                    arrivals.append(
                        GroundTruthArrival(
                            station_code=station_code,
                            destination_code=dest_code,
                            expected_time=expected_time,
                            line_color=line_color,
                            headsign=headsign,
                            minutes_away=minutes_away,
                            train_id=train_id,
                            track=track,
                        )
                    )

        return arrivals

    return asyncio.run(_fetch())


# --- Fetch ground truth from Amtrak ---


def fetch_amtrak_ground_truth() -> list[GroundTruthArrival]:
    """Fetch ground truth departures from Amtrak API.

    Uses AmtrakClient.get_all_trains() and filters to NEC stations
    (those with internal station code mappings).
    """
    from trackrat.collectors.amtrak.client import AmtrakClient

    arrivals: list[GroundTruthArrival] = []

    async def _fetch() -> list[GroundTruthArrival]:
        async with AmtrakClient() as client:
            trains_by_num = await client.get_all_trains()

        for train_num, train_list in trains_by_num.items():
            for train in train_list:
                stations = train.stations
                if not stations:
                    continue

                # Find the last station with a mapped internal code as destination
                dest_code = None
                for stop in reversed(stations):
                    mapped = map_amtrak_station_code(stop.code)
                    if mapped:
                        dest_code = mapped
                        break

                if not dest_code:
                    continue

                headsign = f"{train.trainNum} {train.routeName}"

                for stop in stations:
                    internal_code = map_amtrak_station_code(stop.code)
                    if not internal_code:
                        continue

                    # Skip the terminal station itself (no departure)
                    if internal_code == dest_code and stop == stations[-1]:
                        continue

                    # Use actual departure > scheduled departure
                    time_str = stop.dep or stop.schDep
                    if not time_str:
                        continue

                    try:
                        # Amtrak times are ISO format with timezone offset
                        if "Z" in time_str:
                            time_str = time_str.replace("Z", "+00:00")
                        expected_time = datetime.fromisoformat(time_str)
                    except ValueError:
                        continue

                    # Ensure timezone-aware
                    if expected_time.tzinfo is None:
                        expected_time = expected_time.replace(tzinfo=timezone.utc)

                    now = datetime.now(timezone.utc)
                    minutes_away = max(0, int((expected_time - now).total_seconds() / 60))
                    platform = stop.platform if stop.platform else None

                    arrivals.append(
                        GroundTruthArrival(
                            station_code=internal_code,
                            destination_code=dest_code,
                            expected_time=expected_time,
                            line_color="",
                            headsign=headsign,
                            minutes_away=minutes_away,
                            train_id=str(train.trainNum),
                            track=platform,
                        )
                    )

        return arrivals

    return asyncio.run(_fetch())


# --- Fetch ground truth from GTFS-RT (LIRR / Metro-North) ---


def _fetch_gtfsrt_ground_truth(
    client_class: type,
    generate_train_id: Callable[[str], str] | None = None,
) -> list[GroundTruthArrival]:
    """Fetch ground truth departures from a GTFS-RT feed (shared by LIRR, MNR, Subway).

    Args:
        client_class: The GTFS-RT client class (LIRRClient or MNRClient).
        generate_train_id: Optional function to derive train_id from trip_id,
            enabling strong-signal matching against TrackRat.
    """
    arrivals: list[GroundTruthArrival] = []

    async def _fetch() -> list[GroundTruthArrival]:
        async with client_class() as client:
            all_arrivals = await client.get_all_arrivals()

        # SubwayClient returns (arrivals, succeeded_feeds) tuple
        if isinstance(all_arrivals, tuple):
            all_arrivals = all_arrivals[0]

        # Group by trip_id to find destination (last stop)
        trips: dict[str, list] = {}
        for arr in all_arrivals:
            trips.setdefault(arr.trip_id, []).append(arr)

        # Find destination for each trip (stop with latest arrival_time)
        trip_dest: dict[str, str] = {}
        for trip_id, stops in trips.items():
            last_stop = max(stops, key=lambda s: s.arrival_time)
            trip_dest[trip_id] = last_stop.station_code

        for arr in all_arrivals:
            dest_code = trip_dest.get(arr.trip_id)
            if not dest_code:
                continue

            # Skip terminal arrivals (no departure from terminal)
            if arr.station_code == dest_code and arr.departure_time is None:
                continue

            expected_time = arr.departure_time or arr.arrival_time
            now = datetime.now(timezone.utc)
            minutes_away = max(0, int((expected_time - now).total_seconds() / 60))

            # Derive train_id from trip_id using collector's logic
            train_id = ""
            if generate_train_id:
                try:
                    train_id = generate_train_id(arr.trip_id)
                except Exception:
                    pass  # Fall back to empty train_id

            arrivals.append(
                GroundTruthArrival(
                    station_code=arr.station_code,
                    destination_code=dest_code,
                    expected_time=expected_time,
                    line_color="",
                    headsign=arr.trip_id,
                    minutes_away=minutes_away,
                    train_id=train_id,
                    track=arr.track,
                    delay_seconds=arr.delay_seconds if arr.delay_seconds != 0 else None,
                )
            )

        return arrivals

    return asyncio.run(_fetch())


def fetch_lirr_ground_truth() -> list[GroundTruthArrival]:
    """Fetch ground truth departures from LIRR GTFS-RT feed."""
    from trackrat.collectors.lirr.client import LIRRClient
    from trackrat.collectors.lirr.collector import _generate_train_id as lirr_train_id

    return _fetch_gtfsrt_ground_truth(LIRRClient, generate_train_id=lirr_train_id)


def fetch_mnr_ground_truth() -> list[GroundTruthArrival]:
    """Fetch ground truth departures from Metro-North GTFS-RT feed."""
    from trackrat.collectors.mnr.client import MNRClient
    from trackrat.collectors.mnr.collector import _generate_train_id as mnr_train_id

    return _fetch_gtfsrt_ground_truth(MNRClient, generate_train_id=mnr_train_id)


def fetch_subway_ground_truth() -> list[GroundTruthArrival]:
    """Fetch ground truth departures from NYC Subway GTFS-RT feeds."""
    from trackrat.collectors.subway.client import SubwayClient

    return _fetch_gtfsrt_ground_truth(SubwayClient)


# --- Fetch TrackRat departures ---


def fetch_trackrat_departures(
    client: httpx.Client, base_url: str, origin: str, destination: str, data_source: str
) -> list[TrackRatDeparture]:
    """Fetch departures from TrackRat API for a specific origin->destination."""
    url = f"{base_url.rstrip('/')}/api/v2/trains/departures"
    params = {
        "from": origin,
        "to": destination,
        "limit": 50,
        "hide_departed": "false",
        "data_sources": data_source,
    }
    try:
        resp = client.get(url, params=params, timeout=15)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        log_fail(f"TrackRat API request failed ({origin}->{destination}): {e}")
        return []

    data = resp.json()
    departures: list[TrackRatDeparture] = []

    for dep in data.get("departures", []):
        dep_info = dep.get("departure", {})

        # Parse all three time tiers
        sched_str = dep_info.get("scheduled_time")
        upd_str = dep_info.get("updated_time")
        act_str = dep_info.get("actual_time")

        sched_dt = _safe_parse_iso(sched_str)
        upd_dt = _safe_parse_iso(upd_str)
        act_dt = _safe_parse_iso(act_str)

        # Best available: actual > updated > scheduled
        dep_time = act_dt or upd_dt or sched_dt
        if not dep_time:
            continue

        line = dep.get("line", {})
        # Resolve destination code from the arrival station info if available
        arrival = dep.get("arrival", {})
        dest_code = arrival.get("code", "") if arrival else ""
        dep_track = dep_info.get("track") or None

        departures.append(
            TrackRatDeparture(
                train_id=dep.get("train_id", ""),
                destination_code=dest_code,
                destination_name=dep.get("destination", ""),
                departure_time=dep_time,
                line_code=line.get("code", ""),
                line_color=line.get("color", ""),
                observation_type=dep.get("observation_type", ""),
                track=dep_track,
                is_cancelled=dep.get("is_cancelled", False),
                scheduled_time=sched_dt,
                updated_time=upd_dt,
                actual_time=act_dt,
            )
        )

    return departures


# --- Matching ---


def _safe_parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO datetime string, returning None on failure or empty input."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def format_delta(seconds: int) -> str:
    """Format seconds into a human-readable delta string."""
    abs_s = abs(seconds)
    if abs_s < 60:
        return f"{abs_s}s"
    minutes = abs_s // 60
    secs = abs_s % 60
    if secs == 0:
        return f"{minutes}m"
    return f"{minutes}m {secs}s"


def compare_route(
    gt_arrivals: list[GroundTruthArrival],
    tr_departures: list[TrackRatDeparture],
    origin: str,
    destination: str,
    tolerance_minutes: float,
) -> ComparisonResult:
    """Compare ground truth arrivals against TrackRat departures for one route direction."""
    route_name = f"{get_station_name(origin)} -> {get_station_name(destination)}"
    result = ComparisonResult(route_name=route_name, origin=origin, destination=destination)

    # Filter GT arrivals at this origin heading to this destination
    relevant_gt = [
        a for a in gt_arrivals if a.station_code == origin and a.destination_code == destination
    ]

    if not relevant_gt:
        return result  # caller handles empty case

    tolerance_secs = tolerance_minutes * 60
    used_tr_indices: set[int] = set()

    # Sort GT by expected time for greedy closest-first matching
    relevant_gt.sort(key=lambda a: a.expected_time)

    for gt in relevant_gt:
        best_idx: int | None = None
        best_delta = tolerance_secs + 1
        best_id_match = False

        for i, tr in enumerate(tr_departures):
            if i in used_tr_indices:
                continue
            delta = abs(int((tr.departure_time - gt.expected_time).total_seconds()))
            # Train ID match is a strong signal: prefer ID-matched candidates
            id_match = bool(gt.train_id and gt.train_id == tr.train_id)
            if delta <= tolerance_secs:
                # Prefer: (1) ID match over non-match, (2) smaller delta as tiebreaker
                if (id_match and not best_id_match) or (
                    id_match == best_id_match and delta < best_delta
                ):
                    best_delta = delta
                    best_idx = i
                    best_id_match = id_match

        if best_idx is not None and best_delta <= tolerance_secs:
            used_tr_indices.add(best_idx)
            matched_tr = tr_departures[best_idx]
            # Check track mismatch: only flag when both sides have a value
            track_mismatch = (
                bool(gt.track and matched_tr.track)
                and gt.track != matched_tr.track
            )
            # Check line color mismatch: only when both have non-empty values
            # Normalize: strip whitespace, lowercase, remove leading '#' (RidePATH
            # returns "D93A30" while TrackRat returns "#D93A30")
            # RidePATH may return comma-separated multi-colors ("4D92FB,FF9900");
            # match if TR color matches any of the GT colors
            tr_color_norm = matched_tr.line_color.lower().strip().lstrip("#") if matched_tr.line_color else ""
            gt_colors_norm = (
                [c.lower().strip().lstrip("#") for c in gt.line_color.split(",")]
                if gt.line_color else []
            )
            gt_colors_norm = [c for c in gt_colors_norm if c]  # drop empties
            line_color_mismatch = (
                bool(gt_colors_norm and tr_color_norm)
                and tr_color_norm not in gt_colors_norm
            )
            # Stale scheduled: train is OBSERVED but has no real-time update
            # (only scheduled_time, no updated_time or actual_time)
            stale_scheduled = (
                matched_tr.observation_type == "OBSERVED"
                and matched_tr.scheduled_time is not None
                and matched_tr.updated_time is None
                and matched_tr.actual_time is None
            )
            # Delay cross-validation (LIRR/MNR): compare GT delay_seconds
            # against TR's implied delay (best_time - scheduled_time)
            delay_mismatch_seconds: int | None = None
            if (
                gt.delay_seconds is not None
                and matched_tr.scheduled_time is not None
            ):
                tr_best = matched_tr.actual_time or matched_tr.updated_time
                if tr_best:
                    tr_implied_delay = int(
                        (tr_best - matched_tr.scheduled_time).total_seconds()
                    )
                    delay_mismatch_seconds = abs(gt.delay_seconds - tr_implied_delay)
            result.matches.append(
                MatchResult(
                    gt=gt, tr=matched_tr, delta_seconds=best_delta,
                    track_mismatch=track_mismatch,
                    line_color_mismatch=line_color_mismatch,
                    stale_scheduled=stale_scheduled,
                    delay_mismatch_seconds=delay_mismatch_seconds,
                )
            )
        elif gt.minutes_away == 0:
            result.arriving_unmatched.append(gt)
        else:
            result.missing.append(gt)

    # Unmatched TrackRat departures
    for i, tr in enumerate(tr_departures):
        if i not in used_tr_indices:
            if tr.is_cancelled:
                result.cancelled_in_tr.append(tr)
            else:
                result.phantoms.append(tr)

    return result


# --- Shared validation logic ---


def _deduplicated_route_directions(routes: list) -> list[tuple[str, str, str]]:
    """Build unique (origin, terminal, label) tuples from routes, avoiding duplicate station pairs."""
    seen: set[tuple[str, str]] = set()
    directions: list[tuple[str, str, str]] = []
    for route in routes:
        stations = list(route.stations)
        if len(stations) < 2:
            continue
        origin, terminal = stations[0], stations[-1]
        for from_st, to_st in [(origin, terminal), (terminal, origin)]:
            if (from_st, to_st) in seen:
                continue
            seen.add((from_st, to_st))
            from_name = get_station_name(from_st)
            to_name = get_station_name(to_st)
            label = f"{from_name} -> {to_name} ({from_st} -> {to_st})"
            directions.append((from_st, to_st, label))
    return directions


def print_summary(route_directions_tested: int) -> None:
    """Print pass/fail/warn/skip summary."""
    total = PASS_COUNT + FAIL_COUNT + WARN_COUNT + SKIP_COUNT
    print(f"\n{BOLD}========== SUMMARY =========={NC}")
    print(f"  {GREEN}PASS{NC}: {PASS_COUNT}")
    print(f"  {RED}FAIL{NC}: {FAIL_COUNT}")
    if WARN_COUNT > 0:
        print(f"  {YELLOW}WARN{NC}: {WARN_COUNT}")
    if SKIP_COUNT > 0:
        print(f"  {YELLOW}SKIP{NC}: {SKIP_COUNT}")
    print(f"  Total: {total} checks across {route_directions_tested} route directions")

    if FAIL_COUNT == 0:
        print(f"\n  {GREEN}{BOLD}ALL PASSED{NC}")
    else:
        print(f"\n  {RED}{BOLD}FAILED{NC} ({FAIL_COUNT} failure{'s' if FAIL_COUNT != 1 else ''})")


def run_validation_loop(
    gt_arrivals: list[GroundTruthArrival],
    data_source: str,
    base_url: str,
    tolerance: float,
    verbose: bool,
    gt_window_minutes: int = 120,
) -> int:
    """Iterate route directions, compare GT vs TrackRat, print results. Returns count of directions tested."""
    et = ZoneInfo("America/New_York")
    routes = get_routes_for_data_source(data_source)
    directions = _deduplicated_route_directions(routes)
    route_directions_tested = 0

    # Filter GT arrivals to a reasonable time window to avoid false FAILs
    # from far-future departures that TrackRat wouldn't return
    now_utc = datetime.now(timezone.utc)
    window_cutoff = now_utc + timedelta(minutes=gt_window_minutes)
    original_count = len(gt_arrivals)
    gt_arrivals = [a for a in gt_arrivals if a.expected_time <= window_cutoff]
    filtered_count = original_count - len(gt_arrivals)
    if filtered_count > 0 and verbose:
        print(f"  Note: Filtered {filtered_count} GT arrivals beyond {gt_window_minutes}-min window")

    client = httpx.Client()
    try:
        for from_st, to_st, label in directions:
            # Filter GT arrivals for this direction
            relevant_gt = [
                a for a in gt_arrivals if a.station_code == from_st and a.destination_code == to_st
            ]

            if not relevant_gt:
                print(f"\n{YELLOW}--- {label} ---{NC}")
                log_skip(f"No ground truth arrivals at {from_st} heading to {to_st}")
                route_directions_tested += 1
                continue

            # Fetch TrackRat departures
            tr_departures = fetch_trackrat_departures(client, base_url, from_st, to_st, data_source)

            print(f"\n{YELLOW}--- {label} ---{NC}")

            if verbose:
                print(f"  GT arrivals: {len(relevant_gt)}, TR departures: {len(tr_departures)}")
                for tr in sorted(tr_departures, key=lambda x: x.departure_time):
                    time_str = tr.departure_time.astimezone(et).strftime("%H:%M:%S")
                    track_str = f"  track={tr.track}" if tr.track else ""
                    cancel_str = "  CANCELLED" if tr.is_cancelled else ""
                    print(
                        f"    TR: {time_str}  {tr.train_id}  "
                        f"line={tr.line_code}  obs={tr.observation_type}{track_str}{cancel_str}"
                    )

            result = compare_route(gt_arrivals, tr_departures, from_st, to_st, tolerance)
            route_directions_tested += 1

            # Report matches
            for m in result.matches:
                time_str = m.gt.expected_time.astimezone(et).strftime("%H:%M")
                detail = ""
                if verbose:
                    tr_time = m.tr.departure_time.astimezone(et).strftime("%H:%M:%S")
                    detail = f" -> {m.tr.train_id} @ {tr_time} ({m.tr.observation_type})"
                track_info = ""
                if m.track_mismatch:
                    track_info = f" [TRACK MISMATCH: GT={m.gt.track} TR={m.tr.track}]"
                elif verbose and (m.gt.track or m.tr.track):
                    track_info = f" [track: GT={m.gt.track or '-'} TR={m.tr.track or '-'}]"
                line_info = ""
                if m.line_color_mismatch:
                    line_info = f" [LINE COLOR MISMATCH: GT={m.gt.line_color} TR={m.tr.line_color}]"
                elif verbose and (m.gt.line_color or m.tr.line_color):
                    line_info = f" [color: GT={m.gt.line_color or '-'} TR={m.tr.line_color or '-'}]"
                stale_info = ""
                if m.stale_scheduled:
                    stale_info = " [STALE: OBSERVED but only scheduled_time, no RT update]"
                delay_info = ""
                if m.delay_mismatch_seconds is not None and m.delay_mismatch_seconds > 60:
                    gt_delay = m.gt.delay_seconds or 0
                    tr_best = m.tr.actual_time or m.tr.updated_time
                    tr_implied = (
                        int((tr_best - m.tr.scheduled_time).total_seconds())
                        if tr_best and m.tr.scheduled_time
                        else 0
                    )
                    delay_info = (
                        f" [DELAY MISMATCH: GT={gt_delay}s TR={tr_implied}s"
                        f" diff={m.delay_mismatch_seconds}s]"
                    )
                elif verbose and m.delay_mismatch_seconds is not None:
                    gt_delay = m.gt.delay_seconds or 0
                    delay_info = f" [delay: GT={gt_delay}s diff={m.delay_mismatch_seconds}s]"
                time_tier_info = ""
                if verbose:
                    s = m.tr.scheduled_time.astimezone(et).strftime("%H:%M:%S") if m.tr.scheduled_time else "-"
                    u = m.tr.updated_time.astimezone(et).strftime("%H:%M:%S") if m.tr.updated_time else "-"
                    a = m.tr.actual_time.astimezone(et).strftime("%H:%M:%S") if m.tr.actual_time else "-"
                    time_tier_info = f" [sched={s} upd={u} act={a}]"
                has_mismatch = (
                    m.track_mismatch
                    or m.line_color_mismatch
                    or m.stale_scheduled
                    or (m.delay_mismatch_seconds is not None and m.delay_mismatch_seconds > 60)
                )
                suffix = (
                    f"{track_info}{line_info}{stale_info}"
                    f"{delay_info}{time_tier_info}"
                )
                if has_mismatch:
                    log_warn(
                        f'Train "{m.gt.headsign}" @ {time_str} matched '
                        f"({chr(0x394)} {format_delta(m.delta_seconds)}){detail}{suffix}"
                    )
                elif m.tr.is_cancelled:
                    log_warn(
                        f'Train "{m.gt.headsign}" @ {time_str} matched but CANCELLED in TrackRat'
                        f"{detail}{suffix}"
                    )
                else:
                    log_pass(
                        f'Train "{m.gt.headsign}" @ {time_str} matched '
                        f"({chr(0x394)} {format_delta(m.delta_seconds)}){detail}{suffix}"
                    )

            # Report arriving-but-unmatched (gray zone)
            for gt in result.arriving_unmatched:
                time_str = gt.expected_time.astimezone(et).strftime("%H:%M")
                log_warn(
                    f'Train "{gt.headsign}" @ {time_str} (arriving) not matched '
                    f"(may have already departed)"
                )

            # Report missing
            for gt in result.missing:
                time_str = gt.expected_time.astimezone(et).strftime("%H:%M")
                detail = ""
                if verbose and tr_departures:
                    nearest = min(
                        tr_departures,
                        key=lambda tr: abs((tr.departure_time - gt.expected_time).total_seconds()),
                    )
                    nearest_delta = int((nearest.departure_time - gt.expected_time).total_seconds())
                    nearest_time = nearest.departure_time.astimezone(et).strftime("%H:%M:%S")
                    detail = (
                        f"Nearest TR: {nearest.train_id} @ {nearest_time} "
                        f"({chr(0x394)} {format_delta(abs(nearest_delta))}, {nearest.observation_type})"
                    )
                log_fail(
                    f'Train "{gt.headsign}" @ {time_str} ({gt.minutes_away} min away) '
                    f"not found in TrackRat",
                    detail=detail,
                )

            # Report phantoms (only OBSERVED trains or those departing within a
            # reasonable window; SCHEDULED trains further out are expected noise)
            now_utc = datetime.now(timezone.utc)
            phantom_window = timedelta(minutes=35)
            for tr in result.phantoms:
                time_str = tr.departure_time.astimezone(et).strftime("%H:%M")
                is_near = abs((tr.departure_time - now_utc).total_seconds()) < phantom_window.total_seconds()
                if tr.observation_type == "OBSERVED" or is_near:
                    log_warn(f"TrackRat train {tr.train_id} @ {time_str} has no ground truth match")
                # Silently skip far-future SCHEDULED trains

            # Report cancelled trains that had no GT match
            for tr in result.cancelled_in_tr:
                time_str = tr.departure_time.astimezone(et).strftime("%H:%M")
                log_warn(f"TrackRat train {tr.train_id} @ {time_str} cancelled (no GT match expected)")
    finally:
        client.close()

    return route_directions_tested


def _print_header(provider: str, base_url: str, tolerance: float, gt_window: int = 120) -> None:
    """Print validation header."""
    et = ZoneInfo("America/New_York")
    now_et = datetime.now(et)
    print(f"\n{BOLD}Ground Truth Validation{NC}")
    print(f"Target: {base_url}")
    print(f"Provider: {provider}")
    tol_secs = tolerance * 60
    tol_str = f"{int(tol_secs)}s" if tolerance != int(tolerance) else f"{int(tolerance)} min"
    print(f"Tolerance: {tol_str}, Window: {gt_window} min")
    print(f"Time: {now_et.strftime('%Y-%m-%d %H:%M')} ET\n")


# --- Provider-specific runners ---


def run_path_validation(base_url: str, tolerance: float, verbose: bool = False, gt_window: int = 120) -> None:
    """Run ground truth validation for PATH."""
    _print_header("PATH", base_url, tolerance, gt_window)
    et = ZoneInfo("America/New_York")

    client = httpx.Client()
    try:
        # 1. Fetch ground truth
        gt_arrivals, oldest_updated = fetch_ridepath_arrivals(client)
        if not gt_arrivals:
            if FAIL_COUNT == 0:
                log_warn("No arrivals from RidePATH API (off-peak / late night?)")
            print(f"\nNote: Fetched 0 arrivals from RidePATH API")
            print_summary(0)
            return
        print(f"Note: Fetched {len(gt_arrivals)} arrivals from RidePATH API")

        if verbose:
            print(f"\n{BOLD}--- Ground Truth Arrivals ---{NC}")
            for a in sorted(gt_arrivals, key=lambda x: (x.station_code, x.expected_time)):
                time_str = a.expected_time.astimezone(et).strftime("%H:%M:%S")
                print(
                    f"  {a.station_code} -> {a.destination_code}  "
                    f'{time_str} ({a.minutes_away}min)  "{a.headsign}"  color={a.line_color}'
                )

        # Check staleness
        if oldest_updated:
            staleness = (datetime.now(timezone.utc) - oldest_updated.astimezone(timezone.utc)).total_seconds()
            if staleness > 120:
                log_warn(f"RidePATH data may be stale (oldest update: {int(staleness)}s ago)")
    finally:
        client.close()

    # 2. Validate against routes
    route_directions_tested = run_validation_loop(gt_arrivals, "PATH", base_url, tolerance, verbose, gt_window)
    print_summary(route_directions_tested)


def run_njt_validation(base_url: str, tolerance: float, verbose: bool = False, gt_window: int = 120) -> None:
    """Run ground truth validation for NJ Transit."""
    # Check for required env var
    token = os.environ.get("TRACKRAT_NJT_API_TOKEN") or os.environ.get("NJT_TOKEN")
    if not token:
        print(f"{YELLOW}WARN{NC} TRACKRAT_NJT_API_TOKEN / NJT_TOKEN not set, skipping NJT validation")
        return

    _print_header("NJT", base_url, tolerance, gt_window)
    et = ZoneInfo("America/New_York")

    gt_arrivals = fetch_njt_ground_truth()
    if not gt_arrivals:
        if FAIL_COUNT == 0:
            log_warn("No departures from NJ Transit API (off-peak / late night?)")
        print(f"\nNote: Fetched 0 departures from NJ Transit API")
        print_summary(0)
        return
    print(f"Note: Fetched {len(gt_arrivals)} departures from NJ Transit API across {len(DISCOVERY_STATIONS)} stations")

    if verbose:
        print(f"\n{BOLD}--- Ground Truth Departures ---{NC}")
        for a in sorted(gt_arrivals, key=lambda x: (x.station_code, x.expected_time)):
            time_str = a.expected_time.astimezone(et).strftime("%H:%M:%S")
            track_str = f"  track={a.track}" if a.track else ""
            print(
                f"  {a.station_code} -> {a.destination_code}  "
                f'{time_str} ({a.minutes_away}min)  "{a.headsign}"{track_str}'
            )

    route_directions_tested = run_validation_loop(gt_arrivals, "NJT", base_url, tolerance, verbose, gt_window)
    print_summary(route_directions_tested)


def run_amtrak_validation(base_url: str, tolerance: float, verbose: bool = False, gt_window: int = 120) -> None:
    """Run ground truth validation for Amtrak (NEC scope)."""
    _print_header("AMTRAK", base_url, tolerance, gt_window)
    et = ZoneInfo("America/New_York")

    gt_arrivals = fetch_amtrak_ground_truth()
    if not gt_arrivals:
        if FAIL_COUNT == 0:
            log_warn("No trains from Amtrak API")
        print(f"\nNote: Fetched 0 departures from Amtrak API")
        print_summary(0)
        return
    print(f"Note: Fetched {len(gt_arrivals)} departures from Amtrak API (NEC-mapped stations)")

    if verbose:
        print(f"\n{BOLD}--- Ground Truth Departures ---{NC}")
        for a in sorted(gt_arrivals, key=lambda x: (x.station_code, x.expected_time)):
            time_str = a.expected_time.astimezone(et).strftime("%H:%M:%S")
            track_str = f"  track={a.track}" if a.track else ""
            print(
                f"  {a.station_code} -> {a.destination_code}  "
                f'{time_str} ({a.minutes_away}min)  "{a.headsign}"{track_str}'
            )

    route_directions_tested = run_validation_loop(gt_arrivals, "AMTRAK", base_url, tolerance, verbose, gt_window)
    print_summary(route_directions_tested)


def run_lirr_validation(base_url: str, tolerance: float, verbose: bool = False, gt_window: int = 120) -> None:
    """Run ground truth validation for LIRR."""
    _print_header("LIRR", base_url, tolerance, gt_window)
    et = ZoneInfo("America/New_York")

    gt_arrivals = fetch_lirr_ground_truth()
    if not gt_arrivals:
        if FAIL_COUNT == 0:
            log_warn("No arrivals from LIRR GTFS-RT feed")
        print(f"\nNote: Fetched 0 departures from LIRR GTFS-RT")
        print_summary(0)
        return
    print(f"Note: Fetched {len(gt_arrivals)} departures from LIRR GTFS-RT")

    if verbose:
        print(f"\n{BOLD}--- Ground Truth Departures ---{NC}")
        for a in sorted(gt_arrivals, key=lambda x: (x.station_code, x.expected_time)):
            time_str = a.expected_time.astimezone(et).strftime("%H:%M:%S")
            track_str = f"  track={a.track}" if a.track else ""
            id_str = f"  id={a.train_id}" if a.train_id else ""
            delay_str = f"  delay={a.delay_seconds}s" if a.delay_seconds else ""
            print(
                f"  {a.station_code} -> {a.destination_code}  "
                f'{time_str} ({a.minutes_away}min)  "{a.headsign}"{id_str}{track_str}{delay_str}'
            )

    route_directions_tested = run_validation_loop(gt_arrivals, "LIRR", base_url, tolerance, verbose, gt_window)
    print_summary(route_directions_tested)


def run_mnr_validation(base_url: str, tolerance: float, verbose: bool = False, gt_window: int = 120) -> None:
    """Run ground truth validation for Metro-North."""
    _print_header("MNR", base_url, tolerance, gt_window)
    et = ZoneInfo("America/New_York")

    gt_arrivals = fetch_mnr_ground_truth()
    if not gt_arrivals:
        if FAIL_COUNT == 0:
            log_warn("No arrivals from Metro-North GTFS-RT feed")
        print(f"\nNote: Fetched 0 departures from MNR GTFS-RT")
        print_summary(0)
        return
    print(f"Note: Fetched {len(gt_arrivals)} departures from MNR GTFS-RT")

    if verbose:
        print(f"\n{BOLD}--- Ground Truth Departures ---{NC}")
        for a in sorted(gt_arrivals, key=lambda x: (x.station_code, x.expected_time)):
            time_str = a.expected_time.astimezone(et).strftime("%H:%M:%S")
            track_str = f"  track={a.track}" if a.track else ""
            id_str = f"  id={a.train_id}" if a.train_id else ""
            delay_str = f"  delay={a.delay_seconds}s" if a.delay_seconds else ""
            print(
                f"  {a.station_code} -> {a.destination_code}  "
                f'{time_str} ({a.minutes_away}min)  "{a.headsign}"{id_str}{track_str}{delay_str}'
            )

    route_directions_tested = run_validation_loop(gt_arrivals, "MNR", base_url, tolerance, verbose, gt_window)
    print_summary(route_directions_tested)


def run_subway_validation(base_url: str, tolerance: float, verbose: bool = False, gt_window: int = 120) -> None:
    """Run ground truth validation for NYC Subway."""
    _print_header("SUBWAY", base_url, tolerance, gt_window)
    et = ZoneInfo("America/New_York")

    gt_arrivals = fetch_subway_ground_truth()
    if not gt_arrivals:
        if FAIL_COUNT == 0:
            log_warn("No arrivals from Subway GTFS-RT feeds")
        print(f"\nNote: Fetched 0 departures from Subway GTFS-RT")
        print_summary(0)
        return
    print(f"Note: Fetched {len(gt_arrivals)} departures from Subway GTFS-RT")

    if verbose:
        print(f"\n{BOLD}--- Ground Truth Departures ---{NC}")
        for a in sorted(gt_arrivals, key=lambda x: (x.station_code, x.expected_time)):
            time_str = a.expected_time.astimezone(et).strftime("%H:%M:%S")
            print(
                f"  {a.station_code} -> {a.destination_code}  "
                f'{time_str} ({a.minutes_away}min)  "{a.headsign}"'
            )

    route_directions_tested = run_validation_loop(gt_arrivals, "SUBWAY", base_url, tolerance, verbose, gt_window)
    print_summary(route_directions_tested)


# --- Main ---


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate TrackRat departures against raw transit provider data."
    )
    parser.add_argument(
        "base_url",
        nargs="?",
        default="https://staging.apiv2.trackrat.net",
        help="TrackRat API base URL (default: staging)",
    )
    parser.add_argument(
        "--provider",
        default="PATH",
        choices=["PATH", "NJT", "AMTRAK", "LIRR", "MNR", "SUBWAY"],
        help="Transit provider to validate (default: PATH)",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1.5,
        help="Matching tolerance in minutes (default: 1.5)",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=120,
        help="GT time window in minutes; ignore GT departures beyond this (default: 120)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show raw GT arrivals, TR departures, and nearest-match details on FAILs",
    )
    args = parser.parse_args()

    runners = {
        "PATH": run_path_validation,
        "NJT": run_njt_validation,
        "AMTRAK": run_amtrak_validation,
        "LIRR": run_lirr_validation,
        "MNR": run_mnr_validation,
        "SUBWAY": run_subway_validation,
    }

    runner = runners.get(args.provider)
    if runner:
        runner(args.base_url, args.tolerance, verbose=args.verbose, gt_window=args.window)
    else:
        print(f"{RED}FAIL{NC} Unsupported provider: {args.provider}")
        sys.exit(1)

    sys.exit(1 if FAIL_COUNT > 0 else 0)


if __name__ == "__main__":
    main()
