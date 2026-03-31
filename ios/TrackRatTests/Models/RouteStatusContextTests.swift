import XCTest
@testable import TrackRat

class RouteStatusContextTests: XCTestCase {

    // MARK: - Subway: RouteTopology format ("subway-m")

    func testGtfsRouteIds_subwayTopologyFormat_singleLetter() {
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: "subway-m", fromStationCode: nil, toStationCode: nil)
        XCTAssertEqual(context.gtfsRouteIds, ["M"], "subway-m should resolve to GTFS route ID 'M'")
    }

    func testGtfsRouteIds_subwayTopologyFormat_number() {
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: "subway-1", fromStationCode: nil, toStationCode: nil)
        XCTAssertEqual(context.gtfsRouteIds, ["1"], "subway-1 should resolve to GTFS route ID '1'")
    }

    func testGtfsRouteIds_subwayTopologyFormat_express() {
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: "subway-6x", fromStationCode: nil, toStationCode: nil)
        XCTAssertEqual(context.gtfsRouteIds, ["6X"], "subway-6x should resolve to GTFS route ID '6X'")
    }

    func testGtfsRouteIds_subwayTopologyFormat_withSuffix() {
        // "subway-a-rockaway" should extract just "A" (before the first dash in the suffix)
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: "subway-a-rockaway", fromStationCode: nil, toStationCode: nil)
        XCTAssertEqual(context.gtfsRouteIds, ["A"], "subway-a-rockaway should resolve to GTFS route ID 'A'")
    }

    // MARK: - Subway: Raw backend line.code format ("M", "L", "1")

    func testGtfsRouteIds_subwayRawCode_singleLetter() {
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: "M", fromStationCode: nil, toStationCode: nil)
        XCTAssertEqual(context.gtfsRouteIds, ["M"], "Raw line code 'M' should resolve to GTFS route ID 'M'")
    }

    func testGtfsRouteIds_subwayRawCode_number() {
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: "1", fromStationCode: nil, toStationCode: nil)
        XCTAssertEqual(context.gtfsRouteIds, ["1"], "Raw line code '1' should resolve to GTFS route ID '1'")
    }

    func testGtfsRouteIds_subwayRawCode_express() {
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: "6X", fromStationCode: nil, toStationCode: nil)
        XCTAssertEqual(context.gtfsRouteIds, ["6X"], "Raw line code '6X' should resolve to GTFS route ID '6X'")
    }

    func testGtfsRouteIds_subwayRawCode_lowercaseNormalized() {
        // Backend might send lowercase; should still match
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: "m", fromStationCode: nil, toStationCode: nil)
        XCTAssertEqual(context.gtfsRouteIds, ["M"], "Raw line code 'm' should be uppercased to 'M'")
    }

    func testGtfsRouteIds_subwayRawCode_shuttle() {
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: "GS", fromStationCode: nil, toStationCode: nil)
        XCTAssertEqual(context.gtfsRouteIds, ["GS"], "Raw line code 'GS' (42 St Shuttle) should resolve correctly")
    }

    // MARK: - Subway: Station pair fallback (lineId nil)

    func testGtfsRouteIds_subwayNilLineId_infersFromStationPair() {
        // SM01 (Middle Village-Metropolitan Av) is on the M line in RouteTopology
        // SM14 is also on the M line
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: nil, fromStationCode: "SM01", toStationCode: "SM14")
        let ids = context.gtfsRouteIds
        XCTAssertFalse(ids.isEmpty, "Should infer GTFS route IDs from station pair via RouteTopology")
        XCTAssertTrue(ids.contains("M"), "SM01 to SM14 are on the M line, should resolve to 'M'")
    }

    func testGtfsRouteIds_subwayNilLineId_crossPlatformTransfer() {
        // "Metropolitan Av" = SG29 (G line stop), "14 St-Union Sq" = S635 (4/5/6 stop)
        // Neither SG29 nor S635 is on the L line directly, but their equivalents are:
        // SG29 ↔ SL10 (L line Metropolitan Av), S635 ↔ SL03 (L line 14 St-Union Sq)
        // The fallback should expand via station equivalents and find the L line.
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: nil, fromStationCode: "SG29", toStationCode: "S635")
        let ids = context.gtfsRouteIds
        XCTAssertFalse(ids.isEmpty, "Should infer line from station equivalents when primary codes don't match a single route")
        XCTAssertTrue(ids.contains("L"), "Metropolitan Av (SG29→SL10) to 14 St-Union Sq (S635→SL03) should resolve to the L line")
    }

    func testGtfsRouteIds_subwayNilLineId_unknownStations_returnsEmpty() {
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: nil, fromStationCode: "FAKE1", toStationCode: "FAKE2")
        XCTAssertTrue(context.gtfsRouteIds.isEmpty, "Unknown stations should return empty set, not all alerts")
    }

    // MARK: - Subway: Multi-line station pair returns all lines

    func testGtfsRouteIds_subwayNilLineId_multiLineSharedTrunk() {
        // S137 and S136 are on the shared 1/2/3 trunk (7th Avenue).
        // With no lineId, gtfsRouteIds should return all lines serving this segment.
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: nil, fromStationCode: "S137", toStationCode: "S136")
        let ids = context.gtfsRouteIds
        XCTAssertTrue(ids.contains("1"), "S137→S136 shared trunk should include the 1 train")
        XCTAssertTrue(ids.contains("2"), "S137→S136 shared trunk should include the 2 train")
        XCTAssertGreaterThanOrEqual(ids.count, 2, "Should return at least 2 GTFS route IDs for multi-line stations")
    }

    func testGtfsRouteIds_subwayNilLineId_8thAveTrunk() {
        // SA24 and SA22 are on the shared A/B/C trunk (8th Avenue).
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: nil, fromStationCode: "SA24", toStationCode: "SA22")
        let ids = context.gtfsRouteIds
        XCTAssertTrue(ids.contains("A"), "SA24→SA22 shared trunk should include the A train")
        XCTAssertTrue(ids.contains("C"), "SA24→SA22 shared trunk should include the C train")
        XCTAssertGreaterThanOrEqual(ids.count, 2, "Should return at least 2 GTFS route IDs for A/C trunk")
    }

    // MARK: - LIRR: RouteTopology format

    func testGtfsRouteIds_lirrTopologyFormat() {
        let context = RouteStatusContext(dataSource: "LIRR", lineId: "lirr-babylon", fromStationCode: nil, toStationCode: nil)
        XCTAssertEqual(context.gtfsRouteIds, ["1"], "lirr-babylon should resolve to GTFS route ID '1'")
    }

    func testGtfsRouteIds_lirrTopologyFormat_portWashington() {
        let context = RouteStatusContext(dataSource: "LIRR", lineId: "lirr-port-washington", fromStationCode: nil, toStationCode: nil)
        XCTAssertEqual(context.gtfsRouteIds, ["9"], "lirr-port-washington should resolve to GTFS route ID '9'")
    }

    // MARK: - LIRR: Raw backend line.code format ("LIRR-BB")

    func testGtfsRouteIds_lirrRawCode() {
        let context = RouteStatusContext(dataSource: "LIRR", lineId: "LIRR-BB", fromStationCode: nil, toStationCode: nil)
        XCTAssertEqual(context.gtfsRouteIds, ["1"], "LIRR-BB should resolve to GTFS route ID '1'")
    }

    func testGtfsRouteIds_lirrRawCode_portWashington() {
        let context = RouteStatusContext(dataSource: "LIRR", lineId: "LIRR-PW", fromStationCode: nil, toStationCode: nil)
        XCTAssertEqual(context.gtfsRouteIds, ["9"], "LIRR-PW should resolve to GTFS route ID '9'")
    }

    // MARK: - MNR: RouteTopology format

    func testGtfsRouteIds_mnrTopologyFormat() {
        let context = RouteStatusContext(dataSource: "MNR", lineId: "mnr-hudson", fromStationCode: nil, toStationCode: nil)
        XCTAssertEqual(context.gtfsRouteIds, ["1"], "mnr-hudson should resolve to GTFS route ID '1'")
    }

    func testGtfsRouteIds_mnrTopologyFormat_newHaven() {
        let context = RouteStatusContext(dataSource: "MNR", lineId: "mnr-new-haven", fromStationCode: nil, toStationCode: nil)
        XCTAssertEqual(context.gtfsRouteIds, ["3"], "mnr-new-haven should resolve to GTFS route ID '3'")
    }

    // MARK: - MNR: Raw backend line.code format ("MNR-HUD")

    func testGtfsRouteIds_mnrRawCode() {
        let context = RouteStatusContext(dataSource: "MNR", lineId: "MNR-HUD", fromStationCode: nil, toStationCode: nil)
        XCTAssertEqual(context.gtfsRouteIds, ["1"], "MNR-HUD should resolve to GTFS route ID '1'")
    }

    func testGtfsRouteIds_mnrRawCode_newHaven() {
        let context = RouteStatusContext(dataSource: "MNR", lineId: "MNR-NH", fromStationCode: nil, toStationCode: nil)
        XCTAssertEqual(context.gtfsRouteIds, ["3"], "MNR-NH should resolve to GTFS route ID '3'")
    }

    // MARK: - Non-MTA data sources

    func testGtfsRouteIds_njtReturnsEmpty() {
        let context = RouteStatusContext(dataSource: "NJT", lineId: "njt-nec", fromStationCode: nil, toStationCode: nil)
        XCTAssertTrue(context.gtfsRouteIds.isEmpty, "NJT should return empty set (no MTA service alerts)")
    }

    func testGtfsRouteIds_pathReturnsEmpty() {
        let context = RouteStatusContext(dataSource: "PATH", lineId: "path-jsq-33", fromStationCode: nil, toStationCode: nil)
        XCTAssertTrue(context.gtfsRouteIds.isEmpty, "PATH should return empty set (no MTA service alerts)")
    }

    // MARK: - Edge cases

    func testGtfsRouteIds_nilLineIdNilStations_returnsEmpty() {
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: nil, fromStationCode: nil, toStationCode: nil)
        XCTAssertTrue(context.gtfsRouteIds.isEmpty, "Nil lineId and nil stations should return empty set")
    }

    func testGtfsRouteIds_unknownLineId_subway_stillReturnsIt() {
        // An unknown subway code should still be returned uppercased (it might be a new line/shuttle)
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: "ZZ", fromStationCode: nil, toStationCode: nil)
        XCTAssertEqual(context.gtfsRouteIds, ["ZZ"], "Unknown subway code should still be passed through uppercased")
    }

    func testGtfsRouteIds_unknownLineId_lirr_returnsEmpty() {
        let context = RouteStatusContext(dataSource: "LIRR", lineId: "unknown-branch", fromStationCode: nil, toStationCode: nil)
        XCTAssertTrue(context.gtfsRouteIds.isEmpty, "Unknown LIRR line should return empty set")
    }

    // MARK: - stationCodes: cross-platform transfers

    func testStationCodes_crossPlatformTransfer_resolvesViaEquivalents() {
        // SG29 (G platform) → S635 (4/5/6 platform) should expand via equivalents
        // to find L line intermediate stations (SL10→SL03)
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: nil, fromStationCode: "SG29", toStationCode: "S635")
        let codes = context.stationCodes
        XCTAssertGreaterThan(codes.count, 2, "Should expand cross-platform route via equivalents, got only \(codes.count) stations: \(codes)")
        // Should contain L line stations between Metropolitan Av and 14 St-Union Sq
        XCTAssertTrue(codes.contains("SL10") || codes.contains("SL03"),
                       "Expanded codes should include L line station codes, got: \(codes)")
    }

    func testStationCodes_sameLine_expandsDirectly() {
        // SM01 and SM14 are both on the M line, should expand directly without needing equivalents
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: nil, fromStationCode: "SM01", toStationCode: "SM14")
        let codes = context.stationCodes
        XCTAssertGreaterThan(codes.count, 2, "Same-line stations should expand to intermediate stations")
    }

    func testStationCodes_withLineId_returnsFullRoute() {
        // When lineId matches a RouteTopology route, return all station codes for that route
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: "subway-l", fromStationCode: nil, toStationCode: nil)
        let codes = context.stationCodes
        XCTAssertGreaterThan(codes.count, 10, "L line should have many stations")
        XCTAssertTrue(codes.contains("SL10"), "L line should contain Metropolitan Av (SL10)")
        XCTAssertTrue(codes.contains("SL03"), "L line should contain 14 St-Union Sq (SL03)")
    }

    func testStationCodes_unknownStations_returnsRawPair() {
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: nil, fromStationCode: "FAKE1", toStationCode: "FAKE2")
        let codes = context.stationCodes
        XCTAssertEqual(codes, ["FAKE1", "FAKE2"], "Unknown stations should return raw pair as fallback")
    }

    // MARK: - resolveGtfsRouteIds consistency

    func testGtfsRouteIds_allLirrBranches_topologyAndCodeAgree() {
        // Verify every LIRR branch produces the same GTFS ID from both formats
        let pairs: [(String, String, String)] = [
            ("lirr-babylon", "LIRR-BB", "1"),
            ("lirr-hempstead", "LIRR-HB", "2"),
            ("lirr-oyster-bay", "LIRR-OB", "3"),
            ("lirr-ronkonkoma", "LIRR-RK", "4"),
            ("lirr-montauk", "LIRR-MK", "5"),
            ("lirr-long-beach", "LIRR-LB", "6"),
            ("lirr-far-rockaway", "LIRR-FR", "7"),
            ("lirr-west-hempstead", "LIRR-WH", "8"),
            ("lirr-port-washington", "LIRR-PW", "9"),
            ("lirr-port-jefferson", "LIRR-PJ", "10"),
            ("lirr-belmont-park", "LIRR-BP", "11"),
            ("lirr-greenport", "LIRR-GP", "13"),
        ]
        for (topologyId, backendCode, expectedGtfs) in pairs {
            let fromTopology = RouteStatusContext(dataSource: "LIRR", lineId: topologyId, fromStationCode: nil, toStationCode: nil).gtfsRouteIds
            let fromBackend = RouteStatusContext(dataSource: "LIRR", lineId: backendCode, fromStationCode: nil, toStationCode: nil).gtfsRouteIds
            XCTAssertEqual(fromTopology, [expectedGtfs], "LIRR topology '\(topologyId)' should resolve to '\(expectedGtfs)'")
            XCTAssertEqual(fromBackend, [expectedGtfs], "LIRR backend '\(backendCode)' should resolve to '\(expectedGtfs)'")
        }
    }

    func testGtfsRouteIds_allMnrBranches_topologyAndCodeAgree() {
        let pairs: [(String, String, String)] = [
            ("mnr-hudson", "MNR-HUD", "1"),
            ("mnr-harlem", "MNR-HAR", "2"),
            ("mnr-new-haven", "MNR-NH", "3"),
            ("mnr-new-canaan", "MNR-NC", "4"),
            ("mnr-danbury", "MNR-DAN", "5"),
            ("mnr-waterbury", "MNR-WAT", "6"),
        ]
        for (topologyId, backendCode, expectedGtfs) in pairs {
            let fromTopology = RouteStatusContext(dataSource: "MNR", lineId: topologyId, fromStationCode: nil, toStationCode: nil).gtfsRouteIds
            let fromBackend = RouteStatusContext(dataSource: "MNR", lineId: backendCode, fromStationCode: nil, toStationCode: nil).gtfsRouteIds
            XCTAssertEqual(fromTopology, [expectedGtfs], "MNR topology '\(topologyId)' should resolve to '\(expectedGtfs)'")
            XCTAssertEqual(fromBackend, [expectedGtfs], "MNR backend '\(backendCode)' should resolve to '\(expectedGtfs)'")
        }
    }
}
