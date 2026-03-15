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
    let journeyDate: Date?
    let line: V2LineInfo
    let destination: String
    let departure: V2StationInfo
    let arrival: V2StationInfo?
    let trainPosition: V2TrainPosition
    let dataFreshness: V2DataFreshness
    let dataSource: String
    let observationType: String?
    let isCancelled: Bool
    let cancellationReason: String?

    enum CodingKeys: String, CodingKey {
        case trainId = "train_id"
        case journeyDate = "journey_date"
        case line, destination, departure, arrival
        case trainPosition = "train_position"
        case dataFreshness = "data_freshness"
        case dataSource = "data_source"
        case observationType = "observation_type"
        case isCancelled = "is_cancelled"
        case cancellationReason = "cancellation_reason"
    }
    
    // Helper to check if this is a scheduled (not observed) train
    var isScheduledOnly: Bool {
        return observationType == "SCHEDULED"
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
    let predictedArrival: Date?
    let predictedArrivalSamples: Int?
    
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
        case predictedArrival = "predicted_arrival"
        case predictedArrivalSamples = "predicted_arrival_samples"
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
    let observationType: String?
    let rawTrainState: String?
    let isCancelled: Bool
    let cancellationReason: String?
    let isCompleted: Bool

    enum CodingKeys: String, CodingKey {
        case trainId = "train_id"
        case journeyDate = "journey_date"
        case line, route
        case trainPosition = "train_position"
        case stops
        case dataFreshness = "data_freshness"
        case dataSource = "data_source"
        case observationType = "observation_type"
        case rawTrainState = "raw_train_state"
        case isCancelled = "is_cancelled"
        case cancellationReason = "cancellation_reason"
        case isCompleted = "is_completed"
    }
    
    // Helper to check if this is a scheduled (not observed) train
    var isScheduledOnly: Bool {
        return observationType == "SCHEDULED"
    }
}

struct V2TrackPrediction: Codable {
    let platformProbabilities: [String: Double]
    let primaryPrediction: String
    let confidence: Double
    let top3: [String]
    let stationCode: String

    enum CodingKeys: String, CodingKey {
        case platformProbabilities = "platform_probabilities"
        case primaryPrediction = "primary_prediction"
        case confidence
        case top3 = "top_3"
        case stationCode = "station_code"
    }
}

struct V2TrainDetailsResponse: Codable {
    let train: V2TrainDetails
    let trackPrediction: V2TrackPrediction?

    enum CodingKeys: String, CodingKey {
        case train
        case trackPrediction = "track_prediction"
    }
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

struct TrainLocationData: Codable, Identifiable {
    let trainId: String
    let line: String
    let dataSource: String
    
    // GPS coordinates (Amtrak only)
    let lat: Double?
    let lon: Double?
    
    // Station-based position (NJT and fallback for Amtrak)
    let lastDepartedStation: String?
    let atStation: String?
    let nextStation: String?
    let betweenStations: Bool
    
    // Progress tracking
    let journeyPercent: Double?
    
    // Movement data (Amtrak only)
    let velocity: Double?
    let heading: String?
    
    var id: String { trainId }
    
    enum CodingKeys: String, CodingKey {
        case trainId = "train_id"
        case line
        case dataSource = "data_source"
        case lat
        case lon
        case lastDepartedStation = "last_departed_station"
        case atStation = "at_station"
        case nextStation = "next_station"
        case betweenStations = "between_stations"
        case journeyPercent = "journey_percent"
        case velocity
        case heading
    }
}

struct IndividualJourneySegment: Codable, Identifiable {
    let journeyId: String
    let trainId: String
    let fromStation: String
    let toStation: String
    let fromStationName: String
    let toStationName: String
    let dataSource: String
    let scheduledDeparture: Date
    let actualDeparture: Date
    let scheduledArrival: Date
    let actualArrival: Date
    let scheduledMinutes: Double
    let actualMinutes: Double
    let delayMinutes: Double
    let congestionFactor: Double
    let congestionLevel: String
    let isCancelled: Bool
    let journeyDate: String  // Changed from Date to String since backend sends "YYYY-MM-DD" format
    
