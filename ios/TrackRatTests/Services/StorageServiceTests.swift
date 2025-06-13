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
        UserDefaults.standard.removeObject(forKey: "trackrat.recentDepartures")
        UserDefaults.standard.removeObject(forKey: "trackrat.recentDestinations")
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
}