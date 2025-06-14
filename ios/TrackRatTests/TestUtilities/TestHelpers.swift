import XCTest
import Foundation
@testable import TrackRat

class TestHelpers {
    
    static func createMockDate(from string: String) -> Date {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        return formatter.date(from: string) ?? Date()
    }
    
    static func createISO8601Date(from string: String) -> Date {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        return formatter.date(from: string) ?? Date()
    }
    
    static func jsonData(from string: String) -> Data? {
        return string.data(using: .utf8)
    }
    
    static func decodeJSON<T: Codable>(_ type: T.Type, from jsonString: String) throws -> T {
        guard let data = jsonData(from: jsonString) else {
            throw TestError.invalidJSON
        }
        
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let dateString = try container.decode(String.self)
            
            if let date = Date.fromISO8601(dateString) {
                return date
            }
            
            throw TestError.invalidDate
        }
        
        return try decoder.decode(type, from: data)
    }
    
    static func assertDatesEqual(_ date1: Date, _ date2: Date, accuracy: TimeInterval = 1.0, file: StaticString = #file, line: UInt = #line) {
        let timeDifference = abs(date1.timeIntervalSince(date2))
        XCTAssertLessThanOrEqual(timeDifference, accuracy, "Dates should be equal within \(accuracy) seconds", file: file, line: line)
    }
    
    static func waitForExpectation(_ expectation: XCTestExpectation, timeout: TimeInterval = 5.0) {
        let result = XCTWaiter.wait(for: [expectation], timeout: timeout)
        XCTAssertEqual(result, .completed, "Expectation should complete within timeout")
    }

    static func httpResponse(urlString: String = "https://example.com", statusCode: Int) -> HTTPURLResponse {
        let url = URL(string: urlString)!
        return HTTPURLResponse(url: url, statusCode: statusCode, httpVersion: "HTTP/1.1", headerFields: nil)!
    }
}

enum TestError: Error {
    case invalidJSON
    case invalidDate
    case networkError
    case unknown
}

extension TestError: LocalizedError {
    var errorDescription: String? {
        switch self {
        case .invalidJSON:
            return "Invalid JSON data"
        case .invalidDate:
            return "Invalid date format"
        case .networkError:
            return "Network error"
        case .unknown:
            return "Unknown error"
        }
    }
}