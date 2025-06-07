# TrackRat Project Guide for Claude

This file provides comprehensive guidance to Claude Code (claude.ai/code) when working with the TrackRat project across both backend and iOS platforms.

## Project Overview

TrackRat is a full-stack train tracking system that combines a sophisticated Python backend (TrackCast) with multiple frontend clients: a native iOS app with Live Activity support and a responsive web application for cross-platform access to real-time track predictions for NJ Transit and Amtrak trains.

### System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Data Sources  │     │     Backend     │     │   Frontend      │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ • NJ Transit    │────▶│ • TrackCast API │────▶│ • iOS App       │
│ • Amtrak        │     │ • ML Models     │     │ • Live Activity │
│                 │     │ • PostgreSQL    │     │ • Web App       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Key Features Across Platforms

1. **Multi-Station Support**: Backend, iOS, and web app support NY Penn, Newark Penn, Trenton, Princeton Junction, and Metropark
2. **Train Consolidation**: Backend merges duplicate trains; all frontends display unified journey data
3. **Track Predictions**: Backend ML models (Owl system) predict tracks; frontends display predictions with confidence levels
4. **Real-Time Updates**: Backend polls APIs every 60-120 seconds; frontends refresh every 30 seconds
5. **Journey Planning**: Backend provides smart filtering; frontends enable origin-destination trip selection

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
- **Web App**: Displays in Eastern Time with proper timezone handling
- **API**: All timestamps in Eastern Time Zone

### Data Models Alignment

#### Train Model
- Backend: `Train` table with comprehensive fields
- iOS: `Train` struct matching API response
- Web App: JavaScript objects matching API response
- Key shared fields: `train_id`, `line`, `destination`, `status`, `status_v2`, `track`, `stops`, `progress`

#### Predictions
- Backend: `PredictionData` with track probabilities
- iOS: `PredictionData` struct with Owl display logic
- Web App: Owl message generation with confidence levels
- Confidence thresholds: ≥80% (high), 50-79% (medium), <50% (low)

#### Status Values
All platforms recognize: `ALL ABOARD`, `BOARDING`, `DEPARTED`, `CANCELLED`, `DELAYED`, etc.
- New `status_v2` field provides enhanced status resolution

## Development Workflow

### When Making Backend Changes

1. **API Changes**:
   - Update OpenAPI spec if modifying endpoints
   - Consider iOS app and web app compatibility
   - Maintain backward compatibility when possible
   - Document new query parameters in backend/CLAUDE.md

2. **Model Changes**:
   - Update database schema with migrations
   - Ensure API serialization matches frontend expectations
   - Test with both consolidated and non-consolidated responses

3. **New Features**:
   - Add corresponding CLI commands
   - Update scheduler if periodic execution needed
   - Consider iOS and web UI implications

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

### When Making Web App Changes

1. **API Integration**:
   - Use consistent API patterns with iOS app
   - Handle all date formats with Eastern Time zone
   - Always specify `from_station_code` and `consolidate=true`

2. **UI Updates**:
   - Maintain responsive design principles
   - Ensure mobile-first approach
   - Test across different screen sizes

3. **Feature Parity**:
   - Core functionality should mirror iOS app
   - Simplified feature set appropriate for web
   - No Live Activities or push notifications

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

### Web App Testing
```bash
# Start backend API
trackcast start-api

# Start web proxy server
cd webpage && python proxy.py

# Test in browser at http://localhost:9998
# Test mobile responsiveness with browser dev tools
```

### End-to-End Testing

1. **Data Flow Verification**:
   - Start backend services: `trackcast start-scheduler`
   - Verify data collection: `trackcast collect-data`
   - Check predictions: `trackcast generate-predictions`
   - Test iOS app and web app against live API

2. **Consolidation Testing**:
   - Enable consolidation in API: `?consolidate=true`
   - Verify all frontends handle merged trains correctly
   - Check track confidence display

## Common Integration Points

### API Endpoints Used by Frontends

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

### Data Synchronization

1. **Polling Intervals**:
   - Backend: 60s (NJ Transit), 120s (Amtrak)
   - iOS: 30s (active view), 30s (Live Activity background)
   - Web App: 30s (train details view)

2. **Cache Considerations**:
   - Backend: Database serves as cache
   - iOS: No persistent cache, real-time fetching
   - Web App: LocalStorage for recent destinations only

