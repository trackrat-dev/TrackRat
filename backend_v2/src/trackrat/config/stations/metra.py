"""Metra (Chicago) station configuration."""

# Metra GTFS-RT feed URLs
# Authentication: append ?api_token=<key> to all feed URLs
METRA_GTFS_RT_FEED_URL = "https://gtfspublic.metrarr.com/gtfs/public/tripupdates"
METRA_POSITIONS_FEED_URL = "https://gtfspublic.metrarr.com/gtfs/public/positions"
METRA_ALERTS_FEED_URL = "https://gtfspublic.metrarr.com/gtfs/public/alerts"


# Metra station names (stop_id -> display name)
METRA_STATION_NAMES: dict[str, str] = {
    "103RD-BEV": "103rd St. - Beverly Hills",
    "103RD-UP": "103rd St. (Rosemoor)",
    "107TH-BEV": "107th St. - Beverly Hills",
    "107TH-UP": "107th St.",
    "111TH-BEV": "111th St. - Morgan Park",
    "111TH-UP": "111th St. (Pullman)",
    "115TH-BEV": "115th St. - Morgan Park",
    "119TH-BEV": "119th St.",
    "123RD-BEV": "123rd St.",
    "143RD-SWS": "Orland Park 143rd",
    "147TH-UP": "147th St.",
    "153RD-SWS": "Orland Park 153rd",
    "179TH-SWS": "Orland Park 179th",
    "18TH-UP": "18th St.",
    "211TH-UP": "211th St.",
    "27TH-UP": "27th St.",
    "35TH": "35th St. - Lou Jones",
    "47TH-UP": "47th St. (Kenwood)",
    "51ST-53RD": "51st/53rd St. (Hyde Park)",
    "55-56-57TH": "55th - 56th - 57th St.",
    "59TH-UP": "59th St. (U. of Chicago)",
    "63RD-UP": "63rd St.",
    "75TH-UP": "75th St. (Grand Crossing)",
    "79TH-SC": "Cheltenham (79th St.)",
    "79TH-UP": "79th St. (Chatham)",
    "83RD-SC": "83rd St.",
    "83RD-UP": "83rd St. (Avalon Park)",
    "87TH-SC": "87th St.",
    "87TH-UP": "87th St. (Woodruff)",
    "91ST-BEV": "91st St. - Beverly Hills",
    "91ST-UP": "91st St.",
    "93RD-SC": "South Chicago (93rd)",
    "95TH-BEV": "95th St. - Beverly Hills",
    "95TH-UP": "95th St.",
    "99TH-BEV": "99th St. - Beverly Hills",
    "ANTIOCH": "Antioch",
    "ARLINGTNHT": "Arlington Heights",
    "ARLINGTNPK": "Arlington Park",
    "ASHBURN": "Ashburn",
    "ASHLAND": "Ashland",
    "AURORA": "Aurora",
    "BARRINGTON": "Barrington",
    "BARTLETT": "Bartlett",
    "BELLWOOD": "Bellwood",
    "BELMONT": "Belmont",
    "BENSENVIL": "Bensenville",
    "BERKELEY": "Berkeley",
    "BERWYN": "Berwyn",
    "BIGTIMBER": "Big Timber",
    "BLUEISLAND": "Blue Island",
    "BNWESTERN": "Western Avenue",
    "BRAESIDE": "Braeside",
    "BRAINERD": "Brainerd",
    "BROOKFIELD": "Brookfield",
    "BRYNMAWR": "Bryn Mawr",
    "BUFFGROVE": "Buffalo Grove",
    "BURROAK": "Burr Oak",
    "CALUMET": "Calumet",
    "CARY": "Cary",
    "CENTRALST": "Central St.",
    "CHICRIDGE": "Chicago Ridge",
    "CICERO": "Cicero",
    "CLARNDNHIL": "Clarendon Hills",
    "CLYBOURN": "Clybourn",
    "COLLEGEAVE": "College Ave",
    "CONGRESSPK": "Congress Park",
    "CRYSTAL": "Crystal Lake",
    "CUMBERLAND": "Cumberland",
    "CUS": "Chicago Union Station",
    "DEERFIELD": "Deerfield",
    "DEEROAD": "Dee Road",
    "DESPLAINES": "Des Plaines",
    "EDGEBROOK": "Edgebrook",
    "EDISONPK": "Edison Park",
    "ELBURN": "Elburn",
    "ELGIN": "Elgin",
    "ELMHURST": "Elmhurst",
    "ELMWOODPK": "Elmwood Park",
    "EVANSTON": "Evanston (Davis St.)",
    "FAIRVIEWDG": "Fairview Ave.",
    "FLOSSMOOR": "Flossmoor",
    "FORESTGLEN": "Forest Glen",
    "FOXLAKE": "Fox Lake",
    "FOXRG": "Fox River Grove",
    "FRANKLIN": "Franklin Park",
    "FRANKLINPK": "Franklin Pk",
    "FTSHERIDAN": "Fort Sheridan",
    "GALEWOOD": "Galewood",
    "GENEVA": "Geneva",
    "GLADSTONEP": "Gladstone Park",
    "GLENCOE": "Glencoe",
    "GLENELLYN": "Glen Ellyn",
    "GLENVIEW": "Glenview",
    "GOLF": "Golf",
    "GRAND-CIC": "Grand/Cicero",
    "GRAYLAND": "Grayland",
    "GRAYSLAKE": "Grayslake",
    "GRESHAM": "Gresham",
    "GRTLAKES": "Great Lakes",
    "HALSTED": "Halsted Street",
    "HANOVERP": "Hanover Park",
    "HANSONPK": "Hanson Park",
    "HARLEM": "Harlem Ave.",
    "HARVARD": "Harvard",
    "HARVEY": "Harvey",
    "HAZELCREST": "Hazel Crest",
    "HEALY": "Healy",
    "HICKORYCRK": "Hickory Creek",
    "HIGHLANDPK": "Highland Park",
    "HIGHLANDS": "Highlands",
    "HIGHWOOD": "Highwood",
    "HINSDALE": "Hinsdale",
    "HOLLYWOOD": "Hollywood",
    "HOMEWOOD": "Homewood",
    "HUBARDWOOD": "Hubbard Woods",
    "INDIANHILL": "Indian Hill",
    "INGLESIDE": "Ingleside",
    "IRVINGPK": "Irving Park",
    "ITASCA": "Itasca",
    "IVANHOE": "Ivanhoe",
    "JEFFERSONP": "Jefferson Park",
    "JOLIET": "Joliet",
    "KEDZIE": "Kedzie",
    "KENILWORTH": "Kenilworth",
    "KENOSHA": "Kenosha",
    "KENSINGTN": "Kensington",
    "LAFOX": "La Fox",
    "LAGRANGE": "LaGrange Road",
    "LAKEBLUFF": "Lake Bluff",
    "LAKECOOKRD": "Lake-Cook",
    "LAKEFRST": "Lake Forest",
    "LAKEVILLA": "Lake Villa",
    "LARAWAY": "Laraway Road",
    "LAVERGNE": "Lavergne",
    "LEMONT": "Lemont",
    "LIBERTYVIL": "Libertyville",
    "LISLE": "Lisle",
    "LKFOREST": "Lake Forest.",
    "LOCKPORT": "Lockport",
    "LOMBARD": "Lombard",
    "LONGLAKE": "Long Lake",
    "LONGWOOD": "95th St.-Longwood",
    "LSS": "LaSalle Street",
    "MAINST": "Main St.",
    "MAINST-DG": "Downers Grove",
    "MANHATTAN": "Manhattan",
    "MANNHEIM": "Mannheim",
    "MARS": "Mars",
    "MATTESON": "Matteson",
    "MAYFAIR": "Mayfair",
    "MAYWOOD": "Maywood",
    "MCCORMICK": "McCormick Place",
    "MCHENRY": "McHenry",
    "MEDINAH": "Medinah",
    "MELROSEPK": "Melrose Park",
    "MIDLOTHIAN": "Midlothian",
    "MILLENNIUM": "Millennium Station",
    "MOKENA": "Mokena",
    "MONTCLARE": "Mont Clare",
    "MORTONGRV": "Morton Grove",
    "MTPROSPECT": "Mt. Prospect",
    "MUNDELEIN": "Mundelein",
    "MUSEUM": "Museum Campus/11th St.",
    "NAPERVILLE": "Naperville",
    "NATIONALS": "National St",
    "NBROOK": "Northbrook",
    "NCHICAGO": "North Chicago",
    "NCSGRAYSLK": "Washington St (Grayslake)",
    "NEWLENOX": "New Lenox",
    "NGLENVIEW": "Glen/N. Glenview",
    "NORWOODP": "Norwood Park",
    "OAKFOREST": "Oak Forest",
    "OAKLAWN": "Oak Lawn Patriot",
    "OAKPARK": "Oak Park",
    "OHARE": "O'Hare Transfer",
    "OLYMPIA": "Olympia Fields",
    "OTC": "Chicago OTC",
    "PALATINE": "Palatine",
    "PALOSHTS": "Palos Heights",
    "PALOSPARK": "Palos Park",
    "PARKRIDGE": "Park Ridge",
    "PETERSON": "Peterson/Ridge",
    "PINGREE": "Pingree Road",
    "PRAIRCROSS": "Prairie Crossing.",
    "PRAIRIEST": "Prairie St.",
    "PRAIRIEVW": "Prairie View",
    "PRAIRIEXNG": "Prairie Crossing",
    "PROSPECTHG": "Prospect Hts",
    "RACINE": "Racine",
    "RAVENSWOOD": "Ravenswood",
    "RAVINIA": "Ravinia",
    "RAVINIAPK": "Ravinia Park",
    "RICHTON": "Richton Park",
    "RIVERDALE": "Riverdale",
    "RIVERGROVE": "River Grove",
    "RIVERSIDE": "Riverside",
    "RIVRFOREST": "River Forest",
    "ROBBINS": "Robbins",
    "ROGERPK": "Rogers Park",
    "ROMEOVILLE": "Romeoville",
    "ROSELLE": "Roselle",
    "ROSEMONT": "Rosemont",
    "ROUNDLAKE": "Round Lake",
    "ROUNDLKBCH": "Round Lake Beach",
    "ROUTE59": "Route 59",
    "SCHAUM": "Schaumburg",
    "SCHILLERPK": "Schiller Park",
    "SOUTHSHORE": "South Shore",
    "STATEST": "State St.",
    "STEWARTRID": "Stewart Ridge",
    "STONEAVE": "Stone Ave.",
    "STONYISLND": "Stony Island",
    "SUMMIT": "Summit",
    "TINLEY80TH": "Tinley-80th",
    "TINLEYPARK": "Tinley Park",
    "UNIVERSITY": "University Park",
    "VANBUREN": "Van Buren St.",
    "VERMONT": "Blue Island-Vermont",
    "VERNON": "Vernon Hills",
    "VILLAPARK": "Villa Park",
    "WASHHGTS": "103rd St.-Washington Hts.",
    "WAUKEGAN": "Waukegan",
    "WCHICAGO": "West Chicago",
    "WESTERNAVE": "Western Ave",
    "WESTMONT": "Westmont",
    "WESTSPRING": "Western Springs",
    "WHEATON": "Wheaton",
    "WHEELING": "Wheeling",
    "WHINSDALE": "West Hinsdale",
    "WILLOWSPRN": "Willow Springs",
    "WILMETTE": "Wilmette",
    "WINDSORPK": "Windsor Park",
    "WINFIELD": "Winfield",
    "WINNETKA": "Winnetka",
    "WINTHROP": "Winthrop Harbor",
    "WOODDALE": "Wood Dale",
    "WOODSTOCK": "Woodstock",
    "WORTH": "Worth",
    "WPULLMAN": "West Pullman",
    "WRIGHTWOOD": "Wrightwood",
    "ZION": "Zion",
}


