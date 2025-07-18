# Historical Data Migration Script

This script migrates historical train data from the old PostgreSQL database dump to the new SQLite backend_v2 database.

## Usage

```bash
# Basic usage (assumes dump.sql and trackrat_v2.db in current directory)
python scripts/migrate_historical_data.py

# Specify custom file paths
python scripts/migrate_historical_data.py --dump-file /path/to/dump.sql --db-file /path/to/trackrat_v2.db
```

## Features

- **Idempotent**: Can be run multiple times safely - skips already imported data
- **Progress tracking**: Shows progress while parsing large dump files
- **Error handling**: Continues processing even if individual records fail
- **Summary statistics**: Reports number of journeys and stops created

## What Gets Migrated

### From PostgreSQL `trains` table → SQLite `train_journeys`:
- Train ID and journey date
- Line information (code and name)
- Departure times (scheduled and actual)
- Track assignments
- Cancellation status
- Origin station

### From PostgreSQL `train_stops` table → SQLite `journey_stops`:
- All stops for each journey
- Scheduled and actual times
- Track assignments (for origin station)
- Departure status

## Data Transformation

1. **Journey Creation**: Groups trains by train_id + date to create unique journeys
2. **Delay Calculation**: Uses delay_minutes field to calculate actual departure times
3. **Status Mapping**: 
   - 'CANCELLED' → is_cancelled = true
   - 'DEPARTED'/'ARRIVED' → is_completed = true
4. **Track Preservation**: Origin station tracks are preserved from trains table

## Limitations

- Only imports NJ Transit data (data_source = 'njtransit')
- Model prediction data is not migrated (can be regenerated)
- Detailed audit trails are not preserved
- Terminal station is assumed to be same as origin (can be updated later)

## Re-running After Database Recreation

When `trackrat_v2.db` is recreated:

1. Ensure database has latest schema: `alembic upgrade head`
2. Run migration script: `python scripts/migrate_historical_data.py`
3. Check summary for successful imports

The script will automatically skip any data that's already been imported, making it safe to run multiple times.