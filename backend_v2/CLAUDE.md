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
- **SQLite-only**: Zero configuration database with built-in concurrency handling

### System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  NJ Transit API │────▶│  Backend V2     │────▶│  Client Apps    │
│                 │     │                 │     │  (iOS/Web)      │
└─────────────────┘     ├─────────────────┤     └─────────────────┘
                        │ • Discovery      │
                        │ • Collection     │
                        │ • JIT Updates    │
                        │ • API Service    │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │   Database      │
                        │   (SQLite)      │
                        └─────────────────┘
```

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
# Find departures between stations
GET /trains/departures?from=NY&to=TR&time_after=2024-01-01T12:00:00

# Get specific train journey
GET /trains/{train_id}

# Get historical performance
GET /trains/{train_id}/history?days=30

# System health and metrics
GET /health
GET /metrics
```

### 4. Background Scheduler

The APScheduler runs in-process and handles:
- **Hourly**: Train discovery from major stations
- **Every 15 min**: Journey collection for active trains
- **Automatic startup**: Begins when FastAPI app starts

## Development Workflow

### Making Changes

1. **API Changes**:
   - Update models in `models/api.py`
   - Modify endpoints in `api/trains.py`
   - Run tests: `poetry run pytest tests/`

2. **Database Changes**:
   - Create migration: `alembic revision -m "description"`
   - Edit migration file in `db/migrations/versions/`
   - Apply: `alembic upgrade head`

3. **Collector Changes**:
   - Discovery logic in `collectors/discovery.py`
   - Journey details in `collectors/journey.py`
   - Test with mock data in `tests/`

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
# Unit tests (fast, uses SQLite)
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
NJ_TRANSIT_USERNAME=your_username
NJ_TRANSIT_PASSWORD=your_password

# Optional
DATABASE_URL=sqlite:///trackrat.db
LOG_LEVEL=INFO
ENVIRONMENT=development
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
- `aiosqlite` for SQLite database access
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

# Use a custom database file
DATABASE_URL=sqlite:///custom_path.db poetry run uvicorn trackrat.main:app

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
  -e NJ_TRANSIT_USERNAME=xxx \
  -e NJ_TRANSIT_PASSWORD=xxx \
  trackrat-backend-v2
```

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
2. **Hourly discovery**: Balances freshness with API efficiency  
3. **15-minute collection**: Captures journey progress without excess
4. **60-second staleness**: Real-time feel without constant polling
5. **In-process scheduler**: Simplifies deployment and monitoring
6. **Async throughout**: Maximum performance with Python
7. **Pydantic settings**: Type-safe configuration management

### Trade-offs Accepted

1. **No Redis**: Simplicity over caching performance
2. **No message queue**: Direct execution over distributed processing
3. **Single deployment**: Monolith over microservices
4. **SQLite-only**: Zero configuration over horizontal scaling
5. **Single writer**: Natural serialization over concurrent writes

## Future Enhancements

### Planned Features

1. **Track Prediction Models**: ML models for track assignment
2. **WebSocket Support**: Real-time updates for clients
3. **Multi-Transit Support**: Amtrak, LIRR, Metro-North
4. **Advanced Analytics**: Journey patterns and delays
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