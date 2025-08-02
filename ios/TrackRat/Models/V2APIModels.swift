import Foundation
import SwiftUI

// MARK: - V2 API Response Models
// These models match the backend_v2 API response structure

// MARK: - Common Models

struct V2LineInfo: Codable {
    let code: String
    let name: String
    let color: String
}

struct V2StationInfo: Codable {
    let code: String
    let name: String
    let scheduledTime: Date?
    let updatedTime: Date?
    let actualTime: Date?
    let track: String?
    
    enum CodingKeys: String, CodingKey {
        case code, name, track
        case scheduledTime = "scheduled_time"
        case updatedTime = "updated_time"
        case actualTime = "actual_time"
    }
}

struct V2DataFreshness: Codable {
    let lastUpdated: Date
    let ageSeconds: Int
    let updateCount: Int?
    let collectionMethod: String?
    
    enum CodingKeys: String, CodingKey {
        case lastUpdated = "last_updated"
        case ageSeconds = "age_seconds"
        case updateCount = "update_count"
        case collectionMethod = "collection_method"
    }
}

struct V2JourneyProgress: Codable {
    let completedStops: Int
    let totalStops: Int
    let percentage: Int
    let currentLocation: String
    let nextStop: String?
    
    enum CodingKeys: String, CodingKey {
        case completedStops = "completed_stops"
        case totalStops = "total_stops"
        case percentage
        case currentLocation = "current_location"
        case nextStop = "next_stop"
    }
}

struct V2JourneyInfo: Codable {
    let origin: String
    let originName: String
    let durationMinutes: Int
    let stopsBetween: Int
    let progress: V2JourneyProgress
    
    enum CodingKeys: String, CodingKey {
        case origin
        case originName = "origin_name"
        case durationMinutes = "duration_minutes"
        case stopsBetween = "stops_between"
        case progress
    }
}

// MARK: - Departures Endpoint Models

struct V2TrainPosition: Codable {
    let lastDepartedStationCode: String?
    let atStationCode: String?
    let nextStationCode: String?
    
    enum CodingKeys: String, CodingKey {
        case lastDepartedStationCode = "last_departed_station_code"
        case atStationCode = "at_station_code"
        case nextStationCode = "next_station_code"
    }
}

struct V2TrainDeparture: Codable {
    let trainId: String
    let line: V2LineInfo
    let destination: String
    let departure: V2StationInfo
    let arrival: V2StationInfo?
    let trainPosition: V2TrainPosition
    let dataFreshness: V2DataFreshness
    let dataSource: String
    let isCancelled: Bool
    
    enum CodingKeys: String, CodingKey {
        case trainId = "train_id"
        case line, destination, departure, arrival
        case trainPosition = "train_position"
        case dataFreshness = "data_freshness"
        case dataSource = "data_source"
        case isCancelled = "is_cancelled"
    }
}

struct V2DeparturesResponse: Codable {
    let departures: [V2TrainDeparture]
    let metadata: V2DeparturesMetadata?
}

struct V2DeparturesMetadata: Codable {
    // Since backend returns dict[str, Any], we'll decode specific fields we need
    let fromStation: V2StationMetadata?
    let toStation: V2StationMetadata?
    let count: Int?
    let generatedAt: Date?
    
    enum CodingKeys: String, CodingKey {
        case fromStation = "from_station"
        case toStation = "to_station"
        case count
        case generatedAt = "generated_at"
    }
}

struct V2StationMetadata: Codable {
    let code: String
    let name: String
}

// MARK: - Train Details Endpoint Models

struct V2RouteInfo: Codable {
    let origin: String
    let destination: String
    let originCode: String
    let destinationCode: String
    
    enum CodingKeys: String, CodingKey {
        case origin, destination
        case originCode = "origin_code"
        case destinationCode = "destination_code"
    }
}

struct V2CurrentStatus: Codable {
    let status: String
    let location: String
    let delayMinutes: Int
    let isCancelled: Bool
    let isCompleted: Bool
    let lastUpdate: Date
    
    enum CodingKeys: String, CodingKey {
        case status, location
        case delayMinutes = "delay_minutes"
        case isCancelled = "is_cancelled"
        case isCompleted = "is_completed"
        case lastUpdate = "last_update"
    }
}

