import Foundation

// MARK: - Train Model
struct Train: Identifiable, Codable {
    let id: Int  // For consolidated: derive from consolidatedId hash, for legacy: use actual id
    let trainId: String
    let line: String
    let destination: String
    let departureTime: Date
    let track: String?
    let status: TrainStatus
    let delayMinutes: Int?
    let stops: [Stop]?
    let predictionData: PredictionData?
    let originStationCode: String?
    let dataSource: String?
    
    // Consolidated data from multiple sources
    let consolidatedId: String?
    let originStation: OriginStation?
    let dataSources: [DataSource]?
    let currentPosition: CurrentPosition?
    let trackAssignment: TrackAssignment?
    let statusSummary: StatusSummary?
    let consolidationMetadata: ConsolidationMetadata?
    
    // New enhanced fields
    let statusV2: StatusV2?
    let progress: TrainProgress?
    
    enum CodingKeys: String, CodingKey {
        case id
        case trainId = "train_id"
        case line
        case destination
        case departureTime = "departure_time"
        case track
        case status
        case delayMinutes = "delay_minutes"
        case stops
        case predictionData = "prediction_data"
        case originStationCode = "origin_station_code"
        case dataSource = "data_source"
        case consolidatedId = "consolidated_id"
        case originStation = "origin_station"
        case dataSources = "data_sources"
        case currentPosition = "current_position"
        case trackAssignment = "track_assignment"
        case statusSummary = "status_summary"
        case consolidationMetadata = "consolidation_metadata"
        case statusV2 = "status_v2"
        case progress
    }
    
    // Custom decoder to handle both legacy and consolidated formats
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        
        // Try to detect format by checking for consolidated_id
        let isConsolidated = container.contains(.consolidatedId)
        
        if isConsolidated {
            // Consolidated format
            consolidatedId = try container.decodeIfPresent(String.self, forKey: .consolidatedId)
            trainId = try container.decode(String.self, forKey: .trainId)
            line = try container.decode(String.self, forKey: .line)
            destination = try container.decode(String.self, forKey: .destination)
            
            // For consolidated, get departure time from origin_station
            originStation = try container.decodeIfPresent(OriginStation.self, forKey: .originStation)
            departureTime = originStation?.departureTime ?? Date()
            
            // Get track from track_assignment
            trackAssignment = try container.decodeIfPresent(TrackAssignment.self, forKey: .trackAssignment)
            track = trackAssignment?.track
            
            // Get status from status_summary
            statusSummary = try container.decodeIfPresent(StatusSummary.self, forKey: .statusSummary)
            if let statusSummary = statusSummary {
                status = Self.mapConsolidatedStatusStatic(statusSummary.currentStatus)
                delayMinutes = statusSummary.delayMinutes
            } else {
                status = .scheduled
                delayMinutes = 0
            }
            
            // Consolidated-specific fields
            dataSources = try container.decodeIfPresent([DataSource].self, forKey: .dataSources)
            currentPosition = try container.decodeIfPresent(CurrentPosition.self, forKey: .currentPosition)
            consolidationMetadata = try container.decodeIfPresent(ConsolidationMetadata.self, forKey: .consolidationMetadata)
            
            // Generate a synthetic ID from consolidated_id hash
            id = consolidatedId?.hashValue ?? trainId.hashValue
            
            // Origin station code from origin_station or first data source
            originStationCode = originStation?.code ?? dataSources?.first?.origin
            
            // Data source from first source
            dataSource = dataSources?.first?.dataSource
            
            // New enhanced fields
            statusV2 = try container.decodeIfPresent(StatusV2.self, forKey: .statusV2)
            progress = try container.decodeIfPresent(TrainProgress.self, forKey: .progress)
            
        } else {
            // Legacy format
            id = try container.decode(Int.self, forKey: .id)
            trainId = try container.decode(String.self, forKey: .trainId)
            line = try container.decode(String.self, forKey: .line)
            destination = try container.decode(String.self, forKey: .destination)
            departureTime = try container.decode(Date.self, forKey: .departureTime)
            track = try container.decodeIfPresent(String.self, forKey: .track)
            status = try container.decode(TrainStatus.self, forKey: .status)
            delayMinutes = try container.decodeIfPresent(Int.self, forKey: .delayMinutes)
            originStationCode = try container.decodeIfPresent(String.self, forKey: .originStationCode)
            dataSource = try container.decodeIfPresent(String.self, forKey: .dataSource)
            
            // Legacy doesn't have consolidated fields
            consolidatedId = nil
            originStation = nil
            dataSources = nil
            currentPosition = nil
            trackAssignment = nil
            statusSummary = nil
            consolidationMetadata = nil
            
            // Enhanced fields can appear in legacy format too
            statusV2 = try container.decodeIfPresent(StatusV2.self, forKey: .statusV2)
            progress = try container.decodeIfPresent(TrainProgress.self, forKey: .progress)
        }
        
