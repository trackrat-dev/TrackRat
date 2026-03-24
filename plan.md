# Track Assignment Notification — Implementation Plan

## Key Insight

The iOS side **already** handles track assignment notifications via `handleCriticalEventNotification` in `TrackRatApp.swift`. When a Live Activity push contains `alertMetadata` with `alert_type: "track_assigned"` in the content state, iOS creates a local banner notification with sound. **No iOS changes needed.**

The backend just needs to:
1. Detect when a track is newly assigned to a followed train's origin stop
2. Include `alertMetadata` in the Live Activity content state push
3. Force-refresh data more aggressively for followed trains awaiting track assignment

## Changes

### 1. Database Migration: Add `track_notified_at` to `LiveActivityToken`

**File:** `backend_v2/src/trackrat/db/migrations/versions/20260323_1200-a1b2c3d4e5f6_add_track_notified_at.py`

Add nullable `DateTime(timezone=True)` column `track_notified_at` to `live_activity_tokens`. This tracks whether we've already sent a track assignment alert for this token, preventing duplicate notifications.

### 2. Model Update: `LiveActivityToken`

**File:** `backend_v2/src/trackrat/models/database.py` (line ~300)

Add `track_notified_at = Column(DateTime(timezone=True), nullable=True)` to `LiveActivityToken`.

### 3. Content State: Add `alertMetadata` for Track Assignments

**File:** `backend_v2/src/trackrat/services/scheduler.py`

Modify `_calculate_live_activity_content_state` to accept a `track_just_assigned: bool` parameter. When `True`, add to the content state dict:

```python
content_state["alertMetadata"] = {
    "alert_type": "track_assigned",
    "train_id": journey.train_id,
    "dynamic_island_priority": "high",
}
```

This matches what the iOS `handleCriticalEventNotification` already expects (line 378-385 of TrackRatApp.swift).

### 4. Live Activity Update Loop: Detect & Notify Track Assignments

**File:** `backend_v2/src/trackrat/services/scheduler.py`

In `update_live_activities`, after calculating content state for each token:

1. Check if `content_state["track"]` is non-null AND `token.track_notified_at` is null
2. If so, set `track_just_assigned=True` when calling `_calculate_live_activity_content_state` (or just inject `alertMetadata` after the call)
3. After successful APNS send, set `token.track_notified_at = now_et()` and commit

### 5. Force Refresh for Followed Trains Awaiting Track

**File:** `backend_v2/src/trackrat/services/scheduler.py`

In `update_live_activities`, for tokens where:
- `token.track_notified_at is None` (haven't notified about track yet)
- Train departs within 30 minutes from origin
- Data source is NJT, LIRR, or MNR (providers with track assignments)

**Always** force a JIT refresh regardless of staleness. This ensures we check the transit API on every 1-minute LA cycle for trains actively awaiting track assignment, reducing worst-case latency from 60s (staleness threshold) to the LA cycle interval (~1 min).

### 6. Fix LIRR/MNR `track_assigned_at` (consistency)

**Files:**
- `backend_v2/src/trackrat/collectors/lirr/collector.py` (lines 476, 585)
- `backend_v2/src/trackrat/collectors/mnr/collector.py` (lines 467, 575)

At each track write location, add:
```python
if arr.track and not existing_stop.track:
    existing_stop.track_assigned_at = now_et()
existing_stop.track = arr.track
```

This ensures `track_assigned_at` is populated consistently across all providers (NJT already does this).

### 7. Tests

**File:** `backend_v2/tests/unit/test_track_assignment_notification.py`

Tests:
- `test_track_assignment_detected`: Content state includes `alertMetadata` when track transitions from None to a value
- `test_track_assignment_not_repeated`: Second call does NOT include `alertMetadata` after `track_notified_at` is set
- `test_no_alert_when_track_already_assigned`: Token created after track already assigned doesn't trigger alert
- `test_force_refresh_for_awaiting_track`: Verify JIT refresh is forced when track is pending and departure is within 30 min
- `test_lirr_mnr_track_assigned_at`: Verify LIRR/MNR collectors set `track_assigned_at`

## Latency Analysis (After Implementation)

| Scenario | Before | After |
|----------|--------|-------|
| NJT, track assigned between collection cycles | Up to 31 min | ~1 min (force refresh on every LA cycle) |
| NJT hot train (<15 min to departure) | ~3 min | ~1 min |
| LIRR/MNR | ~5 min | ~1 min (force refresh on every LA cycle) |
| Best case (user viewing train) | ~1-2 min | ~1 min |

The 1-minute floor is the Live Activity scheduler interval. Could be reduced further by increasing LA update frequency for tokens awaiting track, but 1 minute is a good starting point.

## What We're NOT Doing

- **No new scheduled job**: The existing 1-minute LA update loop handles everything
- **No iOS changes**: The `handleCriticalEventNotification` + `createFallbackNotification("track_assigned")` path already works
- **No device token linkage**: Using local notifications triggered by LA push, not a separate APNS alert push
- **No Amtrak**: Amtrak API doesn't provide track/platform data
- **No Subway**: Subway doesn't have meaningful platform assignments
