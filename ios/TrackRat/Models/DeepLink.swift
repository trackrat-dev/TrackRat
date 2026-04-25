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
        // Legacy Universal Link:  https://trackrat.net/train/{id}?date=&from=&to=
        // Share Universal Link:   https://apiv2.trackrat.net/share/train/{id}?date=&from=&to=
        // Custom URL Scheme:      trackrat://train/{id}?date=&from=&to=
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: true) else {
            return nil
        }

        // Validate scheme and host
        let isHTTPS = components.scheme == "https" || components.scheme == "http"
        let isLegacyUniversalLink = isHTTPS &&
                                    (components.host == "trackrat.net" || components.host == "www.trackrat.net")
        let isShareUniversalLink = isHTTPS && components.host == "apiv2.trackrat.net"
        let isCustomScheme = components.scheme == "trackrat"

        guard isLegacyUniversalLink || isShareUniversalLink || isCustomScheme else {
            return nil
        }

        // Extract train ID from path
        let pathComponents = components.path.components(separatedBy: "/")

        // For custom URL scheme, the path might be "train/{id}" or "/train/{id}" or host could be "train"
        // For Universal Links, it's "/train/{id}" (legacy) or "/share/train/{id}" (share preview).
        let trainIndex: Int
        if isCustomScheme {
            // Handle format: "trackrat://train/A174" (train is host, A174 is path)
            if components.host == "train" && pathComponents.count >= 2 && !pathComponents[1].isEmpty {
                trainIndex = 1
            }
            // Handle format: "trackrat://host/train/A174" (train in path)
            else if pathComponents.count >= 2 && pathComponents[1] == "train" && pathComponents.count >= 3 {
                trainIndex = 2
            } else if pathComponents.count >= 3 && pathComponents[2] == "train" && pathComponents.count >= 4 {
                trainIndex = 3
            } else {
                return nil
            }
        } else if isShareUniversalLink {
            // Share Universal Link: "https://apiv2.trackrat.net/share/train/123"
            guard pathComponents.count >= 4,
                  pathComponents[1] == "share",
                  pathComponents[2] == "train" else {
                return nil
            }
            trainIndex = 3
        } else {
            // Legacy Universal Link: "https://trackrat.net/train/123"
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
    
    /// Generate URL for sharing.
    ///
    /// Emits the rich-preview share URL on apiv2.trackrat.net, which serves
    /// OG-tagged HTML so iMessage and other unfurlers can render a preview,
    /// then redirects (and Universal-Links into this app) on tap.
    func generateURL() -> URL? {
        var components = URLComponents()
        components.scheme = "https"
        components.host = "apiv2.trackrat.net"
        components.path = "/share/train/\(trainId)"
        
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
           let fromName = Stations.stationName(forCode: fromCode) {
            text += " from \(Stations.displayName(for: fromName))"
        }

        if let destName = destinationName {
            text += " to \(destName)"
        } else if let toCode = toStationCode,
                  let toName = Stations.stationName(forCode: toCode) {
            text += " to \(Stations.displayName(for: toName))"
        }
        
        return text
    }
}