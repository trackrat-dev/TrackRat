import Foundation

// MARK: - Completed Trip Model
/// Represents a trip that was tracked via Live Activity.
/// Records are created when the train departs from the user's origin station.
struct CompletedTrip: Codable, Identifiable, Equatable {
    let id: UUID
    let trainId: String
    let trainNumber: String
    let lineName: String

    // Route information (full journey from user's origin to destination)
    let originCode: String
    let originName: String
    let destinationCode: String
    let destinationName: String

    // Timing - captures full journey times
    let tripDate: Date  // Day of travel (normalized to midnight for grouping)
    let scheduledDeparture: Date
    let scheduledArrival: Date

    // These get updated as actuals become available
    var actualDeparture: Date?
    var actualArrival: Date?  // Best available: actual > updated > scheduled
    var departureDelayMinutes: Int
    var arrivalDelayMinutes: Int
    var track: String?

    // Recording metadata
    var lastUpdated: Date

    // MARK: - Computed Properties

    var isOnTime: Bool {
        arrivalDelayMinutes <= 5
    }

    var formattedDelay: String {
        if arrivalDelayMinutes <= 0 {
            return "On time"
        } else if arrivalDelayMinutes < 60 {
            return "+\(arrivalDelayMinutes)m"
        } else {
            let hours = arrivalDelayMinutes / 60
            let minutes = arrivalDelayMinutes % 60
            return minutes > 0 ? "+\(hours)h \(minutes)m" : "+\(hours)h"
        }
    }

    var routeDescription: String {
        "\(originName) → \(destinationName)"
    }
}

// MARK: - Trip Statistics
/// Computed statistics from trip history - not persisted, calculated on demand
struct TripStats {
    let totalTrips: Int
    let totalDelayMinutes: Int
    let totalOnTimeTrips: Int
    let averageDelayMinutes: Double
    let mostFrequentRoute: (originName: String, destinationName: String, count: Int)?
    let firstTripDate: Date?
    let weeklyStreak: Int  // Consecutive weeks with at least one trip

    // MARK: - Computed Properties

    var onTimePercentage: Int {
        guard totalTrips > 0 else { return 0 }
        return Int((Double(totalOnTimeTrips) / Double(totalTrips)) * 100)
    }

    var formattedTotalDelay: String {
        if totalDelayMinutes < 60 {
            return "\(totalDelayMinutes)m"
        } else {
            let hours = totalDelayMinutes / 60
            let minutes = totalDelayMinutes % 60
            return minutes > 0 ? "\(hours)h \(minutes)m" : "\(hours)h"
        }
    }

    static let empty = TripStats(
        totalTrips: 0,
        totalDelayMinutes: 0,
        totalOnTimeTrips: 0,
        averageDelayMinutes: 0,
        mostFrequentRoute: nil,
        firstTripDate: nil,
        weeklyStreak: 0
    )
}
