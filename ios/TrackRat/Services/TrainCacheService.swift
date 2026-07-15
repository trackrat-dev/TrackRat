//
//  TrainCacheService.swift
//  TrackRat
//
//  Created by Claude on 2025-11-17.
//

import Foundation

/// Service responsible for caching train details to enable instant loading
/// Uses two-tier caching: in-memory for speed, UserDefaults for persistence across app launches
@MainActor
class TrainCacheService {
    static let shared = TrainCacheService()

    private let userDefaults = UserDefaults.standard
    private let cacheKeyPrefix = "train_cache_"
    private let cacheMetadataKey = "train_cache_metadata"

    // In-memory cache for fast access during active session
    private var memoryCache: [String: CachedTrain] = [:]
    // PERFORMANCE: Track access order for LRU eviction
    private var memoryCacheAccessOrder: [String] = []
    // PERFORMANCE: Maximum number of entries in memory cache to prevent unbounded growth
    private let maxMemoryCacheSize = 50

    // How long entries are retained at all. Stale entries (past the freshness
    // window but within retention) are kept so offline readers can render
    // last-known data via `allowStale` — e.g. tapping a Live Activity with no
    // cell service. Swept on initialization.
    private let maxCacheRetention: TimeInterval = 24 * 60 * 60

    private init() {
        // Clean up old cache entries on initialization
        cleanupExpiredCache()
    }

    // MARK: - Cache Models

    struct CachedTrain: Codable {
        let train: TrainV2
        let cachedAt: Date
        let cacheKey: String

        /// Freshness window (5 minutes). This is separate from API data
        /// freshness - it's how long we trust our local cache. Older entries
        /// are stale: not served by default reads, but retained for
        /// `allowStale` readers.
        static let freshnessWindow: TimeInterval = 300

        var isExpired: Bool {
            Date().timeIntervalSince(cachedAt) > Self.freshnessWindow
        }

        var ageSeconds: Int {
            Int(Date().timeIntervalSince(cachedAt))
        }
    }

    struct CacheMetadata: Codable {
        var keys: [String: Date] // cache key -> cached timestamp
    }

    // MARK: - Cache Key Generation

    private func dateCacheKey(for date: Date) -> String {
        Calendar.current.startOfDay(for: date)
            .formatted(.iso8601.year().month().day())
    }

    private func normalizedDataSource(_ dataSource: String?) -> String? {
        guard let source = dataSource?.trimmingCharacters(in: .whitespacesAndNewlines),
              !source.isEmpty else {
            return nil
        }
        return source
    }

    /// Legacy key used before dataSource became part of train identity.
    private func generateLegacyCacheKey(trainNumber: String, date: Date) -> String {
        "\(trainNumber)|\(dateCacheKey(for: date))"
    }

    /// Cache key is `dataSource|trainNumber|YYYY-MM-DD` when the source is known.
    private func generateCacheKey(
        trainNumber: String,
        date: Date,
        dataSource: String?
    ) -> String {
        let dateString = dateCacheKey(for: date)
        if let source = normalizedDataSource(dataSource) {
            return "\(source)|\(trainNumber)|\(dateString)"
        }
        return "\(trainNumber)|\(dateString)"
    }

    private func lookupKeys(
        trainNumber: String,
        date: Date,
        dataSource: String?
    ) -> [String] {
        let primaryKey = generateCacheKey(
            trainNumber: trainNumber,
            date: date,
            dataSource: dataSource
        )
        let legacyKey = generateLegacyCacheKey(trainNumber: trainNumber, date: date)
        return primaryKey == legacyKey ? [primaryKey] : [primaryKey, legacyKey]
    }

