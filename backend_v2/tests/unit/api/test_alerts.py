"""
Tests for the route alert subscription API endpoints.

Uses the e2e_client fixture for real database integration.
"""

import pytest
from starlette.testclient import TestClient


class TestDeviceRegistration:
    """POST /api/v2/devices/register"""

    def test_register_new_device(self, e2e_client: TestClient):
        """Registering a new device returns 200 with status=registered."""
        resp = e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-1", "apns_token": "tok-aaa"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "registered"

    def test_register_updates_existing_device(self, e2e_client: TestClient):
        """Re-registering same device_id with new token updates the token."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-2", "apns_token": "tok-old"},
        )
        resp = e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-2", "apns_token": "tok-new"},
        )
        assert resp.status_code == 200


class TestSyncSubscriptions:
    """PUT /api/v2/alerts/subscriptions"""

    def test_sync_replaces_all_subscriptions(self, e2e_client: TestClient):
        """Sync should delete old subscriptions and insert new ones."""
        # Register device first
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-sync-1", "apns_token": "tok-sync"},
        )

        # First sync: 2 subscriptions
        resp1 = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-sync-1",
                "subscriptions": [
                    {"data_source": "NJT", "line_id": "njt-nec"},
                    {"data_source": "PATH", "line_id": "path-hob-33"},
                ],
            },
        )
        assert resp1.status_code == 200
        assert resp1.json()["count"] == 2

        # Second sync: replace with 1 subscription
        resp2 = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-sync-1",
                "subscriptions": [
                    {
                        "data_source": "NJT",
                        "from_station_code": "NY",
                        "to_station_code": "TR",
                    },
                ],
            },
        )
        assert resp2.status_code == 200
        assert resp2.json()["count"] == 1

        # Verify via GET
        get_resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-sync-1")
        assert get_resp.status_code == 200
        subs = get_resp.json()["subscriptions"]
        assert len(subs) == 1
        assert subs[0]["from_station_code"] == "NY"
        assert subs[0]["to_station_code"] == "TR"

    def test_sync_unknown_device_returns_404(self, e2e_client: TestClient):
        """Syncing for an unregistered device should return 404."""
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "does-not-exist",
                "subscriptions": [],
            },
        )
        assert resp.status_code == 404

    def test_sync_empty_list_clears_subscriptions(self, e2e_client: TestClient):
        """Syncing with an empty list should remove all subscriptions."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-empty", "apns_token": "tok-empty"},
        )
        # Add some subscriptions
        e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-empty",
                "subscriptions": [
                    {"data_source": "NJT", "line_id": "njt-nec"},
                ],
            },
        )
        # Now clear
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={"device_id": "dev-empty", "subscriptions": []},
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

        get_resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-empty")
        assert get_resp.json()["subscriptions"] == []


class TestSubscriptionValidation:
    """Pydantic validation on SubscriptionItem."""

    def test_missing_both_line_and_stations_returns_422(self, e2e_client: TestClient):
        """Subscription with no line_id and no station codes is rejected."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-val-1", "apns_token": "tok-val"},
        )
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-val-1",
                "subscriptions": [{"data_source": "NJT"}],
            },
        )
        assert (
            resp.status_code == 422
        ), f"Expected 422, got {resp.status_code}: {resp.json()}"

    def test_partial_station_codes_returns_422(self, e2e_client: TestClient):
        """Subscription with only from_station_code but no to_station_code is rejected."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-val-2", "apns_token": "tok-val2"},
        )
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-val-2",
                "subscriptions": [
                    {"data_source": "NJT", "from_station_code": "NY"},
                ],
            },
        )
        assert (
            resp.status_code == 422
        ), f"Expected 422, got {resp.status_code}: {resp.json()}"

    def test_line_id_alone_is_valid(self, e2e_client: TestClient):
        """Subscription with just line_id is accepted."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-val-3", "apns_token": "tok-val3"},
        )
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-val-3",
                "subscriptions": [
                    {"data_source": "NJT", "line_id": "njt-nec"},
                ],
            },
        )
        assert resp.status_code == 200

    def test_both_station_codes_is_valid(self, e2e_client: TestClient):
        """Subscription with both station codes is accepted."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-val-4", "apns_token": "tok-val4"},
        )
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-val-4",
                "subscriptions": [
                    {
                        "data_source": "NJT",
                        "from_station_code": "NY",
                        "to_station_code": "TR",
                    },
                ],
            },
        )
        assert resp.status_code == 200


