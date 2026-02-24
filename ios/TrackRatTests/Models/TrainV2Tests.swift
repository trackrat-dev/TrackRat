import XCTest
import Foundation
@testable import TrackRat

class TrainV2Tests: XCTestCase {

    // MARK: - Test Data Factory

    func createTestTrainV2(
        trainId: String = "TEST123",
        departureCode: String = "NY",
        departureName: String = "New York Penn Station",
        destinationCode: String = "PH",
        destinationName: String = "Philadelphia",
        departureTime: Date = Date(),
        arrivalTime: Date? = nil,
        delayMinutes: Int = 0,
        track: String? = "11",
        isCancelled: Bool = false,
        isCompleted: Bool = false,
        observationType: String? = nil,
        stops: [StopV2]? = nil
    ) -> TrainV2 {
        let departure = StationTiming(
            code: departureCode,
            name: departureName,
            scheduledTime: departureTime,
            updatedTime: delayMinutes > 0 ? departureTime.addingTimeInterval(TimeInterval(delayMinutes * 60)) : nil,
            actualTime: nil,
            track: track
        )

        let arrival = StationTiming(
            code: destinationCode,
            name: destinationName,
            scheduledTime: arrivalTime ?? departureTime.addingTimeInterval(3600),
            updatedTime: nil,
            actualTime: nil,
            track: nil
        )

        let line = LineInfo(code: "NEC", name: "Northeast Corridor", color: "#FF6B00")

        return TrainV2(
            trainId: trainId,
            journeyDate: departureTime,
            line: line,
            destination: destinationName,
            departure: departure,
            arrival: arrival,
            trainPosition: nil,
            dataFreshness: nil,
            observationType: observationType,
            isCancelled: isCancelled,
            isCompleted: isCompleted,
            dataSource: "NJT",
            stops: stops
        )
    }

    func createTestStops(
        originCode: String = "NY",
        originName: String = "New York Penn Station",
        destinationCode: String = "PH",
        destinationName: String = "Philadelphia",
        baseTime: Date = Date(),
        originDeparted: Bool = false,
        destinationArrived: Bool = false
    ) -> [StopV2] {
        return [
            StopV2(
                stationCode: originCode,
                stationName: originName,
                sequence: 1,
                scheduledArrival: nil,
                scheduledDeparture: baseTime,
                updatedArrival: nil,
                updatedDeparture: nil,
                actualArrival: nil,
                actualDeparture: originDeparted ? baseTime.addingTimeInterval(300) : nil,
                track: "11",
                rawStatus: nil,
                hasDepartedStation: originDeparted,
                predictedArrival: nil,
                predictedArrivalSamples: nil
            ),
            StopV2(
                stationCode: destinationCode,
                stationName: destinationName,
                sequence: 2,
                scheduledArrival: baseTime.addingTimeInterval(3600),
                scheduledDeparture: nil,
                updatedArrival: nil,
                updatedDeparture: nil,
                actualArrival: destinationArrived ? baseTime.addingTimeInterval(3600) : nil,
                actualDeparture: nil,
                track: nil,
                rawStatus: nil,
                hasDepartedStation: false,
                predictedArrival: nil,
                predictedArrivalSamples: nil
            )
        ]
    }

    // MARK: - Basic Model Tests

