import SwiftUI
import MapKit

struct MapContainerView: View {
    @EnvironmentObject private var appState: AppState
    @State private var bottomSheetPosition: BottomSheetPosition = .compact
    @StateObject private var mapViewModel = CongestionMapViewModel()
    @State private var selectedSegment: CongestionSegment?
    
    // Map region state - DC to Boston corridor view
    @State private var mapRegion = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 40.6, longitude: -74.5), // Center between DC and Boston
        span: MKCoordinateSpan(latitudeDelta: 4.5, longitudeDelta: 3.0)   // Wide enough to show DC to Boston
    )
    
    var body: some View {
        ZStack {
            // Always show the map, just without congestion data when loading
            SystemCongestionMapView(
                region: $mapRegion,
                segments: mapViewModel.segments,
                individualSegments: mapViewModel.individualSegments,
                stations: mapViewModel.stations,
                selectedRoute: appState.selectedRoute,
                onSegmentTap: { segment in
                    selectedSegment = segment
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                },
                onIndividualSegmentTap: { individualSegment in
                    print("Tapped individual segment: \(individualSegment.trainDisplayName)")
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                }
            )
            .ignoresSafeArea()
            
            // Optional: Show subtle loading indicator when data is loading
            if mapViewModel.isLoading && mapViewModel.segments.isEmpty {
                VStack {
                    Spacer()
                    HStack {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .orange))
                            .scaleEffect(0.8)
                        
                        Text("Loading traffic data...")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .padding()
                    .background(
                        RoundedRectangle(cornerRadius: 8)
                            .fill(.ultraThinMaterial)
                    )
                    .padding(.bottom, 120) // Above bottom sheet
                }
            }
            
            // Gradient overlay at top for better readability
            VStack {
                LinearGradient(
                    colors: [.black.opacity(0.6), .clear],
                    startPoint: .top,
                    endPoint: .bottom
                )
                .frame(height: 100)
                .ignoresSafeArea()
                
                Spacer()
            }
            
            
            // Bottom sheet with navigation content
            BottomSheetView(position: $bottomSheetPosition) {
                NavigationStack(path: $appState.navigationPath) {
                    TripSelectionView(onBottomSheetPositionChange: { newPosition in
                        bottomSheetPosition = newPosition
                    })
                        .navigationDestination(for: NavigationDestination.self) { destination in
                            bottomSheetNavigationContent(for: destination)
                        }
                }
            }
        }
        .preferredColorScheme(.dark)
        .task {
            // Load congestion data when map container appears
            // This restores data loading that was removed from ViewModel init for performance
            await mapViewModel.fetchCongestionData()
        }
        .onAppear {
            // Ensure we start with overall congestion view
            appState.mapDisplayMode = .overallCongestion
            appState.selectedRoute = nil
        }
        .onChange(of: appState.selectedRoute) { _, newRoute in
            // Animate map to show selected route when it changes
            if let route = newRoute {
                // Use current bottom sheet position since we're not changing it here
                animateMapToRoute(route, targetSheetPosition: bottomSheetPosition)
            }
        }
        .onChange(of: appState.departureStationCode) { _, newDepartureCode in
            // Animate map to show departure station when it changes (origin selection)
            if let departureCode = newDepartureCode, appState.selectedRoute == nil {
                // Only animate to single station if no full route is selected yet
                // Use current bottom sheet position since we're not changing it here
                animateMapToStation(departureCode, targetSheetPosition: bottomSheetPosition)
            }
        }
        .onChange(of: appState.navigationPath) { _, newPath in
            // Handle navigation-based map mode switching
            handleNavigationChange(newPath)
        }
        .onChange(of: appState.mapDisplayMode) { _, newMode in
            // Update map when display mode changes
            print("🗺️ Map display mode changed to: \(newMode)")
            // Note: MapDisplayMode handles overall map focus, not congestion visualization
            // Individual vs aggregated congestion is handled by CongestionMapView directly
        }
        .sheet(item: $selectedSegment) { segment in
            SegmentTrainDetailsView(segment: segment)
                .presentationDetents([.height(600), .large])
                .presentationDragIndicator(.visible)
        }
    }
    
    private func handleNavigationChange(_ navigationPath: NavigationPath) {
        if navigationPath.isEmpty {
            // Back to home - switch to overall mode and reset bottom sheet
            appState.mapDisplayMode = .overallCongestion
            // Clear any route selection to show all congestion data
            appState.selectedRoute = nil
            // Clear route filter from map view model
            mapViewModel.setRouteFilter(nil)
            bottomSheetPosition = .compact
        } else {
            // Check if we're navigating to train details
            if isNavigatingToTrainDetails(navigationPath) {
                // Animate map FIRST using target position to avoid race condition
                if let route = appState.selectedRoute {
                    animateMapToRoute(route, targetSheetPosition: .expanded)
                }
                
                // Then snap bottom sheet to full screen (100%) when navigating to train details
                withAnimation(.easeInOut(duration: 0.3)) {
                    bottomSheetPosition = .expanded
                }
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            }
            
            // Handle train details for map mode switching
            if isOnTrainDetails(navigationPath) {
                switchToJourneyFocus()
            }
        }
    }
    
    private func isNavigatingToTrainDetails(_ navigationPath: NavigationPath) -> Bool {
        // Check if we just navigated to train details by looking at current train context
        // This will be true when a train is selected and we have navigation context
        // Also check if we have the required route information for proper train details display
        return appState.currentTrainId != nil && 
               !navigationPath.isEmpty && 
               appState.departureStationCode != nil && 
               appState.selectedDestination != nil
    }
    
    private func isOnTrainDetails(_ navigationPath: NavigationPath) -> Bool {
        // Check if the navigation path contains train details destinations
        // We can't directly access NavigationPath contents, so we'll use the selected route
        // and current train info to infer if we're on train details
        return appState.currentTrainId != nil && appState.selectedRoute != nil
    }
    
    private func switchToJourneyFocus() {
        guard let route = appState.selectedRoute,
              let trainId = appState.currentTrainId else {
            print("🗺️ Cannot switch to journey focus - missing route or train info")
            return
        }
        
        print("🗺️ Fetching full train details for journey focus...")
        
        // Fetch full train details like TrainDetailsView does
        Task {
            do {
                // Extract just the train number from the full train ID
                // trainId might be "7833-NY-1754230560.0" but API wants just "7833"
                let trainNumber = extractTrainNumber(from: trainId)
                print("🗺️ DEBUG: Full trainId: \(trainId)")
                print("🗺️ DEBUG: Extracted trainNumber: \(trainNumber)")
                
                let fullTrain = try await APIService.shared.fetchTrainDetailsFlexible(
                    id: nil,
                    trainId: trainNumber,
                    fromStationCode: route.departureCode
                )
                
                print("🗺️ DEBUG: Full train data loaded:")
                print("🗺️ DEBUG: Train ID: \(fullTrain.trainId)")
                print("🗺️ DEBUG: Train has stops: \(fullTrain.stops != nil)")
                print("🗺️ DEBUG: Number of stops: \(fullTrain.stops?.count ?? 0)")
                print("🗺️ DEBUG: Route: \(route.departureCode) → \(route.destinationCode)")
                
                // Get actual train stops between origin and destination
                let trainStops = getActualTrainStops(train: fullTrain, from: route.departureCode, to: route.destinationCode)
                
                print("🗺️ Switching to journey focus mode: \(route.departureCode) → \(route.destinationCode)")
                print("🗺️ Actual train stops: \(trainStops)")
                
                // Only switch to journey focus if we have actual train stops data
                if !trainStops.isEmpty {
                    await MainActor.run {
                        appState.mapDisplayMode = .journeyFocus(
                            trainId: trainId,
                            origin: route.departureCode,
                            destination: route.destinationCode,
                            trainStops: trainStops
                        )
                        
                        // Apply route filter to the map view model
                        mapViewModel.setRouteFilter(route, journeyStations: trainStops)
                    }
                } else {
                    print("🗺️ No valid train stops - staying in overall congestion mode")
                }
                
            } catch {
                print("🗺️ Failed to fetch full train details: \(error)")
                print("🗺️ Staying in overall congestion mode")
            }
        }
        
        // Animate map to focus on the journey area immediately using expanded position
        animateMapToRoute(route, targetSheetPosition: .expanded)
    }
    
    private func extractTrainNumber(from fullTrainId: String) -> String {
        // Extract train number from IDs like "7833-NY-1754230560.0" -> "7833"
        if let firstDash = fullTrainId.firstIndex(of: "-") {
            return String(fullTrainId[..<firstDash])
        }
        // If no dash found, return the whole string
        return fullTrainId
    }
    
    private func getActualTrainStops(train: TrainV2, from origin: String, to destination: String) -> [String] {
        guard let stops = train.stops, !stops.isEmpty else {
            print("🗺️ No stops available for train - cannot show route")
            return []
        }
        
        print("🗺️ All train stops: \(stops.map { "\($0.stationCode)(\($0.stationName))" })")
        
        // Find indices of origin and destination in train stops
        let originIndex = stops.firstIndex { stop in
            stop.stationCode.uppercased() == origin.uppercased()
        }
        
        // For destination, try direct station code match first, then name matching
        let destinationIndex = stops.firstIndex { stop in
            // Try direct station code match first (destination is likely already a code)
            if stop.stationCode.uppercased() == destination.uppercased() {
                return true
            }
            // Try station name to code lookup as fallback
            if let destCode = Stations.getStationCode(destination) {
                return stop.stationCode.uppercased() == destCode.uppercased()
            }
            // Final fallback to name matching
            return stop.stationName.lowercased().contains(destination.lowercased())
        }
        
        print("🗺️ Origin '\(origin)' found at index: \(originIndex?.description ?? "nil")")
        print("🗺️ Destination '\(destination)' found at index: \(destinationIndex?.description ?? "nil")")
        
        guard let startIdx = originIndex, let endIdx = destinationIndex else {
            print("🗺️ Could not find origin/destination in train stops - cannot show route")
            print("🗺️ Available station codes: \(stops.map { $0.stationCode })")
            return []
        }
        
        // Get all station codes between origin and destination (inclusive)
        let journeyStops = stops[min(startIdx, endIdx)...max(startIdx, endIdx)]
        let stationCodes = journeyStops.map { $0.stationCode }
        
        print("🗺️ Extracted journey stops: \(stationCodes)")
        print("🗺️ Journey stop details: \(journeyStops.map { "\($0.stationCode)(\($0.stationName))" })")
        return stationCodes
    }
    
    private func animateMapToRoute(_ route: TripPair, targetSheetPosition: BottomSheetPosition? = nil) {
        // Get coordinates for departure and destination
        guard let fromCoords = Stations.getCoordinates(for: route.departureCode),
              let toCoords = Stations.getCoordinates(for: route.destinationCode) else {
            return
        }
        
        // Calculate center and span to show both stations
        let centerLat = (fromCoords.latitude + toCoords.latitude) / 2
        let centerLon = (fromCoords.longitude + toCoords.longitude) / 2
        
        let latDelta = abs(fromCoords.latitude - toCoords.latitude) * 2.0
        let lonDelta = abs(fromCoords.longitude - toCoords.longitude) * 2.0
        
        // Ensure minimum zoom level
        let minDelta: Double = 0.3
        let finalSpan = MKCoordinateSpan(
            latitudeDelta: max(latDelta, minDelta),
            longitudeDelta: max(lonDelta, minDelta)
        )
        
        // Calculate zoom-aware offset based on target sheet position and actual zoom level
        let sheetPosition = targetSheetPosition ?? bottomSheetPosition
        let offset = calculateZoomAwareOffset(for: sheetPosition, span: finalSpan)
        
        // Adjust center to account for bottom sheet coverage
        let adjustedCenter = CLLocationCoordinate2D(
            latitude: centerLat + offset,
            longitude: centerLon
        )
        
        withAnimation(.easeInOut(duration: 0.5)) {
            mapRegion = MKCoordinateRegion(
                center: adjustedCenter,
                span: finalSpan
            )
        }
    }
    
    private func calculateVisibleAreaOffset(for position: BottomSheetPosition) -> Double {
        // Calculate latitude offset to center content in the actual visible map area
        // Negative offsets move map center south (down), positioning stations in visible area above bottom sheet
        // Values tuned for northeast corridor geography (roughly 25 miles per 0.1°)
        switch position {
        case .compact:      // 75% visible area, center should be at 37.5% from top
            return -0.08    // Small adjustment south (~5 miles)
        case .medium:       // 50% visible area, center should be at 25% from top
            return -0.10    // Small-medium adjustment south (~7 miles)
        case .seventyFive:  // 25% visible area, center should be at 12.5% from top
            return -0.22    // Moderate adjustment south (~15 miles)
        case .large:        // 10% visible area, center should be at 5% from top
            return -0.30    // Larger adjustment south (~20 miles)
        case .expanded:     // 0% visible area - position in off-screen area
            return -0.38    // Significant adjustment south (~25 miles) to keep stations at very top
        }
    }
    
    private func calculateZoomAwareOffset(for position: BottomSheetPosition, span: MKCoordinateSpan) -> Double {
        let baseOffset = calculateVisibleAreaOffset(for: position)
        let avgSpan = (span.latitudeDelta + span.longitudeDelta) / 2
        let scaleFactor = max(1.0, avgSpan / 0.3) // Scale based on span vs minimum zoom
        let cappedScale = min(scaleFactor, 3.0) // Cap at 3x to prevent extreme offsets
        return baseOffset * cappedScale
    }
    
    private func animateMapToStation(_ stationCode: String, targetSheetPosition: BottomSheetPosition? = nil) {
        // Get coordinates for the station
        guard let coords = Stations.getCoordinates(for: stationCode) else {
            return
        }
        
        // Calculate offset based on target sheet position (or current if not provided)
        let sheetPosition = targetSheetPosition ?? bottomSheetPosition
        let offset = calculateVisibleAreaOffset(for: sheetPosition)
        
        // Adjust center to account for bottom sheet coverage
        let adjustedCenter = CLLocationCoordinate2D(
            latitude: coords.latitude + offset,
            longitude: coords.longitude
        )
        
        // Set zoom level for single station view
        let zoomDelta: Double = 0.2
        
        withAnimation(.easeInOut(duration: 0.5)) {
            mapRegion = MKCoordinateRegion(
                center: adjustedCenter,
                span: MKCoordinateSpan(
                    latitudeDelta: zoomDelta,
                    longitudeDelta: zoomDelta
                )
            )
        }
    }
    
    @ViewBuilder
    private func bottomSheetNavigationContent(for destination: NavigationDestination) -> some View {
        switch destination {
        case .departureSelector:
            DeparturePickerView()
        case .destinationPicker:
            DestinationPickerView()
        case .trainList(let stationName):
            TrainListView(destination: stationName)
        case .trainDetails(let trainId):
            TrainDetailsView(trainId: trainId)
        case .trainDetailsFlexible(let trainNumber, let fromStation):
            TrainDetailsView(trainNumber: trainNumber, fromStation: fromStation)
        case .trainNumberSearch:
            TrainNumberSearchView()
        case .advancedConfiguration:
            AdvancedConfigurationView()
        case .myProfile:
            MyProfileView()
        case .congestionMap:
            // Since map is always visible, show map controls and expand bottom sheet
            CongestionMapControlsView(
                mapViewModel: mapViewModel,
                onDismiss: {
                    // Reset to default map view and collapse bottom sheet
                    bottomSheetPosition = .medium
                }
            )
        }
    }
}

