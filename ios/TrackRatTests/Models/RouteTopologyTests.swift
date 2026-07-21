import XCTest
@testable import TrackRat

class RouteTopologyTests: XCTestCase {

    // MARK: - routeContaining Tests

    func testRouteContainingFindsNJTNortheastCorridor() {
        // NY (New York Penn) and TR (Trenton) are on the NJT Northeast Corridor
        let route = RouteTopology.routeContaining(from: "NY", to: "TR", dataSource: "NJT")
        XCTAssertNotNil(route, "Should find a route containing NY and TR on NJT")
        XCTAssertEqual(route?.id, "njt-nec", "NY to TR should be on the Northeast Corridor")
        XCTAssertEqual(route?.dataSource, "NJT")
    }

    func testRouteContainingFindsReverseDirection() {
        // TR → NY is reverse direction but should still match NEC
        let route = RouteTopology.routeContaining(from: "TR", to: "NY", dataSource: "NJT")
        XCTAssertNotNil(route, "Should find a route for reverse direction TR → NY")
        XCTAssertEqual(route?.id, "njt-nec", "TR to NY should still match the Northeast Corridor")
    }

    func testRouteContainingFiltersByDataSource() {
        // NY exists on NJT routes but searching with wrong data source should not match NJT routes
        let route = RouteTopology.routeContaining(from: "NY", to: "TR", dataSource: "PATH")
        // PATH doesn't have NY→TR so this should either be nil or find a different route
        if let route = route {
            XCTAssertEqual(route.dataSource, "PATH", "Returned route should match requested data source")
        }
    }

    func testRouteContainingReturnsNilForUnknownStations() {
        let route = RouteTopology.routeContaining(from: "NONEXISTENT1", to: "NONEXISTENT2", dataSource: "NJT")
        XCTAssertNil(route, "Should return nil for stations that don't exist on any route")
    }

    func testRouteContainingPrefersForwardDirection() {
        // When from < to in the route's station order, that route should be preferred
        let route = RouteTopology.routeContaining(from: "NY", to: "TR", dataSource: "NJT")
        XCTAssertNotNil(route)
        if let route = route {
            let fromIdx = route.stationCodes.firstIndex(of: "NY")
            let toIdx = route.stationCodes.firstIndex(of: "TR")
            XCTAssertNotNil(fromIdx, "From station should exist in route")
            XCTAssertNotNil(toIdx, "To station should exist in route")
            if let f = fromIdx, let t = toIdx {
                XCTAssertLessThan(f, t, "Forward direction match should have from before to")
            }
        }
    }

    func testRouteContainingFindsPATHRoute() {
        // PNK (Newark) and PWC (World Trade Center) are on PATH
        let route = RouteTopology.routeContaining(from: "PNK", to: "PWC", dataSource: "PATH")
        XCTAssertNotNil(route, "Should find a PATH route containing PNK and PWC")
        XCTAssertEqual(route?.dataSource, "PATH")
    }

    func testRouteContainingFindsHobokenPATHRouteViaEquivalent() {
        let route = RouteTopology.routeContaining(from: "HB", to: "P33", dataSource: "PATH")
        XCTAssertNotNil(route, "Should find a PATH route from canonical Hoboken to 33rd Street")
        XCTAssertEqual(route?.dataSource, "PATH")
    }

    func testRouteContainingReturnsNilForPartialMatch() {
        // When only one station matches, return nil rather than a misleading partial match
        let route = RouteTopology.routeContaining(from: "NY", to: "NONEXISTENT", dataSource: "NJT")
        XCTAssertNil(route, "Should return nil when only one station matches (no last-resort fallback)")
    }

    func testRouteContainingResolvesCrossPlatformViaEquivalents() {
        // SG29 (Metropolitan Av, G line) and S635 (14 St-Union Sq, 4/5/6)
        // Neither is on the L line, but their equivalents are: SG29↔SL10, S635↔SL03
        let route = RouteTopology.routeContaining(from: "SG29", to: "S635", dataSource: "SUBWAY")
        XCTAssertNotNil(route, "Should find L line via station equivalents for SG29→S635")
        XCTAssertEqual(route?.id, "subway-l", "Cross-platform transfer SG29→S635 should resolve to the L line")
    }

