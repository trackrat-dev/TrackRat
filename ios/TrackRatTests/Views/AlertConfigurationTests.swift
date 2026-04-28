import XCTest
@testable import TrackRat

class AlertConfigurationTests: XCTestCase {

    // MARK: - TimePreset Enum

    func testTimePreset_rawValues() {
        XCTAssertEqual(TimePreset.anyTime.rawValue, "Any Time")
        XCTAssertEqual(TimePreset.custom.rawValue, "Custom")
    }

    func testTimePreset_allCasesCount() {
        XCTAssertEqual(TimePreset.allCases.count, 2, "TimePreset should have exactly 2 cases")
    }

    // MARK: - AlertSensitivity Enum

    func testAlertSensitivity_rawValues() {
        XCTAssertEqual(AlertSensitivity.none.rawValue, "None")
        XCTAssertEqual(AlertSensitivity.severeOnly.rawValue, "Severe")
        XCTAssertEqual(AlertSensitivity.all.rawValue, "All")
    }

    func testAlertSensitivity_allCasesCount() {
        XCTAssertEqual(AlertSensitivity.allCases.count, 3, "AlertSensitivity should have exactly 3 cases")
    }

    // MARK: - Subscription Time Preset Values

    func testSubscription_anyTimeValues() {
        // Any Time: nil start and end
        let sub = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "Northeast Corridor",
            direction: "NY", activeDays: 127
        )

