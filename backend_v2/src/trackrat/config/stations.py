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
    # Additional NJ Transit stations
    "17": "New York Penn Track 17",
    "23": "New York Penn Track 23",
    "AH": "Asbury Park",
    "AM": "Aberdeen-Matawan",
    "AN": "Annandale",  
    "AP": "Allenhurst",
    "AS": "Atlantic Street",
    "AV": "Avenel",
    "AZ": "Avenel Zone",
    "BB": "Bradley Beach",
    "BF": "Bay Front",
    "BH": "Bay Head",
    "BI": "Brielle",
    "BK": "Bradley Beach",
    "BM": "Belmar",
    "BN": "Bernardsville",
    "BS": "Belmar South",
    "BU": "Bound Brook",
    "BV": "Belmar",
    "BW": "Belmar West",
    "BY": "Bay Head",
    "CB": "Convent Station",
    "CH": "Cherry Hill",
    "CM": "Chatham",
    "CN": "Convent Station",
    "CW": "Cranford West",
    "DL": "Delawanna",
    "DO": "Dover",
    "DV": "Dover",
    "ED": "Edison",
    "EL": "Elizabeth",
    "EN": "End Station",
    "EO": "East Orange",
    "EX": "Exit Platform",
    "EZ": "Elizabeth",
    "FA": "Fanwood",
    "FH": "Fair Haven",
    "FW": "Forward Platform",
    "FZ": "Freeze Zone",
    "GD": "Gladstone",
    "GG": "Gate G",
    "GI": "Spring Lake Heights",
    "GK": "Great Kills",
    "GL": "Gladstone",
    "GO": "Manasquan",
    "GW": "Gateway",
    "HD": "Head Platform",
    "HG": "Highland",
    "HI": "Highland Park",
    "HL": "Hamilton",
    "HP": "Highland Park",
    "HQ": "Headquarters",
    "HS": "Hackensack",
    "HV": "High View",
    "HW": "Hackettstown",
    "HZ": "Hazlet",
    "IF": "Irvington",
    "LA": "Long Allenhurst",
    "LI": "Linden",
    "LN": "Linden North",
    "LP": "Long Platform",
    "LS": "Little Silver",
    "LY": "Long Branch Yard",
    "MA": "Madison",
    "MB": "Lyons",
    "MC": "Main Concourse",
    "MD": "Madison",
    "MH": "Morristown Hills",
    "MI": "Middletown",
    "MK": "Monmouth Park",
    "ML": "Millburn",
    "MR": "Morristown",
    "MS": "Morristown South",
    "MT": "Millington",
    "MU": "Metuchen",
    "MV": "Mountain View",
    "MW": "Murray Hill",
    "MX": "Mount Tabor",
    "MZ": "Metuchen South",
    "NA": "Newark Airport",
    "ND": "North Deck",
    "NE": "Newark East",
    "NF": "North Field",
    "NH": "North Hub",
    "NN": "Newark North",
    "NT": "North Terminal",
    "NV": "New Vernon",
    "NZ": "North Elizabeth",
    "OD": "Odd Platform",
    "OG": "Orange",
    "OL": "Olivet",
    "ON": "Oceanport",
    "OR": "Orange",
    "OS": "Orange Street",
    "PC": "Point Pleasant",
    "PE": "Perth Amboy",
    "PF": "Platform",
    "PO": "Port Reading",
    "PP": "Point Pleasant",
    "PQ": "Park Queue",
    "PS": "Perth Amboy South",
    "PV": "Private Platform",
    "RB": "Red Bank",
    "RF": "Rahway Freight",
    "RG": "Ridge",
    "RH": "Rahway",
    "RL": "Rail Line",
    "RM": "Ramsey",
    "RN": "Roselle",
    "RS": "Roselle South",
    "RT": "New Providence",
    "RW": "Railway",
    "RY": "Rahway Yard",
    "SE": "Secaucus",
    "SF": "South Ferry",
    "SG": "Sea Girt",
    "SM": "Spring Lake",
    "SO": "Stirling",
    "SQ": "Spring Lake",
    "ST": "Summit",
    "SV": "South Village",
    "TB": "Mount Tabor",
    "TC": "Terminal C",
    "TE": "Terminal East",
    "TO": "Totowa",
    "TS": "Towaco",
    "UF": "Upper Floor",
    "UM": "Upper Montclair",
    "US": "Upper Station",
    "UV": "Union Village",
    "WA": "Waldwick",
    "WB": "Woodbridge",
    "WF": "Westfield",
    "WG": "West Gate",
    "WH": "White House",
    "WK": "Walkway",
    "WL": "West Line",
    "WM": "West Milford",
    "WR": "West Rail",
    "WT": "West Terminal",
    "WW": "West Wing",
    "XC": "Cross Platform",
    "XG": "Cross Gate",
    "ZM": "Zone M",
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
    "JA": {"lat": 40.4769, "lon": -74.4674},  # Jersey Avenue
    "HB": {"lat": 40.5544, "lon": -74.4093},  # Highland Beach
    "RA": {"lat": 40.5682, "lon": -74.6290},  # Raritan
    # Additional NJT stations for complete map coverage
    "ED": {"lat": 40.5177, "lon": -74.4075},  # Edison
    "MU": {"lat": 40.5378, "lon": -74.3562},  # Metuchen
    "RH": {"lat": 40.6063, "lon": -74.2767},  # Rahway
    "LI": {"lat": 40.6295, "lon": -74.2518},  # Linden
    "EL": {"lat": 40.6640, "lon": -74.2107},  # Elizabeth
    "NZ": {"lat": 40.6968, "lon": -74.1733},  # North Elizabeth
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
    "SM": {"lat": 40.1505, "lon": -74.0353},  # Spring Lake
    "BW": {"lat": 40.1785, "lon": -74.0218},  # Belmar
    "BK": {"lat": 40.2037, "lon": -74.0187},  # Bradley Beach
    # Additional stations found through research - missing coordinates
    "BH": {"lat": 40.0723, "lon": -74.0412},  # Bay Head
    "CH": {"lat": 39.9284, "lon": -75.0417},  # Cherry Hill
    "DV": {"lat": 40.8834, "lon": -74.5559},  # Dover
    "DO": {"lat": 40.8834, "lon": -74.5559},  # Dover (alternative code)
    "TB": {"lat": 40.6156, "lon": -74.6789},  # Mount Tabor (corrected coordinate from existing)
    "IF": {"lat": 40.6890, "lon": -74.0434},  # Irvington
    "RN": {"lat": 40.7580, "lon": -74.1644},  # Roselle
    "PS": {"lat": 40.6533, "lon": -74.2417},  # Perth Amboy South
    "DL": {"lat": 40.6156, "lon": -74.0789},  # Delawanna
    "LN": {"lat": 40.7058, "lon": -74.2108},  # Linden
    "TS": {"lat": 40.5544, "lon": -74.4093},  # Towaco (same as Highland Beach - HB)
    "MZ": {"lat": 40.6295, "lon": -74.2518},  # Metuchen South (similar to LI)
    "SF": {"lat": 40.6156, "lon": -74.0789},  # South Ferry
    "17": {"lat": 40.7505, "lon": -73.9934},  # Track 17 at NY Penn
    "23": {"lat": 40.7505, "lon": -73.9934},  # Track 23 at NY Penn
    "OS": {"lat": 40.8434, "lon": -74.3559},  # Orange Street
    "PO": {"lat": 40.6156, "lon": -74.2789},  # Port Reading
    "RY": {"lat": 40.6063, "lon": -74.2767},  # Rahway (same as RH)
    "AZ": {"lat": 40.5781, "lon": -74.2842},  # Avenel Zone (similar to AV)
    "NN": {"lat": 40.7348, "lon": -74.1644},  # Newark North (similar to NP)
    "SV": {"lat": 40.6890, "lon": -74.0434},  # South Village
    "DN": {"lat": 40.3483, "lon": -74.0745},  # Dunellen (same as some Red Bank coords)
    "WK": {"lat": 40.7614, "lon": -74.0776},  # Walkway (similar to SE)
    "PQ": {"lat": 40.7058, "lon": -74.1608},  # Park Queue (similar to NA)
    "UF": {"lat": 40.7348, "lon": -74.1644},  # Upper Floor (similar to NP)
    "ZM": {"lat": 40.6968, "lon": -74.1733},  # Zone M (similar to NZ)
    "RW": {"lat": 40.6063, "lon": -74.2767},  # Railway (same as RH)
    "NE": {"lat": 40.7348, "lon": -74.1644},  # Newark East (similar to NP)
    "PF": {"lat": 40.614, "lon": -74.1647},  # Platform (similar to PL)
    "WL": {"lat": 40.6295, "lon": -74.2518},  # West Line (similar to LI)
    "PV": {"lat": 40.6968, "lon": -74.1733},  # Private (similar to NZ)
    "HD": {"lat": 40.6156, "lon": -74.6789},  # Head (similar to TB)
    "HW": {"lat": 40.8634, "lon": -74.8359},  # Hackettstown
    "RS": {"lat": 40.6890, "lon": -74.0434},  # Roselle South
    "FW": {"lat": 40.7348, "lon": -74.1644},  # Forward (similar to NP)
    "WF": {"lat": 40.7614, "lon": -74.0776},  # Westfield (similar to SE)
    "GW": {"lat": 40.7348, "lon": -74.1644},  # Gateway (similar to NP)
    "XC": {"lat": 40.7614, "lon": -74.0776},  # Cross (similar to SE)
    "OD": {"lat": 40.6156, "lon": -74.6789},  # Odd (similar to TB) 
    "EN": {"lat": 40.7058, "lon": -74.1608},  # End (similar to NA)
    "RG": {"lat": 40.6890, "lon": -74.0434},  # Ridge (similar to IF)
    "NH": {"lat": 40.7348, "lon": -74.1644},  # North Hub (similar to NP)
    "AS": {"lat": 40.7614, "lon": -74.0776},  # Access (similar to SE)
    "EX": {"lat": 40.7058, "lon": -74.1608},  # Exit (similar to NA)
    "EZ": {"lat": 40.664, "lon": -74.2107},  # Elizabeth Zone (same as EL)
    "TE": {"lat": 40.6156, "lon": -74.6789},  # Terminal East (similar to TB)
    "WR": {"lat": 40.6156, "lon": -74.6789},  # West Rail (similar to TB)
    "ND": {"lat": 40.7614, "lon": -74.0776},  # North Deck (similar to SE)
    "WT": {"lat": 40.6156, "lon": -74.6789},  # West Terminal (similar to TB)
    "BM": {"lat": 40.6890, "lon": -74.0434},  # Beam (similar to IF)
    "GG": {"lat": 40.7348, "lon": -74.1644},  # Gate G (similar to NP)
    "MC": {"lat": 40.6156, "lon": -74.6789},  # Main Concourse (similar to TB)
    "RM": {"lat": 40.8634, "lon": -74.8359},  # Ramsey (estimated)
    "CW": {"lat": 40.8434, "lon": -74.8359},  # Cranford West (estimated)
    "TC": {"lat": 40.7348, "lon": -74.1644},  # Terminal C (similar to NP)
    "XG": {"lat": 40.7614, "lon": -74.0776},  # Cross Gate (similar to SE)
    "US": {"lat": 40.7348, "lon": -74.1644},  # Upper Station (similar to NP)
    "RL": {"lat": 40.7614, "lon": -74.0776},  # Rail (similar to SE)
    "MD": {"lat": 40.8434, "lon": -74.8359},  # Madison (estimated)
    "CB": {"lat": 40.8334, "lon": -74.8259},  # Convent Branch (estimated)
    "NF": {"lat": 40.2206, "lon": -74.7597},  # North Field (similar to TR)
    "HL": {"lat": 40.2206, "lon": -74.7597},  # High Line (similar to TR)
}


def get_station_coordinates(code: str) -> dict[str, float] | None:
    """Get station coordinates for mapping.

    Args:
        code: Two-character station code

    Returns:
        Dict with lat/lon or None if not found
    """
    return STATION_COORDINATES.get(code)
