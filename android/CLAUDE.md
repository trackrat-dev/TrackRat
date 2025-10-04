# TrackRat Android - Development Guide for Claude

This guide provides comprehensive information for Claude Code when working with the TrackRat Android application, ensuring consistency with the iOS app while maintaining Android platform conventions.

## Java Setup (Required for Building)

### Using Homebrew OpenJDK on macOS

If Java is not available in your environment, you need to activate the Homebrew-installed OpenJDK:

```bash
# Check available OpenJDK installations
brew list | grep openjdk

# Set JAVA_HOME and PATH (for OpenJDK 17)
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
export PATH=$JAVA_HOME/bin:$PATH

# Verify Java is working
java -version

# For persistent setup, add to ~/.zshrc or ~/.bash_profile:
echo 'export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home' >> ~/.zshrc
echo 'export PATH=$JAVA_HOME/bin:$PATH' >> ~/.zshrc
source ~/.zshrc
```

## Quick Start

```bash
# Navigate to Android directory
cd android

# Set up Java (if needed)
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
export PATH=$JAVA_HOME/bin:$PATH

# Build debug APK
./gradlew assembleDebug

# Build without running tests (faster)
./gradlew assembleDebug -x test

# Run on connected device/emulator
./gradlew installDebug

# Run all tests
./gradlew test

# Clean and rebuild
./gradlew clean build
```

### APK Output Location

After successful build, the debug APK is located at:
```
app/build/outputs/apk/debug/app-debug.apk
```

## Architecture Overview

### Technology Stack

- **Language**: Kotlin (100% Kotlin, no Java)
- **UI Framework**: Jetpack Compose (declarative UI matching SwiftUI approach)
- **Architecture**: MVVM with Unidirectional Data Flow
- **Dependency Injection**: Hilt (compile-time DI)
- **Networking**: Retrofit2 + OkHttp3 + Moshi
- **Async Operations**: Kotlin Coroutines + Flow
- **Local Storage**: DataStore Preferences (no Room DB yet)
- **Navigation**: Jetpack Navigation Compose
- **Design System**: Material3 with custom theming

### Project Structure

```
android/
├── app/
│   ├── src/main/java/com/trackrat/android/
│   │   ├── MainActivity.kt              # Single activity entry point
│   │   ├── TrackRatApp.kt              # Application class with Hilt
│   │   ├── data/
│   │   │   ├── api/
│   │   │   │   ├── TrackRatApiService.kt    # Retrofit API interface
│   │   │   │   └── ZonedDateTimeAdapter.kt  # Eastern Time handling
│   │   │   ├── models/
│   │   │   │   ├── TrainV2.kt              # Core train model with V2 fields
│   │   │   │   ├── StatusV2.kt             # Enhanced status model
│   │   │   │   ├── Progress.kt             # Journey progress tracking
│   │   │   │   ├── PredictionData.kt       # Owl ML predictions
│   │   │   │   ├── Stop.kt                 # Station stop with times
│   │   │   │   ├── DeparturesResponse.kt   # API response wrapper
│   │   │   │   └── ApiResult.kt            # Result wrapper for errors
│   │   │   ├── preferences/
│   │   │   │   └── UserPreferencesRepository.kt  # DataStore preferences
│   │   │   └── repository/
│   │   │       └── TrackRatRepository.kt   # Data repository pattern
│   │   ├── di/
│   │   │   ├── NetworkModule.kt            # Network DI configuration
│   │   │   └── AppModule.kt                # App-level DI providers
│   │   ├── ui/
│   │   │   ├── components/
│   │   │   │   ├── LoadingSkeletons.kt     # Shimmer loading effects
│   │   │   │   └── ErrorContent.kt         # Error state UI
│   │   │   ├── theme/
│   │   │   │   ├── Color.kt                # Color definitions (Orange!)
│   │   │   │   ├── Theme.kt                # Material3 theme setup
│   │   │   │   └── Type.kt                 # Typography definitions
│   │   │   ├── stationselection/
│   │   │   │   ├── StationSelectionScreen.kt    # Origin/destination picker
│   │   │   │   └── StationSelectionViewModel.kt # Station selection logic
│   │   │   ├── trainlist/
│   │   │   │   ├── TrainListScreen.kt          # Departure list UI
│   │   │   │   └── TrainListViewModel.kt       # Train list logic
│   │   │   └── traindetail/
│   │   │       ├── TrainDetailScreen.kt        # Journey detail UI
│   │   │       └── TrainDetailViewModel.kt     # Detail logic
│   │   └── utils/
│   │       ├── Constants.kt                # App constants
│   │       └── HapticFeedbackHelper.kt     # Haptic feedback utility
│   └── src/test/                           # Unit tests
└── build.gradle.kts                        # Gradle build configuration
```

