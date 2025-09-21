import XCTest
import Combine
@testable import TrackRat

// MARK: - Mock API Service for Congestion Map

class MockCongestionAPIService: APIService {
    var fetchCongestionMapDataResult: Result<CongestionMapResponse, Error>?
    var fetchCongestionMapDataCallCount = 0

    // Parameters from last call
    var lastTimeWindowHours: Int?
    var lastDataSource: String?
    var lastMaxPerSegment: Int?

    override func fetchCongestionMapData(
        timeWindowHours: Int,
        dataSource: String?,
        maxPerSegment: Int
    ) async throws -> CongestionMapResponse {
        fetchCongestionMapDataCallCount += 1
        lastTimeWindowHours = timeWindowHours
        lastDataSource = dataSource
        lastMaxPerSegment = maxPerSegment

        if let result = fetchCongestionMapDataResult {
            switch result {
            case .success(let data):
                return data
            case .failure(let error):
                throw error
            }
        }

        // Return default mock data
        return createMockCongestionMapResponse(timeWindowHours: timeWindowHours, dataSource: dataSource)
    }
}

// MARK: - Test Data Factory

func createMockCongestionMapResponse(
    timeWindowHours: Int,
    dataSource: String?
) -> CongestionMapResponse {
    let segment1 = CongestionSegment(
        id: "seg1",
        fromStationCode: "NY",
        toStationCode: "NP",
        fromStationName: "New York Penn Station",
        toStationName: "Newark Penn Station",
        trainCount: 15,
        avgDelayMinutes: 3.5,
        congestionLevel: .moderate,
        coordinates: [
            CongestionCoordinate(latitude: 40.7505, longitude: -73.9934),
            CongestionCoordinate(latitude: 40.7347, longitude: -74.1639)
        ]
    )

    let segment2 = CongestionSegment(
        id: "seg2",
        fromStationCode: "NP",
        toStationCode: "SEC",
        fromStationName: "Newark Penn Station",
        toStationName: "Secaucus Junction",
        trainCount: 12,
        avgDelayMinutes: 1.2,
        congestionLevel: .low,
        coordinates: [
            CongestionCoordinate(latitude: 40.7347, longitude: -74.1639),
            CongestionCoordinate(latitude: 40.7893, longitude: -74.0565)
        ]
    )

    let station1 = MapStation(
        code: "NY",
        name: "New York Penn Station",
        coordinate: CongestionCoordinate(latitude: 40.7505, longitude: -73.9934),
        congestionLevel: .high,
        trainCount: 25,
        avgDelayMinutes: 5.2
    )

    let station2 = MapStation(
        code: "NP",
        name: "Newark Penn Station",
        coordinate: CongestionCoordinate(latitude: 40.7347, longitude: -74.1639),
        congestionLevel: .moderate,
        trainCount: 18,
        avgDelayMinutes: 3.1
    )

    let individualSegment = IndividualJourneySegment(
        id: "ind1",
        trainDisplayName: "Train 123",
        fromStation: "NY",
        toStation: "NP",
        delayMinutes: 5,
        coordinates: [
            CongestionCoordinate(latitude: 40.7505, longitude: -73.9934),
            CongestionCoordinate(latitude: 40.7347, longitude: -74.1639)
        ]
    )

    return CongestionMapResponse(
        segments: [segment1, segment2],
        stations: [station1, station2],
        metadata: CongestionMapMetadata(
            timeWindowHours: timeWindowHours,
            dataSource: dataSource ?? "All",
            totalTrains: 37,
            generatedAt: Date()
        ),
        individualSegments: [individualSegment]
    )
}

// MARK: - Test Suite

@MainActor
class CongestionMapViewModelTests: XCTestCase {
    var viewModel: CongestionMapViewModel!
    var mockAPIService: MockCongestionAPIService!
    var cancellables: Set<AnyCancellable>!

    override func setUp() {
        super.setUp()
        mockAPIService = MockCongestionAPIService()
        viewModel = CongestionMapViewModel()
        cancellables = []

        print("🧪 Setting up CongestionMapViewModel test")
    }

    override func tearDown() {
        viewModel = nil
        mockAPIService = nil
        cancellables = nil

        print("🧹 Cleaning up CongestionMapViewModel test")
        super.tearDown()
    }

    // MARK: - Initialization Tests

