import Foundation
import Combine

// MARK: - Clean API Service for V2 Backend
final class APIService: ObservableObject {
    static let shared = APIService()

    private var baseURL: String
    private let session: URLSession
    private let storageService = StorageService()

    // Configuration constants
    // PERFORMANCE: Reduced from 1000 to 50 to minimize payload size and parsing time.
    // The app filters to 6-hour window anyway, and pagination can be added later if needed.
    private static let DEPARTURE_LIMIT = "50"
    // PERFORMANCE: Configure shorter timeout (15s) instead of default 60s
    private static let REQUEST_TIMEOUT: TimeInterval = 15
    // PERFORMANCE: Retry configuration for transient failures
    private static let MAX_RETRIES = 2
    private static let RETRY_DELAY_BASE: TimeInterval = 1.0

    init() {
        let environment = storageService.loadServerEnvironment()
        self.baseURL = environment.baseURL

        // PERFORMANCE: Configure URLSession with shorter timeout
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = APIService.REQUEST_TIMEOUT
        configuration.timeoutIntervalForResource = APIService.REQUEST_TIMEOUT * 2
        self.session = URLSession(configuration: configuration)
    }

    // MARK: - Retry Logic

    /// Execute a request with automatic retry on transient failures
    private func executeWithRetry<T>(
        operation: @escaping () async throws -> T,
        retries: Int = MAX_RETRIES
    ) async throws -> T {
        var lastError: Error?
        var attempt = 0

        while attempt <= retries {
            do {
                return try await operation()
            } catch {
                lastError = error

                // Only retry on network/timeout errors, not on HTTP errors
                let shouldRetry = isRetryableError(error) && attempt < retries
                if shouldRetry {
                    attempt += 1
                    let delay = APIService.RETRY_DELAY_BASE * pow(2.0, Double(attempt - 1))
                    print("⚠️ Request failed, retrying in \(delay)s (attempt \(attempt)/\(retries)): \(error.localizedDescription)")
                    try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                } else {
                    throw error
                }
            }
        }

        throw lastError ?? APIError.noData
    }

