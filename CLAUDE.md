# TrackRat Project Guide for Claude

This file provides comprehensive guidance to Claude Code (claude.ai/code) when working with the TrackRat project across both backend and iOS platforms.

## Project Overview

TrackRat is a full-stack train tracking system that combines a simplified Python backend V2 with a native iOS app featuring Live Activity support for real-time track predictions for NJ Transit and Amtrak trains.

### System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Data Sources  │     │   Cloud Run     │     │   iOS Frontend  │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ • NJ Transit    │────▶│ • API Service   │────▶│ • iOS App       │
│ • Amtrak APIs   │     │ • Scheduler     │     │ • Live Activity │
│                 │     │ • ML Models     │     │ • Widgets       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                │
                        ┌───────▼────────┐
                        │    SQLite      │
                        │   Database     │
                        └────────────────┘
                                │
                        ┌───────▼────────┐
                        │ Cloud Monitoring│
                        │ • Dashboards    │
                        │ • Metrics       │
                        │ • Alerts       │
                        └────────────────┘
```

### Key Features

1. **Multi-Station Support**: Backend and iOS app support NY Penn, Newark Penn, Trenton, Princeton Junction, and Metropark
2. **Train Consolidation**: Backend merges duplicate trains; iOS app displays unified journey data
3. **Track Predictions**: Track assignments from NJ Transit API; iOS app displays "Owl" predictions when available
4. **Real-Time Updates**: Backend updates hourly + on-demand; iOS app refreshes every 30 seconds
5. **Journey Planning**: Backend provides smart filtering; iOS app enables origin-destination trip selection
6. **Live Activities**: Real-time train tracking on Lock Screen and Dynamic Island
7. **Push Notifications**: Background updates for Live Activities with status changes

## iOS Integration Conventions

### Station Codes
The iOS app uses these station codes:
- `NY` - New York Penn Station
- `NP` - Newark Penn Station  
- `TR` - Trenton Transit Center
- `PJ` - Princeton Junction
- `MP` - Metropark
- Additional Amtrak stations use standard codes (e.g., `WAS` for Washington Union)

### Time Handling
- **Backend**: Stores in Eastern Time, converts to/from UTC as needed
- **iOS**: Displays in Eastern Time, handles fractional seconds in ISO8601
- **API**: All timestamps in Eastern Time Zone

### Data Models

#### Train Model
- Backend: `Train` table with comprehensive fields
- iOS: `Train` struct matching API response
- Key shared fields: `train_id`, `line`, `destination`, `status`, `status_v2`, `track`, `stops`, `progress`

#### Predictions
- Backend: `PredictionData` with track probabilities
- iOS: `PredictionData` struct with Owl display logic
- Confidence thresholds: ≥80% (high), 50-79% (medium), <50% (low)

#### Status Values
The system recognizes: `ALL ABOARD`, `BOARDING`, `DEPARTED`, `CANCELLED`, `DELAYED`, etc.
- New `status_v2` field provides enhanced status resolution

## Development Workflow

### Local Development

For local development, run the components individually:

```bash
# Backend V2 development
cd backend_v2
poetry run uvicorn trackrat.main:app --reload

# iOS development
cd ios
open TrackRat.xcodeproj

# Infrastructure management
cd infra
terraform plan
terraform apply
```

### Automated Deployment

The system uses GitHub Actions for fully automated CI/CD:

1. **On Push to Main**:
   - Docker images built and pushed to Artifact Registry
   - Infrastructure deployed via Terraform
   - Cloud Run services updated with new images
   - Database migrations run automatically
   - Health checks verify deployment success

2. **Manual Operations** (if needed):
   - Populate secrets in Secret Manager
   - Train new ML models
   - Trigger data collection manually

### When Making Backend Changes

1. **API Changes**:
   - Update OpenAPI spec if modifying endpoints
   - Consider iOS app and web app compatibility
   - Maintain backward compatibility when possible
   - Changes deploy automatically on push to main

2. **Model Changes**:
   - Update database schema with migrations
   - Database migrations run automatically during deployment
   - Ensure API serialization matches frontend expectations
   - Test with both consolidated and non-consolidated responses

3. **New Features**:
   - Add corresponding CLI commands
   - Update scheduler configuration if needed
   - Consider iOS and web UI implications
   - Test in development environment first

### When Making iOS Changes

1. **API Integration**:
   - Use existing `APIService` patterns
   - Handle all date formats with custom decoder
   - Always specify `from_station_code` for origin context

2. **UI Updates**:
   - Maintain glassmorphism design system
   - Use orange tint color consistently
   - Follow dark mode preference

3. **Live Activities**:
   - Test background updates thoroughly
   - Handle all train statuses appropriately
   - Ensure auto-end logic works correctly

4. **Testing**:
   - Test on both simulator and physical devices
   - Verify Live Activity functionality
   - Check push notification behavior

## Testing

### Backend V2 Testing
```bash
# Run all tests (uses SQLite)
poetry run pytest

