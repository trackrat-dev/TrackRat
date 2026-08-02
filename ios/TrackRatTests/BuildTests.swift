import XCTest
import SwiftUI
@testable import TrackRat

class BuildTests: XCTestCase {
    
    func testProjectBuilds() {
        // This test will pass if the project compiles successfully
        XCTAssertTrue(true, "Project builds successfully")
    }
    
    func testCoreModelsCanBeInstantiated() {
        // Test that we can instantiate core models without crashing
        
        // Test Train model creation
        let train = Train(
            id: 1,
            trainId: "123",
            line: "Northeast Corridor",
            destination: "New York Penn Station",
            departureTime: Date(),
            track: "1",
            status: .onTime,
            delayMinutes: nil,
            stops: nil,
            predictionData: nil,
            originStationCode: "NP",
            dataSource: "NJTransit",
            consolidatedId: nil,
            originStation: nil,
            dataSources: nil,
            currentPosition: nil,
            trackAssignment: nil,
            statusSummary: nil,
            consolidationMetadata: nil,
            statusV2: nil,
            progress: nil
        )
        
        XCTAssertNotNil(train)
        XCTAssertEqual(train.trainId, "123")
        XCTAssertEqual(train.line, "Northeast Corridor")
        XCTAssertEqual(train.destination, "New York Penn Station")
    }
    
    func testStationsExist() {
        // Test that Stations static data is available
        XCTAssertFalse(Stations.all.isEmpty, "Stations data should not be empty")
        XCTAssertTrue(Stations.departureStations.count > 0, "Should have departure stations")
    }
    
    @MainActor
    func testAPIServiceExists() {
        // Test that APIService can be instantiated
        let apiService = APIService.shared
        XCTAssertNotNil(apiService)
    }
    
    func testStorageServiceExists() {
        // Test that StorageService can be instantiated
        let storageService = StorageService()
        XCTAssertNotNil(storageService)
    }
    
    @MainActor
    func testLiveActivityServiceExists() {
        // Test that LiveActivityService can be instantiated
        let liveActivityService = LiveActivityService.shared
        XCTAssertNotNil(liveActivityService)
    }
}

final class TrackPredictionViewTests: XCTestCase {
    func testNYPennGroupsIndividualTracksIntoPlatforms() {
        let segments = TrackPredictionSegment.makeSegments(
            from: ["1": 0.2, "2": 0.3, "3": 0.5],
            groupTracksAtNYPenn: true
        )

        XCTAssertEqual(segments.map(\.platformName), ["1 & 2", "3 & 4"])
        XCTAssertEqual(segments.map(\.probability), [0.5, 0.5])
    }

    func testNYPennPreservesPregroupedPlatformKeys() {
        let segments = TrackPredictionSegment.makeSegments(
            from: ["1 & 2": 0.6, "3 & 4": 0.4],
            groupTracksAtNYPenn: true
        )

        XCTAssertEqual(segments.map(\.platformName), ["1 & 2", "3 & 4"])
        XCTAssertEqual(segments.map(\.probability), [0.6, 0.4])
    }

    func testNonNYPennTracksRemainSeparate() {
        let segments = TrackPredictionSegment.makeSegments(
            from: ["1": 0.4, "2": 0.35, "10": 0.25],
            groupTracksAtNYPenn: false
        )

        XCTAssertEqual(segments.map(\.platformName), ["1", "2", "10"])
    }

    func testExpandedRankingIncludesLowProbabilityCandidates() {
        let segments = TrackPredictionSegment.makeSegments(
            from: ["1": 0.12, "2": 0.7, "3": 0.18],
            groupTracksAtNYPenn: false
        )

        XCTAssertEqual(
            segments.sortedByProbability.map(\.platformName),
            ["2", "3", "1"]
        )
        XCTAssertEqual(segments.sortedByProbability.last?.percentageText, "12%")
    }

    func testProbabilityFingerprintChangesWhenDistributionChangesWithSameLeader() {
        let original = TrackPredictionSegment.probabilityFingerprint([
            "7 & 8": 0.6,
            "9 & 10": 0.4
        ])
        let updated = TrackPredictionSegment.probabilityFingerprint([
            "7 & 8": 0.55,
            "9 & 10": 0.45
        ])

        XCTAssertNotEqual(original, updated)
    }

