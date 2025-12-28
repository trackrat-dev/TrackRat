import Foundation

// MARK: - Server Environment Model
enum ServerEnvironment: String, CaseIterable, Codable {
    case production = "production"
    case staging = "staging"
    case local = "local"
    
    var displayName: String {
        switch self {
        case .production:
            return "Production"
        case .staging:
            return "Staging"
        case .local:
            return "Local"
        }
    }
    
    var baseURL: String {
        switch self {
        case .production:
            return "https://apiv2.trackrat.net/api"
        case .staging:
            return "https://staging.apiv2.trackrat.net/api"
        case .local:
            return "http://localhost:8000/api"
        }
    }
    
    var supportsHistoricalData: Bool {
        switch self {
        case .production, .staging, .local:
            return true
        }
    }
}

// MARK: - Favorite Station Model
struct FavoriteStation: Codable, Identifiable, Equatable {
    let id: String  // Station code (e.g., "NY", "TR")
    let name: String  // Station name
    let lastUsed: Date
    
    init(code: String, name: String, lastUsed: Date = Date()) {
        self.id = code
        self.name = name
        self.lastUsed = lastUsed
    }
}

// MARK: - Trip Pair Model
struct TripPair: Codable, Identifiable, Equatable {
    let id: String  // Normalized: "MP-NY" (alphabetical order)
    private let stationA: (code: String, name: String)  // First station alphabetically
    private let stationB: (code: String, name: String)  // Second station alphabetically
    var preferredDirection: Direction = .aToB   // Which direction to display
    let lastUsed: Date
    let isFavorite: Bool
    
    enum Direction: String, Codable {
        case aToB  // A → B
        case bToA  // B → A
    }
    
    // Computed properties for display
    var departureCode: String {
        preferredDirection == .aToB ? stationA.code : stationB.code
    }
    
    var departureName: String {
        preferredDirection == .aToB ? stationA.name : stationB.name
    }
    
    var destinationCode: String {
        preferredDirection == .aToB ? stationB.code : stationA.code
    }
    
    var destinationName: String {
        preferredDirection == .aToB ? stationB.name : stationA.name
    }
    
    // Custom coding to handle tuple encoding
    enum CodingKeys: String, CodingKey {
        case id, preferredDirection, lastUsed, isFavorite
        case stationACode, stationAName, stationBCode, stationBName
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        preferredDirection = try container.decode(Direction.self, forKey: .preferredDirection)
        lastUsed = try container.decode(Date.self, forKey: .lastUsed)
        isFavorite = try container.decode(Bool.self, forKey: .isFavorite)
        
        let aCode = try container.decode(String.self, forKey: .stationACode)
        let aName = try container.decode(String.self, forKey: .stationAName)
        let bCode = try container.decode(String.self, forKey: .stationBCode)
        let bName = try container.decode(String.self, forKey: .stationBName)
        
        stationA = (code: aCode, name: aName)
        stationB = (code: bCode, name: bName)
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(preferredDirection, forKey: .preferredDirection)
        try container.encode(lastUsed, forKey: .lastUsed)
        try container.encode(isFavorite, forKey: .isFavorite)
        try container.encode(stationA.code, forKey: .stationACode)
        try container.encode(stationA.name, forKey: .stationAName)
        try container.encode(stationB.code, forKey: .stationBCode)
        try container.encode(stationB.name, forKey: .stationBName)
    }
    
    init(departureCode: String, departureName: String, destinationCode: String, destinationName: String, lastUsed: Date = Date(), isFavorite: Bool = false) {
        // Normalize the station codes alphabetically
        let isNormalized = departureCode < destinationCode
        
        if isNormalized {
            self.id = "\(departureCode)-\(destinationCode)"
            self.stationA = (code: departureCode, name: departureName)
            self.stationB = (code: destinationCode, name: destinationName)
            self.preferredDirection = .aToB
        } else {
            self.id = "\(destinationCode)-\(departureCode)"
            self.stationA = (code: destinationCode, name: destinationName)
            self.stationB = (code: departureCode, name: departureName)
            self.preferredDirection = .bToA
        }
        
        self.lastUsed = lastUsed
        self.isFavorite = isFavorite
    }
    
