# TrackRat V2 Backend

A simplified, efficient train tracking system for NJ Transit, Amtrak, PATH, PATCO, LIRR, Metro-North, and NYC Subway built with FastAPI, PostgreSQL, and modern Python.

**Version:** 2.1.0 (February 2026)
**Database:** PostgreSQL with asyncpg (production-ready)
**Python:** 3.11+ with strict type checking

## ✨ Features

- **🔄 Minimal API Polling**: 30-min discovery + on-demand updates (~95% fewer API calls)
- **📅 Schedule Generation**: Daily NJT schedules + Amtrak pattern-based predictions + GTFS static data
- **📆 Future Date Schedules**: View train schedules for future dates via GTFS data integration
- **⚡ Just-in-Time Updates**: Fresh data when users request it (<1 minute staleness)
- **🎯 Single Journey Records**: One record per train, no duplicates
- **🛡️ Type-Safe**: Strict mypy checking enforced from day one
- **🚀 Async Throughout**: Built on asyncpg for maximum PostgreSQL performance
- **📊 Built-in Monitoring**: Health checks, metrics, validation, and structured logging
- **🤖 ML Predictions**: Track assignment predictions with confidence scoring
- **📱 Live Activities**: Push notification support for iOS Live Activity updates
- **🚂 Multi-Transit**: NJ Transit, Amtrak, PATH, PATCO, LIRR, Metro-North, and NYC Subway with extensible architecture
- **🔔 Route Alerts**: Push notifications for delays and cancellations on subscribed routes
- **🔍 Coverage Validation**: Hourly validation ensures complete train coverage
- **💾 API Caching**: Intelligent response caching with pre-computation
- **🔄 Horizontal Scaling**: Database-coordinated task execution across replicas

## 📈 V2 Improvements

Compared to the original backend:
- **~95% reduction** in NJ Transit API calls
- **Simplified architecture** - easier to understand and maintain
- **Better performance** - async everywhere, optimized queries
- **Production-ready** - PostgreSQL with connection pooling and horizontal scaling
- **Enhanced monitoring** - comprehensive health checks and metrics

## Quick Start

### Prerequisites

- Python 3.11+
- Poetry for dependency management
- **APNS Certificate**: Valid Apple Push Notification Service P8 certificate for Live Activities

### Installation

```bash
# Clone and navigate to backend_v2
cd backend_v2

# Install dependencies
poetry install

# Set up PostgreSQL database (required)
# Create database and user:
psql -U postgres
CREATE DATABASE trackratdb;
CREATE USER trackratuser WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE trackratdb TO trackratuser;
\q

# Copy environment template
cp .env.example .env
# Edit .env with your configuration:
# - TRACKRAT_NJT_API_TOKEN: Your NJ Transit API token
# - TRACKRAT_DATABASE_URL: postgresql+asyncpg://trackratuser:password@localhost:5432/trackratdb
# Note: Amtrak uses public API (api-v3.amtraker.com) - no token required

# Run database migrations
poetry run alembic upgrade head

# Start the application (scheduler starts automatically)
poetry run uvicorn trackrat.main:app --reload
```

### Scheduler Activation

**No additional steps needed!** The background scheduler starts automatically when you run the application:

- **Daily 4:00 AM ET**: NJT 27-hour schedule collection
- **Daily 4:30 AM ET**: Amtrak pattern-based schedule generation
- **Every 30 minutes**: Train discovery for NJT and Amtrak
- **Every 15 minutes**: Journey collection for active NJT/Amtrak trains
- **Every 4 minutes**: PATH train collection (unified discovery + updates)
- **Every 4 minutes**: LIRR train collection (unified GTFS-RT collector)
- **Every 4 minutes**: Metro-North train collection (unified GTFS-RT collector)
- **Every 4 minutes**: NYC Subway collection (8 GTFS-RT feeds, 36 routes)
- **Every 5 minutes**: Update checks for active journeys
- **Every 5 minutes**: Route alert evaluation and push notifications
- **Hourly at :05**: Validation across key routes
- Monitor scheduler status at `/scheduler/status` endpoint

**Note**: PATH, LIRR, Metro-North, and NYC Subway each use unified collectors that handle both discovery and journey updates in a single pass. LIRR, Metro-North, and Subway use MTA's GTFS-RT feeds with shared logic in `mta_common.py`. PATCO uses GTFS static schedules only (no real-time API).

## Configuration

All configuration is done via environment variables. See `.env.example` for available options.

