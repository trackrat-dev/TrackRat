import XCTest
@testable import TrackRat

@available(iOS 16.1, *)
@MainActor
class LiveActivityServiceTests: XCTestCase {

    var liveActivityService: LiveActivityService!
    var mockAPIService: MockAPIService!

    override func setUp() {
        super.setUp()
        mockAPIService = MockAPIService()
        liveActivityService = LiveActivityService.shared
    }

    override func tearDown() {
        liveActivityService = nil
        mockAPIService = nil
        super.tearDown()
    }

    // MARK: - Basic Tests

    func testServiceInitialization() {
        XCTAssertNotNil(liveActivityService)
        XCTAssertFalse(liveActivityService.isActivityActive)
    }

    func testMockAPIServiceTrainFetch() async throws {
        // Setup mock train
        let mockTrain = MockDataFactory.createMockTrainV2(
            trainId: "TEST123",
            fromStationCode: "NY",
            destination: "Philadelphia"
        )

        mockAPIService.fetchTrainDetailsResult = .success(mockTrain)

        // Test the mock
        let result = try await mockAPIService.fetchTrainDetails(
            id: "TEST123",
            fromStationCode: "NY"
        )

        XCTAssertEqual(result.trainId, "TEST123")
        XCTAssertEqual(result.destination, "Philadelphia")
        XCTAssertEqual(mockAPIService.fetchTrainDetailsCallCount, 1)
    }

    func testMockAPIServiceTokenRegistration() async throws {
        mockAPIService.registerTokenResult = .success(())

        // Test registration
        try await mockAPIService.registerLiveActivityToken(
            pushToken: "test-token",
            activityId: "test-activity",
            trainNumber: "123",
            originCode: "NY",
            destinationCode: "PH"
        )

        XCTAssertEqual(mockAPIService.registerTokenCallCount, 1)
        XCTAssertEqual(mockAPIService.lastPushToken, "test-token")
        XCTAssertEqual(mockAPIService.lastActivityId, "test-activity")
    }

    func testMockAPIServiceTokenUnregistration() async throws {
        mockAPIService.unregisterTokenResult = .success(())

        // Test unregistration
        try await mockAPIService.unregisterLiveActivityToken(pushToken: "test-token")

        XCTAssertEqual(mockAPIService.unregisterTokenCallCount, 1)
        XCTAssertEqual(mockAPIService.lastPushToken, "test-token")
    }

    // MARK: - Error Handling Tests

    func testAPIServiceErrorHandling() async {
        mockAPIService.fetchTrainDetailsResult = .failure(MockTestError.networkError)

        do {
            _ = try await mockAPIService.fetchTrainDetails(
                id: "TEST123",
                fromStationCode: "NY"
            )
            XCTFail("Should have thrown error")
        } catch {
            XCTAssertTrue(error is MockTestError)
        }
    }

    func testTokenRegistrationError() async {
        mockAPIService.registerTokenResult = .failure(MockTestError.networkError)

        do {
            try await mockAPIService.registerLiveActivityToken(
                pushToken: "test-token",
                activityId: "test-activity",
                trainNumber: "123",
                originCode: "NY",
                destinationCode: "PH"
            )
            XCTFail("Should have thrown error")
        } catch {
            XCTAssertTrue(error is MockTestError)
        }
    }

    // MARK: - Journey Progress Tests

    func testJourneyProgressCalculation() {
        let train = MockDataFactory.createMockTrainV2(
            trainId: "PROGRESS123",
            fromStationCode: "NY",
            destination: "Philadelphia",
            departureTime: Date().addingTimeInterval(-1800) // 30 min ago
        )

        // Test progress calculation
        let progress = train.calculateJourneyProgress(from: "NY", to: "Philadelphia")

        // Since we have 2 stops and haven't marked any as departed,
        // progress should be 0
        XCTAssertEqual(progress, 0.0, accuracy: 0.01)
    }

    func testTrainDepartureDetection() {
        let train = MockDataFactory.createMockTrainV2(
            trainId: "DEPT123",
            fromStationCode: "NY"
        )

        // By default, train hasn't departed
        let hasDeparted = train.hasTrainDepartedFromStation("NY")
        XCTAssertFalse(hasDeparted)
    }

    // MARK: - Content State Tests

    func testLiveActivityContentState() {
        let train = MockDataFactory.createMockTrainV2(
            trainId: "CONTENT123",
            fromStationCode: "NY",
            destination: "Philadelphia"
        )

        let contentState = train.toLiveActivityContentState(from: "NY", to: "Philadelphia")

        XCTAssertNotNil(contentState.status)
        XCTAssertNotNil(contentState.journeyProgress)
        XCTAssertNotNil(contentState.status)
        XCTAssertEqual(contentState.journeyProgress, 0.0, accuracy: 0.01)
    }
}