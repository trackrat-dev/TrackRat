import Foundation
import ActivityKit
import UserNotifications
import UIKit

@available(iOS 16.1, *)
class LiveActivityService: ObservableObject {
    static let shared = LiveActivityService()
    
    @Published var currentActivity: Activity<TrainActivityAttributes>?
    @Published var isActivityActive: Bool = false
    
    private var lastKnownStatus: TrainStatus?
    private var lastKnownStops: [Stop] = []
    private var lastDepartedStopIndex: Int?
    private var approachingNotificationsSent: Set<String> = []
    
    private init() {
        checkCurrentActivity()
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
        
        // Check and request notification permissions
        try await checkAndRequestNotificationPermissions()
        
        // Validate input data before creating Live Activity
        try validateLiveActivityData(train: train, originCode: originCode, destinationCode: destinationCode, origin: origin, destination: destination)
        
        // Create activity attributes with validated data
        let attributes = TrainActivityAttributes(
            trainNumber: sanitizeTrainNumber(train.trainId),
            trainId: String(train.id),
            routeDescription: "\(sanitizeStationName(origin)) → \(sanitizeStationName(destination))",
            origin: sanitizeStationName(origin),
            destination: sanitizeStationName(destination),
            originStationCode: originCode,
            destinationStationCode: destinationCode
        )
        
        // Create initial content state with validation
        let initialState = train.toLiveActivityContentState(
            from: originCode,
            to: destinationCode
        )
        
        // Final validation of content state
        try validateContentState(initialState)
        
        // Start the activity with enhanced error handling
        do {
            // Check if Live Activities are available
            guard ActivityAuthorizationInfo().areActivitiesEnabled else {
                throw LiveActivityError.permissionDenied
            }
            
            let activity = try Activity<TrainActivityAttributes>.request(
                attributes: attributes,
                content: .init(state: initialState, staleDate: nil),
                pushType: nil
            )
            
            await MainActor.run {
                self.currentActivity = activity
                self.isActivityActive = true
                self.lastKnownStatus = train.status
                self.lastKnownStops = train.stops ?? []
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
            
            // Send push notification for starting to watch
            await sendTrackingStartedNotification(train: train, route: "\(sanitizeStationName(origin)) → \(sanitizeStationName(destination))")
            
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
            lastKnownStatus: lastKnownStatus
        )
        
        // Validate new state before updating
        do {
            try validateContentState(newState)
        } catch {
            print("❌ Invalid content state, skipping Live Activity update: \(error)")
            return
        }
        
        // Check for stop departures and approaching stops
        if let stops = train.stops {
            await detectAndNotifyStopDepartures(
                newStops: stops,
                train: train,
                originCode: attributes.originStationCode,
                destinationCode: attributes.destinationStationCode
            )
            
            await detectAndNotifyApproachingStops(
                stops: stops,
                train: train,
                originCode: attributes.originStationCode,
                destinationCode: attributes.destinationStationCode
            )
            
            // Update stored stops state
            await MainActor.run {
                self.lastKnownStops = stops
            }
        }
        
        // Check for status changes that warrant haptic feedback
        if newState.hasStatusChanged {
            await handleStatusChange(from: lastKnownStatus, to: train.status)
        }
        
        // Update activity
        await activity.update(.init(state: newState, staleDate: nil))
        
        await MainActor.run {
            self.lastKnownStatus = train.status
        }
        
        print("🔄 Live Activity updated for train \(train.trainId)")
        
        // Check if we should auto-end the activity
        if shouldAutoEndActivity(train: train, state: newState) {
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
        await activity.end(.init(state: finalState, staleDate: nil), dismissalPolicy: .immediate)
        
        await MainActor.run {
            self.currentActivity = nil
            self.isActivityActive = false
            self.lastKnownStatus = nil
            self.lastKnownStops = []
            self.lastDepartedStopIndex = nil
            self.approachingNotificationsSent.removeAll()
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
        guard let _ = Int(attributes.trainId) else { // trainId is String, but APIService expects Int for trainNumber
            print("❌ Invalid trainId in current activity attributes: \(attributes.trainId)")
            return
        }

        do {
            print("🔄 Making API request for train \(attributes.trainNumber) from \(attributes.originStationCode) (background)")
            let train = try await APIService.shared.fetchTrainDetailsFlexible(
                trainId: attributes.trainNumber, // This is the train number (e.g., "P625")
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
                    // Send departure notification
                    await sendStopDepartureNotification(
                        stop: stop,
                        train: train,
                        attributes: attributes,
                        stopsRemaining: destIndex - index,
                        nextStop: index < destIndex ? newStops[index + 1] : nil
                    )
                    
                    // Store the last departed stop index
                    await MainActor.run {
                        self.lastDepartedStopIndex = index
                    }
                }
            }
        }
    }
    
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
                        await sendApproachingStopNotification(
                            stop: stop,
                            train: train,
                            attributes: attributes,
                            minutesAway: minutesToArrival,
                            isDestination: stop.stationName == attributes.destination
                        )
                        
                        // Mark as sent
                        _ = await MainActor.run {
                            self.approachingNotificationsSent.insert(notificationKey)
                        }
                    }
                }
            }
        }
    }
    
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
            print("📍 Sent approaching notification for \(stop.stationName)")
            
            // Haptic feedback for approaching stops
            await MainActor.run {
                let notification = UINotificationFeedbackGenerator()
                notification.notificationOccurred(isDestination ? .warning : .success)
            }
        } catch {
            print("❌ Failed to send approaching stop notification: \(error)")
        }
    }
    
    // MARK: - Permissions and Notifications
    
    public func checkAndRequestNotificationPermissions() async throws {
        let center = UNUserNotificationCenter.current()
        let settings = await center.notificationSettings()

        switch settings.authorizationStatus {
        case .notDetermined:
            print("Notification permission not determined. Requesting authorization...")
            let granted = try await center.requestAuthorization(options: [.alert, .sound, .badge])
            if !granted {
                print("⚠️ Notification permission not granted")
                // Continue anyway as Live Activities can work without notifications
            }
            print("✅ Notification permission granted.")
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
    
    private func sendStatusChangeNotification(from oldStatus: TrainStatus, to newStatus: TrainStatus) async {
        guard let activity = currentActivity else { return }
        
        let content = UNMutableNotificationContent()
        let attributes = activity.attributes
        
        switch newStatus {
        case .boarding:
            content.title = "🚪 Train \(attributes.trainNumber) is Boarding!"
            content.body = "Your train to \(attributes.destination) is now boarding"
            content.sound = .default
        case .delayed:
            content.title = "⏰ Train \(attributes.trainNumber) Delayed"
            content.body = "Your train to \(attributes.destination) has been delayed"
            content.sound = .default
        case .departed:
            content.title = "🚆 Train \(attributes.trainNumber) Departed"
            content.body = "Your train to \(attributes.destination) has left the station"
            content.sound = .default
        default:
            return // Don't send notifications for other status changes
        }
        
        let request = UNNotificationRequest(
            identifier: "status-change-\(attributes.trainNumber)-\(Date().timeIntervalSince1970)",
            content: content,
            trigger: nil // Immediate notification
        )
        
        do {
            try await UNUserNotificationCenter.current().add(request)
            print("📱 Sent status change notification: \(oldStatus.displayText) → \(newStatus.displayText)")
        } catch {
            print("❌ Failed to send status change notification: \(error)")
        }
    }
    
    private func handleStatusChange(from oldStatus: TrainStatus?, to newStatus: TrainStatus) async {
        guard let oldStatus = oldStatus, oldStatus != newStatus else { return }
        
        // Generate haptic feedback for important status changes
        let haptic: UINotificationFeedbackGenerator.FeedbackType?
        
        switch newStatus {
        case .boarding:
            haptic = .success
        case .delayed:
            haptic = .warning
        case .departed:
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
        
        // Send push notification for status changes
        await sendStatusChangeNotification(from: oldStatus, to: newStatus)
        
        print("📱 Status changed from \(oldStatus.displayText) to \(newStatus.displayText)")
    }
    
    // MARK: - Auto-End Conditions
    
    private func shouldAutoEndActivity(train: Train, state: TrainActivityAttributes.ContentState) -> Bool {
        // End if arrived
        if case .arrived = state.currentLocation {
            return true
        }
        
        // End if journey is complete (100% progress)
        if state.journeyProgress >= 1.0 {
            return true
        }
        
        // End if train has been departed for a while and we're past the destination ETA
        if train.status == .departed,
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
            return ActivityAuthorizationInfo().areActivitiesEnabled
        }
        return false
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
        
        guard train.id > 0 else {
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
        // Validate status has displayText
        guard !state.status.displayText.isEmpty else {
            throw LiveActivityError.invalidData("Status display text cannot be empty")
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
        // Limit to 20 characters for display
        let sanitized = String(stationName.prefix(20))
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
