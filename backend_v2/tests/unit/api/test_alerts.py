"""
Tests for the route alert subscription API endpoints.

Uses the e2e_client fixture for real database integration.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from starlette.testclient import TestClient

from trackrat.api.alerts import (
    SubscriptionItem,
    _subscription_identity,
    _subscription_identity_from_item,
)
from trackrat.models.database import RouteAlertSubscription


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

    def test_system_wide_subscription_is_valid(self, e2e_client: TestClient):
        """Subscription with only data_source (no line/stations/train) is a valid system-wide subscription."""
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
            resp.status_code == 200
        ), f"Expected 200, got {resp.status_code}: {resp.json()}"
        assert resp.json()["count"] == 1

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
                    {"data_source": "NJT", "train_id": "3254", "active_days": 31},
                ],
            },
        )
        assert (
            resp.status_code == 200
        ), f"Expected 200, got {resp.status_code}: {resp.json()}"
        assert resp.json()["count"] == 1

    def test_train_id_with_all_days(self, e2e_client: TestClient):
        """Train subscription with active_days=127 (all days) is accepted."""
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
                        "active_days": 127,
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
                    {"data_source": "NJT", "train_id": "3254", "active_days": 31},
                ],
            },
        )

        resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-train-3")
        assert resp.status_code == 200
        subs = resp.json()["subscriptions"]
        assert len(subs) == 1
        assert subs[0]["train_id"] == "3254"
        assert subs[0]["active_days"] == 31
        assert subs[0]["data_source"] == "NJT"
        assert subs[0]["line_id"] is None
        assert subs[0]["from_station_code"] is None
        print(f"  Train subscription round-tripped: {subs[0]}")

    def test_active_days_defaults_to_127(self, e2e_client: TestClient):
        """active_days defaults to 127 (all days) when not provided."""
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
        assert subs[0]["active_days"] == 127
        print(f"  active_days default: {subs[0]['active_days']}")

    def test_customization_fields_roundtrip(self, e2e_client: TestClient):
        """All customization fields should round-trip through PUT/GET."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-custom-1", "apns_token": "tok-custom1"},
        )
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-custom-1",
                "subscriptions": [
                    {
                        "data_source": "NJT",
                        "line_id": "njt-nec",
                        "active_days": 31,
                        "active_start_minutes": 360,
                        "active_end_minutes": 600,
                        "timezone": "America/New_York",
                        "delay_threshold_minutes": 5,
                        "service_threshold_pct": 70,
                        "notify_recovery": True,
                        "digest_time_minutes": 420,
                    },
                ],
            },
        )
        assert resp.status_code == 200

        get_resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-custom-1")
        subs = get_resp.json()["subscriptions"]
        assert len(subs) == 1
        s = subs[0]
        assert s["active_days"] == 31
        assert s["active_start_minutes"] == 360
        assert s["active_end_minutes"] == 600
        assert s["timezone"] == "America/New_York"
        assert s["delay_threshold_minutes"] == 5
        assert s["service_threshold_pct"] == 70
        assert s["notify_recovery"] is True
        assert s["digest_time_minutes"] == 420
        print(f"  All customization fields round-tripped: {s}")

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
                    {"data_source": "NJT", "train_id": "3254", "active_days": 31},
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


