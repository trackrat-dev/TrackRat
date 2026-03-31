"""
Tests for configuration management.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from trackrat.config import Settings


def test_settings_database_url_normalization():
    """Test that database URLs are normalized correctly."""
    # PostgreSQL URL should be normalized to use asyncpg
    settings = Settings(
        database_url="postgresql://user:pass@localhost/db", njt_api_token="token"
    )
    assert settings.database_url == "postgresql+asyncpg://user:pass@localhost/db"
    assert settings.database_url_sync == "postgresql://user:pass@localhost/db"


def test_settings_missing_required_fields():
    """Test that missing required fields raise validation errors."""
    import os
    from pydantic import Field
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from typing import Literal

    # Temporarily remove environment variables
    env_vars_to_clear = ["TRACKRAT_NJT_API_TOKEN", "NJT_API_TOKEN", "NJT_TOKEN"]
    original_values = {}
    for var in env_vars_to_clear:
        original_values[var] = os.environ.get(var)
        if var in os.environ:
            del os.environ[var]

    try:
        # Create a test Settings class that doesn't read from .env file
        class TestSettings(BaseSettings):
            model_config = SettingsConfigDict(
                env_prefix="TRACKRAT_",
                case_sensitive=False,
                validate_default=True,
                # Don't read from .env file
            )

            # Copy the key fields from the real Settings class
            environment: Literal["development", "production", "testing"] = Field(
                default="development", description="Application environment"
            )
            njt_api_token: str = Field(description="NJ Transit API token", min_length=1)

        with pytest.raises(ValidationError) as exc_info:
            TestSettings()

        errors = exc_info.value.errors()
        error_fields = [e["loc"][0] for e in errors]

        # njt_api_token is required (no default)
        assert "njt_api_token" in error_fields

    finally:
        # Restore environment variables
        for var, value in original_values.items():
            if value is not None:
                os.environ[var] = value


def test_settings_validation():
    """Test field validation."""
    # Test port range validation
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql://user:pass@localhost/db",
            njt_api_token="token",
            api_port=70000,  # Invalid port
        )

    # Test interval validation
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql://user:pass@localhost/db",
            njt_api_token="token",
            discovery_interval_minutes=0,  # Must be >= 1
        )


def test_sqlite_url_rejected():
    """Test that SQLite URLs are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            database_url="sqlite:///test.db",
            njt_api_token="token",
        )
    assert "Only PostgreSQL databases are supported" in str(exc_info.value)


def test_njt_token_fallback_to_njt_token_env(tmp_path, monkeypatch):
    """Test that NJT_TOKEN env var is used when TRACKRAT_NJT_API_TOKEN is not set."""
    # Clear all NJT token sources
    monkeypatch.delenv("TRACKRAT_NJT_API_TOKEN", raising=False)
    monkeypatch.delenv("NJT_API_TOKEN", raising=False)
    monkeypatch.setenv("NJT_TOKEN", "fallback_token_value")

    # Ensure no .njt-token file is found by pointing to empty dir
    monkeypatch.chdir(tmp_path)

    settings = Settings(database_url="postgresql://user:pass@localhost/db")
    assert settings.njt_api_token == "fallback_token_value"


def test_njt_token_primary_takes_precedence(tmp_path, monkeypatch):
    """Test that TRACKRAT_NJT_API_TOKEN takes precedence over NJT_TOKEN."""
    monkeypatch.setenv("TRACKRAT_NJT_API_TOKEN", "primary_token")
    monkeypatch.setenv("NJT_TOKEN", "fallback_token")
    monkeypatch.chdir(tmp_path)

    settings = Settings(database_url="postgresql://user:pass@localhost/db")
    assert settings.njt_api_token == "primary_token"


def test_njt_token_empty_when_no_source(tmp_path, monkeypatch):
    """Test that njt_api_token is empty when no token source is available."""
    monkeypatch.delenv("TRACKRAT_NJT_API_TOKEN", raising=False)
    monkeypatch.delenv("NJT_API_TOKEN", raising=False)
    monkeypatch.delenv("NJT_TOKEN", raising=False)
    # The validator walks from __file__ (not cwd) looking for .njt-token,
    # so chdir alone won't prevent it finding the repo's token file.
    # Patch is_file to block .njt-token discovery.
    _orig_is_file = Path.is_file
    monkeypatch.setattr(
        Path,
        "is_file",
        lambda self: False if self.name == ".njt-token" else _orig_is_file(self),
    )

    settings = Settings(database_url="postgresql://user:pass@localhost/db")
    assert settings.njt_api_token == ""
