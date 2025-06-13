import XCTest
@testable import TrackRat

class StationsTests: XCTestCase {
    
    func testStationsDataExists() {
        XCTAssertFalse(Stations.all.isEmpty, "All stations list should not be empty")
        XCTAssertTrue(Stations.all.count > 0, "Should have at least one station")
    }
    
    func testDepartureStationsExist() {
        XCTAssertFalse(Stations.departureStations.isEmpty, "Departure stations should not be empty")
        XCTAssertTrue(Stations.departureStations.count >= 5, "Should have at least 5 departure stations")
    }
    
    func testKnownStations() {
        // Test that key stations are present
        let stationNames = Stations.all
        
        XCTAssertTrue(stationNames.contains("New York Penn Station"), "Should include NY Penn")
        XCTAssertTrue(stationNames.contains("Newark Penn Station"), "Should include Newark Penn")
        XCTAssertTrue(stationNames.contains("Trenton"), "Should include Trenton")
        XCTAssertTrue(stationNames.contains("Princeton Junction"), "Should include Princeton Junction")
        XCTAssertTrue(stationNames.contains("Metropark"), "Should include Metropark")
    }
    
    func testStationCodes() {
        // Test that stations have proper codes
        let stationCodes = Stations.stationCodes
        
        XCTAssertTrue(stationCodes.keys.contains("New York Penn Station"), "Should include NY Penn")
        XCTAssertTrue(stationCodes.keys.contains("Newark Penn Station"), "Should include Newark Penn")
        XCTAssertEqual(stationCodes["New York Penn Station"], "NY", "NY Penn should have code NY")
        XCTAssertEqual(stationCodes["Newark Penn Station"], "NP", "Newark Penn should have code NP")
    }
    
    func testStationSearch() {
        // Test search functionality if it exists
        let results = Stations.search("New York")
        XCTAssertTrue(results.count > 0, "Search for 'New York' should return results")
        
        let nyResults = results.filter { $0.contains("New York") }
        XCTAssertTrue(nyResults.count > 0, "Should find New York stations")
    }
}