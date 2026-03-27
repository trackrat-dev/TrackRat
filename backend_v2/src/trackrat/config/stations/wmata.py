"""WMATA (Washington DC Metro) station configuration."""

# WMATA station names - using native WMATA RTU codes directly as internal codes.
# Transfer stations have two codes (one per platform level); both are included.
WMATA_STATION_NAMES: dict[str, str] = {
    # Red Line (A/B branch)
    "A01": "Metro Center",
    "A02": "Farragut North",
    "A03": "Dupont Circle",
    "A04": "Woodley Park-Zoo/Adams Morgan",
    "A05": "Cleveland Park",
    "A06": "Van Ness-UDC",
    "A07": "Tenleytown-AU",
    "A08": "Friendship Heights",
    "A09": "Bethesda",
    "A10": "Medical Center",
    "A11": "Grosvenor-Strathmore",
    "A12": "North Bethesda",
    "A13": "Twinbrook",
    "A14": "Rockville",
    "A15": "Shady Grove",
    "B01": "Gallery Pl-Chinatown",
    "B02": "Judiciary Square",
    "B03": "Union Station",
    "B04": "Rhode Island Ave-Brentwood",
    "B05": "Brookland-CUA",
    "B06": "Fort Totten",
    "B07": "Takoma",
    "B08": "Silver Spring",
    "B09": "Forest Glen",
    "B10": "Wheaton",
    "B11": "Glenmont",
    "B35": "NoMa-Gallaudet U",
    # Blue/Orange/Silver shared (C/D branch)
    "C01": "Metro Center",
    "C02": "McPherson Square",
    "C03": "Farragut West",
    "C04": "Foggy Bottom-GWU",
    "C05": "Rosslyn",
    "C06": "Arlington Cemetery",
    "C07": "Pentagon",
    "C08": "Pentagon City",
    "C09": "Crystal City",
    "C10": "Ronald Reagan Washington National Airport",
    "C11": "Potomac Yard",
    "C12": "Braddock Road",
    "C13": "King St-Old Town",
    "C14": "Eisenhower Avenue",
    "C15": "Huntington",
    # Blue/Orange/Silver east (D branch)
    "D01": "Federal Triangle",
    "D02": "Smithsonian",
    "D03": "L'Enfant Plaza",
    "D04": "Federal Center SW",
    "D05": "Capitol South",
    "D06": "Eastern Market",
    "D07": "Potomac Ave",
    "D08": "Stadium-Armory",
    "D09": "Minnesota Ave",
    "D10": "Deanwood",
    "D11": "Cheverly",
    "D12": "Landover",
    "D13": "New Carrollton",
    # Green/Yellow (E/F branch)
    "E01": "Mt Vernon Sq 7th St-Convention Center",
    "E02": "Shaw-Howard U",
    "E03": "U Street/African-Amer Civil War Memorial/Cardozo",
    "E04": "Columbia Heights",
    "E05": "Georgia Ave-Petworth",
    "E06": "Fort Totten",
    "E07": "West Hyattsville",
    "E08": "Hyattsville Crossing",
    "E09": "College Park-U of Md",
    "E10": "Greenbelt",
    "F01": "Gallery Pl-Chinatown",
    "F02": "Archives-Navy Memorial-Penn Quarter",
    "F03": "L'Enfant Plaza",
    "F04": "Waterfront",
    "F05": "Navy Yard-Ballpark",
    "F06": "Anacostia",
    "F07": "Congress Heights",
    "F08": "Southern Avenue",
    "F09": "Naylor Road",
    "F10": "Suitland",
    "F11": "Branch Ave",
    # Blue/Silver east (G branch)
    "G01": "Benning Road",
    "G02": "Capitol Heights",
    "G03": "Addison Road-Seat Pleasant",
    "G04": "Morgan Boulevard",
    "G05": "Downtown Largo",
    # Blue south (J branch)
    "J02": "Van Dorn Street",
    "J03": "Franconia-Springfield",
    # Orange west (K branch)
    "K01": "Court House",
    "K02": "Clarendon",
    "K03": "Virginia Square-GMU",
    "K04": "Ballston-MU",
    "K05": "East Falls Church",
    "K06": "West Falls Church",
    "K07": "Dunn Loring-Merrifield",
    "K08": "Vienna/Fairfax-GMU",
    # Silver west (N branch)
    "N01": "McLean",
    "N02": "Tysons",
    "N03": "Greensboro",
    "N04": "Spring Hill",
    "N06": "Wiehle-Reston East",
    "N07": "Reston Town Center",
    "N08": "Herndon",
    "N09": "Innovation Center",
    "N10": "Washington Dulles International Airport",
    "N11": "Loudoun Gateway",
    "N12": "Ashburn",
}

