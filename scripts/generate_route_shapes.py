#!/usr/bin/env python3
"""
Generate route shape coordinates from GTFS shapes.txt for iOS map rendering.

Downloads GTFS feeds for all transit providers, extracts shapes.txt, maps shape
points to station-pair segments, simplifies with Douglas-Peucker, and generates
a Swift file with embedded coordinate arrays.

Segments come from two passes per provider:
1. Trip pass: consecutive mapped-stop pairs of sampled rail trips (bus trips
   like Amtrak Thruway are excluded via route_type). This yields the
   journey-granularity keys the congestion API returns.
2. Topology pass: adjacent station pairs from backend route_topology AND iOS
   RouteTopology.swift that the trip pass missed (coarse express hops like
   OMA-DEN that no trip serves as consecutive stops) are sliced out of full
   trip shapes, so the iOS route base layer follows real track too.

Usage:
    cd backend_v2
    poetry run python3 ../scripts/generate_route_shapes.py [--output-dir /tmp/route_shapes]
    # Review output, then copy RouteShapes.swift into ios/TrackRat/Shared/

Output: RouteShapes.swift containing a dictionary mapping "fromStation-toStation"
keys to arrays of intermediate [lat, lon] points for drawing polylines.
"""

import argparse
import csv
import io
import math
import os
import re
import urllib.request
import zipfile
from collections import defaultdict
from dataclasses import dataclass

# GTFS feed URLs (mirrors backend_v2/src/trackrat/services/gtfs.py)
GTFS_FEEDS = {
    "NJT": "https://content.njtransit.com/public/developers-resources/rail_data.zip",
    "AMTRAK": "https://content.amtrak.com/content/gtfs/GTFS.zip",
    "PATH": "http://data.trilliumtransit.com/gtfs/path-nj-us/path-nj-us.zip",
    "PATCO": "https://rapid.nationalrtap.org/GTFSFileManagement/UserUploadFiles/13562/PATCO_GTFS.zip",
    "LIRR": "https://rrgtfsfeeds.s3.amazonaws.com/gtfslirr.zip",
    "MNR": "https://rrgtfsfeeds.s3.amazonaws.com/gtfsmnr.zip",
    "SUBWAY": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_supplemented.zip",
    "SEPTA_RR": "https://www3.septa.org/developer/google_rail.zip",
    "SEPTA_METRO": "https://www3.septa.org/developer/google_bus.zip",
}

# GTFS route_type values we extract shapes for: 0 = tram/trolley, 1 = subway,
# 2 = rail. Excludes buses (3) — the Amtrak feed leads with hundreds of Thruway
# connecting-bus trips and the SEPTA google_bus feed is mostly buses; without
# this filter the trip sampling budget is spent on bus routes before any rail
# route is reached.
RAIL_ROUTE_TYPES = {"0", "1", "2"}

# Trip sampling: enough distinct stopping patterns per route to cover its
# variety (locals vs expresses hit different consecutive station pairs).
# Trips with an already-seen (shape, stop sequence) are skipped without
# consuming budget, so the cap counts patterns, not raw trips. A global cap
# is wrong here — feeds list trips grouped by route, so a global cap exhausts
# the budget on the first few routes and leaves the rest with no shapes at all
# (this is how Amtrak shipped with near-zero coverage).
MAX_PATTERNS_PER_ROUTE = 200

# Topology pass: a station anchors a shape slice only if the shape's polyline
# passes within this distance of it. Keeps a shape that merely comes near a
# city from being mistaken for one that actually serves its station. 2 km
# tolerates same-city terminal splits (the Downeaster's shape runs to Boston
# North Station, ~1.7 km from the coordinates stored for code BOS).
MAX_STATION_TO_SHAPE_M = 2000.0

_IOS_SHARED_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "ios", "TrackRat", "Shared"
)

# iOS route topology — parsed for its adjacent station pairs so the base-layer
# renderer (which walks RouteTopology.swift, not the backend topology) finds a
# shape for every segment it draws.
IOS_TOPOLOGY_PATH = os.path.join(_IOS_SHARED_DIR, "RouteTopology.swift")

# iOS station coordinates — the renderer's own chord endpoints, used as the
# last-resort anchor for stations absent from both the GTFS feed and the
# backend STATION_COORDINATES table.
IOS_COORDINATES_PATH = os.path.join(_IOS_SHARED_DIR, "StationCoordinates.swift")

# Import station code mapping from backend to map GTFS stop_ids to our codes.
# We do this by adding backend_v2/src to sys.path.
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_SRC = os.path.join(SCRIPT_DIR, "..", "backend_v2", "src")
sys.path.insert(0, BACKEND_SRC)

