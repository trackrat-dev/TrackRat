import Foundation

/// Service for fetching ML-based track predictions from the backend
class DynamicTrackPredictionService {
    static let shared = DynamicTrackPredictionService()
    
    private struct CachedPrediction {
        let data: PredictionData
        let timestamp: Date
        
        var isExpired: Bool {
            // Cache for 5 minutes
            Date().timeIntervalSince(timestamp) > 300
        }
    }
    
    // Cache predictions to avoid repeated API calls
    private var cache: [String: CachedPrediction] = [:]
    private let cacheQueue = DispatchQueue(label: "trackprediction.cache", attributes: .concurrent)
    
    private init() {}
    
    /// Get ML-based track prediction for a train
    /// - Parameter train: The train to get predictions for
    /// - Returns: PredictionData if available, nil otherwise
    func getPrediction(for train: TrainV2) async -> PredictionData? {
        // Only support NY Penn Station initially
        guard train.originStationCode == "NY" else {
            // Fall back to static predictions for other stations
            return StaticTrackDistributionService.shared.getPredictionData(for: train)
        }
        
        // Check if we already have a track assigned
        if train.track != nil {
            return nil
        }
        
        // Check cache first
        let cacheKey = getCacheKey(for: train)
        if let cached = getCachedPrediction(key: cacheKey) {
            return cached
        }
        
        do {
            // Extract journey date from scheduled departure
            guard let scheduledDeparture = train.scheduledDeparture else {
                print("No scheduled departure for train \(train.trainId)")
                return fallbackToStatic(for: train)
            }
            
            // Call ML prediction endpoint
            let prediction = try await APIService.shared.fetchMLTrackPrediction(
                stationCode: train.originStationCode ?? "NY",
                trainId: train.trainId,
                journeyDate: scheduledDeparture
            )
            
            // Convert to PredictionData format
            let predictionData = convertToPredictionData(prediction)
            
            // Cache the result
            cachePrediction(predictionData, key: cacheKey)
            
            return predictionData
            
        } catch {
            print("ML track prediction failed: \(error)")
            // Fall back to static predictions on error
            return fallbackToStatic(for: train)
        }
    }
    
    /// Check if predictions should be shown for a train
    func shouldShowPredictions(for train: TrainV2) -> Bool {
        // Show predictions if:
        // 1. Train originates from NY Penn
        // 2. No track assigned yet
        return train.originStationCode == "NY" && train.track == nil
    }
    
    // MARK: - Private Methods
    
    private func getCacheKey(for train: TrainV2) -> String {
        let date = train.scheduledDeparture ?? Date()
        let dateString = ISO8601DateFormatter().string(from: date)
        return "\(train.trainId)_\(dateString)"
    }
    
    private func getCachedPrediction(key: String) -> PredictionData? {
        return cacheQueue.sync {
            guard let cached = cache[key], !cached.isExpired else {
                return nil
            }
            return cached.data
        }
    }
    
    private func cachePrediction(_ data: PredictionData, key: String) {
        cacheQueue.async(flags: .barrier) {
            self.cache[key] = CachedPrediction(
                data: data,
                timestamp: Date()
            )
            
            // Clean up old cache entries
            self.cleanupCache()
        }
    }
    
    private func cleanupCache() {
        // Remove expired entries
        let now = Date()
        cache = cache.filter { _, value in
            !value.isExpired
        }
        
        // Keep only last 100 entries if cache grows too large
        if cache.count > 100 {
            let sortedKeys = cache.keys.sorted { key1, key2 in
                (cache[key1]?.timestamp ?? Date.distantPast) >
                (cache[key2]?.timestamp ?? Date.distantPast)
            }
            
            let keysToKeep = Set(sortedKeys.prefix(100))
            cache = cache.filter { keysToKeep.contains($0.key) }
        }
    }
    
    private func convertToPredictionData(_ mlPrediction: MLTrackPredictionResponse) -> PredictionData {
        // Convert ML response to PredictionData format used by iOS app
        return PredictionData(
            trackProbabilities: mlPrediction.trackProbabilities
        )
    }
    
    private func fallbackToStatic(for train: TrainV2) -> PredictionData? {
        // Fall back to static predictions
        return StaticTrackDistributionService.shared.getPredictionData(for: train)
    }
}

// MARK: - ML Prediction Response Model

struct MLTrackPredictionResponse: Codable {
    let trackProbabilities: [String: Double]
    let primaryPrediction: String
    let confidence: Double
    let top3: [String]
    let modelVersion: String
    let stationCode: String
    let trainId: String
    let featuresUsed: MLPredictionFeatures?
    
    enum CodingKeys: String, CodingKey {
        case trackProbabilities = "track_probabilities"
        case primaryPrediction = "primary_prediction"
        case confidence
        case top3 = "top_3"
        case modelVersion = "model_version"
        case stationCode = "station_code"
        case trainId = "train_id"
        case featuresUsed = "features_used"
    }
}

struct MLPredictionFeatures: Codable {
    let hourOfDay: Int
    let dayOfWeek: Int
    let isAmtrak: Int
    let lineCode: String
    let destination: String
    let avgMinutesSinceTrackUsed: Double
    let avgMinutesSincePlatformUsed: Double
    
    enum CodingKeys: String, CodingKey {
        case hourOfDay = "hour_of_day"
        case dayOfWeek = "day_of_week"
        case isAmtrak = "is_amtrak"
        case lineCode = "line_code"
        case destination
        case avgMinutesSinceTrackUsed = "avg_minutes_since_track_used"
        case avgMinutesSincePlatformUsed = "avg_minutes_since_platform_used"
    }
}