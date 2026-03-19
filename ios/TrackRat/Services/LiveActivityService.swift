import Foundation
import ActivityKit
import UserNotifications
import UIKit

@MainActor
class LiveActivityService: ObservableObject {
    static let shared = LiveActivityService()

    @Published var currentActivity: Activity<TrainActivityAttributes>?
    @Published var isActivityActive: Bool = false
    @Published var journeyStationCodes: [String] = []
    @Published var journeyDataSource: String = ""

    private var updateTimer: Timer?
    private var pushTokenTask: Task<Void, Never>?
    private var currentPushToken: Data?
    private let cacheService = TrainCacheService.shared

    /// Tracks whether train has departed from user's origin (fires events once on transition)
    private var hasDepartedOrigin: Bool = false

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

        // Reset trip recording state for new journey
        TripRecordingService.shared.reset()

        // Reset departure tracking for new journey
        hasDepartedOrigin = false

        // Record Live Activity start for Rat Sense
        RatSenseService.shared.recordLiveActivityStart(from: originCode, to: destinationCode)

        // Request notification permissions
        do {
            try await requestNotificationPermissions()
        } catch {
            throw error
        }

        // Get estimated times for the user's journey using existing train data
        // (We'll refresh with detailed data after the activity starts for snappier UX)
        // Use estimated times (delay-adjusted) so Live Activity shows accurate arrival times
        let estimatedDepartureTime = train.getEstimatedDepartureTime(fromStationCode: originCode)
        let estimatedArrivalTime = train.getEstimatedArrivalTime(toStationCode: destinationCode)
        let scheduledArrivalTime = train.getScheduledArrivalTime(toStationCode: destinationCode)

        // Store data source for system filtering
        await MainActor.run {
            self.journeyDataSource = train.dataSource
        }

        // Extract journey station codes from origin to destination using existing stops
        if let stops = train.stops {
            let sortedStops = stops.sorted { $0.sequence < $1.sequence }
            if let originIndex = sortedStops.firstIndex(where: { Stations.areEquivalentStations($0.stationCode, originCode) }),
               let destIndex = sortedStops.lastIndex(where: { Stations.areEquivalentStations($0.stationCode, destinationCode) }),
               originIndex <= destIndex {
                let journeyStops = sortedStops[originIndex...destIndex]
                await MainActor.run {
                    self.journeyStationCodes = journeyStops.map { $0.stationCode }
                }
            }
        }

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
        let context = JourneyContext(from: originCode, toCode: destinationCode, toName: destination)
        let contextStatus = train.calculateStatus(for: context)
        let initialCurrentStop = train.stops?.last(where: { $0.hasDepartedStation })?.stationName ?? origin
        let initialNextStop = getNextStopName(train, originCode: originCode, destinationCode: destinationCode, hasTrainDeparted: hasTrainDeparted)
        let initialNextStopCode = getNextStopCode(train, originCode: originCode, destinationCode: destinationCode, hasTrainDeparted: hasTrainDeparted)

