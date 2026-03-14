import XCTest
@testable import TrackRat

class AlertSubscriptionServiceTests: XCTestCase {

    var service: AlertSubscriptionService!

    override func setUp() {
        super.setUp()
        service = AlertSubscriptionService.shared
        // Clear existing subscriptions for clean test state
        for sub in service.subscriptions {
            service.removeSubscription(sub)
        }
    }

    override func tearDown() {
        // Clean up subscriptions after each test
        for sub in service.subscriptions {
            service.removeSubscription(sub)
        }
        service = nil
        super.tearDown()
    }

    // MARK: - addSubscriptions: Line Subscriptions

    func testAddLineSubscriptions_addsBothDirections() {
        let subA = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "Northeast Corridor",
            direction: "NY", activeDays: 31, activeStartMinutes: 360, activeEndMinutes: 540
        )
        let subB = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "Northeast Corridor",
            direction: "TR", activeDays: 31, activeStartMinutes: 1020, activeEndMinutes: 1200
        )

        service.addSubscriptions([subA, subB])

        XCTAssertEqual(service.subscriptions.count, 2, "Should have two subscriptions, one per direction")

        let toNY = service.subscriptions.first { $0.direction == "NY" }
        let toTR = service.subscriptions.first { $0.direction == "TR" }
        XCTAssertNotNil(toNY, "Should have subscription toward NY")
        XCTAssertNotNil(toTR, "Should have subscription toward TR")

        // Verify independent configuration
        XCTAssertEqual(toNY?.activeStartMinutes, 360, "Morning direction should have 6am start")
        XCTAssertEqual(toTR?.activeStartMinutes, 1020, "Evening direction should have 5pm start")
    }

    func testAddLineSubscriptions_deduplicatesExistingDirection() {
        let sub1 = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "Northeast Corridor",
            direction: "NY", activeDays: 31
        )
        service.addSubscriptions([sub1])
        XCTAssertEqual(service.subscriptions.count, 1)

        // Try to add same direction again
        let sub2 = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "Northeast Corridor",
            direction: "NY", activeDays: 127
        )
        service.addSubscriptions([sub2])

        XCTAssertEqual(service.subscriptions.count, 1, "Duplicate direction should be skipped")
        XCTAssertEqual(service.subscriptions.first?.activeDays, 31, "Original config should be preserved")
    }

    func testAddLineSubscriptions_allowsDifferentDirectionsSameLine() {
        let sub1 = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "Northeast Corridor",
            direction: "NY"
        )
        service.addSubscriptions([sub1])

        let sub2 = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "Northeast Corridor",
            direction: "TR"
        )
        service.addSubscriptions([sub2])

        XCTAssertEqual(service.subscriptions.count, 2, "Different directions should both be added")
    }

    // MARK: - addSubscriptions: Station-Pair Subscriptions

    func testAddStationPairSubscriptions_addsBothDirections() {
        let subAB = RouteAlertSubscription(
            dataSource: "NJT", fromStationCode: "NY", toStationCode: "TR",
            activeDays: 31, activeStartMinutes: 360, activeEndMinutes: 540
        )
        let subBA = RouteAlertSubscription(
            dataSource: "NJT", fromStationCode: "TR", toStationCode: "NY",
            activeDays: 31, activeStartMinutes: 1020, activeEndMinutes: 1200
        )

        service.addSubscriptions([subAB, subBA])

        XCTAssertEqual(service.subscriptions.count, 2, "Should have two subscriptions, one per direction")

        let nyToTr = service.subscriptions.first { $0.fromStationCode == "NY" && $0.toStationCode == "TR" }
        let trToNy = service.subscriptions.first { $0.fromStationCode == "TR" && $0.toStationCode == "NY" }
        XCTAssertNotNil(nyToTr, "Should have NY→TR subscription")
        XCTAssertNotNil(trToNy, "Should have TR→NY subscription")

        // Verify independent configuration
        XCTAssertEqual(nyToTr?.activeStartMinutes, 360, "Morning commute should start at 6am")
        XCTAssertEqual(trToNy?.activeStartMinutes, 1020, "Evening commute should start at 5pm")
    }

    func testAddStationPairSubscriptions_deduplicatesExistingPair() {
        let sub1 = RouteAlertSubscription(
            dataSource: "NJT", fromStationCode: "NY", toStationCode: "TR"
        )
        service.addSubscriptions([sub1])

        let sub2 = RouteAlertSubscription(
            dataSource: "NJT", fromStationCode: "NY", toStationCode: "TR"
        )
        service.addSubscriptions([sub2])

        XCTAssertEqual(service.subscriptions.count, 1, "Duplicate station pair should be skipped")
    }

    func testAddStationPairSubscriptions_allowsReverseDirection() {
        let sub1 = RouteAlertSubscription(
            dataSource: "NJT", fromStationCode: "NY", toStationCode: "TR"
        )
        service.addSubscriptions([sub1])

        let sub2 = RouteAlertSubscription(
            dataSource: "NJT", fromStationCode: "TR", toStationCode: "NY"
        )
        service.addSubscriptions([sub2])

        XCTAssertEqual(service.subscriptions.count, 2, "Reverse direction should be a separate subscription")
    }

    // MARK: - addSubscriptions: Train Subscriptions

    func testAddTrainSubscription_addsSingle() {
        let sub = RouteAlertSubscription(
            dataSource: "NJT", trainId: "3254", trainName: "NJT 3254"
        )
        service.addSubscriptions([sub])

        XCTAssertEqual(service.subscriptions.count, 1)
        XCTAssertEqual(service.subscriptions.first?.trainId, "3254")
    }

    func testAddTrainSubscription_deduplicates() {
        let sub1 = RouteAlertSubscription(
            dataSource: "NJT", trainId: "3254", trainName: "NJT 3254"
        )
        service.addSubscriptions([sub1])

        let sub2 = RouteAlertSubscription(
            dataSource: "NJT", trainId: "3254", trainName: "NJT 3254 updated"
        )
        service.addSubscriptions([sub2])

        XCTAssertEqual(service.subscriptions.count, 1, "Duplicate train should be skipped")
    }

    func testAddTrainSubscription_allowsDifferentDataSources() {
        let sub1 = RouteAlertSubscription(
            dataSource: "NJT", trainId: "3254", trainName: "NJT 3254"
        )
        let sub2 = RouteAlertSubscription(
            dataSource: "AMTRAK", trainId: "3254", trainName: "Amtrak 3254"
        )
        service.addSubscriptions([sub1, sub2])

        XCTAssertEqual(service.subscriptions.count, 2, "Same trainId on different data sources should both be added")
    }

    // MARK: - addSubscriptions: Empty Array

    func testAddSubscriptions_emptyArray() {
        service.addSubscriptions([])
        XCTAssertEqual(service.subscriptions.count, 0, "Adding empty array should not change state")
    }

    // MARK: - copySettings

    func testCopySettings_preservesIdentityFields() {
        let source = RouteAlertSubscription(
            dataSource: "NJT", fromStationCode: "NY", toStationCode: "TR",
            activeDays: 31, activeStartMinutes: 360, activeEndMinutes: 540,
            delayThresholdMinutes: 10, notifyCancellation: false, notifyDelay: true,
            notifyRecovery: true, digestTimeMinutes: 420
        )
        let target = RouteAlertSubscription(
            dataSource: "NJT", fromStationCode: "TR", toStationCode: "NY"
        )

        let result = RouteAlertSubscription.copySettings(from: source, to: target)

        // Identity preserved
        XCTAssertEqual(result.fromStationCode, "TR", "Target from station should be preserved")
        XCTAssertEqual(result.toStationCode, "NY", "Target to station should be preserved")
        XCTAssertEqual(result.id, target.id, "Target id should be preserved")

        // Settings copied
        XCTAssertEqual(result.activeDays, 31, "Active days should be copied from source")
        XCTAssertEqual(result.activeStartMinutes, 360, "Start minutes should be copied from source")
        XCTAssertEqual(result.activeEndMinutes, 540, "End minutes should be copied from source")
        XCTAssertEqual(result.delayThresholdMinutes, 10, "Delay threshold should be copied from source")
        XCTAssertEqual(result.notifyCancellation, false, "Cancellation toggle should be copied from source")
        XCTAssertEqual(result.notifyDelay, true, "Delay toggle should be copied from source")
        XCTAssertEqual(result.notifyRecovery, true, "Recovery toggle should be copied from source")
        XCTAssertEqual(result.digestTimeMinutes, 420, "Digest time should be copied from source")
    }

    // MARK: - Commute Scenario: Independent Direction Configuration

    func testCommuteScenario_morningAndEveningDirections() {
        // User wants morning alerts for NY→TR (commute to work)
        // and evening alerts for TR→NY (commute home)
        let morningCommute = RouteAlertSubscription(
            dataSource: "NJT", fromStationCode: "NY", toStationCode: "TR",
            activeDays: 31,  // Weekdays only
            activeStartMinutes: 360,   // 6:00 AM
            activeEndMinutes: 540,     // 9:00 AM
            timezone: "America/New_York",
            delayThresholdMinutes: 5
        )
        let eveningCommute = RouteAlertSubscription(
            dataSource: "NJT", fromStationCode: "TR", toStationCode: "NY",
            activeDays: 31,  // Weekdays only
            activeStartMinutes: 960,   // 4:00 PM
            activeEndMinutes: 1140,    // 7:00 PM
            timezone: "America/New_York",
            delayThresholdMinutes: 10
        )

        service.addSubscriptions([morningCommute, eveningCommute])

        XCTAssertEqual(service.subscriptions.count, 2, "Both commute directions should be added")

        let morning = service.subscriptions.first { $0.fromStationCode == "NY" }!
        let evening = service.subscriptions.first { $0.fromStationCode == "TR" }!

        XCTAssertEqual(morning.activeStartMinutes, 360, "Morning commute starts at 6am")
        XCTAssertEqual(morning.activeEndMinutes, 540, "Morning commute ends at 9am")
        XCTAssertEqual(morning.delayThresholdMinutes, 5, "Morning: more sensitive to delays")

        XCTAssertEqual(evening.activeStartMinutes, 960, "Evening commute starts at 4pm")
        XCTAssertEqual(evening.activeEndMinutes, 1140, "Evening commute ends at 7pm")
        XCTAssertEqual(evening.delayThresholdMinutes, 10, "Evening: less sensitive to delays")
    }
}
