"""
Tests for in-memory request statistics tracking.

Validates that RequestStats correctly counts requests, classifies user agents,
tracks route searches, computes latency percentiles, supports time-windowed
queries, iOS-only filtering, per-IP tracking, and latency trend bucketing.
"""

import time
from trackrat.utils.request_stats import (
    RequestRecord,
    RequestStats,
    _classify_user_agent,
    _compute_usage_analytics,
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

        assert (
            snap_all["total_requests"] == 2
        ), f"Expected 2 total requests, got {snap_all['total_requests']}"
        assert (
            snap_1h["total_requests"] == 1
        ), f"Expected 1 request in 1h window, got {snap_1h['total_requests']}"
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
        assert (
            "/old" not in snap["requests_by_path"]
        ), f"Old path should be excluded, got: {snap['requests_by_path']}"
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
        assert (
            snap["total_requests"] == 2
        ), f"Expected 2 iOS requests, got {snap['total_requests']}"
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
        assert (
            snap["total_requests"] == 1
        ), f"Expected 1 recent iOS request, got {snap['total_requests']}"
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
        assert (
            snap["requests_by_ip"]["10.0.0.1"] == 2
        ), f"Expected 2 requests from 10.0.0.1, got {snap['requests_by_ip']}"
        assert snap["requests_by_ip"]["10.0.0.2"] == 1

    def test_unique_ips_count(self):
        """unique_ips reflects distinct IP addresses."""
        stats = RequestStats()
        self._make_request(stats, client_ip="10.0.0.1")
        self._make_request(stats, client_ip="10.0.0.1")
        self._make_request(stats, client_ip="10.0.0.2")
        self._make_request(stats, client_ip="10.0.0.3")

        snap = stats.snapshot()
        assert (
            snap["unique_ips"] == 3
        ), f"Expected 3 unique IPs, got {snap['unique_ips']}"

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
        assert (
            snap["unique_ips"] == 2
        ), f"Expected 2 unique iOS IPs, got {snap['unique_ips']}"
        assert "10.0.0.2" not in snap["requests_by_ip"], "Non-iOS IP should be excluded"


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
        assert (
            "/test" in snap["latency_trend"]
        ), f"Expected /test in trend data, got: {list(snap['latency_trend'].keys())}"

    def test_trend_has_12_buckets(self):
        """Each path in latency_trend has exactly 12 five-minute buckets."""
        stats = RequestStats()
        self._make_request(stats, duration=0.05)

        snap = stats.snapshot()
        trend = snap["latency_trend"]["/test"]
        assert len(trend) == 12, f"Expected 12 trend buckets, got {len(trend)}"

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
        assert bucket["avg_ms"] > 0, f"Expected positive avg_ms, got {bucket['avg_ms']}"
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
        assert (
            abs(bucket["avg_ms"] - expected_avg_ms) < 0.1
        ), f"Expected avg_ms ≈ {expected_avg_ms}, got {bucket['avg_ms']}"

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


class TestUsageAnalytics:
    """Tests for _compute_usage_analytics iOS usage tracking."""

    def _make_record(
        self,
        path: str = "/api/v2/trains/departures",
        client_label: str = "iOS/230",
        client_ip: str = "10.0.0.1",
        timestamp: float | None = None,
    ) -> RequestRecord:
        return RequestRecord(
            timestamp=timestamp or time.time(),
            path_template=path,
            status_code=200,
            client_label=client_label,
            client_ip=client_ip,
            duration=0.05,
        )

    def test_empty_when_no_ios_records(self):
        """Returns empty dict when there are no iOS records at all."""
        records = [
            self._make_record(client_label="curl", client_ip="1.1.1.1"),
            self._make_record(client_label="browser", client_ip="2.2.2.2"),
        ]
        result = _compute_usage_analytics(records)
        assert result == {}, f"Expected empty dict for non-iOS records, got: {result}"

    def test_unique_users_counts_distinct_ips(self):
        """unique_users is the count of distinct iOS client IPs."""
        records = [
            self._make_record(client_ip="10.0.0.1"),
            self._make_record(client_ip="10.0.0.1"),  # same IP
            self._make_record(client_ip="10.0.0.2"),
            self._make_record(client_ip="10.0.0.3"),
        ]
        result = _compute_usage_analytics(records)
        assert result["unique_users"] == 3, (
            f"Expected 3 unique users, got {result['unique_users']}"
        )

    def test_action_counts(self):
        """Actions are correctly counted and mapped from path templates."""
        records = [
            self._make_record(path="/api/v2/trains/departures"),
            self._make_record(path="/api/v2/trains/departures"),
            self._make_record(path="/api/v2/trains/{train_id}"),
            self._make_record(path="/api/v2/trips/search"),
        ]
        result = _compute_usage_analytics(records)
        actions_by_name = {a["action"]: a["count"] for a in result["actions"]}
        assert actions_by_name["departure_searches"] == 2, (
            f"Expected 2 departure_searches, got {actions_by_name}"
        )
        assert actions_by_name["train_detail_views"] == 1
        assert actions_by_name["trip_searches"] == 1
        assert result["total_actions"] == 4

    def test_unique_users_per_action(self):
        """Each action tracks how many unique IPs performed it."""
        records = [
            self._make_record(path="/api/v2/trains/departures", client_ip="10.0.0.1"),
            self._make_record(path="/api/v2/trains/departures", client_ip="10.0.0.1"),
            self._make_record(path="/api/v2/trains/departures", client_ip="10.0.0.2"),
            self._make_record(path="/api/v2/trains/{train_id}", client_ip="10.0.0.1"),
        ]
        result = _compute_usage_analytics(records)
        actions_by_name = {a["action"]: a for a in result["actions"]}

        dep = actions_by_name["departure_searches"]
        assert dep["count"] == 3, f"Expected 3 departure search count, got {dep['count']}"
        assert dep["unique_users"] == 2, (
            f"Expected 2 unique users for departures, got {dep['unique_users']}"
        )

        detail = actions_by_name["train_detail_views"]
        assert detail["unique_users"] == 1

    def test_non_ios_records_ignored(self):
        """Non-iOS records are excluded from analytics."""
        records = [
            self._make_record(client_label="iOS/230", client_ip="10.0.0.1"),
            self._make_record(client_label="curl", client_ip="10.0.0.2"),
            self._make_record(client_label="browser", client_ip="10.0.0.3"),
        ]
        result = _compute_usage_analytics(records)
        assert result["unique_users"] == 1, (
            f"Expected 1 iOS user, got {result['unique_users']}"
        )

    def test_unmapped_paths_not_counted_as_actions(self):
        """Paths not in _ACTION_MAP don't appear in actions list."""
        records = [
            self._make_record(path="/admin/stats"),
            self._make_record(path="/health"),
        ]
        result = _compute_usage_analytics(records)
        assert result["actions"] == [], (
            f"Expected no actions for unmapped paths, got {result['actions']}"
        )
        assert result["total_actions"] == 0
        # But unique_users should still be counted (we saw iOS traffic)
        assert result["unique_users"] == 1

    def test_prediction_paths_merged(self):
        """Multiple prediction paths map to single 'prediction_lookups' action."""
        records = [
            self._make_record(path="/api/v2/predictions/track"),
            self._make_record(path="/api/v2/predictions/delay"),
            self._make_record(path="/api/v2/predictions/supported-stations"),
        ]
        result = _compute_usage_analytics(records)
        actions_by_name = {a["action"]: a["count"] for a in result["actions"]}
        assert actions_by_name["prediction_lookups"] == 3, (
            f"Expected 3 prediction_lookups, got {actions_by_name}"
        )

    def test_hourly_trend(self):
        """Hourly trend groups users and actions by hour bucket."""
        now = time.time()
        hour_ago = now - 3600
        records = [
            self._make_record(client_ip="10.0.0.1", timestamp=hour_ago),
            self._make_record(client_ip="10.0.0.2", timestamp=hour_ago),
            self._make_record(client_ip="10.0.0.1", timestamp=now),
        ]
        result = _compute_usage_analytics(records)
        trend = result["hourly_trend"]
        assert len(trend) >= 1, f"Expected at least 1 hourly bucket, got {len(trend)}"

        # Total actions across all buckets should match total records
        total = sum(h["total_actions"] for h in trend)
        assert total == 3, f"Expected 3 total actions in trend, got {total}"

    def test_top_users_ordered_by_action_count(self):
        """Top users are sorted by total action count descending."""
        records = [
            # User A: 1 action
            self._make_record(client_ip="10.0.0.1"),
            # User B: 3 actions
            self._make_record(client_ip="10.0.0.2"),
            self._make_record(client_ip="10.0.0.2"),
            self._make_record(client_ip="10.0.0.2"),
            # User C: 2 actions
            self._make_record(client_ip="10.0.0.3"),
            self._make_record(client_ip="10.0.0.3"),
        ]
        result = _compute_usage_analytics(records)
        top = result["top_users"]
        assert top[0]["ip"] == "10.0.0.2", f"Expected top user 10.0.0.2, got {top[0]}"
        assert top[0]["actions"] == 3
        assert top[1]["ip"] == "10.0.0.3"
        assert top[1]["actions"] == 2
        assert top[2]["ip"] == "10.0.0.1"
        assert top[2]["actions"] == 1

    def test_top_users_shows_primary_activity(self):
        """Top user's top_action reflects their most frequent action."""
        records = [
            self._make_record(
                path="/api/v2/trains/departures", client_ip="10.0.0.1"
            ),
            self._make_record(
                path="/api/v2/trains/departures", client_ip="10.0.0.1"
            ),
            self._make_record(
                path="/api/v2/trains/{train_id}", client_ip="10.0.0.1"
            ),
        ]
        result = _compute_usage_analytics(records)
        top = result["top_users"]
        assert top[0]["top_action"] == "departure_searches", (
            f"Expected departure_searches as top action, got {top[0]['top_action']}"
        )

    def test_version_distribution(self):
        """Version distribution counts requests per iOS version."""
        records = [
            self._make_record(client_label="iOS/230"),
            self._make_record(client_label="iOS/230"),
            self._make_record(client_label="iOS/191"),
        ]
        result = _compute_usage_analytics(records)
        versions = result["version_distribution"]
        assert versions["iOS/230"] == 2, f"Expected iOS/230: 2, got {versions}"
        assert versions["iOS/191"] == 1

    def test_actions_display_order(self):
        """Actions are returned in display order, not arbitrary counter order."""
        records = [
            self._make_record(path="/api/v2/feedback"),  # low priority
            self._make_record(path="/api/v2/trains/departures"),  # high priority
            self._make_record(path="/api/v2/trips/search"),  # mid priority
        ]
        result = _compute_usage_analytics(records)
        action_names = [a["action"] for a in result["actions"]]
        assert action_names.index("departure_searches") < action_names.index(
            "trip_searches"
        ), f"Departure searches should come before trip searches: {action_names}"
        assert action_names.index("trip_searches") < action_names.index(
            "feedback_submissions"
        ), f"Trip searches should come before feedback: {action_names}"

    def test_actions_per_user(self):
        """actions_per_user is average mapped actions divided by unique users."""
        records = [
            # User A: 3 mapped actions
            self._make_record(client_ip="10.0.0.1"),
            self._make_record(client_ip="10.0.0.1"),
            self._make_record(client_ip="10.0.0.1"),
            # User B: 1 mapped action
            self._make_record(client_ip="10.0.0.2"),
        ]
        result = _compute_usage_analytics(records)
        # 4 actions / 2 users = 2.0
        assert result["actions_per_user"] == 2.0, (
            f"Expected 2.0 actions/user, got {result['actions_per_user']}"
        )

    def test_top_routes_with_unique_users(self):
        """top_routes shows routes searched by iOS users with unique user counts."""
        records = [
            self._make_record(client_ip="10.0.0.1"),  # has from_station/to_station=None
            self._make_record(client_ip="10.0.0.2"),
        ]
        # Override from_station/to_station on the records
        records[0].from_station = "NY"
        records[0].to_station = "TR"
        records[1].from_station = "NY"
        records[1].to_station = "TR"

        result = _compute_usage_analytics(records)
        assert len(result["top_routes"]) == 1, (
            f"Expected 1 route, got {result['top_routes']}"
        )
        route = result["top_routes"][0]
        assert route["from"] == "NY"
        assert route["to"] == "TR"
        assert route["searches"] == 2
        assert route["unique_users"] == 2

    def test_top_routes_empty_without_station_params(self):
        """top_routes is empty when records have no from/to station."""
        records = [self._make_record()]  # from_station=None by default
        result = _compute_usage_analytics(records)
        assert result["top_routes"] == [], (
            f"Expected empty top_routes, got {result['top_routes']}"
        )

    def test_zero_action_users_excluded_from_top_users(self):
        """Users who only hit unmapped paths don't appear in top_users."""
        records = [
            self._make_record(path="/admin/stats", client_ip="10.0.0.1"),
            self._make_record(
                path="/api/v2/trains/departures", client_ip="10.0.0.2"
            ),
        ]
        result = _compute_usage_analytics(records)
        top_ips = [u["ip"] for u in result["top_users"]]
        assert "10.0.0.1" not in top_ips, (
            f"User with only unmapped paths should not be in top_users: {top_ips}"
        )
        assert "10.0.0.2" in top_ips

    def test_analytics_in_snapshot(self):
        """usage_analytics key appears in snapshot when iOS traffic exists."""
        stats = RequestStats()
        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="TrackRat/230 CFNetwork/1568",
            duration=0.05,
            client_ip="10.0.0.1",
        )
        snap = stats.snapshot()
        assert "usage_analytics" in snap, (
            f"Expected usage_analytics in snapshot, keys: {list(snap.keys())}"
        )
        assert snap["usage_analytics"]["unique_users"] == 1
        assert snap["usage_analytics"]["total_actions"] == 1

    def test_analytics_absent_without_ios_traffic(self):
        """usage_analytics key is absent when no iOS traffic exists."""
        stats = RequestStats()
        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="curl/7",
            duration=0.05,
            client_ip="10.0.0.1",
        )
        snap = stats.snapshot()
        assert "usage_analytics" not in snap, (
            "usage_analytics should not be present without iOS traffic"
        )


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