        // Common fields
        stops = try container.decodeIfPresent([Stop].self, forKey: .stops)
        predictionData = try container.decodeIfPresent(PredictionData.self, forKey: .predictionData)
    }
    
    // Programmatic initializer for creating Train objects directly
    init(id: Int, trainId: String, line: String, destination: String, departureTime: Date, track: String?, status: TrainStatus, delayMinutes: Int?, stops: [Stop]?, predictionData: PredictionData?, originStationCode: String?, dataSource: String?, consolidatedId: String? = nil, originStation: OriginStation? = nil, dataSources: [DataSource]? = nil, currentPosition: CurrentPosition? = nil, trackAssignment: TrackAssignment? = nil, statusSummary: StatusSummary? = nil, consolidationMetadata: ConsolidationMetadata? = nil, statusV2: StatusV2? = nil, progress: TrainProgress? = nil) {
        self.id = id
        self.trainId = trainId
        self.line = line
        self.destination = destination
        self.departureTime = departureTime
        self.track = track
        self.status = status
        self.delayMinutes = delayMinutes
        self.stops = stops
        self.predictionData = predictionData
        self.originStationCode = originStationCode
        self.dataSource = dataSource
        self.consolidatedId = consolidatedId
        self.originStation = originStation
        self.dataSources = dataSources
        self.currentPosition = currentPosition
        self.trackAssignment = trackAssignment
        self.statusSummary = statusSummary
        self.consolidationMetadata = consolidationMetadata
        self.statusV2 = statusV2
        self.progress = progress
    }
    
    // Static helper to map consolidated status strings (for use in decoder)
    private static func mapConsolidatedStatusStatic(_ statusString: String) -> TrainStatus {
        switch statusString.lowercased() {
        case "scheduled", "": return .scheduled
        case "on time", "on_time": return .onTime
        case "delayed": return .delayed
        case "boarding", "all aboard": return .boarding
        case "departed", "in transit": return .departed
        default: return .unknown
        }
    }
    
    // Instance helper to map consolidated status strings
    private func mapConsolidatedStatus(_ statusString: String) -> TrainStatus {
        return Self.mapConsolidatedStatusStatic(statusString)
    }
}

// MARK: - Train Status
enum TrainStatus: String, Codable {
    case scheduled = "SCHEDULED"
    case onTime = "ON_TIME"
    case delayed = "DELAYED"
    case boarding = "BOARDING"
    case departed = "DEPARTED"
    case unknown = "UNKNOWN"
    
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        let statusString = try container.decode(String.self)
        
        // Handle empty string as scheduled (no status)
        if statusString.isEmpty {
            self = .scheduled
        } else {
            self = TrainStatus(rawValue: statusString) ?? .unknown
        }
    }
    
    var displayText: String {
        switch self {
        case .scheduled: return "Scheduled"
        case .onTime: return "On Time"
        case .delayed: return "Delayed"
        case .boarding: return "Boarding"
        case .departed: return "Departed"
        case .unknown: return "Unknown"
        }
    }
    
    var color: String {
        switch self {
        case .scheduled: return "gray"
        case .onTime: return "green"
        case .delayed: return "red"
        case .boarding: return "orange"
        case .departed: return "gray"
        case .unknown: return "gray"
        }
    }
}

