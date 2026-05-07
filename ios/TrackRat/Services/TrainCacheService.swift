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

    // Maximum age for cached data (5 minutes = 300 seconds)
    // This is separate from API data freshness - it's how long we trust our local cache
    private let maxCacheAge: TimeInterval = 300

    private init() {
        // Clean up old cache entries on initialization
        cleanupExpiredCache()
    }

    // MARK: - Cache Models

    struct CachedTrain: Codable {
        let train: TrainV2
        let cachedAt: Date
        let cacheKey: String

        var isExpired: Bool {
            Date().timeIntervalSince(cachedAt) > 300 // 5 minutes
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

    // MARK: - Retrieval

    /// Retrieves cached train details. Returns nil for miss or expired entry.
    func getCachedTrain(
        trainNumber: String,
        date: Date = Date(),
        dataSource: String? = nil
    ) -> CachedTrain? {
        let requestedSource = normalizedDataSource(dataSource)

        for cacheKey in lookupKeys(
            trainNumber: trainNumber,
            date: date,
            dataSource: dataSource
        ) {
            if let cached = getCachedTrainByKey(cacheKey) {
                if let requestedSource,
                   normalizedDataSource(cached.train.dataSource) != requestedSource {
                    continue
                }
                return cached
            }
        }
        return nil
    }

    /// Internal helper to get cached train by key
    private func getCachedTrainByKey(_ cacheKey: String) -> CachedTrain? {
        // Check in-memory cache first (fastest)
        if let cached = memoryCache[cacheKey] {
            if !cached.isExpired {
                print("✅ Cache HIT (memory): \(cacheKey) - age: \(cached.ageSeconds)s")
                // Update LRU access order
                updateAccessOrder(for: cacheKey)
                return cached
            } else {
                print("⏰ Cache EXPIRED (memory): \(cacheKey) - age: \(cached.ageSeconds)s")
                memoryCache.removeValue(forKey: cacheKey)
                memoryCacheAccessOrder.removeAll { $0 == cacheKey }
            }
        }

        // Check persistent cache (UserDefaults)
        let persistentKey = cacheKeyPrefix + cacheKey
        if let data = userDefaults.data(forKey: persistentKey),
           let cached = try? JSONDecoder().decode(CachedTrain.self, from: data) {
            if !cached.isExpired {
                print("✅ Cache HIT (persistent): \(cacheKey) - age: \(cached.ageSeconds)s")
                // Restore to memory cache with LRU tracking
                addToMemoryCache(key: cacheKey, value: cached)
                return cached
            } else {
                print("⏰ Cache EXPIRED (persistent): \(cacheKey) - age: \(cached.ageSeconds)s")
                userDefaults.removeObject(forKey: persistentKey)
            }
        }

        print("❌ Cache MISS: \(cacheKey)")
        return nil
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

    /// Removes expired cache entries from persistent storage
    private func cleanupExpiredCache() {
        var metadata = getCacheMetadata()
        var hasChanges = false

        for (cacheKey, cachedAt) in metadata.keys {
            let age = Date().timeIntervalSince(cachedAt)
            if age > maxCacheAge {
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

    /// Test-only: seed the old trainNumber+date cache shape.
    func injectLegacyTrainForTesting(
        _ train: TrainV2,
        trainNumber: String,
        date: Date = Date()
    ) {
        let cacheKey = generateLegacyCacheKey(trainNumber: trainNumber, date: date)
        let cached = CachedTrain(train: train, cachedAt: Date(), cacheKey: cacheKey)

        addToMemoryCache(key: cacheKey, value: cached)
        if let encoded = try? JSONEncoder().encode(cached) {
            userDefaults.set(encoded, forKey: cacheKeyPrefix + cacheKey)
            var metadata = getCacheMetadata()
            metadata.keys[cacheKey] = cached.cachedAt
            saveCacheMetadata(metadata)
        }
    }
}
