"""BART (Bay Area Rapid Transit) station configuration."""

# BART station names — all prefixed with BART_ to avoid collisions
BART_STATION_NAMES: dict[str, str] = {
    "BART_12TH": "12th St. Oakland City Center",
    "BART_16TH": "16th St. Mission",
    "BART_19TH": "19th St. Oakland",
    "BART_24TH": "24th St. Mission",
    "BART_ANTC": "Antioch",
    "BART_ASHB": "Ashby",
    "BART_BALB": "Balboa Park",
    "BART_BAYF": "Bay Fair",
    "BART_BERY": "Berryessa / North San Jose",
    "BART_CAST": "Castro Valley",
    "BART_CIVC": "Civic Center / UN Plaza",
    "BART_COLS": "Coliseum",
    "BART_COLM": "Colma",
    "BART_CONC": "Concord",
    "BART_DALY": "Daly City",
    "BART_DBRK": "Downtown Berkeley",
    "BART_DELN": "El Cerrito del Norte",
    "BART_DUBL": "Dublin / Pleasanton",
    "BART_EMBR": "Embarcadero",
    "BART_FRMT": "Fremont",
    "BART_FTVL": "Fruitvale",
    "BART_GLEN": "Glen Park",
    "BART_HAYW": "Hayward",
    "BART_LAFY": "Lafayette",
    "BART_LAKE": "Lake Merritt",
    "BART_MCAR": "MacArthur",
    "BART_MLBR": "Millbrae",
    "BART_MLPT": "Milpitas",
    "BART_MONT": "Montgomery St.",
    "BART_NBRK": "North Berkeley",
    "BART_NCON": "North Concord / Martinez",
    "BART_OAKL": "Oakland International Airport",
    "BART_ORIN": "Orinda",
    "BART_PCTR": "Pittsburg Center",
    "BART_PHIL": "Pleasant Hill / Contra Costa Centre",
    "BART_PITT": "Pittsburg / Bay Point",
    "BART_PLZA": "El Cerrito Plaza",
    "BART_POWL": "Powell St.",
    "BART_RICH": "Richmond",
    "BART_ROCK": "Rockridge",
    "BART_SANL": "San Leandro",
    "BART_SBRN": "San Bruno",
    "BART_SFIA": "San Francisco Intl Airport",
    "BART_SHAY": "South Hayward",
    "BART_SSAN": "South San Francisco",
    "BART_UCTY": "Union City",
    "BART_WARM": "Warm Springs / South Fremont",
    "BART_WCRK": "Walnut Creek",
    "BART_WDUB": "West Dublin / Pleasanton",
    "BART_WOAK": "West Oakland",
}

BART_GTFS_RT_FEED_URL = "https://api.bart.gov/gtfsrt/tripupdate.aspx"

BART_ALERTS_FEED_URL = "https://api.bart.gov/gtfsrt/alerts.aspx"

