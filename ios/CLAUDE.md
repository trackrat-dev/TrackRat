# TrackRat iOS App - Design Documentation

## Overview

TrackRat iOS is a comprehensive SwiftUI app for tracking train departures from multiple origin stations in the NJ Transit and Amtrak network. The app features Live Activities for real-time train tracking on the Lock Screen and Dynamic Island, intelligent track predictions via the Owl system, and historical analytics. Built with iOS 17.0+ and leveraging the latest iOS features including ActivityKit, push notifications, and consolidated train data APIs.

## Architecture

### Core Stack
- **SwiftUI**: Modern declarative UI framework (iOS 17.0+)
- **ActivityKit**: Live Activities and Dynamic Island support (iOS 16.1+)
- **UserNotifications**: Push notifications for Live Activity updates
- **Combine**: Reactive data flow with automatic UI updates
- **Async/Await**: Clean asynchronous API calls
- **MVVM Pattern**: ViewModels for complex screens

### State Management
- **@StateObject AppState**: Global app state for navigation, user data, and Live Activities
- **@EnvironmentObject**: Dependency injection throughout view hierarchy
- **NavigationPath**: Type-safe navigation stack with flexible train details
- **@Published properties**: Automatic UI updates on state changes
- **UNUserNotificationCenterDelegate**: Foreground notification handling

## Screen Architecture

### 1. **TripSelectionView** (Start Screen)
- Shows active Live Activities at the top with journey progress
- Recent trips list with quick selection
- "Add New Trip" button for new journeys
- "Search by Train Number" for direct lookup
- Glassmorphism design with dark mode preference
- Orange accent color throughout

### 2. **DeparturePickerView**
- Origin station selection for departures
- Primary stations: NY Penn, Newark Penn, Trenton, Princeton Junction, Metropark
- Additional Southeast Amtrak stations: Charlotte, Raleigh, Atlanta, Miami, Jacksonville, Tampa, Orlando, and more
- Total station coverage: ~144 stations (up from ~100)
- Glassmorphism cards with owl background
- Navigates to destination picker after selection

### 3. **DestinationPickerView** 
- Recent destinations with UserDefaults persistence
- Real-time search with Stations.search()
- Shows selected departure station in header
- Haptic feedback on selection
- Gradient background with glassmorphism

### 4. **TrainListView**
- 30-second auto-refresh with Timer.publish
- Pull-to-refresh gesture
- Boarding status highlighting with orange theme
- Owl predictions inline with Live Activity controls
- Origin-based departure time display
- Train deduplication by train_id
- Shows departure and destination in header
- Live Activity toggle buttons for each train

### 5. **TrainDetailsView**
- Real-time status updates with consolidated train data
- Journey visualization with stop indicators
- Boarding state with orange theming
- Modal sheet for historical data
- Origin-aware timing display
- Live Activity controls with start/stop functionality
- Background refresh when Live Activity is active
- Flexible navigation support (by ID or train number)

### 6. **HistoricalDataView**
- Delay performance bars
- Track usage visualization
- Three-tier analytics (train/line/destination)
- Origin-filtered historical data
- Modal presentation from train details

### 7. **TrainNumberSearchView**
- Direct train lookup by number
- Origin-aware search results
- Integrated into home screen flow

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
- **Base URL**: `https://prod.api.trackrat.net/api`
- **JSONDecoder**: Multiple ISO8601 date format support with fractional seconds
- **URLSession**: Native networking with proper timeout handling
- **Error handling**: Typed errors with recovery
- **Eastern Time Zone**: Automatic conversion for all timestamps

### Endpoints Used (V2 API)
- `GET /v2/trains/departures?from=X&to=Y&limit=50` - Search trains between stations
- `GET /v2/trains/{train_id}?date=YYYY-MM-DD&refresh=true` - Train details with optional forced refresh
- `GET /v2/routes/history?from_station=X&to_station=Y&data_source=NJT&days=30` - Route historical performance data
- `POST /v2/live-activities/register` - Register Live Activity for updates
- `DELETE /v2/live-activities/{push_token}` - Unregister Live Activity

### New API Features
- **Consolidated Train Data**: Merges data from multiple sources (Amtrak, NJTransit)
- **Real-time Position**: Current train location with segment progress
- **Enhanced Track Assignment**: Source attribution for track predictions
- **Flexible Train Lookup**: Support for both numeric IDs and train numbers

## Data Models

### Core Types
- **TrainV2**: Main model with comprehensive train data (current implementation)
  - Extensions for origin-based departure time calculation
  - Methods: `getScheduledDepartureTime(fromStationCode:)`, `getFormattedScheduledDepartureTime(fromStationCode:)`
  - Live Activity support: `toActivityAttributes()`, `toContentState()`
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
  - `.trainDetailsFlexible(trainNumber: String, fromStation: String?)`
  - Support for both train IDs and train numbers

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

### Historical Types
- **DelayStats**: Performance percentages
- **TrackStats**: Usage distribution
- **HistoricalData**: Combined analytics

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

### New UI Components
- **ActiveTripsSection**: Horizontal scroll of active Live Activities with progress indicators
- **LiveActivityControls**: Start/stop buttons with status indicators
- **LiveActivityDebugView**: Developer tools for testing states
- **Glassmorphic Cards**: Consistent card styling with backdrop blur

### Extensions & Utilities
- **Color+Hex**: Initialize colors from hex strings
- **DateFormatter+Eastern**: Eastern Time zone formatting
- **View+GlassmorphicNavBar**: Custom navigation bar styling

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