# WMATA API station codes are used directly as internal codes (identity mapping).
# The GetPrediction API returns LocationCode/DestinationCode using these same codes.
WMATA_API_TO_INTERNAL_MAP: dict[str, str] = {code: code for code in WMATA_STATION_NAMES}

INTERNAL_TO_WMATA_API_MAP: dict[str, str] = {
    v: k for k, v in WMATA_API_TO_INTERNAL_MAP.items()
}

# Transfer stations: physical stations served by multiple platform levels.
# Each tuple is (primary_code, secondary_code).
# The API returns predictions under both codes depending on the platform.
WMATA_TRANSFER_STATIONS: list[tuple[str, str]] = [
    ("A01", "C01"),  # Metro Center (Red / Blue-Orange-Silver)
    ("B01", "F01"),  # Gallery Pl-Chinatown (Red / Green-Yellow)
    ("B06", "E06"),  # Fort Totten (Red / Green-Yellow)
    ("D03", "F03"),  # L'Enfant Plaza (Blue-Orange-Silver / Green-Yellow)
]

# Line definitions: WMATA line code -> (line_code, display_name, hex_color)
# Colors from official WMATA branding
WMATA_ROUTES: dict[str, tuple[str, str, str]] = {
    "RD": ("RD", "Red Line", "#BF0D3E"),
    "OR": ("OR", "Orange Line", "#ED8B00"),
    "SV": ("SV", "Silver Line", "#919D9D"),
    "BL": ("BL", "Blue Line", "#009CDE"),
    "YL": ("YL", "Yellow Line", "#FFD100"),
    "GR": ("GR", "Green Line", "#00B140"),
}

# Ordered station codes per line (terminus to terminus).
# Transfer stations use the platform code specific to each line.
WMATA_ROUTE_STOPS: dict[str, list[str]] = {
    # Red Line: Shady Grove <-> Glenmont
    "RD": [
        "A15",
        "A14",
        "A13",
        "A12",
        "A11",
        "A10",
        "A09",
        "A08",
        "A07",
        "A06",
        "A05",
        "A04",
        "A03",
        "A02",
        "A01",
        "B35",
        "B01",
        "B02",
        "B03",
        "B04",
        "B05",
        "B06",
        "B07",
        "B08",
        "B09",
        "B10",
        "B11",
    ],
    # Orange Line: Vienna <-> New Carrollton
    "OR": [
        "K08",
        "K07",
        "K06",
        "K05",
        "K04",
        "K03",
        "K02",
        "K01",
        "C05",
        "C04",
        "C03",
        "C02",
        "C01",
        "D01",
        "D02",
        "D03",
        "D04",
        "D05",
        "D06",
        "D07",
        "D08",
        "D09",
        "D10",
        "D11",
        "D12",
        "D13",
    ],
    # Silver Line: Ashburn <-> Downtown Largo
    "SV": [
        "N12",
        "N11",
        "N10",
        "N09",
        "N08",
        "N07",
        "N06",
        "N04",
        "N03",
        "N02",
        "N01",
        "K05",
        "K04",
        "K03",
        "K02",
        "K01",
        "C05",
        "C04",
        "C03",
        "C02",
        "C01",
        "D01",
        "D02",
        "D03",
        "D04",
        "D05",
        "D06",
        "D07",
        "D08",
        "G01",
        "G02",
        "G03",
        "G04",
        "G05",
    ],
    # Blue Line: Franconia-Springfield <-> Downtown Largo
    "BL": [
        "J03",
        "J02",
        "C13",
        "C12",
        "C11",
        "C10",
        "C09",
        "C08",
        "C07",
        "C06",
        "C05",
        "C04",
        "C03",
        "C02",
        "C01",
        "D01",
        "D02",
        "D03",
        "D04",
        "D05",
        "D06",
        "D07",
        "D08",
        "G01",
        "G02",
        "G03",
        "G04",
        "G05",
    ],
    # Yellow Line: Huntington <-> Fort Totten
    # Pentagon (C07) -> L'Enfant Plaza (F03) via Yellow Line bridge
    "YL": [
        "C15",
        "C14",
        "C13",
        "C12",
        "C11",
        "C10",
        "C09",
        "C08",
        "C07",
        "F03",
        "F02",
        "F01",
        "E01",
        "E02",
        "E03",
        "E04",
        "E05",
        "E06",
    ],
    # Green Line: Branch Ave <-> Greenbelt
    "GR": [
        "F11",
        "F10",
        "F09",
        "F08",
        "F07",
        "F06",
        "F05",
        "F04",
        "F03",
        "F02",
        "F01",
        "E01",
        "E02",
        "E03",
        "E04",
        "E05",
        "E06",
        "E07",
        "E08",
        "E09",
        "E10",
    ],
}

