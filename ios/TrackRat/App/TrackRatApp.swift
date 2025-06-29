import SwiftUI
import ActivityKit
import WidgetKit
import UserNotifications
import BackgroundTasks

let BACKGROUND_REFRESH_TASK_ID = "com.trackrat.backgroundrefresh"

@main
struct TrackRatApp: App {
    @StateObject private var appState = AppState()
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @State private var showLaunchScreen = true
    @Environment(\.scenePhase) private var scenePhase
    
    var body: some Scene {
        WindowGroup {
            ZStack {
                if showLaunchScreen {
                    LaunchScreenView {
                        withAnimation(.easeInOut(duration: 0.5)) {
                            showLaunchScreen = false
                        }
                    }
                } else {
                    ContentView()
                        .environmentObject(appState)
                        .preferredColorScheme(.dark)
                        .tint(TrackRatTheme.Colors.accent)
                        .transition(.opacity)
                }
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
        // Widget registration now handled by Widget Extension target
        // No need to manually register here
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
        UNUserNotificationCenter.current().delegate = self
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
            self.handleAppRefresh(task: task as! BGAppRefreshTask)
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
        print("📱 Device token received: \(tokenString)")
        
        // DEBUG: Print actual bundle ID being used
        if let bundleId = Bundle.main.bundleIdentifier {
            print("📱 iOS App Bundle ID: \(bundleId)")
        }
        
        // Store device token for Live Activity registration
        Task { @MainActor in
            AppDelegate.deviceToken = tokenString
        }
        
        // Register device token with backend - ensure this completes first
        Task {
            await registerDeviceToken(tokenString)
            print("📱 Device token registration completed - ready for Live Activity registration")
        }
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
    
    private func registerDeviceToken(_ token: String) async {
        do {
            try await APIService.shared.registerDeviceToken(token)
            print("✅ Device token registered with backend: \(token)")
        } catch {
            print("❌ Failed to register device token with backend: \(error)")
            print("❌ Device token that failed: \(token)")
            // Continue without registration - app will still work with local updates
        }
    }
    
    private func handleLiveActivityPushUpdate(_ userInfo: [AnyHashable: Any]) async {
        print("🔄 Processing Live Activity push update")
        print("📦 Full payload: \(userInfo)")
        
        // Extract the aps payload
        guard let aps = userInfo["aps"] as? [String: Any] else {
            print("❌ No aps payload found in Live Activity push notification")
            return
        }
        
        // Log the content-state for debugging
        if let contentState = aps["content-state"] as? [String: Any] {
            print("📊 Content State Keys: \(Array(contentState.keys))")
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

        // It's good practice to store these before starting an async task
        // trainId in attributes is already a String, matching what fetchTrainDetailsFlexible expects for trainNumber
        // let trainIdString = activityAttributes.trainId
        // Guarding Int conversion is not strictly necessary here if APIService.fetchTrainDetailsFlexible expects trainId as String (trainNumber)
        // guard let _ = Int(trainIdString) else {
        //     print("Invalid trainId in Live Activity attributes: \(trainIdString)")
        //     task.setTaskCompleted(success: false)
        //     return
        // }

        print("Performing background fetch for Live Activity: Train \(activityAttributes.trainNumber)")

        Task {
            await LiveActivityService.shared.fetchAndUpdateTrain()
            // The fetchAndUpdateTrain method itself handles errors internally by logging them.
            // We assume success here unless a more specific error handling from fetchAndUpdateTrain is needed.
            print("Background fetch completed for Live Activity: Train \(activityAttributes.trainNumber)")
            task.setTaskCompleted(success: true)
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

// MARK: - App State
@MainActor
final class AppState: ObservableObject {
    @Published var selectedDestination: String?
    @Published var destinationStationCode: String?
    @Published var selectedDeparture: String?
    @Published var departureStationCode: String?
    @Published var currentTrainId: Int?
    @Published var navigationPath = NavigationPath()
    
    private let apiService = APIService()
    private let storageService = StorageService()
    
    // Recent destinations
    @Published var recentDestinations: [String] = []
    @Published var recentTrips: [TripPair] = []
    @Published var recentDepartures: [RecentDeparture] = []
    
    init() {
        loadRecentDestinations()
        loadRecentTrips()
        loadRecentDepartures()
        
        // Migrate existing data
        storageService.migrateRecentDestinations()
        loadRecentTrips() // Reload after migration
    }
    
    func loadRecentDestinations() {
        recentDestinations = storageService.loadRecentDestinations()
    }
    
    func saveDestination(_ destination: String) {
        storageService.saveDestination(destination)
        loadRecentDestinations()
    }
    
    func removeDestination(_ destination: String) {
        storageService.removeDestination(destination)
        loadRecentDestinations()
    }
    
    func resetSelections() {
        selectedDestination = nil
        destinationStationCode = nil
        selectedDeparture = nil
        departureStationCode = nil
        currentTrainId = nil
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
    
    // MARK: - Departure Management
    func loadRecentDepartures() {
        recentDepartures = storageService.loadRecentDepartures()
    }
    
    func saveDeparture() {
        guard let departure = selectedDeparture,
              let departureCode = departureStationCode else { return }
        
        storageService.saveDeparture(code: departureCode, name: departure)
        loadRecentDepartures()
    }
    
    func removeDeparture(_ departure: RecentDeparture) {
        var departures = recentDepartures
        departures.removeAll { $0.code == departure.code }
        
        if let encoded = try? JSONEncoder().encode(departures) {
            UserDefaults.standard.set(encoded, forKey: "trackrat.recentDepartures")
        }
        
        loadRecentDepartures()
    }
}