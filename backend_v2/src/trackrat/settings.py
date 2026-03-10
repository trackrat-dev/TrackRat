"""
Configuration management for TrackRat V2.

Uses Pydantic Settings for type-safe configuration with environment variable support.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TRACKRAT_",
        case_sensitive=False,
        # Validate even when using defaults
        validate_default=True,
        # Allow explicit env names to override prefix
        env_ignore_empty=True,
    )

    # Environment
    environment: Literal["development", "staging", "production", "testing"] = Field(
        default="development", description="Application environment"
    )
    debug: bool = Field(default=False, description="Enable debug mode")

    def model_post_init(self, __context: Any) -> None:
        """Post-init to set debug mode based on environment."""
        if self.environment == "development":
            object.__setattr__(self, "debug", True)

    # API Settings
    api_host: str = Field(default="0.0.0.0", description="API host to bind to")
    api_port: int = Field(
        default=8000, description="API port to bind to", ge=1, le=65535
    )

    # Database
    database_url: str = Field(
        description="PostgreSQL database connection URL (required, set via TRACKRAT_DATABASE_URL env var)",
    )

    # NJ Transit API
    njt_api_url: str = Field(
        default="https://raildata.njtransit.com/api",
        description="NJ Transit API base URL",
    )
    njt_api_token: str = Field(default="", description="NJ Transit API token")

    @field_validator("njt_api_token", mode="before")
    @classmethod
    def load_njt_token_from_file(cls, v: str) -> str:
        """Load NJT API token from env vars or .njt-token file."""
        if v:
            return v
        # Check NJT_TOKEN env var (used in CI/cloud environments)
        from_env = os.environ.get("NJT_TOKEN", "")
        if from_env:
            return from_env
        # Walk up from this file to find .njt-token in the repo root
        for parent in Path(__file__).resolve().parents:
            token_file = parent / ".njt-token"
            if token_file.is_file():
                token = token_file.read_text().strip()
                if token:
                    return token
                break
        return v

    # Collection Settings
    discovery_interval_minutes: int = Field(
        default=30, description="Interval between discovery runs (minutes)", ge=1
    )
    journey_update_interval_minutes: int = Field(
        default=15, description="Interval between journey updates (minutes)", ge=1
    )
    data_staleness_seconds: int = Field(
        default=60, description="Maximum age of data before refresh (seconds)", ge=1
    )
    hot_data_staleness_seconds: int = Field(
        default=20,
        description="Maximum age of data before refresh for trains departing soon (seconds)",
        ge=5,
    )
    hot_train_window_minutes: int = Field(
        default=15,
        description="Window before departure for more frequent updates (minutes)",
        ge=1,
    )
    hot_train_update_interval_seconds: int = Field(
        default=120,
        description="Update interval for trains departing soon (seconds)",
        ge=30,
    )

    # Validation Settings
    internal_api_url: str = Field(
        default="http://localhost:8000",
        description="Internal API URL for validation service (uses localhost in Cloud Run)",
    )
    validation_max_trains_to_verify: int = Field(
        default=20,
        description="Maximum number of missing trains to verify in detail",
        ge=1,
    )

    # Feature Flags
    use_optimized_amtrak_pattern_analysis: bool = Field(
        default=True,
        description="Use database-aggregated pattern analysis for Amtrak schedules (reduces memory usage by ~99%)",
    )
    # Developer Chat
    chat_admin_registration_code: str = Field(
        default="test132T",
        description="Secret code for registering admin devices for developer chat",
    )

    # Monitoring
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )
    enable_sql_logging: bool = Field(
        default=False, description="Enable SQLAlchemy query logging"
    )

    # Backup Settings
    gcs_backup_bucket: str = Field(
        default="",
        description="GCS bucket name for database backups (empty = no backup)",
    )
    backup_interval_seconds: int = Field(
        default=300, description="Backup interval in seconds", ge=60
    )

    # APNS Settings (optional - Live Activities work without if not configured)
    # Use non-prefixed env vars for compatibility with V1 backend
    apns_team_id: str = Field(
        default_factory=lambda: os.getenv("APNS_TEAM_ID", ""),
        description="Apple Developer Team ID",
    )
    apns_key_id: str = Field(
        default_factory=lambda: os.getenv("APNS_KEY_ID", ""),
        description="APNS Auth Key ID",
    )
    apns_auth_key: str = Field(
        default_factory=lambda: os.getenv("APNS_AUTH_KEY", ""),
        description="APNS Auth Key (P8 content) - legacy environment variable approach",
    )
    apns_auth_key_path: str = Field(
        default_factory=lambda: os.getenv("APNS_AUTH_KEY_PATH", ""),
        description="Path to APNS Auth Key (P8 file) - preferred file-based approach",
    )
    apns_bundle_id: str = Field(
        default_factory=lambda: os.getenv("APNS_BUNDLE_ID", "net.trackrat.TrackRat"),
        description="iOS App Bundle ID",
    )
    apns_environment: str = Field(
        default_factory=lambda: os.getenv("APNS_ENVIRONMENT", "dev"),
        description="APNS Environment (dev for sandbox, prod for production)",
    )

    @property
    def apns_auth_key_content(self) -> str:
        """
        Get APNS auth key content, prioritizing file path over environment variable.
        Returns empty string if neither is available or file cannot be read.
        """
        # First try to load from file path if it exists
        if self.apns_auth_key_path:
            try:
                with open(self.apns_auth_key_path) as f:
                    return f.read().strip()
            except (FileNotFoundError, PermissionError, OSError):
                # Fall through to environment variable
                pass

        # Fall back to environment variable
        return self.apns_auth_key

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate and normalize PostgreSQL database URL."""
        if not v.startswith("postgresql"):
            raise ValueError(
                f"Only PostgreSQL databases are supported. Got: {v[:50]}..."
            )

        # Ensure async driver is used
        if not v.startswith("postgresql+asyncpg://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://")

        return v

    @property
    def database_url_sync(self) -> str:
        """Get synchronous PostgreSQL URL for Alembic migrations."""
        return str(self.database_url).replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
