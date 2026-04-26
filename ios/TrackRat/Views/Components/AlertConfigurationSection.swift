import SwiftUI

// MARK: - Directional Alert Configuration Sheet

/// Identifiable wrapper for presenting a directional sheet via `.sheet(item:)`.
struct DirectionalSheetData: Identifiable {
    let id = UUID()
    let directions: [DirectionDraft]
}

/// A direction draft for use in the directional configuration sheet.
struct DirectionDraft {
    let label: String
    var subscription: RouteAlertSubscription
    let alreadySubscribed: Bool
}

// MARK: - Line Discovery for Alert Configuration

/// Lightweight model that discovers available systems/lines for a station pair.
@MainActor
class LineDiscoveryModel: ObservableObject {
    @Published var discoveredSystems: [RouteSystemInfo] = []
    @Published var enabledLineIds: Set<String> = []

    func discover(from: String, to: String) async {
        let fromSystems = Stations.systemsForStation(from)
        let toSystems = Stations.systemsForStation(to)
        let commonSystems = fromSystems.intersection(toSystems).sorted { $0.displayName < $1.displayName }

        guard !commonSystems.isEmpty else { return }

        // Snapshot the user-facing selection up front so we can detect mid-flight edits.
        // Late preference writes must not stomp on toggles the user makes while the API is in-flight.
        let initialEnabledLineIds = enabledLineIds

        do {
            let trains = try await APIService.shared.searchTrains(
                fromStationCode: from,
                toStationCode: to,
                dataSources: Set(commonSystems)
            )

            var linesBySystem: [String: [RouteLineInfo]] = [:]
            var seenLines = Set<String>()

            for train in trains {
                let lineId = "\(train.dataSource):\(train.line.code)"
                guard !seenLines.contains(lineId) else { continue }
                seenLines.insert(lineId)

                let info = RouteLineInfo(
                    dataSource: train.dataSource,
                    lineCode: train.line.code,
                    lineName: train.line.name,
                    lineColor: train.line.color
                )
                linesBySystem[train.dataSource, default: []].append(info)
            }

            var systems: [RouteSystemInfo] = []
            for system in commonSystems {
                let lines = linesBySystem[system.rawValue] ?? []
                if !lines.isEmpty {
                    systems.append(RouteSystemInfo(system: system, lines: lines.sorted { $0.lineCode < $1.lineCode }))
                }
            }

            discoveredSystems = systems
        } catch {
            // Silently fail — line selection simply won't appear
        }

        // Load saved preference. Only apply it if the user hasn't already toggled lines while we waited.
        let deviceId = AlertSubscriptionService.shared.deviceId
        do {
            let pref = try await APIService.shared.fetchRoutePreference(
                deviceId: deviceId, from: from, to: to
            )
            var lineIds = Set<String>()
            for (system, lines) in pref.enabledSystems {
                if lines.isEmpty {
                    for discoveredSystem in discoveredSystems where discoveredSystem.system.rawValue == system {
                        for line in discoveredSystem.lines {
                            lineIds.insert(line.id)
                        }
                    }
                } else {
                    for lineCode in lines {
                        lineIds.insert("\(system):\(lineCode)")
                    }
                }
            }
            if enabledLineIds == initialEnabledLineIds {
                enabledLineIds = lineIds
            }
        } catch {
            // No saved preference — leave whatever the user has, including the "all enabled" default (empty set).
        }
    }

    func savePreference(from: String, to: String) async {
        let deviceId = AlertSubscriptionService.shared.deviceId
        var systems: [String: [String]] = [:]
        if enabledLineIds.isEmpty {
            for system in discoveredSystems {
                systems[system.system.rawValue] = []
            }
        } else {
            for lineId in enabledLineIds {
                let parts = lineId.split(separator: ":")
                guard parts.count == 2 else { continue }
                let system = String(parts[0])
                let lineCode = String(parts[1])
                systems[system, default: []].append(lineCode)
            }
        }
        do {
            try await APIService.shared.saveRoutePreference(
                deviceId: deviceId, from: from, to: to, enabledSystems: systems
            )
        } catch {
            print("⚠️ Failed to save route preference: \(error.localizedDescription)")
        }
    }
}