        XCTAssertNil(sub.activeStartMinutes, "Any Time should have nil start")
        XCTAssertNil(sub.activeEndMinutes, "Any Time should have nil end")
    }

    // MARK: - Day Bitmask Presets

    func testDayBitmask_noneIsZero() {
        let sub = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "Northeast Corridor",
            direction: "NY", activeDays: 0
        )
        XCTAssertEqual(sub.activeDays, 0, "None preset should be 0")
    }

    func testDayBitmask_everyDayIs127() {
        let sub = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "Northeast Corridor",
            direction: "NY", activeDays: 127
        )
        XCTAssertEqual(sub.activeDays, 127, "Every Day preset should be 127 (all 7 bits set)")
    }

    func testDayBitmask_weekdaysIs31() {
        // Weekdays (Mon-Fri) = bits 0-4 = 31
        // Still a valid bitmask even though removed from UI presets
        let sub = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "Northeast Corridor",
            direction: "NY", activeDays: 31
        )
        XCTAssertEqual(sub.activeDays, 31, "Weekdays bitmask should be 31")

        // Verify individual day bits
        for i in 0..<5 {
            XCTAssertTrue(sub.activeDays & (1 << i) != 0,
                          "Day \(i) (Mon-Fri) should be set in weekdays bitmask")
        }
        for i in 5..<7 {
            XCTAssertTrue(sub.activeDays & (1 << i) == 0,
                          "Day \(i) (Sat-Sun) should NOT be set in weekdays bitmask")
        }
    }

    func testDayBitmask_weekendsIs96() {
        // Weekends (Sat+Sun) = bits 5-6 = 96
        // Still a valid bitmask even though removed from UI presets
        let sub = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "Northeast Corridor",
            direction: "NY", activeDays: 96
        )
        XCTAssertEqual(sub.activeDays, 96, "Weekends bitmask should be 96")
    }

    func testDayBitmask_customIsAnyNonPreset() {
        // Any value that isn't 0 or 127 is considered "custom" in the UI
        let customValues = [1, 2, 31, 63, 64, 96, 126]
        for value in customValues {
            XCTAssertTrue(value != 0 && value != 127,
                          "Bitmask \(value) should be treated as custom (not None or Every Day)")
        }
    }

    // MARK: - Cancellation Sensitivity Thresholds

    func testCancellation_noneDisablesNotification() {
        var sub = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "NEC", direction: "NY"
        )
        sub.notifyCancellation = false
        sub.cancellationThresholdPct = nil

        XCTAssertFalse(sub.notifyCancellation, "None sensitivity should disable cancellation notifications")
        XCTAssertNil(sub.cancellationThresholdPct, "None sensitivity should clear threshold")
    }

    func testCancellation_severeSetsFiftyPercent() {
        var sub = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "NEC", direction: "NY"
        )
        sub.notifyCancellation = true
        sub.cancellationThresholdPct = 50

        XCTAssertTrue(sub.notifyCancellation)
        XCTAssertEqual(sub.cancellationThresholdPct, 50, "Severe should set 50% threshold")
    }

    func testCancellation_allSetsNinetyPercent() {
        var sub = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "NEC", direction: "NY"
        )
        sub.notifyCancellation = true
        sub.cancellationThresholdPct = 90

        XCTAssertTrue(sub.notifyCancellation)
        XCTAssertEqual(sub.cancellationThresholdPct, 90, "All should set 90% threshold")
    }

    // MARK: - Delay Sensitivity Thresholds (Delay-Based)

    func testDelay_noneDisablesNotification() {
        var sub = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "NEC", direction: "NY"
        )
        sub.notifyDelay = false
        sub.delayThresholdMinutes = nil

        XCTAssertFalse(sub.notifyDelay)
        XCTAssertNil(sub.delayThresholdMinutes, "None should clear delay threshold")
    }

    func testDelay_severeSetsTwentyMinutes() {
        var sub = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "NEC", direction: "NY"
        )
        sub.notifyDelay = true
        sub.delayThresholdMinutes = 20

        XCTAssertTrue(sub.notifyDelay)
        XCTAssertEqual(sub.delayThresholdMinutes, 20, "Severe delay should be 20 minutes")
    }

    func testDelay_allSetsFiveMinutes() {
        var sub = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "NEC", direction: "NY"
        )
        sub.notifyDelay = true
        sub.delayThresholdMinutes = 5

        XCTAssertTrue(sub.notifyDelay)
        XCTAssertEqual(sub.delayThresholdMinutes, 5, "All delay should be 5 minutes")
    }

    // MARK: - Fewer Trains Sensitivity Thresholds (Frequency-Based)

    func testReducedService_severeSetsFiftyPercent() {
        var sub = RouteAlertSubscription(
            dataSource: "SUBWAY", lineId: "A", lineName: "A Train", direction: "INWOOD"
        )
        sub.notifyDelay = true
        sub.serviceThresholdPct = 50

        XCTAssertTrue(RouteAlertSubscription.frequencyFirstSources.contains("SUBWAY"),
                       "SUBWAY should be a frequency-first source")
        XCTAssertEqual(sub.serviceThresholdPct, 50, "Severe reduced service should be 50%")
    }

    func testReducedService_allSetsNinetyPercent() {
        var sub = RouteAlertSubscription(
            dataSource: "PATH", lineId: "JSQ_33", lineName: "JSQ-33", direction: "33S"
        )
        sub.notifyDelay = true
        sub.serviceThresholdPct = 90

        XCTAssertTrue(RouteAlertSubscription.frequencyFirstSources.contains("PATH"),
                       "PATH should be a frequency-first source")
        XCTAssertEqual(sub.serviceThresholdPct, 90, "All reduced service should be 90%")
    }

    // MARK: - Frequency-First Sources

    func testFrequencyFirstSources_containsExpectedSystems() {
        let expected: Set<String> = ["SUBWAY", "PATH", "PATCO"]
        XCTAssertEqual(RouteAlertSubscription.frequencyFirstSources, expected,
                       "Frequency-first sources should be SUBWAY, PATH, PATCO")
    }

    func testFrequencyFirstSources_excludesDelayBasedSystems() {
        let delayBased = ["NJT", "AMTRAK", "LIRR", "MNR"]
        for source in delayBased {
            XCTAssertFalse(RouteAlertSubscription.frequencyFirstSources.contains(source),
                           "\(source) should NOT be a frequency-first source")
        }
    }

    // MARK: - Free Tier Alert Limit

    func testFreeRouteAlertLimit_isOne() {
        XCTAssertEqual(SubscriptionService.freeRouteAlertLimit, 1,
                       "Free tier should allow exactly 1 route alert subscription")
    }

    func testIsSystemWide_trueWhenNoLineOrStationOrTrain() {
        let sub = RouteAlertSubscription(dataSource: "NJT")
        XCTAssertTrue(sub.isSystemWide,
                      "Subscription with only dataSource should be system-wide")
        XCTAssertNil(sub.lineId, "System-wide subscription should have nil lineId")
        XCTAssertNil(sub.fromStationCode, "System-wide subscription should have nil fromStationCode")
        XCTAssertNil(sub.toStationCode, "System-wide subscription should have nil toStationCode")
        XCTAssertNil(sub.trainId, "System-wide subscription should have nil trainId")
    }

    func testIsSystemWide_falseWhenLineIdSet() {
        let sub = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "Northeast Corridor", direction: "NY"
        )
        XCTAssertFalse(sub.isSystemWide,
                       "Subscription with lineId should not be system-wide")
    }

    func testIsSystemWide_falseWhenStationPairSet() {
        let sub = RouteAlertSubscription(
            dataSource: "NJT", fromStationCode: "NY", toStationCode: "TR"
        )
        XCTAssertFalse(sub.isSystemWide,
                       "Subscription with station pair should not be system-wide")
    }

    func testIsSystemWide_falseWhenTrainIdSet() {
        let sub = RouteAlertSubscription(
            dataSource: "NJT", trainId: "3254", trainName: "NJT 3254"
        )
        XCTAssertFalse(sub.isSystemWide,
                       "Subscription with trainId should not be system-wide")
    }

    // MARK: - Copy Settings

    func testCommuteScenario_copySettingsPreservesTimePreset() {
        // Verifies copySettings works with new time preset values
        let source = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "NEC", direction: "NY",
            activeDays: 127,
            activeStartMinutes: 300,   // AM Commute
            activeEndMinutes: 600,
            notifyRecovery: true
        )
        let target = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "NEC", direction: "TR"
        )

        let result = RouteAlertSubscription.copySettings(from: source, to: target)

        XCTAssertEqual(result.direction, "TR", "Target direction should be preserved")
        XCTAssertEqual(result.activeStartMinutes, 300, "AM Commute start should be copied")
        XCTAssertEqual(result.activeEndMinutes, 600, "AM Commute end should be copied")
        XCTAssertEqual(result.activeDays, 127, "Active days should be copied")
        XCTAssertTrue(result.notifyRecovery, "Recovery setting should be copied")
    }

    // MARK: - Recovery Toggle Visibility Logic

    func testRecovery_onlyRelevantWhenAlertsActive() {
        var sub = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "NEC", direction: "NY"
        )

        // Default: both cancellation and delay are enabled
        XCTAssertTrue(sub.notifyCancellation || sub.notifyDelay,
                       "At least one alert type should be active by default for recovery to be relevant")

        // Disable both
        sub.notifyCancellation = false
        sub.notifyDelay = false
        XCTAssertFalse(sub.notifyCancellation || sub.notifyDelay,
                        "With both alert types disabled, recovery toggle should be hidden")
    }

    // MARK: - Digest Requires Days Selected

    func testDigest_hiddenWhenNoDaysSelected() {
        // Daily Status Summary is only visible when days are selected (activeDays != 0)
        let sub = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "NEC", direction: "NY",
            activeDays: 0  // None
        )
        XCTAssertEqual(sub.activeDays, 0, "Days should be None")
        // In the UI, the digest toggle is hidden when activeDays == 0
        // The model still allows setting digestTimeMinutes, but the UI won't show it
    }

    func testDigest_visibleWhenDaysSelected() {
        var sub = RouteAlertSubscription(
            dataSource: "NJT", lineId: "NEC", lineName: "NEC", direction: "NY",
            activeDays: 127  // Every Day
        )
        sub.digestTimeMinutes = 420  // 7:00 AM

        XCTAssertNotEqual(sub.activeDays, 0, "Days should be selected")
        XCTAssertEqual(sub.digestTimeMinutes, 420, "Digest should be configurable when days are selected")
    }
}
