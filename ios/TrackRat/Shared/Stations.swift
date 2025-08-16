import Foundation
import CoreLocation

struct Stations {
    static let all: [String] = [
        // NJ Transit stations (corrected codes to match API)
        "New York Penn Station", "Newark Penn Station", "Secaucus Upper Lvl",
        "Metropark", "New Brunswick", "Princeton Junction", "Trenton", "Hamilton",
        "Newark Airport",
        "Elizabeth", "Linden", "Rahway", "Metuchen", "Edison", "Iselin",
        "Jersey Avenue", "North Elizabeth",
        
        // Missing Keystone Service stations (PA)
        "Middletown PA", "Elizabethtown", "Mount Joy", "Lancaster", "Parkesburg", "Coatesville",
        "Downingtown", "Exton", "Paoli",
        
        // Amtrak stations (Northeast Corridor and beyond) - Updated with new stations
        "Boston South", "Boston Back Bay", "Providence", "New Haven", "Bridgeport",
        "Stamford", "Hartford", "Meriden", "New London", "Old Saybrook", "Wallingford", 
        "Windsor Locks", "Springfield", "Claremont", "Dover NH", "Durham-UNH", "Exeter",
        "Philadelphia", "Baltimore Station", "Washington Union Station", "BWI Thurgood Marshall Airport",
        "Wilmington Station", "New Carrollton", "Aberdeen", "Alexandria", "Charlottesville",
        "Lorton", "Norfolk", "Richmond Main Street", "Roanoke", "Harrisburg", "Lancaster",
        "Kingston", "Westerly"
    ].sorted()
    
