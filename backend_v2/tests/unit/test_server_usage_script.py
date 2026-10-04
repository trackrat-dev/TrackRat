"""Unit tests for the repo-root ``scripts/server-usage.py`` usage report.

This ops script lives at the repository root (outside the ``trackrat`` package)
and has a hyphenated filename, so it is loaded by file path via ``importlib``
rather than a normal import. The tests cover the pure analysis helpers that back
the daily usage report: user-agent parsing, client-class mapping, the
per-client-class (iOS app vs web app vs other) breakout derived from the
backend's ``http_request`` log events, and the traffic-source caveats.
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


def _entry(path, ua, *, status=200, duration_ms=50.0, ip="1.1.1.1", query="",
           method="GET"):
    """Build a cos_containers ``http_request`` entry as the backend logs it.

    Field names mirror request_stats_middleware in backend_v2/src/trackrat/main.py;
    tests/unit/test_request_logging_middleware.py pins that side.
    """
    return {
        "jsonPayload": {
            "event": "http_request",
            "environment": "production",
            "method": method,
            "path": path,
            "query": query,
            "status_code": status,
            "duration_ms": duration_ms,
            "client_ip": ip,
            "user_agent": ua,
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
    assert su.client_class("unknown") == "other"


def test_analyze_request_entries_splits_ios_web_and_other(su):
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
        # Noise: a scanner probe (must not count as API).
        _entry("/wp-login.php", "Go-http-client/1.1", ip="10.0.0.9", status=404),
    ]

    result = su.analyze_request_entries(entries, station_names)

    # Six real API requests; noise excluded.
    assert result["total_api"] == 6
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


def test_trip_searches_count_as_route_searches(su):
    """/trips/search is the primary route search on both iOS and web.

    Before it was classified, every trip search fell into total_non_api, so the
    report dropped most route searches and undercounted API requests.
    """
    station_names = {"SD35": "Times Sq-42 St", "SD43": "Grand Central-42 St"}
    entries = [
        _entry("/api/v2/trips/search", _IOS_UA, ip="10.0.0.1",
               query="from=SD35&to=SD43&limit=50&hide_departed=true"),
        _entry("/api/v2/trips/search", _WEB_UA, ip="10.0.0.2",
               query="from=SD35&to=SD43&limit=50"),
        _entry("/api/v2/trains/departures", _IOS_UA, ip="10.0.0.1",
               query="from=SD35&to=SD43"),
    ]

    result = su.analyze_request_entries(entries, station_names)
    print(f"endpoint_counts={dict(result['endpoint_counts'])} "
          f"route_searches={dict(result['route_searches'])}")

    assert result["total_api"] == 3
    assert result["total_non_api"] == 0
    assert result["endpoint_counts"]["trip_search"] == 2
    assert result["endpoint_counts"]["departures"] == 1
    route = "Times Sq-42 St -> Grand Central-42 St"
    assert result["route_searches"][route] == 3
    assert result["client_breakdown"]["ios"]["routes"][route] == 2
    assert result["client_breakdown"]["web"]["routes"][route] == 1


def test_latency_and_status_come_from_the_request_event(su):
    """duration_ms is reported in seconds, and status codes are kept per request."""
    entries = [
        _entry("/api/v2/trips/search", _IOS_UA, duration_ms=1250.0, query="from=A&to=B"),
        _entry("/api/v2/trips/search", _IOS_UA, duration_ms=250.0, status=500,
               query="from=A&to=B"),
    ]

    result = su.analyze_request_entries(entries, {})

    assert sorted(result["latencies"]["trip_search"]) == [0.25, 1.25]
    assert result["status_codes"] == {200: 1, 500: 1}


def test_report_reads_the_events_the_backend_actually_logs(su, client):
    """Contract test: the backend's real http_request event feeds the report.

    The middleware and this script live in different trees and agree on field
    names only by convention; renaming one side would silently zero the report.
    The event is captured from a real request and wrapped the way Cloud Logging
    delivers a cos_containers JSON line (fields under ``jsonPayload``).
    """
    from structlog.testing import capture_logs

    with capture_logs() as captured:
        resp = client.get(
            "/api/v2/predictions/supported-stations?from=NY&to=TR",
            headers={"user-agent": _IOS_UA, "cf-connecting-ip": "203.0.113.7"},
        )
    assert resp.status_code == 200, resp.text
    events = [e for e in captured if e.get("event") == "http_request"]
    assert len(events) == 1, captured

    result = su.analyze_request_entries(
        [{"jsonPayload": events[0]}], {"NY": "New York Penn", "TR": "Trenton"}
    )
    print(f"event={events[0]} -> endpoint_counts={dict(result['endpoint_counts'])}")

    assert result["total_api"] == 1
    assert result["endpoint_counts"]["prediction_stations"] == 1
    assert result["status_codes"] == {200: 1}
    assert result["unique_ips"] == 1
    ios = result["client_breakdown"]["ios"]
    assert ios["requests"] == 1 and ios["unique_users"] == 1
    lat = result["latencies"]["prediction_stations"][0]
    assert 0 <= lat < 60, f"duration not converted to seconds: {lat}"


def test_json_report_includes_client_breakdown(su):
    """build_json_report surfaces the iOS/web/other split as plain dicts."""
    station_names = {"NY": "New York Penn", "TR": "Trenton"}
    entries = [
        _entry("/api/v2/trains/departures", _IOS_UA, ip="10.0.0.1", query="from=NY&to=TR"),
        _entry("/api/v2/trains/departures", _WEB_UA, ip="10.0.0.3", query="from=NY&to=TR"),
    ]
    analysis = su.analyze_request_entries(entries, station_names)
    app_analysis = su.analyze_app_logs([], [], [])

    report = su.build_json_report("production", 24, {}, {}, analysis, app_analysis)

    breakdown = report["api_traffic"]["client_breakdown"]
    assert breakdown["ios"]["requests"] == 1
    assert breakdown["ios"]["unique_users"] == 1
    assert breakdown["ios"]["top_routes"] == {"New York Penn -> Trenton": 1}
    assert breakdown["web"]["requests"] == 1
    # Serializable: no Counter/set instances leak into the JSON payload.
    assert isinstance(breakdown["ios"]["top_routes"], dict)
    assert isinstance(breakdown["web"]["endpoints"], dict)


# ---------------------------------------------------------------------------
# Traffic-source caveats
#
# The traffic section is built from the backend's http_request events. An empty
# window cannot tell "nobody used the server" from "nothing was logged", and a
# truncated query covers only the newest slice of the window — rendering either
# as bare counts states as fact something the report cannot know.
# ---------------------------------------------------------------------------
def test_traffic_note_absent_for_a_complete_window(su):
    """A window with entries and no truncation carries no caveat."""
    assert su.traffic_source_note(1, False) is None
    assert su.traffic_source_note(4200, False) is None


def test_traffic_note_for_an_empty_window(su):
    """Zero entries is reported as missing data, not as zero traffic."""
    note = su.traffic_source_note(0, False)

    assert note is not None
    assert "No http_request log entries" in note
    assert "not because nobody used the server" in note


def test_traffic_note_for_a_truncated_window(su):
    """A truncated query must say its counts cover only part of the window."""
    note = su.traffic_source_note(20000, True)

    assert note is not None, "truncated window rendered without a caveat"
    assert "20000 entries" in note
    assert "only the most recent part of this window" in note
    # Entries were counted; the wording must not claim an empty window.
    assert "No http_request" not in note


def test_json_report_carries_the_traffic_warning(su):
    """The JSON the daily Routine consumes exposes the caveat next to the zeros."""
    analysis = su.analyze_request_entries([], {})
    app_analysis = su.analyze_app_logs([], [], [])
    note = su.traffic_source_note(0, False)

    report = su.build_json_report(
        "production", 24, {}, {}, analysis, app_analysis, traffic_note=note
    )

    assert report["api_traffic"]["total_requests"] == 0
    assert report["traffic_source_warning"] == note


def test_json_report_omits_the_warning_on_a_complete_window(su):
    """A production report with traffic reports no warning at all."""
    entries = [_entry("/api/v2/trains/departures", _IOS_UA, query="from=NY&to=TR")]
    analysis = su.analyze_request_entries(entries, {"NY": "New York Penn", "TR": "Trenton"})
    app_analysis = su.analyze_app_logs([], [], [])

    report = su.build_json_report(
        "production", 1, {}, {}, analysis, app_analysis,
        traffic_note=su.traffic_source_note(len(entries), False),
    )

    assert report["api_traffic"]["total_requests"] == 1
    assert report["traffic_source_warning"] is None


def test_text_report_prints_the_warning_above_the_counts(su):
    """The rendered report surfaces the caveat inside the API TRAFFIC section."""
    analysis = su.analyze_request_entries([], {})
    app_analysis = su.analyze_app_logs([], [], [])
    note = su.traffic_source_note(0, False)

    text = su.format_report(
        "production", 24, {}, {}, analysis, app_analysis, use_color=False,
        traffic_note=note,
    )

    # "WARNING: " with the colon — a bare "WARNING" would also match the
    # unrelated "ERRORS & WARNINGS" section header and pass vacuously.
    assert "WARNING: " in text
    assert "No http_request log entries" in text
    # The caveat precedes the count it qualifies.
    assert text.index("No http_request log entries") < text.index("API requests:")


def test_text_report_unchanged_when_traffic_is_real(su):
    """No caveat leaks into an ordinary report with traffic."""
    entries = [_entry("/api/v2/trains/departures", _IOS_UA, query="from=NY&to=TR")]
    analysis = su.analyze_request_entries(entries, {"NY": "New York Penn", "TR": "Trenton"})
    app_analysis = su.analyze_app_logs([], [], [])

    text = su.format_report(
        "production", 1, {}, {}, analysis, app_analysis, use_color=False,
        traffic_note=su.traffic_source_note(len(entries), False),
    )

    # "WARNING: " with the colon — the report always contains an unrelated
    # "ERRORS & WARNINGS" header, so a bare "WARNING" could never be absent.
    assert "WARNING: " not in text
    assert "API requests:     1" in text
    assert "Route Searches (1 total)" in text


def test_api_urls_point_at_universal_ssl_covered_hosts(su):
    """Both API hosts sit one label below the apex, which Universal SSL covers.

    Cloudflare Universal SSL's SANs are trackrat.net and *.trackrat.net, and a
    wildcard matches a single label — the constraint that forced staging off
    staging.apiv2.trackrat.net.
    """
    for env, url in su.API_URLS.items():
        host = url.split("://", 1)[1].split("/", 1)[0]
        assert host.endswith(".trackrat.net"), f"{env}: {host}"
        labels_below_apex = host[: -len(".trackrat.net")].split(".")
        assert len(labels_below_apex) == 1, f"{env}: {host} is more than one label deep"
