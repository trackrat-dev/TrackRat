import Foundation

// MARK: - Journey Context
// Represents the user's journey segment for context-aware calculations
struct JourneyContext {
    let originStationCode: String
    let destinationName: String?
    
    init(from originCode: String, to destinationName: String? = nil) {
        self.originStationCode = originCode
        self.destinationName = destinationName
    }
}

// MARK: - Pure Data Train Model for Backend V2
// This model uses the pure data approach where the backend provides
// objective facts and the iOS client calculates context-aware status

struct TrainV2: Identifiable, Codable {
    // Core fields
    let id: Int  // Generated from trainId.hashValue for Identifiable
    let trainId: String
    let line: LineInfo
    let destination: String
    let departure: StationTiming
    let arrival: StationTiming?
    let trainPosition: TrainPosition?
    let dataFreshness: DataFreshness?
    
    // Optional detailed stops (populated from detail endpoint)
    var stops: [StopV2]? = nil
    
    // MARK: - Computed Properties for UI Compatibility
    
    var departureTime: Date {
        departure.scheduledTime ?? Date()
    }
    
    var track: String? {
        departure.track
    }
    
    var status: TrainStatus {
        // Default to scheduled - context-aware status should be calculated separately
        .scheduled
    }
    
    var delayMinutes: Int {
        departure.delayMinutes
    }
    
    var originStationCode: String {
        departure.code
    }
    
    var originStationName: String {
        departure.name
    }
    
    var destinationStationCode: String? {
        arrival?.code
    }
    
    // Static track prediction data (temporary until backend implementation)
    var predictionData: PredictionData? {
        return StaticTrackDistributionService.shared.getPredictionData(for: self)
    }
    
    // Enhanced display status using train position
    var enhancedDisplayStatus: String {
        if let position = trainPosition {
            if let nextStation = position.nextStationCode {
                return "En Route to \(nextStation)"
            } else if let atStation = position.atStationCode {
                return "At \(atStation)"
            }
        }
        return status.displayText
    }
    
    // Check if train is boarding at user's origin (requires journey context)
    func isBoarding(fromStationCode: String) -> Bool {
        // Check if train is at the user's origin station
        if let position = trainPosition,
           position.atStationCode == fromStationCode {
            // Check if train has departed from this station
            if let stop = stops?.first(where: { $0.stationCode == fromStationCode }) {
                return !stop.hasDepartedStation
            }
        }
        return false
    }
    
    // MARK: - Helper Methods
    
    // Calculate context-aware status based on user's journey
    func calculateStatus(fromStationCode: String, toStationName: String? = nil) -> TrainStatus {
        // Check if train has departed from user's origin
        if hasTrainDepartedFromStation(fromStationCode) {
            return .departed
        }
        
        // Check if train is at user's origin and boarding
        if isBoarding(fromStationCode: fromStationCode) {
            return .boarding
        }
        
        // Check for delays
        if delayMinutes > 0 {
            return .delayed
        }
        
        return .onTime
    }
    
    // Convenience method using JourneyContext
    func calculateStatus(for context: JourneyContext) -> TrainStatus {
        return calculateStatus(fromStationCode: context.originStationCode, toStationName: context.destinationName)
    }
    
    // Check if train has departed from a specific station
    func hasTrainDepartedFromStation(_ stationCode: String) -> Bool {
        if let stop = stops?.first(where: { $0.stationCode == stationCode }) {
            return stop.hasDepartedStation
        }
        return false
    }
    
    // Get departure time from a specific station
    func getDepartureTime(fromStationCode: String) -> Date? {
        if fromStationCode == originStationCode {
            return departureTime
        }
        
        // Find departure from stops if available
        return stops?.first { $0.stationCode == fromStationCode }?.scheduledDeparture
    }
    
    // Get scheduled departure time from a specific station
    func getScheduledDepartureTime(fromStationCode: String) -> Date? {
        if fromStationCode == originStationCode {
            return departure.scheduledTime
        }
        
        // Find departure from stops if available
        return stops?.first { $0.stationCode == fromStationCode }?.scheduledDeparture
    }
    
    // Get scheduled arrival time at a specific destination
    func getScheduledArrivalTime(toStationName: String) -> Date? {
        // Check if destination matches
        if destination.lowercased().contains(toStationName.lowercased()) {
            return arrival?.scheduledTime
        }
        
        // Find arrival from stops if available
        return stops?.first { 
            $0.stationName.lowercased().contains(toStationName.lowercased()) 
        }?.scheduledArrival
    }
    
    // Get formatted departure time for display
    func getFormattedDepartureTime(fromStationCode: String) -> String {
        guard let time = getDepartureTime(fromStationCode: fromStationCode) else {
            return "--:--"
        }
        
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        formatter.dateFormat = "h:mm a"
        return formatter.string(from: time)
    }
    
