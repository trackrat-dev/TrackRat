import XCTest
@testable import TrackRat

class TrainTests: XCTestCase {

    // MARK: - Initialization Tests

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
            dataSource: "NJTransit"
        )

        XCTAssertEqual(train.delayMinutes, 15)
        XCTAssertEqual(train.status, .delayed)
    }

    func testTrainWithStops() {
        let stops = [
            Stop.mock(stationName: "Newark Penn Station", stationCode: "NP"),
            Stop.mock(stationName: "New York Penn Station", stationCode: "NY")
        ]

        let train = Train(
            id: 1,
            trainId: "123",
            line: "Northeast Corridor",
            destination: "New York Penn Station",
            departureTime: Date(),
            track: "1",
            status: .onTime,
            delayMinutes: nil,
            stops: stops,
            predictionData: nil,
            originStationCode: "NP",
            dataSource: "NJTransit"
        )

        XCTAssertEqual(train.stops?.count, 2)
        XCTAssertEqual(train.stops?[0].stationCode, "NP")
        XCTAssertEqual(train.stops?[1].stationCode, "NY")
    }

    // MARK: - Codable Tests

    func testTrainJSONDecoding() {
        let jsonString = TrainTestData.sampleTrainJSON

        do {
            let train = try TestHelpers.decodeJSON(Train.self, from: jsonString)
            XCTAssertEqual(train.trainId, "123")
            XCTAssertEqual(train.line, "Northeast Corridor")
            XCTAssertEqual(train.destination, "New York Penn Station")
            XCTAssertEqual(train.track, "1")
            XCTAssertEqual(train.originStationCode, "NP")
            XCTAssertEqual(train.dataSource, "NJT")
        } catch {
            XCTFail("Should be able to decode Train from JSON. Error: \(error)")
        }
    }

    func testTrainJSONEncoding() {
        let train = TrainTestData.sampleTrain()

        do {
            let data = try JSONEncoder().encode(train)
            let decoded = try JSONDecoder().decode(Train.self, from: data)

            XCTAssertEqual(train.trainId, decoded.trainId)
            XCTAssertEqual(train.line, decoded.line)
            XCTAssertEqual(train.destination, decoded.destination)
            XCTAssertEqual(train.track, decoded.track)
        } catch {
            XCTFail("Should be able to encode/decode Train. Error: \(error)")
        }
    }

    func testInvalidTrainJSONDecoding() {
        let invalidJSON = """
        {
            "train_id": "123",
            "line": "Northeast Corridor",
            "invalid_field": "should cause error"
        }
        """

        let data = invalidJSON.data(using: .utf8)!
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        XCTAssertThrowsError(try decoder.decode(Train.self, from: data)) { error in
            XCTAssertTrue(error is DecodingError)
        }
    }

    // MARK: - Origin-Aware Methods Tests

    func testGetDepartureTimeFromOrigin() {
        let baseTime = Date()
        let npDepartureTime = Calendar.current.date(byAdding: .minute, value: 10, to: baseTime)!
        let nyDepartureTime = Calendar.current.date(byAdding: .minute, value: 30, to: baseTime)!

        let stops = [
            Stop.mock(
                stationName: "Newark Penn Station",
                stationCode: "NP",
                scheduledTime: npDepartureTime,
                departureTime: npDepartureTime
            ),
            Stop.mock(
                stationName: "New York Penn Station",
                stationCode: "NY",
                scheduledTime: nyDepartureTime,
                departureTime: nyDepartureTime
            )
        ]

        let train = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: baseTime,
            track: "1", status: .onTime, delayMinutes: nil,
            stops: stops, predictionData: nil, originStationCode: "NP",
            dataSource: "NJTransit"
        )

        let npTime = train.getDepartureTime(fromStationCode: "NP")
        let nyTime = train.getDepartureTime(fromStationCode: "NY")
        let fallbackTime = train.getDepartureTime(fromStationCode: "UNKNOWN")

        XCTAssertEqual(npTime, npDepartureTime)
        XCTAssertEqual(nyTime, nyDepartureTime)
        XCTAssertEqual(fallbackTime, baseTime) // Falls back to train's departure time
    }

    func testGetFormattedDepartureTime() {
        let train = TrainTestData.sampleTrain()
        let formatted = train.getFormattedDepartureTime(fromStationCode: "NP")

        XCTAssertFalse(formatted.isEmpty)
        XCTAssertTrue(formatted.contains(":")) // Should contain time separator

        // Test with Eastern Time formatting
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        let expected = formatter.string(from: train.getDepartureTime(fromStationCode: "NP"))

        XCTAssertEqual(formatted, expected)
    }

    // MARK: - Track Properties Tests

    func testDisplayTrackProperties() {
        // Test basic track property
        let basicTrain = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: Date(),
            track: "1", status: .onTime, delayMinutes: nil,
            stops: nil, predictionData: nil, originStationCode: "NP",
            dataSource: "NJTransit"
        )
        XCTAssertEqual(basicTrain.track, "1")
        XCTAssertEqual(basicTrain.displayTrack, "1")
    }

    func testGetTrackForStation() {
        let train = TrainTestData.sampleTrain()

        // Test getting track for origin station
        let track = train.getTrackForStation("NP")

        // Should return the train's track since no specific track assignment
        XCTAssertEqual(track, train.track)
    }

    // MARK: - Consolidated Data Tests

    func testIsConsolidated() {
        // Test non-consolidated train
        let basicTrain = TrainTestData.sampleTrain()
        XCTAssertFalse(basicTrain.isConsolidated)

        // Test consolidated train
        let consolidatedTrain = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: Date(),
            track: "1", status: .onTime, delayMinutes: nil,
            stops: nil, predictionData: nil, originStationCode: "NP",
            dataSource: "NJTransit", consolidatedId: "consolidated_123"
        )
        XCTAssertTrue(consolidatedTrain.isConsolidated)
    }

    // MARK: - Status Tests

    func testTrainStatusValues() {
        let onTimeTrain = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: Date(),
            track: "1", status: .onTime, delayMinutes: nil,
            stops: nil, predictionData: nil, originStationCode: "NP",
            dataSource: "NJTransit"
        )
        XCTAssertEqual(onTimeTrain.status, .onTime)

        let delayedTrain = Train(
            id: 2, trainId: "124", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: Date(),
            track: "2", status: .delayed, delayMinutes: 10,
            stops: nil, predictionData: nil, originStationCode: "NP",
            dataSource: "NJTransit"
        )
        XCTAssertEqual(delayedTrain.status, .delayed)
        XCTAssertEqual(delayedTrain.delayMinutes, 10)
    }

    // MARK: - Stop Interaction Tests

    func testNormalizedStops() {
        let stops = [
            Stop.mock(stationName: "Newark Penn Station", stationCode: "NP"),
            Stop.mock(stationName: "New York Penn Station", stationCode: "NY")
        ]

        let train = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: Date(),
            track: "1", status: .onTime, delayMinutes: nil,
            stops: stops, predictionData: nil, originStationCode: "NP",
            dataSource: "NJTransit"
        )

        let normalizedStops = train.normalizedStops
        XCTAssertEqual(normalizedStops.count, 2)
        XCTAssertEqual(normalizedStops[0].stationCode, "NP")
        XCTAssertEqual(normalizedStops[1].stationCode, "NY")
    }

    // MARK: - Prediction Data Tests

    func testTrainWithPredictionData() {
        let predictionData = TrainTestData.createMockPredictionData()

        let train = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: Date(),
            track: "1", status: .onTime, delayMinutes: nil,
            stops: nil, predictionData: predictionData, originStationCode: "NP",
            dataSource: "NJTransit"
        )

        XCTAssertNotNil(train.predictionData)
        XCTAssertNotNil(train.predictionData?.trackProbabilities)
    }

    // MARK: - Edge Cases

    func testTrainWithNilValues() {
        let train = Train(
            id: 1,
            trainId: "123",
            line: "Northeast Corridor",
            destination: "New York Penn Station",
            departureTime: Date(),
            track: nil, // Nil track
            status: .onTime,
            delayMinutes: nil, // Nil delay
            stops: nil, // Nil stops
            predictionData: nil, // Nil predictions
            originStationCode: nil, // Nil origin
            dataSource: "NJTransit"
        )

        XCTAssertNil(train.track)
        XCTAssertNil(train.delayMinutes)
        XCTAssertNil(train.stops)
        XCTAssertNil(train.predictionData)
        XCTAssertNil(train.originStationCode)
    }

    func testTrainDisplayTrackWithNilTrack() {
        let train = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: Date(),
            track: nil, status: .onTime, delayMinutes: nil,
            stops: nil, predictionData: nil, originStationCode: "NP",
            dataSource: "NJTransit"
        )

        XCTAssertNil(train.displayTrack)
    }

    // MARK: - Complex Object Tests

    func testTrainWithComplexStops() {
        let stops = TrainTestData.consolidatedStops()

        let train = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "Trenton", departureTime: Date(),
            track: "1", status: .onTime, delayMinutes: nil,
            stops: stops, predictionData: nil, originStationCode: "NY",
            dataSource: "NJTransit"
        )

        XCTAssertEqual(train.stops?.count, 5)
        XCTAssertEqual(train.stops?[0].stationCode, "NY")
        XCTAssertEqual(train.stops?[4].stationCode, "TRE")
    }

    // MARK: - Initialization Edge Cases

    func testMinimalTrainInitialization() {
        // Test with only required parameters
        let train = Train(
            id: 1,
            trainId: "MINIMAL",
            line: "Test Line",
            destination: "Test Destination",
            departureTime: Date(),
            track: nil,
            status: .scheduled,
            delayMinutes: nil,
            stops: nil,
            predictionData: nil,
            originStationCode: nil,
            dataSource: nil
        )

        XCTAssertEqual(train.trainId, "MINIMAL")
        XCTAssertEqual(train.line, "Test Line")
        XCTAssertEqual(train.destination, "Test Destination")
        XCTAssertEqual(train.status, .scheduled)
    }
}