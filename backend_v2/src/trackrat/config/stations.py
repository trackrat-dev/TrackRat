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
    # Additional Amtrak stations
    "BRP": "Bridgeport",
    "HFD": "Hartford",
    "MDN": "Meriden",
    "NHV": "New Haven",
    "NLC": "New London",
    "OSB": "Old Saybrook",
    "STM": "Stamford",
    "WFD": "Wallingford",
    "WNL": "Windsor Locks",
    "ABE": "Aberdeen",
    "NCR": "New Carrollton",
    "SPG": "Springfield",
    "CLA": "Claremont",
    "DOV": "Dover",
    "DHM": "Durham-UNH",
    "EXR": "Exeter",
    "HAR": "Harrisburg",
    "LNC": "Lancaster",
    "KIN": "Kingston",
    "PVD": "Providence",
    "WLY": "Westerly",
    "ALX": "Alexandria",
    "CVS": "Charlottesville",
    "LOR": "Lorton",
    "NFK": "Norfolk",
    "RVR": "Richmond Main Street",
    "RNK": "Roanoke",
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
    # Additional Amtrak stations
    "BPT": "BRP",  # Bridgeport, CT
    "HFD": "HFD",  # Hartford, CT
    "MDN": "MDN",  # Meriden, CT
    "NHV": "NHV",  # New Haven, CT
    "NLC": "NLC",  # New London, CT
    "OSB": "OSB",  # Old Saybrook, CT
    "STM": "STM",  # Stamford, CT
    "WFD": "WFD",  # Wallingford, CT
    "WNL": "WNL",  # Windsor Locks, CT
    "ABE": "ABE",  # Aberdeen, MD
    "NCR": "NCR",  # New Carrollton, MD
    "SPG": "SPG",  # Springfield, MA
    "CLA": "CLA",  # Claremont, NH
    "DOV": "DOV",  # Dover, NH
    "DHM": "DHM",  # Durham-UNH, NH
    "EXR": "EXR",  # Exeter, NH
    "HAR": "HAR",  # Harrisburg, PA
    "LNC": "LNC",  # Lancaster, PA
    "KIN": "KIN",  # Kingston, RI
    "PVD": "PVD",  # Providence, RI
    "WLY": "WLY",  # Westerly, RI
    "ALX": "ALX",  # Alexandria, VA
    "CVS": "CVS",  # Charlottesville, VA
    "LOR": "LOR",  # Lorton, VA
    "NFK": "NFK",  # Norfolk, VA
    "RVR": "RVR",  # Richmond Main Street, VA
    "RNK": "RNK",  # Roanoke, VA
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
    # Additional Amtrak stations
    "BRP": "BPT",  # Bridgeport, CT
    "HFD": "HFD",  # Hartford, CT
    "MDN": "MDN",  # Meriden, CT
    "NHV": "NHV",  # New Haven, CT
    "NLC": "NLC",  # New London, CT
    "OSB": "OSB",  # Old Saybrook, CT
    "STM": "STM",  # Stamford, CT
    "WFD": "WFD",  # Wallingford, CT
    "WNL": "WNL",  # Windsor Locks, CT
    "ABE": "ABE",  # Aberdeen, MD
    "NCR": "NCR",  # New Carrollton, MD
    "SPG": "SPG",  # Springfield, MA
    "CLA": "CLA",  # Claremont, NH
    "DOV": "DOV",  # Dover, NH
    "DHM": "DHM",  # Durham-UNH, NH
    "EXR": "EXR",  # Exeter, NH
    "HAR": "HAR",  # Harrisburg, PA
    "LNC": "LNC",  # Lancaster, PA
    "KIN": "KIN",  # Kingston, RI
    "PVD": "PVD",  # Providence, RI
    "WLY": "WLY",  # Westerly, RI
    "ALX": "ALX",  # Alexandria, VA
    "CVS": "CVS",  # Charlottesville, VA
    "LOR": "LOR",  # Lorton, VA
    "NFK": "NFK",  # Norfolk, VA
    "RVR": "RVR",  # Richmond Main Street, VA
    "RNK": "RNK",  # Roanoke, VA
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
    "NY": {"lat": 40.7506, "lon": -73.9939},  # New York Penn Station - Updated GPS
    "NP": {"lat": 40.7347, "lon": -74.1644},  # Newark Penn Station - Updated GPS
    "TR": {"lat": 40.218518, "lon": -74.753923},  # Trenton Transit Center - Updated GPS
    "PJ": {"lat": 40.3167, "lon": -74.6233},  # Princeton Junction - Updated GPS
    "MP": {"lat": 40.5378, "lon": -74.3562},  # Metropark - Updated GPS
    "NA": {"lat": 40.7058, "lon": -74.1608},  # Newark Airport
    "NB": {"lat": 40.4862, "lon": -74.4518},  # New Brunswick
    "SE": {"lat": 40.7612, "lon": -74.0758},  # Secaucus Junction - Updated GPS
    "PH": {
        "lat": 39.9570,
        "lon": -75.1820,
    },  # Philadelphia 30th Street Station - Updated GPS
    "WI": {"lat": 39.7369, "lon": -75.5522},  # Wilmington - Updated GPS
    "BA": {"lat": 39.1896, "lon": -76.6934},  # BWI Airport Rail Station - Updated GPS
    "BL": {"lat": 39.3081, "lon": -76.6175},  # Baltimore Penn Station - Updated GPS
    "WS": {"lat": 38.8973, "lon": -77.0064},  # Washington Union Station - Updated GPS
    "BOS": {"lat": 42.3520, "lon": -71.0552},  # Boston South Station - Updated GPS
    "BBY": {"lat": 42.3473, "lon": -71.0764},  # Boston Back Bay - Updated GPS
    # Additional Amtrak stations with GPS coordinates
    "BRP": {"lat": 41.1767, "lon": -73.1874},  # Bridgeport, CT
    "HFD": {"lat": 41.7678, "lon": -72.6821},  # Hartford, CT
    "MDN": {"lat": 41.5390, "lon": -72.8012},  # Meriden, CT
    "NHV": {"lat": 41.2987, "lon": -72.9259},  # New Haven, CT
    "NLC": {"lat": 41.3543, "lon": -72.0939},  # New London, CT
    "OSB": {"lat": 41.3005, "lon": -72.3760},  # Old Saybrook, CT
    "STM": {"lat": 41.0462, "lon": -73.5427},  # Stamford, CT
    "WFD": {"lat": 41.4571, "lon": -72.8254},  # Wallingford, CT
    "WNL": {"lat": 41.9272, "lon": -72.6286},  # Windsor Locks, CT
    "ABE": {"lat": 39.5095, "lon": -76.1630},  # Aberdeen, MD
    "NCR": {"lat": 38.9533, "lon": -76.8644},  # New Carrollton, MD
    "SPG": {"lat": 42.1060, "lon": -72.5936},  # Springfield, MA
    "CLA": {"lat": 43.3688, "lon": -72.3793},  # Claremont, NH
    "DOV": {"lat": 43.1979, "lon": -70.8737},  # Dover, NH
    "DHM": {"lat": 43.1340, "lon": -70.9267},  # Durham-UNH, NH
    "EXR": {"lat": 42.9809, "lon": -70.9478},  # Exeter, NH
    "HAR": {"lat": 40.2616, "lon": -76.8782},  # Harrisburg, PA
    "LNC": {"lat": 40.0538, "lon": -76.3076},  # Lancaster, PA
    "KIN": {"lat": 41.4885, "lon": -71.5204},  # Kingston, RI
    "PVD": {"lat": 41.8256, "lon": -71.4160},  # Providence, RI
    "WLY": {"lat": 41.3770, "lon": -71.8307},  # Westerly, RI
    "ALX": {"lat": 38.8062, "lon": -77.0626},  # Alexandria, VA
    "CVS": {"lat": 38.0320, "lon": -78.4921},  # Charlottesville, VA
    "LOR": {"lat": 38.7060, "lon": -77.2214},  # Lorton, VA
    "NFK": {"lat": 36.8583, "lon": -76.2876},  # Norfolk, VA
    "RVR": {"lat": 37.6143, "lon": -77.4966},  # Richmond Main Street, VA
    "RNK": {"lat": 37.3077, "lon": -79.9803},  # Roanoke, VA
    "LB": {"lat": 40.0849, "lon": -74.1990},  # Long Branch
    "JA": {"lat": 40.4769, "lon": -74.4674},  # Jersey Avenue
    "HB": {"lat": 40.734843, "lon": -74.028043},  # Hoboken Terminal - Updated GPS
    "RA": {"lat": 40.5682, "lon": -74.6290},  # Raritan
    # Additional NJT stations for complete map coverage
    "ED": {"lat": 40.5177, "lon": -74.4075},  # Edison - Updated GPS
    "MU": {"lat": 40.5378, "lon": -74.3562},  # Metuchen - Updated GPS
    "RH": {"lat": 40.6039, "lon": -74.2723},  # Rahway - Updated GPS
    "LI": {"lat": 40.629487, "lon": -74.251772},  # Linden - Updated GPS
    "EL": {"lat": 40.667859, "lon": -74.215171},  # Elizabeth - Updated GPS
    "EZ": {"lat": 40.667869, "lon": -74.215171},  # Elizabeth Zone (same as EL)
    "NZ": {"lat": 40.6968, "lon": -74.1733},  # North Elizabeth
    # Bergen County Line (Main Line) - Updated GPS coordinates
    "LY": {"lat": 40.8123, "lon": -74.1246},  # Lyndhurst
    "DL": {"lat": 40.8180, "lon": -74.1370},  # Delawanna
    "PA": {"lat": 40.8570, "lon": -74.1294},  # Passaic
    "CL": {"lat": 40.8584, "lon": -74.1637},  # Clifton
    "PT": {"lat": 40.9166, "lon": -74.1710},  # Paterson
    "HT": {"lat": 40.9494, "lon": -74.1527},  # Hawthorne
    "GR": {"lat": 40.9633, "lon": -74.1269},  # Glen Rock
    "RW": {"lat": 40.9808, "lon": -74.1168},  # Ridgewood
    "HH": {"lat": 40.9956, "lon": -74.1115},  # Ho-Ho-Kus
    "WA": {"lat": 41.0108, "lon": -74.1267},  # Waldwick
    "AL": {"lat": 41.0312, "lon": -74.1306},  # Allendale
    "RM": {"lat": 41.0571, "lon": -74.1413},  # Ramsey
    "R17": {"lat": 41.0615, "lon": -74.1456},  # Ramsey-Route 17
    "MH": {"lat": 41.0886, "lon": -74.1438},  # Mahwah
    "SF": {"lat": 41.1144, "lon": -74.1496},  # Suffern, NY
    # Bergen County Line (Ridgewood Branch)
    "RT": {"lat": 40.8267, "lon": -74.1069},  # Rutherford
    "WE": {"lat": 40.8356, "lon": -74.0989},  # Wesmont
    "GA": {"lat": 40.8815, "lon": -74.1133},  # Garfield
    "PL": {"lat": 40.8879, "lon": -74.1202},  # Plauderville
    "BW": {"lat": 40.9188, "lon": -74.1316},  # Broadway (Fair Lawn)
    "RB": {"lat": 40.9405, "lon": -74.1320},  # Radburn
    "GB": {"lat": 40.9595, "lon": -74.1329},  # Glen Rock–Boro Hall
    # Pascack Valley Line
    "WR": {"lat": 40.8449, "lon": -74.0883},  # Wood-Ridge
    "TB": {"lat": 40.8602, "lon": -74.0639},  # Teterboro
    "ES": {"lat": 40.8836, "lon": -74.0436},  # Essex Street
    "AN": {"lat": 40.8944, "lon": -74.0447},  # Anderson Street
    "RE": {"lat": 40.9264, "lon": -74.0413},  # River Edge
    "OR": {"lat": 40.9545, "lon": -74.0369},  # Oradell
    "EM": {"lat": 40.9758, "lon": -74.0281},  # Emerson
    "WW": {"lat": 40.9909, "lon": -74.0336},  # Westwood
    "HL": {"lat": 41.0021, "lon": -74.0408},  # Hillsdale
    "WL": {"lat": 41.0230, "lon": -74.0569},  # Woodcliff Lake
    "MV": {"lat": 41.0521, "lon": -74.0372},  # Montvale
    "PR": {"lat": 41.0595, "lon": -74.0197},  # Pearl River, NY
    "NU": {"lat": 41.0869, "lon": -74.0130},  # Nanuet, NY
    "SV": {"lat": 41.1130, "lon": -74.0436},  # Spring Valley, NY
    # Port Jervis Line (from Suffern)
    "SL": {"lat": 41.1568, "lon": -74.1937},  # Sloatsburg, NY
    "TX": {"lat": 41.1970, "lon": -74.1885},  # Tuxedo, NY
    "HR": {"lat": 41.3098, "lon": -74.1526},  # Harriman, NY
    "SM": {"lat": 41.4426, "lon": -74.1351},  # Salisbury Mills–Cornwall, NY
    "CH": {"lat": 41.4446, "lon": -74.2452},  # Campbell Hall, NY
    "MD": {"lat": 41.4459, "lon": -74.4222},  # Middletown, NY
    "OT": {"lat": 41.4783, "lon": -74.5336},  # Otisville, NY
    # Morris & Essex Line / Gladstone Branch - Updated GPS
    "ML": {"lat": 40.725667, "lon": -74.303694},  # Millburn
    "ST": {"lat": 40.7099, "lon": -74.3546},  # Summit
    "ND": {"lat": 40.7418, "lon": -74.1698},  # Newark Broad Street
    "DV": {"lat": 40.8837, "lon": -74.4753},  # Denville
    "PE": {"lat": 40.7052, "lon": -74.6550},  # Peapack
    # Montclair-Boonton Line - Updated GPS
    "MS": {"lat": 40.8695, "lon": -74.1975},  # Montclair State University
    "DO": {"lat": 40.883417, "lon": -74.555884},  # Dover
    "BO": {"lat": 40.903378, "lon": -74.407733},  # Boonton
}


def get_station_coordinates(code: str) -> dict[str, float] | None:
    """Get station coordinates for mapping.

    Args:
        code: Two-character station code

    Returns:
        Dict with lat/lon or None if not found
    """
    return STATION_COORDINATES.get(code)
