"""PATH station configuration."""

# PATH station names
PATH_STATION_NAMES: dict[str, str] = {
    # PATH stations (3-char codes to match API constraints)
    "PNK": "Newark PATH",
    "PHR": "Harrison PATH",
    "PJS": "Journal Square",
    "PGR": "Grove Street",
    "PEX": "Exchange Place",
    "PNP": "Newport",
    "PHO": "Hoboken PATH",
    "PCH": "Christopher Street",
    "P9S": "9th Street",
    "P14": "14th Street",
    "P23": "23rd Street",
    "P33": "33rd Street",
    "PWC": "World Trade Center",
}


# PATH Transiter stop ID to internal station code mapping
# IDs verified against live Transiter API 2026-01-18
PATH_TRANSITER_TO_INTERNAL_MAP: dict[str, str] = {
    "26722": "P14",  # 14th Street
    "26723": "P23",  # 23rd Street
    "26724": "P33",  # 33rd Street
    "26725": "P9S",  # 9th Street
    "26726": "PCH",  # Christopher Street
    "26727": "PEX",  # Exchange Place
    "26728": "PGR",  # Grove Street
    "26729": "PHR",  # Harrison
    "26730": "PHO",  # Hoboken
    "26731": "PJS",  # Journal Square
    "26732": "PNP",  # Newport
    "26733": "PNK",  # Newark
    "26734": "PWC",  # World Trade Center
}

# Reverse mapping for PATH
INTERNAL_TO_PATH_TRANSITER_MAP: dict[str, str] = {
    v: k for k, v in PATH_TRANSITER_TO_INTERNAL_MAP.items()
}

# PATH route mappings (Transiter route ID -> line code, name, color)
# Verified against live Transiter API 2026-01-18
PATH_ROUTES: dict[str, tuple[str, str, str]] = {
    "859": ("HOB-33", "Hoboken - 33rd Street", "#4d92fb"),
    "860": ("HOB-WTC", "Hoboken - World Trade Center", "#65c100"),
    "861": ("JSQ-33", "Journal Square - 33rd Street", "#ff9900"),
    "862": ("NWK-WTC", "Newark - World Trade Center", "#d93a30"),
    "1024": ("JSQ-33H", "Journal Square - 33rd Street (via Hoboken)", "#ff9900"),
    "77285": ("WTC-33", "World Trade Center - 33rd Street", "#65c100"),
    "74320": ("NWK-HAR", "Newark - Harrison Shuttle", "#8c3c96"),
}

# PATH route stop sequences (station codes in order from one terminus to the other)
# Used to populate all stops when a train is discovered at a terminus
PATH_ROUTE_STOPS: dict[str, list[str]] = {
    # HOB-33: Hoboken <-> 33rd Street (via 6th Ave)
    "859": ["PHO", "PCH", "P9S", "P14", "P23", "P33"],
    # HOB-WTC: Hoboken <-> World Trade Center
    "860": ["PHO", "PNP", "PEX", "PWC"],
    # JSQ-33: Journal Square <-> 33rd Street (via 6th Ave)
    "861": ["PJS", "PGR", "PNP", "PCH", "P9S", "P14", "P23", "P33"],
    # NWK-WTC: Newark <-> World Trade Center
    "862": ["PNK", "PHR", "PJS", "PGR", "PEX", "PWC"],
    # JSQ-33H: Journal Square <-> 33rd Street via Hoboken
    "1024": ["PJS", "PGR", "PNP", "PHO", "PCH", "P9S", "P14", "P23", "P33"],
    # WTC-33: World Trade Center <-> 33rd Street (same as part of JSQ-33)
    "77285": ["PWC", "PEX", "PNP", "PCH", "P9S", "P14", "P23", "P33"],
    # NWK-HAR: Newark <-> Harrison Shuttle
    "74320": ["PNK", "PHR"],
}

# PATH discovery stations - ONLY terminus stations
# Transiter API only shows trains where the queried station is their destination.
# Mid-route stations won't return useful results.
# Using internal codes (Transiter IDs are in PATH_TRANSITER_TO_INTERNAL_MAP)
PATH_DISCOVERY_STATIONS = [
    "PHO",  # Hoboken terminus (26730) - HOB-33, HOB-WTC, JSQ-33-HOB
    "PWC",  # World Trade Center terminus (26734) - HOB-WTC, NWK-WTC, WTC-33
    "P33",  # 33rd Street terminus (26724) - HOB-33, JSQ-33, JSQ-33-HOB, WTC-33
    "PNK",  # Newark terminus (26733) - NWK-WTC, NWK-HAR origin
]

# PATH GTFS stop name to internal station code mapping
# Used for parsing PATH GTFS schedule data
PATH_GTFS_NAME_TO_INTERNAL_MAP: dict[str, str] = {
    "14th street": "P14",
    "14 st": "P14",
    "23rd street": "P23",
    "23 st": "P23",
    "33rd street": "P33",
    "33 st": "P33",
    "9th street": "P9S",
    "9 st": "P9S",
    "christopher street": "PCH",
    "christopher st": "PCH",
    "exchange place": "PEX",
    "grove street": "PGR",
    "grove st": "PGR",
    "harrison": "PHR",
    "hoboken": "PHO",
    "journal square": "PJS",
    "newport": "PNP",
    "newark": "PNK",
    "newark penn station": "PNK",
    "world trade center": "PWC",
    "wtc": "PWC",
}

