import XCTest
@testable import TrackRat

class BuildTests: XCTestCase {
    
    func testProjectBuilds() {
        // This test will pass if the project compiles successfully
        XCTAssertTrue(true, "Project builds successfully")
    }
    
    func testCoreModelsCanBeInstantiated() {
        // Test that we can instantiate core models without crashing
        
        // Test Train model creation
        let train = Train(
            id: 1,
            trainId: "123",
            line: "Northeast Corridor",
            destination: "New York Penn Station",
            departureTime: Date(),
            track: "1",
            status: .onTime,
            delayMinutes: nil,
            stops: nil,
            predictionData: nil,
            originStationCode: "NP",
            dataSource: "NJTransit",
            consolidatedId: nil,
            originStation: nil,
            dataSources: nil,
            currentPosition: nil,
            trackAssignment: nil,
            statusSummary: nil,
            consolidationMetadata: nil,
            statusV2: nil,
            progress: nil
        )
        
        XCTAssertNotNil(train)
        XCTAssertEqual(train.trainId, "123")
        XCTAssertEqual(train.line, "Northeast Corridor")
        XCTAssertEqual(train.destination, "New York Penn Station")
    }
    
    func testStationsExist() {
        // Test that Stations static data is available
        XCTAssertFalse(Stations.all.isEmpty, "Stations data should not be empty")
        XCTAssertTrue(Stations.departureStations.count > 0, "Should have departure stations")
    }
    
    func testAPIServiceExists() {
        // Test that APIService can be instantiated
        let apiService = APIService.shared
        XCTAssertNotNil(apiService)
    }
    
    func testStorageServiceExists() {
        // Test that StorageService can be instantiated
        let storageService = StorageService()
        XCTAssertNotNil(storageService)
    }
    
    func testLiveActivityServiceExists() {
        // Test that LiveActivityService can be instantiated
        let liveActivityService = LiveActivityService.shared
        XCTAssertNotNil(liveActivityService)
    }
}