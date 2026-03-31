"""
Tests for the route preference API endpoints.

Uses the e2e_client fixture for real database integration.
"""

import pytest
from starlette.testclient import TestClient


def _register_device(e2e_client: TestClient, device_id: str) -> None:
    """Helper: register a device so FK constraints pass."""
    resp = e2e_client.post(
        "/api/v2/devices/register",
        json={"device_id": device_id, "apns_token": "tok-test"},
    )
    assert resp.status_code == 200


class TestGetRoutePreference:
    """GET /api/v2/routes/preferences"""

    def test_returns_404_when_no_preference_saved(self, e2e_client: TestClient):
        """Should return 404 for a device+route with no saved preference."""
        _register_device(e2e_client, "pref-get-1")
        resp = e2e_client.get(
            "/api/v2/routes/preferences",
            params={"device_id": "pref-get-1", "from": "NY", "to": "TR"},
        )
        assert (
            resp.status_code == 404
        ), f"Expected 404, got {resp.status_code}: {resp.text}"

    def test_returns_saved_preference(self, e2e_client: TestClient):
        """Should return the previously saved preference."""
        _register_device(e2e_client, "pref-get-2")

        # Save a preference first
        e2e_client.put(
            "/api/v2/routes/preferences",
            json={
                "device_id": "pref-get-2",
                "from_station_code": "NY",
                "to_station_code": "TR",
                "enabled_systems": {"NJT": ["NE"], "AMTRAK": []},
            },
        )

        # Now GET it
        resp = e2e_client.get(
            "/api/v2/routes/preferences",
            params={"device_id": "pref-get-2", "from": "NY", "to": "TR"},
        )
        assert (
            resp.status_code == 200
        ), f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["from_station_code"] == "NY"
        assert data["to_station_code"] == "TR"
        assert data["enabled_systems"] == {"NJT": ["NE"], "AMTRAK": []}


class TestUpsertRoutePreference:
    """PUT /api/v2/routes/preferences"""

    def test_creates_new_preference(self, e2e_client: TestClient):
        """Should create a preference for a new device+route pair."""
        _register_device(e2e_client, "pref-put-1")

        resp = e2e_client.put(
            "/api/v2/routes/preferences",
            json={
                "device_id": "pref-put-1",
                "from_station_code": "R268",
                "to_station_code": "R236",
                "enabled_systems": {"SUBWAY": ["1", "A", "C", "E"]},
            },
        )
        assert (
            resp.status_code == 200
        ), f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["from_station_code"] == "R268"
        assert data["to_station_code"] == "R236"
        assert data["enabled_systems"] == {"SUBWAY": ["1", "A", "C", "E"]}

    def test_updates_existing_preference(self, e2e_client: TestClient):
        """Should update enabled_systems when preference already exists."""
        _register_device(e2e_client, "pref-put-2")

        # Create initial preference
        e2e_client.put(
            "/api/v2/routes/preferences",
            json={
                "device_id": "pref-put-2",
                "from_station_code": "NY",
                "to_station_code": "PJ",
                "enabled_systems": {"NJT": ["NE"], "AMTRAK": ["AM"]},
            },
        )

        # Update: disable Amtrak
        resp = e2e_client.put(
            "/api/v2/routes/preferences",
            json={
                "device_id": "pref-put-2",
                "from_station_code": "NY",
                "to_station_code": "PJ",
                "enabled_systems": {"NJT": ["NE"]},
            },
        )
        assert (
            resp.status_code == 200
        ), f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json()["enabled_systems"] == {"NJT": ["NE"]}

        # Verify via GET
        get_resp = e2e_client.get(
            "/api/v2/routes/preferences",
            params={"device_id": "pref-put-2", "from": "NY", "to": "PJ"},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["enabled_systems"] == {"NJT": ["NE"]}

    def test_rejects_unregistered_device(self, e2e_client: TestClient):
        """Should return 404 if device_id is not registered."""
        resp = e2e_client.put(
            "/api/v2/routes/preferences",
            json={
                "device_id": "nonexistent-device",
                "from_station_code": "NY",
                "to_station_code": "TR",
                "enabled_systems": {"NJT": []},
            },
        )
        assert (
            resp.status_code == 404
        ), f"Expected 404, got {resp.status_code}: {resp.text}"

    def test_multiple_routes_per_device(self, e2e_client: TestClient):
        """A device can have different preferences for different routes."""
        _register_device(e2e_client, "pref-put-3")

        # Route 1
        resp1 = e2e_client.put(
            "/api/v2/routes/preferences",
            json={
                "device_id": "pref-put-3",
                "from_station_code": "NY",
                "to_station_code": "TR",
                "enabled_systems": {"NJT": ["NE"]},
            },
        )
        assert resp1.status_code == 200

        # Route 2
        resp2 = e2e_client.put(
            "/api/v2/routes/preferences",
            json={
                "device_id": "pref-put-3",
                "from_station_code": "R268",
                "to_station_code": "R236",
                "enabled_systems": {"SUBWAY": ["1", "A"]},
            },
        )
        assert resp2.status_code == 200

        # Both should be independently retrievable
        get1 = e2e_client.get(
            "/api/v2/routes/preferences",
            params={"device_id": "pref-put-3", "from": "NY", "to": "TR"},
        )
        assert get1.json()["enabled_systems"] == {"NJT": ["NE"]}

        get2 = e2e_client.get(
            "/api/v2/routes/preferences",
            params={"device_id": "pref-put-3", "from": "R268", "to": "R236"},
        )
        assert get2.json()["enabled_systems"] == {"SUBWAY": ["1", "A"]}

    def test_empty_systems_clears_filter(self, e2e_client: TestClient):
        """Saving empty enabled_systems should succeed (means 'show nothing' or reset)."""
        _register_device(e2e_client, "pref-put-4")

        resp = e2e_client.put(
            "/api/v2/routes/preferences",
            json={
                "device_id": "pref-put-4",
                "from_station_code": "NY",
                "to_station_code": "TR",
                "enabled_systems": {},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["enabled_systems"] == {}
