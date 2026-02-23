import Foundation

// MARK: - Journey Context
// Represents the user's journey segment for context-aware calculations
struct JourneyContext {
    let originStationCode: String
    let destinationStationCode: String?
    let destinationName: String?  // Keep for display purposes

    init(from originCode: String, toCode destinationCode: String? = nil, toName destinationName: String? = nil) {
        self.originStationCode = originCode
        self.destinationStationCode = destinationCode
        self.destinationName = destinationName
    }
}

// MARK: - Pure Data Train Model for Backend V2
// This model uses the pure data approach where the backend provides
// objective facts and the iOS client calculates context-aware status

struct TrainV2: Identifiable, Codable {
    // Core fields
    var id: String {
        // Combine trainId + departure station + scheduled time for uniqueness
        let timeString = departure.scheduledTime?.timeIntervalSince1970.description ?? "0"
        return "\(trainId)-\(departure.code)-\(timeString)"
    }
    let trainId: String
    let journeyDate: Date?
    let line: LineInfo
    let destination: String
    let departure: StationTiming
    let arrival: StationTiming?
    let trainPosition: TrainPosition?
    let dataFreshness: DataFreshness?
    let observationType: String?
    let isCancelled: Bool
    let cancellationReason: String?
    let isCompleted: Bool
    let dataSource: String

    // Optional detailed stops (populated from detail endpoint)
    var stops: [StopV2]? = nil

    // Inline track prediction from train details endpoint (populated when track is unassigned)
    var trackPrediction: V2TrackPrediction? = nil

    enum CodingKeys: String, CodingKey {
        case trainId = "train_id"
        case journeyDate = "journey_date"
        case line
        case destination
        case departure
        case arrival
        case trainPosition = "train_position"
        case dataFreshness = "data_freshness"
        case observationType = "observation_type"
        case isCancelled = "is_cancelled"
        case cancellationReason = "cancellation_reason"
        case isCompleted = "is_completed"
        case dataSource = "data_source"
        case stops
        case trackPrediction = "track_prediction"
    }
    
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
    
