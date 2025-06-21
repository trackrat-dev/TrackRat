# Performance Improvements for TrackRat Backend API

## Overview
This document outlines the performance improvements implemented to address slow API response times, particularly for the `/api/trains/` endpoint with consolidation enabled.

## Problem Analysis
The API was experiencing ~10 second response times due to:

1. **N+1 Query Problem**: For each train returned, a separate database query was made to fetch stops
2. **Missing Database Indexes**: Complex queries lacked proper indexes for optimization
3. **Inefficient Stop Loading**: Individual queries per train instead of batch loading

## Solution Implemented

### 1. Eager Loading for Train Stops

**File Modified**: `trackcast/db/repository.py`

**Changes**:
- Added `get_trains_with_stops()` method that loads stops for multiple trains in a single query
- Uses batch loading strategy to eliminate N+1 queries
- Groups stops by train ID for efficient lookup

**Key Benefits**:
- Reduces 100+ individual queries to just 2-3 queries
- Dramatically improves response time for APIs that load many trains

### 2. API Endpoint Optimization

**File Modified**: `trackcast/api/routers/trains.py`

**Changes**:
- Updated `list_trains()` endpoint to use eager loading
- Replaced individual `_enrich_train_with_stops()` calls with batch loading
- Maintained existing functionality while improving performance

**Key Benefits**:
- Direct application of eager loading to the slow endpoint
- Preserves all existing features (consolidation, filtering, etc.)

### 3. Database Indexes

**Files Added**:
- `trackcast/db/migrations/add_performance_indexes.sql`
- `trackcast/db/migrations/add_performance_indexes.py`

**File Modified**: `trackcast/cli.py`

**Indexes Added**:
1. `idx_train_stops_train_lookup`: Composite index on `(train_id, train_departure_time, scheduled_time)`
2. `idx_train_stops_station_scheduled`: Index on `(station_code, scheduled_time)` for station filtering
3. `idx_train_stops_departed`: Index on `departed` for filtering future stops
4. `idx_train_stops_station_departed_scheduled`: Composite index for complex from/to queries
5. `idx_train_stops_data_source`: Index on `data_source` for source filtering
6. `idx_trains_id_train_id_departure`: Index on trains table for consolidation queries

**CLI Command Added**:
```bash
trackcast migrate-performance-indexes
trackcast migrate-performance-indexes --rollback  # to remove indexes
```

## Deployment Instructions

### 1. Apply Database Migrations
```bash
# Navigate to backend directory
cd backend

# Apply the performance indexes
trackcast migrate-performance-indexes
```

### 2. Deploy Code Changes
The code changes are backward compatible and can be deployed immediately:
- `trackcast/db/repository.py` - New eager loading method
- `trackcast/api/routers/trains.py` - Updated API endpoint
- `trackcast/cli.py` - New migration command

### 3. Verify Performance
Use the test script to verify improvements:
```bash
python3 test_performance_improvements.py
```

## Expected Performance Improvements

### Before Optimization
- **Response Time**: ~10 seconds for 100 trains with consolidation
- **Database Queries**: 100+ individual queries for stops
- **Bottleneck**: N+1 query problem + missing indexes

### After Optimization  
- **Response Time**: Expected 1-3 seconds for same request
- **Database Queries**: 2-3 queries total (1 for trains, 1 for stops)
- **Improvement**: 70-90% reduction in response time

## Monitoring

### Query Performance Metrics
The repository includes timing metrics that are exposed via:
- `DB_QUERY_DURATION_SECONDS.labels(query_type="get_trains_with_stops")`
- Existing `get_trains` timing is preserved

### Logs to Monitor
Look for these log messages:
```
INFO - Eager loading stops for X trains
INFO - Loaded stops for X trains in Y.YYYs
```

## Rollback Plan

If issues are encountered:

### 1. Rollback Database Indexes
```bash
trackcast migrate-performance-indexes --rollback
```

### 2. Rollback Code Changes
```bash
# Restore from backup
cp trackcast/db/repository.py.backup.perf trackcast/db/repository.py
# Then remove the eager loading changes from trains.py
```

## Testing

### Unit Tests
Added comprehensive unit tests for all new functionality:

**Test Files Added:**
- `tests/unit/test_eager_loading.py` - Tests for the new eager loading functionality
- `tests/unit/test_performance_migrations.py` - Tests for database migration functionality

**Test Coverage:**
- Eager loading query optimization and N+1 prevention
- Database migration execution and error handling  
- Integration with existing migration system
- CLI command functionality
- Performance improvement validation

### Automated Database Migrations
The performance indexes are now **automatically applied during application startup** via the existing migration system:

**Integration Added:**
- New migration function `add_performance_indexes()` in `trackcast/db/migrations.py`
- Automatically runs when `trackcast update-schema` is called
- Included in the standard migration sequence during deployment
- Uses idempotent `IF NOT EXISTS` statements for safe re-runs

**No Manual Migration Required:**
The performance improvements will be applied automatically on the next deployment when the application starts up and runs its migration sequence.

### Manual Testing (Optional)
For manual verification, test the specific slow endpoint:
```bash
curl "https://trackrat-api-dev-41862227966.us-central1.run.app/api/trains/?from_station_code=MP&to_station_code=PJ&departure_time_after=2025-06-21T11:45:46&limit=100&consolidate=true"
```

## Files Modified/Added

### Modified Files
1. `trackcast/db/repository.py` - Added eager loading method
2. `trackcast/api/routers/trains.py` - Updated endpoint to use eager loading  
3. `trackcast/cli.py` - Added migration command

### Added Files
1. `trackcast/db/migrations/add_performance_indexes.sql` - SQL migration
2. `trackcast/db/migrations/add_performance_indexes.py` - Python migration
3. `tests/unit/test_eager_loading.py` - Unit tests for eager loading functionality
4. `tests/unit/test_performance_migrations.py` - Unit tests for migration functionality
5. `PERFORMANCE_IMPROVEMENTS.md` - This documentation

### Backup Files
1. `trackcast/db/repository.py.backup.perf` - Backup before changes

## Future Optimizations

Additional improvements that could be implemented:
1. **Query Result Caching**: Cache frequent queries for additional speed
2. **Database Connection Pooling**: Optimize connection management
3. **Pagination Optimization**: Improve large result set handling
4. **GraphQL Migration**: More efficient data fetching patterns

## Notes
- All changes are backward compatible
- No breaking changes to existing API contracts
- Migration can be safely rolled back if needed
- Performance improvements scale with the number of trains requested