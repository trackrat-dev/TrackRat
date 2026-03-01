import SwiftUI

struct EditRouteAlertsView: View {
    @EnvironmentObject private var appState: AppState
    @ObservedObject private var alertService = AlertSubscriptionService.shared
    @State private var showAddSheet = false
    @State private var selectedRouteStatus: RouteStatusContext?
    @State private var selectedTrainAlert: RouteAlertSubscription?

    /// Group subscriptions by data source for display, sorted alphabetically within each group.
    private var groupedSubscriptions: [(String, [RouteAlertSubscription])] {
        Dictionary(grouping: alertService.subscriptions, by: { $0.dataSource })
            .sorted { $0.key < $1.key }
            .map { ($0.key, $0.value.sorted { ($0.lineName ?? $0.trainName ?? $0.fromStationCode ?? "") < ($1.lineName ?? $1.trainName ?? $1.fromStationCode ?? "") }) }
    }

    var body: some View {
        VStack(spacing: 0) {
            if alertService.subscriptions.isEmpty {
                emptyState
            } else {
                subscriptionList
            }
        }
        .navigationTitle("Route Alerts")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    showAddSheet = true
                } label: {
                    Image(systemName: "plus")
                        .foregroundColor(.orange)
                }
            }
        }
        .sheet(isPresented: $showAddSheet) {
            AddRouteAlertView()
                .environmentObject(appState)
        }
        .onAppear {
            autoPopulateIfNeeded()
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
                            if sub.trainId != nil {
                                selectedTrainAlert = sub
                            } else {
                                selectedRouteStatus = routeStatusContext(for: sub)
                            }
                        } label: {
                            HStack {
                                if let trainName = sub.trainName, sub.trainId != nil {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Label(trainName, systemImage: "train.side.front.car")
                                        if sub.weekdaysOnly {
                                            Text("Weekdays only")
                                                .font(.caption2)
                                                .foregroundColor(.white.opacity(0.5))
                                        }
                                    }
                                } else if let lineName = sub.lineName {
                                    VStack(alignment: .leading, spacing: 4) {
                                        Label(lineDisplayName(sub: sub, lineName: lineName), systemImage: "tram.fill")
                                        if let lineId = sub.lineId,
                                           let route = RouteTopology.allRoutes.first(where: { $0.id == lineId }),
                                           let subtitle = route.terminalSubtitle {
                                            Text(subtitle)
                                                .font(.caption2)
                                                .foregroundColor(.white.opacity(0.5))
                                        }
                                    }
                                } else if let from = sub.fromStationCode, let to = sub.toStationCode {
                                    Label(
                                        "\(Stations.displayName(for: from)) to \(Stations.displayName(for: to))",
                                        systemImage: "arrow.right"
                                    )
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
        .sheet(item: $selectedRouteStatus) { context in
            RouteStatusView(context: context)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
        .sheet(item: $selectedTrainAlert) { sub in
            NavigationStack {
                TrainDetailsView(
                    trainNumber: sub.trainId ?? "",
                    dataSource: sub.dataSource
                )
            }
            .presentationDetents([.large])
            .presentationDragIndicator(.visible)
        }
    }

    // MARK: - Helpers

    /// Auto-populate with home↔work if subscriptions are empty and RatSense has both.
    private func autoPopulateIfNeeded() {
        guard alertService.subscriptions.isEmpty else { return }
        let ratSense = RatSenseService.shared

        guard let home = ratSense.getHomeStation(),
              let work = ratSense.getWorkStation() else { return }

        // Infer data source from the intersection of both stations and user's selected systems
        let homeSystems = Stations.systemStringsForStation(home)
        let workSystems = Stations.systemStringsForStation(work)
        let selectedStrings = appState.selectedSystems.asRawStrings
        let common = homeSystems.intersection(workSystems).intersection(selectedStrings)
        guard let dataSource = common.first ?? homeSystems.intersection(workSystems).first else { return }

        alertService.addStationPairSubscriptions(
            dataSource: dataSource,
            fromStationCode: home,
            toStationCode: work
        )
    }

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