// MARK: - Stop Model
struct Stop: Identifiable, Codable {
    let id = UUID()
    let stationCode: String?
    let stationName: String
    let scheduledArrival: Date?
    let scheduledDeparture: Date?
    let actualArrival: Date?
    let actualDeparture: Date?
    let estimatedArrival: Date?
    let pickupOnly: Bool?
    let dropoffOnly: Bool?
    let departed: Bool?
    let departedConfirmedBy: [String]?
    let stopStatus: String?
    let platform: String?
    
    // Legacy computed properties for backward compatibility
    var scheduledTime: Date? { scheduledArrival }
    var departureTime: Date? { actualDeparture ?? scheduledDeparture }
    
    enum CodingKeys: String, CodingKey {
        case stationCode = "station_code"
        case stationName = "station_name"
        case scheduledArrival = "scheduled_arrival"
        case scheduledDeparture = "scheduled_departure"
        case actualArrival = "actual_arrival"
        case actualDeparture = "actual_departure"
        case estimatedArrival = "estimated_arrival"
        case pickupOnly = "pickup_only"
        case dropoffOnly = "dropoff_only"
        case departed
        case departedConfirmedBy = "departed_confirmed_by"
        case stopStatus = "stop_status"
        case platform
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        
        stationCode = try container.decodeIfPresent(String.self, forKey: .stationCode)
        stationName = try container.decode(String.self, forKey: .stationName)
        scheduledArrival = try container.decodeIfPresent(Date.self, forKey: .scheduledArrival)
        scheduledDeparture = try container.decodeIfPresent(Date.self, forKey: .scheduledDeparture)
        actualArrival = try container.decodeIfPresent(Date.self, forKey: .actualArrival)
        actualDeparture = try container.decodeIfPresent(Date.self, forKey: .actualDeparture)
        estimatedArrival = try container.decodeIfPresent(Date.self, forKey: .estimatedArrival)
        pickupOnly = try container.decodeIfPresent(Bool.self, forKey: .pickupOnly)
        dropoffOnly = try container.decodeIfPresent(Bool.self, forKey: .dropoffOnly)
        departed = try container.decodeIfPresent(Bool.self, forKey: .departed) ?? false
        departedConfirmedBy = try container.decodeIfPresent([String].self, forKey: .departedConfirmedBy)
        stopStatus = try container.decodeIfPresent(String.self, forKey: .stopStatus)
        platform = try container.decodeIfPresent(String.self, forKey: .platform)
    }
    
    init(stationCode: String?, stationName: String, scheduledArrival: Date?, scheduledDeparture: Date?, actualArrival: Date?, actualDeparture: Date?, estimatedArrival: Date?, pickupOnly: Bool?, dropoffOnly: Bool?, departed: Bool?, departedConfirmedBy: [String]?, stopStatus: String?, platform: String?) {
        self.stationCode = stationCode
        self.stationName = stationName
        self.scheduledArrival = scheduledArrival
        self.scheduledDeparture = scheduledDeparture
        self.actualArrival = actualArrival
        self.actualDeparture = actualDeparture
        self.estimatedArrival = estimatedArrival
        self.pickupOnly = pickupOnly
        self.dropoffOnly = dropoffOnly
        self.departed = departed ?? false
        self.departedConfirmedBy = departedConfirmedBy
        self.stopStatus = stopStatus
        self.platform = platform
    }
}

// MARK: - Stop Extensions
extension Stop {
    /// Returns the normalized display name for this stop's station
    var normalizedStationName: String {
        return StationNameNormalizer.normalizedName(for: stationName)
    }
}

// MARK: - Prediction Data
struct PredictionData: Codable {
    let trackProbabilities: [String: Double]?
    
    enum CodingKeys: String, CodingKey {
        case trackProbabilities = "track_probabilities"
    }
}

// MARK: - Consolidated Data Structures
struct OriginStation: Codable {
    let code: String
    let name: String
    let departureTime: Date
    
    enum CodingKeys: String, CodingKey {
        case code
        case name
        case departureTime = "departure_time"
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        code = try container.decode(String.self, forKey: .code)
        name = try container.decode(String.self, forKey: .name)
        
        // Handle date decoding with custom parser
        let dateString = try container.decode(String.self, forKey: .departureTime)
        if let date = Date.fromISO8601(dateString) {
            departureTime = date
        } else {
            throw DecodingError.dataCorrupted(
                DecodingError.Context(
                    codingPath: container.codingPath + [CodingKeys.departureTime],
                    debugDescription: "Invalid date format: \(dateString)"
                )
            )
        }
    }
    