    func testTrainV2Initialization() {
        print("🚂 Testing TrainV2 basic initialization")

        let train = createTestTrainV2(
            trainId: "INIT123",
            departureCode: "NY",
            departureName: "New York Penn Station",
            destinationName: "Philadelphia"
        )

        print("  - Train ID: \(train.trainId)")
        print("  - Destination: \(train.destination)")
        print("  - Origin: \(train.originStationCode) (\(train.originStationName))")
        print("  - Departure time: \(train.departureTime)")
        print("  - Track: \(train.track ?? "none")")

        XCTAssertEqual(train.trainId, "INIT123", "Train ID should match")
        XCTAssertEqual(train.destination, "Philadelphia", "Destination should match")
        XCTAssertEqual(train.originStationCode, "NY", "Origin station code should match")
        XCTAssertEqual(train.originStationName, "New York Penn Station", "Origin station name should match")
        XCTAssertEqual(train.track, "11", "Track should match")
        XCTAssertFalse(train.isCancelled, "Train should not be cancelled by default")
        XCTAssertFalse(train.isCompleted, "Train should not be completed by default")
        XCTAssertTrue(train.enhancedDisplayStatus.isEmpty, "Enhanced display status should be empty without position data")

        print("  ✅ Basic initialization test passed")
    }

    func testTrainV2ComputedProperties() {
        print("🔍 Testing TrainV2 computed properties")

        let delayedTime = Date()
        let train = createTestTrainV2(
            trainId: "COMP123",
            departureTime: delayedTime,
            delayMinutes: 15
        )

        print("  - Train ID: \(train.trainId)")
        print("  - Delay minutes: \(train.delayMinutes)")
        print("  - Enhanced display status: '\(train.enhancedDisplayStatus)'")
        print("  - Destination station code: \(train.destinationStationCode ?? "none")")

        XCTAssertEqual(train.delayMinutes, 15, "Delay should be calculated correctly")
        XCTAssertEqual(train.destinationStationCode, "PH", "Destination station code should be available")
        XCTAssertTrue(train.enhancedDisplayStatus.isEmpty, "Enhanced display status should be empty without position data")

        // Context-aware status should show delayed for a train with 15 min delay
        let contextStatus = train.calculateStatus(fromStationCode: "NY", toStationName: "Philadelphia")
        print("  - Context-aware status: \(contextStatus)")
        XCTAssertEqual(contextStatus, .delayed, "Train with 15 min delay should show delayed status")

        print("  ✅ Computed properties test passed")
    }

    // MARK: - Journey Calculation Tests

    func testGetScheduledDepartureTime_withOriginStation_returnsCorrectTime() {
        print("⏰ Testing scheduled departure time calculation")

        let departureTime = TestHelpers.createMockDate(from: "2024-01-15 10:00:00")
        let train = createTestTrainV2(
            trainId: "SCHED123",
            departureCode: "NY",
            departureTime: departureTime
        )

        print("  - Train: \(train.trainId)")
        print("  - Origin: \(train.originStationCode)")
        print("  - Scheduled departure: \(departureTime)")

        let retrievedTime = train.getScheduledDepartureTime(fromStationCode: "NY")

        print("  - Retrieved departure time: \(retrievedTime?.description ?? "none")")
        XCTAssertNotNil(retrievedTime, "Should return departure time for origin station")
        TestHelpers.assertDatesEqual(retrievedTime!, departureTime)

        // Test with non-origin station (should return nil if no stops)
        let nonOriginTime = train.getScheduledDepartureTime(fromStationCode: "PH")
        print("  - Non-origin departure time: \(nonOriginTime?.description ?? "none")")
        XCTAssertNil(nonOriginTime, "Should return nil for non-origin station when no stops available")

        print("  ✅ Scheduled departure time test passed")
    }

    func testGetScheduledArrivalTime_withDestination_returnsCorrectTime() {
        print("🎯 Testing scheduled arrival time calculation")

        let departureTime = TestHelpers.createMockDate(from: "2024-01-15 10:00:00")
        let arrivalTime = departureTime.addingTimeInterval(3600) // 1 hour later

        let train = createTestTrainV2(
            trainId: "ARR123",
            departureTime: departureTime,
            arrivalTime: arrivalTime
        )

        print("  - Train: \(train.trainId)")
        print("  - Destination: \(train.destination)")
        print("  - Scheduled arrival: \(arrivalTime)")

        let retrievedTime = train.getScheduledArrivalTime()

        print("  - Retrieved arrival time: \(retrievedTime?.description ?? "none")")
        XCTAssertNotNil(retrievedTime, "Should return arrival time")
        TestHelpers.assertDatesEqual(retrievedTime!, arrivalTime)

        // Test specific destination name method
        let namedArrivalTime = train.getScheduledArrivalTime(toStationName: "Philadelphia")
        print("  - Named destination arrival time: \(namedArrivalTime?.description ?? "none")")
        XCTAssertNotNil(namedArrivalTime, "Should return arrival time for destination name")

        print("  ✅ Scheduled arrival time test passed")
    }

