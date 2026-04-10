import SwiftUI
import Foundation
import UIKit

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

/// A UIView that only intercepts touches near the left edge.
/// All other touches pass through to views below.
class EdgeSwipeView: UIView {
    // Keep narrow to not block back button, but store initial touch for gesture
    private let hitTestEdgeWidth: CGFloat = 16

    // Store initial touch location for edge detection
    var initialTouchX: CGFloat = 0

    override var intrinsicContentSize: CGSize {
        return CGSize(width: UIView.noIntrinsicMetric, height: UIView.noIntrinsicMetric)
    }

    override func hitTest(_ point: CGPoint, with event: UIEvent?) -> UIView? {
        // Only intercept touches at the very edge (before content padding begins)
        if point.x <= hitTestEdgeWidth {
            initialTouchX = point.x
            return self
        }
        // Let all other touches pass through to back button and content
        return nil
    }
}

/// Enables edge-swipe-to-go-back navigation using a UIPanGestureRecognizer.
/// Captures initial touch position via hitTest to detect edge swipes reliably,
/// even when used alongside ScrollViews in a sheet presentation.
struct EdgeSwipeBackGesture: UIViewRepresentable {
    @Binding var navigationPath: NavigationPath

    func makeUIView(context: Context) -> EdgeSwipeView {
        let view = EdgeSwipeView()
        view.backgroundColor = .clear

        let panGesture = UIPanGestureRecognizer(
            target: context.coordinator,
            action: #selector(Coordinator.handlePan(_:))
        )
        panGesture.delegate = context.coordinator
        view.addGestureRecognizer(panGesture)

        return view
    }

    func updateUIView(_ uiView: EdgeSwipeView, context: Context) {}

    func makeCoordinator() -> Coordinator {
        Coordinator(navigationPath: $navigationPath)
    }

    class Coordinator: NSObject, UIGestureRecognizerDelegate {
        @Binding var navigationPath: NavigationPath
        private var gestureStartX: CGFloat = 0
        // Larger threshold because gesture.location reports position at recognition time,
        // not initial touch time - finger may have moved 20-30px by then
        private let edgeThreshold: CGFloat = 50
        private let swipeThreshold: CGFloat = 80

        init(navigationPath: Binding<NavigationPath>) {
            _navigationPath = navigationPath
        }

        @objc func handlePan(_ gesture: UIPanGestureRecognizer) {
            guard let edgeView = gesture.view as? EdgeSwipeView else { return }

            switch gesture.state {
            case .began:
                gestureStartX = edgeView.initialTouchX
            case .ended:
                let translation = gesture.translation(in: gesture.view)
                if gestureStartX <= edgeThreshold && translation.x > swipeThreshold {
                    if !navigationPath.isEmpty {
                        navigationPath.removeLast()
                    }
                }
            default:
                break
            }
        }

        // MARK: - UIGestureRecognizerDelegate

        func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer) -> Bool {
            // Allow simultaneous recognition to not block scroll views
            return true
        }
    }
}

extension View {
    /// Adds edge-swipe gesture to navigate back using UIScreenEdgePanGestureRecognizer
    func edgeSwipeBack(path: Binding<NavigationPath>) -> some View {
        self.overlay(
            EdgeSwipeBackGesture(navigationPath: path)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .ignoresSafeArea()
        )
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

// MARK: - Congestion Map Color Helpers

/// Shared color helpers used by CongestionMapView and JourneyCongestionMapView.
enum CongestionColors {
    // Thresholds mirror backend `congestion_types.py`:
    //   normal   factor <= 1.10  (≤10% slower than baseline)
    //   moderate factor <= 1.25  (10-25% slower)
    //   heavy    factor <= 1.50  (25-50% slower)
    //   severe   factor >  1.50  (>50% slower)
    static let normalThreshold: Double = 1.10
    static let moderateThreshold: Double = 1.25
    static let heavyThreshold: Double = 1.50

    /// Color for delay-based congestion factor (higher = more delayed).
    static func color(forCongestionFactor factor: Double) -> UIColor {
        if factor <= normalThreshold { return .systemGreen }
        else if factor <= moderateThreshold { return .systemYellow }
        else if factor <= heavyThreshold { return .systemOrange }
        else { return .systemRed }
    }

    /// Color for frequency factor (higher = healthier service).
    static func color(forFrequencyFactor factor: Double?) -> UIColor {
        guard let factor else { return .systemGray }
        if factor >= 0.9 { return .systemGreen }
        else if factor >= 0.7 { return .systemYellow }
        else if factor >= 0.5 { return .systemOrange }
        else { return .systemRed }
    }
}