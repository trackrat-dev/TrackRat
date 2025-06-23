import Foundation
import ActivityKit

// MARK: - Live Activity Extensions for Train
extension Train {
    /// Calculate journey progress between origin and destination with time-based interpolation
    func calculateJourneyProgress(from originCode: String, to destinationCode: String) -> JourneyProgress {
        guard let stops = stops else { return .unknown }
        
        // Find origin and destination indices using robust matching
        let originIndex = stops.firstIndex { Stations.stationMatches($0, stationCode: originCode) }
        let destinationIndex = stops.firstIndex { Stations.stationMatches($0, stationCode: destinationCode) }
        
        guard let fromIdx = originIndex, let toIdx = destinationIndex, fromIdx < toIdx else {
            return .unknown
        }
        
        let journeyStops = Array(stops[fromIdx...toIdx])
        let completedStops = journeyStops.filter { $0.departed ?? false }.count
        
        // Find current stop index in journey
        let currentStopIndex = journeyStops.firstIndex { !($0.departed ?? false) }
        
        // Calculate interpolated progress if between stops
        var interpolatedProgress = Double(completedStops) / Double(journeyStops.count)
        
        if completedStops > 0 && completedStops < journeyStops.count {
            // Find the last departed stop and next stop
            let departedInJourney = journeyStops.filter { $0.departed ?? false }
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
        
        // Check train-level status (StatusV2 only)
        if isActuallyBoarding {
            // Find the origin station for boarding using robust matching
            if let originStop = stops.first(where: { Stations.stationMatches($0, stationCode: originCode) }) {
                return .boarding(station: originStop.stationName)
            }
        }
        
        // Find last departed stop
        let departedStops = stops.filter { $0.departed ?? false }
        let nextStop = stops.first { !($0.departed ?? false) }
        
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
        
        let nextStop = stops.first { !($0.departed ?? false) }
        guard let next = nextStop else { return nil }
        
        let estimatedTime = next.departureTime ?? next.scheduledTime
        guard let eta = estimatedTime else { return nil }
        
        let isDelayed = (next.departureTime != nil && next.scheduledTime != nil) ?
                       next.departureTime! > next.scheduledTime! : false
        
        let delayMinutes = isDelayed ? calculateStopDelay(next) : 0
        
        // Calculate minutes away
        let minutesAway = max(0, Int(eta.timeIntervalSince(Date()) / 60))
        
        // Check if this is the destination (this logic should be refined based on your needs)
        let isDestination = false // You'll need to pass destination info to determine this
        
        return NextStopInfo(
            stationName: next.stationName,
            estimatedArrival: eta,
            scheduledArrival: next.scheduledTime,
            isDelayed: isDelayed,
            delayMinutes: delayMinutes,
            isDestination: isDestination,
            minutesAway: minutesAway
        )
    }
    
    /// Get destination ETA for user's final stop
    func getDestinationETA(to destinationCode: String) -> Date? {
        guard let stops = stops, !stops.isEmpty else { return nil }
        guard !destinationCode.isEmpty else { return nil }
        
        let destinationStop = stops.first { Stations.stationMatches($0, stationCode: destinationCode) }
        guard let destStop = destinationStop else { 
            // Fallback: try to find by station name if robust matching fails
            return stops.first { $0.stationName.lowercased().contains(destinationCode.lowercased()) }?
                .departureTime ?? stops.first { $0.stationName.lowercased().contains(destinationCode.lowercased()) }?
                .scheduledTime
        }
        
        return destStop.departureTime ?? destStop.scheduledTime
    }
    
    /// Convert prediction data to Live Activity format
    func getTrackRatPredictionInfo() -> TrackRatPredictionInfo? {
        guard let predictionData = predictionData,
              let trackProbs = predictionData.trackProbabilities,
              !trackProbs.isEmpty else { return nil }
        
        // Sort tracks by probability
        let sortedTracks = trackProbs.sorted { $0.value > $1.value }
        guard let topTrack = sortedTracks.first else { return nil }
        
        let alternatives = sortedTracks.dropFirst().prefix(2).map { $0.key }
        
        return TrackRatPredictionInfo(
            topTrack: topTrack.key,
            confidence: topTrack.value,
            alternativeTracks: Array(alternatives)
        )
    }
    
    /// Create Live Activity content state from current train data (StatusV2 only)
    func toLiveActivityContentState(from originCode: String, to destinationCode: String, lastKnownStatusV2: String? = nil) -> TrainActivityAttributes.ContentState {
        // Use new enhanced location if available
        var currentLocation = getCurrentLocation(from: originCode)
        if let statusV2 = statusV2 {
            // Override with enhanced status location
            switch statusV2.current {
            case "BOARDING":
                currentLocation = .boarding(station: statusV2.location.replacingOccurrences(of: "at ", with: ""))
            case "EN_ROUTE":
                // Extract stations from "between X and Y" format
                if statusV2.location.contains("between") && statusV2.location.contains("and") {
                    let parts = statusV2.location.replacingOccurrences(of: "between ", with: "").components(separatedBy: " and ")
                    if parts.count == 2 {
                        currentLocation = .enRoute(between: parts[0], and: parts[1])
                    }
                }
            case "DEPARTED":
                if let lastDeparted = progress?.lastDeparted {
                    let timeSinceDeparture = Date().timeIntervalSince(lastDeparted.departedAt)
                    let stationName = Stations.stationCodes.first(where: { $0.value == lastDeparted.stationCode })?.key ?? lastDeparted.stationCode
                    currentLocation = .departed(from: stationName, 
                                              minutesAgo: Int(timeSinceDeparture / 60))
                }
            case "ARRIVED":
                currentLocation = .arrived
            default:
                break
            }
        }
        
        // Use enhanced next stop info if available
        var nextStop = getNextStopInfo()
        if let progress = progress, let nextArrival = progress.nextArrival {
            nextStop = NextStopInfo(
                stationName: Stations.stationCodes.first(where: { $0.value == nextArrival.stationCode })?.key ?? nextArrival.stationCode,
                estimatedArrival: nextArrival.estimatedTime,
                scheduledArrival: nextArrival.scheduledTime,
                isDelayed: nextArrival.estimatedTime > nextArrival.scheduledTime,
                delayMinutes: Int((nextArrival.estimatedTime.timeIntervalSince(nextArrival.scheduledTime)) / 60),
                isDestination: nextArrival.stationCode == destinationCode,
                minutesAway: nextArrival.minutesAway
            )
        }
        
        // Use enhanced journey progress if available
        var journeyProgress = calculateJourneyProgress(from: originCode, to: destinationCode)
        if let progress = progress {
            journeyProgress = JourneyProgress(
                totalStops: progress.totalStops,
                completedStops: progress.stopsCompleted,
                progress: Double(progress.journeyPercent) / 100.0,
                currentStopIndex: nil
            )
        }
        
        let destinationETA = getDestinationETA(to: destinationCode)
        let trackRatPrediction = getTrackRatPredictionInfo()
        
        let hasStatusChanged = lastKnownStatusV2 != nil && lastKnownStatusV2 != statusV2?.current
        
        return TrainActivityAttributes.ContentState(
            statusV2: statusV2?.current ?? "UNKNOWN",
            statusLocation: statusV2?.location,
            track: displayTrack,  // Use displayTrack instead of track for consolidated data
            delayMinutes: displayDelayMinutes,  // Use displayDelayMinutes for consolidated data
            currentLocation: currentLocation,
            nextStop: nextStop,
            journeyProgress: journeyProgress.progress,
            destinationETA: destinationETA,
            trackRatPrediction: trackRatPrediction,
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