# BART GTFS stop_id to internal station code mapping.
# GTFS-RT uses platform-level stop_ids like "A40-2", "M10-1".
# The parent_station field in stops.txt gives the 4-letter station code.
# We map both platform-level and parent-level stop_ids.
BART_GTFS_STOP_TO_INTERNAL_MAP: dict[str, str] = {
    # Parent stations (4-letter codes used as fallback)
    "12TH": "BART_12TH",
    "16TH": "BART_16TH",
    "19TH": "BART_19TH",
    "24TH": "BART_24TH",
    "ANTC": "BART_ANTC",
    "ASHB": "BART_ASHB",
    "BALB": "BART_BALB",
    "BAYF": "BART_BAYF",
    "BERY": "BART_BERY",
    "CAST": "BART_CAST",
    "CIVC": "BART_CIVC",
    "COLS": "BART_COLS",
    "COLM": "BART_COLM",
    "CONC": "BART_CONC",
    "DALY": "BART_DALY",
    "DBRK": "BART_DBRK",
    "DELN": "BART_DELN",
    "DUBL": "BART_DUBL",
    "EMBR": "BART_EMBR",
    "FRMT": "BART_FRMT",
    "FTVL": "BART_FTVL",
    "GLEN": "BART_GLEN",
    "HAYW": "BART_HAYW",
    "LAFY": "BART_LAFY",
    "LAKE": "BART_LAKE",
    "MCAR": "BART_MCAR",
    "MLBR": "BART_MLBR",
    "MLPT": "BART_MLPT",
    "MONT": "BART_MONT",
    "NBRK": "BART_NBRK",
    "NCON": "BART_NCON",
    "OAKL": "BART_OAKL",
    "ORIN": "BART_ORIN",
    "PCTR": "BART_PCTR",
    "PHIL": "BART_PHIL",
    "PITT": "BART_PITT",
    "PLZA": "BART_PLZA",
    "POWL": "BART_POWL",
    "RICH": "BART_RICH",
    "ROCK": "BART_ROCK",
    "SANL": "BART_SANL",
    "SBRN": "BART_SBRN",
    "SFIA": "BART_SFIA",
    "SHAY": "BART_SHAY",
    "SSAN": "BART_SSAN",
    "UCTY": "BART_UCTY",
    "WARM": "BART_WARM",
    "WCRK": "BART_WCRK",
    "WDUB": "BART_WDUB",
    "WOAK": "BART_WOAK",
    # Platform-level stop_ids (e.g., "A40-2" for San Leandro platform 2)
    # 12th St. Oakland City Center
    "K10-1": "BART_12TH",
    "K10-2": "BART_12TH",
    "K10-3": "BART_12TH",
    # 16th St. Mission
    "M50-1": "BART_16TH",
    "M50-2": "BART_16TH",
    # 19th St. Oakland
    "K20-1": "BART_19TH",
    "K20-2": "BART_19TH",
    "K20-3": "BART_19TH",
    # 24th St. Mission
    "M60-1": "BART_24TH",
    "M60-2": "BART_24TH",
    # Antioch
    "E30-1": "BART_ANTC",
    "E30-2": "BART_ANTC",
    # Ashby
    "R10-1": "BART_ASHB",
    "R10-2": "BART_ASHB",
    # Balboa Park
    "M80-1": "BART_BALB",
    "M80-2": "BART_BALB",
    # Bay Fair
    "A50-1": "BART_BAYF",
    "A50-2": "BART_BAYF",
    # Berryessa / North San Jose
    "S50-1": "BART_BERY",
    "S50-2": "BART_BERY",
    # Castro Valley
    "L10-1": "BART_CAST",
    "L10-2": "BART_CAST",
    # Civic Center / UN Plaza
    "M40-1": "BART_CIVC",
    "M40-2": "BART_CIVC",
    # Coliseum
    "A30-1": "BART_COLS",
    "A30-2": "BART_COLS",
    "H10": "BART_COLS",  # OAC connector platform
    # Colma
    "W10-1": "BART_COLM",
    "W10-2": "BART_COLM",
    # Concord
    "C60-1": "BART_CONC",
    "C60-2": "BART_CONC",
    # Daly City
    "M90-1": "BART_DALY",
    "M90-2": "BART_DALY",
    "M90-3": "BART_DALY",
    # Downtown Berkeley
    "R20-1": "BART_DBRK",
    "R20-2": "BART_DBRK",
    # El Cerrito del Norte
    "R50-1": "BART_DELN",
    "R50-2": "BART_DELN",
    # Dublin / Pleasanton
    "L30-1": "BART_DUBL",
    "L30-2": "BART_DUBL",
    # Embarcadero
    "M16-1": "BART_EMBR",
    "M16-2": "BART_EMBR",
    # Fremont
    "A90-1": "BART_FRMT",
    "A90-2": "BART_FRMT",
    # Fruitvale
    "A20-1": "BART_FTVL",
    "A20-2": "BART_FTVL",
    # Glen Park
    "M70-1": "BART_GLEN",
    "M70-2": "BART_GLEN",
    # Hayward
    "A60-1": "BART_HAYW",
    "A60-2": "BART_HAYW",
    # Lafayette
    "C30-1": "BART_LAFY",
    "C30-2": "BART_LAFY",
    # Lake Merritt
    "A10-1": "BART_LAKE",
    "A10-2": "BART_LAKE",
    # MacArthur
    "K30-1": "BART_MCAR",
    "K30-2": "BART_MCAR",
    "K30-3": "BART_MCAR",
    "K30-4": "BART_MCAR",
    # Millbrae
    "W40-3": "BART_MLBR",
    # Milpitas
    "S40-1": "BART_MLPT",
    "S40-2": "BART_MLPT",
    # Montgomery St.
    "M20-1": "BART_MONT",
    "M20-2": "BART_MONT",
    # North Berkeley
    "R30-1": "BART_NBRK",
    "R30-2": "BART_NBRK",
    # North Concord / Martinez
    "C70-1": "BART_NCON",
    "C70-2": "BART_NCON",
    # Oakland International Airport
    "H40": "BART_OAKL",
    # Orinda
    "C20-1": "BART_ORIN",
    "C20-2": "BART_ORIN",
    # Pittsburg Center
    "E20-1": "BART_PCTR",
    "E20-2": "BART_PCTR",
    # Pleasant Hill / Contra Costa Centre
    "C50-1": "BART_PHIL",
    "C50-2": "BART_PHIL",
    # Pittsburg / Bay Point
    "C80-1": "BART_PITT",
    "C80-2": "BART_PITT",
    # El Cerrito Plaza
    "R40-1": "BART_PLZA",
    "R40-2": "BART_PLZA",
    # Powell St.
    "M30-1": "BART_POWL",
    "M30-2": "BART_POWL",
    # Richmond
    "R60-1": "BART_RICH",
    "R60-2": "BART_RICH",
    # Rockridge
    "C10-1": "BART_ROCK",
    "C10-2": "BART_ROCK",
    # San Leandro
    "A40-1": "BART_SANL",
    "A40-2": "BART_SANL",
    # San Bruno
    "W30-1": "BART_SBRN",
    "W30-2": "BART_SBRN",
    # San Francisco International Airport
    "Y10-1": "BART_SFIA",
    "Y10-2": "BART_SFIA",
    "Y10-3": "BART_SFIA",
    # South Hayward
    "A70-1": "BART_SHAY",
    "A70-2": "BART_SHAY",
    # South San Francisco
    "W20-1": "BART_SSAN",
    "W20-2": "BART_SSAN",
    # Union City
    "A80-1": "BART_UCTY",
    "A80-2": "BART_UCTY",
    # Warm Springs / South Fremont
    "S20-1": "BART_WARM",
    "S20-2": "BART_WARM",
    # Walnut Creek
    "C40-1": "BART_WCRK",
    "C40-2": "BART_WCRK",
    # West Dublin / Pleasanton
    "L20-1": "BART_WDUB",
    "L20-2": "BART_WDUB",
    # West Oakland
    "M10-1": "BART_WOAK",
    "M10-2": "BART_WOAK",
}

