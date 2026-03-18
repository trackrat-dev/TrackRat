# Fix Route Details Sections — Design Proposal

## Summary

Three changes to iOS `RouteStatusView`:
1. **Always show Service Alerts section** with empty state (confirmed user request)
2. **Fix NJT alert filtering bug** (confirmed real bug in multi-system contexts)
3. **Fix cache miss for system-specific departures** (confirmed performance issue)

Plus one minor backend fix.

---

## Change 1: Always Show Service Alerts Section + Empty State

**File:** `ios/TrackRat/Views/Screens/RouteStatusView.swift`

**Current (line 361):** The entire section is wrapped in `if !viewModel.serviceAlerts.isEmpty`, so it's invisible when there are zero alerts.

**Fix:** Remove the `isEmpty` gate. Always render the section header + segmented picker. When the filtered alerts list is empty, show "No active service alerts" / "No upcoming service alerts" depending on the selected tab.

```swift
// BEFORE (line 361)
if !viewModel.serviceAlerts.isEmpty {

// AFTER
// Always show section — remove the isEmpty guard
// (keep the VStack and everything inside, just remove the wrapping `if`)
```

Add an empty-state message inside the existing `if filteredAlerts.isEmpty` block (line 384) — this block already exists but currently shows nothing useful when the outer `if` was hiding everything.

---

## Change 2: Fix NJT Service Alert Filtering Bug

**Bug confirmed:** When a user has toggled specific lines in a multi-system context (e.g., NJT + SUBWAY), NJT line codes are silently dropped from `enabledGtfsRouteIds`, causing NJT alerts to be filtered out.

**Root cause:** `enabledGtfsRouteIds` (line 931) handles SUBWAY, LIRR, and MNR line codes but has no branch for NJT. NJT line codes like `"NE"`, `"NC"` are dropped, which means `relevantRouteIds` contains only SUBWAY IDs. NJT alerts (whose `affectedRouteIds` are `["NE", "NC"]`) never intersect with SUBWAY IDs and get filtered out.

In pure NJT contexts, this "works by accident" because the empty set triggers the `relevantRouteIds.isEmpty` fallback (line 1243) which bypasses filtering entirely. But in multi-system contexts, the SUBWAY IDs are present so filtering runs, and NJT alerts are lost.

**Fix — two locations:**

### A. `RouteStatusView.swift` line 942 — `enabledGtfsRouteIds`

Add NJT passthrough. NJT backend line codes (`NE`, `NC`, etc.) ARE the `affected_route_ids` used in service alerts, so they should be passed through directly:

```swift
// BEFORE
if system == "SUBWAY" {
    ids.insert(lineCode.uppercased())
} else if let gtfsId = Self.lirrCodeToGtfs[lineCode] ?? Self.mnrCodeToGtfs[lineCode] {
    ids.insert(gtfsId)
}

// AFTER
if system == "SUBWAY" {
    ids.insert(lineCode.uppercased())
} else if system == "NJT" || system == "AMTRAK" {
    // NJT/Amtrak line codes match affected_route_ids from backend directly
    ids.insert(lineCode)
} else if let gtfsId = Self.lirrCodeToGtfs[lineCode] ?? Self.mnrCodeToGtfs[lineCode] {
    ids.insert(gtfsId)
}
```

### B. `TrackRatApp.swift` line 640 — `resolveGtfsRouteIds`

Add NJT/Amtrak branch. Currently returns `nil` for NJT, which means `gtfsRouteIds` (the fallback in `loadServiceAlerts`) also returns empty for NJT contexts:

```swift
// Add before the LIRR topology mapping (around line 652)
if dataSource == "NJT" || dataSource == "AMTRAK" {
    // NJT/Amtrak line codes are used as affected_route_ids in service alerts
    return [lineId]
}
```

**Why Amtrak too:** Same pattern — Amtrak line codes from the backend are used as `affected_route_ids`. Not handling them would leave the same silent-drop bug for Amtrak once service alerts are added for that system.

---

## Change 3: Cache Hit for System-Specific Departures

**Problem confirmed:** iOS passes `data_sources=SUBWAY` (or PATH, etc.) for system-specific routes. Cache precomputation stores entries with `data_sources=None` (all systems). Since `data_sources` is part of the cache key hash, iOS requests ALWAYS miss the precomputed cache, triggering full computation on every request.

**Fix — backend `api/trains.py`:** When the exact cache key misses and `data_sources` is specified, fall back to the `data_sources=None` cache entry and filter the response in-memory. The `None` cache already contains a superset of the data.

```python
# In the departures endpoint, after the primary cache lookup fails:
if use_cache and source_list and not cached_response:
    # Try the superset cache (data_sources=None) and filter
    superset_params = {**cache_params, "data_sources": None}
    superset_response = await cache_service.get_cached_response(
        db, "/api/v2/trains/departures", superset_params
    )
    if superset_response:
        # Filter departures to requested data_sources
        superset_response["departures"] = [
            d for d in superset_response.get("departures", [])
            if d.get("data_source") in source_list
        ]
        superset_response["metadata"]["count"] = len(superset_response["departures"])
        try:
            return DeparturesResponse(**superset_response)
        except (TypeError, ValueError):
            pass  # Fall through to fresh computation
```

**Impact:** Every iOS request for system-specific routes that currently misses cache will now hit the precomputed superset cache. This is the biggest performance win — avoids full DB query + NJT JIT check + GTFS merge for every cache miss.

---

## Change 4: Skip PATH Cutoff Query When PATH Not Requested (minor)

**File:** `backend_v2/src/trackrat/services/departure.py` line 405

**Current:** `_get_path_cutoff_time` is called unconditionally even when PATH isn't in `allowed_sources`.

**Fix:**
```python
# BEFORE
path_cutoff_time = await self._get_path_cutoff_time(...)

# AFTER
if "PATH" in allowed_sources:
    path_cutoff_time = await self._get_path_cutoff_time(...)
else:
    path_cutoff_time = current_time  # No PATH departures, cutoff irrelevant
```

Saves one DB query per non-PATH request on cache miss. Minor but free.

---

## What's NOT Changing

- **LineSelectionView `hasContent`**: The code-analyzer confirms this is correct behavior — hiding a filter when there's nothing to filter. Showing a single non-interactive line would be a useless UI element.
- **Progressive rendering**: Per your request, not changing `isInitialLoading` behavior.
- **Web platform**: No service alerts section exists on web (MVP phase). Out of scope.
- **Cache precomputation routes**: Not adding system-specific precomputation entries — the superset fallback (Change 3) handles this more elegantly without doubling cache entries.

---

## Files Modified

| File | Change |
|------|--------|
| `ios/TrackRat/Views/Screens/RouteStatusView.swift` | Always show service alerts section; NJT passthrough in `enabledGtfsRouteIds` |
| `ios/TrackRat/App/TrackRatApp.swift` | NJT/Amtrak branch in `resolveGtfsRouteIds` |
| `backend_v2/src/trackrat/api/trains.py` | Superset cache fallback for system-specific requests |
| `backend_v2/src/trackrat/services/departure.py` | Guard PATH cutoff query |
