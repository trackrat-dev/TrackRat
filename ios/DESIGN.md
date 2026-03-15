# TrackRat iOS App - Design Documentation

This document contains detailed design specifications, screen documentation, and implementation details for the TrackRat iOS app. For essential development information, see `CLAUDE.md`.

## Screen Architecture

### 1. **ContentView** (App Entry Point)
- Routes to MapContainerView as main interface
- Handles initial app setup and navigation

### 2. **MapContainerView** (Primary Interface)
- Full-screen map with real-time train positions
- Bottom sheet with multiple positions (.collapsed, .medium, .large)
- Integrated journey planning and Live Activity management
- Congestion visualization overlay
- Coordinated scrolling between map and sheet content
- Map layer controls (congestion, routes, stations) via layers button
- Route topology overlay for all transit systems (NJT, Amtrak, PATH, PATCO, LIRR, MNR, Subway)

### 3. **TripSelectionView** (Journey Planning Screen)
- Shows active Live Activities at the top with journey progress
- RatSense AI suggestions based on time of day and user patterns
- Recent trips list with quick selection
- "Add New Trip" button for new journeys
- Glassmorphism design with dark mode preference
- Orange accent color throughout

### 4. **DeparturePickerView**
- Origin station selection for departures
- Primary stations: NY Penn, Newark Penn, Trenton, Princeton Junction, Metropark
- Additional Southeast Amtrak stations: Charlotte, Raleigh, Atlanta, Miami, Jacksonville, Tampa, Orlando, and more
- PATH: 13 stations, PATCO: 14 stations, Keystone: 8 Pennsylvania stations
- Total station coverage: 250+ stations across all transit systems
- Glassmorphism cards with owl background
- Navigates to destination picker after selection

### 5. **DestinationPickerView**
- Recent destinations with UserDefaults persistence
- Real-time search with Stations.search()
- Shows selected departure station in header
- Haptic feedback on selection
- Gradient background with glassmorphism

### 6. **TrainListView**
- 30-second auto-refresh with Timer.publish
- Pull-to-refresh gesture
- Boarding status highlighting with orange theme
- Owl predictions inline with Live Activity controls
- Origin-based departure time display
- Train deduplication by train_id
- Shows departure and destination in header
- Live Activity toggle buttons for each train

### 7. **TrainDetailsView**
- Real-time status updates with consolidated train data
- Journey visualization with stop indicators
- Boarding state with orange theming
- Modal sheet for historical data
- Origin-aware timing display
- Live Activity controls with start/stop functionality
- Background refresh when Live Activity is active
- Flexible navigation support (by ID or train number)

### 8. **HistoricalDataView**
- Delay performance bars
- Track usage visualization
- Three-tier analytics (train/line/destination)
- Origin-filtered historical data
- Modal presentation from train details

### 9. **CongestionMapView**
- Network-wide congestion visualization
- Real-time occupied tracks at major stations
- Segment-based train density display
- Interactive segment selection for detailed train lists
- Color-coded congestion levels
- Time window filtering (1-24 hours)
- Map layer controls: Congestion (Off/Summary/Trains), Routes, Stations
- Route topology overlay for NJT, Amtrak, PATH, PATCO, LIRR, MNR, Subway lines
- Pro-only congestion map feature with paywall prompt

### 10. **OnboardingView**
- Multi-step user onboarding flow
- Intro video with automatic progression
- Home/work station configuration
- Favorite stations setup
- Video fallback handling for errors

### 11. **RouteStatusView** (Route Alert Details)
- Per-route performance dashboard triggered from notification taps
- Frequency baseline coloring (system-appropriate health metric)
- Recent departures with delay/cancellation stats
- Map visualization of subscribed route
- Integrates with route alert subscription system

### 12. **AddRouteAlertView** (Add Route Alert)
- Multi-add workflow for route alert subscriptions
- Station pickers for origin/destination
- System-appropriate metric selection
- Recurring train alert configuration per train number

### 13. **ChatView** (Developer Chat)
- Two-party messaging between user and developer
- Real-time message history with send/receive
- Push notification integration for new messages
- Unread message count badge

### 14. **AdminChatListView** (Admin Chat Management)
- Lists all user conversations for admin
- Admin registration via secret code
- Per-conversation message history and reply

### 15. **AdvancedConfigurationView**
- Server environment selection (Production/Staging/Local)
- Home/work station management
- Favorite stations configuration
- Developer debug tools
- Cache clearing utilities
- Backend health check testing

### 16. **SettingsView**
- **Trip Statistics**: Total trips, on-time percentage, minutes saved vs scheduled
- **Trip History Access**: Link to full TripHistoryView
- **Favorite Stations**: Inline editing (no separate view)
- **Route Alerts**: Inline management (no separate EditRouteAlertsView)
- **Train System Preferences**: Enable/disable transit systems
- **Amtrak Mode**: Tri-state toggle (Off / NEC Only / All)
- User preferences and settings
- Quick access to advanced configuration

### 17. **TripHistoryView**
- Complete history of recorded trips from Live Activities
- Trip details: origin, destination, train, duration, delay
- Filtering by date range or data source
- Visual delay indicators (green/yellow/red)

