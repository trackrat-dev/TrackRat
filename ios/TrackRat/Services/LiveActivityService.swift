import Foundation
import ActivityKit
import UserNotifications
import UIKit



@available(iOS 16.1, *)
class LiveActivityService: ObservableObject {
    static let shared = LiveActivityService()
    
    @Published var currentActivity: Activity<TrainActivityAttributes>?
    @Published var isActivityActive: Bool = false
    
    private var lastKnownStatusV2: String?
    private var lastKnownStops: [Stop] = []
    private var lastDepartedStopIndex: Int?
    private var approachingNotificationsSent: Set<String> = []
    private var lastKnownState: TrainActivityAttributes.ContentState?
    private var lastKnownTrack: String?
    private var lastKnownDelayMinutes: Int?
    
    private init() {
        checkCurrentActivity()
    }
    
    // MARK: - Relevance Scoring
    
    /// Calculate relevance score for Live Activity prioritization with enhanced metadata
    private func calculateRelevanceScore(for train: Train, alertMetadata: AlertMetadata? = nil) -> Double {
        var score = 95.0 // Maximum base score for best Dynamic Island visibility
        
        // Use backend-provided priority if available
        if let metadata = alertMetadata {
            switch metadata.dynamicIslandPriority {
            case "urgent":
                return 100.0 // Maximum possible priority
            case "high":
                score = 95.0
            case "medium":
                score = 80.0
            case "low":
                score = 60.0
            default:
                score = 70.0 // Default fallback
            }
            
            // Small boost for very recent alerts
            let now = Date().timeIntervalSince1970
            if now - metadata.timestamp < 30 { // Within 30 seconds
                score += 5.0
            }
            
            return min(score, 100.0)
        }
        
        // Fallback to local scoring logic if no metadata available
        // Maximum priority for boarding
        if train.statusV2?.current.contains("BOARDING") == true || train.status.rawValue.contains("BOARDING") {
            return 100.0
        }
        
        // High priority for track assignments
        if let track = train.track, !track.isEmpty {
            score = 95.0
        }
        
        // Priority for approaching/departing
        if let statusV2 = train.statusV2?.current {
            if statusV2.contains("APPROACHING") {
                score = 92.0
            } else if statusV2.contains("DEPARTED") {
                score = 88.0
            }
        }
        
        // Boost based on journey progress
        if let progress = train.progress?.journeyPercent {
            score += (Double(progress) * 10) // 0-10 bonus
        }
        
        // Boost for delays (more urgent)
        if let delayMinutes = train.delayMinutes, delayMinutes > 0 {
            score += min(Double(delayMinutes), 15.0) // Up to 15 point boost for delays
        }
        
        return min(score, 100.0)
    }
    
    
    
    // MARK: - Activity Management
    
