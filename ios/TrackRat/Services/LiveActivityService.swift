import Foundation
import ActivityKit
import UserNotifications
import UIKit

// MARK: - ActivityKit Protocols

@available(iOS 16.1, *)
protocol TRActivityProtocol {
    var id: String { get }
    var activityState: ActivityState { get }
    var pushToken: Data? { get }
    
    // Type-erased properties and methods
    var trainAttributes: TrainActivityAttributes? { get }
    var trainContentState: TrainActivityAttributes.ContentState? { get }
    
    func updateTrain(state: TrainActivityAttributes.ContentState, staleDate: Date?, alertConfiguration: AlertConfiguration?) async
    func endTrain(state: TrainActivityAttributes.ContentState?, dismissalPolicy: ActivityUIDismissalPolicy) async
}

@available(iOS 16.1, *)
protocol TRActivityKitModuleProtocol {
    func request<Attributes: ActivityAttributes>(
        attributes: Attributes,
        content: ActivityContent<Attributes.ContentState>,
        pushType: PushType?
    ) async throws -> (any TRActivityProtocol)? where Attributes.ContentState: Codable & Sendable

    var activities: [any TRActivityProtocol] { get }
    func authorizationInfo() -> ActivityAuthorizationInfo
}

// MARK: - Concrete Implementations

@available(iOS 16.1, *)
class ConcreteActivity<A: ActivityAttributes>: TRActivityProtocol {
    private let activity: Activity<A>

    init(activity: Activity<A>) {
        self.activity = activity
    }

    var id: String {
        activity.id
    }

    var activityState: ActivityState {
        activity.activityState
    }

    var pushToken: Data? {
        activity.pushToken
    }
    
    var trainAttributes: TrainActivityAttributes? {
        activity.attributes as? TrainActivityAttributes
    }
    
    var trainContentState: TrainActivityAttributes.ContentState? {
        activity.content.state as? TrainActivityAttributes.ContentState
    }

    func updateTrain(state: TrainActivityAttributes.ContentState, staleDate: Date?, alertConfiguration: AlertConfiguration?) async {
        guard let trainState = state as? A.ContentState else { return }
        let activityContent = ActivityContent(state: trainState, staleDate: staleDate ?? Date(), relevanceScore: 0.0)
        await activity.update(activityContent, alertConfiguration: alertConfiguration)
    }

    func endTrain(state: TrainActivityAttributes.ContentState?, dismissalPolicy: ActivityUIDismissalPolicy) async {
        let finalContent: ActivityContent<A.ContentState>?
        if let finalState = state, let trainState = finalState as? A.ContentState {
            finalContent = ActivityContent(state: trainState, staleDate: Date(), relevanceScore: 0.0)
        } else {
            finalContent = nil
        }
        await activity.end(finalContent, dismissalPolicy: dismissalPolicy)
    }
}

@available(iOS 16.1, *)
class ConcreteActivityKitModule: TRActivityKitModuleProtocol {

    func request<A: ActivityAttributes>(
        attributes: A,
        content: ActivityContent<A.ContentState>,
        pushType: PushType?
    ) async throws -> (any TRActivityProtocol)? where A.ContentState : Decodable, A.ContentState : Encodable, A.ContentState : Sendable {
        let realActivity = try await Activity<A>.request(
            attributes: attributes,
            content: content,
            pushType: pushType
        )
        return ConcreteActivity(activity: realActivity)
    }

    var activities: [any TRActivityProtocol] {
        return Activity<TrainActivityAttributes>.activities.map { ConcreteActivity(activity: $0) }
    }

    func authorizationInfo() -> ActivityAuthorizationInfo {
        return ActivityAuthorizationInfo()
    }
}

// MARK: - Live Activity Service

@available(iOS 16.1, *)
class LiveActivityService: ObservableObject {
    // Make shared instance use the new initializer with default UNUserNotificationCenter and ConcreteActivityKitModule
    static let shared = LiveActivityService(notificationCenter: .current(), activityKitModule: ConcreteActivityKitModule())
    
    @Published var currentActivity: (any TRActivityProtocol)? // Changed to protocol type
    @Published var isActivityActive: Bool = false
    
    private var updateTimer: Timer?
    private var lastKnownStatus: TrainStatus?
    private var lastKnownStops: [Stop] = []
    private var lastDepartedStopIndex: Int?
    private var approachingNotificationsSent: Set<String> = []

    // Instance of UNUserNotificationCenter, injectable for testing
    private let notificationCenter: UNUserNotificationCenter
    // Instance of TRActivityKitModuleProtocol, injectable for testing
    private let activityKitModule: TRActivityKitModuleProtocol
    