from trackrat.config.stations import (  # noqa: E402
    get_station_coordinates,
    map_gtfs_stop_to_station_code,
)
from trackrat.config.route_topology import ALL_ROUTES  # noqa: E402

# Build a mapping from equivalent station codes to the canonical code used
# in route topology. E.g., "TS" -> "SE" because route definitions use "SE"
# for Secaucus. Without this, shape data keyed by GTFS-derived codes (like
# "TS" for Secaucus Lower Level) is inaccessible to the iOS renderer which
# looks up segments using topology codes.
_TOPOLOGY_CODES: set[str] = set()
for _route in ALL_ROUTES:
    _TOPOLOGY_CODES.update(_route.stations)

try:
    from trackrat.config.stations.common import STATION_EQUIVALENTS

    SHAPE_CODE_REMAP: dict[str, str] = {}
    for code, group in STATION_EQUIVALENTS.items():
        if code in _TOPOLOGY_CODES:
            continue
        # Find the canonical code from this equivalence group that IS in topology
        canonical = next((c for c in group if c in _TOPOLOGY_CODES), None)
        if canonical:
            SHAPE_CODE_REMAP[code] = canonical
except ImportError:
    SHAPE_CODE_REMAP = {}


@dataclass
class ShapePoint:
    lat: float
    lon: float
    sequence: int
    dist_traveled: float = 0.0


def download_gtfs(provider: str, cache_dir: str = "/tmp/gtfs_shapes") -> str:
    """Download GTFS zip, return path. Uses cached copy if available."""
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"{provider.lower()}.zip")
    if os.path.exists(cache_path):
        print(f"  Using cached {cache_path}")
        return cache_path
    url = GTFS_FEEDS[provider]
    print(f"  Downloading {url}...")
    urllib.request.urlretrieve(url, cache_path)
    return cache_path


def parse_gtfs_file(zip_path: str, filename: str) -> list[dict]:
    """Parse a CSV file from a GTFS zip. Returns empty list if file not found."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            # Match the exact file, or the same file nested in a subdirectory.
            # A plain endswith() would wrongly match e.g. "route_stops.txt" when
            # asked for "stops.txt" (SEPTA ships both).
            matching = [
                n for n in zf.namelist() if n == filename or n.endswith("/" + filename)
            ]
            if not matching:
                return []
            with zf.open(matching[0]) as f:
                text = io.TextIOWrapper(f, encoding="utf-8-sig")
                return list(csv.DictReader(text))
    except (KeyError, zipfile.BadZipFile):
        return []


def parse_shapes(rows: list[dict]) -> dict[str, list[ShapePoint]]:
    """Parse shapes.txt into {shape_id: [ShapePoint]} sorted by sequence."""
    shapes: dict[str, list[ShapePoint]] = defaultdict(list)
    for row in rows:
        shape_id = row.get("shape_id", "")
        if not shape_id:
            continue
        pt = ShapePoint(
            lat=float(row["shape_pt_lat"]),
            lon=float(row["shape_pt_lon"]),
            sequence=int(row["shape_pt_sequence"]),
            dist_traveled=float(row.get("shape_dist_traveled", 0) or 0),
        )
        shapes[shape_id].append(pt)
    # Sort each shape by sequence
    for shape_id in shapes:
        shapes[shape_id].sort(key=lambda p: p.sequence)
    return shapes


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters."""
    r = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * math.sin(dlon / 2) ** 2
    return r * 2 * math.asin(math.sqrt(min(1, a)))


def find_nearest_shape_index(
    shape_points: list[ShapePoint], lat: float, lon: float
) -> int:
    """Find the index of the shape point nearest to the given coordinate."""
    best_idx = 0
    best_dist = float("inf")
    for i, pt in enumerate(shape_points):
        d = haversine_m(pt.lat, pt.lon, lat, lon)
        if d < best_dist:
            best_dist = d
            best_idx = i
    return best_idx


def douglas_peucker(
    points: list[tuple[float, float]], epsilon: float
) -> list[tuple[float, float]]:
    """Simplify a polyline using Douglas-Peucker algorithm. Epsilon in degrees."""
    if len(points) <= 2:
        return points

    # Find the point with the maximum distance from the line between first and last
    start, end = points[0], points[-1]
    max_dist = 0.0
    max_idx = 0

    for i in range(1, len(points) - 1):
        d = _perpendicular_distance(points[i], start, end)
        if d > max_dist:
            max_dist = d
            max_idx = i

    if max_dist > epsilon:
        left = douglas_peucker(points[: max_idx + 1], epsilon)
        right = douglas_peucker(points[max_idx:], epsilon)
        return left[:-1] + right
    else:
        return [start, end]


