"""
Tests for in-memory request statistics tracking.

Validates that RequestStats correctly counts requests, classifies user agents,
tracks route searches, and computes latency percentiles.
"""

import time
from trackrat.utils.request_stats import (
    RequestStats,
    _classify_user_agent,
    reset_request_stats,
    get_request_stats,
)


class TestClassifyUserAgent:
    """Tests for User-Agent string classification."""

    def test_ios_app_with_build_number(self):
        ua = "TrackRat/230 CFNetwork/1568.200.51 Darwin/24.1.0"
        assert _classify_user_agent(ua) == "iOS/230"

    def test_ios_app_different_version(self):
        ua = "TrackRat/191 CFNetwork/1485 Darwin/23.1.0"
        assert _classify_user_agent(ua) == "iOS/191"

    def test_curl(self):
        assert _classify_user_agent("curl/7.88.1") == "curl"

    def test_curl_case_insensitive(self):
        assert _classify_user_agent("Curl/8.0") == "curl"

    def test_browser_chrome(self):
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0"
        assert _classify_user_agent(ua) == "browser"

    def test_browser_safari(self):
        ua = "Safari/605.1.15"
        assert _classify_user_agent(ua) == "browser"

    def test_scanner_go_http(self):
        assert _classify_user_agent("Go-http-client/2.0") == "scanner"

    def test_scanner_python_requests(self):
        assert _classify_user_agent("python-requests/2.31.0") == "scanner"

    def test_scanner_nuclei(self):
        assert _classify_user_agent("Nuclei - Open-source project") == "scanner"

    def test_scanner_zgrab(self):
        assert _classify_user_agent("zgrab/0.x") == "scanner"

    def test_scanner_bot(self):
        assert _classify_user_agent("Googlebot/2.1") == "scanner"

    def test_empty_string(self):
        assert _classify_user_agent("") == "unknown"

    def test_unknown_agent(self):
        assert _classify_user_agent("some-custom-tool/1.0") == "other"


