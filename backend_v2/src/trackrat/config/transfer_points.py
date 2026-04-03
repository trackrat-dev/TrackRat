"""Auto-generated transfer point map for multi-system trip planning.

Transfer points are pairs of stations in different transit systems that are
close enough for a passenger to walk between. They are discovered by:
1. Shared station codes (e.g., NY used by NJT, Amtrak, and LIRR)
2. Existing STATION_EQUIVALENCE_GROUPS (e.g., Amtrak NRO <-> MNR MNRC)
3. Coordinate proximity (stations within WALK_THRESHOLD_METERS of each other)
4. Intra-subway complexes where different subway lines meet (e.g., Union Sq L + 4/5/6)
5. Intra-system junctions where different routes within the same system share a station
   (e.g., PATH Journal Sq where NWK-WTC meets JSQ-33)
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from trackrat.config.route_topology import ALL_ROUTES
from trackrat.config.stations.common import (
    STATION_COORDINATES,
    STATION_EQUIVALENCE_GROUPS,
    STATION_EQUIVALENTS,
    get_station_name,
)
from trackrat.config.stations.subway import SUBWAY_STATION_COMPLEXES

# Maximum walking distance in meters to consider a transfer viable
WALK_THRESHOLD_METERS = 400

# Minimum transfer time in minutes (time to walk + wait)
MIN_TRANSFER_MINUTES = 5

# Walking speed: ~80 meters per minute (brisk urban walk)
WALK_SPEED_METERS_PER_MINUTE = 80


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance between two points in meters."""
    R = 6_371_000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@dataclass(frozen=True)
class TransferPoint:
    """A walking transfer between two stations in different transit systems."""

    station_a: str  # station code in system A
    system_a: str  # data source (e.g., "NJT")
    station_b: str  # station code in system B
    system_b: str
    walk_meters: float  # 0 for same-station transfers
    walk_minutes: int  # estimated walking + buffer time
    same_station: bool  # same physical station (shared code or equivalence)
    # Subway line codes at each side (non-empty only for intra-subway transfers)
    lines_a: frozenset[str] = frozenset()
    lines_b: frozenset[str] = frozenset()

    @property
    def station_a_name(self) -> str:
        return get_station_name(self.station_a)

    @property
    def station_b_name(self) -> str:
        return get_station_name(self.station_b)


def _estimate_walk_minutes(walk_meters: float) -> int:
    """Estimate walk time with a minimum floor."""
    if walk_meters == 0:
        return MIN_TRANSFER_MINUTES
    raw = walk_meters / WALK_SPEED_METERS_PER_MINUTE
    return max(MIN_TRANSFER_MINUTES, math.ceil(raw))


def _build_station_to_systems() -> dict[str, set[str]]:
    """Map each station code to the set of transit systems that serve it."""
    station_systems: dict[str, set[str]] = defaultdict(set)
    for route in ALL_ROUTES:
        for station_code in route.stations:
            station_systems[station_code].add(route.data_source)
    return dict(station_systems)


_STATION_SYSTEMS: dict[str, set[str]] = _build_station_to_systems()


def _build_subway_station_lines() -> dict[str, frozenset[str]]:
    """Map each subway station code to the set of subway line codes serving it."""
    return _build_station_lines_for_system("SUBWAY")


def _build_station_lines_for_system(system: str) -> dict[str, frozenset[str]]:
    """Map each station code to the set of line codes serving it within a system."""
    station_lines: dict[str, set[str]] = defaultdict(set)
    for route in ALL_ROUTES:
        if route.data_source == system:
            for station_code in route.stations:
                station_lines[station_code].update(route.line_codes)
    return {k: frozenset(v) for k, v in station_lines.items()}


_SUBWAY_STATION_LINES: dict[str, frozenset[str]] = _build_subway_station_lines()

# Systems with branching routes that benefit from intra-system transfers.
# Excludes SUBWAY (handled separately via SUBWAY_STATION_COMPLEXES) and
# hub-and-spoke systems where the hub is already a shared station code
# (MNR→GCT, AMTRAK→NY, PATCO single line, WMATA shared core).
_INTRA_TRANSFER_SYSTEMS = ("PATH", "BART", "NJT", "LIRR", "MBTA", "METRA")

