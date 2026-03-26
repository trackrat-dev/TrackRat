"""Common station utilities and shared data.

Contains the unified STATION_NAMES dict (built from all per-system modules),
STATION_EQUIVALENTS, STATION_COORDINATES, and shared lookup functions.
"""

from trackrat.config.stations.amtrak import (
    AMTRAK_STATION_NAMES,
    map_amtrak_station_code,
)
from trackrat.config.stations.lirr import (
    LIRR_GTFS_STOP_TO_INTERNAL_MAP,
    LIRR_STATION_NAMES,
)
from trackrat.config.stations.mbta import (
    MBTA_GTFS_STOP_TO_INTERNAL_MAP,
    MBTA_STATION_COORDINATES,
    MBTA_STATION_NAMES,
)
from trackrat.config.stations.mnr import (
    MNR_GTFS_STOP_TO_INTERNAL_MAP,
    MNR_STATION_NAMES,
)
from trackrat.config.stations.njt import (
    NJT_GTFS_STOP_TO_INTERNAL_MAP,
    NJT_STATION_NAMES,
)
from trackrat.config.stations.patco import (
    PATCO_GTFS_STOP_TO_INTERNAL_MAP,
    PATCO_STATION_NAMES,
)
from trackrat.config.stations.path import (
    PATH_GTFS_NAME_TO_INTERNAL_MAP,
    PATH_STATION_NAMES,
    PATH_TRANSITER_TO_INTERNAL_MAP,
)
from trackrat.config.stations.subway import (
    SUBWAY_STATION_COMPLEXES,
    SUBWAY_STATION_COORDINATES,
    SUBWAY_STATION_NAMES,
    map_subway_gtfs_stop,
)

# Unified station code to name mapping (all systems)
STATION_NAMES: dict[str, str] = {
    **NJT_STATION_NAMES,
    **AMTRAK_STATION_NAMES,
    **PATCO_STATION_NAMES,
    **PATH_STATION_NAMES,
    **LIRR_STATION_NAMES,
    **MNR_STATION_NAMES,
    **SUBWAY_STATION_NAMES,
    **MBTA_STATION_NAMES,
}


def get_station_name(code: str) -> str:
    """Get the full station name for a given code.

    Args:
        code: Two-character station code

    Returns:
        Full station name, or the code if not found
    """
    return STATION_NAMES.get(code, code)


# Station code equivalence groups for physically identical stations.
# Each set contains all codes for the same physical station across systems.
# Cross-system: Amtrak / Metro-North shared stations.
# Subway: platform complexes from SUBWAY_STATION_COMPLEXES.
STATION_EQUIVALENCE_GROUPS: list[set[str]] = [
    {"NRO", "MNRC"},  # New Rochelle
    {"YNY", "MYON"},  # Yonkers
    {"CRT", "MCRH"},  # Croton-Harmon
    {"POU", "MPOK"},  # Poughkeepsie
    {"STM", "MSTM"},  # Stamford
    {"BRP", "MBGP"},  # Bridgeport
    {"NHV", "MNHV"},  # New Haven
    {"STS", "MNSS"},  # New Haven-State St
    {"NP", "PNK"},  # Newark Penn Station / Newark PATH
    *SUBWAY_STATION_COMPLEXES,
    # PATH ↔ Subway cross-system equivalences (must be after SUBWAY_STATION_COMPLEXES
    # so the larger group overwrites the subway-only group for shared codes)
    {"PWC", "S138", "S228", "SA36", "SE01", "SR25"},  # World Trade Center / Oculus
]

# Derived lookup: code -> full equivalence group
STATION_EQUIVALENTS: dict[str, set[str]] = {}
for _group in STATION_EQUIVALENCE_GROUPS:
    for _code in _group:
        STATION_EQUIVALENTS[_code] = _group


def expand_station_codes(code: str) -> list[str]:
    """Return [code] plus any equivalent codes for the same physical station.

    Some physical stations are served by multiple transit systems that use
    different internal codes (e.g., Amtrak's NRO vs Metro-North's MNRC for
    New Rochelle). This function returns all codes for the same physical station
    so queries can match trains from any system.
    """
    group = STATION_EQUIVALENTS.get(code)
    if group:
        return [code] + sorted(group - {code})
    return [code]


def canonical_station_code(code: str) -> str:
    """Return a canonical code for station equivalence groups.

    Used for cache keys so that equivalent codes (e.g., NRO and MNRC)
    produce the same cache key.
    """
    group = STATION_EQUIVALENTS.get(code)
    if group:
        return min(group)
    return code


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
    "WA": {"lat": 40.817165, "lon": -74.209557},  # Walnut Street
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

# Merge subway coordinates (stored as (lat, lon) tuples in subway module)
for _code, (_lat, _lon) in SUBWAY_STATION_COORDINATES.items():
    STATION_COORDINATES[_code] = {"lat": _lat, "lon": _lon}

# Merge MBTA coordinates (stored as {"lat": float, "lon": float} dicts)
STATION_COORDINATES.update(MBTA_STATION_COORDINATES)


def get_station_coordinates(code: str) -> dict[str, float] | None:
    """Get station coordinates for mapping.

    Args:
        code: Two-character station code

    Returns:
        Dict with lat/lon or None if not found
    """
    return STATION_COORDINATES.get(code)


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
        data_source: "NJT", "AMTRAK", "PATH", "PATCO", "LIRR", "MNR", "SUBWAY", or "MBTA"

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

    if data_source == "MBTA":
        # MBTA uses child stop_ids like "NEC-2287", "BNT-0000"
        return MBTA_GTFS_STOP_TO_INTERNAL_MAP.get(gtfs_stop_id)

    if data_source == "SUBWAY":
        # NYC Subway stop IDs have N/S directional suffix
        return map_subway_gtfs_stop(gtfs_stop_id)

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
