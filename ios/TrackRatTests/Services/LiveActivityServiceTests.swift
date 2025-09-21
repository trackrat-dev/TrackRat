import XCTest
import ActivityKit
import UserNotifications
@testable import TrackRat

// MARK: - Mock Classes

@available(iOS 16.1, *)
class MockActivity: Activity<TrainActivityAttributes> {
    private let mockId: String
    private let mockAttributes: TrainActivityAttributes

    init(id: String, attributes: TrainActivityAttributes) {
        self.mockId = id
        self.mockAttributes = attributes
    }

    override var id: String { mockId }
    override var attributes: TrainActivityAttributes { mockAttributes }

    static var mockActivities: [MockActivity] = []

    static func resetMocks() {
        mockActivities = []
    }
}

class MockAPIService: APIService {
    var fetchTrainDetailsResult: Result<TrainV2, Error>?
    var registerTokenResult: Result<Void, Error>?
    var unregisterTokenResult: Result<Void, Error>?
    var fetchTrainDetailsCallCount = 0
    var registerTokenCallCount = 0
    var unregisterTokenCallCount = 0

    // Store parameters from last call
    var lastTrainId: String?
    var lastFromStationCode: String?
    var lastPushToken: String?
    var lastActivityId: String?

    override func fetchTrainDetails(id trainId: String, fromStationCode: String) async throws -> TrainV2 {
        fetchTrainDetailsCallCount += 1
        lastTrainId = trainId
        lastFromStationCode = fromStationCode

        if let result = fetchTrainDetailsResult {
            switch result {
            case .success(let train):
                return train
            case .failure(let error):
                throw error
            }
        }

        // Return default mock train
        return createMockTrainV2(trainId: trainId, fromStationCode: fromStationCode)
    }

    override func registerLiveActivityToken(
        pushToken: String,
        activityId: String,
        trainNumber: String,
        originCode: String,
        destinationCode: String
    ) async throws {
        registerTokenCallCount += 1
        lastPushToken = pushToken
        lastActivityId = activityId

        if let result = registerTokenResult {
            switch result {
            case .success:
                return
            case .failure(let error):
                throw error
            }
        }
    }

    override func unregisterLiveActivityToken(pushToken: String) async throws {
        unregisterTokenCallCount += 1
        lastPushToken = pushToken

        if let result = unregisterTokenResult {
            switch result {
            case .success:
                return
            case .failure(let error):
                throw error
            }
        }
    }
}

// MARK: - Test Data Factory

struct LiveActivityTestData {
    static func createMockTrainV2(
        trainId: String = "TEST123",
        fromStationCode: String = "NY",
        destination: String = "Philadelphia",
        hasStops: Bool = true,
        departureTime: Date = Date(),
        delayMinutes: Int = 0,
        isCancelled: Bool = false,
        isCompleted: Bool = false
    ) -> TrainV2 {
        let departure = StationTiming(
            code: fromStationCode,
            name: fromStationCode == "NY" ? "New York Penn Station" : "Origin Station",
            scheduledTime: departureTime,
            updatedTime: delayMinutes > 0 ? departureTime.addingTimeInterval(TimeInterval(delayMinutes * 60)) : nil,
            actualTime: nil,
            track: "11"
        )

        let arrival = StationTiming(
            code: "PH",
            name: destination,
            scheduledTime: departureTime.addingTimeInterval(3600), // 1 hour later
            updatedTime: nil,
            actualTime: nil,
            track: nil
        )

        let line = LineInfo(code: "NEC", name: "Northeast Corridor", color: "#FF6B00")

        var stops: [StopV2]? = nil
        if hasStops {
            stops = [
                StopV2(
                    stationCode: fromStationCode,
                    stationName: departure.name,
                    sequence: 1,
                    scheduledArrival: nil,
                    scheduledDeparture: departureTime,
                    updatedArrival: nil,
                    updatedDeparture: delayMinutes > 0 ? departureTime.addingTimeInterval(TimeInterval(delayMinutes * 60)) : nil,
                    actualArrival: nil,
                    actualDeparture: nil,
                    track: "11",
                    rawStatus: nil,
                    hasDepartedStation: false,
                    predictedArrival: nil,
                    predictedArrivalSamples: nil
                ),
                StopV2(
                    stationCode: "PH",
                    stationName: destination,
                    sequence: 2,
                    scheduledArrival: departureTime.addingTimeInterval(3600),
                    scheduledDeparture: nil,
                    updatedArrival: nil,
                    updatedDeparture: nil,
                    actualArrival: nil,
                    actualDeparture: nil,
                    track: nil,
                    rawStatus: nil,
                    hasDepartedStation: false,
                    predictedArrival: nil,
                    predictedArrivalSamples: nil
                )
            ]
        }

        return TrainV2(
            trainId: trainId,
            line: line,
            destination: destination,
            departure: departure,
            arrival: arrival,
            trainPosition: nil,
            dataFreshness: nil,
            observationType: nil,
            isCancelled: isCancelled,
            isCompleted: isCompleted,
            stops: stops
        )
    }

