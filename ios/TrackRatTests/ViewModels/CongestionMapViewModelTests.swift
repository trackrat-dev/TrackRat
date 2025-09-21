import XCTest
@testable import TrackRat

class CongestionMapViewModelTests: XCTestCase {

    var mockAPIService: MockAPIService!

    override func setUp() {
        super.setUp()
        mockAPIService = MockAPIService()
    }

    override func tearDown() {
        mockAPIService = nil
        super.tearDown()
    }

    func testFetchCongestionMapDataSuccess() async throws {
        // The mock will return its default data
        mockAPIService.fetchCongestionMapDataResult = nil // Use default

        // Call the mock service
        let result = try await mockAPIService.fetchCongestionMapData(
            timeWindowHours: 24,
            dataSource: "NJT",
            maxPerSegment: 10
        )

        XCTAssertEqual(result.timeWindowHours, 24)
        XCTAssertEqual(result.maxPerSegment, 10)
        XCTAssertEqual(mockAPIService.fetchCongestionMapDataCallCount, 1)
    }

    func testFetchCongestionMapDataError() async {
        mockAPIService.fetchCongestionMapDataResult = .failure(MockTestError.networkError)

        do {
            _ = try await mockAPIService.fetchCongestionMapData(
                timeWindowHours: 24,
                dataSource: "NJT",
                maxPerSegment: 10
            )
            XCTFail("Should have thrown error")
        } catch {
            XCTAssertTrue(error is MockTestError)
        }
    }
}