# Metra uses descriptive stop_ids (e.g., "GENEVA", "AURORA") that are
# unique across all TrackRat providers, so GTFS stop_id == internal code.
METRA_GTFS_STOP_TO_INTERNAL_MAP: dict[str, str] = {
    sid: sid for sid in METRA_STATION_NAMES
}


# Reverse mapping
INTERNAL_TO_METRA_GTFS_STOP_MAP: dict[str, str] = {
    v: k for k, v in METRA_GTFS_STOP_TO_INTERNAL_MAP.items()
}


# Metra route definitions (route_id -> line_code, name, color)
# Colors from official Metra GTFS
METRA_ROUTES: dict[str, tuple[str, str, str]] = {
    "BNSF": ("METRA-BNSF", "Burlington Northern", "#29C233"),
    "HC": ("METRA-HC", "Heritage Corridor", "#550E0C"),
    "MD-N": ("METRA-MD-N", "Milwaukee North", "#CC5500"),
    "MD-W": ("METRA-MD-W", "Milwaukee West", "#F1AD0E"),
    "ME": ("METRA-ME", "Metra Electric", "#EB5C00"),
    "NCS": ("METRA-NCS", "North Central Service", "#9785BC"),
    "RI": ("METRA-RI", "Rock Island", "#E02400"),
    "SWS": ("METRA-SWS", "Southwest Service", "#0042A8"),
    "UP-N": ("METRA-UP-N", "Union Pacific North", "#008000"),
    "UP-NW": ("METRA-UP-NW", "Union Pacific Northwest", "#FFE600"),
    "UP-W": ("METRA-UP-W", "Union Pacific West", "#FE8D81"),
}


