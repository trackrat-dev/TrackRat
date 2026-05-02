"""
Station-specific configurations for track predictions.

This module defines which stations support track predictions and their track configurations.
"""

from typing import Any

# Station configurations for track predictions
# Note: Stations with platform_mappings group adjacent tracks sharing an island platform.
# Currently NY (Penn Station) and GCT (Grand Central) have platform groupings.
STATION_PREDICTION_CONFIGS = {
    "NY": {
        "predictions_enabled": True,
        "tracks": [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
            "11",
            "12",
            "13",
            "14",
            "15",
            "16",
            "17",
            "18",
            "19",
            "20",
            "21",
        ],
        "platform_mappings": {
            "1": "1 & 2",
            "2": "1 & 2",
            "3": "3 & 4",
            "4": "3 & 4",
            "5": "5 & 6",
            "6": "5 & 6",
            "7": "7 & 8",
            "8": "7 & 8",
            "9": "9 & 10",
            "10": "9 & 10",
            "11": "11 & 12",
            "12": "11 & 12",
            "13": "13 & 14",
            "14": "13 & 14",
            "15": "15 & 16",
            "16": "15 & 16",
            "17": "17",
            "18": "18 & 19",
            "19": "18 & 19",
            "20": "20 & 21",
            "21": "20 & 21",
        },
    },
    "NP": {  # Newark Penn - 761 records
        "predictions_enabled": True,
        "tracks": ["1", "2", "3", "4", "5", "A"],
        "platform_mappings": None,  # Track = Platform
    },
    "ND": {  # 565 records
        "predictions_enabled": True,
        "tracks": ["1", "2", "3"],
        "platform_mappings": None,
    },
    "HB": {  # Hoboken - 389 records
        "predictions_enabled": True,
        "tracks": [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
            "11",
            "12",
            "13",
            "14",
            "15",
            "16",
            "17",
        ],
        "platform_mappings": None,
    },
    "MP": {  # Metropark - 369 records
        "predictions_enabled": True,
        "tracks": ["1", "4"],
        "platform_mappings": None,
    },
    "ST": {  # 349 records
        "predictions_enabled": True,
        "tracks": ["0", "1", "2", "W"],
        "platform_mappings": None,
    },
    "TR": {  # Trenton - 338 records
        "predictions_enabled": True,
        "tracks": ["1", "2", "4", "5"],
        "platform_mappings": None,
    },
    "PH": {  # Princeton/Philadelphia? - 275 records
        "predictions_enabled": True,
        "tracks": ["2", "3", "4", "5", "6", "7", "9"],
        "platform_mappings": None,
    },
    "DV": {  # 249 records
        "predictions_enabled": True,
        "tracks": ["1", "2", "Sing+"],
        "platform_mappings": None,
    },
    "DN": {  # 137 records
        "predictions_enabled": True,
        "tracks": ["1", "2"],
        "platform_mappings": None,
    },
    "PL": {  # 132 records
        "predictions_enabled": True,
        "tracks": ["1", "2"],
        "platform_mappings": None,
    },
    "LB": {  # 118 records
        "predictions_enabled": True,
        "tracks": ["1", "2"],
        "platform_mappings": None,
    },
    "JA": {  # Jersey Avenue (NJT) - 113 records
        "predictions_enabled": True,
        "tracks": ["1", "2"],
        "platform_mappings": None,
    },
    "JAM": {  # Jamaica (LIRR) - busiest junction in the system
        "predictions_enabled": True,
        "tracks": ["2", "6", "7", "8", "11", "12"],
        "platform_mappings": None,
    },
    "GCT": {  # Grand Central - MNR Terminal (tracks 13-114) + LIRR Madison (tracks 201-304)
        "predictions_enabled": True,
        "tracks": [
            # MNR Grand Central Terminal
            "13",
            "15",
            "16",
            "18",
            "19",
            "20",
            "23",
            "24",
            "25",
            "28",
            "32",
            "33",
            "35",
            "36",
            "37",
            "38",
            "39",
            "42",
            "102",
            "103",
            "104",
            "106",
            "107",
            "111",
            "112",
            "114",
            # LIRR Grand Central Madison
            "201",
            "202",
            "204",
            "301",
            "302",
            "304",
        ],
        "platform_mappings": {
            # Upper Level - island platform pairs
            "11": "11 & 13",
            "13": "11 & 13",
            "14": "14 & 15",
            "15": "14 & 15",
            "16": "16 & 17",
            "17": "16 & 17",
            "18": "18 & 19",
            "19": "18 & 19",
            "20": "20 & 21",
            "21": "20 & 21",
            "23": "23 & 24",
            "24": "23 & 24",
            "25": "25 & 26",
            "26": "25 & 26",
            "27": "27 & 28",
            "28": "27 & 28",
            "29": "29 & 30",
            "30": "29 & 30",
            "32": "32 & 33",
            "33": "32 & 33",
            "34": "34 & 35",
            "35": "34 & 35",
            "36": "36 & 37",
            "37": "36 & 37",
            "38": "38",
            "39": "39 & 40",
            "40": "39 & 40",
            "41": "41 & 42",
            "42": "41 & 42",
            # Lower Level - island platform pairs
            "102": "102 & 103",
            "103": "102 & 103",
            "104": "104 & 105",
            "105": "104 & 105",
            "106": "106 & 107",
            "107": "106 & 107",
            "111": "111 & 112",
            "112": "111 & 112",
            "113": "113 & 114",
            "114": "113 & 114",
            # LIRR Madison tracks - no platform grouping data
        },
    },
    # Default configuration for stations not explicitly listed
    "_default": {
        "predictions_enabled": False,
        "tracks": [],
        "platform_mappings": None,
    },
}


