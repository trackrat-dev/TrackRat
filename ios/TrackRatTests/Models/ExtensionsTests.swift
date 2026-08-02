import XCTest
import SwiftUI
import UIKit

@testable import TrackRat

class ExtensionsTests: XCTestCase {
    
    // MARK: - Color Extension Tests
    
    func testColorHexInitialization() {
        // Test 6-digit hex (RGB)
        let redColor = Color(hex: "FF0000")
        let greenColor = Color(hex: "00FF00")
        let blueColor = Color(hex: "0000FF")
        let whiteColor = Color(hex: "FFFFFF")
        let blackColor = Color(hex: "000000")
        
        // Colors should be created without throwing
        XCTAssertNotNil(redColor)
        XCTAssertNotNil(greenColor)
        XCTAssertNotNil(blueColor)
        XCTAssertNotNil(whiteColor)
        XCTAssertNotNil(blackColor)
    }
    
    func testColorHex3Digit() {
        // Test 3-digit hex (RGB shorthand)
        let red = Color(hex: "F00")
        let green = Color(hex: "0F0")
        let blue = Color(hex: "00F")
        let white = Color(hex: "FFF")
        let black = Color(hex: "000")
        
        XCTAssertNotNil(red)
        XCTAssertNotNil(green)
        XCTAssertNotNil(blue)
        XCTAssertNotNil(white)
        XCTAssertNotNil(black)
    }
    
    func testColorHex8Digit() {
        // Test 8-digit hex (ARGB)
        let transparentRed = Color(hex: "80FF0000")
        let opaqueBlue = Color(hex: "FF0000FF")
        
        XCTAssertNotNil(transparentRed)
        XCTAssertNotNil(opaqueBlue)
    }
    
    func testColorHexWithPrefixes() {
        // Test with # prefix (should be stripped)
        let withHash = Color(hex: "#FF0000")
        let withoutHash = Color(hex: "FF0000")
        
        XCTAssertNotNil(withHash)
        XCTAssertNotNil(withoutHash)
    }
    
    func testColorHexLowercase() {
        // Test lowercase hex
        let lowercaseRed = Color(hex: "ff0000")
        let mixedCaseGreen = Color(hex: "00Ff00")
        
        XCTAssertNotNil(lowercaseRed)
        XCTAssertNotNil(mixedCaseGreen)
    }
    
    func testColorHexInvalidFormats() {
        // Test invalid hex formats (should default to transparent black-ish)
        let empty = Color(hex: "")
        let tooShort = Color(hex: "F")
        let tooLong = Color(hex: "FF0000FF00")
        let invalidChars = Color(hex: "GGGGGG")
        
        XCTAssertNotNil(empty)
        XCTAssertNotNil(tooShort)
        XCTAssertNotNil(tooLong)
        XCTAssertNotNil(invalidChars)
    }
    
    // MARK: - DateFormatter Extension Tests
    
    func testEasternTimeFormatter() {
        let formatter = DateFormatter.easternTimeFormatter
        
        XCTAssertEqual(formatter.timeZone?.identifier, "America/New_York")
        XCTAssertNotNil(formatter)
    }
    
    func testEasternTimeWithStyles() {
        let dateTimeFormatter = DateFormatter.easternTime(date: .short, time: .short)
        let timeOnlyFormatter = DateFormatter.easternTime(time: .medium)
        let dateOnlyFormatter = DateFormatter.easternTime(date: .long)
        
        XCTAssertEqual(dateTimeFormatter.timeZone?.identifier, "America/New_York")
        XCTAssertEqual(dateTimeFormatter.dateStyle, .short)
        XCTAssertEqual(dateTimeFormatter.timeStyle, .short)
        
        XCTAssertEqual(timeOnlyFormatter.timeZone?.identifier, "America/New_York")
        XCTAssertEqual(timeOnlyFormatter.timeStyle, .medium)
        
        XCTAssertEqual(dateOnlyFormatter.timeZone?.identifier, "America/New_York")
        XCTAssertEqual(dateOnlyFormatter.dateStyle, .long)
    }
    
