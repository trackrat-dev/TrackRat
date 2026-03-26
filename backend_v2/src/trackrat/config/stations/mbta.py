"""MBTA (Massachusetts Bay Transportation Authority) Commuter Rail station configuration."""

# MBTA Commuter Rail station names
# Stations shared with Amtrak reuse existing codes: BOS, BBY, PVD, RTE, WOR
# MBTA-only stations use B prefix to avoid conflicts with existing providers
MBTA_STATION_NAMES: dict[str, str] = {
    "BABI": "Abington",
    "BAND": "Andover",
    "BASH": "Ashland",
    "BATT": "Attleboro",
    "BAUB": "Auburndale",
    "BAWB": "Anderson/Woburn",
    "BAYE": "Ayer",
    "BBDG": "Bridgewater",
    "BBEV": "Beverly",
    "BBFM": "Beverly Farms",
    "BBHA": "Blue Hill Avenue",
    "BBLN": "Boston Landing",
    "BBLV": "Bellevue",
    "BBMT": "Belmont",
    "BBNE": "Bourne",
    "BBNR": "Brandeis/Roberts",
    "BBRD": "Bradford",
    "BBRN": "Braintree",
    "BBRO": "Brockton",
    "BBVL": "Ballardvale",
    "BBY": "Back Bay",
    "BBZB": "Buzzards Bay",
    "BCHE": "Chelsea",
    "BCJN": "Canton Junction",
    "BCMP": "Campello",
    "BCNC": "Canton Center",
    "BCOH": "Cohasset",
    "BCON": "Concord",
    "BCST": "Church Street",
    "BDCC": "Dedham Corporate Center",
    "BEND": "Endicott",
    "BETN": "East Taunton",
    "BEWY": "East Weymouth",
    "BFCG": "Four Corners/Geneva",
    "BFHL": "Forest Hills",
    "BFIT": "Fitchburg",
    "BFMT": "Fairmount",
    "BFOX": "Foxboro",
    "BFPK": "Forge Park/495",
    "BFRD": "Fall River Depot",
    "BFRK": "Franklin/Dean College",
    "BFRM": "Framingham",
    "BFTW": "Freetown",
    "BGLO": "Gloucester",
    "BGNW": "Greenwood",
    "BGRB": "Greenbush",
    "BGRF": "Grafton",
    "BHAN": "Hanson",
    "BHAV": "Haverhill",
    "BHLD": "Highland",
    "BHLR": "Holbrook/Randolph",
    "BHLX": "Halifax",
    "BHPK": "Hyde Park",
    "BHRS": "Hersey",
    "BHST": "Hastings",
    "BHWN": "Hamilton/Wenham",
    "BHYN": "Hyannis",
    "BIPS": "Ipswich",
    "BISL": "Islington",
    "BJFK": "JFK/UMass",
    "BKGN": "Kendal Green",
    "BKNG": "Kingston",
    "BLAW": "Lawrence",
    "BLDN": "Lansdowne",
    "BLIN": "Lincoln",
    "BLIT": "Littleton/Route 495",
    "BLKV": "Lakeville",
    "BLNI": "Lynn Interim",
    "BLNN": "Lynn",
    "BLOW": "Lowell",
    "BMAL": "Malden Center",
    "BMAN": "Mansfield",
    "BMCH": "Manchester",
    "BMCP": "Melrose/Cedar Park",
    "BMHG": "Melrose Highlands",
    "BMID": "Middleborough",
    "BMRT": "Morton Street",
    "BMSH": "Mishawum",
    "BMTL": "Montello",
    "BMTS": "Montserrat",
    "BNAN": "Nantasket Junction",
    "BNBD": "New Bedford",
    "BNBL": "North Billerica",
    "BNBP": "Newburyport",
    "BNBV": "North Beverly",
    "BNDC": "Needham Center",
    "BNDH": "Needham Heights",
    "BNFK": "Norfolk",
    "BNJN": "Needham Junction",
    "BNLM": "North Leominster",
    "BNMK": "Newmarket",
    "BNSC": "North Scituate",
    "BNST": "North Station",
    "BNTC": "Natick Center",
    "BNVL": "Newtonville",
    "BNWC": "Norwood Central",
    "BNWD": "Norwood Depot",
    "BNWI": "North Wilmington",
    "BOKG": "Oak Grove",
    "BOS": "South Station",
    "BPCF": "Pawtucket/Central Falls",
    "BPLM": "Plimptonville",
    "BPLY": "Plymouth",
    "BPOR": "Porter",
    "BPRC": "Prides Crossing",
    "BQNC": "Quincy Center",
    "BRDG": "Reading",
    "BRDV": "Readville",
    "BROW": "Rowley",
    "BRPT": "Rockport",
    "BRSV": "Roslindale Village",
    "BRUG": "Ruggles",
    "BRWK": "River Works",
    "BSAC": "South Acton",
    "BSAT": "South Attleboro",
    "BSBO": "Southborough",
    "BSHA": "Sharon",
    "BSHR": "Shirley",
    "BSLH": "Silver Hill",
    "BSLM": "Salem",
    "BSTO": "Stoughton",
    "BSWP": "Swampscott",
    "BSWY": "South Weymouth",
    "BTFG": "TF Green Airport",
    "BTLB": "Talbot Avenue",
    "BUPH": "Uphams Corner",
    "BWAC": "Wachusett",
    "BWAK": "Wakefield",
    "BWAL": "Walpole",
    "BWAV": "Waverley",
    "BWCN": "West Concord",
    "BWDG": "Windsor Gardens",
    "BWDM": "Wedgemere",
    "BWFM": "Wellesley Farms",
    "BWGL": "West Gloucester",
    "BWHI": "West Hingham",
    "BWHL": "Wellesley Hills",
    "BWHT": "Whitman",
    "BWKF": "Wickford Junction",
    "BWLE": "Weymouth Landing/East Braintree",
    "BWLM": "Wilmington",
    "BWMF": "West Medford",
    "BWNA": "West Natick",
    "BWNC": "Winchester Center",
    "BWNT": "West Newton",
    "BWRV": "Wareham Village",
    "BWRX": "West Roxbury",
    "BWSB": "Westborough",
    "BWSQ": "Wellesley Square",
    "BWTH": "Waltham",
    "BWYH": "Wyoming Hill",
    "PVD": "Providence",
    "RTE": "Route 128",
    "WOR": "Worcester",
}


