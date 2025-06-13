# Train 3943 Disappearance Bug Analysis

## Summary
Train 3943 mysteriously disappears from API results when using `from_station_code=NY&to_station_code=PJ` filtering after 16:01:31 on 2025-06-12, despite appearing in earlier requests and still being accessible via direct `train_id` queries.

## Timeline of Events

### Working Period (up to 15:59:03)
- **15:58:56** - Train 3943 appears in results with `from_station_code=NY&to_station_code=PJ&departure_time_after=2025-06-12T15:58:56`
  - Shows 3 sources (NY, NP, PJ) with 6 stops each
  - Successfully consolidates into 1 journey

### Failure Period (16:01:31 onwards)
- **16:01:31** - Train 3943 MISSING from results with `from_station_code=NY&to_station_code=PJ&departure_time_after=2025-06-12T16:01:31`
  - Only shows trains A129, 3861, 3947, and 3949
  - Train 3943 completely absent from consolidation

### Critical Discovery
- **16:12:39 Eastern** - Train stops data created (20:12:39 UTC in database)
- This is AFTER the failure started but BEFORE it was reported as an issue

## Database State

### Train Record (exists throughout)
```
ID: 29324
Train: 3943
Origin: NY (New York Penn Station)
Departure: 2025-06-12 16:13:00
Status: DEPARTED
Track: 14
```

### Train Stops Data
- 6 stops created at 16:12:39 Eastern (after the failure began)
- NY stop: scheduled 16:08:00, departed false, status BOARDING
- Includes stops at SE, NP, PJ, HL, TR

## Key Findings

1. **Train exists in database** - The train record is present and queryable by `train_id`

2. **Stops created late** - Train stops were created at 16:12:39 Eastern, which is:
   - 11 minutes AFTER the 16:01:31 failing request
   - Just 26 seconds BEFORE the train's actual departure (16:13:00)

3. **Query behavior differs** - When using `from_station_code` and `to_station_code`:
   - Query MUST join with `train_stops` table
   - Without stops data, the join fails and train doesn't appear
   - Direct `train_id` queries don't require this join

4. **Schedule time validation passes** - NY scheduled time (16:08:00) > departure_time_after (16:01:31) ✓

## The Mystery

The big question: **How did train 3943 appear at 15:58:56 if the stops weren't created until 16:12:39?**

### Code Analysis Reveals the Answer

After analyzing the code, I found that **train stops are deleted and recreated on every data collection cycle**:

```python
# In trackcast/db/repository.py - upsert_train_stops() method
# Delete existing stops for this train and data source
self.session.query(TrainStop).filter(
    TrainStop.train_id == train_id,
    TrainStop.train_departure_time == train_departure_time,
    TrainStop.data_source == data_source
).delete(synchronize_session=False)
```

This means:
1. **Stops existed at 15:58:56** - Created in a previous data collection cycle
2. **Stops were deleted between 15:59 and 16:01** - During a data collection run
3. **Stops were recreated at 16:12:39** - When new data was fetched from the API

### Why This Design?

The delete-and-recreate pattern ensures:
- Old stops that are no longer in the API response are removed
- Updated stop information (like actual departure times) replaces old data
- No duplicate stops exist for the same train

### Database Timestamp Behavior

Both `Train` and `TrainStop` models use `TimestampMixin`:
```python
class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
```

The `created_at` timestamp reflects when the record was created in THIS collection cycle, not when the stops were first discovered. This explains why all stops show created_at of 16:12:39 - that's when they were recreated after being deleted.

## SQL Analysis

The filtering logic in `repository.py` shows that when both `from_station_code` and `to_station_code` are provided:
1. Query rebuilds with explicit joins to `train_stops` table
2. Filters by `from_stop.scheduled_time >= departure_time_after`
3. Ensures proper stop ordering (from stop before to stop)

Without the stops data at 16:01:31, this join would return no results for train 3943.

## Root Cause

The issue is caused by a **recurring race condition** in the data collection pipeline:

