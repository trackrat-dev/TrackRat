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
///
/// Cancellations are folded into the delay/frequency factor before bucketing into a
/// color tier, so a single color communicates "how bad is this segment" combining
/// delays and cancellations. Weights are tuned so a 10% cancellation rate shifts
/// the color roughly one tier toward red.
enum CongestionColors {
    // Thresholds mirror backend `congestion_types.py`:
    //   normal   factor <= 1.10  (≤10% slower than baseline)
    //   moderate factor <= 1.25  (10-25% slower)
    //   heavy    factor <= 1.50  (25-50% slower)
    //   severe   factor >  1.50  (>50% slower)
    static let normalThreshold: Double = 1.10
    static let moderateThreshold: Double = 1.25
    static let heavyThreshold: Double = 1.50

    static let cancellationCongestionWeight: Double = 0.015  // ~1 tier per 10% cancellation
    static let cancellationFrequencyWeight: Double = 0.020   // ~1 tier per 10% cancellation

    /// Minimum scheduled journeys (running + cancelled) before cancellations may
    /// escalate a segment's delay color. Mirrors backend
    /// `congestion_types.CANCELLATION_MIN_JOURNEYS`; keep the two in step, or iOS
    /// paints a segment red that the backend reports as normal. Below the floor
    /// one cancellation against one running train is a 50% rate — enough on its
    /// own for severe, with every train that ran exactly on time (issue #1638).
    static let cancellationMinJourneys: Int = 5

    /// Whether a cancellation rate measured over `totalJourneys` journeys is
    /// solid enough to move a segment's color.
    static func cancellationsAreConclusive(totalJourneys: Int) -> Bool {
        totalJourneys >= cancellationMinJourneys
    }

    /// Delay factor with the cancellation term applied only when it is conclusive.
    private static func effectiveCongestionFactor(
        _ factor: Double, cancellationRate: Double, totalJourneys: Int
    ) -> Double {
        guard cancellationsAreConclusive(totalJourneys: totalJourneys) else { return factor }
        return factor + max(0, cancellationRate) * cancellationCongestionWeight
    }

    /// Factor at which each tier's color is fully reached. `severe` has no upper
    /// bound as a tier, so 2.0 — twice the baseline transit time — anchors the end
    /// of the ramp; past it the color simply stays fully red.
    private static let rampStops: [(factor: Double, color: UIColor)] = [
        (normalThreshold, .systemGreen),
        (moderateThreshold, .systemYellow),
        (heavyThreshold, .systemOrange),
        (2.0, .systemRed),
    ]

    /// How many discrete colors the ramp is quantised to.
    ///
    /// The map merges runs of adjacent segments that render the same color into a
    /// single overlay (`aggregatedCongestionRuns`), so the color has to come from
    /// a finite set — a truly continuous ramp would give every segment its own
    /// color and therefore its own overlay.
    ///
    /// Sized against the *narrowest* span, not the whole ramp: moderate is only
    /// 0.15 wide against the ramp's 0.9, so it gets a ninth of the steps. At 24
    /// steps that span would be crossed in four visible jumps — banding, which is
    /// the same complaint in miniature. 64 keeps every span smooth while still
    /// collapsing the on-time plateau, which is the large majority of segments,
    /// into a single merged color at step 0.
    static let congestionRampSteps = 64

    /// Color for a delay-based congestion factor (higher = more delayed),
    /// interpolated between the tier colors rather than snapped to one of four.
    ///
    /// The tier colors still land exactly on their own thresholds, so the map
    /// legend keeps describing the map truthfully; only the space between
    /// thresholds is filled in. This is issue #1715: adjacent segments whose
    /// delays differ slightly now differ slightly in color, instead of one at
    /// 1.24 rendering full yellow beside one at 1.26 rendering full orange.
    ///
    /// Everything at or below `normalThreshold` stays flat green — that plateau
    /// is the backend's "these trains are on time" statement (sub-minute noise is
    /// pinned to exactly 1.0 by `MIN_CONGESTION_DELAY_MINUTES`), so shading it
    /// would make ordinary on-time track read as faintly congested.
    static func color(forCongestionFactor factor: Double) -> UIColor {
        rampColor(atStep: rampStep(forFactor: factor))
    }

    /// Quantised position along the ramp, `0...congestionRampSteps`.
    /// Colors and merge keys are both derived from this, so two segments share an
    /// overlay exactly when they share a color.
    static func rampStep(forFactor factor: Double) -> Int {
        guard factor.isFinite else { return 0 }
        let first = rampStops[0].factor
        let last = rampStops[rampStops.count - 1].factor
        let position = (factor - first) / (last - first)
        let clamped = min(max(position, 0), 1)
        return Int((clamped * Double(congestionRampSteps)).rounded())
    }