        // Create simple initial content state
        let initialState = TrainActivityAttributes.ContentState(
            status: contextStatus.rawValue,
            track: train.track,
            currentStopName: initialCurrentStop,
            nextStopName: initialNextStop,
            delayMinutes: train.delayMinutes,
            journeyProgress: 0.0,
            dataTimestamp: Date().timeIntervalSince1970,  // Current timestamp for local data
            scheduledDepartureTime: estimatedDepartureTime?.toISO8601String(),
            scheduledArrivalTime: estimatedArrivalTime?.toISO8601String(),
            nextStopArrivalTime: nextStopArrivalTime?.toISO8601String(),
            nextStopCode: initialNextStopCode,
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
        print("  - Estimated Departure: \(estimatedDepartureTime?.description ?? "none")")
        print("  - Estimated Arrival: \(estimatedArrivalTime?.description ?? "none")")

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

            // Start periodic updates every 30 seconds (must be on main thread for Timer)
            await MainActor.run {
                startPeriodicUpdates()
            }

            // Reset journey feedback state for new activity
            await JourneyFeedbackService.shared.onActivityStarted()

            print("✅ Live Activity started successfully")
            print("  - Activity ID: \(activity.id)")

            // Immediately fetch fresh data in background to update with detailed info
            // This runs async so it doesn't block the button from updating
            Task { [weak self] in
                await self?.fetchAndUpdateTrain()
            }

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

        // Stop periodic updates first
        stopPeriodicUpdates()

        // Finalize trip recording (only matters if train departed)
        TripRecordingService.shared.finalizeTrip()

        // Cancel push token subscription and wait for completion
        if let task = pushTokenTask {
            task.cancel()
            // Give the task a moment to complete
            try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds
        }
        pushTokenTask = nil

        // Unregister push token if we have one
        if let pushToken = currentPushToken {
            let tokenString = pushToken.map { String(format: "%02x", $0) }.joined()
            do {
                try await APIService.shared.unregisterLiveActivityToken(pushToken: tokenString)
                print("✅ Unregistered push token from server")
            } catch {
                print("⚠️ Failed to unregister push token: \(error)")
                // Continue with cleanup anyway
            }
        }

        // End the activity with final content state
        let finalState = activity.content.state
        await activity.end(ActivityContent(state: finalState, staleDate: nil), dismissalPolicy: .immediate)

        // Clear all references with weak self for extra safety
        await MainActor.run { [weak self] in
            self?.currentActivity = nil
            self?.isActivityActive = false
            self?.currentPushToken = nil
            self?.journeyStationCodes = []
            self?.journeyDataSource = ""
            self?.hasDepartedOrigin = false
        }

        // Clear journey feedback state
        await JourneyFeedbackService.shared.onActivityEnded()

        print("🛑 Live Activity ended and cleaned up")
    }
    
    // MARK: - Updates
    