    // Designated initializer
    init(
        notificationCenter: UNUserNotificationCenter = .current(),
        activityKitModule: TRActivityKitModuleProtocol = ConcreteActivityKitModule()
    ) {
        self.notificationCenter = notificationCenter
        self.activityKitModule = activityKitModule
        checkCurrentActivity() // Check for existing activities on init
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
        
        // Request permissions
        try await requestPermissions()
        
        // Create activity attributes
        let attributes = TrainActivityAttributes(
            trainNumber: train.trainId,
            trainId: String(train.id),
            routeDescription: "\(origin) → \(destination)",
            origin: origin,
            destination: destination,
            originStationCode: originCode,
            destinationStationCode: destinationCode
        )
        
        // Create initial content state
        let initialState = train.toLiveActivityContentState(
            from: originCode,
            to: destinationCode
        )
        
        // Start the activity
        do {
            // Use the activityKitModule to request the activity
            let requestedActivity = try await activityKitModule.request(
                attributes: attributes,
                content: ActivityContent(state: initialState, staleDate: nil), // Use ActivityContent directly
                pushType: nil
            )
            
            guard let activity = requestedActivity else {
                // This case should ideally be handled by the module throwing an error if request truly fails.
                // Or if request can return nil for non-error "cannot start now" cases.
                throw LiveActivityError.failedToStart(NSError(domain: "LiveActivityService", code: -1, userInfo: [NSLocalizedDescriptionKey: "Activity request returned nil"]))
            }

            await MainActor.run {
                self.currentActivity = activity // Assigning the protocol type
                self.isActivityActive = true
                self.lastKnownStatus = train.status
                self.lastKnownStops = train.stops ?? []
            }
            
            // Start background updates - ensure attributes are accessible from the protocol
            // We might need to cast currentActivity.attributes if TRActivityProtocol's associatedtype isn't constrained
            // For now, assuming currentActivity holds TrainActivityAttributes compatible attributes
            if let trainAttributes = activity.trainAttributes {
                 startBackgroundUpdates(trainId: train.id, attributes: trainAttributes)
            } else {
                // Handle case where attributes are not the expected type, though this shouldn't happen
                // if request is type-safe.
                print("Error: Activity attributes are not of type TrainActivityAttributes")
            }
            
            // Send haptic feedback
            await MainActor.run {
                let impact = UIImpactFeedbackGenerator(style: .medium)
                impact.impactOccurred()
            }
            
            // Send push notification for starting to watch
            await sendTrackingStartedNotification(train: train, route: "\(origin) → \(destination)")
            
            print("✅ Live Activity started for train \(train.trainId)")
            
        } catch {
            print("❌ Failed to start Live Activity: \(error)")
            throw LiveActivityError.failedToStart(error)
        }
    }
    
    /// Update the current Live Activity with new train data
    func updateActivity(with train: Train) async {
        guard let activity = currentActivity else { return }
        
        // We need to cast attributes to TrainActivityAttributes to access its specific properties
        guard let attributes = activity.trainAttributes else {
            print("Error: Could not cast activity attributes to TrainActivityAttributes for update.")
            return
        }

        let newState = train.toLiveActivityContentState(
            from: attributes.originStationCode, // Now accessible
            to: attributes.destinationStationCode, // Now accessible
            lastKnownStatus: lastKnownStatus
        )
        
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
        
        // Use the simpler state update on the protocol
        await activity.updateTrain(state: newState, staleDate: nil, alertConfiguration: nil)
        
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
        guard let activity = currentActivity else { return }
        
        // Cast attributes to TrainActivityAttributes
        guard let attributes = activity.trainAttributes else {
            print("Error: Could not cast activity attributes to TrainActivityAttributes for refresh.")
            return
        }
        guard let trainId = Int(attributes.trainId) else { return } // trainId is part of TrainActivityAttributes
        
        await fetchAndUpdateTrain(trainId: trainId, attributes: attributes) // attributes is now TrainActivityAttributes
    }
    
    /// End the current Live Activity
    func endCurrentActivity() async {
        guard let activity = currentActivity else { return }
        
        stopBackgroundUpdates()
        
        // Use the simpler end method from the protocol
        let finalState = activity.trainContentState
        await activity.endTrain(state: finalState, dismissalPolicy: .immediate)
        
        await MainActor.run {
            self.currentActivity = nil
            self.isActivityActive = false
            self.lastKnownStatus = nil
            self.lastKnownStops = []
            self.lastDepartedStopIndex = nil
            self.approachingNotificationsSent.removeAll()
        }
        
        print("🛑 Live Activity ended")
    }
    
    // MARK: - Background Updates
    
    private func startBackgroundUpdates(trainId: Int, attributes: TrainActivityAttributes) {
        stopBackgroundUpdates() // Stop any existing timer
        
        // Ensure timer runs on main thread
        DispatchQueue.main.async { [weak self] in
            self?.updateTimer = Timer.scheduledTimer(withTimeInterval: 30.0, repeats: true) { [weak self] _ in
                print("⏰ Background timer fired for train \(attributes.trainNumber)")
                Task {
                    await self?.fetchAndUpdateTrain(trainId: trainId, attributes: attributes)
                }
            }
            print("🕐 Background timer started for train \(attributes.trainNumber) - will fire every 30 seconds")
        }
    }
    
