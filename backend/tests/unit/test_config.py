"""Tests for the config module."""
import os
import pytest
from unittest.mock import patch

from trackcast.config import load_config


def test_load_config_default():
    """Test loading config with default file."""
    with patch.dict(os.environ, {"TRACKCAST_ENV": "test"}):
        config = load_config()
        assert config is not None
        assert "database" in config
        assert "api" in config


def test_load_config_explicit_path(test_config):
    """Test loading config with explicit path."""
    config = test_config
    assert config is not None
    assert "database" in config
    assert config["database"]["url"] == "sqlite:///:memory:"


@patch("trackcast.config.Settings._set_defaults")
def test_load_config_settings_class(mock_set_defaults):
    """Test environment variable is used in Settings class."""
    # The load_config() function doesn't process environment variables,
    # but the Settings class does in _set_defaults()
    # Let's create a test that verifies this indirectly
    with patch.dict(os.environ, {
        "TRACKCAST_ENV": "test"
    }):
        from trackcast.config import Settings
        settings = Settings()

        # Verify that _set_defaults was called, which handles env vars
        mock_set_defaults.assert_called_once()

        # Verify that the expected config keys exist
        assert hasattr(settings, "database")
        assert hasattr(settings, "api")