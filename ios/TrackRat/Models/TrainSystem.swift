import Foundation

/// Represents the different train systems supported by TrackRat
enum TrainSystem: String, CaseIterable, Codable, Identifiable {
    case njt = "NJT"
    case amtrak = "AMTRAK"
    case path = "PATH"
    case patco = "PATCO"
    case lirr = "LIRR"
    case mnr = "MNR"

    var id: String { rawValue }

    /// Human-readable display name
    var displayName: String {
        switch self {
        case .njt: return "NJ Transit"
        case .amtrak: return "Amtrak"
        case .path: return "PATH"
        case .patco: return "PATCO"
        case .lirr: return "LIRR"
        case .mnr: return "Metro-North"
        }
    }

    /// Short description for the system
    var description: String {
        switch self {
        case .njt: return "New Jersey commuter rail"
        case .amtrak: return "National passenger rail"
        case .path: return "NY-NJ rapid transit"
        case .patco: return "Philly-South Jersey"
        case .lirr: return "Long Island commuter rail"
        case .mnr: return "NYC-Hudson Valley rail"
        }
    }

    /// SF Symbol icon for the system
    var icon: String {
        switch self {
        case .njt: return "tram.fill"
        case .amtrak: return "train.side.front.car"
        case .path: return "tram"
        case .patco: return "lightrail.fill"
        case .lirr: return "train.side.rear.car"
        case .mnr: return "train.side.front.car"
        }
    }

    /// Brand color for the system
    var color: String {
        switch self {
        case .njt: return "#004D6E"   // NJ Transit blue
        case .amtrak: return "#004B87" // Amtrak blue
        case .path: return "#FF5722"  // PATH orange
        case .patco: return "#0072CE" // PATCO blue
        case .lirr: return "#0039A6"  // MTA LIRR blue
        case .mnr: return "#0039A6"   // MTA Metro-North blue
        }
    }

    /// Whether this system is in beta (shown as label in UI)
    var isBeta: Bool {
        switch self {
        case .path, .lirr, .mnr: return true
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

    /// Default enabled systems (NJT and Amtrak only)
    /// PATH and PATCO must be explicitly enabled in Advanced Configuration
    static var defaultEnabled: Set<TrainSystem> {
        [.njt, .amtrak]
    }

    /// Converts to raw string set for use with Stations filtering
    var asRawStrings: Set<String> {
        var result = Set<String>()
        for system in self {
            result.insert(system.rawValue)
        }
        return result
    }
}

// MARK: - Stations Extensions (TrainSystem-aware wrappers)

extension Stations {
    /// Returns the train systems that serve a given station
    /// Defaults to NJT + Amtrak if not explicitly mapped (most NJT commuter stations)
    static func systemsForStation(_ code: String) -> Set<TrainSystem> {
        let rawSystems = systemStringsForStation(code)
        return Set(rawSystems.compactMap { TrainSystem(rawValue: $0) })
    }

    /// Check if a station should be visible based on selected systems
    /// A station is visible if ANY of the selected systems serve it
    static func isStationVisible(_ code: String, withSystems selectedSystems: Set<TrainSystem>) -> Bool {
        return isStationVisible(code, withSystemStrings: selectedSystems.asRawStrings)
    }
}
