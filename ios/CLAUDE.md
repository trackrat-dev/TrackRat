# TrackRat iOS App

## Overview

SwiftUI app for tracking trains across 13 transit systems: NJ Transit, Amtrak, PATH, PATCO, LIRR, Metro-North, NYC Subway, BART, MBTA, Metra, WMATA (DC Metro), and SEPTA (Regional Rail + Metro). Features Live Activities, track predictions (Owl), route alerts with recurring train subscriptions, congestion maps, multi-leg trip search, and Pro subscription.

- **iOS 18.0+** deployment target
- **Xcode 16.0+** required

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
├── App/              # TrackRatApp.swift, ContentView.swift
├── Views/
│   ├── Screens/      # 18 screen-level views
│   ├── Components/   # 28 reusable UI components
│   └── Paywall/      # PaywallView, ProFeatureLockView
├── Models/           # Train, TrainV2, V2APIModels, TrainSystem, TripOption, CompletedTrip, DeepLink
├── Services/         # 15 singleton services
├── Shared/           # Stations, StationData, StationCoordinates, StationDepartures, LiveActivityModels, RouteTopology, RouteShapes, SubwayLines
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
| AlertSubscriptionService | Route alert subscriptions and APNS registration |
| Prefetcher | Warms trip list + train detail caches for instant navigation |
| DeepLinkService | Deep link handling |
| ShareService | Sharing functionality |
| JourneyFeedbackService | Journey feedback |
| TripRecordingService | Trip recording |
| StaticTrackDistributionService | Static track distribution data |
| ThemeManager | Theme management |

## API Endpoints

Base URL: `https://apiv2.trackrat.net/api`

Key endpoints:
- `GET /v2/trains/departures?from=X&to=Y` - Search trains
- `GET /v2/trains/{id}?include_predictions=true` - Train details
- `GET /v2/predictions/track?station_code=X&train_id=Y` - Owl predictions
- `GET /v2/predictions/delay` - Delay/cancellation forecasts
- `GET /v2/routes/congestion` - Network congestion
- `POST /v2/live-activities/register` - Register Live Activity
- `GET /v2/trips/search` - Multi-leg trip search with transfers
- `POST /v2/devices/register` - Register APNS device for route alerts
- `PUT /v2/alerts/subscriptions` - Sync route alert subscriptions
- `GET /v2/alerts/service` - MTA service alerts (planned work, delays)

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

CI: `.github/workflows/ios-ci.yml` builds and runs the test suite on every push/PR touching `ios/` (dynamically selects an available simulator on the macOS runner).

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
- Track/platform prediction shown on the Lock Screen when available (`predictedTrack` / `predictedTrackConfidence`)
- Departure/arrival countdown shown as minute-granular text (`minutesUntilDeparture` / `minutesUntilArrival` on `ContentState`, e.g. "Departing in 5 minutes" / "~5 min"), refreshed by the 30s backend pushes. Deliberately not a seconds-ticking `Text(timerInterval:)` / `.relative` view: the schedule has only minute resolution, so a MM:SS countdown would imply false precision.
- Offline tap: TrainDetailsView renders instantly from `TrainCacheService` even when the entry is stale (`allowStale: true`), overlays the activity's pushed `ContentState` when it is newer than the cache (`TrainV2.applyingLiveActivityState` — departed stops, origin track, cancellation), and shows a `StaleDataBanner` while refreshes keep failing. No stops array is ever pushed through APNs (4KB Live Activity payload cap).

## Testing

Physical device recommended for:
- Push notification testing
- Live Activity behavior
- Performance profiling

## Important Notes

- All timestamps use Eastern Time zone
- Train lookup supports both IDs and train numbers
- `TrainSystem.disabledSystems` (BART, WMATA, MBTA, Metra) hides systems app-wide; use `TrainSystem.availableCases` for any user-facing system list (mirrors backend `TRACKRAT_DISABLED_DATA_SOURCES`). Persisted selections are sanitized on load.
- Pro subscription offers 1-week free trial via Apple introductory offer
- `debugOverrideEnabled` in SubscriptionService controls Pro feature override (defaults to `false`)

---

See `DESIGN.md` for detailed screen documentation, data models, and feature specifications.
