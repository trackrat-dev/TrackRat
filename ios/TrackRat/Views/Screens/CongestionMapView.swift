import SwiftUI
import MapKit
import UIKit
import Combine
import ActivityKit

struct CongestionMapView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.scenePhase) private var scenePhase
    @ObservedObject private var subscriptionService = SubscriptionService.shared
    @StateObject private var viewModel = CongestionMapViewModel()
    @State private var region = MKCoordinateRegion.newarkPennDefault // Updated to selected systems on appear
    @State private var routeStatusContext: RouteStatusContext?
    @State private var selectedIndividualSegment: IndividualJourneySegment?
    @State private var showingFilters = false
    @State private var timeWindow = 1
    @State private var selectedDataSource: String = "All"
    @State private var showingLayers = false
    @State private var showingPaywall = false

    var body: some View {
        ZStack {
            // Map
            // Note: segments/individualSegments arrays are controlled by applyDisplayModeFilter()
            // which sets them based on highlightMode - no need for ternary checks here
            SystemCongestionMapView(
                region: $region,
                segments: viewModel.segments,
                individualSegments: viewModel.individualSegments,
                stations: viewModel.showStations ? (viewModel.showRoutes ? viewModel.routeStations : viewModel.stations) : [],
                showRoutes: viewModel.showRoutes,
                selectedSystems: appState.selectedSystems,
                highlightMode: viewModel.highlightMode,
                onSegmentTap: { segment in
                    guard appState.enableSegmentTap else { return }
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
                onIndividualSegmentTap: { individualSegment in
                    guard appState.enableSegmentTap else { return }
                    selectedIndividualSegment = individualSegment
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                }
            )
            .ignoresSafeArea()

            // Controls overlay
            VStack {
                // Header
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Train Traffic")
                            .font(.largeTitle)
                            .fontWeight(.bold)

                        if viewModel.isLoading {
                            Text("Loading...")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        } else {
                            Text(headerSubtitle)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }

                    Spacer()

                    HStack(spacing: 12) {
                        // Layers button
                        Button {
                            withAnimation(.easeInOut(duration: 0.2)) {
                                showingLayers.toggle()
                            }
                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        } label: {
                            Image(systemName: "square.3.layers.3d")
                                .font(.title2)
                                .foregroundColor(showingLayers ? .white : .orange)
                                .padding(10)
                                .background {
                                    if showingLayers {
                                        Circle().fill(Color.orange)
                                    } else {
                                        Circle().fill(.ultraThinMaterial)
                                    }
                                }
                        }

                        // Filter button
                        Button {
                            showingFilters.toggle()
                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        } label: {
                            Image(systemName: "slider.horizontal.3")
                                .font(.title2)
                                .foregroundColor(.orange)
                                .padding(10)
                                .background(
                                    Circle()
                                        .fill(.ultraThinMaterial)
                                )
                        }
                    }
                }
                .padding(.horizontal)
                .padding(.top, 60)
                .background(
                    LinearGradient(
                        colors: [.black, .clear],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                    .ignoresSafeArea()
                )

                Spacer()

                // Bottom panel: Layers + Legend
                VStack(spacing: 12) {
                    // Layer Controls (collapsible)
                    if showingLayers {
                        HStack {
                            Spacer()
                            layerControlsView
                        }
                        .transition(.opacity.combined(with: .move(edge: .bottom)))
                    }

                    // Segment Legend (only when highlighting is visible)
                    if viewModel.highlightMode != .off {
                        segmentLegendView
                    }
                }
                .padding()
            }
        }
        .sheet(isPresented: $showingFilters) {
            FilterSheet(
                timeWindow: $timeWindow,
                selectedDataSource: $selectedDataSource,
                onApply: {
                    Task {
                        await viewModel.fetchCongestionData(
                            timeWindowHours: timeWindow,
                            dataSource: selectedDataSource == "All" ? nil : selectedDataSource
                        )
                    }
                }
            )
        }
        .sheet(item: $routeStatusContext) { context in
            RouteStatusView(context: context)
        }
        .sheet(item: $selectedIndividualSegment) { segment in
            TrainDetailsView(
                trainNumber: segment.trainId,
                fromStation: segment.fromStation,
                journeyDate: segment.actualDeparture,
                dataSource: segment.dataSource,
                isSheet: true
            )
            .presentationDetents([.large])
            .presentationDragIndicator(.visible)
        }
        .sheet(isPresented: $showingPaywall) {
            PaywallView(context: .trainSystems)
        }
        .task {
            await viewModel.fetchCongestionData()
            viewModel.startAutoRefresh()
        }
        .onChange(of: appState.selectedSystems) { _, newSystems in
            viewModel.setSelectedSystems(newSystems)
            // Re-center map to show the newly selected systems
            withAnimation(.easeInOut(duration: 0.3)) {
                region = newSystems.combinedMapRegion
            }
        }
        .onChange(of: appState.mapHighlightMode) { _, newMode in
            viewModel.highlightMode = newMode
        }
        .onChange(of: appState.showMapStations) { _, newValue in
            viewModel.showStations = newValue
        }
        .onAppear {
            // Sync AppState settings to ViewModel on appear
            viewModel.setSelectedSystems(appState.selectedSystems)
            viewModel.highlightMode = appState.mapHighlightMode
            viewModel.showStations = appState.showMapStations
            // Set initial region based on selected systems
            region = appState.selectedSystems.combinedMapRegion
        }
        .onDisappear {
            viewModel.stopAutoRefresh()
        }
        .onChange(of: scenePhase) { _, newPhase in
            switch newPhase {
            case .active:
                viewModel.refreshIfStale()
                viewModel.startAutoRefresh()
            case .background, .inactive:
                viewModel.stopAutoRefresh()
            @unknown default:
                break
            }
        }
    }

    // MARK: - Computed Properties

    private var headerSubtitle: String {
        var parts: [String] = []
        if viewModel.highlightMode != .off && !viewModel.segments.isEmpty {
            parts.append("\(viewModel.segments.count) segments")
        }
        if viewModel.showRoutes {
            // Count only routes for selected systems
            let selectedSystemStrings = appState.selectedSystems.asRawStrings
            let filteredRouteCount = RouteTopology.allRoutes.filter { selectedSystemStrings.contains($0.dataSource) }.count
            parts.append("\(filteredRouteCount) routes")
        }
        if viewModel.showStations {
            let stationCount = viewModel.showRoutes ? viewModel.routeStations.count : viewModel.stations.count
            if stationCount > 0 {
                parts.append("\(stationCount) stations")
            }
        }
        return parts.isEmpty ? "No layers visible" : parts.joined(separator: " · ")
    }

    // MARK: - Layer Controls View

    private var layerControlsView: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Layers")
                .font(.headline)
                .fontWeight(.semibold)

            // Segment visibility toggle (on/off — per-segment coloring is automatic)
            LayerToggleButton(
                label: "Segments",
                icon: viewModel.highlightMode != .off ? "waveform.path.ecg" : "eye.slash",
                isOn: viewModel.highlightMode != .off,
                detail: viewModel.highlightMode != .off ? "On" : "Off"
            ) {
                let wasOff = viewModel.highlightMode == .off
                viewModel.cycleHighlightMode()
                appState.mapHighlightMode = viewModel.highlightMode
                UIImpactFeedbackGenerator(style: .light).impactOccurred()

                // Reload congestion data when turning on (from off state)
                if wasOff && viewModel.highlightMode != .off {
                    Task {
                        await viewModel.fetchCongestionData()
                    }
                }
            }

            // Detail mode toggle (Summary vs Trains) - only show when segments are visible
            if viewModel.highlightMode != .off {
                LayerToggleButton(
                    label: "Detail",
                    icon: viewModel.detailMode.iconName,
                    isOn: viewModel.detailMode == .trains,
                    detail: viewModel.detailMode.rawValue
                ) {
                    viewModel.cycleDetailMode()
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                }
            }

            // Routes toggle
            LayerToggleButton(
                label: "Routes",
                icon: "point.topleft.down.to.point.bottomright.curvepath",
                isOn: viewModel.showRoutes,
                detail: viewModel.showRoutes ? "On" : "Off"
            ) {
                viewModel.showRoutes.toggle()
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            }

            // Stations toggle
            LayerToggleButton(
                label: "Stations",
                icon: "mappin.circle.fill",
                isOn: viewModel.showStations,
                detail: viewModel.showStations ? "On" : "Off"
            ) {
                viewModel.showStations.toggle()
                appState.showMapStations = viewModel.showStations
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            }

            Divider()
                .background(Color.white.opacity(0.2))

            // Train Systems section
            Text("Train Systems")
                .font(.subheadline)
                .foregroundColor(.secondary)

            ForEach(TrainSystem.allCases, id: \.self) { system in
                let isSelected = appState.isSystemSelected(system)
                let atFreeLimit = !subscriptionService.isPro
                    && !isSelected
                    && appState.selectedSystems.count >= SubscriptionService.freeTrainSystemLimit
                SystemToggleButton(
                    system: system,
                    isSelected: isSelected,
                    action: {
                        if atFreeLimit {
                            showingPaywall = true
                        } else {
                            appState.toggleSystem(system)
                        }
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                    }
                )
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(.ultraThinMaterial)
        )
        .fixedSize(horizontal: true, vertical: false)
    }

    // MARK: - Segment Legend View

    @ViewBuilder
    private var segmentLegendView: some View {
        if viewModel.highlightMode != .off {
            let dataSources = Set(viewModel.segments.map(\.dataSource))
            let hasFrequencySystems = dataSources.contains { TrainSystem(rawValue: $0)?.preferredHighlightMode == .health }
            let hasDelaySystems = dataSources.contains { TrainSystem(rawValue: $0)?.preferredHighlightMode != .health }

            VStack(alignment: .leading, spacing: 12) {
                if hasFrequencySystems {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Service Health")
                            .trackRatSectionHeader()

                        HStack(spacing: 16) {
                            LegendItem(color: .green, label: "Healthy")
                            LegendItem(color: .yellow, label: "Moderate")
                            LegendItem(color: .orange, label: "Reduced")
                            LegendItem(color: .red, label: "Severe")
                        }

                        if let summary = frequencySummaryText {
                            Text(summary)
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        } else {
                            Text("Train count vs typical for this time")
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                    }
                }

                if hasDelaySystems {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Delay Levels")
                            .trackRatSectionHeader()

                        HStack(spacing: 16) {
                            LegendItem(color: .green, label: "Normal")
                            LegendItem(color: .yellow, label: "Moderate")
                            LegendItem(color: .orange, label: "Heavy")
                            LegendItem(color: .red, label: "Severe")
                        }

                        LegendItem(color: .red, label: "Cancellations")
                    }
                }
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(.ultraThinMaterial)
            )
        }
    }

    /// Summarize headway across visible segments for the legend subtitle
    private var frequencySummaryText: String? {
        let segmentsWithData = viewModel.segments.filter { $0.hasFrequencyData }
        guard !segmentsWithData.isEmpty else { return nil }

        let headways = segmentsWithData.compactMap {
            $0.currentHeadwayMinutes(timeWindowHours: timeWindow)
        }
        guard !headways.isEmpty else { return nil }

        let avgHeadway = Int((headways.reduce(0, +) / Double(headways.count)).rounded())
        let totalTrains = segmentsWithData.compactMap(\.trainCount).reduce(0, +)

        if avgHeadway <= 1 {
            return "\(totalTrains) trains · Avg every ~1 min"
        }
        return "\(totalTrains) trains · Avg every ~\(avgHeadway) min"
    }
}

