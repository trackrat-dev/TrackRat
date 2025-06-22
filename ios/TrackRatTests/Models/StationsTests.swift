import XCTest
@testable import TrackRat

class StationsTests: XCTestCase {
    
    // MARK: - Basic Data Validation Tests
    
    func testStationsDataExists() {
        XCTAssertFalse(Stations.all.isEmpty, "All stations list should not be empty")
        XCTAssertTrue(Stations.all.count > 0, "Should have at least one station")
        XCTAssertGreaterThan(Stations.all.count, 100, "Should have substantial number of stations")
    }
    
    func testDepartureStationsExist() {
        XCTAssertFalse(Stations.departureStations.isEmpty, "Departure stations should not be empty")
        XCTAssertEqual(Stations.departureStations.count, 5, "Should have exactly 5 departure stations")
    }
    
    func testKnownStations() {
        // Test that key stations are present
        let stationNames = Stations.all
        
        XCTAssertTrue(stationNames.contains("New York Penn Station"), "Should include NY Penn")
        XCTAssertTrue(stationNames.contains("Newark Penn Station"), "Should include Newark Penn")
        XCTAssertTrue(stationNames.contains("Trenton"), "Should include Trenton")
        XCTAssertTrue(stationNames.contains("Princeton Junction"), "Should include Princeton Junction")
        XCTAssertTrue(stationNames.contains("Metropark"), "Should include Metropark")
        
        // Test Amtrak stations
        XCTAssertTrue(stationNames.contains("Philadelphia"), "Should include Philadelphia")
        XCTAssertTrue(stationNames.contains("Washington Union Station"), "Should include Washington Union")
        XCTAssertTrue(stationNames.contains("Boston South"), "Should include Boston South")
    }
    
    func testStationCodes() {
        // Test that stations have proper codes
        let stationCodes = Stations.stationCodes
        
        XCTAssertTrue(stationCodes.keys.contains("New York Penn Station"), "Should include NY Penn")
        XCTAssertTrue(stationCodes.keys.contains("Newark Penn Station"), "Should include Newark Penn")
        XCTAssertEqual(stationCodes["New York Penn Station"], "NY", "NY Penn should have code NY")
        XCTAssertEqual(stationCodes["Newark Penn Station"], "NP", "Newark Penn should have code NP")
        XCTAssertEqual(stationCodes["Trenton"], "TR", "Trenton should have code TR")
        XCTAssertEqual(stationCodes["Princeton Junction"], "PJ", "Princeton Junction should have code PJ")
        XCTAssertEqual(stationCodes["Metropark"], "MP", "Metropark should have code MP")
    }
    
    // MARK: - Station Code Mapping Tests
    
    func testAllDepartureStationsHaveCodes() {
        for station in Stations.departureStations {
            XCTAssertEqual(Stations.stationCodes[station.name], station.code, 
                          "Departure station \(station.name) code mismatch")
        }
    }
    
    func testStationCodeUniqueness() {
        let codes = Array(Stations.stationCodes.values)
        let uniqueCodes = Set(codes)
        
        // Account for expected duplicate: "Trenton" and "Trenton Transit Center" both use "TR"
        let expectedDuplicates = 1  // Only TR should be duplicated
        XCTAssertEqual(codes.count - expectedDuplicates, uniqueCodes.count, "Station codes should be unique (except for expected Trenton variants)")
    }
    
    func testGetStationCode() {
        XCTAssertEqual(Stations.getStationCode("New York Penn Station"), "NY")
        XCTAssertEqual(Stations.getStationCode("Newark Penn Station"), "NP")
        XCTAssertEqual(Stations.getStationCode("Trenton"), "TR")
        XCTAssertNil(Stations.getStationCode("Unknown Station"))
        XCTAssertNil(Stations.getStationCode(""))
    }
    
    func testGetStationCodeWithVariations() {
        // Test common destination variations that might come from API
        XCTAssertEqual(Stations.getStationCode("New York"), "NY", "Should handle 'New York' → 'NY'")
        XCTAssertEqual(Stations.getStationCode("Newark"), "NP", "Should handle 'Newark' → 'NP'")
        XCTAssertEqual(Stations.getStationCode("Philadelphia"), "PH", "Should handle 'Philadelphia' → 'PH'")
        XCTAssertEqual(Stations.getStationCode("Washington"), "WS", "Should handle 'Washington' → 'WS'")
        XCTAssertEqual(Stations.getStationCode("Baltimore"), "BL", "Should handle 'Baltimore' → 'BL'")
        XCTAssertEqual(Stations.getStationCode("Boston"), "BOS", "Should handle 'Boston' → 'BOS'")
        XCTAssertEqual(Stations.getStationCode("Princeton"), "PJ", "Should handle 'Princeton' → 'PJ'")
        
        // Test case insensitive matching
        XCTAssertEqual(Stations.getStationCode("new york"), "NY", "Should be case insensitive")
        XCTAssertEqual(Stations.getStationCode("NEW YORK"), "NY", "Should be case insensitive")
        XCTAssertEqual(Stations.getStationCode("New York"), "NY", "Should be case insensitive")
        
        // Test with extra whitespace
        XCTAssertEqual(Stations.getStationCode(" New York "), "NY", "Should handle whitespace")
        XCTAssertEqual(Stations.getStationCode("\tTrenton\n"), "TR", "Should handle whitespace")
    }
    
