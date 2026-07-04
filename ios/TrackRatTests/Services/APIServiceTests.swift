import XCTest
@testable import TrackRat

class APIServiceTests: XCTestCase {
    
    var apiService: APIService!
    
    @MainActor
    override func setUp() {
        super.setUp()
        apiService = APIService.shared
    }
    
    override func tearDown() {
        apiService = nil
        super.tearDown()
    }
    
    @MainActor
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

    func testPlatformPredictionDecodesValidResponse() {
        let jsonString = """
        {
            "platform_probabilities": {"1": 0.6, "2": 0.4},
            "primary_prediction": "1",
            "confidence": 0.85,
            "top_3": ["1", "2", "3"],
            "model_version": "v1",
            "station_code": "NY",
            "train_id": "1234"
        }
        """
        do {
            let prediction = try TestHelpers.decodeJSON(PlatformPrediction.self, from: jsonString)
            XCTAssertEqual(prediction.primaryPrediction, "1")
            XCTAssertEqual(prediction.confidence, 0.85, accuracy: 0.0001)
            XCTAssertEqual(prediction.top3, ["1", "2", "3"])
        } catch {
            XCTFail("Should decode a valid PlatformPrediction. Error: \(error)")
        }
    }

    func testPlatformPredictionDoesNotDecodeFromErrorBody() {
        // Backend returns a 404 with this body when there's no historical data
        // (see backend_v2/src/trackrat/api/predictions.py).
        // Pre-fix behavior: getPlatformPrediction would attempt to decode this
        // body as a PlatformPrediction, surfacing a misleading "Decoding error"
        // in the caller. The fix is to throw APIError.notFound on a 404 status
        // before decoding. This test guards that the error body is not
        // accidentally decodable to PlatformPrediction.
        let errorBody = """
        {"detail": "Insufficient historical data to predict track for train 1234 at station NY"}
        """
        XCTAssertThrowsError(
            try TestHelpers.decodeJSON(PlatformPrediction.self, from: errorBody),
            "An error response body must not silently decode as a PlatformPrediction"
        )
    }

    func testAPIErrorDescriptions() {
        XCTAssertEqual(APIError.notFound.errorDescription, "Resource not found")
        XCTAssertEqual(APIError.serverError.errorDescription, "Server error")
    }

    // MARK: - validate(_:) status mapping
    // Guards issue #1375: every endpoint must map HTTP status the same way,
    // so a 5xx from a load-balancer blip surfaces as .serverError (retryable)
    // instead of being decoded as a success body and blowing up as a DecodingError.

    private func httpResponse(statusCode: Int) -> HTTPURLResponse {
        HTTPURLResponse(
            url: URL(string: "https://staging.apiv2.trackrat.net/api/v2/routes/summary")!,
            statusCode: statusCode,
            httpVersion: "HTTP/1.1",
            headerFields: nil
        )!
    }

    @MainActor
    func testValidateThrowsNotFoundOn404() {
        XCTAssertThrowsError(try apiService.validate(httpResponse(statusCode: 404))) { error in
            guard let apiError = error as? APIError else {
                return XCTFail("Expected APIError, got \(error)")
            }
            XCTAssertEqual(apiError.errorDescription, APIError.notFound.errorDescription)
        }
    }

    @MainActor
    func testValidateThrowsServerErrorOn5xx() {
        for statusCode in [500, 502, 503, 504] {
            XCTAssertThrowsError(try apiService.validate(httpResponse(statusCode: statusCode))) { error in
                guard let apiError = error as? APIError else {
                    return XCTFail("Expected APIError for status \(statusCode), got \(error)")
                }
                XCTAssertEqual(apiError.errorDescription, APIError.serverError.errorDescription, "Status \(statusCode) should map to .serverError")
            }
        }
    }

    @MainActor
    func testValidateThrowsInvalidParametersOnOther4xx() {
        for statusCode in [400, 401, 403, 422] {
            XCTAssertThrowsError(try apiService.validate(httpResponse(statusCode: statusCode))) { error in
                guard let apiError = error as? APIError else {
                    return XCTFail("Expected APIError for status \(statusCode), got \(error)")
                }
                XCTAssertEqual(apiError.errorDescription, APIError.invalidParameters.errorDescription, "Status \(statusCode) should map to .invalidParameters")
            }
        }
    }

    @MainActor
    func testValidateDoesNotThrowOn2xx() {
        for statusCode in [200, 201, 204] {
            XCTAssertNoThrow(try apiService.validate(httpResponse(statusCode: statusCode)), "Status \(statusCode) should not throw")
        }
    }
}