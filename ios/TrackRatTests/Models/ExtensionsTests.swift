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
    
    func testEasternTimeFormatting() {\n        let date = Date(timeIntervalSince1970: 1609459200) // 2021-01-01 00:00:00 UTC\n        let formatter = DateFormatter.easternTime(date: .short, time: .short)\n        \n        let formatted = formatter.string(from: date)\n        \n        // Should include date and time in Eastern format\n        XCTAssertFalse(formatted.isEmpty)\n        XCTAssertTrue(formatted.contains("/") || formatted.contains("-")) // Date separator\n        XCTAssertTrue(formatted.contains(":")) // Time separator\n    }\n    \n    // MARK: - StationNameNormalizer Tests\n    \n    func testStationNameNormalizationKnownMappings() {\n        XCTAssertEqual(StationNameNormalizer.normalizedName(for: "Washington Station"), \n                      "Washington Union Station")\n        XCTAssertEqual(StationNameNormalizer.normalizedName(for: "Washington Union"), \n                      "Washington Union Station")\n        XCTAssertEqual(StationNameNormalizer.normalizedName(for: "WASHI"), \n                      "Washington Union Station")\n    }\n    \n    func testStationNameNormalizationUnknownStations() {\n        let unknownStation = "Unknown Railway Station"\n        XCTAssertEqual(StationNameNormalizer.normalizedName(for: unknownStation), unknownStation)\n        \n        let emptyStation = ""\n        XCTAssertEqual(StationNameNormalizer.normalizedName(for: emptyStation), emptyStation)\n    }\n    \n    func testStationNameNormalizationCaseSensitive() {\n        // Test that mapping is case-sensitive\n        XCTAssertEqual(StationNameNormalizer.normalizedName(for: "washington station"), \n                      "washington station") // Should not match\n        XCTAssertEqual(StationNameNormalizer.normalizedName(for: "Washington Station"), \n                      "Washington Union Station") // Should match\n    }\n    \n    // MARK: - Stations Extension Tests\n    \n    func testStationsDisplayName() {\n        XCTAssertEqual(Stations.displayName(for: "New York Penn Station"), "New York Penn")\n        XCTAssertEqual(Stations.displayName(for: "Newark Penn Station"), "Newark Penn")\n        XCTAssertEqual(Stations.displayName(for: "Washington Union Station"), "Washington Union")\n        \n        // Test normalized input\n        XCTAssertEqual(Stations.displayName(for: "Washington Station"), "Washington Union")\n        \n        // Test unknown station (should return normalized name)\n        XCTAssertEqual(Stations.displayName(for: "Unknown Station"), "Unknown Station")\n    }\n    \n    func testStationsDisplayNameWithNormalization() {\n        // Test that display name works with names that need normalization\n        XCTAssertEqual(Stations.displayName(for: "WASHI"), "Washington Union")\n    }\n    \n    func testStationMatches() {\n        // Test direct station code match\n        let stopWithCode = Stop(\n            stationCode: "NY",\n            stationName: "New York Penn Station",\n            scheduledTime: nil,\n            departureTime: nil,\n            pickupOnly: false,\n            dropoffOnly: false,\n            departed: false,\n            departedConfirmedBy: nil,\n            stopStatus: nil,\n            platform: nil\n        )\n        \n        XCTAssertTrue(Stations.stationMatches(stopWithCode, stationCode: "NY"))\n        XCTAssertFalse(Stations.stationMatches(stopWithCode, stationCode: "NP"))\n    }\n    \n    func testStationMatchesWithoutCode() {\n        // Test fallback to name matching when no station code\n        let stopWithoutCode = Stop(\n            stationCode: nil,\n            stationName: "New York Penn Station",\n            scheduledTime: nil,\n            departureTime: nil,\n            pickupOnly: false,\n            dropoffOnly: false,\n            departed: false,\n            departedConfirmedBy: nil,\n            stopStatus: nil,\n            platform: nil\n        )\n        \n        XCTAssertTrue(Stations.stationMatches(stopWithoutCode, stationCode: "NY"))\n        XCTAssertFalse(Stations.stationMatches(stopWithoutCode, stationCode: "NP"))\n    }\n    \n    func testStationMatchesWithNormalization() {\n        // Test station matching with name that needs normalization\n        let stopWithUnnormalizedName = Stop(\n            stationCode: nil,\n            stationName: "Washington Station", // Will be normalized to "Washington Union Station"\n            scheduledTime: nil,\n            departureTime: nil,\n            pickupOnly: false,\n            dropoffOnly: false,\n            departed: false,\n            departedConfirmedBy: nil,\n            stopStatus: nil,\n            platform: nil\n        )\n        \n        XCTAssertTrue(Stations.stationMatches(stopWithUnnormalizedName, stationCode: "WS"))\n    }\n    \n    func testStationMatchesEmptyCode() {\n        let stop = Stop(\n            stationCode: "",\n            stationName: "New York Penn Station",\n            scheduledTime: nil,\n            departureTime: nil,\n            pickupOnly: false,\n            dropoffOnly: false,\n            departed: false,\n            departedConfirmedBy: nil,\n            stopStatus: nil,\n            platform: nil\n        )\n        \n        XCTAssertTrue(Stations.stationMatches(stop, stationCode: "NY"))\n        XCTAssertFalse(Stations.stationMatches(stop, stationCode: ""))\n    }\n    \n    func testStationMatchesUnknownStation() {\n        let unknownStop = Stop(\n            stationCode: nil,\n            stationName: "Unknown Railway Station",\n            scheduledTime: nil,\n            departureTime: nil,\n            pickupOnly: false,\n            dropoffOnly: false,\n            departed: false,\n            departedConfirmedBy: nil,\n            stopStatus: nil,\n            platform: nil\n        )\n        \n        XCTAssertFalse(Stations.stationMatches(unknownStop, stationCode: "NY"))\n        XCTAssertFalse(Stations.stationMatches(unknownStop, stationCode: "UNKNOWN"))\n    }\n    \n    // MARK: - View Extension Tests\n    \n    func testGlassmorphicNavigationBarModifier() {\n        let view = Text("Test")\n        let modifiedView = view.glassmorphicNavigationBar()\n        \n        // Verify the modifier is applied (basic test)\n        XCTAssertNotNil(modifiedView)\n    }\n    \n    func testCornerRadiusModifier() {\n        let view = Rectangle()\n        let modifiedView = view.cornerRadius(10, corners: [.topLeft, .topRight])\n        \n        // Verify the modifier is applied (basic test)\n        XCTAssertNotNil(modifiedView)\n    }\n    \n    // MARK: - RoundedCorners Shape Tests\n    \n    func testRoundedCornersShape() {\n        let shape = RoundedCorners(radius: 10, corners: .topLeft)\n        let rect = CGRect(x: 0, y: 0, width: 100, height: 100)\n        let path = shape.path(in: rect)\n        \n        XCTAssertNotNil(path)\n        XCTAssertFalse(path.isEmpty)\n    }\n    \n    func testRoundedCornersAllCorners() {\n        let shape = RoundedCorners(radius: 15, corners: .allCorners)\n        let rect = CGRect(x: 0, y: 0, width: 50, height: 50)\n        let path = shape.path(in: rect)\n        \n        XCTAssertNotNil(path)\n        XCTAssertFalse(path.isEmpty)\n    }\n    \n    func testRoundedCornersNoCorners() {\n        let shape = RoundedCorners(radius: 10, corners: [])\n        let rect = CGRect(x: 0, y: 0, width: 100, height: 100)\n        let path = shape.path(in: rect)\n        \n        XCTAssertNotNil(path)\n    }\n    \n    func testRoundedCornersZeroRadius() {\n        let shape = RoundedCorners(radius: 0, corners: .allCorners)\n        let rect = CGRect(x: 0, y: 0, width: 100, height: 100)\n        let path = shape.path(in: rect)\n        \n        XCTAssertNotNil(path)\n        XCTAssertFalse(path.isEmpty)\n    }\n    \n    // MARK: - Integration Tests\n    \n    func testStationMatchingWithRealData() {\n        // Test with realistic station data\n        let stops = [\n            Stop(\n                stationCode: "NY",\n                stationName: "New York Penn Station",\n                scheduledTime: Date(),\n                departureTime: Date(),\n                pickupOnly: false,\n                dropoffOnly: false,\n                departed: false,\n                departedConfirmedBy: nil,\n                stopStatus: nil,\n                platform: "7"\n            ),\n            Stop(\n                stationCode: nil,\n                stationName: "Washington Station", // Needs normalization\n                scheduledTime: Date(),\n                departureTime: Date(),\n                pickupOnly: false,\n                dropoffOnly: false,\n                departed: false,\n                departedConfirmedBy: nil,\n                stopStatus: nil,\n                platform: "12"\n            )\n        ]\n        \n        XCTAssertTrue(Stations.stationMatches(stops[0], stationCode: "NY"))\n        XCTAssertTrue(Stations.stationMatches(stops[1], stationCode: "WS")) // Should match normalized name\n        XCTAssertFalse(Stations.stationMatches(stops[0], stationCode: "WS"))\n        XCTAssertFalse(Stations.stationMatches(stops[1], stationCode: "NY"))\n    }\n    \n    func testDisplayNameConsistency() {\n        // Test that display names are consistent with station codes\n        let testStations = [\n            "New York Penn Station",\n            "Newark Penn Station", \n            "Washington Union Station",\n            "Philadelphia",\n            "Boston South"\n        ]\n        \n        for station in testStations {\n            let displayName = Stations.displayName(for: station)\n            XCTAssertFalse(displayName.isEmpty, "Display name should not be empty for \\(station)")\n            \n            // Display name should be shorter or equal to original\n            XCTAssertLessThanOrEqual(displayName.count, station.count, \n                                   "Display name should not be longer than original for \\(station)")\n        }\n    }\n    \n    // MARK: - Edge Cases and Error Handling\n    \n    func testStationMatchingEmptyInputs() {\n        let emptyStop = Stop(\n            stationCode: "",\n            stationName: "",\n            scheduledTime: nil,\n            departureTime: nil,\n            pickupOnly: false,\n            dropoffOnly: false,\n            departed: false,\n            departedConfirmedBy: nil,\n            stopStatus: nil,\n            platform: nil\n        )\n        \n        XCTAssertFalse(Stations.stationMatches(emptyStop, stationCode: ""))\n        XCTAssertFalse(Stations.stationMatches(emptyStop, stationCode: "NY"))\n    }\n    \n    func testColorHexPerformance() {\n        measure {\n            for _ in 0..<1000 {\n                _ = Color(hex: "FF0000")\n                _ = Color(hex: "00FF00")\n                _ = Color(hex: "0000FF")\n            }\n        }\n    }\n    \n    func testStationNormalizationPerformance() {\n        let stations = ["Washington Station", "Washington Union", "WASHI", "Unknown Station"]\n        \n        measure {\n            for _ in 0..<1000 {\n                for station in stations {\n                    _ = StationNameNormalizer.normalizedName(for: station)\n                }\n            }\n        }\n    }\n    \n    func testDateFormatterPerformance() {\n        let date = Date()\n        \n        measure {\n            for _ in 0..<100 {\n                let formatter = DateFormatter.easternTime(date: .short, time: .short)\n                _ = formatter.string(from: date)\n            }\n        }\n    }\n}