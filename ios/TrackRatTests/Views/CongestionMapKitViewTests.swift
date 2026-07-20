import XCTest
import CoreLocation
@testable import TrackRat

/// Tests for the route-topology base layer of `CongestionMapKitView` (#1561).
///
/// The route-status map only receives live congestion segments, so a
/// low-frequency route like the Amtrak Keystone showed gaps (e.g. Paoli→
/// Philadelphia 30th St) whenever no train completed a segment inside the
/// congestion window. `baseRoutePolylineCoordinates` builds the static
/// topology path that is drawn beneath the live segments to close those gaps.
final class CongestionMapKitViewTests: XCTestCase {

    // MARK: - Reported gap: Keystone Paoli → Philadelphia 30th St

    func testKeystonePaoliToPhiladelphiaUsesShapeData() {
        let runs = CongestionMapKitView.baseRoutePolylineCoordinates(stationCodes: ["PH", "PAO"])

        XCTAssertEqual(runs.count, 1, "PH→PAO is one adjacent pair and must produce exactly one polyline, got \(runs.count)")
        guard let run = runs.first else { return }
        XCTAssertGreaterThan(
            run.count, 2,
            "PAO-PH has GTFS shape data in RouteShapes, so the polyline should follow the track (\(run.count) points), not a 2-point straight line"
        )
    }

    // MARK: - Full Keystone line has no gaps

    func testFullKeystoneRouteDrawsEveryAdjacentPair() {
        guard let keystone = RouteTopology.allRoutes.first(where: { $0.id == "amtrak-keystone" }) else {
            XCTFail("amtrak-keystone route missing from RouteTopology")
            return
        }

        let runs = CongestionMapKitView.baseRoutePolylineCoordinates(stationCodes: keystone.stationCodes)

        XCTAssertEqual(
            runs.count, keystone.stationCodes.count - 1,
            "Every adjacent Keystone pair must produce a polyline (stations: \(keystone.stationCodes)), otherwise the base layer has gaps like the reported PAO→PH one"
        )
        for (index, run) in runs.enumerated() {
            XCTAssertGreaterThanOrEqual(
                run.count, 2,
                "Polyline \(index) (\(keystone.stationCodes[index])→\(keystone.stationCodes[index + 1])) needs at least 2 coordinates to draw, got \(run.count)"
            )
        }
    }

    // MARK: - Straight-line fallback

    func testStraightLineFallbackForPairWithoutShapeData() {
        // NY→HAR are not topology-adjacent, so no GTFS shape exists for the pair.
        // If this precondition ever breaks, RouteShapes gained a NY-HAR entry and
        // the pair below needs replacing with another shapeless one.
        XCTAssertNil(
            RouteShapes.coordinates(from: "NY", to: "HAR"),
            "Test precondition: NY-HAR must have no shape data so the fallback path is exercised"
        )

        let runs = CongestionMapKitView.baseRoutePolylineCoordinates(stationCodes: ["NY", "HAR"])

        XCTAssertEqual(runs.count, 1, "A pair of known stations must still produce a polyline without shape data")
        guard let run = runs.first,
              let nyCoords = Stations.getCoordinates(for: "NY"),
              let harCoords = Stations.getCoordinates(for: "HAR") else {
            XCTFail("NY and HAR must both have station coordinates")
            return
        }
        XCTAssertEqual(run.count, 2, "Without shape data the fallback is a straight from→to line, got \(run.count) points")
        XCTAssertEqual(run[0].latitude, nyCoords.latitude, accuracy: 0.0001, "Straight line must start at the from-station")
        XCTAssertEqual(run[0].longitude, nyCoords.longitude, accuracy: 0.0001, "Straight line must start at the from-station")
        XCTAssertEqual(run[1].latitude, harCoords.latitude, accuracy: 0.0001, "Straight line must end at the to-station")
        XCTAssertEqual(run[1].longitude, harCoords.longitude, accuracy: 0.0001, "Straight line must end at the to-station")
    }

    // MARK: - Unknown codes and degenerate input

    func testUnknownStationCodesAreSkipped() {
        let runs = CongestionMapKitView.baseRoutePolylineCoordinates(stationCodes: ["PH", "NOT_A_STATION", "PAO"])
        XCTAssertTrue(
            runs.isEmpty,
            "Both pairs touch an unknown station code, so no polylines should be produced, got \(runs.count)"
        )
    }

    func testEmptyAndSingleStationPathsProduceNoPolylines() {
        XCTAssertTrue(
            CongestionMapKitView.baseRoutePolylineCoordinates(stationCodes: []).isEmpty,
            "An empty path has no pairs to draw"
        )
        XCTAssertTrue(
            CongestionMapKitView.baseRoutePolylineCoordinates(stationCodes: ["PH"]).isEmpty,
            "A single station has no pairs to draw"
        )
    }
}
