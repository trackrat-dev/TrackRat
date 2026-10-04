"""Tests for the structured ``http_request`` log emitted per inbound request.

Production and staging are fronted by the Cloudflare Tunnel, so no load
balancer records API traffic. ``request_stats_middleware`` therefore logs one
``http_request`` event per request, and ``scripts/server-usage.py`` builds the
traffic section of the usage report from those events (#1759). These tests pin
the fields that report reads, the client attribution behind the tunnel, and
that no request — including one that crashes its handler — goes unrecorded.
"""

import pytest
from structlog.testing import capture_logs

from trackrat.api.telemetry import ONBOARDING_PATH
from trackrat.main import app
from trackrat.settings import get_settings

_IOS_UA = "TrackRat/230 CFNetwork/1568.200.51 Darwin/24.1.0"


def _http_request_events(captured):
    return [e for e in captured if e.get("event") == "http_request"]


def test_api_request_is_logged_with_every_field_the_report_reads(client):
    with capture_logs() as captured:
        resp = client.get(
            "/api/v2/predictions/supported-stations?from=NY&to=TR&date=2026-10-04",
            headers={
                "user-agent": _IOS_UA,
                # Behind the tunnel the socket peer is the cloudflared container,
                # so the real client only appears in this header.
                "cf-connecting-ip": "203.0.113.7",
            },
        )

    assert resp.status_code == 200, resp.text
    events = _http_request_events(captured)
    assert len(events) == 1, f"expected one http_request event, got {captured}"
    event = events[0]
    print(f"http_request event: {event}")

    assert event["environment"] == get_settings().environment
    assert event["method"] == "GET"
    assert event["path"] == "/api/v2/predictions/supported-stations"
    # Only the route-search fields survive; everything else is dropped.
    assert event["query"] == "from=NY&to=TR"
    assert event["train_id"] is None
    assert event["status_code"] == 200
    assert event["client_ip"] == "203.0.113.7"
    assert event["user_agent"] == _IOS_UA
    assert isinstance(event["duration_ms"], float)
    assert event["duration_ms"] >= 0


def test_health_and_metrics_paths_are_not_logged(client):
    """Probes would dominate a multi-hour window and crowd out real traffic."""
    with capture_logs() as captured:
        for path in ("/health/live", "/health/ready", "/health"):
            client.get(path)

    events = _http_request_events(captured)
    assert events == [], f"probe requests leaked into http_request: {events}"


def test_onboarding_beacon_is_not_logged(client):
    """The http_request event carries a client IP, so it must honor the same
    privacy contract as request_stats: the onboarding beacon stays IP-free."""
    with capture_logs() as captured:
        resp = client.post(
            ONBOARDING_PATH,
            json={"systems": "NJT"},
            headers={"cf-connecting-ip": "203.0.113.7"},
        )

    assert resp.status_code < 400, resp.text
    events = _http_request_events(captured)
    assert events == [], f"onboarding beacon logged with a client IP: {events}"
    # Not vacuous: the beacon's own event was captured, so logging was live.
    assert any(e.get("event") == "onboarding_completed" for e in captured), captured


def test_unmatched_write_request_keeps_its_method_and_status(client):
    """Scanner probes and write endpoints must keep their method and status.

    Device registrations and alert-subscription syncs are POST/PUT, and the
    report counts a request that matched no route as a scanner, so neither may
    be filtered out here. The probed path itself is not logged.
    """
    with capture_logs() as captured:
        resp = client.post(
            "/wp-login.php", headers={"user-agent": "Go-http-client/1.1"}
        )

    assert resp.status_code in (404, 405), resp.status_code
    events = _http_request_events(captured)
    assert len(events) == 1, captured
    print(f"scanner event: {events[0]}")
    assert events[0]["method"] == "POST"
    assert events[0]["path"] is None
    assert events[0]["status_code"] == resp.status_code
    assert events[0]["query"] == ""


def test_train_detail_logs_the_route_template_and_train_id(client):
    """Train views keep their train_id (public) beside the route template."""
    with capture_logs() as captured:
        client.get("/api/v2/trains/3918")

    events = _http_request_events(captured)
    assert len(events) == 1, captured
    print(f"train event: {events[0]}")
    assert events[0]["path"] == "/api/v2/trains/{train_id}"
    assert events[0]["train_id"] == "3918"


@pytest.mark.parametrize(
    ("method", "url", "template"),
    [
        (
            "GET",
            "/api/v2/alerts/subscriptions/DEVICE-SECRET-123",
            "/api/v2/alerts/subscriptions/{device_id}",
        ),
        (
            "GET",
            "/api/v2/routes/preferences?device_id=DEVICE-SECRET-123",
            "/api/v2/routes/preferences",
        ),
        (
            "DELETE",
            "/api/v2/live-activities/DEVICE-SECRET-123",
            "/api/v2/live-activities/{push_token}",
        ),
    ],
)
def test_device_identifiers_never_reach_the_log(client, method, url, template):
    """The log pairs each request with a client IP; a persistent device_id or
    push token beside it would make every device trackable from the logs."""
    with capture_logs() as captured:
        client.request(method, url)

    events = _http_request_events(captured)
    assert len(events) == 1, captured
    print(f"{method} {url} -> {events[0]}")
    assert events[0]["path"] == template
    assert "DEVICE-SECRET-123" not in repr(events[0])


@pytest.fixture
def crashing_route():
    """Register a route whose handler raises, and remove it afterwards."""
    path = "/api/v2/__test_unhandled_exception"

    async def boom():
        raise RuntimeError("handler crashed")

    app.add_api_route(path, boom)
    yield path
    app.router.routes[:] = [
        r for r in app.router.routes if getattr(r, "path", None) != path
    ]


def test_unhandled_exception_is_logged_as_500(client, crashing_route):
    """A crashing handler is what the client sees as a 500 — record it as one."""
    with capture_logs() as captured:
        with pytest.raises(RuntimeError, match="handler crashed"):
            client.get(crashing_route)

    events = _http_request_events(captured)
    assert len(events) == 1, f"crashed request went unrecorded: {captured}"
    print(f"crash event: {events[0]}")
    assert events[0]["path"] == crashing_route
    assert events[0]["status_code"] == 500
