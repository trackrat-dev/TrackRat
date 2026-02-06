"""
Station-specific configurations for ML track predictions.

This module defines which stations support ML predictions and their track configurations.
All stations use a minimum of 100 samples for training.
"""

from typing import Any

# Station configurations for ML track predictions
# Note: Only NY has platform groupings. All other stations use track = platform
STATION_ML_CONFIGS = {
    "NY": {
        "ml_enabled": True,
        "min_samples_required": 100,
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
        "ml_enabled": True,
        "min_samples_required": 100,
        "tracks": ["1", "2", "3", "4", "5", "A"],
        "platform_mappings": None,  # Track = Platform
    },
    "ND": {  # 565 records
        "ml_enabled": True,
        "min_samples_required": 100,
        "tracks": ["1", "2", "3"],
        "platform_mappings": None,
    },
    "HB": {  # Hoboken - 389 records
        "ml_enabled": True,
        "min_samples_required": 100,
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
        "ml_enabled": True,
        "min_samples_required": 100,
        "tracks": ["1", "4"],
        "platform_mappings": None,
    },
    "ST": {  # 349 records
        "ml_enabled": True,
        "min_samples_required": 100,
        "tracks": ["0", "1", "2", "W"],
        "platform_mappings": None,
    },
    "TR": {  # Trenton - 338 records
        "ml_enabled": True,
        "min_samples_required": 100,
        "tracks": ["1", "2", "4", "5"],
        "platform_mappings": None,
    },
    "PH": {  # Princeton/Philadelphia? - 275 records
        "ml_enabled": True,
        "min_samples_required": 100,
        "tracks": ["2", "3", "4", "5", "6", "7", "9"],
        "platform_mappings": None,
    },
    "DV": {  # 249 records
        "ml_enabled": True,
        "min_samples_required": 100,
        "tracks": ["1", "2", "Sing+"],
        "platform_mappings": None,
    },
    "DN": {  # 137 records
        "ml_enabled": True,
        "min_samples_required": 100,
        "tracks": ["1", "2"],
        "platform_mappings": None,
    },
    "PL": {  # 132 records
        "ml_enabled": True,
        "min_samples_required": 100,
        "tracks": ["1", "2"],
        "platform_mappings": None,
    },
    "LB": {  # 118 records
        "ml_enabled": True,
        "min_samples_required": 100,
        "tracks": ["1", "2"],
        "platform_mappings": None,
    },
    "JA": {  # Jersey Avenue (NJT) - 113 records
        "ml_enabled": True,
        "min_samples_required": 100,
        "tracks": ["1", "2"],
        "platform_mappings": None,
    },
    "JAM": {  # Jamaica (LIRR) - busiest junction in the system
        "ml_enabled": True,
        "min_samples_required": 100,
        "tracks": ["2", "6", "7", "8", "11", "12"],
        "platform_mappings": None,
    },
    "GCT": {  # Grand Central - MNR Terminal (tracks 13-114) + LIRR Madison (tracks 201-304)
        "ml_enabled": True,
        "min_samples_required": 100,
        "tracks": [
            # MNR Grand Central Terminal
            "13", "15", "16", "18", "19", "20",
            "23", "24", "25", "28",
            "32", "33", "35", "36", "37", "38", "39",
            "42",
            "102", "103", "104", "106", "107", "111", "112", "114",
            # LIRR Grand Central Madison
            "201", "202", "204",
            "301", "302", "304",
        ],
        "platform_mappings": None,
    },
    # Default configuration for stations not explicitly listed
    "_default": {
        "ml_enabled": False,
        "min_samples_required": 100,
        "tracks": [],
        "platform_mappings": None,
    },
}


def get_station_config(station_code: str) -> dict[str, Any]:
    """
    Get ML configuration for a station.

    Args:
        station_code: Station code (e.g., 'NY', 'NP')

    Returns:
        Dictionary with station configuration
    """
    return STATION_ML_CONFIGS.get(station_code, STATION_ML_CONFIGS["_default"])


def station_has_ml_predictions(station_code: str) -> bool:
    """
    Check if station has ML predictions enabled.

    Args:
        station_code: Station code (e.g., 'NY', 'NP')

    Returns:
        True if ML predictions are enabled for this station
    """
    config = get_station_config(station_code)
    return bool(config["ml_enabled"])


def get_platform_for_track(station_code: str, track: str) -> str:
    """
    Get platform name for a given track at a station.

    Args:
        station_code: Station code (e.g., 'NY', 'NP')
        track: Track identifier (e.g., '1', 'A')

    Returns:
        Platform name (may be same as track for non-NY stations)
    """
    config = get_station_config(station_code)

    if config["platform_mappings"]:
        # Station has platform mappings (currently only NY)
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


def get_ml_enabled_stations() -> list[str]:
    """
    Get list of all stations with ML predictions enabled.

    Returns:
        List of station codes that have ML enabled
    """
    return [
        code
        for code, config in STATION_ML_CONFIGS.items()
        if code != "_default" and config.get("ml_enabled", False)
    ]