    // MARK: - Equatable
    static func == (lhs: TripPair, rhs: TripPair) -> Bool {
        return lhs.id == rhs.id && 
               lhs.preferredDirection == rhs.preferredDirection &&
               lhs.isFavorite == rhs.isFavorite
    }
}


// MARK: - Storage Service
final class StorageService {
    private let recentTripsKey = "trackrat.recentTrips"
    private let favoriteStationsKey = "trackrat.favoriteStations"
    private let serverEnvironmentKey = "trackrat.serverEnvironment"
    private let maxRecentTrips = 10
    private let maxFavoriteStations = 10
    
    private let userDefaults = UserDefaults.standard
    
    
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
    
    func reverseFavoriteDirection(_ trip: TripPair) {
        var trips = loadRecentTrips()
        
        if let index = trips.firstIndex(where: { $0.id == trip.id }) {
            var updatedTrip = trips[index]
            updatedTrip.preferredDirection = updatedTrip.preferredDirection == .aToB ? .bToA : .aToB
            trips[index] = updatedTrip
            
            if let data = try? JSONEncoder().encode(trips) {
                userDefaults.set(data, forKey: recentTripsKey)
            }
        }
    }
    
    func clearRecentTrips() {
        userDefaults.removeObject(forKey: recentTripsKey)
    }
    
    // MARK: - Favorite Stations
    func loadFavoriteStations() -> [FavoriteStation] {
        // Load stored favorites from UserDefaults
        var stations: [FavoriteStation] = []
        if let data = userDefaults.data(forKey: favoriteStationsKey),
           let decodedStations = try? JSONDecoder().decode([FavoriteStation].self, from: data) {
            stations = decodedStations
        }
        
        // Always include home station if set
        if let homeCode = RatSenseService.shared.getHomeStation(),
           !stations.contains(where: { $0.id == homeCode }) {
            let homeName = Stations.displayName(for: homeCode)
            stations.append(FavoriteStation(code: homeCode, name: homeName))
        }

        // Always include work station if set
        if let workCode = RatSenseService.shared.getWorkStation(),
           !stations.contains(where: { $0.id == workCode }) {
            let workName = Stations.displayName(for: workCode)
            stations.append(FavoriteStation(code: workCode, name: workName))
        }
        
        // If no stations at all (no stored favorites and no home/work), return NYC as default
        if stations.isEmpty {
            stations = [FavoriteStation(code: "NY", name: "New York Penn Station")]
        }
        
        return stations.sorted { $0.lastUsed > $1.lastUsed }
    }
    
    func toggleFavoriteStation(code: String, name: String) {
        var stations = loadFavoriteStations()
        
        if let index = stations.firstIndex(where: { $0.id == code }) {
            // Remove from favorites
            stations.remove(at: index)
        } else {
            // Add to favorites
            let newStation = FavoriteStation(code: code, name: name)
            stations.insert(newStation, at: 0)
            
            // Keep only max items
            if stations.count > maxFavoriteStations {
                stations = Array(stations.prefix(maxFavoriteStations))
            }
        }
        
        if let data = try? JSONEncoder().encode(stations) {
            userDefaults.set(data, forKey: favoriteStationsKey)
        }
    }
    
    func isStationFavorited(code: String) -> Bool {
        // Check if it's in the favorites list
        let isInFavorites = loadFavoriteStations().contains { $0.id == code }
        
        // Also check if it's home or work station (these are always treated as favorites)
        let isHomeStation = RatSenseService.shared.getHomeStation() == code
        let isWorkStation = RatSenseService.shared.getWorkStation() == code
        
        return isInFavorites || isHomeStation || isWorkStation
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
        // Get existing destinations from UserDefaults directly (since we removed the method)
        let existingDestinations = userDefaults.stringArray(forKey: "trackrat.recentDestinations") ?? []
        
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
            
            // Clean up old keys after migration
            userDefaults.removeObject(forKey: "trackrat.recentDestinations")
            userDefaults.removeObject(forKey: "trackrat.recentDepartures")
        }
    }
}