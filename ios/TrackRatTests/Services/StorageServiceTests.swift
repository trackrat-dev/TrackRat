import XCTest
@testable import TrackRat

class StorageServiceTests: XCTestCase {
    
    var storageService: StorageService!
    var testUserDefaults: UserDefaults!
    private let testSuiteName = "com.trackrat.test.storageservice"
    
    override func setUp() {
        super.setUp()
        testUserDefaults = UserDefaults(suiteName: testSuiteName)!
        storageService = StorageService(userDefaults: testUserDefaults)
        // No need to call clearTestData() here as tearDown will handle it for the *next* test.
    }
    
    override func tearDown() {
        // Clean up after tests
        testUserDefaults.removePersistentDomain(forName: testSuiteName)
        testUserDefaults = nil
        storageService = nil
        super.tearDown()
    }
    
    // clearTestData() is removed as its functionality is now in tearDown for better per-test isolation.
    
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
    
    func testSaveAndRetrieveRecentDepartures() {
        // Save a departure
        storageService.saveDeparture(code: "NY", name: "New York Penn Station")
        
        // Retrieve departures
        let recentDepartures = storageService.loadRecentDepartures()
        
        XCTAssertEqual(recentDepartures.count, 1, "Should have one recent departure")
        XCTAssertEqual(recentDepartures.first?.code, "NY")
        XCTAssertEqual(recentDepartures.first?.name, "New York Penn Station")
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
    
    func testRecentDeparturesLimit() {
        // Add more than 5 departures to test the limit
        for i in 1...8 {
            storageService.saveDeparture(code: "ST\(i)", name: "Station \(i)")
        }
        
        let recentDepartures = storageService.loadRecentDepartures()
        XCTAssertEqual(recentDepartures.count, 5, "Should limit recent departures to 5")
    }
    
    func testDestinationOperations() {
        // Test destination functionality
        storageService.saveDestination("New York Penn Station")
        
        let destinations = storageService.loadRecentDestinations()
        XCTAssertEqual(destinations.count, 1, "Should have one destination")
        XCTAssertEqual(destinations.first, "New York Penn Station")
    }

    // MARK: - TripPair Management Tests

    func testSaveTrip_AddsNewTrip() {
        let initialTime = Date()
        storageService.saveTrip(departureCode: "PHL", departureName: "Philadelphia",
                               destinationCode: "BAL", destinationName: "Baltimore")
        let trips = storageService.loadRecentTrips()

        XCTAssertEqual(trips.count, 1)
        let trip = trips.first!
        XCTAssertEqual(trip.departureCode, "PHL")
        XCTAssertEqual(trip.destinationCode, "BAL")
        XCTAssertFalse(trip.isFavorite)
        XCTAssertTrue(trip.lastUsed >= initialTime, "lastUsed should be recent")
    }

    func testSaveTrip_UpdatesExistingTrip_MovesToFrontAndUpdatesLastUsed() {
        // Save trip A
        storageService.saveTrip(departureCode: "DC", departureName: "Washington DC",
                               destinationCode: "BOS", destinationName: "Boston")
        let timeAfterFirstSave = Date()

        // Wait a bit to ensure time difference
        Thread.sleep(forTimeInterval: 0.05)

        // Save trip B
        storageService.saveTrip(departureCode: "NYP", departureName: "New York",
                               destinationCode: "PHL", destinationName: "Philadelphia")
        let tripB_lastUsed = storageService.loadRecentTrips().first(where: { $0.departureCode == "NYP" })?.lastUsed

        XCTAssertNotNil(tripB_lastUsed, "Trip B should exist and have a lastUsed date")

        // Wait a bit more
        Thread.sleep(forTimeInterval: 0.05)
        let timeBeforeSecondSaveOfA = Date()

        // Save trip A again
        storageService.saveTrip(departureCode: "DC", departureName: "Washington DC",
                               destinationCode: "BOS", destinationName: "Boston")

        let trips = storageService.loadRecentTrips()
        XCTAssertEqual(trips.count, 2, "Should still have 2 trips")

        let tripA = trips.first! // Trip A should now be at the front
        XCTAssertEqual(tripA.departureCode, "DC", "Trip A should be first")
        XCTAssertFalse(tripA.isFavorite, "Re-saving a trip currently makes it non-favorite")
        XCTAssertTrue(tripA.lastUsed > timeAfterFirstSave, "Trip A's lastUsed should be updated.")
        XCTAssertTrue(tripA.lastUsed >= timeBeforeSecondSaveOfA, "Trip A's lastUsed should be very recent.")

        if let tripB_lastUsed = tripB_lastUsed { // Ensure tripB_lastUsed is not nil
             XCTAssertTrue(tripA.lastUsed > tripB_lastUsed, "Trip A should be more recent than Trip B")
        }
    }

    func testSaveTrip_Limit() {
        let maxRecentTrips = 10 // Private constant in StorageService
        for i in 0..<maxRecentTrips + 1 { // Save 11 trips
            storageService.saveTrip(departureCode: "D\(i)", departureName: "Dep\(i)",
                                   destinationCode: "A\(i)", destinationName: "Arr\(i)")
        }
        let trips = storageService.loadRecentTrips()
        XCTAssertEqual(trips.count, maxRecentTrips)
        // The first trip saved (D0, A0) should be gone.
        // The latest trip saved (D10, A10) should be at the front.
        XCTAssertEqual(trips.first?.departureCode, "D\(maxRecentTrips)")
        XCTAssertFalse(trips.contains(where: { $0.departureCode == "D0" }))
    }

    func testToggleFavorite_NewTrip_AddsAsFavorite() {
        let newTrip = TripPair(departureCode: "NEW", departureName: "New Haven",
                               destinationCode: "SPR", destinationName: "Springfield")

        storageService.toggleFavorite(for: newTrip)
        let trips = storageService.loadRecentTrips()

        XCTAssertEqual(trips.count, 1)
        let favoritedTrip = trips.first!
        XCTAssertEqual(favoritedTrip.id, newTrip.id)
        XCTAssertTrue(favoritedTrip.isFavorite)
        XCTAssertTrue(favoritedTrip.lastUsed >= newTrip.lastUsed) // lastUsed should be set/updated
    }

    func testToggleFavorite_ExistingNonFavorite_BecomesFavorite() {
        storageService.saveTrip(departureCode: "TRE", departureName: "Trenton",
                               destinationCode: "MET", destinationName: "Metropark")
        var trip = storageService.loadRecentTrips().first!
        XCTAssertFalse(trip.isFavorite)
        let initialLastUsed = trip.lastUsed

        Thread.sleep(forTimeInterval: 0.01) // Ensure lastUsed can change
        storageService.toggleFavorite(for: trip)

        trip = storageService.loadRecentTrips().first!
        XCTAssertTrue(trip.isFavorite)
        XCTAssertTrue(trip.lastUsed > initialLastUsed, "lastUsed should be updated on toggle")
    }

    func testToggleFavorite_ExistingFavorite_BecomesNonFavorite() {
        // Add as favorite initially
        var trip = TripPair(departureCode: "BAL", departureName: "Baltimore",
                            destinationCode: "WAS", destinationName: "Washington DC")
        storageService.toggleFavorite(for: trip) // Becomes favorite

        trip = storageService.loadRecentTrips().first!
        XCTAssertTrue(trip.isFavorite)
        let initialLastUsed = trip.lastUsed

        Thread.sleep(forTimeInterval: 0.01) // Ensure lastUsed can change
        storageService.toggleFavorite(for: trip) // Toggle again

        trip = storageService.loadRecentTrips().first!
        XCTAssertFalse(trip.isFavorite)
        XCTAssertTrue(trip.lastUsed > initialLastUsed, "lastUsed should be updated on toggle")
    }

    func testLoadFavoriteTrips() {
        // Save 3 trips, favorite 2 of them
        let trip1 = TripPair(departureCode: "A", departureName: "A", destinationCode: "B", destinationName: "B")
        let trip2 = TripPair(departureCode: "C", departureName: "C", destinationCode: "D", destinationName: "D")
        let trip3 = TripPair(departureCode: "E", departureName: "E", destinationCode: "F", destinationName: "F")

        storageService.toggleFavorite(for: trip1) // Favorite
        storageService.saveTrip(departureCode: trip2.departureCode, departureName: trip2.departureName, destinationCode: trip2.destinationCode, destinationName: trip2.destinationName) // Not favorite
        storageService.toggleFavorite(for: trip3) // Favorite

        let favoriteTrips = storageService.loadFavoriteTrips()
        XCTAssertEqual(favoriteTrips.count, 2)
        XCTAssertTrue(favoriteTrips.allSatisfy { $0.isFavorite })
        XCTAssertTrue(favoriteTrips.contains(where: { $0.id == trip1.id }))
        XCTAssertTrue(favoriteTrips.contains(where: { $0.id == trip3.id }))
        XCTAssertFalse(favoriteTrips.contains(where: { $0.id == trip2.id }))
    }

    func testLoadFavoriteTrips_NoFavorites() {
        storageService.saveTrip(departureCode: "G", departureName: "G", destinationCode: "H", destinationName: "H") // Not favorite
        let favoriteTrips = storageService.loadFavoriteTrips()
        XCTAssertTrue(favoriteTrips.isEmpty, "Should return an empty array if no trips are favorited")
    }

    func testRemoveTrip_ExistingTrip() {
        let tripA = TripPair(departureCode: "A", departureName: "A", destinationCode: "B", destinationName: "B")
        let tripB = TripPair(departureCode: "C", departureName: "C", destinationCode: "D", destinationName: "D")
        storageService.saveTrip(departureCode: tripA.departureCode, departureName: tripA.departureName, destinationCode: tripA.destinationCode, destinationName: tripA.destinationName)
        storageService.saveTrip(departureCode: tripB.departureCode, departureName: tripB.departureName, destinationCode: tripB.destinationCode, destinationName: tripB.destinationName)

        XCTAssertEqual(storageService.loadRecentTrips().count, 2)
        storageService.removeTrip(tripA)

        let remainingTrips = storageService.loadRecentTrips()
        XCTAssertEqual(remainingTrips.count, 1)
        XCTAssertEqual(remainingTrips.first?.id, tripB.id)
    }

    func testRemoveTrip_NonExistentTrip() {
        let tripA = TripPair(departureCode: "A", departureName: "A", destinationCode: "B", destinationName: "B")
        let nonExistentTrip = TripPair(departureCode: "X", departureName: "X", destinationCode: "Y", destinationName: "Y")
        storageService.saveTrip(departureCode: tripA.departureCode, departureName: tripA.departureName, destinationCode: tripA.destinationCode, destinationName: tripA.destinationName)

        XCTAssertEqual(storageService.loadRecentTrips().count, 1)
        storageService.removeTrip(nonExistentTrip) // Attempt to remove a trip not in storage

        let remainingTrips = storageService.loadRecentTrips()
        XCTAssertEqual(remainingTrips.count, 1)
        XCTAssertEqual(remainingTrips.first?.id, tripA.id)
    }

    func testClearRecentTrips() {
        storageService.saveTrip(departureCode: "A", departureName: "A", destinationCode: "B", destinationName: "B")
        storageService.saveTrip(departureCode: "C", departureName: "C", destinationCode: "D", destinationName: "D")
        XCTAssertFalse(storageService.loadRecentTrips().isEmpty)

        storageService.clearRecentTrips()
        XCTAssertTrue(storageService.loadRecentTrips().isEmpty)
    }

    // MARK: - RecentDeparture Management Tests

    func testSaveDeparture_AddsNewDeparture() {
        storageService.saveDeparture(code: "PHL", name: "Philadelphia")
        let departures = storageService.loadRecentDepartures()

        XCTAssertEqual(departures.count, 1)
        XCTAssertEqual(departures.first?.code, "PHL")
        XCTAssertEqual(departures.first?.name, "Philadelphia")
    }

    func testSaveDeparture_ReAddingExisting_MovesToFront() {
        storageService.saveDeparture(code: "DC", name: "Washington DC") // A
        storageService.saveDeparture(code: "NYP", name: "New York")    // B
        storageService.saveDeparture(code: "DC", name: "Washington DC") // A again

        let departures = storageService.loadRecentDepartures()
        XCTAssertEqual(departures.count, 2, "Should have 2 unique departures")
        XCTAssertEqual(departures.first?.code, "DC", "DC should now be at the front")
        XCTAssertEqual(departures.last?.code, "NYP")
    }

    // testRecentDeparturesLimit() already exists and covers the count.
    // Let's enhance it to check *which* items are kept.
    func testRecentDeparturesLimit_EnsuresLatestAreKept() {
        let maxRecentDepartures = 5 // Private constant in StorageService
        // Save 8 departures
        for i in 0..<maxRecentDepartures + 3 {
             storageService.saveDeparture(code: "ST\(i)", name: "Station \(i)")
        }

        let recentDepartures = storageService.loadRecentDepartures()
        XCTAssertEqual(recentDepartures.count, maxRecentDepartures, "Should limit recent departures to \(maxRecentDepartures)")

        // Check that the latest 5 are kept. ST0, ST1, ST2 should be gone.
        // ST7 should be first, ST3 should be last among the 5.
        XCTAssertEqual(recentDepartures.first?.code, "ST\(maxRecentDepartures + 2)") // ST7
        XCTAssertEqual(recentDepartures.last?.code, "ST3")
        XCTAssertFalse(recentDepartures.contains(where: { $0.code == "ST0"}))
        XCTAssertFalse(recentDepartures.contains(where: { $0.code == "ST1"}))
        XCTAssertFalse(recentDepartures.contains(where: { $0.code == "ST2"}))
    }


    // MARK: - Legacy RecentDestination Management Tests

    func testSaveDestination_AddsNewDestination() {
        // This is similar to existing testDestinationOperations, make it more specific
        storageService.saveDestination("Philadelphia")
        let destinations = storageService.loadRecentDestinations()

        XCTAssertEqual(destinations.count, 1)
        XCTAssertEqual(destinations.first, "Philadelphia")
    }

    func testSaveDestination_ReAddingExisting_MovesToFront() {
        storageService.saveDestination("Washington DC") // A
        storageService.saveDestination("New York")    // B
        storageService.saveDestination("Washington DC") // A again

        let destinations = storageService.loadRecentDestinations()
        XCTAssertEqual(destinations.count, 2, "Should have 2 unique destinations")
        XCTAssertEqual(destinations.first, "Washington DC", "Washington DC should now be at the front")
        XCTAssertEqual(destinations.last, "New York")
    }

    func testSaveDestination_Limit() {
        let maxRecentDestinations = 5 // Private constant in StorageService
        // Save 6 destinations
        for i in 0..<maxRecentDestinations + 1 {
             storageService.saveDestination("Destination \(i)")
        }

        let destinations = storageService.loadRecentDestinations()
        XCTAssertEqual(destinations.count, maxRecentDestinations, "Should limit recent destinations to \(maxRecentDestinations)")

        // Check that the latest 5 are kept. "Destination 0" should be gone.
        // "Destination 5" should be first.
        XCTAssertEqual(destinations.first, "Destination \(maxRecentDestinations)")
        XCTAssertFalse(destinations.contains("Destination 0"))
    }

    func testRemoveDestination_ExistingDestination() {
        storageService.saveDestination("Destination A")
        storageService.saveDestination("Destination B")
        XCTAssertEqual(storageService.loadRecentDestinations().count, 2)

        storageService.removeDestination("Destination A")
        let destinations = storageService.loadRecentDestinations()
        XCTAssertEqual(destinations.count, 1)
        XCTAssertEqual(destinations.first, "Destination B")
    }

    func testRemoveDestination_NonExistentDestination() {
        storageService.saveDestination("Destination A")
        XCTAssertEqual(storageService.loadRecentDestinations().count, 1)

        storageService.removeDestination("NonExistent Destination")
        let destinations = storageService.loadRecentDestinations()
        XCTAssertEqual(destinations.count, 1)
        XCTAssertEqual(destinations.first, "Destination A")
    }

    func testClearRecentDestinations() {
        storageService.saveDestination("Destination A")
        storageService.saveDestination("Destination B")
        XCTAssertFalse(storageService.loadRecentDestinations().isEmpty)

        storageService.clearRecentDestinations()
        XCTAssertTrue(storageService.loadRecentDestinations().isEmpty, "Destinations list should be empty after clear")
    }

    // MARK: - Migration Tests

    func testMigrateRecentDestinations_WithExistingDestinationsAndNoTrips() {
        // Setup: Ensure recentTripsKey is empty (tearDown handles this by default)
        // Save some legacy destinations
        let destName1 = "Newark Penn Station" // Valid
        let destName2 = "Trenton Transit Center" // Valid
        storageService.saveDestination(destName1)
        storageService.saveDestination(destName2)

        // Action
        storageService.migrateRecentDestinations()

        // Assertions
        let trips = storageService.loadRecentTrips()
        XCTAssertEqual(trips.count, 2, "Should create trips for valid legacy destinations")

        let expectedDepartureCode = "NY"
        let expectedDepartureName = Stations.displayName(for: "New York Penn Station")

        let tripForDest1 = trips.first { $0.destinationName == destName1 }
        XCTAssertNotNil(tripForDest1)
        XCTAssertEqual(tripForDest1?.departureCode, expectedDepartureCode)
        XCTAssertEqual(tripForDest1?.departureName, expectedDepartureName)
        XCTAssertEqual(tripForDest1?.destinationCode, Stations.getStationCode(destName1))
        XCTAssertFalse(tripForDest1?.isFavorite ?? true)

        let tripForDest2 = trips.first { $0.destinationName == destName2 }
        XCTAssertNotNil(tripForDest2)
        XCTAssertEqual(tripForDest2?.departureCode, expectedDepartureCode)
        XCTAssertEqual(tripForDest2?.departureName, expectedDepartureName)
        XCTAssertEqual(tripForDest2?.destinationCode, Stations.getStationCode(destName2))
        XCTAssertFalse(tripForDest2?.isFavorite ?? true)

        // Ensure they are ordered with most recent legacy destination first if saveDestination maintains order
        // and migrateRecentDestinations processes them in that order.
        // The test saves destName1, then destName2. So destName2 is "more recent" in legacy.
        // Migration iterates legacy destinations, so trip for destName2 should be first in new trips list.
        XCTAssertEqual(trips.first?.destinationName, destName2)
    }

    func testMigrateRecentDestinations_NoLegacyDestinations() {
        // Setup: recentDestinationsKey and recentTripsKey are empty (tearDown handles this)
        XCTAssertTrue(storageService.loadRecentDestinations().isEmpty)
        XCTAssertTrue(storageService.loadRecentTrips().isEmpty)

        // Action
        storageService.migrateRecentDestinations()

        // Assertions
        XCTAssertTrue(storageService.loadRecentTrips().isEmpty, "No trips should be created")
    }

    func testMigrateRecentDestinations_WithExistingTrips() {
        // Setup
        storageService.saveDestination("Newark Penn Station") // Legacy destination
        storageService.saveTrip(departureCode: "PHL", departureName: "Philadelphia", destinationCode: "BAL", destinationName: "Baltimore") // Existing trip

        // Action
        storageService.migrateRecentDestinations()

        // Assertions
        let trips = storageService.loadRecentTrips()
        XCTAssertEqual(trips.count, 1, "Should not migrate if trips already exist")
        XCTAssertEqual(trips.first?.departureCode, "PHL", "Existing trip should remain unchanged")
    }

    func testMigrateRecentDestinations_WithInvalidLegacyDestinationName() {
        // Setup: recentTripsKey is empty
        let validDestName = "Secaucus Junction"
        let invalidDestName = "Invalid Station Name That Wont Resolve"
        storageService.saveDestination(validDestName)
        storageService.saveDestination(invalidDestName)

        XCTAssertEqual(storageService.loadRecentDestinations().count, 2)

        // Action
        storageService.migrateRecentDestinations()

        // Assertions
        let trips = storageService.loadRecentTrips()
        XCTAssertEqual(trips.count, 1, "Should only create trip for the valid legacy destination")

        let migratedTrip = trips.first
        XCTAssertNotNil(migratedTrip)
        XCTAssertEqual(migratedTrip?.destinationName, validDestName)
        XCTAssertEqual(migratedTrip?.destinationCode, Stations.getStationCode(validDestName))
        XCTAssertEqual(migratedTrip?.departureCode, "NY")
    }
}