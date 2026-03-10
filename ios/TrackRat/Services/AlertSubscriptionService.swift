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

    /// Add two line subscriptions (one per direction) for the given route.
    func addLineSubscriptions(dataSource: String, lineId: String, lineName: String, route: RouteLine, includePlannedWork: Bool = false) {
        guard let first = route.stationCodes.first,
              let last = route.stationCodes.last else { return }
        addSingleLineSubscription(dataSource: dataSource, lineId: lineId, lineName: lineName, direction: first, includePlannedWork: includePlannedWork)
        addSingleLineSubscription(dataSource: dataSource, lineId: lineId, lineName: lineName, direction: last, includePlannedWork: includePlannedWork)
    }

    /// Add a single directional line subscription (deduped on lineId + dataSource + direction).
    func addSingleLineSubscription(dataSource: String, lineId: String, lineName: String, direction: String?, includePlannedWork: Bool = false) {
        guard !subscriptions.contains(where: {
            $0.lineId == lineId && $0.dataSource == dataSource && $0.direction == direction
        }) else { return }
        let sub = RouteAlertSubscription(
            dataSource: dataSource,
            lineId: lineId,
            lineName: lineName,
            direction: direction,
            includePlannedWork: includePlannedWork
        )
        subscriptions.append(sub)
        saveToDefaults()
    }

    /// Add station-pair subscriptions for both directions.
    func addStationPairSubscriptions(dataSource: String, fromStationCode: String, toStationCode: String) {
        addSingleStationPairSubscription(dataSource: dataSource, fromStationCode: fromStationCode, toStationCode: toStationCode)
        addSingleStationPairSubscription(dataSource: dataSource, fromStationCode: toStationCode, toStationCode: fromStationCode)
    }

    /// Add a single station-pair subscription (deduped on from + to + dataSource).
    func addSingleStationPairSubscription(dataSource: String, fromStationCode: String, toStationCode: String) {
        guard !subscriptions.contains(where: {
            $0.fromStationCode == fromStationCode &&
            $0.toStationCode == toStationCode &&
            $0.dataSource == dataSource
        }) else { return }
        let sub = RouteAlertSubscription(
            dataSource: dataSource,
            fromStationCode: fromStationCode,
            toStationCode: toStationCode
        )
        subscriptions.append(sub)
        saveToDefaults()
    }

    func addTrainSubscription(dataSource: String, trainId: String, trainName: String, weekdaysOnly: Bool) {
        let sub = RouteAlertSubscription(
            dataSource: dataSource,
            trainId: trainId,
            trainName: trainName,
            weekdaysOnly: weekdaysOnly
        )
        guard !subscriptions.contains(where: {
            $0.trainId == trainId && $0.dataSource == dataSource
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
    let trainId: String?
    let trainName: String?
    let direction: String?
    let weekdaysOnly: Bool
    let includePlannedWork: Bool

    /// Line-based subscription with direction (terminus station code).
    init(dataSource: String, lineId: String, lineName: String, direction: String?, includePlannedWork: Bool = false) {
        self.id = UUID()
        self.dataSource = dataSource
        self.lineId = lineId
        self.lineName = lineName
        self.fromStationCode = nil
        self.toStationCode = nil
        self.trainId = nil
        self.trainName = nil
        self.direction = direction
        self.weekdaysOnly = false
        self.includePlannedWork = includePlannedWork
    }

    /// Station-pair subscription.
    init(dataSource: String, fromStationCode: String, toStationCode: String) {
        self.id = UUID()
        self.dataSource = dataSource
        self.lineId = nil
        self.lineName = nil
        self.fromStationCode = fromStationCode
        self.toStationCode = toStationCode
        self.trainId = nil
        self.trainName = nil
        self.direction = nil
        self.weekdaysOnly = false
        self.includePlannedWork = false
    }

    /// Train-specific subscription.
    init(dataSource: String, trainId: String, trainName: String, weekdaysOnly: Bool) {
        self.id = UUID()
        self.dataSource = dataSource
        self.lineId = nil
        self.lineName = nil
        self.fromStationCode = nil
        self.toStationCode = nil
        self.trainId = trainId
        self.trainName = trainName
        self.direction = nil
        self.weekdaysOnly = weekdaysOnly
        self.includePlannedWork = false
    }

    /// Backward-compatible decoding: new fields default to nil/false if missing.
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(UUID.self, forKey: .id)
        dataSource = try container.decode(String.self, forKey: .dataSource)
        lineId = try container.decodeIfPresent(String.self, forKey: .lineId)
        lineName = try container.decodeIfPresent(String.self, forKey: .lineName)
        fromStationCode = try container.decodeIfPresent(String.self, forKey: .fromStationCode)
        toStationCode = try container.decodeIfPresent(String.self, forKey: .toStationCode)
        trainId = try container.decodeIfPresent(String.self, forKey: .trainId)
        trainName = try container.decodeIfPresent(String.self, forKey: .trainName)
        direction = try container.decodeIfPresent(String.self, forKey: .direction)
        weekdaysOnly = try container.decodeIfPresent(Bool.self, forKey: .weekdaysOnly) ?? false
        includePlannedWork = try container.decodeIfPresent(Bool.self, forKey: .includePlannedWork) ?? false
    }
}