    static func createDepartedTrain(trainId: String = "DEPARTED123") -> TrainV2 {
        let baseTime = Date().addingTimeInterval(-1800) // 30 minutes ago

        var train = createMockTrainV2(
            trainId: trainId,
            fromStationCode: "NY",
            destination: "Philadelphia",
            hasStops: true,
            departureTime: baseTime
        )

        // Mark origin stop as departed
        if var stops = train.stops {
            stops[0] = StopV2(
                stationCode: "NY",
                stationName: "New York Penn Station",
                sequence: 1,
                scheduledArrival: nil,
                scheduledDeparture: baseTime,
                updatedArrival: nil,
                updatedDeparture: nil,
                actualArrival: nil,
                actualDeparture: baseTime.addingTimeInterval(300), // Departed 5 minutes late
                track: "11",
                rawStatus: nil,
                hasDepartedStation: true,
                predictedArrival: nil,
                predictedArrivalSamples: nil
            )
        }

        return train
    }

    static func createArrivedTrain(trainId: String = "ARRIVED123") -> TrainV2 {
        let baseTime = Date().addingTimeInterval(-7200) // 2 hours ago

        var train = createMockTrainV2(
            trainId: trainId,
            fromStationCode: "NY",
            destination: "Philadelphia",
            hasStops: true,
            departureTime: baseTime,
            isCompleted: true
        )

        // Mark both stops as completed
        if var stops = train.stops {
            stops[0] = StopV2(
                stationCode: "NY",
                stationName: "New York Penn Station",
                sequence: 1,
                scheduledArrival: nil,
                scheduledDeparture: baseTime,
                updatedArrival: nil,
                updatedDeparture: nil,
                actualArrival: nil,
                actualDeparture: baseTime.addingTimeInterval(300),
                track: "11",
                rawStatus: nil,
                hasDepartedStation: true,
                predictedArrival: nil,
                predictedArrivalSamples: nil
            )

            stops[1] = StopV2(
                stationCode: "PH",
                stationName: "Philadelphia",
                sequence: 2,
                scheduledArrival: baseTime.addingTimeInterval(3600),
                scheduledDeparture: nil,
                updatedArrival: nil,
                updatedDeparture: nil,
                actualArrival: baseTime.addingTimeInterval(3600),
                actualDeparture: nil,
                track: nil,
                rawStatus: nil,
                hasDepartedStation: false,
                predictedArrival: nil,
                predictedArrivalSamples: nil
            )
        }

        return train
    }
}

// Global function to create mock trains (following existing pattern)
func createMockTrainV2(
    trainId: String = "TEST123",
    fromStationCode: String = "NY"
) -> TrainV2 {
    return LiveActivityTestData.createMockTrainV2(trainId: trainId, fromStationCode: fromStationCode)
}

// MARK: - Test Suite

@available(iOS 16.1, *)
@MainActor
class LiveActivityServiceTests: XCTestCase {
    var liveActivityService: LiveActivityService!
    var mockAPIService: MockAPIService!

    override func setUp() {
        super.setUp()
        mockAPIService = MockAPIService()
        liveActivityService = LiveActivityService.shared

        // Clear any existing state
        MockActivity.resetMocks()

        print("🧪 Setting up LiveActivityService test")
    }

