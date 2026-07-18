#!/usr/bin/env python3
"""Generate SEPTA station & route config modules from the SEPTA GTFS static feeds.

SEPTA publishes two GTFS bundles inside ``gtfs_public.zip``:
  * ``google_rail.zip`` — Regional Rail (13 lines, route_type 2)
  * ``google_bus.zip``  — everything else; the Metro network is the subset with
                          route_type 0 (trolley/light-rail) and 1 (subway/metro)

This script parses those feeds and writes two backend config modules:
  * ``config/stations/septa_rr.py``    (data_source "SEPTA_RR")
  * ``config/stations/septa_metro.py`` (data_source "SEPTA_METRO")

Internal station codes are prefixed to stay globally unique across every
TrackRat provider (SEPTA's raw GTFS stop_ids are plain numbers that collide with
existing subway/WMATA codes): ``SEPR`` + stop_id for Regional Rail, ``SEPM`` + a
per-station id for Metro. Metro heavy-rail (subway) platforms are grouped into
one station per name (each station has a directional stop_id per direction);
trolley curb stops stay 1:1.

Usage:
    # Uses a pre-extracted feed dir (rail/ and bus/ subdirs), or downloads:
    python3 scripts/generate_septa_data.py [--gtfs-dir DIR] [--output-dir DIR]

Re-run to refresh the data when SEPTA publishes feed changes.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import urllib.request
import zipfile
from collections import defaultdict

GTFS_PUBLIC_URL = "https://www3.septa.org/developer/gtfs_public.zip"

# Regional Rail: all lines share SEPTA's regional-rail blue in GTFS; keep it.
RR_FEED_TRIP_URL = "https://www3.septa.org/gtfsrt/septarail-pa-us/Trip/rtTripUpdates.pb"
RR_FEED_POS_URL = "https://www3.septa.org/gtfsrt/septarail-pa-us/Vehicle/rtVehiclePosition.pb"
RR_FEED_ALERT_URL = "https://www3.septa.org/gtfsrt/septarail-pa-us/Service/rtServiceAlerts.pb"
RR_STATIC_URL = "https://www3.septa.org/developer/google_rail.zip"

METRO_FEED_TRIP_URL = "https://www3.septa.org/gtfsrt/septa-pa-us/Trip/rtTripUpdates.pb"
METRO_FEED_POS_URL = "https://www3.septa.org/gtfsrt/septa-pa-us/Vehicle/rtVehiclePosition.pb"
METRO_FEED_ALERT_URL = "https://www3.septa.org/gtfsrt/septa-pa-us/Service/rtServiceAlerts.pb"
METRO_STATIC_URL = "https://www3.septa.org/developer/google_bus.zip"

# GTFS route_type -> True if part of the Metro rail network we ingest.
METRO_ROUTE_TYPES = {"0", "1"}  # 0 = trolley/light-rail, 1 = subway/metro


def _read_csv(path: str) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _load_feed(gtfs_dir: str, sub: str) -> dict[str, list[dict[str, str]]]:
    """Load the txt tables we need from an extracted GTFS feed subdir."""
    base = os.path.join(gtfs_dir, sub)
    return {
        name: _read_csv(os.path.join(base, f"{name}.txt"))
        for name in ("stops", "routes", "trips", "stop_times", "route_stops")
        if os.path.exists(os.path.join(base, f"{name}.txt"))
    }


def _ensure_feeds(gtfs_dir: str) -> None:
    """Download + extract gtfs_public.zip into gtfs_dir/{rail,bus} if absent."""
    if os.path.exists(os.path.join(gtfs_dir, "rail", "stops.txt")):
        return
    os.makedirs(gtfs_dir, exist_ok=True)
    print(f"Downloading {GTFS_PUBLIC_URL} ...")
    with urllib.request.urlopen(GTFS_PUBLIC_URL) as resp:  # noqa: S310
        outer = zipfile.ZipFile(io.BytesIO(resp.read()))
    for member, sub in (("google_rail.zip", "rail"), ("google_bus.zip", "bus")):
        inner = zipfile.ZipFile(io.BytesIO(outer.read(member)))
        inner.extractall(os.path.join(gtfs_dir, sub))


def _py_dict(items: list[tuple[str, str]], value_is_code: bool = False) -> str:
    """Render ``{"k": "v", ...}`` lines (one per line), values are strings."""
    return "\n".join(f'    "{k}": "{v}",' for k, v in items)


def _fmt_coords(code: str, lat: float, lon: float, name: str) -> str:
    return f'    "{code}": {{"lat": {lat}, "lon": {lon}}},  # {name}'


# --------------------------------------------------------------------------- #
# Regional Rail
# --------------------------------------------------------------------------- #
def generate_regional_rail(gtfs_dir: str, output_dir: str) -> None:
    feed = _load_feed(gtfs_dir, "rail")
    stops = {s["stop_id"]: s for s in feed["stops"]}
    routes = feed["routes"]
    route_stops = feed.get("route_stops", [])

    def code(stop_id: str) -> str:
        return f"SEPR{stop_id}"

    # Station names + coordinates (156 single stops, one per station)
    names = sorted(stops.values(), key=lambda s: s["stop_name"])
    station_names = [(code(s["stop_id"]), s["stop_name"]) for s in names]
    gtfs_map = [(s["stop_id"], code(s["stop_id"])) for s in names]
    coords = [
        _fmt_coords(code(s["stop_id"]), float(s["stop_lat"]), float(s["stop_lon"]), s["stop_name"])
        for s in names
    ]

    # Routes: route_id -> (line_code, long_name, "#color")
    route_rows = sorted(routes, key=lambda r: r["route_id"])
    route_lines = []
    for r in route_rows:
        color = r.get("route_color") or "4F758B"
        route_lines.append(
            f'    "{r["route_id"]}": ("SEPTA-{r["route_id"]}", "{r["route_long_name"]}", "#{color}"),'
        )

    # Ordered station sequences per line from route_stops.txt (direction 0).
    seqs: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for rs in route_stops:
        if rs["direction_id"] == "0":
            seqs[rs["route_id"]].append((int(rs["route_stop_sort_order"]), rs["stop_id"]))
    route_stations_lines = []
    for route_id in sorted(seqs):
        ordered = [code(sid) for _, sid in sorted(seqs[route_id])]
        joined = "\n".join(f'        "{c}",' for c in ordered)
        route_stations_lines.append(f'    "{route_id}": (\n{joined}\n    ),')

    # Discovery hubs: Center City through-stations (match by name substring).
    hub_substrings = ("30th St", "Suburban", "Jefferson", "Temple U", "Gray 30th")
    discovery = [
        code(s["stop_id"])
        for s in names
        if any(h in s["stop_name"] for h in hub_substrings)
    ]

    module = f'''"""SEPTA Regional Rail station configuration.

