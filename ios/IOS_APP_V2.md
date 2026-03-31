# TrackRat iOS App v2 Architecture

## Executive Summary

TrackRat v2 is a complete rewrite focusing on simplicity, maintainability, and iOS best practices. The app provides real-time NJ Transit and Amtrak train tracking with Live Activity support for iPhone Lock Screen and Dynamic Island.

### Core Principles
1. **Radical Simplicity**: Every line of code must justify its existence
2. **Native First**: Use iOS conventions and components wherever possible
3. **Single Responsibility**: Each component does one thing well
4. **No Backwards Compatibility**: Clean slate design
5. **Fail Gracefully**: Network issues should never crash the app

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    SwiftUI App                          │
├─────────────────┬─────────────────┬────────────────────┤
│   Views         │  View Models    │     Services       │
├─────────────────┼─────────────────┼────────────────────┤
│ • HomeView      │ • TrainListVM   │ • APIClient        │
│ • TrainListView │ • TrainDetailVM │ • LiveActivityMgr  │
│ • TrainDetail   │                 │ • NotificationSvc  │
└─────────────────┴─────────────────┴────────────────────┘
                           │
                    ┌──────┴──────┐
                    │   Models    │
                    ├─────────────┤
                    │ • Train     │
                    │ • Station   │
                    │ • Trip      │
                    └─────────────┘
```

## Data Models

### Core Domain Models

```swift
// MARK: - Station
struct Station: Identifiable, Codable, Hashable {
    let id: String      // "NY", "NP", "TR", etc.
    let name: String    // "New York Penn Station"
    let shortName: String // "NY Penn"
}

// MARK: - Train Status
enum TrainStatus: String, Codable {
    case onTime = "ON_TIME"
    case delayed = "DELAYED"
    case boarding = "BOARDING"
    case departed = "DEPARTED"
    case arrived = "ARRIVED"
    case cancelled = "CANCELLED"
}

// MARK: - Train
struct Train: Identifiable, Codable {
    let id: String              // "3949"
    let line: String            // "Northeast Corridor"
    let destination: String     // "TRENTON"
    let status: TrainStatus
    let scheduledDeparture: Date
    let actualDeparture: Date?  // nil if not departed
    let track: String?          // nil if not assigned
    let stops: [Stop]
    
    // Computed properties for UI
    var displayTime: Date { actualDeparture ?? scheduledDeparture }
    var delayMinutes: Int? {
        guard let actual = actualDeparture else { return nil }
        return Int(actual.timeIntervalSince(scheduledDeparture) / 60)
    }
    var isActive: Bool {
        status != .arrived && status != .cancelled
    }
}

// MARK: - Stop
struct Stop: Identifiable, Codable {
    let id: String              // "NY-3949-0"
    let stationId: String       // "NY"
    let stationName: String     // "New York Penn Station"
    let scheduledTime: Date
    let actualTime: Date?
    let isDeparted: Bool
    
    var displayTime: Date { actualTime ?? scheduledTime }
}

// MARK: - Trip (User Selection)
struct Trip: Identifiable, Codable, Hashable {
    let id = UUID()
    let originId: String
    let destinationId: String
    let originName: String
    let destinationName: String
    
    var displayName: String {
        "\(originName) → \(destinationName)"
    }
}
```

### API Response Models

```swift
// MARK: - API Response Wrapper
struct APIResponse<T: Codable>: Codable {
    let data: T
    let timestamp: Date
}

// MARK: - Train List Response
struct TrainListResponse: Codable {
    let trains: [Train]
    let nextUpdate: Date?
}

// MARK: - Error Response
struct APIError: Error, Codable {
    let message: String
    let code: String
}
```

### Live Activity Models

```swift
// MARK: - Live Activity Content State
struct TrainActivityContent: Codable {
    let trainId: String
    let line: String
    let destination: String
    let status: TrainStatus
    let track: String?
    let nextStop: String?
    let minutesToNextStop: Int?
    let lastUpdated: Date
}

