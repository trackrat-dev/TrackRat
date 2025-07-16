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
        
        // Request notification permissions
        try await requestNotificationPermissions()
        
        // Get scheduled times for the user's journey
        let scheduledDepartureTime = train.getScheduledDepartureTime(fromStationCode: originCode)
        let scheduledArrivalTime = train.getScheduledArrivalTime(toStationName: destination)
        
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
            scheduledArrivalTime: scheduledArrivalTime
        )
        
        // Determine if train has departed user's origin
        let hasTrainDeparted = self.hasTrainDeparted(train, fromStation: originCode)
        
        // Get next stop arrival time if available
        let nextStopArrivalTime = self.getNextStopArrivalTime(train)
        
        // Calculate proper initial stops using context-aware methods
        let context = JourneyContext(from: originCode, to: destination)
        let contextStatus = train.calculateStatus(for: context)
        let initialCurrentStop = train.stops?.last(where: { $0.hasDepartedStation })?.stationName ?? origin
        let initialNextStop = train.stops?.first(where: { !$0.hasDepartedStation })?.stationName
        
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
            
            // Get current and next stop names using new fields
            let currentStop = train.stops?.last(where: { $0.hasDepartedStation })?.stationName ?? activity.attributes.origin
            let nextStop = train.stops?.first(where: { !$0.hasDepartedStation })?.stationName
            
            // Get scheduled times and departure status
            let scheduledDepartureTime = train.getScheduledDepartureTime(fromStationCode: activity.attributes.originStationCode)
            let scheduledArrivalTime = train.getScheduledArrivalTime(toStationName: activity.attributes.destination)
            let hasTrainDeparted = self.hasTrainDeparted(train, fromStation: activity.attributes.originStationCode)
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
            
            // Auto-end if journey is complete
            if progress >= 1.0 {
                print("🏁 Journey complete, ending Live Activity")
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