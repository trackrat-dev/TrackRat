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

        // PATCO Speedline Stations (Philadelphia - South Jersey)
        "Lindenwold", "Ashland", "Woodcrest", "Haddonfield",
        "Westmont", "Collingswood", "Ferry Avenue", "Broadway PATCO",
        "City Hall PATCO", "Franklin Square", "8th and Market",
        "9-10th and Locust", "12-13th and Locust", "15-16th and Locust",

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
        "Delray Beach", "Waldo", "Ocala", "Winter Haven", "Palatka", "Thurmond",

        // Nationwide Amtrak Stations
        // Major hubs and junctions
        "Chicago Union Station", "St. Louis", "Milwaukee",
        "Los Angeles Union Station", "Seattle King Street", "Portland Union Station",
        "Emeryville", "Sacramento", "New Orleans", "San Antonio", "Denver Union Station",
        // California / Southwest
        "Santa Barbara", "San Luis Obispo", "San Jose", "Oceanside", "Santa Ana",
        "Fullerton", "San Diego Old Town", "Albuquerque", "Flagstaff", "Tucson",
        "El Paso", "Reno", "Truckee",
        // Pacific Northwest
        "Spokane", "Tacoma", "Eugene", "Salem OR", "Salt Lake City",
        "Whitefish", "East Glacier Park", "Havre", "St. Paul-Minneapolis",
        // Texas / South Central
        "Dallas", "Fort Worth", "Houston", "Austin", "Little Rock", "Memphis",
        // Midwest / Great Lakes
        "Kansas City", "Oklahoma City", "Omaha", "Indianapolis", "Cincinnati",
        "Cleveland", "Toledo", "Detroit", "Grand Rapids", "Pittsburgh",
        // Northeast extensions
        "Albany-Rensselaer", "Syracuse", "Rochester", "Buffalo Depew", "Montreal",
        "Portland ME", "Essex Junction", "Burlington VT",
        // Virginia / Southeast
        "Lynchburg", "Newport News", "Williamsburg VA", "Columbia SC", "Birmingham", "Mobile",

        // Additional Amtrak stations (nationwide expansion)
        "Anaheim", "Arcata", "Auburn", "Barstow", "Burbank", "Bakersfield",
        "Berkeley", "Burbank", "Chico", "Claremont", "Camarillo", "Colfax",
        "Carpinteria", "Chatsworth", "Davis", "Dublin-Pleasanton", "Dunsmuir", "Elko",
        "Fairfield-Vacaville", "Fremont", "Fresno", "Santa Clara Great America", "Glendale", "Gilroy",
        "Goleta", "Guadalupe", "Grover Beach", "Hayward", "Hanford", "Arcata",
        "Irvine", "Lodi", "Lompoc-Surf", "Las Vegas", "Merced", "Moorpark",
        "Marysville", "Martinez", "Seaside-Marina", "Santa Clarita-Newhall", "Northridge", "Oakland Coliseum/Airport",
        "Oakland", "Ontario", "Oxnard", "Pomona", "Paso Robles", "Palm Springs",
        "Petaluma", "Redding", "Richmond", "Riverside", "Rocklin", "Roseville",
        "Santa Clara", "San Francisco", "Simi Valley", "Stockton", "Stockton", "Santa Monica Pier",
        "San Bernardino", "San Juan Capistrano", "San Clemente Pier", "Salinas", "Solana Beach", "Suisun-Fairfield",
        "Vallejo", "Ventura", "Van Nuys", "Victorville", "Winnemucca", "Willits Calif Western Railroad Depot",
        "Albion", "Ann Arbor", "Bangor", "Battle Creek", "Columbus", "Dearborn",
        "Durand", "Erie", "Flint", "Glenview", "Holland", "Jackson",
        "Kalamazoo", "East Lansing", "Lapeer", "General Mitchell Intl. Airport", "Pontiac", "Portage",
        "Port Huron", "Royal Oak", "St. Joseph-Benton Harbor", "Sturtevant", "Troy", "Wisconsin Dells",
        "Altoona", "Ardmore", "Berlin", "Branford", "Bowie State", "Clinton",
        "Coatesville", "Connellsville", "Croton-Harmon", "Cumberland", "Cornwells Heights", "Downingtown",
        "Edgewood", "Exton", "Greensburg", "Guilford", "Halethorpe", "Harpers Ferry",
        "Huntingdon", "Johnstown", "Latrobe", "Lewistown", "Madison", "Middletown",
        "Martinsburg", "Martin Airport", "Mystic", "Newark", "New Rochelle", "Odenton",
        "Paoli", "Parkesburg", "North Philadelphia", "Poughkeepsie", "Perryville", "Rhinecliff",
        "Rockville", "New Haven", "Tyrone", "West Baltimore", "Windsor", "Westbrook",
        "Yonkers", "Ashland", "Alliance", "Alderson", "Bloomington-Normal", "Bryan",
        "Carbondale", "Centralia", "Champaign-Urbana", "Charleston", "Connersville", "Crawfordsville",
        "Carlinville", "Dowagiac", "Du Quoin", "Dwight", "Dyer", "Effingham",
        "Elkhart", "Elyria", "Fulton", "Gilman", "Hinton", "Hammond-Whiting",
        "Homewood", "Huntington", "Joliet Gateway Center", "Kannapolis", "Kewanee", "Kankakee",
        "Lafayette", "La Grange", "Lincoln", "Mattoon", "Maysville", "Mendota",
        "Montgomery", "Newbern-Dyersburg", "New Buffalo", "Niles", "Naperville", "Princeton",
        "Peoria", "Plano", "Pontiac", "Prince", "Rensselaer", "Rantoul",
        "Sandusky", "Summit", "South Bend", "Springfield", "South Portsmouth", "Thurmond",
        "White Sulphur Springs", "Waterloo", "Arcadia Valley", "Ardmore", "Alton", "Alpine",
        "Arkadelphia", "Beaumont", "Brookhaven", "Burlington", "Cleburne", "Creston",
        "Dodge City", "Detroit Lakes", "Del Rio", "Devils Lake", "Fargo", "Fort Madison",
        "Fort Morgan", "Galesburg", "Garden City", "Grand Forks", "Gainesville", "Greenwood",
        "Hastings", "Hazlehurst", "Hermann", "Holdrege", "Hammond", "Hope",
        "Hutchinson", "Independence", "Jackson", "Jefferson City", "Killeen", "Kirkwood",
        "La Junta", "La Plata", "Lbo", "Lake Charles", "Lee'S Summit", "Lafayette",
        "Lamar", "Lincoln", "Lawrence", "La Crosse", "Longview", "Macomb",
        "Mccomb", "Mcgregor", "Mccook", "Marshall", "Mineola", "Marks",
        "Minot", "Mt. Pleasant", "Malvern", "New Iberia", "Norman", "Osceola",
        "Ottumwa", "Poplar Bluff", "Purcell", "Pauls Valley", "Quincy", "Raton",
        "Red Wing", "Rugby", "St. Cloud", "Schriever", "Sedalia", "Shreveport Sportran Intermodal Terminal",
        "San Marcos", "Sanderson", "Staples", "Stanley", "Taylor", "Tomah",
        "Topeka", "Temple", "Trinidad", "Texarkana", "Washington", "Warrensburg",
        "Wellington", "Wichita", "Winona", "Walnut Ridge", "Williston", "Yazoo City",
        "Amsterdam", "Aldershot", "Buffalo", "Bellows Falls", "Boston", "Brattleboro",
        "Brunswick", "Canadian Border", "Castleton", "Fort Edward", "Framingham", "Freeport",
        "Ticonderoga", "Greenfield", "Grimsby", "Haverhill", "Holyoke", "Hudson",
        "Middlebury", "Montpelier-Berlin", "Niagara Falls", "Niagara Falls", "Northampton", "Oakville",
        "Old Orchard Beach", "Pittsfield", "Plattsburgh", "Port Henry", "Rome", "Randolph",
        "Rouses Point", "Route 128", "Rutland", "St. Albans", "Saco", "Saratoga Springs",
        "St. Catherines", "Schenectady", "St-Lambert", "Toronto", "Utica", "Ferrisburgh",
        "Waterbury-Stowe", "Wells", "Whitehall", "Windsor-Mt. Ascutney", "Woburn", "Worcester Union",
        "White River Junction", "Westport", "Albany", "Bellingham", "Bingen-White Salmon", "Browning",
        "Chemult", "Centralia", "Cut Bank", "Edmonds", "Ephrata", "Essex",
        "Everett", "Glasgow", "Granby", "Kelso-Longview", "Klamath Falls", "Libby",
        "Leavenworth", "Malta", "Mount Vernon", "Olympia-Lacey", "Oregon City", "Provo",
        "Pasco", "Shelby", "Sandpoint", "Stanwood", "Tukwila", "Vancouver",
        "Vancouver", "Wenatchee", "West Glacier", "Wishram", "Wolf Point", "Anniston",
        "Bay St Louis", "Bradenton", "Biloxi Amtrak Sta", "Camden", "Deerfield Beach", "Denmark",
        "Gainesville", "Gulfport Amtrak Sta", "Hattiesburg", "Hollywood", "Jesup", "Lakeland",
        "Laurel", "Meridian Union", "Okeechobee", "Pascagoula", "Palatka", "Picayune",
        "Sebring", "Slidell", "Sanford Amtrak Auto Train", "St. Petersburg", "Toccoa", "Tuscaloosa",
        "Waldo", "Wildwood", "Yemassee", "Burke Centre", "Burlington", "Clifton Forge",
        "Culpeper", "Cary", "Danville", "Fayetteville", "Fredericksburg", "Goldsboro",
        "Greensboro", "Havelock", "Kinston", "Morehead City", "Quantico", "Seabrook",
        "Southern Pines", "Selma", "Staunton", "Swansboro", "Woodbridge", "Wilmington",
        "Benson", "Deming", "Grand Junction", "Gallup", "Green River", "Glenwood Springs",
        "Helper", "Kingman", "Lordsburg", "Lamy", "Las Vegas", "Maricopa",
        "Needles", "Phoenix Sky Harbor Airport", "North Phoenix Metro Center Transit", "Santa Fe", "Winter Park/Fraser", "Winslow",
        "Williams", "Winter Park Ski Resort", "Winter Park", "Yuma"
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

        // PATCO Speedline stations (Philadelphia - South Jersey)
        "Lindenwold": "LND",
        "Ashland": "ASD",
        "Woodcrest": "WCT",
        "Haddonfield": "HDF",
        "Westmont": "WMT",
        "Collingswood": "CLD",
        "Ferry Avenue": "FRY",
        "Broadway PATCO": "BWY",
        "City Hall PATCO": "CTH",
        "Franklin Square": "FKS",
        "8th and Market": "EMK",
        "9-10th and Locust": "NTL",
        "12-13th and Locust": "TWL",
        "15-16th and Locust": "FFL",

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
        "Thurmond": "THU",
        // Nationwide Amtrak stations
        "Chicago Union Station": "CHI",
        "St. Louis": "STL",
        "Milwaukee": "MKE",
        "Los Angeles Union Station": "LAX",
        "Seattle King Street": "SEA",
        "Portland Union Station": "PDX",
        "Emeryville": "EMY",
        "Sacramento": "SAC",
        "New Orleans": "NOL",
        "San Antonio": "SAS",
        "Denver Union Station": "DEN",
        // California / Southwest
        "Santa Barbara": "SBA",
        "San Luis Obispo": "SLO",
        "San Jose": "SJC",
        "Oceanside": "OSD",
        "Santa Ana": "SNA",
        "Fullerton": "FUL",
        "San Diego Old Town": "OLT",
        "Albuquerque": "ABQ",
        "Flagstaff": "FLG",
        "Tucson": "TUS",
        "El Paso": "ELP",
        "Reno": "RNO",
        "Truckee": "TRU",
        // Pacific Northwest
        "Spokane": "SPK",
        "Tacoma": "TAC",
        "Eugene": "EUG",
        "Salem OR": "SLM",
        "Salt Lake City": "SLC",
        "Whitefish": "WFH",
        "East Glacier Park": "GPK",
        "Havre": "HAV",
        "St. Paul-Minneapolis": "MSP",
        // Texas / South Central
        "Dallas": "DAL",
        "Fort Worth": "FTW",
        "Houston": "HOS",
        "Austin": "AUS",
        "Little Rock": "LRK",
        "Memphis": "MEM",
        // Midwest / Great Lakes
        "Kansas City": "KCY",
        "Oklahoma City": "OKC",
        "Omaha": "OMA",
        "Indianapolis": "IND",
        "Cincinnati": "CIN",
        "Cleveland": "CLE",
        "Toledo": "TOL",
        "Detroit": "DET",
        "Grand Rapids": "GRR",
        "Pittsburgh": "PGH",
        // Northeast extensions
        "Albany-Rensselaer": "ALB",
        "Syracuse": "SYR",
        "Rochester": "ROC",
        "Buffalo Depew": "BUF",
        "Montreal": "MTR",
        "Portland ME": "POR",
        "Essex Junction": "ESX",
        "Burlington VT": "BTN",
        // Virginia / Southeast
        "Lynchburg": "LYH",
        "Newport News": "NPN",
        "Williamsburg VA": "WBG",
        "Columbia SC": "CLB",
        "Birmingham": "BHM",
        "Mobile": "MOE",

        // California
        "Anaheim": "ANA",
        "Arcata": "ARC",
        "Auburn": "ARN",
        "Barstow": "BAR",
        "Burbank": "BBK",
        "Bakersfield": "BFD",
        "Berkeley": "BKY",
        "Burbank": "BUR",
        "Chico": "CIC",
        "Claremont": "CLM",
        "Camarillo": "CML",
        "Colfax": "COX",
        "Carpinteria": "CPN",
        "Chatsworth": "CWT",
        "Davis": "DAV",
        "Dublin-Pleasanton": "DBP",
        "Dunsmuir": "DUN",
        "Elko": "ELK",
        "Fairfield-Vacaville": "FFV",
        "Fremont": "FMT",
        "Fresno": "FNO",
        "Santa Clara Great America": "GAC",
        "Glendale": "GDL",
        "Gilroy": "GLY",
        "Goleta": "GTA",
        "Guadalupe": "GUA",
        "Grover Beach": "GVB",
        "Hayward": "HAY",
        "Hanford": "HNF",
        "Arcata": "HSU",
        "Irvine": "IRV",
        "Lodi": "LOD",
        "Lompoc-Surf": "LPS",
        "Las Vegas": "LVS",
        "Merced": "MCD",
        "Moorpark": "MPK",
        "Marysville": "MRV",
        "Martinez": "MTZ",
        "Seaside-Marina": "MYU",
        "Santa Clarita-Newhall": "NHL",
        "Northridge": "NRG",
        "Oakland Coliseum/Airport": "OAC",
        "Oakland": "OKJ",
        "Ontario": "ONA",
        "Oxnard": "OXN",
        "Pomona": "POS",
        "Paso Robles": "PRB",
        "Palm Springs": "PSN",
        "Petaluma": "PTC",
        "Redding": "RDD",
        "Richmond": "RIC",
        "Riverside": "RIV",
        "Rocklin": "RLN",
        "Roseville": "RSV",
        "Santa Clara": "SCC",
        "San Francisco": "SFC",
        "Simi Valley": "SIM",
        "Stockton": "SKN",
        "Stockton": "SKT",
        "Santa Monica Pier": "SMN",
        "San Bernardino": "SNB",
        "San Juan Capistrano": "SNC",
        "San Clemente Pier": "SNP",
        "Salinas": "SNS",
        "Solana Beach": "SOL",
        "Suisun-Fairfield": "SUI",
        "Vallejo": "VAL",
        "Ventura": "VEC",
        "Van Nuys": "VNC",
        "Victorville": "VRV",
        "Winnemucca": "WNN",
        "Willits Calif Western Railroad Depot": "WTS",

        // Great Lakes
        "Albion": "ALI",
        "Ann Arbor": "ARB",
        "Bangor": "BAM",
        "Battle Creek": "BTL",
        "Columbus": "CBS",
        "Dearborn": "DER",
        "Durand": "DRD",
        "Erie": "ERI",
        "Flint": "FLN",
        "Glenview": "GLN",
        "Holland": "HOM",
        "Jackson": "JXN",
        "Kalamazoo": "KAL",
        "East Lansing": "LNS",
        "Lapeer": "LPE",
        "General Mitchell Intl. Airport": "MKA",
        "Pontiac": "PNT",
        "Portage": "POG",
        "Port Huron": "PTH",
        "Royal Oak": "ROY",
        "St. Joseph-Benton Harbor": "SJM",
        "Sturtevant": "SVT",
        "Troy": "TRM",
        "Wisconsin Dells": "WDL",

        // Mid-Atlantic
        "Altoona": "ALT",
        "Ardmore": "ARD",
        "Berlin": "BER",
        "Branford": "BNF",
        "Bowie State": "BWE",
        "Clinton": "CLN",
        "Coatesville": "COT",
        "Connellsville": "COV",
        "Croton-Harmon": "CRT",
        "Cumberland": "CUM",
        "Cornwells Heights": "CWH",
        "Downingtown": "DOW",
        "Edgewood": "EDG",
        "Exton": "EXT",
        "Greensburg": "GNB",
        "Guilford": "GUI",
        "Halethorpe": "HAE",
        "Harpers Ferry": "HFY",
        "Huntingdon": "HGD",
        "Johnstown": "JST",
        "Latrobe": "LAB",
        "Lewistown": "LEW",
        "Madison": "MDS",
        "Middletown": "MID",
        "Martinsburg": "MRB",
        "Martin Airport": "MSA",
        "Mystic": "MYS",
        "Newark": "NRK",
        "New Rochelle": "NRO",
        "Odenton": "OTN",
        "Paoli": "PAO",
        "Parkesburg": "PAR",
        "North Philadelphia": "PHN",
        "Poughkeepsie": "POU",
        "Perryville": "PRV",
        "Rhinecliff": "RHI",
        "Rockville": "RKV",
        "New Haven": "STS",
        "Tyrone": "TYR",
        "West Baltimore": "WBL",
        "Windsor": "WND",
        "Westbrook": "WSB",
        "Yonkers": "YNY",

        // Midwest
        "Ashland": "AKY",
        "Alliance": "ALC",
        "Alderson": "ALD",
        "Bloomington-Normal": "BNL",
        "Bryan": "BYN",
        "Carbondale": "CDL",
        "Centralia": "CEN",
        "Champaign-Urbana": "CHM",
        "Charleston": "CHW",
        "Connersville": "COI",
        "Crawfordsville": "CRF",
        "Carlinville": "CRV",
        "Dowagiac": "DOA",
        "Du Quoin": "DQN",
        "Dwight": "DWT",
        "Dyer": "DYE",
        "Effingham": "EFG",
        "Elkhart": "EKH",
        "Elyria": "ELY",
        "Fulton": "FTN",
        "Gilman": "GLM",
        "Hinton": "HIN",
        "Hammond-Whiting": "HMI",
        "Homewood": "HMW",
        "Huntington": "HUN",
        "Joliet Gateway Center": "JOL",
        "Kannapolis": "KAN",
        "Kewanee": "KEE",
        "Kankakee": "KKI",
        "Lafayette": "LAF",
        "La Grange": "LAG",
        "Lincoln": "LCN",
        "Mattoon": "MAT",
        "Maysville": "MAY",
        "Mendota": "MDT",
        "Montgomery": "MNG",
        "Newbern-Dyersburg": "NBN",
        "New Buffalo": "NBU",
        "Niles": "NLS",
        "Naperville": "NPV",
        "Princeton": "PCT",
        "Peoria": "PIA",
        "Plano": "PLO",
        "Pontiac": "PON",
        "Prince": "PRC",
        "Rensselaer": "REN",
        "Rantoul": "RTL",
        "Sandusky": "SKY",
        "Summit": "SMT",
        "South Bend": "SOB",
        "Springfield": "SPI",
        "South Portsmouth": "SPM",
        "Thurmond": "THN",
        "White Sulphur Springs": "WSS",
        "Waterloo": "WTI",

        // Mountain West
        "Arcadia Valley": "ACD",
        "Ardmore": "ADM",
        "Alton": "ALN",
        "Alpine": "ALP",
        "Arkadelphia": "ARK",
        "Beaumont": "BMT",
        "Brookhaven": "BRH",
        "Burlington": "BRL",
        "Cleburne": "CBR",
        "Creston": "CRN",
        "Dodge City": "DDG",
        "Detroit Lakes": "DLK",
        "Del Rio": "DRT",
        "Devils Lake": "DVL",
        "Fargo": "FAR",
        "Fort Madison": "FMD",
        "Fort Morgan": "FMG",
        "Galesburg": "GBB",
        "Garden City": "GCK",
        "Grand Forks": "GFK",
        "Gainesville": "GLE",
        "Greenwood": "GWD",
        "Hastings": "HAS",
        "Hazlehurst": "HAZ",
        "Hermann": "HEM",
        "Holdrege": "HLD",
        "Hammond": "HMD",
        "Hope": "HOP",
        "Hutchinson": "HUT",
        "Independence": "IDP",
        "Jackson": "JAN",
        "Jefferson City": "JEF",
        "Killeen": "KIL",
        "Kirkwood": "KWD",
        "La Junta": "LAJ",
        "La Plata": "LAP",
        "Lbo": "LBO",
        "Lake Charles": "LCH",
        "Lee'S Summit": "LEE",
        "Lafayette": "LFT",
        "Lamar": "LMR",
        "Lincoln": "LNK",
        "Lawrence": "LRC",
        "La Crosse": "LSE",
        "Longview": "LVW",
        "Macomb": "MAC",
        "Mccomb": "MCB",
        "Mcgregor": "MCG",
        "Mccook": "MCK",
        "Marshall": "MHL",
        "Mineola": "MIN",
        "Marks": "MKS",
        "Minot": "MOT",
        "Mt. Pleasant": "MTP",
        "Malvern": "MVN",
        "New Iberia": "NIB",
        "Norman": "NOR",
        "Osceola": "OSC",
        "Ottumwa": "OTM",
        "Poplar Bluff": "PBF",
        "Purcell": "PUR",
        "Pauls Valley": "PVL",
        "Quincy": "QCY",
        "Raton": "RAT",
        "Red Wing": "RDW",
        "Rugby": "RUG",
        "St. Cloud": "SCD",
        "Schriever": "SCH",
        "Sedalia": "SED",
        "Shreveport Sportran Intermodal Terminal": "SHR",
        "San Marcos": "SMC",
        "Sanderson": "SND",
        "Staples": "SPL",
        "Stanley": "STN",
        "Taylor": "TAY",
        "Tomah": "TOH",
        "Topeka": "TOP",
        "Temple": "TPL",
        "Trinidad": "TRI",
        "Texarkana": "TXA",
        "Washington": "WAH",
        "Warrensburg": "WAR",
        "Wellington": "WEL",
        "Wichita": "WIC",
        "Winona": "WIN",
        "Walnut Ridge": "WNR",
        "Williston": "WTN",
        "Yazoo City": "YAZ",

        // New England
        "Amsterdam": "AMS",
        "Aldershot": "AST",
        "Buffalo": "BFX",
        "Bellows Falls": "BLF",
        "Boston": "BON",
        "Brattleboro": "BRA",
        "Brunswick": "BRK",
        "Canadian Border": "CBN",
        "Castleton": "CNV",
        "Fort Edward": "FED",
        "Framingham": "FRA",
        "Freeport": "FRE",
        "Ticonderoga": "FTC",
        "Greenfield": "GFD",
        "Grimsby": "GMS",
        "Haverhill": "HHL",
        "Holyoke": "HLK",
        "Hudson": "HUD",
        "Middlebury": "MBY",
        "Montpelier-Berlin": "MPR",
        "Niagara Falls": "NFL",
        "Niagara Falls": "NFS",
        "Northampton": "NHT",
        "Oakville": "OKL",
        "Old Orchard Beach": "ORB",
        "Pittsfield": "PIT",
        "Plattsburgh": "PLB",
        "Port Henry": "POH",
        "Rome": "ROM",
        "Randolph": "RPH",
        "Rouses Point": "RSP",
        "Route 128": "RTE",
        "Rutland": "RUD",
        "St. Albans": "SAB",
        "Saco": "SAO",
        "Saratoga Springs": "SAR",
        "St. Catherines": "SCA",
        "Schenectady": "SDY",
        "St-Lambert": "SLQ",
        "Toronto": "TWO",
        "Utica": "UCA",
        "Ferrisburgh": "VRN",
        "Waterbury-Stowe": "WAB",
        "Wells": "WEM",
        "Whitehall": "WHL",
        "Windsor-Mt. Ascutney": "WNM",
        "Woburn": "WOB",
        "Worcester Union": "WOR",
        "White River Junction": "WRJ",
        "Westport": "WSP",

        // Pacific Northwest
        "Albany": "ALY",
        "Bellingham": "BEL",
        "Bingen-White Salmon": "BNG",
        "Browning": "BRO",
        "Chemult": "CMO",
        "Centralia": "CTL",
        "Cut Bank": "CUT",
        "Edmonds": "EDM",
        "Ephrata": "EPH",
        "Essex": "ESM",
        "Everett": "EVR",
        "Glasgow": "GGW",
        "Granby": "GRA",
        "Kelso-Longview": "KEL",
        "Klamath Falls": "KFS",
        "Libby": "LIB",
        "Leavenworth": "LWA",
        "Malta": "MAL",
        "Mount Vernon": "MVW",
        "Olympia-Lacey": "OLW",
        "Oregon City": "ORC",
        "Provo": "PRO",
        "Pasco": "PSC",
        "Shelby": "SBY",
        "Sandpoint": "SPT",
        "Stanwood": "STW",
        "Tukwila": "TUK",
        "Vancouver": "VAC",
        "Vancouver": "VAN",
        "Wenatchee": "WEN",
        "West Glacier": "WGL",
        "Wishram": "WIH",
        "Wolf Point": "WPT",

        // South Central
        "Anniston": "ATN",
        "Bay St Louis": "BAS",
        "Bradenton": "BDT",
        "Biloxi Amtrak Sta": "BIX",
        "Camden": "CAM",
        "Deerfield Beach": "DFB",
        "Denmark": "DNK",
        "Gainesville": "GNS",
        "Gulfport Amtrak Sta": "GUF",
        "Hattiesburg": "HBG",
        "Hollywood": "HOL",
        "Jesup": "JSP",
        "Lakeland": "LAK",
        "Laurel": "LAU",
        "Meridian Union": "MEI",
        "Okeechobee": "OKE",
        "Pascagoula": "PAG",
        "Palatka": "PAK",
        "Picayune": "PIC",
        "Sebring": "SBG",
        "Slidell": "SDL",
        "Sanford Amtrak Auto Train": "SFA",
        "St. Petersburg": "STP",
        "Toccoa": "TCA",
        "Tuscaloosa": "TCL",
        "Waldo": "WDO",
        "Wildwood": "WWD",
        "Yemassee": "YEM",

        // Southeast
        "Burke Centre": "BCV",
        "Burlington": "BNC",
        "Clifton Forge": "CLF",
        "Culpeper": "CLP",
        "Cary": "CYN",
        "Danville": "DAN",
        "Fayetteville": "FAY",
        "Fredericksburg": "FBG",
        "Goldsboro": "GBO",
        "Greensboro": "GRO",
        "Havelock": "HVL",
        "Kinston": "KNC",
        "Morehead City": "MHD",
        "Quantico": "QAN",
        "Seabrook": "SEB",
        "Southern Pines": "SOP",
        "Selma": "SSM",
        "Staunton": "STA",
        "Swansboro": "SWB",
        "Woodbridge": "WDB",
        "Wilmington": "WMN",

        // Southwest
        "Benson": "BEN",
        "Deming": "DEM",
        "Grand Junction": "GJT",
        "Gallup": "GLP",
        "Green River": "GRI",
        "Glenwood Springs": "GSC",
        "Helper": "HER",
        "Kingman": "KNG",
        "Lordsburg": "LDB",
        "Lamy": "LMY",
        "Las Vegas": "LSV",
        "Maricopa": "MRC",
        "Needles": "NDL",
        "Phoenix Sky Harbor Airport": "PHA",
        "North Phoenix Metro Center Transit": "PXN",
        "Santa Fe": "SAF",
        "Winter Park/Fraser": "WIP",
        "Winslow": "WLO",
        "Williams": "WMH",
        "Winter Park Ski Resort": "WPR",
        "Winter Park": "WPS",
        "Yuma": "YUM",

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
        "PAO": CLLocationCoordinate2D(latitude: 40.0423, longitude: -75.4767),  // Paoli, PA (Keystone)
        "EXT": CLLocationCoordinate2D(latitude: 40.0131, longitude: -75.6233),  // Exton, PA (Keystone)
        "DOW": CLLocationCoordinate2D(latitude: 40.0003, longitude: -75.7042),  // Downingtown, PA (Keystone)
        "COT": CLLocationCoordinate2D(latitude: 39.9823, longitude: -75.8233),  // Coatesville, PA (Keystone)
        "PKB": CLLocationCoordinate2D(latitude: 39.9612, longitude: -75.9193),  // Parkesburg, PA (Keystone)
        "MJY": CLLocationCoordinate2D(latitude: 40.1071, longitude: -76.5033),  // Mount Joy, PA (Keystone)
        "ELT": CLLocationCoordinate2D(latitude: 40.1524, longitude: -76.5258),  // Elizabethtown, PA (Keystone)
        "MIDPA": CLLocationCoordinate2D(latitude: 40.1996, longitude: -76.7322),  // Middletown, PA (Keystone)
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
	"GA": CLLocationCoordinate2D(latitude: 40.8847, longitude: -74.2539),   // Great Notch
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

        // PATCO Speedline stations - synced with backend_v2/src/trackrat/config/stations.py
        "LND": CLLocationCoordinate2D(latitude: 39.833962, longitude: -75.000664),  // Lindenwold
        "ASD": CLLocationCoordinate2D(latitude: 39.858705, longitude: -75.00921),   // Ashland
        "WCT": CLLocationCoordinate2D(latitude: 39.870263, longitude: -75.011242),  // Woodcrest
        "HDF": CLLocationCoordinate2D(latitude: 39.89764, longitude: -75.037141),   // Haddonfield
        "WMT": CLLocationCoordinate2D(latitude: 39.90706, longitude: -75.046553),   // Westmont
        "CLD": CLLocationCoordinate2D(latitude: 39.91359, longitude: -75.06456),    // Collingswood
        "FRY": CLLocationCoordinate2D(latitude: 39.922572, longitude: -75.091805),  // Ferry Avenue
        "BWY": CLLocationCoordinate2D(latitude: 39.943135, longitude: -75.120364),  // Broadway PATCO
        "CTH": CLLocationCoordinate2D(latitude: 39.945469, longitude: -75.121242),  // City Hall PATCO
        "FKS": CLLocationCoordinate2D(latitude: 39.955298, longitude: -75.151157),  // Franklin Square
        "EMK": CLLocationCoordinate2D(latitude: 39.950979, longitude: -75.153515),  // 8th and Market
        "NTL": CLLocationCoordinate2D(latitude: 39.947345, longitude: -75.15751),   // 9-10th and Locust
        "TWL": CLLocationCoordinate2D(latitude: 39.947944, longitude: -75.162365),  // 12-13th and Locust
        "FFL": CLLocationCoordinate2D(latitude: 39.948634, longitude: -75.167792),  // 15-16th and Locust

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
        "WLD": CLLocationCoordinate2D(latitude: 29.7899, longitude: -82.1712),                     // Waldo, FL
        "OCA": CLLocationCoordinate2D(latitude: 29.1871, longitude: -82.1301),                     // Ocala, FL
        "WLN": CLLocationCoordinate2D(latitude: 35.7230682373047, longitude: -77.9082946777344),   // Wilson, NC
        "WPB": CLLocationCoordinate2D(latitude: 26.7153, longitude: -80.0534),                     // West Palm Beach, FL
        "WPK": CLLocationCoordinate2D(latitude: 28.5990, longitude: -81.3392),                     // Winter Park, FL
        "WTH": CLLocationCoordinate2D(latitude: 28.0222, longitude: -81.7323),                     // Winter Haven, FL

        // Missing Southeast stations (added for route topology)
        "SOU": CLLocationCoordinate2D(latitude: 35.1740, longitude: -79.3920),                     // Southern Pines, NC
        "SEL": CLLocationCoordinate2D(latitude: 35.5351, longitude: -78.2836),                     // Selma-Smithfield, NC
        "CAR": CLLocationCoordinate2D(latitude: 35.7830, longitude: -78.7810),                     // Cary, NC
        "GRB": CLLocationCoordinate2D(latitude: 36.0726, longitude: -79.7920),                     // Greensboro, NC
        "GVL": CLLocationCoordinate2D(latitude: 34.8526, longitude: -82.3940),                     // Greenville, SC
        "TOC": CLLocationCoordinate2D(latitude: 34.5773, longitude: -83.3315),                     // Toccoa, GA
        "GAI": CLLocationCoordinate2D(latitude: 34.2979, longitude: -83.8241),                     // Gainesville, GA
        "JES": CLLocationCoordinate2D(latitude: 31.6036, longitude: -81.8854),                     // Jesup, GA
        "PAL": CLLocationCoordinate2D(latitude: 29.6486, longitude: -81.6376),                     // Palatka, FL
        "SAN": CLLocationCoordinate2D(latitude: 28.8122, longitude: -81.3130),                     // Sanford, FL
        "HLW": CLLocationCoordinate2D(latitude: 26.0112, longitude: -80.1495),                     // Hollywood, FL

        // Nationwide Amtrak stations
        "CHI": CLLocationCoordinate2D(latitude: 41.8787, longitude: -87.6394),  // Chicago Union Station
        "STL": CLLocationCoordinate2D(latitude: 38.6242, longitude: -90.2040),  // St. Louis
        "MKE": CLLocationCoordinate2D(latitude: 43.0345, longitude: -87.9171),  // Milwaukee
        "LAX": CLLocationCoordinate2D(latitude: 34.0562, longitude: -118.2368), // Los Angeles Union Station
        "SEA": CLLocationCoordinate2D(latitude: 47.5984, longitude: -122.3302), // Seattle King Street
        "PDX": CLLocationCoordinate2D(latitude: 45.5287, longitude: -122.6768), // Portland Union Station
        "EMY": CLLocationCoordinate2D(latitude: 37.8405, longitude: -122.2916), // Emeryville
        "SAC": CLLocationCoordinate2D(latitude: 38.5840, longitude: -121.5007), // Sacramento
        "NOL": CLLocationCoordinate2D(latitude: 29.9461, longitude: -90.0783),  // New Orleans
        "SAS": CLLocationCoordinate2D(latitude: 29.4194, longitude: -98.4781),  // San Antonio
        "DEN": CLLocationCoordinate2D(latitude: 39.7530, longitude: -104.9999), // Denver Union Station
        // California / Southwest
        "SBA": CLLocationCoordinate2D(latitude: 34.4137, longitude: -119.6857), // Santa Barbara
        "SLO": CLLocationCoordinate2D(latitude: 35.2730, longitude: -120.6574), // San Luis Obispo
        "SJC": CLLocationCoordinate2D(latitude: 37.3297, longitude: -121.9021), // San Jose
        "OSD": CLLocationCoordinate2D(latitude: 33.1954, longitude: -117.3803), // Oceanside
        "SNA": CLLocationCoordinate2D(latitude: 33.7489, longitude: -117.8664), // Santa Ana
        "FUL": CLLocationCoordinate2D(latitude: 33.8715, longitude: -117.9246), // Fullerton
        "OLT": CLLocationCoordinate2D(latitude: 32.7548, longitude: -117.1976), // San Diego Old Town
        "ABQ": CLLocationCoordinate2D(latitude: 35.0844, longitude: -106.6488), // Albuquerque
        "FLG": CLLocationCoordinate2D(latitude: 35.1981, longitude: -111.6476), // Flagstaff
        "TUS": CLLocationCoordinate2D(latitude: 32.2193, longitude: -110.9643), // Tucson
        "ELP": CLLocationCoordinate2D(latitude: 31.7590, longitude: -106.4890), // El Paso
        "RNO": CLLocationCoordinate2D(latitude: 39.5295, longitude: -119.7773), // Reno
        "TRU": CLLocationCoordinate2D(latitude: 39.3278, longitude: -120.1850), // Truckee
        // Pacific Northwest
        "SPK": CLLocationCoordinate2D(latitude: 47.6533, longitude: -117.4083), // Spokane
        "TAC": CLLocationCoordinate2D(latitude: 47.2420, longitude: -122.4282), // Tacoma
        "EUG": CLLocationCoordinate2D(latitude: 44.0543, longitude: -123.0950), // Eugene
        "SLM": CLLocationCoordinate2D(latitude: 44.9429, longitude: -123.0353), // Salem
        "SLC": CLLocationCoordinate2D(latitude: 40.7774, longitude: -111.9301), // Salt Lake City
        "WFH": CLLocationCoordinate2D(latitude: 48.4106, longitude: -114.3375), // Whitefish
        "GPK": CLLocationCoordinate2D(latitude: 48.4481, longitude: -113.2176), // East Glacier Park
        "HAV": CLLocationCoordinate2D(latitude: 48.5528, longitude: -109.6822), // Havre
        "MSP": CLLocationCoordinate2D(latitude: 44.9464, longitude: -93.0854),  // St. Paul-Minneapolis
        // Texas / South Central
        "DAL": CLLocationCoordinate2D(latitude: 32.7789, longitude: -96.8083),  // Dallas
        "FTW": CLLocationCoordinate2D(latitude: 32.7511, longitude: -97.3340),  // Fort Worth
        "HOS": CLLocationCoordinate2D(latitude: 29.7689, longitude: -95.3597),  // Houston
        "AUS": CLLocationCoordinate2D(latitude: 30.2748, longitude: -97.7268),  // Austin
        "LRK": CLLocationCoordinate2D(latitude: 34.7345, longitude: -92.2740),  // Little Rock
        "MEM": CLLocationCoordinate2D(latitude: 35.1352, longitude: -90.0510),  // Memphis
        // Midwest / Great Lakes
        "KCY": CLLocationCoordinate2D(latitude: 39.0912, longitude: -94.5556),  // Kansas City
        "OKC": CLLocationCoordinate2D(latitude: 35.4728, longitude: -97.5153),  // Oklahoma City
        "OMA": CLLocationCoordinate2D(latitude: 41.2535, longitude: -95.9319),  // Omaha
        "IND": CLLocationCoordinate2D(latitude: 39.7642, longitude: -86.1637),  // Indianapolis
        "CIN": CLLocationCoordinate2D(latitude: 39.1033, longitude: -84.5123),  // Cincinnati
        "CLE": CLLocationCoordinate2D(latitude: 41.5159, longitude: -81.6848),  // Cleveland
        "TOL": CLLocationCoordinate2D(latitude: 41.6529, longitude: -83.5328),  // Toledo
        "DET": CLLocationCoordinate2D(latitude: 42.3289, longitude: -83.0521),  // Detroit
        "GRR": CLLocationCoordinate2D(latitude: 42.9669, longitude: -85.6760),  // Grand Rapids
        "PGH": CLLocationCoordinate2D(latitude: 40.4447, longitude: -79.9923),  // Pittsburgh
        // Northeast extensions
        "ALB": CLLocationCoordinate2D(latitude: 42.6418, longitude: -73.7542),  // Albany-Rensselaer
        "SYR": CLLocationCoordinate2D(latitude: 43.0473, longitude: -76.1440),  // Syracuse
        "ROC": CLLocationCoordinate2D(latitude: 43.1566, longitude: -77.6088),  // Rochester
        "BUF": CLLocationCoordinate2D(latitude: 42.9038, longitude: -78.8636),  // Buffalo Depew
        "MTR": CLLocationCoordinate2D(latitude: 45.5017, longitude: -73.5673),  // Montreal
        "POR": CLLocationCoordinate2D(latitude: 43.6559, longitude: -70.2614),  // Portland ME
        "ESX": CLLocationCoordinate2D(latitude: 44.4881, longitude: -73.1820),  // Essex Junction
        "BTN": CLLocationCoordinate2D(latitude: 44.4759, longitude: -73.2121),  // Burlington VT
        // Virginia / Southeast
        "LYH": CLLocationCoordinate2D(latitude: 37.4083, longitude: -79.1428),  // Lynchburg
        "NPN": CLLocationCoordinate2D(latitude: 36.9814, longitude: -76.4356),  // Newport News
        "WBG": CLLocationCoordinate2D(latitude: 37.2710, longitude: -76.7075),  // Williamsburg
        "CLB": CLLocationCoordinate2D(latitude: 34.0006, longitude: -81.0349),  // Columbia SC
        "BHM": CLLocationCoordinate2D(latitude: 33.5206, longitude: -86.8344),  // Birmingham
        "MOE": CLLocationCoordinate2D(latitude: 30.6959, longitude: -88.0411),  // Mobile

        // California
        "ANA": CLLocationCoordinate2D(latitude: 33.8038, longitude: -117.8773),  // Anaheim
        "ARC": CLLocationCoordinate2D(latitude: 40.8686, longitude: -124.0838),  // Arcata
        "ARN": CLLocationCoordinate2D(latitude: 38.9036, longitude: -121.0832),  // Auburn
        "BAR": CLLocationCoordinate2D(latitude: 34.9048, longitude: -117.0254),  // Barstow
        "BBK": CLLocationCoordinate2D(latitude: 34.1789, longitude: -118.3118),  // Burbank
        "BFD": CLLocationCoordinate2D(latitude: 35.3721, longitude: -119.0082),  // Bakersfield
        "BKY": CLLocationCoordinate2D(latitude: 37.8673, longitude: -122.3007),  // Berkeley
        "BUR": CLLocationCoordinate2D(latitude: 34.1931, longitude: -118.3538),  // Burbank
        "CIC": CLLocationCoordinate2D(latitude: 39.7233, longitude: -121.8459),  // Chico
        "CLM": CLLocationCoordinate2D(latitude: 34.0945, longitude: -117.7169),  // Claremont
        "CML": CLLocationCoordinate2D(latitude: 34.2159, longitude: -119.0341),  // Camarillo
        "COX": CLLocationCoordinate2D(latitude: 39.0992, longitude: -120.9531),  // Colfax
        "CPN": CLLocationCoordinate2D(latitude: 34.3968, longitude: -119.5230),  // Carpinteria
        "CWT": CLLocationCoordinate2D(latitude: 34.2532, longitude: -118.5994),  // Chatsworth
        "DAV": CLLocationCoordinate2D(latitude: 38.5436, longitude: -121.7377),  // Davis
        "DBP": CLLocationCoordinate2D(latitude: 37.7028, longitude: -121.8977),  // Dublin-Pleasanton
        "DUN": CLLocationCoordinate2D(latitude: 41.2111, longitude: -122.2706),  // Dunsmuir
        "ELK": CLLocationCoordinate2D(latitude: 40.8365, longitude: -115.7505),  // Elko
        "FFV": CLLocationCoordinate2D(latitude: 38.2856, longitude: -121.9679),  // Fairfield-Vacaville
        "FMT": CLLocationCoordinate2D(latitude: 37.5591, longitude: -122.0075),  // Fremont
        "FNO": CLLocationCoordinate2D(latitude: 36.7385, longitude: -119.7829),  // Fresno
        "GAC": CLLocationCoordinate2D(latitude: 37.4068, longitude: -121.9670),  // Santa Clara Great America
        "GDL": CLLocationCoordinate2D(latitude: 34.1237, longitude: -118.2589),  // Glendale
        "GLY": CLLocationCoordinate2D(latitude: 37.0040, longitude: -121.5668),  // Gilroy
        "GTA": CLLocationCoordinate2D(latitude: 34.4377, longitude: -119.8431),  // Goleta
        "GUA": CLLocationCoordinate2D(latitude: 34.9629, longitude: -120.5734),  // Guadalupe
        "GVB": CLLocationCoordinate2D(latitude: 35.1213, longitude: -120.6293),  // Grover Beach
        "HAY": CLLocationCoordinate2D(latitude: 37.6660, longitude: -122.0993),  // Hayward
        "HNF": CLLocationCoordinate2D(latitude: 36.3261, longitude: -119.6518),  // Hanford
        "HSU": CLLocationCoordinate2D(latitude: 40.8733, longitude: -124.0815),  // Arcata
        "IRV": CLLocationCoordinate2D(latitude: 33.6568, longitude: -117.7337),  // Irvine
        "LOD": CLLocationCoordinate2D(latitude: 38.1332, longitude: -121.2719),  // Lodi
        "LPS": CLLocationCoordinate2D(latitude: 34.6827, longitude: -120.6050),  // Lompoc-Surf
        "LVS": CLLocationCoordinate2D(latitude: 36.1645, longitude: -115.1497),  // Las Vegas
        "MCD": CLLocationCoordinate2D(latitude: 37.3072, longitude: -120.4768),  // Merced
        "MPK": CLLocationCoordinate2D(latitude: 34.2848, longitude: -118.8781),  // Moorpark
        "MRV": CLLocationCoordinate2D(latitude: 39.1437, longitude: -121.5973),  // Marysville
        "MTZ": CLLocationCoordinate2D(latitude: 38.0189, longitude: -122.1388),  // Martinez
        "MYU": CLLocationCoordinate2D(latitude: 36.6535, longitude: -121.8014),  // Seaside-Marina
        "NHL": CLLocationCoordinate2D(latitude: 34.3795, longitude: -118.5273),  // Santa Clarita-Newhall
        "NRG": CLLocationCoordinate2D(latitude: 34.2307, longitude: -118.5454),  // Northridge
        "OAC": CLLocationCoordinate2D(latitude: 37.7525, longitude: -122.1981),  // Oakland Coliseum/Airport
        "OKJ": CLLocationCoordinate2D(latitude: 37.7939, longitude: -122.2717),  // Oakland
        "ONA": CLLocationCoordinate2D(latitude: 34.0617, longitude: -117.6496),  // Ontario
        "OXN": CLLocationCoordinate2D(latitude: 34.1992, longitude: -119.1760),  // Oxnard
        "POS": CLLocationCoordinate2D(latitude: 34.0592, longitude: -117.7506),  // Pomona
        "PRB": CLLocationCoordinate2D(latitude: 35.6227, longitude: -120.6879),  // Paso Robles
        "PSN": CLLocationCoordinate2D(latitude: 33.8975, longitude: -116.5479),  // Palm Springs
        "PTC": CLLocationCoordinate2D(latitude: 38.2365, longitude: -122.6358),  // Petaluma
        "RDD": CLLocationCoordinate2D(latitude: 40.5836, longitude: -122.3934),  // Redding
        "RIC": CLLocationCoordinate2D(latitude: 37.9368, longitude: -122.3541),  // Richmond
        "RIV": CLLocationCoordinate2D(latitude: 33.9757, longitude: -117.3700),  // Riverside
        "RLN": CLLocationCoordinate2D(latitude: 38.7910, longitude: -121.2373),  // Rocklin
        "RSV": CLLocationCoordinate2D(latitude: 38.7500, longitude: -121.2863),  // Roseville
        "SCC": CLLocationCoordinate2D(latitude: 37.3532, longitude: -121.9366),  // Santa Clara
        "SFC": CLLocationCoordinate2D(latitude: 37.7886, longitude: -122.3989),  // San Francisco
        "SIM": CLLocationCoordinate2D(latitude: 34.2702, longitude: -118.6952),  // Simi Valley
        "SKN": CLLocationCoordinate2D(latitude: 37.9455, longitude: -121.2856),  // Stockton
        "SKT": CLLocationCoordinate2D(latitude: 37.9570, longitude: -121.2790),  // Stockton
        "SMN": CLLocationCoordinate2D(latitude: 34.0127, longitude: -118.4946),  // Santa Monica Pier
        "SNB": CLLocationCoordinate2D(latitude: 34.1041, longitude: -117.3107),  // San Bernardino
        "SNC": CLLocationCoordinate2D(latitude: 33.5013, longitude: -117.6638),  // San Juan Capistrano
        "SNP": CLLocationCoordinate2D(latitude: 33.4196, longitude: -117.6197),  // San Clemente Pier
        "SNS": CLLocationCoordinate2D(latitude: 36.6791, longitude: -121.6567),  // Salinas
        "SOL": CLLocationCoordinate2D(latitude: 32.9929, longitude: -117.2711),  // Solana Beach
        "SUI": CLLocationCoordinate2D(latitude: 38.2434, longitude: -122.0411),  // Suisun-Fairfield
        "VAL": CLLocationCoordinate2D(latitude: 38.1003, longitude: -122.2592),  // Vallejo
        "VEC": CLLocationCoordinate2D(latitude: 34.2769, longitude: -119.2999),  // Ventura
        "VNC": CLLocationCoordinate2D(latitude: 34.2113, longitude: -118.4482),  // Van Nuys
        "VRV": CLLocationCoordinate2D(latitude: 34.5372, longitude: -117.2930),  // Victorville
        "WNN": CLLocationCoordinate2D(latitude: 40.9690, longitude: -117.7322),  // Winnemucca
        "WTS": CLLocationCoordinate2D(latitude: 39.4126, longitude: -123.3510),  // Willits Calif Western Railroad Depot

        // Great Lakes
        "ALI": CLLocationCoordinate2D(latitude: 42.2472, longitude: -84.7558),  // Albion
        "ARB": CLLocationCoordinate2D(latitude: 42.2877, longitude: -83.7432),  // Ann Arbor
        "BAM": CLLocationCoordinate2D(latitude: 42.3145, longitude: -86.1116),  // Bangor
        "BTL": CLLocationCoordinate2D(latitude: 42.3185, longitude: -85.1878),  // Battle Creek
        "CBS": CLLocationCoordinate2D(latitude: 43.3406, longitude: -89.0126),  // Columbus
        "DER": CLLocationCoordinate2D(latitude: 42.3072, longitude: -83.2353),  // Dearborn
        "DRD": CLLocationCoordinate2D(latitude: 42.9095, longitude: -83.9823),  // Durand
        "ERI": CLLocationCoordinate2D(latitude: 42.1208, longitude: -80.0824),  // Erie
        "FLN": CLLocationCoordinate2D(latitude: 43.0154, longitude: -83.6517),  // Flint
        "GLN": CLLocationCoordinate2D(latitude: 42.0750, longitude: -87.8056),  // Glenview
        "HOM": CLLocationCoordinate2D(latitude: 42.7911, longitude: -86.0966),  // Holland
        "JXN": CLLocationCoordinate2D(latitude: 42.2481, longitude: -84.3997),  // Jackson
        "KAL": CLLocationCoordinate2D(latitude: 42.2953, longitude: -85.5840),  // Kalamazoo
        "LNS": CLLocationCoordinate2D(latitude: 42.7187, longitude: -84.4960),  // East Lansing
        "LPE": CLLocationCoordinate2D(latitude: 43.0495, longitude: -83.3062),  // Lapeer
        "MKA": CLLocationCoordinate2D(latitude: 42.9406, longitude: -87.9244),  // General Mitchell Intl. Airport
        "PNT": CLLocationCoordinate2D(latitude: 42.6328, longitude: -83.2923),  // Pontiac
        "POG": CLLocationCoordinate2D(latitude: 43.5471, longitude: -89.4676),  // Portage
        "PTH": CLLocationCoordinate2D(latitude: 42.9604, longitude: -82.4438),  // Port Huron
        "ROY": CLLocationCoordinate2D(latitude: 42.4884, longitude: -83.1470),  // Royal Oak
        "SJM": CLLocationCoordinate2D(latitude: 42.1091, longitude: -86.4845),  // St. Joseph-Benton Harbor
        "SVT": CLLocationCoordinate2D(latitude: 42.7183, longitude: -87.9063),  // Sturtevant
        "TRM": CLLocationCoordinate2D(latitude: 42.5426, longitude: -83.1910),  // Troy
        "WDL": CLLocationCoordinate2D(latitude: 43.6265, longitude: -89.7775),  // Wisconsin Dells

        // Mid-Atlantic
        "ALT": CLLocationCoordinate2D(latitude: 40.5145, longitude: -78.4016),  // Altoona
        "ARD": CLLocationCoordinate2D(latitude: 40.0083, longitude: -75.2904),  // Ardmore
        "BER": CLLocationCoordinate2D(latitude: 41.6356, longitude: -72.7653),  // Berlin
        "BNF": CLLocationCoordinate2D(latitude: 41.2745, longitude: -72.8172),  // Branford
        "BWE": CLLocationCoordinate2D(latitude: 39.0178, longitude: -76.7650),  // Bowie State
        "CLN": CLLocationCoordinate2D(latitude: 41.2795, longitude: -72.5283),  // Clinton
        "COT": CLLocationCoordinate2D(latitude: 39.9857, longitude: -75.8209),  // Coatesville
        "COV": CLLocationCoordinate2D(latitude: 40.0203, longitude: -79.5928),  // Connellsville
        "CRT": CLLocationCoordinate2D(latitude: 41.1899, longitude: -73.8824),  // Croton-Harmon
        "CUM": CLLocationCoordinate2D(latitude: 39.6506, longitude: -78.7580),  // Cumberland
        "CWH": CLLocationCoordinate2D(latitude: 40.0717, longitude: -74.9522),  // Cornwells Heights
        "DOW": CLLocationCoordinate2D(latitude: 40.0022, longitude: -75.7108),  // Downingtown
        "EDG": CLLocationCoordinate2D(latitude: 39.4162, longitude: -76.2928),  // Edgewood
        "EXT": CLLocationCoordinate2D(latitude: 40.0193, longitude: -75.6217),  // Exton
        "GNB": CLLocationCoordinate2D(latitude: 40.3050, longitude: -79.5469),  // Greensburg
        "GUI": CLLocationCoordinate2D(latitude: 41.2756, longitude: -72.6735),  // Guilford
        "HAE": CLLocationCoordinate2D(latitude: 39.2372, longitude: -76.6915),  // Halethorpe
        "HFY": CLLocationCoordinate2D(latitude: 39.3245, longitude: -77.7311),  // Harpers Ferry
        "HGD": CLLocationCoordinate2D(latitude: 40.4837, longitude: -78.0118),  // Huntingdon
        "JST": CLLocationCoordinate2D(latitude: 40.3297, longitude: -78.9220),  // Johnstown
        "LAB": CLLocationCoordinate2D(latitude: 40.3174, longitude: -79.3851),  // Latrobe
        "LEW": CLLocationCoordinate2D(latitude: 40.5883, longitude: -77.5800),  // Lewistown
        "MDS": CLLocationCoordinate2D(latitude: 41.2836, longitude: -72.5994),  // Madison
        "MID": CLLocationCoordinate2D(latitude: 40.1957, longitude: -76.7365),  // Middletown
        "MRB": CLLocationCoordinate2D(latitude: 39.4587, longitude: -77.9610),  // Martinsburg
        "MSA": CLLocationCoordinate2D(latitude: 39.3301, longitude: -76.4214),  // Martin Airport
        "MYS": CLLocationCoordinate2D(latitude: 41.3509, longitude: -71.9631),  // Mystic
        "NRK": CLLocationCoordinate2D(latitude: 39.6697, longitude: -75.7535),  // Newark
        "NRO": CLLocationCoordinate2D(latitude: 40.9115, longitude: -73.7843),  // New Rochelle
        "OTN": CLLocationCoordinate2D(latitude: 39.0871, longitude: -76.7064),  // Odenton
        "PAO": CLLocationCoordinate2D(latitude: 40.0428, longitude: -75.4838),  // Paoli
        "PAR": CLLocationCoordinate2D(latitude: 39.9592, longitude: -75.9221),  // Parkesburg
        "PHN": CLLocationCoordinate2D(latitude: 39.9968, longitude: -75.1551),  // North Philadelphia
        "POU": CLLocationCoordinate2D(latitude: 41.7071, longitude: -73.9375),  // Poughkeepsie
        "PRV": CLLocationCoordinate2D(latitude: 39.5580, longitude: -76.0732),  // Perryville
        "RHI": CLLocationCoordinate2D(latitude: 41.9213, longitude: -73.9513),  // Rhinecliff
        "RKV": CLLocationCoordinate2D(latitude: 39.0845, longitude: -77.1460),  // Rockville
        "STS": CLLocationCoordinate2D(latitude: 41.3053, longitude: -72.9221),  // New Haven
        "TYR": CLLocationCoordinate2D(latitude: 40.6677, longitude: -78.2405),  // Tyrone
        "WBL": CLLocationCoordinate2D(latitude: 39.2934, longitude: -76.6533),  // West Baltimore
        "WND": CLLocationCoordinate2D(latitude: 41.8520, longitude: -72.6423),  // Windsor
        "WSB": CLLocationCoordinate2D(latitude: 41.2888, longitude: -72.4480),  // Westbrook
        "YNY": CLLocationCoordinate2D(latitude: 40.9356, longitude: -73.9023),  // Yonkers

        // Midwest
        "AKY": CLLocationCoordinate2D(latitude: 38.4809, longitude: -82.6396),  // Ashland
        "ALC": CLLocationCoordinate2D(latitude: 40.9213, longitude: -81.0929),  // Alliance
        "ALD": CLLocationCoordinate2D(latitude: 37.7243, longitude: -80.6449),  // Alderson
        "BNL": CLLocationCoordinate2D(latitude: 40.5090, longitude: -88.9843),  // Bloomington-Normal
        "BYN": CLLocationCoordinate2D(latitude: 41.4803, longitude: -84.5518),  // Bryan
        "CDL": CLLocationCoordinate2D(latitude: 37.7242, longitude: -89.2166),  // Carbondale
        "CEN": CLLocationCoordinate2D(latitude: 38.5275, longitude: -89.1361),  // Centralia
        "CHM": CLLocationCoordinate2D(latitude: 40.1158, longitude: -88.2414),  // Champaign-Urbana
        "CHW": CLLocationCoordinate2D(latitude: 38.3464, longitude: -81.6385),  // Charleston
        "COI": CLLocationCoordinate2D(latitude: 39.6460, longitude: -85.1334),  // Connersville
        "CRF": CLLocationCoordinate2D(latitude: 40.0447, longitude: -86.8992),  // Crawfordsville
        "CRV": CLLocationCoordinate2D(latitude: 39.2793, longitude: -89.8893),  // Carlinville
        "DOA": CLLocationCoordinate2D(latitude: 41.9809, longitude: -86.1090),  // Dowagiac
        "DQN": CLLocationCoordinate2D(latitude: 38.0123, longitude: -89.2403),  // Du Quoin
        "DWT": CLLocationCoordinate2D(latitude: 41.0899, longitude: -88.4307),  // Dwight
        "DYE": CLLocationCoordinate2D(latitude: 41.5154, longitude: -87.5181),  // Dyer
        "EFG": CLLocationCoordinate2D(latitude: 39.1171, longitude: -88.5471),  // Effingham
        "EKH": CLLocationCoordinate2D(latitude: 41.6807, longitude: -85.9718),  // Elkhart
        "ELY": CLLocationCoordinate2D(latitude: 41.3700, longitude: -82.0967),  // Elyria
        "FTN": CLLocationCoordinate2D(latitude: 36.5257, longitude: -88.8888),  // Fulton
        "GLM": CLLocationCoordinate2D(latitude: 40.7525, longitude: -87.9981),  // Gilman
        "HIN": CLLocationCoordinate2D(latitude: 37.6750, longitude: -80.8922),  // Hinton
        "HMI": CLLocationCoordinate2D(latitude: 41.6912, longitude: -87.5065),  // Hammond-Whiting
        "HMW": CLLocationCoordinate2D(latitude: 41.5624, longitude: -87.6687),  // Homewood
        "HUN": CLLocationCoordinate2D(latitude: 38.4158, longitude: -82.4397),  // Huntington
        "JOL": CLLocationCoordinate2D(latitude: 41.5246, longitude: -88.0787),  // Joliet Gateway Center
        "KAN": CLLocationCoordinate2D(latitude: 35.4962, longitude: -80.6249),  // Kannapolis
        "KEE": CLLocationCoordinate2D(latitude: 41.2458, longitude: -89.9275),  // Kewanee
        "KKI": CLLocationCoordinate2D(latitude: 41.1193, longitude: -87.8654),  // Kankakee
        "LAF": CLLocationCoordinate2D(latitude: 40.4193, longitude: -86.8959),  // Lafayette
        "LAG": CLLocationCoordinate2D(latitude: 41.8156, longitude: -87.8715),  // La Grange
        "LCN": CLLocationCoordinate2D(latitude: 40.1482, longitude: -89.3631),  // Lincoln
        "MAT": CLLocationCoordinate2D(latitude: 39.4827, longitude: -88.3760),  // Mattoon
        "MAY": CLLocationCoordinate2D(latitude: 38.6521, longitude: -83.7711),  // Maysville
        "MDT": CLLocationCoordinate2D(latitude: 41.5496, longitude: -89.1179),  // Mendota
        "MNG": CLLocationCoordinate2D(latitude: 38.1807, longitude: -81.3240),  // Montgomery
        "NBN": CLLocationCoordinate2D(latitude: 36.1127, longitude: -89.2623),  // Newbern-Dyersburg
        "NBU": CLLocationCoordinate2D(latitude: 41.7967, longitude: -86.7458),  // New Buffalo
        "NLS": CLLocationCoordinate2D(latitude: 41.8374, longitude: -86.2524),  // Niles
        "NPV": CLLocationCoordinate2D(latitude: 41.7795, longitude: -88.1455),  // Naperville
        "PCT": CLLocationCoordinate2D(latitude: 41.3852, longitude: -89.4668),  // Princeton
        "PIA": CLLocationCoordinate2D(latitude: 40.6894, longitude: -89.5936),  // Peoria
        "PLO": CLLocationCoordinate2D(latitude: 41.6624, longitude: -88.5383),  // Plano
        "PON": CLLocationCoordinate2D(latitude: 40.8787, longitude: -88.6372),  // Pontiac
        "PRC": CLLocationCoordinate2D(latitude: 37.8566, longitude: -81.0607),  // Prince
        "REN": CLLocationCoordinate2D(latitude: 40.9433, longitude: -87.1551),  // Rensselaer
        "RTL": CLLocationCoordinate2D(latitude: 40.3109, longitude: -88.1591),  // Rantoul
        "SKY": CLLocationCoordinate2D(latitude: 41.4407, longitude: -82.7179),  // Sandusky
        "SMT": CLLocationCoordinate2D(latitude: 41.7949, longitude: -87.8097),  // Summit
        "SOB": CLLocationCoordinate2D(latitude: 41.6784, longitude: -86.2873),  // South Bend
        "SPI": CLLocationCoordinate2D(latitude: 39.8023, longitude: -89.6514),  // Springfield
        "SPM": CLLocationCoordinate2D(latitude: 38.7213, longitude: -82.9638),  // South Portsmouth
        "THN": CLLocationCoordinate2D(latitude: 37.9570, longitude: -81.0788),  // Thurmond
        "WSS": CLLocationCoordinate2D(latitude: 37.7864, longitude: -80.3040),  // White Sulphur Springs
        "WTI": CLLocationCoordinate2D(latitude: 41.4318, longitude: -85.0243),  // Waterloo

        // Mountain West
        "ACD": CLLocationCoordinate2D(latitude: 37.5922, longitude: -90.6244),  // Arcadia Valley
        "ADM": CLLocationCoordinate2D(latitude: 34.1725, longitude: -97.1255),  // Ardmore
        "ALN": CLLocationCoordinate2D(latitude: 38.9210, longitude: -90.1573),  // Alton
        "ALP": CLLocationCoordinate2D(latitude: 30.3573, longitude: -103.6615),  // Alpine
        "ARK": CLLocationCoordinate2D(latitude: 34.1139, longitude: -93.0533),  // Arkadelphia
        "BMT": CLLocationCoordinate2D(latitude: 30.0765, longitude: -94.1274),  // Beaumont
        "BRH": CLLocationCoordinate2D(latitude: 31.5830, longitude: -90.4411),  // Brookhaven
        "BRL": CLLocationCoordinate2D(latitude: 40.8058, longitude: -91.1020),  // Burlington
        "CBR": CLLocationCoordinate2D(latitude: 32.3497, longitude: -97.3823),  // Cleburne
        "CRN": CLLocationCoordinate2D(latitude: 41.0569, longitude: -94.3616),  // Creston
        "DDG": CLLocationCoordinate2D(latitude: 37.7523, longitude: -100.0170),  // Dodge City
        "DLK": CLLocationCoordinate2D(latitude: 46.8197, longitude: -95.8460),  // Detroit Lakes
        "DRT": CLLocationCoordinate2D(latitude: 29.3622, longitude: -100.9027),  // Del Rio
        "DVL": CLLocationCoordinate2D(latitude: 48.1105, longitude: -98.8614),  // Devils Lake
        "FAR": CLLocationCoordinate2D(latitude: 46.8810, longitude: -96.7854),  // Fargo
        "FMD": CLLocationCoordinate2D(latitude: 40.6296, longitude: -91.3135),  // Fort Madison
        "FMG": CLLocationCoordinate2D(latitude: 40.2472, longitude: -103.8028),  // Fort Morgan
        "GBB": CLLocationCoordinate2D(latitude: 40.9447, longitude: -90.3641),  // Galesburg
        "GCK": CLLocationCoordinate2D(latitude: 37.9644, longitude: -100.8733),  // Garden City
        "GFK": CLLocationCoordinate2D(latitude: 47.9175, longitude: -97.1108),  // Grand Forks
        "GLE": CLLocationCoordinate2D(latitude: 33.6252, longitude: -97.1409),  // Gainesville
        "GWD": CLLocationCoordinate2D(latitude: 33.5172, longitude: -90.1765),  // Greenwood
        "HAS": CLLocationCoordinate2D(latitude: 40.5843, longitude: -98.3875),  // Hastings
        "HAZ": CLLocationCoordinate2D(latitude: 31.8613, longitude: -90.3943),  // Hazlehurst
        "HEM": CLLocationCoordinate2D(latitude: 38.7073, longitude: -91.4326),  // Hermann
        "HLD": CLLocationCoordinate2D(latitude: 40.4360, longitude: -99.3701),  // Holdrege
        "HMD": CLLocationCoordinate2D(latitude: 30.5072, longitude: -90.4622),  // Hammond
        "HOP": CLLocationCoordinate2D(latitude: 33.6689, longitude: -93.5922),  // Hope
        "HUT": CLLocationCoordinate2D(latitude: 38.0557, longitude: -97.9315),  // Hutchinson
        "IDP": CLLocationCoordinate2D(latitude: 39.0869, longitude: -94.4297),  // Independence
        "JAN": CLLocationCoordinate2D(latitude: 32.3008, longitude: -90.1909),  // Jackson
        "JEF": CLLocationCoordinate2D(latitude: 38.5789, longitude: -92.1699),  // Jefferson City
        "KIL": CLLocationCoordinate2D(latitude: 31.1212, longitude: -97.7286),  // Killeen
        "KWD": CLLocationCoordinate2D(latitude: 38.5811, longitude: -90.4068),  // Kirkwood
        "LAJ": CLLocationCoordinate2D(latitude: 37.9882, longitude: -103.5436),  // La Junta
        "LAP": CLLocationCoordinate2D(latitude: 40.0292, longitude: -92.4934),  // La Plata
        "LBO": CLLocationCoordinate2D(latitude: 54.7740, longitude: -101.8481),  // Lbo
        "LCH": CLLocationCoordinate2D(latitude: 30.2381, longitude: -93.2170),  // Lake Charles
        "LEE": CLLocationCoordinate2D(latitude: 38.9126, longitude: -94.3780),  // Lee'S Summit
        "LFT": CLLocationCoordinate2D(latitude: 30.2265, longitude: -92.0145),  // Lafayette
        "LMR": CLLocationCoordinate2D(latitude: 38.0896, longitude: -102.6186),  // Lamar
        "LNK": CLLocationCoordinate2D(latitude: 40.8159, longitude: -96.7132),  // Lincoln
        "LRC": CLLocationCoordinate2D(latitude: 38.9712, longitude: -95.2305),  // Lawrence
        "LSE": CLLocationCoordinate2D(latitude: 43.8332, longitude: -91.2473),  // La Crosse
        "LVW": CLLocationCoordinate2D(latitude: 32.4940, longitude: -94.7283),  // Longview
        "MAC": CLLocationCoordinate2D(latitude: 40.4612, longitude: -90.6709),  // Macomb
        "MCB": CLLocationCoordinate2D(latitude: 31.2445, longitude: -90.4513),  // Mccomb
        "MCG": CLLocationCoordinate2D(latitude: 31.4434, longitude: -97.4048),  // Mcgregor
        "MCK": CLLocationCoordinate2D(latitude: 40.1976, longitude: -100.6258),  // Mccook
        "MHL": CLLocationCoordinate2D(latitude: 32.5515, longitude: -94.3670),  // Marshall
        "MIN": CLLocationCoordinate2D(latitude: 32.6620, longitude: -95.4891),  // Mineola
        "MKS": CLLocationCoordinate2D(latitude: 34.2582, longitude: -90.2723),  // Marks
        "MOT": CLLocationCoordinate2D(latitude: 48.2361, longitude: -101.2986),  // Minot
        "MTP": CLLocationCoordinate2D(latitude: 40.9712, longitude: -91.5508),  // Mt. Pleasant
        "MVN": CLLocationCoordinate2D(latitude: 34.3655, longitude: -92.8140),  // Malvern
        "NIB": CLLocationCoordinate2D(latitude: 30.0084, longitude: -91.8238),  // New Iberia
        "NOR": CLLocationCoordinate2D(latitude: 35.2200, longitude: -97.4430),  // Norman
        "OSC": CLLocationCoordinate2D(latitude: 41.0371, longitude: -93.7649),  // Osceola
        "OTM": CLLocationCoordinate2D(latitude: 41.0188, longitude: -92.4149),  // Ottumwa
        "PBF": CLLocationCoordinate2D(latitude: 36.7540, longitude: -90.3933),  // Poplar Bluff
        "PUR": CLLocationCoordinate2D(latitude: 35.0120, longitude: -97.3574),  // Purcell
        "PVL": CLLocationCoordinate2D(latitude: 34.7417, longitude: -97.2185),  // Pauls Valley
        "QCY": CLLocationCoordinate2D(latitude: 39.9571, longitude: -91.3685),  // Quincy
        "RAT": CLLocationCoordinate2D(latitude: 36.9011, longitude: -104.4379),  // Raton
        "RDW": CLLocationCoordinate2D(latitude: 44.5662, longitude: -92.5371),  // Red Wing
        "RUG": CLLocationCoordinate2D(latitude: 48.3698, longitude: -99.9976),  // Rugby
        "SCD": CLLocationCoordinate2D(latitude: 45.5677, longitude: -94.1491),  // St. Cloud
        "SCH": CLLocationCoordinate2D(latitude: 29.7467, longitude: -90.8152),  // Schriever
        "SED": CLLocationCoordinate2D(latitude: 38.7116, longitude: -93.2287),  // Sedalia
        "SHR": CLLocationCoordinate2D(latitude: 32.4997, longitude: -93.7567),  // Shreveport Sportran Intermodal Terminal
        "SMC": CLLocationCoordinate2D(latitude: 29.8766, longitude: -97.9410),  // San Marcos
        "SND": CLLocationCoordinate2D(latitude: 30.1400, longitude: -102.3987),  // Sanderson
        "SPL": CLLocationCoordinate2D(latitude: 46.3546, longitude: -94.7953),  // Staples
        "STN": CLLocationCoordinate2D(latitude: 48.3198, longitude: -102.3894),  // Stanley
        "TAY": CLLocationCoordinate2D(latitude: 30.5677, longitude: -97.4078),  // Taylor
        "TOH": CLLocationCoordinate2D(latitude: 43.9860, longitude: -90.5053),  // Tomah
        "TOP": CLLocationCoordinate2D(latitude: 39.0514, longitude: -95.6649),  // Topeka
        "TPL": CLLocationCoordinate2D(latitude: 31.0959, longitude: -97.3458),  // Temple
        "TRI": CLLocationCoordinate2D(latitude: 37.1727, longitude: -104.5080),  // Trinidad
        "TXA": CLLocationCoordinate2D(latitude: 33.4201, longitude: -94.0431),  // Texarkana
        "WAH": CLLocationCoordinate2D(latitude: 38.5615, longitude: -91.0127),  // Washington
        "WAR": CLLocationCoordinate2D(latitude: 38.7627, longitude: -93.7409),  // Warrensburg
        "WEL": CLLocationCoordinate2D(latitude: 37.2749, longitude: -97.3818),  // Wellington
        "WIC": CLLocationCoordinate2D(latitude: 37.6847, longitude: -97.3341),  // Wichita
        "WIN": CLLocationCoordinate2D(latitude: 44.0444, longitude: -91.6401),  // Winona
        "WNR": CLLocationCoordinate2D(latitude: 36.0677, longitude: -90.9568),  // Walnut Ridge
        "WTN": CLLocationCoordinate2D(latitude: 48.1430, longitude: -103.6209),  // Williston
        "YAZ": CLLocationCoordinate2D(latitude: 32.8485, longitude: -90.4152),  // Yazoo City

        // New England
        "AMS": CLLocationCoordinate2D(latitude: 42.9537, longitude: -74.2195),  // Amsterdam
        "AST": CLLocationCoordinate2D(latitude: 43.3134, longitude: -79.8557),  // Aldershot
        "BFX": CLLocationCoordinate2D(latitude: 42.8784, longitude: -78.8737),  // Buffalo
        "BLF": CLLocationCoordinate2D(latitude: 43.1365, longitude: -72.4446),  // Bellows Falls
        "BON": CLLocationCoordinate2D(latitude: 42.3662, longitude: -71.0611),  // Boston
        "BRA": CLLocationCoordinate2D(latitude: 42.8508, longitude: -72.5565),  // Brattleboro
        "BRK": CLLocationCoordinate2D(latitude: 43.9114, longitude: -69.9655),  // Brunswick
        "CBN": CLLocationCoordinate2D(latitude: 43.1092, longitude: -79.0584),  // Canadian Border
        "CNV": CLLocationCoordinate2D(latitude: 43.6134, longitude: -73.1713),  // Castleton
        "FED": CLLocationCoordinate2D(latitude: 43.2696, longitude: -73.5806),  // Fort Edward
        "FRA": CLLocationCoordinate2D(latitude: 42.2760, longitude: -71.4200),  // Framingham
        "FRE": CLLocationCoordinate2D(latitude: 43.8550, longitude: -70.1024),  // Freeport
        "FTC": CLLocationCoordinate2D(latitude: 43.8538, longitude: -73.3897),  // Ticonderoga
        "GFD": CLLocationCoordinate2D(latitude: 42.5855, longitude: -72.6008),  // Greenfield
        "GMS": CLLocationCoordinate2D(latitude: 43.1959, longitude: -79.5579),  // Grimsby
        "HHL": CLLocationCoordinate2D(latitude: 42.7733, longitude: -71.0864),  // Haverhill
        "HLK": CLLocationCoordinate2D(latitude: 42.2042, longitude: -72.6023),  // Holyoke
        "HUD": CLLocationCoordinate2D(latitude: 42.2539, longitude: -73.7977),  // Hudson
        "MBY": CLLocationCoordinate2D(latitude: 44.0174, longitude: -73.1698),  // Middlebury
        "MPR": CLLocationCoordinate2D(latitude: 44.2557, longitude: -72.6064),  // Montpelier-Berlin
        "NFL": CLLocationCoordinate2D(latitude: 43.1099, longitude: -79.0553),  // Niagara Falls
        "NFS": CLLocationCoordinate2D(latitude: 43.1087, longitude: -79.0633),  // Niagara Falls
        "NHT": CLLocationCoordinate2D(latitude: 42.3189, longitude: -72.6264),  // Northampton
        "OKL": CLLocationCoordinate2D(latitude: 43.4554, longitude: -79.6824),  // Oakville
        "ORB": CLLocationCoordinate2D(latitude: 43.5143, longitude: -70.3762),  // Old Orchard Beach
        "PIT": CLLocationCoordinate2D(latitude: 42.4516, longitude: -73.2538),  // Pittsfield
        "PLB": CLLocationCoordinate2D(latitude: 44.6967, longitude: -73.4463),  // Plattsburgh
        "POH": CLLocationCoordinate2D(latitude: 44.0423, longitude: -73.4588),  // Port Henry
        "ROM": CLLocationCoordinate2D(latitude: 43.1994, longitude: -75.4500),  // Rome
        "RPH": CLLocationCoordinate2D(latitude: 43.9224, longitude: -72.6655),  // Randolph
        "RSP": CLLocationCoordinate2D(latitude: 44.9949, longitude: -73.3711),  // Rouses Point
        "RTE": CLLocationCoordinate2D(latitude: 42.2102, longitude: -71.1479),  // Route 128
        "RUD": CLLocationCoordinate2D(latitude: 43.6058, longitude: -72.9815),  // Rutland
        "SAB": CLLocationCoordinate2D(latitude: 44.8124, longitude: -73.0862),  // St. Albans
        "SAO": CLLocationCoordinate2D(latitude: 43.4962, longitude: -70.4491),  // Saco
        "SAR": CLLocationCoordinate2D(latitude: 43.0828, longitude: -73.8100),  // Saratoga Springs
        "SCA": CLLocationCoordinate2D(latitude: 43.1478, longitude: -79.2560),  // St. Catherines
        "SDY": CLLocationCoordinate2D(latitude: 42.8147, longitude: -73.9429),  // Schenectady
        "SLQ": CLLocationCoordinate2D(latitude: 45.4989, longitude: -73.5073),  // St-Lambert
        "TWO": CLLocationCoordinate2D(latitude: 43.6454, longitude: -79.3808),  // Toronto
        "UCA": CLLocationCoordinate2D(latitude: 43.1039, longitude: -75.2234),  // Utica
        "VRN": CLLocationCoordinate2D(latitude: 44.1809, longitude: -73.2488),  // Ferrisburgh
        "WAB": CLLocationCoordinate2D(latitude: 44.3350, longitude: -72.7518),  // Waterbury-Stowe
        "WEM": CLLocationCoordinate2D(latitude: 43.3208, longitude: -70.6122),  // Wells
        "WHL": CLLocationCoordinate2D(latitude: 43.5547, longitude: -73.4032),  // Whitehall
        "WNM": CLLocationCoordinate2D(latitude: 43.4799, longitude: -72.3850),  // Windsor-Mt. Ascutney
        "WOB": CLLocationCoordinate2D(latitude: 42.5174, longitude: -71.1438),  // Woburn
        "WOR": CLLocationCoordinate2D(latitude: 42.2615, longitude: -71.7948),  // Worcester Union
        "WRJ": CLLocationCoordinate2D(latitude: 43.6478, longitude: -72.3173),  // White River Junction
        "WSP": CLLocationCoordinate2D(latitude: 44.1873, longitude: -73.4518),  // Westport

        // Pacific Northwest
        "ALY": CLLocationCoordinate2D(latitude: 44.6305, longitude: -123.1028),  // Albany
        "BEL": CLLocationCoordinate2D(latitude: 48.7203, longitude: -122.5113),  // Bellingham
        "BNG": CLLocationCoordinate2D(latitude: 45.7150, longitude: -121.4687),  // Bingen-White Salmon
        "BRO": CLLocationCoordinate2D(latitude: 48.5341, longitude: -113.0132),  // Browning
        "CMO": CLLocationCoordinate2D(latitude: 43.2168, longitude: -121.7816),  // Chemult
        "CTL": CLLocationCoordinate2D(latitude: 46.7175, longitude: -122.9531),  // Centralia
        "CUT": CLLocationCoordinate2D(latitude: 48.6384, longitude: -112.3316),  // Cut Bank
        "EDM": CLLocationCoordinate2D(latitude: 47.8111, longitude: -122.3841),  // Edmonds
        "EPH": CLLocationCoordinate2D(latitude: 47.3209, longitude: -119.5493),  // Ephrata
        "ESM": CLLocationCoordinate2D(latitude: 48.2755, longitude: -113.6109),  // Essex
        "EVR": CLLocationCoordinate2D(latitude: 47.9754, longitude: -122.1979),  // Everett
        "GGW": CLLocationCoordinate2D(latitude: 48.1949, longitude: -106.6362),  // Glasgow
        "GRA": CLLocationCoordinate2D(latitude: 40.0842, longitude: -105.9355),  // Granby
        "KEL": CLLocationCoordinate2D(latitude: 46.1423, longitude: -122.9130),  // Kelso-Longview
        "KFS": CLLocationCoordinate2D(latitude: 42.2255, longitude: -121.7720),  // Klamath Falls
        "LIB": CLLocationCoordinate2D(latitude: 48.3948, longitude: -115.5489),  // Libby
        "LWA": CLLocationCoordinate2D(latitude: 47.6065, longitude: -120.6440),  // Leavenworth
        "MAL": CLLocationCoordinate2D(latitude: 48.3605, longitude: -107.8722),  // Malta
        "MVW": CLLocationCoordinate2D(latitude: 48.4185, longitude: -122.3347),  // Mount Vernon
        "OLW": CLLocationCoordinate2D(latitude: 46.9913, longitude: -122.7941),  // Olympia-Lacey
        "ORC": CLLocationCoordinate2D(latitude: 45.3661, longitude: -122.5959),  // Oregon City
        "PRO": CLLocationCoordinate2D(latitude: 40.2260, longitude: -111.6640),  // Provo
        "PSC": CLLocationCoordinate2D(latitude: 46.2370, longitude: -119.0877),  // Pasco
        "SBY": CLLocationCoordinate2D(latitude: 48.5067, longitude: -111.8566),  // Shelby
        "SPT": CLLocationCoordinate2D(latitude: 48.2762, longitude: -116.5456),  // Sandpoint
        "STW": CLLocationCoordinate2D(latitude: 48.2426, longitude: -122.3499),  // Stanwood
        "TUK": CLLocationCoordinate2D(latitude: 47.4611, longitude: -122.2403),  // Tukwila
        "VAC": CLLocationCoordinate2D(latitude: 49.2738, longitude: -123.0983),  // Vancouver
        "VAN": CLLocationCoordinate2D(latitude: 45.6289, longitude: -122.6865),  // Vancouver
        "WEN": CLLocationCoordinate2D(latitude: 47.4216, longitude: -120.3066),  // Wenatchee
        "WGL": CLLocationCoordinate2D(latitude: 48.4962, longitude: -113.9792),  // West Glacier
        "WIH": CLLocationCoordinate2D(latitude: 45.6577, longitude: -120.9661),  // Wishram
        "WPT": CLLocationCoordinate2D(latitude: 48.0917, longitude: -105.6427),  // Wolf Point

        // South Central
        "ATN": CLLocationCoordinate2D(latitude: 33.6491, longitude: -85.8321),  // Anniston
        "BAS": CLLocationCoordinate2D(latitude: 30.3087, longitude: -89.3340),  // Bay St Louis
        "BDT": CLLocationCoordinate2D(latitude: 27.5285, longitude: -82.5123),  // Bradenton
        "BIX": CLLocationCoordinate2D(latitude: 30.3991, longitude: -88.8916),  // Biloxi Amtrak Sta
        "CAM": CLLocationCoordinate2D(latitude: 34.2482, longitude: -80.6252),  // Camden
        "DFB": CLLocationCoordinate2D(latitude: 26.3171, longitude: -80.1221),  // Deerfield Beach
        "DNK": CLLocationCoordinate2D(latitude: 33.3262, longitude: -81.1436),  // Denmark
        "GNS": CLLocationCoordinate2D(latitude: 34.2889, longitude: -83.8197),  // Gainesville
        "GUF": CLLocationCoordinate2D(latitude: 30.3690, longitude: -89.0948),  // Gulfport Amtrak Sta
        "HBG": CLLocationCoordinate2D(latitude: 31.3269, longitude: -89.2865),  // Hattiesburg
        "HOL": CLLocationCoordinate2D(latitude: 26.0116, longitude: -80.1679),  // Hollywood
        "JSP": CLLocationCoordinate2D(latitude: 31.6056, longitude: -81.8822),  // Jesup
        "LAK": CLLocationCoordinate2D(latitude: 28.0456, longitude: -81.9519),  // Lakeland
        "LAU": CLLocationCoordinate2D(latitude: 31.6922, longitude: -89.1279),  // Laurel
        "MEI": CLLocationCoordinate2D(latitude: 32.3642, longitude: -88.6966),  // Meridian Union
        "OKE": CLLocationCoordinate2D(latitude: 27.2519, longitude: -80.8308),  // Okeechobee
        "PAG": CLLocationCoordinate2D(latitude: 30.3678, longitude: -88.5595),  // Pascagoula
        "PAK": CLLocationCoordinate2D(latitude: 29.6497, longitude: -81.6405),  // Palatka
        "PIC": CLLocationCoordinate2D(latitude: 30.5246, longitude: -89.6803),  // Picayune
        "SBG": CLLocationCoordinate2D(latitude: 27.4966, longitude: -81.4342),  // Sebring
        "SDL": CLLocationCoordinate2D(latitude: 30.2784, longitude: -89.7826),  // Slidell
        "SFA": CLLocationCoordinate2D(latitude: 28.8085, longitude: -81.2913),  // Sanford Amtrak Auto Train
        "STP": CLLocationCoordinate2D(latitude: 27.8430, longitude: -82.6444),  // St. Petersburg
        "TCA": CLLocationCoordinate2D(latitude: 34.5785, longitude: -83.3315),  // Toccoa
        "TCL": CLLocationCoordinate2D(latitude: 33.1932, longitude: -87.5602),  // Tuscaloosa
        "WDO": CLLocationCoordinate2D(latitude: 29.7905, longitude: -82.1667),  // Waldo
        "WWD": CLLocationCoordinate2D(latitude: 28.8662, longitude: -82.0395),  // Wildwood
        "YEM": CLLocationCoordinate2D(latitude: 32.6883, longitude: -80.8469),  // Yemassee

        // Southeast
        "BCV": CLLocationCoordinate2D(latitude: 38.7973, longitude: -77.2988),  // Burke Centre
        "BNC": CLLocationCoordinate2D(latitude: 36.0942, longitude: -79.4345),  // Burlington
        "CLF": CLLocationCoordinate2D(latitude: 37.8145, longitude: -79.8274),  // Clifton Forge
        "CLP": CLLocationCoordinate2D(latitude: 38.4724, longitude: -77.9934),  // Culpeper
        "CYN": CLLocationCoordinate2D(latitude: 35.7883, longitude: -78.7822),  // Cary
        "DAN": CLLocationCoordinate2D(latitude: 36.5841, longitude: -79.3840),  // Danville
        "FAY": CLLocationCoordinate2D(latitude: 35.0550, longitude: -78.8848),  // Fayetteville
        "FBG": CLLocationCoordinate2D(latitude: 38.2984, longitude: -77.4572),  // Fredericksburg
        "GBO": CLLocationCoordinate2D(latitude: 35.3857, longitude: -78.0033),  // Goldsboro
        "GRO": CLLocationCoordinate2D(latitude: 36.0698, longitude: -79.7871),  // Greensboro
        "HVL": CLLocationCoordinate2D(latitude: 34.8912, longitude: -76.9261),  // Havelock
        "KNC": CLLocationCoordinate2D(latitude: 35.2437, longitude: -77.5845),  // Kinston
        "MHD": CLLocationCoordinate2D(latitude: 34.7214, longitude: -76.7157),  // Morehead City
        "QAN": CLLocationCoordinate2D(latitude: 38.5219, longitude: -77.2930),  // Quantico
        "SEB": CLLocationCoordinate2D(latitude: 38.9727, longitude: -76.8436),  // Seabrook
        "SOP": CLLocationCoordinate2D(latitude: 35.1751, longitude: -79.3903),  // Southern Pines
        "SSM": CLLocationCoordinate2D(latitude: 35.5328, longitude: -78.2801),  // Selma
        "STA": CLLocationCoordinate2D(latitude: 38.1476, longitude: -79.0718),  // Staunton
        "SWB": CLLocationCoordinate2D(latitude: 34.6971, longitude: -77.1396),  // Swansboro
        "WDB": CLLocationCoordinate2D(latitude: 38.6589, longitude: -77.2479),  // Woodbridge
        "WMN": CLLocationCoordinate2D(latitude: 34.2512, longitude: -77.8749),  // Wilmington

        // Southwest
        "BEN": CLLocationCoordinate2D(latitude: 31.9688, longitude: -110.2969),  // Benson
        "DEM": CLLocationCoordinate2D(latitude: 32.2718, longitude: -107.7543),  // Deming
        "GJT": CLLocationCoordinate2D(latitude: 39.0644, longitude: -108.5699),  // Grand Junction
        "GLP": CLLocationCoordinate2D(latitude: 35.5292, longitude: -108.7405),  // Gallup
        "GRI": CLLocationCoordinate2D(latitude: 38.9920, longitude: -110.1652),  // Green River
        "GSC": CLLocationCoordinate2D(latitude: 39.5479, longitude: -107.3232),  // Glenwood Springs
        "HER": CLLocationCoordinate2D(latitude: 39.6840, longitude: -110.8539),  // Helper
        "KNG": CLLocationCoordinate2D(latitude: 35.1883, longitude: -114.0528),  // Kingman
        "LDB": CLLocationCoordinate2D(latitude: 32.3501, longitude: -108.7070),  // Lordsburg
        "LMY": CLLocationCoordinate2D(latitude: 35.4810, longitude: -105.8800),  // Lamy
        "LSV": CLLocationCoordinate2D(latitude: 35.5934, longitude: -105.2128),  // Las Vegas
        "MRC": CLLocationCoordinate2D(latitude: 33.0563, longitude: -112.0471),  // Maricopa
        "NDL": CLLocationCoordinate2D(latitude: 34.8406, longitude: -114.6062),  // Needles
        "PHA": CLLocationCoordinate2D(latitude: 33.4364, longitude: -112.0130),  // Phoenix Sky Harbor Airport
        "PXN": CLLocationCoordinate2D(latitude: 33.6395, longitude: -112.1192),  // North Phoenix Metro Center Transit
        "SAF": CLLocationCoordinate2D(latitude: 35.6843, longitude: -105.9466),  // Santa Fe
        "WIP": CLLocationCoordinate2D(latitude: 39.9476, longitude: -105.8174),  // Winter Park/Fraser
        "WLO": CLLocationCoordinate2D(latitude: 35.0217, longitude: -110.6950),  // Winslow
        "WMH": CLLocationCoordinate2D(latitude: 35.2511, longitude: -112.1981),  // Williams
        "WPR": CLLocationCoordinate2D(latitude: 39.8876, longitude: -105.7632),  // Winter Park Ski Resort
        "WPS": CLLocationCoordinate2D(latitude: 39.8837, longitude: -105.7618),  // Winter Park
        "YUM": CLLocationCoordinate2D(latitude: 32.7231, longitude: -114.6156),  // Yuma

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

    // MARK: - Station to Train System Mapping

    /// Maps station codes to the train systems that serve them (as raw strings for cross-target compatibility)
    /// Used to filter stations based on user's selected train systems
    /// Keys: "NJT", "AMTRAK", "PATH", "PATCO"
    static let stationSystemStrings: [String: Set<String>] = [
        // PATH stations (PATH only)
        "PNK": ["PATH"],   // Newark PATH
        "PHR": ["PATH"],   // Harrison PATH
        "PJS": ["PATH"],   // Journal Square
        "PGR": ["PATH"],   // Grove Street
        "PEX": ["PATH"],   // Exchange Place
        "PNP": ["PATH"],   // Newport
        "PHO": ["PATH"],   // Hoboken PATH
        "PCH": ["PATH"],   // Christopher Street
        "P9S": ["PATH"],   // 9th Street
        "P14": ["PATH"],   // 14th Street
        "P23": ["PATH"],   // 23rd Street
        "P33": ["PATH"],   // 33rd Street
        "PWC": ["PATH"],   // World Trade Center

        // PATCO stations (PATCO only)
        "LND": ["PATCO"],  // Lindenwold
        "ASD": ["PATCO"],  // Ashland
        "WCT": ["PATCO"],  // Woodcrest
        "HDF": ["PATCO"],  // Haddonfield
        "WMT": ["PATCO"],  // Westmont
        "CLD": ["PATCO"],  // Collingswood
        "FRY": ["PATCO"],  // Ferry Avenue
        "BWY": ["PATCO"],  // Broadway PATCO
        "CTH": ["PATCO"],  // City Hall PATCO
        "FKS": ["PATCO"],  // Franklin Square
        "EMK": ["PATCO"],  // 8th and Market
        "NTL": ["PATCO"],  // 9-10th and Locust
        "TWL": ["PATCO"],  // 12-13th and Locust
        "FFL": ["PATCO"],  // 15-16th and Locust

        // Multi-system stations
        "NY": ["NJT", "AMTRAK"],  // New York Penn Station
        "NP": ["NJT", "AMTRAK", "PATH"],  // Newark Penn Station (PATH adjacent)
        "TR": ["NJT", "AMTRAK"],  // Trenton
        "PH": ["NJT", "AMTRAK"],  // Philadelphia 30th Street
        "WI": ["AMTRAK"],  // Wilmington
        "BA": ["AMTRAK"],  // BWI Airport
        "BL": ["AMTRAK"],  // Baltimore Penn
        "WS": ["AMTRAK"],  // Washington Union

        // Amtrak-only stations
        "BOS": ["AMTRAK"],  // Boston South
        "BBY": ["AMTRAK"],  // Boston Back Bay
        "PVD": ["AMTRAK"],  // Providence
        "NHV": ["AMTRAK"],  // New Haven
        "BRP": ["AMTRAK"],  // Bridgeport
        "STM": ["AMTRAK"],  // Stamford
        "HFD": ["AMTRAK"],  // Hartford
        "SPG": ["AMTRAK"],  // Springfield
        "HAR": ["AMTRAK"],  // Harrisburg
        "LNC": ["AMTRAK"],  // Lancaster

        // Keystone stations (Amtrak)
        "PAO": ["AMTRAK"],  // Paoli
        "EXT": ["AMTRAK"],  // Exton
        "DOW": ["AMTRAK"],  // Downingtown
        "COT": ["AMTRAK"],  // Coatesville
        "PKB": ["AMTRAK"],  // Parkesburg
        "ELT": ["AMTRAK"],  // Elizabethtown
        "MJY": ["AMTRAK"],  // Mount Joy

        // Southeast Amtrak stations
        "CLT": ["AMTRAK"],  // Charlotte
        "RGH": ["AMTRAK"],  // Raleigh
        "ATL": ["AMTRAK"],  // Atlanta
        "JAX": ["AMTRAK"],  // Jacksonville
        "MIA": ["AMTRAK"],  // Miami
        "ORL": ["AMTRAK"],  // Orlando
        "TPA": ["AMTRAK"],  // Tampa
        "SAV": ["AMTRAK"],  // Savannah
    ]

    /// Returns the raw system strings that serve a given station
    /// Defaults to NJT + Amtrak if not explicitly mapped (most NJT commuter stations)
    static func systemStringsForStation(_ code: String) -> Set<String> {
        return stationSystemStrings[code] ?? ["NJT", "AMTRAK"]
    }

    /// Check if a station should be visible based on selected system strings
    /// A station is visible if ANY of the selected systems serve it
    static func isStationVisible(_ code: String, withSystemStrings selectedSystems: Set<String>) -> Bool {
        let stationSystems = systemStringsForStation(code)
        return !stationSystems.isDisjoint(with: selectedSystems)
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
