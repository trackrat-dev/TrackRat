"""
Tests for in-memory request statistics tracking.

Validates that RequestStats correctly counts requests, classifies user agents,
tracks route searches, computes latency percentiles, supports time-windowed
queries, iOS-only filtering, per-IP tracking, and latency trend bucketing.
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

    def _make_request(self, stats, **kwargs):
        """Helper to record a request with sensible defaults."""
        defaults = {
            "path_template": "/test",
            "status_code": 200,
            "user_agent": "curl/7",
            "duration": 0.01,
            "client_ip": "1.2.3.4",
        }
        defaults.update(kwargs)
        stats.record_request(**defaults)

    def test_record_increments_total(self):
        stats = RequestStats()
        self._make_request(stats, path_template="/api/v2/trains/departures")
        snap = stats.snapshot()
        assert snap["total_requests"] == 1

    def test_record_tracks_path(self):
        stats = RequestStats()
        self._make_request(stats, path_template="/api/v2/trains/departures")
        self._make_request(stats, path_template="/api/v2/trains/{train_id}")
        self._make_request(stats, path_template="/api/v2/trains/departures")

        snap = stats.snapshot()
        assert snap["requests_by_path"]["/api/v2/trains/departures"] == 2
        assert snap["requests_by_path"]["/api/v2/trains/{train_id}"] == 1

    def test_record_tracks_status_codes(self):
        stats = RequestStats()
        for _ in range(3):
            self._make_request(stats, status_code=200)
        self._make_request(stats, status_code=404)

        snap = stats.snapshot()
        assert snap["requests_by_status"][200] == 3
        assert snap["requests_by_status"][404] == 1

    def test_record_classifies_clients(self):
        stats = RequestStats()
        self._make_request(stats, user_agent="TrackRat/230 CFNetwork/1568")
        self._make_request(stats, user_agent="curl/7.88")

        snap = stats.snapshot()
        assert snap["requests_by_client"]["iOS/230"] == 1
        assert snap["requests_by_client"]["curl"] == 1

    def test_route_search_tracking(self):
        """Route searches are captured from departures endpoint query params."""
        stats = RequestStats()
        self._make_request(
            stats,
            path_template="/api/v2/trains/departures",
            user_agent="TrackRat/230",
            duration=0.05,
            query_params={"from": "NY", "to": "TR"},
        )
        self._make_request(
            stats,
            path_template="/api/v2/trains/departures",
            user_agent="TrackRat/230",
            duration=0.04,
            query_params={"from": "NY", "to": "TR"},
        )
        self._make_request(
            stats,
            path_template="/api/v2/trains/departures",
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
        self._make_request(
            stats,
            path_template="/api/v2/trains/{train_id}",
            query_params={"from": "NY", "to": "TR"},
        )

        snap = stats.snapshot()
        assert len(snap["route_searches"]) == 0

    def test_route_search_requires_both_params(self):
        """Route search only tracked when both from and to are present."""
        stats = RequestStats()
        self._make_request(
            stats,
            path_template="/api/v2/trains/departures",
            query_params={"from": "NY"},
        )

        snap = stats.snapshot()
        assert len(snap["route_searches"]) == 0

    def test_latency_statistics(self):
        """Latency stats compute avg, p50, p95, max correctly."""
        stats = RequestStats()
        for i in range(100):
            self._make_request(stats, duration=i * 0.01)

        snap = stats.snapshot()
        lat = snap["latency"]["/test"]
        assert lat["count"] == 100
        assert abs(lat["avg"] - 0.495) < 0.01
        assert abs(lat["p50"] - 0.50) < 1e-9
        assert abs(lat["p95"] - 0.95) < 1e-9
        assert abs(lat["max"] - 0.99) < 1e-9

    def test_snapshot_uptime(self):
        """Snapshot includes uptime that increases over time."""
        stats = RequestStats(start_time=time.time() - 120)
        snap = stats.snapshot()
        assert snap["uptime_seconds"] >= 119

    def test_snapshot_returns_copy(self):
        """Snapshot data is independent of ongoing recording."""
        stats = RequestStats()
        self._make_request(stats)
        snap1 = stats.snapshot()

        self._make_request(stats)
        snap2 = stats.snapshot()

        assert snap1["total_requests"] == 1
        assert snap2["total_requests"] == 2

    def test_no_query_params(self):
        """Recording without query_params doesn't error."""
        stats = RequestStats()
        self._make_request(
            stats,
            path_template="/api/v2/trains/departures",
            query_params=None,
        )
        snap = stats.snapshot()
        assert snap["total_requests"] == 1


