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
- **Maps**: Google Maps SDK with Compose integration
- **Dependency Injection**: Hilt (compile-time DI)
- **Networking**: Retrofit2 + OkHttp3 + Moshi
- **Async Operations**: Kotlin Coroutines + Flow
- **Local Storage**: DataStore Preferences (no Room DB yet)
- **Navigation**: Jetpack Navigation Compose (within bottom sheet overlay)
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
│   │   │   │   ├── TrainV2.kt              # Train list model with V2 fields
│   │   │   │   ├── TrainDetailV2.kt        # Train detail model
│   │   │   │   ├── DepartureV2.kt          # Enhanced departure data
│   │   │   │   ├── StatusV2.kt             # Enhanced status with location
│   │   │   │   ├── Progress.kt / ProgressV2.kt  # Journey progress (both exist)
│   │   │   │   ├── PredictionData.kt       # Track prediction from API
│   │   │   │   ├── PlatformPrediction.kt   # ML platform predictions
│   │   │   │   ├── CongestionSegment.kt    # Network congestion data
│   │   │   │   ├── Stop.kt / StopDetail.kt # Station stops
│   │   │   │   ├── DeparturesResponse.kt   # API response wrapper
│   │   │   │   └── ApiResult.kt            # Result wrapper for errors
│   │   │   ├── preferences/
│   │   │   │   └── UserPreferencesRepository.kt  # DataStore preferences
│   │   │   ├── repository/
│   │   │   │   ├── TrackRatRepository.kt   # Data repository pattern
│   │   │   │   └── TrackingStateRepository.kt  # Notification state
│   │   │   └── services/
│   │   │       ├── TrackPredictionService.kt    # ML prediction logic
│   │   │       └── BackendHealthService.kt      # Server validation
│   │   ├── di/
│   │   │   ├── NetworkModule.kt            # Network DI configuration
│   │   │   └── AppModule.kt                # App-level DI providers
│   │   ├── services/
│   │   │   ├── TrainTrackingService.kt     # Foreground service
│   │   │   └── TrainTrackingNotificationManager.kt  # Notification UI
│   │   ├── ui/
│   │   │   ├── components/
│   │   │   │   ├── DraggableBottomSheet.kt      # Spring-animated sheet
│   │   │   │   ├── BottomSheetDragState.kt      # Gesture coordination
│   │   │   │   ├── SheetAwareScrollView.kt      # Smart scrolling
│   │   │   │   ├── LoadingSkeletons.kt          # Shimmer loading
│   │   │   │   └── ErrorContent.kt              # Error state UI
│   │   │   ├── theme/
│   │   │   │   ├── Color.kt                # Color definitions (Orange!)
│   │   │   │   ├── Theme.kt                # Material3 theme setup
│   │   │   │   └── Type.kt                 # Typography definitions
│   │   │   ├── map/
│   │   │   │   ├── MapContainerScreen.kt        # Root screen with map
│   │   │   │   ├── MapContainerViewModel.kt     # Map logic & congestion
│   │   │   │   └── PolylineHitDetector.kt       # Tap detection utility
│   │   │   ├── stationselection/
│   │   │   │   ├── StationSelectionScreen.kt    # Origin picker
│   │   │   │   └── StationSelectionViewModel.kt # Station selection logic
│   │   │   ├── destinationselection/
│   │   │   │   └── DestinationSelectionScreen.kt  # Destination picker
│   │   │   ├── trainlist/
│   │   │   │   ├── TrainListScreen.kt          # Departure list UI
│   │   │   │   └── TrainListViewModel.kt       # Train list logic
│   │   │   ├── traindetail/
│   │   │   │   ├── TrainDetailScreen.kt         # Journey detail UI
│   │   │   │   ├── TrainDetailViewModel.kt      # Detail logic
│   │   │   │   └── SegmentedTrackPredictionBar.kt  # Platform predictions
│   │   │   └── profile/
│   │   │       ├── ProfileScreen.kt             # User settings
│   │   │       ├── FavoriteStationsScreen.kt    # Favorites management
│   │   │       └── AdvancedConfigScreen.kt      # Server switching
│   │   └── utils/
│   │       ├── Constants.kt                # App constants
│   │       ├── HapticFeedbackHelper.kt     # Haptic feedback utility
│   │       ├── Stations.kt                 # 150+ station coordinates
│   │       └── EnvironmentManager.kt       # Dev/prod switching
│   ├── src/test/                           # Unit tests
│   └── src/main/res/raw/
│       └── dark_map_style.json             # Dark mode map styling
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