struct V2RawStopStatus: Codable {
    let amtrakStatus: String?
    let njtDepartedFlag: String?
    
    enum CodingKeys: String, CodingKey {
        case amtrakStatus = "amtrak_status"
        case njtDepartedFlag = "njt_departed_flag"
    }
}

struct V2StopDetails: Codable {
    let station: V2SimpleStationInfo
    let stopSequence: Int
    let scheduledArrival: Date?
    let scheduledDeparture: Date?
    let updatedArrival: Date?
    let updatedDeparture: Date?
    let actualArrival: Date?
    let actualDeparture: Date?
    let track: String?
    let trackAssignedAt: Date?
    let rawStatus: V2RawStopStatus
    let hasDepartedStation: Bool
    
    enum CodingKeys: String, CodingKey {
        case station, track
        case stopSequence = "stop_sequence"
        case scheduledArrival = "scheduled_arrival"
        case scheduledDeparture = "scheduled_departure"
        case updatedArrival = "updated_arrival"
        case updatedDeparture = "updated_departure"
        case actualArrival = "actual_arrival"
        case actualDeparture = "actual_departure"
        case trackAssignedAt = "track_assigned_at"
        case rawStatus = "raw_status"
        case hasDepartedStation = "has_departed_station"
    }
}

struct V2SimpleStationInfo: Codable {
    let code: String
    let name: String
}

struct V2TrainDetails: Codable {
    let trainId: String
    let journeyDate: Date
    let line: V2LineInfo
    let route: V2RouteInfo
    let trainPosition: V2TrainPosition
    let stops: [V2StopDetails]
    let dataFreshness: V2DataFreshness
    let dataSource: String
    let rawTrainState: String?
    let isCancelled: Bool
    let isCompleted: Bool
    
    enum CodingKeys: String, CodingKey {
        case trainId = "train_id"
        case journeyDate = "journey_date"
        case line, route
        case trainPosition = "train_position"
        case stops
        case dataFreshness = "data_freshness"
        case dataSource = "data_source"
        case rawTrainState = "raw_train_state"
        case isCancelled = "is_cancelled"
        case isCompleted = "is_completed"
    }
}

struct V2TrainDetailsResponse: Codable {
    let train: V2TrainDetails
}

// MARK: - History Endpoint Models

struct V2HistoricalJourney: Codable {
    let journeyDate: Date
    let scheduledDeparture: Date
    let actualDeparture: Date?
    let scheduledArrival: Date
    let actualArrival: Date?
    let delayMinutes: Int
    let wasCancelled: Bool
    let trackAssignments: [String: String?]
    
    enum CodingKeys: String, CodingKey {
        case journeyDate = "journey_date"
        case scheduledDeparture = "scheduled_departure"
        case actualDeparture = "actual_departure"
        case scheduledArrival = "scheduled_arrival"
        case actualArrival = "actual_arrival"
        case delayMinutes = "delay_minutes"
        case wasCancelled = "was_cancelled"
        case trackAssignments = "track_assignments"
    }
}

struct V2TrainHistoryResponse: Codable {
    let trainId: String
    let journeys: [V2HistoricalJourney]
    let statistics: V2HistoryStatistics?
    
    enum CodingKeys: String, CodingKey {
        case trainId = "train_id"
        case journeys, statistics
    }
}

struct V2HistoryStatistics: Codable {
    let totalJourneys: Int
    let onTimePercentage: Double
    let averageDelayMinutes: Double
    let cancellationRate: Double
    
    enum CodingKeys: String, CodingKey {
        case totalJourneys = "total_journeys"
        case onTimePercentage = "on_time_percentage"
        case averageDelayMinutes = "average_delay_minutes"
        case cancellationRate = "cancellation_rate"
    }
}

// MARK: - Occupied Tracks Endpoint Models

struct V2OccupiedTrack: Codable {
    let trackNumber: String
    let trainId: String
    let line: V2LineInfo
    let destination: String
    let scheduledDeparture: Date
    let updatedDeparture: Date?
    let actualDeparture: Date?
    let status: String
    let trackAssignedAt: Date?
    let platform: String?
    
    enum CodingKeys: String, CodingKey {
        case trackNumber = "track_number"
        case trainId = "train_id"
        case line, destination, status, platform
        case scheduledDeparture = "scheduled_departure"
        case updatedDeparture = "updated_departure"
        case actualDeparture = "actual_departure"
        case trackAssignedAt = "track_assigned_at"
    }
}