    /// Source-qualified keys (`dataSource|trainNumber|date`) that match the
    /// requested trainNumber and date. Used as a fallback when a caller looks
    /// up without a dataSource so we still surface entries cached by newer
    /// source-aware paths. The leading `|` in the suffix ensures the legacy
    /// `trainNumber|date` form never matches.
    private func sourceQualifiedKeysMatching(
        trainNumber: String,
        date: Date
    ) -> [String] {
        let suffix = "|\(trainNumber)|\(dateCacheKey(for: date))"
        var keys: Set<String> = []
        for key in memoryCache.keys where key.hasSuffix(suffix) {
            keys.insert(key)
        }
        for key in getCacheMetadata().keys.keys where key.hasSuffix(suffix) {
            keys.insert(key)
        }
        // Sorted so a source-less lookup deterministically prefers the same
        // data source every time when two systems cache the same train
        // number/date (e.g. NJT 7801 vs Amtrak 7801), instead of picking
        // whichever the Set happened to iterate first.
        return keys.sorted()
    }

    // MARK: - Retrieval

    /// Retrieves cached train details. Returns nil for miss or expired entry.
    /// With `allowStale`, an expired entry still within `maxCacheRetention` is
    /// returned when no fresh one exists, so callers can render last-known data
    /// while the network is unavailable. Check `CachedTrain.isExpired` on the
    /// result to surface staleness to the user.
    func getCachedTrain(
        trainNumber: String,
        date: Date = Date(),
        dataSource: String? = nil,
        allowStale: Bool = false
    ) -> CachedTrain? {
        // Fresh entries always win; only fall back to a stale one when allowed,
        // so a stale entry under one key never shadows a fresh one under another.
        if let fresh = lookupCachedTrain(
            trainNumber: trainNumber,
            date: date,
            dataSource: dataSource,
            allowStale: false
        ) {
            return fresh
        }
        guard allowStale else { return nil }
        return lookupCachedTrain(
            trainNumber: trainNumber,
            date: date,
            dataSource: dataSource,
            allowStale: true
        )
    }

    private func lookupCachedTrain(
        trainNumber: String,
        date: Date,
        dataSource: String?,
        allowStale: Bool
    ) -> CachedTrain? {
        let requestedSource = normalizedDataSource(dataSource)

        for cacheKey in lookupKeys(
            trainNumber: trainNumber,
            date: date,
            dataSource: dataSource
        ) {
            if let cached = getCachedTrainByKey(cacheKey, allowStale: allowStale) {
                if let requestedSource,
                   normalizedDataSource(cached.train.dataSource) != requestedSource {
                    continue
                }
                return cached
            }
        }

        // When the caller doesn't know the data source, also check entries
        // cached under newer `dataSource|trainNumber|date` keys. Without this,
        // legacy/source-less navigation paths would deterministically miss
        // entries written by source-aware paths (Live Activities, Train List,
        // Prefetcher) for the same train.
        if requestedSource == nil {
            for cacheKey in sourceQualifiedKeysMatching(
                trainNumber: trainNumber,
                date: date
            ) {
                if let cached = getCachedTrainByKey(cacheKey, allowStale: allowStale) {
                    return cached
                }
            }
        }
        return nil
    }

    /// Internal helper to get cached train by key. Expired entries are retained
    /// (for `allowStale` readers) until they age past `maxCacheRetention`.
    private func getCachedTrainByKey(_ cacheKey: String, allowStale: Bool) -> CachedTrain? {
        // Check in-memory cache first (fastest)
        if let cached = memoryCache[cacheKey] {
            if Double(cached.ageSeconds) > maxCacheRetention {
                print("🧹 Cache RETENTION EXPIRED (memory): \(cacheKey) - age: \(cached.ageSeconds)s")
                removeCacheEntry(cacheKey)
                return nil
            }
            if !cached.isExpired || allowStale {
                print("✅ Cache HIT (memory\(cached.isExpired ? ", stale" : "")): \(cacheKey) - age: \(cached.ageSeconds)s")
                // Update LRU access order
                updateAccessOrder(for: cacheKey)
                return cached
            }
            print("⏰ Cache EXPIRED (memory): \(cacheKey) - age: \(cached.ageSeconds)s")
            // Memory is written on every cacheTrain alongside UserDefaults, so
            // the persistent tier can never hold a fresher copy — stop here.
            return nil
        }

        // Check persistent cache (UserDefaults)
        let persistentKey = cacheKeyPrefix + cacheKey
        if let data = userDefaults.data(forKey: persistentKey),
           let cached = try? JSONDecoder().decode(CachedTrain.self, from: data) {
            if Double(cached.ageSeconds) > maxCacheRetention {
                print("🧹 Cache RETENTION EXPIRED (persistent): \(cacheKey) - age: \(cached.ageSeconds)s")
                removeCacheEntry(cacheKey)
                return nil
            }
            if !cached.isExpired || allowStale {
                print("✅ Cache HIT (persistent\(cached.isExpired ? ", stale" : "")): \(cacheKey) - age: \(cached.ageSeconds)s")
                // Restore to memory cache with LRU tracking
                addToMemoryCache(key: cacheKey, value: cached)
                return cached
            }
            print("⏰ Cache EXPIRED (persistent): \(cacheKey) - age: \(cached.ageSeconds)s")
            return nil
        }

        print("❌ Cache MISS: \(cacheKey)")
        return nil
    }