// Get track predictions (NY Penn only)
GET /predictions/track?train_id={trainId}&date={date}

// Get congestion data (✅ implemented)
GET /routes/congestion?time_window_hours=3&max_per_segment=200

// Get route history (not yet implemented in UI)
GET /routes/history?from_station={from}&to_station={to}
```

### 2. Data Models

**Train Model Hierarchy**:
- `TrainV2`: Train list model with V2 fields
- `TrainDetailV2`: Train detail model with full journey data
- `DepartureV2`: Enhanced departure with position and freshness
- `StatusV2`: Enhanced status with location context
- `Progress` / `ProgressV2`: Real-time journey tracking (⚠️ duplicates exist)
- `PredictionData`: Track prediction from API (single track confidence)
- `PlatformPrediction`: ML platform predictions (NY Penn only)
- `CongestionSegment`: Network congestion data with color/severity
- `Stop` / `StopDetail`: Station stop information

**Critical Field Mappings**:
```kotlin
// TrainV2 (used in train list)
@Json(name = "train_id") val trainId: String          // Can be alphanumeric
@Json(name = "status_v2") val statusV2: StatusV2?     // Enhanced status
@Json(name = "progress") val progress: Progress?       // Journey progress
@Json(name = "prediction") val prediction: PredictionData?  // Track prediction

// DepartureV2 (enhanced departure data)
@Json(name = "train") val train: TrainV2
@Json(name = "train_position") val trainPosition: String?  // e.g., "between NY and NP"
@Json(name = "data_freshness") val dataFreshness: String?  // e.g., "2 minutes ago"

// CongestionSegment
@Json(name = "from_station") val fromStation: String
@Json(name = "to_station") val toStation: String
@Json(name = "congestion_factor") val congestionFactor: Double  // 1.0-2.0+
@Json(name = "color") val color: String  // "green", "yellow", "orange", "red"
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

**App Architecture**:
- `MapContainerScreen`: Root screen with Google Maps + draggable bottom sheet
- Bottom sheet contains `NavHost` with all app screens
- Sheet positions: MEDIUM (50% height) and EXPANDED (100% height)
- Navigation embedded within bottom sheet overlay

**Screen Flow**:
1. `MapContainerScreen` → Root with map background
2. `StationSelectionScreen` → Select origin (sheet content)
3. `DestinationSelectionScreen` → Select destination
4. `TrainListScreen` → Show departures with 30-second refresh
5. `TrainDetailScreen` → Full journey with stops and progress
6. `ProfileScreen` → Settings and server switching (not fully wired)

**Key UI Features**:
- Google Maps with congestion overlay and route visualization
- Draggable bottom sheet with spring animation
- Sheet-aware scrolling (gesture coordination)
- Pull-to-refresh on train list
- 30-second auto-refresh timer
- Loading skeletons with shimmer
- Error states with retry
- Haptic feedback on interactions
- Orange accent color theme
- Dark mode map styling

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

### 1. Bottom Sheet Gesture Coordination System

**BottomSheetDragState** - Shared gesture state machine (`BottomSheetDragState.kt`):
```kotlin
enum class GestureMode {
    IDLE,           // No active gesture
    SHEET_MOVING,   // Sheet is expanding/collapsing
    SCROLLING       // Content is scrolling
}

// Gesture routing logic matching iOS SheetAwareScrollView
fun determineGestureMode(
    currentPosition: SheetPosition,
    isAtScrollTop: Boolean,
    isDraggingUp: Boolean
): GestureMode {
    return when {
        currentPosition == MEDIUM && isDraggingUp -> SHEET_MOVING
        currentPosition == EXPANDED && isAtScrollTop && !isDraggingUp -> SHEET_MOVING
        currentPosition == EXPANDED -> SCROLLING
        else -> IDLE
    }
}
```