_SYSTEM_STATION_LINES: dict[str, dict[str, frozenset[str]]] = {
    system: _build_station_lines_for_system(system)
    for system in _INTRA_TRANSFER_SYSTEMS
}


def _generate_transfer_points() -> tuple[TransferPoint, ...]:
    """Auto-generate all transfer points from station data.

    Three sources of transfer points:
    1. Shared station codes: same code used by multiple systems (NY, GCT, NP, etc.)
    2. Equivalence groups: STATION_EQUIVALENCE_GROUPS (Amtrak/MNR pairs, subway complexes)
    3. Coordinate proximity: stations within WALK_THRESHOLD_METERS across systems
    """
    station_systems = _STATION_SYSTEMS
    seen: set[frozenset[tuple[str, str]]] = set()
    transfers: list[TransferPoint] = []

    def _add(
        code_a: str,
        sys_a: str,
        code_b: str,
        sys_b: str,
        walk_m: float,
        same: bool,
        lines_a: frozenset[str] = frozenset(),
        lines_b: frozenset[str] = frozenset(),
    ) -> None:
        key = frozenset({(code_a, sys_a), (code_b, sys_b)})
        if key not in seen:
            seen.add(key)
            transfers.append(
                TransferPoint(
                    station_a=code_a,
                    system_a=sys_a,
                    station_b=code_b,
                    system_b=sys_b,
                    walk_meters=walk_m,
                    walk_minutes=_estimate_walk_minutes(walk_m),
                    same_station=same,
                    lines_a=lines_a,
                    lines_b=lines_b,
                )
            )

    # --- Source 1: Shared station codes ---
    for code, systems in station_systems.items():
        if len(systems) > 1:
            system_list = sorted(systems)
            for i, sys_a in enumerate(system_list):
                for sys_b in system_list[i + 1 :]:
                    _add(code, sys_a, code, sys_b, 0.0, True)

    # --- Source 2: Equivalence groups (skip subway-only complexes) ---
    for group in STATION_EQUIVALENCE_GROUPS:
        # Find which system each code belongs to
        code_sys_pairs: list[tuple[str, str]] = []
        for code in group:
            for system in station_systems.get(code, set()):
                code_sys_pairs.append((code, system))
        # Create transfer between different-system pairs
        for i, (code_a, sys_a) in enumerate(code_sys_pairs):
            for code_b, sys_b in code_sys_pairs[i + 1 :]:
                if sys_a != sys_b:
                    _add(code_a, sys_a, code_b, sys_b, 0.0, True)

    # --- Source 3: Coordinate proximity ---
    # Build list of (code, system, lat, lon) for all stations with coordinates
    station_coords: list[tuple[str, str, float, float]] = []
    for code, systems in station_systems.items():
        coords = STATION_COORDINATES.get(code)
        if coords:
            for system in systems:
                station_coords.append((code, system, coords["lat"], coords["lon"]))

    # Check pairwise distances across different systems
    for i, (code_a, sys_a, lat_a, lon_a) in enumerate(station_coords):
        for code_b, sys_b, lat_b, lon_b in station_coords[i + 1 :]:
            if sys_a == sys_b:
                continue
            if code_a == code_b:
                continue  # Already handled as shared code
            dist = _haversine_meters(lat_a, lon_a, lat_b, lon_b)
            if dist <= WALK_THRESHOLD_METERS:
                _add(code_a, sys_a, code_b, sys_b, dist, False)

    # --- Source 4: Intra-subway transfers at station complexes ---
    # At each subway complex, pair platform codes serving different line groups.
    # The departure service already expands station equivalences, so these
    # transfer points enable line-change connections within the subway system.
    for complex_stations in SUBWAY_STATION_COMPLEXES:
        codes_with_lines: list[tuple[str, frozenset[str]]] = []
        for code in complex_stations:
            lines = _SUBWAY_STATION_LINES.get(code)
            if lines and code in station_systems and "SUBWAY" in station_systems[code]:
                codes_with_lines.append((code, lines))
        for i, (code_a, lines_a) in enumerate(codes_with_lines):
            for code_b, lines_b in codes_with_lines[i + 1 :]:
                if lines_a != lines_b:  # Different line groups = valid transfer
                    _add(
                        code_a,
                        "SUBWAY",
                        code_b,
                        "SUBWAY",
                        0.0,
                        True,
                        lines_a=lines_a,
                        lines_b=lines_b,
                    )

    # --- Source 5: Intra-system junctions for branching route systems ---
    # At junction stations where different routes within the same system meet,
    # create transfer points so trip search can route across branches.
    # E.g., PATH Journal Sq (PJS) where NWK-WTC meets JSQ-33.
    for system, system_lines in _SYSTEM_STATION_LINES.items():
        # Find stations served by multiple distinct line-code sets
        for station_code, lines in system_lines.items():
            if station_code not in station_systems:
                continue
            if system not in station_systems[station_code]:
                continue
            # Get all routes through this station
            route_groups: list[frozenset[str]] = []
            for route in ALL_ROUTES:
                if (
                    route.data_source == system
                    and station_code in route.stations
                ):
                    if route.line_codes not in route_groups:
                        route_groups.append(route.line_codes)
            # If station is served by 2+ distinct route groups, it's a junction
            if len(route_groups) >= 2:
                # Merge all line codes reachable from each route group
                # into two sides: routes that share codes vs those that don't
                for i, codes_a in enumerate(route_groups):
                    for codes_b in route_groups[i + 1 :]:
                        # Same station, same system, different route groups
                        _add(
                            station_code,
                            system,
                            station_code,
                            system,
                            0.0,
                            True,
                            lines_a=codes_a,
                            lines_b=codes_b,
                        )

    return tuple(sorted(transfers, key=lambda t: (t.system_a, t.system_b, t.station_a)))


