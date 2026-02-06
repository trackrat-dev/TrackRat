#!/usr/bin/env python3
"""
Validate LIRR and Metro-North station data against GTFS static feeds.

Downloads the MTA GTFS feed, extracts stops.txt, and compares each stop's
name and coordinates against our STATION_NAMES and STATION_COORDINATES.

Reports:
  - GTFS stops that fail to map to any internal station code
  - Coordinate mismatches (>500m) between GTFS and our data
  - Name mismatches between GTFS and our data
  - Stale mapping entries (stop_id in our map but not in GTFS)
  - Internal codes missing from STATION_NAMES or STATION_COORDINATES
  - Station codes missing from backend route topology

Usage:
  python validate_mta_stations.py lirr
  python validate_mta_stations.py mnr
  python validate_mta_stations.py all
"""

import argparse
import csv
import io
import math
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# Add backend src to path so we can import station config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from trackrat.config.stations import (
    LIRR_GTFS_STOP_TO_INTERNAL_MAP,
    MNR_GTFS_STOP_TO_INTERNAL_MAP,
    STATION_COORDINATES,
    STATION_NAMES,
    map_gtfs_stop_to_station_code,
)
from trackrat.config.route_topology import get_routes_for_data_source

# GTFS static feed URLs (mirrors services/gtfs.py)
GTFS_URLS = {
    "LIRR": "http://web.mta.info/developers/data/lirr/google_transit.zip",
    "MNR": "http://web.mta.info/developers/data/mnr/google_transit.zip",
}

STOP_MAPS = {
    "LIRR": LIRR_GTFS_STOP_TO_INTERNAL_MAP,
    "MNR": MNR_GTFS_STOP_TO_INTERNAL_MAP,
}

SYSTEM_LABELS = {
    "LIRR": "LONG ISLAND RAIL ROAD",
    "MNR": "METRO-NORTH RAILROAD",
}

