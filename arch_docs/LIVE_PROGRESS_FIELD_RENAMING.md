# Live Progress Field Renaming Strategy

## Executive Summary

This document outlines a comprehensive strategy to fix the train stop time field naming and mapping issues in the TrackRat backend. The current system incorrectly overwrites scheduled departure times with actual departure times, causing impossible time sequences in API responses. This fix will provide clear, accurate time tracking for all train stops.

## Problem Statement

### Current Issues

1. **Field Naming Confusion**: The field `scheduled_time` is ambiguous - it represents scheduled arrival time but isn't clearly named.

2. **Data Overwriting**: The `train_stop_updater.py` incorrectly overwrites `departure_time` (scheduled departure) with actual departure times from the NJ Transit API, causing:
   - Actual arrival times appearing after departure times (impossible)
   - Loss of scheduled departure data
   - Incorrect delay calculations

3. **Missing Fields**: No field exists to store actual departure times, preventing accurate progress tracking.

4. **API Inconsistency**: The consolidated API response doesn't include `actual_arrival_time`, even though it's available in the database.

### Example of Current Problem

```json
{
  "station_code": "NP",
  "scheduled_time": "2025-06-22T16:10:15",
  "departure_time": "2025-06-22T16:12:00",    // Gets overwritten with actual
  "actual_arrival_time": "2025-06-22T16:18:00"
}
```

After train_stop_updater runs:
```json
{
  "station_code": "NP", 
  "scheduled_time": "2025-06-22T16:10:15",
  "departure_time": "2025-06-22T16:19:30",    // Now contains actual departure!
  "actual_arrival_time": "2025-06-22T16:18:00" // Train arrived before it departed?!
}
```

## Solution Overview

### New Field Schema

| Old Field Name | New Field Name | Description | Source |
|----------------|----------------|-------------|---------|
| `scheduled_time` | `scheduled_arrival` | When train should arrive at platform | getTrainSchedule TIME |
| `departure_time` | `scheduled_departure` | When train should depart from platform | getTrainSchedule DEP_TIME |
| `actual_arrival_time` | `actual_arrival` | When train actually arrived at platform | getTrainStopList TIME |
| (new) | `actual_departure` | When train actually departed from platform | getTrainStopList DEP_TIME |

### NJ Transit API Mapping

#### getTrainSchedule (Initial Collection)
- `TIME` → `scheduled_arrival`
- `DEP_TIME` → `scheduled_departure`
- `DEPARTED` → `departed`
- `STOP_STATUS` → `stop_status`

#### getTrainStopList (Real-time Updates)
- `TIME` → `actual_arrival`
- `DEP_TIME` → `actual_departure`
- `DEPARTED` → `departed`
- `STOP_STATUS` → `stop_status`

## Implementation Plan

### Phase 1: Database Migration

1. **Add new columns**:
   - `scheduled_arrival` (rename from `scheduled_time`)
   - `scheduled_departure` (rename from `departure_time`)
   - `actual_arrival` (rename from `actual_arrival_time`)
   - `actual_departure` (new column)

2. **Migration strategy**:
   - Create new columns alongside old ones
   - Copy data from old to new columns
   - Update code to use new columns
   - Drop old columns after verification

### Phase 2: Code Updates

#### 2.1 Update Database Models (`models.py`)

```python
class TrainStop(Base):
    # Timing information - clear naming
    scheduled_arrival = Column(DateTime, nullable=True)    # When train should arrive
    scheduled_departure = Column(DateTime, nullable=True)  # When train should depart
    actual_arrival = Column(DateTime, nullable=True)       # When train actually arrived
    actual_departure = Column(DateTime, nullable=True)     # When train actually departed
```

#### 2.2 Update Collectors (`collectors.py`)

```python
# In process_train_schedule_data:
stops.append({
    "station_code": station_code,
    "station_name": station_name,
    "scheduled_arrival": stop_time,      # Was: scheduled_time
    "scheduled_departure": dep_time,     # Was: departure_time
    "actual_arrival": None,
    "actual_departure": None,
    "departed": departed_val == "YES",
    "stop_status": status_val
})
```

