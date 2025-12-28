import SwiftUI
import ActivityKit
import WidgetKit
import UserNotifications
import BackgroundTasks

let BACKGROUND_REFRESH_TASK_ID = "com.trackrat.backgroundrefresh"

@main
struct TrackRatApp: App {
    @StateObject private var appState = AppState()
    @ObservedObject private var themeManager = ThemeManager.shared
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @Environment(\.scenePhase) private var scenePhase
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false
    
    var body: some Scene {
        WindowGroup {
            Group {
                if hasCompletedOnboarding {
                    ContentView()
                } else {
                    OnboardingView()
                }
            }
            .environmentObject(appState)
            .environmentObject(themeManager)
            .preferredColorScheme(themeManager.colorScheme)
            .tint(themeManager.tintColor)
            .onOpenURL { url in
                print("🔗 App received URL: \(url)")
                DeepLinkService.shared.handleOpenURL(url, appState: appState)
            }
            .onChange(of: scenePhase) { _, newPhase in
                switch newPhase {
                case .active:
                    print("📱 Scene Phase Active: Triggering backend wake-up...")
                    Task {
                        BackendWakeupService.shared.wakeupBackend()
                    }
                case .inactive:
                    print("📱 Scene Phase Inactive")
                case .background:
                    print("📱 Scene Phase Background")
                @unknown default:
                    break
                }
            }
        }
    }
    
    init() {
        // Live Activity widget configuration handled by TrainLiveActivityBundle
    }
}

