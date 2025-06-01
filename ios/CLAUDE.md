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
- Supports 5 stations: NY Penn, Newark Penn, Trenton, Princeton Junction, Metropark
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
- **Base URL**: `https://trackcast.andymartin.cc/api`
- **JSONDecoder**: Multiple ISO8601 date format support with fractional seconds
- **URLSession**: Native networking with proper timeout handling
- **Error handling**: Typed errors with recovery
- **Eastern Time Zone**: Automatic conversion for all timestamps

### Endpoints Used
- `GET /trains/?from_station_code=X&to_station_code=Y&departure_time_after=Z&limit=N` - Search by origin/destination
- `GET /trains/{id}?from_station_code=X` - Train details filtered by origin
- `GET /trains/{train_number}?from_station_code=X` - Lookup by number with origin filter
- `GET /trains/?train_id=X&no_pagination=true&from_station_code=Y` - Historical data by origin
- `GET /trains/?line=X&limit=1000&from_station_code=Y` - Line history by origin
- `GET /trains/?destination=X&limit=1000&from_station_code=Y` - Destination history by origin
- `GET /consolidated_trains/{train_id}` - Consolidated train data with multi-source support

### New API Features
- **Consolidated Train Data**: Merges data from multiple sources (Amtrak, NJTransit)
- **Real-time Position**: Current train location with segment progress
- **Enhanced Track Assignment**: Source attribution for track predictions
- **Flexible Train Lookup**: Support for both numeric IDs and train numbers

## Data Models

### Core Types
- **Train**: Main model with comprehensive train data
  - Extensions for origin-based departure time calculation
  - Methods: `getDepartureTime(fromStationCode:)`, `getFormattedDepartureTime(fromStationCode:)`
  - Live Activity support: `toActivityAttributes()`, `toContentState()`
  - New fields: `originStation`, `dataSource`, `currentPosition`, `trackAssignment`
  - Status summary with delay information
  - Consolidation metadata for multi-source trains
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
- **Bundle Identifier**: `com.andymartin.TrackRat`
- **Development Team**: Set in Xcode project settings
- **Code Signing**: Automatic with development certificate
- **Capabilities**: 
  - Push Notifications
  - Background Modes (Background fetch, Remote notifications)

### Development Commands
```bash
# Open project
open TrackRat.xcodeproj

# Build for simulator
xcodebuild -scheme TrackRat -sdk iphonesimulator

# Build for device
xcodebuild -scheme TrackRat -sdk iphoneos

# Run tests
xcodebuild test -scheme TrackRat -destination 'platform=iOS Simulator,name=iPhone 15'

# Archive for distribution
xcodebuild archive -scheme TrackRat -archivePath ./build/TrackRat.xcarchive
```

### Testing Live Activities
- Use LiveActivityDebugView for testing different states
- Simulator supports Live Activities from iOS 16.1+
- Physical device recommended for push notification testing
- Use Console.app to debug Live Activity updates

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

## Future Considerations

### Planned Features
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