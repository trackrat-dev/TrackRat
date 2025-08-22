import Foundation
import ActivityKit
import UserNotifications
import UIKit

@available(iOS 16.1, *)
class LiveActivityService: ObservableObject {
    static let shared = LiveActivityService()
    
    @Published var currentActivity: Activity<TrainActivityAttributes>?
    @Published var isActivityActive: Bool = false
    
    private var updateTimer: Timer?
    private var pushTokenTask: Task<Void, Never>?
    private var currentPushToken: Data?
    
    private init() {
        checkCurrentActivity()
    }
    
    // MARK: - Activity Management
    
    /// Start tracking a train with Live Activity
    func startTrackingTrain(
        _ train: TrainV2,
        from originCode: String,
        to destinationCode: String,
        origin: String,
        destination: String
    ) async throws {
        // End any existing activity first
        await endCurrentActivity()
        
        // Record Live Activity start for Rat Sense
        RatSenseService.shared.recordLiveActivityStart(from: originCode, to: destinationCode)
        
        // Request notification permissions
        try await requestNotificationPermissions()
        
        // Get scheduled times for the user's journey
        let scheduledDepartureTime = train.getScheduledDepartureTime(fromStationCode: originCode)
        
        // Fetch full train details to get correct destination timing
        let detailedTrain = try await APIService.shared.fetchTrainDetails(
            id: train.trainId, 
            fromStationCode: originCode
        )
        let scheduledArrivalTime = detailedTrain.getScheduledArrivalTime(toStationName: destination)
        
        // Create activity attributes
        let attributes = TrainActivityAttributes(
            trainNumber: train.trainId,
            trainId: train.trainId,
            routeDescription: "\(origin) → \(destination)",
            origin: origin,
            destination: destination,
            originStationCode: originCode,
            destinationStationCode: destinationCode,
            departureTime: train.getDepartureTime(fromStationCode: originCode) ?? train.departureTime,
            scheduledArrivalTime: scheduledArrivalTime,
            theme: "black"
        )
        
        // Determine if train has departed user's origin
        let hasTrainDeparted = self.hasTrainDeparted(train, fromStation: originCode)
        
        // Get next stop arrival time if available
        let nextStopArrivalTime = self.getNextStopArrivalTime(train)
        
        // Calculate proper initial stops using context-aware methods
        let context = JourneyContext(from: originCode, to: destination)
        let contextStatus = train.calculateStatus(for: context)
        let initialCurrentStop = train.stops?.last(where: { $0.hasDepartedStation })?.stationName ?? origin
        let initialNextStop = getNextStopName(train, originCode: originCode, destinationName: destination, hasTrainDeparted: hasTrainDeparted)
        
        // Create simple initial content state
        let initialState = TrainActivityAttributes.ContentState(
            status: contextStatus.rawValue,
            track: train.track,
            currentStopName: initialCurrentStop,
            nextStopName: initialNextStop,
            delayMinutes: train.delayMinutes,
            journeyProgress: 0.0,
            dataTimestamp: Date().timeIntervalSince1970,  // Current timestamp for local data
            scheduledDepartureTime: scheduledDepartureTime?.toISO8601String(),
            scheduledArrivalTime: scheduledArrivalTime?.toISO8601String(),
            nextStopArrivalTime: nextStopArrivalTime?.toISO8601String(),
            hasTrainDeparted: hasTrainDeparted,
            originStationCode: originCode,
            destinationStationCode: destinationCode
        )
        
        // Log initial state details
        print("🚀 Starting Live Activity:")
        print("  - Train: \(train.trainId)")
        print("  - Route: \(origin) → \(destination)")
        print("  - Has Departed: \(hasTrainDeparted)")
        print("  - Initial Progress: 0.0")
        print("  - Track: \(train.track ?? "none")")
        print("  - Scheduled Departure: \(scheduledDepartureTime?.description ?? "none")")
        print("  - Scheduled Arrival: \(scheduledArrivalTime?.description ?? "none")")
        
        // Start the activity
        do {
            let activity = try Activity<TrainActivityAttributes>.request(
                attributes: attributes,
                content: ActivityContent(state: initialState, staleDate: Date().addingTimeInterval(120)),
                pushType: .token
            )
            
            await MainActor.run {
                self.currentActivity = activity
                self.isActivityActive = true
            }
            
            // Subscribe to push token updates (async)
            startPushTokenSubscription(for: activity, train: train, from: originCode, to: destinationCode)
            
            // Start periodic updates every 30 seconds
            startPeriodicUpdates()
            
            print("✅ Live Activity started successfully")
            print("  - Activity ID: \(activity.id)")
            
        } catch {
            print("❌ Failed to start Live Activity: \(error)")
            print("  - Error type: \(type(of: error))")
            print("  - Error details: \(error.localizedDescription)")
            throw error
        }
    }
    
