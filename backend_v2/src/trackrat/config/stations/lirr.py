"""LIRR (Long Island Rail Road) station configuration."""

# LIRR station names
# Penn Station "NY" is already defined in NJT, used for LIRR Penn Station too
LIRR_STATION_NAMES: dict[str, str] = {
    "ABT": "Albertson",
    "AGT": "Amagansett",
    "AVL": "Amityville",
    "LAT": "Atlantic Terminal",  # Using LAT to avoid conflict with Atlanta ATL
    "ADL": "Auburndale",
    "BTA": "Babylon",
    "BWN": "Baldwin",
    "BSR": "Bay Shore",
    "BSD": "Bayside",
    "BRS": "Bellerose",
    "BMR": "Bellmore",
    "BPT": "Bellport",
    "BRT": "Belmont Park",
    "BPG": "Bethpage",
    "BWD": "Brentwood",
    "BHN": "Bridgehampton",
    "BDY": "Broadway LIRR",
    "CPL": "Carle Place",
    "CHT": "Cedarhurst",
    "CI": "Central Islip",
    "CAV": "Centre Avenue",
    "CSH": "Cold Spring Harbor",
    "CPG": "Copiague",
    "LCLP": "Country Life Press",  # Using LCLP to avoid conflict with Amtrak CLP (Culpeper)
    "DPK": "Deer Park",
    "DGL": "Douglaston",
    "EHN": "East Hampton",
    "ENY": "East New York",
    "ERY": "East Rockaway",
    "EWN": "East Williston",
    "EMT": "Elmont-UBS Arena",
    "LFRY": "Far Rockaway",  # Using LFRY to avoid conflict with PATCO FRY (Ferry Avenue)
    "LFMD": "Farmingdale",  # Using LFMD to avoid conflict with Amtrak FMD (Fort Madison)
    "FPK": "Floral Park",
    "FLS": "Flushing Main Street",
    "FHL": "Forest Hills",
    "FPT": "Freeport",
    "GCY": "Garden City",
    "GBN": "Gibson",
    "GCV": "Glen Cove",
    "GHD": "Glen Head",
    "GST": "Glen Street",
    "GCT": "Grand Central Terminal",  # Shared with MNR
    "GNK": "Great Neck",
    "GRV": "Great River",
    "GWN": "Greenlawn",
    "GPT": "Greenport",
    "LGVL": "Greenvale",  # Using LGVL to avoid conflict with Amtrak GVL (Greenville)
    "HBY": "Hampton Bays",
    "HGN": "Hempstead Gardens",
    "LHEM": "Hempstead",  # Using LHEM to avoid conflict with Amtrak HEM (Hermann)
    "HWT": "Hewlett",
    "LHVL": "Hicksville",  # Using LHVL to avoid conflict with Amtrak HVL (Havelock)
    "LHOL": "Hollis",  # Using LHOL to avoid conflict with Amtrak HOL (Hollywood)
    "HPA": "Hunterspoint Avenue",
    "LHUN": "Huntington",  # Using LHUN to avoid conflict with Amtrak HUN (Huntington WV)
    "IWD": "Inwood",
    "IPK": "Island Park",
    "ISP": "Islip",
    "JAM": "Jamaica",
    "KGN": "Kew Gardens",
    "KPK": "Kings Park",
    "LLVW": "Lakeview",  # Using LLVW to avoid conflict with Amtrak LVW (Longview)
    "LTN": "Laurelton",
    "LCE": "Lawrence",
    "LHT": "Lindenhurst",
    "LLNK": "Little Neck",  # Using LLNK to avoid conflict with Amtrak LNK (Lincoln)
    "LLMR": "Locust Manor",  # Using LLMR to avoid conflict with Amtrak LMR (Lamar)
    "LVL": "Locust Valley",
    "LBH": "Long Beach",
    "LIC": "Long Island City",
    "LYN": "Lynbrook",
    "LMVN": "Malverne",  # Using LMVN to avoid conflict with Amtrak MVN (Malvern)
    "MHT": "Manhasset",
    "LMPK": "Massapequa Park",  # Using LMPK to avoid conflict with Amtrak MPK (Moorpark)
    "MQA": "Massapequa",
    "MSY": "Mastic-Shirley",
    "MAK": "Mattituck",
    "MFD": "Medford",
    "MAV": "Merillon Avenue",
    "MRK": "Merrick",
    "LSSM": "Mets-Willets Point",  # Using LSSM to avoid conflict with Amtrak SSM (Selma)
    "LMIN": "Mineola",  # Using LMIN to avoid conflict with Amtrak MIN (Mineola TX)
    "MTK": "Montauk",
    "LMHL": "Murray Hill LIRR",  # Using LMHL to avoid conflict with Amtrak MHL (Marshall)
    "NBD": "Nassau Boulevard",
    "NHP": "New Hyde Park",
    "NPT": "Northport",
    "NAV": "Nostrand Avenue",
    "ODL": "Oakdale",
    "ODE": "Oceanside",
    "OBY": "Oyster Bay",
    "PGE": "Patchogue",
    "PLN": "Pinelawn",
    "PDM": "Plandome",
    "PJN": "Port Jefferson",
    "PWS": "Port Washington",
    "QVG": "Queens Village",
    "RHD": "Riverhead",
    "RVC": "Rockville Centre",
    "RON": "Ronkonkoma",
    "ROS": "Rosedale",
    "RSN": "Roslyn",
    "SVL": "Sayville",
    "SCF": "Sea Cliff",
    "SFD": "Seaford",
    "LSTN": "Smithtown",  # Using LSTN to avoid conflict with Amtrak STN (Stanley)
    "SHN": "Southampton",
    "SHD": "Southold",
    "LSPK": "Speonk",  # Using LSPK to avoid conflict with Amtrak SPK (Spokane)
    "LSAB": "St. Albans",  # Using LSAB to avoid conflict with Amtrak SAB (St. Albans VT)
    "LSJM": "St. James",  # Using LSJM to avoid conflict with Amtrak SJM (St. Joseph)
    "SMR": "Stewart Manor",
    "LSBK": "Stony Brook",  # Using LSBK to avoid conflict with NJT BK (Bound Brook)
    "SYT": "Syosset",
    "VSM": "Valley Stream",
    "WGH": "Wantagh",
    "WHD": "West Hempstead",
    "WBY": "Westbury",
    "WHN": "Westhampton",
    "LWWD": "Westwood LIRR",  # Using LWWD to avoid conflict with Amtrak WWD (Wildwood)
    "WMR": "Woodmere",
    "WDD": "Woodside",
    "WYD": "Wyandanch",
    "YPK": "Yaphank",
}


