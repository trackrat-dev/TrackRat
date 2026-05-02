"""
Data sanitization utilities for TrackRat V2.

Handles cleaning and normalizing data from external APIs to fit database constraints.
"""

import re

from structlog import get_logger

from trackrat.config.station_configs import get_valid_tracks

logger = get_logger(__name__)


def sanitize_track(track_value: str | None) -> str | None:
    """
    Sanitize track values to fit database constraints (5 char max).

    Preserves meaningful track information while ensuring data fits in database.

    Args:
        track_value: Raw track value from API

    Returns:
        Sanitized track value (max 5 chars) or None

    Examples:
        >>> sanitize_track(None)
        None
        >>> sanitize_track("1")
        '1'
        >>> sanitize_track("Track 2")
        '2'
        >>> sanitize_track("Millstone Running")
        'Mill+'
    """
    if not track_value:
        return None

    # Clean whitespace
    track_value = str(track_value).strip()

    # Return None if empty after stripping
    if not track_value:
        return None

    # If already fits, return as-is
    if len(track_value) <= 5:
        return track_value

    # Try to extract meaningful track identifier
    # Common patterns: "Track 1", "Platform 2", "1 Running", etc.
    # Look for track numbers/letters (e.g., 1, 2A, A1, etc.)
    track_pattern = re.search(r"\b(\d+[A-Z]?|[A-Z]\d*)\b", track_value)
    if track_pattern:
        extracted = track_pattern.group(1)
        if len(extracted) <= 5:
            logger.warning(
                "sanitized_track_extracted_number",
                original=track_value,
                sanitized=extracted,
            )
            return extracted

    # Fallback: truncate to 4 chars + indicator
    truncated = track_value[:4] + "+"
    logger.warning(
        "sanitized_track_truncated",
        original=track_value,
        sanitized=truncated,
    )
    return truncated


def validate_track(
    station_code: str,
    track: str | None,
    data_source: str,
    train_id: str | None = None,
) -> str | None:
    """Reject implausible track values; pass through where we lack a full list.

    For (station, data_source) pairs with an exhaustive track list in
    ``VALIDATED_TRACKS`` (``station_configs.py``), reject any value not in the
    set. For all others, return the track unchanged. This protects against
    occasional bad frames in upstream feeds (notably MTA GTFS-RT) while
    avoiding false rejections where our list might be incomplete.

    On rejection, logs a structured ``track_value_implausible`` warning so feed
    quality issues are visible.

    Args:
        station_code: The station where the track is being reported.
        track: The track value from the upstream feed (may be None/empty).
        data_source: Transit system ("LIRR", "MNR", "SUBWAY", ...). Used both
            for lookup and for log correlation.
        train_id: Optional train identifier for log correlation.

    Returns:
        ``track`` if valid (or if no validation set is configured for this
        station+data_source), ``None`` if the value is implausible or empty.
    """
    if not track:
        return None
    valid = get_valid_tracks(station_code, data_source)
    if valid is None or track in valid:
        return track
    logger.warning(
        "track_value_implausible",
        station_code=station_code,
        track=track,
        data_source=data_source,
        train_id=train_id,
    )
    return None
