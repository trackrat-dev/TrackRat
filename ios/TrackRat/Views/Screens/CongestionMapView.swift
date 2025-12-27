import SwiftUI
import MapKit
import UIKit
import Combine
import ActivityKit

struct CongestionMapView: View {
    @StateObject private var viewModel = CongestionMapViewModel()
    @State private var region = MKCoordinateRegion.newarkPennDefault
    @State private var selectedSegment: CongestionSegment?
    @State private var showingFilters = false
    @State private var timeWindow = 1
    @State private var selectedDataSource: String = "All"
    
    var body: some View {
        ZStack {
            // Map
            SystemCongestionMapView(
                region: $region,
                segments: viewModel.segments,
                individualSegments: viewModel.individualSegments,
                stations: viewModel.stations,
                onSegmentTap: { segment in
                    selectedSegment = segment
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                },
                onIndividualSegmentTap: { individualSegment in
                    // For now, we'll just show regular segment details
                    // TODO: Create specific individual segment details view
                    print("Tapped individual segment: \(individualSegment.trainDisplayName) \(individualSegment.fromStation) → \(individualSegment.toStation)")
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
                            Text("\(viewModel.segments.count) segments")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    
                    Spacer()
                    
                    HStack(spacing: 12) {
                        // Display mode toggle
                        Button {
                            Task {
                                switch viewModel.displayMode {
                                case .aggregated:
                                    await viewModel.updateDisplayMode(.individual)
                                case .individual, .individualLimited:
                                    await viewModel.updateDisplayMode(.aggregated)
                                }
                            }
                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        } label: {
                            Image(systemName: viewModel.displayMode == .aggregated ? "line.horizontal.3" : "dot.square")
                                .font(.title2)
                                .foregroundColor(.orange)
                                .padding(10)
                                .background(
                                    Circle()
                                        .fill(.ultraThinMaterial)
                                )
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
                
                // Legend
                VStack(alignment: .leading, spacing: 8) {
                    Text("Congestion Levels")
                        .trackRatSectionHeader()

                    HStack(spacing: 16) {
                        LegendItem(color: .green, label: "Normal")
                        LegendItem(color: .yellow, label: "Moderate")
                        LegendItem(color: .orange, label: "Heavy")
                        LegendItem(color: .red, label: "Severe")
                    }
                    
                    // Cancellation legend
                    HStack(spacing: 8) {
                        HStack(spacing: 4) {
                            Rectangle()
                                .fill(.red)
                                .frame(width: 20, height: 2)
                                .overlay(
                                    Rectangle()
                                        .fill(.clear)
                                        .frame(width: 20, height: 2)
                                        .overlay(
                                            HStack(spacing: 1) {
                                                ForEach(0..<4, id: \.self) { _ in
                                                    Rectangle()
                                                        .fill(.red)
                                                        .frame(width: 2, height: 2)
                                                }
                                            }
                                        )
                                )
                            Text("High Cancellations")
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                .padding()
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(.ultraThinMaterial)
                )
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
        .sheet(item: $selectedSegment) { segment in
            SegmentTrainDetailsView(segment: segment)
                .presentationDetents([.height(600), .large])
                .presentationDragIndicator(.visible)
        }
        .task {
            await viewModel.fetchCongestionData()
        }
    }
    
}

// MARK: - View Model

enum CongestionDisplayMode: Equatable {
    case aggregated
    case individual
    case individualLimited(maxPerSegment: Int)
}

@MainActor
class CongestionMapViewModel: ObservableObject {
    @Published var segments: [CongestionSegment] = []
    @Published var individualSegments: [IndividualJourneySegment] = []
    @Published var stations: [MapStation] = []
    @Published var isLoading = false
    @Published var error: String?
    @Published var displayMode: CongestionDisplayMode = .individual
    
    // Store all segments and filter based on display mode
    private var allAggregatedSegments: [CongestionSegment] = []
    private var allIndividualSegments: [IndividualJourneySegment] = []
    private var allStations: [MapStation] = []
    private var currentDisplayMode: MapDisplayMode = .overallCongestion
    
    // Current journey filter
    private var selectedRoute: TripPair?
    private var journeyStations: [String] = []

    // Live Activity observation
    private var liveActivityCancellables = Set<AnyCancellable>()

    init() {
        // Don't start loading data immediately - wait for explicit trigger
        // This prevents blocking the UI during app startup and navigation
        print("🚦 CongestionMapViewModel init - data loading deferred")

        // Observe Live Activity state changes
        if #available(iOS 16.1, *) {
            observeLiveActivityState()
        }
    }

    @available(iOS 16.1, *)
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
            // Live Activity is active - apply route filter
            if #available(iOS 16.1, *),
               let activity = LiveActivityService.shared.currentActivity {
                let attributes = activity.attributes
                let route = TripPair(
                    departureCode: attributes.originStationCode,
                    departureName: attributes.origin,
                    destinationCode: attributes.destinationStationCode,
                    destinationName: attributes.destination
                )
                setRouteFilter(route, journeyStations: stationCodes)
                print("🗺️ Applied route filter for Live Activity: \(attributes.originStationCode) → \(attributes.destinationStationCode)")
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
        
        do {
            let maxPerSegment = switch displayMode {
            case .aggregated: 0
            case .individual: 100
            case .individualLimited(let max): max
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
            
        } catch {
            self.error = error.localizedDescription
            print("🚦 Failed to fetch congestion data: \(error)")
        }
        
        isLoading = false
        print("🚦 Congestion data fetch completed. Final segments: \(segments.count)")
    }
    
    func updateDisplayMode(_ mode: CongestionDisplayMode) async {
        print("🚦 Updating display mode to: \(mode)")
        displayMode = mode

        // OPTIMIZATION: Only re-filter cached data instead of re-fetching from API
        // This is instant and doesn't require a network call
        applyDisplayModeFilter()
    }
    
    private func applyDisplayModeFilter() {
        // First apply route filter if we have one
        let filteredAggregated = selectedRoute != nil ? filterSegmentsForRoute(allAggregatedSegments) : allAggregatedSegments
        let filteredIndividual = selectedRoute != nil ? filterIndividualSegmentsForRoute(allIndividualSegments) : allIndividualSegments
        
        switch displayMode {
        case .aggregated:
            // Show aggregated segments only
            segments = filteredAggregated
            individualSegments = []
            stations = allStations
            print("🚦 Applied aggregated filter: \(segments.count) aggregated segments")
            
        case .individual, .individualLimited:
            // Show individual journey segments
            segments = filteredAggregated // Keep aggregated for reference
            individualSegments = filteredIndividual
            stations = allStations
            print("🚦 Applied individual filter: \(individualSegments.count) individual segments")
        }
    }
    
    func setRouteFilter(_ route: TripPair?, journeyStations: [String] = []) {
        print("🚦 Setting route filter: \(route?.departureCode ?? "none") → \(route?.destinationCode ?? "none")")
        print("🚦 Journey stations: \(journeyStations)")

        self.selectedRoute = route
        self.journeyStations = journeyStations

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
            
            // Include segments where 'to' station comes after 'from' station in the journey
            return toIndex > fromIndex
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
            
            // Include segments where 'to' station comes after 'from' station in the journey
            return toIndex > fromIndex
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
                        Text("NJ Transit").tag("NJT")
                        Text("Amtrak").tag("AMTRAK")
                    }
                    .pickerStyle(.segmented)
                }
            }
            .scrollContentBackground(.hidden)
            .background(Color.black)
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

        // Early exit if nothing changed
        guard desiredAggregatedState != context.coordinator.currentAggregatedOverlayState ||
              desiredIndividualState != context.coordinator.currentIndividualOverlayState else {
            return
        }

        // Diff aggregated overlays
        let aggregatedToRemove = context.coordinator.currentAggregatedOverlayState.subtracting(desiredAggregatedState)
        let aggregatedToAdd = desiredAggregatedState.subtracting(context.coordinator.currentAggregatedOverlayState)

        // Diff individual overlays
        let individualToRemove = context.coordinator.currentIndividualOverlayState.subtracting(desiredIndividualState)
        let individualToAdd = desiredIndividualState.subtracting(context.coordinator.currentIndividualOverlayState)

        // Remove old aggregated overlays (batch operation)
        if !aggregatedToRemove.isEmpty {
            let overlaysToRemove = aggregatedToRemove.compactMap { context.coordinator.aggregatedOverlayMap[$0.segmentID] }
            if !overlaysToRemove.isEmpty {
                mapView.removeOverlays(overlaysToRemove)
            }
            aggregatedToRemove.forEach { context.coordinator.aggregatedOverlayMap.removeValue(forKey: $0.segmentID) }
        }

        // Remove old individual overlays (batch operation)
        if !individualToRemove.isEmpty {
            let overlaysToRemove = individualToRemove.compactMap { context.coordinator.individualOverlayMap[$0.segmentID] }
            if !overlaysToRemove.isEmpty {
                mapView.removeOverlays(overlaysToRemove)
            }
            individualToRemove.forEach { context.coordinator.individualOverlayMap.removeValue(forKey: $0.segmentID) }
        }

        // Add new aggregated overlays (batch operation)
        if !aggregatedToAdd.isEmpty {
            let segmentsToAdd = segments.filter { aggregatedToAdd.contains(OverlayIdentity(segmentID: $0.id, congestionLevel: $0.congestionLevel)) }
            let sortedSegments = segmentsToAdd.sorted { $0.congestionFactor < $1.congestionFactor }

            var newOverlays: [SystemCongestionPolyline] = []
            for segment in sortedSegments {
                if let fromCoords = Stations.getCoordinates(for: segment.fromStation),
                   let toCoords = Stations.getCoordinates(for: segment.toStation) {
                    let coordinates = [fromCoords, toCoords]
                    let polyline = SystemCongestionPolyline(coordinates: coordinates, count: coordinates.count)
                    polyline.segment = segment
                    polyline.isDimmed = !individualSegments.isEmpty
                    newOverlays.append(polyline)
                    context.coordinator.aggregatedOverlayMap[segment.id] = polyline
                }
            }
            if !newOverlays.isEmpty {
                mapView.addOverlays(newOverlays)
            }
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

                    let offsetCoords = createOffsetCoordinates(from: fromCoords, to: toCoords, offsetIndex: offsetIndex)
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
            for overlay in context.coordinator.aggregatedOverlayMap.values {
                if overlay.isDimmed != shouldDim {
                    overlay.isDimmed = shouldDim
                    if let renderer = mapView.renderer(for: overlay) as? MKPolylineRenderer {
                        renderer.alpha = shouldDim ? 0.3 : 0.8
                    }
                }
            }
        }

        // Always clear and re-add annotations (they're lightweight)
        mapView.removeAnnotations(mapView.annotations.filter { !($0 is MKUserLocation) })

        // Update state
        context.coordinator.currentAggregatedOverlayState = desiredAggregatedState
        context.coordinator.currentIndividualOverlayState = desiredIndividualState
        
        // Update coordinator with current segments for tap handling
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

        var currentAggregatedOverlayState: Set<OverlayIdentity> = []
        var aggregatedOverlayMap: [String: SystemCongestionPolyline] = [:]
        var currentIndividualOverlayState: Set<OverlayIdentity> = []
        var individualOverlayMap: [String: IndividualJourneyPolyline] = [:]

        // MARK: - Polyline Rendering
        func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
            // Handle individual journey polylines
            if let polyline = overlay as? IndividualJourneyPolyline {
                let renderer = MKPolylineRenderer(polyline: polyline)
                
                if let segment = polyline.individualSegment {
                    // Check if this individual train is cancelled - make it stand out
                    if segment.isCancelled {
                        renderer.strokeColor = UIColor.systemRed
                        renderer.lineWidth = 5.0 // Wider than normal individual lines
                        renderer.lineDashPattern = [3, 3]
                        renderer.alpha = 0.9 // Keep cancelled trains highly visible
                    } else {
                        renderer.strokeColor = getUIColor(for: segment.congestionFactor)
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
                let renderer = MKPolylineRenderer(polyline: polyline)
                
                if let segment = polyline.segment {
                    // Check if this segment has cancellations - treat as severe + dashed
                    if segment.cancellationRate > 0 {
                        renderer.strokeColor = UIColor.systemRed
                        renderer.lineWidth = 11 // Same as severe congestion
                        renderer.lineDashPattern = [3, 3]
                    } else {
                        renderer.strokeColor = getUIColor(for: segment.congestionFactor)
                        renderer.lineWidth = getCongestionLineWidth(segment.congestionFactor)
                        // Add dashed pattern for other types of cancellations
                        if let dashPattern = segment.dashPattern {
                            renderer.lineDashPattern = dashPattern
                        }
                    }
                    renderer.alpha = polyline.isDimmed ? 0.3 : 0.8 // Dim when showing individual segments
                } else {
                    renderer.strokeColor = UIColor.gray
                    renderer.alpha = polyline.isDimmed ? 0.3 : 0.8
                }
                
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
            
            
            return nil
        }
        
        // MARK: - Helper Methods
        private func getCongestionLineWidth(_ factor: Double) -> CGFloat {
            if factor < 1.05 {
                return 5
            } else if factor < 1.25 {
                return 7
            } else if factor < 2.0 {
                return 9
            } else {
                return 11
            }
        }
        
        private func getUIColor(for congestionFactor: Double) -> UIColor {
            if congestionFactor < 1.05 {
                return UIColor.systemGreen
            } else if congestionFactor < 1.25 {
                return UIColor.systemYellow
            } else if congestionFactor < 2.0 {
                return UIColor.systemOrange
            } else {
                return UIColor.systemRed
            }
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
        
    }
}

// MARK: - Helper Functions

func createOffsetCoordinates(from: CLLocationCoordinate2D, to: CLLocationCoordinate2D, offsetIndex: Int) -> [CLLocationCoordinate2D] {
    guard offsetIndex > 0 else { return [from, to] }
    
    // Calculate perpendicular offset (small distance to prevent overlap)
    let offsetDistance = Double(offsetIndex) * 0.0001 // About 10 meters per offset
    
    // Calculate the perpendicular direction
    let dx = to.longitude - from.longitude
    let dy = to.latitude - from.latitude
    
    // Perpendicular vector (rotated 90 degrees)
    let perpDx = -dy
    let perpDy = dx
    
    // Normalize and apply offset
    let length = sqrt(perpDx * perpDx + perpDy * perpDy)
    guard length > 0 else { return [from, to] }
    
    let offsetLat = offsetDistance * (perpDy / length)
    let offsetLon = offsetDistance * (perpDx / length)
    
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

// MARK: - Custom Polyline Classes

class SystemCongestionPolyline: MKPolyline {
    var segment: CongestionSegment?
    var isDimmed: Bool = false
}

class IndividualJourneyPolyline: MKPolyline {
    var individualSegment: IndividualJourneySegment?
    var offsetIndex: Int = 0
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

// MARK: - Segment Train Details View

struct SegmentTrainDetailsView: View {
    let segment: CongestionSegment
    @StateObject private var viewModel: SegmentTrainDetailsViewModel
    @Environment(\.dismiss) private var dismiss
    
    init(segment: CongestionSegment) {
        self.segment = segment
        self._viewModel = StateObject(wrappedValue: SegmentTrainDetailsViewModel(segment: segment))
    }
    
    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(spacing: 20) {
                    // Segment Header
                    segmentHeaderSection

                    // Summary Stats
                    if let summary = viewModel.segmentDetails?.summary {
                        summaryStatsSection(summary: summary)
                    }

                    // Train List
                    if viewModel.isLoading {
                        loadingSection
                    } else if let trains = viewModel.segmentDetails?.trains, !trains.isEmpty {
                        trainsSection(trains: trains)
                    } else if let error = viewModel.error {
                        errorSection(error: error)
                    } else {
                        noDataSection
                    }
                }
                .padding()
            }
            .background(Color.black)
            .navigationTitle("Segment Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(.ultraThinMaterial, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                    .foregroundColor(.white)
                }
            }
        }
        .preferredColorScheme(.dark)
        .task {
            await viewModel.loadTrainDetails()
        }
    }
    
    // MARK: - Header Section
    
    private var segmentHeaderSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Route Information
            VStack(alignment: .leading, spacing: 8) {
                Text("\(segment.fromStationDisplayName) → \(segment.toStationDisplayName)")
                    .font(.title2)
                    .fontWeight(.bold)
                
                Label(segment.dataSource, systemImage: "train.side.front.car")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            // Current Congestion Status
            HStack {
                Circle()
                    .fill(segment.displayColor)
                    .frame(width: 16, height: 16)
                
                Text(segment.displayCongestionLevel)
                    .font(.headline)
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 2) {
                    Text(segment.congestionFactorDisplay)
                        .font(.subheadline)
                        .fontWeight(.medium)
                    
                    Text(segment.cancellationDisplayText)
                        .font(.caption)
                        .foregroundColor(segment.cancellationRate > 10 ? .red : .secondary)
                }
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(.ultraThinMaterial)
            )
        }
    }
    
    // MARK: - Summary Stats Section
    
    private func summaryStatsSection(summary: SegmentSummary) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Summary Statistics")
                    .font(.headline)
                    .fontWeight(.semibold)
                
                Spacer()
                

            }


            
            LazyVGrid(columns: [
                GridItem(.flexible()),
                GridItem(.flexible()),
                GridItem(.flexible())
            ], spacing: 16) {

                
                SegmentStatCard(
                    title: "Avg Departure Delay",
                    value: summary.averageDepartureDelay > 0 ? "+\(Int(summary.averageDepartureDelay))m" : "On time",
                    color: summary.averageDepartureDelay <= 2 ? .green : summary.averageDepartureDelay <= 6 ? .yellow : .orange,
                    icon: "arrow.up.circle.fill"
                )

                SegmentStatCard(
                    title: "Avg Arrival Delay",
                    value: summary.averageArrivalDelay > 0 ? "+\(Int(summary.averageArrivalDelay))m" : "On time",
                    color: summary.averageArrivalDelay <= 2 ? .green : summary.averageArrivalDelay <= 6 ? .yellow : .orange,
                    icon: "arrow.down.circle.fill"
                )
                
                SegmentStatCard(
                    title: "Cancellation Rate",
                    value: "\(Int(segment.cancellationRate))%",
                    color: segment.cancellationRate < 5 ? .green : 
                           segment.cancellationRate < 15 ? .orange : .red,
                    icon: "xmark.circle.fill"
                )
            }
        }
    }
    
