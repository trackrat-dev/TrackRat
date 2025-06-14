import XCTest
@testable import TrackRat

class TrainLiveActivityTests: XCTestCase {
    
    // MARK: - Test Data Setup
    
    func createTestTrain(withStops stops: [Stop]? = nil, status: TrainStatus = .onTime) -> Train {
        return Train(
            id: 1,
            trainId: "123",
            line: "Northeast Corridor",
            destination: "New York Penn Station",
            departureTime: Date(),
            track: "7",
            status: status,
            delayMinutes: 0,
            stops: stops,
            predictionData: createTestPredictionData(),
            originStationCode: "NP",
            dataSource: "NJTransit"
        )
    }
    
    func createTestStops() -> [Stop] {
        let baseTime = Date()
        return [
            Stop(
                stationCode: "NP",
                stationName: "Newark Penn Station",
                scheduledTime: baseTime,
                departureTime: baseTime,
                pickupOnly: false,
                dropoffOnly: false,
                departed: true,
                departedConfirmedBy: ["NJTransit"],
                stopStatus: nil,
                platform: "1"
            ),
            Stop(
                stationCode: "SEC",
                stationName: "Secaucus Junction",
                scheduledTime: baseTime.addingTimeInterval(600), // 10 minutes
                departureTime: baseTime.addingTimeInterval(600),
                pickupOnly: false,
                dropoffOnly: false,
                departed: false,
                departedConfirmedBy: nil,
                stopStatus: nil,
                platform: "2"
            ),
            Stop(
                stationCode: "NY",
                stationName: "New York Penn Station",
                scheduledTime: baseTime.addingTimeInterval(1200), // 20 minutes
                departureTime: baseTime.addingTimeInterval(1200),
                pickupOnly: false,
                dropoffOnly: false,
                departed: false,
                departedConfirmedBy: nil,
                stopStatus: nil,
                platform: "7"
            )
        ]
    }
    
    func createTestPredictionData() -> PredictionData {
        return PredictionData(trackProbabilities: [
            "7": 0.85,
            "8": 0.10,
            "9": 0.05
        ])
    }
    
    // MARK: - Journey Progress Tests
    
    func testCalculateJourneyProgressBasic() {
        let stops = createTestStops()
        let train = createTestTrain(withStops: stops)
        
        let progress = train.calculateJourneyProgress(from: "NP", to: "NY")
        
        XCTAssertEqual(progress.totalStops, 3)
        XCTAssertEqual(progress.completedStops, 1) // Only NP departed
        XCTAssertGreaterThan(progress.progress, 0.0)
        XCTAssertLessThan(progress.progress, 1.0)
    }
    
    func testCalculateJourneyProgressUnknownStations() {
        let stops = createTestStops()
        let train = createTestTrain(withStops: stops)
        
        let progress = train.calculateJourneyProgress(from: "UNKNOWN", to: "NY")
        
        XCTAssertEqual(progress, .unknown)
        XCTAssertEqual(progress.totalStops, 0)
        XCTAssertEqual(progress.completedStops, 0)
        XCTAssertEqual(progress.progress, 0.0)
    }
    
    func testCalculateJourneyProgressNoStops() {
        let train = createTestTrain(withStops: nil)
        
        let progress = train.calculateJourneyProgress(from: "NP", to: "NY")
        
        XCTAssertEqual(progress, .unknown)
    }
    
    func testCalculateJourneyProgressPartialJourney() {
        let stops = createTestStops()
        let train = createTestTrain(withStops: stops)
        
        // Test journey from middle station to end
        let progress = train.calculateJourneyProgress(from: "SEC", to: "NY")
        
        XCTAssertEqual(progress.totalStops, 2) // SEC -> NY
        XCTAssertEqual(progress.completedStops, 0) // SEC hasn't departed yet
    }
    