    /// End the current Live Activity
    func endCurrentActivity() async {
        guard let activity = currentActivity else { return }
        
        // Stop periodic updates
        stopPeriodicUpdates()
        
        // Cancel push token subscription
        pushTokenTask?.cancel()
        pushTokenTask = nil
        
        // Unregister push token if we have one
        if let pushToken = currentPushToken {
            let tokenString = pushToken.map { String(format: "%02x", $0) }.joined()
            try? await APIService.shared.unregisterLiveActivityToken(pushToken: tokenString)
        }
        
        // End the activity
        await activity.end(dismissalPolicy: .immediate)
        
        await MainActor.run {
            self.currentActivity = nil
            self.isActivityActive = false
            self.currentPushToken = nil
        }
        
        print("🛑 Live Activity ended")
    }
    
    // MARK: - Updates
    
    private func startPeriodicUpdates() {
        stopPeriodicUpdates()
        
        updateTimer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { _ in
            Task {
                await self.fetchAndUpdateTrain()
            }
        }
    }
    
    private func stopPeriodicUpdates() {
        updateTimer?.invalidate()
        updateTimer = nil
    }
    
    func fetchAndUpdateTrain() async {
        guard let activity = currentActivity else { return }
        
        do {
            let train = try await APIService.shared.fetchTrainDetails(
                id: activity.attributes.trainId,
                fromStationCode: activity.attributes.originStationCode
            )
            
            // Calculate context-aware progress for user's journey
            let context = JourneyContext(from: activity.attributes.originStationCode, to: activity.attributes.destination)
            let progress = train.calculateJourneyProgress(for: context)
            
            print("🔄 Live Activity Update Source: Client calculation (30s timer)")
            print("  - Client calculated progress: \(progress)")
            
            // Get scheduled times and departure status
            let scheduledDepartureTime = train.getScheduledDepartureTime(fromStationCode: activity.attributes.originStationCode)
            let scheduledArrivalTime = train.getScheduledArrivalTime(toStationName: activity.attributes.destination)
            let hasTrainDeparted = self.hasTrainDeparted(train, fromStation: activity.attributes.originStationCode)
            
            // Get current and next stop names using new fields
            let currentStop = train.stops?.last(where: { $0.hasDepartedStation })?.stationName ?? activity.attributes.origin
            let nextStop = getNextStopName(train, originCode: activity.attributes.originStationCode, destinationName: activity.attributes.destination, hasTrainDeparted: hasTrainDeparted)
            let nextStopArrivalTime = self.getNextStopArrivalTime(train)
            
            // Calculate context-aware status
            let contextStatus = train.calculateStatus(for: context)
            
            // Create updated state
            let updatedState = TrainActivityAttributes.ContentState(
                status: contextStatus.rawValue,
                track: train.track,
                currentStopName: currentStop,
                nextStopName: nextStop,
                delayMinutes: train.delayMinutes,
                journeyProgress: progress,
                dataTimestamp: Date().timeIntervalSince1970,  // Current timestamp for local update
                scheduledDepartureTime: scheduledDepartureTime?.toISO8601String(),
                scheduledArrivalTime: scheduledArrivalTime?.toISO8601String(),
                nextStopArrivalTime: nextStopArrivalTime?.toISO8601String(),
                hasTrainDeparted: hasTrainDeparted,
                originStationCode: activity.attributes.originStationCode,
                destinationStationCode: activity.attributes.destinationStationCode
            )
            
            // Log the update details
            print("📊 Live Activity Update:")
            print("  - Progress: \(progress)")
            print("  - Current Stop: \(currentStop)")
            print("  - Next Stop: \(nextStop ?? "none")")
            print("  - Track: \(train.track ?? "none")")
            print("  - Has Departed: \(hasTrainDeparted)")
            print("  - Scheduled Departure: \(scheduledDepartureTime?.description ?? "none")")
            print("  - Scheduled Arrival: \(scheduledArrivalTime?.description ?? "none")")
            
            // Update the activity
            await activity.update(
                ActivityContent(state: updatedState, staleDate: Date().addingTimeInterval(120))
            )
            
            print("✅ Live Activity updated successfully")
            
            // Auto-end if journey is complete using comprehensive check
            if shouldEndActivity(train: train, activity: activity) {
                print("🏁 Live Activity ending due to journey completion")
                print("  - Notifying server to stop updates...")
                
                // Notify server first to stop sending updates
                if let pushToken = currentPushToken {
                    let tokenString = pushToken.map { String(format: "%02x", $0) }.joined()
                    do {
                        try await APIService.shared.unregisterLiveActivityToken(pushToken: tokenString)
                        print("  ✅ Server notified successfully")
                    } catch {
                        print("  ⚠️ Failed to notify server: \(error)")
                        // Continue with local ending anyway
                    }
                }
                
                // Then end locally
                await endCurrentActivity()
            }
            
        } catch {
            print("❌ Failed to update Live Activity: \(error)")
            print("  - Error details: \(error.localizedDescription)")
        }
    }
    
