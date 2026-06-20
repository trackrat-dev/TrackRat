"""Tests for the feedback endpoint and the shared client-IP helper.

The client IP is derived server-side and attached to the structured
``user_feedback_submitted`` log event, which the feedback-notifier Cloud
Function later renders into the GitHub issue. These tests cover both the
extraction logic and that the endpoint logs the resolved IP.
"""

from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.testclient import TestClient

from trackrat.api.utils import get_client_ip


def _make_request(
    headers: dict[str, str] | None = None,
    client: tuple[str, int] | None = None,
) -> Request:
    """Build a minimal Starlette Request for helper-level tests."""
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "headers": raw_headers, "client": client})


class TestGetClientIp:
    """Unit tests for the X-Forwarded-For aware client-IP helper."""

    def test_prefers_first_forwarded_for_entry(self) -> None:
        """Behind GCP's LB the real client IP is the first XFF entry."""
        request = _make_request(
            headers={"x-forwarded-for": "203.0.113.7, 35.191.0.1"},
            client=("10.0.0.1", 5000),
        )
        assert get_client_ip(request) == "203.0.113.7"

    def test_strips_whitespace_from_forwarded_entry(self) -> None:
        request = _make_request(headers={"x-forwarded-for": "  203.0.113.7  "})
        assert get_client_ip(request) == "203.0.113.7"

    def test_falls_back_to_direct_peer_without_header(self) -> None:
        request = _make_request(client=("198.51.100.4", 443))
        assert get_client_ip(request) == "198.51.100.4"

    def test_empty_header_falls_back_to_direct_peer(self) -> None:
        request = _make_request(
            headers={"x-forwarded-for": ""}, client=("198.51.100.4", 443)
        )
        assert get_client_ip(request) == "198.51.100.4"

    def test_returns_unknown_when_nothing_available(self) -> None:
        request = _make_request()
        assert get_client_ip(request) == "unknown"


class TestSubmitFeedback:
    """Endpoint-level tests for /api/v2/feedback."""

    def test_logs_forwarded_client_ip(self, client: TestClient, caplog) -> None:
        """The endpoint records the X-Forwarded-For client IP on the log event."""
        caplog.set_level(logging.INFO)
        resp = client.post(
            "/api/v2/feedback",
            json={"message": "Wrong arrival time", "screen": "train_details"},
            headers={"x-forwarded-for": "203.0.113.7, 35.191.0.1"},
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "received"
        assert "user_feedback_submitted" in caplog.text
        assert "client_ip=203.0.113.7" in caplog.text
