import XCTest
@testable import TrackRat

class CongestionMapViewModelTests: XCTestCase {

    func testDecodeCongestionResponseWithMergedFromSystems() throws {
        // Backend returns merged_from_systems as an array in metadata
        // for multi-provider responses. CodableValue must handle arrays.
        let json = """
        {
            "individual_segments": [],
            "aggregated_segments": [],
            "train_positions": [],
            "generated_at": "2026-03-28T12:00:00-04:00",
            "time_window_hours": 2,
            "max_per_segment": 100,
            "metadata": {
                "total_individual_segments": 500,
                "total_aggregated_segments": 100,
                "congestion_levels": {"normal": 80, "moderate": 15, "heavy": 4, "severe": 1},
                "total_trains": 50,
                "merged_from_systems": ["NJT", "PATH", "AMTRAK", "LIRR", "MNR", "SUBWAY"]
            }
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let data = json.data(using: .utf8)!
        let response = try decoder.decode(CongestionMapResponse.self, from: data)

        XCTAssertEqual(response.timeWindowHours, 2, "time_window_hours should decode correctly")
        XCTAssertEqual(response.maxPerSegment, 100, "max_per_segment should decode correctly")
        XCTAssertEqual(response.totalIndividualSegments, 500, "total_individual_segments from metadata")
        XCTAssertEqual(response.totalAggregatedSegments, 100, "total_aggregated_segments from metadata")
        XCTAssertEqual(response.totalTrains, 50, "total_trains from metadata")
    }

    func testDecodeCongestionResponseWithNullMetadataValue() throws {
        // A null value anywhere in metadata (e.g. a not-yet-computed stat) must
        // decode via CodableValue's .null case instead of failing the whole response.
        let json = """
        {
            "individual_segments": [],
            "aggregated_segments": [],
            "train_positions": [],
            "generated_at": "2026-03-28T12:00:00-04:00",
            "time_window_hours": 2,
            "max_per_segment": 100,
            "metadata": {
                "total_individual_segments": 500,
                "total_aggregated_segments": 100,
                "total_trains": 50,
                "unavailable_stat": null
            }
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let data = json.data(using: .utf8)!
        let response = try decoder.decode(CongestionMapResponse.self, from: data)

        XCTAssertEqual(response.totalTrains, 50, "decode should succeed despite the null metadata value")
    }
}
