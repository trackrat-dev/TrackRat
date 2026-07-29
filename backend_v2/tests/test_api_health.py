"""
Tests for health and monitoring endpoints.
"""

import pytest
from datetime import datetime


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] in ["healthy", "degraded", "unhealthy"]
    assert "timestamp" in data
    assert data["version"] == "2.0.0"
    assert data["environment"] == "testing"
    assert "checks" in data

    # Verify check structure
    assert "database" in data["checks"]
    assert "scheduler" in data["checks"]
    assert "data_freshness" in data["checks"]


def test_health_reports_data_sources(client):
    """Health should expose the all/active/disabled data-source lists.

    Clients and the E2E suite read this to skip systems that are turned off
    via TRACKRAT_DISABLED_DATA_SOURCES. With nothing disabled (default test
    settings), active must equal the full list and disabled must be empty.
    """
    from trackrat.services.departure import ALL_DATA_SOURCES

    data = client.get("/health").json()
    assert "data_sources" in data
    ds = data["data_sources"]
    assert ds["all"] == ALL_DATA_SOURCES
    assert ds["disabled"] == []
    assert ds["active"] == ALL_DATA_SOURCES


def test_health_reflects_disabled_data_sources(client):
    """When systems are disabled, health drops them from `active`."""
    from trackrat.main import app
    from trackrat.services.departure import ALL_DATA_SOURCES
    from trackrat.settings import Settings, get_settings

    disabled_settings = Settings(
        environment="testing",
        database_url="postgresql+asyncpg://x:x@localhost/x",
        njt_api_token="test_token",
        disabled_data_sources="MBTA, wmata",  # mixed case + spacing on purpose
    )
    # The `client` fixture clears dependency_overrides on teardown, so this
    # override only affects the current test.
    app.dependency_overrides[get_settings] = lambda: disabled_settings
    ds = client.get("/health").json()["data_sources"]

    assert ds["all"] == ALL_DATA_SOURCES
    assert ds["disabled"] == ["MBTA", "WMATA"]  # uppercased + sorted
    assert "MBTA" not in ds["active"]
    assert "WMATA" not in ds["active"]
    assert set(ds["active"]) == set(ALL_DATA_SOURCES) - {"MBTA", "WMATA"}


def test_liveness_probe(client):
    """Test the liveness probe endpoint."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_probe(client):
    """Test the readiness probe endpoint."""
    response = client.get("/health/ready")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] in ["ready", "not_ready"]

    # In test environment with mocks, should be ready
    assert data["status"] == "ready"


def test_scheduler_status(client):
    """Test the scheduler status endpoint."""
    response = client.get("/scheduler/status")
    assert response.status_code == 200

    data = response.json()
    assert "running" in data
    assert "jobs_count" in data
    assert data["running"] is True  # Mocked to be running


def test_health_reports_gtfs_feed_freshness(client):
    """The endpoint must expose a gtfs_feeds check for every active source.

    Static-feed freshness had no representation in /health at all, so a source
    could serve a frozen schedule indefinitely with no HTTP-reachable evidence
    (issue #1646). This pins the wiring; the freshness logic itself is covered
    against real Postgres in tests/integration/test_gtfs_feed_observability.py.
    """
    from trackrat.services.gtfs import GTFS_FEED_URLS, GTFS_STALE_FEED_HOURS

    check = client.get("/health").json()["checks"]["gtfs_feeds"]

    assert check["stale_after_hours"] == GTFS_STALE_FEED_HOURS
    assert set(check["feeds"]) == set(GTFS_FEED_URLS)
    # Nothing is disabled under default test settings, and this fixture's
    # database has no feed rows, so every source reads as never-parsed.
    assert set(check["stale_sources"]) == set(GTFS_FEED_URLS)
    assert check["status"] == "warning"
