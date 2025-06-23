import Foundation
import Combine

// Helper to handle multiple ISO8601 date formats
extension Formatter {
    static let iso8601withFractionalSeconds: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSS"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(identifier: "America/New_York") // Assume Eastern Time
        return formatter
    }()
    
    static let iso8601withFractionalSecondsAndTimezone: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSXXXXX"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        return formatter
    }()
    
    // Changed to standard DateFormatter for more control over format without fractional seconds
    static let customISO8601withoutFractionalSeconds: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        formatter.locale = Locale(identifier: "en_US_POSIX") // Essential for specific formats
        formatter.timeZone = TimeZone(identifier: "America/New_York")    // Assume Eastern Time if no offset provided
        return formatter
    }()
    
    static let customISO8601withTimezone: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ssXXXXX"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        return formatter
    }()
}

extension Date {
    static func fromISO8601(_ string: String) -> Date? {
        // Try different date formats in order of likelihood
        
        // 1. With timezone offset and fractional seconds
        if let date = Formatter.iso8601withFractionalSecondsAndTimezone.date(from: string) {
            return date
        }
        
        // 2. With timezone offset but no fractional seconds
        if let date = Formatter.customISO8601withTimezone.date(from: string) {
            return date
        }
        
        // 3. Remove 'Z' suffix if present to treat as Eastern Time
        let cleanedString = string.hasSuffix("Z") ? String(string.dropLast()) : string
        
        // 4. Try with fractional seconds (no timezone)
        if let date = Formatter.iso8601withFractionalSeconds.date(from: cleanedString) {
            return date
        }
        
        // 5. Try without fractional seconds (no timezone)
        if let date = Formatter.customISO8601withoutFractionalSeconds.date(from: cleanedString) {
            return date
        }
        
        // 6. Fallback: if the original string had 'Z', try standard ISO8601 parsing
        if string.hasSuffix("Z") {
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = formatter.date(from: string) {
                return date
            }
            formatter.formatOptions = [.withInternetDateTime]
            return formatter.date(from: string)
        }
        
        return nil
    }
}

