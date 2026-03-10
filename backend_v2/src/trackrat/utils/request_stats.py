"""
In-memory request statistics tracking.

Provides lightweight middleware-compatible tracking of inbound HTTP requests,
route searches, and client activity. All data resets on server restart.
"""

import re
import threading
import time
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class RequestStats:
    """Thread-safe in-memory request statistics collector."""

    start_time: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # Counters
    total_requests: int = 0
    requests_by_path: Counter = field(default_factory=Counter)
    requests_by_status: Counter = field(default_factory=Counter)
    requests_by_client: Counter = field(default_factory=Counter)
    route_searches: Counter = field(default_factory=Counter)

    # Latency tracking: path_template -> list of durations (capped)
    _latencies: dict[str, list[float]] = field(default_factory=dict)
    _MAX_LATENCY_SAMPLES: int = 500

    def record_request(
        self,
        *,
        path_template: str,
        status_code: int,
        user_agent: str,
        duration: float,
        query_params: dict[str, str] | None = None,
    ) -> None:
        """Record a single inbound request."""
        client = _classify_user_agent(user_agent)

        with self._lock:
            self.total_requests += 1
            self.requests_by_path[path_template] += 1
            self.requests_by_status[status_code] += 1
            self.requests_by_client[client] += 1

            # Latency
            samples = self._latencies.setdefault(path_template, [])
            if len(samples) < self._MAX_LATENCY_SAMPLES:
                samples.append(duration)

            # Track route searches from departures endpoint
            if query_params and path_template == "/api/v2/trains/departures":
                from_station = query_params.get("from", "")
                to_station = query_params.get("to", "")
                if from_station and to_station:
                    self.route_searches[(from_station, to_station)] += 1

    def snapshot(self) -> dict:
        """Return a point-in-time copy of all stats."""
        with self._lock:
            latency_stats = {}
            for path, samples in self._latencies.items():
                if samples:
                    s = sorted(samples)
                    latency_stats[path] = {
                        "count": len(s),
                        "avg": sum(s) / len(s),
                        "p50": s[len(s) // 2],
                        "p95": s[int(len(s) * 0.95)] if len(s) >= 20 else s[-1],
                        "max": s[-1],
                    }

            return {
                "uptime_seconds": time.time() - self.start_time,
                "total_requests": self.total_requests,
                "requests_by_path": dict(self.requests_by_path.most_common()),
                "requests_by_status": dict(self.requests_by_status.most_common()),
                "requests_by_client": dict(self.requests_by_client.most_common()),
                "route_searches": dict(self.route_searches.most_common(20)),
                "latency": latency_stats,
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
