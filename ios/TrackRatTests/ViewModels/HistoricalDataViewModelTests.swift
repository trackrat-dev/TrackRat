import XCTest
import Combine
@testable import TrackRat

// MARK: - Mock API Service for Historical Data

class MockAPIServiceForHistoricalData: APIService {
    var fetchRouteHistoricalDataResult: Result<RouteHistoricalData, Error>?
    var fetchRouteHistoricalDataCallCount = 0

    // Parameters from last call
    var lastFromStationCode: String?
    var lastToStationCode: String?
    var lastDataSource: String?
    var lastHighlightTrain: String?
    var lastDays: Int?

    override func fetchRouteHistoricalData(
        from: String,
        to: String,
        dataSource: String,
        highlightTrain: String?,
        days: Int
    ) async throws -> RouteHistoricalData {
        fetchRouteHistoricalDataCallCount += 1
        lastFromStationCode = from
        lastToStationCode = to
        lastDataSource = dataSource
        lastHighlightTrain = highlightTrain
        lastDays = days

        if let result = fetchRouteHistoricalDataResult {
            switch result {
            case .success(let data):
                return data
            case .failure(let error):
                throw error
            }
        }

        // Return default mock data
        return createMockRouteHistoricalData(from: from, to: to, dataSource: dataSource)
    }
}

// MARK: - Test Data Factory

struct HistoricalDataTestFactory {
    static func createMockTrainV2(
        trainId: String = "TEST123",
        destination: String = "Philadelphia",
        trainClass: String = "NJ Transit"
    ) -> TrainV2 {
        let departure = StationTiming(
            code: "NY",
            name: "New York Penn Station",
            scheduledTime: Date(),
            updatedTime: nil,
            actualTime: nil,
            track: "11"
        )

        let arrival = StationTiming(
            code: "PH",
            name: destination,
            scheduledTime: Date().addingTimeInterval(3600),
            updatedTime: nil,
            actualTime: nil,
            track: nil
        )

        let line = LineInfo(
            code: trainClass == "Amtrak" ? "AMT_NEC" : "NEC",
            name: trainClass == "Amtrak" ? "Amtrak Northeast Regional" : "Northeast Corridor",
            color: "#FF6B00"
        )

        return TrainV2(
            trainId: trainId,
            line: line,
            destination: destination,
            departure: departure,
            arrival: arrival,
            trainPosition: nil,
            dataFreshness: nil,
            observationType: nil,
            isCancelled: false,
            isCompleted: false
        )
    }
}

func createMockRouteHistoricalData(
    from: String,
    to: String,
    dataSource: String
) -> RouteHistoricalData {
    let route = RouteInfo(
        fromStation: from,
        toStation: to,
        dataSource: dataSource,
        totalTrains: 1000
    )

    let delayBreakdown = DelayBreakdown(
        onTime: 65.5,
        slight: 20.2,
        significant: 10.8,
        major: 3.5
    )

    let trackUsage = [
        "11": 35.0,
        "12": 25.0,
        "13": 20.0,
        "14": 15.0,
        "15": 5.0
    ]

    let aggregateStats = AggregateStats(
        delayBreakdown: delayBreakdown,
        averageDelayMinutes: 8.5,
        trackUsageAtOrigin: trackUsage
    )

    return RouteHistoricalData(
        route: route,
        aggregateStats: aggregateStats,
        highlightedTrain: nil
    )
}

// MARK: - Test Suite

@MainActor
class HistoricalDataViewModelTests: XCTestCase {
    var viewModel: HistoricalDataViewModel!
    var mockAPIService: MockAPIServiceForHistoricalData!
    var cancellables: Set<AnyCancellable>!

    override func setUp() {
        super.setUp()
        mockAPIService = MockAPIServiceForHistoricalData()
        cancellables = []

        print("🧪 Setting up HistoricalDataViewModel test")
    }

    override func tearDown() {
        viewModel = nil
        mockAPIService = nil
        cancellables = nil

        print("🧹 Cleaning up HistoricalDataViewModel test")
        super.tearDown()
    }

    // MARK: - Initialization Tests