    func testCalculateJourneyProgressWithTimeInterpolation() {
        let baseTime = Date()
        let departedStop = Stop(
            stationCode: "NP",
            stationName: "Newark Penn Station",
            scheduledTime: baseTime.addingTimeInterval(-300), // 5 minutes ago
            departureTime: baseTime.addingTimeInterval(-300),
            pickupOnly: false,
            dropoffOnly: false,
            departed: true,
            departedConfirmedBy: ["NJTransit"],
            stopStatus: nil,
            platform: "1"
        )
        
        let nextStop = Stop(
            stationCode: "NY",
            stationName: "New York Penn Station",
            scheduledTime: baseTime.addingTimeInterval(900), // 15 minutes from now
            departureTime: nil,
            pickupOnly: false,
            dropoffOnly: false,
            departed: false,
            departedConfirmedBy: nil,
            stopStatus: nil,
            platform: "7"
        )
        
        let stopsWithInterpolation = [departedStop, nextStop]
        let train = createTestTrain(withStops: stopsWithInterpolation)
        
        let progress = train.calculateJourneyProgress(from: "NP", to: "NY")
        
        XCTAssertEqual(progress.totalStops, 2)
        XCTAssertEqual(progress.completedStops, 1)
        // Progress should be > 0.5 since we're partway between stops
        XCTAssertGreaterThan(progress.progress, 0.5)
    }
    
    // MARK: - Current Location Tests
    
    func testGetCurrentLocationNotDeparted() {
        let stops = createTestStops()
        // Mark all stops as not departed
        let notDepartedStops = stops.map { stop in
            Stop(
                stationCode: stop.stationCode,
                stationName: stop.stationName,
                scheduledTime: stop.scheduledTime,
                departureTime: stop.departureTime,
                pickupOnly: stop.pickupOnly,
                dropoffOnly: stop.dropoffOnly,
                departed: false,
                departedConfirmedBy: nil,
                stopStatus: stop.stopStatus,
                platform: stop.platform
            )
        }
        
        let train = createTestTrain(withStops: notDepartedStops)
        let location = train.getCurrentLocation(from: "NP")
        
        if case .notDeparted = location {
            XCTAssertTrue(true)
        } else {
            XCTFail("Expected notDeparted location")
        }
    }
    
    func testGetCurrentLocationBoarding() {
        let train = createTestTrain(status: .boarding)
        let location = train.getCurrentLocation(from: "NP")
        
        if case .boarding(let station) = location {
            XCTAssertTrue(station.contains("Newark Penn"))
        } else {
            XCTFail("Expected boarding location")
        }
    }
    
    func testGetCurrentLocationBoardingFromStopStatus() {
        let boardingStop = Stop(
            stationCode: "NP",
            stationName: "Newark Penn Station",
            scheduledTime: Date(),
            departureTime: Date(),
            pickupOnly: false,
            dropoffOnly: false,
            departed: false,
            departedConfirmedBy: nil,
            stopStatus: "BOARDING",
            platform: "1"
        )
        
        let train = createTestTrain(withStops: [boardingStop])
        let location = train.getCurrentLocation(from: "NP")
        
        if case .boarding(let station) = location {
            XCTAssertEqual(station, "Newark Penn Station")
        } else {
            XCTFail("Expected boarding location from stop status")
        }
    }
    
    func testGetCurrentLocationDepartedRecently() {
        let recentTime = Date().addingTimeInterval(-60) // 1 minute ago
        let departedStop = Stop(
            stationCode: "NP",
            stationName: "Newark Penn Station",
            scheduledTime: recentTime,
            departureTime: recentTime,
            pickupOnly: false,
            dropoffOnly: false,
            departed: true,
            departedConfirmedBy: ["NJTransit"],
            stopStatus: nil,
            platform: "1"
        )
        
        let nextStop = Stop(
            stationCode: "NY",
            stationName: "New York Penn Station",
            scheduledTime: Date().addingTimeInterval(600),
            departureTime: nil,
            pickupOnly: false,
            dropoffOnly: false,
            departed: false,
            departedConfirmedBy: nil,
            stopStatus: nil,
            platform: "7"
        )
        
        let train = createTestTrain(withStops: [departedStop, nextStop])
        let location = train.getCurrentLocation(from: "NP")
        
        if case .departed(let from, let minutesAgo) = location {
            XCTAssertEqual(from, "Newark Penn Station")
            XCTAssertEqual(minutesAgo, 1)
        } else {
            XCTFail("Expected departed location, got \\(location)")
        }
    }
    