    enum CodingKeys: String, CodingKey {
        case journeyId = "journey_id"
        case trainId = "train_id"
        case fromStation = "from_station"
        case toStation = "to_station"
        case fromStationName = "from_station_name"
        case toStationName = "to_station_name"
        case dataSource = "data_source"
        case scheduledDeparture = "scheduled_departure"
        case actualDeparture = "actual_departure"
        case scheduledArrival = "scheduled_arrival"
        case actualArrival = "actual_arrival"
        case scheduledMinutes = "scheduled_minutes"
        case actualMinutes = "actual_minutes"
        case delayMinutes = "delay_minutes"
        case congestionFactor = "congestion_factor"
        case congestionLevel = "congestion_level"
        case isCancelled = "is_cancelled"
        case journeyDate = "journey_date"
    }
    
    // Identifiable
    var id: String {
        "\(journeyId)-\(fromStation)-\(toStation)"
    }
}

struct CongestionMapResponse: Codable {
    let individualSegments: [IndividualJourneySegment]
    let aggregatedSegments: [CongestionSegment]
    let trainPositions: [TrainLocationData]
    let generatedAt: Date
    let timeWindowHours: Int
    let maxPerSegment: Int
    
    // Use a custom metadata structure that matches what backend actually sends
    private let rawMetadata: [String: CodableValue]
    
    enum CodingKeys: String, CodingKey {
        case individualSegments = "individual_segments"
        case aggregatedSegments = "aggregated_segments"
        case trainPositions = "train_positions"
        case generatedAt = "generated_at"
        case timeWindowHours = "time_window_hours"
        case maxPerSegment = "max_per_segment"
        case rawMetadata = "metadata"
    }
    
    // Computed properties to access metadata fields safely
    var totalIndividualSegments: Int {
        rawMetadata["total_individual_segments"]?.intValue ?? 0
    }
    
    var totalAggregatedSegments: Int {
        rawMetadata["total_aggregated_segments"]?.intValue ?? 0
    }
    
