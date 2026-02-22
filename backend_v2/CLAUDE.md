# TrackRat Backend V2 - Development Guide for Claude

This guide provides comprehensive information for Claude Code when working with the TrackRat Backend V2, a radical simplification of the train tracking system that reduces API calls by ~95% while maintaining production robustness.

**Last Updated:** February 2026
**Database:** PostgreSQL with asyncpg (production-ready)
**Key Features:** Multi-transit support (NJT, Amtrak, PATH, PATCO, LIRR, Metro-North, NYC Subway), ML predictions, API caching, schedule generation, GTFS integration

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
- **Multi-Transit Support**: NJ Transit, Amtrak, PATH, PATCO, LIRR, Metro-North, and NYC Subway data sources with extensible architecture
- **ML-Powered Features**: Track predictions, arrival forecasting, and congestion analysis
- **API Response Caching**: Intelligent caching system for performance optimization

### System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Transit APIs    │────▶│  Backend V2     │────▶│  Client Apps    │
│ • NJ Transit    │     │ • Discovery     │     │ • iOS App       │
│ • Amtrak        │     │ • Schedule Gen  │     │ • Android App   │
│ • PATH          │     │ • JIT Updates   │     │ • Web App       │
│ • PATCO (GTFS)  │     │ • ML Predictions│     │ • Live Activities│
│ • LIRR (GTFS-RT)│     │ • GTFS Feed     │     └─────────────────┘
│ • MNR (GTFS-RT) │     │ • API Caching   │
│ • Subway(GTFS-RT)│     │ • Route Alerts  │
└─────────────────┘     │ • Analytics     │
                        │ • Validation    │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐
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
   - **NJT**: Polls 7 major stations (NY, NP, PJ, TR, LB, PL, DN) via `getTrainSchedule`
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
    data_source (NJT/AMTRAK/PATH/PATCO/LIRR/MNR/SUBWAY), observation_type (OBSERVED/SCHEDULED),
    scheduled_departure, scheduled_arrival, actual_departure, actual_arrival,
    has_complete_journey, stops_count, is_cancelled, is_completed,
    api_error_count, is_expired, discovery_track, discovery_station_code

-- Individual stops with times and tracks
journey_stops (
    journey_id, station_code, stop_sequence,
    scheduled_departure, scheduled_arrival,
    actual_departure, actual_arrival,
    track, status
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
    journey_id, snapshot_type, api_response, created_at
)

-- API response caching
cached_api_responses (
    id, endpoint, params_hash, params, response, created_at, expires_at
)

-- Scheduler coordination (for horizontal scaling)
scheduler_task_runs (
    task_name, last_successful_run, run_count, last_run_revision
)

-- Live Activity tokens
live_activity_tokens (
    id, push_token, activity_id, train_number,
    origin_code, destination_code, expires_at
)