**DraggableBottomSheet** - Low-level gesture capture (`DraggableBottomSheet.kt`):
```kotlin
// Key parameters
isScrollable: Boolean = false  // Enable gesture coordination

// Gesture thresholds (matching iOS)
val VELOCITY_THRESHOLD = 50f
val TRANSLATION_THRESHOLD = 50f
val DEAD_ZONE = 5.px

// Low-level gesture handling
awaitPointerEventScope {
    val down = awaitFirstDown(requireUnconsumed = false)

    verticalDrag(down.id) { change ->
        if (shouldCaptureGesture(translation, velocity)) {
            change.consume()  // Capture gesture from children
            dragState.translation.value = translation
        }
    }
}
```

**SheetAwareScrollView** - Smart scroll wrapper (`SheetAwareScrollView.kt`):
```kotlin
// For Column with verticalScroll
SheetAwareScrollView(
    dragState = dragState,
    scrollState = rememberScrollState()
) {
    Column { /* content */ }
}

// For LazyColumn
SheetAwareLazyColumn(
    dragState = dragState,
    state = rememberLazyListState()
) {
    items(trains) { /* content */ }
}

// Coordinated scrolling
when (dragState.gestureMode.value) {
    SHEET_MOVING -> scrollEnabled = false
    SCROLLING -> scrollEnabled = true
    IDLE -> scrollEnabled = true
}
```

**"One Swipe = One Action" Pattern**:
- FROM MEDIUM + swipe up → expands sheet to EXPANDED
- FROM EXPANDED + at top + swipe down → collapses to MEDIUM
- FROM EXPANDED + mid-scroll + swipe down → scrolls content up
- Haptic feedback on position changes
- Spring animation (dampingRatio=0.8, stiffness=400f)

### 2. Map Integration & Congestion Overlay

**MapContainerViewModel** - Congestion data management (`MapContainerViewModel.kt`):
```kotlin
// Fetch congestion on launch, refresh every 5 minutes
init {
    fetchCongestionData()
    viewModelScope.launch {
        while (true) {
            delay(5 * 60 * 1000)  // 5 minutes
            fetchCongestionData()
        }
    }
}

// Camera animation with sheet-aware offset
fun animateCameraToRoute(fromStation: String, toStation: String) {
    val bounds = calculateRegion(fromCoords, toCoords)
    val offset = when (sheetPosition) {
        MEDIUM -> -0.10  // ~7 miles south
        EXPANDED -> -0.38  // ~25 miles south
        else -> 0.0
    }
    cameraPositionState.animate(
        update = CameraUpdateFactory.newLatLngBounds(bounds, 0),
        durationMs = 250
    )
}
```

**PolylineHitDetector** - Tap detection utility (`PolylineHitDetector.kt`):
```kotlin
// Screen-coordinate-based tap detection
fun detectPolylineHit(
    tapLatLng: LatLng,
    polylines: List<Polyline>,
    projection: Projection,
    tolerancePx: Float = 30f
): String? {
    val tapPoint = projection.toScreenLocation(tapLatLng)

    polylines.forEach { polyline ->
        val segmentPoints = polyline.points.map {
            projection.toScreenLocation(it)
        }

        segmentPoints.zipWithNext().forEach { (p1, p2) ->
            val distance = distanceToLineSegment(tapPoint, p1, p2)
            if (distance <= tolerancePx) {
                return polyline.tag as? String
            }
        }
    }
    return null
}
```