# Unit tests only
poetry run pytest tests/unit/

# Integration tests
poetry run pytest tests/integration/

# With coverage
poetry run pytest --cov=trackrat
```

### iOS Testing
```bash
# Simulator testing
xcodebuild test -scheme TrackRat -destination 'platform=iOS Simulator,name=iPhone 15'

# Live Activity testing
# Use LiveActivityDebugView in the app
```

### End-to-End Testing

1. **Data Flow Verification**:
   - Start backend V2: `poetry run uvicorn trackrat.main:app`
   - Monitor health: `curl http://localhost:8000/health`
   - Check metrics: `curl http://localhost:8000/metrics`
   - Test iOS app against API

2. **Consolidation Testing**:
   - Enable consolidation in API: `?consolidate=true`
   - Verify iOS app handles merged trains correctly
   - Check track confidence display
   - Test Live Activity updates with consolidated data

## API Integration Points

### API Endpoints Used by iOS App

1. **Train Departures** (V2):
   ```
   GET /api/v2/trains/departures?from=X&to=Y&limit=50
   ```

2. **Train Details** (V2):
   ```
   GET /api/v2/trains/{train_id}?date=YYYY-MM-DD&refresh=true
   ```

3. **Route History** (V2):
   ```
   GET /api/v2/routes/history?from_station=X&to_station=Y&data_source=NJT&days=30
   ```

4. **Route Congestion** (V2 - NEW):
   ```
   GET /api/v2/routes/congestion?time_window_hours=3&data_source=NJT
   ```

5. **Live Activities**:
   ```
   POST /api/v2/live-activities/register    # Register Live Activity
   DELETE /api/v2/live-activities/{token}   # Unregister Live Activity
   ```

5. **Health & Metrics**:
   ```
   GET /health                  # System health check
   GET /health/live             # Liveness probe
   GET /health/ready            # Readiness probe
   GET /scheduler/status        # Scheduler status
   GET /metrics                 # Prometheus metrics endpoint
   ```

### Data Synchronization

1. **Polling Intervals**:
   - Backend V2: Hourly discovery + just-in-time updates when requested
   - iOS: 30s (active view), 30s (Live Activity background)

2. **Cache Considerations**:
   - Backend: Database serves as cache
   - iOS: No persistent cache, real-time fetching

3. **State Management**:
   - Backend: Stateless API, database for persistence
   - iOS: @StateObject for app state, UserDefaults for preferences

## Deployment Considerations

### Backend V2 Deployment
- **Database**: SQLite with zero configuration (development) or Cloud SQL (production)
- **Scheduler**: APScheduler runs in-process, starts automatically
- **Docker**: Container with APNS validation at startup
- **Scaling**: Simplified architecture with reduced API calls (~95% reduction)
- **Health Checks**: Built-in endpoints at `/health` and `/metrics`

### iOS Deployment
- Update bundle version and build number
- Test on physical devices for Live Activities
- Verify push notification certificates
- Archive and upload to App Store Connect

### Operational Requirements

**Automated Operations:**
- ✅ Data collection every 1-2 minutes via Cloud Scheduler
- ✅ Auto-scaling based on traffic
- ✅ Database backups and maintenance
- ✅ Health monitoring and restart on failure

**Manual Operations:**
- Configure NJ Transit API credentials
- Set up APNS certificates for iOS push notifications
- Monitor system health and performance
- Rotate secrets quarterly

## Performance Optimization

### Backend V2
- Just-in-time updates reduce API calls by ~95%
- SQLite database with efficient queries
- Async processing throughout the stack
- Smart caching and staleness checks

### iOS
- Lazy loading with pagination
- Background refresh only when needed
- Efficient Live Activity updates
- Minimal network requests
- SwiftUI view composition for performance
- Haptic feedback optimization

## Security Best Practices