    var totalTrains: Int {
        rawMetadata["total_trains"]?.intValue ?? 0
    }
}

// Helper enum to handle different value types in metadata
enum CodableValue: Codable {
    case int(Int)
    case string(String)
    case double(Double)
    case bool(Bool)
    case dictionary([String: CodableValue])
    
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        
        if let intValue = try? container.decode(Int.self) {
            self = .int(intValue)
        } else if let stringValue = try? container.decode(String.self) {
            self = .string(stringValue)
        } else if let doubleValue = try? container.decode(Double.self) {
            self = .double(doubleValue)
        } else if let boolValue = try? container.decode(Bool.self) {
            self = .bool(boolValue)
        } else if let dictValue = try? container.decode([String: CodableValue].self) {
            self = .dictionary(dictValue)
        } else {
            throw DecodingError.typeMismatch(CodableValue.self, DecodingError.Context(codingPath: decoder.codingPath, debugDescription: "Unsupported type"))
        }
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .int(let value):
            try container.encode(value)
        case .string(let value):
            try container.encode(value)
        case .double(let value):
            try container.encode(value)
        case .bool(let value):
            try container.encode(value)
        case .dictionary(let value):
            try container.encode(value)
        }
    }
    
    var intValue: Int? {
        if case .int(let value) = self {
            return value
        }
        return nil
    }
    
    var stringValue: String? {
        if case .string(let value) = self {
            return value
        }
        return nil
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
    let cancellationCount: Int
    let cancellationRate: Double
    // Frequency/health metrics (nil for schedule-only sources like PATCO)
    let trainCount: Int?
    let baselineTrainCount: Double?
    let frequencyFactor: Double?
    let frequencyLevel: String?

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
        case cancellationCount = "cancellation_count"
        case cancellationRate = "cancellation_rate"
        case trainCount = "train_count"
        case baselineTrainCount = "baseline_train_count"
        case frequencyFactor = "frequency_factor"
        case frequencyLevel = "frequency_level"
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
    
    // Cancellation visualization properties
    var hasCancellations: Bool {
        return cancellationCount > 0
    }
    
    var hasHighCancellationRate: Bool {
        return cancellationRate > 10.0
    }
    
    var shouldShowDashedLine: Bool {
        return cancellationRate > 5.0
    }
    
    var cancellationDisplayText: String {
        if cancellationRate == 0 {
            return "No cancellations"
        } else {
            return "\(Int(cancellationRate))% cancelled"
        }
    }
    
    var dashPattern: [NSNumber]? {
        guard shouldShowDashedLine else { return nil }

        if cancellationRate > 20 {
            return [2, 2]  // Short dashes for high cancellation
        } else if cancellationRate > 10 {
            return [5, 3]  // Medium dashes
        } else {
            return [8, 4]  // Long dashes
        }
    }

    // MARK: - Frequency/Health Display Properties

    /// Whether this segment has frequency data (real-time sources only)
    var hasFrequencyData: Bool {
        frequencyFactor != nil && baselineTrainCount != nil
    }

    /// Color for frequency/health visualization (higher is better)
    var frequencyDisplayColor: Color {
        guard let factor = frequencyFactor else { return .gray }
        if factor >= 0.9 {
            return .green    // Healthy: ≥90% of baseline
        } else if factor >= 0.7 {
            return .yellow   // Moderate: 70-90% of baseline
        } else if factor >= 0.5 {
            return .orange   // Reduced: 50-70% of baseline
        } else {
            return .red      // Severe: <50% of baseline
        }
    }

    /// Display text for frequency level
    var displayFrequencyLevel: String {
        guard let level = frequencyLevel else { return "No data" }
        switch level {
        case "healthy": return "Healthy service"
        case "moderate": return "Moderate service"
        case "reduced": return "Reduced service"
        case "severe": return "Severe disruption"
        default: return level.capitalized
        }
    }

    /// Percentage of baseline service running
    var frequencyPercentage: Int? {
        guard let factor = frequencyFactor else { return nil }
        return Int((factor * 100).rounded())
    }

    /// Current average minutes between departures
    func currentHeadwayMinutes(timeWindowHours: Int) -> Double? {
        guard let count = trainCount, count > 0 else { return nil }
        return Double(timeWindowHours * 60) / Double(count)
    }

    /// Baseline average minutes between departures
    func baselineHeadwayMinutes(timeWindowHours: Int) -> Double? {
        guard let baseline = baselineTrainCount, baseline > 0 else { return nil }
        return Double(timeWindowHours * 60) / baseline
    }

    /// Human-readable headway string, e.g. "Every ~8 min"
    func headwayDisplayText(timeWindowHours: Int) -> String? {
        guard let headway = currentHeadwayMinutes(timeWindowHours: timeWindowHours) else {
            return nil
        }
        let rounded = Int(headway.rounded())
        if rounded <= 1 {
            return "Every ~1 min"
        }
        return "Every ~\(rounded) min"
    }

    /// Preferred highlight mode based on this segment's data source.
    /// Rapid transit (PATH, Subway, PATCO) → frequency coloring.
    /// Commuter/intercity rail (NJT, Amtrak, LIRR, MNR) → delay coloring.
    var preferredHighlightMode: SegmentHighlightMode {
        guard let system = TrainSystem(rawValue: dataSource) else { return .delays }
        return system.preferredHighlightMode
    }
}

// MARK: - Segment Highlight Mode

/// Display mode for map segment highlighting
enum SegmentHighlightMode: String, CaseIterable {
    case off = "off"
    case health = "health"        // Train frequency vs baseline
    case delays = "delays"        // Congestion/transit time

    var displayName: String {
        switch self {
        case .off: return "Off"
        case .health: return "Train Count"
        case .delays: return "Travel Time"
        }
    }

    var icon: String {
        switch self {
        case .off: return "eye.slash"
        case .health: return "waveform"
        case .delays: return "clock.badge.exclamationmark"
        }
    }

    /// Toggle segments on/off. Per-segment coloring is automatic based on data source.
    var next: SegmentHighlightMode {
        switch self {
        case .off: return .delays
        case .delays, .health: return .off
        }
    }
}

struct StationCoordinates: Codable {
    let lat: Double
    let lon: Double
}

// Removed CongestionMetadata and CongestionLevelCounts structs
// Backend sends metadata as generic dictionary, handled by CodableValue in CongestionMapResponse

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