**Congestion Visualization**:
```kotlin
// Color scheme matching iOS
val color = when (segment.color) {
    "green" -> Color(0xFF34C759)
    "yellow" -> Color(0xFFFFCC00)
    "orange" -> Color(0xFFFF9500)
    "red" -> Color(0xFFFF3B30)
    else -> Color.Gray
}

// Dynamic width based on congestion (5-11pt)
val width = (5f + (segment.congestionFactor - 1.0f) * 6f).coerceIn(5f, 11f)

// Selected segment highlighting
val selectedWidth = 9f
val selectedColor = Color(0xFF007AFF)  // iOS blue

// Polyline rendering
Polyline(
    points = segment.coordinates,
    color = if (isSelected) selectedColor else color,
    width = if (isSelected) selectedWidth else width,
    zIndex = if (isSelected) 15f else 5f
)
```

### 3. Ongoing Notifications (Android Live Activities Equivalent)

**TrainTrackingService** - Foreground service (`TrainTrackingService.kt`):
```kotlin
class TrainTrackingService : Service() {
    // ✅ IMPLEMENTED
    // 30-second updates via AlarmManager
    // Custom notification layout with RemoteViews
    // Journey progress, next stop, delays
    // Auto-stop on arrival

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val trainId = intent?.getStringExtra(EXTRA_TRAIN_ID)
        val date = intent?.getStringExtra(EXTRA_DATE)

        // Register alarm for updates
        scheduleNextUpdate()

        // Start foreground with notification
        startForeground(NOTIFICATION_ID, createNotification())

        return START_STICKY
    }
}

// TrainTrackingNotificationManager - Custom layouts
val notification = NotificationCompat.Builder(context, CHANNEL_ID)
    .setCustomContentView(customView)
    .setOngoing(true)  // Cannot be dismissed
    .setPriority(NotificationCompat.PRIORITY_HIGH)
    .build()

// Manifest registration
<service android:name=".services.TrainTrackingService"
    android:foregroundServiceType="dataSync" />
```

### 4. StatusV2 Display Logic

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

### 5. Track Prediction Display

**SegmentedTrackPredictionBar** - Platform probability visualization (`SegmentedTrackPredictionBar.kt`):
```kotlin
// NY Penn Station only, pre-track-assignment
fun shouldShowPredictions(train: TrainDetailV2): Boolean {
    return train.origin == "NY" &&  // New York Penn Station
           train.track == null &&   // No track assigned yet
           platformPredictions.isNotEmpty()
}

// Platform grouping (converts track probabilities back to platforms)
val platformGroups = predictions
    .groupBy { it.platform }
    .mapValues { (_, tracks) -> tracks.sumOf { it.probability } }
    .filter { it.value >= 0.17 }  // 17% threshold

// Segmented bar visualization
Row {
    platformGroups.forEach { (platform, probability) ->
        Box(
            modifier = Modifier
                .weight(probability.toFloat())
                .background(platformColor(platform))
        ) {
            Text("${platform}: ${(probability * 100).toInt()}%")
        }
    }
}

// "No clear favorite" message if all < 17%
if (platformGroups.isEmpty()) {
    Text("No clear favorite platform")
}
```

### 6. Owl Prediction Display (Individual Track)

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

### 7. Progress Visualization

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

### 8. Auto-Refresh Implementation

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
| Live Activities | TrainTrackingService + Ongoing Notification | ✅ Implemented |
| MapKit | Google Maps SDK | ✅ Implemented |
| SwiftUI | Jetpack Compose | ✅ Implemented |
| UserDefaults | DataStore Preferences | ✅ Implemented |
| URLSession | Retrofit + OkHttp | ✅ Implemented |
| Combine | Kotlin Flow | ✅ Implemented |
| Sheet Gestures | BottomSheetDragState + DraggableBottomSheet | ✅ Implemented |
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

### Phase 1: MVP Completion ✅ COMPLETE
- ✅ Core navigation and screens
- ✅ API integration
- ✅ Map-based UI with Material3
- ✅ Ongoing notifications (TrainTrackingService)
- ✅ StatusV2 display logic
- ✅ Progress visualization
- ✅ Track prediction display (segmented bar + confidence)
- ✅ Bottom sheet gesture coordination

