import SwiftUI
import Foundation

// MARK: - Date Formatter Extensions for API
extension Formatter {
    static let iso8601withFractionalSeconds: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSS"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(identifier: "America/New_York") // Assume Eastern Time
        return formatter
    }()
    
    static let iso8601withFractionalSecondsAndTimezone: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSXXXXX"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        return formatter
    }()
    
    // Changed to standard DateFormatter for more control over format without fractional seconds
    static let customISO8601withoutFractionalSeconds: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        formatter.locale = Locale(identifier: "en_US_POSIX") // Essential for specific formats
        formatter.timeZone = TimeZone(identifier: "America/New_York")    // Assume Eastern Time if no offset provided
        return formatter
    }()
    
    static let customISO8601withTimezone: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ssXXXXX"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        return formatter
    }()
}

// MARK: - Date Extension for ISO8601 Parsing
extension Date {
    static func fromISO8601(_ string: String) -> Date? {
        // Try different date formats in order of likelihood
        
        // 1. With timezone offset and fractional seconds
        if let date = Formatter.iso8601withFractionalSecondsAndTimezone.date(from: string) {
            return date
        }
        
        // 2. With timezone offset but no fractional seconds
        if let date = Formatter.customISO8601withTimezone.date(from: string) {
            return date
        }
        
        // 3. Remove 'Z' suffix if present to treat as Eastern Time
        let cleanedString = string.hasSuffix("Z") ? String(string.dropLast()) : string
        
        // 4. Try with fractional seconds (no timezone)
        if let date = Formatter.iso8601withFractionalSeconds.date(from: cleanedString) {
            return date
        }
        
        // 5. Try without fractional seconds (no timezone)
        if let date = Formatter.customISO8601withoutFractionalSeconds.date(from: cleanedString) {
            return date
        }
        
        // 6. Fallback: if the original string had 'Z', try standard ISO8601 parsing
        if string.hasSuffix("Z") {
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = formatter.date(from: string) {
                return date
            }
            formatter.formatOptions = [.withInternetDateTime]
            return formatter.date(from: string)
        }
        
        return nil
    }
    
    /// Convert Date to ISO8601 string with timezone for Live Activities
    func toISO8601String() -> String {
        // Use the timezone-aware formatter to ensure consistent format
        return Formatter.customISO8601withTimezone.string(from: self)
    }
}

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
    
    init?(hex: String?) {
        guard let hex = hex else { return nil }
        self.init(hex: hex)
    }
}

// MARK: - Date Extension for Eastern Time
extension DateFormatter {
    static let easternTimeFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        return formatter
    }()

    /// Cached formatter for "h:mm a" in Eastern Time - used for departure/arrival times
    /// PERFORMANCE: DateFormatter instantiation is expensive, reuse this static instance
    static let easternTimeShort: DateFormatter = {
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        formatter.dateFormat = "h:mm a"
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

// MARK: - Edge Swipe Back Gesture

/// A view modifier that adds edge-swipe-to-go-back functionality.
/// This enables iOS-native-feeling swipe-back navigation even when
/// the system navigation bar is hidden.
struct EdgeSwipeBackModifier: ViewModifier {
    @Binding var navigationPath: NavigationPath
    @GestureState private var dragOffset: CGFloat = 0

    private let edgeWidth: CGFloat = 30
    private let triggerThreshold: CGFloat = 80

    func body(content: Content) -> some View {
        content
            .gesture(
                DragGesture()
                    .updating($dragOffset) { value, state, _ in
                        // Only track if started from left edge
                        if value.startLocation.x < edgeWidth {
                            state = value.translation.width
                        }
                    }
                    .onEnded { value in
                        // Check if started from left edge and dragged far enough
                        if value.startLocation.x < edgeWidth && value.translation.width > triggerThreshold {
                            if !navigationPath.isEmpty {
                                navigationPath.removeLast()
                            }
                        }
                    }
            )
    }
}

extension View {
    /// Adds edge-swipe gesture to navigate back
    func edgeSwipeBack(path: Binding<NavigationPath>) -> some View {
        self.modifier(EdgeSwipeBackModifier(navigationPath: path))
    }
}

// MARK: - Navigation Bar Styling
struct GlassmorphicNavigationBar: ViewModifier {
    func body(content: Content) -> some View {
        content
            .toolbarBackground(.ultraThinMaterial, for: .navigationBar)
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