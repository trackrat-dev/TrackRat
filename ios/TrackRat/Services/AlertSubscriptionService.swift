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

    func addTrainSubscription(dataSource: String, trainId: String, trainName: String, activeDays: Int = 127) {
        let sub = RouteAlertSubscription(
            dataSource: dataSource,
            trainId: trainId,
            trainName: trainName,
            activeDays: activeDays
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

    func updateSubscription(_ updated: RouteAlertSubscription) {
        if let index = subscriptions.firstIndex(where: { $0.id == updated.id }) {
            subscriptions[index] = updated
            saveToDefaults()
        }
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
    var activeDays: Int          // Bitmask: Mon=1..Sun=64, 127=all
    var activeStartMinutes: Int? // Minutes from midnight, nil = all day
    var activeEndMinutes: Int?   // Minutes from midnight, nil = all day
    var timezone: String?        // IANA timezone
    var delayThresholdMinutes: Int?  // nil = system default (15)
    var serviceThresholdPct: Int?    // nil = system default (50)
    var notifyRecovery: Bool
    var digestTimeMinutes: Int?  // Minutes from midnight, nil = disabled
    var includePlannedWork: Bool

    /// Frequency-first systems use service threshold; delay-first use delay threshold.
    static let frequencyFirstSources: Set<String> = ["SUBWAY", "PATH", "PATCO"]

    private enum CodingKeys: String, CodingKey {
        case id, dataSource, lineId, lineName, fromStationCode, toStationCode
        case trainId, trainName, direction, activeDays, activeStartMinutes
        case activeEndMinutes, timezone, delayThresholdMinutes, serviceThresholdPct
        case notifyRecovery, digestTimeMinutes, includePlannedWork
        case weekdaysOnly  // Legacy key for migration
    }

    /// Line-based subscription with direction (terminus station code).
    init(
        dataSource: String, lineId: String, lineName: String, direction: String?,
        activeDays: Int = 127, activeStartMinutes: Int? = nil, activeEndMinutes: Int? = nil,
        timezone: String? = nil, delayThresholdMinutes: Int? = nil, serviceThresholdPct: Int? = nil,
        notifyRecovery: Bool = false, digestTimeMinutes: Int? = nil,
        includePlannedWork: Bool = false
    ) {
        self.id = UUID()
        self.dataSource = dataSource
        self.lineId = lineId
        self.lineName = lineName
        self.fromStationCode = nil
        self.toStationCode = nil
        self.trainId = nil
        self.trainName = nil
        self.direction = direction
        self.activeDays = activeDays
        self.activeStartMinutes = activeStartMinutes
        self.activeEndMinutes = activeEndMinutes
        self.timezone = timezone
        self.delayThresholdMinutes = delayThresholdMinutes
        self.serviceThresholdPct = serviceThresholdPct
        self.notifyRecovery = notifyRecovery
        self.digestTimeMinutes = digestTimeMinutes
        self.includePlannedWork = includePlannedWork
    }

    /// Station-pair subscription.
    init(
        dataSource: String, fromStationCode: String, toStationCode: String,
        activeDays: Int = 127, activeStartMinutes: Int? = nil, activeEndMinutes: Int? = nil,
        timezone: String? = nil, delayThresholdMinutes: Int? = nil, serviceThresholdPct: Int? = nil,
        notifyRecovery: Bool = false, digestTimeMinutes: Int? = nil
    ) {
        self.id = UUID()
        self.dataSource = dataSource
        self.lineId = nil
        self.lineName = nil
        self.fromStationCode = fromStationCode
        self.toStationCode = toStationCode
        self.trainId = nil
        self.trainName = nil
        self.direction = nil
        self.activeDays = activeDays
        self.activeStartMinutes = activeStartMinutes
        self.activeEndMinutes = activeEndMinutes
        self.timezone = timezone
        self.delayThresholdMinutes = delayThresholdMinutes
        self.serviceThresholdPct = serviceThresholdPct
        self.notifyRecovery = notifyRecovery
        self.digestTimeMinutes = digestTimeMinutes
        self.includePlannedWork = false
    }

    /// Train-specific subscription.
    init(
        dataSource: String, trainId: String, trainName: String,
        activeDays: Int = 127, activeStartMinutes: Int? = nil, activeEndMinutes: Int? = nil,
        timezone: String? = nil, delayThresholdMinutes: Int? = nil, serviceThresholdPct: Int? = nil,
        notifyRecovery: Bool = false, digestTimeMinutes: Int? = nil
    ) {
        self.id = UUID()
        self.dataSource = dataSource
        self.lineId = nil
        self.lineName = nil
        self.fromStationCode = nil
        self.toStationCode = nil
        self.trainId = trainId
        self.trainName = trainName
        self.direction = nil
        self.activeDays = activeDays
        self.activeStartMinutes = activeStartMinutes
        self.activeEndMinutes = activeEndMinutes
        self.timezone = timezone
        self.delayThresholdMinutes = delayThresholdMinutes
        self.serviceThresholdPct = serviceThresholdPct
        self.notifyRecovery = notifyRecovery
        self.digestTimeMinutes = digestTimeMinutes
        self.includePlannedWork = false
    }

    /// Backward-compatible decoding: new fields default to sensible values if missing.
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
        // Migrate old weekdaysOnly=true → activeDays=31 (Mon-Fri)
        let oldWeekdaysOnly = try container.decodeIfPresent(Bool.self, forKey: .weekdaysOnly) ?? false
        let decodedActiveDays = try container.decodeIfPresent(Int.self, forKey: .activeDays)
        if decodedActiveDays != nil {
            activeDays = decodedActiveDays!
        } else {
            activeDays = oldWeekdaysOnly ? 31 : 127
        }
        activeStartMinutes = try container.decodeIfPresent(Int.self, forKey: .activeStartMinutes)
        activeEndMinutes = try container.decodeIfPresent(Int.self, forKey: .activeEndMinutes)
        timezone = try container.decodeIfPresent(String.self, forKey: .timezone)
        delayThresholdMinutes = try container.decodeIfPresent(Int.self, forKey: .delayThresholdMinutes)
        serviceThresholdPct = try container.decodeIfPresent(Int.self, forKey: .serviceThresholdPct)
        notifyRecovery = try container.decodeIfPresent(Bool.self, forKey: .notifyRecovery) ?? false
        digestTimeMinutes = try container.decodeIfPresent(Int.self, forKey: .digestTimeMinutes)
        includePlannedWork = try container.decodeIfPresent(Bool.self, forKey: .includePlannedWork) ?? false
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(dataSource, forKey: .dataSource)
        try container.encodeIfPresent(lineId, forKey: .lineId)
        try container.encodeIfPresent(lineName, forKey: .lineName)
        try container.encodeIfPresent(fromStationCode, forKey: .fromStationCode)
        try container.encodeIfPresent(toStationCode, forKey: .toStationCode)
        try container.encodeIfPresent(trainId, forKey: .trainId)
        try container.encodeIfPresent(trainName, forKey: .trainName)
        try container.encodeIfPresent(direction, forKey: .direction)
        try container.encode(activeDays, forKey: .activeDays)
        try container.encodeIfPresent(activeStartMinutes, forKey: .activeStartMinutes)
        try container.encodeIfPresent(activeEndMinutes, forKey: .activeEndMinutes)
        try container.encodeIfPresent(timezone, forKey: .timezone)
        try container.encodeIfPresent(delayThresholdMinutes, forKey: .delayThresholdMinutes)
        try container.encodeIfPresent(serviceThresholdPct, forKey: .serviceThresholdPct)
        try container.encode(notifyRecovery, forKey: .notifyRecovery)
        try container.encodeIfPresent(digestTimeMinutes, forKey: .digestTimeMinutes)
        try container.encode(includePlannedWork, forKey: .includePlannedWork)
        // weekdaysOnly intentionally not encoded — legacy decode-only key
    }
}
