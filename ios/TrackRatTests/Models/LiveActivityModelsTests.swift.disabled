import XCTest
import ActivityKit
@testable import TrackRat

class LiveActivityModelsTests: XCTestCase {
    
    // MARK: - TrainActivityAttributes Tests
    
    func testTrainActivityAttributesInitialization() {
        let attributes = TrainActivityAttributes(
            trainNumber: "123",
            trainId: "nec_123",
            routeDescription: "Northeast Corridor",
            origin: "Newark Penn Station",
            destination: "New York Penn Station",
            originStationCode: "NP",
            destinationStationCode: "NY"
        )
        
        XCTAssertEqual(attributes.trainNumber, "123")
        XCTAssertEqual(attributes.trainId, "nec_123")
        XCTAssertEqual(attributes.routeDescription, "Northeast Corridor")
        XCTAssertEqual(attributes.origin, "Newark Penn Station")
        XCTAssertEqual(attributes.destination, "New York Penn Station")
        XCTAssertEqual(attributes.originStationCode, "NP")
        XCTAssertEqual(attributes.destinationStationCode, "NY")
    }
    
    // MARK: - ContentState Tests
    
    func testContentStateInitialization() {
        let contentState = TrainActivityAttributes.ContentState(
            status: "BOARDING",
            track: "7",
            currentStopName: "Newark Penn Station",
            nextStopName: "New York Penn Station",
            delayMinutes: 5,
            journeyProgress: 0.25,
            dataTimestamp: Date().timeIntervalSince1970
        )
        
        XCTAssertEqual(contentState.status, "BOARDING")
        XCTAssertEqual(contentState.track, "7")
        XCTAssertEqual(contentState.currentStopName, "Newark Penn Station")
        XCTAssertEqual(contentState.nextStopName, "New York Penn Station")
        XCTAssertEqual(contentState.delayMinutes, 5)
        XCTAssertEqual(contentState.journeyProgress, 0.25)
    }
    
    func testContentStateCodable() throws {
        let contentState = TrainActivityAttributes.ContentState(
            status: "EN_ROUTE",
            track: nil,
            currentStopName: "Newark Penn Station",
            nextStopName: "New York Penn Station",
            delayMinutes: 0,
            journeyProgress: 0.5,
            dataTimestamp: Date().timeIntervalSince1970
        )
        
        let encoder = JSONEncoder()
        let decoder = JSONDecoder()
        
        let data = try encoder.encode(contentState)
        let decoded = try decoder.decode(TrainActivityAttributes.ContentState.self, from: data)
        
        XCTAssertEqual(contentState.status, decoded.status)
        XCTAssertEqual(contentState.track, decoded.track)
        XCTAssertEqual(contentState.currentStopName, decoded.currentStopName)
        XCTAssertEqual(contentState.nextStopName, decoded.nextStopName)
        XCTAssertEqual(contentState.delayMinutes, decoded.delayMinutes)
        XCTAssertEqual(contentState.journeyProgress, decoded.journeyProgress, accuracy: 0.001)
    }
    
    // MARK: - Hashable Tests
    
    func testContentStateHashable() {
        let contentState1 = TrainActivityAttributes.ContentState(
            status: "BOARDING",
            track: "7",
            currentStopName: "Newark Penn Station",
            nextStopName: "New York Penn Station",
            delayMinutes: 0,
            journeyProgress: 0.25,
            dataTimestamp: Date().timeIntervalSince1970
        )
        
        let contentState2 = TrainActivityAttributes.ContentState(
            status: "BOARDING",
            track: "7",
            currentStopName: "Newark Penn Station",
            nextStopName: "New York Penn Station",
            delayMinutes: 0,
            journeyProgress: 0.25,
            dataTimestamp: Date().timeIntervalSince1970
        )
        
        // Test hashable implementation
        let set = Set([contentState1, contentState2])
        XCTAssertEqual(set.count, 1) // Should be identical
    }
    
    // MARK: - Edge Cases Tests
    
    func testContentStateWithNilValues() {
        let contentState = TrainActivityAttributes.ContentState(
            status: "UNKNOWN",
            track: nil,
            currentStopName: "Unknown",
            nextStopName: nil,
            delayMinutes: 0,
            journeyProgress: 0.0,
            dataTimestamp: Date().timeIntervalSince1970
        )
        
        XCTAssertEqual(contentState.status, "UNKNOWN")
        XCTAssertNil(contentState.track)
        XCTAssertEqual(contentState.currentStopName, "Unknown")
        XCTAssertNil(contentState.nextStopName)
        XCTAssertEqual(contentState.delayMinutes, 0)
        XCTAssertEqual(contentState.journeyProgress, 0.0)
    }
    
    func testJourneyProgressBounds() {
        // Test progress at boundaries
        let zeroProgress = TrainActivityAttributes.ContentState(
            status: "SCHEDULED",
            track: nil,
            currentStopName: "Origin",
            nextStopName: "Destination",
            delayMinutes: 0,
            journeyProgress: 0.0,
            dataTimestamp: Date().timeIntervalSince1970
        )
        XCTAssertEqual(zeroProgress.journeyProgress, 0.0)
        
        let fullProgress = TrainActivityAttributes.ContentState(
            status: "ARRIVED",
            track: nil,
            currentStopName: "Destination",
            nextStopName: nil,
            delayMinutes: 0,
            journeyProgress: 1.0,
            dataTimestamp: Date().timeIntervalSince1970
        )
        XCTAssertEqual(fullProgress.journeyProgress, 1.0)
    }
}