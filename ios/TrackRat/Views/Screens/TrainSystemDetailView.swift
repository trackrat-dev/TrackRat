import SwiftUI
import MapKit

/// System-level details: an interactive system-wide route map, a network
/// operations summary, current service alerts, a clickable list of routes,
/// and the full alert-configuration form for system-wide route alerts.
///
/// Reached from:
/// - SettingsView selected-systems list (push)
/// - SettingsView Route Alerts list when the tapped subscription is system-wide (sheet)
/// - Notification deep-link when the notification is system-wide (sheet via MapContainerView)
///
/// Tapping a map segment or a route row presents `RouteStatusView` as a sheet.
struct TrainSystemDetailView: View {
    let system: TrainSystem

    @StateObject private var mapViewModel = CongestionMapViewModel()
    @ObservedObject private var alertService = AlertSubscriptionService.shared
    @ObservedObject private var subscriptionService = SubscriptionService.shared

    @State private var region: MKCoordinateRegion
    @State private var serviceAlerts: [V2ServiceAlert] = []
    @State private var showingPaywall = false
    @State private var routeStatusContext: RouteStatusContext?
    @State private var feedbackRequest: FeedbackSheetRequest?

    /// Locally-edited copies of the matching system-wide subscription, keyed by ID.
    /// Persisted to `alertService` on disappear.
    @State private var editedSubscriptions: [UUID: RouteAlertSubscription] = [:]

    /// Draft subscription used when no matching system-wide subscription exists yet.
    /// Initialized in `.task`; consumed when the user picks any active day.
    @State private var draftSubscription: RouteAlertSubscription?

