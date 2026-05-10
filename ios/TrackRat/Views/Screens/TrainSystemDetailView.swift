import SwiftUI
import MapKit

/// System-level details: an interactive system-wide route map, a network
/// operations summary, current service alerts, and a single opt-in toggle for
/// system-wide route alerts. Pushed from SettingsView when a TrainSystemRow is
/// tapped outside of edit mode.
///
/// Tapping a map segment presents `RouteStatusView` as a sheet with the
/// concrete origin/destination pair, mirroring `CongestionMapView`.
struct TrainSystemDetailView: View {
    let system: TrainSystem

    @StateObject private var mapViewModel = CongestionMapViewModel()
    @ObservedObject private var alertService = AlertSubscriptionService.shared
    @ObservedObject private var subscriptionService = SubscriptionService.shared

    @State private var region: MKCoordinateRegion
    @State private var serviceAlerts: [V2ServiceAlert] = []
    @State private var showingPaywall = false
    @State private var routeStatusContext: RouteStatusContext?

    /// Data sources whose backend feeds publish service alerts. Other systems
    /// (PATH, BART, MBTA, etc.) have `supportsAlerts = true` for delay/cancel
    /// push notifications but no service-alert feed, so the section is hidden.
    private static let serviceAlertSystems: Set<String> = ["SUBWAY", "LIRR", "MNR", "NJT"]

    private var hasServiceAlertFeed: Bool {
        Self.serviceAlertSystems.contains(system.dataSource)
    }

    init(system: TrainSystem) {
        self.system = system
        self._region = State(initialValue: system.defaultMapRegion)
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                mapSection
                OperationsSummaryView(scope: .network)
                if hasServiceAlertFeed {
                    ServiceAlertsSection(alerts: serviceAlerts)
                }
                routesSection
                alertsSection
                FeedbackButton(
                    screen: "system_detail",
                    trainId: nil,
                    originCode: nil,
                    destinationCode: nil
                )
                .padding(.top, 8)
            }
            .padding()
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle(system.displayName)
        .navigationBarTitleDisplayMode(.inline)
        .task {
            mapViewModel.highlightMode = system.preferredHighlightMode
            mapViewModel.showRoutes = true
            mapViewModel.showStations = false
            await mapViewModel.fetchCongestionData(dataSource: system.dataSource)
            await loadServiceAlerts()
        }
        .sheet(isPresented: $showingPaywall) {
            PaywallView(context: .routeAlerts)
        }
        .sheet(item: $routeStatusContext) { context in
            RouteStatusView(context: context)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
    }

    // MARK: - Sections

    private var mapSection: some View {
        ZStack(alignment: .topTrailing) {
            SystemCongestionMapView(
                region: $region,
                segments: mapViewModel.segments,
                individualSegments: [],
                stations: [],
                showRoutes: mapViewModel.showRoutes,
                selectedSystems: [system],
                highlightMode: mapViewModel.highlightMode,
                onSegmentTap: { segment in
                    let route = RouteTopology.routeContaining(
                        from: segment.fromStation,
                        to: segment.toStation,
                        dataSource: segment.dataSource
                    )
                    routeStatusContext = RouteStatusContext(
                        dataSource: segment.dataSource,
                        lineId: route?.id,
                        fromStationCode: segment.fromStation,
                        toStationCode: segment.toStation
                    )
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                },
                onIndividualSegmentTap: nil
            )
            .frame(height: 280)
            .clipShape(RoundedRectangle(cornerRadius: 12))

            if mapViewModel.isLoading {
                ProgressView()
                    .padding(8)
                    .background(.ultraThinMaterial, in: Capsule())
                    .padding(8)
            }
        }
    }