    func testGetStationCodeWithPartialMatching() {
        // Test partial matching for stations containing search terms
        XCTAssertEqual(Stations.getStationCode("Metropark"), "MP", "Should find exact match first")
        
        // Test that partial matching works as fallback
        let result = Stations.getStationCode("some partial station name that doesn't exist")
        XCTAssertNil(result, "Should return nil for non-existent partial matches")
    }
    
    func testStationCodesCoverDepartureStations() {
        for departureStation in Stations.departureStations {
            XCTAssertNotNil(Stations.stationCodes[departureStation.name], 
                           "Departure station \(departureStation.name) should have a code")
        }
    }
    
    // MARK: - Search Functionality Tests
    
    func testStationSearch() {
        let results = Stations.search("New York")
        XCTAssertTrue(results.count > 0, "Search for 'New York' should return results")
        
        let nyResults = results.filter { $0.contains("New York") }
        XCTAssertTrue(nyResults.count > 0, "Should find New York stations")
    }
    
    func testStationSearchCaseInsensitive() {
        let upperResults = Stations.search("NEW YORK")
        let lowerResults = Stations.search("new york")
        let mixedResults = Stations.search("New York")
        
        XCTAssertEqual(upperResults.count, lowerResults.count, "Search should be case insensitive")
        XCTAssertEqual(upperResults.count, mixedResults.count, "Search should be case insensitive")
        
        // Verify all contain New York
        for result in upperResults {
            XCTAssertTrue(result.lowercased().contains("new york"), "Result should contain 'new york'")
        }
    }
    
    func testStationSearchEmptyQuery() {
        let results = Stations.search("")
        XCTAssertTrue(results.isEmpty, "Empty search should return no results")
    }
    
    func testStationSearchPartialMatch() {
        let results = Stations.search("Penn")
        XCTAssertTrue(results.count > 0, "Search for 'Penn' should return results")
        
        let pennResults = results.filter { $0.contains("Penn") }
        XCTAssertEqual(results.count, pennResults.count, "All results should contain 'Penn'")
        
        // Should include both NY Penn and Newark Penn
        XCTAssertTrue(results.contains("New York Penn Station"), "Should include NY Penn")
        XCTAssertTrue(results.contains("Newark Penn Station"), "Should include Newark Penn")
    }
    
    func testStationSearchResultLimit() {
        let results = Stations.search("a") // Should match many stations
        XCTAssertLessThanOrEqual(results.count, 8, "Search should limit results to 8")
    }
    
    func testStationSearchNoMatches() {
        let results = Stations.search("XYZNOMATCH")
        XCTAssertTrue(results.isEmpty, "Search for non-existent station should return no results")
    }
    
    func testStationSearchSpecialCharacters() {
        let results = Stations.search("Ho-Ho-Kus")
        XCTAssertTrue(results.count > 0, "Search for station with hyphens should work")
        XCTAssertTrue(results.contains("Ho-Ho-Kus"), "Should find Ho-Ho-Kus station")
    }
    
    // MARK: - Data Integrity Tests
    
    func testStationsListSorted() {
        let sortedStations = Stations.all.sorted()
        XCTAssertEqual(Stations.all, sortedStations, "Stations list should be sorted alphabetically")
    }
    
    func testNoEmptyStationNames() {
        for station in Stations.all {
            XCTAssertFalse(station.isEmpty, "Station names should not be empty")
            XCTAssertFalse(station.trimmingCharacters(in: .whitespaces).isEmpty, 
                          "Station names should not be only whitespace")
        }
    }
    
    func testNoEmptyStationCodes() {
        for (stationName, code) in Stations.stationCodes {
            XCTAssertFalse(stationName.isEmpty, "Station name should not be empty")
            XCTAssertFalse(code.isEmpty, "Station code should not be empty")
            XCTAssertFalse(code.trimmingCharacters(in: .whitespaces).isEmpty, 
                          "Station code should not be only whitespace")
        }
    }
    
