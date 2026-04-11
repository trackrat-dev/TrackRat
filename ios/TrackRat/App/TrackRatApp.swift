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
    
    /// True if user needs onboarding: either never completed, or state is corrupt (no systems selected)
    private var shouldShowOnboarding: Bool {
        !hasCompletedOnboarding || appState.selectedSystems.isEmpty
    }

    var body: some Scene {
        WindowGroup {
            Group {
                if shouldShowOnboarding {
                    OnboardingView()
                } else {
                    ContentView()
                }
            }
            .environmentObject(appState)
            .environmentObject(themeManager)
            .preferredColorScheme(themeManager.colorScheme)
            .tint(themeManager.tintColor)
            .onAppear {
                AppDelegate.appState = appState
                // Pick up any route status from a cold-launch notification tap
                if let pending = AppDelegate.pendingColdLaunchRouteStatus {
                    AppDelegate.pendingColdLaunchRouteStatus = nil
                    appState.pendingRouteStatus = pending
                }
            }
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
                    // Refresh subscription status in case user cancelled in Settings
                    SubscriptionService.shared.refreshOnForeground()
                    // Re-sync route alert subscriptions if stale (e.g. after server DB restore)
                    AlertSubscriptionService.shared.syncIfNeeded()
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

    /// Weak reference to AppState, set by TrackRatApp on launch
    @MainActor static weak var appState: AppState?

    /// Pending route status from notification tap during cold launch (before appState is set)
    @MainActor static var pendingColdLaunchRouteStatus: RouteStatusContext?

    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey : Any]? = nil) -> Bool {
        // Set up notification delegate
        UNUserNotificationCenter.current().delegate = self
        setupNotificationCategories()
        registerBackgroundTasks()

        // Request notification permissions after onboarding (don't prompt on first launch)
        if UserDefaults.standard.bool(forKey: "hasCompletedOnboarding") {
            Task {
                await requestNotificationPermissions()
            }
            application.registerForRemoteNotifications()
        }

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
                options: [.alert, .sound, .badge]
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
        let userInfo = response.notification.request.content.userInfo
        if let routeAlert = userInfo["route_alert"] as? [String: Any] {
            let context = RouteStatusContext(
                dataSource: routeAlert["data_source"] as? String ?? "",
                lineId: routeAlert["line_id"] as? String,
                direction: routeAlert["direction"] as? String,
                fromStationCode: routeAlert["from_station_code"] as? String,
                toStationCode: routeAlert["to_station_code"] as? String
            )
            Task { @MainActor in
                if let appState = AppDelegate.appState {
                    appState.pendingRouteStatus = context
                } else {
                    AppDelegate.pendingColdLaunchRouteStatus = context
                }
            }
        } else if let serviceAlert = userInfo["service_alert"] as? [String: Any] {
            let context = RouteStatusContext(
                dataSource: serviceAlert["data_source"] as? String ?? "",
                lineId: serviceAlert["line_id"] as? String,
                direction: serviceAlert["direction"] as? String,
                fromStationCode: serviceAlert["from_station_code"] as? String,
                toStationCode: serviceAlert["to_station_code"] as? String
            )
            Task { @MainActor in
                if let appState = AppDelegate.appState {
                    appState.pendingRouteStatus = context
                } else {
                    AppDelegate.pendingColdLaunchRouteStatus = context
                }
            }
        }
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

        // Sync route alert subscriptions with backend
        Task {
            await AlertSubscriptionService.shared.syncWithBackend(apnsToken: tokenString)
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
        guard LiveActivityService.shared.currentActivity != nil else {
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
              let _ = eventData["station"] as? String,
              let _ = eventData["is_origin"] as? Bool,
              let _ = eventData["stops_remaining"] as? Int else {
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

// MARK: - Route Status Context
struct RouteStatusContext: Identifiable, Equatable {
    let id = UUID()
    let dataSource: String
    let lineId: String?
    let direction: String?
    let fromStationCode: String?
    let toStationCode: String?

    init(dataSource: String, lineId: String? = nil, direction: String? = nil, fromStationCode: String? = nil, toStationCode: String? = nil) {
        self.dataSource = dataSource
        self.lineId = lineId
        self.direction = direction
        self.fromStationCode = fromStationCode
        self.toStationCode = toStationCode
    }

    /// Human-readable title for the route
    var title: String {
        if let from = fromStationCode, let to = toStationCode {
            return "\(Stations.displayName(for: from)) to \(Stations.displayName(for: to))"
        }
        if let lineId = lineId,
           let route = RouteTopology.allRoutes.first(where: { $0.id == lineId }) {
            if let direction = direction {
                return "\(route.name) toward \(direction)"
            }
            return route.name
        }
        return dataSource
    }

    /// Station codes for filtering congestion segments.
    /// Expands via station equivalents for cross-platform transfers (e.g., G→L at Metropolitan Av).
    var stationCodes: [String] {
        if let lineId = lineId,
           let route = RouteTopology.allRoutes.first(where: { $0.id == lineId }) {
            // When from/to are specified, clip to just that segment of the route
            if let from = fromStationCode, let to = toStationCode,
               let fromIdx = route.stationCodes.firstIndex(of: from),
               let toIdx = route.stationCodes.firstIndex(of: to) {
                let lower = min(fromIdx, toIdx)
                let upper = max(fromIdx, toIdx)
                return Array(route.stationCodes[lower...upper])
            }
            return route.stationCodes
        }
        if let from = fromStationCode, let to = toStationCode {
            let direct = RouteTopology.expandStationCodes([from, to], dataSource: dataSource)
            if direct.count > 2 { return direct }

            // Try station equivalents for cross-platform transfers
            let fromCodes = Stations.stationEquivalents[from] ?? [from]
            let toCodes = Stations.stationEquivalents[to] ?? [to]
            for f in fromCodes {
                for t in toCodes {
                    let expanded = RouteTopology.expandStationCodes([f, t], dataSource: dataSource)
                    if expanded.count > 2 { return expanded }
                }
            }
            return direct
        }
        return []
    }

    /// GTFS route IDs for filtering service alerts by relevance.
    /// Maps lineId to the GTFS route_ids used in MTA alert feeds.
    /// Handles both RouteTopology IDs ("subway-m") and raw backend line codes ("M", "LIRR-BB").
    var gtfsRouteIds: Set<String> {
        // Try resolving from lineId first, then fall back to station pair inference
        if let lineId = lineId {
            if let ids = Self.resolveGtfsRouteIds(lineId: lineId, dataSource: dataSource) {
                return ids
            }
        }

        // Fallback: infer lines from station pair via RouteTopology.
        // Expand via station equivalents to handle cross-platform transfers
        // (e.g., "SG29" → "SL10" for Metropolitan Av G↔L complex).
        // Collects ALL matching routes so multi-line stations return all relevant GTFS IDs.
        if let from = fromStationCode, let to = toStationCode {
            let fromCodes = Stations.stationEquivalents[from] ?? [from]
            let toCodes = Stations.stationEquivalents[to] ?? [to]
            var allIds = Set<String>()
            for f in fromCodes {
                for t in toCodes {
                    for route in RouteTopology.routesContaining(from: f, to: t, dataSource: dataSource) {
                        if let ids = Self.resolveGtfsRouteIds(lineId: route.id, dataSource: dataSource) {
                            allIds.formUnion(ids)
                        }
                    }
                }
            }
            if !allIds.isEmpty { return allIds }
        }

        return []
    }

    /// Resolves a lineId to route IDs for service alert matching.
    /// Accepts RouteTopology IDs ("subway-m", "lirr-babylon") or backend line codes ("M", "LIRR-BB", "NE").
    private static func resolveGtfsRouteIds(lineId: String, dataSource: String) -> Set<String>? {
        if dataSource == "SUBWAY" {
            if lineId.hasPrefix("subway-") {
                // RouteTopology format: "subway-1" → "1", "subway-6x" → "6X", "subway-a-rockaway" → "A"
                let suffix = String(lineId.dropFirst("subway-".count))
                let routeId = suffix.split(separator: "-").first.map(String.init) ?? suffix
                return [routeId.uppercased()]
            }
            // Raw backend line.code: "M", "L", "1", "6X" — already a GTFS route ID
            return [lineId.uppercased()]
        }

        // NJT/Amtrak: line codes are used as affected_route_ids directly (e.g., "NE", "NC")
        if dataSource == "NJT" || dataSource == "AMTRAK" {
            return [lineId]
        }

        // LIRR: RouteTopology ID → GTFS route_id
        let lirrTopologyMapping: [String: String] = [
            "lirr-babylon": "1", "lirr-hempstead": "2", "lirr-oyster-bay": "3",
            "lirr-ronkonkoma": "4", "lirr-montauk": "5", "lirr-long-beach": "6",
            "lirr-far-rockaway": "7", "lirr-west-hempstead": "8",
            "lirr-port-washington": "9", "lirr-port-washington-gct": "9",
            "lirr-port-jefferson": "10",
            "lirr-belmont-park": "11", "lirr-greenport": "13",
        ]
        // LIRR: Backend line.code → GTFS route_id (e.g., "LIRR-BB" → "1")
        let lirrCodeMapping: [String: String] = [
            "LIRR-BB": "1", "LIRR-HB": "2", "LIRR-OB": "3",
            "LIRR-RK": "4", "LIRR-MK": "5", "LIRR-LB": "6",
            "LIRR-FR": "7", "LIRR-WH": "8", "LIRR-PW": "9",
            "LIRR-PJ": "10", "LIRR-BP": "11", "LIRR-GP": "13",
        ]

        // MNR: RouteTopology ID → GTFS route_id
        let mnrTopologyMapping: [String: String] = [
            "mnr-hudson": "1", "mnr-harlem": "2", "mnr-new-haven": "3",
            "mnr-new-canaan": "4", "mnr-danbury": "5", "mnr-waterbury": "6",
        ]
        // MNR: Backend line.code → GTFS route_id (e.g., "MNR-HUD" → "1")
        let mnrCodeMapping: [String: String] = [
            "MNR-HUD": "1", "MNR-HAR": "2", "MNR-NH": "3",
            "MNR-NC": "4", "MNR-DAN": "5", "MNR-WAT": "6",
        ]

        if let gtfsId = lirrTopologyMapping[lineId] ?? lirrCodeMapping[lineId]
            ?? mnrTopologyMapping[lineId] ?? mnrCodeMapping[lineId] {
            return [gtfsId]
        }

        return nil
    }

    /// First station code (for API calls)
    var effectiveFromStation: String? {
        if let from = fromStationCode { return from }
        if let lineId = lineId,
           let route = RouteTopology.allRoutes.first(where: { $0.id == lineId }) {
            return route.stationCodes.first
        }
        return nil
    }

    /// Last station code (for API calls)
    var effectiveToStation: String? {
        if let to = toStationCode { return to }
        if let lineId = lineId,
           let route = RouteTopology.allRoutes.first(where: { $0.id == lineId }) {
            return route.stationCodes.last
        }
        return nil
    }

    static func == (lhs: RouteStatusContext, rhs: RouteStatusContext) -> Bool {
        lhs.id == rhs.id
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
    @Published var selectedTrip: TripOption?  // Currently selected multi-leg trip for trip details
    
    // Deep link navigation state
    @Published var deepLinkTrainNumber: String? = nil
    @Published var deepLinkFromStation: String? = nil
    @Published var deepLinkToStation: String? = nil
    @Published var deepLinkDate: Date? = nil
    @Published var shouldExpandForDeepLink: Bool = false

    // Pending navigation - set by views to request navigation that requires sheet expansion first
    // MapContainerView observes this and handles: expand sheet → wait → navigate
    @Published var pendingNavigation: NavigationDestination? = nil

    // Route status sheet - set by notification tap or route alert row tap
    @Published var pendingRouteStatus: RouteStatusContext? = nil

    private let apiService = APIService()
    private let storageService = StorageService()
    
    // Recent trips
    @Published var recentTrips: [TripPair] = []
    
    // Favorite stations
    @Published var favoriteStations: [FavoriteStation] = []

    // Selected train systems (persisted via UserDefaults)
    // These control which systems are visible on the map
    @Published var selectedSystems: Set<TrainSystem> = .defaultEnabled {
        didSet {
            UserDefaults.standard.set(selectedSystems.commaSeparated, forKey: "selectedTrainSystems")
        }
    }

    // Map display settings (persisted via UserDefaults)
    @Published var mapHighlightMode: SegmentHighlightMode = .delays {
        didSet {
            UserDefaults.standard.set(mapHighlightMode.rawValue, forKey: "mapHighlightMode")
        }
    }

    @Published var showMapStations: Bool = false {
        didSet {
            UserDefaults.standard.set(showMapStations, forKey: "showMapStations")
        }
    }

    // Beta feature: Show departure odds on train details
    @Published var showDepartureOdds: Bool = false {
        didSet {
            UserDefaults.standard.set(showDepartureOdds, forKey: "showDepartureOdds")
        }
    }

    // Beta feature: Enable tapping route segments to view details
    @Published var enableSegmentTap: Bool = true {
        didSet {
            UserDefaults.standard.set(enableSegmentTap, forKey: "enableSegmentTap")
        }
    }

    init() {
        loadRecentTrips()
        loadFavoriteStations()
        loadSelectedSystems()
        loadMapSettings()
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
        deepLinkDate = nil
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
        }
        // Always reload — home/work injection means the display list may have changed
        // even if the station was already "favorited" via its home/work designation
        loadFavoriteStations()
    }

    /// Explicitly removes a station from favorites
    func removeFavoriteStation(code: String) {
        // Use dedicated remove (never adds) — safe even if the station was only
        // present via home/work injection and not in stored favorites
        storageService.removeFavoriteStation(code: code)
        loadFavoriteStations()
    }

    // MARK: - Train Systems

    /// Load selected systems from UserDefaults (with migration from legacy AMTRAK_NEC)
    private func loadSelectedSystems() {
        if let stored = UserDefaults.standard.string(forKey: "selectedTrainSystems"), !stored.isEmpty {
            // Migration: convert legacy "AMTRAK_NEC" to "AMTRAK"
            let migrated = stored.contains("AMTRAK_NEC")
                ? stored.replacingOccurrences(of: "AMTRAK_NEC", with: "AMTRAK")
                : stored
            let loaded = Set<TrainSystem>.from(commaSeparated: migrated)
            selectedSystems = loaded.isEmpty ? .defaultEnabled : loaded
        } else {
            selectedSystems = .defaultEnabled
        }
    }

    /// Check if a system is selected (visible on map)
    func isSystemSelected(_ system: TrainSystem) -> Bool {
        selectedSystems.contains(system)
    }

    /// Toggle a system's selection state.
    /// Set allowEmpty to true during onboarding where the UI hides the Continue button when empty.
    func toggleSystem(_ system: TrainSystem, allowEmpty: Bool = false) {
        if selectedSystems.contains(system) {
            guard allowEmpty || selectedSystems.count > 1 else { return }
            selectedSystems.remove(system)
        } else {
            selectedSystems.insert(system)
        }
    }

    /// Select exactly one system, replacing any previous selection.
    /// Used during onboarding for single-select flow.
    func selectSystem(_ system: TrainSystem) {
        selectedSystems = [system]
    }

    /// Select all systems
    func selectAllSystems() {
        selectedSystems = Set(TrainSystem.allCases)
    }

    // MARK: - Map Settings

    /// Load map display settings from UserDefaults
    private func loadMapSettings() {
        // Load highlight mode (on/off toggle — per-segment coloring is automatic)
        if let stored = UserDefaults.standard.string(forKey: "mapHighlightMode"),
           let mode = SegmentHighlightMode(rawValue: stored) {
            // Migrate: .health is no longer user-selectable, treat as "on" (.delays)
            mapHighlightMode = mode == .health ? .delays : mode
        } else {
            mapHighlightMode = .delays
        }

        // Load stations visibility
        showMapStations = UserDefaults.standard.bool(forKey: "showMapStations")

        // Load beta features
        showDepartureOdds = UserDefaults.standard.bool(forKey: "showDepartureOdds")
        // Migration: previous bug stored false for users who never toggled this setting
        if !UserDefaults.standard.bool(forKey: "enableSegmentTap_defaultFixed") {
            UserDefaults.standard.set(true, forKey: "enableSegmentTap")
            UserDefaults.standard.set(true, forKey: "enableSegmentTap_defaultFixed")
        }
        enableSegmentTap = UserDefaults.standard.bool(forKey: "enableSegmentTap")
    }

}

