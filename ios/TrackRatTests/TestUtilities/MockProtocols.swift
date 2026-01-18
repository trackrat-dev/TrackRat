import Foundation
@testable import TrackRat

// MARK: - API Service Protocol for Mocking

protocol APIServiceProtocol {
    func searchTrains(fromStationCode: String, toStationCode: String) async throws -> [Train]
    func fetchTrainDetails(id trainId: String, fromStationCode: String) async throws -> TrainV2
    func fetchRouteHistoricalData(from: String, to: String, dataSource: String, highlightTrain: String?, days: Int) async throws -> RouteHistoricalData
    func fetchCongestionMapData(timeWindowHours: Int, dataSource: String?, maxPerSegment: Int) async throws -> CongestionMapResponse
    func registerLiveActivityToken(pushToken: String, activityId: String, trainNumber: String, originCode: String, destinationCode: String) async throws
    func unregisterLiveActivityToken(pushToken: String) async throws
}

// Note: APIService is final and can't be extended to conform to the protocol
// The protocol is only for mocking purposes

// MARK: - Mock API Service

class MockAPIService: APIServiceProtocol {
    // Search trains
    var searchTrainsResult: Result<[Train], Error>?
    var trainsToReturn: [Train] = []
    var searchTrainsCallCount = 0
    var lastFromStationCode: String?
    var lastToStationCode: String?

    func searchTrains(fromStationCode: String, toStationCode: String) async throws -> [Train] {
        searchTrainsCallCount += 1
        lastFromStationCode = fromStationCode
        lastToStationCode = toStationCode

        if let result = searchTrainsResult {
            switch result {
            case .success(let trains):
                return trains
            case .failure(let error):
                throw error
            }
        }

        return trainsToReturn
    }

    // Fetch train details
    var fetchTrainDetailsResult: Result<TrainV2, Error>?
    var fetchTrainDetailsCallCount = 0
    var lastTrainId: String?
    var lastFromStationCodeForDetails: String?

    func fetchTrainDetails(id trainId: String, fromStationCode: String) async throws -> TrainV2 {
        fetchTrainDetailsCallCount += 1
        lastTrainId = trainId
        lastFromStationCodeForDetails = fromStationCode

        if let result = fetchTrainDetailsResult {
            switch result {
            case .success(let train):
                return train
            case .failure(let error):
                throw error
            }
        }

        // Return a default mock train
        return MockDataFactory.createMockTrainV2(trainId: trainId, fromStationCode: fromStationCode)
    }

    // Historical data
    var fetchRouteHistoricalDataResult: Result<RouteHistoricalData, Error>?
    var fetchRouteHistoricalDataCallCount = 0
    var lastHistoricalFromCode: String?
    var lastHistoricalToCode: String?

    func fetchRouteHistoricalData(from: String, to: String, dataSource: String, highlightTrain: String?, days: Int) async throws -> RouteHistoricalData {
        fetchRouteHistoricalDataCallCount += 1
        lastHistoricalFromCode = from
        lastHistoricalToCode = to

        if let result = fetchRouteHistoricalDataResult {
            switch result {
            case .success(let data):
                return data
            case .failure(let error):
                throw error
            }
        }

        // Return default mock data
        return RouteHistoricalData(
            route: RouteHistoricalData.RouteInfo(
                fromStation: from,
                toStation: to,
                totalTrains: 100,
                dataSource: dataSource
            ),
            aggregateStats: RouteHistoricalData.Stats(
                onTimePercentage: 85.0,
                averageDelayMinutes: 5.2,
                cancellationRate: 2.0,
                delayBreakdown: RouteHistoricalData.DelayBreakdown(
                    onTime: 40,
                    slight: 30,
                    significant: 20,
                    major: 10
                ),
                trackUsageAtOrigin: ["11": 40, "12": 30, "13": 30]
            ),
            highlightedTrain: nil
        )
    }

    // Congestion map
    var fetchCongestionMapDataResult: Result<CongestionMapResponse, Error>?
    var fetchCongestionMapDataCallCount = 0