def _perpendicular_distance(
    point: tuple[float, float],
    line_start: tuple[float, float],
    line_end: tuple[float, float],
) -> float:
    """Perpendicular distance from a point to a line segment (in degrees, approximate)."""
    dx = line_end[0] - line_start[0]
    dy = line_end[1] - line_start[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.sqrt(
            (point[0] - line_start[0]) ** 2 + (point[1] - line_start[1]) ** 2
        )
    t = max(
        0,
        min(
            1,
            ((point[0] - line_start[0]) * dx + (point[1] - line_start[1]) * dy)
            / length_sq,
        ),
    )
    proj = (line_start[0] + t * dx, line_start[1] + t * dy)
    return math.sqrt((point[0] - proj[0]) ** 2 + (point[1] - proj[1]) ** 2)


def rail_trip_filter(trips: list[dict], routes: list[dict]) -> list[dict]:
    """Keep only trips on rail routes (route_type 0/1/2), dropping buses.

    If routes.txt is missing or carries no route_type data, all trips pass
    through unchanged — every feed we consume is then rail-only anyway.
    """
    route_types = {
        r["route_id"]: (r.get("route_type") or "").strip()
        for r in routes
        if r.get("route_id")
    }
    if not any(route_types.values()):
        return trips
    return [
        t for t in trips if route_types.get(t.get("route_id", "")) in RAIL_ROUTE_TYPES
    ]


def extract_segment_shapes(
    provider: str,
    shapes: dict[str, list[ShapePoint]],
    trips: list[dict],
    stop_times: list[dict],
    stops: list[dict],
) -> dict[str, list[tuple[float, float]]]:
    """
    For each consecutive station pair in this provider's trips, extract the
    shape points between those stations.

    Returns: {"fromCode-toCode": [(lat, lon), ...]}
    """
    if not shapes:
        print(f"  No shapes.txt data for {provider}")
        return {}

    # Build stop coordinate and name lookups
    stop_coords: dict[str, tuple[float, float]] = {}
    stop_names: dict[str, str] = {}
    for stop in stops:
        stop_names[stop["stop_id"]] = stop.get("stop_name", "")
        # Some feeds include stops with no coordinates (station complexes,
        # entrances). Skip those — they can't anchor a shape segment.
        lat, lon = stop.get("stop_lat", ""), stop.get("stop_lon", "")
        if not lat or not lon:
            continue
        stop_coords[stop["stop_id"]] = (float(lat), float(lon))

    # Build trip -> shape_id and trip -> route_id mappings
    trip_shape: dict[str, str] = {}
    trip_route: dict[str, str] = {}
    for trip in trips:
        shape_id = trip.get("shape_id", "")
        if shape_id:
            trip_shape[trip["trip_id"]] = shape_id
            trip_route[trip["trip_id"]] = trip.get("route_id", "")

    # Build trip -> ordered stops
    trip_stops: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for st in stop_times:
        trip_id = st["trip_id"]
        if trip_id not in trip_shape:
            continue
        seq = int(st["stop_sequence"])
        trip_stops[trip_id].append((seq, st["stop_id"]))

    # Sort each trip's stops by sequence
    for trip_id in trip_stops:
        trip_stops[trip_id].sort()

    # For each trip, extract shape segments between consecutive stops
    # Accumulate all shapes per segment key, keep the one with the most points
    segment_shapes: dict[str, list[tuple[float, float]]] = {}
    route_pattern_counts: dict[str, int] = defaultdict(int)
    seen_patterns: set[tuple] = set()

    for trip_id, ordered_stops in trip_stops.items():
        shape_id = trip_shape.get(trip_id)
        if not shape_id or shape_id not in shapes:
            continue

        # Identical (shape, stop sequence) trips add nothing — skip them
        # without consuming the per-route pattern budget
        pattern = (shape_id, tuple(stop_id for _, stop_id in ordered_stops))
        if pattern in seen_patterns:
            continue

        route_id = trip_route.get(trip_id, "")
        if route_pattern_counts[route_id] >= MAX_PATTERNS_PER_ROUTE:
            continue
        seen_patterns.add(pattern)

        shape_points = shapes[shape_id]
        if len(shape_points) < 2:
            continue

        # Map GTFS stop IDs to our station codes (with equivalence remapping)
        mapped_stops: list[tuple[str, str]] = []  # (our_code, gtfs_stop_id)
        for _, gtfs_stop_id in ordered_stops:
            stop_name = stop_names.get(gtfs_stop_id, "")
            our_code = map_gtfs_stop_to_station_code(gtfs_stop_id, stop_name, provider)
            if our_code:
                our_code = SHAPE_CODE_REMAP.get(our_code, our_code)
                mapped_stops.append((our_code, gtfs_stop_id))

        if len(mapped_stops) < 2:
            continue

        # Find shape indices for each stop
        stop_shape_indices: list[tuple[str, int]] = []
        for our_code, gtfs_stop_id in mapped_stops:
            coords = stop_coords.get(gtfs_stop_id)
            if not coords:
                continue
            idx = find_nearest_shape_index(shape_points, coords[0], coords[1])
            stop_shape_indices.append((our_code, idx))

        # Extract shape points between consecutive station pairs
        for i in range(len(stop_shape_indices) - 1):
            from_code, from_idx = stop_shape_indices[i]
            to_code, to_idx = stop_shape_indices[i + 1]

            if from_code == to_code:
                continue

            # Canonical key (alphabetical order for consistency)
            key = f"{from_code}-{to_code}" if from_code < to_code else f"{to_code}-{from_code}"

            # Extract points between the two stops
            if from_idx <= to_idx:
                segment_pts = [
                    (p.lat, p.lon) for p in shape_points[from_idx : to_idx + 1]
                ]
            else:
                segment_pts = [
                    (p.lat, p.lon) for p in shape_points[to_idx : from_idx + 1]
                ]
                segment_pts.reverse()

            # Normalize direction: points must go from alphabetically-first
            # station to alphabetically-second, matching the canonical key.
            # Without this, the iOS polyline merger concatenates backwards
            # segments, causing visual artifacts (squiggling / doubling back).
            if from_code > to_code:
                segment_pts.reverse()

            # Keep the version with the most points (most detail)
            if key not in segment_shapes or len(segment_pts) > len(
                segment_shapes[key]
            ):
                segment_shapes[key] = segment_pts

        route_pattern_counts[route_id] += 1

    return segment_shapes


def parse_ios_topology() -> dict[str, list[list[str]]]:
    """Parse RouteTopology.swift into {provider: [ordered station code lists]}.

    The iOS base-layer renderer draws one polyline per *iOS* adjacent station
    pair, and its route lists are coarser than the backend's (e.g. the iOS
    California Zephyr lists 8 stations where the backend lists every stop), so
    backend topology alone cannot supply all the keys iOS looks up.
    """
    try:
        with open(IOS_TOPOLOGY_PATH, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"  ⚠️  Cannot read iOS RouteTopology.swift ({e}) — "
              "base-layer pairs limited to backend topology")
        return {}

    result: dict[str, list[list[str]]] = defaultdict(list)
    pattern = re.compile(
        r'dataSource:\s*"([A-Z_]+)"\s*,\s*stationCodes:\s*\[([^\]]*)\]', re.S
    )
    for match in pattern.finditer(text):
        provider = match.group(1)
        codes = re.findall(r'"([^"]+)"', match.group(2))
        if len(codes) >= 2:
            result[provider].append(codes)
    return dict(result)


def parse_ios_station_coordinates() -> dict[str, dict[str, float]]:
    """Parse StationCoordinates.swift into {code: {lat, lon}}.

    These are the exact coordinates the iOS renderer draws chord endpoints
    from, and the file covers stations that the current GTFS feed and the
    backend STATION_COORDINATES table both lack (e.g. Amtrak stations with
    temporarily suspended service).
    """
    try:
        with open(IOS_COORDINATES_PATH, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"  ⚠️  Cannot read iOS StationCoordinates.swift ({e})")
        return {}

    pattern = re.compile(
        r'"([A-Z0-9]+)":\s*CLLocationCoordinate2D\('
        r"latitude:\s*(-?[\d.]+),\s*longitude:\s*(-?[\d.]+)\)"
    )
    return {
        m.group(1): {"lat": float(m.group(2)), "lon": float(m.group(3))}
        for m in pattern.finditer(text)
    }


def resolve_station_coords(
    needed_pairs: set[tuple[str, str]],
    feed_coords: dict[str, dict[str, float]],
    ios_coords: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    """Best coordinates per topology station: the feed's own stops.txt first
    (it matches the feed's shape geometry), then backend STATION_COORDINATES,
    then iOS StationCoordinates.swift."""
    resolved: dict[str, dict[str, float]] = {}
    for pair in needed_pairs:
        for code in pair:
            if code in resolved:
                continue
            coords = (
                feed_coords.get(code)
                or get_station_coordinates(code)
                or ios_coords.get(code)
            )
            if coords:
                resolved[code] = coords
    return resolved


def topology_adjacent_pairs(
    provider: str, ios_topology: dict[str, list[list[str]]]
) -> set[tuple[str, str]]:
    """All adjacent station pairs (canonically ordered) that renderers walk:
    backend route_topology plus the iOS RouteTopology.swift lists."""
    pairs: set[tuple[str, str]] = set()
    station_lists = [
        route.stations for route in ALL_ROUTES if route.data_source == provider
    ]
    station_lists.extend(ios_topology.get(provider, []))
    for stations in station_lists:
        for a, b in zip(stations, stations[1:], strict=False):
            if a != b:
                pairs.add((a, b) if a < b else (b, a))
    return pairs


def find_nearest_shape_position(
    shape_points: list[ShapePoint], lat: float, lon: float
) -> tuple[float, int, float, float, float]:
    """Nearest position ON the polyline (not just nearest vertex).

    Long-distance shapes space vertices kilometers apart, so vertex distance
    wildly overstates how far a station is from the line (Syracuse sits ~0 m
    from the Empire Corridor track but 3.5 km from the nearest vertex).

    Returns (dist_m, segment_index, t, proj_lat, proj_lon) where the position
    lies on the segment between vertex segment_index and segment_index + 1 at
    fraction t. Projection happens in raw degree space — good enough to pick
    the nearest segment — while dist_m is a true haversine distance.
    """
    best: tuple[float, int, float, float, float] | None = None
    for i in range(len(shape_points) - 1):
        a, b = shape_points[i], shape_points[i + 1]
        dx, dy = b.lat - a.lat, b.lon - a.lon
        length_sq = dx * dx + dy * dy
        if length_sq == 0:
            t = 0.0
        else:
            t = max(0.0, min(1.0, ((lat - a.lat) * dx + (lon - a.lon) * dy) / length_sq))
        proj_lat, proj_lon = a.lat + t * dx, a.lon + t * dy
        dist = haversine_m(proj_lat, proj_lon, lat, lon)
        if best is None or dist < best[0]:
            best = (dist, i, t, proj_lat, proj_lon)
    return best


def station_coords_for_provider(
    provider: str, stops: list[dict]
) -> dict[str, dict[str, float]]:
    """Station code -> coordinates from the feed's own stops.txt.

    The feed's coordinates are authoritative for anchoring against the feed's
    shapes; the backend STATION_COORDINATES table is only a fallback (used in
    slice_topology_pairs) and has gaps for some Amtrak stations.
    """
    coords: dict[str, dict[str, float]] = {}
    for stop in stops:
        code = map_gtfs_stop_to_station_code(
            stop.get("stop_id", ""), stop.get("stop_name", ""), provider
        )
        if not code:
            continue
        code = SHAPE_CODE_REMAP.get(code, code)
        lat, lon = stop.get("stop_lat", ""), stop.get("stop_lon", "")
        if not lat or not lon:
            continue
        coords.setdefault(code, {"lat": float(lat), "lon": float(lon)})
    return coords


def slice_topology_pairs(
    shapes: dict[str, list[ShapePoint]],
    needed_pairs: set[tuple[str, str]],
    existing_keys: set[str],
    station_coords: dict[str, dict[str, float]],
) -> dict[str, list[tuple[float, float]]]:
    """Slice shapes for topology-adjacent pairs the trip pass missed.

    Coarse pairs (express hops like OMA-DEN) are never consecutive stops of any
    trip, so the trip pass cannot produce them. For each missing pair, find the
    shape whose polyline passes closest to both stations (each within
    MAX_STATION_TO_SHAPE_M) and cut it between the two projected positions.

    Returns: {"fromCode-toCode": [(lat, lon), ...]} for newly covered pairs.
    """
    # Precompute bounding boxes for a cheap containment prefilter
    margin = 0.02  # ~2 km in latitude
    candidates = []
    for shape_points in shapes.values():
        if len(shape_points) < 2:
            continue
        lats = [p.lat for p in shape_points]
        lons = [p.lon for p in shape_points]
        candidates.append(
            (shape_points, min(lats) - margin, max(lats) + margin,
             min(lons) - margin, max(lons) + margin)
        )

    def in_bbox(coord: dict, bbox) -> bool:
        _, lat_lo, lat_hi, lon_lo, lon_hi = bbox
        return lat_lo <= coord["lat"] <= lat_hi and lon_lo <= coord["lon"] <= lon_hi

    new_segments: dict[str, list[tuple[float, float]]] = {}
    for code_a, code_b in sorted(needed_pairs):
        key = f"{code_a}-{code_b}"  # pairs arrive canonically ordered (a < b)
        if key in existing_keys or key in new_segments:
            continue
        coord_a = station_coords.get(code_a)
        coord_b = station_coords.get(code_b)
        if not coord_a or not coord_b:
            continue

        best = None  # (score, shape_points, pos_a, pos_b)
        for bbox in candidates:
            if not (in_bbox(coord_a, bbox) and in_bbox(coord_b, bbox)):
                continue
            shape_points = bbox[0]
            pos_a = find_nearest_shape_position(shape_points, coord_a["lat"], coord_a["lon"])
            pos_b = find_nearest_shape_position(shape_points, coord_b["lat"], coord_b["lon"])
            dist_a, dist_b = pos_a[0], pos_b[0]
            if dist_a > MAX_STATION_TO_SHAPE_M or dist_b > MAX_STATION_TO_SHAPE_M:
                continue
            score = dist_a + dist_b
            if best is None or score < best[0]:
                best = (score, shape_points, pos_a, pos_b)

        if best is None:
            continue
        _, shape_points, pos_a, pos_b = best
        _, seg_a, t_a, proj_a_lat, proj_a_lon = pos_a
        _, seg_b, t_b, proj_b_lat, proj_b_lon = pos_b
        scalar_a, scalar_b = seg_a + t_a, seg_b + t_b
        if scalar_a == scalar_b:
            continue  # both stations project to the same spot — degenerate

        if scalar_a <= scalar_b:
            interior = [(p.lat, p.lon) for p in shape_points[seg_a + 1 : seg_b + 1]]
            segment_pts = [(proj_a_lat, proj_a_lon)] + interior + [(proj_b_lat, proj_b_lon)]
        else:
            interior = [(p.lat, p.lon) for p in shape_points[seg_b + 1 : seg_a + 1]]
            segment_pts = [(proj_b_lat, proj_b_lon)] + interior + [(proj_a_lat, proj_a_lon)]
            segment_pts.reverse()  # run code_a -> code_b, matching the canonical key

        # Projections at t=0/1 coincide with vertices — drop exact duplicates
        deduped = [segment_pts[0]]
        for pt in segment_pts[1:]:
            if pt != deduped[-1]:
                deduped.append(pt)
        if len(deduped) < 2:
            continue
        new_segments[key] = deduped

    return new_segments


def simplify_shapes(
    segment_shapes: dict[str, list[tuple[float, float]]],
    epsilon: float = 0.0001,  # ~11 meters
) -> dict[str, list[tuple[float, float]]]:
    """Simplify all segment shapes using Douglas-Peucker.

    Long intercity segments (Amtrak long-distance hops span hundreds of km)
    get a proportionally larger tolerance: they are only ever viewed at
    national zoom, and ~11 m fidelity there would balloon the generated file.
    """
    result = {}
    for key, points in segment_shapes.items():
        span_m = haversine_m(points[0][0], points[0][1], points[-1][0], points[-1][1])
        if span_m > 200_000:
            eps = epsilon * 20  # ~220 m
        elif span_m > 50_000:
            eps = epsilon * 5  # ~55 m
        else:
            eps = epsilon
        simplified = douglas_peucker(points, eps)
        # Only keep if we have more than 2 points (straight line needs no shape data)
        if len(simplified) > 2:
            result[key] = simplified
        elif len(points) > 2:
            # If simplification reduced to 2 but original had more,
            # the segment is nearly straight — skip it
            pass
        # Segments with <=2 original points are straight lines — skip
    return result


def validate_direction(
    all_shapes: dict[str, dict[str, list[tuple[float, float]]]],
) -> int:
    """
    Validate that shape data direction matches canonical key order.

    For each segment key "A-B" (A < B alphabetically), the first coordinate
    should be closer to station A and the last coordinate closer to station B.
    Returns the number of violations found.
    """
    from trackrat.config.stations import get_station_coordinates

    violations = 0
    for provider, shapes in all_shapes.items():
        for key, points in shapes.items():
            if len(points) < 2:
                continue
            parts = key.split("-")
            if len(parts) != 2:
                continue
            code_a, code_b = parts
            coord_a = get_station_coordinates(code_a)
            coord_b = get_station_coordinates(code_b)
            if not coord_a or not coord_b:
                continue

            first_pt = points[0]
            last_pt = points[-1]

            # Distance from first point to station A vs station B
            dist_first_to_a = haversine_m(first_pt[0], first_pt[1], coord_a["lat"], coord_a["lon"])
            dist_first_to_b = haversine_m(first_pt[0], first_pt[1], coord_b["lat"], coord_b["lon"])
            dist_last_to_a = haversine_m(last_pt[0], last_pt[1], coord_a["lat"], coord_a["lon"])
            dist_last_to_b = haversine_m(last_pt[0], last_pt[1], coord_b["lat"], coord_b["lon"])

            # First point should be closer to A, last point closer to B
            if dist_first_to_b < dist_first_to_a and dist_last_to_a < dist_last_to_b:
                print(f"  ⚠️  REVERSED: {provider} {key} — first point near {code_b}, last near {code_a}")
                violations += 1

    return violations


def merge_provider_shapes(
    all_shapes: dict[str, dict[str, list[tuple[float, float]]]],
) -> dict[str, dict[str, list[tuple[float, float]]]]:
    """Resolve cross-provider duplicate keys before Swift emission.

    Providers that share track also share station codes (NJT and Amtrak both
    produce "NP-NY"), but a Swift dictionary literal with duplicate keys is a
    runtime crash, so each key must be emitted exactly once. Keep the version
    with the most points; ties go to the alphabetically-first provider.
    """
    winners: dict[str, str] = {}
    for provider in sorted(all_shapes):
        for key, points in all_shapes[provider].items():
            current = winners.get(key)
            if current is None or len(points) > len(all_shapes[current][key]):
                winners[key] = provider

    merged: dict[str, dict[str, list[tuple[float, float]]]] = {
        provider: {} for provider in all_shapes
    }
    duplicates = 0
    for key, provider in winners.items():
        merged[provider][key] = all_shapes[provider][key]
        duplicates += sum(1 for p in all_shapes if key in all_shapes[p]) - 1
    if duplicates:
        print(f"  Deduplicated {duplicates} cross-provider key(s)")
    return merged


def generate_swift(
    all_shapes: dict[str, dict[str, list[tuple[float, float]]]],
    output_path: str,
) -> None:
    """Generate RouteShapes.swift with embedded coordinate arrays."""

    all_shapes = merge_provider_shapes(all_shapes)
    total_segments = sum(len(shapes) for shapes in all_shapes.values())
    total_points = sum(
        len(pts) for shapes in all_shapes.values() for pts in shapes.values()
    )

    lines = [
        "// RouteShapes.swift",
        "// Auto-generated by scripts/generate_route_shapes.py",
        "// Do not edit manually.",
        "//",
        f"// {total_segments} segments, {total_points} points total",
        "",
        "import CoreLocation",
        "",
        "/// Pre-computed route shape coordinates from GTFS shapes.txt data.",
        "/// Maps canonical segment keys (\"fromStation-toStation\" alphabetically ordered)",
        "/// to arrays of intermediate coordinates for drawing smooth polylines.",
        "/// Segments not in this dictionary should be drawn as straight lines.",
        "enum RouteShapes {",
        "",
        "    /// Look up shape coordinates for a station pair.",
        "    /// Returns nil if no shape data exists (draw a straight line).",
        "    /// The returned array includes the from and to station coordinates.",
        "    static func coordinates(from fromStation: String, to toStation: String) -> [CLLocationCoordinate2D]? {",
        '        let key = fromStation < toStation ? "\\(fromStation)-\\(toStation)" : "\\(toStation)-\\(fromStation)"',
        "        guard let rawPoints = shapeData[key], rawPoints.count >= 4, rawPoints.count.isMultiple(of: 2) else { return nil }",
        "        let points = stride(from: 0, to: rawPoints.count, by: 2).map {",
        "            CLLocationCoordinate2D(latitude: rawPoints[$0], longitude: rawPoints[$0 + 1])",
        "        }",
        "        return fromStation > toStation ? points.reversed() : points",
        "    }",
        "",
        "    // MARK: - Shape Data",
        "    // Encoded as \"KEY|lat,lon,lat,lon,...\" text lines and parsed on first",
        "    // access. Deliberately NOT a [String: [Double]] literal: a numeric",
        "    // collection literal this size (60k+ Doubles, compiled once per target)",
        "    // sends the Swift type checker into minutes-long territory and timed out",
        "    // iOS CI. String literals type-check in constant time.",
        "",
        f"    private static let shapeData: [String: [Double]] = {{",
        f"        var result = [String: [Double]](minimumCapacity: {total_segments})",
        "        for block in encodedShapeData {",
        '            for line in block.split(separator: "\\n") {',
        '                guard let separator = line.firstIndex(of: "|") else { continue }',
        "                let key = String(line[..<separator])",
        "                let values = line[line.index(after: separator)...]",
        '                    .split(separator: ",")',
        "                    .compactMap { Double($0) }",
        "                guard values.count >= 4, values.count.isMultiple(of: 2) else { continue }",
        "                result[key] = values",
        "            }",
        "        }",
        "        return result",
        "    }()",
        "",
        "    private static let encodedShapeData: [String] = [",
    ]

    for provider in sorted(all_shapes.keys()):
        shapes = all_shapes[provider]
        if not shapes:
            continue
        lines.append(f"        // {provider}")
        lines.append('        """')
        for key in sorted(shapes.keys()):
            flat = []
            for p in shapes[key]:
                flat.extend([f"{p[0]:.6f}", f"{p[1]:.6f}"])
            lines.append(f"        {key}|{','.join(flat)}")
        lines.append('        """,')

    lines.append("    ]")
    lines.append("}")
    lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"\nGenerated {output_path}")
    print(f"  {total_segments} segments, {total_points} points")


def main():
    parser = argparse.ArgumentParser(description="Generate route shapes from GTFS data")
    parser.add_argument(
        "--output-dir",
        default="/tmp/route_shapes",
        help="Output directory (default: /tmp/route_shapes)",
    )
    parser.add_argument(
        "--providers",
        nargs="+",
        default=list(GTFS_FEEDS.keys()),
        help="Providers to process (default: all)",
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        default=0.0001,
        help="Douglas-Peucker simplification tolerance in degrees (~11m, default: 0.0001)",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    ios_topology = parse_ios_topology()
    ios_coords = parse_ios_station_coordinates()
    all_shapes: dict[str, dict[str, list[tuple[float, float]]]] = {}

    for provider in args.providers:
        print(f"\nProcessing {provider}...")

        try:
            zip_path = download_gtfs(provider)
        except Exception as e:
            print(f"  Failed to download {provider}: {e}")
            continue

        # Parse GTFS files
        shapes_raw = parse_gtfs_file(zip_path, "shapes.txt")
        if not shapes_raw:
            print(f"  No shapes.txt found for {provider} — skipping")
            continue

        trips = parse_gtfs_file(zip_path, "trips.txt")
        stop_times = parse_gtfs_file(zip_path, "stop_times.txt")
        stops = parse_gtfs_file(zip_path, "stops.txt")
        routes = parse_gtfs_file(zip_path, "routes.txt")

        print(f"  Parsed: {len(shapes_raw)} shape points, {len(trips)} trips, {len(stop_times)} stop_times, {len(stops)} stops")

        # Drop bus trips (Amtrak Thruway, SEPTA buses) before sampling
        rail_trips = rail_trip_filter(trips, routes)
        if len(rail_trips) != len(trips):
            print(f"  {len(rail_trips)} rail trips after route_type filter ({len(trips) - len(rail_trips)} non-rail dropped)")

        # Process shapes
        shapes = parse_shapes(shapes_raw)
        print(f"  {len(shapes)} unique shapes")

        # Extract segment shapes from sampled trips
        segment_shapes = extract_segment_shapes(
            provider, shapes, rail_trips, stop_times, stops
        )
        print(f"  {len(segment_shapes)} station-pair segments from trip pass")

        # Slice shapes for topology-adjacent pairs the trip pass missed, using
        # only rail trips' shapes so a bus shape can never win the slice.
        rail_shape_ids = {t["shape_id"] for t in rail_trips if t.get("shape_id")}
        rail_shapes = {sid: pts for sid, pts in shapes.items() if sid in rail_shape_ids}
        needed_pairs = topology_adjacent_pairs(provider, ios_topology)
        feed_coords = station_coords_for_provider(provider, stops)
        station_coords = resolve_station_coords(needed_pairs, feed_coords, ios_coords)
        sliced = slice_topology_pairs(
            rail_shapes, needed_pairs, set(segment_shapes.keys()), station_coords
        )
        if sliced:
            segment_shapes.update(sliced)
            print(f"  {len(sliced)} additional segments from topology pass")
        still_missing = [
            f"{a}-{b}" for a, b in sorted(needed_pairs)
            if f"{a}-{b}" not in segment_shapes
        ]
        if still_missing:
            print(f"  {len(still_missing)} topology pairs without shape data: {', '.join(still_missing[:20])}{'…' if len(still_missing) > 20 else ''}")

        # Simplify
        simplified = simplify_shapes(segment_shapes, epsilon=args.epsilon)
        print(f"  {len(simplified)} segments after simplification (straight lines removed)")

        all_shapes[provider] = simplified

    # Validate direction consistency
    print("\nValidating shape directions...")
    violations = validate_direction(all_shapes)
    if violations:
        print(f"\n❌ {violations} segments with reversed direction detected!")
        print("This indicates a bug in extract_segment_shapes direction normalization.")
    else:
        print("✅ All segments have correct direction")

    # Generate Swift file
    swift_path = os.path.join(args.output_dir, "RouteShapes.swift")
    generate_swift(all_shapes, swift_path)


if __name__ == "__main__":
    main()