// Create a new AppDelegate class to handle notification delegate methods
class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    // Store device token for Live Activity registration
    private static var storedDeviceToken: String?

    @MainActor static var deviceToken: String? {
        get { storedDeviceToken }
        set { storedDeviceToken = newValue }
    }

    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey : Any]? = nil) -> Bool {
        // Set up notification delegate
        UNUserNotificationCenter.current().delegate = self
        setupNotificationCategories()
        registerBackgroundTasks()

        // Request notification permissions (required for Live Activities)
        Task {
            await requestNotificationPermissions()
        }

        // Register for remote notifications (push notifications)
        application.registerForRemoteNotifications()

        // Wake up backend on app launch
        print("📱 App Launch: Triggering backend wake-up...")
        Task {
            BackendWakeupService.shared.wakeupBackend()
        }

        return true
    }
    
    /// Request notification permissions (required for Live Activities)
    private func requestNotificationPermissions() async {
        do {
            let granted = try await UNUserNotificationCenter.current().requestAuthorization(
                options: [.alert, .sound, .badge, .provisional]
            )
            print("🔔 Notification permission granted: \(granted)")
            
            if granted {
                print("✅ Notifications enabled - Live Activities should work")
            } else {
                print("❌ Notifications denied - Live Activities will not work")
                print("💡 User needs to enable notifications in Settings for Live Activities")
            }
        } catch {
            print("❌ Failed to request notification permissions: \(error)")
        }
    }

    func registerBackgroundTasks() {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: BACKGROUND_REFRESH_TASK_ID, using: nil) { task in
            guard let bgTask = task as? BGAppRefreshTask else {
                task.setTaskCompleted(success: false)
                return
            }
            self.handleAppRefresh(task: bgTask)
        }
    }

    // Handle foreground notifications
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification, withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound, .badge]) // Show banner, play sound, update badge
    }

    // Handle user interaction with notifications
    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse, withCompletionHandler completionHandler: @escaping () -> Void) {
        // Here you can add logic to navigate to a specific part of your app based on the notification
        completionHandler()
    }
    
    // MARK: - Push Notification Delegate Methods
    
    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let tokenString = deviceToken.map { String(format: "%02x", $0) }.joined()

        #if DEBUG
        print("📱 Device token received: \(tokenString)")
        if let bundleId = Bundle.main.bundleIdentifier {
            print("📱 iOS App Bundle ID: \(bundleId)")
        }
        #endif

        // Store device token for Live Activity registration
        Task { @MainActor in
            AppDelegate.deviceToken = tokenString
        }

        #if DEBUG
        print("📱 Device token stored - Live Activities ready")
        #endif
    }
    
    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        print("❌ Failed to register for remote notifications: \(error)")
        // Continue without push notifications - Live Activities can still work with local updates
    }
    
    func application(_ application: UIApplication, didReceiveRemoteNotification userInfo: [AnyHashable : Any], fetchCompletionHandler completionHandler: @escaping (UIBackgroundFetchResult) -> Void) {
        print("📥 Received remote notification: \(userInfo)")
        
        // Handle Live Activity push notifications (standard Apple format)
        if let aps = userInfo["aps"] as? [String: Any] {
            print("🔄 Processing Live Activity push notification with aps payload")
            print("📋 APS Keys: \(Array(aps.keys))")
            
            // Check if this is a Live Activity update (has content-state or event field)
            if aps["content-state"] != nil || aps["event"] != nil {
                print("✅ Detected Live Activity update in push notification")
                print("⏰ Timestamp: \(aps["timestamp"] ?? "none")")
                print("🎯 Event: \(aps["event"] ?? "none")")
                Task {
                    await handleLiveActivityPushUpdate(userInfo)
                    completionHandler(.newData)
                }
                return
            } else {
                print("ℹ️ APS payload doesn't contain Live Activity fields")
            }
        }
        
        // Handle legacy format (custom live_activity_update flag)
        if userInfo["live_activity_update"] as? Bool == true {
            print("🔄 Processing legacy Live Activity push notification")
            Task {
                await handleLiveActivityPushUpdate(userInfo)
                completionHandler(.newData)
            }
        } else {
            print("ℹ️ Push notification is not a Live Activity update")
            completionHandler(.noData)
        }
    }
    
    // MARK: - Push Notification Helpers
    
    private func handleLiveActivityPushUpdate(_ userInfo: [AnyHashable: Any]) async {
        print("🔄 Live Activity Update Source: Server push notification (APNS)")
        print("📦 Full payload: \(userInfo)")
        
        // Extract the aps payload
        guard let aps = userInfo["aps"] as? [String: Any] else {
            print("❌ No aps payload found in Live Activity push notification")
            return
        }
        
        // Log the content-state for debugging
        if let contentState = aps["content-state"] as? [String: Any] {
            print("📊 Content State Keys: \(Array(contentState.keys))")
            if let progress = contentState["journeyProgress"] as? Double {
                print("  - Server calculated progress: \(progress)")
            }
            if let trainNumber = contentState["trainNumber"] as? String {
                print("🚂 Train Number: \(trainNumber)")
            }
            if let statusV2 = contentState["statusV2"] as? String {
                print("📍 Status V2: \(statusV2)")
            }
            if let track = contentState["track"] as? String {
                print("🛤️ Track: \(track)")
            }
        }
        
        // Check if we have an active Live Activity
        guard let currentActivity = LiveActivityService.shared.currentActivity else {
            print("⚠️ No active Live Activity found, ignoring push update")
            return
        }
        
        // Extract event type from top level or aps.alert
        let eventType = userInfo["event_type"] as? String
        
        print("🎯 Event Type: \(eventType ?? "none")")
        
        // Check for critical events that should trigger banner notifications
        await handleCriticalEventNotification(userInfo)
        
        // Handle specific event types
        if let eventType = eventType {
            switch eventType {
            case "stop_departure":
                await handleStopDeparturePush(userInfo)
            case "approaching_stop":
                await handleApproachingStopPush(userInfo)
            case "train_update":
                await handleTrainDataUpdate(userInfo)
            default:
                print("⚠️ Unknown event type: \(eventType)")
                // Still update the Live Activity with new content-state
                await LiveActivityService.shared.fetchAndUpdateTrain()
            }
        } else {
            // No specific event type, just update the Live Activity with new data
            print("ℹ️ No event type, updating Live Activity with new content-state")
            await LiveActivityService.shared.fetchAndUpdateTrain()
        }
        
        print("✅ Live Activity push update processing complete")
    }
    
    private func handleTrainDataUpdate(_ userInfo: [AnyHashable: Any]) async {
        // Extract train data from push notification
        guard let trainData = userInfo["train_data"] as? [String: Any],
              let trainId = trainData["train_id"] as? String else {
            print("❌ Invalid Live Activity push notification data")
            return
        }
        
        // Update Live Activity if it matches current activity
        if let currentActivity = LiveActivityService.shared.currentActivity,
           currentActivity.attributes.trainId == trainId || currentActivity.attributes.trainNumber == trainId {
            await LiveActivityService.shared.fetchAndUpdateTrain()
            print("✅ Live Activity updated from push notification")
        } else {
            print("ℹ️ Push notification for different train, ignoring")
            print("ℹ️ Expected trainId: \(LiveActivityService.shared.currentActivity?.attributes.trainId ?? "none")")
            print("ℹ️ Expected trainNumber: \(LiveActivityService.shared.currentActivity?.attributes.trainNumber ?? "none")")
            print("ℹ️ Received trainId: \(trainId)")
        }
    }
    
    private func handleStopDeparturePush(_ userInfo: [AnyHashable: Any]) async {
        guard let eventData = userInfo["event_data"] as? [String: Any],
              let stationName = eventData["station"] as? String,
              let isOrigin = eventData["is_origin"] as? Bool,
              let stopsRemaining = eventData["stops_remaining"] as? Int else {
            print("❌ Invalid stop departure push data")
            return
        }
        
        // The Live Activity update will trigger the Dynamic Island alert
        // Just fetch and update the train data
        await LiveActivityService.shared.fetchAndUpdateTrain()
    }
    
    private func handleApproachingStopPush(_ userInfo: [AnyHashable: Any]) async {
        print("🚂 Processing approaching_stop event")
        
        guard let eventData = userInfo["event_data"] as? [String: Any],
              let stationName = eventData["station"] as? String,
              let minutesAway = eventData["minutes_away"] as? Int,
              let isDestination = eventData["is_destination"] as? Bool else {
            print("❌ Invalid approaching stop push data")
            print("📦 Available userInfo keys: \(Array(userInfo.keys))")
            if let eventData = userInfo["event_data"] as? [String: Any] {
                print("📦 Available event_data keys: \(Array(eventData.keys))")
            }
            return
        }
        
        print("📍 Approaching \(stationName) in \(minutesAway) minutes (destination: \(isDestination))")
        
        // The Live Activity update will trigger the Dynamic Island alert
        await LiveActivityService.shared.fetchAndUpdateTrain()
        
        print("✅ Approaching stop event processing complete")
    }
    
    /// Handle critical events that should trigger banner notifications alongside Live Activity updates
    private func handleCriticalEventNotification(_ userInfo: [AnyHashable: Any]) async {
        guard let aps = userInfo["aps"] as? [String: Any],
              let contentState = aps["content-state"] as? [String: Any],
              let alertMetadata = contentState["alertMetadata"] as? [String: Any] else {
            return
        }
        
        // Extract alert metadata
        guard let alertType = alertMetadata["alert_type"] as? String,
              let trainId = alertMetadata["train_id"] as? String,
              let priority = alertMetadata["dynamic_island_priority"] as? String else {
            return
        }
        
        // Only send banner notifications for high-priority events
        guard priority == "urgent" || priority == "high" else { return }
        
        // Get alert content from aps.alert if available
        if let alert = aps["alert"] as? [String: Any],
           let title = alert["title"] as? String,
           let body = alert["body"] as? String {
            
            // Use the existing LiveActivityService function to send banner notification
            await LiveActivityService.shared.sendCriticalBannerNotification(
                title: title,
                body: body,
                priority: priority,
                trainId: trainId
            )
        } else {
            // Fallback: create notification based on alert type
            let (title, body) = createFallbackNotification(alertType: alertType, contentState: contentState)
            
            await LiveActivityService.shared.sendCriticalBannerNotification(
                title: title,
                body: body,
                priority: priority, 
                trainId: trainId
            )  
        }
    }
    
    /// Create fallback notification content when aps.alert is not available
    private func createFallbackNotification(alertType: String, contentState: [String: Any]) -> (String, String) {
        let trainNumber = contentState["trainNumber"] as? String ?? "Train"
        
        switch alertType {
        case "track_assigned":
            let track = contentState["track"] as? String ?? "TBD"
            return ("Track Assigned! 🚂", "Track \(track) - Get Ready to Board")
        case "boarding":
            return ("Time to Board! 🚆", "\(trainNumber) is now boarding")
        case "departure":
            return ("Train Departed 🚄", "\(trainNumber) has left the station")
        case "approaching":
            return ("Approaching Stop 📍", "\(trainNumber) approaching next station")
        case "delay":
            let delayMinutes = contentState["delayMinutes"] as? Int ?? 0
            return ("Delay Alert ⏰", "\(trainNumber) delayed by \(delayMinutes) minutes")
        default:
            return ("Train Update 🚂", "\(trainNumber) status updated")
        }
    }
    
    /// Setup notification categories for critical train updates
    private func setupNotificationCategories() {
        let criticalCategory = UNNotificationCategory(
            identifier: "CRITICAL_TRAIN_UPDATE",
            actions: [],
            intentIdentifiers: [],
            options: [.customDismissAction, .allowInCarPlay]
        )
        
        UNUserNotificationCenter.current().setNotificationCategories([criticalCategory])
        print("📱 Notification categories configured")
    }

    func scheduleAppRefresh() {
        let request = BGAppRefreshTaskRequest(identifier: BACKGROUND_REFRESH_TASK_ID)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60) // 15 minutes from now
        do {
            try BGTaskScheduler.shared.submit(request)
            print("Background refresh task scheduled.")
        } catch {
            print("Could not schedule app refresh: \(error)")
        }
    }

    func handleAppRefresh(task: BGAppRefreshTask) {
        print("Background task started: \(task.identifier)")

        // Schedule the next refresh right away
        scheduleAppRefresh()

        task.expirationHandler = {
            // Handle cleanup, e.g., cancel network requests
            print("Background task expired: \(task.identifier)")
            task.setTaskCompleted(success: false)
        }

        // Ensure there's an active activity to update
        guard let activityAttributes = LiveActivityService.shared.currentActivity?.attributes else {
            print("No active Live Activity to update in background.")
            task.setTaskCompleted(success: true) // No work to do, but task is "complete"
            return
        }

        print("Performing background fetch for Live Activity: Train \(activityAttributes.trainNumber)")

        // Use Task with proper completion and timeout
        Task {
            do {
                // Add 25-second timeout to prevent hanging
                try await withTimeout(seconds: 25) {
                    await LiveActivityService.shared.fetchAndUpdateTrain()
                }
                print("Background fetch completed successfully for Live Activity: Train \(activityAttributes.trainNumber)")
                task.setTaskCompleted(success: true)
            } catch {
                print("Background fetch failed or timed out: \(error)")
                task.setTaskCompleted(success: false)
            }
        }
    }

    // Helper function for timeout
    private func withTimeout<T>(seconds: TimeInterval, operation: @escaping () async throws -> T) async throws -> T {
        try await withThrowingTaskGroup(of: T.self) { group in
            // Add the actual operation
            group.addTask {
                try await operation()
            }

            // Add timeout task
            group.addTask {
                try await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000))
                throw CancellationError()
            }

            // Wait for first to complete and cancel the other
            guard let result = try await group.next() else {
                group.cancelAll()
                throw CancellationError()
            }
            group.cancelAll()
            return result
        }
    }

    func cancelAllPendingBackgroundTasks() {
        BGTaskScheduler.shared.cancelAllTaskRequests()
        print("All pending background tasks cancelled.")
    }
    
    func applicationDidEnterBackground(_ application: UIApplication) {
        // Schedule background refresh when app enters background
        scheduleAppRefresh()
    }
    
    func applicationWillEnterForeground(_ application: UIApplication) {
        // Cancel background tasks when returning to foreground
        BGTaskScheduler.shared.cancelAllTaskRequests()
        
        // Wake up backend when coming from background
        print("📱 App Foreground: Triggering backend wake-up...")
        Task {
            BackendWakeupService.shared.wakeupBackend()
        }
        
        // Resume timer-based updates if there's an active Live Activity
        Task {
            await LiveActivityService.shared.refreshCurrentActivity()
        }
    }
    
    func applicationDidBecomeActive(_ application: UIApplication) {
        // This is called more reliably when app becomes active
        print("📱 App Active: Checking if backend wake-up needed...")
        
        // Wake up backend when app becomes active
        Task {
            BackendWakeupService.shared.wakeupBackend()
        }
    }
}

