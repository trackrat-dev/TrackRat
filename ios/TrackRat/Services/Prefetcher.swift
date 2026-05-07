import Foundation

/// Warms caches for the most likely next navigation so user-visible loads render
/// instantly. Two endpoints:
///
/// - **Trips list** (`/v2/trips/search`): memory-only cache keyed by
///   `from|to|YYYY-MM-DD|sortedSystemsCsv`, 60s TTL, FIFO eviction.
/// - **Train details** (`/v2/trains/{id}`): writes through to the existing
///   `TrainCacheService.shared` cache.
///
/// Concurrent calls for the same key coalesce into a single network request.
/// Prefetch (fire-and-forget) skips work if the cache is already fresh; the
/// async `fetchTrips` always hits the network so the list view's auto-refresh
/// is not gated by TTL.
@MainActor
final class Prefetcher {
    static let shared = Prefetcher()

    // MARK: - Configuration

    /// Trips list cache freshness. Shorter than the list view's 30s auto-refresh
    /// so even a cache hit is followed by a silent refresh in-place.
    private let tripsTTL: TimeInterval = 60

    /// Skip detail prefetch when the existing cache is fresher than this.
    private let detailsSkipIfFresherThan: TimeInterval = 60

    /// Hard cap on the trips cache to bound memory across long sessions.
    private let maxTripsCacheEntries = 20

    // MARK: - State

    private struct CachedTrips {
        let trips: [TripOption]
        let cachedAt: Date
        var ageSeconds: Int { Int(Date().timeIntervalSince(cachedAt)) }
    }

    private var tripsCache: [String: CachedTrips] = [:]
    private var tripsCacheOrder: [String] = []
    private var inFlightTrips: [String: Task<[TripOption], Error>] = [:]
    private var inFlightDetails: Set<String> = []

    private let apiService: APIService

    // MARK: - Init

    init(apiService: APIService = .shared) {
        self.apiService = apiService
    }

    // MARK: - Trips

    /// Synchronous read. Returns nil for miss or expired entry (and evicts the expired entry).
    func cachedTrips(
        from: String,
        to: String,
        date: Date,
        systems: Set<TrainSystem>
    ) -> [TripOption]? {
        let key = tripsCacheKey(from: from, to: to, date: date, systems: systems)
        guard let entry = tripsCache[key] else { return nil }
        if TimeInterval(entry.ageSeconds) > tripsTTL {
            tripsCache.removeValue(forKey: key)
            tripsCacheOrder.removeAll { $0 == key }
            return nil
        }
        Log.debug("Prefetcher: trips cache HIT (\(entry.ageSeconds)s) \(key)")
        return entry.trips
    }

    /// Always hits the network. Coalesces concurrent calls for the same key and writes the
    /// result to cache. Use this from list-view load and silent-refresh paths.
    @discardableResult
    func fetchTrips(
        from: String,
        to: String,
        date: Date,
        systems: Set<TrainSystem>
    ) async throws -> [TripOption] {
        let key = tripsCacheKey(from: from, to: to, date: date, systems: systems)
        if let existing = inFlightTrips[key] {
            return try await existing.value
        }
        let dataSources: Set<TrainSystem>? = systems.isEmpty ? nil : systems
        let task = Task<[TripOption], Error> {
            // Cleanup runs on task completion regardless of caller cancellation, so a
            // cancelled awaiter never leaves a stale in-flight entry behind.
            defer { self.inFlightTrips.removeValue(forKey: key) }
            let trips = try await self.apiService.searchTrips(
                fromStationCode: from,
                toStationCode: to,
                date: date,
                dataSources: dataSources
            )
            self.recordTrips(trips, key: key)
            return trips
        }
        inFlightTrips[key] = task
        return try await task.value
    }