    init(code: String, name: String, departureTime: Date) {
        self.code = code
        self.name = name
        self.departureTime = departureTime
    }
}

struct ConsolidationMetadata: Codable {
    let sourceCount: Int
    let lastUpdate: Date
    let confidenceScore: Double
    
    enum CodingKeys: String, CodingKey {
        case sourceCount = "source_count"
        case lastUpdate = "last_update"
        case confidenceScore = "confidence_score"
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        sourceCount = try container.decode(Int.self, forKey: .sourceCount)
        confidenceScore = try container.decode(Double.self, forKey: .confidenceScore)
        
        // Handle date decoding with custom parser
        let dateString = try container.decode(String.self, forKey: .lastUpdate)
        if let date = Date.fromISO8601(dateString) {
            lastUpdate = date
        } else {
            throw DecodingError.dataCorrupted(
                DecodingError.Context(
                    codingPath: container.codingPath + [CodingKeys.lastUpdate],
                    debugDescription: "Invalid date format: \(dateString)"
                )
            )
        }
    }
    
    init(sourceCount: Int, lastUpdate: Date, confidenceScore: Double) {
        self.sourceCount = sourceCount
        self.lastUpdate = lastUpdate
        self.confidenceScore = confidenceScore
    }
}

struct DataSource: Codable {
    let origin: String
    let dataSource: String
    let lastUpdate: Date
    let status: String?
    let track: String?
    let delayMinutes: Int?
    let dbId: Int
    
    enum CodingKeys: String, CodingKey {
        case origin
        case dataSource = "data_source"
        case lastUpdate = "last_update"
        case status
        case track
        case delayMinutes = "delay_minutes"
        case dbId = "db_id"
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        origin = try container.decode(String.self, forKey: .origin)
        dataSource = try container.decode(String.self, forKey: .dataSource)
        status = try container.decodeIfPresent(String.self, forKey: .status)
        track = try container.decodeIfPresent(String.self, forKey: .track)
        delayMinutes = try container.decodeIfPresent(Int.self, forKey: .delayMinutes)
        dbId = try container.decode(Int.self, forKey: .dbId)
        
        // Handle date decoding with custom parser
        let dateString = try container.decode(String.self, forKey: .lastUpdate)
        if let date = Date.fromISO8601(dateString) {
            lastUpdate = date
        } else {
            throw DecodingError.dataCorrupted(
                DecodingError.Context(
                    codingPath: container.codingPath + [CodingKeys.lastUpdate],
                    debugDescription: "Invalid date format: \(dateString)"
                )
            )
        }
    }
    
    init(origin: String, dataSource: String, lastUpdate: Date, status: String?, track: String?, delayMinutes: Int?, dbId: Int) {
        self.origin = origin
        self.dataSource = dataSource
        self.lastUpdate = lastUpdate
        self.status = status
        self.track = track
        self.delayMinutes = delayMinutes
        self.dbId = dbId
    }
}

struct CurrentPosition: Codable {
    let status: String?
    let lastDepartedStation: StationStatus?
    let nextStation: StationStatus?
    let segmentProgress: Double?
    let estimatedSpeedMph: Double?
    
    enum CodingKeys: String, CodingKey {
        case status
        case lastDepartedStation = "last_departed_station"
        case nextStation = "next_station"
        case segmentProgress = "segment_progress"
        case estimatedSpeedMph = "estimated_speed_mph"
    }
}

struct StationStatus: Codable {
    let code: String
    let name: String
    let scheduledDeparture: Date?
    let scheduledArrival: Date?
    let actualDeparture: Date?
    let estimatedArrival: Date?
    let distanceMiles: Double?
    
    enum CodingKeys: String, CodingKey {
        case code
        case name
        case scheduledDeparture = "scheduled_departure"
        case scheduledArrival = "scheduled_arrival"
        case actualDeparture = "actual_departure"
        case estimatedArrival = "estimated_arrival"
        case distanceMiles = "distance_miles"
    }
}

struct TrackAssignment: Codable {
    let track: String?
    let assignedAt: Date?
    let assignedBy: String?
    let source: String?
    