// MARK: - Map Display Mode
enum MapDisplayMode: Equatable {
    case overallCongestion
    case journeyFocus(trainId: String, origin: String, destination: String, trainStops: [String])
}

// MARK: - App State
@MainActor
final class AppState: ObservableObject {
    @Published var selectedDestination: String?
    @Published var destinationStationCode: String?
    @Published var selectedDeparture: String?
    @Published var departureStationCode: String?
    @Published var currentTrainId: String?
    @Published var navigationPath = NavigationPath()
    @Published var selectedRoute: TripPair?  // Currently selected route for map highlighting
    @Published var activeTrainRoute: TripPair?  // Route from active Live Activity (persistent blue line)
    @Published var mapDisplayMode: MapDisplayMode = .overallCongestion
    @Published var currentTrain: TrainV2?  // Currently selected train for journey focus
    
    // Deep link navigation state
    @Published var deepLinkTrainNumber: String? = nil
    @Published var deepLinkFromStation: String? = nil
    @Published var deepLinkToStation: String? = nil
    @Published var shouldExpandForDeepLink: Bool = false

    // Pending navigation - set by views to request navigation that requires sheet expansion first
    // MapContainerView observes this and handles: expand sheet → wait → navigate
    @Published var pendingNavigation: NavigationDestination? = nil

