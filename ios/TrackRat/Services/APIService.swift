import Foundation
import Combine

// MARK: - Clean API Service for V2 Backend
@MainActor
final class APIService: ObservableObject {
    static let shared = APIService()
    
    private var baseURL: String
    private let session = URLSession.shared
    private let storageService = StorageService()
    
    init() {
        let environment = storageService.loadServerEnvironment()
        self.baseURL = environment.baseURL
    }
    
    func updateServerEnvironment(_ environment: ServerEnvironment) {
        self.baseURL = environment.baseURL
    }
    
    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder throws -> Date in
            let container = try decoder.singleValueContainer()
            let dateString = try container.decode(String.self)
            if let date = Date.fromISO8601(dateString) {
                return date
            }
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Cannot decode date string \(dateString)")
        }
        return decoder
    }()
    
    // MARK: - Train Search
    
    func searchTrains(fromStationCode: String, toStationCode: String) async throws -> [TrainV2] {
        var components = URLComponents(string: "\(baseURL)/v2/trains/departures")!
        components.queryItems = [
            URLQueryItem(name: "from", value: fromStationCode),
            URLQueryItem(name: "to", value: toStationCode),
            URLQueryItem(name: "limit", value: "100")
        ]
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        let (data, _) = try await session.data(from: url)
        
        do {
            let response = try decoder.decode(V2DeparturesResponse.self, from: data)
            return response.departures.map { adaptV2DepartureToTrainV2($0) }
        } catch {
            print("🔴 V2 DECODING ERROR (searchTrains): \(error)")
            if let jsonString = String(data: data, encoding: .utf8) {
                print("🔴 RAW DATA: \(jsonString.prefix(500))")
            }
            throw error
        }
    }
    
    // MARK: - Train Details
    
    func fetchTrainDetails(id: String, fromStationCode: String? = nil) async throws -> TrainV2 {
        var components = URLComponents(string: "\(baseURL)/v2/trains/\(id)")!
        
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        components.queryItems = [
            URLQueryItem(name: "date", value: formatter.string(from: Date()))
        ]
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        let (data, response) = try await session.data(from: url)
        
        if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 404 {
            throw APIError.noData
        }
        
        do {
            let detailsResponse = try decoder.decode(V2TrainDetailsResponse.self, from: data)
            return adaptV2TrainDetailsToTrainV2(detailsResponse.train, fromStationCode: fromStationCode)
        } catch {
            print("🔴 V2 DECODING ERROR (fetchTrainDetails for id: \(id)): \(error)")
            throw error
        }
    }
    
    // MARK: - Train by Number
    
    func fetchTrainByNumber(_ number: String, fromStationCode: String? = nil) async throws -> TrainV2 {
        // V2 backend doesn't support search by train number in list endpoint
        // So we try to fetch details directly
        return try await fetchTrainDetails(id: number, fromStationCode: fromStationCode)
    }
    
    // MARK: - Flexible Train Details
    
    func fetchTrainDetailsFlexible(id: String? = nil, trainId: String? = nil, fromStationCode: String? = nil) async throws -> TrainV2 {
        let trainNumber = id ?? trainId ?? ""
        return try await fetchTrainDetails(id: trainNumber, fromStationCode: fromStationCode)
    }
    
    // MARK: - Historical Data (Simplified for V2)
    
    func fetchHistoricalData(for train: TrainV2, fromStationCode: String, toStationCode: String) async throws -> HistoricalData {
        // V2 backend has a different history endpoint
        // For now, return empty historical data
        return HistoricalData(
            trainStats: nil,
            lineStats: nil,
            destinationStats: nil,
            trainTrackStats: nil,
            lineTrackStats: nil,
            destinationTrackStats: nil
        )
    }
    
    // MARK: - Push Notification Registration
    
    /// Register device token for push notifications
    func registerDeviceToken(_ token: String) async throws {
        let url = URL(string: "\(baseURL)/notifications/device-tokens")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let payload = [
            "device_token": token,
            "platform": "ios",
            "timestamp": ISO8601DateFormatter().string(from: Date())
        ]
        
        request.httpBody = try JSONSerialization.data(withJSONObject: payload)
        
        do {
            let (_, response) = try await session.data(for: request)
            
            if let httpResponse = response as? HTTPURLResponse {
                print("📱 Device token registration response: \(httpResponse.statusCode)")
                if httpResponse.statusCode != 200 && httpResponse.statusCode != 201 {
                    throw APIError.invalidParameters
                }
            }
            
            print("✅ Device token registered successfully")
        } catch {
            print("❌ Failed to register device token: \(error)")
            throw error
        }
    }
    
    // MARK: - Live Activity Registration
    
    struct LiveActivityTokenRequest: Codable {
        let trainId: String
        let pushToken: String
        let deviceToken: String?
        let userOriginStationCode: String?
        let userDestinationStationCode: String?
        
        enum CodingKeys: String, CodingKey {
            case trainId = "train_id"
            case pushToken = "push_token"
            case deviceToken = "device_token"
            case userOriginStationCode = "user_origin_station_code"
            case userDestinationStationCode = "user_destination_station_code"
        }
    }
    
    func registerLiveActivity(
        trainId: String,
        pushToken: String,
        deviceToken: String?,
        userOrigin: String?,
        userDestination: String?
    ) async throws {
        let url = URL(string: "\(baseURL)/notifications/live-activities/register")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let requestBody = LiveActivityTokenRequest(
            trainId: trainId,
            pushToken: pushToken,
            deviceToken: deviceToken,
            userOriginStationCode: userOrigin,
            userDestinationStationCode: userDestination
        )
        
        do {
            request.httpBody = try JSONEncoder().encode(requestBody)
        } catch {
            print("Failed to encode request body: \(error)")
            throw APIError.encodingError
        }
        
        let (data, response) = try await session.data(for: request)
        
        if let httpResponse = response as? HTTPURLResponse {
            print("📱 Live Activity token registration response: \(httpResponse.statusCode)")
            
            if let responseString = String(data: data, encoding: .utf8) {
                print("📱 Live Activity registration response body: \(responseString)")
            }
            
            if httpResponse.statusCode != 200 && httpResponse.statusCode != 201 {
                throw APIError.invalidParameters
            }
        }
        
        print("✅ Live Activity token registered for train \(trainId)")
    }
    
    // MARK: - Live Activity Token Registration (V2)
    
    func registerLiveActivityToken(pushToken: String, activityId: String, trainNumber: String, originCode: String, destinationCode: String) async throws {
        // Create V2 endpoint
        let endpoint = "/v2/live-activities/register"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw APIError.invalidURL
        }
        
        // Create request body matching new backend
        struct RegisterRequest: Encodable {
            let push_token: String
            let activity_id: String
            let train_number: String
            let origin_code: String
            let destination_code: String
        }
        
        let body = RegisterRequest(
            push_token: pushToken,
            activity_id: activityId,
            train_number: trainNumber,
            origin_code: originCode,
            destination_code: destinationCode
        )
        
        // Create request
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let encoder = JSONEncoder()
        request.httpBody = try encoder.encode(body)
        
        print("📱 Registering Live Activity token (V2):")
        print("  Token: \(pushToken.prefix(10))...")
        print("  Train: \(trainNumber)")
        print("  Route: \(originCode) → \(destinationCode)")
        
        let (_, response) = try await session.data(for: request)
        
        if let httpResponse = response as? HTTPURLResponse {
            if httpResponse.statusCode != 200 && httpResponse.statusCode != 201 {
                throw APIError.invalidParameters
            }
        }
        
        print("✅ Live Activity token registered for train \(trainNumber)")
    }
    
    func unregisterLiveActivityToken(pushToken: String) async throws {
        // Create V2 endpoint
        let endpoint = "/v2/live-activities/\(pushToken)"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw APIError.invalidURL
        }
        
        // Create request
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        
        let (_, response) = try await session.data(for: request)
        
        if let httpResponse = response as? HTTPURLResponse {
            if httpResponse.statusCode != 200 && httpResponse.statusCode != 404 {
                throw APIError.invalidParameters
            }
        }
        
        print("✅ Live Activity token unregistered")
    }
    
    // MARK: - V2 API Adapters
    
    private func adaptV2DepartureToTrainV2(_ departure: V2TrainDeparture) -> TrainV2 {
        return TrainV2(
            id: departure.trainId.hashValue,
            trainId: departure.trainId,
            line: LineInfo(
                code: departure.line.code,
                name: departure.line.name,
                color: departure.line.color
            ),
            destination: departure.destination,
            departure: StationTiming(
                code: departure.departure.code,
                name: departure.departure.name,
                scheduledTime: departure.departure.scheduledTime,
                updatedTime: departure.departure.updatedTime,
                actualTime: departure.departure.actualTime,
                track: departure.departure.track
            ),
            arrival: departure.arrival.map { arrival in
                StationTiming(
                    code: arrival.code,
                    name: arrival.name,
                    scheduledTime: arrival.scheduledTime,
                    updatedTime: arrival.updatedTime,
                    actualTime: arrival.actualTime,
                    track: arrival.track
                )
            },
            trainPosition: TrainPosition(
                lastDepartedStationCode: departure.trainPosition.lastDepartedStationCode,
                atStationCode: departure.trainPosition.atStationCode,
                nextStationCode: departure.trainPosition.nextStationCode
            ),
            dataFreshness: DataFreshness(
                lastUpdated: departure.dataFreshness.lastUpdated,
                ageSeconds: departure.dataFreshness.ageSeconds,
                updateCount: departure.dataFreshness.updateCount,
                collectionMethod: departure.dataFreshness.collectionMethod
            ),
            stops: nil
        )
    }
    
    private func adaptV2TrainDetailsToTrainV2(_ details: V2TrainDetails, fromStationCode: String?) -> TrainV2 {
        // Find departure and arrival stations from stops
        let departureStop = details.stops.first
        let arrivalStop = details.stops.last
        
        // Convert stops
        let stops = details.stops.map { stop in
            StopV2(
                stationCode: stop.station.code,
                stationName: stop.station.name,
                sequence: stop.stopSequence,
                scheduledArrival: stop.scheduledArrival,
                scheduledDeparture: stop.scheduledDeparture,
                updatedArrival: stop.updatedArrival,
                updatedDeparture: stop.updatedDeparture,
                actualArrival: stop.actualArrival,
                actualDeparture: stop.actualDeparture,
                track: stop.track,
                rawStatus: RawStopStatus(
                    amtrakStatus: stop.rawStatus.amtrakStatus, 
                    njtDepartedFlag: stop.rawStatus.njtDepartedFlag
                ),
                hasDepartedStation: stop.hasDepartedStation
            )
        }
        
        // Create departure timing from first stop or requested station
        let departureTiming: StationTiming
        if let fromCode = fromStationCode,
           let requestedStop = details.stops.first(where: { $0.station.code == fromCode }) {
            departureTiming = StationTiming(
                code: requestedStop.station.code,
                name: requestedStop.station.name,
                scheduledTime: requestedStop.scheduledDeparture,
                updatedTime: requestedStop.updatedDeparture,
                actualTime: requestedStop.actualDeparture,
                track: requestedStop.track
            )
        } else if let firstStop = departureStop {
            departureTiming = StationTiming(
                code: firstStop.station.code,
                name: firstStop.station.name,
                scheduledTime: firstStop.scheduledDeparture,
                updatedTime: firstStop.updatedDeparture,
                actualTime: firstStop.actualDeparture,
                track: firstStop.track
            )
        } else {
            departureTiming = StationTiming(
                code: details.route.originCode,
                name: details.route.origin,
                scheduledTime: nil,
                updatedTime: nil,
                actualTime: nil,
                track: nil
            )
        }
        
        // Create arrival timing from last stop
        let arrivalTiming = arrivalStop.map { stop in
            StationTiming(
                code: stop.station.code,
                name: stop.station.name,
                scheduledTime: stop.scheduledArrival,
                updatedTime: stop.updatedArrival,
                actualTime: stop.actualArrival,
                track: stop.track
            )
        }
        
        return TrainV2(
            id: details.trainId.hashValue,
            trainId: details.trainId,
            line: LineInfo(
                code: details.line.code,
                name: details.line.name,
                color: details.line.color
            ),
            destination: details.route.destination,
            departure: departureTiming,
            arrival: arrivalTiming,
            trainPosition: TrainPosition(
                lastDepartedStationCode: details.trainPosition.lastDepartedStationCode,
                atStationCode: details.trainPosition.atStationCode,
                nextStationCode: details.trainPosition.nextStationCode
            ),
            dataFreshness: DataFreshness(
                lastUpdated: details.dataFreshness.lastUpdated,
                ageSeconds: details.dataFreshness.ageSeconds,
                updateCount: details.dataFreshness.updateCount,
                collectionMethod: details.dataFreshness.collectionMethod
            ),
            stops: stops
        )
    }
}

// MARK: - API Errors
enum APIError: LocalizedError {
    case invalidURL
    case noData
    case decodingError
    case invalidParameters
    case encodingError
    
    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid URL"
        case .noData: return "No data received"
        case .decodingError: return "Failed to decode response"
        case .invalidParameters: return "Invalid parameters provided"
        case .encodingError: return "Failed to encode request body"
        }
    }
}