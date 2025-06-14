import Foundation
@testable import TrackRat // Import the main module to access URLSessionProtocol

class MockURLSession: URLSessionProtocol {
    // For simple tests with a single expected request
    var mockData: Data?
    var mockResponse: URLResponse?
    var mockError: Error?
    var capturedURL: URL? // Captures the last URL requested

    // For complex tests with multiple, different expected requests
    typealias RequestHandler = (URL) throws -> (Data, URLResponse)
    var requestHandler: RequestHandler?

    // To capture all URLs requested when using a requestHandler
    var capturedURLs: [URL] = []

    func data(from url: URL, delegate: URLSessionTaskDelegate?) async throws -> (Data, URLResponse) {
        capturedURL = url
        capturedURLs.append(url)

        if let requestHandler = requestHandler {
            return try requestHandler(url)
        }

        // Fallback to simple mocking if no handler is set
        if let error = mockError {
            throw error
        }
        guard let data = mockData, let response = mockResponse else {
            throw NSError(domain: "MockURLSession", code: 0, userInfo: [NSLocalizedDescriptionKey: "Mock data/response not set for URL: \(url.absoluteString). Or requestHandler not implemented."])
        }
        return (data, response)
    }

    func resetMock() {
        mockData = nil
        mockResponse = nil
        mockError = nil
        capturedURL = nil
        requestHandler = nil
        capturedURLs = []
    }
}
