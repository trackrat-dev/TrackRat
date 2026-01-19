import Foundation

/// Represents the different train systems supported by TrackRat
enum TrainSystem: String, CaseIterable, Codable, Identifiable {
    case njt = "NJT"
    case amtrak = "AMTRAK"
    case path = "PATH"
    case patco = "PATCO"

    var id: String { rawValue }

    /// Human-readable display name
    var displayName: String {
        switch self {
        case .njt: return "NJ Transit"
        case .amtrak: return "Amtrak"
        case .path: return "PATH"
        case .patco: return "PATCO"
        }
    }

    /// Short description for the system
    var description: String {
        switch self {
        case .njt: return "New Jersey commuter rail"
        case .amtrak: return "National passenger rail"
        case .path: return "NY-NJ rapid transit"
        case .patco: return "Philly-South Jersey"
        }
    }

    /// SF Symbol icon for the system
    var icon: String {
        switch self {
        case .njt: return "tram.fill"
        case .amtrak: return "train.side.front.car"
        case .path: return "tram"
        case .patco: return "lightrail.fill"
        }
    }

    /// Brand color for the system
    var color: String {
        switch self {
        case .njt: return "#004D6E"   // NJ Transit blue
        case .amtrak: return "#004B87" // Amtrak blue
        case .path: return "#FF5722"  // PATH orange
        case .patco: return "#0072CE" // PATCO blue
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
}
