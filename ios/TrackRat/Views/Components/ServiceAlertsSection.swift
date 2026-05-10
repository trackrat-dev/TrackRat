import SwiftUI

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

// MARK: - Service Alerts Section

/// Reusable section that splits service alerts into Active vs Upcoming buckets,
/// renders a segmented picker with counts, and lists `ServiceAlertCard`s for the
/// selected bucket. Used by `RouteStatusView` and `TrainSystemDetailView`.
///
/// The caller is responsible for deciding whether to render this view at all
/// (e.g. only for systems whose data sources publish alert feeds).
struct ServiceAlertsSection: View {
    let alerts: [V2ServiceAlert]
    @State private var selectedFilter: ServiceAlertFilter = .active

    private var activeAlerts: [V2ServiceAlert] {
        alerts
            .filter { $0.isActiveNow }
            .sorted { $0.earliestStartEpoch < $1.earliestStartEpoch }
    }

    private var upcomingAlerts: [V2ServiceAlert] {
        alerts
            .filter { !$0.isActiveNow }
            .sorted { $0.earliestStartEpoch < $1.earliestStartEpoch }
    }

    private var filteredAlerts: [V2ServiceAlert] {
        selectedFilter == .active ? activeAlerts : upcomingAlerts
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Service Alerts")
                    .font(.headline)
                Spacer()
                Picker("", selection: $selectedFilter) {
                    ForEach(ServiceAlertFilter.allCases, id: \.self) { filter in
                        Text(filter.label(activeCount: activeAlerts.count, upcomingCount: upcomingAlerts.count)).tag(filter)
                    }
                }
                .pickerStyle(.segmented)
                .frame(width: 220)
            }

            if filteredAlerts.isEmpty {
                Text(selectedFilter == .active ? "No active alerts" : "No upcoming alerts")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 8)
            } else {
                ForEach(filteredAlerts) { alert in
                    ServiceAlertCard(alert: alert)
                }
            }
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
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