// MARK: - Map Controls View
// This view appears when user taps "View Live Traffic" from the menu
struct CongestionMapControlsView: View {
    @ObservedObject var mapViewModel: CongestionMapViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var showingFilters = false
    @State private var timeWindow = 3
    @State private var selectedDataSource = "All"
    let onDismiss: (() -> Void)?
    
    init(mapViewModel: CongestionMapViewModel, onDismiss: (() -> Void)? = nil) {
        self.mapViewModel = mapViewModel
        self.onDismiss = onDismiss
    }
    
    var body: some View {
        VStack(spacing: 20) {
            // Header
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Train Traffic")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                    
                    if mapViewModel.isLoading {
                        Text("Loading...")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    } else {
                        Text("\(mapViewModel.segments.count) segments")
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
            .padding(.horizontal)
            
            Spacer()
            
            // Close button
            Button {
                onDismiss?()
                dismiss()
            } label: {
                Text("Close")
                    .font(.headline)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(Color.orange)
                    )
            }
            .padding(.horizontal)
            .padding(.bottom)
        }
        .sheet(isPresented: $showingFilters) {
            FilterSheet(
                timeWindow: $timeWindow,
                selectedDataSource: $selectedDataSource,
                onApply: {
                    Task {
                        await mapViewModel.fetchCongestionData(
                            timeWindowHours: timeWindow,
                            dataSource: selectedDataSource == "All" ? nil : selectedDataSource
                        )
                    }
                }
            )
        }
    }
}


#Preview {
    MapContainerView()
        .environmentObject(AppState())
}