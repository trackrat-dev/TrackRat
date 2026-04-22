#!/usr/bin/env python3
"""
One-time script to generate subway station & route data from MTA GTFS static feed.

Downloads the MTA subway GTFS zip, parses stops.txt, routes.txt, trips.txt, and
stop_times.txt, then generates:
  1. Python station data for backend (subway.py)
  2. Swift station data fragments for iOS
  3. Route topology data for both backend and iOS

Usage:
    python3 scripts/generate_subway_data.py [--output-dir /tmp/subway_generated]

Output files are written to --output-dir (default: /tmp/subway_generated/).
Review the output before pasting into the codebase.
"""

import argparse
import csv
import io
import os
import re
import urllib.request
import zipfile
from collections import defaultdict

GTFS_URL = "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_supplemented.zip"

# Route colors from official MTA branding (hex without #)
# The GTFS file has slightly different colors; we use official MTA bullet colors.
OFFICIAL_ROUTE_COLORS = {
    "1": "EE352E", "2": "EE352E", "3": "EE352E",
    "4": "00933C", "5": "00933C", "6": "00933C", "6X": "00933C",
    "7": "B933AD", "7X": "B933AD",
    "A": "0039A6", "C": "0039A6", "E": "0039A6",
    "B": "FF6319", "D": "FF6319", "F": "FF6319", "FX": "FF6319", "M": "FF6319",
    "G": "6CBE45",
    "J": "996633", "Z": "996633",
    "L": "A7A9AC",
    "N": "FCCC0A", "Q": "FCCC0A", "R": "FCCC0A", "W": "FCCC0A",
    "GS": "808183", "FS": "808183", "H": "808183",
    "SI": "1D2E86",
}

# Human-readable route display names
ROUTE_DISPLAY_NAMES = {
    "1": "1 Broadway-7th Ave Local",
    "2": "2 7th Ave Express",
    "3": "3 7th Ave Express",
    "4": "4 Lexington Ave Express",
    "5": "5 Lexington Ave Express",
    "6": "6 Lexington Ave Local",
    "6X": "6 Pelham Express",
    "7": "7 Flushing Local",
    "7X": "7 Flushing Express",
    "A": "A 8th Ave Express",
    "C": "C 8th Ave Local",
    "E": "E 8th Ave Local",
    "B": "B 6th Ave Express",
    "D": "D 6th Ave Express",
    "F": "F Queens Blvd Express/6th Ave Local",
    "FX": "F Brooklyn Express",
    "M": "M Queens Blvd Local/6th Ave Local",
    "G": "G Brooklyn-Queens Crosstown",
    "J": "J Nassau St Local",
    "Z": "Z Nassau St Express",
    "L": "L 14th St-Canarsie Local",
    "N": "N Broadway Local",
    "Q": "Q Broadway Express",
    "R": "R Broadway Local",
    "W": "W Broadway Local",
    "GS": "S 42nd St Shuttle",
    "FS": "S Franklin Ave Shuttle",
    "H": "S Rockaway Park Shuttle",
    "SI": "SIR Staten Island Railway",
}


def download_and_extract(url: str, cache_path: str = "/tmp/gtfs_subway.zip") -> dict[str, list[dict]]:
    """Download GTFS zip and parse CSV files into dicts."""
    if not os.path.exists(cache_path):
        print(f"Downloading {url}...")
        urllib.request.urlretrieve(url, cache_path)
    else:
        print(f"Using cached {cache_path}")

    data = {}
    with zipfile.ZipFile(cache_path) as zf:
        for name in ["stops.txt", "routes.txt", "trips.txt", "stop_times.txt", "transfers.txt"]:
            print(f"  Parsing {name}...")
            with zf.open(name) as f:
                text = io.TextIOWrapper(f, encoding="utf-8-sig")
                data[name.replace(".txt", "")] = list(csv.DictReader(text))
    return data