### Required Settings
- `TRACKRAT_NJT_API_TOKEN`: Your NJ Transit API token
- `TRACKRAT_DATABASE_URL`: PostgreSQL connection string
- Note: Amtrak uses the public Amtraker API (no authentication required)
- **APNS Configuration** (required for Live Activities):
  - `APNS_TEAM_ID`: Apple Developer Team ID (10 characters)
  - `APNS_KEY_ID`: APNS Auth Key ID (10 characters)
  - `APNS_BUNDLE_ID`: iOS app bundle identifier (e.g., `net.trackrat.TrackRat`)
  - `APNS_ENVIRONMENT`: `dev` for sandbox, `prod` for production
  - **APNS P8 Certificate**: Place your `.p8` auth key in `certs/apns_auth_key.p8`

### Optional Settings
- `TRACKRAT_DISCOVERY_INTERVAL_MINUTES`: How often to discover new trains (default: 30)
- `TRACKRAT_JOURNEY_UPDATE_INTERVAL_MINUTES`: How often to collect journey data (default: 15)
- `TRACKRAT_DATA_STALENESS_SECONDS`: When to refresh data on-demand (default: 60)
- `TRACKRAT_ENABLE_METRICS`: Enable Prometheus metrics endpoint (default: true)
- `TRACKRAT_LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `TRACKRAT_ENVIRONMENT`: Environment name (development, staging, production)
- `TRACKRAT_GCS_BACKUP_BUCKET`: GCS bucket for database backups (optional)
- `TRACKRAT_INTERNAL_API_URL`: Internal API URL for validation service (default: http://localhost:8000)
- `TRACKRAT_VALIDATION_MAX_TRAINS_TO_VERIFY`: Max missing trains to verify in detail (default: 20)
- `TRACKRAT_USE_OPTIMIZED_AMTRAK_PATTERN_ANALYSIS`: Use database-aggregated pattern analysis (default: true)
- `TRACKRAT_ENABLE_SQL_LOGGING`: Enable SQLAlchemy query logging (default: false)

### APNS Certificate Setup

1. **Generate APNS Auth Key**:
   - In Apple Developer Console, create an Apple Push Notification service key
   - Download the `.p8` file (named like `AuthKey_XXXXXXXXXX.p8`)

2. **Configure Certificate**:
   ```bash
   # Place the certificate in the expected location
   mkdir -p certs/
   cp /path/to/your/AuthKey_XXXXXXXXXX.p8 certs/apns_auth_key.p8
   
   # Or set custom path
   export APNS_AUTH_KEY_PATH=/custom/path/to/key.p8
   ```

3. **Verify Configuration**:
   ```bash
   # Use the included script to validate APNS setup
   ./run_backend.sh  # Will validate and exit if APNS is misconfigured
   ```

## API Endpoints

### Core Train Operations

#### Train Departures
```
GET /api/v2/trains/departures?from=NY&to=TR&limit=50&data_source=ALL&hide_departed=true
```
Get trains between stations with filtering:
- `from`/`to`: Station codes (works for any segment)
- `limit`: Max results (default: 50)
- `data_source`: NJT, AMTRAK, PATH, PATCO, LIRR, MNR, or ALL
- `hide_departed`: Skip trains that have already departed (default: false). When true, also skips expensive past-train refresh for better performance.
- Returns both SCHEDULED and OBSERVED trains

#### Train Details
```
GET /api/v2/trains/{train_id}?date=2025-09-15&refresh=true
```
Complete journey with all stops:
- `refresh=true`: Force fresh data from API
- Includes progress tracking and arrival predictions
- Returns enhanced status_v2 field

#### Train History
```
GET /api/v2/trains/{train_id}/history?date=2025-09-15
```
Historical train performance with delay breakdowns

### Route Analytics

#### Route History
```
GET /api/v2/routes/history?from_station=NY&to_station=TR&days=30
```
Historical performance with:
- Delay breakdowns by category
- Track usage statistics
- Journey time analysis

#### Network Congestion
```
GET /api/v2/routes/congestion?time_window_hours=3&data_source=NJT
```
Real-time congestion analysis:
- Color-coded severity levels
- Segment-by-segment delays
- Cached for performance

#### Operations Summary
```
GET /api/v2/routes/summary
```
Natural language summary of network operations status

#### Segment Trains
```
GET /api/v2/routes/segments/{from_station}/{to_station}/trains?hours=24
```
Detailed train records for a specific segment

### ML Predictions

#### Track Assignment Prediction
```
GET /api/v2/predictions/track?station_code=NY&train_id=1234&journey_date=2025-09-15
```
ML-powered track predictions with confidence scoring

#### Supported Stations
```
GET /api/v2/predictions/supported-stations
```
List of stations with ML-enabled track predictions

#### Track Occupancy
```
GET /api/v2/trains/stations/{station_code}/tracks/occupied
```
Real-time track availability analysis

### System Operations

#### Health Check
```
GET /health
```
Comprehensive health with:
- Database connectivity
- Scheduler status
- Data freshness metrics
- Model accuracy statistics

#### Scheduler Status
```
GET /scheduler/status
```
Detailed scheduler information:
- All job statuses
- Next run times
- Execution history

#### Metrics
```
GET /metrics
```
Prometheus-compatible metrics:
- API latencies
- Train counts
- Validation coverage
- Cache hit rates

#### Validation Status
```
GET /api/v2/validation/status
```
Current validation status and recent results

#### Validation Results
```
GET /api/v2/validation/results/{route}/{source}
```
Route-specific validation details (e.g., `/api/v2/validation/results/NY-TR/NJT`)

### Route Alerts

#### Register Device
```
POST /api/v2/devices/register
{"device_token": "...", "platform": "ios"}
```

#### Sync Alert Subscriptions
```
PUT /api/v2/alerts/subscriptions
{"device_token": "...", "subscriptions": [...]}
```
Sync route alert subscriptions for delay/cancellation push notifications

### Feedback
```
POST /api/v2/feedback
```
Submit user feedback for train data accuracy

### Live Activities

#### Register Live Activity
```
POST /api/v2/live-activities/register
{
  "push_token": "...",
  "activity_id": "...",
  "train_number": "1234",
  "origin_code": "NY",
  "destination_code": "TR"
}
```

#### Unregister Live Activity
```
DELETE /api/v2/live-activities/{token}
```

## Development

### 🧪 Running Tests

The V2 backend includes a comprehensive test suite covering core functionality:

```bash
# Run all tests (recommended)
poetry run pytest -v

