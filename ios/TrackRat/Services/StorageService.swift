import Foundation

// MARK: - Trip Pair Model
struct TripPair: Codable, Identifiable {
    var id: String { "\(departureCode)-\(destinationCode)" }
    let departureCode: String
    let departureName: String
    let destinationCode: String
    let destinationName: String
    let lastUsed: Date
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
        
        // Add new trip
        let newTrip = TripPair(
            departureCode: departureCode,
            departureName: departureName,
            destinationCode: destinationCode,
            destinationName: destinationName,
            lastUsed: Date()
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