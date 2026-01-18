"""
Station configuration for TrackRat V2.

Contains station codes, names, and related functions.
"""

# Station code to name mapping
STATION_NAMES: dict[str, str] = {
    # NJ Transit stations from authoritative STATION_CODES.txt
    "17": "Ramsey Route 17",
    "23": "Wayne-Route 23",
    "AB": "Absecon",
    "AC": "Atlantic City Rail Terminal",
    "AH": "Allenhurst",
    "AM": "Aberdeen-Matawan",
    "AN": "Annandale",
    "AO": "Atco",
    "AP": "Asbury Park",
    "AS": "Anderson Street",
    "AV": "Avenel",
    "AZ": "Allendale",
    "BA": "BWI Thurgood Marshall Airport",
    "BB": "Bradley Beach",
    "BF": "Broadway Fair Lawn",
    "BH": "Bay Head",
    "BI": "Basking Ridge",
    "BK": "Bound Brook",
    "BL": "Baltimore Station",
    "BM": "Bloomfield",
    "BN": "Boonton",
    "BS": "Belmar",
    "BU": "Brick Church",
    "BV": "Bernardsville",
    "BW": "Bridgewater",
    "BY": "Berkeley Heights",
    "CB": "Campbell Hall",
    "CH": "South Amboy",
    "CM": "Chatham",
    "CN": "Convent Station",
    "CW": "Salisbury Mills-Cornwall",
    "CY": "Cherry Hill",
    "DL": "Delawanna",
    "DN": "Dunellen",
    "DO": "Dover",
    "DV": "Denville",
    "ED": "Edison",
    "EH": "Egg Harbor City",
    "EL": "Elberon",
    "EN": "Emerson",
    "EO": "East Orange",
    "EX": "Essex Street",
    "EZ": "Elizabeth",
    "FA": "Little Falls",
    "FE": "Finderne",
    "FH": "Far Hills",
    "FW": "Fanwood",
    "FZ": "Radburn Fair Lawn",
    "GA": "Great Notch",
    "GD": "Garfield",
    "GG": "Glen Ridge",
    "GI": "Gillette",
    "GK": "Glen Rock Boro Hall",
    "GL": "Gladstone",
    "GO": "Millington",
    "GW": "Garwood",
    "HB": "Hoboken",
    "HD": "Hillsdale",
    "HG": "High Bridge",
    "HI": "Highland Avenue",
    "HL": "Hamilton",
    "HN": "Hammonton",
    "HP": "Lake Hopatcong",
    "HQ": "Hackettstown",
    "HS": "Montclair Heights",
    "HV": "Mount Arlington",
    "HW": "Hawthorne",
    "HZ": "Hazlet",
    "IF": "Clifton",
    "JA": "Jersey Avenue",
    "KG": "Kingsland",
    "LA": "Spring Lake",
    "LB": "Long Branch",
    "LI": "Linden",
    "LN": "Lyndhurst",
    "LP": "Lincoln Park",
    "LS": "Little Silver",
    "LW": "Lindenwold",
    "LY": "Lyons",
    "MA": "Madison",
    "MB": "Millburn",
    "MC": "Bay Street",
    "MH": "Murray Hill",
    "MI": "Middletown",
    "MK": "Monmouth Park",
    "ML": "Mountain Lakes",
    "MP": "Metropark",
    "MR": "Morristown",
    "MS": "Mountain Avenue",
    "MT": "Mountain Station",
    "MU": "Metuchen",
    "MV": "Mountain View",
    "MW": "Maplewood",
    "MX": "Morris Plains",
    "MZ": "Mahwah",
    "NA": "Newark Airport",
    "NB": "New Brunswick",
    "NC": "New Carrollton Station",
    "ND": "Newark Broad Street",
    "NE": "Netherwood",
    "NF": "North Philadelphia",
    "NH": "New Bridge Landing",
    "NN": "Nanuet",
    "NP": "Newark Penn Station",
    "NT": "Netcong",
    "NV": "New Providence",
    "NY": "New York Penn Station",
    "NZ": "North Elizabeth",
    "OD": "Oradell",
    "OG": "Orange",
    "OL": "Mount Olive",
    "ON": "Lebanon",
    "OR": "North Branch",
    "OS": "Otisville",
    "PC": "Peapack",
    "PE": "Perth Amboy",
    "PF": "Plainfield",
    "PH": "Philadelphia",
    "PJ": "Princeton Junction",
    "PL": "Plauderville",
    "PN": "Pennsauken",
    "PO": "Port Jervis",
    "PP": "Point Pleasant Beach",
    "PQ": "Pearl River",
    "PR": "Princeton",
    "PS": "Passaic",
    "PV": "Park Ridge",
    "RA": "Raritan",
    "RB": "Red Bank",
    "RF": "Rutherford",
    "RG": "River Edge",
    "RH": "Rahway",
    "RL": "Roselle Park",
    "RM": "Harriman",
    "RN": "Paterson",
    "RS": "Glen Rock Main Line",
    "RT": "Short Hills",
    "RW": "Ridgewood",
    "RY": "Ramsey Main St",
    "SC": "Secaucus Concourse",
    "SE": "Secaucus Upper Lvl",
    "SF": "Suffern",
    "SG": "Stirling",
    "SM": "Somerville",
    "SO": "South Orange",
    "SQ": "Manasquan",
    "ST": "Summit",
    "SV": "Spring Valley",
    "TB": "Mount Tabor",
    "TC": "Tuxedo",
    "TE": "Teterboro",
    "TO": "Towaco",
    "TR": "Trenton",
    "TS": "Secaucus Lower Lvl",
    "UF": "Hohokus",
    "UM": "Upper Montclair",
    "US": "Union",
    "UV": "Montclair State U",
    "WB": "Woodbridge",
    "WF": "Westfield",
    "WG": "Watchung Avenue",
    "WH": "White House",
    "WI": "Wilmington Station",
    "WK": "Waldwick",
    "WL": "Woodcliff Lake",
    "WM": "Wesmont",
    "WR": "Wood Ridge",
    "WT": "Watsessing Avenue",
    "WW": "Westwood",
    "XC": "Cranford",
    "XG": "Sloatsburg",
    "ZM": "Montvale",
    # Additional Amtrak stations not in NJ Transit network
    "WS": "Washington Union Station",
    "BOS": "Boston South Station",
    "BBY": "Boston Back Bay",
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
    "MSS": "Manassas",
    "NFK": "Norfolk",
    "RVR": "Richmond Staples Mill Road",
    "RVM": "Richmond Main Street",
    "RNK": "Roanoke",
    # Southeast Amtrak stations
    "CLT": "Charlotte",
    "RGH": "Raleigh",
    "SEL": "Selma-Smithfield",
    "WLN": "Wilson",
    "RMT": "Rocky Mount",
    "PTB": "Petersburg",
    "SAV": "Savannah",
    "JES": "Jesup",
    "JAX": "Jacksonville",
    "WLD": "Waldo",
    "OCA": "Ocala",
    "WTH": "Winter Haven",
    "LKL": "Lakeland",
    "TPA": "Tampa",
    "WPB": "West Palm Beach",
    "DLB": "Delray Beach",
    "FTL": "Fort Lauderdale",
    "HLW": "Hollywood",
    "MIA": "Miami",
    "ORL": "Orlando",
    "KIS": "Kissimmee",
    "WPK": "Winter Park",
    "DLD": "DeLand",
    "PAL": "Palatka",
    "SAN": "Sanford",
    "THU": "Thurmond",
    "CHS": "Charleston",
    "KTR": "Kingstree",
    "FLO": "Florence",
    "DIL": "Dillon",
    "HAM": "Hamlet",
    "SOU": "Southern Pines",
    "CAR": "Cary",
    "DNC": "Durham",
    "GRB": "Greensboro",
    "HPT": "High Point",
    "SAL": "Salisbury",
    "GAS": "Gastonia",
    "SPB": "Spartanburg",
    "GVL": "Greenville",
    "ATL": "Atlanta",
    "GAI": "Gainesville",
    "TOC": "Toccoa",
    "CSN": "Clemson",
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
    "MSS": "MSS",  # Manassas, VA
    "NFK": "NFK",  # Norfolk, VA
    "RVR": "RVR",  # Richmond Staples Mill Road, VA
    "RVM": "RVM",  # Richmond Main Street, VA
    "RNK": "RNK",  # Roanoke, VA
    # Southeast Amtrak stations
    "CLT": "CLT",  # Charlotte, NC
    "RGH": "RGH",  # Raleigh, NC
    "SEL": "SEL",  # Selma-Smithfield, NC
    "WLN": "WLN",  # Wilson, NC
    "RMT": "RMT",  # Rocky Mount, NC
    "PTB": "PTB",  # Petersburg, VA
    "SAV": "SAV",  # Savannah, GA
    "JES": "JES",  # Jesup, GA
    "JAX": "JAX",  # Jacksonville, FL
    "WLD": "WLD",  # Waldo, FL
    "OCA": "OCA",  # Ocala, FL
    "WTH": "WTH",  # Winter Haven, FL
    "LKL": "LKL",  # Lakeland, FL
    "TPA": "TPA",  # Tampa, FL
    "WPB": "WPB",  # West Palm Beach, FL
    "DLB": "DLB",  # Delray Beach, FL
    "FTL": "FTL",  # Fort Lauderdale, FL
    "HLW": "HLW",  # Hollywood, FL
    "MIA": "MIA",  # Miami, FL
    "ORL": "ORL",  # Orlando, FL
    "KIS": "KIS",  # Kissimmee, FL
    "WPK": "WPK",  # Winter Park, FL
    "DLD": "DLD",  # DeLand, FL
    "PAL": "PAL",  # Palatka, FL
    "SAN": "SAN",  # Sanford, FL
    "THU": "THU",  # Thurmond, WV
    "CHS": "CHS",  # Charleston, SC
    "KTR": "KTR",  # Kingstree, SC
    "FLO": "FLO",  # Florence, SC
    "DIL": "DIL",  # Dillon, SC
    "HAM": "HAM",  # Hamlet, NC
    "SOU": "SOU",  # Southern Pines, NC
    "CAR": "CAR",  # Cary, NC
    "DNC": "DNC",  # Durham, NC
    "GRB": "GRB",  # Greensboro, NC
    "HPT": "HPT",  # High Point, NC
    "SAL": "SAL",  # Salisbury, NC
    "GAS": "GAS",  # Gastonia, NC
    "SPB": "SPB",  # Spartanburg, SC
    "GVL": "GVL",  # Greenville, SC
    "ATL": "ATL",  # Atlanta, GA
    "GAI": "GAI",  # Gainesville, GA
    "TOC": "TOC",  # Toccoa, GA
    "CSN": "CSN",  # Clemson, SC
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
    "MSS": "MSS",  # Manassas, VA
    "NFK": "NFK",  # Norfolk, VA
    "RVR": "RVR",  # Richmond Staples Mill Road, VA
    "RVM": "RVM",  # Richmond Main Street, VA
    "RNK": "RNK",  # Roanoke, VA
    # Southeast Amtrak stations
    "CLT": "CLT",  # Charlotte, NC
    "RGH": "RGH",  # Raleigh, NC
    "SEL": "SEL",  # Selma-Smithfield, NC
    "WLN": "WLN",  # Wilson, NC
    "RMT": "RMT",  # Rocky Mount, NC
    "PTB": "PTB",  # Petersburg, VA
    "SAV": "SAV",  # Savannah, GA
    "JES": "JES",  # Jesup, GA
    "JAX": "JAX",  # Jacksonville, FL
    "WLD": "WLD",  # Waldo, FL
    "OCA": "OCA",  # Ocala, FL
    "WTH": "WTH",  # Winter Haven, FL
    "LKL": "LKL",  # Lakeland, FL
    "TPA": "TPA",  # Tampa, FL
    "WPB": "WPB",  # West Palm Beach, FL
    "DLB": "DLB",  # Delray Beach, FL
    "FTL": "FTL",  # Fort Lauderdale, FL
    "HLW": "HLW",  # Hollywood, FL
    "MIA": "MIA",  # Miami, FL
    "ORL": "ORL",  # Orlando, FL
    "KIS": "KIS",  # Kissimmee, FL
    "WPK": "WPK",  # Winter Park, FL
    "DLD": "DLD",  # DeLand, FL
    "PAL": "PAL",  # Palatka, FL
    "SAN": "SAN",  # Sanford, FL
    "THU": "THU",  # Thurmond, WV
    "CHS": "CHS",  # Charleston, SC
    "KTR": "KTR",  # Kingstree, SC
    "FLO": "FLO",  # Florence, SC
    "DIL": "DIL",  # Dillon, SC
    "HAM": "HAM",  # Hamlet, NC
    "SOU": "SOU",  # Southern Pines, NC
    "CAR": "CAR",  # Cary, NC
    "DNC": "DNC",  # Durham, NC
    "GRB": "GRB",  # Greensboro, NC
    "HPT": "HPT",  # High Point, NC
    "SAL": "SAL",  # Salisbury, NC
    "GAS": "GAS",  # Gastonia, NC
    "SPB": "SPB",  # Spartanburg, SC
    "GVL": "GVL",  # Greenville, SC
    "ATL": "ATL",  # Atlanta, GA
    "GAI": "GAI",  # Gainesville, GA
    "TOC": "TOC",  # Toccoa, GA
    "CSN": "CSN",  # Clemson, SC
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
    # Major NJ Transit/Amtrak hubs - verified coordinates
    "NY": {"lat": 40.7506, "lon": -73.9939},  # New York Penn Station
    "NP": {"lat": 40.7347, "lon": -74.1644},  # Newark Penn Station
    "TR": {"lat": 40.218518, "lon": -74.753923},  # Trenton Transit Center
    "PJ": {"lat": 40.3167, "lon": -74.6233},  # Princeton Junction
    "MP": {"lat": 40.5378, "lon": -74.3562},  # Metropark
    "NA": {"lat": 40.7058, "lon": -74.1608},  # Newark Airport
    "NB": {"lat": 40.4862, "lon": -74.4518},  # New Brunswick
    "SE": {"lat": 40.7612, "lon": -74.0758},  # Secaucus Upper Level
    "SC": {"lat": 40.7612, "lon": -74.0758},  # Secaucus Concourse
    "TS": {"lat": 40.7612, "lon": -74.0758},  # Secaucus Lower Level
    "HB": {"lat": 40.734843, "lon": -74.028043},  # Hoboken Terminal
    "PH": {"lat": 39.9570, "lon": -75.1820},  # Philadelphia 30th Street Station
    "WI": {"lat": 39.7369, "lon": -75.5522},  # Wilmington
    "BA": {"lat": 39.1896, "lon": -76.6934},  # BWI Airport Rail Station
    "BL": {"lat": 39.3081, "lon": -76.6175},  # Baltimore Penn Station
    "WS": {"lat": 38.8973, "lon": -77.0064},  # Washington Union Station
    "BOS": {"lat": 42.3520, "lon": -71.0552},  # Boston South Station
    "BBY": {"lat": 42.3473, "lon": -71.0764},  # Boston Back Bay
    # NJ Coast Line
    "LB": {"lat": 40.3042, "lon": -73.9920},  # Long Branch
    "AP": {"lat": 40.2202, "lon": -74.0120},  # Asbury Park
    "BS": {"lat": 40.1784, "lon": -74.0276},  # Belmar
    "SQ": {"lat": 40.1057, "lon": -74.0500},  # Manasquan
    "PP": {"lat": 40.0917, "lon": -74.0680},  # Point Pleasant Beach
    "BH": {"lat": 40.0585, "lon": -74.1066},  # Bay Head
    "AH": {"lat": 40.2301, "lon": -74.0063},  # Allenhurst
    "EL": {"lat": 40.2689, "lon": -73.9858},  # Elberon
    "LS": {"lat": 40.3369, "lon": -74.0436},  # Little Silver
    "MK": {"lat": 40.3086, "lon": -74.0253},  # Monmouth Park
    "RB": {"lat": 40.3503, "lon": -74.0750},  # Red Bank
    "HZ": {"lat": 40.4236, "lon": -74.1848},  # Hazlet
    "AM": {"lat": 40.4183, "lon": -74.2206},  # Aberdeen-Matawan
    "MI": {"lat": 40.4453, "lon": -74.1126},  # Middletown
    "LA": {"lat": 40.1530, "lon": -74.0340},  # Spring Lake
    "BB": {"lat": 40.1929, "lon": -74.0218},  # Bradley Beach
    # Northeast Corridor
    "EZ": {"lat": 40.667859, "lon": -74.215171},  # Elizabeth
    "LI": {"lat": 40.629487, "lon": -74.251772},  # Linden
    "RH": {"lat": 40.6039, "lon": -74.2723},  # Rahway
    "MU": {"lat": 40.5378, "lon": -74.3562},  # Metuchen
    "ED": {"lat": 40.5177, "lon": -74.4075},  # Edison
    "HL": {"lat": 40.1992, "lon": -74.6877},  # Hamilton
    "NZ": {"lat": 40.6968, "lon": -74.1733},  # North Elizabeth
    # Raritan Valley Line
    "RA": {"lat": 40.5682, "lon": -74.6290},  # Raritan
    "BK": {"lat": 40.5582, "lon": -74.5397},  # Bound Brook
    "BW": {"lat": 40.5697, "lon": -74.5194},  # Bridgewater
    "SM": {"lat": 40.5681, "lon": -74.6119},  # Somerville
    "DN": {"lat": 40.5892, "lon": -74.4719},  # Dunellen
    "PF": {"lat": 40.6140, "lon": -74.4147},  # Plainfield
    "NE": {"lat": 40.6344, "lon": -74.4182},  # Netherwood
    "FW": {"lat": 40.6415, "lon": -74.3826},  # Fanwood
    "WF": {"lat": 40.6588, "lon": -74.3488},  # Westfield
    "GW": {"lat": 40.6514, "lon": -74.3241},  # Garwood
    "XC": {"lat": 40.6559, "lon": -74.3004},  # Cranford
    "RL": {"lat": 40.6642, "lon": -74.2687},  # Roselle Park
    "US": {"lat": 40.6973, "lon": -74.2636},  # Union
    "HG": {"lat": 40.7133, "lon": -74.8771},  # High Bridge
    "AN": {"lat": 40.6994, "lon": -74.8819},  # Annandale
    "ON": {"lat": 40.6414, "lon": -74.8283},  # Lebanon
    "WH": {"lat": 40.6390, "lon": -74.7632},  # White House
    # Morris & Essex Line
    "ST": {"lat": 40.7099, "lon": -74.3546},  # Summit
    "CM": {"lat": 40.7428, "lon": -74.4319},  # Chatham
    "MA": {"lat": 40.7698, "lon": -74.4151},  # Madison
    "CN": {"lat": 40.7806, "lon": -74.4656},  # Convent Station
    "MR": {"lat": 40.7970, "lon": -74.4724},  # Morristown
    "MX": {"lat": 40.8256, "lon": -74.4615},  # Morris Plains
    "DV": {"lat": 40.8838, "lon": -74.4752},  # Denville
    "DO": {"lat": 40.883417, "lon": -74.555884},  # Dover
    "MT": {"lat": 40.9042, "lon": -74.6254},  # Mount Tabor
    "HQ": {"lat": 41.0046, "lon": -74.7973},  # Hackettstown
    "MB": {"lat": 40.725667, "lon": -74.303694},  # Millburn
    "RT": {"lat": 40.7144, "lon": -74.3215},  # Short Hills
    "ND": {"lat": 40.7418, "lon": -74.1698},  # Newark Broad Street
    "OG": {"lat": 40.7706, "lon": -74.2327},  # Orange
    "HI": {"lat": 40.7681, "lon": -74.2470},  # Highland Avenue
    "MV": {"lat": 40.8122, "lon": -74.2425},  # Mountain View
    "SO": {"lat": 40.7591, "lon": -74.2528},  # South Orange
    "MW": {"lat": 40.7503, "lon": -74.2736},  # Maplewood
    # Gladstone Branch
    "BV": {"lat": 40.7184, "lon": -74.6194},  # Bernardsville
    "FH": {"lat": 40.6834, "lon": -74.6359},  # Far Hills
    "PC": {"lat": 40.7052, "lon": -74.6550},  # Peapack
    "GL": {"lat": 40.7194, "lon": -74.6653},  # Gladstone
    "SG": {"lat": 40.7422, "lon": -74.5438},  # Stirling
    "GO": {"lat": 40.7028, "lon": -74.5622},  # Millington
    "LY": {"lat": 40.6723, "lon": -74.5662},  # Lyons
    "BI": {"lat": 40.6828, "lon": -74.5607},  # Basking Ridge
    "MH": {"lat": 40.7731, "lon": -74.4984},  # Murray Hill
    "NV": {"lat": 40.7355, "lon": -74.4641},  # New Providence
    "BY": {"lat": 40.6976, "lon": -74.5031},  # Berkeley Heights
    "GI": {"lat": 40.7527, "lon": -74.5241},  # Gillette
    # Main/Bergen County Lines
    "RF": {"lat": 40.8267, "lon": -74.1069},  # Rutherford
    "LN": {"lat": 40.8123, "lon": -74.1246},  # Lyndhurst
    "KG": {"lat": 40.8044, "lon": -74.1399},  # Kingsland
    "DL": {"lat": 40.8180, "lon": -74.1370},  # Delawanna
    "PS": {"lat": 40.8570, "lon": -74.1294},  # Passaic
    "IF": {"lat": 40.8584, "lon": -74.1637},  # Clifton
    "RN": {"lat": 40.9166, "lon": -74.1710},  # Paterson
    "HW": {"lat": 40.9494, "lon": -74.1527},  # Hawthorne
    "GK": {"lat": 40.9719, "lon": -74.1338},  # Glen Rock Boro Hall
    "RS": {"lat": 40.9633, "lon": -74.1269},  # Glen Rock Main Line
    "RW": {"lat": 40.9808, "lon": -74.1168},  # Ridgewood
    "UF": {"lat": 40.9956, "lon": -74.1115},  # Ho-Ho-Kus
    "WK": {"lat": 41.0108, "lon": -74.1267},  # Waldwick
    "AZ": {"lat": 41.0312, "lon": -74.1306},  # Allendale
    "RY": {"lat": 41.0571, "lon": -74.1413},  # Ramsey Main St
    "17": {"lat": 41.0615, "lon": -74.1456},  # Ramsey-Route 17
    "MZ": {"lat": 41.0886, "lon": -74.1438},  # Mahwah
    "SF": {"lat": 41.1144, "lon": -74.1496},  # Suffern, NY
    # Montclair-Boonton Line
    "BM": {"lat": 40.8132, "lon": -74.2050},  # Bloomfield
    "GG": {"lat": 40.8061, "lon": -74.2070},  # Glen Ridge
    "BF": {"lat": 40.8926, "lon": -74.1405},  # Broadway Fair Lawn
    "FZ": {"lat": 40.9405, "lon": -74.1320},  # Radburn Fair Lawn
    "HS": {"lat": 40.8283, "lon": -74.2093},  # Montclair Heights
    "MS": {"lat": 40.8263, "lon": -74.2022},  # Mountain Avenue
    "UM": {"lat": 40.8295, "lon": -74.1987},  # Upper Montclair
    "WG": {"lat": 40.8070, "lon": -74.1871},  # Watchung Avenue
    "WT": {"lat": 40.8033, "lon": -74.1738},  # Watsessing Avenue
    "UV": {"lat": 40.8695, "lon": -74.1975},  # Montclair State University
    "FA": {"lat": 40.8757, "lon": -74.2290},  # Little Falls
    "GA": {"lat": 40.8847, "lon": -74.2539},  # Great Notch
    "TB": {"lat": 40.9033, "lon": -74.3959},  # Mount Tabor
    "BN": {"lat": 40.903378, "lon": -74.407733},  # Boonton
    "ML": {"lat": 40.9248, "lon": -74.4095},  # Mountain Lakes
    "LP": {"lat": 40.8822, "lon": -74.3014},  # Lincoln Park
    "TO": {"lat": 40.8723, "lon": -74.2808},  # Towaco
    "HV": {"lat": 40.8648, "lon": -74.5473},  # Mount Arlington
    "HP": {"lat": 40.9298, "lon": -74.6631},  # Lake Hopatcong
    "NT": {"lat": 40.9036, "lon": -74.6969},  # Netcong
    "OL": {"lat": 40.8450, "lon": -74.6885},  # Mount Olive
    "WM": {"lat": 40.8356, "lon": -74.0989},  # Wesmont
    "EO": {"lat": 40.7661, "lon": -74.2052},  # East Orange
    # Pascack Valley Line
    "WR": {"lat": 40.8449, "lon": -74.0883},  # Wood Ridge
    "TE": {"lat": 40.8602, "lon": -74.0639},  # Teterboro
    "EX": {"lat": 40.8836, "lon": -74.0436},  # Essex Street
    "AS": {"lat": 40.8944, "lon": -74.0447},  # Anderson Street
    "RG": {"lat": 40.9264, "lon": -74.0413},  # River Edge
    "NH": {"lat": 40.9119, "lon": -74.0362},  # New Bridge Landing
    "OD": {"lat": 40.9545, "lon": -74.0369},  # Oradell
    "EN": {"lat": 40.9758, "lon": -74.0281},  # Emerson
    "WW": {"lat": 40.9909, "lon": -74.0336},  # Westwood
    "HD": {"lat": 41.0021, "lon": -74.0408},  # Hillsdale
    "WL": {"lat": 41.0230, "lon": -74.0569},  # Woodcliff Lake
    "PV": {"lat": 41.0371, "lon": -74.0743},  # Park Ridge
    "ZM": {"lat": 41.0521, "lon": -74.0372},  # Montvale
    "PQ": {"lat": 41.0595, "lon": -74.0197},  # Pearl River, NY
    "NN": {"lat": 41.0869, "lon": -74.0130},  # Nanuet, NY
    "SV": {"lat": 41.1130, "lon": -74.0436},  # Spring Valley, NY
    # Port Jervis Line
    "XG": {"lat": 41.1568, "lon": -74.1937},  # Sloatsburg, NY
    "TC": {"lat": 41.1970, "lon": -74.1885},  # Tuxedo, NY
    "RM": {"lat": 41.3098, "lon": -74.1526},  # Harriman, NY
    "CW": {"lat": 41.4426, "lon": -74.1351},  # Salisbury Mills-Cornwall, NY
    "CB": {"lat": 41.4446, "lon": -74.2452},  # Campbell Hall, NY
    "OS": {"lat": 41.4783, "lon": -74.5336},  # Otisville, NY
    "PO": {"lat": 41.3753, "lon": -74.6897},  # Port Jervis, NY
    "23": {"lat": 40.8932, "lon": -74.2458},  # Wayne-Route 23
    # Raritan Valley Line Extension
    "JA": {"lat": 40.7328, "lon": -74.0379},  # Jersey Avenue
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
    "ABE": {
        "lat": 39.5095,
        "lon": -76.1630,
    },  # Aberdeen, MD (Note: conflict with AM for Aberdeen-Matawan)
    "NCR": {
        "lat": 38.9533,
        "lon": -76.8644,
    },  # New Carrollton, MD (Note: conflict with NC)
    "SPG": {"lat": 42.1060, "lon": -72.5936},  # Springfield, MA
    "CLA": {"lat": 43.3688, "lon": -72.3793},  # Claremont, NH
    "DOV": {
        "lat": 43.1979,
        "lon": -70.8737,
    },  # Dover, NH (Note: conflict with DO for Dover NJ)
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
    "MSS": {"lat": 38.7511, "lon": -77.4752},  # Manassas, VA
    "NFK": {"lat": 36.8583, "lon": -76.2876},  # Norfolk, VA
    "RVR": {"lat": 37.61741, "lon": -77.49755},  # Richmond Staples Mill Road, VA
    "RVM": {"lat": 37.6143, "lon": -77.4966},  # Richmond Main Street, VA
    "RNK": {"lat": 37.3077, "lon": -79.9803},  # Roanoke, VA
}