    func testRouteContainingResolvesCrossPlatformReverse() {
        // Same as above but reversed direction
        let route = RouteTopology.routeContaining(from: "S635", to: "SG29", dataSource: "SUBWAY")
        XCTAssertNotNil(route, "Should find L line via equivalents in reverse direction")
        XCTAssertEqual(route?.id, "subway-l", "Reverse cross-platform transfer should also resolve to L line")
    }

    // MARK: - allRoutes Validation

    func testAllRoutesNotEmpty() {
        XCTAssertFalse(RouteTopology.allRoutes.isEmpty, "Should have route definitions")
        XCTAssertGreaterThan(RouteTopology.allRoutes.count, 10, "Should have substantial number of routes")
    }

    func testAllRoutesHaveUniqueIds() {
        let ids = RouteTopology.allRoutes.map { $0.id }
        let uniqueIds = Set(ids)
        XCTAssertEqual(ids.count, uniqueIds.count, "All route IDs should be unique")
    }

    func testAllRoutesHaveAtLeastTwoStations() {
        for route in RouteTopology.allRoutes {
            XCTAssertGreaterThanOrEqual(
                route.stationCodes.count, 2,
                "Route \(route.id) (\(route.name)) should have at least 2 stations, has \(route.stationCodes.count)"
            )
        }
    }

    // MARK: - routesContaining (plural)

    func testRoutesContainingFindsMultipleSubwayRoutes() {
        // S137 and S136 are on the shared 1/2/3 trunk (7th Avenue)
        let routes = RouteTopology.routesContaining(from: "S137", to: "S136", dataSource: "SUBWAY")
        let ids = Set(routes.map { $0.id })
        XCTAssertTrue(ids.contains("subway-1"), "S137→S136 should match the 1 train")
        XCTAssertTrue(ids.contains("subway-2"), "S137→S136 should match the 2 train")
        XCTAssertGreaterThanOrEqual(routes.count, 2, "Should find at least 2 routes for shared trunk stations")
    }

    func testRoutesContainingFindsABCSharedTrunk() {
        // SA24 and SA22 are on the shared A/B/C trunk (8th Avenue)
        let routes = RouteTopology.routesContaining(from: "SA24", to: "SA22", dataSource: "SUBWAY")
        let ids = Set(routes.map { $0.id })
        XCTAssertTrue(ids.contains("subway-a"), "SA24→SA22 should match the A train")
        XCTAssertTrue(ids.contains("subway-c"), "SA24→SA22 should match the C train")
        XCTAssertGreaterThanOrEqual(routes.count, 2, "Should find at least 2 routes for A/B/C shared trunk")
    }

    func testRoutesContainingReturnsEmptyForUnknownStations() {
        let routes = RouteTopology.routesContaining(from: "FAKE1", to: "FAKE2", dataSource: "SUBWAY")
        XCTAssertTrue(routes.isEmpty, "Should return empty array for unknown stations")
    }

    func testRoutesContainingFiltersByDataSource() {
        // S137 is a subway station, should not match NJT
        let routes = RouteTopology.routesContaining(from: "S137", to: "S136", dataSource: "NJT")
        XCTAssertTrue(routes.isEmpty, "Subway station codes should not match NJT data source")
    }

    func testRoutesContainingReturnsSingleRouteForUniqueSegment() {
        // NJT NEC is typically the only NJT route with NY and TR
        let routes = RouteTopology.routesContaining(from: "NY", to: "TR", dataSource: "NJT")
        XCTAssertEqual(routes.count, 1, "NY→TR on NJT should match exactly one route")
        XCTAssertEqual(routes.first?.id, "njt-nec")
    }

    // MARK: - Amtrak NEC includes NJT shared stations

    func testAmtrakNECIncludesPrincetonJunction() {
        let route = RouteTopology.routeContaining(from: "PJ", to: "NY", dataSource: "AMTRAK")
        XCTAssertNotNil(route, "Amtrak NEC should contain Princeton Junction (PJ)")
        XCTAssertEqual(route?.id, "amtrak-nec", "PJ→NY on AMTRAK should match the Northeast Corridor")
    }

    func testAmtrakNECIncludesMetropark() {
        let route = RouteTopology.routeContaining(from: "MP", to: "NY", dataSource: "AMTRAK")
        XCTAssertNotNil(route, "Amtrak NEC should contain Metropark (MP)")
        XCTAssertEqual(route?.id, "amtrak-nec", "MP→NY on AMTRAK should match the Northeast Corridor")
    }

