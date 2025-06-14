import XCTest
import Combine
@testable import TrackRat

@MainActor
class TrainListViewModelTests: XCTestCase {

    var viewModel: TrainListViewModel!
    var mockAPIService: MockAPIService!
    var cancellables: Set<AnyCancellable>!

    override func setUp() {
        super.setUp()
        mockAPIService = MockAPIService()
        viewModel = TrainListViewModel(apiService: mockAPIService)
        cancellables = []
    }

    override func tearDown() {
        viewModel = nil
        mockAPIService = nil
        cancellables = nil
        super.tearDown()
    }

    // MARK: - Test Cases

    func testLoadTrains_Success() async {
        // Arrange
        let departureTime1 = Date().addingTimeInterval(3600)
        let departureTime2 = Date().addingTimeInterval(7200)
        let expectedTrains = [
            Train.mock(id: 1, trainId: "101", departureTime: departureTime1, stops: [Stop.mock(stationCode: "NYP", departureTime: departureTime1)]),
            Train.mock(id: 2, trainId: "102", departureTime: departureTime2, stops: [Stop.mock(stationCode: "NYP", departureTime: departureTime2)])
        ]
        mockAPIService.searchTrainsResult = .success(expectedTrains)

        let expectation = XCTestExpectation(description: "Trains are loaded")

        viewModel.$trains
            .dropFirst()
            .sink { trains in
                XCTAssertEqual(trains.count, 2)
                XCTAssertEqual(trains.first?.trainId, "101")
                expectation.fulfill()
            }
            .store(in: &cancellables)

        // Act
        await viewModel.loadTrains(destination: "Newark Penn Station", fromStationCode: "NYP")

        // Assert
        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertNil(viewModel.error)
    }

    func testLoadTrains_ApiError() async {
        // Arrange
        mockAPIService.searchTrainsResult = .failure(APIError.invalidURL)
        let expectation = XCTestExpectation(description: "Error is set")

        viewModel.$error
            .dropFirst()
            .sink { error in
                XCTAssertNotNil(error)
                XCTAssertEqual(error, APIError.invalidURL.localizedDescription) // Or your custom error message
                expectation.fulfill()
            }
            .store(in: &cancellables)

        // Act
        await viewModel.loadTrains(destination: "Invalid Destination", fromStationCode: "NYP")

        // Assert
        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertTrue(viewModel.trains.isEmpty)
    }

    func testLoadTrains_FiltersAndSortsTrains() async {
        // Arrange
        let now = Date()
        let earlierTrainDepartureTime = now.addingTimeInterval(2 * 3600)
        let laterTrainDepartureTime = now.addingTimeInterval(3 * 3600)
        let beyond6HoursDepartureTime = now.addingTimeInterval(7 * 3600)

        let earlierTrain = Train.mock(id: 1, trainId: "101", stops: [Stop.mock(stationCode: "NYP", departureTime: earlierTrainDepartureTime)])
        let laterTrainWithin6Hours = Train.mock(id: 2, trainId: "102", stops: [Stop.mock(stationCode: "NYP", departureTime: laterTrainDepartureTime)])
        let trainBeyond6Hours = Train.mock(id: 3, trainId: "103", stops: [Stop.mock(stationCode: "NYP", departureTime: beyond6HoursDepartureTime)])

        // Ensure the top-level departureTime of Train.mock matches the stop's departureTime for consistent sorting if getDepartureTime is not perfectly mocked/used.
        // For these tests, getDepartureTime(fromStationCode:) is the source of truth for filtering and sorting.
        let mockEarlierTrain = Train.mock(id: 1, trainId: "101", departureTime: earlierTrainDepartureTime, stops: [Stop.mock(stationCode: "NYP", departureTime: earlierTrainDepartureTime)])
        let mockLaterTrain = Train.mock(id: 2, trainId: "102", departureTime: laterTrainDepartureTime, stops: [Stop.mock(stationCode: "NYP", departureTime: laterTrainDepartureTime)])
        let mockBeyondHourTrain = Train.mock(id: 3, trainId: "103", departureTime: beyond6HoursDepartureTime, stops: [Stop.mock(stationCode: "NYP", departureTime: beyond6HoursDepartureTime)])


        mockAPIService.searchTrainsResult = .success([mockLaterTrain, mockBeyondHourTrain, mockEarlierTrain])

        let expectation = XCTestExpectation(description: "Trains are filtered and sorted")

        viewModel.$trains
            .dropFirst()
            .sink { trains in
                XCTAssertEqual(trains.count, 2, "Should filter out train departing beyond 6 hours. Found: \(trains.map { $0.trainId } )")
                XCTAssertEqual(trains[0].id, mockEarlierTrain.id, "Trains should be sorted by departure time")
                XCTAssertEqual(trains[1].id, mockLaterTrain.id, "Trains should be sorted by departure time")
                expectation.fulfill()
            }
            .store(in: &cancellables)

        await viewModel.loadTrains(destination: "Destination", fromStationCode: "NYP")

        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertNil(viewModel.error)
    }

