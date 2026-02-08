"""
Station configuration for TrackRat V2.

Contains station codes, names, and related functions.
"""

# Station code to name mapping
STATION_NAMES: dict[str, str] = {
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
    "MH": "Murray Hill",
    "MI": "Middletown",
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
    "PNT": "Pontiac",
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
    "STS": "New Haven",
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
    "PON": "Pontiac",
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
    "VAC": "Vancouver",
    "VAN": "Vancouver",
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
    # PATCO Speedline stations (Philadelphia - South Jersey)
    # 3-char codes chosen to avoid conflicts with NJT, Amtrak, and PATH
    "LND": "Lindenwold",  # PATCO terminus (NJ)
    "ASD": "Ashland",
    "WCT": "Woodcrest",
    "HDF": "Haddonfield",
    "WMT": "Westmont",
    "CLD": "Collingswood",
    "FRY": "Ferry Avenue",
    "BWY": "Broadway",
    "CTH": "City Hall",  # Camden City Hall
    "FKS": "Franklin Square",
    "EMK": "8th and Market",
    "NTL": "9-10th and Locust",
    "TWL": "12-13th and Locust",
    "FFL": "15-16th and Locust",  # PATCO terminus (Philadelphia)
    # PATH stations (3-char codes to match API constraints)
    "PNK": "Newark PATH",
    "PHR": "Harrison PATH",
    "PJS": "Journal Square",
    "PGR": "Grove Street",
    "PEX": "Exchange Place",
    "PNP": "Newport",
    "PHO": "Hoboken PATH",
    "PCH": "Christopher Street",
    "P9S": "9th Street",
    "P14": "14th Street",
    "P23": "23rd Street",
    "P33": "33rd Street",
    "PWC": "World Trade Center",
    # LIRR stations (Long Island Rail Road)
    # Penn Station "NY" is already defined above, used for LIRR Penn Station too
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


def get_station_name(code: str) -> str:
    """Get the full station name for a given code.

    Args:
        code: Two-character station code

    Returns:
        Full station name, or the code if not found
    """
    return STATION_NAMES.get(code, code)


# Station code equivalences for physically identical stations served by multiple systems.
# Some stations are shared between Amtrak and Metro-North but use different internal codes.
# E.g., New Rochelle is "NRO" in Amtrak data and "MNRC" in Metro-North data.
STATION_EQUIVALENTS: dict[str, str] = {
    "NRO": "MNRC",
    "MNRC": "NRO",  # New Rochelle
    "YNY": "MYON",
    "MYON": "YNY",  # Yonkers
    "CRT": "MCRH",
    "MCRH": "CRT",  # Croton-Harmon
    "POU": "MPOK",
    "MPOK": "POU",  # Poughkeepsie
    "STM": "MSTM",
    "MSTM": "STM",  # Stamford
    "BRP": "MBGP",
    "MBGP": "BRP",  # Bridgeport
    "NHV": "MNHV",
    "MNHV": "NHV",  # New Haven
}


def expand_station_codes(code: str) -> list[str]:
    """Return [code] plus any equivalent codes for the same physical station.

    Some physical stations are served by multiple transit systems that use
    different internal codes (e.g., Amtrak's NRO vs Metro-North's MNRC for
    New Rochelle). This function returns all codes for the same physical station
    so queries can match trains from any system.
    """
    equiv = STATION_EQUIVALENTS.get(code)
    return [code, equiv] if equiv else [code]


def canonical_station_code(code: str) -> str:
    """Return a canonical code for station equivalence groups.

    Used for cache keys so that equivalent codes (e.g., NRO and MNRC)
    produce the same cache key.
    """
    equiv = STATION_EQUIVALENTS.get(code)
    if equiv:
        return min(code, equiv)  # Alphabetically first
    return code


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
    "CRT": "CRT",  # Croton-Harmon
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
    "POU": "POU",  # Poughkeepsie
    "PRV": "PRV",  # Perryville
    "RHI": "RHI",  # Rhinecliff
    "RKV": "RKV",  # Rockville
    "STS": "STS",  # New Haven
    "TYR": "TYR",  # Tyrone
    "WBL": "WBL",  # West Baltimore
    "WND": "WND",  # Windsor
    "WSB": "WSB",  # Westbrook
    "YNY": "YNY",  # Yonkers
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
    "HUD": "HUD",  # Hudson
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
    "SAR": "SAR",  # Saratoga Springs
    "SCA": "SCA",  # St. Catherines
    "SDY": "SDY",  # Schenectady
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
    "CRT": "CRT",  # Croton-Harmon
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
    "POU": "POU",  # Poughkeepsie
    "PRV": "PRV",  # Perryville
    "RHI": "RHI",  # Rhinecliff
    "RKV": "RKV",  # Rockville
    "STS": "STS",  # New Haven
    "TYR": "TYR",  # Tyrone
    "WBL": "WBL",  # West Baltimore
    "WND": "WND",  # Windsor
    "WSB": "WSB",  # Westbrook
    "YNY": "YNY",  # Yonkers
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
    "HUD": "HUD",  # Hudson
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
    "SAR": "SAR",  # Saratoga Springs
    "SCA": "SCA",  # St. Catherines
    "SDY": "SDY",  # Schenectady
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


# PATH Transiter stop ID to internal station code mapping
# IDs verified against live Transiter API 2026-01-18
PATH_TRANSITER_TO_INTERNAL_MAP: dict[str, str] = {
    "26722": "P14",  # 14th Street
    "26723": "P23",  # 23rd Street
    "26724": "P33",  # 33rd Street
    "26725": "P9S",  # 9th Street
    "26726": "PCH",  # Christopher Street
    "26727": "PEX",  # Exchange Place
    "26728": "PGR",  # Grove Street
    "26729": "PHR",  # Harrison
    "26730": "PHO",  # Hoboken
    "26731": "PJS",  # Journal Square
    "26732": "PNP",  # Newport
    "26733": "PNK",  # Newark
    "26734": "PWC",  # World Trade Center
}

# Reverse mapping for PATH
INTERNAL_TO_PATH_TRANSITER_MAP: dict[str, str] = {
    v: k for k, v in PATH_TRANSITER_TO_INTERNAL_MAP.items()
}

# PATH route mappings (Transiter route ID -> line code, name, color)
# Verified against live Transiter API 2026-01-18
PATH_ROUTES: dict[str, tuple[str, str, str]] = {
    "859": ("HOB-33", "Hoboken - 33rd Street", "#4d92fb"),
    "860": ("HOB-WTC", "Hoboken - World Trade Center", "#65c100"),
    "861": ("JSQ-33", "Journal Square - 33rd Street", "#ff9900"),
    "862": ("NWK-WTC", "Newark - World Trade Center", "#d93a30"),
    "1024": ("JSQ-33H", "Journal Square - 33rd Street (via Hoboken)", "#ff9900"),
    "77285": ("WTC-33", "World Trade Center - 33rd Street", "#65c100"),
    "74320": ("NWK-HAR", "Newark - Harrison Shuttle", "#8c3c96"),
}

# PATH route stop sequences (station codes in order from one terminus to the other)
# Used to populate all stops when a train is discovered at a terminus
PATH_ROUTE_STOPS: dict[str, list[str]] = {
    # HOB-33: Hoboken <-> 33rd Street (via 6th Ave)
    "859": ["PHO", "PCH", "P9S", "P14", "P23", "P33"],
    # HOB-WTC: Hoboken <-> World Trade Center
    "860": ["PHO", "PNP", "PEX", "PWC"],
    # JSQ-33: Journal Square <-> 33rd Street (via 6th Ave)
    "861": ["PJS", "PGR", "PNP", "PCH", "P9S", "P14", "P23", "P33"],
    # NWK-WTC: Newark <-> World Trade Center
    "862": ["PNK", "PHR", "PJS", "PGR", "PEX", "PWC"],
    # JSQ-33H: Journal Square <-> 33rd Street via Hoboken
    "1024": ["PJS", "PGR", "PNP", "PHO", "PCH", "P9S", "P14", "P23", "P33"],
    # WTC-33: World Trade Center <-> 33rd Street (same as part of JSQ-33)
    "77285": ["PWC", "PEX", "PNP", "PCH", "P9S", "P14", "P23", "P33"],
    # NWK-HAR: Newark <-> Harrison Shuttle
    "74320": ["PNK", "PHR"],
}

# PATH discovery stations - ONLY terminus stations
# Transiter API only shows trains where the queried station is their destination.
# Mid-route stations won't return useful results.
# Using internal codes (Transiter IDs are in PATH_TRANSITER_TO_INTERNAL_MAP)
PATH_DISCOVERY_STATIONS = [
    "PHO",  # Hoboken terminus (26730) - HOB-33, HOB-WTC, JSQ-33-HOB
    "PWC",  # World Trade Center terminus (26734) - HOB-WTC, NWK-WTC, WTC-33
    "P33",  # 33rd Street terminus (26724) - HOB-33, JSQ-33, JSQ-33-HOB, WTC-33
    "PNK",  # Newark terminus (26733) - NWK-WTC, NWK-HAR origin
]

# PATH GTFS stop name to internal station code mapping
# Used for parsing PATH GTFS schedule data
PATH_GTFS_NAME_TO_INTERNAL_MAP: dict[str, str] = {
    "14th street": "P14",
    "14 st": "P14",
    "23rd street": "P23",
    "23 st": "P23",
    "33rd street": "P33",
    "33 st": "P33",
    "9th street": "P9S",
    "9 st": "P9S",
    "christopher street": "PCH",
    "christopher st": "PCH",
    "exchange place": "PEX",
    "grove street": "PGR",
    "grove st": "PGR",
    "harrison": "PHR",
    "hoboken": "PHO",
    "journal square": "PJS",
    "newport": "PNP",
    "newark": "PNK",
    "newark penn station": "PNK",
    "world trade center": "PWC",
    "wtc": "PWC",
}

# PATH native RidePATH API station codes to internal codes
# The native API uses different codes than Transiter (e.g., "NWK" vs "26733")
# Used by collectors/path/ridepath_client.py for real-time arrival data
PATH_RIDEPATH_API_TO_INTERNAL_MAP: dict[str, str] = {
    "NWK": "PNK",  # Newark
    "HAR": "PHR",  # Harrison
    "JSQ": "PJS",  # Journal Square
    "GRV": "PGR",  # Grove Street
    "NEW": "PNP",  # Newport
    "EXP": "PEX",  # Exchange Place
    "WTC": "PWC",  # World Trade Center
    "HOB": "PHO",  # Hoboken
    "CHR": "PCH",  # Christopher Street
    "09S": "P9S",  # 9th Street
    "14S": "P14",  # 14th Street
    "23S": "P23",  # 23rd Street
    "33S": "P33",  # 33rd Street
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
PATCO_GTFS_STOP_TO_INTERNAL_MAP: dict[str, str] = {
    "1": "LND",  # Lindenwold
    "2": "ASD",  # Ashland
    "3": "WCT",  # Woodcrest
    "4": "HDF",  # Haddonfield
    "5": "WMT",  # Westmont
    "6": "CLD",  # Collingswood
    "7": "FRY",  # Ferry Avenue
    "8": "BWY",  # Broadway
    "9": "CTH",  # City Hall
    "10": "FKS",  # Franklin Square
    "11": "EMK",  # 8th and Market
    "12": "NTL",  # 9-10th and Locust
    "13": "TWL",  # 12-13th and Locust
    "14": "FFL",  # 15-16th and Locust
}

# Reverse mapping for PATCO
INTERNAL_TO_PATCO_GTFS_STOP_MAP: dict[str, str] = {
    v: k for k, v in PATCO_GTFS_STOP_TO_INTERNAL_MAP.items()
}

# PATCO route definition (route_id -> line_code, name, color)
# Only one route in PATCO GTFS
PATCO_ROUTES: dict[str, tuple[str, str, str]] = {
    "2": ("PATCO", "PATCO Speedline", "#BC0035"),
}

# PATCO station sequence (Lindenwold to Philadelphia)
# Used for building complete journeys
PATCO_ROUTE_STOPS: list[str] = [
    "LND",  # Lindenwold (NJ terminus)
    "ASD",  # Ashland
    "WCT",  # Woodcrest
    "HDF",  # Haddonfield
    "WMT",  # Westmont
    "CLD",  # Collingswood
    "FRY",  # Ferry Avenue
    "BWY",  # Broadway
    "CTH",  # City Hall
    "FKS",  # Franklin Square
    "EMK",  # 8th and Market
    "NTL",  # 9-10th and Locust
    "TWL",  # 12-13th and Locust
    "FFL",  # 15-16th and Locust (Philadelphia terminus)
]

# PATCO terminus stations for schedule generation
PATCO_TERMINUS_STATIONS = ["LND", "FFL"]

# PATCO GTFS feed URL
PATCO_GTFS_FEED_URL = "https://rapid.nationalrtap.org/GTFSFileManagement/UserUploadFiles/13562/PATCO_GTFS.zip"


# =============================================================================
# LIRR (Long Island Rail Road) Configuration
# =============================================================================

# LIRR GTFS-RT feed URL (MTA direct)
LIRR_GTFS_RT_FEED_URL = (
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/lirr%2Fgtfs-lirr"
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

# Metro-North GTFS-RT feed URL (MTA direct)
MNR_GTFS_RT_FEED_URL = (
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/mnr%2Fgtfs-mnr"
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


def get_patco_route_info(gtfs_route_id: str) -> tuple[str, str, str] | None:
    """Get PATCO route info from GTFS route ID.

    Args:
        gtfs_route_id: GTFS route_id (e.g., '2')

    Returns:
        Tuple of (line_code, route_name, color) or None if not mapped
    """
    return PATCO_ROUTES.get(gtfs_route_id)


def map_patco_gtfs_stop(gtfs_stop_id: str) -> str | None:
    """Map PATCO GTFS stop_id to our internal station code.

    Args:
        gtfs_stop_id: GTFS stop_id (e.g., '1' for Lindenwold)

    Returns:
        Our internal station code (e.g., 'LND') or None if not mapped
    """
    return PATCO_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_stop_id)


def get_patco_route_stops(direction_id: int) -> list[str]:
    """Get ordered station list for PATCO based on direction.

    Args:
        direction_id: 0 for westbound (to Philadelphia), 1 for eastbound (to Lindenwold)

    Returns:
        List of station codes in travel order
    """
    if direction_id == 0:
        # Westbound: Lindenwold -> Philadelphia
        return PATCO_ROUTE_STOPS.copy()
    else:
        # Eastbound: Philadelphia -> Lindenwold
        return list(reversed(PATCO_ROUTE_STOPS))


def get_path_route_stops(route_id: str, terminus_station: str) -> list[str]:
    """Get the ordered list of stops for a PATH route heading to a terminus.

    Args:
        route_id: Transiter route ID (e.g., '859')
        terminus_station: The terminus station code where the train was discovered

    Returns:
        List of station codes in order from origin to destination (terminus)
    """
    stops = PATH_ROUTE_STOPS.get(route_id)
    if not stops:
        return [terminus_station]  # Fallback to just the terminus

    # If terminus is at the end, return as-is
    if stops[-1] == terminus_station:
        return stops.copy()

    # If terminus is at the start, reverse the list
    if stops[0] == terminus_station:
        return list(reversed(stops))

    # Terminus not found at either end - just return terminus
    return [terminus_station]


def get_path_stops_by_origin_destination(
    origin_station: str, destination_station: str
) -> list[str] | None:
    """Get ordered stops for a PATH journey from origin to destination.

    Finds the appropriate route by matching origin and destination stations
    against all known PATH routes. Returns the subset of stops from origin
    to destination (inclusive).

    Args:
        origin_station: Station code where train departs (e.g., 'PHO')
        destination_station: Station code for destination (e.g., 'P33')

    Returns:
        List of station codes from origin to destination, or None if no route found
    """
    for stops in PATH_ROUTE_STOPS.values():
        # Check if both stations are in this route
        if origin_station in stops and destination_station in stops:
            origin_idx = stops.index(origin_station)
            dest_idx = stops.index(destination_station)

            if origin_idx < dest_idx:
                # Origin comes before destination - return slice
                return stops[origin_idx : dest_idx + 1]
            else:
                # Origin comes after destination - reverse direction
                return list(reversed(stops[dest_idx : origin_idx + 1]))

    # No matching route found
    return None


def map_path_station_code(transiter_stop_id: str) -> str | None:
    """Map PATH Transiter stop ID to our internal code.

    Args:
        transiter_stop_id: Transiter's stop ID (e.g., '26735')

    Returns:
        Our internal station code (e.g., 'PATH_HOB') or None if not mapped
    """
    return PATH_TRANSITER_TO_INTERNAL_MAP.get(transiter_stop_id)


def map_internal_to_path_station(internal_code: str) -> str | None:
    """Map our internal station code to PATH Transiter stop ID.

    Args:
        internal_code: Our internal station code (e.g., 'PATH_HOB')

    Returns:
        Transiter's stop ID (e.g., '26735') or None if not mapped
    """
    return INTERNAL_TO_PATH_TRANSITER_MAP.get(internal_code)


def get_path_route_info(transiter_route_id: str) -> tuple[str, str, str] | None:
    """Get PATH route info from Transiter route ID.

    Args:
        transiter_route_id: Transiter's route ID (e.g., '859')

    Returns:
        Tuple of (line_code, route_name, color) or None if not mapped
    """
    return PATH_ROUTES.get(transiter_route_id)


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


def get_all_stations() -> list[dict[str, str]]:
    """Get all configured stations.

    Returns:
        List of station dictionaries with 'code' and 'name' keys
    """
    return [{"code": code, "name": name} for code, name in STATION_NAMES.items()]


# Station coordinates for map visualization
STATION_COORDINATES = {
    # Major NJ Transit/Amtrak hubs - verified coordinates
    "NY": {"lat": 40.750046, "lon": -73.992358},  # New York Penn Station
    "NP": {"lat": 40.734221, "lon": -74.164554},  # Newark Penn Station
    "TR": {"lat": 40.218515, "lon": -74.753926},  # Trenton Transit Center
    "PJ": {"lat": 40.316316, "lon": -74.623753},  # Princeton Junction
    "MP": {"lat": 40.56864, "lon": -74.329394},  # Metropark
    "NA": {"lat": 40.704415, "lon": -74.190717},  # Newark Airport
    "NB": {"lat": 40.497278, "lon": -74.445751},  # New Brunswick
    "SE": {"lat": 40.761188, "lon": -74.075821},  # Secaucus Upper Level
    "SC": {"lat": 40.7612, "lon": -74.0758},  # Secaucus Concourse
    "TS": {"lat": 40.761188, "lon": -74.075821},  # Secaucus Lower Level
    "HB": {"lat": 40.734843, "lon": -74.028046},  # Hoboken Terminal
    "PH": {"lat": 39.956565, "lon": -75.182327},  # Philadelphia 30th Street Station
    "WI": {"lat": 39.7369, "lon": -75.5522},  # Wilmington
    "BA": {"lat": 39.1896, "lon": -76.6934},  # BWI Airport Rail Station
    "BL": {"lat": 39.3081, "lon": -76.6175},  # Baltimore Penn Station
    "WS": {"lat": 38.8973, "lon": -77.0064},  # Washington Union Station
    "BOS": {"lat": 42.3520, "lon": -71.0552},  # Boston South Station
    "BBY": {"lat": 42.3473, "lon": -71.0764},  # Boston Back Bay
    # NJ Coast Line
    "LB": {"lat": 40.297145, "lon": -73.988331},  # Long Branch
    "AP": {"lat": 40.215359, "lon": -74.014786},  # Asbury Park
    "BS": {"lat": 40.18059, "lon": -74.027301},  # Belmar
    "SQ": {"lat": 40.120573, "lon": -74.047688},  # Manasquan
    "PP": {"lat": 40.092718, "lon": -74.048191},  # Point Pleasant Beach
    "BH": {"lat": 40.077178, "lon": -74.046183},  # Bay Head
    "AH": {"lat": 40.237659, "lon": -74.006769},  # Allenhurst
    "EL": {"lat": 40.265292, "lon": -73.99762},  # Elberon
    "LS": {"lat": 40.326715, "lon": -74.041054},  # Little Silver
    "MK": {"lat": 40.3086, "lon": -74.0253},  # Monmouth Park
    "RB": {"lat": 40.348284, "lon": -74.074538},  # Red Bank
    "HZ": {"lat": 40.415385, "lon": -74.190393},  # Hazlet
    "AM": {"lat": 40.420161, "lon": -74.223702},  # Aberdeen-Matawan
    "CH": {"lat": 40.484308, "lon": -74.280140},  # South Amboy
    "MI": {"lat": 40.38978, "lon": -74.116131},  # Middletown
    "LA": {"lat": 40.150557, "lon": -74.035481},  # Spring Lake
    "BB": {"lat": 40.203751, "lon": -74.018891},  # Bradley Beach
    # Northeast Corridor
    "EZ": {"lat": 40.667857, "lon": -74.215174},  # Elizabeth
    "LI": {"lat": 40.629485, "lon": -74.251772},  # Linden
    "RH": {"lat": 40.606338, "lon": -74.276692},  # Rahway
    "MU": {"lat": 40.540736, "lon": -74.360671},  # Metuchen
    "ED": {"lat": 40.519148, "lon": -74.410972},  # Edison
    "HL": {"lat": 40.255309, "lon": -74.70412},  # Hamilton
    "AV": {"lat": 40.577620, "lon": -74.277530},  # Avenel
    "BU": {"lat": 40.765134, "lon": -74.218612},  # Brick Church
    "WB": {"lat": 40.556610, "lon": -74.277751},  # Woodbridge
    "PE": {"lat": 40.509398, "lon": -74.273752},  # Perth Amboy
    "NZ": {"lat": 40.680265, "lon": -74.206165},  # North Elizabeth
    # Atlantic City Line
    "AC": {"lat": 39.363299, "lon": -74.441486},  # Atlantic City Rail Terminal
    "AB": {"lat": 39.424333, "lon": -74.502094},  # Absecon
    "EH": {"lat": 39.526441, "lon": -74.648028},  # Egg Harbor City
    "HN": {"lat": 39.631673, "lon": -74.79946},  # Hammonton
    "AO": {"lat": 39.783547, "lon": -74.907588},  # Atco
    "LW": {"lat": 39.833809, "lon": -75.000314},  # Lindenwold (NJT)
    "CY": {"lat": 39.928447, "lon": -75.041661},  # Cherry Hill
    "PN": {"lat": 39.977769, "lon": -75.061796},  # Pennsauken
    "NF": {"lat": 39.9984, "lon": -75.1560},  # North Philadelphia
    "PR": {"lat": 40.342088, "lon": -74.65887},  # Princeton (shuttle station)
    # Raritan Valley Line
    "RA": {"lat": 40.571005, "lon": -74.634364},  # Raritan
    "BK": {"lat": 40.560929, "lon": -74.530617},  # Bound Brook
    "BW": {"lat": 40.559904, "lon": -74.551741},  # Bridgewater
    "SM": {"lat": 40.566075, "lon": -74.61397},  # Somerville
    "DN": {"lat": 40.590869, "lon": -74.463043},  # Dunellen
    "PF": {"lat": 40.618425, "lon": -74.420163},  # Plainfield
    "NE": {"lat": 40.629148, "lon": -74.403455},  # Netherwood
    "FW": {"lat": 40.64106, "lon": -74.385003},  # Fanwood
    "WF": {"lat": 40.649448, "lon": -74.347629},  # Westfield
    "GW": {"lat": 40.652569, "lon": -74.324794},  # Garwood
    "XC": {"lat": 40.655523, "lon": -74.303226},  # Cranford
    "RL": {"lat": 40.66715, "lon": -74.266323},  # Roselle Park
    "US": {"lat": 40.683663, "lon": -74.238605},  # Union
    "HG": {"lat": 40.666884, "lon": -74.895863},  # High Bridge
    "AN": {"lat": 40.645173, "lon": -74.878569},  # Annandale
    "ON": {"lat": 40.636903, "lon": -74.835766},  # Lebanon
    "WH": {"lat": 40.615611, "lon": -74.77066},  # White House
    "OR": {"lat": 40.592020, "lon": -74.683802},  # North Branch
    # Morris & Essex Line
    "ST": {"lat": 40.716549, "lon": -74.357807},  # Summit
    "CM": {"lat": 40.740137, "lon": -74.384812},  # Chatham
    "MA": {"lat": 40.757028, "lon": -74.415105},  # Madison
    "CN": {"lat": 40.779038, "lon": -74.443435},  # Convent Station
    "MR": {"lat": 40.797113, "lon": -74.474086},  # Morristown
    "MX": {"lat": 40.828637, "lon": -74.478197},  # Morris Plains
    "DV": {"lat": 40.8839, "lon": -74.481513},  # Denville
    "DO": {"lat": 40.883415, "lon": -74.555887},  # Dover
    "MT": {"lat": 40.755365, "lon": -74.253024},  # Mountain Station
    "HQ": {"lat": 40.851444, "lon": -74.835352},  # Hackettstown
    "MB": {"lat": 40.725622, "lon": -74.303755},  # Millburn
    "RT": {"lat": 40.725249, "lon": -74.323754},  # Short Hills
    "ND": {"lat": 40.747621, "lon": -74.171943},  # Newark Broad Street
    "OG": {"lat": 40.771883, "lon": -74.233103},  # Orange
    "HI": {"lat": 40.766863, "lon": -74.243744},  # Highland Avenue
    "MV": {"lat": 40.914402, "lon": -74.268158},  # Mountain View
    "SO": {"lat": 40.745952, "lon": -74.260538},  # South Orange
    "MW": {"lat": 40.731149, "lon": -74.275427},  # Maplewood
    # Gladstone Branch
    "BV": {"lat": 40.716845, "lon": -74.571023},  # Bernardsville
    "FH": {"lat": 40.68571, "lon": -74.633734},  # Far Hills
    "PC": {"lat": 40.708794, "lon": -74.658469},  # Peapack
    "GL": {"lat": 40.720284, "lon": -74.666371},  # Gladstone
    "SG": {"lat": 40.674579, "lon": -74.493723},  # Stirling
    "GO": {"lat": 40.673513, "lon": -74.523606},  # Millington
    "LY": {"lat": 40.684844, "lon": -74.54947},  # Lyons
    "BI": {"lat": 40.711378, "lon": -74.55527},  # Basking Ridge
    "MH": {"lat": 40.695068, "lon": -74.403134},  # Murray Hill
    "NV": {"lat": 40.712022, "lon": -74.386501},  # New Providence
    "BY": {"lat": 40.682345, "lon": -74.442649},  # Berkeley Heights
    "GI": {"lat": 40.678251, "lon": -74.468317},  # Gillette
    # Main/Bergen County Lines
    "RF": {"lat": 40.828248, "lon": -74.100563},  # Rutherford
    "LN": {"lat": 40.814165, "lon": -74.122696},  # Lyndhurst
    "KG": {"lat": 40.8044, "lon": -74.1399},  # Kingsland
    "DL": {"lat": 40.831369, "lon": -74.131262},  # Delawanna
    "PS": {"lat": 40.849411, "lon": -74.133933},  # Passaic
    "GD": {"lat": 40.866669, "lon": -74.105560},  # Garfield
    "PL": {"lat": 40.884916, "lon": -74.102695},  # Plauderville
    "IF": {"lat": 40.867998, "lon": -74.153206},  # Clifton
    "RN": {"lat": 40.914887, "lon": -74.16733},  # Paterson
    "HW": {"lat": 40.942539, "lon": -74.152411},  # Hawthorne
    "GK": {"lat": 40.96137, "lon": -74.1293},  # Glen Rock Boro Hall
    "RS": {"lat": 40.962206, "lon": -74.133485},  # Glen Rock Main Line
    "RW": {"lat": 40.980629, "lon": -74.120592},  # Ridgewood
    "UF": {"lat": 40.997369, "lon": -74.113521},  # Ho-Ho-Kus
    "WK": {"lat": 41.012734, "lon": -74.123412},  # Waldwick
    "AZ": {"lat": 41.030902, "lon": -74.130957},  # Allendale
    "RY": {"lat": 41.0571, "lon": -74.1413},  # Ramsey Main St
    "17": {"lat": 41.07513, "lon": -74.145485},  # Ramsey-Route 17
    "MZ": {"lat": 41.094416, "lon": -74.14662},  # Mahwah
    "SF": {"lat": 41.11354, "lon": -74.153442},  # Suffern, NY
    # Montclair-Boonton Line
    "BM": {"lat": 40.792709, "lon": -74.200043},  # Bloomfield
    "MC": {"lat": 40.808178, "lon": -74.208681},  # Bay Street (Montclair)
    "GG": {"lat": 40.80059, "lon": -74.204655},  # Glen Ridge
    "BF": {"lat": 40.922505, "lon": -74.115236},  # Broadway Fair Lawn
    "FZ": {"lat": 40.939914, "lon": -74.121617},  # Radburn Fair Lawn
    "HS": {"lat": 40.857536, "lon": -74.2025},  # Montclair Heights
    "MS": {"lat": 40.848715, "lon": -74.205306},  # Mountain Avenue
    "UM": {"lat": 40.842004, "lon": -74.209368},  # Upper Montclair
    "WG": {"lat": 40.829514, "lon": -74.206934},  # Watchung Avenue
    "WT": {"lat": 40.782743, "lon": -74.198451},  # Watsessing Avenue
    "UV": {"lat": 40.869782, "lon": -74.197439},  # Montclair State University
    "FA": {"lat": 40.880669, "lon": -74.235372},  # Little Falls
    "GA": {"lat": 40.8847, "lon": -74.2539},  # Great Notch
    "TB": {"lat": 40.875904, "lon": -74.481915},  # Mount Tabor
    "BN": {"lat": 40.903378, "lon": -74.407736},  # Boonton
    "ML": {"lat": 40.885947, "lon": -74.433604},  # Mountain Lakes
    "LP": {"lat": 40.924138, "lon": -74.301826},  # Lincoln Park
    "TO": {"lat": 40.922809, "lon": -74.343842},  # Towaco
    "HV": {"lat": 40.89659, "lon": -74.632731},  # Mount Arlington
    "HP": {"lat": 40.904219, "lon": -74.665697},  # Lake Hopatcong
    "NT": {"lat": 40.897552, "lon": -74.707317},  # Netcong
    "OL": {"lat": 40.907376, "lon": -74.730653},  # Mount Olive
    "WM": {"lat": 40.854979, "lon": -74.096951},  # Wesmont
    "EO": {"lat": 40.760977, "lon": -74.210464},  # East Orange
    # Pascack Valley Line
    "WR": {"lat": 40.843974, "lon": -74.078719},  # Wood Ridge
    "TE": {"lat": 40.864858, "lon": -74.062676},  # Teterboro
    "EX": {"lat": 40.878973, "lon": -74.051893},  # Essex Street
    "AS": {"lat": 40.894458, "lon": -74.043781},  # Anderson Street
    "RG": {"lat": 40.935146, "lon": -74.02914},  # River Edge
    "NH": {"lat": 40.910856, "lon": -74.035044},  # New Bridge Landing
    "OD": {"lat": 40.953478, "lon": -74.029983},  # Oradell
    "EN": {"lat": 40.975036, "lon": -74.027474},  # Emerson
    "WW": {"lat": 40.990817, "lon": -74.032696},  # Westwood
    "HD": {"lat": 41.002414, "lon": -74.041033},  # Hillsdale
    "WL": {"lat": 41.021078, "lon": -74.040775},  # Woodcliff Lake
    "PV": {"lat": 41.032305, "lon": -74.036164},  # Park Ridge
    "ZM": {"lat": 41.040879, "lon": -74.029152},  # Montvale
    "PQ": {"lat": 41.058181, "lon": -74.02232},  # Pearl River, NY
    "NN": {"lat": 41.090015, "lon": -74.014794},  # Nanuet, NY
    "SV": {"lat": 41.111978, "lon": -74.043991},  # Spring Valley, NY
    # Port Jervis Line
    "XG": {"lat": 41.157138, "lon": -74.191307},  # Sloatsburg, NY
    "TC": {"lat": 41.194208, "lon": -74.18446},  # Tuxedo, NY
    "RM": {"lat": 41.293354, "lon": -74.13987},  # Harriman, NY
    "CW": {"lat": 41.437073, "lon": -74.101871},  # Salisbury Mills-Cornwall, NY
    "CB": {"lat": 41.450917, "lon": -74.266554},  # Campbell Hall, NY
    "OS": {"lat": 41.471784, "lon": -74.529212},  # Otisville, NY
    "PO": {"lat": 41.374899, "lon": -74.694622},  # Port Jervis, NY
    "23": {"lat": 40.900254, "lon": -74.256971},  # Wayne-Route 23
    # Raritan Valley Line Extension
    "JA": {"lat": 40.476912, "lon": -74.467363},  # Jersey Avenue
    # Additional Amtrak stations with GPS coordinates
    "BRP": {"lat": 41.1767, "lon": -73.1874},  # Bridgeport, CT
    "HFD": {"lat": 41.7678, "lon": -72.6821},  # Hartford, CT
    "MDN": {"lat": 41.5390, "lon": -72.8012},  # Meriden, CT
    "NHV": {"lat": 41.2987, "lon": -72.9259},  # New Haven, CT
    "NLC": {"lat": 41.3543, "lon": -72.0939},  # New London, CT
    "OSB": {"lat": 41.3005, "lon": -72.3760},  # Old Saybrook, CT
    "STM": {"lat": 41.0462, "lon": -73.5427},  # Stamford, CT
    "WFD": {"lat": 41.4571, "lon": -72.8254},  # Wallingford, CT
    "WNL": {"lat": 41.9272, "lon": -72.6286},  # Windsor Locks, CT
    "ABE": {
        "lat": 39.5095,
        "lon": -76.1630,
    },  # Aberdeen, MD (Note: conflict with AM for Aberdeen-Matawan)
    "NCR": {
        "lat": 38.9533,
        "lon": -76.8644,
    },  # New Carrollton, MD (Note: conflict with NC)
    "SPG": {"lat": 42.1060, "lon": -72.5936},  # Springfield, MA
    "CLA": {"lat": 43.3688, "lon": -72.3793},  # Claremont, NH
    "DOV": {
        "lat": 43.1979,
        "lon": -70.8737,
    },  # Dover, NH (Note: conflict with DO for Dover NJ)
    "DHM": {"lat": 43.1340, "lon": -70.9267},  # Durham-UNH, NH
    "EXR": {"lat": 42.9809, "lon": -70.9478},  # Exeter, NH
    "HAR": {"lat": 40.2616, "lon": -76.8782},  # Harrisburg, PA
    "LNC": {"lat": 40.0538, "lon": -76.3076},  # Lancaster, PA
    "MJY": {"lat": 40.1071, "lon": -76.5033},  # Mount Joy, PA (Keystone)
    "ELT": {"lat": 40.1524, "lon": -76.5258},  # Elizabethtown, PA (Keystone)
    "MIDPA": {"lat": 40.1996, "lon": -76.7322},  # Middletown, PA (Keystone)
    "KIN": {"lat": 41.4885, "lon": -71.5204},  # Kingston, RI
    "PVD": {"lat": 41.8256, "lon": -71.4160},  # Providence, RI
    "WLY": {"lat": 41.3770, "lon": -71.8307},  # Westerly, RI
    "ALX": {"lat": 38.8062, "lon": -77.0626},  # Alexandria, VA
    "CVS": {"lat": 38.0320, "lon": -78.4921},  # Charlottesville, VA
    "LOR": {"lat": 38.7060, "lon": -77.2214},  # Lorton, VA
    "MSS": {"lat": 38.7511, "lon": -77.4752},  # Manassas, VA
    "NFK": {"lat": 36.8583, "lon": -76.2876},  # Norfolk, VA
    "RVR": {"lat": 37.61741, "lon": -77.49755},  # Richmond Staples Mill Road, VA
    "RVM": {"lat": 37.6143, "lon": -77.4966},  # Richmond Main Street, VA
    "RNK": {"lat": 37.3077, "lon": -79.9803},  # Roanoke, VA
    # PATH stations (3-char codes)
    "PNK": {"lat": 40.7358, "lon": -74.1647},  # Newark PATH
    "PHR": {"lat": 40.7390, "lon": -74.1557},  # Harrison PATH
    "PJS": {"lat": 40.7326, "lon": -74.0628},  # Journal Square
    "PGR": {"lat": 40.7193, "lon": -74.0432},  # Grove Street
    "PEX": {"lat": 40.7162, "lon": -74.0327},  # Exchange Place
    "PNP": {"lat": 40.7268, "lon": -74.0338},  # Newport
    "PHO": {"lat": 40.7355, "lon": -74.0295},  # Hoboken PATH
    "PCH": {"lat": 40.7328, "lon": -74.0070},  # Christopher Street
    "P9S": {"lat": 40.7342, "lon": -74.0026},  # 9th Street
    "P14": {"lat": 40.7374, "lon": -73.9968},  # 14th Street
    "P23": {"lat": 40.7428, "lon": -73.9927},  # 23rd Street
    "P33": {"lat": 40.7491, "lon": -73.9882},  # 33rd Street
    "PWC": {"lat": 40.7116, "lon": -74.0112},  # World Trade Center
    # PATCO Speedline stations (coordinates from GTFS)
    "LND": {"lat": 39.833962, "lon": -75.000664},  # Lindenwold
    "ASD": {"lat": 39.858705, "lon": -75.00921},  # Ashland
    "WCT": {"lat": 39.870263, "lon": -75.011242},  # Woodcrest
    "HDF": {"lat": 39.89764, "lon": -75.037141},  # Haddonfield
    "WMT": {"lat": 39.90706, "lon": -75.046553},  # Westmont
    "CLD": {"lat": 39.91359, "lon": -75.06456},  # Collingswood
    "FRY": {"lat": 39.922572, "lon": -75.091805},  # Ferry Avenue
    "BWY": {"lat": 39.943135, "lon": -75.120364},  # Broadway
    "CTH": {"lat": 39.945469, "lon": -75.121242},  # City Hall
    "FKS": {"lat": 39.955298, "lon": -75.151157},  # Franklin Square
    "EMK": {"lat": 39.950979, "lon": -75.153515},  # 8th and Market
    "NTL": {"lat": 39.947345, "lon": -75.15751},  # 9-10th and Locust
    "TWL": {"lat": 39.947944, "lon": -75.162365},  # 12-13th and Locust
    "FFL": {"lat": 39.948634, "lon": -75.167792},  # 15-16th and Locust
    # Florida Amtrak stations
    "WLD": {"lat": 29.7899, "lon": -82.1712},  # Waldo, FL
    "OCA": {"lat": 29.1871, "lon": -82.1301},  # Ocala, FL
    # Nationwide Amtrak stations
    "CHI": {"lat": 41.8787, "lon": -87.6394},  # Chicago Union Station
    "STL": {"lat": 38.6242, "lon": -90.2040},  # St. Louis
    "MKE": {"lat": 43.0345, "lon": -87.9171},  # Milwaukee
    "LAX": {"lat": 34.0562, "lon": -118.2368},  # Los Angeles Union Station
    "SEA": {"lat": 47.5984, "lon": -122.3302},  # Seattle King Street
    "PDX": {"lat": 45.5287, "lon": -122.6768},  # Portland Union Station
    "EMY": {"lat": 37.8405, "lon": -122.2916},  # Emeryville
    "SAC": {"lat": 38.5840, "lon": -121.5007},  # Sacramento
    "NOL": {"lat": 29.9461, "lon": -90.0783},  # New Orleans
    "SAS": {"lat": 29.4194, "lon": -98.4781},  # San Antonio
    "DEN": {"lat": 39.7530, "lon": -104.9999},  # Denver Union Station
    # California / Southwest
    "SBA": {"lat": 34.4137, "lon": -119.6857},  # Santa Barbara
    "SLO": {"lat": 35.2730, "lon": -120.6574},  # San Luis Obispo
    "SJC": {"lat": 37.3297, "lon": -121.9021},  # San Jose
    "OSD": {"lat": 33.1954, "lon": -117.3803},  # Oceanside
    "SNA": {"lat": 33.7489, "lon": -117.8664},  # Santa Ana
    "FUL": {"lat": 33.8715, "lon": -117.9246},  # Fullerton
    "OLT": {"lat": 32.7548, "lon": -117.1976},  # San Diego Old Town
    "ABQ": {"lat": 35.0844, "lon": -106.6488},  # Albuquerque
    "FLG": {"lat": 35.1981, "lon": -111.6476},  # Flagstaff
    "TUS": {"lat": 32.2193, "lon": -110.9643},  # Tucson
    "ELP": {"lat": 31.7590, "lon": -106.4890},  # El Paso
    "RNO": {"lat": 39.5295, "lon": -119.7773},  # Reno
    "TRU": {"lat": 39.3278, "lon": -120.1850},  # Truckee
    # Pacific Northwest
    "SPK": {"lat": 47.6533, "lon": -117.4083},  # Spokane
    "TAC": {"lat": 47.2420, "lon": -122.4282},  # Tacoma
    "EUG": {"lat": 44.0543, "lon": -123.0950},  # Eugene
    "SLM": {"lat": 44.9429, "lon": -123.0353},  # Salem
    "SLC": {"lat": 40.7774, "lon": -111.9301},  # Salt Lake City
    "WFH": {"lat": 48.4106, "lon": -114.3375},  # Whitefish
    "GPK": {"lat": 48.4481, "lon": -113.2176},  # East Glacier Park
    "HAV": {"lat": 48.5528, "lon": -109.6822},  # Havre
    "MSP": {"lat": 44.9464, "lon": -93.0854},  # St. Paul-Minneapolis
    # Texas / South Central
    "DAL": {"lat": 32.7789, "lon": -96.8083},  # Dallas
    "FTW": {"lat": 32.7511, "lon": -97.3340},  # Fort Worth
    "HOS": {"lat": 29.7689, "lon": -95.3597},  # Houston
    "AUS": {"lat": 30.2748, "lon": -97.7268},  # Austin
    "LRK": {"lat": 34.7345, "lon": -92.2740},  # Little Rock
    "MEM": {"lat": 35.1352, "lon": -90.0510},  # Memphis
    # Midwest / Great Lakes
    "KCY": {"lat": 39.0912, "lon": -94.5556},  # Kansas City
    "OKC": {"lat": 35.4728, "lon": -97.5153},  # Oklahoma City
    "OMA": {"lat": 41.2535, "lon": -95.9319},  # Omaha
    "IND": {"lat": 39.7642, "lon": -86.1637},  # Indianapolis
    "CIN": {"lat": 39.1033, "lon": -84.5123},  # Cincinnati
    "CLE": {"lat": 41.5159, "lon": -81.6848},  # Cleveland
    "TOL": {"lat": 41.6529, "lon": -83.5328},  # Toledo
    "DET": {"lat": 42.3289, "lon": -83.0521},  # Detroit
    "GRR": {"lat": 42.9669, "lon": -85.6760},  # Grand Rapids
    "PGH": {"lat": 40.4447, "lon": -79.9923},  # Pittsburgh
    # Northeast extensions
    "ALB": {"lat": 42.6418, "lon": -73.7542},  # Albany-Rensselaer
    "SYR": {"lat": 43.0473, "lon": -76.1440},  # Syracuse
    "ROC": {"lat": 43.1566, "lon": -77.6088},  # Rochester
    "BUF": {"lat": 42.9038, "lon": -78.8636},  # Buffalo Depew
    "MTR": {"lat": 45.5017, "lon": -73.5673},  # Montreal
    "POR": {"lat": 43.6559, "lon": -70.2614},  # Portland ME
    "ESX": {"lat": 44.4881, "lon": -73.1820},  # Essex Junction
    "BTN": {"lat": 44.4759, "lon": -73.2121},  # Burlington VT
    # Virginia / Southeast
    "LYH": {"lat": 37.4083, "lon": -79.1428},  # Lynchburg
    "NPN": {"lat": 36.9814, "lon": -76.4356},  # Newport News
    "WBG": {"lat": 37.2710, "lon": -76.7075},  # Williamsburg
    "CLB": {"lat": 34.0006, "lon": -81.0349},  # Columbia SC
    "BHM": {"lat": 33.5206, "lon": -86.8344},  # Birmingham
    "MOE": {"lat": 30.6959, "lon": -88.0411},  # Mobile
    # California Amtrak stations
    "ANA": {"lat": 33.8038, "lon": -117.8773},  # Anaheim
    "ARC": {"lat": 40.8686, "lon": -124.0838},  # Arcata
    "ARN": {"lat": 38.9036, "lon": -121.0832},  # Auburn
    "BAR": {"lat": 34.9048, "lon": -117.0254},  # Barstow
    "BBK": {"lat": 34.1789, "lon": -118.3118},  # Burbank
    "BFD": {"lat": 35.3721, "lon": -119.0082},  # Bakersfield
    "BKY": {"lat": 37.8673, "lon": -122.3007},  # Berkeley
    "BUR": {"lat": 34.1931, "lon": -118.3538},  # Burbank
    "CIC": {"lat": 39.7233, "lon": -121.8459},  # Chico
    "CLM": {"lat": 34.0945, "lon": -117.7169},  # Claremont
    "CML": {"lat": 34.2159, "lon": -119.0341},  # Camarillo
    "COX": {"lat": 39.0992, "lon": -120.9531},  # Colfax
    "CPN": {"lat": 34.3968, "lon": -119.5230},  # Carpinteria
    "CWT": {"lat": 34.2532, "lon": -118.5994},  # Chatsworth
    "DAV": {"lat": 38.5436, "lon": -121.7377},  # Davis
    "DBP": {"lat": 37.7028, "lon": -121.8977},  # Dublin-Pleasanton
    "DUN": {"lat": 41.2111, "lon": -122.2706},  # Dunsmuir
    "ELK": {"lat": 40.8365, "lon": -115.7505},  # Elko
    "FFV": {"lat": 38.2856, "lon": -121.9679},  # Fairfield-Vacaville
    "FMT": {"lat": 37.5591, "lon": -122.0075},  # Fremont
    "FNO": {"lat": 36.7385, "lon": -119.7829},  # Fresno
    "GAC": {"lat": 37.4068, "lon": -121.9670},  # Santa Clara Great America
    "GDL": {"lat": 34.1237, "lon": -118.2589},  # Glendale
    "GLY": {"lat": 37.0040, "lon": -121.5668},  # Gilroy
    "GTA": {"lat": 34.4377, "lon": -119.8431},  # Goleta
    "GUA": {"lat": 34.9629, "lon": -120.5734},  # Guadalupe
    "GVB": {"lat": 35.1213, "lon": -120.6293},  # Grover Beach
    "HAY": {"lat": 37.6660, "lon": -122.0993},  # Hayward
    "HNF": {"lat": 36.3261, "lon": -119.6518},  # Hanford
    "HSU": {"lat": 40.8733, "lon": -124.0815},  # Arcata
    "IRV": {"lat": 33.6568, "lon": -117.7337},  # Irvine
    "LOD": {"lat": 38.1332, "lon": -121.2719},  # Lodi
    "LPS": {"lat": 34.6827, "lon": -120.6050},  # Lompoc-Surf
    "LVS": {"lat": 36.1645, "lon": -115.1497},  # Las Vegas
    "MCD": {"lat": 37.3072, "lon": -120.4768},  # Merced
    "MPK": {"lat": 34.2848, "lon": -118.8781},  # Moorpark
    "MRV": {"lat": 39.1437, "lon": -121.5973},  # Marysville
    "MTZ": {"lat": 38.0189, "lon": -122.1388},  # Martinez
    "MYU": {"lat": 36.6535, "lon": -121.8014},  # Seaside-Marina
    "NHL": {"lat": 34.3795, "lon": -118.5273},  # Santa Clarita-Newhall
    "NRG": {"lat": 34.2307, "lon": -118.5454},  # Northridge
    "OAC": {"lat": 37.7525, "lon": -122.1981},  # Oakland Coliseum/Airport
    "OKJ": {"lat": 37.7939, "lon": -122.2717},  # Oakland
    "ONA": {"lat": 34.0617, "lon": -117.6496},  # Ontario
    "OXN": {"lat": 34.1992, "lon": -119.1760},  # Oxnard
    "POS": {"lat": 34.0592, "lon": -117.7506},  # Pomona
    "PRB": {"lat": 35.6227, "lon": -120.6879},  # Paso Robles
    "PSN": {"lat": 33.8975, "lon": -116.5479},  # Palm Springs
    "PTC": {"lat": 38.2365, "lon": -122.6358},  # Petaluma
    "RDD": {"lat": 40.5836, "lon": -122.3934},  # Redding
    "RIC": {"lat": 37.9368, "lon": -122.3541},  # Richmond
    "RIV": {"lat": 33.9757, "lon": -117.3700},  # Riverside
    "RLN": {"lat": 38.7910, "lon": -121.2373},  # Rocklin
    "RSV": {"lat": 38.7500, "lon": -121.2863},  # Roseville
    "SCC": {"lat": 37.3532, "lon": -121.9366},  # Santa Clara
    "SFC": {"lat": 37.7886, "lon": -122.3989},  # San Francisco
    "SIM": {"lat": 34.2702, "lon": -118.6952},  # Simi Valley
    "SKN": {"lat": 37.9455, "lon": -121.2856},  # Stockton
    "SKT": {"lat": 37.9570, "lon": -121.2790},  # Stockton
    "SMN": {"lat": 34.0127, "lon": -118.4946},  # Santa Monica Pier
    "SNB": {"lat": 34.1041, "lon": -117.3107},  # San Bernardino
    "SNC": {"lat": 33.5013, "lon": -117.6638},  # San Juan Capistrano
    "SNP": {"lat": 33.4196, "lon": -117.6197},  # San Clemente Pier
    "SNS": {"lat": 36.6791, "lon": -121.6567},  # Salinas
    "SOL": {"lat": 32.9929, "lon": -117.2711},  # Solana Beach
    "SUI": {"lat": 38.2434, "lon": -122.0411},  # Suisun-Fairfield
    "VAL": {"lat": 38.1003, "lon": -122.2592},  # Vallejo
    "VEC": {"lat": 34.2769, "lon": -119.2999},  # Ventura
    "VNC": {"lat": 34.2113, "lon": -118.4482},  # Van Nuys
    "VRV": {"lat": 34.5372, "lon": -117.2930},  # Victorville
    "WNN": {"lat": 40.9690, "lon": -117.7322},  # Winnemucca
    "WTS": {"lat": 39.4126, "lon": -123.3510},  # Willits Calif Western Railroad Depot
    # Great Lakes Amtrak stations
    "ALI": {"lat": 42.2472, "lon": -84.7558},  # Albion
    "ARB": {"lat": 42.2877, "lon": -83.7432},  # Ann Arbor
    "BAM": {"lat": 42.3145, "lon": -86.1116},  # Bangor
    "BTL": {"lat": 42.3185, "lon": -85.1878},  # Battle Creek
    "CBS": {"lat": 43.3406, "lon": -89.0126},  # Columbus
    "DER": {"lat": 42.3072, "lon": -83.2353},  # Dearborn
    "DRD": {"lat": 42.9095, "lon": -83.9823},  # Durand
    "ERI": {"lat": 42.1208, "lon": -80.0824},  # Erie
    "FLN": {"lat": 43.0154, "lon": -83.6517},  # Flint
    "GLN": {"lat": 42.0750, "lon": -87.8056},  # Glenview
    "HOM": {"lat": 42.7911, "lon": -86.0966},  # Holland
    "JXN": {"lat": 42.2481, "lon": -84.3997},  # Jackson
    "KAL": {"lat": 42.2953, "lon": -85.5840},  # Kalamazoo
    "LNS": {"lat": 42.7187, "lon": -84.4960},  # East Lansing
    "LPE": {"lat": 43.0495, "lon": -83.3062},  # Lapeer
    "MKA": {"lat": 42.9406, "lon": -87.9244},  # General Mitchell Intl. Airport
    "PNT": {"lat": 42.6328, "lon": -83.2923},  # Pontiac
    "POG": {"lat": 43.5471, "lon": -89.4676},  # Portage
    "PTH": {"lat": 42.9604, "lon": -82.4438},  # Port Huron
    "ROY": {"lat": 42.4884, "lon": -83.1470},  # Royal Oak
    "SJM": {"lat": 42.1091, "lon": -86.4845},  # St. Joseph-Benton Harbor
    "SVT": {"lat": 42.7183, "lon": -87.9063},  # Sturtevant
    "TRM": {"lat": 42.5426, "lon": -83.1910},  # Troy
    "WDL": {"lat": 43.6265, "lon": -89.7775},  # Wisconsin Dells
    # Mid-Atlantic Amtrak stations
    "ALT": {"lat": 40.5145, "lon": -78.4016},  # Altoona
    "ARD": {"lat": 40.0083, "lon": -75.2904},  # Ardmore
    "BER": {"lat": 41.6356, "lon": -72.7653},  # Berlin
    "BNF": {"lat": 41.2745, "lon": -72.8172},  # Branford
    "BWE": {"lat": 39.0178, "lon": -76.7650},  # Bowie State
    "CLN": {"lat": 41.2795, "lon": -72.5283},  # Clinton
    "COT": {"lat": 39.9857, "lon": -75.8209},  # Coatesville
    "COV": {"lat": 40.0203, "lon": -79.5928},  # Connellsville
    "CRT": {"lat": 41.1899, "lon": -73.8824},  # Croton-Harmon
    "CUM": {"lat": 39.6506, "lon": -78.7580},  # Cumberland
    "CWH": {"lat": 40.0717, "lon": -74.9522},  # Cornwells Heights
    "DOW": {"lat": 40.0022, "lon": -75.7108},  # Downingtown
    "EDG": {"lat": 39.4162, "lon": -76.2928},  # Edgewood
    "EXT": {"lat": 40.0193, "lon": -75.6217},  # Exton
    "GNB": {"lat": 40.3050, "lon": -79.5469},  # Greensburg
    "GUI": {"lat": 41.2756, "lon": -72.6735},  # Guilford
    "HAE": {"lat": 39.2372, "lon": -76.6915},  # Halethorpe
    "HFY": {"lat": 39.3245, "lon": -77.7311},  # Harpers Ferry
    "HGD": {"lat": 40.4837, "lon": -78.0118},  # Huntingdon
    "JST": {"lat": 40.3297, "lon": -78.9220},  # Johnstown
    "LAB": {"lat": 40.3174, "lon": -79.3851},  # Latrobe
    "LEW": {"lat": 40.5883, "lon": -77.5800},  # Lewistown
    "MDS": {"lat": 41.2836, "lon": -72.5994},  # Madison
    "MID": {"lat": 40.1957, "lon": -76.7365},  # Middletown
    "MRB": {"lat": 39.4587, "lon": -77.9610},  # Martinsburg
    "MSA": {"lat": 39.3301, "lon": -76.4214},  # Martin Airport
    "MYS": {"lat": 41.3509, "lon": -71.9631},  # Mystic
    "NRK": {"lat": 39.6697, "lon": -75.7535},  # Newark
    "NRO": {"lat": 40.9115, "lon": -73.7843},  # New Rochelle
    "OTN": {"lat": 39.0871, "lon": -76.7064},  # Odenton
    "PAO": {"lat": 40.0428, "lon": -75.4838},  # Paoli
    "PAR": {"lat": 39.9592, "lon": -75.9221},  # Parkesburg
    "PHN": {"lat": 39.9968, "lon": -75.1551},  # North Philadelphia
    "POU": {"lat": 41.7071, "lon": -73.9375},  # Poughkeepsie
    "PRV": {"lat": 39.5580, "lon": -76.0732},  # Perryville
    "RHI": {"lat": 41.9213, "lon": -73.9513},  # Rhinecliff
    "RKV": {"lat": 39.0845, "lon": -77.1460},  # Rockville
    "STS": {"lat": 41.3053, "lon": -72.9221},  # New Haven
    "TYR": {"lat": 40.6677, "lon": -78.2405},  # Tyrone
    "WBL": {"lat": 39.2934, "lon": -76.6533},  # West Baltimore
    "WND": {"lat": 41.8520, "lon": -72.6423},  # Windsor
    "WSB": {"lat": 41.2888, "lon": -72.4480},  # Westbrook
    "YNY": {"lat": 40.9356, "lon": -73.9023},  # Yonkers
    # Midwest Amtrak stations
    "AKY": {"lat": 38.4809, "lon": -82.6396},  # Ashland
    "ALC": {"lat": 40.9213, "lon": -81.0929},  # Alliance
    "ALD": {"lat": 37.7243, "lon": -80.6449},  # Alderson
    "BNL": {"lat": 40.5090, "lon": -88.9843},  # Bloomington-Normal
    "BYN": {"lat": 41.4803, "lon": -84.5518},  # Bryan
    "CDL": {"lat": 37.7242, "lon": -89.2166},  # Carbondale
    "CEN": {"lat": 38.5275, "lon": -89.1361},  # Centralia
    "CHM": {"lat": 40.1158, "lon": -88.2414},  # Champaign-Urbana
    "CHW": {"lat": 38.3464, "lon": -81.6385},  # Charleston
    "COI": {"lat": 39.6460, "lon": -85.1334},  # Connersville
    "CRF": {"lat": 40.0447, "lon": -86.8992},  # Crawfordsville
    "CRV": {"lat": 39.2793, "lon": -89.8893},  # Carlinville
    "DOA": {"lat": 41.9809, "lon": -86.1090},  # Dowagiac
    "DQN": {"lat": 38.0123, "lon": -89.2403},  # Du Quoin
    "DWT": {"lat": 41.0899, "lon": -88.4307},  # Dwight
    "DYE": {"lat": 41.5154, "lon": -87.5181},  # Dyer
    "EFG": {"lat": 39.1171, "lon": -88.5471},  # Effingham
    "EKH": {"lat": 41.6807, "lon": -85.9718},  # Elkhart
    "ELY": {"lat": 41.3700, "lon": -82.0967},  # Elyria
    "FTN": {"lat": 36.5257, "lon": -88.8888},  # Fulton
    "GLM": {"lat": 40.7525, "lon": -87.9981},  # Gilman
    "HIN": {"lat": 37.6750, "lon": -80.8922},  # Hinton
    "HMI": {"lat": 41.6912, "lon": -87.5065},  # Hammond-Whiting
    "HMW": {"lat": 41.5624, "lon": -87.6687},  # Homewood
    "HUN": {"lat": 38.4158, "lon": -82.4397},  # Huntington
    "JOL": {"lat": 41.5246, "lon": -88.0787},  # Joliet Gateway Center
    "KAN": {"lat": 35.4962, "lon": -80.6249},  # Kannapolis
    "KEE": {"lat": 41.2458, "lon": -89.9275},  # Kewanee
    "KKI": {"lat": 41.1193, "lon": -87.8654},  # Kankakee
    "LAF": {"lat": 40.4193, "lon": -86.8959},  # Lafayette
    "LAG": {"lat": 41.8156, "lon": -87.8715},  # La Grange
    "LCN": {"lat": 40.1482, "lon": -89.3631},  # Lincoln
    "MAT": {"lat": 39.4827, "lon": -88.3760},  # Mattoon
    "MAY": {"lat": 38.6521, "lon": -83.7711},  # Maysville
    "MDT": {"lat": 41.5496, "lon": -89.1179},  # Mendota
    "MNG": {"lat": 38.1807, "lon": -81.3240},  # Montgomery
    "NBN": {"lat": 36.1127, "lon": -89.2623},  # Newbern-Dyersburg
    "NBU": {"lat": 41.7967, "lon": -86.7458},  # New Buffalo
    "NLS": {"lat": 41.8374, "lon": -86.2524},  # Niles
    "NPV": {"lat": 41.7795, "lon": -88.1455},  # Naperville
    "PCT": {"lat": 41.3852, "lon": -89.4668},  # Princeton
    "PIA": {"lat": 40.6894, "lon": -89.5936},  # Peoria
    "PLO": {"lat": 41.6624, "lon": -88.5383},  # Plano
    "PON": {"lat": 40.8787, "lon": -88.6372},  # Pontiac
    "PRC": {"lat": 37.8566, "lon": -81.0607},  # Prince
    "REN": {"lat": 40.9433, "lon": -87.1551},  # Rensselaer
    "RTL": {"lat": 40.3109, "lon": -88.1591},  # Rantoul
    "SKY": {"lat": 41.4407, "lon": -82.7179},  # Sandusky
    "SMT": {"lat": 41.7949, "lon": -87.8097},  # Summit
    "SOB": {"lat": 41.6784, "lon": -86.2873},  # South Bend
    "SPI": {"lat": 39.8023, "lon": -89.6514},  # Springfield
    "SPM": {"lat": 38.7213, "lon": -82.9638},  # South Portsmouth
    "THN": {"lat": 37.9570, "lon": -81.0788},  # Thurmond
    "WSS": {"lat": 37.7864, "lon": -80.3040},  # White Sulphur Springs
    "WTI": {"lat": 41.4318, "lon": -85.0243},  # Waterloo
    # Mountain West Amtrak stations
    "ACD": {"lat": 37.5922, "lon": -90.6244},  # Arcadia Valley
    "ADM": {"lat": 34.1725, "lon": -97.1255},  # Ardmore
    "ALN": {"lat": 38.9210, "lon": -90.1573},  # Alton
    "ALP": {"lat": 30.3573, "lon": -103.6615},  # Alpine
    "ARK": {"lat": 34.1139, "lon": -93.0533},  # Arkadelphia
    "BMT": {"lat": 30.0765, "lon": -94.1274},  # Beaumont
    "BRH": {"lat": 31.5830, "lon": -90.4411},  # Brookhaven
    "BRL": {"lat": 40.8058, "lon": -91.1020},  # Burlington
    "CBR": {"lat": 32.3497, "lon": -97.3823},  # Cleburne
    "CRN": {"lat": 41.0569, "lon": -94.3616},  # Creston
    "DDG": {"lat": 37.7523, "lon": -100.0170},  # Dodge City
    "DLK": {"lat": 46.8197, "lon": -95.8460},  # Detroit Lakes
    "DRT": {"lat": 29.3622, "lon": -100.9027},  # Del Rio
    "DVL": {"lat": 48.1105, "lon": -98.8614},  # Devils Lake
    "FAR": {"lat": 46.8810, "lon": -96.7854},  # Fargo
    "FMD": {"lat": 40.6296, "lon": -91.3135},  # Fort Madison
    "FMG": {"lat": 40.2472, "lon": -103.8028},  # Fort Morgan
    "GBB": {"lat": 40.9447, "lon": -90.3641},  # Galesburg
    "GCK": {"lat": 37.9644, "lon": -100.8733},  # Garden City
    "GFK": {"lat": 47.9175, "lon": -97.1108},  # Grand Forks
    "GLE": {"lat": 33.6252, "lon": -97.1409},  # Gainesville
    "GWD": {"lat": 33.5172, "lon": -90.1765},  # Greenwood
    "HAS": {"lat": 40.5843, "lon": -98.3875},  # Hastings
    "HAZ": {"lat": 31.8613, "lon": -90.3943},  # Hazlehurst
    "HEM": {"lat": 38.7073, "lon": -91.4326},  # Hermann
    "HLD": {"lat": 40.4360, "lon": -99.3701},  # Holdrege
    "HMD": {"lat": 30.5072, "lon": -90.4622},  # Hammond
    "HOP": {"lat": 33.6689, "lon": -93.5922},  # Hope
    "HUT": {"lat": 38.0557, "lon": -97.9315},  # Hutchinson
    "IDP": {"lat": 39.0869, "lon": -94.4297},  # Independence
    "JAN": {"lat": 32.3008, "lon": -90.1909},  # Jackson
    "JEF": {"lat": 38.5789, "lon": -92.1699},  # Jefferson City
    "KIL": {"lat": 31.1212, "lon": -97.7286},  # Killeen
    "KWD": {"lat": 38.5811, "lon": -90.4068},  # Kirkwood
    "LAJ": {"lat": 37.9882, "lon": -103.5436},  # La Junta
    "LAP": {"lat": 40.0292, "lon": -92.4934},  # La Plata
    "LBO": {"lat": 54.7740, "lon": -101.8481},  # Lbo
    "LCH": {"lat": 30.2381, "lon": -93.2170},  # Lake Charles
    "LEE": {"lat": 38.9126, "lon": -94.3780},  # Lee'S Summit
    "LFT": {"lat": 30.2265, "lon": -92.0145},  # Lafayette
    "LMR": {"lat": 38.0896, "lon": -102.6186},  # Lamar
    "LNK": {"lat": 40.8159, "lon": -96.7132},  # Lincoln
    "LRC": {"lat": 38.9712, "lon": -95.2305},  # Lawrence
    "LSE": {"lat": 43.8332, "lon": -91.2473},  # La Crosse
    "LVW": {"lat": 32.4940, "lon": -94.7283},  # Longview
    "MAC": {"lat": 40.4612, "lon": -90.6709},  # Macomb
    "MCB": {"lat": 31.2445, "lon": -90.4513},  # Mccomb
    "MCG": {"lat": 31.4434, "lon": -97.4048},  # Mcgregor
    "MCK": {"lat": 40.1976, "lon": -100.6258},  # Mccook
    "MHL": {"lat": 32.5515, "lon": -94.3670},  # Marshall
    "MIN": {"lat": 32.6620, "lon": -95.4891},  # Mineola
    "MKS": {"lat": 34.2582, "lon": -90.2723},  # Marks
    "MOT": {"lat": 48.2361, "lon": -101.2986},  # Minot
    "MTP": {"lat": 40.9712, "lon": -91.5508},  # Mt. Pleasant
    "MVN": {"lat": 34.3655, "lon": -92.8140},  # Malvern
    "NIB": {"lat": 30.0084, "lon": -91.8238},  # New Iberia
    "NOR": {"lat": 35.2200, "lon": -97.4430},  # Norman
    "OSC": {"lat": 41.0371, "lon": -93.7649},  # Osceola
    "OTM": {"lat": 41.0188, "lon": -92.4149},  # Ottumwa
    "PBF": {"lat": 36.7540, "lon": -90.3933},  # Poplar Bluff
    "PUR": {"lat": 35.0120, "lon": -97.3574},  # Purcell
    "PVL": {"lat": 34.7417, "lon": -97.2185},  # Pauls Valley
    "QCY": {"lat": 39.9571, "lon": -91.3685},  # Quincy
    "RAT": {"lat": 36.9011, "lon": -104.4379},  # Raton
    "RDW": {"lat": 44.5662, "lon": -92.5371},  # Red Wing
    "RUG": {"lat": 48.3698, "lon": -99.9976},  # Rugby
    "SCD": {"lat": 45.5677, "lon": -94.1491},  # St. Cloud
    "SCH": {"lat": 29.7467, "lon": -90.8152},  # Schriever
    "SED": {"lat": 38.7116, "lon": -93.2287},  # Sedalia
    "SHR": {"lat": 32.4997, "lon": -93.7567},  # Shreveport Sportran Intermodal Terminal
    "SMC": {"lat": 29.8766, "lon": -97.9410},  # San Marcos
    "SND": {"lat": 30.1400, "lon": -102.3987},  # Sanderson
    "SPL": {"lat": 46.3546, "lon": -94.7953},  # Staples
    "STN": {"lat": 48.3198, "lon": -102.3894},  # Stanley
    "TAY": {"lat": 30.5677, "lon": -97.4078},  # Taylor
    "TOH": {"lat": 43.9860, "lon": -90.5053},  # Tomah
    "TOP": {"lat": 39.0514, "lon": -95.6649},  # Topeka
    "TPL": {"lat": 31.0959, "lon": -97.3458},  # Temple
    "TRI": {"lat": 37.1727, "lon": -104.5080},  # Trinidad
    "TXA": {"lat": 33.4201, "lon": -94.0431},  # Texarkana
    "WAH": {"lat": 38.5615, "lon": -91.0127},  # Washington
    "WAR": {"lat": 38.7627, "lon": -93.7409},  # Warrensburg
    "WEL": {"lat": 37.2749, "lon": -97.3818},  # Wellington
    "WIC": {"lat": 37.6847, "lon": -97.3341},  # Wichita
    "WIN": {"lat": 44.0444, "lon": -91.6401},  # Winona
    "WNR": {"lat": 36.0677, "lon": -90.9568},  # Walnut Ridge
    "WTN": {"lat": 48.1430, "lon": -103.6209},  # Williston
    "YAZ": {"lat": 32.8485, "lon": -90.4152},  # Yazoo City
    # New England Amtrak stations
    "AMS": {"lat": 42.9537, "lon": -74.2195},  # Amsterdam
    "AST": {"lat": 43.3134, "lon": -79.8557},  # Aldershot
    "BFX": {"lat": 42.8784, "lon": -78.8737},  # Buffalo
    "BLF": {"lat": 43.1365, "lon": -72.4446},  # Bellows Falls
    "BON": {"lat": 42.3662, "lon": -71.0611},  # Boston North
    "BRA": {"lat": 42.8508, "lon": -72.5565},  # Brattleboro
    "BRK": {"lat": 43.9114, "lon": -69.9655},  # Brunswick
    "CBN": {"lat": 43.1092, "lon": -79.0584},  # Canadian Border
    "CNV": {"lat": 43.6134, "lon": -73.1713},  # Castleton
    "FED": {"lat": 43.2696, "lon": -73.5806},  # Fort Edward
    "FRA": {"lat": 42.2760, "lon": -71.4200},  # Framingham
    "FRE": {"lat": 43.8550, "lon": -70.1024},  # Freeport
    "FTC": {"lat": 43.8538, "lon": -73.3897},  # Ticonderoga
    "GFD": {"lat": 42.5855, "lon": -72.6008},  # Greenfield
    "GMS": {"lat": 43.1959, "lon": -79.5579},  # Grimsby
    "HHL": {"lat": 42.7733, "lon": -71.0864},  # Haverhill
    "HLK": {"lat": 42.2042, "lon": -72.6023},  # Holyoke
    "HUD": {"lat": 42.2539, "lon": -73.7977},  # Hudson
    "MBY": {"lat": 44.0174, "lon": -73.1698},  # Middlebury
    "MPR": {"lat": 44.2557, "lon": -72.6064},  # Montpelier-Berlin
    "NFL": {"lat": 43.1099, "lon": -79.0553},  # Niagara Falls
    "NFS": {"lat": 43.1087, "lon": -79.0633},  # Niagara Falls
    "NHT": {"lat": 42.3189, "lon": -72.6264},  # Northampton
    "OKL": {"lat": 43.4554, "lon": -79.6824},  # Oakville
    "ORB": {"lat": 43.5143, "lon": -70.3762},  # Old Orchard Beach
    "PIT": {"lat": 42.4516, "lon": -73.2538},  # Pittsfield
    "PLB": {"lat": 44.6967, "lon": -73.4463},  # Plattsburgh
    "POH": {"lat": 44.0423, "lon": -73.4588},  # Port Henry
    "ROM": {"lat": 43.1994, "lon": -75.4500},  # Rome
    "RPH": {"lat": 43.9224, "lon": -72.6655},  # Randolph
    "RSP": {"lat": 44.9949, "lon": -73.3711},  # Rouses Point
    "RTE": {"lat": 42.2102, "lon": -71.1479},  # Route 128
    "RUD": {"lat": 43.6058, "lon": -72.9815},  # Rutland
    "SAB": {"lat": 44.8124, "lon": -73.0862},  # St. Albans
    "SAO": {"lat": 43.4962, "lon": -70.4491},  # Saco
    "SAR": {"lat": 43.0828, "lon": -73.8100},  # Saratoga Springs
    "SCA": {"lat": 43.1478, "lon": -79.2560},  # St. Catherines
    "SDY": {"lat": 42.8147, "lon": -73.9429},  # Schenectady
    "SLQ": {"lat": 45.4989, "lon": -73.5073},  # St-Lambert
    "TWO": {"lat": 43.6454, "lon": -79.3808},  # Toronto
    "UCA": {"lat": 43.1039, "lon": -75.2234},  # Utica
    "VRN": {"lat": 44.1809, "lon": -73.2488},  # Ferrisburgh
    "WAB": {"lat": 44.3350, "lon": -72.7518},  # Waterbury-Stowe
    "WEM": {"lat": 43.3208, "lon": -70.6122},  # Wells
    "WHL": {"lat": 43.5547, "lon": -73.4032},  # Whitehall
    "WNM": {"lat": 43.4799, "lon": -72.3850},  # Windsor-Mt. Ascutney
    "WOB": {"lat": 42.5174, "lon": -71.1438},  # Woburn
    "WOR": {"lat": 42.2615, "lon": -71.7948},  # Worcester Union
    "WRJ": {"lat": 43.6478, "lon": -72.3173},  # White River Junction
    "WSP": {"lat": 44.1873, "lon": -73.4518},  # Westport
    # Pacific Northwest Amtrak stations
    "ALY": {"lat": 44.6305, "lon": -123.1028},  # Albany
    "BEL": {"lat": 48.7203, "lon": -122.5113},  # Bellingham
    "BNG": {"lat": 45.7150, "lon": -121.4687},  # Bingen-White Salmon
    "BRO": {"lat": 48.5341, "lon": -113.0132},  # Browning
    "CMO": {"lat": 43.2168, "lon": -121.7816},  # Chemult
    "CTL": {"lat": 46.7175, "lon": -122.9531},  # Centralia
    "CUT": {"lat": 48.6384, "lon": -112.3316},  # Cut Bank
    "EDM": {"lat": 47.8111, "lon": -122.3841},  # Edmonds
    "EPH": {"lat": 47.3209, "lon": -119.5493},  # Ephrata
    "ESM": {"lat": 48.2755, "lon": -113.6109},  # Essex
    "EVR": {"lat": 47.9754, "lon": -122.1979},  # Everett
    "GGW": {"lat": 48.1949, "lon": -106.6362},  # Glasgow
    "GRA": {"lat": 40.0842, "lon": -105.9355},  # Granby
    "KEL": {"lat": 46.1423, "lon": -122.9130},  # Kelso-Longview
    "KFS": {"lat": 42.2255, "lon": -121.7720},  # Klamath Falls
    "LIB": {"lat": 48.3948, "lon": -115.5489},  # Libby
    "LWA": {"lat": 47.6065, "lon": -120.6440},  # Leavenworth
    "MAL": {"lat": 48.3605, "lon": -107.8722},  # Malta
    "MVW": {"lat": 48.4185, "lon": -122.3347},  # Mount Vernon
    "OLW": {"lat": 46.9913, "lon": -122.7941},  # Olympia-Lacey
    "ORC": {"lat": 45.3661, "lon": -122.5959},  # Oregon City
    "PRO": {"lat": 40.2260, "lon": -111.6640},  # Provo
    "PSC": {"lat": 46.2370, "lon": -119.0877},  # Pasco
    "SBY": {"lat": 48.5067, "lon": -111.8566},  # Shelby
    "SPT": {"lat": 48.2762, "lon": -116.5456},  # Sandpoint
    "STW": {"lat": 48.2426, "lon": -122.3499},  # Stanwood
    "TUK": {"lat": 47.4611, "lon": -122.2403},  # Tukwila
    "VAC": {"lat": 49.2738, "lon": -123.0983},  # Vancouver
    "VAN": {"lat": 45.6289, "lon": -122.6865},  # Vancouver
    "WEN": {"lat": 47.4216, "lon": -120.3066},  # Wenatchee
    "WGL": {"lat": 48.4962, "lon": -113.9792},  # West Glacier
    "WIH": {"lat": 45.6577, "lon": -120.9661},  # Wishram
    "WPT": {"lat": 48.0917, "lon": -105.6427},  # Wolf Point
    # South Central Amtrak stations
    "ATN": {"lat": 33.6491, "lon": -85.8321},  # Anniston
    "BAS": {"lat": 30.3087, "lon": -89.3340},  # Bay St Louis
    "BDT": {"lat": 27.5285, "lon": -82.5123},  # Bradenton
    "BIX": {"lat": 30.3991, "lon": -88.8916},  # Biloxi Amtrak Sta
    "CAM": {"lat": 34.2482, "lon": -80.6252},  # Camden
    "DFB": {"lat": 26.3171, "lon": -80.1221},  # Deerfield Beach
    "DNK": {"lat": 33.3262, "lon": -81.1436},  # Denmark
    "GNS": {"lat": 34.2889, "lon": -83.8197},  # Gainesville
    "GUF": {"lat": 30.3690, "lon": -89.0948},  # Gulfport Amtrak Sta
    "HBG": {"lat": 31.3269, "lon": -89.2865},  # Hattiesburg
    "HOL": {"lat": 26.0116, "lon": -80.1679},  # Hollywood
    "JSP": {"lat": 31.6056, "lon": -81.8822},  # Jesup
    "LAK": {"lat": 28.0456, "lon": -81.9519},  # Lakeland
    "LAU": {"lat": 31.6922, "lon": -89.1279},  # Laurel
    "MEI": {"lat": 32.3642, "lon": -88.6966},  # Meridian Union
    "OKE": {"lat": 27.2519, "lon": -80.8308},  # Okeechobee
    "PAG": {"lat": 30.3678, "lon": -88.5595},  # Pascagoula
    "PAK": {"lat": 29.6497, "lon": -81.6405},  # Palatka
    "PIC": {"lat": 30.5246, "lon": -89.6803},  # Picayune
    "SBG": {"lat": 27.4966, "lon": -81.4342},  # Sebring
    "SDL": {"lat": 30.2784, "lon": -89.7826},  # Slidell
    "SFA": {"lat": 28.8085, "lon": -81.2913},  # Sanford Amtrak Auto Train
    "STP": {"lat": 27.8430, "lon": -82.6444},  # St. Petersburg
    "TCA": {"lat": 34.5785, "lon": -83.3315},  # Toccoa
    "TCL": {"lat": 33.1932, "lon": -87.5602},  # Tuscaloosa
    "WDO": {"lat": 29.7905, "lon": -82.1667},  # Waldo
    "WWD": {"lat": 28.8662, "lon": -82.0395},  # Wildwood
    "YEM": {"lat": 32.6883, "lon": -80.8469},  # Yemassee
    # Southeast Amtrak stations
    "BCV": {"lat": 38.7973, "lon": -77.2988},  # Burke Centre
    "BNC": {"lat": 36.0942, "lon": -79.4345},  # Burlington
    "CLF": {"lat": 37.8145, "lon": -79.8274},  # Clifton Forge
    "CLP": {"lat": 38.4724, "lon": -77.9934},  # Culpeper
    "CYN": {"lat": 35.7883, "lon": -78.7822},  # Cary
    "DAN": {"lat": 36.5841, "lon": -79.3840},  # Danville
    "FAY": {"lat": 35.0550, "lon": -78.8848},  # Fayetteville
    "FBG": {"lat": 38.2984, "lon": -77.4572},  # Fredericksburg
    "GBO": {"lat": 35.3857, "lon": -78.0033},  # Goldsboro
    "GRO": {"lat": 36.0698, "lon": -79.7871},  # Greensboro
    "HVL": {"lat": 34.8912, "lon": -76.9261},  # Havelock
    "KNC": {"lat": 35.2437, "lon": -77.5845},  # Kinston
    "MHD": {"lat": 34.7214, "lon": -76.7157},  # Morehead City
    "QAN": {"lat": 38.5219, "lon": -77.2930},  # Quantico
    "SEB": {"lat": 38.9727, "lon": -76.8436},  # Seabrook
    "SOP": {"lat": 35.1751, "lon": -79.3903},  # Southern Pines
    "SSM": {"lat": 35.5328, "lon": -78.2801},  # Selma
    "STA": {"lat": 38.1476, "lon": -79.0718},  # Staunton
    "SWB": {"lat": 34.6971, "lon": -77.1396},  # Swansboro
    "WDB": {"lat": 38.6589, "lon": -77.2479},  # Woodbridge
    "WMN": {"lat": 34.2512, "lon": -77.8749},  # Wilmington
    # Southwest Amtrak stations
    "BEN": {"lat": 31.9688, "lon": -110.2969},  # Benson
    "DEM": {"lat": 32.2718, "lon": -107.7543},  # Deming
    "GJT": {"lat": 39.0644, "lon": -108.5699},  # Grand Junction
    "GLP": {"lat": 35.5292, "lon": -108.7405},  # Gallup
    "GRI": {"lat": 38.9920, "lon": -110.1652},  # Green River
    "GSC": {"lat": 39.5479, "lon": -107.3232},  # Glenwood Springs
    "HER": {"lat": 39.6840, "lon": -110.8539},  # Helper
    "KNG": {"lat": 35.1883, "lon": -114.0528},  # Kingman
    "LDB": {"lat": 32.3501, "lon": -108.7070},  # Lordsburg
    "LMY": {"lat": 35.4810, "lon": -105.8800},  # Lamy
    "LSV": {"lat": 35.5934, "lon": -105.2128},  # Las Vegas
    "MRC": {"lat": 33.0563, "lon": -112.0471},  # Maricopa
    "NDL": {"lat": 34.8406, "lon": -114.6062},  # Needles
    "PHA": {"lat": 33.4364, "lon": -112.0130},  # Phoenix Sky Harbor Airport
    "PXN": {"lat": 33.6395, "lon": -112.1192},  # North Phoenix Metro Center Transit
    "SAF": {"lat": 35.6843, "lon": -105.9466},  # Santa Fe
    "WIP": {"lat": 39.9476, "lon": -105.8174},  # Winter Park/Fraser
    "WLO": {"lat": 35.0217, "lon": -110.6950},  # Winslow
    "WMH": {"lat": 35.2511, "lon": -112.1981},  # Williams
    "WPR": {"lat": 39.8876, "lon": -105.7632},  # Winter Park Ski Resort
    "WPS": {"lat": 39.8837, "lon": -105.7618},  # Winter Park
    "YUM": {"lat": 32.7231, "lon": -114.6156},  # Yuma
    # LIRR stations (Long Island Rail Road)
    "ABT": {"lat": 40.77206317, "lon": -73.64169095},  # Albertson
    "AGT": {"lat": 40.98003964, "lon": -72.13233416},  # Amagansett
    "AVL": {"lat": 40.68024859, "lon": -73.42031192},  # Amityville
    "LAT": {"lat": 40.68359596, "lon": -73.97567112},  # Atlantic Terminal
    "ADL": {"lat": 40.76144288, "lon": -73.78995927},  # Auburndale
    "BTA": {"lat": 40.70068942, "lon": -73.32405561},  # Babylon
    "BWN": {"lat": 40.65673224, "lon": -73.60716245},  # Baldwin
    "BSR": {"lat": 40.72443344, "lon": -73.25408295},  # Bay Shore
    "BSD": {"lat": 40.76315241, "lon": -73.77124986},  # Bayside
    "BRS": {"lat": 40.72220443, "lon": -73.71665289},  # Bellerose
    "BMR": {"lat": 40.66880043, "lon": -73.52886016},  # Bellmore
    "BPT": {"lat": 40.7737389, "lon": -72.94396574},  # Bellport
    "BRT": {"lat": 40.71368754, "lon": -73.72829722},  # Belmont Park
    "BPG": {"lat": 40.74303924, "lon": -73.48343821},  # Bethpage
    "BWD": {"lat": 40.78083474, "lon": -73.24361074},  # Brentwood
    "BHN": {"lat": 40.93898378, "lon": -72.31004593},  # Bridgehampton
    "BDY": {"lat": 40.76165318, "lon": -73.80176612},  # Broadway LIRR
    "CPL": {"lat": 40.74920704, "lon": -73.60365242},  # Carle Place
    "CHT": {"lat": 40.62217451, "lon": -73.72618275},  # Cedarhurst
    "CI": {"lat": 40.79185312, "lon": -73.19486082},  # Central Islip
    "CAV": {"lat": 40.64831835, "lon": -73.6639675},  # Centre Avenue
    "CSH": {"lat": 40.83563832, "lon": -73.45108591},  # Cold Spring Harbor
    "CPG": {"lat": 40.68101528, "lon": -73.39834027},  # Copiague
    "LCLP": {"lat": 40.72145656, "lon": -73.62967386},  # Country Life Press
    "DPK": {"lat": 40.76948364, "lon": -73.29356494},  # Deer Park
    "DGL": {"lat": 40.76806862, "lon": -73.74941265},  # Douglaston
    "EHN": {"lat": 40.96508629, "lon": -72.19324238},  # East Hampton
    "ENY": {"lat": 40.67581191, "lon": -73.90280882},  # East New York
    "ERY": {"lat": 40.64221085, "lon": -73.65821626},  # East Rockaway
    "EWN": {"lat": 40.7560191, "lon": -73.63940764},  # East Williston
    "EMT": {"lat": 40.720074, "lon": -73.725549},  # Elmont-UBS Arena
    "LFRY": {"lat": 40.60914311, "lon": -73.75054135},  # Far Rockaway
    "LFMD": {"lat": 40.73591503, "lon": -73.44123878},  # Farmingdale
    "FPK": {"lat": 40.72463725, "lon": -73.70639714},  # Floral Park
    "FLS": {"lat": 40.75789494, "lon": -73.83134684},  # Flushing Main Street
    "FHL": {"lat": 40.71957556, "lon": -73.84481402},  # Forest Hills
    "FPT": {"lat": 40.65745799, "lon": -73.58232401},  # Freeport
    "GCY": {"lat": 40.72310156, "lon": -73.64036107},  # Garden City
    "GBN": {"lat": 40.64925173, "lon": -73.70183483},  # Gibson
    "GCV": {"lat": 40.86583421, "lon": -73.61616614},  # Glen Cove
    "GHD": {"lat": 40.83222531, "lon": -73.62611822},  # Glen Head
    "GST": {"lat": 40.85798112, "lon": -73.62121715},  # Glen Street
    "GCT": {
        "lat": 40.752998,
        "lon": -73.977056,
    },  # Grand Central Terminal (shared with MNR)
    "GNK": {"lat": 40.78721647, "lon": -73.72610046},  # Great Neck
    "GRV": {"lat": 40.74044444, "lon": -73.17019585},  # Great River
    "GWN": {"lat": 40.86866524, "lon": -73.36284977},  # Greenlawn
    "GPT": {"lat": 41.09970991, "lon": -72.36310396},  # Greenport
    "LGVL": {"lat": 40.81571566, "lon": -73.62687152},  # Greenvale
    "HBY": {"lat": 40.87660916, "lon": -72.52394936},  # Hampton Bays
    "HGN": {"lat": 40.69491356, "lon": -73.64620888},  # Hempstead Gardens
    "LHEM": {"lat": 40.71329663, "lon": -73.62503239},  # Hempstead
    "HWT": {"lat": 40.63676432, "lon": -73.70513866},  # Hewlett
    "LHVL": {"lat": 40.76717491, "lon": -73.52853322},  # Hicksville
    "LHOL": {"lat": 40.71018151, "lon": -73.76675252},  # Hollis
    "HPA": {"lat": 40.74239046, "lon": -73.94678997},  # Hunterspoint Avenue
    "LHUN": {"lat": 40.85300971, "lon": -73.40952576},  # Huntington
    "IWD": {"lat": 40.61228773, "lon": -73.74418354},  # Inwood
    "IPK": {"lat": 40.60129906, "lon": -73.65474248},  # Island Park
    "ISP": {"lat": 40.73583449, "lon": -73.20932145},  # Islip
    "JAM": {"lat": 40.69960817, "lon": -73.80852987},  # Jamaica
    "KGN": {"lat": 40.70964917, "lon": -73.83088807},  # Kew Gardens
    "KPK": {"lat": 40.88366659, "lon": -73.25624757},  # Kings Park
    "LLVW": {"lat": 40.68585582, "lon": -73.65213777},  # Lakeview
    "LTN": {"lat": 40.66848304, "lon": -73.75174687},  # Laurelton
    "LCE": {"lat": 40.6157347, "lon": -73.73589955},  # Lawrence
    "LHT": {"lat": 40.68826504, "lon": -73.36921149},  # Lindenhurst
    "LLNK": {"lat": 40.77504393, "lon": -73.74064662},  # Little Neck
    "LLMR": {"lat": 40.67513907, "lon": -73.76504303},  # Locust Manor
    "LVL": {"lat": 40.87446697, "lon": -73.59830284},  # Locust Valley
    "LBH": {"lat": 40.5901817, "lon": -73.66481822},  # Long Beach
    "LIC": {"lat": 40.74134343, "lon": -73.95763922},  # Long Island City
    "LYN": {"lat": 40.65605814, "lon": -73.67607083},  # Lynbrook
    "LMVN": {"lat": 40.67547844, "lon": -73.66886364},  # Malverne
    "MHT": {"lat": 40.7967241, "lon": -73.69989909},  # Manhasset
    "LMPK": {"lat": 40.6778591, "lon": -73.45473724},  # Massapequa Park
    "MQA": {"lat": 40.67693014, "lon": -73.46905552},  # Massapequa
    "MSY": {"lat": 40.79898815, "lon": -72.86442272},  # Mastic-Shirley
    "MAK": {"lat": 40.99179354, "lon": -72.53606243},  # Mattituck
    "MFD": {"lat": 40.81739665, "lon": -72.99890946},  # Medford
    "MAV": {"lat": 40.73516903, "lon": -73.66252148},  # Merillon Avenue
    "MRK": {"lat": 40.6638004, "lon": -73.55062102},  # Merrick
    "LSSM": {"lat": 40.75239835, "lon": -73.84370059},  # Mets-Willets Point
    "LMIN": {"lat": 40.74034743, "lon": -73.64086293},  # Mineola
    "MTK": {"lat": 41.04710896, "lon": -71.95388103},  # Montauk
    "LMHL": {"lat": 40.76270926, "lon": -73.81453928},  # Murray Hill LIRR
    "NBD": {"lat": 40.72296245, "lon": -73.66269823},  # Nassau Boulevard
    "NHP": {"lat": 40.73075708, "lon": -73.68095886},  # New Hyde Park
    "NPT": {"lat": 40.88064972, "lon": -73.32848513},  # Northport
    "NAV": {"lat": 40.67838785, "lon": -73.94822108},  # Nostrand Avenue
    "ODL": {"lat": 40.74343275, "lon": -73.13243549},  # Oakdale
    "ODE": {"lat": 40.63472102, "lon": -73.65466582},  # Oceanside
    "OBY": {"lat": 40.87533774, "lon": -73.53403366},  # Oyster Bay
    "PGE": {"lat": 40.76187901, "lon": -73.01574451},  # Patchogue
    "PLN": {"lat": 40.74535851, "lon": -73.39960092},  # Pinelawn
    "PDM": {"lat": 40.81069853, "lon": -73.69521438},  # Plandome
    "PJN": {"lat": 40.9345531, "lon": -73.05250164},  # Port Jefferson
    "PWS": {"lat": 40.82903533, "lon": -73.687401},  # Port Washington
    "QVG": {"lat": 40.71745785, "lon": -73.73645989},  # Queens Village
    "RHD": {"lat": 40.91983928, "lon": -72.66691054},  # Riverhead
    "RVC": {"lat": 40.65831811, "lon": -73.64654935},  # Rockville Centre
    "RON": {"lat": 40.80808613, "lon": -73.10594023},  # Ronkonkoma
    "ROS": {"lat": 40.66594933, "lon": -73.73554816},  # Rosedale
    "RSN": {"lat": 40.7904781, "lon": -73.64326175},  # Roslyn
    "SVL": {"lat": 40.74035373, "lon": -73.08645531},  # Sayville
    "SCF": {"lat": 40.85236805, "lon": -73.62541695},  # Sea Cliff
    "SFD": {"lat": 40.67572393, "lon": -73.48656847},  # Seaford
    "LSTN": {"lat": 40.85654755, "lon": -73.19803235},  # Smithtown
    "SHN": {"lat": 40.89471874, "lon": -72.39012376},  # Southampton
    "SHD": {"lat": 41.06632089, "lon": -72.4278803},  # Southold
    "LSPK": {"lat": 40.82131516, "lon": -72.70526225},  # Speonk
    "LSAB": {"lat": 40.69118348, "lon": -73.76550937},  # St. Albans
    "LSJM": {"lat": 40.88216931, "lon": -73.15950725},  # St. James
    "SMR": {"lat": 40.72302771, "lon": -73.68102041},  # Stewart Manor
    "LSBK": {"lat": 40.92032252, "lon": -73.12854943},  # Stony Brook
    "SYT": {"lat": 40.82485746, "lon": -73.5004456},  # Syosset
    "VSM": {"lat": 40.66151762, "lon": -73.70475875},  # Valley Stream
    "WGH": {"lat": 40.67299016, "lon": -73.50896484},  # Wantagh
    "WHD": {"lat": 40.70196099, "lon": -73.64164361},  # West Hempstead
    "WBY": {"lat": 40.75345386, "lon": -73.5858661},  # Westbury
    "WHN": {"lat": 40.83030532, "lon": -72.65032454},  # Westhampton
    "LWWD": {"lat": 40.66837227, "lon": -73.68120878},  # Westwood LIRR
    "WMR": {"lat": 40.63133646, "lon": -73.71371544},  # Woodmere
    "WDD": {"lat": 40.74585067, "lon": -73.90297516},  # Woodside
    "WYD": {"lat": 40.75480101, "lon": -73.35806588},  # Wyandanch
    "YPK": {"lat": 40.82561319, "lon": -72.91587848},  # Yaphank
    # Metro-North Railroad stations (GCT shared with LIRR above)
    "M125": {"lat": 40.805157, "lon": -73.939149},  # Harlem-125th Street
    "MEYS": {"lat": 40.8253, "lon": -73.9299},  # Yankees-E 153 St
    "MMRH": {"lat": 40.854252, "lon": -73.919583},  # Morris Heights
    "MUNH": {"lat": 40.862248, "lon": -73.91312},  # University Heights
    "MMBL": {"lat": 40.874333, "lon": -73.910941},  # Marble Hill
    "MSDV": {"lat": 40.878245, "lon": -73.921455},  # Spuyten Duyvil
    "MRVD": {"lat": 40.903981, "lon": -73.914126},  # Riverdale
    "MLUD": {"lat": 40.924972, "lon": -73.904612},  # Ludlow
    "MYON": {"lat": 40.935795, "lon": -73.902668},  # Yonkers
    "MGWD": {"lat": 40.950496, "lon": -73.899062},  # Glenwood
    "MGRY": {"lat": 40.972705, "lon": -73.889069},  # Greystone
    "MHOH": {"lat": 40.994109, "lon": -73.884512},  # Hastings-on-Hudson
    "MDBF": {"lat": 41.012459, "lon": -73.87949},  # Dobbs Ferry
    "MARD": {"lat": 41.026198, "lon": -73.876543},  # Ardsley-on-Hudson
    "MIRV": {"lat": 41.039993, "lon": -73.873083},  # Irvington
    "MTTN": {"lat": 41.076473, "lon": -73.864563},  # Tarrytown
    "MPHM": {"lat": 41.09492, "lon": -73.869755},  # Philipse Manor
    "MSCB": {"lat": 41.135763, "lon": -73.866163},  # Scarborough
    "MOSS": {"lat": 41.157663, "lon": -73.869281},  # Ossining
    "MCRH": {"lat": 41.189903, "lon": -73.882394},  # Croton-Harmon
    "MCRT": {"lat": 41.246259, "lon": -73.921884},  # Cortlandt
    "MPKS": {"lat": 41.285962, "lon": -73.93042},  # Peekskill
    "MMAN": {"lat": 41.332601, "lon": -73.970426},  # Manitou
    "MGAR": {"lat": 41.38178, "lon": -73.947202},  # Garrison
    "MCSP": {"lat": 41.415283, "lon": -73.95809},  # Cold Spring
    "MBRK": {"lat": 41.450181, "lon": -73.982449},  # Breakneck Ridge
    "MBCN": {"lat": 41.504007, "lon": -73.984528},  # Beacon
    "MNHB": {"lat": 41.587448, "lon": -73.947226},  # New Hamburg
    "MPOK": {"lat": 41.705839, "lon": -73.937946},  # Poughkeepsie
    "MMEL": {"lat": 40.825761, "lon": -73.915231},  # Melrose
    "MTRM": {"lat": 40.847301, "lon": -73.89955},  # Tremont
    "MFOR": {"lat": 40.8615, "lon": -73.89058},  # Fordham
    "MBOG": {"lat": 40.866555, "lon": -73.883109},  # Botanical Garden
    "MWBG": {"lat": 40.878569, "lon": -73.871064},  # Williams Bridge
    "MWDL": {"lat": 40.895361, "lon": -73.862916},  # Woodlawn
    "MWKF": {"lat": 40.905936, "lon": -73.85568},  # Wakefield
    "MMVW": {"lat": 40.912142, "lon": -73.851129},  # Mt Vernon West
    "MFLT": {"lat": 40.92699, "lon": -73.83948},  # Fleetwood
    "MBRX": {"lat": 40.93978, "lon": -73.835208},  # Bronxville
    "MTUC": {"lat": 40.949393, "lon": -73.830166},  # Tuckahoe
    "MCWD": {"lat": 40.958997, "lon": -73.820564},  # Crestwood
    "MSCD": {"lat": 40.989168, "lon": -73.808634},  # Scarsdale
    "MHSD": {"lat": 41.010333, "lon": -73.796407},  # Hartsdale
    "MWPL": {"lat": 41.032589, "lon": -73.775208},  # White Plains
    "MNWP": {"lat": 41.049806, "lon": -73.773142},  # North White Plains
    "MVAL": {"lat": 41.072819, "lon": -73.772599},  # Valhalla
    "MMTP": {"lat": 41.095877, "lon": -73.793822},  # Mt Pleasant
    "MHWT": {"lat": 41.108581, "lon": -73.79625},  # Hawthorne
    "MPLV": {"lat": 41.135222, "lon": -73.792661},  # Pleasantville
    "MCHP": {"lat": 41.158015, "lon": -73.774885},  # Chappaqua
    "MMTK": {"lat": 41.208242, "lon": -73.729778},  # Mt Kisco
    "MBDH": {"lat": 41.237316, "lon": -73.699936},  # Bedford Hills
    "MKAT": {"lat": 41.259552, "lon": -73.684155},  # Katonah
    "MGLD": {"lat": 41.294338, "lon": -73.677655},  # Goldens Bridge
    "MPRD": {"lat": 41.325775, "lon": -73.659061},  # Purdy's
    "MCFL": {"lat": 41.347722, "lon": -73.662269},  # Croton Falls
    "MBRS": {"lat": 41.39447, "lon": -73.619802},  # Brewster
    "MSET": {"lat": 41.413203, "lon": -73.623787},  # Southeast
    "MPAT": {"lat": 41.511827, "lon": -73.604584},  # Patterson
    "MPAW": {"lat": 41.564205, "lon": -73.600524},  # Pawling
    "MAPT": {"lat": 41.592871, "lon": -73.588032},  # Appalachian Trail
    "MHVW": {"lat": 41.637525, "lon": -73.57145},  # Harlem Valley-Wingdale
    "MDVP": {"lat": 41.740401, "lon": -73.576502},  # Dover Plains
    "MTMR": {"lat": 41.779938, "lon": -73.558204},  # Tenmile River
    "MWAS": {"lat": 41.814722, "lon": -73.562197},  # Wassaic
    "MMVE": {"lat": 40.912161, "lon": -73.832185},  # Mt Vernon East
    "MPEL": {"lat": 40.910321, "lon": -73.810242},  # Pelham
    "MNRC": {"lat": 40.911605, "lon": -73.783807},  # New Rochelle
    "MLRM": {"lat": 40.933394, "lon": -73.759792},  # Larchmont
    "MMAM": {"lat": 40.954061, "lon": -73.736125},  # Mamaroneck
    "MHRR": {"lat": 40.969432, "lon": -73.712964},  # Harrison
    "MRYE": {"lat": 40.985922, "lon": -73.682553},  # Rye
    "MPCH": {"lat": 41.000732, "lon": -73.6647},  # Port Chester
    "MGRN": {"lat": 41.021277, "lon": -73.624621},  # Greenwich
    "MCOC": {"lat": 41.030171, "lon": -73.598306},  # Cos Cob
    "MRSD": {"lat": 41.031682, "lon": -73.588173},  # Riverside
    "MODG": {"lat": 41.033817, "lon": -73.565859},  # Old Greenwich
    "MSTM": {"lat": 41.046611, "lon": -73.542846},  # Stamford
    "MNOH": {"lat": 41.069041, "lon": -73.49788},  # Noroton Heights
    "MDAR": {"lat": 41.076913, "lon": -73.472966},  # Darien
    "MROW": {"lat": 41.077456, "lon": -73.445527},  # Rowayton
    "MSNW": {"lat": 41.09673, "lon": -73.421132},  # South Norwalk
    "MENW": {"lat": 41.103996, "lon": -73.404588},  # East Norwalk
    "MWPT": {"lat": 41.118928, "lon": -73.371413},  # Westport
    "MGRF": {"lat": 41.122265, "lon": -73.315408},  # Green's Farms
    "MSPT": {"lat": 41.134844, "lon": -73.28897},  # Southport
    "MFFD": {"lat": 41.143077, "lon": -73.257742},  # Fairfield
    "MFBR": {"lat": 41.161, "lon": -73.234336},  # Fairfield-Black Rock
    "MBGP": {"lat": 41.178677, "lon": -73.187076},  # Bridgeport
    "MSTR": {"lat": 41.194255, "lon": -73.131532},  # Stratford
    "MMIL": {"lat": 41.223231, "lon": -73.057647},  # Milford
    "MWHN": {"lat": 41.27142, "lon": -72.963488},  # West Haven
    "MNHV": {"lat": 41.296501, "lon": -72.92829},  # New Haven
    "MNSS": {"lat": 41.304979, "lon": -72.921747},  # New Haven-State St
    "MGLB": {"lat": 41.070547, "lon": -73.520021},  # Glenbrook
    "MSPD": {"lat": 41.08876, "lon": -73.517828},  # Springdale
    "MTMH": {"lat": 41.116012, "lon": -73.498149},  # Talmadge Hill
    "MNCA": {"lat": 41.146305, "lon": -73.495626},  # New Canaan
    "MMR7": {"lat": 41.146618, "lon": -73.427859},  # Merritt 7
    "MWIL": {"lat": 41.196202, "lon": -73.432434},  # Wilton
    "MCAN": {"lat": 41.21662, "lon": -73.426703},  # Cannondale
    "MBVL": {"lat": 41.26763, "lon": -73.441421},  # Branchville
    "MRED": {"lat": 41.325684, "lon": -73.4338},  # Redding
    "MBTH": {"lat": 41.376225, "lon": -73.418171},  # Bethel
    "MDBY": {"lat": 41.396146, "lon": -73.44879},  # Danbury
    "MDBS": {"lat": 41.319718, "lon": -73.083548},  # Derby-Shelton
    "MANS": {"lat": 41.344156, "lon": -73.079892},  # Ansonia
    "MSYM": {"lat": 41.395139, "lon": -73.072499},  # Seymour
    "MBCF": {"lat": 41.441752, "lon": -73.06359},  # Beacon Falls
    "MNAU": {"lat": 41.494204, "lon": -73.052655},  # Naugatuck
    "MWTB": {"lat": 41.552728, "lon": -73.046126},  # Waterbury
}


def get_station_coordinates(code: str) -> dict[str, float] | None:
    """Get station coordinates for mapping.

    Args:
        code: Two-character station code

    Returns:
        Dict with lat/lon or None if not found
    """
    return STATION_COORDINATES.get(code)


# Discovery stations for train polling - centralized configuration
DISCOVERY_STATIONS = [
    "NY",  # New York Penn Station
    "NP",  # Newark Penn Station
    "TR",  # Trenton
    "LB",  # Long Branch
    "PL",  # Plauderville
    "DN",  # Denville
    "MP",  # Metropark
    "HB",  # Hoboken
    "HG",  # High Bridge
    "GL",  # Gladstone
    "ND",  # Newark Broad Street
    "HQ",  # Hackettstown
    "DV",  # Dover
    "JA",  # Jersey Avenue
    "RA",  # Raritan
    "ST",  # Summit - major Morris & Essex terminal for inbound trains
    "SV",  # Spring Valley - Pascack Valley Line terminus
]


# =============================================================================
# GTFS Station Mapping
# =============================================================================

# Reverse mapping from station name (normalized) to code for GTFS matching
# Built from STATION_NAMES for efficient lookup
_NORMALIZED_NAME_TO_CODE: dict[str, str] = {}


def _normalize_station_name(name: str) -> str:
    """Normalize station name for fuzzy matching.

    Handles variations like:
    - "NEW YORK PENN STATION" -> "new york penn station"
    - "Newark Penn Station" -> "newark penn station"
    - "Trenton Transit Center" -> "trenton transit center"
    """
    return name.lower().strip()


def _build_name_to_code_map() -> dict[str, str]:
    """Build reverse mapping from normalized names to codes."""
    if _NORMALIZED_NAME_TO_CODE:
        return _NORMALIZED_NAME_TO_CODE

    for code, name in STATION_NAMES.items():
        normalized = _normalize_station_name(name)
        _NORMALIZED_NAME_TO_CODE[normalized] = code

        # Also add common variations
        # Remove common suffixes for matching
        for suffix in [" station", " terminal", " transit center"]:
            if normalized.endswith(suffix):
                base = normalized[: -len(suffix)].strip()
                if base not in _NORMALIZED_NAME_TO_CODE:
                    _NORMALIZED_NAME_TO_CODE[base] = code

    return _NORMALIZED_NAME_TO_CODE


def map_gtfs_stop_to_station_code(
    gtfs_stop_id: str, gtfs_stop_name: str, data_source: str
) -> str | None:
    """Map a GTFS stop to our internal station code.

    Args:
        gtfs_stop_id: The GTFS stop_id (numeric for NJT, code for Amtrak)
        gtfs_stop_name: The GTFS stop_name for fallback matching
        data_source: "NJT", "AMTRAK", "PATH", "PATCO", "LIRR", or "MNR"

    Returns:
        Our internal station code or None if no match found
    """
    if data_source == "AMTRAK":
        # Amtrak uses their standard codes as stop_id
        return map_amtrak_station_code(gtfs_stop_id)

    if data_source == "PATCO":
        # PATCO uses numeric stop_id (1-14)
        return PATCO_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_stop_id)

    if data_source == "LIRR":
        # LIRR uses numeric stop_id from MTA GTFS
        return LIRR_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_stop_id)

    if data_source == "MNR":
        # Metro-North uses numeric stop_id from MTA GTFS
        return MNR_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_stop_id)

    if data_source == "PATH":
        # PATH - first try by stop_id (GTFS uses same IDs as Transiter: 26722-26734)
        if gtfs_stop_id in PATH_TRANSITER_TO_INTERNAL_MAP:
            return PATH_TRANSITER_TO_INTERNAL_MAP[gtfs_stop_id]
        # Fallback: match by normalized stop name
        normalized = gtfs_stop_name.lower().strip()
        if normalized in PATH_GTFS_NAME_TO_INTERNAL_MAP:
            return PATH_GTFS_NAME_TO_INTERNAL_MAP[normalized]
        # Try partial match (e.g., "14th Street" matches "14th street")
        for name_pattern, code in PATH_GTFS_NAME_TO_INTERNAL_MAP.items():
            if name_pattern in normalized or normalized in name_pattern:
                return code
        return None

    # For NJ Transit, first try explicit stop_id mapping for known problem stops
    if data_source == "NJT" and gtfs_stop_id in NJT_GTFS_STOP_TO_INTERNAL_MAP:
        return NJT_GTFS_STOP_TO_INTERNAL_MAP[gtfs_stop_id]

    # Then try to match by name
    name_map = _build_name_to_code_map()
    normalized_name = _normalize_station_name(gtfs_stop_name)

    # Direct match
    if normalized_name in name_map:
        return name_map[normalized_name]

    # Try matching just the first part of the name (before any dash or parenthesis)
    for separator in [" - ", " (", "-"]:
        if separator in normalized_name:
            base_name = normalized_name.split(separator)[0].strip()
            if base_name in name_map:
                return name_map[base_name]

    # Try partial matching for common patterns
    # "Penn Station New York" -> match "New York Penn Station"
    for stored_name, code in name_map.items():
        # Check if all words from one are in the other
        stored_words = set(stored_name.split())
        name_words = set(normalized_name.split())
        if len(stored_words & name_words) >= 2:  # At least 2 words match
            # Prefer matches with more overlap
            overlap = len(stored_words & name_words) / max(
                len(stored_words), len(name_words)
            )
            if overlap >= 0.5:
                return code

    return None


def get_station_code_by_name(name: str) -> str | None:
    """Get station code by looking up a station name.

    Args:
        name: Station name to look up

    Returns:
        Station code or None if not found
    """
    name_map = _build_name_to_code_map()
    normalized = _normalize_station_name(name)
    return name_map.get(normalized)