    func testEasternTimeFormatting() {
        let date = Date(timeIntervalSince1970: 1609459200) // 2021-01-01 00:00:00 UTC
        let formatter = DateFormatter.easternTime(date: .short, time: .short)

        let formatted = formatter.string(from: date)

        // Should include date and time in Eastern format
        XCTAssertFalse(formatted.isEmpty)
        XCTAssertTrue(formatted.contains("/") || formatted.contains("-")) // Date separator
        XCTAssertTrue(formatted.contains(":")) // Time separator
    }

    // MARK: - StationNameNormalizer Tests

    func testStationNameNormalizationKnownMappings() {
        XCTAssertEqual(StationNameNormalizer.normalizedName(for: "Washington Station"),
                      "Washington Union Station")
        XCTAssertEqual(StationNameNormalizer.normalizedName(for: "Washington Union"),
                      "Washington Union Station")
        XCTAssertEqual(StationNameNormalizer.normalizedName(for: "WASHI"),
                      "Washington Union Station")
    }

    func testStationNameNormalizationUnknownStations() {
        let unknownStation = "Unknown Railway Station"
        XCTAssertEqual(StationNameNormalizer.normalizedName(for: unknownStation), unknownStation)

        let emptyStation = ""
        XCTAssertEqual(StationNameNormalizer.normalizedName(for: emptyStation), emptyStation)
    }

    func testStationNameNormalizationCaseSensitive() {
        // Test that mapping is case-sensitive
        XCTAssertEqual(StationNameNormalizer.normalizedName(for: "washington station"),
                      "washington station") // Should not match
        XCTAssertEqual(StationNameNormalizer.normalizedName(for: "Washington Station"),
                      "Washington Union Station") // Should match
    }

    // MARK: - Stations Extension Tests

    func testStationsDisplayName() {
        XCTAssertEqual(Stations.displayName(for: "New York Penn Station"), "New York Penn")
        XCTAssertEqual(Stations.displayName(for: "Newark Penn Station"), "Newark Penn")
        XCTAssertEqual(Stations.displayName(for: "Washington Union Station"), "Washington Union")

        // Test normalized input
        XCTAssertEqual(Stations.displayName(for: "Washington Station"), "Washington Union")

        // Test unknown station (should return normalized name)
        XCTAssertEqual(Stations.displayName(for: "Unknown Station"), "Unknown Station")
    }

    func testStationsDisplayNameWithNormalization() {
        // Test that display name works with names that need normalization
        XCTAssertEqual(Stations.displayName(for: "WASHI"), "Washington Union")
    }

    func testStationMatches() {
        // Test direct station code match
        let stopWithCode = Stop(
            stationCode: "NY",
            stationName: "New York Penn Station",
            scheduledArrival: nil,
            scheduledDeparture: nil,
            actualArrival: nil,
            actualDeparture: nil,
            estimatedArrival: nil,
            pickupOnly: false,
            dropoffOnly: false,
            departed: false,
            departedConfirmedBy: nil,
            stopStatus: nil,
            platform: nil
        )

        XCTAssertTrue(Stations.stationMatches(stopWithCode, stationCode: "NY"))
        XCTAssertFalse(Stations.stationMatches(stopWithCode, stationCode: "NP"))
    }

    func testStationMatchesWithoutCode() {
        // Test fallback to name matching when no station code
        let stopWithoutCode = Stop(
            stationCode: nil,
            stationName: "New York Penn Station",
            scheduledArrival: nil,
            scheduledDeparture: nil,
            actualArrival: nil,
            actualDeparture: nil,
            estimatedArrival: nil,
            pickupOnly: false,
            dropoffOnly: false,
            departed: false,
            departedConfirmedBy: nil,
            stopStatus: nil,
            platform: nil
        )

        XCTAssertTrue(Stations.stationMatches(stopWithoutCode, stationCode: "NY"))
        XCTAssertFalse(Stations.stationMatches(stopWithoutCode, stationCode: "NP"))
    }

    func testStationMatchesWithNormalization() {
        // Test station matching with name that needs normalization
        let stopWithUnnormalizedName = Stop(
            stationCode: nil,
            stationName: "Washington Station", // Will be normalized to "Washington Union Station"
            scheduledArrival: nil,
            scheduledDeparture: nil,
            actualArrival: nil,
            actualDeparture: nil,
            estimatedArrival: nil,
            pickupOnly: false,
            dropoffOnly: false,
            departed: false,
            departedConfirmedBy: nil,
            stopStatus: nil,
            platform: nil
        )

        XCTAssertTrue(Stations.stationMatches(stopWithUnnormalizedName, stationCode: "WS"))
    }

