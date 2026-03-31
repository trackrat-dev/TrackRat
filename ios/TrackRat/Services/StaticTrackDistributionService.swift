import Foundation

/// Dynamic service providing track probability predictions for supported stations
/// Uses platform predictions from the backend and converts them to track probabilities
class StaticTrackDistributionService {
    static let shared = StaticTrackDistributionService()

    /// Stations that support track predictions (backend has predictions_enabled: true for these)
    /// The backend controls the actual list - this is for early filtering to avoid unnecessary API calls
    static let supportedStations: Set<String> = ["NY", "NP", "ND", "HB", "MP", "ST", "TR", "PH", "DV", "DN", "PL", "LB", "JA", "JAM", "GCT"]

    private init() {}

    /// Generate ML-based prediction data for a train
    /// Returns nil for unsupported stations
    func getPredictionData(for train: TrainV2) -> PredictionData? {
        // Note: This is now a synchronous method but the actual prediction is async
        // For synchronous access, return nil - UI should use async methods
        return nil
    }

    /// Check if predictions should be shown for a given train
    func shouldShowPredictions(for train: TrainV2) -> Bool {
        // Show predictions if:
        // 1. Train originates from a supported station
        // 2. No track assigned yet
        let stationCode = train.originStationCode
        return Self.supportedStations.contains(stationCode) && train.track == nil
    }

    /// Get ML-based track prediction for a train
    /// - Parameters:
    ///   - train: The train to get predictions for
    ///   - excludingOccupiedTracks: Ignored - backend already considers track usage
    /// - Returns: PredictionData if available, nil otherwise
    func getAdjustedPredictionData(for train: TrainV2, excludingOccupiedTracks: Bool = true) async -> PredictionData? {
        print("🔍 [StaticTrackDistribution] Getting predictions for train \(train.trainId)")
        print("   - Origin: \(train.originStationCode)")
        print("   - Track: \(train.track ?? "nil")")

        // Only support configured stations
        let stationCode = train.originStationCode
        guard Self.supportedStations.contains(stationCode) else {
            print("❌ [StaticTrackDistribution] Station not supported - no predictions")
            return nil
        }

        // Don't show predictions if track already assigned
        if train.track != nil {
            print("❌ [StaticTrackDistribution] Track already assigned: \(train.track!) - no predictions")
            return nil
        }

        do {
            // Extract journey date from scheduled departure
            guard let scheduledDeparture = train.departure.scheduledTime else {
                print("❌ [StaticTrackDistribution] No scheduled departure for train \(train.trainId)")
                return nil
            }

            print("📡 [StaticTrackDistribution] Calling API for predictions...")
            print("   - Station: \(train.originStationCode)")
            print("   - Train ID: \(train.trainId)")
            print("   - Journey Date: \(scheduledDeparture)")

            // Call ML platform prediction endpoint
            let platformPrediction = try await APIService.shared.getPlatformPrediction(
                stationCode: train.originStationCode,
                trainId: train.trainId,
                journeyDate: scheduledDeparture
            )

            print("✅ [StaticTrackDistribution] API returned platform predictions")
            print("   - Primary: \(platformPrediction.primaryPrediction)")
            print("   - Confidence: \(platformPrediction.confidence)")
            print("   - Top 3: \(platformPrediction.top3)")

            // Convert platform predictions to track predictions
            let trackProbabilities = platformPrediction.convertToTrackProbabilities()

            print("🎯 [StaticTrackDistribution] Converted to \(trackProbabilities.count) track probabilities")
            let sortedTracks = trackProbabilities.sorted { $0.value > $1.value }
            for (track, probability) in sortedTracks.prefix(3) {
                print("   - Track \(track): \(String(format: "%.1f%%", probability * 100))")
            }

            return PredictionData(trackProbabilities: trackProbabilities)

        } catch {
            print("❌ [StaticTrackDistribution] ML platform prediction failed:")
            print("   Error: \(error)")
            print("   Localized: \(error.localizedDescription)")
            // If API fails, don't show predictions
            return nil
        }
    }
}