import Foundation

/// Represents the different train systems supported by TrackRat
enum TrainSystem: String, CaseIterable, Codable, Identifiable {
    case njt = "NJT"
    case amtrak = "AMTRAK"
    case amtrakNEC = "AMTRAK_NEC"
    case path = "PATH"
    case patco = "PATCO"
    case lirr = "LIRR"
    case mnr = "MNR"
    case subway = "SUBWAY"

    var id: String { rawValue }

    /// Backend data source string (e.g. .amtrakNEC shares "AMTRAK")
    var dataSource: String {
        switch self {
        case .amtrakNEC: return "AMTRAK"
        default: return rawValue
        }
    }

    /// Route IDs this system is restricted to, or nil for no restriction
    var routeIds: [String]? {
        switch self {
        case .amtrakNEC: return ["amtrak-nec", "amtrak-keystone"]
        default: return nil
        }
    }

    /// Human-readable display name
    var displayName: String {
        switch self {
        case .njt: return "NJ Transit"
        case .amtrak: return "Amtrak"
        case .amtrakNEC: return "Amtrak (NEC Only)"
        case .path: return "PATH"
        case .patco: return "PATCO"
        case .lirr: return "LIRR"
        case .mnr: return "Metro-North"
        case .subway: return "NYC Subway"
        }
    }

    /// Short description for the system
    var description: String {
        switch self {
        case .njt: return "New Jersey commuter rail"
        case .amtrak: return "National passenger rail"
        case .amtrakNEC: return "Northeast Corridor & Keystone"
        case .path: return "NY-NJ rapid transit"
        case .patco: return "Philly-South Jersey"
        case .lirr: return "Long Island commuter rail"
        case .mnr: return "NYC-Hudson Valley rail"
        case .subway: return "NYC rapid transit"
        }
    }

    /// SF Symbol icon for the system
    var icon: String {
        switch self {
        case .njt: return "tram.fill"
        case .amtrak, .amtrakNEC: return "train.side.front.car"
        case .path: return "tram"
        case .patco: return "lightrail.fill"
        case .lirr: return "train.side.rear.car"
        case .mnr: return "train.side.front.car"
        case .subway: return "tram.fill"
        }
    }

    /// Brand color for the system
    var color: String {
        switch self {
        case .njt: return "#004D6E"   // NJ Transit blue
        case .amtrak, .amtrakNEC: return "#004B87" // Amtrak blue
        case .path: return "#FF5722"  // PATH orange
        case .patco: return "#0072CE" // PATCO blue
        case .lirr: return "#0039A6"  // MTA LIRR blue
        case .mnr: return "#0039A6"   // MTA Metro-North blue
        case .subway: return "#0039A6"  // MTA blue
        }
    }

    /// Whether this system uses synthetic (non-user-facing) train IDs.
    /// These systems should display destination or line name instead of raw train ID.
    static let syntheticTrainIdSources: Set<String> = ["PATH", "PATCO", "LIRR", "MNR", "SUBWAY"]

    /// Whether this system is in beta (shown as label in UI)
    var isBeta: Bool {
        switch self {
        case .subway: return true
        default: return false
        }
    }
}

// MARK: - Set Extensions

extension Set where Element == TrainSystem {
    /// Returns a comma-separated string of raw values for API calls and storage
    var commaSeparated: String {
        self.map(\.rawValue).sorted().joined(separator: ",")
    }

    /// Creates a Set from a comma-separated string
    static func from(commaSeparated: String) -> Set<TrainSystem> {
        Set(commaSeparated.split(separator: ",").compactMap { TrainSystem(rawValue: String($0)) })
    }

    /// All systems selected
    static var all: Set<TrainSystem> {
        Set(TrainSystem.allCases)
    }

    /// No systems enabled by default — user picks during onboarding
    static var defaultEnabled: Set<TrainSystem> {
        []
    }

    /// Deduplicated data source strings for API calls (e.g. both .amtrak and .amtrakNEC → "AMTRAK")
    var apiDataSources: String {
        Set<String>(self.map(\.dataSource)).sorted().joined(separator: ",")
    }

    /// Converts to raw data source string set for use with Stations/route filtering
    var asRawStrings: Set<String> {
        var result = Set<String>()
        for system in self {
            result.insert(system.dataSource)
        }
        return result
    }
}

// MARK: - Stations Extensions (TrainSystem-aware wrappers)

extension Stations {
    /// Cached mapping of route-filtered system rawValues to their allowed station codes.
    /// For systems like .amtrakNEC that restrict to specific routes.
    static let routeFilteredStations: [String: Set<String>] = {
        var result: [String: Set<String>] = [:]
        for system in TrainSystem.allCases {
            guard let routeIds = system.routeIds else { continue }
            var codes = Set<String>()
            for route in RouteTopology.allRoutes where routeIds.contains(route.id) {
                codes.formUnion(route.stationCodes)
            }
            result[system.rawValue] = codes
        }
        return result
    }()

    /// Returns the train systems that serve a given station
    /// Defaults to NJT + Amtrak if not explicitly mapped (most NJT commuter stations)
    static func systemsForStation(_ code: String) -> Set<TrainSystem> {
        let rawSystems = systemStringsForStation(code)
        return Set(rawSystems.compactMap { TrainSystem(rawValue: $0) })
    }

    /// Check if a station should be visible based on selected systems
    /// A station is visible if ANY of the selected systems serve it
    static func isStationVisible(_ code: String, withSystems selectedSystems: Set<TrainSystem>) -> Bool {
        for system in selectedSystems {
            if let allowedStations = routeFilteredStations[system.rawValue] {
                if allowedStations.contains(code) { return true }
            } else {
                let stationSystems = systemStringsForStation(code)
                if stationSystems.contains(system.dataSource) { return true }
            }
        }
        return false
    }
}