    /// Start tracking a train with Live Activity
    func startTrackingTrain(
        _ train: Train,
        from originCode: String,
        to destinationCode: String,
        origin: String,
        destination: String
    ) async throws {
        // End any existing activity first
        await endCurrentActivity()
        
        // Debug Live Activity status first
        debugLiveActivityStatus()
        
        // Check and request notification permissions
        try await checkAndRequestNotificationPermissions()
        
        // Validate input data before creating Live Activity
        do {
            try validateLiveActivityData(train: train, originCode: originCode, destinationCode: destinationCode, origin: origin, destination: destination)
            print("✅ Live Activity data validation passed")
        } catch {
            print("❌ Live Activity data validation failed: \(error)")
            throw error
        }
        
        // Create activity attributes with validated data
        let attributes = TrainActivityAttributes(
            trainNumber: sanitizeTrainNumber(train.trainId),
            trainId: train.trainId,
            routeDescription: "\(sanitizeStationName(origin)) → \(sanitizeStationName(destination))",
            origin: sanitizeStationName(origin),
            destination: sanitizeStationName(destination),
            originStationCode: originCode,
            destinationStationCode: destinationCode
        )
        print("✅ Live Activity attributes created")
        
        // Create initial content state with validation
        let initialState: TrainActivityAttributes.ContentState
        do {
            initialState = train.toLiveActivityContentState(
                from: originCode,
                to: destinationCode
            )
            print("✅ Live Activity content state created")
        } catch {
            print("❌ Failed to create content state: \(error)")
            throw LiveActivityError.invalidData("Failed to create content state: \(error)")
        }
        
        // Debug content state
        print("🔍 Live Activity Content State Debug:")
        print("  - statusV2: '\(initialState.statusV2)'")
        print("  - track: '\(initialState.track ?? "nil")'")
        print("  - journeyProgress: \(initialState.journeyProgress)")
        print("  - currentLocation: \(initialState.currentLocation)")
        print("  - hasStatusChanged: \(initialState.hasStatusChanged)")
        print("  - nextStop: \(initialState.nextStop?.stationName ?? "nil")")
        
        // Final validation of content state
        do {
            try validateContentState(initialState)
            print("✅ Live Activity content state validation passed")
        } catch {
            print("❌ Live Activity content state validation failed: \(error)")
            throw error
        }
        
        // Start the activity with enhanced error handling
        do {
            // Check ActivityAuthorizationInfo in detail
            let authInfo = ActivityAuthorizationInfo()
            print("🔍 Live Activity Authorization Debug:")
            print("  - areActivitiesEnabled: \(authInfo.areActivitiesEnabled)")
            print("  - frequentPushesEnabled: \(authInfo.frequentPushesEnabled)")
            print("  - iOS Version: \(UIDevice.current.systemVersion)")
            print("  - Device Model: \(UIDevice.current.model)")
            
            // Check notification permissions too
            let notificationSettings = await UNUserNotificationCenter.current().notificationSettings()
            print("🔍 Notification Authorization:")
            print("  - authorizationStatus: \(notificationSettings.authorizationStatus.rawValue)")
            print("  - alertSetting: \(notificationSettings.alertSetting.rawValue)")
            
            // Check if Live Activities are available
            guard authInfo.areActivitiesEnabled else {
                print("❌ Live Activities are not enabled")
                print("💡 User needs to enable Live Activities in Settings > Face ID & Passcode > Live Activities")
                throw LiveActivityError.permissionDenied
            }
            
            // Check notification permissions
            guard notificationSettings.authorizationStatus == .authorized || notificationSettings.authorizationStatus == .provisional else {
                print("❌ Notification permissions not granted")
                print("💡 User needs to allow notifications for Live Activities to work")
                throw LiveActivityError.permissionDenied
            }
            
            // Create activity content with staleDate and relevance scoring
            let relevanceScore = calculateRelevanceScore(for: train, alertMetadata: initialState.alertMetadata)
            let activityContent = ActivityContent(
                state: initialState,
                staleDate: Date().addingTimeInterval(120), // 2 minutes for freshness
                relevanceScore: relevanceScore
            )
            print("✅ Activity content created with relevance score: \(relevanceScore)")
            
            print("🚀 Attempting to create Live Activity...")
            print("  - Train ID: \(attributes.trainId)")
            print("  - Train Number: \(attributes.trainNumber)")
            print("  - Route: \(attributes.routeDescription)")
            print("  - Relevance Score: \(relevanceScore)")
            
            let activity: Activity<TrainActivityAttributes>
            do {
                activity = try Activity<TrainActivityAttributes>.request(
                    attributes: attributes,
                    content: activityContent,
                    pushType: .token // Enable push tokens for Dynamic Island and remote updates
                )
                print("✅ Activity.request() completed successfully")
            } catch {
                print("❌ Activity.request() failed with error: \(error)")
                print("❌ Error type: \(type(of: error))")
                print("❌ Error description: \(error.localizedDescription)")
                throw error
            }
            
            print("✅ Live Activity created successfully")
            
            await MainActor.run {
                self.currentActivity = activity
                self.isActivityActive = true
                self.lastKnownStatusV2 = train.statusV2?.current
                self.lastKnownStops = train.stops ?? []
                self.lastKnownState = initialState
                self.lastKnownTrack = train.track
                self.lastKnownDelayMinutes = train.delayMinutes
            }
            
            print("🔍 Live Activity Status Check:")
            print("  - Activity ID: \(activity.id)")
            print("  - Activity State: \(activity.activityState)")
            print("  - Content State StatusV2: \(activity.content.state.statusV2)")
            print("  - Is Active: \(isActivityActive)")
            
            // Monitor push token for backend registration
            Task {
                for await pushTokenData in activity.pushTokenUpdates {
                    let pushToken = pushTokenData.reduce("") { $0 + String(format: "%02x", $1) }
                    print("✅ Received new push token: \(pushToken)")
                    
                    // Register with your server
                    let apiService = APIService.shared
                    let deviceToken = UserDefaults.standard.string(forKey: "deviceToken")
                    
                    do {
                        try await apiService.registerLiveActivity(
                            trainId: train.trainId,
                            pushToken: pushToken,
                            deviceToken: deviceToken,
                            userOrigin: originCode,
                            userDestination: destinationCode
                        )
                    } catch {
                        print("❌ Failed to register push token: \(error)")
                    }
                }
            }
            
            // Schedule background refresh
            if let appDelegate = await UIApplication.shared.delegate as? AppDelegate {
                await appDelegate.scheduleAppRefresh()
            }
            
            // Send haptic feedback
            await MainActor.run {
                let impact = UIImpactFeedbackGenerator(style: .medium)
                impact.impactOccurred()
            }
            
            // REMOVED: Redundant tracking started notification - Live Activity appearing is sufficient
            // await sendTrackingStartedNotification(train: train, route: "\(sanitizeStationName(origin)) → \(sanitizeStationName(destination))")
            
            print("✅ Live Activity started for train \(train.trainId)")
            
        } catch let error as LiveActivityError {
            print("❌ Live Activity error: \(error.localizedDescription)")
            throw error
        } catch {
            print("❌ Failed to start Live Activity: \(error)")
            
            // Check if it's an authorization issue
            if error.localizedDescription.contains("not authorized") || 
               error.localizedDescription.contains("denied") {
                throw LiveActivityError.permissionDenied
            } else if error.localizedDescription.contains("not supported") ||
                      error.localizedDescription.contains("not enabled") {
                throw LiveActivityError.notSupported
            }
            
            throw LiveActivityError.failedToStart(error)
        }
    }
    