    // Check if train is departing soon (within specified minutes)
    func isDepartingSoon(fromStationCode: String, withinMinutes: Int = 11) -> Bool {
        guard let departureTime = getDepartureTime(fromStationCode: fromStationCode) else {
            return false
        }
        
        let now = Date()
        let timeUntilDeparture = departureTime.timeIntervalSince(now)
        
        // Check if departure is in the future and within the specified time window
        return timeUntilDeparture > 0 && timeUntilDeparture <= Double(withinMinutes * 60)
    }
}

// MARK: - Supporting Models

struct LineInfo: Codable {
    let code: String
    let name: String
    let color: String
}

struct StationTiming: Codable {
    let code: String
    let name: String
    let scheduledTime: Date?
    let updatedTime: Date?  // Renamed from estimatedTime to match backend
    let actualTime: Date?
    let track: String?
    
    // Computed property to calculate delay client-side (pure data approach)
    var delayMinutes: Int {
        guard let scheduled = scheduledTime else { return 0 }
        
        // Use actual time if available, otherwise updated time
        let compareTime = actualTime ?? updatedTime ?? scheduled
        
        let delaySeconds = compareTime.timeIntervalSince(scheduled)
        return max(0, Int(delaySeconds / 60))
    }
    
    enum CodingKeys: String, CodingKey {
        case code, name, track
        case scheduledTime = "scheduled_time"
        case updatedTime = "updated_time"
        case actualTime = "actual_time"
    }
}

struct TrainPosition: Codable {
    let lastDepartedStationCode: String?
    let atStationCode: String?
    let nextStationCode: String?
    
    enum CodingKeys: String, CodingKey {
        case lastDepartedStationCode = "last_departed_station_code"
        case atStationCode = "at_station_code"
        case nextStationCode = "next_station_code"
    }
}

struct DataFreshness: Codable {
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
    
    var isStale: Bool {
        ageSeconds > 300  // Consider stale after 5 minutes
    }
    
    var formattedAge: String {
        if ageSeconds < 60 {
            return "Updated just now"
        } else if ageSeconds < 3600 {
            return "Updated \(ageSeconds / 60) min ago"
        } else {
            return "Updated \(ageSeconds / 3600) hr ago"
        }
    }
}

// MARK: - Simplified Stop Model for V2

struct StopV2: Identifiable, Codable {
    let stationCode: String
    let stationName: String
    let sequence: Int
    let scheduledArrival: Date?
    let scheduledDeparture: Date?
    let updatedArrival: Date?
    let updatedDeparture: Date?
    let actualArrival: Date?
    let actualDeparture: Date?
    let track: String?
    let rawStatus: RawStopStatus?
    let hasDepartedStation: Bool
    
    var id: String {
        "\(stationCode)-\(sequence)"
    }
    
    // Computed delay based on updated vs scheduled times
    var delayMinutes: Int {
        if let updated = updatedDeparture ?? updatedArrival,
           let scheduled = scheduledDeparture ?? scheduledArrival {
            return max(0, Int(updated.timeIntervalSince(scheduled) / 60))
        }
        return 0
    }
    
    enum CodingKeys: String, CodingKey {
        case stationCode = "station_code"
        case stationName = "station_name"
        case sequence
        case scheduledArrival = "scheduled_arrival"
        case scheduledDeparture = "scheduled_departure"
        case updatedArrival = "updated_arrival"
        case updatedDeparture = "updated_departure"
        case actualArrival = "actual_arrival"
        case actualDeparture = "actual_departure"
        case track
        case rawStatus = "raw_status"
        case hasDepartedStation = "has_departed_station"
    }
}

struct RawStopStatus: Codable {
    let amtrakStatus: String?
    let njtDepartedFlag: String?
    
    enum CodingKeys: String, CodingKey {
        case amtrakStatus = "amtrak_status"
        case njtDepartedFlag = "njt_departed_flag"
    }
}

// MARK: - Live Activity Support Extension

extension TrainV2 {
    // Convert to Live Activity attributes
    func toActivityAttributes(toStationName: String) -> TrainActivityAttributes {
        return TrainActivityAttributes(
            trainNumber: trainId,
            trainId: trainId,
            routeDescription: "\(departure.name) → \(destination)",
            origin: departure.name,
            destination: destination,
            originStationCode: departure.code,
            destinationStationCode: destinationStationCode ?? "",
            departureTime: departureTime,
            scheduledArrivalTime: getScheduledArrivalTime(toStationName: toStationName)
        )
    }
    
