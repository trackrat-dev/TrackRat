```swift
import XCTest
import Combine
@testable import TrackRat // Assuming your app module is named TrackRat

// Mock APIService
class MockAPIService: APIService {
    var searchTrainsResult: Result<[TrackRat.Train], Error>?
    var trainsToReturn: [TrackRat.Train] = []
    var searchTrainsCallCount = 0
    var lastFromStationCode: String?
    var lastToStationCode: String?

    override func searchTrains(fromStationCode: String, toStationCode: String) async throws -> [TrackRat.Train] {
        searchTrainsCallCount += 1
        lastFromStationCode = fromStationCode
        lastToStationCode = toStationCode

        if let result = searchTrainsResult {
            switch result {
            case .success(let trains):
                return trains
            case .failure(let error):
                throw error
            }
        }
        return trainsToReturn // Return pre-set trains if no result is set
    }
}

// Helper to create Date objects from strings easily
func dateFromString(_ dateString: String, format: String = "yyyy-MM-dd HH:mm:ss") -> Date {
    let dateFormatter = DateFormatter()
    dateFormatter.dateFormat = format
    dateFormatter.timeZone = TimeZone(secondsFromGMT: 0) // Use UTC for consistency in tests
    return dateFormatter.date(from: dateString)!
}

// Global static station codes for tests
let TEST_STATION_A = "STA"
let TEST_STATION_B = "STB"
let TEST_STATION_C = "STC"


class TrainListViewModelTests: XCTestCase {
    var viewModel: TrainListViewModel!
    var mockAPIService: MockAPIService!
    private var cancellables: Set<AnyCancellable>!

    // Store the original shared instance
    static var originalSharedAPIService: APIService?

    override func setUp() {
        super.setUp()

        // Save the original shared instance if not already saved
        if TrainListViewModelTests.originalSharedAPIService == nil {
            TrainListViewModelTests.originalSharedAPIService = APIService.shared
        }

        mockAPIService = MockAPIService()
        APIService.shared = mockAPIService // Replace shared instance with mock

        viewModel = TrainListViewModel() // Now uses the mocked APIService.shared
        cancellables = []

        // Mock Stations.getStationCode - this is also tricky without modifying Stations.
        // We'll assume "DEST_CODE" is returned for "Destination"
        // Ideally, `Stations` would also be injectable or have a test mode.
    }

    override func tearDown() {
        // Restore the original shared instance
        if let original = TrainListViewModelTests.originalSharedAPIService {
            APIService.shared = original
        }
        // Don't nullify originalSharedAPIService here if tests run in parallel or if
        // the test runner reuses the class instance for multiple test methods.
        // Standard XCTest behavior is new class instance per test method, so nullifying after class is fine.
        // For safety during multiple test classes, it's better to handle this in a suite-level setup/teardown if possible,
        // or ensure each class saves/restores independently. The static var approach is per-class.

        viewModel = nil
        mockAPIService = nil
        cancellables = nil
        super.tearDown()
    }

    // Helper to create test Train instances
    // Ensure `departureTime` is the generic one, and `stops` contains specific departure time for `fromStationCode`
    func createTestTrain(id: Int, trainId: String, genericDepartureTime: Date, stationSpecificStops: [TrackRat.Stop]) -> TrackRat.Train {
        return TrackRat.Train(
            id: id,
            trainId: trainId,
            line: "TestLine",
            destination: "TestDestination",
            departureTime: genericDepartureTime, // Generic departure time
            track: "1",
            status: .scheduled,
            delayMinutes: 0,
            stops: stationSpecificStops, // Specific stops for getDepartureTime
            predictionData: nil,
            originStationCode: stationSpecificStops.first?.stationCode, // Assume first stop is origin
            dataSource: "test",
            consolidatedId: "cons-\(id)",
            originStation: TrackRat.OriginStation(code: stationSpecificStops.first?.stationCode ?? "", name: stationSpecificStops.first?.stationName ?? "", departureTime: stationSpecificStops.first?.departureTime ?? genericDepartureTime),
            dataSources: nil,
            currentPosition: nil,
            trackAssignment: nil,
            statusSummary: TrackRat.StatusSummary(currentStatus: "Scheduled", delayMinutes: 0, onTimePerformance: "100%"),
            consolidationMetadata: TrackRat.ConsolidationMetadata(sourceCount: 1, lastUpdate: Date(), confidenceScore: 1.0)
        )
    }

    // Helper to create a Stop for testing purposes
    func createTestStop(stationCode: String, stationName: String, departureTime: Date) -> TrackRat.Stop {
        return TrackRat.Stop(
            stationCode: stationCode,
            stationName: stationName,
            scheduledTime: departureTime, // Using departureTime for scheduledTime for simplicity
            departureTime: departureTime,
            pickupOnly: false,
            dropoffOnly: false,
            departed: false,
            departedConfirmedBy: nil,
            stopStatus: "On Time",
            platform: "A"
        )
    }


    func testLoadTrains_SortsCorrectlyByStationSpecificDepartureTime() async {
        // Arrange
        let fromStation = TEST_STATION_A

        // Train 1: Departs STA at 10:00, Generic departure at 09:00
        let train1_STA_Departure = dateFromString("2023-01-01 10:00:00")
        let train1_Generic_Departure = dateFromString("2023-01-01 09:00:00")
        let train1_stop_STA = createTestStop(stationCode: TEST_STATION_A, stationName: "Station A", departureTime: train1_STA_Departure)
        let train1 = createTestTrain(id: 1, trainId: "T1", genericDepartureTime: train1_Generic_Departure, stationSpecificStops: [train1_stop_STA])

        // Train 2: Departs STA at 09:30, Generic departure at 08:30
        let train2_STA_Departure = dateFromString("2023-01-01 09:30:00")
        let train2_Generic_Departure = dateFromString("2023-01-01 08:30:00")
        let train2_stop_STA = createTestStop(stationCode: TEST_STATION_A, stationName: "Station A", departureTime: train2_STA_Departure)
        let train2 = createTestTrain(id: 2, trainId: "T2", genericDepartureTime: train2_Generic_Departure, stationSpecificStops: [train2_stop_STA])

        mockAPIService.trainsToReturn = [train1, train2] // API returns them in this order initially

        // Act
        // Need to mock Stations.getStationCode("Destination") to return something for the API call to proceed
        // This is a limitation. For now, we assume it works or the API call doesn't strictly need it for this test path if mocked.
        // The current APIService.searchTrains doesn't use the destination code internally if mocked.
        await viewModel.loadTrains(destination: "Destination", fromStationCode: fromStation)

        // Assert
        XCTAssertEqual(viewModel.trains.count, 2)
        XCTAssertEqual(viewModel.trains.map { $0.id }, [2, 1], "Trains should be sorted by station-specific departure time (T2 then T1)")
        // Verify T2 (09:30 from STA) is before T1 (10:00 from STA)
        if viewModel.trains.count == 2 {
             XCTAssertTrue(train2.getDepartureTime(fromStationCode: fromStation) < train1.getDepartureTime(fromStationCode: fromStation))
             XCTAssertEqual(viewModel.trains[0].id, 2)
             XCTAssertEqual(viewModel.trains[1].id, 1)
        }
    }

    func testRefreshTrains_MaintainsCorrectSortOrderWithStationSpecificTimes() async {
        // Arrange: Initial load
        let fromStation = TEST_STATION_A

        // Train 1: Departs STA at 10:00
        let train1_STA_Departure = dateFromString("2023-01-01 10:00:00")
        let train1_Generic_Departure = dateFromString("2023-01-01 09:00:00")
        let train1_stop_STA = createTestStop(stationCode: TEST_STATION_A, stationName: "Station A", departureTime: train1_STA_Departure)
        let train1 = createTestTrain(id: 1, trainId: "T1", genericDepartureTime: train1_Generic_Departure, stationSpecificStops: [train1_stop_STA])

        // Train 2: Departs STA at 11:00
        let train2_STA_Departure = dateFromString("2023-01-01 11:00:00")
        let train2_Generic_Departure = dateFromString("2023-01-01 08:30:00") // Generic earlier than T1's generic
        let train2_stop_STA = createTestStop(stationCode: TEST_STATION_A, stationName: "Station A", departureTime: train2_STA_Departure)
        let train2 = createTestTrain(id: 2, trainId: "T2", genericDepartureTime: train2_Generic_Departure, stationSpecificStops: [train2_stop_STA])

        mockAPIService.trainsToReturn = [train1, train2] // Correctly sorted by station time
        await viewModel.loadTrains(destination: "Destination", fromStationCode: fromStation)
        XCTAssertEqual(viewModel.trains.map { $0.id }, [1, 2], "Initial load sort order incorrect. Expected T1 (10:00), T2 (11:00)")

        // Arrange: Refresh data - introduces a new train that should be first
        // Train 3 (New): Departs STA at 09:00, Generic departure at 09:00
        let train3_STA_Departure = dateFromString("2023-01-01 09:00:00")
        let train3_Generic_Departure = dateFromString("2023-01-01 09:00:00")
        let train3_stop_STA = createTestStop(stationCode: TEST_STATION_A, stationName: "Station A", departureTime: train3_STA_Departure)
        let train3 = createTestTrain(id: 3, trainId: "T3", genericDepartureTime: train3_Generic_Departure, stationSpecificStops: [train3_stop_STA])

        mockAPIService.trainsToReturn = [train1, train3, train2] // Deliberately unsorted by station time for refresh

        // Act
        await viewModel.refreshTrains()

        // Assert
        XCTAssertEqual(viewModel.trains.count, 3)
        // Expected order by station-specific time: T3 (09:00), T1 (10:00), T2 (11:00)
        XCTAssertEqual(viewModel.trains.map { $0.id }, [3, 1, 2], "Trains should be re-sorted correctly by station-specific time after refresh")

        if viewModel.trains.count == 3 {
            let t3_time = viewModel.trains[0].getDepartureTime(fromStationCode: fromStation)
            let t1_time = viewModel.trains[1].getDepartureTime(fromStationCode: fromStation)
            let t2_time = viewModel.trains[2].getDepartureTime(fromStationCode: fromStation)
            XCTAssertEqual(viewModel.trains[0].id, 3)
            XCTAssertEqual(viewModel.trains[1].id, 1)
            XCTAssertEqual(viewModel.trains[2].id, 2)
            XCTAssertTrue(t3_time < t1_time, "T3 departure (\(t3_time)) should be before T1 (\(t1_time))")
            XCTAssertTrue(t1_time < t2_time, "T1 departure (\(t1_time)) should be before T2 (\(t2_time))")
        }
    }

    func testRefreshTrains_HandlesExistingTrainUpdateAndSort() async {
        // Arrange: Initial load
        let fromStation = TEST_STATION_A

        // Train 1: Departs STA at 10:00
        let train1_STA_InitialDeparture = dateFromString("2023-01-01 10:00:00")
        let train1_Generic_Departure = dateFromString("2023-01-01 09:00:00")
        let train1_stop_STA_Initial = createTestStop(stationCode: TEST_STATION_A, stationName: "Station A", departureTime: train1_STA_InitialDeparture)
        let train1 = createTestTrain(id: 1, trainId: "T1", genericDepartureTime: train1_Generic_Departure, stationSpecificStops: [train1_stop_STA_Initial])

        // Train 2: Departs STA at 11:00
        let train2_STA_Departure = dateFromString("2023-01-01 11:00:00")
        let train2_Generic_Departure = dateFromString("2023-01-01 08:30:00")
        let train2_stop_STA = createTestStop(stationCode: TEST_STATION_A, stationName: "Station A", departureTime: train2_STA_Departure)
        let train2 = createTestTrain(id: 2, trainId: "T2", genericDepartureTime: train2_Generic_Departure, stationSpecificStops: [train2_stop_STA])

        mockAPIService.trainsToReturn = [train1, train2]
        await viewModel.loadTrains(destination: "Destination", fromStationCode: fromStation)
        XCTAssertEqual(viewModel.trains.map { $0.id }, [1, 2], "Initial load sort order incorrect. Expected T1 (10:00), T2 (11:00)")

        // Arrange: Refresh data - Train 1 is now delayed and should appear after Train 2
        // Updated Train 1: Now departs STA at 12:00
        let train1_STA_UpdatedDeparture = dateFromString("2023-01-01 12:00:00")
        let train1_stop_STA_Updated = createTestStop(stationCode: TEST_STATION_A, stationName: "Station A", departureTime: train1_STA_UpdatedDeparture)
        let updatedTrain1 = createTestTrain(id: 1, trainId: "T1", genericDepartureTime: train1_Generic_Departure, stationSpecificStops: [train1_stop_STA_Updated])

        mockAPIService.trainsToReturn = [updatedTrain1, train2] // API returns updated T1 and T2

        // Act
        await viewModel.refreshTrains()

        // Assert
        XCTAssertEqual(viewModel.trains.count, 2)
        // Expected order by station-specific time: T2 (11:00), Updated T1 (12:00)
        XCTAssertEqual(viewModel.trains.map { $0.id }, [2, 1], "Trains should be re-sorted correctly after an update causes reordering")

        if viewModel.trains.count == 2 {
            let t2_time = viewModel.trains[0].getDepartureTime(fromStationCode: fromStation) // Should be T2
            let t1_updated_time = viewModel.trains[1].getDepartureTime(fromStationCode: fromStation) // Should be updated T1
            XCTAssertEqual(viewModel.trains[0].id, 2)
            XCTAssertEqual(viewModel.trains[1].id, 1)
            XCTAssertTrue(t2_time < t1_updated_time, "T2 departure (\(t2_time)) should be before updated T1 (\(t1_updated_time))")
        }
    }
}
```