    // Station name to code mapping - Updated to match backend STATION_CODES.txt
    static let stationCodes: [String: String] = [
        // NJ Transit stations from authoritative STATION_CODES.txt
        "New York Penn Station": "NY",
        "Newark Penn Station": "NP",
        "Secaucus Upper Lvl": "SE",
        "Secaucus Lower Lvl": "TS",
        "Secaucus Concourse": "SC",
        "Woodbridge": "WB",
        "Metropark": "MP",
        "New Brunswick": "NB",
        "Princeton Junction": "PJ",
        "Princeton": "PR",
        "Trenton": "TR",
        "Trenton Transit Center": "TR",  // Alias for Trenton
        "Hamilton": "HL",
        "Morristown": "MR",
        "Madison": "MA",
        "Summit": "ST",
        "Millburn": "MB",
        "Short Hills": "RT",
        "Newark Airport": "NA",
        "Newark Broad Street": "ND",
        "Elizabeth": "EZ",
        "North Elizabeth": "NZ",
        "Linden": "LI",
        "Rahway": "RH",
        "Metuchen": "MU",
        "Edison": "ED",
        "Perth Amboy": "PE",
        "South Amboy": "CH",
        "Aberdeen-Matawan": "AM",
        "Hazlet": "HZ",
        "Middletown": "MI",
        "Red Bank": "RB",
        "Little Silver": "LS",
        "Monmouth Park": "MK",
        "Long Branch": "LB",
        "Elberon": "EL",
        "Allenhurst": "AH",
        "Asbury Park": "AP",
        "Bradley Beach": "BB",
        "Belmar": "BS",
        "Spring Lake": "LA",
        "Manasquan": "SQ",
        "Point Pleasant Beach": "PP",
        "Bay Head": "BH",
        "Montclair State U": "UV",
        "Montclair Heights": "HS",
        "Upper Montclair": "UM",
        "Mountain Avenue": "MS",
        "Watchung Avenue": "WG",
        "Watsessing Avenue": "WT",
        "Orange": "OG",
        "East Orange": "EO",
        "Highland Avenue": "HI",
        "Mountain View": "MV",
        "Brick Church": "BU",
        "Bloomfield": "BM",
        "Glen Ridge": "GG",
        "Bay Street": "MC",
        "Walnut Street": "WS",  // Note: WS conflicts with Washington Union Station
        "Ridgewood": "RW",
        "Hohokus": "UF",
        "Waldwick": "WK",
        "Allendale": "AZ",
        "Ramsey Route 17": "17",
        "Ramsey Main St": "RY",
        "Mahwah": "MZ",
        "Suffern": "SF",
        "Sloatsburg": "XG",
        "Tuxedo": "TC",
        "Harriman": "RM",
        "Campbell Hall": "CB",
        "Salisbury Mills-Cornwall": "CW",
        "Otisville": "OS",
        "Port Jervis": "PO",
        "Denville": "DV",
        "Dover": "DO",
        "Mount Tabor": "TB",
        "Mount Arlington": "HV",
        "Lake Hopatcong": "HP",
        "Netcong": "NT",
        "Mount Olive": "OL",
        "Hackettstown": "HQ",
        "Boonton": "BN",
        "Mountain Lakes": "ML",
        "Lincoln Park": "LP",
        "Towaco": "TO",
        "Montclair-Boonton Line": "MO",  // Generic
        "Little Falls": "FA",
        "Wayne-Route 23": "23",
        "Mountain Station": "MT",
        "Convent Station": "CN",
        "Chatham": "CM",
        "New Providence": "NV",
        "Murray Hill": "MH",
        "Berkeley Heights": "BY",
        "Gillette": "GI",
        "Stirling": "SG",
        "Millington": "GO",
        "Lyons": "LY",
        "Basking Ridge": "BI",
        "Bernardsville": "BV",
        "Far Hills": "FH",
        "Peapack": "PC",
        "Gladstone": "GL",
        "High Bridge": "HG",
        "Annandale": "AN",
        "Lebanon": "ON",
        "White House": "WH",
        "North Branch": "OR",
        "Raritan": "RA",
        "Somerville": "SM",
        "Bridgewater": "BW",
        "Bound Brook": "BK",
        "Dunellen": "DN",
        "Plainfield": "PF",
        "Netherwood": "NE",
        "Fanwood": "FW",
        "Westfield": "WF",
        "Garwood": "GW",
        "Cranford": "XC",
        "Roselle Park": "RL",
        "Union": "US",
        "Avenel": "AV",
        "Jersey Avenue": "JA",
        "Hoboken": "HB",
        "Kingsland": "KG",
        "Lyndhurst": "LN",
        "Delawanna": "DL",
        "Passaic": "PS",
        "Clifton": "IF",
        "Paterson": "RN",
        "Hawthorne": "HW",
        "Glen Rock Main Line": "RS",
        "Glen Rock Boro Hall": "GK",
        "Fair Lawn-Broadway": "BF",
        "Radburn Fair Lawn": "FZ",
        "Garfield": "GD",
        "Plauderville": "PL",
        "Rutherford": "RF",
        "Wood Ridge": "WR",
        "Wesmont": "WM",
        "Teterboro": "TE",
        "Essex Street": "EX",
        "Anderson Street": "AS",
        "New Bridge Landing": "NH",
        "River Edge": "RG",
        "Oradell": "OD",
        "Emerson": "EN",
        "Westwood": "WW",
        "Hillsdale": "HD",
        "Woodcliff Lake": "WL",
        "Park Ridge": "PV",
        "Montvale": "ZM",
        "Pearl River": "PQ",
        "Nanuet": "NN",
        "Spring Valley": "SV",
        "Maplewood": "MW",
        "South Orange": "SO",
        "Morris Plains": "MX",
        "Great Notch": "GA",
        
        // Missing Keystone Service stations (PA)
        "Middletown PA": "MIDPA",  // Renamed to avoid conflict with Middletown NJ
        "Elizabethtown": "ELT",
        "Mount Joy": "MJY",
        "Parkesburg": "PKB",
        "Coatesville": "COT",
        "Downingtown": "DOW",
        "Exton": "EXT",
        "Paoli": "PAO",
        
        // Amtrak stations (corrected with updated codes to match backend)
        "Boston South": "BOS",
        "Boston Back Bay": "BBY",
        "Providence": "PVD",
        "New Haven": "NHV",
        "Bridgeport": "BRP",
        "Stamford": "STM",
        "Hartford": "HFD",
        "Meriden": "MDN",
        "New London": "NLC",
        "Old Saybrook": "OSB",
        "Wallingford": "WFD",
        "Windsor Locks": "WNL",
        "Springfield": "SPG",
        "Claremont": "CLA",
        "Dover NH": "DOV",  // Renamed to avoid conflict with Dover NJ
        "Durham-UNH": "DHM",
        "Exeter": "EXR",
        "Philadelphia": "PH",
        "Baltimore Station": "BL",
        "Washington Union Station": "WS",
        "BWI Thurgood Marshall Airport": "BA",
        "Wilmington Station": "WI",
        "New Carrollton": "NCR",
        "Aberdeen": "ABE",
        "Alexandria": "ALX",
        "Charlottesville": "CVS",
        "Lorton": "LOR",
        "Norfolk": "NFK",
        "Richmond Main Street": "RVR",
        "Roanoke": "RNK",
        "Harrisburg": "HAR",
        "Lancaster": "LNC",
        "Kingston": "KIN",
        "Westerly": "WLY"
    ]
    
