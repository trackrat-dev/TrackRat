#!/usr/bin/env python3
"""
Generate Amtrak station data from official GTFS feed.

Downloads Amtrak's GTFS feed and extracts station codes, names, and coordinates
for use in TrackRat's station configuration.

Usage:
    python scripts/generate_amtrak_stations.py

Output:
    Prints Python dictionary entries ready to paste into stations.py
"""

import csv
import io
import urllib.request
import zipfile
from collections import defaultdict

# Amtrak's official GTFS feed URL
GTFS_URL = "https://content.amtrak.com/content/gtfs/GTFS.zip"

# Stations we already have in stations.py (to avoid duplicates)
EXISTING_STATIONS = {
    # NEC and shared NJT stations
    "NYP", "NWK", "TRE", "PJC", "MET", "NBK", "EWR", "WAS", "PHL", "WIL",
    "BAL", "BWI", "BOS", "BBY",
    # Connecticut/New England
    "BPT", "HFD", "MDN", "NHV", "NLC", "OSB", "STM", "WFD", "WNL",
    # Maryland
    "ABE", "NCR",
    # Massachusetts
    "SPG",
    # New Hampshire
    "CLA", "DOV", "DHM", "EXR",
    # Pennsylvania
    "HAR", "LNC",
    # Rhode Island
    "KIN", "PVD", "WLY",
    # Virginia
    "ALX", "CVS", "LOR", "MSS", "NFK", "RVR", "RVM", "RNK",
    # Southeast (already added)
    "CLT", "RGH", "SEL", "WLN", "RMT", "PTB", "SAV", "JES", "JAX",
    "WLD", "OCA", "WTH", "LKL", "TPA", "WPB", "DLB", "FTL", "HLW",
    "MIA", "ORL", "KIS", "WPK", "DLD", "PAL", "SAN", "THU", "CHS",
    "KTR", "FLO", "DIL", "HAM", "SOU", "CAR", "DNC", "GRB", "HPT",
    "SAL", "GAS", "SPB", "GVL", "ATL", "GAI", "TOC", "CSN",
    # Nationwide discovery hubs (already added)
    "CHI", "STL", "MKE", "LAX", "SEA", "PDX", "EMY", "SAC", "NOL", "SAS", "DEN",
    # California / Southwest (already added)
    "SBA", "SLO", "SJC", "OSD", "SNA", "FUL", "OLT", "ABQ", "FLG", "TUS", "ELP", "RNO", "TRU",
    # Pacific Northwest (already added)
    "SPK", "TAC", "EUG", "SLM", "SLC", "WFH", "GPK", "HAV", "MSP",
    # Texas / South Central (already added)
    "DAL", "FTW", "HOS", "AUS", "LRK", "MEM",
    # Midwest / Great Lakes (already added)
    "KCY", "OKC", "OMA", "IND", "CIN", "CLE", "TOL", "DET", "GRR", "PGH",
    # Northeast extensions (already added)
    "ALB", "SYR", "ROC", "BUF", "MTR", "POR", "ESX", "BTN",
    # Virginia / Southeast (already added)
    "LYH", "NPN", "WBG", "CLB", "BHM", "MOE",
    # Codes that conflict with existing NJT/PATH/PATCO
    "ASD", "BRP", "ELT", "GRV", "MJY", "NEW",
}


def download_gtfs():
    """Download and parse Amtrak GTFS feed."""
    print(f"Downloading GTFS from {GTFS_URL}...")

    with urllib.request.urlopen(GTFS_URL, timeout=30) as response:
        data = response.read()

    print(f"Downloaded {len(data)} bytes")

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        # Parse stops.txt
        with zf.open('stops.txt') as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8'))
            stops = list(reader)

        # Parse routes.txt for route information
        with zf.open('routes.txt') as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8'))
            routes = {r['route_id']: r for r in reader}

        # Parse trips.txt to link routes to stops
        with zf.open('trips.txt') as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8'))
            trips = list(reader)

        # Parse stop_times.txt for route-stop relationships
        with zf.open('stop_times.txt') as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8'))
            stop_times = list(reader)

    return stops, routes, trips, stop_times


def categorize_by_region(stations):
    """Categorize stations by geographic region based on coordinates."""
    regions = defaultdict(list)

    for code, name, lat, lon in stations:
        # Simple region detection based on longitude/latitude
        if lon > -80:  # East of Appalachians
            if lat > 42:
                region = "New England"
            elif lat > 39:
                region = "Mid-Atlantic"
            else:
                region = "Southeast"
        elif lon > -90:  # Central
            if lat > 42:
                region = "Great Lakes"
            elif lat > 35:
                region = "Midwest"
            else:
                region = "South Central"
        elif lon > -105:  # Mountain
            region = "Mountain West"
        elif lon > -115:  # Southwest
            if lat > 40:
                region = "Pacific Northwest"
            else:
                region = "Southwest"
        else:  # Pacific
            if lat > 42:
                region = "Pacific Northwest"
            else:
                region = "California"

        regions[region].append((code, name, lat, lon))

    return regions