## Live Activities

### Implementation Details
- **iOS 16.1+ Feature**: Real-time train tracking on Lock Screen and Dynamic Island
- **Background Updates**: Automatic refresh every 30 seconds via URLSession
- **Push Notifications**: Status changes, boarding alerts, stop departures
- **Journey Progress**: Real-time position tracking with interpolation
- **Auto-End Logic**: Intelligent termination based on arrival or data staleness

### Live Activity Components
- **LiveActivityService**: Core service managing Live Activity lifecycle
  - Start/stop Live Activities with train data
  - Background update scheduling
  - Push notification handling
  - Journey progress calculation
  - Haptic feedback for important events
- **TrainLiveActivityBundle**: Activity configuration and setup
- **LiveActivityWidget**: Lock Screen and Dynamic Island UI
  - Compact view: Next stop and time remaining
  - Expanded view: Full journey visualization
  - Minimal view: Train number and status

### User Experience Features
- **Visual Journey Progress**: Color-coded stops with current position
- **Smart Notifications**:
  - Approaching stop (within 3 minutes)
  - Status changes (delays, track assignments)
  - Boarding announcements
  - Departure confirmations
- **Haptic Feedback**: Status changes and important events
- **Auto-End Conditions**:
  - Train reaches final destination
  - No updates for 15 minutes
  - Train departs without user

### UI Components
- **ActiveTripsSection**: Shows all active Live Activities on home screen
- **LiveActivityControls**: Start/stop buttons in train views
- **LiveActivityDebugView**: Developer tools for testing

## API Integration

### Service Layer
- **APIService**: Singleton with shared instance
- **Base URL**: `https://apiv2.trackrat.net/api`
- **JSONDecoder**: Multiple ISO8601 date format support with fractional seconds
- **URLSession**: Native networking with proper timeout handling
- **Error handling**: Typed errors with recovery
- **Eastern Time Zone**: Automatic conversion for all timestamps

### Endpoints Used (V2 API)
- `GET /v2/trains/departures?from=X&to=Y&limit=1000&date=YYYY-MM-DD` - Search trains between stations (supports up to 1000 results)
- `GET /v2/trains/{id}?date=YYYY-MM-DD&include_predictions=true&from_station=X` - Train details with predictions
- `GET /v2/trains/{id}/history?days=365&from_station=X&to_station=Y&include_route_trains=true` - Historical train data
- `GET /v2/routes/history?from_station=X&to_station=Y&data_source=NJT&days=30` - Route historical performance
- `GET /v2/trains/stations/{code}/tracks/occupied` - Real-time occupied tracks at station
- `GET /v2/routes/congestion?time_window_hours=1&max_per_segment=100&data_source=X` - Network congestion data
- `GET /v2/routes/segments/{from}/{to}/trains?max_trains=X&data_source=Y` - Segment-specific train details
- `GET /v2/predictions/track?station_code=X&train_id=Y` - Owl track predictions
- `GET /v2/predictions/delay?train_id=X&station_code=Y&journey_date=Z` - Delay and cancellation forecasts
- `GET /v2/operations/summary?scope=X&from_station=Y&to_station=Z&train_id=W` - Operations summary (network/route/train)
- `POST /v2/feedback` - Submit user feedback for data issues
- `POST /v2/live-activities/register` - Register Live Activity for updates
- `DELETE /v2/live-activities/{push_token}` - Unregister Live Activity
- `POST /v2/devices/register` - Register APNS device token for route alerts
- `PUT /v2/alerts/subscriptions` - Sync route alert subscriptions
- `GET /v2/routes/history?from_station=X&to_station=Y&data_source=Z&days=N` - Route performance history
- `GET /health` - Backend health check for wake-up service

### API Features
- **Consolidated Train Data**: Merges data from multiple sources (Amtrak, NJTransit)
- **Real-time Position**: Current train location with segment progress
- **Enhanced Track Assignment**: Source attribution for track predictions
- **Flexible Train Lookup**: Support for both numeric IDs and train numbers
- **Multi-Environment Support**: Production, Staging, and Local development environments
- **Backend Wake-up**: 15-minute cached health checks to warm serverless backends

## Data Models

### Core Types
- **TrainV2**: Main model with comprehensive train data (current implementation)
  - Extensions for origin-based departure time calculation
  - Methods: `getScheduledDepartureTime(fromStationCode:)`, `getFormattedScheduledDepartureTime(fromStationCode:)`
  - Live Activity support: `toLiveActivityContentState(from:toCode:toName:)`
  - New fields: `originStation`, `dataSource`, `currentPosition`, `trackAssignment`, `statusV2`, `progress`
  - Status summary with delay information
  - Consolidation metadata for multi-source trains
  - Enhanced properties: `enhancedDisplayStatus`, `displayLocation`, `journeyProgress`
- **Train**: Legacy model maintained for compatibility
- **TrainStatus**: Enum with color mappings and display strings
- **Stop**: Station with times, status, and departure confirmations
  - Enhanced with `departedConfirmedBy` array for multi-source validation
