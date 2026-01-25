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
    "BON": "Boston",
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
}


def get_station_name(code: str) -> str:
    """Get the full station name for a given code.

    Args:
        code: Two-character station code

    Returns:
        Full station name, or the code if not found
    """
    return STATION_NAMES.get(code, code)


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
    "BON": "BON",  # Boston
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
    "BON": "BON",  # Boston
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
# Only includes stops where name-based matching fails
# (Most NJT stops are mapped by fuzzy name matching)
NJT_GTFS_STOP_TO_INTERNAL_MAP: dict[str, str] = {
    "1": "PH",  # 30TH ST. PHL. -> Philadelphia
    "38": "ED",  # EDISON STATION -> Edison
    "85": "MI",  # MIDDLETOWN NJ -> Middletown
    "125": "PJ",  # PRINCETON JCT. -> Princeton Junction
    "126": "FZ",  # RADBURN -> Radburn Fair Lawn
    "128": "17",  # RAMSEY -> Ramsey Route 17
    "148": "TR",  # TRENTON TRANSIT CENTER -> Trenton
    "160": "WR",  # WOOD-RIDGE -> Wood Ridge
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
    "NY": {"lat": 40.7506, "lon": -73.9939},  # New York Penn Station
    "NP": {"lat": 40.7347, "lon": -74.1644},  # Newark Penn Station
    "TR": {"lat": 40.218518, "lon": -74.753923},  # Trenton Transit Center
    "PJ": {"lat": 40.3167, "lon": -74.6233},  # Princeton Junction
    "MP": {"lat": 40.5378, "lon": -74.3562},  # Metropark
    "NA": {"lat": 40.7058, "lon": -74.1608},  # Newark Airport
    "NB": {"lat": 40.4862, "lon": -74.4518},  # New Brunswick
    "SE": {"lat": 40.7612, "lon": -74.0758},  # Secaucus Upper Level
    "SC": {"lat": 40.7612, "lon": -74.0758},  # Secaucus Concourse
    "TS": {"lat": 40.7612, "lon": -74.0758},  # Secaucus Lower Level
    "HB": {"lat": 40.734843, "lon": -74.028043},  # Hoboken Terminal
    "PH": {"lat": 39.9570, "lon": -75.1820},  # Philadelphia 30th Street Station
    "WI": {"lat": 39.7369, "lon": -75.5522},  # Wilmington
    "BA": {"lat": 39.1896, "lon": -76.6934},  # BWI Airport Rail Station
    "BL": {"lat": 39.3081, "lon": -76.6175},  # Baltimore Penn Station
    "WS": {"lat": 38.8973, "lon": -77.0064},  # Washington Union Station
    "BOS": {"lat": 42.3520, "lon": -71.0552},  # Boston South Station
    "BBY": {"lat": 42.3473, "lon": -71.0764},  # Boston Back Bay
    # NJ Coast Line
    "LB": {"lat": 40.3042, "lon": -73.9920},  # Long Branch
    "AP": {"lat": 40.2202, "lon": -74.0120},  # Asbury Park
    "BS": {"lat": 40.1784, "lon": -74.0276},  # Belmar
    "SQ": {"lat": 40.1057, "lon": -74.0500},  # Manasquan
    "PP": {"lat": 40.0917, "lon": -74.0680},  # Point Pleasant Beach
    "BH": {"lat": 40.0585, "lon": -74.1066},  # Bay Head
    "AH": {"lat": 40.2301, "lon": -74.0063},  # Allenhurst
    "EL": {"lat": 40.2689, "lon": -73.9858},  # Elberon
    "LS": {"lat": 40.3369, "lon": -74.0436},  # Little Silver
    "MK": {"lat": 40.3086, "lon": -74.0253},  # Monmouth Park
    "RB": {"lat": 40.3503, "lon": -74.0750},  # Red Bank
    "HZ": {"lat": 40.4236, "lon": -74.1848},  # Hazlet
    "AM": {"lat": 40.4183, "lon": -74.2206},  # Aberdeen-Matawan
    "MI": {"lat": 40.4453, "lon": -74.1126},  # Middletown
    "LA": {"lat": 40.1530, "lon": -74.0340},  # Spring Lake
    "BB": {"lat": 40.1929, "lon": -74.0218},  # Bradley Beach
    # Northeast Corridor
    "EZ": {"lat": 40.667859, "lon": -74.215171},  # Elizabeth
    "LI": {"lat": 40.629487, "lon": -74.251772},  # Linden
    "RH": {"lat": 40.6039, "lon": -74.2723},  # Rahway
    "MU": {"lat": 40.5378, "lon": -74.3562},  # Metuchen
    "ED": {"lat": 40.5177, "lon": -74.4075},  # Edison
    "HL": {"lat": 40.1992, "lon": -74.6877},  # Hamilton
    "NZ": {"lat": 40.6968, "lon": -74.1733},  # North Elizabeth
    # Atlantic City Line
    "AC": {"lat": 39.3644, "lon": -74.4414},  # Atlantic City Rail Terminal
    "AB": {"lat": 39.4273, "lon": -74.4968},  # Absecon
    "EH": {"lat": 39.5221, "lon": -74.6482},  # Egg Harbor City
    "HN": {"lat": 39.6380, "lon": -74.8039},  # Hammonton
    "AO": {"lat": 39.7854, "lon": -74.8887},  # Atco
    "LW": {"lat": 39.8340, "lon": -74.9995},  # Lindenwold (NJT)
    "CY": {"lat": 39.9319, "lon": -74.9722},  # Cherry Hill
    "PN": {"lat": 39.9707, "lon": -75.0565},  # Pennsauken
    "NF": {"lat": 39.9984, "lon": -75.1560},  # North Philadelphia
    "PR": {"lat": 40.3448, "lon": -74.6552},  # Princeton (shuttle station)
    # Raritan Valley Line
    "RA": {"lat": 40.5682, "lon": -74.6290},  # Raritan
    "BK": {"lat": 40.5582, "lon": -74.5397},  # Bound Brook
    "BW": {"lat": 40.5697, "lon": -74.5194},  # Bridgewater
    "SM": {"lat": 40.5681, "lon": -74.6119},  # Somerville
    "DN": {"lat": 40.5892, "lon": -74.4719},  # Dunellen
    "PF": {"lat": 40.6140, "lon": -74.4147},  # Plainfield
    "NE": {"lat": 40.6344, "lon": -74.4182},  # Netherwood
    "FW": {"lat": 40.6415, "lon": -74.3826},  # Fanwood
    "WF": {"lat": 40.6588, "lon": -74.3488},  # Westfield
    "GW": {"lat": 40.6514, "lon": -74.3241},  # Garwood
    "XC": {"lat": 40.6559, "lon": -74.3004},  # Cranford
    "RL": {"lat": 40.6642, "lon": -74.2687},  # Roselle Park
    "US": {"lat": 40.6973, "lon": -74.2636},  # Union
    "HG": {"lat": 40.7133, "lon": -74.8771},  # High Bridge
    "AN": {"lat": 40.6994, "lon": -74.8819},  # Annandale
    "ON": {"lat": 40.6414, "lon": -74.8283},  # Lebanon
    "WH": {"lat": 40.6390, "lon": -74.7632},  # White House
    # Morris & Essex Line
    "ST": {"lat": 40.7099, "lon": -74.3546},  # Summit
    "CM": {"lat": 40.7428, "lon": -74.4319},  # Chatham
    "MA": {"lat": 40.7698, "lon": -74.4151},  # Madison
    "CN": {"lat": 40.7806, "lon": -74.4656},  # Convent Station
    "MR": {"lat": 40.7970, "lon": -74.4724},  # Morristown
    "MX": {"lat": 40.8256, "lon": -74.4615},  # Morris Plains
    "DV": {"lat": 40.8838, "lon": -74.4752},  # Denville
    "DO": {"lat": 40.883417, "lon": -74.555884},  # Dover
    "MT": {"lat": 40.9042, "lon": -74.6254},  # Mount Tabor
    "HQ": {"lat": 41.0046, "lon": -74.7973},  # Hackettstown
    "MB": {"lat": 40.725667, "lon": -74.303694},  # Millburn
    "RT": {"lat": 40.7144, "lon": -74.3215},  # Short Hills
    "ND": {"lat": 40.7418, "lon": -74.1698},  # Newark Broad Street
    "OG": {"lat": 40.7706, "lon": -74.2327},  # Orange
    "HI": {"lat": 40.7681, "lon": -74.2470},  # Highland Avenue
    "MV": {"lat": 40.8122, "lon": -74.2425},  # Mountain View
    "SO": {"lat": 40.7591, "lon": -74.2528},  # South Orange
    "MW": {"lat": 40.7503, "lon": -74.2736},  # Maplewood
    # Gladstone Branch
    "BV": {"lat": 40.7184, "lon": -74.6194},  # Bernardsville
    "FH": {"lat": 40.6834, "lon": -74.6359},  # Far Hills
    "PC": {"lat": 40.7052, "lon": -74.6550},  # Peapack
    "GL": {"lat": 40.7194, "lon": -74.6653},  # Gladstone
    "SG": {"lat": 40.7422, "lon": -74.5438},  # Stirling
    "GO": {"lat": 40.7028, "lon": -74.5622},  # Millington
    "LY": {"lat": 40.6723, "lon": -74.5662},  # Lyons
    "BI": {"lat": 40.6828, "lon": -74.5607},  # Basking Ridge
    "MH": {"lat": 40.7731, "lon": -74.4984},  # Murray Hill
    "NV": {"lat": 40.7355, "lon": -74.4641},  # New Providence
    "BY": {"lat": 40.6976, "lon": -74.5031},  # Berkeley Heights
    "GI": {"lat": 40.7527, "lon": -74.5241},  # Gillette
    # Main/Bergen County Lines
    "RF": {"lat": 40.8267, "lon": -74.1069},  # Rutherford
    "LN": {"lat": 40.8123, "lon": -74.1246},  # Lyndhurst
    "KG": {"lat": 40.8044, "lon": -74.1399},  # Kingsland
    "DL": {"lat": 40.8180, "lon": -74.1370},  # Delawanna
    "PS": {"lat": 40.8570, "lon": -74.1294},  # Passaic
    "IF": {"lat": 40.8584, "lon": -74.1637},  # Clifton
    "RN": {"lat": 40.9166, "lon": -74.1710},  # Paterson
    "HW": {"lat": 40.9494, "lon": -74.1527},  # Hawthorne
    "GK": {"lat": 40.9719, "lon": -74.1338},  # Glen Rock Boro Hall
    "RS": {"lat": 40.9633, "lon": -74.1269},  # Glen Rock Main Line
    "RW": {"lat": 40.9808, "lon": -74.1168},  # Ridgewood
    "UF": {"lat": 40.9956, "lon": -74.1115},  # Ho-Ho-Kus
    "WK": {"lat": 41.0108, "lon": -74.1267},  # Waldwick
    "AZ": {"lat": 41.0312, "lon": -74.1306},  # Allendale
    "RY": {"lat": 41.0571, "lon": -74.1413},  # Ramsey Main St
    "17": {"lat": 41.0615, "lon": -74.1456},  # Ramsey-Route 17
    "MZ": {"lat": 41.0886, "lon": -74.1438},  # Mahwah
    "SF": {"lat": 41.1144, "lon": -74.1496},  # Suffern, NY
    # Montclair-Boonton Line
    "BM": {"lat": 40.8132, "lon": -74.2050},  # Bloomfield
    "GG": {"lat": 40.8061, "lon": -74.2070},  # Glen Ridge
    "BF": {"lat": 40.8926, "lon": -74.1405},  # Broadway Fair Lawn
    "FZ": {"lat": 40.9405, "lon": -74.1320},  # Radburn Fair Lawn
    "HS": {"lat": 40.8283, "lon": -74.2093},  # Montclair Heights
    "MS": {"lat": 40.8263, "lon": -74.2022},  # Mountain Avenue
    "UM": {"lat": 40.8295, "lon": -74.1987},  # Upper Montclair
    "WG": {"lat": 40.8070, "lon": -74.1871},  # Watchung Avenue
    "WT": {"lat": 40.8033, "lon": -74.1738},  # Watsessing Avenue
    "UV": {"lat": 40.8695, "lon": -74.1975},  # Montclair State University
    "FA": {"lat": 40.8757, "lon": -74.2290},  # Little Falls
    "GA": {"lat": 40.8847, "lon": -74.2539},  # Great Notch
    "TB": {"lat": 40.9033, "lon": -74.3959},  # Mount Tabor
    "BN": {"lat": 40.903378, "lon": -74.407733},  # Boonton
    "ML": {"lat": 40.9248, "lon": -74.4095},  # Mountain Lakes
    "LP": {"lat": 40.8822, "lon": -74.3014},  # Lincoln Park
    "TO": {"lat": 40.8723, "lon": -74.2808},  # Towaco
    "HV": {"lat": 40.8648, "lon": -74.5473},  # Mount Arlington
    "HP": {"lat": 40.9298, "lon": -74.6631},  # Lake Hopatcong
    "NT": {"lat": 40.9036, "lon": -74.6969},  # Netcong
    "OL": {"lat": 40.8450, "lon": -74.6885},  # Mount Olive
    "WM": {"lat": 40.8356, "lon": -74.0989},  # Wesmont
    "EO": {"lat": 40.7661, "lon": -74.2052},  # East Orange
    # Pascack Valley Line
    "WR": {"lat": 40.8449, "lon": -74.0883},  # Wood Ridge
    "TE": {"lat": 40.8602, "lon": -74.0639},  # Teterboro
    "EX": {"lat": 40.8836, "lon": -74.0436},  # Essex Street
    "AS": {"lat": 40.8944, "lon": -74.0447},  # Anderson Street
    "RG": {"lat": 40.9264, "lon": -74.0413},  # River Edge
    "NH": {"lat": 40.9119, "lon": -74.0362},  # New Bridge Landing
    "OD": {"lat": 40.9545, "lon": -74.0369},  # Oradell
    "EN": {"lat": 40.9758, "lon": -74.0281},  # Emerson
    "WW": {"lat": 40.9909, "lon": -74.0336},  # Westwood
    "HD": {"lat": 41.0021, "lon": -74.0408},  # Hillsdale
    "WL": {"lat": 41.0230, "lon": -74.0569},  # Woodcliff Lake
    "PV": {"lat": 41.0371, "lon": -74.0743},  # Park Ridge
    "ZM": {"lat": 41.0521, "lon": -74.0372},  # Montvale
    "PQ": {"lat": 41.0595, "lon": -74.0197},  # Pearl River, NY
    "NN": {"lat": 41.0869, "lon": -74.0130},  # Nanuet, NY
    "SV": {"lat": 41.1130, "lon": -74.0436},  # Spring Valley, NY
    # Port Jervis Line
    "XG": {"lat": 41.1568, "lon": -74.1937},  # Sloatsburg, NY
    "TC": {"lat": 41.1970, "lon": -74.1885},  # Tuxedo, NY
    "RM": {"lat": 41.3098, "lon": -74.1526},  # Harriman, NY
    "CW": {"lat": 41.4426, "lon": -74.1351},  # Salisbury Mills-Cornwall, NY
    "CB": {"lat": 41.4446, "lon": -74.2452},  # Campbell Hall, NY
    "OS": {"lat": 41.4783, "lon": -74.5336},  # Otisville, NY
    "PO": {"lat": 41.3753, "lon": -74.6897},  # Port Jervis, NY
    "23": {"lat": 40.8932, "lon": -74.2458},  # Wayne-Route 23
    # Raritan Valley Line Extension
    "JA": {"lat": 40.7328, "lon": -74.0379},  # Jersey Avenue
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
    "BON": {"lat": 42.3662, "lon": -71.0611},  # Boston
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
        data_source: "NJT", "AMTRAK", "PATH", or "PATCO"

    Returns:
        Our internal station code or None if no match found
    """
    if data_source == "AMTRAK":
        # Amtrak uses their standard codes as stop_id
        return map_amtrak_station_code(gtfs_stop_id)

    if data_source == "PATCO":
        # PATCO uses numeric stop_id (1-14)
        return PATCO_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_stop_id)

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