class TestRequestStats:
    """Tests for the RequestStats data structure."""

    def test_record_increments_total(self):
        stats = RequestStats()
        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="curl/7.88",
            duration=0.05,
        )
        assert stats.total_requests == 1

    def test_record_tracks_path(self):
        stats = RequestStats()
        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="curl/7.88",
            duration=0.05,
        )
        stats.record_request(
            path_template="/api/v2/trains/{train_id}",
            status_code=200,
            user_agent="curl/7.88",
            duration=0.03,
        )
        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="curl/7.88",
            duration=0.04,
        )

        snap = stats.snapshot()
        assert snap["requests_by_path"]["/api/v2/trains/departures"] == 2
        assert snap["requests_by_path"]["/api/v2/trains/{train_id}"] == 1

    def test_record_tracks_status_codes(self):
        stats = RequestStats()
        for _ in range(3):
            stats.record_request(
                path_template="/test",
                status_code=200,
                user_agent="curl/7",
                duration=0.01,
            )
        stats.record_request(
            path_template="/test",
            status_code=404,
            user_agent="curl/7",
            duration=0.01,
        )

        snap = stats.snapshot()
        assert snap["requests_by_status"][200] == 3
        assert snap["requests_by_status"][404] == 1

    def test_record_classifies_clients(self):
        stats = RequestStats()
        stats.record_request(
            path_template="/test",
            status_code=200,
            user_agent="TrackRat/230 CFNetwork/1568",
            duration=0.01,
        )
        stats.record_request(
            path_template="/test",
            status_code=200,
            user_agent="curl/7.88",
            duration=0.01,
        )

        snap = stats.snapshot()
        assert snap["requests_by_client"]["iOS/230"] == 1
        assert snap["requests_by_client"]["curl"] == 1

    def test_route_search_tracking(self):
        """Route searches are captured from departures endpoint query params."""
        stats = RequestStats()
        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="TrackRat/230",
            duration=0.05,
            query_params={"from": "NY", "to": "TR"},
        )
        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="TrackRat/230",
            duration=0.04,
            query_params={"from": "NY", "to": "TR"},
        )
        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="TrackRat/230",
            duration=0.03,
            query_params={"from": "NP", "to": "NY"},
        )

        snap = stats.snapshot()
        searches = {(e["from"], e["to"]): e["count"] for e in snap["route_searches"]}
        assert searches[("NY", "TR")] == 2
        assert searches[("NP", "NY")] == 1

    def test_route_search_not_tracked_for_other_endpoints(self):
        """Only /departures endpoint triggers route search tracking."""
        stats = RequestStats()
        stats.record_request(
            path_template="/api/v2/trains/{train_id}",
            status_code=200,
            user_agent="curl/7",
            duration=0.01,
            query_params={"from": "NY", "to": "TR"},
        )

        snap = stats.snapshot()
        assert len(snap["route_searches"]) == 0

    def test_route_search_requires_both_params(self):
        """Route search only tracked when both from and to are present."""
        stats = RequestStats()
        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="curl/7",
            duration=0.01,
            query_params={"from": "NY"},
        )

        snap = stats.snapshot()
        assert len(snap["route_searches"]) == 0

    def test_latency_statistics(self):
        """Latency stats compute avg, p50, p95, max correctly."""
        stats = RequestStats()
        # Add 100 requests with known durations
        for i in range(100):
            stats.record_request(
                path_template="/test",
                status_code=200,
                user_agent="curl/7",
                duration=i * 0.01,  # 0.00 to 0.99
            )

        snap = stats.snapshot()
        lat = snap["latency"]["/test"]
        assert lat["count"] == 100
        assert abs(lat["avg"] - 0.495) < 0.01  # mean of 0..99 * 0.01
        assert abs(lat["p50"] - 0.50) < 1e-9  # median
        assert abs(lat["p95"] - 0.95) < 1e-9  # 95th percentile
        assert abs(lat["max"] - 0.99) < 1e-9

    def test_latency_cap(self):
        """Latency samples are capped at _MAX_LATENCY_SAMPLES."""
        stats = RequestStats()
        for i in range(600):
            stats.record_request(
                path_template="/test",
                status_code=200,
                user_agent="curl/7",
                duration=0.01,
            )

        snap = stats.snapshot()
        assert snap["latency"]["/test"]["count"] == 500

    def test_snapshot_uptime(self):
        """Snapshot includes uptime that increases over time."""
        stats = RequestStats(start_time=time.time() - 120)
        snap = stats.snapshot()
        assert snap["uptime_seconds"] >= 119  # Allow for small timing variance

    def test_snapshot_returns_copy(self):
        """Snapshot data is independent of ongoing recording."""
        stats = RequestStats()
        stats.record_request(
            path_template="/test",
            status_code=200,
            user_agent="curl/7",
            duration=0.01,
        )

        snap1 = stats.snapshot()
        stats.record_request(
            path_template="/test",
            status_code=200,
            user_agent="curl/7",
            duration=0.01,
        )
        snap2 = stats.snapshot()

        assert snap1["total_requests"] == 1
        assert snap2["total_requests"] == 2

    def test_no_query_params(self):
        """Recording without query_params doesn't error."""
        stats = RequestStats()
        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="curl/7",
            duration=0.01,
            query_params=None,
        )
        assert stats.total_requests == 1


    def test_departure_result_counts(self):
        """record_departure_results tracks avg trains and empty count per route."""
        stats = RequestStats()
        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="TrackRat/230",
            duration=0.05,
            query_params={"from": "NY", "to": "TR"},
        )
        # Record result counts: 5 trains, 0 trains, 3 trains
        stats.record_departure_results("NY", "TR", 5)
        stats.record_departure_results("NY", "TR", 0)
        stats.record_departure_results("NY", "TR", 3)

        snap = stats.snapshot()
        route_entry = next(
            e for e in snap["route_searches"] if e["from"] == "NY" and e["to"] == "TR"
        )
        assert abs(route_entry["avg_trains"] - (5 + 0 + 3) / 3) < 0.01
        assert route_entry["empty_count"] == 1

    def test_departure_result_all_empty(self):
        """All-empty results correctly counted."""
        stats = RequestStats()
        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="curl/7",
            duration=0.01,
            query_params={"from": "NP", "to": "AB"},
        )
        stats.record_departure_results("NP", "AB", 0)
        stats.record_departure_results("NP", "AB", 0)

        snap = stats.snapshot()
        route_entry = next(
            e for e in snap["route_searches"] if e["from"] == "NP" and e["to"] == "AB"
        )
        assert route_entry["avg_trains"] == 0.0
        assert route_entry["empty_count"] == 2

    def test_departure_result_no_results_recorded(self):
        """Route search without result recording has no avg/empty fields."""
        stats = RequestStats()
        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="curl/7",
            duration=0.01,
            query_params={"from": "NY", "to": "TR"},
        )

        snap = stats.snapshot()
        route_entry = next(
            e for e in snap["route_searches"] if e["from"] == "NY" and e["to"] == "TR"
        )
        assert "avg_trains" not in route_entry
        assert "empty_count" not in route_entry

    def test_train_detail_view_tracking(self):
        """record_train_detail_view tracks train ID, origin, and destination."""
        stats = RequestStats()
        stats.record_train_detail_view("3254", "NY", "TR")
        stats.record_train_detail_view("3254", "NY", "TR")
        stats.record_train_detail_view("1078", "NP", "NY")

        snap = stats.snapshot()
        views = {
            (e["train_id"], e["from"], e["to"]): e["count"]
            for e in snap["train_detail_views"]
        }
        assert views[("3254", "NY", "TR")] == 2
        assert views[("1078", "NP", "NY")] == 1

    def test_train_detail_views_top_20(self):
        """Only top 20 train detail views are returned in snapshot."""
        stats = RequestStats()
        for i in range(25):
            for _ in range(i + 1):  # Different counts so ordering is deterministic
                stats.record_train_detail_view(f"T{i:03d}", "NY", "TR")

        snap = stats.snapshot()
        assert len(snap["train_detail_views"]) == 20
        # Most popular should be first (T024 with 25 views)
        assert snap["train_detail_views"][0]["train_id"] == "T024"

    def test_train_detail_views_empty(self):
        """Snapshot includes empty train_detail_views when none recorded."""
        stats = RequestStats()
        snap = stats.snapshot()
        assert snap["train_detail_views"] == []


class TestSingleton:
    """Tests for the module-level singleton."""

    def test_get_returns_same_instance(self):
        reset_request_stats()
        a = get_request_stats()
        b = get_request_stats()
        assert a is b

    def test_reset_creates_new_instance(self):
        reset_request_stats()
        a = get_request_stats()
        reset_request_stats()
        b = get_request_stats()
        assert a is not b
