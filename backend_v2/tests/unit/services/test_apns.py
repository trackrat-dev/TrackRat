"""
Tests for APNS service payload construction.

Verifies that custom_data merges into the APNS payload correctly.
APNS HTTP calls are mocked since we cannot hit Apple's servers in tests.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trackrat.services.apns import ApnsSendResult, SimpleAPNSService


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


def _mock_apns_response(*, status_code: int, body: dict | None = None) -> AsyncMock:
    """Build an httpx.AsyncClient mock that returns a single response.

    The response's `.json()` returns the supplied body (or raises if None).
    `.text` is the JSON-encoded body or empty string.
    """
    import json as _json

    resp = MagicMock()
    resp.status_code = status_code
    if body is None:
        resp.json = MagicMock(side_effect=ValueError("no json"))
        resp.text = ""
    else:
        resp.json = MagicMock(return_value=body)
        resp.text = _json.dumps(body)

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


@pytest.mark.asyncio
class TestLiveActivityResultClassification:
    """`send_live_activity_update` and `send_live_activity_end` must classify
    APNS responses into the right `ApnsSendResult` so the scheduler
    deactivates tokens only when the failure is permanent.

    Critical invariants:
    - 200 => SUCCESS
    - 410 (any/no body) => INVALID_TOKEN (Unregistered/ExpiredToken — token gone)
    - 400 with reason in {BadDeviceToken, DeviceTokenNotForTopic} => INVALID_TOKEN
    - 400 with any other reason (e.g., BadCollapseId, IdleTimeout) => TRANSIENT_FAILURE
    - 5xx, 429, network errors, timeouts, JWT failures => TRANSIENT_FAILURE
    """

    async def test_200_returns_success(self):
        service = _make_configured_apns()
        with patch(
            "httpx.AsyncClient",
            return_value=_mock_apns_response(status_code=200),
        ):
            result = await service.send_live_activity_update("token", {"k": "v"})
        assert result is ApnsSendResult.SUCCESS

    async def test_410_returns_invalid_token_even_without_body(self):
        service = _make_configured_apns()
        with patch(
            "httpx.AsyncClient",
            return_value=_mock_apns_response(status_code=410),
        ):
            result = await service.send_live_activity_update("token", {"k": "v"})
        assert result is ApnsSendResult.INVALID_TOKEN

    async def test_410_with_unregistered_reason_returns_invalid_token(self):
        service = _make_configured_apns()
        with patch(
            "httpx.AsyncClient",
            return_value=_mock_apns_response(
                status_code=410, body={"reason": "Unregistered", "timestamp": 12345}
            ),
        ):
            result = await service.send_live_activity_update("token", {"k": "v"})
        assert result is ApnsSendResult.INVALID_TOKEN

    async def test_400_bad_device_token_returns_invalid_token(self):
        """Regression for Codex P1: APNS returns permanent token failures
        as 400 BadDeviceToken too, not just 410. Without this, broken
        tokens stay active forever and get retried every scheduler tick."""
        service = _make_configured_apns()
        with patch(
            "httpx.AsyncClient",
            return_value=_mock_apns_response(
                status_code=400, body={"reason": "BadDeviceToken"}
            ),
        ):
            result = await service.send_live_activity_update("token", {"k": "v"})
        assert result is ApnsSendResult.INVALID_TOKEN

    async def test_400_device_token_not_for_topic_returns_invalid_token(self):
        """Regression for Codex P1: 400 DeviceTokenNotForTopic also means
        the token is permanently unusable for our app/topic."""
        service = _make_configured_apns()
        with patch(
            "httpx.AsyncClient",
            return_value=_mock_apns_response(
                status_code=400, body={"reason": "DeviceTokenNotForTopic"}
            ),
        ):
            result = await service.send_live_activity_update("token", {"k": "v"})
        assert result is ApnsSendResult.INVALID_TOKEN

    async def test_400_bad_collapse_id_is_transient(self):
        """Other 400 reasons are not token-specific (request issue, not
        token issue) — should be TRANSIENT_FAILURE so the token stays
        active and the scheduler keeps trying."""
        service = _make_configured_apns()
        with patch(
            "httpx.AsyncClient",
            return_value=_mock_apns_response(
                status_code=400, body={"reason": "BadCollapseId"}
            ),
        ):
            result = await service.send_live_activity_update("token", {"k": "v"})
        assert result is ApnsSendResult.TRANSIENT_FAILURE

    async def test_503_returns_transient_failure(self):
        service = _make_configured_apns()
        with patch(
            "httpx.AsyncClient",
            return_value=_mock_apns_response(
                status_code=503, body={"reason": "ServiceUnavailable"}
            ),
        ):
            result = await service.send_live_activity_update("token", {"k": "v"})
        assert result is ApnsSendResult.TRANSIENT_FAILURE

    async def test_429_returns_transient_failure(self):
        service = _make_configured_apns()
        with patch(
            "httpx.AsyncClient",
            return_value=_mock_apns_response(
                status_code=429, body={"reason": "TooManyRequests"}
            ),
        ):
            result = await service.send_live_activity_update("token", {"k": "v"})
        assert result is ApnsSendResult.TRANSIENT_FAILURE

    async def test_network_exception_returns_transient_failure(self):
        service = _make_configured_apns()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=ConnectionError("network blip"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service.send_live_activity_update("token", {"k": "v"})
        assert result is ApnsSendResult.TRANSIENT_FAILURE

    async def test_end_400_bad_device_token_returns_invalid_token(self):
        """`send_live_activity_end` must classify identically to
        `send_live_activity_update`."""
        service = _make_configured_apns()
        with patch(
            "httpx.AsyncClient",
            return_value=_mock_apns_response(
                status_code=400, body={"reason": "BadDeviceToken"}
            ),
        ):
            result = await service.send_live_activity_end("token", {"k": "v"})
        assert result is ApnsSendResult.INVALID_TOKEN

    async def test_end_410_returns_invalid_token(self):
        service = _make_configured_apns()
        with patch(
            "httpx.AsyncClient",
            return_value=_mock_apns_response(status_code=410),
        ):
            result = await service.send_live_activity_end("token", {"k": "v"})
        assert result is ApnsSendResult.INVALID_TOKEN
