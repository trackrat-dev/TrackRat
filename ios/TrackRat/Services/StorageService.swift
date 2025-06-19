import Foundation

// MARK: - Server Environment Model
enum ServerEnvironment: String, CaseIterable, Codable {
    case production = "production"
    case staging = "staging"
    case development = "development"
    
    var displayName: String {
        switch self {
        case .production:
            return "Production"
        case .staging:
            return "Staging"
        case .development:
            return "Development"
        }
    }
    
    var baseURL: String {
        switch self {
        case .production:
            return "https://prod.api.trackrat.net/api"
        case .staging:
            return "https://staging.api.trackrat.net/api"
        case .development:
            return "https://dev.api.trackrat.net/api"
        }
    }
}

// MARK: - Trip Pair Model
struct TripPair: Codable, Identifiable {
    var id: String { "\(departureCode)-\(destinationCode)" }
    let departureCode: String
    let departureName: String
    let destinationCode: String
    let destinationName: String
    let lastUsed: Date
    let isFavorite: Bool
    
    init(departureCode: String, departureName: String, destinationCode: String, destinationName: String, lastUsed: Date = Date(), isFavorite: Bool = false) {
        self.departureCode = departureCode
        self.departureName = departureName
        self.destinationCode = destinationCode
        self.destinationName = destinationName
        self.lastUsed = lastUsed
        self.isFavorite = isFavorite
    }
}

// MARK: - Departure Model
struct RecentDeparture: Codable {
    let code: String
    let name: String
}

// MARK: - Storage Service
final class StorageService {
    private let recentDestinationsKey = "trackrat.recentDestinations"
    private let recentTripsKey = "trackrat.recentTrips"
    private let recentDeparturesKey = "trackrat.recentDepartures"
    private let serverEnvironmentKey = "trackrat.serverEnvironment"
    private let maxRecentDestinations = 5
    private let maxRecentTrips = 10
    private let maxRecentDepartures = 5
    
    private let userDefaults = UserDefaults.standard
    
    // MARK: - Recent Destinations
    func loadRecentDestinations() -> [String] {
        return userDefaults.stringArray(forKey: recentDestinationsKey) ?? []
    }
    
    func saveDestination(_ destination: String) {
        var recent = loadRecentDestinations()
        
        // Remove if already exists
        recent.removeAll { $0 == destination }
        
        // Add to front
        recent.insert(destination, at: 0)
        
        // Keep only max items
        if recent.count > maxRecentDestinations {
            recent = Array(recent.prefix(maxRecentDestinations))
        }
        
        userDefaults.set(recent, forKey: recentDestinationsKey)
    }
    
    func removeDestination(_ destination: String) {
        var recent = loadRecentDestinations()
        recent.removeAll { $0 == destination }
        userDefaults.set(recent, forKey: recentDestinationsKey)
    }
    
    func clearRecentDestinations() {
        userDefaults.removeObject(forKey: recentDestinationsKey)
    }
    
    // MARK: - Trip Pairs
    func loadRecentTrips() -> [TripPair] {
        guard let data = userDefaults.data(forKey: recentTripsKey),
              let trips = try? JSONDecoder().decode([TripPair].self, from: data) else {
            return []
        }
        return trips
    }
    
    func saveTrip(departureCode: String, departureName: String,
                  destinationCode: String, destinationName: String) {
        var trips = loadRecentTrips()
        
        // Remove existing trip with same departure/destination
        trips.removeAll {
            $0.departureCode == departureCode &&
            $0.destinationCode == destinationCode
        }
        
        // Add new trip (not favorited by default)
        let newTrip = TripPair(
            departureCode: departureCode,
            departureName: departureName,
            destinationCode: destinationCode,
            destinationName: destinationName,
            lastUsed: Date(),
            isFavorite: false
        )
        
        trips.insert(newTrip, at: 0)
        
        // Keep only max items
        if trips.count > maxRecentTrips {
            trips = Array(trips.prefix(maxRecentTrips))
        }
        
        if let data = try? JSONEncoder().encode(trips) {
            userDefaults.set(data, forKey: recentTripsKey)
        }
    }
    
    func toggleFavorite(for trip: TripPair) {
        var trips = loadRecentTrips()
        
        if let index = trips.firstIndex(where: { $0.id == trip.id }) {
            let updatedTrip = TripPair(
                departureCode: trip.departureCode,
                departureName: trip.departureName,
                destinationCode: trip.destinationCode,
                destinationName: trip.destinationName,
                lastUsed: Date(),
                isFavorite: !trip.isFavorite
            )
            trips[index] = updatedTrip
        } else {
            // Trip doesn't exist, add it as a favorite
            let newTrip = TripPair(
                departureCode: trip.departureCode,
                departureName: trip.departureName,
                destinationCode: trip.destinationCode,
                destinationName: trip.destinationName,
                lastUsed: Date(),
                isFavorite: true
            )
            trips.insert(newTrip, at: 0)
        }
        
        if let data = try? JSONEncoder().encode(trips) {
            userDefaults.set(data, forKey: recentTripsKey)
        }
    }
    
    func loadFavoriteTrips() -> [TripPair] {
        return loadRecentTrips().filter { $0.isFavorite }
    }
    
    func removeTrip(_ trip: TripPair) {
        var trips = loadRecentTrips()
        trips.removeAll { $0.id == trip.id }
        
        if let data = try? JSONEncoder().encode(trips) {
            userDefaults.set(data, forKey: recentTripsKey)
        }
    }
    
    func clearRecentTrips() {
        userDefaults.removeObject(forKey: recentTripsKey)
    }
    
    // MARK: - Recent Departures
    func loadRecentDepartures() -> [RecentDeparture] {
        guard let data = userDefaults.data(forKey: recentDeparturesKey),
              let departures = try? JSONDecoder().decode([RecentDeparture].self, from: data) else {
            return []
        }
        return departures
    }
    
    func saveDeparture(code: String, name: String) {
        var departures = loadRecentDepartures()
        
        // Remove if already exists
        departures.removeAll { $0.code == code }
        
        // Add to front
        let newDeparture = RecentDeparture(code: code, name: name)
        departures.insert(newDeparture, at: 0)
        
        // Keep only max items
        if departures.count > maxRecentDepartures {
            departures = Array(departures.prefix(maxRecentDepartures))
        }
        
        if let data = try? JSONEncoder().encode(departures) {
            userDefaults.set(data, forKey: recentDeparturesKey)
        }
    }
    
    // MARK: - Server Environment
    func loadServerEnvironment() -> ServerEnvironment {
        guard let environmentString = userDefaults.string(forKey: serverEnvironmentKey),
              let environment = ServerEnvironment(rawValue: environmentString) else {
            return .production // Default to production
        }
        return environment
    }
    
    func saveServerEnvironment(_ environment: ServerEnvironment) {
        userDefaults.set(environment.rawValue, forKey: serverEnvironmentKey)
    }
    
    // MARK: - Migration
    func migrateRecentDestinations() {
        let existingDestinations = loadRecentDestinations()
        if !existingDestinations.isEmpty && loadRecentTrips().isEmpty {
            // Create trip pairs with NY Penn as default departure
            for destination in existingDestinations {
                if let destCode = Stations.getStationCode(destination) {
                    saveTrip(
                        departureCode: "NY",
                        departureName: Stations.displayName(for: "New York Penn Station"),
                        destinationCode: destCode,
                        destinationName: destination
                    )
                }
            }
        }
    }
}