class TestDirectionSubscriptions:
    """Tests for the direction field on line subscriptions."""

    def test_line_with_direction_roundtrips(self, e2e_client: TestClient):
        """A line subscription with direction is stored and returned correctly."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-dir-1", "apns_token": "tok-dir1"},
        )
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-dir-1",
                "subscriptions": [
                    {"data_source": "NJT", "line_id": "njt-nec", "direction": "TR"},
                    {"data_source": "NJT", "line_id": "njt-nec", "direction": "NY"},
                ],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

        get_resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-dir-1")
        subs = get_resp.json()["subscriptions"]
        assert len(subs) == 2
        directions = {s["direction"] for s in subs}
        assert directions == {"TR", "NY"}
        for s in subs:
            assert s["line_id"] == "njt-nec"
            assert s["data_source"] == "NJT"
        print(f"  Direction roundtrip: {directions}")

    def test_direction_null_by_default(self, e2e_client: TestClient):
        """A line subscription without direction has direction=null."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-dir-2", "apns_token": "tok-dir2"},
        )
        e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-dir-2",
                "subscriptions": [
                    {"data_source": "NJT", "line_id": "njt-nec"},
                ],
            },
        )

        get_resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-dir-2")
        subs = get_resp.json()["subscriptions"]
        assert len(subs) == 1
        assert subs[0]["direction"] is None
        print(f"  Direction default null: {subs[0]}")

    def test_mixed_direction_subscriptions(self, e2e_client: TestClient):
        """A sync with all subscription types including direction is accepted."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-dir-4", "apns_token": "tok-dir4"},
        )
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-dir-4",
                "subscriptions": [
                    {"data_source": "NJT", "line_id": "njt-nec", "direction": "TR"},
                    {"data_source": "NJT", "line_id": "njt-nec", "direction": "NY"},
                    {
                        "data_source": "NJT",
                        "from_station_code": "NY",
                        "to_station_code": "TR",
                    },
                    {"data_source": "NJT", "train_id": "3254", "active_days": 31},
                ],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 4

        get_resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-dir-4")
        subs = get_resp.json()["subscriptions"]
        assert len(subs) == 4
        line_subs = [s for s in subs if s["line_id"]]
        assert len(line_subs) == 2
        assert {s["direction"] for s in line_subs} == {"TR", "NY"}
        print(f"  Mixed subs with direction: {len(subs)} total")


class TestPlannedWorkSubscriptions:
    """Tests for include_planned_work field on subscriptions."""

    def test_include_planned_work_roundtrips(self, e2e_client: TestClient):
        """include_planned_work=true is stored and returned correctly."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-pw-1", "apns_token": "tok-pw1"},
        )
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-pw-1",
                "subscriptions": [
                    {
                        "data_source": "SUBWAY",
                        "line_id": "subway-G",
                        "include_planned_work": True,
                    },
                ],
            },
        )
        assert resp.status_code == 200

        get_resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-pw-1")
        subs = get_resp.json()["subscriptions"]
        assert len(subs) == 1
        assert subs[0]["include_planned_work"] is True
        print(f"  include_planned_work roundtrip: {subs[0]['include_planned_work']}")

    def test_include_planned_work_defaults_false(self, e2e_client: TestClient):
        """include_planned_work defaults to false when not provided."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-pw-2", "apns_token": "tok-pw2"},
        )
        e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-pw-2",
                "subscriptions": [
                    {"data_source": "NJT", "line_id": "njt-nec"},
                ],
            },
        )

        get_resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-pw-2")
        subs = get_resp.json()["subscriptions"]
        assert subs[0]["include_planned_work"] is False
        print(f"  include_planned_work default: {subs[0]['include_planned_work']}")

    def test_mixed_planned_work_subscriptions(self, e2e_client: TestClient):
        """Mix of planned work opt-in and opt-out subscriptions works."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-pw-3", "apns_token": "tok-pw3"},
        )
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-pw-3",
                "subscriptions": [
                    {
                        "data_source": "SUBWAY",
                        "line_id": "subway-G",
                        "include_planned_work": True,
                    },
                    {
                        "data_source": "NJT",
                        "line_id": "njt-nec",
                        "include_planned_work": False,
                    },
                ],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

        get_resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-pw-3")
        subs = get_resp.json()["subscriptions"]
        pw_values = {s["data_source"]: s["include_planned_work"] for s in subs}
        assert pw_values["SUBWAY"] is True
        assert pw_values["NJT"] is False