## Key Implementation Details

### 1. API Integration

**Base URL Configuration** (`NetworkModule.kt`):
```kotlin
// Production (default)
val BASE_URL = "https://prod.api.trackrat.net/api/v2/"

// Local development with emulator
val BASE_URL = "http://10.0.2.2:8000/api/v2/"

// Local development with physical device
val BASE_URL = "http://YOUR_LOCAL_IP:8000/api/v2/"
```

**V2 API Endpoints** (`TrackRatApiService.kt`):
```kotlin
// Get departures between stations
GET /trains/departures?from={from}&to={to}&limit=50

// Get train details with refresh
GET /trains/{trainId}?date={date}&refresh=true

// Get route history (not yet implemented in UI)
GET /routes/history?from_station={from}&to_station={to}

// Get congestion data (not yet implemented in UI)
GET /routes/congestion?time_window_hours=3
```

### 2. Data Models

**Train Model Hierarchy**:
- `TrainV2`: Complete V2 model with all fields
- `Train`: Legacy model (deprecated, remove in cleanup)
- `StatusV2`: Enhanced status with location context
- `Progress`: Real-time journey tracking
- `PredictionData`: ML track predictions with confidence

**Critical Field Mappings**:
```kotlin
@Json(name = "train_id") val trainId: String          // Can be alphanumeric
@Json(name = "status_v2") val statusV2: StatusV2?     // Enhanced status
@Json(name = "progress") val progress: Progress?       // Journey progress
@Json(name = "prediction") val prediction: PredictionData?  // Owl predictions
```

### 3. Time Handling

**Eastern Time Zone** (`ZonedDateTimeAdapter.kt`):
```kotlin
// All times are Eastern Time
val ET_ZONE = ZoneId.of("America/New_York")

// Parse ISO8601 with fractional seconds
// Handle both "2024-01-01T12:00:00.123456-05:00" and "2024-01-01T12:00:00-05:00"
```

### 4. UI Components

**Screen Flow**:
1. `StationSelectionScreen` → Select origin/destination or search by train
2. `TrainListScreen` → Show departures with 30-second refresh
3. `TrainDetailScreen` → Full journey with stops and progress

**Key UI Features**:
- Pull-to-refresh on train list
- 30-second auto-refresh timer
- Loading skeletons with shimmer
- Error states with retry
- Haptic feedback on interactions
- Orange accent color theme

### 5. State Management

**ViewModel Pattern**:
```kotlin
class TrainListViewModel @Inject constructor(
    private val repository: TrackRatRepository,
    private val preferences: UserPreferencesRepository
) : ViewModel() {
    // StateFlow for UI state
    val uiState = MutableStateFlow(TrainListUiState())
    
    // Coroutines for async operations
    viewModelScope.launch {
        repository.getDepartures(from, to)
            .collect { result ->
                // Update UI state
            }
    }
}
```

## Critical Implementation Requirements

### 1. Ongoing Notifications (Android Live Activities Equivalent)