# Downtown Chicago terminals — the inbound terminus for each line.
# CUS = Chicago Union Station (6 lines)
# OTC = Ogilvie Transportation Center (3 lines)
# LSS = LaSalle Street Station (Rock Island)
# MILLENNIUM = Millennium Station (Metra Electric)
METRA_DOWNTOWN_TERMINALS = frozenset({"CUS", "OTC", "LSS", "MILLENNIUM"})

# Per-line downtown terminal mapping
METRA_LINE_TERMINAL: dict[str, str] = {
    "BNSF": "CUS",
    "HC": "CUS",
    "MD-N": "CUS",
    "MD-W": "CUS",
    "NCS": "CUS",
    "SWS": "CUS",
    "UP-N": "OTC",
    "UP-NW": "OTC",
    "UP-W": "OTC",
    "RI": "LSS",
    "ME": "MILLENNIUM",
}


# Ordered station sequences per line, extracted from GTFS static stop_times.txt.
# Inbound direction (toward Chicago terminal). Branch lines modeled separately.
METRA_ROUTE_STATIONS: dict[str, tuple[str, ...]] = {
    # Union Station lines
    "BNSF": (
        "AURORA",
        "ROUTE59",
        "NAPERVILLE",
        "LISLE",
        "BELMONT",
        "MAINST-DG",
        "FAIRVIEWDG",
        "WESTMONT",
        "CLARNDNHIL",
        "WHINSDALE",
        "HINSDALE",
        "HIGHLANDS",
        "WESTSPRING",
        "STONEAVE",
        "LAGRANGE",
        "CONGRESSPK",
        "BROOKFIELD",
        "HOLLYWOOD",
        "RIVERSIDE",
        "HARLEM",
        "BERWYN",
        "LAVERGNE",
        "CICERO",
        "BNWESTERN",
        "HALSTED",
        "CUS",
    ),
    "HC": (
        "JOLIET",
        "LOCKPORT",
        "ROMEOVILLE",
        "LEMONT",
        "WILLOWSPRN",
        "SUMMIT",
        "CUS",
    ),
    "MD-N": (
        "FOXLAKE",
        "INGLESIDE",
        "LONGLAKE",
        "ROUNDLAKE",
        "GRAYSLAKE",
        "PRAIRIEXNG",
        "LIBERTYVIL",
        "LAKEFRST",
        "DEERFIELD",
        "LAKECOOKRD",
        "NBROOK",
        "NGLENVIEW",
        "GLENVIEW",
        "GOLF",
        "MORTONGRV",
        "EDGEBROOK",
        "FORESTGLEN",
        "MAYFAIR",
        "GRAYLAND",
        "HEALY",
        "WESTERNAVE",
        "CUS",
    ),
    "MD-W": (
        "BIGTIMBER",
        "ELGIN",
        "NATIONALS",
        "BARTLETT",
        "HANOVERP",
        "SCHAUM",
        "ROSELLE",
        "MEDINAH",
        "ITASCA",
        "WOODDALE",
        "BENSENVIL",
        "MANNHEIM",
        "FRANKLIN",
        "RIVERGROVE",
        "ELMWOODPK",
        "MONTCLARE",
        "MARS",
        "GALEWOOD",
        "HANSONPK",
        "GRAND-CIC",
        "WESTERNAVE",
        "CUS",
    ),
    "NCS": (
        "ANTIOCH",
        "LAKEVILLA",
        "ROUNDLKBCH",
        "NCSGRAYSLK",
        "PRAIRCROSS",
        "MUNDELEIN",
        "VERNON",
        "PRAIRIEVW",
        "BUFFGROVE",
        "WHEELING",
        "PROSPECTHG",
        "OHARE",
        "ROSEMONT",
        "SCHILLERPK",
        "FRANKLINPK",
        "RIVERGROVE",
        "WESTERNAVE",
        "CUS",
    ),
    "SWS": (
        "MANHATTAN",
        "LARAWAY",
        "179TH-SWS",
        "153RD-SWS",
        "143RD-SWS",
        "PALOSPARK",
        "PALOSHTS",
        "WORTH",
        "CHICRIDGE",
        "OAKLAWN",
        "ASHBURN",
        "WRIGHTWOOD",
        "CUS",
    ),
    # Ogilvie Transportation Center lines
    "UP-N": (
        "KENOSHA",
        "WINTHROP",
        "ZION",
        "WAUKEGAN",
        "NCHICAGO",
        "GRTLAKES",
        "LAKEBLUFF",
        "LKFOREST",
        "FTSHERIDAN",
        "HIGHWOOD",
        "HIGHLANDPK",
        "RAVINIA",
        "BRAESIDE",
        "GLENCOE",
        "HUBARDWOOD",
        "WINNETKA",
        "INDIANHILL",
        "KENILWORTH",
        "WILMETTE",
        "CENTRALST",
        "EVANSTON",
        "MAINST",
        "ROGERPK",
        "PETERSON",
        "RAVENSWOOD",
        "CLYBOURN",
        "OTC",
    ),
    "UP-NW": (
        "HARVARD",
        "WOODSTOCK",
        "CRYSTAL",
        "PINGREE",
        "CARY",
        "FOXRG",
        "BARRINGTON",
        "PALATINE",
        "ARLINGTNPK",
        "ARLINGTNHT",
        "MTPROSPECT",
        "CUMBERLAND",
        "DESPLAINES",
        "DEEROAD",
        "PARKRIDGE",
        "EDISONPK",
        "NORWOODP",
        "JEFFERSONP",
        "IRVINGPK",
        "CLYBOURN",
        "OTC",
    ),
    "UP-NW-MCHENRY": (
        "MCHENRY",
        "PINGREE",
        "BARRINGTON",
        "PALATINE",
        "ARLINGTNPK",
        "ARLINGTNHT",
        "MTPROSPECT",
        "CUMBERLAND",
        "DESPLAINES",
        "CLYBOURN",
        "OTC",
    ),
    "UP-W": (
        "ELBURN",
        "LAFOX",
        "GENEVA",
        "WCHICAGO",
        "WINFIELD",
        "WHEATON",
        "COLLEGEAVE",
        "GLENELLYN",
        "LOMBARD",
        "VILLAPARK",
        "ELMHURST",
        "BERKELEY",
        "BELLWOOD",
        "MELROSEPK",
        "MAYWOOD",
        "RIVRFOREST",
        "OAKPARK",
        "KEDZIE",
        "OTC",
    ),
    # LaSalle Street Station
    "RI": (
        "JOLIET",
        "NEWLENOX",
        "MOKENA",
        "HICKORYCRK",
        "TINLEY80TH",
        "TINLEYPARK",
        "OAKFOREST",
        "MIDLOTHIAN",
        "ROBBINS",
        "VERMONT",
        "PRAIRIEST",
        "123RD-BEV",
        "119TH-BEV",
        "115TH-BEV",
        "111TH-BEV",
        "107TH-BEV",
        "103RD-BEV",
        "99TH-BEV",
        "95TH-BEV",
        "91ST-BEV",
        "BRAINERD",
        "GRESHAM",
        "35TH",
        "LSS",
    ),
    # Millennium Station — 3 branches merging at different points
    "ME": (
        "UNIVERSITY",
        "RICHTON",
        "MATTESON",
        "211TH-UP",
        "OLYMPIA",
        "FLOSSMOOR",
        "HOMEWOOD",
        "CALUMET",
        "HAZELCREST",
        "HARVEY",
        "147TH-UP",
        "IVANHOE",
        "RIVERDALE",
        "KENSINGTN",
        "111TH-UP",
        "107TH-UP",
        "103RD-UP",
        "91ST-UP",
        "87TH-UP",
        "83RD-UP",
        "79TH-UP",
        "75TH-UP",
        "63RD-UP",
        "59TH-UP",
        "55-56-57TH",
        "51ST-53RD",
        "47TH-UP",
        "27TH-UP",
        "MCCORMICK",
        "18TH-UP",
        "MUSEUM",
        "VANBUREN",
        "MILLENNIUM",
    ),
    "ME-BI": (
        "BLUEISLAND",
        "BURROAK",
        "ASHLAND",
        "RACINE",
        "WPULLMAN",
        "STEWARTRID",
        "STATEST",
        "KENSINGTN",
        "111TH-UP",
        "107TH-UP",
        "103RD-UP",
        "91ST-UP",
        "87TH-UP",
        "83RD-UP",
        "79TH-UP",
        "75TH-UP",
        "63RD-UP",
        "59TH-UP",
        "55-56-57TH",
        "51ST-53RD",
        "47TH-UP",
        "27TH-UP",
        "MCCORMICK",
        "18TH-UP",
        "MUSEUM",
        "VANBUREN",
        "MILLENNIUM",
    ),
    "ME-SC": (
        "93RD-SC",
        "87TH-SC",
        "83RD-SC",
        "79TH-SC",
        "WINDSORPK",
        "SOUTHSHORE",
        "BRYNMAWR",
        "STONYISLND",
        "63RD-UP",
        "59TH-UP",
        "55-56-57TH",
        "51ST-53RD",
        "47TH-UP",
        "27TH-UP",
        "MCCORMICK",
        "18TH-UP",
        "MUSEUM",
        "VANBUREN",
        "MILLENNIUM",
    ),
}


