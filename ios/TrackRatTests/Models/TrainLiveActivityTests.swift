import XCTest
@testable import TrackRat

class TrainLiveActivityTests: XCTestCase {
    
    // MARK: - Test Data Setup
    
    func createTestTrainV2(withStops stops: [StopV2]? = nil, status: String = "ON_TIME") -> TrainV2 {
        let departure = StationTiming(
            code: "NP",
            name: "Newark Penn Station",
            scheduledTime: Date(),
            actualTime: nil,
            estimatedTime: nil,
            track: "7",
            status: status,
            delayMinutes: 0
        )
        
        let arrival = StationTiming(
            code: "NY",
            name: "New York Penn Station",
            scheduledTime: Date().addingTimeInterval(1200),
            actualTime: nil,
            estimatedTime: nil,
            track: nil,
            status: nil,
            delayMinutes: 0
        )
        
        let line = LineInfo(code: "NE", name: "Northeast Corridor", color: "#0066CC")
        
        let journey = JourneyInfo(
            origin: "NP",
            originName: "Newark Penn Station",
            durationMinutes: 20,
            stopsBetween: 1,
            progress: JourneyProgressV2(
                completedStops: 1,
                totalStops: 3,
                percentage: 33,
                currentLocation: "Newark Penn Station",
                nextStop: "Secaucus Junction"
            )
        )
        
        return TrainV2(
            id: 123,
            trainId: "123",
            line: line,
            destination: "New York Penn Station",
            departure: departure,
            arrival: arrival,
            journey: journey,
            dataFreshness: nil,
            stops: stops
        )
    }
    
    func createTestStops() -> [StopV2] {
        let baseTime = Date()
        return [
            StopV2(
                stationCode: "NP",
                stationName: "Newark Penn Station",
                sequence: 1,
                scheduledArrival: nil,
                scheduledDeparture: baseTime,
                actualArrival: nil,
                actualDeparture: baseTime,
                estimatedArrival: nil,
                estimatedDeparture: nil,
                track: "1",
                status: "DEPARTED",
                delayMinutes: 0,
                departed: true
            ),
            StopV2(
                stationCode: "SEC",
                stationName: "Secaucus Junction",
                sequence: 2,
                scheduledArrival: baseTime.addingTimeInterval(600),
                scheduledDeparture: baseTime.addingTimeInterval(600),
                actualArrival: nil,
                actualDeparture: nil,
                estimatedArrival: nil,
                estimatedDeparture: nil,
                track: "2",
                status: "SCHEDULED",
                delayMinutes: 0,
                departed: false
            ),
            StopV2(
                stationCode: "NY",
                stationName: "New York Penn Station",
                sequence: 3,
                scheduledArrival: baseTime.addingTimeInterval(1200),
                scheduledDeparture: nil,
                actualArrival: nil,
                actualDeparture: nil,
                estimatedArrival: nil,
                estimatedDeparture: nil,
                track: "7",
                status: "SCHEDULED",
                delayMinutes: 0,
                departed: false
            )
        ]
    }
    
    // MARK: - Live Activity Content State Tests
    
    func testToLiveActivityContentStateBasic() {
        let stops = createTestStops()
        let train = createTestTrainV2(withStops: stops)
        
        let contentState = train.toLiveActivityContentState(from: "NP", to: "NY")
        
        XCTAssertEqual(contentState.status, "ON_TIME")
        XCTAssertEqual(contentState.track, "7")
        XCTAssertEqual(contentState.currentStopName, "Newark Penn Station")
        XCTAssertEqual(contentState.nextStopName, "Secaucus Junction")
        XCTAssertEqual(contentState.delayMinutes, 0)
        XCTAssertGreaterThan(contentState.journeyProgress, 0.0)
        XCTAssertLessThan(contentState.journeyProgress, 1.0)
    }
    
    func testToLiveActivityContentStateWithoutStops() {
        let train = createTestTrainV2(withStops: nil)
        
        let contentState = train.toLiveActivityContentState(from: "NP", to: "NY")
        
        XCTAssertEqual(contentState.status, "ON_TIME")
        XCTAssertEqual(contentState.track, "7")
        XCTAssertEqual(contentState.currentStopName, "Newark Penn Station")
        XCTAssertNil(contentState.nextStopName)
        XCTAssertEqual(contentState.delayMinutes, 0)
        XCTAssertEqual(contentState.journeyProgress, 0.0)
    }
    