**Implementation Strategy**:
```kotlin
// 1. Create ForegroundService
class TrainTrackingService : Service() {
    // Update notification every 30 seconds
    // Use NotificationCompat.Builder with custom layout
    // Show journey progress, next stop, delays
}

// 2. Custom notification layout (RemoteViews)
val notification = NotificationCompat.Builder(context, CHANNEL_ID)
    .setCustomContentView(customView)
    .setOngoing(true)  // Cannot be dismissed
    .setPriority(NotificationCompat.PRIORITY_HIGH)
    .build()

// 3. Register in manifest
<service android:name=".services.TrainTrackingService"
    android:foregroundServiceType="dataSync" />
```

### 2. StatusV2 Display Logic

**Always prefer StatusV2 when available**:
```kotlin
// In TrainV2 model
val displayStatus: String
    get() = statusV2?.enhancedStatus ?: status

// StatusV2 provides:
// - enhancedStatus: "DEPARTED from New York Penn"
// - locationContext: Current position information
// - lastUpdate: When status was last changed

// Boarding logic (TrainListViewModel)
fun isTrainBoarding(train: TrainV2): Boolean {
    val status = train.statusV2?.enhancedStatus ?: train.status
    return status.contains("BOARDING", ignoreCase = true) ||
           status.contains("ALL ABOARD", ignoreCase = true)
}
```

### 3. Owl Prediction Display

**Confidence-based visualization**:
```kotlin
when (prediction?.confidence) {
    in 80..100 -> {
        // High confidence: Bold text + checkmark
        Text(
            text = "Track ${prediction.track} ✓",
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.primary
        )
    }
    in 50..79 -> {
        // Medium confidence: Normal text
        Text(
            text = "Track ${prediction.track} (likely)",
            fontWeight = FontWeight.Normal
        )
    }
    else -> {
        // Low confidence: Gray + question mark
        Text(
            text = "Track ${prediction.track}?",
            color = Color.Gray
        )
    }
}
```

### 4. Progress Visualization

**Journey progress tracking**:
```kotlin
// Progress model provides:
// - stopsCompleted: Number of stops passed
// - stopsTotal: Total journey stops (renamed from totalStops)
// - journeyPercent: 0-100 journey percentage (renamed from percentComplete)
// - nextArrival?.minutesToArrival: ETA to next station
// - lastDeparted: Last departed station name

// Display as progress bar (already implemented in TrainListScreen)
LinearProgressIndicator(
    progress = progress.journeyPercent / 100f,
    modifier = Modifier
        .fillMaxWidth()
        .clip(RoundedCornerShape(4.dp)),
    color = Color(Constants.BRAND_ORANGE)
)

// With text display:
Text(
    text = "${progress.stopsCompleted}/${progress.stopsTotal} stops" +
            (progress.nextArrival?.minutesToArrival?.let { " • $it min remaining" } ?: ""),
    style = MaterialTheme.typography.bodySmall
)
```

### 5. Auto-Refresh Implementation

**30-second refresh pattern (implemented in TrainListScreen)**:
```kotlin
// In TrainListScreen Composable
LaunchedEffect(fromStation, toStation) {
    while (true) {
        kotlinx.coroutines.delay(30_000) // 30 seconds
        if (!pullToRefreshState.isRefreshing) {
            viewModel.refresh()
        }
    }
}

// Pull-to-refresh handling
if (pullToRefreshState.isRefreshing) {
    LaunchedEffect(true) {
        viewModel.refresh()
    }
}
```

## Platform-Specific Considerations

### Android vs iOS Feature Mapping

| iOS Feature | Android Implementation | Status |
|------------|------------------------|---------|
| Live Activities | Foreground Service + Ongoing Notification | ❌ Not implemented |
| SwiftUI | Jetpack Compose | ✅ Implemented |
| UserDefaults | DataStore Preferences | ✅ Implemented |
| URLSession | Retrofit + OkHttp | ✅ Implemented |
| Combine | Kotlin Flow | ✅ Implemented |
| Core Location | Not needed (no location features) | N/A |
| Push Notifications | FCM (Firebase Cloud Messaging) | ❌ Not implemented |
| Widgets | Glance API widgets | ❌ Not implemented |
| Haptic Feedback | Vibrator API | ✅ Implemented |