    @ViewBuilder
    private var routesSection: some View {
        let routes = RouteTopology.allRoutes.filter { $0.dataSource == system.dataSource }
        if !routes.isEmpty {
            VStack(alignment: .leading, spacing: 0) {
                HStack {
                    Text("Routes")
                        .font(.headline)
                    Spacer()
                    Text("\(routes.count)")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .padding(.horizontal)
                .padding(.top)
                .padding(.bottom, 8)

                ForEach(Array(routes.enumerated()), id: \.element.id) { index, route in
                    Button {
                        routeStatusContext = RouteStatusContext(
                            dataSource: system.dataSource,
                            lineId: route.id
                        )
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                    } label: {
                        SystemRouteListRow(
                            route: route,
                            system: system,
                            averageDelayMinutes: averageDelay(for: route)
                        )
                    }
                    .buttonStyle(.plain)

                    if index < routes.count - 1 {
                        Divider().padding(.leading)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.bottom, 8)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(.ultraThinMaterial)
            )
        }
    }

    /// Average delay (in minutes) across the segments that make up `route`,
    /// or `nil` if no segments are loaded for the route's consecutive station
    /// pairs. Uses `mapViewModel.segments` so the value updates with the map.
    private func averageDelay(for route: RouteLine) -> Double? {
        let codes = route.stationCodes
        guard codes.count >= 2 else { return nil }
        var totals: [Double] = []
        for i in 0..<(codes.count - 1) {
            let from = codes[i]
            let to = codes[i + 1]
            if let segment = mapViewModel.segments.first(where: {
                $0.fromStation == from
                    && $0.toStation == to
                    && $0.dataSource == route.dataSource
            }) {
                totals.append(segment.averageDelayMinutes)
            }
        }
        guard !totals.isEmpty else { return nil }
        return totals.reduce(0, +) / Double(totals.count)
    }

    private var alertsSection: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 16) {
                Image(systemName: "bell.badge.fill")
                    .font(.title2)
                    .foregroundColor(.orange)
                    .frame(width: 24, height: 24)

                VStack(alignment: .leading, spacing: 2) {
                    Text("System-wide Alerts")
                        .font(.headline)
                    Text(alertSubtitleText)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Spacer()

                if system.supportsAlerts {
                    Toggle("", isOn: subscribedToggleBinding)
                        .labelsHidden()
                        .tint(.orange)
                } else {
                    Text("Unavailable")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            .padding()

            if isSubscribed {
                Divider()

                Text("Customize delivery, days, and thresholds from Route Alerts in Settings.")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal)
                    .padding(.vertical, 12)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(.ultraThinMaterial)
        )
    }

    // MARK: - Derived state

    private var existingSystemWideSub: RouteAlertSubscription? {
        alertService.subscriptions.first {
            $0.isSystemWide && $0.dataSource == system.dataSource
        }
    }

    private var isSubscribed: Bool { existingSystemWideSub != nil }

    private var atFreeRouteAlertLimit: Bool {
        !subscriptionService.isPro
            && alertService.subscriptions.count >= SubscriptionService.freeRouteAlertLimit
    }

    /// Two-way binding for the alerts toggle. The setter never mutates state
    /// directly — it routes through `handleToggle`, which gates on the free
    /// route-alert limit. If the gate trips, `isSubscribed` is unchanged and
    /// SwiftUI re-renders the Toggle in its prior state.
    private var subscribedToggleBinding: Binding<Bool> {
        Binding(
            get: { isSubscribed },
            set: { handleToggle($0) }
        )
    }

    private var alertSubtitleText: String {
        if !system.supportsAlerts {
            return "Real-time alerts not available for \(system.displayName)."
        }
        return isSubscribed
            ? "You'll be notified about delays across \(system.displayName)."
            : "Get notified about delays across \(system.displayName)."
    }

    // MARK: - Actions

    private func handleToggle(_ newValue: Bool) {
        if newValue {
            if atFreeRouteAlertLimit {
                showingPaywall = true
                return
            }
            let sub = RouteAlertSubscription(dataSource: system.dataSource)
            alertService.addSubscriptions([sub])
            alertService.syncIfPossible()
        } else if let sub = existingSystemWideSub {
            alertService.removeSubscription(sub)
            alertService.syncIfPossible()
        }
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }

    private func loadServiceAlerts() async {
        guard hasServiceAlertFeed else { return }
        do {
            serviceAlerts = try await APIService.shared.fetchServiceAlerts(dataSource: system.dataSource)
        } catch {
            print("TrainSystemDetailView: failed to load service alerts for \(system.dataSource): \(error)")
        }
    }
}

#Preview {
    NavigationStack {
        TrainSystemDetailView(system: .njt)
            .environmentObject(AppState())
            .environmentObject(ThemeManager.shared)
    }
}
