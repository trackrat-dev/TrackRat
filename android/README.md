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
- **V2 API Endpoints**: Correctly configured for production backend (https://prod.api.trackrat.net/api/v2/)
- **Custom DateTime Adapter**: Proper handling of Eastern Time zone with ZonedDateTime
- **Error Handling**: ApiResult wrapper for consistent error management
- **Network Logging**: Debug logging for API calls in development builds

#### Data Models
- **Complete V2 Models**: TrainV2, StatusV2, Progress, PredictionData, Stop models matching backend
- **Response Models**: DeparturesResponse, TrainDetailsResponse for API responses
- **Station Data**: All 5 major stations (NY, NP, TR, PJ, MP) plus extended Amtrak stations
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
  - Historical data modal (bottom sheet)
  - Support for both train IDs and numbers

#### User Experience
- **Haptic Feedback**: Tactile responses on user interactions
- **User Preferences**: DataStore for persisting user settings and recent trips
- **Loading States**: Shimmer effects and skeleton screens
- **Error Handling**: Graceful error states with retry options
- **Theme**: Orange accent color matching iOS app

### 🚧 In Progress / Partially Implemented

#### Notifications System
- **Foreground Service**: Structure exists but needs implementation for ongoing notifications
- **Notification Channels**: Setup required for different notification types
- **Firebase Integration**: FCM setup needed for push notifications

#### Data Features
- **Journey Progress Tracking**: Model exists but UI visualization needs completion
- **StatusV2 Display**: Model exists but enhanced display logic needs implementation
- **Owl Predictions**: Data structure ready but confidence visualization needs work
- **Congestion Analysis**: Models exist but UI components need implementation

### ❌ Not Yet Implemented

#### Critical Missing Features
1. **Live Train Tracking (Ongoing Notifications)**
   - Foreground service for continuous updates
   - Custom notification layout with journey progress
   - Background data refresh mechanism

2. **Network Congestion Visualization**
   - Congestion map UI component
   - Color-coded delay indicators
   - Real-time updates from `/api/v2/routes/congestion`

3. **Historical Route Analytics**
   - Route performance charts
   - Delay breakdown visualization
   - Track usage statistics

4. **Advanced Features**
   - Home screen widget (using Glance API)
   - Deep linking for train sharing
   - Offline mode with local caching
   - Search filters and sorting options

## Recommended Future Improvements

### High Priority (Essential for MVP)

1. **Implement Ongoing Notifications**
   ```kotlin
   // Create ForegroundService for live tracking
   // Use NotificationCompat for rich notifications
   // Update every 30 seconds when active
   ```

2. **Complete Progress Visualization**
   - Add journey progress bar to train list items
   - Implement stop-by-stop progress in detail screen
   - Show real-time position updates

3. **Fix StatusV2 Display Logic**
   - Use `statusV2?.enhancedStatus ?: status` pattern
   - Implement proper status color coding
   - Add location context from StatusV2

4. **Add Owl Prediction Confidence Display**
   - High confidence (≥80%): Bold with checkmark
   - Medium confidence (50-79%): Normal text
   - Low confidence (<50%): Gray with question mark

### Medium Priority (Enhanced UX)

1. **Add Route History Screen**
   - Historical performance metrics
   - Delay patterns visualization
   - Peak/off-peak analysis

2. **Implement Congestion Map**
   - Real-time network status
   - Color-coded segments
   - Tap for details functionality

3. **Add Trip Planning Features**
   - Save favorite routes
   - Schedule reminders
   - Multi-stop journey planning

4. **Performance Optimizations**
   - Implement proper pagination for train lists
   - Add memory caching for API responses
   - Optimize Compose recompositions

### Low Priority (Nice to Have)

1. **Widget Implementation**
   - Next departure widget
   - Active journey widget
   - Quick access shortcuts

2. **Additional Transit Systems**
   - LIRR support
   - Metro-North support
   - SEPTA/PATH integration

3. **Accessibility Improvements**
   - Screen reader optimization
   - High contrast mode
   - Font size adjustments

## Getting Started - Development Setup

### Prerequisites

1. **Android Studio**: Latest stable version (Hedgehog or newer)
2. **JDK**: Version 11 or higher
3. **Android SDK**: API 34 (Android 14)
4. **Git**: For version control

### Initial Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-repo/TrackRat.git
   cd TrackRat/android
   ```

2. **Open in Android Studio**
   - File → Open → Select the `android` folder
   - Let Gradle sync complete

3. **Configure local development (optional)**
   
   For local backend testing, update `NetworkModule.kt`:
   ```kotlin
   // For emulator connecting to localhost
   val BASE_URL = "http://10.0.2.2:8000/api/v2/"
   
   // For physical device on same network
   val BASE_URL = "http://YOUR_LOCAL_IP:8000/api/v2/"
   ```

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
# Unit tests
./gradlew test

# Instrumented tests (requires device/emulator)
./gradlew connectedAndroidTest

# All tests with coverage
./gradlew testDebugUnitTest jacocoTestReport
```

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
│       │   │   │   ├── api/              # API service & adapters
│       │   │   │   ├── models/           # Data models
│       │   │   │   ├── preferences/      # User preferences
│       │   │   │   └── repository/       # Data repositories
│       │   │   ├── di/                   # Dependency injection
│       │   │   ├── ui/
│       │   │   │   ├── components/       # Reusable UI components
│       │   │   │   ├── theme/            # Material3 theming
│       │   │   │   ├── stationselection/ # Station selection screen
│       │   │   │   ├── trainlist/        # Train list screen
│       │   │   │   └── traindetail/      # Train detail screen
│       │   │   └── utils/                # Utilities & helpers
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
   - Check JDK version (must be 11+)
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

- `GET /api/v2/trains/departures` - Get departures between stations
- `GET /api/v2/trains/{trainId}` - Get train details
- `GET /api/v2/routes/history` - Historical route performance
- `GET /api/v2/routes/congestion` - Real-time congestion data
- `POST /api/v2/live-activities/register` - Register for notifications

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
- Mock API responses for testing
- Test edge cases and error states
- Aim for >70% code coverage
- Use test fixtures for common data

## Contact & Support

For questions about the Android implementation:
- Review this README and `android-app.md`
- Check existing code patterns
- Consult the iOS app for feature parity
- Review backend API documentation

Remember: The goal is to create an Android app that matches the iOS experience while feeling native to the Android platform.