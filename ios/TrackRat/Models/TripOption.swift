import Foundation

// MARK: - Trip Option Models
// Represents a complete trip that may involve one or more legs with transfers

struct TripLeg: Identifiable {
    var id: String {
        "\(trainId)-\(boarding.code)-\(boarding.scheduledTime?.timeIntervalSince1970.description ?? "0")"
    }
    let trainId: String
    let journeyDate: Date?
    let line: LineInfo
    let dataSource: String
    let destination: String
    let boarding: StationTiming
    let alighting: StationTiming
    let observationType: String?
    let isCancelled: Bool
    let trainPosition: TrainPosition?
}

struct TransferInfo {
    let fromStation: SimpleStation
    let toStation: SimpleStation
    let walkMinutes: Int
    let sameStation: Bool

    var walkDescription: String {
        if sameStation {
            return "Same station"
        } else if walkMinutes <= 1 {
            return "Short walk"
        } else {
            return "\(walkMinutes) min walk"
        }
    }
}

struct SimpleStation {
    let code: String
    let name: String
}

struct TripOption: Identifiable {
    var id: String {
        legs.map(\.id).joined(separator: "-")
    }
    let legs: [TripLeg]
    let transfers: [TransferInfo]
    let departureTime: Date
    let arrivalTime: Date
    let totalDurationMinutes: Int
    let isDirect: Bool

    /// Convert a direct trip's single leg to TrainV2 for existing UI components
    func asTrainV2() -> TrainV2? {
        guard isDirect, let leg = legs.first else { return nil }
        return TrainV2(
            trainId: leg.trainId,
            journeyDate: leg.journeyDate,
            line: leg.line,
            destination: leg.destination,
            departure: leg.boarding,
            arrival: leg.alighting,
            trainPosition: leg.trainPosition,
            dataFreshness: nil,
            observationType: leg.observationType,
            isCancelled: leg.isCancelled,
            cancellationReason: nil,
            isCompleted: false,
            dataSource: leg.dataSource
        )
    }

    /// Display label for the trip duration
    var durationDisplay: String {
        if totalDurationMinutes < 60 {
            return "\(totalDurationMinutes) min"
        }
        let hours = totalDurationMinutes / 60
        let mins = totalDurationMinutes % 60
        if mins == 0 {
            return "\(hours)h"
        }
        return "\(hours)h \(mins)m"
    }
}