#### 2.3 Fix Train Stop Updater (`train_stop_updater.py`)

```python
# Update actual times - NEVER modify scheduled times!
if stop_data.get('TIME'):
    existing_stop.actual_arrival = self._parse_nj_datetime(stop_data['TIME'])

if stop_data.get('DEP_TIME'):
    existing_stop.actual_departure = self._parse_nj_datetime(stop_data['DEP_TIME'])
```

#### 2.4 Update API Models (`api/models.py`)

```python
class TrainStop(BaseModel):
    station_code: Optional[str] = None
    station_name: str
    scheduled_arrival: Optional[datetime] = None
    scheduled_departure: Optional[datetime] = None
    actual_arrival: Optional[datetime] = None
    actual_departure: Optional[datetime] = None
    departed: bool = False
    stop_status: Optional[str] = None

class ConsolidatedStop(BaseModel):
    # Same fields as TrainStop plus:
    departed_confirmed_by: List[str] = []
    platform: Optional[str] = None
```

#### 2.5 Update Consolidation Service (`train_consolidation.py`)

```python
# In _merge_stops method:
stop_map[key] = {
    "station_code": stop.station_code,
    "station_name": stop.station_name,
    "scheduled_arrival": stop.scheduled_arrival.isoformat() if stop.scheduled_arrival else None,
    "scheduled_departure": stop.scheduled_departure.isoformat() if stop.scheduled_departure else None,
    "actual_arrival": stop.actual_arrival.isoformat() if stop.actual_arrival else None,
    "actual_departure": stop.actual_departure.isoformat() if stop.actual_departure else None,
    "departed": stop.departed,
    "departed_confirmed_by": [],
    "stop_status": stop.stop_status,
    "platform": train.track if stop.station_code == train.origin_station_code else None
}
```

### Phase 3: API Response Updates

Ensure both consolidated and non-consolidated responses include all time fields:

```json
{
  "station_code": "NP",
  "station_name": "Newark Penn Station",
  "scheduled_arrival": "2025-06-22T16:10:15",
  "scheduled_departure": "2025-06-22T16:12:00",
  "actual_arrival": "2025-06-22T16:18:00",
  "actual_departure": "2025-06-22T16:19:30",
  "departed": true,
  "stop_status": "Late"
}
```

### Phase 4: Testing Strategy

1. **Unit Tests**:
   - Test new field mappings in collectors
   - Test train stop updater doesn't overwrite scheduled times
   - Test consolidation includes all fields

2. **Integration Tests**:
   - Test full data flow from collection to API response
   - Test consolidated vs non-consolidated responses
   - Verify example query works correctly

3. **Manual Testing**:
   - Test with real NJ Transit data
   - Verify iOS app receives correct times
   - Check delay calculations are accurate

## Rollback Plan

If issues arise:

1. **Database**: Migration includes rollback to restore old columns
2. **Code**: Git revert to previous commit
3. **API**: Maintain backward compatibility during transition

## Success Criteria

1. **Data Integrity**: No scheduled times are overwritten
2. **Complete Information**: All four time points are captured
3. **API Consistency**: Both response types include all fields
4. **iOS Compatibility**: App displays realistic times
5. **Query Functionality**: Example query returns correct data

## Timeline

1. **Day 1**: Database migration and model updates
2. **Day 2**: Update collectors and stop updater
3. **Day 3**: API and consolidation updates
4. **Day 4**: Testing and verification
5. **Day 5**: Deployment and monitoring

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data loss during migration | High | Backup database before migration |
| API breaking changes | High | Maintain old field names temporarily |
| iOS app incompatibility | Medium | Coordinate with iOS team on field names |
| Performance impact | Low | Index new columns appropriately |

## Monitoring

Post-deployment monitoring:

1. Track API error rates
2. Monitor data collection pipeline
3. Verify stop update process
4. Check iOS app functionality
5. Review delay calculation accuracy

## Conclusion

This comprehensive field renaming will:
- Eliminate data overwriting issues
- Provide complete journey timing data
- Enable accurate progress tracking
- Support better delay calculations
- Improve API clarity and consistency

The careful, phased approach ensures minimal disruption while fixing a critical data integrity issue.