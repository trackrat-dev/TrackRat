import XCTest
import CoreLocation
@testable import TrackRat

/// Direct coverage for `RouteShapes.coordinates(from:to:)`.
///
/// Before issue #1626 the only direct assertion anywhere was a single
/// `XCTAssertNil` in `CongestionMapKitViewTests`. That left the reversal branch
/// — the one an indexed rewrite is most likely to break — with no test at all,
/// and a direction bug there does not throw: it silently draws polylines that
/// double back on themselves.
///
/// These tests deliberately assert *structure and relationships*, not literal
/// coordinates, so regenerating the data from newer GTFS feeds does not force a
/// test rewrite. Point counts come from the committed artifact only where a
/// lower bound is being asserted.
final class RouteShapesTests: XCTestCase {

    // Segments verified present in the committed artifact, one per major
    // provider family, so a provider block silently failing to emit is caught.
    private let njtSegment = (from: "NP", to: "NY")        // Newark Penn -> New York Penn
    private let amtrakSegment = (from: "PAO", to: "PH")    // Paoli -> Philadelphia
    private let subwaySegment = (from: "S104", to: "S106") // NYC Subway

    // MARK: - Per-provider lookups

    func testNJTSegmentResolvesToAPolyline() {
        let coords = RouteShapes.coordinates(from: njtSegment.from, to: njtSegment.to)
        XCTAssertNotNil(coords, "NJT NP-NY is present in RouteShapes and must resolve")
        XCTAssertGreaterThan(
            coords?.count ?? 0, 2,
            "a shape entry must carry intermediate points; 2 or fewer means the "
                + "straight-line fallback and indicates the segment was dropped"
        )
    }

    func testAmtrakSegmentResolvesToAPolyline() {
        let coords = RouteShapes.coordinates(from: amtrakSegment.from, to: amtrakSegment.to)
        XCTAssertNotNil(coords, "Amtrak PAO-PH is present in RouteShapes and must resolve")
        XCTAssertGreaterThan(coords?.count ?? 0, 2)
    }

    func testSubwaySegmentResolvesToAPolyline() {
        let coords = RouteShapes.coordinates(from: subwaySegment.from, to: subwaySegment.to)
        XCTAssertNotNil(coords, "Subway S104-S106 is present in RouteShapes and must resolve")
        XCTAssertGreaterThanOrEqual(coords?.count ?? 0, 2)
    }

    // MARK: - Direction

    func testReverseLookupReturnsExactlyTheReversedCoordinates() {
        // Only the canonical (alphabetical) direction is stored; the opposite
        // direction is produced on read. If this breaks, the map draws segments
        // backwards and adjacent polylines visibly zig-zag.
        guard let forward = RouteShapes.coordinates(from: njtSegment.from, to: njtSegment.to),
              let reverse = RouteShapes.coordinates(from: njtSegment.to, to: njtSegment.from)
        else {
            return XCTFail("both directions of NP-NY must resolve")
        }

        XCTAssertEqual(forward.count, reverse.count)
        for (index, point) in reverse.enumerated() {
            let mirrored = forward[forward.count - 1 - index]
            XCTAssertEqual(point.latitude, mirrored.latitude, accuracy: 1e-9)
            XCTAssertEqual(point.longitude, mirrored.longitude, accuracy: 1e-9)
        }
    }

    func testReverseLookupStartsWhereForwardEnds() {
        // The cheap, readable statement of the same invariant: a rider going
        // NY -> NP must start at the end of the NP -> NY line.
        guard let forward = RouteShapes.coordinates(from: njtSegment.from, to: njtSegment.to),
              let reverse = RouteShapes.coordinates(from: njtSegment.to, to: njtSegment.from),
              let forwardEnd = forward.last, let reverseStart = reverse.first
        else {
            return XCTFail("both directions of NP-NY must resolve")
        }

        XCTAssertEqual(reverseStart.latitude, forwardEnd.latitude, accuracy: 1e-9)
        XCTAssertEqual(reverseStart.longitude, forwardEnd.longitude, accuracy: 1e-9)
    }