LIRR_GTFS_RT_FEED_URL = (
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/lirr%2Fgtfs-lirr"
)

LIRR_ALERTS_FEED_URL = (
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Flirr-alerts"
)

# LIRR GTFS stop_id to internal station code mapping
# Penn Station (stop_id 237) maps to "NY" for unified experience with NJT/Amtrak
# Atlantic Terminal uses "LAT" to avoid conflict with Atlanta "ATL"
LIRR_GTFS_STOP_TO_INTERNAL_MAP: dict[str, str] = {
    "1": "ABT",  # Albertson
    "100": "ISP",  # Islip
    "101": "IWD",  # Inwood
    "102": "JAM",  # Jamaica
    "107": "KGN",  # Kew Gardens
    "11": "BDY",  # Broadway
    "111": "KPK",  # Kings Park
    "113": "LBH",  # Long Beach
    "114": "LCE",  # Lawrence
    "117": "LHT",  # Lindenhurst
    "118": "LIC",  # Long Island City
    "119": "LLMR",  # Locust Manor
    "120": "LLNK",  # Little Neck
    "122": "LTN",  # Laurelton
    "123": "LVL",  # Locust Valley
    "124": "LLVW",  # Lakeview
    "125": "LYN",  # Lynbrook
    "126": "MAK",  # Mattituck
    "127": "MAV",  # Merillon Avenue
    "129": "MFD",  # Medford
    "13": "BHN",  # Bridgehampton
    "130": "LMHL",  # Murray Hill LIRR
    "131": "MHT",  # Manhasset
    "132": "LMIN",  # Mineola
    "135": "LMPK",  # Massapequa Park
    "136": "MQA",  # Massapequa
    "14": "LSBK",  # Stony Brook (using LSBK to avoid NJT BK conflict)
    "140": "MSY",  # Mastic-Shirley
    "141": "MTK",  # Montauk
    "142": "LMVN",  # Malverne
    "148": "NAV",  # Nostrand Avenue
    "149": "NBD",  # Nassau Boulevard
    "152": "NHP",  # New Hyde Park
    "153": "NPT",  # Northport
    "154": "OBY",  # Oyster Bay
    "155": "ODE",  # Oceanside
    "157": "ODL",  # Oakdale
    "16": "BMR",  # Bellmore
    "162": "PDM",  # Plandome
    "163": "PGE",  # Patchogue
    "164": "PJN",  # Port Jefferson
    "165": "PLN",  # Pinelawn
    "171": "PWS",  # Port Washington
    "175": "QVG",  # Queens Village
    "176": "RHD",  # Riverhead
    "179": "RON",  # Ronkonkoma
    "180": "ROS",  # Rosedale
    "182": "RSN",  # Roslyn
    "183": "RVC",  # Rockville Centre
    "184": "LSAB",  # St. Albans
    "185": "SCF",  # Sea Cliff
    "187": "SFD",  # Seaford
    "190": "SHD",  # Southold
    "191": "SHN",  # Southampton
    "193": "LSJM",  # St. James
    "195": "SMR",  # Stewart Manor
    "198": "LSPK",  # Speonk
    "199": "LSSM",  # Mets-Willets Point
    "2": "ADL",  # Auburndale
    "20": "BPG",  # Bethpage
    "202": "LSTN",  # Smithtown
    "204": "SVL",  # Sayville
    "205": "SYT",  # Syosset
    "21": "BPT",  # Bellport
    "211": "VSM",  # Valley Stream
    "213": "WBY",  # Westbury
    "214": "WDD",  # Woodside
    "215": "WGH",  # Wantagh
    "216": "WHD",  # West Hempstead
    "217": "WMR",  # Woodmere
    "219": "LWWD",  # Westwood LIRR
    "220": "WYD",  # Wyandanch
    "223": "YPK",  # Yaphank
    "225": "BWN",  # Baldwin
    "226": "MRK",  # Merrick
    "23": "BRS",  # Bellerose
    "233": "WHN",  # Westhampton
    "237": "NY",  # Penn Station (unified with NJT/Amtrak)
    "24": "BRT",  # Belmont Park
    "241": "LAT",  # Atlantic Terminal
    "25": "BSD",  # Bayside
    "26": "BSR",  # Bay Shore
    "27": "BTA",  # Babylon
    "29": "BWD",  # Brentwood
    "31": "CAV",  # Centre Avenue
    "32": "CHT",  # Cedarhurst
    "33": "CI",  # Central Islip
    "349": "GCT",  # Grand Central Madison
    "359": "EMT",  # Elmont-UBS Arena
    "36": "LCLP",  # Country Life Press
    "38": "CPG",  # Copiague
    "39": "CPL",  # Carle Place
    "4": "AGT",  # Amagansett
    "40": "CSH",  # Cold Spring Harbor
    "42": "DGL",  # Douglaston
    "44": "DPK",  # Deer Park
    "48": "EHN",  # East Hampton
    "50": "ENY",  # East New York
    "51": "ERY",  # East Rockaway
    "52": "EWN",  # East Williston
    "55": "FHL",  # Forest Hills
    "56": "FLS",  # Flushing Main Street
    "59": "LFMD",  # Farmingdale
    "63": "FPK",  # Floral Park
    "64": "FPT",  # Freeport
    "65": "LFRY",  # Far Rockaway
    "66": "GBN",  # Gibson
    "67": "GCV",  # Glen Cove
    "68": "GCY",  # Garden City
    "71": "GHD",  # Glen Head
    "72": "GNK",  # Great Neck
    "73": "GPT",  # Greenport
    "74": "GRV",  # Great River
    "76": "GST",  # Glen Street
    "77": "LGVL",  # Greenvale
    "78": "GWN",  # Greenlawn
    "8": "AVL",  # Amityville
    "83": "HBY",  # Hampton Bays
    "84": "LHEM",  # Hempstead
    "85": "HGN",  # Hempstead Gardens
    "89": "LHOL",  # Hollis
    "90": "HPA",  # Hunterspoint Avenue
    "91": "LHUN",  # Huntington
    "92": "LHVL",  # Hicksville
    "94": "HWT",  # Hewlett
    "99": "IPK",  # Island Park
}