struct V2OccupiedTracksResponse: Codable {
    let stationCode: String
    let stationName: String
    let occupiedTracks: [String]
    let lastUpdated: Date
    let cacheExpiresAt: Date
    
    enum CodingKeys: String, CodingKey {
        case stationCode = "station_code"
        case stationName = "station_name"
        case occupiedTracks = "occupied_tracks"
        case lastUpdated = "last_updated"
        case cacheExpiresAt = "cache_expires_at"
    }
}

struct V2OccupiedTracksMetadata: Codable {
    let station: V2StationMetadata
    let generatedAt: Date
    let totalTracks: Int
    let occupiedCount: Int
    
    enum CodingKeys: String, CodingKey {
        case station
        case generatedAt = "generated_at"
        case totalTracks = "total_tracks"
        case occupiedCount = "occupied_count"
    }
}

// MARK: - Congestion Data Models

struct CongestionResponse: Codable {
    let segments: [CongestionSegment]
    let generatedAt: Date
    let timeWindowHours: Int
    let metadata: CongestionMetadata
    
    enum CodingKeys: String, CodingKey {
        case segments
        case generatedAt = "generated_at"
        case timeWindowHours = "time_window_hours"
        case metadata
    }
}

struct CongestionSegment: Codable, Identifiable {
    let fromStation: String
    let toStation: String
    let fromStationName: String
    let toStationName: String
    let dataSource: String
    let congestionFactor: Double
    let congestionLevel: String
    let averageDelayMinutes: Double
    let baselineMinutes: Double
    let currentAverageMinutes: Double
    let sampleCount: Int
    
    enum CodingKeys: String, CodingKey {
        case fromStation = "from_station"
        case toStation = "to_station"
        case fromStationName = "from_station_name"
        case toStationName = "to_station_name"
        case dataSource = "data_source"
        case congestionFactor = "congestion_factor"
        case congestionLevel = "congestion_level"
        case averageDelayMinutes = "average_delay_minutes"
        case baselineMinutes = "baseline_minutes"
        case currentAverageMinutes = "current_average_minutes"
        case sampleCount = "sample_count"
    }
    
    // Identifiable
    var id: String {
        "\(fromStation)-\(toStation)-\(dataSource)"
    }
    
    // Computed properties for display
    var displayCongestionLevel: String {
        switch congestionLevel {
        case "normal": return "Normal conditions"
        case "moderate": return "Moderate delays"
        case "heavy": return "Heavy delays"
        case "severe": return "Severe delays"
        default: return congestionLevel.capitalized
        }
    }
    
    var displayColor: Color {
        if congestionFactor < 1.05 {
            return .green
        } else if congestionFactor < 1.25 {
            return .yellow
        } else if congestionFactor < 2.0 {
            return .orange
        } else {
            return .red
        }
    }
}

struct StationCoordinates: Codable {
    let lat: Double
    let lon: Double
}

struct CongestionMetadata: Codable {
    let totalSegments: Int
    let congestionLevels: CongestionLevelCounts
    
    enum CodingKeys: String, CodingKey {
        case totalSegments = "total_segments"
        case congestionLevels = "congestion_levels"
    }
}

struct CongestionLevelCounts: Codable {
    let normal: Int
    let moderate: Int
    let heavy: Int
    let severe: Int
}

// MARK: - Segment Train Details Models

struct SegmentTrainDetail: Codable, Identifiable {
    let trainId: String
    let line: String
    let scheduledDeparture: Date
    let actualDeparture: Date
    let scheduledArrival: Date
    let actualArrival: Date
    let departureDelayMinutes: Int
    let arrivalDelayMinutes: Int
    let congestionFactor: Double
    let delayCategory: String
    let dataSource: String
    
    enum CodingKeys: String, CodingKey {
        case trainId = "train_id"
        case line
        case scheduledDeparture = "scheduled_departure"
        case actualDeparture = "actual_departure"
        case scheduledArrival = "scheduled_arrival"
        case actualArrival = "actual_arrival"
        case departureDelayMinutes = "departure_delay_minutes"
        case arrivalDelayMinutes = "arrival_delay_minutes"
        case congestionFactor = "congestion_factor"
        case delayCategory = "delay_category"
        case dataSource = "data_source"
    }
    