    /// Update the current Live Activity with new train data
    func updateActivity(with train: Train) async {
        guard let activity = currentActivity else { return }
        
        let attributes = activity.attributes
        let newState = train.toLiveActivityContentState(
            from: attributes.originStationCode,
            to: attributes.destinationStationCode,
            lastKnownStatusV2: lastKnownStatusV2
        )
        
        // Validate new state before updating
        do {
            try validateContentState(newState)
        } catch {
            print("❌ Invalid content state, skipping Live Activity update: \(error)")
            return
        }
        
        // Update stored stops state if available
        if let stops = train.stops {
            await MainActor.run {
                self.lastKnownStops = stops
            }
        }
        
        // Create content with enhanced relevance scoring using backend metadata
        let relevanceScore = calculateRelevanceScore(for: train, alertMetadata: newState.alertMetadata)
        
        let updatedContent = ActivityContent(
            state: newState,
            staleDate: Date().addingTimeInterval(120), // 2 minutes for freshness
            relevanceScore: relevanceScore
        )
        
        // Regular update without alert
        await activity.update(updatedContent)
        
        // Check for status changes that warrant additional haptic feedback
        if newState.hasStatusChanged {
            await handleStatusChange(from: lastKnownStatusV2, to: train.statusV2?.current)
        }
        
        // Handle backend-requested haptic feedback
        if let metadata = newState.alertMetadata, metadata.requiresHapticFeedback {
            await handleEnhancedHapticFeedback(metadata: metadata)
            
            // Also send banner notification for critical local updates
            await sendCriticalBannerNotificationIfNeeded(metadata: metadata, train: train)
        }
        
        await MainActor.run {
            self.lastKnownStatusV2 = train.statusV2?.current
            self.lastKnownState = newState
            self.lastKnownTrack = train.track
            self.lastKnownDelayMinutes = train.delayMinutes
        }
        
        print("🔄 Live Activity updated for train \(train.trainId)")
        
        // Check if we should auto-end the activity
        let shouldEnd = shouldAutoEndActivity(train: train, state: newState)
        print("🔍 Auto-end check: shouldEnd=\(shouldEnd), progress=\(newState.journeyProgress), location=\(newState.currentLocation)")
        
        if shouldEnd {
            print("🛑 Auto-ending Live Activity for train \(train.trainId)")
            await endCurrentActivity()
        }
    }
    
    /// Refresh the current Live Activity data
    func refreshCurrentActivity() async {
        // This method might need to be re-evaluated or used carefully,
        // as fetchAndUpdateTrain now relies on currentActivity.
        // For now, let's assume it's called when currentActivity is valid.
        await fetchAndUpdateTrain()
    }
    
    /// End the current Live Activity
    func endCurrentActivity() async {
        guard let activity = currentActivity else { return }
        
        if let appDelegate = await UIApplication.shared.delegate as? AppDelegate {
            await appDelegate.cancelAllPendingBackgroundTasks()
        }
        
        let finalState = activity.content.state
        let finalContent = ActivityContent(
            state: finalState,
            staleDate: Date().addingTimeInterval(60) // 1 minute stale date for ending
        )
        // Keep ended activity visible for 30 seconds for user to see final state
        await activity.end(finalContent, dismissalPolicy: .after(Date().addingTimeInterval(30)))
        
        await MainActor.run {
            self.currentActivity = nil
            self.isActivityActive = false
            self.lastKnownStatusV2 = nil
            self.lastKnownStops = []
            self.lastDepartedStopIndex = nil
            self.approachingNotificationsSent.removeAll()
            self.lastKnownState = nil
            self.lastKnownTrack = nil
            self.lastKnownDelayMinutes = nil
        }
        
        print("🛑 Live Activity ended and cleaned up")
    }
    
