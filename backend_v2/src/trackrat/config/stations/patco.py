"""PATCO Speedline station configuration."""

# PATCO station names
PATCO_STATION_NAMES: dict[str, str] = {
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
}


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