3. **State Management**:
   - Backend: Stateless API, database for persistence
   - iOS: @StateObject for app state, UserDefaults for preferences
   - Web App: JavaScript state management, LocalStorage for preferences

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

### Web App Deployment
- Static files can be served by any web server
- Proxy server (proxy.py) for local development only
- Production deployment should proxy API directly
- Test responsive design on multiple devices

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

### Web App
- 30-second refresh interval for real-time updates
- LocalStorage caching for station data
- Minimal DOM manipulation for performance
- Mobile-first responsive design

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

### Web App
- No user tracking or analytics
- LocalStorage only for recent destinations
- No third-party dependencies
- Secure API communication via HTTPS

## Troubleshooting Guide

### Common Backend Issues
1. **Missing predictions**: Check model files exist in `models/` directory
2. **API timeouts**: Verify network connectivity to NJ Transit/Amtrak
3. **Database errors**: Check PostgreSQL connection and migrations

### Common iOS Issues
1. **Live Activities not appearing**: Verify Info.plist configuration
2. **API connection errors**: Check backend URL and network
3. **Push notifications failing**: Verify APNS setup

### Common Web App Issues
1. **API connection errors**: Check proxy server is running (proxy.py)
2. **Cross-origin issues**: Ensure proper CORS headers in production
3. **Mobile layout issues**: Test responsive design on actual devices

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

### JavaScript (Web App)
- Modern ES6+ syntax
- Consistent naming conventions
- Minimal DOM manipulation
- No external dependencies

## Feature Development Checklist

When adding new features that span multiple platforms:

- [ ] Design API contract first
- [ ] Implement backend functionality
- [ ] Add comprehensive tests
- [ ] Update API documentation
- [ ] Implement iOS UI/functionality
- [ ] Implement web app functionality
- [ ] Test end-to-end flow on all platforms
- [ ] Update all CLAUDE.md files
- [ ] Consider Live Activity implications
- [ ] Verify performance impact
- [ ] Check error handling
- [ ] Test mobile responsiveness

## Recent Enhancements

### Enhanced Status Resolution (StatusV2)
All platforms now support intelligent status conflict resolution:
- **Backend**: New `status_v2` field with DEPARTED > BOARDING priority
- **iOS**: Enhanced display using `statusV2` with fallback to legacy
- **Web App**: Uses `status_v2` with fallback to `status` for backward compatibility
- **Benefits**: Solves the "stuck BOARDING" issue when trains depart

### Real-time Progress Tracking
New `progress` field provides detailed journey information:
- **Backend**: Calculates stops completed, minutes to arrival, journey percentage
- **iOS**: Enhanced Live Activities and progress bars using this data
- **Web App**: Progress visualization with journey completion bars
- **Benefits**: Accurate progress visualization and time-to-arrival

### API Changes Summary
- **New Fields**: `status_v2`, `progress` (both optional for backward compatibility)
- **Enhanced Data**: `last_departed`, `next_arrival`, `journey_percent`
- **No Breaking Changes**: All existing fields preserved

## Architecture Decisions

### Why These Choices?

1. **Station-Specific Models**: Better accuracy than combined model
2. **Train Consolidation**: Unified view across data sources
3. **30-Second Refresh**: Balance between real-time and battery life
4. **Eastern Time Zone**: Natural for Northeast Corridor users
5. **No User Accounts**: Privacy-first approach
6. **StatusV2 Design**: Resolves conflicts while maintaining compatibility
7. **Progress Tracking**: Provides real-time journey visualization

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

3. **Web App**:
   - Progressive Web App (PWA) support
   - Service worker for offline caching
   - Push notifications via web standards
   - Desktop app packaging

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

### Web App Key Files
```
webpage/index.html                   # Main HTML structure
webpage/script.js                    # Core application logic
webpage/styles.css                   # Responsive styling
webpage/proxy.py                     # Development proxy server
webpage/CLAUDE.md                    # Web app specific guidance
```

### API Base URLs
- Development: `http://localhost:8000/api`
- Production: `https://trackcast.andymartin.cc/api`

## Contact for Questions

When working on this project, refer to:
- Backend details: `backend/CLAUDE.md`
- iOS details: `ios/CLAUDE.md`
- Web app details: `webpage/CLAUDE.md`
- This file for cross-platform guidance

Remember: The goal is seamless integration between a powerful prediction backend and intuitive frontend experiences across iOS (with Live Activities) and web platforms.