### Material Design Principles

**Follow Material3 Guidelines**:
- Use Material You dynamic colors where appropriate
- Implement proper elevation and shadows
- Follow touch target guidelines (48dp minimum)
- Use standard Material components when possible
- Maintain consistent spacing (4dp grid)

### Performance Optimizations

**Compose Performance**:
```kotlin
// Use remember for expensive computations
val sortedTrains = remember(trains) {
    trains.sortedBy { it.scheduledDeparture }
}

// Use keys for lists
LazyColumn {
    items(trains, key = { it.trainId }) { train ->
        TrainListItem(train)
    }
}

// Avoid unnecessary recompositions
val stableState by viewModel.uiState.collectAsState()
```

## Testing Strategy

### Unit Tests

**ViewModel Testing**:
```kotlin
@Test
fun `when departures loaded then ui state updated`() = runTest {
    // Given
    val mockTrains = listOf(mockTrain1, mockTrain2)
    coEvery { repository.getDepartures(any(), any()) } returns 
        flow { emit(ApiResult.Success(mockTrains)) }
    
    // When
    viewModel.loadDepartures("NY", "TR")
    
    // Then
    assertEquals(mockTrains, viewModel.uiState.value.trains)
}
```

**Repository Testing**:
```kotlin
@Test
fun `when api call fails then return error`() = runTest {
    // Given
    coEvery { apiService.getDepartures(any(), any()) } throws Exception()
    
    // When
    val result = repository.getDepartures("NY", "TR")
    
    // Then
    assertTrue(result is ApiResult.Error)
}
```

### UI Tests

**Compose Testing**:
```kotlin
@Test
fun trainListScreen_showsLoadingState() {
    composeTestRule.setContent {
        TrainListScreen(
            uiState = TrainListUiState(isLoading = true)
        )
    }
    
    composeTestRule
        .onNodeWithTag("loading_indicator")
        .assertIsDisplayed()
}
```

## Common Development Tasks

### Adding a New Feature

1. **Define the data model** in `data/models/`
2. **Add API endpoint** to `TrackRatApiService`
3. **Update repository** with new data fetching logic
4. **Create/update ViewModel** with business logic
5. **Build UI in Compose** following Material3
6. **Add tests** for ViewModel and repository
7. **Test on device** for performance and UX

### Debugging Tips

**Network Debugging**:
```kotlin
// Enable verbose logging in NetworkModule
HttpLoggingInterceptor.Level.BODY

// Use Charles Proxy or similar
// Add proxy settings to emulator
```

**Compose Debugging**:
```kotlin
// Enable layout inspector
// Tools → Layout Inspector in Android Studio

// Show recomposition counts
@Composable
fun MyComposable() {
    // In debug builds
    if (BuildConfig.DEBUG) {
        SideEffect {
            Log.d("Recomposition", "MyComposable recomposed")
        }
    }
}
```

**Memory Leaks**:
```kotlin
// Use LeakCanary in debug builds
debugImplementation("com.squareup.leakcanary:leakcanary-android:2.12")

// Check ViewModel lifecycle
// Ensure coroutines are cancelled properly
```

## Deployment Checklist

### Pre-release Tasks

- [ ] Update version code and name in `build.gradle.kts`
- [ ] Test on minimum SDK version (26 / Android 8.0)
- [ ] Test on latest SDK version (34 / Android 14)
- [ ] Verify ProGuard rules if enabling minification
- [ ] Test on various screen sizes (phone, tablet)
- [ ] Check dark mode appearance
- [ ] Verify network error handling
- [ ] Test with slow/no internet connection
- [ ] Profile for performance issues
- [ ] Run lint checks: `./gradlew lint`