# Maps GTFS stop_id values (used in GTFS-RT TripUpdates) to internal station codes.
# MBTA uses child stop_ids like "NEC-2287" (South Station), "BNT-0000" (North Station).
# Multiple child stop_ids can map to the same parent station (different platforms/tracks).
MBTA_GTFS_STOP_TO_INTERNAL_MAP: dict[str, str] = {
    "BNT-0000": "BNST",  # North Station
    "CM-0493-S": "BWRV",  # Wareham Village
    "CM-0547-S": "BBZB",  # Buzzards Bay
    "CM-0564-S": "BBNE",  # Bourne
    "CM-0790-S": "BHYN",  # Hyannis
    "DB-2205-01": "BFMT",  # Fairmount
    "DB-2205-02": "BFMT",  # Fairmount
    "DB-2222-01": "BBHA",  # Blue Hill Avenue
    "DB-2222-02": "BBHA",  # Blue Hill Avenue
    "DB-2230-01": "BMRT",  # Morton Street
    "DB-2230-02": "BMRT",  # Morton Street
    "DB-2240-01": "BTLB",  # Talbot Avenue
    "DB-2240-02": "BTLB",  # Talbot Avenue
    "DB-2249-01": "BFCG",  # Four Corners/Geneva
    "DB-2249-02": "BFCG",  # Four Corners/Geneva
    "DB-2258-01": "BUPH",  # Uphams Corner
    "DB-2258-02": "BUPH",  # Uphams Corner
    "DB-2265-01": "BNMK",  # Newmarket
    "DB-2265-02": "BNMK",  # Newmarket
    "ER-0042-01": "BCHE",  # Chelsea
    "ER-0042-02": "BCHE",  # Chelsea
    "ER-0099-01": "BRWK",  # River Works
    "ER-0099-02": "BRWK",  # River Works
    "ER-0117-01": "BLNI",  # Lynn Interim
    "ER-0117-02": "BLNI",  # Lynn Interim
    "ER-0128-01": "BSWP",  # Swampscott
    "ER-0128-02": "BSWP",  # Swampscott
    "ER-0168-S": "BSLM",  # Salem
    "ER-0183-01": "BBEV",  # Beverly
    "ER-0183-02": "BBEV",  # Beverly
    "ER-0208-01": "BNBV",  # North Beverly
    "ER-0208-02": "BNBV",  # North Beverly
    "ER-0227-S": "BHWN",  # Hamilton/Wenham
    "ER-0276-S": "BIPS",  # Ipswich
    "ER-0312-S": "BROW",  # Rowley
    "ER-0362-01": "BNBP",  # Newburyport
    "FB-0095-04": "BRDV",  # Readville
    "FB-0095-05": "BRDV",  # Readville
    "FB-0109-01": "BEND",  # Endicott
    "FB-0109-02": "BEND",  # Endicott
    "FB-0118-01": "BDCC",  # Dedham Corporate Center
    "FB-0118-02": "BDCC",  # Dedham Corporate Center
    "FB-0125-01": "BISL",  # Islington
    "FB-0125-02": "BISL",  # Islington
    "FB-0143-01": "BNWD",  # Norwood Depot
    "FB-0143-02": "BNWD",  # Norwood Depot
    "FB-0148-01": "BNWC",  # Norwood Central
    "FB-0148-02": "BNWC",  # Norwood Central
    "FB-0166-S": "BWDG",  # Windsor Gardens
    "FB-0191-S": "BWAL",  # Walpole
    "FB-0230-S": "BNFK",  # Norfolk
    "FB-0275-S": "BFRK",  # Franklin/Dean College
    "FB-0303-S": "BFPK",  # Forge Park/495
    "FR-0034-01": "BPOR",  # Porter
    "FR-0034-02": "BPOR",  # Porter
    "FR-0064-01": "BBMT",  # Belmont
    "FR-0064-02": "BBMT",  # Belmont
    "FR-0074-01": "BWAV",  # Waverley
    "FR-0074-02": "BWAV",  # Waverley
    "FR-0098-01": "BWTH",  # Waltham
    "FR-0098-S": "BWTH",  # Waltham
    "FR-0115-01": "BBNR",  # Brandeis/Roberts
    "FR-0115-02": "BBNR",  # Brandeis/Roberts
    "FR-0132-01": "BKGN",  # Kendal Green
    "FR-0132-02": "BKGN",  # Kendal Green
    "FR-0147-01": "BSLH",  # Silver Hill
    "FR-0147-02": "BSLH",  # Silver Hill
    "FR-0167-01": "BLIN",  # Lincoln
    "FR-0167-02": "BLIN",  # Lincoln
    "FR-0201-01": "BCON",  # Concord
    "FR-0201-02": "BCON",  # Concord
    "FR-0219-01": "BWCN",  # West Concord
    "FR-0219-02": "BWCN",  # West Concord
    "FR-0253-01": "BSAC",  # South Acton
    "FR-0253-02": "BSAC",  # South Acton
    "FR-0301-01": "BLIT",  # Littleton/Route 495
    "FR-0301-02": "BLIT",  # Littleton/Route 495
    "FR-0361-01": "BAYE",  # Ayer
    "FR-0361-02": "BAYE",  # Ayer
    "FR-0394-01": "BSHR",  # Shirley
    "FR-0394-02": "BSHR",  # Shirley
    "FR-0451-01": "BNLM",  # North Leominster
    "FR-0451-02": "BNLM",  # North Leominster
    "FR-0494-CS": "BFIT",  # Fitchburg
    "FR-3338-CS": "BWAC",  # Wachusett
    "FRS-0054-S": "BFTW",  # Freetown
    "FRS-0109-S": "BFRD",  # Fall River Depot
    "FS-0049-S": "BFOX",  # Foxboro
    "GB-0198-01": "BMTS",  # Montserrat
    "GB-0198-02": "BMTS",  # Montserrat
    "GB-0229-01": "BBFM",  # Beverly Farms
    "GB-0229-02": "BBFM",  # Beverly Farms
    "GB-0254-01": "BMCH",  # Manchester
    "GB-0254-02": "BMCH",  # Manchester
    "GB-0296-01": "BWGL",  # West Gloucester
    "GB-0296-02": "BWGL",  # West Gloucester
    "GB-0316-S": "BGLO",  # Gloucester
    "GB-0353-S": "BRPT",  # Rockport
    "GRB-0118-S": "BWLE",  # Weymouth Landing/East Braintree
    "GRB-0146-S": "BEWY",  # East Weymouth
    "GRB-0162-S": "BWHI",  # West Hingham
    "GRB-0183-S": "BNAN",  # Nantasket Junction
    "GRB-0199-S": "BCOH",  # Cohasset
    "GRB-0233-S": "BNSC",  # North Scituate
    "GRB-0276-S": "BGRB",  # Greenbush
    "KB-0351-S": "BKNG",  # Kingston
    "MBS-0350-S": "BMID",  # Middleborough
    "MM-0023-S": "BJFK",  # JFK/UMass
    "MM-0079-S": "BQNC",  # Quincy Center
    "MM-0109-S": "BBRN",  # Braintree
    "MM-0150-S": "BHLR",  # Holbrook/Randolph
    "MM-0186-CS": "BMTL",  # Montello
    "MM-0186-S": "BMTL",  # Montello
    "MM-0200-CS": "BBRO",  # Brockton
    "MM-0200-S": "BBRO",  # Brockton
    "MM-0219-S": "BCMP",  # Campello
    "MM-0277-S": "BBDG",  # Bridgewater
    "MM-0356-S": "BLKV",  # Lakeville
    "NB-0064-S": "BRSV",  # Roslindale Village
    "NB-0072-S": "BBLV",  # Bellevue
    "NB-0076-S": "BHLD",  # Highland
    "NB-0080-S": "BWRX",  # West Roxbury
    "NB-0109-S": "BHRS",  # Hersey
    "NB-0120-S": "BNJN",  # Needham Junction
    "NB-0127-S": "BNDC",  # Needham Center
    "NB-0137-S": "BNDH",  # Needham Heights
    "NBM-0374": "BETN",  # East Taunton
    "NBM-0374-01": "BETN",  # East Taunton
    "NBM-0374-02": "BETN",  # East Taunton
    "NBM-0523-S": "BCST",  # Church Street
    "NBM-0546-S": "BNBD",  # New Bedford
    "NEC-1659-03": "BWKF",  # Wickford Junction
    "NEC-1768-03": "BTFG",  # TF Green Airport
    "NEC-1851-03": "PVD",  # Providence
    "NEC-1891-01": "BPCF",  # Pawtucket/Central Falls
    "NEC-1891-02": "BPCF",  # Pawtucket/Central Falls
    "NEC-1919-01": "BSAT",  # South Attleboro
    "NEC-1919-02": "BSAT",  # South Attleboro
    "NEC-1969-03": "BATT",  # Attleboro
    "NEC-1969-04": "BATT",  # Attleboro
    "NEC-2040-01": "BMAN",  # Mansfield
    "NEC-2040-02": "BMAN",  # Mansfield
    "NEC-2108-01": "BSHA",  # Sharon
    "NEC-2108-02": "BSHA",  # Sharon
    "NEC-2139": "BCJN",  # Canton Junction
    "NEC-2139-01": "BCJN",  # Canton Junction
    "NEC-2139-02": "BCJN",  # Canton Junction
    "NEC-2173-01": "RTE",  # Route 128
    "NEC-2173-02": "RTE",  # Route 128
    "NEC-2192-02": "BRDV",  # Readville
    "NEC-2192-03": "BRDV",  # Readville
    "NEC-2203-02": "BHPK",  # Hyde Park
    "NEC-2203-03": "BHPK",  # Hyde Park
    "NEC-2237-03": "BFHL",  # Forest Hills
    "NEC-2237-05": "BFHL",  # Forest Hills
    "NEC-2265": "BRUG",  # Ruggles
    "NEC-2265-01": "BRUG",  # Ruggles
    "NEC-2265-02": "BRUG",  # Ruggles
    "NEC-2265-03": "BRUG",  # Ruggles
    "NEC-2276": "BBY",  # Back Bay
    "NEC-2276-01": "BBY",  # Back Bay
    "NEC-2276-02": "BBY",  # Back Bay
    "NEC-2276-03": "BBY",  # Back Bay
    "NEC-2287": "BOS",  # South Station
    "NHRML-0055-01": "BWMF",  # West Medford
    "NHRML-0055-02": "BWMF",  # West Medford
    "NHRML-0073-01": "BWDM",  # Wedgemere
    "NHRML-0073-02": "BWDM",  # Wedgemere
    "NHRML-0078-01": "BWNC",  # Winchester Center
    "NHRML-0078-02": "BWNC",  # Winchester Center
    "NHRML-0127-01": "BAWB",  # Anderson/Woburn
    "NHRML-0127-02": "BAWB",  # Anderson/Woburn
    "NHRML-0152-01": "BWLM",  # Wilmington
    "NHRML-0152-02": "BWLM",  # Wilmington
    "NHRML-0218-01": "BNBL",  # North Billerica
    "NHRML-0218-02": "BNBL",  # North Billerica
    "NHRML-0254-04": "BLOW",  # Lowell
    "PB-0158-S": "BSWY",  # South Weymouth
    "PB-0194-S": "BABI",  # Abington
    "PB-0212-S": "BWHT",  # Whitman
    "PB-0245-S": "BHAN",  # Hanson
    "PB-0281-S": "BHLX",  # Halifax
    "SB-0150-04": "BCJN",  # Canton Junction
    "SB-0150-06": "BCJN",  # Canton Junction
    "SB-0156-S": "BCNC",  # Canton Center
    "SB-0189-S": "BSTO",  # Stoughton
    "WML-0012-05": "BBY",  # Back Bay
    "WML-0012-07": "BBY",  # Back Bay
    "WML-0025-05": "BLDN",  # Lansdowne
    "WML-0025-07": "BLDN",  # Lansdowne
    "WML-0035-01": "BBLN",  # Boston Landing
    "WML-0035-02": "BBLN",  # Boston Landing
    "WML-0081-02": "BNVL",  # Newtonville
    "WML-0091-02": "BWNT",  # West Newton
    "WML-0102-02": "BAUB",  # Auburndale
    "WML-0125-01": "BWFM",  # Wellesley Farms
    "WML-0125-02": "BWFM",  # Wellesley Farms
    "WML-0135-01": "BWHL",  # Wellesley Hills
    "WML-0135-02": "BWHL",  # Wellesley Hills
    "WML-0147-01": "BWSQ",  # Wellesley Square
    "WML-0147-02": "BWSQ",  # Wellesley Square
    "WML-0177-01": "BNTC",  # Natick Center
    "WML-0177-02": "BNTC",  # Natick Center
    "WML-0199-01": "BWNA",  # West Natick
    "WML-0199-02": "BWNA",  # West Natick
    "WML-0214-01": "BFRM",  # Framingham
    "WML-0214-02": "BFRM",  # Framingham
    "WML-0252-01": "BASH",  # Ashland
    "WML-0252-02": "BASH",  # Ashland
    "WML-0274-01": "BSBO",  # Southborough
    "WML-0274-02": "BSBO",  # Southborough
    "WML-0340-01": "BWSB",  # Westborough
    "WML-0340-02": "BWSB",  # Westborough
    "WML-0364-01": "BGRF",  # Grafton
    "WML-0364-02": "BGRF",  # Grafton
    "WML-0442-CS": "WOR",  # Worcester
    "WR-0045-S": "BMAL",  # Malden Center
    "WR-0053-S": "BOKG",  # Oak Grove
    "WR-0062-01": "BWYH",  # Wyoming Hill
    "WR-0062-02": "BWYH",  # Wyoming Hill
    "WR-0067-01": "BMCP",  # Melrose/Cedar Park
    "WR-0067-02": "BMCP",  # Melrose/Cedar Park
    "WR-0075-01": "BMHG",  # Melrose Highlands
    "WR-0075-02": "BMHG",  # Melrose Highlands
    "WR-0085-01": "BGNW",  # Greenwood
    "WR-0085-02": "BGNW",  # Greenwood
    "WR-0099-01": "BWAK",  # Wakefield
    "WR-0099-02": "BWAK",  # Wakefield
    "WR-0120-S": "BRDG",  # Reading
    "WR-0163-S": "BNWI",  # North Wilmington
    "WR-0205-02": "BBVL",  # Ballardvale
    "WR-0228-02": "BAND",  # Andover
    "WR-0264-02": "BLAW",  # Lawrence
    "WR-0325-01": "BBRD",  # Bradford
    "WR-0325-02": "BBRD",  # Bradford
    "WR-0329-01": "BHAV",  # Haverhill
    "WR-0329-02": "BHAV",  # Haverhill
}