class TestCancellationThreshold:
    """Tests for cancellation_threshold_pct field on subscriptions."""

    def test_cancellation_threshold_roundtrips(self, e2e_client: TestClient):
        """cancellation_threshold_pct is stored and returned correctly."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-ct-1", "apns_token": "tok-ct1"},
        )
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-ct-1",
                "subscriptions": [
                    {
                        "data_source": "SUBWAY",
                        "line_id": "subway-G",
                        "cancellation_threshold_pct": 50,
                        "notify_cancellation": True,
                    },
                ],
            },
        )
        assert resp.status_code == 200

        get_resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-ct-1")
        subs = get_resp.json()["subscriptions"]
        assert len(subs) == 1
        assert subs[0]["cancellation_threshold_pct"] == 50
        assert subs[0]["notify_cancellation"] is True
        print(
            f"  cancellation_threshold_pct roundtrip: {subs[0]['cancellation_threshold_pct']}"
        )

    def test_cancellation_threshold_defaults_null(self, e2e_client: TestClient):
        """cancellation_threshold_pct defaults to null when not provided."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-ct-2", "apns_token": "tok-ct2"},
        )
        e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-ct-2",
                "subscriptions": [
                    {"data_source": "NJT", "line_id": "njt-nec"},
                ],
            },
        )

        get_resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-ct-2")
        subs = get_resp.json()["subscriptions"]
        assert subs[0]["cancellation_threshold_pct"] is None
        print(
            f"  cancellation_threshold_pct default: {subs[0]['cancellation_threshold_pct']}"
        )

    def test_sensitivity_levels_roundtrip(self, e2e_client: TestClient):
        """All three sensitivity levels (none=off, severe=50, all=90) round-trip correctly."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-ct-3", "apns_token": "tok-ct3"},
        )
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-ct-3",
                "subscriptions": [
                    {
                        "data_source": "SUBWAY",
                        "line_id": "subway-G",
                        "notify_cancellation": False,
                        "cancellation_threshold_pct": None,
                    },
                    {
                        "data_source": "PATH",
                        "line_id": "path-hob-33",
                        "notify_cancellation": True,
                        "cancellation_threshold_pct": 50,
                    },
                    {
                        "data_source": "SUBWAY",
                        "line_id": "subway-L",
                        "notify_cancellation": True,
                        "cancellation_threshold_pct": 90,
                    },
                ],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 3

        get_resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-ct-3")
        subs = get_resp.json()["subscriptions"]
        assert len(subs) == 3

        by_line = {s["line_id"]: s for s in subs}
        # None: off
        assert by_line["subway-G"]["notify_cancellation"] is False
        assert by_line["subway-G"]["cancellation_threshold_pct"] is None
        # Severe Only: 50%
        assert by_line["path-hob-33"]["notify_cancellation"] is True
        assert by_line["path-hob-33"]["cancellation_threshold_pct"] == 50
        # All: 90%
        assert by_line["subway-L"]["notify_cancellation"] is True
        assert by_line["subway-L"]["cancellation_threshold_pct"] == 90
        print("  All three sensitivity levels verified")


class TestServiceAlertsEndpoint:
    """GET /api/v2/alerts/service"""

    def test_empty_service_alerts(self, e2e_client: TestClient):
        """Returns empty list when no service alerts exist."""
        resp = e2e_client.get("/api/v2/alerts/service")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["alerts"] == []

    def test_service_alerts_with_data_source_filter(self, e2e_client: TestClient):
        """Filtering by data_source works."""
        resp = e2e_client.get("/api/v2/alerts/service?data_source=SUBWAY")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["alerts"], list)
        assert isinstance(data["count"], int)

    def test_service_alerts_with_alert_type_filter(self, e2e_client: TestClient):
        """Filtering by alert_type works."""
        resp = e2e_client.get("/api/v2/alerts/service?alert_type=planned_work")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["alerts"], list)

    def test_service_alerts_with_both_filters(self, e2e_client: TestClient):
        """Combined data_source and alert_type filters work."""
        resp = e2e_client.get(
            "/api/v2/alerts/service?data_source=SUBWAY&alert_type=planned_work"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["alerts"], list)


class TestNotifyTypeToggleSubscriptions:
    """Tests for notify_cancellation and notify_delay field round-tripping."""

    def test_notify_toggles_default_to_true(self, e2e_client: TestClient):
        """When not specified, notify_cancellation and notify_delay default to True."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-notify-1", "apns_token": "tok-notify-1"},
        )
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-notify-1",
                "subscriptions": [
                    {"data_source": "NJT", "line_id": "NE"},
                ],
            },
        )
        assert resp.status_code == 200
        print(f"  Sync response: {resp.json()}")

        get_resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-notify-1")
        assert get_resp.status_code == 200
        subs = get_resp.json()["subscriptions"]
        assert len(subs) == 1
        assert subs[0]["notify_cancellation"] is True
        assert subs[0]["notify_delay"] is True
        print("  Verified: defaults are True when not specified")

    def test_notify_toggles_round_trip(self, e2e_client: TestClient):
        """Setting notify_cancellation=False and notify_delay=False persists correctly."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-notify-2", "apns_token": "tok-notify-2"},
        )
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-notify-2",
                "subscriptions": [
                    {
                        "data_source": "NJT",
                        "line_id": "NE",
                        "notify_cancellation": False,
                        "notify_delay": False,
                    },
                ],
            },
        )
        assert resp.status_code == 200

        get_resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-notify-2")
        subs = get_resp.json()["subscriptions"]
        assert len(subs) == 1
        assert subs[0]["notify_cancellation"] is False
        assert subs[0]["notify_delay"] is False
        print("  Verified: False values round-trip correctly")

    def test_mixed_notify_values(self, e2e_client: TestClient):
        """One toggle on, one off — verifies independence."""
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": "dev-notify-3", "apns_token": "tok-notify-3"},
        )
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": "dev-notify-3",
                "subscriptions": [
                    {
                        "data_source": "SUBWAY",
                        "line_id": "1",
                        "notify_cancellation": True,
                        "notify_delay": False,
                    },
                ],
            },
        )
        assert resp.status_code == 200

        get_resp = e2e_client.get("/api/v2/alerts/subscriptions/dev-notify-3")
        subs = get_resp.json()["subscriptions"]
        assert len(subs) == 1
        assert subs[0]["notify_cancellation"] is True
        assert subs[0]["notify_delay"] is False
        print("  Verified: mixed toggle values round-trip independently")


class TestSubscriptionIdentityHelpers:
    """Unit tests for _subscription_identity and _subscription_identity_from_item."""

    def test_line_identity(self):
        """Line-based subscription identity uses data_source, line_id, direction."""
        row = RouteAlertSubscription(
            device_id="d1",
            data_source="NJT",
            line_id="njt-nec",
            direction="TR",
        )
        assert _subscription_identity(row) == ("line", "NJT", "njt-nec", "TR")

    def test_station_pair_identity(self):
        """Station-pair subscription identity uses data_source + station codes."""
        row = RouteAlertSubscription(
            device_id="d1",
            data_source="NJT",
            from_station_code="NY",
            to_station_code="TR",
        )
        assert _subscription_identity(row) == ("stations", "NJT", "NY", "TR")

    def test_train_identity(self):
        """Train-specific subscription identity uses data_source + train_id."""
        row = RouteAlertSubscription(
            device_id="d1",
            data_source="NJT",
            train_id="3254",
        )
        assert _subscription_identity(row) == ("train", "NJT", "3254")

    def test_item_matches_row_identity(self):
        """_subscription_identity_from_item produces the same key as _subscription_identity."""
        cases = [
            (
                {"data_source": "NJT", "line_id": "njt-nec", "direction": "TR"},
                RouteAlertSubscription(
                    device_id="d1",
                    data_source="NJT",
                    line_id="njt-nec",
                    direction="TR",
                ),
            ),
            (
                {
                    "data_source": "NJT",
                    "from_station_code": "NY",
                    "to_station_code": "TR",
                },
                RouteAlertSubscription(
                    device_id="d1",
                    data_source="NJT",
                    from_station_code="NY",
                    to_station_code="TR",
                ),
            ),
            (
                {"data_source": "NJT", "train_id": "3254"},
                RouteAlertSubscription(
                    device_id="d1", data_source="NJT", train_id="3254"
                ),
            ),
        ]
        for item_kwargs, row in cases:
            item = SubscriptionItem(**item_kwargs)
            item_key = _subscription_identity_from_item("d1", item)
            row_key = _subscription_identity(row)
            assert (
                item_key == row_key
            ), f"Mismatch for {item_kwargs}: item={item_key}, row={row_key}"
            print(f"  Matched: {row_key}")

    def test_line_null_direction_identity(self):
        """Line subscription with direction=None has distinct identity from direction='TR'."""
        row_null = RouteAlertSubscription(
            device_id="d1", data_source="NJT", line_id="njt-nec", direction=None
        )
        row_tr = RouteAlertSubscription(
            device_id="d1", data_source="NJT", line_id="njt-nec", direction="TR"
        )
        assert _subscription_identity(row_null) != _subscription_identity(row_tr)
        print(
            f"  null={_subscription_identity(row_null)}, TR={_subscription_identity(row_tr)}"
        )


class TestSyncPreservesNotificationState:
    """Verify that re-syncing subscriptions preserves server-side dedup state.

    This is the core regression test for the duplicate notification bug:
    the old delete-all-then-recreate pattern wiped last_alerted_at,
    last_alert_hash, last_digest_at, and last_service_alert_ids on every sync.
    """

    def _set_state_on_subscriptions(
        self, sync_session, device_id: str
    ) -> dict[str, dict]:
        """Directly set notification state columns on DB rows.

        Returns a map of line_id/train_id -> state dict for later assertion.
        """
        rows = (
            sync_session.execute(
                select(RouteAlertSubscription).where(
                    RouteAlertSubscription.device_id == device_id
                )
            )
            .scalars()
            .all()
        )
        state_by_key = {}
        now = datetime.now(UTC)
        for i, row in enumerate(rows):
            state = {
                "last_alerted_at": now,
                "last_alert_hash": f"hash-{i}",
                "last_digest_at": now,
                "last_service_alert_ids": [f"alert-{i}-a", f"alert-{i}-b"],
            }
            row.last_alerted_at = state["last_alerted_at"]
            row.last_alert_hash = state["last_alert_hash"]
            row.last_digest_at = state["last_digest_at"]
            row.last_service_alert_ids = state["last_service_alert_ids"]
            # Key by whichever identity field is set
            key = (
                row.line_id
                or row.train_id
                or f"{row.from_station_code}-{row.to_station_code}"
            )
            state_by_key[key] = state
        sync_session.commit()
        return state_by_key

    def _get_state_from_db(self, sync_session, device_id: str) -> dict[str, dict]:
        """Read notification state columns from DB rows after a sync."""
        rows = (
            sync_session.execute(
                select(RouteAlertSubscription).where(
                    RouteAlertSubscription.device_id == device_id
                )
            )
            .scalars()
            .all()
        )
        result = {}
        for row in rows:
            key = (
                row.line_id
                or row.train_id
                or f"{row.from_station_code}-{row.to_station_code}"
            )
            result[key] = {
                "last_alerted_at": row.last_alerted_at,
                "last_alert_hash": row.last_alert_hash,
                "last_digest_at": row.last_digest_at,
                "last_service_alert_ids": row.last_service_alert_ids,
            }
        return result

    def test_resync_identical_line_subs_preserves_state(
        self, e2e_client: TestClient, sync_session
    ):
        """Re-syncing the same line subscriptions preserves all four state columns."""
        device_id = "dev-state-line"
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": device_id, "apns_token": "tok-state-line"},
        )

        subs_payload = [
            {"data_source": "NJT", "line_id": "njt-nec", "direction": "TR"},
            {"data_source": "SUBWAY", "line_id": "subway-G"},
        ]

        # Initial sync
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={"device_id": device_id, "subscriptions": subs_payload},
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

        # Set notification state directly in DB
        original_state = self._set_state_on_subscriptions(sync_session, device_id)
        print(f"  Set state on {len(original_state)} subscriptions")
        assert len(original_state) == 2

        # Re-sync with identical subscriptions (simulates app launch)
        resp2 = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={"device_id": device_id, "subscriptions": subs_payload},
        )
        assert resp2.status_code == 200
        assert resp2.json()["count"] == 2

        # Verify state was preserved
        sync_session.expire_all()
        after_state = self._get_state_from_db(sync_session, device_id)
        for key, orig in original_state.items():
            after = after_state[key]
            assert (
                after["last_alerted_at"] is not None
            ), f"{key}: last_alerted_at was wiped"
            assert (
                after["last_alert_hash"] == orig["last_alert_hash"]
            ), f"{key}: last_alert_hash was wiped"
            assert (
                after["last_digest_at"] is not None
            ), f"{key}: last_digest_at was wiped"
            assert (
                after["last_service_alert_ids"] == orig["last_service_alert_ids"]
            ), f"{key}: last_service_alert_ids was wiped"
            print(f"  {key}: all state columns preserved")

    def test_resync_identical_station_pair_preserves_state(
        self, e2e_client: TestClient, sync_session
    ):
        """Re-syncing station-pair subscriptions preserves state."""
        device_id = "dev-state-stn"
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": device_id, "apns_token": "tok-state-stn"},
        )

        subs_payload = [
            {"data_source": "NJT", "from_station_code": "NY", "to_station_code": "TR"},
        ]

        e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={"device_id": device_id, "subscriptions": subs_payload},
        )
        original_state = self._set_state_on_subscriptions(sync_session, device_id)

        # Re-sync
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={"device_id": device_id, "subscriptions": subs_payload},
        )
        assert resp.status_code == 200

        sync_session.expire_all()
        after_state = self._get_state_from_db(sync_session, device_id)
        key = "NY-TR"
        assert (
            after_state[key]["last_alert_hash"]
            == original_state[key]["last_alert_hash"]
        )
        assert (
            after_state[key]["last_service_alert_ids"]
            == original_state[key]["last_service_alert_ids"]
        )
        print(f"  Station-pair state preserved: {key}")

    def test_resync_identical_train_sub_preserves_state(
        self, e2e_client: TestClient, sync_session
    ):
        """Re-syncing train subscriptions preserves state."""
        device_id = "dev-state-train"
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": device_id, "apns_token": "tok-state-train"},
        )

        subs_payload = [
            {"data_source": "NJT", "train_id": "3254", "active_days": 31},
        ]

        e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={"device_id": device_id, "subscriptions": subs_payload},
        )
        original_state = self._set_state_on_subscriptions(sync_session, device_id)

        # Re-sync
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={"device_id": device_id, "subscriptions": subs_payload},
        )
        assert resp.status_code == 200

        sync_session.expire_all()
        after_state = self._get_state_from_db(sync_session, device_id)
        assert (
            after_state["3254"]["last_alert_hash"]
            == original_state["3254"]["last_alert_hash"]
        )
        assert (
            after_state["3254"]["last_service_alert_ids"]
            == original_state["3254"]["last_service_alert_ids"]
        )
        print("  Train subscription state preserved")

    def test_new_subscription_gets_null_state(
        self, e2e_client: TestClient, sync_session
    ):
        """A genuinely new subscription added during sync starts with NULL state."""
        device_id = "dev-state-new"
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": device_id, "apns_token": "tok-state-new"},
        )

        # Initial sync with one sub
        e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": device_id,
                "subscriptions": [
                    {"data_source": "NJT", "line_id": "njt-nec"},
                ],
            },
        )
        self._set_state_on_subscriptions(sync_session, device_id)

        # Re-sync with original + one new subscription
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": device_id,
                "subscriptions": [
                    {"data_source": "NJT", "line_id": "njt-nec"},
                    {"data_source": "SUBWAY", "line_id": "subway-G"},
                ],
            },
        )
        assert resp.status_code == 200

        sync_session.expire_all()
        after_state = self._get_state_from_db(sync_session, device_id)

        # Existing sub should have preserved state
        assert after_state["njt-nec"]["last_alert_hash"] is not None
        print("  Existing sub preserved state")

        # New sub should have NULL state
        assert after_state["subway-G"]["last_alerted_at"] is None
        assert after_state["subway-G"]["last_alert_hash"] is None
        assert after_state["subway-G"]["last_digest_at"] is None
        assert after_state["subway-G"]["last_service_alert_ids"] is None
        print("  New sub has NULL state (correct)")

    def test_removed_subscription_state_not_carried_to_different_sub(
        self, e2e_client: TestClient, sync_session
    ):
        """Removing a subscription and adding a different one doesn't leak state."""
        device_id = "dev-state-remove"
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": device_id, "apns_token": "tok-state-remove"},
        )

        # Initial sync
        e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": device_id,
                "subscriptions": [
                    {"data_source": "NJT", "line_id": "njt-nec"},
                ],
            },
        )
        self._set_state_on_subscriptions(sync_session, device_id)

        # Re-sync replacing the sub entirely
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": device_id,
                "subscriptions": [
                    {"data_source": "SUBWAY", "line_id": "subway-G"},
                ],
            },
        )
        assert resp.status_code == 200

        sync_session.expire_all()
        after_state = self._get_state_from_db(sync_session, device_id)
        assert "njt-nec" not in after_state, "Old subscription should be gone"
        assert (
            after_state["subway-G"]["last_alert_hash"] is None
        ), "New subscription should not inherit old state"
        print("  No state leakage between different subscriptions")

    def test_config_change_preserves_state(self, e2e_client: TestClient, sync_session):
        """Changing config fields (e.g. delay_threshold) preserves notification state."""
        device_id = "dev-state-cfg"
        e2e_client.post(
            "/api/v2/devices/register",
            json={"device_id": device_id, "apns_token": "tok-state-cfg"},
        )

        # Initial sync
        e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": device_id,
                "subscriptions": [
                    {
                        "data_source": "NJT",
                        "line_id": "njt-nec",
                        "delay_threshold_minutes": 5,
                    },
                ],
            },
        )
        original_state = self._set_state_on_subscriptions(sync_session, device_id)

        # Re-sync with changed config
        resp = e2e_client.put(
            "/api/v2/alerts/subscriptions",
            json={
                "device_id": device_id,
                "subscriptions": [
                    {
                        "data_source": "NJT",
                        "line_id": "njt-nec",
                        "delay_threshold_minutes": 10,
                    },
                ],
            },
        )
        assert resp.status_code == 200

        sync_session.expire_all()
        after_state = self._get_state_from_db(sync_session, device_id)
        assert (
            after_state["njt-nec"]["last_alert_hash"]
            == original_state["njt-nec"]["last_alert_hash"]
        )
        assert (
            after_state["njt-nec"]["last_service_alert_ids"]
            == original_state["njt-nec"]["last_service_alert_ids"]
        )
        print("  Config change preserved notification state")
