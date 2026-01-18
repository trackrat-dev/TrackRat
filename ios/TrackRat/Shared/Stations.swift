import Foundation
import CoreLocation
import MapKit

struct Stations {
    static let all: [String] = [
        // Major Hub Stations
        "New York Penn Station", "Newark Penn Station", "Hoboken",
        "Secaucus Upper Lvl", "Secaucus Lower Lvl",
        "Trenton", "Philadelphia",
        
        // Northeast Corridor Line
        "Princeton Junction", "Princeton", "Hamilton",
        "Metropark", "New Brunswick", "Edison", "Metuchen",
        "Rahway", "Linden", "Elizabeth", "North Elizabeth",
        "Newark Airport", "Newark Broad Street",
        
        // North Jersey Coast Line  
        "Woodbridge", "Perth Amboy", "South Amboy", "Aberdeen-Matawan",
        "Hazlet", "Middletown", "Red Bank", "Little Silver",
        "Monmouth Park", "Long Branch", "Elberon", "Allenhurst",
        "Asbury Park", "Bradley Beach", "Belmar", "Spring Lake",
        "Manasquan", "Point Pleasant Beach", "Bay Head",
        
        // Morris & Essex Lines
        "Summit", "Chatham", "Madison", "Convent Station",
        "Morristown", "Morris Plains", "Denville", "Dover",
        "Mount Tabor", "Mount Arlington", "Lake Hopatcong", "Netcong",
        "Mount Olive", "Hackettstown", "Millburn", "Short Hills",
        "South Orange", "Maplewood", "Orange", "East Orange",
        "Brick Church", "Highland Avenue", "Mountain View",
        
        // Gladstone Branch
        "Murray Hill", "New Providence", "Berkeley Heights", "Gillette",
        "Stirling", "Millington", "Lyons", "Basking Ridge",
        "Bernardsville", "Far Hills", "Peapack", "Gladstone",
        
        // Raritan Valley Line
        "Union", "Roselle Park", "Cranford", "Garwood", "Westfield",
        "Fanwood", "Netherwood", "Plainfield", "Dunellen",
        "Bound Brook", "Bridgewater", "Somerville", "Raritan",
        "High Bridge", "Annandale", "Lebanon", "White House",
        "North Branch",
        
        // Main/Bergen County Lines
        "Kingsland", "Lyndhurst", "Delawanna", "Passaic", "Clifton",
        "Paterson", "Hawthorne", "Glen Rock Main Line", "Glen Rock Boro Hall",
        "Ridgewood", "Ho-Ho-Kus", "Waldwick", "Allendale",
        "Ramsey Main St", "Ramsey Route 17", "Mahwah", "Suffern",
        "Fair Lawn-Broadway", "Radburn Fair Lawn", "Garfield", "Plauderville",
        "Rutherford", "Wesmont",
        
        // Montclair-Boonton Line
        "Bloomfield", "Glen Ridge", "Bay Street", "Walnut Street",
        "Montclair Heights", "Montclair State U", "Upper Montclair",
        "Mountain Avenue", "Watchung Avenue", "Watsessing Avenue",
        "Little Falls", "Wayne-Route 23", "Mountain Station",
        "Boonton", "Mountain Lakes", "Lincoln Park", "Towaco",
        "Great Notch",
        
        // Pascack Valley Line
        "Wood Ridge", "Teterboro", "Essex Street", "Anderson Street",
        "New Bridge Landing", "River Edge", "Oradell", "Emerson",
        "Westwood", "Hillsdale", "Woodcliff Lake", "Park Ridge",
        "Montvale", "Pearl River", "Nanuet", "Spring Valley",
        
        // Port Jervis Line
        "Sloatsburg", "Tuxedo", "Harriman", "Salisbury Mills-Cornwall",
        "Campbell Hall", "Otisville", "Port Jervis",
        
        // Additional NJ Transit Stations
        "Avenel", "Jersey Avenue",

        // PATH Stations
        "Newark PATH", "Harrison PATH", "Journal Square",
        "Grove Street", "Exchange Place", "Newport",
        "Hoboken PATH", "Christopher Street", "9th Street",
        "14th Street", "23rd Street", "33rd Street",
        "World Trade Center",

        // Pennsylvania Stations (Keystone Service)
        "Middletown PA", "Elizabethtown", "Mount Joy", "Parkesburg",
        "Coatesville", "Downingtown", "Exton", "Paoli",
        
        // Amtrak Northeast Corridor
        "Boston South", "Boston Back Bay", "Providence", "Kingston", "Westerly",
        "New London", "Old Saybrook", "New Haven", "Bridgeport", "Stamford",
        "Baltimore Station", "BWI Thurgood Marshall Airport",
        "Washington Union Station", "Wilmington Station",
        
        // Additional Amtrak Stations
        "Hartford", "Meriden", "Wallingford", "Windsor Locks", "Springfield",
        "Claremont", "Dover NH", "Durham-UNH", "Exeter",
        "New Carrollton", "Aberdeen", "Alexandria", "Charlottesville",
        "Lorton", "Manassas", "Norfolk", "Richmond Main Street", "Richmond Staples Mill Road", "Roanoke",
        "Harrisburg", "Lancaster",
        
        // Southeast Amtrak Stations (Silver Star/Meteor and Carolinian/Piedmont routes)
        "Charlotte", "Raleigh", "Greensboro", "Durham", "Rocky Mount", "Wilson",
        "Cary", "Southern Pines", "High Point", "Salisbury", "Gastonia", "Hamlet",
        "Selma-Smithfield", "Petersburg",
        "Charleston", "Spartanburg", "Greenville", "Kingstree", "Florence", "Dillon", "Clemson",
        "Savannah", "Atlanta", "Jesup", "Gainesville GA", "Toccoa",
        "Jacksonville", "Miami", "Orlando", "Tampa", "Fort Lauderdale", "West Palm Beach",
        "Kissimmee", "Lakeland", "Winter Park FL", "DeLand", "Sanford FL", "Hollywood FL",
        "Delray Beach", "Waldo", "Ocala", "Winter Haven", "Palatka", "Thurmond"
    ].sorted()
    
