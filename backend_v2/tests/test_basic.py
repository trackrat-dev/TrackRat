"""
Basic functionality tests that don't require the full app.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from trackrat.utils.time import parse_njt_time, calculate_delay, now_et
from trackrat.config import Settings


def test_parse_njt_time():
    """Test NJ Transit time parsing."""
    result = parse_njt_time("30-May-2024 10:52:30 AM")
    assert result.year == 2024
    assert result.month == 5
    assert result.day == 30
    assert result.hour == 10
    assert result.minute == 52
    assert result.second == 30


def test_calculate_delay():
    """Test delay calculation."""
    from trackrat.utils.time import ET

    scheduled = ET.localize(datetime(2024, 7, 4, 14, 30, 0))

    # On time
    actual = scheduled
    assert calculate_delay(scheduled, actual) == 0

    # 5 minutes late
    actual = scheduled + timedelta(minutes=5)
    assert calculate_delay(scheduled, actual) == 5

    # None actual time (not departed)
    assert calculate_delay(scheduled, None) == 0


def test_settings_creation():
    """Test that settings can be created with required fields."""
    settings = Settings(
        database_url="postgresql://user:pass@localhost/testdb",
        njt_api_token="test_token",
    )

    assert settings.database_url == "postgresql+asyncpg://user:pass@localhost/testdb"
    assert settings.njt_api_token == "test_token"
    assert settings.environment == "development"


def test_database_url_normalization():
    """Test database URL normalization."""
    # PostgreSQL - should add asyncpg driver
    settings = Settings(
        database_url="postgresql://user:pass@host/db", njt_api_token="token"
    )
    assert "postgresql+asyncpg://" in settings.database_url