class TestTimeWindowedSnapshot:
    """Tests for time-windowed filtering via snapshot(hours=N)."""

    def _make_request(self, stats, **kwargs):
        defaults = {
            "path_template": "/test",
            "status_code": 200,
            "user_agent": "curl/7",
            "duration": 0.01,
            "client_ip": "1.2.3.4",
        }
        defaults.update(kwargs)
        stats.record_request(**defaults)

    def test_hours_filter_excludes_old_records(self):
        """snapshot(hours=1) excludes records older than 1 hour."""
        stats = RequestStats()

        # Record a request, then manually backdate it
        self._make_request(stats)
        with stats._lock:
            stats._records[-1].timestamp = time.time() - 7200  # 2 hours ago

        # Record a recent request
        self._make_request(stats)

        snap_all = stats.snapshot()
        snap_1h = stats.snapshot(hours=1)

        assert snap_all["total_requests"] == 2, (
            f"Expected 2 total requests, got {snap_all['total_requests']}"
        )
        assert snap_1h["total_requests"] == 1, (
            f"Expected 1 request in 1h window, got {snap_1h['total_requests']}"
        )
        assert snap_1h["window_hours"] == 1

    def test_hours_none_returns_all(self):
        """snapshot(hours=None) returns all records (default behavior)."""
        stats = RequestStats()
        self._make_request(stats)
        with stats._lock:
            stats._records[-1].timestamp = time.time() - 86400  # 24h ago

        self._make_request(stats)

        snap = stats.snapshot(hours=None)
        assert snap["total_requests"] == 2
        assert "window_hours" not in snap

    def test_hours_filter_applies_to_all_aggregations(self):
        """Time window affects paths, status codes, clients, and route searches."""
        stats = RequestStats()

        # Old request (2h ago)
        self._make_request(
            stats,
            path_template="/old",
            status_code=500,
            user_agent="curl/7",
            client_ip="10.0.0.1",
        )
        with stats._lock:
            stats._records[-1].timestamp = time.time() - 7200

        # Recent request
        self._make_request(
            stats,
            path_template="/new",
            status_code=200,
            user_agent="TrackRat/230",
            client_ip="10.0.0.2",
        )

        snap = stats.snapshot(hours=1)
        assert "/old" not in snap["requests_by_path"], (
            f"Old path should be excluded, got: {snap['requests_by_path']}"
        )
        assert snap["requests_by_path"]["/new"] == 1
        assert 500 not in snap["requests_by_status"]
        assert snap["requests_by_status"][200] == 1
        assert "curl" not in snap["requests_by_client"]
        assert snap["requests_by_client"]["iOS/230"] == 1


class TestIosOnlyFilter:
    """Tests for iOS-only filtering via snapshot(ios_only=True)."""

    def _make_request(self, stats, **kwargs):
        defaults = {
            "path_template": "/test",
            "status_code": 200,
            "user_agent": "curl/7",
            "duration": 0.01,
            "client_ip": "1.2.3.4",
        }
        defaults.update(kwargs)
        stats.record_request(**defaults)

    def test_ios_only_filters_non_ios(self):
        """Only iOS client requests are included when ios_only=True."""
        stats = RequestStats()
        self._make_request(stats, user_agent="TrackRat/230", client_ip="10.0.0.1")
        self._make_request(stats, user_agent="curl/7.88", client_ip="10.0.0.2")
        self._make_request(stats, user_agent="TrackRat/191", client_ip="10.0.0.3")
        self._make_request(
            stats, user_agent="Mozilla/5.0 Chrome/120", client_ip="10.0.0.4"
        )

        snap = stats.snapshot(ios_only=True)
        assert snap["total_requests"] == 2, (
            f"Expected 2 iOS requests, got {snap['total_requests']}"
        )
        assert snap["ios_only"] is True
        assert "curl" not in snap["requests_by_client"]
        assert "browser" not in snap["requests_by_client"]

    def test_ios_only_false_includes_all(self):
        """ios_only=False includes all client types."""
        stats = RequestStats()
        self._make_request(stats, user_agent="TrackRat/230")
        self._make_request(stats, user_agent="curl/7")

        snap = stats.snapshot(ios_only=False)
        assert snap["total_requests"] == 2
        assert "ios_only" not in snap

    def test_ios_only_combined_with_hours(self):
        """Both filters can be applied simultaneously."""
        stats = RequestStats()

        # Old iOS request
        self._make_request(stats, user_agent="TrackRat/230", client_ip="10.0.0.1")
        with stats._lock:
            stats._records[-1].timestamp = time.time() - 7200

        # Recent iOS request
        self._make_request(stats, user_agent="TrackRat/230", client_ip="10.0.0.2")
        # Recent non-iOS request
        self._make_request(stats, user_agent="curl/7", client_ip="10.0.0.3")

        snap = stats.snapshot(hours=1, ios_only=True)
        assert snap["total_requests"] == 1, (
            f"Expected 1 recent iOS request, got {snap['total_requests']}"
        )
        assert snap["window_hours"] == 1
        assert snap["ios_only"] is True