    // MARK: - Background Updates
    
    func fetchAndUpdateTrain() async {
        guard let activity = self.currentActivity else {
            print("ℹ️ No current activity to update from background.")
            return
        }
        let attributes = activity.attributes
        // trainId can be alphanumeric (e.g., "P625", "A671") - no need to validate as Int

        do {
            print("🔄 Making API request for train \(attributes.trainNumber) from \(attributes.originStationCode) (background)")
            let train = try await APIService.shared.fetchTrainDetailsFlexible(
                trainId: attributes.trainId, // Use trainId instead of trainNumber for consistency
                fromStationCode: attributes.originStationCode
            )
            print("✅ API request successful for train \(attributes.trainNumber) (background)")
            await updateActivity(with: train)
        } catch {
            print("❌ Failed to fetch train data for Live Activity update (background): \(error)")
            print("❌ Full error details: \(String(describing: error))")
            
            // Handle specific error cases
            if let urlError = error as? URLError {
                switch urlError.code {
                case .notConnectedToInternet, .networkConnectionLost:
                    print("📶 Network connectivity issue, will retry on next cycle")
                case .timedOut:
                    print("⏱️ Request timed out, will retry on next cycle")
                case .cancelled:
                    print("🛑 Request was cancelled")
                default:
                    print("🌐 Network error: \(urlError.localizedDescription)")
                }
            }
            
            // Don't end activity immediately on network errors
            // Let it retry on the next cycle
        }
    }
    
    // MARK: - Stop Departure Detection
    
    private func detectAndNotifyStopDepartures(
        newStops: [Stop],
        train: Train,
        originCode: String,
        destinationCode: String
    ) async {
        guard let activity = currentActivity else { return }
        let attributes = activity.attributes
        
        // Find stops between origin and destination using robust matching
        guard let originIndex = newStops.firstIndex(where: { Stations.stationMatches($0, stationCode: originCode) }),
              let destIndex = newStops.firstIndex(where: { Stations.stationMatches($0, stationCode: destinationCode) }) else {
            return
        }
        
        // Check each stop in the journey for departure changes
        for (index, stop) in newStops.enumerated() {
            // Only check stops in our journey range
            guard index >= originIndex && index <= destIndex else { continue }
            
            // Find corresponding old stop
            if let oldStop = lastKnownStops.first(where: { $0.stationName == stop.stationName }) {
                // Check if this stop just departed
                if !(oldStop.departed ?? false) && (stop.departed ?? false) {
                    // REMOVED: Local notification - will be handled by backend push updates
                    // Keep detection logic for local state tracking
                    /*
                    await sendStopDepartureNotification(
                        stop: stop,
                        train: train,
                        attributes: attributes,
                        stopsRemaining: destIndex - index,
                        nextStop: index < destIndex ? newStops[index + 1] : nil
                    )
                    */
                    
                    // Store the last departed stop index
                    await MainActor.run {
                        self.lastDepartedStopIndex = index
                    }
                }
            }
        }
    }
    
    // REMOVED: Local notification function - will be handled by backend push updates
    /*
    private func sendStopDepartureNotification(
        stop: Stop,
        train: Train,
        attributes: TrainActivityAttributes,
        stopsRemaining: Int,
        nextStop: Stop?
    ) async {
        let content = UNMutableNotificationContent()
        
        if stop.stationName == attributes.origin {
            // Departure from origin
            content.title = "🚂 Your train just left \(Stations.displayName(for: stop.stationName))"
            if let next = nextStop {
                content.body = "Next stop: \(Stations.displayName(for: next.stationName))"
                if let arrivalTime = next.scheduledTime {
                    let formatter = DateFormatter()
                    formatter.timeStyle = .short
                    formatter.timeZone = TimeZone(identifier: "America/New_York")
                    content.body += " (ETA: \(formatter.string(from: arrivalTime)))"
                }
            }
        } else if stop.stationName == attributes.destination {
            // Should not happen as we check before destination
            return
        } else {
            // Intermediate stop departure
            content.title = "✅ Departed \(Stations.displayName(for: stop.stationName))"
            if stopsRemaining == 1 {
                content.body = "Next stop is your destination!"
            } else if stopsRemaining > 1 {
                content.body = "\(stopsRemaining) stops remaining to \(Stations.displayName(for: attributes.destination))"
            }
            
            if let next = nextStop {
                content.body += "\nNext: \(Stations.displayName(for: next.stationName))"
            }
        }
        
        content.sound = .default
        
        let request = UNNotificationRequest(
            identifier: "stop-departure-\(train.id)-\(stop.stationName)-\(Date().timeIntervalSince1970)",
            content: content,
            trigger: nil
        )
        
        do {
            try await UNUserNotificationCenter.current().add(request)
            print("📍 Sent departure notification for \(stop.stationName)")
            
            // Haptic feedback for stop departure
            await MainActor.run {
                let impact = UIImpactFeedbackGenerator(style: .light)
                impact.impactOccurred()
            }
        } catch {
            print("❌ Failed to send stop departure notification: \(error)")
        }
    }
    */
    
