import CoreLocation
import XCTest
@testable import TrackRat

/// Tests for the location-driven setup shortcuts: picking the rider's system and
/// surfacing the stations nearest to them instead of making them search.
///
/// These exercise the pure ranking helpers against the real station data, which
/// is what the onboarding screen and the station picker actually call.
final class LocationServiceTests: XCTestCase {

    // Real coordinates from Stations.stationCoordinates, so a station's own
    // location scores a distance of zero and must rank first.
    private let newYorkPenn = CLLocationCoordinate2D(latitude: 40.750046, longitude: -73.992358)
    private let trenton = CLLocationCoordinate2D(latitude: 40.218515, longitude: -74.753926)
    private let ronkonkoma = CLLocationCoordinate2D(latitude: 40.80808613, longitude: -73.10594023)
    private let bostonSouth = CLLocationCoordinate2D(latitude: 42.3520, longitude: -71.0552)
    private let sanFrancisco = CLLocationCoordinate2D(latitude: 37.7749, longitude: -122.4194)
    /// Mid-Atlantic — thousands of kilometres from any station TrackRat knows.
    private let openOcean = CLLocationCoordinate2D(latitude: 35.0, longitude: -40.0)

    // MARK: - LocationFix

    func testLocationFixExposesItsCoordinate() {
        let fix = LocationFix(latitude: 40.75, longitude: -73.99)

        XCTAssertEqual(fix.coordinate.latitude, 40.75, accuracy: 0.0001)
        XCTAssertEqual(fix.coordinate.longitude, -73.99, accuracy: 0.0001)
    }

    func testLocationFixEquatabilitySoViewsCanObserveChanges() {
        // SwiftUI's onChange needs this — it is why the fix isn't a raw
        // CLLocationCoordinate2D, which has no Equatable conformance.
        XCTAssertEqual(
            LocationFix(latitude: 40.75, longitude: -73.99),
            LocationFix(latitude: 40.75, longitude: -73.99)
        )
        XCTAssertNotEqual(
            LocationFix(latitude: 40.75, longitude: -73.99),
            LocationFix(latitude: 40.76, longitude: -73.99)
        )
    }

    // MARK: - Nearest Stations

    func testNearestCodesRanksTheStationYouAreStandingInFirst() {
        let nearest = Stations.nearestCodes(to: trenton, systems: [.njt], limit: 3)

        XCTAssertEqual(nearest.first, "TR", "Standing at Trenton should rank Trenton first, got \(nearest)")
    }

    func testNearestCodesHonorsTheLimit() {
        let nearest = Stations.nearestCodes(to: newYorkPenn, limit: 4)

        XCTAssertEqual(nearest.count, 4, "Expected exactly 4 rows near Penn Station, got \(nearest)")
    }

    func testNearestCodesReturnsNothingFarFromEveryStation() {
        let nearest = Stations.nearestCodes(to: openOcean)

        XCTAssertTrue(nearest.isEmpty, "Nothing is within range mid-Atlantic, got \(nearest)")
    }

    func testNearestCodesRespectsTheMaximumDistance() {
        // One kilometre around Penn Station: a handful of stations, not the region.
        let nearest = Stations.nearestCodes(to: newYorkPenn, limit: 20, within: 1_000)

        for code in nearest {
            guard let coordinate = Stations.getCoordinates(for: code) else {
                return XCTFail("\(code) was ranked without coordinates")
            }
            let distance = CLLocation(latitude: newYorkPenn.latitude, longitude: newYorkPenn.longitude)
                .distance(from: CLLocation(latitude: coordinate.latitude, longitude: coordinate.longitude))
            XCTAssertLessThanOrEqual(distance, 1_000, "\(code) is \(Int(distance))m away, beyond the limit")
        }
    }

    func testNearestCodesCollapsesTheSameStationUnderSeveralCodes() {
        // Penn Station is the worst case: the rail station and several subway
        // platform codes sit on top of each other. A list of five entrances to
        // one station would be useless.
        let nearest = Stations.nearestCodes(to: newYorkPenn, limit: 8)

        for (index, code) in nearest.enumerated() {
            for other in nearest[(index + 1)...] {
                XCTAssertFalse(
                    Stations.areEquivalentStations(code, other),
                    "\(code) and \(other) are the same station and should not both be listed: \(nearest)"
                )
            }
        }
    }

    func testNearestCodesFilteredToASystemOnlyReturnsThatSystemsStations() {
        let nearest = Stations.nearestCodes(to: newYorkPenn, systems: [.njt], limit: 10)

        XCTAssertFalse(nearest.isEmpty, "NJ Transit serves Penn Station; expected results")
        for code in nearest {
            XCTAssertTrue(
                Stations.systemStringsForStation(code).contains("NJT"),
                "\(code) is not served by NJ Transit but was returned under an NJT filter"
            )
        }
    }

    func testNearestCodesWithoutAFilterStillExcludesDisabledOnlySystems() {
        // Boston is MBTA country, and MBTA is disabled app-wide. Only the
        // stations Amtrak also serves may come back.
        let nearest = Stations.nearestCodes(to: bostonSouth, limit: 10)

        for code in nearest {
            XCTAssertTrue(
                Stations.isStationAvailable(code),
                "\(code) belongs only to disabled systems and must not be offered"
            )
        }
    }

    // MARK: - Nearest System

    func testNearestSystemOnLongIslandIsLIRR() {
        // Ronkonkoma is LIRR-only, so standing on its platform scores LIRR at
        // zero distance — no other system can beat it.
        XCTAssertEqual(Stations.nearestSystem(to: ronkonkoma), .lirr)
    }

    func testNearestSystemAtPennStationIsOneThatActuallyServesIt() {
        guard let system = Stations.nearestSystem(to: newYorkPenn) else {
            return XCTFail("Penn Station should resolve to a system")
        }

        XCTAssertTrue(
            Stations.systemsForStation("NY").contains(system) || system == .subway,
            "\(system) does not serve Penn Station or its subway complex"
        )
    }

    func testNearestSystemReturnsNilFarFromEveryStation() {
        XCTAssertNil(Stations.nearestSystem(to: openOcean))
    }

    func testNearestSystemNeverSuggestsADisabledSystem() {
        // A rider in the Bay Area or Boston must not be steered into BART or
        // MBTA — they are switched off and would serve nothing.
        for coordinate in [sanFrancisco, bostonSouth] {
            if let system = Stations.nearestSystem(to: coordinate) {
                XCTAssertFalse(
                    system.isDisabled,
                    "\(system) is disabled app-wide and must never be suggested"
                )
            }
        }
    }

    func testNearestSystemIsStableForTheSameCoordinate() {
        // Dictionary iteration order varies per run; ties break deterministically
        // so a rider isn't shown a different system each time they tap the button.
        let first = Stations.nearestSystem(to: newYorkPenn)

        for _ in 0..<5 {
            XCTAssertEqual(Stations.nearestSystem(to: newYorkPenn), first)
        }
    }
}
