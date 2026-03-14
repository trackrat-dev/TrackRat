import XCTest
@testable import TrackRat

class TrainSystemTests: XCTestCase {

    // MARK: - supportsAlerts

    func testSupportsAlerts_realtimeSystems() {
        let realtimeSystems: [TrainSystem] = [.njt, .amtrak, .path, .lirr, .mnr, .subway]
        for system in realtimeSystems {
            XCTAssertTrue(
                system.supportsAlerts,
                "\(system.displayName) has real-time data and should support alerts"
            )
        }
    }

    func testSupportsAlerts_scheduleOnlySystems() {
        let scheduleOnlySystems: [TrainSystem] = [.patco]
        for system in scheduleOnlySystems {
            XCTAssertFalse(
                system.supportsAlerts,
                "\(system.displayName) is schedule-only and should not support alerts"
            )
        }
    }

    func testSupportsAlerts_coversAllCases() {
        // Ensures every TrainSystem case has been considered.
        // If a new case is added to TrainSystem, this test forces the developer
        // to explicitly decide whether it supports alerts.
        let allSystems = TrainSystem.allCases
        let alertCapable = allSystems.filter { $0.supportsAlerts }
        let scheduleOnly = allSystems.filter { !$0.supportsAlerts }

        XCTAssertEqual(
            alertCapable.count + scheduleOnly.count,
            allSystems.count,
            "Every TrainSystem must be classified as either alert-capable or schedule-only"
        )
        // Current expectations: 6 real-time, 1 schedule-only
        XCTAssertEqual(alertCapable.count, 6, "Expected 6 alert-capable systems: \(alertCapable)")
        XCTAssertEqual(scheduleOnly.count, 1, "Expected 1 schedule-only system: \(scheduleOnly)")
    }

    // MARK: - Alert-capable filtering (Set extension)

    func testAlertCapableFiltering() {
        let allSystems: Set<TrainSystem> = Set(TrainSystem.allCases)
        let filtered = allSystems.filter { $0.supportsAlerts }

        XCTAssertTrue(filtered.contains(.njt), "NJT should be in alert-capable set")
        XCTAssertTrue(filtered.contains(.path), "PATH should be in alert-capable set")
        XCTAssertFalse(filtered.contains(.patco), "PATCO should not be in alert-capable set")
    }

    func testAlertCapableFiltering_patcoOnly() {
        let patcoOnly: Set<TrainSystem> = [.patco]
        let filtered = patcoOnly.filter { $0.supportsAlerts }
        XCTAssertTrue(filtered.isEmpty, "PATCO-only selection should yield empty alert-capable set")
    }

    func testAlertCapableFiltering_mixedSelection() {
        let mixed: Set<TrainSystem> = [.patco, .njt, .path]
        let filtered = mixed.filter { $0.supportsAlerts }
        XCTAssertEqual(filtered.count, 2, "Should have 2 alert-capable systems from mixed selection")
        XCTAssertTrue(filtered.contains(.njt))
        XCTAssertTrue(filtered.contains(.path))
        XCTAssertFalse(filtered.contains(.patco))
    }
}