extension IndividualJourneySegment {
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
    
    /// Convert the journey date string to a Date object
    var journeyDateAsDate: Date? {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        return formatter.date(from: journeyDate)
    }
    
    var displayCongestionLevel: String {
        switch congestionLevel {
        case "normal": return "Normal"
        case "moderate": return "Moderate"
        case "heavy": return "Heavy"
        case "severe": return "Severe"
        default: return congestionLevel.capitalized
        }
    }
    
    var delayText: String {
        if delayMinutes > 0 {
            return "+\(Int(delayMinutes))m"
        } else if delayMinutes < 0 {
            return "\(Int(delayMinutes))m"
        } else {
            return "On time"
        }
    }
    
    var trainDisplayName: String {
        // For trains with synthetic IDs (GTFS-derived), show destination instead
        if TrainSystem.syntheticTrainIdSources.contains(dataSource) {
            return toStationName.isEmpty ? Stations.displayName(for: toStation) : toStationName
        }
        return "Train \(trainId)"
    }
}

extension CongestionSegment {
    var fromStationDisplayName: String {
        fromStationName.isEmpty ? Stations.displayName(for: fromStation) : fromStationName
    }

    var toStationDisplayName: String {
        toStationName.isEmpty ? Stations.displayName(for: toStation) : toStationName
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

// MARK: - Operations Summary Models

/// Summary scope for operations summary API
enum SummaryScope: String, Codable {
    case network
    case route
    case train
}

/// Delay category for train visualization
enum DelayCategory: String, Codable {
    case onTime = "on_time"
    case slightDelay = "slight_delay"
    case delayed = "delayed"
    case cancelled = "cancelled"
}

/// Summary of a single train's delay for visualization
struct TrainDelaySummary: Codable, Identifiable {
    let trainId: String
    let delayMinutes: Double
    let category: DelayCategory
    let scheduledDeparture: Date

    var id: String { trainId }

    enum CodingKeys: String, CodingKey {
        case trainId = "train_id"
        case delayMinutes = "delay_minutes"
        case category
        case scheduledDeparture = "scheduled_departure"
    }
}

/// Raw metrics included with summary response
struct SummaryMetrics: Codable {
    // Departure stats
    let onTimePercentage: Double?
    let averageDelayMinutes: Double?
    // Arrival stats (nil if no arrival data available)
    let arrivalOnTimePercentage: Double?
    let arrivalAverageDelayMinutes: Double?
    // Counts
    let cancellationCount: Int?
    let trainCount: Int?
    let trainsByCategory: [String: [TrainDelaySummary]]?
    let trainsByHeadway: [String: [TrainDelaySummary]]?

    enum CodingKeys: String, CodingKey {
        case onTimePercentage = "on_time_percentage"
        case averageDelayMinutes = "average_delay_minutes"
        case arrivalOnTimePercentage = "arrival_on_time_percentage"
        case arrivalAverageDelayMinutes = "arrival_average_delay_minutes"
        case cancellationCount = "cancellation_count"
        case trainCount = "train_count"
        case trainsByCategory = "trains_by_category"
        case trainsByHeadway = "trains_by_headway"
    }
}

/// Response for operations summary endpoint
struct OperationsSummaryResponse: Codable {
    /// Short headline for collapsed view (max 50 chars)
    let headline: String

    /// Detailed summary (2-4 sentences) for expanded view
    let body: String

    /// Summary scope: network, route, or train
    let scope: String

    /// Time window in minutes (90 for recent, 43200 for 30-day)
    let timeWindowMinutes: Int

    /// Age of data in seconds
    let dataFreshnessSeconds: Int

    /// When summary was generated
    let generatedAt: Date

    /// Raw metrics for optional UI display
    let metrics: SummaryMetrics?

    enum CodingKeys: String, CodingKey {
        case headline
        case body
        case scope
        case timeWindowMinutes = "time_window_minutes"
        case dataFreshnessSeconds = "data_freshness_seconds"
        case generatedAt = "generated_at"
        case metrics
    }

    /// Formatted data freshness for display
    var dataFreshnessFormatted: String {
        if dataFreshnessSeconds < 60 {
            return "just now"
        } else if dataFreshnessSeconds < 3600 {
            let minutes = dataFreshnessSeconds / 60
            return "\(minutes) min ago"
        } else {
            let hours = dataFreshnessSeconds / 3600
            return "\(hours) hr ago"
        }
    }
}

// MARK: - Service Alert Models

struct V2ServiceAlertActivePeriod: Codable {
    let start: Int?
    let end: Int?
}

struct V2ServiceAlert: Codable, Identifiable {
    let alertId: String
    let dataSource: String
    let alertType: String
    let affectedRouteIds: [String]
    let headerText: String
    let descriptionText: String?
    let activePeriods: [V2ServiceAlertActivePeriod]

    var id: String { alertId }

    enum CodingKeys: String, CodingKey {
        case alertId = "alert_id"
        case dataSource = "data_source"
        case alertType = "alert_type"
        case affectedRouteIds = "affected_route_ids"
        case headerText = "header_text"
        case descriptionText = "description_text"
        case activePeriods = "active_periods"
    }

    /// Human-readable alert type label
    var alertTypeLabel: String {
        switch alertType {
        case "planned_work": return "Planned Work"
        case "alert": return "Alert"
        case "elevator": return "Elevator"
        default: return alertType.capitalized
        }
    }

    /// Whether any active period covers the current time
    var isActiveNow: Bool {
        guard !activePeriods.isEmpty else { return true } // No periods = always active
        let now = Date().timeIntervalSince1970
        return activePeriods.contains { period in
            let start = period.start.map { TimeInterval($0) } ?? 0
            let end = period.end.map { TimeInterval($0) } ?? .infinity
            return now >= start && now <= end
        }
    }

    /// Formatted string for the most relevant active period
    var activePeriodText: String? {
        guard !activePeriods.isEmpty else { return nil }

        let now = Date()
        let nowEpoch = now.timeIntervalSince1970

        // Find the current or next-upcoming period
        let sorted = activePeriods.sorted { ($0.start ?? 0) < ($1.start ?? 0) }
        let relevant = sorted.first { period in
            let end = period.end.map { TimeInterval($0) } ?? .infinity
            return end >= nowEpoch
        } ?? sorted.last!

        return Self.formatPeriod(relevant, relativeTo: now)
    }

    /// Additional period count beyond the displayed one
    var additionalPeriodCount: Int {
        max(0, activePeriods.count - 1)
    }

    /// Earliest start time across all active periods (for chronological sorting)
    var earliestStartEpoch: TimeInterval {
        activePeriods.compactMap { $0.start }.map { TimeInterval($0) }.min() ?? 0
    }

    private static func formatPeriod(_ period: V2ServiceAlertActivePeriod, relativeTo now: Date) -> String {
        let calendar = Calendar.current
        let startDate = period.start.map { Date(timeIntervalSince1970: TimeInterval($0)) }
        let endDate = period.end.map { Date(timeIntervalSince1970: TimeInterval($0)) }

        let timeFormatter = DateFormatter()
        timeFormatter.dateFormat = "h:mm a"
        timeFormatter.timeZone = TimeZone(identifier: "America/New_York")

        let dateTimeFormatter = DateFormatter()
        dateTimeFormatter.dateFormat = "MMM d, h:mm a"
        dateTimeFormatter.timeZone = TimeZone(identifier: "America/New_York")

        let dateOnlyFormatter = DateFormatter()
        dateOnlyFormatter.dateFormat = "MMM d"
        dateOnlyFormatter.timeZone = TimeZone(identifier: "America/New_York")

        switch (startDate, endDate) {
        case let (.some(start), .some(end)):
            let tz = TimeZone(identifier: "America/New_York")!
            let sameDay = calendar.isDate(start, inSameDayAs: end)
            // Check if times are midnight (all-day events)
            let startComps = calendar.dateComponents(in: tz, from: start)
            let endComps = calendar.dateComponents(in: tz, from: end)
            let startIsMidnight = startComps.hour == 0 && startComps.minute == 0
            let endIsMidnight = endComps.hour == 0 && endComps.minute == 0

            if startIsMidnight && endIsMidnight {
                // All-day: "Mar 14" or "Mar 14–16"
                if sameDay || calendar.isDate(end, inSameDayAs: calendar.date(byAdding: .day, value: 1, to: start)!) {
                    return dateOnlyFormatter.string(from: start)
                } else {
                    // End midnight means "through" the previous day
                    let adjustedEnd = calendar.date(byAdding: .day, value: -1, to: end) ?? end
                    if calendar.component(.month, from: start) == calendar.component(.month, from: adjustedEnd) {
                        return "\(dateOnlyFormatter.string(from: start))–\(calendar.component(.day, from: adjustedEnd))"
                    }
                    return "\(dateOnlyFormatter.string(from: start)) – \(dateOnlyFormatter.string(from: adjustedEnd))"
                }
            } else if sameDay {
                // Same day with times: "Mar 14, 10:00 PM – 5:00 AM"
                return "\(dateOnlyFormatter.string(from: start)), \(timeFormatter.string(from: start)) – \(timeFormatter.string(from: end))"
            } else {
                // Multi-day with times: "Mar 14, 10:00 PM – Mar 16, 5:00 AM"
                return "\(dateTimeFormatter.string(from: start)) – \(dateTimeFormatter.string(from: end))"
            }
        case let (.some(start), .none):
            return "Starting \(dateTimeFormatter.string(from: start))"
        case let (.none, .some(end)):
            return "Until \(dateTimeFormatter.string(from: end))"
        case (.none, .none):
            return "Ongoing"
        }
    }
}

struct V2ServiceAlertsResponse: Codable {
    let alerts: [V2ServiceAlert]
    let count: Int
}

// MARK: - Delay Forecast Models

/// Delay probability breakdown
struct DelayBreakdownProbabilities: Codable {
    let onTime: Double
    let slight: Double
    let significant: Double
    let major: Double

    enum CodingKeys: String, CodingKey {
        case onTime = "on_time"
        case slight
        case significant
        case major
    }
}

/// Response for delay/cancellation forecast endpoint
struct DelayForecastResponse: Codable {
    let trainId: String
    let stationCode: String
    let journeyDate: String

    /// Probability of cancellation (0.0-1.0)
    let cancellationProbability: Double

    /// Delay probabilities (sum to 1.0 for non-cancelled scenario)
    let delayProbabilities: DelayBreakdownProbabilities

    /// Expected delay in minutes
    let expectedDelayMinutes: Int

    /// Confidence level: "high", "medium", or "low"
    let confidence: String

    /// Historical samples used
    let sampleCount: Int

    /// Factors used in forecast
    let factors: [String]

    enum CodingKeys: String, CodingKey {
        case trainId = "train_id"
        case stationCode = "station_code"
        case journeyDate = "journey_date"
        case cancellationProbability = "cancellation_probability"
        case delayProbabilities = "delay_probabilities"
        case expectedDelayMinutes = "expected_delay_minutes"
        case confidence
        case sampleCount = "sample_count"
        case factors
    }

    // MARK: - Display Helpers

    /// Formatted on-time probability as percentage
    var onTimePercentage: Int {
        Int(delayProbabilities.onTime * 100)
    }

    /// Formatted cancellation probability as percentage
    var cancellationPercentage: Int {
        Int(cancellationProbability * 100)
    }

    /// Whether to show cancellation warning (> 5%)
    var showCancellationWarning: Bool {
        cancellationProbability > 0.05
    }

    /// Color for on-time probability
    var onTimeColor: Color {
        if delayProbabilities.onTime >= 0.80 {
            return .green
        } else if delayProbabilities.onTime >= 0.60 {
            return .yellow
        } else {
            return .orange
        }
    }

    /// Display text for delay breakdown
    var delayBreakdownText: String {
        let onTime = onTimePercentage
        let slight = Int(delayProbabilities.slight * 100)

        if slight > 5 {
            return "\(onTime)% on-time · \(slight)% slight delay"
        } else {
            return "\(onTime)% on-time"
        }
    }

    /// Confidence display text
    var confidenceText: String {
        switch confidence {
        case "high": return "High confidence"
        case "medium": return "Medium confidence"
        default: return "Low confidence"
        }
    }
}
