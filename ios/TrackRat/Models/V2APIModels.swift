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