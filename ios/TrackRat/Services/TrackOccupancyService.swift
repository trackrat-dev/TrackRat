import Foundation

class TrackOccupancyService {
    static let shared = TrackOccupancyService()
    
    private struct CachedOccupancy {
        let tracks: Set<String>
        let fetchedAt: Date
        
        var isExpired: Bool {
            Date().timeIntervalSince(fetchedAt) > 60 // 1 minute
        }
    }
    
    private var cache: [String: CachedOccupancy] = [:]
    private let cacheQueue = DispatchQueue(label: "trackoccupancy.cache", qos: .userInitiated)
    
    private init() {}
    
    func getOccupiedTracks(for stationCode: String) async throws -> Set<String> {
        // Check cache first
        if let cached = getCachedTracks(for: stationCode), !cached.isExpired {
            return cached.tracks
        }
        
        // Fetch fresh data
        let response = try await APIService.shared.fetchOccupiedTracks(stationCode: stationCode)
        
        // Cache the result
        let occupiedTracks = Set(response.occupiedTracks)
        cacheQueue.async { [weak self] in
            self?.cache[stationCode] = CachedOccupancy(
                tracks: occupiedTracks,
                fetchedAt: Date()
            )
        }
        
        return occupiedTracks
    }
    
    private func getCachedTracks(for stationCode: String) -> CachedOccupancy? {
        return cacheQueue.sync {
            return cache[stationCode]
        }
    }
    
    func clearCache() {
        cacheQueue.async { [weak self] in
            self?.cache.removeAll()
        }
    }
}