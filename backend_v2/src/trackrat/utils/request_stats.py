"""
In-memory request statistics tracking.

Provides lightweight middleware-compatible tracking of inbound HTTP requests,
route searches, and client activity. All data resets on server restart.

Stores individual request records in a bounded deque, enabling time-windowed
queries and per-client-IP filtering at snapshot time.
"""

import random
import re
import threading
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RequestRecord:
    """A single recorded request."""

    timestamp: float
    path_template: str
    status_code: int
    client_label: str
    client_ip: str
    duration: float
    from_station: str | None = None
    to_station: str | None = None


# Max records kept in memory. At ~200 bytes each, 50K ≈ 10 MB.
_MAX_RECORDS = 50_000

# Latency trend bucket size in seconds (5 minutes).
_TREND_BUCKET_SECONDS = 300


@dataclass
class RequestStats:
    """Thread-safe in-memory request statistics collector."""

    start_time: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _records: deque[RequestRecord] = field(
        default_factory=lambda: deque(maxlen=_MAX_RECORDS)
    )
    # (from, to) -> list of (timestamp, train_count) tuples
    route_search_results: dict[tuple[str, str], list[tuple[float, int]]] = field(
        default_factory=dict
    )
    # list of (timestamp, train_id, from, to) tuples
    train_detail_views: list[tuple[float, str, str, str]] = field(default_factory=list)
    _MAX_LATENCY_SAMPLES: int = 500
    _MAX_DETAIL_VIEWS: int = 10_000

    def record_request(
        self,
        *,
        path_template: str,
        status_code: int,
        user_agent: str,
        duration: float,
        client_ip: str = "",
        query_params: dict[str, str] | None = None,
    ) -> None:
        """Record a single inbound request."""
        client = _classify_user_agent(user_agent)
        from_station: str | None = None
        to_station: str | None = None

        if query_params and path_template == "/api/v2/trains/departures":
            from_station = query_params.get("from") or None
            to_station = query_params.get("to") or None

        record = RequestRecord(
            timestamp=time.time(),
            path_template=path_template,
            status_code=status_code,
            client_label=client,
            client_ip=client_ip or "unknown",
            duration=duration,
            from_station=from_station,
            to_station=to_station,
        )

        with self._lock:
            self._records.append(record)

    def record_departure_results(
        self, from_station: str, to_station: str, count: int
    ) -> None:
        """Record the number of trains returned for a departure search."""
        key = (from_station, to_station)
        now = time.time()
        with self._lock:
            samples = self.route_search_results.setdefault(key, [])
            # Keep last 500 samples per route to bound memory
            if len(samples) < self._MAX_LATENCY_SAMPLES:
                samples.append((now, count))
            else:
                idx = random.randint(0, len(samples) - 1)
                samples[idx] = (now, count)

    def record_train_detail_view(
        self, train_id: str, from_station: str, to_station: str
    ) -> None:
        """Record a train detail page view with user's origin/destination."""
        now = time.time()
        with self._lock:
            self.train_detail_views.append((now, train_id, from_station, to_station))
            # Bound memory
            if len(self.train_detail_views) > self._MAX_DETAIL_VIEWS:
                self.train_detail_views = self.train_detail_views[
                    -self._MAX_DETAIL_VIEWS :
                ]

    def snapshot(
        self,
        *,
        hours: int | None = None,
        ios_only: bool = False,
    ) -> dict[str, Any]:
        """Return a point-in-time copy of all stats.

        Args:
            hours: If set, only include records from the last N hours.
            ios_only: If True, only include requests from iOS clients.
        """
        now = time.time()
        cutoff = (now - hours * 3600) if hours else 0.0

        with self._lock:
            records = [
                r
                for r in self._records
                if r.timestamp >= cutoff
                and (not ios_only or r.client_label.startswith("iOS/"))
            ]

        # Aggregate counters from filtered records
        total = len(records)
        by_path: Counter[str] = Counter()
        by_status: Counter[int] = Counter()
        by_client: Counter[str] = Counter()
        by_ip: Counter[str] = Counter()
        route_searches: Counter[tuple[str, str]] = Counter()
        ip_set: set[str] = set()

        # Latency: collect all durations per path for percentile calculation
        latency_samples: dict[str, list[float]] = {}
        # Latency trend: bucket -> path -> list of durations
        trend_buckets: dict[int, dict[str, list[float]]] = {}

        for r in records:
            by_path[r.path_template] += 1
            by_status[r.status_code] += 1
            by_client[r.client_label] += 1
            by_ip[r.client_ip] += 1
            ip_set.add(r.client_ip)

            if r.from_station and r.to_station:
                route_searches[(r.from_station, r.to_station)] += 1

            latency_samples.setdefault(r.path_template, []).append(r.duration)

            # Assign to trend bucket (floored to _TREND_BUCKET_SECONDS)
            bucket = int(r.timestamp // _TREND_BUCKET_SECONDS) * _TREND_BUCKET_SECONDS
            trend_buckets.setdefault(bucket, {}).setdefault(r.path_template, []).append(
                r.duration
            )

        # Compute latency percentiles
        latency_stats = {}
        for path, samples in latency_samples.items():
            s = sorted(samples)
            latency_stats[path] = {
                "count": len(s),
                "avg": sum(s) / len(s),
                "p50": s[len(s) // 2],
                "p95": s[int(len(s) * 0.95)] if len(s) >= 20 else s[-1],
                "max": s[-1],
            }

        # Compute per-route search result stats (time-filtered)
        route_search_stats: dict[tuple[str, str], dict[str, float]] = {}
        with self._lock:
            for key, result_samples in self.route_search_results.items():
                filtered = [count for ts, count in result_samples if ts >= cutoff]
                if filtered:
                    route_search_stats[key] = {
                        "avg_trains": sum(filtered) / len(filtered),
                        "empty_count": filtered.count(0),
                    }

        # Compute train detail views (time-filtered)
        detail_view_counter: Counter[tuple[str, str, str]] = Counter()
        with self._lock:
            for ts, train_id, from_s, to_s in self.train_detail_views:
                if ts >= cutoff:
                    detail_view_counter[(train_id, from_s, to_s)] += 1

        # Compute req/min over last 5 minutes
        five_min_ago = now - 300
        recent_count = sum(1 for r in records if r.timestamp >= five_min_ago)
        req_per_min = round(recent_count / 5, 1) if recent_count > 0 else 0

        # Compute request rate sparkline: requests per 5-min bucket (last 12)
        current_bucket = int(now // _TREND_BUCKET_SECONDS) * _TREND_BUCKET_SECONDS
        rate_buckets = [
            current_bucket - i * _TREND_BUCKET_SECONDS for i in range(11, -1, -1)
        ]
        rate_sparkline: list[int] = []
        for b in rate_buckets:
            count_in_bucket = sum(
                len(durations) for durations in trend_buckets.get(b, {}).values()
            )
            rate_sparkline.append(count_in_bucket)

        # Compute latency trends: last 12 buckets per path, sorted by time
        latency_trend = _compute_latency_trends(trend_buckets, now)

        result: dict[str, Any] = {
            "uptime_seconds": now - self.start_time,
            "total_requests": total,
            "requests_by_path": dict(by_path.most_common()),
            "requests_by_status": dict(by_status.most_common()),
            "requests_by_client": dict(by_client.most_common()),
            "route_searches": [
                {
                    "from": k[0],
                    "to": k[1],
                    "count": v,
                    **route_search_stats.get(k, {}),
                }
                for k, v in route_searches.most_common(20)
            ],
            "train_detail_views": [
                {
                    "train_id": k[0],
                    "from": k[1],
                    "to": k[2],
                    "count": v,
                }
                for k, v in detail_view_counter.most_common(20)
            ],
            "latency": latency_stats,
            "latency_trend": latency_trend,
            "unique_ips": len(ip_set),
            "requests_by_ip": dict(by_ip.most_common()),
            "req_per_min": req_per_min,
            "rate_sparkline": rate_sparkline,
            "recent_errors": [
                {
                    "timestamp": r.timestamp,
                    "path": r.path_template,
                    "status": r.status_code,
                    "client": r.client_label,
                    "client_ip": r.client_ip,
                }
                for r in sorted(
                    (r for r in records if r.status_code >= 500),
                    key=lambda r: r.timestamp,
                    reverse=True,
                )[:20]
            ],
        }

        if hours:
            result["window_hours"] = hours
        if ios_only:
            result["ios_only"] = True

        # iOS usage analytics (always computed from full record set,
        # regardless of ios_only filter — the function filters internally)
        usage_analytics = _compute_usage_analytics(records)
        if usage_analytics:
            result["usage_analytics"] = usage_analytics

        return result


def _compute_latency_trends(
    trend_buckets: dict[int, dict[str, list[float]]],
    now: float,
) -> dict[str, list[dict[str, Any]]]:
    """Compute per-path latency trends from the last 12 five-minute buckets."""
    if not trend_buckets:
        return {}

    # Determine the 12 most recent buckets up to now
    current_bucket = int(now // _TREND_BUCKET_SECONDS) * _TREND_BUCKET_SECONDS
    recent_buckets = [
        current_bucket - i * _TREND_BUCKET_SECONDS for i in range(11, -1, -1)
    ]

    # Collect all paths that appear in any recent bucket
    all_paths: set[str] = set()
    for b in recent_buckets:
        if b in trend_buckets:
            all_paths.update(trend_buckets[b].keys())

    result: dict[str, list[dict[str, Any]]] = {}
    for path in all_paths:
        buckets_data = []
        for b in recent_buckets:
            durations = trend_buckets.get(b, {}).get(path, [])
            if durations:
                buckets_data.append(
                    {
                        "bucket": b,
                        "avg_ms": (sum(durations) / len(durations)) * 1000,
                        "count": len(durations),
                    }
                )
            else:
                buckets_data.append({"bucket": b, "avg_ms": 0, "count": 0})
        result[path] = buckets_data

    return result


# ---------------------------------------------------------------------------
# iOS usage analytics
# ---------------------------------------------------------------------------

# Map path templates to human-readable action names for iOS analytics.
_ACTION_MAP: dict[str, str] = {
    "/api/v2/trains/departures": "departure_searches",
    "/api/v2/trains/{train_id}": "train_detail_views",
    "/api/v2/trains/{train_id}/history": "train_history_views",
    "/api/v2/trips/search": "trip_searches",
    "/api/v2/live-activities/register": "live_activity_starts",
    "/api/v2/alerts/subscriptions": "alert_subscriptions",
    "/api/v2/alerts/subscriptions/{device_id}": "alert_subscriptions",
    "/api/v2/feedback": "feedback_submissions",
    "/api/v2/predictions/track": "prediction_lookups",
    "/api/v2/predictions/delay": "prediction_lookups",
    "/api/v2/predictions/supported-stations": "prediction_lookups",
    "/api/v2/devices/register": "device_registrations",
    "/api/v2/routes/preferences": "preference_updates",
    "/api/v2/alerts/service": "service_alert_views",
}

# Display order for action table (most interesting first).
_ACTION_DISPLAY_ORDER = [
    "departure_searches",
    "train_detail_views",
    "trip_searches",
    "prediction_lookups",
    "train_history_views",
    "live_activity_starts",
    "alert_subscriptions",
    "service_alert_views",
    "device_registrations",
    "preference_updates",
    "feedback_submissions",
]


def _compute_usage_analytics(
    records: list["RequestRecord"],
) -> dict[str, Any]:
    """Compute iOS-specific usage analytics from filtered request records.

    Returns a dict with unique user counts, per-action breakdowns, hourly trends,
    and top user summaries — all based on iOS client IPs as a user proxy.
    """
    ios_records = [r for r in records if r.client_label.startswith("iOS/")]
    if not ios_records:
        return {}

    # Per-IP action counters
    ip_actions: dict[str, Counter[str]] = defaultdict(Counter)
    action_ips: dict[str, set[str]] = defaultdict(set)
    action_counts: Counter[str] = Counter()
    all_ips: set[str] = set()

    for r in ios_records:
        all_ips.add(r.client_ip)
        action = _ACTION_MAP.get(r.path_template)
        if action:
            ip_actions[r.client_ip][action] += 1
            action_ips[action].add(r.client_ip)
            action_counts[action] += 1

    # Build ordered action breakdown
    actions: list[dict[str, Any]] = []
    for action_name in _ACTION_DISPLAY_ORDER:
        count = action_counts.get(action_name, 0)
        if count > 0:
            actions.append(
                {
                    "action": action_name,
                    "count": count,
                    "unique_users": len(action_ips[action_name]),
                }
            )
    # Append any actions not in the display order
    for action_name, count in action_counts.most_common():
        if action_name not in _ACTION_DISPLAY_ORDER and count > 0:
            actions.append(
                {
                    "action": action_name,
                    "count": count,
                    "unique_users": len(action_ips[action_name]),
                }
            )

    # Hourly trend: unique iOS users + total actions per hour bucket
    hourly: dict[int, dict[str, Any]] = {}
    for r in ios_records:
        bucket = int(r.timestamp // 3600) * 3600
        if bucket not in hourly:
            hourly[bucket] = {"ips": set(), "count": 0}
        hourly[bucket]["ips"].add(r.client_ip)
        hourly[bucket]["count"] += 1

    hourly_trend: list[dict[str, Any]] = []
    for bucket in sorted(hourly.keys()):
        hourly_trend.append(
            {
                "bucket": bucket,
                "unique_users": len(hourly[bucket]["ips"]),
                "total_actions": hourly[bucket]["count"],
            }
        )

    # Top users (by total action count, top 15)
    top_users: list[dict[str, Any]] = []
    for ip, actions_counter in sorted(
        ip_actions.items(), key=lambda x: x[1].total(), reverse=True
    )[:15]:
        top_action = actions_counter.most_common(1)[0][0] if actions_counter else ""
        top_users.append(
            {
                "ip": ip,
                "actions": actions_counter.total(),
                "top_action": top_action,
            }
        )

    # Version distribution
    version_counts: Counter[str] = Counter()
    for r in ios_records:
        version_counts[r.client_label] += 1

    return {
        "unique_users": len(all_ips),
        "total_actions": sum(action_counts.values()),
        "actions": actions,
        "hourly_trend": hourly_trend,
        "top_users": top_users,
        "version_distribution": dict(version_counts.most_common()),
    }


# ---------------------------------------------------------------------------
# User-Agent classification
# ---------------------------------------------------------------------------

_IOS_PATTERN = re.compile(r"TrackRat/(\d+)")
_CURL_PATTERN = re.compile(r"^curl/", re.IGNORECASE)
_SCANNER_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"bot",
        r"spider",
        r"crawl",
        r"scan",
        r"masscan",
        r"zgrab",
        r"nuclei",
        r"nmap",
        r"sqlmap",
        r"nikto",
        r"Go-http-client",
        r"python-requests",
        r"python-httpx",
    ]
]


def _classify_user_agent(ua: str) -> str:
    """Classify a User-Agent string into a short label."""
    if not ua:
        return "unknown"

    m = _IOS_PATTERN.search(ua)
    if m:
        return f"iOS/{m.group(1)}"

    if _CURL_PATTERN.search(ua):
        return "curl"

    if any(p.search(ua) for p in _SCANNER_PATTERNS):
        return "scanner"

    if "Mozilla" in ua or "Chrome" in ua or "Safari" in ua:
        return "browser"

    return "other"


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_stats: RequestStats | None = None


def get_request_stats() -> RequestStats:
    """Get or create the global RequestStats singleton."""
    global _stats
    if _stats is None:
        _stats = RequestStats()
    return _stats


def reset_request_stats() -> None:
    """Reset stats (for testing)."""
    global _stats
    _stats = None