// MARK: - Layer Toggle Button

private struct LayerToggleButton: View {
    let label: String
    let icon: String
    let isOn: Bool
    let detail: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.body)
                    .foregroundColor(isOn ? .orange : .secondary)
                    .frame(width: 20)

                Text(label)
                    .font(.subheadline)
                    .foregroundColor(.primary)

                Text(detail)
                    .font(.caption)
                    .foregroundColor(isOn ? .orange : .secondary)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 3)
                    .background(
                        Capsule()
                            .fill(isOn ? Color.orange.opacity(0.2) : Color.secondary.opacity(0.1))
                    )
            }
            .padding(.vertical, 4)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - System Toggle Button

private struct SystemToggleButton: View {
    let system: TrainSystem
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                Image(systemName: system.icon)
                    .font(.body)
                    .foregroundColor(isSelected ? .orange : .secondary)
                    .frame(width: 20)

                VStack(alignment: .leading, spacing: 1) {
                    Text(system.displayName)
                        .font(.subheadline)
                        .foregroundColor(.primary)

                }

                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.body)
                    .foregroundColor(isSelected ? .orange : .secondary.opacity(0.5))
            }
            .padding(.vertical, 4)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - View Model

/// Display mode for individual vs aggregated segments (when highlighting is on)
enum SegmentDetailMode: String, CaseIterable {
    case summary = "Summary"
    case trains = "Trains"

    var next: SegmentDetailMode {
        switch self {
        case .summary: return .trains
        case .trains: return .summary
        }
    }

    var iconName: String {
        switch self {
        case .summary: return "chart.bar.fill"
        case .trains: return "train.side.front.car"
        }
    }
}

@MainActor
class CongestionMapViewModel: ObservableObject {
    // MARK: - Layer Visibility
    // Note: These are synced from AppState on view appear via onChange handlers
    @Published var highlightMode: SegmentHighlightMode = .off
    @Published var detailMode: SegmentDetailMode = .summary  // Summary vs individual trains
    @Published var showRoutes: Bool = false  // Default: Off
    @Published var showStations: Bool = false  // Default: Off

    // MARK: - Data
    @Published var segments: [CongestionSegment] = []
    @Published var individualSegments: [IndividualJourneySegment] = []
    @Published var stations: [MapStation] = []
    @Published var routeStations: [MapStation] = []  // Stations from route topology
    @Published var isLoading = false
    @Published var error: String?
    @Published var lastTimeWindowHours: Int = 1  // Track fetched time window for headway calc

    // MARK: - Internal State
    private var allAggregatedSegments: [CongestionSegment] = []
    private var allIndividualSegments: [IndividualJourneySegment] = []
    private var allStations: [MapStation] = []
    private var allRouteStations: [MapStation] = []

    // Current journey filter
    private var selectedRoute: TripPair?
    private var journeyStations: [String] = []
    private var journeyDataSource: String = ""

    // System filter
    private var selectedSystems: Set<TrainSystem> = .all

    // Live Activity observation
    private var liveActivityCancellables = Set<AnyCancellable>()

    // MARK: - Auto-Refresh
    private static let refreshInterval: TimeInterval = 60
    private var refreshTimer: Timer?
    private var lastFetchDate: Date?
    private var lastDataSource: String?

    init() {
        // Don't start loading data immediately - wait for explicit trigger
        // This prevents blocking the UI during app startup and navigation
        print("🚦 CongestionMapViewModel init - data loading deferred")

        // Load route topology stations (immediate, client-side)
        loadRouteTopologyStations()

        // Observe Live Activity state changes
        observeLiveActivityState()
    }

    // MARK: - Auto-Refresh Methods

    func startAutoRefresh() {
        guard refreshTimer == nil else { return }
        refreshTimer = Timer.scheduledTimer(withTimeInterval: Self.refreshInterval, repeats: true) { [weak self] _ in
            Task { [weak self] in
                await self?.fetchCongestionData(
                    timeWindowHours: self?.lastTimeWindowHours ?? 1,
                    dataSource: self?.lastDataSource
                )
            }
        }
        print("🚦 Auto-refresh started (\(Int(Self.refreshInterval))s interval)")
    }

    func stopAutoRefresh() {
        refreshTimer?.invalidate()
        refreshTimer = nil
    }

    /// Fetches immediately if data is older than the refresh interval (e.g., after returning from background)
    func refreshIfStale() {
        guard let lastFetch = lastFetchDate else { return }
        if Date().timeIntervalSince(lastFetch) > Self.refreshInterval {
            Task {
                await fetchCongestionData(
                    timeWindowHours: lastTimeWindowHours,
                    dataSource: lastDataSource
                )
            }
        }
    }

