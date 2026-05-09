import SwiftUI
import MapKit

/// System-level details: a route map, recent network stats, and a single
/// opt-in toggle for system-wide route alerts. Pushed from SettingsView when
/// a TrainSystemRow is tapped outside of edit mode.
struct TrainSystemDetailView: View {
    let system: TrainSystem

    @StateObject private var mapViewModel = CongestionMapViewModel()
    @ObservedObject private var alertService = AlertSubscriptionService.shared
    @ObservedObject private var subscriptionService = SubscriptionService.shared

    @State private var region: MKCoordinateRegion
    @State private var serviceAlerts: [V2ServiceAlert] = []
    @State private var showingPaywall = false

    init(system: TrainSystem) {
        self.system = system
        self._region = State(initialValue: system.defaultMapRegion)
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                mapSection
                statsSection
                alertsSection
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
    }

    // MARK: - Sections

    private var mapSection: some View {
        ZStack(alignment: .topTrailing) {
            // Embedded map preview. Hit-testing is disabled so vertical scroll
            // gestures aren't stolen by MKMapView; the map serves as visual
            // context, not as a fully interactive surface.
            SystemCongestionMapView(
                region: $region,
                segments: mapViewModel.segments,
                individualSegments: [],
                stations: [],
                showRoutes: mapViewModel.showRoutes,
                selectedSystems: [system],
                highlightMode: mapViewModel.highlightMode,
                onSegmentTap: { _ in },
                onIndividualSegmentTap: nil
            )
            .frame(height: 280)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .allowsHitTesting(false)

            if mapViewModel.isLoading {
                ProgressView()
                    .padding(8)
                    .background(.ultraThinMaterial, in: Capsule())
                    .padding(8)
            }
        }
    }

    private var statsSection: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 16) {
                Image(systemName: "chart.bar.fill")
                    .font(.title2)
                    .foregroundColor(.orange)
                    .frame(width: 24, height: 24)

                Text("Recent Activity")
                    .font(.headline)

                Spacer()
            }
            .padding()

            Divider()

            statRow(icon: "clock.fill", label: "Average delay", value: averageDelayDisplay)
            Divider()
            statRow(icon: "map.fill", label: "Routes", value: "\(systemRouteCount)")
            Divider()
            statRow(
                icon: "exclamationmark.triangle.fill",
                label: "Active alerts",
                value: activeAlertCount > 0 ? "\(activeAlertCount)" : "None"
            )
            Divider()
            statRow(
                icon: "wrench.and.screwdriver.fill",
                label: "Planned work",
                value: plannedWorkCount > 0 ? "\(plannedWorkCount)" : "None"
            )
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(.ultraThinMaterial)
        )
    }

    private func statRow(icon: String, label: String, value: String) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.body)
                .foregroundColor(.orange.opacity(0.8))
                .frame(width: 24)
            Text(label)
                .font(.subheadline)
            Spacer()
            Text(value)
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundColor(.secondary)
        }
        .padding(.horizontal)
        .padding(.vertical, 12)
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

    private var systemRouteCount: Int {
        RouteTopology.allRoutes.filter { $0.dataSource == system.dataSource }.count
    }

    private var averageDelayDisplay: String {
        let segments = mapViewModel.segments
        guard !segments.isEmpty else {
            return mapViewModel.isLoading ? "—" : "No data"
        }
        let avg = segments.map(\.averageDelayMinutes).reduce(0, +) / Double(segments.count)
        if avg < 0.5 { return "On time" }
        return String(format: "%.1f min", avg)
    }

    private var activeAlertCount: Int {
        serviceAlerts.filter { $0.alertType == "alert" && $0.isActiveNow }.count
    }

    private var plannedWorkCount: Int {
        serviceAlerts.filter { $0.alertType == "planned_work" && $0.isActiveNow }.count
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
        guard system.supportsAlerts else { return }
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
