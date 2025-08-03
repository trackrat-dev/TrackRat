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
    
    func fetchHistoricalData(for train: TrainV2, fromStationCode: String, toStationCode: String, includeRouteTrains: Bool = false) async throws -> HistoricalData {
        var urlString = "\(baseURL)/v2/trains/\(train.trainId)/history?days=365&from_station=\(fromStationCode)&to_station=\(toStationCode)"
        if includeRouteTrains {
            urlString += "&include_route_trains=true"
        }
        guard let url = URL(string: urlString) else {
            throw APIError.invalidURL
        }
        
        print("📊 Fetching historical data from: \(url)")
        
        let (data, _) = try await URLSession.shared.data(from: url)
        
        // Debug: Print raw response
        if let jsonString = String(data: data, encoding: .utf8) {
            print("📊 Raw historical data response: \(jsonString.prefix(500))...")
        }
        
        // Define response structure for V2 history endpoint
        struct V2HistoryResponse: Decodable {
            let trainId: String
            let statistics: V2Statistics
            let routeStatistics: V2Statistics?
            let dataSource: String?
            
            struct V2Statistics: Decodable {
                let totalJourneys: Int
                let onTimePercentage: Double
                let averageDelayMinutes: Double
                let cancellationRate: Double
                let delayBreakdown: DelayBreakdown?
                let trackUsage: [String: Int]?
                
                struct DelayBreakdown: Decodable {
                    let onTime: Int
                    let slight: Int
                    let significant: Int
                    let major: Int
                    
                    private enum CodingKeys: String, CodingKey {
                        case onTime = "on_time"
                        case slight
                        case significant
                        case major
                    }
                }
                
                private enum CodingKeys: String, CodingKey {
                    case totalJourneys = "total_journeys"
                    case onTimePercentage = "on_time_percentage"
                    case averageDelayMinutes = "average_delay_minutes"
                    case cancellationRate = "cancellation_rate"
                    case delayBreakdown = "delay_breakdown"
                    case trackUsage = "track_usage"
                }
            }
            
            private enum CodingKeys: String, CodingKey {
                case trainId = "train_id"
                case statistics
                case routeStatistics = "route_statistics"
                case dataSource = "data_source"
            }
        }
        
        let response: V2HistoryResponse
        do {
            response = try decoder.decode(V2HistoryResponse.self, from: data)
        } catch {
            print("❌ Failed to decode historical data: \(error)")
            throw error
        }
        
        // Transform V2 response to iOS HistoricalData model
        var trainStats: DelayStats? = nil
        var trainTrackStats: TrackStats? = nil
        var routeStats: DelayStats? = nil
        var routeTrackStats: TrackStats? = nil
        
        // Create delay stats if we have delay breakdown
        if let breakdown = response.statistics.delayBreakdown {
            trainStats = DelayStats(
                onTime: breakdown.onTime,
                slight: breakdown.slight,
                significant: breakdown.significant,
                major: breakdown.major,
                total: response.statistics.totalJourneys,
                avgDelay: Int(response.statistics.averageDelayMinutes.rounded())
            )
        }
        
        // Create track stats if we have track usage data
        if let trackUsage = response.statistics.trackUsage, !trackUsage.isEmpty {
            let tracks = trackUsage
                .sorted { $0.value > $1.value }  // Sort by usage percentage descending
                .map { (track: $0.key, percentage: $0.value, count: Int(Double(response.statistics.totalJourneys) * Double($0.value) / 100)) }
            
            trainTrackStats = TrackStats(
                tracks: tracks,
                total: response.statistics.totalJourneys
            )
        }
        
        // Create route delay stats if we have route statistics
        if let routeStatistics = response.routeStatistics,
           let breakdown = routeStatistics.delayBreakdown {
            routeStats = DelayStats(
                onTime: breakdown.onTime,
                slight: breakdown.slight,
                significant: breakdown.significant,
                major: breakdown.major,
                total: routeStatistics.totalJourneys,
                avgDelay: Int(routeStatistics.averageDelayMinutes.rounded())
            )
        }
        
        // Create route track stats if we have route track usage data
        if let routeStatistics = response.routeStatistics,
           let trackUsage = routeStatistics.trackUsage, !trackUsage.isEmpty {
            let tracks = trackUsage
                .sorted { $0.value > $1.value }  // Sort by usage percentage descending
                .map { (track: $0.key, percentage: $0.value, count: Int(Double(routeStatistics.totalJourneys) * Double($0.value) / 100)) }
            
            routeTrackStats = TrackStats(
                tracks: tracks,
                total: routeStatistics.totalJourneys
            )
        }
        
        return HistoricalData(
            trainStats: trainStats,
            lineStats: nil,  // Not provided by backend
            destinationStats: nil,  // Not provided by backend
            trainTrackStats: trainTrackStats,
            lineTrackStats: nil,  // Not provided by backend
            destinationTrackStats: nil,  // Not provided by backend
            routeStats: routeStats,
            routeTrackStats: routeTrackStats,
            dataSource: response.dataSource
        )
    }
    
    // MARK: - Route Historical Data
    
    func fetchRouteHistoricalData(
        from: String,
        to: String,
        dataSource: String,
        highlightTrain: String? = nil,
        days: Int = 365
    ) async throws -> RouteHistoricalData {
        var urlComponents = URLComponents(string: "\(baseURL)/v2/routes/history")!
        urlComponents.queryItems = [
            URLQueryItem(name: "from_station", value: from),
            URLQueryItem(name: "to_station", value: to),
            URLQueryItem(name: "data_source", value: dataSource),
            URLQueryItem(name: "days", value: String(days))
        ]
        
        if let highlightTrain = highlightTrain {
            urlComponents.queryItems?.append(URLQueryItem(name: "highlight_train", value: highlightTrain))
        }
        
        guard let url = urlComponents.url else {
            throw APIError.invalidURL
        }
        
        print("📊 Fetching route historical data from: \(url)")
        
        let (data, _) = try await URLSession.shared.data(from: url)
        
        // Debug: Print raw response
        if let jsonString = String(data: data, encoding: .utf8) {
            print("📊 Raw route historical response: \(jsonString.prefix(500))...")
        }
        
        // Define response structure for route history endpoint
        struct RouteHistoryResponse: Decodable {
            let route: RouteInfo
            let aggregateStats: AggregateStats
            let highlightedTrain: HighlightedTrainStats?
            
            struct RouteInfo: Decodable {
                let fromStation: String
                let toStation: String
                let totalTrains: Int
                let dataSource: String
                
                private enum CodingKeys: String, CodingKey {
                    case fromStation = "from_station"
                    case toStation = "to_station"
                    case totalTrains = "total_trains"
                    case dataSource = "data_source"
                }
            }
            
            struct AggregateStats: Decodable {
                let onTimePercentage: Double
                let averageDelayMinutes: Double
                let cancellationRate: Double
                let delayBreakdown: DelayBreakdown
                let trackUsageAtOrigin: [String: Int]
                
                private enum CodingKeys: String, CodingKey {
                    case onTimePercentage = "on_time_percentage"
                    case averageDelayMinutes = "average_delay_minutes"
                    case cancellationRate = "cancellation_rate"
                    case delayBreakdown = "delay_breakdown"
                    case trackUsageAtOrigin = "track_usage_at_origin"
                }
            }
            
            struct HighlightedTrainStats: Decodable {
                let trainId: String
                let onTimePercentage: Double
                let averageDelayMinutes: Double
                let delayBreakdown: DelayBreakdown
                let trackUsageAtOrigin: [String: Int]
                
                private enum CodingKeys: String, CodingKey {
                    case trainId = "train_id"
                    case onTimePercentage = "on_time_percentage"
                    case averageDelayMinutes = "average_delay_minutes"
                    case delayBreakdown = "delay_breakdown"
                    case trackUsageAtOrigin = "track_usage_at_origin"
                }
            }
            
            struct DelayBreakdown: Decodable {
                let onTime: Int
                let slight: Int
                let significant: Int
                let major: Int
                
                private enum CodingKeys: String, CodingKey {
                    case onTime = "on_time"
                    case slight
                    case significant
                    case major
                }
            }
            
            private enum CodingKeys: String, CodingKey {
                case route
                case aggregateStats = "aggregate_stats"
                case highlightedTrain = "highlighted_train"
            }
        }
        
        let response: RouteHistoryResponse
        do {
            response = try decoder.decode(RouteHistoryResponse.self, from: data)
        } catch {
            print("❌ Failed to decode route historical data: \(error)")
            throw error
        }
        
        // Transform to RouteHistoricalData model
        return RouteHistoricalData(
            route: RouteHistoricalData.RouteInfo(
                fromStation: response.route.fromStation,
                toStation: response.route.toStation,
                totalTrains: response.route.totalTrains,
                dataSource: response.route.dataSource
            ),
            aggregateStats: RouteHistoricalData.Stats(
                onTimePercentage: response.aggregateStats.onTimePercentage,
                averageDelayMinutes: response.aggregateStats.averageDelayMinutes,
                cancellationRate: response.aggregateStats.cancellationRate,
                delayBreakdown: RouteHistoricalData.DelayBreakdown(
                    onTime: response.aggregateStats.delayBreakdown.onTime,
                    slight: response.aggregateStats.delayBreakdown.slight,
                    significant: response.aggregateStats.delayBreakdown.significant,
                    major: response.aggregateStats.delayBreakdown.major
                ),
                trackUsageAtOrigin: response.aggregateStats.trackUsageAtOrigin
            ),
            highlightedTrain: response.highlightedTrain.map { highlighted in
                RouteHistoricalData.Stats(
                    onTimePercentage: highlighted.onTimePercentage,
                    averageDelayMinutes: highlighted.averageDelayMinutes,
                    cancellationRate: 0.0, // Not provided for individual trains
                    delayBreakdown: RouteHistoricalData.DelayBreakdown(
                        onTime: highlighted.delayBreakdown.onTime,
                        slight: highlighted.delayBreakdown.slight,
                        significant: highlighted.delayBreakdown.significant,
                        major: highlighted.delayBreakdown.major
                    ),
                    trackUsageAtOrigin: highlighted.trackUsageAtOrigin
                )
            }
        )
    }
    
    // MARK: - Congestion Data
    
    func fetchCongestionData(timeWindowHours: Int = 3) async throws -> CongestionMapResponse {
        return try await fetchCongestionData(timeWindowHours: timeWindowHours, maxPerSegment: 100, dataSource: nil)
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
    
    // MARK: - Occupied Tracks
    
    func fetchOccupiedTracks(stationCode: String) async throws -> V2OccupiedTracksResponse {
        var components = URLComponents(string: "\(baseURL)/v2/trains/stations/\(stationCode)/tracks/occupied")!
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        let (data, response) = try await session.data(from: url)
        
        if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 404 {
            throw APIError.noData
        }
        
        do {
            let response = try decoder.decode(V2OccupiedTracksResponse.self, from: data)
            return response
        } catch {
            print("🔴 V2 DECODING ERROR (fetchOccupiedTracks for station: \(stationCode)): \(error)")
            if let jsonString = String(data: data, encoding: .utf8) {
                print("🔴 RAW DATA: \(jsonString.prefix(500))")
            }
            throw error
        }
    }
    
    // MARK: - Congestion Data
    
    func fetchCongestionData(timeWindowHours: Int = 3, maxPerSegment: Int = 100, dataSource: String? = nil) async throws -> CongestionMapResponse {
        var components = URLComponents(string: "\(baseURL)/v2/routes/congestion")!
        components.queryItems = [
            URLQueryItem(name: "time_window_hours", value: String(timeWindowHours)),
            URLQueryItem(name: "max_per_segment", value: String(maxPerSegment))
        ]
        
        if let dataSource = dataSource {
            components.queryItems?.append(URLQueryItem(name: "data_source", value: dataSource))
        }
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        let (data, _) = try await session.data(from: url)
        
        do {
            let response = try decoder.decode(CongestionMapResponse.self, from: data)
            return response
        } catch {
            print("🔴 DECODING ERROR (fetchCongestionData): \(error)")
            if let jsonString = String(data: data, encoding: .utf8) {
                print("🔴 RAW DATA: \(jsonString.prefix(500))")
            }
            throw error
        }
    }
    
    func fetchSegmentTrainDetails(
        fromStation: String,
        toStation: String,
        dataSource: String? = nil,
        startTime: Date? = nil,
        endTime: Date? = nil,
        limit: Int = 50,
        status: String? = nil
    ) async throws -> SegmentTrainDetailsResponse {
        var components = URLComponents(string: "\(baseURL)/v2/routes/segments/\(fromStation)/\(toStation)/trains")!
        var queryItems: [URLQueryItem] = []
        
        if let dataSource = dataSource {
            queryItems.append(URLQueryItem(name: "data_source", value: dataSource))
        }
        
        if let startTime = startTime {
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            queryItems.append(URLQueryItem(name: "start_time", value: formatter.string(from: startTime)))
        }
        
        if let endTime = endTime {
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            queryItems.append(URLQueryItem(name: "end_time", value: formatter.string(from: endTime)))
        }
        
        queryItems.append(URLQueryItem(name: "limit", value: String(limit)))
        
        if let status = status {
            queryItems.append(URLQueryItem(name: "status", value: status))
        }
        
        components.queryItems = queryItems.isEmpty ? nil : queryItems
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        let (data, response) = try await session.data(from: url)
        
        if let httpResponse = response as? HTTPURLResponse {
            if httpResponse.statusCode == 404 {
                throw APIError.noData
            } else if httpResponse.statusCode != 200 {
                throw APIError.invalidParameters
            }
        }
        
        do {
            let response = try decoder.decode(SegmentTrainDetailsResponse.self, from: data)
            return response
        } catch {
            print("🔴 DECODING ERROR (fetchSegmentTrainDetails): \(error)")
            if let jsonString = String(data: data, encoding: .utf8) {
                print("🔴 RAW DATA: \(jsonString.prefix(500))")
            }
            throw error
        }
    }
    
    // MARK: - V2 API Adapters
    
    private func adaptV2DepartureToTrainV2(_ departure: V2TrainDeparture) -> TrainV2 {
        return TrainV2(
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
            isCancelled: departure.isCancelled,
            isCompleted: false, // Departures are never completed at search time
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
            isCancelled: details.isCancelled,
            isCompleted: details.isCompleted,
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