    // MARK: - Trains Section
    
    private func trainsSection(trains: [SegmentTrainDetail]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Recent Trains")
                .font(.headline)
                .fontWeight(.semibold)
            
            LazyVStack(spacing: 12) {
                ForEach(trains) { train in
                    SegmentTrainDetailCard(train: train)
                }
            }
        }
    }
    
    // MARK: - Loading & Error States
    
    private var loadingSection: some View {
        VStack(spacing: 16) {
            ProgressView()
                .progressViewStyle(CircularProgressViewStyle(tint: .orange))
                .scaleEffect(1.2)
            
            Text("Loading train details...")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(height: 100)
    }
    
    private func errorSection(error: String) -> some View {
        VStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.largeTitle)
                .foregroundColor(.orange)
            
            Text("Unable to load train details")
                .font(.headline)
            
            Text(error)
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(.ultraThinMaterial)
        )
    }
    
    private var noDataSection: some View {
        VStack(spacing: 12) {
            Image(systemName: "train.side.front.car")
                .font(.largeTitle)
                .foregroundColor(.gray)
            
            Text("No train data available")
                .font(.headline)
            
            Text("Try adjusting the time window or check back later")
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(.ultraThinMaterial)
        )
    }
}

// MARK: - Supporting Views for Segment Details