    /// Determine if an error is retryable (transient network issues)
    private func isRetryableError(_ error: Error) -> Bool {
        if let urlError = error as? URLError {
            switch urlError.code {
            case .timedOut, .networkConnectionLost, .notConnectedToInternet,
                 .cannotConnectToHost, .cannotFindHost:
                return true
            default:
                return false
            }
        }
        return false
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

    func searchTrains(fromStationCode: String, toStationCode: String? = nil, date: Date? = nil, dataSources: Set<TrainSystem>? = nil) async throws -> [TrainV2] {
        guard var components = URLComponents(string: "\(baseURL)/v2/trains/departures") else {
            throw APIError.invalidURL
        }

        var queryItems = [
            URLQueryItem(name: "from", value: fromStationCode),
            URLQueryItem(name: "limit", value: APIService.DEPARTURE_LIMIT),
            // PERFORMANCE: Filter out already-departed trains server-side
            // This reduces payload size and eliminates redundant client filtering
            URLQueryItem(name: "hide_departed", value: "true")
        ]

        if let toStationCode = toStationCode {
            queryItems.append(URLQueryItem(name: "to", value: toStationCode))
        }

        if let date = date {
            let formatter = DateFormatter()
            formatter.dateFormat = "yyyy-MM-dd"
            formatter.timeZone = TimeZone(identifier: "America/New_York")
            queryItems.append(URLQueryItem(name: "date", value: formatter.string(from: date)))
        }

        // Add data_sources filter if specified (comma-separated)
        if let dataSources = dataSources, !dataSources.isEmpty {
            queryItems.append(URLQueryItem(name: "data_sources", value: dataSources.apiDataSources))
        }

        components.queryItems = queryItems

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        print("🔵 DEBUG API: Fetching trains from URL: \(url)")

        // PERFORMANCE: Use retry logic for transient network failures
        return try await executeWithRetry {
            let (data, _) = try await self.session.data(from: url)

            do {
                let response = try self.decoder.decode(V2DeparturesResponse.self, from: data)
                print("🔵 DEBUG API: Decoded \(response.departures.count) departures from API")
                print("🔵 DEBUG API: Train IDs in response: \(response.departures.map { $0.trainId })")

                let adaptedTrains = response.departures.map { self.adaptV2DepartureToTrainV2($0) }
                print("🔵 DEBUG API: Adapted to \(adaptedTrains.count) TrainV2 objects")

                return adaptedTrains
            } catch {
                print("🔴 V2 DECODING ERROR (searchTrains): \(error)")
                if let jsonString = String(data: data, encoding: .utf8) {
                    print("🔴 RAW DATA: \(jsonString.prefix(500))")
                }
                throw error
            }
        }
    }
    
    // MARK: - Trip Search

    func searchTrips(fromStationCode: String, toStationCode: String, date: Date? = nil, dataSources: Set<TrainSystem>? = nil) async throws -> [TripOption] {
        guard var components = URLComponents(string: "\(baseURL)/v2/trips/search") else {
            throw APIError.invalidURL
        }

        var queryItems = [
            URLQueryItem(name: "from", value: fromStationCode),
            URLQueryItem(name: "to", value: toStationCode),
            URLQueryItem(name: "limit", value: APIService.DEPARTURE_LIMIT),
            URLQueryItem(name: "hide_departed", value: "true")
        ]

        if let date = date {
            let formatter = DateFormatter()
            formatter.dateFormat = "yyyy-MM-dd"
            formatter.timeZone = TimeZone(identifier: "America/New_York")
            queryItems.append(URLQueryItem(name: "date", value: formatter.string(from: date)))
        }

        if let dataSources = dataSources, !dataSources.isEmpty {
            queryItems.append(URLQueryItem(name: "data_sources", value: dataSources.apiDataSources))
        }

        components.queryItems = queryItems

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        print("🔵 DEBUG API: Searching trips from URL: \(url)")

        return try await executeWithRetry {
            let (data, _) = try await self.session.data(from: url)

            do {
                let response = try self.decoder.decode(V2TripSearchResponse.self, from: data)
                print("🔵 DEBUG API: Decoded \(response.trips.count) trip options (search_type: \(response.metadata?.searchType ?? "unknown"))")

                return response.trips.map { self.adaptV2TripOption($0) }
            } catch {
                print("🔴 V2 DECODING ERROR (searchTrips): \(error)")
                if let jsonString = String(data: data, encoding: .utf8) {
                    print("🔴 RAW DATA: \(jsonString.prefix(500))")
                }
                throw error
            }
        }
    }

    // MARK: - Train Details

    func fetchTrainDetails(id: String, fromStationCode: String? = nil, date: Date? = nil, dataSource: String? = nil) async throws -> TrainV2 {
        var components = URLComponents(string: "\(baseURL)/v2/trains/\(id)")!

        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.timeZone = TimeZone(identifier: "America/New_York")

        let queryDate = date ?? Date()
        var queryItems = [
            URLQueryItem(name: "date", value: formatter.string(from: queryDate)),
            URLQueryItem(name: "include_predictions", value: "true")
        ]

        // Pass the user's origin station to filter out meaningless predictions
        // Only pass if not nil and not empty
        if let fromStation = fromStationCode, !fromStation.isEmpty {
            queryItems.append(URLQueryItem(name: "from_station", value: fromStation))
        }

        // Pass data source to filter to specific transit system (NJT, AMTRAK, PATH, PATCO)
        // This avoids ambiguity when train IDs collide between systems
        if let source = dataSource, !source.isEmpty {
            queryItems.append(URLQueryItem(name: "data_source", value: source))
        }

        components.queryItems = queryItems
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }

        // PERFORMANCE: Use retry logic for transient network failures
        return try await executeWithRetry {
            let (data, response) = try await self.session.data(from: url)

            if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 404 {
                throw APIError.noData
            }

            do {
                let detailsResponse = try self.decoder.decode(V2TrainDetailsResponse.self, from: data)
                return self.adaptV2TrainDetailsToTrainV2(detailsResponse.train, fromStationCode: fromStationCode, trackPrediction: detailsResponse.trackPrediction)
            } catch {
                print("🔴 V2 DECODING ERROR (fetchTrainDetails for id: \(id)): \(error)")
                throw error
            }
        }
    }
    
    // MARK: - Train by Number
    
    func fetchTrainByNumber(_ number: String, fromStationCode: String? = nil) async throws -> TrainV2 {
        // V2 backend doesn't support search by train number in list endpoint
        // So we try to fetch details directly
        return try await fetchTrainDetails(id: number, fromStationCode: fromStationCode)
    }
    
    // MARK: - Flexible Train Details

