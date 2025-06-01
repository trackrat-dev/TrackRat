"""Utility functions for TrackCast."""

import json
import logging
import math
import os
from datetime import datetime
from typing import Any, Optional, Tuple

import pytz
import yaml

from trackcast.constants import (
    DEFAULT_CONFIG_PATH,
    DEV_CONFIG_PATH,
    ENV_VAR_NAME,
    EVENING_RUSH_END_HOUR,
    EVENING_RUSH_START_HOUR,
    MORNING_RUSH_END_HOUR,
    MORNING_RUSH_START_HOUR,
    PROD_CONFIG_PATH,
)
from trackcast.exceptions import ConfigError

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO") -> None:
    """Set up logging with the specified level.

    Args:
        level: Logging level (default: INFO)
    """
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_config(env: Optional[str] = None) -> dict[str, Any]:
    """Load configuration from YAML file based on environment.

    Args:
        env: Environment name (dev, prod, or None to use env var)

    Returns:
        Dict containing configuration

    Raises:
        ConfigError: If config file not found or invalid
    """
    if env is None:
        env = os.environ.get(ENV_VAR_NAME, "dev")

    config_path = {
        "dev": DEV_CONFIG_PATH,
        "prod": PROD_CONFIG_PATH,
    }.get(env.lower(), DEFAULT_CONFIG_PATH)

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # Also load default config if using environment-specific config
        if config_path != DEFAULT_CONFIG_PATH:
            try:
                with open(DEFAULT_CONFIG_PATH, "r") as f:
                    default_config = yaml.safe_load(f)

                # Merge configs, with environment-specific config taking precedence
                merged_config: dict[str, Any] = {**default_config, **config}
                return merged_config
            except (FileNotFoundError, yaml.YAMLError) as e:
                logger.warning(f"Could not load default config: {str(e)}")
                return config
        return config
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {config_path}")
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in config file: {str(e)}")


