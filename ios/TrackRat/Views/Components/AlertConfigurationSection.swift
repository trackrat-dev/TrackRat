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
                AlertConfigurationSection(subscription: $sub)
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

/// Reusable alert configuration UI that can be embedded in any ScrollView.
/// Renders as card-style sections matching the `.ultraThinMaterial` pattern
/// used throughout the app (e.g., RouteStatusView history cards).
struct AlertConfigurationSection: View {
    @Binding var subscription: RouteAlertSubscription

    /// Whether this subscription's data source uses frequency-based metrics (subway, PATH, PATCO).
    private var isFrequencyBased: Bool {
        RouteAlertSubscription.frequencyFirstSources.contains(subscription.dataSource)
    }

    /// MTA systems that support planned work notifications.
    private static let plannedWorkSystems: Set<String> = ["SUBWAY", "LIRR", "MNR"]

    /// Whether this is a line subscription on an MTA system (planned work eligible).
    private var showPlannedWork: Bool {
        subscription.lineId != nil && Self.plannedWorkSystems.contains(subscription.dataSource)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Alert Settings")
                .font(.headline)

            alertTypesCard
            daysCard
            timeWindowCard
            if showPlannedWork {
                plannedWorkCard
            }
            digestCard
        }
    }

    // MARK: - Days

    private var daysCard: some View {
        configCard {
            Text("Active Days")
                .font(.subheadline.bold())
                .foregroundColor(.secondary)

            dayPresetRow
            dayGrid
        }
    }

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
                        // Don't allow deselecting the last active day
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

    private var timeWindowCard: some View {
        configCard {
            Toggle(isOn: timeWindowEnabled) {
                Text("Time window")
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

    // MARK: - Alert Types

    private var alertTypesCard: some View {
        configCard {
            Text("Real-Time Alerts")
                .font(.subheadline.bold())
                .foregroundColor(.secondary)

            Toggle(isOn: $subscription.notifyCancellation) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Cancellations")
                    Text("Alert when trains are cancelled")
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.5))
                }
            }
            .tint(.orange)

            Toggle(isOn: $subscription.notifyDelay) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(isFrequencyBased ? "Reduced service" : "Delays")
                    Text(isFrequencyBased
                         ? "Alert when service frequency drops"
                         : "Alert when trains are significantly delayed")
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.5))
                }
            }
            .tint(.orange)

            if subscription.notifyDelay {
                if isFrequencyBased {
                    serviceThresholdRow
                } else {
                    delayThresholdRow
                }
            }

            if subscription.notifyCancellation || subscription.notifyDelay {
                Toggle(isOn: $subscription.notifyRecovery) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Recovery alerts")
                        Text("Notify when your route returns to normal")
                            .font(.caption2)
                            .foregroundColor(.white.opacity(0.5))
                    }
                }
                .tint(.orange)
            }
        }
    }

    // MARK: - Threshold

    private var delayThresholdRow: some View {
        HStack {
            Text("Delay threshold")
                .foregroundColor(.white)
            Spacer()
            Menu {
                Button("Default (15 min)") { subscription.delayThresholdMinutes = nil }
                ForEach([5, 10, 15, 20, 30], id: \.self) { min in
                    Button("\(min) min") { subscription.delayThresholdMinutes = min }
                }
            } label: {
                HStack(spacing: 4) {
                    Text(subscription.delayThresholdMinutes.map { "\($0) min" } ?? "Default")
                        .foregroundColor(.white)
                    Image(systemName: "chevron.up.chevron.down")
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.3))
                }
            }
        }
    }

    private var serviceThresholdRow: some View {
        HStack {
            Text("Service threshold")
                .foregroundColor(.white)
            Spacer()
            Menu {
                Button("Default (50%)") { subscription.serviceThresholdPct = nil }
                ForEach([30, 40, 50, 60, 70, 80], id: \.self) { pct in
                    Button("\(pct)%") { subscription.serviceThresholdPct = pct }
                }
            } label: {
                HStack(spacing: 4) {
                    Text(subscription.serviceThresholdPct.map { "\($0)%" } ?? "Default")
                        .foregroundColor(.white)
                    Image(systemName: "chevron.up.chevron.down")
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.3))
                }
            }
        }
    }

    // MARK: - Planned Work

    private var plannedWorkCard: some View {
        configCard {
            Toggle(isOn: $subscription.includePlannedWork) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Planned work alerts")
                    Text("Get notified about upcoming service changes")
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.5))
                }
            }
            .tint(.orange)
        }
    }

    // MARK: - Digest

    private var digestCard: some View {
        configCard {
            Toggle(isOn: digestEnabled) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Morning digest")
                    Text("Daily status summary at a set time")
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