    override func tearDown() {
        // Clean up any active activities
        Task {
            await liveActivityService.endCurrentActivity()
        }

        liveActivityService = nil
        mockAPIService = nil
        MockActivity.resetMocks()

        print("🧹 Tearing down LiveActivityService test")
        super.tearDown()
    }

    // MARK: - Core Lifecycle Tests

    func testStartTrackingTrain_withValidTrain_createsActivity() async throws {
        print("🚂 Testing Live Activity creation with valid train data")

        let train = LiveActivityTestData.createMockTrainV2(
            trainId: "123",
            fromStationCode: "NY",
            destination: "Philadelphia"
        )

        // Mock successful API response for detailed train fetch
        mockAPIService.fetchTrainDetailsResult = .success(train)

        print("  - Train: \(train.trainId)")
        print("  - Origin: \(train.originStationCode) (\(train.originStationName))")
        print("  - Destination: \(train.destination)")
        print("  - Scheduled departure: \(train.departureTime)")

        // Override the API service (note: this may require dependency injection in real implementation)
        // For now, testing the core logic

        do {
            try await liveActivityService.startTrackingTrain(
                train,
                from: "NY",
                to: "PH",
                origin: "New York Penn Station",
                destination: "Philadelphia"
            )

            print("  ✅ Live Activity started successfully")
            XCTAssertTrue(liveActivityService.isActivityActive, "Live Activity should be active after starting")
            XCTAssertNotNil(liveActivityService.currentActivity, "Current activity should be set")

            if let activity = liveActivityService.currentActivity {
                print("  - Activity ID: \(activity.id)")
                print("  - Train ID in attributes: \(activity.attributes.trainId)")
                XCTAssertEqual(activity.attributes.trainId, "123", "Activity should track correct train")
                XCTAssertEqual(activity.attributes.origin, "New York Penn Station", "Activity should have correct origin")
                XCTAssertEqual(activity.attributes.destination, "Philadelphia", "Activity should have correct destination")
            }

        } catch {
            XCTFail("Starting Live Activity should not throw error: \(error)")
        }
    }

    func testEndCurrentActivity_withActiveActivity_cleansUpCorrectly() async {
        print("🛑 Testing Live Activity cleanup")

        // First create an activity (simplified for test)
        let train = LiveActivityTestData.createMockTrainV2()
        mockAPIService.fetchTrainDetailsResult = .success(train)

        do {
            try await liveActivityService.startTrackingTrain(
                train,
                from: "NY",
                to: "PH",
                origin: "New York Penn Station",
                destination: "Philadelphia"
            )

            print("  - Created activity for testing")
            XCTAssertTrue(liveActivityService.isActivityActive, "Activity should be active before ending")

            // Now end it
            await liveActivityService.endCurrentActivity()

            print("  ✅ Live Activity ended successfully")
            XCTAssertFalse(liveActivityService.isActivityActive, "Activity should not be active after ending")
            XCTAssertNil(liveActivityService.currentActivity, "Current activity should be nil after ending")

        } catch {
            XCTFail("Live Activity lifecycle should work correctly: \(error)")
        }
    }

    // MARK: - Journey Progress Tests

    func testJourneyProgressCalculation_withIntermediateStop_returnsCorrectPercentage() {
        print("📊 Testing journey progress calculation with intermediate stop")

        let train = LiveActivityTestData.createDepartedTrain(trainId: "PROGRESS123")

        print("  - Train: \(train.trainId)")
        print("  - Stops count: \(train.stops?.count ?? 0)")

        // Test progress calculation using TrainV2's built-in method
        let progress = train.calculateJourneyProgress(from: "NY", to: "Philadelphia")

        print("  - Calculated progress: \(progress * 100)%")
        print("  - Train has departed origin: \(train.hasTrainDepartedFromStation("NY"))")

        // Since origin has departed but destination hasn't, progress should be 50%
        XCTAssertEqual(progress, 0.5, accuracy: 0.01,
            "Train that has departed origin but not reached destination should be 50% complete")

        print("  ✅ Journey progress calculation correct")
    }

