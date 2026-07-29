import XCTest
import SwiftUI
import UIKit

@testable import TrackRat

/// Issue #1638: a congestion segment escalated by cancellations rather than
/// delays was captioned "Severe delays" beside an average delay of zero, and
/// `CongestionComparisonBar` printed "On time" tinted with the segment's red
/// `displayColor`. The backend now marks such a segment `cancellation_driven`;
/// these tests pin the display strings and the color that read from it.
final class CongestionSegmentLabelTests: XCTestCase {

    /// Build a segment by decoding the API JSON shape — its only initializer —
    /// so the CodingKeys mapping is exercised rather than assumed.
    private func segment(
        congestionLevel: String,
        congestionFactor: Double = 1.0,
        averageDelayMinutes: Double = 0.0,
        sampleCount: Int = 5,
        cancellationCount: Int = 5,
        cancellationRate: Double = 50.0,
        cancellationDriven: Bool? = nil
    ) throws -> CongestionSegment {
        var json: [String: Any] = [
            "from_station": "CH",
            "to_station": "PE",
            "from_station_name": "South Amboy",
            "to_station_name": "Perth Amboy",
            "data_source": "NJT",
            "congestion_factor": congestionFactor,
            "congestion_level": congestionLevel,
            "average_delay_minutes": averageDelayMinutes,
            "baseline_minutes": 6.0,
            "current_average_minutes": 6.0 + averageDelayMinutes,
            "sample_count": sampleCount,
            "cancellation_count": cancellationCount,
            "cancellation_rate": cancellationRate,
        ]
        if let cancellationDriven { json["cancellation_driven"] = cancellationDriven }
        let data = try JSONSerialization.data(withJSONObject: json)
        return try JSONDecoder().decode(CongestionSegment.self, from: data)
    }

    // MARK: - Decoding

    func testCancellationDrivenDecodesFromTheAPIField() throws {
        let driven = try segment(congestionLevel: "severe", cancellationDriven: true)
        XCTAssertTrue(driven.isCancellationDriven)

        let notDriven = try segment(congestionLevel: "severe", cancellationDriven: false)
        XCTAssertFalse(notDriven.isCancellationDriven)
    }

    /// A backend that predates the field must not flip every segment into the
    /// cancellation wording; absence means "not known to be cancellation-driven".
    func testMissingFieldIsTreatedAsNotCancellationDriven() throws {
        let legacy = try segment(congestionLevel: "severe")
        XCTAssertNil(legacy.cancellationDriven)
        XCTAssertFalse(legacy.isCancellationDriven)
        XCTAssertEqual(legacy.displayCongestionLevel, "Severe delays")
    }

    // MARK: - Display level

    func testCancellationDrivenSegmentNamesCancellationsNotDelays() throws {
        for (level, expected) in [
            ("moderate", "Moderate cancellations"),
            ("heavy", "Heavy cancellations"),
            ("severe", "Severe cancellations"),
        ] {
            let seg = try segment(congestionLevel: level, cancellationDriven: true)
            XCTAssertEqual(
                seg.displayCongestionLevel, expected,
                "a \(level) segment escalated by cancellations must not claim delays")
        }
    }

    func testDelayedSegmentKeepsTheDelayWording() throws {
        let seg = try segment(
            congestionLevel: "severe",
            congestionFactor: 2.0,
            averageDelayMinutes: 6.0,
            cancellationDriven: false)
        XCTAssertEqual(seg.displayCongestionLevel, "Severe delays")
    }

    /// A normal segment was never escalated, so the flag must not invent a
    /// cancellation story for it.
    func testNormalLevelWordingIsUnchangedByTheFlag() throws {
        let seg = try segment(congestionLevel: "normal", cancellationDriven: true)
        XCTAssertEqual(seg.displayCongestionLevel, "Normal conditions")
    }

    // MARK: - Color

    /// `displayColor` re-derives the tier client-side, so it must apply the same
    /// journey floor as the backend or iOS paints a segment red that the API
    /// reports as normal.
    func testSparseCancellationDoesNotColorTheSegmentRed() throws {
        // The reported shape: one train ran on time, one was cancelled.
        let sparse = try segment(
            congestionLevel: "normal",
            sampleCount: 1,
            cancellationCount: 1,
            cancellationRate: 50.0,
            cancellationDriven: false)
        XCTAssertEqual(sparse.totalJourneys, 2)
        XCTAssertEqual(sparse.displayUIColor, .systemGreen)
    }

    func testSustainedCancellationsStillColorTheSegmentRed() throws {
        let sustained = try segment(
            congestionLevel: "severe",
            sampleCount: 5,
            cancellationCount: 5,
            cancellationRate: 50.0,
            cancellationDriven: true)
        XCTAssertEqual(sustained.totalJourneys, 10)
        XCTAssertEqual(sustained.displayUIColor, .systemRed)
    }

    /// The map merge key and the color must agree; a mismatch draws a merged run
    /// in a color none of its segments would render on its own.
    func testTierKeyAgreesWithDisplayColorAcrossTheFloor() throws {
        let sparse = try segment(
            congestionLevel: "normal", sampleCount: 1, cancellationCount: 1)
        XCTAssertEqual(sparse.congestionTierKey, "normal")

        let sustained = try segment(
            congestionLevel: "severe", sampleCount: 5, cancellationCount: 5)
        XCTAssertEqual(sustained.congestionTierKey, "severe")
    }

    /// The floor gates cancellations only — a sparse segment whose train really
    /// lost time still escalates.
    func testSparseButGenuinelyDelayedSegmentStillColorsRed() throws {
        let delayed = try segment(
            congestionLevel: "severe",
            congestionFactor: 2.0,
            averageDelayMinutes: 6.0,
            sampleCount: 1,
            cancellationCount: 1,
            cancellationDriven: false)
        XCTAssertEqual(delayed.displayUIColor, .systemRed)
        XCTAssertEqual(delayed.congestionTierKey, "severe")
    }
}