    func testStationMatchesEmptyCode() {
        let stop = Stop(
            stationCode: "",
            stationName: "New York Penn Station",
            scheduledArrival: nil,
            scheduledDeparture: nil,
            actualArrival: nil,
            actualDeparture: nil,
            estimatedArrival: nil,
            pickupOnly: false,
            dropoffOnly: false,
            departed: false,
            departedConfirmedBy: nil,
            stopStatus: nil,
            platform: nil
        )

        XCTAssertTrue(Stations.stationMatches(stop, stationCode: "NY"))
        XCTAssertFalse(Stations.stationMatches(stop, stationCode: ""))
    }

    func testStationMatchesUnknownStation() {
        let unknownStop = Stop(
            stationCode: nil,
            stationName: "Unknown Railway Station",
            scheduledArrival: nil,
            scheduledDeparture: nil,
            actualArrival: nil,
            actualDeparture: nil,
            estimatedArrival: nil,
            pickupOnly: false,
            dropoffOnly: false,
            departed: false,
            departedConfirmedBy: nil,
            stopStatus: nil,
            platform: nil
        )

        XCTAssertFalse(Stations.stationMatches(unknownStop, stationCode: "NY"))
        XCTAssertFalse(Stations.stationMatches(unknownStop, stationCode: "UNKNOWN"))
    }

    // MARK: - View Extension Tests

    func testGlassmorphicNavigationBarModifier() {
        let view = Text("Test")
        let modifiedView = view.glassmorphicNavigationBar()

        // Verify the modifier is applied (basic test)
        XCTAssertNotNil(modifiedView)
    }

    func testCornerRadiusModifier() {
        let view = Rectangle()
        let modifiedView = view.cornerRadius(10, corners: [.topLeft, .topRight])

        // Verify the modifier is applied (basic test)
        XCTAssertNotNil(modifiedView)
    }

    // MARK: - RoundedCorners Shape Tests

    func testRoundedCornersShape() {
        let shape = RoundedCorners(radius: 10, corners: .topLeft)
        let rect = CGRect(x: 0, y: 0, width: 100, height: 100)
        let path = shape.path(in: rect)

        XCTAssertNotNil(path)
        XCTAssertFalse(path.isEmpty)
    }

    func testRoundedCornersAllCorners() {
        let shape = RoundedCorners(radius: 15, corners: .allCorners)
        let rect = CGRect(x: 0, y: 0, width: 50, height: 50)
        let path = shape.path(in: rect)

        XCTAssertNotNil(path)
        XCTAssertFalse(path.isEmpty)
    }

    func testRoundedCornersNoCorners() {
        let shape = RoundedCorners(radius: 10, corners: [])
        let rect = CGRect(x: 0, y: 0, width: 100, height: 100)
        let path = shape.path(in: rect)

        XCTAssertNotNil(path)
    }

    func testRoundedCornersZeroRadius() {
        let shape = RoundedCorners(radius: 0, corners: .allCorners)
        let rect = CGRect(x: 0, y: 0, width: 100, height: 100)
        let path = shape.path(in: rect)

        XCTAssertNotNil(path)
        XCTAssertFalse(path.isEmpty)
    }

    // MARK: - Integration Tests

    func testStationMatchingWithRealData() {
        // Test with realistic station data
        let stops = [
            Stop(
                stationCode: "NY",
                stationName: "New York Penn Station",
                scheduledArrival: Date(),
                scheduledDeparture: Date(),
                actualArrival: nil,
                actualDeparture: nil,
                estimatedArrival: nil,
                pickupOnly: false,
                dropoffOnly: false,
                departed: false,
                departedConfirmedBy: nil,
                stopStatus: nil,
                platform: "7"
            ),
            Stop(
                stationCode: nil,
                stationName: "Washington Station", // Needs normalization
                scheduledArrival: Date(),
                scheduledDeparture: Date(),
                actualArrival: nil,
                actualDeparture: nil,
                estimatedArrival: nil,
                pickupOnly: false,
                dropoffOnly: false,
                departed: false,
                departedConfirmedBy: nil,
                stopStatus: nil,
                platform: "12"
            )
        ]

        XCTAssertTrue(Stations.stationMatches(stops[0], stationCode: "NY"))
        XCTAssertTrue(Stations.stationMatches(stops[1], stationCode: "WS")) // Should match normalized name
        XCTAssertFalse(Stations.stationMatches(stops[0], stationCode: "WS"))
        XCTAssertFalse(Stations.stationMatches(stops[1], stationCode: "NY"))
    }