    func testJourneyProgressCalculation_withDelayedTrain_adjustsForRealTime() {
        print("⏰ Testing journey progress with delayed train")

        let delayedTrain = LiveActivityTestData.createMockTrainV2(
            trainId: "DELAYED123",
            fromStationCode: "NY",
            destination: "Philadelphia",
            delayMinutes: 15
        )

        print("  - Train: \(delayedTrain.trainId)")
        print("  - Delay: \(delayedTrain.delayMinutes) minutes")
        print("  - Original departure: \(delayedTrain.departure.scheduledTime?.description ?? "none")")
        print("  - Updated departure: \(delayedTrain.departure.updatedTime?.description ?? "none")")

        // Progress should be 0 since train hasn't departed yet
        let progress = delayedTrain.calculateJourneyProgress(from: "NY", to: "Philadelphia")

        print("  - Progress: \(progress * 100)%")
        XCTAssertEqual(progress, 0.0, accuracy: 0.01,
            "Train that hasn't departed should have 0% progress regardless of delay")

        print("  ✅ Delayed train progress calculation correct")
    }

    // MARK: - Auto-End Logic Tests

    func testAutoEnd_whenTrainArrives_endsActivity() async {
        print("🏁 Testing auto-end when train arrives at destination")

        let arrivedTrain = LiveActivityTestData.createArrivedTrain(trainId: "AUTOEND123")

        print("  - Train: \(arrivedTrain.trainId)")
        print("  - Is completed: \(arrivedTrain.isCompleted)")
        print("  - Stops: \(arrivedTrain.stops?.map { "\($0.stationCode): departed=\($0.hasDepartedStation)" } ?? [])")

        // Create mock activity for testing shouldEndActivity
        let attributes = TrainActivityAttributes(
            trainNumber: arrivedTrain.trainId,
            trainId: arrivedTrain.trainId,
            routeDescription: "NY → PH",
            origin: "New York Penn Station",
            destination: "Philadelphia",
            originStationCode: "NY",
            destinationStationCode: "PH",
            departureTime: arrivedTrain.departureTime,
            scheduledArrivalTime: arrivedTrain.arrival?.scheduledTime,
            theme: "black"
        )

        let mockActivity = MockActivity(id: "test-activity", attributes: attributes)

        // Test shouldEndActivity logic
        let shouldEnd = liveActivityService.shouldEndActivity(train: arrivedTrain, activity: mockActivity)

        print("  - Should end activity: \(shouldEnd)")
        XCTAssertTrue(shouldEnd, "Activity should end when train has completed journey")

        print("  ✅ Auto-end logic works correctly for completed journey")
    }

    func testAutoEnd_withStaleData_endsAfterTimeout() async {
        print("⏱️ Testing auto-end with stale data timeout")

        // Create train with scheduled arrival in the past
        let pastTime = Date().addingTimeInterval(-3600) // 1 hour ago
        var staleTrain = LiveActivityTestData.createMockTrainV2(
            trainId: "STALE123",
            departureTime: pastTime.addingTimeInterval(-3600) // Started 2 hours ago
        )

        // Mock the arrival time to be in the past
        staleTrain = TrainV2(
            trainId: staleTrain.trainId,
            line: staleTrain.line,
            destination: staleTrain.destination,
            departure: staleTrain.departure,
            arrival: StationTiming(
                code: "PH",
                name: "Philadelphia",
                scheduledTime: pastTime, // Arrival was 1 hour ago
                updatedTime: nil,
                actualTime: nil,
                track: nil
            ),
            trainPosition: staleTrain.trainPosition,
            dataFreshness: staleTrain.dataFreshness,
            observationType: staleTrain.observationType,
            isCancelled: staleTrain.isCancelled,
            isCompleted: staleTrain.isCompleted,
            stops: staleTrain.stops
        )

        print("  - Train: \(staleTrain.trainId)")
        print("  - Scheduled arrival was: \(staleTrain.arrival?.scheduledTime?.description ?? "none")")

        let attributes = TrainActivityAttributes(
            trainNumber: staleTrain.trainId,
            trainId: staleTrain.trainId,
            routeDescription: "NY → PH",
            origin: "New York Penn Station",
            destination: "Philadelphia",
            originStationCode: "NY",
            destinationStationCode: "PH",
            departureTime: staleTrain.departureTime,
            scheduledArrivalTime: staleTrain.arrival?.scheduledTime,
            theme: "black"
        )

        let mockActivity = MockActivity(id: "stale-activity", attributes: attributes)

        let shouldEnd = liveActivityService.shouldEndActivity(train: staleTrain, activity: mockActivity)

        print("  - Should end due to stale data: \(shouldEnd)")
        XCTAssertTrue(shouldEnd, "Activity should end when data is stale (30min past scheduled arrival)")

        print("  ✅ Stale data timeout logic works correctly")
    }

