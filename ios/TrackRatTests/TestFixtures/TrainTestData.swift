import Foundation
@testable import TrackRat

struct TrainTestData {
    
    // MARK: - Basic Train Objects
    
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
    
    static func consolidatedTrain() -> Train {
        return Train(
            id: 1001,
            trainId: "2150",
            line: "Northeast Corridor",
            destination: "Washington Union Station",
            departureTime: Date(),
            track: nil, // Will use trackAssignment
            status: .onTime,
            delayMinutes: nil,
            stops: consolidatedStops(),
            predictionData: samplePredictionData(),
            originStationCode: "NY",
            dataSource: "Amtrak",
            consolidatedId: "amtrak_2150_njtransit_456",
            originStation: sampleOriginStation(),
            dataSources: sampleDataSources(),
            currentPosition: sampleCurrentPosition(),
            trackAssignment: sampleTrackAssignment(),
            statusSummary: sampleStatusSummary(),
            consolidationMetadata: sampleConsolidationMetadata(),
            statusV2: sampleStatusV2(),
            progress: sampleProgress()
        )
    }
    
    static func enhancedTrain() -> Train {
        return Train(
            id: 2001,
            trainId: "3945",
            line: "Northeast Corridor",
            destination: "Boston South",
            departureTime: Date().addingTimeInterval(-1800), // Departed 30 minutes ago
            track: "11",
            status: .departed,
            delayMinutes: 5,
            stops: enhancedStops(),
            predictionData: samplePredictionData(),
            originStationCode: "NY",
            dataSource: "Amtrak",
            consolidatedId: nil,
            originStation: nil,
            dataSources: nil,
            currentPosition: nil,
            trackAssignment: nil,
            statusSummary: nil,
            consolidationMetadata: nil,
            statusV2: enhancedStatusV2(),
            progress: enhancedProgress()
        )
    }
    
    // MARK: - Stop Data
    
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
    
    static func consolidatedStops() -> [Stop] {
        let baseTime = Date()
        return [
            Stop(
                stationCode: "NY",
                stationName: "New York Penn Station",
                scheduledTime: baseTime,
                departureTime: baseTime,
                pickupOnly: false,
                dropoffOnly: false,
                departed: true,
                departedConfirmedBy: ["Amtrak", "NJTransit"],
                stopStatus: "DEPARTED",
                platform: "11"
            ),
            Stop(
                stationCode: "NP",
                stationName: "Newark Penn Station",
                scheduledTime: baseTime.addingTimeInterval(420), // 7 minutes
                departureTime: baseTime.addingTimeInterval(420),
                pickupOnly: false,
                dropoffOnly: false,
                departed: true,
                departedConfirmedBy: ["NJTransit"],
                stopStatus: "DEPARTED",
                platform: "2"
            ),
            Stop(
                stationCode: "PH",
                stationName: "Philadelphia",
                scheduledTime: baseTime.addingTimeInterval(5400), // 90 minutes
                departureTime: nil,
                pickupOnly: false,
                dropoffOnly: false,
                departed: false,
                departedConfirmedBy: nil,
                stopStatus: "SCHEDULED",
                platform: "12"
            ),
            Stop(
                stationCode: "WS",
                stationName: "Washington Union Station",
                scheduledTime: baseTime.addingTimeInterval(10800), // 3 hours
                departureTime: nil,
                pickupOnly: false,
                dropoffOnly: false,
                departed: false,
                departedConfirmedBy: nil,
                stopStatus: "SCHEDULED",
                platform: "8"
            )
        ]
    }
    
    static func enhancedStops() -> [Stop] {
        let baseTime = Date().addingTimeInterval(-1800) // 30 minutes ago
        return [
            Stop(
                stationCode: "NY",
                stationName: "New York Penn Station",
                scheduledTime: baseTime,
                departureTime: baseTime.addingTimeInterval(300), // 5 minutes late
                pickupOnly: false,
                dropoffOnly: false,
                departed: true,
                departedConfirmedBy: ["Amtrak"],
                stopStatus: "DEPARTED",
                platform: "11"
            ),
            Stop(
                stationCode: "STM",
                stationName: "Stamford",
                scheduledTime: baseTime.addingTimeInterval(2400), // 40 minutes
                departureTime: nil,
                pickupOnly: false,
                dropoffOnly: false,
                departed: false,
                departedConfirmedBy: nil,
                stopStatus: "APPROACHING",
                platform: "3"
            ),
            Stop(
                stationCode: "BOS",
                stationName: "Boston South",
                scheduledTime: baseTime.addingTimeInterval(14400), // 4 hours
                departureTime: nil,
                pickupOnly: false,
                dropoffOnly: false,
                departed: false,
                departedConfirmedBy: nil,
                stopStatus: "SCHEDULED",
                platform: "5"
            )
        ]
    }
    