    func testDisplayNameConsistency() {
        // Test that display names are consistent with station codes
        let testStations = [
            "New York Penn Station",
            "Newark Penn Station",
            "Washington Union Station",
            "Philadelphia",
            "Boston South"
        ]

        for station in testStations {
            let displayName = Stations.displayName(for: station)
            XCTAssertFalse(displayName.isEmpty, "Display name should not be empty for \(station)")

            // Display name should be shorter or equal to original
            XCTAssertLessThanOrEqual(displayName.count, station.count,
                                   "Display name should not be longer than original for \(station)")
        }
    }

    // MARK: - Edge Cases and Error Handling

    func testStationMatchingEmptyInputs() {
        let emptyStop = Stop(
            stationCode: "",
            stationName: "",
            scheduledArrival: nil,
            scheduledDeparture: nil,
            actualArrival: nil,
            actualDeparture: nil,
            estimatedArrival: nil,
            pickupOnly: false,
            dropoffOnly: false,
            departed: false,
            departedConfirmedBy: nil,
            stopStatus: nil,
            platform: nil
        )

        XCTAssertFalse(Stations.stationMatches(emptyStop, stationCode: ""))
        XCTAssertFalse(Stations.stationMatches(emptyStop, stationCode: "NY"))
    }

    func testColorHexPerformance() {
        measure {
            for _ in 0..<1000 {
                _ = Color(hex: "FF0000")
                _ = Color(hex: "00FF00")
                _ = Color(hex: "0000FF")
            }
        }
    }

    func testStationNormalizationPerformance() {
        let stations = ["Washington Station", "Washington Union", "WASHI", "Unknown Station"]

        measure {
            for _ in 0..<1000 {
                for station in stations {
                    _ = StationNameNormalizer.normalizedName(for: station)
                }
            }
        }
    }

    func testDateFormatterPerformance() {
        let date = Date()

        measure {
            for _ in 0..<100 {
                let formatter = DateFormatter.easternTime(date: .short, time: .short)
                _ = formatter.string(from: date)
            }
        }
    }

    // MARK: - CongestionColors Tier Keys

    /// A nil frequency factor renders gray ("no data") and gets its own key so
    /// those segments only merge with each other.
    func testFrequencyTierKeyNilIsNoFreq() {
        XCTAssertEqual(CongestionColors.frequencyTierKey(forFactor: nil, cancellationRate: 0), "nofreq")
    }

    /// The tier key boundaries must line up with the frequency color thresholds
    /// (healthy ≥ 0.9, moderate ≥ 0.7, reduced ≥ 0.5, else severe) so a merged
    /// run is drawn in exactly the color its segments would render individually.
    func testFrequencyTierKeyBoundariesMatchColorThresholds() {
        XCTAssertEqual(CongestionColors.frequencyTierKey(forFactor: 1.3, cancellationRate: 0), "healthy")
        XCTAssertEqual(CongestionColors.frequencyTierKey(forFactor: 0.9, cancellationRate: 0), "healthy")
        XCTAssertEqual(CongestionColors.frequencyTierKey(forFactor: 0.89, cancellationRate: 0), "moderate")
        XCTAssertEqual(CongestionColors.frequencyTierKey(forFactor: 0.7, cancellationRate: 0), "moderate")
        XCTAssertEqual(CongestionColors.frequencyTierKey(forFactor: 0.69, cancellationRate: 0), "reduced")
        XCTAssertEqual(CongestionColors.frequencyTierKey(forFactor: 0.5, cancellationRate: 0), "reduced")
        XCTAssertEqual(CongestionColors.frequencyTierKey(forFactor: 0.49, cancellationRate: 0), "severe")
    }

