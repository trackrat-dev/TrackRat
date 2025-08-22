"""
Platform groupings for train stations.

These mappings define which tracks belong to the same platform,
used for calculating platform-level usage patterns in track predictions.
"""

# NY Penn Station platform groupings
# Based on physical platform layout where tracks share a platform
NY_PENN_PLATFORMS = {
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
    "17": "17",  # Single track platform
    "18": "18 & 19",
    "19": "18 & 19",
    "20": "20 & 21",
    "21": "20 & 21",
}

# Add other stations as needed in the future
# Example:
# NEWARK_PENN_PLATFORMS = {
#     "1": "1",
#     "2": "2",
#     ...
# }


def get_platform_for_track(station_code: str, track: str) -> str:
    """
    Get the platform group for a given track at a station.

    Args:
        station_code: Station code (e.g., 'NY')
        track: Track number/letter (e.g., '7', 'A')

    Returns:
        Platform group name, or the track itself if no mapping exists
    """
    if station_code == "NY":
        return NY_PENN_PLATFORMS.get(track, track)

    # Default: track is its own platform
    return track


def get_tracks_for_platform(station_code: str, platform: str) -> list[str]:
    """
    Get all tracks that belong to a platform group.

    Args:
        station_code: Station code (e.g., 'NY')
        platform: Platform group name (e.g., '7 & 8')

    Returns:
        List of track numbers/letters in that platform group
    """
    tracks = []

    if station_code == "NY":
        for track, plat in NY_PENN_PLATFORMS.items():
            if plat == platform:
                tracks.append(track)

    # If no tracks found, assume platform is a single track
    if not tracks:
        tracks = [platform]

    return tracks
