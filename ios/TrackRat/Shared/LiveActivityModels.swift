import Foundation
import ActivityKit

// MARK: - Live Activity Attributes
struct TrainActivityAttributes: ActivityAttributes {
    public struct ContentState: Codable, Hashable {
        // Core train info (StatusV2 only)
        let statusV2: String  // StatusV2.current value
        let statusLocation: String?  // StatusV2.location value
        let track: String?
        let delayMinutes: Int?
        
        // Journey progress
        let currentLocation: CurrentLocation
        let nextStop: NextStopInfo?
        let journeyProgress: Double
        let destinationETA: Date?
        
        // TrackRat predictions
        let trackRatPrediction: TrackRatPredictionInfo?
        
        // Metadata
        let lastUpdated: Date
        let hasStatusChanged: Bool
        
        // Enhanced alert metadata for Dynamic Island prominence
        let alertMetadata: AlertMetadata?
        let dynamicIslandPriority: String?
        let requiresHapticFeedback: Bool?
        let pushTimestamp: TimeInterval?
    }
    
    // Static attributes that don't change during activity
    let trainNumber: String
    let trainId: String
    let routeDescription: String
    let origin: String
    let destination: String
    let originStationCode: String
    let destinationStationCode: String
}

// MARK: - Supporting Data Models

// Helper function to truncate station names
private func truncateStationName(_ name: String, maxLength: Int = 18) -> String {
    if name.count > maxLength {
        return name.prefix(maxLength - 1) + "…"
    }
    return name
}

enum CurrentLocation: Codable, Hashable {
    case notDeparted(departureTime: Date)
    case boarding(station: String)
    case departed(from: String, minutesAgo: Int)
    case approaching(station: String, minutesAway: Int)
    case enRoute(between: String, and: String)
    case atStation(String)
    case arrived
    
    var displayText: String {
        switch self {
        case .notDeparted:
            return "Preparing to depart"
        case .boarding(let station):
            return "Boarding at \(truncateStationName(station))"
        case .departed(let from, let minutes):
            if minutes == 0 {
                return "Just departed \(truncateStationName(from))"
            } else {
                return "Departed \(truncateStationName(from)) \(minutes) min ago"
            }
        case .approaching(let station, let minutes):
            if minutes == 0 {
                return "Arriving at \(truncateStationName(station))"
            } else {
                return "Approaching \(truncateStationName(station)) (~\(minutes) min)"
            }
        case .enRoute(let from, let to):
            return "Between \(truncateStationName(from)) and \(truncateStationName(to))"
        case .atStation(let station):
            return "At \(truncateStationName(station))"
        case .arrived:
            return "Arrived"
        }
    }
}

struct NextStopInfo: Codable, Hashable {
    let stationName: String
    let estimatedArrival: Date
    let scheduledArrival: Date?
    let isDelayed: Bool
    let delayMinutes: Int
    let isDestination: Bool
    let minutesAway: Int
    
    // Convenience property for accessing station name
    var name: String {
        return stationName
    }
    
    var displayText: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        
        let truncatedStationName = truncateStationName(stationName)
        if isDelayed {
            return "\(truncatedStationName) ~\(formatter.string(from: estimatedArrival))"
        } else {
            return "\(truncatedStationName) \(formatter.string(from: estimatedArrival))"
        }
    }
}

struct TrackRatPredictionInfo: Codable, Hashable {
    let topTrack: String
    let confidence: Double
    let alternativeTracks: [String]
    
    var displayText: String {
        // Ensure valid track number
        guard !topTrack.isEmpty else {
            return "🤷 TrackRat is thinking..."
        }
        
        if confidence >= 0.8 {
            return "🐀 TrackRat predicts track \(topTrack)"
        } else if confidence >= 0.5 {
            return "🤔 TrackRat thinks it may be track \(topTrack)"
        } else {
            let validTracks = ([topTrack] + alternativeTracks.prefix(2)).filter { !$0.isEmpty }
            let tracksText = validTracks.isEmpty ? "unknown" : validTracks.joined(separator: ", ")
            return "🤷 TrackRat guesses tracks \(tracksText)"
        }
    }
}

// MARK: - Alert Metadata for Enhanced Dynamic Island Handling

struct AlertMetadata: Codable, Hashable {
    let alertType: String
    let trainId: String
    let track: String?
    let dynamicIslandPriority: String
    let requiresHapticFeedback: Bool
    let timestamp: TimeInterval
}

