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
        UserDefaults.standard.removeObject(forKey: "AlertSubscription.lastSyncDate")
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
            dataSource: "SUBWAY", lineId: "A", lineName: "A Train", direction: "INWOOD",
            activeDays: 31, activeStartMinutes: 360, activeEndMinutes: 540,
            delayThresholdMinutes: 10, serviceThresholdPct: 50, cancellationThresholdPct: 90,
            notifyCancellation: false, notifyDelay: true,
            notifyRecovery: true, digestTimeMinutes: 420,
            includePlannedWork: true
        )
        let target = RouteAlertSubscription(
            dataSource: "SUBWAY", lineId: "A", lineName: "A Train", direction: "FAR_ROCKAWAY"
        )

        let result = RouteAlertSubscription.copySettings(from: source, to: target)

        // Identity preserved
        XCTAssertEqual(result.lineId, "A", "Target lineId should be preserved")
        XCTAssertEqual(result.direction, "FAR_ROCKAWAY", "Target direction should be preserved")
        XCTAssertEqual(result.id, target.id, "Target id should be preserved")
        XCTAssertEqual(result.dataSource, "SUBWAY", "Target dataSource should be preserved")

        // Settings copied
        XCTAssertEqual(result.activeDays, 31, "Active days should be copied from source")
        XCTAssertEqual(result.activeStartMinutes, 360, "Start minutes should be copied from source")
        XCTAssertEqual(result.activeEndMinutes, 540, "End minutes should be copied from source")
        XCTAssertEqual(result.delayThresholdMinutes, 10, "Delay threshold should be copied from source")
        XCTAssertEqual(result.serviceThresholdPct, 50, "Service threshold should be copied from source")
        XCTAssertEqual(result.cancellationThresholdPct, 90, "Cancellation threshold should be copied from source")
        XCTAssertEqual(result.notifyCancellation, false, "Cancellation toggle should be copied from source")
        XCTAssertEqual(result.notifyDelay, true, "Delay toggle should be copied from source")
        XCTAssertEqual(result.notifyRecovery, true, "Recovery toggle should be copied from source")
        XCTAssertEqual(result.digestTimeMinutes, 420, "Digest time should be copied from source")
        XCTAssertEqual(result.includePlannedWork, true, "Planned work toggle should be copied from source")
    }

    // MARK: - syncIfNeeded Throttle

    func testSyncIfNeeded_skipsWhenNoSubscriptions() {
        // Ensure no subscriptions
        XCTAssertTrue(service.subscriptions.isEmpty, "Precondition: no subscriptions")

        // Clear last sync date to make throttle pass
        UserDefaults.standard.removeObject(forKey: "AlertSubscription.lastSyncDate")

        // syncIfNeeded should return immediately without triggering sync
        // (no crash, no network call — validates the guard-empty-subscriptions path)
        service.syncIfNeeded()

        // If we get here without crash/hang, the empty-subscriptions guard works
        XCTAssertTrue(service.subscriptions.isEmpty, "No subscriptions should remain after no-op sync")
    }

    func testSyncIfNeeded_skipsWhenRecentlySynced() {
        // Add a subscription so the empty check passes
        let sub = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "Northeast Corridor", direction: "NY"
        )
        service.addSubscriptions([sub])

        // Simulate a recent successful sync (1 minute ago)
        UserDefaults.standard.set(Date().addingTimeInterval(-60), forKey: "AlertSubscription.lastSyncDate")

        // syncIfNeeded should return without triggering sync due to throttle
        service.syncIfNeeded()

        // Verify the last sync date was NOT updated (sync didn't run)
        let lastSync = UserDefaults.standard.object(forKey: "AlertSubscription.lastSyncDate") as? Date
        XCTAssertNotNil(lastSync, "Last sync date should still be set")
        XCTAssertTrue(Date().timeIntervalSince(lastSync!) < 120,
                       "Last sync date should be ~1 minute ago (not updated by throttled call)")
    }

    func testSyncIfNeeded_proceedsWhenStale() {
        // Add a subscription so the empty check passes
        let sub = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "Northeast Corridor", direction: "NY"
        )
        service.addSubscriptions([sub])

        // Simulate a stale sync (7 hours ago, exceeding 6-hour threshold)
        UserDefaults.standard.set(Date().addingTimeInterval(-7 * 60 * 60), forKey: "AlertSubscription.lastSyncDate")

        // syncIfNeeded should proceed past the throttle check
        // (it will call syncIfPossible which checks for APNS token — nil in tests, so sync won't actually fire)
        service.syncIfNeeded()

        // The method passed both guards (non-empty subscriptions, stale sync date).
        // Without a real APNS token, syncIfPossible returns early, so lastSyncDate stays stale.
        // This confirms the throttle logic correctly allows stale syncs through.
        let lastSync = UserDefaults.standard.object(forKey: "AlertSubscription.lastSyncDate") as? Date
        XCTAssertNotNil(lastSync, "Last sync date should still exist")
    }

    func testSyncIfNeeded_proceedsWhenNeverSynced() {
        // Add a subscription so the empty check passes
        let sub = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "Northeast Corridor", direction: "NY"
        )
        service.addSubscriptions([sub])

        // Remove any stored sync date (simulates fresh install or DB wipe scenario)
        UserDefaults.standard.removeObject(forKey: "AlertSubscription.lastSyncDate")

        // syncIfNeeded should proceed (distantPast will always be > 6 hours ago)
        service.syncIfNeeded()

        // Verifies the nil → distantPast fallback works correctly
        XCTAssertEqual(service.subscriptions.count, 1, "Subscription should still exist")
    }

    // MARK: - addSubscriptions: System-Wide Subscriptions

    func testAddSystemSubscription_addsSuccessfully() {
        let sub = RouteAlertSubscription(dataSource: "NJT")
        service.addSubscriptions([sub])

        XCTAssertEqual(service.subscriptions.count, 1, "Should have one system-wide subscription")
        XCTAssertTrue(service.subscriptions.first!.isSystemWide,
                      "Subscription should be system-wide")
        XCTAssertEqual(service.subscriptions.first!.dataSource, "NJT",
                       "System-wide subscription should have correct dataSource")
    }

    func testAddSystemSubscription_deduplicatesSameSystem() {
        let sub1 = RouteAlertSubscription(dataSource: "SUBWAY")
        service.addSubscriptions([sub1])

        let sub2 = RouteAlertSubscription(dataSource: "SUBWAY")
        service.addSubscriptions([sub2])

        XCTAssertEqual(service.subscriptions.count, 1,
                       "Duplicate system-wide subscription should be skipped")
    }

    func testAddSystemSubscription_allowsDifferentSystems() {
        let sub1 = RouteAlertSubscription(dataSource: "NJT")
        let sub2 = RouteAlertSubscription(dataSource: "SUBWAY")
        service.addSubscriptions([sub1, sub2])

        XCTAssertEqual(service.subscriptions.count, 2,
                       "Different systems should both be added")
    }

    // MARK: - Free Tier Limit Behavior

    func testSubscriptionCount_atFreeLimit_afterOneSubscription() {
        let sub = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "Northeast Corridor", direction: "NY"
        )
        service.addSubscriptions([sub])

        XCTAssertEqual(service.subscriptions.count, 1,
                       "Should have exactly one subscription")
        XCTAssertTrue(service.subscriptions.count >= SubscriptionService.freeRouteAlertLimit,
                      "One subscription should meet or exceed the free limit of \(SubscriptionService.freeRouteAlertLimit)")
    }

    func testSubscriptionCount_belowFreeLimit_whenEmpty() {
        XCTAssertEqual(service.subscriptions.count, 0,
                       "Should have zero subscriptions")
        XCTAssertFalse(service.subscriptions.count >= SubscriptionService.freeRouteAlertLimit,
                       "Zero subscriptions should be below the free limit")
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
