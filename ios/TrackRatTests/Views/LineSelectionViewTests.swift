import XCTest
@testable import TrackRat

class LineSelectionViewTests: XCTestCase {

    // MARK: - hasContent

    func testHasContent_noSystems_returnsFalse() {
        var enabledLineIds: Set<String> = []
        let view = LineSelectionView(systems: [], enabledLineIds: .constant(enabledLineIds))
        XCTAssertFalse(view.hasContent, "Empty systems should not show line selection")
    }

    func testHasContent_singleSystemSingleLine_returnsFalse() {
        let systems = [
            RouteSystemInfo(system: .njt, lines: [
                RouteLineInfo(dataSource: "NJT", lineCode: "NEC", lineName: "Northeast Corridor", lineColor: "#FF0000")
            ])
        ]
        let view = LineSelectionView(systems: systems, enabledLineIds: .constant([]))
        XCTAssertFalse(view.hasContent, "Single system with one line should not show line selection")
    }

    func testHasContent_singleSystemMultipleLines_returnsTrue() {
        let systems = [
            RouteSystemInfo(system: .subway, lines: [
                RouteLineInfo(dataSource: "SUBWAY", lineCode: "A", lineName: "A", lineColor: "#0039A6"),
                RouteLineInfo(dataSource: "SUBWAY", lineCode: "C", lineName: "C", lineColor: "#0039A6"),
            ])
        ]
        let view = LineSelectionView(systems: systems, enabledLineIds: .constant([]))
        XCTAssertTrue(view.hasContent, "Single system with multiple lines should show line selection")
    }

    func testHasContent_multipleSystems_returnsTrue() {
        let systems = [
            RouteSystemInfo(system: .njt, lines: [
                RouteLineInfo(dataSource: "NJT", lineCode: "NEC", lineName: "Northeast Corridor", lineColor: "#FF0000")
            ]),
            RouteSystemInfo(system: .amtrak, lines: [
                RouteLineInfo(dataSource: "AMTRAK", lineCode: "NEC", lineName: "Northeast Corridor", lineColor: "#004990")
            ])
        ]
        let view = LineSelectionView(systems: systems, enabledLineIds: .constant([]))
        XCTAssertTrue(view.hasContent, "Multiple systems should show line selection")
    }

    func testHasContent_singleSystemNoLines_returnsFalse() {
        let systems = [
            RouteSystemInfo(system: .njt, lines: [])
        ]
        let view = LineSelectionView(systems: systems, enabledLineIds: .constant([]))
        XCTAssertFalse(view.hasContent, "Single system with no discovered lines should not show line selection")
    }

    // MARK: - enabledGtfsRouteIds (ViewModel)

    func testEnabledGtfsRouteIds_emptyMeansNoFilter() {
        // When enabledLineIds is empty, all lines are enabled — no filtering
        let vm = RouteStatusViewModel(context: RouteStatusContext(
            dataSource: "SUBWAY", lineId: nil, fromStationCode: "SA24", toStationCode: "SA22"
        ))
        vm.enabledLineIds = []
        XCTAssertTrue(vm.enabledGtfsRouteIds.isEmpty,
                     "Empty enabledLineIds should return empty GTFS IDs (no filtering)")
    }

    func testEnabledGtfsRouteIds_subwayLineCodesAreGtfsIds() {
        let vm = RouteStatusViewModel(context: RouteStatusContext(
            dataSource: "SUBWAY", lineId: nil, fromStationCode: "SA24", toStationCode: "SA22"
        ))
        vm.enabledLineIds = ["SUBWAY:A", "SUBWAY:C"]
        let gtfsIds = vm.enabledGtfsRouteIds
        XCTAssertEqual(gtfsIds, ["A", "C"],
                      "Subway line codes should map directly to GTFS route IDs, got: \(gtfsIds)")
    }

    func testEnabledGtfsRouteIds_lirrBranchMapping() {
        let vm = RouteStatusViewModel(context: RouteStatusContext(
            dataSource: "LIRR", lineId: nil, fromStationCode: "JM", toStationCode: "GCT"
        ))
        vm.enabledLineIds = ["LIRR:LIRR-BB", "LIRR:LIRR-PW"]
        let gtfsIds = vm.enabledGtfsRouteIds
        XCTAssertEqual(gtfsIds, ["1", "9"],
                      "LIRR line codes should map to GTFS route IDs, got: \(gtfsIds)")
    }

    func testEnabledGtfsRouteIds_mnrBranchMapping() {
        let vm = RouteStatusViewModel(context: RouteStatusContext(
            dataSource: "MNR", lineId: nil, fromStationCode: "GCT", toStationCode: "MNR-SSN"
        ))
        vm.enabledLineIds = ["MNR:MNR-NH"]
        let gtfsIds = vm.enabledGtfsRouteIds
        XCTAssertEqual(gtfsIds, ["3"],
                      "MNR line codes should map to GTFS route IDs, got: \(gtfsIds)")
    }

    func testEnabledGtfsRouteIds_mixedSystemsIgnoresUnmapped() {
        let vm = RouteStatusViewModel(context: RouteStatusContext(
            dataSource: "NJT", lineId: nil, fromStationCode: "NY", toStationCode: "TR"
        ))
        // NJT lines don't have GTFS mapping (only MTA systems do)
        vm.enabledLineIds = ["NJT:NEC"]
        let gtfsIds = vm.enabledGtfsRouteIds
        XCTAssertTrue(gtfsIds.isEmpty,
                     "NJT lines should not produce GTFS IDs (no service alert mapping), got: \(gtfsIds)")
    }
}
