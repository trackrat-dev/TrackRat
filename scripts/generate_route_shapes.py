#!/usr/bin/env python3
"""
Generate route shape coordinates from GTFS shapes.txt for iOS map rendering.

Downloads GTFS feeds for all transit providers, extracts shapes.txt, maps shape
points to station-pair segments, simplifies with Douglas-Peucker, and generates
a Swift file with embedded coordinate arrays.

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
}

# Import station code mapping from backend to map GTFS stop_ids to our codes.
# We do this by adding backend_v2/src to sys.path.
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_SRC = os.path.join(SCRIPT_DIR, "..", "backend_v2", "src")
sys.path.insert(0, BACKEND_SRC)

from trackrat.config.stations import map_gtfs_stop_to_station_code  # noqa: E402
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
            # Some feeds nest files in subdirectories
            matching = [n for n in zf.namelist() if n.endswith(filename)]
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
        stop_coords[stop["stop_id"]] = (
            float(stop["stop_lat"]),
            float(stop["stop_lon"]),
        )
        stop_names[stop["stop_id"]] = stop.get("stop_name", "")

    # Build trip -> shape_id mapping
    trip_shape: dict[str, str] = {}
    for trip in trips:
        shape_id = trip.get("shape_id", "")
        if shape_id:
            trip_shape[trip["trip_id"]] = shape_id

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
    processed_trips = 0

    for trip_id, ordered_stops in trip_stops.items():
        shape_id = trip_shape.get(trip_id)
        if not shape_id or shape_id not in shapes:
            continue

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

        processed_trips += 1
        # Only need a handful of trips per route to get shape coverage
        if processed_trips >= 200:
            break

    return segment_shapes


def simplify_shapes(
    segment_shapes: dict[str, list[tuple[float, float]]],
    epsilon: float = 0.0001,  # ~11 meters
) -> dict[str, list[tuple[float, float]]]:
    """Simplify all segment shapes using Douglas-Peucker."""
    result = {}
    for key, points in segment_shapes.items():
        simplified = douglas_peucker(points, epsilon)
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


def generate_swift(
    all_shapes: dict[str, dict[str, list[tuple[float, float]]]],
    output_path: str,
) -> None:
    """Generate RouteShapes.swift with embedded coordinate arrays."""

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
        "    // Stored as flat [lat, lon, lat, lon, ...] arrays for compact representation.",
        "",
        "    private static let shapeData: [String: [Double]] = [",
    ]

    for provider in sorted(all_shapes.keys()):
        shapes = all_shapes[provider]
        if not shapes:
            continue
        lines.append(f"        // {provider}")
        for key in sorted(shapes.keys()):
            points = shapes[key]
            flat = []
            for p in points:
                flat.extend([f"{p[0]:.6f}", f"{p[1]:.6f}"])
            flat_str = ", ".join(flat)
            if len(flat_str) <= 120:
                lines.append(f'        "{key}": [{flat_str}],')
            else:
                # Wrap long arrays
                lines.append(f'        "{key}": [')
                # Group into coordinate pairs for readability
                for i in range(0, len(flat), 8):  # 4 coordinate pairs per line
                    chunk = ", ".join(flat[i:i+8])
                    lines.append(f"            {chunk},")
                lines.append("        ],")
        lines.append("")

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

        print(f"  Parsed: {len(shapes_raw)} shape points, {len(trips)} trips, {len(stop_times)} stop_times, {len(stops)} stops")

        # Process shapes
        shapes = parse_shapes(shapes_raw)
        print(f"  {len(shapes)} unique shapes")

        # Extract segment shapes
        segment_shapes = extract_segment_shapes(
            provider, shapes, trips, stop_times, stops
        )
        print(f"  {len(segment_shapes)} station-pair segments with shape data")

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
