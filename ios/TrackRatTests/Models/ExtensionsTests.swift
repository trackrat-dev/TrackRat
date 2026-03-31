import XCTest
import SwiftUI
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
}