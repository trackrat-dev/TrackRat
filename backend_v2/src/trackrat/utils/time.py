"""
Time utilities for TrackRat V2.

Handles Eastern Time conversions and NJ Transit time format parsing.
"""

from datetime import date, datetime, time, timedelta

import pytz
from dateutil import parser as date_parser

# Eastern Time Zone
ET = pytz.timezone("America/New_York")

# Central Time Zone (for Chicago Metra)
CT = pytz.timezone("America/Chicago")

# Pacific Time Zone (for BART)
PT = pytz.timezone("America/Los_Angeles")

# Provider timezone mapping — used by collectors and GTFS parsing to determine
# the correct local timezone for each transit provider
PROVIDER_TIMEZONE: dict[str, pytz.BaseTzInfo] = {
    "NJT": ET,
    "AMTRAK": ET,
    "PATH": ET,
    "PATCO": ET,
    "LIRR": ET,
    "MNR": ET,
    "SUBWAY": ET,
    "METRA": CT,
    "BART": PT,
    "MBTA": ET,
    "WMATA": ET,
}


def now_for_provider(data_source: str) -> datetime:
    """Get current time in the local timezone for a given transit provider.

    Args:
        data_source: Provider identifier (e.g., "LIRR", "METRA")

    Returns:
        Timezone-aware datetime in the provider's local timezone
    """
    tz = PROVIDER_TIMEZONE.get(data_source, ET)
    return datetime.now(tz)


# Timezone-aware min/max constants for safe datetime comparisons
# Note: year 9999 causes OverflowError in pytz, use 2099/1900 as safe bounds
# These should be used instead of datetime.min/datetime.max when comparing
# with timezone-aware datetimes (e.g., from database or parse_njt_time)
DATETIME_MAX_ET = ET.localize(datetime(2099, 12, 31, 23, 59, 59))
DATETIME_MIN_ET = ET.localize(datetime(1900, 1, 1, 0, 0, 0))


def now_et() -> datetime:
    """Get current time in Eastern Time."""
    return datetime.now(ET)


def parse_njt_time(time_str: str) -> datetime:
    """Parse NJ Transit time format.

    Examples:
    - "30-May-2024 10:52:30 AM"
    - "15-Jan-2024 02:30:00 PM"

    Args:
        time_str: Time string from NJ Transit API

    Returns:
        Timezone-aware datetime in Eastern Time
    """
    # Parse the datetime
    dt = date_parser.parse(time_str)

    # NJ Transit times are in Eastern Time
    if dt.tzinfo is None:
        dt = ET.localize(dt)

    return dt


def parse_date(date_str: str) -> date:
    """Parse date string in various formats.

    Args:
        date_str: Date string (YYYY-MM-DD or other formats)

    Returns:
        Date object
    """
    if isinstance(date_str, date):
        return date_str

    # Try ISO format first
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        # Fall back to dateutil parser
        return date_parser.parse(date_str).date()


def combine_date_time(date_obj: date, time_str: str) -> datetime:
    """Combine a date with a time string.

    Args:
        date_obj: Date object
        time_str: Time string (e.g., "14:30:00" or "2:30 PM")

    Returns:
        Timezone-aware datetime in Eastern Time
    """
    # Parse time string
    if ":" in time_str and len(time_str.split(":")) == 3:
        # Format: HH:MM:SS
        time_parts = time_str.split(":")
        time_obj = time(
            hour=int(time_parts[0]),
            minute=int(time_parts[1]),
            second=int(time_parts[2]),
        )
    else:
        # Let dateutil handle other formats
        parsed = date_parser.parse(time_str)
        time_obj = parsed.time()

    # Combine and localize
    dt = datetime.combine(date_obj, time_obj)
    return ET.localize(dt)


def format_iso(dt: datetime | None) -> str | None:
    """Format datetime as ISO string with timezone.

    Args:
        dt: Datetime object (can be None)

    Returns:
        ISO formatted string or None
    """
    if dt is None:
        return None
    return dt.isoformat()


def calculate_delay(scheduled: datetime, actual: datetime | None) -> int:
    """Calculate delay in minutes with timezone safety.

    Args:
        scheduled: Scheduled datetime
        actual: Actual datetime (None if not departed)

    Returns:
        Delay in minutes (0 if on time or not departed)
    """
    if actual is None:
        return 0

    # Ensure both datetimes are timezone-aware
    scheduled_tz = ensure_timezone_aware(scheduled)
    actual_tz = ensure_timezone_aware(actual)

    delay = safe_datetime_subtract(actual_tz, scheduled_tz).total_seconds() / 60
    return max(0, int(delay))  # Never negative


def ensure_timezone_aware(dt: datetime, default_tz: pytz.BaseTzInfo = ET) -> datetime:
    """Ensure datetime is timezone-aware, defaulting to Eastern Time.

    Args:
        dt: Datetime object (may be naive or aware)
        default_tz: Default timezone for naive datetimes

    Returns:
        Timezone-aware datetime
    """
    if dt.tzinfo is None:
        # Handle DST transitions safely
        try:
            return default_tz.localize(dt)
        except pytz.AmbiguousTimeError:
            # During DST transition, use the first occurrence
            return default_tz.localize(dt, is_dst=True)
    return dt


def normalize_to_et(dt: datetime) -> datetime:
    """Convert any timezone-aware datetime to Eastern Time.

    Args:
        dt: Timezone-aware datetime

    Returns:
        Datetime converted to Eastern Time
    """
    dt = ensure_timezone_aware(dt)
    return dt.astimezone(ET)


def safe_datetime_subtract(dt1: datetime, dt2: datetime) -> timedelta:
    """Safely subtract datetimes, ensuring consistent timezones.

    Args:
        dt1: First datetime
        dt2: Second datetime

    Returns:
        Timedelta representing the difference
    """
    # Ensure both datetimes are timezone-aware first
    dt1 = ensure_timezone_aware(dt1)
    dt2 = ensure_timezone_aware(dt2)

    # Then normalize to same timezone
    dt1_normalized = normalize_to_et(dt1)
    dt2_normalized = normalize_to_et(dt2)
    return dt1_normalized - dt2_normalized


MAX_FUTURE_DAYS = 60
MIN_VALID_DATE = date(2020, 1, 1)


def validate_journey_date(journey_date: date) -> bool:
    """Check whether a journey_date is within a plausible range.

    Rejects dates before 2020-01-01 or more than 60 days in the future.
    NJT schedules cover a 27-hour window, so anything beyond ~30 days
    is necessarily garbage from a parsing error.
    """
    today = now_et().date()
    return journey_date >= MIN_VALID_DATE and journey_date <= today + timedelta(
        days=MAX_FUTURE_DAYS
    )


def is_stale(last_updated: datetime, max_age_seconds: int) -> bool:
    """Check if data is stale with timezone safety.

    Args:
        last_updated: When data was last updated
        max_age_seconds: Maximum age in seconds

    Returns:
        True if data is older than max_age_seconds
    """
    age = safe_datetime_subtract(now_et(), last_updated).total_seconds()
    return age > max_age_seconds