# Pre-computed at import time
TRANSFER_POINTS: tuple[TransferPoint, ...] = _generate_transfer_points()

# Lookup indexes
_TRANSFERS_BY_SYSTEM_PAIR: dict[tuple[str, str], list[TransferPoint]] = defaultdict(
    list
)
_TRANSFERS_BY_STATION: dict[str, list[TransferPoint]] = defaultdict(list)

for _tp in TRANSFER_POINTS:
    # Index by both orderings of the system pair
    _TRANSFERS_BY_SYSTEM_PAIR[(_tp.system_a, _tp.system_b)].append(_tp)
    if _tp.system_a != _tp.system_b:
        _TRANSFERS_BY_SYSTEM_PAIR[(_tp.system_b, _tp.system_a)].append(_tp)
    # Index by station code
    _TRANSFERS_BY_STATION[_tp.station_a].append(_tp)
    if _tp.station_a != _tp.station_b:
        _TRANSFERS_BY_STATION[_tp.station_b].append(_tp)


def get_transfer_points(system_a: str, system_b: str) -> list[TransferPoint]:
    """Get all transfer points connecting two transit systems."""
    return _TRANSFERS_BY_SYSTEM_PAIR.get((system_a, system_b), [])


def get_transfers_from_station(station_code: str) -> list[TransferPoint]:
    """Get all transfers available at a given station."""
    return _TRANSFERS_BY_STATION.get(station_code, [])


def get_systems_serving_station(station_code: str) -> set[str]:
    """Get all transit systems that serve a station code."""
    return _STATION_SYSTEMS.get(station_code, set())


def get_subway_lines_at_station(station_code: str) -> frozenset[str]:
    """Get all subway line codes at a station, including equivalent stations.

    Expands station equivalences so that e.g. SG29 (G at Metropolitan Av)
    also returns L lines from its equivalent SL10 (Lorimer St).
    """
    lines: set[str] = set()
    group = STATION_EQUIVALENTS.get(station_code)
    codes = sorted(group) if group else [station_code]
    for code in codes:
        code_lines = _SUBWAY_STATION_LINES.get(code)
        if code_lines:
            lines.update(code_lines)
    return frozenset(lines)


def get_intra_system_transfers(system: str) -> list[TransferPoint]:
    """Get all intra-system transfer points (same system, different lines)."""
    return _TRANSFERS_BY_SYSTEM_PAIR.get((system, system), [])


def get_intra_subway_transfers() -> list[TransferPoint]:
    """Get all intra-subway transfer points (same system, different lines)."""
    return get_intra_system_transfers("SUBWAY")


def get_station_lines(station_code: str, system: str) -> frozenset[str]:
    """Get line codes at a station for a given system.

    For SUBWAY, expands station equivalences. For other systems, direct lookup.
    """
    if system == "SUBWAY":
        return get_subway_lines_at_station(station_code)
    return _SYSTEM_STATION_LINES.get(system, {}).get(station_code, frozenset())
