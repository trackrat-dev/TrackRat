"""Metro-North Railroad station configuration."""

# Metro-North station names (GCT shared with LIRR)
MNR_STATION_NAMES: dict[str, str] = {
    # Metro-North Railroad stations (GCT shared with LIRR above)
    "M125": "Harlem-125th Street",
    "MEYS": "Yankees-E 153 St",
    "MMRH": "Morris Heights",
    "MUNH": "University Heights",
    "MMBL": "Marble Hill",
    "MSDV": "Spuyten Duyvil",
    "MRVD": "Riverdale",
    "MLUD": "Ludlow",
    "MYON": "Yonkers",
    "MGWD": "Glenwood",
    "MGRY": "Greystone",
    "MHOH": "Hastings-on-Hudson",
    "MDBF": "Dobbs Ferry",
    "MARD": "Ardsley-on-Hudson",
    "MIRV": "Irvington",
    "MTTN": "Tarrytown",
    "MPHM": "Philipse Manor",
    "MSCB": "Scarborough",
    "MOSS": "Ossining",
    "MCRH": "Croton-Harmon",
    "MCRT": "Cortlandt",
    "MPKS": "Peekskill",
    "MMAN": "Manitou",
    "MGAR": "Garrison",
    "MCSP": "Cold Spring",
    "MBRK": "Breakneck Ridge",
    "MBCN": "Beacon",
    "MNHB": "New Hamburg",
    "MPOK": "Poughkeepsie",
    "MMEL": "Melrose",
    "MTRM": "Tremont",
    "MFOR": "Fordham",
    "MBOG": "Botanical Garden",
    "MWBG": "Williams Bridge",
    "MWDL": "Woodlawn",
    "MWKF": "Wakefield",
    "MMVW": "Mt Vernon West",
    "MFLT": "Fleetwood",
    "MBRX": "Bronxville",
    "MTUC": "Tuckahoe",
    "MCWD": "Crestwood",
    "MSCD": "Scarsdale",
    "MHSD": "Hartsdale",
    "MWPL": "White Plains",
    "MNWP": "North White Plains",
    "MVAL": "Valhalla",
    "MMTP": "Mt Pleasant",
    "MHWT": "Hawthorne",
    "MPLV": "Pleasantville",
    "MCHP": "Chappaqua",
    "MMTK": "Mt Kisco",
    "MBDH": "Bedford Hills",
    "MKAT": "Katonah",
    "MGLD": "Goldens Bridge",
    "MPRD": "Purdy's",
    "MCFL": "Croton Falls",
    "MBRS": "Brewster",
    "MSET": "Southeast",
    "MPAT": "Patterson",
    "MPAW": "Pawling",
    "MAPT": "Appalachian Trail",
    "MHVW": "Harlem Valley-Wingdale",
    "MDVP": "Dover Plains",
    "MTMR": "Tenmile River",
    "MWAS": "Wassaic",
    "MMVE": "Mt Vernon East",
    "MPEL": "Pelham",
    "MNRC": "New Rochelle",
    "MLRM": "Larchmont",
    "MMAM": "Mamaroneck",
    "MHRR": "Harrison",
    "MRYE": "Rye",
    "MPCH": "Port Chester",
    "MGRN": "Greenwich",
    "MCOC": "Cos Cob",
    "MRSD": "Riverside",
    "MODG": "Old Greenwich",
    "MSTM": "Stamford",
    "MNOH": "Noroton Heights",
    "MDAR": "Darien",
    "MROW": "Rowayton",
    "MSNW": "South Norwalk",
    "MENW": "East Norwalk",
    "MWPT": "Westport",
    "MGRF": "Green's Farms",
    "MSPT": "Southport",
    "MFFD": "Fairfield",
    "MFBR": "Fairfield-Black Rock",
    "MBGP": "Bridgeport",
    "MSTR": "Stratford",
    "MMIL": "Milford",
    "MWHN": "West Haven",
    "MNHV": "New Haven",
    "MNSS": "New Haven-State St",
    "MGLB": "Glenbrook",
    "MSPD": "Springdale",
    "MTMH": "Talmadge Hill",
    "MNCA": "New Canaan",
    "MMR7": "Merritt 7",
    "MWIL": "Wilton",
    "MCAN": "Cannondale",
    "MBVL": "Branchville",
    "MRED": "Redding",
    "MBTH": "Bethel",
    "MDBY": "Danbury",
    "MDBS": "Derby-Shelton",
    "MANS": "Ansonia",
    "MSYM": "Seymour",
    "MBCF": "Beacon Falls",
    "MNAU": "Naugatuck",
    "MWTB": "Waterbury",
}