// MARK: - Push Notification Payload
struct ActivityUpdatePayload: Codable {
    let trainId: String
    let event: UpdateEvent
    
    enum UpdateEvent: String, Codable {
        case trackAssigned
        case nowBoarding
        case departed
        case approachingStop
        case arrived
    }
}
```

## User Interface Flow

### Navigation Structure

```
HomeView (Tab 1)
├── Recent Trips (List)
├── Search Button → StationPicker (Modal)
│   ├── Origin Selection
│   └── Destination Selection
└── Selected Trip → TrainListView
    └── Train Row → TrainDetailView
        └── Start Tracking → Live Activity

Direct Search (Tab 2)
└── Train Number Input → TrainDetailView
```

### View Specifications

#### HomeView
```swift
struct HomeView: View {
    @StateObject private var viewModel = HomeViewModel()
    @State private var showingStationPicker = false
    @State private var selectedTrip: Trip?
    
    var body: some View {
        NavigationStack {
            ScrollView {
                // Recent trips section
                RecentTripsSection(trips: viewModel.recentTrips) { trip in
                    selectedTrip = trip
                }
                
                // Search button
                Button("Search Trains") {
                    showingStationPicker = true
                }
            }
            .navigationTitle("TrackRat")
            .navigationDestination(item: $selectedTrip) { trip in
                TrainListView(trip: trip)
            }
            .sheet(isPresented: $showingStationPicker) {
                StationPicker { origin, destination in
                    let trip = Trip(
                        originId: origin.id,
                        destinationId: destination.id,
                        originName: origin.name,
                        destinationName: destination.name
                    )
                    viewModel.saveRecentTrip(trip)
                    selectedTrip = trip
                }
            }
        }
    }
}
```

#### StationPicker
```swift
struct StationPicker: View {
    @State private var origin: Station?
    @State private var destination: Station?
    let onSelection: (Station, Station) -> Void
    
    private let stations = [
        Station(id: "NY", name: "New York Penn Station", shortName: "NY Penn"),
        Station(id: "NP", name: "Newark Penn Station", shortName: "Newark"),
        Station(id: "TR", name: "Trenton Transit Center", shortName: "Trenton"),
        Station(id: "PJ", name: "Princeton Junction", shortName: "Princeton"),
        Station(id: "MP", name: "Metropark", shortName: "Metropark")
    ]
    
    var body: some View {
        NavigationStack {
            Form {
                Picker("From", selection: $origin) {
                    Text("Select Station").tag(nil as Station?)
                    ForEach(stations) { station in
                        Text(station.name).tag(station as Station?)
                    }
                }
                
                Picker("To", selection: $destination) {
                    Text("Select Station").tag(nil as Station?)
                    ForEach(stations.filter { $0.id != origin?.id }) { station in
                        Text(station.name).tag(station as Station?)
                    }
                }
            }
            .navigationTitle("Select Trip")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { /* dismiss */ }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Search") {
                        if let origin, let destination {
                            onSelection(origin, destination)
                        }
                    }
                    .disabled(origin == nil || destination == nil)
                }
            }
        }
    }
}
```

#### TrainListView
```swift
struct TrainListView: View {
    let trip: Trip
    @StateObject private var viewModel: TrainListViewModel
    
    init(trip: Trip) {
        self.trip = trip
        self._viewModel = StateObject(wrappedValue: TrainListViewModel(trip: trip))
    }
    
    var body: some View {
        List(viewModel.trains) { train in
            NavigationLink(value: train) {
                TrainRow(train: train, trip: trip)
            }
        }
        .navigationTitle(trip.displayName)
        .navigationBarTitleDisplayMode(.inline)
        .refreshable {
            await viewModel.refresh()
        }
        .onAppear {
            viewModel.startAutoRefresh()
        }
        .onDisappear {
            viewModel.stopAutoRefresh()
        }
        .overlay {
            if viewModel.isLoading && viewModel.trains.isEmpty {
                ProgressView()
            }
        }
        .navigationDestination(for: Train.self) { train in
            TrainDetailView(train: train, trip: trip)
        }
    }
}
```

#### TrainRow
```swift
struct TrainRow: View {
    let train: Train
    let trip: Trip
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Train \(train.id)")
                    .font(.headline)
                Text(train.line)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            
            Spacer()
            
