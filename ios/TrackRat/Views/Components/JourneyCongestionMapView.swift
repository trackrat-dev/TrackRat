import SwiftUI
import MapKit
import UIKit

struct JourneyCongestionMapView: View {
    @StateObject private var viewModel: JourneyCongestionViewModel
    @State private var selectedSegment: CongestionSegment?
    
    let train: TrainV2
    let userOrigin: String?
    let userDestination: String?
    
    init(train: TrainV2, userOrigin: String?, userDestination: String?) {
        self.train = train
        self.userOrigin = userOrigin
        self.userDestination = userDestination
        self._viewModel = StateObject(wrappedValue: JourneyCongestionViewModel(
            train: train,
            userOrigin: userOrigin,
            userDestination: userDestination
        ))
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Map container with fixed height
            ZStack {
                if viewModel.isLoading {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(.ultraThinMaterial)
                        .frame(height: 200)
                        .overlay(
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: .orange))
                        )
                } else if !viewModel.filteredSegments.isEmpty {
                    CongestionMapKitView(
                        region: $viewModel.mapRegion,
                        segments: viewModel.filteredSegments,
                        stations: viewModel.journeyStations,
                        onSegmentTap: { segment in
                            selectedSegment = segment
                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        }
                    )
                    .frame(height: 200)
                    .cornerRadius(12)
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(Color.white.opacity(0.2), lineWidth: 1)
                    )
                } else {
                    // No congestion data
                    RoundedRectangle(cornerRadius: 12)
                        .fill(.ultraThinMaterial)
                        .frame(height: 200)
                        .overlay(
                            VStack(spacing: 8) {
                                Image(systemName: "map.fill")
                                    .font(.largeTitle)
                                    .foregroundColor(.gray)
                                Text("No congestion data available")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        )
                }
            }
            
            // Congestion legend
            if !viewModel.filteredSegments.isEmpty {
                HStack(spacing: 16) {
                    LegendItem(color: .green, label: "Normal")
                    LegendItem(color: .yellow, label: "Moderate")
                    LegendItem(color: .orange, label: "Heavy")
                    LegendItem(color: .red, label: "Severe")
                }
                .padding(.top, 8)
                .font(.caption2)
            }
        }
        .sheet(item: $selectedSegment) { segment in
            SegmentDetailSheet(segment: segment)
        }
        .task {
            await viewModel.loadCongestionData()
        }
    }
}

// MARK: - View Model

@MainActor
class JourneyCongestionViewModel: ObservableObject {
    @Published var filteredSegments: [CongestionSegment] = []
    @Published var journeyStations: [JourneyStation] = []
    @Published var mapRegion = MKCoordinateRegion()
    @Published var isLoading = false
    
    private let train: TrainV2
    private let userOrigin: String?
    private let userDestination: String?
    
    init(train: TrainV2, userOrigin: String?, userDestination: String?) {
        self.train = train
        self.userOrigin = userOrigin
        self.userDestination = userDestination
    }
    
    func loadCongestionData() async {
        isLoading = true
        
        do {
            // Fetch congestion data
            let congestionData = try await APIService.shared.fetchCongestionData(timeWindowHours: 3)
            
            // Filter segments to only those in the user's journey
            let journeyStationCodes = getJourneyStationCodes()
            filteredSegments = congestionData.segments.filter { segment in
                journeyStationCodes.contains(segment.fromStation) && 
                journeyStationCodes.contains(segment.toStation)
            }
            
            // Create journey stations for map annotations
            createJourneyStations()
            
            // Set map region to show the journey
            setMapRegion()
            
        } catch {
            print("Failed to load congestion data: \(error)")
        }
        
        isLoading = false
    }
    
    private func getJourneyStationCodes() -> Set<String> {
        guard let stops = train.stops,
              let originCode = userOrigin,
              let destinationName = userDestination else {
            return []
        }
        
        // Find origin and destination indices
        let originIndex = stops.firstIndex { $0.stationCode.uppercased() == originCode.uppercased() }
        let destinationIndex = stops.firstIndex { stop in
            if let destinationCode = Stations.getStationCode(destinationName) {
                return stop.stationCode.uppercased() == destinationCode.uppercased()
            }
            return stop.stationName.lowercased() == destinationName.lowercased()
        }
        
        guard let startIdx = originIndex, let endIdx = destinationIndex, startIdx <= endIdx else {
            return []
        }
        
        // Get all station codes in the journey
        let journeyStops = stops[startIdx...endIdx]
        return Set(journeyStops.compactMap { $0.stationCode })
    }
    
    private func createJourneyStations() {
        guard let stops = train.stops,
              let originCode = userOrigin,
              let destinationName = userDestination else {
            return
        }
        
        var stations: [JourneyStation] = []
        let journeyStationCodes = getJourneyStationCodes()
        
        for stop in stops where journeyStationCodes.contains(stop.stationCode) {
            // Find coordinates from congestion segments
            var coordinate: CLLocationCoordinate2D?
            
            for segment in filteredSegments {
                if segment.fromStation == stop.stationCode,
                   let coords = segment.fromStationCoords {
                    coordinate = CLLocationCoordinate2D(latitude: coords.lat, longitude: coords.lon)
                    break
                } else if segment.toStation == stop.stationCode,
                          let coords = segment.toStationCoords {
                    coordinate = CLLocationCoordinate2D(latitude: coords.lat, longitude: coords.lon)
                    break
                }
            }
            
            if let coordinate = coordinate {
                let isDestination: Bool
                if let destinationCode = Stations.getStationCode(destinationName) {
                    isDestination = stop.stationCode.uppercased() == destinationCode.uppercased()
                } else {
                    isDestination = stop.stationName.lowercased() == destinationName.lowercased()
                }
                
                stations.append(JourneyStation(
                    code: stop.stationCode,
                    name: stop.stationName,
                    coordinate: coordinate,
                    isOrigin: stop.stationCode.uppercased() == originCode.uppercased(),
                    isDestination: isDestination
                ))
            }
        }
        
        journeyStations = stations
    }
    