MNR_GTFS_RT_FEED_URL = (
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/mnr%2Fgtfs-mnr"
)

MNR_ALERTS_FEED_URL = (
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fmnr-alerts"
)

# MNR GTFS stop_id to internal station code mapping
# Grand Central (stop_id 1) maps to "GCT" for unified experience
# Codes use M prefix to avoid conflicts with NJT/Amtrak/LIRR
MNR_GTFS_STOP_TO_INTERNAL_MAP: dict[str, str] = {
    # Hudson Line
    "1": "GCT",  # Grand Central Terminal (shared)
    "4": "M125",  # Harlem-125th Street
    "622": "MEYS",  # Yankees-E 153 St
    "9": "MMRH",  # Morris Heights
    "10": "MUNH",  # University Heights
    "11": "MMBL",  # Marble Hill
    "14": "MSDV",  # Spuyten Duyvil
    "16": "MRVD",  # Riverdale
    "17": "MLUD",  # Ludlow
    "18": "MYON",  # Yonkers
    "19": "MGWD",  # Glenwood
    "20": "MGRY",  # Greystone
    "22": "MHOH",  # Hastings-on-Hudson
    "23": "MDBF",  # Dobbs Ferry
    "24": "MARD",  # Ardsley-on-Hudson
    "25": "MIRV",  # Irvington
    "27": "MTTN",  # Tarrytown
    "29": "MPHM",  # Philipse Manor
    "30": "MSCB",  # Scarborough
    "31": "MOSS",  # Ossining
    "33": "MCRH",  # Croton-Harmon
    "37": "MCRT",  # Cortlandt
    "39": "MPKS",  # Peekskill
    "40": "MMAN",  # Manitou
    "42": "MGAR",  # Garrison
    "43": "MCSP",  # Cold Spring
    "44": "MBRK",  # Breakneck Ridge
    "46": "MBCN",  # Beacon
    "49": "MNHB",  # New Hamburg
    "51": "MPOK",  # Poughkeepsie
    # Harlem Line
    "54": "MMEL",  # Melrose
    "55": "MTRM",  # Tremont
    "56": "MFOR",  # Fordham
    "57": "MBOG",  # Botanical Garden
    "58": "MWBG",  # Williams Bridge
    "59": "MWDL",  # Woodlawn
    "61": "MWKF",  # Wakefield
    "62": "MMVW",  # Mt Vernon West
    "64": "MFLT",  # Fleetwood
    "65": "MBRX",  # Bronxville
    "66": "MTUC",  # Tuckahoe
    "68": "MCWD",  # Crestwood
    "71": "MSCD",  # Scarsdale
    "72": "MHSD",  # Hartsdale
    "74": "MWPL",  # White Plains
    "76": "MNWP",  # North White Plains
    "78": "MVAL",  # Valhalla
    "79": "MMTP",  # Mt Pleasant
    "80": "MHWT",  # Hawthorne
    "81": "MPLV",  # Pleasantville
    "83": "MCHP",  # Chappaqua
    "84": "MMTK",  # Mt Kisco
    "85": "MBDH",  # Bedford Hills
    "86": "MKAT",  # Katonah
    "88": "MGLD",  # Goldens Bridge
    "89": "MPRD",  # Purdy's
    "90": "MCFL",  # Croton Falls
    "91": "MBRS",  # Brewster
    "94": "MSET",  # Southeast
    "97": "MPAT",  # Patterson
    "98": "MPAW",  # Pawling
    "99": "MAPT",  # Appalachian Trail
    "100": "MHVW",  # Harlem Valley-Wingdale
    "101": "MDVP",  # Dover Plains
    "176": "MTMR",  # Tenmile River
    "177": "MWAS",  # Wassaic
    # New Haven Line
    "105": "MMVE",  # Mt Vernon East
    "106": "MPEL",  # Pelham
    "108": "MNRC",  # New Rochelle
    "110": "MLRM",  # Larchmont
    "111": "MMAM",  # Mamaroneck
    "112": "MHRR",  # Harrison
    "114": "MRYE",  # Rye
    "115": "MPCH",  # Port Chester
    "116": "MGRN",  # Greenwich
    "118": "MCOC",  # Cos Cob
    "120": "MRSD",  # Riverside
    "121": "MODG",  # Old Greenwich
    "124": "MSTM",  # Stamford
    "127": "MNOH",  # Noroton Heights
    "128": "MDAR",  # Darien
    "129": "MROW",  # Rowayton
    "131": "MSNW",  # South Norwalk
    "133": "MENW",  # East Norwalk
    "134": "MWPT",  # Westport
    "136": "MGRF",  # Green's Farms
    "137": "MSPT",  # Southport
    "138": "MFFD",  # Fairfield
    "188": "MFBR",  # Fairfield-Black Rock
    "140": "MBGP",  # Bridgeport
    "143": "MSTR",  # Stratford
    "145": "MMIL",  # Milford
    "190": "MWHN",  # West Haven
    "149": "MNHV",  # New Haven
    "151": "MNSS",  # New Haven-State St
    # New Canaan Branch
    "153": "MGLB",  # Glenbrook
    "154": "MSPD",  # Springdale
    "155": "MTMH",  # Talmadge Hill
    "157": "MNCA",  # New Canaan
    # Danbury Branch
    "158": "MMR7",  # Merritt 7
    "160": "MWIL",  # Wilton
    "161": "MCAN",  # Cannondale
    "162": "MBVL",  # Branchville
    "163": "MRED",  # Redding
    "164": "MBTH",  # Bethel
    "165": "MDBY",  # Danbury
    # Waterbury Branch
    "167": "MDBS",  # Derby-Shelton
    "168": "MANS",  # Ansonia
    "169": "MSYM",  # Seymour
    "170": "MBCF",  # Beacon Falls
    "171": "MNAU",  # Naugatuck
    "172": "MWTB",  # Waterbury
}