            VStack(alignment: .trailing, spacing: 4) {
                Text(train.displayTime, style: .time)
                    .font(.headline)
                
                if let delay = train.delayMinutes, delay > 0 {
                    Text("+\(delay) min")
                        .font(.caption)
                        .foregroundStyle(.red)
                }
                
                if let track = train.track {
                    Text("Track \(track)")
                        .font(.caption)
                        .foregroundStyle(.orange)
                        .bold()
                }
            }
        }
        .padding(.vertical, 4)
        .background(train.status == .boarding ? Color.orange.opacity(0.1) : Color.clear)
        .cornerRadius(8)
    }
}
```

#### TrainDetailView
```swift
struct TrainDetailView: View {
    let train: Train
    let trip: Trip
    @StateObject private var viewModel: TrainDetailViewModel
    @State private var isTrackingActive = false
    
    init(train: Train, trip: Trip) {
        self.train = train
        self.trip = trip
        self._viewModel = StateObject(wrappedValue: TrainDetailViewModel(trainId: train.id))
    }
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Header
                TrainHeaderView(train: viewModel.train)
                
                // Live Activity Control
                LiveActivityButton(
                    isActive: $isTrackingActive,
                    train: viewModel.train
                )
                
                // Stops
                StopsListView(
                    stops: viewModel.train.stops,
                    currentStopIndex: viewModel.currentStopIndex
                )
            }
            .padding()
        }
        .navigationTitle("Train \(train.id)")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            viewModel.startAutoRefresh()
        }
        .onDisappear {
            viewModel.stopAutoRefresh()
        }
    }
}
```

## Services Architecture

### APIClient
```swift
final class APIClient {
    static let shared = APIClient()
    private let baseURL = "https://api.trackrat.net/api"
    private let session = URLSession.shared
    
    // MARK: - Train Operations
    func fetchTrains(from: String, to: String, after: Date) async throws -> [Train] {
        let url = URL(string: "\(baseURL)/trains")!
            .appending(queryItems: [
                URLQueryItem(name: "from_station_code", value: from),
                URLQueryItem(name: "to_station_code", value: to),
                URLQueryItem(name: "departure_time_after", value: ISO8601DateFormatter().string(from: after))
            ])
        
        let (data, _) = try await session.data(from: url)
        let response = try JSONDecoder.trackRat.decode(TrainListResponse.self, from: data)
        return response.trains
    }
    
    func fetchTrain(id: String, from: String) async throws -> Train {
        let url = URL(string: "\(baseURL)/trains/\(id)")!
            .appending(queryItems: [
                URLQueryItem(name: "from_station_code", value: from)
            ])
        
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder.trackRat.decode(Train.self, from: data)
    }
    
    // MARK: - Notification Operations
    func registerDevice(token: Data) async throws {
        var request = URLRequest(url: URL(string: "\(baseURL)/notifications/device-tokens")!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode([
            "token": token.hexString,
            "platform": "ios"
        ])
        
        let (_, response) = try await session.data(for: request)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else {
            throw APIError(message: "Failed to register device", code: "DEVICE_REGISTRATION_FAILED")
        }
    }
}

// MARK: - JSON Decoder Extension
extension JSONDecoder {
    static let trackRat: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let dateString = try container.decode(String.self)
            
            // Try ISO8601 with fractional seconds first
            if let date = ISO8601DateFormatter.withFractionalSeconds.date(from: dateString) {
                return date
            }
            
            // Fallback to standard ISO8601
            if let date = ISO8601DateFormatter().date(from: dateString) {
                return date
            }
            
            throw DecodingError.dataCorrupted(.init(
                codingPath: decoder.codingPath,
                debugDescription: "Invalid date format: \(dateString)"
            ))
        }
        return decoder
    }()
}
```

### LiveActivityManager
```swift
import ActivityKit