# Terminus stations for each line
WMATA_TERMINUS_STATIONS: dict[str, tuple[str, str]] = {
    "RD": ("A15", "B11"),  # Shady Grove, Glenmont
    "OR": ("K08", "D13"),  # Vienna, New Carrollton
    "SV": ("N12", "G05"),  # Ashburn, Downtown Largo
    "BL": ("J03", "G05"),  # Franconia-Springfield, Downtown Largo
    "YL": ("C15", "E06"),  # Huntington, Fort Totten
    "GR": ("F11", "E10"),  # Branch Ave, Greenbelt
}

# Default minutes per segment when GTFS data is unavailable.
# WMATA metro averages ~2 minutes between stations.
DEFAULT_MINUTES_PER_SEGMENT = 2.0


def get_wmata_route_info(line_code: str) -> tuple[str, str, str] | None:
    """Get WMATA route info from line code.

    Args:
        line_code: WMATA line code (e.g., 'RD', 'BL')

    Returns:
        Tuple of (line_code, route_name, color) or None if not mapped
    """
    return WMATA_ROUTES.get(line_code)


def map_wmata_api_stop(api_code: str) -> str | None:
    """Map WMATA API station code to internal code (identity mapping).

    Args:
        api_code: Station code from WMATA API (e.g., 'A01')

    Returns:
        Internal station code or None if not recognized
    """
    return WMATA_API_TO_INTERNAL_MAP.get(api_code)


def get_wmata_route_stops(line_code: str, direction: int | None = None) -> list[str]:
    """Get the ordered list of stops for a WMATA line.

    Args:
        line_code: WMATA line code (e.g., 'RD')
        direction: 1 for normal order, 2 for reverse. None returns normal.

    Returns:
        List of station codes in order
    """
    stops = WMATA_ROUTE_STOPS.get(line_code, [])
    if direction == 2:
        return list(reversed(stops))
    return stops.copy()


def get_wmata_line_for_station(station_code: str) -> list[str]:
    """Get all line codes that serve a station.

    Args:
        station_code: WMATA station code (e.g., 'C05')

    Returns:
        List of line codes (e.g., ['BL', 'OR', 'SV'])
    """
    lines = []
    for line_code, stops in WMATA_ROUTE_STOPS.items():
        if station_code in stops:
            lines.append(line_code)
    return lines


def get_wmata_route_and_stops(
    origin_station: str,
    destination_station: str,
    line_code: str | None = None,
) -> tuple[str, list[str]] | None:
    """Get line code and ordered stops for a WMATA journey.

    Finds the appropriate line by matching origin and destination stations.
    When line_code is provided, uses it directly. Otherwise finds the shortest
    matching route.

    Args:
        origin_station: Station code where train departs
        destination_station: Station code for destination
        line_code: Optional line code for route disambiguation

    Returns:
        Tuple of (line_code, stops) or None if no route found
    """
    candidates: list[tuple[str, list[str]]] = []

    lines_to_check = [line_code] if line_code else list(WMATA_ROUTE_STOPS.keys())

    for lc in lines_to_check:
        stops = WMATA_ROUTE_STOPS.get(lc)
        if not stops:
            continue
        if origin_station in stops and destination_station in stops:
            origin_idx = stops.index(origin_station)
            dest_idx = stops.index(destination_station)
            if origin_idx < dest_idx:
                segment = stops[origin_idx : dest_idx + 1]
            else:
                segment = list(reversed(stops[dest_idx : origin_idx + 1]))
            candidates.append((lc, segment))

    if not candidates:
        return None

    # Prefer specified line, then shortest route
    if len(candidates) == 1:
        return candidates[0]

    candidates.sort(key=lambda c: len(c[1]))
    return candidates[0]


def infer_wmata_origin(
    line_code: str, destination_code: str, direction: int | None = None
) -> str | None:
    """Infer the origin station given a line and destination.

    For a train heading to a destination on a given line, the origin is the
    opposite terminus.

    Args:
        line_code: WMATA line code (e.g., 'RD')
        destination_code: Destination station code
        direction: WMATA direction number (1 or 2), optional

    Returns:
        Inferred origin station code or None
    """
    termini = WMATA_TERMINUS_STATIONS.get(line_code)
    if not termini:
        return None

    stops = WMATA_ROUTE_STOPS.get(line_code, [])
    if not stops:
        return None

    # If destination is the last station, origin is the first (and vice versa)
    if destination_code == stops[-1] or destination_code == termini[1]:
        return stops[0]
    if destination_code == stops[0] or destination_code == termini[0]:
        return stops[-1]

    # For mid-route destinations (e.g., short-turn trains), use direction
    if direction == 1:
        return stops[0]
    if direction == 2:
        return stops[-1]

    # Default: pick the terminus farther from the destination
    if destination_code in stops:
        dest_idx = stops.index(destination_code)
        if dest_idx <= len(stops) // 2:
            return stops[-1]
        else:
            return stops[0]

    return stops[0]