    /// Loads all stations from route topology (client-side, no API call)
    private func loadRouteTopologyStations() {
        allRouteStations = RouteTopology.allStationCodes.compactMap { code in
            guard let coord = Stations.getCoordinates(for: code) else { return nil }
            let name = Stations.stationName(forCode: code) ?? code
            return MapStation(code: code, name: name, coordinate: coord)
        }
        // Apply system filter to get visible stations
        routeStations = allRouteStations.filter { station in
            Stations.isStationVisible(station.code, withSystems: selectedSystems)
        }
        print("🗺️ Loaded \(allRouteStations.count) route topology stations, \(routeStations.count) visible with current systems")
    }

    /// Updates the selected systems filter and reapplies all filtering
    func setSelectedSystems(_ systems: Set<TrainSystem>) {
        let changed = systems != selectedSystems
        selectedSystems = systems
        guard changed else { return }
        print("🚦 Selected systems updated: \(systems.map(\.rawValue).sorted().joined(separator: ", "))")

        // Refilter route stations
        routeStations = allRouteStations.filter { station in
            Stations.isStationVisible(station.code, withSystems: selectedSystems)
        }

        // Reapply all filters
        applyDisplayModeFilter()
    }

    private func observeLiveActivityState() {
        let liveActivityService = LiveActivityService.shared

        // Observe both isActivityActive and journeyStationCodes
        Publishers.CombineLatest(
            liveActivityService.$isActivityActive,
            liveActivityService.$journeyStationCodes
        )
        .receive(on: DispatchQueue.main)
        .sink { [weak self] isActive, stationCodes in
            self?.handleLiveActivityStateChange(isActive: isActive, stationCodes: stationCodes)
        }
        .store(in: &liveActivityCancellables)
    }

    private func handleLiveActivityStateChange(isActive: Bool, stationCodes: [String]) {
        if isActive && !stationCodes.isEmpty {
            // Live Activity is active - apply route filter with system lock
            if let activity = LiveActivityService.shared.currentActivity {
                let attributes = activity.attributes
                let dataSource = LiveActivityService.shared.journeyDataSource
                let route = TripPair(
                    departureCode: attributes.originStationCode,
                    departureName: attributes.origin,
                    destinationCode: attributes.destinationStationCode,
                    destinationName: attributes.destination
                )
                // Expand skip-stop gaps so intermediate canonical segments match
                let expandedCodes = RouteTopology.expandStationCodes(stationCodes, dataSource: dataSource)
                setRouteFilter(route, journeyStations: expandedCodes, dataSource: dataSource)
                print("🗺️ Applied route filter for Live Activity: \(attributes.originStationCode) → \(attributes.destinationStationCode) [\(dataSource)] (\(stationCodes.count) stops → \(expandedCodes.count) expanded)")
            }
        } else {
            // No active Live Activity - clear filter to show all segments
            clearRouteFilter()
            print("🗺️ Cleared route filter - showing all segments")
        }
    }
    
    func fetchCongestionDataIfNeeded(timeWindowHours: Int = 1, dataSource: String? = nil) async {
        // Only fetch if we don't already have data and we're not currently loading
        guard allAggregatedSegments.isEmpty && !isLoading else {
            print("🚦 Skipping congestion data fetch - already have data or loading")
            return
        }
        
        await fetchCongestionData(timeWindowHours: timeWindowHours, dataSource: dataSource)
    }
    
    func fetchCongestionData(timeWindowHours: Int = 1, dataSource: String? = nil) async {
        // Prevent duplicate fetches if already loading
        guard !isLoading else {
            print("🚦 Skipping duplicate fetch - already loading")
            return
        }
        
        print("🚦 Starting congestion data fetch (timeWindow: \(timeWindowHours), dataSource: \(dataSource ?? "All"))")
        isLoading = true
        error = nil
        lastTimeWindowHours = timeWindowHours
        lastDataSource = dataSource

        do {
            // Determine maxPerSegment based on detail mode (fetch individual trains only if showing)
            let maxPerSegment: Int
            switch detailMode {
            case .summary:
                maxPerSegment = 0
            case .trains:
                maxPerSegment = 100
            }
            
            let response = try await APIService.shared.fetchCongestionData(
                timeWindowHours: timeWindowHours,
                maxPerSegment: maxPerSegment,
                dataSource: dataSource
            )
            
            print("🚦 API response received: \(response.aggregatedSegments.count) aggregated, \(response.individualSegments.count) individual segments")

            // Debug: Print first few segments to see what we're getting
            if !response.individualSegments.isEmpty {
                print("🚦 Sample individual segments:")
                for (index, segment) in response.individualSegments.prefix(3).enumerated() {
                    print("  \(index): \(segment.fromStation) → \(segment.toStation) (\(segment.trainId))")
                }
            }
            if !response.aggregatedSegments.isEmpty {
                print("🚦 Sample aggregated segments:")
                for (index, segment) in response.aggregatedSegments.prefix(3).enumerated() {
                    print("  \(index): \(segment.fromStation) → \(segment.toStation)")
                }
            }

            // OPTIMIZATION: Process station data in background to avoid blocking UI
            // This moves the heavy coordinate lookups off the main thread
            let processedData = await Task.detached(priority: .userInitiated) {
                // Store segments (immutable copy for background processing)
                let aggregatedSegments = response.aggregatedSegments
                let individualSegments = response.individualSegments

                // Extract unique stations from both segment types
                var stationMap: [String: MapStation] = [:]

                // From aggregated segments
                for segment in aggregatedSegments {
                    if let coords = Stations.getCoordinates(for: segment.fromStation) {
                        stationMap[segment.fromStation] = MapStation(
                            code: segment.fromStation,
                            name: segment.fromStationDisplayName,
                            coordinate: coords
                        )
                    }
                    if let coords = Stations.getCoordinates(for: segment.toStation) {
                        stationMap[segment.toStation] = MapStation(
                            code: segment.toStation,
                            name: segment.toStationDisplayName,
                            coordinate: coords
                        )
                    }
                }

                // From individual segments
                for segment in individualSegments {
                    if let coords = Stations.getCoordinates(for: segment.fromStation) {
                        stationMap[segment.fromStation] = MapStation(
                            code: segment.fromStation,
                            name: segment.fromStationName,
                            coordinate: coords
                        )
                    } else {
                        print("🚦 ⚠️ No coordinates for station: \(segment.fromStation)")
                    }
                    if let coords = Stations.getCoordinates(for: segment.toStation) {
                        stationMap[segment.toStation] = MapStation(
                            code: segment.toStation,
                            name: segment.toStationName,
                            coordinate: coords
                        )
                    } else {
                        print("🚦 ⚠️ No coordinates for station: \(segment.toStation)")
                    }
                }

                let stations = Array(stationMap.values)
                print("🚦 Processed \(stations.count) stations from segments in background")

                return (aggregatedSegments, individualSegments, stations)
            }.value

            // Update state on main thread with processed data
            allAggregatedSegments = processedData.0
            allIndividualSegments = processedData.1
            allStations = processedData.2

            // Filter based on current display mode
            applyDisplayModeFilter()
            lastFetchDate = Date()

        } catch {
            self.error = error.localizedDescription
            print("🚦 Failed to fetch congestion data: \(error)")
        }
        
        isLoading = false
        print("🚦 Congestion data fetch completed. Final segments: \(segments.count)")
    }
    
    /// Cycles the congestion mode (off -> aggregated -> individual -> off)
    /// Cycle through highlight modes: Off → Health → Delays → Off
    func cycleHighlightMode() {
        highlightMode = highlightMode.next
        print("🚦 Highlight mode changed to: \(highlightMode.displayName)")
        // Defer filter application to let UI animations complete
        applyDisplayModeFilterDeferred()
    }

    /// Toggle between Summary and Trains detail modes
    func cycleDetailMode() {
        detailMode = detailMode.next
        print("🚦 Detail mode changed to: \(detailMode.rawValue)")
        applyDisplayModeFilterDeferred()
    }


    /// Applies display mode filter with a delay to prevent UI lag during button animations
    private func applyDisplayModeFilterDeferred() {
        Task { @MainActor in
            // Small delay to let button animation complete
            try? await Task.sleep(nanoseconds: 150_000_000) // 150ms
            applyDisplayModeFilter()
        }
    }