# Discovery stations — major hubs to validate coverage
METRA_DISCOVERY_STATIONS = [
    "CUS",  # Chicago Union Station (6 lines)
    "OTC",  # Ogilvie Transportation Center (3 lines)
    "MILLENNIUM",  # Millennium Station (Metra Electric)
    "LSS",  # LaSalle Street Station (Rock Island)
]


# Station coordinates for map visualization
METRA_STATION_COORDINATES: dict[str, dict[str, float]] = {
    "103RD-BEV": {"lat": 41.706111, "lon": -87.668889},  # 103rd St. - Beverly Hills
    "103RD-UP": {"lat": 41.706944, "lon": -87.607222},  # 103rd St. (Rosemoor)
    "107TH-BEV": {"lat": 41.698889, "lon": -87.670000},  # 107th St. - Beverly Hills
    "107TH-UP": {"lat": 41.699722, "lon": -87.608889},  # 107th St.
    "111TH-BEV": {"lat": 41.692778, "lon": -87.670556},  # 111th St. - Morgan Park
    "111TH-UP": {"lat": 41.692778, "lon": -87.610556},  # 111th St. (Pullman)
    "115TH-BEV": {"lat": 41.685000, "lon": -87.671667},  # 115th St. - Morgan Park
    "119TH-BEV": {"lat": 41.676389, "lon": -87.672500},  # 119th St.
    "123RD-BEV": {"lat": 41.670000, "lon": -87.673611},  # 123rd St.
    "143RD-SWS": {"lat": 41.630556, "lon": -87.859167},  # Orland Park 143rd
    "147TH-UP": {"lat": 41.622778, "lon": -87.636111},  # 147th St.
    "153RD-SWS": {"lat": 41.609444, "lon": -87.873333},  # Orland Park 153rd
    "179TH-SWS": {"lat": 41.563889, "lon": -87.902500},  # Orland Park 179th
    "18TH-UP": {"lat": 41.858333, "lon": -87.618056},  # 18th St.
    "211TH-UP": {"lat": 41.506111, "lon": -87.698333},  # 211th St.
    "27TH-UP": {"lat": 41.844167, "lon": -87.613333},  # 27th St.
    "35TH": {"lat": 41.831389, "lon": -87.629167},  # 35th St. - Lou Jones
    "47TH-UP": {"lat": 41.809722, "lon": -87.591389},  # 47th St. (Kenwood)
    "51ST-53RD": {"lat": 41.800000, "lon": -87.586944},  # 51st/53rd St. (Hyde Park)
    "55-56-57TH": {"lat": 41.793333, "lon": -87.587500},  # 55th - 56th - 57th St.
    "59TH-UP": {"lat": 41.788056, "lon": -87.588611},  # 59th St. (U. of Chicago)
    "63RD-UP": {"lat": 41.780278, "lon": -87.590556},  # 63rd St.
    "75TH-UP": {"lat": 41.758889, "lon": -87.595278},  # 75th St. (Grand Crossing)
    "79TH-SC": {"lat": 41.752222, "lon": -87.552500},  # Cheltenham (79th St.)
    "79TH-UP": {"lat": 41.750833, "lon": -87.597222},  # 79th St. (Chatham)
    "83RD-SC": {"lat": 41.745000, "lon": -87.551667},  # 83rd St.
    "83RD-UP": {"lat": 41.744167, "lon": -87.598611},  # 83rd St. (Avalon Park)
    "87TH-SC": {"lat": 41.737778, "lon": -87.548333},  # 87th St.
    "87TH-UP": {"lat": 41.736944, "lon": -87.600278},  # 87th St. (Woodruff)
    "91ST-BEV": {"lat": 41.728056, "lon": -87.667222},  # 91st St. - Beverly Hills
    "91ST-UP": {"lat": 41.729444, "lon": -87.601944},  # 91st St.
    "93RD-SC": {"lat": 41.726667, "lon": -87.547778},  # South Chicago (93rd)
    "95TH-BEV": {"lat": 41.721389, "lon": -87.667222},  # 95th St. - Beverly Hills
    "95TH-UP": {"lat": 41.721944, "lon": -87.603889},  # 95th St.
    "99TH-BEV": {"lat": 41.713611, "lon": -87.667500},  # 99th St. - Beverly Hills
    "ANTIOCH": {"lat": 42.481111, "lon": -88.092500},  # Antioch
    "ARLINGTNHT": {"lat": 42.084167, "lon": -87.983611},  # Arlington Heights
    "ARLINGTNPK": {"lat": 42.095278, "lon": -88.009167},  # Arlington Park
    "ASHBURN": {"lat": 41.741667, "lon": -87.712500},  # Ashburn
    "ASHLAND": {"lat": 41.669444, "lon": -87.660556},  # Ashland
    "AURORA": {"lat": 41.760833, "lon": -88.308333},  # Aurora
    "BARRINGTON": {"lat": 42.152778, "lon": -88.131944},  # Barrington
    "BARTLETT": {"lat": 41.992222, "lon": -88.183889},  # Bartlett
    "BELLWOOD": {"lat": 41.891389, "lon": -87.882500},  # Bellwood
    "BELMONT": {"lat": 41.795278, "lon": -88.038056},  # Belmont
    "BENSENVIL": {"lat": 41.956944, "lon": -87.941944},  # Bensenville
    "BERKELEY": {"lat": 41.896111, "lon": -87.915278},  # Berkeley
    "BERWYN": {"lat": 41.833056, "lon": -87.793611},  # Berwyn
    "BIGTIMBER": {"lat": 42.058611, "lon": -88.327778},  # Big Timber
    "BLUEISLAND": {"lat": 41.656111, "lon": -87.675833},  # Blue Island
    "BNWESTERN": {"lat": 41.857778, "lon": -87.685278},  # Western Avenue
    "BRAESIDE": {"lat": 42.152778, "lon": -87.772500},  # Braeside
    "BRAINERD": {"lat": 41.732222, "lon": -87.658889},  # Brainerd
    "BROOKFIELD": {"lat": 41.821944, "lon": -87.843056},  # Brookfield
    "BRYNMAWR": {"lat": 41.766111, "lon": -87.576667},  # Bryn Mawr
    "BUFFGROVE": {"lat": 42.168611, "lon": -87.941389},  # Buffalo Grove
    "BURROAK": {"lat": 41.662222, "lon": -87.668889},  # Burr Oak
    "CALUMET": {"lat": 41.573611, "lon": -87.662500},  # Calumet
    "CARY": {"lat": 42.208889, "lon": -88.241389},  # Cary
    "CENTRALST": {"lat": 42.064167, "lon": -87.698056},  # Central St.
    "CHICRIDGE": {"lat": 41.703333, "lon": -87.780278},  # Chicago Ridge
    "CICERO": {"lat": 41.844167, "lon": -87.745556},  # Cicero
    "CLARNDNHIL": {"lat": 41.796944, "lon": -87.953611},  # Clarendon Hills
    "CLYBOURN": {"lat": 41.916944, "lon": -87.668056},  # Clybourn
    "COLLEGEAVE": {"lat": 41.868333, "lon": -88.090278},  # College Ave
    "CONGRESSPK": {"lat": 41.818889, "lon": -87.857500},  # Congress Park
    "CRYSTAL": {"lat": 42.244167, "lon": -88.317222},  # Crystal Lake
    "CUMBERLAND": {"lat": 42.052500, "lon": -87.912222},  # Cumberland
    "CUS": {"lat": 41.878889, "lon": -87.638889},  # Chicago Union Station
    "DEERFIELD": {"lat": 42.168056, "lon": -87.850000},  # Deerfield
    "DEEROAD": {"lat": 42.024167, "lon": -87.856111},  # Dee Road
    "DESPLAINES": {"lat": 42.040833, "lon": -87.886667},  # Des Plaines
    "EDGEBROOK": {"lat": 41.997778, "lon": -87.765556},  # Edgebrook
    "EDISONPK": {"lat": 42.002222, "lon": -87.817500},  # Edison Park
    "ELBURN": {"lat": 41.890556, "lon": -88.463889},  # Elburn
    "ELGIN": {"lat": 42.036111, "lon": -88.286111},  # Elgin
    "ELMHURST": {"lat": 41.899722, "lon": -87.940833},  # Elmhurst
    "ELMWOODPK": {"lat": 41.924722, "lon": -87.814722},  # Elmwood Park
    "EVANSTON": {"lat": 42.048056, "lon": -87.684722},  # Evanston (Davis St.)
    "FAIRVIEWDG": {"lat": 41.795278, "lon": -87.993611},  # Fairview Ave.
    "FLOSSMOOR": {"lat": 41.543056, "lon": -87.678611},  # Flossmoor
    "FORESTGLEN": {"lat": 41.978056, "lon": -87.755556},  # Forest Glen
    "FOXLAKE": {"lat": 42.398333, "lon": -88.182222},  # Fox Lake
    "FOXRG": {"lat": 42.197778, "lon": -88.219444},  # Fox River Grove
    "FRANKLIN": {"lat": 41.936667, "lon": -87.866389},  # Franklin Park
    "FRANKLINPK": {"lat": 41.937778, "lon": -87.860000},  # Franklin Pk
    "FTSHERIDAN": {"lat": 42.217500, "lon": -87.820833},  # Fort Sheridan
    "GALEWOOD": {"lat": 41.916389, "lon": -87.785833},  # Galewood
    "GENEVA": {"lat": 41.881667, "lon": -88.310000},  # Geneva
    "GLADSTONEP": {"lat": 41.979722, "lon": -87.778056},  # Gladstone Park
    "GLENCOE": {"lat": 42.135556, "lon": -87.758056},  # Glencoe
    "GLENELLYN": {"lat": 41.876667, "lon": -88.064722},  # Glen Ellyn
    "GLENVIEW": {"lat": 42.075000, "lon": -87.805556},  # Glenview
    "GOLF": {"lat": 42.058333, "lon": -87.796944},  # Golf
    "GRAND-CIC": {"lat": 41.914444, "lon": -87.746111},  # Grand/Cicero
    "GRAYLAND": {"lat": 41.948889, "lon": -87.740278},  # Grayland
    "GRAYSLAKE": {"lat": 42.333611, "lon": -88.043333},  # Grayslake
    "GRESHAM": {"lat": 41.736389, "lon": -87.644722},  # Gresham
    "GRTLAKES": {"lat": 42.306944, "lon": -87.846389},  # Great Lakes
    "HALSTED": {"lat": 41.860278, "lon": -87.647222},  # Halsted Street
    "HANOVERP": {"lat": 41.988056, "lon": -88.149167},  # Hanover Park
    "HANSONPK": {"lat": 41.916667, "lon": -87.766944},  # Hanson Park
    "HARLEM": {"lat": 41.831389, "lon": -87.801944},  # Harlem Ave.
    "HARVARD": {"lat": 42.419722, "lon": -88.617500},  # Harvard
    "HARVEY": {"lat": 41.608333, "lon": -87.643889},  # Harvey
    "HAZELCREST": {"lat": 41.580833, "lon": -87.658611},  # Hazel Crest
    "HEALY": {"lat": 41.924722, "lon": -87.727778},  # Healy
    "HICKORYCRK": {"lat": 41.548611, "lon": -87.845556},  # Hickory Creek
    "HIGHLANDPK": {"lat": 42.183333, "lon": -87.797500},  # Highland Park
    "HIGHLANDS": {"lat": 41.805000, "lon": -87.918333},  # Highlands
    "HIGHWOOD": {"lat": 42.203333, "lon": -87.810556},  # Highwood
    "HINSDALE": {"lat": 41.802778, "lon": -87.928333},  # Hinsdale
    "HOLLYWOOD": {"lat": 41.824444, "lon": -87.833889},  # Hollywood
    "HOMEWOOD": {"lat": 41.562222, "lon": -87.668611},  # Homewood
    "HUBARDWOOD": {"lat": 42.118056, "lon": -87.743611},  # Hubbard Woods
    "INDIANHILL": {"lat": 42.094444, "lon": -87.723889},  # Indian Hill
    "INGLESIDE": {"lat": 42.383889, "lon": -88.153611},  # Ingleside
    "IRVINGPK": {"lat": 41.952500, "lon": -87.729722},  # Irving Park
    "ITASCA": {"lat": 41.971389, "lon": -88.014167},  # Itasca
    "IVANHOE": {"lat": 41.633333, "lon": -87.630278},  # Ivanhoe
    "JEFFERSONP": {"lat": 41.971389, "lon": -87.763333},  # Jefferson Park
    "JOLIET": {"lat": 41.524444, "lon": -88.079722},  # Joliet
    "KEDZIE": {"lat": 41.888333, "lon": -87.706944},  # Kedzie
    "KENILWORTH": {"lat": 42.086389, "lon": -87.716667},  # Kenilworth
    "KENOSHA": {"lat": 42.585833, "lon": -87.825833},  # Kenosha
    "KENSINGTN": {"lat": 41.685833, "lon": -87.612222},  # Kensington
    "LAFOX": {"lat": 41.886667, "lon": -88.412222},  # La Fox
    "LAGRANGE": {"lat": 41.815833, "lon": -87.871111},  # LaGrange Road
    "LAKEBLUFF": {"lat": 42.279722, "lon": -87.846667},  # Lake Bluff
    "LAKECOOKRD": {"lat": 42.151667, "lon": -87.841389},  # Lake-Cook
    "LAKEFRST": {"lat": 42.223611, "lon": -87.874722},  # Lake Forest
    "LAKEVILLA": {"lat": 42.417500, "lon": -88.079444},  # Lake Villa
    "LARAWAY": {"lat": 41.484722, "lon": -87.959722},  # Laraway Road
    "LAVERGNE": {"lat": 41.835556, "lon": -87.783333},  # Lavergne
    "LEMONT": {"lat": 41.673611, "lon": -88.002500},  # Lemont
    "LIBERTYVIL": {"lat": 42.291111, "lon": -87.956389},  # Libertyville
    "LISLE": {"lat": 41.797778, "lon": -88.071944},  # Lisle
    "LKFOREST": {"lat": 42.252500, "lon": -87.839722},  # Lake Forest.
    "LOCKPORT": {"lat": 41.585000, "lon": -88.060278},  # Lockport
    "LOMBARD": {"lat": 41.886667, "lon": -88.018611},  # Lombard
    "LONGLAKE": {"lat": 42.368056, "lon": -88.128056},  # Long Lake
    "LONGWOOD": {"lat": 41.721111, "lon": -87.650278},  # 95th St.-Longwood
    "LSS": {"lat": 41.876389, "lon": -87.632222},  # LaSalle Street
    "MAINST": {"lat": 42.033333, "lon": -87.680000},  # Main St.
    "MAINST-DG": {"lat": 41.795278, "lon": -88.009722},  # Downers Grove
    "MANHATTAN": {"lat": 41.418333, "lon": -87.989167},  # Manhattan
    "MANNHEIM": {"lat": 41.941667, "lon": -87.883333},  # Mannheim
    "MARS": {"lat": 41.919167, "lon": -87.794444},  # Mars
    "MATTESON": {"lat": 41.498611, "lon": -87.702222},  # Matteson
    "MAYFAIR": {"lat": 41.959722, "lon": -87.745833},  # Mayfair
    "MAYWOOD": {"lat": 41.888333, "lon": -87.838611},  # Maywood
    "MCCORMICK": {"lat": 41.851389, "lon": -87.616389},  # McCormick Place
    "MCHENRY": {"lat": 42.343333, "lon": -88.276111},  # McHenry
    "MEDINAH": {"lat": 41.978056, "lon": -88.050833},  # Medinah
    "MELROSEPK": {"lat": 41.890278, "lon": -87.855556},  # Melrose Park
    "MIDLOTHIAN": {"lat": 41.626389, "lon": -87.711667},  # Midlothian
    "MILLENNIUM": {"lat": 41.884167, "lon": -87.623056},  # Millennium Station
    "MOKENA": {"lat": 41.530833, "lon": -87.886667},  # Mokena
    "MONTCLARE": {"lat": 41.921667, "lon": -87.801667},  # Mont Clare
    "MORTONGRV": {"lat": 42.035000, "lon": -87.785278},  # Morton Grove
    "MTPROSPECT": {"lat": 42.063056, "lon": -87.936111},  # Mt. Prospect
    "MUNDELEIN": {"lat": 42.266944, "lon": -87.998056},  # Mundelein
    "MUSEUM": {"lat": 41.868611, "lon": -87.621389},  # Museum Campus/11th St.
    "NAPERVILLE": {"lat": 41.779722, "lon": -88.145556},  # Naperville
    "NATIONALS": {"lat": 42.026389, "lon": -88.278889},  # National St
    "NBROOK": {"lat": 42.126944, "lon": -87.827778},  # Northbrook
    "NCHICAGO": {"lat": 42.328611, "lon": -87.836944},  # North Chicago
    "NCSGRAYSLK": {"lat": 42.359167, "lon": -88.050556},  # Washington St (Grayslake)
    "NEWLENOX": {"lat": 41.514444, "lon": -87.965278},  # New Lenox
    "NGLENVIEW": {"lat": 42.097500, "lon": -87.815833},  # Glen/N. Glenview
    "NORWOODP": {"lat": 41.991667, "lon": -87.798889},  # Norwood Park
    "OAKFOREST": {"lat": 41.604444, "lon": -87.738333},  # Oak Forest
    "OAKLAWN": {"lat": 41.719444, "lon": -87.748611},  # Oak Lawn Patriot
    "OAKPARK": {"lat": 41.886944, "lon": -87.801111},  # Oak Park
    "OHARE": {"lat": 41.995000, "lon": -87.880556},  # O'Hare Transfer
    "OLYMPIA": {"lat": 41.521389, "lon": -87.690000},  # Olympia Fields
    "OTC": {"lat": 41.882222, "lon": -87.640556},  # Chicago OTC
    "PALATINE": {"lat": 42.113056, "lon": -88.048333},  # Palatine
    "PALOSHTS": {"lat": 41.681944, "lon": -87.806944},  # Palos Heights
    "PALOSPARK": {"lat": 41.668889, "lon": -87.820278},  # Palos Park
    "PARKRIDGE": {"lat": 42.010278, "lon": -87.831667},  # Park Ridge
    "PETERSON": {"lat": 41.991111, "lon": -87.675000},  # Peterson/Ridge
    "PINGREE": {"lat": 42.234167, "lon": -88.298056},  # Pingree Road
    "PRAIRCROSS": {"lat": 42.318056, "lon": -88.017222},  # Prairie Crossing.
    "PRAIRIEST": {"lat": 41.662500, "lon": -87.675000},  # Prairie St.
    "PRAIRIEVW": {"lat": 42.198056, "lon": -87.955833},  # Prairie View
    "PRAIRIEXNG": {"lat": 42.320833, "lon": -88.015278},  # Prairie Crossing
    "PROSPECTHG": {"lat": 42.092222, "lon": -87.908056},  # Prospect Hts
    "RACINE": {"lat": 41.674167, "lon": -87.651944},  # Racine
    "RAVENSWOOD": {"lat": 41.968333, "lon": -87.674444},  # Ravenswood
    "RAVINIA": {"lat": 42.165000, "lon": -87.782778},  # Ravinia
    "RAVINIAPK": {"lat": 42.158056, "lon": -87.776944},  # Ravinia Park
    "RICHTON": {"lat": 41.485556, "lon": -87.709444},  # Richton Park
    "RIVERDALE": {"lat": 41.646667, "lon": -87.623333},  # Riverdale
    "RIVERGROVE": {"lat": 41.931111, "lon": -87.836111},  # River Grove
    "RIVERSIDE": {"lat": 41.827222, "lon": -87.820000},  # Riverside
    "RIVRFOREST": {"lat": 41.886944, "lon": -87.825000},  # River Forest
    "ROBBINS": {"lat": 41.640833, "lon": -87.694444},  # Robbins
    "ROGERPK": {"lat": 42.009444, "lon": -87.675556},  # Rogers Park
    "ROMEOVILLE": {"lat": 41.637222, "lon": -88.049444},  # Romeoville
    "ROSELLE": {"lat": 41.981389, "lon": -88.067222},  # Roselle
    "ROSEMONT": {"lat": 41.976111, "lon": -87.873889},  # Rosemont
    "ROUNDLAKE": {"lat": 42.354444, "lon": -88.094167},  # Round Lake
    "ROUNDLKBCH": {"lat": 42.385000, "lon": -88.065556},  # Round Lake Beach
    "ROUTE59": {"lat": 41.777778, "lon": -88.208611},  # Route 59
    "SCHAUM": {"lat": 41.989167, "lon": -88.118056},  # Schaumburg
    "SCHILLERPK": {"lat": 41.962778, "lon": -87.870556},  # Schiller Park
    "SOUTHSHORE": {"lat": 41.765278, "lon": -87.565833},  # South Shore
    "STATEST": {"lat": 41.674444, "lon": -87.621944},  # State St.
    "STEWARTRID": {"lat": 41.674444, "lon": -87.631667},  # Stewart Ridge
    "STONEAVE": {"lat": 41.814167, "lon": -87.878333},  # Stone Ave.
    "STONYISLND": {"lat": 41.766111, "lon": -87.586944},  # Stony Island
    "SUMMIT": {"lat": 41.795000, "lon": -87.809722},  # Summit
    "TINLEY80TH": {"lat": 41.564444, "lon": -87.809444},  # Tinley-80th
    "TINLEYPARK": {"lat": 41.575833, "lon": -87.782778},  # Tinley Park
    "UNIVERSITY": {"lat": 41.459444, "lon": -87.723333},  # University Park
    "VANBUREN": {"lat": 41.876944, "lon": -87.623056},  # Van Buren St.
    "VERMONT": {"lat": 41.654722, "lon": -87.677778},  # Blue Island-Vermont
    "VERNON": {"lat": 42.215556, "lon": -87.964444},  # Vernon Hills
    "VILLAPARK": {"lat": 41.896389, "lon": -87.977500},  # Villa Park
    "WASHHGTS": {"lat": 41.705556, "lon": -87.655833},  # 103rd St.-Washington Hts.
    "WAUKEGAN": {"lat": 42.360556, "lon": -87.828333},  # Waukegan
    "WCHICAGO": {"lat": 41.881111, "lon": -88.198889},  # West Chicago
    "WESTERNAVE": {"lat": 41.889167, "lon": -87.688056},  # Western Ave
    "WESTMONT": {"lat": 41.795556, "lon": -87.976389},  # Westmont
    "WESTSPRING": {"lat": 41.808889, "lon": -87.901111},  # Western Springs
    "WHEATON": {"lat": 41.864444, "lon": -88.111944},  # Wheaton
    "WHEELING": {"lat": 42.136389, "lon": -87.927222},  # Wheeling
    "WHINSDALE": {"lat": 41.798889, "lon": -87.945278},  # West Hinsdale
    "WILLOWSPRN": {"lat": 41.733333, "lon": -87.878333},  # Willow Springs
    "WILMETTE": {"lat": 42.077222, "lon": -87.709167},  # Wilmette
    "WINDSORPK": {"lat": 41.758611, "lon": -87.559444},  # Windsor Park
    "WINFIELD": {"lat": 41.870000, "lon": -88.156944},  # Winfield
    "WINNETKA": {"lat": 42.105278, "lon": -87.732778},  # Winnetka
    "WINTHROP": {"lat": 42.482778, "lon": -87.816111},  # Winthrop Harbor
    "WOODDALE": {"lat": 41.962500, "lon": -87.975278},  # Wood Dale
    "WOODSTOCK": {"lat": 42.316944, "lon": -88.447500},  # Woodstock
    "WORTH": {"lat": 41.691389, "lon": -87.795833},  # Worth
    "WPULLMAN": {"lat": 41.674167, "lon": -87.642222},  # West Pullman
    "WRIGHTWOOD": {"lat": 41.748889, "lon": -87.703611},  # Wrightwood
    "ZION": {"lat": 42.449167, "lon": -87.818056},  # Zion
}


def get_metra_route_info(gtfs_route_id: str) -> tuple[str, str, str] | None:
    """Get Metra route info from GTFS route ID.

    Args:
        gtfs_route_id: GTFS route_id (e.g., "BNSF", "UP-N")

    Returns:
        Tuple of (line_code, route_name, color) or None if not mapped
    """
    return METRA_ROUTES.get(gtfs_route_id)


def map_metra_gtfs_stop(gtfs_stop_id: str) -> str | None:
    """Map Metra GTFS stop_id to our internal station code.

    Args:
        gtfs_stop_id: GTFS stop_id (e.g., "GENEVA", "CUS")

    Returns:
        Our internal station code or None if not mapped
    """
    return METRA_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_stop_id)
