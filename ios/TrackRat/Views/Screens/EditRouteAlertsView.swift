import SwiftUI

struct EditRouteAlertsView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var alertService = AlertSubscriptionService.shared
    @State private var showAddSheet = false
    @State private var selectedSubscription: RouteAlertSubscription?

    /// Group subscriptions by data source for display, sorted alphabetically within each group.
    private var groupedSubscriptions: [(String, [RouteAlertSubscription])] {
        Dictionary(grouping: alertService.subscriptions, by: { $0.dataSource })
            .sorted { $0.key < $1.key }
            .map { ($0.key, $0.value.sorted { ($0.lineName ?? $0.trainName ?? $0.fromStationCode ?? "") < ($1.lineName ?? $1.trainName ?? $1.fromStationCode ?? "") }) }
    }

    var body: some View {
        VStack(spacing: 0) {
            TrackRatNavigationHeader(
                title: "Route Alerts",
                showBackButton: true,
                onBackAction: { dismiss() }
            ) {
                Button {
                    showAddSheet = true
                } label: {
                    Image(systemName: "plus")
                        .foregroundColor(.orange)
                        .frame(minWidth: 44, minHeight: 44)
                }
                .buttonStyle(.plain)
            }

            if alertService.subscriptions.isEmpty {
                emptyState
            } else {
                subscriptionList
            }
        }
        .navigationBarHidden(true)
        .sheet(isPresented: $showAddSheet) {
            AddRouteAlertView()
                .environmentObject(appState)
        }
        .onDisappear {
            syncIfPossible()
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "bell.slash")
                .font(.system(size: 48))
                .foregroundColor(.white.opacity(0.3))
            Text("No Route Alerts")
                .font(.headline)
                .foregroundColor(.white)
            Text("Get notified when trains on your routes are delayed or cancelled.")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.6))
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)

            Button {
                showAddSheet = true
            } label: {
                Text("Add Route Alert")
                    .font(.headline)
                    .foregroundColor(.black)
                    .padding(.horizontal, 24)
                    .padding(.vertical, 12)
                    .background(Capsule().fill(.orange))
            }
            .padding(.top, 8)
            Spacer()
        }
    }

    // MARK: - List

    private var subscriptionList: some View {
        List {
            ForEach(groupedSubscriptions, id: \.0) { dataSource, subs in
                Section(header: Text(dataSource).foregroundColor(.white.opacity(0.7))) {
                    ForEach(subs) { sub in
                        Button {
                            selectedSubscription = sub
                        } label: {
                            HStack {
                                if let trainName = sub.trainName, sub.trainId != nil {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Label(trainName, systemImage: "train.side.front.car")
                                        scheduleSummary(for: sub)
                                    }
                                } else if let lineName = sub.lineName {
                                    VStack(alignment: .leading, spacing: 4) {
                                        Label(lineDisplayName(sub: sub, lineName: lineName), systemImage: "tram.fill")
                                        Text("\(TrainSystem(rawValue: sub.dataSource)?.displayName ?? sub.dataSource): \(lineName)")
                                            .font(.caption2)
                                            .foregroundColor(.white.opacity(0.5))
                                        if sub.includePlannedWork {
                                            Text("Includes planned work alerts")
                                                .font(.caption2)
                                                .foregroundColor(.orange.opacity(0.7))
                                        }
                                        scheduleSummary(for: sub)
                                    }
                                } else if let from = sub.fromStationCode, let to = sub.toStationCode {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Label(
                                            "\(Stations.displayName(for: from)) to \(Stations.displayName(for: to))",
                                            systemImage: "arrow.right"
                                        )
                                        scheduleSummary(for: sub)
                                    }
                                }
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            .foregroundColor(.white)
                        }
                    }
                    .onDelete { offsets in
                        let toRemove = offsets.map { subs[$0] }
                        for sub in toRemove {
                            alertService.removeSubscription(sub)
                        }
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .sheet(item: $selectedSubscription) { sub in
            if sub.trainId != nil {
                NavigationStack {
                    TrainDetailsView(
                        trainNumber: sub.trainId!,
                        dataSource: sub.dataSource,
                        isSheet: true,
                        subscription: sub,
                        onSave: { updated in alertService.updateSubscription(updated) }
                    )
                }
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
            } else {
                RouteStatusView(context: routeStatusContext(for: sub))
                    .presentationDetents([.large])
                    .presentationDragIndicator(.visible)
            }
        }
    }

    // MARK: - Schedule Summary

    @ViewBuilder
    private func scheduleSummary(for sub: RouteAlertSubscription) -> some View {
        let parts = scheduleParts(for: sub)
        if !parts.isEmpty {
            Text(parts.joined(separator: " · "))
                .font(.caption2)
                .foregroundColor(.white.opacity(0.5))
        }
    }

    private func scheduleParts(for sub: RouteAlertSubscription) -> [String] {
        var parts: [String] = []

        // Day schedule
        let days = sub.activeDays
        if days == 31 {
            parts.append("Weekdays")
        } else if days == 96 {
            parts.append("Weekends")
        } else if days != 127 {
            parts.append(dayAbbreviations(for: days))
        }

        // Time window
        if let start = sub.activeStartMinutes, let end = sub.activeEndMinutes {
            parts.append("\(formatMinutes(start))–\(formatMinutes(end))")
        }

        // Custom threshold
        if let threshold = sub.delayThresholdMinutes {
            parts.append("≥\(threshold)m delay")
        }
        if let pct = sub.serviceThresholdPct {
            parts.append("≥\(pct)% service")
        }

        // Recovery
        if sub.notifyRecovery {
            parts.append("Recovery")
        }

        // Digest
        if let digest = sub.digestTimeMinutes {
            parts.append("Digest \(formatMinutes(digest))")
        }

        return parts
    }

    private func dayAbbreviations(for bitmask: Int) -> String {
        let names = ["M", "T", "W", "Th", "F", "Sa", "Su"]
        return names.enumerated()
            .filter { bitmask & (1 << $0.offset) != 0 }
            .map(\.element)
            .joined()
    }

    private func formatMinutes(_ minutes: Int) -> String {
        let h = minutes / 60
        let m = minutes % 60
        let ampm = h >= 12 ? "pm" : "am"
        let h12 = h == 0 ? 12 : (h > 12 ? h - 12 : h)
        return m == 0 ? "\(h12)\(ampm)" : String(format: "%d:%02d%@", h12, m, ampm)
    }

    // MARK: - Helpers

    private func syncIfPossible() {
        Task { @MainActor in
            guard let token = AppDelegate.deviceToken else { return }
            await alertService.syncWithBackend(apnsToken: token)
        }
    }

    /// Build display name for a line subscription, showing "{from} to {destination}".
    private func lineDisplayName(sub: RouteAlertSubscription, lineName: String) -> String {
        guard let direction = sub.direction else { return lineName }
        let directionName = Stations.displayName(for: direction)
        // Use route station codes to find the "from" terminus
        if let lineId = sub.lineId,
           let route = RouteTopology.allRoutes.first(where: { $0.id == lineId }) {
            let stations = route.stationCodes
            let fromCode = direction == stations.last ? stations.first : stations.last
            if let fromCode = fromCode {
                return "\(Stations.displayName(for: fromCode)) to \(directionName)"
            }
        }
        return "\(lineName) to \(directionName)"
    }

    /// Build a RouteStatusContext for a subscription, using direction to set from/to.
    private func routeStatusContext(for sub: RouteAlertSubscription) -> RouteStatusContext {
        if let lineId = sub.lineId, let direction = sub.direction,
           let route = RouteTopology.allRoutes.first(where: { $0.id == lineId }) {
            let stations = route.stationCodes
            if direction == stations.last {
                return RouteStatusContext(
                    dataSource: sub.dataSource,
                    lineId: lineId,
                    fromStationCode: stations.first,
                    toStationCode: stations.last
                )
            } else {
                return RouteStatusContext(
                    dataSource: sub.dataSource,
                    lineId: lineId,
                    fromStationCode: stations.last,
                    toStationCode: stations.first
                )
            }
        }
        return RouteStatusContext(
            dataSource: sub.dataSource,
            lineId: sub.lineId,
            fromStationCode: sub.fromStationCode,
            toStationCode: sub.toStationCode
        )
    }
}
