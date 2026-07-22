import SwiftUI
import MapKit
import UIKit
import Combine
import ActivityKit

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
    @Published var showStations: Bool = false  // Default: Off

    // MARK: - Data
    @Published var segments: [CongestionSegment] = []
    @Published var individualSegments: [IndividualJourneySegment] = []
    @Published var routeStations: [MapStation] = []  // Stations from route topology
    @Published var isLoading = false
    @Published var error: String?
    @Published var lastTimeWindowHours: Int = 2  // Track effective time window for headway calc (backend min is 2)

    // MARK: - Internal State
    private var allAggregatedSegments: [CongestionSegment] = []
    private var allIndividualSegments: [IndividualJourneySegment] = []
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
    private var lastSystems: Set<TrainSystem>?

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
                    timeWindowHours: self?.lastTimeWindowHours ?? 2,
                    dataSource: self?.lastDataSource,
                    systems: self?.lastSystems
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
                    dataSource: lastDataSource,
                    systems: lastSystems
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

    /// Updates the selected systems filter, re-fetches from server, and reapplies filtering
    func setSelectedSystems(_ systems: Set<TrainSystem>, refetch: Bool = true) {
        let changed = systems != selectedSystems
        selectedSystems = systems
        guard changed else { return }
        print("🚦 Selected systems updated: \(systems.map(\.rawValue).sorted().joined(separator: ", "))")

        // Refilter route stations immediately (client-side, instant)
        routeStations = allRouteStations.filter { station in
            Stations.isStationVisible(station.code, withSystems: selectedSystems)
        }

        // Apply client-side filter immediately for fast visual update
        applyDisplayModeFilter()

        // Re-fetch from server with new system filter (skip during initial setup)
        if refetch {
            Task {
                await fetchCongestionData(
                    timeWindowHours: lastTimeWindowHours,
                    dataSource: lastDataSource,
                    systems: systems
                )
            }
        }
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
    
    func fetchCongestionDataIfNeeded(timeWindowHours: Int = 2, dataSource: String? = nil, systems: Set<TrainSystem>? = nil) async {
        // Only fetch if we don't already have data and we're not currently loading
        guard allAggregatedSegments.isEmpty && !isLoading else {
            print("🚦 Skipping congestion data fetch - already have data or loading")
            return
        }

        await fetchCongestionData(timeWindowHours: timeWindowHours, dataSource: dataSource, systems: systems)
    }
    
    func fetchCongestionData(timeWindowHours: Int = 2, dataSource: String? = nil, systems: Set<TrainSystem>? = nil) async {
        // Prevent duplicate fetches if already loading
        guard !isLoading else {
            print("🚦 Skipping duplicate fetch - already loading")
            return
        }

        print("🚦 Starting congestion data fetch (timeWindow: \(timeWindowHours), dataSource: \(dataSource ?? "All"), systems: \(systems?.map(\.rawValue).sorted().joined(separator: ",") ?? "nil"))")
        isLoading = true
        error = nil
        lastTimeWindowHours = timeWindowHours  // Will be updated from response below
        lastDataSource = dataSource
        lastSystems = systems

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
                dataSource: dataSource,
                systems: systems
            )
            
            // Use the effective time window from the backend (may differ from requested, e.g. min 2h)
            lastTimeWindowHours = response.timeWindowHours

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

            // Segments arrive ready to use; the map draws its base network from route
            // topology and station pins from `routeStations`, so no per-segment station
            // extraction is needed here.
            allAggregatedSegments = response.aggregatedSegments
            allIndividualSegments = response.individualSegments

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
            print("🚦 Segments hidden")
        } else {
            // Show segments based on detail mode
            switch detailMode {
            case .summary:
                // Show aggregated segments only
                segments = filteredAggregated
                individualSegments = []
                print("🚦 Applied summary filter: \(segments.count) aggregated segments, mode: \(highlightMode.displayName)")

            case .trains:
                // Show individual journey segments
                segments = filteredAggregated // Keep aggregated for reference (dimmed)
                individualSegments = filteredIndividual
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
                        Text("2 hours").tag(2)
                        Text("3 hours").tag(3)
                    }
                    .pickerStyle(.segmented)
                }

                Section("Data Source") {
                    Picker("Source", selection: $selectedDataSource) {
                        Text("All").tag("All")
                        ForEach(TrainSystem.availableCases) { system in
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
    let selectedSystems: Set<TrainSystem>
    let highlightMode: SegmentHighlightMode
    let onSegmentTap: (CongestionSegment) -> Void
    let onIndividualSegmentTap: ((IndividualJourneySegment) -> Void)?
    let onStationTap: ((String) -> Void)?

    init(
        region: Binding<MKCoordinateRegion>,
        segments: [CongestionSegment],
        individualSegments: [IndividualJourneySegment],
        stations: [MapStation],
        selectedSystems: Set<TrainSystem>,
        highlightMode: SegmentHighlightMode,
        onSegmentTap: @escaping (CongestionSegment) -> Void,
        onIndividualSegmentTap: ((IndividualJourneySegment) -> Void)? = nil,
        onStationTap: ((String) -> Void)? = nil
    ) {
        self._region = region
        self.segments = segments
        self.individualSegments = individualSegments
        self.stations = stations
        self.selectedSystems = selectedSystems
        self.highlightMode = highlightMode
        self.onSegmentTap = onSegmentTap
        self.onIndividualSegmentTap = onIndividualSegmentTap
        self.onStationTap = onStationTap
    }

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
        tapGesture.delegate = context.coordinator
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
        
        reconcileLiveOverlays(on: mapView, coordinator: context.coordinator)

        let desiredBaseRoutes = RouteTopology.congestionMapBaseRoutes(selectedDataSources: selectedSystems.asRawStrings)
        let desiredRouteIDs = Set(desiredBaseRoutes.map(\.id))
        let routeOverlaysChanged = desiredRouteIDs != context.coordinator.renderedRouteIDs
        let desiredStationCodes = Set(stations.map { $0.code })
        let stationsChanged = desiredStationCodes != context.coordinator.currentStationCodes
        let systemsChanged = selectedSystems != context.coordinator.currentSelectedSystems

        // Handle route topology overlays. The full base network for the selected systems is
        // always drawn (issue #1602) so low-frequency systems like Amtrak aren't reduced to
        // scattered congestion segments over empty map. See `RouteTopology.congestionMapBaseRoutes`.
        if routeOverlaysChanged {
            // Remove existing overlays
            if !context.coordinator.routeTopologyOverlays.isEmpty {
                mapView.removeOverlays(context.coordinator.routeTopologyOverlays)
                context.coordinator.routeTopologyOverlays = []
            }

            if !desiredBaseRoutes.isEmpty {
                var newRouteOverlays: [RouteTopologyPolyline] = []
                var drawnSegments = Set<String>()
                for route in desiredBaseRoutes {
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
            context.coordinator.renderedRouteIDs = desiredRouteIDs
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

    }

    /// Reconciles only live aggregate/individual overlays. Kept callable so regression tests
    /// exercise the same retained-object and rebuild behavior used by `updateUIView`.
    func reconcileLiveOverlays(on mapView: MKMapView, coordinator: Coordinator) {
        coordinator.segments = segments
        coordinator.individualSegments = individualSegments
        coordinator.onSegmentTap = onSegmentTap
        coordinator.onIndividualSegmentTap = onIndividualSegmentTap ?? { _ in }
        coordinator.onStationTap = onStationTap

        let latestSegmentsByID = congestionSegmentsByID(segments)
        for overlay in coordinator.aggregatedOverlays {
            overlay.segments = overlay.segments.compactMap { latestSegmentsByID[$0.id] }
        }
        let latestIndividualSegments = individualSegments.reduce(into: [String: IndividualJourneySegment]()) {
            $0[$1.id] = $1
        }
        for (segmentID, overlay) in coordinator.individualOverlayMap {
            overlay.individualSegment = latestIndividualSegments[segmentID]
        }

        let desiredAggregatedState = systemCongestionOverlayState(for: segments)
        let desiredIndividualState = individualJourneyOverlayState(for: individualSegments)
        let highlightModeChanged = highlightMode != coordinator.highlightMode
        if highlightModeChanged {
            coordinator.highlightMode = highlightMode
            for overlay in coordinator.aggregatedOverlays {
                if let renderer = mapView.renderer(for: overlay) as? MKPolylineRenderer,
                   let segment = overlay.segment {
                    renderer.strokeColor = coordinator.getColorForSegmentPublic(segment)
                    renderer.setNeedsDisplay()
                }
            }
        }

        let aggregatedChanged = desiredAggregatedState != coordinator.currentAggregatedOverlayState
        if aggregatedChanged {
            if !coordinator.aggregatedOverlays.isEmpty {
                mapView.removeOverlays(coordinator.aggregatedOverlays)
            }
            let newOverlays = buildMergedAggregatedOverlays(
                from: segments,
                isDimmed: !individualSegments.isEmpty
            )
            let aggregateStartIndex = coordinator.routeTopologyOverlays.count
            for (index, overlay) in newOverlays.enumerated() {
                mapView.insertOverlay(overlay, at: aggregateStartIndex + index)
            }
            coordinator.aggregatedOverlays = newOverlays
        }

        let individualChanged = desiredIndividualState != coordinator.currentIndividualOverlayState
        if individualChanged {
            let oldOverlays = Array(coordinator.individualOverlayMap.values)
            if !oldOverlays.isEmpty {
                mapView.removeOverlays(oldOverlays)
            }
            coordinator.individualOverlayMap = [:]

            var newOverlays: [IndividualJourneyPolyline] = []
            var segmentCounts: [String: Int] = [:]
            for individualSegment in sortedIndividualJourneySegments(individualSegments) {
                guard let fromCoords = Stations.getCoordinates(for: individualSegment.fromStation),
                      let toCoords = Stations.getCoordinates(for: individualSegment.toStation) else {
                    continue
                }
                let segmentKey = "\(individualSegment.fromStation)-\(individualSegment.toStation)"
                let offsetIndex = segmentCounts[segmentKey, default: 0]
                segmentCounts[segmentKey] = offsetIndex + 1

                let offsetCoords: [CLLocationCoordinate2D]
                if let shapeCoords = RouteShapes.coordinates(
                    from: individualSegment.fromStation,
                    to: individualSegment.toStation
                ) {
                    offsetCoords = offsetPolylineCoordinates(shapeCoords, offsetIndex: offsetIndex)
                } else {
                    offsetCoords = createOffsetCoordinates(
                        from: fromCoords,
                        to: toCoords,
                        offsetIndex: offsetIndex
                    )
                }
                let polyline = IndividualJourneyPolyline(
                    coordinates: offsetCoords,
                    count: offsetCoords.count
                )
                polyline.individualSegment = individualSegment
                polyline.offsetIndex = offsetIndex
                newOverlays.append(polyline)
                coordinator.individualOverlayMap[individualSegment.id] = polyline
            }
            if !newOverlays.isEmpty {
                mapView.addOverlays(newOverlays)
            }
        }

        if individualChanged {
            let shouldDim = !individualSegments.isEmpty
            for overlay in coordinator.aggregatedOverlays where overlay.isDimmed != shouldDim {
                overlay.isDimmed = shouldDim
                if let renderer = mapView.renderer(for: overlay) as? MKPolylineRenderer {
                    renderer.alpha = shouldDim ? 0.3 : 0.8
                }
            }
        }

        // Recency alpha changes with wall-clock time, so repaint retained individual overlays
        // on every representable update even when their semantic state is unchanged.
        for overlay in coordinator.individualOverlayMap.values {
            if let renderer = mapView.renderer(for: overlay) as? MKPolylineRenderer {
                coordinator.configureIndividualRenderer(renderer, for: overlay)
                renderer.setNeedsDisplay()
            }
        }

        coordinator.currentAggregatedOverlayState = desiredAggregatedState
        coordinator.currentIndividualOverlayState = desiredIndividualState
    }
    
    
    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    class Coordinator: NSObject, MKMapViewDelegate, UIGestureRecognizerDelegate {
        var segments: [CongestionSegment] = []
        var individualSegments: [IndividualJourneySegment] = []
        var onSegmentTap: (CongestionSegment) -> Void = { _ in }
        var onIndividualSegmentTap: (IndividualJourneySegment) -> Void = { _ in }
        var onStationTap: ((String) -> Void)?
        var highlightMode: SegmentHighlightMode = .delays

        var currentAggregatedOverlayState: [SystemCongestionOverlayIdentity] = []
        var aggregatedOverlays: [SystemCongestionPolyline] = []
        var currentIndividualOverlayState: [IndividualJourneyOverlayIdentity] = []
        var individualOverlayMap: [String: IndividualJourneyPolyline] = [:]

        // Route topology state
        var routeTopologyOverlays: [RouteTopologyPolyline] = []
        var renderedRouteIDs: Set<String> = []
        var currentSelectedSystems: Set<TrainSystem> = .all

        // Station annotation state
        var currentStationCodes: Set<String> = []

        // MARK: - Polyline Rendering
        func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
            // Handle individual journey polylines
            if let polyline = overlay as? IndividualJourneyPolyline {
                let renderer = MKPolylineRenderer(polyline: polyline)
                configureIndividualRenderer(renderer, for: polyline)
                return renderer
            }

            // Handle aggregated segment polylines
            if let polyline = overlay as? SystemCongestionPolyline {
                let renderer = MKPolylineRenderer(polyline: polyline)

                if let segment = polyline.segment {
                    // Base color from delay/frequency metrics
                    renderer.strokeColor = getColorForSegment(segment)
                    renderer.lineWidth = 4.0
                    renderer.alpha = polyline.isDimmed ? 0.3 : 0.8 // Dim when showing individual segments
                } else {
                    renderer.strokeColor = UIColor.gray
                    renderer.lineWidth = 4.0
                    renderer.alpha = polyline.isDimmed ? 0.3 : 0.8
                }

                return renderer
            }

            // Handle route topology polylines
            if let polyline = overlay as? RouteTopologyPolyline {
                return polyline.makeRenderer()
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

        /// Get color for aggregated segment based on its data source's preferred mode.
        /// Cancellation rate is folded into the color so a single hue communicates both
        /// delay severity and cancellation severity.
        private func getColorForSegment(_ segment: CongestionSegment) -> UIColor {
            guard highlightMode != .off else { return UIColor.clear }
            switch segment.preferredHighlightMode {
            case .health:
                // Fall back to delay coloring when no frequency baseline exists yet
                if segment.frequencyFactor != nil {
                    return CongestionColors.color(forFrequencyFactor: segment.frequencyFactor, cancellationRate: segment.cancellationRate)
                }
                return CongestionColors.color(forCongestionFactor: segment.congestionFactor, cancellationRate: segment.cancellationRate)
            case .delays, .off:
                return CongestionColors.color(forCongestionFactor: segment.congestionFactor, cancellationRate: segment.cancellationRate)
            }
        }

        /// Public accessor for getColorForSegment (used by updateUIView for mode changes)
        func getColorForSegmentPublic(_ segment: CongestionSegment) -> UIColor {
            getColorForSegment(segment)
        }

        /// Get color for individual segment based on highlight mode.
        /// Individual segments don't carry cancellation rates (per-train, not aggregated).
        private func getColorForIndividualSegment(_ segment: IndividualJourneySegment) -> UIColor {
            guard highlightMode != .off else { return UIColor.clear }
            return CongestionColors.color(forCongestionFactor: segment.congestionFactor)
        }

        func configureIndividualRenderer(
            _ renderer: MKPolylineRenderer,
            for polyline: IndividualJourneyPolyline
        ) {
            guard let segment = polyline.individualSegment else { return }
            renderer.lineWidth = 4.0
            if segment.isCancelled {
                renderer.strokeColor = UIColor.systemRed
                renderer.alpha = 0.9
                return
            }

            renderer.strokeColor = getColorForIndividualSegment(segment)
            renderer.alpha = getRecencyBasedAlpha(for: segment.actualDeparture)
            let alphaMod = CGFloat(polyline.offsetIndex % 3) * 0.05
            renderer.alpha = max(0.3, renderer.alpha - alphaMod)
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

        /// Tapping a station pin pushes that station's details. We deselect immediately so
        /// the same pin can be tapped again after returning, and avoid the default callout.
        func mapView(_ mapView: MKMapView, didSelect view: MKAnnotationView) {
            guard let stationAnnotation = view.annotation as? SystemStationAnnotation,
                  let code = stationAnnotation.station?.code,
                  let onStationTap else { return }
            mapView.deselectAnnotation(view.annotation, animated: false)
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
            onStationTap(code)
        }

        /// Annotation taps are routed through `mapView(_:didSelect:)`. Without
        /// this filter, a tap on a pin sitting over a route polyline also fires
        /// the polyline-tap recognizer below, so a single tap triggers both
        /// station-detail navigation and a segment popup.
        func gestureRecognizer(
            _ gestureRecognizer: UIGestureRecognizer,
            shouldReceive touch: UITouch
        ) -> Bool {
            var view: UIView? = touch.view
            while let candidate = view {
                if candidate is MKAnnotationView { return false }
                view = candidate.superview
            }
            return true
        }

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

// MARK: - Overlay Reconciliation

/// Semantic identity of one aggregate segment overlay.
struct CongestionOverlayIdentity: Hashable {
    let segmentID: String
    let visualKey: String

    init(_ segment: CongestionSegment) {
        segmentID = segment.id
        visualKey = visualMergeKey(for: segment)
    }
}

typealias AggregatedCongestionRunItem = (
    segment: CongestionSegment,
    fromCode: String,
    toCode: String
)

struct AggregatedCongestionRun {
    let items: [AggregatedCongestionRunItem]
    let representative: CongestionSegment

    init?(_ items: [AggregatedCongestionRunItem]) {
        guard let representative = items.first?.segment else { return nil }
        self.items = items
        self.representative = representative
    }
}

struct SystemCongestionOverlayIdentity: Hashable {
    let segmentIDs: [String]
    let visualKey: String

    init(_ run: AggregatedCongestionRun) {
        segmentIDs = run.items.map { $0.segment.id }
        visualKey = visualMergeKey(for: run.representative)
    }
}

/// Semantic style identity; array order separately captures offset/draw-order changes.
struct IndividualJourneyOverlayIdentity: Hashable {
    let id: String
    let visualKey: String

    init(_ segment: IndividualJourneySegment) {
        id = segment.id
        visualKey = segment.isCancelled
            ? "cancelled"
            : "delay:" + CongestionColors.congestionTierKey(
                forFactor: segment.congestionFactor,
                cancellationRate: 0
            )
    }
}

func congestionSegmentsByID(
    _ segments: [CongestionSegment]
) -> [String: CongestionSegment] {
    segments.reduce(into: [String: CongestionSegment]()) {
        $0[$1.id] = $1
    }
}

/// Selects one stable winner for each bidirectional station pair.
/// More samples win; equal samples use segment id so response ordering is irrelevant.
func selectedBidirectionalCongestionSegments(
    from segments: [CongestionSegment]
) -> [CongestionSegment] {
    let selectedByCanonicalKey = segments.reduce(into: [String: CongestionSegment]()) {
        selected, candidate in
        let key = canonicalSegmentKey(
            candidate.fromStation,
            candidate.toStation,
            candidate.dataSource
        )
        guard let existing = selected[key] else {
            selected[key] = candidate
            return
        }
        if candidate.sampleCount > existing.sampleCount ||
            (candidate.sampleCount == existing.sampleCount && candidate.id < existing.id) {
            selected[key] = candidate
        }
    }
    return selectedByCanonicalKey.values.sorted(by: congestionDrawsBefore)
}

func congestionDrawsBefore(_ lhs: CongestionSegment, _ rhs: CongestionSegment) -> Bool {
    if lhs.congestionFactor != rhs.congestionFactor {
        return lhs.congestionFactor < rhs.congestionFactor
    }
    return lhs.id < rhs.id
}

func systemCongestionOverlayState(
    for segments: [CongestionSegment]
) -> [SystemCongestionOverlayIdentity] {
    aggregatedCongestionRuns(from: segments).map(SystemCongestionOverlayIdentity.init)
}

func sortedJourneyCongestionSegments(
    _ segments: [CongestionSegment]
) -> [CongestionSegment] {
    segments.sorted(by: congestionDrawsBefore)
}

func journeyCongestionOverlayState(
    for segments: [CongestionSegment]
) -> [CongestionOverlayIdentity] {
    sortedJourneyCongestionSegments(segments).map(CongestionOverlayIdentity.init)
}

func sortedIndividualJourneySegments(
    _ segments: [IndividualJourneySegment]
) -> [IndividualJourneySegment] {
    segments.sorted { lhs, rhs in
        if lhs.congestionFactor != rhs.congestionFactor {
            return lhs.congestionFactor < rhs.congestionFactor
        }
        if lhs.actualDeparture != rhs.actualDeparture {
            return lhs.actualDeparture < rhs.actualDeparture
        }
        return lhs.id < rhs.id
    }
}

func individualJourneyOverlayState(
    for segments: [IndividualJourneySegment]
) -> [IndividualJourneyOverlayIdentity] {
    sortedIndividualJourneySegments(segments).map(IndividualJourneyOverlayIdentity.init)
}

// MARK: - Segment Merging

func aggregatedCongestionRuns(
    from segments: [CongestionSegment]
) -> [AggregatedCongestionRun] {
    var segmentIndex: [String: CongestionSegment] = [:]
    for segment in selectedBidirectionalCongestionSegments(from: segments) {
        segmentIndex[canonicalSegmentKey(
            segment.fromStation,
            segment.toStation,
            segment.dataSource
        )] = segment
    }

    var usedCanonicalKeys = Set<String>()
    var runs: [AggregatedCongestionRun] = []

    func appendRun(_ items: inout [AggregatedCongestionRunItem]) {
        guard let run = AggregatedCongestionRun(items) else { return }
        runs.append(run)
        for item in items {
            usedCanonicalKeys.insert(canonicalSegmentKey(
                item.fromCode,
                item.toCode,
                item.segment.dataSource
            ))
        }
        items = []
    }

    // Walk each route line and find runs of adjacent same-visual segments
    for route in RouteTopology.allRoutes {
        var currentRun: [AggregatedCongestionRunItem] = []
        var currentKey: String?

        for i in 0..<(route.stationCodes.count - 1) {
            let fromCode = route.stationCodes[i]
            let toCode = route.stationCodes[i + 1]
            let lookupKey = canonicalSegmentKey(fromCode, toCode, route.dataSource)

            if let segment = segmentIndex[lookupKey], !usedCanonicalKeys.contains(lookupKey) {
                let vizKey = visualMergeKey(for: segment)
                if vizKey == currentKey {
                    currentRun.append((segment, fromCode, toCode))
                } else {
                    appendRun(&currentRun)
                    currentRun = [(segment, fromCode, toCode)]
                    currentKey = vizKey
                }
            } else {
                appendRun(&currentRun)
                currentKey = nil
            }
        }
        appendRun(&currentRun)
    }

    // Handle segments not matched to any route line (rendered as individual overlays)
    for (canonicalKey, segment) in segmentIndex where !usedCanonicalKeys.contains(canonicalKey) {
        if let run = AggregatedCongestionRun([(
            segment: segment,
            fromCode: segment.fromStation,
            toCode: segment.toStation
        )]) {
            runs.append(run)
        }
    }

    // Sort by congestion factor so lower-congestion segments draw first (higher on top)
    return runs.sorted {
        congestionDrawsBefore($0.representative, $1.representative)
    }
}

/// Groups adjacent segments with the same visual properties into continuous polylines.
func buildMergedAggregatedOverlays(
    from segments: [CongestionSegment],
    isDimmed: Bool
) -> [SystemCongestionPolyline] {
    aggregatedCongestionRuns(from: segments).compactMap {
        createMergedOverlay(from: $0.items, isDimmed: isDimmed)
    }
}

/// Alphabetically-ordered canonical key for a station pair + data source.
private func canonicalSegmentKey(_ stationA: String, _ stationB: String, _ dataSource: String) -> String {
    let (a, b) = stationA < stationB ? (stationA, stationB) : (stationB, stationA)
    return "\(a)-\(b)-\(dataSource)"
}

/// Key that determines whether two segments can be visually merged (same effective color).
/// Must mirror `getColorForSegment` exactly: in health mode a segment is colored by its
/// frequency tier when a frequency factor exists, otherwise by the delay-fallback tier.
/// Keying on the delay tier alone (the old behavior) left same-color frequency segments
/// unmerged and merged different-color ones into a single wrongly-colored run — most
/// visible on frequency-first systems with many short segments (SEPTA Metro).
func visualMergeKey(for segment: CongestionSegment) -> String {
    switch segment.preferredHighlightMode {
    case .health:
        if segment.frequencyFactor != nil {
            return "freq:" + CongestionColors.frequencyTierKey(
                forFactor: segment.frequencyFactor, cancellationRate: segment.cancellationRate)
        }
        return "delay:" + CongestionColors.congestionTierKey(
            forFactor: segment.congestionFactor, cancellationRate: segment.cancellationRate)
    case .delays, .off:
        return "delay:" + CongestionColors.congestionTierKey(
            forFactor: segment.congestionFactor, cancellationRate: segment.cancellationRate)
    }
}

/// Create a single polyline from a run of adjacent segments by concatenating their coordinates.
private func createMergedOverlay(
    from run: [AggregatedCongestionRunItem],
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

    /// Shared styling so route-topology lines look identical on every map
    /// (full congestion map and the route-status base layer).
    func makeRenderer() -> MKPolylineRenderer {
        let renderer = MKPolylineRenderer(polyline: self)
        renderer.strokeColor = UIColor.white
        renderer.lineWidth = 4.0
        renderer.alpha = 0.6
        return renderer
    }
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
