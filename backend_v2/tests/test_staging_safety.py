"""
Tests for the staging notification safety check.

Verifies that _check_staging_notification_safety correctly detects
production notification data left in a staging database after a
production-to-staging disk clone, and returns True to disable APNS
when the threshold is exceeded.
"""

import pytest
from contextlib import asynccontextmanager
from unittest.mock import patch

from trackrat.main import (
    _STAGING_DEVICE_TOKEN_THRESHOLD,
    _check_staging_notification_safety,
)
from trackrat.models.database import DeviceToken, LiveActivityToken
from trackrat.settings import Settings


@pytest.fixture
def staging_settings() -> Settings:
    """Settings configured as staging environment."""
    return Settings(
        environment="staging",
        database_url="postgresql+asyncpg://trackratuser:password@localhost:5434/trackratdb_test",
        njt_api_token="test_token",
    )


def _session_context(db_session):
    """Create a fake async context manager that yields the test db_session."""

    @asynccontextmanager
    async def fake_get_session():
        yield db_session

    return fake_get_session


@pytest.mark.asyncio
async def test_safety_check_empty_db_returns_false(
    db_session, staging_settings, caplog
):
    """With no device tokens, returns False (APNS safe) and logs OK."""
    with patch("trackrat.main.get_session", _session_context(db_session)):
        result = await _check_staging_notification_safety(staging_settings)

    assert result is False
    assert "staging_notification_safety_ok" in caplog.text


@pytest.mark.asyncio
async def test_safety_check_few_tokens_returns_false(
    db_session, staging_settings, caplog
):
    """With a few tokens (below threshold), returns False and logs info."""
    for i in range(3):
        db_session.add(
            DeviceToken(
                device_id=f"test_device_{i:03d}",
                apns_token=f"test_apns_token_{i:03d}",
            )
        )
    await db_session.commit()

    with patch("trackrat.main.get_session", _session_context(db_session)):
        result = await _check_staging_notification_safety(staging_settings)

    assert result is False
    assert "staging_notification_tokens_present" in caplog.text
    assert "staging testers" in caplog.text


@pytest.mark.asyncio
async def test_safety_check_many_tokens_returns_true(
    db_session, staging_settings, caplog
):
    """With many tokens (above threshold), returns True to disable APNS."""
    count = _STAGING_DEVICE_TOKEN_THRESHOLD + 10
    for i in range(count):
        db_session.add(
            DeviceToken(
                device_id=f"prod_device_{i:04d}",
                apns_token=f"prod_apns_token_{i:04d}",
            )
        )
    await db_session.commit()

    with patch("trackrat.main.get_session", _session_context(db_session)):
        result = await _check_staging_notification_safety(staging_settings)

    assert result is True
    assert "staging_notification_safety_warning" in caplog.text
    assert "APNS will be disabled" in caplog.text
    assert str(count) in caplog.text


@pytest.mark.asyncio
async def test_safety_check_exactly_at_threshold_returns_false(
    db_session, staging_settings, caplog
):
    """Exactly at threshold should NOT trigger (only above threshold)."""
    for i in range(_STAGING_DEVICE_TOKEN_THRESHOLD):
        db_session.add(
            DeviceToken(
                device_id=f"edge_device_{i:04d}",
                apns_token=f"edge_apns_token_{i:04d}",
            )
        )
    await db_session.commit()

    with patch("trackrat.main.get_session", _session_context(db_session)):
        result = await _check_staging_notification_safety(staging_settings)

    assert result is False
    assert "staging_notification_safety_warning" not in caplog.text


@pytest.mark.asyncio
async def test_safety_check_live_activity_tokens_counted(
    db_session, staging_settings, caplog
):
    """Live Activity token count should appear in the warning message."""
    from datetime import datetime, timedelta, timezone

    count = _STAGING_DEVICE_TOKEN_THRESHOLD + 5
    for i in range(count):
        db_session.add(
            DeviceToken(
                device_id=f"la_device_{i:04d}",
                apns_token=f"la_apns_token_{i:04d}",
            )
        )

    la_count = 3
    for i in range(la_count):
        db_session.add(
            LiveActivityToken(
                push_token=f"la_push_token_{i:03d}",
                activity_id=f"activity_{i:03d}",
                train_number=f"100{i}",
                origin_code="NY",
                destination_code="TR",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=6),
            )
        )
    await db_session.commit()

    with patch("trackrat.main.get_session", _session_context(db_session)):
        result = await _check_staging_notification_safety(staging_settings)

    assert result is True
    assert "staging_notification_safety_warning" in caplog.text
    assert str(la_count) in caplog.text


@pytest.mark.asyncio
async def test_safety_check_handles_db_errors_gracefully(staging_settings, caplog):
    """If the database query fails, returns False (allow startup) with warning."""

    @asynccontextmanager
    async def failing_get_session():
        raise ConnectionError("Database unavailable")
        yield  # pragma: no cover

    with patch("trackrat.main.get_session", failing_get_session):
        result = await _check_staging_notification_safety(staging_settings)

    assert result is False
    assert "staging_notification_safety_check_failed" in caplog.text
    assert "Proceeding with caution" in caplog.text
