# TrackRat Backend V2 - Development Guide for Claude

This guide provides comprehensive information for Claude Code when working with the TrackRat Backend V2, a radical simplification of the train tracking system that reduces API calls by ~95% while maintaining production robustness.

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
- **Multi-Transit Support**: NJ Transit and Amtrak data sources with extensible architecture
- **ML-Powered Features**: Track predictions, arrival forecasting, and congestion analysis
- **API Response Caching**: Intelligent caching system for performance optimization

### System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Transit APIs    │────▶│  Backend V2     │────▶│  Client Apps    │
│ • NJ Transit    │     │ • Discovery     │     │ • iOS App       │
│ • Amtrak        │     │ • Collection    │     │ • Web App       │
│ • (SEPTA)*      │     │ • JIT Updates   │     │ • Live Activities│
│ • (PATH)*       │     │ • ML Predictions│     └─────────────────┘
│ • (LIRR)*       │     │ • API Service   │
└─────────────────┘     │ • Caching       │
                        │ • Analytics     │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │   PostgreSQL    │
                        │ • Train Data    │
                        │ • ML Models     │
                        │ • Analytics     │
                        │ • Cache         │
                        └─────────────────┘
```

*Note: SEPTA, PATH, and LIRR collectors have placeholder directories but are not yet implemented.

## Key Components

### 1. Data Collection Pipeline

**Three-Phase Approach:**

1. **Discovery Phase** (Hourly)
   - Polls 7 major stations: NY, NP, PJ, TR, LB, PL, DN
   - Finds all active trains using `getDepartureVisionData`
   - Creates or updates train_journey records

2. **Collection Phase** (Every 15 minutes)
   - Collects full journey details via `getTrainStopList`
   - Updates all stops with actual times and tracks
   - Only collects trains discovered in last 90 minutes

3. **JIT Update Phase** (On-demand)
   - Refreshes data when requested by users
   - Only updates if data is >60 seconds stale
   - Ensures real-time accuracy without constant polling

### 2. Database Schema

```sql
-- Core journey record (one per train per day)
train_journeys (
    id, train_id, journey_date, line, direction,
    first_station_scheduled_departure, last_station_scheduled_arrival,
    created_at, updated_at, last_api_update, status
)

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
    initial_delay_minutes, total_delay_minutes
)

-- Historical snapshots for ML training
journey_snapshots (
    journey_id, snapshot_type, api_response,
    created_at
)

-- Audit trails
discovery_runs (
    id, station_code, trains_found,
    created_at, duration_seconds
)
```

### 3. API Endpoints

All endpoints are prefixed with `/api/v2/`:

```python
# Train Operations
GET /trains/departures?from=NY&to=TR&limit=50         # Find departures between stations
GET /trains/{train_id}?date=2024-01-01&refresh=true   # Get specific train journey

# Route Analytics
GET /routes/history?from_station=NY&to_station=TR&data_source=NJT&days=30  # Historical route performance
GET /routes/congestion?time_window_hours=3&data_source=NJT                 # Real-time congestion analysis

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

### 4. Background Scheduler

The APScheduler runs in-process and handles:
- **Every 30 min** (configurable): NJ Transit train discovery from major stations
- **Every 30 min** (configurable): Amtrak train discovery
- **Every 5 min**: Journey update checks for active trains
- **Every 15 min** (configurable): Individual journey collection updates
- **Every 15 min**: API cache pre-computation for congestion endpoints
- **Automatic startup**: Begins when FastAPI app starts

### 5. Transit Time Tracking System

**NEW: Advanced Analytics and Congestion Monitoring**

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
- `/api/v2/routes/congestion` - Real-time network congestion map
- `/api/v2/routes/history` - Historical route performance with highlighted trains
- `/api/v2/trains/{train_id}` - Enhanced train details with `progress` field and arrival forecasting
- `/api/v2/predictions/track-occupancy/{station}` - Real-time track occupancy analysis
- Enhanced `/health` endpoint with model prediction accuracy metrics

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
   - NJT collectors in `collectors/njt/` (discovery.py, journey.py, client.py)
   - Amtrak collectors in `collectors/amtrak/` (discovery.py, journey.py, client.py)
   - Base classes in `collectors/base.py`
   - Test with mock data in `tests/unit/collectors/`
   - Note: SEPTA, PATH, LIRR collectors have placeholder directories only

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
# Required
TRACKRAT_NJT_API_TOKEN=your_nj_transit_api_token
TRACKRAT_NJT_API_URL=https://raildata.njtransit.com/api
TRACKRAT_AMTRAK_API_TOKEN=your_amtrak_api_token
TRACKRAT_AMTRAK_API_URL=https://maps.amtrak.com/services

# Optional (defaults to PostgreSQL)
TRACKRAT_DATABASE_URL=postgresql+asyncpg://trackratuser:password@localhost:5432/trackratdb
TRACKRAT_LOG_LEVEL=INFO
TRACKRAT_ENVIRONMENT=development

# APNS Settings (for Live Activities)
APNS_TEAM_ID=your_team_id
APNS_KEY_ID=your_key_id
APNS_AUTH_KEY_PATH=certs/AuthKey_4WC3F645FR.p8
APNS_BUNDLE_ID=net.trackrat.TrackRat
APNS_ENVIRONMENT=dev

# Backup Settings (optional)
TRACKRAT_GCS_BACKUP_BUCKET=your-backup-bucket
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
- Custom exceptions in `utils/exceptions.py`
- Retry logic for API calls
- Graceful degradation
- Structured error logging

### 3. Performance Optimizations

- Database connection pooling
- Efficient queries with proper indexes
- Minimal API calls through smart caching
- Background processing for heavy operations

### 4. Monitoring & Observability

- Prometheus metrics at `/metrics`
- Structured JSON logging
- Health checks with detailed status
- Request correlation IDs

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
  -e APNS_TEAM_ID=xxx \
  -e APNS_KEY_ID=xxx \
  trackrat-backend-v2
```

**Important**: Database migrations run automatically during container startup, **after** any backup restore from GCS.

### Production Checklist

- [ ] Set production DATABASE_URL
- [ ] Configure secrets in environment
- [ ] Enable Prometheus scraping
- [ ] Set up log aggregation
- [ ] Configure health check monitoring
- [ ] Review database connection pool settings
- [ ] Enable CORS for frontend domains

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

### Debug Commands

```bash
# Check database connectivity
poetry run python -c "from trackrat.db.engine import test_connection; import asyncio; asyncio.run(test_connection())"

# Verify NJ Transit API
poetry run python -c "from trackrat.utils.nj_transit import test_api; import asyncio; asyncio.run(test_api())"

# View scheduler jobs
curl http://localhost:8000/health | jq .scheduler
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
3. **Additional Transit Systems**: LIRR, Metro-North, SEPTA, PATH (placeholder directories exist)
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

## Contact & Support

For questions about the V2 backend:
- Review this guide first
- Check the test suite for examples
- Consult the API documentation
- Review git history for context

Remember: The goal is radical simplicity. If something seems complex, there's probably a simpler way.