Auto-generated by ``scripts/generate_septa_data.py`` from the SEPTA GTFS static
feed (``google_rail.zip``). Do not edit by hand — re-run the generator to
refresh. Internal station codes are the GTFS stop_id prefixed with ``SEPR`` to
stay unique across every TrackRat provider.
"""

# GTFS-RT feeds (public, no authentication). Regional Rail's TripUpdates feed is
# delay-based: each stop_time_update carries a `delay` (seconds) keyed by
# stop_sequence, not an absolute time — the collector joins the static schedule.
SEPTA_RR_GTFS_RT_FEED_URL = "{RR_FEED_TRIP_URL}"
SEPTA_RR_POSITIONS_FEED_URL = "{RR_FEED_POS_URL}"
SEPTA_RR_ALERTS_FEED_URL = "{RR_FEED_ALERT_URL}"
SEPTA_RR_GTFS_FEED_URL = "{RR_STATIC_URL}"


# Internal code -> display name
SEPTA_RR_STATION_NAMES: dict[str, str] = {{
{_py_dict(station_names)}
}}


# GTFS stop_id -> internal code (used by the GTFS static loader; the RT feed
# carries no stop_id, so times are joined to static by (trip_id, stop_sequence)).
SEPTA_RR_GTFS_STOP_TO_INTERNAL_MAP: dict[str, str] = {{
{_py_dict(gtfs_map, value_is_code=True)}
}}

INTERNAL_TO_SEPTA_RR_GTFS_STOP_MAP: dict[str, str] = {{
    v: k for k, v in SEPTA_RR_GTFS_STOP_TO_INTERNAL_MAP.items()
}}


# GTFS route_id -> (line_code, display name, color)
SEPTA_RR_ROUTES: dict[str, tuple[str, str, str]] = {{
{chr(10).join(route_lines)}
}}


# Ordered station sequences per line (direction_id=0), from route_stops.txt.
SEPTA_RR_ROUTE_STATIONS: dict[str, tuple[str, ...]] = {{
{chr(10).join(route_stations_lines)}
}}


# Center City through-stations — coverage-validation hubs.
SEPTA_RR_DISCOVERY_STATIONS = {discovery!r}


# Station coordinates for map visualization
SEPTA_RR_STATION_COORDINATES: dict[str, dict[str, float]] = {{
{chr(10).join(coords)}
}}


def get_septa_rr_route_info(gtfs_route_id: str) -> tuple[str, str, str] | None:
    """Get SEPTA Regional Rail route info from a GTFS route_id (e.g. "AIR")."""
    return SEPTA_RR_ROUTES.get(gtfs_route_id)


def map_septa_rr_gtfs_stop(gtfs_stop_id: str) -> str | None:
    """Map a SEPTA Regional Rail GTFS stop_id to our internal station code."""
    return SEPTA_RR_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_stop_id)
'''
    out = os.path.join(output_dir, "septa_rr.py")
    with open(out, "w", encoding="utf-8") as f:
        f.write(module)
    print(f"Wrote {out}: {len(station_names)} stations, {len(route_rows)} lines, "
          f"{len(discovery)} discovery hubs")


# --------------------------------------------------------------------------- #
# Metro (subway + trolley)
# --------------------------------------------------------------------------- #
def generate_metro(gtfs_dir: str, output_dir: str) -> None:
    feed = _load_feed(gtfs_dir, "bus")
    stops = {s["stop_id"]: s for s in feed["stops"]}
    routes = {r["route_id"]: r for r in feed["routes"]}
    trips = feed["trips"]
    stop_times = feed["stop_times"]
    route_stops = feed.get("route_stops", [])

    # Metro routes = route_type 0 (trolley) or 1 (subway).
    metro_routes = {rid: r for rid, r in routes.items() if r["route_type"] in METRO_ROUTE_TYPES}
    heavy_route_ids = {rid for rid, r in metro_routes.items() if r["route_type"] == "1"}

    trip_route = {t["trip_id"]: t["route_id"] for t in trips if t["route_id"] in metro_routes}
    # Which stops each route class uses.
    heavy_stop_ids: set[str] = set()
    trolley_stop_ids: set[str] = set()
    for st in stop_times:
        rid = trip_route.get(st["trip_id"])
        if rid is None:
            continue
        (heavy_stop_ids if rid in heavy_route_ids else trolley_stop_ids).add(st["stop_id"])
    # A stop shared with a subway route is grouped as heavy-rail.
    trolley_stop_ids -= heavy_stop_ids

    # Heavy-rail: group directional platforms sharing a name into one station.
    by_name: dict[str, list[str]] = defaultdict(list)
    for sid in heavy_stop_ids:
        by_name[stops[sid]["stop_name"]].append(sid)
    stop_to_code: dict[str, str] = {}
    station_names: dict[str, str] = {}
    station_coords: dict[str, tuple[float, float]] = {}
    for name, sids in by_name.items():
        code = "SEPM" + min(sids, key=int)  # stable representative id
        for sid in sids:
            stop_to_code[sid] = code
        station_names[code] = name
        lat = sum(float(stops[s]["stop_lat"]) for s in sids) / len(sids)
        lon = sum(float(stops[s]["stop_lon"]) for s in sids) / len(sids)
        station_coords[code] = (round(lat, 6), round(lon, 6))

    # Trolley: each curb stop is its own station (1:1).
    for sid in trolley_stop_ids:
        code = "SEPM" + sid
        stop_to_code[sid] = code
        station_names[code] = stops[sid]["stop_name"]
        station_coords[code] = (float(stops[sid]["stop_lat"]), float(stops[sid]["stop_lon"]))

    # Ordered station sequences per route from route_stops.txt (direction 0),
    # collapsing consecutive duplicates produced by platform grouping.
    seqs: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for rs in route_stops:
        if rs["route_id"] in metro_routes and rs["direction_id"] == "0":
            sid = rs["stop_id"]
            if sid in stop_to_code:
                seqs[rs["route_id"]].append((int(rs["route_stop_sort_order"]), sid))
    route_stations: dict[str, list[str]] = {}
    for rid, pairs in seqs.items():
        ordered: list[str] = []
        for _, sid in sorted(pairs):
            c = stop_to_code[sid]
            if not ordered or ordered[-1] != c:
                ordered.append(c)
        route_stations[rid] = ordered

    # Render sections.
    names_sorted = sorted(station_names.items(), key=lambda kv: kv[1])
    names_block = _py_dict(names_sorted)
    gtfs_map_block = "\n".join(
        f'    "{sid}": "{stop_to_code[sid]}",' for sid in sorted(stop_to_code)
    )
    coords_block = "\n".join(
        _fmt_coords(c, station_coords[c][0], station_coords[c][1], station_names[c])
        for c, _ in names_sorted
    )
    route_lines = []
    for rid in sorted(metro_routes):
        r = metro_routes[rid]
        color = r.get("route_color") or "999999"
        kind = "subway" if rid in heavy_route_ids else "trolley"
        route_lines.append(
            f'    "{rid}": ("SEPTA-{rid}", "{r["route_long_name"]}", "#{color}"),  # {kind}'
        )
    route_stations_lines = []
    for rid in sorted(route_stations):
        joined = "\n".join(f'        "{c}",' for c in route_stations[rid])
        route_stations_lines.append(f'    "{rid}": (\n{joined}\n    ),')

    # Lines with no real-time trip updates from SEPTA today (schedule-only).
    schedule_only = sorted(r for r in metro_routes if r.startswith(("B", "L")))

    module = f'''"""SEPTA Metro (subway + trolley) station configuration.

