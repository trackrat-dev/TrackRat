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
    
    func testLiveActivityServiceExists() {
        // Test that LiveActivityService can be instantiated
        let liveActivityService = LiveActivityService.shared
        XCTAssertNotNil(liveActivityService)
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

        let fitted = host.sizeThatFits(in: CGSize(width: 320, height: .greatestFiniteMagnitude))
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

        let fitted = host.sizeThatFits(in: CGSize(width: 320, height: .greatestFiniteMagnitude))
        XCTAssertGreaterThan(fitted.height, 10, "Subway stop with chips must also render with positive height")
    }
}