# Reverse mapping for BART
INTERNAL_TO_BART_GTFS_STOP_MAP: dict[str, str] = {
    v: k
    for k, v in BART_GTFS_STOP_TO_INTERNAL_MAP.items()
    # Only include 4-letter parent station codes in reverse map
    if "-" not in k and len(k) <= 4
}

# BART route definitions (route_id -> line_code, name, color)
# BART GTFS uses directional route_ids (e.g., 1=Yellow-S, 2=Yellow-N).
# We map both directions to the same line.
BART_ROUTES: dict[str, tuple[str, str, str]] = {
    "1": ("BART-YEL", "Antioch - SFO/Millbrae", "#FFFF33"),
    "2": ("BART-YEL", "Antioch - SFO/Millbrae", "#FFFF33"),
    "3": ("BART-ORG", "Berryessa - Richmond", "#FF9933"),
    "4": ("BART-ORG", "Berryessa - Richmond", "#FF9933"),
    "5": ("BART-GRN", "Berryessa - Daly City", "#339933"),
    "6": ("BART-GRN", "Berryessa - Daly City", "#339933"),
    "7": ("BART-RED", "Richmond - SFO/Millbrae", "#FF0000"),
    "8": ("BART-RED", "Richmond - SFO/Millbrae", "#FF0000"),
    "11": ("BART-BLU", "Dublin/Pleasanton - Daly City", "#0099CC"),
    "12": ("BART-BLU", "Dublin/Pleasanton - Daly City", "#0099CC"),
    "19": ("BART-OAK", "Oakland Airport - Coliseum", "#B0BEC7"),
    "20": ("BART-OAK", "Oakland Airport - Coliseum", "#B0BEC7"),
}