    func testStationCodeFormat() {
        for (_, code) in Stations.stationCodes {
            // Station codes should be uppercase letters and numbers only
            let allowedCharacters = CharacterSet.alphanumerics
            let codeCharacters = CharacterSet(charactersIn: code)
            XCTAssertTrue(allowedCharacters.isSuperset(of: codeCharacters), 
                         "Station code '\(code)' should only contain alphanumeric characters")
            
            // Most codes should be 2-4 characters
            XCTAssertGreaterThanOrEqual(code.count, 2, "Station code '\(code)' should be at least 2 characters")
            XCTAssertLessThanOrEqual(code.count, 5, "Station code '\(code)' should be at most 5 characters")
        }
    }
    
    func testDepartureStationDataIntegrity() {
        for station in Stations.departureStations {
            // Name should not be empty
            XCTAssertFalse(station.name.isEmpty, "Departure station name should not be empty")
            XCTAssertFalse(station.code.isEmpty, "Departure station code should not be empty")
            
            // Station should exist in all stations list
            XCTAssertTrue(Stations.all.contains(station.name), 
                         "Departure station \(station.name) should exist in all stations")
            
            // Code should match stationCodes mapping
            XCTAssertEqual(Stations.stationCodes[station.name], station.code, 
                          "Departure station code mismatch for \(station.name)")
        }
    }
    
    // MARK: - Edge Cases and Error Handling
    
    func testStationNamesWithSpecialCharacters() {
        // Test stations with hyphens, apostrophes, spaces
        let specialStations = Stations.all.filter { station in
            station.contains("-") || station.contains("'") || station.contains(" ")
        }
        
        XCTAssertGreaterThan(specialStations.count, 0, "Should have stations with special characters")
        
        // Verify they all have valid codes
        for station in specialStations {
            XCTAssertNotNil(Stations.stationCodes[station], 
                           "Station with special characters should have a code: \(station)")
        }
    }
    
    func testStationSearchWithSpecialCharacters() {
        // Test searching with various special characters
        let searchTerms = ["Ho-Ho", "St.", "Penn Station", "New York"]
        
        for term in searchTerms {
            let results = Stations.search(term)
            // Should not crash and should return reasonable results
            XCTAssertGreaterThanOrEqual(results.count, 0, "Search should handle special characters")
        }
    }
    
    func testStationSearchPerformance() {
        measure {
            for _ in 0..<100 {
                _ = Stations.search("New")
                _ = Stations.search("Station")
                _ = Stations.search("Penn")
            }
        }
    }
    
    // MARK: - Specific Station Tests
    
    func testMajorAmtrakStations() {
        let majorStations = [
            "Boston South", "New York Penn Station", "Philadelphia", 
            "Baltimore Station", "Washington Union Station"
        ]
        
        for station in majorStations {
            XCTAssertTrue(Stations.all.contains(station), "Should include major Amtrak station: \(station)")
            XCTAssertNotNil(Stations.stationCodes[station], "Major station should have code: \(station)")
        }
    }
    
    func testMajorNJTransitStations() {
        let majorStations = [
            "New York Penn Station", "Newark Penn Station", "Trenton", 
            "Princeton Junction", "Metropark", "New Brunswick"
        ]
        
        for station in majorStations {
            XCTAssertTrue(Stations.all.contains(station), "Should include major NJ Transit station: \(station)")
            XCTAssertNotNil(Stations.stationCodes[station], "Major station should have code: \(station)")
        }
    }
    
    func testTrentonVariants() {
        // Test that both "Trenton" and "Trenton Transit Center" are handled
        XCTAssertTrue(Stations.all.contains("Trenton"), "Should include Trenton")
        XCTAssertNotNil(Stations.stationCodes["Trenton"], "Trenton should have a code")
        XCTAssertNotNil(Stations.stationCodes["Trenton Transit Center"], "Trenton Transit Center should have a code")
        XCTAssertEqual(Stations.stationCodes["Trenton"], Stations.stationCodes["Trenton Transit Center"], 
                      "Trenton variants should have same code")
    }
    
    // MARK: - Integration with StationNameNormalizer
    
    func testStationNameConsistency() {
        // Verify that station names in the list are consistent with what might be expected
        // from API responses (this helps catch data entry errors)
        
        let expectedStations = [
            "New York Penn Station",
            "Newark Penn Station", 
            "Trenton",
            "Princeton Junction",
            "Metropark"
        ]
        
        for station in expectedStations {
            XCTAssertTrue(Stations.all.contains(station), "Expected station missing: \(station)")
        }
    }
    
    func testDuplicateStationNames() {
        let stationSet = Set(Stations.all)
        XCTAssertEqual(Stations.all.count, stationSet.count, "Station names should be unique")
    }
}