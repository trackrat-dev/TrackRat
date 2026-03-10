import SwiftUI

struct AlertCustomizationSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var sub: RouteAlertSubscription
    private let onSave: (RouteAlertSubscription) -> Void

    init(subscription: RouteAlertSubscription, onSave: @escaping (RouteAlertSubscription) -> Void) {
        _sub = State(initialValue: subscription)
        self.onSave = onSave
    }

    /// Whether this subscription's data source uses frequency-based metrics (subway, PATH, PATCO).
    private var isFrequencyBased: Bool {
        RouteAlertSubscription.frequencyFirstSources.contains(sub.dataSource)
    }

    /// MTA systems that support planned work notifications.
    private static let plannedWorkSystems: Set<String> = ["SUBWAY", "LIRR", "MNR"]

    /// Whether this is a line subscription on an MTA system (planned work eligible).
    private var showPlannedWork: Bool {
        sub.lineId != nil && Self.plannedWorkSystems.contains(sub.dataSource)
    }

    var body: some View {
        NavigationStack {
            List {
                alertTypesSection
                daysSection
                timeWindowSection
                if showPlannedWork {
                    plannedWorkSection
                }
                digestSection
            }
            .listStyle(.insetGrouped)
            .scrollContentBackground(.hidden)
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

    // MARK: - Alert Types

    private var alertTypesSection: some View {
        Section {
            Toggle(isOn: $sub.notifyCancellation) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Cancellations")
                    Text("Alert when trains are cancelled")
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.5))
                }
            }
            .tint(.orange)

            Toggle(isOn: $sub.notifyDelay) {
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

            if sub.notifyDelay {
                if isFrequencyBased {
                    serviceThresholdRow
                } else {
                    delayThresholdRow
                }
            }

            if sub.notifyCancellation || sub.notifyDelay {
                Toggle(isOn: $sub.notifyRecovery) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Recovery alerts")
                        Text("Notify when your route returns to normal")
                            .font(.caption2)
                            .foregroundColor(.white.opacity(0.5))
                    }
                }
                .tint(.orange)
            }
        } header: {
            Text("Real-Time Alerts")
        }
    }

    // MARK: - Days

    private var daysSection: some View {
        Section {
            dayPresetRow
            dayGrid
        } header: {
            Text("Active Days")
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
            sub.activeDays = bitmask
        } label: {
            Text(label)
                .font(.caption)
                .fontWeight(sub.activeDays == bitmask ? .bold : .regular)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(
                    Capsule().fill(sub.activeDays == bitmask ? Color.orange : Color.white.opacity(0.1))
                )
                .foregroundColor(sub.activeDays == bitmask ? .black : .white)
        }
        .buttonStyle(.plain)
    }

    private var dayGrid: some View {
        let dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return HStack(spacing: 6) {
            ForEach(0..<7, id: \.self) { index in
                let bit = 1 << index
                let isOn = sub.activeDays & bit != 0
                Button {
                    if isOn {
                        sub.activeDays &= ~bit
                    } else {
                        sub.activeDays |= bit
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

    private var timeWindowSection: some View {
        Section {
            Toggle(isOn: timeWindowEnabled) {
                Text("Time window")
            }
            .tint(.orange)

            if sub.activeStartMinutes != nil {
                HStack {
                    Text("From")
                        .foregroundColor(.white.opacity(0.6))
                    Spacer()
                    minutePicker(selection: Binding(
                        get: { sub.activeStartMinutes ?? 360 },
                        set: { sub.activeStartMinutes = $0 }
                    ))
                }
                HStack {
                    Text("To")
                        .foregroundColor(.white.opacity(0.6))
                    Spacer()
                    minutePicker(selection: Binding(
                        get: { sub.activeEndMinutes ?? 1200 },
                        set: { sub.activeEndMinutes = $0 }
                    ))
                }
            }
        } header: {
            Text("Time Window")
        } footer: {
            if sub.activeStartMinutes != nil {
                Text("Alerts only sent during this window. Uses your device timezone.")
            }
        }
    }

    private var timeWindowEnabled: Binding<Bool> {
        Binding(
            get: { sub.activeStartMinutes != nil },
            set: { enabled in
                if enabled {
                    sub.activeStartMinutes = 360   // 6:00 AM
                    sub.activeEndMinutes = 1200     // 8:00 PM
                    sub.timezone = TimeZone.current.identifier
                } else {
                    sub.activeStartMinutes = nil
                    sub.activeEndMinutes = nil
                    sub.timezone = nil
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

    // MARK: - Threshold

    private var delayThresholdRow: some View {
        HStack {
            Text("Delay threshold")
                .foregroundColor(.white)
            Spacer()
            Menu {
                Button("Default (15 min)") { sub.delayThresholdMinutes = nil }
                ForEach([5, 10, 15, 20, 30], id: \.self) { min in
                    Button("\(min) min") { sub.delayThresholdMinutes = min }
                }
            } label: {
                HStack(spacing: 4) {
                    Text(sub.delayThresholdMinutes.map { "\($0) min" } ?? "Default")
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
                Button("Default (50%)") { sub.serviceThresholdPct = nil }
                ForEach([30, 40, 50, 60, 70, 80], id: \.self) { pct in
                    Button("\(pct)%") { sub.serviceThresholdPct = pct }
                }
            } label: {
                HStack(spacing: 4) {
                    Text(sub.serviceThresholdPct.map { "\($0)%" } ?? "Default")
                        .foregroundColor(.white)
                    Image(systemName: "chevron.up.chevron.down")
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.3))
                }
            }
        }
    }

    // MARK: - Planned Work

    private var plannedWorkSection: some View {
        Section {
            Toggle(isOn: $sub.includePlannedWork) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Planned work alerts")
                    Text("Get notified about upcoming service changes")
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.5))
                }
            }
            .tint(.orange)
        } header: {
            Text("Planned Work")
        }
    }

    // MARK: - Digest

    private var digestSection: some View {
        Section {
            Toggle(isOn: digestEnabled) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Morning digest")
                    Text("Daily status summary at a set time")
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.5))
                }
            }
            .tint(.orange)

            if sub.digestTimeMinutes != nil {
                HStack {
                    Text("Digest time")
                        .foregroundColor(.white.opacity(0.6))
                    Spacer()
                    minutePicker(selection: Binding(
                        get: { sub.digestTimeMinutes ?? 420 },
                        set: { sub.digestTimeMinutes = $0 }
                    ))
                }
            }
        } header: {
            Text("Morning Digest")
        } footer: {
            if sub.digestTimeMinutes != nil {
                Text("Sends a route status summary once per day at this time.")
            }
        }
    }

    private var digestEnabled: Binding<Bool> {
        Binding(
            get: { sub.digestTimeMinutes != nil },
            set: { enabled in
                if enabled {
                    sub.digestTimeMinutes = 420  // 7:00 AM
                    if sub.timezone == nil {
                        sub.timezone = TimeZone.current.identifier
                    }
                } else {
                    sub.digestTimeMinutes = nil
                }
            }
        )
    }
}
