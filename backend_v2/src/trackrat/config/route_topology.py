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

from collections import defaultdict, deque

from dataclasses import dataclass

from trackrat.config.stations.metra import METRA_ROUTE_STATIONS, METRA_ROUTES


@dataclass(frozen=True)
class Route:
    """A transit route with ordered station sequence."""

    id: str  # Unique identifier (e.g., "njt-nec")
    name: str  # Display name
    data_source: str  # "NJT", "AMTRAK", "PATH", "PATCO", "LIRR", "MNR", "SUBWAY"
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
    line_codes=frozenset({"GL", "Gl"}),  # "Gl" for pre-2026-03 DB records
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
    line_codes=frozenset({"RV", "Ra"}),  # "Ra" for pre-2026-03 DB records
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
    line_codes=frozenset({"MO", "Mo"}),  # "Mo" for pre-2026-03 DB records
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
    line_codes=frozenset({"MA", "Ma"}),  # "Ma" for pre-2026-03 DB records
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
    line_codes=frozenset({"BE", "Be"}),  # "Be" for pre-2026-03 DB records
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
    stations=("SF", "XG", "TC", "RM", "MD", "CW", "CB", "OS", "PO"),
)

NJT_PASCACK_VALLEY = Route(
    id="njt-pascack",
    name="Pascack Valley Line",
    data_source="NJT",
    line_codes=frozenset({"PV", "Pa"}),  # "Pa" for pre-2026-03 DB records
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
    line_codes=frozenset({"AC", "At"}),  # "At" for pre-2026-03 DB records
    stations=("PH", "PN", "CY", "LW", "AO", "HN", "EH", "AB", "AC"),
)

NJT_PRINCETON_BRANCH = Route(
    id="njt-princeton",
    name="Princeton Branch",
    data_source="NJT",
    line_codes=frozenset({"PR", "Pr"}),  # "Pr" for pre-2026-03 DB records
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
    name="Journal Square - 33rd Street via Hoboken",
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
        "RTE",
        "PVD",
        "KIN",
        "WLY",
        "NLC",
        "OSB",
        "NHV",
        "BRP",
        "STM",
        "NRO",
        "NY",
        "NP",
        "MP",
        "NB",
        "PJ",
        "TR",
        "CWH",
        "PHN",
        "PH",
        "WI",
        "ABE",
        "BL",
        "BA",
        "NCR",
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
        "MP",
        "NB",
        "PJ",
        "TR",
        "CWH",
        "PHN",
        "PH",
        "PAO",
        "EXT",
        "DOW",
        "COT",
        "PAR",
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
    stations=(
        "CLT",
        "GAS",
        "SPB",
        "GVL",
        "TOC",
        "GAI",
        "ATL",
        "ATN",
        "BHM",
        "TCL",
        "MEI",
        "LAU",
        "HBG",
        "PIC",
        "SDL",
        "NOL",
    ),
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
    stations=(
        "CHI",
        "NPV",
        "PLO",
        "GBB",
        "BRL",
        "MTP",
        "OTM",
        "CRN",
        "OMA",
        "LNK",
        "HAS",
        "HLD",
        "MCK",
        "FMG",
        "DEN",
        "WIP",
        "GSC",
        "GJT",
        "HER",
        "PRO",
        "SLC",
        "ELK",
        "WNN",
        "RNO",
        "TRU",
        "SAC",
        "EMY",
    ),
)

AMTRAK_CHIEF = Route(
    id="amtrak-chief",
    name="Southwest Chief",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "CHI",
        "GBB",
        "FMD",
        "LAP",
        "KCY",
        "TOP",
        "LRC",
        "DDG",
        "GCK",
        "LAJ",
        "TRI",
        "RAT",
        "LSV",
        "LMY",
        "ABQ",
        "GLP",
        "WLO",
        "FLG",
        "WMH",
        "KNG",
        "NDL",
        "BAR",
        "LAX",
    ),
)

AMTRAK_EMPIRE_BUILDER = Route(
    id="amtrak-empire-builder",
    name="Empire Builder",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "CHI",
        "GLN",
        "MKE",
        "CBS",
        "POG",
        "WDL",
        "TOH",
        "LSE",
        "WIN",
        "RDW",
        "MSP",
        "SCD",
        "SPL",
        "DLK",
        "FAR",
        "GFK",
        "DVL",
        "RUG",
        "MOT",
        "STN",
        "WTN",
        "WPT",
        "GGW",
        "MAL",
        "HAV",
        "SBY",
        "CUT",
        "BRO",
        "ESM",
        "WGL",
        "GPK",
        "WFH",
        "LIB",
        "SPT",
        "SPK",
        "EPH",
        "WEN",
        "LWA",
        "EVR",
        "EDM",
        "SEA",
    ),
)

AMTRAK_EMPIRE_BUILDER_PDX = Route(
    id="amtrak-empire-builder-pdx",
    name="Empire Builder (Portland)",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        # Splits from main Empire Builder at Spokane
        "SPK",
        "PSC",
        "WIH",
        "BNG",
        "PDX",
    ),
)

AMTRAK_STARLIGHT = Route(
    id="amtrak-starlight",
    name="Coast Starlight",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "SEA",
        "TAC",
        "CTL",
        "KEL",
        "PDX",
        "SLM",
        "EUG",
        "DUN",
        "RDD",
        "CIC",
        "MRV",
        "SAC",
        "EMY",
        "SJC",
        "SNS",
        "PRB",
        "SLO",
        "SBA",
        "OXN",
        "LAX",
    ),
)

AMTRAK_SUNSET = Route(
    id="amtrak-sunset",
    name="Sunset Limited",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "NOL",
        "SCH",
        "NIB",
        "LFT",
        "LCH",
        "BMT",
        "HOS",
        "SAS",
        "DRT",
        "SND",
        "ALP",
        "ELP",
        "DEM",
        "LDB",
        "BEN",
        "TUS",
        "MRC",
        "LAX",
    ),
)

AMTRAK_TEXAS_EAGLE = Route(
    id="amtrak-texas-eagle",
    name="Texas Eagle",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "CHI",
        "STL",
        "LRK",
        "TXA",
        "MHL",
        "LVW",
        "DAL",
        "FTW",
        "CBR",
        "MCG",
        "TPL",
        "TAY",
        "AUS",
        "SMC",
        "SAS",
    ),
)

AMTRAK_CITY_NOLA = Route(
    id="amtrak-city-nola",
    name="City of New Orleans",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "CHI",
        "HMW",
        "KKI",
        "CHM",
        "MAT",
        "EFG",
        "CEN",
        "CDL",
        "MEM",
        "GWD",
        "YAZ",
        "JAN",
        "HAZ",
        "BRH",
        "MCB",
        "HMD",
        "NOL",
    ),
)

AMTRAK_CAPITOL = Route(
    id="amtrak-capitol",
    name="Capitol Limited",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "CHI",
        "SOB",
        "EKH",
        "WTI",
        "BYN",
        "TOL",
        "SKY",
        "ELY",
        "CLE",
        "ALC",
        "PGH",
        "COV",
        "CUM",
        "MRB",
        "HFY",
        "WS",
    ),
)

AMTRAK_LAKESHORE = Route(
    id="amtrak-lakeshore",
    name="Lake Shore Limited",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "CHI",
        "SOB",
        "EKH",
        "WTI",
        "BYN",
        "TOL",
        "SKY",
        "ELY",
        "CLE",
        "ERI",
        "BUF",
        "ROC",
        "SYR",
        "UCA",
        "AMS",
        "ALB",
        "REN",
        "NY",
    ),
)

AMTRAK_SURFLINER = Route(
    id="amtrak-surfliner",
    name="Pacific Surfliner",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "SLO",
        "GVB",
        "LPS",
        "GTA",
        "SBA",
        "VEC",
        "OXN",
        "CML",
        "MPK",
        "SIM",
        "BUR",
        "VNC",
        "LAX",
        "FUL",
        "ANA",
        "SNA",
        "IRV",
        "SNC",
        "SNP",
        "OSD",
        "SOL",
        "OLT",
    ),
)

AMTRAK_CASCADES = Route(
    id="amtrak-cascades",
    name="Cascades",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "VAN",
        "BEL",
        "MVW",
        "EDM",
        "SEA",
        "TUK",
        "TAC",
        "OLW",
        "CTL",
        "KEL",
        "PDX",
        "ORC",
        "SLM",
        "EUG",
    ),
)

AMTRAK_EMPIRE_SERVICE = Route(
    id="amtrak-empire-service",
    name="Empire Service",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "NY",
        "YNY",
        "CRT",
        "POU",
        "RHI",
        "HUD",
        "SDY",
        "ALB",
        "AMS",
        "UCA",
        "SYR",
        "ROC",
        "BUF",
    ),
)

