#!/usr/bin/env python3
"""Ground truth validation: compare TrackRat departures against raw transit provider data.

Run from the repo root using the backend poetry environment:
    cd backend_v2 && poetry run python3 ../scripts/ground-truth-validate.py [base_url] [--provider PATH] [--tolerance 5]
"""

import argparse
import sys
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx

# Add backend src to path so trackrat package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend_v2", "src"))

from trackrat.collectors.path.collector import (  # noqa: E402
    _get_destination_station_from_headsign,
    _get_line_info_from_headsign,
)
from trackrat.collectors.path.ridepath_client import RIDEPATH_API_URL  # noqa: E402
from trackrat.config.route_topology import get_routes_for_data_source  # noqa: E402
from trackrat.config.stations import (  # noqa: E402
    PATH_RIDEPATH_API_TO_INTERNAL_MAP,
    get_station_name,
)

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


@dataclass
class TrackRatDeparture:
    train_id: str
    destination_code: str
    destination_name: str
    departure_time: datetime
    line_code: str
    line_color: str
    observation_type: str


@dataclass
class MatchResult:
    gt: GroundTruthArrival
    tr: TrackRatDeparture
    delta_seconds: int


@dataclass
class ComparisonResult:
    route_name: str
    origin: str
    destination: str
    matches: list[MatchResult] = field(default_factory=list)
    missing: list[GroundTruthArrival] = field(default_factory=list)
    phantoms: list[TrackRatDeparture] = field(default_factory=list)
    arriving_unmatched: list[GroundTruthArrival] = field(default_factory=list)


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
                expected_time = now + timedelta(minutes=minutes)

                # Track staleness
                last_updated_str = msg.get("lastUpdated")
                if last_updated_str:
                    try:
                        lu = datetime.fromisoformat(last_updated_str)
                        if oldest_updated is None or lu < oldest_updated:
                            oldest_updated = lu
                    except ValueError:
                        pass

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


# --- Fetch TrackRat departures ---


def fetch_trackrat_departures(
    client: httpx.Client, base_url: str, origin: str, destination: str
) -> list[TrackRatDeparture]:
    """Fetch departures from TrackRat API for a specific origin->destination."""
    url = f"{base_url.rstrip('/')}/api/v2/trains/departures"
    params = {
        "from": origin,
        "to": destination,
        "limit": 50,
        "hide_departed": "false",
        "data_sources": "PATH",
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
        scheduled = dep_info.get("actual_time") or dep_info.get("updated_time") or dep_info.get("scheduled_time")
        if not scheduled:
            continue

        try:
            dep_time = datetime.fromisoformat(scheduled)
        except ValueError:
            continue

        line = dep.get("line", {})
        # Resolve destination code from the arrival station info if available
        arrival = dep.get("arrival", {})
        dest_code = arrival.get("code", "") if arrival else ""

        departures.append(
            TrackRatDeparture(
                train_id=dep.get("train_id", ""),
                destination_code=dest_code,
                destination_name=dep.get("destination", ""),
                departure_time=dep_time,
                line_code=line.get("code", ""),
                line_color=line.get("color", ""),
                observation_type=dep.get("observation_type", ""),
            )
        )

    return departures


# --- Matching ---


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
    tolerance_minutes: int,
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

        for i, tr in enumerate(tr_departures):
            if i in used_tr_indices:
                continue
            delta = abs(int((tr.departure_time - gt.expected_time).total_seconds()))
            if delta < best_delta:
                best_delta = delta
                best_idx = i

        if best_idx is not None and best_delta <= tolerance_secs:
            used_tr_indices.add(best_idx)
            result.matches.append(
                MatchResult(gt=gt, tr=tr_departures[best_idx], delta_seconds=best_delta)
            )
        elif gt.minutes_away == 0:
            result.arriving_unmatched.append(gt)
        else:
            result.missing.append(gt)

    # Unmatched TrackRat departures = phantoms
    for i, tr in enumerate(tr_departures):
        if i not in used_tr_indices:
            result.phantoms.append(tr)

    return result


# --- Main ---


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


def run_path_validation(base_url: str, tolerance: int, verbose: bool = False) -> None:
    """Run ground truth validation for PATH."""
    et = timezone(timedelta(hours=-5))
    now_et = datetime.now(et)
    print(f"\n{BOLD}Ground Truth Validation{NC}")
    print(f"Target: {base_url}")
    print(f"Provider: PATH")
    print(f"Tolerance: {tolerance} min")
    print(f"Time: {now_et.strftime('%Y-%m-%d %H:%M')} ET\n")

    client = httpx.Client()
    try:
        # 1. Fetch ground truth
        gt_arrivals, oldest_updated = fetch_ridepath_arrivals(client)
        if not gt_arrivals:
            if FAIL_COUNT == 0:
                # API didn't fail, just no trains
                log_warn("No arrivals from RidePATH API (off-peak / late night?)")
            print(f"\nNote: Fetched 0 arrivals from RidePATH API")
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

        # 2. Get PATH routes and test each direction (deduplicated)
        routes = get_routes_for_data_source("PATH")
        directions = _deduplicated_route_directions(routes)
        route_directions_tested = 0

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
            tr_departures = fetch_trackrat_departures(client, base_url, from_st, to_st)

            print(f"\n{YELLOW}--- {label} ---{NC}")

            if verbose:
                print(f"  GT arrivals: {len(relevant_gt)}, TR departures: {len(tr_departures)}")
                for tr in sorted(tr_departures, key=lambda x: x.departure_time):
                    time_str = tr.departure_time.astimezone(et).strftime("%H:%M:%S")
                    print(
                        f"    TR: {time_str}  {tr.train_id}  "
                        f"line={tr.line_code}  obs={tr.observation_type}"
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
                log_pass(
                    f'Train "{m.gt.headsign}" @ {time_str} matched '
                    f"({chr(0x394)} {format_delta(m.delta_seconds)}){detail}"
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
                # In verbose mode, show nearest TrackRat departure for debugging
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

            # Report phantoms (only OBSERVED trains or those departing within the
            # RidePATH window ~30min; SCHEDULED trains further out are expected noise)
            now_utc = datetime.now(timezone.utc)
            phantom_window = timedelta(minutes=35)
            for tr in result.phantoms:
                time_str = tr.departure_time.astimezone(et).strftime("%H:%M")
                is_near = abs((tr.departure_time - now_utc).total_seconds()) < phantom_window.total_seconds()
                if tr.observation_type == "OBSERVED" or is_near:
                    log_warn(f"TrackRat train {tr.train_id} @ {time_str} has no ground truth match")
                # Silently skip far-future SCHEDULED trains

    finally:
        client.close()

    # Summary
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
        choices=["PATH"],
        help="Transit provider to validate (default: PATH)",
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=3,
        help="Matching tolerance in minutes (default: 3)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show raw GT arrivals, TR departures, and nearest-match details on FAILs",
    )
    args = parser.parse_args()

    if args.provider == "PATH":
        run_path_validation(args.base_url, args.tolerance, verbose=args.verbose)
    else:
        print(f"{RED}FAIL{NC} Unsupported provider: {args.provider}")
        sys.exit(1)

    sys.exit(1 if FAIL_COUNT > 0 else 0)


if __name__ == "__main__":
    main()
