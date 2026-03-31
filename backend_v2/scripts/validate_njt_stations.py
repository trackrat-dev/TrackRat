#!/usr/bin/env python3
"""
Validate NJ Transit station names and coordinates against GTFS stops.txt.

Downloads the NJT GTFS feed, extracts stops.txt, and compares each stop's
name and coordinates against our STATION_NAMES and STATION_COORDINATES.

Reports:
  - GTFS stops that fail to map to any internal station code
  - Coordinate mismatches (>500m) between GTFS and our data
  - Internal stations with no GTFS counterpart
  - Name mismatches between GTFS and our data
"""

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
    STATION_COORDINATES,
    STATION_NAMES,
    NJT_GTFS_STOP_TO_INTERNAL_MAP,
    map_gtfs_stop_to_station_code,
)

NJT_GTFS_URL = "https://content.njtransit.com/public/developers-resources/rail_data.zip"

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


def download_gtfs_stops() -> list[dict[str, str]]:
    """Download NJT GTFS feed and extract stops.txt rows."""
    print(f"Downloading NJT GTFS feed from {NJT_GTFS_URL}...")

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = tmp.name

    result = subprocess.run(
        ["curl", "-sL", "-o", tmp_path, NJT_GTFS_URL],
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


def validate(gtfs_stops: list[dict[str, str]]) -> dict:
    """Run all validation checks. Returns summary dict."""
    unmapped_stops = []
    coord_mismatches = []
    name_mismatches = []
    mapped_internal_codes: set[str] = set()

    for stop in gtfs_stops:
        stop_id = stop.get("stop_id", "")
        stop_name = stop.get("stop_name", "")
        stop_lat = float(stop.get("stop_lat", "0"))
        stop_lon = float(stop.get("stop_lon", "0"))

        # Try to map this GTFS stop to our internal code
        code = map_gtfs_stop_to_station_code(stop_id, stop_name, "NJT")

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
        # Only flag if they're quite different (not just suffix/abbreviation)
        if our_normalized != gtfs_normalized:
            # Check if one contains the other (acceptable variation)
            if our_normalized not in gtfs_normalized and gtfs_normalized not in our_normalized:
                # Check word overlap
                our_words = set(our_normalized.split())
                gtfs_words = set(gtfs_normalized.split())
                overlap = len(our_words & gtfs_words)
                total = max(len(our_words), len(gtfs_words))
                if overlap / total < 0.5:
                    name_mismatches.append({
                        "code": code,
                        "our_name": our_name,
                        "gtfs_name": stop_name,
                        "gtfs_stop_id": stop_id,
                    })

    # Find internal NJT station codes that have no GTFS counterpart
    # Filter to likely NJT codes (2-char codes, excluding known Amtrak-only)
    njt_codes_in_names = {
        code for code in STATION_NAMES
        if len(code) <= 2 and code not in {"BA", "BL", "WS"}
    }
    orphan_codes = njt_codes_in_names - mapped_internal_codes

    return {
        "total_gtfs_stops": len(gtfs_stops),
        "mapped_count": len(mapped_internal_codes),
        "unmapped_stops": unmapped_stops,
        "coord_mismatches": sorted(coord_mismatches, key=lambda x: -x["distance_m"]),
        "name_mismatches": name_mismatches,
        "orphan_codes": sorted(orphan_codes),
    }


def print_report(results: dict) -> None:
    """Print a human-readable validation report."""
    print("=" * 80)
    print("NJ TRANSIT STATION VALIDATION REPORT")
    print("=" * 80)

    print(f"\nTotal GTFS stops:           {results['total_gtfs_stops']}")
    print(f"Successfully mapped:        {results['mapped_count']}")
    print(f"Failed to map:              {len(results['unmapped_stops'])}")
    print(f"Coordinate mismatches:      {len(results['coord_mismatches'])}")
    print(f"Name mismatches:            {len(results['name_mismatches'])}")
    print(f"Internal codes without GTFS:{len(results['orphan_codes'])}")

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
            print(f"  stop_id={s['stop_id']:>6}  {s['stop_name']:<40}  ({s['stop_lat']}, {s['stop_lon']})")

    if results["name_mismatches"]:
        print("\n" + "-" * 80)
        print("NAME MISMATCHES (low word overlap)")
        print("-" * 80)
        for m in results["name_mismatches"]:
            print(f"  [{m['code']}] Our: {m['our_name']:<35} GTFS: {m['gtfs_name']}")

    if results["orphan_codes"]:
        print("\n" + "-" * 80)
        print("INTERNAL CODES WITH NO GTFS COUNTERPART")
        print("-" * 80)
        for code in results["orphan_codes"]:
            name = STATION_NAMES.get(code, "???")
            has_coords = "yes" if code in STATION_COORDINATES else "NO"
            print(f"  [{code}] {name:<35} coords={has_coords}")

    print("\n" + "=" * 80)
    print("END OF REPORT")
    print("=" * 80)


def main():
    gtfs_stops = download_gtfs_stops()
    results = validate(gtfs_stops)
    print_report(results)

    # Exit with error if there are coordinate mismatches
    if results["coord_mismatches"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