def get_station_coordinates(code: str) -> dict[str, float] | None:
    """Get station coordinates for mapping.

    Args:
        code: Two-character station code

    Returns:
        Dict with lat/lon or None if not found
    """
    return STATION_COORDINATES.get(code)


# Discovery stations for train polling - centralized configuration
DISCOVERY_STATIONS = [
    "NY",  # New York Penn Station
    "NP",  # Newark Penn Station
    "TR",  # Trenton
    "LB",  # Long Branch
    "PL",  # Plauderville
    "DN",  # Denville
    "MP",  # Metropark
    "HB",  # Hoboken
    "HG",  # High Bridge
    "GL",  # Gladstone
    "ND",  # Newark Broad Street
    "HQ",  # Hackettstown
    "DV",  # Dover
    "JA",  # Jersey Avenue
    "RA",  # Raritan
    "ST",  # Summit - major Morris & Essex terminal for inbound trains
    "SV",  # Spring Valley - Pascack Valley Line terminus
]


# =============================================================================
# GTFS Station Mapping
# =============================================================================

# Reverse mapping from station name (normalized) to code for GTFS matching
# Built from STATION_NAMES for efficient lookup
_NORMALIZED_NAME_TO_CODE: dict[str, str] = {}


def _normalize_station_name(name: str) -> str:
    """Normalize station name for fuzzy matching.

    Handles variations like:
    - "NEW YORK PENN STATION" -> "new york penn station"
    - "Newark Penn Station" -> "newark penn station"
    - "Trenton Transit Center" -> "trenton transit center"
    """
    return name.lower().strip()