    func testRefreshTrains_SuccessUpdatesAndAddsTrainsAndSorts() async {
        let now = Date()
        let departureTime1 = now.addingTimeInterval(1000)
        let departureTime2 = now.addingTimeInterval(2000) // For new train, later
        let departureTime3 = now.addingTimeInterval(500)  // For another new train, earlier

        let initialTrain = Train.mock(id: 1, trainId: "T1", status: .onTime, departureTime: departureTime1, stops: [Stop.mock(stationCode: "NYP", departureTime: departureTime1)])
        viewModel.trains = [initialTrain]
        viewModel.currentDestination = "Destination"
        viewModel.currentFromStationCode = "NYP"

        let updatedTrain1 = Train.mock(id: 1, trainId: "T1", status: .delayed, departureTime: departureTime1, stops: [Stop.mock(stationCode: "NYP", departureTime: departureTime1)])
        let newTrain2 = Train.mock(id: 2, trainId: "T2", status: .onTime, departureTime: departureTime2, stops: [Stop.mock(stationCode: "NYP", departureTime: departureTime2)])
        let newTrain3 = Train.mock(id: 3, trainId: "T3", status: .onTime, departureTime: departureTime3, stops: [Stop.mock(stationCode: "NYP", departureTime: departureTime3)])

        // API returns trains that are filtered by 6hr window and sorted by getDepartureTime(fromStationCode:)
        // Let's emulate that for the mock response
        let apiResponseTrains = [newTrain3, updatedTrain1, newTrain2] // Sorted by departure time from NYP
        mockAPIService.searchTrainsResult = .success(apiResponseTrains)

        let expectation = XCTestExpectation(description: "Trains are refreshed, updated, new ones added, and finally sorted by Train.departureTime")

        var observationCount = 0
        viewModel.$trains
            .sink { trains in
                observationCount += 1
                if observationCount > 1 { // After initial state
                    // Final check: 3 trains, T1 updated, all sorted by Train.departureTime
                    if trains.count == 3 &&
                       trains.first(where: { $0.id == 1 })?.status == .delayed &&
                       trains.map({ $0.id }) == [3, 1, 2] { // Sorted by original departureTime property
                        expectation.fulfill()
                    }
                }
            }
            .store(in: &cancellables)

        await viewModel.refreshTrains()

        await fulfillment(of: [expectation], timeout: 2.0)
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertNil(viewModel.error)
        XCTAssertEqual(viewModel.trains.map({ $0.id }), [3, 1, 2]) // Final assertion on order
        XCTAssertEqual(viewModel.trains.first(where: { $0.id == 1 })?.status, .delayed)
    }

    func testRefreshTrains_HapticFeedbackOnBoarding() async {
        let departureTime = Date().addingTimeInterval(1000)
        let initialTrain = Train.mock(id: 1, trainId: "101", status: .onTime, departureTime: departureTime, stops: [Stop.mock(stationCode: "NYP", departureTime: departureTime)])
        viewModel.trains = [initialTrain]
        viewModel.currentDestination = "Destination"
        viewModel.currentFromStationCode = "NYP"

        let boardingTrain = Train.mock(id: 1, trainId: "101", status: .boarding, departureTime: departureTime, stops: [Stop.mock(stationCode: "NYP", departureTime: departureTime)])
        mockAPIService.searchTrainsResult = .success([boardingTrain])

        let expectation = XCTestExpectation(description: "Train status updates to boarding on refresh")
        var observationCount = 0
        viewModel.$trains
            .sink { trains in
                 observationCount += 1
                if observationCount > 1 && trains.first?.status == .boarding {
                    expectation.fulfill()
                }
            }
            .store(in: &cancellables)

        await viewModel.refreshTrains()

        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertEqual(viewModel.trains.first?.status, .boarding)
        // Actual haptic feedback test would require injecting a mock UINotificationFeedbackGenerator
    }

    func testLoadTrains_InvalidDestinationCode() async {
        // Arrange
        let expectation = XCTestExpectation(description: "Error is set for invalid destination code")
        viewModel.$error
            .dropFirst()
            .sink { error in
                XCTAssertNotNil(error)
                XCTAssertEqual(error, "Invalid destination station code for: Invalid Destination")
                expectation.fulfill()
            }
            .store(in: &cancellables)

        // Act
        // Simulate Stations.getStationCode(destination) returning nil by using a destination
        // that is known not to be in the Stations.stationCodes map.
        await viewModel.loadTrains(destination: "Invalid Destination", fromStationCode: "NYP")

        // Assert
        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertTrue(viewModel.trains.isEmpty)
    }