    func testToLiveActivityContentStateWithDelay() {
        let delayedTrain = createTestTrainV2()
        // Create a train with delay
        let departure = StationTiming(
            code: "NP",
            name: "Newark Penn Station",
            scheduledTime: Date(),
            actualTime: nil,
            estimatedTime: nil,
            track: "7",
            status: "DELAYED",
            delayMinutes: 15
        )
        
        let delayedTrainV2 = TrainV2(
            id: 123,
            trainId: "123",
            line: delayedTrain.line,
            destination: delayedTrain.destination,
            departure: departure,
            arrival: delayedTrain.arrival,
            journey: delayedTrain.journey,
            dataFreshness: nil,
            stops: nil
        )
        
        let contentState = delayedTrainV2.toLiveActivityContentState(from: "NP", to: "NY")
        
        XCTAssertEqual(contentState.status, "DELAYED")
        XCTAssertEqual(contentState.delayMinutes, 15)
    }
    
    func testToLiveActivityContentStateAllDeparted() {
        let allDepartedStops = createTestStops().map { stop in
            StopV2(
                stationCode: stop.stationCode,
                stationName: stop.stationName,
                sequence: stop.sequence,
                scheduledArrival: stop.scheduledArrival,
                scheduledDeparture: stop.scheduledDeparture,
                actualArrival: stop.actualArrival,
                actualDeparture: stop.actualDeparture,
                estimatedArrival: stop.estimatedArrival,
                estimatedDeparture: stop.estimatedDeparture,
                track: stop.track,
                status: "DEPARTED",
                delayMinutes: stop.delayMinutes,
                departed: true
            )
        }
        
        let train = createTestTrainV2(withStops: allDepartedStops)
        let contentState = train.toLiveActivityContentState(from: "NP", to: "NY")
        
        // Should be complete journey
        XCTAssertEqual(contentState.journeyProgress, 1.0)
        XCTAssertEqual(contentState.currentStopName, "New York Penn Station")
        XCTAssertNil(contentState.nextStopName)
    }
    
    // MARK: - Progress Calculation Tests
    
    func testJourneyProgressCalculation() {
        let stops = createTestStops()
        let train = createTestTrainV2(withStops: stops)
        
        let contentState = train.toLiveActivityContentState(from: "NP", to: "NY")
        
        // Should be 1 out of 3 stops completed
        XCTAssertEqual(contentState.journeyProgress, 1.0/3.0, accuracy: 0.01)
    }
    
    func testJourneyProgressWithEmptyStops() {
        let train = createTestTrainV2(withStops: [])
        
        let contentState = train.toLiveActivityContentState(from: "NP", to: "NY")
        
        XCTAssertEqual(contentState.journeyProgress, 0.0)
    }
    
    // MARK: - Edge Cases
    
    func testContentStateWithNilTrack() {
        let departure = StationTiming(
            code: "NP",
            name: "Newark Penn Station",
            scheduledTime: Date(),
            actualTime: nil,
            estimatedTime: nil,
            track: nil, // No track assigned
            status: "SCHEDULED",
            delayMinutes: 0
        )
        
        let train = TrainV2(
            id: 123,
            trainId: "123",
            line: LineInfo(code: "NE", name: "Northeast Corridor", color: "#0066CC"),
            destination: "New York Penn Station",
            departure: departure,
            arrival: nil,
            journey: nil,
            dataFreshness: nil,
            stops: nil
        )
        
        let contentState = train.toLiveActivityContentState(from: "NP", to: "NY")
        
        XCTAssertNil(contentState.track)
        XCTAssertEqual(contentState.status, "SCHEDULED")
    }
    
    func testContentStateWithUnknownStatus() {
        let train = createTestTrainV2(status: "UNKNOWN_STATUS")
        
        let contentState = train.toLiveActivityContentState(from: "NP", to: "NY")
        
        XCTAssertEqual(contentState.status, "UNKNOWN_STATUS")
    }
}