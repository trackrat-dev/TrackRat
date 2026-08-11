"""
Data sanitization utilities for TrackRat V2.

Handles cleaning and normalizing data from external APIs to fit database constraints.
"""

import re

from structlog import get_logger

from trackrat.config.station_configs import get_valid_tracks

logger = get_logger(__name__)

# (station_code, data_source, track) keys whose implausible-value warning has
# already fired in this process.
#
# A rejected value is usually a permanent property of the feed rather than the
# occasional bad frame this check was written to catch: LIRR reports tracks
# "1"-"4" at Grand Central Madison on every poll, for every train. Logging per
# stop per parse made `track_value_implausible` 46% of all warning volume on
# production and buried the genuine feed-quality warnings this event exists to
# surface (issue #1792). The feed is also re-parsed far more often than the
# collection interval suggests — the JIT path builds a fresh client per API
# request, so the volume scaled with traffic, not just with time.
#
# Mirrors ``GTFSService._empty_service_warned``: the first sighting of a given
# bad value is the informative one, and repeats add nothing.
_implausible_track_warned: set[tuple[str, str, str]] = set()

# Ceiling on that memo so a feed emitting unbounded distinct junk cannot grow it
# without limit. On overflow the memo is dropped and rebuilt: memory stays
# fixed, and the worst case is that warnings repeat occasionally — still far
# quieter than per-stop, and it fails toward visibility rather than silence.
_MAX_IMPLAUSIBLE_TRACK_KEYS = 1024


def bounded_text(text: str, limit: int) -> str:
    """Truncate text to ``limit`` chars, annotating how much was dropped.

    Upstream providers do not always answer with the content type they
    advertise — NJT serves Cloudflare-style HTML error pages on some failures
    — and an untruncated body interpolated into a log line or an exception
    message can be tens of kilobytes, repeated once per train (issue #1725).
    Annotating the dropped length keeps the entry honest about being partial.
    """
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... [truncated {len(text) - limit} chars]"


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
    quality issues are visible — but only once per
    ``(station_code, data_source, track)`` per process (issue #1792). A feed
    that reports the same bad value on every poll is one fact, not thousands,
    and logging it per stop drowned out every other warning. ``train_id``
    therefore identifies the *first* train seen with that value, not the only
    one.

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
    warn_key = (station_code, data_source, track)
    if warn_key not in _implausible_track_warned:
        if len(_implausible_track_warned) >= _MAX_IMPLAUSIBLE_TRACK_KEYS:
            _implausible_track_warned.clear()
        _implausible_track_warned.add(warn_key)
        logger.warning(
            "track_value_implausible",
            station_code=station_code,
            track=track,
            data_source=data_source,
            train_id=train_id,
        )
    return None
