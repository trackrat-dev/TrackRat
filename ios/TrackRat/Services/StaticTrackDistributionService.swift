import Foundation

/// Temporary service providing static track probability distributions for NY Penn Station
/// This service will be removed once dynamic track predictions are implemented in the backend
class StaticTrackDistributionService {
    static let shared = StaticTrackDistributionService()
    
    private init() {}
    
    /// NJ Transit track distribution for NY Penn Station
    private let njTransitDistribution: [String: Double] = [
        "1": 0.1178526841,
        "2": 0.1458177278,
        "3": 0.1440699126,
        "4": 0.129588015,
        "5": 0.001997503121,
        "6": 0.02172284644,
        "7": 0.05293383271,
        "8": 0.045443196,
        "9": 0.0709113608,
        "10": 0.07965043695,
        "11": 0.06392009988,
        "12": 0.04968789014,
        "13": 0.06392009988,
        "14": 0.008739076155,
        "15": 0.002746566792,
        "16": 0.0002496878901,
        "17": 0.0002496878901,
        "18": 0.0002496878901,
        "19": 0.0002496878901
    ]
    
    /// Amtrak track distribution for NY Penn Station
    private let amtrakDistribution: [String: Double] = [
        "1": 0.0004355400697,
        "2": 0.0004355400697,
        "3": 0.0004355400697,
        "4": 0.0004355400697,
        "5": 0.07970383275,
        "6": 0.06968641115,
        "7": 0.06445993031,
        "8": 0.09494773519,
        "9": 0.07317073171,
        "10": 0.07099303136,
        "11": 0.08144599303,
        "12": 0.1010452962,
        "13": 0.08449477352,
        "14": 0.1912020906,
        "15": 0.08144599303,
        "16": 0.003919860627,
        "17": 0.0004355400697,
        "18": 0.0008710801394,
        "19": 0.0004355400697
    ]
    
    /// Generate prediction data for a train, only for NY Penn Station departures
    /// Returns nil for all other stations
    func getPredictionData(for train: TrainV2) -> PredictionData? {
        // Only provide predictions for NY Penn Station (code "NY")
        guard train.originStationCode == "NY" else {
            return nil
        }
        
        // Determine if train is Amtrak or NJ Transit based on train ID
        let isAmtrak = train.trainId.uppercased().hasPrefix("A")
        
        let distribution = isAmtrak ? amtrakDistribution : njTransitDistribution
        
        return PredictionData(trackProbabilities: distribution)
    }
    
    /// Check if predictions should be shown for a given train
    func shouldShowPredictions(for train: TrainV2) -> Bool {
        return train.originStationCode == "NY" && train.track == nil
    }
}