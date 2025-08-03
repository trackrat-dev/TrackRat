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
            // Background map - always visible
            SystemCongestionMapView(
                region: $mapRegion,
                segments: mapViewModel.segments,
                stations: mapViewModel.stations,
                selectedRoute: appState.selectedRoute,
                onSegmentTap: { segment in
                    selectedSegment = segment
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                }
            )
            .id("congestion-map-\(mapViewModel.segments.count)")
            .ignoresSafeArea()
            .onAppear {
                // Load congestion data when view appears
                print("🗺️ MapContainerView appeared - loading congestion data...")
                Task {
                    await mapViewModel.fetchCongestionData()
                    print("🗺️ Congestion data loaded: \(mapViewModel.segments.count) segments")
                }
            }
            .task {
                // Also load immediately when view is created
                print("🗺️ MapContainerView task - loading congestion data...")
                await mapViewModel.fetchCongestionData()
                print("🗺️ Task congestion data loaded: \(mapViewModel.segments.count) segments")
            }
            .onChange(of: appState.selectedRoute) { _, newRoute in
                // Animate map to show selected route when it changes
                if let route = newRoute {
                    animateMapToRoute(route)
                }
            }
            .onChange(of: appState.departureStationCode) { _, newDepartureCode in
                // Animate map to show departure station when it changes (origin selection)
                if let departureCode = newDepartureCode, appState.selectedRoute == nil {
                    // Only animate to single station if no full route is selected yet
                    animateMapToStation(departureCode)
                }
            }
            .onChange(of: appState.navigationPath) { _, newPath in
                // Handle navigation-based map mode switching
                handleNavigationChange(newPath)
            }
            .onChange(of: appState.mapDisplayMode) { _, newMode in
                // Update map when display mode changes
                print("🗺️ Map display mode changed to: \(newMode)")
                Task {
                    await mapViewModel.updateDisplayMode(newMode)
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
        .onAppear {
            // Ensure we start with overall congestion view
            appState.mapDisplayMode = .overallCongestion
            appState.selectedRoute = nil
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
            bottomSheetPosition = .compact
        }
        // Don't automatically expand bottom sheet for any navigation
        // Let users manually control the bottom sheet position
        // Only handle train details for map mode switching
        if isOnTrainDetails(navigationPath) {
            switchToJourneyFocus()
        }
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
                    }
                } else {
                    print("🗺️ No valid train stops - staying in overall congestion mode")
                }
                
            } catch {
                print("🗺️ Failed to fetch full train details: \(error)")
                print("🗺️ Staying in overall congestion mode")
            }
        }
        
        // Animate map to focus on the journey area immediately
        animateMapToRoute(route)
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
    
    private func animateMapToRoute(_ route: TripPair) {
        // Get coordinates for departure and destination
        guard let fromCoords = Stations.getCoordinates(for: route.departureCode),
              let toCoords = Stations.getCoordinates(for: route.destinationCode) else {
            return
        }
        
        // Calculate center and span to show both stations
        let centerLat = (fromCoords.latitude + toCoords.latitude) / 2
        let centerLon = (fromCoords.longitude + toCoords.longitude) / 2
        
        // Calculate offset based on current bottom sheet position
        let offset = calculateVisibleAreaOffset(for: bottomSheetPosition)
        
        // Adjust center to account for bottom sheet coverage
        let adjustedCenter = CLLocationCoordinate2D(
            latitude: centerLat + offset,
            longitude: centerLon
        )
        
        let latDelta = abs(fromCoords.latitude - toCoords.latitude) * 2.0
        let lonDelta = abs(fromCoords.longitude - toCoords.longitude) * 2.0
        
        // Ensure minimum zoom level
        let minDelta: Double = 0.3
        
        withAnimation(.easeInOut(duration: 0.5)) {
            mapRegion = MKCoordinateRegion(
                center: adjustedCenter,
                span: MKCoordinateSpan(
                    latitudeDelta: max(latDelta, minDelta),
                    longitudeDelta: max(lonDelta, minDelta)
                )
            )
        }
    }
    
    private func calculateVisibleAreaOffset(for position: BottomSheetPosition) -> Double {
        // Calculate latitude offset to center content in visible map area
        // Offset values in degrees (approximate, works well for northeast corridor)
        switch position {
        case .compact:      // 25% coverage
            return 0.05     // Small upward offset
        case .medium:       // 50% coverage  
            return 0.10     // Medium upward offset
        case .large:        // 90% coverage
            return 0.20     // Large upward offset
        case .expanded:     // 100% coverage
            return 0.25     // Maximum upward offset
        }
    }
    
    private func animateMapToStation(_ stationCode: String) {
        // Get coordinates for the station
        guard let coords = Stations.getCoordinates(for: stationCode) else {
            return
        }
        
        // Calculate offset based on current bottom sheet position
        let offset = calculateVisibleAreaOffset(for: bottomSheetPosition)
        
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