final class LiveActivityManager {
    static let shared = LiveActivityManager()
    private var currentActivity: Activity<TrainActivityAttributes>?
    
    // MARK: - Activity Lifecycle
    func startTracking(train: Train) async throws {
        guard ActivityAuthorizationInfo().areActivitiesEnabled else {
            throw LiveActivityError.activitiesDisabled
        }
        
        // End any existing activity
        if let current = currentActivity {
            await endTracking()
        }
        
        // Create activity attributes
        let attributes = TrainActivityAttributes(
            trainId: train.id,
            line: train.line,
            destination: train.destination
        )
        
        // Create initial content state
        let initialState = TrainActivityContent(
            trainId: train.id,
            line: train.line,
            destination: train.destination,
            status: train.status,
            track: train.track,
            nextStop: train.stops.first { !$0.isDeparted }?.stationName,
            minutesToNextStop: nil,
            lastUpdated: Date()
        )
        
        // Start activity
        let activity = try Activity.request(
            attributes: attributes,
            content: .init(state: initialState, staleDate: nil),
            pushType: .token
        )
        
        currentActivity = activity
        
        // Register for push updates
        if let token = activity.pushToken {
            try await NotificationService.shared.registerLiveActivity(
                activityId: activity.id,
                token: token,
                trainId: train.id
            )
        }
    }
    
    func updateActivity(with train: Train) async {
        guard let activity = currentActivity else { return }
        
        let updatedState = TrainActivityContent(
            trainId: train.id,
            line: train.line,
            destination: train.destination,
            status: train.status,
            track: train.track,
            nextStop: train.stops.first { !$0.isDeparted }?.stationName,
            minutesToNextStop: calculateMinutesToNextStop(train: train),
            lastUpdated: Date()
        )
        
        await activity.update(
            ActivityContent(state: updatedState, staleDate: nil)
        )
    }
    
    func endTracking() async {
        guard let activity = currentActivity else { return }
        
        await activity.end(
            ActivityContent(state: activity.content.state, staleDate: nil),
            dismissalPolicy: .immediate
        )
        
        currentActivity = nil
    }
    
    // MARK: - Helpers
    private func calculateMinutesToNextStop(train: Train) -> Int? {
        guard let nextStop = train.stops.first(where: { !$0.isDeparted }) else {
            return nil
        }
        
        let now = Date()
        let timeToStop = nextStop.displayTime.timeIntervalSince(now)
        return Int(timeToStop / 60)
    }
}

// MARK: - Live Activity Attributes
struct TrainActivityAttributes: ActivityAttributes {
    let trainId: String
    let line: String
    let destination: String
}
```

### NotificationService
```swift
import UserNotifications

final class NotificationService: NSObject {
    static let shared = NotificationService()
    
    override init() {
        super.init()
        UNUserNotificationCenter.current().delegate = self
    }
    
    // MARK: - Device Registration
    func requestAuthorization() async throws {
        let center = UNUserNotificationCenter.current()
        let granted = try await center.requestAuthorization(options: [.alert, .sound, .badge])
        
        guard granted else {
            throw NotificationError.authorizationDenied
        }
        
        await MainActor.run {
            UIApplication.shared.registerForRemoteNotifications()
        }
    }
    
    func handleDeviceToken(_ token: Data) async throws {
        try await APIClient.shared.registerDevice(token: token)
        UserDefaults.standard.set(token, forKey: "deviceToken")
    }
    
    // MARK: - Live Activity Registration
    func registerLiveActivity(activityId: String, token: Data, trainId: String) async throws {
        var request = URLRequest(url: URL(string: "\(APIClient.shared.baseURL)/notifications/live-activities/register")!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode([
            "activity_id": activityId,
            "push_token": token.hexString,
            "train_id": trainId,
            "device_token": UserDefaults.standard.data(forKey: "deviceToken")?.hexString ?? ""
        ])
        
        let (_, response) = try await URLSession.shared.data(for: request)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else {
            throw NotificationError.registrationFailed
        }
    }
}

// MARK: - UNUserNotificationCenterDelegate
extension NotificationService: UNUserNotificationCenterDelegate {
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse
    ) async {
        // Handle notification taps
        let userInfo = response.notification.request.content.userInfo
        if let trainId = userInfo["train_id"] as? String {
            // Navigate to train detail
            NotificationCenter.default.post(
                name: .navigateToTrain,
                object: nil,
                userInfo: ["trainId": trainId]
            )
        }
    }
}
```

## View Models

### TrainListViewModel
```swift
@MainActor
final class TrainListViewModel: ObservableObject {
    @Published var trains: [Train] = []
    @Published var isLoading = false
    @Published var error: Error?
    
