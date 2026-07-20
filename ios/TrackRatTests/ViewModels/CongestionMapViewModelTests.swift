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

    func testSkipStopSegmentResolvesTapToRealServedPair() throws {
        // Issue #1560: a tapped Amtrak CWH→PHN sub-segment (stations no train
        // stops at) must navigate to the real served leg the backend supplies.
        let json = """
        {
            "individual_segments": [],
            "aggregated_segments": [{
                "from_station": "CWH",
                "to_station": "PHN",
                "from_station_name": "Cornwells Heights",
                "to_station_name": "North Philadelphia",
                "data_source": "AMTRAK",
                "congestion_level": "normal",
                "congestion_factor": 1.1,
                "average_delay_minutes": 2.0,
                "sample_count": 12,
                "baseline_minutes": 28.0,
                "current_average_minutes": 30.0,
                "real_from_station": "TR",
                "real_to_station": "PH"
            }],
            "train_positions": [],
            "generated_at": "2026-03-28T12:00:00-04:00",
            "time_window_hours": 2,
            "max_per_segment": 100,
            "metadata": {}
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let response = try decoder.decode(
            CongestionMapResponse.self, from: json.data(using: .utf8)!)

        let segment = try XCTUnwrap(response.aggregatedSegments.first)
        XCTAssertEqual(segment.realFromStation, "TR")
        XCTAssertEqual(segment.realToStation, "PH")
        // The tap resolves to the served pair, not the skip-stop endpoints.
        XCTAssertEqual(segment.navFromStation, "TR")
        XCTAssertEqual(segment.navToStation, "PH")
    }

    func testSegmentWithoutRealPairFallsBackToOwnEndpoints() throws {
        // Older backends omit real_from_station/real_to_station; the tap must
        // fall back to the segment's own endpoints.
        let json = """
        {
            "individual_segments": [],
            "aggregated_segments": [{
                "from_station": "NY",
                "to_station": "SE",
                "from_station_name": "New York Penn",
                "to_station_name": "Secaucus",
                "data_source": "NJT",
                "congestion_level": "normal",
                "congestion_factor": 1.1,
                "average_delay_minutes": 0.5,
                "sample_count": 10,
                "baseline_minutes": 4.5,
                "current_average_minutes": 5.0
            }],
            "train_positions": [],
            "generated_at": "2026-03-28T12:00:00-04:00",
            "time_window_hours": 2,
            "max_per_segment": 100,
            "metadata": {}
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let response = try decoder.decode(
            CongestionMapResponse.self, from: json.data(using: .utf8)!)

        let segment = try XCTUnwrap(response.aggregatedSegments.first)
        XCTAssertNil(segment.realFromStation)
        XCTAssertNil(segment.realToStation)
        XCTAssertEqual(segment.navFromStation, "NY")
        XCTAssertEqual(segment.navToStation, "SE")
    }
}
