import SwiftUI

struct EditRouteAlertsView: View {
    @EnvironmentObject private var appState: AppState
    @ObservedObject private var alertService = AlertSubscriptionService.shared
    @State private var showAddSheet = false

    /// Group subscriptions by data source for display.
    private var groupedSubscriptions: [(String, [RouteAlertSubscription])] {
        Dictionary(grouping: alertService.subscriptions, by: { $0.dataSource })
            .sorted { $0.key < $1.key }
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
        .onChange(of: alertService.subscriptions.count) { _, _ in
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
                        HStack {
                            if let lineName = sub.lineName {
                                Label(lineName, systemImage: "tram.fill")
                            } else if let from = sub.fromStationCode, let to = sub.toStationCode {
                                Label(
                                    "\(Stations.displayName(for: from)) → \(Stations.displayName(for: to))",
                                    systemImage: "arrow.right"
                                )
                            }
                            Spacer()
                        }
                        .foregroundColor(.white)
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
    }

    // MARK: - Helpers

    /// Auto-populate with home↔work if subscriptions are empty and RatSense has both.
    private func autoPopulateIfNeeded() {
        guard alertService.subscriptions.isEmpty else { return }
        let ratSense = RatSenseService.shared

        guard let home = ratSense.getHomeStation(),
              let work = ratSense.getWorkStation() else { return }

        // Infer data source from home station
        let systems = Stations.systemStringsForStation(home)
        guard let dataSource = systems.first else { return }

        alertService.addStationPairSubscription(
            dataSource: dataSource,
            fromStationCode: home,
            toStationCode: work
        )
        alertService.addStationPairSubscription(
            dataSource: dataSource,
            fromStationCode: work,
            toStationCode: home
        )
    }

    private func syncIfPossible() {
        Task { @MainActor in
            guard let token = AppDelegate.deviceToken else { return }
            await alertService.syncWithBackend(apnsToken: token)
        }
    }
}
