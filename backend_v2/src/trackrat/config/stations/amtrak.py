"""Amtrak station configuration."""

# Amtrak-specific station names (stations not in NJT network)
AMTRAK_STATION_NAMES: dict[str, str] = {
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
    # Nationwide Amtrak stations
    # Discovery hubs and major junctions
    "CHI": "Chicago Union Station",
    "STL": "St. Louis",
    "MKE": "Milwaukee",
    "LAX": "Los Angeles Union Station",
    "SEA": "Seattle King Street",
    "PDX": "Portland Union Station",
    "EMY": "Emeryville",
    "SAC": "Sacramento",
    "NOL": "New Orleans",
    "SAS": "San Antonio",
    "DEN": "Denver Union Station",
    # California / Southwest corridor stations
    "SBA": "Santa Barbara",
    "SLO": "San Luis Obispo",
    "SJC": "San Jose",
    "OSD": "Oceanside",
    "SNA": "Santa Ana",
    "FUL": "Fullerton",
    "OLT": "San Diego Old Town",
    "ABQ": "Albuquerque",
    "FLG": "Flagstaff",
    "TUS": "Tucson",
    "ELP": "El Paso",
    "RNO": "Reno",
    "TRU": "Truckee",
    # Pacific Northwest / Empire Builder
    "SPK": "Spokane",
    "TAC": "Tacoma",
    "EUG": "Eugene",
    "SLM": "Salem",
    "SLC": "Salt Lake City",
    "WFH": "Whitefish",
    "GPK": "East Glacier Park",
    "HAV": "Havre",
    "MSP": "St. Paul-Minneapolis",
    # Texas / South Central
    "DAL": "Dallas",
    "FTW": "Fort Worth",
    "HOS": "Houston",
    "AUS": "Austin",
    "LRK": "Little Rock",
    "MEM": "Memphis",
    # Midwest / Great Lakes
    "KCY": "Kansas City",
    "OKC": "Oklahoma City",
    "OMA": "Omaha",
    "IND": "Indianapolis",
    "CIN": "Cincinnati",
    "CLE": "Cleveland",
    "TOL": "Toledo",
    "DET": "Detroit",
    "GRR": "Grand Rapids",
    "PGH": "Pittsburgh",
    # Northeast extensions
    "ALB": "Albany-Rensselaer",
    "SYR": "Syracuse",
    "ROC": "Rochester",
    "BUF": "Buffalo Depew",
    "MTR": "Montreal",
    "POR": "Portland ME",
    "ESX": "Essex Junction",
    "BTN": "Burlington VT",
    # Virginia / Southeast inland
    "LYH": "Lynchburg",
    "NPN": "Newport News",
    "WBG": "Williamsburg",
    "CLB": "Columbia SC",
    "BHM": "Birmingham",
    "MOE": "Mobile",
    # California Amtrak stations
    "ANA": "Anaheim",
    "ARC": "Arcata",
    "ARN": "Auburn",
    "BAR": "Barstow",
    "BBK": "Burbank",
    "BFD": "Bakersfield",
    "BKY": "Berkeley",
    "BUR": "Burbank",
    "CIC": "Chico",
    "CLM": "Claremont",
    "CML": "Camarillo",
    "COX": "Colfax",
    "CPN": "Carpinteria",
    "CWT": "Chatsworth",
    "DAV": "Davis",
    "DBP": "Dublin-Pleasanton",
    "DUN": "Dunsmuir",
    "ELK": "Elko",
    "FFV": "Fairfield-Vacaville",
    "FMT": "Fremont",
    "FNO": "Fresno",
    "GAC": "Santa Clara Great America",
    "GDL": "Glendale",
    "GLY": "Gilroy",
    "GTA": "Goleta",
    "GUA": "Guadalupe",
    "GVB": "Grover Beach",
    "HAY": "Hayward",
    "HNF": "Hanford",
    "HSU": "Arcata",
    "IRV": "Irvine",
    "LOD": "Lodi",
    "LPS": "Lompoc-Surf",
    "LVS": "Las Vegas",
    "MCD": "Merced",
    "MPK": "Moorpark",
    "MRV": "Marysville",
    "MTZ": "Martinez",
    "MYU": "Seaside-Marina",
    "NHL": "Santa Clarita-Newhall",
    "NRG": "Northridge",
    "OAC": "Oakland Coliseum/Airport",
    "OKJ": "Oakland",
    "ONA": "Ontario",
    "OXN": "Oxnard",
    "POS": "Pomona",
    "PRB": "Paso Robles",
    "PSN": "Palm Springs",
    "PTC": "Petaluma",
    "RDD": "Redding",
    "RIC": "Richmond",
    "RIV": "Riverside",
    "RLN": "Rocklin",
    "RSV": "Roseville",
    "SCC": "Santa Clara",
    "SFC": "San Francisco",
    "SIM": "Simi Valley",
    "SKN": "Stockton",
    "SKT": "Stockton",
    "SMN": "Santa Monica Pier",
    "SNB": "San Bernardino",
    "SNC": "San Juan Capistrano",
    "SNP": "San Clemente Pier",
    "SNS": "Salinas",
    "SOL": "Solana Beach",
    "SUI": "Suisun-Fairfield",
    "VAL": "Vallejo",
    "VEC": "Ventura",
    "VNC": "Van Nuys",
    "VRV": "Victorville",
    "WNN": "Winnemucca",
    "WTS": "Willits Calif Western Railroad Depot",
    # Great Lakes Amtrak stations
    "ALI": "Albion",
    "ARB": "Ann Arbor",
    "BAM": "Bangor",
    "BTL": "Battle Creek",
    "CBS": "Columbus",
    "DER": "Dearborn",
    "DRD": "Durand",
    "ERI": "Erie",
    "FLN": "Flint",
    "GLN": "Glenview",
    "HOM": "Holland",
    "JXN": "Jackson",
    "KAL": "Kalamazoo",
    "LNS": "East Lansing",
    "LPE": "Lapeer",
    "MKA": "General Mitchell Intl. Airport",
    "PNT": "Pontiac, MI",
    "POG": "Portage",
    "PTH": "Port Huron",
    "ROY": "Royal Oak",
    "SJM": "St. Joseph-Benton Harbor",
    "SVT": "Sturtevant",
    "TRM": "Troy",
    "WDL": "Wisconsin Dells",
    # Mid-Atlantic Amtrak stations
    "ALT": "Altoona",
    "ARD": "Ardmore",
    "BER": "Berlin",
    "BNF": "Branford",
    "BWE": "Bowie State",
    "CLN": "Clinton",
    "COT": "Coatesville",
    "COV": "Connellsville",
    "CRT": "Croton-Harmon",
    "CUM": "Cumberland",
    "CWH": "Cornwells Heights",
    "DOW": "Downingtown",
    "EDG": "Edgewood",
    "EXT": "Exton",
    "GNB": "Greensburg",
    "GUI": "Guilford",
    "HAE": "Halethorpe",
    "HFY": "Harpers Ferry",
    "HGD": "Huntingdon",
    "JST": "Johnstown",
    "LAB": "Latrobe",
    "LEW": "Lewistown",
    "MDS": "Madison",
    "MID": "Middletown",
    "MRB": "Martinsburg",
    "MSA": "Martin Airport",
    "MYS": "Mystic",
    "NRK": "Newark",
    "NRO": "New Rochelle",
    "OTN": "Odenton",
    "PAO": "Paoli",
    "PAR": "Parkesburg",
    "PHN": "North Philadelphia",
    "POU": "Poughkeepsie",
    "PRV": "Perryville",
    "RHI": "Rhinecliff",
    "RKV": "Rockville",
    "STS": "New Haven-State St",
    "TYR": "Tyrone",
    "WBL": "West Baltimore",
    "WND": "Windsor",
    "WSB": "Westbrook",
    "YNY": "Yonkers",
    # Midwest Amtrak stations
    "AKY": "Ashland",
    "ALC": "Alliance",
    "ALD": "Alderson",
    "BNL": "Bloomington-Normal",
    "BYN": "Bryan",
    "CDL": "Carbondale",
    "CEN": "Centralia",
    "CHM": "Champaign-Urbana",
    "CHW": "Charleston",
    "COI": "Connersville",
    "CRF": "Crawfordsville",
    "CRV": "Carlinville",
    "DOA": "Dowagiac",
    "DQN": "Du Quoin",
    "DWT": "Dwight",
    "DYE": "Dyer",
    "EFG": "Effingham",
    "EKH": "Elkhart",
    "ELY": "Elyria",
    "FTN": "Fulton",
    "GLM": "Gilman",
    "HIN": "Hinton",
    "HMI": "Hammond-Whiting",
    "HMW": "Homewood",
    "HUN": "Huntington",
    "JOL": "Joliet Gateway Center",
    "KAN": "Kannapolis",
    "KEE": "Kewanee",
    "KKI": "Kankakee",
    "LAF": "Lafayette",
    "LAG": "La Grange",
    "LCN": "Lincoln",
    "MAT": "Mattoon",
    "MAY": "Maysville",
    "MDT": "Mendota",
    "MNG": "Montgomery",
    "NBN": "Newbern-Dyersburg",
    "NBU": "New Buffalo",
    "NLS": "Niles",
    "NPV": "Naperville",
    "PCT": "Princeton",
    "PIA": "Peoria",
    "PLO": "Plano",
    "PON": "Pontiac, IL",
    "PRC": "Prince",
    "REN": "Rensselaer",
    "RTL": "Rantoul",
    "SKY": "Sandusky",
    "SMT": "Summit",
    "SOB": "South Bend",
    "SPI": "Springfield",
    "SPM": "South Portsmouth",
    "THN": "Thurmond",
    "WSS": "White Sulphur Springs",
    "WTI": "Waterloo",
    # Mountain West Amtrak stations
    "ACD": "Arcadia Valley",
    "ADM": "Ardmore",
    "ALN": "Alton",
    "ALP": "Alpine",
    "ARK": "Arkadelphia",
    "BMT": "Beaumont",
    "BRH": "Brookhaven",
    "BRL": "Burlington",
    "CBR": "Cleburne",
    "CRN": "Creston",
    "DDG": "Dodge City",
    "DLK": "Detroit Lakes",
    "DRT": "Del Rio",
    "DVL": "Devils Lake",
    "FAR": "Fargo",
    "FMD": "Fort Madison",
    "FMG": "Fort Morgan",
    "GBB": "Galesburg",
    "GCK": "Garden City",
    "GFK": "Grand Forks",
    "GLE": "Gainesville",
    "GWD": "Greenwood",
    "HAS": "Hastings",
    "HAZ": "Hazlehurst",
    "HEM": "Hermann",
    "HLD": "Holdrege",
    "HMD": "Hammond",
    "HOP": "Hope",
    "HUT": "Hutchinson",
    "IDP": "Independence",
    "JAN": "Jackson",
    "JEF": "Jefferson City",
    "KIL": "Killeen",
    "KWD": "Kirkwood",
    "LAJ": "La Junta",
    "LAP": "La Plata",
    "LBO": "Lbo",
    "LCH": "Lake Charles",
    "LEE": "Lee'S Summit",
    "LFT": "Lafayette",
    "LMR": "Lamar",
    "LNK": "Lincoln",
    "LRC": "Lawrence",
    "LSE": "La Crosse",
    "LVW": "Longview",
    "MAC": "Macomb",
    "MCB": "Mccomb",
    "MCG": "Mcgregor",
    "MCK": "Mccook",
    "MHL": "Marshall",
    "MIN": "Mineola",
    "MKS": "Marks",
    "MOT": "Minot",
    "MTP": "Mt. Pleasant",
    "MVN": "Malvern",
    "NIB": "New Iberia",
    "NOR": "Norman",
    "OSC": "Osceola",
    "OTM": "Ottumwa",
    "PBF": "Poplar Bluff",
    "PUR": "Purcell",
    "PVL": "Pauls Valley",
    "QCY": "Quincy",
    "RAT": "Raton",
    "RDW": "Red Wing",
    "RUG": "Rugby",
    "SCD": "St. Cloud",
    "SCH": "Schriever",
    "SED": "Sedalia",
    "SHR": "Shreveport Sportran Intermodal Terminal",
    "SMC": "San Marcos",
    "SND": "Sanderson",
    "SPL": "Staples",
    "STN": "Stanley",
    "TAY": "Taylor",
    "TOH": "Tomah",
    "TOP": "Topeka",
    "TPL": "Temple",
    "TRI": "Trinidad",
    "TXA": "Texarkana",
    "WAH": "Washington",
    "WAR": "Warrensburg",
    "WEL": "Wellington",
    "WIC": "Wichita",
    "WIN": "Winona",
    "WNR": "Walnut Ridge",
    "WTN": "Williston",
    "YAZ": "Yazoo City",
    # New England Amtrak stations
    "AMS": "Amsterdam",
    "AST": "Aldershot",
    "BFX": "Buffalo",
    "BLF": "Bellows Falls",
    "BON": "Boston North",
    "BRA": "Brattleboro",
    "BRK": "Brunswick",
    "CBN": "Canadian Border",
    "CNV": "Castleton",
    "FED": "Fort Edward",
    "FRA": "Framingham",
    "FRE": "Freeport",
    "FTC": "Ticonderoga",
    "GFD": "Greenfield",
    "GMS": "Grimsby",
    "HHL": "Haverhill",
    "HLK": "Holyoke",
    "HUD": "Hudson",
    "MBY": "Middlebury",
    "MPR": "Montpelier-Berlin",
    "NFL": "Niagara Falls",
    "NFS": "Niagara Falls",
    "NHT": "Northampton",
    "OKL": "Oakville",
    "ORB": "Old Orchard Beach",
    "PIT": "Pittsfield",
    "PLB": "Plattsburgh",
    "POH": "Port Henry",
    "ROM": "Rome",
    "RPH": "Randolph",
    "RSP": "Rouses Point",
    "RTE": "Route 128",
    "RUD": "Rutland",
    "SAB": "St. Albans",
    "SAO": "Saco",
    "SAR": "Saratoga Springs",
    "SCA": "St. Catherines",
    "SDY": "Schenectady",
    "SLQ": "St-Lambert",
    "TWO": "Toronto",
    "UCA": "Utica",
    "VRN": "Ferrisburgh",
    "WAB": "Waterbury-Stowe",
    "WEM": "Wells",
    "WHL": "Whitehall",
    "WNM": "Windsor-Mt. Ascutney",
    "WOB": "Woburn",
    "WOR": "Worcester Union",
    "WRJ": "White River Junction",
    "WSP": "Westport",
    # Pacific Northwest Amtrak stations
    "ALY": "Albany",
    "BEL": "Bellingham",
    "BNG": "Bingen-White Salmon",
    "BRO": "Browning",
    "CMO": "Chemult",
    "CTL": "Centralia",
    "CUT": "Cut Bank",
    "EDM": "Edmonds",
    "EPH": "Ephrata",
    "ESM": "Essex",
    "EVR": "Everett",
    "GGW": "Glasgow",
    "GRA": "Granby",
    "KEL": "Kelso-Longview",
    "KFS": "Klamath Falls",
    "LIB": "Libby",
    "LWA": "Leavenworth",
    "MAL": "Malta",
    "MVW": "Mount Vernon",
    "OLW": "Olympia-Lacey",
    "ORC": "Oregon City",
    "PRO": "Provo",
    "PSC": "Pasco",
    "SBY": "Shelby",
    "SPT": "Sandpoint",
    "STW": "Stanwood",
    "TUK": "Tukwila",
    "VAC": "Vancouver, BC",
    "VAN": "Vancouver, WA",
    "WEN": "Wenatchee",
    "WGL": "West Glacier",
    "WIH": "Wishram",
    "WPT": "Wolf Point",
    # South Central Amtrak stations
    "ATN": "Anniston",
    "BAS": "Bay St Louis",
    "BDT": "Bradenton",
    "BIX": "Biloxi Amtrak Sta",
    "CAM": "Camden",
    "DFB": "Deerfield Beach",
    "DNK": "Denmark",
    "GNS": "Gainesville",
    "GUF": "Gulfport Amtrak Sta",
    "HBG": "Hattiesburg",
    "HOL": "Hollywood",
    "JSP": "Jesup",
    "LAK": "Lakeland",
    "LAU": "Laurel",
    "MEI": "Meridian Union",
    "OKE": "Okeechobee",
    "PAG": "Pascagoula",
    "PAK": "Palatka",
    "PIC": "Picayune",
    "SBG": "Sebring",
    "SDL": "Slidell",
    "SFA": "Sanford Amtrak Auto Train",
    "STP": "St. Petersburg",
    "TCA": "Toccoa",
    "TCL": "Tuscaloosa",
    "WDO": "Waldo",
    "WWD": "Wildwood",
    "YEM": "Yemassee",
    # Southeast Amtrak stations
    "BCV": "Burke Centre",
    "BNC": "Burlington",
    "CLF": "Clifton Forge",
    "CLP": "Culpeper",
    "CYN": "Cary",
    "DAN": "Danville",
    "FAY": "Fayetteville",
    "FBG": "Fredericksburg",
    "GBO": "Goldsboro",
    "GRO": "Greensboro",
    "HVL": "Havelock",
    "KNC": "Kinston",
    "MHD": "Morehead City",
    "QAN": "Quantico",
    "SEB": "Seabrook",
    "SOP": "Southern Pines",
    "SSM": "Selma",
    "STA": "Staunton",
    "SWB": "Swansboro",
    "WDB": "Woodbridge",
    "WMN": "Wilmington",
    # Southwest Amtrak stations
    "BEN": "Benson",
    "DEM": "Deming",
    "GJT": "Grand Junction",
    "GLP": "Gallup",
    "GRI": "Green River",
    "GSC": "Glenwood Springs",
    "HER": "Helper",
    "KNG": "Kingman",
    "LDB": "Lordsburg",
    "LMY": "Lamy",
    "LSV": "Las Vegas",
    "MRC": "Maricopa",
    "NDL": "Needles",
    "PHA": "Phoenix Sky Harbor Airport",
    "PXN": "North Phoenix Metro Center Transit",
    "SAF": "Santa Fe",
    "WIP": "Winter Park/Fraser",
    "WLO": "Winslow",
    "WMH": "Williams",
    "WPR": "Winter Park Ski Resort",
    "WPS": "Winter Park",
    "YUM": "Yuma",
}


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
    # Nationwide stations (identity mappings)
    "CHI": "CHI",  # Chicago Union Station
    "STL": "STL",  # St. Louis
    "MKE": "MKE",  # Milwaukee
    "LAX": "LAX",  # Los Angeles Union Station
    "SEA": "SEA",  # Seattle King Street
    "PDX": "PDX",  # Portland Union Station
    "EMY": "EMY",  # Emeryville
    "SAC": "SAC",  # Sacramento
    "NOL": "NOL",  # New Orleans
    "SAS": "SAS",  # San Antonio
    "DEN": "DEN",  # Denver Union Station
    # California / Southwest
    "SBA": "SBA",  # Santa Barbara
    "SLO": "SLO",  # San Luis Obispo
    "SJC": "SJC",  # San Jose
    "OSD": "OSD",  # Oceanside
    "SNA": "SNA",  # Santa Ana
    "FUL": "FUL",  # Fullerton
    "OLT": "OLT",  # San Diego Old Town
    "ABQ": "ABQ",  # Albuquerque
    "FLG": "FLG",  # Flagstaff
    "TUS": "TUS",  # Tucson
    "ELP": "ELP",  # El Paso
    "RNO": "RNO",  # Reno
    "TRU": "TRU",  # Truckee
    # Pacific Northwest
    "SPK": "SPK",  # Spokane
    "TAC": "TAC",  # Tacoma
    "EUG": "EUG",  # Eugene
    "SLM": "SLM",  # Salem
    "SLC": "SLC",  # Salt Lake City
    "WFH": "WFH",  # Whitefish
    "GPK": "GPK",  # East Glacier Park
    "HAV": "HAV",  # Havre
    "MSP": "MSP",  # St. Paul-Minneapolis
    # Texas / South Central
    "DAL": "DAL",  # Dallas
    "FTW": "FTW",  # Fort Worth
    "HOS": "HOS",  # Houston
    "AUS": "AUS",  # Austin
    "LRK": "LRK",  # Little Rock
    "MEM": "MEM",  # Memphis
    # Midwest / Great Lakes
    "KCY": "KCY",  # Kansas City
    "OKC": "OKC",  # Oklahoma City
    "OMA": "OMA",  # Omaha
    "IND": "IND",  # Indianapolis
    "CIN": "CIN",  # Cincinnati
    "CLE": "CLE",  # Cleveland
    "TOL": "TOL",  # Toledo
    "DET": "DET",  # Detroit
    "GRR": "GRR",  # Grand Rapids
    "PGH": "PGH",  # Pittsburgh
    # Empire Corridor (Hudson Valley)
    "CRT": "CRT",  # Croton-Harmon
    "YNY": "YNY",  # Yonkers
    "POU": "POU",  # Poughkeepsie
    "RHI": "RHI",  # Rhinecliff
    "HUD": "HUD",  # Hudson
    "SDY": "SDY",  # Schenectady
    "SAR": "SAR",  # Saratoga Springs
    # Northeast extensions
    "ALB": "ALB",  # Albany-Rensselaer
    "SYR": "SYR",  # Syracuse
    "ROC": "ROC",  # Rochester
    "BUF": "BUF",  # Buffalo Depew
    "MTR": "MTR",  # Montreal
    "POR": "POR",  # Portland ME
    "ESX": "ESX",  # Essex Junction
    "BTN": "BTN",  # Burlington VT
    # Virginia / Southeast
    "LYH": "LYH",  # Lynchburg
    "NPN": "NPN",  # Newport News
    "WBG": "WBG",  # Williamsburg
    "CLB": "CLB",  # Columbia SC
    "BHM": "BHM",  # Birmingham
    "MOE": "MOE",  # Mobile
    # California
    "ANA": "ANA",  # Anaheim
    "ARC": "ARC",  # Arcata
    "ARN": "ARN",  # Auburn
    "BAR": "BAR",  # Barstow
    "BBK": "BBK",  # Burbank
    "BFD": "BFD",  # Bakersfield
    "BKY": "BKY",  # Berkeley
    "BUR": "BUR",  # Burbank
    "CIC": "CIC",  # Chico
    "CLM": "CLM",  # Claremont
    "CML": "CML",  # Camarillo
    "COX": "COX",  # Colfax
    "CPN": "CPN",  # Carpinteria
    "CWT": "CWT",  # Chatsworth
    "DAV": "DAV",  # Davis
    "DBP": "DBP",  # Dublin-Pleasanton
    "DUN": "DUN",  # Dunsmuir
    "ELK": "ELK",  # Elko
    "FFV": "FFV",  # Fairfield-Vacaville
    "FMT": "FMT",  # Fremont
    "FNO": "FNO",  # Fresno
    "GAC": "GAC",  # Santa Clara Great America
    "GDL": "GDL",  # Glendale
    "GLY": "GLY",  # Gilroy
    "GTA": "GTA",  # Goleta
    "GUA": "GUA",  # Guadalupe
    "GVB": "GVB",  # Grover Beach
    "HAY": "HAY",  # Hayward
    "HNF": "HNF",  # Hanford
    "HSU": "HSU",  # Arcata
    "IRV": "IRV",  # Irvine
    "LOD": "LOD",  # Lodi
    "LPS": "LPS",  # Lompoc-Surf
    "LVS": "LVS",  # Las Vegas
    "MCD": "MCD",  # Merced
    "MPK": "MPK",  # Moorpark
    "MRV": "MRV",  # Marysville
    "MTZ": "MTZ",  # Martinez
    "MYU": "MYU",  # Seaside-Marina
    "NHL": "NHL",  # Santa Clarita-Newhall
    "NRG": "NRG",  # Northridge
    "OAC": "OAC",  # Oakland Coliseum/Airport
    "OKJ": "OKJ",  # Oakland
    "ONA": "ONA",  # Ontario
    "OXN": "OXN",  # Oxnard
    "POS": "POS",  # Pomona
    "PRB": "PRB",  # Paso Robles
    "PSN": "PSN",  # Palm Springs
    "PTC": "PTC",  # Petaluma
    "RDD": "RDD",  # Redding
    "RIC": "RIC",  # Richmond
    "RIV": "RIV",  # Riverside
    "RLN": "RLN",  # Rocklin
    "RSV": "RSV",  # Roseville
    "SCC": "SCC",  # Santa Clara
    "SFC": "SFC",  # San Francisco
    "SIM": "SIM",  # Simi Valley
    "SKN": "SKN",  # Stockton
    "SKT": "SKT",  # Stockton
    "SMN": "SMN",  # Santa Monica Pier
    "SNB": "SNB",  # San Bernardino
    "SNC": "SNC",  # San Juan Capistrano
    "SNP": "SNP",  # San Clemente Pier
    "SNS": "SNS",  # Salinas
    "SOL": "SOL",  # Solana Beach
    "SUI": "SUI",  # Suisun-Fairfield
    "VAL": "VAL",  # Vallejo
    "VEC": "VEC",  # Ventura
    "VNC": "VNC",  # Van Nuys
    "VRV": "VRV",  # Victorville
    "WNN": "WNN",  # Winnemucca
    "WTS": "WTS",  # Willits Calif Western Railroad Depot
    # Great Lakes
    "ALI": "ALI",  # Albion
    "ARB": "ARB",  # Ann Arbor
    "BAM": "BAM",  # Bangor
    "BTL": "BTL",  # Battle Creek
    "CBS": "CBS",  # Columbus
    "DER": "DER",  # Dearborn
    "DRD": "DRD",  # Durand
    "ERI": "ERI",  # Erie
    "FLN": "FLN",  # Flint
    "GLN": "GLN",  # Glenview
    "HOM": "HOM",  # Holland
    "JXN": "JXN",  # Jackson
    "KAL": "KAL",  # Kalamazoo
    "LNS": "LNS",  # East Lansing
    "LPE": "LPE",  # Lapeer
    "MKA": "MKA",  # General Mitchell Intl. Airport
    "PNT": "PNT",  # Pontiac
    "POG": "POG",  # Portage
    "PTH": "PTH",  # Port Huron
    "ROY": "ROY",  # Royal Oak
    "SJM": "SJM",  # St. Joseph-Benton Harbor
    "SVT": "SVT",  # Sturtevant
    "TRM": "TRM",  # Troy
    "WDL": "WDL",  # Wisconsin Dells
    # Mid-Atlantic
    "ALT": "ALT",  # Altoona
    "ARD": "ARD",  # Ardmore
    "BER": "BER",  # Berlin
    "BNF": "BNF",  # Branford
    "BWE": "BWE",  # Bowie State
    "CLN": "CLN",  # Clinton
    "COT": "COT",  # Coatesville
    "COV": "COV",  # Connellsville
    "CUM": "CUM",  # Cumberland
    "CWH": "CWH",  # Cornwells Heights
    "DOW": "DOW",  # Downingtown
    "EDG": "EDG",  # Edgewood
    "EXT": "EXT",  # Exton
    "GNB": "GNB",  # Greensburg
    "GUI": "GUI",  # Guilford
    "HAE": "HAE",  # Halethorpe
    "HFY": "HFY",  # Harpers Ferry
    "HGD": "HGD",  # Huntingdon
    "JST": "JST",  # Johnstown
    "LAB": "LAB",  # Latrobe
    "LEW": "LEW",  # Lewistown
    "MDS": "MDS",  # Madison
    "MID": "MID",  # Middletown
    "MRB": "MRB",  # Martinsburg
    "MSA": "MSA",  # Martin Airport
    "MYS": "MYS",  # Mystic
    "NRK": "NRK",  # Newark
    "NRO": "NRO",  # New Rochelle
    "OTN": "OTN",  # Odenton
    "PAO": "PAO",  # Paoli
    "PAR": "PAR",  # Parkesburg
    "PHN": "PHN",  # North Philadelphia
    "PRV": "PRV",  # Perryville
    "RKV": "RKV",  # Rockville
    "STS": "STS",  # New Haven
    "TYR": "TYR",  # Tyrone
    "WBL": "WBL",  # West Baltimore
    "WND": "WND",  # Windsor
    "WSB": "WSB",  # Westbrook
    # Midwest
    "AKY": "AKY",  # Ashland
    "ALC": "ALC",  # Alliance
    "ALD": "ALD",  # Alderson
    "BNL": "BNL",  # Bloomington-Normal
    "BYN": "BYN",  # Bryan
    "CDL": "CDL",  # Carbondale
    "CEN": "CEN",  # Centralia
    "CHM": "CHM",  # Champaign-Urbana
    "CHW": "CHW",  # Charleston
    "COI": "COI",  # Connersville
    "CRF": "CRF",  # Crawfordsville
    "CRV": "CRV",  # Carlinville
    "DOA": "DOA",  # Dowagiac
    "DQN": "DQN",  # Du Quoin
    "DWT": "DWT",  # Dwight
    "DYE": "DYE",  # Dyer
    "EFG": "EFG",  # Effingham
    "EKH": "EKH",  # Elkhart
    "ELY": "ELY",  # Elyria
    "FTN": "FTN",  # Fulton
    "GLM": "GLM",  # Gilman
    "HIN": "HIN",  # Hinton
    "HMI": "HMI",  # Hammond-Whiting
    "HMW": "HMW",  # Homewood
    "HUN": "HUN",  # Huntington
    "JOL": "JOL",  # Joliet Gateway Center
    "KAN": "KAN",  # Kannapolis
    "KEE": "KEE",  # Kewanee
    "KKI": "KKI",  # Kankakee
    "LAF": "LAF",  # Lafayette
    "LAG": "LAG",  # La Grange
    "LCN": "LCN",  # Lincoln
    "MAT": "MAT",  # Mattoon
    "MAY": "MAY",  # Maysville
    "MDT": "MDT",  # Mendota
    "MNG": "MNG",  # Montgomery
    "NBN": "NBN",  # Newbern-Dyersburg
    "NBU": "NBU",  # New Buffalo
    "NLS": "NLS",  # Niles
    "NPV": "NPV",  # Naperville
    "PCT": "PCT",  # Princeton
    "PIA": "PIA",  # Peoria
    "PLO": "PLO",  # Plano
    "PON": "PON",  # Pontiac
    "PRC": "PRC",  # Prince
    "REN": "REN",  # Rensselaer
    "RTL": "RTL",  # Rantoul
    "SKY": "SKY",  # Sandusky
    "SMT": "SMT",  # Summit
    "SOB": "SOB",  # South Bend
    "SPI": "SPI",  # Springfield
    "SPM": "SPM",  # South Portsmouth
    "THN": "THN",  # Thurmond
    "WSS": "WSS",  # White Sulphur Springs
    "WTI": "WTI",  # Waterloo
    # Mountain West
    "ACD": "ACD",  # Arcadia Valley
    "ADM": "ADM",  # Ardmore
    "ALN": "ALN",  # Alton
    "ALP": "ALP",  # Alpine
    "ARK": "ARK",  # Arkadelphia
    "BMT": "BMT",  # Beaumont
    "BRH": "BRH",  # Brookhaven
    "BRL": "BRL",  # Burlington
    "CBR": "CBR",  # Cleburne
    "CRN": "CRN",  # Creston
    "DDG": "DDG",  # Dodge City
    "DLK": "DLK",  # Detroit Lakes
    "DRT": "DRT",  # Del Rio
    "DVL": "DVL",  # Devils Lake
    "FAR": "FAR",  # Fargo
    "FMD": "FMD",  # Fort Madison
    "FMG": "FMG",  # Fort Morgan
    "GBB": "GBB",  # Galesburg
    "GCK": "GCK",  # Garden City
    "GFK": "GFK",  # Grand Forks
    "GLE": "GLE",  # Gainesville
    "GWD": "GWD",  # Greenwood
    "HAS": "HAS",  # Hastings
    "HAZ": "HAZ",  # Hazlehurst
    "HEM": "HEM",  # Hermann
    "HLD": "HLD",  # Holdrege
    "HMD": "HMD",  # Hammond
    "HOP": "HOP",  # Hope
    "HUT": "HUT",  # Hutchinson
    "IDP": "IDP",  # Independence
    "JAN": "JAN",  # Jackson
    "JEF": "JEF",  # Jefferson City
    "KIL": "KIL",  # Killeen
    "KWD": "KWD",  # Kirkwood
    "LAJ": "LAJ",  # La Junta
    "LAP": "LAP",  # La Plata
    "LBO": "LBO",  # Lbo
    "LCH": "LCH",  # Lake Charles
    "LEE": "LEE",  # Lee'S Summit
    "LFT": "LFT",  # Lafayette
    "LMR": "LMR",  # Lamar
    "LNK": "LNK",  # Lincoln
    "LRC": "LRC",  # Lawrence
    "LSE": "LSE",  # La Crosse
    "LVW": "LVW",  # Longview
    "MAC": "MAC",  # Macomb
    "MCB": "MCB",  # Mccomb
    "MCG": "MCG",  # Mcgregor
    "MCK": "MCK",  # Mccook
    "MHL": "MHL",  # Marshall
    "MIN": "MIN",  # Mineola
    "MKS": "MKS",  # Marks
    "MOT": "MOT",  # Minot
    "MTP": "MTP",  # Mt. Pleasant
    "MVN": "MVN",  # Malvern
    "NIB": "NIB",  # New Iberia
    "NOR": "NOR",  # Norman
    "OSC": "OSC",  # Osceola
    "OTM": "OTM",  # Ottumwa
    "PBF": "PBF",  # Poplar Bluff
    "PUR": "PUR",  # Purcell
    "PVL": "PVL",  # Pauls Valley
    "QCY": "QCY",  # Quincy
    "RAT": "RAT",  # Raton
    "RDW": "RDW",  # Red Wing
    "RUG": "RUG",  # Rugby
    "SCD": "SCD",  # St. Cloud
    "SCH": "SCH",  # Schriever
    "SED": "SED",  # Sedalia
    "SHR": "SHR",  # Shreveport Sportran Intermodal Terminal
    "SMC": "SMC",  # San Marcos
    "SND": "SND",  # Sanderson
    "SPL": "SPL",  # Staples
    "STN": "STN",  # Stanley
    "TAY": "TAY",  # Taylor
    "TOH": "TOH",  # Tomah
    "TOP": "TOP",  # Topeka
    "TPL": "TPL",  # Temple
    "TRI": "TRI",  # Trinidad
    "TXA": "TXA",  # Texarkana
    "WAH": "WAH",  # Washington
    "WAR": "WAR",  # Warrensburg
    "WEL": "WEL",  # Wellington
    "WIC": "WIC",  # Wichita
    "WIN": "WIN",  # Winona
    "WNR": "WNR",  # Walnut Ridge
    "WTN": "WTN",  # Williston
    "YAZ": "YAZ",  # Yazoo City
    # New England
    "AMS": "AMS",  # Amsterdam
    "AST": "AST",  # Aldershot
    "BFX": "BFX",  # Buffalo
    "BLF": "BLF",  # Bellows Falls
    "BON": "BON",  # Boston North
    "BRA": "BRA",  # Brattleboro
    "BRK": "BRK",  # Brunswick
    "CBN": "CBN",  # Canadian Border
    "CNV": "CNV",  # Castleton
    "FED": "FED",  # Fort Edward
    "FRA": "FRA",  # Framingham
    "FRE": "FRE",  # Freeport
    "FTC": "FTC",  # Ticonderoga
    "GFD": "GFD",  # Greenfield
    "GMS": "GMS",  # Grimsby
    "HHL": "HHL",  # Haverhill
    "HLK": "HLK",  # Holyoke
    "MBY": "MBY",  # Middlebury
    "MPR": "MPR",  # Montpelier-Berlin
    "NFL": "NFL",  # Niagara Falls
    "NFS": "NFS",  # Niagara Falls
    "NHT": "NHT",  # Northampton
    "OKL": "OKL",  # Oakville
    "ORB": "ORB",  # Old Orchard Beach
    "PIT": "PIT",  # Pittsfield
    "PLB": "PLB",  # Plattsburgh
    "POH": "POH",  # Port Henry
    "ROM": "ROM",  # Rome
    "RPH": "RPH",  # Randolph
    "RSP": "RSP",  # Rouses Point
    "RTE": "RTE",  # Route 128
    "RUD": "RUD",  # Rutland
    "SAB": "SAB",  # St. Albans
    "SAO": "SAO",  # Saco
    "SCA": "SCA",  # St. Catherines
    "SLQ": "SLQ",  # St-Lambert
    "TWO": "TWO",  # Toronto
    "UCA": "UCA",  # Utica
    "VRN": "VRN",  # Ferrisburgh
    "WAB": "WAB",  # Waterbury-Stowe
    "WEM": "WEM",  # Wells
    "WHL": "WHL",  # Whitehall
    "WNM": "WNM",  # Windsor-Mt. Ascutney
    "WOB": "WOB",  # Woburn
    "WOR": "WOR",  # Worcester Union
    "WRJ": "WRJ",  # White River Junction
    "WSP": "WSP",  # Westport
    # Pacific Northwest
    "ALY": "ALY",  # Albany
    "BEL": "BEL",  # Bellingham
    "BNG": "BNG",  # Bingen-White Salmon
    "BRO": "BRO",  # Browning
    "CMO": "CMO",  # Chemult
    "CTL": "CTL",  # Centralia
    "CUT": "CUT",  # Cut Bank
    "EDM": "EDM",  # Edmonds
    "EPH": "EPH",  # Ephrata
    "ESM": "ESM",  # Essex
    "EVR": "EVR",  # Everett
    "GGW": "GGW",  # Glasgow
    "GRA": "GRA",  # Granby
    "KEL": "KEL",  # Kelso-Longview
    "KFS": "KFS",  # Klamath Falls
    "LIB": "LIB",  # Libby
    "LWA": "LWA",  # Leavenworth
    "MAL": "MAL",  # Malta
    "MVW": "MVW",  # Mount Vernon
    "OLW": "OLW",  # Olympia-Lacey
    "ORC": "ORC",  # Oregon City
    "PRO": "PRO",  # Provo
    "PSC": "PSC",  # Pasco
    "SBY": "SBY",  # Shelby
    "SPT": "SPT",  # Sandpoint
    "STW": "STW",  # Stanwood
    "TUK": "TUK",  # Tukwila
    "VAC": "VAC",  # Vancouver
    "VAN": "VAN",  # Vancouver
    "WEN": "WEN",  # Wenatchee
    "WGL": "WGL",  # West Glacier
    "WIH": "WIH",  # Wishram
    "WPT": "WPT",  # Wolf Point
    # South Central
    "ATN": "ATN",  # Anniston
    "BAS": "BAS",  # Bay St Louis
    "BDT": "BDT",  # Bradenton
    "BIX": "BIX",  # Biloxi Amtrak Sta
    "CAM": "CAM",  # Camden
    "DFB": "DFB",  # Deerfield Beach
    "DNK": "DNK",  # Denmark
    "GNS": "GNS",  # Gainesville
    "GUF": "GUF",  # Gulfport Amtrak Sta
    "HBG": "HBG",  # Hattiesburg
    "HOL": "HOL",  # Hollywood
    "JSP": "JSP",  # Jesup
    "LAK": "LAK",  # Lakeland
    "LAU": "LAU",  # Laurel
    "MEI": "MEI",  # Meridian Union
    "OKE": "OKE",  # Okeechobee
    "PAG": "PAG",  # Pascagoula
    "PAK": "PAK",  # Palatka
    "PIC": "PIC",  # Picayune
    "SBG": "SBG",  # Sebring
    "SDL": "SDL",  # Slidell
    "SFA": "SFA",  # Sanford Amtrak Auto Train
    "STP": "STP",  # St. Petersburg
    "TCA": "TCA",  # Toccoa
    "TCL": "TCL",  # Tuscaloosa
    "WDO": "WDO",  # Waldo
    "WWD": "WWD",  # Wildwood
    "YEM": "YEM",  # Yemassee
    # Southeast
    "BCV": "BCV",  # Burke Centre
    "BNC": "BNC",  # Burlington
    "CLF": "CLF",  # Clifton Forge
    "CLP": "CLP",  # Culpeper
    "CYN": "CYN",  # Cary
    "DAN": "DAN",  # Danville
    "FAY": "FAY",  # Fayetteville
    "FBG": "FBG",  # Fredericksburg
    "GBO": "GBO",  # Goldsboro
    "GRO": "GRO",  # Greensboro
    "HVL": "HVL",  # Havelock
    "KNC": "KNC",  # Kinston
    "MHD": "MHD",  # Morehead City
    "QAN": "QAN",  # Quantico
    "SEB": "SEB",  # Seabrook
    "SOP": "SOP",  # Southern Pines
    "SSM": "SSM",  # Selma
    "STA": "STA",  # Staunton
    "SWB": "SWB",  # Swansboro
    "WDB": "WDB",  # Woodbridge
    "WMN": "WMN",  # Wilmington
    # Southwest
    "BEN": "BEN",  # Benson
    "DEM": "DEM",  # Deming
    "GJT": "GJT",  # Grand Junction
    "GLP": "GLP",  # Gallup
    "GRI": "GRI",  # Green River
    "GSC": "GSC",  # Glenwood Springs
    "HER": "HER",  # Helper
    "KNG": "KNG",  # Kingman
    "LDB": "LDB",  # Lordsburg
    "LMY": "LMY",  # Lamy
    "LSV": "LSV",  # Las Vegas
    "MRC": "MRC",  # Maricopa
    "NDL": "NDL",  # Needles
    "PHA": "PHA",  # Phoenix Sky Harbor Airport
    "PXN": "PXN",  # North Phoenix Metro Center Transit
    "SAF": "SAF",  # Santa Fe
    "WIP": "WIP",  # Winter Park/Fraser
    "WLO": "WLO",  # Winslow
    "WMH": "WMH",  # Williams
    "WPR": "WPR",  # Winter Park Ski Resort
    "WPS": "WPS",  # Winter Park
    "YUM": "YUM",  # Yuma
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
    # Nationwide stations (identity mappings)
    "CHI": "CHI",  # Chicago Union Station
    "STL": "STL",  # St. Louis
    "MKE": "MKE",  # Milwaukee
    "LAX": "LAX",  # Los Angeles Union Station
    "SEA": "SEA",  # Seattle King Street
    "PDX": "PDX",  # Portland Union Station
    "EMY": "EMY",  # Emeryville
    "SAC": "SAC",  # Sacramento
    "NOL": "NOL",  # New Orleans
    "SAS": "SAS",  # San Antonio
    "DEN": "DEN",  # Denver Union Station
    # California / Southwest
    "SBA": "SBA",  # Santa Barbara
    "SLO": "SLO",  # San Luis Obispo
    "SJC": "SJC",  # San Jose
    "OSD": "OSD",  # Oceanside
    "SNA": "SNA",  # Santa Ana
    "FUL": "FUL",  # Fullerton
    "OLT": "OLT",  # San Diego Old Town
    "ABQ": "ABQ",  # Albuquerque
    "FLG": "FLG",  # Flagstaff
    "TUS": "TUS",  # Tucson
    "ELP": "ELP",  # El Paso
    "RNO": "RNO",  # Reno
    "TRU": "TRU",  # Truckee
    # Pacific Northwest
    "SPK": "SPK",  # Spokane
    "TAC": "TAC",  # Tacoma
    "EUG": "EUG",  # Eugene
    "SLM": "SLM",  # Salem
    "SLC": "SLC",  # Salt Lake City
    "WFH": "WFH",  # Whitefish
    "GPK": "GPK",  # East Glacier Park
    "HAV": "HAV",  # Havre
    "MSP": "MSP",  # St. Paul-Minneapolis
    # Texas / South Central
    "DAL": "DAL",  # Dallas
    "FTW": "FTW",  # Fort Worth
    "HOS": "HOS",  # Houston
    "AUS": "AUS",  # Austin
    "LRK": "LRK",  # Little Rock
    "MEM": "MEM",  # Memphis
    # Midwest / Great Lakes
    "KCY": "KCY",  # Kansas City
    "OKC": "OKC",  # Oklahoma City
    "OMA": "OMA",  # Omaha
    "IND": "IND",  # Indianapolis
    "CIN": "CIN",  # Cincinnati
    "CLE": "CLE",  # Cleveland
    "TOL": "TOL",  # Toledo
    "DET": "DET",  # Detroit
    "GRR": "GRR",  # Grand Rapids
    "PGH": "PGH",  # Pittsburgh
    # Empire Corridor (Hudson Valley)
    "CRT": "CRT",  # Croton-Harmon
    "YNY": "YNY",  # Yonkers
    "POU": "POU",  # Poughkeepsie
    "RHI": "RHI",  # Rhinecliff
    "HUD": "HUD",  # Hudson
    "SDY": "SDY",  # Schenectady
    "SAR": "SAR",  # Saratoga Springs
    # Northeast extensions
    "ALB": "ALB",  # Albany-Rensselaer
    "SYR": "SYR",  # Syracuse
    "ROC": "ROC",  # Rochester
    "BUF": "BUF",  # Buffalo Depew
    "MTR": "MTR",  # Montreal
    "POR": "POR",  # Portland ME
    "ESX": "ESX",  # Essex Junction
    "BTN": "BTN",  # Burlington VT
    # Virginia / Southeast
    "LYH": "LYH",  # Lynchburg
    "NPN": "NPN",  # Newport News
    "WBG": "WBG",  # Williamsburg
    "CLB": "CLB",  # Columbia SC
    "BHM": "BHM",  # Birmingham
    "MOE": "MOE",  # Mobile
    # California
    "ANA": "ANA",  # Anaheim
    "ARC": "ARC",  # Arcata
    "ARN": "ARN",  # Auburn
    "BAR": "BAR",  # Barstow
    "BBK": "BBK",  # Burbank
    "BFD": "BFD",  # Bakersfield
    "BKY": "BKY",  # Berkeley
    "BUR": "BUR",  # Burbank
    "CIC": "CIC",  # Chico
    "CLM": "CLM",  # Claremont
    "CML": "CML",  # Camarillo
    "COX": "COX",  # Colfax
    "CPN": "CPN",  # Carpinteria
    "CWT": "CWT",  # Chatsworth
    "DAV": "DAV",  # Davis
    "DBP": "DBP",  # Dublin-Pleasanton
    "DUN": "DUN",  # Dunsmuir
    "ELK": "ELK",  # Elko
    "FFV": "FFV",  # Fairfield-Vacaville
    "FMT": "FMT",  # Fremont
    "FNO": "FNO",  # Fresno
    "GAC": "GAC",  # Santa Clara Great America
    "GDL": "GDL",  # Glendale
    "GLY": "GLY",  # Gilroy
    "GTA": "GTA",  # Goleta
    "GUA": "GUA",  # Guadalupe
    "GVB": "GVB",  # Grover Beach
    "HAY": "HAY",  # Hayward
    "HNF": "HNF",  # Hanford
    "HSU": "HSU",  # Arcata
    "IRV": "IRV",  # Irvine
    "LOD": "LOD",  # Lodi
    "LPS": "LPS",  # Lompoc-Surf
    "LVS": "LVS",  # Las Vegas
    "MCD": "MCD",  # Merced
    "MPK": "MPK",  # Moorpark
    "MRV": "MRV",  # Marysville
    "MTZ": "MTZ",  # Martinez
    "MYU": "MYU",  # Seaside-Marina
    "NHL": "NHL",  # Santa Clarita-Newhall
    "NRG": "NRG",  # Northridge
    "OAC": "OAC",  # Oakland Coliseum/Airport
    "OKJ": "OKJ",  # Oakland
    "ONA": "ONA",  # Ontario
    "OXN": "OXN",  # Oxnard
    "POS": "POS",  # Pomona
    "PRB": "PRB",  # Paso Robles
    "PSN": "PSN",  # Palm Springs
    "PTC": "PTC",  # Petaluma
    "RDD": "RDD",  # Redding
    "RIC": "RIC",  # Richmond
    "RIV": "RIV",  # Riverside
    "RLN": "RLN",  # Rocklin
    "RSV": "RSV",  # Roseville
    "SCC": "SCC",  # Santa Clara
    "SFC": "SFC",  # San Francisco
    "SIM": "SIM",  # Simi Valley
    "SKN": "SKN",  # Stockton
    "SKT": "SKT",  # Stockton
    "SMN": "SMN",  # Santa Monica Pier
    "SNB": "SNB",  # San Bernardino
    "SNC": "SNC",  # San Juan Capistrano
    "SNP": "SNP",  # San Clemente Pier
    "SNS": "SNS",  # Salinas
    "SOL": "SOL",  # Solana Beach
    "SUI": "SUI",  # Suisun-Fairfield
    "VAL": "VAL",  # Vallejo
    "VEC": "VEC",  # Ventura
    "VNC": "VNC",  # Van Nuys
    "VRV": "VRV",  # Victorville
    "WNN": "WNN",  # Winnemucca
    "WTS": "WTS",  # Willits Calif Western Railroad Depot
    # Great Lakes
    "ALI": "ALI",  # Albion
    "ARB": "ARB",  # Ann Arbor
    "BAM": "BAM",  # Bangor
    "BTL": "BTL",  # Battle Creek
    "CBS": "CBS",  # Columbus
    "DER": "DER",  # Dearborn
    "DRD": "DRD",  # Durand
    "ERI": "ERI",  # Erie
    "FLN": "FLN",  # Flint
    "GLN": "GLN",  # Glenview
    "HOM": "HOM",  # Holland
    "JXN": "JXN",  # Jackson
    "KAL": "KAL",  # Kalamazoo
    "LNS": "LNS",  # East Lansing
    "LPE": "LPE",  # Lapeer
    "MKA": "MKA",  # General Mitchell Intl. Airport
    "PNT": "PNT",  # Pontiac
    "POG": "POG",  # Portage
    "PTH": "PTH",  # Port Huron
    "ROY": "ROY",  # Royal Oak
    "SJM": "SJM",  # St. Joseph-Benton Harbor
    "SVT": "SVT",  # Sturtevant
    "TRM": "TRM",  # Troy
    "WDL": "WDL",  # Wisconsin Dells
    # Mid-Atlantic
    "ALT": "ALT",  # Altoona
    "ARD": "ARD",  # Ardmore
    "BER": "BER",  # Berlin
    "BNF": "BNF",  # Branford
    "BWE": "BWE",  # Bowie State
    "CLN": "CLN",  # Clinton
    "COT": "COT",  # Coatesville
    "COV": "COV",  # Connellsville
    "CUM": "CUM",  # Cumberland
    "CWH": "CWH",  # Cornwells Heights
    "DOW": "DOW",  # Downingtown
    "EDG": "EDG",  # Edgewood
    "EXT": "EXT",  # Exton
    "GNB": "GNB",  # Greensburg
    "GUI": "GUI",  # Guilford
    "HAE": "HAE",  # Halethorpe
    "HFY": "HFY",  # Harpers Ferry
    "HGD": "HGD",  # Huntingdon
    "JST": "JST",  # Johnstown
    "LAB": "LAB",  # Latrobe
    "LEW": "LEW",  # Lewistown
    "MDS": "MDS",  # Madison
    "MID": "MID",  # Middletown
    "MRB": "MRB",  # Martinsburg
    "MSA": "MSA",  # Martin Airport
    "MYS": "MYS",  # Mystic
    "NRK": "NRK",  # Newark
    "NRO": "NRO",  # New Rochelle
    "OTN": "OTN",  # Odenton
    "PAO": "PAO",  # Paoli
    "PAR": "PAR",  # Parkesburg
    "PHN": "PHN",  # North Philadelphia
    "PRV": "PRV",  # Perryville
    "RKV": "RKV",  # Rockville
    "STS": "STS",  # New Haven
    "TYR": "TYR",  # Tyrone
    "WBL": "WBL",  # West Baltimore
    "WND": "WND",  # Windsor
    "WSB": "WSB",  # Westbrook
    # Midwest
    "AKY": "AKY",  # Ashland
    "ALC": "ALC",  # Alliance
    "ALD": "ALD",  # Alderson
    "BNL": "BNL",  # Bloomington-Normal
    "BYN": "BYN",  # Bryan
    "CDL": "CDL",  # Carbondale
    "CEN": "CEN",  # Centralia
    "CHM": "CHM",  # Champaign-Urbana
    "CHW": "CHW",  # Charleston
    "COI": "COI",  # Connersville
    "CRF": "CRF",  # Crawfordsville
    "CRV": "CRV",  # Carlinville
    "DOA": "DOA",  # Dowagiac
    "DQN": "DQN",  # Du Quoin
    "DWT": "DWT",  # Dwight
    "DYE": "DYE",  # Dyer
    "EFG": "EFG",  # Effingham
    "EKH": "EKH",  # Elkhart
    "ELY": "ELY",  # Elyria
    "FTN": "FTN",  # Fulton
    "GLM": "GLM",  # Gilman
    "HIN": "HIN",  # Hinton
    "HMI": "HMI",  # Hammond-Whiting
    "HMW": "HMW",  # Homewood
    "HUN": "HUN",  # Huntington
    "JOL": "JOL",  # Joliet Gateway Center
    "KAN": "KAN",  # Kannapolis
    "KEE": "KEE",  # Kewanee
    "KKI": "KKI",  # Kankakee
    "LAF": "LAF",  # Lafayette
    "LAG": "LAG",  # La Grange
    "LCN": "LCN",  # Lincoln
    "MAT": "MAT",  # Mattoon
    "MAY": "MAY",  # Maysville
    "MDT": "MDT",  # Mendota
    "MNG": "MNG",  # Montgomery
    "NBN": "NBN",  # Newbern-Dyersburg
    "NBU": "NBU",  # New Buffalo
    "NLS": "NLS",  # Niles
    "NPV": "NPV",  # Naperville
    "PCT": "PCT",  # Princeton
    "PIA": "PIA",  # Peoria
    "PLO": "PLO",  # Plano
    "PON": "PON",  # Pontiac
    "PRC": "PRC",  # Prince
    "REN": "REN",  # Rensselaer
    "RTL": "RTL",  # Rantoul
    "SKY": "SKY",  # Sandusky
    "SMT": "SMT",  # Summit
    "SOB": "SOB",  # South Bend
    "SPI": "SPI",  # Springfield
    "SPM": "SPM",  # South Portsmouth
    "THN": "THN",  # Thurmond
    "WSS": "WSS",  # White Sulphur Springs
    "WTI": "WTI",  # Waterloo
    # Mountain West
    "ACD": "ACD",  # Arcadia Valley
    "ADM": "ADM",  # Ardmore
    "ALN": "ALN",  # Alton
    "ALP": "ALP",  # Alpine
    "ARK": "ARK",  # Arkadelphia
    "BMT": "BMT",  # Beaumont
    "BRH": "BRH",  # Brookhaven
    "BRL": "BRL",  # Burlington
    "CBR": "CBR",  # Cleburne
    "CRN": "CRN",  # Creston
    "DDG": "DDG",  # Dodge City
    "DLK": "DLK",  # Detroit Lakes
    "DRT": "DRT",  # Del Rio
    "DVL": "DVL",  # Devils Lake
    "FAR": "FAR",  # Fargo
    "FMD": "FMD",  # Fort Madison
    "FMG": "FMG",  # Fort Morgan
    "GBB": "GBB",  # Galesburg
    "GCK": "GCK",  # Garden City
    "GFK": "GFK",  # Grand Forks
    "GLE": "GLE",  # Gainesville
    "GWD": "GWD",  # Greenwood
    "HAS": "HAS",  # Hastings
    "HAZ": "HAZ",  # Hazlehurst
    "HEM": "HEM",  # Hermann
    "HLD": "HLD",  # Holdrege
    "HMD": "HMD",  # Hammond
    "HOP": "HOP",  # Hope
    "HUT": "HUT",  # Hutchinson
    "IDP": "IDP",  # Independence
    "JAN": "JAN",  # Jackson
    "JEF": "JEF",  # Jefferson City
    "KIL": "KIL",  # Killeen
    "KWD": "KWD",  # Kirkwood
    "LAJ": "LAJ",  # La Junta
    "LAP": "LAP",  # La Plata
    "LBO": "LBO",  # Lbo
    "LCH": "LCH",  # Lake Charles
    "LEE": "LEE",  # Lee'S Summit
    "LFT": "LFT",  # Lafayette
    "LMR": "LMR",  # Lamar
    "LNK": "LNK",  # Lincoln
    "LRC": "LRC",  # Lawrence
    "LSE": "LSE",  # La Crosse
    "LVW": "LVW",  # Longview
    "MAC": "MAC",  # Macomb
    "MCB": "MCB",  # Mccomb
    "MCG": "MCG",  # Mcgregor
    "MCK": "MCK",  # Mccook
    "MHL": "MHL",  # Marshall
    "MIN": "MIN",  # Mineola
    "MKS": "MKS",  # Marks
    "MOT": "MOT",  # Minot
    "MTP": "MTP",  # Mt. Pleasant
    "MVN": "MVN",  # Malvern
    "NIB": "NIB",  # New Iberia
    "NOR": "NOR",  # Norman
    "OSC": "OSC",  # Osceola
    "OTM": "OTM",  # Ottumwa
    "PBF": "PBF",  # Poplar Bluff
    "PUR": "PUR",  # Purcell
    "PVL": "PVL",  # Pauls Valley
    "QCY": "QCY",  # Quincy
    "RAT": "RAT",  # Raton
    "RDW": "RDW",  # Red Wing
    "RUG": "RUG",  # Rugby
    "SCD": "SCD",  # St. Cloud
    "SCH": "SCH",  # Schriever
    "SED": "SED",  # Sedalia
    "SHR": "SHR",  # Shreveport Sportran Intermodal Terminal
    "SMC": "SMC",  # San Marcos
    "SND": "SND",  # Sanderson
    "SPL": "SPL",  # Staples
    "STN": "STN",  # Stanley
    "TAY": "TAY",  # Taylor
    "TOH": "TOH",  # Tomah
    "TOP": "TOP",  # Topeka
    "TPL": "TPL",  # Temple
    "TRI": "TRI",  # Trinidad
    "TXA": "TXA",  # Texarkana
    "WAH": "WAH",  # Washington
    "WAR": "WAR",  # Warrensburg
    "WEL": "WEL",  # Wellington
    "WIC": "WIC",  # Wichita
    "WIN": "WIN",  # Winona
    "WNR": "WNR",  # Walnut Ridge
    "WTN": "WTN",  # Williston
    "YAZ": "YAZ",  # Yazoo City
    # New England
    "AMS": "AMS",  # Amsterdam
    "AST": "AST",  # Aldershot
    "BFX": "BFX",  # Buffalo
    "BLF": "BLF",  # Bellows Falls
    "BON": "BON",  # Boston North
    "BRA": "BRA",  # Brattleboro
    "BRK": "BRK",  # Brunswick
    "CBN": "CBN",  # Canadian Border
    "CNV": "CNV",  # Castleton
    "FED": "FED",  # Fort Edward
    "FRA": "FRA",  # Framingham
    "FRE": "FRE",  # Freeport
    "FTC": "FTC",  # Ticonderoga
    "GFD": "GFD",  # Greenfield
    "GMS": "GMS",  # Grimsby
    "HHL": "HHL",  # Haverhill
    "HLK": "HLK",  # Holyoke
    "MBY": "MBY",  # Middlebury
    "MPR": "MPR",  # Montpelier-Berlin
    "NFL": "NFL",  # Niagara Falls
    "NFS": "NFS",  # Niagara Falls
    "NHT": "NHT",  # Northampton
    "OKL": "OKL",  # Oakville
    "ORB": "ORB",  # Old Orchard Beach
    "PIT": "PIT",  # Pittsfield
    "PLB": "PLB",  # Plattsburgh
    "POH": "POH",  # Port Henry
    "ROM": "ROM",  # Rome
    "RPH": "RPH",  # Randolph
    "RSP": "RSP",  # Rouses Point
    "RTE": "RTE",  # Route 128
    "RUD": "RUD",  # Rutland
    "SAB": "SAB",  # St. Albans
    "SAO": "SAO",  # Saco
    "SCA": "SCA",  # St. Catherines
    "SLQ": "SLQ",  # St-Lambert
    "TWO": "TWO",  # Toronto
    "UCA": "UCA",  # Utica
    "VRN": "VRN",  # Ferrisburgh
    "WAB": "WAB",  # Waterbury-Stowe
    "WEM": "WEM",  # Wells
    "WHL": "WHL",  # Whitehall
    "WNM": "WNM",  # Windsor-Mt. Ascutney
    "WOB": "WOB",  # Woburn
    "WOR": "WOR",  # Worcester Union
    "WRJ": "WRJ",  # White River Junction
    "WSP": "WSP",  # Westport
    # Pacific Northwest
    "ALY": "ALY",  # Albany
    "BEL": "BEL",  # Bellingham
    "BNG": "BNG",  # Bingen-White Salmon
    "BRO": "BRO",  # Browning
    "CMO": "CMO",  # Chemult
    "CTL": "CTL",  # Centralia
    "CUT": "CUT",  # Cut Bank
    "EDM": "EDM",  # Edmonds
    "EPH": "EPH",  # Ephrata
    "ESM": "ESM",  # Essex
    "EVR": "EVR",  # Everett
    "GGW": "GGW",  # Glasgow
    "GRA": "GRA",  # Granby
    "KEL": "KEL",  # Kelso-Longview
    "KFS": "KFS",  # Klamath Falls
    "LIB": "LIB",  # Libby
    "LWA": "LWA",  # Leavenworth
    "MAL": "MAL",  # Malta
    "MVW": "MVW",  # Mount Vernon
    "OLW": "OLW",  # Olympia-Lacey
    "ORC": "ORC",  # Oregon City
    "PRO": "PRO",  # Provo
    "PSC": "PSC",  # Pasco
    "SBY": "SBY",  # Shelby
    "SPT": "SPT",  # Sandpoint
    "STW": "STW",  # Stanwood
    "TUK": "TUK",  # Tukwila
    "VAC": "VAC",  # Vancouver
    "VAN": "VAN",  # Vancouver
    "WEN": "WEN",  # Wenatchee
    "WGL": "WGL",  # West Glacier
    "WIH": "WIH",  # Wishram
    "WPT": "WPT",  # Wolf Point
    # South Central
    "ATN": "ATN",  # Anniston
    "BAS": "BAS",  # Bay St Louis
    "BDT": "BDT",  # Bradenton
    "BIX": "BIX",  # Biloxi Amtrak Sta
    "CAM": "CAM",  # Camden
    "DFB": "DFB",  # Deerfield Beach
    "DNK": "DNK",  # Denmark
    "GNS": "GNS",  # Gainesville
    "GUF": "GUF",  # Gulfport Amtrak Sta
    "HBG": "HBG",  # Hattiesburg
    "HOL": "HOL",  # Hollywood
    "JSP": "JSP",  # Jesup
    "LAK": "LAK",  # Lakeland
    "LAU": "LAU",  # Laurel
    "MEI": "MEI",  # Meridian Union
    "OKE": "OKE",  # Okeechobee
    "PAG": "PAG",  # Pascagoula
    "PAK": "PAK",  # Palatka
    "PIC": "PIC",  # Picayune
    "SBG": "SBG",  # Sebring
    "SDL": "SDL",  # Slidell
    "SFA": "SFA",  # Sanford Amtrak Auto Train
    "STP": "STP",  # St. Petersburg
    "TCA": "TCA",  # Toccoa
    "TCL": "TCL",  # Tuscaloosa
    "WDO": "WDO",  # Waldo
    "WWD": "WWD",  # Wildwood
    "YEM": "YEM",  # Yemassee
    # Southeast
    "BCV": "BCV",  # Burke Centre
    "BNC": "BNC",  # Burlington
    "CLF": "CLF",  # Clifton Forge
    "CLP": "CLP",  # Culpeper
    "CYN": "CYN",  # Cary
    "DAN": "DAN",  # Danville
    "FAY": "FAY",  # Fayetteville
    "FBG": "FBG",  # Fredericksburg
    "GBO": "GBO",  # Goldsboro
    "GRO": "GRO",  # Greensboro
    "HVL": "HVL",  # Havelock
    "KNC": "KNC",  # Kinston
    "MHD": "MHD",  # Morehead City
    "QAN": "QAN",  # Quantico
    "SEB": "SEB",  # Seabrook
    "SOP": "SOP",  # Southern Pines
    "SSM": "SSM",  # Selma
    "STA": "STA",  # Staunton
    "SWB": "SWB",  # Swansboro
    "WDB": "WDB",  # Woodbridge
    "WMN": "WMN",  # Wilmington
    # Southwest
    "BEN": "BEN",  # Benson
    "DEM": "DEM",  # Deming
    "GJT": "GJT",  # Grand Junction
    "GLP": "GLP",  # Gallup
    "GRI": "GRI",  # Green River
    "GSC": "GSC",  # Glenwood Springs
    "HER": "HER",  # Helper
    "KNG": "KNG",  # Kingman
    "LDB": "LDB",  # Lordsburg
    "LMY": "LMY",  # Lamy
    "LSV": "LSV",  # Las Vegas
    "MRC": "MRC",  # Maricopa
    "NDL": "NDL",  # Needles
    "PHA": "PHA",  # Phoenix Sky Harbor Airport
    "PXN": "PXN",  # North Phoenix Metro Center Transit
    "SAF": "SAF",  # Santa Fe
    "WIP": "WIP",  # Winter Park/Fraser
    "WLO": "WLO",  # Winslow
    "WMH": "WMH",  # Williams
    "WPR": "WPR",  # Winter Park Ski Resort
    "WPS": "WPS",  # Winter Park
    "YUM": "YUM",  # Yuma
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