    func fetchCongestionMapData(timeWindowHours: Int, dataSource: String?, maxPerSegment: Int) async throws -> CongestionMapResponse {
        fetchCongestionMapDataCallCount += 1

        if let result = fetchCongestionMapDataResult {
            switch result {
            case .success(let data):
                return data
            case .failure(let error):
                throw error
            }
        }

        // Create a simple mock CongestionMapResponse
        // Since it's Codable and has complex init, we'll create a minimal JSON and decode it
        let json = """
        {
            "individual_segments": [],
            "aggregated_segments": [],
            "train_positions": [],
            "generated_at": "\(ISO8601DateFormatter().string(from: Date()))",
            "time_window_hours": \(timeWindowHours),
            "max_per_segment": \(maxPerSegment),
            "metadata": {}
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        if let data = json.data(using: .utf8),
           let response = try? decoder.decode(CongestionMapResponse.self, from: data) {
            return response
        }

        // Fallback - throw error if we can't create the response
        throw MockTestError.invalidData
    }

    // Live activity tokens
    var registerTokenResult: Result<Void, Error>?
    var registerTokenCallCount = 0
    var lastPushToken: String?
    var lastActivityId: String?

    func registerLiveActivityToken(pushToken: String, activityId: String, trainNumber: String, originCode: String, destinationCode: String) async throws {
        registerTokenCallCount += 1
        lastPushToken = pushToken
        lastActivityId = activityId

        if let result = registerTokenResult {
            switch result {
            case .success:
                return
            case .failure(let error):
                throw error
            }
        }
    }

    var unregisterTokenResult: Result<Void, Error>?
    var unregisterTokenCallCount = 0

    func unregisterLiveActivityToken(pushToken: String) async throws {
        unregisterTokenCallCount += 1
        lastPushToken = pushToken

        if let result = unregisterTokenResult {
            switch result {
            case .success:
                return
            case .failure(let error):
                throw error
            }
        }
    }
}

// MARK: - Mock Data Factory

struct MockDataFactory {
    static func createMockTrain(
        trainId: String = "123",
        destination: String = "Philadelphia",
        originStationCode: String = "NY",
        departureTime: Date = Date(),
        status: TrainStatus = .onTime,
        delayMinutes: Int = 0
    ) -> Train {
        return Train(
            id: Int(trainId) ?? 123,
            trainId: trainId,
            line: "Northeast Corridor",
            destination: destination,
            departureTime: departureTime,
            track: "11",
            status: status,
            delayMinutes: delayMinutes > 0 ? delayMinutes : nil,
            stops: [],
            predictionData: nil,
            originStationCode: originStationCode,
            dataSource: "NJT",
            consolidatedId: nil,
            originStation: OriginStation(code: originStationCode, name: "New York Penn Station", departureTime: departureTime),
            dataSources: nil,
            currentPosition: nil,
            trackAssignment: nil,
            statusSummary: nil,
            consolidationMetadata: nil,
            statusV2: nil,
            progress: nil,
            observationType: "scheduled"
        )
    }

    static func createMockTrainV2(
        trainId: String = "TEST123",
        fromStationCode: String = "NY",
        destination: String = "Philadelphia",
        departureTime: Date = Date(),
        delayMinutes: Int = 0,
        isCancelled: Bool = false,
        isCompleted: Bool = false
    ) -> TrainV2 {
        let departure = StationTiming(
            code: fromStationCode,
            name: fromStationCode == "NY" ? "New York Penn Station" : "Origin Station",
            scheduledTime: departureTime,
            updatedTime: delayMinutes > 0 ? departureTime.addingTimeInterval(TimeInterval(delayMinutes * 60)) : nil,
            actualTime: nil,
            track: "11"
        )

        let arrival = StationTiming(
            code: "PH",
            name: destination,
            scheduledTime: departureTime.addingTimeInterval(3600),
            updatedTime: nil,
            actualTime: nil,
            track: nil
        )

        let line = LineInfo(code: "NEC", name: "Northeast Corridor", color: "#FF6B00")

        let stops: [StopV2] = [
            StopV2(
                stationCode: fromStationCode,
                stationName: departure.name,
                sequence: 1,
                scheduledArrival: nil,
                scheduledDeparture: departureTime,
                updatedArrival: nil,
                updatedDeparture: delayMinutes > 0 ? departureTime.addingTimeInterval(TimeInterval(delayMinutes * 60)) : nil,
                actualArrival: nil,
                actualDeparture: nil,
                track: "11",
                rawStatus: nil,
                hasDepartedStation: false,
                predictedArrival: nil,
                predictedArrivalSamples: nil
            ),
            StopV2(
                stationCode: "PH",
                stationName: destination,
                sequence: 2,
                scheduledArrival: departureTime.addingTimeInterval(3600),
                scheduledDeparture: nil,
                updatedArrival: nil,
                updatedDeparture: nil,
                actualArrival: nil,
                actualDeparture: nil,
                track: nil,
                rawStatus: nil,
                hasDepartedStation: false,
                predictedArrival: nil,
                predictedArrivalSamples: nil
            )
        ]

        return TrainV2(
            trainId: trainId,
            journeyDate: departureTime,
            line: line,
            destination: destination,
            departure: departure,
            arrival: arrival,
            trainPosition: nil,
            dataFreshness: nil,
            observationType: nil,
            isCancelled: isCancelled,
            isCompleted: isCompleted,
            dataSource: "NJT",
            stops: stops
        )
    }
}

// MARK: - Mock Test Error

enum MockTestError: Error {
    case networkError
    case notFound
    case invalidData
}