    func testAccessibilitySummaryLimitsCollapsedAnnouncement() {
        let segments = TrackPredictionSegment.makeSegments(
            from: ["1": 0.4, "2": 0.3, "3": 0.2, "4": 0.1],
            groupTracksAtNYPenn: false
        )

        XCTAssertEqual(
            segments.accessibilitySummary,
            "Track 1, 40%, Track 2, 30%, Track 3, 20%, and 1 more"
        )
    }

    func testTrackLabelsAreReadableForAccessibility() {
        let grouped = TrackPredictionSegment(
            id: "7 & 8",
            platformName: "7 & 8",
            probability: 0.421,
            rank: 1
        )
        let single = TrackPredictionSegment(
            id: "17",
            platformName: "17",
            probability: 0.1,
            rank: 2
        )

        XCTAssertEqual(grouped.trackLabel, "Tracks 7 & 8")
        XCTAssertEqual(grouped.percentageText, "42%")
        XCTAssertEqual(single.trackLabel, "Track 17")
        XCTAssertEqual(single.percentageText, "10%")
    }
}

/// Regression tests for `StationNameWithBadges`. The component's custom
/// `StationNameBadgesLayout` once collapsed to zero size when the badge
/// subview was empty — i.e. on every non-subway stop in TrainDetailsView —
/// because the inner `Text` was wrapped in `.frame(maxWidth: .infinity)`,
/// making its ideal width report `.infinity` and the layout's defensive
/// `resolvedWidth` clamp return 0. These tests host the view in a flexible
/// HStack (the same arrangement that exercises the unspecified-proposal
/// measurement pass) and assert the rendered size is non-zero.
@MainActor
class StationNameWithBadgesLayoutTests: XCTestCase {

    func testRendersNameWhenBadgesAreEmpty() {
        let view = HStack(spacing: 12) {
            StationNameWithBadges(
                name: "Princeton Junction",
                subwayLines: [],
                font: .subheadline,
                chipSize: 14,
                includeSystemChips: false
            )
            Spacer()
        }

        let host = UIHostingController(rootView: view)
        host.view.frame = CGRect(x: 0, y: 0, width: 320, height: 100)
        host.view.layoutIfNeeded()

        let fitted = host.sizeThatFits(in: CGSize(width: 320, height: CGFloat.greatestFiniteMagnitude))
        XCTAssertGreaterThan(
            fitted.height, 10,
            "Station name with no badges must contribute non-zero height (regression: TrainDetailsView non-subway stops rendered no station name)"
        )
    }

    func testRendersNameWhenBadgesArePresent() {
        let view = HStack(spacing: 12) {
            StationNameWithBadges(
                name: "Times Sq-42 St",
                subwayLines: ["1", "2", "3", "N", "Q", "R"],
                font: .subheadline,
                chipSize: 14
            )
            Spacer()
        }

        let host = UIHostingController(rootView: view)
        host.view.frame = CGRect(x: 0, y: 0, width: 320, height: 100)
        host.view.layoutIfNeeded()

        let fitted = host.sizeThatFits(in: CGSize(width: 320, height: CGFloat.greatestFiniteMagnitude))
        XCTAssertGreaterThan(fitted.height, 10, "Subway stop with chips must also render with positive height")
    }

    func testNaturalTextBehaviorKeepsTrainDetailsStationNamesUnscaled() {
        let stationName = "Princeton Junction Station With A Long Display Name"
        let width: CGFloat = 120

        let protected = StationNameWithBadges(
            name: stationName,
            subwayLines: [],
            font: .subheadline,
            chipSize: 14,
            includeSystemChips: false
        )
        .frame(width: width)

        let natural = StationNameWithBadges(
            name: stationName,
            subwayLines: [],
            font: .subheadline,
            chipSize: 14,
            includeSystemChips: false,
            textBehavior: .natural
        )
        .frame(width: width)

        let protectedHeight = fittedHeight(for: protected, width: width)
        let naturalHeight = fittedHeight(for: natural, width: width)

        XCTAssertGreaterThan(
            naturalHeight,
            protectedHeight + 6,
            "TrainDetailsView station names should keep the old natural Text behavior instead of shrinking like protected picker rows"
        )
    }

    private func fittedHeight<V: View>(for view: V, width: CGFloat) -> CGFloat {
        let host = UIHostingController(rootView: view)
        host.view.frame = CGRect(x: 0, y: 0, width: width, height: 200)
        host.view.layoutIfNeeded()
        return host.sizeThatFits(in: CGSize(width: width, height: CGFloat.greatestFiniteMagnitude)).height
    }
}
