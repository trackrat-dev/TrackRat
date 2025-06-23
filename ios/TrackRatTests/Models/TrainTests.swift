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
    
    // MARK: - JSON Decoding Tests
    
    func testLegacyTrainJSONDecoding() throws {
        let json = """
        {
            "id": 1,
            "train_id": "123",
            "line": "Northeast Corridor",
            "destination": "New York Penn Station",
            "departure_time": "2024-01-01T10:00:00-05:00",
            "track": "1",
            "status": "ON_TIME",
            "delay_minutes": null,
            "origin_station_code": "NP",
            "data_source": "NJTransit"
        }
        """
        
        let data = json.data(using: .utf8)!
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        
        let train = try decoder.decode(Train.self, from: data)
        
        XCTAssertEqual(train.id, 1)
        XCTAssertEqual(train.trainId, "123")
        XCTAssertEqual(train.line, "Northeast Corridor")
        XCTAssertEqual(train.destination, "New York Penn Station")
        XCTAssertEqual(train.track, "1")
        XCTAssertEqual(train.status, .onTime)
        XCTAssertNil(train.delayMinutes)
        XCTAssertEqual(train.originStationCode, "NP")
        XCTAssertEqual(train.dataSource, "NJTransit")
        XCTAssertNil(train.consolidatedId)
        XCTAssertFalse(train.isConsolidated)
    }
    
    func testConsolidatedTrainJSONDecoding() throws {
        let json = """
        {
            "consolidated_id": "amtrak_123_njtransit_456",
            "train_id": "123",
            "line": "Northeast Corridor",
            "destination": "New York Penn Station",
            "origin_station": {
                "code": "NP",
                "name": "Newark Penn Station",
                "departure_time": "2024-01-01T10:00:00-05:00"
            },
            "track_assignment": {
                "track": "2",
                "assigned_at": "2024-01-01T09:45:00-05:00",
                "assigned_by": "Dispatcher",
                "source": "NJTransit"
            },
            "status_summary": {
                "current_status": "on time",
                "delay_minutes": 0,
                "on_time_performance": "good"
            },
            "data_sources": [
                {
                    "origin": "NP",
                    "data_source": "NJTransit",
                    "last_update": "2024-01-01T09:30:00-05:00",
                    "status": "ON_TIME",
                    "track": "2",
                    "delay_minutes": 0,
                    "db_id": 123
                }
            ]
        }
        """
        
        do {
            let train = try TestHelpers.decodeJSON(Train.self, from: json)
            
            XCTAssertEqual(train.consolidatedId, "amtrak_123_njtransit_456")
            XCTAssertEqual(train.trainId, "123")
            XCTAssertEqual(train.line, "Northeast Corridor")
            XCTAssertEqual(train.destination, "New York Penn Station")
            XCTAssertEqual(train.displayTrack, "2")
            XCTAssertEqual(train.displayStatus, .onTime)
            XCTAssertEqual(train.displayDelayMinutes, 0)
            XCTAssertEqual(train.originStationCode, "NP")
            XCTAssertEqual(train.dataSource, "NJTransit")
            XCTAssertTrue(train.isConsolidated)
            XCTAssertNotNil(train.originStation)
            XCTAssertNotNil(train.trackAssignment)
            XCTAssertNotNil(train.statusSummary)
            XCTAssertEqual(train.dataSources?.count, 1)
        } catch {
            XCTFail("Should be able to decode consolidated train from JSON. Error: \(error)")
        }
    }
    
    func testEnhancedFieldsDecoding() throws {
        let json = """
        {
            "id": 1,
            "train_id": "123",
            "line": "Northeast Corridor",
            "destination": "New York Penn Station",
            "departure_time": "2024-01-01T10:00:00-05:00",
            "track": "1",
            "status": "BOARDING",
            "origin_station_code": "NP",
            "data_source": "NJTransit",
            "status_v2": {
                "current": "BOARDING",
                "location": "Platform 1",
                "updated_at": "2024-01-01T09:58:00-05:00",
                "confidence": "high",
                "source": "NJTransit"
            },
            "progress": {
                "last_departed": {
                    "station_code": "NP",
                    "departed_at": "2024-01-01T09:45:00-05:00",
                    "delay_minutes": 0
                },
                "next_arrival": {
                    "station_code": "NY",
                    "scheduled_arrival": "2024-01-01T10:15:00-05:00",
                    "estimated_time": "2024-01-01T10:15:00-05:00",
                    "minutes_away": 15
                },
                "journey_percent": 25,
                "stops_completed": 1,
                "total_stops": 4
            }
        }
        """
        
        do {
            let train = try TestHelpers.decodeJSON(Train.self, from: json)
            
            XCTAssertNotNil(train.statusV2)
            XCTAssertEqual(train.statusV2?.current, "BOARDING")
            XCTAssertEqual(train.statusV2?.location, "Platform 1")
            XCTAssertEqual(train.statusV2?.confidence, "high")
            XCTAssertEqual(train.enhancedDisplayStatus, "BOARDING")
            XCTAssertEqual(train.displayLocation, "Platform 1")
            
            XCTAssertNotNil(train.progress)
            XCTAssertEqual(train.progress?.journeyPercent, 25)
            XCTAssertEqual(train.progress?.stopsCompleted, 1)
            XCTAssertEqual(train.progress?.totalStops, 4)
            XCTAssertNotNil(train.journeyProgress)
            XCTAssertEqual(train.progress?.nextArrival?.minutesAway, 15)
        } catch {
            XCTFail("Should be able to decode enhanced train from JSON. Error: \(error)")
        }
    }
    
    func testMalformedJSONHandling() {
        let json = """
        {
            "id": "invalid",
            "train_id": 123,
            "line": null,
            "destination": "",
            "departure_time": "invalid-date",
            "status": "INVALID_STATUS"
        }
        """
        
        let data = json.data(using: .utf8)!
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
            Stop(stationCode: "NP", stationName: "Newark Penn Station", 
                 scheduledTime: npDepartureTime, departureTime: npDepartureTime,
                 pickupOnly: false, dropoffOnly: false, departed: false,
                 departedConfirmedBy: nil, stopStatus: nil, platform: nil),
            Stop(stationCode: "NY", stationName: "New York Penn Station",
                 scheduledTime: nyDepartureTime, departureTime: nyDepartureTime,
                 pickupOnly: false, dropoffOnly: false, departed: false,
                 departedConfirmedBy: nil, stopStatus: nil, platform: nil)
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
    
    // MARK: - Enhanced Properties Tests
    
    func testDisplayTrackProperties() {
        // Test legacy track
        let legacyTrain = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: Date(),
            track: "1", status: .onTime, delayMinutes: nil,
            stops: nil, predictionData: nil, originStationCode: "NP",
            dataSource: "NJTransit"
        )
        XCTAssertEqual(legacyTrain.displayTrack, "1")
        
        // Test consolidated track assignment
        let trackAssignment = TrackAssignment(track: "2", assignedAt: Date(), assignedBy: "System", source: "NJTransit")
        let consolidatedTrain = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: Date(),
            track: "1", status: .onTime, delayMinutes: nil,
            stops: nil, predictionData: nil, originStationCode: "NP",
            dataSource: "NJTransit", consolidatedId: "consolidated_123",
            trackAssignment: trackAssignment
        )
        XCTAssertEqual(consolidatedTrain.displayTrack, "2") // Prefers consolidated
    }
    
    func testDisplayStatusProperties() {
        // Test legacy status
        let legacyTrain = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: Date(),
            track: "1", status: .delayed, delayMinutes: 10,
            stops: nil, predictionData: nil, originStationCode: "NP",
            dataSource: "NJTransit"
        )
        XCTAssertEqual(legacyTrain.displayStatus, .delayed)
        XCTAssertEqual(legacyTrain.enhancedDisplayStatus, "Delayed")
        XCTAssertNil(legacyTrain.displayLocation)
        
        // Test enhanced status with StatusV2
        let statusV2 = StatusV2(current: "BOARDING", location: "Platform 3", 
                               updatedAt: Date(), confidence: "high", source: "NJTransit")
        let enhancedTrain = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: Date(),
            track: "1", status: .scheduled, delayMinutes: nil,
            stops: nil, predictionData: nil, originStationCode: "NP",
            dataSource: "NJTransit", statusV2: statusV2
        )
        XCTAssertEqual(enhancedTrain.enhancedDisplayStatus, "BOARDING")
        XCTAssertEqual(enhancedTrain.displayLocation, "Platform 3")
    }
    
    func testDisplayDelayProperties() {
        // Test legacy delay
        let legacyTrain = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: Date(),
            track: "1", status: .delayed, delayMinutes: 15,
            stops: nil, predictionData: nil, originStationCode: "NP",
            dataSource: "NJTransit"
        )
        XCTAssertEqual(legacyTrain.displayDelayMinutes, 15)
        
        // Test consolidated delay
        let statusSummary = StatusSummary(currentStatus: "delayed", delayMinutes: 20, onTimePerformance: "poor")
        let consolidatedTrain = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: Date(),
            track: "1", status: .delayed, delayMinutes: 15,
            stops: nil, predictionData: nil, originStationCode: "NP",
            dataSource: "NJTransit", statusSummary: statusSummary
        )
        XCTAssertEqual(consolidatedTrain.displayDelayMinutes, 20) // Prefers consolidated
    }
    
    func testPositionTrackingProperties() {
        let currentPosition = CurrentPosition(
            status: "en_route", lastDepartedStation: nil, nextStation: nil,
            segmentProgress: 0.75, estimatedSpeedMph: 65.0
        )
        
        let train = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: Date(),
            track: "1", status: .departed, delayMinutes: nil,
            stops: nil, predictionData: nil, originStationCode: "NP",
            dataSource: "NJTransit", currentPosition: currentPosition
        )
        
        XCTAssertTrue(train.hasPositionTracking)
        XCTAssertEqual(train.segmentProgress, 0.75)
        XCTAssertEqual(train.estimatedSpeed, 65.0)
        
        // Test train without position tracking
        let basicTrain = TrainTestData.sampleTrain()
        XCTAssertFalse(basicTrain.hasPositionTracking)
        XCTAssertEqual(basicTrain.segmentProgress, 0.0)
        XCTAssertNil(basicTrain.estimatedSpeed)
    }
    
    func testConsolidationProperties() {
        // Test non-consolidated train
        let singleTrain = TrainTestData.sampleTrain()
        XCTAssertFalse(singleTrain.isConsolidated)
        
        // Test consolidated train with multiple sources
        let dataSources = [
            DataSource(origin: "NP", dataSource: "NJTransit", lastUpdate: Date(), 
                      status: "ON_TIME", track: "1", delayMinutes: 0, dbId: 123),
            DataSource(origin: "NP", dataSource: "Amtrak", lastUpdate: Date(),
                      status: "ON_TIME", track: "1", delayMinutes: 0, dbId: 456)
        ]
        
        let consolidatedTrain = Train(
            id: 1, trainId: "123", line: "Northeast Corridor",
            destination: "New York Penn Station", departureTime: Date(),
            track: "1", status: .onTime, delayMinutes: nil,
            stops: nil, predictionData: nil, originStationCode: "NP",
            dataSource: "NJTransit", consolidatedId: "consolidated_123",
            dataSources: dataSources
        )
        
        XCTAssertTrue(consolidatedTrain.isConsolidated)
    }
    
    // MARK: - TrainStatus Tests
    
    func testTrainStatusEnum() {
        XCTAssertEqual(TrainStatus.scheduled.displayText, "Scheduled")
        XCTAssertEqual(TrainStatus.onTime.displayText, "On Time")
        XCTAssertEqual(TrainStatus.delayed.displayText, "Delayed")
        XCTAssertEqual(TrainStatus.boarding.displayText, "Boarding")
        XCTAssertEqual(TrainStatus.departed.displayText, "Departed")
        XCTAssertEqual(TrainStatus.unknown.displayText, "Unknown")
        
        XCTAssertEqual(TrainStatus.scheduled.color, "gray")
        XCTAssertEqual(TrainStatus.onTime.color, "green")
        XCTAssertEqual(TrainStatus.delayed.color, "red")
        XCTAssertEqual(TrainStatus.boarding.color, "orange")
        XCTAssertEqual(TrainStatus.departed.color, "gray")
        XCTAssertEqual(TrainStatus.unknown.color, "gray")
    }
    
    func testTrainStatusDecoding() throws {
        // Test empty string handling
        let emptyJson = "\"\"" 
        let emptyData = emptyJson.data(using: .utf8)!
        let decoder = JSONDecoder()
        let emptyStatus = try decoder.decode(TrainStatus.self, from: emptyData)
        XCTAssertEqual(emptyStatus, .scheduled)
        
        // Test unknown status handling
        let unknownJson = "\"INVALID_STATUS\""
        let unknownData = unknownJson.data(using: .utf8)!
        let unknownStatus = try decoder.decode(TrainStatus.self, from: unknownData)
        XCTAssertEqual(unknownStatus, .unknown)
        
        // Test valid status
        let validJson = "\"BOARDING\""
        let validData = validJson.data(using: .utf8)!
        let validStatus = try decoder.decode(TrainStatus.self, from: validData)
        XCTAssertEqual(validStatus, .boarding)
    }
}