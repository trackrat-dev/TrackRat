# TrackRat Backend V2 - Development Guide for Claude

This guide provides comprehensive information for Claude Code when working with the TrackRat Backend V2, a radical simplification of the train tracking system that reduces API calls by ~95% while maintaining production robustness.

**Last Updated:** April 2026
**Database:** PostgreSQL with asyncpg (production-ready)
**Key Features:** Multi-transit support (NJT, Amtrak, PATH, PATCO, LIRR, Metro-North, NYC Subway, BART, MBTA, Metra, WMATA), track/delay predictions, route alerts, API caching, schedule generation, GTFS integration

## Quick Start

```bash
# Install dependencies
cd backend_v2
poetry install

# Run database migrations
alembic upgrade head

# Start the development server
poetry run uvicorn trackrat.main:app --reload --port 8000

# Run tests
poetry run pytest
```

## Architecture Overview

### Core Philosophy: Radical Simplicity

The V2 backend eliminates the complexity of V1 by:
- **Single source of truth**: One database record per train journey per day
- **Minimal API calls**: ~95% reduction through smart caching and scheduling
- **No consolidation needed**: Unified data model from the start
- **PostgreSQL**: Production-ready database with async driver and connection pooling
- **Multi-Transit Support**: NJ Transit, Amtrak, PATH, PATCO, LIRR, Metro-North, NYC Subway, BART, MBTA, Metra, and WMATA data sources with extensible architecture
- **Prediction Features**: Track predictions, arrival forecasting, delay/cancellation forecasting, and congestion analysis
- **API Response Caching**: Intelligent caching system for performance optimization

### System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Transit APIs    │────▶│  Backend V2     │────▶│  Client Apps    │
│ • NJ Transit    │     │ • Discovery     │     │ • iOS App       │
│ • Amtrak        │     │ • Schedule Gen  │     │ • Android App   │
│ • PATH          │     │ • JIT Updates   │     │ • Web App       │
│ • PATCO (GTFS)  │     │ • Predictions   │     │ • Live Activities│
│ • LIRR (GTFS-RT)│     │ • GTFS Feed     │     └─────────────────┘
│ • MNR (GTFS-RT) │     │ • API Caching   │
│ • Subway(GTFS-RT)│    │ • Route Alerts  │
│ • BART (GTFS-RT)│     │ • Analytics     │
│ • MBTA (GTFS-RT)│     │ • Validation    │
│ • Metra(GTFS-RT)│     └────────┬────────┘
│ • WMATA (REST)  │              │
└─────────────────┘     ┌────────▼────────┐
                        │   PostgreSQL    │
                        │ • Train Data    │
                        │ • ML Models     │
                        │ • Analytics     │
                        │ • Cache         │
                        │ • Schedules     │
                        └─────────────────┘