    /// Drops an entry from both tiers and the metadata index.
    private func removeCacheEntry(_ cacheKey: String) {
        memoryCache.removeValue(forKey: cacheKey)
        memoryCacheAccessOrder.removeAll { $0 == cacheKey }
        userDefaults.removeObject(forKey: cacheKeyPrefix + cacheKey)
        var metadata = getCacheMetadata()
        if metadata.keys.removeValue(forKey: cacheKey) != nil {
            saveCacheMetadata(metadata)
        }
    }

    /// Returns the age of the cache in seconds, or nil if not cached. Used to gate
    /// background refresh and prefetch when the existing entry is already fresh.
    func getCacheAge(
        trainNumber: String,
        date: Date = Date(),
        dataSource: String? = nil
    ) -> TimeInterval? {
        if let cached = getCachedTrain(
            trainNumber: trainNumber,
            date: date,
            dataSource: dataSource
        ) {
            return TimeInterval(cached.ageSeconds)
        }
        return nil
    }

    // MARK: - Storage

    /// Stores train details using the canonical dataSource+trainNumber+date key when
    /// the caller has a source, otherwise the legacy trainNumber+date key.
    func cacheTrain(
        _ train: TrainV2,
        trainNumber: String,
        date: Date = Date(),
        dataSource: String? = nil
    ) {
        let cacheKey = generateCacheKey(
            trainNumber: trainNumber,
            date: date,
            dataSource: normalizedDataSource(dataSource)
        )

        let cached = CachedTrain(
            train: train,
            cachedAt: Date(),
            cacheKey: cacheKey
        )

        // Store in memory cache with LRU tracking
        addToMemoryCache(key: cacheKey, value: cached)

        // Store in persistent cache
        if let encoded = try? JSONEncoder().encode(cached) {
            let persistentKey = cacheKeyPrefix + cacheKey
            userDefaults.set(encoded, forKey: persistentKey)

            // Update metadata
            var metadata = getCacheMetadata()
            metadata.keys[cacheKey] = cached.cachedAt
            saveCacheMetadata(metadata)

            print("💾 Cached train: \(cacheKey)")
        }
    }

    // MARK: - LRU Cache Management

    /// Update the access order for LRU tracking
    private func updateAccessOrder(for key: String) {
        // Remove from current position and add to end (most recently used)
        memoryCacheAccessOrder.removeAll { $0 == key }
        memoryCacheAccessOrder.append(key)
    }

    /// Add item to memory cache with LRU eviction
    private func addToMemoryCache(key: String, value: CachedTrain) {
        // If key already exists, update access order
        if memoryCache[key] != nil {
            updateAccessOrder(for: key)
        } else {
            // New entry - add to access order
            memoryCacheAccessOrder.append(key)
        }

        memoryCache[key] = value

        // PERFORMANCE: Evict least recently used entries if over limit
        while memoryCache.count > maxMemoryCacheSize {
            if let oldestKey = memoryCacheAccessOrder.first {
                memoryCache.removeValue(forKey: oldestKey)
                memoryCacheAccessOrder.removeFirst()
                print("🧹 LRU evicted: \(oldestKey)")
            } else {
                break
            }
        }
    }

