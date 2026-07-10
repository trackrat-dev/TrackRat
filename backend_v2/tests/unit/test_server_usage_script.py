"""Unit tests for the repo-root ``scripts/server-usage.py`` usage report.

This ops script lives at the repository root (outside the ``trackrat`` package)
and has a hyphenated filename, so it is loaded by file path via ``importlib``
rather than a normal import. The tests cover the pure analysis helpers that back
the daily usage report: user-agent parsing, client-class mapping, and the
per-client-class (iOS app vs web app vs other) breakout derived from
load-balancer log entries.
"""

import importlib.util
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "server-usage.py"


@pytest.fixture(scope="module")
def su():
    """Load scripts/server-usage.py as an importable module."""
    assert _SCRIPT_PATH.exists(), f"missing script: {_SCRIPT_PATH}"
    spec = importlib.util.spec_from_file_location("server_usage", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _entry(path, ua, *, status=200, latency="0.05s", ip="1.1.1.1", query=""):
    """Build a minimal GCP load-balancer log entry for analysis."""
    url = f"https://apiv2.trackrat.net{path}"
    if query:
        url = f"{url}?{query}"
    return {
        "httpRequest": {
            "requestUrl": url,
            "userAgent": ua,
            "status": status,
            "latency": latency,
            "remoteIp": ip,
        }
    }


# Realistic user-agent samples.
_IOS_UA = "TrackRat/230 CFNetwork/1490.0.4 Darwin/23.4.0"
_WEB_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15"
)
_CURL_UA = "curl/8.4.0"


def test_parse_user_agent_labels(su):
    """iOS, browser, curl, and empty agents map to distinct labels."""
    assert su.parse_user_agent(_IOS_UA) == "iOS/230"
    assert su.parse_user_agent(_WEB_UA) == "browser"
    assert su.parse_user_agent(_CURL_UA) == "curl"
    assert su.parse_user_agent("") == "unknown"


def test_client_class_mapping(su):
    """Client-class collapses labels into ios / web / other buckets."""
    assert su.client_class("iOS/230") == "ios"
    assert su.client_class("iOS/191") == "ios"
    assert su.client_class("browser") == "web"
    assert su.client_class("curl") == "other"
    assert su.client_class("go-scanner") == "other"
    assert su.client_class("gcp-healthcheck") == "other"
    assert su.client_class("unknown") == "other"


def test_analyze_lb_entries_splits_ios_web_and_other(su):
    """The breakout separates iOS/web/other by requests, users, and routes."""
    station_names = {"NY": "New York Penn", "TR": "Trenton", "NP": "Newark Penn"}
    entries = [
        # iOS user A searches NY -> TR twice (same device / IP).
        _entry("/api/v2/trains/departures", _IOS_UA, ip="10.0.0.1", query="from=NY&to=TR"),
        _entry("/api/v2/trains/departures", _IOS_UA, ip="10.0.0.1", query="from=NY&to=TR"),
        # iOS user B searches NP -> NY once.
        _entry("/api/v2/trains/departures", _IOS_UA, ip="10.0.0.2", query="from=NP&to=NY"),
        # Web user C searches NY -> TR and views a train detail.
        _entry("/api/v2/trains/departures", _WEB_UA, ip="10.0.0.3", query="from=NY&to=TR"),
        _entry("/api/v2/trains/1234", _WEB_UA, ip="10.0.0.3"),
        # Other: a curl departures call from D.
        _entry("/api/v2/trains/departures", _CURL_UA, ip="10.0.0.4", query="from=NY&to=TR"),
        # Noise: a health check and a scanner probe (must not count as API).
        _entry("/health", "GoogleStackdriver_UptimeCheck", ip="10.0.0.9"),
        _entry("/wp-login.php", "Go-http-client/1.1", ip="10.0.0.9"),
    ]

    result = su.analyze_lb_entries(entries, station_names)

    # Six real API requests; noise excluded.
    assert result["total_api"] == 6
    assert result["healthcheck_count"] == 1
    assert result["scanner_count"] == 1
    assert result["unique_ips"] == 4

    cb = result["client_breakdown"]

    ios = cb["ios"]
    assert ios["requests"] == 3
    assert ios["unique_users"] == 2  # 10.0.0.1 and 10.0.0.2
    assert ios["routes"]["New York Penn -> Trenton"] == 2
    assert ios["routes"]["Newark Penn -> New York Penn"] == 1

    web = cb["web"]
    assert web["requests"] == 2
    assert web["unique_users"] == 1
    assert web["routes"]["New York Penn -> Trenton"] == 1
    assert web["endpoints"]["train_detail"] == 1

    other = cb["other"]
    assert other["requests"] == 1
    assert other["unique_users"] == 1
    assert other["routes"]["New York Penn -> Trenton"] == 1


def test_json_report_includes_client_breakdown(su):
    """build_json_report surfaces the iOS/web/other split as plain dicts."""
    station_names = {"NY": "New York Penn", "TR": "Trenton"}
    entries = [
        _entry("/api/v2/trains/departures", _IOS_UA, ip="10.0.0.1", query="from=NY&to=TR"),
        _entry("/api/v2/trains/departures", _WEB_UA, ip="10.0.0.3", query="from=NY&to=TR"),
    ]
    lb = su.analyze_lb_entries(entries, station_names)
    app_analysis = su.analyze_app_logs([], [], [])

    report = su.build_json_report("production", 24, {}, {}, lb, app_analysis)

    breakdown = report["api_traffic"]["client_breakdown"]
    assert breakdown["ios"]["requests"] == 1
    assert breakdown["ios"]["unique_users"] == 1
    assert breakdown["ios"]["top_routes"] == {"New York Penn -> Trenton": 1}
    assert breakdown["web"]["requests"] == 1
    # Serializable: no Counter/set instances leak into the JSON payload.
    assert isinstance(breakdown["ios"]["top_routes"], dict)
    assert isinstance(breakdown["web"]["endpoints"], dict)