    // MARK: - Approaching Stop Detection
    
    private func detectAndNotifyApproachingStops(
        stops: [Stop],
        train: Train,
        originCode: String,
        destinationCode: String
    ) async {
        guard let activity = currentActivity else { return }
        let attributes = activity.attributes
        
        // Find stops between origin and destination using robust matching
        guard let originIndex = stops.firstIndex(where: { Stations.stationMatches($0, stationCode: originCode) }),
              let destIndex = stops.firstIndex(where: { Stations.stationMatches($0, stationCode: destinationCode) }) else {
            return
        }
        
        // Check each upcoming stop in the journey
        for (index, stop) in stops.enumerated() {
            // Only check stops in our journey range that haven't departed yet
            // Skip the origin stop (first stop) - we don't want arrival notifications for departure
            guard index > originIndex && index <= destIndex && !(stop.departed ?? false) else { continue }
            
            // Calculate time to arrival
            if let arrivalTime = stop.scheduledTime {
                let timeToArrival = arrivalTime.timeIntervalSince(Date())
                let minutesToArrival = Int(timeToArrival / 60)
                
                // Check if we're within the notification window (2-3 minutes)
                if timeToArrival > 0 && timeToArrival <= 180 { // Within 3 minutes
                    let notificationKey = "\(train.id)-\(stop.stationName)-approaching"
                    
                    // Only send if we haven't already sent for this stop
                    if !approachingNotificationsSent.contains(notificationKey) {
                        // REMOVED: Local notification - will be handled by backend push updates
                        // Keep detection logic for local state tracking
                        /*
                        await sendApproachingStopNotification(
                            stop: stop,
                            train: train,
                            attributes: attributes,
                            minutesAway: minutesToArrival,
                            isDestination: stop.stationName == attributes.destination
                        )
                        */
                        
                        // Mark as sent
                        _ = await MainActor.run {
                            self.approachingNotificationsSent.insert(notificationKey)
                        }
                    }
                }
            }
        }
    }
    
    // REMOVED: Local notification function - will be handled by backend push updates
    /*
    private func sendApproachingStopNotification(
        stop: Stop,
        train: Train,
        attributes: TrainActivityAttributes,
        minutesAway: Int,
        isDestination: Bool
    ) async {
        let content = UNMutableNotificationContent()
        
        if isDestination {
            content.title = "📍 Approaching Your Destination!"
            if minutesAway == 0 {
                content.body = "Arriving at \(Stations.displayName(for: stop.stationName)) now"
            } else {
                content.body = "Arriving at \(Stations.displayName(for: stop.stationName)) in ~\(minutesAway) minute\(minutesAway == 1 ? "" : "s")"
            }
            content.sound = .default
        } else {
            content.title = "📍 Approaching \(Stations.displayName(for: stop.stationName))"
            if minutesAway == 0 {
                content.body = "Arrival imminent"
            } else {
                content.body = "Arrival in ~\(minutesAway) minute\(minutesAway == 1 ? "" : "s")"
            }
            content.sound = .default
        }
        
        let request = UNNotificationRequest(
            identifier: "approaching-\(train.id)-\(stop.stationName)-\(Date().timeIntervalSince1970)",
            content: content,
            trigger: nil
        )
        
        do {
            try await UNUserNotificationCenter.current().add(request)
            print("📍 Sent approaching notification for \(stop.stationName))"
            
            // Haptic feedback for approaching stops
            await MainActor.run {
                let notification = UINotificationFeedbackGenerator()
                notification.notificationOccurred(isDestination ? .warning : .success)
            }
        } catch {
            print("❌ Failed to send approaching stop notification: \(error)")
        }
    }
    */
    
