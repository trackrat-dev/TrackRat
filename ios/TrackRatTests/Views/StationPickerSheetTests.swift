import XCTest
@testable import TrackRat

@MainActor
final class StationPickerSheetTests: XCTestCase {

    private let disabledStationNames = [
        "West Oakland",
        "Metro Center",
        "North Station",
        "Naperville Metra",
    ]

    /// Previously in `disabledStationNames`; SEPTA was re-enabled for the #1634
    /// rollout, so the picker must now render them.
    private let reEnabledSeptaStationNames = [
        "Media",
        "Olney Transit Center - B1",
    ]

    func testBrowseRowsExcludeDisabledOnlyStationsWithoutASelectionFilter() {
        let rows = StationPickerSheet.pickerStations(selectedSystems: nil)
        let rowNames = Set(rows.map(\.name))

        for name in disabledStationNames {
            XCTAssertFalse(rowNames.contains(name), "Picker browse rows must exclude disabled-only station \(name)")
        }
        XCTAssertTrue(
            rowNames.contains("Boston South"),
            "A shared Amtrak/MBTA station must remain in picker browse rows through Amtrak"
        )
    }

    func testSearchRowsExcludeDisabledOnlyStationsFromOtherSystems() {
        for name in disabledStationNames {
            guard let disabledCode = Stations.getStationCode(name) else {
                XCTFail("Missing station code for \(name)")
                continue
            }
            let results = StationPickerSheet.pickerSearchResults(name, selectedSystems: [.njt])
            XCTAssertFalse(
                (results.active + results.inactive).contains { $0.code == disabledCode },
                "Picker search must not render disabled-only station \(name) as a selectable row"
            )
        }
    }

    func testSearchRowsIncludeReEnabledSeptaStations() {
        for name in reEnabledSeptaStationNames {
            guard let code = Stations.getStationCode(name) else {
                XCTFail("Missing station code for \(name)")
                continue
            }
            let results = StationPickerSheet.pickerSearchResults(name, selectedSystems: nil)
            XCTAssertTrue(
                (results.active + results.inactive).contains { $0.code == code },
                "Picker search must render re-enabled SEPTA station \(name)"
            )
        }
    }

    func testBrowseRowsIncludeReEnabledSeptaStations() {
        let rowNames = Set(StationPickerSheet.pickerStations(selectedSystems: nil).map(\.name))
        for name in reEnabledSeptaStationNames {
            XCTAssertTrue(
                rowNames.contains(name),
                "Picker browse rows must include re-enabled SEPTA station \(name)"
            )
        }
    }
}