    // Convert to Live Activity content state with origin and destination
    func toLiveActivityContentState(from originCode: String, to destinationName: String) -> TrainActivityAttributes.ContentState {
        // Calculate context-aware progress for user's journey segment
        let progress = calculateJourneyProgress(from: originCode, to: destinationName)
        
        // Get current and next stop names based on train position
        let currentStop = trainPosition?.atStationCode ?? 
                         stops?.last(where: { $0.hasDepartedStation })?.stationName ?? 
                         departure.name
        let nextStop = trainPosition?.nextStationCode ??
                      stops?.first(where: { !$0.hasDepartedStation })?.stationName
        
        // Calculate context-aware status
        let contextStatus = calculateStatus(fromStationCode: originCode, toStationName: destinationName)
        
        // Determine if train has departed user's origin
        let hasTrainDeparted = hasTrainDepartedFromStation(originCode)
        
        // Get next stop arrival time
        let nextStopArrivalTime = getNextStopArrivalTime()
        
        return TrainActivityAttributes.ContentState(
            status: contextStatus.rawValue,
            track: track,
            currentStopName: currentStop,
            nextStopName: nextStop,
            delayMinutes: delayMinutes,
            journeyProgress: progress,
            dataTimestamp: Date().timeIntervalSince1970,
            scheduledDepartureTime: getScheduledDepartureTime(fromStationCode: originCode)?.toISO8601String(),
            scheduledArrivalTime: getScheduledArrivalTime(toStationName: destinationName)?.toISO8601String(),
            nextStopArrivalTime: nextStopArrivalTime?.toISO8601String(),
            hasTrainDeparted: hasTrainDeparted,
            originStationCode: originCode,
            destinationStationCode: destinationStationCode ?? ""
        )
    }
    
    // Convert to Live Activity content state (simple version)
    func toContentState() -> TrainActivityAttributes.ContentState {
        // Calculate overall progress
        let progress = calculateOverallProgress()
        
        // Get current and next stop names from train position
        let currentStop = trainPosition?.atStationCode ?? 
                         stops?.last(where: { $0.hasDepartedStation })?.stationName ?? 
                         departure.name
        let nextStop = trainPosition?.nextStationCode ??
                      stops?.first(where: { !$0.hasDepartedStation })?.stationName
        
        return TrainActivityAttributes.ContentState(
            status: status.rawValue,
            track: track,
            currentStopName: currentStop,
            nextStopName: nextStop,
            delayMinutes: delayMinutes,
            journeyProgress: progress,
            dataTimestamp: Date().timeIntervalSince1970,
            scheduledDepartureTime: departure.scheduledTime?.toISO8601String(),
            scheduledArrivalTime: arrival?.scheduledTime?.toISO8601String(),
            nextStopArrivalTime: getNextStopArrivalTime()?.toISO8601String(),
            hasTrainDeparted: hasTrainDepartedFromStation(originStationCode),
            originStationCode: originStationCode,
            destinationStationCode: destinationStationCode ?? ""
        )
    }
    
    // MARK: - Helper Methods for Live Activities
    
    // Calculate journey progress for a specific origin-destination segment
    func calculateJourneyProgress(from originCode: String, to destinationName: String) -> Double {
        guard let stops = stops else { return 0.0 }
        
        // Find origin and destination stops
        let originIndex = stops.firstIndex { $0.stationCode == originCode }
        let destinationIndex = stops.lastIndex { $0.stationName.lowercased().contains(destinationName.lowercased()) }
        
        guard let fromIndex = originIndex, let toIndex = destinationIndex, fromIndex < toIndex else {
            return 0.0
        }
        
        // Get the journey segment stops
        let journeyStops = Array(stops[fromIndex...toIndex])
        let completedInSegment = journeyStops.filter { $0.hasDepartedStation }.count
        
        return Double(completedInSegment) / Double(journeyStops.count)
    }
    
    // Convenience method using JourneyContext
    func calculateJourneyProgress(for context: JourneyContext) -> Double {
        guard let destinationName = context.destinationName else { return calculateOverallProgress() }
        return calculateJourneyProgress(from: context.originStationCode, to: destinationName)
    }
    
    // Calculate overall train progress (all stops)
    func calculateOverallProgress() -> Double {
        guard let stops = stops, !stops.isEmpty else { return 0.0 }
        
        let departedCount = stops.filter { $0.hasDepartedStation }.count
        return Double(departedCount) / Double(stops.count)
    }
    
    /// Get the next stop arrival time
    private func getNextStopArrivalTime() -> Date? {
        // Find the next non-departed stop
        if let stops = stops {
            // Find first stop that hasn't departed
            for stop in stops {
                if !stop.hasDepartedStation {
                    return stop.updatedArrival ?? stop.scheduledArrival
                }
            }
        }
        
        return nil
    }
}