    private let trip: Trip
    private var refreshTimer: Timer?
    
    init(trip: Trip) {
        self.trip = trip
        Task {
            await loadTrains()
        }
    }
    
    func loadTrains() async {
        isLoading = true
        error = nil
        
        do {
            trains = try await APIClient.shared.fetchTrains(
                from: trip.originId,
                to: trip.destinationId,
                after: Date()
            )
        } catch {
            self.error = error
        }
        
        isLoading = false
    }
    
    func refresh() async {
        await loadTrains()
    }
    
    func startAutoRefresh() {
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { _ in
            Task {
                await self.loadTrains()
            }
        }
    }
    
    func stopAutoRefresh() {
        refreshTimer?.invalidate()
        refreshTimer = nil
    }
}
```

### TrainDetailViewModel
```swift
@MainActor
final class TrainDetailViewModel: ObservableObject {
    @Published var train: Train
    @Published var isLoading = false
    @Published var currentStopIndex: Int = 0
    
    private let trainId: String
    private var refreshTimer: Timer?
    
    init(trainId: String) {
        self.trainId = trainId
        self.train = Train(
            id: trainId,
            line: "Loading...",
            destination: "Loading...",
            status: .onTime,
            scheduledDeparture: Date(),
            actualDeparture: nil,
            track: nil,
            stops: []
        )
        
        Task {
            await loadTrainDetails()
        }
    }
    
    func loadTrainDetails() async {
        isLoading = true
        
        do {
            // For now, use NY as default origin - in real app, pass this through
            train = try await APIClient.shared.fetchTrain(
                id: trainId,
                from: "NY"
            )
            updateCurrentStop()
        } catch {
            // Handle error
        }
        
        isLoading = false
    }
    
    func startAutoRefresh() {
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { _ in
            Task {
                await self.loadTrainDetails()
            }
        }
    }
    
    func stopAutoRefresh() {
        refreshTimer?.invalidate()
        refreshTimer = nil
    }
    
    private func updateCurrentStop() {
        if let index = train.stops.firstIndex(where: { !$0.isDeparted }) {
            currentStopIndex = index
        }
    }
}
```

## Technical Implementation Details

### App Configuration
```swift
@main
struct TrackRatApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .preferredColorScheme(.dark)
                .tint(.orange)
        }
    }
}

class AppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        // Request notification permissions
        Task {
            try? await NotificationService.shared.requestAuthorization()
        }
        return true
    }
    
    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        Task {
            try? await NotificationService.shared.handleDeviceToken(deviceToken)
        }
    }
}
```

### Storage
```swift
// Simple UserDefaults-based storage for v2
extension UserDefaults {
    private enum Keys {
        static let recentTrips = "recentTrips"
        static let favoriteTrains = "favoriteTrains"
    }
    
    var recentTrips: [Trip] {
        get {
            guard let data = data(forKey: Keys.recentTrips) else { return [] }
            return (try? JSONDecoder().decode([Trip].self, from: data)) ?? []
        }
        set {
            let data = try? JSONEncoder().encode(Array(newValue.prefix(5)))
            set(data, forKey: Keys.recentTrips)
        }
    }
}
```

### Error Handling
```swift
enum TrackRatError: LocalizedError {
    case networkError(Error)
    case decodingError(Error)
    case noTrainsFound
    case invalidStation
    
