import SwiftUI

/// Sheet wrapper around AlertConfigurationSection for use during subscription creation.
/// Presents Cancel/Save buttons and only commits changes on explicit Save.
struct AlertConfigurationSheetWrapper: View {
    @Environment(\.dismiss) private var dismiss
    @State private var sub: RouteAlertSubscription
    private let onSave: (RouteAlertSubscription) -> Void

    init(subscription: RouteAlertSubscription, onSave: @escaping (RouteAlertSubscription) -> Void) {
        _sub = State(initialValue: subscription)
        self.onSave = onSave
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 12) {
                    AlertConfigurationSection(subscription: $sub)
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
                        onSave(sub)
                        dismiss()
                    }
                    .foregroundColor(.orange)
                    .fontWeight(.semibold)
                }
            }
        }
        .preferredColorScheme(.dark)
    }
}

// MARK: - Directional Alert Configuration Sheet

/// A direction draft for use in the directional configuration sheet.
struct DirectionDraft {
    let label: String
    var subscription: RouteAlertSubscription
    var enabled: Bool
    let alreadySubscribed: Bool
}

/// Sheet that shows both directions of a route with independent alert settings.
/// Each direction can be enabled/disabled and configured separately.
struct DirectionalAlertConfigurationSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var directions: [DirectionDraft]
    @State private var selectedIndex: Int
    private let onSave: ([RouteAlertSubscription]) -> Void

    init(directions: [DirectionDraft], onSave: @escaping ([RouteAlertSubscription]) -> Void) {
        let firstNew = directions.firstIndex(where: { !$0.alreadySubscribed }) ?? 0
        _directions = State(initialValue: directions)
        _selectedIndex = State(initialValue: firstNew)
        self.onSave = onSave
    }

    private var canSave: Bool {
        directions.contains { $0.enabled && !$0.alreadySubscribed }
    }

    private var currentSubscription: Binding<RouteAlertSubscription> {
        Binding(
            get: { directions[selectedIndex].subscription },
            set: { directions[selectedIndex].subscription = $0 }
        )
    }

    private var currentEnabled: Binding<Bool> {
        Binding(
            get: { directions[selectedIndex].enabled },
            set: { directions[selectedIndex].enabled = $0 }
        )
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 12) {
                    directionPicker

                    if directions[selectedIndex].alreadySubscribed {
                        alreadySubscribedBanner
                    } else {
                        Toggle("Enable this direction", isOn: currentEnabled)
                            .tint(.orange)
                            .padding()
                            .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))

                        if directions[selectedIndex].enabled {
                            copySettingsButton
                            AlertConfigurationSection(subscription: currentSubscription)
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
                        let enabledSubs = directions
                            .filter { $0.enabled && !$0.alreadySubscribed }
                            .map(\.subscription)
                        onSave(enabledSubs)
                        dismiss()
                    }
                    .foregroundColor(.orange)
                    .fontWeight(.semibold)
                    .disabled(!canSave)
                }
            }
        }
        .preferredColorScheme(.dark)
    }

    // MARK: - Direction Picker

    private var directionPicker: some View {
        Picker("Direction", selection: $selectedIndex) {
            ForEach(0..<directions.count, id: \.self) { i in
                Text(directions[i].label).tag(i)
            }
        }
        .pickerStyle(.segmented)
    }

    // MARK: - Already Subscribed Banner

    private var alreadySubscribedBanner: some View {
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

    // MARK: - Copy Settings Button

    @ViewBuilder
    private var copySettingsButton: some View {
        if directions.count == 2 {
            let otherIndex = selectedIndex == 0 ? 1 : 0
            let other = directions[otherIndex]
            if other.enabled && !other.alreadySubscribed {
                Button {
                    directions[selectedIndex].subscription = RouteAlertSubscription.copySettings(
                        from: directions[otherIndex].subscription,
                        to: directions[selectedIndex].subscription
                    )
                } label: {
                    Label("Copy settings from \(directions[otherIndex].label)", systemImage: "doc.on.doc")
                        .font(.caption)
                        .foregroundColor(.orange)
                }
            }
        }
    }
}

// MARK: - Alert Sensitivity

/// Tri-state alert sensitivity for cancellation and delay/reduced-service controls.
enum AlertSensitivity: String, CaseIterable {
    case none = "None"
    case severeOnly = "Severe"
    case all = "All"
}

// MARK: - Alert Configuration Section

/// Unified alert settings card: active days, alert types, and collapsible advanced options
/// (recovery, planned work, time window, daily digest).
struct AlertConfigurationSection: View {
    @Binding var subscription: RouteAlertSubscription
    @State private var showCustomDays = false
    @State private var showMoreOptions = false

    private static let presetBitmasks: Set<Int> = [0, 31, 96, 127]

    private var isCustomDays: Bool {
        !Self.presetBitmasks.contains(subscription.activeDays)
    }

    private var isFrequencyBased: Bool {
        RouteAlertSubscription.frequencyFirstSources.contains(subscription.dataSource)
    }

