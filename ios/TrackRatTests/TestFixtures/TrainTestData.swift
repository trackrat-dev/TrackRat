import Foundation
@testable import TrackRat

// MARK: - Test Extensions

extension Stop {
    static func mock(
        stationName: String = "Mock Station",
        stationCode: String = "MSK",
        scheduledTime: Date? = Date(),
        departureTime: Date? = Date(),
        actualTime: Date? = nil,
        departed: Bool? = false,
        stopStatus: String? = "ON_TIME"
    ) -> Stop {
        return Stop(
            stationCode: stationCode,
            stationName: stationName,
            scheduledArrival: scheduledTime,
            scheduledDeparture: departureTime ?? scheduledTime,
            actualArrival: actualTime,
            actualDeparture: nil,
            estimatedArrival: nil,
            pickupOnly: nil,
            dropoffOnly: nil,
            departed: departed,
            departedConfirmedBy: nil,
            stopStatus: stopStatus,
            platform: nil
        )
    }
}

struct TrainTestData {

    // MARK: - Basic Train Creation

    static func sampleTrain() -> Train {
        return Train(
            id: 1,
            trainId: "3949",
            line: "Northeast Corridor",
            destination: "New York Penn Station",
            departureTime: Date(),
            track: "12",
            status: .onTime,
            delayMinutes: 0,
            stops: sampleStops(),
            predictionData: nil,
            originStationCode: "NP",
            dataSource: "NJT"
        )
    }

    static func delayedTrain() -> Train {
        return Train(
            id: 2,
            trainId: "3951",
            line: "Northeast Corridor",
            destination: "New York Penn Station",
            departureTime: Date().addingTimeInterval(900), // 15 minutes delay
            track: "12",
            status: .delayed,
            delayMinutes: 15,
            stops: delayedStops(),
            predictionData: nil,
            originStationCode: "NP",
            dataSource: "NJT"
        )
    }

    static func cancelledTrain() -> Train {
        return Train(
            id: 3,
            trainId: "3953",
            line: "Northeast Corridor",
            destination: "New York Penn Station",
            departureTime: Date(),
            track: nil,
            status: .cancelled,
            delayMinutes: nil,
            stops: nil,
            predictionData: nil,
            originStationCode: "NP",
            dataSource: "NJT"
        )
    }

    static func boardingTrain() -> Train {
        return Train(
            id: 4,
            trainId: "3955",
            line: "Northeast Corridor",
            destination: "New York Penn Station",
            departureTime: Date().addingTimeInterval(300), // Leaves in 5 minutes
            track: "12",
            status: .boarding,
            delayMinutes: 0,
            stops: boardingStops(),
            predictionData: nil,
            originStationCode: "NP",
            dataSource: "NJT"
        )
    }

    // MARK: - Train with Different Statuses

    static func departedTrain() -> Train {
        return Train(
            id: 5,
            trainId: "3957",
            line: "Northeast Corridor",
            destination: "New York Penn Station",
            departureTime: Date().addingTimeInterval(-300), // Left 5 minutes ago
            track: "12",
            status: .departed,
            delayMinutes: 0,
            stops: departedStops(),
            predictionData: nil,
            originStationCode: "NP",
            dataSource: "NJT"
        )
    }

    // MARK: - Trains with Different Lines

    static func raritanValleyTrain() -> Train {
        return Train(
            id: 6,
            trainId: "5401",
            line: "Raritan Valley Line",
            destination: "New York Penn Station",
            departureTime: Date().addingTimeInterval(600),
            track: "7",
            status: .onTime,
            delayMinutes: 0,
            stops: raritanValleyStops(),
            predictionData: nil,
            originStationCode: "NWB",
            dataSource: "NJT"
        )
    }

    static func northJerseyCoastTrain() -> Train {
        return Train(
            id: 7,
            trainId: "3801",
            line: "North Jersey Coast Line",
            destination: "New York Penn Station",
            departureTime: Date().addingTimeInterval(900),
            track: "9",
            status: .onTime,
            delayMinutes: 0,
            stops: coastLineStops(),
            predictionData: nil,
            originStationCode: "LBR",
            dataSource: "NJT"
        )
    }

    // MARK: - Stop Collections

    static func sampleStops() -> [Stop] {
        return [
            Stop.mock(
                stationName: "Newark Penn Station",
                stationCode: "NP",
                scheduledTime: Date(),
                departureTime: Date(),
                departed: false,
                stopStatus: "Scheduled"
            ),
            Stop.mock(
                stationName: "New York Penn Station",
                stationCode: "NY",
                scheduledTime: Calendar.current.date(byAdding: .minute, value: 20, to: Date()) ?? Date(),
                departureTime: Calendar.current.date(byAdding: .minute, value: 20, to: Date()) ?? Date(),
                departed: false,
                stopStatus: "Scheduled"
            )
        ]
    }