# Run specific test categories
poetry run pytest tests/test_basic.py -v           # Core functionality only
poetry run pytest tests/test_config.py -v         # Configuration tests
poetry run pytest tests/test_utils.py -v          # Utility function tests

# Run with coverage report
poetry run pytest --cov=trackrat --cov-report=html
open htmlcov/index.html  # View coverage report

# Code quality checks
poetry run mypy src/                               # Type checking (strict)
poetry run ruff check src/                        # Fast linting
poetry run black src/ tests/ --check              # Code formatting check

# Auto-format code
poetry run black src/ tests/                      # Format all code
```

#### 📋 Test Status

Current test coverage:
- ✅ **Core functionality**: Configuration, time utilities, database models
- ✅ **Basic API functionality**: Health endpoints, app startup/shutdown
- ⚠️ **Integration tests**: Require live database setup (some may need fixes)
- 📝 **Note**: 4/4 critical tests pass, ensuring core system reliability

### Database Management
```bash
# Create a new migration
poetry run alembic revision --autogenerate -m "Description"

# Apply migrations
poetry run alembic upgrade head

# Rollback one migration
poetry run alembic downgrade -1
```

## Architecture

### Data Collection Pipeline

The system uses a sophisticated multi-phase approach:

#### 1. Schedule Generation (Daily)
- **NJT Schedule Collection** (4:00 AM ET)
  - Fetches 27-hour schedule data in single API call
  - Creates SCHEDULED journey records for all trains
  - Updates to OBSERVED when trains appear in discovery

- **Amtrak Pattern Analysis** (4:30 AM ET)
  - Analyzes 22 days of historical patterns
  - Identifies trains that run regularly (≥2 times in 3 weeks)
  - Generates SCHEDULED records for expected trains

#### 2. Train Discovery (Every 30 minutes for NJT/Amtrak)
- Polls major stations for active trains
- NJT: NY, NP, PJ, TR, LB, PL, DN stations
- Amtrak: Major corridor stations
- Updates journey status from SCHEDULED to OBSERVED

#### PATH Collection (Every 4 minutes - Unified)
- Uses native RidePATH API (`panynj.gov/bin/portauthority/ridepath.json`)
- Discovers trains at all 13 PATH stations (not just terminus)
- Unified collector handles both discovery and journey updates in single pass
- Infers train origin from route when seen mid-journey
- Calculates consistent train_id for deduplication across stations

#### LIRR / Metro-North Collection (Every 4 minutes - Unified GTFS-RT)
- Single unified collector per system using MTA's official GTFS-RT feeds
- Shared logic in `mta_common.py` for stop merging, departure inference, completion detection
- GTFS static schedules backfill stops that GTFS-RT omits (e.g., origin terminals)
- Handles discovery and journey updates in one pass

#### NYC Subway Collection (Every 4 minutes - Unified GTFS-RT)
- Single collector processes 8 GTFS-RT feeds covering 36 routes and 472 stations
- Uses MTA's official GTFS-RT feeds with shared logic from `mta_common.py`
- Station complexes aggregated via `STATION_EQUIVALENTS` mapping
- Full trip_id used as train ID (not truncated)

#### PATCO Collection (Schedule-based only)
- Uses GTFS static schedules from SEPTA feed
- 14 stations from Lindenwold to 15-16th & Locust
- No real-time API available; times are scheduled only

#### 3. Journey Collection (Every 15 minutes)
- Fetches complete journey details for active trains
- Updates all stops with actual times and tracks
- Calculates transit times and dwell times
- Updates progress tracking

#### 4. Just-in-Time Updates (On-demand)
- Triggered when users request data
- Only refreshes if data >60 seconds stale
- Ensures real-time accuracy

#### 5. Validation & Monitoring (Hourly)
- Validates coverage across key routes
- Detects missing trains
- Updates coverage metrics

### Horizontal Scaling

The scheduler supports multiple replicas:
- **Database coordination** via `scheduler_task_runs` table
- **Row-level locking** prevents duplicate execution
- **Freshness checks** ensure tasks run at correct intervals
- **Instance tracking** via GCE instance hostname

### Key Services

#### Data Collection
- **SchedulerService**: Orchestrates all background tasks
- **NJTScheduleCollector**: Daily NJT schedule fetching
- **AmtrakPatternScheduler**: Pattern-based Amtrak schedules
- **PathCollector**: Unified PATH discovery + journey collection using RidePATH API
- **RidePathClient**: Native PATH API client with 30-second caching
- **LIRRCollector**: Unified LIRR collector using MTA GTFS-RT feeds
- **MNRCollector**: Unified Metro-North collector using MTA GTFS-RT feeds
- **SubwayCollector**: Unified NYC Subway collector processing 8 GTFS-RT feeds
- **MTA Common**: Shared MTA logic for stop merging, departure inference, completion detection
- **JustInTimeUpdateService**: On-demand data refresh (supports NJT, Amtrak, PATH)

**Note**: PATCO uses GTFS static schedules only (no dedicated collector).

#### API & Analytics
- **DepartureService**: Train departure queries
- **TransitAnalyzer**: Journey time analysis
- **CongestionAnalyzer**: Network congestion monitoring
- **DirectArrivalForecaster**: Real-time arrival predictions
- **ApiCacheService**: Response caching with pre-computation
- **SummaryService**: Natural language operations summaries

#### ML & Predictions
- **HistoricalTrackPredictor**: Track assignment predictions using historical patterns
- **TrackOccupancyService**: Track availability analysis

#### Route Alerts
- **AlertEvaluatorService**: Evaluates delay/cancellation conditions for push notifications

#### Infrastructure
- **SimpleAPNSService**: iOS Live Activity notifications and route alert pushes
- **BackupService**: GCS database backups
- **TrainValidationService**: Coverage monitoring

## Monitoring & Observability

### Metrics
- **Prometheus endpoint** at `/metrics`
- Train discovery counts
- API call latencies
- Cache hit rates
- Validation coverage percentages
- Model prediction accuracy

### Health Monitoring
- **Comprehensive health** at `/health`
- **Liveness probe** at `/health/live`
- **Readiness probe** at `/health/ready`
- Database connectivity checks
- Scheduler job status
- Data freshness indicators

### Logging
- Structured JSON logging with `structlog`
- Correlation IDs for request tracing
- Configurable log levels
- Detailed error context

## 🎯 Performance & Optimization

### API Performance
- **~95% reduction** in external API calls vs V1
- **<100ms** response time (p95) with caching
- **~80% cache hit rate** for popular routes
- **<10ms** database query time for indexed queries

### Data Efficiency
- **Single database record** per train journey
- **Intelligent caching** with 15-minute pre-computation
- **Direct arrival forecasting** without intermediate storage
- **Pattern-based schedules** reduce API dependency

### System Resources
- **Memory usage**: ~300-400MB typical
- **CPU usage**: Low, spikes during discovery/collection
- **Database connections**: Pooled with asyncpg
- **Concurrent operations**: Full async/await architecture

### Scaling Characteristics
- **Horizontal scaling** via database coordination
- **Stateless API** servers
- **Connection pooling** for database efficiency
- **Background task distribution** across replicas

## 🚀 Production Deployment

### Docker

**⚠️ APNS Validation**: The container will **automatically exit** if APNS is not properly configured. This ensures Live Activities work correctly in production.

```bash
# Build the image
docker build -t trackrat-v2 .

