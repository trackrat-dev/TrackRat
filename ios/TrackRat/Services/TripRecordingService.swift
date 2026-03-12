import Foundation

/// Service responsible for recording trips when user's train departs from origin.
/// Trips are recorded immediately on departure and updated with latest arrival data.
/// Note: Trip recording is a Pro feature - only Pro users can record and view trip statistics.
@MainActor
final class TripRecordingService {
    static let shared = TripRecordingService()

    // MARK: - State

    private var activeTripId: UUID?
    private var destinationCode: String?

    private init() {}

    // MARK: - Public API

    /// Called once when train departs from user's origin station - creates the trip record
    @MainActor
    func recordDeparture(
        train: TrainV2,
        originCode: String,
        destinationCode: String,
        originName: String,
        destinationName: String
    ) {
        guard let stops = train.stops else {
            print("TripRecording: No stops data - cannot record trip")
            return
        }

        // Find origin and destination stops
        let originStop = stops.first { $0.stationCode.caseInsensitiveCompare(originCode) == .orderedSame }
        let destStop = stops.first { $0.stationCode.caseInsensitiveCompare(destinationCode) == .orderedSame }

        guard originStop != nil else {
            print("TripRecording: Origin stop not found in train data")
            return
        }

        // Store destination code for updates
        self.destinationCode = destinationCode

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
            scheduledDeparture: originStop?.scheduledDeparture ?? Date(),
            scheduledArrival: destStop?.scheduledArrival ?? Date(),
            actualDeparture: originStop?.actualDeparture,
            actualArrival: destStop?.actualArrival ?? destStop?.updatedArrival,
            departureDelayMinutes: calculateDelay(
                scheduled: originStop?.scheduledDeparture,
                actual: originStop?.actualDeparture
            ),
            arrivalDelayMinutes: calculateDelay(
                scheduled: destStop?.scheduledArrival,
                actual: destStop?.actualArrival ?? destStop?.updatedArrival
            ),
            track: originStop?.track,
            lastUpdated: Date()
        )

        activeTripId = trip.id
        StorageService.shared.saveCompletedTrip(trip)

        print("TripRecording: ✅ Trip recorded on departure")
        print("  - Route: \(originName) → \(destinationName)")
        print("  - Train: \(train.trainId)")
        print("  - Departure delay: \(trip.departureDelayMinutes) min")
    }

    /// Called on each update after departure to capture latest arrival data
    func updateTripProgress(train: TrainV2) {
        guard let id = activeTripId, let destCode = destinationCode else { return }

        StorageService.shared.updateCompletedTrip(id: id) { [weak self] trip in
            guard let self = self else { return }

            if let destStop = train.stops?.first(where: { $0.stationCode.caseInsensitiveCompare(destCode) == .orderedSame }) {
                let newActualArrival = destStop.actualArrival ?? destStop.updatedArrival
                trip.actualArrival = newActualArrival ?? trip.actualArrival
                trip.arrivalDelayMinutes = self.calculateDelay(
                    scheduled: trip.scheduledArrival,
                    actual: trip.actualArrival
                )
            }
            trip.lastUpdated = Date()
        }
    }

    /// Called when Live Activity ends - clears state
    func finalizeTrip() {
        if activeTripId != nil {
            print("TripRecording: Trip finalized")
        } else {
            print("TripRecording: No trip to finalize (train never departed)")
        }
        reset()
    }

    /// Reset state - called when activity ends or is cancelled
    func reset() {
        activeTripId = nil
        destinationCode = nil
    }

    // MARK: - Private Methods

    private func calculateDelay(scheduled: Date?, actual: Date?) -> Int {
        guard let scheduled = scheduled, let actual = actual else { return 0 }
        return max(0, Int(actual.timeIntervalSince(scheduled) / 60))
    }
}