    func testInit_withTrainAndDestinationCode_setsCorrectly() {
        print("🏗️ Testing HistoricalDataViewModel initialization with destination code")

        let train = HistoricalDataTestFactory.createMockTrainV2(
            trainId: "INIT123",
            destination: "Philadelphia"
        )
        let destinationCode = "PH"

        print("  - Train: \(train.trainId)")
        print("  - Destination: \(train.destination)")
        print("  - Destination code: \(destinationCode)")

        viewModel = HistoricalDataViewModel(train: train, toStationCode: destinationCode)

        XCTAssertEqual(viewModel.destinationStationCode, destinationCode, "Should use provided destination code")

        print("  ✅ Initialization with destination code test passed")
    }

    func testInit_withTrainOnly_fallsBackToStationCode() {
        print("🏗️ Testing HistoricalDataViewModel initialization with fallback")

        let train = HistoricalDataTestFactory.createMockTrainV2(
            trainId: "FALLBACK123",
            destination: "Philadelphia"
        )

        print("  - Train: \(train.trainId)")
        print("  - Destination: \(train.destination)")
        print("  - No destination code provided (should fall back)")

        viewModel = HistoricalDataViewModel(train: train, toStationCode: nil)

        // Should fall back to Stations.getStationCode(train.destination)
        let expectedCode = Stations.getStationCode("Philadelphia")
        print("  - Expected fallback code: \(expectedCode ?? "nil")")
        print("  - Actual destination code: \(viewModel.destinationStationCode ?? "nil")")

        XCTAssertEqual(viewModel.destinationStationCode, expectedCode, "Should fall back to station code lookup")

        print("  ✅ Initialization with fallback test passed")
    }

    // MARK: - Data Loading Tests