### Backend
- API credentials in environment variables
- No sensitive data in logs
- Proper error handling without exposing internals
- Rate limiting considerations

### iOS
- No user tracking or analytics
- Local storage only for preferences
- No third-party SDKs
- Secure API communication
- Privacy-first Live Activities
- Local-only trip history

## Troubleshooting Guide

### Common Backend V2 Issues
1. **No trains found**: Check NJ Transit API credentials in environment
2. **API timeouts**: Verify network connectivity to NJ Transit/Amtrak
3. **Database errors**: Run `alembic upgrade head` for migrations
4. **APNS failures**: Verify certificate in `certs/` directory

### Common iOS Issues
1. **Live Activities not appearing**: Verify Info.plist configuration
2. **API connection errors**: Check backend URL and network
3. **Push notifications failing**: Verify APNS setup
4. **Background updates failing**: Check background modes configuration
5. **Live Activity updates not appearing**: Verify push notification certificates

### Integration Issues
1. **Time mismatches**: Ensure Eastern Time Zone handling
2. **Missing trains**: Check JIT update logic and data staleness
3. **No track info**: Verify NJ Transit API is returning track data
4. **Live Activity data inconsistencies**: Check API response format

## Code Style Guidelines

### Python (Backend)
- Follow PEP 8 with Black formatting
- Type hints for all functions
- Comprehensive docstrings
- No magic numbers, use constants

### Swift (iOS)
- Follow Swift API Design Guidelines
- Use SwiftUI best practices
- Explicit access control
- Meaningful variable names
- Async/await for API calls
- Combine for reactive programming

## Feature Development Checklist

When adding new features:

- [ ] Design API contract first
- [ ] Implement backend functionality
- [ ] Add comprehensive tests
- [ ] Update API documentation
- [ ] Implement iOS UI/functionality
- [ ] Test end-to-end flow
- [ ] Update all CLAUDE.md files with new features
- [ ] Consider Live Activity implications
- [ ] Verify performance impact
- [ ] Check error handling
- [ ] Test on physical devices
- [ ] Verify push notification behavior
- [ ] Add monitoring dashboards if needed
- [ ] Update metrics collection
- [ ] Document in Recent Enhancements section

## Recent Enhancements

### Transit Time Tracking & Congestion Analysis (NEW)
Comprehensive analytics system for route performance monitoring:
- **Backend**: New `TransitAnalyzer` service calculates segment times, dwell times, and journey progress
- **Database**: Added `segment_transit_times`, `station_dwell_times`, and `journey_progress` tables
- **API**: New `/api/v2/routes/congestion` endpoint provides real-time network congestion data
- **Analysis**: Automatic delay breakdown categorization (on-time, slight, significant, major)
- **Visualization**: Color-coded congestion levels (Normal→Green, Moderate→Yellow, Heavy→Orange, Severe→Red)
- **Benefits**: Real-time network performance monitoring and historical route analysis

### Enhanced Status Resolution (StatusV2)
The system now supports intelligent status conflict resolution:
- **Backend**: New `status_v2` field with DEPARTED > BOARDING priority
- **iOS**: Enhanced display using `statusV2` with fallback to legacy
- **Benefits**: Solves the "stuck BOARDING" issue when trains depart

### Real-time Progress Tracking
New `progress` field provides detailed journey information:
- **Backend**: Calculates stops completed, minutes to arrival, journey percentage
- **iOS**: Enhanced Live Activities and progress bars using this data
- **Benefits**: Accurate progress visualization and time-to-arrival

### API Changes Summary
- **New Endpoints**: `/api/v2/routes/congestion` for real-time network congestion analysis
- **Enhanced Endpoints**: `/api/v2/routes/history` with delay breakdown and track usage stats  
- **New Fields**: `status_v2`, `progress` (both optional for backward compatibility)
- **Enhanced Data**: `last_departed`, `next_arrival`, `journey_percent`
- **New Models**: `SegmentCongestion`, `CongestionMapResponse`, `DelayBreakdown`, `AggregateStats`
- **No Breaking Changes**: All existing fields preserved

### Executive Dashboard
High-level monitoring dashboard for system health and performance:
- **Infrastructure**: Google Cloud Monitoring dashboards deployed via Terraform
- **Metrics**: System health score, daily trains processed, prediction accuracy, API uptime
- **Monitoring**: Four dashboards (Executive, Operations, Business KPIs, Troubleshooting)
- **Access**: Via GCP Console (no frontend implementation)
- **Benefits**: At-a-glance system health monitoring for stakeholders

