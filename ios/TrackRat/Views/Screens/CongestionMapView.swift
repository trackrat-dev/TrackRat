import SwiftUI
import MapKit
import UIKit

struct CongestionMapView: View {
    @StateObject private var viewModel = CongestionMapViewModel()
    @State private var region = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 40.7348, longitude: -74.1644), // Newark Penn as default
        span: MKCoordinateSpan(latitudeDelta: 1.5, longitudeDelta: 1.5)
    )
    @State private var selectedSegment: CongestionSegment?
    @State private var showingFilters = false
    @State private var timeWindow = 3
    @State private var selectedDataSource: String = "All"
    
    var body: some View {
        ZStack {
            // Map
            SystemCongestionMapView(
                region: $region,
                segments: viewModel.segments,
                stations: viewModel.stations,
                selectedRoute: nil,  // No route highlighting in standalone map view
                onSegmentTap: { segment in
                    selectedSegment = segment
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
                    Text("CONGESTION LEVELS")
                        .font(.caption2)
                        .fontWeight(.semibold)
                        .foregroundColor(.secondary)
                    
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

@MainActor
class CongestionMapViewModel: ObservableObject {
    @Published var segments: [CongestionSegment] = []
    @Published var stations: [MapStation] = []
    @Published var isLoading = false
    @Published var error: String?
    
    // Store all segments and filter based on display mode
    private var allSegments: [CongestionSegment] = []
    private var allStations: [MapStation] = []
    private var currentDisplayMode: MapDisplayMode = .overallCongestion
    
    init() {
        // Start loading congestion data immediately
        print("🚦 CongestionMapViewModel init - starting immediate data load")
        Task {
            await fetchCongestionData()
        }
    }
    
    func fetchCongestionData(timeWindowHours: Int = 3, dataSource: String? = nil) async {
        print("🚦 Starting congestion data fetch (timeWindow: \(timeWindowHours), dataSource: \(dataSource ?? "All"))")
        isLoading = true
        error = nil
        
        do {
            let response = try await APIService.shared.fetchCongestionData(
                timeWindowHours: timeWindowHours,
                dataSource: dataSource
            )
            
            print("🚦 API response received: \(response.segments.count) segments")
            
            // Store all segments
            allSegments = response.segments
            
            // Extract unique stations
            var stationMap: [String: MapStation] = [:]
            
            for segment in allSegments {
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
            
            allStations = Array(stationMap.values)
            print("🚦 Processed \(allStations.count) stations from segments")
            
            // Filter based on current display mode
            applyDisplayModeFilter()
            
        } catch {
            self.error = error.localizedDescription
            print("🚦 Failed to fetch congestion data: \(error)")
        }
        
        isLoading = false
        print("🚦 Congestion data fetch completed. Final segments: \(segments.count)")
    }
    
    func updateDisplayMode(_ mode: MapDisplayMode) async {
        print("🚦 Updating display mode to: \(mode)")
        currentDisplayMode = mode
        applyDisplayModeFilter()
    }
    
    private func applyDisplayModeFilter() {
        switch currentDisplayMode {
        case .overallCongestion:
            // Show all segments and stations
            segments = allSegments
            stations = allStations
            print("🚦 Applied overall congestion filter: \(segments.count) segments")
            
        case .journeyFocus(_, let origin, let destination, let trainStops):
            // Filter to show only segments relevant to this journey using actual train stops
            let journeySegments = getJourneySegments(trainStops: trainStops)
            let journeyStations = getJourneyStations(for: journeySegments)
            
            segments = journeySegments
            stations = journeyStations
            print("🚦 Applied journey focus filter: \(segments.count) segments for \(origin) → \(destination) with stops: \(trainStops)")
        }
    }
    
    private func getJourneySegments(trainStops: [String]) -> [CongestionSegment] {
        print("🚦 Filtering segments for train stops: \(trainStops)")
        print("🚦 Available segments: \(allSegments.map { "\($0.fromStation)→\($0.toStation)" })")
        
        // Filter segments that are part of this train's actual route
        let journeySegments = allSegments.filter { segment in
            if let fromIndex = trainStops.firstIndex(of: segment.fromStation),
               let toIndex = trainStops.firstIndex(of: segment.toStation) {
                // Include segments where stations are adjacent in the train's route
                let isAdjacent = toIndex == fromIndex + 1
                if isAdjacent {
                    print("🚦 ✅ Including segment: \(segment.fromStation)→\(segment.toStation)")
                }
                return isAdjacent
            }
            return false
        }
        
        print("🚦 Final journey segments: \(journeySegments.map { "\($0.fromStation)→\($0.toStation)" })")
        return journeySegments
    }
    
    // Keep the old method for backward compatibility
    private func getJourneySegments(from origin: String, to destination: String) -> [CongestionSegment] {
        // Get the route stations between origin and destination
        let routeStations = getStationCodesInRoute(from: origin, to: destination)
        
        // Filter segments that are part of this route
        return allSegments.filter { segment in
            if let fromIndex = routeStations.firstIndex(of: segment.fromStation),
               let toIndex = routeStations.firstIndex(of: segment.toStation) {
                // Include segments where stations are adjacent in the route
                return toIndex == fromIndex + 1
            }
            return false
        }
    }
    
    private func getJourneyStations(for segments: [CongestionSegment]) -> [MapStation] {
        // Get unique stations from the journey segments
        var stationCodes = Set<String>()
        
        for segment in segments {
            stationCodes.insert(segment.fromStation)
            stationCodes.insert(segment.toStation)
        }
        
        return allStations.filter { station in
            stationCodes.contains(station.code)
        }
    }
    
    private func getStationCodesInRoute(from: String, to: String) -> [String] {
        // Use the same logic from the existing route highlighting
        let necCorridor = ["NY", "NP", "TR", "PJ", "MP", "NBK", "MET", "EWR", "SECAUCUS", "HOB"]
        
        if let fromIndex = necCorridor.firstIndex(of: from),
           let toIndex = necCorridor.firstIndex(of: to) {
            if fromIndex < toIndex {
                return Array(necCorridor[fromIndex...toIndex])
            } else {
                return Array(necCorridor[toIndex...fromIndex].reversed())
            }
        }
        
        // Fallback to just the two stations
        return [from, to]
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
        NavigationView {
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
            .navigationTitle("Filter Options")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Apply") {
                        onApply()
                        dismiss()
                    }
                    .fontWeight(.semibold)
                }
            }
        }
    }
}



// MARK: - MapKit-based System Congestion Map View
struct SystemCongestionMapView: UIViewRepresentable {
    @Binding var region: MKCoordinateRegion
    let segments: [CongestionSegment]
    let stations: [MapStation]
    let selectedRoute: TripPair?
    let onSegmentTap: (CongestionSegment) -> Void
    
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
        
        // Clear existing overlays and annotations
        mapView.removeOverlays(mapView.overlays)
        mapView.removeAnnotations(mapView.annotations.filter { !($0 is MKUserLocation) })
        
        // Add congestion polylines
        print("🗺️ Adding \(segments.count) congestion segments to map")
        for segment in segments {
            if let fromCoords = Stations.getCoordinates(for: segment.fromStation),
               let toCoords = Stations.getCoordinates(for: segment.toStation) {
                let coordinates = [fromCoords, toCoords]
                
                let polyline = SystemCongestionPolyline(coordinates: coordinates, count: coordinates.count)
                polyline.segment = segment
                mapView.addOverlay(polyline)
                print("🗺️ Added segment: \(segment.fromStation) → \(segment.toStation) (congestion: \(segment.congestionFactor))")
            } else {
                print("🗺️ Missing coordinates for segment: \(segment.fromStation) → \(segment.toStation)")
            }
        }
        
        // Station annotations removed - only showing train segments
        
        // Update coordinator with current segments for tap handling
        context.coordinator.segments = segments
        context.coordinator.onSegmentTap = onSegmentTap
        context.coordinator.selectedRoute = selectedRoute
    }
    
    func makeCoordinator() -> Coordinator {
        Coordinator()
    }
    
    class Coordinator: NSObject, MKMapViewDelegate {
        var segments: [CongestionSegment] = []
        var onSegmentTap: (CongestionSegment) -> Void = { _ in }
        var selectedRoute: TripPair?
        
        // MARK: - Polyline Rendering
        func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
            if let polyline = overlay as? SystemCongestionPolyline {
                let renderer = MKPolylineRenderer(polyline: polyline)
                
                // Check if this segment is part of the selected route
                let isSelectedSegment = isSegmentInSelectedRoute(polyline.segment)
                
                if let segment = polyline.segment {
                    print("🎨 Rendering segment: \(segment.fromStation) → \(segment.toStation), congestion: \(segment.congestionFactor), selected: \(isSelectedSegment)")
                }
                
                // Convert congestion factor to color
                if let segment = polyline.segment {
                    renderer.strokeColor = getUIColor(for: segment.congestionFactor)
                    
                    // Add dashed pattern for cancellations
                    if let dashPattern = segment.dashPattern {
                        renderer.lineDashPattern = dashPattern
                    }
                } else {
                    renderer.strokeColor = UIColor.gray
                }
                
                // Adjust appearance based on selection
                if selectedRoute == nil {
                    // No route selected - show all segments at full visibility
                    renderer.lineWidth = getCongestionLineWidth(polyline.segment?.congestionFactor ?? 1.0)
                    renderer.alpha = 0.8
                } else if isSelectedSegment {
                    // Route selected and this segment is part of it - emphasize
                    renderer.lineWidth = getCongestionLineWidth(polyline.segment?.congestionFactor ?? 1.0) * 1.5
                    renderer.alpha = 1.0
                } else {
                    // Route selected but this segment is not part of it - dim
                    renderer.lineWidth = getCongestionLineWidth(polyline.segment?.congestionFactor ?? 1.0)
                    renderer.alpha = 0.4
                }
                
                return renderer
            }
            return MKOverlayRenderer(overlay: overlay)
        }
        
        // MARK: - Annotation Rendering
        func mapView(_ mapView: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            // Only show default user location, no station annotations
            if annotation is MKUserLocation {
                return nil // Use default user location view
            }
            return nil
        }
        
        // MARK: - Helper Methods
        private func isSegmentInSelectedRoute(_ segment: CongestionSegment?) -> Bool {
            guard let segment = segment,
                  let route = selectedRoute else {
                return false
            }
            
            // Get all station codes that are part of the route
            let routeStations = getStationCodesInRoute(from: route.departureCode, to: route.destinationCode)
            
            // Check if both segment stations are in the route and adjacent
            if let fromIndex = routeStations.firstIndex(of: segment.fromStation),
               let toIndex = routeStations.firstIndex(of: segment.toStation) {
                // Segment is part of route if stations are adjacent in the correct order
                return toIndex == fromIndex + 1
            }
            
            return false
        }
        
        private func getStationCodesInRoute(from: String, to: String) -> [String] {
            // For now, return a simple path between stations
            // In a real implementation, this would use actual route data
            // This is a simplified version that assumes direct routes
            
            // Define major corridor routes
            let necCorridor = ["NY", "NP", "TR", "PJ", "MP", "NBK", "MET", "EWR", "SECAUCUS", "HOB"]
            
            if let fromIndex = necCorridor.firstIndex(of: from),
               let toIndex = necCorridor.firstIndex(of: to) {
                if fromIndex < toIndex {
                    return Array(necCorridor[fromIndex...toIndex])
                } else {
                    return Array(necCorridor[toIndex...fromIndex].reversed())
                }
            }
            
            // Fallback to just the two stations
            return [from, to]
        }
        
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
        
    }
}

// MARK: - Custom Polyline Class for System Map
class SystemCongestionPolyline: MKPolyline {
    var segment: CongestionSegment?
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
        NavigationView {
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
            .navigationTitle("Segment Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
            .refreshable {
                await viewModel.loadTrainDetails()
            }
        }
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
                    color: summary.averageDepartureDelay <= 0 ? .green : summary.averageDepartureDelay <= 5 ? .yellow : .orange,
                    icon: "arrow.up.circle.fill"
                )
                
                SegmentStatCard(
                    title: "Avg Arrival Delay",
                    value: summary.averageArrivalDelay > 0 ? "+\(Int(summary.averageArrivalDelay))m" : "On time",
                    color: summary.averageArrivalDelay <= 0 ? .green : summary.averageArrivalDelay <= 5 ? .yellow : .orange,
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