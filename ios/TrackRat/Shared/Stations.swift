import Foundation
import CoreLocation
import MapKit

struct Stations {
    static func search(_ query: String) -> [String] {
        guard !query.isEmpty else { return [] }
        let q = query.lowercased()
        let prefixMatches = all.filter { $0.lowercased().hasPrefix(q) }
        let substringMatches = all.filter {
            !$0.lowercased().hasPrefix(q) && $0.lowercased().contains(q)
        }
        return Array((prefixMatches + substringMatches).prefix(12))
    }
    
   static func getStationCode(_ stationName: String) -> String? { 
        // First try exact match
        if let code = stationCodes[stationName] {
            return code
        }
        
        // Try common variations for ambiguous names
        let normalized = stationName.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        
        // Handle NJ Transit destinations with -SEC suffix, emojis, and HTML entities
        if normalized.contains("-sec") || normalized.contains("✈") || normalized.contains("&#9992") {
            let cleaned = normalized
                .replacingOccurrences(of: " -sec", with: "")
                .replacingOccurrences(of: "-sec", with: "")
                .replacingOccurrences(of: " ✈", with: "")
                .replacingOccurrences(of: "✈", with: "")
                .replacingOccurrences(of: " &#9992", with: "")
                .replacingOccurrences(of: "&#9992", with: "")
                .trimmingCharacters(in: .whitespacesAndNewlines)
            
            // If we cleaned something, try again with the cleaned string
            if cleaned != normalized {
                // Capitalize first letter of each word for the recursive call
                let capitalized = cleaned.split(separator: " ")
                    .map { $0.prefix(1).uppercased() + $0.dropFirst() }
                    .joined(separator: " ")
                
                if let code = getStationCode(capitalized) {
                    return code
                }
            }
        }
        
        switch normalized {
        case "new york":
            return "NY"
        case "newark":
            return "NP"  // Default to Newark Penn Station
        case "trenton":
            return "TR"
        case "princeton":
            return "PJ"  // Princeton Junction is more common than Princeton
        case "philadelphia":
            return "PH"
        case "washington":
            return "WS"  // Washington Union Station
        case "baltimore":
            return "BL"
        case "boston":
            return "BOS"  // Boston South Station
        default:
            break
        }
        
        // Try partial matching for "Penn Station" destinations
        if normalized.contains("penn") {
            if normalized.contains("new york") || normalized.contains("ny") {
                return "NY"
            } else if normalized.contains("newark") {
                return "NP"
            }
        }
        
        // Try partial matching - find station names that contain the search term
        for (fullName, code) in stationCodes {
            if fullName.lowercased().contains(normalized) {
                return code
            }
        }
        
        return nil
    }
    
    static func getCoordinates(for code: String) -> CLLocationCoordinate2D? {
        return stationCoordinates[code]
    }

    /// Smart display name that handles both station codes and station names.
    /// - For codes (e.g., "NY", "MP"): Returns the full station name
    /// - For names (e.g., "New York Penn Station"): Returns shortened version
    static func displayName(for input: String) -> String {
        // First, check if input is a station code
        if let fullName = stationName(forCode: input) {
            return shortenedDisplayName(for: fullName)
        }
        // Otherwise, assume it's a station name and apply shortening
        return shortenedDisplayName(for: input)
    }

    /// Returns a shortened display name for UI (strips "Station", etc.)
    private static func shortenedDisplayName(for stationName: String) -> String {
        // First normalize the name to handle API inconsistencies
        let normalizedName = StationNameNormalizer.normalizedName(for: stationName)

        // Apply short display names for common stations
        switch normalizedName {
        case "New York Penn Station":
            return "New York Penn"
        case "Newark Penn Station":
            return "Newark Penn"
        case "Washington Union Station":
            return "Washington Union"
        default:
            return normalizedName
        }
    }

    // MARK: - Station to Train System Mapping

    /// Special overrides for stations that need manual mapping beyond what RouteTopology provides.
    /// Most stations are automatically derived from RouteTopology - only add overrides here for:
    /// - Stations with adjacent systems (e.g., NP has PATH adjacency)
    /// - Stations that need different mapping than their route membership implies
    private static let stationSystemOverrides: [String: Set<String>] = [
        "NP": ["NJT", "AMTRAK", "PATH"],  // Newark Penn Station (PATH adjacent)
    ]

    /// Cached mapping of station codes to their systems, derived from RouteTopology.
    /// Computed once on first access for performance.
    private static let derivedStationSystems: [String: Set<String>] = {
        var mapping: [String: Set<String>] = [:]
        for route in RouteTopology.allRoutes {
            for code in route.stationCodes {
                mapping[code, default: []].insert(route.dataSource)
            }
        }
        return mapping
    }()

    /// Returns the raw system strings that serve a given station.
    /// Priority: 1) Explicit overrides, 2) Derived from RouteTopology, 3) Default to NJT
    static func systemStringsForStation(_ code: String) -> Set<String> {
        // Check explicit overrides first (for special cases like PATH adjacency)
        if let override = stationSystemOverrides[code] {
            return override
        }
        // Use RouteTopology-derived mapping
        if let derived = derivedStationSystems[code] {
            return derived
        }
        // Default for stations not in any route (shouldn't happen, but safe fallback)
        return ["NJT"]
    }

    /// Check if a station should be visible based on selected system strings
    /// A station is visible if ANY of the selected systems serve it
    static func isStationVisible(_ code: String, withSystemStrings selectedSystems: Set<String>) -> Bool {
        let stationSystems = systemStringsForStation(code)
        return !stationSystems.isDisjoint(with: selectedSystems)
    }

    // MARK: - Station Code Equivalence

    /// Returns true if two station codes refer to the same physical station.
    /// Handles cross-system equivalents (Amtrak/MNR) and subway complexes.
    static func areEquivalentStations(_ code1: String, _ code2: String) -> Bool {
        if code1 == code2 { return true }
        guard let group = stationEquivalents[code1] else { return false }
        return group.contains(code2)
    }
}

// MARK: - Default Map Region

extension MKCoordinateRegion {
    /// Default map region centered on Newark Penn Station with appropriate zoom level
    /// for viewing the NJ Transit network. Used as the consistent "home" view.
    static let newarkPennDefault = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 40.7348, longitude: -74.1644), // Newark Penn Station
        span: MKCoordinateSpan(latitudeDelta: 1.5, longitudeDelta: 1.5)
    )
}