### Phase 2: Feature Parity with iOS ✅ COMPLETE
- ✅ Map integration with Google Maps
- ✅ Congestion visualization with tap detection
- ✅ Route polyline visualization
- ✅ Station favorites
- ✅ Profile system with server switching
- ❌ Push notifications (FCM) - not needed yet
- ❌ Route history screen - backend endpoint exists, UI not built
- ❌ Deep linking support - not implemented
- ❌ Share functionality - not implemented

### Phase 3: Android-Specific Enhancements (Future)
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
- **Map-Based UI**: Google Maps with dark mode styling as root screen
- **Bottom Sheet Navigation**: Draggable sheet with MEDIUM/EXPANDED positions
- **Gesture Coordination**: "One swipe = one action" pattern matching iOS
- **6 Main Screens**: Map container, station selection, destination selection, train list, train detail, profile
- **API Integration**: Full V2 API support (departures, details, predictions, congestion)
- **Real-time Updates**: 30-second auto-refresh and pull-to-refresh
- **Glassmorphic UI**: Matching iOS design aesthetic
- **Station Favorites**: Heart icons with DataStore persistence
- **Progress Tracking**: Journey progress bars with stop counts
- **Track Predictions**: Segmented platform probability bar (NY Penn only)
- **Congestion Overlay**: Color-coded polylines with tap-to-highlight
- **Ongoing Notifications**: TrainTrackingService with 30-second updates
- **Boarding Status**: Orange card highlighting for boarding trains
- **HTML Entity Decoding**: Proper display of emojis in destination names
- **Environment Switching**: Debug builds can switch between prod/staging servers

**Map Features:**
- ✅ Congestion polylines with dynamic width (5-11pt) based on severity
- ✅ Color scheme: green/yellow/orange/red matching iOS
- ✅ Tap detection with 30px tolerance
- ✅ Selected segment highlighting (iOS blue, thicker line)
- ✅ Route polyline visualization
- ✅ Camera animation with zoom-aware offset for sheet visibility
- ✅ 5-minute auto-refresh of congestion data
- ✅ 150+ station coordinates synchronized with iOS and backend

**Notification Features:**
- ✅ Foreground service with custom notification layouts
- ✅ 30-second updates via AlarmManager
- ✅ Journey progress, next stop, and delay information
- ✅ Auto-stop on train arrival
- ✅ Persistent tracking state with TrackingStateRepository

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
- ✅ Map-based architecture matching iOS MapContainerView
- ✅ Bottom sheet gesture coordination with GestureMode state machine
- ✅ Congestion overlay with interactive tap detection
- ✅ Track predictions (both segmented bar and individual confidence)
- ✅ Ongoing notifications (TrainTrackingService)
- ✅ StatusV2 integration for better status display
- ✅ Progress tracking for journey visualization
- ✅ Profile system with favorites and server switching
- ✅ DepartureV2 API model with enhanced train position and data freshness
- ✅ HTML entity decoding for destination names
- ✅ Core app functionality works and APK builds successfully
- ⚠️  Unit tests need updates for new TrainV2 constructor (can be addressed later)
- ⚠️  ProfileScreen not fully wired to main navigation (intentionally disabled)

## Known Issues & Areas for Improvement

### ⚠️ Technical Debt

1. **Duplicate Models**: Multiple versions of similar models need consolidation
   - `Progress` vs `ProgressV2` (both exist in codebase)
   - `Stop` vs `StopDetail` (different use cases but similar)
   - Consider single model with optional fields

2. **Missing Tests**: Unit tests need updating
   - TrainV2 constructor changes broke existing tests
   - New features (map, predictions, notifications) lack test coverage
   - Repository and ViewModel tests need mocking updates

3. **ProfileScreen Not Wired**: Profile navigation is commented out
   - Functionality exists but not accessible from main UI
   - Need UI/UX decision on where to place profile entry point
   - Consider tab bar, settings icon, or gesture

4. **Hard-coded Values**: Some configuration should be externalized
   - Maps API key in manifest (currently placeholder-based)
   - API base URLs in NetworkModule (need BuildConfig integration)
   - Station coordinates in Stations.kt (consider loading from backend)