    var errorDescription: String? {
        switch self {
        case .networkError:
            return "Unable to connect. Please check your connection."
        case .decodingError:
            return "Unable to process data. Please try again."
        case .noTrainsFound:
            return "No trains found for this route."
        case .invalidStation:
            return "Invalid station selection."
        }
    }
}
```

### Constants
```swift
enum Constants {
    static let refreshInterval: TimeInterval = 30
    static let staleDataThreshold: TimeInterval = 300 // 5 minutes
    
    enum API {
        static let baseURL = "https://api.trackrat.net/api"
        static let timeout: TimeInterval = 15
    }
    
    enum UI {
        static let cornerRadius: CGFloat = 12
        static let padding: CGFloat = 16
        static let accentColor = Color.orange
    }
}
```

## Testing Strategy

### Unit Tests
```swift
// Test data models
class TrainModelTests: XCTestCase {
    func testTrainDecoding() throws {
        let json = """
        {
            "id": "3949",
            "line": "Northeast Corridor",
            "destination": "TRENTON",
            "status": "ON_TIME",
            "scheduled_departure": "2024-01-15T14:30:00",
            "track": "7",
            "stops": []
        }
        """.data(using: .utf8)!
        
        let train = try JSONDecoder.trackRat.decode(Train.self, from: json)
        XCTAssertEqual(train.id, "3949")
        XCTAssertEqual(train.track, "7")
    }
}

// Test view models
class TrainListViewModelTests: XCTestCase {
    func testLoadTrains() async {
        let trip = Trip(
            originId: "NY",
            destinationId: "TR",
            originName: "New York",
            destinationName: "Trenton"
        )
        let viewModel = TrainListViewModel(trip: trip)
        
        await viewModel.loadTrains()
        
        XCTAssertFalse(viewModel.trains.isEmpty)
        XCTAssertFalse(viewModel.isLoading)
    }
}
```

### UI Tests
```swift
class TrackRatUITests: XCTestCase {
    func testTrainSelection() throws {
        let app = XCUIApplication()
        app.launch()
        
        // Test trip selection flow
        app.buttons["Search Trains"].tap()
        app.pickers["From"].tap()
        app.pickerWheels.element.adjust(toPickerWheelValue: "New York Penn Station")
        
        app.pickers["To"].tap()
        app.pickerWheels.element.adjust(toPickerWheelValue: "Trenton Transit Center")
        
        app.buttons["Search"].tap()
        
        // Verify train list appears
        XCTAssert(app.tables.cells.count > 0)
    }
}
```

## Performance Considerations

1. **Lazy Loading**: Use List instead of ScrollView + VStack for train lists
2. **Image Caching**: If adding images later, use AsyncImage with caching
3. **Background Updates**: Limit to active Live Activities only
4. **Memory Management**: Clear old data when navigating away
5. **Network Optimization**: Batch requests where possible

## Migration from v1

Since we're not maintaining backwards compatibility:

1. **Clean Install**: Users must delete v1 and install v2
2. **No Data Migration**: Fresh start with no imported data
3. **Settings Reset**: All preferences start fresh
4. **New Bundle ID**: `com.trackrat.ios.v2`

## Future Enhancements

These are explicitly NOT in v2 scope but could be added later:

1. **Widget Extension**: Home screen widgets for favorite trains
2. **Apple Watch App**: Companion app for quick glances
3. **Siri Shortcuts**: "Hey Siri, when's my train?"
4. **Offline Schedule Cache**: Download schedules for offline viewing
5. **Multi-Language Support**: Spanish, Chinese, etc.
6. **Accessibility**: Full VoiceOver support and Dynamic Type

## Summary

TrackRat v2 embraces radical simplicity while delivering core functionality:

- **Minimal Models**: Only essential fields, no legacy support
- **Simple Navigation**: 3-level hierarchy maximum
- **Native UI**: Standard iOS components with light customization
- **Clear Services**: Single-responsibility service classes
- **Smart Defaults**: Opinionated choices that work for 90% of users
- **No Feature Creep**: Core functionality only, executed perfectly

The entire app should be implementable in under 2,000 lines of Swift code, making it maintainable, testable, and performant.