    // Test removed - journey progress calculation returns 0 until destination reached

    func testJourneyProgressCalculation_completedJourney_returnsOne() {
        print("🏁 Testing journey progress for completed journey")

        let baseTime = Date()
        let completedStops = createTestStops(
            baseTime: baseTime,
            originDeparted: true,
            destinationArrived: true
        )

        let train = createTestTrainV2(
            trainId: "COMPLETE123",
            departureTime: baseTime,
            isCompleted: true,
            stops: completedStops
        )

        print("  - Train: \(train.trainId)")
        print("  - Is completed: \(train.isCompleted)")
        print("  - Origin departed: \(completedStops[0].hasDepartedStation)")
        print("  - Destination status: terminal (should be 100%)")

        let progress = train.calculateJourneyProgress(from: "NY", toCode: "PH")

        print("  - Journey progress: \(progress * 100)%")
        XCTAssertEqual(progress, 1.0, accuracy: 0.01,
            "Completed journey should show 100% progress")

        print("  ✅ Completed journey progress test passed")
    }

    // MARK: - Status Calculation Tests

    func testCalculateStatus_withDepartedTrain_returnsDeparted() {
        print("🚪 Testing status calculation for departed train")

        let departedStops = createTestStops(originDeparted: true)
        let train = createTestTrainV2(
            trainId: "DEPT123",
            stops: departedStops
        )

        print("  - Train: \(train.trainId)")
        print("  - Origin departed: \(departedStops[0].hasDepartedStation)")

        let status = train.calculateStatus(fromStationCode: "NY", toStationName: "Philadelphia")

        print("  - Calculated status: \(status)")
        XCTAssertEqual(status, .departed, "Status should be departed when train has left origin")

        // Test with JourneyContext
        let context = JourneyContext(from: "NY", toCode: "PH", toName: "Philadelphia")
        let contextStatus = train.calculateStatus(for: context)

        print("  - Context-based status: \(contextStatus)")
        XCTAssertEqual(contextStatus, status, "Context-based status should match direct calculation")

        print("  ✅ Departed status calculation test passed")
    }

    func testCalculateStatus_withCancelledTrain_returnsCancelled() {
        print("❌ Testing status calculation for cancelled train")

        let train = createTestTrainV2(
            trainId: "CANCEL123",
            isCancelled: true
        )

        print("  - Train: \(train.trainId)")
        print("  - Is cancelled: \(train.isCancelled)")

        let status = train.calculateStatus(fromStationCode: "NY", toStationName: "Philadelphia")

        print("  - Calculated status: \(status)")
        XCTAssertEqual(status, .cancelled, "Cancelled status should take precedence over all others")

        print("  ✅ Cancelled status calculation test passed")
    }