class TestIpTracking:
    """Tests for per-client-IP tracking."""

    def _make_request(self, stats, **kwargs):
        defaults = {
            "path_template": "/test",
            "status_code": 200,
            "user_agent": "TrackRat/230",
            "duration": 0.01,
            "client_ip": "1.2.3.4",
        }
        defaults.update(kwargs)
        stats.record_request(**defaults)

    def test_requests_by_ip_populated(self):
        """requests_by_ip counts requests per IP address."""
        stats = RequestStats()
        self._make_request(stats, client_ip="10.0.0.1")
        self._make_request(stats, client_ip="10.0.0.1")
        self._make_request(stats, client_ip="10.0.0.2")

        snap = stats.snapshot()
        assert snap["requests_by_ip"]["10.0.0.1"] == 2, (
            f"Expected 2 requests from 10.0.0.1, got {snap['requests_by_ip']}"
        )
        assert snap["requests_by_ip"]["10.0.0.2"] == 1

    def test_unique_ips_count(self):
        """unique_ips reflects distinct IP addresses."""
        stats = RequestStats()
        self._make_request(stats, client_ip="10.0.0.1")
        self._make_request(stats, client_ip="10.0.0.1")
        self._make_request(stats, client_ip="10.0.0.2")
        self._make_request(stats, client_ip="10.0.0.3")

        snap = stats.snapshot()
        assert snap["unique_ips"] == 3, (
            f"Expected 3 unique IPs, got {snap['unique_ips']}"
        )

    def test_default_ip_when_not_provided(self):
        """Default client_ip is 'unknown' when not provided."""
        stats = RequestStats()
        stats.record_request(
            path_template="/test",
            status_code=200,
            user_agent="curl/7",
            duration=0.01,
        )

        snap = stats.snapshot()
        assert "unknown" in snap["requests_by_ip"]

    def test_ip_filtering_with_ios_only(self):
        """IP counts respect the ios_only filter."""
        stats = RequestStats()
        self._make_request(stats, user_agent="TrackRat/230", client_ip="10.0.0.1")
        self._make_request(stats, user_agent="curl/7", client_ip="10.0.0.2")
        self._make_request(stats, user_agent="TrackRat/191", client_ip="10.0.0.3")

        snap = stats.snapshot(ios_only=True)
        assert snap["unique_ips"] == 2, (
            f"Expected 2 unique iOS IPs, got {snap['unique_ips']}"
        )
        assert "10.0.0.2" not in snap["requests_by_ip"], (
            "Non-iOS IP should be excluded"
        )


class TestLatencyTrend:
    """Tests for latency trend bucketing."""

    def _make_request(self, stats, **kwargs):
        defaults = {
            "path_template": "/test",
            "status_code": 200,
            "user_agent": "curl/7",
            "duration": 0.01,
            "client_ip": "1.2.3.4",
        }
        defaults.update(kwargs)
        stats.record_request(**defaults)

    def test_trend_present_in_snapshot(self):
        """latency_trend key is present in snapshot output."""
        stats = RequestStats()
        self._make_request(stats, duration=0.05)

        snap = stats.snapshot()
        assert "latency_trend" in snap, "latency_trend should be in snapshot"
        assert "/test" in snap["latency_trend"], (
            f"Expected /test in trend data, got: {list(snap['latency_trend'].keys())}"
        )

    def test_trend_has_12_buckets(self):
        """Each path in latency_trend has exactly 12 five-minute buckets."""
        stats = RequestStats()
        self._make_request(stats, duration=0.05)

        snap = stats.snapshot()
        trend = snap["latency_trend"]["/test"]
        assert len(trend) == 12, (
            f"Expected 12 trend buckets, got {len(trend)}"
        )

    def test_trend_bucket_structure(self):
        """Each trend bucket has bucket, avg_ms, and count keys."""
        stats = RequestStats()
        self._make_request(stats, duration=0.1)

        snap = stats.snapshot()
        trend = snap["latency_trend"]["/test"]

        # Find the bucket with data (should be the last one since request is recent)
        non_empty = [b for b in trend if b["count"] > 0]
        assert len(non_empty) >= 1, "Should have at least one non-empty bucket"

        bucket = non_empty[0]
        assert "bucket" in bucket
        assert "avg_ms" in bucket
        assert "count" in bucket
        assert bucket["avg_ms"] > 0, (
            f"Expected positive avg_ms, got {bucket['avg_ms']}"
        )
        assert bucket["count"] >= 1

    def test_trend_avg_ms_calculation(self):
        """Trend bucket avg_ms is correctly computed from durations."""
        stats = RequestStats()
        # Record 3 requests with known durations — they'll fall in the same bucket
        self._make_request(stats, duration=0.1)
        self._make_request(stats, duration=0.2)
        self._make_request(stats, duration=0.3)

        snap = stats.snapshot()
        trend = snap["latency_trend"]["/test"]
        non_empty = [b for b in trend if b["count"] > 0]
        assert len(non_empty) == 1

        bucket = non_empty[0]
        assert bucket["count"] == 3
        expected_avg_ms = (0.1 + 0.2 + 0.3) / 3 * 1000  # 200ms
        assert abs(bucket["avg_ms"] - expected_avg_ms) < 0.1, (
            f"Expected avg_ms ≈ {expected_avg_ms}, got {bucket['avg_ms']}"
        )

    def test_trend_empty_when_no_requests(self):
        """latency_trend is empty dict when no requests recorded."""
        stats = RequestStats()
        snap = stats.snapshot()
        assert snap["latency_trend"] == {}


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