    func testAmtrakNECIncludesNewBrunswick() {
        let route = RouteTopology.routeContaining(from: "NB", to: "NY", dataSource: "AMTRAK")
        XCTAssertNotNil(route, "Amtrak NEC should contain New Brunswick (NB)")
        XCTAssertEqual(route?.id, "amtrak-nec", "NB→NY on AMTRAK should match the Northeast Corridor")
    }

    func testAmtrakKeystoneIncludesNJTSharedStations() {
        // Metropark, New Brunswick, Princeton Junction are between NP and TR on Keystone too
        let route = RouteTopology.routeContaining(from: "PJ", to: "PH", dataSource: "AMTRAK")
        XCTAssertNotNil(route, "Amtrak Keystone should contain Princeton Junction (PJ)")
    }

    func testPrincetonJunctionToNYRouteOnBothSystems() {
        // PJ→NY should be findable on both NJT and AMTRAK
        let njtRoute = RouteTopology.routeContaining(from: "PJ", to: "NY", dataSource: "NJT")
        let amtrakRoute = RouteTopology.routeContaining(from: "PJ", to: "NY", dataSource: "AMTRAK")
        XCTAssertNotNil(njtRoute, "PJ→NY should exist on NJT")
        XCTAssertNotNil(amtrakRoute, "PJ→NY should exist on AMTRAK")
        XCTAssertNotEqual(njtRoute?.id, amtrakRoute?.id,
                         "NJT and AMTRAK routes should be different routes")
    }

    func testAmtrakNECIncludesCornwellsHeights() {
        let route = RouteTopology.routeContaining(from: "CWH", to: "PH", dataSource: "AMTRAK")
        XCTAssertNotNil(route, "Amtrak NEC should contain Cornwells Heights (CWH)")
        XCTAssertEqual(route?.id, "amtrak-nec", "CWH→PH on AMTRAK should match the Northeast Corridor")
    }

    func testAmtrakNECIncludesNorthPhiladelphia() {
        let route = RouteTopology.routeContaining(from: "PHN", to: "PH", dataSource: "AMTRAK")
        XCTAssertNotNil(route, "Amtrak NEC should contain North Philadelphia (PHN)")
    }

    func testAmtrakNECIncludesNewRochelle() {
        let route = RouteTopology.routeContaining(from: "NRO", to: "NY", dataSource: "AMTRAK")
        XCTAssertNotNil(route, "Amtrak NEC should contain New Rochelle (NRO)")
        XCTAssertEqual(route?.id, "amtrak-nec", "NRO→NY on AMTRAK should match the Northeast Corridor")
    }

    // MARK: - Amtrak Empire Service includes Hudson Valley stations

    func testAmtrakEmpireServiceIncludesHudsonValley() {
        let hudsonValley = ["YNY", "CRT", "POU", "RHI", "HUD", "SDY"]
        for code in hudsonValley {
            let route = RouteTopology.routeContaining(from: code, to: "ALB", dataSource: "AMTRAK")
            XCTAssertNotNil(route,
                           "Amtrak Empire Service should contain \(code)")
            XCTAssertEqual(route?.id, "amtrak-empire-service",
                          "\(code)→ALB on AMTRAK should match Empire Service")
        }
    }

    func testAmtrakEmpireServiceNYToPoughkeepsie() {
        let route = RouteTopology.routeContaining(from: "NY", to: "POU", dataSource: "AMTRAK")
        XCTAssertNotNil(route, "NY→POU should resolve to Amtrak Empire Service")
        XCTAssertEqual(route?.id, "amtrak-empire-service")
    }

    // MARK: - allStationCodes

    func testAllStationCodesNotEmpty() {
        XCTAssertFalse(RouteTopology.allStationCodes.isEmpty, "Should have station codes across all routes")
        XCTAssertGreaterThan(RouteTopology.allStationCodes.count, 50, "Should have substantial number of station codes")
    }

    // MARK: - expandStationCodes (hub chaining)