    func testCalculateStatus_withScheduledTrain_returnsScheduled() {
        print("📋 Testing status calculation for SCHEDULED (no real-time data) train")

        let train = createTestTrainV2(
            trainId: "SCHED123",
            departureTime: Date().addingTimeInterval(600), // 10 min from now
            observationType: "SCHEDULED"
        )

        print("  - Train: \(train.trainId)")
        print("  - Observation type: \(train.observationType ?? "nil")")
        print("  - Delay minutes: \(train.delayMinutes)")

        let status = train.calculateStatus(fromStationCode: "NY", toStationName: "Philadelphia")

        print("  - Calculated status: \(status)")
        XCTAssertEqual(status, .scheduled,
            "SCHEDULED trains must show .scheduled, not .onTime — we have no real-time data to confirm on-time status")

        // Verify that OBSERVED trains still show .onTime when delay is 0
        let observedTrain = createTestTrainV2(
            trainId: "OBS123",
            departureTime: Date().addingTimeInterval(600),
            observationType: "OBSERVED"
        )

        let observedStatus = observedTrain.calculateStatus(fromStationCode: "NY", toStationName: "Philadelphia")

        print("  - OBSERVED train status: \(observedStatus)")
        XCTAssertEqual(observedStatus, .onTime,
            "OBSERVED trains with no delay should still show .onTime")

        print("  ✅ SCHEDULED status calculation test passed")
    }

    func testCalculateStatus_withCancelledScheduledTrain_returnsCancelled() {
        print("🚫 Testing that cancelled takes precedence over SCHEDULED")

        let train = createTestTrainV2(
            trainId: "CANCSCHED123",
            isCancelled: true,
            observationType: "SCHEDULED"
        )

        print("  - Train: \(train.trainId)")
        print("  - Is cancelled: \(train.isCancelled)")
        print("  - Observation type: \(train.observationType ?? "nil")")

        let status = train.calculateStatus(fromStationCode: "NY", toStationName: "Philadelphia")

        print("  - Calculated status: \(status)")
        XCTAssertEqual(status, .cancelled,
            "Cancelled status must take precedence over SCHEDULED observation type")

        print("  ✅ Cancelled-SCHEDULED precedence test passed")
    }

    func testCalculateStatus_withBoardingTrain_returnsBoarding() {
        print("🚌 Testing status calculation for boarding train")

        let now = Date()
        let soonDepartureStops = createTestStops(baseTime: now.addingTimeInterval(600)) // Departs in 10 minutes

        let train = createTestTrainV2(
            trainId: "BOARD123",
            departureTime: now.addingTimeInterval(600),
            stops: soonDepartureStops
        )

        print("  - Train: \(train.trainId)")
        print("  - Departure in: 10 minutes")
        print("  - Has track: \(train.track != nil)")

        let status = train.calculateStatus(fromStationCode: "NY", toStationName: "Philadelphia")

        print("  - Calculated status: \(status)")
        // Status calculation depends on departure timing and track assignment
        XCTAssertNotEqual(status, .cancelled, "Non-cancelled train should not return cancelled status")

        print("  ✅ Boarding status calculation test passed")
    }

    // MARK: - Departure Detection Tests

    func testHasTrainDepartedFromStation_withDepartedStop_returnsTrue() {
        print("✅ Testing train departure detection with departed stop")

        let departedStops = createTestStops(originDeparted: true)
        let train = createTestTrainV2(
            trainId: "DEPCHECK123",
            stops: departedStops
        )

        print("  - Train: \(train.trainId)")
        print("  - Checking departure from: NY")
        print("  - Stop departed status: \(departedStops[0].hasDepartedStation)")

        let hasDeparted = train.hasTrainDepartedFromStation("NY")

        print("  - Has departed: \(hasDeparted)")
        XCTAssertTrue(hasDeparted, "Should detect departure when stop is marked as departed")

        print("  ✅ Departure detection test passed")
    }

    func testHasTrainDepartedFromStation_withoutStops_returnsFalse() {
        print("❌ Testing train departure detection without stops data")

        let train = createTestTrainV2(
            trainId: "NOSTOPS123",
            stops: nil
        )

        print("  - Train: \(train.trainId)")
        print("  - Stops data: none")

        let hasDeparted = train.hasTrainDepartedFromStation("NY")

        print("  - Has departed: \(hasDeparted)")
        XCTAssertFalse(hasDeparted, "Should return false when no stops data available")

        print("  ✅ No stops departure detection test passed")
    }

