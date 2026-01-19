# TrackRat iOS App 🚂

A comprehensive iOS app for tracking NJ Transit, Amtrak, PATH, and PATCO trains with Live Activities, real-time updates, intelligent track predictions, and innovative navigation features.

## 🎯 Key Features

### Live Activities & Real-time Tracking
- **Lock Screen Integration**: Real-time train tracking on Lock Screen and Dynamic Island
- **Push Notifications**: Automatic updates for boarding, delays, and arrivals
- **30-Second Refresh**: Continuous background updates while tracking
- **Smart Auto-End**: Automatically ends tracking when journey completes

### Multi-Station Support
- **Primary Hubs**: NY Penn, Newark Penn, Trenton, Princeton Junction, Metropark
- **Southeast Corridor**: 44+ Amtrak stations across NC, SC, GA, FL, VA, WV
- **Total Coverage**: ~144 stations across the Eastern United States
- **Train Services**: NJ Transit, Amtrak (Silver Star, Silver Meteor, Carolinian, Piedmont, Crescent), PATH, PATCO

### Intelligent Features
- **🦉 Owl Track Predictions**: AI-powered track predictions with confidence levels
- **🐀 RatSense Journey Suggestions**: Learns your travel patterns and suggests likely trips
- **Penn Station Navigation Guide**: Interactive video guides for efficient navigation
- **Historical Analytics**: Performance data, delay statistics, and track usage patterns
- **Map Layer Controls**: Toggleable congestion, routes, and station markers on map
- **GTFS Future Schedules**: View train schedules for future dates via GTFS data

### Pro Subscription Features
- **Congestion Maps**: Premium map overlay showing network congestion levels
- **StoreKit 2 Integration**: Modern subscription management

### User Experience
- **Native iOS Design**: SwiftUI with glassmorphism and smooth animations
- **Haptic Feedback**: Tactile responses for important interactions
- **Pull-to-Refresh**: Natural gesture support throughout
- **Deep Linking**: Direct access to trains and journeys from external apps
- **Offline Support**: Recent trips and favorites available without connection

## 📱 Screenshots & UI

### Design Philosophy
- **Dark Mode First**: Optimized for low-light viewing at stations
- **Orange Accent**: Consistent branding with high visibility
- **Glassmorphism**: Modern translucent design elements
- **Progressive Disclosure**: Complex features revealed as needed

## 🏗️ Architecture

### Technology Stack
- **Language**: Swift 5.9+
- **UI Framework**: SwiftUI (iOS 17.0+)
- **Concurrency**: Swift Async/Await
- **Reactive**: Combine framework
- **Activities**: ActivityKit for Live Activities
- **Notifications**: UserNotifications framework
- **Networking**: URLSession with custom decoders

### Design Patterns
- **MVVM Architecture**: Clear separation of concerns
- **Singleton Services**: Shared instances for API, storage, and activities
- **Observable Pattern**: @Published properties for reactive UI
- **Dependency Injection**: EnvironmentObject for app-wide state

### Project Structure
```
TrackRat/
├── App/                         # Application lifecycle
│   ├── TrackRatApp.swift       # Main entry point, push handling
│   └── ContentView.swift        # Root navigation controller
│
├── Models/                      # Data layer
│   ├── TrainV2.swift           # Pure data model with context-aware calculations
│   ├── V2APIModels.swift       # Backend V2 API models
│   ├── DeepLink.swift          # URL scheme handling
│   └── Train.swift             # Legacy compatibility model
│
├── Services/                    # Business logic (12 services)
│   ├── APIService.swift        # Network communication
│   ├── LiveActivityService.swift # Live Activity management
│   ├── RatSenseService.swift   # AI journey predictions
│   ├── BackendWakeupService.swift # Backend health management
│   ├── StorageService.swift    # Local persistence
│   ├── DeepLinkService.swift   # URL routing
│   ├── ShareService.swift      # Social sharing
│   ├── TrainCacheService.swift # Two-tier train caching with LRU
│   ├── ThemeManager.swift      # Theme configuration
│   ├── SubscriptionService.swift # Pro subscription management
│   ├── TripRecordingService.swift # Trip statistics tracking
│   └── StaticTrackDistributionService.swift # Track analytics
│
├── Views/                       # UI layer
│   ├── Screens/                # Full-screen views (12 screens)
│   │   ├── TripSelectionView.swift      # Home screen with search
│   │   ├── DeparturePickerView.swift    # Origin station selection
│   │   ├── DestinationPickerView.swift  # Destination selection
│   │   ├── TrainListView.swift          # Departure board
│   │   ├── TrainDetailsView.swift       # Train journey details
│   │   ├── PennStationGuideView.swift   # Navigation assistance
│   │   ├── CongestionMapView.swift      # Network congestion
│   │   ├── HistoricalDataView.swift     # Performance analytics
│   │   ├── MyProfileView.swift          # User settings
│   │   ├── MapContainerView.swift       # Primary map interface
│   │   ├── OnboardingView.swift         # User onboarding
│   │   └── AdvancedConfigurationView.swift # Developer settings
│   │
│   └── Components/              # Reusable UI components (16 files)
│       ├── ActiveTripsSection.swift     # Live Activity cards
│       ├── LegacyBottomSheetView.swift  # Draggable sheets
│       ├── LegacySheetAwareScrollView.swift # Coordinated scrolling
│       ├── LiveActivityControls.swift   # Start/stop buttons
│       ├── LiveActivityDebugView.swift  # Debug tools
│       ├── TrackRatMascot.swift         # Animated character
│       ├── FeedbackButton.swift         # Issue reporting
│       ├── OperationsSummaryView.swift  # Operations summary
│       ├── TrainStatsSummaryView.swift  # Train performance
│       └── TrainDistributionChart.swift # Delay visualization
│
├── Shared/                      # Cross-target code
│   ├── Stations.swift          # Station database
│   ├── LiveActivityModels.swift # Widget shared types
│   └── RouteTopology.swift      # Route definitions for map layers
│
├── Theme/                       # Visual design
│   └── TrackRatTheme.swift     # Colors and styles
│
├── Utilities/                   # Helper code
│   ├── Extensions.swift         # Swift extensions
│   └── Logger.swift            # Debug logging framework
│
└── TrainLiveActivityExtension/  # Widget extension
    ├── TrainLiveActivityBundle.swift
    └── LiveActivityWidget.swift

TrackRatTests/                   # Test suite
├── BuildTests.swift            # Build verification
├── Models/                     # Model tests
├── Services/                   # Service tests
├── ViewModels/                 # ViewModel tests
├── TestUtilities/              # Test helpers
└── TestFixtures/               # JSON fixtures
```