    private func applyDisplayModeFilter() {
        // When route filter is active (Live Activity), lock to the journey's train system.
        // Otherwise use the user's selected systems.
        let effectiveSystems: Set<TrainSystem>
        if selectedRoute != nil, !journeyDataSource.isEmpty,
           let system = TrainSystem(rawValue: journeyDataSource) {
            effectiveSystems = Set([system])
        } else {
            effectiveSystems = selectedSystems
        }
        let effectiveSystemStrings = effectiveSystems.asRawStrings

        // First filter by effective systems
        let systemFilteredAggregated = allAggregatedSegments.filter { effectiveSystemStrings.contains($0.dataSource) }
        let systemFilteredIndividual = allIndividualSegments.filter { effectiveSystemStrings.contains($0.dataSource) }
        let systemFilteredStations = allStations.filter { Stations.isStationVisible($0.code, withSystems: effectiveSystems) }

        // Update route station visibility to match effective systems
        routeStations = allRouteStations.filter { station in
            Stations.isStationVisible(station.code, withSystems: effectiveSystems)
        }

        // Then apply route filter if we have one
        let filteredAggregated = selectedRoute != nil ? filterSegmentsForRoute(systemFilteredAggregated) : systemFilteredAggregated
        let filteredIndividual = selectedRoute != nil ? filterIndividualSegmentsForRoute(systemFilteredIndividual) : systemFilteredIndividual

        // Apply highlight mode
        if highlightMode == .off {
            // Hide all segment data
            segments = []
            individualSegments = []
            stations = systemFilteredStations
            print("🚦 Segments hidden")
        } else {
            // Show segments based on detail mode
            switch detailMode {
            case .summary:
                // Show aggregated segments only
                segments = filteredAggregated
                individualSegments = []
                stations = systemFilteredStations
                print("🚦 Applied summary filter: \(segments.count) aggregated segments, mode: \(highlightMode.displayName)")

            case .trains:
                // Show individual journey segments
                segments = filteredAggregated // Keep aggregated for reference (dimmed)
                individualSegments = filteredIndividual
                stations = systemFilteredStations
                print("🚦 Applied trains filter: \(individualSegments.count) individual segments, mode: \(highlightMode.displayName)")
            }
        }
    }
    
    func setRouteFilter(_ route: TripPair?, journeyStations: [String] = [], dataSource: String = "") {
        print("🚦 Setting route filter: \(route?.departureCode ?? "none") → \(route?.destinationCode ?? "none") [\(dataSource)]")
        print("🚦 Journey stations: \(journeyStations)")

        self.selectedRoute = route
        self.journeyStations = journeyStations
        self.journeyDataSource = dataSource

        // Re-apply filters with the new route
        applyDisplayModeFilter()
    }

    func clearRouteFilter() {
        setRouteFilter(nil, journeyStations: [])
    }
    
    private func filterSegmentsForRoute(_ segments: [CongestionSegment]) -> [CongestionSegment] {
        guard let route = selectedRoute, !journeyStations.isEmpty else {
            return segments
        }
        
        print("🚦 Filtering \(segments.count) aggregated segments for route \(route.departureCode) → \(route.destinationCode)")
        
        let filtered = segments.filter { segment in
            // Find indices of from and to stations in the journey
            guard let fromIndex = journeyStations.firstIndex(of: segment.fromStation),
                  let toIndex = journeyStations.firstIndex(of: segment.toStation) else {
                return false
            }
            
            // Include only consecutive segments (exact journey path)
            return toIndex == fromIndex + 1
        }

        print("🚦 Filtered aggregated segments: \(filtered.count) segments for journey")
        return filtered
    }
    
    private func filterIndividualSegmentsForRoute(_ segments: [IndividualJourneySegment]) -> [IndividualJourneySegment] {
        guard let route = selectedRoute, !journeyStations.isEmpty else {
            return segments
        }
        
        print("🚦 Filtering \(segments.count) individual segments for route \(route.departureCode) → \(route.destinationCode)")
        
        let filtered = segments.filter { segment in
            // Find indices of from and to stations in the journey
            guard let fromIndex = journeyStations.firstIndex(of: segment.fromStation),
                  let toIndex = journeyStations.firstIndex(of: segment.toStation) else {
                return false
            }
            
            // Include only consecutive segments (exact journey path)
            return toIndex == fromIndex + 1
        }

        print("🚦 Filtered individual segments: \(filtered.count) segments for journey")
        return filtered
    }
    
}

// MARK: - Supporting Views

struct StationPin: View {
    let station: MapStation
    
    var body: some View {
        VStack(spacing: 0) {
            Image(systemName: "mappin.circle.fill")
                .font(.title)
                .foregroundColor(.orange)
            
            Text(station.code)
                .font(.caption2)
                .fontWeight(.semibold)
                .foregroundColor(.white)
                .padding(.horizontal, 4)
                .padding(.vertical, 2)
                .background(
                    Capsule()
                        .fill(.black.opacity(0.7))
                )
        }
    }
}

struct LegendItem: View {
    let color: Color
    let label: String
    
    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(color)
                .frame(width: 10, height: 10)
            Text(label)
                .font(.caption2)
                .foregroundColor(.primary)
        }
    }
}

struct FilterSheet: View {
    @Binding var timeWindow: Int
    @Binding var selectedDataSource: String
    @Environment(\.dismiss) private var dismiss
    let onApply: () -> Void
    
    var body: some View {
        NavigationStack {
            Form {
                Section("Time Window") {
                    Picker("Hours", selection: $timeWindow) {
                        Text("1 hour").tag(1)
                        Text("3 hours").tag(3)
                        Text("6 hours").tag(6)
                        Text("12 hours").tag(12)
                    }
                    .pickerStyle(.segmented)
                }

                Section("Data Source") {
                    Picker("Source", selection: $selectedDataSource) {
                        Text("All").tag("All")
                        ForEach(TrainSystem.allCases) { system in
                            Text(system.displayName).tag(system.rawValue)
                        }
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .background(.ultraThinMaterial)
            .navigationTitle("Filter Options")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(.ultraThinMaterial, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                    .foregroundColor(.white)
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Apply") {
                        onApply()
                        dismiss()
                    }
                    .fontWeight(.semibold)
                    .foregroundColor(.orange)
                }
            }
        }
        .preferredColorScheme(.dark)
    }
}



// MARK: - MapKit-based System Congestion Map View
struct SystemCongestionMapView: UIViewRepresentable {
    @Binding var region: MKCoordinateRegion
    let segments: [CongestionSegment]
    let individualSegments: [IndividualJourneySegment]
    let stations: [MapStation]
    let showRoutes: Bool
    let selectedSystems: Set<TrainSystem>
    let highlightMode: SegmentHighlightMode
    let onSegmentTap: (CongestionSegment) -> Void
    let onIndividualSegmentTap: ((IndividualJourneySegment) -> Void)?

    func makeUIView(context: Context) -> MKMapView {
        let mapView = MKMapView()
        mapView.delegate = context.coordinator
        mapView.showsUserLocation = true
        mapView.userTrackingMode = .none

        // Configure map appearance
        mapView.mapType = .standard
        mapView.showsCompass = true
        mapView.showsScale = true

        // Add tap gesture recognizer for polyline interaction
        let tapGesture = UITapGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.handleMapTap(_:)))
        mapView.addGestureRecognizer(tapGesture)