    private let apiService = APIService()
    private let storageService = StorageService()
    
    // Recent trips
    @Published var recentTrips: [TripPair] = []
    
    // Favorite stations
    @Published var favoriteStations: [FavoriteStation] = []
    
    init() {
        loadRecentTrips()
        loadFavoriteStations()
        
        // Migrate existing data
        storageService.migrateRecentDestinations()
        loadRecentTrips() // Reload after migration
    }
    
    
    func resetSelections() {
        selectedDestination = nil
        destinationStationCode = nil
        selectedDeparture = nil
        departureStationCode = nil
        currentTrainId = nil
        selectedRoute = nil
        mapDisplayMode = .overallCongestion
        currentTrain = nil
    }
    
    // Clear deep link state after handling
    func clearDeepLinkState() {
        deepLinkTrainNumber = nil
        deepLinkFromStation = nil
        deepLinkToStation = nil
        shouldExpandForDeepLink = false
    }
    
    // MARK: - Trip Management
    func loadRecentTrips() {
        recentTrips = storageService.loadRecentTrips()
    }
    
    func saveCurrentTrip() {
        guard let departure = selectedDeparture,
              let departureCode = departureStationCode,
              let destination = selectedDestination,
              let destinationCode = destinationStationCode ?? Stations.getStationCode(destination) else { return }
        
        storageService.saveTrip(
            departureCode: departureCode,
            departureName: departure,
            destinationCode: destinationCode,
            destinationName: destination
        )
        loadRecentTrips()
    }
    