    func testRefreshTrains_MissingParameters() async {
        // Arrange
        // Ensure currentDestination or currentFromStationCode is nil
        viewModel.currentDestination = nil
        viewModel.currentFromStationCode = "NYP"

        let initialTrainCount = viewModel.trains.count // Should remain unchanged

        // Act
        await viewModel.refreshTrains()

        // Assert
        XCTAssertEqual(viewModel.trains.count, initialTrainCount, "Trains list should not change if parameters are missing.")
        XCTAssertFalse(viewModel.isLoading) // Should not enter loading state
        XCTAssertNil(viewModel.error)       // Should not set an error
    }

    func testRefreshTrains_ApiErrorIsSilent() async {
        // Arrange
        viewModel.currentDestination = "Destination"
        viewModel.currentFromStationCode = "NYP"
        let initialTrain = Train.mock(id: 1, trainId: "T1")
        viewModel.trains = [initialTrain]

        mockAPIService.searchTrainsResult = .failure(APIError.decodingError) // Simulate an API error

        // Act
        await viewModel.refreshTrains()

        // Assert
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertNil(viewModel.error, "Error should be nil for silent refresh failure.")
        XCTAssertEqual(viewModel.trains.count, 1, "Train list should not change on silent error.")
        XCTAssertEqual(viewModel.trains.first?.id, 1, "Train list should not change on silent error.")
    }
}

class MockAPIService: APIServiceProtocol {
    var searchTrainsResult: Result<[Train], APIError>?
    var fetchTrainDetailsFlexibleResult: Result<Train, APIError>?

    // Add a closure for more dynamic mocking if needed
    var fetchTrainDetailsFlexibleResultClosure: ((String?, String?, String?) -> Result<Train, APIError>)?

    func searchTrains(fromStationCode: String, toStationCode: String) async throws -> [Train] {
        // ... (existing implementation)
        if let result = searchTrainsResult {
            switch result {
            case .success(let trains): return trains
            case .failure(let error): throw error
            }
        }
        fatalError("searchTrainsResult not set in MockAPIService")
    }

    func fetchTrainDetailsFlexible(id: String?, trainId: String?, fromStationCode: String?) async throws -> Train {
        if let closure = fetchTrainDetailsFlexibleResultClosure {
            switch closure(id, trainId, fromStationCode) {
            case .success(let train): return train
            case .failure(let error): throw error
            }
        }
        if let result = fetchTrainDetailsFlexibleResult {
            switch result {
            case .success(let train): return train
            case .failure(let error): throw error
            }
        }
        fatalError("fetchTrainDetailsFlexibleResult or closure not set in MockAPIService")
    }

    // ... (other methods like fetchTrainDetails, fetchTrainByTrainId, fetchHistoricalData remain)
    func fetchTrainDetails(id: String, fromStationCode: String?) async throws -> Train {
        // This could also use the closure if refactored, or keep its specific logic
        if let closure = fetchTrainDetailsFlexibleResultClosure { // Simplified: assuming it can use the same closure logic
             switch closure(id, nil, fromStationCode) {
            case .success(let train): return train
            case .failure(let error): throw error
            }
        }
        if let result = fetchTrainDetailsFlexibleResult {
             switch result {
            case .success(let train): return train
            case .failure(let error): throw error
            }
        }
        fatalError("fetchTrainDetails not implemented or result/closure not set in MockAPIService")
    }

    func fetchTrainByTrainId(_ trainId: String, sinceHoursAgo: Int, consolidate: Bool) async throws -> [Train] {
        // This logic might need adjustment if using the closure for all train fetching scenarios.
        // For now, keeping its existing mock logic.
        if let result = searchTrainsResult, case .success(let trains) = result {
            return trains.filter { $0.trainId == trainId }
        }
        // If you want to use the closure for this too:
        // if let closure = fetchTrainDetailsFlexibleResultClosure,
        //    let trainIdActual = trainId { // Assuming trainId is the primary lookup here
        //     switch closure(nil, trainIdActual, nil) { // Adapt parameters as needed
        //         case .success(let train): return [train] // Assuming it returns one, wrap in array
        //         case .failure(let error): throw error
        //     }
        // }
        fatalError("fetchTrainByTrainId not implemented or result not set in MockAPIService for trainId: \(trainId)")
    }

    func fetchHistoricalData(for train: Train, fromStationCode: String, toStationCode: String) async throws -> HistoricalData {
        fatalError("fetchHistoricalData not implemented in MockAPIService")
    }
}
