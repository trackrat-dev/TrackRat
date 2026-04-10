"""NJ Transit station configuration."""

# NJ Transit station names (includes shared stations with Amtrak like NY, NP, TR)
NJT_STATION_NAMES: dict[str, str] = {
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
    "MD": "Middletown NY",
    "MH": "Murray Hill",
    "MI": "Middletown NJ",
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
    "WA": "Walnut Street",
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
}


# =============================================================================
# NJ Transit GTFS Configuration
# =============================================================================

# NJT GTFS stop_id to internal station code mapping
# Complete explicit mapping for all NJT rail stops.
# Prevents fuzzy name matching issues where NJT station names
# (e.g., "DOVER", "SUMMIT", "MADISON") collide with Amtrak/PATCO codes.
NJT_GTFS_STOP_TO_INTERNAL_MAP: dict[str, str] = {
    "1": "PH",  # 30TH ST. PHL.
    "2": "AB",  # ABSECON
    "3": "AZ",  # ALLENDALE
    "4": "AH",  # ALLENHURST
    "5": "AS",  # ANDERSON STREET
    "6": "AN",  # ANNANDALE
    "8": "AP",  # ASBURY PARK
    "9": "AO",  # ATCO
    "10": "AC",  # ATLANTIC CITY
    "11": "AV",  # AVENEL
    "12": "BI",  # BASKING RIDGE
    "13": "BH",  # BAY HEAD
    "14": "MC",  # BAY STREET (Montclair)
    "15": "BS",  # BELMAR
    "17": "BY",  # BERKELEY HEIGHTS
    "18": "BV",  # BERNARDSVILLE
    "19": "BM",  # BLOOMFIELD
    "20": "BN",  # BOONTON
    "21": "BK",  # BOUND BROOK
    "22": "BB",  # BRADLEY BEACH
    "23": "BU",  # BRICK CHURCH
    "24": "BW",  # BRIDGEWATER
    "25": "BF",  # BROADWAY (Fair Lawn, NJT — not PATCO BWY)
    "26": "CB",  # CAMPBELL HALL
    "27": "CM",  # CHATHAM
    "28": "CY",  # CHERRY HILL
    "29": "IF",  # CLIFTON
    "30": "CN",  # CONVENT
    "31": "RL",  # ROSELLE PARK
    "32": "XC",  # CRANFORD
    "33": "DL",  # DELAWANNA
    "34": "DV",  # DENVILLE
    "35": "DO",  # DOVER (NJT — not Amtrak DOV)
    "36": "DN",  # DUNELLEN
    "37": "EO",  # EAST ORANGE
    "38": "ED",  # EDISON STATION
    "39": "EH",  # EGG HARBOR
    "40": "EL",  # ELBERON
    "41": "EZ",  # ELIZABETH
    "42": "EN",  # EMERSON
    "43": "EX",  # ESSEX STREET
    "44": "FW",  # FANWOOD
    "45": "FH",  # FAR HILLS
    "46": "GD",  # GARFIELD
    "47": "GW",  # GARWOOD
    "48": "GI",  # GILLETTE
    "49": "GL",  # GLADSTONE
    "50": "GG",  # GLEN RIDGE
    "51": "GK",  # GLEN ROCK BORO HALL
    "52": "RS",  # GLEN ROCK MAIN LINE
    "54": "HQ",  # HACKETTSTOWN
    "55": "HN",  # HAMMONTON
    "57": "RM",  # HARRIMAN
    "58": "HW",  # HAWTHORNE
    "59": "HZ",  # HAZLET
    "60": "HG",  # HIGH BRIDGE
    "61": "HI",  # HIGHLAND AVENUE
    "62": "HD",  # HILLSDALE
    "63": "HB",  # HOBOKEN
    "64": "UF",  # HOHOKUS
    "67": "HP",  # LAKE HOPATCONG
    "68": "ON",  # LEBANON
    "69": "LP",  # LINCOLN PARK
    "70": "LI",  # LINDEN
    "71": "LW",  # LINDENWOLD (NJT — not PATCO LND)
    "72": "FA",  # LITTLE FALLS
    "73": "LS",  # LITTLE SILVER
    "74": "LB",  # LONG BRANCH
    "75": "LN",  # LYNDHURST
    "76": "LY",  # LYONS
    "77": "MA",  # MADISON (NJT — not Amtrak MDS)
    "78": "MZ",  # MAHWAH
    "79": "SQ",  # MANASQUAN
    "81": "MW",  # MAPLEWOOD
    "83": "MP",  # METROPARK
    "84": "MU",  # METUCHEN
    "85": "MI",  # MIDDLETOWN NJ
    "86": "MD",  # MIDDLETOWN NY (Port Jervis Line)
    "87": "MB",  # MILLBURN
    "88": "GO",  # MILLINGTON
    "89": "HS",  # MONTCLAIR HEIGHTS
    "90": "ZM",  # MONTVALE
    "91": "MX",  # MORRIS PLAINS
    "92": "MR",  # MORRISTOWN
    "93": "OL",  # MOUNT OLIVE
    "94": "TB",  # MOUNT TABOR
    "95": "MS",  # MOUNTAIN AVENUE
    "96": "ML",  # MOUNTAIN LAKES
    "97": "MT",  # MOUNTAIN STATION
    "98": "MV",  # MOUNTAIN VIEW
    "99": "MH",  # MURRAY HILL
    "100": "NN",  # NANUET
    "101": "NT",  # NETCONG
    "102": "NE",  # NETHERWOOD
    "103": "NB",  # NEW BRUNSWICK
    "104": "NV",  # NEW PROVIDENCE
    "105": "NY",  # NEW YORK PENN STATION
    "106": "ND",  # NEWARK BROAD ST
    "107": "NP",  # NEWARK PENN STATION
    "108": "OR",  # NORTH BRANCH
    "109": "NZ",  # NORTH ELIZABETH
    "110": "NH",  # NEW BRIDGE LANDING
    "111": "OD",  # ORADELL
    "112": "OG",  # ORANGE
    "113": "OS",  # OTISVILLE
    "114": "PV",  # PARK RIDGE
    "115": "PS",  # PASSAIC
    "116": "RN",  # PATERSON
    "117": "PC",  # PEAPACK
    "118": "PQ",  # PEARL RIVER
    "119": "PE",  # PERTH AMBOY
    "120": "PF",  # PLAINFIELD
    "121": "PL",  # PLAUDERVILLE
    "122": "PP",  # POINT PLEASANT
    "123": "PO",  # PORT JERVIS
    "124": "PR",  # PRINCETON (NJT — not Amtrak PCT)
    "125": "PJ",  # PRINCETON JCT.
    "126": "FZ",  # RADBURN
    "127": "RH",  # RAHWAY
    "128": "17",  # RAMSEY
    "129": "RA",  # RARITAN
    "130": "RB",  # RED BANK
    "131": "RW",  # RIDGEWOOD
    "132": "RG",  # RIVER EDGE
    "134": "RF",  # RUTHERFORD
    "135": "CW",  # SALISBURY MILLS-CORNWALL
    "136": "RT",  # SHORT HILLS
    "137": "XG",  # SLOATSBURG
    "138": "SM",  # SOMERVILLE
    "139": "CH",  # SOUTH AMBOY
    "140": "SO",  # SOUTH ORANGE
    "141": "LA",  # SPRING LAKE
    "142": "SV",  # SPRING VALLEY
    "143": "SG",  # STIRLING
    "144": "SF",  # SUFFERN
    "145": "ST",  # SUMMIT (NJT — not Amtrak SMT)
    "146": "TE",  # TETERBORO
    "147": "TO",  # TOWACO
    "148": "TR",  # TRENTON TRANSIT CENTER
    "149": "TC",  # TUXEDO
    "150": "UM",  # UPPER MONTCLAIR
    "151": "WK",  # WALDWICK
    "152": "WA",  # WALNUT STREET
    "153": "WG",  # WATCHUNG AVENUE
    "154": "WT",  # WATSESSING AVENUE
    "155": "WF",  # WESTFIELD
    "156": "WW",  # WESTWOOD
    "157": "WH",  # WHITE HOUSE
    "158": "WB",  # WOODBRIDGE (NJT — not Amtrak WDB)
    "159": "WL",  # WOODCLIFF LAKE
    "160": "WR",  # WOOD-RIDGE
    # Alternate/extended stop_ids for the same stations
    "32905": "HL",  # HAMILTON
    "32906": "JA",  # JERSEY AVE.
    "37169": "AM",  # ABERDEEN-MATAWAN
    "37953": "NA",  # NEWARK AIRPORT RAILROAD STATION
    "38081": "UV",  # MSU (Montclair State University)
    "38105": "US",  # UNION
    "38174": "TS",  # FRANK R LAUTENBERG SECAUCUS LOWER LEVEL
    "38187": "SE",  # FRANK R LAUTENBERG SECAUCUS UPPER LEVEL
    "38417": "17",  # RAMSEY ROUTE 17 STATION
    "39472": "HV",  # MOUNT ARLINGTON
    "39635": "23",  # WAYNE/ROUTE 23 TRANSIT CENTER [RR]
    "43298": "PN",  # PENNSAUKEN TRANSIT CENTER
    "43599": "WM",  # WESMONT
}