    // MARK: - Permissions and Notifications
    
    public func checkAndRequestNotificationPermissions() async throws {
        let center = UNUserNotificationCenter.current()
        let settings = await center.notificationSettings()
        
        print("🔍 Notification Permission Debug:")
        print("  - authorizationStatus: \(settings.authorizationStatus.rawValue)")
        print("  - alertSetting: \(settings.alertSetting.rawValue)")
        print("  - badgeSetting: \(settings.badgeSetting.rawValue)")
        print("  - soundSetting: \(settings.soundSetting.rawValue)")

        switch settings.authorizationStatus {
        case .notDetermined:
            print("🔔 Notification permission not determined. Requesting authorization...")
            let granted = try await center.requestAuthorization(options: [.alert, .sound, .badge])
            print("🔔 Notification permission request result: \(granted)")
            if !granted {
                print("⚠️ Notification permission not granted")
                // Continue anyway as Live Activities can work without notifications
            } else {
                print("✅ Notification permission granted.")
            }
        case .denied:
            print("⚠️ Notification permission denied, Live Activities may have limited functionality")
            // Continue anyway as Live Activities don't require notifications
        case .authorized, .provisional, .ephemeral:
            print("✅ Notification permission already granted (\(settings.authorizationStatus)).")
            // Permission already granted
            break
        @unknown default:
            print("⚠️ Unknown notification authorization status: \(settings.authorizationStatus).")
            // Handle future cases or consider it an error
            throw LiveActivityError.permissionDenied // Or a more specific error
        }
    }
    
    // REMOVED: Redundant function - Live Activity appearing is sufficient indication
    /*
    private func sendTrackingStartedNotification(train: Train, route: String) async {
        let content = UNMutableNotificationContent()
        content.title = "🚆 Now Tracking Train \(train.trainId)"
        content.body = "We'll notify you of any status changes for \(route)"
        content.sound = .default
        
        let request = UNNotificationRequest(
            identifier: "tracking-started-\(train.id)",
            content: content,
            trigger: nil // Immediate notification
        )
        
        do {
            try await UNUserNotificationCenter.current().add(request)
            print("📱 Sent tracking started notification")
        } catch {
            print("❌ Failed to send tracking started notification: \(error)")
        }
    }
    */
    
    
    /// Handle enhanced haptic feedback based on backend metadata
    private func handleEnhancedHapticFeedback(metadata: AlertMetadata) async {
        await MainActor.run {
            let feedbackStyle: UIImpactFeedbackGenerator.FeedbackStyle
            
            // Map backend priority to haptic intensity
            switch metadata.dynamicIslandPriority {
            case "urgent":
                feedbackStyle = .heavy
            case "high":
                feedbackStyle = .medium
            case "medium":
                feedbackStyle = .light
            case "low":
                feedbackStyle = .soft
            default:
                feedbackStyle = .medium
            }
            
            let generator = UIImpactFeedbackGenerator(style: feedbackStyle)
            generator.impactOccurred()
            
            print("📳 Enhanced haptic feedback triggered for \(metadata.alertType) with \(metadata.dynamicIslandPriority) priority")
        }
    }
    
    /// Send critical banner notification alongside Live Activity updates for high-priority events
    func sendCriticalBannerNotification(title: String, body: String, priority: String, trainId: String) async {
        // Only send banner notifications for urgent and high priority events
        guard priority == "urgent" || priority == "high" else { return }
        
        // Check if notifications are authorized
        let notificationCenter = UNUserNotificationCenter.current()
        let authorizationStatus = await notificationCenter.notificationSettings().authorizationStatus
        
        guard authorizationStatus == .authorized || authorizationStatus == .provisional else {
            print("❌ Cannot send banner notification - not authorized")
            return
        }
        
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default
        content.categoryIdentifier = "CRITICAL_TRAIN_UPDATE"
        
        // Set interruption level for time-sensitive notifications (iOS 15+)
        if #available(iOS 15.0, *) {
            content.interruptionLevel = priority == "urgent" ? .timeSensitive : .active
            content.relevanceScore = priority == "urgent" ? 1.0 : 0.8
        }
        
        // Add train-specific identifier to avoid duplicates
        let identifier = "critical-\(trainId)-\(priority)-\(Date().timeIntervalSince1970)"
        
        let request = UNNotificationRequest(
            identifier: identifier,
            content: content,
            trigger: nil // Immediate delivery
        )
        
