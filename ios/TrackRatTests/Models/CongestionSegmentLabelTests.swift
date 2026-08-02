import XCTest
import SwiftUI
import UIKit

@testable import TrackRat

/// Issue #1638: a congestion segment escalated by cancellations rather than
/// delays was captioned "Severe delays" beside an average delay of zero, and
/// `CongestionComparisonBar` printed "On time" tinted with the segment's red
/// `displayColor`. The backend now reports a three-valued `congestion_cause`;
/// these tests pin the display strings and the colour that read from it,
/// including the mixed delayed-and-cancelled case raised in review of #1681.
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
        congestionCause: String? = nil
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
        if let congestionCause { json["congestion_cause"] = congestionCause }
        let data = try JSONSerialization.data(withJSONObject: json)
        return try JSONDecoder().decode(CongestionSegment.self, from: data)
    }

    // MARK: - Decoding

    func testCauseDecodesFromTheAPIField() throws {
        for (raw, expected) in [
            ("delays", CongestionSegment.Cause.delays),
            ("cancellations", CongestionSegment.Cause.cancellations),
            ("both", CongestionSegment.Cause.both),
        ] {
            let seg = try segment(congestionLevel: "severe", congestionCause: raw)
            XCTAssertEqual(seg.cause, expected)
        }
    }

    /// An unrecognised value from a newer backend must degrade to the safe
    /// default rather than crashing or inventing a cancellation story.
    func testUnknownCauseFallsBackToDelays() throws {
        let seg = try segment(congestionLevel: "severe", congestionCause: "gremlins")
        XCTAssertEqual(seg.cause, .delays)
        XCTAssertFalse(seg.involvesCancellations)
    }

    /// "both" must count as involving cancellations, or a mixed segment's
    /// cancellation count is dropped from every caption.
    func testMixedCauseInvolvesCancellations() throws {
        XCTAssertTrue(
            try segment(congestionLevel: "heavy", congestionCause: "both").involvesCancellations)
        XCTAssertTrue(
            try segment(congestionLevel: "heavy", congestionCause: "cancellations")
                .involvesCancellations)
        XCTAssertFalse(
            try segment(congestionLevel: "heavy", congestionCause: "delays").involvesCancellations)
    }

    /// A backend that predates the field must not flip every segment into the
    /// cancellation wording; absence means "not known to be cancellation-driven".
    func testMissingFieldIsTreatedAsDelays() throws {
        let legacy = try segment(congestionLevel: "severe")
        XCTAssertNil(legacy.congestionCause)
        XCTAssertEqual(legacy.cause, .delays)
        XCTAssertFalse(legacy.involvesCancellations)
        XCTAssertEqual(legacy.displayCongestionLevel, "Severe delays")
    }

    // MARK: - Display level

    func testCancellationDrivenSegmentNamesCancellationsNotDelays() throws {
        for (level, expected) in [
            ("moderate", "Moderate cancellations"),
            ("heavy", "Heavy cancellations"),
            ("severe", "Severe cancellations"),
        ] {
            let seg = try segment(congestionLevel: level, congestionCause: "cancellations")
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
            congestionCause: "delays")
        XCTAssertEqual(seg.displayCongestionLevel, "Severe delays")
    }

    /// A normal segment was never escalated, so the flag must not invent a
    /// cancellation story for it.
    func testNormalLevelWordingIsUnchangedByTheCause() throws {
        for cause in ["delays", "cancellations", "both"] {
            let seg = try segment(congestionLevel: "normal", congestionCause: cause)
            XCTAssertEqual(seg.displayCongestionLevel, "Normal conditions")
        }
    }

    /// Raised in review of #1681: a segment can be genuinely delayed AND pushed
    /// a tier further by cancellations. Naming only one cause either contradicts
    /// the non-zero delay shown beside it or hides the cancellations.
    func testMixedCauseNamesBoth() throws {
        for (level, expected) in [
            ("moderate", "Moderate delays and cancellations"),
            ("heavy", "Heavy delays and cancellations"),
            ("severe", "Severe delays and cancellations"),
        ] {
            let seg = try segment(congestionLevel: level, congestionCause: "both")
            XCTAssertEqual(seg.displayCongestionLevel, expected)
        }
    }

    // MARK: - Comparison-bar caption
    //
    // `CongestionComparisonBar.delayText` is private, so these mirror its exact
    // rule against the same inputs. The rule is small and the contradiction it
    // prevents is the reported bug, so it is worth pinning here rather than
    // leaving the only coverage in a view that cannot be reached from a test.

    private func delayText(for segment: CongestionSegment) -> String {
        let delayMinutes = Int(segment.averageDelayMinutes.rounded())
        let cancelled = segment.involvesCancellations
            ? "\(segment.cancellationCount) cancelled"
            : nil
        guard delayMinutes > 0 else { return cancelled ?? "On time" }
        let delay = "+\(delayMinutes) min delay"
        guard let cancelled else { return delay }
        return "\(delay), \(cancelled)"
    }

    func testCaptionNeverSaysOnTimeOnACancellationEscalatedSegment() throws {
        let seg = try segment(
            congestionLevel: "severe",
            averageDelayMinutes: 0.0,
            cancellationCount: 4,
            congestionCause: "cancellations")
        XCTAssertEqual(delayText(for: seg), "4 cancelled")
    }

    func testCaptionKeepsBothFactsOnAMixedSegment() throws {
        // Reporting only "+2 min delay" drops the cancellations that are half
        // the reason the bar is coloured as it is (review of #1681).
        let seg = try segment(
            congestionLevel: "heavy",
            congestionFactor: 1.2,
            averageDelayMinutes: 2.0,
            cancellationCount: 3,
            congestionCause: "both")
        XCTAssertEqual(delayText(for: seg), "+2 min delay, 3 cancelled")
    }

    func testCaptionIsUnchangedForAnOrdinaryOnTimeSegment() throws {
        let seg = try segment(
            congestionLevel: "normal",
            averageDelayMinutes: 0.0,
            cancellationCount: 0,
            cancellationRate: 0.0,
            congestionCause: "delays")
        XCTAssertEqual(delayText(for: seg), "On time")
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
            congestionCause: "delays")
        XCTAssertEqual(sparse.totalJourneys, 2)
        XCTAssertEqual(sparse.displayUIColor, .systemGreen)
    }

    func testSustainedCancellationsStillColorTheSegmentRed() throws {
        // Colours are ramped (#1715), so "red" is now "well along the ramp
        // toward red", not literally `.systemRed`: a 50% cancellation rate
        // blends to 1.75, three quarters of the way up. Asserting a specific
        // UIColor here would just re-encode the ramp's arithmetic.
        let sustained = try segment(
            congestionLevel: "severe",
            sampleCount: 5,
            cancellationCount: 5,
            cancellationRate: 50.0,
            congestionCause: "cancellations")
        XCTAssertEqual(sustained.totalJourneys, 10)
        XCTAssertNotEqual(sustained.displayUIColor, .systemGreen)
        XCTAssertEqual(
            sustained.congestionColorKey,
            CongestionColors.congestionColorKey(forFactor: 1.75))
    }

    /// The map merge key and the color must agree; a mismatch draws a merged run
    /// in a color none of its segments would render on its own.
    func testColorKeyAgreesWithDisplayColorAcrossTheFloor() throws {
        // Below the floor the cancellations are dropped, so this segment must key
        // and render exactly like an on-time one.
        let sparse = try segment(
            congestionLevel: "normal", sampleCount: 1, cancellationCount: 1)
        XCTAssertEqual(
            sparse.congestionColorKey, CongestionColors.congestionColorKey(forFactor: 1.0))
        XCTAssertEqual(sparse.displayUIColor, .systemGreen)

        let sustained = try segment(
            congestionLevel: "severe", sampleCount: 5, cancellationCount: 5)
        XCTAssertNotEqual(sustained.congestionColorKey, sparse.congestionColorKey)
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
            congestionCause: "delays")
        // 2.0 is the top of the ramp, so this one *is* fully severe.
        XCTAssertEqual(delayed.displayUIColor, .systemRed)
        XCTAssertEqual(
            delayed.congestionColorKey, CongestionColors.congestionColorKey(forFactor: 2.0))
    }
}
