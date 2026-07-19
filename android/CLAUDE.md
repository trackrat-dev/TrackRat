# TrackRat Android

## Java Setup (Required)

```bash
# macOS (Homebrew)
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
export PATH=$JAVA_HOME/bin:$PATH

# Linux
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PATH=$JAVA_HOME/bin:$PATH
```

## Quick Start

```bash
cd android

# Build debug APK
./gradlew assembleDebug -x test

# Install on device/emulator
./gradlew installDebug

# Run tests
./gradlew test

# Clean and rebuild
./gradlew clean build
```

APK output: `app/build/outputs/apk/debug/app-debug.apk`

## Architecture

### Tech Stack
- **Kotlin** (100%, no Java)
- **Jetpack Compose** (declarative UI)
- **MVVM** with Unidirectional Data Flow
- **Google Maps SDK** with Compose integration
- **Hilt** for dependency injection
- **Retrofit2 + OkHttp3 + Moshi** for networking
- **Kotlin Coroutines + Flow** for async
- **DataStore Preferences** for local storage
- **Material3** with custom theming

### Project Structure

```
android/app/src/main/java/com/trackrat/android/
├── MainActivity.kt              # Single activity entry point
├── TrackRatApp.kt              # Application class with Hilt
├── data/
│   ├── api/                    # Retrofit API interface, adapters (HtmlEntityDecoder, ZonedDateTimeAdapter)
│   ├── mappers/                # TrainMappers
│   ├── models/                 # Data models (TrainV2, StatusV2, etc.)
│   ├── preferences/            # DataStore preferences, EnvironmentManager
│   ├── repository/             # Data repository pattern
│   ├── services/               # TrackPrediction, BackendHealth
│   └── Stations.kt             # Station data with LatLng (used by the map; a second list, models/Stations.kt, matches iOS — known duplication)
├── di/                         # Hilt DI modules
├── navigation/                 # TrackRatDestinations, Navigator
├── services/                   # TrainTrackingService, RatSense, Notifications, TrackingStateRepository, TrainUpdateReceiver
├── ui/
│   ├── advanced/               # Advanced config screen
│   ├── components/             # Reusable UI (BottomSheet, Loading, etc.)
│   ├── destinationselection/   # Destination picker
│   ├── favorites/              # Favorite stations
│   ├── map/                    # MapContainerScreen, MapContainerViewModel, PolylineHitDetector
│   ├── onboarding/             # Onboarding flow
│   ├── profile/                # Settings screens, components/ (ProfileActionRow, ProfileSectionCard)
│   ├── stationselection/       # Origin picker
│   ├── theme/                  # Material3 theme, colors, typography
│   ├── traindetail/            # Journey details
│   └── trainlist/              # Departure list
└── utils/                      # Constants, HapticFeedbackHelper, ShareService, ErrorUtils
```

## API Integration

**Base URL**: `https://apiv2.trackrat.net/api/v2/`

Key endpoints:
- `GET /trains/departures?from={from}&to={to}` - Departures
- `GET /trains/{trainId}?date={date}` - Train details
- `GET /predictions/track?station_code={code}&train_id={trainId}&journey_date={date}` - Track predictions
- `GET /routes/congestion` - Network congestion

All times are Eastern Time (handled by `ZonedDateTimeAdapter`).

## Key Models

| Model | Purpose |
|-------|---------|
| TrainV2 | Train list with V2 fields |
| TrainDetailV2 | Full journey data |
| DepartureV2 | Enhanced departure with position |
| StatusV2 | Status with location context |
| Progress | Journey tracking (duplicated as `ProgressV2` in TrainDetailV2.kt — known model confusion) |
| PlatformPrediction | ML platform predictions |
| CongestionSegment | Network congestion |

## UI Architecture

- `MapContainerScreen`: Root with Google Maps + draggable bottom sheet
- Bottom sheet contains `NavHost` with all screens
- Sheet positions: MEDIUM (50%) and EXPANDED (100%)
- 30-second auto-refresh on train list

**Screen Flow**: Map → Station Selection → Destination → Train List → Train Detail

## Critical Patterns

### Bottom Sheet Gestures
- `BottomSheetDragState`: Shared gesture state machine
- `DraggableBottomSheet`: Low-level gesture capture
- `SheetAwareScrollView`: Smart scroll coordination
- "One swipe = one action" pattern matching iOS

### Ongoing Notifications
- `TrainTrackingService`: Foreground service
- 30-second updates via AlarmManager
- Custom notification layouts
- Auto-stop on arrival

### StatusV2 Display
Always prefer `statusV2?.enhancedStatus` over `status` when available.

## Code Style

```kotlin
// Classes: PascalCase
class TrainListViewModel

// Functions: camelCase
fun loadDepartures()

// Constants: UPPER_SNAKE_CASE
const val MAX_RETRY_COUNT = 3

// Composables: PascalCase
@Composable
fun TrainListItem()
```

### Compose Best Practices
- Use `remember` for expensive computations
- Add `key` parameter to LazyColumn items
- Collect state with `collectAsState()`
- Hoist state up for testability

## Design System

- Orange accent color (`Constants.BRAND_ORANGE`)
- Material3 with custom theming
- Dark mode map styling (`dark_map_style.json`)
- Glassmorphic cards matching iOS
- 48dp minimum touch targets

## Implementation Status

**Working:**
- Map-based UI with congestion overlay
- Bottom sheet gesture coordination
- 9 main screens with navigation
- API integration (departures, details, predictions)
- 30-second auto-refresh
- Ongoing notifications
- Station favorites
- Track predictions (segmented bar)

**Not Implemented:**
- Push notifications (FCM)
- Home screen widgets

---

See `DESIGN.md` for detailed implementation specs, troubleshooting, and enhancement roadmap.
