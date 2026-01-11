import Foundation

/// Service responsible for recording trips at journey milestones
/// Trips are recorded at: halfway point, second-to-last stop, and journey end
/// This ensures data capture even if user exits the app early
final class TripRecordingService {
    static let shared = TripRecordingService()

    // MARK: - State (per-activity session)

    private var activeTripId: UUID?
    private var triggeredMilestones: Set<CompletedTrip.RecordingMilestone> = []

    private init() {}

    // MARK: - Public API

    /// Called on every Live Activity update with fresh train data
    /// Checks if we've reached a recording milestone and records/updates accordingly
    func processTrainUpdate(
        train: TrainV2,
        originCode: String,
        destinationCode: String,
        originName: String,
        destinationName: String
    ) {
        guard let position = calculateJourneyPosition(
            train: train,
            originCode: originCode,
            destinationCode: destinationCode
        ) else {
            print("TripRecording: Could not calculate journey position")
            return
        }

        let (departedStopCount, totalStops) = position

        // Halfway milestone: triggered when we've departed >= half the stops before destination
        // For N stops, there are N-1 segments. Halfway = (N-1)/2 segments completed
        // Use max(1, ...) to ensure at least one stop must be departed (fixes 2-stop trips recording too early)
        let halfwayThreshold = max(1, (totalStops - 1) / 2)
        if departedStopCount >= halfwayThreshold && !triggeredMilestones.contains(.halfway) {
            print("TripRecording: Reached halfway milestone (departed \(departedStopCount) of \(totalStops) stops)")
            recordMilestone(
                .halfway,
                train: train,
                originCode: originCode,
                destinationCode: destinationCode,
                originName: originName,
                destinationName: destinationName
            )
        }

        // Second-to-last milestone: triggered when we've departed the penultimate stop
        // This means departedStopCount >= totalStops - 2 (0-indexed, so -2 is second to last)
        let secondToLastThreshold = max(0, totalStops - 2)
        if departedStopCount >= secondToLastThreshold && !triggeredMilestones.contains(.secondToLast) {
            // Don't trigger if it's the same as halfway (short trips)
            if triggeredMilestones.contains(.halfway) {
                print("TripRecording: Reached second-to-last milestone (departed \(departedStopCount) stops)")
                recordMilestone(
                    .secondToLast,
                    train: train,
                    originCode: originCode,
                    destinationCode: destinationCode,
                    originName: originName,
                    destinationName: destinationName
                )
            }
        }
    }

    /// Called when Live Activity ends (user-initiated or auto)
    /// Finalizes the trip record if one was created
    func finalizeTrip(
        train: TrainV2?,
        originCode: String,
        destinationCode: String,
        originName: String,
        destinationName: String
    ) {
        // Only finalize if we have an active trip (means we hit halfway at minimum)
        guard activeTripId != nil else {
            print("TripRecording: No active trip to finalize (user exited before halfway)")
            reset()
            return
        }

        if let train = train {
            print("TripRecording: Finalizing trip with latest train data")
            recordMilestone(
                .completed,
                train: train,
                originCode: originCode,
                destinationCode: destinationCode,
                originName: originName,
                destinationName: destinationName
            )
        } else {
            // No train data available, just mark as completed with existing data
            print("TripRecording: Finalizing trip without new train data")
            if let tripId = activeTripId {
                StorageService.shared.updateCompletedTrip(id: tripId) { trip in
                    trip.recordingMilestone = .completed
                    trip.lastUpdated = Date()
                }
            }
        }

        reset()
    }

    /// Reset state - called when activity ends or is cancelled
    func reset() {
        print("TripRecording: Resetting state")
        activeTripId = nil
        triggeredMilestones = []
    }

    // MARK: - Private Methods

    /// Calculate how many stops the user has departed within their journey segment
    /// Returns (departedStopCount, totalStopsInJourney)
    private func calculateJourneyPosition(
        train: TrainV2,
        originCode: String,
        destinationCode: String
    ) -> (departedStopCount: Int, totalStops: Int)? {
        guard let stops = train.stops else {
            print("TripRecording: No stops data available")
            return nil
        }

        // Debug: Print all station codes to diagnose matching issues
        let allStationCodes = stops.map { $0.stationCode }
        print("TripRecording: Looking for origin '\(originCode)' and dest '\(destinationCode)' in stops: \(allStationCodes)")

        // Find origin and destination indices
        guard let originIdx = stops.firstIndex(where: { $0.stationCode.uppercased() == originCode.uppercased() }),
              let destIdx = stops.firstIndex(where: { $0.stationCode.uppercased() == destinationCode.uppercased() }),
              originIdx < destIdx else {
            print("TripRecording: Could not find origin/destination in stops")
            print("  - Origin '\(originCode)' found: \(stops.contains { $0.stationCode.uppercased() == originCode.uppercased() })")
            print("  - Dest '\(destinationCode)' found: \(stops.contains { $0.stationCode.uppercased() == destinationCode.uppercased() })")
            return nil
        }

        // Get journey segment (origin to destination inclusive)
        let journeyStops = Array(stops[originIdx...destIdx])
        let totalStops = journeyStops.count

        // Count how many stops have been departed (origin counts when departed)
        let departedCount = journeyStops.filter { $0.hasDepartedStation }.count

        // Debug: Print departure status for each stop in journey
        print("TripRecording: Journey segment (\(totalStops) stops):")
        for (idx, stop) in journeyStops.enumerated() {
            print("  [\(idx)] \(stop.stationCode): hasDepartedStation=\(stop.hasDepartedStation)")
        }
        print("TripRecording: departedCount=\(departedCount), halfwayThreshold=\((totalStops - 1) / 2)")

        return (departedCount, totalStops)
    }