INTERNAL_TO_MBTA_GTFS_STOP_MAP: dict[str, str] = {
    v: k for k, v in MBTA_GTFS_STOP_TO_INTERNAL_MAP.items()
}


# MBTA Commuter Rail routes
# Format: GTFS route_id -> (line_code, route_name, color_hex)
MBTA_ROUTES: dict[str, tuple[str, str, str]] = {
    "CR-Fairmount": ("MBTA-FA", "Fairmount Line", "#80276C"),
    "CR-Fitchburg": ("MBTA-FI", "Fitchburg Line", "#80276C"),
    "CR-Foxboro": ("MBTA-FX", "Foxboro Event Service", "#80276C"),
    "CR-Franklin": ("MBTA-FR", "Franklin/Foxboro Line", "#80276C"),
    "CR-Greenbush": ("MBTA-GR", "Greenbush Line", "#80276C"),
    "CR-Haverhill": ("MBTA-HA", "Haverhill Line", "#80276C"),
    "CR-Kingston": ("MBTA-KN", "Kingston Line", "#80276C"),
    "CR-Lowell": ("MBTA-LO", "Lowell Line", "#80276C"),
    "CR-Middleborough": ("MBTA-MI", "Middleborough/Lakeville Line", "#80276C"),
    "CR-Needham": ("MBTA-NE", "Needham Line", "#80276C"),
    "CR-NewBedford": ("MBTA-NB", "Fall River/New Bedford Line", "#80276C"),
    "CR-Newburyport": ("MBTA-NP", "Newburyport/Rockport Line", "#80276C"),
    "CR-Providence": ("MBTA-PV", "Providence/Stoughton Line", "#80276C"),
    "CR-Worcester": ("MBTA-WR", "Framingham/Worcester Line", "#80276C"),
    "CapeFlyer": ("MBTA-CF", "CapeFLYER", "#006595"),
}