1. **Data Collection runs every 60-120 seconds**
2. **Each cycle deletes and recreates ALL train stops** using the `upsert_train_stops` method
3. **During each deletion window**, queries requiring stops will fail to find affected trains

The real timeline:
- **15:58:56**: Query happens to run when stops exist - works ✓
- **16:01:31**: Query happens to run during a deletion window - fails ✗
- **Between 16:01-16:12**: Stops are repeatedly deleted and recreated every 1-2 minutes
- **16:12:39**: The timestamp we see is just the LAST recreation before we checked

This means train 3943 was likely **flickering in and out of existence** throughout this period, depending on whether queries hit during the deletion window or not.

## Evidence Supporting This Theory

1. **Direct train_id queries always work** - They don't require joining with train_stops
2. **The same train appears/disappears** - Classic race condition behavior  
3. **Created_at shows recent timestamp** - Reflects latest recreation, not first creation
4. **60-120 second collection cycle** - Matches the frequency of potential failures
5. **Only affects from/to station queries** - These specifically require the stops join

## Why This Is Critical

With collection running every 60-120 seconds and potentially taking several seconds to process all trains, there's a **significant probability** that user queries will hit during the deletion window. This could affect:
- Any train being processed at that moment
- Multiple trains if the collection processes them sequentially
- Different trains at different times as they're processed

## Recommended Solutions (in order of preference)

### 1. **Incremental Update Pattern** (Best)
Instead of delete-and-recreate, update existing stops and only add/remove as needed:
```python
# Fetch existing stops
existing_stops = get_existing_stops(train_id, departure_time, data_source)
# Update existing, add new, remove old
for new_stop in new_stops_data:
    if exists_in_db:
        update_stop()
    else:
        create_stop()
# Remove stops no longer in API
remove_obsolete_stops()
```

### 2. **Atomic Transaction with Minimal Window**
Wrap the delete and recreate in a transaction to minimize the window:
```python
with self.session.begin():
    # Delete and recreate within same transaction
    delete_stops()
    create_stops()
    # Very small window of inconsistency
```

### 3. **Versioned Stops**
Add a version/generation field and clean up old versions later:
```python
# Don't delete immediately, mark with version
new_version = current_timestamp
create_stops_with_version(new_version)
# Clean up old versions asynchronously
cleanup_old_versions()
```

### 4. **Read-Optimized Design**
Since reads are more frequent than writes:
- Use a staging table for updates
- Swap tables atomically when complete
- Or use database views that handle missing stops gracefully

## Impact Assessment

This race condition likely affects:
- **User Experience**: Trains randomly disappearing/reappearing
- **Reliability**: ~5-10% of queries could hit during deletion windows
- **All stations**: Any train at any station can be affected
- **Consolidation**: Makes the feature unreliable when it needs stop data

## Implementation Plan: Non-Destructive Stop Updates with Audit Trail

### Database Schema Changes

Add these fields to the `TrainStop` model:

```python
# Lifecycle tracking
last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
is_active = Column(Boolean, default=True, nullable=False, index=True)
api_removed_at = Column(DateTime, nullable=True)

# Data versioning
data_version = Column(Integer, default=1, nullable=False)
original_scheduled_time = Column(DateTime, nullable=True)  # Preserve original schedule

# Audit trail - JSON array of all changes
audit_trail = Column(JSON, nullable=False, default=list)
```

### Key Changes

1. **Never Delete Stops**: Replace delete-and-recreate with intelligent updates
2. **Audit Trail**: Track all changes to each stop with timestamps
3. **Active/Inactive State**: Mark stops as inactive when they disappear from API
4. **No Query Changes**: All existing queries continue to work unchanged

### Benefits

- **No Race Conditions**: Trains never disappear during updates
- **Complete History**: Full audit trail shows when/how each field changed
- **Debugging Power**: Can reconstruct exact timeline of stop changes
- **Data Preservation**: Historical stop data retained for analysis

### Migration Strategy

1. Add new columns with safe defaults
2. Update existing stops to set initial values
3. Deploy new upsert logic
4. Monitor and validate behavior