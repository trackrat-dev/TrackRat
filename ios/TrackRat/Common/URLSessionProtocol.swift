import Foundation

protocol URLSessionProtocol {
    func data(from url: URL, delegate: URLSessionTaskDelegate?) async throws -> (Data, URLResponse)
}

extension URLSession: URLSessionProtocol {}
