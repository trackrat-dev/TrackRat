import XCTest
@testable import TrackRat

extension XCTestCase {
    
    func createTestTrain(
        id: Int = 1,
        trainId: String = "123",
        trainLine: String = "Northeast Corridor",
        destination: String = "New York Penn Station",
        departureTime: Date = Date(),
        track: String? = "1",
        status: TrainStatus = .onTime,
        delayMinutes: Int? = nil,
        originStationCode: String = "NP",
        dataSource: String = "NJTransit"
    ) -> Train {
        return Train(
            id: id,
            trainId: trainId,
            line: trainLine,
            destination: destination,
            departureTime: departureTime,
            track: track,
            status: status,
            delayMinutes: delayMinutes,
            stops: nil,
            predictionData: nil,
            originStationCode: originStationCode,
            dataSource: dataSource,
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
    }
    
    func assertTrainEquals(
        _ train: Train,
        id: Int,
        trainId: String,
        trainLine: String,
        destination: String,
        status: TrainStatus,
        file: StaticString = #file,
        line: UInt = #line
    ) {
        XCTAssertEqual(train.id, id, "Train ID should match", file: file, line: line)
        XCTAssertEqual(train.trainId, trainId, "Train ID string should match", file: file, line: line)
        XCTAssertEqual(train.line, trainLine, "Train line should match", file: file, line: line)
        XCTAssertEqual(train.destination, destination, "Train destination should match", file: file, line: line)
        XCTAssertEqual(train.status, status, "Train status should match", file: file, line: line)
    }
    
    func assertThrowsError<T>(_ expression: @autoclosure () throws -> T, file: StaticString = #file, line: UInt = #line, _ handler: (Error) -> Void = { _ in }) {
        XCTAssertThrowsError(try expression(), file: file, line: line, handler)
    }
    
    func assertNoThrow<T>(_ expression: @autoclosure () throws -> T, file: StaticString = #file, line: UInt = #line) -> T? {
        do {
            return try expression()
        } catch {
            XCTFail("Expression should not throw error: \(error)", file: file, line: line)
            return nil
        }
    }
    
    func expectation(description: String, fulfillmentCount: Int = 1) -> XCTestExpectation {
        let expectation = expectation(description: description)
        expectation.expectedFulfillmentCount = fulfillmentCount
        return expectation
    }
}