    /// Fire-and-forget warmup. Skips if the cache is fresh.
    func prefetchTrips(
        from: String,
        to: String,
        date: Date = Date(),
        systems: Set<TrainSystem>
    ) {
        if cachedTrips(from: from, to: to, date: date, systems: systems) != nil { return }
        Task {
            do {
                _ = try await self.fetchTrips(from: from, to: to, date: date, systems: systems)
            } catch {
                Log.warning("Prefetcher: prefetchTrips failed for \(from)->\(to): \(error.localizedDescription)")
            }
        }
    }

    // MARK: - Train details

    /// Fire-and-forget warmup of the train detail cache. Skips if `TrainCacheService` already
    /// has a fresh entry. Concurrent prefetches for the same train+date coalesce.
    ///
    /// Note: a fast tap can race a prefetch with `TrainDetailsView`'s direct fetch — both will
    /// run, both write the same cache entry. Wasted bandwidth, no correctness issue.
    func prefetchTrainDetails(
        trainNumber: String,
        fromStation: String?,
        date: Date = Date(),
        dataSource: String?
    ) {
        guard !trainNumber.isEmpty else { return }
        if let age = TrainCacheService.shared.getCacheAge(trainNumber: trainNumber, date: date),
           age < detailsSkipIfFresherThan {
            return
        }
        let key = trainDetailsKey(trainNumber: trainNumber, date: date)
        guard !inFlightDetails.contains(key) else { return }
        inFlightDetails.insert(key)
        Task {
            defer { self.inFlightDetails.remove(key) }
            do {
                let train = try await self.apiService.fetchTrainDetails(
                    id: trainNumber,
                    fromStationCode: fromStation,
                    date: date,
                    dataSource: dataSource
                )
                TrainCacheService.shared.cacheTrain(train, trainNumber: trainNumber, date: date)
                Log.debug("Prefetcher: train details warmed for \(trainNumber)")
            } catch {
                Log.warning("Prefetcher: prefetchTrainDetails failed for \(trainNumber): \(error.localizedDescription)")
            }
        }
    }

    // MARK: - Internals

    private func recordTrips(_ trips: [TripOption], key: String) {
        tripsCache[key] = CachedTrips(trips: trips, cachedAt: Date())
        tripsCacheOrder.removeAll { $0 == key }
        tripsCacheOrder.append(key)
        while tripsCache.count > maxTripsCacheEntries, let oldest = tripsCacheOrder.first {
            tripsCache.removeValue(forKey: oldest)
            tripsCacheOrder.removeFirst()
        }
    }

    private func tripsCacheKey(
        from: String,
        to: String,
        date: Date,
        systems: Set<TrainSystem>
    ) -> String {
        let dateString = Calendar.current.startOfDay(for: date)
            .formatted(.iso8601.year().month().day())
        let systemsCsv = systems.map(\.rawValue).sorted().joined(separator: ",")
        return "\(from)|\(to)|\(dateString)|\(systemsCsv)"
    }

    private func trainDetailsKey(trainNumber: String, date: Date) -> String {
        let dateString = Calendar.current.startOfDay(for: date)
            .formatted(.iso8601.year().month().day())
        return "\(trainNumber)|\(dateString)"
    }

    // MARK: - Test support

    /// Test-only: clear all cached state.
    func resetForTesting() {
        tripsCache.removeAll()
        tripsCacheOrder.removeAll()
        inFlightTrips.removeAll()
        inFlightDetails.removeAll()
    }

    /// Test-only: seed the trips cache with a known entry. `cachedAt` lets tests simulate
    /// expired entries without manipulating the system clock.
    func injectTripsForTesting(
        _ trips: [TripOption],
        from: String,
        to: String,
        date: Date,
        systems: Set<TrainSystem>,
        cachedAt: Date = Date()
    ) {
        let key = tripsCacheKey(from: from, to: to, date: date, systems: systems)
        tripsCache[key] = CachedTrips(trips: trips, cachedAt: cachedAt)
        tripsCacheOrder.removeAll { $0 == key }
        tripsCacheOrder.append(key)
    }
}
