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
    static let shared = StorageService()

    private let recentTripsKey = "trackrat.recentTrips"
    private let favoriteStationsKey = "trackrat.favoriteStations"
    private let serverEnvironmentKey = "trackrat.serverEnvironment"
    private let completedTripsKey = "trackrat.completedTrips"
    private let maxRecentTrips = 10
    private let maxFavoriteStations = 10
    private let maxCompletedTrips = 500  // ~2 years of daily commuting

    private let userDefaults = UserDefaults.standard

    init() {}
    
    
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

    /// Loads only the explicitly saved favorites from UserDefaults (no home/work injection).
    private func loadStoredFavorites() -> [FavoriteStation] {
        guard let data = userDefaults.data(forKey: favoriteStationsKey),
              let stations = try? JSONDecoder().decode([FavoriteStation].self, from: data) else {
            return []
        }
        return stations
    }

    /// Persists the given favorites to UserDefaults.
    private func saveStoredFavorites(_ stations: [FavoriteStation]) {
        if let data = try? JSONEncoder().encode(stations) {
            userDefaults.set(data, forKey: favoriteStationsKey)
        }
    }

    /// Returns the full favorites list including home/work stations (for display).
    func loadFavoriteStations() -> [FavoriteStation] {
        var stations = loadStoredFavorites()

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

        return stations.sorted { $0.lastUsed > $1.lastUsed }
    }

    func toggleFavoriteStation(code: String, name: String) {
        var stations = loadStoredFavorites()

        if let index = stations.firstIndex(where: { $0.id == code }) {
            stations.remove(at: index)
        } else {
            let newStation = FavoriteStation(code: code, name: name)
            stations.insert(newStation, at: 0)

            if stations.count > maxFavoriteStations {
                stations = Array(stations.prefix(maxFavoriteStations))
            }
        }

        saveStoredFavorites(stations)
    }

    /// Removes a station from the explicit favorites list (no-op if not present).
    /// Unlike toggleFavoriteStation, this never adds.
    func removeFavoriteStation(code: String) {
        var stations = loadStoredFavorites()
        if let index = stations.firstIndex(where: { $0.id == code }) {
            stations.remove(at: index)
            saveStoredFavorites(stations)
        }
    }

    func isStationFavorited(code: String) -> Bool {
        let isInStored = loadStoredFavorites().contains { $0.id == code }
        let isHomeStation = RatSenseService.shared.getHomeStation() == code
        let isWorkStation = RatSenseService.shared.getWorkStation() == code
        return isInStored || isHomeStation || isWorkStation
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
    
    // MARK: - Completed Trips (Trip History)

    func saveCompletedTrip(_ trip: CompletedTrip) {
        var trips = loadCompletedTrips()
        trips.insert(trip, at: 0)

        // Trim old trips if over limit
        if trips.count > maxCompletedTrips {
            trips = Array(trips.prefix(maxCompletedTrips))
        }

        persistCompletedTrips(trips)
    }

    func updateCompletedTrip(id: UUID, update: (inout CompletedTrip) -> Void) {
        var trips = loadCompletedTrips()
        if let index = trips.firstIndex(where: { $0.id == id }) {
            update(&trips[index])
            persistCompletedTrips(trips)
        }
    }

    func deleteCompletedTrip(id: UUID) {
        var trips = loadCompletedTrips()
        trips.removeAll { $0.id == id }
        persistCompletedTrips(trips)
    }

    func loadCompletedTrips() -> [CompletedTrip] {
        guard let data = userDefaults.data(forKey: completedTripsKey),
              let trips = try? JSONDecoder().decode([CompletedTrip].self, from: data) else {
            return []
        }
        return trips
    }

    func clearCompletedTrips() {
        userDefaults.removeObject(forKey: completedTripsKey)
    }

    private func persistCompletedTrips(_ trips: [CompletedTrip]) {
        if let data = try? JSONEncoder().encode(trips) {
            userDefaults.set(data, forKey: completedTripsKey)
        }
    }

    // MARK: - Trip Statistics

    func computeTripStats() -> TripStats {
        let trips = loadCompletedTrips()

        guard !trips.isEmpty else {
            return .empty
        }

        // Basic counts
        let totalDelay = trips.reduce(0) { $0 + $1.arrivalDelayMinutes }
        let onTimeCount = trips.filter { $0.isOnTime }.count
        let avgDelay = Double(totalDelay) / Double(trips.count)

        // Most frequent route
        var routeCounts: [String: (originName: String, destinationName: String, count: Int)] = [:]
        for trip in trips {
            let key = "\(trip.originCode)-\(trip.destinationCode)"
            if let existing = routeCounts[key] {
                routeCounts[key] = (existing.originName, existing.destinationName, existing.count + 1)
            } else {
                routeCounts[key] = (trip.originName, trip.destinationName, 1)
            }
        }
        let topRoute = routeCounts.values.max(by: { $0.count < $1.count })

        // First trip date
        let firstDate = trips.last?.tripDate

        // Weekly streak calculation
        let weeklyStreak = calculateWeeklyStreak(trips: trips)

        return TripStats(
            totalTrips: trips.count,
            totalDelayMinutes: totalDelay,
            totalOnTimeTrips: onTimeCount,
            averageDelayMinutes: avgDelay,
            mostFrequentRoute: topRoute,
            firstTripDate: firstDate,
            weeklyStreak: weeklyStreak
        )
    }

    /// Calculate consecutive weeks with at least one trip, counting back from current week
    private func calculateWeeklyStreak(trips: [CompletedTrip]) -> Int {
        let calendar = Calendar.current

        // Get the start of the current week (Sunday)
        guard let currentWeekStart = calendar.dateInterval(of: .weekOfYear, for: Date())?.start else {
            return 0
        }

        // Get unique weeks that have trips (as week start dates)
        var weeksWithTrips = Set<Date>()
        for trip in trips {
            if let weekStart = calendar.dateInterval(of: .weekOfYear, for: trip.tripDate)?.start {
                weeksWithTrips.insert(weekStart)
            }
        }

        var streak = 0
        var checkWeek = currentWeekStart

        // Count backwards from current week
        while weeksWithTrips.contains(checkWeek) {
            streak += 1
            guard let previousWeek = calendar.date(byAdding: .weekOfYear, value: -1, to: checkWeek) else {
                break
            }
            checkWeek = previousWeek
        }

        return streak
    }
}