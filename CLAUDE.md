# TrackRat Project Guide for Claude

This file provides comprehensive guidance to Claude Code (claude.ai/code) when working with the TrackRat project across both backend and iOS platforms.

## Project Overview

TrackRat is a full-stack train tracking system that combines a sophisticated Python backend (TrackCast) with a native iOS app featuring Live Activity support for real-time track predictions for NJ Transit and Amtrak trains.

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
                        │  Cloud SQL     │
                        │  (PostgreSQL)  │
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
3. **Track Predictions**: Backend ML models (Owl system) predict tracks; iOS app displays predictions with confidence levels
4. **Real-Time Updates**: Backend polls APIs every 60-120 seconds; iOS app refreshes every 30 seconds
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

### Local Development Deployment

For rapid iteration during development, use the local deployment tools:

```bash
# Quick deployment (most common - skip tests and Terraform)
make deploy-dev-quick

# Full deployment (infrastructure + application)
./deploy-dev.sh

# Check deployment status
make status-dev

# View logs
make logs-dev
```

The `deploy-dev.sh` script handles:
- Docker image building and pushing to Artifact Registry
- Terraform infrastructure updates (optional)
- Cloud Run service deployments
- Health checks and verification
- Rollback on failure

See [Deployment Tools](#deployment-tools) section for detailed options.

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

### Backend Testing
```bash
# Unit tests (fast, SQLite)
pytest tests/unit/

# Integration tests (requires PostgreSQL)
pytest tests/integration/

# Full test suite
pytest
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
   - Start backend services: `trackcast start-scheduler`
   - Verify data collection: `trackcast collect-data`
   - Check predictions: `trackcast generate-predictions`
   - Test iOS app against live API

2. **Consolidation Testing**:
   - Enable consolidation in API: `?consolidate=true`
   - Verify iOS app handles merged trains correctly
   - Check track confidence display
   - Test Live Activity updates with consolidated data

## API Integration Points

### API Endpoints Used by iOS App

1. **Train Search**:
   ```
   GET /api/trains/?from_station_code=X&to_station_code=Y&departure_time_after=Z
   ```

2. **Train Details**:
   ```
   GET /api/trains/{id}?from_station_code=X
   GET /api/trains/{train_number}?from_station_code=X
   ```

3. **Historical Data**:
   ```
   GET /api/trains/?train_id=X&no_pagination=true&from_station_code=Y
   ```

4. **Consolidated Trains** (via query parameter):
   ```
   GET /api/trains/?consolidate=true&train_id=X
   ```

5. **Health & Metrics**:
   ```
   GET /health                  # System health with quality metrics
   GET /metrics                 # Prometheus metrics endpoint
   ```

### Data Synchronization

1. **Polling Intervals**:
   - Backend: 60s (NJ Transit), 120s (Amtrak)
   - iOS: 30s (active view), 30s (Live Activity background)

2. **Cache Considerations**:
   - Backend: Database serves as cache
   - iOS: No persistent cache, real-time fetching

3. **State Management**:
   - Backend: Stateless API, database for persistence
   - iOS: @StateObject for app state, UserDefaults for preferences

## Deployment Considerations

### Backend Deployment (Cloud Run)
- **Automatic**: GitHub Actions handles build, deploy, and migrations
- **Configuration**: Via Terraform and Secret Manager
- **Scaling**: Auto-scales from 0 to configured max instances
- **Health Checks**: Built-in startup and liveness probes with extended timeout
- **Database**: Cloud SQL PostgreSQL with VPC connectivity
- **Startup**: Extended startup probe (10 minutes) for model loading
- **VPC Connector**: Name limited to 25 characters (e.g., `trackrat-dev-vpc`)

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
- Populate API credentials in Secret Manager
- Train and update ML models periodically
- Monitor system health and performance
- Rotate secrets quarterly

## Performance Optimization

### Backend
- Station-specific models reduce prediction time
- Database indexes on frequently queried fields
- Connection pooling for database efficiency
- Async processing where applicable

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

### Common Backend Issues
1. **Missing predictions**: Check model files exist in `models/` directory
2. **API timeouts**: Verify network connectivity to NJ Transit/Amtrak
3. **Database errors**: Check PostgreSQL connection and migrations

### Common iOS Issues
1. **Live Activities not appearing**: Verify Info.plist configuration
2. **API connection errors**: Check backend URL and network
3. **Push notifications failing**: Verify APNS setup
4. **Background updates failing**: Check background modes configuration
5. **Live Activity updates not appearing**: Verify push notification certificates

### Integration Issues
1. **Time mismatches**: Ensure Eastern Time Zone handling
2. **Missing trains**: Check consolidation logic
3. **Wrong predictions**: Verify correct station model is loaded
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
- **New Fields**: `status_v2`, `progress` (both optional for backward compatibility)
- **Enhanced Data**: `last_departed`, `next_arrival`, `journey_percent`
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

1. **Backend**:
   - GraphQL API for more efficient queries
   - WebSocket support for real-time updates
   - Additional ML model types
   - More data sources
   - Enhanced prediction algorithms

2. **iOS**:
   - Widget Extension
   - Apple Watch app
   - Offline mode with caching
   - iPad optimization
   - Siri Shortcuts integration
   - CarPlay support

## Deployment Tools

### Quick Deployment Commands

```bash
# Most common - quick app deployment
make deploy-dev-quick

# Full deployment options
make deploy-dev         # Full deployment (infrastructure + application)
make deploy-dev-infra   # Infrastructure only
make deploy-dev-docker  # Docker only
make status-dev         # Check environment status
make logs-dev           # View recent logs
```

### Deployment Script (`deploy-dev.sh`)

The main deployment script provides flexible options:

```bash
./deploy-dev.sh [OPTIONS]
  --skip-tests          Skip running tests
  --skip-terraform      Skip Terraform apply (only update Cloud Run)
  --skip-docker         Skip Docker build (only run Terraform)
  --terraform-only      Only apply Terraform changes
  --docker-only         Only build/deploy Docker images
  --auto-approve        Skip confirmation prompts
  --dry-run             Show what would be done without executing
```

### Configuration

Deployment settings in `.deploy/`:
- `dev.env` - Development environment variables
- `deploy.config` - Default deployment behavior

### Deployment Workflow

1. **Pre-flight checks**: GCP auth, git status, Docker buildx setup
2. **Testing** (optional): Backend tests, Terraform validation
3. **Docker operations**: Build for linux/amd64, tag, push to Artifact Registry
4. **Infrastructure**: Terraform plan and apply
5. **Cloud Run update**: Deploy new image to services
6. **Verification**: Health checks, API tests

**Note**: The script automatically builds Docker images for `linux/amd64` platform to ensure compatibility with Cloud Run, even when running on Apple Silicon (M1/M2) Macs.

## Quick Reference

### Backend Commands
```bash
trackcast init-db                    # Initialize database
trackcast collect-data               # Collect train data
trackcast generate-predictions       # Generate predictions
trackcast start-api                  # Start API server
trackcast start-scheduler            # Start all services
trackcast train-model --station NY   # Train station model
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
- **Operations**: `/OPERATORS_GUIDE.md` - Comprehensive operational procedures for deployed system
- **Backend details**: `backend/CLAUDE.md` - Development and deployment guidance
- **iOS details**: `ios/CLAUDE.md` - iOS app development
- **Infrastructure**: `infra/CLAUDE.md` - Terraform and GCP infrastructure
- **Integration guidance**: This file for backend-iOS integration

### Quick Reference

**For Operators**: Start with `/OPERATORS_GUIDE.md` for comprehensive operational procedures, monitoring, and troubleshooting.

**For Developers**: Backend and iOS components have detailed CLAUDE.md files with development workflows and deployment procedures.

**For Infrastructure**: Use `infra/CLAUDE.md` for Terraform operations and `backend/DEPLOYMENT.md` for Cloud Run deployment details.

Remember: The goal is seamless integration between a powerful prediction backend and an intuitive iOS frontend experience with Live Activities, all running on a fully automated Cloud Run infrastructure.