# =============================================================================
# PATCO Speedline Configuration
# =============================================================================

# PATCO GTFS stop_id to internal station code mapping
# GTFS uses numeric stop_id (1-14), matching stop_code

# Discovery stations for train polling - centralized configuration.
#
# Every NJT line must have at least one *intermediate* station here (not just
# a terminal), otherwise trains originating from non-discovery stations on
# that line remain SCHEDULED forever and are hidden by the
# SCHEDULED_VISIBILITY_THRESHOLD_MINUTES filter in departure.py before users
# ever see them. Terminal stations catch only trains that *depart* from them
# (outbound), because arriving trains have no SCHED_DEP_DATE and are skipped
# by discovery.py.
DISCOVERY_STATIONS = [
    "NY",  # New York Penn Station
    "NP",  # Newark Penn Station
    "TR",  # Trenton
    "LB",  # Long Branch
    "PL",  # Plauderville - Bergen County Line midline
    "DN",  # Dunellen - Raritan Valley Line midline
    "MP",  # Metropark
    "HB",  # Hoboken
    "HG",  # High Bridge
    "GL",  # Gladstone
    "ND",  # Newark Broad Street
    "BU",  # Brick Church - Morris & Essex junction near Newark
    "HQ",  # Hackettstown
    "DV",  # Denville - Morris & Essex / Montclair-Boonton western coverage
    "JA",  # Jersey Avenue
    "RA",  # Raritan
    "ST",  # Summit - major Morris & Essex terminal for inbound trains
    "SV",  # Spring Valley - Pascack Valley Line terminus
    "RW",  # Ridgewood - Main / Bergen County / Port Jervis shared trunk
    "WW",  # Westwood - Pascack Valley Line midline
    "HN",  # Hammonton - Atlantic City Line midline
]