def save_json(data: Any, file_path: str) -> None:
    """Save data as JSON to the specified file path.

    Args:
        data: Data to save
        file_path: Path to save JSON file
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def load_json(file_path: str) -> Any:
    """Load JSON data from the specified file path.

    Args:
        file_path: Path to JSON file

    Returns:
        Parsed JSON data
    """
    with open(file_path, "r") as f:
        return json.load(f)


def is_weekend(dt: datetime) -> bool:
    """Check if the given datetime is a weekend.

    Args:
        dt: Datetime to check

    Returns:
        True if weekend, False otherwise
    """
    return dt.weekday() >= 5  # 5 = Saturday, 6 = Sunday


def is_morning_rush(dt: datetime) -> bool:
    """Check if the given datetime is during morning rush hour.

    Args:
        dt: Datetime to check

    Returns:
        True if morning rush hour, False otherwise
    """
    return (
        dt.weekday() < 5 and MORNING_RUSH_START_HOUR <= dt.hour < MORNING_RUSH_END_HOUR  # Weekday
    )


def is_evening_rush(dt: datetime) -> bool:
    """Check if the given datetime is during evening rush hour.

    Args:
        dt: Datetime to check

    Returns:
        True if evening rush hour, False otherwise
    """
    return (
        dt.weekday() < 5 and EVENING_RUSH_START_HOUR <= dt.hour < EVENING_RUSH_END_HOUR  # Weekday
    )


def cyclical_encode(value: int, period: int) -> Tuple[float, float]:
    """Encode a cyclical feature (like hour of day) as sine and cosine components.

    Args:
        value: Value to encode
        period: Period of the cycle

    Returns:
        Tuple of (sin, cos) values
    """
    sin_value = math.sin(2 * math.pi * value / period)
    cos_value = math.cos(2 * math.pi * value / period)
    return sin_value, cos_value


def encode_hour_of_day(dt: datetime) -> Tuple[float, float]:
    """Encode hour of day as cyclical features.

    Args:
        dt: Datetime to encode

    Returns:
        Tuple of (hour_sin, hour_cos)
    """
    return cyclical_encode(dt.hour, 24)


def encode_day_of_week(dt: datetime) -> Tuple[float, float]:
    """Encode day of week as cyclical features.

    Args:
        dt: Datetime to encode

    Returns:
        Tuple of (day_sin, day_cos)
    """
    return cyclical_encode(dt.weekday(), 7)


def parse_njtransit_datetime(date_str: str) -> datetime:
    """Parse a datetime string from NJ Transit API format.

    Args:
        date_str: Datetime string in format "DD-MMM-YYYY HH:MM:SS AM/PM"

    Returns:
        Parsed datetime object
    """
    return datetime.strptime(date_str, "%d-%b-%Y %I:%M:%S %p")


def format_iso_datetime(dt: datetime) -> str:
    """Format a datetime as ISO 8601 string.

    Args:
        dt: Datetime to format

    Returns:
        ISO 8601 formatted string
    """
    return dt.isoformat()


def clean_destination(destination: str) -> str:
    """Clean destination name by removing special characters and suffixes.

    Removes:
    - "-SEC"
    - "&#9992" (airplane symbol HTML entity)
    - Other special characters that might be present

    Args:
        destination: Raw destination string from API or import

    Returns:
        Cleaned destination string
    """
    if not destination:
        return ""

    # Remove -SEC
    destination = destination.replace("-SEC", "")

    # Remove airplane symbol HTML entity
    destination = destination.replace("&#9992", "")

    # Trim whitespace
    destination = destination.strip()

    return destination


def utc_to_eastern(utc_dt: datetime) -> datetime:
    """Convert UTC datetime to Eastern timezone (handles DST automatically).

    Args:
        utc_dt: UTC datetime (can be timezone-aware or naive)

    Returns:
        Naive datetime in Eastern timezone
    """
    eastern = pytz.timezone('US/Eastern')
    
    # If the datetime is naive, assume it's UTC
    if utc_dt.tzinfo is None:
        utc_dt = pytz.UTC.localize(utc_dt)
    elif utc_dt.tzinfo != pytz.UTC:
        # Convert to UTC first if it's in a different timezone
        utc_dt = utc_dt.astimezone(pytz.UTC)
    
    # Convert to Eastern time
    eastern_dt = utc_dt.astimezone(eastern)
    
    # Return as naive datetime (remove timezone info)
    return eastern_dt.replace(tzinfo=None)


def ensure_eastern_timezone(dt: datetime) -> datetime:
    """Ensure datetime is in Eastern timezone.
    
    If timezone-aware, converts to Eastern.
    If naive, assumes it's already Eastern.

    Args:
        dt: Datetime to convert

    Returns:
        Naive datetime in Eastern timezone
    """
    if dt.tzinfo is None:
        # Already assumed to be Eastern
        return dt
    
    eastern = pytz.timezone('US/Eastern')
    eastern_dt = dt.astimezone(eastern)
    return eastern_dt.replace(tzinfo=None)


def parse_iso_datetime_to_eastern(datetime_str: str) -> Optional[datetime]:
    """Parse ISO datetime string (potentially with timezone) to Eastern time.

    Args:
        datetime_str: ISO format datetime string (e.g., "2025-05-31T14:57:00Z")

    Returns:
        Naive datetime in Eastern timezone, or None if parsing fails
    """
    if not datetime_str:
        return None
        
    try:
        # Handle 'Z' suffix (UTC indicator)
        if datetime_str.endswith('Z'):
            datetime_str = datetime_str[:-1] + '+00:00'
        
        # Parse the datetime
        dt = datetime.fromisoformat(datetime_str)
        
        # Convert to Eastern time
        return utc_to_eastern(dt)
        
    except (ValueError, AttributeError) as e:
        logger.warning(f"Failed to parse datetime string '{datetime_str}': {str(e)}")
        return None
