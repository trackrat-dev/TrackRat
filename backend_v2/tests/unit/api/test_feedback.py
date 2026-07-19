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
    """Unit tests for the X-Forwarded-For aware client-IP helper.

    GCP's external HTTP(S) load balancer appends ``"<client-ip>,<lb-ip>"`` to
    any existing X-Forwarded-For header, so the trusted client IP is the
    second-to-last entry and any earlier entries may have been forged by the
    caller.
    """

    def test_returns_second_to_last_entry_behind_gcp_lb(self) -> None:
        """The LB-appended pair is at the tail; the real client IP is at -2."""
        request = _make_request(
            headers={"x-forwarded-for": "203.0.113.7, 35.191.0.1"},
            client=("10.0.0.1", 5000),
        )
        assert get_client_ip(request) == "203.0.113.7"

    def test_ignores_spoofed_entries_before_lb_appended_pair(self) -> None:
        """Client-supplied XFF entries appear before the LB-appended pair and
        must not be trusted; only the LB's recorded client IP (position -2)
        counts."""
        request = _make_request(
            headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8, 203.0.113.7, 35.191.0.1"},
            client=("10.0.0.1", 5000),
        )
        assert get_client_ip(request) == "203.0.113.7"

    def test_strips_whitespace_around_entries(self) -> None:
        request = _make_request(
            headers={"x-forwarded-for": "  203.0.113.7  ,  35.191.0.1  "}
        )
        assert get_client_ip(request) == "203.0.113.7"

    def test_single_xff_entry_falls_back_to_direct_peer(self) -> None:
        """A single XFF entry can't be the LB-appended pair (the LB always adds
        its own), so it isn't trusted — fall back to the direct peer."""
        request = _make_request(
            headers={"x-forwarded-for": "203.0.113.7"},
            client=("10.0.0.1", 5000),
        )
        assert get_client_ip(request) == "10.0.0.1"

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

    def test_prefers_cf_connecting_ip_behind_cloudflare(self) -> None:
        """Behind Cloudflare Tunnel the app sees the tunnel peer and a
        single-entry XFF; the true client IP is in CF-Connecting-IP and must be
        used instead of collapsing every visitor to the tunnel peer."""
        request = _make_request(
            headers={
                "cf-connecting-ip": "203.0.113.7",
                "x-forwarded-for": "203.0.113.7",
            },
            client=("172.18.0.5", 5000),
        )
        assert get_client_ip(request) == "203.0.113.7"

    def test_cf_connecting_ip_takes_precedence_over_xff_pair(self) -> None:
        """When both a CF header and a GCP-style XFF pair are present, the
        Cloudflare header wins (Cloudflare is the active front)."""
        request = _make_request(
            headers={
                "cf-connecting-ip": "198.51.100.9",
                "x-forwarded-for": "203.0.113.7, 35.191.0.1",
            },
            client=("10.0.0.1", 5000),
        )
        assert get_client_ip(request) == "198.51.100.9"

    def test_blank_cf_connecting_ip_falls_through_to_xff(self) -> None:
        """An empty CF header must not shadow the GCP LB path."""
        request = _make_request(
            headers={
                "cf-connecting-ip": "  ",
                "x-forwarded-for": "203.0.113.7, 35.191.0.1",
            },
            client=("10.0.0.1", 5000),
        )
        assert get_client_ip(request) == "203.0.113.7"


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
