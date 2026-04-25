import Foundation
import ActivityKit
import SwiftUI

// MARK: - Live Activity Attributes
struct TrainActivityAttributes: ActivityAttributes {
    public struct ContentState: Codable, Hashable {
        // Simplified fields matching backend exactly
        let status: String
        let track: String?
        let currentStopName: String
        let nextStopName: String?
        let delayMinutes: Int
        let journeyProgress: Double
        let dataTimestamp: TimeInterval  // Unix timestamp for data freshness
        
        // Additional fields for enhanced time display - using String to handle APNS JSON decoding
        let scheduledDepartureTime: String?
        let scheduledArrivalTime: String?
        let nextStopArrivalTime: String?
        let nextStopCode: String?
        let hasTrainDeparted: Bool
        
        // Computed property for data freshness
        var freshnessText: String {
            let now = Date().timeIntervalSince1970
            let secondsAgo = Int(now - dataTimestamp)
            
            if secondsAgo < 60 {
                return "\(secondsAgo) sec ago"
            } else {
                let minutesAgo = secondsAgo / 60
                return "\(minutesAgo) min ago"
            }
        }
        
        // Check if data is stale (older than 3 minutes)
        var isDataStale: Bool {
            let now = Date().timeIntervalSince1970
            return (now - dataTimestamp) > 180  // 3 minutes
        }
        
        // MARK: - New Computed Properties for Time-Based Display
        
        /// Minutes until train departs from user's origin station
        var minutesUntilDeparture: Int? {
            guard !hasTrainDeparted,
                  let departureTimeString = scheduledDepartureTime,
                  let departureTime = Date.fromISO8601(departureTimeString) else { return nil }
            
            let now = Date()
            let interval = departureTime.timeIntervalSince(now)
            
            // If departure is in the past, return nil
            if interval < 0 { return nil }
            
            return Int(interval / 60)
        }
        
        /// Minutes until train arrives at user's destination station
        var minutesUntilArrival: Int? {
            guard let arrivalTimeString = scheduledArrivalTime,
                  let arrivalTime = Date.fromISO8601(arrivalTimeString) else { return nil }
            
            let now = Date()
            let interval = arrivalTime.timeIntervalSince(now)
            
            // Can be negative if arrival is overdue
            return Int(interval / 60)
        }
        
        /// Whether to show boarding state: track assigned, not departed, and within 15 minutes of departure
        var isBoarding: Bool {
            guard trackDisplay != nil, !hasTrainDeparted else { return false }
            guard let minutes = minutesUntilDeparture else { return true }
            return minutes <= 15
        }

        /// Display text for compact leading area
        var compactLeadingText: String {
            if hasTrainDeparted {
                return "Arriving"
            } else if isBoarding {
                return "Boarding"
            } else {
                return "Departing"
            }
        }
        
        /// Display text for compact trailing area
        var compactTrailingText: String {
            if hasTrainDeparted {
                if let minutes = minutesUntilArrival {
                    if minutes > 0 {
                        return "~\(minutes) min"
                    } else if minutes == 0 {
                        return "now"
                    } else {
                        return "late"
                    }
                }
            } else if isBoarding {
                return trackDisplay!
            } else {
                if let minutes = minutesUntilDeparture {
                    if minutes > 0 {
                        return "~\(minutes) min"
                    } else if minutes == 0 {
                        return "now"
                    } else {
                        return "late"
                    }
                }
            }
            return ""
        }
        
        /// Track display with "T" prefix
        var trackDisplay: String? {
            guard let track = track else { return nil }
            return "T\(track)"
        }
        
        /// Destination arrival time for expanded view
        var destinationArrivalTime: Date? {
            guard let arrivalTimeString = scheduledArrivalTime else { return nil }
            return Date.fromISO8601(arrivalTimeString)
        }
        
        /// Next stop arrival time as Date for display
        var nextStopArrivalTimeAsDate: Date? {
            guard let arrivalTimeString = nextStopArrivalTime else { return nil }
            return Date.fromISO8601(arrivalTimeString)
        }
        
        /// Context-aware time display: departure time for origin station, arrival time for others
        var contextAwareNextStopTime: Date? {
            // If train hasn't departed yet and we're at the origin station, show departure time
            if !hasTrainDeparted && isCurrentStopOriginStation {
                guard let departureTimeString = scheduledDepartureTime else { return nil }
                return Date.fromISO8601(departureTimeString)
            }
            
            // Otherwise show arrival time at next stop
            return nextStopArrivalTimeAsDate
        }
        
        /// Check if the current/next stop is the user's origin station
        private var isCurrentStopOriginStation: Bool {
            guard let originCode = originStationCode,
                  let stopCode = nextStopCode else { return false }
            return originCode == stopCode
        }
        
        /// Color based on delay minutes for timing text
        var delayColor: Color {
            switch delayMinutes {
            case 0...1:
                return Color(hex: "#0e5c8d")
            case 2...5:
                return .yellow
            case 6...14:
                return .orange
            default: // 15+
                return .red
            }
        }
        
        // Reference to parent attributes for access to static data
        var originStationCode: String?
        var destinationStationCode: String?
    }
    
    // Static attributes that don't change during activity
    let trainNumber: String
    let trainId: String
    let routeDescription: String
    let origin: String
    let destination: String
    let originStationCode: String
    let destinationStationCode: String
    let departureTime: Date
    let scheduledArrivalTime: Date?
    let theme: String // Theme name as string (blue, black, white)
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
        // Ensure valid track/platform
        guard !topTrack.isEmpty else {
            return "🤷 TrackRat is thinking..."
        }
        
        if confidence >= 0.8 {
            return "🐀 TrackRat predicts tracks \(topTrack)"
        } else if confidence >= 0.5 {
            return "🤔 TrackRat thinks it may be tracks \(topTrack)"
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
