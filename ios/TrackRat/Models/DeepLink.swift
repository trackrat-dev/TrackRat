import Foundation

/// Represents a deep link into the TrackRat app
struct DeepLink {
    let trainId: String
    let date: Date?
    let fromStationCode: String?
    let toStationCode: String?
    
    /// Create a deep link with direct parameters
    init(trainId: String, date: Date? = nil, fromStationCode: String? = nil, toStationCode: String? = nil) {
        self.trainId = trainId
        self.date = date
        self.fromStationCode = fromStationCode
        self.toStationCode = toStationCode
    }
    
    /// Create a deep link from URL components
    init?(url: URL) {
        // Expected formats:
        // Universal Links: https://trackrat.net/train/{train_id}?date={YYYY-MM-DD}&from={station_code}&to={station_code}
        // Custom URL Scheme: trackrat://train/{train_id}?date={YYYY-MM-DD}&from={station_code}&to={station_code}
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: true) else {
            return nil
        }
        
        // Validate scheme and host
        let isUniversalLink = (components.scheme == "https" || components.scheme == "http") &&
                             (components.host == "trackrat.net" || components.host == "www.trackrat.net")
        let isCustomScheme = components.scheme == "trackrat"
        
        guard isUniversalLink || isCustomScheme else {
            return nil
        }
        
        // Extract train ID from path
        let pathComponents = components.path.components(separatedBy: "/")
        
        // For custom URL scheme, the path might be "train/{id}" or "/train/{id}"
        // For Universal Links, it's "/train/{id}"
        let trainIndex: Int
        if isCustomScheme {
            // Custom scheme: "trackrat://train/123" or "trackrat:///train/123"
            if pathComponents.count >= 2 && pathComponents[1] == "train" && pathComponents.count >= 3 {
                trainIndex = 2
            } else if pathComponents.count >= 3 && pathComponents[2] == "train" && pathComponents.count >= 4 {
                trainIndex = 3
            } else {
                return nil
            }
        } else {
            // Universal Link: "https://trackrat.net/train/123"
            guard pathComponents.count >= 3,
                  pathComponents[1] == "train" else {
                return nil
            }
            trainIndex = 2
        }
        
        guard trainIndex < pathComponents.count,
              !pathComponents[trainIndex].isEmpty else {
            return nil
        }
        
        self.trainId = pathComponents[trainIndex]
        
        // Parse query parameters
        let queryItems = components.queryItems ?? []
        
        // Parse date
        if let dateString = queryItems.first(where: { $0.name == "date" })?.value {
            let formatter = DateFormatter()
            formatter.dateFormat = "yyyy-MM-dd"
            formatter.timeZone = TimeZone(identifier: "America/New_York")
            self.date = formatter.date(from: dateString)
        } else {
            self.date = nil
        }
        
        // Parse station codes
        self.fromStationCode = queryItems.first(where: { $0.name == "from" })?.value
        self.toStationCode = queryItems.first(where: { $0.name == "to" })?.value
    }
    
    /// Generate URL for sharing
    func generateURL() -> URL? {
        var components = URLComponents()
        components.scheme = "https"
        components.host = "trackrat.net"
        components.path = "/train/\(trainId)"
        
        var queryItems: [URLQueryItem] = []
        
        // Add date if provided
        if let date = date {
            let formatter = DateFormatter()
            formatter.dateFormat = "yyyy-MM-dd"
            formatter.timeZone = TimeZone(identifier: "America/New_York")
            queryItems.append(URLQueryItem(name: "date", value: formatter.string(from: date)))
        }
        
        // Add station codes if provided
        if let fromCode = fromStationCode {
            queryItems.append(URLQueryItem(name: "from", value: fromCode))
        }
        
        if let toCode = toStationCode {
            queryItems.append(URLQueryItem(name: "to", value: toCode))
        }
        
        if !queryItems.isEmpty {
            components.queryItems = queryItems
        }
        
        return components.url
    }
    
    /// Generate share text for the train
    func generateShareText(trainLine: String? = nil, destinationName: String? = nil) -> String {
        var text = "Check out train \(trainId)"
        
        if let line = trainLine {
            text += " (\(line))"
        }
        
        if let fromCode = fromStationCode,
           let fromName = Stations.stationCodes.first(where: { $0.value == fromCode })?.key {
            text += " from \(Stations.displayName(for: fromName))"
        }
        
        if let destName = destinationName {
            text += " to \(destName)"
        } else if let toCode = toStationCode,
                  let toName = Stations.stationCodes.first(where: { $0.value == toCode })?.key {
            text += " to \(Stations.displayName(for: toName))"
        }
        
        return text
    }
}