    func fetchTrainDetailsFlexible(id: String? = nil, trainId: String? = nil, fromStationCode: String? = nil, date: Date? = nil, dataSource: String? = nil) async throws -> TrainV2 {
        let trainNumber = id ?? trainId ?? ""
        return try await fetchTrainDetails(id: trainNumber, fromStationCode: fromStationCode, date: date, dataSource: dataSource)
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

        let (data, _) = try await session.data(from: url)
        
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
        days: Int = 365,
        hours: Int? = nil
    ) async throws -> RouteHistoricalData {
        var urlComponents = URLComponents(string: "\(baseURL)/v2/routes/history")!
        urlComponents.queryItems = [
            URLQueryItem(name: "from_station", value: from),
            URLQueryItem(name: "to_station", value: to),
            URLQueryItem(name: "data_source", value: dataSource),
            URLQueryItem(name: "days", value: String(days))
        ]

        if let hours = hours {
            urlComponents.queryItems?.append(URLQueryItem(name: "hours", value: String(hours)))
        }

        if let highlightTrain = highlightTrain {
            urlComponents.queryItems?.append(URLQueryItem(name: "highlight_train", value: highlightTrain))
        }
        
        guard let url = urlComponents.url else {
            throw APIError.invalidURL
        }
        
        let (data, _) = try await session.data(from: url)

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
                let baselineTrainCount: Double?

                private enum CodingKeys: String, CodingKey {
                    case fromStation = "from_station"
                    case toStation = "to_station"
                    case totalTrains = "total_trains"
                    case dataSource = "data_source"
                    case baselineTrainCount = "baseline_train_count"
                }
            }
            
            struct AggregateStats: Decodable {
                let onTimePercentage: Double
                let averageDelayMinutes: Double
                let averageDepartureDelayMinutes: Double?
                let cancellationRate: Double
                let delayBreakdown: DelayBreakdown
                let trackUsageAtOrigin: [String: Int]

                private enum CodingKeys: String, CodingKey {
                    case onTimePercentage = "on_time_percentage"
                    case averageDelayMinutes = "average_delay_minutes"
                    case averageDepartureDelayMinutes = "average_departure_delay_minutes"
                    case cancellationRate = "cancellation_rate"
                    case delayBreakdown = "delay_breakdown"
                    case trackUsageAtOrigin = "track_usage_at_origin"
                }
            }
            
            struct HighlightedTrainStats: Decodable {
                let trainId: String
                let onTimePercentage: Double
                let averageDelayMinutes: Double
                let averageDepartureDelayMinutes: Double?
                let delayBreakdown: DelayBreakdown
                let trackUsageAtOrigin: [String: Int]

