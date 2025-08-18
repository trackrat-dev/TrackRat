"""
Data sanitization utilities for TrackRat V2.

Handles cleaning and normalizing data from external APIs to fit database constraints.
"""

import re

from structlog import get_logger

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