# PATH native RidePATH API station codes to internal codes
# The native API uses different codes than Transiter (e.g., "NWK" vs "26733")
# Used by collectors/path/ridepath_client.py for real-time arrival data
PATH_RIDEPATH_API_TO_INTERNAL_MAP: dict[str, str] = {
    "NWK": "PNK",  # Newark
    "HAR": "PHR",  # Harrison
    "JSQ": "PJS",  # Journal Square
    "GRV": "PGR",  # Grove Street
    "NEW": "PNP",  # Newport
    "EXP": "PEX",  # Exchange Place
    "WTC": "PWC",  # World Trade Center
    "HOB": "PHO",  # Hoboken
    "CHR": "PCH",  # Christopher Street
    "09S": "P9S",  # 9th Street
    "14S": "P14",  # 14th Street
    "23S": "P23",  # 23rd Street
    "33S": "P33",  # 33rd Street
}


def get_path_route_stops(route_id: str, terminus_station: str) -> list[str]:
    """Get the ordered list of stops for a PATH route heading to a terminus.

    Args:
        route_id: Transiter route ID (e.g., '859')
        terminus_station: The terminus station code where the train was discovered

    Returns:
        List of station codes in order from origin to destination (terminus)
    """
    stops = PATH_ROUTE_STOPS.get(route_id)
    if not stops:
        return [terminus_station]  # Fallback to just the terminus

    # If terminus is at the end, return as-is
    if stops[-1] == terminus_station:
        return stops.copy()

    # If terminus is at the start, reverse the list
    if stops[0] == terminus_station:
        return list(reversed(stops))

    # Terminus not found at either end - just return terminus
    return [terminus_station]


def get_path_route_and_stops(
    origin_station: str,
    destination_station: str,
    line_color: str | None = None,
) -> tuple[str, list[str]] | None:
    """Get route ID and ordered stops for a PATH journey.

    Finds the appropriate route by matching origin and destination stations
    against all known PATH routes. Returns the route ID and the subset of
    stops from origin to destination (inclusive).

    When line_color is provided, uses it to disambiguate overlapping routes.
    For example, PJS→P33 matches both JSQ-33 (861, orange) and JSQ-33H (1024,
    orange) — but also HOB-33 (859, blue) wouldn't match orange, filtering it
    out. For routes sharing the same color, the longest matching route is
    preferred (JSQ-33H over JSQ-33 when PHO is in the route and travel
    includes it).

    Args:
        origin_station: Station code where train departs (e.g., 'PHO')
        destination_station: Station code for destination (e.g., 'P33')
        line_color: Optional line color for route disambiguation

    Returns:
        Tuple of (route_id, stops) or None if no route found
    """
    # Normalize the provided color for comparison
    normalized_color = None
    if line_color:
        normalized_color = line_color.split(",")[0].strip().lower()
        if not normalized_color.startswith("#"):
            normalized_color = f"#{normalized_color}"

    candidates: list[tuple[str, list[str]]] = []

    for route_id, stops in PATH_ROUTE_STOPS.items():
        if origin_station in stops and destination_station in stops:
            origin_idx = stops.index(origin_station)
            dest_idx = stops.index(destination_station)

            if origin_idx < dest_idx:
                segment = stops[origin_idx : dest_idx + 1]
            else:
                segment = list(reversed(stops[dest_idx : origin_idx + 1]))

            candidates.append((route_id, segment))

    if not candidates:
        return None

    # If only one candidate, return it directly
    if len(candidates) == 1:
        return candidates[0]

    # Multiple candidates — filter by color if available
    if normalized_color and len(candidates) > 1:
        color_filtered = [
            c
            for c in candidates
            if PATH_ROUTES.get(c[0])
            and PATH_ROUTES[c[0]][2].lower() == normalized_color
        ]
        if color_filtered:
            candidates = color_filtered

    # If still multiple candidates, prefer the longest route (most stops)
    # e.g., JSQ-33H (9 stops via Hoboken) over JSQ-33 (8 stops)
    if len(candidates) > 1:
        candidates.sort(key=lambda c: len(PATH_ROUTE_STOPS.get(c[0], [])), reverse=True)

    return candidates[0]


def get_path_stops_by_origin_destination(
    origin_station: str, destination_station: str
) -> list[str] | None:
    """Get ordered stops for a PATH journey from origin to destination.

    Finds the appropriate route by matching origin and destination stations
    against all known PATH routes. Returns the subset of stops from origin
    to destination (inclusive).

    Args:
        origin_station: Station code where train departs (e.g., 'PHO')
        destination_station: Station code for destination (e.g., 'P33')

    Returns:
        List of station codes from origin to destination, or None if no route found
    """
    result = get_path_route_and_stops(origin_station, destination_station)
    if result is None:
        return None
    return result[1]


def map_path_station_code(transiter_stop_id: str) -> str | None:
    """Map PATH Transiter stop ID to our internal code.

    Args:
        transiter_stop_id: Transiter's stop ID (e.g., '26735')

    Returns:
        Our internal station code (e.g., 'PATH_HOB') or None if not mapped
    """
    return PATH_TRANSITER_TO_INTERNAL_MAP.get(transiter_stop_id)


def map_internal_to_path_station(internal_code: str) -> str | None:
    """Map our internal station code to PATH Transiter stop ID.

    Args:
        internal_code: Our internal station code (e.g., 'PATH_HOB')

    Returns:
        Transiter's stop ID (e.g., '26735') or None if not mapped
    """
    return INTERNAL_TO_PATH_TRANSITER_MAP.get(internal_code)


def get_path_route_info(transiter_route_id: str) -> tuple[str, str, str] | None:
    """Get PATH route info from Transiter route ID.

    Args:
        transiter_route_id: Transiter's route ID (e.g., '859')

    Returns:
        Tuple of (line_code, route_name, color) or None if not mapped
    """
    return PATH_ROUTES.get(transiter_route_id)