/// Sheet that shows both directions of a route with independent alert settings.
/// Each direction is shown inline with its own configuration section.
/// For free users, only the first direction is configurable; the second shows a Pro upsell.
struct DirectionalAlertConfigurationSheet: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var subscriptionService = SubscriptionService.shared
    @StateObject private var lineDiscovery = LineDiscoveryModel()
    @State private var directions: [DirectionDraft]
    @State private var showingPaywall = false
    /// Snapshot of `isPro` taken on first appearance. Stabilizes the i>0 branch against transient
    /// StoreKit refreshes (e.g., scenePhase=.active triggers refreshOnForeground which can briefly
    /// reset subscriptionStatus to .notSubscribed). Only upgrades (false→true) are honored so a
    /// mid-flow paywall purchase still unlocks the second direction.
    @State private var isProSticky: Bool? = nil
    private let onSave: ([RouteAlertSubscription]) -> Void

    init(directions: [DirectionDraft], onSave: @escaping ([RouteAlertSubscription]) -> Void) {
        _directions = State(initialValue: directions)
        self.onSave = onSave
    }

    private var effectiveIsPro: Bool {
        isProSticky ?? subscriptionService.isPro
    }

    /// Station pair from the first non-subscribed direction (for line discovery).
    private var stationPair: (from: String, to: String)? {
        for dir in directions where !dir.alreadySubscribed {
            if let from = dir.subscription.fromStationCode,
               let to = dir.subscription.toStationCode {
                return (from, to)
            }
        }
        return nil
    }

    /// Hashable key for `.task(id:)` so discovery only re-fires when the station pair changes.
    private var stationPairKey: String {
        guard let pair = stationPair else { return "" }
        return "\(pair.from)|\(pair.to)"
    }

    private var canSave: Bool {
        directions.contains { !$0.alreadySubscribed && $0.subscription.activeDays != 0 }
    }

    @ViewBuilder
    var body: some View {
        if directions.isEmpty {
            Color.clear
        } else {
            NavigationStack {
                ScrollView {
                    VStack(spacing: 20) {
                        // Line Selection (shown when multiple systems/lines serve this route)
                        LineSelectionView(
                            systems: lineDiscovery.discoveredSystems,
                            enabledLineIds: $lineDiscovery.enabledLineIds
                        )

                        ForEach(0..<directions.count, id: \.self) { i in
                            if directions[i].alreadySubscribed {
                                alreadySubscribedBanner(label: directions[i].label)
                            } else if i > 0 && !effectiveIsPro {
                                proLockedDirectionBanner(label: directions[i].label)
                            } else {
                                AlertConfigurationSection(
                                    subscription: $directions[i].subscription,
                                    headerText: directions[i].label
                                )
                            }
                        }
                    }
                    .padding()
                }
                .background(Color(.systemGroupedBackground))
                .navigationTitle("Customize Alert")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .topBarLeading) {
                        Button("Cancel") { dismiss() }
                            .foregroundColor(.orange)
                    }
                    ToolbarItem(placement: .topBarTrailing) {
                        Button("Save") {
                            let enabledSubs = directions.enumerated()
                                .filter { index, draft in
                                    !draft.alreadySubscribed
                                    && draft.subscription.activeDays != 0
                                    && (index == 0 || effectiveIsPro)
                                }
                                .map(\.element.subscription)
                            onSave(enabledSubs)
                            // Save line selection preference
                            if let pair = stationPair {
                                Task { await lineDiscovery.savePreference(from: pair.from, to: pair.to) }
                            }
                            dismiss()
                        }
                        .foregroundColor(.orange)
                        .fontWeight(.semibold)
                        .disabled(!canSave)
                    }
                }
                .onAppear {
                    if isProSticky == nil {
                        isProSticky = subscriptionService.isPro
                    }
                }
                .onChange(of: subscriptionService.isPro) { _, newValue in
                    if newValue {
                        isProSticky = true
                    }
                }
                .task(id: stationPairKey) {
                    if let pair = stationPair {
                        await lineDiscovery.discover(from: pair.from, to: pair.to)
                    }
                }
            }
            .preferredColorScheme(.dark)
            .sheet(isPresented: $showingPaywall) {
                PaywallView(context: .routeAlerts)
            }
        }
    }

    // MARK: - Already Subscribed Banner

    private func alreadySubscribedBanner(label: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label)
                .font(.headline)
            HStack {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.green)
                Text("Already subscribed")
                    .foregroundColor(.white.opacity(0.7))
            }
            .padding()
            .frame(maxWidth: .infinity)
            .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
        }
    }

    // MARK: - Pro Locked Direction Banner

    private func proLockedDirectionBanner(label: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label)
                .font(.headline)
            Button {
                showingPaywall = true
                UIImpactFeedbackGenerator(style: .medium).impactOccurred()
            } label: {
                HStack {
                    Image(systemName: "lock.fill")
                        .foregroundColor(.orange)
                    Text("Start a free trial and upgrade to Pro to add more than one route alert")
                        .foregroundColor(.white.opacity(0.7))
                    Spacer()
                    Text("PRO")
                        .font(.caption2.bold())
                        .foregroundColor(.white)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Capsule().fill(.orange))
                }
                .padding()
                .frame(maxWidth: .infinity)
                .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
            }
            .buttonStyle(.plain)
        }
    }
}