- **PredictionData**: Track probabilities from Owl system
- **Stations**: Static station data with code mappings
  - Complete station list including all NJ Transit and Amtrak stations
  - Station code dictionary for API queries
  - Supported departure stations list

### Live Activity Types
- **TrainActivityAttributes**: ActivityKit attributes for train tracking
- **TrainActivityContentState**: Dynamic content for Live Activities
- **JourneyProgress**: Real-time position tracking
  - Current/next stop indices
  - Segment progress percentage
  - Location state enumeration
- **NextStopInfo**: Next stop details for widgets
- **OwlPredictionInfo**: Simplified predictions for Live Activities
- **LiveActivityModels**: Shared types between app and widget

### Storage Types
- **TripPair**: Origin-destination pair with station codes
- **RecentDeparture**: Recently used departure stations
- **StorageService**: UserDefaults wrapper with migration support

### Navigation Types
- **NavigationDestination**: Enhanced enum with flexible train details
  - `.departureSelector` - Departure station picker
  - `.destinationPicker` - Destination station picker
  - `.trainList(destination: String)` - List of trains for route
  - `.trainDetails(trainId: Int)` - Legacy train details by ID
  - `.trainDetailsFlexible(trainNumber: String, fromStation: String?, journeyDate: Date?)` - Flexible train lookup
  - `.advancedConfiguration` - Developer settings
  - `.settings` - Settings
  - `.congestionMap` - Network congestion view
  - `.favoriteStations` - Favorite stations (managed inline in SettingsView)
  - `.addRouteAlert` - Add new route alert
  - `.routeStatus(route)` - Route alert performance dashboard

### API Response Types
- **OriginStation**: Train origin information
- **DataSource**: Data provider enumeration (Amtrak, NJTransit)
- **CurrentPosition**: Real-time train location
- **TrackAssignment**: Track info with source attribution
- **StatusSummary**: Consolidated status with delays
- **ConsolidationMetadata**: Multi-source merge information
- **StatusV2**: Enhanced status with conflict resolution and location info
- **Progress**: Real-time journey tracking with completion percentage
- **DepartedStation**: Last departed stop with delay information
- **NextArrival**: Next station arrival with estimated time
- **OperationsSummaryResponse**: Summary of train operations with headline and body
- **SummaryMetrics**: Metrics including trains by delay category
- **SummaryScope**: Enum (network, route, train) for operations summary
- **TrainDelaySummary**: Individual train delay info with category
- **DelayCategory**: Enum (on_time, slight_delay, delayed, cancelled)

### Deep Link Types
- **DeepLink**: URL parsing and generation for train deep links
  - Supports `trackrat://train/{trainId}` and `https://trackrat.net/train/{trainId}`
  - Query parameters: date, from, to station codes
  - Methods: `init?(url:)`, `generateURL()`, `generateShareText()`

### Historical Types
- **DelayStats**: Performance percentages
- **TrackStats**: Usage distribution
- **HistoricalData**: Combined analytics

### Configuration Types
- **ServerEnvironment**: Multi-environment support (production, staging, local)
- **FavoriteStation**: User's saved stations with codes and names
- **JourneyContext**: User-specific journey information for calculations

### Map & Congestion Types
- **CongestionSegment**: Route segment with train density
- **SegmentTrain**: Train information for congestion visualization
- **OccupiedTrack**: Real-time track occupancy at stations
- **MapRegion**: Map viewport and positioning

## UI/UX Patterns