    // MARK: - Enhanced Data Models
    
    static func sampleOriginStation() -> OriginStation {
        return OriginStation(
            code: "NY",
            name: "New York Penn Station",
            departureTime: Date()
        )
    }
    
    static func sampleDataSources() -> [DataSource] {
        let baseTime = Date()
        return [
            DataSource(
                origin: "NY",
                dataSource: "Amtrak",
                lastUpdate: baseTime,
                status: "ON_TIME",
                track: "11",
                delayMinutes: 0,
                dbId: 12345
            ),
            DataSource(
                origin: "NY",
                dataSource: "NJTransit",
                lastUpdate: baseTime.addingTimeInterval(-60),
                status: "ON_TIME",
                track: "11",
                delayMinutes: 0,
                dbId: 67890
            )
        ]
    }
    
    static func sampleCurrentPosition() -> CurrentPosition {
        return CurrentPosition(
            status: "en_route",
            lastDepartedStation: StationStatus(
                code: "NP",
                name: "Newark Penn Station",
                scheduledDeparture: Date().addingTimeInterval(-420),
                scheduledArrival: Date().addingTimeInterval(-480),
                actualDeparture: Date().addingTimeInterval(-420),
                estimatedArrival: nil,
                distanceMiles: 0.0
            ),
            nextStation: StationStatus(
                code: "PH",
                name: "Philadelphia",
                scheduledDeparture: nil,
                scheduledArrival: Date().addingTimeInterval(4680),
                actualDeparture: nil,
                estimatedArrival: Date().addingTimeInterval(4680),
                distanceMiles: 90.0
            ),
            segmentProgress: 0.15,
            estimatedSpeedMph: 65.0
        )
    }
    
    static func sampleTrackAssignment() -> TrackAssignment {
        return TrackAssignment(
            track: "11",
            assignedAt: Date().addingTimeInterval(-600),
            assignedBy: "Dispatcher",
            source: "Amtrak"
        )
    }
    
    static func sampleStatusSummary() -> StatusSummary {
        return StatusSummary(
            currentStatus: "on time",
            delayMinutes: 0,
            onTimePerformance: "good"
        )
    }
    
    static func sampleConsolidationMetadata() -> ConsolidationMetadata {
        return ConsolidationMetadata(
            sourceCount: 2,
            lastUpdate: Date(),
            confidenceScore: 0.95
        )
    }
    
    static func sampleStatusV2() -> StatusV2 {
        return StatusV2(
            current: "ON_TIME",
            location: "Platform 11",
            updatedAt: Date(),
            confidence: "high",
            source: "Amtrak"
        )
    }
    
    static func enhancedStatusV2() -> StatusV2 {
        return StatusV2(
            current: "EN_ROUTE",
            location: "between Newark Penn Station and Philadelphia",
            updatedAt: Date(),
            confidence: "high",
            source: "Amtrak"
        )
    }
    
    static func sampleProgress() -> TrackRat.TrainProgress {
        return TrainProgress(
            lastDeparted: DepartedStation(
                stationCode: "NP",
                departedAt: Date().addingTimeInterval(-420),
                delayMinutes: 0
            ),
            nextArrival: NextArrival(
                stationCode: "PH",
                scheduledTime: Date().addingTimeInterval(4680),
                estimatedTime: Date().addingTimeInterval(4680),
                minutesAway: 78
            ),
            journeyPercent: 25,
            stopsCompleted: 2,
            totalStops: 4
        )
    }
    
