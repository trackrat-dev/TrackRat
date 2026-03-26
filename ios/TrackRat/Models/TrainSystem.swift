import Foundation
import MapKit

/// Represents the different train systems supported by TrackRat
enum TrainSystem: String, CaseIterable, Codable, Identifiable {
    case njt = "NJT"
    case amtrak = "AMTRAK"
    case path = "PATH"
    case patco = "PATCO"
    case lirr = "LIRR"
    case mnr = "MNR"
    case subway = "SUBWAY"
    case metra = "METRA"

    var id: String { rawValue }

    /// Backend data source string
    var dataSource: String { rawValue }

    /// Human-readable display name
    var displayName: String {
        switch self {
        case .njt: return "NJ Transit"
        case .amtrak: return "Amtrak"
        case .path: return "PATH"
        case .patco: return "PATCO"
        case .lirr: return "LIRR"
        case .mnr: return "Metro-North"
        case .subway: return "NYC Subway"
        case .metra: return "Metra"
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
        case .subway: return "tram.fill"
        case .metra: return "tram.fill"
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
        case .subway: return "#0039A6"  // MTA blue
        case .metra: return "#00558A"  // Metra blue
        }
    }

    /// Whether this system uses synthetic (non-user-facing) train IDs.
    /// These systems should display destination or line name instead of raw train ID.
    static let syntheticTrainIdSources: Set<String> = ["PATH", "PATCO", "LIRR", "MNR", "SUBWAY", "METRA"]

    /// Systems where boarding track numbers are not meaningful to display.
    /// Subway and PATH use fixed platforms, not assignable tracks.
    static let noTrackDisplaySources: Set<String> = ["PATH", "SUBWAY"]

    /// Whether this system has real-time data capable of generating meaningful route alerts.
    /// Schedule-only systems (e.g., PATCO) cannot detect delays or cancellations.
    var supportsAlerts: Bool {
        switch self {
        case .njt, .amtrak, .path, .lirr, .mnr, .subway, .metra:
            return true
        case .patco:
            return false
        }
    }

    /// Whether this system is in beta (shown as label in UI)
    var isBeta: Bool {
        switch self {
        case .metra: return true
        default: return false
        }
    }