def main():
    stops, routes, trips, stop_times = download_gtfs()

    # Filter to actual stations (parent stations, not platforms)
    # Amtrak uses stop_id as station code
    stations = []
    seen_codes = set()

    for stop in stops:
        code = stop['stop_id'].strip()
        name = stop['stop_name'].strip()

        # Skip if we already have this station
        if code in EXISTING_STATIONS:
            continue

        # Skip duplicates
        if code in seen_codes:
            continue

        # Skip platform-level entries (usually have parent_station set)
        if stop.get('parent_station', '').strip():
            continue

        try:
            lat = float(stop['stop_lat'])
            lon = float(stop['stop_lon'])
        except (ValueError, KeyError):
            print(f"Warning: Invalid coordinates for {code}: {name}")
            continue

        # Skip invalid coordinates
        if lat == 0 or lon == 0:
            continue

        # Skip bus stops (Amtrak Thruway connections, not rail stations)
        if "Bus Stop" in name or "Thruway" in name:
            continue

        # Clean up station names - remove redundant suffixes
        clean_name = name
        for suffix in [" Amtrak Station", " Amtrak", " Station"]:
            if clean_name.endswith(suffix):
                clean_name = clean_name[:-len(suffix)]
                break

        seen_codes.add(code)
        stations.append((code, clean_name, lat, lon))

    print(f"\nFound {len(stations)} new stations (excluding {len(EXISTING_STATIONS)} existing)")

    # Categorize by region
    regions = categorize_by_region(stations)

    # Print STATION_NAMES additions
    print("\n" + "=" * 80)
    print("# STATION_NAMES additions for stations.py")
    print("# Copy these into the STATION_NAMES dictionary")
    print("=" * 80)

    for region in sorted(regions.keys()):
        print(f"\n    # {region} Amtrak stations")
        for code, name, _, _ in sorted(regions[region], key=lambda x: x[0]):
            # Escape any quotes in station names
            escaped_name = name.replace('"', '\\"')
            print(f'    "{code}": "{escaped_name}",')

    # Print mapping additions (identity mappings for non-NJT stations)
    print("\n" + "=" * 80)
    print("# AMTRAK_TO_INTERNAL_STATION_MAP additions")
    print("# These are identity mappings since they don't overlap with NJT")
    print("=" * 80)

    for region in sorted(regions.keys()):
        print(f"\n    # {region}")
        for code, name, _, _ in sorted(regions[region], key=lambda x: x[0]):
            print(f'    "{code}": "{code}",  # {name}')

    # Print coordinate additions
    print("\n" + "=" * 80)
    print("# STATION_COORDINATES additions for stations.py")
    print("=" * 80)

    for region in sorted(regions.keys()):
        print(f"\n    # {region} Amtrak stations")
        for code, name, lat, lon in sorted(regions[region], key=lambda x: x[0]):
            print(f'    "{code}": {{"lat": {lat:.4f}, "lon": {lon:.4f}}},  # {name}')

    # Print iOS Stations.swift additions
    print("\n" + "=" * 80)
    print("# iOS Stations.swift - stationCodes additions")
    print("=" * 80)

    for region in sorted(regions.keys()):
        print(f"\n        // {region}")
        for code, name, _, _ in sorted(regions[region], key=lambda x: x[0]):
            escaped_name = name.replace('"', '\\"')
            print(f'        "{escaped_name}": "{code}",')

    # Print iOS coordinate additions
    print("\n" + "=" * 80)
    print("# iOS Stations.swift - stationCoordinates additions")
    print("=" * 80)

    for region in sorted(regions.keys()):
        print(f"\n        // {region}")
        for code, name, lat, lon in sorted(regions[region], key=lambda x: x[0]):
            print(f'        "{code}": CLLocationCoordinate2D(latitude: {lat:.4f}, longitude: {lon:.4f}),  // {name}')

    # Print summary
    print("\n" + "=" * 80)
    print("# SUMMARY")
    print("=" * 80)
    print(f"\nTotal new stations: {len(stations)}")
    print("\nBy region:")
    for region in sorted(regions.keys()):
        print(f"  {region}: {len(regions[region])} stations")

    # Print suggested discovery hubs
    print("\n" + "=" * 80)
    print("# SUGGESTED DISCOVERY HUBS")
    print("# Major junction stations that should be added to DISCOVERY_HUBS")
    print("=" * 80)

    major_hubs = [
        ("CHI", "Chicago Union Station"),
        ("LAX", "Los Angeles Union Station"),
        ("SEA", "Seattle King Street Station"),
        ("PDX", "Portland Union Station"),
        ("NOL", "New Orleans Union Passenger Terminal"),
        ("EMY", "Emeryville"),
        ("DEN", "Denver Union Station"),
        ("SAS", "San Antonio"),
        ("SAC", "Sacramento"),
        ("MKE", "Milwaukee Intermodal Station"),
    ]

    print("\nDISCOVERY_HUBS = {")
    print("    # Existing Eastern hubs")
    print('    "NYP", "PHL", "WAS", "BOS", "WIL", "RVR", "CLT",')
    print("    # National expansion hubs")
    for code, name in major_hubs:
        print(f'    "{code}",  # {name}')
    print("}")


if __name__ == "__main__":
    main()