    private func stopBackgroundUpdates() {
        if updateTimer != nil {
            print("🛑 Stopping background timer")
            updateTimer?.invalidate()
            updateTimer = nil
        }
    }
    
    private func fetchAndUpdateTrain(trainId: Int, attributes: TrainActivityAttributes) async {
        do {
            print("🔄 Making API request for train \(attributes.trainNumber) from \(attributes.originStationCode)")
            let train = try await APIService.shared.fetchTrainDetailsFlexible(
                trainId: attributes.trainNumber,
                fromStationCode: attributes.originStationCode
            )
            print("✅ API request successful for train \(attributes.trainNumber)")
            await updateActivity(with: train)
        } catch {
            print("❌ Failed to fetch train data for Live Activity update: \(error)")
            print("❌ Full error details: \(String(describing: error))")
        }
    }
    
    // MARK: - Stop Departure Detection
    
    private func detectAndNotifyStopDepartures(
        newStops: [Stop],
        train: Train,
        originCode: String,
        destinationCode: String
    ) async {
        guard let activity = currentActivity,
              let attributes = activity.trainAttributes else { return }
        // attributes is now TrainActivityAttributes
        
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
        attributes: TrainActivityAttributes, // This was already TrainActivityAttributes, no change needed here
        stopsRemaining: Int,
        nextStop: Stop?
    ) async {
        let content = UNMutableNotificationContent()
        
        // attributes is already TrainActivityAttributes from the calling context
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
            try await self.notificationCenter.add(request)
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
        guard let activity = currentActivity,
              let attributes = activity.trainAttributes else { return }
        // attributes is now TrainActivityAttributes
        
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
        attributes: TrainActivityAttributes, // This was already TrainActivityAttributes
        minutesAway: Int,
        isDestination: Bool
    ) async {
        let content = UNMutableNotificationContent()
        
        // attributes is already TrainActivityAttributes
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
            try await self.notificationCenter.add(request)
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
    
    private func requestPermissions() async throws {
        // Request Live Activity permission (automatic prompt if needed)
        let settings = await self.notificationCenter.notificationSettings()
        let authorizationStatus = settings.authorizationStatus
        
        if authorizationStatus == .notDetermined {
            let granted = try await self.notificationCenter.requestAuthorization(options: [.alert, .sound, .badge])
            if !granted {
                print("⚠️ Notification permission not granted")
            }
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
            try await self.notificationCenter.add(request)
            print("📱 Sent tracking started notification")
        } catch {
            print("❌ Failed to send tracking started notification: \(error)")
        }
    }
    
    private func sendStatusChangeNotification(from oldStatus: TrainStatus, to newStatus: TrainStatus) async {
        guard let activity = currentActivity,
              let attributes = activity.trainAttributes else { return }
        // attributes is now TrainActivityAttributes
        
        let content = UNMutableNotificationContent()
        // No need to redefine attributes, it's already casted above
        
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
            try await self.notificationCenter.add(request)
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
        // Use the activityKitModule to get current activities
        if let existingActivityProtocol = activityKitModule.activities.first(where: { $0.trainAttributes != nil }) {
            // Assuming we only care about resuming activities with TrainActivityAttributes
            // And that `activities` returns `any TRActivityProtocol`
            self.currentActivity = existingActivityProtocol // Assigning the protocol type
            self.isActivityActive = true
            
            // Resume background updates if needed
            if let attributes = existingActivityProtocol.trainAttributes,
               let trainId = Int(attributes.trainId) {
                startBackgroundUpdates(trainId: trainId, attributes: attributes)
                print("📱 Resumed existing Live Activity for train \(attributes.trainNumber)")
            } else {
                 print("Error: Could not resume activity due to attribute type mismatch or missing trainId.")
            }
            
        }
    }

    /// Check if Live Activities are supported and available
    var isSupported: Bool {
        if #available(iOS 16.1, *) {
            // Use the activityKitModule to get authorization info
            return activityKitModule.authorizationInfo().areActivitiesEnabled
        }
        return false
    }

    /// Get current activity status for UI
    var activityStatus: String {
        guard let activity = currentActivity,
              let attributes = activity.trainAttributes else {
            return "No active tracking"
        }
        return "Tracking Train \(attributes.trainNumber)"
    }
}

// MARK: - Error Types

enum LiveActivityError: LocalizedError {
    case notSupported
    case failedToStart(Error)
    case permissionDenied
    
    var errorDescription: String? {
        switch self {
        case .notSupported:
            return "Live Activities are not supported on this device"
        case .failedToStart(let error):
            return "Failed to start Live Activity: \(error.localizedDescription)"
        case .permissionDenied:
            return "Permission denied for Live Activities"
        }
    }
}