# BART discovery stations — major transfer hubs
BART_DISCOVERY_STATIONS: list[str] = [
    "BART_EMBR",  # Embarcadero (downtown SF hub)
    "BART_MCAR",  # MacArthur (transfer between Richmond & Pittsburg lines)
    "BART_12TH",  # 12th St. Oakland (transfer hub)
    "BART_BAYF",  # Bay Fair (transfer between Fremont & Dublin lines)
    "BART_DALY",  # Daly City (southern terminus for multiple lines)
]

# BART station coordinates (lat, lon) from GTFS
BART_STATION_COORDINATES: dict[str, tuple[float, float]] = {
    "BART_12TH": (37.803482, -122.271630),
    "BART_16TH": (37.765173, -122.419704),
    "BART_19TH": (37.808078, -122.268758),
    "BART_24TH": (37.752419, -122.418468),
    "BART_ANTC": (37.995373, -121.780346),
    "BART_ASHB": (37.853072, -122.269771),
    "BART_BALB": (37.721747, -122.447457),
    "BART_BAYF": (37.696908, -122.126446),
    "BART_BERY": (37.368473, -121.874681),
    "BART_CAST": (37.690737, -122.075601),
    "BART_CIVC": (37.779408, -122.413826),
    "BART_COLS": (37.753576, -122.196716),
    "BART_COLM": (37.684635, -122.466157),
    "BART_CONC": (37.973757, -122.029072),
    "BART_DALY": (37.706259, -122.468908),
    "BART_DBRK": (37.870110, -122.268109),
    "BART_DELN": (37.925184, -122.316892),
    "BART_DUBL": (37.701646, -121.899229),
    "BART_EMBR": (37.792762, -122.397037),
    "BART_FRMT": (37.557480, -121.976619),
    "BART_FTVL": (37.774841, -122.224081),
    "BART_GLEN": (37.733235, -122.433515),
    "BART_HAYW": (37.669699, -122.086958),
    "BART_LAFY": (37.893183, -122.124620),
    "BART_LAKE": (37.797322, -122.265247),
    "BART_MCAR": (37.828803, -122.267105),
    "BART_MLBR": (37.600237, -122.386757),
    "BART_MLPT": (37.410277, -121.891081),
    "BART_MONT": (37.789173, -122.401587),
    "BART_NBRK": (37.874005, -122.283523),
    "BART_NCON": (38.003383, -122.024512),
    "BART_OAKL": (37.713256, -122.212237),
    "BART_ORIN": (37.878481, -122.183667),
    "BART_PCTR": (38.016847, -121.889062),
    "BART_PHIL": (37.928434, -122.055971),
    "BART_PITT": (38.018910, -121.944236),
    "BART_PLZA": (37.902610, -122.298920),
    "BART_POWL": (37.784606, -122.407331),
    "BART_RICH": (37.936758, -122.353047),
    "BART_ROCK": (37.844755, -122.251235),
    "BART_SANL": (37.721784, -122.160740),
    "BART_SBRN": (37.637730, -122.416326),
    "BART_SFIA": (37.616091, -122.391954),
    "BART_SHAY": (37.634340, -122.057182),
    "BART_SSAN": (37.664462, -122.444211),
    "BART_UCTY": (37.590735, -122.017248),
    "BART_WARM": (37.502285, -121.939395),
    "BART_WCRK": (37.905791, -122.067327),
    "BART_WDUB": (37.699721, -121.928277),
    "BART_WOAK": (37.804888, -122.295151),
}


def map_bart_gtfs_stop(gtfs_stop_id: str) -> str | None:
    """Map BART GTFS stop_id to our internal station code.

    Handles both platform-level stop_ids (e.g., 'A40-2') and
    parent station codes (e.g., 'SANL').

    Args:
        gtfs_stop_id: GTFS stop_id from the BART feed

    Returns:
        Internal station code (e.g., 'BART_SANL') or None if not mapped
    """
    return BART_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_stop_id)


def get_bart_route_info(gtfs_route_id: str) -> tuple[str, str, str] | None:
    """Get BART route info from GTFS route ID.

    Args:
        gtfs_route_id: GTFS route_id (e.g., '1' for Yellow-S)

    Returns:
        Tuple of (line_code, route_name, color) or None if not mapped
    """
    return BART_ROUTES.get(gtfs_route_id)
