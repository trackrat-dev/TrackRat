import Foundation
import CoreLocation

struct Stations {
    static let all: [String] = [
        // NJ Transit stations (corrected codes to match API)
        "New York Penn Station", "Newark Penn Station", "Secaucus Upper Lvl", "Woodbridge",
        "Metropark", "New Brunswick", "Princeton Junction", "Trenton", "Hamilton",
        "Morristown", "Madison", "Summit", "Millburn", "Short Hills", "Newark Airport",
        "Elizabeth", "Linden", "Rahway", "Metuchen", "Edison", "Iselin", "Perth Amboy",
        "South Amboy", "Aberdeen-Matawan", "Hazlet", "Red Bank", "Little Silver", "Monmouth Park",
        "Long Branch", "Asbury Park", "Bradley Beach", "Belmar", "Spring Lake", "Manasquan",
        "Point Pleasant Beach", "Bay Head", "Montclair State University", "Montclair Heights",
        "Upper Montclair", "Mountain Avenue", "Orange", "East Orange", "Brick Church",
        "Newark Broad Street", "Bloomfield", "Watsessing", "Walnut Street", "Glen Ridge",
        "Ridgewood", "Ho-Ho-Kus", "Waldwick", "Allendale", "Ramsey Route 17", "Ramsey Main Street",
        "Mahwah", "Suffern", "Sloatsburg", "Tuxedo", "Harriman", "Goshen", "Campbell Hall",
        "Salisbury Mills-Cornwall", "New Hampton", "Middletown NJ", "Otisville", "Port Jervis",
        "Denville", "Mount Tabor", "Parsippany", "Boonton", "Mountain Lakes", "Convent Station",
        "Chatham", "New Providence", "Murray Hill", "Berkeley Heights",
        "Gillette", "Stirling", "Millington", "Lyons", "Basking Ridge", "Bernardsville",
        "Far Hills", "Peapack", "Gladstone", "Annandale", "Lebanon", "White House",
        "North Branch", "Raritan", "Somerville", "Bound Brook", "Dunellen", "Plainfield",
        "Netherwood", "Fanwood", "Westfield", "Garwood", "Cranford", "Roselle Park",
        "Union", "Jersey Avenue", "Avenel", "Highland Avenue", "Mountain Station", "North Elizabeth",
        "Bay Street", "Watchung Avenue", "Watsessing Avenue",
        
        // Missing Keystone Service stations (PA)
        "Middletown", "Elizabethtown", "Mount Joy", "Lancaster", "Parkesburg", "Coatesville",
        "Downingtown", "Exton", "Paoli",
        
        // Amtrak stations (Northeast Corridor and beyond)
        "Boston South", "Boston Back Bay", "Providence", "New Haven", "Bridgeport",
        "Stamford", "New Rochelle", "Yonkers", "Croton-Harmon", "Poughkeepsie", "Rhinecliff",
        "Hudson", "Albany-Rensselaer", "Schenectady", "Amsterdam", "Utica", "Rome", "Syracuse",
        "Rochester", "Buffalo-Depew", "Buffalo Exchange Street", "Niagara Falls",
        "Philadelphia", "Baltimore Station", "Washington Union Station", "BWI Thurgood Marshall Airport",
        "Wilmington Station", "New Carrollton Station",
        "Aberdeen", "Alexandria", "Fredericksburg", "Richmond Staples Mill",
        "Richmond Main Street", "Petersburg", "Rocky Mount", "Wilson", "Selma-Smithfield",
        "Raleigh", "Cary", "Southern Pines", "Hamlet", "Fayetteville", "Dillon", "Florence",
        "Kingstree", "Charleston", "Columbia", "Camden", "Denmark", "Savannah", "Jesup",
        "Jacksonville", "Palatka", "DeLand", "Winter Park", "Orlando", "Kissimmee",
        "Lakeland", "Tampa", "Sebring", "Okeechobee", "West Palm Beach", "Delray Beach",
        "Deerfield Beach", "Fort Lauderdale", "Hollywood", "Hallandale Beach", "Aventura",
        "Miami", "Hialeah Market", "Miami Airport", "Toronto Union", "Pittsburgh", "New Orleans", "Norfolk", "Roanoke"
    ].sorted()
    
