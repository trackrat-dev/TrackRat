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
