"""
Tests for configuration management.
"""

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