# Reverse mapping for LIRR
INTERNAL_TO_LIRR_GTFS_STOP_MAP: dict[str, str] = {
    v: k for k, v in LIRR_GTFS_STOP_TO_INTERNAL_MAP.items()
}

# LIRR route definitions (route_id -> line_code, name, color)
# Colors from official MTA GTFS
LIRR_ROUTES: dict[str, tuple[str, str, str]] = {
    "1": ("LIRR-BB", "Babylon Branch", "#00985F"),
    "2": ("LIRR-HB", "Hempstead Branch", "#CE8E00"),
    "3": ("LIRR-OB", "Oyster Bay Branch", "#00AF3F"),
    "4": ("LIRR-RK", "Ronkonkoma Branch", "#A626AA"),
    "5": ("LIRR-MK", "Montauk Branch", "#00B2A9"),
    "6": ("LIRR-LB", "Long Beach Branch", "#FF6319"),
    "7": ("LIRR-FR", "Far Rockaway Branch", "#6E3219"),
    "8": ("LIRR-WH", "West Hempstead Branch", "#00A1DE"),
    "9": ("LIRR-PW", "Port Washington Branch", "#C60C30"),
    "10": ("LIRR-PJ", "Port Jefferson Branch", "#006EC7"),
    "11": ("LIRR-BP", "Belmont Park", "#60269E"),
    "12": ("LIRR-CT", "City Terminal Zone", "#4D5357"),
    "13": ("LIRR-GP", "Greenport Service", "#A626AA"),
}

