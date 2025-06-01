import Foundation
import ActivityKit

// MARK: - Live Activity Extensions for Train
extension Train {
    /// Calculate journey progress between origin and destination with time-based interpolation
    func calculateJourneyProgress(from originCode: String, to destinationCode: String) -> JourneyProgress {
        guard let stops = stops else { return .unknown }
        
        // Find origin and destination indices
        let originIndex = stops.firstIndex { Stations.getStationCode($0.stationName) == originCode }
        let destinationIndex = stops.firstIndex { Stations.getStationCode($0.stationName) == destinationCode }
        
        guard let fromIdx = originIndex, let toIdx = destinationIndex, fromIdx < toIdx else {
            return .unknown
        }
        
        let journeyStops = Array(stops[fromIdx...toIdx])
        let completedStops = journeyStops.filter { $0.departed }.count
        
        // Find current stop index in journey
        let currentStopIndex = journeyStops.firstIndex { !$0.departed }
        
        // Calculate interpolated progress if between stops
        var interpolatedProgress = Double(completedStops) / Double(journeyStops.count)
        
        if completedStops > 0 && completedStops < journeyStops.count {
            // Find the last departed stop and next stop
            let departedInJourney = journeyStops.filter { $0.departed }
            if let lastDeparted = departedInJourney.last,
               let lastDepartedIndex = journeyStops.firstIndex(where: { $0.stationName == lastDeparted.stationName }),
               lastDepartedIndex + 1 < journeyStops.count {
                
                let nextStop = journeyStops[lastDepartedIndex + 1]
                
                // Get departure time from last stop
                if let departureTime = lastDeparted.departureTime ?? lastDeparted.scheduledTime,
                   let arrivalTime = nextStop.scheduledTime {
                    
                    let now = Date()
                    let totalTravelTime = arrivalTime.timeIntervalSince(departureTime)
                    let elapsedTime = now.timeIntervalSince(departureTime)
                    
                    // Calculate position between stops (0.0 to 1.0)
                    let segmentProgress = min(max(elapsedTime / totalTravelTime, 0.0), 1.0)
                    
                    // Add the segment progress to the base progress
                    let baseProgress = Double(completedStops) / Double(journeyStops.count)
                    let segmentWeight = 1.0 / Double(journeyStops.count)
                    interpolatedProgress = baseProgress + (segmentProgress * segmentWeight)
                }
            }
        }
        
        return JourneyProgress(
            totalStops: journeyStops.count,
            completedStops: completedStops,
            progress: interpolatedProgress,
            currentStopIndex: currentStopIndex
        )
    }
    
    /// Determine current location based on stops and status
    func getCurrentLocation(from originCode: String) -> CurrentLocation {
        guard let stops = stops else {
            return .notDeparted(departureTime: departureTime)
        }
        
        // Check for explicit boarding status
        if let boardingStop = stops.first(where: { $0.stopStatus == "BOARDING" }) {
            return .boarding(station: boardingStop.stationName)
        }
        
        // Check train-level status
        if status == .boarding {
            // Find the origin station for boarding
            if let originStop = stops.first(where: { Stations.getStationCode($0.stationName) == originCode }) {
                return .boarding(station: originStop.stationName)
            }
        }
        
        // Find last departed stop
        let departedStops = stops.filter { $0.departed }
        let nextStop = stops.first { !$0.departed }
        
        if departedStops.isEmpty {
            // Haven't departed yet
            return .notDeparted(departureTime: getDepartureTime(fromStationCode: originCode))
        } else if let lastDeparted = departedStops.last {
            if let next = nextStop {
                // Calculate if we've just departed (within 2 minutes)
                if let departureTime = lastDeparted.departureTime ?? lastDeparted.scheduledTime {
                    let timeSinceDeparture = Date().timeIntervalSince(departureTime)
                    if timeSinceDeparture < 120 { // Within 2 minutes
                        return .departed(from: lastDeparted.stationName, minutesAgo: Int(timeSinceDeparture / 60))
                    }
                }
                
                // Check if approaching next stop (within 3 minutes)
                if let arrivalTime = next.scheduledTime {
                    let timeToArrival = arrivalTime.timeIntervalSince(Date())
                    if timeToArrival > 0 && timeToArrival < 180 { // Within 3 minutes
                        return .approaching(station: next.stationName, minutesAway: Int(timeToArrival / 60))
                    }
                }
                
                return .enRoute(between: lastDeparted.stationName, and: next.stationName)
            } else {
                // No more stops - arrived
                return .arrived
            }
        } else {
            return .notDeparted(departureTime: departureTime)
        }
    }
    