    // MARK: - Push Token Management
    
    private func startPushTokenSubscription(for activity: Activity<TrainActivityAttributes>, train: TrainV2, from originCode: String, to destinationCode: String) {
        // Cancel any existing subscription
        pushTokenTask?.cancel()
        
        pushTokenTask = Task {
            print("🔄 Starting push token subscription for Live Activity...")
            
            do {
                for await pushToken in activity.pushTokenUpdates {
                    print("📡 Received Live Activity push token: \(pushToken.prefix(20))...")
                    
                    // Store the token for later use (e.g., unregistration)
                    await MainActor.run {
                        self.currentPushToken = pushToken
                    }
                    
                    // Register with backend
                    await registerPushToken(pushToken, for: train, from: originCode, to: destinationCode)
                    
                    // We only need the first token, so break
                    break
                }
            } catch {
                print("❌ Push token subscription failed: \(error)")
            }
        }
    }
    
    // MARK: - Push Token Registration
    
    private func registerPushToken(_ token: Data, for train: TrainV2, from originCode: String, to destinationCode: String) async {
        let tokenString = token.map { String(format: "%02x", $0) }.joined()
        print("🔧 Converting push token to string: \(tokenString.prefix(20))...")
        
        Task {
            for activity in Activity<TrainActivityAttributes>.activities {
                if activity.id == currentActivity?.id {
                    print("📤 Making HTTP request to register Live Activity token...")
                    do {
                        try await APIService.shared.registerLiveActivityToken(
                            pushToken: tokenString,
                            activityId: activity.id,
                            trainNumber: train.trainId,
                            originCode: originCode,
                            destinationCode: destinationCode
                        )
                        print("✅ Live Activity token registration successful")
                    } catch {
                        print("❌ Live Activity token registration failed: \(error)")
                    }
                    break // Only register for the current activity
                }
            }
        }
    }
    
    // MARK: - Permissions
    
    private func requestNotificationPermissions() async throws {
        let center = UNUserNotificationCenter.current()
        let granted = try await center.requestAuthorization(options: [.alert, .sound, .badge])
        
        if !granted {
            throw LiveActivityError.permissionDenied
        }
    }
    
    // MARK: - Utilities
    
    private func checkCurrentActivity() {
        // Check if there's an existing activity
        if let activity = Activity<TrainActivityAttributes>.activities.first {
            self.currentActivity = activity
            self.isActivityActive = true
            startPeriodicUpdates()
            
            // Note: For existing activities, we don't start a new push token subscription
            // since we don't have the original train data. The activity should already
            // be registered if it was created properly.
            print("📱 Found existing Live Activity: \(activity.id)")
        }
    }
    
    // MARK: - Helper Methods
    