        return mapView
    }
    
    func updateUIView(_ mapView: MKMapView, context: Context) {
        // Update region if needed
        let currentRegion = mapView.region
        let threshold: Double = 0.01
        
        if abs(currentRegion.center.latitude - region.center.latitude) > threshold ||
           abs(currentRegion.center.longitude - region.center.longitude) > threshold ||
           abs(currentRegion.span.latitudeDelta - region.span.latitudeDelta) > threshold ||
           abs(currentRegion.span.longitudeDelta - region.span.longitudeDelta) > threshold {
            mapView.setRegion(region, animated: true)
        }
        
        // Build desired overlay states (include congestionLevel to catch visual changes)
        let desiredAggregatedState = Set(segments.map { OverlayIdentity(segmentID: $0.id, congestionLevel: $0.congestionLevel) })
        let desiredIndividualState = Set(individualSegments.map { OverlayIdentity(segmentID: $0.id, congestionLevel: String($0.congestionFactor)) })

        // Check if anything changed (congestion, routes, stations, systems, or highlight mode)
        let congestionChanged = desiredAggregatedState != context.coordinator.currentAggregatedOverlayState ||
                               desiredIndividualState != context.coordinator.currentIndividualOverlayState
        let routesChanged = showRoutes != context.coordinator.routesVisible
        let desiredStationCodes = Set(stations.map { $0.code })
        let stationsChanged = desiredStationCodes != context.coordinator.currentStationCodes
        let systemsChanged = selectedSystems != context.coordinator.currentSelectedSystems
        let highlightModeChanged = highlightMode != context.coordinator.highlightMode

        // Early exit if nothing changed
        guard congestionChanged || routesChanged || stationsChanged || systemsChanged || highlightModeChanged else {
            return
        }

        // If highlight mode changed, update existing overlay renderers
        if highlightModeChanged {
            context.coordinator.highlightMode = highlightMode
            // Update aggregated segment colors
            for overlay in context.coordinator.aggregatedOverlays {
                if let renderer = mapView.renderer(for: overlay) as? MKPolylineRenderer,
                   let segment = overlay.segment {
                    var color = context.coordinator.getColorForSegmentPublic(segment)
                    if segment.cancellationRate > 20 {
                        color = UIColor.systemRed
                    } else if segment.cancellationRate > 10 {
                        color = context.coordinator.escalateColorPublic(color)
                    }
                    renderer.strokeColor = color
                }
            }
            // Update individual segment colors
            for (_, overlay) in context.coordinator.individualOverlayMap {
                if let renderer = mapView.renderer(for: overlay) as? MKPolylineRenderer,
                   let segment = overlay.individualSegment,
                   !segment.isCancelled {
                    renderer.strokeColor = context.coordinator.getColorForIndividualSegmentPublic(segment)
                }
            }
        }

        // Diff individual overlays
        let individualToRemove = context.coordinator.currentIndividualOverlayState.subtracting(desiredIndividualState)
        let individualToAdd = desiredIndividualState.subtracting(context.coordinator.currentIndividualOverlayState)

        // Rebuild aggregated overlays when any segment changed (merging makes incremental updates impractical)
        let aggregatedChanged = desiredAggregatedState != context.coordinator.currentAggregatedOverlayState
        if aggregatedChanged {
            if !context.coordinator.aggregatedOverlays.isEmpty {
                mapView.removeOverlays(context.coordinator.aggregatedOverlays)
                context.coordinator.aggregatedOverlays = []
            }

            let newOverlays = buildMergedAggregatedOverlays(from: segments, isDimmed: !individualSegments.isEmpty)
            if !newOverlays.isEmpty {
                mapView.addOverlays(newOverlays)
            }
            context.coordinator.aggregatedOverlays = newOverlays
        }

        // Remove old individual overlays (batch operation)
        if !individualToRemove.isEmpty {
            let overlaysToRemove = individualToRemove.compactMap { context.coordinator.individualOverlayMap[$0.segmentID] }
            if !overlaysToRemove.isEmpty {
                mapView.removeOverlays(overlaysToRemove)
            }
            individualToRemove.forEach { context.coordinator.individualOverlayMap.removeValue(forKey: $0.segmentID) }
        }

        // Add new individual overlays (batch operation)
        if !individualToAdd.isEmpty {
            let segmentsToAdd = individualSegments.filter { individualToAdd.contains(OverlayIdentity(segmentID: $0.id, congestionLevel: String($0.congestionFactor))) }
            let sortedSegments = segmentsToAdd.sorted { segment1, segment2 in
                if segment1.congestionFactor != segment2.congestionFactor {
                    return segment1.congestionFactor < segment2.congestionFactor
                }
                return segment1.actualDeparture < segment2.actualDeparture
            }

            var newOverlays: [IndividualJourneyPolyline] = []
            var segmentCounts: [String: Int] = [:]

            for individualSegment in sortedSegments {
                if let fromCoords = Stations.getCoordinates(for: individualSegment.fromStation),
                   let toCoords = Stations.getCoordinates(for: individualSegment.toStation) {
                    let segmentKey = "\(individualSegment.fromStation)-\(individualSegment.toStation)"
                    let offsetIndex = segmentCounts[segmentKey, default: 0]
                    segmentCounts[segmentKey] = offsetIndex + 1

                    var offsetCoords: [CLLocationCoordinate2D]
                    if let shapeCoords = RouteShapes.coordinates(from: individualSegment.fromStation, to: individualSegment.toStation) {
                        offsetCoords = offsetPolylineCoordinates(shapeCoords, offsetIndex: offsetIndex)
                    } else {
                        offsetCoords = createOffsetCoordinates(from: fromCoords, to: toCoords, offsetIndex: offsetIndex)
                    }
                    let polyline = IndividualJourneyPolyline(coordinates: offsetCoords, count: offsetCoords.count)
                    polyline.individualSegment = individualSegment
                    polyline.offsetIndex = offsetIndex
                    newOverlays.append(polyline)
                    context.coordinator.individualOverlayMap[individualSegment.id] = polyline
                }
            }
            if !newOverlays.isEmpty {
                mapView.addOverlays(newOverlays)
            }
        }

        // Update dimming on existing aggregated overlays if individual segments changed
        if desiredIndividualState != context.coordinator.currentIndividualOverlayState {
            let shouldDim = !individualSegments.isEmpty
            for overlay in context.coordinator.aggregatedOverlays {
                if overlay.isDimmed != shouldDim {
                    overlay.isDimmed = shouldDim
                    if let renderer = mapView.renderer(for: overlay) as? MKPolylineRenderer {
                        renderer.alpha = shouldDim ? 0.3 : 0.8
                    }
                }
            }
        }

        // Handle route topology overlays
        let routesVisibilityChanged = showRoutes != context.coordinator.routesVisible

        if routesVisibilityChanged || (showRoutes && systemsChanged) {
            // Remove existing overlays
            if !context.coordinator.routeTopologyOverlays.isEmpty {
                mapView.removeOverlays(context.coordinator.routeTopologyOverlays)
                context.coordinator.routeTopologyOverlays = []
            }

            if showRoutes {
                // Filter routes by selected systems and add overlays
                let selectedSystemStrings = selectedSystems.asRawStrings
                let filteredRoutes = RouteTopology.allRoutes.filter { selectedSystemStrings.contains($0.dataSource) }

                var newRouteOverlays: [RouteTopologyPolyline] = []
                var drawnSegments = Set<String>()
                for route in filteredRoutes {
                    for i in 0..<(route.stationCodes.count - 1) {
                        let fromCode = route.stationCodes[i]
                        let toCode = route.stationCodes[i + 1]

                        // Deduplicate shared track segments (e.g., NEC and NJCL share NY→RH)
                        // Use canonical ordering so A→B and B→A are the same segment
                        let segmentKey = fromCode < toCode ? "\(fromCode)-\(toCode)" : "\(toCode)-\(fromCode)"
                        guard drawnSegments.insert(segmentKey).inserted else { continue }

                        guard let fromCoord = Stations.getCoordinates(for: fromCode),
                              let toCoord = Stations.getCoordinates(for: toCode) else { continue }

                        // Use GTFS shape data for smooth curves, fall back to straight line
                        let coordinates = RouteShapes.coordinates(from: fromCode, to: toCode) ?? [fromCoord, toCoord]
                        let polyline = RouteTopologyPolyline(coordinates: coordinates, count: coordinates.count)
                        polyline.routeId = route.id
                        polyline.routeName = route.name
                        polyline.dataSource = route.dataSource
                        newRouteOverlays.append(polyline)
                    }
                }
                if !newRouteOverlays.isEmpty {
                    mapView.insertOverlay(newRouteOverlays.first!, at: 0)
                    for (index, overlay) in newRouteOverlays.dropFirst().enumerated() {
                        mapView.insertOverlay(overlay, at: index + 1)
                    }
                }
                context.coordinator.routeTopologyOverlays = newRouteOverlays
            }
            context.coordinator.routesVisible = showRoutes
        }

        // Handle station annotations (update if stations or systems changed)
        if stationsChanged || systemsChanged {
            mapView.removeAnnotations(mapView.annotations.filter { !($0 is MKUserLocation) })
            for station in stations {
                let annotation = SystemStationAnnotation()
                annotation.coordinate = station.coordinate
                annotation.title = station.name
                annotation.subtitle = station.code
                annotation.station = station
                mapView.addAnnotation(annotation)
            }
            context.coordinator.currentStationCodes = desiredStationCodes
            context.coordinator.currentSelectedSystems = selectedSystems
        }

        // Update state
        context.coordinator.currentAggregatedOverlayState = desiredAggregatedState
        context.coordinator.currentIndividualOverlayState = desiredIndividualState

        // Update coordinator with current segments and highlight mode for rendering
        context.coordinator.segments = segments
        context.coordinator.individualSegments = individualSegments
        context.coordinator.onSegmentTap = onSegmentTap
        context.coordinator.onIndividualSegmentTap = onIndividualSegmentTap ?? { _ in }
    }
    
    
    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    struct OverlayIdentity: Hashable {
        let segmentID: String
        let congestionLevel: String
    }

    class Coordinator: NSObject, MKMapViewDelegate {
        var segments: [CongestionSegment] = []
        var individualSegments: [IndividualJourneySegment] = []
        var onSegmentTap: (CongestionSegment) -> Void = { _ in }
        var onIndividualSegmentTap: (IndividualJourneySegment) -> Void = { _ in }
        var highlightMode: SegmentHighlightMode = .delays

        var currentAggregatedOverlayState: Set<OverlayIdentity> = []
        var aggregatedOverlays: [SystemCongestionPolyline] = []
        var currentIndividualOverlayState: Set<OverlayIdentity> = []
        var individualOverlayMap: [String: IndividualJourneyPolyline] = [:]

        // Route topology state
        var routeTopologyOverlays: [RouteTopologyPolyline] = []
        var routesVisible: Bool = false
        var currentSelectedSystems: Set<TrainSystem> = .all

        // Station annotation state
        var currentStationCodes: Set<String> = []

        // MARK: - Polyline Rendering
        func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
            // Handle individual journey polylines
            if let polyline = overlay as? IndividualJourneyPolyline {
                let renderer = MKPolylineRenderer(polyline: polyline)

                if let segment = polyline.individualSegment {
                    // Check if this individual train is cancelled
                    if segment.isCancelled {
                        renderer.strokeColor = UIColor.systemRed
                        renderer.lineWidth = 3.0
                        renderer.alpha = 0.9 // Keep cancelled trains highly visible
                    } else {
                        // Use highlight mode to determine color
                        renderer.strokeColor = getColorForIndividualSegment(segment)
                        renderer.lineWidth = 3.0 // Thinner for individual journeys

                        // Calculate opacity based on recency of departure
                        renderer.alpha = getRecencyBasedAlpha(for: segment.actualDeparture)

                        // Add slight variation based on offset index for visual distinction
                        let alphaMod = CGFloat(polyline.offsetIndex % 3) * 0.05 // Reduced from 0.1 to preserve recency effect
                        renderer.alpha = max(0.3, renderer.alpha - alphaMod)
                    }
                }

                return renderer
            }

            // Handle aggregated segment polylines
            if let polyline = overlay as? SystemCongestionPolyline {
                let renderer = OutlinedPolylineRenderer(polyline: polyline)

                if let segment = polyline.segment {
                    // Base color from delay/frequency metrics
                    var color = getColorForSegment(segment)

                    // Escalate color for significant cancellation rates
                    if segment.cancellationRate > 20 {
                        color = UIColor.systemRed
                    } else if segment.cancellationRate > 10 {
                        color = escalateColor(color)
                    }

                    renderer.strokeColor = color
                    renderer.lineWidth = 6.0

                    // Dash pattern indicates cancellation severity (>5%)
                    if let dashPattern = segment.dashPattern {
                        renderer.lineDashPattern = dashPattern
                    }
                    renderer.alpha = polyline.isDimmed ? 0.3 : 0.8 // Dim when showing individual segments
                } else {
                    renderer.strokeColor = UIColor.gray
                    renderer.lineWidth = 6.0
                    renderer.alpha = polyline.isDimmed ? 0.3 : 0.8
                }

                return renderer
            }

            // Handle route topology polylines
            if let polyline = overlay as? RouteTopologyPolyline {
                let renderer = MKPolylineRenderer(polyline: polyline)
                renderer.strokeColor = UIColor.white
                renderer.lineWidth = 4.0
                renderer.alpha = 0.6
                return renderer
            }

            return MKOverlayRenderer(overlay: overlay)
        }

        // MARK: - Annotation Rendering
        func mapView(_ mapView: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            // Handle user location
            if annotation is MKUserLocation {
                return nil // Use default user location view
            }

            // Handle station annotations with small markers
            if let stationAnnotation = annotation as? SystemStationAnnotation {
                let identifier = "StationMarker"
                var annotationView = mapView.dequeueReusableAnnotationView(withIdentifier: identifier)

                if annotationView == nil {
                    annotationView = MKAnnotationView(annotation: stationAnnotation, reuseIdentifier: identifier)
                    annotationView?.canShowCallout = true
                } else {
                    annotationView?.annotation = stationAnnotation
                }

                // Create small station marker (~30% of default pin size)
                let size: CGFloat = 12  // Small dot size
                let renderer = UIGraphicsImageRenderer(size: CGSize(width: size, height: size))
                let image = renderer.image { context in
                    // Draw orange circle
                    UIColor.systemOrange.setFill()
                    context.cgContext.fillEllipse(in: CGRect(x: 0, y: 0, width: size, height: size))
                    // Draw white border
                    UIColor.white.setStroke()
                    context.cgContext.setLineWidth(1.5)
                    context.cgContext.strokeEllipse(in: CGRect(x: 0.75, y: 0.75, width: size - 1.5, height: size - 1.5))
                }

                annotationView?.image = image
                annotationView?.centerOffset = CGPoint(x: 0, y: 0)

                return annotationView
            }

            return nil
        }
        
        // MARK: - Helper Methods
        private func getUIColor(for congestionFactor: Double) -> UIColor {
            CongestionColors.color(forCongestionFactor: congestionFactor)
        }

        private func getFrequencyUIColor(for frequencyFactor: Double?) -> UIColor {
            CongestionColors.color(forFrequencyFactor: frequencyFactor)
        }

        /// Get color for aggregated segment based on its data source's preferred mode
        private func getColorForSegment(_ segment: CongestionSegment) -> UIColor {
            guard highlightMode != .off else { return UIColor.clear }
            switch segment.preferredHighlightMode {
            case .health:
                // Fall back to delay coloring when no frequency baseline exists yet
                if let _ = segment.frequencyFactor {
                    return getFrequencyUIColor(for: segment.frequencyFactor)
                }
                return getUIColor(for: segment.congestionFactor)
            case .delays, .off:
                return getUIColor(for: segment.congestionFactor)
            }
        }

        /// Public accessor for getColorForSegment (used by updateUIView for mode changes)
        func getColorForSegmentPublic(_ segment: CongestionSegment) -> UIColor {
            getColorForSegment(segment)
        }

        /// Get color for individual segment based on highlight mode
        private func getColorForIndividualSegment(_ segment: IndividualJourneySegment) -> UIColor {
            // Individual segments don't have per-train frequency data, always use congestion coloring
            guard highlightMode != .off else { return UIColor.clear }
            return getUIColor(for: segment.congestionFactor)
        }

        /// Public accessor for getColorForIndividualSegment (used by updateUIView for mode changes)
        func getColorForIndividualSegmentPublic(_ segment: IndividualJourneySegment) -> UIColor {
            getColorForIndividualSegment(segment)
        }

        /// Escalate a health color by one level toward red for cancellation impact
        private func escalateColor(_ color: UIColor) -> UIColor {
            if color == UIColor.systemGreen { return UIColor.systemYellow }
            if color == UIColor.systemYellow { return UIColor.systemOrange }
            return UIColor.systemRed // orange/red stay red
        }

        /// Public accessor for escalateColor (used by updateUIView for mode changes)
        func escalateColorPublic(_ color: UIColor) -> UIColor {
            escalateColor(color)
        }

        private func getRecencyBasedAlpha(for departureTime: Date) -> CGFloat {
            let now = Date()
            let timeSinceDeparture = now.timeIntervalSince(departureTime)
            let hoursAgo = timeSinceDeparture / 3600.0

            // Scale opacity based on how long ago the train departed
            // Most recent (0-1 hours): 0.9 alpha (most opaque)
            // 1-2 hours ago: 0.8-0.6 alpha (linear fade)
            // 2-3 hours ago: 0.6-0.4 alpha (more fade)
            // 3+ hours ago: 0.3 alpha (most transparent)

            if hoursAgo < 0 {
                // Future departure or very recent - most opaque
                return 0.9
            } else if hoursAgo <= 1.0 {
                // 0-1 hours ago: 0.9 to 0.8
                return 0.9 - CGFloat(hoursAgo) * 0.1
            } else if hoursAgo <= 2.0 {
                // 1-2 hours ago: 0.8 to 0.6
                return 0.8 - CGFloat((hoursAgo - 1.0)) * 0.2
            } else if hoursAgo <= 3.0 {
                // 2-3 hours ago: 0.6 to 0.4
                return 0.6 - CGFloat((hoursAgo - 2.0)) * 0.2
            } else {
                // 3+ hours ago: minimum opacity
                return 0.3
            }
        }

        // MARK: - Tap Handling

        @objc func handleMapTap(_ gesture: UITapGestureRecognizer) {
            guard let mapView = gesture.view as? MKMapView else { return }

            let tapPoint = gesture.location(in: mapView)
            let tapCoordinate = mapView.convert(tapPoint, toCoordinateFrom: mapView)

            // Check individual journey polylines first (they're on top visually)
            for (_, polyline) in individualOverlayMap {
                if isCoordinate(tapCoordinate, nearPolyline: polyline, inMapView: mapView) {
                    if let segment = polyline.individualSegment {
                        onIndividualSegmentTap(segment)
                        return
                    }
                }
            }

            // Then check aggregated segment polylines (may be merged)
            for polyline in aggregatedOverlays {
                if isCoordinate(tapCoordinate, nearPolyline: polyline, inMapView: mapView) {
                    if let segment = closestSegment(at: tapCoordinate, in: polyline, mapView: mapView) {
                        onSegmentTap(segment)
                        return
                    }
                }
            }
        }

        private func isCoordinate(_ coordinate: CLLocationCoordinate2D, nearPolyline polyline: MKPolyline, inMapView mapView: MKMapView) -> Bool {
            guard polyline.pointCount >= 2 else { return false }

            let points = polyline.points()
            let tapPoint = mapView.convert(coordinate, toPointTo: mapView)

            // Check each line segment in the polyline
            for i in 0..<(polyline.pointCount - 1) {
                let screenPoint1 = mapView.convert(points[i].coordinate, toPointTo: mapView)
                let screenPoint2 = mapView.convert(points[i + 1].coordinate, toPointTo: mapView)

                let distance = distanceFromPoint(tapPoint, toLineSegmentBetween: screenPoint1, and: screenPoint2)
                if distance <= 30 {
                    return true
                }
            }
            return false
        }

        /// For merged polylines, find which constituent segment the tap is closest to.
        private func closestSegment(at coordinate: CLLocationCoordinate2D, in polyline: SystemCongestionPolyline, mapView: MKMapView) -> CongestionSegment? {
            guard polyline.segments.count > 1 else { return polyline.segment }

            let tapPoint = mapView.convert(coordinate, toPointTo: mapView)
            var bestSegment: CongestionSegment?
            var bestDistance = CGFloat.infinity

            for segment in polyline.segments {
                guard let fromCoord = Stations.getCoordinates(for: segment.fromStation),
                      let toCoord = Stations.getCoordinates(for: segment.toStation) else { continue }
                let midCoord = CLLocationCoordinate2D(
                    latitude: (fromCoord.latitude + toCoord.latitude) / 2,
                    longitude: (fromCoord.longitude + toCoord.longitude) / 2
                )
                let midPoint = mapView.convert(midCoord, toPointTo: mapView)
                let dist = hypot(tapPoint.x - midPoint.x, tapPoint.y - midPoint.y)
                if dist < bestDistance {
                    bestDistance = dist
                    bestSegment = segment
                }
            }
            return bestSegment
        }

        private func distanceFromPoint(_ point: CGPoint, toLineSegmentBetween p1: CGPoint, and p2: CGPoint) -> CGFloat {
            let dx = p2.x - p1.x
            let dy = p2.y - p1.y
            let lengthSquared = dx * dx + dy * dy

            if lengthSquared == 0 {
                return hypot(point.x - p1.x, point.y - p1.y)
            }

            let t = max(0, min(1, ((point.x - p1.x) * dx + (point.y - p1.y) * dy) / lengthSquared))
            let closestPoint = CGPoint(x: p1.x + t * dx, y: p1.y + t * dy)
            return hypot(point.x - closestPoint.x, point.y - closestPoint.y)
        }

    }
}