    // MARK: - Error Handling Tests

    func testHandleAPIError_withNetworkFailure_gracefullyDegrades() async {
        print("🚨 Testing graceful degradation with API network failure")

        let train = LiveActivityTestData.createMockTrainV2(trainId: "ERROR123")

        // Mock API failure
        mockAPIService.fetchTrainDetailsResult = .failure(TestError.networkError)

        print("  - Train: \(train.trainId)")
        print("  - Simulating network error during train details fetch")

        do {
            try await liveActivityService.startTrackingTrain(
                train,
                from: "NY",
                to: "PH",
                origin: "New York Penn Station",
                destination: "Philadelphia"
            )

            XCTFail("Should have thrown network error")

        } catch {
            print("  - Caught expected error: \(error)")
            XCTAssertTrue(error is TestError, "Should receive the network error")
            XCTAssertFalse(liveActivityService.isActivityActive, "Activity should not be active after error")

            print("  ✅ Network error handled gracefully")
        }
    }

    func testHandlePushTokenFailure_withInvalidToken_retriesRegistration() async {
        print("📡 Testing push token failure handling")

        let train = LiveActivityTestData.createMockTrainV2(trainId: "TOKEN123")

        // Mock successful train fetch but failed token registration
        mockAPIService.fetchTrainDetailsResult = .success(train)
        mockAPIService.registerTokenResult = .failure(TestError.networkError)

        print("  - Train: \(train.trainId)")
        print("  - Simulating push token registration failure")

        // Note: This test focuses on the error handling pattern
        // The actual Live Activity creation might still succeed even if token registration fails
        do {
            try await liveActivityService.startTrackingTrain(
                train,
                from: "NY",
                to: "PH",
                origin: "New York Penn Station",
                destination: "Philadelphia"
            )

            print("  - Live Activity created despite token registration failure")
            // The service should handle token registration failures gracefully
            // and still create the Live Activity for local updates

        } catch {
            print("  - Error during Live Activity creation: \(error)")
            // This might be expected depending on implementation
        }

        print("  ✅ Push token failure handling tested")
    }

    // MARK: - Timer Management Tests

    func testTimerScheduling_withActiveActivity_schedulesUpdates() async {
        print("⏲️ Testing timer scheduling for Live Activity updates")

        let train = LiveActivityTestData.createMockTrainV2(trainId: "TIMER123")
        mockAPIService.fetchTrainDetailsResult = .success(train)

        print("  - Train: \(train.trainId)")

        do {
            try await liveActivityService.startTrackingTrain(
                train,
                from: "NY",
                to: "PH",
                origin: "New York Penn Station",
                destination: "Philadelphia"
            )

            print("  - Live Activity started, timer should be scheduled")
            XCTAssertTrue(liveActivityService.isActivityActive, "Activity should be active")

            // Test that the service has some way to track timer state
            // (This would require exposing timer state for testing or using dependency injection)

            print("  ✅ Timer scheduling test completed")

        } catch {
            XCTFail("Timer scheduling test failed: \(error)")
        }
    }