# Run with environment variables and APNS certificate
docker run -p 8000:8000 \
  -e APNS_TEAM_ID="your_team_id" \
  -e APNS_KEY_ID="your_key_id" \
  -e APNS_BUNDLE_ID="net.trackrat.TrackRat" \
  -e APNS_ENVIRONMENT="prod" \
  -e TRACKRAT_NJT_API_TOKEN="your_token" \
  -v $(pwd)/certs:/app/certs:ro \
  -v $(pwd)/data:/app/data \
  trackrat-v2
```

### Docker Compose

```bash
# Copy the example configuration
cp docker-compose.example.yml docker-compose.yml

# Create environment file with your credentials
cat > .env << EOF
TRACKRAT_NJT_API_TOKEN=your_nj_transit_token
APNS_TEAM_ID=your_team_id
APNS_KEY_ID=your_key_id
EOF

# Place APNS certificate
mkdir -p certs
cp /path/to/AuthKey_XXXXXXXXXX.p8 certs/apns_auth_key.p8

# Start the service
docker-compose up -d
```

### Container Validation

The container performs comprehensive APNS validation at startup:

- ✅ **Certificate file exists and is valid**
- ✅ **Environment variables are set and properly formatted**
- ✅ **P8 certificate can be loaded by cryptography library**
- ❌ **Container exits immediately if any validation fails**

Test the validation:
```bash
# Test container validation (should fail without APNS)
./test-docker-apns.sh
```
```