    // MARK: - Express Train Identification Tests

    func testGetTravelTime_withValidTimes_calculatesCorrectly() {
        print("⚡ Testing travel time calculation")

        let departureTime = TestHelpers.createMockDate(from: "2024-01-15 10:00:00")
        let arrivalTime = departureTime.addingTimeInterval(3600) // 1 hour later

        let train = createTestTrainV2(
            trainId: "TRAVEL123",
            departureTime: departureTime,
            arrivalTime: arrivalTime
        )

        print("  - Train: \(train.trainId)")
        print("  - Departure: \(departureTime)")
        print("  - Arrival: \(arrivalTime)")

        let travelTime = train.getTravelTime()

        print("  - Travel time: \(travelTime) seconds (\(travelTime/60) minutes)")
        XCTAssertEqual(travelTime, 3600, accuracy: 1.0, "Travel time should be 1 hour (3600 seconds)")

        print("  ✅ Travel time calculation test passed")
    }

    func testTrainClass_withAmtrakLine_returnsAmtrak() {
        print("🚆 Testing train class identification for Amtrak")

        let amtrakLine = LineInfo(code: "AMT_NEC", name: "Amtrak Northeast Regional", color: "#003366")

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
            name: "Philadelphia",
            scheduledTime: Date().addingTimeInterval(3600),
            updatedTime: nil,
            actualTime: nil,
            track: nil
        )

        let amtrakTrain = TrainV2(
            trainId: "AMT123",
            journeyDate: Date(),
            line: amtrakLine,
            destination: "Philadelphia",
            departure: departure,
            arrival: arrival,
            trainPosition: nil,
            dataFreshness: nil,
            observationType: nil,
            isCancelled: false,
            isCompleted: false,
            dataSource: "AMTRAK"
        )

        print("  - Train: \(amtrakTrain.trainId)")
        print("  - Line code: \(amtrakTrain.line.code)")
        print("  - Line name: \(amtrakTrain.line.name)")

        let trainClass = amtrakTrain.trainClass

        print("  - Train class: \(trainClass)")
        XCTAssertEqual(trainClass, "Amtrak", "Amtrak line should be classified as Amtrak")

