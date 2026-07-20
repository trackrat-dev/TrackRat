import XCTest
@testable import TrackRat

/// Tests for `RouteStatusViewModel.baseRoutePath` — the topology path drawn as
/// the map's base layer must follow the *active* system filter, not the
/// context the screen was opened from (PR #1582 review). NP→NY is the
/// canonical divergent pair: NJT runs via Secaucus (SE), Amtrak runs direct.
@MainActor
final class RouteStatusViewModelTests: XCTestCase {

    private func makeViewModel(dataSource: String) -> RouteStatusViewModel {
        RouteStatusViewModel(context: RouteStatusContext(
            dataSource: dataSource,
            fromStationCode: "NP",
            toStationCode: "NY"
        ))
    }

    func testBasePathUsesContextTopologyWhenItsSystemIsEnabled() {
        let viewModel = makeViewModel(dataSource: "NJT")
        let path = viewModel.baseRoutePath(for: ["NJT", "AMTRAK"])
        XCTAssertEqual(
            path, ["NP", "SE", "NY"],
            "With NJT still enabled the base layer keeps the context's own topology (via Secaucus), got \(path)"
        )
    }

    func testBasePathFollowsFilterWhenContextSystemIsExcluded() {
        let viewModel = makeViewModel(dataSource: "NJT")
        let path = viewModel.baseRoutePath(for: ["AMTRAK"])
        XCTAssertEqual(
            path, ["NP", "NY"],
            "Filtered to Amtrak only, the base layer must use Amtrak's direct NP→NY topology, not NJT's Secaucus routing, got \(path)"
        )
    }

    func testBasePathReversedContextFollowsFilterToo() {
        let viewModel = makeViewModel(dataSource: "AMTRAK")
        let path = viewModel.baseRoutePath(for: ["NJT"])
        XCTAssertEqual(
            path, ["NP", "SE", "NY"],
            "An Amtrak context filtered to NJT only must switch the base layer to NJT's topology via Secaucus, got \(path)"
        )
    }

    func testBasePathEmptyWhenContextHasNoStations() {
        let viewModel = RouteStatusViewModel(context: RouteStatusContext(dataSource: "NJT"))
        XCTAssertTrue(
            viewModel.baseRoutePath(for: ["AMTRAK"]).isEmpty,
            "A context with no stations and no line cannot produce a base path for another system"
        )
    }
}
