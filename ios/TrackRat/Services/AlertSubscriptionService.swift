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

    /// Add fully-configured subscriptions, deduplicating against existing ones.
    /// Supports line (lineId+direction), station-pair (from+to), and train (trainId) subscriptions.
    func addSubscriptions(_ subs: [RouteAlertSubscription]) {
        for sub in subs {
            let isDuplicate: Bool
            if let lineId = sub.lineId, let direction = sub.direction {
                isDuplicate = subscriptions.contains {
                    $0.lineId == lineId && $0.dataSource == sub.dataSource && $0.direction == direction
                }
            } else if let from = sub.fromStationCode, let to = sub.toStationCode {
                isDuplicate = subscriptions.contains {
                    $0.fromStationCode == from && $0.toStationCode == to && $0.dataSource == sub.dataSource
                }
            } else if let trainId = sub.trainId {
                isDuplicate = subscriptions.contains {
                    $0.trainId == trainId && $0.dataSource == sub.dataSource
                }
            } else {
                isDuplicate = false
            }
            if !isDuplicate {
                subscriptions.append(sub)
            }
        }
        saveToDefaults()
    }

    /// Find subscriptions matching a route context (by dataSource + station codes or lineId).
    func subscriptions(for context: RouteStatusContext) -> [RouteAlertSubscription] {
        subscriptions.filter { sub in
            guard sub.dataSource == context.dataSource else { return false }
            // Match line subscriptions
            if let lineId = sub.lineId, lineId == context.lineId {
                return true
            }
            // Match station-pair subscriptions (either direction)
            if let from = sub.fromStationCode, let to = sub.toStationCode,
               let ctxFrom = context.fromStationCode, let ctxTo = context.toStationCode {
                return (from == ctxFrom && to == ctxTo) || (from == ctxTo && to == ctxFrom)
            }
            return false
        }
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

    private let chatTokenKey = "AlertSubscription.chatToken"

    /// The chat bearer token returned by the server during device registration.
    var chatToken: String? {
        UserDefaults.standard.string(forKey: chatTokenKey)
    }

    func syncWithBackend(apnsToken: String) async {
        do {
            let response = try await APIService.shared.registerDevice(deviceId: deviceId, apnsToken: apnsToken)
            if let token = response.chat_token {
                UserDefaults.standard.set(token, forKey: chatTokenKey)
            }
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
    var cancellationThresholdPct: Int? // nil = system default
    var notifyCancellation: Bool
    var notifyDelay: Bool
    var notifyRecovery: Bool
    var digestTimeMinutes: Int?  // Minutes from midnight, nil = disabled
    var includePlannedWork: Bool

    /// Frequency-first systems use service threshold; delay-first use delay threshold.
    static let frequencyFirstSources: Set<String> = ["SUBWAY", "PATH", "PATCO"]

    /// Copy mutable alert settings from `source` onto `target`, preserving target's identity fields.
    static func copySettings(from source: RouteAlertSubscription, to target: RouteAlertSubscription) -> RouteAlertSubscription {
        var result = target
        result.activeDays = source.activeDays
        result.activeStartMinutes = source.activeStartMinutes
        result.activeEndMinutes = source.activeEndMinutes
        result.timezone = source.timezone
        result.delayThresholdMinutes = source.delayThresholdMinutes
        result.serviceThresholdPct = source.serviceThresholdPct
        result.cancellationThresholdPct = source.cancellationThresholdPct
        result.notifyCancellation = source.notifyCancellation
        result.notifyDelay = source.notifyDelay
        result.notifyRecovery = source.notifyRecovery
        result.digestTimeMinutes = source.digestTimeMinutes
        result.includePlannedWork = source.includePlannedWork
        return result
    }

    private enum CodingKeys: String, CodingKey {
        case id, dataSource, lineId, lineName, fromStationCode, toStationCode
        case trainId, trainName, direction, activeDays, activeStartMinutes
        case activeEndMinutes, timezone, delayThresholdMinutes, serviceThresholdPct
        case cancellationThresholdPct, notifyCancellation, notifyDelay
        case notifyRecovery, digestTimeMinutes, includePlannedWork
        case weekdaysOnly  // Legacy key for migration
    }

    /// Line-based subscription with direction (terminus station code).
    init(
        dataSource: String, lineId: String, lineName: String, direction: String?,
        activeDays: Int = 127, activeStartMinutes: Int? = nil, activeEndMinutes: Int? = nil,
        timezone: String? = nil, delayThresholdMinutes: Int? = nil, serviceThresholdPct: Int? = nil,
        cancellationThresholdPct: Int? = nil,
        notifyCancellation: Bool = true, notifyDelay: Bool = true,
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
        self.cancellationThresholdPct = cancellationThresholdPct
        self.notifyCancellation = notifyCancellation
        self.notifyDelay = notifyDelay
        self.notifyRecovery = notifyRecovery
        self.digestTimeMinutes = digestTimeMinutes
        self.includePlannedWork = includePlannedWork
    }

    /// Station-pair subscription.
    init(
        dataSource: String, fromStationCode: String, toStationCode: String,
        activeDays: Int = 127, activeStartMinutes: Int? = nil, activeEndMinutes: Int? = nil,
        timezone: String? = nil, delayThresholdMinutes: Int? = nil, serviceThresholdPct: Int? = nil,
        cancellationThresholdPct: Int? = nil,
        notifyCancellation: Bool = true, notifyDelay: Bool = true,
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
        self.cancellationThresholdPct = cancellationThresholdPct
        self.notifyCancellation = notifyCancellation
        self.notifyDelay = notifyDelay
        self.notifyRecovery = notifyRecovery
        self.digestTimeMinutes = digestTimeMinutes
        self.includePlannedWork = false
    }

    /// Train-specific subscription.
    init(
        dataSource: String, trainId: String, trainName: String,
        activeDays: Int = 127, activeStartMinutes: Int? = nil, activeEndMinutes: Int? = nil,
        timezone: String? = nil, delayThresholdMinutes: Int? = nil, serviceThresholdPct: Int? = nil,
        cancellationThresholdPct: Int? = nil,
        notifyCancellation: Bool = true, notifyDelay: Bool = true,
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
        self.cancellationThresholdPct = cancellationThresholdPct
        self.notifyCancellation = notifyCancellation
        self.notifyDelay = notifyDelay
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
        cancellationThresholdPct = try container.decodeIfPresent(Int.self, forKey: .cancellationThresholdPct)
        notifyCancellation = try container.decodeIfPresent(Bool.self, forKey: .notifyCancellation) ?? true
        notifyDelay = try container.decodeIfPresent(Bool.self, forKey: .notifyDelay) ?? true
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
        try container.encodeIfPresent(cancellationThresholdPct, forKey: .cancellationThresholdPct)
        try container.encode(notifyCancellation, forKey: .notifyCancellation)
        try container.encode(notifyDelay, forKey: .notifyDelay)
        try container.encode(notifyRecovery, forKey: .notifyRecovery)
        try container.encodeIfPresent(digestTimeMinutes, forKey: .digestTimeMinutes)
        try container.encode(includePlannedWork, forKey: .includePlannedWork)
        // weekdaysOnly intentionally not encoded — legacy decode-only key
    }
}