def build_station_data(stops: list[dict]) -> list[dict]:
    """Extract parent stations with S-prefix internal codes."""
    stations = []
    for stop in stops:
        if stop["location_type"] != "1":
            continue
        gtfs_id = stop["stop_id"]
        # Internal code: prefix with S (SIR stops S01-S31 become SS01-SS31)
        internal_code = f"S{gtfs_id}"
        stations.append({
            "gtfs_id": gtfs_id,
            "code": internal_code,
            "name": stop["stop_name"],
            "lat": float(stop["stop_lat"]),
            "lon": float(stop["stop_lon"]),
        })
    stations.sort(key=lambda s: s["code"])
    return stations


def build_route_data(routes: list[dict]) -> list[dict]:
    """Build route info from GTFS routes.txt with official colors."""
    result = []
    for route in routes:
        route_id = route["route_id"]
        color = OFFICIAL_ROUTE_COLORS.get(route_id, route["route_color"])
        display_name = ROUTE_DISPLAY_NAMES.get(route_id, f"{route_id} {route['route_long_name']}")
        result.append({
            "route_id": route_id,
            "line_code": route_id,
            "display_name": display_name,
            "color": f"#{color}",
        })
    result.sort(key=lambda r: r["route_id"])
    return result


def build_route_stop_sequences(trips: list[dict], stop_times: list[dict], stations: list[dict]) -> dict:
    """Build ordered station sequences for each route from stop_times.

    Returns dict of route_id -> list of internal station codes in order.
    We pick the longest trip per route/direction to get the full sequence.
    """
    gtfs_to_internal = {s["gtfs_id"]: s["code"] for s in stations}

    # Group stop_times by trip_id
    trip_stops: dict[str, list[dict]] = defaultdict(list)
    for st in stop_times:
        trip_stops[st["trip_id"]].append(st)

    # Group trips by (route_id, direction_id)
    trip_by_route_dir: dict[tuple, list[str]] = defaultdict(list)
    for trip in trips:
        key = (trip["route_id"], trip.get("direction_id", "0"))
        trip_by_route_dir[key].append(trip["trip_id"])

    # For each route+direction, find the trip with the most stops
    route_sequences: dict[str, list[str]] = {}
    for (route_id, direction_id), trip_ids in trip_by_route_dir.items():
        best_trip_id = None
        best_count = 0
        for tid in trip_ids[:200]:  # Sample first 200 trips for speed
            count = len(trip_stops.get(tid, []))
            if count > best_count:
                best_count = count
                best_trip_id = tid

        if best_trip_id:
            stops_sorted = sorted(trip_stops[best_trip_id], key=lambda s: int(s["stop_sequence"]))
            codes = []
            for s in stops_sorted:
                # Strip N/S directional suffix to get parent station
                stop_id = s["stop_id"]
                parent_id = stop_id.rstrip("NS") if stop_id[-1] in ("N", "S") else stop_id
                code = gtfs_to_internal.get(parent_id)
                if code and code not in codes:  # Deduplicate
                    codes.append(code)

            key = f"{route_id}_d{direction_id}"
            if key not in route_sequences or len(codes) > len(route_sequences[key]):
                route_sequences[key] = codes

    return route_sequences