    // Identifiable
    var id: String {
        "\(trainId)-\(scheduledDeparture.timeIntervalSince1970)"
    }
    
    // Computed properties for display
    var transitTime: TimeInterval {
        actualArrival.timeIntervalSince(actualDeparture)
    }

    var transitTimeDisplay: String {
        let minutes = Int(transitTime / 60)
        return "\(minutes) min transit"
    }

    var delayCategoryDisplay: String {
        switch delayCategory {
        case "on_time": return "On Time"
        case "slight_delay": return "Slight Delay"
        case "delayed": return "Delayed"
        case "significantly_delayed": return "Significantly Delayed"
        case "no": return ""
        default: return delayCategory.capitalized
        }
    }
    
    var delayCategoryColor: Color {
        switch delayCategory {
        case "on_time": return .green
        case "slight_delay": return .yellow
        case "delayed": return .orange
        case "significantly_delayed": return .red
        default: return .gray
        }
    }
    
    var congestionFactorDisplay: String {
        let percentage = Int((congestionFactor - 1) * 100)
        if percentage > 0 {
            return "+\(percentage)% slower"
        } else {
            return "Normal time"
        }
    }
    
    var departureDelayDisplay: String {
        if departureDelayMinutes > 0 {
            return "+\(departureDelayMinutes)m late"
        } else if departureDelayMinutes < 0 {
            return "\(abs(departureDelayMinutes))m early"
        } else {
            return "On time"
        }
    }
    
    var arrivalDelayDisplay: String {
        if arrivalDelayMinutes > 0 {
            return "+\(arrivalDelayMinutes)m late"
        } else if arrivalDelayMinutes < 0 {
            return "\(abs(arrivalDelayMinutes))m early"
        } else {
            return "On time"
        }
    }
}

struct SegmentInfo: Codable {
    let fromStation: String
    let toStation: String
    let fromStationName: String
    let toStationName: String
    
    enum CodingKeys: String, CodingKey {
        case fromStation = "from_station"
        case toStation = "to_station"
        case fromStationName = "from_station_name"
        case toStationName = "to_station_name"
    }
}

struct SegmentSummary: Codable {
    let totalTrains: Int
    let returnedTrains: Int
    let averageDepartureDelay: Double
    let averageArrivalDelay: Double
    let averageCongestionFactor: Double
    let onTimePercentage: Double
    
    enum CodingKeys: String, CodingKey {
        case totalTrains = "total_trains"
        case returnedTrains = "returned_trains"
        case averageDepartureDelay = "average_departure_delay"
        case averageArrivalDelay = "average_arrival_delay"
        case averageCongestionFactor = "average_congestion_factor"
        case onTimePercentage = "on_time_percentage"
    }
}

struct SegmentTrainDetailsResponse: Codable {
    let segment: SegmentInfo
    let trains: [SegmentTrainDetail]
    let summary: SegmentSummary
    let timeWindow: TimeWindowInfo?
    
    enum CodingKeys: String, CodingKey {
        case segment
        case trains
        case summary
        case timeWindow = "time_window"
    }
}

struct TimeWindowInfo: Codable {
    let startTime: Date
    let endTime: Date
    let generatedAt: Date
    
    enum CodingKeys: String, CodingKey {
        case startTime = "start_time"
        case endTime = "end_time"
        case generatedAt = "generated_at"
    }
}


// MARK: - Extensions for Display

extension CongestionSegment {
    var fromStationDisplayName: String {
        fromStationName.isEmpty ? Stations.displayNameForCode(fromStation) : fromStationName
    }
    
    var toStationDisplayName: String {
        toStationName.isEmpty ? Stations.displayNameForCode(toStation) : toStationName
    }
    
    var averageTransitTimeText: String {
        return ""
    }
    
    var sampleCountText: String {
        "\(sampleCount) train\(sampleCount == 1 ? "" : "s")"
    }
    
    var delayText: String {
        return ""
    }
    
    var congestionFactorDisplay: String {
        let percentage = Int((congestionFactor - 1) * 100)
        if percentage > 0 {
            return "+\(percentage)% slower"
        } else {
            return "Normal time"
        }
    }
}