### Production Considerations

#### Database
- **PostgreSQL required** (not SQLite)
- Configure connection pooling (built-in with asyncpg)
- Set appropriate pool size based on load
- Regular backups (GCS integration available)
- Monitor slow queries and optimize indexes

#### API & Security
- Configure CORS for your frontend domains
- Use reverse proxy (nginx/caddy) for SSL
- Implement rate limiting at proxy level
- Monitor external API rate limits
- Rotate API tokens regularly

#### Monitoring
- Set up Prometheus/Grafana for metrics
- Configure log aggregation (ELK, CloudWatch, etc.)
- Set alerts for:
  - High API error rates
  - Low validation coverage
  - Stale data indicators
  - Memory/CPU thresholds

#### Scaling
- GCE Managed Instance Groups with auto-healing
- Configure appropriate replica counts
- Monitor database connection limits
- Consider Redis for future caching layer

## 🛣️ Roadmap

### Future Enhancements

1. **🌐 Additional Transit Systems**: SEPTA regional rail, NJ Light Rail
2. **🤖 Enhanced ML**: Improved track prediction models with occupancy detection
3. **📊 Advanced Monitoring**: Grafana dashboards for Prometheus metrics
4. **⚡ Performance**: Redis caching layer for frequent queries
5. **🌟 Advanced API**: WebSocket support for real-time updates

### 🤝 Contributing

The V2 backend is designed for easy contribution:
- **Clear architecture** - well-documented modules
- **Type safety** - reduces bugs and improves code quality
- **Comprehensive tests** - ensures changes don't break functionality
- **Modern tooling** - Poetry, Ruff, Black for smooth development

## 🐛 Known Issues & Improvements Needed

### Critical Issues
1. **Schedule Duplication**: SCHEDULED records may duplicate if trains appear early
2. **Pattern Detection**: Amtrak pattern analysis may miss irregular services
3. **Test Coverage**: Limited tests for new schedule generation features

### Performance Improvements
1. **Cache Invalidation**: Current strategy is time-based only, needs smarter invalidation
2. **Database Indexes**: Some queries could benefit from additional indexes
3. **Memory Usage**: Pattern analysis loads full 22-day dataset into memory

### Feature Gaps
1. **Configuration**: Validation routes are hardcoded, should be configurable
2. **ML Models**: Accuracy tracking needs more comprehensive metrics
3. **Error Recovery**: Some edge cases in API failures need better handling

### Technical Debt
1. **Code Duplication**: Some similar logic between NJT and Amtrak collectors
2. **Type Annotations**: Some older code missing proper type hints
3. **Test Data**: Mock data needs updating for new features

### Future Enhancements
1. **WebSocket Support**: Real-time updates for connected clients
2. **GraphQL API**: More flexible querying for complex data needs
3. **Additional Transit**: SEPTA regional rail support
4. **Advanced ML**: Passenger flow analysis and enhanced predictions

## System Requirements

### Minimum Requirements
- Python 3.11+
- PostgreSQL 14+
- 512MB RAM
- 1GB disk space

### Recommended Production
- Python 3.11+
- PostgreSQL 15+
- 2GB RAM
- 10GB disk space
- Redis (future caching)

## License

Copyright 2025-2026 TrackRat Team