class TestTrainSubscriptionValidation:
    """Pydantic validation for train_id subscriptions."""

    def test_train_id_alone_is_valid(self, e2e_client: TestClient):
        """Subscription with just train_id is accepted."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-train-1", "apns_token": "tok-train1"},
        )
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-train-1",
                "subscriptions": [
                    {"data_source": "NJT", "train_id": "3254", "weekdays_only": True},
                ],
            },
        )
        assert (
            resp.status_code == 200
        ), f"Expected 200, got {resp.status_code}: {resp.json()}"
        assert resp.json()["count"] == 1

    def test_train_id_with_weekdays_only_false(self, e2e_client: TestClient):
        """Train subscription with weekdays_only=false is accepted."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-train-2", "apns_token": "tok-train2"},
        )
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-train-2",
                "subscriptions": [
                    {
                        "data_source": "AMTRAK",
                        "train_id": "A171",
                        "weekdays_only": False,
                    },
                ],
            },
        )
        assert resp.status_code == 200

    def test_train_id_roundtrips_via_get(self, e2e_client: TestClient):
        """Train subscription fields are returned correctly by GET."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-train-3", "apns_token": "tok-train3"},
        )
        e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-train-3",
                "subscriptions": [
                    {"data_source": "NJT", "train_id": "3254", "weekdays_only": True},
                ],
            },
        )

        resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-train-3")
        assert resp.status_code == 200
        subs = resp.json()["subscriptions"]
        assert len(subs) == 1
        assert subs[0]["train_id"] == "3254"
        assert subs[0]["weekdays_only"] is True
        assert subs[0]["data_source"] == "NJT"
        assert subs[0]["line_id"] is None
        assert subs[0]["from_station_code"] is None
        print(f"  Train subscription round-tripped: {subs[0]}")

    def test_weekdays_only_defaults_false(self, e2e_client: TestClient):
        """weekdays_only defaults to false when not provided."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-train-4", "apns_token": "tok-train4"},
        )
        e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-train-4",
                "subscriptions": [
                    {"data_source": "NJT", "line_id": "njt-nec"},
                ],
            },
        )

        resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-train-4")
        subs = resp.json()["subscriptions"]
        assert subs[0]["weekdays_only"] is False
        print(f"  weekdays_only default: {subs[0]['weekdays_only']}")

    def test_mixed_subscription_types(self, e2e_client: TestClient):
        """A sync with all three subscription types is accepted."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-train-5", "apns_token": "tok-train5"},
        )
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-train-5",
                "subscriptions": [
                    {"data_source": "NJT", "line_id": "njt-nec"},
                    {
                        "data_source": "NJT",
                        "from_station_code": "NY",
                        "to_station_code": "TR",
                    },
                    {"data_source": "NJT", "train_id": "3254", "weekdays_only": True},
                ],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 3

        get_resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-train-5")
        subs = get_resp.json()["subscriptions"]
        assert len(subs) == 3
        types = {
            "line": any(s["line_id"] for s in subs),
            "station": any(s["from_station_code"] for s in subs),
            "train": any(s["train_id"] for s in subs),
        }
        assert all(types.values()), f"Expected all three types present: {types}"


class TestGetSubscriptions:
    """GET /api/v2/alerts/subscriptions/{device_id}"""

    def test_get_returns_subscriptions(self, e2e_client: TestClient):
        """Getting subscriptions for a registered device returns the list."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-get-1", "apns_token": "tok-get"},
        )
        e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-get-1",
                "subscriptions": [
                    {"data_source": "NJT", "line_id": "njt-nec"},
                    {
                        "data_source": "PATH",
                        "from_station_code": "HB",
                        "to_station_code": "WTC",
                    },
                ],
            },
        )

        resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-get-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["device_id"] == "dev-get-1"
        assert len(data["subscriptions"]) == 2

    def test_get_unknown_device_returns_404(self, e2e_client: TestClient):
        """Getting subscriptions for an unregistered device returns 404."""
        resp = e2e_client.get("/api/v2/alerts/subscriptions/no-such-device")
        assert resp.status_code == 404