# Reverse mapping for MNR
INTERNAL_TO_MNR_GTFS_STOP_MAP: dict[str, str] = {
    v: k for k, v in MNR_GTFS_STOP_TO_INTERNAL_MAP.items()
}

# MNR route definitions (route_id -> line_code, name, color)
# Colors from official MTA GTFS
MNR_ROUTES: dict[str, tuple[str, str, str]] = {
    "1": ("MNR-HUD", "Hudson Line", "#009B3A"),
    "2": ("MNR-HAR", "Harlem Line", "#0039A6"),
    "3": ("MNR-NH", "New Haven Line", "#EE0034"),
    "4": ("MNR-NC", "New Canaan Branch", "#EE0034"),
    "5": ("MNR-DAN", "Danbury Branch", "#EE0034"),
    "6": ("MNR-WAT", "Waterbury Branch", "#EE0034"),
}

# MNR discovery stations - major hubs to poll for train discovery
MNR_DISCOVERY_STATIONS = [
    "GCT",  # Grand Central Terminal
    "M125",  # Harlem-125th Street
    "MPOK",  # Poughkeepsie (Hudson terminus)
    "MWAS",  # Wassaic (Harlem terminus)
    "MNHV",  # New Haven (New Haven terminus)
]


def get_mnr_route_info(gtfs_route_id: str) -> tuple[str, str, str] | None:
    """Get Metro-North route info from GTFS route ID.

    Args:
        gtfs_route_id: GTFS route_id (e.g., '1' for Hudson Line)

    Returns:
        Tuple of (line_code, route_name, color) or None if not mapped
    """
    return MNR_ROUTES.get(gtfs_route_id)


def map_mnr_gtfs_stop(gtfs_stop_id: str) -> str | None:
    """Map Metro-North GTFS stop_id to our internal station code.

    Args:
        gtfs_stop_id: GTFS stop_id (e.g., '1' for Grand Central)

    Returns:
        Our internal station code (e.g., 'GCT') or None if not mapped
    """
    return MNR_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_stop_id)
