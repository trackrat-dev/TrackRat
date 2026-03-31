"""
Tests for APNS service payload construction.

Verifies that custom_data merges into the APNS payload correctly.
APNS HTTP calls are mocked since we cannot hit Apple's servers in tests.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trackrat.services.apns import SimpleAPNSService


def _make_configured_apns() -> SimpleAPNSService:
    """Create an APNS service with mocked configuration."""
    with patch.object(SimpleAPNSService, "__init__", lambda self: None):
        service = SimpleAPNSService()
        service.is_configured = True
        service.base_url = "https://api.sandbox.push.apple.com"
        service.bundle_id = "net.trackrat.TrackRat"
        service._get_jwt_token = MagicMock(return_value="fake-jwt")
        return service


@pytest.mark.asyncio
class TestAPNSAlertPayload:
    """Tests for send_alert_notification payload construction."""

    async def test_alert_without_custom_data(self):
        """Basic alert has only aps key in payload."""
        service = _make_configured_apns()

        captured_payload = {}

        async def mock_post(url, json, headers):
            captured_payload.update(json)
            resp = MagicMock()
            resp.status_code = 200
            return resp

        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service.send_alert_notification(
                "device-token", "Title", "Body"
            )

        assert result is True
        assert "aps" in captured_payload
        assert captured_payload["aps"]["alert"]["title"] == "Title"
        assert captured_payload["aps"]["alert"]["body"] == "Body"
        assert "route_alert" not in captured_payload

    async def test_alert_with_custom_data_merges_into_payload(self):
        """Custom data should be merged into payload root alongside aps."""
        service = _make_configured_apns()

        captured_payload = {}

        async def mock_post(url, json, headers):
            captured_payload.update(json)
            resp = MagicMock()
            resp.status_code = 200
            return resp

        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        custom = {
            "route_alert": {
                "data_source": "NJT",
                "line_id": None,
                "from_station_code": "NY",
                "to_station_code": "TR",
            }
        }

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service.send_alert_notification(
                "device-token", "Title", "Body", custom_data=custom
            )

        assert result is True
        assert "aps" in captured_payload
        assert "route_alert" in captured_payload
        assert captured_payload["route_alert"]["data_source"] == "NJT"
        assert captured_payload["route_alert"]["from_station_code"] == "NY"
        assert captured_payload["route_alert"]["to_station_code"] == "TR"

    async def test_custom_data_does_not_overwrite_aps(self):
        """Custom data should not clobber the aps key."""
        service = _make_configured_apns()

        captured_payload = {}

        async def mock_post(url, json, headers):
            captured_payload.update(json)
            resp = MagicMock()
            resp.status_code = 200
            return resp

        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        # Deliberately include an "aps" key that should be stripped
        custom = {"aps": {"alert": {"title": "Evil"}}, "extra_info": "value"}

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service.send_alert_notification(
                "device-token", "Title", "Body", custom_data=custom
            )

        assert result is True
        # aps should still have original title, not the injected one
        assert captured_payload["aps"]["alert"]["title"] == "Title"
        assert captured_payload["aps"]["alert"]["body"] == "Body"
        # Non-aps keys should pass through
        assert captured_payload["extra_info"] == "value"
        # The injected aps key should have been filtered out
        assert "Evil" not in str(captured_payload["aps"])

    async def test_not_configured_returns_false(self):
        """When APNS is not configured, send returns False without hitting network."""
        service = _make_configured_apns()
        service.is_configured = False

        result = await service.send_alert_notification(
            "device-token", "Title", "Body", custom_data={"key": "val"}
        )
        assert result is False