    private func startPeriodicUpdates() {
        stopPeriodicUpdates()

        // Use weak self in timer closure to avoid retain cycle
        updateTimer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { [weak self] _ in
            Task { [weak self] in
                await self?.fetchAndUpdateTrain()
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
            // Fetch train details
            let train = try await APIService.shared.fetchTrainDetails(
                id: activity.attributes.trainId,
                fromStationCode: activity.attributes.originStationCode
            )

            // Cache the fresh train data for instant loading in TrainDetailsView
            // Use trainId (which is actually the train number) with today's date
            await MainActor.run {
                cacheService.cacheTrain(train, trainNumber: activity.attributes.trainId, date: Date())
            }

            // Check for departure event (fires exactly once when train departs origin)
            let justDeparted = !hasDepartedOrigin &&
                train.hasTrainDepartedFromStation(activity.attributes.originStationCode)

            if justDeparted {
                hasDepartedOrigin = true
                print("🚀 Train departed from origin - triggering journey events")

                // Record trip immediately on departure (Pro feature)
                await TripRecordingService.shared.recordDeparture(
                    train: train,
                    originCode: activity.attributes.originStationCode,
                    destinationCode: activity.attributes.destinationStationCode,
                    originName: activity.attributes.origin,
                    destinationName: activity.attributes.destination
                )

                // Trigger feedback eligibility on departure
                await JourneyFeedbackService.shared.onDeparture(
                    trainId: activity.attributes.trainId,
                    originCode: activity.attributes.originStationCode,
                    destinationCode: activity.attributes.destinationStationCode
                )
            }

            // Update trip data on every poll after departure (for arrival times, delays)
            if hasDepartedOrigin {
                TripRecordingService.shared.updateTripProgress(train: train)
            }

            // Calculate context-aware progress for user's journey
            let context = JourneyContext(from: activity.attributes.originStationCode, toCode: activity.attributes.destinationStationCode, toName: activity.attributes.destination)
            let progress = train.calculateJourneyProgress(for: context)
            
            print("🔄 Live Activity Update Source: Client calculation (30s timer)")
            print("  - Client calculated progress: \(progress)")

            // Get estimated times (delay-adjusted) and departure status
            let estimatedDepartureTime = train.getEstimatedDepartureTime(fromStationCode: activity.attributes.originStationCode)
            let estimatedArrivalTime = train.getEstimatedArrivalTime(toStationCode: activity.attributes.destinationStationCode)
            let hasTrainDeparted = self.hasTrainDeparted(train, fromStation: activity.attributes.originStationCode)
            
            // Get current and next stop names using new fields
            let currentStop = train.stops?.last(where: { $0.hasDepartedStation })?.stationName ?? activity.attributes.origin
            let nextStop = getNextStopName(train, originCode: activity.attributes.originStationCode, destinationCode: activity.attributes.destinationStationCode, hasTrainDeparted: hasTrainDeparted)
            let nextStopCode = getNextStopCode(train, originCode: activity.attributes.originStationCode, destinationCode: activity.attributes.destinationStationCode, hasTrainDeparted: hasTrainDeparted)
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
                scheduledDepartureTime: estimatedDepartureTime?.toISO8601String(),
                scheduledArrivalTime: estimatedArrivalTime?.toISO8601String(),
                nextStopArrivalTime: nextStopArrivalTime?.toISO8601String(),
                nextStopCode: nextStopCode,
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
            print("  - Estimated Departure: \(estimatedDepartureTime?.description ?? "none")")
            print("  - Estimated Arrival: \(estimatedArrivalTime?.description ?? "none")")
            
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

        pushTokenTask = Task { [weak self] in
            guard let self = self else { return }

            print("🔄 Starting push token subscription for Live Activity...")

            for await pushToken in activity.pushTokenUpdates {
                // Check for cancellation
                if Task.isCancelled {
                    print("⚠️ Push token subscription cancelled")
                    break
                }

                #if DEBUG
                print("📡 Received Live Activity push token: \(pushToken.prefix(20))...")
                #endif

                // Store the token for later use (e.g., unregistration)
                await MainActor.run { [weak self] in
                    self?.currentPushToken = pushToken
                }

                // Register with backend
                await self.registerPushToken(pushToken, for: train, from: originCode, to: destinationCode)

                // We only need the first token, so break
                break
            }

            print("✅ Push token subscription task completed")
        }
    }
    
    // MARK: - Push Token Registration
    
    private func registerPushToken(_ token: Data, for train: TrainV2, from originCode: String, to destinationCode: String) async {
        let tokenString = token.map { String(format: "%02x", $0) }.joined()
        #if DEBUG
        print("🔧 Converting push token to string: \(tokenString.prefix(20))...")
        #endif

        // Remove nested Task - we're already in async context
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
            // Ensure timer is scheduled on main thread
            DispatchQueue.main.async { [weak self] in
                self?.startPeriodicUpdates()
            }
            
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
        let contentState = train.toLiveActivityContentState(from: activity.attributes.originStationCode, toCode: activity.attributes.destinationStationCode, toName: activity.attributes.destination)
        
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
        if let scheduledArrival = train.getScheduledArrivalTime(toStationCode: activity.attributes.destinationStationCode) {
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
    
    /// Get the next stop in user's journey segment
    private func getNextStop(_ train: TrainV2, originCode: String, destinationCode: String, hasTrainDeparted: Bool) -> Stop? {
        guard let stops = train.stops else { return nil }

        // Find origin and destination stops by station CODE (reliable)
        let originIndex = stops.firstIndex { Stations.areEquivalentStations($0.stationCode, originCode) }
        let destinationIndex = stops.firstIndex { Stations.areEquivalentStations($0.stationCode, destinationCode) }

        guard let fromIndex = originIndex, let toIndex = destinationIndex, fromIndex < toIndex else {
            return nil
        }

        // Get the journey segment stops
        let journeyStops = Array(stops[fromIndex...toIndex])

        // If train hasn't departed from origin, next stop is origin station
        if !hasTrainDeparted {
            return journeyStops.first
        }

        // If train has departed, find next non-departed stop in journey
        return journeyStops.first(where: { !$0.hasDepartedStation })
    }

    /// Get the next stop name for user's journey segment
    private func getNextStopName(_ train: TrainV2, originCode: String, destinationCode: String, hasTrainDeparted: Bool) -> String? {
        return getNextStop(train, originCode: originCode, destinationCode: destinationCode, hasTrainDeparted: hasTrainDeparted)?.stationName
    }

    /// Get the next stop code for user's journey segment
    private func getNextStopCode(_ train: TrainV2, originCode: String, destinationCode: String, hasTrainDeparted: Bool) -> String? {
        return getNextStop(train, originCode: originCode, destinationCode: destinationCode, hasTrainDeparted: hasTrainDeparted)?.stationCode
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