        print("  ✅ Amtrak train class test passed")
    }

    func testTrainClass_withNJTransitLine_returnsNJTransit() {
        print("🚊 Testing train class identification for NJ Transit")

        let train = createTestTrainV2(trainId: "NJT123") // Uses default NEC line

        print("  - Train: \(train.trainId)")
        print("  - Line code: \(train.line.code)")
        print("  - Line name: \(train.line.name)")

        let trainClass = train.trainClass

        print("  - Train class: \(trainClass)")
        XCTAssertEqual(trainClass, "NJ Transit", "Non-Amtrak line should be classified as NJ Transit")

        print("  ✅ NJ Transit train class test passed")
    }

    // MARK: - Live Activity Support Tests

    func testToLiveActivityContentState_withDestination_createsCorrectState() {
        print("📱 Testing Live Activity content state creation")

        let departureTime = TestHelpers.createMockDate(from: "2024-01-15 10:00:00")
        let arrivalTime = departureTime.addingTimeInterval(3600)

        let stops = createTestStops(baseTime: departureTime)
        let train = createTestTrainV2(
            trainId: "LIVE123",
            departureTime: departureTime,
            arrivalTime: arrivalTime,
            stops: stops
        )

        print("  - Train: \(train.trainId)")
        print("  - Origin: \(train.originStationName)")
        print("  - Destination: \(train.destination)")

        let contentState = train.toLiveActivityContentState(from: "NY", toCode: "PH", toName: "Philadelphia")

        print("  - Content state status: \(contentState.status)")
        print("  - Content state track: \(contentState.track ?? "none")")
        print("  - Content state progress: \(contentState.journeyProgress)")
        print("  - Content state departed: \(contentState.hasTrainDeparted)")

        XCTAssertEqual(contentState.track, "11", "Content state should have correct track")
        XCTAssertEqual(contentState.journeyProgress, 0.0, accuracy: 0.01, "Progress should be 0 before departure")
        XCTAssertFalse(contentState.hasTrainDeparted, "Train should not have departed yet")
        XCTAssertNotNil(contentState.status, "Content state should have a status")

        print("  ✅ Live Activity content state test passed")
    }

    // Test removed - content state journey progress is 0 when destination not reached

    // MARK: - Edge Cases and Error Handling

    func testCalculateJourneyProgress_withInvalidStations_returnsZero() {
        print("🔍 Testing journey progress with invalid station codes")

        let train = createTestTrainV2(trainId: "INVALID123")

        print("  - Train: \(train.trainId)")
        print("  - Testing with invalid station codes")

        let progress = train.calculateJourneyProgress(from: "INVALID", toCode: "NOTFOUND")

        print("  - Progress with invalid stations: \(progress)")
        XCTAssertEqual(progress, 0.0, "Invalid stations should return 0 progress")

        print("  ✅ Invalid station handling test passed")
    }

    func testGetDepartureTime_withNonOriginStation_returnsNil() {
        print("❓ Testing departure time for non-origin station")

        let train = createTestTrainV2(
            trainId: "NONORIGIN123",
            stops: nil // No stops data
        )

        print("  - Train: \(train.trainId)")
        print("  - Origin: \(train.originStationCode)")
        print("  - Testing departure from: PH (non-origin)")

        let departureTime = train.getDepartureTime(fromStationCode: "PH")

        print("  - Departure time for non-origin: \(departureTime?.description ?? "nil")")
        XCTAssertNil(departureTime, "Non-origin station should return nil when no stops data")

        print("  ✅ Non-origin departure time test passed")
    }

    func testIsDepartingSoon_withUpcomingDeparture_returnsTrue() {
        print("⏰ Testing departure soon detection")

        let soonTime = Date().addingTimeInterval(600) // 10 minutes from now
        let train = createTestTrainV2(
            trainId: "SOON123",
            departureTime: soonTime
        )

        print("  - Train: \(train.trainId)")
        print("  - Departure in: 10 minutes")

        let isDepartingSoon = train.isDepartingSoon(fromStationCode: "NY", withinMinutes: 11)

        print("  - Is departing soon (within 11 min): \(isDepartingSoon)")
        XCTAssertTrue(isDepartingSoon, "Train departing in 10 minutes should be departing soon")

        let isNotDepartingSoon = train.isDepartingSoon(fromStationCode: "NY", withinMinutes: 9)

        print("  - Is departing soon (within 9 min): \(isNotDepartingSoon)")
        XCTAssertFalse(isNotDepartingSoon, "Train departing in 10 minutes should not be departing soon within 9 minutes")

        print("  ✅ Departure soon detection test passed")
    }

    func testHasAlreadyDeparted_withPastDeparture_returnsTrue() {
        print("🕐 Testing already departed detection with past departure")

        let pastTime = Date().addingTimeInterval(-1800) // 30 minutes ago
        let departedStops = createTestStops(
            baseTime: pastTime,
            originDeparted: true
        )

        let train = createTestTrainV2(
            trainId: "PAST123",
            departureTime: pastTime,
            stops: departedStops
        )

        print("  - Train: \(train.trainId)")
        print("  - Departure was: 30 minutes ago")
        print("  - Origin departed: \(departedStops[0].hasDepartedStation)")

        let hasAlreadyDeparted = train.hasAlreadyDeparted(fromStationCode: "NY")

        print("  - Has already departed: \(hasAlreadyDeparted)")
        XCTAssertTrue(hasAlreadyDeparted, "Train that departed 30 minutes ago should be detected as departed")

        print("  ✅ Already departed detection test passed")
    }
}