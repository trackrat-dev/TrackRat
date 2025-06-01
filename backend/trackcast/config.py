"""
Configuration management for TrackCast.
"""

import logging
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Exception raised for configuration errors."""

    pass


class DotDict(SimpleNamespace):
    """
    A dictionary that allows dot notation access to its keys.
    For example, instead of settings['database']['url'],
    use settings.database.url
    """

    def __init__(self, data: Dict[str, Any]):
        super().__init__(**{k: self._process_value(v) for k, v in data.items()})

    def _process_value(self, value: Any) -> Any:
        """Convert dictionaries to DotDict recursively."""
        if isinstance(value, dict):
            return DotDict(value)
        elif isinstance(value, list):
            return [self._process_value(item) for item in value]
        return value

    def __getattr__(self, key: str) -> Any:
        """Get attribute with fallback to None."""
        try:
            return super().__getattr__(key)
        except AttributeError:
            return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the DotDict back to a regular dictionary."""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, DotDict):
                result[key] = value.to_dict()
            elif isinstance(value, list):
                result[key] = [
                    item.to_dict() if isinstance(item, DotDict) else item for item in value
                ]
            else:
                result[key] = value
        return result


class Settings:
    """Configuration settings for TrackCast."""

    def __init__(self):
        self.env = os.environ.get("TRACKCAST_ENV", "dev")
        self.config_dir = Path(__file__).parent.parent / "config"
        self.config_path = os.environ.get(
            "TRACKCAST_CONFIG", str(self.config_dir / f"{self.env}.yaml")
        )
        self._config = self._load_config()

        # Convert to dot notation
        self._settings = DotDict(self._config)

        # Set default values
        self._set_defaults()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, "r") as file:
                config = yaml.safe_load(file)
                logger.info(f"Loaded configuration from {self.config_path}")
                return config or {}
        except FileNotFoundError:
            logger.warning(f"Configuration file not found: {self.config_path}")
            return {}
        except yaml.YAMLError as e:
            logger.error(f"Error parsing configuration file: {str(e)}")
            raise ConfigurationError(f"Invalid YAML in configuration file: {str(e)}")

    def _set_defaults(self) -> None:
        """Set default values for configuration."""
        # Debug mode - default to True in dev, False in prod
        if not hasattr(self._settings, "debug"):
            self._settings.debug = self.env == "dev"

        # If database URL isn't set, use a default SQLite URL for development
        if not self._settings.database or not getattr(self._settings.database, "url", None):
            if not self._settings.database:
                self._settings.database = DotDict({})
            self._settings.database.url = f"sqlite:///trackcast_{self.env}.db"
            logger.warning(f"Database URL not specified, using {self._settings.database.url}")

        # Default model settings
        if not self._settings.model:
            self._settings.model = DotDict(
                {"version": "0.1.0", "save_path": "models/", "type": "xgboost"}
            )

    def __getattr__(self, name: str) -> Any:
        """Support settings.some_setting syntax."""
        return getattr(self._settings, name)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key."""
        keys = key.split(".")
        value = self._settings

        for k in keys:
            if not hasattr(value, k):
                return default
            value = getattr(value, k)

        return value

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to a dictionary."""
        return self._settings.to_dict()


# Create a singleton instance for easy import
settings = Settings()


def load_config(config_path: Optional[str] = None, env: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from a YAML file.

    Args:
        config_path: Path to the configuration file
        env: Environment name (dev, prod, etc.)

    Returns:
        Dictionary containing the configuration
    """
    if not config_path:
        # Use environment-specific config file
        env = env or os.environ.get("TRACKCAST_ENV", "dev")
        config_dir = Path(__file__).parent.parent / "config"
        config_path = str(config_dir / f"{env}.yaml")

    try:
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)
            logger.info(f"Loaded configuration from {config_path}")
            return config or {}
    except FileNotFoundError:
        logger.warning(f"Configuration file not found: {config_path}")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"Error parsing configuration file: {str(e)}")
        raise ConfigurationError(f"Invalid YAML in configuration file: {str(e)}")