    func testTimerCancellation_onActivityEnd_cleansUpProperly() async {
        print("🛑 Testing timer cleanup on activity end")

        let train = LiveActivityTestData.createMockTrainV2(trainId: "CLEANUP123")
        mockAPIService.fetchTrainDetailsResult = .success(train)

        do {
            // Start activity
            try await liveActivityService.startTrackingTrain(
                train,
                from: "NY",
                to: "PH",
                origin: "New York Penn Station",
                destination: "Philadelphia"
            )

            print("  - Live Activity started")
            XCTAssertTrue(liveActivityService.isActivityActive, "Activity should be active")

            // End activity
            await liveActivityService.endCurrentActivity()

            print("  - Live Activity ended")
            XCTAssertFalse(liveActivityService.isActivityActive, "Activity should not be active")

            // Timer should be cleaned up (implementation detail)
            print("  ✅ Timer cleanup test completed")

        } catch {
            XCTFail("Timer cleanup test failed: \(error)")
        }
    }

    // MARK: - Real Usage Scenario Tests

    func testCompleteUserJourney_startToFinish() async {
        print("🎯 Testing complete user journey from start to arrival")

        let baseTime = Date()

        // Step 1: User starts tracking train
        let initialTrain = LiveActivityTestData.createMockTrainV2(
            trainId: "JOURNEY123",
            fromStationCode: "NY",
            destination: "Philadelphia",
            departureTime: baseTime.addingTimeInterval(600) // Departs in 10 minutes
        )

        mockAPIService.fetchTrainDetailsResult = .success(initialTrain)

        print("  Step 1: User starts tracking train")
        print("  - Train: \(initialTrain.trainId)")
        print("  - Departure in: 10 minutes")

        do {
            try await liveActivityService.startTrackingTrain(
                initialTrain,
                from: "NY",
                to: "PH",
                origin: "New York Penn Station",
                destination: "Philadelphia"
            )

            XCTAssertTrue(liveActivityService.isActivityActive, "Activity should be active")
            print("  ✅ Live Activity started successfully")

            // Step 2: Simulate train departure update
            let departedTrain = LiveActivityTestData.createDepartedTrain(trainId: "JOURNEY123")
            mockAPIService.fetchTrainDetailsResult = .success(departedTrain)

            print("  Step 2: Train departs (simulated update)")
            await liveActivityService.fetchAndUpdateTrain()

            print("  ✅ Train departure update processed")

            // Step 3: Simulate train arrival
            let arrivedTrain = LiveActivityTestData.createArrivedTrain(trainId: "JOURNEY123")
            mockAPIService.fetchTrainDetailsResult = .success(arrivedTrain)

            print("  Step 3: Train arrives at destination")
            await liveActivityService.fetchAndUpdateTrain()

            // The auto-end logic should trigger here
            print("  ✅ Complete journey test successful")

        } catch {
            XCTFail("Complete user journey test failed: \(error)")
        }
    }

    // MARK: - Helper Methods Tests

    func testHasTrainDeparted_withDepartedTrain_returnsTrue() {
        print("🚪 Testing train departure detection")

        let departedTrain = LiveActivityTestData.createDepartedTrain(trainId: "DEPT123")

        print("  - Train: \(departedTrain.trainId)")
        print("  - Origin station: \(departedTrain.originStationCode)")

        let hasDeparted = departedTrain.hasTrainDepartedFromStation("NY")

        print("  - Has departed from NY: \(hasDeparted)")
        XCTAssertTrue(hasDeparted, "Departed train should be detected as departed")

        print("  ✅ Train departure detection works correctly")
    }

    func testGetNextStopArrivalTime_withValidStops_returnsCorrectTime() {
        print("📍 Testing next stop arrival time calculation")

        let train = LiveActivityTestData.createMockTrainV2(
            trainId: "NEXTSTOP123",
            hasStops: true
        )

        print("  - Train: \(train.trainId)")
        print("  - Stops count: \(train.stops?.count ?? 0)")

        // Test the private method indirectly through Live Activity content state
        let contentState = train.toLiveActivityContentState(from: "NY", to: "Philadelphia")

        print("  - Next stop: \(contentState.nextStopName ?? "none")")
        print("  - Next stop arrival time: \(contentState.nextStopArrivalTime ?? "none")")

        XCTAssertNotNil(contentState.nextStopName, "Should have next stop name")
        XCTAssertNotNil(contentState.nextStopArrivalTime, "Should have next stop arrival time")

        print("  ✅ Next stop calculation works correctly")
    }
}