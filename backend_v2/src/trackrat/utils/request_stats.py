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
from collections import Counter, deque
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
    route_search_results: dict[tuple[str, str], list[int]] = field(default_factory=dict)
    train_detail_views: Counter[tuple[str, str, str]] = field(
        default_factory=Counter
    )  # (train_id, from_station, to_station)
    _MAX_LATENCY_SAMPLES: int = 500

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
        with self._lock:
            samples = self.route_search_results.setdefault(key, [])
            # Keep last 500 samples per route to bound memory
            if len(samples) < self._MAX_LATENCY_SAMPLES:
                samples.append(count)
            else:
                idx = random.randint(0, len(samples) - 1)
                samples[idx] = count

    def record_train_detail_view(
        self, train_id: str, from_station: str, to_station: str
    ) -> None:
        """Record a train detail page view with user's origin/destination."""
        with self._lock:
            self.train_detail_views[(train_id, from_station, to_station)] += 1

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
            trend_buckets.setdefault(bucket, {}).setdefault(
                r.path_template, []
            ).append(r.duration)

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

        # Compute per-route search result stats
        route_search_stats: dict[tuple[str, str], dict[str, float]] = {}
        for key, rss in self.route_search_results.items():
            if rss:
                route_search_stats[key] = {
                    "avg_trains": sum(rss) / len(rss),
                    "empty_count": rss.count(0),
                }

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
                for k, v in self.train_detail_views.most_common(20)
            ],
            "latency": latency_stats,
            "latency_trend": latency_trend,
            "unique_ips": len(ip_set),
            "requests_by_ip": dict(by_ip.most_common()),
        }

        if hours:
            result["window_hours"] = hours
        if ios_only:
            result["ios_only"] = True

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