# MBTA GTFS-RT feed URL (protobuf, no auth required for CDN)
MBTA_GTFS_RT_FEED_URL = "https://cdn.mbta.com/realtime/TripUpdates.pb"

# MBTA V3 API for track assignments (requires API key)
MBTA_PREDICTIONS_API_URL = "https://api-v3.mbta.com/predictions"

# MBTA service alerts feed
MBTA_ALERTS_FEED_URL = "https://cdn.mbta.com/realtime/Alerts.pb"


# Major hub stations for train discovery
MBTA_DISCOVERY_STATIONS: list[str] = ["BOS", "BNST", "BBY", "BBRN", "PVD"]


# Station coordinates for MBTA-only stations
# Shared Amtrak stations (BOS, BBY, PVD, RTE, WOR) already have coordinates in common.py
MBTA_STATION_COORDINATES: dict[str, dict[str, float]] = {
    "BABI": {"lat": 42.107156, "lon": -70.934405},
    "BAND": {"lat": 42.658336, "lon": -71.144502},
    "BASH": {"lat": 42.26149, "lon": -71.482161},
    "BATT": {"lat": 41.940739, "lon": -71.285094},
    "BAUB": {"lat": 42.345833, "lon": -71.250373},
    "BAWB": {"lat": 42.516987, "lon": -71.144475},
    "BAYE": {"lat": 42.559074, "lon": -71.588476},
    "BBDG": {"lat": 41.984916, "lon": -70.96537},
    "BBEV": {"lat": 42.547276, "lon": -70.885432},
    "BBFM": {"lat": 42.561651, "lon": -70.811405},
    "BBHA": {"lat": 42.271466, "lon": -71.095782},
    "BBLN": {"lat": 42.357293, "lon": -71.139883},
    "BBLV": {"lat": 42.286588, "lon": -71.145557},
    "BBMT": {"lat": 42.395896, "lon": -71.17619},
    "BBNE": {"lat": 41.7464973, "lon": -70.5887722},
    "BBNR": {"lat": 42.361898, "lon": -71.260065},
    "BBRD": {"lat": 42.766912, "lon": -71.088411},
    "BBRN": {"lat": 42.2078543, "lon": -71.0011385},
    "BBRO": {"lat": 42.084659, "lon": -71.016534},
    "BBVL": {"lat": 42.627356, "lon": -71.159962},
    "BBZB": {"lat": 41.744805, "lon": -70.616226},
    "BCHE": {"lat": 42.397024, "lon": -71.041314},
    "BCJN": {"lat": 42.163204, "lon": -71.15376},
    "BCMP": {"lat": 42.060951, "lon": -71.011004},
    "BCNC": {"lat": 42.157095, "lon": -71.14628},
    "BCOH": {"lat": 42.24421, "lon": -70.837529},
    "BCON": {"lat": 42.456565, "lon": -71.357677},
    "BCST": {"lat": 41.674308, "lon": -70.939322},
    "BDCC": {"lat": 42.227079, "lon": -71.174254},
    "BEND": {"lat": 42.233249, "lon": -71.158647},
    "BETN": {"lat": 41.868197, "lon": -71.061694},
    "BEWY": {"lat": 42.2191, "lon": -70.9214},
    "BFCG": {"lat": 42.305037, "lon": -71.076833},
    "BFHL": {"lat": 42.300713, "lon": -71.113943},
    "BFIT": {"lat": 42.58072, "lon": -71.792611},
    "BFMT": {"lat": 42.253638, "lon": -71.11927},
    "BFOX": {"lat": 42.0951, "lon": -71.26151},
    "BFPK": {"lat": 42.089941, "lon": -71.43902},
    "BFRD": {"lat": 41.713982, "lon": -71.154182},
    "BFRK": {"lat": 42.083238, "lon": -71.396102},
    "BFRM": {"lat": 42.276108, "lon": -71.420055},
    "BFTW": {"lat": 41.773672, "lon": -71.090733},
    "BGLO": {"lat": 42.616799, "lon": -70.668345},
    "BGNW": {"lat": 42.483005, "lon": -71.067247},
    "BGRB": {"lat": 42.178776, "lon": -70.746641},
    "BGRF": {"lat": 42.2466, "lon": -71.685325},
    "BHAN": {"lat": 42.043967, "lon": -70.882438},
    "BHAV": {"lat": 42.773474, "lon": -71.086237},
    "BHLD": {"lat": 42.284969, "lon": -71.153937},
    "BHLR": {"lat": 42.156343, "lon": -71.027371},
    "BHLX": {"lat": 42.014739, "lon": -70.824263},
    "BHPK": {"lat": 42.25503, "lon": -71.125526},
    "BHRS": {"lat": 42.275648, "lon": -71.215528},
    "BHST": {"lat": 42.385755, "lon": -71.289203},
    "BHWN": {"lat": 42.609212, "lon": -70.874801},
    "BHYN": {"lat": 41.660225, "lon": -70.276583},
    "BIPS": {"lat": 42.676921, "lon": -70.840589},
    "BISL": {"lat": 42.22105, "lon": -71.183961},
    "BJFK": {"lat": 42.320685, "lon": -71.052391},
    "BKGN": {"lat": 42.37897, "lon": -71.282411},
    "BKNG": {"lat": 41.97762, "lon": -70.721709},
    "BLAW": {"lat": 42.701806, "lon": -71.15198},
    "BLDN": {"lat": 42.347581, "lon": -71.099974},
    "BLIN": {"lat": 42.413641, "lon": -71.325512},
    "BLIT": {"lat": 42.519236, "lon": -71.502643},
    "BLKV": {"lat": 41.87821, "lon": -70.918444},
    "BLNI": {"lat": 42.4652901, "lon": -70.9404344},
    "BLNN": {"lat": 42.462953, "lon": -70.945421},
    "BLOW": {"lat": 42.63535, "lon": -71.314543},
    "BMAL": {"lat": 42.426632, "lon": -71.07411},
    "BMAN": {"lat": 42.032787, "lon": -71.219917},
    "BMCH": {"lat": 42.573687, "lon": -70.77009},
    "BMCP": {"lat": 42.458768, "lon": -71.069789},
    "BMHG": {"lat": 42.469464, "lon": -71.068297},
    "BMID": {"lat": 41.887, "lon": -70.923209},
    "BMRT": {"lat": 42.280994, "lon": -71.085475},
    "BMSH": {"lat": 42.504402, "lon": -71.137618},
    "BMTL": {"lat": 42.106555, "lon": -71.022001},
    "BMTS": {"lat": 42.562171, "lon": -70.869254},
    "BNAN": {"lat": 42.244959, "lon": -70.869205},
    "BNBD": {"lat": 41.643703, "lon": -70.9252},
    "BNBL": {"lat": 42.593248, "lon": -71.280995},
    "BNBP": {"lat": 42.797837, "lon": -70.87797},
    "BNBV": {"lat": 42.583779, "lon": -70.883851},
    "BNDC": {"lat": 42.280775, "lon": -71.237686},
    "BNDH": {"lat": 42.293444, "lon": -71.236027},
    "BNFK": {"lat": 42.120694, "lon": -71.325217},
    "BNJN": {"lat": 42.273187, "lon": -71.235559},
    "BNLM": {"lat": 42.539017, "lon": -71.739186},
    "BNMK": {"lat": 42.327415, "lon": -71.065674},
    "BNSC": {"lat": 42.219528, "lon": -70.788602},
    "BNST": {"lat": 42.365577, "lon": -71.06129},
    "BNTC": {"lat": 42.285719, "lon": -71.347133},
    "BNVL": {"lat": 42.351702, "lon": -71.205408},
    "BNWC": {"lat": 42.188775, "lon": -71.199665},
    "BNWD": {"lat": 42.196857, "lon": -71.196688},
    "BNWI": {"lat": 42.571073, "lon": -71.160939},
    "BOKG": {"lat": 42.43668, "lon": -71.071097},
    "BPCF": {"lat": 41.878762, "lon": -71.392},
    "BPLM": {"lat": 42.159123, "lon": -71.236125},
    "BPLY": {"lat": 41.981278, "lon": -70.690421},
    "BPOR": {"lat": 42.3884, "lon": -71.119149},
    "BPRC": {"lat": 42.559446, "lon": -70.825541},
    "BQNC": {"lat": 42.251809, "lon": -71.005409},
    "BRDG": {"lat": 42.52221, "lon": -71.108294},
    "BRDV": {"lat": 42.238405, "lon": -71.133246},
    "BROW": {"lat": 42.726845, "lon": -70.859034},
    "BRPT": {"lat": 42.655491, "lon": -70.627055},
    "BRSV": {"lat": 42.287442, "lon": -71.130283},
    "BRUG": {"lat": 42.336377, "lon": -71.088961},
    "BRWK": {"lat": 42.449927, "lon": -70.969848},
    "BSAC": {"lat": 42.460375, "lon": -71.457744},
    "BSAT": {"lat": 41.897943, "lon": -71.354621},
    "BSBO": {"lat": 42.267024, "lon": -71.524371},
    "BSHA": {"lat": 42.124553, "lon": -71.184468},
    "BSHR": {"lat": 42.545089, "lon": -71.648004},
    "BSLH": {"lat": 42.395625, "lon": -71.302357},
    "BSLM": {"lat": 42.524792, "lon": -70.895876},
    "BSTO": {"lat": 42.124084, "lon": -71.103627},
    "BSWP": {"lat": 42.473743, "lon": -70.922537},
    "BSWY": {"lat": 42.155025, "lon": -70.953302},
    "BTFG": {"lat": 41.726599, "lon": -71.442453},
    "BTLB": {"lat": 42.292246, "lon": -71.07814},
    "BUPH": {"lat": 42.319125, "lon": -71.068627},
    "BWAC": {"lat": 42.553477, "lon": -71.848488},
    "BWAK": {"lat": 42.502126, "lon": -71.075566},
    "BWAL": {"lat": 42.145477, "lon": -71.25779},
    "BWAV": {"lat": 42.3876, "lon": -71.190744},
    "BWCN": {"lat": 42.457043, "lon": -71.392892},
    "BWDG": {"lat": 42.172127, "lon": -71.219366},
    "BWDM": {"lat": 42.444948, "lon": -71.140169},
    "BWFM": {"lat": 42.323608, "lon": -71.272288},
    "BWGL": {"lat": 42.611933, "lon": -70.705417},
    "BWHI": {"lat": 42.235838, "lon": -70.902708},
    "BWHL": {"lat": 42.31037, "lon": -71.277044},
    "BWHT": {"lat": 42.082749, "lon": -70.923411},
    "BWKF": {"lat": 41.581289, "lon": -71.491147},
    "BWLE": {"lat": 42.221503, "lon": -70.968152},
    "BWLM": {"lat": 42.546624, "lon": -71.174334},
    "BWMF": {"lat": 42.421776, "lon": -71.133342},
    "BWNA": {"lat": 42.283064, "lon": -71.391797},
    "BWNC": {"lat": 42.451088, "lon": -71.13783},
    "BWNT": {"lat": 42.347878, "lon": -71.230528},
    "BWRV": {"lat": 41.7604, "lon": -70.7171},
    "BWRX": {"lat": 42.281358, "lon": -71.160065},
    "BWSB": {"lat": 42.269644, "lon": -71.647076},
    "BWSQ": {"lat": 42.297526, "lon": -71.294173},
    "BWTH": {"lat": 42.374296, "lon": -71.235615},
    "BWYH": {"lat": 42.451731, "lon": -71.069379},
}


def get_mbta_route_info(gtfs_route_id: str) -> tuple[str, str, str] | None:
    """Get MBTA route info (line_code, name, color) from GTFS route_id."""
    return MBTA_ROUTES.get(gtfs_route_id)


def map_mbta_gtfs_stop(gtfs_stop_id: str) -> str | None:
    """Map an MBTA GTFS stop_id to an internal station code."""
    return MBTA_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_stop_id)