    /// Simple check using the same logic as the Live Activity widget
    func shouldEndActivity(train: TrainV2, activity: Activity<TrainActivityAttributes>) -> Bool {
        print("🔍 Checking if Live Activity should end (using widget logic):")
        print("  - Train: \(train.trainId)")
        print("  - Origin: \(activity.attributes.originStationCode)")
        print("  - Destination: \(activity.attributes.destination)")
        
        // Get the content state that the widget uses
        let contentState = train.toLiveActivityContentState(from: activity.attributes.originStationCode, to: activity.attributes.destination)
        
        // Use the exact same logic as the widget: if minutesUntilArrival <= 0, journey is complete
        if let minutesUntilArrival = contentState.minutesUntilArrival {
            print("  - Minutes until arrival: \(minutesUntilArrival)")
            
            if minutesUntilArrival <= 0 {
                print("  ✅ Journey complete - widget shows 'Arrived' (minutes: \(minutesUntilArrival))")
                return true
            } else {
                print("  ❌ Journey not complete - widget shows 'Arriving in \(minutesUntilArrival) minutes'")
                return false
            }
        }
        
        // Fallback: If no arrival time available, use failsafe timeout
        if let scheduledArrival = train.getScheduledArrivalTime(toStationName: activity.attributes.destination) {
            let bufferTime: TimeInterval = 30 * 60 // 30 minutes
            let now = Date()
            
            if now > scheduledArrival.addingTimeInterval(bufferTime) {
                print("  ✅ Journey complete - failsafe timeout (30min past scheduled arrival)")
                return true
            }
        }
        
        print("  ⚠️ No arrival time data available - continuing Live Activity")
        return false
    }
    
    /// Determine if train has departed from the user's origin station
    private func hasTrainDeparted(_ train: TrainV2, fromStation originCode: String) -> Bool {
        // Use the context-aware method from TrainV2
        return train.hasTrainDepartedFromStation(originCode)
    }
    
    /// Get the next stop arrival time
    private func getNextStopArrivalTime(_ train: TrainV2) -> Date? {
        // Find the next non-departed stop using new field
        if let stops = train.stops {
            // Find first stop that hasn't departed
            for stop in stops {
                if !stop.hasDepartedStation {
                    return stop.updatedArrival ?? stop.scheduledArrival
                }
            }
        }
        
        return nil
    }
    
    /// Get the next stop name for user's journey segment
    private func getNextStopName(_ train: TrainV2, originCode: String, destinationName: String, hasTrainDeparted: Bool) -> String? {
        guard let stops = train.stops else { return nil }
        
        // Find origin and destination stops
        let originIndex = stops.firstIndex { $0.stationCode == originCode }
        let destinationIndex = stops.lastIndex { $0.stationName.lowercased().contains(destinationName.lowercased()) }
        
        guard let fromIndex = originIndex, let toIndex = destinationIndex, fromIndex < toIndex else {
            return nil
        }
        
        // Get the journey segment stops
        let journeyStops = Array(stops[fromIndex...toIndex])
        
        // If train hasn't departed from origin, next stop is origin station
        if !hasTrainDeparted {
            return journeyStops.first?.stationName
        }
        
        // If train has departed, find next non-departed stop in journey
        return journeyStops.first(where: { !$0.hasDepartedStation })?.stationName
    }
    
    // MARK: - Compatibility Methods for TrackRatApp
    
    /// Simplified method for critical notifications - just logs for now
    func sendCriticalBannerNotification(title: String, body: String, priority: String, trainId: String) async {
        print("🔔 Critical notification (simplified): \(title) - \(body)")
        // In a simplified architecture, we could just trigger a local notification
        // but for now, we'll just log it
    }
    
    /// Simplified refresh method - just calls fetchAndUpdateTrain
    func refreshCurrentActivity() async {
        await fetchAndUpdateTrain()
    }
}

// MARK: - Errors

enum LiveActivityError: LocalizedError {
    case permissionDenied
    case invalidData(String)
    
    var errorDescription: String? {
        switch self {
        case .permissionDenied:
            return "Notification permissions are required for Live Activities"
        case .invalidData(let message):
            return "Invalid data: \(message)"
        }
    }
}