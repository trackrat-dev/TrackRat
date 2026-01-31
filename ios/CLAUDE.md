# TrackRat iOS App

## Overview

SwiftUI app for tracking NJ Transit, Amtrak, PATH, and PATCO trains. Features Live Activities, track predictions (Owl), and Pro subscription.

- **iOS 18.0+** deployment target
- **Xcode 15.0+** required

## Architecture

### Core Stack
- **SwiftUI** with MVVM embedded in view files (no separate ViewModel files)
- **ActivityKit** for Live Activities and Dynamic Island
- **Combine** + async/await for data flow
- **MapKit** for congestion visualization

### State Management
- `@StateObject AppState` for global state
- `@EnvironmentObject` for dependency injection
- `NavigationPath` for type-safe navigation
- Singleton services pattern (`APIService.shared`, `LiveActivityService.shared`)

## Project Structure

```
TrackRat/
├── App/              # TrackRatApp.swift, AppState
├── Views/
│   ├── Screens/      # All screen-level views
│   └── Components/   # Reusable UI components
├── Models/           # Data models, API responses, DeepLink
├── Services/         # 13 singleton services
├── Shared/           # Stations.swift, LiveActivityModels
├── Theme/            # TrackRatTheme.swift
├── Utilities/        # Extensions.swift, Logger.swift
└── Resources/        # Assets, Info.plist
TrainLiveActivityExtension/  # Live Activity widget
TrackRatTests/               # Unit tests
```

## Key Services

| Service | Purpose |
|---------|---------|
| APIService | V2 API calls, date handling, environment switching |
| LiveActivityService | Live Activity lifecycle, background updates |
| StorageService | UserDefaults wrapper, migration support |
| RatSenseService | AI journey predictions |
| TrainCacheService | Two-tier caching with LRU eviction |
| SubscriptionService | StoreKit 2 Pro subscription |
| BackendWakeupService | Health checks with 15-min cache |

## API Endpoints

Base URL: `https://apiv2.trackrat.net/api`

Key endpoints:
- `GET /v2/trains/departures?from=X&to=Y` - Search trains
- `GET /v2/trains/{id}?include_predictions=true` - Train details
- `GET /v2/predictions/track?station_code=X&train_id=Y` - Owl predictions
- `GET /v2/routes/congestion` - Network congestion
- `POST /v2/live-activities/register` - Register Live Activity

## Development Commands

```bash
# Open project
open TrackRat.xcodeproj

# Build for simulator
xcodebuild -scheme TrackRat -sdk iphonesimulator build \
  -destination 'platform=iOS Simulator,name=iPhone 16'

# Run tests
xcodebuild test -scheme TrackRat \
  -destination 'platform=iOS Simulator,name=iPhone 16'

# Check for errors only
xcodebuild -scheme TrackRat -sdk iphonesimulator build \
  -destination 'platform=iOS Simulator,name=iPhone 16' 2>&1 \
  | grep -E "(error|failed|BUILD FAILED)" || echo "BUILD SUCCESSFUL"
```

## Code Conventions

### Swift Style
- Clear, descriptive names following Swift API Design Guidelines
- Explicit `private` for non-public members
- Avoid force unwrapping - use `guard let` / `if let`
- Document complex logic and public APIs

### SwiftUI Patterns
- Small, focused views composed together
- ViewModels embedded in view files
- Meaningful preview data for all views

### Design System
- Dark mode preferred (`.preferredColorScheme(.dark)`)
- Orange accent color (`.tint(.orange)`)
- Purple gradient (#667eea → #764ba2)
- `.ultraThinMaterial` for glass effects
- 16pt spacing grid

## Key Models

- **TrainV2**: Main train model with origin-based departure times
- **Stop**: Station with times and departure confirmations
- **JourneyProgress**: Real-time position tracking
- **NavigationDestination**: Type-safe navigation enum

## Live Activities

- Background updates every 30 seconds
- Auto-end on arrival or 15 minutes of no updates
- Push notifications for status changes
- Journey progress with interpolation

## Testing

Physical device recommended for:
- Push notification testing
- Live Activity behavior
- Performance profiling

Use `LiveActivityDebugView` for testing Live Activity states in simulator.

## Important Notes

- All timestamps use Eastern Time zone
- Train lookup supports both IDs and train numbers
- Pro subscription has 16-hour preview period for new users
- `debugOverrideEnabled = true` gives all users Pro features during soft launch

---

See `DESIGN.md` for detailed screen documentation, data models, and feature specifications.
