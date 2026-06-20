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

    func testRemoveFavoriteStation_injectedOnly_doesNotAdd() {
        // Removing a station that only exists via home/work injection (not in UserDefaults)
        // must NOT add it to UserDefaults. This was the toggle-direction bug.
        print("--- testRemoveFavoriteStation_injectedOnly_doesNotAdd ---")

        RatSenseService.shared.setHomeStation("NY")
        print("  Home set to NY (not explicitly favorited)")

        // Verify NY appears in display list via injection
        var favorites = storageService.loadFavoriteStations()
        XCTAssertTrue(favorites.contains { $0.id == "NY" }, "NY should be in display list via injection")

        // Now clear home and call removeFavoriteStation
        RatSenseService.shared.setHomeStation(nil)
        storageService.removeFavoriteStation(code: "NY")

        favorites = storageService.loadFavoriteStations()
        print("  After clearing home + remove: \(favorites.map(\.id))")
        XCTAssertFalse(favorites.contains { $0.id == "NY" },
                       "NY should NOT be in favorites — remove must not add an injected-only station")
        XCTAssertFalse(storageService.isStationFavorited(code: "NY"),
                       "NY should not report as favorited")
    }

    func testRemoveFavoriteStation_explicitlyAdded_removes() {
        // Removing a station that was explicitly added should remove it
        print("--- testRemoveFavoriteStation_explicitlyAdded_removes ---")

        storageService.toggleFavoriteStation(code: "TR", name: "Trenton")
        XCTAssertTrue(storageService.isStationFavorited(code: "TR"), "TR should be favorited")

        storageService.removeFavoriteStation(code: "TR")
        XCTAssertFalse(storageService.isStationFavorited(code: "TR"),
                       "TR should be removed after explicit remove")
    }

    func testRemoveFavoriteStation_notPresent_noOp() {
        // Removing a station that doesn't exist at all should be a safe no-op
        print("--- testRemoveFavoriteStation_notPresent_noOp ---")

        storageService.removeFavoriteStation(code: "NONEXISTENT")
        let favorites = storageService.loadFavoriteStations()
        print("  After removing nonexistent: \(favorites.map(\.id))")
        XCTAssertTrue(favorites.isEmpty, "Should have no favorites after removing nonexistent station")
    }

    func testLoadFavoriteStations_orderingHomeFirstWorkSecondThenAlphabetical() {
        // The list shown for picking a departure/arrival station should always
        // surface home first, work second, then the rest sorted alphabetically
        // by display name. See issue #1195.
        print("--- testLoadFavoriteStations_orderingHomeFirstWorkSecondThenAlphabetical ---")

        // Add favorites in non-alphabetical order so insertion order can't
        // accidentally satisfy the assertion.
        storageService.toggleFavoriteStation(code: "TR", name: "Trenton")
        storageService.toggleFavoriteStation(code: "WS", name: "Washington Union Station")
        storageService.toggleFavoriteStation(code: "HB", name: "Hoboken")
        storageService.toggleFavoriteStation(code: "PJ", name: "Princeton Junction")

        // Designate home (BL = Baltimore) and work (NY = New York Penn).
        // Neither is an explicit favorite — they must be injected and
        // appear in the home/work slots even so.
        RatSenseService.shared.setHomeStation("BL")
        RatSenseService.shared.setWorkStation("NY")

        let ordered = storageService.loadFavoriteStations()
        let codes = ordered.map(\.id)
        print("  ordered codes: \(codes)")

        XCTAssertEqual(codes.first, "BL", "Home (BL) must be first")
        XCTAssertEqual(codes.dropFirst().first, "NY", "Work (NY) must be second")

        // Tail = explicit favorites that aren't home/work, alphabetical by display name.
        let tail = Array(codes.dropFirst(2))
        let tailNames = tail.map { Stations.displayName(for: $0) }
        let sortedTailNames = tailNames.sorted {
            $0.localizedCaseInsensitiveCompare($1) == .orderedAscending
        }
        XCTAssertEqual(tailNames, sortedTailNames,
                       "Non-home/work favorites must be alphabetical by display name — got: \(tailNames)")

        // Tail must contain exactly the explicit favorites we added (no duplicates).
        XCTAssertEqual(Set(tail), Set(["TR", "WS", "HB", "PJ"]),
                       "Tail must contain the 4 explicit favorites — got: \(tail)")
    }

    func testLoadFavoriteStations_homeAndWorkSameCode_noDuplicate() {
        // Defensive: if a user has somehow set home and work to the same station,
        // it must appear once (in the home slot), not twice.
        print("--- testLoadFavoriteStations_homeAndWorkSameCode_noDuplicate ---")

        RatSenseService.shared.setHomeStation("NY")
        RatSenseService.shared.setWorkStation("NY")
        storageService.toggleFavoriteStation(code: "TR", name: "Trenton")

        let ordered = storageService.loadFavoriteStations()
        let codes = ordered.map(\.id)
        print("  ordered codes: \(codes)")

        XCTAssertEqual(codes.filter { $0 == "NY" }.count, 1,
                       "NY must appear exactly once when home == work — got: \(codes)")
        XCTAssertEqual(codes.first, "NY", "Home/work station must be first")
        XCTAssertEqual(codes.last, "TR", "Other favorite must follow")
    }

    func testLoadFavoriteStations_noHomeOrWork_isAlphabetical() {
        // With no home/work designation, the whole list must be alphabetical.
        print("--- testLoadFavoriteStations_noHomeOrWork_isAlphabetical ---")

        storageService.toggleFavoriteStation(code: "TR", name: "Trenton")
        storageService.toggleFavoriteStation(code: "HB", name: "Hoboken")
        storageService.toggleFavoriteStation(code: "NY", name: "New York Penn Station")
        storageService.toggleFavoriteStation(code: "BL", name: "Baltimore Station")

        let ordered = storageService.loadFavoriteStations()
        let names = ordered.map { Stations.displayName(for: $0.name) }
        let sortedNames = names.sorted {
            $0.localizedCaseInsensitiveCompare($1) == .orderedAscending
        }
        print("  ordered names: \(names)")

        XCTAssertEqual(names, sortedNames,
                       "With no home/work, favorites must be fully alphabetical — got: \(names)")
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