def _build_name_to_code_map() -> dict[str, str]:
    """Build reverse mapping from normalized names to codes."""
    if _NORMALIZED_NAME_TO_CODE:
        return _NORMALIZED_NAME_TO_CODE

    for code, name in STATION_NAMES.items():
        normalized = _normalize_station_name(name)
        _NORMALIZED_NAME_TO_CODE[normalized] = code

        # Also add common variations
        # Remove common suffixes for matching
        for suffix in [" station", " terminal", " transit center"]:
            if normalized.endswith(suffix):
                base = normalized[: -len(suffix)].strip()
                if base not in _NORMALIZED_NAME_TO_CODE:
                    _NORMALIZED_NAME_TO_CODE[base] = code

    return _NORMALIZED_NAME_TO_CODE


def map_gtfs_stop_to_station_code(
    gtfs_stop_id: str, gtfs_stop_name: str, data_source: str
) -> str | None:
    """Map a GTFS stop to our internal station code.

    Args:
        gtfs_stop_id: The GTFS stop_id (numeric for NJT, code for Amtrak)
        gtfs_stop_name: The GTFS stop_name for fallback matching
        data_source: "NJT" or "AMTRAK"

    Returns:
        Our internal station code or None if no match found
    """
    if data_source == "AMTRAK":
        # Amtrak uses their standard codes as stop_id
        return map_amtrak_station_code(gtfs_stop_id)

    # For NJ Transit, try to match by name
    name_map = _build_name_to_code_map()
    normalized_name = _normalize_station_name(gtfs_stop_name)

    # Direct match
    if normalized_name in name_map:
        return name_map[normalized_name]

    # Try matching just the first part of the name (before any dash or parenthesis)
    for separator in [" - ", " (", "-"]:
        if separator in normalized_name:
            base_name = normalized_name.split(separator)[0].strip()
            if base_name in name_map:
                return name_map[base_name]

    # Try partial matching for common patterns
    # "Penn Station New York" -> match "New York Penn Station"
    for stored_name, code in name_map.items():
        # Check if all words from one are in the other
        stored_words = set(stored_name.split())
        name_words = set(normalized_name.split())
        if len(stored_words & name_words) >= 2:  # At least 2 words match
            # Prefer matches with more overlap
            overlap = len(stored_words & name_words) / max(
                len(stored_words), len(name_words)
            )
            if overlap >= 0.5:
                return code

    return None


def get_station_code_by_name(name: str) -> str | None:
    """Get station code by looking up a station name.

    Args:
        name: Station name to look up

    Returns:
        Station code or None if not found
    """
    name_map = _build_name_to_code_map()
    normalized = _normalize_station_name(name)
    return name_map.get(normalized)
