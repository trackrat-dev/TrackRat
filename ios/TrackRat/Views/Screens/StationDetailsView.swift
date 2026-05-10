import SwiftUI
import MapKit

/// Per-station overview: upcoming/recent departures, service alerts, routes
/// served, and quick actions (favorite, set as home/work). Reachable from
/// any station row via the `stationDetailsContextMenu` modifier or via a
/// direct tap from places where users browse stations (Settings favorites,
/// Onboarding favorites list).
struct StationDetailsView: View {
    let stationCode: String

    @StateObject private var viewModel: StationDetailsViewModel
    @EnvironmentObject private var appState: AppState
    @ObservedObject private var ratSense = RatSenseService.shared

    init(stationCode: String) {
        self.stationCode = stationCode
        self._viewModel = StateObject(wrappedValue: StationDetailsViewModel(stationCode: stationCode))
    }

    private var displayName: String { Stations.displayName(for: stationCode) }
    private var fullName: String { Stations.stationName(forCode: stationCode) ?? displayName }
    private var stationSystems: Set<TrainSystem> { Stations.systemsForStation(stationCode) }
    private var hasAlertSupport: Bool { stationSystems.contains { Self.alertSupportedSystems.contains($0) } }
    private var coordinate: CLLocationCoordinate2D? { Stations.getCoordinates(for: stationCode) }