Auto-generated by ``scripts/generate_septa_data.py`` from the SEPTA GTFS static
feed (``google_bus.zip``, route_type 0 trolley + 1 subway). Do not edit by hand —
re-run the generator to refresh.

Internal station codes are prefixed ``SEPM`` to stay unique across every
TrackRat provider. Subway stations group their directional platforms into one
code; each trolley curb stop is its own station.
"""

# GTFS-RT feeds (public, no authentication). One combined feed covers the whole
# Metro network; the collector filters to the SEPTA_METRO_ROUTES below.
SEPTA_METRO_GTFS_RT_FEED_URL = "{METRO_FEED_TRIP_URL}"
SEPTA_METRO_POSITIONS_FEED_URL = "{METRO_FEED_POS_URL}"
SEPTA_METRO_ALERTS_FEED_URL = "{METRO_FEED_ALERT_URL}"
SEPTA_METRO_GTFS_FEED_URL = "{METRO_STATIC_URL}"


# Internal code -> display name
SEPTA_METRO_STATION_NAMES: dict[str, str] = {{
{names_block}
}}


# GTFS stop_id -> internal code (many-to-one for grouped subway platforms).
SEPTA_METRO_GTFS_STOP_TO_INTERNAL_MAP: dict[str, str] = {{
{gtfs_map_block}
}}

INTERNAL_TO_SEPTA_METRO_GTFS_STOP_MAP: dict[str, str] = {{
    v: k for k, v in SEPTA_METRO_GTFS_STOP_TO_INTERNAL_MAP.items()
}}


# GTFS route_id -> (line_code, display name, color)
SEPTA_METRO_ROUTES: dict[str, tuple[str, str, str]] = {{
{chr(10).join(route_lines)}
}}


# Route_ids for which SEPTA publishes no real-time trip updates today. These are
# served schedule-only (like PATCO); the collector still upgrades any line SEPTA
# starts feeding, with no config change required.
SEPTA_METRO_SCHEDULE_ONLY_ROUTES: frozenset[str] = frozenset({schedule_only!r})


# Ordered station sequences per route (direction_id=0), from route_stops.txt.
SEPTA_METRO_ROUTE_STATIONS: dict[str, tuple[str, ...]] = {{
{chr(10).join(route_stations_lines)}
}}


# Station coordinates for map visualization
SEPTA_METRO_STATION_COORDINATES: dict[str, dict[str, float]] = {{
{coords_block}
}}


def get_septa_metro_route_info(gtfs_route_id: str) -> tuple[str, str, str] | None:
    """Get SEPTA Metro route info from a GTFS route_id (e.g. "B1", "L1", "T3")."""
    return SEPTA_METRO_ROUTES.get(gtfs_route_id)


def map_septa_metro_gtfs_stop(gtfs_stop_id: str) -> str | None:
    """Map a SEPTA Metro GTFS stop_id to our internal station code."""
    return SEPTA_METRO_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_stop_id)
'''
    out = os.path.join(output_dir, "septa_metro.py")
    with open(out, "w", encoding="utf-8") as f:
        f.write(module)
    print(f"Wrote {out}: {len(station_names)} stations "
          f"({len(by_name)} subway, {len(trolley_stop_ids)} trolley), "
          f"{len(metro_routes)} routes, schedule-only={schedule_only}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gtfs-dir", default="/tmp/septa_gtfs",
                    help="Dir with extracted rail/ and bus/ GTFS feeds (downloaded if absent)")
    ap.add_argument("--output-dir",
                    default=os.path.join(os.path.dirname(__file__), "..", "backend_v2",
                                         "src", "trackrat", "config", "stations"),
                    help="Where to write the generated config modules")
    ap.add_argument("--only", choices=["rr", "metro"], help="Generate only one module")
    args = ap.parse_args()

    _ensure_feeds(args.gtfs_dir)
    output_dir = os.path.abspath(args.output_dir)

    if args.only in (None, "rr"):
        generate_regional_rail(args.gtfs_dir, output_dir)
    if args.only in (None, "metro"):
        generate_metro(args.gtfs_dir, output_dir)


if __name__ == "__main__":
    main()
