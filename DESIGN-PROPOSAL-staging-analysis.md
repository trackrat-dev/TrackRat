# Design Proposal: Staging Analysis Fixes

## Overview

Analysis of the staging environment surfaced 4 issues at different severity levels. This document proposes fixes for each, ordered by priority.

---

## Issue 1: STATION_EQUIVALENTS Cross-Line Contamination (Production Bug)

### Problem

`SUBWAY_STATION_COMPLEXES` groups all platform codes at 42nd St into single equivalence groups:

- **Times Square**: `{S127(1/2/3), S725(7), S902(GS), SA27(A/C/E), SR16(N/Q/R/W)}`
- **Grand Central**: `{S631(4/5/6), S723(7), S901(GS)}`

When the departures API receives `from=S901&to=S902` (GS shuttle), `expand_station_codes` expands this to include `S723`/`S725` (7 train), `S631`/`S127` (4/5/6, 1/2/3), etc. The departure query then returns trains from ALL lines at the complex — not just the GS shuttle.

There is **no route/line_code filtering** anywhere in the 13 call sites that use `expand_station_codes`.

### Impact

- Users querying GS shuttle departures see 7 train departures mixed in (and vice versa)
- Affects: departure service, route analytics, summary service, track occupancy, GTFS schedule queries
- iOS sends a single canonical code (e.g., S127) → gets all lines back
- Web lists per-line stations but expansion still returns all lines regardless

### Options Considered

| Option | Change Size | Fixes GS/7 | Fixes all cross-line | Risk |
|--------|-------------|-------------|---------------------|------|
| **A: Split GS codes only** | ~4 lines in subway.py | Yes | No | Very low |
| **B: Split all 42nd St complexes** | ~10 lines subway.py + iOS StationData.swift | Yes | Yes | Low |
| **C: Add line_code filter to departure queries** | 13 call sites across 6 services | Yes | Yes | Medium — wide blast radius |
| **D: Remove all SUBWAY_STATION_COMPLEXES** | subway.py + iOS StationData.swift | Yes | Yes, globally | Medium — may over-correct |

### Recommendation: Option A (Split GS codes only)

Remove `S901` and `S902` from their complexes. This is the minimal fix that resolves the most visible bug (GS shuttle is only 2 stops, both contaminated).

**Why not B/C/D:** The other complexes group lines that share physical platforms and similar frequency (e.g., 1/2/3 and 7 at Times Square). Cross-contamination between these high-frequency lines is far less noticeable than GS shuttle trains appearing in 7 train results. A broader fix can be considered separately if users report issues.

### Files Changed

| File | Change |
|------|--------|
| `backend_v2/src/trackrat/config/stations/subway.py` | Remove `S902` from Times Sq complex, remove `S901` from Grand Central complex |

### Concrete Change

```python
# Times Square complex — BEFORE:
{"S127", "S725", "S902", "SA27", "SR16"}

# AFTER (remove S902):
{"S127", "S725", "SA27", "SR16"}

# Grand Central complex — BEFORE:
{"S631", "S723", "S901"}

# AFTER (remove S901):
{"S631", "S723"}
```

S901 and S902 become standalone codes — no equivalents — which is correct since the GS shuttle has dedicated platforms with no shared service.

---

## Issue 2: E2E Validation False Positives (Test Bug)

### Problem

`scripts/e2e-api-test.sh` (line 267) fails any route with 0 SCHEDULED trains:

```bash
elif [[ "$sched" -eq 0 ]]; then
  fail "No SCHEDULED trains ($obs observed, 0 scheduled)"
```

This fails for MNR (all 5 routes), Subway (2 routes), and Amtrak (3 routes) because these providers **never create SCHEDULED records**:

- **MNR/Subway**: Unified GTFS-RT collectors create all journeys as `OBSERVED` directly. No schedule generation phase exists.
- **Amtrak**: Pattern scheduler creates SCHEDULED, but journey collector promotes them to OBSERVED aggressively. Combined with the 15-minute stale filter, 0 SCHEDULED is a normal state.

The check was designed for NJT, which has a dedicated schedule collector that creates SCHEDULED records hours in advance.

### Recommendation: Add realtime-only flag

Add an `r` flag to route definitions for providers without a schedule generation phase. Downgrade the check from `fail` to `pass` for flagged routes.

### Files Changed