def build_station_complexes(transfers: list[dict], stations: list[dict]) -> list[set[str]]:
    """Build connected components of station complexes from transfers.txt.

    Filters for transfer_type=2 (in-station transfers between platform complexes)
    and groups parent stations that share physical connections into equivalence sets.
    Returns only groups with 2+ members (single stations need no equivalence).
    """
    gtfs_to_internal = {s["gtfs_id"]: s["code"] for s in stations}

    # Build adjacency from transfer_type=2 (timed transfer between stops)
    adjacency: dict[str, set[str]] = defaultdict(set)
    for transfer in transfers:
        if transfer.get("transfer_type") != "2":
            continue
        from_id = transfer["from_stop_id"]
        to_id = transfer["to_stop_id"]
        if from_id == to_id:
            continue
        # Only consider parent stations (those in our station map)
        from_code = gtfs_to_internal.get(from_id)
        to_code = gtfs_to_internal.get(to_id)
        if from_code and to_code and from_code != to_code:
            adjacency[from_code].add(to_code)
            adjacency[to_code].add(from_code)

    # Manual overrides: station pairs that should be grouped but are missing
    # from transfers.txt (MTA omits some in-station transfers).
    MANUAL_COMPLEX_MERGES: list[set[str]] = [
        {"S128", "SA28"},   # 34 St-Penn Station (1/2/3 + A/C/E)
        {"S230", "S419"},   # Wall St (2/3 + 4/5)
        {"S139", "SR26"},   # Rector St (1 + N/R/W)
        {"SA11", "SD12"},   # 155 St (A/C + B/D)
    ]
    for group in MANUAL_COMPLEX_MERGES:
        codes = list(group)
        for i in range(len(codes)):
            for j in range(i + 1, len(codes)):
                adjacency[codes[i]].add(codes[j])
                adjacency[codes[j]].add(codes[i])

    # Find connected components via BFS
    visited: set[str] = set()
    complexes: list[set[str]] = []
    for code in adjacency:
        if code in visited:
            continue
        component: set[str] = set()
        queue = [code]
        while queue:
            current = queue.pop()
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            for neighbor in adjacency.get(current, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        if len(component) >= 2:
            complexes.append(component)

    complexes.sort(key=lambda s: min(s))
    return complexes


# Curated display names for complexes where the default (first code's stripped name)
# isn't the best choice. Key: frozenset of station codes → chosen display name.
# Complexes not listed here use the stripped name of their first (sorted) member.
# These frozensets must match the actual output of build_station_complexes().
COMPLEX_DISPLAY_NAMES: dict[frozenset[str], str] = {
    frozenset({"S228", "SA36", "SE01", "SR25"}): "Chambers St-WTC",  # Park Place / Chambers St / WTC / Cortlandt St → searchable
    frozenset({"S112", "SA09"}): "168 St",                        # 168 St-Washington Hts / 168 St → shorter
    frozenset({"S239", "SS04"}): "Franklin Av",                   # Franklin Av-Medgar Evers College / Botanic Garden → shorter
    frozenset({"S254", "SL26"}): "Livonia Av",                    # Junius St / Livonia Av → L train name more prominent
    frozenset({"S629", "SB08", "SR11"}): "Lexington Av/59 St",   # 59 St / Lex-63 St / Lex-59 St → standard name
    frozenset({"S630", "SF11"}): "Lexington Av/53 St",            # 51 St / Lex-53 St → standard name
    frozenset({"S637", "SD21"}): "Broadway-Lafayette St",          # Bleecker St / Broadway-Lafayette St → more prominent
    frozenset({"S710", "SG14"}): "Jackson Hts-Roosevelt Av",      # 74 St-Broadway / Jackson Hts-Roosevelt Av
    frozenset({"S724", "SD16"}): "42 St-Bryant Pk",               # 5 Av / 42 St-Bryant Pk → more prominent
    frozenset({"SB16", "SN04"}): "New Utrecht Av",                # 62 St / New Utrecht Av → more recognizable
}


def strip_route_suffix(name: str) -> str:
    """Strip trailing route suffix like '(1/2/3)' or '(A/C/E)' from station name.

    Also handles patterns like '(SA63)' station code suffixes and ' - 1' style suffixes.
    """
    # Strip " (X/Y/Z)" or " (X)" style suffixes where contents are route letters/numbers/slashes
    name = re.sub(r"\s*\([A-Za-z0-9/]+\)\s*$", "", name)
    # Strip " - X" style suffixes (e.g., "Cathedral Pkwy (110 St) - 1")
    name = re.sub(r"\s*-\s*[A-Z0-9/]+\s*$", "", name)
    return name.strip()


def build_consolidated_stations(
    stations: list[dict], complexes: list[set[str]]
) -> list[dict]:
    """Build consolidated station list: one entry per complex + standalone stations.

    Returns list of dicts with keys:
      - name: display name (route suffix stripped)
      - canonical_code: the code to use in stationCodes
      - all_codes: set of all codes in this group (for equivalence mapping)
    """
    code_to_station = {s["code"]: s for s in stations}

    # Build code → complex mapping
    code_to_complex: dict[str, set[str]] = {}
    for group in complexes:
        for code in group:
            code_to_complex[code] = group

    consolidated = []
    seen_codes: set[str] = set()

    for group in complexes:
        frozen = frozenset(group)
        # Use curated name if available, otherwise strip suffix from first station
        if frozen in COMPLEX_DISPLAY_NAMES:
            display_name = COMPLEX_DISPLAY_NAMES[frozen]
        else:
            # Pick the name from the first code (sorted) and strip suffix
            first_code = sorted(group)[0]
            display_name = strip_route_suffix(code_to_station[first_code]["name"])

        canonical_code = sorted(group)[0]  # Alphabetically first code
        consolidated.append({
            "name": display_name,
            "canonical_code": canonical_code,
            "all_codes": group,
        })
        seen_codes.update(group)

    # Add standalone stations
    for s in stations:
        if s["code"] not in seen_codes:
            consolidated.append({
                "name": strip_route_suffix(s["name"]),
                "canonical_code": s["code"],
                "all_codes": {s["code"]},
            })

    consolidated.sort(key=lambda e: e["canonical_code"])
    return consolidated


# Manual additions to the GTFS-derived station_routes mapping.
# Used where MTA's GTFS static feed misses service patterns that are genuinely
# present in the real world (e.g., platforms shared by multiple routes where
# only one shows up in the static schedule sample).
MANUAL_STATION_ROUTE_ADDITIONS: dict[str, set[str]] = {
    # Canal St BMT Broadway express/bridge platform: both N (via Manhattan
    # Bridge during weekday daytime) and Q use it; GTFS static only lists Q.
    "SQ01": {"N"},
}


def build_station_routes(
    trips: list[dict], stop_times: list[dict], stations: list[dict]
) -> dict[str, set[str]]:
    """Build mapping of internal station code → set of route IDs that serve it."""
    gtfs_to_internal = {s["gtfs_id"]: s["code"] for s in stations}

    # trip_id → route_id
    trip_route: dict[str, str] = {}
    for trip in trips:
        trip_route[trip["trip_id"]] = trip["route_id"]

    station_routes: dict[str, set[str]] = defaultdict(set)
    for st in stop_times:
        route_id = trip_route.get(st["trip_id"])
        if not route_id:
            continue
        stop_id = st["stop_id"]
        parent_id = stop_id.rstrip("NS") if stop_id[-1] in ("N", "S") else stop_id
        code = gtfs_to_internal.get(parent_id)
        if code:
            station_routes[code].add(route_id)

    for code, extra_routes in MANUAL_STATION_ROUTE_ADDITIONS.items():
        station_routes[code].update(extra_routes)

    return dict(station_routes)


def _format_route_suffix(routes: set[str]) -> str | None:
    """Format a set of route IDs into a display suffix like '1/2/3' or 'A/B/C'.

    Filters out express variants (6X, 7X, FX) since the base route is already present.
    Returns None if no displayable routes remain.
    """
    display_routes = {r for r in routes if not r.endswith("X")}
    if not display_routes:
        return None
    # Sort: numbers first (ascending), then letters (alphabetical)
    sorted_routes = sorted(
        display_routes,
        key=lambda r: (not r[0].isdigit(), int(r) if r.isdigit() else 0, r),
    )
    return "/".join(sorted_routes)


def resolve_name_collisions(
    consolidated: list[dict], station_routes: dict[str, set[str]]
) -> None:
    """Add minimal route suffixes to disambiguate entries sharing the same display name.

    Uses actual route-serving data (which lines stop at each station) to build
    human-readable suffixes like "(1/2/3)" or "(A/C/E)".
    """
    # Group by display name
    name_groups: dict[str, list[dict]] = defaultdict(list)
    for entry in consolidated:
        name_groups[entry["name"]].append(entry)

    for name, entries in name_groups.items():
        if len(entries) <= 1:
            continue
        # Multiple entries share this name — disambiguate with route info
        for entry in entries:
            # Collect all routes serving any station in this group
            routes: set[str] = set()
            for code in entry["all_codes"]:
                routes.update(station_routes.get(code, set()))

            suffix = _format_route_suffix(routes)
            if suffix:
                entry["name"] = f"{name} ({suffix})"
            else:
                # No route info available — use canonical code as fallback
                entry["name"] = f"{name} ({entry['canonical_code']})"


def resolve_backend_name_collisions(
    stations: list[dict], station_routes: dict[str, set[str]]
) -> None:
    """Add route suffixes to backend station names where GTFS names collide.

    Most GTFS station names already include route suffixes (e.g., '96 St (1/2/3)'),
    but a few don't (e.g., '104 St' on the A line). This resolves those remaining
    collisions using actual route-serving data instead of station codes.
    """
    name_groups: dict[str, list[dict]] = defaultdict(list)
    for station in stations:
        name_groups[station["name"]].append(station)

    for name, entries in name_groups.items():
        if len(entries) <= 1:
            continue
        for entry in entries:
            routes = station_routes.get(entry["code"], set())
            suffix = _format_route_suffix(routes)
            if suffix:
                entry["name"] = f"{name} ({suffix})"
            else:
                entry["name"] = f"{name} ({entry['code']})"


def generate_python_stations(
    stations: list[dict], routes: list[dict], route_sequences: dict,
    complexes: list[set[str]] | None = None,
) -> str:
    """Generate Python source for subway.py station data."""
    lines = [
        '"""',
        "NYC Subway station and route configuration.",
        "",
        "Auto-generated by scripts/generate_subway_data.py from MTA GTFS static feed.",
        "Do not edit manually.",
        '"""',
        "",
        "",
        "# GTFS-RT feed URLs for all subway line groups",
        "SUBWAY_GTFS_RT_FEED_URLS: dict[str, str] = {",
        '    "1234567S": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs",',
        '    "ACE": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace",',
        '    "BDFM": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm",',
        '    "G": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-g",',
        '    "JZ": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-jz",',
        '    "L": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-l",',
        '    "NQRW": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw",',
        '    "SIR": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-si",',
        "}",
        "",
        "# GTFS static feed URL",
        'SUBWAY_GTFS_STATIC_URL = "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_supplemented.zip"',
        "",
        "",
    ]

    # Station names
    lines.append("# Station code -> display name")
    lines.append("SUBWAY_STATION_NAMES: dict[str, str] = {")
    for s in stations:
        lines.append(f'    "{s["code"]}": "{s["name"]}",')
    lines.append("}")
    lines.append("")
    lines.append("")

    # GTFS stop to internal map
    lines.append("# GTFS parent station ID -> internal station code")
    lines.append("SUBWAY_GTFS_STOP_TO_INTERNAL_MAP: dict[str, str] = {")
    for s in stations:
        lines.append(f'    "{s["gtfs_id"]}": "{s["code"]}",')
    lines.append("}")
    lines.append("")
    lines.append("")

    # Reverse map
    lines.append("# Internal station code -> GTFS parent station ID")
    lines.append("INTERNAL_TO_SUBWAY_GTFS_STOP_MAP: dict[str, str] = {")
    for s in stations:
        lines.append(f'    "{s["code"]}": "{s["gtfs_id"]}",')
    lines.append("}")
    lines.append("")
    lines.append("")

    # Routes
    lines.append("# GTFS route_id -> (line_code, display_name, color_hex)")
    lines.append("SUBWAY_ROUTES: dict[str, tuple[str, str, str]] = {")
    for r in routes:
        lines.append(f'    "{r["route_id"]}": ("{r["line_code"]}", "{r["display_name"]}", "{r["color"]}"),')
    lines.append("}")
    lines.append("")
    lines.append("")

    # Discovery stations (major hubs)
    lines.append("# Major hub stations for discovery/monitoring")
    lines.append("SUBWAY_DISCOVERY_STATIONS: list[str] = [")
    hubs = [
        ("S127", "Times Sq-42 St"),
        ("S635", "14 St-Union Sq"),
        ("SD24", "Atlantic Av-Barclays Ctr"),
        ("SA38", "Fulton St"),
        ("SD17", "34 St-Herald Sq"),
        ("SA41", "Jay St-MetroTech"),
        ("S225", "125 St"),
        ("SG14", "Jackson Hts-Roosevelt Av"),
        ("S701", "Flushing-Main St"),
        ("SA24", "59 St-Columbus Circle"),
    ]
    # Verify hub codes match actual station names
    station_names = {s["code"]: s["name"] for s in stations}
    for code, expected in hubs:
        actual = station_names.get(code)
        if actual is None:
            print(f"  WARNING: Hub code {code} not found in station data")
        elif expected.lower() not in actual.lower():
            print(f"  WARNING: Hub {code} expected '{expected}' but found '{actual}'")

    for code, name in hubs:
        lines.append(f'    "{code}",  # {name}')
    lines.append("]")
    lines.append("")
    lines.append("")

    # Station coordinates
    lines.append("# Station code -> (latitude, longitude)")
    lines.append("SUBWAY_STATION_COORDINATES: dict[str, tuple[float, float]] = {")
    for s in stations:
        lines.append(f'    "{s["code"]}": ({s["lat"]}, {s["lon"]}),')
    lines.append("}")
    lines.append("")
    lines.append("")

    # Station complexes (groups of platform codes at the same physical station)
    if complexes:
        lines.append("# Station complexes: groups of platform codes at the same physical station.")
        lines.append("# Used by STATION_EQUIVALENTS to aggregate departures across platforms.")
        lines.append("SUBWAY_STATION_COMPLEXES: list[set[str]] = [")
        for group in complexes:
            sorted_codes = sorted(group)
            codes_str = ", ".join(f'"{c}"' for c in sorted_codes)
            # Add comment with station names for readability
            names = sorted(set(
                next((s["name"] for s in stations if s["code"] == c), c)
                for c in sorted_codes
            ))
            comment = " / ".join(names)
            lines.append(f"    {{{codes_str}}},  # {comment}")
        lines.append("]")
    else:
        lines.append("SUBWAY_STATION_COMPLEXES: list[set[str]] = []")
    lines.append("")
    lines.append("")

    # Helper functions
    lines.extend([
        "",
        "def map_subway_gtfs_stop(gtfs_stop_id: str) -> str | None:",
        '    """Map a GTFS stop ID (possibly with N/S suffix) to internal station code."""',
        "    # Strip directional suffix (e.g., '101N' -> '101')",
        '    parent_id = gtfs_stop_id.rstrip("NS") if gtfs_stop_id[-1:] in ("N", "S") else gtfs_stop_id',
        "    return SUBWAY_GTFS_STOP_TO_INTERNAL_MAP.get(parent_id)",
        "",
        "",
        "def get_subway_route_info(route_id: str) -> tuple[str, str, str] | None:",
        '    """Get (line_code, display_name, color) for a subway route."""',
        "    return SUBWAY_ROUTES.get(route_id)",
        "",
    ])

    return "\n".join(lines)


def generate_python_coordinates(stations: list[dict]) -> str:
    """Generate Python dict entries for STATION_COORDINATES in common.py."""
    lines = ["# Subway station coordinates (add to STATION_COORDINATES)"]
    for s in stations:
        lines.append(
            f'    "{s["code"]}": {{"lat": {s["lat"]}, "lon": {s["lon"]}}},'
        )
    return "\n".join(lines)


def generate_swift_station_data(stations: list[dict]) -> str:
    """Generate Swift entries for StationData.swift (unconsolidated, one per GTFS station)."""
    lines = [
        "// MARK: - Subway Stations",
        "// Auto-generated by scripts/generate_subway_data.py",
        "",
        "// Add to Stations.all array:",
    ]
    for s in stations:
        name = s["name"].replace('"', '\\"')
        lines.append(f'    "{name}",')

    lines.append("")
    lines.append("// Add to Stations.stationCodes dict:")
    for s in stations:
        name = s["name"].replace('"', '\\"')
        lines.append(f'    "{name}": "{s["code"]}",')

    lines.append("")
    lines.append("// Add to Stations.stationCodeToName dict:")
    for s in stations:
        name = s["name"].replace('"', '\\"')
        lines.append(f'    "{s["code"]}": "{name}",')

    return "\n".join(lines)


def generate_swift_consolidated_station_data(
    consolidated: list[dict],
) -> str:
    """Generate consolidated Swift entries for StationData.swift.

    Produces three sections:
    1. Stations.all — one entry per consolidated station
    2. stationCodes — consolidated name → canonical code
    3. stationCodeToName equivalents — maps non-canonical codes → canonical code's name
    """
    lines = [
        "// MARK: - Consolidated Subway Stations",
        "// Auto-generated by scripts/generate_subway_data.py",
        "// Complexes are consolidated into single entries; backend expand_station_codes() handles expansion.",
        "",
        "// ---- Stations.all array entries ----",
    ]
    for entry in consolidated:
        name = entry["name"].replace('"', '\\"')
        lines.append(f'        "{name}",')

    lines.append("")
    lines.append("// ---- stationCodes dict entries ----")
    for entry in consolidated:
        name = entry["name"].replace('"', '\\"')
        lines.append(f'        "{name}": "{entry["canonical_code"]}",')

    lines.append("")
    lines.append("// ---- stationCodeToName subway complex equivalents ----")
    lines.append("// Add inside stationCodeToName computed property, after amtrakEquivalents block.")
    lines.append("// Maps non-canonical complex codes to the canonical code so all resolve to the same name.")
    lines.append("        let subwayComplexEquivalents: [(alternateCode: String, canonicalCode: String)] = [")
    for entry in consolidated:
        if len(entry["all_codes"]) <= 1:
            continue
        canonical = entry["canonical_code"]
        for code in sorted(entry["all_codes"]):
            if code != canonical:
                name = entry["name"].replace('"', '\\"')
                lines.append(f'            ("{code}", "{canonical}"),  // {name}')
    lines.append("        ]")
    lines.append("        for (alternateCode, canonicalCode) in subwayComplexEquivalents {")
    lines.append("            if let name = result[canonicalCode] {")
    lines.append("                result[alternateCode] = name")
    lines.append("            }")
    lines.append("        }")

    return "\n".join(lines)


def generate_swift_coordinates(stations: list[dict]) -> str:
    """Generate Swift entries for StationCoordinates.swift."""
    lines = [
        "// MARK: - Subway Station Coordinates",
        "// Auto-generated by scripts/generate_subway_data.py",
        "",
        "// Add to Stations.stationCoordinates dict:",
    ]
    for s in stations:
        lines.append(
            f'    "{s["code"]}": CLLocationCoordinate2D(latitude: {s["lat"]}, longitude: {s["lon"]}),'
        )
    return "\n".join(lines)


def generate_route_topology_python(routes: list[dict], route_sequences: dict) -> str:
    """Generate Python Route definitions for route_topology.py."""
    lines = [
        "# Subway routes for route_topology.py",
        "# Auto-generated by scripts/generate_subway_data.py",
        "",
    ]

    for r in routes:
        route_id = r["route_id"]
        var_name = f"SUBWAY_{route_id.replace('X', '_EXPRESS')}"

        # Find direction 0 sequence (southbound/inbound is typically direction 0)
        seq_key = f"{route_id}_d0"
        seq = route_sequences.get(seq_key, [])
        if not seq:
            seq_key = f"{route_id}_d1"
            seq = route_sequences.get(seq_key, [])

        if not seq:
            lines.append(f"# WARNING: No stop sequence found for route {route_id}")
            continue

        lines.append(f'{var_name} = Route(')
        lines.append(f'    name="{r["display_name"]}",')
        lines.append(f'    line_code="{r["line_code"]}",')
        lines.append(f'    data_source="SUBWAY",')
        lines.append(f'    color="{r["color"]}",')
        lines.append(f"    stations=(")
        for code in seq:
            lines.append(f'        "{code}",')
        lines.append(f"    ),")
        lines.append(f")")
        lines.append("")

    return "\n".join(lines)


def generate_swift_route_topology(routes: list[dict], route_sequences: dict, stations: list[dict]) -> str:
    """Generate Swift RouteLine entries for RouteTopology.swift."""
    station_map = {s["code"]: s for s in stations}
    lines = [
        "// MARK: - Subway Routes",
        "// Auto-generated by scripts/generate_subway_data.py",
        "",
    ]

    for r in routes:
        route_id = r["route_id"]
        seq_key = f"{route_id}_d0"
        seq = route_sequences.get(seq_key, [])
        if not seq:
            seq_key = f"{route_id}_d1"
            seq = route_sequences.get(seq_key, [])
        if not seq:
            continue

        # Build coordinate pairs
        coord_pairs = []
        for code in seq:
            s = station_map.get(code)
            if s:
                coord_pairs.append(f'        ({s["lat"]}, {s["lon"]})')

        var_name = f"subway{route_id.replace('X', 'Express')}"
        color = r["color"]

        lines.append(f'static let {var_name} = RouteLine(')
        lines.append(f'    name: "{r["display_name"]}",')
        lines.append(f'    lineCode: "{r["line_code"]}",')
        lines.append(f'    dataSource: "SUBWAY",')
        lines.append(f'    color: "{color}",')
        lines.append(f'    coordinates: [')
        lines.append(",\n".join(coord_pairs))
        lines.append(f'    ]')
        lines.append(f')')
        lines.append("")

    return "\n".join(lines)


def generate_discovery_station_verification(stations: list[dict]) -> str:
    """Print discovery station code verification."""
    name_to_code = {}
    for s in stations:
        name_to_code[s["name"]] = s["code"]

    hub_names = [
        "Times Sq-42 St",
        "14 St-Union Sq",
        "Atlantic Av-Barclays Ctr",
        "Fulton St",
        "34 St-Herald Sq",
        "Jay St-MetroTech",
        "125 St",
        "Jackson Hts-Roosevelt Av",
        "Flushing-Main St",
        "59 St-Columbus Circle",
    ]

    lines = ["Discovery station verification:"]
    for name in hub_names:
        matches = [(s["code"], s["name"]) for s in stations if name.lower() in s["name"].lower()]
        lines.append(f"  {name}:")
        for code, full_name in matches:
            lines.append(f"    {code}: {full_name}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate subway station data from MTA GTFS")
    parser.add_argument("--output-dir", default="/tmp/subway_generated", help="Output directory")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Download and parse GTFS
    data = download_and_extract(GTFS_URL)

    # Build station data
    stations = build_station_data(data["stops"])
    print(f"\nFound {len(stations)} parent stations")

    # Build route data
    routes = build_route_data(data["routes"])
    print(f"Found {len(routes)} routes")

    # Build route stop sequences
    print("Building route stop sequences (this may take a moment)...")
    route_sequences = build_route_stop_sequences(data["trips"], data["stop_times"], stations)
    print(f"Built {len(route_sequences)} route/direction sequences")

    # Build station complexes from transfers
    complexes = build_station_complexes(data["transfers"], stations)
    print(f"Found {len(complexes)} station complexes (multi-platform groups)")

    # Build station routes mapping (used for name collision resolution)
    station_routes = build_station_routes(data["trips"], data["stop_times"], stations)

    # Resolve backend name collisions (GTFS names like "104 St" that lack route suffixes)
    resolve_backend_name_collisions(stations, station_routes)

    # Build consolidated stations for iOS
    consolidated = build_consolidated_stations(stations, complexes)
    resolve_name_collisions(consolidated, station_routes)
    print(f"Consolidated to {len(consolidated)} station entries "
          f"({len(stations) - len(consolidated)} fewer than raw GTFS)")

    # Verify discovery stations
    print()
    print(generate_discovery_station_verification(stations))

    # Generate outputs
    outputs = {
        "subway.py": generate_python_stations(stations, routes, route_sequences, complexes),
        "subway_coordinates.py": generate_python_coordinates(stations),
        "StationData_subway.swift": generate_swift_station_data(stations),
        "StationData_subway_consolidated.swift": generate_swift_consolidated_station_data(consolidated),
        "StationCoordinates_subway.swift": generate_swift_coordinates(stations),
        "route_topology_subway.py": generate_route_topology_python(routes, route_sequences),
        "RouteTopology_subway.swift": generate_swift_route_topology(routes, route_sequences, stations),
    }

    for filename, content in outputs.items():
        path = os.path.join(args.output_dir, filename)
        with open(path, "w") as f:
            f.write(content)
        line_count = content.count("\n") + 1
        print(f"  Wrote {path} ({line_count} lines)")

    print(f"\nDone! Review files in {args.output_dir}/")


if __name__ == "__main__":
    main()
