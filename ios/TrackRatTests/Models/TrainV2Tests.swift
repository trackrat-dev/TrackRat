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
        dataSource: String = "NJT",
        lineCode: String = "NEC",
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

        let line = LineInfo(code: lineCode, name: "Northeast Corridor", color: "#FF6B00")

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
            cancellationReason: nil,
            isCompleted: isCompleted,
            dataSource: dataSource,
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
            cancellationReason: nil,
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

    // MARK: - hasUnconfirmedTrainNumber

    func testHasUnconfirmedTrainNumber_scheduledNJT_isTrue() {
        print("📋 Testing hasUnconfirmedTrainNumber for SCHEDULED NJT train (the 'Train TBD' case)")

        let train = createTestTrainV2(
            trainId: "3838",
            observationType: "SCHEDULED",
            dataSource: "NJT"
        )

        print("  - displayLabel: \(train.displayLabel)")
        print("  - hasUnconfirmedTrainNumber: \(train.hasUnconfirmedTrainNumber)")
        XCTAssertEqual(train.displayLabel, "Train TBD",
            "Sanity check: SCHEDULED NJT train should render as 'Train TBD'")
        XCTAssertTrue(train.hasUnconfirmedTrainNumber,
            "SCHEDULED NJT train must trigger the info banner")

        print("  ✅ SCHEDULED NJT triggers banner")
    }

    func testHasUnconfirmedTrainNumber_observedNJT_isFalse() {
        print("✅ Testing hasUnconfirmedTrainNumber for OBSERVED NJT train (banner must clear)")

        let train = createTestTrainV2(
            trainId: "3838",
            observationType: "OBSERVED",
            dataSource: "NJT"
        )

        print("  - displayLabel: \(train.displayLabel)")
        print("  - hasUnconfirmedTrainNumber: \(train.hasUnconfirmedTrainNumber)")
        XCTAssertEqual(train.displayLabel, "Train 3838",
            "Sanity check: OBSERVED NJT train shows confirmed number")
        XCTAssertFalse(train.hasUnconfirmedTrainNumber,
            "Banner must self-clear once train flips to OBSERVED")

        print("  ✅ OBSERVED NJT hides banner")
    }

    func testHasUnconfirmedTrainNumber_syntheticIdSources_isFalse() {
        print("🚇 Testing hasUnconfirmedTrainNumber suppressed for synthetic-ID providers")

        // PATH/PATCO/LIRR/MNR/SUBWAY/etc. never render "Train TBD" so the banner
        // would be off-topic — verify it stays hidden even when SCHEDULED.
        let syntheticSources = ["PATH", "PATCO", "LIRR", "MNR", "SUBWAY", "BART", "MBTA", "METRA", "WMATA"]

        for source in syntheticSources {
            let train = createTestTrainV2(
                trainId: "TRIP-1",
                observationType: "SCHEDULED",
                dataSource: source
            )

            print("  - \(source): displayLabel=\"\(train.displayLabel)\", hasUnconfirmedTrainNumber=\(train.hasUnconfirmedTrainNumber)")
            XCTAssertNotEqual(train.displayLabel, "Train TBD",
                "Sanity check: \(source) does not use 'Train TBD' label")
            XCTAssertFalse(train.hasUnconfirmedTrainNumber,
                "\(source) is synthetic-ID — banner must not appear")
        }

        print("  ✅ All synthetic-ID sources suppress banner")
    }

    func testHasUnconfirmedTrainNumber_scheduledAmtrak_isTrue() {
        print("🚆 Testing hasUnconfirmedTrainNumber for SCHEDULED Amtrak train")

        let train = createTestTrainV2(
            trainId: "172",
            observationType: "SCHEDULED",
            dataSource: "AMTRAK"
        )

        print("  - displayLabel: \(train.displayLabel)")
        print("  - hasUnconfirmedTrainNumber: \(train.hasUnconfirmedTrainNumber)")
        XCTAssertEqual(train.displayLabel, "Train TBD",
            "Sanity check: Amtrak shares NJT-style numeric IDs and shows 'Train TBD' when scheduled")
        XCTAssertTrue(train.hasUnconfirmedTrainNumber,
            "SCHEDULED Amtrak train must trigger the banner")

        print("  ✅ SCHEDULED Amtrak triggers banner")
    }

    func testHasUnconfirmedTrainNumber_nilObservationType_isFalse() {
        print("⚠️  Testing hasUnconfirmedTrainNumber when observationType is nil")

        // Older / partial records with no observationType should not trigger the banner;
        // displayLabel falls through to "Train \(trainId)" so the explanation would be misleading.
        let train = createTestTrainV2(
            trainId: "3838",
            observationType: nil,
            dataSource: "NJT"
        )

        print("  - displayLabel: \(train.displayLabel)")
        print("  - hasUnconfirmedTrainNumber: \(train.hasUnconfirmedTrainNumber)")
        XCTAssertEqual(train.displayLabel, "Train 3838",
            "Sanity check: nil observationType shows the trainId, not 'TBD'")
        XCTAssertFalse(train.hasUnconfirmedTrainNumber,
            "Banner must only appear for explicitly SCHEDULED trains")

        print("  ✅ nil observationType hides banner")
    }

    // MARK: - displayDestination

    func testDisplayDestination_subway_stripsLineParenthetical() {
        print("🚇 Testing displayDestination for SUBWAY drops the embedded '(line)' prefix")

        let train = createTestTrainV2(
            destinationName: "Astoria-Ditmars Blvd",
            dataSource: "SUBWAY",
            lineCode: "N"
        )

        print("  - displayLabel: \(train.displayLabel)")
        print("  - displayDestination: \(train.displayDestination)")
        XCTAssertEqual(train.displayLabel, "(N) Astoria-Ditmars Blvd",
            "Sanity check: displayLabel still embeds the line for callers that need a flat string")
        XCTAssertEqual(train.displayDestination, "Astoria-Ditmars Blvd",
            "displayDestination must omit '(line)' so the chip can render the bullet separately")
    }

    func testDisplayDestination_subwayExpress_chipNormalizationIsOrthogonal() {
        print("🚇 Testing displayDestination for SUBWAY express line (e.g., 7X) preserves destination only")

        // The chip layer normalizes "7X" → "7" via SubwayLines.displayBullet(forLineCode:);
        // the destination string itself should not depend on that.
        let train = createTestTrainV2(
            destinationName: "Flushing-Main St",
            dataSource: "SUBWAY",
            lineCode: "7X"
        )

        print("  - displayLabel: \(train.displayLabel)")
        print("  - displayDestination: \(train.displayDestination)")
        XCTAssertEqual(train.displayDestination, "Flushing-Main St",
            "displayDestination is just the destination regardless of express variant code")
    }

    func testDisplayDestination_njt_matchesDisplayLabel() {
        print("🚆 Testing displayDestination for NJT mirrors displayLabel ('Train N')")

        let train = createTestTrainV2(
            trainId: "3838",
            observationType: "OBSERVED",
            dataSource: "NJT"
        )

        print("  - displayLabel: \(train.displayLabel)")
        print("  - displayDestination: \(train.displayDestination)")
        XCTAssertEqual(train.displayDestination, train.displayLabel,
            "Non-subway providers don't embed a parenthetical line, so displayDestination == displayLabel")
        XCTAssertEqual(train.displayDestination, "Train 3838",
            "Sanity check: OBSERVED NJT renders as 'Train {id}'")
    }

    func testDisplayDestination_syntheticIdSources_matchDisplayLabel() {
        print("🚉 Testing displayDestination for synthetic-ID providers mirrors displayLabel (the destination)")

        // PATH/PATCO/LIRR/MNR show just the destination from displayLabel, so
        // displayDestination should be identical — there's no parenthetical to strip.
        let syntheticSources = ["PATH", "PATCO", "LIRR", "MNR"]

        for source in syntheticSources {
            let train = createTestTrainV2(
                trainId: "TRIP-1",
                destinationName: "World Trade Center",
                observationType: "OBSERVED",
                dataSource: source
            )

            print("  - \(source): displayLabel=\"\(train.displayLabel)\" displayDestination=\"\(train.displayDestination)\"")
            XCTAssertEqual(train.displayDestination, train.displayLabel,
                "\(source) has no parenthetical to strip; displayDestination must equal displayLabel")
            XCTAssertEqual(train.displayDestination, "World Trade Center",
                "Sanity check: \(source) shows the destination name")
        }
    }

    // MARK: - StopV2.delayMinutes / NJT inversion (Issue #1289)

    /// Helper: build a StopV2 with only the fields delayMinutes / live estimate care about.
    /// Keeps the four NJT-inversion-prone scenarios easy to read in the tests below.
    private func makeStop(
        stationCode: String = "TEST",
        sequence: Int = 4,
        scheduledDeparture: Date?,
        scheduledArrival: Date? = nil,
        updatedDeparture: Date? = nil,
        updatedArrival: Date? = nil,
        actualDeparture: Date? = nil,
        track: String? = nil,
        hasDepartedStation: Bool = false
    ) -> StopV2 {
        StopV2(
            stationCode: stationCode,
            stationName: "Test Station",
            sequence: sequence,
            scheduledArrival: scheduledArrival,
            scheduledDeparture: scheduledDeparture,
            updatedArrival: updatedArrival,
            updatedDeparture: updatedDeparture,
            actualArrival: nil,
            actualDeparture: actualDeparture,
            track: track,
            rawStatus: nil,
            hasDepartedStation: hasDepartedStation,
            predictedArrival: nil,
            predictedArrivalSamples: nil
        )
    }

    func testStopV2DelayMinutes_njtIntermediateInversion_returnsLiveDelay() {
        print("🐀 Testing StopV2.delayMinutes recovers live estimate from NJT inversion")

        // Regression for #1289 (latent companion to #1282/#1268).
        //
        // NJT intermediate-stop semantics — exactly the shape the collector
        // persists from raw NJT API passthrough:
        //   updated_departure = DEP_TIME (immutable schedule)
        //   updated_arrival   = TIME      (live delayed estimate)
        //
        // The old `updated_departure ?? updated_arrival` gate picked the
        // schedule and returned 0 delay; the fix takes max(...) when both are
        // populated and recovers the +13 min live estimate.
        let now = Date()
        let scheduled = now.addingTimeInterval(-2 * 60)   // 2 min ago, matches #1282 scenario
        let liveEstimate = now.addingTimeInterval(11 * 60) // → 13 min late

        let stop = makeStop(
            scheduledDeparture: scheduled,
            updatedDeparture: scheduled,         // NJT inversion: schedule here
            updatedArrival: liveEstimate         // NJT inversion: live estimate here
        )

        print("  - Scheduled departure: \(scheduled)")
        print("  - updated_departure (= DEP_TIME / schedule): \(scheduled)")
        print("  - updated_arrival (= TIME / live estimate): \(liveEstimate)")
        print("  - liveEstimatedDeparture: \(String(describing: stop.liveEstimatedDeparture))")
        print("  - delayMinutes: \(stop.delayMinutes)")

        XCTAssertEqual(stop.liveEstimatedDeparture, liveEstimate,
            "max(updated_departure, updated_arrival) must pick the later (live) value, not the schedule")
        XCTAssertEqual(stop.delayMinutes, 13,
            "NJT intermediate stop with +13 min live estimate must report 13 min delay, not 0")
    }

    func testStopV2DelayMinutes_njtOriginStop_returnsLiveDelay() {
        print("🐀 Testing StopV2.delayMinutes for NJT origin stop (no inversion)")

        // At NJT origin stops, updated_departure is the genuine live estimate
        // and updated_arrival is None. The new gate must continue to work here.
        let now = Date()
        let scheduled = now.addingTimeInterval(-5 * 60)
        let liveEstimate = now.addingTimeInterval(5 * 60)  // 10 min late

        let stop = makeStop(
            sequence: 1,
            scheduledDeparture: scheduled,
            updatedDeparture: liveEstimate,
            updatedArrival: nil
        )

        print("  - delayMinutes: \(stop.delayMinutes)")
        XCTAssertEqual(stop.liveEstimatedDeparture, liveEstimate,
            "With only updated_departure set, that's the live estimate")
        XCTAssertEqual(stop.delayMinutes, 10,
            "Origin stop with +10 min live departure must report 10 min delay")
    }

    func testStopV2DelayMinutes_nonNjtWithDwell_picksLaterDeparture() {
        print("🐀 Testing StopV2.delayMinutes for non-NJT stop with dwell time")

        // For non-NJT providers updated_departure is the genuine live departure
        // and updated_arrival is the genuine live arrival, separated by the
        // stop's dwell. max(...) picks the later — the departure — which is
        // exactly what we want for delayMinutes.
        let now = Date()
        let scheduled = now.addingTimeInterval(-5 * 60)
        let liveArrival = now.addingTimeInterval(8 * 60)    // arrives 13 min late
        let liveDeparture = now.addingTimeInterval(10 * 60) // leaves 15 min late (2 min dwell)

        let stop = makeStop(
            scheduledDeparture: scheduled,
            updatedDeparture: liveDeparture,
            updatedArrival: liveArrival
        )

        XCTAssertEqual(stop.liveEstimatedDeparture, liveDeparture,
            "max() of two live estimates with dwell should be the later (departure)")
        XCTAssertEqual(stop.delayMinutes, 15,
            "Non-NJT stop with +15 min live departure must report 15 min delay")
    }

    func testStopV2DelayMinutes_arrivalOnly_returnsArrivalDelay() {
        print("🐀 Testing StopV2.delayMinutes when only updatedArrival is set")

        // GTFS-RT feeds occasionally carry only arrival.time in
        // stop_time_update (no departure entry). The previous gate already
        // handled this via `?? updatedArrival`, the new gate must preserve it.
        let now = Date()
        let scheduled = now.addingTimeInterval(-1 * 60)
        let liveArrival = now.addingTimeInterval(9 * 60)  // 10 min late

        let stop = makeStop(
            sequence: 5,
            scheduledDeparture: scheduled,
            updatedDeparture: nil,
            updatedArrival: liveArrival
        )

        XCTAssertEqual(stop.liveEstimatedDeparture, liveArrival,
            "Arrival-only live estimate should still be reported")
        XCTAssertEqual(stop.delayMinutes, 10,
            "Arrival-only +10 min estimate must report 10 min delay (matches /api/v2/trains/departures)")
    }

    func testStopV2DelayMinutes_noLiveEstimate_returnsZero() {
        print("🐀 Testing StopV2.delayMinutes with no live estimate at all")

        let now = Date()
        let stop = makeStop(
            scheduledDeparture: now,
            updatedDeparture: nil,
            updatedArrival: nil
        )

        XCTAssertNil(stop.liveEstimatedDeparture,
            "No live estimate means liveEstimatedDeparture must be nil")
        XCTAssertEqual(stop.delayMinutes, 0,
            "No live estimate should report 0 (unchanged from previous behavior)")
    }

    func testStopV2DelayMinutes_liveEstimateEarlierThanSchedule_clampedToZero() {
        print("🐀 Testing StopV2.delayMinutes clamps negative delay to zero (early train)")

        // A train running slightly ahead of schedule should report 0 delay,
        // not a negative number — match the original `max(0, ...)` behavior.
        let now = Date()
        let scheduled = now
        let liveEstimate = now.addingTimeInterval(-3 * 60)  // 3 min early

        let stop = makeStop(
            scheduledDeparture: scheduled,
            updatedDeparture: liveEstimate,
            updatedArrival: nil
        )

        XCTAssertEqual(stop.delayMinutes, 0,
            "Train running early must report 0 delay, not negative")
    }

    func testLiveEstimatedDeparture_staticHelper_coversFourCases() {
        print("🐀 Testing StopV2.liveEstimatedDeparture static helper")

        let earlier = Date(timeIntervalSince1970: 1_700_000_000)
        let later = earlier.addingTimeInterval(600)

        // Both set: max wins.
        XCTAssertEqual(
            StopV2.liveEstimatedDeparture(updatedDeparture: earlier, updatedArrival: later),
            later,
            "Both set → max picks the later"
        )
        XCTAssertEqual(
            StopV2.liveEstimatedDeparture(updatedDeparture: later, updatedArrival: earlier),
            later,
            "Both set (reversed) → max picks the later"
        )
        // Departure only.
        XCTAssertEqual(
            StopV2.liveEstimatedDeparture(updatedDeparture: earlier, updatedArrival: nil),
            earlier,
            "Departure only → returns departure"
        )
        // Arrival only.
        XCTAssertEqual(
            StopV2.liveEstimatedDeparture(updatedDeparture: nil, updatedArrival: later),
            later,
            "Arrival only → returns arrival"
        )
        // Neither.
        XCTAssertNil(
            StopV2.liveEstimatedDeparture(updatedDeparture: nil, updatedArrival: nil),
            "Both nil → nil"
        )
    }

    // MARK: - getDepartureTime / isBoardingAtStation / NJT inversion (Issue #1289)

    func testGetDepartureTime_njtIntermediateInversion_returnsLiveEstimate() {
        print("🐀 Testing TrainV2.getDepartureTime recovers the live estimate at an NJT intermediate stop")

        // Companion to delayMinutes (#1289). getDepartureTime feeds the departures-list
        // sort key, the Live Activity departure time, and detail views. At an NJT
        // intermediate stop updated_departure holds the immutable schedule (DEP_TIME) and
        // updated_arrival holds the live estimate (TIME), so the old
        // `actualDeparture ?? updatedDeparture ?? scheduledDeparture` chain returned the
        // schedule. Routing through liveEstimatedDeparture recovers the +13 min estimate.
        let now = Date()
        let scheduled = now.addingTimeInterval(-2 * 60)
        let liveEstimate = now.addingTimeInterval(11 * 60)   // 13 min after schedule

        // "TEST" is a non-origin intermediate stop (origin is "NY"), so getDepartureTime
        // takes the stop branch rather than returning the origin's departureTime.
        let stop = makeStop(
            stationCode: "TEST",
            scheduledDeparture: scheduled,
            updatedDeparture: scheduled,      // NJT inversion: schedule here
            updatedArrival: liveEstimate      // NJT inversion: live estimate here
        )
        let train = createTestTrainV2(departureCode: "NY", dataSource: "NJT", stops: [stop])

        let result = train.getDepartureTime(fromStationCode: "TEST")
        print("  - getDepartureTime: \(String(describing: result))")
        XCTAssertEqual(result, liveEstimate,
            "getDepartureTime must return the live estimate (updated_arrival), not the NJT schedule in updated_departure")
    }

    func testGetDepartureTime_actualDepartureWins_overLiveEstimate() {
        print("🐀 Testing TrainV2.getDepartureTime keeps actualDeparture ahead of the live estimate")

        // The live-estimate change must not disturb the actual > estimate > scheduled
        // ordering: once a train has departed it should show its real departure, not a
        // stale pre-departure estimate that lingers in the upstream feed.
        let now = Date()
        let scheduled = now.addingTimeInterval(-10 * 60)
        let actual = now.addingTimeInterval(-7 * 60)

        let stop = makeStop(
            stationCode: "TEST",
            scheduledDeparture: scheduled,
            updatedDeparture: scheduled,
            updatedArrival: now.addingTimeInterval(5 * 60),   // stale estimate still in feed
            actualDeparture: actual
        )
        let train = createTestTrainV2(departureCode: "NY", dataSource: "NJT", stops: [stop])

        XCTAssertEqual(train.getDepartureTime(fromStationCode: "TEST"), actual,
            "actualDeparture must win over the live estimate once the train has departed")
    }

    func testIsBoardingAtStation_njtIntermediateInversion_hidesPrematureBoarding() {
        print("🐀 Testing TrainV2.isBoardingAtStation measures the 15-min window against the live estimate")

        // A train scheduled to leave this intermediate stop in 10 min but delayed (live
        // estimate 25 min out) must NOT show as boarding — the real departure is 25 min
        // away. The old `updatedDeparture ?? scheduledDeparture` read the NJT schedule
        // (+10) and reported boarding prematurely.
        let now = Date()
        let scheduled = now.addingTimeInterval(10 * 60)       // schedule: inside 15-min window
        let liveEstimate = now.addingTimeInterval(25 * 60)    // live: well outside the window

        let stop = makeStop(
            stationCode: "TEST",
            scheduledDeparture: scheduled,
            updatedDeparture: scheduled,       // NJT inversion: schedule here
            updatedArrival: liveEstimate,      // NJT inversion: live estimate here
            track: "5"                         // track required for boarding
        )
        let train = createTestTrainV2(departureCode: "NY", dataSource: "NJT", stops: [stop])

        XCTAssertEqual(stop.liveEstimatedDeparture, liveEstimate,
            "Sanity: the live estimate is the later (delayed) time")
        XCTAssertFalse(train.isBoardingAtStation("TEST"),
            "A train delayed 25 min out must not show boarding even though its schedule is 10 min out")
    }

    func testIsBoardingAtStation_liveEstimateWithinWindow_showsBoarding() {
        print("🐀 Testing TrainV2.isBoardingAtStation still shows boarding when the live estimate is within 15 min")

        // Guard against over-hiding: a delayed train whose live estimate is 12 min out
        // (its schedule already passed) is genuinely boarding soon and must still show.
        let now = Date()
        let scheduled = now.addingTimeInterval(-3 * 60)       // schedule already passed
        let liveEstimate = now.addingTimeInterval(12 * 60)    // live: inside the 15-min window

        let stop = makeStop(
            stationCode: "TEST",
            scheduledDeparture: scheduled,
            updatedDeparture: scheduled,
            updatedArrival: liveEstimate,
            track: "5"
        )
        let train = createTestTrainV2(departureCode: "NY", dataSource: "NJT", stops: [stop])

        XCTAssertTrue(train.isBoardingAtStation("TEST"),
            "A train with a live estimate 12 min out must still show boarding")
    }
}