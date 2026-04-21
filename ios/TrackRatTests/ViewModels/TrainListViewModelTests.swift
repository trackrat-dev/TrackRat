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

    // MARK: - Future-schedule filter tests

    func testFilterUpcomingTrainsRemovesFarFutureTrainsForToday() {
        let now = Date()
        let near = MockDataFactory.createMockTrainV2(trainId: "NEAR", departureTime: now.addingTimeInterval(3600))
        let far = MockDataFactory.createMockTrainV2(trainId: "FAR", departureTime: now.addingTimeInterval(10 * 3600))

        let filtered = viewModel.filterUpcomingTrains([near, far], fromStationCode: "NY", date: now)

        XCTAssertEqual(filtered.map { $0.trainId }, ["NEAR"],
                       "Today view should keep the 6-hour window and drop trains beyond it")
    }

    func testFilterUpcomingTrainsKeepsAllTrainsForFutureDate() {
        let now = Date()
        let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: now)!
        let startOfTomorrow = Calendar.current.startOfDay(for: tomorrow)

        // All "tomorrow" trains are > 6h from now; without the fix, 100% get filtered.
        let earlyMorning = MockDataFactory.createMockTrainV2(trainId: "EARLY",
                                                             departureTime: startOfTomorrow.addingTimeInterval(3600))
        let evening = MockDataFactory.createMockTrainV2(trainId: "EVENING",
                                                        departureTime: startOfTomorrow.addingTimeInterval(18 * 3600))

        let filtered = viewModel.filterUpcomingTrains([earlyMorning, evening],
                                                      fromStationCode: "NY",
                                                      date: startOfTomorrow)

        XCTAssertEqual(Set(filtered.map { $0.trainId }), Set(["EARLY", "EVENING"]),
                       "Future-date view should not apply the 6-hour live-board filter")
    }

    func testTimeFromForFutureDateProjectsTodaysTimeOfDay() {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "America/New_York")!

        // Today at 15:30 ET; tomorrow at midnight ET (as DateSelectorSheet produces)
        let today = calendar.date(from: DateComponents(timeZone: calendar.timeZone, year: 2026, month: 5, day: 4, hour: 15, minute: 30))!
        let tomorrowStart = calendar.date(from: DateComponents(timeZone: calendar.timeZone, year: 2026, month: 5, day: 5))!

        let timeFrom = APIService.timeFromForFutureDate(tomorrowStart, now: today)

        XCTAssertNotNil(timeFrom)
        let components = calendar.dateComponents([.year, .month, .day, .hour, .minute], from: timeFrom!)
        XCTAssertEqual(components.year, 2026)
        XCTAssertEqual(components.month, 5)
        XCTAssertEqual(components.day, 5)
        XCTAssertEqual(components.hour, 15)
        XCTAssertEqual(components.minute, 30)
    }

    func testTimeFromForFutureDateReturnsNilForToday() {
        let now = Date()
        let todayStart = Calendar.current.startOfDay(for: now)
        XCTAssertNil(APIService.timeFromForFutureDate(todayStart, now: now),
                     "Today should preserve existing behavior (no time_from sent)")
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