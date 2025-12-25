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

    /// Generates a unique cache key for a train based on lookup parameters
    func generateCacheKey(
        trainId: String? = nil,
        trainNumber: String? = nil,
        date: Date? = nil,
        fromStation: String? = nil
    ) -> String {
        var components: [String] = []

        if let trainId = trainId {
            components.append("id:\(trainId)")
        }
        if let trainNumber = trainNumber {
            components.append("num:\(trainNumber)")
        }

        let dateString = date?.formatted(.iso8601.year().month().day()) ?? "today"
        components.append("date:\(dateString)")

        if let fromStation = fromStation {
            components.append("from:\(fromStation)")
        }

        return components.joined(separator: "|")
    }

    // MARK: - Retrieval

    /// Retrieves cached train details if available and not expired
    func getCachedTrain(
        trainId: String? = nil,
        trainNumber: String? = nil,
        date: Date? = nil,
        fromStation: String? = nil
    ) -> TrainV2? {
        let cacheKey = generateCacheKey(
            trainId: trainId,
            trainNumber: trainNumber,
            date: date,
            fromStation: fromStation
        )

        // Check in-memory cache first (fastest)
        if let cached = memoryCache[cacheKey] {
            if !cached.isExpired {
                print("✅ Cache HIT (memory): \(cacheKey) - age: \(cached.ageSeconds)s")
                // Update LRU access order
                updateAccessOrder(for: cacheKey)
                return cached.train
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
                return cached.train
            } else {
                print("⏰ Cache EXPIRED (persistent): \(cacheKey) - age: \(cached.ageSeconds)s")
                userDefaults.removeObject(forKey: persistentKey)
            }
        }

        print("❌ Cache MISS: \(cacheKey)")
        return nil
    }

    /// Returns the age of the cache in seconds, or nil if not cached
    /// PERFORMANCE: Used to determine if we should skip background refresh on cache hit
    func getCacheAge(
        trainId: String? = nil,
        trainNumber: String? = nil,
        date: Date? = nil,
        fromStation: String? = nil
    ) -> TimeInterval? {
        let cacheKey = generateCacheKey(
            trainId: trainId,
            trainNumber: trainNumber,
            date: date,
            fromStation: fromStation
        )

        // Check in-memory cache first
        if let cached = memoryCache[cacheKey], !cached.isExpired {
            return TimeInterval(cached.ageSeconds)
        }

        // Check persistent cache
        let persistentKey = cacheKeyPrefix + cacheKey
        if let data = userDefaults.data(forKey: persistentKey),
           let cached = try? JSONDecoder().decode(CachedTrain.self, from: data),
           !cached.isExpired {
            return TimeInterval(cached.ageSeconds)
        }

        return nil
    }

    // MARK: - Storage

    /// Stores train details in both in-memory and persistent cache
    func cacheTrain(
        _ train: TrainV2,
        trainId: String? = nil,
        trainNumber: String? = nil,
        date: Date? = nil,
        fromStation: String? = nil
    ) {
        let cacheKey = generateCacheKey(
            trainId: trainId,
            trainNumber: trainNumber,
            date: date,
            fromStation: fromStation
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

    /// Clears all cached train data
    func clearAllCache() {
        memoryCache.removeAll()
        memoryCacheAccessOrder.removeAll()

        let metadata = getCacheMetadata()
        for cacheKey in metadata.keys.keys {
            let persistentKey = cacheKeyPrefix + cacheKey
            userDefaults.removeObject(forKey: persistentKey)
        }

        userDefaults.removeObject(forKey: cacheMetadataKey)
        print("🗑️ Cleared all train cache")
    }

    /// Removes cache for a specific train
    func clearCache(
        trainId: String? = nil,
        trainNumber: String? = nil,
        date: Date? = nil,
        fromStation: String? = nil
    ) {
        let cacheKey = generateCacheKey(
            trainId: trainId,
            trainNumber: trainNumber,
            date: date,
            fromStation: fromStation
        )

        memoryCache.removeValue(forKey: cacheKey)
        memoryCacheAccessOrder.removeAll { $0 == cacheKey }

        let persistentKey = cacheKeyPrefix + cacheKey
        userDefaults.removeObject(forKey: persistentKey)

        var metadata = getCacheMetadata()
        metadata.keys.removeValue(forKey: cacheKey)
        saveCacheMetadata(metadata)

        print("🗑️ Cleared cache: \(cacheKey)")
    }

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

    // MARK: - Debug Helpers

    /// Returns cache statistics for debugging
    func getCacheStats() -> String {
        let metadata = getCacheMetadata()
        let memoryCount = memoryCache.count
        let persistentCount = metadata.keys.count

        return """
        📊 Cache Stats:
        - Memory cache: \(memoryCount) entries
        - Persistent cache: \(persistentCount) entries
        - Max age: \(Int(maxCacheAge))s
        """
    }
}