## Services

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
- **Consolidated Train Support**: New endpoints for multi-source data
- **Flexible Lookups**: Support for both train IDs and numbers
- **Date Handling**: Multiple ISO8601 formats with fractional seconds
- **Eastern Time Zone**: Automatic conversion for all timestamps
- **Error Recovery**: Typed errors with user-friendly messages

## Accessibility

- Dynamic Type support throughout
- Semantic colors for status indicators
- VoiceOver labels on interactive elements
- High contrast borders for visibility

## Security & Privacy

- No user tracking or analytics
- Local storage only for user preferences and recent trips
- Push notifications only for active Live Activities
- No external dependencies or third-party SDKs
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
- iOS 17.0+ deployment target
- Swift 5.9+
- macOS 14.0+ for development

### Build Configuration
- **Bundle Identifier**: `net.trackrat.TrackRat`
- **Development Team**: Set in Xcode project settings
- **Code Signing**: Automatic with development certificate
- **Capabilities**: 
  - Push Notifications
  - Background Modes (Background fetch, Remote notifications)

### Development Commands
```bash
# Open project
open TrackRat.xcodeproj

# Build for simulator (complete build with destination)
xcodebuild -scheme TrackRat -sdk iphonesimulator build -destination 'platform=iOS Simulator,name=iPhone 16'

# Build for simulator (basic build)
xcodebuild -scheme TrackRat -sdk iphonesimulator

# Build for device
xcodebuild -scheme TrackRat -sdk iphoneos

# Check for compilation errors only
xcodebuild -scheme TrackRat -sdk iphonesimulator build -destination 'platform=iOS Simulator,name=iPhone 16' 2>&1 | grep -E "(error|failed|BUILD FAILED)" || echo "BUILD SUCCESSFUL"

# Run tests
xcodebuild test -scheme TrackRat -destination 'platform=iOS Simulator,name=iPhone 16'

# Archive for distribution
xcodebuild archive -scheme TrackRat -archivePath ./build/TrackRat.xcarchive

# Note: Use iPhone 16 instead of iPhone 15 as it's available in current simulators
# Available destinations can be checked with: xcodebuild -scheme TrackRat -showdestinations
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

## Code Conventions

### Swift Style Guide
- **Naming**: Clear, descriptive names following Swift API Design Guidelines
- **Access Control**: Explicit `private` for non-public members
- **Force Unwrapping**: Avoided except for IBOutlets and guaranteed non-nil values
- **Optionals**: Prefer `guard let` and `if let` for unwrapping
- **Comments**: Document complex logic and public APIs

### SwiftUI Best Practices
- **View Composition**: Small, focused views composed together
- **State Management**: Use appropriate property wrappers (@State, @StateObject, etc.)
- **Modifiers**: Order matters - apply in logical sequence
- **Previews**: Provide meaningful preview data for all views

### Project Organization
- **Views/**: All SwiftUI views organized by feature
- **Models/**: Data models and extensions
- **Services/**: Singletons and service classes
- **ViewModels/**: Complex screen logic separated from views
- **Utilities/**: Helper functions and extensions
- **Resources/**: Assets, Info.plist, and other resources

## Recent Enhancements

### New Features Not Previously Documented

#### Penn Station Navigation Guide (PennStationGuideView)
Interactive guide helping users navigate Penn Station efficiently:
- **YouTube Integration**: Embedded video guides with thumbnails
- **Swipeable Cards**: Step-by-step navigation instructions
- **Platform-Specific**: Separate guides for NJ Transit and Amtrak
- **Visual Aids**: Station photos showing exact locations
- **Amtrak Guide**: West End Concourse strategy via Moynihan Hall
- **NJ Transit Guide**: 7th Avenue sub-level Exit Concourse approach

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
- **BottomSheetView**: Draggable bottom sheet with multiple positions
- **SheetAwareScrollView**: Smart scrolling that coordinates with bottom sheets
- **TrackRatLoadingView**: Custom loading animation
- **VideoPlayerView**: Native video playback for onboarding
- **YouTubeLinkView**: YouTube video embedding with thumbnails
- **TrackRatMascot**: Animated mascot character
- **JourneyCongestionMapView**: Visual congestion mapping

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
- **Additional Transit Systems**: LIRR, Metro-North, SEPTA, PATH integration
- **Widget Extension**: Home/Lock Screen widgets for favorite routes
- **Apple Watch App**: Companion app with Live Activity sync
- **Siri Shortcuts**: Quick access to frequent trips
- **Offline Mode**: Core Data caching for reliability
- **Remote Push Notifications**: Server-side Live Activity updates
- **Interactive Notifications**: Quick actions from alerts
- **CarPlay Support**: Hands-free train tracking

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
4. **Analytics**: No usage tracking for feature improvement
5. **Crash Reporting**: No automated crash collection

### Code Quality Issues
1. **Test Coverage**: <10% test coverage across the codebase
2. **Documentation**: Many complex functions lack documentation
3. **Magic Numbers**: Hard-coded values throughout (timeouts, delays, sizes)
4. **Code Duplication**: Similar logic repeated in multiple views
5. **SwiftLint**: No linting rules enforced

### Security Concerns
1. **API Keys**: No certificate pinning for API calls
2. **Token Storage**: Push tokens stored in memory without encryption
3. **Deep Links**: No validation of deep link parameters

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