    // Station name to code mapping - Updated to match backend STATION_CODES.txt
    static let stationCodes: [String: String] = [
        // NJ Transit stations from authoritative STATION_CODES.txt
        "New York Penn Station": "NY",
        "Newark Penn Station": "NP",
        "Secaucus Upper Lvl": "SE",
        "Secaucus Lower Lvl": "TS",
        "Woodbridge": "WB",
        "Metropark": "MP",
        "New Brunswick": "NB",
        "Princeton Junction": "PJ",
        "Princeton": "PR",
        "Trenton": "TR",
        "Trenton Transit Center": "TR",
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
        "Walnut Street": "WA",
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
        "Ridgewood": "RW",
        "Ho-Ho-Kus": "UF",
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

        // PATH stations (3-char codes to match API constraints)
        "Newark PATH": "PNK",
        "Harrison PATH": "PHR",
        "Journal Square": "PJS",
        "Grove Street": "PGR",
        "Exchange Place": "PEX",
        "Newport": "PNP",
        "Hoboken PATH": "PHO",
        "Christopher Street": "PCH",
        "9th Street": "P9S",
        "14th Street": "P14",
        "23rd Street": "P23",
        "33rd Street": "P33",
        "World Trade Center": "PWC",

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
        "Manassas": "MSS",
        "Norfolk": "NFK",
        "Richmond Main Street": "RVM",
        "Richmond Staples Mill Road": "RVR",
        "Roanoke": "RNK",
        "Harrisburg": "HAR",
        "Lancaster": "LNC",
        "Kingston": "KIN",
        "Westerly": "WLY",
        
        // Southeast Amtrak stations
        "Charlotte": "CLT",
        "Raleigh": "RGH",
        "Greensboro": "GRB",
        "Durham": "DNC",
        "Rocky Mount": "RMT",
        "Wilson": "WLN",
        "Cary": "CAR",
        "Southern Pines": "SOU",
        "High Point": "HPT",
        "Salisbury": "SAL",
        "Gastonia": "GAS",
        "Hamlet": "HAM",
        "Selma-Smithfield": "SEL",
        "Petersburg": "PTB",
        "Charleston": "CHS",
        "Spartanburg": "SPB",
        "Greenville": "GVL",
        "Kingstree": "KTR",
        "Florence": "FLO",
        "Dillon": "DIL",
        "Clemson": "CSN",
        "Savannah": "SAV",
        "Atlanta": "ATL",
        "Jesup": "JES",
        "Gainesville GA": "GAI",
        "Toccoa": "TOC",
        "Jacksonville": "JAX",
        "Miami": "MIA",
        "Orlando": "ORL",
        "Tampa": "TPA",
        "Fort Lauderdale": "FTL",
        "West Palm Beach": "WPB",
        "Kissimmee": "KIS",
        "Lakeland": "LKL",
        "Winter Park FL": "WPK",
        "DeLand": "DLD",
        "Sanford FL": "SAN",
        "Hollywood FL": "HLW",
        "Delray Beach": "DLB",
        "Waldo": "WLD",
        "Ocala": "OCA",
        "Winter Haven": "WTH",
        "Palatka": "PAL",
        "Thurmond": "THU"
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
        "MSS": CLLocationCoordinate2D(latitude: 38.7511, longitude: -77.4752),  // Manassas, VA
        "NFK": CLLocationCoordinate2D(latitude: 36.8583, longitude: -76.2876),  // Norfolk, VA
        "RVR": CLLocationCoordinate2D(latitude: 37.61741, longitude: -77.49755),  // Richmond Staples Mill Road, VA
        "RVM": CLLocationCoordinate2D(latitude: 37.6143, longitude: -77.4966),  // Richmond Main Street, VA
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
        "NZ": CLLocationCoordinate2D(latitude: 40.680341475, longitude: -74.2061729014),   // North Elizabeth 40.68034147548386, -74.20617290142303
        
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
        "PP": CLLocationCoordinate2D(latitude: 40.0928885, longitude: -74.048128),   // Point Pleasant Beach 40.092888539579086, -74.04812800404557
        "BH": CLLocationCoordinate2D(latitude: 40.0771313, longitude: -74.046189485),   // Bay Head 40.077131308867386, -74.04618948520402
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
        "CW": CLLocationCoordinate2D(latitude: 41.436533265, longitude: -74.101601729),   // Salisbury Mills-Cornwall 41.436533265171164, -74.10160172915069
        "OS": CLLocationCoordinate2D(latitude: 41.4783, longitude: -74.5336),   // Otisville
        "PO": CLLocationCoordinate2D(latitude: 41.3753, longitude: -74.6897),   // Port Jervis
        "MD": CLLocationCoordinate2D(latitude: 41.45748, longitude: -74.370408),   // Middletown NY 41.4574804003699, -74.37040800377328
       
        
        // Bergen County Line (Main Line) - New GPS coordinates
        "KG": CLLocationCoordinate2D(latitude: 40.8123, longitude: -74.1246),   // Kingsland
        "LN": CLLocationCoordinate2D(latitude: 40.8123, longitude: -74.1246),   // Lyndhurst
        "DL": CLLocationCoordinate2D(latitude: 40.8318187, longitude: -74.1314617),   // Delawanna 40.83181871791698, -74.13146171567368
        "PS": CLLocationCoordinate2D(latitude: 40.8494377, longitude: -74.133866768),   // Passaic 40.84943770250315, -74.13386676844108
        "IF": CLLocationCoordinate2D(latitude: 40.867912098, longitude: -74.15326859),   // Clifton 40.86791209797451, -74.15326859173946
        "RN": CLLocationCoordinate2D(latitude: 40.9166, longitude: -74.1710),   // Paterson
        "HW": CLLocationCoordinate2D(latitude: 40.942528946, longitude: -74.152399138),   // Hawthorne 40.94252894598973, -74.15239913775797
        "GR": CLLocationCoordinate2D(latitude: 40.9633, longitude: -74.1269),   // Glen Rock
        "AL": CLLocationCoordinate2D(latitude: 41.0312, longitude: -74.1306),   // Allendale
        
        // Bergen County Line (Ridgewood Branch)
        "RF": CLLocationCoordinate2D(latitude: 40.8267, longitude: -74.1069),   // Rutherford
        "WM": CLLocationCoordinate2D(latitude: 40.8356, longitude: -74.0989),   // Wesmont
        "GD": CLLocationCoordinate2D(latitude: 40.8815, longitude: -74.1133),   // Garfield
        "PL": CLLocationCoordinate2D(latitude: 40.8879, longitude: -74.1202),  // Plauderville
        "BF": CLLocationCoordinate2D(latitude: 40.9188, longitude: -74.1316),   // Broadway (Fair Lawn)
        "GK": CLLocationCoordinate2D(latitude: 40.9595, longitude: -74.1329),   // Glen Rock–Boro Hall
        "FZ": CLLocationCoordinate2D(latitude: 40.939645, longitude: -74.12154647),   // Radburn Fiar Lawn 40.93964512609563, -74.12154647334052
        
        // Pascack Valley Line
        "WR": CLLocationCoordinate2D(latitude: 40.8449, longitude: -74.0883),   // Wood-Ridge
        "TE": CLLocationCoordinate2D(latitude: 40.8602, longitude: -74.0639),   // Teterboro
        "EX": CLLocationCoordinate2D(latitude: 40.8836, longitude: -74.0436),   // Essex Street
        "AS": CLLocationCoordinate2D(latitude: 40.8944, longitude: -74.0447),   // Anderson Street
        "NH": CLLocationCoordinate2D(latitude: 40.9079, longitude: -74.0384),  // New Bridge Landing
        "RG": CLLocationCoordinate2D(latitude: 40.9264, longitude: -74.0413),   // River Edge
        "OD": CLLocationCoordinate2D(latitude: 40.9545, longitude: -74.0369),   // Oradell
        "EN": CLLocationCoordinate2D(latitude: 40.9758, longitude: -74.0281),   // Emerson
        "HD": CLLocationCoordinate2D(latitude: 41.00241888, longitude: -74.040956),   // Hillsdale 41.002418880662276, -74.0409560175139
        "WW": CLLocationCoordinate2D(latitude: 40.9909, longitude: -74.0336),   // Westwood
        "WL": CLLocationCoordinate2D(latitude: 41.0230, longitude: -74.0569),   // Woodcliff Lake
        "PV": CLLocationCoordinate2D(latitude: 41.0375, longitude: -74.0406),   // Park Ridge
        "ZM": CLLocationCoordinate2D(latitude: 41.0521, longitude: -74.0372),   // Montvale
        "PQ": CLLocationCoordinate2D(latitude: 41.0595, longitude: -74.0197),  // Pearl River, NY
        "NN": CLLocationCoordinate2D(latitude: 41.0869, longitude: -74.0130),   // Nanuet, NY
        "SV": CLLocationCoordinate2D(latitude: 41.1130, longitude: -74.0436),   // Spring Valley, NY
        /*
        // Port Jervis Line (from Suffern)
        "SL": CLLocationCoordinate2D(latitude: 41.1568, longitude: -74.1937),   // Sloatsburg, NY
        "TX": CLLocationCoordinate2D(latitude: 41.1970, longitude: -74.1885),   // Tuxedo, NY
        "HR": CLLocationCoordinate2D(latitude: 41.3098, longitude: -74.1526),   // Harriman, NY
        "SM": CLLocationCoordinate2D(latitude: 41.4426, longitude: -74.1351),   // Salisbury Mills–Cornwall, NY
        "MD": CLLocationCoordinate2D(latitude: 41.4459, longitude: -74.4222),   // Middletown, NY
        "OT": CLLocationCoordinate2D(latitude: 41.4783, longitude: -74.5336),   // Otisville, NY
        "PJV": CLLocationCoordinate2D(latitude: 41.3746, longitude: -74.6927),  // Port Jervis, NY
        */
        
        // Morris & Essex Line / Gladstone Branch - Updated GPS
        "MB": CLLocationCoordinate2D(latitude: 40.7256749, longitude: -74.3036915), // Millburn 40.72567492520069, -74.30369154451178
        "BU": CLLocationCoordinate2D(latitude: 40.765656, longitude: -74.21909888), // Brick Church 40.76565601951543, -74.2190988886858
        "EO": CLLocationCoordinate2D(latitude: 40.76089825, longitude: -74.2107669), // East Orange 40.7608982536601, -74.2107669015754
        "OG": CLLocationCoordinate2D(latitude: 40.771899, longitude: -74.2331103), // Orange 40.77189922949034, -74.23311030419556
        "HI": CLLocationCoordinate2D(latitude: 40.7668668, longitude: -74.24370939), // Highland Avenue 40.76686685018996, -74.24370939011305
        "MT": CLLocationCoordinate2D(latitude: 40.7553832255, longitude: -74.2529918156), // Mountain Station 40.75538322553456, -74.25299181567573
        "SO": CLLocationCoordinate2D(latitude: 40.74598917, longitude: -74.260345), // South Orange 40.745989173313006, -74.26034504763733
        "MW": CLLocationCoordinate2D(latitude: 40.731052531, longitude: -74.275368), // Maplewood 40.73105253148527, -74.27536805310443
        "RT": CLLocationCoordinate2D(latitude: 40.725183794, longitude: -74.323772644), // Short Hills 40.72518379457189, -74.32377264451166
        "CM": CLLocationCoordinate2D(latitude: 40.740191597, longitude: -74.384824495), // Chatham 40.740191597353025, -74.38482449543406
        "MA": CLLocationCoordinate2D(latitude: 40.757040225, longitude: -74.415224486), // Madison 40.75704022512916, -74.41522448684061
        "CN": CLLocationCoordinate2D(latitude: 40.778934247, longitude: -74.4433639138), // Convent Station 40.778934247012046, -74.4433639138298
        "MR": CLLocationCoordinate2D(latitude: 40.7971792932, longitude: -74.474198069), // Morristown 40.797179293283016, -74.47419806965395
        "MX": CLLocationCoordinate2D(latitude: 40.828603425, longitude: -74.4782465138), // Morris Plains 40.82860342578615, -74.47824651382828
        "TB": CLLocationCoordinate2D(latitude: 40.875882396, longitude: -74.481767307079), // Mount Tabor 40.87588239601982, -74.48176730707961
        "ST": CLLocationCoordinate2D(latitude: 40.716664548, longitude: -74.3576803),   // Summit  40.71666454825247, -74.35768030218206
        "ND": CLLocationCoordinate2D(latitude: 40.7418, longitude: -74.1698),   // Newark Broad Street
        "DV": CLLocationCoordinate2D(latitude: 40.8837, longitude: -74.4753),   // Denville
        "PC": CLLocationCoordinate2D(latitude: 40.7052, longitude: -74.6550),   // Peapack
        "NV": CLLocationCoordinate2D(latitude: 40.71207692699218, longitude: -74.3865321865084),   // New Providence
	"MH": CLLocationCoordinate2D(latitude: 40.69498340590801, longitude: -74.40318790190945),   // Murray Hill
	"BY": CLLocationCoordinate2D(latitude: 40.68239885512966, longitude: -74.44270357307379),   // Berkeley Heights
	"GI": CLLocationCoordinate2D(latitude: 40.67823715581587, longitude: -74.4682388381484),   // Gillette
	"SG": CLLocationCoordinate2D(latitude: 40.67468000927561, longitude: -74.49339662637885),   // Stirling
	"GO": CLLocationCoordinate2D(latitude: 40.67356917492084, longitude: -74.52362581672504),   // Millington
	"LY": CLLocationCoordinate2D(latitude: 40.68483490714862, longitude: -74.54952358841823),   // Lyons
	"BI": CLLocationCoordinate2D(latitude: 40.711327481896824, longitude: -74.55527314719112),   // Basking Ridge
	"BV": CLLocationCoordinate2D(latitude: 40.716945533975355, longitude: -74.57125871486349),   // Bernardsville
	"FH": CLLocationCoordinate2D(latitude: 40.685599814033345, longitude: -74.6337807442374),   // Far Hills
         // Montclair-Boonton Line - Updated GPS
	"WT": CLLocationCoordinate2D(latitude: 40.78291485164349, longitude: -74.1985652261131),   // Watsessing Ave
	"BM": CLLocationCoordinate2D(latitude: 40.792818916372745, longitude: -74.19999693101497),   // Bloomfield
	"GG": CLLocationCoordinate2D(latitude: 40.800468228026226, longitude: -74.20449363776208),   // Glenn Ridge
	"MC": CLLocationCoordinate2D(latitude: 40.808188091934255, longitude: -74.20858344266387),   // Bay Street
	"WA": CLLocationCoordinate2D(latitude: 40.81716518884647, longitude: -74.20955720561183),   // Walnut street
	"WG": CLLocationCoordinate2D(latitude: 40.82971140825341, longitude: -74.20705692883614),   // Watchung
	"UM": CLLocationCoordinate2D(latitude: 40.8420714374858, longitude: -74.20941682888828),   // Upper Montclair
	"MS": CLLocationCoordinate2D(latitude: 40.84886257848428, longitude: -74.20572784233256),   // Mountain Avenue
	"HS": CLLocationCoordinate2D(latitude: 40.85778632525093, longitude: -74.20258147801873), // Montclair Heights
	"UV": CLLocationCoordinate2D(latitude: 40.869877328760076, longitude: -74.1973970868374),   // Montclair State University
	"FA": CLLocationCoordinate2D(latitude: 40.880597100429924, longitude: -74.23527448868244),   // Little Falls
	"23": CLLocationCoordinate2D(latitude: 40.90014887124657, longitude: -74.25698821936236),   // Wayne Rt 23
	"MV": CLLocationCoordinate2D(latitude: 40.913900511412734, longitude: -74.26769562647546),   // Mountain View
	"LP": CLLocationCoordinate2D(latitude: 40.924111086002696, longitude: -74.3018546214956),   // Lincoln Park
	"TO": CLLocationCoordinate2D(latitude: 40.9231266856343, longitude: -74.34342958314522),   // Towaco
	"DO": CLLocationCoordinate2D(latitude: 40.88350334976419, longitude: -74.55552377794903), // Dover
	"ML": CLLocationCoordinate2D(latitude: 40.88593889355365, longitude: -74.43361065984737),   // Mountain Lakes
	"BN": CLLocationCoordinate2D(latitude: 40.90337853269087, longitude: -74.4077830932363),  // Boonton

	"HV": CLLocationCoordinate2D(latitude: 40.89659277960788, longitude: -74.63275424450669),  // Mount Arlington
	"HP": CLLocationCoordinate2D(latitude: 40.90408226231908, longitude: -74.66561057518699),  // Lake Hopatcong
	"NT": CLLocationCoordinate2D(latitude: 40.897623899501745, longitude: -74.70742034940882),  // Netcong
	"OL": CLLocationCoordinate2D(latitude: 40.90739863717089, longitude: -74.73084167518675),  // Mount Olive
	"HQ": CLLocationCoordinate2D(latitude: 40.851897810525074, longitude: -74.83489363939469),  // Hackettstown
	"GL": CLLocationCoordinate2D(latitude: 40.72024745131554, longitude: -74.66637267519233),  // Gladstone
	"OR": CLLocationCoordinate2D(latitude: 40.592500971292836, longitude: -74.68422484941766),  // North Branch
	"WH": CLLocationCoordinate2D(latitude: 40.615644648058776, longitude: -74.77069208869021),  //  White House
	"ON": CLLocationCoordinate2D(latitude: 40.63685173471974, longitude: -74.83598194792847),  // Lebanon
	"AN": CLLocationCoordinate2D(latitude: 40.645122790094504, longitude: -74.87893201752432),  // Annandale
	"HG": CLLocationCoordinate2D(latitude: 40.666798999008535, longitude: -74.89591082917332),  // High Bridge

        // PATH stations - synced with backend_v2/src/trackrat/config/stations.py
        "PNK": CLLocationCoordinate2D(latitude: 40.7365, longitude: -74.1640),   // Newark PATH
        "PHR": CLLocationCoordinate2D(latitude: 40.7393, longitude: -74.1560),   // Harrison PATH
        "PJS": CLLocationCoordinate2D(latitude: 40.7328, longitude: -74.0630),   // Journal Square
        "PGR": CLLocationCoordinate2D(latitude: 40.7197, longitude: -74.0434),   // Grove Street
        "PEX": CLLocationCoordinate2D(latitude: 40.7167, longitude: -74.0333),   // Exchange Place
        "PNP": CLLocationCoordinate2D(latitude: 40.7265, longitude: -74.0337),   // Newport
        "PHO": CLLocationCoordinate2D(latitude: 40.7348, longitude: -74.0280),   // Hoboken PATH
        "PCH": CLLocationCoordinate2D(latitude: 40.7329, longitude: -74.0067),   // Christopher Street
        "P9S": CLLocationCoordinate2D(latitude: 40.7340, longitude: -73.9997),   // 9th Street
        "P14": CLLocationCoordinate2D(latitude: 40.7376, longitude: -73.9967),   // 14th Street
        "P23": CLLocationCoordinate2D(latitude: 40.7428, longitude: -73.9930),   // 23rd Street
        "P33": CLLocationCoordinate2D(latitude: 40.7487, longitude: -73.9880),   // 33rd Street
        "PWC": CLLocationCoordinate2D(latitude: 40.7118, longitude: -74.0101),   // World Trade Center

        // Additional Amtrak stations (Southeast/South)
        "ATL": CLLocationCoordinate2D(latitude: 33.7995643615723, longitude: -84.3917846679688),   // Atlanta, GA
        "CHS": CLLocationCoordinate2D(latitude: 32.8755340576172, longitude: -79.9989013671875),   // Charleston, SC
        "CSN": CLLocationCoordinate2D(latitude: 34.6910, longitude: -82.8325),   // Clemson, SC
        "CLT": CLLocationCoordinate2D(latitude: 35.2411460876465, longitude: -80.8236389160156),   // Charlotte, NC
        "DIL": CLLocationCoordinate2D(latitude: 34.418285369873, longitude: -79.3717575073242),    // Dillon, SC
        "DLB": CLLocationCoordinate2D(latitude: 26.4551792144775, longitude: -80.092529296875),    // Delray Beach, FL
        "DLD": CLLocationCoordinate2D(latitude: 29.0168342590332, longitude: -81.3524551391602),   // DeLand, FL
        "DNC": CLLocationCoordinate2D(latitude: 35.9970359802246, longitude: -78.9072265625),     // Durham, NC
        "FLO": CLLocationCoordinate2D(latitude: 34.1988182067871, longitude: -79.7570953369141),   // Florence, SC
        "FTL": CLLocationCoordinate2D(latitude: 26.1196136474609, longitude: -80.1701889038086),   // Fort Lauderdale, FL
        "GAS": CLLocationCoordinate2D(latitude: 35.2683563232422, longitude: -81.1639785766602),   // Gastonia, NC
        "HAM": CLLocationCoordinate2D(latitude: 34.8830718994141, longitude: -79.6984558105469),   // Hamlet, NC
        "HPT": CLLocationCoordinate2D(latitude: 35.9575080871582, longitude: -80.0058364868164),   // High Point, NC
        "JAX": CLLocationCoordinate2D(latitude: 30.3665771484375, longitude: -81.7246017456055),   // Jacksonville, FL
        "KIS": CLLocationCoordinate2D(latitude: 28.293270111084, longitude: -81.4048690795898),    // Kissimmee, FL
        "KTR": CLLocationCoordinate2D(latitude: 33.664379119873, longitude: -79.8290634155273),    // Kingstree, SC
        "LKL": CLLocationCoordinate2D(latitude: 28.04568, longitude: -81.95188),   // Lakeland, FL
        "MIA": CLLocationCoordinate2D(latitude: 25.8498477935791, longitude: -80.2580718994141),   // Miami, FL
        "ORL": CLLocationCoordinate2D(latitude: 28.5256938934326, longitude: -81.3817443847656),   // Orlando, FL
        "PTB": CLLocationCoordinate2D(latitude: 37.2416191101074, longitude: -77.4289703369141),   // Petersburg, VA
        "RGH": CLLocationCoordinate2D(latitude: 35.7795, longitude: -78.6382),                     // Raleigh, NC
        "RMT": CLLocationCoordinate2D(latitude: 35.9382, longitude: -77.7905),                     // Rocky Mount, NC
        "SAL": CLLocationCoordinate2D(latitude: 35.6740, longitude: -80.4842),                     // Salisbury, NC
        "SAV": CLLocationCoordinate2D(latitude: 32.0835, longitude: -81.0998),                     // Savannah, GA
        "SPB": CLLocationCoordinate2D(latitude: 34.9496, longitude: -81.9318),                     // Spartanburg, SC
        "TPA": CLLocationCoordinate2D(latitude: 27.9506, longitude: -82.4572),                     // Tampa, FL
        "WLN": CLLocationCoordinate2D(latitude: 35.7230682373047, longitude: -77.9082946777344),   // Wilson, NC
        "WPB": CLLocationCoordinate2D(latitude: 26.7153, longitude: -80.0534),                     // West Palm Beach, FL
        "WPK": CLLocationCoordinate2D(latitude: 28.5990, longitude: -81.3392),                     // Winter Park, FL
        "WTH": CLLocationCoordinate2D(latitude: 28.0222, longitude: -81.7323)                      // Winter Haven, FL
    ]
    
