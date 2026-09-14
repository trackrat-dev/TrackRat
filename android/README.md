   # TrackRat Android Application

## Current Implementation Status

### ✅ Completed Features

#### Core Architecture
- **Modern Kotlin + Jetpack Compose**: Fully native implementation using latest Android technologies
- **MVVM Architecture**: Clean separation of concerns with ViewModels and repositories
- **Dependency Injection**: Hilt setup for maintainable dependency management
- **Navigation**: Compose Navigation with proper deep linking support
- **Material3 Design**: Modern Material You theming with dark mode support

#### API Integration
- **Retrofit + Moshi**: Robust networking stack with proper JSON parsing
- **V2 API Endpoints**: Correctly configured for production backend (https://apiv2.trackrat.net/api/v2/)
- **Custom DateTime Adapter**: Proper handling of Eastern Time zone with ZonedDateTime
- **Error Handling**: ApiResult wrapper for consistent error management
- **Network Logging**: Debug logging for API calls in development builds

#### Data Models
- **Complete V2 Models**: TrainV2, StatusV2, Progress, PredictionData, Stop models matching backend
- **Response Models**: DeparturesResponse, TrainDetailsResponse for API responses
- **Station Data**: Major NJ Transit stations (NY, NP, TR, PJ, MP) plus Amtrak stations (`data/Stations.kt` for coordinates, `data/models/Stations.kt` for the picker lists). PATH, PATCO and the other systems the backend serves are not in the Android tree yet.
- **Proper Field Mapping**: JSON annotations for snake_case to camelCase conversion

#### User Interface
- **Station Selection Screen**: 
  - Origin/destination selection with recent trips
  - Search by train number functionality
  - Material3 cards with proper theming
  - Recent destinations persistence

- **Train List Screen**:
  - Pull-to-refresh support
  - 30-second auto-refresh timer
  - Loading skeletons and error states
  - Train deduplication by ID
  - Origin-based departure time display
  - Track predictions ("Owl") display ready

- **Train Detail Screen**:
  - Journey visualization with stops
  - Real-time status updates
  - Progress indicators
  - Support for both train IDs and numbers

#### User Experience
- **Haptic Feedback**: Tactile responses on user interactions
- **User Preferences**: DataStore for persisting user settings and recent trips
- **Loading States**: Shimmer effects and skeleton screens
- **Error Handling**: Graceful error states with retry options
- **Theme**: Orange accent color matching iOS app

### 🚀 Partially Implemented Features

#### Journey Progress
- ✅ Progress bars in train list
- ✅ Stop count display
- ✅ Minutes remaining calculation
- ⚠️ Model confusion (Progress vs ProgressV2)
- ❌ Full journey visualization incomplete

#### Track Predictions (Owl)
- ✅ Confidence-based UI styling
- ✅ Display in train list
- ❌ Not available in train details
- ❌ Platform aggregation not shown

#### StatusV2 Integration
- ✅ Basic enhanced status display
- ✅ Boarding detection logic
- ❌ Location context not utilized
- ❌ Status history not tracked

### ❌ Not Yet Implemented

1. **Push Notifications** (FCM) - not needed yet
2. **Route History Screen** - backend endpoint exists, UI not built
3. **Home Screen Widgets** (Glance API)
4. **Offline Mode** - no local caching

## Getting Started - Development Setup

### Prerequisites

1. **Android Studio**: Latest stable version (Hedgehog or newer)
2. **JDK**: Version 17 or higher
3. **Android SDK**: API 34 (Android 14)
4. **Git**: For version control
5. **Maps**: Will need a Google Cloud Account with a configured Maps API Key

### Initial Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/trackrat-dev/TrackRat.git
   cd TrackRat/android
   ```

2. **Open in Android Studio**
   - File → Open → Select the `android` folder
   - Let Gradle sync complete

3. **Configure local development (optional)**
   
   `NetworkModule.kt` has no hardcoded base URL — it resolves one at runtime from
   `EnvironmentManager`, and the cases live in `data/models/ServerEnvironment.kt`
   (`LOCAL` is already `http://10.0.2.2:8000/api/v2/`, the emulator's host loopback).
   Debug builds set `ALLOW_ENVIRONMENT_SWITCHING = true`, so switch environments in
   the app. For anything else, edit the `API_BASE_URL` buildConfigField in
   `app/build.gradle.kts`:
   ```kotlin
   buildConfigField("String", "API_BASE_URL", "\"http://YOUR_LOCAL_IP:8000/api/v2/\"")
   ```
   A cleartext `http://` host other than the ones already listed will be **blocked**:
   `res/xml/network_security_config.xml` sets `cleartextTrafficPermitted="false"` in its
   `base-config`, and only names `localhost`, `10.0.2.2` and `127.0.0.1` as cleartext
   exceptions. The `10.0.0.0/8` and `192.168.0.0/16` entries beside them are `<domain>`
   values, which Android matches as literal hostnames, not CIDR ranges — they do **not**
   whitelist a real LAN address like `192.168.1.10`. To reach a physical device on the
   LAN, either serve the backend over HTTPS or add that exact IP as its own `<domain>`
   entry in the cleartext `domain-config`.
   
4. ** Add Google Maps API Key **
    - Navigate to local.properties
    - Add a key `maps.apiKey=` (the Gradle property name; `mapsApiKey` is only the
      manifest placeholder it feeds, and a `local.properties` entry by that name is
      silently ignored)
    - Set the value equal to your Google Maps SDK API Key

### Building and Running

#### Debug Build
1. Select a device/emulator in Android Studio
2. Click "Run" (or press Shift+F10)
3. The app will build and install automatically

#### Release Build
```bash
# From android directory
./gradlew assembleRelease

# Output APK location:
# app/build/outputs/apk/release/app-release-unsigned.apk
```

#### Running Tests
```bash
# Unit tests (app/src/test/ — the only test source set that exists today)
./gradlew test
./gradlew testDebugUnitTest
```

There is no `app/src/androidTest/` source set and no JaCoCo plugin, so
`connectedAndroidTest` and `jacocoTestReport` have nothing to run.

### Common Development Tasks

#### Adding a New API Endpoint

1. Update `TrackRatApiService.kt`:
   ```kotlin
   @GET("your/endpoint")
   suspend fun getYourData(@Query("param") param: String): YourResponse
   ```

2. Add response model in `data/models/`:
   ```kotlin
   @JsonClass(generateAdapter = true)
   data class YourResponse(
       @Json(name = "field_name") val fieldName: String
   )
   ```

3. Update repository:
   ```kotlin
   suspend fun getYourData(param: String): ApiResult<YourResponse> {
       return safeApiCall { apiService.getYourData(param) }
   }
   ```

#### Modifying UI Theme

Edit `ui/theme/Color.kt`:
```kotlin
// Change primary color
val Orange = Color(0xFFFF6B35)  // TrackRat orange

// Update color scheme in Theme.kt
val LightColorScheme = lightColorScheme(
    primary = Orange,
    // ... other colors
)
```

#### Debugging Network Requests

1. Enable verbose logging in `NetworkModule.kt`
2. Use Android Studio's Profiler → Network tab
3. Check Logcat with filter: `OkHttp`

### Project Structure

```
android/
├── app/
│   ├── build.gradle.kts           # App-level build config
│   └── src/
│       ├── main/
│       │   ├── java/com/trackrat/android/
│       │   │   ├── MainActivity.kt         # Entry point
│       │   │   ├── TrackRatApp.kt         # Application class
│       │   │   ├── data/
│       │   │   │   ├── api/              # API service, HtmlEntityDecoder, ZonedDateTimeAdapter
│       │   │   │   ├── mappers/          # TrainMappers
│       │   │   │   ├── models/           # Data models
│       │   │   │   ├── preferences/      # UserPreferencesRepository, EnvironmentManager
│       │   │   │   ├── repository/       # Data repositories
│       │   │   │   ├── services/         # TrackPrediction, BackendHealth
│       │   │   │   └── Stations.kt       # Station data
│       │   │   ├── di/                   # Dependency injection
│       │   │   ├── navigation/           # TrackRatDestinations, Navigator
│       │   │   ├── services/             # TrainTrackingService, RatSense, Notifications, TrackingStateRepository, TrainUpdateReceiver
│       │   │   ├── ui/
│       │   │   │   ├── advanced/         # Advanced config screen
│       │   │   │   ├── components/       # Reusable UI components
│       │   │   │   ├── destinationselection/ # Destination picker
│       │   │   │   ├── favorites/        # Favorite stations
│       │   │   │   ├── map/              # MapContainerScreen, MapContainerViewModel, PolylineHitDetector
│       │   │   │   ├── onboarding/       # Onboarding flow
│       │   │   │   ├── profile/          # Settings screens, components/ (ProfileActionRow, ProfileSectionCard)
│       │   │   │   ├── stationselection/ # Station selection screen
│       │   │   │   ├── theme/            # Material3 theming
│       │   │   │   ├── traindetail/      # Train detail screen
│       │   │   │   └── trainlist/        # Train list screen
│       │   │   └── utils/                # Constants, HapticFeedbackHelper, ShareService, ErrorUtils
│       │   ├── res/                      # Resources (strings, themes)
│       │   └── AndroidManifest.xml       # App manifest
│       └── test/                          # Unit tests
├── build.gradle.kts                       # Project-level build config
├── gradle.properties                      # Gradle properties
└── settings.gradle.kts                    # Project settings
```

### Troubleshooting

#### Common Issues

1. **Gradle sync fails**
   - File → Invalidate Caches and Restart
   - Check JDK version (must be 17+)
   - Ensure Android SDK 34 is installed

2. **API connection errors**
   - Check internet permission in manifest
   - Verify BASE_URL is correct
   - Check if backend is running (for local dev)

3. **Build errors with Hilt**
   - Clean project: Build → Clean Project
   - Rebuild: Build → Rebuild Project
   - Check kapt is enabled in build.gradle.kts

4. **Compose preview not working**
   - Build → Make Project first
   - Ensure preview annotations are correct
   - Check Compose version compatibility

### Backend API Reference

The Android app uses the TrackRat V2 API. Key endpoints:

The five endpoints declared in `TrackRatApiService.kt` are the whole surface the app
calls today:

- `GET /api/v2/trains/departures` - Get departures between stations
- `GET /api/v2/trains/{trainId}` - Get train details
- `GET /api/v2/predictions/track` - Track/platform predictions
- `GET /api/v2/routes/congestion` - Real-time congestion data
- `GET /health` - Backend health check

See `backend_v2/CLAUDE.md` for complete API documentation.

### Contributing

1. Create a feature branch from `main`
2. Make your changes following the existing patterns
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request with clear description

### Code Style

- Follow Kotlin coding conventions
- Use meaningful variable names
- Add KDoc comments for public APIs
- Keep composables small and focused
- Extract business logic to ViewModels

### Testing Guidelines

- Write unit tests for ViewModels and repositories
- Use test fixtures for API response testing
- Test edge cases and error states
- Aim for >70% code coverage
- Use test fixtures for common data

## Contact & Support

For questions about the Android implementation:
- Review this README and `DESIGN.md`
- Check existing code patterns
- Consult the iOS app for feature parity
- Review backend API documentation

Remember: The goal is to create an Android app that matches the iOS experience while feeling native to the Android platform.