### Release Build

```bash
# Create release build
./gradlew assembleRelease

# With signing (requires keystore)
./gradlew assembleRelease \
  -Pandroid.injected.signing.store.file=$KEYSTORE_PATH \
  -Pandroid.injected.signing.store.password=$STORE_PASSWORD \
  -Pandroid.injected.signing.key.alias=$KEY_ALIAS \
  -Pandroid.injected.signing.key.password=$KEY_PASSWORD
```

## Troubleshooting Guide

### Common Issues and Solutions

**1. Gradle sync failures**
```bash
# Clear Gradle cache
./gradlew clean
rm -rf ~/.gradle/caches/

# In Android Studio
File → Invalidate Caches and Restart
```

**2. Hilt compilation errors**
```kotlin
// Ensure all injected classes have @Inject constructor
// ViewModels need @HiltViewModel annotation
// Activities need @AndroidEntryPoint
```

**3. Compose preview not working**
```kotlin
// Add @Preview annotation properly
@Preview(showBackground = true)
@Composable
fun PreviewFunction() {
    TrackRatTheme {
        YourComposable()
    }
}
```

**4. API connection issues**
```kotlin
// Check manifest permissions
<uses-permission android:name="android.permission.INTERNET" />

// For local development, check IP address
// Emulator uses 10.0.2.2 for host machine
```

**5. DateTime parsing errors**
```kotlin
// Ensure ZonedDateTimeAdapter is registered in Moshi
// Check for fractional seconds in timestamps
// Verify Eastern Time zone handling
```

## Code Style Guidelines

### Kotlin Conventions

**Naming**:
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

**Formatting**:
```kotlin
// Use trailing commas in multi-line parameters
fun example(
    param1: String,
    param2: Int,
    param3: Boolean,  // Trailing comma
)

// Prefer expression bodies for simple functions
fun isValid() = value != null && value.isNotEmpty()
```

### Compose Best Practices

**State Management**:
```kotlin
// Hoist state up
@Composable
fun StatelessComposable(
    value: String,
    onValueChange: (String) -> Unit
)

// Use remember for expensive operations
val processedData = remember(rawData) {
    processRawData(rawData)
}
```

**Performance**:
```kotlin
// Use stable types for parameters
@Stable
data class TrainUiModel(...)

// Avoid inline lambdas that capture variables
val onClick = remember { { handleClick() } }
```

## Future Enhancements Roadmap

### Phase 1: MVP Completion (High Priority)
- ✅ Core navigation and screens
- ✅ API integration
- ✅ Basic UI with Material3
- ❌ Ongoing notifications (Foreground Service)
- ❌ StatusV2 display logic
- ❌ Progress visualization
- ❌ Owl prediction confidence display

### Phase 2: Feature Parity with iOS (Medium Priority)
- ❌ Push notifications (FCM)
- ❌ Route history screen
- ❌ Congestion visualization
- ❌ Deep linking support
- ❌ Trip favorites
- ❌ Share functionality

### Phase 3: Android-Specific Enhancements (Low Priority)
- ❌ Home screen widgets (Glance API)
- ❌ Wear OS companion app
- ❌ Android Auto integration
- ❌ Quick Settings tile
- ❌ Notification actions (shortcuts)

## Integration with Backend

### API Response Caching

The backend implements intelligent caching:
- Congestion endpoint responses cached for 15 minutes
- Train details cached until next update
- Use `refresh=true` parameter to force update

### Real-time Updates

Current polling strategy:
- Discovery: Every 30 minutes
- Journey updates: Every 15 minutes
- Client refresh: Every 30 seconds (when active)
- JIT updates: On-demand with 60-second staleness check

### Error Handling

Expected error responses:
- `404`: Train not found
- `400`: Invalid parameters
- `500`: Server error (retry with backoff)
- `503`: Service unavailable (show maintenance message)

## Current Implementation Status

### ✅ Successfully Implemented Features

