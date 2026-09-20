import UserNotifications
import XCTest
@testable import TrackRat

/// Tests for the notification permission state the alerts UI reads.
///
/// The distinction that matters: a status that can still deliver alerts, versus
/// one the user must be walked back through Settings to change.
@MainActor
final class NotificationPermissionServiceTests: XCTestCase {

    func testAuthorizedStatusesCanDeliverAlerts() {
        XCTAssertTrue(NotificationPermissionService.canDeliverAlerts(.authorized))
    }

    func testProvisionalAndEphemeralCanDeliverAlerts() {
        // Quiet-delivery grants still reach the user, so alerts are worth setting up.
        XCTAssertTrue(NotificationPermissionService.canDeliverAlerts(.provisional))
        XCTAssertTrue(NotificationPermissionService.canDeliverAlerts(.ephemeral))
    }

    func testDeniedCannotDeliverAlerts() {
        XCTAssertFalse(NotificationPermissionService.canDeliverAlerts(.denied))
    }

    func testNotDeterminedCannotDeliverAlertsUntilAsked() {
        // Undecided is not permission: the prompt still has to be shown, which is
        // exactly what requestIfNeeded() does at the moment an alert is created.
        XCTAssertFalse(NotificationPermissionService.canDeliverAlerts(.notDetermined))
    }

    func testIsDeniedOnlyReflectsAnActualRefusal() {
        // The recovery banner keys off this, and must not appear for a user who
        // simply hasn't been asked yet.
        let service = NotificationPermissionService.shared

        XCTAssertEqual(service.isDenied, service.authorizationStatus == .denied)
        XCTAssertFalse(service.isDenied, "The test host has never refused notifications")
    }

    func testRefreshStatusReadsTheSystemSetting() async {
        let service = NotificationPermissionService.shared
        let systemStatus = await UNUserNotificationCenter.current()
            .notificationSettings()
            .authorizationStatus

        await service.refreshStatus()

        XCTAssertEqual(service.authorizationStatus, systemStatus)
    }
}