```

## Key Components

### 1. Data Collection Pipeline

**Multi-Phase Approach:**

1. **Schedule Generation** (Daily)
   - **NJT**: Fetches 27-hour schedule data once daily, creates SCHEDULED journey records
   - **Amtrak**: Analyzes 22-day patterns, generates SCHEDULED records for expected trains
   - Provides future train visibility beyond 30-60 minute window

2. **Discovery Phase** (Every 30 minutes, configurable)
   - **NJT**: Polls 21 stations (NY, NP, TR, LB, PL, DN, MP, HB, HG, GL, ND, BU, HQ, DV, JA, RA, ST, SV, RW, WW, HN) via `getTrainSchedule`
   - **Amtrak**: Polls major stations for active trains
   - Updates journey records from SCHEDULED to OBSERVED when trains appear

3. **Collection Phase** (Every 15 minutes, configurable)
   - Collects full journey details via `getTrainStopList` (NJT) or station APIs (Amtrak)
   - Updates all stops with actual times and tracks
   - Only collects trains discovered in last 90 minutes

4. **JIT Update Phase** (On-demand)
   - Refreshes data when requested by users
   - Only updates if data is >60 seconds stale
   - Ensures real-time accuracy without constant polling

5. **Validation Phase** (Hourly)
   - Validates train coverage across key routes
   - Detects missing trains and API discrepancies
   - Updates metrics for monitoring dashboard

### 2. Database Schema

```sql
-- Core journey record (one per train per day)
train_journeys (
    id, train_id, journey_date, line_code, line_name, line_color,
    destination, origin_station_code, terminal_station_code,
    data_source (NJT/AMTRAK/PATH/PATCO/LIRR/MNR/SUBWAY/BART/MBTA/METRA/WMATA), observation_type (OBSERVED/SCHEDULED),
    first_seen_at, last_updated_at, update_count,
    scheduled_departure, scheduled_arrival, actual_departure, actual_arrival,
    has_complete_journey, stops_count, is_cancelled, cancellation_reason, is_completed,
    api_error_count, is_expired, discovery_track, discovery_station_code

-- Individual stops with times and tracks
-- NOTE: updated_arrival / updated_departure have INVERTED semantics for NJT.
-- For most providers these are live estimates. For NJT intermediate stops,
-- updated_departure = original schedule, updated_arrival = live estimate.
-- Consumers must use max(updated_departure, updated_arrival) for NJT departures.
-- See database.py JourneyStop model for full documentation.
journey_stops (
    journey_id, station_code, station_name, stop_sequence,
    scheduled_departure, scheduled_arrival,
    updated_departure, updated_arrival,
    actual_departure, actual_arrival,
    raw_amtrak_status, raw_njt_departed_flag,
    has_departed_station, departure_source, arrival_source,
    track, track_assigned_at, pickup_only, dropoff_only,
    created_at, updated_at
)

-- Transit time analysis (NEW)
segment_transit_times (
    journey_id, from_station_code, to_station_code,
    scheduled_minutes, actual_minutes, delay_minutes,
    departure_time, hour_of_day, day_of_week
)

-- Station dwell time analysis (NEW)
station_dwell_times (
    journey_id, station_code, scheduled_minutes, actual_minutes,
    excess_dwell_minutes, is_origin, is_terminal,
    arrival_time, departure_time, hour_of_day, day_of_week
)

-- Real-time journey progress (NEW)
journey_progress (
    journey_id, last_departed_station, next_station,
    stops_completed, stops_total, journey_percent,
    initial_delay_minutes, total_delay_minutes,
    cumulative_transit_delay, cumulative_dwell_delay,
    prediction_confidence, prediction_based_on
)

-- Historical snapshots for ML training
journey_snapshots (
    journey_id, captured_at, raw_stop_list_data,
    train_status, delay_minutes, completed_stops, total_stops,
    track_assignments
)

-- API response caching
cached_api_responses (
    id, endpoint, params_hash, params, response, created_at, expires_at
)

-- Scheduler coordination (for horizontal scaling)
scheduler_task_runs (
    task_name, last_successful_run, last_attempt, run_count,
    average_duration_ms, last_duration_ms, last_instance_id,
    created_at, updated_at
)

-- Live Activity tokens
live_activity_tokens (
    id, push_token, activity_id, train_number,
    origin_code, destination_code, expires_at
)

-- Validation results
validation_results (
    id, run_at, route, source,
    transit_train_count, api_train_count, coverage_percent,
    missing_trains, extra_trains, details
)

-- Device tokens for push notifications
device_tokens (
    id, device_id, apns_token, created_at, updated_at
)

-- Route alert subscriptions
route_alert_subscriptions (
    id, device_id, data_source, line_id, from_station_code, to_station_code,
    train_id, direction, active_days, active_start_minutes, active_end_minutes,
    timezone, delay_threshold_minutes, service_threshold_pct, cancellation_threshold_pct,
    notify_cancellation, notify_delay, notify_recovery,
    digest_time_minutes, include_planned_work,
    created_at, last_alerted_at, last_alert_hash, last_digest_at, last_service_alert_ids
)

-- Discovery run tracking
discovery_runs (
    id, data_source, station_code, started_at, completed_at,
    trains_found, trains_created, trains_updated, error
)

-- MTA service alerts
service_alerts (
    id, alert_id, data_source, alert_type, header, description,
    affected_routes, affected_stops, active_periods, is_active,
    first_seen_at, last_seen_at, created_at, updated_at
)

-- GTFS static data tables
gtfs_feed_info, gtfs_routes, gtfs_trips, gtfs_stop_times,
gtfs_calendar, gtfs_calendar_dates

-- Route preferences
route_preferences (
    id, device_id, from_station_code, to_station_code, data_source,
    display_order, created_at, updated_at
)
```

### 3. API Endpoints

All endpoints are prefixed with `/api/v2/`:

```python
# Train Operations
GET /trains/departures?from=NY&to=TR&limit=50         # Find departures between stations
GET /trains/{train_id}?date=2024-01-01&refresh=true   # Get specific train journey
GET /trains/{train_id}/history?date=2024-01-01        # Historical train performance
GET /trains/stations/{station_code}/tracks/occupied   # Real-time track occupancy

# Route Analytics
GET /routes/history?from_station=NY&to_station=TR&data_source=NJT&days=30  # Historical route performance
GET /routes/congestion?time_window_hours=3&data_source=NJT                 # Real-time congestion analysis
GET /routes/summary                                   # Natural language operations summary
GET /routes/segments/{from}/{to}/trains?hours=24      # Segment train records

# Predictions
GET /predictions/track?station_code=NY&train_id=1234&journey_date=2024-01-01  # Track prediction
GET /predictions/delay?train_id=1234&station_code=NY&journey_date=2024-01-01  # Delay/cancellation forecast
GET /predictions/supported-stations                   # Stations with predictions

# Route Alerts & Service Alerts
POST /devices/register                               # Register APNS device token
PUT  /alerts/subscriptions                           # Sync route alert subscriptions
GET  /alerts/subscriptions/{device_id}               # Get current alert subscriptions
GET  /alerts/service                                 # MTA service alerts (planned work, delays)

# Validation
GET /validation/status                               # Validation status and recent results
GET /validation/results/{route}/{source}             # Route-specific validation details

# Feedback
POST /feedback                                       # Submit user feedback

# Live Activities Management
POST /live-activities/register    # Register Live Activity
DELETE /live-activities/{token}   # Unregister Live Activity

# Admin (NOT under /api/v2/ prefix)
GET /admin/stats              # Server usage statistics (HTML, supports ?hours=N&ios_only=true)
GET /admin/stats.json         # Server usage statistics (JSON)

# Trip Search
GET /trips/search             # Multi-leg trip search with transfers

# Route Preferences
GET /routes/preferences       # User route preferences
PUT /routes/preferences       # Update route preferences

# System Health and Metrics
GET /health                    # Comprehensive health check
GET /health/live              # Liveness probe
GET /health/ready             # Readiness probe
GET /scheduler/status         # Detailed scheduler status
GET /metrics                  # Prometheus metrics
```

### 4. Background Scheduler (Horizontally Scalable)

The APScheduler runs in-process and handles:
- **Daily at 12:30 AM ET**: NJT schedule collection (27-hour schedules)
- **Daily at 12:45 AM ET**: Amtrak pattern-based schedule generation
- **Daily at 1:00 AM ET**: Lock manager cleanup
- **Daily at 3:00 AM ET**: GTFS static schedule refresh
- **Every 30 min**: NJT and Amtrak train discovery from major stations
- **Every 4 min**: PATH collection (unified, RidePATH API)
- **Every 4 min**: LIRR collection (unified, MTA GTFS-RT)
- **Every 4 min**: Metro-North collection (unified, MTA GTFS-RT)
- **Every 4 min**: NYC Subway collection (8 GTFS-RT feeds, 36 routes)
- **Every 4 min**: BART collection (unified, GTFS-RT)
- **Every 4 min**: MBTA Commuter Rail collection (unified, GTFS-RT)
- **Every 4 min**: Metra collection (unified, GTFS-RT, requires API token)
- **Every 3 min**: WMATA/DC Metro collection (REST API, requires API key)
- **Every 5 min**: Journey update checks for active trains
- **Every 90 sec**: Departure cache pre-computation
- **Every 5 min**: Route history cache pre-computation
- **Every 15 min**: Congestion cache pre-computation
- **Every 15 min**: Service alerts collection (MTA + NJT)
- **Every 1 min**: Live Activity push notification updates
- **Hourly**: Live Activity token cleanup
- **Hourly**: Train validation across key routes
- **Every 5 min**: Route alert evaluation and push notifications
- **Every 5 min**: Morning digest evaluation
- **Automatic startup**: Begins when FastAPI app starts

**Horizontal Scaling Support:**
- **Database-based coordination**: Multiple replicas coordinate through `scheduler_task_runs` table
- **Freshness checking**: Tasks check last run time before executing to prevent duplicates
- **Safe intervals**: Tasks use 90% of scheduled interval with 2-minute buffer to prevent over-execution
- **Row-level locking**: PostgreSQL `WITH FOR UPDATE SKIP LOCKED` prevents race conditions
- **Instance tracking**: GCE instance hostname tracked for debugging
- **Task-level timeouts**: Each collector task has a timeout of 2x its scheduled interval; stuck tasks are cancelled via `asyncio.TimeoutError`
- **Batch commits**: GTFS-RT collectors commit every 50 trips, preserving partial progress if a task hits its timeout

### 5. Advanced Service Architecture

#### Schedule Generation Services
- **NJTScheduleCollector**: Fetches daily 27-hour schedules, creates SCHEDULED records
- **AmtrakPatternScheduler**: Analyzes 22-day patterns, generates expected train schedules
  - MIN_OCCURRENCES: 2 times in 3 weeks
  - TIME_VARIANCE_THRESHOLD: 35 minutes
  - Creates SCHEDULED records for trains not yet OBSERVED

#### Transit Analytics System

The system now includes comprehensive transit time analysis:

**Components:**
- **TransitAnalyzer**: Calculates segment times, dwell times, and journey progress
- **CongestionAnalyzer**: Real-time network congestion analysis
- **Route Analytics**: Historical performance metrics with delay breakdowns
- **DirectArrivalForecaster**: Real-time arrival time predictions calculated directly from recent journey data without intermediate storage
- **ApiCacheService**: Intelligent response caching with automatic pre-computation
- **TrackOccupancyService**: Real-time track availability analysis for predictions

**Automatic Analysis:**
- Segment transit times between consecutive stations
- Station dwell time tracking (arrival to departure)
- Journey progress updates with real-time position
- Congestion factor calculation using baseline vs current times

**API Endpoints:**
- `/api/v2/routes/congestion` - Real-time network congestion map with caching
- `/api/v2/routes/history` - Historical route performance with delay breakdowns
- `/api/v2/routes/summary` - Natural language operations summary
- `/api/v2/trains/departures` - Train departures with filtering and JIT updates
- `/api/v2/trains/{train_id}` - Enhanced details with progress and arrival forecasting
- `/api/v2/trains/{train_id}/history` - Historical train performance
- `/api/v2/trains/stations/{station_code}/tracks/occupied` - Real-time track availability
- `/api/v2/predictions/track` - Track/platform predictions
- `/api/v2/predictions/supported-stations` - Stations with predictions
- `/api/v2/validation/status` - Validation status and recent results
- `/api/v2/validation/results/{route}/{source}` - Route-specific validation details
- `/api/v2/feedback` - User feedback submission
- `/health` - Comprehensive health with scheduler status and accuracy metrics
- `/scheduler/status` - Detailed scheduler job status
- `/metrics` - Prometheus metrics endpoint

**Congestion Levels:**
- **Normal** (≤10% slower): Green (`#00ff00`)
- **Moderate** (10-25% slower): Yellow (`#ffff00`) 
- **Heavy** (25-50% slower): Orange (`#ff8800`)
- **Severe** (>50% slower): Red (`#ff0000`)

## Development Workflow

### Making Changes

1. **API Changes**:
   - Update models in `models/api.py`
   - Modify endpoints in `api/trains.py`
   - Run tests: `poetry run pytest tests/`

2. **Database Changes**:
   - Create migration: `poetry run alembic revision -m "description"` — this generates a unique 12-char hex revision ID for you. **Never hand-write a migration file with a made-up or placeholder revision ID** (e.g. `a1b2c3d4e5f6`). Duplicate IDs cause Alembic to refuse to load the tree and the backend crash-loops on startup.
   - Edit the generated file in `db/migrations/versions/` (upgrade/downgrade bodies only; leave the `revision =` / `down_revision =` lines alone).
   - Before committing, verify the tree is valid: `poetry run alembic heads` must print exactly one head, and `poetry run alembic upgrade head --sql >/dev/null` must succeed. These two commands catch duplicate revision IDs and broken chains that application tests won't.
   - **NOTE**: Migrations run automatically during application startup (after backup restore). A broken migration tree = staging/prod crash loop.

3. **Collector Changes**:
   - NJT collectors in `collectors/njt/` (discovery.py, journey.py, client.py, schedule.py)
   - Amtrak collectors in `collectors/amtrak/` (discovery.py, journey.py, client.py)
   - PATH collector in `collectors/path/` (collector.py, client.py, ridepath_client.py, segment_times.py)
   - LIRR collector in `collectors/lirr/` (collector.py, client.py)
   - Metro-North collector in `collectors/mnr/` (collector.py, client.py)
   - NYC Subway collector in `collectors/subway/` (collector.py, client.py)
   - BART collector in `collectors/bart/` (collector.py, client.py)
   - MBTA collector in `collectors/mbta/` (collector.py, client.py)
   - Metra collector in `collectors/metra/` (collector.py, client.py)
   - WMATA collector in `collectors/wmata/` (collector.py, client.py)
   - Service alerts collector in `collectors/service_alerts.py`
   - MTA shared logic in `collectors/mta_common.py` and `collectors/mta_extensions.py`
   - Base classes in `collectors/base.py`
   - Test with data in `tests/unit/collectors/`

### Code Style & Quality

```bash
# Format code
poetry run black .

# Lint
poetry run ruff check .

# Type check
poetry run mypy src/

# Run all checks
poetry run black . && poetry run ruff check . && poetry run mypy src/
```

### Testing

```bash
# Unit tests (requires PostgreSQL test database)
poetry run pytest tests/unit/

# Integration tests (requires PostgreSQL)
poetry run pytest tests/integration/

# All tests with coverage
poetry run pytest --cov=trackrat
```

## Configuration

### Environment Variables

```bash
# Required - NJ Transit API
TRACKRAT_NJT_API_TOKEN=your_nj_transit_api_token
TRACKRAT_NJT_API_URL=https://raildata.njtransit.com/api

# Note: Amtrak uses public API - no authentication required
# Amtrak data collected from https://api-v3.amtraker.com/v3/trains

# WMATA (DC Metro) API
TRACKRAT_WMATA_API_KEY=your_wmata_developer_api_key

# Metra GTFS-RT API
TRACKRAT_METRA_API_TOKEN=your_metra_api_token

# Note: BART uses public GTFS-RT feed - no authentication required

# MBTA API (optional, for higher rate limits)
TRACKRAT_MBTA_API_KEY=your_mbta_api_key

# Database Configuration (defaults to PostgreSQL)
TRACKRAT_DATABASE_URL=postgresql+asyncpg://trackratuser:password@localhost:5432/trackratdb
TRACKRAT_LOG_LEVEL=INFO
TRACKRAT_ENVIRONMENT=development

# APNS Settings (for Live Activities)
APNS_TEAM_ID=your_team_id
APNS_KEY_ID=your_key_id
APNS_AUTH_KEY_PATH=certs/apns_auth_key.p8
APNS_BUNDLE_ID=net.trackrat.TrackRat
APNS_ENVIRONMENT=dev

# Backup Settings (optional)
TRACKRAT_GCS_BACKUP_BUCKET=your-backup-bucket

# Collection Intervals (optional)
TRACKRAT_DISCOVERY_INTERVAL_MINUTES=30           # Train discovery frequency
TRACKRAT_JOURNEY_UPDATE_INTERVAL_MINUTES=15      # Journey collection frequency
TRACKRAT_DATA_STALENESS_SECONDS=60               # JIT refresh threshold
TRACKRAT_HOT_DATA_STALENESS_SECONDS=20           # JIT refresh threshold for near-departure trains
TRACKRAT_HOT_TRAIN_WINDOW_MINUTES=15             # How close to departure triggers aggressive refresh
TRACKRAT_HOT_TRAIN_UPDATE_INTERVAL_SECONDS=120   # Update interval for near-departure trains

# Validation Settings (optional)
TRACKRAT_INTERNAL_API_URL=http://localhost:8000  # Internal API for validation
TRACKRAT_VALIDATION_MAX_TRAINS_TO_VERIFY=20      # Max missing trains to verify

# Feature Flags (optional)
TRACKRAT_USE_OPTIMIZED_AMTRAK_PATTERN_ANALYSIS=true  # Database-aggregated patterns
TRACKRAT_ENABLE_SQL_LOGGING=false                    # SQLAlchemy query logging

# Server Settings (optional)
TRACKRAT_DEBUG=false                             # Enable debug mode
TRACKRAT_API_HOST=0.0.0.0                        # API bind host
TRACKRAT_API_PORT=8000                           # API bind port
TRACKRAT_SKIP_MIGRATIONS=false                   # Skip auto-migrations on startup
TRACKRAT_BACKUP_INTERVAL_SECONDS=3600            # GCS backup frequency

# APNS Auth Key Content (alternative to file path)
APNS_AUTH_KEY=                                   # Raw P8 key content (fallback if APNS_AUTH_KEY_PATH unavailable)

# GCE Instance Configuration (for horizontal scaling)
# K_REVISION is automatically set by GCE MIG (used for instance tracking)
```

### Settings Management

Settings are managed via Pydantic in `settings.py`:
- Automatic validation
- Environment variable loading
- Type conversion
- Default values

## Key Implementation Details

### 1. Async Everything

The backend uses async/await throughout:
- `asyncpg` for PostgreSQL database access
- `httpx` for API calls
- FastAPI async endpoints

### 2. Error Handling

Comprehensive error handling with:
- FastAPI HTTPException patterns in `api/utils.py`
- Retry logic for API calls
- Graceful degradation
- Structured error logging

### 3. Performance Optimizations

- Database connection pooling
- Efficient queries with proper indexes
- Minimal API calls through smart caching
- Background processing for heavy operations

### 4. Monitoring & Observability

- **Prometheus metrics** at `/metrics`
- **Structured JSON logging** with correlation IDs
- **Health checks** with detailed scheduler and database status
- **Request middleware** for correlation ID propagation

## Common Tasks

### Running Locally

```bash
# Start the development server
poetry run uvicorn trackrat.main:app --reload

# Use a custom database URL
TRACKRAT_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/custom_db poetry run uvicorn trackrat.main:app

# Run scheduler only
poetry run python -m trackrat.scheduler
```

### Database Operations

```bash
# Create new migration
alembic revision --autogenerate -m "Add new column"

# Apply migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1

# View migration history
alembic history

# Migration files are located in:
# src/trackrat/db/migrations/versions/
```

### Debugging

```python
# Enable debug logging
TRACKRAT_LOG_LEVEL=DEBUG poetry run uvicorn trackrat.main:app

# Use interactive debugger
import ipdb; ipdb.set_trace()

# Check scheduler status
curl http://localhost:8000/health | jq .
```

## Deployment

### Docker

```bash
# Build image
docker build -t trackrat-backend-v2 .

# Run container
docker run -p 8000:8000 \
  -e TRACKRAT_NJT_API_TOKEN=xxx \
  -e TRACKRAT_DATABASE_URL=postgresql+asyncpg://... \
  -e APNS_TEAM_ID=xxx \
  -e APNS_KEY_ID=xxx \
  -e K_REVISION=local-dev \
  trackrat-backend-v2
```

**Important**: Database migrations run automatically during container startup, **after** any backup restore from GCS.

### Production Checklist

- [ ] Set production DATABASE_URL
- [ ] Configure secrets in environment (NJT API token, APNS keys)
- [ ] Enable Prometheus scraping on `/metrics`
- [ ] Set up log aggregation (Cloud Logging, etc.)
- [ ] Configure health check monitoring (`/health/live`, `/health/ready`)
- [ ] Review database connection pool settings
- [ ] Enable CORS for frontend domains
- [ ] Verify K_REVISION is set (used for instance tracking; automatic in GCE MIG)

## Troubleshooting

### Common Issues

1. **No trains found during discovery**
   - Check NJ Transit credentials
   - Verify station codes are correct
   - Check API is accessible

2. **Database connection errors**
   - Verify DATABASE_URL format
   - Check database is running
   - Run migrations: `alembic upgrade head`

3. **Scheduler not running**
   - Check logs for errors
   - Verify APScheduler is starting
   - Check system time is correct

4. **Duplicate task execution in multiple replicas**
   - Check scheduler_task_runs table for task status
   - Verify database locking is working
   - Look for "task_locked_by_another_replica" in logs
   - Ensure K_REVISION env var is set (automatic in GCE MIG)

### Debug Commands

```bash
# Check database connectivity
poetry run python -c "from trackrat.db.engine import get_engine; print('DB engine:', get_engine())"

# Verify NJ Transit API connectivity
curl -s http://localhost:8000/health | jq .data_freshness

# View scheduler jobs
curl http://localhost:8000/health | jq .scheduler

# Check scheduler task run history
poetry run python -c "
import asyncio
from trackrat.db.engine import get_session
from sqlalchemy import text

async def check_tasks():
    async with get_session() as db:
        result = await db.execute(text('SELECT * FROM scheduler_task_runs ORDER BY last_successful_run DESC'))
        for row in result:
            print(f'{row.task_name}: Last run {row.last_successful_run}, Count: {row.run_count}')

asyncio.run(check_tasks())
"
```

## Architecture Decisions

### Why These Choices?

1. **Single journey record**: Eliminates duplicate data issues
2. **30-minute discovery**: Balances freshness with API efficiency  
3. **15-minute collection**: Captures journey progress without excess
4. **60-second staleness**: Real-time feel without constant polling
5. **In-process scheduler**: Simplifies deployment and monitoring
6. **Async throughout**: Maximum performance with Python
7. **Pydantic settings**: Type-safe configuration management
8. **Database-based task coordination**: Simple, robust horizontal scaling without Redis/external services

### Trade-offs Accepted

1. **No Redis**: Simplicity over caching performance
2. **No message queue**: Direct execution over distributed processing
3. **Single deployment**: Monolith over microservices
4. **PostgreSQL-only**: Reliability over configuration simplicity
5. **Connection pooling**: Efficient database access over naive connections

## Future Enhancements

### Planned Features

1. **Enhanced Track Prediction Models**: Improved ML models with occupancy detection
2. **WebSocket Support**: Real-time updates for clients
3. **Additional Transit Systems**: SEPTA regional rail, NJ Light Rail, Caltrain
4. **Advanced Analytics**: Enhanced journey pattern analysis
5. **GraphQL API**: More efficient client queries

### Performance Targets

- API response time: <100ms (p95)
- Discovery completion: <30 seconds
- Journey collection: <5 seconds per train
- Database queries: <10ms
- Memory usage: <512MB

## Contributing Guidelines

### Code Standards

1. **Type hints required**: All functions must have type annotations
2. **Docstrings**: Google style for all public functions
3. **Tests**: Minimum 80% coverage for new code
4. **Async preferred**: Use sync only when necessary
5. **Error handling**: Never swallow exceptions silently

### Pull Request Process

1. Create feature branch from `main`
2. Write tests for new functionality
3. Ensure all checks pass
4. Update documentation
5. Request review from maintainers

## Key Service Classes

### Core Services

The backend is organized into service classes for better maintainability:

#### Data Collection
- **SchedulerService** (`services/scheduler.py`): Manages all background tasks and coordination
- **JustInTimeUpdateService** (`services/jit.py`): On-demand data refresh with staleness checking
- **NJTScheduleCollector** (`collectors/njt/schedule.py`): Daily NJT schedule collection
- **AmtrakPatternScheduler** (`services/amtrak_pattern_scheduler.py`): Pattern-based Amtrak schedules

#### API Services
- **DepartureService** (`services/departure.py`): Train departures with filtering and JIT updates
- **TrainValidationService** (`services/validation.py`): Coverage validation and monitoring
- **ApiCacheService** (`services/api_cache.py`): Intelligent response caching with pre-computation
- **SummaryService** (`services/summary.py`): Natural language operations summaries
- **GTFSService** (`services/gtfs.py`): GTFS static and real-time feed management
- **SegmentNormalizer** (`services/segment_normalizer.py`): Station segment normalization for analytics

#### Analytics & ML
- **TransitAnalyzer** (`services/transit_analyzer.py`): Transit time and dwell time analysis
- **CongestionAnalyzer** (`services/congestion.py`, `services/congestion_types.py`): Real-time network congestion monitoring
- **DirectArrivalForecaster** (`services/direct_forecaster.py`): Direct arrival predictions from recent data
- **HistoricalTrackPredictor** (`services/historical_track_predictor.py`): Historical pattern-based track predictions
- **TrackOccupancyService** (`services/track_occupancy.py`): Real-time track availability
- **DelayForecaster** (`services/delay_forecaster.py`): Delay and cancellation forecasting using hierarchical historical data

#### Route Alerts
- **AlertEvaluatorService** (`services/alert_evaluator.py`): Evaluates delay/cancellation conditions for route alert push notifications
- **AlertsAPI** (`api/alerts.py`): Device registration and alert subscription management endpoints

#### Trip Search & Transfers
- **TripSearchService** (`services/trip_search.py`): Multi-leg trip search across transit systems
- **TransferPoints** (`config/transfer_points.py`): Defines transfer connections between transit systems
- **TripsAPI** (`api/trips.py`): Trip search endpoint

#### Infrastructure
- **SimpleAPNSService** (`services/apns.py`): Apple Push Notifications for Live Activities and Route Alerts
- **BackupService** (`services/backup_service.py`): GCS backup management (optional)

## Recent Improvements & Known Issues

### Recent Improvements (April 2026)
- ✅ Intra-system transfers for PATH, BART, NJT, LIRR, MBTA, Metra trip search
- ✅ Fix NJT congestion 500 error
- ✅ Fix trip search returning routes from disabled transit systems
- ✅ Fix reverse journey search returning no results for transfer trips
- ✅ Disambiguate all duplicate and confusing Amtrak station names
- ✅ Fix startup crash from duplicate 'Hollywood, FL' key in stationCodes dictionary
- ✅ Parallelize transfer queries and cache GTFS service IDs for faster trip search
- ✅ Multi-leg trip details view for web and iOS
- ✅ Open-source release (GPLv3)

### Recent Improvements (March 2026)
- ✅ PATH line color disambiguation: resolves misattribution for overlapping routes (e.g., JSQ-33H vs HOB-33)
- ✅ Expanded subway station complexes: 15+ missing in-station transfers added to STATION_EQUIVALENTS
- ✅ Unified shuttle station equivalences (S901/S902) across backend and iOS
- ✅ Fix cache race condition causing 503s on departures endpoint
- ✅ Fix Alembic migration cycle causing staging crash loop
- ✅ SUBWAY service alerts crash fix caused by duplicate entity IDs in MTA feed
- ✅ NJT alert deduplication and defensive active_periods handling
- ✅ Duplicate-row protection added to GTFS static parsers
- ✅ Removed Newark PATH (PNK) from search; Newark Penn Station covers it via equivalence
- ✅ Merged Newark PATH into Newark Penn Station equivalence group
- ✅ Subscription sync fix preventing notification deduplication state wipe
- ✅ Fix route segment map showing full route instead of selected segment
- ✅ Backend instance upgrade from t2d-standard-1 to t2d-standard-2
- ✅ Multi-leg trip search with transit transfers (`/api/v2/trips/search`)
- ✅ Transfer points configuration for cross-system connections
- ✅ System-wide alert subscriptions (not just per-route)
- ✅ Request stats tracking for API usage metrics
- ✅ Track assignment push notifications
- ✅ LIRR Port Washington line code collision fix

### Recent Improvements (February 2026)
- ✅ Recurring train alerts: subscribe to specific train numbers for daily commute monitoring
- ✅ Frequency-based stats for subway/PATH/PATCO recent departures (replaces on-time metric)
- ✅ System-appropriate health metric: auto-selects frequency vs on-time by transit system
- ✅ Frequency baseline coloring for route alert performance views
- ✅ PATH departure time fix: tz normalization eliminating lag vs station signs
- ✅ Scheduler stagger and jitter to prevent thundering herd on startup
- ✅ NJT fuzzy matching for scheduled-to-observed train merging
- ✅ NJT line code collision fixes preventing duplicate SCHEDULED trains
- ✅ Subway JIT refresh fix: correct train matching on non-branching lines
- ✅ Subway origin inference topology bug fix and increased train ID hash length
- ✅ Departure cache miss fix (params_hash including data_sources)
- ✅ Deadlock cascade prevention via scheduler coordination improvements
- ✅ Station code mismatch fix for subway/MNR departure times
- ✅ LIRR date-suffix trip_id handling for GTFS static backfill
- ✅ Greenlet lazy-load fix preventing greenlet_spawn errors in async context

### Previous Improvements (January 2026)
- ✅ Added NYC Subway (MTA) support: 472 stations, 36 routes, 8 GTFS-RT feeds
- ✅ Added route-based delay & cancellation alert system with APNS push notifications
- ✅ Added LIRR, Metro-North support with unified GTFS-RT collectors
- ✅ Added PATH train support with full GTFS integration
- ✅ Added PATCO Speedline support with schedule-based GTFS data (14 stations)
- ✅ Shared MTA logic in `mta_common.py` for stop merging, departure inference, completion detection
- ✅ Subway station complex aggregation via STATION_EQUIVALENTS
- ✅ Split station config into per-provider `stations/` package
- ✅ Added delay and cancellation forecasting with predictions
- ✅ Implemented GTFS future date schedule viewing for all transit systems
- ✅ Added `hide_departed` parameter for departures endpoint
- ✅ Ground truth validation expanded to include all providers

### Previous Improvements (Aug-Sep 2025)
- ✅ Added NJT schedule collection for future train visibility
- ✅ Implemented Amtrak pattern-based schedule generation
- ✅ Added horizontal scaling support with database coordination
- ✅ Implemented API response caching with pre-computation
- ✅ Added comprehensive validation service for coverage monitoring
- ✅ Enhanced arrival forecasting with direct calculation method
- ✅ Added support for SCHEDULED vs OBSERVED journey types
- ✅ Fixed stop_sequence nullable issue for schedule-only stops
- ✅ Added departure_source tracking for analytics
- ✅ Journey progress table with cumulative delay tracking
- ✅ Historical track predictor using pattern analysis
- ✅ Correlation ID middleware for request tracing

### Known Issues & Areas for Improvement
- ⚠️ Cache invalidation strategy could be more sophisticated
- ⚠️ Test coverage for schedule generation features needs expansion
- ⚠️ Validation service route pairs are hardcoded (should be configurable)
- ⚠️ Track prediction accuracy metrics need dashboard visualization
- ℹ️ Note: ML model files (`ml_features.py`, `ml_predictor.py`) were planned but not implemented
- ℹ️ Current track prediction uses historical pattern analysis instead

### Performance Characteristics
- API response time: <100ms (p95) with caching
- Discovery completion: ~30 seconds for 21 stations
- Schedule generation: <60 seconds for all NJT trains
- Cache hit rate: ~80% for popular routes
- Database queries: <10ms for indexed queries
- Memory usage: ~300-400MB typical

## Contact & Support

For questions about the V2 backend:
- Review this guide first
- Check the test suite for examples
- Consult the API documentation
- Review git history for context
- Check recent migration files for schema changes

Remember: The goal is radical simplicity. If something seems complex, there's probably a simpler way.