    /// Regression test for the NYP→Huntington route alert map.
    /// No single LIRR route contains both NY and LHUN (Port Washington has NY but
    /// not LHUN; Port Jefferson has LHUN starting at JAM). The expander must
    /// bridge through Jamaica so the route alert's congestion-segment filter
    /// matches every adjacent NY-WDD-...-JAM-LMIN-...-CSH-LHUN segment.
    func testExpandStationCodesBridgesNYPToHuntingtonViaJamaica() {
        let expanded = RouteTopology.expandStationCodes(["NY", "LHUN"], dataSource: "LIRR")

        XCTAssertEqual(expanded.first, "NY", "Expansion should preserve the starting station")
        XCTAssertEqual(expanded.last, "LHUN", "Expansion should preserve the ending station")
        XCTAssertTrue(expanded.contains("JAM"), "Expansion must pass through Jamaica hub")
        XCTAssertGreaterThan(
            expanded.count, 2,
            "NY→LHUN crosses two LIRR branches; hub chaining should yield more than the [from, to] fallback"
        )

        // Spot-check a few intermediate stops on each leg so segment filtering will match.
        // Leg 1 (NY → JAM via Belmont/Greenport prefix): WDD, FHL, KGN
        XCTAssertTrue(expanded.contains("WDD"), "Should include Woodside on the NY→JAM leg")
        XCTAssertTrue(expanded.contains("KGN"), "Should include Kew Gardens on the NY→JAM leg")
        // Leg 2 (JAM → LHUN on Port Jefferson Branch): LMIN, LHVL, SYT, CSH
        XCTAssertTrue(expanded.contains("LMIN"), "Should include Mineola on the JAM→LHUN leg")
        XCTAssertTrue(expanded.contains("CSH"), "Should include Cold Spring Harbor on the JAM→LHUN leg")
    }

    func testExpandStationCodesBridgesReverseHuntingtonToNYP() {
        let expanded = RouteTopology.expandStationCodes(["LHUN", "NY"], dataSource: "LIRR")

        XCTAssertEqual(expanded.first, "LHUN", "Reverse expansion should start at LHUN")
        XCTAssertEqual(expanded.last, "NY", "Reverse expansion should end at NY")
        XCTAssertTrue(expanded.contains("JAM"), "Reverse expansion must also pass through Jamaica hub")
        XCTAssertGreaterThan(expanded.count, 2, "Reverse cross-branch pair should also be hub-chained")
    }

    /// Same-branch pairs must keep working without hub chaining (no regression).
    /// JAM→LHUN sits entirely on the Port Jefferson Branch.
    func testExpandStationCodesSameBranchUnchanged() {
        let expanded = RouteTopology.expandStationCodes(["JAM", "LHUN"], dataSource: "LIRR")

        XCTAssertEqual(expanded.first, "JAM")
        XCTAssertEqual(expanded.last, "LHUN")
        // Port Jefferson Branch JAM→LHUN: JAM, LMIN, LHVL, SYT, CSH, LHUN
        XCTAssertEqual(
            expanded, ["JAM", "LMIN", "LHVL", "SYT", "CSH", "LHUN"],
            "Same-branch JAM→LHUN should expand using Port Jefferson Branch only, no hub detour"
        )
    }

    /// Bridging only happens when no single route contains both stations.
    /// NY→PWS is entirely on the Port Washington Branch and must not detour through JAM.
    func testExpandStationCodesPortWashingtonNotRoutedViaJamaica() {
        let expanded = RouteTopology.expandStationCodes(["NY", "PWS"], dataSource: "LIRR")

        XCTAssertEqual(expanded.first, "NY")
        XCTAssertEqual(expanded.last, "PWS")
        XCTAssertFalse(expanded.contains("JAM"), "Port Washington Branch does not pass through Jamaica")
    }

    /// When hub-chained legs share trunk stations beyond the hub (e.g. NY→GCT where
    /// both legs traverse FHL/KGN), the overlap must be collapsed so no station
    /// appears twice. Repeated stations break filterSegmentsForRoute which uses firstIndex.
    func testExpandStationCodesCollapsesTrunkOverlapOnHubChain() {
        let expanded = RouteTopology.expandStationCodes(["NY", "GCT"], dataSource: "LIRR")

        XCTAssertEqual(expanded.first, "NY", "Should start at NY")
        XCTAssertEqual(expanded.last, "GCT", "Should end at GCT")

        let uniqueCount = Set(expanded).count
        XCTAssertEqual(
            uniqueCount, expanded.count,
            "No station should appear twice after overlap collapse, got: \(expanded)"
        )
    }

