import XCTest
@testable import TrackRat

class HistoricalDataViewModelTests: XCTestCase {

    var mockAPIService: MockAPIService!

    override func setUp() {
        super.setUp()
        mockAPIService = MockAPIService()
    }

    override func tearDown() {
        mockAPIService = nil
        super.tearDown()
    }

    func testFetchRouteHistoricalData() async throws {
        // Setup mock response
        let mockData = RouteHistoricalData(
            route: RouteHistoricalData.RouteInfo(
                fromStation: "New York Penn Station",
                toStation: "Philadelphia",
                totalTrains: 100,
                dataSource: "NJT"
            ),
            aggregateStats: RouteHistoricalData.Stats(
                onTimePercentage: 85.0,
                averageDelayMinutes: 5.2,
                averageDepartureDelayMinutes: 3.1,
                cancellationRate: 2.0,
                delayBreakdown: RouteHistoricalData.DelayBreakdown(
                    onTime: 40,
                    slight: 30,
                    significant: 20,
                    major: 10
                ),
                trackUsageAtOrigin: ["11": 40, "12": 30, "13": 30]
            ),
            highlightedTrain: nil
        )

        mockAPIService.fetchRouteHistoricalDataResult = .success(mockData)

        // Call the mock service
        let result = try await mockAPIService.fetchRouteHistoricalData(
            from: "NY",
            to: "PH",
            dataSource: "NJT",
            highlightTrain: nil,
            days: 30
        )

        XCTAssertEqual(result.route.totalTrains, 100)
        XCTAssertEqual(result.aggregateStats.onTimePercentage, 85.0)
        XCTAssertEqual(mockAPIService.fetchRouteHistoricalDataCallCount, 1)
    }

    func testFetchRouteHistoricalDataError() async {
        mockAPIService.fetchRouteHistoricalDataResult = .failure(MockTestError.networkError)

        do {
            _ = try await mockAPIService.fetchRouteHistoricalData(
                from: "NY",
                to: "PH",
                dataSource: "NJT",
                highlightTrain: nil,
                days: 30
            )
            XCTFail("Should have thrown error")
        } catch {
            XCTAssertTrue(error is MockTestError)
        }
    }
}