// MARK: - Helper Functions

func createOffsetCoordinates(from: CLLocationCoordinate2D, to: CLLocationCoordinate2D, offsetIndex: Int) -> [CLLocationCoordinate2D] {
    guard offsetIndex != 0 else { return [from, to] }

    // Calculate perpendicular offset to separate bidirectional segments
    let offsetDistance = Double(offsetIndex) * 0.00015 // About 15 meters per offset

    // Use CANONICAL direction (west-to-east) for perpendicular calculation
    // This ensures +1 always means north side, -1 always means south side,
    // regardless of which way the train is traveling
    let (refFrom, refTo) = from.longitude <= to.longitude ? (from, to) : (to, from)

    let dx = refTo.longitude - refFrom.longitude
    let dy = refTo.latitude - refFrom.latitude

    // Perpendicular vector (rotated 90 degrees counterclockwise)
    let perpDx = -dy
    let perpDy = dx

    // Normalize and apply offset
    let length = sqrt(perpDx * perpDx + perpDy * perpDy)
    guard length > 0 else { return [from, to] }

    let offsetLat = offsetDistance * (perpDy / length)
    let offsetLon = offsetDistance * (perpDx / length)

    // Apply offset to ORIGINAL from/to coordinates
    let offsetFrom = CLLocationCoordinate2D(
        latitude: from.latitude + offsetLat,
        longitude: from.longitude + offsetLon
    )
    let offsetTo = CLLocationCoordinate2D(
        latitude: to.latitude + offsetLat,
        longitude: to.longitude + offsetLon
    )

    return [offsetFrom, offsetTo]
}

