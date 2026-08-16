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
    // `departure` and `isCancelled` are mutable so applyingLiveActivityState
    // can overlay fresher pushed Live Activity facts onto cached data.
    var departure: StationTiming
    let arrival: StationTiming?
    let trainPosition: TrainPosition?
    let dataFreshness: DataFreshness?
    let observationType: String?
    var isCancelled: Bool
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
    
    // Best-known departure time at the origin: actual > updated > scheduled.
    // Preferring actualTime once set keeps the displayed time honest after
    // the train has physically departed, even when the upstream API
    // continues to publish a stale delayed-departure estimate.
    var departureTime: Date {
        departure.actualTime ?? departure.updatedTime ?? departure.scheduledTime ?? Date()
    }
    
    var track: String? {
        guard !TrainSystem.noTrackDisplaySources.contains(dataSource) else { return nil }
        return departure.track
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
    
    // Enhanced display status using train position (empty when no position data)
    var enhancedDisplayStatus: String {
        if let position = trainPosition {
            if let nextStation = position.nextStationCode {
                return "En Route to \(nextStation)"
            } else if let atStation = position.atStationCode {
                return "At \(atStation)"
            }
        }
        return ""
    }
    
    // Check if train is boarding at user's origin (requires journey context)
    func isBoarding(fromStationCode: String) -> Bool {
        // Check if train is at the user's origin station
        if let position = trainPosition,
           Stations.areEquivalentStations(position.atStationCode ?? "", fromStationCode) {
            // Check if train has departed from this station
            if let stop = stops?.first(where: { Stations.areEquivalentStations($0.stationCode, fromStationCode) }) {
                return !stop.hasDepartedStation
            }
        }
        return false
    }
    
    // Track-based boarding detection with time window - works for both NJ Transit and Amtrak
    func isBoardingAtStation(_ stationCode: String) -> Bool {
        guard let stop = stops?.first(where: { Stations.areEquivalentStations($0.stationCode, stationCode) }) else {
            return false
        }

        // Must have track assigned and not yet departed
        guard stop.track != nil && !stop.hasDepartedStation else {
            return false
        }

        // Only show boarding within 15 minutes of departure (some stations assign tracks far in advance).
        // Use the NJT-inversion-safe live estimate (see StopV2.liveEstimatedDeparture) so a delayed
        // intermediate stop measures the window against the real estimated departure, not the schedule
        // sitting in updated_departure — otherwise a train delayed well beyond 15 min still shows boarding.
        guard let departureTime = stop.liveEstimatedDeparture ?? stop.scheduledDeparture else {
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
        
        // Check for delays
        if delayMinutes > 0 {
            return .delayed
        }

        // SCHEDULED trains have no real-time observation, so we can't claim on-time.
        // Surface .scheduled rather than implying confirmed on-time status.
        if observationType == "SCHEDULED" {
            return .scheduled
        }

        return .onTime
    }
    
    // Convenience method using JourneyContext
    func calculateStatus(for context: JourneyContext) -> TrainStatus {
        return calculateStatus(fromStationCode: context.originStationCode, toStationName: context.destinationName)
    }
    
    // Check if train has departed from a specific station
    func hasTrainDepartedFromStation(_ stationCode: String) -> Bool {
        if let stop = stops?.first(where: { Stations.areEquivalentStations($0.stationCode, stationCode) }) {
            return stop.hasDepartedStation
        }
        return false
    }
    
    /// Index of the stop that is genuinely this journey's terminal *and* whose
    /// provider needs the #1492 turnaround exemption, or nil when neither
    /// holds. The iOS twin of the backend's `utils/train.terminal_stop_index`.
    ///
    /// Only NJT gets an index: for every other provider both `updated_*` fields
    /// are genuine live estimates and the later one is the dwell-end departure,
    /// so exempting the terminal would discard real data.
    ///
    /// The positional guard mirrors the backend's. There, an unsequenced stop
    /// (NJT discovery/schedule rows before full collection) sorts last and
    /// `terminal_station_code` is still an origin placeholder, so trusting
    /// `stops.last` would skip the `max()` at an ordinary intermediate stop and
    /// re-expose the raw scheduled `DEP_TIME` — hiding that stop's delay. Those
    /// rows reach the client as `stop_sequence = 0` (`api/trains.py` coalesces
    /// the null) still sorted to the end, so requiring the last stop to hold
    /// the strict maximum sequence rejects exactly that shape. Matching
    /// `destinationStationCode` is the second half of the backend's test.
    static func njtTerminalStopIndex(
        dataSource: String,
        stops: [StopV2]?,
        destinationStationCode: String?
    ) -> Int? {
        guard dataSource == TrainSystem.njt.dataSource,
              let stops,
              let last = stops.last,
              let destination = destinationStationCode,
              Stations.areEquivalentStations(last.stationCode, destination),
              stops.dropLast().allSatisfy({ $0.sequence < last.sequence })
        else { return nil }
        return stops.count - 1
    }

    /// Whether `stop` is this journey's NJT terminal (see `njtTerminalStopIndex`).
    func isNJTTerminal(_ stop: StopV2) -> Bool {
        guard let index = TrainV2.njtTerminalStopIndex(
            dataSource: dataSource,
            stops: stops,
            destinationStationCode: destinationStationCode
        ), let stops else { return false }
        return stops[index].id == stop.id
    }

    /// Best known departure at `stop`, with NJT's terminal turnaround excluded.
    ///
    /// `StopV2.bestKnownDeparture` cannot make this call — it has neither
    /// `dataSource` nor the journey's terminal — so at an NJT terminal it hands
    /// back `max(updatedDeparture, updatedArrival)`, which is the later
    /// turnaround departure whenever NJT publishes one. Rendered as a departure
    /// that is the #1492 complaint on a different row: a fabricated `+Nm delay`
    /// on a train that arrived on time, and a `minutesSinceDeparture` clamped
    /// to 0 long after the train actually left (issue #1799).
    func bestKnownDeparture(at stop: StopV2) -> Date? {
        stop.actualDeparture
            ?? StopV2.liveEstimatedDeparture(
                updatedDeparture: stop.updatedDeparture,
                updatedArrival: stop.updatedArrival,
                isNJTTerminal: isNJTTerminal(stop)
            )
            ?? stop.scheduledDeparture
    }

    // Get departure time from a specific station (see StopV2.bestKnownDeparture
    // for why the live estimate sits between the actual and the schedule).
    func getDepartureTime(fromStationCode: String) -> Date? {
        if Stations.areEquivalentStations(fromStationCode, originStationCode) {
            return departureTime
        }

        if let stop = stops?.first(where: { Stations.areEquivalentStations($0.stationCode, fromStationCode) }) {
            return bestKnownDeparture(at: stop)
        }
        return nil
    }
    
    // Get scheduled departure time from a specific station
    func getScheduledDepartureTime(fromStationCode: String) -> Date? {
        if Stations.areEquivalentStations(fromStationCode, originStationCode) {
            return departure.scheduledTime
        }

        // Find departure from stops if available
        return stops?.first { Stations.areEquivalentStations($0.stationCode, fromStationCode) }?.scheduledDeparture
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
               Stations.areEquivalentStations($0.stationCode, toStationCode)
           }) {
            return destinationStop.scheduledArrival
        }
        // Fallback to train's final destination if station not found
        return arrival?.scheduledTime
    }

    // Get estimated (delay-adjusted) departure time from a specific station.
    // Uses the NJT-inversion-safe live estimate (see StopV2.liveEstimatedDeparture)
    // and falls back to the schedule when no live estimate is available.
    func getEstimatedDepartureTime(fromStationCode: String) -> Date? {
        if let stop = stops?.first(where: { Stations.areEquivalentStations($0.stationCode, fromStationCode) }) {
            return stop.liveEstimatedDeparture ?? stop.scheduledDeparture
        }
        // Fallback for origin station
        if Stations.areEquivalentStations(fromStationCode, originStationCode) {
            return departure.updatedTime ?? departure.scheduledTime
        }
        return nil
    }

    // Get estimated (delay-adjusted) arrival time at specific destination station
    // Returns updatedArrival if available, otherwise falls back to scheduledArrival
    func getEstimatedArrivalTime(toStationCode: String) -> Date? {
        if let stops = stops,
           let destinationStop = stops.first(where: {
               Stations.areEquivalentStations($0.stationCode, toStationCode)
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
    
    // Check if train is departing soon (within specified minutes).
    // Allows a 5-minute grace period past the departure time so that
    // boarding indicators remain visible for delayed trains that are
    // still at the station. The actual departure is gated separately
    // by hasDepartedStation in isBoardingAtStation.
    func isDepartingSoon(fromStationCode: String, withinMinutes: Int = 11) -> Bool {
        guard let departureTime = getDepartureTime(fromStationCode: fromStationCode) else {
            return false
        }

        let now = Date()
        let timeUntilDeparture = departureTime.timeIntervalSince(now)

        // Show from withinMinutes before departure until 5 minutes after
        // (train may still be at station if delayed or waiting)
        return timeUntilDeparture > -300 && timeUntilDeparture <= Double(withinMinutes * 60)
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
        if let stop = stops?.first(where: { Stations.areEquivalentStations($0.stationCode, fromStationCode) }),
           let actualDeparture = stop.actualDeparture {
            return actualDeparture < now
        }

        // Third priority: Check station timing actual time (for origin station)
        if Stations.areEquivalentStations(fromStationCode, originStationCode),
           let actualDeparture = departure.actualTime {
            return actualDeparture < now
        }
        
        // Fallback: Use best available departure time with buffer
        if let scheduledDeparture = getDepartureTime(fromStationCode: fromStationCode) {
            // Allow 1 minute past departure time for late boarding
            let departureWithBuffer = scheduledDeparture.addingTimeInterval(1 * 60)
            return departureWithBuffer < now
        }
        
        // If no departure time available, don't filter out (safe default)
        return false
    }

    /// Returns minutes since departure from the specified station, or nil if train hasn't departed
    func minutesSinceDeparture(fromStationCode: String) -> Int? {
        guard hasAlreadyDeparted(fromStationCode: fromStationCode) else { return nil }

        // Best-known departure time: actual > live estimate > scheduled.
        // Skipping the live estimate here fell straight from a missing actual
        // to the schedule, so a delayed departed stop (actual withheld by the
        // server per issue #1768) computed minutes-ago from the timetable and
        // instantly lost filterUpcomingTrains' 10-minute grace window.
        let departureTime: Date?
        if let stop = stops?.first(where: { Stations.areEquivalentStations($0.stationCode, fromStationCode) }) {
            departureTime = bestKnownDeparture(at: stop)
        } else if Stations.areEquivalentStations(fromStationCode, originStationCode) {
            departureTime = departure.actualTime ?? departure.updatedTime ?? departure.scheduledTime
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
    // Mutable so applyingLiveActivityState can adopt a track assignment pushed
    // to the Live Activity after the cached train data was written.
    var track: String?
    
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
    // `track` and `hasDepartedStation` are mutable so applyingLiveActivityState
    // can overlay fresher pushed Live Activity facts onto cached data.
    var track: String?
    let rawStatus: RawStopStatus?
    var hasDepartedStation: Bool
    
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

    /// Live estimated departure that survives NJT's TIME/DEP_TIME inversion.
    ///
    /// NJT persists `updated_departure = DEP_TIME` (the immutable schedule) and
    /// `updated_arrival = TIME` (the live delayed estimate) at intermediate
    /// stops, so a plain `updatedDeparture ?? updatedArrival` picks the
    /// schedule and reports 0 delay. Taking the later of the two when both are
    /// populated recovers the live estimate for NJT and stays correct for
    /// other providers (where the later value is the dwell-end departure,
    /// matching what `services/departure.py` returns to `/api/v2/trains/
    /// departures`). Today the server normalizes NJT updated_* in PR #1271, so
    /// this method is defensive belt-and-suspenders, but it keeps the contract
    /// correct-by-construction independent of any single server endpoint.
    ///
    /// The `max()` is correct at intermediate stops and wrong at an NJT
    /// **terminal**, which is what `isNJTTerminal` exists for. The train does
    /// not continue onward there, so `DEP_TIME` is not a live departure
    /// estimate — NJT can populate it with a later *turnaround* departure, and
    /// the server deliberately hands the raw pair through at that stop
    /// (`utils/train.effective_njt_updated_times` with `is_terminal=True`, the
    /// #1492 exemption) precisely so the `max()` is not applied. Callers that
    /// know the stop's position must say so; the caller that cannot is
    /// `StopV2` itself, which carries neither `dataSource` nor the journey's
    /// terminal — hence `TrainV2.bestKnownDeparture(at:)` (issue #1799).
    ///
    /// At the terminal the live reading is `TIME` (`updatedArrival`) alone,
    /// with no fall back to `updatedDeparture`: the entire point is that that
    /// value belongs to the next run, not this one.
    static func liveEstimatedDeparture(
        updatedDeparture: Date?,
        updatedArrival: Date?,
        isNJTTerminal: Bool = false
    ) -> Date? {
        if isNJTTerminal {
            return updatedArrival
        }
        switch (updatedDeparture, updatedArrival) {
        case let (departure?, arrival?):
            return max(departure, arrival)
        case let (departure?, nil):
            return departure
        case let (nil, arrival?):
            return arrival
        case (nil, nil):
            return nil
        }
    }

    /// Live estimated departure for this stop (see `liveEstimatedDeparture`).
    ///
    /// Terminal-unaware by construction — `StopV2` cannot tell whether it is a
    /// journey's terminal. Anything rendering a *departure* at a stop that
    /// might be one wants `TrainV2.bestKnownDeparture(at:)` instead.
    var liveEstimatedDeparture: Date? {
        StopV2.liveEstimatedDeparture(
            updatedDeparture: updatedDeparture,
            updatedArrival: updatedArrival
        )
    }

    /// Best known departure time for this stop: a real observation when we have
    /// one, else the live estimate, else the timetable.
    ///
    /// `actualDeparture` wins once set so a departed train stops showing the
    /// pre-departure estimate, which sometimes lingers in the upstream API for
    /// hours after the train left on time. The live estimate has to sit between
    /// the two rather than being skipped: falling straight from a missing
    /// actual to `scheduledDeparture` presents the timetable as though it were
    /// what happened, so the row renders a late train as on time — the display
    /// half of issue #1768, which the server's `resolve_actual_departure` fix
    /// would otherwise expose more often by (correctly) leaving
    /// `actual_departure` null rather than filling it with the schedule.
    ///
    /// Terminal-unaware, for the same reason `liveEstimatedDeparture` is: use
    /// `TrainV2.bestKnownDeparture(at:)` wherever the stop could be the
    /// journey's terminal (issue #1799).
    var bestKnownDeparture: Date? {
        actualDeparture ?? liveEstimatedDeparture ?? scheduledDeparture
    }

    // Computed delay based on the live estimated departure vs the schedule.
    var delayMinutes: Int {
        if let updated = liveEstimatedDeparture,
           let scheduled = scheduledDeparture ?? scheduledArrival {
            return max(0, Int(updated.timeIntervalSince(scheduled) / 60))
        }
        return 0
    }

    /// Formats the arrival delay badge ("+Nm delay" / "Nm early") shown on the
    /// train-detail stop row, from an arrival time vs the scheduled arrival.
    ///
    /// The `arrival` may be an *actual* arrival or a *live estimate*
    /// (`updatedArrival`): both cases must annotate the row identically so a
    /// not-yet-reached terminal or upcoming stop still shows its delay. At an
    /// NJT terminal `updatedArrival` = live TIME and `updatedDeparture` is nil,
    /// so there is no TIME/DEP_TIME inversion to undo here. Returns an empty
    /// string when on-time, roughly on-time, or either input is missing so the
    /// caller can suppress the badge. Pure and testable.
    static func arrivalDelayBadge(arrival: Date?, scheduledArrival: Date?) -> String {
        guard let arrival = arrival, let scheduledArrival = scheduledArrival else { return "" }
        let delayMinutes = Int(arrival.timeIntervalSince(scheduledArrival) / 60)
        if delayMinutes > 0 {
            return "+\(delayMinutes)m delay"
        } else if delayMinutes < -1 {
            return "\(abs(delayMinutes))m early"
        }
        return "" // Don't show anything for on-time or 1 minute early
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
        
        // Get current and next stop based on train position
        let currentStop = trainPosition?.atStationCode ??
                         stops?.last(where: { $0.hasDepartedStation })?.stationName ??
                         departure.name
        let nextStopObj = stops?.first(where: { !$0.hasDepartedStation })
        let nextStop = trainPosition?.nextStationCode ?? nextStopObj?.stationName
        let nextStopCode = nextStopObj?.stationCode

        // Calculate context-aware status
        let contextStatus = calculateStatus(fromStationCode: originCode, toStationName: destinationName)

        // Determine if train has departed user's origin
        let hasTrainDeparted = hasTrainDepartedFromStation(originCode)

        // Get next stop arrival time
        let nextStopArrivalTime = getNextStopArrivalTime()

        // Only surface the predicted track when there is no actual track yet
        let (predictedTrackValue, predictedTrackConfidenceValue): (String?, Double?) = {
            guard track == nil || track?.isEmpty == true,
                  let prediction = trackPrediction,
                  !prediction.primaryPrediction.isEmpty else {
                return (nil, nil)
            }
            return (prediction.primaryPrediction, prediction.confidence)
        }()

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
            nextStopCode: nextStopCode,
            hasTrainDeparted: hasTrainDeparted,
            predictedTrack: predictedTrackValue,
            predictedTrackConfidence: predictedTrackConfidenceValue,
            originStationCode: originCode,
            destinationStationCode: destinationStationCode ?? ""
        )
    }

    /// Overlays fresher pushed Live Activity state onto (typically cached) train data.
    ///
    /// APNs keeps updating the Live Activity while the app is suspended, so after the
    /// app returns from the background the pushed ContentState is often newer than any
    /// cached train — and when the network is unavailable it is the freshest train data
    /// on the device. The push carries no stops array, only scalar facts, so this
    /// applies exactly those facts to the cached stops: stops the train has passed,
    /// the origin track assignment, and cancellation. Times keep their cached values.
    ///
    /// Returns self unchanged when the pushed state is not newer than `dataAsOf`
    /// (the time the cached data was fetched).
    func applyingLiveActivityState(
        _ state: TrainActivityAttributes.ContentState,
        ifNewerThan dataAsOf: Date
    ) -> TrainV2 {
        guard state.dataTimestamp > dataAsOf.timeIntervalSince1970 else { return self }
        var updated = self

        // Mark stops the train has passed since the cache was written. The push's
        // nextStopCode is the first stop not yet departed within the user's journey
        // segment, so once the train has left the user's origin every stop before
        // it has been departed. Two combinations carry no trustworthy "stops
        // passed" information and must mark nothing:
        // - hasTrainDeparted false: the train may still be short of the origin,
        //   where stops before nextStopCode aren't departed yet.
        // - nextStopCode == the activity's origin: the backend only produces this
        //   when the origin stop's departed flag is unset, so hasTrainDeparted is
        //   its schedule-time fallback (scheduled departure in the past), not an
        //   observation — the train is likely overdue at or short of the origin,
        //   and marking anything departed would misstate an unobserved fact.
        if state.hasTrainDeparted,
           let nextStopCode = state.nextStopCode,
           let activityOriginCode = state.originStationCode,
           !Stations.areEquivalentStations(nextStopCode, activityOriginCode),
           var stops = updated.stops,
           let nextIndex = stops.firstIndex(where: {
               Stations.areEquivalentStations($0.stationCode, nextStopCode)
           }) {
            for index in stops.indices where index < nextIndex {
                stops[index].hasDepartedStation = true
            }
            updated.stops = stops
        }

        // Adopt a track assignment pushed after the cache was written. The pushed
        // track is for the activity's origin station, so only apply it there.
        if let track = state.track, !track.isEmpty,
           let originCode = state.originStationCode {
            if Stations.areEquivalentStations(updated.departure.code, originCode) {
                updated.departure.track = track
            }
            if var stops = updated.stops,
               let originIndex = stops.firstIndex(where: {
                   Stations.areEquivalentStations($0.stationCode, originCode)
               }) {
                stops[originIndex].track = track
                updated.stops = stops
            }
        }

        // Cancellation is the one status worth trusting immediately — it changes
        // what the user should do next. Other statuses are derived client-side
        // from the (now overlaid) stops, so they need no explicit copy.
        if state.status == TrainStatus.cancelled.rawValue {
            updated.isCancelled = true
        }

        return updated
    }

    // MARK: - Helper Methods for Live Activities

    // Calculate journey progress for a specific origin-destination segment
    func calculateJourneyProgress(from originCode: String, toCode destinationCode: String) -> Double {
        guard let stops = stops else { return 0.0 }

        // Find origin and destination stops by station CODE (reliable)
        let originIndex = stops.firstIndex { Stations.areEquivalentStations($0.stationCode, originCode) }
        let destinationIndex = stops.firstIndex { Stations.areEquivalentStations($0.stationCode, destinationCode) }
        
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
        case "MBTA":
            return "MBTA"
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
    /// or just the destination for other synthetic-ID sources (PATH, LIRR, MNR, PATCO).
    /// SCHEDULED trains show "Train TBD" since their IDs are unconfirmed schedule data.
    var displayLabel: String {
        if dataSource == "SUBWAY" {
            return "(\(line.code)) \(destination)"
        }
        if usesSyntheticTrainId {
            return destination
        }
        return observationType == "SCHEDULED" ? "Train TBD" : "Train \(trainId)"
    }

    /// User-facing label without the parenthetical line code that `displayLabel`
    /// embeds for subway. Use this when the line is rendered separately (e.g.,
    /// next to a `SubwayLineChips` bullet); otherwise use `displayLabel`.
    var displayDestination: String {
        return dataSource == "SUBWAY" ? destination : displayLabel
    }

    /// True when displayLabel returns "Train TBD" — a scheduled-only train
    /// from a provider that uses public train numbers (NJT, Amtrak).
    var hasUnconfirmedTrainNumber: Bool {
        return observationType == "SCHEDULED"
            && dataSource != "SUBWAY"
            && !usesSyntheticTrainId
    }
}
