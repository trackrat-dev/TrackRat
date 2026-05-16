import SwiftUI

// MARK: - Service Alerts Section

/// Two-tab service alerts section (Active / Upcoming) with badge counts.
/// Defaults to currently-active alerts. Shared by `RouteStatusView` and
/// `StationDetailsView`; callers decide whether to render it (e.g. only when
/// the system supports alerts and loading has finished).
struct ServiceAlertsSection: View {
    let alerts: [V2ServiceAlert]
    @State private var selectedFilter: ServiceAlertFilter = .active

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
                    ServiceAlertCard(alert: alert)
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
    @State private var isExpanded = false

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