| File | Change |
|------|--------|
| `scripts/e2e-api-test.sh` | Add `r` flag to MNR, Subway, Amtrak route definitions; add flag handling in observation-type check |

### Concrete Change

```bash
# Route definitions — add 'r' flag:
"MNR Hudson|GCT|MPOK|MNR|GCT|r"
"Subway 1|S101|S142|SUBWAY||r"
"Amtrak NEC|NY|WS|AMTRAK|NY|r"
# ... etc for all MNR, Subway, Amtrak routes

# Check logic — add handling before the sched==0 check:
elif [[ "$flags" == *r* ]]; then
  # Realtime-only provider: no schedule generation, 0 SCHEDULED is normal
  pass "Realtime-only: $obs observed"
elif [[ "$sched" -eq 0 ]]; then
  fail "No SCHEDULED trains ($obs observed, 0 scheduled)"
```

LIRR also uses a unified GTFS-RT collector but isn't currently failing. If it starts failing, add the `r` flag to LIRR routes too.

---

## Issue 3: Missing Subway `generate_train_id` in Ground Truth Validation

### Problem

`ground-truth-validate.py` doesn't pass `generate_train_id` for subway (unlike LIRR/MNR), so all subway `GroundTruthArrival` objects have `train_id=""`. The validation falls back to pure time-proximity matching, which is less accurate with 472 stations and frequent service.

### Complication

Subway's `_generate_train_id` takes 3 args `(trip_id, nyct_train_id, route_id)` while LIRR/MNR take 1 arg `(trip_id)`. The `_fetch_gtfsrt_ground_truth` callback is typed `Callable[[str], str]`.

### Recommendation: Adapt `_fetch_gtfsrt_ground_truth` to support subway's 3-arg signature

Use `hasattr` to detect subway-specific fields on the arrival object and pass extra args.

### Files Changed

| File | Change |
|------|--------|
| `scripts/ground-truth-validate.py` | ~10 lines: update `_fetch_gtfsrt_ground_truth` callback dispatch + import subway's `_generate_train_id` |

### Concrete Change

```python
# In _fetch_gtfsrt_ground_truth, where train_id is generated (~line 448):
if generate_train_id:
    if hasattr(arr, 'nyct_train_id'):
        train_id = generate_train_id(arr.trip_id, arr.nyct_train_id, arr.route_id)
    else:
        train_id = generate_train_id(arr.trip_id)

# In fetch_subway_ground_truth:
def fetch_subway_ground_truth() -> list[GroundTruthArrival]:
    from trackrat.collectors.subway.client import SubwayClient
    from trackrat.collectors.subway.collector import _generate_train_id as subway_train_id
    return _fetch_gtfsrt_ground_truth(SubwayClient, generate_train_id=subway_train_id)
```

---

## Issue 4: Validation Service ReadTimeout (Low Priority)

### Problem

The hourly `TrainValidationService` calls its own departures API at `localhost:8000` with a 30s timeout. This self-call can trigger JIT (Just-In-Time) data refresh, which cascades into external API calls, causing occasional ReadTimeouts. The error is logged as `api_scan_failed`.

### Impact

Non-critical — validation is purely observational. A timeout skips that route's validation for one hour and self-corrects on the next run. No data corruption.

### Recommendation: Increase self-call timeout + add retry transport

### Files Changed

| File | Change |
|------|--------|
| `backend_v2/src/trackrat/services/validation.py` | ~3 lines: increase timeout to 60s, add retry transport |

### Concrete Change

```python
# Line 88 — BEFORE:
self.http_client = httpx.AsyncClient(timeout=30.0)

# AFTER:
self.http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(60.0),
    transport=httpx.AsyncHTTPTransport(retries=2),
)
```

---

## Summary

| # | Issue | Severity | Files | Lines Changed |
|---|-------|----------|-------|---------------|
| 1 | GS/7 station equivalents | **Medium** (production) | 1 | ~4 |
| 2 | E2E SCHEDULED false positives | **Low** (test only) | 1 | ~15 |
| 3 | Subway generate_train_id | **Low** (validation only) | 1 | ~10 |
| 4 | Validation ReadTimeout | **Low** (observability) | 1 | ~3 |

Total: 4 files, ~32 lines changed. All fixes are independent and can be applied in any order.

## Already Fixed

| Issue | Status |
|-------|--------|
| SubwayClient tuple crash in ground-truth-validate.py | Committed and pushed |