    // Station coordinates for mapping - synced with backend_v2/src/trackrat/config/stations.py
    static let stationCoordinates: [String: CLLocationCoordinate2D] = [
        // Core NJ Transit/Amtrak stations - Updated GPS coordinates
        "NY": CLLocationCoordinate2D(latitude: 40.7506, longitude: -73.9939),   // New York Penn Station - Updated GPS
        "NP": CLLocationCoordinate2D(latitude: 40.7347, longitude: -74.1644),   // Newark Penn Station - Updated GPS
        "TR": CLLocationCoordinate2D(latitude: 40.218518, longitude: -74.753923), // Trenton Transit Center - Updated GPS
        "HL": CLLocationCoordinate2D(latitude: 40.2547, longitude: -74.7036),   // Hamilton
        "PJ": CLLocationCoordinate2D(latitude: 40.3167, longitude: -74.6233),   // Princeton Junction - Updated GPS
        "MP": CLLocationCoordinate2D(latitude: 40.5378, longitude: -74.3562),   // Metropark - Updated GPS
        "NB": CLLocationCoordinate2D(latitude: 40.4862, longitude: -74.4518),   // New Brunswick
        "SE": CLLocationCoordinate2D(latitude: 40.7612, longitude: -74.0758),   // Secaucus Junction - Updated GPS
        "PH": CLLocationCoordinate2D(latitude: 39.9570, longitude: -75.1820),   // Philadelphia 30th Street Station - Updated GPS
        "WI": CLLocationCoordinate2D(latitude: 39.7369, longitude: -75.5522),   // Wilmington - Updated GPS
        "BA": CLLocationCoordinate2D(latitude: 39.1896, longitude: -76.6934),   // BWI Airport Rail Station - Updated GPS
        "BL": CLLocationCoordinate2D(latitude: 39.3081, longitude: -76.6175),   // Baltimore Penn Station - Updated GPS
        "WS": CLLocationCoordinate2D(latitude: 38.8973, longitude: -77.0064),   // Washington Union Station - Updated GPS
        "BOS": CLLocationCoordinate2D(latitude: 42.3520, longitude: -71.0552),  // Boston South Station - Updated GPS
        "BBY": CLLocationCoordinate2D(latitude: 42.3473, longitude: -71.0764),  // Boston Back Bay - Updated GPS
        
        // Additional Amtrak stations with GPS coordinates
        "BRP": CLLocationCoordinate2D(latitude: 41.1767, longitude: -73.1874),  // Bridgeport, CT
        "HFD": CLLocationCoordinate2D(latitude: 41.7678, longitude: -72.6821),  // Hartford, CT
        "MDN": CLLocationCoordinate2D(latitude: 41.5390, longitude: -72.8012),  // Meriden, CT
        "NHV": CLLocationCoordinate2D(latitude: 41.2987, longitude: -72.9259),  // New Haven, CT
        "NLC": CLLocationCoordinate2D(latitude: 41.3543, longitude: -72.0939),  // New London, CT
        "OSB": CLLocationCoordinate2D(latitude: 41.3005, longitude: -72.3760),  // Old Saybrook, CT
        "STM": CLLocationCoordinate2D(latitude: 41.0462, longitude: -73.5427),  // Stamford, CT
        "WFD": CLLocationCoordinate2D(latitude: 41.4571, longitude: -72.8254),  // Wallingford, CT
        "WNL": CLLocationCoordinate2D(latitude: 41.9272, longitude: -72.6286),  // Windsor Locks, CT
        "ABE": CLLocationCoordinate2D(latitude: 39.5095, longitude: -76.1630),  // Aberdeen, MD
        "NCR": CLLocationCoordinate2D(latitude: 38.9533, longitude: -76.8644),  // New Carrollton, MD
        "SPG": CLLocationCoordinate2D(latitude: 42.1060, longitude: -72.5936),  // Springfield, MA
        "CLA": CLLocationCoordinate2D(latitude: 43.3688, longitude: -72.3793),  // Claremont, NH
        "DOV": CLLocationCoordinate2D(latitude: 43.1979, longitude: -70.8737),  // Dover, NH
        "DHM": CLLocationCoordinate2D(latitude: 43.1340, longitude: -70.9267),  // Durham-UNH, NH
        "EXR": CLLocationCoordinate2D(latitude: 42.9809, longitude: -70.9478),  // Exeter, NH
        "HAR": CLLocationCoordinate2D(latitude: 40.2616, longitude: -76.8782),  // Harrisburg, PA
        "LNC": CLLocationCoordinate2D(latitude: 40.0538, longitude: -76.3076),  // Lancaster, PA
        "KIN": CLLocationCoordinate2D(latitude: 41.4885, longitude: -71.5204),  // Kingston, RI
        "PVD": CLLocationCoordinate2D(latitude: 41.8256, longitude: -71.4160),  // Providence, RI
        "WLY": CLLocationCoordinate2D(latitude: 41.3770, longitude: -71.8307),  // Westerly, RI
        "ALX": CLLocationCoordinate2D(latitude: 38.8062, longitude: -77.0626),  // Alexandria, VA
        "CVS": CLLocationCoordinate2D(latitude: 38.0320, longitude: -78.4921),  // Charlottesville, VA
        "LOR": CLLocationCoordinate2D(latitude: 38.7060, longitude: -77.2214),  // Lorton, VA
        "NFK": CLLocationCoordinate2D(latitude: 36.8583, longitude: -76.2876),  // Norfolk, VA
        "RVR": CLLocationCoordinate2D(latitude: 37.6143, longitude: -77.4966),  // Richmond Main Street, VA
        "RNK": CLLocationCoordinate2D(latitude: 37.3077, longitude: -79.9803),  // Roanoke, VA
        "PF": CLLocationCoordinate2D(latitude: 40.6140, longitude: -74.4147),   // Plainfield (corrected code from PL to PF)
        "LB": CLLocationCoordinate2D(latitude: 40.2970, longitude: -73.9883),   // Long Branch
        "JA": CLLocationCoordinate2D(latitude: 40.4769, longitude: -74.4674),   // Jersey Avenue
        "US": CLLocationCoordinate2D(latitude: 40.683542211, longitude: -74.23800686),   // Union Station 40.683542211783646, -74.2380068698304
        "AZ": CLLocationCoordinate2D(latitude: 41.0308516, longitude: -74.13104499),  // Allendale 41.030851610302, -74.13104499027673
        "NA": CLLocationCoordinate2D(latitude: 40.7044941, longitude: -74.1909959),   // Newark Airport
        "RH": CLLocationCoordinate2D(latitude: 40.6039, longitude: -74.2723),   // Rahway (corrected code from RY to RH)
        "HB": CLLocationCoordinate2D(latitude: 40.734843, longitude: -74.028043), // Hoboken Terminal - Updated GPS
        "RA": CLLocationCoordinate2D(latitude: 40.57091522, longitude: -74.6344244),   // Raritan  40.5709152209129, -74.63442444281485
        "DN": CLLocationCoordinate2D(latitude: 40.5892, longitude: -74.4719),   // Dunellen
        
        // Additional NJT stations for complete map coverage - Updated GPS
        "ED": CLLocationCoordinate2D(latitude: 40.5177, longitude: -74.4075),   // Edison - Updated GPS
        "MU": CLLocationCoordinate2D(latitude: 40.5378, longitude: -74.3562),   // Metuchen - Updated GPS
        "LI": CLLocationCoordinate2D(latitude: 40.629487, longitude: -74.251772), // Linden - Updated GPS
        "EL": CLLocationCoordinate2D(latitude: 40.265251, longitude: -73.997479), // Elberon - Updated GPS 40.265251400000004, -73.99747922393298
        "EZ": CLLocationCoordinate2D(latitude: 40.667859, longitude: -74.215171), // Elizabeth - Updated GPS
        "NZ": CLLocationCoordinate2D(latitude: 40.6968, longitude: -74.1733),   // North Elizabeth
        
        // Additional stations for Raritan Valley and North Jersey Coast Lines
        "BK": CLLocationCoordinate2D(latitude: 40.5612539, longitude: -74.53021426),   // Bound Brook 40.56125391599582, -74.53021426346963
        "WF": CLLocationCoordinate2D(latitude: 40.64944139, longitude: -74.34758901),   // Westfield  40.649441391496225, -74.34758901567885
        "AV": CLLocationCoordinate2D(latitude: 40.5778386, longitude: -74.2773454),   // Avenale 40.57783860099064, -74.27734540034069
        "FW": CLLocationCoordinate2D(latitude: 40.64061996, longitude: -74.384423727),   // Fanwood  40.64061996072567, -74.38442372790603
        "GW": CLLocationCoordinate2D(latitude: 40.65255335, longitude: -74.325004422),   // Garwood 40.65255335293603, -74.3250044226773
        "NE": CLLocationCoordinate2D(latitude: 40.62921816688, longitude: -74.403226634),   // Netherwood  40.62921816688348, -74.40322663407635
        "LS": CLLocationCoordinate2D(latitude: 40.32654188, longitude: -74.040546829),   // Little Silver 40.32654188152892, -74.04054682918307
        "MK": CLLocationCoordinate2D(latitude: 40.3086, longitude: -74.0253),   // Monmouth Park
        "HZ": CLLocationCoordinate2D(latitude: 40.41515409, longitude: -74.190629424),   // Hazlet 40.41515409414224, -74.19062942410835
        "MI": CLLocationCoordinate2D(latitude: 40.39082051, longitude: -74.116794),   // Middletown 40.39082051439342, -74.11679433408341
        "WB": CLLocationCoordinate2D(latitude: 40.5559, longitude: -74.2780),   // Woodbridge
        "RB": CLLocationCoordinate2D(latitude: 40.348271404, longitude: -74.074151249),   // Red Banka 40.34827140444035, -74.0741512494248
        "PE": CLLocationCoordinate2D(latitude: 40.509372, longitude: -74.27381259),   // 40.509372943783205, -74.27381259301205
        "CH": CLLocationCoordinate2D(latitude: 40.48490168, longitude: -74.2804993),   // South Amboy is mislabelled as Cherry Hill 40.48490168088479, -74.28049932024226
        "AM": CLLocationCoordinate2D(latitude: 40.419773943, longitude: -74.22209923),   // Aberdeen-Matawan - 40.41977394340468, -74.22209923287113
        
        // Additional NJ Transit stations from STATION_CODES.txt
        "AH": CLLocationCoordinate2D(latitude: 40.2301, longitude: -74.0063),   // Allenhurst
        "AP": CLLocationCoordinate2D(latitude: 40.2202, longitude: -74.0120),   // Asbury Park
        "BB": CLLocationCoordinate2D(latitude: 40.1929, longitude: -74.0218),   // Bradley Beach
        "BS": CLLocationCoordinate2D(latitude: 40.1784, longitude: -74.0276),   // Belmar
        "LA": CLLocationCoordinate2D(latitude: 40.1530, longitude: -74.0340),   // Spring Lake
        "SQ": CLLocationCoordinate2D(latitude: 40.1057, longitude: -74.0500),   // Manasquan
        "PP": CLLocationCoordinate2D(latitude: 40.0917, longitude: -74.0680),   // Point Pleasant Beach
        "BH": CLLocationCoordinate2D(latitude: 40.0585, longitude: -74.1066),   // Bay Head
        "SC": CLLocationCoordinate2D(latitude: 40.7612, longitude: -74.0758),   // Secaucus Concourse (same as SE/TS)
        "TS": CLLocationCoordinate2D(latitude: 40.7612, longitude: -74.0758),   // Secaucus Lower Lvl (same location)
        "BW": CLLocationCoordinate2D(latitude: 40.561009, longitude: -74.55175689),   // Bridgewater 40.56100944598027, -74.55175688984208
        "SM": CLLocationCoordinate2D(latitude: 40.56608, longitude: -74.6138659),   // Somerville 40.56608372758163, -74.61386593713499
        "XC": CLLocationCoordinate2D(latitude: 40.6559, longitude: -74.3004),   // Cranford
        "RL": CLLocationCoordinate2D(latitude: 40.6642, longitude: -74.2687),   // Roselle Park
        "RW": CLLocationCoordinate2D(latitude: 40.9808, longitude: -74.1168),   // Ridgewood
        "RS": CLLocationCoordinate2D(latitude: 40.9808, longitude: -74.1168),   // Glen Rock Main Line
        "UF": CLLocationCoordinate2D(latitude: 40.9956, longitude: -74.1115),   // Hohokus
        "WK": CLLocationCoordinate2D(latitude: 41.0108, longitude: -74.1267),   // Waldwick
        "17": CLLocationCoordinate2D(latitude: 41.0615, longitude: -74.1456),   // Ramsey Route 17
        "RY": CLLocationCoordinate2D(latitude: 41.0571, longitude: -74.1413),   // Ramsey Main St
        "MZ": CLLocationCoordinate2D(latitude: 41.0886, longitude: -74.1438),   // Mahwah
        "SF": CLLocationCoordinate2D(latitude: 41.1144, longitude: -74.1496),   // Suffern
        "XG": CLLocationCoordinate2D(latitude: 41.1568, longitude: -74.1937),   // Sloatsburg
        "TC": CLLocationCoordinate2D(latitude: 41.1970, longitude: -74.1885),   // Tuxedo
        "RM": CLLocationCoordinate2D(latitude: 41.3098, longitude: -74.1526),   // Harriman
        "CB": CLLocationCoordinate2D(latitude: 41.4446, longitude: -74.2452),   // Campbell Hall
        "CW": CLLocationCoordinate2D(latitude: 41.4426, longitude: -74.1351),   // Salisbury Mills-Cornwall
        "OS": CLLocationCoordinate2D(latitude: 41.4783, longitude: -74.5336),   // Otisville
        "PO": CLLocationCoordinate2D(latitude: 41.3753, longitude: -74.6897),   // Port Jervis
       
        
        // Bergen County Line (Main Line) - New GPS coordinates
        "KG": CLLocationCoordinate2D(latitude: 40.8123, longitude: -74.1246),   // Kingsland
        "LN": CLLocationCoordinate2D(latitude: 40.8123, longitude: -74.1246),   // Lyndhurst
        "DL": CLLocationCoordinate2D(latitude: 40.8180, longitude: -74.1370),   // Delawanna
        "PS": CLLocationCoordinate2D(latitude: 40.8570, longitude: -74.1294),   // Passaic
        "IF": CLLocationCoordinate2D(latitude: 40.8584, longitude: -74.1637),   // Clifton
        "RN": CLLocationCoordinate2D(latitude: 40.9166, longitude: -74.1710),   // Paterson
        "HW": CLLocationCoordinate2D(latitude: 40.9494, longitude: -74.1527),   // Hawthorne
        "GR": CLLocationCoordinate2D(latitude: 40.9633, longitude: -74.1269),   // Glen Rock
        "WA": CLLocationCoordinate2D(latitude: 41.0108, longitude: -74.1267),   // Waldwick
        "AL": CLLocationCoordinate2D(latitude: 41.0312, longitude: -74.1306),   // Allendale
        "MH": CLLocationCoordinate2D(latitude: 41.0886, longitude: -74.1438),   // Mahwah
        /*
        // Bergen County Line (Ridgewood Branch)
        "RT": CLLocationCoordinate2D(latitude: 40.8267, longitude: -74.1069),   // Rutherford
        "WE": CLLocationCoordinate2D(latitude: 40.8356, longitude: -74.0989),   // Wesmont
        "GA": CLLocationCoordinate2D(latitude: 40.8815, longitude: -74.1133),   // Garfield
        "PLD": CLLocationCoordinate2D(latitude: 40.8879, longitude: -74.1202),  // Plauderville
        "BW": CLLocationCoordinate2D(latitude: 40.9188, longitude: -74.1316),   // Broadway (Fair Lawn)
        "GB": CLLocationCoordinate2D(latitude: 40.9595, longitude: -74.1329),   // Glen Rock–Boro Hall
        
        // Pascack Valley Line
        "WR": CLLocationCoordinate2D(latitude: 40.8449, longitude: -74.0883),   // Wood-Ridge
        "TB": CLLocationCoordinate2D(latitude: 40.8602, longitude: -74.0639),   // Teterboro
        "ES": CLLocationCoordinate2D(latitude: 40.8836, longitude: -74.0436),   // Essex Street
        "AN": CLLocationCoordinate2D(latitude: 40.8944, longitude: -74.0447),   // Anderson Street
        "NBL": CLLocationCoordinate2D(latitude: 40.9079, longitude: -74.0384),  // New Bridge Landing
        "RE": CLLocationCoordinate2D(latitude: 40.9264, longitude: -74.0413),   // River Edge
        "OR": CLLocationCoordinate2D(latitude: 40.9545, longitude: -74.0369),   // Oradell
        "EM": CLLocationCoordinate2D(latitude: 40.9758, longitude: -74.0281),   // Emerson
        "WW": CLLocationCoordinate2D(latitude: 40.9909, longitude: -74.0336),   // Westwood
        "WL": CLLocationCoordinate2D(latitude: 41.0230, longitude: -74.0569),   // Woodcliff Lake
        "PR": CLLocationCoordinate2D(latitude: 41.0375, longitude: -74.0406),   // Park Ridge
        "MV": CLLocationCoordinate2D(latitude: 41.0521, longitude: -74.0372),   // Montvale
        "PER": CLLocationCoordinate2D(latitude: 41.0595, longitude: -74.0197),  // Pearl River, NY
        "NU": CLLocationCoordinate2D(latitude: 41.0869, longitude: -74.0130),   // Nanuet, NY
        "SV": CLLocationCoordinate2D(latitude: 41.1130, longitude: -74.0436),   // Spring Valley, NY
        
        // Port Jervis Line (from Suffern)
        "SL": CLLocationCoordinate2D(latitude: 41.1568, longitude: -74.1937),   // Sloatsburg, NY
        "TX": CLLocationCoordinate2D(latitude: 41.1970, longitude: -74.1885),   // Tuxedo, NY
        "HR": CLLocationCoordinate2D(latitude: 41.3098, longitude: -74.1526),   // Harriman, NY
        "SM": CLLocationCoordinate2D(latitude: 41.4426, longitude: -74.1351),   // Salisbury Mills–Cornwall, NY
        "MD": CLLocationCoordinate2D(latitude: 41.4459, longitude: -74.4222),   // Middletown, NY
        "OT": CLLocationCoordinate2D(latitude: 41.4783, longitude: -74.5336),   // Otisville, NY
        "PJV": CLLocationCoordinate2D(latitude: 41.3746, longitude: -74.6927),  // Port Jervis, NY
        
        // Morris & Essex Line / Gladstone Branch - Updated GPS
        "ML": CLLocationCoordinate2D(latitude: 40.725667, longitude: -74.303694), // Millburn
        "ST": CLLocationCoordinate2D(latitude: 40.7099, longitude: -74.3546),   // Summit
        "ND": CLLocationCoordinate2D(latitude: 40.7418, longitude: -74.1698),   // Newark Broad Street
        "DV": CLLocationCoordinate2D(latitude: 40.8837, longitude: -74.4753),   // Denville
        "PE": CLLocationCoordinate2D(latitude: 40.7052, longitude: -74.6550),   // Peapack
        
        // Montclair-Boonton Line - Updated GPS
        "MHT": CLLocationCoordinate2D(latitude: 40.857538, longitude: -74.202493), // Montclair Heights
        "MS": CLLocationCoordinate2D(latitude: 40.8695, longitude: -74.1975),   // Montclair State University
        "DO": CLLocationCoordinate2D(latitude: 40.883417, longitude: -74.555884), // Dover
        "BO": CLLocationCoordinate2D(latitude: 40.903378, longitude: -74.407733)  // Boonton
        */
    ]
    
    // Supported departure stations - Updated to match backend
    static let departureStations: [(name: String, code: String)] = [
        ("New York Penn Station", "NY"),
        ("Hoboken", "HB"),
        ("Metropark", "MP"),
        ("Princeton Junction", "PJ"),
        ("Hamilton", "HL"),
        ("Trenton", "TR"),
        ("Long Branch", "LB"),
        ("Plainfield", "PF"),  // Changed from PL to PF
        ("Dunellen", "DN"),
        ("Raritan", "RA"),
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
