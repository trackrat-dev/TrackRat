import SwiftUI

// MARK: - Service Alerts Section

/// Two-tab service alerts section (Active / Upcoming) with badge counts.
/// Defaults to currently-active alerts. Shared by `RouteStatusView` and
/// `StationDetailsView`; callers decide whether to render it (e.g. only when
/// the system supports alerts and loading has finished).
struct ServiceAlertsSection: View {
    let alerts: [V2ServiceAlert]
    /// Alert IDs the section was opened to focus on (from a tapped push).
    /// Focused cards start expanded and highlighted, and the initial tab is
    /// chosen to contain a focused alert.
    let focusedAlertIds: Set<String>
    @State private var selectedFilter: ServiceAlertFilter

    init(alerts: [V2ServiceAlert], focusedAlertIds: Set<String> = []) {
        self.alerts = alerts
        self.focusedAlertIds = focusedAlertIds
        _selectedFilter = State(initialValue: Self.initialFilter(alerts: alerts, focusedAlertIds: focusedAlertIds))
    }

    /// Picks the initial tab: `.upcoming` only when a focused alert exists and
    /// none of the focused alerts are active now; otherwise `.active` (the
    /// default), matching prior behavior when nothing is focused.
    static func initialFilter(alerts: [V2ServiceAlert], focusedAlertIds: Set<String>) -> ServiceAlertFilter {
        guard !focusedAlertIds.isEmpty else { return .active }
        let focused = alerts.filter { focusedAlertIds.contains($0.alertId) }
        guard !focused.isEmpty else { return .active }
        return focused.contains(where: { $0.isActiveNow }) ? .active : .upcoming
    }

    var body: some View {
        let active = alerts
            .filter { $0.isActiveNow }
            .sorted { $0.earliestStartEpoch < $1.earliestStartEpoch }
        let upcoming = alerts
            .filter { !$0.isActiveNow }
            .sorted { $0.earliestStartEpoch < $1.earliestStartEpoch }
        let visible = selectedFilter == .active ? active : upcoming

        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Service Alerts")
                    .font(.headline)
                Spacer()
                Picker("", selection: $selectedFilter) {
                    ForEach(ServiceAlertFilter.allCases, id: \.self) { filter in
                        Text(filter.label(activeCount: active.count, upcomingCount: upcoming.count)).tag(filter)
                    }
                }
                .pickerStyle(.segmented)
                .frame(width: 220)
            }

            if visible.isEmpty {
                Text(selectedFilter == .active ? "No active alerts" : "No upcoming alerts")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 8)
            } else {
                ForEach(visible) { alert in
                    ServiceAlertCard(alert: alert, isFocused: focusedAlertIds.contains(alert.alertId))
                }
            }
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
    }
}

// MARK: - Service Alert Filter

enum ServiceAlertFilter: CaseIterable {
    case active, upcoming

    func label(activeCount: Int, upcomingCount: Int) -> String {
        switch self {
        case .active: return "Active (\(activeCount))"
        case .upcoming: return "Upcoming (\(upcomingCount))"
        }
    }
}

// MARK: - Service Alert Card

struct ServiceAlertCard: View {
    let alert: V2ServiceAlert
    let isFocused: Bool
    @State private var isExpanded: Bool

    init(alert: V2ServiceAlert, isFocused: Bool = false) {
        self.alert = alert
        self.isFocused = isFocused
        // The alert the user tapped to get here starts expanded.
        _isExpanded = State(initialValue: isFocused)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Text(alert.alertTypeLabel.uppercased())
                    .font(.caption2.bold())
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Capsule().fill(alertTypeColor.opacity(0.2)))
                    .foregroundColor(alertTypeColor)

                if alert.isActiveNow && !alert.activePeriods.isEmpty {
                    Text("ACTIVE NOW")
                        .font(.caption2.bold())
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Capsule().fill(Color.green.opacity(0.2)))
                        .foregroundColor(.green)
                }

                Spacer()
            }

            if let periodText = alert.activePeriodText {
                HStack(spacing: 4) {
                    Image(systemName: "calendar")
                        .font(.caption2)
                    Text(periodText)
                        .font(.caption)
                    if alert.additionalPeriodCount > 0 {
                        Text("(+\(alert.additionalPeriodCount) more)")
                            .font(.caption)
                    }
                }
                .foregroundColor(.secondary)
            }

            Text(alert.headerText)
                .font(.subheadline)
                .foregroundColor(.primary)

            if let description = alert.descriptionText, !description.isEmpty {
                Text(description)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(isExpanded ? nil : 3)

                if description.count > 120 {
                    Button(isExpanded ? "Show Less" : "Show More") {
                        withAnimation { isExpanded.toggle() }
                    }
                    .font(.caption.bold())
                    .foregroundColor(.orange)
                }
            }
        }
        .padding(10)
        .background(RoundedRectangle(cornerRadius: 8).fill(Color(.secondarySystemGroupedBackground)))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(Color.orange, lineWidth: isFocused ? 2 : 0)
        )
    }

    private var alertTypeColor: Color {
        switch alert.alertType {
        case "planned_work": return .yellow
        case "alert": return .red
        case "elevator": return .blue
        default: return .orange
        }
    }
}