private struct SegmentStatCard: View {
    let title: String
    let value: String
    let color: Color
    let icon: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(color)
                
                Spacer()
            }
            
            Text(value)
                .font(.title3)
                .fontWeight(.bold)
                .foregroundColor(color)
            
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.leading)
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(.ultraThinMaterial)
        )
    }
}

private struct SegmentTrainDetailCard: View {
    let train: SegmentTrainDetail
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header with train ID and line
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Train \(train.trainId)")
                        .font(.headline)
                        .fontWeight(.semibold)
                    
                    Text(train.line)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 2) {
                    if !train.delayCategoryDisplay.isEmpty {
                        Text(train.delayCategoryDisplay)
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundColor(train.delayCategoryColor)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(
                                Capsule()
                                    .fill(train.delayCategoryColor.opacity(0.2))
                            )
                    }
                    
                    Text(train.transitTimeDisplay)
                }
            }
            
            // Time details
            VStack(spacing: 8) {
                SegmentTimeDetailRow(
                    label: "Departure",
                    scheduled: train.scheduledDeparture,
                    actual: train.actualDeparture,
                    delay: train.departureDelayDisplay,
                    delayColor: train.departureDelayMinutes > 0 ? .orange : .green
                )
                
                SegmentTimeDetailRow(
                    label: "Arrival",
                    scheduled: train.scheduledArrival,
                    actual: train.actualArrival,
                    delay: train.arrivalDelayDisplay,
                    delayColor: train.arrivalDelayMinutes > 0 ? .orange : .green
                )
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(.ultraThinMaterial)
        )
    }
}