    /// Cancellations drag the effective frequency down (~1 tier per 10%), matching
    /// `color(forFrequencyFactor:cancellationRate:)`.
    func testFrequencyTierKeyFoldsCancellations() {
        XCTAssertEqual(CongestionColors.frequencyTierKey(forFactor: 0.95, cancellationRate: 0), "healthy")
        // 0.95 - 20% * 0.020 = 0.55 -> reduced
        XCTAssertEqual(CongestionColors.frequencyTierKey(forFactor: 0.95, cancellationRate: 20), "reduced")
    }

    /// Cancellations may only move the delay tier once enough scheduled journeys
    /// back the rate. Below `cancellationMinJourneys`, one cancelled train against
    /// one running train is a 50% rate that alone clears severe — the arithmetic
    /// behind issue #1638's "red but there are no delays" report.
    func testCongestionColorKeyIgnoresCancellationsBelowTheJourneyFloor() {
        // 1.0 + 50% * 0.015 = 1.75 (severe) if the rate were counted. Compared
        // against an undelayed segment's own key rather than a literal, so the
        // assertion survives changes to the ramp's step count.
        XCTAssertEqual(
            CongestionColors.congestionColorKey(
                forFactor: 1.0, cancellationRate: 50, totalJourneys: 2),
            CongestionColors.congestionColorKey(forFactor: 1.0)
        )
    }

    /// The floor is inclusive, and above it the #1246 escalation is unchanged.
    func testCongestionColorKeyFoldsCancellationsAtAndAboveTheFloor() {
        XCTAssertEqual(
            CongestionColors.congestionColorKey(
                forFactor: 1.0, cancellationRate: 50,
                totalJourneys: CongestionColors.cancellationMinJourneys),
            CongestionColors.congestionColorKey(forFactor: 1.75)
        )
        XCTAssertNotEqual(
            CongestionColors.congestionColorKey(
                forFactor: 1.0, cancellationRate: 50,
                totalJourneys: CongestionColors.cancellationMinJourneys),
            CongestionColors.congestionColorKey(forFactor: 1.0)
        )
        XCTAssertEqual(
            CongestionColors.congestionColorKey(
                forFactor: 1.0, cancellationRate: 50,
                totalJourneys: CongestionColors.cancellationMinJourneys - 1),
            CongestionColors.congestionColorKey(forFactor: 1.0)
        )
    }

    /// The floor gates cancellations only. A sparse segment whose trains really
    /// lost time must still escalate, or the floor would mute real delays on the
    /// low-frequency stretches riders most need warning about.
    func testCongestionColorKeyKeepsDelaysBelowTheJourneyFloor() {
        XCTAssertNotEqual(
            CongestionColors.congestionColorKey(
                forFactor: 1.8, cancellationRate: 50, totalJourneys: 1),
            CongestionColors.congestionColorKey(forFactor: 1.0)
        )
    }

    /// The color and the merge key must agree, or a merged run is drawn in a
    /// color none of its segments would render individually. With a ramp the
    /// interesting case is no longer "which of four tiers" but "do equal keys
    /// imply equal colors, and unequal keys imply unequal colors".
    func testCongestionColorAgreesWithColorKeyAcrossTheFloor() {
        // Below the journey floor the cancellations are dropped, so this is an
        // undelayed segment: flat green, and the same key as factor 1.0.
        XCTAssertEqual(
            CongestionColors.color(
                forCongestionFactor: 1.0, cancellationRate: 50, totalJourneys: 2),
            .systemGreen
        )

        let sparse = (factor: 1.0, rate: 50.0, journeys: 2)
        let sustained = (factor: 1.0, rate: 50.0, journeys: 10)
        let sustainedColor = CongestionColors.color(
            forCongestionFactor: sustained.factor,
            cancellationRate: sustained.rate, totalJourneys: sustained.journeys)

        // Sustained cancellations must move the segment well off green...
        XCTAssertNotEqual(
            rgba(sustainedColor), rgba(.systemGreen),
            "sustained cancellations must not render as an on-time segment")
        // ...and the key must move with it.
        XCTAssertNotEqual(
            CongestionColors.congestionColorKey(
                forFactor: sparse.factor, cancellationRate: sparse.rate,
                totalJourneys: sparse.journeys),
            CongestionColors.congestionColorKey(
                forFactor: sustained.factor, cancellationRate: sustained.rate,
                totalJourneys: sustained.journeys)
        )
    }