AMTRAK_CAPITOL_CORRIDOR = Route(
    id="amtrak-capitol-corridor",
    name="Capitol Corridor",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "SJC",
        "SCC",
        "GAC",
        "FMT",
        "HAY",
        "OAC",
        "OKJ",
        "EMY",
        "BKY",
        "RIC",
        "MTZ",
        "SUI",
        "FFV",
        "DAV",
        "SAC",
        "RSV",
        "RLN",
        "ARN",
    ),
)

AMTRAK_HIAWATHA = Route(
    id="amtrak-hiawatha",
    name="Hiawatha",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("CHI", "GLN", "SVT", "MKA", "MKE"),
)

AMTRAK_LINCOLN = Route(
    id="amtrak-lincoln",
    name="Lincoln Service",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("CHI", "SMT", "JOL", "PON", "BNL", "LCN", "SPI", "CRV", "ALN", "STL"),
)

AMTRAK_SAN_JOAQUINS_SAC = Route(
    id="amtrak-san-joaquins-sac",
    name="San Joaquins (Sacramento)",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("SAC", "SKT", "LOD", "MCD", "HNF", "BFD"),
)

AMTRAK_SAN_JOAQUINS_OAK = Route(
    id="amtrak-san-joaquins-oak",
    name="San Joaquins (Oakland)",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("OKJ", "SKN", "MCD", "HNF", "BFD"),
)

AMTRAK_WOLVERINE = Route(
    id="amtrak-wolverine",
    name="Wolverine",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "CHI",
        "NLS",
        "DOA",
        "KAL",
        "BTL",
        "ALI",
        "JXN",
        "ARB",
        "DER",
        "ROY",
        "TRM",
        "PNT",
    ),
)

AMTRAK_DOWNEASTER = Route(
    id="amtrak-downeaster",
    name="Downeaster",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("BOS", "HHL", "EXR", "DOV", "SAO", "POR", "FRE", "BRK"),
)

AMTRAK_PIEDMONT = Route(
    id="amtrak-piedmont",
    name="Piedmont",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("RGH", "DNC", "GRO", "HPT", "CLT"),
)

AMTRAK_VERMONTER = Route(
    id="amtrak-vermonter",
    name="Vermonter",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        # NEC trunk included so cross-route segments (e.g. NY→BTN)
        # can be resolved without requiring a multi-route chain lookup.
        "NY",
        "NRO",
        "STM",
        "BRP",
        "NHV",
        "HFD",
        "WNL",
        "SPG",
        "HLK",
        "NHT",
        "GFD",
        "BRA",
        "BLF",
        "CLA",
        "WND",
        "WRJ",
        "RPH",
        "MPR",
        "WAB",
        "ESX",
        "BTN",
        "SAB",
    ),
)

AMTRAK_ETHAN_ALLEN = Route(
    id="amtrak-ethan-allen",
    name="Ethan Allen Express",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "NY",
        "YNY",
        "CRT",
        "POU",
        "RHI",
        "HUD",
        "SDY",
        "ALB",
        "SAR",
        "FED",
        "WHL",
        "CNV",
        "RUD",
    ),
)

AMTRAK_ADIRONDACK = Route(
    id="amtrak-adirondack",
    name="Adirondack",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "NY",
        "YNY",
        "CRT",
        "POU",
        "RHI",
        "HUD",
        "SDY",
        "ALB",
        "SAR",
        "FED",
        "WHL",
        "FTC",
        "POH",
        "PLB",
        "RSP",
        "MTR",
    ),
)

AMTRAK_PALMETTO = Route(
    id="amtrak-palmetto",
    name="Palmetto",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        # NEC trunk included so cross-route segments (e.g. NY→SAV)
        # can be resolved without requiring a multi-route chain lookup.
        # Overlaps with AMTRAK_SOUTHEAST (WS→CLT) and AMTRAK_COASTAL (DIL→JAX)
        # but provides the full NY→SAV path for trains skipping branches.
        "NY",
        "NP",
        "MP",
        "NB",
        "PJ",
        "TR",
        "CWH",
        "PHN",
        "PH",
        "WI",
        "ABE",
        "BL",
        "BA",
        "NCR",
        "WS",
        "ALX",
        "RVR",
        "PTB",
        "RMT",
        "WLN",
        "SEL",
        "RGH",
        "FLO",
        "CHS",
        "SAV",
    ),
)

AMTRAK_CARDINAL = Route(
    id="amtrak-cardinal",
    name="Cardinal",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        # NEC trunk included so cross-route segments (e.g. NY→CHI)
        # can be resolved without requiring a multi-route chain lookup.
        "NY",
        "NP",
        "MP",
        "NB",
        "PJ",
        "TR",
        "CWH",
        "PHN",
        "PH",
        "WI",
        "ABE",
        "BL",
        "BA",
        "NCR",
        "WS",
        "CLP",
        "CVS",
        "STA",
        "CLF",
        "WSS",
        "ALD",
        "HIN",
        "THU",
        "CHW",
        "HUN",
        "AKY",
        "SPM",
        "MAY",
        "CIN",
        "COI",
        "IND",
        "CRF",
        "CHI",
    ),
)

AMTRAK_PERE_MARQUETTE = Route(
    id="amtrak-pere-marquette",
    name="Pere Marquette",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "CHI",
        "NLS",
        "DOA",
        "KAL",
        "BTL",
        "ALI",
        "JXN",
        "LNS",
        "HOM",
        "GRR",
    ),
)

AMTRAK_BLUE_WATER = Route(
    id="amtrak-blue-water",
    name="Blue Water",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "CHI",
        "NLS",
        "DOA",
        "KAL",
        "BTL",
        "ALI",
        "JXN",
        "LNS",
        "DRD",
        "FLN",
        "LPE",
        "PTH",
    ),
)

AMTRAK_ILLINOIS_ZEPHYR = Route(
    id="amtrak-illinois-zephyr",
    name="Illinois Zephyr / Carl Sandburg",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=(
        "CHI",
        "NPV",
        "PLO",
        "MDT",
        "PCT",
        "KEE",
        "GBB",
        "MAC",
        "QCY",
    ),
)

