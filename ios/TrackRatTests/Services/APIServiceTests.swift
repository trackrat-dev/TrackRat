import XCTest
@testable import TrackRat

class APIServiceTests: XCTestCase {
    
    var apiService: APIService!
    
    override func setUp() {
        super.setUp()
        apiService = APIService.shared
    }
    
    override func tearDown() {
        apiService = nil
        super.tearDown()
    }
    
    func testAPIServiceSingleton() {
        let firstInstance = APIService.shared
        let secondInstance = APIService.shared
        
        XCTAssertTrue(firstInstance === secondInstance, "APIService should be a singleton")
    }
    
    func testDateDecodingFromISO8601() {
        // Test the date decoding functionality
        let testDateString = "2024-01-01T10:00:00"
        let decodedDate = Date.fromISO8601(testDateString)
        
        XCTAssertNotNil(decodedDate, "Should be able to decode ISO8601 date string")
        
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        let expectedDate = formatter.date(from: testDateString)
        
        XCTAssertEqual(decodedDate, expectedDate, "Decoded date should match expected date")
    }
    
    func testDateDecodingWithFractionalSeconds() {
        // Test date decoding with fractional seconds
        let testDateString = "2024-01-01T10:00:00.123"
        let decodedDate = Date.fromISO8601(testDateString)
        
        XCTAssertNotNil(decodedDate, "Should be able to decode ISO8601 date string with fractional seconds")
    }
    
    func testTrainJSONDecoding() {
        // Test that we can decode a train from JSON
        let jsonString = TrainTestData.sampleTrainJSON
        
        do {
            let train = try TestHelpers.decodeJSON(Train.self, from: jsonString)
            XCTAssertEqual(train.trainId, "123")
            XCTAssertEqual(train.line, "Northeast Corridor")
            XCTAssertEqual(train.destination, "New York Penn Station")
            XCTAssertEqual(train.track, "1")
            XCTAssertEqual(train.originStationCode, "NP")
        } catch {
            XCTFail("Should be able to decode Train from JSON. Error: \(error)")
        }
    }
}