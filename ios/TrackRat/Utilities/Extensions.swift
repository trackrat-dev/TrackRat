import SwiftUI
import Foundation

// MARK: - Color Extension
extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (1, 1, 1, 0)
        }
        
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue:  Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

// MARK: - Date Extension for Eastern Time
extension DateFormatter {
    static let easternTimeFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        return formatter
    }()
    
    static func easternTime(date dateStyle: DateFormatter.Style? = nil, time timeStyle: DateFormatter.Style? = nil) -> DateFormatter {
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        if let dateStyle = dateStyle {
            formatter.dateStyle = dateStyle
        }
        if let timeStyle = timeStyle {
            formatter.timeStyle = timeStyle
        }
        return formatter
    }
}

// MARK: - Navigation Bar Styling
struct GlassmorphicNavigationBar: ViewModifier {
    func body(content: Content) -> some View {
        content
            .toolbarBackground(.ultraThinMaterial, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
    }
}

struct ScrollAwareNavigationBar: ViewModifier {
    let isVisible: Bool
    
    func body(content: Content) -> some View {
        content
            .toolbarBackground(.ultraThinMaterial, for: .navigationBar)
            .toolbarBackground(isVisible ? .visible : .hidden, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
    }
}

extension View {
    func glassmorphicNavigationBar() -> some View {
        self.modifier(GlassmorphicNavigationBar())
    }
    
    func scrollAwareNavigationBar(isVisible: Bool) -> some View {
        self.modifier(ScrollAwareNavigationBar(isVisible: isVisible))
    }
    
    func cornerRadius(_ radius: CGFloat, corners: UIRectCorner) -> some View {
        clipShape(RoundedCorners(radius: radius, corners: corners))
    }
}

struct RoundedCorners: Shape {
    var radius: CGFloat = .infinity
    var corners: UIRectCorner = .allCorners

    func path(in rect: CGRect) -> Path {
        let path = UIBezierPath(
            roundedRect: rect,
            byRoundingCorners: corners,
            cornerRadii: CGSize(width: radius, height: radius)
        )
        return Path(path.cgPath)
    }
}

// MARK: - Station Name Normalizer
struct StationNameNormalizer {
    /// Mapping from API station names to preferred display names
    private static let displayNameMapping: [String: String] = [
        // Washington DC stations - unify all variations to "Washington Union Station"
        "Washington Station": "Washington Union Station",
        "Washington Union": "Washington Union Station",
        "WASHI": "Washington Union Station",
        
        // Future mappings can be added here for other station name inconsistencies
        // Example: "Newark Airport": "Newark Liberty International Airport"
    ]
    
    /// Returns the normalized display name for a given API station name.
    /// If no mapping exists, returns the original station name unchanged.
    static func normalizedName(for apiStationName: String) -> String {
        return displayNameMapping[apiStationName] ?? apiStationName
    }
}

// MARK: - Stations Extension
extension Stations {
    static func displayName(for stationName: String) -> String {
        // First normalize the station name to handle API inconsistencies
        let normalizedName = StationNameNormalizer.normalizedName(for: stationName)
        
        // Then apply short display names for UI
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
    
    /// Robust station matching that handles API inconsistencies
    /// Uses station code first (most reliable), falls back to normalized name matching
    static func stationMatches(_ stop: Stop, stationCode: String) -> Bool {
        // Strategy 1: Direct station code match (most reliable)
        if let stopCode = stop.stationCode, stopCode == stationCode {
            return true
        }
        
        // Strategy 2: Normalized name matching (fallback)
        let normalizedStopName = StationNameNormalizer.normalizedName(for: stop.stationName)
        return getStationCode(normalizedStopName) == stationCode
    }
}