# LIRR discovery stations - major hubs to poll for train discovery
# Penn Station and Jamaica are the two most critical hubs
LIRR_DISCOVERY_STATIONS = [
    "NY",  # Penn Station (all branches terminate here)
    "JAM",  # Jamaica (transfer hub for all branches)
    "LAT",  # Atlantic Terminal
    "GCT",  # Grand Central Madison
    "HPA",  # Hunterspoint Avenue
]


def get_lirr_route_info(gtfs_route_id: str) -> tuple[str, str, str] | None:
    """Get LIRR route info from GTFS route ID.

    Args:
        gtfs_route_id: GTFS route_id (e.g., '1' for Babylon Branch)

    Returns:
        Tuple of (line_code, route_name, color) or None if not mapped
    """
    return LIRR_ROUTES.get(gtfs_route_id)


def map_lirr_gtfs_stop(gtfs_stop_id: str) -> str | None:
    """Map LIRR GTFS stop_id to our internal station code.

    Args:
        gtfs_stop_id: GTFS stop_id (e.g., '237' for Penn Station)

    Returns:
        Our internal station code (e.g., 'NY') or None if not mapped
    """
    return LIRR_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_stop_id)


# =============================================================================
# METRO-NORTH RAILROAD (MNR) CONFIGURATION
# =============================================================================