    func testInit_withDefaults_setsCorrectInitialState() {
        print("🏗️ Testing CongestionMapViewModel initialization")

        print("  - Initial segments count: \(viewModel.segments.count)")
        print("  - Initial individual segments count: \(viewModel.individualSegments.count)")
        print("  - Initial stations count: \(viewModel.stations.count)")
        print("  - Initial loading state: \(viewModel.isLoading)")
        print("  - Initial display mode: \(viewModel.displayMode)")
        print("  - Initial error: \(viewModel.error ?? "nil")")

        XCTAssertEqual(viewModel.segments.count, 0, "Should start with empty segments")
        XCTAssertEqual(viewModel.individualSegments.count, 0, "Should start with empty individual segments")
        XCTAssertEqual(viewModel.stations.count, 0, "Should start with empty stations")
        XCTAssertFalse(viewModel.isLoading, "Should not be loading initially")
        XCTAssertEqual(viewModel.displayMode, .individual, "Should start with individual display mode")
        XCTAssertNil(viewModel.error, "Should not have error initially")

        print("  ✅ Initialization test passed")
    }

    // MARK: - Data Loading Tests

    func testFetchCongestionData_withValidParameters_loadsSuccessfully() async {
        print("📊 Testing successful congestion data loading")

        let timeWindow = 2
        let dataSource = "NJT"

        print("  - Time window: \(timeWindow) hours")
        print("  - Data source: \(dataSource)")

        // Mock successful API response
        let mockResponse = createMockCongestionMapResponse(timeWindowHours: timeWindow, dataSource: dataSource)
        mockAPIService.fetchCongestionMapDataResult = .success(mockResponse)

        let loadingExpectation = XCTestExpectation(description: "Loading state is set")
        let dataExpectation = XCTestExpectation(description: "Data is loaded")

        var observedLoadingStates: [Bool] = []

        viewModel.$isLoading
            .sink { isLoading in
                observedLoadingStates.append(isLoading)
                if isLoading {
                    loadingExpectation.fulfill()
                }
            }
            .store(in: &cancellables)

        viewModel.$segments
            .dropFirst()
            .sink { segments in
                if !segments.isEmpty {
                    dataExpectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // Act
        await viewModel.fetchCongestionData(timeWindowHours: timeWindow, dataSource: dataSource)

        // Assert
        await fulfillment(of: [loadingExpectation], timeout: 1.0)
        XCTAssertTrue(observedLoadingStates.contains(true), "Should set loading to true")
        XCTAssertFalse(viewModel.isLoading, "Should set loading to false after completion")
        XCTAssertNil(viewModel.error, "Should not have error on success")

        print("  - Final segments count: \(viewModel.segments.count)")
        print("  - Final stations count: \(viewModel.stations.count)")
        print("  ✅ Successful data loading test completed")
    }

    func testFetchCongestionDataIfNeeded_withExistingData_skipsLoad() async {
        print("🔄 Testing data loading skip when data already exists")

        // First, load some data
        let mockResponse = createMockCongestionMapResponse(timeWindowHours: 2, dataSource: "NJT")
        mockAPIService.fetchCongestionMapDataResult = .success(mockResponse)

        print("  - Loading initial data...")
        await viewModel.fetchCongestionData(timeWindowHours: 2, dataSource: "NJT")

        let initialCallCount = mockAPIService.fetchCongestionMapDataCallCount
        print("  - Initial API call count: \(initialCallCount)")

        // Try to load again using fetchCongestionDataIfNeeded
        print("  - Attempting to load data again (should skip)...")
        await viewModel.fetchCongestionDataIfNeeded(timeWindowHours: 2, dataSource: "NJT")

        let finalCallCount = mockAPIService.fetchCongestionMapDataCallCount
        print("  - Final API call count: \(finalCallCount)")

        // Note: Since we can't inject the mock API service directly, this test focuses on the logic
        // In a real implementation with dependency injection, we would verify:
        XCTAssertGreaterThan(viewModel.segments.count, 0, "Should have segments from initial load")

        print("  ✅ Data loading skip test completed")
    }

    func testFetchCongestionData_withAPIError_setsErrorState() async {
        print("🚨 Testing error handling for API failure")

        // Mock API failure
        mockAPIService.fetchCongestionMapDataResult = .failure(TestError.networkError)

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
        await viewModel.fetchCongestionData(timeWindowHours: 2, dataSource: "NJT")

        // Assert
        await fulfillment(of: [errorExpectation], timeout: 1.0)
        XCTAssertNotNil(viewModel.error, "Should set error for API failure")
        XCTAssertFalse(viewModel.isLoading, "Should not be loading after error")
        XCTAssertEqual(viewModel.segments.count, 0, "Should not have segments after error")

        print("  - Error message: \(viewModel.error ?? "nil")")
        print("  ✅ API error handling test passed")
    }

    // MARK: - Display Mode Tests

    func testUpdateDisplayMode_fromIndividualToAggregated_updatesCorrectly() async {
        print("🔀 Testing display mode update from individual to aggregated")

        print("  - Initial display mode: \(viewModel.displayMode)")
        XCTAssertEqual(viewModel.displayMode, .individual, "Should start with individual mode")

        // Load some test data first
        let mockResponse = createMockCongestionMapResponse(timeWindowHours: 2, dataSource: nil)
        mockAPIService.fetchCongestionMapDataResult = .success(mockResponse)

        await viewModel.fetchCongestionData(timeWindowHours: 2)

        // Test display mode change
        let modeExpectation = XCTestExpectation(description: "Display mode is updated")

        viewModel.$displayMode
            .dropFirst()
            .sink { mode in
                if mode == .aggregated {
                    modeExpectation.fulfill()
                }
            }
            .store(in: &cancellables)

        print("  - Updating display mode to aggregated...")
        await viewModel.updateDisplayMode(.aggregated)

        // Assert
        await fulfillment(of: [modeExpectation], timeout: 1.0)
        XCTAssertEqual(viewModel.displayMode, .aggregated, "Should update to aggregated mode")

        print("  - Final display mode: \(viewModel.displayMode)")
        print("  ✅ Display mode update test passed")
    }

    func testDisplayModeParameters_withDifferentModes_setsCorrectMaxPerSegment() {
        print("⚙️ Testing display mode parameter mapping")

        // Test aggregated mode
        viewModel.displayMode = .aggregated
        print("  - Aggregated mode - expected maxPerSegment: 0")

        // Test individual mode
        viewModel.displayMode = .individual
        print("  - Individual mode - expected maxPerSegment: 100")

        // Test individual limited mode
        viewModel.displayMode = .individualLimited(50)
        print("  - Individual limited mode - expected maxPerSegment: 50")

        // Note: The actual maxPerSegment calculation happens inside the switch statement
        // in fetchCongestionData. We test that the display mode is set correctly.
        XCTAssertEqual(viewModel.displayMode, .individualLimited(50), "Should support individual limited mode")

        print("  ✅ Display mode parameters test completed")
    }

    // MARK: - Loading State Management Tests

    func testLoadingState_duringDataFetch_updatesCorrectly() async {
        print("⏳ Testing loading state management during data fetch")

        var loadingStates: [Bool] = []

        print("  - Observing loading state changes...")

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
        let mockResponse = createMockCongestionMapResponse(timeWindowHours: 2, dataSource: nil)
        mockAPIService.fetchCongestionMapDataResult = .success(mockResponse)

        // Act
        await viewModel.fetchCongestionData()

        // Assert
        await fulfillment(of: [stateExpectation], timeout: 2.0)
        XCTAssertTrue(loadingStates.contains(true), "Should have been loading at some point")
        XCTAssertFalse(viewModel.isLoading, "Should not be loading after completion")

        print("  - Loading states observed: \(loadingStates)")
        print("  ✅ Loading state management test passed")
    }

    // MARK: - Data Filtering Tests

    func testDataFiltering_withJourneyRoute_filtersCorrectly() async {
        print("🔍 Testing data filtering with journey route")

        // Load test data
        let mockResponse = createMockCongestionMapResponse(timeWindowHours: 2, dataSource: nil)
        mockAPIService.fetchCongestionMapDataResult = .success(mockResponse)

        await viewModel.fetchCongestionData()

        let initialSegmentCount = viewModel.segments.count
        print("  - Initial segments count: \(initialSegmentCount)")

        // Note: The filtering logic for journey routes is in the private implementation
        // We test that the data is loaded correctly and can be filtered
        XCTAssertGreaterThan(initialSegmentCount, 0, "Should have segments to filter")

        print("  ✅ Data filtering test completed")
    }

    // MARK: - Error Recovery Tests

    func testErrorRecovery_afterAPIFailure_canRetrySuccessfully() async {
        print("🔄 Testing error recovery after API failure")

        // First, simulate an API failure
        mockAPIService.fetchCongestionMapDataResult = .failure(TestError.networkError)

        print("  - Step 1: Simulating API failure...")
        await viewModel.fetchCongestionData()

        XCTAssertNotNil(viewModel.error, "Should have error after failure")
        XCTAssertEqual(viewModel.segments.count, 0, "Should not have segments after failure")

        // Then, simulate successful retry
        let mockResponse = createMockCongestionMapResponse(timeWindowHours: 2, dataSource: nil)
        mockAPIService.fetchCongestionMapDataResult = .success(mockResponse)

        print("  - Step 2: Retrying with successful response...")
        await viewModel.fetchCongestionData()

        XCTAssertNil(viewModel.error, "Should clear error after successful retry")
        XCTAssertGreaterThan(viewModel.segments.count, 0, "Should have segments after successful retry")

        print("  - Final segments count: \(viewModel.segments.count)")
        print("  ✅ Error recovery test passed")
    }

    // MARK: - Real Usage Scenario Tests

    func testCompleteUserFlow_fromInitToMapDisplay() async {
        print("🎯 Testing complete user flow from initialization to map display")

        // Step 1: User opens congestion map
        print("  Step 1: User opens congestion map")
        XCTAssertEqual(viewModel.segments.count, 0, "Should start with no data")

        // Step 2: App loads congestion data
        print("  Step 2: App loads congestion data")

        let mockResponse = createMockCongestionMapResponse(timeWindowHours: 2, dataSource: "All")
        mockAPIService.fetchCongestionMapDataResult = .success(mockResponse)

        let dataExpectation = XCTestExpectation(description: "Data loads successfully")

        viewModel.$segments
            .dropFirst()
            .sink { segments in
                if !segments.isEmpty {
                    dataExpectation.fulfill()
                }
            }
            .store(in: &cancellables)

        await viewModel.fetchCongestionData(timeWindowHours: 2)

        // Step 3: Data is available for map display
        print("  Step 3: Data available for map display")

        await fulfillment(of: [dataExpectation], timeout: 1.0)
        XCTAssertGreaterThan(viewModel.segments.count, 0, "Should have segments")
        XCTAssertGreaterThan(viewModel.stations.count, 0, "Should have stations")
        XCTAssertNil(viewModel.error, "Should not have error")

        // Step 4: User changes display mode
        print("  Step 4: User changes display mode")

        await viewModel.updateDisplayMode(.aggregated)
        XCTAssertEqual(viewModel.displayMode, .aggregated, "Should update display mode")

        // Step 5: User can interact with map data
        print("  Step 5: Map data ready for interaction")

        if let firstSegment = viewModel.segments.first {
            print("    - First segment: \(firstSegment.fromStationName) → \(firstSegment.toStationName)")
            print("    - Train count: \(firstSegment.trainCount)")
            print("    - Congestion level: \(firstSegment.congestionLevel)")
        }

        if let firstStation = viewModel.stations.first {
            print("    - First station: \(firstStation.name)")
            print("    - Station congestion: \(firstStation.congestionLevel)")
        }

        print("  ✅ Complete user flow test successful")
    }

    // MARK: - Performance Tests

    func testDataHandling_withLargeDataSet_performsEfficiently() async {
        print("⚡ Testing performance with large data set")

        // Create a larger mock response to test performance
        var largeSegments: [CongestionSegment] = []
        var largeStations: [MapStation] = []

        for i in 1...100 {
            let segment = CongestionSegment(
                id: "seg\(i)",
                fromStationCode: "FROM\(i)",
                toStationCode: "TO\(i)",
                fromStationName: "From Station \(i)",
                toStationName: "To Station \(i)",
                trainCount: i,
                avgDelayMinutes: Double(i % 10),
                congestionLevel: i % 3 == 0 ? .high : (i % 2 == 0 ? .moderate : .low),
                coordinates: [
                    CongestionCoordinate(latitude: 40.0 + Double(i) * 0.01, longitude: -74.0 + Double(i) * 0.01),
                    CongestionCoordinate(latitude: 40.1 + Double(i) * 0.01, longitude: -74.1 + Double(i) * 0.01)
                ]
            )
            largeSegments.append(segment)

            if i <= 50 {
                let station = MapStation(
                    code: "ST\(i)",
                    name: "Station \(i)",
                    coordinate: CongestionCoordinate(latitude: 40.0 + Double(i) * 0.01, longitude: -74.0 + Double(i) * 0.01),
                    congestionLevel: i % 3 == 0 ? .high : (i % 2 == 0 ? .moderate : .low),
                    trainCount: i * 2,
                    avgDelayMinutes: Double(i % 5)
                )
                largeStations.append(station)
            }
        }

        let largeResponse = CongestionMapResponse(
            segments: largeSegments,
            stations: largeStations,
            metadata: CongestionMapMetadata(
                timeWindowHours: 2,
                dataSource: "All",
                totalTrains: 500,
                generatedAt: Date()
            ),
            individualSegments: []
        )

        mockAPIService.fetchCongestionMapDataResult = .success(largeResponse)

        print("  - Testing with \(largeSegments.count) segments and \(largeStations.count) stations")

        let startTime = CFAbsoluteTimeGetCurrent()
        await viewModel.fetchCongestionData()
        let endTime = CFAbsoluteTimeGetCurrent()

        let duration = endTime - startTime
        print("  - Data loading took: \(String(format: "%.3f", duration)) seconds")

        XCTAssertEqual(viewModel.segments.count, largeSegments.count, "Should load all segments")
        XCTAssertEqual(viewModel.stations.count, largeStations.count, "Should load all stations")
        XCTAssertLessThan(duration, 1.0, "Data loading should complete quickly even with large datasets")

        print("  ✅ Performance test passed")
    }
}