                private enum CodingKeys: String, CodingKey {
                    case trainId = "train_id"
                    case onTimePercentage = "on_time_percentage"
                    case averageDelayMinutes = "average_delay_minutes"
                    case averageDepartureDelayMinutes = "average_departure_delay_minutes"
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
                dataSource: response.route.dataSource,
                baselineTrainCount: response.route.baselineTrainCount
            ),
            aggregateStats: RouteHistoricalData.Stats(
                onTimePercentage: response.aggregateStats.onTimePercentage,
                averageDelayMinutes: response.aggregateStats.averageDelayMinutes,
                averageDepartureDelayMinutes: response.aggregateStats.averageDepartureDelayMinutes ?? 0,
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
                    averageDepartureDelayMinutes: highlighted.averageDepartureDelayMinutes ?? 0,
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
    
    func fetchCongestionData(timeWindowHours: Int = 1) async throws -> CongestionMapResponse {
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
        
        #if DEBUG
        print("📱 Registering Live Activity token (V2):")
        print("  Token: \(pushToken.prefix(10))...")
        print("  Train: \(trainNumber)")
        print("  Route: \(originCode) → \(destinationCode)")
        #endif
        
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
        let components = URLComponents(string: "\(baseURL)/v2/trains/stations/\(stationCode)/tracks/occupied")!
        
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
    
    func fetchCongestionData(timeWindowHours: Int = 1, maxPerSegment: Int = 100, dataSource: String? = nil) async throws -> CongestionMapResponse {
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

    // MARK: - Operations Summary

    /// Fetch operations summary for network, route, or train scope
    /// - Parameters:
    ///   - scope: Summary scope (network, route, or train)
    ///   - fromStation: Origin station code (required for route, optional for train)
    ///   - toStation: Destination station code (required for route)
    ///   - trainId: Train ID (required for train scope)
    ///   - dataSource: Optional filter by NJT or AMTRAK
    /// - Returns: OperationsSummaryResponse with headline and body
    func fetchOperationsSummary(
        scope: SummaryScope,
        fromStation: String? = nil,
        toStation: String? = nil,
        trainId: String? = nil,
        dataSource: String? = nil
    ) async throws -> OperationsSummaryResponse {
        var components = URLComponents(string: "\(baseURL)/v2/routes/summary")!
        var queryItems: [URLQueryItem] = [
            URLQueryItem(name: "scope", value: scope.rawValue)
        ]

        if let fromStation = fromStation {
            queryItems.append(URLQueryItem(name: "from_station", value: fromStation))
        }

        if let toStation = toStation {
            queryItems.append(URLQueryItem(name: "to_station", value: toStation))
        }

        if let trainId = trainId {
            queryItems.append(URLQueryItem(name: "train_id", value: trainId))
        }

        if let dataSource = dataSource {
            queryItems.append(URLQueryItem(name: "data_source", value: dataSource))
        }

        components.queryItems = queryItems

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        print("📊 Fetching operations summary from: \(url)")

        let (data, response) = try await session.data(from: url)

        if let httpResponse = response as? HTTPURLResponse {
            if httpResponse.statusCode == 400 {
                throw APIError.invalidParameters
            } else if httpResponse.statusCode != 200 {
                throw APIError.noData
            }
        }

        do {
            let response = try decoder.decode(OperationsSummaryResponse.self, from: data)
            print("✅ Operations summary decoded: \(response.headline)")
            return response
        } catch {
            print("🔴 DECODING ERROR (fetchOperationsSummary): \(error)")
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
            journeyDate: departure.journeyDate,
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
            observationType: departure.observationType,
            isCancelled: departure.isCancelled,
            cancellationReason: departure.cancellationReason,
            isCompleted: false, // Departures are never completed at search time
            dataSource: departure.dataSource,
            stops: nil
        )
    }

    private func adaptV2TripOption(_ option: V2TripOption) -> TripOption {
        let legs = option.legs.map { leg in
            TripLeg(
                trainId: leg.trainId,
                journeyDate: leg.journeyDate,
                line: LineInfo(
                    code: leg.line.code,
                    name: leg.line.name,
                    color: leg.line.color
                ),
                dataSource: leg.dataSource,
                destination: leg.destination,
                boarding: StationTiming(
                    code: leg.boarding.code,
                    name: leg.boarding.name,
                    scheduledTime: leg.boarding.scheduledTime,
                    updatedTime: leg.boarding.updatedTime,
                    actualTime: leg.boarding.actualTime,
                    track: leg.boarding.track
                ),
                alighting: StationTiming(
                    code: leg.alighting.code,
                    name: leg.alighting.name,
                    scheduledTime: leg.alighting.scheduledTime,
                    updatedTime: leg.alighting.updatedTime,
                    actualTime: leg.alighting.actualTime,
                    track: leg.alighting.track
                ),
                observationType: leg.observationType,
                isCancelled: leg.isCancelled,
                trainPosition: leg.trainPosition.map {
                    TrainPosition(
                        lastDepartedStationCode: $0.lastDepartedStationCode,
                        atStationCode: $0.atStationCode,
                        nextStationCode: $0.nextStationCode
                    )
                }
            )
        }

        let transfers = option.transfers.map { transfer in
            TransferInfo(
                fromStation: SimpleStation(code: transfer.fromStation.code, name: transfer.fromStation.name),
                toStation: SimpleStation(code: transfer.toStation.code, name: transfer.toStation.name),
                walkMinutes: transfer.walkMinutes,
                sameStation: transfer.sameStation
            )
        }

        return TripOption(
            legs: legs,
            transfers: transfers,
            departureTime: option.departureTime,
            arrivalTime: option.arrivalTime,
            totalDurationMinutes: option.totalDurationMinutes,
            isDirect: option.isDirect
        )
    }

    private func adaptV2TrainDetailsToTrainV2(_ details: V2TrainDetails, fromStationCode: String?, trackPrediction: V2TrackPrediction? = nil) -> TrainV2 {
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
                hasDepartedStation: stop.hasDepartedStation,
                predictedArrival: stop.predictedArrival,
                predictedArrivalSamples: stop.predictedArrivalSamples
            )
        }
        
        // Create departure timing from first stop or requested station
        let departureTiming: StationTiming
        if let fromCode = fromStationCode,
           let requestedStop = details.stops.first(where: { Stations.areEquivalentStations($0.station.code, fromCode) }) {
            departureTiming = StationTiming(
                code: fromCode,
                name: Stations.stationName(forCode: fromCode) ?? requestedStop.station.name,
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
            journeyDate: details.journeyDate,
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
            observationType: details.observationType,
            isCancelled: details.isCancelled,
            cancellationReason: details.cancellationReason,
            isCompleted: details.isCompleted,
            dataSource: details.dataSource,
            stops: stops,
            trackPrediction: trackPrediction
        )
    }

    // MARK: - Platform Predictions
    
    func getPlatformPrediction(
        stationCode: String,
        trainId: String,
        journeyDate: Date
    ) async throws -> PlatformPrediction {
        var components = URLComponents(string: "\(baseURL)/v2/predictions/track")!

        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"
        dateFormatter.timeZone = TimeZone(identifier: "America/New_York")
        let dateString = dateFormatter.string(from: journeyDate)

        components.queryItems = [
            URLQueryItem(name: "station_code", value: stationCode),
            URLQueryItem(name: "train_id", value: trainId),
            URLQueryItem(name: "journey_date", value: dateString)
        ]

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        print("🌐 [APIService] Fetching predictions from: \(url.absoluteString)")

        let (data, response) = try await session.data(from: url)

        if let httpResponse = response as? HTTPURLResponse {
            print("📡 [APIService] Response status: \(httpResponse.statusCode)")
            if httpResponse.statusCode != 200 {
                print("⚠️ [APIService] Non-200 status code")
                if let responseStr = String(data: data, encoding: .utf8) {
                    print("   Response body: \(responseStr)")
                }
            }
        }

        do {
            // Try to decode the response
            let prediction = try decoder.decode(PlatformPrediction.self, from: data)
            print("✅ [APIService] Successfully decoded platform prediction")
            return prediction
        } catch {
            print("❌ [APIService] Decoding error: \(error)")
            if let responseStr = String(data: data, encoding: .utf8) {
                print("   Raw response: \(responseStr.prefix(500))...")
            }
            throw error
        }
    }

    // MARK: - Delay Forecasts

    /// Get delay and cancellation forecast for a train
    func getDelayForecast(
        trainId: String,
        stationCode: String,
        journeyDate: Date
    ) async throws -> DelayForecastResponse {
        var components = URLComponents(string: "\(baseURL)/v2/predictions/delay")!

        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"
        dateFormatter.timeZone = TimeZone(identifier: "America/New_York")
        let dateString = dateFormatter.string(from: journeyDate)

        components.queryItems = [
            URLQueryItem(name: "train_id", value: trainId),
            URLQueryItem(name: "station_code", value: stationCode),
            URLQueryItem(name: "journey_date", value: dateString)
        ]

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        print("🌐 [APIService] Fetching delay forecast from: \(url.absoluteString)")

        let (data, response) = try await session.data(from: url)

        if let httpResponse = response as? HTTPURLResponse {
            print("📡 [APIService] Response status: \(httpResponse.statusCode)")
            if httpResponse.statusCode != 200 {
                print("⚠️ [APIService] Non-200 status code")
                if let responseStr = String(data: data, encoding: .utf8) {
                    print("   Response body: \(responseStr)")
                }
            }
        }

        do {
            let forecast = try decoder.decode(DelayForecastResponse.self, from: data)
            print("✅ [APIService] Successfully decoded delay forecast")
            return forecast
        } catch {
            print("❌ [APIService] Decoding error: \(error)")
            if let responseStr = String(data: data, encoding: .utf8) {
                print("   Raw response: \(responseStr.prefix(500))...")
            }
            throw error
        }
    }

    // MARK: - User Feedback

    /// Submit user feedback about data issues
    func submitFeedback(
        message: String,
        screen: String,
        trainId: String? = nil,
        originCode: String? = nil,
        destinationCode: String? = nil
    ) async throws {
        let endpoint = "/v2/feedback"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw APIError.invalidURL
        }

        struct FeedbackRequest: Encodable {
            let message: String
            let screen: String
            let train_id: String?
            let origin_code: String?
            let destination_code: String?
            let app_version: String?
            let device_model: String?
        }

        let appVersion = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String
        var deviceModel = "Unknown"
        var systemInfo = utsname()
        uname(&systemInfo)
        deviceModel = withUnsafePointer(to: &systemInfo.machine) {
            $0.withMemoryRebound(to: CChar.self, capacity: 1) {
                String(validatingUTF8: $0) ?? "Unknown"
            }
        }

        let body = FeedbackRequest(
            message: message,
            screen: screen,
            train_id: trainId,
            origin_code: originCode,
            destination_code: destinationCode,
            app_version: appVersion,
            device_model: deviceModel
        )

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)

        let (_, response) = try await session.data(for: request)

        if let httpResponse = response as? HTTPURLResponse {
            if httpResponse.statusCode != 200 && httpResponse.statusCode != 201 {
                throw APIError.invalidParameters
            }
        }

        print("✅ Feedback submitted successfully")
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

// MARK: - Platform Prediction Models

/// Response from the ML platform prediction API
struct PlatformPrediction: Codable {
    let platformProbabilities: [String: Double]
    let primaryPrediction: String
    let confidence: Double
    let top3: [String]
    let modelVersion: String
    let stationCode: String
    let trainId: String
    // featuresUsed field removed - no longer needed after migration to historical predictor

    enum CodingKeys: String, CodingKey {
        case platformProbabilities = "platform_probabilities"
        case primaryPrediction = "primary_prediction"
        case confidence
        case top3 = "top_3"
        case modelVersion = "model_version"
        case stationCode = "station_code"
        case trainId = "train_id"
        // featuresUsed removed from CodingKeys after historical predictor migration
    }
}

// PredictionFeatures struct removed - obsolete after migration from ML to historical predictor

// MARK: - Platform to Track Mapping

extension PlatformPrediction {
    /// Convert platform probabilities to individual track probabilities
    /// For NY Penn: platforms like "1 & 2" are split into individual tracks
    /// For other stations: track = platform, so return as-is
    func convertToTrackProbabilities() -> [String: Double] {
        // Only NY Penn has platform groupings (multiple tracks per platform)
        // For all other stations, platform = track, so return as-is
        guard stationCode == "NY" else {
            return platformProbabilities
        }

        var trackProbabilities: [String: Double] = [:]

        // Platform to tracks mapping for NY Penn Station
        let platformToTracks: [String: [String]] = [
            "1 & 2": ["1", "2"],
            "3 & 4": ["3", "4"],
            "5 & 6": ["5", "6"],
            "7 & 8": ["7", "8"],
            "9 & 10": ["9", "10"],
            "11 & 12": ["11", "12"],
            "13 & 14": ["13", "14"],
            "15 & 16": ["15", "16"],
            "17": ["17"],
            "18 & 19": ["18", "19"],
            "20 & 21": ["20", "21"]
        ]

        // Convert platform probabilities to track probabilities
        for (platform, probability) in platformProbabilities {
            if let tracks = platformToTracks[platform] {
                // Split probability evenly among tracks in the platform
                let probabilityPerTrack = probability / Double(tracks.count)

                for track in tracks {
                    trackProbabilities[track] = probabilityPerTrack
                }
            }
        }

        return trackProbabilities
    }
}

// MARK: - Route Alert Subscriptions

extension APIService {
    func registerDevice(deviceId: String, apnsToken: String) async throws {
        let endpoint = "/v2/devices/register"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw APIError.invalidURL
        }

        struct RegisterRequest: Encodable {
            let device_id: String
            let apns_token: String
        }

        let body = RegisterRequest(device_id: deviceId, apns_token: apnsToken)

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)

        let (_, response) = try await session.data(for: request)
        if let httpResponse = response as? HTTPURLResponse,
           httpResponse.statusCode != 200 && httpResponse.statusCode != 201 {
            throw APIError.invalidParameters
        }
    }

    func syncAlertSubscriptions(deviceId: String, subscriptions: [RouteAlertSubscription]) async throws {
        let endpoint = "/v2/alerts/subscriptions"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw APIError.invalidURL
        }

        struct SubscriptionItem: Encodable {
            let data_source: String
            let line_id: String?
            let from_station_code: String?
            let to_station_code: String?
            let train_id: String?
            let direction: String?
            let weekdays_only: Bool
        }

        struct SyncRequest: Encodable {
            let device_id: String
            let subscriptions: [SubscriptionItem]
        }

        let items = subscriptions.map { sub in
            SubscriptionItem(
                data_source: sub.dataSource,
                line_id: sub.lineId,
                from_station_code: sub.fromStationCode,
                to_station_code: sub.toStationCode,
                train_id: sub.trainId,
                direction: sub.direction,
                weekdays_only: sub.weekdaysOnly
            )
        }

        let body = SyncRequest(device_id: deviceId, subscriptions: items)

        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)

        let (_, response) = try await session.data(for: request)
        if let httpResponse = response as? HTTPURLResponse,
           httpResponse.statusCode != 200 && httpResponse.statusCode != 201 {
            throw APIError.invalidParameters
        }
    }
}