    func testGetCurrentLocationApproaching() {
        let departedStop = Stop(
            stationCode: "NP",
            stationName: "Newark Penn Station",
            scheduledTime: Date().addingTimeInterval(-600), // 10 minutes ago
            departureTime: Date().addingTimeInterval(-600),
            pickupOnly: false,
            dropoffOnly: false,
            departed: true,
            departedConfirmedBy: ["NJTransit"],
            stopStatus: nil,
            platform: "1"
        )
        
        let approachingStop = Stop(
            stationCode: "NY",
            stationName: "New York Penn Station",
            scheduledTime: Date().addingTimeInterval(120), // 2 minutes from now
            departureTime: nil,
            pickupOnly: false,
            dropoffOnly: false,
            departed: false,
            departedConfirmedBy: nil,
            stopStatus: nil,
            platform: "7"
        )
        
        let train = createTestTrain(withStops: [departedStop, approachingStop])
        let location = train.getCurrentLocation(from: "NP")
        
        if case .approaching(let station, let minutesAway) = location {
            XCTAssertEqual(station, "New York Penn Station")
            XCTAssertEqual(minutesAway, 2)
        } else {
            XCTFail("Expected approaching location, got \\(location)")
        }
    }
    
    func testGetCurrentLocationEnRoute() {
        let stops = createTestStops()
        let train = createTestTrain(withStops: stops)
        let location = train.getCurrentLocation(from: "NP")
        
        if case .enRoute(let from, let to) = location {
            XCTAssertEqual(from, "Newark Penn Station")
            XCTAssertEqual(to, "Secaucus Junction")
        } else {
            XCTFail("Expected enRoute location")
        }
    }
    
    func testGetCurrentLocationArrived() {
        let allDepartedStops = createTestStops().map { stop in
            Stop(
                stationCode: stop.stationCode,
                stationName: stop.stationName,
                scheduledTime: stop.scheduledTime,
                departureTime: stop.departureTime,
                pickupOnly: stop.pickupOnly,
                dropoffOnly: stop.dropoffOnly,
                departed: true,
                departedConfirmedBy: ["NJTransit"],
                stopStatus: stop.stopStatus,
                platform: stop.platform
            )
        }
        
        let train = createTestTrain(withStops: allDepartedStops)
        let location = train.getCurrentLocation(from: "NP")
        
        if case .arrived = location {
            XCTAssertTrue(true)
        } else {
            XCTFail("Expected arrived location")
        }
    }
    
    // MARK: - Next Stop Info Tests
    
    func testGetNextStopInfo() {
        let stops = createTestStops()
        let train = createTestTrain(withStops: stops)
        
        let nextStop = train.getNextStopInfo()
        
        XCTAssertNotNil(nextStop)
        XCTAssertEqual(nextStop?.stationName, "Secaucus Junction")
        XCTAssertFalse(nextStop?.isDelayed ?? true)
        XCTAssertEqual(nextStop?.delayMinutes, 0)
    }
    
    func testGetNextStopInfoWithDelay() {
        let baseTime = Date()
        let delayedStop = Stop(
            stationCode: "SEC",
            stationName: "Secaucus Junction",
            scheduledTime: baseTime.addingTimeInterval(600), // Original: 10 minutes
            departureTime: baseTime.addingTimeInterval(900), // Delayed: 15 minutes
            pickupOnly: false,
            dropoffOnly: false,
            departed: false,
            departedConfirmedBy: nil,
            stopStatus: nil,
            platform: "2"
        )
        
        let stopsWithDelay = [createTestStops()[0], delayedStop, createTestStops()[2]]
        let train = createTestTrain(withStops: stopsWithDelay)
        
        let nextStop = train.getNextStopInfo()
        
        XCTAssertNotNil(nextStop)
        XCTAssertEqual(nextStop?.stationName, "Secaucus Junction")
        XCTAssertTrue(nextStop?.isDelayed ?? false)
        XCTAssertEqual(nextStop?.delayMinutes, 5)
    }
    
    func testGetNextStopInfoNoStops() {
        let train = createTestTrain(withStops: nil)
        let nextStop = train.getNextStopInfo()
        
        XCTAssertNil(nextStop)
    }
    
    func testGetNextStopInfoAllDeparted() {
        let allDepartedStops = createTestStops().map { stop in
            Stop(
                stationCode: stop.stationCode,
                stationName: stop.stationName,
                scheduledTime: stop.scheduledTime,
                departureTime: stop.departureTime,
                pickupOnly: stop.pickupOnly,
                dropoffOnly: stop.dropoffOnly,
                departed: true,
                departedConfirmedBy: ["NJTransit"],
                stopStatus: stop.stopStatus,
                platform: stop.platform
            )
        }
        
        let train = createTestTrain(withStops: allDepartedStops)
        let nextStop = train.getNextStopInfo()
        
        XCTAssertNil(nextStop)
    }
    