// MARK: - Alert Sensitivity

/// Tri-state alert sensitivity for cancellation and delay/fewer-trains controls.
enum AlertSensitivity: String, CaseIterable {
    case none = "None"
    case severeOnly = "Severe"
    case all = "All"
}

// MARK: - Time Preset

/// Quick time window presets for common commute patterns.
enum TimePreset: String, CaseIterable {
    case anyTime = "Anytime"
    case custom = "Custom"
}

// MARK: - Alert Configuration Section

/// Unified alert settings card: day/time selection, alert types, recovery, planned work, and daily status summary.
struct AlertConfigurationSection: View {
    @Binding var subscription: RouteAlertSubscription
    var headerText: String = "Alert Settings"
    @State private var showCustomDays = false
    @State private var showCustomTime = false

    private static let presetBitmasks: Set<Int> = [0, 127]

    private var isCustomDays: Bool {
        !Self.presetBitmasks.contains(subscription.activeDays)
    }

    private var isFrequencyBased: Bool {
        RouteAlertSubscription.frequencyFirstSources.contains(subscription.dataSource)
    }

    /// Systems that support planned work notifications.
    private static let plannedWorkSystems: Set<String> = ["SUBWAY", "LIRR", "MNR", "NJT"]

    private var showPlannedWork: Bool {
        (subscription.isSystemWide || subscription.lineId != nil || subscription.fromStationCode != nil)
            && Self.plannedWorkSystems.contains(subscription.dataSource)
    }

    private var activeTimePreset: TimePreset {
        guard subscription.activeStartMinutes != nil,
              subscription.activeEndMinutes != nil else {
            return .anyTime
        }
        return .custom
    }

    private var hasDaysSelected: Bool {
        subscription.activeDays != 0
    }

