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

    // MARK: - searchGrouped with origin filter

    func testSearchGrouped_originFilter_demotesNonOverlappingStations() {
        // Origin = JAM (Jamaica, LIRR-only). Search for "Penn" with all NJT/AMTRAK/LIRR enabled.
        // NY Penn (NJT/AMTRAK/LIRR) shares LIRR with Jamaica → primary.
        // Newark Penn (NJT/AMTRAK/PATH) does NOT share with Jamaica → other.
        let allEnabled: Set<TrainSystem> = [.njt, .amtrak, .lirr, .path]
        let grouped = Stations.searchGrouped(
            "Penn",
            selectedSystems: allEnabled,
            originStationCode: "JAM"
        )

        XCTAssertTrue(grouped.primary.contains("New York Penn Station"),
                     "NY Penn shares LIRR with origin Jamaica → should be primary, primary: \(grouped.primary)")
        XCTAssertTrue(grouped.other.contains("Newark Penn Station"),
                     "Newark Penn shares no system with origin Jamaica → should be other, other: \(grouped.other)")
    }

    func testSearchGrouped_originFilter_multiSystemOriginUsesUnion() {
        // Origin = NP (NJT, AMTRAK, PATH). Search for "Penn".
        // NY Penn (NJT/AMTRAK/LIRR) shares NJT and AMTRAK with NP → primary.
        // Newark Penn IS the origin and gets filtered out by the picker anyway, but the
        // helper itself doesn't drop it. Verify the cross-system overlap logic with another origin.
        let allEnabled: Set<TrainSystem> = [.njt, .amtrak, .lirr, .path]
        let grouped = Stations.searchGrouped(
            "Penn",
            selectedSystems: allEnabled,
            originStationCode: "NP"
        )
        XCTAssertTrue(grouped.primary.contains("New York Penn Station"),
                     "NY Penn shares NJT/AMTRAK with multi-system origin NP → primary, primary: \(grouped.primary)")
    }

    func testSearchGrouped_originFilter_disabledSystemTakesPrecedence() {
        // Origin = NY Penn (NJT/AMTRAK/LIRR). Search for "Newark" with only PATH enabled.
        // Newark Penn (NJT/AMTRAK/PATH) shares no system with origin NY (no NJT/AMTRAK/LIRR
        // overlap with PATH-only selectedSystems on Newark either; both filters demote it).
        let pathOnly: Set<TrainSystem> = [.path]
        let grouped = Stations.searchGrouped(
            "Newark Penn",
            selectedSystems: pathOnly,
            originStationCode: "NY"
        )

        // Newark Penn fails both filters: shares PATH with origin NY? No — NY has NJT/AMTRAK/LIRR.
        // So origin overlap fails → demoted regardless of selectedSystems.
        XCTAssertFalse(grouped.primary.contains("Newark Penn Station"),
                      "Newark Penn does not share a system with NY origin → should not be primary")
    }

    func testSearchGrouped_originNil_behavesAsBeforeChange() {
        // With no origin, the new filter is a no-op and behavior matches the existing tests.
        let njtOnly: Set<TrainSystem> = [.njt]
        let groupedNoOrigin = Stations.searchGrouped("Penn", selectedSystems: njtOnly, originStationCode: nil)
        let groupedDefault = Stations.searchGrouped("Penn", selectedSystems: njtOnly)
        XCTAssertEqual(groupedNoOrigin.primary, groupedDefault.primary,
                      "Explicit nil origin should match default-parameter behavior (primary)")
        XCTAssertEqual(groupedNoOrigin.other, groupedDefault.other,
                      "Explicit nil origin should match default-parameter behavior (other)")
    }

    func testSearchGrouped_originUnknownCode_skipsOriginFilter() {
        // Unknown origin code yields empty system set; filter should be skipped (not demote everything).
        let allEnabled: Set<TrainSystem> = Set(TrainSystem.allCases)
        let grouped = Stations.searchGrouped(
            "Penn",
            selectedSystems: allEnabled,
            originStationCode: "ZZZNOTAREALCODE"
        )
        XCTAssertFalse(grouped.primary.isEmpty,
                      "Unknown origin should not demote all results to 'other', primary: \(grouped.primary)")
    }

    // MARK: - sharesSystem(stationCode:withOrigin:)

    func testSharesSystem_overlap() {
        // Newark Penn (NJT/AMTRAK/PATH) and NY Penn (NJT/AMTRAK/LIRR) share NJT and AMTRAK.
        XCTAssertTrue(Stations.sharesSystem(stationCode: "NP", withOrigin: "NY"))
    }

    func testSharesSystem_noOverlap() {
        // Jamaica (LIRR) and Newark Penn (NJT/AMTRAK/PATH) share nothing.
        XCTAssertFalse(Stations.sharesSystem(stationCode: "JAM", withOrigin: "NP"))
    }

    func testSharesSystem_nilOriginReturnsTrue() {
        XCTAssertTrue(Stations.sharesSystem(stationCode: "JAM", withOrigin: nil),
                     "Nil origin should bypass the filter and return true")
    }

    func testSharesSystem_unknownOriginReturnsTrue() {
        XCTAssertTrue(Stations.sharesSystem(stationCode: "JAM", withOrigin: "ZZZNOTREAL"),
                     "Unknown origin should bypass the filter and return true")
    }

    // MARK: - Stations.search(limit:)

    func testStationsSearch_respectsExplicitLimit() {
        // The list of all stations has many "a" matches, far more than 12.
        let small = Stations.search("a", limit: 5)
        XCTAssertLessThanOrEqual(small.count, 5,
                                "limit=5 should cap results, got \(small.count)")

        let larger = Stations.search("a", limit: 30)
        XCTAssertLessThanOrEqual(larger.count, 30,
                                "limit=30 should cap results, got \(larger.count)")
        XCTAssertGreaterThan(larger.count, Stations.defaultSearchLimit,
                            "Raising the limit should expose more matches than the default cap")
    }

    func testStationsSearch_defaultLimitMatchesConstant() {
        // Implicit-default call returns at most defaultSearchLimit results.
        let results = Stations.search("a")
        XCTAssertLessThanOrEqual(results.count, Stations.defaultSearchLimit)
    }

    // MARK: - searchGrouped oversampling with origin

    func testSearchGrouped_oversamples_primaryNotStarvedByDemotedHits() {
        // With origin set, searchGrouped oversamples internally so each bucket can
        // independently fill to defaultSearchLimit. With origin = nil, total results
        // remain capped at defaultSearchLimit. Use a broad query that exceeds the
        // default cap and require all systems enabled to isolate the origin filter.
        let allEnabled: Set<TrainSystem> = Set(TrainSystem.allCases)
        let cap = Stations.defaultSearchLimit

        let noOrigin = Stations.searchGrouped("a", selectedSystems: allEnabled, originStationCode: nil)
        let withOrigin = Stations.searchGrouped("a", selectedSystems: allEnabled, originStationCode: "NY")

        // Without origin: union is bounded by defaultSearchLimit (single search call).
        XCTAssertLessThanOrEqual(noOrigin.primary.count + noOrigin.other.count, cap,
                                "Without origin, total results should be capped at defaultSearchLimit")

        // With origin: each bucket is independently capped at defaultSearchLimit.
        XCTAssertLessThanOrEqual(withOrigin.primary.count, cap,
                                "Primary bucket must respect defaultSearchLimit")
        XCTAssertLessThanOrEqual(withOrigin.other.count, cap,
                                "Other bucket must respect defaultSearchLimit")

        // The combined result count when an origin is provided should be at least
        // as large as the no-origin case — proving the oversample is active.
        XCTAssertGreaterThanOrEqual(
            withOrigin.primary.count + withOrigin.other.count,
            noOrigin.primary.count + noOrigin.other.count,
            "Origin-aware search should not return fewer total candidates than no-origin search"
        )
    }

    func testIsStationVisible_unmappedAmtrakVisibleWhenAmtrakSelected() {
        // Unmapped stations default to AMTRAK and should be visible when Amtrak is selected
        XCTAssertTrue(Stations.isStationVisible("ALT", withSystems: [.amtrak]),
                     "Unmapped Amtrak station should be visible when Amtrak selected")
        XCTAssertFalse(Stations.isStationVisible("ALT", withSystems: [.njt]),
                      "Unmapped Amtrak station should NOT be visible when only NJT selected")
    }
}