### Model Prediction Accuracy Tracking
Real-time tracking of ML model performance:
- **Backend**: Automatic accuracy calculation when actual track is assigned
- **Metrics**: `model_prediction_accuracy` Prometheus metric by station
- **API**: Enhanced `/health` endpoint with quality metrics
- **Monitoring**: Accuracy trends displayed in executive dashboard
- **Benefits**: Continuous model performance monitoring and alerting

## Architecture Decisions

### Why These Choices?

1. **Station-Specific Models**: Better accuracy than combined model
2. **Train Consolidation**: Unified view across data sources
3. **30-Second Refresh**: Balance between real-time and battery life
4. **Eastern Time Zone**: Natural for Northeast Corridor users
5. **No User Accounts**: Privacy-first approach
6. **StatusV2 Design**: Resolves conflicts while maintaining compatibility
7. **Progress Tracking**: Provides real-time journey visualization
8. **Live Activities**: Native iOS integration for real-time updates
9. **SwiftUI Architecture**: Modern declarative UI framework

### Future Considerations

1. **Backend V2**:
   - ML track prediction models (planned)
   - GraphQL API for more efficient queries
   - WebSocket support for real-time updates
   - Additional transit systems (LIRR, Metro-North)
   - Redis caching layer

2. **iOS**:
   - Widget Extension
   - Apple Watch app
   - Offline mode with caching
   - iPad optimization
   - Siri Shortcuts integration
   - CarPlay support

## Development Tools

### Development Commands

```bash
# Run tests and linting
make test                            # Run all tests
make lint                            # Run linting checks  
make clean                           # Clean build artifacts

# Backend commands
make backend-test                    # Run backend tests
make backend-migrate                 # Run database migrations

# Infrastructure commands  
make infra-plan                      # Plan infrastructure changes
make infra-validate                  # Validate Terraform configuration

# Setup development environment
make setup                           # Install dependencies and initialize
```

## Quick Reference

### Backend V2 Commands
```bash
# Start development server (scheduler starts automatically)
poetry run uvicorn trackrat.main:app --reload

# Database management
poetry run alembic upgrade head           # Apply migrations
poetry run alembic revision -m "desc"     # Create new migration

# Run tests
poetry run pytest                         # Run all tests
poetry run pytest tests/unit/             # Unit tests only
```

### iOS Commands
```bash
# Build iOS app for simulator
xcodebuild -scheme TrackRat -sdk iphonesimulator build -destination 'platform=iOS Simulator,name=iPhone 16'

# Check for compilation errors only
xcodebuild -scheme TrackRat -sdk iphonesimulator build -destination 'platform=iOS Simulator,name=iPhone 16' 2>&1 | grep -E "(error|failed|BUILD FAILED)" || echo "BUILD SUCCESSFUL"

# Run iOS tests
xcodebuild test -scheme TrackRat -destination 'platform=iOS Simulator,name=iPhone 16'

# Open Xcode project
open ios/TrackRat.xcodeproj

# Show available destinations
xcodebuild -scheme TrackRat -showdestinations
```

### iOS Key Files
```
TrackRat/App/TrackRatApp.swift      # App entry point
TrackRat/Services/APIService.swift   # API integration
TrackRat/Services/LiveActivityService.swift  # Live Activities
TrackRat/Models/Train.swift          # Core data model
TrackRat/Views/                      # All UI components
```


### API Base URLs
- Development: `http://localhost:8000/api`
- Production: `https://prod.api.trackrat.net/api`

## Contact for Questions

When working on this project, refer to:
- **Backend V2 details**: `backend_v2/CLAUDE.md` - Simplified V2 backend development
- **iOS details**: `ios/CLAUDE.md` - iOS app development with Live Activities
- **Infrastructure**: `infra/CLAUDE.md` - Terraform and GCP infrastructure  
- **Integration guidance**: This file for backend-iOS integration

### Quick Reference

**For Developers**: Backend and iOS components have detailed CLAUDE.md files with development workflows.

**For Infrastructure**: Use `infra/CLAUDE.md` for Terraform operations and Cloud Run deployment details.

Remember: The goal is seamless integration between an efficient backend V2 (with ~95% fewer API calls) and an intuitive iOS frontend experience with Live Activities.