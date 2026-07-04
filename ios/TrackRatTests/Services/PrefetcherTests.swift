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

@MainActor
final class TrainCacheServiceTests: XCTestCase {

    private let cacheService = TrainCacheService.shared

    override func setUp() {
        super.setUp()
        cacheService.resetForTesting()
    }

    override func tearDown() {
        cacheService.resetForTesting()
        super.tearDown()
    }

    private func makeTrain(trainId: String, dataSource: String) -> TrainV2 {
        let now = Date()
        let departure = StationTiming(
            code: "NY",
            name: "New York Penn Station",
            scheduledTime: now,
            updatedTime: nil,
            actualTime: nil,
            track: "11"
        )
        let arrival = StationTiming(
            code: "PH",
            name: "Philadelphia",
            scheduledTime: now.addingTimeInterval(3600),
            updatedTime: nil,
            actualTime: nil,
            track: nil
        )

        return TrainV2(
            trainId: trainId,
            journeyDate: now,
            line: LineInfo(code: "NEC", name: "Northeast Corridor", color: "#FF6B00"),
            destination: "Philadelphia",
            departure: departure,
            arrival: arrival,
            trainPosition: nil,
            dataFreshness: nil,
            observationType: nil,
            isCancelled: false,
            isCompleted: false,
            dataSource: dataSource,
            stops: nil
        )
    }

    func testCacheSeparatesCollidingTrainNumbersByDataSource() {
        let date = Date()
        let njtTrain = makeTrain(trainId: "100", dataSource: "NJT")
        let amtrakTrain = makeTrain(trainId: "100", dataSource: "AMTRAK")

        cacheService.cacheTrain(
            njtTrain,
            trainNumber: "100",
            date: date,
            dataSource: "NJT"
        )
        cacheService.cacheTrain(
            amtrakTrain,
            trainNumber: "100",
            date: date,
            dataSource: "AMTRAK"
        )

        let cachedNJT = cacheService.getCachedTrain(
            trainNumber: "100",
            date: date,
            dataSource: "NJT"
        )
        let cachedAmtrak = cacheService.getCachedTrain(
            trainNumber: "100",
            date: date,
            dataSource: "AMTRAK"
        )

        XCTAssertEqual(cachedNJT?.train.dataSource, "NJT")
        XCTAssertEqual(cachedAmtrak?.train.dataSource, "AMTRAK")
    }

    func testDataSourceLookupFallsBackToLegacyCacheEntry() {
        let date = Date()
        let train = makeTrain(trainId: "200", dataSource: "NJT")

        cacheService.injectLegacyTrainForTesting(train, trainNumber: "200", date: date)

        let cached = cacheService.getCachedTrain(
            trainNumber: "200",
            date: date,
            dataSource: "NJT"
        )

        XCTAssertEqual(cached?.train.trainId, "200")
        XCTAssertEqual(cached?.train.dataSource, "NJT")
    }

    func testDataSourceLookupRejectsMismatchedLegacyCacheEntry() {
        let date = Date()
        let train = makeTrain(trainId: "300", dataSource: "NJT")

        cacheService.injectLegacyTrainForTesting(train, trainNumber: "300", date: date)

        let cached = cacheService.getCachedTrain(
            trainNumber: "300",
            date: date,
            dataSource: "AMTRAK"
        )

        XCTAssertNil(cached)
    }

    func testSourcelessLookupFindsSourceQualifiedCacheEntry() {
        // Source-aware paths cache under `dataSource|trainNumber|date`. Legacy
        // call sites that don't pass a dataSource must still surface those
        // entries; otherwise they'd hit deterministic cache misses and refetch
        // the same train. Codex review on PR #1136.
        let date = Date()
        let train = makeTrain(trainId: "400", dataSource: "NJT")

        cacheService.cacheTrain(
            train,
            trainNumber: "400",
            date: date,
            dataSource: "NJT"
        )

        let cached = cacheService.getCachedTrain(
            trainNumber: "400",
            date: date,
            dataSource: nil
        )

        XCTAssertNotNil(cached, "Source-less lookup should find source-qualified entry")
        XCTAssertEqual(cached?.train.trainId, "400")
        XCTAssertEqual(cached?.train.dataSource, "NJT")
    }

    func testSourcelessLookupIsDeterministicAcrossCollidingSources() {
        // Two systems can legitimately share a train number on the same date
        // (e.g. NJT 500 and AMTRAK 500). A source-less lookup can only return
        // one of them; sourceQualifiedKeysMatching breaks the tie by sorting
        // keys, so the alphabetically-first data source always wins rather
        // than whichever the underlying Set happened to iterate first.
        let date = Date()
        cacheService.cacheTrain(makeTrain(trainId: "500", dataSource: "NJT"), trainNumber: "500", date: date, dataSource: "NJT")
        cacheService.cacheTrain(makeTrain(trainId: "500", dataSource: "AMTRAK"), trainNumber: "500", date: date, dataSource: "AMTRAK")

        let cached = cacheService.getCachedTrain(trainNumber: "500", date: date, dataSource: nil)

        XCTAssertEqual(cached?.train.dataSource, "AMTRAK", "AMTRAK sorts before NJT, so it must win the source-less lookup")
    }

    // MARK: - Expiry

    func testExpiredEntryReturnsNilFromGetCachedTrain() {
        let date = Date()
        let train = makeTrain(trainId: "600", dataSource: "NJT")
        // Cached 301 seconds ago — just past the 5-minute cache window.
        let staleTimestamp = Date().addingTimeInterval(-301)
        cacheService.injectTrainForTesting(train, trainNumber: "600", date: date, dataSource: "NJT", cachedAt: staleTimestamp)

        XCTAssertNil(cacheService.getCachedTrain(trainNumber: "600", date: date, dataSource: "NJT"))
    }

    func testFreshEntryWithinCacheWindowReturnsHit() {
        let date = Date()
        let train = makeTrain(trainId: "601", dataSource: "NJT")
        // Cached 60 seconds ago — well within the 5-minute cache window.
        let recentTimestamp = Date().addingTimeInterval(-60)
        cacheService.injectTrainForTesting(train, trainNumber: "601", date: date, dataSource: "NJT", cachedAt: recentTimestamp)

        let cached = cacheService.getCachedTrain(trainNumber: "601", date: date, dataSource: "NJT")
        XCTAssertEqual(cached?.train.trainId, "601")
    }

    // MARK: - Persistence

    func testPersistedEntrySurvivesMemoryCacheClear() {
        let date = Date()
        let train = makeTrain(trainId: "700", dataSource: "NJT")
        cacheService.cacheTrain(train, trainNumber: "700", date: date, dataSource: "NJT")

        // Simulate a fresh app launch: memory cache is empty, only UserDefaults persists.
        cacheService.clearMemoryCacheForTesting()

        let cached = cacheService.getCachedTrain(trainNumber: "700", date: date, dataSource: "NJT")
        XCTAssertEqual(cached?.train.trainId, "700", "Entry must be recoverable from UserDefaults after memory cache is cleared")
    }

    // MARK: - LRU eviction

    func testMemoryCacheEvictsAtCapacity() {
        // Cap is 50; seed 51 distinct entries so the oldest must be evicted.
        for i in 0..<51 {
            let train = makeTrain(trainId: "\(800 + i)", dataSource: "NJT")
            cacheService.cacheTrain(train, trainNumber: "\(800 + i)", date: Date(), dataSource: "NJT")
        }

        XCTAssertEqual(cacheService.cachedEntryCountForTesting, 50, "Memory cache must not grow past its LRU cap")
    }
}
