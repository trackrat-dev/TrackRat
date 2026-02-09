"""
Canonical route definitions for segment normalization.

Each route defines the ordered sequence of stations that trains traverse.
This enables:
1. Expanding skip-stop journeys (A→C becomes A→B, B→C)
2. Validating segment directions
3. Consistent grouping across data sources

Mirrors iOS RouteTopology.swift for consistency.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    """A transit route with ordered station sequence."""

    id: str  # Unique identifier (e.g., "njt-nec")
    name: str  # Display name
    data_source: str  # "NJT", "PATH", "PATCO", "AMTRAK", "LIRR", "MNR"
    line_codes: frozenset[str]  # Valid line_code values for this route
    stations: tuple[str, ...]  # Ordered station codes

    def __post_init__(self) -> None:
        # Cache station set for O(1) membership tests
        # Use object.__setattr__ since dataclass is frozen
        object.__setattr__(self, "_station_set", frozenset(self.stations))

    _station_set: frozenset[str] = frozenset()  # Populated in __post_init__

    def contains_segment(self, from_station: str, to_station: str) -> bool:
        """Check if both stations exist on this route. O(1) lookup."""
        return from_station in self._station_set and to_station in self._station_set

    def get_intermediate_stations(
        self, from_station: str, to_station: str
    ) -> list[str] | None:
        """
        Get ordered stations between from and to (inclusive).

        Note: Returns stations in the direction specified (from -> to).
        If from_station comes after to_station on the route, returns
        the reversed sequence.

        Returns None if either station is not on this route.
        """
        try:
            from_idx = self.stations.index(from_station)
            to_idx = self.stations.index(to_station)
            if from_idx < to_idx:
                return list(self.stations[from_idx : to_idx + 1])
            else:
                # Reverse direction
                return list(reversed(self.stations[to_idx : from_idx + 1]))
        except ValueError:
            return None

    def expand_to_canonical_segments(
        self, from_station: str, to_station: str
    ) -> list[tuple[str, str]] | None:
        """
        Expand a segment into canonical consecutive pairs.
        A→C becomes [(A, B), (B, C)] if B is between them.
        Returns None if segment not on this route.
        """
        stations = self.get_intermediate_stations(from_station, to_station)
        if stations is None or len(stations) < 2:
            return None
        return [(stations[i], stations[i + 1]) for i in range(len(stations) - 1)]


# =============================================================================
# NJT ROUTES
# =============================================================================

NJT_NORTHEAST_CORRIDOR = Route(
    id="njt-nec",
    name="Northeast Corridor",
    data_source="NJT",
    line_codes=frozenset({"NE"}),
    stations=(
        "NY",
        "SE",
        "NP",
        "NA",
        "NZ",
        "EZ",
        "LI",
        "RH",
        "MP",
        "MU",
        "ED",
        "NB",
        "JA",
        "PJ",
        "HL",
        "TR",
    ),
)

NJT_NORTH_JERSEY_COAST = Route(
    id="njt-njcl",
    name="North Jersey Coast Line",
    data_source="NJT",
    line_codes=frozenset({"NC"}),
    stations=(
        "NY",
        "SE",
        "NP",
        "NA",
        "NZ",
        "EZ",
        "LI",
        "RH",
        "AV",
        "WB",
        "PE",
        "CH",
        "AM",
        "HZ",
        "MI",
        "RB",
        "LS",
        "MK",
        "LB",
        "EL",
        "AH",
        "AP",
        "BB",
        "BS",
        "LA",
        "SQ",
        "PP",
        "BH",
    ),
)

NJT_MORRIS_ESSEX_MORRISTOWN = Route(
    id="njt-me-morristown",
    name="Morris & Essex (Morristown)",
    data_source="NJT",
    line_codes=frozenset({"ME"}),  # Morris & Essex uses "ME"
    stations=(
        "HB",
        "SE",
        "NP",
        "ND",
        "BU",
        "EO",
        "OG",
        "HI",
        "MT",
        "SO",
        "MW",
        "MB",
        "RT",
        "ST",
        "CM",
        "MA",
        "CN",
        "MR",
        "MX",
        "TB",
        "DV",
        "DO",
        "HV",
        "HP",
        "NT",
        "OL",
        "HQ",
    ),
)

NJT_GLADSTONE = Route(
    id="njt-gladstone",
    name="Gladstone Branch",
    data_source="NJT",
    line_codes=frozenset({"GL"}),
    stations=(
        "ST",
        "NV",
        "MH",
        "BY",
        "GI",
        "SG",
        "GO",
        "LY",
        "BI",
        "BV",
        "FH",
        "PC",
        "GL",
    ),
)

NJT_RARITAN_VALLEY = Route(
    id="njt-rvl",
    name="Raritan Valley Line",
    data_source="NJT",
    line_codes=frozenset({"RV"}),
    stations=(
        "NP",
        "EZ",
        "US",
        "RL",
        "XC",
        "GW",
        "WF",
        "FW",
        "NE",
        "PF",
        "DN",
        "BK",
        "BW",
        "SM",
        "RA",
        "OR",
        "WH",
        "ON",
        "AN",
        "HG",
    ),
)

NJT_MONTCLAIR_BOONTON = Route(
    id="njt-mobo",
    name="Montclair-Boonton Line",
    data_source="NJT",
    line_codes=frozenset({"MO"}),  # Montclair-Boonton uses "MO"
    stations=(
        "HB",
        "SE",
        "ND",
        "WT",
        "BM",
        "GG",
        "MC",
        "WA",
        "WG",
        "UM",
        "MS",
        "HS",
        "UV",
        "FA",
        "23",
        "MV",
        "LP",
        "TO",
        "BN",
        "ML",
        "DV",
    ),
)

NJT_MAIN_LINE = Route(
    id="njt-main",
    name="Main Line",
    data_source="NJT",
    line_codes=frozenset({"MA"}),
    stations=(
        "HB",
        "SE",
        "KG",
        "LN",
        "DL",
        "PS",
        "IF",
        "RN",
        "HW",
        "RS",
        "RW",
        "UF",
        "WK",
        "AZ",
        "RY",
        "17",
        "MZ",
        "SF",
    ),
)

NJT_BERGEN_COUNTY = Route(
    id="njt-bergen",
    name="Bergen County Line",
    data_source="NJT",
    line_codes=frozenset({"BE"}),
    stations=(
        "HB",
        "SE",
        "RF",
        "WM",
        "GD",
        "PL",
        "BF",
        "FZ",
        "GK",
        "RW",
        "UF",
        "WK",
        "AZ",
        "RY",
        "17",
        "MZ",
        "SF",
    ),
)

NJT_PORT_JERVIS = Route(
    id="njt-port-jervis",
    name="Port Jervis Line",
    data_source="NJT",
    line_codes=frozenset({"PJ"}),
    stations=("SF", "XG", "TC", "RM", "CW", "CB", "OS", "PO"),
)

NJT_PASCACK_VALLEY = Route(
    id="njt-pascack",
    name="Pascack Valley Line",
    data_source="NJT",
    line_codes=frozenset({"PV"}),
    stations=(
        "HB",
        "SE",
        "WR",
        "TE",
        "EX",
        "AS",
        "NH",
        "RG",
        "OD",
        "EN",
        "WW",
        "HD",
        "WL",
        "PV",
        "ZM",
        "PQ",
        "NN",
        "SV",
    ),
)

NJT_ATLANTIC_CITY = Route(
    id="njt-atlc",
    name="Atlantic City Line",
    data_source="NJT",
    line_codes=frozenset({"AC"}),
    stations=("PH", "TR"),  # Limited - add more if coordinates available
)

NJT_PRINCETON_BRANCH = Route(
    id="njt-princeton",
    name="Princeton Branch",
    data_source="NJT",
    line_codes=frozenset({"PR"}),
    stations=("PJ", "PR"),
)

# =============================================================================
# PATH ROUTES
# =============================================================================

PATH_HOB_33 = Route(
    id="path-hob-33",
    name="Hoboken - 33rd Street",
    data_source="PATH",
    line_codes=frozenset({"HOB-33", "859"}),
    stations=("PHO", "PCH", "P9S", "P14", "P23", "P33"),
)

PATH_HOB_WTC = Route(
    id="path-hob-wtc",
    name="Hoboken - WTC",
    data_source="PATH",
    line_codes=frozenset({"HOB-WTC", "860"}),
    stations=("PHO", "PNP", "PEX", "PWC"),
)

PATH_JSQ_33 = Route(
    id="path-jsq-33",
    name="Journal Square - 33rd Street",
    data_source="PATH",
    line_codes=frozenset({"JSQ-33", "861"}),
    stations=("PJS", "PGR", "PNP", "PCH", "P9S", "P14", "P23", "P33"),
)

PATH_NWK_WTC = Route(
    id="path-nwk-wtc",
    name="Newark - WTC",
    data_source="PATH",
    line_codes=frozenset({"NWK-WTC", "862"}),
    stations=("PNK", "PHR", "PJS", "PGR", "PEX", "PWC"),
)

PATH_JSQ_33_HOB = Route(
    id="path-jsq-33-hob",
    name="JSQ - 33rd via Hoboken",
    data_source="PATH",
    line_codes=frozenset({"JSQ-33H", "1024"}),
    stations=("PJS", "PGR", "PNP", "PHO", "PCH", "P9S", "P14", "P23", "P33"),
)

PATH_NWK_HAR = Route(
    id="path-nwk-har",
    name="Newark - Harrison",
    data_source="PATH",
    line_codes=frozenset({"NWK-HAR", "74320"}),
    stations=("PNK", "PHR"),
)

# =============================================================================
# PATCO
# =============================================================================

PATCO_SPEEDLINE = Route(
    id="patco-speedline",
    name="PATCO Speedline",
    data_source="PATCO",
    line_codes=frozenset({"PATCO"}),
    stations=(
        "LND",
        "ASD",
        "WCT",
        "HDF",
        "WMT",
        "CLD",
        "FRY",
        "BWY",
        "CTH",
        "FKS",
        "EMK",
        "NTL",
        "TWL",
        "FFL",
    ),
)

# =============================================================================
# AMTRAK ROUTES
# =============================================================================

AMTRAK_NEC = Route(
    id="amtrak-nec",
    name="Northeast Corridor",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "BOS",
        "BBY",
        "PVD",
        "KIN",
        "WLY",
        "NLC",
        "OSB",
        "NHV",
        "BRP",
        "STM",
        "NY",
        "NP",
        "TR",
        "PH",
        "WI",
        "BL",
        "BA",
        "WS",
    ),
)

AMTRAK_KEYSTONE = Route(
    id="amtrak-keystone",
    name="Keystone Service",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "NY",
        "NP",
        "TR",
        "PH",
        "PAO",
        "EXT",
        "DOW",
        "COT",
        "PKB",
        "LNC",
        "HAR",
    ),
)

AMTRAK_SOUTHEAST = Route(
    id="amtrak-southeast",
    name="Silver Service / Carolinian",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "WS",
        "ALX",
        "RVR",
        "PTB",
        "RMT",
        "WLN",
        "SEL",
        "RGH",
        "CAR",
        "DNC",
        "GRB",
        "HPT",
        "SAL",
        "CLT",
    ),
)

AMTRAK_CRESCENT = Route(
    id="amtrak-crescent",
    name="Crescent",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("CLT", "GAS", "SPB", "GVL", "TOC", "GAI", "ATL"),
)

AMTRAK_SILVER_SOUTH = Route(
    id="amtrak-silver-south",
    name="Silver Service (South)",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("SEL", "SOU", "HAM", "DIL"),
)

AMTRAK_COASTAL = Route(
    id="amtrak-coastal",
    name="Silver Service (Coastal)",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("DIL", "FLO", "KTR", "CHS", "SAV", "JES", "JAX"),
)

AMTRAK_FLORIDA = Route(
    id="amtrak-florida",
    name="Silver Star (Tampa)",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("JAX", "PAL", "DLD", "SAN", "WPK", "ORL", "KIS", "WTH", "LKL", "TPA"),
)

AMTRAK_MIAMI = Route(
    id="amtrak-miami",
    name="Silver Meteor (Miami)",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "JAX",
        "PAL",
        "DLD",
        "SAN",
        "WPK",
        "ORL",
        "KIS",
        "WPB",
        "DLB",
        "FTL",
        "HLW",
        "MIA",
    ),
)

AMTRAK_ZEPHYR = Route(
    id="amtrak-zephyr",
    name="California Zephyr",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("CHI", "OMA", "DEN", "SLC", "RNO", "TRU", "SAC", "EMY"),
)

AMTRAK_CHIEF = Route(
    id="amtrak-chief",
    name="Southwest Chief",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("CHI", "KCY", "ABQ", "FLG", "LAX"),
)

AMTRAK_EMPIRE_BUILDER = Route(
    id="amtrak-empire-builder",
    name="Empire Builder",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("CHI", "MKE", "MSP", "HAV", "GPK", "WFH", "SPK", "SEA"),
)

AMTRAK_STARLIGHT = Route(
    id="amtrak-starlight",
    name="Coast Starlight",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "SEA",
        "TAC",
        "PDX",
        "SLM",
        "EUG",
        "SAC",
        "EMY",
        "SJC",
        "SLO",
        "SBA",
        "LAX",
    ),
)

AMTRAK_SUNSET = Route(
    id="amtrak-sunset",
    name="Sunset Limited",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("NOL", "HOS", "SAS", "ELP", "TUS", "LAX"),
)

AMTRAK_TEXAS_EAGLE = Route(
    id="amtrak-texas-eagle",
    name="Texas Eagle",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("CHI", "STL", "LRK", "DAL", "FTW", "AUS", "SAS"),
)

AMTRAK_CITY_NOLA = Route(
    id="amtrak-city-nola",
    name="City of New Orleans",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("CHI", "MEM", "NOL"),
)

AMTRAK_CAPITOL = Route(
    id="amtrak-capitol",
    name="Capitol Limited",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("CHI", "TOL", "CLE", "PGH", "WS"),
)

AMTRAK_LAKESHORE = Route(
    id="amtrak-lakeshore",
    name="Lake Shore Limited",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("CHI", "TOL", "CLE", "BUF", "ALB", "NY"),
)

AMTRAK_SURFLINER = Route(
    id="amtrak-surfliner",
    name="Pacific Surfliner",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("OLT", "OSD", "SNA", "FUL", "LAX", "SBA", "SLO"),
)

AMTRAK_CASCADES = Route(
    id="amtrak-cascades",
    name="Cascades",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("EUG", "SLM", "PDX", "TAC", "SEA"),
)

AMTRAK_EMPIRE_SERVICE = Route(
    id="amtrak-empire-service",
    name="Empire Service",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("NY", "ALB", "SYR", "ROC", "BUF"),
)

# =============================================================================
# LIRR ROUTES
# =============================================================================
# Note: Unlike iOS RouteTopology.swift which splits trunk from branches for map
# drawing, backend routes include the full station path (trunk + branch) so that
# segment normalization can expand skip-stop segments end-to-end.
#
# Station codes use L-prefix where needed to avoid Amtrak/NJT collisions
# (e.g., LMIN for Mineola vs Amtrak MIN for Mineola TX).

LIRR_BABYLON = Route(
    id="lirr-babylon",
    name="Babylon Branch",
    data_source="LIRR",
    line_codes=frozenset({"LIRR-BB"}),
    stations=(
        "NY",
        "WDD",
        "FHL",
        "KGN",
        "JAM",
        "VSM",
        "LYN",
        "RVC",
        "BWN",
        "FPT",
        "MRK",
        "BMR",
        "WGH",
        "SFD",
        "MQA",
        "LMPK",
        "AVL",
        "CPG",
        "LHT",
        "BTA",
    ),
)

LIRR_HEMPSTEAD = Route(
    id="lirr-hempstead",
    name="Hempstead Branch",
    data_source="LIRR",
    line_codes=frozenset({"LIRR-HB"}),
    stations=(
        "NY",
        "WDD",
        "FHL",
        "KGN",
        "JAM",
        "QVG",
        "LHOL",
        "FPK",
        "SMR",
        "NBD",
        "GCY",
        "LCLP",
        "HGN",
        "LHEM",
    ),
)

LIRR_OYSTER_BAY = Route(
    id="lirr-oyster-bay",
    name="Oyster Bay Branch",
    data_source="LIRR",
    line_codes=frozenset({"LIRR-OB"}),
    stations=(
        "NY",
        "WDD",
        "FHL",
        "KGN",
        "JAM",
        "MAV",
        "LMIN",
        "EWN",
        "ABT",
        "RSN",
        "LGVL",
        "GHD",
        "SCF",
        "GST",
        "GCV",
        "LVL",
        "OBY",
    ),
)

LIRR_RONKONKOMA = Route(
    id="lirr-ronkonkoma",
    name="Ronkonkoma Branch",
    data_source="LIRR",
    line_codes=frozenset({"LIRR-RK"}),
    stations=(
        "NY",
        "WDD",
        "FHL",
        "KGN",
        "JAM",
        "MAV",
        "LMIN",
        "CPL",
        "WBY",
        "LHVL",
        "BPG",
        "LFMD",
        "PLN",
        "WYD",
        "DPK",
        "BWD",
        "CI",
        "RON",
    ),
)

LIRR_MONTAUK = Route(
    id="lirr-montauk",
    name="Montauk Branch",
    data_source="LIRR",
    line_codes=frozenset({"LIRR-MK"}),
    stations=(
        # Trunk + Babylon Branch (Montauk trains run via Babylon)
        "NY",
        "WDD",
        "FHL",
        "KGN",
        "JAM",
        "VSM",
        "LYN",
        "RVC",
        "BWN",
        "FPT",
        "MRK",
        "BMR",
        "WGH",
        "SFD",
        "MQA",
        "LMPK",
        "AVL",
        "CPG",
        "LHT",
        "BTA",
        # Montauk Branch extension east of Babylon
        "BSR",
        "ISP",
        "GRV",
        "ODL",
        "SVL",
        "PGE",
        "BPT",
        "MSY",
        "LSPK",
        "WHN",
        "HBY",
        "SHN",
        "BHN",
        "EHN",
        "AGT",
        "MTK",
    ),
)

LIRR_LONG_BEACH = Route(
    id="lirr-long-beach",
    name="Long Beach Branch",
    data_source="LIRR",
    line_codes=frozenset({"LIRR-LB"}),
    stations=(
        "NY",
        "WDD",
        "FHL",
        "KGN",
        "JAM",
        "VSM",
        "LYN",
        "CAV",
        "ERY",
        "ODE",
        "IPK",
        "LBH",
    ),
)

LIRR_FAR_ROCKAWAY = Route(
    id="lirr-far-rockaway",
    name="Far Rockaway Branch",
    data_source="LIRR",
    line_codes=frozenset({"LIRR-FR"}),
    stations=(
        "NY",
        "WDD",
        "FHL",
        "KGN",
        "JAM",
        "LLMR",
        "LTN",
        "ROS",
        "VSM",
        "GBN",
        "HWT",
        "WMR",
        "CHT",
        "LCE",
        "IWD",
        "LFRY",
    ),
)

LIRR_WEST_HEMPSTEAD = Route(
    id="lirr-west-hempstead",
    name="West Hempstead Branch",
    data_source="LIRR",
    line_codes=frozenset({"LIRR-WH"}),
    stations=(
        "NY",
        "WDD",
        "FHL",
        "KGN",
        "JAM",
        "LSAB",
        "VSM",
        "LWWD",
        "LMVN",
        "LLVW",
        "HGN",
        "WHD",
    ),
)

LIRR_PORT_WASHINGTON = Route(
    id="lirr-port-washington",
    name="Port Washington Branch",
    data_source="LIRR",
    line_codes=frozenset({"LIRR-PW"}),
    stations=(
        # Port Washington doesn't go through Jamaica
        "NY",
        "WDD",
        "LSSM",
        "FLS",
        "LMHL",
        "BDY",
        "ADL",
        "BSD",
        "DGL",
        "LLNK",
        "GNK",
        "MHT",
        "PDM",
        "PWS",
    ),
)

LIRR_PORT_JEFFERSON = Route(
    id="lirr-port-jefferson",
    name="Port Jefferson Branch",
    data_source="LIRR",
    line_codes=frozenset({"LIRR-PJ"}),
    stations=(
        "NY",
        "WDD",
        "FHL",
        "KGN",
        "JAM",
        "MAV",
        "LMIN",
        "LHVL",
        "SYT",
        "CSH",
        "LHUN",
        "GWN",
        "NPT",
        "KPK",
        "LSTN",
        "LSJM",
        "LSBK",
        "PJN",
    ),
)

LIRR_ATLANTIC = Route(
    id="lirr-atlantic",
    name="Atlantic Branch",
    data_source="LIRR",
    line_codes=frozenset(),  # Terminal approach, trains tagged with branch line_code
    stations=("LAT", "NAV", "ENY", "JAM"),
)

LIRR_GRAND_CENTRAL = Route(
    id="lirr-grand-central",
    name="Grand Central Madison",
    data_source="LIRR",
    line_codes=frozenset(),  # Terminal approach, trains tagged with branch line_code
    stations=("GCT", "JAM"),
)

LIRR_BELMONT_PARK = Route(
    id="lirr-belmont-park",
    name="Belmont Park",
    data_source="LIRR",
    line_codes=frozenset({"LIRR-BP"}),
    stations=(
        "NY",
        "WDD",
        "FHL",
        "KGN",
        "JAM",
        "QVG",
        "BRS",
        "EMT",
    ),
)

LIRR_GREENPORT = Route(
    id="lirr-greenport",
    name="Greenport Service",
    data_source="LIRR",
    line_codes=frozenset({"LIRR-GP"}),
    stations=(
        # Greenport service runs via Ronkonkoma Branch
        "NY",
        "WDD",
        "FHL",
        "KGN",
        "JAM",
        "MAV",
        "LMIN",
        "CPL",
        "WBY",
        "LHVL",
        "BPG",
        "LFMD",
        "PLN",
        "WYD",
        "DPK",
        "BWD",
        "CI",
        "RON",
        # Eastern extension to Greenport
        "MFD",
        "YPK",
        "RHD",
        "MAK",
        "SHD",
        "GPT",
    ),
)

# =============================================================================
# MNR ROUTES
# =============================================================================
# MNR station codes use M-prefix consistently (e.g., MYON for Yonkers).
# Station sequences match iOS RouteTopology.swift.

MNR_HUDSON = Route(
    id="mnr-hudson",
    name="Hudson Line",
    data_source="MNR",
    line_codes=frozenset({"MNR-HUD"}),
    stations=(
        "GCT",
        "M125",
        "MEYS",
        "MMRH",
        "MUNH",
        "MMBL",
        "MSDV",
        "MRVD",
        "MLUD",
        "MYON",
        "MGWD",
        "MGRY",
        "MHOH",
        "MDBF",
        "MARD",
        "MIRV",
        "MTTN",
        "MPHM",
        "MSCB",
        "MOSS",
        "MCRH",
        "MCRT",
        "MPKS",
        "MMAN",
        "MGAR",
        "MCSP",
        "MBRK",
        "MBCN",
        "MNHB",
        "MPOK",
    ),
)

MNR_HARLEM = Route(
    id="mnr-harlem",
    name="Harlem Line",
    data_source="MNR",
    line_codes=frozenset({"MNR-HAR"}),
    stations=(
        "GCT",
        "M125",
        "MMEL",
        "MTRM",
        "MFOR",
        "MBOG",
        "MWBG",
        "MWDL",
        "MWKF",
        "MMVW",
        "MFLT",
        "MBRX",
        "MTUC",
        "MCWD",
        "MSCD",
        "MHSD",
        "MWPL",
        "MNWP",
        "MVAL",
        "MMTP",
        "MHWT",
        "MPLV",
        "MCHP",
        "MMTK",
        "MBDH",
        "MKAT",
        "MGLD",
        "MPRD",
        "MCFL",
        "MBRS",
        "MSET",
        "MPAT",
        "MPAW",
        "MAPT",
        "MHVW",
        "MDVP",
        "MTMR",
        "MWAS",
    ),
)

MNR_NEW_HAVEN = Route(
    id="mnr-new-haven",
    name="New Haven Line",
    data_source="MNR",
    line_codes=frozenset({"MNR-NH"}),
    stations=(
        "GCT",
        "M125",
        "MMVE",
        "MPEL",
        "MNRC",
        "MLRM",
        "MMAM",
        "MHRR",
        "MRYE",
        "MPCH",
        "MGRN",
        "MCOC",
        "MRSD",
        "MODG",
        "MSTM",
        "MNOH",
        "MDAR",
        "MROW",
        "MSNW",
        "MENW",
        "MWPT",
        "MGRF",
        "MSPT",
        "MFFD",
        "MFBR",
        "MBGP",
        "MSTR",
        "MMIL",
        "MWHN",
        "MNHV",
        "MNSS",
    ),
)

MNR_NEW_CANAAN = Route(
    id="mnr-new-canaan",
    name="New Canaan Branch",
    data_source="MNR",
    line_codes=frozenset({"MNR-NC"}),
    stations=(
        # New Haven trunk: GCT to Stamford (branch junction)
        "GCT",
        "M125",
        "MMVE",
        "MPEL",
        "MNRC",
        "MLRM",
        "MMAM",
        "MHRR",
        "MRYE",
        "MPCH",
        "MGRN",
        "MCOC",
        "MRSD",
        "MODG",
        # New Canaan branch
        "MSTM",
        "MGLB",
        "MSPD",
        "MTMH",
        "MNCA",
    ),
)

MNR_DANBURY = Route(
    id="mnr-danbury",
    name="Danbury Branch",
    data_source="MNR",
    line_codes=frozenset({"MNR-DAN"}),
    stations=(
        # New Haven trunk: GCT to South Norwalk (branch junction)
        "GCT",
        "M125",
        "MMVE",
        "MPEL",
        "MNRC",
        "MLRM",
        "MMAM",
        "MHRR",
        "MRYE",
        "MPCH",
        "MGRN",
        "MCOC",
        "MRSD",
        "MODG",
        "MSTM",
        "MNOH",
        "MDAR",
        "MROW",
        # Danbury branch
        "MSNW",
        "MMR7",
        "MWIL",
        "MCAN",
        "MBVL",
        "MRED",
        "MBTH",
        "MDBY",
    ),
)

MNR_WATERBURY = Route(
    id="mnr-waterbury",
    name="Waterbury Branch",
    data_source="MNR",
    line_codes=frozenset({"MNR-WAT"}),
    stations=(
        # New Haven trunk: GCT to Bridgeport (branch junction)
        "GCT",
        "M125",
        "MMVE",
        "MPEL",
        "MNRC",
        "MLRM",
        "MMAM",
        "MHRR",
        "MRYE",
        "MPCH",
        "MGRN",
        "MCOC",
        "MRSD",
        "MODG",
        "MSTM",
        "MNOH",
        "MDAR",
        "MROW",
        "MSNW",
        "MENW",
        "MWPT",
        "MGRF",
        "MSPT",
        "MFFD",
        "MFBR",
        # Waterbury branch
        "MBGP",
        "MSTR",
        "MDBS",
        "MANS",
        "MSYM",
        "MBCF",
        "MNAU",
        "MWTB",
    ),
)

# =============================================================================
# REGISTRY
# =============================================================================

# Route order matters for segment expansion when line_code is not provided.
# When a segment exists on multiple routes (e.g., NY-SE on NEC and NJCL),
# the first matching route in ALL_ROUTES is used for expansion. This is safe
# because overlapping segments share the same intermediate stations.
#
# If future routes have different intermediate stations for the same physical
# segment, pass line_code to get_canonical_segments() for correct expansion.

ALL_ROUTES: tuple[Route, ...] = (
    # NJT
    NJT_NORTHEAST_CORRIDOR,
    NJT_NORTH_JERSEY_COAST,
    NJT_MORRIS_ESSEX_MORRISTOWN,
    NJT_GLADSTONE,
    NJT_RARITAN_VALLEY,
    NJT_MONTCLAIR_BOONTON,
    NJT_MAIN_LINE,
    NJT_BERGEN_COUNTY,
    NJT_PORT_JERVIS,
    NJT_PASCACK_VALLEY,
    NJT_ATLANTIC_CITY,
    NJT_PRINCETON_BRANCH,
    # PATH
    PATH_HOB_33,
    PATH_HOB_WTC,
    PATH_JSQ_33,
    PATH_NWK_WTC,
    PATH_JSQ_33_HOB,
    PATH_NWK_HAR,
    # PATCO
    PATCO_SPEEDLINE,
    # AMTRAK
    AMTRAK_NEC,
    AMTRAK_KEYSTONE,
    AMTRAK_SOUTHEAST,
    AMTRAK_CRESCENT,
    AMTRAK_SILVER_SOUTH,
    AMTRAK_COASTAL,
    AMTRAK_FLORIDA,
    AMTRAK_MIAMI,
    AMTRAK_ZEPHYR,
    AMTRAK_CHIEF,
    AMTRAK_EMPIRE_BUILDER,
    AMTRAK_STARLIGHT,
    AMTRAK_SUNSET,
    AMTRAK_TEXAS_EAGLE,
    AMTRAK_CITY_NOLA,
    AMTRAK_CAPITOL,
    AMTRAK_LAKESHORE,
    AMTRAK_SURFLINER,
    AMTRAK_CASCADES,
    AMTRAK_EMPIRE_SERVICE,
    # LIRR
    LIRR_BABYLON,
    LIRR_HEMPSTEAD,
    LIRR_OYSTER_BAY,
    LIRR_RONKONKOMA,
    LIRR_MONTAUK,
    LIRR_LONG_BEACH,
    LIRR_FAR_ROCKAWAY,
    LIRR_WEST_HEMPSTEAD,
    LIRR_PORT_WASHINGTON,
    LIRR_PORT_JEFFERSON,
    LIRR_ATLANTIC,
    LIRR_GRAND_CENTRAL,
    LIRR_BELMONT_PARK,
    LIRR_GREENPORT,
    # MNR
    MNR_HUDSON,
    MNR_HARLEM,
    MNR_NEW_HAVEN,
    MNR_NEW_CANAAN,
    MNR_DANBURY,
    MNR_WATERBURY,
)

# Lookup indexes for fast access
_ROUTES_BY_DATA_SOURCE: dict[str, list[Route]] = {}
_ROUTES_BY_LINE_CODE: dict[tuple[str, str], Route] = {}

for _route in ALL_ROUTES:
    _ROUTES_BY_DATA_SOURCE.setdefault(_route.data_source, []).append(_route)
    for _line_code in _route.line_codes:
        _ROUTES_BY_LINE_CODE[(_route.data_source, _line_code)] = _route


def get_route_by_line_code(data_source: str, line_code: str) -> Route | None:
    """Get route by data source and line code."""
    return _ROUTES_BY_LINE_CODE.get((data_source, line_code))


def get_routes_for_data_source(data_source: str) -> list[Route]:
    """Get all routes for a data source."""
    return _ROUTES_BY_DATA_SOURCE.get(data_source, [])


def find_route_for_segment(
    data_source: str,
    from_station: str,
    to_station: str,
    line_code: str | None = None,
) -> Route | None:
    """
    Find the route that contains a given segment.

    If line_code is provided, looks up directly.
    Otherwise, searches all routes for the data source.
    """
    if line_code:
        route = get_route_by_line_code(data_source, line_code)
        if route and route.contains_segment(from_station, to_station):
            return route

    # Search all routes for this data source
    for route in get_routes_for_data_source(data_source):
        if route.contains_segment(from_station, to_station):
            return route

    return None


def get_canonical_segments(
    data_source: str,
    from_station: str,
    to_station: str,
    line_code: str | None = None,
) -> list[tuple[str, str]]:
    """
    Get canonical segment pairs for a given segment.

    If the segment spans multiple stations (A→C), expands it to
    canonical pairs [(A, B), (B, C)] using route topology.

    If no matching route is found, returns the original segment as-is.

    Args:
        data_source: The transit system (NJT, PATH, etc.)
        from_station: Starting station code
        to_station: Ending station code
        line_code: Optional line code for more precise route matching

    Returns:
        List of (from_station, to_station) tuples representing canonical segments
    """
    route = find_route_for_segment(data_source, from_station, to_station, line_code)

    if route is None:
        # No matching route - return segment as-is
        return [(from_station, to_station)]

    canonical = route.expand_to_canonical_segments(from_station, to_station)

    if canonical is None or len(canonical) == 0:
        # Shouldn't happen if route.contains_segment was true, but handle gracefully
        return [(from_station, to_station)]

    return canonical
