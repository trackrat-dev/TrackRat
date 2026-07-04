import XCTest
@testable import TrackRat

class V2APIModelsTests: XCTestCase {

    // MARK: - DelayCategory Unknown-Case Fallback

    func testTrainDelaySummaryDecodesKnownCategory() throws {
        let json = """
        {
            "train_id": "3847",
            "delay_minutes": 5,
            "category": "slight_delay",
            "scheduled_departure": "2026-03-28T12:00:00-04:00"
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let summary = try decoder.decode(TrainDelaySummary.self, from: json.data(using: .utf8)!)

        XCTAssertEqual(summary.category, .slightDelay)
    }

    func testTrainDelaySummaryFallsBackToUnknownForUnrecognizedCategory() throws {
        // Backend adds a new delay_category value the app doesn't know about yet.
        // Decode must degrade to .unknown instead of failing the whole response.
        let json = """
        {
            "train_id": "3847",
            "delay_minutes": 5,
            "category": "severely_delayed",
            "scheduled_departure": "2026-03-28T12:00:00-04:00"
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let summary = try decoder.decode(TrainDelaySummary.self, from: json.data(using: .utf8)!)

        XCTAssertEqual(summary.category, .unknown)
    }
}
