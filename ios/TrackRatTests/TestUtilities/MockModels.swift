import Foundation
@testable import TrackRat

extension Train {
    static func mock(
        id: Int = Int.random(in: 1...1000),
        trainId: String = "TR\(Int.random(in: 100...999))",
        destination: String = "Mock Destination",
        origin: String = "Mock Origin",
        line: String = "Mock Line",
        status: TrainStatus = .onTime,
        departureTime: Date = Date(),
        arrivalTime: Date? = nil,
        delayMinutes: Int? = nil,
        track: String? = nil,
        stops: [Stop]? = [Stop.mock()],
        lastUpdated: Date = Date(),
        isConsolidated: Bool = false,
        dataSources: [DataSource]? = nil,
        predictionData: PredictionData? = nil,
        trackAssignment: TrackAssignment? = nil,
        statusV2: StatusV2? = nil,
        progress: ProgressData? = nil,
        currentPosition: CurrentPosition? = nil,
        estimatedSpeed: Double? = nil,
        displayStatus: TrainStatus? = nil,
        displayTrack: String? = nil
    ) -> Train {
        // Simplified: The main departureTime property of Train is used for the *final* sort in refreshTrains.
        // The getDepartureTime(fromStationCode:) method, which uses stop data, is used for *filtering* and *initial sorting* in loadTrains and refreshTrains.
        // For robust mocks, ensure the Stop.mock within `stops` has a departureTime that aligns with tests for getDepartureTime.
        // And the top-level `departureTime` parameter for Train.mock aligns with tests for the final sort.
        return Train(
            id: id,
            trainId: trainId,
            destination: destination,
            origin: origin,
            line: line,
            status: status,
            departureTime: departureTime,
            arrivalTime: arrivalTime,
            delayMinutes: delayMinutes,
            track: track,
            stops: stops,
            lastUpdated: lastUpdated,
            isConsolidated: isConsolidated,
            dataSources: dataSources,
            predictionData: predictionData,
            trackAssignment: trackAssignment,
            statusV2: statusV2,
            progress: progress,
            currentPosition: currentPosition,
            estimatedSpeed: estimatedSpeed,
            displayStatus: displayStatus ?? status,
            displayTrack: displayTrack ?? track
        )
    }
}

extension Stop {
    static func mock(
        stationName: String = "Mock Station",
        stationCode: String = "MSK",
        scheduledTime: Date? = Date(),
        departureTime: Date? = Date(),
        actualTime: Date? = nil,
        departed: Bool? = false,
        stopStatus: String? = "ON_TIME"
    ) -> Stop {
        return Stop(
            stationCode: stationCode,
            stationName: stationName,
            scheduledArrival: scheduledTime,
            scheduledDeparture: departureTime ?? scheduledTime,
            actualArrival: actualTime,
            actualDeparture: nil,
            estimatedArrival: nil,
            pickupOnly: nil,
            dropoffOnly: nil,
            departed: departed,
            departedConfirmedBy: nil,
            stopStatus: stopStatus,
            platform: nil
        )
    }
}

// Minimal mocks for other types referenced by Train model
struct DataSource: Codable, Hashable, Identifiable { public var id: Int { dbId }; var dbId: Int; var dataSource: String; var origin: String; var status: String?; var track: String?; var timestamp: Date }
struct TrackAssignment: Codable, Hashable { var track: String; var assignedBy: String?; var confidence: Double?; var timestamp: Date }
struct PredictionData: Codable, Hashable { var trackProbabilities: [String: Double]? }
struct StatusV2: Codable, Hashable { var current: String; var location: String }
struct ProgressData: Codable, Hashable { var journeyPercent: Int; var stopsCompleted: Int; var totalStops: Int; var nextArrival: ArrivalInfo?; var lastDeparted: DepartureInfo? }
struct CurrentPosition: Codable, Hashable { var lastDepartedStation: StationInfo?; var nextStation: StationInfo?; var segmentProgress: Double?; var estimatedCurrentTrack: String? }
struct StationInfo: Codable, Hashable { var name: String; var code: String; var timestamp: Date; var delayMinutes: Int }
struct ArrivalInfo: Codable, Hashable { var stationCode: String; var minutesAway: Int; var delayMinutes: Int }
struct DepartureInfo: Codable, Hashable { var stationCode: String; var timestamp: Date; var delayMinutes: Int }

// Provide static mock initializers for these simple structs too if complex mocking is needed later
extension HistoricalData { // Assuming HistoricalData is a struct; define if not present
    static func mock() -> HistoricalData { HistoricalData(trainStats: nil, lineStats: nil, destinationStats: nil, trainTrackStats: nil, lineTrackStats: nil, destinationTrackStats: nil) }
}
// Define HistoricalData and its sub-structs (DelayStats, TrackStats) if not available in scope
struct DelayStats: Codable, Hashable { /* fields */ }
struct TrackStats: Codable, Hashable { /* fields */ }
struct HistoricalData: Codable, Hashable {
    var trainStats: DelayStats?
    var lineStats: DelayStats?
    var destinationStats: DelayStats?
    var trainTrackStats: TrackStats?
    var lineTrackStats: TrackStats?
    var destinationTrackStats: TrackStats?
}