    private func setMapRegion() {
        guard !journeyStations.isEmpty else { return }
        
        let coordinates = journeyStations.map { $0.coordinate }
        let minLat = coordinates.map { $0.latitude }.min() ?? 0
        let maxLat = coordinates.map { $0.latitude }.max() ?? 0
        let minLon = coordinates.map { $0.longitude }.min() ?? 0
        let maxLon = coordinates.map { $0.longitude }.max() ?? 0
        
        let center = CLLocationCoordinate2D(
            latitude: (minLat + maxLat) / 2,
            longitude: (minLon + maxLon) / 2
        )
        
        let span = MKCoordinateSpan(
            latitudeDelta: (maxLat - minLat) * 1.5,
            longitudeDelta: (maxLon - minLon) * 1.5
        )
        
        mapRegion = MKCoordinateRegion(center: center, span: span)
    }
}

// MARK: - Supporting Models

struct JourneyStation: Identifiable {
    let id = UUID()
    let code: String
    let name: String
    let coordinate: CLLocationCoordinate2D
    let isOrigin: Bool
    let isDestination: Bool
}

// MARK: - Preview

// MARK: - MapKit-based Congestion Map View
struct CongestionMapKitView: UIViewRepresentable {
    @Binding var region: MKCoordinateRegion
    let segments: [CongestionSegment]
    let stations: [JourneyStation]
    let onSegmentTap: (CongestionSegment) -> Void
    
    func makeUIView(context: Context) -> MKMapView {
        let mapView = MKMapView()
        mapView.delegate = context.coordinator
        mapView.showsUserLocation = true
        mapView.userTrackingMode = .none
        
        // Configure map appearance
        mapView.mapType = .standard
        mapView.showsCompass = false
        mapView.showsScale = false
        
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
                
                let polyline = CongestionPolyline(coordinates: coordinates, count: coordinates.count)
                polyline.segment = segment
                mapView.addOverlay(polyline)
            }
        }
        
        // Add station annotations
        for station in stations {
            let annotation = StationAnnotation()
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
            if let polyline = overlay as? CongestionPolyline {
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
            
            guard let stationAnnotation = annotation as? StationAnnotation else {
                return nil
            }
            
            let identifier = "StationAnnotation"
            var annotationView = mapView.dequeueReusableAnnotationView(withIdentifier: identifier)
            
            if annotationView == nil {
                annotationView = MKAnnotationView(annotation: annotation, reuseIdentifier: identifier)
                annotationView?.canShowCallout = true
            } else {
                annotationView?.annotation = annotation
            }
            
            // Create custom station pin
            if let station = stationAnnotation.station {
                let pinView = createStationPinView(for: station)
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
        
        private func createStationPinView(for station: JourneyStation) -> UIView {
            let containerView = UIView(frame: CGRect(x: 0, y: 0, width: 40, height: 16))
            
            // Only label for station code (no circle)
            let label = UILabel(frame: CGRect(x: 0, y: 0, width: 40, height: 16))
            label.text = station.code
            label.font = UIFont.systemFont(ofSize: 10, weight: .semibold)
            label.textColor = .white
            label.textAlignment = .center
            label.backgroundColor = UIColor.black.withAlphaComponent(0.8)
            label.layer.cornerRadius = 8
            label.clipsToBounds = true
            
            containerView.addSubview(label)
            
            return containerView
        }
    }
}

// MARK: - Custom Polyline Class
class CongestionPolyline: MKPolyline {
    var segment: CongestionSegment?
}

// MARK: - Custom Annotation Class
class StationAnnotation: NSObject, MKAnnotation {
    var coordinate: CLLocationCoordinate2D = CLLocationCoordinate2D()
    var title: String?
    var subtitle: String?
    var station: JourneyStation!
}

// MARK: - UIView Extension for Image Conversion
extension UIView {
    func asUIImage() -> UIImage {
        let renderer = UIGraphicsImageRenderer(bounds: bounds)
        return renderer.image { rendererContext in
            layer.render(in: rendererContext.cgContext)
        }
    }
}

#Preview {
    JourneyCongestionMapView(
        train: TrainV2(
            trainId: "2307",
            line: LineInfo(code: "NEC", name: "Northeast Corridor", color: "#0066CC"),
            destination: "New York Penn Station",
            departure: StationTiming(code: "TR", name: "Trenton", scheduledTime: Date(), updatedTime: nil, actualTime: nil, track: nil),
            arrival: nil,
            trainPosition: nil,
            dataFreshness: nil,
            isCancelled: false,
            isCompleted: false,
            stops: []
        ),
        userOrigin: "TR",
        userDestination: "New York Penn Station"
    )
    .padding()
    .background(Color.black)
}