    init(system: TrainSystem) {
        self.system = system
        self._region = State(initialValue: system.defaultMapRegion)
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                mapSection
                OperationsSummaryView(scope: .network, dataSource: system.dataSource)
                if system.hasServiceAlertFeed {
                    ServiceAlertsSection(alerts: serviceAlerts)
                }
                routesSection
                alertsSection
                FeedbackButton(
                    screen: "system_detail",
                    trainId: nil,
                    originCode: nil,
                    destinationCode: nil,
                    onRequest: { feedbackRequest = $0 }
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
            // Seed the draft when no system-wide subscription exists yet, so the
            // AlertConfigurationSection has a stable binding to mutate.
            if matchingSubscriptions.isEmpty && draftSubscription == nil {
                draftSubscription = RouteAlertSubscription(
                    dataSource: system.dataSource,
                    activeDays: 0
                )
            }
            await mapViewModel.fetchCongestionData(dataSource: system.dataSource)
            await loadServiceAlerts()
        }
        .onDisappear {
            guard !editedSubscriptions.isEmpty else { return }
            for (_, edited) in editedSubscriptions {
                alertService.updateSubscription(edited)
            }
            alertService.syncIfPossible()
        }
        .sheet(isPresented: $showingPaywall) {
            PaywallView(context: .routeAlerts)
        }
        .sheet(item: $routeStatusContext) { context in
            RouteStatusView(context: context)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
        .feedbackSheet(request: $feedbackRequest)
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
            // Build the segment lookup once per render so each row's
            // delay computation is O(stops) instead of O(stops × segments).
            // Key by an alphabetically-ordered pair so A→B and B→A collapse
            // to the same entry; the backend can return either direction and
            // we want consecutive route stops to find a match regardless.
            // When both directions are present, keep the one with more samples.
            let segmentsByPair: [String: CongestionSegment] = mapViewModel.segments
                .reduce(into: [:]) { acc, segment in
                    let key = Self.canonicalPairKey(segment.fromStation, segment.toStation)
                    if let existing = acc[key], existing.sampleCount >= segment.sampleCount {
                        return
                    }
                    acc[key] = segment
                }

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
                            averageDelayMinutes: averageDelay(for: route, segmentsByPair: segmentsByPair)
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
    /// pairs. Looks up segments via the caller-provided dictionary so the cost
    /// is O(stops) per route instead of O(stops × segments).
    private func averageDelay(for route: RouteLine, segmentsByPair: [String: CongestionSegment]) -> Double? {
        let codes = route.stationCodes
        guard codes.count >= 2 else { return nil }
        var totals: [Double] = []
        for i in 0..<(codes.count - 1) {
            let key = Self.canonicalPairKey(codes[i], codes[i + 1])
            if let segment = segmentsByPair[key] {
                totals.append(segment.averageDelayMinutes)
            }
        }
        guard !totals.isEmpty else { return nil }
        return totals.reduce(0, +) / Double(totals.count)
    }

    /// Alphabetically-ordered key for a station pair so A↔B collapses to a
    /// single canonical entry. Matches the convention used by
    /// `buildMergedAggregatedOverlays` in `CongestionMapView`.
    private static func canonicalPairKey(_ a: String, _ b: String) -> String {
        a < b ? "\(a)|\(b)" : "\(b)|\(a)"
    }

    @ViewBuilder
    private var alertsSection: some View {
        if system.supportsAlerts {
            AlertConfigurationSection(
                subscription: alertConfigBinding,
                headerText: "\(system.displayName) Alerts"
            )
            .onChange(of: alertConfigBinding.wrappedValue.activeDays) { _, newDays in
                handleActiveDaysChange(newDays)
            }
        } else {
            HStack(spacing: 16) {
                Image(systemName: "bell.slash.fill")
                    .font(.title2)
                    .foregroundColor(.secondary)
                    .frame(width: 24, height: 24)

                VStack(alignment: .leading, spacing: 2) {
                    Text("\(system.displayName) Alerts")
                        .font(.headline)
                    Text("Real-time alerts not available for \(system.displayName).")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Spacer()
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(.ultraThinMaterial)
            )
        }
    }

    // MARK: - Derived state

    private var matchingSubscriptions: [RouteAlertSubscription] {
        alertService.subscriptions.filter {
            $0.isSystemWide && $0.dataSource == system.dataSource
        }
    }

    private var isSubscribed: Bool { !matchingSubscriptions.isEmpty }

    private var atFreeRouteAlertLimit: Bool {
        !subscriptionService.isPro
            && alertService.subscriptions.count >= SubscriptionService.freeRouteAlertLimit
    }

    /// Single binding for alert configuration. Uses the matching system-wide
    /// subscription if one exists; otherwise falls back to the draft.
    private var alertConfigBinding: Binding<RouteAlertSubscription> {
        if let first = matchingSubscriptions.first {
            return Binding(
                get: { editedSubscriptions[first.id] ?? first },
                set: { newValue in
                    let edited = RouteAlertSubscription.copySettings(
                        from: newValue,
                        to: editedSubscriptions[first.id] ?? first
                    )
                    editedSubscriptions[first.id] = edited
                }
            )
        }
        return Binding(
            get: {
                draftSubscription ?? RouteAlertSubscription(
                    dataSource: system.dataSource,
                    activeDays: 0
                )
            },
            set: { draftSubscription = $0 }
        )
    }

    // MARK: - Actions

    /// Auto-subscribe when activeDays goes non-zero, auto-unsubscribe when it
    /// returns to zero. Mirrors the per-route flow in `RouteStatusView`.
    private func handleActiveDaysChange(_ newDays: Int) {
        if newDays > 0 && !isSubscribed {
            if atFreeRouteAlertLimit {
                // Revert the UI to "None" when the paywall is dismissed.
                draftSubscription?.activeDays = 0
                showingPaywall = true
                return
            }
            let template = draftSubscription ?? RouteAlertSubscription(
                dataSource: system.dataSource,
                activeDays: newDays
            )
            let sub = RouteAlertSubscription(
                dataSource: template.dataSource,
                activeDays: newDays,
                activeStartMinutes: template.activeStartMinutes,
                activeEndMinutes: template.activeEndMinutes,
                timezone: template.timezone,
                delayThresholdMinutes: template.delayThresholdMinutes,
                serviceThresholdPct: template.serviceThresholdPct,
                cancellationThresholdPct: template.cancellationThresholdPct,
                notifyCancellation: template.notifyCancellation,
                notifyDelay: template.notifyDelay,
                notifyRecovery: template.notifyRecovery,
                digestTimeMinutes: template.digestTimeMinutes,
                includePlannedWork: template.includePlannedWork
            )
            alertService.addSubscriptions([sub])
            draftSubscription = nil
            alertService.syncIfPossible()
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        } else if newDays == 0 && isSubscribed {
            for sub in matchingSubscriptions {
                alertService.removeSubscription(sub)
            }
            editedSubscriptions.removeAll()
            draftSubscription = RouteAlertSubscription(
                dataSource: system.dataSource,
                activeDays: 0
            )
            alertService.syncIfPossible()
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        }
    }

    private func loadServiceAlerts() async {
        guard system.hasServiceAlertFeed else { return }
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
