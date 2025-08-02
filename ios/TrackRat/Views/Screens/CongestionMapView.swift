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
    
    func fetchCongestionData(timeWindowHours: Int = 3, dataSource: String? = nil) async {
        isLoading = true
        error = nil
        
        do {
            let response = try await APIService.shared.fetchCongestionData(
                timeWindowHours: timeWindowHours,
                dataSource: dataSource
            )
            
            segments = response.segments
            
            // Extract unique stations
            var stationMap: [String: MapStation] = [:]
            
            for segment in segments {
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
            
            stations = Array(stationMap.values)
            
        } catch {
            self.error = error.localizedDescription
            print("Failed to fetch congestion data: \(error)")
        }
        
        isLoading = false
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
        for segment in segments {
            if let fromCoords = Stations.getCoordinates(for: segment.fromStation),
               let toCoords = Stations.getCoordinates(for: segment.toStation) {
                let coordinates = [fromCoords, toCoords]
                
                let polyline = SystemCongestionPolyline(coordinates: coordinates, count: coordinates.count)
                polyline.segment = segment
                mapView.addOverlay(polyline)
            }
        }
        
        // Add station annotations
        for station in stations {
            let annotation = SystemStationAnnotation()
            annotation.coordinate = station.coordinate
            annotation.title = station.code
            annotation.subtitle = station.name
            annotation.station = station
            mapView.addAnnotation(annotation)
        }
        
        // Update coordinator with current segments for tap handling
        context.coordinator.segments = segments
        context.coordinator.onSegmentTap = onSegmentTap
    }
    
    func makeCoordinator() -> Coordinator {
        Coordinator()
    }
    
    class Coordinator: NSObject, MKMapViewDelegate {
        var segments: [CongestionSegment] = []
        var onSegmentTap: (CongestionSegment) -> Void = { _ in }
        
        // MARK: - Polyline Rendering
        func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
            if let polyline = overlay as? SystemCongestionPolyline {
                let renderer = MKPolylineRenderer(polyline: polyline)
                
                // Convert congestion factor to color
                if let segment = polyline.segment {
                    renderer.strokeColor = getUIColor(for: segment.congestionFactor)
                } else {
                    renderer.strokeColor = UIColor.gray
                }
                renderer.lineWidth = getCongestionLineWidth(polyline.segment?.congestionFactor ?? 1.0)
                renderer.alpha = 0.8
                return renderer
            }
            return MKOverlayRenderer(overlay: overlay)
        }
        
        // MARK: - Annotation Rendering
        func mapView(_ mapView: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            if annotation is MKUserLocation {
                return nil // Use default user location view
            }
            
            guard let stationAnnotation = annotation as? SystemStationAnnotation else {
                return nil
            }
            
            let identifier = "SystemStationAnnotation"
            var annotationView = mapView.dequeueReusableAnnotationView(withIdentifier: identifier)
            
            if annotationView == nil {
                annotationView = MKAnnotationView(annotation: annotation, reuseIdentifier: identifier)
                annotationView?.canShowCallout = true
            } else {
                annotationView?.annotation = annotation
            }
            
            // Create custom station pin (without circles)
            if let station = stationAnnotation.station {
                let pinView = createSystemStationPinView(for: station)
                annotationView?.image = pinView.asUIImage()
                annotationView?.centerOffset = CGPoint(x: 0, y: -pinView.frame.height / 2)
            }
            
            return annotationView
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
        
        private func createSystemStationPinView(for station: MapStation) -> UIView {
            let containerView = UIView(frame: CGRect(x: 0, y: 0, width: 50, height: 18))
            
            // Only label for station code (no circle)
            let label = UILabel(frame: CGRect(x: 0, y: 0, width: 50, height: 18))
            label.text = station.code
            label.font = UIFont.systemFont(ofSize: 12, weight: .semibold)
            label.textColor = .white
            label.textAlignment = .center
            label.backgroundColor = UIColor.black.withAlphaComponent(0.8)
            label.layer.cornerRadius = 9
            label.clipsToBounds = true
            
            containerView.addSubview(label)
            
            return containerView
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
                    
                    Text("vs normal time")
                        .font(.caption2)
                        .foregroundColor(.secondary)
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
                
                Text("\(summary.returnedTrains) of \(summary.totalTrains) trains")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            LazyVGrid(columns: [
                GridItem(.flexible()),
                GridItem(.flexible())
            ], spacing: 16) {
                SegmentStatCard(
                    title: "On-Time Performance",
                    value: "\(summary.onTimePercentage.formatted(.number.precision(.fractionLength(1))))%",
                    color: summary.onTimePercentage >= 80 ? .green : summary.onTimePercentage >= 60 ? .orange : .red,
                    icon: "clock.fill"
                )
                
                SegmentStatCard(
                    title: "Avg Congestion",
                    value: "\(Int((summary.averageCongestionFactor - 1) * 100))%",
                    color: summary.averageCongestionFactor < 1.05 ? .green : summary.averageCongestionFactor < 1.25 ? .yellow : .orange,
                    icon: "gauge.medium"
                )
                
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
                    
                    Text(train.congestionFactorDisplay)
                        .font(.caption2)
                        .foregroundColor(.secondary)
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