    static func consolidatedStops() -> [Stop] {
        let baseTime = Date()
        return [
            Stop.mock(
                stationName: "New York Penn Station",
                stationCode: "NY",
                scheduledTime: baseTime,
                departureTime: baseTime,
                departed: true,
                stopStatus: "DEPARTED"
            ),
            Stop.mock(
                stationName: "Newark Penn Station",
                stationCode: "NP",
                scheduledTime: baseTime.addingTimeInterval(600),
                departureTime: baseTime.addingTimeInterval(600),
                departed: false,
                stopStatus: "ON_TIME"
            ),
            Stop.mock(
                stationName: "Princeton Junction",
                stationCode: "PJC",
                scheduledTime: baseTime.addingTimeInterval(1200),
                departureTime: baseTime.addingTimeInterval(1200),
                departed: false,
                stopStatus: "ON_TIME"
            ),
            Stop.mock(
                stationName: "Princeton",
                stationCode: "PRC",
                scheduledTime: baseTime.addingTimeInterval(1500),
                departureTime: nil,
                departed: false,
                stopStatus: "ON_TIME"
            ),
            Stop.mock(
                stationName: "Trenton",
                stationCode: "TRE",
                scheduledTime: baseTime.addingTimeInterval(1800),
                departureTime: nil,
                departed: false,
                stopStatus: "ON_TIME"
            )
        ]
    }

    static func multiSourceStops() -> [Stop] {
        let baseTime = Date()
        return [
            Stop.mock(
                stationName: "Washington",
                stationCode: "WAS",
                scheduledTime: baseTime.addingTimeInterval(-3600),
                departureTime: baseTime.addingTimeInterval(-3600),
                departed: true,
                stopStatus: "DEPARTED"
            ),
            Stop.mock(
                stationName: "Baltimore",
                stationCode: "BAL",
                scheduledTime: baseTime.addingTimeInterval(-2700),
                departureTime: baseTime.addingTimeInterval(-2700),
                departed: true,
                stopStatus: "DEPARTED"
            ),
            Stop.mock(
                stationName: "Philadelphia",
                stationCode: "PHL",
                scheduledTime: baseTime.addingTimeInterval(-1800),
                departureTime: baseTime.addingTimeInterval(-1800),
                departed: true,
                stopStatus: "DEPARTED"
            ),
            Stop.mock(
                stationName: "Trenton",
                stationCode: "TRE",
                scheduledTime: baseTime.addingTimeInterval(-900),
                departureTime: baseTime.addingTimeInterval(-900),
                departed: true,
                stopStatus: "DEPARTED"
            ),
            Stop.mock(
                stationName: "New York Penn Station",
                stationCode: "NY",
                scheduledTime: baseTime,
                departureTime: nil,
                departed: false,
                stopStatus: "ON_TIME"
            )
        ]
    }

    // MARK: - Status-Specific Stops

    static func delayedStops() -> [Stop] {
        return [
            Stop.mock(
                stationName: "Newark Penn Station",
                stationCode: "NP",
                scheduledTime: Date(),
                departureTime: Date().addingTimeInterval(900), // 15 minutes delay
                departed: false,
                stopStatus: "DELAYED"
            ),
            Stop.mock(
                stationName: "New York Penn Station",
                stationCode: "NY",
                scheduledTime: Calendar.current.date(byAdding: .minute, value: 20, to: Date()) ?? Date(),
                departureTime: Calendar.current.date(byAdding: .minute, value: 35, to: Date()) ?? Date(), // Propagated delay
                departed: false,
                stopStatus: "DELAYED"
            )
        ]
    }

    static func boardingStops() -> [Stop] {
        return [
            Stop.mock(
                stationName: "Newark Penn Station",
                stationCode: "NP",
                scheduledTime: Date(),
                departureTime: Date().addingTimeInterval(300), // Leaves in 5 minutes
                departed: false,
                stopStatus: "BOARDING"
            ),
            Stop.mock(
                stationName: "New York Penn Station",
                stationCode: "NY",
                scheduledTime: Calendar.current.date(byAdding: .minute, value: 25, to: Date()) ?? Date(),
                departureTime: Calendar.current.date(byAdding: .minute, value: 25, to: Date()) ?? Date(),
                departed: false,
                stopStatus: "ON_TIME"
            )
        ]
    }