-- Validation results
validation_results (
    id, validation_run_id, route, data_source,
    expected_trains, found_trains, missing_trains,
    coverage_percent, validation_time
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

# Route Alerts
POST /devices/register                               # Register APNS device token
PUT  /alerts/subscriptions                           # Sync route alert subscriptions
GET  /alerts/subscriptions                           # Get current alert subscriptions

# Validation
GET /validation/status                               # Validation status and recent results
GET /validation/results/{route}/{source}             # Route-specific validation details

# Feedback
POST /feedback                                       # Submit user feedback

# Live Activities Management
POST /live-activities/register    # Register Live Activity
DELETE /live-activities/{token}   # Unregister Live Activity

# System Health and Metrics
GET /health                    # Comprehensive health check
GET /health/live              # Liveness probe
GET /health/ready             # Readiness probe
GET /scheduler/status         # Detailed scheduler status
GET /metrics                  # Prometheus metrics
```

### 4. Background Scheduler (Horizontally Scalable)

The APScheduler runs in-process and handles:
- **Daily at 4 AM ET**: NJT schedule collection (27-hour schedules)
- **Daily at 4:30 AM ET**: Amtrak pattern-based schedule generation
- **Every 30 min**: NJT and Amtrak train discovery from major stations
- **Every 5 min**: Journey update checks for active trains
- **Every 15 min**: Individual journey collection updates
- **Every 15 min**: API cache pre-computation for congestion endpoints
- **Hourly at :05**: Train validation across key routes
- **Every 30 min**: Live Activity push notification updates
- **Every 5 min**: Route alert evaluation and push notifications
- **Automatic startup**: Begins when FastAPI app starts

**Horizontal Scaling Support:**
- **Database-based coordination**: Multiple replicas coordinate through `scheduler_task_runs` table
- **Freshness checking**: Tasks check last run time before executing to prevent duplicates
- **Safe intervals**: Tasks use 90% of scheduled interval with 2-minute buffer to prevent over-execution
- **Row-level locking**: PostgreSQL `WITH FOR UPDATE SKIP LOCKED` prevents race conditions
- **Instance tracking**: GCE instance hostname tracked for debugging

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
- `/api/v2/predictions/track` - ML-powered track predictions
- `/api/v2/predictions/supported-stations` - ML-enabled stations list
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
   - Create migration: `alembic revision -m "description"`
   - Edit migration file in `db/migrations/versions/`
   - **NOTE**: Migrations run automatically during application startup (after backup restore)

3. **Collector Changes**:
   - NJT collectors in `collectors/njt/` (discovery.py, journey.py, client.py, schedule.py)
   - Amtrak collectors in `collectors/amtrak/` (discovery.py, journey.py, client.py)
   - PATH collector in `collectors/path/` (collector.py, client.py, ridepath_client.py, segment_times.py)
   - LIRR collector in `collectors/lirr/` (collector.py, client.py)
   - Metro-North collector in `collectors/mnr/` (collector.py, client.py)
   - NYC Subway collector in `collectors/subway/` (collector.py, client.py)
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
make lint
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

# Validation Settings (optional)
TRACKRAT_INTERNAL_API_URL=http://localhost:8000  # Internal API for validation
TRACKRAT_VALIDATION_MAX_TRAINS_TO_VERIFY=20      # Max missing trains to verify

# Feature Flags (optional)
TRACKRAT_USE_OPTIMIZED_AMTRAK_PATTERN_ANALYSIS=true  # Database-aggregated patterns
TRACKRAT_ENABLE_SQL_LOGGING=false                    # SQLAlchemy query logging

# GCE Instance Configuration (for horizontal scaling)
# Instance hostname is automatically set by GCE MIG
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
LOG_LEVEL=DEBUG poetry run uvicorn trackrat.main:app

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
- [ ] Verify K_REVISION is set (automatic in Cloud Run)

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
   - Ensure K_REVISION env var is set in Cloud Run

### Debug Commands

```bash
# Check database connectivity
poetry run python -c "from trackrat.db.engine import test_connection; import asyncio; asyncio.run(test_connection())"

# Verify NJ Transit API
poetry run python -c "from trackrat.utils.nj_transit import test_api; import asyncio; asyncio.run(test_api())"

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
3. **Additional Transit Systems**: SEPTA regional rail, NJ Light Rail
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

#### Analytics & ML
- **TransitAnalyzer** (`services/transit_analyzer.py`): Transit time and dwell time analysis
- **CongestionAnalyzer** (`services/congestion.py`): Real-time network congestion monitoring
- **DirectArrivalForecaster** (`services/direct_forecaster.py`): Direct arrival predictions from recent data
- **HistoricalTrackPredictor** (`services/historical_track_predictor.py`): Historical pattern-based track predictions
- **TrackOccupancyService** (`services/track_occupancy.py`): Real-time track availability
- **DelayForecaster** (`services/delay_forecaster.py`): ML-powered delay and cancellation forecasting using hierarchical historical data

#### Route Alerts
- **AlertEvaluatorService** (`services/alert_evaluator.py`): Evaluates delay/cancellation conditions for route alert push notifications
- **AlertsAPI** (`api/alerts.py`): Device registration and alert subscription management endpoints

#### Infrastructure
- **SimpleAPNSService** (`services/apns.py`): Apple Push Notifications for Live Activities and Route Alerts
- **BackupService** (`services/backup_service.py`): GCS backup management (optional)

## Recent Improvements & Known Issues

### Recent Improvements (January-February 2026)
- ✅ Added NYC Subway (MTA) support: 472 stations, 36 routes, 8 GTFS-RT feeds
- ✅ Added route-based delay & cancellation alert system with APNS push notifications
- ✅ Added Amtrak NEC train system for Northeast Corridor filtering
- ✅ PATH departure time precision improvements with GTFS segment times
- ✅ Split station config into per-provider `stations/` package (njt, amtrak, path, patco, lirr, mnr, subway)
- ✅ Subway station complex aggregation via STATION_EQUIVALENTS
- ✅ Renamed ML-prefixed identifiers to prediction-agnostic names
- ✅ Ground truth validation expanded to include SUBWAY provider
- ✅ Amtrak delay propagation: parse depCmnt/arrCmnt into updated times
- ✅ Added LIRR support with unified GTFS-RT collector
- ✅ Added Metro-North support with unified GTFS-RT collector
- ✅ Shared MTA logic in `mta_common.py` for stop merging, departure inference, completion detection
- ✅ Added PATH train support with full GTFS integration
- ✅ Added PATCO Speedline support with schedule-based GTFS data (14 stations)
- ✅ Implemented GTFS future date schedule viewing for all transit systems
- ✅ Added headsign fallback lookup for PATH/PATCO train details
- ✅ Fixed train lookup for systems without numeric train IDs
- ✅ Simplified route summary body text format with natural language
- ✅ Added delay and cancellation forecasting with predictions
- ✅ Expanded track predictions to support multiple stations beyond NY Penn
- ✅ Added hot train updates for reduced event latency
- ✅ Implemented `hide_departed` parameter for departures endpoint
- ✅ Improved NJT API resilience for null/empty ITEMS in low-traffic stations
- ✅ Track prediction now returns 404 instead of uniform distribution when insufficient data
- ✅ Optimized departure service with data freshness indicators
- ✅ Fixed delay forecaster floor calculations for accuracy

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
- Discovery completion: ~30 seconds for 7 stations
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