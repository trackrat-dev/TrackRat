import Foundation
import UIKit
import UserNotifications

/// Notification permission, asked for when a feature actually needs it rather
/// than on first launch.
///
/// Route alerts are the only feature that needs it: Live Activities are gated by
/// the separate system Live Activities setting, and the APNs token used to push
/// updates to them comes from `registerForRemoteNotifications()`, which never
/// prompts. Spending the one prompt iOS allows during setup therefore buys
/// nothing and loses alerts for everyone who taps "Don't Allow".
@MainActor
final class NotificationPermissionService: ObservableObject {
    static let shared = NotificationPermissionService()

    @Published private(set) var authorizationStatus: UNAuthorizationStatus = .notDetermined

    private init() {}

    /// The user actively refused. iOS will not prompt again, so the only way
    /// back is the Settings app.
    var isDenied: Bool { authorizationStatus == .denied }

    /// Whether alerts can currently reach the user.
    static func canDeliverAlerts(_ status: UNAuthorizationStatus) -> Bool {
        switch status {
        case .authorized, .provisional, .ephemeral:
            return true
        case .denied, .notDetermined:
            return false
        @unknown default:
            return false
        }
    }

    func refreshStatus() async {
        authorizationStatus = await UNUserNotificationCenter.current()
            .notificationSettings()
            .authorizationStatus
    }

    /// Ask for permission if it hasn't been decided yet, and report whether
    /// alerts can be delivered. Safe to call repeatedly — iOS only shows the
    /// prompt while the status is `.notDetermined`.
    @discardableResult
    func requestIfNeeded() async -> Bool {
        await refreshStatus()
        guard authorizationStatus == .notDetermined else {
            return Self.canDeliverAlerts(authorizationStatus)
        }

        let granted = (try? await UNUserNotificationCenter.current()
            .requestAuthorization(options: [.alert, .sound, .badge])) ?? false
        Log.info("Notification authorization requested, granted: \(granted)")

        await refreshStatus()
        return Self.canDeliverAlerts(authorizationStatus)
    }

    /// Open this app's page in Settings so a denied user can turn alerts on.
    func openSystemSettings() {
        guard let url = URL(string: UIApplication.openSettingsURLString) else { return }
        UIApplication.shared.open(url)
    }
}