    static func departedStops() -> [Stop] {
        return [
            Stop.mock(
                stationName: "Newark Penn Station",
                stationCode: "NP",
                scheduledTime: Date().addingTimeInterval(-300),
                departureTime: Date().addingTimeInterval(-300), // Left 5 minutes ago
                departed: true,
                stopStatus: "DEPARTED"
            ),
            Stop.mock(
                stationName: "New York Penn Station",
                stationCode: "NY",
                scheduledTime: Date().addingTimeInterval(900),
                departureTime: Date().addingTimeInterval(900),
                departed: false,
                stopStatus: "ON_TIME"
            )
        ]
    }

    // MARK: - Line-Specific Stops

    static func raritanValleyStops() -> [Stop] {
        return [
            Stop.mock(
                stationName: "New Brunswick",
                stationCode: "NWB",
                scheduledTime: Date(),
                departureTime: Date().addingTimeInterval(600),
                departed: false,
                stopStatus: "ON_TIME"
            ),
            Stop.mock(
                stationName: "Newark Penn Station",
                stationCode: "NP",
                scheduledTime: Date().addingTimeInterval(1500),
                departureTime: Date().addingTimeInterval(1500),
                departed: false,
                stopStatus: "ON_TIME"
            ),
            Stop.mock(
                stationName: "New York Penn Station",
                stationCode: "NY",
                scheduledTime: Date().addingTimeInterval(2100),
                departureTime: nil,
                departed: false,
                stopStatus: "ON_TIME"
            )
        ]
    }

    static func coastLineStops() -> [Stop] {
        return [
            Stop.mock(
                stationName: "Long Branch",
                stationCode: "LBR",
                scheduledTime: Date(),
                departureTime: Date().addingTimeInterval(900),
                departed: false,
                stopStatus: "ON_TIME"
            ),
            Stop.mock(
                stationName: "Red Bank",
                stationCode: "RBK",
                scheduledTime: Date().addingTimeInterval(600),
                departureTime: Date().addingTimeInterval(600),
                departed: false,
                stopStatus: "ON_TIME"
            ),
            Stop.mock(
                stationName: "Rahway",
                stationCode: "RAH",
                scheduledTime: Date().addingTimeInterval(2400),
                departureTime: Date().addingTimeInterval(2400),
                departed: false,
                stopStatus: "ON_TIME"
            ),
            Stop.mock(
                stationName: "Newark Penn Station",
                stationCode: "NP",
                scheduledTime: Date().addingTimeInterval(3000),
                departureTime: Date().addingTimeInterval(3000),
                departed: false,
                stopStatus: "ON_TIME"
            ),
            Stop.mock(
                stationName: "New York Penn Station",
                stationCode: "NY",
                scheduledTime: Date().addingTimeInterval(3600),
                departureTime: nil,
                departed: false,
                stopStatus: "ON_TIME"
            )
        ]
    }

    // MARK: - Test Utility Functions

    static func createTrainArray(count: Int = 5) -> [Train] {
        var trains: [Train] = []
        let baseTime = Date()

        for i in 0..<count {
            let train = Train(
                id: i + 1,
                trainId: "\(3900 + i * 2)",
                line: "Northeast Corridor",
                destination: "New York Penn Station",
                departureTime: baseTime.addingTimeInterval(TimeInterval(i * 600)), // Every 10 minutes
                track: "\(10 + i)",
                status: i == 0 ? .boarding : .onTime,
                delayMinutes: i == 2 ? 5 : 0, // One delayed train
                stops: i < 2 ? sampleStops() : nil,
                predictionData: nil,
                originStationCode: "NP",
                dataSource: "NJT"
            )
            trains.append(train)
        }

        return trains
    }

    static func createMockPredictionData() -> PredictionData {
        return PredictionData(trackProbabilities: [
            "11": 0.85,
            "12": 0.15
        ])
    }

    // MARK: - Test Constants

    static let testStationCode = "NP"
    static let testDestination = "New York Penn Station"
    static let testLine = "Northeast Corridor"
    static let testTrackPrediction = "11"

    // MARK: - JSON Test Data

    static let sampleTrainJSON = """
    {
        "id": 123,
        "train_id": "123",
        "line": "Northeast Corridor",
        "destination": "New York Penn Station",
        "departure_time": "2024-01-15T10:00:00Z",
        "track": "1",
        "status": "ON_TIME",
        "delay_minutes": null,
        "stops": [],
        "prediction_data": null,
        "origin_station_code": "NP",
        "data_source": "NJT"
    }
    """
}

// MARK: - Helper Extensions for Testing

extension Date {
    static func testDate(minutesFromNow: Int) -> Date {
        return Calendar.current.date(byAdding: .minute, value: minutesFromNow, to: Date()) ?? Date()
    }
}

