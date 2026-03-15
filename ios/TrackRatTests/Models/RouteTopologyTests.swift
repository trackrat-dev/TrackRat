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

    func testRouteContainingFallsBackToPartialMatch() {
        // Test that a station on only one end still returns a route (last resort)
        let route = RouteTopology.routeContaining(from: "NY", to: "NONEXISTENT", dataSource: "NJT")
        XCTAssertNotNil(route, "Should fall back to route containing at least one station")
        guard let route = route else { return }
        XCTAssertEqual(route.dataSource, "NJT")
        XCTAssertTrue(route.stationCodes.contains("NY"), "Fallback route should contain the known station")
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

    // MARK: - allStationCodes

    func testAllStationCodesNotEmpty() {
        XCTAssertFalse(RouteTopology.allStationCodes.isEmpty, "Should have station codes across all routes")
        XCTAssertGreaterThan(RouteTopology.allStationCodes.count, 50, "Should have substantial number of station codes")
    }
}
