import XCTest
@testable import TrackRat

class TrainTests: XCTestCase {
    
    func testTrainInitialization() {
        let departureTime = Date()
        let train = Train(
            id: 1,
            trainId: "123",
            line: "Northeast Corridor",
            destination: "New York Penn Station",
            departureTime: departureTime,
            track: "1",
            status: .onTime,
            delayMinutes: nil,
            stops: nil,
            predictionData: nil,
            originStationCode: "NP",
            dataSource: "NJTransit",
            consolidatedId: nil,
            originStation: nil,
            dataSources: nil,
            currentPosition: nil,
            trackAssignment: nil,
            statusSummary: nil,
            consolidationMetadata: nil,
            statusV2: nil,
            progress: nil
        )
        
        XCTAssertEqual(train.id, 1)
        XCTAssertEqual(train.trainId, "123")
        XCTAssertEqual(train.line, "Northeast Corridor")
        XCTAssertEqual(train.destination, "New York Penn Station")
        XCTAssertEqual(train.departureTime, departureTime)
        XCTAssertEqual(train.track, "1")
        XCTAssertEqual(train.status, .onTime)
        XCTAssertEqual(train.originStationCode, "NP")
        XCTAssertEqual(train.dataSource, "NJTransit")
    }
    
    func testTrainWithDelayMinutes() {
        let train = Train(
            id: 1,
            trainId: "123",
            line: "Northeast Corridor",
            destination: "New York Penn Station",
            departureTime: Date(),
            track: "1",
            status: .delayed,
            delayMinutes: 15,
            stops: nil,
            predictionData: nil,
            originStationCode: "NP",
            dataSource: "NJTransit",
            consolidatedId: nil,
            originStation: nil,
            dataSources: nil,
            currentPosition: nil,
            trackAssignment: nil,
            statusSummary: nil,
            consolidationMetadata: nil,
            statusV2: nil,
            progress: nil
        )
        
        XCTAssertEqual(train.delayMinutes, 15)
        XCTAssertEqual(train.status, .delayed)
    }
    
    func testTrainStatus() {
        // Test different status cases
        XCTAssertNotNil(TrainStatus.onTime)
        XCTAssertNotNil(TrainStatus.delayed)
        XCTAssertNotNil(TrainStatus.boarding)
        XCTAssertNotNil(TrainStatus.departed)
        XCTAssertNotNil(TrainStatus.scheduled)
    }
}