    enum CodingKeys: String, CodingKey {
        case track
        case assignedAt = "assigned_at"
        case assignedBy = "assigned_by"
        case source
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        track = try container.decodeIfPresent(String.self, forKey: .track)
        assignedBy = try container.decodeIfPresent(String.self, forKey: .assignedBy)
        source = try container.decodeIfPresent(String.self, forKey: .source)
        
        // Handle date decoding with custom parser
        if let dateString = try container.decodeIfPresent(String.self, forKey: .assignedAt) {
            if let date = Date.fromISO8601(dateString) {
                assignedAt = date
            } else {
                throw DecodingError.dataCorrupted(
                    DecodingError.Context(
                        codingPath: container.codingPath + [CodingKeys.assignedAt],
                        debugDescription: "Invalid date format: \(dateString)"
                    )
                )
            }
        } else {
            assignedAt = nil
        }
    }
    
    init(track: String?, assignedAt: Date?, assignedBy: String?, source: String?) {
        self.track = track
        self.assignedAt = assignedAt
        self.assignedBy = assignedBy
        self.source = source
    }
}

struct StatusSummary: Codable {
    let currentStatus: String
    let delayMinutes: Int
    let onTimePerformance: String
    
    enum CodingKeys: String, CodingKey {
        case currentStatus = "current_status"
        case delayMinutes = "delay_minutes"
        case onTimePerformance = "on_time_performance"
    }
}

// MARK: - Train Extensions
extension Train {
    /// Get the departure time from a specific origin station
    func getDepartureTime(fromStationCode: String) -> Date {
        // Find the stop that matches our departure station using robust matching
        if let stops = stops,
           let originStop = stops.first(where: { stop in
               Stations.stationMatches(stop, stationCode: fromStationCode)
           }),
           let departureTime = originStop.departureTime {
            return departureTime
        }
        
        // Fall back to the train's overall departure time
        return departureTime
    }
    
    /// Get formatted departure time from a specific origin station
    func getFormattedDepartureTime(fromStationCode: String) -> String {
        let time = getDepartureTime(fromStationCode: fromStationCode)
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        return formatter.string(from: time)
    }
    
    /// Returns an array of stops with normalized station names for display purposes
    var normalizedStops: [Stop] {
        return stops ?? []
        // Note: We don't need to create new Stop instances since we can use 
        // the normalizedStationName computed property on each Stop directly
    }
    
    // MARK: - Consolidated Data Helpers
    
    /// Check if this train has consolidated data from multiple sources
    var isConsolidated: Bool {
        return consolidatedId != nil
    }
    
    /// Get the best available track assignment
    var displayTrack: String? {
        // Prefer track from consolidated assignment
        if let consolidatedTrack = trackAssignment?.track {
            return consolidatedTrack
        }
        
        // Fall back to legacy track field
        return track
    }
    
    /// StatusV2-only status display (no fallbacks)
    var statusV2Display: String {
        guard let statusV2 = statusV2 else {
            return "UNKNOWN"
        }
        return statusV2.current
    }
    
    /// Check if train is actually boarding (requires StatusV2 and track)
    var isActuallyBoarding: Bool {
        guard let statusV2 = statusV2 else {
            return false
        }
        return statusV2.current == "BOARDING" && displayTrack != nil
    }
    
    /// Check if train has departed (StatusV2 only)
    var hasDeparted: Bool {
        guard let statusV2 = statusV2 else {
            return false
        }
        return statusV2.current == "EN_ROUTE" || statusV2.current == "ARRIVED"
    }
    
    /// Get StatusV2-based color for UI display
    var statusV2Color: String {
        guard let statusV2 = statusV2 else {
            return "gray"
        }
        
        switch statusV2.current {
        case "BOARDING":
            return displayTrack != nil ? "orange" : "gray"
        case "EN_ROUTE":
            return "blue"
        case "ARRIVED":
            return "green"
        case "DELAYED":
            return "red"
        case "CANCELLED":
            return "red"
        default:
            return "gray"
        }
    }
    
