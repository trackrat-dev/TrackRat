import XCTest
@testable import TrackRat

class APIServiceTests: XCTestCase {
    
    var apiService: APIService!
    
    override func setUp() {
        super.setUp()
        // Initialize with MockURLSession for testing
        apiService = APIService(session: MockURLSession())
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

    // MARK: - searchTrains Tests

    func testSearchTrains_Success() async throws {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)

        let expectedResponseData = TrainTestData.trainListResponseJSON.data(using: .utf8)!
        mockSession.mockData = expectedResponseData
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/")!, statusCode: 200, httpVersion: nil, headerFields: nil)

        let fromStationCode = "NLC"
        let toStationCode = "NYP"

        let trains = try await apiService.searchTrains(fromStationCode: fromStationCode, toStationCode: toStationCode)

        XCTAssertNotNil(mockSession.capturedURL, "URL should have been captured")
        let capturedURLString = mockSession.capturedURL?.absoluteString ?? ""
        XCTAssertTrue(capturedURLString.contains("from_station_code=\(fromStationCode)"), "URL should contain from_station_code")
        XCTAssertTrue(capturedURLString.contains("to_station_code=\(toStationCode)"), "URL should contain to_station_code")
        XCTAssertTrue(capturedURLString.contains("limit=100"), "URL should contain limit")
        XCTAssertTrue(capturedURLString.contains("consolidate=true"), "URL should contain consolidate")
        // Note: Testing departure_time_after is tricky due to its dynamic nature.
        // A more robust test might parse the URL components and validate the date separately.
        // For now, we check its presence.
        XCTAssertTrue(capturedURLString.contains("departure_time_after="), "URL should contain departure_time_after")


        XCTAssertEqual(trains.count, 3, "Should return 3 trains based on mock JSON")
        XCTAssertEqual(trains[0].trainId, "123", "First train ID should match mock data")
        XCTAssertEqual(trains[1].trainId, "456", "Second train ID should match mock data")
        XCTAssertEqual(trains[2].trainId, "2150", "Third train ID should match mock data")
    }

    func testSearchTrains_NetworkError() async {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)

        let expectedError = URLError(.notConnectedToInternet)
        mockSession.mockError = expectedError

