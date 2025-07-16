import Foundation

// MARK: - Simplified Train Model for Backend V2
// This model is designed to work with the backend_v2 API structure
// without consolidation or ML predictions

struct TrainV2: Identifiable, Codable {
    // Core fields
    let id: Int  // Generated from trainId.hashValue for Identifiable
    let trainId: String
    let line: LineInfo
    let destination: String
    let departure: StationTiming
    let arrival: StationTiming?
    let journey: JourneyInfo?
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
        mapV2StatusToTrainStatus(departure.status ?? "SCHEDULED")
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
    
    // Enhanced display status using journey progress
    var enhancedDisplayStatus: String {
        if let progress = journey?.progress {
            if progress.percentage >= 100 {
                return "Arrived"
            } else if progress.percentage > 0 {
                return "En Route - \(progress.currentLocation)"
            }
        }
        return status.displayText
    }
    
    // Check if train is boarding
    var isBoarding: Bool {
        status == .boarding
    }
    
    // MARK: - Helper Methods
    
    private func mapV2StatusToTrainStatus(_ v2Status: String) -> TrainStatus {
        switch v2Status.uppercased() {
        case "ON_TIME": return .onTime
        case "LATE", "DELAYED": return .delayed
        case "BOARDING", "ALL_ABOARD": return .boarding
        case "DEPARTED", "IN_TRANSIT": return .departed
        case "CANCELLED": return .delayed  // Map cancelled to delayed for now
        case "ARRIVED": return .departed  // Map arrived to departed for now
        default: return .scheduled
        }
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

struct JourneyInfo: Codable {
    let origin: String
    let originName: String
    let durationMinutes: Int
    let stopsBetween: Int
    let progress: JourneyProgressV2
    
    enum CodingKeys: String, CodingKey {
        case origin
        case originName = "origin_name"
        case durationMinutes = "duration_minutes"
        case stopsBetween = "stops_between"
        case progress
    }
}

struct JourneyProgressV2: Codable {
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
    let actualArrival: Date?
    let actualDeparture: Date?
    let estimatedArrival: Date?
    let estimatedDeparture: Date?
    let track: String?
    let status: String?
    let delayMinutes: Int
    let departed: Bool
    
    var id: String {
        "\(stationCode)-\(sequence)"
    }
    
    enum CodingKeys: String, CodingKey {
        case stationCode = "station_code"
        case stationName = "station_name"
        case sequence
        case scheduledArrival = "scheduled_arrival"
        case scheduledDeparture = "scheduled_departure"
        case actualArrival = "actual_arrival"
        case actualDeparture = "actual_departure"
        case estimatedArrival = "estimated_arrival"
        case estimatedDeparture = "estimated_departure"
        case track
        case status
        case delayMinutes = "delay_minutes"
        case departed
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
    func toLiveActivityContentState(from originCode: String, to destinationName: String, lastKnownStatusV2: String? = nil) -> TrainActivityAttributes.ContentState {
        // Calculate simple progress (0.0 to 1.0)
        var progress = 0.0
        if let stops = stops {
            let departedCount = stops.filter { $0.departed }.count
            progress = Double(departedCount) / Double(stops.count)
        }
        
        // Get current and next stop names
        let currentStop = stops?.last(where: { $0.departed })?.stationName ?? departure.name
        let nextStop = stops?.first(where: { !$0.departed })?.stationName
        
        // Determine if train has departed user's origin
        let hasTrainDeparted = self.hasTrainDeparted(fromStation: originCode)
        
        // Get next stop arrival time
        let nextStopArrivalTime = self.getNextStopArrivalTime()
        
        return TrainActivityAttributes.ContentState(
            status: status.rawValue,
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
        // Calculate simple progress (0.0 to 1.0)
        var progress = 0.0
        if let stops = stops {
            let departedCount = stops.filter { $0.departed }.count
            progress = Double(departedCount) / Double(stops.count)
        } else if let journey = journey {
            progress = Double(journey.progress.percentage) / 100.0
        }
        
        // Get current and next stop names
        let currentStop = stops?.last(where: { $0.departed })?.stationName ?? 
                         journey?.progress.currentLocation ?? 
                         departure.name
        let nextStop = stops?.first(where: { !$0.departed })?.stationName ?? 
                      journey?.progress.nextStop
        
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
            hasTrainDeparted: hasTrainDeparted(fromStation: originStationCode),
            originStationCode: originStationCode,
            destinationStationCode: destinationStationCode ?? ""
        )
    }
    
    // MARK: - Helper Methods for Live Activities
    
    /// Determine if train has departed from the user's origin station
    private func hasTrainDeparted(fromStation originCode: String) -> Bool {
        // Check if train has departed based on stops
        if let stops = stops {
            // Find the origin stop
            if let originStop = stops.first(where: { $0.stationCode == originCode }) {
                // Check if stop is marked as departed
                if originStop.departed {
                    return true
                }
                
                // Check if actual departure time exists and is in the past
                if let actualDeparture = originStop.actualDeparture {
                    return actualDeparture < Date()
                }
            }
        }
        
        // Check basic status
        return status == .departed || status == .onTime && departureTime < Date()
    }
    
    /// Get the next stop arrival time
    private func getNextStopArrivalTime() -> Date? {
        // Find the next non-departed stop
        if let stops = stops {
            // Find first stop that hasn't departed
            for stop in stops {
                if !stop.departed {
                    return stop.scheduledArrival ?? stop.estimatedArrival
                }
            }
        }
        
        return nil
    }
}