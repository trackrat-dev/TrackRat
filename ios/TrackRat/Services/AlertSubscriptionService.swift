import Foundation

/// Manages route alert subscriptions for delay/cancellation push notifications.
final class AlertSubscriptionService: ObservableObject {
    static let shared = AlertSubscriptionService()

    @Published var subscriptions: [RouteAlertSubscription] = []

    private let deviceIdKey = "AlertSubscription.deviceId"
    private let subscriptionsKey = "AlertSubscription.subscriptions"

    /// Stable device identifier for this installation.
    var deviceId: String {
        if let existing = UserDefaults.standard.string(forKey: deviceIdKey) {
            return existing
        }
        let new = UUID().uuidString
        UserDefaults.standard.set(new, forKey: deviceIdKey)
        return new
    }

    private init() {
        loadFromDefaults()
    }

    // MARK: - Mutation

    func addLineSubscription(dataSource: String, lineId: String, lineName: String) {
        let sub = RouteAlertSubscription(
            dataSource: dataSource,
            lineId: lineId,
            lineName: lineName
        )
        guard !subscriptions.contains(where: { $0.lineId == lineId && $0.dataSource == dataSource }) else { return }
        subscriptions.append(sub)
        saveToDefaults()
    }

    func addStationPairSubscription(dataSource: String, fromStationCode: String, toStationCode: String) {
        let sub = RouteAlertSubscription(
            dataSource: dataSource,
            fromStationCode: fromStationCode,
            toStationCode: toStationCode
        )
        guard !subscriptions.contains(where: {
            $0.fromStationCode == fromStationCode &&
            $0.toStationCode == toStationCode &&
            $0.dataSource == dataSource
        }) else { return }
        subscriptions.append(sub)
        saveToDefaults()
    }

    func removeSubscription(_ sub: RouteAlertSubscription) {
        subscriptions.removeAll { $0.id == sub.id }
        saveToDefaults()
    }

    // MARK: - Backend Sync

    func syncWithBackend(apnsToken: String) async {
        do {
            try await APIService.shared.registerDevice(deviceId: deviceId, apnsToken: apnsToken)
            try await APIService.shared.syncAlertSubscriptions(deviceId: deviceId, subscriptions: subscriptions)
        } catch {
            print("Alert subscription sync failed: \(error)")
        }
    }

    // MARK: - Persistence

    private func loadFromDefaults() {
        guard let data = UserDefaults.standard.data(forKey: subscriptionsKey) else { return }
        if let decoded = try? JSONDecoder().decode([RouteAlertSubscription].self, from: data) {
            subscriptions = decoded
        }
    }

    private func saveToDefaults() {
        if let data = try? JSONEncoder().encode(subscriptions) {
            UserDefaults.standard.set(data, forKey: subscriptionsKey)
        }
    }
}

// MARK: - Model

struct RouteAlertSubscription: Codable, Identifiable, Equatable {
    let id: UUID
    let dataSource: String
    let lineId: String?
    let lineName: String?
    let fromStationCode: String?
    let toStationCode: String?

    /// Line-based subscription.
    init(dataSource: String, lineId: String, lineName: String) {
        self.id = UUID()
        self.dataSource = dataSource
        self.lineId = lineId
        self.lineName = lineName
        self.fromStationCode = nil
        self.toStationCode = nil
    }

    /// Station-pair subscription.
    init(dataSource: String, fromStationCode: String, toStationCode: String) {
        self.id = UUID()
        self.dataSource = dataSource
        self.lineId = nil
        self.lineName = nil
        self.fromStationCode = fromStationCode
        self.toStationCode = toStationCode
    }
}