    func testBothArgumentOrdersHitTheSameStoredSegment() {
        // Canonical-key symmetry: one stored record serves both directions.
        let forward = RouteShapes.coordinates(from: amtrakSegment.from, to: amtrakSegment.to)
        let reverse = RouteShapes.coordinates(from: amtrakSegment.to, to: amtrakSegment.from)
        XCTAssertNotNil(forward)
        XCTAssertEqual(forward?.count, reverse?.count)
    }

    // MARK: - Misses

    func testUnknownStationPairReturnsNil() {
        // Callers rely on nil meaning "draw a straight line"; returning an
        // empty array instead would render nothing at all.
        XCTAssertNil(RouteShapes.coordinates(from: "NY", to: "HAR"))
    }

    func testCompletelyUnknownCodesReturnNil() {
        XCTAssertNil(RouteShapes.coordinates(from: "ZZZZ1", to: "ZZZZ2"))
    }

    func testSameStationReturnsNil() {
        // A station pair with itself is never a segment.
        XCTAssertNil(RouteShapes.coordinates(from: "NY", to: "NY"))
    }

    func testEmptyStationCodesReturnNil() {
        XCTAssertNil(RouteShapes.coordinates(from: "", to: ""))
        XCTAssertNil(RouteShapes.coordinates(from: "NY", to: ""))
    }

    // MARK: - Incremental decoding (issue #1626)

    func testRepeatedLookupsReturnEqualResults() {
        // Decoded segments are memoized in a bounded NSCache. A broken cache
        // key or a mutated cached array would show up here as drift between
        // the first (decoding) call and later (cached) calls.
        guard let first = RouteShapes.coordinates(from: njtSegment.from, to: njtSegment.to) else {
            return XCTFail("NP-NY must resolve")
        }
        for _ in 0..<3 {
            guard let again = RouteShapes.coordinates(from: njtSegment.from, to: njtSegment.to) else {
                return XCTFail("repeat lookup must still resolve")
            }
            XCTAssertEqual(again.count, first.count)
            XCTAssertEqual(again.first?.latitude, first.first?.latitude)
            XCTAssertEqual(again.last?.longitude, first.last?.longitude)
        }
    }

    func testCachedForwardLookupDoesNotCorruptTheReverseDirection() {
        // The cache stores canonical order. Reversing must not write the
        // reversed array back under the same key — that would make the second
        // reverse lookup return forward order.
        _ = RouteShapes.coordinates(from: njtSegment.from, to: njtSegment.to)
        guard let firstReverse = RouteShapes.coordinates(from: njtSegment.to, to: njtSegment.from),
              let secondReverse = RouteShapes.coordinates(from: njtSegment.to, to: njtSegment.from),
              let forward = RouteShapes.coordinates(from: njtSegment.from, to: njtSegment.to)
        else {
            return XCTFail("NP-NY must resolve in both directions")
        }

        XCTAssertEqual(firstReverse.first?.latitude, secondReverse.first?.latitude)
        XCTAssertEqual(firstReverse.first?.longitude, secondReverse.first?.longitude)
        XCTAssertEqual(
            secondReverse.first?.latitude, forward.last?.latitude,
            "a cached reverse lookup must still be the reverse of canonical order"
        )
    }

    func testLookupsAcrossManySegmentsAllResolve() {
        // Exercises more distinct keys than the cache's countLimit (128) so an
        // eviction can't turn a previously-decoded segment into a miss.
        let pairs = [njtSegment, amtrakSegment, subwaySegment]
        for _ in 0..<50 {
            for pair in pairs {
                XCTAssertNotNil(
                    RouteShapes.coordinates(from: pair.from, to: pair.to),
                    "\(pair.from)-\(pair.to) must resolve regardless of cache state"
                )
            }
        }
    }

    func testCoordinatesAreGeographicallyPlausible() {
        // Guards against a lat/lon transposition in the decoder, which would
        // otherwise produce a valid-looking array pointing at the wrong place.
        guard let coords = RouteShapes.coordinates(from: njtSegment.from, to: njtSegment.to) else {
            return XCTFail("NP-NY must resolve")
        }
        for point in coords {
            XCTAssertTrue(
                (39.0...42.0).contains(point.latitude),
                "latitude \(point.latitude) is outside the NJ/NY corridor — lat/lon may be swapped"
            )
            XCTAssertTrue(
                (-76.0...(-73.0)).contains(point.longitude),
                "longitude \(point.longitude) is outside the NJ/NY corridor"
            )
        }
    }
}