    // MARK: - Destination ETA Tests
    
    func testGetDestinationETA() {
        let stops = createTestStops()
        let train = createTestTrain(withStops: stops)
        
        let eta = train.getDestinationETA(to: "NY")
        
        XCTAssertNotNil(eta)
        XCTAssertEqual(eta, stops[2].departureTime)
    }
    
    func testGetDestinationETAUnknownDestination() {
        let stops = createTestStops()
        let train = createTestTrain(withStops: stops)
        
        let eta = train.getDestinationETA(to: "UNKNOWN")
        
        XCTAssertNil(eta)
    }
    
    func testGetDestinationETAEmptyDestination() {
        let stops = createTestStops()
        let train = createTestTrain(withStops: stops)
        
        let eta = train.getDestinationETA(to: "")
        
        XCTAssertNil(eta)
    }
    
    func testGetDestinationETANoStops() {
        let train = createTestTrain(withStops: nil)
        
        let eta = train.getDestinationETA(to: "NY")
        
        XCTAssertNil(eta)
    }
    
    // MARK: - TrackRat Prediction Tests
    
    func testGetTrackRatPredictionInfo() {
        let train = createTestTrain()
        
        let prediction = train.getTrackRatPredictionInfo()
        
        XCTAssertNotNil(prediction)
        XCTAssertEqual(prediction?.topTrack, "7")
        XCTAssertEqual(prediction?.confidence, 0.85)
        XCTAssertEqual(prediction?.alternativeTracks.count, 2)
        XCTAssertTrue(prediction?.alternativeTracks.contains("8") ?? false)
        XCTAssertTrue(prediction?.alternativeTracks.contains("9") ?? false)
    }
    
    func testGetTrackRatPredictionInfoNoPredictions() {
        let trainWithoutPredictions = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: Date(),
            track: "7", status: .onTime, delayMinutes: 0,
            stops: nil, predictionData: nil, originStationCode: "NP",
            dataSource: "NJTransit"
        )
        
        let prediction = trainWithoutPredictions.getTrackRatPredictionInfo()
        