    var body: some View {
        configCard {
            Text(headerText)
                .font(.headline)

                // Day selection (top — controls subscribe/unsubscribe)
                Text("Send me notifications...")
                    .font(.subheadline)
                    .foregroundColor(.white.opacity(0.6))
                dayPresetRow

                if isCustomDays || showCustomDays {
                    dayGrid
                        .transition(.opacity.combined(with: .move(edge: .top)))
                }

                // Time window presets (directly below day picker)
                timePresetRow

                if activeTimePreset == .custom || showCustomTime {
                    customTimeWindow
                        .transition(.opacity.combined(with: .move(edge: .top)))
                }

                if hasDaysSelected {
                    Divider().opacity(0.3)

                    // Alert types
                    Text("When there are...")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.6))
                    sensitivityRow(label: "Cancellations", sensitivity: cancellationSensitivity)
                    sensitivityRow(
                        label: isFrequencyBased ? "Fewer Trains" : "Delays",
                        sensitivity: delaySensitivity
                    )

                    // Service alerts (MTA + NJT systems)
                    if showPlannedWork {
                        Toggle(isOn: $subscription.includePlannedWork) {
                            Text("Service Alerts")
                        }
                        .tint(.orange)
                    }

                    // Recovery & daily summary
                    if subscription.notifyCancellation || subscription.notifyDelay {
                        Text("Also...")
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.6))
                        Toggle(isOn: $subscription.notifyRecovery) {
                            Text("Notify on Recovery")
                        }
                        .tint(.orange)
                    }

                    // Daily status summary
                    Toggle(isOn: digestEnabled) {
                        Text("Send a Daily Status Summary")
                    }
                    .tint(.orange)

                    if subscription.digestTimeMinutes != nil {
                        HStack {
                            Text("Digest time")
                                .foregroundColor(.white.opacity(0.6))
                            Spacer()
                            minuteOfDayPicker(selection: Binding(
                                get: { subscription.digestTimeMinutes ?? 420 },
                                set: { subscription.digestTimeMinutes = $0 }
                            ))
                        }
                    }
                }
            }
        }

    // MARK: - Time Presets

    private var timePresetRow: some View {
        HStack(spacing: 8) {
            timePresetButton(.anyTime)

            Button {
                withAnimation(.easeInOut(duration: 0.2)) {
                    if activeTimePreset != .custom {
                        // Switching to custom: set a reasonable default if no window exists
                        if subscription.activeStartMinutes == nil {
                            subscription.activeStartMinutes = 360   // 6:00 AM
                            subscription.activeEndMinutes = 1200     // 8:00 PM
                            subscription.timezone = TimeZone.current.identifier
                        }
                    }
                    showCustomTime.toggle()
                }
            } label: {
                Text("Custom")
                    .font(.caption)
                    .fontWeight(activeTimePreset == .custom ? .bold : .regular)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(
                        Capsule().fill(activeTimePreset == .custom ? Color.orange : Color.white.opacity(0.1))
                    )
                    .foregroundColor(activeTimePreset == .custom ? .black : .white)
            }
            .buttonStyle(.plain)
        }
    }

    private func timePresetButton(_ preset: TimePreset) -> some View {
        let isSelected = activeTimePreset == preset
        return Button {
            withAnimation(.easeInOut(duration: 0.2)) {
                switch preset {
                case .anyTime:
                    subscription.activeStartMinutes = nil
                    subscription.activeEndMinutes = nil
                    if subscription.digestTimeMinutes == nil {
                        subscription.timezone = nil
                    }
                case .custom:
                    break
                }
                showCustomTime = false
            }
        } label: {
            Text(preset.rawValue)
                .font(.caption)
                .fontWeight(isSelected ? .bold : .regular)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(
                    Capsule().fill(isSelected ? Color.orange : Color.white.opacity(0.1))
                )
                .foregroundColor(isSelected ? .black : .white)
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder
    private var customTimeWindow: some View {
        HStack {
            Text("From")
                .foregroundColor(.white.opacity(0.6))
            Spacer()
            minuteOfDayPicker(selection: Binding(
                get: { subscription.activeStartMinutes ?? 360 },
                set: { subscription.activeStartMinutes = $0 }
            ))
        }
        HStack {
            Text("To")
                .foregroundColor(.white.opacity(0.6))
            Spacer()
            minuteOfDayPicker(selection: Binding(
                get: { subscription.activeEndMinutes ?? 1200 },
                set: { subscription.activeEndMinutes = $0 }
            ))
        }
    }

    // MARK: - Digest

    private var digestEnabled: Binding<Bool> {
        Binding(
            get: { subscription.digestTimeMinutes != nil },
            set: { enabled in
                if enabled {
                    subscription.digestTimeMinutes = 420  // 7:00 AM
                    if subscription.timezone == nil {
                        subscription.timezone = TimeZone.current.identifier
                    }
                } else {
                    subscription.digestTimeMinutes = nil
                }
            }
        )
    }

    // MARK: - Sensitivity Rows

    private func sensitivityRow(label: String, sensitivity: Binding<AlertSensitivity>) -> some View {
        HStack {
            Text(label)
            Spacer()
            Picker("", selection: sensitivity) {
                ForEach(AlertSensitivity.allCases, id: \.self) { level in
                    Text(level.rawValue).tag(level)
                }
            }
            .pickerStyle(.segmented)
            .frame(width: 180)
        }
    }

    // MARK: - Cancellation Sensitivity Binding

    private var cancellationSensitivity: Binding<AlertSensitivity> {
        Binding(
            get: {
                guard subscription.notifyCancellation else { return .none }
                switch subscription.cancellationThresholdPct {
                case 50: return .severeOnly
                default: return .all
                }
            },
            set: { level in
                switch level {
                case .none:
                    subscription.notifyCancellation = false
                    subscription.cancellationThresholdPct = nil
                case .severeOnly:
                    subscription.notifyCancellation = true
                    subscription.cancellationThresholdPct = 50
                case .all:
                    subscription.notifyCancellation = true
                    subscription.cancellationThresholdPct = 90
                }
            }
        )
    }

    // MARK: - Delay / Fewer Trains Sensitivity Binding

    private var delaySensitivity: Binding<AlertSensitivity> {
        Binding(
            get: {
                guard subscription.notifyDelay else { return .none }
                if isFrequencyBased {
                    switch subscription.serviceThresholdPct {
                    case 50: return .severeOnly
                    default: return .all
                    }
                } else {
                    switch subscription.delayThresholdMinutes {
                    case 20: return .severeOnly
                    default: return .all
                    }
                }
            },
            set: { level in
                switch level {
                case .none:
                    subscription.notifyDelay = false
                    if isFrequencyBased {
                        subscription.serviceThresholdPct = nil
                    } else {
                        subscription.delayThresholdMinutes = nil
                    }
                case .severeOnly:
                    subscription.notifyDelay = true
                    if isFrequencyBased {
                        subscription.serviceThresholdPct = 50
                    } else {
                        subscription.delayThresholdMinutes = 20
                    }
                case .all:
                    subscription.notifyDelay = true
                    if isFrequencyBased {
                        subscription.serviceThresholdPct = 90
                    } else {
                        subscription.delayThresholdMinutes = 5
                    }
                }
            }
        )
    }

    // MARK: - Days

    private var dayPresetRow: some View {
        HStack(spacing: 8) {
            presetButton("None", bitmask: 0)
            presetButton("Every Day", bitmask: 127)

            Button {
                withAnimation(.easeInOut(duration: 0.2)) {
                    if !isCustomDays {
                        // Switching to custom: if currently None, start with weekdays
                        if subscription.activeDays == 0 {
                            subscription.activeDays = 31
                        }
                    }
                    showCustomDays.toggle()
                }
            } label: {
                Text("Custom")
                    .font(.caption)
                    .fontWeight(isCustomDays ? .bold : .regular)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(
                        Capsule().fill(isCustomDays ? Color.orange : Color.white.opacity(0.1))
                    )
                    .foregroundColor(isCustomDays ? .black : .white)
            }
            .buttonStyle(.plain)
        }
    }

    private func presetButton(_ label: String, bitmask: Int) -> some View {
        Button {
            withAnimation(.easeInOut(duration: 0.2)) {
                subscription.activeDays = bitmask
                showCustomDays = false
            }
        } label: {
            Text(label)
                .font(.caption)
                .fontWeight(subscription.activeDays == bitmask ? .bold : .regular)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(
                    Capsule().fill(subscription.activeDays == bitmask ? Color.orange : Color.white.opacity(0.1))
                )
                .foregroundColor(subscription.activeDays == bitmask ? .black : .white)
        }
        .buttonStyle(.plain)
    }

    private var dayGrid: some View {
        let dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return HStack(spacing: 6) {
            ForEach(0..<7, id: \.self) { index in
                let bit = 1 << index
                let isOn = subscription.activeDays & bit != 0
                Button {
                    if isOn {
                        subscription.activeDays &= ~bit
                    } else {
                        subscription.activeDays |= bit
                    }
                } label: {
                    Text(dayNames[index])
                        .font(.caption2)
                        .fontWeight(.medium)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                        .background(
                            RoundedRectangle(cornerRadius: 8)
                                .fill(isOn ? Color.orange : Color.white.opacity(0.08))
                        )
                        .foregroundColor(isOn ? .black : .white.opacity(0.6))
                }
                .buttonStyle(.plain)
            }
        }
    }

    // MARK: - Card Helper

    private func configCard<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            content()
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
    }
}

// MARK: - Shared Helpers

/// Time-of-day picker that converts between minutes-from-midnight and a Date for DatePicker.
func minuteOfDayPicker(selection: Binding<Int>) -> some View {
    let date = Binding<Date>(
        get: {
            Calendar.current.startOfDay(for: Date())
                .addingTimeInterval(TimeInterval(selection.wrappedValue * 60))
        },
        set: { newDate in
            let comps = Calendar.current.dateComponents([.hour, .minute], from: newDate)
            selection.wrappedValue = (comps.hour ?? 0) * 60 + (comps.minute ?? 0)
        }
    )
    return DatePicker("", selection: date, displayedComponents: .hourAndMinute)
        .labelsHidden()
}
