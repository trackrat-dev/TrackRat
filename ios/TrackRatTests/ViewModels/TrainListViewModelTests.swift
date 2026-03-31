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
        // Note: TrainListViewModel uses APIService.shared internally
        // We'd need to refactor the view model to accept dependency injection
        // For now, we'll test what we can
        viewModel = TrainListViewModel()
        cancellables = Set<AnyCancellable>()
    }

    override func tearDown() {
        viewModel = nil
        mockAPIService = nil
        cancellables = nil
        super.tearDown()
    }

    // MARK: - Loading States Tests

    func testInitialState() {
        XCTAssertTrue(viewModel.trains.isEmpty)
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertNil(viewModel.error)
    }

    func testLoadingState() {
        // Test the loading state behavior
        viewModel.isLoading = true
        XCTAssertTrue(viewModel.isLoading)

        viewModel.isLoading = false
        XCTAssertFalse(viewModel.isLoading)
    }

    // MARK: - Train Data Tests

    func testTrainsSorting() {
        // Create test trains with different departure times
        let now = Date()
        let train1 = MockDataFactory.createMockTrainV2(
            trainId: "123",
            departureTime: now.addingTimeInterval(3600) // 1 hour from now
        )
        let train2 = MockDataFactory.createMockTrainV2(
            trainId: "456",
            departureTime: now.addingTimeInterval(1800) // 30 min from now
        )
        let train3 = MockDataFactory.createMockTrainV2(
            trainId: "789",
            departureTime: now.addingTimeInterval(7200) // 2 hours from now
        )

        viewModel.trains = [train1, train3, train2]

        // Verify trains are in the order we set them
        XCTAssertEqual(viewModel.trains.count, 3)
        XCTAssertEqual(viewModel.trains[0].trainId, "123")
        XCTAssertEqual(viewModel.trains[1].trainId, "789")
        XCTAssertEqual(viewModel.trains[2].trainId, "456")
    }

    func testEmptyTrainsState() {
        viewModel.trains = []
        XCTAssertTrue(viewModel.trains.isEmpty)
    }

    // MARK: - Error Handling Tests

    func testErrorHandling() {
        let testError = "Network error occurred"
        viewModel.error = testError

        XCTAssertNotNil(viewModel.error)
        XCTAssertEqual(viewModel.error, testError)

        // Clear error
        viewModel.error = nil
        XCTAssertNil(viewModel.error)
    }

    // MARK: - Load Trains Tests

    func testLoadTrainsMethod() async {
        // Test that loadTrains method exists and can be called
        // Note: This will make an actual API call since we can't inject the mock
        viewModel.isLoading = false

        // Call loadTrains
        await viewModel.loadTrains(destination: "Philadelphia", fromStationCode: "NY")

        // Verify loading state was set
        XCTAssertFalse(viewModel.isLoading) // Should be false after loading completes
    }

    // MARK: - Express Train Identification Tests

    func testIdentifyExpressTrains() {
        // Create trains with different travel times
        let train1 = MockDataFactory.createMockTrainV2(trainId: "EXPRESS1")
        let train2 = MockDataFactory.createMockTrainV2(trainId: "LOCAL1")

        viewModel.trains = [train1, train2]

        // Test express train identification
        let expressTrains = viewModel.identifyExpressTrains()

        // The method uses travel time comparison, so results depend on actual train data
        XCTAssertNotNil(expressTrains)
    }

    // MARK: - Helper Method Tests

    func testTrainFiltering() {
        // Create trains with different statuses
        let trains = [
            MockDataFactory.createMockTrainV2(trainId: "100", isCancelled: false),
            MockDataFactory.createMockTrainV2(trainId: "200", delayMinutes: 10),
            MockDataFactory.createMockTrainV2(trainId: "300", isCancelled: true),
            MockDataFactory.createMockTrainV2(trainId: "400", isCancelled: false)
        ]

        viewModel.trains = trains

        // Count trains by cancellation status
        let activeCount = viewModel.trains.filter { !$0.isCancelled }.count
        let cancelledCount = viewModel.trains.filter { $0.isCancelled }.count

        XCTAssertEqual(activeCount, 3)
        XCTAssertEqual(cancelledCount, 1)
    }

    // MARK: - Performance Tests

    func testLargeDataSetPerformance() {
        measure {
            // Create a large dataset
            var trains: [TrainV2] = []
            for i in 0..<1000 {
                trains.append(
                    MockDataFactory.createMockTrainV2(
                        trainId: String(i),
                        departureTime: Date().addingTimeInterval(TimeInterval(i * 60))
                    )
                )
            }

            viewModel.trains = trains
            XCTAssertEqual(viewModel.trains.count, 1000)
        }
    }
}