    /// MTA systems that support planned work notifications.
    private static let plannedWorkSystems: Set<String> = ["SUBWAY", "LIRR", "MNR"]

    private var showPlannedWork: Bool {
        (subscription.lineId != nil || subscription.fromStationCode != nil)
            && Self.plannedWorkSystems.contains(subscription.dataSource)
    }

    private var hasActiveAdvancedOptions: Bool {
        subscription.notifyRecovery
            || subscription.includePlannedWork
            || subscription.activeStartMinutes != nil
            || subscription.digestTimeMinutes != nil
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Alert Settings")
                .font(.headline)

            configCard {
                // Active Days (top — controls subscribe/unsubscribe)
                Text("Active Days")
                    .font(.subheadline.bold())
                    .foregroundColor(.secondary)
                dayPresetRow

                if isCustomDays || showCustomDays {
                    dayGrid
                        .transition(.opacity.combined(with: .move(edge: .top)))
                }

                Divider().opacity(0.3)

                // Cancellations
                sensitivityRow(
                    label: "Cancellations",
                    hint: cancellationSensitivity.wrappedValue == .severeOnly
                        ? "Major cancellations only"
                        : "All cancellations",
                    sensitivity: cancellationSensitivity
                )

                // Reduced Service / Delays
                sensitivityRow(
                    label: isFrequencyBased ? "Reduced Service" : "Delays",
                    hint: isFrequencyBased
                        ? (delaySensitivity.wrappedValue == .severeOnly ? "50%+ service reduction" : "Any service reduction")
                        : (delaySensitivity.wrappedValue == .severeOnly ? "20+ min delays" : "5+ min delays"),
                    sensitivity: delaySensitivity
                )

                Divider().opacity(0.3)

                // More Options (collapsible advanced settings)
                moreOptionsButton

                if showMoreOptions || hasActiveAdvancedOptions {
                    moreOptionsContent
                        .transition(.opacity.combined(with: .move(edge: .top)))
                }
            }
        }
    }

    // MARK: - More Options

    private var moreOptionsButton: some View {
        Button {
            withAnimation(.easeInOut(duration: 0.2)) {
                showMoreOptions.toggle()
            }
        } label: {
            HStack {
                Text("More Options")
                    .foregroundColor(.white)
                if hasActiveAdvancedOptions {
                    Circle()
                        .fill(Color.orange)
                        .frame(width: 6, height: 6)
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .rotationEffect(.degrees(showMoreOptions || hasActiveAdvancedOptions ? 90 : 0))
            }
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder
    private var moreOptionsContent: some View {
        // Recovery (only when at least one alert type is active)
        if subscription.notifyCancellation || subscription.notifyDelay {
            Toggle(isOn: $subscription.notifyRecovery) {
                Text("Notify on recovery")
            }
            .tint(.orange)
        }

        // Planned work (MTA systems only)
        if showPlannedWork {
            Toggle(isOn: $subscription.includePlannedWork) {
                Text("Planned work")
            }
            .tint(.orange)
        }

        // Time Window
        Toggle(isOn: timeWindowEnabled) {
            Text("Time window")
        }
        .tint(.orange)

        if subscription.activeStartMinutes != nil {
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

            Text("Alerts only sent during this window. Overnight ranges (e.g. 10pm–6am) are supported.")
                .font(.caption2)
                .foregroundColor(.secondary)
        }

        Divider().opacity(0.3)

        // Daily Digest
        Toggle(isOn: digestEnabled) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Daily digest")
                Text("Route status summary at a set time")
                    .font(.caption2)
                    .foregroundColor(.white.opacity(0.5))
            }
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

    private func sensitivityRow(label: String, hint: String?, sensitivity: Binding<AlertSensitivity>) -> some View {
        VStack(alignment: .leading, spacing: 4) {
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
            if let hint, sensitivity.wrappedValue != .none {
                Text(hint)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
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

    // MARK: - Delay / Reduced Service Sensitivity Binding

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
            presetButton("Weekdays", bitmask: 31)
            presetButton("Weekends", bitmask: 96)
            presetButton("Every Day", bitmask: 127)

            Button {
                withAnimation(.easeInOut(duration: 0.2)) {
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
            subscription.activeDays = bitmask
            withAnimation(.easeInOut(duration: 0.2)) {
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

    // MARK: - Time Window

    private var timeWindowEnabled: Binding<Bool> {
        Binding(
            get: { subscription.activeStartMinutes != nil },
            set: { enabled in
                if enabled {
                    subscription.activeStartMinutes = 360   // 6:00 AM
                    subscription.activeEndMinutes = 1200     // 8:00 PM
                    subscription.timezone = TimeZone.current.identifier
                } else {
                    subscription.activeStartMinutes = nil
                    subscription.activeEndMinutes = nil
                    if subscription.digestTimeMinutes == nil {
                        subscription.timezone = nil
                    }
                }
            }
        )
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
