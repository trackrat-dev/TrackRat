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

        // LIRR Stations (Long Island Rail Road)
        "Albertson", "Amagansett", "Amityville", "Atlantic Terminal",
        "Auburndale", "Babylon", "Baldwin", "Bay Shore", "Bayside",
        "Bellerose", "Bellmore", "Bellport", "Belmont Park", "Bethpage",
        "Brentwood", "Bridgehampton", "Broadway LIRR", "Carle Place",
        "Cedarhurst", "Central Islip", "Centre Avenue", "Cold Spring Harbor",
        "Copiague", "Country Life Press", "Deer Park", "Douglaston",
        "East Hampton", "East New York", "East Rockaway", "East Williston",
        "Elmont-UBS Arena", "Far Rockaway", "Farmingdale", "Floral Park",
        "Flushing Main Street", "Forest Hills", "Freeport", "Garden City",
        "Gibson", "Glen Cove", "Glen Head", "Glen Street", "Grand Central Madison",
        "Great Neck", "Great River", "Greenlawn", "Greenport", "Greenvale",
        "Hampton Bays", "Hempstead Gardens", "Hempstead", "Hewlett", "Hicksville",
        "Hollis", "Hunterspoint Avenue", "Huntington", "Inwood", "Island Park",
        "Islip", "Jamaica", "Kew Gardens", "Kings Park", "Lakeview",
        "Laurelton", "Lawrence", "Lindenhurst", "Little Neck", "Locust Manor",
        "Locust Valley", "Long Beach", "Long Island City", "Lynbrook",
        "Malverne", "Manhasset", "Massapequa Park", "Massapequa",
        "Mastic-Shirley", "Mattituck", "Medford", "Merillon Avenue", "Merrick",
        "Mets-Willets Point", "Mineola", "Montauk", "Murray Hill LIRR",
        "Nassau Boulevard", "New Hyde Park", "Northport", "Nostrand Avenue",
        "Oakdale", "Oceanside", "Oyster Bay", "Patchogue", "Pinelawn",
        "Plandome", "Port Jefferson", "Port Washington", "Queens Village",
        "Riverhead", "Rockville Centre", "Ronkonkoma", "Rosedale", "Roslyn",
        "Sayville", "Sea Cliff", "Seaford", "Smithtown", "Southampton",
        "Southold", "Speonk", "St. Albans", "St. James", "Stewart Manor",
        "Stony Brook", "Syosset", "Valley Stream", "Wantagh", "West Hempstead",
        "Westbury", "Westhampton", "Westwood LIRR", "Woodmere", "Woodside",
        "Wyandanch", "Yaphank",
        
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

        // LIRR stations (Long Island Rail Road)
        // Note: Penn Station maps to "NY" for unified experience with NJT/Amtrak
        // Atlantic Terminal uses "LAT" to avoid conflict with Atlanta "ATL"
        "Albertson": "ABT",
        "Amagansett": "AGT",
        "Amityville": "AVL",
        "Atlantic Terminal": "LAT",
        "Auburndale": "ADL",
        "Babylon": "BTA",
        "Baldwin": "BWN",
        "Bay Shore": "BSR",
        "Bayside": "BSD",
        "Bellerose": "BRS",
        "Bellmore": "BMR",
        "Bellport": "BPT",
        "Belmont Park": "BRT",
        "Bethpage": "BPG",
        "Brentwood": "BWD",
        "Bridgehampton": "BHN",
        "Broadway LIRR": "BDY",
        "Carle Place": "CPL",
        "Cedarhurst": "CHT",
        "Central Islip": "CI",
        "Centre Avenue": "CAV",
        "Cold Spring Harbor": "CSH",
        "Copiague": "CPG",
        "Country Life Press": "CLP",
        "Deer Park": "DPK",
        "Douglaston": "DGL",
        "East Hampton": "EHN",
        "East New York": "ENY",
        "East Rockaway": "ERY",
        "East Williston": "EWN",
        "Elmont-UBS Arena": "EMT",
        "Far Rockaway": "FRY",
        "Farmingdale": "FMD",
        "Floral Park": "FPK",
        "Flushing Main Street": "FLS",
        "Forest Hills": "FHL",
        "Freeport": "FPT",
        "Garden City": "GCY",
        "Gibson": "GBN",
        "Glen Cove": "GCV",
        "Glen Head": "GHD",
        "Glen Street": "GST",
        "Grand Central Madison": "GCT",
        "Great Neck": "GNK",
        "Great River": "GRV",
        "Greenlawn": "GWN",
        "Greenport": "GPT",
        "Greenvale": "GVL",
        "Hampton Bays": "HBY",
        "Hempstead Gardens": "HGN",
        "Hempstead": "HEM",
        "Hewlett": "HWT",
        "Hicksville": "HVL",
        "Hollis": "HOL",
        "Hunterspoint Avenue": "HPA",
        "Huntington": "HUN",
        "Inwood": "IWD",
        "Island Park": "IPK",
        "Islip": "ISP",
        "Jamaica": "JAM",
        "Kew Gardens": "KGN",
        "Kings Park": "KPK",
        "Lakeview": "LVW",
        "Laurelton": "LTN",
        "Lawrence": "LCE",
        "Lindenhurst": "LHT",
        "Little Neck": "LNK",
        "Locust Manor": "LMR",
        "Locust Valley": "LVL",
        "Long Beach": "LBH",
        "Long Island City": "LIC",
        "Lynbrook": "LYN",
        "Malverne": "MVN",
        "Manhasset": "MHT",
        "Massapequa Park": "MPK",
        "Massapequa": "MQA",
        "Mastic-Shirley": "MSY",
        "Mattituck": "MAK",
        "Medford": "MFD",
        "Merillon Avenue": "MAV",
        "Merrick": "MRK",
        "Mets-Willets Point": "SSM",
        "Mineola": "MIN",
        "Montauk": "MTK",
        "Murray Hill LIRR": "MHL",
        "Nassau Boulevard": "NBD",
        "New Hyde Park": "NHP",
        "Northport": "NPT",
        "Nostrand Avenue": "NAV",
        "Oakdale": "ODL",
        "Oceanside": "ODE",
        "Oyster Bay": "OBY",
        "Patchogue": "PGE",
        "Pinelawn": "PLN",
        "Plandome": "PDM",
        "Port Jefferson": "PJN",
        "Port Washington": "PWS",
        "Queens Village": "QVG",
        "Riverhead": "RHD",
        "Rockville Centre": "RVC",
        "Ronkonkoma": "RON",
        "Rosedale": "ROS",
        "Roslyn": "RSN",
        "Sayville": "SVL",
        "Sea Cliff": "SCF",
        "Seaford": "SFD",
        "Smithtown": "STN",
        "Southampton": "SHN",
        "Southold": "SHD",
        "Speonk": "SPK",
        "St. Albans": "SAB",
        "St. James": "SJM",
        "Stewart Manor": "SMR",
        "Stony Brook": "LSBK",
        "Syosset": "SYT",
        "Valley Stream": "VSM",
        "Wantagh": "WGH",
        "West Hempstead": "WHD",
        "Westbury": "WBY",
        "Westhampton": "WHN",
        "Westwood LIRR": "WWD",
        "Woodmere": "WMR",
        "Woodside": "WDD",
        "Wyandanch": "WYD",
        "Yaphank": "YPK",

        // Metro-North Railroad stations
        "Grand Central Terminal": "GCT",
        "Harlem-125th Street": "MHL",
        "Yankees-E 153 St": "MEYS",
        "Morris Heights": "MMRH",
        "University Heights": "MUNH",
        "Marble Hill": "MMBL",
        "Spuyten Duyvil": "MSDV",
        "Riverdale": "MRVD",
        "Ludlow": "MLUD",
        "Yonkers": "MYON",
        "Glenwood": "MGWD",
        "Greystone": "MGRY",
        "Hastings-on-Hudson": "MHOH",
        "Dobbs Ferry": "MDBF",
        "Ardsley-on-Hudson": "MARD",
        "Irvington": "MIRV",
        "Tarrytown": "MTTN",
        "Philipse Manor": "MPHM",
        "Scarborough": "MSCB",
        "Ossining": "MOSS",
        "Croton-Harmon": "MCRH",
        "Cortlandt": "MCRT",
        "Peekskill": "MPKS",
        "Manitou": "MMAN",
        "Garrison": "MGAR",
        "Cold Spring": "MCSP",
        "Breakneck Ridge": "MBRK",
        "Beacon": "MBCN",
        "New Hamburg": "MNHB",
        "Poughkeepsie": "MPOK",
        "Melrose": "MMEL",
        "Tremont": "MTRM",
        "Fordham": "MFOR",
        "Botanical Garden": "MBOG",
        "Williams Bridge": "MWBG",
        "Woodlawn": "MWDL",
        "Wakefield": "MWKF",
        "Mt Vernon West": "MMVW",
        "Fleetwood": "MFLT",
        "Bronxville": "MBRX",
        "Tuckahoe": "MTUC",
        "Crestwood": "MCWD",
        "Scarsdale": "MSCD",
        "Hartsdale": "MHSD",
        "White Plains": "MWPL",
        "North White Plains": "MNWP",
        "Valhalla": "MVAL",
        "Mt Pleasant": "MMTP",
        "Hawthorne": "MHWT",
        "Pleasantville": "MPLV",
        "Chappaqua": "MCHP",
        "Mt Kisco": "MMTK",
        "Bedford Hills": "MBDH",
        "Katonah": "MKAT",
        "Goldens Bridge": "MGLD",
        "Purdys": "MPRD",
        "Croton Falls": "MCFL",
        "Brewster": "MBRS",
        "Southeast": "MSET",
        "Patterson": "MPAT",
        "Pawling": "MPAW",
        "Appalachian Trail": "MAPT",
        "Harlem Valley-Wingdale": "MHVW",
        "Dover Plains": "MDVP",
        "Tenmile River": "MTMR",
        "Wassaic": "MWAS",
        "Mt Vernon East": "MMVE",
        "Pelham": "MPEL",
        "New Rochelle": "MNRC",
        "Larchmont": "MLRM",
        "Mamaroneck": "MMAM",
        "Harrison": "MHRR",
        "Rye": "MRYE",
        "Port Chester": "MPCH",
        "Greenwich": "MGRN",
        "Cos Cob": "MCOC",
        "Riverside": "MRSD",
        "Old Greenwich": "MODG",
        "Stamford": "MSTM",
        "Noroton Heights": "MNOH",
        "Darien": "MDAR",
        "Rowayton": "MROW",
        "South Norwalk": "MSNW",
        "East Norwalk": "MENW",
        "Westport": "MWPT",
        "Greens Farms": "MGRF",
        "Southport": "MSPT",
        "Fairfield": "MFFD",
        "Fairfield-Black Rock": "MFBR",
        "Bridgeport": "MBGP",
        "Stratford": "MSTR",
        "Milford": "MMIL",
        "West Haven": "MWHN",
        "New Haven": "MNHV",
        "New Haven-State St": "MNSS",
        "Glenbrook": "MGLB",
        "Springdale": "MSPD",
        "Talmadge Hill": "MTMH",
        "New Canaan": "MNCA",
        "Merritt 7": "MMR7",
        "Wilton": "MWIL",
        "Cannondale": "MCAN",
        "Branchville": "MBVL",
        "Redding": "MRED",
        "Bethel": "MBTH",
        "Danbury": "MDBY",
        "Derby-Shelton": "MDBS",
        "Ansonia": "MANS",
        "Seymour": "MSYM",
        "Beacon Falls": "MBCF",
        "Naugatuck": "MNAU",
        "Waterbury": "MWTB",

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

        // LIRR stations (Long Island Rail Road)
        "ABT": CLLocationCoordinate2D(latitude: 40.77206317, longitude: -73.64169095),  // Albertson
        "AGT": CLLocationCoordinate2D(latitude: 40.98003964, longitude: -72.13233416),  // Amagansett
        "AVL": CLLocationCoordinate2D(latitude: 40.68024859, longitude: -73.42031192),  // Amityville
        "LAT": CLLocationCoordinate2D(latitude: 40.68359596, longitude: -73.97567112),  // Atlantic Terminal
        "ADL": CLLocationCoordinate2D(latitude: 40.76144288, longitude: -73.78995927),  // Auburndale
        "BTA": CLLocationCoordinate2D(latitude: 40.70068942, longitude: -73.32405561),  // Babylon
        "BWN": CLLocationCoordinate2D(latitude: 40.65673224, longitude: -73.60716245),  // Baldwin
        "BSR": CLLocationCoordinate2D(latitude: 40.72443344, longitude: -73.25408295),  // Bay Shore
        "BSD": CLLocationCoordinate2D(latitude: 40.76315241, longitude: -73.77124986),  // Bayside
        "BRS": CLLocationCoordinate2D(latitude: 40.72220443, longitude: -73.71665289),  // Bellerose
        "BMR": CLLocationCoordinate2D(latitude: 40.66880043, longitude: -73.52886016),  // Bellmore
        "BPT": CLLocationCoordinate2D(latitude: 40.7737389, longitude: -72.94396574),   // Bellport
        "BRT": CLLocationCoordinate2D(latitude: 40.71368754, longitude: -73.72829722),  // Belmont Park
        "BPG": CLLocationCoordinate2D(latitude: 40.74303924, longitude: -73.48343821),  // Bethpage
        "BWD": CLLocationCoordinate2D(latitude: 40.78083474, longitude: -73.24361074),  // Brentwood
        "BHN": CLLocationCoordinate2D(latitude: 40.93898378, longitude: -72.31004593),  // Bridgehampton
        "BDY": CLLocationCoordinate2D(latitude: 40.76165318, longitude: -73.80176612),  // Broadway LIRR
        "CPL": CLLocationCoordinate2D(latitude: 40.74920704, longitude: -73.60365242),  // Carle Place
        "CHT": CLLocationCoordinate2D(latitude: 40.62217451, longitude: -73.72618275),  // Cedarhurst
        "CI": CLLocationCoordinate2D(latitude: 40.79185312, longitude: -73.19486082),   // Central Islip
        "CAV": CLLocationCoordinate2D(latitude: 40.64831835, longitude: -73.6639675),   // Centre Avenue
        "CSH": CLLocationCoordinate2D(latitude: 40.83563832, longitude: -73.45108591),  // Cold Spring Harbor
        "CPG": CLLocationCoordinate2D(latitude: 40.68101528, longitude: -73.39834027),  // Copiague
        "CLP": CLLocationCoordinate2D(latitude: 40.72145656, longitude: -73.62967386),  // Country Life Press
        "DPK": CLLocationCoordinate2D(latitude: 40.76948364, longitude: -73.29356494),  // Deer Park
        "DGL": CLLocationCoordinate2D(latitude: 40.76806862, longitude: -73.74941265),  // Douglaston
        "EHN": CLLocationCoordinate2D(latitude: 40.96508629, longitude: -72.19324238),  // East Hampton
        "ENY": CLLocationCoordinate2D(latitude: 40.67581191, longitude: -73.90280882),  // East New York
        "ERY": CLLocationCoordinate2D(latitude: 40.64221085, longitude: -73.65821626),  // East Rockaway
        "EWN": CLLocationCoordinate2D(latitude: 40.7560191, longitude: -73.63940764),   // East Williston
        "EMT": CLLocationCoordinate2D(latitude: 40.720074, longitude: -73.725549),      // Elmont-UBS Arena
        "FRY": CLLocationCoordinate2D(latitude: 40.60914311, longitude: -73.75054135),  // Far Rockaway
        "FMD": CLLocationCoordinate2D(latitude: 40.73591503, longitude: -73.44123878),  // Farmingdale
        "FPK": CLLocationCoordinate2D(latitude: 40.72463725, longitude: -73.70639714),  // Floral Park
        "FLS": CLLocationCoordinate2D(latitude: 40.75789494, longitude: -73.83134684),  // Flushing Main Street
        "FHL": CLLocationCoordinate2D(latitude: 40.71957556, longitude: -73.84481402),  // Forest Hills
        "FPT": CLLocationCoordinate2D(latitude: 40.65745799, longitude: -73.58232401),  // Freeport
        "GCY": CLLocationCoordinate2D(latitude: 40.72310156, longitude: -73.64036107),  // Garden City
        "GBN": CLLocationCoordinate2D(latitude: 40.64925173, longitude: -73.70183483),  // Gibson
        "GCV": CLLocationCoordinate2D(latitude: 40.86583421, longitude: -73.61616614),  // Glen Cove
        "GHD": CLLocationCoordinate2D(latitude: 40.83222531, longitude: -73.62611822),  // Glen Head
        "GST": CLLocationCoordinate2D(latitude: 40.85798112, longitude: -73.62121715),  // Glen Street
        "GCT": CLLocationCoordinate2D(latitude: 40.755162, longitude: -73.975455),      // Grand Central Madison
        "GNK": CLLocationCoordinate2D(latitude: 40.78721647, longitude: -73.72610046),  // Great Neck
        "GRV": CLLocationCoordinate2D(latitude: 40.74044444, longitude: -73.17019585),  // Great River
        "GWN": CLLocationCoordinate2D(latitude: 40.86866524, longitude: -73.36284977),  // Greenlawn
        "GPT": CLLocationCoordinate2D(latitude: 41.09970991, longitude: -72.36310396),  // Greenport
        "GVL": CLLocationCoordinate2D(latitude: 40.81571566, longitude: -73.62687152),  // Greenvale
        "HBY": CLLocationCoordinate2D(latitude: 40.87660916, longitude: -72.52394936),  // Hampton Bays
        "HGN": CLLocationCoordinate2D(latitude: 40.69491356, longitude: -73.64620888),  // Hempstead Gardens
        "HEM": CLLocationCoordinate2D(latitude: 40.71329663, longitude: -73.62503239),  // Hempstead
        "HWT": CLLocationCoordinate2D(latitude: 40.63676432, longitude: -73.70513866),  // Hewlett
        "HVL": CLLocationCoordinate2D(latitude: 40.76717491, longitude: -73.52853322),  // Hicksville
        "HOL": CLLocationCoordinate2D(latitude: 40.71018151, longitude: -73.76675252),  // Hollis
        "HPA": CLLocationCoordinate2D(latitude: 40.74239046, longitude: -73.94678997),  // Hunterspoint Avenue
        "HUN": CLLocationCoordinate2D(latitude: 40.85300971, longitude: -73.40952576),  // Huntington
        "IWD": CLLocationCoordinate2D(latitude: 40.61228773, longitude: -73.74418354),  // Inwood
        "IPK": CLLocationCoordinate2D(latitude: 40.60129906, longitude: -73.65474248),  // Island Park
        "ISP": CLLocationCoordinate2D(latitude: 40.73583449, longitude: -73.20932145),  // Islip
        "JAM": CLLocationCoordinate2D(latitude: 40.69960817, longitude: -73.80852987),  // Jamaica
        "KGN": CLLocationCoordinate2D(latitude: 40.70964917, longitude: -73.83088807),  // Kew Gardens
        "KPK": CLLocationCoordinate2D(latitude: 40.88366659, longitude: -73.25624757),  // Kings Park
        "LVW": CLLocationCoordinate2D(latitude: 40.68585582, longitude: -73.65213777),  // Lakeview
        "LTN": CLLocationCoordinate2D(latitude: 40.66848304, longitude: -73.75174687),  // Laurelton
        "LCE": CLLocationCoordinate2D(latitude: 40.6157347, longitude: -73.73589955),   // Lawrence
        "LHT": CLLocationCoordinate2D(latitude: 40.68826504, longitude: -73.36921149),  // Lindenhurst
        "LNK": CLLocationCoordinate2D(latitude: 40.77504393, longitude: -73.74064662),  // Little Neck
        "LMR": CLLocationCoordinate2D(latitude: 40.67513907, longitude: -73.76504303),  // Locust Manor
        "LVL": CLLocationCoordinate2D(latitude: 40.87446697, longitude: -73.59830284),  // Locust Valley
        "LBH": CLLocationCoordinate2D(latitude: 40.5901817, longitude: -73.66481822),   // Long Beach
        "LIC": CLLocationCoordinate2D(latitude: 40.74134343, longitude: -73.95763922),  // Long Island City
        "LYN": CLLocationCoordinate2D(latitude: 40.65605814, longitude: -73.67607083),  // Lynbrook
        "MVN": CLLocationCoordinate2D(latitude: 40.67547844, longitude: -73.66886364),  // Malverne
        "MHT": CLLocationCoordinate2D(latitude: 40.7967241, longitude: -73.69989909),   // Manhasset
        "MPK": CLLocationCoordinate2D(latitude: 40.6778591, longitude: -73.45473724),   // Massapequa Park
        "MQA": CLLocationCoordinate2D(latitude: 40.67693014, longitude: -73.46905552),  // Massapequa
        "MSY": CLLocationCoordinate2D(latitude: 40.79898815, longitude: -72.86442272),  // Mastic-Shirley
        "MAK": CLLocationCoordinate2D(latitude: 40.99179354, longitude: -72.53606243),  // Mattituck
        "MFD": CLLocationCoordinate2D(latitude: 40.81739665, longitude: -72.99890946),  // Medford
        "MAV": CLLocationCoordinate2D(latitude: 40.73516903, longitude: -73.66252148),  // Merillon Avenue
        "MRK": CLLocationCoordinate2D(latitude: 40.6638004, longitude: -73.55062102),   // Merrick
        "SSM": CLLocationCoordinate2D(latitude: 40.75239835, longitude: -73.84370059),  // Mets-Willets Point
        "MIN": CLLocationCoordinate2D(latitude: 40.74034743, longitude: -73.64086293),  // Mineola
        "MTK": CLLocationCoordinate2D(latitude: 41.04710896, longitude: -71.95388103),  // Montauk
        "MHL": CLLocationCoordinate2D(latitude: 40.76270926, longitude: -73.81453928),  // Murray Hill LIRR
        "NBD": CLLocationCoordinate2D(latitude: 40.72296245, longitude: -73.66269823),  // Nassau Boulevard
        "NHP": CLLocationCoordinate2D(latitude: 40.73075708, longitude: -73.68095886),  // New Hyde Park
        "NPT": CLLocationCoordinate2D(latitude: 40.88064972, longitude: -73.32848513),  // Northport
        "NAV": CLLocationCoordinate2D(latitude: 40.67838785, longitude: -73.94822108),  // Nostrand Avenue
        "ODL": CLLocationCoordinate2D(latitude: 40.74343275, longitude: -73.13243549),  // Oakdale
        "ODE": CLLocationCoordinate2D(latitude: 40.63472102, longitude: -73.65466582),  // Oceanside
        "OBY": CLLocationCoordinate2D(latitude: 40.87533774, longitude: -73.53403366),  // Oyster Bay
        "PGE": CLLocationCoordinate2D(latitude: 40.76187901, longitude: -73.01574451),  // Patchogue
        "PLN": CLLocationCoordinate2D(latitude: 40.74535851, longitude: -73.39960092),  // Pinelawn
        "PDM": CLLocationCoordinate2D(latitude: 40.81069853, longitude: -73.69521438),  // Plandome
        "PJN": CLLocationCoordinate2D(latitude: 40.9345531, longitude: -73.05250164),   // Port Jefferson
        "PWS": CLLocationCoordinate2D(latitude: 40.82903533, longitude: -73.687401),    // Port Washington
        "QVG": CLLocationCoordinate2D(latitude: 40.71745785, longitude: -73.73645989),  // Queens Village
        "RHD": CLLocationCoordinate2D(latitude: 40.91983928, longitude: -72.66691054),  // Riverhead
        "RVC": CLLocationCoordinate2D(latitude: 40.65831811, longitude: -73.64654935),  // Rockville Centre
        "RON": CLLocationCoordinate2D(latitude: 40.80808613, longitude: -73.10594023),  // Ronkonkoma
        "ROS": CLLocationCoordinate2D(latitude: 40.66594933, longitude: -73.73554816),  // Rosedale
        "RSN": CLLocationCoordinate2D(latitude: 40.7904781, longitude: -73.64326175),   // Roslyn
        "SVL": CLLocationCoordinate2D(latitude: 40.74035373, longitude: -73.08645531),  // Sayville
        "SCF": CLLocationCoordinate2D(latitude: 40.85236805, longitude: -73.62541695),  // Sea Cliff
        "SFD": CLLocationCoordinate2D(latitude: 40.67572393, longitude: -73.48656847),  // Seaford
        "STN": CLLocationCoordinate2D(latitude: 40.85654755, longitude: -73.19803235),  // Smithtown
        "SHN": CLLocationCoordinate2D(latitude: 40.89471874, longitude: -72.39012376),  // Southampton
        "SHD": CLLocationCoordinate2D(latitude: 41.06632089, longitude: -72.4278803),   // Southold
        "SPK": CLLocationCoordinate2D(latitude: 40.82131516, longitude: -72.70526225),  // Speonk
        "SAB": CLLocationCoordinate2D(latitude: 40.69118348, longitude: -73.76550937),  // St. Albans
        "SJM": CLLocationCoordinate2D(latitude: 40.88216931, longitude: -73.15950725),  // St. James
        "SMR": CLLocationCoordinate2D(latitude: 40.72302771, longitude: -73.68102041),  // Stewart Manor
        "LSBK": CLLocationCoordinate2D(latitude: 40.92032252, longitude: -73.12854943),   // Stony Brook
        "SYT": CLLocationCoordinate2D(latitude: 40.82485746, longitude: -73.5004456),   // Syosset
        "VSM": CLLocationCoordinate2D(latitude: 40.66151762, longitude: -73.70475875),  // Valley Stream
        "WGH": CLLocationCoordinate2D(latitude: 40.67299016, longitude: -73.50896484),  // Wantagh
        "WHD": CLLocationCoordinate2D(latitude: 40.70196099, longitude: -73.64164361),  // West Hempstead
        "WBY": CLLocationCoordinate2D(latitude: 40.75345386, longitude: -73.5858661),   // Westbury
        "WHN": CLLocationCoordinate2D(latitude: 40.83030532, longitude: -72.65032454),  // Westhampton
        "WWD": CLLocationCoordinate2D(latitude: 40.66837227, longitude: -73.68120878),  // Westwood LIRR
        "WMR": CLLocationCoordinate2D(latitude: 40.63133646, longitude: -73.71371544),  // Woodmere
        "WDD": CLLocationCoordinate2D(latitude: 40.74585067, longitude: -73.90297516),  // Woodside
        "WYD": CLLocationCoordinate2D(latitude: 40.75480101, longitude: -73.35806588),  // Wyandanch
        "YPK": CLLocationCoordinate2D(latitude: 40.82561319, longitude: -72.91587848),  // Yaphank

        // Metro-North Railroad stations
        "GCT": CLLocationCoordinate2D(latitude: 40.752998, longitude: -73.977056),     // Grand Central Terminal
        "MHL": CLLocationCoordinate2D(latitude: 40.805157, longitude: -73.939149),     // Harlem-125th Street
        "MEYS": CLLocationCoordinate2D(latitude: 40.8253, longitude: -73.9299),        // Yankees-E 153 St
        "MMRH": CLLocationCoordinate2D(latitude: 40.854252, longitude: -73.919583),    // Morris Heights
        "MUNH": CLLocationCoordinate2D(latitude: 40.862248, longitude: -73.91312),     // University Heights
        "MMBL": CLLocationCoordinate2D(latitude: 40.874333, longitude: -73.910941),    // Marble Hill
        "MSDV": CLLocationCoordinate2D(latitude: 40.878245, longitude: -73.921455),    // Spuyten Duyvil
        "MRVD": CLLocationCoordinate2D(latitude: 40.903981, longitude: -73.914126),    // Riverdale
        "MLUD": CLLocationCoordinate2D(latitude: 40.924972, longitude: -73.904612),    // Ludlow
        "MYON": CLLocationCoordinate2D(latitude: 40.935795, longitude: -73.902668),    // Yonkers
        "MGWD": CLLocationCoordinate2D(latitude: 40.950496, longitude: -73.899062),    // Glenwood
        "MGRY": CLLocationCoordinate2D(latitude: 40.972705, longitude: -73.889069),    // Greystone
        "MHOH": CLLocationCoordinate2D(latitude: 40.994109, longitude: -73.884512),    // Hastings-on-Hudson
        "MDBF": CLLocationCoordinate2D(latitude: 41.012459, longitude: -73.87949),     // Dobbs Ferry
        "MARD": CLLocationCoordinate2D(latitude: 41.026198, longitude: -73.876543),    // Ardsley-on-Hudson
        "MIRV": CLLocationCoordinate2D(latitude: 41.039993, longitude: -73.873083),    // Irvington
        "MTTN": CLLocationCoordinate2D(latitude: 41.076473, longitude: -73.864563),    // Tarrytown
        "MPHM": CLLocationCoordinate2D(latitude: 41.09492, longitude: -73.869755),     // Philipse Manor
        "MSCB": CLLocationCoordinate2D(latitude: 41.135763, longitude: -73.866163),    // Scarborough
        "MOSS": CLLocationCoordinate2D(latitude: 41.157663, longitude: -73.869281),    // Ossining
        "MCRH": CLLocationCoordinate2D(latitude: 41.189903, longitude: -73.882394),    // Croton-Harmon
        "MCRT": CLLocationCoordinate2D(latitude: 41.246259, longitude: -73.921884),    // Cortlandt
        "MPKS": CLLocationCoordinate2D(latitude: 41.285962, longitude: -73.93042),     // Peekskill
        "MMAN": CLLocationCoordinate2D(latitude: 41.332601, longitude: -73.970426),    // Manitou
        "MGAR": CLLocationCoordinate2D(latitude: 41.38178, longitude: -73.947202),     // Garrison
        "MCSP": CLLocationCoordinate2D(latitude: 41.415283, longitude: -73.95809),     // Cold Spring
        "MBRK": CLLocationCoordinate2D(latitude: 41.450181, longitude: -73.982449),    // Breakneck Ridge
        "MBCN": CLLocationCoordinate2D(latitude: 41.504007, longitude: -73.984528),    // Beacon
        "MNHB": CLLocationCoordinate2D(latitude: 41.587448, longitude: -73.947226),    // New Hamburg
        "MPOK": CLLocationCoordinate2D(latitude: 41.705839, longitude: -73.937946),    // Poughkeepsie
        "MMEL": CLLocationCoordinate2D(latitude: 40.825761, longitude: -73.915231),    // Melrose
        "MTRM": CLLocationCoordinate2D(latitude: 40.847301, longitude: -73.89955),     // Tremont
        "MFOR": CLLocationCoordinate2D(latitude: 40.8615, longitude: -73.89058),       // Fordham
        "MBOG": CLLocationCoordinate2D(latitude: 40.866555, longitude: -73.883109),    // Botanical Garden
        "MWBG": CLLocationCoordinate2D(latitude: 40.878569, longitude: -73.871064),    // Williams Bridge
        "MWDL": CLLocationCoordinate2D(latitude: 40.895361, longitude: -73.862916),    // Woodlawn
        "MWKF": CLLocationCoordinate2D(latitude: 40.905936, longitude: -73.85568),     // Wakefield
        "MMVW": CLLocationCoordinate2D(latitude: 40.912142, longitude: -73.851129),    // Mt Vernon West
        "MFLT": CLLocationCoordinate2D(latitude: 40.92699, longitude: -73.83948),      // Fleetwood
        "MBRX": CLLocationCoordinate2D(latitude: 40.93978, longitude: -73.835208),     // Bronxville
        "MTUC": CLLocationCoordinate2D(latitude: 40.949393, longitude: -73.830166),    // Tuckahoe
        "MCWD": CLLocationCoordinate2D(latitude: 40.958997, longitude: -73.820564),    // Crestwood
        "MSCD": CLLocationCoordinate2D(latitude: 40.989168, longitude: -73.808634),    // Scarsdale
        "MHSD": CLLocationCoordinate2D(latitude: 41.010333, longitude: -73.796407),    // Hartsdale
        "MWPL": CLLocationCoordinate2D(latitude: 41.032589, longitude: -73.775208),    // White Plains
        "MNWP": CLLocationCoordinate2D(latitude: 41.049806, longitude: -73.773142),    // North White Plains
        "MVAL": CLLocationCoordinate2D(latitude: 41.072819, longitude: -73.772599),    // Valhalla
        "MMTP": CLLocationCoordinate2D(latitude: 41.095877, longitude: -73.793822),    // Mt Pleasant
        "MHWT": CLLocationCoordinate2D(latitude: 41.108581, longitude: -73.79625),     // Hawthorne
        "MPLV": CLLocationCoordinate2D(latitude: 41.135222, longitude: -73.792661),    // Pleasantville
        "MCHP": CLLocationCoordinate2D(latitude: 41.158015, longitude: -73.774885),    // Chappaqua
        "MMTK": CLLocationCoordinate2D(latitude: 41.208242, longitude: -73.729778),    // Mt Kisco
        "MBDH": CLLocationCoordinate2D(latitude: 41.237316, longitude: -73.699936),    // Bedford Hills
        "MKAT": CLLocationCoordinate2D(latitude: 41.259552, longitude: -73.684155),    // Katonah
        "MGLD": CLLocationCoordinate2D(latitude: 41.294338, longitude: -73.677655),    // Goldens Bridge
        "MPRD": CLLocationCoordinate2D(latitude: 41.325775, longitude: -73.659061),    // Purdys
        "MCFL": CLLocationCoordinate2D(latitude: 41.347722, longitude: -73.662269),    // Croton Falls
        "MBRS": CLLocationCoordinate2D(latitude: 41.39447, longitude: -73.619802),     // Brewster
        "MSET": CLLocationCoordinate2D(latitude: 41.413203, longitude: -73.623787),    // Southeast
        "MPAT": CLLocationCoordinate2D(latitude: 41.511827, longitude: -73.604584),    // Patterson
        "MPAW": CLLocationCoordinate2D(latitude: 41.564205, longitude: -73.600524),    // Pawling
        "MAPT": CLLocationCoordinate2D(latitude: 41.592871, longitude: -73.588032),    // Appalachian Trail
        "MHVW": CLLocationCoordinate2D(latitude: 41.637525, longitude: -73.57145),     // Harlem Valley-Wingdale
        "MDVP": CLLocationCoordinate2D(latitude: 41.740401, longitude: -73.576502),    // Dover Plains
        "MTMR": CLLocationCoordinate2D(latitude: 41.779938, longitude: -73.558204),    // Tenmile River
        "MWAS": CLLocationCoordinate2D(latitude: 41.814722, longitude: -73.562197),    // Wassaic
        "MMVE": CLLocationCoordinate2D(latitude: 40.912161, longitude: -73.832185),    // Mt Vernon East
        "MPEL": CLLocationCoordinate2D(latitude: 40.910321, longitude: -73.810242),    // Pelham
        "MNRC": CLLocationCoordinate2D(latitude: 40.911605, longitude: -73.783807),    // New Rochelle
        "MLRM": CLLocationCoordinate2D(latitude: 40.933394, longitude: -73.759792),    // Larchmont
        "MMAM": CLLocationCoordinate2D(latitude: 40.954061, longitude: -73.736125),    // Mamaroneck
        "MHRR": CLLocationCoordinate2D(latitude: 40.969432, longitude: -73.712964),    // Harrison
        "MRYE": CLLocationCoordinate2D(latitude: 40.985922, longitude: -73.682553),    // Rye
        "MPCH": CLLocationCoordinate2D(latitude: 41.000732, longitude: -73.6647),      // Port Chester
        "MGRN": CLLocationCoordinate2D(latitude: 41.021277, longitude: -73.624621),    // Greenwich
        "MCOC": CLLocationCoordinate2D(latitude: 41.030171, longitude: -73.598306),    // Cos Cob
        "MRSD": CLLocationCoordinate2D(latitude: 41.031682, longitude: -73.588173),    // Riverside
        "MODG": CLLocationCoordinate2D(latitude: 41.033817, longitude: -73.565859),    // Old Greenwich
        "MSTM": CLLocationCoordinate2D(latitude: 41.046611, longitude: -73.542846),    // Stamford
        "MNOH": CLLocationCoordinate2D(latitude: 41.069041, longitude: -73.49788),     // Noroton Heights
        "MDAR": CLLocationCoordinate2D(latitude: 41.076913, longitude: -73.472966),    // Darien
        "MROW": CLLocationCoordinate2D(latitude: 41.077456, longitude: -73.445527),    // Rowayton
        "MSNW": CLLocationCoordinate2D(latitude: 41.09673, longitude: -73.421132),     // South Norwalk
        "MENW": CLLocationCoordinate2D(latitude: 41.103996, longitude: -73.404588),    // East Norwalk
        "MWPT": CLLocationCoordinate2D(latitude: 41.118928, longitude: -73.371413),    // Westport
        "MGRF": CLLocationCoordinate2D(latitude: 41.122265, longitude: -73.315408),    // Greens Farms
        "MSPT": CLLocationCoordinate2D(latitude: 41.134844, longitude: -73.28897),     // Southport
        "MFFD": CLLocationCoordinate2D(latitude: 41.143077, longitude: -73.257742),    // Fairfield
        "MFBR": CLLocationCoordinate2D(latitude: 41.161, longitude: -73.234336),       // Fairfield-Black Rock
        "MBGP": CLLocationCoordinate2D(latitude: 41.178677, longitude: -73.187076),    // Bridgeport
        "MSTR": CLLocationCoordinate2D(latitude: 41.194255, longitude: -73.131532),    // Stratford
        "MMIL": CLLocationCoordinate2D(latitude: 41.223231, longitude: -73.057647),    // Milford
        "MWHN": CLLocationCoordinate2D(latitude: 41.27142, longitude: -72.963488),     // West Haven
        "MNHV": CLLocationCoordinate2D(latitude: 41.296501, longitude: -72.92829),     // New Haven
        "MNSS": CLLocationCoordinate2D(latitude: 41.304979, longitude: -72.921747),    // New Haven-State St
        "MGLB": CLLocationCoordinate2D(latitude: 41.070547, longitude: -73.520021),    // Glenbrook
        "MSPD": CLLocationCoordinate2D(latitude: 41.08876, longitude: -73.517828),     // Springdale
        "MTMH": CLLocationCoordinate2D(latitude: 41.116012, longitude: -73.498149),    // Talmadge Hill
        "MNCA": CLLocationCoordinate2D(latitude: 41.146305, longitude: -73.495626),    // New Canaan
        "MMR7": CLLocationCoordinate2D(latitude: 41.146618, longitude: -73.427859),    // Merritt 7
        "MWIL": CLLocationCoordinate2D(latitude: 41.196202, longitude: -73.432434),    // Wilton
        "MCAN": CLLocationCoordinate2D(latitude: 41.21662, longitude: -73.426703),     // Cannondale
        "MBVL": CLLocationCoordinate2D(latitude: 41.26763, longitude: -73.441421),     // Branchville
        "MRED": CLLocationCoordinate2D(latitude: 41.325684, longitude: -73.4338),      // Redding
        "MBTH": CLLocationCoordinate2D(latitude: 41.376225, longitude: -73.418171),    // Bethel
        "MDBY": CLLocationCoordinate2D(latitude: 41.396146, longitude: -73.44879),     // Danbury
        "MDBS": CLLocationCoordinate2D(latitude: 41.319718, longitude: -73.083548),    // Derby-Shelton
        "MANS": CLLocationCoordinate2D(latitude: 41.344156, longitude: -73.079892),    // Ansonia
        "MSYM": CLLocationCoordinate2D(latitude: 41.395139, longitude: -73.072499),    // Seymour
        "MBCF": CLLocationCoordinate2D(latitude: 41.441752, longitude: -73.06359),     // Beacon Falls
        "MNAU": CLLocationCoordinate2D(latitude: 41.494204, longitude: -73.052655),    // Naugatuck
        "MWTB": CLLocationCoordinate2D(latitude: 41.552728, longitude: -73.046126)     // Waterbury
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
        ("Atlanta", "ATL"),
        // LIRR hubs
        ("Jamaica", "JAM"),
        ("Atlantic Terminal", "LAT"),
        ("Grand Central Madison", "GCT"),
        ("Hicksville", "HVL"),
        ("Ronkonkoma", "RON"),
        ("Babylon", "BTA"),
        ("Huntington", "HUN"),
        ("Port Washington", "PWS"),
        ("Long Beach", "LBH")
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
        "NY": ["NJT", "AMTRAK", "LIRR"],  // New York Penn Station
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

        // LIRR stations (Long Island Rail Road)
        "ABT": ["LIRR"],  // Albertson
        "AGT": ["LIRR"],  // Amagansett
        "AVL": ["LIRR"],  // Amityville
        "LAT": ["LIRR"],  // Atlantic Terminal
        "ADL": ["LIRR"],  // Auburndale
        "BTA": ["LIRR"],  // Babylon
        "BWN": ["LIRR"],  // Baldwin
        "BSR": ["LIRR"],  // Bay Shore
        "BSD": ["LIRR"],  // Bayside
        "BRS": ["LIRR"],  // Bellerose
        "BMR": ["LIRR"],  // Bellmore
        "BPT": ["LIRR"],  // Bellport
        "BRT": ["LIRR"],  // Belmont Park
        "BPG": ["LIRR"],  // Bethpage
        "BWD": ["LIRR"],  // Brentwood
        "BHN": ["LIRR"],  // Bridgehampton
        "BDY": ["LIRR"],  // Broadway LIRR
        "CPL": ["LIRR"],  // Carle Place
        "CHT": ["LIRR"],  // Cedarhurst
        "CI": ["LIRR"],   // Central Islip
        "CAV": ["LIRR"],  // Centre Avenue
        "CSH": ["LIRR"],  // Cold Spring Harbor
        "CPG": ["LIRR"],  // Copiague
        "CLP": ["LIRR"],  // Country Life Press
        "DPK": ["LIRR"],  // Deer Park
        "DGL": ["LIRR"],  // Douglaston
        "EHN": ["LIRR"],  // East Hampton
        "ENY": ["LIRR"],  // East New York
        "ERY": ["LIRR"],  // East Rockaway
        "EWN": ["LIRR"],  // East Williston
        "EMT": ["LIRR"],  // Elmont-UBS Arena
        "FRY": ["LIRR"],  // Far Rockaway
        "FMD": ["LIRR"],  // Farmingdale
        "FPK": ["LIRR"],  // Floral Park
        "FLS": ["LIRR"],  // Flushing Main Street
        "FHL": ["LIRR"],  // Forest Hills
        "FPT": ["LIRR"],  // Freeport
        "GCY": ["LIRR"],  // Garden City
        "GBN": ["LIRR"],  // Gibson
        "GCV": ["LIRR"],  // Glen Cove
        "GHD": ["LIRR"],  // Glen Head
        "GST": ["LIRR"],  // Glen Street
        "GCT": ["LIRR"],  // Grand Central Madison
        "GNK": ["LIRR"],  // Great Neck
        "GRV": ["LIRR"],  // Great River
        "GWN": ["LIRR"],  // Greenlawn
        "GPT": ["LIRR"],  // Greenport
        "GVL": ["LIRR"],  // Greenvale
        "HBY": ["LIRR"],  // Hampton Bays
        "HGN": ["LIRR"],  // Hempstead Gardens
        "HEM": ["LIRR"],  // Hempstead
        "HWT": ["LIRR"],  // Hewlett
        "HVL": ["LIRR"],  // Hicksville
        "HOL": ["LIRR"],  // Hollis
        "HPA": ["LIRR"],  // Hunterspoint Avenue
        "HUN": ["LIRR"],  // Huntington
        "IWD": ["LIRR"],  // Inwood
        "IPK": ["LIRR"],  // Island Park
        "ISP": ["LIRR"],  // Islip
        "JAM": ["LIRR"],  // Jamaica
        "KGN": ["LIRR"],  // Kew Gardens
        "KPK": ["LIRR"],  // Kings Park
        "LVW": ["LIRR"],  // Lakeview
        "LTN": ["LIRR"],  // Laurelton
        "LCE": ["LIRR"],  // Lawrence
        "LHT": ["LIRR"],  // Lindenhurst
        "LNK": ["LIRR"],  // Little Neck
        "LMR": ["LIRR"],  // Locust Manor
        "LVL": ["LIRR"],  // Locust Valley
        "LBH": ["LIRR"],  // Long Beach
        "LIC": ["LIRR"],  // Long Island City
        "LYN": ["LIRR"],  // Lynbrook
        "MVN": ["LIRR"],  // Malverne
        "MHT": ["LIRR"],  // Manhasset
        "MPK": ["LIRR"],  // Massapequa Park
        "MQA": ["LIRR"],  // Massapequa
        "MSY": ["LIRR"],  // Mastic-Shirley
        "MAK": ["LIRR"],  // Mattituck
        "MFD": ["LIRR"],  // Medford
        "MAV": ["LIRR"],  // Merillon Avenue
        "MRK": ["LIRR"],  // Merrick
        "SSM": ["LIRR"],  // Mets-Willets Point
        "MIN": ["LIRR"],  // Mineola
        "MTK": ["LIRR"],  // Montauk
        "MHL": ["LIRR"],  // Murray Hill LIRR
        "NBD": ["LIRR"],  // Nassau Boulevard
        "NHP": ["LIRR"],  // New Hyde Park
        "NPT": ["LIRR"],  // Northport
        "NAV": ["LIRR"],  // Nostrand Avenue
        "ODL": ["LIRR"],  // Oakdale
        "ODE": ["LIRR"],  // Oceanside
        "OBY": ["LIRR"],  // Oyster Bay
        "PGE": ["LIRR"],  // Patchogue
        "PLN": ["LIRR"],  // Pinelawn
        "PDM": ["LIRR"],  // Plandome
        "PJN": ["LIRR"],  // Port Jefferson
        "PWS": ["LIRR"],  // Port Washington
        "QVG": ["LIRR"],  // Queens Village
        "RHD": ["LIRR"],  // Riverhead
        "RVC": ["LIRR"],  // Rockville Centre
        "RON": ["LIRR"],  // Ronkonkoma
        "ROS": ["LIRR"],  // Rosedale
        "RSN": ["LIRR"],  // Roslyn
        "SVL": ["LIRR"],  // Sayville
        "SCF": ["LIRR"],  // Sea Cliff
        "SFD": ["LIRR"],  // Seaford
        "STN": ["LIRR"],  // Smithtown
        "SHN": ["LIRR"],  // Southampton
        "SHD": ["LIRR"],  // Southold
        "SPK": ["LIRR"],  // Speonk
        "SAB": ["LIRR"],  // St. Albans
        "SJM": ["LIRR"],  // St. James
        "SMR": ["LIRR"],  // Stewart Manor
        "LSBK": ["LIRR"],   // Stony Brook
        "SYT": ["LIRR"],  // Syosset
        "VSM": ["LIRR"],  // Valley Stream
        "WGH": ["LIRR"],  // Wantagh
        "WHD": ["LIRR"],  // West Hempstead
        "WBY": ["LIRR"],  // Westbury
        "WHN": ["LIRR"],  // Westhampton
        "WWD": ["LIRR"],  // Westwood LIRR
        "WMR": ["LIRR"],  // Woodmere
        "WDD": ["LIRR"],  // Woodside
        "WYD": ["LIRR"],  // Wyandanch
        "YPK": ["LIRR"],  // Yaphank

        // Metro-North Railroad stations
        "GCT": ["MNR", "LIRR"],  // Grand Central Terminal (shared)
        "MHL": ["MNR"],          // Harlem-125th Street
        "MEYS": ["MNR"],         // Yankees-E 153 St
        "MMRH": ["MNR"],         // Morris Heights
        "MUNH": ["MNR"],         // University Heights
        "MMBL": ["MNR"],         // Marble Hill
        "MSDV": ["MNR"],         // Spuyten Duyvil
        "MRVD": ["MNR"],         // Riverdale
        "MLUD": ["MNR"],         // Ludlow
        "MYON": ["MNR"],         // Yonkers
        "MGWD": ["MNR"],         // Glenwood
        "MGRY": ["MNR"],         // Greystone
        "MHOH": ["MNR"],         // Hastings-on-Hudson
        "MDBF": ["MNR"],         // Dobbs Ferry
        "MARD": ["MNR"],         // Ardsley-on-Hudson
        "MIRV": ["MNR"],         // Irvington
        "MTTN": ["MNR"],         // Tarrytown
        "MPHM": ["MNR"],         // Philipse Manor
        "MSCB": ["MNR"],         // Scarborough
        "MOSS": ["MNR"],         // Ossining
        "MCRH": ["MNR"],         // Croton-Harmon
        "MCRT": ["MNR"],         // Cortlandt
        "MPKS": ["MNR"],         // Peekskill
        "MMAN": ["MNR"],         // Manitou
        "MGAR": ["MNR"],         // Garrison
        "MCSP": ["MNR"],         // Cold Spring
        "MBRK": ["MNR"],         // Breakneck Ridge
        "MBCN": ["MNR"],         // Beacon
        "MNHB": ["MNR"],         // New Hamburg
        "MPOK": ["MNR"],         // Poughkeepsie
        "MMEL": ["MNR"],         // Melrose
        "MTRM": ["MNR"],         // Tremont
        "MFOR": ["MNR"],         // Fordham
        "MBOG": ["MNR"],         // Botanical Garden
        "MWBG": ["MNR"],         // Williams Bridge
        "MWDL": ["MNR"],         // Woodlawn
        "MWKF": ["MNR"],         // Wakefield
        "MMVW": ["MNR"],         // Mt Vernon West
        "MFLT": ["MNR"],         // Fleetwood
        "MBRX": ["MNR"],         // Bronxville
        "MTUC": ["MNR"],         // Tuckahoe
        "MCWD": ["MNR"],         // Crestwood
        "MSCD": ["MNR"],         // Scarsdale
        "MHSD": ["MNR"],         // Hartsdale
        "MWPL": ["MNR"],         // White Plains
        "MNWP": ["MNR"],         // North White Plains
        "MVAL": ["MNR"],         // Valhalla
        "MMTP": ["MNR"],         // Mt Pleasant
        "MHWT": ["MNR"],         // Hawthorne
        "MPLV": ["MNR"],         // Pleasantville
        "MCHP": ["MNR"],         // Chappaqua
        "MMTK": ["MNR"],         // Mt Kisco
        "MBDH": ["MNR"],         // Bedford Hills
        "MKAT": ["MNR"],         // Katonah
        "MGLD": ["MNR"],         // Goldens Bridge
        "MPRD": ["MNR"],         // Purdys
        "MCFL": ["MNR"],         // Croton Falls
        "MBRS": ["MNR"],         // Brewster
        "MSET": ["MNR"],         // Southeast
        "MPAT": ["MNR"],         // Patterson
        "MPAW": ["MNR"],         // Pawling
        "MAPT": ["MNR"],         // Appalachian Trail
        "MHVW": ["MNR"],         // Harlem Valley-Wingdale
        "MDVP": ["MNR"],         // Dover Plains
        "MTMR": ["MNR"],         // Tenmile River
        "MWAS": ["MNR"],         // Wassaic
        "MMVE": ["MNR"],         // Mt Vernon East
        "MPEL": ["MNR"],         // Pelham
        "MNRC": ["MNR"],         // New Rochelle
        "MLRM": ["MNR"],         // Larchmont
        "MMAM": ["MNR"],         // Mamaroneck
        "MHRR": ["MNR"],         // Harrison
        "MRYE": ["MNR"],         // Rye
        "MPCH": ["MNR"],         // Port Chester
        "MGRN": ["MNR"],         // Greenwich
        "MCOC": ["MNR"],         // Cos Cob
        "MRSD": ["MNR"],         // Riverside
        "MODG": ["MNR"],         // Old Greenwich
        "MSTM": ["MNR"],         // Stamford
        "MNOH": ["MNR"],         // Noroton Heights
        "MDAR": ["MNR"],         // Darien
        "MROW": ["MNR"],         // Rowayton
        "MSNW": ["MNR"],         // South Norwalk
        "MENW": ["MNR"],         // East Norwalk
        "MWPT": ["MNR"],         // Westport
        "MGRF": ["MNR"],         // Greens Farms
        "MSPT": ["MNR"],         // Southport
        "MFFD": ["MNR"],         // Fairfield
        "MFBR": ["MNR"],         // Fairfield-Black Rock
        "MBGP": ["MNR"],         // Bridgeport
        "MSTR": ["MNR"],         // Stratford
        "MMIL": ["MNR"],         // Milford
        "MWHN": ["MNR"],         // West Haven
        "MNHV": ["MNR"],         // New Haven
        "MNSS": ["MNR"],         // New Haven-State St
        "MGLB": ["MNR"],         // Glenbrook
        "MSPD": ["MNR"],         // Springdale
        "MTMH": ["MNR"],         // Talmadge Hill
        "MNCA": ["MNR"],         // New Canaan
        "MMR7": ["MNR"],         // Merritt 7
        "MWIL": ["MNR"],         // Wilton
        "MCAN": ["MNR"],         // Cannondale
        "MBVL": ["MNR"],         // Branchville
        "MRED": ["MNR"],         // Redding
        "MBTH": ["MNR"],         // Bethel
        "MDBY": ["MNR"],         // Danbury
        "MDBS": ["MNR"],         // Derby-Shelton
        "MANS": ["MNR"],         // Ansonia
        "MSYM": ["MNR"],         // Seymour
        "MBCF": ["MNR"],         // Beacon Falls
        "MNAU": ["MNR"],         // Naugatuck
        "MWTB": ["MNR"],         // Waterbury
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
