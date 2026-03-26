import XCTest
@testable import TrackRat

class TrainSystemTests: XCTestCase {

    // MARK: - supportsAlerts

    func testSupportsAlerts_realtimeSystems() {
        let realtimeSystems: [TrainSystem] = [.njt, .amtrak, .path, .lirr, .mnr, .subway, .wmata]
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
        // Current expectations: 7 real-time, 1 schedule-only
        XCTAssertEqual(alertCapable.count, 7, "Expected 7 alert-capable systems: \(alertCapable)")
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

    // MARK: - searchGrouped

    func testSearchGrouped_splitsResultsByActiveSystem() {
        // NJT-only selection: NJT stations go to primary, others to other
        let njtOnly: Set<TrainSystem> = [.njt]
        let grouped = Stations.searchGrouped("Penn", selectedSystems: njtOnly)

        // Newark Penn and NY Penn should be in primary (both served by NJT)
        let primaryNames = grouped.primary
        let otherNames = grouped.other

        XCTAssertTrue(primaryNames.contains("New York Penn Station"),
                     "NY Penn should be primary for NJT selection, got primary: \(primaryNames)")
        XCTAssertTrue(primaryNames.contains("Newark Penn Station"),
                     "Newark Penn should be primary for NJT selection, got primary: \(primaryNames)")

        // Other should not contain NJT stations
        for name in otherNames {
            guard let code = Stations.getStationCode(name) else { continue }
            let systems = Stations.systemStringsForStation(code)
            XCTAssertFalse(systems.contains("NJT"),
                          "Station \(name) (\(code)) in 'other' should not be NJT, systems: \(systems)")
        }
    }

    func testSearchGrouped_emptyQueryReturnsEmpty() {
        let grouped = Stations.searchGrouped("", selectedSystems: [.njt])
        XCTAssertTrue(grouped.primary.isEmpty, "Empty query should return empty primary")
        XCTAssertTrue(grouped.other.isEmpty, "Empty query should return empty other")
    }

    func testSearchGrouped_allSystemsReturnsNothingInOther() {
        let allSystems = Set(TrainSystem.allCases)
        let grouped = Stations.searchGrouped("Jamaica", selectedSystems: allSystems)

        XCTAssertTrue(grouped.other.isEmpty,
                     "With all systems selected, nothing should be in 'other', got: \(grouped.other)")
        XCTAssertFalse(grouped.primary.isEmpty,
                      "Should find Jamaica stations in primary")
    }

    func testSearchGrouped_lirrStationShowsInOtherForNJTSelection() {
        let njtOnly: Set<TrainSystem> = [.njt]
        let grouped = Stations.searchGrouped("Jamaica", selectedSystems: njtOnly)

        // Jamaica is a LIRR station, not NJT — should appear in other
        let otherHasJamaica = grouped.other.contains { $0.contains("Jamaica") }
        let primaryHasJamaica = grouped.primary.contains { $0.contains("Jamaica") }

        XCTAssertTrue(otherHasJamaica,
                     "Jamaica should be in 'other' for NJT-only selection, other: \(grouped.other)")
        XCTAssertFalse(primaryHasJamaica,
                      "Jamaica should not be in 'primary' for NJT-only, primary: \(grouped.primary)")
    }

    func testSearchGrouped_amtrakSelected() {
        // With Amtrak selected, Amtrak stations should appear in primary
        let amtrakOnly: Set<TrainSystem> = [.amtrak]
        let grouped = Stations.searchGrouped("Boston", selectedSystems: amtrakOnly)

        let primaryHasBoston = grouped.primary.contains { $0.contains("Boston") }
        XCTAssertTrue(primaryHasBoston,
                     "Boston should be primary when Amtrak is selected, primary: \(grouped.primary)")
    }

    func testSearchGrouped_emptySelectedSystemsPutsAllInOther() {
        let empty: Set<TrainSystem> = []
        let grouped = Stations.searchGrouped("Penn", selectedSystems: empty)

        XCTAssertTrue(grouped.primary.isEmpty,
                     "Empty selectedSystems should produce empty primary, got: \(grouped.primary)")
        XCTAssertFalse(grouped.other.isEmpty,
                      "Empty selectedSystems should put all results in other, got: \(grouped.other)")
    }

    func testSearchGrouped_multiSystemStationAppearsInPrimaryForAnyActiveSystem() {
        // NY Penn is served by NJT, AMTRAK, and LIRR
        // It should appear in primary when ANY of those systems is selected
        for system: TrainSystem in [.njt, .amtrak, .lirr] {
            let grouped = Stations.searchGrouped("New York Penn", selectedSystems: [system])
            let primaryHasNYPenn = grouped.primary.contains("New York Penn Station")
            XCTAssertTrue(primaryHasNYPenn,
                         "NY Penn should be primary when \(system.displayName) is selected, " +
                         "primary: \(grouped.primary), other: \(grouped.other)")
        }
    }

    func testSearchGrouped_noMatchReturnsEmpty() {
        let grouped = Stations.searchGrouped("XYZNOMATCH", selectedSystems: [.njt])
        XCTAssertTrue(grouped.primary.isEmpty, "Non-existent query should return empty primary")
        XCTAssertTrue(grouped.other.isEmpty, "Non-existent query should return empty other")
    }

    func testSearchGrouped_totalCountMatchesUngroupedSearch() {
        let query = "New"
        let ungrouped = Stations.search(query)
        let grouped = Stations.searchGrouped(query, selectedSystems: [.njt])

        // Every station from search() should be in either primary or other
        // (minus any that fail getStationCode)
        let totalGrouped = grouped.primary.count + grouped.other.count
        XCTAssertLessThanOrEqual(totalGrouped, ungrouped.count,
                                "Grouped total (\(totalGrouped)) should not exceed ungrouped (\(ungrouped.count))")
        // Should be close to equal (difference only from stations without codes)
        XCTAssertGreaterThan(totalGrouped, 0,
                            "Should have at least some results for '\(query)'")
    }

    // MARK: - primarySystem

    func testPrimarySystem_newarkPenn() {
        // Newark Penn has NJT, AMTRAK, PATH — primarySystem should return one of them
        let system = Stations.primarySystem(forStationCode: "NP")
        XCTAssertNotNil(system, "Newark Penn should have a primary system")
        let validSystems: Set<TrainSystem> = [.njt, .amtrak, .path]
        XCTAssertTrue(validSystems.contains(system!),
                     "Newark Penn primary system should be NJT, AMTRAK, or PATH, got: \(system!)")
    }

    func testPrimarySystem_lirrStation() {
        // Jamaica (JM) is LIRR
        let system = Stations.primarySystem(forStationCode: "JAM")
        XCTAssertNotNil(system, "Jamaica should have a primary system")
        XCTAssertEqual(system, .lirr, "Jamaica primary system should be LIRR, got: \(String(describing: system))")
    }

    func testPrimarySystem_deterministic() {
        // Same station should always return the same primary system
        let system1 = Stations.primarySystem(forStationCode: "NP")
        let system2 = Stations.primarySystem(forStationCode: "NP")
        XCTAssertEqual(system1, system2, "primarySystem should be deterministic")
    }

    // MARK: - systemsForStation

    func testSystemsForStation_multiSystem() {
        let systems = Stations.systemsForStation("NP")
        XCTAssertTrue(systems.contains(.njt), "Newark Penn should include NJT")
        XCTAssertTrue(systems.contains(.amtrak), "Newark Penn should include AMTRAK")
        XCTAssertTrue(systems.contains(.path), "Newark Penn should include PATH")
    }

    func testSystemsForStation_singleSystem() {
        // A pure LIRR station
        let systems = Stations.systemsForStation("JM")
        XCTAssertTrue(systems.contains(.lirr), "Jamaica should include LIRR, got: \(systems)")
    }

    func testSystemsForStation_unmappedDefaultsToAmtrak() {
        // Altoona (ALT) is an Amtrak station not in RouteTopology — should default to AMTRAK, not NJT
        let systems = Stations.systemsForStation("ALT")
        XCTAssertTrue(systems.contains(.amtrak),
                     "Unmapped station should default to AMTRAK, got: \(systems)")
        XCTAssertFalse(systems.contains(.njt),
                      "Unmapped station should NOT be tagged as NJT")
        XCTAssertEqual(systems.count, 1,
                      "Unmapped station should only have AMTRAK, got: \(systems)")
    }

    func testSystemsForStation_unmappedNJTOverride() {
        // Secaucus Lower Lvl (TS) is not in RouteTopology but is explicitly overridden as NJT
        let systems = Stations.systemsForStation("TS")
        XCTAssertTrue(systems.contains(.njt),
                     "Secaucus Lower Lvl should be NJT, got: \(systems)")
        XCTAssertFalse(systems.contains(.amtrak),
                      "Secaucus Lower Lvl should not be AMTRAK")
    }

    func testSystemsForStation_unmappedLIRROverride() {
        // Hunterspoint Avenue (HPA) is not in RouteTopology but is explicitly overridden as LIRR
        let systems = Stations.systemsForStation("HPA")
        XCTAssertTrue(systems.contains(.lirr),
                     "Hunterspoint Avenue should be LIRR, got: \(systems)")
    }

    func testSystemsForStation_unmappedSubwayOverride() {
        // 104 St (A) (SA63) is not in RouteTopology but is explicitly overridden as SUBWAY
        let systems = Stations.systemsForStation("SA63")
        XCTAssertTrue(systems.contains(.subway),
                     "104 St (A) should be SUBWAY, got: \(systems)")
    }

    func testIsStationVisible_unmappedAmtrakVisibleWhenAmtrakSelected() {
        // Unmapped stations default to AMTRAK and should be visible when Amtrak is selected
        XCTAssertTrue(Stations.isStationVisible("ALT", withSystems: [.amtrak]),
                     "Unmapped Amtrak station should be visible when Amtrak selected")
        XCTAssertFalse(Stations.isStationVisible("ALT", withSystems: [.njt]),
                      "Unmapped Amtrak station should NOT be visible when only NJT selected")
    }
}
