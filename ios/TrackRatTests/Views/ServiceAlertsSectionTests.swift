import XCTest
@testable import TrackRat

/// Tests for the service-alert deep-link logic used when a user taps a
/// service-alert push. `ServiceAlertsSection.initialFilter` decides which
/// tab (Active / Upcoming) to open so the tapped alert is visible.
final class ServiceAlertsSectionTests: XCTestCase {

    // MARK: - Helpers

    /// Builds an alert that is either currently active or purely upcoming,
    /// driven by explicit active periods so `isActiveNow` is deterministic.
    private func makeAlert(id: String, active: Bool) -> V2ServiceAlert {
        let now = Int(Date().timeIntervalSince1970)
        let periods: [V2ServiceAlertActivePeriod] = active
            ? [V2ServiceAlertActivePeriod(start: now - 3600, end: now + 3600)]
            : [V2ServiceAlertActivePeriod(start: now + 3600, end: now + 7200)]
        return V2ServiceAlert(
            alertId: id,
            dataSource: "SUBWAY",
            alertType: "alert",
            affectedRouteIds: [],
            headerText: "Header \(id)",
            descriptionText: nil,
            activePeriods: periods
        )
    }

    // MARK: - initialFilter

    func testInitialFilter_noFocusedIds_defaultsToActive() {
        let alerts = [makeAlert(id: "a", active: false)]
        XCTAssertEqual(
            ServiceAlertsSection.initialFilter(alerts: alerts, focusedAlertIds: []),
            .active,
            "With nothing focused, the section should default to the Active tab (prior behavior)"
        )
    }

    func testInitialFilter_focusedActiveAlert_selectsActive() {
        let alerts = [makeAlert(id: "active", active: true), makeAlert(id: "future", active: false)]
        XCTAssertEqual(
            ServiceAlertsSection.initialFilter(alerts: alerts, focusedAlertIds: ["active"]),
            .active,
            "A focused alert that is active now should open the Active tab"
        )
    }

    func testInitialFilter_focusedUpcomingOnly_selectsUpcoming() {
        let alerts = [makeAlert(id: "active", active: true), makeAlert(id: "future", active: false)]
        XCTAssertEqual(
            ServiceAlertsSection.initialFilter(alerts: alerts, focusedAlertIds: ["future"]),
            .upcoming,
            "A focused alert that is only upcoming should open the Upcoming tab so it's visible"
        )
    }

    func testInitialFilter_focusedActiveAndUpcoming_prefersActive() {
        let alerts = [makeAlert(id: "active", active: true), makeAlert(id: "future", active: false)]
        XCTAssertEqual(
            ServiceAlertsSection.initialFilter(alerts: alerts, focusedAlertIds: ["active", "future"]),
            .active,
            "When focused IDs span both tabs, prefer Active"
        )
    }

    func testInitialFilter_focusedIdNotPresent_defaultsToActive() {
        let alerts = [makeAlert(id: "a", active: false)]
        XCTAssertEqual(
            ServiceAlertsSection.initialFilter(alerts: alerts, focusedAlertIds: ["missing"]),
            .active,
            "A focused ID that isn't in the loaded alerts should fall back to Active"
        )
    }

    func testInitialFilter_emptyActivePeriods_treatedAsActive() {
        // An alert with no active periods is "always active" (isActiveNow == true).
        let alert = V2ServiceAlert(
            alertId: "sys",
            dataSource: "SUBWAY",
            alertType: "alert",
            affectedRouteIds: [],
            headerText: "System-wide advisory",
            descriptionText: nil,
            activePeriods: []
        )
        XCTAssertEqual(
            ServiceAlertsSection.initialFilter(alerts: [alert], focusedAlertIds: ["sys"]),
            .active,
            "A system-wide alert with no active periods should be treated as active"
        )
    }

    // MARK: - RouteStatusContext focused-alert plumbing (push deep-link)

    func testRouteStatusContext_focusedAlertIds_defaultsToEmpty() {
        let context = RouteStatusContext(dataSource: "SUBWAY", lineId: "M")
        XCTAssertTrue(context.focusedAlertIds.isEmpty, "focusedAlertIds should default to empty when not provided")
    }

    func testRouteStatusContext_focusedAlertIds_storedWhenProvided() {
        let context = RouteStatusContext(
            dataSource: "NJT",
            fromStationCode: "NY",
            toStationCode: "PJ",
            focusedAlertIds: ["a1", "a2"]
        )
        XCTAssertEqual(
            context.focusedAlertIds,
            ["a1", "a2"],
            "focusedAlertIds should be stored verbatim from the push payload"
        )
    }
}