    /// Factor at a normalised position `0...1` along the ramp — the inverse of
    /// `rampStep(forFactor:)`. The map legend walks this to draw the exact
    /// gradient the overlays are painted with.
    static func rampFactor(atPosition position: Double) -> Double {
        let first = rampStops[0].factor
        let last = rampStops[rampStops.count - 1].factor
        return first + (last - first) * min(max(position, 0), 1)
    }

    private static func rampColor(atStep step: Int) -> UIColor {
        let factor = rampFactor(
            atPosition: Double(step) / Double(congestionRampSteps))

        for i in 1..<rampStops.count where factor < rampStops[i].factor {
            let lower = rampStops[i - 1]
            let upper = rampStops[i]
            let t = (factor - lower.factor) / (upper.factor - lower.factor)
            return blend(lower.color, upper.color, CGFloat(t))
        }
        return rampStops[rampStops.count - 1].color
    }

    /// Interpolate two colors while preserving their light/dark adaptation:
    /// both endpoints are resolved inside the dynamic provider, against whatever
    /// traits the renderer is drawing with, rather than being flattened up front.
    ///
    /// The endpoints are returned as-is rather than wrapped, so a step that lands
    /// exactly on a tier yields that tier's own system color — which is the
    /// overwhelmingly common case (the on-time plateau is step 0) and keeps those
    /// segments on a plain, allocation-free `.systemGreen`.
    private static func blend(_ from: UIColor, _ to: UIColor, _ t: CGFloat) -> UIColor {
        if t <= 0 { return from }
        if t >= 1 { return to }
        return UIColor { traits in
            var fr: CGFloat = 0, fg: CGFloat = 0, fb: CGFloat = 0, fa: CGFloat = 0
            var tr: CGFloat = 0, tg: CGFloat = 0, tb: CGFloat = 0, ta: CGFloat = 0
            from.resolvedColor(with: traits).getRed(&fr, green: &fg, blue: &fb, alpha: &fa)
            to.resolvedColor(with: traits).getRed(&tr, green: &tg, blue: &tb, alpha: &ta)
            return UIColor(
                red: fr + (tr - fr) * t,
                green: fg + (tg - fg) * t,
                blue: fb + (tb - fb) * t,
                alpha: fa + (ta - fa) * t)
        }
    }

    /// Color for delay-based congestion factor with cancellation rate folded in.
    ///
    /// `totalJourneys` is how many scheduled journeys (running + cancelled) the
    /// rate was measured over; below `cancellationMinJourneys` the cancellation
    /// term is dropped, matching the backend's gate (issue #1638).
    static func color(
        forCongestionFactor factor: Double, cancellationRate: Double, totalJourneys: Int
    ) -> UIColor {
        color(
            forCongestionFactor: effectiveCongestionFactor(
                factor, cancellationRate: cancellationRate, totalJourneys: totalJourneys))
    }

    /// Color for frequency factor (higher = healthier service).
    static func color(forFrequencyFactor factor: Double?) -> UIColor {
        guard let factor else { return .systemGray }
        if factor >= 0.9 { return .systemGreen }
        else if factor >= 0.7 { return .systemYellow }
        else if factor >= 0.5 { return .systemOrange }
        else { return .systemRed }
    }

    /// Color for frequency factor with cancellation rate folded in.
    static func color(forFrequencyFactor factor: Double?, cancellationRate: Double) -> UIColor {
        guard let factor else { return .systemGray }
        return color(forFrequencyFactor: factor - max(0, cancellationRate) * cancellationFrequencyWeight)
    }

    /// Stable identifier for the delay-based color this segment would render as.
    /// Used to group adjacent segments with the same effective color into one overlay.
    static func congestionColorKey(
        forFactor factor: Double, cancellationRate: Double, totalJourneys: Int
    ) -> String {
        congestionColorKey(
            forFactor: effectiveCongestionFactor(
                factor, cancellationRate: cancellationRate, totalJourneys: totalJourneys))
    }

    /// Color key for a delay factor with no cancellation component — the
    /// per-train individual-journey segments, which carry no cancellation rate.
    /// Derived from the same quantised ramp step as the color itself, so segments
    /// merge into one overlay exactly when they render identically.
    static func congestionColorKey(forFactor effective: Double) -> String {
        "ramp\(rampStep(forFactor: effective))"
    }

    /// Stable identifier for the frequency-based color tier this segment would render as.
    /// Mirrors `color(forFrequencyFactor:cancellationRate:)` so merged runs group exactly
    /// as they are colored in Health mode. A nil factor renders gray ("no data") and gets
    /// its own key so those segments only merge with each other.
    static func frequencyTierKey(forFactor factor: Double?, cancellationRate: Double) -> String {
        guard let factor else { return "nofreq" }
        let effective = factor - max(0, cancellationRate) * cancellationFrequencyWeight
        if effective >= 0.9 { return "healthy" }
        if effective >= 0.7 { return "moderate" }
        if effective >= 0.5 { return "reduced" }
        return "severe"
    }
}