    /// Systems with no hub configured fall back to [from, to] when no route
    /// contains both stations — same behavior as before this change.
    func testExpandStationCodesNoHubFallsBackToPair() {
        let expanded = RouteTopology.expandStationCodes(["NY", "FAKE_STATION"], dataSource: "NJT")
        XCTAssertEqual(expanded, ["NY", "FAKE_STATION"], "No-hub system with unmatched pair returns inputs unchanged")
    }

    // MARK: - scheduleOnlyRouteIDs

    /// Helper: every route ID for a given data source.
    private func routeIDs(forDataSource dataSource: String) -> Set<String> {
        Set(RouteTopology.allRoutes.filter { $0.dataSource == dataSource }.map(\.id))
    }

    func testScheduleOnlyRouteIDs_containsSeptaMetroBroadStAndMarketFrankford() {
        // These four SEPTA Metro lines are served schedule-only (no real-time feed), matching
        // the backend's classification. They must be the ones that always draw a white base line.
        for id in ["SEPTA-B1", "SEPTA-B2", "SEPTA-B3", "SEPTA-L1"] {
            XCTAssertTrue(RouteTopology.scheduleOnlyRouteIDs.contains(id),
                          "\(id) is schedule-only and must be in scheduleOnlyRouteIDs")
        }
    }

    func testScheduleOnlyRouteIDs_excludesSeptaMetroRealtimeLines() {
        // NHSL (M1), Girard trolley (G1), Media/Sharon Hill trolleys (D1/D2), and city
        // trolleys (T1) are real-time — they must NOT be forced as always-on base lines.
        for id in ["SEPTA-M1", "SEPTA-G1", "SEPTA-D1", "SEPTA-D2", "SEPTA-T1"] {
            XCTAssertFalse(RouteTopology.scheduleOnlyRouteIDs.contains(id),
                           "\(id) is real-time and must not be in scheduleOnlyRouteIDs")
        }
    }

    func testScheduleOnlyRouteIDs_containsAllPATCORoutes() {
        // PATCO is fully schedule-only, so every one of its routes qualifies.
        let patcoIDs = routeIDs(forDataSource: "PATCO")
        XCTAssertFalse(patcoIDs.isEmpty, "Expected PATCO to have route definitions")
        XCTAssertTrue(patcoIDs.isSubset(of: RouteTopology.scheduleOnlyRouteIDs),
                      "All PATCO routes must be schedule-only: missing \(patcoIDs.subtracting(RouteTopology.scheduleOnlyRouteIDs))")
    }

    func testScheduleOnlyRouteIDs_excludesRealtimeSystems() {
        // No fully real-time system's routes should be flagged schedule-only.
        for dataSource in ["NJT", "AMTRAK", "LIRR", "SUBWAY", "SEPTA_RR"] {
            let ids = routeIDs(forDataSource: dataSource)
            XCTAssertTrue(ids.isDisjoint(with: RouteTopology.scheduleOnlyRouteIDs),
                          "\(dataSource) routes must not be schedule-only: leaked \(ids.intersection(RouteTopology.scheduleOnlyRouteIDs))")
        }
    }

    // MARK: - congestionMapBaseRoutes

    /// Regression for the Market-Frankford bug AND Codex's follow-up: with the Routes layer
    /// off, SEPTA Metro must draw exactly its schedule-only lines (Broad St + Market-Frankford)
    /// — not its real-time NHSL/trolley lines, which stay under the user's Routes toggle.
    func testCongestionMapBaseRoutes_septaMetro_routesOff_onlyScheduleOnlyLines() {
        let routes = RouteTopology.congestionMapBaseRoutes(selectedDataSources: ["SEPTA_METRO"], showRoutes: false)
        let ids = Set(routes.map(\.id))
        XCTAssertEqual(ids, ["SEPTA-B1", "SEPTA-B2", "SEPTA-B3", "SEPTA-L1"],
                       "SEPTA Metro with Routes off must draw only its schedule-only lines, got \(ids.sorted())")
    }