def get_station_config(station_code: str) -> dict[str, Any]:
    """
    Get prediction configuration for a station.

    Args:
        station_code: Station code (e.g., 'NY', 'NP')

    Returns:
        Dictionary with station configuration
    """
    return STATION_PREDICTION_CONFIGS.get(
        station_code, STATION_PREDICTION_CONFIGS["_default"]
    )


def station_has_predictions(station_code: str) -> bool:
    """Check if station has track predictions enabled."""
    config = get_station_config(station_code)
    return bool(config["predictions_enabled"])


def get_platform_for_track(station_code: str, track: str) -> str:
    """
    Get platform name for a given track at a station.

    Args:
        station_code: Station code (e.g., 'NY', 'NP')
        track: Track identifier (e.g., '1', 'A')

    Returns:
        Platform name (may be same as track for stations without platform mappings)
    """
    config = get_station_config(station_code)

    if config["platform_mappings"]:
        return str(config["platform_mappings"].get(track, track))
    else:
        # For stations without platform mappings, platform = track
        return track


def get_tracks_for_station(station_code: str) -> list[str]:
    """
    Get list of valid tracks for a station.

    Args:
        station_code: Station code (e.g., 'NY', 'NP')

    Returns:
        List of track identifiers
    """
    config = get_station_config(station_code)
    return list(config.get("tracks", []))


def get_prediction_enabled_stations() -> list[str]:
    """Get list of all stations with track predictions enabled."""
    return [
        code
        for code, config in STATION_PREDICTION_CONFIGS.items()
        if code != "_default" and config.get("predictions_enabled", False)
    ]


def get_valid_tracks(station_code: str, data_source: str) -> frozenset[str] | None:
    """Return the full set of valid tracks for a (station, data_source), or None.

    Distinct from the per-station ``tracks`` lists above, which enumerate tracks
    with enough historical coverage to *predict*. This set enumerates every
    *legal* track so that clearly bogus feed values (e.g., LIRR reporting track
    "1" at Grand Central Madison) can be rejected before they reach users.

    Returns ``None`` when the (station, data_source) pair has no configured
    validation set, so callers pass the value through unchanged. We enable
    validation only where we can fully enumerate the tracks — partial lists
    would false-reject legitimate tracks.

    Args:
        station_code: Station code (e.g., 'GCT').
        data_source: Transit system (e.g., 'LIRR', 'MNR', 'SUBWAY').

    Returns:
        frozenset of valid track strings, or None if not configured.
    """
    return VALIDATED_TRACKS.get((station_code, data_source))


# Explicit, complete track sets for validation at the feed-ingest boundary.
# Only add a (station, data_source) entry when the list is exhaustive —
# partial lists cause false rejections of legitimate tracks.
VALIDATED_TRACKS: dict[tuple[str, str], frozenset[str]] = {
    # Grand Central Madison — LIRR terminal on three levels, 4 tracks per level.
    ("GCT", "LIRR"): frozenset(
        {
            "201",
            "202",
            "203",
            "204",
            "301",
            "302",
            "303",
            "304",
            "401",
            "402",
            "403",
            "404",
        }
    ),
}