    // Track prediction data - now handled async in UI components
    var predictionData: PredictionData? {
        // Predictions are now fetched asynchronously using DynamicTrackPredictionService
        // UI components should call DynamicTrackPredictionService.shared.getPrediction(for:) directly
        return nil
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
    
    // Track-based boarding detection with time window - works for both NJ Transit and Amtrak
    func isBoardingAtStation(_ stationCode: String) -> Bool {
        guard let stop = stops?.first(where: { $0.stationCode == stationCode }) else {
            return false
        }

        // Must have track assigned and not yet departed
        guard stop.track != nil && !stop.hasDepartedStation else {
            return false
        }

        // Only show boarding within 15 minutes of departure (some stations assign tracks far in advance)
        guard let departureTime = stop.updatedDeparture ?? stop.scheduledDeparture else {
            return false
        }

        let minutesUntilDeparture = departureTime.timeIntervalSinceNow / 60
        return minutesUntilDeparture <= 15
    }
    
    // MARK: - Helper Methods
    
    // Calculate context-aware status based on user's journey
    func calculateStatus(fromStationCode: String, toStationName: String? = nil) -> TrainStatus {
        // Cancelled takes precedence over all other statuses
        if isCancelled {
            return .cancelled
        }
        
        // Check if train has departed from user's origin
        if hasTrainDepartedFromStation(fromStationCode) {
            return .departed
        }
        
        // Check if train is at user's origin and boarding
        if isBoarding(fromStationCode: fromStationCode) {
            return .boarding
        }
        
        // SCHEDULED trains have no confirmed real-time data —
        // don't claim "on time" when we don't actually know.
        if observationType == "SCHEDULED" {
            return .scheduled
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
    
    // Get scheduled arrival time at destination
    func getScheduledArrivalTime() -> Date? {
        // API already filtered for correct destination
        return arrival?.scheduledTime
    }
    
    // Get scheduled arrival time at specific destination station by CODE (reliable)
    func getScheduledArrivalTime(toStationCode: String) -> Date? {
        if let stops = stops,
           let destinationStop = stops.first(where: {
               $0.stationCode.uppercased() == toStationCode.uppercased()
           }) {
            return destinationStop.scheduledArrival
        }
        // Fallback to train's final destination if station not found
        return arrival?.scheduledTime
    }

    // Get scheduled arrival time at specific destination station by NAME (legacy, less reliable)
    @available(*, deprecated, message: "Use getScheduledArrivalTime(toStationCode:) instead for reliable matching")
    func getScheduledArrivalTime(toStationName: String) -> Date? {
        // Look up the specific station in stops array
        if let stops = stops,
           let destinationStop = stops.first(where: {
               $0.stationName.lowercased().contains(toStationName.lowercased())
           }) {
            return destinationStop.scheduledArrival
        }

        // Fallback to train's final destination if station not found
        return arrival?.scheduledTime
    }

    // Get estimated (delay-adjusted) departure time from a specific station
    // Returns updatedDeparture if available, otherwise falls back to scheduledDeparture
    func getEstimatedDepartureTime(fromStationCode: String) -> Date? {
        if let stop = stops?.first(where: { $0.stationCode.uppercased() == fromStationCode.uppercased() }) {
            return stop.updatedDeparture ?? stop.scheduledDeparture
        }
        // Fallback for origin station
        if fromStationCode.uppercased() == originStationCode.uppercased() {
            return departure.updatedTime ?? departure.scheduledTime
        }
        return nil
    }

    // Get estimated (delay-adjusted) arrival time at specific destination station
    // Returns updatedArrival if available, otherwise falls back to scheduledArrival
    func getEstimatedArrivalTime(toStationCode: String) -> Date? {
        if let stops = stops,
           let destinationStop = stops.first(where: {
               $0.stationCode.uppercased() == toStationCode.uppercased()
           }) {
            return destinationStop.updatedArrival ?? destinationStop.scheduledArrival
        }
        // Fallback to train's final destination if station not found
        return arrival?.updatedTime ?? arrival?.scheduledTime
    }
    
    // Get formatted departure time for display
    func getFormattedDepartureTime(fromStationCode: String) -> String {
        guard let time = getDepartureTime(fromStationCode: fromStationCode) else {
            return "--:--"
        }
        // PERFORMANCE: Use cached static formatter instead of creating new one each call
        return DateFormatter.easternTimeShort.string(from: time)
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
    
    // Check if train has already departed from the specified station
    func hasAlreadyDeparted(fromStationCode: String) -> Bool {
        // Cancelled trains never physically departed — keep them visible
        if isCancelled { return false }

        let now = Date()
        
        // First priority: Use existing stop data method (most accurate)
        if hasTrainDepartedFromStation(fromStationCode) {
            return true
        }
        
        // Second priority: Check actual departure time from stop data
        if let stop = stops?.first(where: { $0.stationCode == fromStationCode }),
           let actualDeparture = stop.actualDeparture {
            return actualDeparture < now
        }
        
        // Third priority: Check station timing actual time (for origin station)
        if fromStationCode == originStationCode,
           let actualDeparture = departure.actualTime {
            return actualDeparture < now
        }
        
        // Fallback: Use scheduled time with buffer for delays
        if let scheduledDeparture = getDepartureTime(fromStationCode: fromStationCode) {
            // Allow 1 minute past scheduled time for delays/late boarding
            let departureWithBuffer = scheduledDeparture.addingTimeInterval(1 * 60)
            return departureWithBuffer < now
        }
        
        // If no departure time available, don't filter out (safe default)
        return false
    }

    /// Returns minutes since departure from the specified station, or nil if train hasn't departed
    func minutesSinceDeparture(fromStationCode: String) -> Int? {
        guard hasAlreadyDeparted(fromStationCode: fromStationCode) else { return nil }

        // Get the actual or scheduled departure time
        let departureTime: Date?
        if let stop = stops?.first(where: { $0.stationCode == fromStationCode }) {
            departureTime = stop.actualDeparture ?? stop.scheduledDeparture
        } else if fromStationCode == originStationCode {
            departureTime = departure.actualTime ?? departure.scheduledTime
        } else {
            departureTime = nil
        }

        guard let depTime = departureTime else { return 0 }
        return max(0, Int(Date().timeIntervalSince(depTime) / 60))
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
    
    // Prediction fields
    let predictedArrival: Date?
    let predictedArrivalSamples: Int?
    
    var id: String {
        "\(stationCode)-\(sequence)"
    }
    
    /// The most accurate arrival time available: actual > updated > scheduled.
    var bestKnownArrival: Date? {
        actualArrival ?? updatedArrival ?? scheduledArrival
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
        case predictedArrival = "predicted_arrival"
        case predictedArrivalSamples = "predicted_arrival_samples"
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
    // Convert to Live Activity content state with origin and destination
    func toLiveActivityContentState(from originCode: String, toCode destinationCode: String, toName destinationName: String) -> TrainActivityAttributes.ContentState {
        // Calculate context-aware progress for user's journey segment
        let progress = calculateJourneyProgress(from: originCode, toCode: destinationCode)
        
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
            scheduledDepartureTime: getEstimatedDepartureTime(fromStationCode: originCode)?.toISO8601String(),
            scheduledArrivalTime: getEstimatedArrivalTime(toStationCode: destinationCode)?.toISO8601String(),
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
            scheduledDepartureTime: getEstimatedDepartureTime(fromStationCode: originStationCode)?.toISO8601String(),
            scheduledArrivalTime: getEstimatedArrivalTime(toStationCode: destinationStationCode ?? "")?.toISO8601String(),
            nextStopArrivalTime: getNextStopArrivalTime()?.toISO8601String(),
            hasTrainDeparted: hasTrainDepartedFromStation(originStationCode),
            originStationCode: originStationCode,
            destinationStationCode: destinationStationCode ?? ""
        )
    }
    
    // MARK: - Helper Methods for Live Activities
    
    // Calculate journey progress for a specific origin-destination segment
    func calculateJourneyProgress(from originCode: String, toCode destinationCode: String) -> Double {
        guard let stops = stops else { return 0.0 }

        // Find origin and destination stops by station CODE (reliable)
        let originIndex = stops.firstIndex { $0.stationCode.uppercased() == originCode.uppercased() }
        let destinationIndex = stops.firstIndex { $0.stationCode.uppercased() == destinationCode.uppercased() }
        
        guard let fromIndex = originIndex, let toIndex = destinationIndex, fromIndex < toIndex else {
            return 0.0
        }
        
        // Get the journey segment stops
        let journeyStops = Array(stops[fromIndex...toIndex])
        let destinationStop = journeyStops.last
        
        // Check if destination is the train's terminal station
        let isDestinationTerminal = (toIndex == stops.count - 1)
        
        // Journey is complete when:
        // - For terminal stations: train has arrived
        // - For intermediate stations: train has departed
        let hasCompletedJourney = isDestinationTerminal ? 
            (destinationStop?.actualArrival != nil || trainPosition?.atStationCode == destinationStop?.stationCode) :
            (destinationStop?.hasDepartedStation == true)
        
        if hasCompletedJourney {
            return 1.0  // Journey complete
        }
        
        // Calculate progress based on completed segments (exclude destination from denominator)
        let stopsBeforeDestination = Array(journeyStops.dropLast())
        let completedStops = stopsBeforeDestination.filter { $0.hasDepartedStation }.count
        let totalSegments = max(1, journeyStops.count - 1)  // Number of segments between stops
        
        return Double(completedStops) / Double(totalSegments)
    }
    
    // Convenience method using JourneyContext
    func calculateJourneyProgress(for context: JourneyContext) -> Double {
        guard let destinationCode = context.destinationStationCode else { return calculateOverallProgress() }
        return calculateJourneyProgress(from: context.originStationCode, toCode: destinationCode)
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
    
    // MARK: - Express Train Identification
    
    /// Calculate travel time between origin and destination
    func getTravelTime() -> TimeInterval {
        // Use departure time from origin station
        let departureTime = departure.scheduledTime ?? Date()
        
        // Use arrival time at destination - API already filtered for correct destination
        if let arrivalTime = arrival?.scheduledTime {
            return arrivalTime.timeIntervalSince(departureTime)
        }
        
        return 0
    }
    
    /// Get the train class display name for the data source
    var trainClass: String {
        switch dataSource {
        case "AMTRAK":
            return "Amtrak"
        case "PATH":
            return "PATH"
        case "PATCO":
            return "PATCO"
        case "LIRR":
            return "LIRR"
        case "MNR":
            return "Metro-North"
        case "SUBWAY":
            return "NYC Subway"
        default:
            return "NJ Transit"
        }
    }

    /// Check if this is a schedule-only data source (no real-time data available)
    var isScheduleOnly: Bool {
        return dataSource == "PATCO"
    }

    /// Whether this train uses synthetic IDs (not user-friendly numeric train numbers)
    /// PATH, PATCO, LIRR, MNR, and SUBWAY use GTFS-derived IDs rather than public train numbers
    var usesSyntheticTrainId: Bool {
        return TrainSystem.syntheticTrainIdSources.contains(dataSource)
    }

    /// User-facing label: "Train 3254" for NJT/Amtrak, "(N) Astoria-Ditmars Blvd" for subway,
    /// or just the destination for other synthetic-ID sources (PATH, LIRR, MNR, PATCO)
    var displayLabel: String {
        if dataSource == "SUBWAY" {
            return "(\(line.code)) \(destination)"
        }
        return usesSyntheticTrainId ? destination : "Train \(trainId)"
    }
}