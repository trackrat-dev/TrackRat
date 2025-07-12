import Foundation

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
    let actualTime: Date?
    let estimatedTime: Date?
    let track: String?
    let status: String?
    let delayMinutes: Int
    
    enum CodingKeys: String, CodingKey {
        case code, name, track, status
        case scheduledTime = "scheduled_time"
        case actualTime = "actual_time"
        case estimatedTime = "estimated_time"
        case delayMinutes = "delay_minutes"
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

struct V2TrainDeparture: Codable {
    let trainId: String
    let line: V2LineInfo
    let destination: String
    let departure: V2StationInfo
    let arrival: V2StationInfo?
    let journey: V2JourneyInfo
    let dataFreshness: V2DataFreshness
    
    enum CodingKeys: String, CodingKey {
        case trainId = "train_id"
        case line, destination, departure, arrival, journey
        case dataFreshness = "data_freshness"
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

struct V2StopDetails: Codable {
    let station: V2SimpleStationInfo
    let sequence: Int
    let scheduledArrival: Date?
    let scheduledDeparture: Date?
    let actualArrival: Date?
    let actualDeparture: Date?
    let estimatedArrival: Date?
    let estimatedDeparture: Date?
    let track: String?
    let status: String?
    let delayMinutes: Int
    let departed: Bool
    
    enum CodingKeys: String, CodingKey {
        case station, sequence, departed, track, status
        case scheduledArrival = "scheduled_arrival"
        case scheduledDeparture = "scheduled_departure"
        case actualArrival = "actual_arrival"
        case actualDeparture = "actual_departure"
        case estimatedArrival = "estimated_arrival"
        case estimatedDeparture = "estimated_departure"
        case delayMinutes = "delay_minutes"
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
    let currentStatus: V2CurrentStatus
    let stops: [V2StopDetails]
    let dataFreshness: V2DataFreshness
    
    enum CodingKeys: String, CodingKey {
        case trainId = "train_id"
        case journeyDate = "journey_date"
        case line, route
        case currentStatus = "current_status"
        case stops
        case dataFreshness = "data_freshness"
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