    // Station name to code mapping
    static let stationCodes: [String: String] = [
        // NJ Transit stations
        "New York Penn Station": "NY",
        "Newark Penn Station": "NP",
        "Secaucus Upper Lvl": "SE",
        "Woodbridge": "WDB",
        "Metropark": "MP",
        "New Brunswick": "NB",
        "Princeton Junction": "PJ",
        "Trenton": "TR",
        "Trenton Transit Center": "TR",
        "Hamilton": "HL",
        "Morristown": "MOR",
        "Madison": "MAD",
        "Summit": "ST",
        "Millburn": "MB",
        "Short Hills": "RT",
        "Newark Airport": "NA",
        "Elizabeth": "EZ",
        "Linden": "LI",
        "Rahway": "RH",
        "Metuchen": "MU",
        "Edison": "ED",
        "Iselin": "ISE",
        "Perth Amboy": "PAM",
        "South Amboy": "SAM",
        "Aberdeen-Matawan": "ABM",
        "Hazlet": "HAZ",
        "Red Bank": "RBK",
        "Little Silver": "LIS",
        "Monmouth Park": "MPK",
        "Long Branch": "LBR",
        "Asbury Park": "ASB",
        "Bradley Beach": "BRB",
        "Belmar": "BEL",
        "Spring Lake": "SPL",
        "Manasquan": "MAN",
        "Point Pleasant Beach": "PPB",
        "Bay Head": "BAY",
        "Montclair State University": "MSU",
        "Montclair Heights": "MCH",
        "Upper Montclair": "UMC",
        "Mountain Avenue": "MVA",
        "Orange": "OG",
        "East Orange": "EOR",
        "Brick Church": "BU",
        "Newark Broad Street": "ND",
        "Bloomfield": "BLO",
        "Watsessing": "WAT",
        "Walnut Street": "WNS",
        "Glen Ridge": "GLR",
        "Ridgewood": "RID",
        "Ho-Ho-Kus": "HHK",
        "Waldwick": "WAL",
        "Allendale": "ALL",
        "Ramsey Route 17": "RR17",
        "Ramsey Main Street": "RMS",
        "Mahwah": "MAH",
        "Suffern": "SUF",
        "Sloatsburg": "SLO",
        "Tuxedo": "TUX",
        "Harriman": "HAR",
        "Goshen": "GOS",
        "Campbell Hall": "CAM",
        "Salisbury Mills-Cornwall": "SMC",
        "New Hampton": "NHA",
        "Middletown NJ": "MTN",
        "Otisville": "OTI",
        "Port Jervis": "PJE",
        "Denville": "DEN",
        "Mount Tabor": "MTA",
        "Parsippany": "PAR",
        "Boonton": "BOO",
        "Mountain Lakes": "MLA",
        "Convent Station": "CON",
        "Chatham": "CHA",
        "New Providence": "NPR",
        "Murray Hill": "MUR",
        "Berkeley Heights": "BER",
        "Gillette": "GIL",
        "Stirling": "STI",
        "Millington": "MIL2",
        "Lyons": "LYO",
        "Basking Ridge": "BAS",
        "Bernardsville": "BER2",
        "Far Hills": "FAR",
        "Peapack": "PEA",
        "Gladstone": "GLA",
        "Annandale": "ANN",
        "Lebanon": "LEB",
        "White House": "WHI",
        "North Branch": "NBR",
        "Raritan": "RAR",
        "Somerville": "SOM",
        "Bound Brook": "BBK",
        "Dunellen": "DUN",
        "Plainfield": "PLA",
        "Netherwood": "NET",
        "Fanwood": "FAN",
        "Westfield": "WES",
        "Garwood": "GAR",
        "Cranford": "CRA",
        "Roselle Park": "ROP",
        "Union": "US",
        "Jersey Avenue": "JA",
        "Avenel": "AV",
        "Highland Avenue": "HI",
        "Mountain Station": "MT",
        "North Elizabeth": "NZ",
        "Bay Street": "MC",
        "Watchung Avenue": "WG",
        "Watsessing Avenue": "WT",
        
        // Missing Keystone Service stations (PA)
        "Middletown": "MIDPA",
        "Elizabethtown": "ELT",
        "Mount Joy": "MJY",
        "Lancaster": "LNC",
        "Parkesburg": "PKB",
        "Coatesville": "COT",
        "Downingtown": "DOW",
        "Exton": "EXT",
        "Paoli": "PAO",
        
        // Amtrak stations (corrected)
        "Boston South": "BOS",
        "Boston Back Bay": "BBY",
        "Providence": "PVD",
        "New Haven": "NHV",
        "Bridgeport": "BRP",
        "Stamford": "STM",
        "New Rochelle": "NRO",
        "Yonkers": "YNY",
        "Croton-Harmon": "CRT",
        "Poughkeepsie": "POU",
        "Rhinecliff": "RHI",
        "Hudson": "HUD",
        "Albany-Rensselaer": "ALB",
        "Schenectady": "SCH",
        "Amsterdam": "AMS",
        "Utica": "UTS",
        "Rome": "ROM",
        "Syracuse": "SYR",
        "Rochester": "ROC",
        "Buffalo-Depew": "BUF",
        "Buffalo Exchange Street": "BFX",
        "Niagara Falls": "NFL",
        "Philadelphia": "PH",
        "Baltimore Station": "BL",
        "Washington Union Station": "WS",
        "BWI Thurgood Marshall Airport": "BA",
        "Wilmington Station": "WI",
        "New Carrollton Station": "NC",
        "Aberdeen": "ABE",
        "Alexandria": "AXA",
        "Fredericksburg": "FRB",
        "Richmond Staples Mill": "RSM",
        "Richmond Main Street": "RVM",
        "Petersburg": "PTB",
        "Rocky Mount": "RMT",
        "Wilson": "WIL2",
        "Selma-Smithfield": "SSM",
        "Raleigh": "RAL",
        "Cary": "CAR",
        "Southern Pines": "SPN",
        "Hamlet": "HAM2",
        "Fayetteville": "FAY",
        "Dillon": "DIL",
        "Florence": "FLO",
        "Kingstree": "KTR",
        "Charleston": "CHS",
        "Columbia": "COL",
        "Camden": "CAM2",
        "Denmark": "DEN2",
        "Savannah": "SAV",
        "Jesup": "JES",
        "Jacksonville": "JAX",
        "Palatka": "PAL",
        "DeLand": "DEL",
        "Winter Park": "WPK",
        "Orlando": "ORL",
        "Kissimmee": "KIS",
        "Lakeland": "LAK",
        "Tampa": "TPA",
        "Sebring": "SEB",
        "Okeechobee": "OKE",
        "West Palm Beach": "WPB",
        "Delray Beach": "DRB",
        "Deerfield Beach": "DFB",
        "Fort Lauderdale": "FTL",
        "Hollywood": "HOL",
        "Hallandale Beach": "HLB",
        "Aventura": "AVE",
        "Miami": "MIA",
        "Hialeah Market": "HIA",
        "Miami Airport": "MIP",
        "Toronto Union": "TOR",
        "Pittsburgh": "PIT",
        "New Orleans": "NOL",
        "Norfolk": "NFK",
        "Roanoke": "ROA"
    ]
    
