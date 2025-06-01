# TrackRat Project Guide for Claude

This file provides comprehensive guidance to Claude Code (claude.ai/code) when working with the TrackRat project across both backend and iOS platforms.

## Project Overview

TrackRat is a full-stack train tracking system that combines a sophisticated Python backend (TrackCast) with a native iOS app to provide real-time track predictions and Live Activity tracking for NJ Transit and Amtrak trains.

### System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Data Sources  │     │     Backend     │     │    Frontend     │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ • NJ Transit    │────▶│ • TrackCast API │────▶│ • iOS App       │
│ • Amtrak        │     │ • ML Models     │     │ • Live Activity │
│                 │     │ • PostgreSQL    │     │ • Push Notifs   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Key Features Across Platforms

1. **Multi-Station Support**: Both backend and iOS support NY Penn, Newark Penn, Trenton, Princeton Junction, and Metropark
2. **Train Consolidation**: Backend merges duplicate trains; iOS displays unified journey data
3. **Track Predictions**: Backend ML models (Owl system) predict tracks; iOS displays predictions with confidence levels
4. **Real-Time Updates**: Backend polls APIs every 60-120 seconds; iOS refreshes every 30 seconds
5. **Journey Planning**: Backend provides smart filtering; iOS enables origin-destination trip selection

## Cross-Platform Conventions

### Station Codes
Both platforms use consistent station codes:
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

### Data Models Alignment

#### Train Model
- Backend: `Train` table with comprehensive fields
- iOS: `Train` struct matching API response
- Key shared fields: `train_id`, `line`, `destination`, `status`, `track`, `stops`

#### Predictions
- Backend: `PredictionData` with track probabilities
- iOS: `PredictionData` struct with Owl display logic
- Confidence thresholds: ≥80% (high), 50-79% (medium), <50% (low)

#### Status Values
Both platforms recognize: `ALL ABOARD`, `BOARDING`, `DEPARTED`, `CANCELLED`, `DELAYED`, etc.

## Development Workflow

### When Making Backend Changes

1. **API Changes**:
   - Update OpenAPI spec if modifying endpoints
   - Consider iOS app compatibility
   - Maintain backward compatibility when possible
   - Document new query parameters in backend/CLAUDE.md

2. **Model Changes**:
   - Update database schema with migrations
   - Ensure API serialization matches iOS expectations
   - Test with both consolidated and non-consolidated responses

3. **New Features**:
   - Add corresponding CLI commands
   - Update scheduler if periodic execution needed
   - Consider iOS UI implications

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

## Testing Across Platforms

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
   - Verify iOS handles merged trains correctly
   - Check track confidence display

## Common Integration Points

### API Endpoints Used by iOS

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

4. **Consolidated Trains** (if available):
   ```
   GET /api/consolidated_trains/{train_id}
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

### Backend Deployment
- Use environment-specific configs (dev.yaml, prod.yaml)
- Set environment variables for API credentials
- Run with Gunicorn in production
- Ensure PostgreSQL is properly configured

### iOS Deployment
- Update bundle version and build number
- Test on physical devices for Live Activities
- Verify push notification certificates
- Archive and upload to App Store Connect

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

## Troubleshooting Guide

### Common Backend Issues
1. **Missing predictions**: Check model files exist in `models/` directory
2. **API timeouts**: Verify network connectivity to NJ Transit/Amtrak
3. **Database errors**: Check PostgreSQL connection and migrations

### Common iOS Issues
1. **Live Activities not appearing**: Verify Info.plist configuration
2. **API connection errors**: Check backend URL and network
3. **Push notifications failing**: Verify APNS setup

### Integration Issues
1. **Time mismatches**: Ensure Eastern Time Zone handling
2. **Missing trains**: Check consolidation logic
3. **Wrong predictions**: Verify correct station model is loaded

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

## Feature Development Checklist

When adding new features that span both platforms:

- [ ] Design API contract first
- [ ] Implement backend functionality
- [ ] Add comprehensive tests
- [ ] Update API documentation
- [ ] Implement iOS UI/functionality
- [ ] Test end-to-end flow
- [ ] Update both CLAUDE.md files
- [ ] Consider Live Activity implications
- [ ] Verify performance impact
- [ ] Check error handling

## Architecture Decisions

### Why These Choices?

1. **Station-Specific Models**: Better accuracy than combined model
2. **Train Consolidation**: Unified view across data sources
3. **30-Second Refresh**: Balance between real-time and battery life
4. **Eastern Time Zone**: Natural for Northeast Corridor users
5. **No User Accounts**: Privacy-first approach

### Future Considerations

1. **Backend**:
   - GraphQL API for more efficient queries
   - WebSocket support for real-time updates
   - Additional ML model types
   - More data sources

2. **iOS**:
   - Widget Extension
   - Apple Watch app
   - Offline mode with caching
   - iPad optimization

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
- Production: `https://trackcast.andymartin.cc/api`

## Contact for Questions

When working on this project, refer to:
- Backend details: `backend/CLAUDE.md`
- iOS details: `ios/CLAUDE.md`
- This file for cross-platform guidance

Remember: The goal is seamless integration between a powerful prediction backend and an intuitive iOS experience with Live Activities.