        do {
            try await notificationCenter.add(request)
            print("📱 Critical banner notification sent: \(title)")
        } catch {
            print("❌ Failed to send banner notification: \(error)")
        }
    }
    
    /// Send banner notification for critical local updates (non-push)
    private func sendCriticalBannerNotificationIfNeeded(metadata: AlertMetadata, train: Train) async {
        // Only send for urgent/high priority events
        guard metadata.dynamicIslandPriority == "urgent" || metadata.dynamicIslandPriority == "high" else { return }
        
        let (title, body) = createLocalNotificationContent(alertType: metadata.alertType, train: train)
        
        await sendCriticalBannerNotification(
            title: title,
            body: body,
            priority: metadata.dynamicIslandPriority,
            trainId: metadata.trainId
        )
    }
    
    /// Create notification content for local updates
    private func createLocalNotificationContent(alertType: String, train: Train) -> (String, String) {
        let trainNumber = train.trainId
        
        switch alertType {
        case "track_assigned":
            let track = train.track ?? "TBD"
            return ("Track Assigned! 🚂", "Track \(track) - Get Ready to Board")
        case "boarding":
            return ("Time to Board! 🚆", "\(trainNumber) is now boarding")
        case "departure":
            return ("Train Departed 🚄", "\(trainNumber) has left the station")
        case "approaching":
            return ("Approaching Stop 📍", "\(trainNumber) approaching next station")
        case "delay":
            let delayMinutes = train.delayMinutes ?? 0
            return ("Delay Alert ⏰", "\(trainNumber) delayed by \(delayMinutes) minutes")
        default:
            return ("Train Update 🚂", "\(trainNumber) status updated")
        }
    }
    
    private func handleStatusChange(from oldStatusV2: String?, to newStatusV2: String?) async {
        guard let oldStatus = oldStatusV2, 
              let newStatus = newStatusV2, 
              oldStatus != newStatus else { return }
        
        // Generate haptic feedback for important status changes
        let haptic: UINotificationFeedbackGenerator.FeedbackType?
        
        switch newStatus {
        case "BOARDING":
            haptic = .success
        case "DELAYED":
            haptic = .warning
        case "EN_ROUTE", "DEPARTED":
            haptic = .success
        default:
            haptic = nil
        }
        
        if let hapticType = haptic {
            await MainActor.run {
                let notification = UINotificationFeedbackGenerator()
                notification.notificationOccurred(hapticType)
            }
        }
        
        // REMOVED: Local notification - will be handled by backend push updates
        
        print("📱 Status changed from \(oldStatus) to \(newStatus)")
    }
    
    // MARK: - Auto-End Conditions
    
    private func shouldAutoEndActivity(train: Train, state: TrainActivityAttributes.ContentState) -> Bool {
        // End if arrived at final destination
        if case .arrived = state.currentLocation {
            return true
        }
        
        // Only end if journey is complete AND the train is actually arrived/departed
        // Don't end just based on progress percentage alone, as this can be inaccurate
        if state.journeyProgress >= 1.0 {
            switch state.currentLocation {
            case .arrived:
                return true // Actually arrived
            case .departed(_, let minutesAgo):
                return minutesAgo > 60 // Departed over an hour ago
            default:
                return false // Don't end if still boarding or en route
            }
        }
        
        // End if train has been departed for a while and we're past the destination ETA
        if train.hasDeparted,
           let destinationETA = state.destinationETA,
           Date() > destinationETA.addingTimeInterval(3600) { // 1 hour buffer
            return true
        }
        
        return false
    }
    
    // MARK: - Helper Methods
    
    private func checkCurrentActivity() {
        // Check if there's an existing activity on app launch
        if let existingActivity = Activity<TrainActivityAttributes>.activities.first {
            currentActivity = existingActivity
            isActivityActive = true
            
            // If resuming, schedule a refresh
            Task {
                if let appDelegate = await UIApplication.shared.delegate as? AppDelegate {
                    await appDelegate.scheduleAppRefresh()
                }
            }
            
            print("📱 Resumed existing Live Activity for train \(existingActivity.attributes.trainNumber)")
        }
    }
    
    /// Check if Live Activities are supported and available
    var isSupported: Bool {
        if #available(iOS 16.1, *) {
            let authInfo = ActivityAuthorizationInfo()
            let notificationSettings = UNUserNotificationCenter.current()
            
            // Check both Live Activities and notification permissions
            return authInfo.areActivitiesEnabled
        }
        return false
    }
    
    /// Get detailed status about Live Activity availability
    var supportStatus: String {
        if #available(iOS 16.1, *) {
            let authInfo = ActivityAuthorizationInfo()
            
            if !authInfo.areActivitiesEnabled {
                return "Live Activities are disabled. Enable them in Settings > Face ID & Passcode > Live Activities."
            }
            
            return "Live Activities are enabled and ready."
        } else {
            return "Live Activities require iOS 16.1 or later."
        }
    }
    
    /// Debug Live Activity permissions and capabilities
    func debugLiveActivityStatus() {
        let authInfo = ActivityAuthorizationInfo()
        print("🔍 Live Activity Debug Status:")
        print("  - iOS version: \(UIDevice.current.systemVersion)")
        print("  - areActivitiesEnabled: \(authInfo.areActivitiesEnabled)")
        print("  - frequentPushesEnabled: \(authInfo.frequentPushesEnabled)")
        print("  - Device model: \(UIDevice.current.model)")
    }
    
    /// Get current activity status for UI
    var activityStatus: String {
        guard let activity = currentActivity else {
            return "No active tracking"
        }
        
        let attributes = activity.attributes
        return "Tracking Train \(attributes.trainNumber)"
    }
    
    // MARK: - Data Validation
    
    /// Validate Live Activity input data
    private func validateLiveActivityData(train: Train, originCode: String, destinationCode: String, origin: String, destination: String) throws {
        // Validate train data
        guard !train.trainId.isEmpty else {
            throw LiveActivityError.invalidData("Train ID cannot be empty")
        }
        
        guard train.id != 0 else {
            throw LiveActivityError.invalidData("Invalid train ID: \(train.id)")
        }
        
        // Validate station codes
        guard !originCode.isEmpty && !destinationCode.isEmpty else {
            throw LiveActivityError.invalidData("Station codes cannot be empty")
        }
        
        guard originCode != destinationCode else {
            throw LiveActivityError.invalidData("Origin and destination cannot be the same")
        }
        
        // Validate station names
        guard !origin.isEmpty && !destination.isEmpty else {
            throw LiveActivityError.invalidData("Station names cannot be empty")
        }
        
        // Validate train number length for Dynamic Island
        guard train.trainId.count <= 10 else {
            throw LiveActivityError.invalidData("Train number too long for Dynamic Island: \(train.trainId)")
        }
    }
    
    /// Validate Live Activity content state
    private func validateContentState(_ state: TrainActivityAttributes.ContentState) throws {
        // Validate statusV2 is not empty
        guard !state.statusV2.isEmpty else {
            throw LiveActivityError.invalidData("StatusV2 cannot be empty")
        }
        
        // Validate journey progress
        guard state.journeyProgress >= 0 && state.journeyProgress <= 1 else {
            throw LiveActivityError.invalidData("Journey progress out of bounds: \(state.journeyProgress)")
        }
        
        // Validate dates are reasonable
        let now = Date()
        if let destinationETA = state.destinationETA {
            // ETA should be within reasonable bounds (not in distant past/future)
            let timeInterval = destinationETA.timeIntervalSince(now)
            guard timeInterval > -3600 && timeInterval < 86400 else { // -1 hour to +24 hours
                throw LiveActivityError.invalidData("Destination ETA out of reasonable bounds")
            }
        }
        
        if let nextStop = state.nextStop {
            let timeInterval = nextStop.estimatedArrival.timeIntervalSince(now)
            guard timeInterval > -3600 && timeInterval < 86400 else {
                throw LiveActivityError.invalidData("Next stop ETA out of reasonable bounds")
            }
        }
    }
    
    /// Sanitize train number for Dynamic Island display
    private func sanitizeTrainNumber(_ trainNumber: String) -> String {
        // Limit to 8 characters for Dynamic Island compatibility
        let sanitized = String(trainNumber.prefix(8))
        return sanitized.isEmpty ? "N/A" : sanitized
    }
    
    /// Sanitize station names for display
    private func sanitizeStationName(_ stationName: String) -> String {
        // No character limit - use full station names
        let sanitized = stationName.trimmingCharacters(in: .whitespacesAndNewlines)
        return sanitized.isEmpty ? "Unknown" : sanitized
    }
}

// MARK: - Error Types

enum LiveActivityError: LocalizedError {
    case notSupported
    case failedToStart(Error)
    case permissionDenied
    case invalidData(String)
    
    var errorDescription: String? {
        switch self {
        case .notSupported:
            return "Live Activities are not supported on this device."
        case .failedToStart(let error):
            return "Failed to start Live Activity: \(error.localizedDescription)."
        case .permissionDenied:
            return "Notifications are disabled. Please enable them in Settings to receive updates."
        case .invalidData(let message):
            return "Invalid Live Activity data: \(message)"
        }
    }
}