    func removeTrip(_ trip: TripPair) {
        storageService.removeTrip(trip)
        loadRecentTrips()
    }
    
    func toggleFavorite(_ trip: TripPair) {
        storageService.toggleFavorite(for: trip)
        loadRecentTrips()
    }
    
    func getFavoriteTrips() -> [TripPair] {
        return recentTrips.filter { $0.isFavorite }
    }
    
    func reverseFavoriteDirection(_ trip: TripPair) {
        storageService.reverseFavoriteDirection(trip)
        loadRecentTrips()
    }
    
    // MARK: - Favorite Stations
    func loadFavoriteStations() {
        favoriteStations = storageService.loadFavoriteStations()
    }
    
    func toggleFavoriteStation(code: String, name: String) {
        storageService.toggleFavoriteStation(code: code, name: name)
        loadFavoriteStations()
    }
    
    func isStationFavorited(code: String) -> Bool {
        return storageService.isStationFavorited(code: code)
    }
    
    /// Explicitly adds a station to favorites (doesn't toggle)
    func addFavoriteStation(code: String, name: String) {
        if !isStationFavorited(code: code) {
            storageService.toggleFavoriteStation(code: code, name: name)
            loadFavoriteStations()
        }
    }
    
    /// Explicitly removes a station from favorites
    func removeFavoriteStation(code: String) {
        if isStationFavorited(code: code) {
            // Find the station name from our current favorites
            if let station = favoriteStations.first(where: { $0.id == code }) {
                storageService.toggleFavoriteStation(code: code, name: station.name)
                loadFavoriteStations()
            }
        }
    }
    
}
