"""
Station configuration for TrackRat V2.

Contains station codes, names, and related functions.
"""

# Station code to name mapping
STATION_NAMES: dict[str, str] = {
    "NY": "New York Penn Station",
    "NP": "Newark Penn Station",
    "PJ": "Princeton Junction",
    "TR": "Trenton",
    "LB": "Long Branch",
    "PL": "Plainfield",
    "DN": "Dunellen",
    "MP": "Metropark",
    "NB": "New Brunswick",
    "JA": "Jersey Avenue",
    "HB": "Hoboken",
    "RA": "Raritan",
    "WS": "Washington Union Station",
    "PH": "Philadelphia",
    "WI": "Wilmington Station",
    "BL": "Baltimore Station",
    "BA": "BWI Thurgood Marshall Airport",
    "BOS": "Boston South Station",
    "BBY": "Boston Back Bay",
}


def get_station_name(code: str) -> str:
    """Get the full station name for a given code.

    Args:
        code: Two-character station code

    Returns:
        Full station name, or the code if not found
    """
    return STATION_NAMES.get(code, code)


# Mapping from Amtrak station codes to our internal codes
AMTRAK_TO_INTERNAL_STATION_MAP: dict[str, str] = {
    "NYP": "NY",  # New York Penn Station
    "NWK": "NP",  # Newark Penn
    "TRE": "TR",  # Trenton
    "PJC": "PJ",  # Princeton Junction
    "MET": "MP",  # Metropark
    "NBK": "NB",  # New Brunswick
    "EWR": "NP",  # Newark Airport → Newark Penn
    "WAS": "WS",  # Washington Union Station
    "PHL": "PH",  # Philadelphia
    "WIL": "WI",  # Wilmington
    "BAL": "BL",  # Baltimore Penn Station
    "BWI": "BA",  # Baltimore BWI Thurgood Marshall Airport
    "BOS": "BOS",  # Boston South Station
    "BBY": "BBY",  # Boston Back Bay
}

# Reverse mapping from internal codes to Amtrak codes (for the first match)
INTERNAL_TO_AMTRAK_STATION_MAP: dict[str, str] = {
    "NY": "NYP",
    "NP": "NWK",
    "TR": "TRE",
    "PJ": "PJC",
    "MP": "MET",
    "NB": "NBK",
    "WS": "WAS",
    "PH": "PHL",
    "WI": "WIL",
    "BL": "BAL",
    "BA": "BWI",
    "BOS": "BOS",
    "BBY": "BBY",
}


def map_amtrak_station_code(amtrak_code: str) -> str | None:
    """Map Amtrak station code to our internal code.

    Args:
        amtrak_code: Amtrak's station code (e.g., 'NYP')

    Returns:
        Our internal station code (e.g., 'NY') or None if not mapped
    """
    return AMTRAK_TO_INTERNAL_STATION_MAP.get(amtrak_code)


def map_internal_to_amtrak_code(internal_code: str) -> str | None:
    """Map our internal station code to Amtrak's code.

    Args:
        internal_code: Our internal station code (e.g., 'NY')

    Returns:
        Amtrak's station code (e.g., 'NYP') or None if not mapped
    """
    return INTERNAL_TO_AMTRAK_STATION_MAP.get(internal_code)


def get_all_stations() -> list[dict[str, str]]:
    """Get all configured stations.

    Returns:
        List of station dictionaries with 'code' and 'name' keys
    """
    return [{"code": code, "name": name} for code, name in STATION_NAMES.items()]


# Station coordinates for map visualization
STATION_COORDINATES = {
    "NY": {"lat": 40.7505, "lon": -73.9934},  # NY Penn
    "NP": {"lat": 40.7348, "lon": -74.1644},  # Newark Penn
    "TR": {"lat": 40.2206, "lon": -74.7597},  # Trenton
    "PJ": {"lat": 40.3170, "lon": -74.6225},  # Princeton Junction
    "MP": {"lat": 40.5686, "lon": -74.3284},  # Metropark
    "NA": {"lat": 40.7058, "lon": -74.1608},  # Newark Airport
    "NB": {"lat": 40.4862, "lon": -74.4518},  # New Brunswick
    "SE": {"lat": 40.7614, "lon": -74.0776},  # Secaucus
    "PH": {"lat": 39.9566, "lon": -75.1820},  # Philadelphia
    "WI": {"lat": 39.7391, "lon": -75.5516},  # Wilmington
    "BA": {"lat": 39.3076, "lon": -76.6159},  # BWI Airport
    "BL": {"lat": 39.3072, "lon": -76.6200},  # Baltimore
    "WS": {"lat": 38.8977, "lon": -77.0063},  # Washington Union
    "BOS": {"lat": 42.3519, "lon": -71.0552},  # Boston South Station
    "BBY": {"lat": 42.3475, "lon": -71.0754},  # Boston Back Bay
    "PL": {"lat": 40.6140, "lon": -74.1647},  # Plainfield
    "LB": {"lat": 40.0849, "lon": -74.1990},  # Long Branch
    "DN": {"lat": 39.9526, "lon": -75.1652},  # Doylestown
    "JA": {"lat": 40.4769, "lon": -74.4674},  # Jersey Avenue
    "HB": {"lat": 40.5544, "lon": -74.4093},  # Highland Beach
    "RA": {"lat": 40.7418, "lon": -74.2656},  # Raritan
}


def get_station_coordinates(code: str) -> dict[str, float] | None:
    """Get station coordinates for mapping.

    Args:
        code: Two-character station code

    Returns:
        Dict with lat/lon or None if not found
    """
    return STATION_COORDINATES.get(code)
