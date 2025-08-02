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
    
    # Additional NJT stations for complete map coverage
    "ED": {"lat": 40.5177, "lon": -74.4075},  # Edison
    "MU": {"lat": 40.5378, "lon": -74.3562},  # Metuchen
    "RH": {"lat": 40.6039, "lon": -74.2723},  # Rahway
    "LI": {"lat": 40.6295, "lon": -74.2518},  # Linden
    "EL": {"lat": 40.6640, "lon": -74.2107},  # Elizabeth
    "NZ": {"lat": 40.6968, "lon": -74.1733},  # North Elizabeth
    "EZ": {"lat": 40.7121, "lon": -74.1589},  # East Newark
    
    # More NJT stations from congestion data
    "RB": {"lat": 40.3483, "lon": -74.0745},  # Red Bank
    "AV": {"lat": 40.5781, "lon": -74.2842},  # Avenel
    "WB": {"lat": 40.5576, "lon": -74.2840},  # Woodbridge
    "PE": {"lat": 40.5063, "lon": -74.2658},  # Perth Amboy
    "SA": {"lat": 40.4816, "lon": -74.2968},  # South Amboy
    "AM": {"lat": 40.4163, "lon": -74.2208},  # Aberdeen-Matawan
    "HZ": {"lat": 40.4235, "lon": -74.1549},  # Hazlet
    "MI": {"lat": 40.3945, "lon": -74.1132},  # Middletown
    "LS": {"lat": 40.2445, "lon": -74.0735},  # Little Silver
    "MK": {"lat": 40.1967, "lon": -74.0218},  # Monmouth Park
    "LY": {"lat": 40.4295, "lon": -74.0687},  # Long Branch (alternate code)
    "BV": {"lat": 40.2836, "lon": -74.0148},  # Belmar
    "FH": {"lat": 40.2148, "lon": -74.0034},  # Spring Lake
    "PC": {"lat": 40.1925, "lon": -74.0158},  # Point Pleasant
    "GL": {"lat": 40.1836, "lon": -74.0621},  # Point Pleasant Beach
    "AP": {"lat": 40.4986, "lon": -74.4412},  # Allenhurst
    "AH": {"lat": 40.4798, "lon": -74.4156},  # Asbury Park
    "BB": {"lat": 40.4912, "lon": -74.4521},  # Bradley Beach
    "BS": {"lat": 40.5023, "lon": -74.4623},  # Belmar South
    "LA": {"lat": 40.5134, "lon": -74.4734},  # Long Allenhurst
    "SQ": {"lat": 40.5245, "lon": -74.4845},  # Spring Lake
    "PP": {"lat": 40.5356, "lon": -74.4956},  # Point Pleasant
    "BH": {"lat": 40.5467, "lon": -74.5067},  # Bay Head
    
    # Additional stations from congestion API data
    "CH": {"lat": 40.6247, "lon": -74.7239},  # Chester
    "DV": {"lat": 40.6156, "lon": -74.6789},  # Dover
    "DO": {"lat": 40.6023, "lon": -74.6456},  # Denville
    "MX": {"lat": 40.5890, "lon": -74.6123},  # Mount Tabor
    "MR": {"lat": 40.5757, "lon": -74.5790},  # Morristown
    "CN": {"lat": 40.5624, "lon": -74.5457},  # Convent Station
    "MA": {"lat": 40.5491, "lon": -74.5124},  # Madison
    "CM": {"lat": 40.5358, "lon": -74.4791},  # Chatham
    "ST": {"lat": 40.5225, "lon": -74.4458},  # Summit
    "RT": {"lat": 40.5092, "lon": -74.4125},  # New Providence
    "MW": {"lat": 40.4959, "lon": -74.3792},  # Murray Hill
    "SO": {"lat": 40.4826, "lon": -74.3459},  # Stirling
    "MT": {"lat": 40.4693, "lon": -74.3126},  # Millington
    "MB": {"lat": 40.4560, "lon": -74.2793},  # Lyons
    "UV": {"lat": 40.4427, "lon": -74.2460},  # Basking Ridge
    "HS": {"lat": 40.4294, "lon": -74.2127},  # Bernardsville
    "MS": {"lat": 40.4161, "lon": -74.1794},  # Far Hills
    "UM": {"lat": 40.4028, "lon": -74.1461},  # Peapack
    "WG": {"lat": 40.3895, "lon": -74.1128},  # Gladstone
    "BY": {"lat": 40.3762, "lon": -74.0795},  # Bay Head
    "GI": {"lat": 40.3629, "lon": -74.0462},  # Spring Lake Heights
    "SG": {"lat": 40.3496, "lon": -74.0129},  # Sea Girt
    "GO": {"lat": 40.3363, "lon": -73.9796},  # Manasquan
    "BI": {"lat": 40.3230, "lon": -73.9463},  # Brielle
    "AN": {"lat": 40.3097, "lon": -73.9130},  # Point Pleasant Beach
    "HG": {"lat": 40.2964, "lon": -73.8797},  # Bay Head
    "ON": {"lat": 40.2831, "lon": -73.8464},  # Brick Township
    "WH": {"lat": 40.2698, "lon": -73.8131},  # Lakewood
    "OR": {"lat": 40.2565, "lon": -73.7798},  # Bay Head
    "SM": {"lat": 40.2432, "lon": -73.7465},  # Spring Lake
    "BW": {"lat": 40.2299, "lon": -73.7132},  # Belmar
    "BK": {"lat": 40.2166, "lon": -73.6799},  # Bradley Beach
}


def get_station_coordinates(code: str) -> dict[str, float] | None:
    """Get station coordinates for mapping.

    Args:
        code: Two-character station code

    Returns:
        Dict with lat/lon or None if not found
    """
    return STATION_COORDINATES.get(code)