    /// Record or update trip at a milestone
    private func recordMilestone(
        _ milestone: CompletedTrip.RecordingMilestone,
        train: TrainV2,
        originCode: String,
        destinationCode: String,
        originName: String,
        destinationName: String
    ) {
        triggeredMilestones.insert(milestone)

        guard let stops = train.stops else { return }

        // Find origin and destination stops for timing data
        let originStop = stops.first { $0.stationCode.uppercased() == originCode.uppercased() }
        let destStop = stops.first { $0.stationCode.uppercased() == destinationCode.uppercased() }

        // Extract timing data - use best available for each field
        let scheduledDeparture = originStop?.scheduledDeparture ?? Date()
        let scheduledArrival = destStop?.scheduledArrival ?? Date()

        // Actual departure: use actual if available
        let actualDeparture = originStop?.actualDeparture

        // Best arrival estimate: actual > updated > scheduled
        let bestArrivalEstimate = destStop?.actualArrival ?? destStop?.updatedArrival ?? destStop?.scheduledArrival

        // Calculate delays
        let departureDelay = calculateDepartureDelay(originStop: originStop)
        let arrivalDelay = calculateArrivalDelay(destStop: destStop, trainDelay: train.delayMinutes)

        if activeTripId == nil {
            // Create new trip record
            let trip = CompletedTrip(
                id: UUID(),
                trainId: train.trainId,
                trainNumber: train.trainId,
                lineName: train.line.name,
                originCode: originCode,
                originName: originName,
                destinationCode: destinationCode,
                destinationName: destinationName,
                tripDate: Calendar.current.startOfDay(for: Date()),
                scheduledDeparture: scheduledDeparture,
                scheduledArrival: scheduledArrival,
                actualDeparture: actualDeparture,
                actualArrival: bestArrivalEstimate,
                departureDelayMinutes: departureDelay,
                arrivalDelayMinutes: arrivalDelay,
                track: originStop?.track,
                recordingMilestone: milestone,
                lastUpdated: Date()
            )

            activeTripId = trip.id
            StorageService.shared.saveCompletedTrip(trip)

            print("TripRecording: Created trip \(trip.id) at \(milestone.rawValue)")
            print("  - Route: \(originName) → \(destinationName)")
            print("  - Scheduled: \(scheduledDeparture) → \(scheduledArrival)")
            print("  - Delay: \(arrivalDelay) minutes")

        } else {
            // Update existing trip
            StorageService.shared.updateCompletedTrip(id: activeTripId!) { trip in
                // Update with latest data
                trip.actualDeparture = actualDeparture ?? trip.actualDeparture
                trip.actualArrival = bestArrivalEstimate ?? trip.actualArrival
                trip.departureDelayMinutes = departureDelay
                trip.arrivalDelayMinutes = arrivalDelay
                trip.track = originStop?.track ?? trip.track
                trip.recordingMilestone = milestone
                trip.lastUpdated = Date()
            }

            print("TripRecording: Updated trip \(activeTripId!) to \(milestone.rawValue)")
            print("  - Arrival delay: \(arrivalDelay) minutes")
        }
    }

    /// Calculate departure delay from origin stop
    private func calculateDepartureDelay(originStop: StopV2?) -> Int {
        guard let stop = originStop,
              let scheduled = stop.scheduledDeparture else {
            return 0
        }

        // Use actual if available, otherwise updated
        let compareTime = stop.actualDeparture ?? stop.updatedDeparture ?? scheduled
        let delaySeconds = compareTime.timeIntervalSince(scheduled)
        return max(0, Int(delaySeconds / 60))
    }

    /// Calculate arrival delay at destination
    private func calculateArrivalDelay(destStop: StopV2?, trainDelay: Int) -> Int {
        guard let stop = destStop,
              let scheduled = stop.scheduledArrival else {
            // Fallback to train's general delay
            return trainDelay
        }

        // Use best available: actual > updated > scheduled
        let compareTime = stop.actualArrival ?? stop.updatedArrival ?? scheduled
        let delaySeconds = compareTime.timeIntervalSince(scheduled)
        return max(0, Int(delaySeconds / 60))
    }
}