**Core Functionality:**
- **Navigation**: Type-safe navigation with Compose Navigation
- **4 Main Screens**: Station selection, destination selection, train list, train detail
- **API Integration**: Full V2 API support with consolidation enabled
- **Real-time Updates**: 30-second auto-refresh and pull-to-refresh
- **Glassmorphic UI**: Matching iOS design aesthetic
- **Favorites**: Station favorites with heart icons
- **Progress Tracking**: Journey progress bars with stop counts
- **Track Predictions**: Owl predictions with confidence visualization
- **Boarding Status**: Orange card highlighting for boarding trains
- **HTML Entity Decoding**: Proper display of emojis in destination names
- **Environment Switching**: Debug builds can switch between environments

**Build Commands:**
```bash
# Set up Java (required each session unless added to shell profile)
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
export PATH=$JAVA_HOME/bin:$PATH

# Build debug APK (skip tests for now)
./gradlew assembleDebug -x test

# Install on device/emulator
./gradlew installDebug
```

**Implementation Status:**
- ✅ HTML entity decoding for destination names (airplane emojis display correctly)
- ✅ Support for DepartureV2 API model with enhanced train position and data freshness
- ✅ StatusV2 integration for better status display
- ✅ Progress tracking for journey visualization
- ✅ Core app functionality works and APK builds successfully
- ⚠️  Unit tests need updates for new TrainV2 constructor (can be addressed later)

## Known Issues & Areas for Improvement

### 🐛 Bugs to Fix

1. **Track Button Not Working**: The "Track This Train" button in TrainDetailScreen is disabled and non-functional
2. **Prediction Data Access**: TrainDetailV2 doesn't include prediction data from the API
3. **Progress Model Inconsistency**: Two different Progress models (Progress vs ProgressV2) need consolidation
4. **Status Display**: StatusChip appears in two different files with duplicate code
5. **No All Departures**: "Show all departures" feature removed as backend doesn't support it

### ⚠️ Technical Debt

1. **Duplicate Models**: Multiple versions of similar models (Train/TrainV2, Progress/ProgressV2)
2. **Missing Tests**: Unit tests need updating for new constructors
3. **Hard-coded Values**: API base URL and other configs should be in BuildConfig
4. **No Error Recovery**: Limited retry logic for network failures
5. **Memory Leaks**: No proper lifecycle management for auto-refresh coroutines

### 🚀 Performance Issues

1. **No Caching**: API responses are not cached locally
2. **Excessive Recomposition**: Train list items may recompose unnecessarily
3. **Large APK Size**: 18.3 MB is quite large for a simple app
4. **No Pagination**: Train list loads all items at once

## Recent Enhancements & Fixes (September 2025)

### Recent Updates

1. **Enhanced Navigation System**
   - Type-safe navigation with `TrackRatNavigator`
   - Separate destination selection screen
   - Proper back stack management

2. **Glassmorphic Design Implementation**
   - `GlassmorphicCard` component matching iOS
   - Semi-transparent cards with borders
   - Special variants for search and elevated cards

3. **Station Favorites**
   - Heart icons for favoriting stations
   - Persistence with DataStore preferences
   - Quick access to favorite destinations

4. **Boarding Status Highlighting**
   - Orange cards for boarding trains
   - Dynamic status chip colors
   - Visual distinction for different states

5. **Track Predictions UI**
   - Confidence-based styling (checkmark, normal, question mark)
   - Owl emoji integration
   - Platform-level aggregation display

6. **Environment Management**
   - `EnvironmentManager` for switching between dev/prod
   - BuildConfig flags for environment control
   - Debug-only switching capability

## Contact for Support

When working on the Android app:
- Follow this guide for implementation details
- Reference `android-app.md` for requirements
- Check iOS implementation for feature parity
- Consult backend documentation for API details
- Use Material Design guidelines for UI decisions

Remember: The goal is to create a native Android experience that matches iOS functionality while feeling natural to Android users.