// MARK: - API Service
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
    func searchTrains(fromStationCode: String, toStationCode: String) async throws -> [Train] {
        // Format current time as Eastern Time without timezone suffix
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        let currentTime = formatter.string(from: Date())
        
        var components = URLComponents(string: "\(baseURL)/trains/")!
        components.queryItems = [
            URLQueryItem(name: "from_station_code", value: fromStationCode),
            URLQueryItem(name: "to_station_code", value: toStationCode),
            URLQueryItem(name: "departure_time_after", value: currentTime),
            URLQueryItem(name: "limit", value: "100"),
            URLQueryItem(name: "consolidate", value: "true")
        ]
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        let (data, _) = try await session.data(from: url)
        
        do {
            let response = try decoder.decode(TrainListResponse.self, from: data)
            return response.trains
        } catch {
            print("🔴 DECODING ERROR (searchTrains): \(error)") // Detailed error print
            print("🔴 RAW ERROR OBJECT (searchTrains): \(String(describing: error))")
            
            // Print raw data on error too
            if let jsonString = String(data: data, encoding: .utf8) {
                print("🔴 RAW DATA THAT FAILED TO DECODE:")
                print(jsonString)
            }
            
            throw error // Re-throw the original error to see it in the UI if not caught elsewhere
        }
    }
    
    // MARK: - Train Details
    func fetchTrainDetails(id: String, fromStationCode: String? = nil) async throws -> Train {
        var urlString = "\(baseURL)/trains/\(id)"
        if let fromCode = fromStationCode {
            urlString += "?from_station_code=\(fromCode)"
        }
        let url = URL(string: urlString)!
        do {
            let (data, _) = try await session.data(from: url)
            // print(String(data: data, encoding: .utf8) ?? "Could not print data") // Optional: for debugging
            return try decoder.decode(Train.self, from: data)
        } catch {
            print("🔴 DECODING ERROR (fetchTrainDetails for id: \(id)): \(error)") // Detailed error print
            print("🔴 RAW ERROR OBJECT (fetchTrainDetails for id: \(id)): \(String(describing: error))")
            if let decodingError = error as? DecodingError {
                print("🔴 DECODING ERROR DETAILS: \(decodingError.localizedDescription)")
                switch decodingError {
                case .typeMismatch(let type, let context):
                    print("🔴 Type Mismatch: type '\(type)' mismatched for '\(context.codingPath.map { $0.stringValue }.joined(separator: "."))'")
                    print("🔴 Context: \(context.debugDescription)")
                case .valueNotFound(let type, let context):
                    print("🔴 Value Not Found: no value was found for type '\(type)' at '\(context.codingPath.map { $0.stringValue }.joined(separator: "."))'")
                    print("🔴 Context: \(context.debugDescription)")
                case .keyNotFound(let key, let context):
                    print("🔴 Key Not Found: key '\(key.stringValue)' not found at '\(context.codingPath.map { $0.stringValue }.joined(separator: "."))'")
                    print("🔴 Context: \(context.debugDescription)")
                case .dataCorrupted(let context):
                    print("🔴 Data Corrupted: data corrupted at '\(context.codingPath.map { $0.stringValue }.joined(separator: "."))'")
                    print("🔴 Context: \(context.debugDescription)")
                @unknown default:
                    print("🔴 Unknown decoding error: \(decodingError)")
                }
            }
            throw error // Re-throw the original error
        }
    }
    
    // MARK: - Train by Number (Legacy)
    func fetchTrainByNumber(_ number: String, fromStationCode: String? = nil) async throws -> Train {
        var components = URLComponents(string: "\(baseURL)/trains/")!
        let queryItems = [
            URLQueryItem(name: "train_id", value: number),
            URLQueryItem(name: "sort_by", value: "departure_time"),
            URLQueryItem(name: "sort_order", value: "desc"),
            URLQueryItem(name: "limit", value: "1"),
            URLQueryItem(name: "consolidate", value: "true")
        ]
        
        components.queryItems = queryItems
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        do {
            let (data, response) = try await session.data(from: url)
            
            // Log the HTTP response status
            if let httpResponse = response as? HTTPURLResponse {
                print("📡 HTTP Response for train \(number): Status \(httpResponse.statusCode)")
                if httpResponse.statusCode != 200 {
                    print("🔴 Non-200 status code: \(httpResponse.statusCode)")
                }
            }
            
            // Log raw data size
            print("📊 Response data size for train \(number): \(data.count) bytes")
            
            // Log the raw response for debugging
            if let responseString = String(data: data, encoding: .utf8) {
                print("📄 Raw response preview (first 500 chars): \(String(responseString.prefix(500)))")
            }
            
            // Try to decode the response
            let trainResponse = try decoder.decode(TrainListResponse.self, from: data)
            
            print("✅ Successfully decoded response with \(trainResponse.trains.count) trains")
            
            // Since we're expecting exactly one train with limit=1, get the first one
            guard let train = trainResponse.trains.first else {
                print("🔴 No trains in response for train \(number) - throwing APIError.noData")
                throw APIError.noData
            }
            
            return train
        } catch {
            print("🔴 ERROR (fetchTrainByNumber for number: \(number)): \(error)") // Detailed error print
            print("🔴 ERROR TYPE: \(type(of: error))")
            print("🔴 RAW ERROR OBJECT (fetchTrainByNumber for number: \(number)): \(String(describing: error))")
            if let decodingError = error as? DecodingError {
                print("🔴 DECODING ERROR DETAILS: \(decodingError.localizedDescription)")
                switch decodingError {
                case .typeMismatch(let type, let context):
                    print("🔴 Type Mismatch: type '\(type)' mismatched for '\(context.codingPath.map { $0.stringValue }.joined(separator: "."))'")
                    print("🔴 Context: \(context.debugDescription)")
                case .valueNotFound(let type, let context):
                    print("🔴 Value Not Found: no value was found for type '\(type)' at '\(context.codingPath.map { $0.stringValue }.joined(separator: "."))'")
                    print("🔴 Context: \(context.debugDescription)")
                case .keyNotFound(let key, let context):
                    print("🔴 Key Not Found: key '\(key.stringValue)' not found at '\(context.codingPath.map { $0.stringValue }.joined(separator: "."))'")
                    print("🔴 Context: \(context.debugDescription)")
                case .dataCorrupted(let context):
                    print("🔴 Data Corrupted: data corrupted at '\(context.codingPath.map { $0.stringValue }.joined(separator: "."))'")
                    print("🔴 Context: \(context.debugDescription)")
                @unknown default:
                    print("🔴 Unknown decoding error: \(decodingError)")
                }
            }
            throw error // Re-throw the original error
        }
    }
    
    // MARK: - Consolidated Train Query
    func fetchTrainByTrainId(_ trainId: String, fromStationCode: String? = nil, sinceHoursAgo: Int = 6, consolidate: Bool = true) async throws -> [Train] {
        print("🔍 fetchTrainByTrainId called for: \(trainId)")
        
        // Calculate time filter (6 hours ago by default)
        let timeFilter = Date().addingTimeInterval(-Double(sinceHoursAgo) * 3600)
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        let departureTimeAfter = formatter.string(from: timeFilter)
        
        var components = URLComponents(string: "\(baseURL)/trains/")!
        var queryItems = [
            URLQueryItem(name: "train_id", value: trainId),
            URLQueryItem(name: "departure_time_after", value: departureTimeAfter),
            URLQueryItem(name: "consolidate", value: String(consolidate)),
            URLQueryItem(name: "show_sources", value: "true"),
            URLQueryItem(name: "include_predictions", value: "true")
        ]
        
        // Add from_station_code if provided
        if let fromStationCode = fromStationCode {
            queryItems.append(URLQueryItem(name: "from_station_code", value: fromStationCode))
        }
        
        components.queryItems = queryItems
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        do {
            let (data, response) = try await session.data(from: url)
            
            // Log the HTTP response
            if let httpResponse = response as? HTTPURLResponse {
                print("📡 HTTP Response for trainId \(trainId): Status \(httpResponse.statusCode)")
            }
            
            print("📊 Response data size for trainId \(trainId): \(data.count) bytes")
            
            let trainResponse = try decoder.decode(TrainListResponse.self, from: data)
            print("✅ fetchTrainByTrainId decoded \(trainResponse.trains.count) trains for trainId: \(trainId)")
            
            return trainResponse.trains
        } catch {
            print("🔴 DECODING ERROR (fetchTrainByTrainId for trainId: \(trainId)): \(error)")
            print("🔴 RAW ERROR OBJECT (fetchTrainByTrainId for trainId: \(trainId)): \(String(describing: error))")
            if let decodingError = error as? DecodingError {
                print("🔴 DECODING ERROR DETAILS: \(decodingError.localizedDescription)")
                switch decodingError {
                case .typeMismatch(let type, let context):
                    print("🔴 Type Mismatch: type '\(type)' mismatched for '\(context.codingPath.map { $0.stringValue }.joined(separator: "."))'")
                    print("🔴 Context: \(context.debugDescription)")
                case .valueNotFound(let type, let context):
                    print("🔴 Value Not Found: no value was found for type '\(type)' at '\(context.codingPath.map { $0.stringValue }.joined(separator: "."))'")
                    print("🔴 Context: \(context.debugDescription)")
                case .keyNotFound(let key, let context):
                    print("🔴 Key Not Found: key '\(key.stringValue)' not found at '\(context.codingPath.map { $0.stringValue }.joined(separator: "."))'")
                    print("🔴 Context: \(context.debugDescription)")
                case .dataCorrupted(let context):
                    print("🔴 Data Corrupted: data corrupted at '\(context.codingPath.map { $0.stringValue }.joined(separator: "."))'")
                    print("🔴 Context: \(context.debugDescription)")
                @unknown default:
                    print("🔴 Unknown decoding error: \(decodingError)")
                }
            }
            throw error
        }
    }
    
    // MARK: - Flexible Train Details
    func fetchTrainDetailsFlexible(id: String? = nil, trainId: String? = nil, fromStationCode: String? = nil) async throws -> Train {
        // If we have a database ID and station code, use existing method
        if let id = id, let fromCode = fromStationCode {
            return try await fetchTrainDetails(id: id, fromStationCode: fromCode)
        }
        
        // If we have a database ID but no station code, try without
        if let id = id {
            return try await fetchTrainDetails(id: id)
        }
        
        // Otherwise, use train_id query with consolidation
        guard let trainId = trainId else {
            throw APIError.invalidParameters
        }
        
        print("🔍 fetchTrainDetailsFlexible: Using fetchTrainByTrainId for trainId: \(trainId)")
        let trains = try await fetchTrainByTrainId(trainId, fromStationCode: fromStationCode)
        print("📊 fetchTrainDetailsFlexible: Got \(trains.count) trains for trainId: \(trainId)")
        
        // If we have a station code, filter for trains that stop there
        if let fromCode = fromStationCode {
            print("🔍 fetchTrainDetailsFlexible: Filtering by station code: \(fromCode)")
            let filtered = trains.filter { train in
                guard let stops = train.stops else { return false }
                return stops.contains { stop in
                    Stations.stationMatches(stop, stationCode: fromCode)
                }
            }
            print("📊 fetchTrainDetailsFlexible: \(filtered.count) trains stop at \(fromCode)")
            if let train = filtered.first {
                return train
            }
        }
        
        // Return most recent train (should typically be only one)
        guard let train = trains.first else {
            print("🔴 fetchTrainDetailsFlexible: No trains found - throwing APIError.noData")
            throw APIError.noData
        }
        
        return train
    }
    
    // MARK: - Historical Data
    func fetchHistoricalData(for train: Train, fromStationCode: String, toStationCode: String) async throws -> HistoricalData {
        async let trainHistoryTask = fetchTrainHistory(trainId: train.trainId, fromStationCode: fromStationCode, toStationCode: toStationCode)
        async let lineHistoryTask = fetchLineHistory(line: train.line, fromStationCode: fromStationCode, toStationCode: toStationCode)
        async let destinationHistoryTask = fetchDestinationHistory(destination: train.destination, fromStationCode: fromStationCode, toStationCode: toStationCode)
        
        let (trainHistory, lineHistory, destinationHistory) = try await (trainHistoryTask, lineHistoryTask, destinationHistoryTask)
        
        return HistoricalData(
            trainStats: calculateDelayStats(from: trainHistory),
            lineStats: calculateDelayStats(from: lineHistory),
            destinationStats: calculateDelayStats(from: destinationHistory),
            trainTrackStats: calculateTrackStats(from: trainHistory, fromStation: fromStationCode),
            lineTrackStats: calculateTrackStats(from: lineHistory, fromStation: fromStationCode),
            destinationTrackStats: calculateTrackStats(from: destinationHistory, fromStation: fromStationCode)
        )
    }
    
    private func fetchTrainHistory(trainId: String, fromStationCode: String, toStationCode: String) async throws -> [Train] {
        var components = URLComponents(string: "\(baseURL)/trains/")!
        let queryItems = [
            URLQueryItem(name: "train_id", value: trainId),
            URLQueryItem(name: "no_pagination", value: "true"),
            URLQueryItem(name: "from_station_code", value: fromStationCode),
            URLQueryItem(name: "to_station_code", value: toStationCode),
            URLQueryItem(name: "consolidate", value: "true")
        ]
        components.queryItems = queryItems
        
        guard let url = components.url else { throw APIError.invalidURL }
        do {
            let (data, _) = try await session.data(from: url)
            let response = try decoder.decode(TrainListResponse.self, from: data)
            return response.trains
        } catch {
            print("🔴 DECODING ERROR (fetchTrainHistory for trainId: \(trainId)): \(error)")
            print("🔴 RAW ERROR OBJECT (fetchTrainHistory for trainId: \(trainId)): \(String(describing: error))")
            throw error
        }
    }
    
    private func fetchLineHistory(line: String, fromStationCode: String, toStationCode: String) async throws -> [Train] {
        var components = URLComponents(string: "\(baseURL)/trains/")!
        let queryItems = [
            URLQueryItem(name: "line", value: line),
            URLQueryItem(name: "limit", value: "1000"),
            URLQueryItem(name: "from_station_code", value: fromStationCode),
            URLQueryItem(name: "to_station_code", value: toStationCode),
            URLQueryItem(name: "consolidate", value: "true")
        ]
        components.queryItems = queryItems
        
        guard let url = components.url else { throw APIError.invalidURL }
        do {
            let (data, _) = try await session.data(from: url)
            let response = try decoder.decode(TrainListResponse.self, from: data)
            return response.trains
        } catch {
            print("🔴 DECODING ERROR (fetchLineHistory for line: \(line)): \(error)")
            print("🔴 RAW ERROR OBJECT (fetchLineHistory for line: \(line)): \(String(describing: error))")
            throw error
        }
    }
    
    private func fetchDestinationHistory(destination: String, fromStationCode: String, toStationCode: String) async throws -> [Train] {
        var components = URLComponents(string: "\(baseURL)/trains/")!
        let queryItems = [
            URLQueryItem(name: "destination", value: destination),
            URLQueryItem(name: "limit", value: "1000"),
            URLQueryItem(name: "from_station_code", value: fromStationCode),
            URLQueryItem(name: "to_station_code", value: toStationCode),
            URLQueryItem(name: "consolidate", value: "true")
        ]
        components.queryItems = queryItems
        
        guard let url = components.url else { throw APIError.invalidURL }
        do {
            let (data, _) = try await session.data(from: url)
            let response = try decoder.decode(TrainListResponse.self, from: data)
            return response.trains
        } catch {
            print("🔴 DECODING ERROR (fetchDestinationHistory for destination: \(destination)): \(error)")
            print("🔴 RAW ERROR OBJECT (fetchDestinationHistory for destination: \(destination)): \(String(describing: error))")
            throw error
        }
    }
    
    // MARK: - Statistics Calculation
    private func calculateDelayStats(from trains: [Train]) -> DelayStats? {
        let departedTrains = trains.filter { $0.status == .departed && $0.delayMinutes != nil }
        guard !departedTrains.isEmpty else { return nil }
        
        var onTime = 0
        var slight = 0
        var significant = 0
        var major = 0
        var totalDelay = 0
        
        for train in departedTrains {
            let delay = train.delayMinutes ?? 0
            totalDelay += delay
            
            switch delay {
            case 0...1: onTime += 1
            case 2...19: slight += 1
            case 20...59: significant += 1
            default: major += 1
            }
        }
        
        let total = departedTrains.count
        return DelayStats(
            onTime: Int((Double(onTime) / Double(total)) * 100),
            slight: Int((Double(slight) / Double(total)) * 100),
            significant: Int((Double(significant) / Double(total)) * 100),
            major: Int((Double(major) / Double(total)) * 100),
            total: total,
            avgDelay: total > 0 ? totalDelay / total : 0
        )
    }
    
    private func calculateTrackStats(from trains: [Train], fromStation: String?) -> TrackStats? {
        var trackCounts: [String: Int] = [:]
        var totalTrainsWithTracks = 0
        
        for train in trains {
            var trackUsed = false
            
            // If we have a fromStation and the train has stops, look for platform data
            if let fromStation = fromStation, let stops = train.stops {
                // Find the stop that matches the fromStation
                if let departureStop = stops.first(where: { stop in
                    stop.stationCode == fromStation
                }), let platform = departureStop.platform, !platform.isEmpty {
                    // Use the platform from the specific stop
                    trackCounts[platform, default: 0] += 1
                    totalTrainsWithTracks += 1
                    trackUsed = true
                }
            }
            
            // Fallback to train track if no platform was used
            if !trackUsed, let track = train.track, !track.isEmpty {
                trackCounts[track, default: 0] += 1
                totalTrainsWithTracks += 1
            }
        }
        
        guard totalTrainsWithTracks > 0 else { return nil }
        
        let sortedTracks = trackCounts.sorted { $0.value > $1.value }
            .map { (track: $0.key, percentage: Int((Double($0.value) / Double(totalTrainsWithTracks)) * 100), count: $0.value) }
        
        return TrackStats(tracks: sortedTracks, total: totalTrainsWithTracks)
    }
    
    // MARK: - Push Notification Registration
    
    /// Register device token for push notifications
    func registerDeviceToken(_ token: String) async throws {
        let url = URL(string: "\(baseURL)/device-tokens/")!
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
    
    /// Register Live Activity push token
    func registerLiveActivityToken(_ token: String, for trainId: String, deviceToken: String? = nil) async throws {
        let url = URL(string: "\(baseURL)/live-activities/register")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        var payload: [String: Any] = [
            "train_id": trainId,
            "push_token": token,
            "platform": "ios",
            "timestamp": ISO8601DateFormatter().string(from: Date())
        ]
        
        // Include device token if available for linking regular notifications
        if let deviceToken = deviceToken {
            payload["device_token"] = deviceToken
        }
        
        request.httpBody = try JSONSerialization.data(withJSONObject: payload)
        
        // Debug logging
        print("📱 Live Activity registration URL: \(url)")
        print("📱 Live Activity registration payload: \(payload)")
        
        do {
            let (data, response) = try await session.data(for: request)
            
            if let httpResponse = response as? HTTPURLResponse {
                print("📱 Live Activity token registration response: \(httpResponse.statusCode)")
                
                // Log response body for debugging
                if let responseString = String(data: data, encoding: .utf8) {
                    print("📱 Live Activity registration response body: \(responseString)")
                }
                
                if httpResponse.statusCode != 200 && httpResponse.statusCode != 201 {
                    throw APIError.invalidParameters
                }
            }
            
            print("✅ Live Activity token registered for train \(trainId)")
        } catch {
            print("❌ Failed to register Live Activity token: \(error)")
            throw error
        }
    }
}

// MARK: - API Errors
enum APIError: LocalizedError {
    case invalidURL
    case noData
    case decodingError
    case invalidParameters
    
    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid URL"
        case .noData: return "No data received"
        case .decodingError: return "Failed to decode response"
        case .invalidParameters: return "Invalid parameters provided"
        }
    }
}