# Distance threshold in meters for flagging coordinate mismatches
DISTANCE_THRESHOLD_METERS = 500


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two lat/lon points in meters."""
    R = 6_371_000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def download_gtfs_stops(system: str) -> list[dict[str, str]]:
    """Download MTA GTFS feed and extract stops.txt rows."""
    url = GTFS_URLS[system]
    print(f"Downloading {system} GTFS feed from {url}...")

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = tmp.name

    result = subprocess.run(
        ["curl", "-sL", "-o", tmp_path, url],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        print(f"  ERROR: curl failed: {result.stderr}")
        sys.exit(1)

    stops = []
    with zipfile.ZipFile(tmp_path) as zf:
        with zf.open("stops.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            for row in reader:
                stops.append(dict(row))

    Path(tmp_path).unlink(missing_ok=True)
    print(f"  Found {len(stops)} stops in GTFS feed\n")
    return stops


def validate(system: str, gtfs_stops: list[dict[str, str]]) -> dict:
    """Run all validation checks for a system. Returns summary dict."""
    stop_map = STOP_MAPS[system]
    unmapped_stops = []
    coord_mismatches = []
    name_mismatches = []
    mapped_internal_codes: set[str] = set()
    gtfs_stop_ids: set[str] = set()

    for stop in gtfs_stops:
        stop_id = stop.get("stop_id", "")
        stop_name = stop.get("stop_name", "")
        stop_lat = float(stop.get("stop_lat", "0"))
        stop_lon = float(stop.get("stop_lon", "0"))
        gtfs_stop_ids.add(stop_id)

        # Try to map this GTFS stop to our internal code
        code = map_gtfs_stop_to_station_code(stop_id, stop_name, system)

        if code is None:
            unmapped_stops.append({
                "stop_id": stop_id,
                "stop_name": stop_name,
                "stop_lat": stop_lat,
                "stop_lon": stop_lon,
            })
            continue

        mapped_internal_codes.add(code)
        our_name = STATION_NAMES.get(code, "???")

        # Check coordinate match
        if code in STATION_COORDINATES:
            our_lat = STATION_COORDINATES[code]["lat"]
            our_lon = STATION_COORDINATES[code]["lon"]
            dist = haversine_meters(stop_lat, stop_lon, our_lat, our_lon)

            if dist > DISTANCE_THRESHOLD_METERS:
                coord_mismatches.append({
                    "code": code,
                    "our_name": our_name,
                    "gtfs_name": stop_name,
                    "gtfs_stop_id": stop_id,
                    "our_lat": our_lat,
                    "our_lon": our_lon,
                    "gtfs_lat": stop_lat,
                    "gtfs_lon": stop_lon,
                    "distance_m": round(dist),
                })

        # Check name similarity (case-insensitive, basic)
        our_normalized = our_name.lower().strip()
        gtfs_normalized = stop_name.lower().strip()
        if our_normalized != gtfs_normalized:
            if our_normalized not in gtfs_normalized and gtfs_normalized not in our_normalized:
                our_words = set(our_normalized.split())
                gtfs_words = set(gtfs_normalized.split())
                overlap = len(our_words & gtfs_words)
                total = max(len(our_words), len(gtfs_words))
                if total > 0 and overlap / total < 0.5:
                    name_mismatches.append({
                        "code": code,
                        "our_name": our_name,
                        "gtfs_name": stop_name,
                        "gtfs_stop_id": stop_id,
                    })

    # Stale mappings: entries in our stop_map whose stop_id isn't in GTFS
    stale_mappings = []
    for gtfs_id, internal_code in sorted(stop_map.items(), key=lambda x: x[1]):
        if gtfs_id not in gtfs_stop_ids:
            stale_mappings.append({
                "gtfs_stop_id": gtfs_id,
                "internal_code": internal_code,
                "name": STATION_NAMES.get(internal_code, "???"),
            })

    # Missing config: mapped codes without STATION_NAMES or STATION_COORDINATES
    all_internal_codes = sorted(set(stop_map.values()))
    missing_names = [code for code in all_internal_codes if code not in STATION_NAMES]
    missing_coords = [code for code in all_internal_codes if code not in STATION_COORDINATES]

    # Route topology coverage
    routes = get_routes_for_data_source(system)
    topology_station_codes: set[str] = set()
    for route in routes:
        topology_station_codes.update(route.stations)

    missing_from_topology = sorted(set(all_internal_codes) - topology_station_codes)
    topology_only = sorted(topology_station_codes - set(all_internal_codes))

    return {
        "system": system,
        "total_gtfs_stops": len(gtfs_stops),
        "total_mapping_entries": len(stop_map),
        "mapped_count": len(mapped_internal_codes),
        "unmapped_stops": unmapped_stops,
        "coord_mismatches": sorted(coord_mismatches, key=lambda x: -x["distance_m"]),
        "name_mismatches": name_mismatches,
        "stale_mappings": stale_mappings,
        "missing_names": missing_names,
        "missing_coords": missing_coords,
        "topology_routes": len(routes),
        "topology_stations": len(topology_station_codes),
        "missing_from_topology": missing_from_topology,
        "topology_only": topology_only,
    }


def print_report(results: dict) -> None:
    """Print a human-readable validation report."""
    system = results["system"]
    label = SYSTEM_LABELS[system]

    print("=" * 80)
    print(f"{label} STATION VALIDATION REPORT")
    print("=" * 80)

    print(f"\nTotal GTFS stops:            {results['total_gtfs_stops']}")
    print(f"Our mapping entries:         {results['total_mapping_entries']}")
    print(f"Successfully mapped:         {results['mapped_count']}")
    print(f"Failed to map:               {len(results['unmapped_stops'])}")
    print(f"Coordinate mismatches:       {len(results['coord_mismatches'])}")
    print(f"Name mismatches:             {len(results['name_mismatches'])}")
    print(f"Stale mapping entries:       {len(results['stale_mappings'])}")
    print(f"Missing STATION_NAMES:       {len(results['missing_names'])}")
    print(f"Missing STATION_COORDINATES: {len(results['missing_coords'])}")
    print(f"Route topology routes:       {results['topology_routes']}")
    print(f"Stations not in topology:    {len(results['missing_from_topology'])}")
    print(f"Topology-only stations:      {len(results['topology_only'])}")

    if results["coord_mismatches"]:
        print("\n" + "-" * 80)
        print("COORDINATE MISMATCHES (>500m)")
        print("-" * 80)
        for m in results["coord_mismatches"]:
            print(f"\n  [{m['code']}] {m['our_name']}")
            print(f"    GTFS name:   {m['gtfs_name']} (stop_id={m['gtfs_stop_id']})")
            print(f"    Our coords:  ({m['our_lat']}, {m['our_lon']})")
            print(f"    GTFS coords: ({m['gtfs_lat']}, {m['gtfs_lon']})")
            print(f"    Distance:    {m['distance_m']:,}m ({m['distance_m']/1000:.1f}km)")

    if results["unmapped_stops"]:
        print("\n" + "-" * 80)
        print("UNMAPPED GTFS STOPS (no internal station code found)")
        print("-" * 80)
        for s in results["unmapped_stops"]:
            print(
                f"  stop_id={s['stop_id']:>6}  {s['stop_name']:<40}"
                f"  ({s['stop_lat']}, {s['stop_lon']})"
            )

    if results["name_mismatches"]:
        print("\n" + "-" * 80)
        print("NAME MISMATCHES (low word overlap)")
        print("-" * 80)
        for m in results["name_mismatches"]:
            print(f"  [{m['code']}] Our: {m['our_name']:<35} GTFS: {m['gtfs_name']}")

    if results["stale_mappings"]:
        print("\n" + "-" * 80)
        print("STALE MAPPINGS (stop_id in our map but not in GTFS feed)")
        print("-" * 80)
        for m in results["stale_mappings"]:
            print(f"  stop_id={m['gtfs_stop_id']:>6} -> [{m['internal_code']}] {m['name']}")

    if results["missing_names"]:
        print("\n" + "-" * 80)
        print("MAPPED CODES MISSING FROM STATION_NAMES")
        print("-" * 80)
        for code in results["missing_names"]:
            print(f"  [{code}]")

    if results["missing_coords"]:
        print("\n" + "-" * 80)
        print("MAPPED CODES MISSING FROM STATION_COORDINATES")
        print("-" * 80)
        for code in results["missing_coords"]:
            name = STATION_NAMES.get(code, "???")
            print(f"  [{code}] {name}")

    if results["missing_from_topology"]:
        print("\n" + "-" * 80)
        print(f"STATIONS NOT IN ROUTE TOPOLOGY ({results['topology_routes']} routes defined)")
        print("-" * 80)
        for code in results["missing_from_topology"]:
            name = STATION_NAMES.get(code, "???")
            print(f"  [{code}] {name}")

    if results["topology_only"]:
        print("\n" + "-" * 80)
        print("TOPOLOGY-ONLY STATIONS (in topology but not in GTFS mapping)")
        print("-" * 80)
        for code in results["topology_only"]:
            name = STATION_NAMES.get(code, "???")
            print(f"  [{code}] {name}")

    print("\n" + "=" * 80)
    print("END OF REPORT")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Validate LIRR and Metro-North station data against GTFS static feeds"
    )
    parser.add_argument(
        "system",
        choices=["lirr", "mnr", "all"],
        help="Which system to validate",
    )
    args = parser.parse_args()

    systems = ["LIRR", "MNR"] if args.system == "all" else [args.system.upper()]
    has_errors = False

    for system in systems:
        gtfs_stops = download_gtfs_stops(system)
        results = validate(system, gtfs_stops)
        print_report(results)

        if results["coord_mismatches"] or results["stale_mappings"]:
            has_errors = True

        if systems.index(system) < len(systems) - 1:
            print("\n\n")

    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