5. **Limited Error Recovery**: Network failures could be handled better
   - No exponential backoff for retries
   - Limited offline support
   - No caching of API responses

### 🚀 Performance Opportunities

1. **API Response Caching**: All responses are fetched fresh
   - Consider caching train details for 60 seconds
   - Cache departures for 30 seconds
   - Cache congestion data for 5 minutes
   - Use Room database or in-memory cache

2. **Recomposition Optimization**: Some composables may recompose excessively
   - Audit `remember`, `derivedStateOf`, and `@Stable` usage
   - Add keys to LazyColumn items
   - Profile with Layout Inspector

3. **APK Size**: Current debug APK is ~18MB
   - Enable ProGuard/R8 for release builds
   - Remove unused resources
   - Consider code splitting for large features

4. **No Pagination**: Train list loads all results
   - Backend supports `limit` parameter
   - Consider lazy loading for large result sets
   - Add "Load more" button or infinite scroll

### 🔮 Future Enhancements

1. **Deep Linking**: Support opening specific trains from URLs
2. **Share Functionality**: Share train status with others
3. **Route History Screen**: UI for `/routes/history` endpoint
4. **Home Screen Widgets**: Glance API widget for favorite routes
5. **Notification Actions**: Quick actions in ongoing notification
6. **Offline Mode**: Cache recent data for offline viewing

## Recent Enhancements & Fixes (October 2025)

### Major Features Added

1. **Map-Based UI Architecture (October 12, 2025)**
   - Migrated from list-based to map-centered interface
   - `MapContainerScreen` as root with Google Maps integration
   - Draggable bottom sheet with MEDIUM/EXPANDED positions
   - 150+ station coordinates synchronized across iOS/Android/backend
   - Dark mode map styling with Material3 integration

2. **Bottom Sheet Gesture Coordination (October 12, 2025)**
   - `BottomSheetDragState` with GestureMode state machine
   - "One swipe = one action" pattern matching iOS
   - Low-level gesture capture with `awaitPointerEventScope`
   - `SheetAwareScrollView` and `SheetAwareLazyColumn` smart wrappers
   - Haptic feedback on position changes
   - Velocity (50f) + translation (50f) thresholds

3. **Congestion Overlay System (October 12, 2025)**
   - Real-time congestion polylines with 5-minute auto-refresh
   - Color-coded severity: green/yellow/orange/red
   - Dynamic width scaling (5-11pt) based on congestion factor
   - `PolylineHitDetector` with 30px tap tolerance
   - Tap-to-highlight with iOS blue selection color
   - Camera animation with zoom-aware offset for sheet visibility

4. **Track Prediction System (October 12, 2025)**
   - `TrackPredictionService` for ML-based platform predictions
   - `SegmentedTrackPredictionBar` with platform probability grouping
   - NY Penn Station only, pre-track-assignment
   - 17% threshold for platform display
   - "No clear favorite" message for low-confidence predictions

5. **Profile System (Earlier October 2025)**
   - ProfileScreen with user settings
   - FavoriteStationsScreen for managing favorites
   - AdvancedConfigScreen with server switching
   - BackendHealthService for environment validation
   - EnvironmentManager for debug builds

6. **Ongoing Notifications (Earlier October 2025)**
   - `TrainTrackingService` foreground service
   - 30-second updates via AlarmManager
   - Custom notification layouts with RemoteViews
   - Journey progress, next stop, and delay display
   - Auto-stop on train arrival
   - TrackingStateRepository for persistent state

### Earlier Enhancements (September 2025)

1. **Enhanced Navigation System**
   - Type-safe navigation with Jetpack Compose Navigation
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

5. **DepartureV2 API Integration**
   - Enhanced departure data with train position
   - Data freshness indicators
   - StatusV2 integration for better status display

## Contact for Support

When working on the Android app:
- Follow this guide for implementation details
- Reference `android-app.md` for requirements
- Check iOS implementation for feature parity
- Consult backend documentation for API details
- Use Material Design guidelines for UI decisions

Remember: The goal is to create a native Android experience that matches iOS functionality while feeling natural to Android users.