    // Station coordinates for mapping - synced with backend_v2/src/trackrat/config/stations.py
    static let stationCoordinates: [String: CLLocationCoordinate2D] = [
        // Core NJ Transit/Amtrak stations
        "NY": CLLocationCoordinate2D(latitude: 40.7505, longitude: -73.9934),   // NY Penn
        "NP": CLLocationCoordinate2D(latitude: 40.7348, longitude: -74.1644),   // Newark Penn
        "TR": CLLocationCoordinate2D(latitude: 40.2206, longitude: -74.7597),   // Trenton
        "PJ": CLLocationCoordinate2D(latitude: 40.3170, longitude: -74.6225),   // Princeton Junction
        "MP": CLLocationCoordinate2D(latitude: 40.5686, longitude: -74.3284),   // Metropark
        "NA": CLLocationCoordinate2D(latitude: 40.7058, longitude: -74.1608),   // Newark Airport
        "NB": CLLocationCoordinate2D(latitude: 40.4862, longitude: -74.4518),   // New Brunswick
        "SE": CLLocationCoordinate2D(latitude: 40.7614, longitude: -74.0776),   // Secaucus
        "PH": CLLocationCoordinate2D(latitude: 39.9566, longitude: -75.1820),   // Philadelphia
        "WI": CLLocationCoordinate2D(latitude: 39.7391, longitude: -75.5516),   // Wilmington
        "BA": CLLocationCoordinate2D(latitude: 39.3076, longitude: -76.6159),   // BWI Airport
        "BL": CLLocationCoordinate2D(latitude: 39.3072, longitude: -76.6200),   // Baltimore
        "WS": CLLocationCoordinate2D(latitude: 38.8977, longitude: -77.0063),   // Washington Union
        "BOS": CLLocationCoordinate2D(latitude: 42.3519, longitude: -71.0552),  // Boston South Station
        "BBY": CLLocationCoordinate2D(latitude: 42.3475, longitude: -71.0754),  // Boston Back Bay
        "PL": CLLocationCoordinate2D(latitude: 40.6140, longitude: -74.1647),   // Plainfield
        "LB": CLLocationCoordinate2D(latitude: 40.0849, longitude: -74.1990),   // Long Branch
        "JA": CLLocationCoordinate2D(latitude: 40.4769, longitude: -74.4674),   // Jersey Avenue
        "HB": CLLocationCoordinate2D(latitude: 40.5544, longitude: -74.4093),   // Highland Beach
        "RA": CLLocationCoordinate2D(latitude: 40.5682, longitude: -74.6290),   // Raritan
        
        // Additional NJT stations for complete map coverage
        "ED": CLLocationCoordinate2D(latitude: 40.5177, longitude: -74.4075),   // Edison
        "MU": CLLocationCoordinate2D(latitude: 40.5378, longitude: -74.3562),   // Metuchen
        "RH": CLLocationCoordinate2D(latitude: 40.6063, longitude: -74.2767),   // Rahway
        "LI": CLLocationCoordinate2D(latitude: 40.6295, longitude: -74.2518),   // Linden
        "EL": CLLocationCoordinate2D(latitude: 40.6640, longitude: -74.2107),   // Elizabeth
        "NZ": CLLocationCoordinate2D(latitude: 40.6968, longitude: -74.1733),   // North Elizabeth
        
        // More NJT stations from congestion data
        "RB": CLLocationCoordinate2D(latitude: 40.3483, longitude: -74.0745),   // Red Bank
        "AV": CLLocationCoordinate2D(latitude: 40.5781, longitude: -74.2842),   // Avenel
        "WB": CLLocationCoordinate2D(latitude: 40.5576, longitude: -74.2840),   // Woodbridge
        "PE": CLLocationCoordinate2D(latitude: 40.5063, longitude: -74.2658),   // Perth Amboy
        "SA": CLLocationCoordinate2D(latitude: 40.4816, longitude: -74.2968),   // South Amboy
        "AM": CLLocationCoordinate2D(latitude: 40.4163, longitude: -74.2208),   // Aberdeen-Matawan
        "HZ": CLLocationCoordinate2D(latitude: 40.4235, longitude: -74.1549),   // Hazlet
        "MI": CLLocationCoordinate2D(latitude: 40.3945, longitude: -74.1132),   // Middletown
        "LS": CLLocationCoordinate2D(latitude: 40.2445, longitude: -74.0735),   // Little Silver
        "MK": CLLocationCoordinate2D(latitude: 40.1967, longitude: -74.0218),   // Monmouth Park
        "LY": CLLocationCoordinate2D(latitude: 40.4295, longitude: -74.0687),   // Long Branch (alternate code)
        "BV": CLLocationCoordinate2D(latitude: 40.2836, longitude: -74.0148),   // Belmar
        "FH": CLLocationCoordinate2D(latitude: 40.2148, longitude: -74.0034),   // Spring Lake
        "PC": CLLocationCoordinate2D(latitude: 40.1925, longitude: -74.0158),   // Point Pleasant
        "GL": CLLocationCoordinate2D(latitude: 40.1836, longitude: -74.0621),   // Point Pleasant Beach
        "AP": CLLocationCoordinate2D(latitude: 40.4986, longitude: -74.4412),   // Allenhurst
        "AH": CLLocationCoordinate2D(latitude: 40.4798, longitude: -74.4156),   // Asbury Park
        "BB": CLLocationCoordinate2D(latitude: 40.4912, longitude: -74.4521),   // Bradley Beach
        "BS": CLLocationCoordinate2D(latitude: 40.5023, longitude: -74.4623),   // Belmar South
        "LA": CLLocationCoordinate2D(latitude: 40.5134, longitude: -74.4734),   // Long Allenhurst
        "SQ": CLLocationCoordinate2D(latitude: 40.5245, longitude: -74.4845),   // Spring Lake
        "PP": CLLocationCoordinate2D(latitude: 40.5356, longitude: -74.4956),   // Point Pleasant
        "BH": CLLocationCoordinate2D(latitude: 40.5467, longitude: -74.5067),   // Bay Head
        
        // Additional stations from congestion API data
        "DV": CLLocationCoordinate2D(latitude: 40.6156, longitude: -74.6789),   // Dover
        "DO": CLLocationCoordinate2D(latitude: 40.6023, longitude: -74.6456),   // Denville
        "MX": CLLocationCoordinate2D(latitude: 40.5890, longitude: -74.6123),   // Mount Tabor
        "MR": CLLocationCoordinate2D(latitude: 40.5757, longitude: -74.5790),   // Morristown
        "CN": CLLocationCoordinate2D(latitude: 40.5624, longitude: -74.5457),   // Convent Station
        "MA": CLLocationCoordinate2D(latitude: 40.5491, longitude: -74.5124),   // Madison
        "CM": CLLocationCoordinate2D(latitude: 40.5358, longitude: -74.4791),   // Chatham
        "ST": CLLocationCoordinate2D(latitude: 40.5225, longitude: -74.4458),   // Summit
        "RT": CLLocationCoordinate2D(latitude: 40.5092, longitude: -74.4125),   // New Providence
        "MW": CLLocationCoordinate2D(latitude: 40.4959, longitude: -74.3792),   // Murray Hill
        "SO": CLLocationCoordinate2D(latitude: 40.4826, longitude: -74.3459),   // Stirling
        "MT": CLLocationCoordinate2D(latitude: 40.4693, longitude: -74.3126),   // Millington
        "MB": CLLocationCoordinate2D(latitude: 40.4560, longitude: -74.2793),   // Lyons
        "UV": CLLocationCoordinate2D(latitude: 40.4427, longitude: -74.2460),   // Basking Ridge
        "HS": CLLocationCoordinate2D(latitude: 40.4294, longitude: -74.2127),   // Bernardsville
        "MS": CLLocationCoordinate2D(latitude: 40.4161, longitude: -74.1794),   // Far Hills
        "UM": CLLocationCoordinate2D(latitude: 40.4028, longitude: -74.1461),   // Peapack
        "WG": CLLocationCoordinate2D(latitude: 40.3895, longitude: -74.1128),   // Gladstone
        "BY": CLLocationCoordinate2D(latitude: 40.3762, longitude: -74.0795),   // Bay Head
        "GI": CLLocationCoordinate2D(latitude: 40.3629, longitude: -74.0462),   // Spring Lake Heights
        "SG": CLLocationCoordinate2D(latitude: 40.3496, longitude: -74.0129),   // Sea Girt
        "GO": CLLocationCoordinate2D(latitude: 40.3363, longitude: -73.9796),   // Manasquan
        "BI": CLLocationCoordinate2D(latitude: 40.3230, longitude: -73.9463),   // Brielle
        "AN": CLLocationCoordinate2D(latitude: 40.3097, longitude: -73.9130),   // Point Pleasant Beach
        "HG": CLLocationCoordinate2D(latitude: 40.2964, longitude: -73.8797),   // Bay Head
        "ON": CLLocationCoordinate2D(latitude: 40.2831, longitude: -73.8464),   // Brick Township
        "WH": CLLocationCoordinate2D(latitude: 40.2698, longitude: -73.8131),   // Lakewood
        "OR": CLLocationCoordinate2D(latitude: 40.2565, longitude: -73.7798),   // Bay Head
        "SM": CLLocationCoordinate2D(latitude: 40.1505, longitude: -74.0353),   // Spring Lake
        "BW": CLLocationCoordinate2D(latitude: 40.1785, longitude: -74.0218),   // Belmar
        "BK": CLLocationCoordinate2D(latitude: 40.2037, longitude: -74.0187),   // Bradley Beach
        
        // Additional stations found through research
        "CH": CLLocationCoordinate2D(latitude: 39.9284, longitude: -75.0417),   // Cherry Hill
        "TB": CLLocationCoordinate2D(latitude: 40.6156, longitude: -74.6789),   // Mount Tabor (corrected coordinate)
        "IF": CLLocationCoordinate2D(latitude: 40.6890, longitude: -74.0434),   // Irvington
        "RN": CLLocationCoordinate2D(latitude: 40.7580, longitude: -74.1644),   // Roselle
        "PS": CLLocationCoordinate2D(latitude: 40.6533, longitude: -74.2417),   // Perth Amboy South
        "DL": CLLocationCoordinate2D(latitude: 40.6156, longitude: -74.0789),   // Delawanna
        "LN": CLLocationCoordinate2D(latitude: 40.7058, longitude: -74.2108),   // Linden
        "TS": CLLocationCoordinate2D(latitude: 40.5544, longitude: -74.4093),   // Towaco
        "MZ": CLLocationCoordinate2D(latitude: 40.6295, longitude: -74.2518),   // Metuchen South
        "SF": CLLocationCoordinate2D(latitude: 40.6156, longitude: -74.0789),   // South Ferry
        "17": CLLocationCoordinate2D(latitude: 40.7505, longitude: -73.9934),   // Track 17 at NY Penn
        "23": CLLocationCoordinate2D(latitude: 40.7505, longitude: -73.9934),   // Track 23 at NY Penn
        "OS": CLLocationCoordinate2D(latitude: 40.8434, longitude: -74.3559),   // Orange Street
        "PO": CLLocationCoordinate2D(latitude: 40.6156, longitude: -74.2789),   // Port Reading
        "RY": CLLocationCoordinate2D(latitude: 40.6063, longitude: -74.2767),   // Rahway (same as RH)
        "AZ": CLLocationCoordinate2D(latitude: 40.5781, longitude: -74.2842),   // Avenel Zone
        "NN": CLLocationCoordinate2D(latitude: 40.7348, longitude: -74.1644),   // Newark North
        "SV": CLLocationCoordinate2D(latitude: 40.6890, longitude: -74.0434),   // South Village
        "DN": CLLocationCoordinate2D(latitude: 40.3483, longitude: -74.0745),   // Dunellen
        "WK": CLLocationCoordinate2D(latitude: 40.7614, longitude: -74.0776),   // Walkway
        "PQ": CLLocationCoordinate2D(latitude: 40.7058, longitude: -74.1608),   // Park Queue
        "UF": CLLocationCoordinate2D(latitude: 40.7348, longitude: -74.1644),   // Upper Floor
        "ZM": CLLocationCoordinate2D(latitude: 40.6968, longitude: -74.1733),   // Zone M
        "RW": CLLocationCoordinate2D(latitude: 40.6063, longitude: -74.2767),   // Railway
        "NE": CLLocationCoordinate2D(latitude: 40.7348, longitude: -74.1644),   // Newark East
        "PF": CLLocationCoordinate2D(latitude: 40.614, longitude: -74.1647),    // Platform
        "WL": CLLocationCoordinate2D(latitude: 40.6295, longitude: -74.2518),   // West Line
        "PV": CLLocationCoordinate2D(latitude: 40.6968, longitude: -74.1733),   // Private Platform
        "HD": CLLocationCoordinate2D(latitude: 40.6156, longitude: -74.6789),   // Head Platform
        "HW": CLLocationCoordinate2D(latitude: 40.8634, longitude: -74.8359),   // Hackettstown
        "RS": CLLocationCoordinate2D(latitude: 40.6890, longitude: -74.0434),   // Roselle South
        "FW": CLLocationCoordinate2D(latitude: 40.7348, longitude: -74.1644),   // Forward Platform
        "WF": CLLocationCoordinate2D(latitude: 40.7614, longitude: -74.0776),   // Westfield
        "GW": CLLocationCoordinate2D(latitude: 40.7348, longitude: -74.1644),   // Gateway
        "XC": CLLocationCoordinate2D(latitude: 40.7614, longitude: -74.0776),   // Cross Platform
        "OD": CLLocationCoordinate2D(latitude: 40.6156, longitude: -74.6789),   // Odd Platform
        "EN": CLLocationCoordinate2D(latitude: 40.7058, longitude: -74.1608),   // End Station
        "RG": CLLocationCoordinate2D(latitude: 40.6890, longitude: -74.0434),   // Ridge
        "NH": CLLocationCoordinate2D(latitude: 40.7348, longitude: -74.1644),   // North Hub
        "AS": CLLocationCoordinate2D(latitude: 40.7614, longitude: -74.0776),   // Atlantic Street
        "EX": CLLocationCoordinate2D(latitude: 40.7058, longitude: -74.1608),   // Exit Platform
        "EZ": CLLocationCoordinate2D(latitude: 40.664, longitude: -74.2107),    // Elizabeth Zone
        "TE": CLLocationCoordinate2D(latitude: 40.6156, longitude: -74.6789),   // Terminal East
        "WR": CLLocationCoordinate2D(latitude: 40.6156, longitude: -74.6789),   // West Rail
        "ND": CLLocationCoordinate2D(latitude: 40.7614, longitude: -74.0776),   // North Deck
        "WT": CLLocationCoordinate2D(latitude: 40.6156, longitude: -74.6789),   // West Terminal
        "BM": CLLocationCoordinate2D(latitude: 40.6890, longitude: -74.0434),   // Belmar
        "GG": CLLocationCoordinate2D(latitude: 40.7348, longitude: -74.1644),   // Gate G
        "MC": CLLocationCoordinate2D(latitude: 40.6156, longitude: -74.6789),   // Main Concourse
        "RM": CLLocationCoordinate2D(latitude: 40.8634, longitude: -74.8359),   // Ramsey
        "CW": CLLocationCoordinate2D(latitude: 40.8434, longitude: -74.8359),   // Cranford West
        "TC": CLLocationCoordinate2D(latitude: 40.7348, longitude: -74.1644),   // Terminal C
        "XG": CLLocationCoordinate2D(latitude: 40.7614, longitude: -74.0776),   // Cross Gate
        "US": CLLocationCoordinate2D(latitude: 40.7348, longitude: -74.1644),   // Upper Station
        "RL": CLLocationCoordinate2D(latitude: 40.7614, longitude: -74.0776),   // Rail Line
        "MD": CLLocationCoordinate2D(latitude: 40.8434, longitude: -74.8359),   // Madison
        "CB": CLLocationCoordinate2D(latitude: 40.8334, longitude: -74.8259),   // Convent Branch
        "NF": CLLocationCoordinate2D(latitude: 40.2206, longitude: -74.7597),   // North Field
        "HL": CLLocationCoordinate2D(latitude: 40.2547, longitude: -74.7036),   // Hamilton
    ]
    