    func testCongestionMapBaseRoutes_septaMetro_routesOn_allLines() {
        let routes = RouteTopology.congestionMapBaseRoutes(selectedDataSources: ["SEPTA_METRO"], showRoutes: true)
        let ids = Set(routes.map(\.id))
        XCTAssertEqual(ids, routeIDs(forDataSource: "SEPTA_METRO"),
                       "SEPTA Metro with Routes on must draw the full topology, including NHSL/trolleys")
        XCTAssertTrue(ids.contains("SEPTA-M1"), "NHSL should appear when Routes is on")
    }

    func testCongestionMapBaseRoutes_patco_routesOff_allRoutes() {
        // PATCO is fully schedule-only, so all its routes draw even with Routes off.
        let routes = RouteTopology.congestionMapBaseRoutes(selectedDataSources: ["PATCO"], showRoutes: false)
        let ids = Set(routes.map(\.id))
        XCTAssertEqual(ids, routeIDs(forDataSource: "PATCO"),
                       "PATCO with Routes off must draw its whole (schedule-only) network")
    }

    func testCongestionMapBaseRoutes_patco_routesToggleHasNoEffect() {
        let off = RouteTopology.congestionMapBaseRoutes(selectedDataSources: ["PATCO"], showRoutes: false)
        let on = RouteTopology.congestionMapBaseRoutes(selectedDataSources: ["PATCO"], showRoutes: true)
        XCTAssertEqual(Set(off.map(\.id)), Set(on.map(\.id)),
                       "PATCO renders the same regardless of the Routes toggle (fully schedule-only)")
    }

    func testCongestionMapBaseRoutes_realtimeSystem_routesOff_empty() {
        // A fully real-time system contributes nothing to the base layer when Routes is off —
        // its lines are shown only as colored congestion segments.
        let routes = RouteTopology.congestionMapBaseRoutes(selectedDataSources: ["NJT"], showRoutes: false)
        XCTAssertTrue(routes.isEmpty,
                      "NJT with Routes off must not draw any base topology, got \(routes.map(\.id))")
    }

    func testCongestionMapBaseRoutes_realtimeSystem_routesOn_allRoutes() {
        let routes = RouteTopology.congestionMapBaseRoutes(selectedDataSources: ["NJT"], showRoutes: true)
        let ids = Set(routes.map(\.id))
        XCTAssertEqual(ids, routeIDs(forDataSource: "NJT"),
                       "NJT with Routes on must draw its full topology")
    }

    func testCongestionMapBaseRoutes_unselectedSystemsDoNotLeak() {
        // Selecting only NJT must not pull in PATCO or SEPTA Metro schedule-only lines.
        let routes = RouteTopology.congestionMapBaseRoutes(selectedDataSources: ["NJT"], showRoutes: false)
        let sources = Set(routes.map(\.dataSource))
        XCTAssertFalse(sources.contains("PATCO"), "Unselected PATCO must not leak into the base layer")
        XCTAssertFalse(sources.contains("SEPTA_METRO"), "Unselected SEPTA Metro must not leak into the base layer")
    }

    func testCongestionMapBaseRoutes_emptySelection_empty() {
        XCTAssertTrue(RouteTopology.congestionMapBaseRoutes(selectedDataSources: [], showRoutes: false).isEmpty)
        XCTAssertTrue(RouteTopology.congestionMapBaseRoutes(selectedDataSources: [], showRoutes: true).isEmpty)
    }

    func testCongestionMapBaseRoutes_mixedSelection_routesOff() {
        // PATCO (all routes) + SEPTA Metro (schedule-only lines only) render; NJT does not.
        let routes = RouteTopology.congestionMapBaseRoutes(
            selectedDataSources: ["PATCO", "SEPTA_METRO", "NJT"],
            showRoutes: false
        )
        let ids = Set(routes.map(\.id))
        var expected = routeIDs(forDataSource: "PATCO")
        expected.formUnion(["SEPTA-B1", "SEPTA-B2", "SEPTA-B3", "SEPTA-L1"])
        XCTAssertEqual(ids, expected,
                       "Routes-off base layer must be all PATCO + SEPTA schedule-only lines, no NJT")
        XCTAssertTrue(Set(routes.map(\.dataSource)).isDisjoint(with: ["NJT"]),
                      "NJT (real-time) must contribute nothing with Routes off")
    }
}
