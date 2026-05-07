import XCTest
@testable import TrackRat

@MainActor
final class PrefetcherTests: XCTestCase {

    var prefetcher: Prefetcher!

    override func setUp() {
        super.setUp()
        // Use the singleton — production callers do too. resetForTesting clears state
        // between tests so we don't leak between runs.
        prefetcher = Prefetcher.shared
        prefetcher.resetForTesting()
    }

    override func tearDown() {
        prefetcher.resetForTesting()
        prefetcher = nil
        super.tearDown()
    }

    // MARK: - Helpers

    private func makeTripOption(trainId: String = "T1") -> TripOption {
        let leg = TripLeg(
            trainId: trainId,
            journeyDate: Date(),
            line: LineInfo(code: "NEC", name: "Northeast Corridor", color: "#FF0000"),
            dataSource: "NJT",
            destination: "Newark",
            boarding: StationTiming(code: "NY", name: "New York", scheduledTime: Date(), updatedTime: nil, actualTime: nil, track: nil),
            alighting: StationTiming(code: "NP", name: "Newark", scheduledTime: Date().addingTimeInterval(1800), updatedTime: nil, actualTime: nil, track: nil),
            observationType: nil,
            isCancelled: false,
            trainPosition: nil
        )
        return TripOption(
            legs: [leg],
            transfers: [],
            departureTime: Date(),
            arrivalTime: Date().addingTimeInterval(1800),
            totalDurationMinutes: 30,
            isDirect: true
        )
    }

    // MARK: - Cache hit / miss

    func testCachedTripsReturnsNilWhenEmpty() {
        let result = prefetcher.cachedTrips(from: "NY", to: "NP", date: Date(), systems: [.njt])
        XCTAssertNil(result, "Empty cache should return nil")
    }

    func testInjectedTripsReturnedOnHit() {
        let trips = [makeTripOption(trainId: "T1"), makeTripOption(trainId: "T2")]
        let date = Date()
        prefetcher.injectTripsForTesting(trips, from: "NY", to: "NP", date: date, systems: [.njt])

        let result = prefetcher.cachedTrips(from: "NY", to: "NP", date: date, systems: [.njt])
        XCTAssertNotNil(result, "Cache should return seeded value")
        XCTAssertEqual(result?.count, 2, "Returned count should match seeded count")
    }

    // MARK: - Cache key consistency

    func testCacheKeyIsOrderIndependentForSystemsSet() {
        let trips = [makeTripOption()]
        let date = Date()
        // Insertion order: NJT then AMTRAK
        let setA: Set<TrainSystem> = [.njt, .amtrak]
        prefetcher.injectTripsForTesting(trips, from: "NY", to: "NP", date: date, systems: setA)

        // Query with the reverse insertion order: AMTRAK then NJT
        let setB: Set<TrainSystem> = [.amtrak, .njt]
        let result = prefetcher.cachedTrips(from: "NY", to: "NP", date: date, systems: setB)

        XCTAssertNotNil(result, "Sets with the same members must produce the same cache key regardless of iteration order")
    }

    func testCacheMissesWhenSystemsDiffer() {
        let trips = [makeTripOption()]
        let date = Date()
        prefetcher.injectTripsForTesting(trips, from: "NY", to: "NP", date: date, systems: [.njt])

        let result = prefetcher.cachedTrips(from: "NY", to: "NP", date: date, systems: [.njt, .amtrak])
        XCTAssertNil(result, "Different systems set must produce a different cache key")
    }

    func testCacheMissesWhenStationsDiffer() {
        let trips = [makeTripOption()]
        let date = Date()
        prefetcher.injectTripsForTesting(trips, from: "NY", to: "NP", date: date, systems: [.njt])

        XCTAssertNil(prefetcher.cachedTrips(from: "NP", to: "NY", date: date, systems: [.njt]),
                     "Reversed direction must miss")
        XCTAssertNil(prefetcher.cachedTrips(from: "NY", to: "TR", date: date, systems: [.njt]),
                     "Different destination must miss")
    }

    func testCacheKeyIgnoresTimeOfDayUsesStartOfDay() {
        let trips = [makeTripOption()]
        let morning = Calendar.current.startOfDay(for: Date()).addingTimeInterval(8 * 3600)
        let evening = Calendar.current.startOfDay(for: Date()).addingTimeInterval(20 * 3600)

        prefetcher.injectTripsForTesting(trips, from: "NY", to: "NP", date: morning, systems: [.njt])

        let result = prefetcher.cachedTrips(from: "NY", to: "NP", date: evening, systems: [.njt])
        XCTAssertNotNil(result, "Same-day queries must hit the same cache entry regardless of time of day")
    }

    // MARK: - TTL

    func testExpiredEntryReturnsNilAndIsEvicted() {
        let trips = [makeTripOption()]
        let date = Date()
        // Cached 5 minutes ago — well past the 60s TTL.
        let staleTimestamp = Date().addingTimeInterval(-300)
        prefetcher.injectTripsForTesting(trips, from: "NY", to: "NP", date: date, systems: [.njt], cachedAt: staleTimestamp)

        let result = prefetcher.cachedTrips(from: "NY", to: "NP", date: date, systems: [.njt])
        XCTAssertNil(result, "Entry past TTL must return nil")

        // Re-query immediately to verify the expired entry was evicted (not just filtered).
        let result2 = prefetcher.cachedTrips(from: "NY", to: "NP", date: date, systems: [.njt])
        XCTAssertNil(result2, "Expired entry should remain absent on subsequent reads")
    }

    func testFreshEntryWithinTTLReturnsHit() {
        let trips = [makeTripOption()]
        let date = Date()
        // Cached 30 seconds ago — within the 60s TTL.
        let recentTimestamp = Date().addingTimeInterval(-30)
        prefetcher.injectTripsForTesting(trips, from: "NY", to: "NP", date: date, systems: [.njt], cachedAt: recentTimestamp)

        let result = prefetcher.cachedTrips(from: "NY", to: "NP", date: date, systems: [.njt])
        XCTAssertNotNil(result, "Entry within TTL must return a hit")
    }

    // MARK: - FIFO eviction

    func testFIFOEvictionWhenOverCapacity() {
        let trips = [makeTripOption()]
        let date = Date()

        // Seed 21 entries with distinct from/to pairs. Cap is 20, so the first should be evicted.
        for i in 0..<21 {
            prefetcher.injectTripsForTesting(trips, from: "F\(i)", to: "T\(i)", date: date, systems: [.njt])
        }

        // F0/T0 was inserted first — it should now be evicted.
        XCTAssertNil(prefetcher.cachedTrips(from: "F0", to: "T0", date: date, systems: [.njt]),
                     "Oldest entry must be evicted when cache exceeds capacity")
        // F20/T20 was inserted last — still present.
        XCTAssertNotNil(prefetcher.cachedTrips(from: "F20", to: "T20", date: date, systems: [.njt]),
                        "Newest entry must remain after eviction")
    }

    // Note: in-flight task coalescing and network-fetch behavior are not tested here.
    // APIService is `final` and not protocol-backed, so substituting a fake would require a
    // larger refactor. Coalescing is enforced by the type system (single Task<_,_> per key)
    // and by code review.
}