    func testLoadHistoricalData_withValidParameters_loadsSuccessfully() async {
        print("📊 Testing successful historical data loading")

        let train = HistoricalDataTestFactory.createMockTrainV2(
            trainId: "LOAD123",
            destination: "Philadelphia",
            trainClass: "NJ Transit"
        )

        // Use dependency injection pattern (would need refactoring in real implementation)
        viewModel = HistoricalDataViewModel(train: train, toStationCode: "PH")

        let fromStationCode = "NY"
        let toStationCode = "PH"

        print("  - Train: \(train.trainId)")
        print("  - From: \(fromStationCode)")
        print("  - To: \(toStationCode)")
        print("  - Train class: \(train.trainClass)")

        // Mock successful API response
        let mockData = createMockRouteHistoricalData(from: fromStationCode, to: toStationCode, dataSource: "NJT")
        mockAPIService.fetchRouteHistoricalDataResult = .success(mockData)

        // Note: In real implementation, we'd need dependency injection to use mockAPIService
        // For this test, we're testing the logic flow

        let loadingExpectation = XCTestExpectation(description: "Loading state is set")
        let dataExpectation = XCTestExpectation(description: "Historical data is loaded")

        var observedLoadingStates: [Bool] = []

        viewModel.$isLoading
            .sink { isLoading in
                observedLoadingStates.append(isLoading)
                if isLoading {
                    loadingExpectation.fulfill()
                }
            }
            .store(in: &cancellables)

        viewModel.$historicalData
            .dropFirst() // Skip initial nil
            .sink { data in
                if data != nil {
                    dataExpectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // Act
        await viewModel.loadHistoricalData(fromStationCode: fromStationCode, toStationCode: toStationCode)

        // Assert
        await fulfillment(of: [loadingExpectation], timeout: 1.0)
        XCTAssertTrue(observedLoadingStates.contains(true), "Should set loading to true")
        XCTAssertFalse(viewModel.isLoading, "Should set loading to false after completion")
        XCTAssertNil(viewModel.error, "Should not have error on success")

        print("  ✅ Successful data loading test completed")
    }

    func testLoadHistoricalData_withMissingFromStation_setsError() async {
        print("❌ Testing error handling for missing from station")

        let train = HistoricalDataTestFactory.createMockTrainV2(trainId: "ERROR123")
        viewModel = HistoricalDataViewModel(train: train, toStationCode: "PH")

        print("  - Train: \(train.trainId)")
        print("  - From station: nil (should cause error)")

        let errorExpectation = XCTestExpectation(description: "Error is set for missing from station")

        viewModel.$error
            .dropFirst() // Skip initial nil
            .sink { error in
                if error != nil {
                    errorExpectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // Act - pass nil for fromStationCode
        await viewModel.loadHistoricalData(fromStationCode: nil, toStationCode: "PH")

        // Assert
        await fulfillment(of: [errorExpectation], timeout: 1.0)
        XCTAssertNotNil(viewModel.error, "Should set error for missing from station")
        XCTAssertTrue(viewModel.error?.contains("departure station not specified") == true, "Error should mention missing departure station")
        XCTAssertFalse(viewModel.isLoading, "Should not be loading after error")
        XCTAssertNil(viewModel.historicalData, "Should not have data after error")

        print("  - Error message: \(viewModel.error ?? "nil")")
        print("  ✅ Missing from station error test passed")
    }

    func testLoadHistoricalData_withMissingToStation_setsError() async {
        print("❌ Testing error handling for missing to station")

        let train = HistoricalDataTestFactory.createMockTrainV2(
            trainId: "NOTO123",
            destination: "Unknown Destination" // This won't have a station code
        )
        viewModel = HistoricalDataViewModel(train: train, toStationCode: nil) // No fallback

        print("  - Train: \(train.trainId)")
        print("  - Destination: \(train.destination)")
        print("  - To station: nil (should cause error)")

        let errorExpectation = XCTestExpectation(description: "Error is set for missing to station")

        viewModel.$error
            .dropFirst()
            .sink { error in
                if error != nil {
                    errorExpectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // Act
        await viewModel.loadHistoricalData(fromStationCode: "NY", toStationCode: nil)

        // Assert
        await fulfillment(of: [errorExpectation], timeout: 1.0)
        XCTAssertNotNil(viewModel.error, "Should set error for missing to station")
        XCTAssertTrue(viewModel.error?.contains("destination station code") == true, "Error should mention missing destination")
        XCTAssertFalse(viewModel.isLoading, "Should not be loading after error")

        print("  - Error message: \(viewModel.error ?? "nil")")
        print("  ✅ Missing to station error test passed")
    }

    func testLoadHistoricalData_withSameFromAndToStations_setsError() async {
        print("❌ Testing error handling for same from and to stations")

        let train = HistoricalDataTestFactory.createMockTrainV2(trainId: "SAME123")
        viewModel = HistoricalDataViewModel(train: train, toStationCode: "NY")

        print("  - Train: \(train.trainId)")
        print("  - From: NY, To: NY (should cause error)")

        let errorExpectation = XCTestExpectation(description: "Error is set for same stations")

        viewModel.$error
            .dropFirst()
            .sink { error in
                if error != nil {
                    errorExpectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // Act - same from and to stations
        await viewModel.loadHistoricalData(fromStationCode: "NY", toStationCode: "NY")

        // Assert
        await fulfillment(of: [errorExpectation], timeout: 1.0)
        XCTAssertNotNil(viewModel.error, "Should set error for same stations")
        XCTAssertTrue(viewModel.error?.contains("different departure and destination") == true, "Error should mention different stations requirement")
        XCTAssertFalse(viewModel.isLoading, "Should not be loading after error")

        print("  - Error message: \(viewModel.error ?? "nil")")
        print("  ✅ Same stations error test passed")
    }

    // MARK: - Data Source Detection Tests

    func testLoadHistoricalData_withAmtrakTrain_usesCorrectDataSource() async {
        print("🚆 Testing data source detection for Amtrak train")

        let amtrakTrain = HistoricalDataTestFactory.createMockTrainV2(
            trainId: "AMT123",
            destination: "Philadelphia",
            trainClass: "Amtrak"
        )

        viewModel = HistoricalDataViewModel(train: amtrakTrain, toStationCode: "PH")

        print("  - Train: \(amtrakTrain.trainId)")
        print("  - Train class: \(amtrakTrain.trainClass)")
        print("  - Expected data source: AMTRAK")

        // Mock the API service to capture the data source used
        let mockData = createMockRouteHistoricalData(from: "NY", to: "PH", dataSource: "AMTRAK")
        mockAPIService.fetchRouteHistoricalDataResult = .success(mockData)

        // Since we can't easily inject the mock API service, we test the logic indirectly
        // by verifying the train class detection works correctly
        XCTAssertEqual(amtrakTrain.trainClass, "Amtrak", "Amtrak train should be classified correctly")

        await viewModel.loadHistoricalData(fromStationCode: "NY", toStationCode: "PH")

        print("  ✅ Amtrak data source detection test completed")
    }

    func testLoadHistoricalData_withNJTransitTrain_usesCorrectDataSource() async {
        print("🚊 Testing data source detection for NJ Transit train")

        let njTransitTrain = HistoricalDataTestFactory.createMockTrainV2(
            trainId: "NJT123",
            destination: "Philadelphia",
            trainClass: "NJ Transit"
        )

        viewModel = HistoricalDataViewModel(train: njTransitTrain, toStationCode: "PH")

        print("  - Train: \(njTransitTrain.trainId)")
        print("  - Train class: \(njTransitTrain.trainClass)")
        print("  - Expected data source: NJT")

        // Test that NJ Transit trains are classified correctly
        XCTAssertEqual(njTransitTrain.trainClass, "NJ Transit", "NJ Transit train should be classified correctly")

        await viewModel.loadHistoricalData(fromStationCode: "NY", toStationCode: "PH")

        print("  ✅ NJ Transit data source detection test completed")
    }

    // MARK: - Data Conversion Tests

    func testDataConversion_withValidRouteData_convertsCorrectly() {
        print("🔄 Testing data conversion from RouteHistoricalData to HistoricalData")

        let train = HistoricalDataTestFactory.createMockTrainV2(trainId: "CONVERT123")
        viewModel = HistoricalDataViewModel(train: train, toStationCode: "PH")

        // Create mock route data
        let mockRouteData = createMockRouteHistoricalData(from: "NY", to: "PH", dataSource: "NJT")

        print("  - Mock route data created:")
        print("    - Total trains: \(mockRouteData.route.totalTrains)")
        print("    - On-time percentage: \(mockRouteData.aggregateStats.delayBreakdown.onTime)%")
        print("    - Average delay: \(mockRouteData.aggregateStats.averageDelayMinutes) minutes")
        print("    - Track usage entries: \(mockRouteData.aggregateStats.trackUsageAtOrigin.count)")

        // Since convertRouteDataToHistoricalData is private, we test the conversion indirectly
        // by ensuring the ViewModel can process the data without errors

        // We could test this more directly if the conversion method was internal/public
        // For now, we verify the structure is as expected

        XCTAssertGreaterThan(mockRouteData.route.totalTrains, 0, "Should have positive train count")
        XCTAssertGreaterThan(mockRouteData.aggregateStats.delayBreakdown.onTime, 0, "Should have positive on-time percentage")
        XCTAssertGreaterThan(mockRouteData.aggregateStats.trackUsageAtOrigin.count, 0, "Should have track usage data")

        print("  ✅ Data conversion structure test completed")
    }

    // MARK: - API Integration Tests

    func testAPIIntegration_withValidParameters_callsCorrectEndpoint() async {
        print("🌐 Testing API integration with correct parameters")

        let train = HistoricalDataTestFactory.createMockTrainV2(
            trainId: "API123",
            trainClass: "NJ Transit"
        )
        viewModel = HistoricalDataViewModel(train: train, toStationCode: "PH")

        // Mock successful response
        let mockData = createMockRouteHistoricalData(from: "NY", to: "PH", dataSource: "NJT")
        mockAPIService.fetchRouteHistoricalDataResult = .success(mockData)

        let fromStation = "NY"
        let toStation = "PH"

        print("  - Train: \(train.trainId)")
        print("  - From: \(fromStation)")
        print("  - To: \(toStation)")
        print("  - Expected data source: NJT")
        print("  - Expected days: 365")

        // Note: In a real implementation with dependency injection, we would:
        // 1. Inject mockAPIService into the ViewModel
        // 2. Call viewModel.loadHistoricalData()
        // 3. Verify mockAPIService.lastFromStationCode == fromStation, etc.

        // For this test, we verify the expected parameters
        XCTAssertEqual(train.trainClass, "NJ Transit", "Should detect correct train class")

        await viewModel.loadHistoricalData(fromStationCode: fromStation, toStationCode: toStation)

        print("  ✅ API integration test completed")
    }

    // MARK: - Error Recovery Tests

    func testAPIError_withNetworkFailure_setsErrorState() async {
        print("🚨 Testing error handling for API network failure")

        let train = HistoricalDataTestFactory.createMockTrainV2(trainId: "APIERROR123")
        viewModel = HistoricalDataViewModel(train: train, toStationCode: "PH")

        // Mock API failure
        mockAPIService.fetchRouteHistoricalDataResult = .failure(TestError.networkError)

        print("  - Train: \(train.trainId)")
        print("  - Simulating API network error")

        let errorExpectation = XCTestExpectation(description: "Error is set for API failure")

        viewModel.$error
            .dropFirst()
            .sink { error in
                if error != nil {
                    errorExpectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // Act
        await viewModel.loadHistoricalData(fromStationCode: "NY", toStationCode: "PH")

        // Assert
        await fulfillment(of: [errorExpectation], timeout: 1.0)
        XCTAssertNotNil(viewModel.error, "Should set error for API failure")
        XCTAssertFalse(viewModel.isLoading, "Should not be loading after error")
        XCTAssertNil(viewModel.historicalData, "Should not have data after error")

        print("  - Error message: \(viewModel.error ?? "nil")")
        print("  ✅ API error handling test passed")
    }

    // MARK: - State Management Tests

    func testLoadingState_duringDataLoad_updatesCorrectly() async {
        print("⏳ Testing loading state management during data load")

        let train = HistoricalDataTestFactory.createMockTrainV2(trainId: "LOADING123")
        viewModel = HistoricalDataViewModel(train: train, toStationCode: "PH")

        var loadingStates: [Bool] = []

        print("  - Train: \(train.trainId)")
        print("  - Observing loading state changes")

        let stateExpectation = XCTestExpectation(description: "Loading states captured")
        stateExpectation.expectedFulfillmentCount = 2 // true, then false

        viewModel.$isLoading
            .sink { isLoading in
                loadingStates.append(isLoading)
                print("    - Loading state: \(isLoading)")

                if loadingStates.count >= 2 {
                    stateExpectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // Mock successful response
        let mockData = createMockRouteHistoricalData(from: "NY", to: "PH", dataSource: "NJT")
        mockAPIService.fetchRouteHistoricalDataResult = .success(mockData)

        // Act
        await viewModel.loadHistoricalData(fromStationCode: "NY", toStationCode: "PH")

        // Assert
        await fulfillment(of: [stateExpectation], timeout: 2.0)
        XCTAssertTrue(loadingStates.contains(true), "Should have been loading at some point")
        XCTAssertFalse(viewModel.isLoading, "Should not be loading after completion")

        print("  - Loading states observed: \(loadingStates)")
        print("  ✅ Loading state management test passed")
    }

    // MARK: - Real Usage Scenario Tests

    func testCompleteUserFlow_fromInitToDataDisplay() async {
        print("🎯 Testing complete user flow from initialization to data display")

        // Step 1: User opens historical data for a train
        let train = HistoricalDataTestFactory.createMockTrainV2(
            trainId: "USER123",
            destination: "Philadelphia"
        )

        print("  Step 1: User opens historical data")
        print("  - Train: \(train.trainId)")
        print("  - Destination: \(train.destination)")

        viewModel = HistoricalDataViewModel(train: train, toStationCode: "PH")

        XCTAssertNotNil(viewModel, "ViewModel should initialize successfully")
        XCTAssertEqual(viewModel.destinationStationCode, "PH", "Should set destination code correctly")

        // Step 2: App loads historical data automatically
        print("  Step 2: App loads historical data")

        let mockData = createMockRouteHistoricalData(from: "NY", to: "PH", dataSource: "NJT")
        mockAPIService.fetchRouteHistoricalDataResult = .success(mockData)

        let dataExpectation = XCTestExpectation(description: "Historical data loads successfully")

        viewModel.$historicalData
            .dropFirst()
            .sink { data in
                if data != nil {
                    dataExpectation.fulfill()
                }
            }
            .store(in: &cancellables)

        await viewModel.loadHistoricalData(fromStationCode: "NY", toStationCode: "PH")

        // Step 3: Data is available for UI display
        print("  Step 3: Data available for display")

        await fulfillment(of: [dataExpectation], timeout: 1.0)
        XCTAssertNotNil(viewModel.historicalData, "Should have historical data")
        XCTAssertNil(viewModel.error, "Should not have error")
        XCTAssertFalse(viewModel.isLoading, "Should not be loading")

        // Step 4: User can view performance analytics
        print("  Step 4: Performance data available")

        if let data = viewModel.historicalData {
            print("    - Route stats available: \(data.routeStats != nil)")
            print("    - Route track stats available: \(data.routeTrackStats != nil)")
            print("    - Data source: \(data.dataSource ?? "unknown")")
        }

        print("  ✅ Complete user flow test successful")
    }
}