## 🚀 Getting Started

### Prerequisites
- macOS 14.0+ (Sonoma or later)
- Xcode 15.0+
- iOS 17.0+ deployment target
- Apple Developer account (for device testing)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/TrackRat.git
   cd TrackRat/ios
   ```

2. **Open in Xcode**
   ```bash
   open TrackRat.xcodeproj
   ```

3. **Configure signing**
   - Select the TrackRat target
   - Choose your development team
   - Update bundle identifier if needed

4. **Build and run**
   - Select target device/simulator
   - Press ⌘R to build and run

### Configuration

#### API Endpoints
The app connects to the TrackRat backend API. Configure in `APIService.swift`:
- **Production**: `https://apiv2.trackrat.net/api`
- **Development**: `http://localhost:8000/api`

#### Push Notifications
For Live Activities with push updates:
1. Enable Push Notifications capability
2. Configure APNS certificates
3. Backend must have matching certificates

## 🧪 Testing

### Unit Tests
```bash
xcodebuild test -scheme TrackRat -destination 'platform=iOS Simulator,name=iPhone 16'
```

### UI Tests
Limited UI tests available. Run from Xcode Test Navigator.

### Manual Testing Checklist
- [ ] Live Activity starts and updates correctly
- [ ] Push notifications received in background
- [ ] Deep links open correct screens
- [ ] RatSense suggestions appear appropriately
- [ ] Penn Station guide videos play
- [ ] Historical data loads and displays
- [ ] Search functionality works for stations and trains
- [ ] Favorite stations persist across launches

## 🐛 Known Issues

### Critical Bugs
1. **Memory Management**: Potential retain cycles in Live Activity push subscriptions
2. **Background Tasks**: Incomplete error handling in background refresh
3. **Race Conditions**: Concurrent train validation not properly synchronized

### Performance Issues
1. **Search Performance**: O(n) station search on every keystroke
2. **Image Loading**: Synchronous video thumbnail loading blocks UI
3. **API Redundancy**: Some views make duplicate network requests

### UI/UX Issues
1. **VoiceOver Support**: Limited accessibility in custom components
2. **iPad Support**: Not optimized for larger screens
3. **Landscape Mode**: Layout issues in landscape orientation

See [CLAUDE.md](CLAUDE.md) for complete technical details and improvement areas.

## 🔧 Development

### Code Style
- Follow Swift API Design Guidelines
- Use SwiftLint for consistency (configuration pending)
- Prefer value types over reference types
- Use `async/await` for asynchronous code

### Debugging Tips
1. **Live Activities**: Use `LiveActivityDebugView` for testing states
2. **Push Notifications**: Monitor Console.app for APNS logs
3. **Network Requests**: Enable network debugging in Xcode
4. **Memory Leaks**: Use Instruments to detect retain cycles

### Contributing
1. Create feature branch from `main`
2. Make changes with clear commits
3. Add/update tests as needed
4. Update documentation
5. Submit pull request with description

## 📊 Analytics & Monitoring

### Current Implementation
- Basic console logging for debugging
- No third-party analytics SDKs
- Privacy-first approach

### Future Considerations
- Anonymous usage statistics
- Crash reporting integration
- Performance monitoring
- User feedback system

## 🔐 Security & Privacy

### Data Protection
- **No User Accounts**: No personal data stored
- **Local Storage Only**: Preferences in UserDefaults
- **No Tracking**: No analytics or advertising SDKs
- **Secure Communication**: HTTPS for all API calls

### Permissions Required
- **Notifications**: For Live Activity updates (optional)
- **Background App Refresh**: For Live Activity updates

## 🚢 Deployment

### App Store Release
1. Update version and build numbers
2. Archive in Xcode (Product → Archive)
3. Upload to App Store Connect
4. Submit for review with screenshots

### TestFlight Beta
1. Archive and upload as above
2. Add external testers in App Store Connect
3. Submit beta for review

## 📈 Future Roadmap

### Near Term (v2.x)
- [ ] Widget Extension for Home Screen
- [ ] Apple Watch companion app
- [ ] Offline mode with caching
- [ ] Siri Shortcuts integration
- [ ] Improved accessibility

### Long Term (v3.x)
- [ ] iPad optimization
- [ ] macOS Catalyst app
- [ ] CarPlay support
- [ ] Additional transit systems (LIRR, Metro-North, SEPTA)
- [ ] Social features (trip sharing)

## 📝 License

Copyright © 2024 TrackRat. All rights reserved.

## 🤝 Acknowledgments

- NJ Transit for API access
- Amtrak for public data
- Open source Swift community
- Beta testers and early users

## 📧 Contact

For questions or support:
- GitHub Issues: [Report bugs](https://github.com/yourusername/TrackRat/issues)
- Email: support@trackrat.net

---

Made with ❤️ for commuters by commuters