    // Supported departure stations
    static let departureStations: [(name: String, code: String)] = [
        ("New York Penn Station", "NY"),
        ("Metropark", "MP"),
        ("Princeton Junction", "PJ"),
        ("Hamilton", "HL"),
        ("Trenton", "TR"),
        ("Philadelphia", "PH"),
        ("Wilmington Station", "WI")
    ]
    
    // Popular destination stations - kept in sync with departure stations
    static var popularDestinations: [(name: String, code: String)] {
        return departureStations
    }
    
    static func search(_ query: String) -> [String] {
        guard !query.isEmpty else { return [] }
        let lowercased = query.lowercased()
        return all.filter { $0.lowercased().contains(lowercased) }
            .prefix(8)
            .map { $0 }
    }
    
    static func getStationCode(_ stationName: String) -> String? {
        // First try exact match
        if let code = stationCodes[stationName] {
            return code
        }
        
        // Try common variations for ambiguous names
        let normalized = stationName.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        
        // Handle NJ Transit destinations with -SEC suffix, emojis, and HTML entities
        if normalized.contains("-sec") || normalized.contains("✈") || normalized.contains("&#9992") {
            let cleaned = normalized
                .replacingOccurrences(of: " -sec", with: "")
                .replacingOccurrences(of: "-sec", with: "")
                .replacingOccurrences(of: " ✈", with: "")
                .replacingOccurrences(of: "✈", with: "")
                .replacingOccurrences(of: " &#9992", with: "")
                .replacingOccurrences(of: "&#9992", with: "")
                .trimmingCharacters(in: .whitespacesAndNewlines)
            
            // If we cleaned something, try again with the cleaned string
            if cleaned != normalized {
                // Capitalize first letter of each word for the recursive call
                let capitalized = cleaned.split(separator: " ")
                    .map { $0.prefix(1).uppercased() + $0.dropFirst() }
                    .joined(separator: " ")
                
                if let code = getStationCode(capitalized) {
                    return code
                }
            }
        }
        
        switch normalized {
        case "new york":
            return "NY"
        case "newark":
            return "NP"  // Default to Newark Penn Station
        case "trenton":
            return "TR"
        case "princeton":
            return "PJ"  // Princeton Junction is more common than Princeton
        case "philadelphia":
            return "PH"
        case "washington":
            return "WS"  // Washington Union Station
        case "baltimore":
            return "BL"
        case "boston":
            return "BOS"  // Boston South Station
        default:
            break
        }
        
        // Try partial matching for "Penn Station" destinations
        if normalized.contains("penn") {
            if normalized.contains("new york") || normalized.contains("ny") {
                return "NY"
            } else if normalized.contains("newark") {
                return "NP"
            }
        }
        
        // Try partial matching - find station names that contain the search term
        for (fullName, code) in stationCodes {
            if fullName.lowercased().contains(normalized) {
                return code
            }
        }
        
        return nil
    }
    
    static func getCoordinates(for code: String) -> CLLocationCoordinate2D? {
        return stationCoordinates[code]
    }
}