    static func enhancedProgress() -> TrackRat.TrainProgress {
        return TrainProgress(
            lastDeparted: DepartedStation(
                stationCode: "NY",
                departedAt: Date().addingTimeInterval(-1800),
                delayMinutes: 5
            ),
            nextArrival: NextArrival(
                stationCode: "STM",
                scheduledTime: Date().addingTimeInterval(600),
                estimatedTime: Date().addingTimeInterval(900),
                minutesAway: 15
            ),
            journeyPercent: 40,
            stopsCompleted: 1,
            totalStops: 3
        )
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
    
    static func highConfidencePredictionData() -> PredictionData {
        return PredictionData(
            trackProbabilities: [
                "11": 0.95,
                "12": 0.03,
                "13": 0.02
            ]
        )
    }
    
    static func lowConfidencePredictionData() -> PredictionData {
        return PredictionData(
            trackProbabilities: [
                "7": 0.35,
                "8": 0.33,
                "9": 0.32
            ]
        )
    }
    
    // MARK: - Train Collections
    
    static func sampleTrainList() -> [Train] {
        return [
            sampleTrain(),
            delayedTrain(),
            boardingTrain()
        ]
    }
    
    static func enhancedTrainList() -> [Train] {
        return [
            sampleTrain(),
            delayedTrain(),
            boardingTrain(),
            consolidatedTrain(),
            enhancedTrain()
        ]
    }
    
    // MARK: - JSON Test Data
    
    // Legacy format JSON
    static let legacyTrainJSON = """
    {
        "id": 1,
        "train_id": "123",
        "line": "Northeast Corridor",
        "destination": "New York Penn Station",
        "departure_time": "2024-01-01T10:00:00-05:00",
        "track": "1",
        "status": "ON_TIME",
        "delay_minutes": null,
        "origin_station_code": "NP",
        "data_source": "NJTransit",
        "stops": [
            {
                "station_code": "NP",
                "station_name": "Newark Penn Station",
                "scheduled_time": "2024-01-01T10:00:00-05:00",
                "departure_time": "2024-01-01T10:00:00-05:00",
                "departed": false,
                "platform": "1"
            },
            {
                "station_code": "NY",
                "station_name": "New York Penn Station",
                "scheduled_time": "2024-01-01T10:20:00-05:00",
                "departure_time": "2024-01-01T10:20:00-05:00",
                "departed": false,
                "platform": "7"
            }
        ],
        "prediction_data": {
            "track_probabilities": {
                "1": 0.85,
                "2": 0.10,
                "3": 0.05
            }
        }
    }
    """
    
    // Consolidated format JSON
    static let consolidatedTrainJSON = """
    {
        "consolidated_id": "amtrak_2150_njtransit_456",
        "train_id": "2150",
        "line": "Northeast Corridor",
        "destination": "Washington Union Station",
        "origin_station": {
            "code": "NY",
            "name": "New York Penn Station",
            "departure_time": "2024-01-01T10:00:00-05:00"
        },
        "track_assignment": {
            "track": "11",
            "assigned_at": "2024-01-01T09:50:00-05:00",
            "assigned_by": "Dispatcher",
            "source": "Amtrak"
        },
        "status_summary": {
            "current_status": "on time",
            "delay_minutes": 0,
            "on_time_performance": "good"
        },
        "data_sources": [
            {
                "origin": "NY",
                "data_source": "Amtrak",
                "last_update": "2024-01-01T10:00:00-05:00",
                "status": "ON_TIME",
                "track": "11",
                "delay_minutes": 0,
                "db_id": 12345
            },
            {
                "origin": "NY",
                "data_source": "NJTransit",
                "last_update": "2024-01-01T09:59:00-05:00",
                "status": "ON_TIME",
                "track": "11",
                "delay_minutes": 0,
                "db_id": 67890
            }
        ],
        "current_position": {
            "status": "en_route",
            "segment_progress": 0.15,
            "estimated_speed_mph": 65.0
        },
        "consolidation_metadata": {
            "source_count": 2,
            "last_update": "2024-01-01T10:00:00-05:00",
            "confidence_score": 0.95
        }
    }
    """
    
    // Enhanced format with StatusV2 and Progress
    static let enhancedTrainJSON = """
    {
        "id": 2001,
        "train_id": "3945",
        "line": "Northeast Corridor",
        "destination": "Boston South",
        "departure_time": "2024-01-01T09:30:00-05:00",
        "track": "11",
        "status": "DEPARTED",
        "delay_minutes": 5,
        "origin_station_code": "NY",
        "data_source": "Amtrak",
        "status_v2": {
            "current": "EN_ROUTE",
            "location": "between New York Penn Station and Stamford",
            "updated_at": "2024-01-01T10:00:00-05:00",
            "confidence": "high",
            "source": "Amtrak"
        },
        "progress": {
            "last_departed": {
                "station_code": "NY",
                "departed_at": "2024-01-01T09:35:00-05:00",
                "delay_minutes": 5
            },
            "next_arrival": {
                "station_code": "STM",
                "scheduled_arrival": "2024-01-01T10:10:00-05:00",
                "estimated_time": "2024-01-01T10:15:00-05:00",
                "minutes_away": 15
            },
            "journey_percent": 40,
            "stops_completed": 1,
            "total_stops": 3
        },
        "stops": [
            {
                "station_code": "NY",
                "station_name": "New York Penn Station",
                "scheduled_time": "2024-01-01T09:30:00-05:00",
                "departure_time": "2024-01-01T09:35:00-05:00",
                "departed": true,
                "departed_confirmed_by": ["Amtrak"],
                "platform": "11"
            },
            {
                "station_code": "STM",
                "station_name": "Stamford",
                "scheduled_arrival": "2024-01-01T10:10:00-05:00",
                "departure_time": null,
                "departed": false,
                "stop_status": "APPROACHING",
                "platform": "3"
            },
            {
                "station_code": "BOS",
                "station_name": "Boston South",
                "scheduled_time": "2024-01-01T13:30:00-05:00",
                "departure_time": null,
                "departed": false,
                "stop_status": "SCHEDULED",
                "platform": "5"
            }
        ]
    }
    """
    
    // API Response with multiple trains
    static let trainListResponseJSON = """
    {
        "metadata": {
            "timestamp": "2024-01-01T10:00:00-05:00",
            "model_version": "2.1.0",
            "train_count": 3,
            "page": 1,
            "total_pages": 1
        },
        "trains": [
            {
                "id": 1,
                "train_id": "123",
                "line": "Northeast Corridor",
                "destination": "New York Penn Station",
                "departure_time": "2024-01-01T10:00:00-05:00",
                "track": "1",
                "status": "ON_TIME",
                "origin_station_code": "NP",
                "data_source": "NJTransit"
            },
            {
                "id": 2,
                "train_id": "456",
                "line": "Northeast Corridor",
                "destination": "Trenton Transit Center",
                "departure_time": "2024-01-01T10:15:00-05:00",
                "track": "2",
                "status": "DELAYED",
                "delay_minutes": 15,
                "origin_station_code": "NY",
                "data_source": "NJTransit"
            },
            {
                "consolidated_id": "amtrak_2150_njtransit_789",
                "train_id": "2150",
                "line": "Northeast Corridor",
                "destination": "Washington Union Station",
                "origin_station": {
                    "code": "NY",
                    "name": "New York Penn Station",
                    "departure_time": "2024-01-01T11:00:00-05:00"
                },
                "status_summary": {
                    "current_status": "boarding",
                    "delay_minutes": 0,
                    "on_time_performance": "good"
                },
                "data_sources": [
                    {
                        "origin": "NY",
                        "data_source": "Amtrak",
                        "last_update": "2024-01-01T10:00:00-05:00",
                        "status": "BOARDING",
                        "track": "11",
                        "db_id": 12345
                    }
                ]
            }
        ]
    }
    """
    
    // Malformed JSON for error testing
    static let malformedTrainJSON = """
    {
        "id": "not_a_number",
        "train_id": null,
        "line": "",
        "destination": "New York Penn Station",
        "departure_time": "invalid-date-format",
        "status": "UNKNOWN_STATUS",
        "stops": "not_an_array"
    }
    """
    
    // MARK: - Legacy Properties for Compatibility
    
    @available(*, deprecated, message: "Use legacyTrainJSON instead")
    static let sampleTrainJSON = legacyTrainJSON
}