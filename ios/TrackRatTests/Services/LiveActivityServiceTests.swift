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
        let progress = train.calculateJourneyProgress(from: "NY", toCode: "PH")

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

        let contentState = train.toLiveActivityContentState(from: "NY", toCode: "PH", toName: "Philadelphia")

        XCTAssertNotNil(contentState.status)
        XCTAssertNotNil(contentState.journeyProgress)
        XCTAssertNotNil(contentState.status)
        XCTAssertEqual(contentState.journeyProgress, 0.0, accuracy: 0.01)
    }

    func testActivityAttributesMatchTrainRequiresDataSourceWhenPresent() {
        let attributes = makeActivityAttributes(trainId: "3254", dataSource: "NJT")

        XCTAssertTrue(attributes.matchesTrain(trainId: "3254", dataSource: "NJT"))
        XCTAssertFalse(attributes.matchesTrain(trainId: "3254", dataSource: "AMTRAK"))
    }

    func testActivityAttributesMatchTrainFallsBackForLegacyActivities() {
        let attributes = makeActivityAttributes(trainId: "3254", dataSource: nil)

        XCTAssertTrue(attributes.matchesTrain(trainId: "3254", dataSource: "AMTRAK"))
    }

    private func makeActivityAttributes(trainId: String, dataSource: String?) -> TrainActivityAttributes {
        TrainActivityAttributes(
            trainNumber: trainId,
            trainId: trainId,
            routeDescription: "New York -> Philadelphia",
            origin: "New York",
            destination: "Philadelphia",
            originStationCode: "NY",
            destinationStationCode: "PH",
            departureTime: Date(),
            scheduledArrivalTime: Date().addingTimeInterval(3600),
            theme: "black",
            dataSource: dataSource
        )
    }

    // MARK: - Predicted Track Tests

    /// Build a content state with the new prediction fields populated.
    /// Keeps the unrelated fields neutral so tests focus on prediction behavior.
    private func makeContentState(
        track: String?,
        predictedTrack: String?,
        predictedTrackConfidence: Double?
    ) -> TrainActivityAttributes.ContentState {
        TrainActivityAttributes.ContentState(
            status: "BOARDING",
            track: track,
            currentStopName: "New York Penn Station",
            nextStopName: "Newark Penn Station",
            delayMinutes: 0,
            journeyProgress: 0.0,
            dataTimestamp: Date().timeIntervalSince1970,
            scheduledDepartureTime: nil,
            scheduledArrivalTime: nil,
            nextStopArrivalTime: nil,
            nextStopCode: "NP",
            hasTrainDeparted: false,
            predictedTrack: predictedTrack,
            predictedTrackConfidence: predictedTrackConfidence,
            originStationCode: "NY",
            destinationStationCode: "PH"
        )
    }

    func testPredictedTrackDisplay_returnsNilWhenActualTrackAssigned() {
        let state = makeContentState(track: "4", predictedTrack: "7", predictedTrackConfidence: 0.95)
        XCTAssertNil(state.predictedTrackDisplay,
                     "Actual track must always win over prediction so we never show a wrong-track guess")
        XCTAssertFalse(state.hasPredictedTrack)
    }

    func testPredictedTrackDisplay_returnsNilWhenNoPrediction() {
        let state = makeContentState(track: nil, predictedTrack: nil, predictedTrackConfidence: nil)
        XCTAssertNil(state.predictedTrackDisplay)
        XCTAssertFalse(state.hasPredictedTrack)
    }

    func testPredictedTrackDisplay_returnsNilWhenPredictionEmpty() {
        let state = makeContentState(track: nil, predictedTrack: "", predictedTrackConfidence: 0.9)
        XCTAssertNil(state.predictedTrackDisplay,
                     "Empty prediction string must be treated as no prediction")
        XCTAssertFalse(state.hasPredictedTrack)
    }

    func testPredictedTrackDisplay_returnsNilWhenConfidenceBelowFloor() {
        let floor = TrainActivityAttributes.ContentState.predictedTrackConfidenceFloor
        let state = makeContentState(track: nil, predictedTrack: "7", predictedTrackConfidence: floor - 0.01)
        XCTAssertNil(state.predictedTrackDisplay,
                     "Confidence below the floor must suppress the prediction to avoid noisy guesses")
        XCTAssertFalse(state.hasPredictedTrack)
    }

    func testPredictedTrackDisplay_returnsTildePrefixedTrackAtFloor() {
        let floor = TrainActivityAttributes.ContentState.predictedTrackConfidenceFloor
        let state = makeContentState(track: nil, predictedTrack: "7", predictedTrackConfidence: floor)
        XCTAssertEqual(state.predictedTrackDisplay, "~T7",
                       "Exactly at the floor confidence the predicted track must be shown")
        XCTAssertTrue(state.hasPredictedTrack)
    }

    func testPredictedTrackDisplay_returnsTildePrefixedTrackWhenHighConfidence() {
        let state = makeContentState(track: nil, predictedTrack: "4", predictedTrackConfidence: 0.92)
        XCTAssertEqual(state.predictedTrackDisplay, "~T4")
        XCTAssertTrue(state.hasPredictedTrack)
    }

    func testPredictedTrackDisplay_returnsNilWhenEmptyTrackAssigned() {
        // Some backends report an empty-string track instead of nil while a real assignment is pending;
        // we treat that as "no actual track" and still surface the prediction.
        let state = makeContentState(track: "", predictedTrack: "9", predictedTrackConfidence: 0.8)
        XCTAssertEqual(state.predictedTrackDisplay, "~T9",
                       "Empty actual track must not block the prediction")
    }

    func testDisplayablePredictedTrack_returnsRawValueWhenPredictionShown() {
        let state = makeContentState(track: nil, predictedTrack: "12", predictedTrackConfidence: 0.7)
        XCTAssertEqual(state.displayablePredictedTrack, "12",
                       "Lock screen uses the raw track value because it adds its own 'Track' prefix")
        XCTAssertEqual(state.predictedTrackDisplay, "~T12",
                       "Compact surfaces use the tilde-prefixed display value")
    }

    func testDisplayablePredictedTrack_returnsNilWhenSuppressed() {
        let state = makeContentState(track: nil, predictedTrack: "12", predictedTrackConfidence: 0.1)
        XCTAssertNil(state.displayablePredictedTrack,
                     "Low-confidence predictions must be suppressed from the lock-screen text")
    }

    func testExtractPredictedTrack_returnsNothingWhenTrainHasActualTrack() {
        // MockDataFactory sets track: "11" on the departure stop and the train track field
        let train = MockDataFactory.createMockTrainV2(trainId: "T1", fromStationCode: "NY")
        // Sanity check: the mock factory's track is non-nil
        XCTAssertNotNil(train.track, "Test relies on the mock having an assigned track")

        let (predicted, confidence) = LiveActivityService.extractPredictedTrack(from: train)
        XCTAssertNil(predicted)
        XCTAssertNil(confidence)
    }
}