/// Offset a multi-point polyline perpendicularly (for separating overlapping segments).
/// Uses the overall segment direction for a consistent offset across all points.
func offsetPolylineCoordinates(_ coordinates: [CLLocationCoordinate2D], offsetIndex: Int) -> [CLLocationCoordinate2D] {
    guard offsetIndex != 0, coordinates.count >= 2 else { return coordinates }

    let offsetDistance = Double(offsetIndex) * 0.00015

    // Use overall direction (first to last point) for consistent offset
    let first = coordinates.first!
    let last = coordinates.last!
    let (refFrom, refTo) = first.longitude <= last.longitude ? (first, last) : (last, first)

    let dx = refTo.longitude - refFrom.longitude
    let dy = refTo.latitude - refFrom.latitude
    let perpDx = -dy
    let perpDy = dx
    let length = sqrt(perpDx * perpDx + perpDy * perpDy)
    guard length > 0 else { return coordinates }

    let offsetLat = offsetDistance * (perpDy / length)
    let offsetLon = offsetDistance * (perpDx / length)

    return coordinates.map {
        CLLocationCoordinate2D(latitude: $0.latitude + offsetLat, longitude: $0.longitude + offsetLon)
    }
}

// MARK: - Segment Merging

/// Groups adjacent segments with the same visual properties into continuous polylines.
/// Walks each route line in RouteTopology, finds runs of consecutive segments that share
/// the same congestion level / cancellation bracket / dash style, and concatenates their
/// coordinates into a single MKPolyline. This dramatically reduces overlay count and
/// eliminates visual seams at station boundaries.
func buildMergedAggregatedOverlays(
    from segments: [CongestionSegment],
    isDimmed: Bool
) -> [SystemCongestionPolyline] {
    guard !segments.isEmpty else { return [] }

    // Index segments by canonical station-pair key for O(1) lookup
    var segmentIndex: [String: CongestionSegment] = [:]
    for segment in segments {
        let key = canonicalSegmentKey(segment.fromStation, segment.toStation, segment.dataSource)
        segmentIndex[key] = segment
    }

    var usedSegmentIDs = Set<String>()
    var result: [SystemCongestionPolyline] = []

    // Walk each route line and find runs of adjacent same-visual segments
    for route in RouteTopology.allRoutes {
        var currentRun: [(segment: CongestionSegment, fromCode: String, toCode: String)] = []
        var currentKey: String?

        for i in 0..<(route.stationCodes.count - 1) {
            let fromCode = route.stationCodes[i]
            let toCode = route.stationCodes[i + 1]
            let lookupKey = canonicalSegmentKey(fromCode, toCode, route.dataSource)

            if let segment = segmentIndex[lookupKey], !usedSegmentIDs.contains(segment.id) {
                let vizKey = visualMergeKey(for: segment)
                if vizKey == currentKey {
                    currentRun.append((segment, fromCode, toCode))
                } else {
                    flushRun(&currentRun, isDimmed: isDimmed, into: &result, used: &usedSegmentIDs)
                    currentRun = [(segment, fromCode, toCode)]
                    currentKey = vizKey
                }
            } else {
                flushRun(&currentRun, isDimmed: isDimmed, into: &result, used: &usedSegmentIDs)
                currentRun = []
                currentKey = nil
            }
        }
        flushRun(&currentRun, isDimmed: isDimmed, into: &result, used: &usedSegmentIDs)
    }

    // Handle segments not matched to any route line (rendered as individual overlays)
    for segment in segments where !usedSegmentIDs.contains(segment.id) {
        if let overlay = createSingleSegmentOverlay(segment, isDimmed: isDimmed) {
            result.append(overlay)
        }
    }

    // Sort by congestion factor so lower-congestion segments draw first (higher on top)
    result.sort { ($0.segment?.congestionFactor ?? 0) < ($1.segment?.congestionFactor ?? 0) }
    return result
}

