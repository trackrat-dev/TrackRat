import XCTest
@testable import TrackRat

class StorageServiceTests: XCTestCase {
    
    var storageService: StorageService!
    
    override func setUp() {
        super.setUp()
        storageService = StorageService()
        // Clear any existing data for clean tests
        clearTestData()
    }
    
    override func tearDown() {
        // Clean up after tests
        clearTestData()
        storageService = nil
        super.tearDown()
    }
    
    private func clearTestData() {
        // Clear UserDefaults data used by tests
        UserDefaults.standard.removeObject(forKey: "trackrat.recentTrips")
        UserDefaults.standard.removeObject(forKey: "trackrat.favoriteStations")
        RatSenseService.shared.setHomeStation(nil)
        RatSenseService.shared.setWorkStation(nil)
    }
    
    func testStorageServiceInstantiation() {
        let storageService = StorageService()
        XCTAssertNotNil(storageService, "StorageService should be instantiable")
    }
    
    func testSaveAndRetrieveRecentTrips() {
        // Save a trip
        storageService.saveTrip(departureCode: "NY", departureName: "New York Penn Station", 
                               destinationCode: "NP", destinationName: "Newark Penn Station")
        
        // Retrieve trips
        let recentTrips = storageService.loadRecentTrips()
        
        XCTAssertEqual(recentTrips.count, 1, "Should have one recent trip")
        XCTAssertEqual(recentTrips.first?.departureCode, "NY")
        XCTAssertEqual(recentTrips.first?.destinationCode, "NP")
    }
    
    
    func testRecentTripsLimit() {
        // Add more than 10 trips to test the limit
        for i in 1...15 {
            storageService.saveTrip(departureCode: "ST\(i)", departureName: "Station \(i)",
                                   destinationCode: "DE\(i)", destinationName: "Dest \(i)")
        }

        let recentTrips = storageService.loadRecentTrips()
        XCTAssertEqual(recentTrips.count, 10, "Should limit recent trips to 10")
    }

    // MARK: - Favorite Stations

    func testToggleFavoriteStation_addAndRemove() {
        print("--- testToggleFavoriteStation_addAndRemove ---")

        // Toggle ON
        storageService.toggleFavoriteStation(code: "NY", name: "New York Penn Station")
        var favorites = storageService.loadFavoriteStations()
        print("  After toggle ON: \(favorites.map(\.id))")
        XCTAssertTrue(favorites.contains { $0.id == "NY" }, "NY should be in favorites after toggle on")

        // Toggle OFF
        storageService.toggleFavoriteStation(code: "NY", name: "New York Penn Station")
        favorites = storageService.loadFavoriteStations()
        print("  After toggle OFF: \(favorites.map(\.id))")
        XCTAssertFalse(favorites.contains { $0.id == "NY" }, "NY should NOT be in favorites after toggle off")
    }

    func testHomeStationAppearsInLoadedFavorites() {
        print("--- testHomeStationAppearsInLoadedFavorites ---")

        RatSenseService.shared.setHomeStation("NY")
        let favorites = storageService.loadFavoriteStations()
        print("  Favorites after setting home: \(favorites.map(\.id))")
        XCTAssertTrue(favorites.contains { $0.id == "NY" }, "Home station should appear in loaded favorites")
        XCTAssertTrue(storageService.isStationFavorited(code: "NY"), "Home station should report as favorited")
    }

    func testWorkStationAppearsInLoadedFavorites() {
        print("--- testWorkStationAppearsInLoadedFavorites ---")

        RatSenseService.shared.setWorkStation("PH")
        let favorites = storageService.loadFavoriteStations()
        print("  Favorites after setting work: \(favorites.map(\.id))")
        XCTAssertTrue(favorites.contains { $0.id == "PH" }, "Work station should appear in loaded favorites")
        XCTAssertTrue(storageService.isStationFavorited(code: "PH"), "Work station should report as favorited")
    }

    func testHomeStationNotLeakedToUserDefaults() {
        // This is the core bug fix: toggling any station should NOT persist
        // the injected home/work stations into the explicit favorites list.
        print("--- testHomeStationNotLeakedToUserDefaults ---")

        // Set home station
        RatSenseService.shared.setHomeStation("NY")
        print("  Home station set to NY")

        // Toggle a different station (this triggers loadFavoriteStations -> persist)
        storageService.toggleFavoriteStation(code: "TR", name: "Trenton")
        print("  Toggled TR as favorite")

        // Now clear the home station
        RatSenseService.shared.setHomeStation(nil)
        print("  Cleared home station")

        // NY should no longer appear in favorites since it was never explicitly added
        let favorites = storageService.loadFavoriteStations()
        print("  Favorites after clearing home: \(favorites.map(\.id))")
        XCTAssertFalse(favorites.contains { $0.id == "NY" },
                       "Home station should NOT leak into explicit favorites — got: \(favorites.map(\.id))")
        XCTAssertTrue(favorites.contains { $0.id == "TR" },
                      "Explicitly toggled station should remain")
        XCTAssertFalse(storageService.isStationFavorited(code: "NY"),
                       "Cleared home station should not report as favorited")
    }

    func testRemoveHomeDesignation_stationDisappearsFromFavorites() {
        // Simulates the Settings X button flow:
        // 1. Onboarding sets home + adds to favorites
        // 2. User hits X -> clears home -> removes favorite
        // 3. Station should be completely gone
        print("--- testRemoveHomeDesignation_stationDisappearsFromFavorites ---")

        // Simulate onboarding: set home and add as explicit favorite
        RatSenseService.shared.setHomeStation("NY")
        storageService.toggleFavoriteStation(code: "NY", name: "New York Penn Station")
        print("  After onboarding: favorites = \(storageService.loadFavoriteStations().map(\.id))")

        // Simulate Settings X button: clear home then remove favorite
        RatSenseService.shared.setHomeStation(nil)
        storageService.toggleFavoriteStation(code: "NY", name: "New York Penn Station")
        print("  After removal: favorites = \(storageService.loadFavoriteStations().map(\.id))")

        let favorites = storageService.loadFavoriteStations()
        XCTAssertFalse(favorites.contains { $0.id == "NY" },
                       "Station should be completely gone after clearing home + removing favorite")
        XCTAssertFalse(storageService.isStationFavorited(code: "NY"),
                       "Station should not report as favorited")
    }

    func testFavoriteStationsLimit() {
        print("--- testFavoriteStationsLimit ---")

        for i in 1...12 {
            storageService.toggleFavoriteStation(code: "S\(i)", name: "Station \(i)")
        }
        let favorites = storageService.loadFavoriteStations()
        print("  Count after adding 12: \(favorites.count)")
        XCTAssertLessThanOrEqual(favorites.count, 10, "Should cap at 10 explicit favorites")
    }

    func testIsStationFavorited_homeWorkAndExplicit() {
        print("--- testIsStationFavorited_homeWorkAndExplicit ---")

        RatSenseService.shared.setHomeStation("NY")
        RatSenseService.shared.setWorkStation("PH")
        storageService.toggleFavoriteStation(code: "TR", name: "Trenton")

        print("  Home=NY, Work=PH, Explicit=TR")
        XCTAssertTrue(storageService.isStationFavorited(code: "NY"), "Home should be favorited")
        XCTAssertTrue(storageService.isStationFavorited(code: "PH"), "Work should be favorited")
        XCTAssertTrue(storageService.isStationFavorited(code: "TR"), "Explicit favorite should be favorited")
        XCTAssertFalse(storageService.isStationFavorited(code: "AB"), "Random station should not be favorited")
    }
}