### Design System
- **Dark Mode**: App-wide `.preferredColorScheme(.dark)`
- **Colors**: Purple gradient (#667eea → #764ba2) with orange accent
- **Tint Color**: Orange (`.tint(.orange)`) throughout the app
- **Materials**: `.ultraThinMaterial` for glass effects
- **Typography**: System fonts with Dynamic Type
- **Spacing**: Consistent 16pt grid

### Interactions
- **Haptic Feedback**:
  - UIImpactFeedbackGenerator for taps and selections
  - UINotificationFeedbackGenerator for status changes
  - Live Activity events (boarding, delays, arrivals)
- **Pull-to-Refresh**: Native `.refreshable` modifier
- **Loading States**: ProgressView with proper sizing
- **Navigation**: Glassmorphic navigation bar styling

### Owl Predictions
- High confidence (≥80%): "🦉 Owl thinks it will be track X"
- Medium confidence (50-79%): "🤔 Owl thinks it may be track X"
- Low confidence (<50%): "🤷 Owl guesses tracks X, Y, Z"

### Train Progress Tracking

The app provides sophisticated real-time journey visualization through multiple UI components:

#### **TrainProgressIndicator** (Main App)
- **Animated Progress Bar**: Green-to-blue gradient track with orange train icon (🚋)
- **Real-time Movement**: Train icon moves smoothly along progress bar with 0.5-second animation
- **Pulsing Animation**: Continuous 1-second pulse effect on train icon for visual attention
- **Smart Positioning**: Proper bounds checking ensures icon stays within track boundaries
- **Progress Calculation**: Shows completion percentage for user's specific origin-destination segment

#### **JourneyProgressBar** (Live Activities)
- **Context-Colored Progress**: Orange (boarding), blue (en route), green (arrived), gray (default)
- **Tram Icon Indicator**: `tram.fill` SF Symbol positioned at current progress point
- **Percentage Display**: Numeric completion (0-100%) with journey status text
- **Smooth Updates**: Real-time position updates every 30 seconds with interpolation

#### **Progress Calculation Method**
- **Origin-Destination Focus**: Only tracks user's journey segment, not entire train route
- **Stop-Based Foundation**: Uses completed vs. total stops in journey segment
- **Time-Based Interpolation**: When between stops, estimates position using:
  - Last departed stop's actual departure time
  - Next stop's scheduled arrival time
  - Current time for real-time positioning
- **Segment Progress**: Calculates 0.0-1.0 progress within current track segment

#### **Location State Detection**
- **`.notDeparted`**: Train hasn't left origin yet
- **`.boarding`**: Currently boarding passengers (orange indicators)
- **`.departed`**: Recently departed (within 2 minutes, shows "X min ago")
- **`.approaching`**: Approaching next stop (within 3 minutes, shows countdown)
- **`.enRoute`**: Traveling between stations
- **`.arrived`**: Journey complete at destination

#### **Multi-Platform Consistency**
- **Lock Screen**: Simplified progress bar in Live Activities
- **Dynamic Island**: Full journey progress in expanded view
- **Main App**: Detailed animated progress with contextual information
- **Home Screen**: Horizontal progress bars for all active trips

### UI Components
- **ActiveTripsSection**: Horizontal scroll of active Live Activities with progress indicators
- **LiveActivityControls**: Start/stop buttons with status indicators
- **LiveActivityDebugView**: Developer tools for testing states
- **FeedbackButton**: User issue reporting button with submission sheet
- **OperationsSummaryView**: Network/route/train operations summary with collapsible display
- **TrainStatsSummaryView**: Train-specific historical performance summary
- **TrainDistributionChart**: Visual bar chart showing train delays by category
- **LegacyBottomSheetView**: Draggable bottom sheet with multiple positions
- **LegacySheetAwareScrollView**: Smart scrolling coordinated with bottom sheets
- **Glassmorphic Cards**: Consistent card styling with backdrop blur

### Extensions & Utilities
- **Color+Hex**: Initialize colors from hex strings
- **DateFormatter+Eastern**: Eastern Time zone formatting
- **View+GlassmorphicNavBar**: Custom navigation bar styling
- **Logger**: Debug-only logging framework using os.log (Log.debug, Log.info, Log.warning, Log.error)

## Performance Optimizations

### Update Strategy
- Silent background refresh every 30 seconds
- Haptic feedback only on status changes
- Efficient diffing with Identifiable models
- Lazy loading with ScrollView

### Memory Management
- @StateObject for view-owned state
- Weak references in timers
- Automatic cleanup on navigation

## Services (Detailed)

### Core Services Overview
All services follow the singleton pattern with `shared` instance for app-wide access. Services are organized in `/TrackRat/Services/`:

1. **APIService** - V2 API integration
2. **LiveActivityService** - Live Activities lifecycle management
3. **StorageService** - UserDefaults wrapper with type safety
4. **RatSenseService** - AI journey prediction engine
5. **BackendWakeupService** - Backend warming with caching
6. **DeepLinkService** - URL scheme handling
7. **ShareService** - Deep link sharing functionality
8. **ThemeManager** - Theme configuration (currently hardcoded to dark)
9. **StaticTrackDistributionService** - Track usage analytics
10. **TrainCacheService** - Two-tier train data caching with LRU eviction
11. **TripRecordingService** - Records completed trips from Live Activities for statistics
12. **JourneyFeedbackService** - Triggers feedback prompts during active journeys
13. **SubscriptionService** - Pro subscription management with StoreKit 2
14. **AlertSubscriptionService** - Route alert subscription management and APNS registration
15. **ChatService** - Developer chat messaging and admin functionality

### LiveActivityService
- **Singleton Pattern**: Shared instance for app-wide access
- **Core Functionality**:
  - Start/stop Live Activities with train data
  - Background update scheduling (30-second intervals)
  - Push notification content generation
  - Journey progress calculation with interpolation
  - Auto-end logic for completed/stale journeys
- **Notification Management**:
  - Approaching stop alerts (3-minute window)
  - Status change notifications
  - Boarding announcements
  - Departure confirmations
  - Smart deduplication to prevent spam
- **State Tracking**:
  - Active Live Activities dictionary
  - Last notification states
  - Update timers management

### StorageService
- **UserDefaults Wrapper**: Type-safe storage with Codable
- **Data Types**:
  - Recent trips (TripPair) - up to 10
  - Recent departures (RecentDeparture) - up to 5
  - Recent destinations (String) - legacy, up to 5
- **Migration Support**: Automatic upgrade from destination-only storage
- **Methods**:
  - `saveRecentTrip()`: Add origin-destination pair
  - `getRecentTrips()`: Retrieve saved trips
  - `saveRecentDeparture()`: Track departure stations
  - `migrateDestinationsToTrips()`: One-time migration

### APIService
- **Consolidated Train Support**: V2 endpoints for multi-source data
- **Flexible Lookups**: Support for both train IDs and numbers
- **Date Handling**: Multiple ISO8601 formats with fractional seconds
- **Eastern Time Zone**: Automatic conversion for all timestamps
- **Error Recovery**: Typed errors with user-friendly messages
- **Environment Switching**: Dynamic base URL based on ServerEnvironment
- **Timeout Handling**: Configurable timeouts per endpoint

### RatSenseService
- **AI Journey Predictions**: Intelligent trip suggestions based on user behavior
- **Time-Based Detection**: Morning (5-9am) and evening (1-8pm) commute patterns
- **Home/Work Learning**: Automatic detection of frequent routes
- **Recent Context**: Suggests same route within 20 minutes of last search
- **Return Journey**: Suggests reverse route 2-8 hours after Live Activity
- **Live Activity Integration**: Records journey patterns from active trips
- **Persistence**: Stores learned patterns in UserDefaults

### BackendWakeupService
- **Health Check API**: Periodic backend warming to reduce cold starts
- **15-Minute Cache**: Prevents redundant wake-up requests
- **Environment-Aware**: Separate caches for production/staging/local
- **Smart Retry Logic**: Clears cache on failures for immediate retry
- **Scene Phase Integration**: Automatically wakes backend on app activation
- **Async Operation**: Non-blocking health checks with proper error handling

### DeepLinkService & ShareService
- **URL Scheme Support**: `trackrat://` custom scheme
- **Train Details**: `trackrat://train/{trainNumber}` for direct train lookup
- **Journey Search**: `trackrat://journey?from={station}&to={station}` for route planning
- **Share Sheet Integration**: Generate deep links for sharing trips
- **Context Preservation**: Maintains origin station and journey date in links

### ThemeManager
- **Centralized Theme System**: Complete design system in TrackRatTheme.swift
- **Color Palette**: Semantic color naming with dark mode support
- **Typography Scale**: Consistent font sizing and weights
- **Spacing System**: Standard spacing values (8pt grid)
- **Corner Radius**: Consistent border radius values
- **View Extensions**: Convenient modifiers for common patterns

### TrainCacheService
- **Two-Tier Caching**: In-memory cache for speed, UserDefaults for persistence
- **LRU Eviction**: Automatic eviction of least recently used entries (max 50 in memory)
- **5-Minute Expiry**: Cached train data expires after 300 seconds
- **Cache Key Generation**: Unique keys based on trainId, trainNumber, date, fromStation
- **Methods**:
  - `getCachedTrain()`: Retrieve cached train if available and not expired
  - `cacheTrain()`: Store train in both memory and persistent cache
  - `clearCache()`: Remove specific or all cached entries
  - `getCacheStats()`: Debug helper for cache statistics

## Accessibility

- Dynamic Type support throughout
- Semantic colors for status indicators
- VoiceOver labels on interactive elements
- High contrast borders for visibility

## Security & Privacy

- **Local Storage**: UserDefaults only for preferences and recent trips
- **Push Notifications**: Only for active Live Activities
- **No User Accounts**: No server-side user profiles or authentication
- **Permissions Required**:
  - Push Notifications (optional, for Live Activity updates)
  - Live Activities (iOS 16.1+)
- **Info.plist Configuration**:
  - `NSSupportsLiveActivities: true`
  - `NSSupportsLiveActivitiesFrequentUpdates: true`
- **Data Privacy**:
  - All data stored locally in UserDefaults
  - No server-side user accounts or profiles
  - Train data fetched on-demand only

## Development Setup

### Requirements
- Xcode 15.0+
- iOS 18.0+ deployment target
- Swift 5.9+
- macOS 14.0+ for development

### Build Configuration
- **Bundle Identifier**: `net.trackrat.TrackRat`
- **Version**: 1.6 (Build 2)
- **Development Team**: Set in Xcode project settings
- **Code Signing**: Automatic with development certificate
- **Capabilities**:
  - Push Notifications
  - Background Modes (Background fetch, Remote notifications)
  - Associated Domains (applinks:trackrat.net, applinks:www.trackrat.net)
  - App Groups (group.net.trackrat.TrackRat)

### Entitlements
```xml
<key>aps-environment</key>
<string>development</string>
<key>com.apple.security.application-groups</key>
<array>
    <string>group.net.trackrat.TrackRat</string>
</array>
<key>com.apple.developer.associated-domains</key>
<array>
    <string>applinks:trackrat.net</string>
    <string>applinks:www.trackrat.net</string>
</array>
```

### Testing Live Activities
- Use LiveActivityDebugView for testing different states
- Simulator supports Live Activities from iOS 16.1+
- Physical device recommended for push notification testing
- Use Console.app to debug Live Activity updates

### Testing Recommendations
1. **Unit Tests**: Add tests for all services and view models
2. **UI Tests**: Automate critical user journeys
3. **Integration Tests**: Test API communication and data flow
4. **Performance Tests**: Monitor app launch time and memory usage
5. **Live Activity Tests**: Validate all state transitions

### Test Directory Structure (TrackRatTests/)
- **BuildTests.swift**: Basic build verification tests
- **Models/**: Model unit tests (TrainV2, DeepLink, etc.)
- **Services/**: Service unit tests (API, Storage, LiveActivity, etc.)
- **ViewModels/**: ViewModel unit tests
- **TestUtilities/**: Test helper functions and mocks
- **TestFixtures/**: JSON fixtures for API response testing

## Additional Features & Components

### Congestion Mapping System
- **Real-time Network Visualization**: Map-based view of train density across the network
- **Segment Analysis**: Click segments to see detailed train lists
- **Occupied Tracks**: View which tracks are currently occupied at major stations
- **Time Window Filtering**: Adjust congestion view from 1-24 hours
- **Color-Coded Density**: Visual representation of crowded vs. empty segments
- **Data Source Filtering**: View Amtrak, NJ Transit, or combined data
- **Map Integration**: Full MapKit integration with coordinate-based visualization

### Video Integration
- **Onboarding Video**: Intro video with AVPlayer integration
- **YouTube Embeds**: Penn Station guide uses YouTube links with thumbnails
- **Fallback Handling**: Graceful degradation when videos fail to load
- **Automatic Progression**: Onboarding advances after video completion
- **Custom Video Player**: VideoPlayerView component for native playback

### Bottom Sheet System
- **Three Positions**: Collapsed (map focus), Medium (peek), Large (full content)
- **Drag Gestures**: Smooth dragging with spring animations
- **Coordinated Scrolling**: LegacySheetAwareScrollView syncs with sheet position
- **Haptic Feedback**: Position changes trigger haptic response
- **State Persistence**: Sheet position maintained during navigation
- **Flexible Content**: Can host any SwiftUI view content

### UI Component Library
- **ActiveTripsSection**: Horizontal scroll of active Live Activities
- **AlertConfigurationSection**: Route alert configuration controls
- **DateSelectorSheet**: Date picker sheet for schedule browsing
- **FeedbackButton**: User issue reporting with submission sheet
- **JourneyCongestionMapView**: Journey-specific congestion visualization
- **JourneyFeedbackPromptView**: Mid-journey feedback prompt
- **LegacyBottomSheetView**: Reusable draggable bottom sheet
- **LegacySheetAwareScrollView**: Smart scrolling coordinated with sheets
- **LiveActivityControls**: Start/stop buttons with status indicators
- **OperationsSummaryView**: Network/route/train operations summary
- **StationButton**: Station selection button component
- **StationPickerSheet**: Modal station picker for settings
- **StationRow**: Station list row component
- **TrackRatLoadingView**: Custom loading animation with mascot
- **TrackRatMascot**: Animated mascot character
- **TrackRatNavigationHeader**: Custom navigation header
- **TrackTrainInlineButton**: Inline train tracking button
- **TrainDistributionChart**: Visual delay distribution chart
- **TrainFrequencyChart**: Frequency chart (column layout) for subway/PATH/PATCO
- **TrainStatsSummaryView**: Train performance analytics display

## Recent Enhancements

### New Features (February 2026)

#### Route Alerts System
- **Route Alert Subscriptions**: Subscribe to routes for delay/cancellation push notifications
- **Recurring Train Alerts**: Subscribe to specific train numbers for daily commute monitoring
- **RouteStatusView**: Per-route performance dashboard with frequency baseline coloring
- **Notification Tap Navigation**: Deep link from alert notifications to route performance view
- **System-Appropriate Health Metric**: Auto-selects frequency vs on-time metric by transit system

#### Settings Redesign
- **Rebranded "My Profile" to "Settings"** with gear icon in tab bar
- **Amtrak Tri-State Toggle**: Off → NEC Only → All (consolidated from separate toggles)
- **Health Indicator Auto-Coloring**: Congestion map segments auto-colored by train system (deprecated manual picker)

#### NYC Subway Support (iOS)
- Full subway station coverage via station code mapping
- Subway-aware congestion map with STATION_EQUIVALENTS aggregation
- System filtering for subway routes

### New Features (January 2026)

#### PATH and PATCO Support
New transit system integrations:
- **PATH Train Support**: Full schedule and real-time data via GTFS
- **PATCO Speedline**: Schedule-based data integration with 14 stations
- **RouteTopology.swift**: Client-side route definitions for map visualization
- **Multi-transit Map Layers**: Visual overlays for all transit lines on map

#### Pro Subscription Tier
Premium features with StoreKit 2 integration:
- **SubscriptionService**: Manages Pro subscription state and purchases
- **ProFeatureLockView**: Paywall prompt for premium features
- **Congestion Map Access**: Pro-only network congestion visualization
- **StoreKit 2**: Modern subscription purchase and management
- **Monthly-Only Pricing**: $3.99/month (configured in App Store Connect)
- **16-Hour Preview Period**: New users automatically get Pro access for 16 hours
- **Debug Override**: `debugOverrideEnabled` defaults to `true` - all users currently get Pro features for free during soft launch. Set to `false` in SubscriptionService.swift to enable actual paywall.

#### Map Layer Controls
Toggleable map visualization options:
- **Layer Controls Button**: Top-right corner access to map layers
- **Congestion Mode**: Cycles through Off/Summary/Trains visualization
- **Route Topology**: Shows/hides static rail line topology
- **Station Markers**: Toggleable station dot markers
- **MapLayerControlsView**: Compact menu for layer selection

#### GTFS Future Date Schedules
View train schedules for future dates:
- **GTFS Static Data**: Integration with transit agency schedule files
- **Future Date Departures**: Browse schedules days in advance
- **Train Details Endpoint**: Support for future date journey viewing

#### Delay and Cancellation Forecasting
ML-powered delay predictions shown in train details:
- **DelayForecastView**: Shows cancellation probability, delay breakdown, and expected delay minutes
- **TrainStatsSummaryView Integration**: Delay forecast is displayed in expandable train summary section
- **API Integration**: Fetches from `/api/v2/predictions/delay` endpoint
- **Confidence Indicators**: Shows prediction confidence based on sample count
- **Factors Display**: Lists contributing factors (time of day, line performance, historical patterns)

#### Trip Statistics & History (Flighty-style)
Comprehensive trip tracking with statistics:
- **TripRecordingService**: Records completed trips from Live Activities with start/end times, delays, train info
- **CompletedTrip Model**: Stores journey data including origin/destination, duration, delay minutes, data source
- **SettingsView**: Shows trip statistics (total trips, on-time %, minutes saved vs scheduled)
- **TripHistoryView**: Full trip history with filtering and detailed journey information
- **StorageService**: Enhanced to persist trip data across sessions

#### Journey Feedback Prompts
Proactive feedback collection during journeys:
- **JourneyFeedbackService**: Triggers feedback prompts at 2/3 journey progress
- **JourneyFeedbackPromptView**: Non-intrusive prompt asking "How's your journey going?"
- **ImprovementFeedbackSheet**: Detailed feedback form for data quality issues
- **LiveActivityService Integration**: Automatically triggers prompts during active Live Activities

### Previously Documented Features

#### RatSense AI Journey Suggestions
Intelligent journey prediction system that learns from user behavior:
- **Smart Suggestions**: Predicts likely trips based on time of day and history
- **Home/Work Detection**: Learns commute patterns automatically
- **Recent Context**: Suggests same route within 20 minutes of last search
- **Return Journey**: Suggests reverse route 2-8 hours after Live Activity
- **Time-Based Logic**: Morning (5-9am) and evening (1-8pm) commute predictions
- **Live Activity Integration**: Records and learns from Live Activity usage

#### Backend Wake-up Service with Caching
Optimized backend communication system:
- **15-Minute Cache**: Prevents redundant wake-up requests
- **Environment-Aware**: Separate caches for dev/staging/production
- **Health Check API**: Full diagnostic endpoint for troubleshooting
- **Smart Retries**: Clears cache on failures for immediate retry
- **Scene Phase Integration**: Wakes backend on app activation

#### Enhanced UI Components
- **LegacyBottomSheetView**: Draggable bottom sheet with multiple positions
- **LegacySheetAwareScrollView**: Smart scrolling that coordinates with bottom sheets
- **TrackRatLoadingView**: Custom loading animation
- **VideoPlayerView**: Native video playback for onboarding
- **TrackRatMascot**: Animated mascot character
- **JourneyCongestionMapView**: Visual congestion mapping
- **FeedbackButton**: User issue reporting component
- **OperationsSummaryView**: Real-time operations summary with metrics
- **TrainDistributionChart**: Delay distribution visualization

#### Deep Linking Support
Complete URL scheme for external navigation:
- **Train Details**: `trackrat://train/{trainNumber}`
- **Journey Search**: `trackrat://journey?from={station}&to={station}`
- **Live Activity Integration**: Deep links from notifications

#### Theme Management System
- **Dynamic Color Schemes**: Light/dark mode support
- **Custom Tint Colors**: User-selectable accent colors
- **Persistent Preferences**: Theme settings saved across launches

#### Advanced Configuration View
- **Server Environment Selection**: Dev/Staging/Production switching
- **Favorite Stations Management**: Add/remove favorite stations
- **Home/Work Station Setting**: Configure for RatSense
- **Debug Tools**: Test data generation and cache clearing

### Southeast Amtrak Station Expansion
Major expansion of station coverage across the Southeast corridor:
- **New Stations**: Added 44 Southeast stations to Stations.swift
- **States Covered**: North Carolina, South Carolina, Georgia, Florida, Virginia, West Virginia
- **Major Cities**: Charlotte (CLT), Raleigh (RGH), Atlanta (ATL), Miami (MIA), Jacksonville (JAX), Tampa (TPA), Orlando (ORL)
- **Train Services**: Full support for Silver Star, Silver Meteor, Carolinian, Piedmont, Crescent
- **Station Codes**: All stations use standard Amtrak codes (e.g., WAS, RVR, CLT, SAV)
- **Total Coverage**: System now supports ~144 stations across the Eastern US

### Enhanced Status Display (StatusV2)
The app now intelligently resolves conflicting train statuses from multiple data sources:
- **Automatic Conflict Resolution**: DEPARTED always overrides BOARDING status
- **Human-Readable Locations**: Shows "between X and Y" for en route trains
- **Confidence Levels**: Indicates data reliability (high/medium/low)
- **Source Attribution**: Shows which station/source provided the status

### Real-time Progress Tracking
New progress tracking provides detailed journey information:
- **Journey Percentage**: Overall trip completion (0-100%)
- **Next Arrival Times**: Estimated arrival with delay calculations
- **Minutes to Next Stop**: Real-time countdown
- **Stop Completion**: X of Y stops completed display

### Live Activity Enhancements
Live Activities now use the enhanced data for better tracking:
- **Smart Location Updates**: Uses StatusV2 for accurate positioning
- **Enhanced Progress**: Shows journey percentage from Progress data
- **Better Delay Info**: Consolidated delay information from all sources
- **Improved Next Stop**: More accurate arrival predictions

### UI Improvements
- **Status Cards**: Show location info from StatusV2
- **Progress Bars**: Display journey percentage visually
- **Next Stop Info**: Minutes away with estimated arrival
- **Fallback Logic**: Gracefully handles missing enhanced data

## Future Considerations

### Planned Features
- **Widget Extension**: Home/Lock Screen widgets for favorite routes
- **Apple Watch App**: Companion app with Live Activity sync
- **Siri Shortcuts**: Quick access to frequent trips
- **Offline Mode**: Core Data caching for reliability
- **Interactive Notifications**: Quick actions from alerts
- **CarPlay Support**: Hands-free train tracking
- **Additional Transit Systems**: SEPTA regional rail

### Potential Enhancements
- **Multi-Language Support**: Localization for broader audience
- **Accessibility Improvements**: Enhanced VoiceOver navigation
- **iPad Optimization**: Multi-column layouts
- **macOS Catalyst**: Desktop companion app
- **CloudKit Sync**: Cross-device preference sync

## Known Issues & Areas for Improvement

### Critical Bugs
1. **Background Task Completion**: Missing proper task completion in some error paths
2. **Push Notification Handling**: Inconsistent handling of different notification payload formats
3. **Train Validation Race Conditions**: Multiple concurrent validation tasks not properly cancelled

### Performance Issues
1. **Image Loading**: Video thumbnails loaded synchronously, blocking UI
2. **API Call Redundancy**: Some views make duplicate API calls on refresh
3. **Memory Usage**: Large video files kept in memory during onboarding

### Architecture Improvements Needed
1. **Dependency Injection**: Hard-coded singletons make testing difficult
2. **Error Handling**: Inconsistent error propagation and user messaging
3. **State Management**: AppState becoming a god object with too many responsibilities
4. **Navigation**: Deep linking implementation is fragile and needs refactoring

### Missing Features
1. **Offline Support**: No caching for offline viewing
2. **Accessibility**: Limited VoiceOver support in custom components
3. **Localization**: No support for multiple languages
4. **User Analytics**: No feature usage analytics
5. **Light Theme**: Theme system exists but only dark mode implemented

### Code Quality Issues
1. **Test Coverage**: <10% test coverage across the codebase
2. **Documentation**: Many complex functions lack documentation
3. **Magic Numbers**: Hard-coded values throughout (timeouts, delays, sizes)
4. **Code Duplication**: Similar logic repeated in multiple views
5. **SwiftLint**: No linting rules enforced

### Security Concerns
1. **API Keys**: No certificate pinning for API calls
2. **Token Storage**: Push tokens stored in memory without encryption
3. **Deep Links**: Limited validation of deep link parameters

## Technical Debt

### Current Issues
- Xcode project file manual management (consider Swift Package Manager)
- Missing unit tests for ViewModels and services
- No integration tests for Live Activities
- Limited error recovery in background updates

### Code Quality Improvements Needed
- Extract magic numbers to constants
- Consolidate date formatting logic
- Add comprehensive logging system
- Implement proper dependency injection
- Create reusable view components library

### Architecture Considerations
- Implement proper deep linking for all screens
- Add analytics framework (privacy-preserving)
- Create abstraction layer for Live Activity updates
- Consider migrating to SwiftData for persistence
- Add proper state restoration support

## Troubleshooting

### Common Issues
- **Live Activities not appearing**: Check Info.plist configuration and capability settings
- **Push notifications not received**: Verify notification permissions and APNS setup
- **Background updates failing**: Ensure background modes are enabled
- **API connection errors**: Check network connectivity and API endpoint availability

### Debug Tools
- **Xcode Console**: Monitor print statements and system logs
- **Network Link Conditioner**: Test under various network conditions
- **Push Notification Console**: Debug remote notifications
- **Activity Monitor**: Check memory and CPU usage

## Contributing Guidelines

### Code Review Checklist
- [ ] Follows Swift style guide
- [ ] Includes appropriate error handling
- [ ] Updates relevant documentation
- [ ] Adds/updates unit tests
- [ ] Tested on both simulator and device
- [ ] Verified Live Activity functionality
- [ ] Checked accessibility features
- [ ] No force unwraps without justification

### Pull Request Process
1. Create feature branch from `main`
2. Implement changes with clear commits
3. Update CLAUDE.md if architecture changes
4. Test thoroughly on multiple devices
5. Submit PR with detailed description
6. Address review feedback promptly