/// Alphabetically-ordered canonical key for a station pair + data source.
private func canonicalSegmentKey(_ stationA: String, _ stationB: String, _ dataSource: String) -> String {
    let (a, b) = stationA < stationB ? (stationA, stationB) : (stationB, stationA)
    return "\(a)-\(b)-\(dataSource)"
}

/// Key that determines whether two segments can be visually merged (same color, dash, etc.).
private func visualMergeKey(for segment: CongestionSegment) -> String {
    let cancBracket = segment.cancellationRate > 20 ? 2 : segment.cancellationRate > 10 ? 1 : 0
    let dashed = segment.dashPattern != nil
    return "\(segment.congestionLevel)-\(cancBracket)-\(dashed)"
}

/// Flush a run of adjacent segments into a single merged overlay.
private func flushRun(
    _ run: inout [(segment: CongestionSegment, fromCode: String, toCode: String)],
    isDimmed: Bool,
    into result: inout [SystemCongestionPolyline],
    used: inout Set<String>
) {
    guard !run.isEmpty else { return }
    if let overlay = createMergedOverlay(from: run, isDimmed: isDimmed) {
        result.append(overlay)
        for item in run { used.insert(item.segment.id) }
    }
    run = []
}

/// Create a single polyline from a run of adjacent segments by concatenating their coordinates.
private func createMergedOverlay(
    from run: [(segment: CongestionSegment, fromCode: String, toCode: String)],
    isDimmed: Bool
) -> SystemCongestionPolyline? {
    guard !run.isEmpty else { return nil }

    var allCoordinates: [CLLocationCoordinate2D] = []

    for (i, item) in run.enumerated() {
        var segCoords: [CLLocationCoordinate2D]
        if let shapeCoords = RouteShapes.coordinates(from: item.fromCode, to: item.toCode) {
            segCoords = shapeCoords
        } else if let fromCoord = Stations.getCoordinates(for: item.fromCode),
                  let toCoord = Stations.getCoordinates(for: item.toCode) {
            segCoords = [fromCoord, toCoord]
        } else {
            continue
        }
        // Skip the shared station coordinate at the join point
        if i > 0 && !allCoordinates.isEmpty && !segCoords.isEmpty {
            segCoords = Array(segCoords.dropFirst())
        }
        allCoordinates.append(contentsOf: segCoords)
    }

    guard allCoordinates.count >= 2 else { return nil }

    // Apply consistent perpendicular offset across the entire merged polyline
    let directionOffset = run.first!.fromCode < run.last!.toCode ? 1 : -1
    let offsetCoords = offsetPolylineCoordinates(allCoordinates, offsetIndex: directionOffset)

    let polyline = SystemCongestionPolyline(coordinates: offsetCoords, count: offsetCoords.count)
    polyline.segments = run.map { $0.segment }
    polyline.isDimmed = isDimmed
    return polyline
}

/// Create a single-segment overlay (for segments not on any known route line).
private func createSingleSegmentOverlay(_ segment: CongestionSegment, isDimmed: Bool) -> SystemCongestionPolyline? {
    guard let fromCoord = Stations.getCoordinates(for: segment.fromStation),
          let toCoord = Stations.getCoordinates(for: segment.toStation) else { return nil }

    let directionOffset = segment.fromStation < segment.toStation ? 1 : -1
    let coordinates: [CLLocationCoordinate2D]
    if let shapeCoords = RouteShapes.coordinates(from: segment.fromStation, to: segment.toStation) {
        coordinates = offsetPolylineCoordinates(shapeCoords, offsetIndex: directionOffset)
    } else {
        coordinates = createOffsetCoordinates(from: fromCoord, to: toCoord, offsetIndex: directionOffset)
    }

    let polyline = SystemCongestionPolyline(coordinates: coordinates, count: coordinates.count)
    polyline.segments = [segment]
    polyline.isDimmed = isDimmed
    return polyline
}

// MARK: - Outlined Polyline Renderer

/// Draws a dark border stroke behind the colored fill stroke for better contrast on any map background.
/// The border uses a darkened version of the stroke color for a cohesive look.
class OutlinedPolylineRenderer: MKPolylineRenderer {
    /// Width of the border around each side of the stroke. Total rendered width = lineWidth + 2 * borderWidth.
    var borderWidth: CGFloat = 1.5

    override func draw(_ mapRect: MKMapRect, zoomScale: MKZoomScale, in context: CGContext) {
        // Round caps/joins for smooth endpoints and transitions
        lineCap = .round
        lineJoin = .round

        let originalColor = strokeColor
        let originalWidth = lineWidth
        let originalAlpha = alpha

        // Draw border: darkened version of the stroke color
        var hue: CGFloat = 0, sat: CGFloat = 0, bri: CGFloat = 0, a: CGFloat = 0
        if let color = originalColor, color.getHue(&hue, saturation: &sat, brightness: &bri, alpha: &a) {
            strokeColor = UIColor(hue: hue, saturation: sat, brightness: bri * 0.4, alpha: a)
        } else {
            strokeColor = UIColor.black.withAlphaComponent(0.5)
        }
        lineWidth = originalWidth + borderWidth * 2
        alpha = originalAlpha
        super.draw(mapRect, zoomScale: zoomScale, in: context)

        // Draw fill on top
        strokeColor = originalColor
        lineWidth = originalWidth
        alpha = originalAlpha
        super.draw(mapRect, zoomScale: zoomScale, in: context)
    }
}

// MARK: - Custom Polyline Classes

class SystemCongestionPolyline: MKPolyline {
    /// All segments represented by this polyline (merged adjacent same-visual segments).
    var segments: [CongestionSegment] = []
    var isDimmed: Bool = false

    /// First (or only) segment — used for color/dash lookups since all merged segments share the same visual properties.
    var segment: CongestionSegment? { segments.first }
}

class IndividualJourneyPolyline: MKPolyline {
    var individualSegment: IndividualJourneySegment?
    var offsetIndex: Int = 0
}

class RouteTopologyPolyline: MKPolyline {
    var routeId: String = ""
    var routeName: String = ""
    var dataSource: String = ""
}

// MARK: - Custom Annotation Class for System Map
class SystemStationAnnotation: NSObject, MKAnnotation {
    var coordinate: CLLocationCoordinate2D = CLLocationCoordinate2D()
    var title: String?
    var subtitle: String?
    var station: MapStation?
}

// MARK: - Supporting Models

struct MapStation: Identifiable {
    let id = UUID()
    let code: String
    let name: String
    let coordinate: CLLocationCoordinate2D
}

// MARK: - Preview

#Preview {
    CongestionMapView()
}


