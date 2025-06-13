import Foundation
@testable import TrackRat

struct TrainTestData {
    
    static func sampleTrain() -> Train {
        return Train(
            id: 1,
            trainId: "123",
            line: "Northeast Corridor",
            destination: "New York Penn Station",
            departureTime: Date(),
            track: "1",
            status: .onTime,
            delayMinutes: nil,
            stops: sampleStops(),
            predictionData: samplePredictionData(),
            originStationCode: "NP",
            dataSource: "NJTransit",
            consolidatedId: nil,
            originStation: nil,
            dataSources: nil,
            currentPosition: nil,
            trackAssignment: nil,
            statusSummary: nil,
            consolidationMetadata: nil,
            statusV2: nil,
            progress: nil
        )
    }
    
    static func delayedTrain() -> Train {
        return Train(
            id: 2,
            trainId: "456",
            line: "Northeast Corridor",
            destination: "Trenton Transit Center",
            departureTime: Calendar.current.date(byAdding: .minute, value: 15, to: Date()) ?? Date(),
            track: "2",
            status: .delayed,
            delayMinutes: 15,
            stops: nil,
            predictionData: nil,
            originStationCode: "NY",
            dataSource: "NJTransit",
            consolidatedId: nil,
            originStation: nil,
            dataSources: nil,
            currentPosition: nil,
            trackAssignment: nil,
            statusSummary: nil,
            consolidationMetadata: nil,
            statusV2: nil,
            progress: nil
        )
    }
    
    static func boardingTrain() -> Train {
        return Train(
            id: 3,
            trainId: "789",
            line: "Northeast Corridor",
            destination: "Princeton Junction",
            departureTime: Date(),
            track: "3",
            status: .boarding,
            delayMinutes: nil,
            stops: nil,
            predictionData: nil,
            originStationCode: "NP",
            dataSource: "NJTransit",
            consolidatedId: nil,
            originStation: nil,
            dataSources: nil,
            currentPosition: nil,
            trackAssignment: nil,
            statusSummary: nil,
            consolidationMetadata: nil,
            statusV2: nil,
            progress: nil
        )
    }
    
    static func sampleStops() -> [Stop] {
        return [
            Stop(
                stationCode: "NP",
                stationName: "Newark Penn Station",
                scheduledTime: Date(),
                departureTime: Date(),
                pickupOnly: false,
                dropoffOnly: false,
                departed: false,
                departedConfirmedBy: nil,
                stopStatus: "Scheduled",
                platform: "1"
            ),
            Stop(
                stationCode: "NY", 
                stationName: "New York Penn Station",
                scheduledTime: Calendar.current.date(byAdding: .minute, value: 20, to: Date()) ?? Date(),
                departureTime: Calendar.current.date(byAdding: .minute, value: 20, to: Date()) ?? Date(),
                pickupOnly: false,
                dropoffOnly: false,
                departed: false,
                departedConfirmedBy: nil,
                stopStatus: "Scheduled",
                platform: "1"
            )
        ]
    }
    
    static func samplePredictionData() -> PredictionData {
        return PredictionData(
            trackProbabilities: [
                "1": 0.85,
                "2": 0.10,
                "3": 0.05
            ]
        )
    }
    
    static func sampleTrainList() -> [Train] {
        return [
            sampleTrain(),
            delayedTrain(),
            boardingTrain()
        ]
    }
    
    // JSON string for testing API responses
    static let sampleTrainJSON = """
    {
        "id": 1,
        "train_id": "123",
        "line": "Northeast Corridor",
        "destination": "New York Penn Station",
        "departure_time": "2024-01-01T10:00:00",
        "track": "1",
        "status": "ON_TIME",
        "delay_minutes": null,
        "origin_station_code": "NP",
        "data_source": "NJTransit"
    }
    """
}