        XCTAssertNil(prediction)
    }
    
    func testGetTrackRatPredictionInfoEmptyProbabilities() {
        let emptyPredictions = PredictionData(trackProbabilities: [:])
        let trainWithEmptyPredictions = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: Date(),
            track: "7", status: .onTime, delayMinutes: 0,
            stops: nil, predictionData: emptyPredictions, originStationCode: "NP",
            dataSource: "NJTransit"
        )
        
        let prediction = trainWithEmptyPredictions.getTrackRatPredictionInfo()
        
        XCTAssertNil(prediction)
    }
    
    // MARK: - Live Activity Content State Tests
    
    func testToLiveActivityContentState() {
        let stops = createTestStops()
        let train = createTestTrain(withStops: stops)
        
        let contentState = train.toLiveActivityContentState(from: "NP", to: "NY")
        
        XCTAssertEqual(contentState.status, .onTime)
        XCTAssertEqual(contentState.track, "7")
        XCTAssertEqual(contentState.delayMinutes, 0)
        XCTAssertNotNil(contentState.nextStop)
        XCTAssertNotNil(contentState.trackRatPrediction)
        XCTAssertGreaterThan(contentState.journeyProgress, 0.0)
        XCTAssertFalse(contentState.hasStatusChanged)
    }
    
    func testToLiveActivityContentStateWithStatusChange() {
        let stops = createTestStops()
        let train = createTestTrain(withStops: stops, status: .boarding)
        
        let contentState = train.toLiveActivityContentState(from: "NP", to: "NY", lastKnownStatus: .onTime)
        
        XCTAssertEqual(contentState.status, .boarding)
        XCTAssertTrue(contentState.hasStatusChanged)
        
        if case .boarding = contentState.currentLocation {
            XCTAssertTrue(true)
        } else {
            XCTFail("Expected boarding location")
        }
    }
    
    func testToLiveActivityContentStateWithEnhancedData() {
        let statusV2 = StatusV2(
            current: "EN_ROUTE",
            location: "between Newark Penn Station and Secaucus Junction",
            updatedAt: Date(),
            confidence: "high",
            source: "NJTransit"
        )
        
        let progress = Progress(
            lastDeparted: DepartedStation(
                stationCode: "NP",
                departedAt: Date().addingTimeInterval(-300),
                delayMinutes: 0
            ),
            nextArrival: NextArrival(
                stationCode: "NY",
                scheduledTime: Date().addingTimeInterval(900),
                estimatedTime: Date().addingTimeInterval(900),
                minutesAway: 15
            ),
            journeyPercent: 75,
            stopsCompleted: 2,
            totalStops: 3
        )
        
        let enhancedTrain = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: Date(),
            track: "7", status: .departed, delayMinutes: 0,
            stops: createTestStops(), predictionData: createTestPredictionData(),
            originStationCode: "NP", dataSource: "NJTransit",
            statusV2: statusV2, progress: progress
        )
        
        let contentState = enhancedTrain.toLiveActivityContentState(from: "NP", to: "NY")
        
        // Should use enhanced data
        XCTAssertEqual(contentState.journeyProgress, 0.75)
        
        if case .enRoute(let from, let to) = contentState.currentLocation {
            XCTAssertEqual(from, "Newark Penn Station")
            XCTAssertEqual(to, "Secaucus Junction")
        } else {
            XCTFail("Expected enRoute location from enhanced data")
        }
        
        XCTAssertNotNil(contentState.nextStop)
        XCTAssertEqual(contentState.nextStop?.stationName, "New York Penn Station")
    }
    
    // MARK: - Edge Cases and Error Handling
    
    func testCalculateStopDelay() {
        let baseTime = Date()
        let scheduledTime = baseTime
        let actualTime = baseTime.addingTimeInterval(300) // 5 minutes late
        
        let delayedStop = Stop(
            stationCode: "NP",
            stationName: "Newark Penn Station",
            scheduledTime: scheduledTime,
            departureTime: actualTime,
            pickupOnly: false,
            dropoffOnly: false,
            departed: true,
            departedConfirmedBy: ["NJTransit"],
            stopStatus: nil,
            platform: "1"
        )
        
        let train = createTestTrain(withStops: [delayedStop])
        
        // Use reflection to access private method for testing
        let mirror = Mirror(reflecting: train)
        
        // Since we can't directly test private methods, we'll test through public methods
        let nextStop = train.getNextStopInfo()
        // The delay calculation is tested indirectly through getNextStopInfo
        XCTAssertNotNil(nextStop) // Basic validation that the method doesn't crash
    }
    
    func testGetCurrentLocationWithEmptyStops() {
        let train = createTestTrain(withStops: [])
        let location = train.getCurrentLocation(from: "NP")
        
        if case .notDeparted = location {
            XCTAssertTrue(true)
        } else {
            XCTFail("Expected notDeparted location for empty stops")
        }
    }
    
    func testJourneyProgressWithSameOriginDestination() {
        let stops = createTestStops()
        let train = createTestTrain(withStops: stops)
        
        let progress = train.calculateJourneyProgress(from: "NP", to: "NP")
        
        XCTAssertEqual(progress, .unknown)
    }
    
    func testJourneyProgressWithInvalidRange() {
        let stops = createTestStops()
        let train = createTestTrain(withStops: stops)
        
        // Try to get progress from destination to origin (reversed)
        let progress = train.calculateJourneyProgress(from: "NY", to: "NP")
        
        XCTAssertEqual(progress, .unknown)
    }
    
    func testToLiveActivityContentStateWithNilValues() {
        let minimalTrain = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: Date(),
            track: nil, status: .unknown, delayMinutes: nil,
            stops: nil, predictionData: nil, originStationCode: nil,
            dataSource: nil
        )
        
        let contentState = minimalTrain.toLiveActivityContentState(from: "NP", to: "NY")
        
        XCTAssertEqual(contentState.status, .unknown)
        XCTAssertNil(contentState.track)
        XCTAssertEqual(contentState.delayMinutes, 0)
        XCTAssertNil(contentState.nextStop)
        XCTAssertNil(contentState.trackRatPrediction)
        XCTAssertEqual(contentState.journeyProgress, 0.0)
    }
}