    /// Get next stop information
    func getNextStopInfo() -> NextStopInfo? {
        guard let stops = stops else { return nil }
        
        let nextStop = stops.first { !$0.departed }
        guard let next = nextStop else { return nil }
        
        let estimatedTime = next.departureTime ?? next.scheduledTime
        guard let eta = estimatedTime else { return nil }
        
        let isDelayed = (next.departureTime != nil && next.scheduledTime != nil) ?
                       next.departureTime! > next.scheduledTime! : false
        
        let delayMinutes = isDelayed ? calculateStopDelay(next) : 0
        
        return NextStopInfo(
            stationName: next.stationName,
            estimatedArrival: eta,
            scheduledArrival: next.scheduledTime,
            isDelayed: isDelayed,
            delayMinutes: delayMinutes
        )
    }
    
    /// Get destination ETA for user's final stop
    func getDestinationETA(to destinationCode: String) -> Date? {
        guard let stops = stops, !stops.isEmpty else { return nil }
        guard !destinationCode.isEmpty else { return nil }
        
        let destinationStop = stops.first { Stations.getStationCode($0.stationName) == destinationCode }
        guard let destStop = destinationStop else { 
            // Fallback: try to find by station name if code lookup fails
            return stops.first { $0.stationName.lowercased().contains(destinationCode.lowercased()) }?
                .departureTime ?? stops.first { $0.stationName.lowercased().contains(destinationCode.lowercased()) }?
                .scheduledTime
        }
        
        return destStop.departureTime ?? destStop.scheduledTime
    }
    
    /// Convert prediction data to Live Activity format
    func getOwlPredictionInfo() -> OwlPredictionInfo? {
        guard let predictionData = predictionData,
              let trackProbs = predictionData.trackProbabilities,
              !trackProbs.isEmpty else { return nil }
        
        // Sort tracks by probability
        let sortedTracks = trackProbs.sorted { $0.value > $1.value }
        guard let topTrack = sortedTracks.first else { return nil }
        
        let alternatives = sortedTracks.dropFirst().prefix(2).map { $0.key }
        
        return OwlPredictionInfo(
            topTrack: topTrack.key,
            confidence: topTrack.value,
            alternativeTracks: Array(alternatives)
        )
    }
    
    /// Create Live Activity content state from current train data
    func toLiveActivityContentState(from originCode: String, to destinationCode: String, lastKnownStatus: TrainStatus? = nil) -> TrainActivityAttributes.ContentState {
        let currentLocation = getCurrentLocation(from: originCode)
        let nextStop = getNextStopInfo()
        let journeyProgress = calculateJourneyProgress(from: originCode, to: destinationCode)
        let destinationETA = getDestinationETA(to: destinationCode)
        let owlPrediction = getOwlPredictionInfo()
        
        let hasStatusChanged = lastKnownStatus != nil && lastKnownStatus != status
        
        return TrainActivityAttributes.ContentState(
            status: status,
            track: track,
            delayMinutes: delayMinutes,
            currentLocation: currentLocation,
            nextStop: nextStop,
            journeyProgress: journeyProgress.progress,
            destinationETA: destinationETA,
            owlPrediction: owlPrediction,
            lastUpdated: Date(),
            hasStatusChanged: hasStatusChanged
        )
    }
    
    /// Helper to calculate delay for a specific stop
    private func calculateStopDelay(_ stop: Stop) -> Int {
        guard let scheduled = stop.scheduledTime,
              let actual = stop.departureTime else { return 0 }
        
        let delay = actual.timeIntervalSince(scheduled) / 60
        return max(0, Int(delay))
    }
}