    // Supported departure stations - Updated to match backend
    static let departureStations: [(name: String, code: String)] = [
        // Northeast Corridor
        ("New York Penn Station", "NY"),
        ("Hoboken", "HB"),
        // PATH
        ("Hoboken PATH", "PHO"),
        ("World Trade Center", "PWC"),
        ("33rd Street", "P33"),
        ("Journal Square", "PJS"),
        ("Newark PATH", "PNK"),
        ("Metropark", "MP"),
        ("Princeton Junction", "PJ"),
        ("Hamilton", "HL"),
        ("Trenton", "TR"),
        ("Long Branch", "LB"),
        ("Plainfield", "PF"),  // Changed from PL to PF
        ("Dunellen", "DN"),
        ("Raritan", "RA"),
        ("Philadelphia", "PH"),
        ("Wilmington Station", "WI"),
        // Mid-Atlantic
        ("Baltimore Station", "BL"),
        ("Washington Union Station", "WS"),
        ("Richmond Staples Mill Road", "RVR"),
        // New England
        ("Springfield", "SPG"),
        // Southeast hubs
        ("Charlotte", "CLT"),
        ("Raleigh", "RGH"),
        ("Savannah", "SAV"),
        ("Jacksonville", "JAX"),
        ("Orlando", "ORL"),
        ("Tampa", "TPA"),
        ("Miami", "MIA"),
        ("Atlanta", "ATL")
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
    
    /// Returns the full station name for a given station code.
    /// Example: stationName(forCode: "NY") returns "New York Penn Station"
    static func stationName(forCode code: String) -> String? {
        return stationCodes.first(where: { $0.value == code })?.key
    }

    /// Smart display name that handles both station codes and station names.
    /// - For codes (e.g., "NY", "MP"): Returns the full station name
    /// - For names (e.g., "New York Penn Station"): Returns shortened version
    static func displayName(for input: String) -> String {
        // First, check if input is a station code
        if let fullName = stationName(forCode: input) {
            return shortenedDisplayName(for: fullName)
        }
        // Otherwise, assume it's a station name and apply shortening
        return shortenedDisplayName(for: input)
    }

    /// Returns a shortened display name for UI (strips "Station", etc.)
    private static func shortenedDisplayName(for stationName: String) -> String {
        // First normalize the name to handle API inconsistencies
        let normalizedName = StationNameNormalizer.normalizedName(for: stationName)

        // Apply short display names for common stations
        switch normalizedName {
        case "New York Penn Station":
            return "New York Penn"
        case "Newark Penn Station":
            return "Newark Penn"
        case "Washington Union Station":
            return "Washington Union"
        default:
            return normalizedName
        }
    }
}

// MARK: - Default Map Region

extension MKCoordinateRegion {
    /// Default map region centered on Newark Penn Station with appropriate zoom level
    /// for viewing the NJ Transit network. Used as the consistent "home" view.
    static let newarkPennDefault = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 40.7348, longitude: -74.1644), // Newark Penn Station
        span: MKCoordinateSpan(latitudeDelta: 1.5, longitudeDelta: 1.5)
    )
}