    /// Preferred health indicator for this system.
    /// High-frequency rapid transit → Train Count (frequency matters more than travel time).
    /// Commuter/intercity rail → Travel Time (delays are more variable and meaningful).
    var preferredHighlightMode: SegmentHighlightMode {
        switch self {
        case .subway, .path, .patco: return .health
        case .njt, .amtrak, .lirr, .mnr, .metra: return .delays
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

    /// Empty by default — user picks during onboarding.
    /// If state is corrupt (empty after onboarding), the app self-heals by re-showing onboarding.
    static var defaultEnabled: Set<TrainSystem> {
        []
    }

    /// Deduplicated data source strings for API calls
    var apiDataSources: String {
        Set<String>(self.map(\.rawValue)).sorted().joined(separator: ",")
    }

    /// Converts to raw data source string set for use with Stations/route filtering
    var asRawStrings: Set<String> {
        Set<String>(self.map(\.rawValue))
    }

}

// MARK: - Stations Extensions (TrainSystem-aware wrappers)

extension Stations {
    /// Returns the train systems that serve a given station.
    /// Returns empty set for unknown codes (all known codes are explicitly mapped).
    static func systemsForStation(_ code: String) -> Set<TrainSystem> {
        let rawSystems = systemStringsForStation(code)
        return Set(rawSystems.compactMap { TrainSystem(rawValue: $0) })
    }

    /// Check if a station should be visible based on selected systems.
    /// A station is visible if ANY of the selected systems serve it.
    static func isStationVisible(_ code: String, withSystems selectedSystems: Set<TrainSystem>) -> Bool {
        let stationSystems = systemStringsForStation(code)
        for system in selectedSystems {
            if stationSystems.contains(system.rawValue) { return true }
        }
        return false
    }

    /// Search stations grouped by active system membership.
    /// Returns stations matching selected systems first, then stations on other systems.
    static func searchGrouped(
        _ query: String,
        selectedSystems: Set<TrainSystem>
    ) -> (primary: [String], other: [String]) {
        let all = search(query)
        var primary: [String] = []
        var other: [String] = []
        for name in all {
            guard let code = getStationCode(name) else { continue }
            if isStationVisible(code, withSystems: selectedSystems) {
                primary.append(name)
            } else {
                other.append(name)
            }
        }
        return (primary, other)
    }

    /// Returns the primary train system for a station (for badge display).
    static func primarySystem(forStationCode code: String) -> TrainSystem? {
        systemsForStation(code).min(by: { $0.displayName < $1.displayName })
    }
}

// MARK: - Per-System Default Map Regions

extension TrainSystem {
    /// Default map region showing the full extent of this system's network.
    /// Used when the user has not set home/work stations.
    var defaultMapRegion: MKCoordinateRegion {
        switch self {
        case .njt:
            return MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: 40.73, longitude: -74.17),
                span: MKCoordinateSpan(latitudeDelta: 2.5, longitudeDelta: 2.0)
            )
        case .amtrak:
            return MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: 40.20, longitude: -74.50),
                span: MKCoordinateSpan(latitudeDelta: 10.0, longitudeDelta: 8.0)
            )
        case .path:
            return MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: 40.730, longitude: -74.035),
                span: MKCoordinateSpan(latitudeDelta: 0.08, longitudeDelta: 0.22)
            )
        case .patco:
            return MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: 39.92, longitude: -75.08),
                span: MKCoordinateSpan(latitudeDelta: 0.18, longitudeDelta: 0.25)
            )
        case .lirr:
            return MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: 40.75, longitude: -73.40),
                span: MKCoordinateSpan(latitudeDelta: 0.65, longitudeDelta: 2.20)
            )
        case .mnr:
            return MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: 41.15, longitude: -73.70),
                span: MKCoordinateSpan(latitudeDelta: 1.20, longitudeDelta: 1.30)
            )
        case .subway:
            return MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: 40.730, longitude: -73.950),
                span: MKCoordinateSpan(latitudeDelta: 0.45, longitudeDelta: 0.55)
            )
        case .metra:
            return MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: 41.88, longitude: -88.00),
                span: MKCoordinateSpan(latitudeDelta: 1.50, longitudeDelta: 2.00)
            )
        }
    }
}

extension Set where Element == TrainSystem {
    /// Combined map region that shows all selected systems.
    /// Computes a bounding box across all selected systems' default regions.
    var combinedMapRegion: MKCoordinateRegion {
        guard !isEmpty else { return .newarkPennDefault }
        if count == 1 { return first!.defaultMapRegion }

        var minLat = Double.greatestFiniteMagnitude
        var maxLat = -Double.greatestFiniteMagnitude
        var minLon = Double.greatestFiniteMagnitude
        var maxLon = -Double.greatestFiniteMagnitude

        for system in self {
            let region = system.defaultMapRegion
            let halfLat = region.span.latitudeDelta / 2
            let halfLon = region.span.longitudeDelta / 2
            minLat = Swift.min(minLat, region.center.latitude - halfLat)
            maxLat = Swift.max(maxLat, region.center.latitude + halfLat)
            minLon = Swift.min(minLon, region.center.longitude - halfLon)
            maxLon = Swift.max(maxLon, region.center.longitude + halfLon)
        }

        let centerLat = (minLat + maxLat) / 2
        let centerLon = (minLon + maxLon) / 2
        let spanLat = (maxLat - minLat) * 1.1
        let spanLon = (maxLon - minLon) * 1.1

        return MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: centerLat, longitude: centerLon),
            span: MKCoordinateSpan(latitudeDelta: spanLat, longitudeDelta: spanLon)
        )
    }
}