private struct SegmentTimeDetailRow: View {
    let label: String
    let scheduled: Date
    let actual: Date
    let delay: String
    let delayColor: Color
    
    var body: some View {
        HStack {
            Text(label)
                .font(.caption)
                .foregroundColor(.secondary)
                .frame(width: 70, alignment: .leading)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(scheduled.formatted(date: .omitted, time: .shortened))
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .strikethrough(scheduled != actual)
                
                if scheduled != actual {
                    Text(actual.formatted(date: .omitted, time: .shortened))
                        .font(.caption)
                        .fontWeight(.medium)
                }
            }
            
            Spacer()
            
            Text(delay)
                .font(.caption)
                .fontWeight(.medium)
                .foregroundColor(delayColor)
        }
    }
}

// MARK: - View Model for Segment Details

@MainActor
class SegmentTrainDetailsViewModel: ObservableObject {
    @Published var segmentDetails: SegmentTrainDetailsResponse?
    @Published var isLoading = false
    @Published var error: String?
    
    private let segment: CongestionSegment
    
    init(segment: CongestionSegment) {
        self.segment = segment
    }
    
    func loadTrainDetails() async {
        isLoading = true
        error = nil
        
        do {
            let details = try await APIService.shared.fetchSegmentTrainDetails(
                fromStation: segment.fromStation,
                toStation: segment.toStation,
                dataSource: segment.dataSource,
                limit: 50
            )
            
            segmentDetails = details
            
        } catch {
            self.error = error.localizedDescription
            print("Failed to load segment train details: \(error)")
        }
        
        isLoading = false
    }
}