    private var routesServingStation: [RouteLine] {
        // Expand via equivalents so station complexes match every route serving
        // them, not just the canonical line. e.g. Times Sq-42 St (S127) also
        // covers 7/A-C-E/N-Q-R-W/shuttle via S725/SA27/SR16/S902.
        let codes = Stations.stationEquivalents[stationCode] ?? [stationCode]
        return RouteTopology.allRoutes
            .filter { $0.stationCodes.contains(where: codes.contains) }
            .filter { TrainSystem(rawValue: $0.dataSource).map(stationSystems.contains) ?? false }
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                mapSnippetSection
                actionsSection
                routesServingSection
                departuresSection
                serviceAlertsSection
            }
            .padding()
            .animation(.easeInOut(duration: 0.3), value: viewModel.isLoadingDepartures)
            .animation(.easeInOut(duration: 0.3), value: viewModel.isLoadingAlerts)
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle(displayName)
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await viewModel.load(alertSupportedSystems: Self.alertSupportedSystems)
        }
        .refreshable {
            await viewModel.load(alertSupportedSystems: Self.alertSupportedSystems)
        }
        .sheet(item: $viewModel.selectedTrain) { train in
            NavigationStack {
                TrainDetailsView(
                    trainNumber: train.trainId,
                    fromStation: stationCode,
                    journeyDate: train.journeyDate,
                    dataSource: train.dataSource,
                    isSheet: true
                )
            }
            .presentationDetents([.large])
            .presentationDragIndicator(.visible)
        }
        .sheet(item: $viewModel.routeStatusContext) { context in
            RouteStatusView(context: context)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
    }

    // MARK: - Map snippet

    @ViewBuilder
    private var mapSnippetSection: some View {
        if let coord = coordinate {
            Map(initialPosition: .region(MKCoordinateRegion(
                center: coord,
                span: MKCoordinateSpan(latitudeDelta: 0.012, longitudeDelta: 0.012)
            ))) {
                Marker(displayName, coordinate: coord)
                    .tint(.orange)
            }
            .mapStyle(.standard(pointsOfInterest: .excludingAll))
            .frame(height: 140)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .allowsHitTesting(false)
        }
    }

    // MARK: - Actions (favorite / home / work)

    @ViewBuilder
    private var actionsSection: some View {
        let isFavorited = appState.isStationFavorited(code: stationCode)
        let isHome = ratSense.getHomeStation() == stationCode
        let isWork = ratSense.getWorkStation() == stationCode

        HStack(spacing: 8) {
            actionButton(
                title: isFavorited ? "Favorited" : "Favorite",
                systemImage: isFavorited ? "heart.fill" : "heart",
                isActive: isFavorited
            ) {
                appState.toggleFavoriteStation(code: stationCode, name: fullName)
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            }
            actionButton(
                title: isHome ? "Home" : "Set Home",
                systemImage: "house.fill",
                isActive: isHome
            ) {
                ratSense.setHomeStation(isHome ? nil : stationCode)
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            }
            actionButton(
                title: isWork ? "Work" : "Set Work",
                systemImage: "briefcase.fill",
                isActive: isWork
            ) {
                ratSense.setWorkStation(isWork ? nil : stationCode)
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            }
        }
    }

    @ViewBuilder
    private func actionButton(title: String, systemImage: String, isActive: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Image(systemName: systemImage)
                    .font(.system(size: 16, weight: .semibold))
                Text(title)
                    .font(.caption.bold())
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
            .background(RoundedRectangle(cornerRadius: 10)
                .fill(isActive ? Color.orange.opacity(0.25) : Color(.secondarySystemGroupedBackground)))
            .foregroundColor(isActive ? .orange : .primary)
        }
        .buttonStyle(.plain)
    }

    // MARK: - Departures (unified recent/upcoming around a NOW divider)

    /// Mirrors `RouteStatusView.departuresSection`: recent trains (oldest at top,
    /// dimmed), a NOW pill, then upcoming trains. Skeleton matches that view's
    /// 2-past / 2-future layout.
    @ViewBuilder
    private var departuresSection: some View {
        if viewModel.isLoadingDepartures {
            VStack(alignment: .leading, spacing: 12) {
                Text("Departures")
                    .font(.headline)

                ForEach(0..<2, id: \.self) { _ in skeletonRow.opacity(0.55) }
                NowDivider()
                ForEach(0..<2, id: \.self) { _ in skeletonRow }
            }
            .padding()
            .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
        } else if !viewModel.upcoming.isEmpty || !viewModel.recent.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Text("Departures")
                    .font(.headline)

                ForEach(Array(viewModel.recent.prefix(3).reversed())) { train in
                    Button { viewModel.selectedTrain = train } label: {
                        TrainRow(train: train, dataSource: train.dataSource)
                    }
                    .buttonStyle(.plain)
                    .opacity(0.55)
                }

                NowDivider()

                ForEach(viewModel.upcoming.prefix(3)) { train in
                    Button { viewModel.selectedTrain = train } label: {
                        TrainRow(train: train, dataSource: train.dataSource)
                    }
                    .buttonStyle(.plain)
                }

                if viewModel.upcoming.isEmpty {
                    Text("No more trains scheduled")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .frame(maxWidth: .infinity, alignment: .center)
                        .padding(.vertical, 4)
                }
            }
            .padding()
            .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
        } else {
            VStack(alignment: .leading, spacing: 12) {
                Text("Departures")
                    .font(.headline)

                Text("No departures available")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 4)
            }
            .padding()
            .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
        }
    }

    // MARK: - Service alerts

    @ViewBuilder
    private var serviceAlertsSection: some View {
        if hasAlertSupport && !viewModel.isLoadingAlerts && !viewModel.alerts.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Text("Service Alerts")
                    .font(.headline)

                ForEach(viewModel.alerts) { alert in
                    ServiceAlertCard(alert: alert)
                }
            }
            .padding()
            .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
        }
    }

    // MARK: - Routes serving

    @ViewBuilder
    private var routesServingSection: some View {
        if !routesServingStation.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Text("Routes Serving This Station")
                    .font(.headline)

                VStack(spacing: 8) {
                    ForEach(routesServingStation) { route in
                        Button {
                            viewModel.routeStatusContext = RouteStatusContext(
                                dataSource: route.dataSource,
                                lineId: route.id
                            )
                        } label: {
                            HStack(spacing: 10) {
                                routeBadge(for: route)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(displayName(for: route))
                                        .font(.subheadline.bold())
                                        .lineLimit(1)
                                    if let subtitle = route.terminalSubtitle {
                                        Text(subtitle)
                                            .font(.caption2)
                                            .foregroundColor(.secondary)
                                            .lineLimit(1)
                                    }
                                }
                                Spacer(minLength: 0)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(10)
                            .background(RoundedRectangle(cornerRadius: 8).fill(Color(.secondarySystemGroupedBackground)))
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .padding()
            .background(RoundedRectangle(cornerRadius: 12).fill(.ultraThinMaterial))
        }
    }

    // MARK: - Helpers

    /// Subway routes get the colored MTA bullet (e.g. orange "B"); non-subway
    /// routes get the system pill (NJT, AMK, LIRR, …). The bullet character is
    /// taken from the first char of `route.name`, which always begins with the
    /// line letter/number — e.g. "6X Pelham Bay Park Express" → "6",
    /// "S 42 St Shuttle" → "S".
    @ViewBuilder
    private func routeBadge(for route: RouteLine) -> some View {
        if route.dataSource == "SUBWAY", let first = route.name.first {
            SubwayLineChips(lines: [String(first)], size: 24)
        } else if let system = TrainSystem(rawValue: route.dataSource) {
            SystemPill(system: system, size: 24)
        }
    }

    /// For subway routes, strip the leading line designator (e.g. "6 ", "6X ",
    /// "S ") since `routeBadge` already renders it as a chip. Non-subway route
    /// names have no line prefix and are returned as-is.
    private func displayName(for route: RouteLine) -> String {
        guard route.dataSource == "SUBWAY",
              let spaceIndex = route.name.firstIndex(of: " ") else {
            return route.name
        }
        return String(route.name[route.name.index(after: spaceIndex)...])
    }

    private var skeletonRow: some View {
        HStack(spacing: 12) {
            ShimmerRect(width: 4, height: 40, cornerRadius: 2)
            VStack(alignment: .leading, spacing: 4) {
                ShimmerRect(width: 90, height: 16)
                ShimmerRect(width: 60, height: 12)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 4) {
                ShimmerRect(width: 60, height: 16)
                ShimmerRect(width: 50, height: 12)
            }
        }
        .padding(.vertical, 4)
        .padding(.horizontal, 10)
        .background(RoundedRectangle(cornerRadius: 8).fill(Color(.secondarySystemGroupedBackground)))
    }

    /// Data sources that publish service alerts. Mirrors the constant in
    /// `RouteStatusViewModel`; kept local to avoid coupling the two views.
    private static let alertSupportedSystems: Set<TrainSystem> = [.subway, .lirr, .mnr, .njt]
}

// MARK: - View Model

@MainActor
final class StationDetailsViewModel: ObservableObject {
    let stationCode: String

    @Published private(set) var upcoming: [TrainV2] = []
    @Published private(set) var recent: [TrainV2] = []
    @Published private(set) var alerts: [V2ServiceAlert] = []
    @Published private(set) var isLoadingDepartures = true
    @Published private(set) var isLoadingAlerts = true
    @Published var selectedTrain: TrainV2?
    @Published var routeStatusContext: RouteStatusContext?

    /// Match `RouteStatusViewModel.recentTrainsWindowMinutes` so the unified
    /// Departures section reads from the same window in both views.
    private static let recentWindowMinutes = 120

    init(stationCode: String) {
        self.stationCode = stationCode
    }

    func load(alertSupportedSystems: Set<TrainSystem>) async {
        let systems = Stations.systemsForStation(stationCode)
        async let departuresAndRecent: () = loadDepartures(systems: systems)
        async let alertsResult: () = loadAlerts(systems: systems, alertSupportedSystems: alertSupportedSystems)
        _ = await (departuresAndRecent, alertsResult)
    }

    // MARK: Departures

    private func loadDepartures(systems: Set<TrainSystem>) async {
        isLoadingDepartures = true
        defer { isLoadingDepartures = false }

        async let upcomingTask = fetchUpcoming(systems: systems)
        async let recentTask = fetchRecent(systems: systems)
        let (u, r) = await (upcomingTask, recentTask)
        upcoming = u
        recent = r
    }

    private func fetchUpcoming(systems: Set<TrainSystem>) async -> [TrainV2] {
        do {
            return try await APIService.shared.searchTrains(
                fromStationCode: stationCode,
                toStationCode: nil,
                date: nil,
                dataSources: systems.isEmpty ? nil : systems
            )
        } catch {
            return []
        }
    }

    private func fetchRecent(systems: Set<TrainSystem>) async -> [TrainV2] {
        do {
            return try await APIService.shared.searchRecentTrains(
                fromStationCode: stationCode,
                toStationCode: nil,
                windowMinutes: Self.recentWindowMinutes,
                dataSources: systems.isEmpty ? nil : systems
            )
        } catch {
            return []
        }
    }

    // MARK: Alerts

    private func loadAlerts(systems: Set<TrainSystem>, alertSupportedSystems: Set<TrainSystem>) async {
        isLoadingAlerts = true
        defer { isLoadingAlerts = false }

        let systemsToFetch = systems.intersection(alertSupportedSystems)
        guard !systemsToFetch.isEmpty else {
            alerts = []
            return
        }

        // Per-system relevant route IDs; filtering is scoped to each system
        // so an unmapped NJT lineId can't accidentally suppress all NJT alerts.
        let relevantRouteIdsBySystem = relevantGtfsRouteIdsBySystem()

        var collected: [V2ServiceAlert] = []
        await withTaskGroup(of: [V2ServiceAlert].self) { group in
            for system in systemsToFetch {
                let relevant = relevantRouteIdsBySystem[system] ?? []
                group.addTask {
                    do {
                        let alerts = try await APIService.shared.fetchServiceAlerts(dataSource: system.dataSource)
                        // No mapping for this system → show all of its alerts (better
                        // to over-show than to silently drop).
                        if relevant.isEmpty { return alerts }
                        return alerts.filter {
                            !Set($0.affectedRouteIds).isDisjoint(with: relevant)
                        }
                    } catch {
                        return []
                    }
                }
            }
            for await result in group {
                collected.append(contentsOf: result)
            }
        }

        // Active first, then upcoming; chronological within each group.
        alerts = collected.sorted {
            if $0.isActiveNow != $1.isActiveNow { return $0.isActiveNow }
            return $0.earliestStartEpoch < $1.earliestStartEpoch
        }
    }

    /// Per-system GTFS route IDs for routes touching this station, used to scope
    /// alerts to lines actually serving the station (e.g., a Penn user shouldn't
    /// see Brooklyn-only G-train alerts).
    private func relevantGtfsRouteIdsBySystem() -> [TrainSystem: Set<String>] {
        var map: [TrainSystem: Set<String>] = [:]
        let codes = Stations.stationEquivalents[stationCode] ?? [stationCode]
        let routes = RouteTopology.allRoutes.filter { $0.stationCodes.contains(where: codes.contains) }
        for route in routes {
            guard let system = TrainSystem(rawValue: route.dataSource) else { continue }
            let context = RouteStatusContext(dataSource: route.dataSource, lineId: route.id)
            map[system, default: []].formUnion(context.gtfsRouteIds)
        }
        return map
    }
}

// MARK: - Context Menu Helper

extension View {
    /// Adds a context menu entry that pushes `StationDetailsView` for the given
    /// station code onto the supplied navigation path. Used on station rows in
    /// the pickers, where the primary tap action selects the station for trip
    /// planning and the secondary action exposes details. A nil code is a
    /// no-op so callers don't need to wrap the modifier in a conditional.
    @ViewBuilder
    func stationDetailsContextMenu(
        code: String?,
        path: Binding<NavigationPath>
    ) -> some View {
        if let code {
            contextMenu {
                Button {
                    path.wrappedValue.append(NavigationDestination.stationDetails(stationCode: code))
                } label: {
                    Label("View Station Details", systemImage: "info.circle")
                }
            }
        } else {
            self
        }
    }
}