AMTRAK_AUTO_TRAIN = Route(
    id="amtrak-auto-train",
    name="Auto Train",
    data_source="AMTRAK",
    line_codes=frozenset({"AM"}),
    stations=("LOR", "SFA"),
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
        "NHP",
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
        "NHP",
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
        # Port Washington — Penn Station terminus
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

LIRR_PORT_WASHINGTON_GCT = Route(
    id="lirr-port-washington-gct",
    name="Port Washington Branch",
    data_source="LIRR",
    line_codes=frozenset(),  # Terminal variant, resolved via find_route_for_segment
    stations=(
        # Port Washington — Grand Central Terminal terminus (via East Side Access)
        "GCT",
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
        "NHP",
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
    stations=("GCT", "FHL", "KGN", "JAM"),
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
        "NHP",
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


# =============================================================================
# NYC Subway Routes
# Auto-generated by scripts/generate_subway_data.py
# =============================================================================

SUBWAY_1 = Route(
    id="subway-1",
    name="1 Broadway - 7 Avenue Local",
    data_source="SUBWAY",
    line_codes=frozenset({"1"}),
    stations=(
        "S142",
        "S139",
        "S138",
        "S137",
        "S136",
        "S135",
        "S134",
        "S133",
        "S132",
        "S131",
        "S130",
        "S129",
        "S128",
        "S127",
        "S126",
        "S125",
        "S124",
        "S123",
        "S122",
        "S121",
        "S120",
        "S119",
        "S118",
        "S117",
        "S116",
        "S115",
        "S114",
        "S113",
        "S112",
        "S111",
        "S110",
        "S109",
        "S108",
        "S107",
        "S106",
        "S104",
        "S103",
        "S101",
    ),
)

SUBWAY_2 = Route(
    id="subway-2",
    name="2 7 Avenue Express",
    data_source="SUBWAY",
    line_codes=frozenset({"2"}),
    stations=(
        "S247",
        "S246",
        "S245",
        "S244",
        "S243",
        "S242",
        "S241",
        "S239",
        "S238",
        "S237",
        "S236",
        "S235",
        "S234",
        "S233",
        "S232",
        "S231",
        "S230",
        "S229",
        "S228",
        "S137",
        "S136",
        "S135",
        "S134",
        "S133",
        "S132",
        "S131",
        "S130",
        "S129",
        "S128",
        "S127",
        "S126",
        "S125",
        "S124",
        "S123",
        "S122",
        "S121",
        "S120",
        "S227",
        "S226",
        "S225",
        "S224",
        "S222",
        "S221",
        "S220",
        "S219",
        "S218",
        "S217",
        "S216",
        "S215",
        "S214",
        "S213",
        "S212",
        "S211",
        "S210",
        "S209",
        "S208",
        "S207",
        "S206",
        "S205",
        "S204",
        "S201",
    ),
)

SUBWAY_3 = Route(
    id="subway-3",
    name="3 7 Avenue Express",
    data_source="SUBWAY",
    line_codes=frozenset({"3"}),
    stations=(
        "S257",
        "S256",
        "S255",
        "S254",
        "S253",
        "S252",
        "S251",
        "S250",
        "S249",
        "S248",
        "S239",
        "S238",
        "S237",
        "S236",
        "S235",
        "S234",
        "S233",
        "S232",
        "S231",
        "S230",
        "S229",
        "S228",
        "S137",
        "S132",
        "S128",
        "S127",
        "S123",
        "S120",
        "S227",
        "S226",
        "S225",
        "S224",
        "S302",
        "S301",
    ),
)

SUBWAY_4 = Route(
    id="subway-4",
    name="4 Lexington Avenue Express",
    data_source="SUBWAY",
    line_codes=frozenset({"4"}),
    stations=(
        "S257",
        "S256",
        "S255",
        "S254",
        "S253",
        "S252",
        "S251",
        "S250",
        "S249",
        "S248",
        "S239",
        "S238",
        "S237",
        "S236",
        "S235",
        "S234",
        "S423",
        "S420",
        "S419",
        "S418",
        "S640",
        "S639",
        "S638",
        "S637",
        "S636",
        "S635",
        "S634",
        "S633",
        "S632",
        "S631",
        "S630",
        "S629",
        "S628",
        "S627",
        "S626",
        "S625",
        "S624",
        "S623",
        "S622",
        "S621",
        "S416",
        "S415",
        "S414",
        "S413",
        "S412",
        "S411",
        "S410",
        "S409",
        "S408",
        "S407",
        "S406",
        "S405",
        "S402",
        "S401",
    ),
)

SUBWAY_5 = Route(
    id="subway-5",
    name="5 Lexington Avenue Express",
    data_source="SUBWAY",
    line_codes=frozenset({"5"}),
    stations=(
        # Rush-hour Brooklyn extension (Flatbush Av → Bowling Green)
        # 5 trains run extended service on 2-line tracks during peak hours
        "S247",
        "S246",
        "S245",
        "S244",
        "S243",
        "S242",
        "S241",
        "S239",
        "S238",
        "S237",
        "S236",
        "S235",
        "S234",
        "S423",
        # Regular 5 service (Bowling Green → Eastchester-Dyre Av)
        # Includes local Lex stops for off-peak/weekend local service
        "S420",
        "S419",
        "S418",
        "S640",
        "S639",
        "S638",
        "S637",
        "S636",
        "S635",
        "S634",
        "S633",
        "S632",
        "S631",
        "S630",
        "S629",
        "S628",
        "S627",
        "S626",
        "S621",
        "S416",
        "S222",
        "S221",
        "S220",
        "S219",
        "S218",
        "S217",
        "S216",
        "S215",
        "S214",
        "S213",
        "S505",
        "S504",
        "S503",
        "S502",
        "S501",
    ),
)

SUBWAY_6 = Route(
    id="subway-6",
    name="6 Lexington Avenue Local",
    data_source="SUBWAY",
    line_codes=frozenset({"6"}),
    stations=(
        "S640",
        "S639",
        "S638",
        "S637",
        "S636",
        "S635",
        "S634",
        "S633",
        "S632",
        "S631",
        "S630",
        "S629",
        "S628",
        "S627",
        "S626",
        "S625",
        "S624",
        "S623",
        "S622",
        "S621",
        "S619",
        "S618",
        "S617",
        "S616",
        "S615",
        "S614",
        "S613",
        "S612",
        "S611",
        "S610",
        "S609",
        "S608",
        "S607",
        "S606",
        "S604",
        "S603",
        "S602",
        "S601",
    ),
)

SUBWAY_6_EXPRESS = Route(
    id="subway-6x",
    name="6X Pelham Bay Park Express",
    data_source="SUBWAY",
    line_codes=frozenset({"6X"}),
    stations=(
        "S640",
        "S639",
        "S638",
        "S637",
        "S636",
        "S635",
        "S634",
        "S633",
        "S632",
        "S631",
        "S630",
        "S629",
        "S628",
        "S627",
        "S626",
        "S625",
        "S624",
        "S623",
        "S622",
        "S621",
        "S619",
        "S613",
        "S608",
        "S607",
        "S606",
        "S604",
        "S603",
        "S602",
        "S601",
    ),
)

SUBWAY_7 = Route(
    id="subway-7",
    name="7 Flushing Local",
    data_source="SUBWAY",
    line_codes=frozenset({"7"}),
    stations=(
        "S726",
        "S725",
        "S724",
        "S723",
        "S721",
        "S720",
        "S719",
        "S718",
        "S716",
        "S715",
        "S714",
        "S713",
        "S712",
        "S711",
        "S710",
        "S709",
        "S708",
        "S707",
        "S706",
        "S705",
        "S702",
        "S701",
    ),
)

SUBWAY_7_EXPRESS = Route(
    id="subway-7x",
    name="7X Flushing Express",
    data_source="SUBWAY",
    line_codes=frozenset({"7X"}),
    stations=(
        "S726",
        "S725",
        "S724",
        "S723",
        "S721",
        "S720",
        "S719",
        "S718",
        "S716",
        "S715",
        "S714",
        "S713",
        "S712",
        "S711",
        "S710",
        "S707",
        "S702",
        "S701",
    ),
)

SUBWAY_A = Route(
    id="subway-a",
    name="A 8 Avenue Express",
    data_source="SUBWAY",
    line_codes=frozenset({"A"}),
    stations=(
        "SH11",
        "SH10",
        "SH09",
        "SH08",
        "SH07",
        "SH06",
        "SH04",
        "SH03",
        "SH02",
        "SH01",
        "SA61",
        "SA60",
        "SA59",
        "SA57",
        "SA55",
        "SA54",
        "SA53",
        "SA52",
        "SA51",
        "SA50",
        "SA49",
        "SA48",
        "SA47",
        "SA46",
        "SA45",
        "SA44",
        "SA43",
        "SA42",
        "SA41",
        "SA40",
        "SA38",
        "SA36",
        "SA34",
        "SA33",
        "SA32",
        "SA31",
        "SA30",
        "SA28",
        "SA27",
        "SA25",
        "SA24",
        "SA22",
        "SA21",
        "SA20",
        "SA19",
        "SA18",
        "SA17",
        "SA16",
        "SA15",
        "SA14",
        "SA12",
        "SA11",
        "SA10",
        "SA09",
        "SA07",
        "SA06",
        "SA05",
        "SA03",
        "SA02",
    ),
)

# A train Rockaway Park branch variant - the A train serves Rockaway Park
# (SH15-SH12) via Broad Channel (SH04) during late nights and some other times,
# replacing the H shuttle. Without this route, segments like SH04→SH12 on an
# A train trip cannot be resolved by the segment normalizer.
SUBWAY_A_ROCKAWAY = Route(
    id="subway-a-rockaway",
    name="A 8 Avenue Express (Rockaway Park)",
    data_source="SUBWAY",
    line_codes=frozenset({"A"}),
    stations=(
        "SH15",
        "SH14",
        "SH13",
        "SH12",
        "SH04",
        "SH03",
        "SH02",
        "SH01",
        "SA61",
        "SA60",
        "SA59",
        "SA57",
        "SA55",
        "SA54",
        "SA53",
        "SA52",
        "SA51",
        "SA50",
        "SA49",
        "SA48",
        "SA47",
        "SA46",
        "SA45",
        "SA44",
        "SA43",
        "SA42",
        "SA41",
        "SA40",
        "SA38",
        "SA36",
        "SA34",
        "SA33",
        "SA32",
        "SA31",
        "SA30",
        "SA28",
        "SA27",
        "SA25",
        "SA24",
        "SA22",
        "SA21",
        "SA20",
        "SA19",
        "SA18",
        "SA17",
        "SA16",
        "SA15",
        "SA14",
        "SA12",
        "SA11",
        "SA10",
        "SA09",
        "SA07",
        "SA06",
        "SA05",
        "SA03",
        "SA02",
    ),
)

# A train Lefferts Blvd branch - diverges from the main A line at Rockaway Blvd
# (SA61). Without this route, segments SA61→SA63→SA64→SA65 are unresolved.
SUBWAY_A_LEFFERTS = Route(
    id="subway-a-lefferts",
    name="A 8 Avenue Express (Lefferts Blvd)",
    data_source="SUBWAY",
    line_codes=frozenset({"A"}),
    stations=(
        "SA65",
        "SA64",
        "SA63",
        "SA61",
        "SA60",
        "SA59",
        "SA57",
        "SA55",
        "SA54",
        "SA53",
        "SA52",
        "SA51",
        "SA50",
        "SA49",
        "SA48",
        "SA47",
        "SA46",
        "SA45",
        "SA44",
        "SA43",
        "SA42",
        "SA41",
        "SA40",
        "SA38",
        "SA36",
        "SA34",
        "SA33",
        "SA32",
        "SA31",
        "SA30",
        "SA28",
        "SA27",
        "SA25",
        "SA24",
        "SA22",
        "SA21",
        "SA20",
        "SA19",
        "SA18",
        "SA17",
        "SA16",
        "SA15",
        "SA14",
        "SA12",
        "SA11",
        "SA10",
        "SA09",
        "SA07",
        "SA06",
        "SA05",
        "SA03",
        "SA02",
    ),
)

SUBWAY_B = Route(
    id="subway-b",
    name="B 6 Avenue Express",
    data_source="SUBWAY",
    line_codes=frozenset({"B"}),
    stations=(
        "SD40",
        "SD39",
        "SD35",
        "SD31",
        "SD28",
        "SD26",
        "SD25",
        "SD24",
        "SR30",
        "SD22",
        "SD21",
        "SD20",
        "SD17",
        "SD16",
        "SD15",
        "SD14",
        "SA24",
        "SA22",
        "SA21",
        "SA20",
        "SA19",
        "SA18",
        "SA17",
        "SA16",
        "SA15",
        "SA14",
        "SD13",
        "SD12",
        "SD11",
        "SD10",
        "SD09",
        "SD08",
        "SD07",
        "SD06",
        "SD05",
        "SD04",
        "SD03",
    ),
)

SUBWAY_C = Route(
    id="subway-c",
    name="C 8 Avenue Local",
    data_source="SUBWAY",
    line_codes=frozenset({"C"}),
    stations=(
        "SA55",
        "SA54",
        "SA53",
        "SA52",
        "SA51",
        "SA50",
        "SA49",
        "SA48",
        "SA47",
        "SA46",
        "SA45",
        "SA44",
        "SA43",
        "SA42",
        "SA41",
        "SA40",
        "SA38",
        "SA36",
        "SA34",
        "SA33",
        "SA32",
        "SA31",
        "SA30",
        "SA28",
        "SA27",
        "SA25",
        "SA24",
        "SA22",
        "SA21",
        "SA20",
        "SA19",
        "SA18",
        "SA17",
        "SA16",
        "SA15",
        "SA14",
        "SA12",
        "SA11",
        "SA10",
        "SA09",
    ),
)

SUBWAY_D = Route(
    id="subway-d",
    name="D 6 Avenue Express",
    data_source="SUBWAY",
    line_codes=frozenset({"D"}),
    stations=(
        "SD43",
        "SB23",
        "SB22",
        "SB21",
        "SB20",
        "SB19",
        "SB18",
        "SB17",
        "SB16",
        "SB15",
        "SB14",
        "SB13",
        "SB12",
        "SR36",
        "SR35",
        "SR34",
        "SR33",
        "SR32",
        "SR31",
        "SR30",
        "SD22",
        "SD21",
        "SD20",
        "SD17",
        "SD16",
        "SD15",
        "SD14",
        "SA24",
        "SA15",
        "SD13",
        "SD12",
        "SD11",
        "SD10",
        "SD09",
        "SD08",
        "SD07",
        "SD06",
        "SD05",
        "SD04",
        "SD03",
        "SD01",
    ),
)

SUBWAY_E = Route(
    id="subway-e",
    name="E 8 Avenue Local",
    data_source="SUBWAY",
    line_codes=frozenset({"E"}),
    stations=(
        "SE01",
        "SA34",
        "SA33",
        "SA32",
        "SA31",
        "SA30",
        "SA28",
        "SA27",
        "SA25",
        "SD14",
        "SF12",
        "SF11",
        "SF09",
        "SG21",
        "SG20",
        "SG19",
        "SG18",
        "SG16",
        "SG15",
        "SG14",
        "SG13",
        "SG12",
        "SG11",
        "SG10",
        "SG09",
        "SG08",
        "SF07",
        "SF06",
        "SF05",
        "SG07",
        "SG06",
        "SG05",
    ),
)

SUBWAY_F = Route(
    id="subway-f",
    name="F Queens Blvd Express/6 Av Local",
    data_source="SUBWAY",
    line_codes=frozenset({"F"}),
    stations=(
        "SD43",
        "SD42",
        "SF39",
        "SF38",
        "SF36",
        "SF35",
        "SF34",
        "SF33",
        "SF32",
        "SF31",
        "SF30",
        "SF29",
        "SF27",
        "SF26",
        "SF25",
        "SF24",
        "SF23",
        "SF22",
        "SF21",
        "SF20",
        "SA41",
        "SF18",
        "SF16",
        "SF15",
        "SF14",
        "SD21",
        "SD20",
        "SD19",
        "SD18",
        "SD17",
        "SD16",
        "SD15",
        "SB10",
        "SB08",
        "SB06",
        "SB04",
        "SG20",
        "SG19",
        "SG18",
        "SG16",
        "SG15",
        "SG14",
        "SG13",
        "SG12",
        "SG11",
        "SG10",
        "SG09",
        "SG08",
        "SF07",
        "SF06",
        "SF05",
        "SF04",
        "SF03",
        "SF02",
        "SF01",
    ),
)

SUBWAY_FS = Route(
    id="subway-fs",
    name="S Franklin Avenue Shuttle",
    data_source="SUBWAY",
    line_codes=frozenset({"FS"}),
    stations=(
        "SD26",
        "SS04",
        "SS03",
        "SS01",
    ),
)

SUBWAY_F_EXPRESS = Route(
    id="subway-fx",
    name="FX Brooklyn F Express",
    data_source="SUBWAY",
    line_codes=frozenset({"FX"}),
    stations=(
        "SD43",
        "SD42",
        "SF39",
        "SF38",
        "SF36",
        "SF35",
        "SF34",
        "SF33",
        "SF32",
        "SF31",
        "SF30",
        "SF29",
        "SF27",
        "SF24",
        "SA41",
        "SF18",
        "SF16",
        "SF15",
        "SF14",
        "SD21",
        "SD20",
        "SD19",
        "SD18",
        "SD17",
        "SD16",
        "SD15",
        "SF12",
        "SF11",
        "SF09",
        "SG21",
        "SG14",
        "SG08",
        "SF07",
        "SF06",
        "SF05",
        "SF04",
        "SF03",
        "SF02",
        "SF01",
    ),
)

SUBWAY_G = Route(
    id="subway-g",
    name="G Brooklyn-Queens Crosstown",
    data_source="SUBWAY",
    line_codes=frozenset({"G"}),
    stations=(
        "SF27",
        "SF26",
        "SF25",
        "SF24",
        "SF23",
        "SF22",
        "SF21",
        "SF20",
        "SA42",
        "SG36",
        "SG35",
        "SG34",
        "SG33",
        "SG32",
        "SG31",
        "SG30",
        "SG29",
        "SG28",
        "SG26",
        "SG24",
        "SG22",
    ),
)

SUBWAY_GS = Route(
    id="subway-gs",
    name="S 42 St Shuttle",
    data_source="SUBWAY",
    line_codes=frozenset({"GS"}),
    stations=(
        "S901",
        "S902",
    ),
)

SUBWAY_H = Route(
    id="subway-h",
    name="S Rockaway Park Shuttle",
    data_source="SUBWAY",
    line_codes=frozenset({"H"}),
    stations=(
        "SH15",
        "SH14",
        "SH13",
        "SH12",
        "SH04",
    ),
)

SUBWAY_J = Route(
    id="subway-j",
    name="J Nassau St Local",
    data_source="SUBWAY",
    line_codes=frozenset({"J"}),
    stations=(
        "SM23",
        "SM22",
        "SM21",
        "SM20",
        "SM19",
        "SM18",
        "SM16",
        "SM14",
        "SM13",
        "SM12",
        "SM11",
        "SJ31",
        "SJ30",
        "SJ29",
        "SJ28",
        "SJ27",
        "SJ24",
        "SJ23",
        "SJ22",
        "SJ21",
        "SJ20",
        "SJ19",
        "SJ17",
        "SJ16",
        "SJ15",
        "SJ14",
        "SJ13",
        "SJ12",
        "SG06",
        "SG05",
    ),
)

SUBWAY_L = Route(
    id="subway-l",
    name="L 14 St-Canarsie Local",
    data_source="SUBWAY",
    line_codes=frozenset({"L"}),
    stations=(
        "SL29",
        "SL28",
        "SL27",
        "SL26",
        "SL25",
        "SL24",
        "SL22",
        "SL21",
        "SL20",
        "SL19",
        "SL17",
        "SL16",
        "SL15",
        "SL14",
        "SL13",
        "SL12",
        "SL11",
        "SL10",
        "SL08",
        "SL06",
        "SL05",
        "SL03",
        "SL02",
        "SL01",
    ),
)

SUBWAY_M = Route(
    id="subway-m",
    name="M Queens Blvd Local/6 Av Local",
    data_source="SUBWAY",
    line_codes=frozenset({"M"}),
    stations=(
        "SM01",
        "SM04",
        "SM05",
        "SM06",
        "SM08",
        "SM09",
        "SM10",
        "SM11",
        "SM12",
        "SM13",
        "SM14",
        "SM16",
        "SM18",
        # 6th Ave local segment (shared with B/D)
        "SD21",  # Broadway-Lafayette St
        "SD20",  # W 4 St-Wash Sq
        "SD19",  # 14 St
        "SD18",  # 23 St
        "SD17",  # 34 St-Herald Sq
        "SD16",  # 42 St-Bryant Pk
        "SD15",  # 47-50 Sts-Rockefeller Ctr
        "SD14",  # 7 Av
    ),
)

SUBWAY_N = Route(
    id="subway-n",
    name="N Broadway Local",
    data_source="SUBWAY",
    line_codes=frozenset({"N"}),
    stations=(
        "SD43",
        "SN10",
        "SN09",
        "SN08",
        "SN07",
        "SN06",
        "SN05",
        "SN04",
        "SN03",
        "SN02",
        "SR41",
        "SR40",
        "SR39",
        "SR36",
        "SR35",
        "SR34",
        "SR33",
        "SR32",
        "SR31",
        "SR30",
        "SR29",
        "SR28",
        "SR27",
        "SR26",
        "SR25",
        "SR24",
        "SR23",
        "SR22",
        "SR21",
        "SR20",
        "SR19",
        "SR18",
        "SR17",
        "SR16",
        "SR15",
        "SR14",
        "SR13",
        "SR11",
        "SR09",
        "SR08",
        "SR06",
        "SR05",
        "SR04",
        "SR03",
        "SR01",
    ),
)

SUBWAY_Q = Route(
    id="subway-q",
    name="Q Broadway Express",
    data_source="SUBWAY",
    line_codes=frozenset({"Q"}),
    stations=(
        "SD43",
        "SD42",
        "SD41",
        "SD40",
        "SD39",
        "SD38",
        "SD37",
        "SD35",
        "SD34",
        "SD33",
        "SD32",
        "SD31",
        "SD30",
        "SD29",
        "SD28",
        "SD27",
        "SD26",
        "SD25",
        "SD24",
        "SR30",
        "SQ01",
        "SR22",
        "SR21",
        "SR20",
        "SR19",
        "SR18",
        "SR17",
        "SR16",
        "SR15",
        "SR14",
        "SB08",
        "SQ03",
        "SQ04",
        "SQ05",
    ),
)

SUBWAY_R = Route(
    id="subway-r",
    name="R Broadway Local",
    data_source="SUBWAY",
    line_codes=frozenset({"R"}),
    stations=(
        "SR45",
        "SR44",
        "SR43",
        "SR42",
        "SR41",
        "SR40",
        "SR39",
        "SR36",
        "SR35",
        "SR34",
        "SR33",
        "SR32",
        "SR31",
        "SR30",
        "SR29",
        "SR28",
        "SR27",
        "SR26",
        "SR25",
        "SR24",
        "SR23",
        "SR22",
        "SR21",
        "SR20",
        "SR19",
        "SR18",
        "SR17",
        "SR16",
        "SR15",
        "SR14",
        "SR13",
        "SR11",
        "SG21",
        "SG20",
        "SG19",
        "SG18",
        "SG16",
        "SG15",
        "SG14",
        "SG13",
        "SG12",
        "SG11",
        "SG10",
        "SG09",
        "SG08",
    ),
)

SUBWAY_SI = Route(
    id="subway-si",
    name="SIR Staten Island Railway",
    data_source="SUBWAY",
    line_codes=frozenset({"SI"}),
    stations=(
        "SS09",
        "SS11",
        "SS13",
        "SS14",
        "SS15",
        "SS16",
        "SS17",
        "SS18",
        "SS19",
        "SS20",
        "SS21",
        "SS22",
        "SS23",
        "SS24",
        "SS25",
        "SS26",
        "SS27",
        "SS28",
        "SS29",
        "SS30",
        "SS31",
    ),
)

SUBWAY_W = Route(
    id="subway-w",
    name="W Broadway Local",
    data_source="SUBWAY",
    line_codes=frozenset({"W"}),
    stations=(
        "SN10",
        "SN09",
        "SN08",
        "SN07",
        "SN06",
        "SN05",
        "SN04",
        "SN03",
        "SN02",
        "SR41",
        "SR40",
        "SR39",
        "SR36",
        "SR35",
        "SR34",
        "SR33",
        "SR32",
        "SR31",
        "SR30",
        "SR29",
        "SR28",
        "SR27",
        "SR26",
        "SR25",
        "SR24",
        "SR23",
        "SR22",
        "SR21",
        "SR20",
        "SR19",
        "SR18",
        "SR17",
        "SR16",
        "SR15",
        "SR14",
        "SR13",
        "SR11",
        "SR09",
        "SR08",
        "SR06",
        "SR05",
        "SR04",
        "SR03",
        "SR01",
    ),
)

SUBWAY_Z = Route(
    id="subway-z",
    name="Z Nassau St Express",
    data_source="SUBWAY",
    line_codes=frozenset({"Z"}),
    stations=(
        "SM23",
        "SM22",
        "SM21",
        "SM20",
        "SM19",
        "SM18",
        "SM16",
        "SM11",
        "SJ30",
        "SJ28",
        "SJ27",
        "SJ24",
        "SJ23",
        "SJ21",
        "SJ20",
        "SJ17",
        "SJ15",
        "SJ14",
        "SJ12",
        "SG06",
        "SG05",
    ),
)


# =============================================================================
# METRA (Chicago) — 11 lines + 3 branch variants = 14 routes
# Station sequences imported from config/stations/metra.py to avoid duplication
# =============================================================================

METRA_BNSF = Route(
    id="metra-bnsf",
    name=METRA_ROUTES["BNSF"][1],
    data_source="METRA",
    line_codes=frozenset({"METRA-BNSF"}),
    stations=METRA_ROUTE_STATIONS["BNSF"],
)

METRA_HC = Route(
    id="metra-hc",
    name=METRA_ROUTES["HC"][1],
    data_source="METRA",
    line_codes=frozenset({"METRA-HC"}),
    stations=METRA_ROUTE_STATIONS["HC"],
)

METRA_MD_N = Route(
    id="metra-md-n",
    name=METRA_ROUTES["MD-N"][1],
    data_source="METRA",
    line_codes=frozenset({"METRA-MD-N"}),
    stations=METRA_ROUTE_STATIONS["MD-N"],
)

METRA_MD_W = Route(
    id="metra-md-w",
    name=METRA_ROUTES["MD-W"][1],
    data_source="METRA",
    line_codes=frozenset({"METRA-MD-W"}),
    stations=METRA_ROUTE_STATIONS["MD-W"],
)

METRA_NCS = Route(
    id="metra-ncs",
    name=METRA_ROUTES["NCS"][1],
    data_source="METRA",
    line_codes=frozenset({"METRA-NCS"}),
    stations=METRA_ROUTE_STATIONS["NCS"],
)

METRA_SWS = Route(
    id="metra-sws",
    name=METRA_ROUTES["SWS"][1],
    data_source="METRA",
    line_codes=frozenset({"METRA-SWS"}),
    stations=METRA_ROUTE_STATIONS["SWS"],
)

METRA_UP_N = Route(
    id="metra-up-n",
    name=METRA_ROUTES["UP-N"][1],
    data_source="METRA",
    line_codes=frozenset({"METRA-UP-N"}),
    stations=METRA_ROUTE_STATIONS["UP-N"],
)

METRA_UP_NW = Route(
    id="metra-up-nw",
    name=METRA_ROUTES["UP-NW"][1],
    data_source="METRA",
    line_codes=frozenset({"METRA-UP-NW"}),
    stations=METRA_ROUTE_STATIONS["UP-NW"],
)

METRA_UP_NW_MCHENRY = Route(
    id="metra-up-nw-mchenry",
    name="Union Pacific Northwest (McHenry)",
    data_source="METRA",
    line_codes=frozenset({"METRA-UP-NW"}),
    stations=METRA_ROUTE_STATIONS["UP-NW-MCHENRY"],
)

METRA_UP_W = Route(
    id="metra-up-w",
    name=METRA_ROUTES["UP-W"][1],
    data_source="METRA",
    line_codes=frozenset({"METRA-UP-W"}),
    stations=METRA_ROUTE_STATIONS["UP-W"],
)

METRA_RI = Route(
    id="metra-ri",
    name=METRA_ROUTES["RI"][1],
    data_source="METRA",
    line_codes=frozenset({"METRA-RI"}),
    stations=METRA_ROUTE_STATIONS["RI"],
)

METRA_ME = Route(
    id="metra-me",
    name=METRA_ROUTES["ME"][1],
    data_source="METRA",
    line_codes=frozenset({"METRA-ME"}),
    stations=METRA_ROUTE_STATIONS["ME"],
)

METRA_ME_BI = Route(
    id="metra-me-bi",
    name="Metra Electric (Blue Island)",
    data_source="METRA",
    line_codes=frozenset({"METRA-ME"}),
    stations=METRA_ROUTE_STATIONS["ME-BI"],
)

METRA_ME_SC = Route(
    id="metra-me-sc",
    name="Metra Electric (South Chicago)",
    data_source="METRA",
    line_codes=frozenset({"METRA-ME"}),
    stations=METRA_ROUTE_STATIONS["ME-SC"],
)


# =============================================================================
# WMATA (Washington DC Metro)
# =============================================================================

WMATA_RED = Route(
    id="wmata-red",
    name="Red Line",
    data_source="WMATA",
    line_codes=frozenset({"RD"}),
    stations=(
        "A15",
        "A14",
        "A13",
        "A12",
        "A11",
        "A10",
        "A09",
        "A08",
        "A07",
        "A06",
        "A05",
        "A04",
        "A03",
        "A02",
        "A01",
        "B35",
        "B01",
        "B02",
        "B03",
        "B04",
        "B05",
        "B06",
        "B07",
        "B08",
        "B09",
        "B10",
        "B11",
    ),
)

WMATA_ORANGE = Route(
    id="wmata-orange",
    name="Orange Line",
    data_source="WMATA",
    line_codes=frozenset({"OR"}),
    stations=(
        "K08",
        "K07",
        "K06",
        "K05",
        "K04",
        "K03",
        "K02",
        "K01",
        "C05",
        "C04",
        "C03",
        "C02",
        "C01",
        "D01",
        "D02",
        "D03",
        "D04",
        "D05",
        "D06",
        "D07",
        "D08",
        "D09",
        "D10",
        "D11",
        "D12",
        "D13",
    ),
)

WMATA_SILVER = Route(
    id="wmata-silver",
    name="Silver Line",
    data_source="WMATA",
    line_codes=frozenset({"SV"}),
    stations=(
        "N12",
        "N11",
        "N10",
        "N09",
        "N08",
        "N07",
        "N06",
        "N04",
        "N03",
        "N02",
        "N01",
        "K05",
        "K04",
        "K03",
        "K02",
        "K01",
        "C05",
        "C04",
        "C03",
        "C02",
        "C01",
        "D01",
        "D02",
        "D03",
        "D04",
        "D05",
        "D06",
        "D07",
        "D08",
        "G01",
        "G02",
        "G03",
        "G04",
        "G05",
    ),
)

WMATA_BLUE = Route(
    id="wmata-blue",
    name="Blue Line",
    data_source="WMATA",
    line_codes=frozenset({"BL"}),
    stations=(
        "J03",
        "J02",
        "C13",
        "C12",
        "C11",
        "C10",
        "C09",
        "C08",
        "C07",
        "C06",
        "C05",
        "C04",
        "C03",
        "C02",
        "C01",
        "D01",
        "D02",
        "D03",
        "D04",
        "D05",
        "D06",
        "D07",
        "D08",
        "G01",
        "G02",
        "G03",
        "G04",
        "G05",
    ),
)

WMATA_YELLOW = Route(
    id="wmata-yellow",
    name="Yellow Line",
    data_source="WMATA",
    line_codes=frozenset({"YL"}),
    stations=(
        "C15",
        "C14",
        "C13",
        "C12",
        "C11",
        "C10",
        "C09",
        "C08",
        "C07",
        "F03",
        "F02",
        "F01",
        "E01",
        "E02",
        "E03",
        "E04",
        "E05",
        "E06",
    ),
)

WMATA_GREEN = Route(
    id="wmata-green",
    name="Green Line",
    data_source="WMATA",
    line_codes=frozenset({"GR"}),
    stations=(
        "F11",
        "F10",
        "F09",
        "F08",
        "F07",
        "F06",
        "F05",
        "F04",
        "F03",
        "F02",
        "F01",
        "E01",
        "E02",
        "E03",
        "E04",
        "E05",
        "E06",
        "E07",
        "E08",
        "E09",
        "E10",
    ),
)


# =============================================================================
# BART ROUTES
# =============================================================================

BART_RED = Route(
    id="bart-red",
    name="Richmond - SFO/Millbrae",
    data_source="BART",
    line_codes=frozenset({"BART-RED"}),
    stations=(
        "BART_RICH",
        "BART_DELN",
        "BART_PLZA",
        "BART_NBRK",
        "BART_DBRK",
        "BART_ASHB",
        "BART_MCAR",
        "BART_19TH",
        "BART_12TH",
        "BART_WOAK",
        "BART_EMBR",
        "BART_MONT",
        "BART_POWL",
        "BART_CIVC",
        "BART_16TH",
        "BART_24TH",
        "BART_GLEN",
        "BART_BALB",
        "BART_DALY",
        "BART_COLM",
        "BART_SSAN",
        "BART_SBRN",
        "BART_MLBR",
        "BART_SFIA",
    ),
)

BART_ORANGE = Route(
    id="bart-orange",
    name="Berryessa - Richmond",
    data_source="BART",
    line_codes=frozenset({"BART-ORG"}),
    stations=(
        "BART_BERY",
        "BART_MLPT",
        "BART_WARM",
        "BART_FRMT",
        "BART_UCTY",
        "BART_SHAY",
        "BART_HAYW",
        "BART_BAYF",
        "BART_SANL",
        "BART_COLS",
        "BART_FTVL",
        "BART_LAKE",
        "BART_12TH",
        "BART_19TH",
        "BART_MCAR",
        "BART_ASHB",
        "BART_DBRK",
        "BART_NBRK",
        "BART_PLZA",
        "BART_DELN",
        "BART_RICH",
    ),
)

BART_YELLOW = Route(
    id="bart-yellow",
    name="Antioch - SFO/Millbrae",
    data_source="BART",
    line_codes=frozenset({"BART-YEL"}),
    stations=(
        "BART_ANTC",
        "BART_PCTR",
        "BART_PITT",
        "BART_NCON",
        "BART_CONC",
        "BART_PHIL",
        "BART_WCRK",
        "BART_LAFY",
        "BART_ORIN",
        "BART_ROCK",
        "BART_MCAR",
        "BART_19TH",
        "BART_12TH",
        "BART_WOAK",
        "BART_EMBR",
        "BART_MONT",
        "BART_POWL",
        "BART_CIVC",
        "BART_16TH",
        "BART_24TH",
        "BART_GLEN",
        "BART_BALB",
        "BART_DALY",
        "BART_COLM",
        "BART_SSAN",
        "BART_SBRN",
        "BART_MLBR",
        "BART_SFIA",
    ),
)

BART_GREEN = Route(
    id="bart-green",
    name="Berryessa - Daly City",
    data_source="BART",
    line_codes=frozenset({"BART-GRN"}),
    stations=(
        "BART_BERY",
        "BART_MLPT",
        "BART_WARM",
        "BART_FRMT",
        "BART_UCTY",
        "BART_SHAY",
        "BART_HAYW",
        "BART_BAYF",
        "BART_SANL",
        "BART_COLS",
        "BART_FTVL",
        "BART_LAKE",
        "BART_WOAK",
        "BART_EMBR",
        "BART_MONT",
        "BART_POWL",
        "BART_CIVC",
        "BART_16TH",
        "BART_24TH",
        "BART_GLEN",
        "BART_BALB",
        "BART_DALY",
    ),
)

BART_BLUE = Route(
    id="bart-blue",
    name="Dublin/Pleasanton - Daly City",
    data_source="BART",
    line_codes=frozenset({"BART-BLU"}),
    stations=(
        "BART_DUBL",
        "BART_WDUB",
        "BART_CAST",
        "BART_BAYF",
        "BART_SANL",
        "BART_COLS",
        "BART_FTVL",
        "BART_LAKE",
        "BART_12TH",
        "BART_19TH",
        "BART_MCAR",
        "BART_WOAK",
        "BART_EMBR",
        "BART_MONT",
        "BART_POWL",
        "BART_CIVC",
        "BART_16TH",
        "BART_24TH",
        "BART_GLEN",
        "BART_BALB",
        "BART_DALY",
    ),
)

BART_OAK = Route(
    id="bart-oak",
    name="Oakland Airport - Coliseum",
    data_source="BART",
    line_codes=frozenset({"BART-OAK"}),
    stations=(
        "BART_COLS",
        "BART_OAKL",
    ),
)


# ============================================================================
# MBTA Commuter Rail routes
# ============================================================================

MBTA_FAIRMOUNT = Route(
    id="mbta-fairmount",
    name="Fairmount Line",
    data_source="MBTA",
    line_codes=frozenset({"MBTA-FA"}),
    stations=(
        "BOS",
        "BNMK",
        "BUPH",
        "BFCG",
        "BTLB",
        "BMRT",
        "BBHA",
        "BFMT",
        "BRDV",
    ),
)

MBTA_FITCHBURG = Route(
    id="mbta-fitchburg",
    name="Fitchburg Line",
    data_source="MBTA",
    line_codes=frozenset({"MBTA-FI"}),
    stations=(
        "BNST",
        "BPOR",
        "BBMT",
        "BWAV",
        "BWTH",
        "BBNR",
        "BKGN",
        "BHST",
        "BSLH",
        "BLIN",
        "BCON",
        "BWCN",
        "BSAC",
        "BLIT",
        "BAYE",
        "BSHR",
        "BNLM",
        "BFIT",
        "BWAC",
    ),
)

MBTA_FOXBORO = Route(
    id="mbta-foxboro",
    name="Foxboro Event Service",
    data_source="MBTA",
    line_codes=frozenset({"MBTA-FX"}),
    stations=("BOS", "BBY", "BDCC", "BFOX"),
)

MBTA_FRANKLIN = Route(
    id="mbta-franklin",
    name="Franklin/Foxboro Line",
    data_source="MBTA",
    line_codes=frozenset({"MBTA-FR"}),
    stations=(
        "BOS",
        "BBY",
        "BRUG",
        "BFHL",
        "BHPK",
        "BRDV",
        "BEND",
        "BDCC",
        "BISL",
        "BNWD",
        "BNWC",
        "BWDG",
        "BPLM",
        "BWAL",
        "BNFK",
        "BFRK",
        "BFPK",
    ),
)

MBTA_GREENBUSH = Route(
    id="mbta-greenbush",
    name="Greenbush Line",
    data_source="MBTA",
    line_codes=frozenset({"MBTA-GR"}),
    stations=(
        "BOS",
        "BJFK",
        "BQNC",
        "BBRN",
        "BWLE",
        "BEWY",
        "BWHI",
        "BNAN",
        "BCOH",
        "BNSC",
        "BGRB",
    ),
)

MBTA_HAVERHILL = Route(
    id="mbta-haverhill",
    name="Haverhill Line",
    data_source="MBTA",
    line_codes=frozenset({"MBTA-HA"}),
    stations=(
        "BNST",
        "BMAL",
        "BOKG",
        "BWYH",
        "BMCP",
        "BMHG",
        "BGNW",
        "BWAK",
        "BRDG",
        "BNWI",
        "BBVL",
        "BAND",
        "BLAW",
        "BBRD",
        "BHAV",
    ),
)

MBTA_KINGSTON = Route(
    id="mbta-kingston",
    name="Kingston Line",
    data_source="MBTA",
    line_codes=frozenset({"MBTA-KN"}),
    stations=(
        "BOS",
        "BJFK",
        "BQNC",
        "BBRN",
        "BSWY",
        "BABI",
        "BWHT",
        "BHAN",
        "BHLX",
        "BKNG",
        "BPLY",
    ),
)

MBTA_LOWELL = Route(
    id="mbta-lowell",
    name="Lowell Line",
    data_source="MBTA",
    line_codes=frozenset({"MBTA-LO"}),
    stations=(
        "BNST",
        "BWMF",
        "BWDM",
        "BWNC",
        "BMSH",
        "BAWB",
        "BWLM",
        "BNBL",
        "BLOW",
    ),
)

MBTA_NEEDHAM = Route(
    id="mbta-needham",
    name="Needham Line",
    data_source="MBTA",
    line_codes=frozenset({"MBTA-NE"}),
    stations=(
        "BOS",
        "BBY",
        "BRUG",
        "BFHL",
        "BRSV",
        "BBLV",
        "BHLD",
        "BWRX",
        "BHRS",
        "BNJN",
        "BNDC",
        "BNDH",
    ),
)

MBTA_NEWBEDFORD = Route(
    id="mbta-newbedford",
    name="Fall River/New Bedford Line",
    data_source="MBTA",
    line_codes=frozenset({"MBTA-NB"}),
    stations=(
        "BOS",
        "BJFK",
        "BQNC",
        "BBRN",
        "BHLR",
        "BMTL",
        "BBRO",
        "BCMP",
        "BBDG",
        "BMID",
        "BETN",
        "BFTW",
        "BFRD",
        "BCST",
        "BNBD",
    ),
)

MBTA_NEWBURYPORT = Route(
    id="mbta-newburyport",
    name="Newburyport Branch",
    data_source="MBTA",
    line_codes=frozenset({"MBTA-NP"}),
    stations=(
        "BNST",
        "BCHE",
        "BRWK",
        "BLNI",
        "BSWP",
        "BSLM",
        "BBEV",
        "BNBV",
        "BHWN",
        "BIPS",
        "BROW",
        "BNBP",
    ),
)

MBTA_ROCKPORT = Route(
    id="mbta-rockport",
    name="Rockport Branch",
    data_source="MBTA",
    line_codes=frozenset({"MBTA-NP"}),  # Same line code as Newburyport (shared trunk)
    stations=(
        "BNST",
        "BCHE",
        "BRWK",
        "BLNI",
        "BSWP",
        "BSLM",
        "BBEV",
        "BMTS",
        "BPRC",
        "BBFM",
        "BMCH",
        "BWGL",
        "BGLO",
        "BRPT",
    ),
)

MBTA_PROVIDENCE = Route(
    id="mbta-providence",
    name="Providence/Stoughton Line",
    data_source="MBTA",
    line_codes=frozenset({"MBTA-PV"}),
    stations=(
        "BOS",
        "BBY",
        "BRUG",
        "BFHL",
        "BHPK",
        "BRDV",
        "RTE",
        "BCJN",
        "BSHA",
        "BMAN",
        "BATT",
        "BSAT",
        "BPCF",
        "PVD",
        "BTFG",
        "BWKF",
    ),
)

MBTA_STOUGHTON = Route(
    id="mbta-stoughton",
    name="Stoughton Branch",
    data_source="MBTA",
    line_codes=frozenset({"MBTA-PV"}),  # Same line code as Providence (shared trunk)
    stations=(
        "BOS",
        "BBY",
        "BRUG",
        "BFHL",
        "BHPK",
        "BRDV",
        "RTE",
        "BCJN",
        "BCNC",
        "BSTO",
    ),
)

MBTA_WORCESTER = Route(
    id="mbta-worcester",
    name="Framingham/Worcester Line",
    data_source="MBTA",
    line_codes=frozenset({"MBTA-WR"}),
    stations=(
        "BOS",
        "BBY",
        "BLDN",
        "BBLN",
        "BNVL",
        "BWNT",
        "BAUB",
        "BWFM",
        "BWHL",
        "BWSQ",
        "BNTC",
        "BWNA",
        "BFRM",
        "BASH",
        "BSBO",
        "BWSB",
        "BGRF",
        "WOR",
    ),
)

MBTA_MIDDLEBOROUGH = Route(
    id="mbta-middleborough",
    name="Middleborough/Lakeville Line",
    data_source="MBTA",
    line_codes=frozenset({"MBTA-MI"}),
    stations=(
        "BOS",
        "BJFK",
        "BQNC",
        "BBRN",
        "BHLR",
        "BMTL",
        "BBRO",
        "BCMP",
        "BBDG",
        "BLKV",
        "BMID",
    ),
)

MBTA_CAPEFLYER = Route(
    id="mbta-capeflyer",
    name="CapeFLYER",
    data_source="MBTA",
    line_codes=frozenset({"MBTA-CF"}),
    stations=("BOS", "BBRN", "BBRO", "BLKV", "BWRV", "BBZB", "BBNE", "BHYN"),
)

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
    AMTRAK_CAPITOL_CORRIDOR,
    AMTRAK_HIAWATHA,
    AMTRAK_LINCOLN,
    AMTRAK_SAN_JOAQUINS_SAC,
    AMTRAK_SAN_JOAQUINS_OAK,
    AMTRAK_WOLVERINE,
    AMTRAK_DOWNEASTER,
    AMTRAK_PIEDMONT,
    AMTRAK_VERMONTER,
    AMTRAK_ETHAN_ALLEN,
    AMTRAK_ADIRONDACK,
    AMTRAK_PALMETTO,
    AMTRAK_CARDINAL,
    AMTRAK_EMPIRE_BUILDER_PDX,
    AMTRAK_PERE_MARQUETTE,
    AMTRAK_BLUE_WATER,
    AMTRAK_ILLINOIS_ZEPHYR,
    AMTRAK_AUTO_TRAIN,
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
    LIRR_PORT_WASHINGTON_GCT,
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
    # Subway
    SUBWAY_1,
    SUBWAY_2,
    SUBWAY_3,
    SUBWAY_4,
    SUBWAY_5,
    SUBWAY_6,
    SUBWAY_6_EXPRESS,
    SUBWAY_7,
    SUBWAY_7_EXPRESS,
    SUBWAY_A_ROCKAWAY,
    SUBWAY_A_LEFFERTS,
    SUBWAY_A,
    SUBWAY_B,
    SUBWAY_C,
    SUBWAY_D,
    SUBWAY_E,
    SUBWAY_F,
    SUBWAY_F_EXPRESS,
    SUBWAY_FS,
    SUBWAY_G,
    SUBWAY_GS,
    SUBWAY_H,
    SUBWAY_J,
    SUBWAY_L,
    SUBWAY_M,
    SUBWAY_N,
    SUBWAY_Q,
    SUBWAY_R,
    SUBWAY_W,
    SUBWAY_SI,
    SUBWAY_Z,
    # Metra
    METRA_BNSF,
    METRA_HC,
    METRA_MD_N,
    METRA_MD_W,
    METRA_NCS,
    METRA_SWS,
    METRA_UP_N,
    METRA_UP_NW,
    METRA_UP_NW_MCHENRY,
    METRA_UP_W,
    METRA_RI,
    METRA_ME,
    METRA_ME_BI,
    METRA_ME_SC,
    # WMATA
    WMATA_RED,
    WMATA_ORANGE,
    WMATA_SILVER,
    WMATA_BLUE,
    WMATA_YELLOW,
    WMATA_GREEN,
    # BART
    BART_RED,
    BART_ORANGE,
    BART_YELLOW,
    BART_GREEN,
    BART_BLUE,
    BART_OAK,
    # MBTA Commuter Rail
    MBTA_FAIRMOUNT,
    MBTA_FITCHBURG,
    MBTA_FOXBORO,
    MBTA_FRANKLIN,
    MBTA_GREENBUSH,
    MBTA_HAVERHILL,
    MBTA_KINGSTON,
    MBTA_LOWELL,
    MBTA_NEEDHAM,
    MBTA_MIDDLEBOROUGH,
    MBTA_NEWBEDFORD,
    MBTA_NEWBURYPORT,
    MBTA_ROCKPORT,
    MBTA_PROVIDENCE,
    MBTA_STOUGHTON,
    MBTA_WORCESTER,
    MBTA_CAPEFLYER,
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


def _resolve_to_topology_code(station_code: str, data_source: str) -> str:
    """Resolve a station code to the code used in route topology via equivalences.

    For example, TS (Secaucus Lower Lvl) resolves to SE (Secaucus Upper Lvl)
    because SE is the code used in route definitions.
    """
    from trackrat.config.stations.common import STATION_EQUIVALENTS

    group = STATION_EQUIVALENTS.get(station_code)
    if not group:
        return station_code

    # If the original code already exists in a route, keep it
    routes = get_routes_for_data_source(data_source)
    for route in routes:
        if station_code in route._station_set:
            return station_code

    # Only resolve to an equivalent if the original is not in any route
    for code in group:
        if code == station_code:
            continue
        for route in routes:
            if code in route._station_set:
                return code
    return station_code


def _resolve_cross_route_chain(
    data_source: str,
    from_station: str,
    to_station: str,
    max_hops: int = 4,
) -> list[tuple[str, str]] | None:
    """
    Find a chain of routes connecting from_station to to_station via
    shared junction stations (stations that appear on 2+ routes).

    Uses BFS to find the shortest chain. Returns the concatenated
    canonical segment pairs, or None if no chain exists.

    Example: NY→CLT via AMTRAK_NEC (NY→WS) + AMTRAK_SOUTHEAST (WS→CLT)
    returns [(NY,NP),(NP,MP),...,(NCR,WS),(WS,ALX),...,(RGH,CLT)].
    """
    routes = get_routes_for_data_source(data_source)
    if not routes:
        return None

    # Build station→routes index for fast lookup
    station_routes: dict[str, list[Route]] = defaultdict(list)
    for route in routes:
        for station in route.stations:
            station_routes[station].append(route)

    # Quick check: both stations must be in at least one route
    if from_station not in station_routes or to_station not in station_routes:
        return None

    # Identify junction stations (on 2+ routes) — these are the only
    # useful transfer points. Also include from/to themselves.
    junctions = {
        s for s, r_list in station_routes.items() if len(r_list) >= 2
    }
    junctions.add(from_station)
    junctions.add(to_station)

    # BFS: (current_station, segments_so_far, routes_used)
    queue: deque[tuple[str, list[tuple[str, str]], frozenset[str]]] = deque()

    # Seed with all routes containing from_station
    visited: set[str] = {from_station}
    for route in station_routes[from_station]:
        # Check if this route directly reaches to_station
        if to_station in route._station_set:
            expansion = route.expand_to_canonical_segments(from_station, to_station)
            if expansion:
                return expansion  # Single-route path found (shouldn't happen if caller checked)

        # Expand to each junction reachable on this route
        for junction in junctions:
            if junction == from_station or junction not in route._station_set:
                continue
            expansion = route.expand_to_canonical_segments(from_station, junction)
            if expansion:
                queue.append((junction, expansion, frozenset({route.id})))

    best: list[tuple[str, str]] | None = None

    while queue:
        current, segments, used_routes = queue.popleft()

        # Prune: too many hops or already found a shorter path
        if len(used_routes) >= max_hops:
            continue
        if best is not None and len(segments) >= len(best):
            continue

        if current in visited and current != from_station:
            # Allow revisiting from_station (seeded above) but skip others
            continue
        visited.add(current)

        for route in station_routes[current]:
            if route.id in used_routes:
                continue

            # Check if this route reaches to_station
            if to_station in route._station_set:
                expansion = route.expand_to_canonical_segments(current, to_station)
                if expansion:
                    candidate = segments + expansion
                    if best is None or len(candidate) < len(best):
                        best = candidate
                continue

            # Otherwise chain through junctions on this route
            next_used = used_routes | frozenset({route.id})
            if len(next_used) >= max_hops:
                continue
            for junction in junctions:
                if junction == current or junction in visited:
                    continue
                if junction not in route._station_set:
                    continue
                expansion = route.expand_to_canonical_segments(current, junction)
                if expansion:
                    queue.append((junction, segments + expansion, next_used))

    return best


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

    When multiple routes contain the same segment, prefers the route
    with the fewest intermediate stations (shortest expansion). This
    prevents e.g. Raritan Valley NP→EZ from being misattributed to
    NEC's NP→NA→NZ→EZ path through Newark Airport.

    Station codes are resolved through equivalence groups before lookup,
    so e.g. TS (Secaucus Lower Lvl) is treated as SE (Secaucus Upper Lvl)
    which appears in route definitions.

    If no matching route is found, returns the original segment as-is.

    Args:
        data_source: The transit system (NJT, PATH, etc.)
        from_station: Starting station code
        to_station: Ending station code
        line_code: Optional line code for more precise route matching

    Returns:
        List of (from_station, to_station) tuples representing canonical segments
    """
    # Resolve station codes to the canonical codes used in route topology
    resolved_from = _resolve_to_topology_code(from_station, data_source)
    resolved_to = _resolve_to_topology_code(to_station, data_source)

    # If line_code is provided, use direct lookup first
    if line_code:
        route = get_route_by_line_code(data_source, line_code)
        if route and route.contains_segment(resolved_from, resolved_to):
            canonical = route.expand_to_canonical_segments(resolved_from, resolved_to)
            if canonical:
                return canonical

    # Find the route with the fewest intermediate stations (shortest expansion).
    # This ensures skip-stop segments are attributed to the correct line.
    best_canonical: list[tuple[str, str]] | None = None
    for route in get_routes_for_data_source(data_source):
        if not route.contains_segment(resolved_from, resolved_to):
            continue
        canonical = route.expand_to_canonical_segments(resolved_from, resolved_to)
        if canonical is None:
            continue
        if best_canonical is None or len(canonical) < len(best_canonical):
            best_canonical = canonical
            # Can't do better than a direct consecutive pair
            if len(canonical) == 1:
                break

    if best_canonical is not None:
        return best_canonical

    # No single route contains both stations — try chaining through
    # shared junction stations (e.g. NY→CLT via NEC NY→WS + Southeast WS→CLT).
    # Only enabled for AMTRAK where routes represent segments of longer train
    # paths that a single service chains through. Other providers (LIRR, MNR,
    # Subway, etc.) use routes for distinct branches that trains don't cross.
    if data_source == "AMTRAK":
        chain = _resolve_cross_route_chain(data_source, resolved_from, resolved_to)
        if chain is not None:
            return chain

    # No matching route or chain - return segment as-is
    return [(from_station, to_station)]