    /// Human-friendly StatusV2 text for display
    var statusV2DisplayText: String {
        guard let statusV2 = statusV2 else {
            return "Unknown"
        }
        
        switch statusV2.current {
        case "BOARDING":
            return displayTrack != nil ? "Boarding" : "Scheduled"
        case "EN_ROUTE":
            return "En Route"
        case "ARRIVED":
            return "Arrived"
        case "DELAYED":
            return "Delayed"
        case "CANCELLED":
            return "Cancelled"
        case "SCHEDULED":
            return "Scheduled"
        default:
            return statusV2.current.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }
    
    /// Get human-readable location description
    var displayLocation: String? {
        return statusV2?.location
    }
    
    /// Get journey progress information
    var journeyProgress: TrainProgress? {
        return progress
    }
    
    
    /// Get the best available delay information
    var displayDelayMinutes: Int {
        // Prefer consolidated delay information
        if let consolidated = statusSummary {
            return consolidated.delayMinutes
        }
        
        // Fall back to legacy delay
        return delayMinutes ?? 0
    }
    
    /// Check if train has real-time position tracking
    var hasPositionTracking: Bool {
        return currentPosition != nil
    }
    
    /// Get progress between stations (0.0 to 1.0)
    var segmentProgress: Double {
        return currentPosition?.segmentProgress ?? 0.0
    }
    
    /// Get estimated speed if available
    var estimatedSpeed: Double? {
        return currentPosition?.estimatedSpeedMph
    }
}

// MARK: - API Response
struct Metadata: Codable {
    let timestamp: String // Or Date, if you want to parse it
    let modelVersion: String
    let trainCount: Int
    let page: Int
    let totalPages: Int

    enum CodingKeys: String, CodingKey {
        case timestamp
        case modelVersion = "model_version"
        case trainCount = "train_count"
        case page
        case totalPages = "total_pages"
    }
}

struct TrainListResponse: Codable {
    let metadata: Metadata
    let trains: [Train]
}

// MARK: - Historical Data
struct HistoricalData {
    let trainStats: DelayStats?
    let lineStats: DelayStats?
    let destinationStats: DelayStats?
    let trainTrackStats: TrackStats?
    let lineTrackStats: TrackStats?
    let destinationTrackStats: TrackStats?
}

struct DelayStats {
    let onTime: Int
    let slight: Int
    let significant: Int
    let major: Int
    let total: Int
    let avgDelay: Int
}

struct TrackStats {
    let tracks: [(track: String, percentage: Int, count: Int)]
    let total: Int
}

// MARK: - Journey Progress Helper
struct JourneyProgress {
    let totalStops: Int
    let completedStops: Int
    let progress: Double
    let currentStopIndex: Int?
    
    static let unknown = JourneyProgress(
        totalStops: 0,
        completedStops: 0,
        progress: 0.0,
        currentStopIndex: nil
    )
}


// MARK: - New Enhanced Status and Progress Models
struct StatusV2: Codable {
    let current: String
    let location: String
    let updatedAt: Date
    let confidence: String
    let source: String
    
    enum CodingKeys: String, CodingKey {
        case current
        case location
        case updatedAt = "updated_at"
        case confidence
        case source
    }
}

struct DepartedStation: Codable {
    let stationCode: String
    let departedAt: Date
    let delayMinutes: Int
    
    enum CodingKeys: String, CodingKey {
        case stationCode = "station_code"
        case departedAt = "departed_at"
        case delayMinutes = "delay_minutes"
    }
}

struct NextArrival: Codable {
    let stationCode: String
    let scheduledTime: Date
    let estimatedTime: Date
    let minutesAway: Int
    
    enum CodingKeys: String, CodingKey {
        case stationCode = "station_code"
        case scheduledTime = "scheduled_arrival"
        case estimatedTime = "estimated_time"
        case minutesAway = "minutes_away"
    }
}

struct TrainProgress: Codable {
    let lastDeparted: DepartedStation?
    let nextArrival: NextArrival?
    let journeyPercent: Int
    let stopsCompleted: Int
    let totalStops: Int
    
    enum CodingKeys: String, CodingKey {
        case lastDeparted = "last_departed"
        case nextArrival = "next_arrival"
        case journeyPercent = "journey_percent"
        case stopsCompleted = "stops_completed"
        case totalStops = "total_stops"
    }
}