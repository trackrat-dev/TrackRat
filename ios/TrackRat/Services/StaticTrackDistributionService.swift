import Foundation

/// Dynamic service providing ML-based track probability predictions for NY Penn Station
/// Uses platform predictions from the backend and converts them to track probabilities
class StaticTrackDistributionService {
    static let shared = StaticTrackDistributionService()
    
    private init() {}
    
    /// Generate ML-based prediction data for a train, only for NY Penn Station departures
    /// Returns nil for all other stations
    func getPredictionData(for train: TrainV2) -> PredictionData? {
        // Note: This is now a synchronous method but the actual prediction is async
        // For synchronous access, return nil - UI should use async methods
        return nil
    }
    
    /// Check if predictions should be shown for a given train
    func shouldShowPredictions(for train: TrainV2) -> Bool {
        // Show predictions if:
        // 1. Train originates from NY Penn
        // 2. No track assigned yet
        return train.originStationCode == "NY" && train.track == nil
    }
    
    /// Get ML-based track prediction for a train
    /// - Parameters:
    ///   - train: The train to get predictions for
    ///   - excludingOccupiedTracks: Ignored - ML model already considers track usage
    /// - Returns: PredictionData if available, nil otherwise
    func getAdjustedPredictionData(for train: TrainV2, excludingOccupiedTracks: Bool = true) async -> PredictionData? {
        // Only support NY Penn Station
        guard train.originStationCode == "NY" else {
            return nil
        }
        
        // Don't show predictions if track already assigned
        if train.track != nil {
            return nil
        }
        
        do {
            // Extract journey date from scheduled departure
            guard let scheduledDeparture = train.departure.scheduledTime else {
                print("No scheduled departure for train \(train.trainId)")
                return nil
            }
            
            // Call ML platform prediction endpoint
            let platformPrediction = try await APIService.shared.getPlatformPrediction(
                stationCode: train.originStationCode ?? "NY",
                trainId: train.trainId,
                journeyDate: scheduledDeparture
            )
            
            // Convert platform predictions to track predictions
            let trackProbabilities = platformPrediction.convertToTrackProbabilities()
            
            return PredictionData(trackProbabilities: trackProbabilities)
            
        } catch {
            print("ML platform prediction failed: \(error)")
            // If API fails, don't show predictions
            return nil
        }
    }
}