        do {
            _ = try await apiService.searchTrains(fromStationCode: "NLC", toStationCode: "NYP")
            XCTFail("Should have thrown a network error")
        } catch {
            XCTAssertEqual(error as? URLError, expectedError, "Error should be the expected network error")
        }
    }

    func testSearchTrains_APIError_NotFound() async {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)

        // Simulate a 404 Not Found response
        // The APIService's current implementation might throw a DecodingError if the data is empty
        // or not the expected JSON structure, rather than a specific APIError for 404.
        // This test will verify that behavior. If a specific APIError for 404 is desired,
        // APIService would need to be updated to handle HTTP status codes more directly.
        mockSession.mockData = Data() // Empty data
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/")!, statusCode: 404, httpVersion: nil, headerFields: nil)

        do {
            _ = try await apiService.searchTrains(fromStationCode: "NLC", toStationCode: "NYP")
            XCTFail("Should have thrown an error")
        } catch {
            // Expecting a DecodingError because empty data cannot be decoded into TrainListResponse
            XCTAssertTrue(error is DecodingError, "Error should be a DecodingError for empty data with 404")
        }
    }

    func testSearchTrains_APIError_ServerError() async {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)

        mockSession.mockData = Data() // Empty data, or some error JSON if the API provides it
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/")!, statusCode: 500, httpVersion: nil, headerFields: nil)

        do {
            _ = try await apiService.searchTrains(fromStationCode: "NLC", toStationCode: "NYP")
            XCTFail("Should have thrown an error due to server error status code")
        } catch {
            // Similar to 404, current APIService will likely throw DecodingError with empty data.
            // If the API returned specific error JSON for a 500, that could be tested here too.
            XCTAssertTrue(error is DecodingError, "Error should be a DecodingError for empty data with 500")
        }
    }

    func testSearchTrains_DecodingError() async {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)

        let malformedJSONData = TrainTestData.malformedTrainJSON.data(using: .utf8)!
        mockSession.mockData = malformedJSONData
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/")!, statusCode: 200, httpVersion: nil, headerFields: nil)

        do {
            _ = try await apiService.searchTrains(fromStationCode: "NLC", toStationCode: "NYP")
            XCTFail("Should have thrown a DecodingError")
        } catch {
            XCTAssertTrue(error is DecodingError, "Error should be a DecodingError")
        }
    }

    // MARK: - fetchTrainDetails Tests

    func testFetchTrainDetails_Success_WithFromStationCode() async throws {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)

        let trainId = "123"
        let fromCode = "PJC"
        let expectedResponseData = TrainTestData.legacyTrainJSON.data(using: .utf8)! // Using legacyTrainJSON as it represents a single train

        mockSession.mockData = expectedResponseData
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/\(trainId)?from_station_code=\(fromCode)")!, statusCode: 200, httpVersion: nil, headerFields: nil)

        let train = try await apiService.fetchTrainDetails(id: trainId, fromStationCode: fromCode)

        XCTAssertNotNil(mockSession.capturedURL, "URL should have been captured")
        let capturedURLString = mockSession.capturedURL?.absoluteString ?? ""
        XCTAssertTrue(capturedURLString.contains("/trains/\(trainId)"), "URL path should contain train ID")
        XCTAssertTrue(capturedURLString.contains("from_station_code=\(fromCode)"), "URL should contain from_station_code query parameter")

        XCTAssertEqual(train.trainId, trainId, "Train ID should match")
        XCTAssertEqual(train.line, "Northeast Corridor", "Train line should match mock data")
        // Add more assertions as needed based on TrainTestData.legacyTrainJSON
    }

    func testFetchTrainDetails_Success_WithoutFromStationCode() async throws {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)

        let trainId = "123"
        let expectedResponseData = TrainTestData.legacyTrainJSON.data(using: .utf8)!

        mockSession.mockData = expectedResponseData
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/\(trainId)")!, statusCode: 200, httpVersion: nil, headerFields: nil)

        let train = try await apiService.fetchTrainDetails(id: trainId, fromStationCode: nil)

        XCTAssertNotNil(mockSession.capturedURL, "URL should have been captured")
        let capturedURLString = mockSession.capturedURL?.absoluteString ?? ""
        XCTAssertTrue(capturedURLString.contains("/trains/\(trainId)"), "URL path should contain train ID")
        XCTAssertFalse(capturedURLString.contains("from_station_code="), "URL should not contain from_station_code query parameter")

        XCTAssertEqual(train.trainId, trainId, "Train ID should match")
        XCTAssertEqual(train.line, "Northeast Corridor", "Train line should match mock data")
    }

    func testFetchTrainDetails_NetworkError() async {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)

        let trainId = "123"
        let expectedError = URLError(.notConnectedToInternet)
        mockSession.mockError = expectedError

        do {
            _ = try await apiService.fetchTrainDetails(id: trainId)
            XCTFail("Should have thrown a network error")
        } catch {
            XCTAssertEqual(error as? URLError, expectedError, "Error should be the expected network error")
        }
    }

    func testFetchTrainDetails_APIError_NotFound() async {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)

        let trainId = "unknownID"
        mockSession.mockData = Data() // Empty data for a 404
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/\(trainId)")!, statusCode: 404, httpVersion: nil, headerFields: nil)

        do {
            _ = try await apiService.fetchTrainDetails(id: trainId)
            XCTFail("Should have thrown an error")
        } catch {
            // Expecting a DecodingError because empty data cannot be decoded into Train
            XCTAssertTrue(error is DecodingError, "Error should be a DecodingError for empty data with 404")
        }
    }

    func testFetchTrainDetails_DecodingError() async {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)

        let trainId = "123"
        // Using malformedTrainJSON which represents a single malformed train object
        let malformedJSONData = TrainTestData.malformedTrainJSON.data(using: .utf8)!
        mockSession.mockData = malformedJSONData
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/\(trainId)")!, statusCode: 200, httpVersion: nil, headerFields: nil)

        do {
            _ = try await apiService.fetchTrainDetails(id: trainId)
            XCTFail("Should have thrown a DecodingError")
        } catch {
            XCTAssertTrue(error is DecodingError, "Error should be a DecodingError")
        }
    }

    // MARK: - fetchTrainByNumber Tests

    func testFetchTrainByNumber_Success() async throws {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)

        let trainNumber = "123"
        let fromStationCode = "PJC" // This param is not used in URL by current APIService impl
        let expectedResponseData = TrainTestData.trainListResponseJSON.data(using: .utf8)!

        mockSession.mockData = expectedResponseData
        // The URL for fetchTrainByNumber is just /trains/ with query params
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/")!, statusCode: 200, httpVersion: nil, headerFields: nil)

        // trainListResponseJSON has 3 trains, first one has trainId "123"
        let train = try await apiService.fetchTrainByNumber(trainNumber, fromStationCode: fromStationCode)

        XCTAssertNotNil(mockSession.capturedURL, "URL should have been captured")
        let capturedURLString = mockSession.capturedURL?.absoluteString ?? ""

        XCTAssertTrue(capturedURLString.contains("train_id=\(trainNumber)"), "URL should contain train_id")
        XCTAssertTrue(capturedURLString.contains("sort_by=departure_time"), "URL should contain sort_by")
        XCTAssertTrue(capturedURLString.contains("sort_order=desc"), "URL should contain sort_order")
        XCTAssertTrue(capturedURLString.contains("limit=1"), "URL should contain limit=1")
        XCTAssertTrue(capturedURLString.contains("consolidate=true"), "URL should contain consolidate=true")
        // fromStationCode is NOT part of the URL for this specific method in APIService
        XCTAssertFalse(capturedURLString.contains("from_station_code="), "URL should NOT contain from_station_code")


        XCTAssertEqual(train.trainId, trainNumber, "Returned train ID should match the first train in the mock list")
        XCTAssertEqual(train.line, "Northeast Corridor") // Based on first train in trainListResponseJSON
    }

    func testFetchTrainByNumber_Success_NoFromStationCode() async throws {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)

        let trainNumber = "456" // Second train in trainListResponseJSON
        let expectedResponseData = TrainTestData.trainListResponseJSON.data(using: .utf8)!

        // To make this test more specific, let's craft a response with only train "456" as the first item.
        // For simplicity here, we'll assume trainListResponseJSON's first item is what we want if limit=1 was truly effective server-side.
        // However, the current mock setup returns the whole list and APIService picks the first.
        // So we need to ensure the *mocked data's first train* matches what we expect.
        // The provided trainListResponseJSON has "123" as first. Let's adjust the expectation or use a more specific mock.
        // For this test, we'll use a modified version of trainListResponseJSON that would place "456" first if the API call was specific.
        // Or, more simply, test with "123" as that's the first in the current mock.

        let firstTrainInMock = try TestHelpers.decodeJSON(TrainListResponse.self, from: TrainTestData.trainListResponseJSON).trains.first!
        mockSession.mockData = expectedResponseData
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/")!, statusCode: 200, httpVersion: nil, headerFields: nil)

        let train = try await apiService.fetchTrainByNumber(firstTrainInMock.trainId, fromStationCode: nil)

        XCTAssertNotNil(mockSession.capturedURL, "URL should have been captured")
        let capturedURLString = mockSession.capturedURL?.absoluteString ?? ""
        XCTAssertTrue(capturedURLString.contains("train_id=\(firstTrainInMock.trainId)"), "URL should contain train_id")
        XCTAssertFalse(capturedURLString.contains("from_station_code="), "URL should NOT contain from_station_code")

        XCTAssertEqual(train.trainId, firstTrainInMock.trainId, "Returned train ID should match")
    }

    func testFetchTrainByNumber_NoTrainInResponse() async {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)

        let trainNumber = "unknownNumber"
        let emptyResponseData = TrainTestData.emptyTrainListResponseJSON.data(using: .utf8)!
        mockSession.mockData = emptyResponseData
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/")!, statusCode: 200, httpVersion: nil, headerFields: nil)

        do {
            _ = try await apiService.fetchTrainByNumber(trainNumber)
            XCTFail("Should have thrown APIError.noData")
        } catch {
            XCTAssertEqual(error as? APIError, APIError.noData, "Error should be APIError.noData")
        }
    }

    func testFetchTrainByNumber_NetworkError() async {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)

        let trainNumber = "123"
        let expectedError = URLError(.notConnectedToInternet)
        mockSession.mockError = expectedError

        do {
            _ = try await apiService.fetchTrainByNumber(trainNumber)
            XCTFail("Should have thrown a network error")
        } catch {
            XCTAssertEqual(error as? URLError, expectedError, "Error should be the expected network error")
        }
    }

    func testFetchTrainByNumber_APIError_ServerError() async {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)

        let trainNumber = "123"
        mockSession.mockData = Data() // Empty data for a server error
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/")!, statusCode: 500, httpVersion: nil, headerFields: nil)

        do {
            _ = try await apiService.fetchTrainByNumber(trainNumber)
            XCTFail("Should have thrown an error")
        } catch {
            // Expecting a DecodingError because empty data cannot be decoded into TrainListResponse
            XCTAssertTrue(error is DecodingError, "Error should be a DecodingError for empty data with 500")
        }
    }

    func testFetchTrainByNumber_DecodingError() async {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)

        let trainNumber = "123"
        let malformedJSONData = TrainTestData.malformedTrainListResponseJSON.data(using: .utf8)!
        mockSession.mockData = malformedJSONData
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/")!, statusCode: 200, httpVersion: nil, headerFields: nil)

        do {
            _ = try await apiService.fetchTrainByNumber(trainNumber)
            XCTFail("Should have thrown a DecodingError")
        } catch {
            XCTAssertTrue(error is DecodingError, "Error should be a DecodingError")
        }
    }

    // MARK: - fetchTrainByTrainId Tests

    private func validateDepartureTimeAfter(urlString: String?, sinceHoursAgo: Int, accuracy: TimeInterval = 5.0) throws {
        guard let urlString = urlString, let url = URL(string: urlString) else {
            XCTFail("Captured URL string is nil or invalid")
            return
        }

        let components = URLComponents(url: url, resolvingAgainstBaseURL: false)
        let departureTimeItem = components?.queryItems?.first(where: { $0.name == "departure_time_after" })

        XCTAssertNotNil(departureTimeItem?.value, "departure_time_after query item should exist")
        guard let departureTimeString = departureTimeItem?.value else { return }

        // Use the same formatter as in APIService
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"

        guard let dateFromQuery = formatter.date(from: departureTimeString) else {
            XCTFail("Could not parse departure_time_after string: \(departureTimeString)")
            return
        }

        let expectedTimeInterval = -Double(sinceHoursAgo) * 3600
        XCTAssertEqual(dateFromQuery.timeIntervalSinceNow, expectedTimeInterval, accuracy: accuracy, "departure_time_after should be approximately \(sinceHoursAgo) hours ago.")
    }

    func testFetchTrainByTrainId_Success_DefaultParams() async throws {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)
        let trainId = "NERegional-170"
        let defaultSinceHoursAgo = 6 // Default in APIService implementation

        let expectedResponseData = TrainTestData.trainListResponseJSON.data(using: .utf8)!
        mockSession.mockData = expectedResponseData
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/")!, statusCode: 200, httpVersion: nil, headerFields: nil)

        let trains = try await apiService.fetchTrainByTrainId(trainId)

        XCTAssertNotNil(mockSession.capturedURL, "URL should have been captured")
        let capturedURLString = mockSession.capturedURL?.absoluteString
        XCTAssertTrue(capturedURLString?.contains("train_id=\(trainId)") ?? false)
        XCTAssertTrue(capturedURLString?.contains("consolidate=true") ?? false)
        XCTAssertTrue(capturedURLString?.contains("show_sources=true") ?? false)
        XCTAssertTrue(capturedURLString?.contains("include_predictions=true") ?? false)

        try validateDepartureTimeAfter(urlString: capturedURLString, sinceHoursAgo: defaultSinceHoursAgo)

        XCTAssertEqual(trains.count, 3, "Should return 3 trains based on mock JSON")
        XCTAssertEqual(trains[0].trainId, "123")
    }

    func testFetchTrainByTrainId_Success_CustomParams() async throws {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)
        let trainId = "NERegional-170"
        let customSinceHoursAgo = 3
        let customConsolidate = false

        let expectedResponseData = TrainTestData.trainListResponseJSON.data(using: .utf8)!
        mockSession.mockData = expectedResponseData
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/")!, statusCode: 200, httpVersion: nil, headerFields: nil)

        let trains = try await apiService.fetchTrainByTrainId(trainId, sinceHoursAgo: customSinceHoursAgo, consolidate: customConsolidate)

        XCTAssertNotNil(mockSession.capturedURL, "URL should have been captured")
        let capturedURLString = mockSession.capturedURL?.absoluteString
        XCTAssertTrue(capturedURLString?.contains("train_id=\(trainId)") ?? false)
        XCTAssertTrue(capturedURLString?.contains("consolidate=\(customConsolidate)") ?? false)
        XCTAssertTrue(capturedURLString?.contains("show_sources=true") ?? false) // This is always true in current impl
        XCTAssertTrue(capturedURLString?.contains("include_predictions=true") ?? false) // This is always true

        try validateDepartureTimeAfter(urlString: capturedURLString, sinceHoursAgo: customSinceHoursAgo)

        XCTAssertEqual(trains.count, 3, "Should return 3 trains based on mock JSON")
    }

    func testFetchTrainByTrainId_EmptyResponse() async throws {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)
        let trainId = "unknownTrainId"

        let emptyResponseData = TrainTestData.emptyTrainListResponseJSON.data(using: .utf8)!
        mockSession.mockData = emptyResponseData
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/")!, statusCode: 200, httpVersion: nil, headerFields: nil)

        let trains = try await apiService.fetchTrainByTrainId(trainId)
        XCTAssertTrue(trains.isEmpty, "Returned train array should be empty")
    }

    func testFetchTrainByTrainId_NetworkError() async {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)
        let trainId = "NERegional-170"
        let expectedError = URLError(.notConnectedToInternet)
        mockSession.mockError = expectedError

        do {
            _ = try await apiService.fetchTrainByTrainId(trainId)
            XCTFail("Should have thrown a network error")
        } catch {
            XCTAssertEqual(error as? URLError, expectedError, "Error should be the expected network error")
        }
    }

    func testFetchTrainByTrainId_APIError_ServerError() async {
        let mockSession = MockURLResponseSession()
        apiService = APIService(session: mockSession)
        let trainId = "NERegional-170"

        mockSession.mockData = Data()
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/")!, statusCode: 500, httpVersion: nil, headerFields: nil)

        do {
            _ = try await apiService.fetchTrainByTrainId(trainId)
            XCTFail("Should have thrown an error")
        } catch {
            XCTAssertTrue(error is DecodingError, "Error should be a DecodingError for empty data with 500")
        }
    }

    func testFetchTrainByTrainId_DecodingError() async {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)
        let trainId = "NERegional-170"

        let malformedJSONData = TrainTestData.malformedTrainListResponseJSON.data(using: .utf8)!
        mockSession.mockData = malformedJSONData
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/")!, statusCode: 200, httpVersion: nil, headerFields: nil)

        do {
            _ = try await apiService.fetchTrainByTrainId(trainId)
            XCTFail("Should have thrown a DecodingError")
        } catch {
            XCTAssertTrue(error is DecodingError, "Error should be a DecodingError")
        }
    }

    // MARK: - fetchTrainDetailsFlexible Tests

    func testFetchTrainDetailsFlexible_WithIdAndFromStationCode() async throws {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)
        let dbId = "dbID123"
        let fromCode = "PJC" // Per TrainTestData.legacyTrainJSON -> sampleTrain -> originStationCode = "NP"
                                    // and stops include NP and NY. Let's use NP for an actual stop.
                                    // The `fromStationCode` in `fetchTrainDetails` is used in the URL.

        let expectedResponseData = TrainTestData.legacyTrainJSON.data(using: .utf8)!
        mockSession.mockData = expectedResponseData
        let expectedURL = URL(string: "https://trackrat.net/api/trains/\(dbId)?from_station_code=\(fromCode)")!
        mockSession.mockResponse = HTTPURLResponse(url: expectedURL, statusCode: 200, httpVersion: nil, headerFields: nil)

        let train = try await apiService.fetchTrainDetailsFlexible(id: dbId, trainId: nil, fromStationCode: fromCode)

        XCTAssertNotNil(mockSession.capturedURL, "URL should have been captured")
        XCTAssertEqual(mockSession.capturedURL?.path(), "/api/trains/\(dbId)", "URL path should target specific ID")
        XCTAssertTrue(mockSession.capturedURL?.query?.contains("from_station_code=\(fromCode)") ?? false, "URL query should contain from_station_code")

        XCTAssertEqual(train.trainId, "123", "Train data should be from legacyTrainJSON")
    }

    func testFetchTrainDetailsFlexible_WithOnlyId() async throws {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)
        let dbId = "dbID456"

        let expectedResponseData = TrainTestData.legacyTrainJSON.data(using: .utf8)! // It will return train "123"
        mockSession.mockData = expectedResponseData
        let expectedURL = URL(string: "https://trackrat.net/api/trains/\(dbId)")!
        mockSession.mockResponse = HTTPURLResponse(url: expectedURL, statusCode: 200, httpVersion: nil, headerFields: nil)

        let train = try await apiService.fetchTrainDetailsFlexible(id: dbId, trainId: nil, fromStationCode: nil)

        XCTAssertNotNil(mockSession.capturedURL, "URL should have been captured")
        XCTAssertEqual(mockSession.capturedURL?.path(), "/api/trains/\(dbId)", "URL path should target specific ID")
        XCTAssertNil(mockSession.capturedURL?.query, "URL query should be nil")

        XCTAssertEqual(train.trainId, "123", "Train data should be from legacyTrainJSON")
    }

    func testFetchTrainDetailsFlexible_WithOnlyTrainId_ReturnsFirst() async throws {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)
        let trainIdToFetch = "NER-170" // This is the train_id used in the API call

        let expectedResponseData = TrainTestData.trainListResponseJSON.data(using: .utf8)!
        // trainListResponseJSON contains trains "123", "456", "2150"
        // The method will call fetchTrainByTrainId, which gets a list, and flexible will pick the first.
        mockSession.mockData = expectedResponseData
        let expectedURL = URL(string: "https://trackrat.net/api/trains/")! // Base URL for fetchTrainByTrainId
        mockSession.mockResponse = HTTPURLResponse(url: expectedURL, statusCode: 200, httpVersion: nil, headerFields: nil)

        let train = try await apiService.fetchTrainDetailsFlexible(id: nil, trainId: trainIdToFetch, fromStationCode: nil)

        XCTAssertNotNil(mockSession.capturedURL, "URL should have been captured")
        XCTAssertTrue(mockSession.capturedURL?.query?.contains("train_id=\(trainIdToFetch)") ?? false, "URL should query for train_id")

        // It should return the first train from trainListResponseJSON
        let firstTrainInMockList = try TestHelpers.decodeJSON(TrainListResponse.self, from: expectedResponseData).trains.first
        XCTAssertEqual(train.trainId, firstTrainInMockList?.trainId, "Should return the first train from the list")
        XCTAssertEqual(train.trainId, "123")
    }

    func testFetchTrainDetailsFlexible_WithTrainIdAndFromStationCode_FiltersCorrectly() async throws {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)
        let trainIdToFetch = "123" // This train_id is in legacyTrainJSON, which has stops "NP" and "NY"
        let fromCodeToFilter = "NP"

        // We expect fetchTrainByTrainId to be called.
        // The response should be a list containing the train we want to filter.
        // TrainTestData.trainListResponseJSON's first train has trainId "123" and includes "NP" in its stops.
        let listResponseData = TrainTestData.trainListResponseJSON.data(using: .utf8)!
        mockSession.mockData = listResponseData
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/")!, statusCode: 200, httpVersion: nil, headerFields: nil)

        let train = try await apiService.fetchTrainDetailsFlexible(id: nil, trainId: trainIdToFetch, fromStationCode: fromCodeToFilter)

        XCTAssertNotNil(mockSession.capturedURL, "URL should have been captured for fetchTrainByTrainId")
        XCTAssertTrue(mockSession.capturedURL?.query?.contains("train_id=\(trainIdToFetch)") ?? false)

        XCTAssertEqual(train.trainId, "123", "Train ID should be 123")
        XCTAssertTrue(train.stops?.contains(where: { $0.stationCode == fromCodeToFilter }) ?? false, "Train should have a stop at \(fromCodeToFilter)")
    }

    func testFetchTrainDetailsFlexible_WithTrainIdAndFromStationCode_NoMatchingStop_ReturnsFirst() async throws {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)
        let trainIdToFetch = "123"
        let nonMatchingFromCode = "UNKNOWN_STATION"

        let listResponseData = TrainTestData.trainListResponseJSON.data(using: .utf8)!
        // The first train ("123") in listResponseData does not stop at "UNKNOWN_STATION".
        mockSession.mockData = listResponseData
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/")!, statusCode: 200, httpVersion: nil, headerFields: nil)

        let train = try await apiService.fetchTrainDetailsFlexible(id: nil, trainId: trainIdToFetch, fromStationCode: nonMatchingFromCode)

        XCTAssertNotNil(mockSession.capturedURL, "URL for fetchTrainByTrainId should be captured")
        XCTAssertTrue(mockSession.capturedURL?.query?.contains("train_id=\(trainIdToFetch)") ?? false)

        // Fallback behavior: returns the first train from the list if no stop matches.
        let firstTrainInMockList = try TestHelpers.decodeJSON(TrainListResponse.self, from: listResponseData).trains.first
        XCTAssertEqual(train.trainId, firstTrainInMockList?.trainId, "Should return the first train as fallback")
        XCTAssertEqual(train.trainId, "123")
        XCTAssertFalse(train.stops?.contains(where: { $0.stationCode == nonMatchingFromCode }) ?? true, "Train should not have a stop at \(nonMatchingFromCode)")
    }

    func testFetchTrainDetailsFlexible_WithTrainId_NoTrainsInResponse() async {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)
        let trainIdToFetch = "NonExistentTrainId"

        let emptyResponseData = TrainTestData.emptyTrainListResponseJSON.data(using: .utf8)!
        mockSession.mockData = emptyResponseData
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/")!, statusCode: 200, httpVersion: nil, headerFields: nil)

        do {
            _ = try await apiService.fetchTrainDetailsFlexible(id: nil, trainId: trainIdToFetch, fromStationCode: nil)
            XCTFail("Should have thrown APIError.noData")
        } catch {
            XCTAssertEqual(error as? APIError, APIError.noData)
        }
    }

    func testFetchTrainDetailsFlexible_InvalidParameters_ThrowsError() async {
        apiService = APIService(session: MockURLSession()) // No network call expected

        do {
            _ = try await apiService.fetchTrainDetailsFlexible(id: nil, trainId: nil, fromStationCode: "PJC")
            XCTFail("Should have thrown APIError.invalidParameters")
        } catch {
            XCTAssertEqual(error as? APIError, APIError.invalidParameters)
        }
    }

    func testFetchTrainDetailsFlexible_Path1_NetworkError() async { // id and fromStationCode
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)
        let dbId = "dbID123"
        let fromCode = "PJC"
        let expectedError = URLError(.notConnectedToInternet)
        mockSession.mockError = expectedError
        // Mock a response URL to ensure the mock is for the correct underlying call
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/\(dbId)?from_station_code=\(fromCode)")!, statusCode: 200, httpVersion: nil, headerFields: nil)


        do {
            _ = try await apiService.fetchTrainDetailsFlexible(id: dbId, trainId: nil, fromStationCode: fromCode)
            XCTFail("Should have thrown a network error")
        } catch {
            XCTAssertEqual(error as? URLError, expectedError)
            XCTAssertTrue(mockSession.capturedURL?.absoluteString.contains("/trains/\(dbId)") ?? false, "Should attempt to call fetchTrainDetails with ID")
            XCTAssertTrue(mockSession.capturedURL?.query?.contains("from_station_code=\(fromCode)") ?? false, "fetchTrainDetails URL should contain from_station_code")
        }
    }

    func testFetchTrainDetailsFlexible_Path3_NetworkError() async { // only trainId
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)
        let trainIdToFetch = "NER-170"
        let expectedError = URLError(.notConnectedToInternet)
        mockSession.mockError = expectedError
        // Mock a response URL to ensure the mock is for the correct underlying call
        mockSession.mockResponse = HTTPURLResponse(url: URL(string: "https://trackrat.net/api/trains/")!, statusCode: 200, httpVersion: nil, headerFields: nil)


        do {
            _ = try await apiService.fetchTrainDetailsFlexible(id: nil, trainId: trainIdToFetch, fromStationCode: nil)
            XCTFail("Should have thrown a network error")
        } catch {
            XCTAssertEqual(error as? URLError, expectedError)
            XCTAssertTrue(mockSession.capturedURL?.query?.contains("train_id=\(trainIdToFetch)") ?? false, "Should attempt to call fetchTrainByTrainId")
        }
    }

    // MARK: - fetchHistoricalData Tests

    // Helper to create a basic train for historical data tests
    private func historicalTestTrain() -> Train {
        return Train(id: 1, trainId: "REG123", line: "TestLine", destination: "TestDestination", departureTime: Date(), track: "1", status: .onTime, delayMinutes: nil, stops: nil, predictionData: nil, originStationCode: "ORI", dataSource: "TestSource", consolidatedId: nil, originStation: nil, dataSources: nil, currentPosition: nil, trackAssignment: nil, statusSummary: nil, consolidationMetadata: nil, statusV2: nil, progress: nil)
    }

    func testFetchHistoricalData_Success() async throws {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)
        let train = historicalTestTrain()
        let fromCode = "STA"
        let toCode = "END"

        let trainHistoryData = try TestHelpers.jsonData(from: TrainTestData.trainListResponseJSON)! // Contains 3 trains
        let lineHistoryData = try TestHelpers.jsonData(from: TrainTestData.lineHistoryResponseJSON)! // Also 3 trains
        let destHistoryData = try TestHelpers.jsonData(from: TrainTestData.destinationHistoryResponseJSON)! // Empty

        mockSession.requestHandler = { url in
            if url.query?.contains("train_id=\(train.trainId)") == true {
                return (trainHistoryData, TestHelpers.httpResponse(statusCode: 200))
            } else if url.query?.contains("line=\(train.line)") == true {
                return (lineHistoryData, TestHelpers.httpResponse(statusCode: 200))
            } else if url.query?.contains("destination=\(train.destination)") == true {
                return (destHistoryData, TestHelpers.httpResponse(statusCode: 200))
            }
            XCTFail("Unexpected URL requested: \(url)")
            throw APIError.invalidURL
        }

        let historicalData = try await apiService.fetchHistoricalData(for: train, fromStationCode: fromCode, toStationCode: toCode)

        XCTAssertNotNil(historicalData.trainStats, "Train stats should be calculated")
        XCTAssertEqual(historicalData.trainStats?.total, 3, "Train history had 3 trains")
        // Further stat assertions would require knowing the content of trainListResponseJSON
        // For example, if all 3 trains were "departed" and on time:
        // XCTAssertEqual(historicalData.trainStats?.onTime, 100)


        XCTAssertNotNil(historicalData.lineStats, "Line stats should be calculated")
        XCTAssertEqual(historicalData.lineStats?.total, 3, "Line history had 3 trains")

        XCTAssertNil(historicalData.destinationStats, "Destination stats should be nil as response was empty")
        XCTAssertNil(historicalData.destinationTrackStats, "Destination track stats should be nil")

        XCTAssertEqual(mockSession.capturedURLs.count, 3, "Should have made 3 network calls")
    }

    func testFetchHistoricalData_TrainHistoryFails() async throws {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)
        let train = historicalTestTrain()
        let fromCode = "STA"
        let toCode = "END"
        let networkError = URLError(.notConnectedToInternet)

        let lineHistoryData = try TestHelpers.jsonData(from: TrainTestData.lineHistoryResponseJSON)!
        let destHistoryData = try TestHelpers.jsonData(from: TrainTestData.destinationHistoryResponseJSON)!

        mockSession.requestHandler = { url in
            if url.query?.contains("train_id=\(train.trainId)") == true {
                throw networkError
            } else if url.query?.contains("line=\(train.line)") == true {
                return (lineHistoryData, TestHelpers.httpResponse(statusCode: 200))
            } else if url.query?.contains("destination=\(train.destination)") == true {
                return (destHistoryData, TestHelpers.httpResponse(statusCode: 200))
            }
            XCTFail("Unexpected URL requested: \(url)")
            throw APIError.invalidURL
        }

        do {
            _ = try await apiService.fetchHistoricalData(for: train, fromStationCode: fromCode, toStationCode: toCode)
            XCTFail("Should have thrown a network error because train history failed")
        } catch {
            XCTAssertEqual(error as? URLError, networkError, "The propagated error should be the one from train history call")
        }
    }

    func testFetchHistoricalData_AllHistoryFails() async throws {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)
        let train = historicalTestTrain()
        let fromCode = "STA"
        let toCode = "END"
        let networkError = URLError(.timedOut)

        mockSession.requestHandler = { url in
            throw networkError // All calls fail
        }

        do {
            _ = try await apiService.fetchHistoricalData(for: train, fromStationCode: fromCode, toStationCode: toCode)
            XCTFail("Should have thrown a network error")
        } catch {
            XCTAssertEqual(error as? URLError, networkError, "The propagated error should be one of the network errors")
        }
         XCTAssertEqual(mockSession.capturedURLs.count, 3, "Should have attempted 3 network calls")
    }

    func testFetchHistoricalData_EmptyResponsesFromHelpers() async throws {
        let mockSession = MockURLSession()
        apiService = APIService(session: mockSession)
        let train = historicalTestTrain()
        let fromCode = "STA"
        let toCode = "END"

        let emptyData = try TestHelpers.jsonData(from: TrainTestData.emptyTrainListResponseJSON)!

        mockSession.requestHandler = { url in
            return (emptyData, TestHelpers.httpResponse(statusCode: 200)) // All return empty lists
        }

        let historicalData = try await apiService.fetchHistoricalData(for: train, fromStationCode: fromCode, toStationCode: toCode)

        XCTAssertNil(historicalData.trainStats, "Train stats should be nil for empty response")
        XCTAssertNil(historicalData.trainTrackStats, "Train track stats should be nil for empty response")
        XCTAssertNil(historicalData.lineStats, "Line stats should be nil for empty response")
        XCTAssertNil(historicalData.lineTrackStats, "Line track stats should be nil for empty response")
        XCTAssertNil(historicalData.destinationStats, "Destination stats should be nil for empty response")
        XCTAssertNil(historicalData.destinationTrackStats, "Destination track stats should be nil for empty response")

        XCTAssertEqual(mockSession.capturedURLs.count, 3, "Should have made 3 network calls")
    }
}