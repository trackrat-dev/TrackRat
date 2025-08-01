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
            SegmentDetailSheet(segment: segment)
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
                if let coords = segment.fromStationCoords {
                    stationMap[segment.fromStation] = MapStation(
                        code: segment.fromStation,
                        name: segment.fromStationDisplayName,
                        coordinate: CLLocationCoordinate2D(latitude: coords.lat, longitude: coords.lon)
                    )
                }
                if let coords = segment.toStationCoords {
                    stationMap[segment.toStation] = MapStation(
                        code: segment.toStation,
                        name: segment.toStationDisplayName,
                        coordinate: CLLocationCoordinate2D(latitude: coords.lat, longitude: coords.lon)
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

struct SegmentDetailSheet: View {
    let segment: CongestionSegment
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationView {
            VStack(alignment: .leading, spacing: 20) {
                // Route header
                VStack(alignment: .leading, spacing: 8) {
                    Text("\(segment.fromStationDisplayName) → \(segment.toStationDisplayName)")
                        .font(.title2)
                        .fontWeight(.bold)
                    
                    Label(segment.dataSource, systemImage: "train.side.front.car")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                // Congestion status
                HStack {
                    Circle()
                        .fill(segment.displayColor)
                        .frame(width: 16, height: 16)
                    
                    Text(segment.displayCongestionLevel)
                        .font(.headline)
                    
                    Spacer()
                    
                    Text("\(Int((segment.congestionFactor - 1) * 100))% slower")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding()
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(.ultraThinMaterial)
                )
                
                // Statistics
                VStack(spacing: 16) {
                    StatRow(
                        label: "Average Transit Time",
                        value: segment.averageTransitTimeText
                    )
                    
                    StatRow(
                        label: "Normal Time",
                        value: "\(Int(segment.baselineMinutes.rounded())) min"
                    )
                    
                    StatRow(
                        label: "Sample Size",
                        value: segment.sampleCountText
                    )
                    
                    StatRow(
                        label: "Last Updated",
                        value: segment.lastUpdated.formatted(date: .omitted, time: .shortened)
                    )
                }
                
                Spacer()
            }
            .padding()
            .navigationTitle("Segment Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
}

struct StatRow: View {
    let label: String
    let value: String
    
    var body: some View {
        HStack {
            Text(label)
                .foregroundColor(.secondary)
            Spacer()
            Text(value)
                .fontWeight(.medium)
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
            if let fromCoords = segment.fromStationCoords,
               let toCoords = segment.toStationCoords {
                let coordinates = [
                    CLLocationCoordinate2D(latitude: fromCoords.lat, longitude: fromCoords.lon),
                    CLLocationCoordinate2D(latitude: toCoords.lat, longitude: toCoords.lon)
                ]
                
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