    /// Equal keys must mean pixel-identical strokes: the merge concatenates
    /// geometry and paints the run with one representative's color, so any
    /// disagreement silently recolors its neighbours.
    func testEqualColorKeysImplyIdenticalColors() {
        var colorsByKey: [String: [UIColor]] = [:]
        for hundredths in 90...220 {
            let factor = Double(hundredths) / 100.0
            let key = CongestionColors.congestionColorKey(forFactor: factor)
            colorsByKey[key, default: []].append(
                CongestionColors.color(forCongestionFactor: factor))
        }
        XCTAssertGreaterThan(colorsByKey.count, 1, "the ramp must have several steps")
        for (key, colors) in colorsByKey {
            let components = Set(colors.map { rgba($0) })
            XCTAssertEqual(
                components.count, 1,
                "key \(key) maps to more than one color: \(components)")
        }
    }

    /// The ramp must not cliff-edge anywhere — the actual complaint in #1715.
    ///
    /// The bound is a fraction of the ramp's own total length rather than an
    /// absolute number, so it stays meaningful if the palette is retuned. Under
    /// the previous four-bucket scheme a single step at a threshold covered a
    /// whole tier-to-tier gap and would blow straight through this.
    func testRampHasNoLargeColorJumps() {
        let samples = stride(from: 1.10, through: 2.00, by: 0.005).map {
            rgba(CongestionColors.color(forCongestionFactor: $0))
        }
        let jumps = zip(samples, samples.dropFirst()).map { from, to in distance(from, to) }
        let rampLength = jumps.reduce(0, +)
        XCTAssertGreaterThan(rampLength, 0, "the ramp must actually travel")
        let largest = jumps.max() ?? 0
        XCTAssertLessThan(
            largest, rampLength / 8,
            "ramp has a cliff: largest single step \(largest) of total \(rampLength)")
    }

    /// Sub-threshold factors stay flat green: that plateau is the backend's
    /// "these trains are on time" statement and must not be shaded.
    func testOnTimePlateauIsFlatGreen() {
        for factor in [0.82, 0.95, 1.0, 1.05, 1.1] {
            XCTAssertEqual(
                CongestionColors.color(forCongestionFactor: factor), .systemGreen,
                "factor \(factor) should render as an on-time segment")
        }
    }

    /// Resolve a possibly-dynamic UIColor to concrete components so two colors
    /// can be compared by appearance rather than by object identity.
    private func rgba(_ color: UIColor) -> [CGFloat] {
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        color.resolvedColor(with: UITraitCollection(userInterfaceStyle: .dark))
            .getRed(&r, green: &g, blue: &b, alpha: &a)
        // Rounded so float noise from interpolation doesn't split equal colors.
        return [r, g, b, a].map { ($0 * 1000).rounded() / 1000 }
    }

    private func distance(_ lhs: [CGFloat], _ rhs: [CGFloat]) -> CGFloat {
        sqrt(zip(lhs, rhs).map { left, right in (left - right) * (left - right) }.reduce(0, +))
    }

    /// The merge fix: in Health mode segments are colored by frequency, so the
    /// merge key must group by the frequency tier, not the delay tier.
    /// Same frequency color but different delay tiers -> one merge key (previously
    /// left unmerged); different frequency colors but the same delay tier ->
    /// different keys (previously merged into one wrongly-colored run).
    func testFrequencyTierKeyRegroupsIndependentlyOfDelay() {
        // Same frequency color (both healthy), different delay tiers -> merge.
        XCTAssertEqual(
            CongestionColors.frequencyTierKey(forFactor: 0.95, cancellationRate: 0),
            CongestionColors.frequencyTierKey(forFactor: 0.92, cancellationRate: 0)
        )
        XCTAssertNotEqual(
            CongestionColors.congestionColorKey(forFactor: 1.0),
            CongestionColors.congestionColorKey(forFactor: 2.0)
        )
        // Different frequency colors, identical delay tier -> do NOT merge.
        XCTAssertNotEqual(
            CongestionColors.frequencyTierKey(forFactor: 0.95, cancellationRate: 0),
            CongestionColors.frequencyTierKey(forFactor: 0.55, cancellationRate: 0)
        )
        XCTAssertEqual(
            CongestionColors.congestionColorKey(forFactor: 1.0),
            CongestionColors.congestionColorKey(forFactor: 1.05)
        )
    }
}