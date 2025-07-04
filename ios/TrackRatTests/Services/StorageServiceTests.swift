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
    
    
}