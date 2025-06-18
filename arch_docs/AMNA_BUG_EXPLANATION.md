# Train Stop Inactive Marking Bug Explanation

## Summary

Train stops are being incorrectly marked as inactive during data collection, even though they are present in the API response. This is caused by a time normalization mismatch in the stop matching logic.

**STATUS: ✅ FIXED** - The bug has been resolved by normalizing existing stop times during key creation to match the incoming format.

## Root Cause

The bug occurs due to inconsistent time handling between incoming API data and existing database records:

1. **Incoming stops** have their `scheduled_time` normalized to the nearest minute (seconds removed)
2. **Existing stops** in the database retain their original times with seconds
3. The stop matching logic uses these times as part of the key, causing mismatches

### Example
- Database stop: `scheduled_time = "2025-06-18T18:36:18"`
- Incoming stop: `scheduled_time = "2025-06-18T18:36:00"` (normalized)
- Result: Different keys → Stop marked as inactive

## Code Path

### 1. Data Collection Flow
**File**: `trackcast/services/data_collector.py`
**Lines**: 305-313

```python
# Time normalization happens here
for stop in train_record["stops"]:
    normalized_stop = stop.copy()
    for time_field in ["scheduled_time", "departure_time"]:
        if time_field in normalized_stop and normalized_stop[time_field]:
            normalized_stop[time_field] = (
                station_mapper.normalize_time_to_nearest_minute(
                    normalized_stop[time_field]
                )
            )
    normalized_stops.append(normalized_stop)
```

### 2. Stop Upsertion Logic
**File**: `trackcast/db/repository.py`
**Method**: `TrainStopRepository.upsert_train_stops`
**Lines**: 1621-1652

```python
# Creating keys for existing stops (uses original time with seconds)
existing_map = {}
for stop in existing_stops:
    scheduled_time_key = (
        stop.scheduled_time.isoformat() if stop.scheduled_time else None
    )
    key = (stop.station_name, stop.station_code, scheduled_time_key)
    existing_map[key] = stop

# Creating keys for incoming stops (uses normalized time without seconds)
scheduled_time_key = self._time_to_isoformat(stop_data.get("scheduled_time"))
station_key = (
    stop_data.get("station_name"),
    stop_data.get("station_code"),
    scheduled_time_key,
)
```

### 3. Marking Stops as Inactive
**Lines**: 1764-1779

```python
# Mark missing stops as inactive
for station_key, stop in existing_map.items():
    if station_key not in seen_stops and stop.is_active:
        stop.is_active = False
        stop.api_removed_at = current_time
        logger.info(f"Marked stop {stop.station_name} as inactive for train {train_id}")
```

## Impact

- Stops with non-zero seconds in their scheduled times fail to match after normalization
- These stops are incorrectly marked as inactive on every data collection cycle
- Affects data integrity and causes unnecessary database updates
- Creates confusing logs showing stops being marked inactive when they exist in the API

## Evidence

From the logs on 2025-06-18 18:01:44:
- 19 trains processed from Newark Penn Station
- Multiple stops marked as inactive across various trains
- API JSON shows all these stops were actually present with complete data

Example: Train 3862 had all 12 stops in the API response, but 3 were marked inactive due to time mismatches.