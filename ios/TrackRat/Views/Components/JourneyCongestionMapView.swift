import SwiftUI
import MapKit
import UIKit

struct JourneyCongestionMapView: View {
    @EnvironmentObject private var appState: AppState
    @StateObject private var viewModel: JourneyCongestionViewModel
    @State private var routeStatusContext: RouteStatusContext?

    let train: TrainV2
    let userOrigin: String?
    let userDestination: String?
    let onSegmentTap: ((CongestionSegment) -> Void)?

    init(train: TrainV2, userOrigin: String?, userDestination: String?, onSegmentTap: ((CongestionSegment) -> Void)? = nil) {
        self.train = train
        self.userOrigin = userOrigin
        self.userDestination = userDestination
        self.onSegmentTap = onSegmentTap
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
                        trainPositions: viewModel.trainPositions,
                        highlightMode: appState.mapHighlightMode,
                        onSegmentTap: { segment in
                            // Call parent callback if provided, otherwise handle locally
                            if let onSegmentTap = onSegmentTap {
                                onSegmentTap(segment)
                            } else {
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
                            }
                        }
                    )
                    .frame(height: 200)
                    .cornerRadius(TrackRatTheme.CornerRadius.md)
                    .overlay(
                        RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                            .stroke(TrackRatTheme.Colors.borderSecondary, lineWidth: 1)
                    )
                } else {
                    // No congestion data
                    RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
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
            
            // Legend adapts to train system's preferred mode
            if !viewModel.filteredSegments.isEmpty {
                let trainMode = TrainSystem(rawValue: train.dataSource)?.preferredHighlightMode ?? .delays
                CompactCongestionLegend(highlightMode: trainMode)
                    .padding(.top, 8)
            }
        }
        .sheet(item: $routeStatusContext) { context in
            RouteStatusView(context: context)
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
    @Published var trainPositions: [TrainLocationData] = []
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
            let congestionData = try await APIService.shared.fetchCongestionData(timeWindowHours: 1)
            
            // Use train's actual data source for filtering
            let expectedDataSource = train.dataSource

            // Filter segments to any valid forward path in the user's journey
            // Expand skip-stop gaps using route topology so intermediate canonical segments match
            let rawStationCodes = getJourneyStationCodes()
            let journeyStationCodes = RouteTopology.expandStationCodes(rawStationCodes, dataSource: expectedDataSource)
            print("🚦 Journey station codes: \(rawStationCodes) → expanded: \(journeyStationCodes)")
            print("🚦 Expected data source: \(expectedDataSource)")
            print("🚦 Total segments to filter: \(congestionData.aggregatedSegments.count)")
            
            filteredSegments = congestionData.aggregatedSegments.filter { segment in
                // First check if data source matches train's system
                guard segment.dataSource == expectedDataSource else {
                    return false
                }
                
                // Find indices of from and to stations
                guard let fromIndex = journeyStationCodes.firstIndex(of: segment.fromStation),
                      let toIndex = journeyStationCodes.firstIndex(of: segment.toStation) else {
                    print("🚦 ❌ Station not found in journey: \(segment.fromStation) → \(segment.toStation)")
                    return false
                }
                
                // Include only consecutive segments (exact journey path)
                let isValid = toIndex == fromIndex + 1
                print("🚦 \(isValid ? "✅" : "❌") Segment: \(segment.fromStation) → \(segment.toStation) (indices: \(fromIndex) → \(toIndex))")
                return isValid
            }
            
            print("🚦 Filtered segments result: \(filteredSegments.count) segments")
            
            // Filter train positions to only show the current train
            trainPositions = congestionData.trainPositions.filter { position in
                position.trainId == train.trainId
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
    
    private func getJourneyStationCodes() -> [String] {
        guard let stops = train.stops,
              let originCode = userOrigin,
              let destinationName = userDestination else {
            return []
        }
        
        // Find origin and destination indices
        let originIndex = stops.firstIndex { Stations.areEquivalentStations($0.stationCode, originCode) }
        let destinationIndex = stops.firstIndex { stop in
            if let destinationCode = Stations.getStationCode(destinationName) {
                return Stations.areEquivalentStations(stop.stationCode, destinationCode)
            }
            return stop.stationName.lowercased() == destinationName.lowercased()
        }
        
        guard let startIdx = originIndex, let endIdx = destinationIndex, startIdx <= endIdx else {
            return []
        }
        
        // Get all station codes in the journey (ordered)
        let journeyStops = stops[startIdx...endIdx]
        return journeyStops.compactMap { $0.stationCode }
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
            // Get coordinates directly from the Stations utility
            if let coordinate = Stations.getCoordinates(for: stop.stationCode) {
                let isDestination: Bool
                if let destinationCode = Stations.getStationCode(destinationName) {
                    isDestination = Stations.areEquivalentStations(stop.stationCode, destinationCode)
                } else {
                    isDestination = stop.stationName.lowercased() == destinationName.lowercased()
                }
                
                stations.append(JourneyStation(
                    code: stop.stationCode,
                    name: stop.stationName,
                    coordinate: coordinate,
                    isOrigin: Stations.areEquivalentStations(stop.stationCode, originCode),
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

// MARK: - MapKit-based Congestion Map View
struct CongestionMapKitView: UIViewRepresentable {
    @Binding var region: MKCoordinateRegion
    let segments: [CongestionSegment]
    let stations: [JourneyStation]
    let trainPositions: [TrainLocationData]
    let highlightMode: SegmentHighlightMode
    let onSegmentTap: (CongestionSegment) -> Void

    init(region: Binding<MKCoordinateRegion>,
         segments: [CongestionSegment],
         stations: [JourneyStation],
         trainPositions: [TrainLocationData] = [],
         highlightMode: SegmentHighlightMode = .delays,
         onSegmentTap: @escaping (CongestionSegment) -> Void) {
        self._region = region
        self.segments = segments
        self.stations = stations
        self.trainPositions = trainPositions
        self.highlightMode = highlightMode
        self.onSegmentTap = onSegmentTap
    }
    
    func makeUIView(context: Context) -> MKMapView {
        let mapView = MKMapView()
        mapView.delegate = context.coordinator
        mapView.showsUserLocation = true
        mapView.userTrackingMode = .none
        
        // Configure map appearance
        mapView.mapType = .standard
        mapView.showsCompass = false
        mapView.showsScale = false
        
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
        
        // Build desired overlay state (include congestionLevel to catch visual changes)
        let desiredOverlayState = Set(segments.map { OverlayIdentity(segmentID: $0.id, congestionLevel: $0.congestionLevel) })
        let highlightModeChanged = highlightMode != context.coordinator.highlightMode

        // If highlight mode changed, update existing overlay renderers
        if highlightModeChanged {
            context.coordinator.highlightMode = highlightMode
            for polyline in context.coordinator.polylines {
                if let renderer = mapView.renderer(for: polyline) as? MKPolylineRenderer,
                   let segment = polyline.segment {
                    renderer.strokeColor = context.coordinator.colorForSegment(segment)
                    renderer.lineWidth = context.coordinator.lineWidthForSegment(segment)
                    renderer.setNeedsDisplay()
                }
            }
        }

        // Early exit if nothing changed
        guard desiredOverlayState != context.coordinator.currentOverlayState else {
            return
        }

        // Diff overlays
        let toRemove = context.coordinator.currentOverlayState.subtracting(desiredOverlayState)
        let toAdd = desiredOverlayState.subtracting(context.coordinator.currentOverlayState)

        // Remove old overlays (batch operation)
        if !toRemove.isEmpty {
            let overlaysToRemove = toRemove.compactMap { context.coordinator.overlayMap[$0.segmentID] }
            if !overlaysToRemove.isEmpty {
                mapView.removeOverlays(overlaysToRemove)
            }
            toRemove.forEach { context.coordinator.overlayMap.removeValue(forKey: $0.segmentID) }
            context.coordinator.polylines.removeAll { polyline in
                toRemove.contains { $0.segmentID == polyline.segment?.id }
            }
        }

        // Add new overlays (batch operation)
        if !toAdd.isEmpty {
            let segmentsToAdd = segments.filter { toAdd.contains(OverlayIdentity(segmentID: $0.id, congestionLevel: $0.congestionLevel)) }
            let sortedSegments = segmentsToAdd.sorted { $0.congestionFactor < $1.congestionFactor }

            var newOverlays: [CongestionPolyline] = []
            for segment in sortedSegments {
                if let fromCoords = Stations.getCoordinates(for: segment.fromStation),
                   let toCoords = Stations.getCoordinates(for: segment.toStation) {
                    let coordinates = [fromCoords, toCoords]
                    let polyline = CongestionPolyline(coordinates: coordinates, count: coordinates.count)
                    polyline.segment = segment
                    newOverlays.append(polyline)
                    context.coordinator.overlayMap[segment.id] = polyline
                    context.coordinator.polylines.append(polyline)
                }
            }
            if !newOverlays.isEmpty {
                mapView.addOverlays(newOverlays)
            }
        }

        // Update state
        context.coordinator.currentOverlayState = desiredOverlayState

        // Always clear and re-add annotations (they're lightweight)
        mapView.removeAnnotations(mapView.annotations.filter { !($0 is MKUserLocation) })

        // Add station annotations
        for station in stations {
            let annotation = StationAnnotation()
            annotation.coordinate = station.coordinate
            annotation.title = station.name
            annotation.station = station
            mapView.addAnnotation(annotation)
        }

        // Add train annotations
        for trainPosition in trainPositions {
            var coordinate: CLLocationCoordinate2D?

            // For Amtrak trains that haven't departed yet - ALWAYS show at user's origin station
            if trainPosition.dataSource == "AMTRAK" && trainPosition.lastDepartedStation == nil {
                // Find the first station in the journey (user's origin)
                if let firstStation = stations.first(where: { $0.isOrigin }) {
                    coordinate = firstStation.coordinate
                }
            } else if let lat = trainPosition.lat, let lon = trainPosition.lon {
                // Use GPS coordinates if available
                coordinate = CLLocationCoordinate2D(latitude: lat, longitude: lon)
            } else if let atStation = trainPosition.atStation {
                // Train is at a station - show it at the station location
                coordinate = Stations.getCoordinates(for: atStation)
            }

            if let coord = coordinate {
                let annotation = TrainAnnotation(trainData: trainPosition, coordinate: coord)
                mapView.addAnnotation(annotation)
            }
        }
        
        // Update coordinator with current segments for tap handling
        context.coordinator.segments = segments
        context.coordinator.onSegmentTap = onSegmentTap
        context.coordinator.mapView = mapView
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
        var onSegmentTap: (CongestionSegment) -> Void = { _ in }
        var polylines: [CongestionPolyline] = []
        weak var mapView: MKMapView?
        var highlightMode: SegmentHighlightMode = .delays

        var currentOverlayState: Set<OverlayIdentity> = []
        var overlayMap: [String: CongestionPolyline] = [:]

        // MARK: - Public color/width helpers (used by updateUIView and rendererFor)
        func colorForSegment(_ segment: CongestionSegment) -> UIColor {
            guard highlightMode != .off else { return UIColor.clear }
            var color: UIColor
            switch segment.preferredHighlightMode {
            case .health:
                // Fall back to delay coloring when no frequency baseline exists yet
                if segment.frequencyFactor != nil {
                    color = getFrequencyUIColor(for: segment.frequencyFactor)
                } else {
                    color = getUIColor(for: segment.congestionFactor)
                }
            case .delays, .off: color = getUIColor(for: segment.congestionFactor)
            }
            // Escalate color for significant cancellation rates
            if segment.cancellationRate > 20 {
                color = UIColor.systemRed
            } else if segment.cancellationRate > 10 {
                color = escalateColor(color)
            }
            return color
        }

        func lineWidthForSegment(_ segment: CongestionSegment) -> CGFloat {
            guard highlightMode != .off else { return 0 }
            switch segment.preferredHighlightMode {
            case .health:
                // Fall back to delay-based width when no frequency baseline exists yet
                guard let factor = segment.frequencyFactor else {
                    return getCongestionLineWidth(segment.congestionFactor)
                }
                if factor >= 0.9 { return 5 }
                else if factor >= 0.7 { return 7 }
                else if factor >= 0.5 { return 8 }
                else { return 9 }
            case .delays, .off: return getCongestionLineWidth(segment.congestionFactor)
            }
        }

        // MARK: - Polyline Rendering
        func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
            if let polyline = overlay as? CongestionPolyline {
                let renderer = MKPolylineRenderer(polyline: polyline)
                if let segment = polyline.segment {
                    renderer.strokeColor = colorForSegment(segment)
                    renderer.lineWidth = lineWidthForSegment(segment)
                } else {
                    renderer.strokeColor = UIColor.gray
                    renderer.lineWidth = 5
                }
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
            
            // Handle train annotations
            if annotation is TrainAnnotation {
                let identifier = "TrainAnnotation"
                var annotationView = mapView.dequeueReusableAnnotationView(withIdentifier: identifier)
                
                if annotationView == nil {
                    annotationView = MKAnnotationView(annotation: annotation, reuseIdentifier: identifier)
                    annotationView?.canShowCallout = false // No callout for trains
                }
                
                // Create train icon view
                let iconView = UIView(frame: CGRect(x: 0, y: 0, width: 30, height: 30))
                iconView.backgroundColor = UIColor.orange
                iconView.layer.cornerRadius = 15
                
                // Add train symbol
                let imageView = UIImageView(frame: CGRect(x: 5, y: 5, width: 20, height: 20))
                imageView.image = UIImage(systemName: "train.side.front.car")
                imageView.tintColor = .white
                imageView.contentMode = .scaleAspectFit
                iconView.addSubview(imageView)
                
                annotationView?.image = iconView.asUIImage()
                annotationView?.annotation = annotation
                
                // Ensure train icons appear on top of other annotations
                annotationView?.layer.zPosition = 1000
                
                return annotationView
            }
            
            // Handle station annotations
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
            
            // Ensure station dots appear below train icons
            annotationView?.layer.zPosition = 0
            
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
            CongestionColors.color(forCongestionFactor: congestionFactor)
        }

        private func getFrequencyUIColor(for frequencyFactor: Double?) -> UIColor {
            CongestionColors.color(forFrequencyFactor: frequencyFactor)
        }

        private func getFrequencyLineWidth(_ frequencyFactor: Double?) -> CGFloat {
            guard let factor = frequencyFactor else { return 5 }
            if factor >= 0.9 { return 5 }
            else if factor >= 0.7 { return 7 }
            else if factor >= 0.5 { return 8 }
            else { return 9 }
        }

        /// Escalate a health color by one level toward red for cancellation impact
        private func escalateColor(_ color: UIColor) -> UIColor {
            if color == UIColor.systemGreen { return UIColor.systemYellow }
            if color == UIColor.systemYellow { return UIColor.systemOrange }
            return UIColor.systemRed
        }

        private func createStationPinView(for station: JourneyStation) -> UIView {
            let size: CGFloat = 12
            let containerView = UIView(frame: CGRect(x: 0, y: 0, width: size, height: size))
            
            // Create a simple circle dot
            let dotView = UIView(frame: CGRect(x: 0, y: 0, width: size, height: size))
            dotView.backgroundColor = UIColor.white
            dotView.layer.cornerRadius = size / 2
            dotView.layer.borderWidth = 2
            dotView.layer.borderColor = UIColor.black.cgColor
            
            // Special styling for origin and destination
            if station.isOrigin || station.isDestination {
                dotView.backgroundColor = UIColor.orange
                dotView.layer.borderColor = UIColor.white.cgColor
            }
            
            containerView.addSubview(dotView)
            
            return containerView
        }
        
        // MARK: - Tap Handling
        @objc func handleMapTap(_ gesture: UITapGestureRecognizer) {
            guard let mapView = mapView else { return }
            
            let tapPoint = gesture.location(in: mapView)
            let tapCoordinate = mapView.convert(tapPoint, toCoordinateFrom: mapView)
            
            // Check each polyline to see if tap is near it
            for polyline in polylines {
                if isCoordinate(tapCoordinate, nearPolyline: polyline, inMapView: mapView) {
                    if let segment = polyline.segment {
                        onSegmentTap(segment)
                        break
                    }
                }
            }
        }
        
        private func isCoordinate(_ coordinate: CLLocationCoordinate2D, nearPolyline polyline: MKPolyline, inMapView mapView: MKMapView) -> Bool {
            // Convert polyline points to screen points
            guard polyline.pointCount >= 2 else { return false }
            
            let points = polyline.points()
            let coord1 = points[0].coordinate
            let coord2 = points[1].coordinate
            
            let screenPoint1 = mapView.convert(coord1, toPointTo: mapView)
            let screenPoint2 = mapView.convert(coord2, toPointTo: mapView)
            let tapPoint = mapView.convert(coordinate, toPointTo: mapView)
            
            // Calculate distance from tap point to line segment
            let distance = distanceFromPoint(tapPoint, toLineSegmentBetween: screenPoint1, and: screenPoint2)
            
            // Consider tap "near" if within 30 points
            return distance <= 30
        }
        
        private func distanceFromPoint(_ point: CGPoint, toLineSegmentBetween p1: CGPoint, and p2: CGPoint) -> CGFloat {
            let dx = p2.x - p1.x
            let dy = p2.y - p1.y
            let lengthSquared = dx * dx + dy * dy
            
            if lengthSquared == 0 {
                // p1 and p2 are the same point
                return hypot(point.x - p1.x, point.y - p1.y)
            }
            
            // Calculate parameter t for closest point on line segment
            let t = max(0, min(1, ((point.x - p1.x) * dx + (point.y - p1.y) * dy) / lengthSquared))
            
            // Calculate closest point on line segment
            let closestPoint = CGPoint(x: p1.x + t * dx, y: p1.y + t * dy)
            
            // Return distance from tap point to closest point
            return hypot(point.x - closestPoint.x, point.y - closestPoint.y)
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

class TrainAnnotation: NSObject, MKAnnotation {
    @objc dynamic var coordinate: CLLocationCoordinate2D
    var title: String?
    var subtitle: String?
    var trainData: TrainLocationData
    
    init(trainData: TrainLocationData, coordinate: CLLocationCoordinate2D) {
        self.trainData = trainData
        self.coordinate = coordinate
        self.title = "Train \(trainData.trainId)"
        self.subtitle = trainData.line
        super.init()
    }
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

// MARK: - Embedded Congestion Map for Train Details

struct EmbeddedCongestionMapView: View {
    @EnvironmentObject private var appState: AppState
    let train: TrainV2
    let userOrigin: String?
    let userDestination: String?

    @StateObject private var viewModel: EmbeddedCongestionViewModel
    @State private var routeStatusContext: RouteStatusContext?

    init(train: TrainV2, userOrigin: String?, userDestination: String?) {
        self.train = train
        self.userOrigin = userOrigin
        self.userDestination = userDestination
        self._viewModel = StateObject(wrappedValue: EmbeddedCongestionViewModel(
            train: train,
            userOrigin: userOrigin,
            userDestination: userDestination
        ))
    }
    
    var body: some View {
        VStack(spacing: 8) {
            if viewModel.isLoading {
                // Loading state
                RoundedRectangle(cornerRadius: 12)
                    .fill(.ultraThinMaterial)
                    .frame(height: 150)
                    .overlay(
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .orange))
                    )
            } else if viewModel.journeySegments.isEmpty {
                // No data state
                RoundedRectangle(cornerRadius: 12)
                    .fill(.ultraThinMaterial)
                    .frame(height: 150)
                    .overlay(
                        VStack(spacing: 8) {
                            Image(systemName: "map.fill")
                                .font(.title2)
                                .foregroundColor(.gray)
                            Text("No congestion data")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    )
            } else {
                // Map showing all segments
                CongestionMapKitView(
                    region: $viewModel.mapRegion,
                    segments: viewModel.journeySegments,
                    stations: viewModel.journeyStations,
                    trainPositions: viewModel.trainPositions,
                    highlightMode: appState.mapHighlightMode,
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
                    }
                )
                .frame(height: 300)
                .cornerRadius(TrackRatTheme.CornerRadius.md)
                .overlay(
                    RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                        .stroke(TrackRatTheme.Colors.borderSecondary, lineWidth: 1)
                )
            }
        }
        .sheet(item: $routeStatusContext) { context in
            RouteStatusView(context: context)
        }
        .task {
            await viewModel.loadCongestionData()
        }
    }
}

// MARK: - Single Segment Map View

struct SingleSegmentMapView: View {
    let segment: CongestionSegment
    let journeyStations: [JourneyStation]
    let onTap: (CongestionSegment) -> Void
    
    @State private var mapRegion = MKCoordinateRegion()
    
    var body: some View {
        ZStack {
            // Single segment map
            CongestionMapKitView(
                region: $mapRegion,
                segments: [segment], // Only show this one segment
                stations: journeyStations,
                trainPositions: [], // No train positions for single segment view
                onSegmentTap: onTap
            )
            .cornerRadius(TrackRatTheme.CornerRadius.md)
            .overlay(
                RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                    .stroke(TrackRatTheme.Colors.borderSecondary, lineWidth: 1)
            )

            // Congestion level overlay
            VStack {
                HStack {
                    Spacer()
                    VStack(alignment: .trailing, spacing: 2) {
                        Text(segment.displayCongestionLevel)
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundColor(.white)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(
                                Capsule()
                                    .fill(segment.displayColor.opacity(0.8))
                            )
                    }
                    .padding(8)
                }
                Spacer()
            }
        }
        .onAppear {
            setMapRegionForSegment()
        }
        .onTapGesture {
            onTap(segment)
        }
    }
    
    private func setMapRegionForSegment() {
        guard let fromCoords = Stations.getCoordinates(for: segment.fromStation),
              let toCoords = Stations.getCoordinates(for: segment.toStation) else {
            return
        }
        
        let centerLat = (fromCoords.latitude + toCoords.latitude) / 2
        let centerLon = (fromCoords.longitude + toCoords.longitude) / 2
        
        let latDelta = abs(fromCoords.latitude - toCoords.latitude) * 2.5
        let lonDelta = abs(fromCoords.longitude - toCoords.longitude) * 2.5
        
        // Ensure minimum zoom level
        let minDelta: Double = 0.05
        
        mapRegion = MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: centerLat, longitude: centerLon),
            span: MKCoordinateSpan(
                latitudeDelta: max(latDelta, minDelta),
                longitudeDelta: max(lonDelta, minDelta)
            )
        )
    }
}

// MARK: - Compact Congestion Legend

struct CompactCongestionLegend: View {
    var highlightMode: SegmentHighlightMode = .delays

    var body: some View {
        HStack(spacing: 12) {
            if highlightMode == .health {
                LegendItem(color: .green, label: "Healthy")
                LegendItem(color: .yellow, label: "Moderate")
                LegendItem(color: .orange, label: "Reduced")
                LegendItem(color: .red, label: "Severe")
            } else {
                LegendItem(color: .green, label: "Normal")
                LegendItem(color: .yellow, label: "Moderate")
                LegendItem(color: .orange, label: "Heavy")
                LegendItem(color: .red, label: "Severe")
            }
        }
        .font(.caption2)
        .padding(.horizontal)
        .padding(.vertical, 6)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(.ultraThinMaterial)
        )
    }
}

// MARK: - Embedded Congestion View Model

@MainActor
class EmbeddedCongestionViewModel: ObservableObject {
    @Published var journeySegments: [CongestionSegment] = []
    @Published var journeyStations: [JourneyStation] = []
    @Published var trainPositions: [TrainLocationData] = []
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
            // Fetch congestion data using existing API
            let congestionData = try await APIService.shared.fetchCongestionData(timeWindowHours: 1)
            
            // Use train's actual data source for filtering
            let expectedDataSource = train.dataSource

            // Filter segments to user's journey path only
            // Expand skip-stop gaps using route topology so intermediate canonical segments match
            let rawStationCodes = getJourneyStationCodes()
            let journeyStationCodes = RouteTopology.expandStationCodes(rawStationCodes, dataSource: expectedDataSource)

            let filteredSegments = congestionData.aggregatedSegments.filter { segment in
                // Check if data source matches train's system
                guard segment.dataSource == expectedDataSource else {
                    return false
                }
                
                // Find indices of from and to stations in the journey
                guard let fromIndex = journeyStationCodes.firstIndex(of: segment.fromStation),
                      let toIndex = journeyStationCodes.firstIndex(of: segment.toStation) else {
                    return false
                }
                
                // Include only consecutive segments (exact journey path)
                return toIndex == fromIndex + 1
            }
            
            // Sort segments by their order in the journey
            journeySegments = filteredSegments.sorted { segment1, segment2 in
                let index1 = journeyStationCodes.firstIndex(of: segment1.fromStation) ?? 0
                let index2 = journeyStationCodes.firstIndex(of: segment2.fromStation) ?? 0
                return index1 < index2
            }
            
            // Filter train positions to only show the current train
            trainPositions = congestionData.trainPositions.filter { position in
                position.trainId == train.trainId
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
    
    private func getJourneyStationCodes() -> [String] {
        guard let stops = train.stops,
              let originCode = userOrigin,
              let destinationName = userDestination else {
            return []
        }
        
        // Find origin and destination indices
        let originIndex = stops.firstIndex { Stations.areEquivalentStations($0.stationCode, originCode) }
        let destinationIndex = stops.firstIndex { stop in
            if let destinationCode = Stations.getStationCode(destinationName) {
                return Stations.areEquivalentStations(stop.stationCode, destinationCode)
            }
            return stop.stationName.lowercased() == destinationName.lowercased()
        }
        
        guard let startIdx = originIndex, let endIdx = destinationIndex, startIdx <= endIdx else {
            return []
        }
        
        // Get all station codes in the journey (ordered)
        let journeyStops = stops[startIdx...endIdx]
        return journeyStops.compactMap { $0.stationCode }
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
            // Get coordinates directly from the Stations utility
            if let coordinate = Stations.getCoordinates(for: stop.stationCode) {
                let isDestination: Bool
                if let destinationCode = Stations.getStationCode(destinationName) {
                    isDestination = Stations.areEquivalentStations(stop.stationCode, destinationCode)
                } else {
                    isDestination = stop.stationName.lowercased() == destinationName.lowercased()
                }
                
                stations.append(JourneyStation(
                    code: stop.stationCode,
                    name: stop.stationName,
                    coordinate: coordinate,
                    isOrigin: Stations.areEquivalentStations(stop.stationCode, originCode),
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

#Preview {
    JourneyCongestionMapView(
        train: TrainV2(
            trainId: "2307",
            journeyDate: Date(),
            line: LineInfo(code: "NEC", name: "Northeast Corridor", color: "#0066CC"),
            destination: "New York Penn Station",
            departure: StationTiming(code: "TR", name: "Trenton", scheduledTime: Date(), updatedTime: nil, actualTime: nil, track: nil),
            arrival: nil,
            trainPosition: nil,
            dataFreshness: nil,
            observationType: nil,
            isCancelled: false,
            cancellationReason: nil,
            isCompleted: false,
            dataSource: "NJT",
            stops: []
        ),
        userOrigin: "TR",
        userDestination: "New York Penn Station"
    )
    .padding()
    .background(.ultraThinMaterial)
}