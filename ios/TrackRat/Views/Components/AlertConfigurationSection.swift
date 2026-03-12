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
                    DigestConfigurationSection(subscription: $sub)
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

// MARK: - Alert Sensitivity

/// Tri-state alert sensitivity for cancellation and delay/reduced-service controls.
enum AlertSensitivity: String, CaseIterable {
    case none = "None"
    case severeOnly = "Severe"
    case all = "All"
}

// MARK: - Alert Configuration Section

/// Unified alert settings card: alert types, recovery, planned work, active days, time window.
/// Digest is handled separately by `DigestConfigurationSection`.
struct AlertConfigurationSection: View {
    @Binding var subscription: RouteAlertSubscription

    private var isFrequencyBased: Bool {
        RouteAlertSubscription.frequencyFirstSources.contains(subscription.dataSource)
    }

    /// MTA systems that support planned work notifications.
    private static let plannedWorkSystems: Set<String> = ["SUBWAY", "LIRR", "MNR"]

    private var showPlannedWork: Bool {
        (subscription.lineId != nil || subscription.fromStationCode != nil)
            && Self.plannedWorkSystems.contains(subscription.dataSource)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Alert Settings")
                .font(.headline)

            configCard {
                // Cancellations
                sensitivityRow(
                    label: "Cancellations",
                    sensitivity: cancellationSensitivity
                )

                // Reduced Service / Delays
                sensitivityRow(
                    label: isFrequencyBased ? "Reduced Service" : "Delays",
                    sensitivity: delaySensitivity
                )

                // Recovery (only when at least one alert type is active)
                if subscription.notifyCancellation || subscription.notifyDelay {
                    Divider().opacity(0.3)
                    Toggle(isOn: $subscription.notifyRecovery) {
                        Text("Recovery alerts")
                    }
                    .tint(.orange)
                }

                // Planned work (MTA systems only)
                if showPlannedWork {
                    Divider().opacity(0.3)
                    Toggle(isOn: $subscription.includePlannedWork) {
                        Text("Planned work")
                    }
                    .tint(.orange)
                }

                Divider().opacity(0.3)

                // Active Days
                Text("Active Days")
                    .font(.subheadline.bold())
                    .foregroundColor(.secondary)
                dayPresetRow
                dayGrid

                Divider().opacity(0.3)

                // Time Window
                Toggle(isOn: timeWindowEnabled) {
                    Text("Time Window")
                }
                .tint(.orange)

                if subscription.activeStartMinutes != nil {
                    HStack {
                        Text("From")
                            .foregroundColor(.white.opacity(0.6))
                        Spacer()
                        minutePicker(selection: Binding(
                            get: { subscription.activeStartMinutes ?? 360 },
                            set: { subscription.activeStartMinutes = $0 }
                        ))
                    }
                    HStack {
                        Text("To")
                            .foregroundColor(.white.opacity(0.6))
                        Spacer()
                        minutePicker(selection: Binding(
                            get: { subscription.activeEndMinutes ?? 1200 },
                            set: { subscription.activeEndMinutes = $0 }
                        ))
                    }

                    Text("Alerts only sent during this window. Overnight ranges (e.g. 10pm–6am) are supported.")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
        }
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
        HStack(spacing: 12) {
            presetButton("Weekdays", bitmask: 31)
            presetButton("Weekends", bitmask: 96)
            presetButton("Every Day", bitmask: 127)
        }
    }

    private func presetButton(_ label: String, bitmask: Int) -> some View {
        Button {
            subscription.activeDays = bitmask
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
                        if subscription.activeDays & ~bit != 0 {
                            subscription.activeDays &= ~bit
                        }
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
                    subscription.timezone = nil
                }
            }
        )
    }

    private func minutePicker(selection: Binding<Int>) -> some View {
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

// MARK: - Digest Configuration Section

/// Standalone digest card, separated from alert settings.
struct DigestConfigurationSection: View {
    @Binding var subscription: RouteAlertSubscription

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Daily Digest")
                .font(.headline)

            VStack(alignment: .leading, spacing: 8) {
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
                        minutePicker(selection: Binding(
                            get: { subscription.digestTimeMinutes ?? 420 },
                            set: { subscription.digestTimeMinutes = $0 }
                        ))
                    }

                    Text("Sends a route status summary once per day at this time.")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
        }
    }

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

    private func minutePicker(selection: Binding<Int>) -> some View {
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
}
