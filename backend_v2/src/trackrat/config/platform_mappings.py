"""
Platform groupings for train stations.

These mappings define which tracks belong to the same platform,
used for calculating platform-level usage patterns in track predictions.

This module now delegates to station_configs.py for centralized configuration.
"""

from trackrat.config.station_configs import (
    get_platform_for_track as _get_platform_for_track,
)
from trackrat.config.station_configs import (
    get_station_config,
)

# Re-export the function with the same name for backward compatibility
get_platform_for_track = _get_platform_for_track


def get_tracks_for_platform(station_code: str, platform: str) -> list[str]:
    """
    Get all tracks that belong to a platform group.

    Args:
        station_code: Station code (e.g., 'NY')
        platform: Platform group name (e.g., '7 & 8')

    Returns:
        List of track numbers/letters in that platform group
    """
    config = get_station_config(station_code)

    if config["platform_mappings"]:
        # Station has platform mappings - find tracks for this platform
        tracks = []
        for track, plat in config["platform_mappings"].items():
            if plat == platform:
                tracks.append(track)
        return tracks if tracks else [platform]
    else:
        # No platform mappings - platform is a single track
        return [platform]