    // MARK: - Cache Management

    /// Removes entries older than the retention window from persistent storage
    private func cleanupExpiredCache() {
        var metadata = getCacheMetadata()
        var hasChanges = false

        for (cacheKey, cachedAt) in metadata.keys {
            let age = Date().timeIntervalSince(cachedAt)
            if age > maxCacheRetention {
                let persistentKey = cacheKeyPrefix + cacheKey
                userDefaults.removeObject(forKey: persistentKey)
                metadata.keys.removeValue(forKey: cacheKey)
                hasChanges = true
                print("🧹 Cleaned up expired cache: \(cacheKey)")
            }
        }

        if hasChanges {
            saveCacheMetadata(metadata)
        }
    }

    // MARK: - Metadata Helpers

    private func getCacheMetadata() -> CacheMetadata {
        guard let data = userDefaults.data(forKey: cacheMetadataKey),
              let metadata = try? JSONDecoder().decode(CacheMetadata.self, from: data) else {
            return CacheMetadata(keys: [:])
        }
        return metadata
    }

    private func saveCacheMetadata(_ metadata: CacheMetadata) {
        if let encoded = try? JSONEncoder().encode(metadata) {
            userDefaults.set(encoded, forKey: cacheMetadataKey)
        }
    }

    // MARK: - Test support

    /// Test-only: number of entries currently held in the in-memory LRU cache.
    var cachedEntryCountForTesting: Int {
        memoryCache.count
    }

    /// Test-only: clear cached state from memory and UserDefaults.
    func resetForTesting() {
        let metadata = getCacheMetadata()
        for cacheKey in metadata.keys.keys {
            userDefaults.removeObject(forKey: cacheKeyPrefix + cacheKey)
        }
        userDefaults.removeObject(forKey: cacheMetadataKey)
        memoryCache.removeAll()
        memoryCacheAccessOrder.removeAll()
    }

    /// Test-only: drop the in-memory cache while leaving UserDefaults intact,
    /// simulating a fresh app launch reading back persisted entries.
    func clearMemoryCacheForTesting() {
        memoryCache.removeAll()
        memoryCacheAccessOrder.removeAll()
    }

    /// Test-only: seed a cache entry with an explicit `cachedAt` to exercise expiry.
    func injectTrainForTesting(
        _ train: TrainV2,
        trainNumber: String,
        date: Date = Date(),
        dataSource: String? = nil,
        cachedAt: Date
    ) {
        let cacheKey = generateCacheKey(
            trainNumber: trainNumber,
            date: date,
            dataSource: normalizedDataSource(dataSource)
        )
        let cached = CachedTrain(train: train, cachedAt: cachedAt, cacheKey: cacheKey)

        addToMemoryCache(key: cacheKey, value: cached)
        if let encoded = try? JSONEncoder().encode(cached) {
            userDefaults.set(encoded, forKey: cacheKeyPrefix + cacheKey)
            var metadata = getCacheMetadata()
            metadata.keys[cacheKey] = cachedAt
            saveCacheMetadata(metadata)
        }
    }

    /// Test-only: seed the old trainNumber+date cache shape.
    func injectLegacyTrainForTesting(
        _ train: TrainV2,
        trainNumber: String,
        date: Date = Date(),
        cachedAt: Date = Date()
    ) {
        let cacheKey = generateLegacyCacheKey(trainNumber: trainNumber, date: date)
        let cached = CachedTrain(train: train, cachedAt: cachedAt, cacheKey: cacheKey)

        addToMemoryCache(key: cacheKey, value: cached)
        if let encoded = try? JSONEncoder().encode(cached) {
            userDefaults.set(encoded, forKey: cacheKeyPrefix + cacheKey)
            var metadata = getCacheMetadata()
            metadata.keys[cacheKey] = cached.cachedAt
            saveCacheMetadata(metadata)
        }
    }
}
