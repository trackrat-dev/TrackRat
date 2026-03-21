# Admin Stats Improvements Plan

## Summary

Add time-windowed views, iOS/IP filtering, JSON parity, and latency trends to the admin stats endpoint. Two files change: `request_stats.py` (data collection) and `admin.py` (rendering + JSON).

## Changes

### 1. `request_stats.py` — Time-windowed + per-client-IP tracking

**Current**: Counters accumulate since restart. No IP tracking. No timestamps on individual records.

**Change**: Instead of bare `Counter`s, store each request as a timestamped record in a bounded deque (ring buffer). This lets us filter by time window at query time.

```python
@dataclass
class RequestRecord:
    timestamp: float
    path_template: str
    status_code: int
    client_label: str  # "iOS/230", "curl", etc.
    client_ip: str
    duration: float
    from_station: str | None = None
    to_station: str | None = None
```

- Add a `collections.deque(maxlen=50_000)` of `RequestRecord` objects (bounded to ~50K, enough for days of typical traffic)
- `record_request()` gains a `client_ip: str` parameter
- `snapshot()` gains an optional `hours: int | None` parameter — when set, filters records to only those within the window
- `snapshot()` gains an optional `ios_only: bool` parameter — when set, filters to iOS client labels only
- Keep the existing reservoir sampling for latency (it's already good), but also add a simple time-bucketed latency structure for trend data: `dict[str, list[tuple[float, float]]]` mapping `path_template -> [(timestamp, duration), ...]`
- The latency trend data enables sparkline-style views

**Latency trends**: For each path, keep the last N minutes of (timestamp, duration) pairs in a separate bounded structure. `snapshot()` returns per-path latency broken into time buckets (e.g., 5-min buckets) with avg latency per bucket.

**snapshot() output additions**:
- `requests_by_ip: dict[str, int]` — only populated when `ios_only=True`
- `unique_ips: int` — count of distinct client IPs in the window
- `latency_trend: dict[str, list[dict]]` — per-path list of `{bucket: str, avg_ms: float, count: int}`

### 2. `main.py` — Pass client IP to middleware

One-line change: extract `request.client.host` (with fallback for X-Forwarded-For behind load balancer) and pass it to `record_request()`.

```python
# In request_stats_middleware
client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
    request.client.host if request.client else "unknown"
)
get_request_stats().record_request(
    ...,
    client_ip=client_ip,
)
```

### 3. `admin.py` — Query params, JSON parity, HTML updates

**Query params** (both HTML and JSON endpoints):
- `?hours=N` — time window (default: None = all since restart)
- `?ios_only=true` — filter to iOS clients only

**JSON parity fixes**:
- Add `scheduler_jobs` to JSON response
- Resolve station names in JSON route searches (use `get_station_name()`)

**HTML additions**:
- Filter controls at the top: links for "All time | 1h | 6h | 24h" and "All clients | iOS only"
- When `ios_only=true`, show a "Requests by IP" table (IP, request count) — gives rough user count
- Show `unique_ips` in the header meta line
- Latency trend: add a simple ASCII/text sparkline next to each endpoint's latency (e.g., `▁▃▅▇▅▃` using Unicode block chars), or a CSS-based mini bar chart. The CSS approach is cleaner and still self-contained (no JS libraries needed).

**Latency trend rendering** (CSS mini bars):
- For each endpoint row, render the last 12 five-minute buckets as tiny inline `<span>` elements with height proportional to avg latency
- Fits in a new column or below the existing latency numbers
- Pure CSS, no JavaScript dependencies

### 4. Tests

New test file or additions to existing admin test file:
- `test_request_stats_time_window` — records span 2 hours, snapshot with `hours=1` returns only recent
- `test_request_stats_ios_filter` — mix of iOS/curl/browser, `ios_only=True` filters correctly
- `test_request_stats_ip_tracking` — verify `requests_by_ip` populated correctly
- `test_request_stats_latency_trend` — verify bucket aggregation
- `test_stats_json_parity` — verify JSON includes scheduler_jobs and resolved station names
- `test_snapshot_default_unchanged` — existing behavior unchanged when no params passed

## File Change Summary

| File | Change |
|------|--------|
| `backend_v2/src/trackrat/utils/request_stats.py` | Add `RequestRecord`, deque, time-windowed snapshot, IP tracking, latency trends |
| `backend_v2/src/trackrat/main.py` | Pass `client_ip` to `record_request()` |
| `backend_v2/src/trackrat/api/admin.py` | Query params, filter UI, JSON parity, latency trend rendering, IP table |
| `backend_v2/tests/unit/test_admin_stats.py` | New tests for all features |

## Design Decisions

**Why a deque instead of just adding timestamps to counters?**
Counters can't be filtered retroactively. A bounded deque of lightweight records lets us slice by any dimension (time, client type, IP) at query time without pre-aggregating. 50K records at ~200 bytes each = ~10MB, negligible.

**Why not use a database?**
The whole point of this endpoint is fast, in-memory, zero-dependency stats. Adding DB writes per request would be a significant change for minimal benefit.

**Why CSS bars instead of a JS charting library?**
Self-contained HTML with no external dependencies is a feature of this page. CSS-only mini bars keep that property.

**Memory bound**: The 50K record deque auto-evicts old entries. At typical traffic (~100 req/min), that's ~8 hours of history. Heavy traffic (~1000 req/min) gives ~50 minutes. This is acceptable for an operational dashboard.
