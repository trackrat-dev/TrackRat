import SwiftUI
import MapKit

struct MapContainerView: View {
    @EnvironmentObject private var appState: AppState
    @State private var bottomSheetPosition: BottomSheetPosition = .medium
    @StateObject private var mapViewModel = CongestionMapViewModel()
    @State private var selectedSegment: CongestionSegment?
    @ObservedObject private var liveActivityService = LiveActivityService.shared
    
    // Default DC-Boston wide view - used consistently for initial and reset scenarios
    private static let defaultMapRegion = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 39.55, longitude: -74.5), // Base center shifted south ~75 miles
        span: MKCoordinateSpan(latitudeDelta: 4.5, longitudeDelta: 3.0)   // Wide enough to show DC to Boston
    )
    
    // Smart default that tries to focus on user's home/work stations, falls back to defaultMapRegion
    private var smartDefaultRegion: MKCoordinateRegion {
        print("🗺️ SmartDefault: Starting smart default region calculation")
        
        // Try to get home and work station codes
        let homeCode = RatSenseService.shared.getHomeStation()
        let workCode = RatSenseService.shared.getWorkStation()
        
        print("🗺️ SmartDefault: Retrieved station codes - Home: \(homeCode ?? "nil"), Work: \(workCode ?? "nil")")
        
        // Try to get coordinates for the stations
        let homeCoord = homeCode.flatMap { code in
            let coord = Stations.getCoordinates(for: code)
            print("🗺️ SmartDefault: Home station '\(code)' coordinates: \(coord?.latitude ?? 0.0), \(coord?.longitude ?? 0.0)")
            return coord
        }
        
        let workCoord = workCode.flatMap { code in
            let coord = Stations.getCoordinates(for: code)
            print("🗺️ SmartDefault: Work station '\(code)' coordinates: \(coord?.latitude ?? 0.0), \(coord?.longitude ?? 0.0)")
            return coord
        }
        
        print("🗺️ SmartDefault: Coordinate resolution - Home: \(homeCoord != nil), Work: \(workCoord != nil)")
        
        // Calculate optimal region based on available stations
        if let home = homeCoord, let work = workCoord {
            print("🗺️ SmartDefault: ✅ Both stations available - calculating two-point region")
            let region = calculateRegionForTwoPoints(home, work)
            print("🗺️ SmartDefault: Two-point region center: \(region.center.latitude), \(region.center.longitude), span: \(region.span.latitudeDelta)°")
            return region
        } else if let singleCoord = homeCoord ?? workCoord {
            let stationType = homeCoord != nil ? "home" : "work"
            print("🗺️ SmartDefault: ✅ Single station available (\(stationType)) - calculating single-point region")
            let region = calculateRegionForSinglePoint(singleCoord)
            print("🗺️ SmartDefault: Single-point region center: \(region.center.latitude), \(region.center.longitude), span: \(region.span.latitudeDelta)°")
            return region
        } else {
            print("🗺️ SmartDefault: ❌ No stations available - using default region")
            print("🗺️ SmartDefault: Default region center: \(Self.defaultMapRegion.center.latitude), \(Self.defaultMapRegion.center.longitude), span: \(Self.defaultMapRegion.span.latitudeDelta)°")
            return Self.defaultMapRegion
        }
    }
    
    // Calculate region that encompasses both home and work stations with appropriate padding
    private func calculateRegionForTwoPoints(_ point1: CLLocationCoordinate2D, _ point2: CLLocationCoordinate2D) -> MKCoordinateRegion {
        print("🗺️ TwoPoints: Calculating region for two points")
        print("🗺️ TwoPoints: Point1: \(point1.latitude), \(point1.longitude)")
        print("🗺️ TwoPoints: Point2: \(point2.latitude), \(point2.longitude)")
        
        // Handle case where both points are the same (home == work)
        if abs(point1.latitude - point2.latitude) < 0.001 && abs(point1.longitude - point2.longitude) < 0.001 {
            print("🗺️ TwoPoints: Points are identical - using single point calculation")
            return calculateRegionForSinglePoint(point1)
        }
        
        // Calculate bounding box for both points
        let minLat = min(point1.latitude, point2.latitude)
        let maxLat = max(point1.latitude, point2.latitude)
        let minLng = min(point1.longitude, point2.longitude)
        let maxLng = max(point1.longitude, point2.longitude)
        
        print("🗺️ TwoPoints: Bounding box - Lat: \(minLat) to \(maxLat), Lng: \(minLng) to \(maxLng)")
        
        // Calculate center point
        let centerLat = (minLat + maxLat) / 2
        let centerLng = (minLng + maxLng) / 2
        
        // Calculate spans with reasonable padding (50% extra space around points)
        let latSpan = max((maxLat - minLat) * 1.5, 0.1) // Minimum span of 0.1 degrees
        let lngSpan = max((maxLng - minLng) * 1.5, 0.1)
        
        print("🗺️ TwoPoints: Final region - Center: \(centerLat), \(centerLng), Span: \(latSpan)° x \(lngSpan)°")
        
        return MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: centerLat, longitude: centerLng),
            span: MKCoordinateSpan(latitudeDelta: latSpan, longitudeDelta: lngSpan)
        )
    }
    
    // Calculate region centered on a single station with comfortable zoom level
    private func calculateRegionForSinglePoint(_ point: CLLocationCoordinate2D) -> MKCoordinateRegion {
        print("🗺️ SinglePoint: Calculating region for single point: \(point.latitude), \(point.longitude)")
        let region = MKCoordinateRegion(
            center: point,
            span: MKCoordinateSpan(latitudeDelta: 0.5, longitudeDelta: 0.5) // Moderate zoom level
        )
        print("🗺️ SinglePoint: Final region - Center: \(region.center.latitude), \(region.center.longitude), Span: \(region.span.latitudeDelta)°")
        return region
    }
    
    // Map region state - will be set dynamically based on bottom sheet position
    @State private var mapRegion = MapContainerView.defaultMapRegion
    @State private var hasInitializedMapRegion = false
    
    var body: some View {
        ZStack {
            // Always show the map, just without congestion data when loading
            SystemCongestionMapView(
                region: $mapRegion,
                segments: mapViewModel.segments,
                individualSegments: mapViewModel.individualSegments,
                stations: mapViewModel.stations,
                selectedRoute: appState.activeTrainRoute ?? appState.selectedRoute,  // Show route for Live Activity or selected route
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
            
            
            // Bottom sheet with navigation content (marked as scrollable)
            BottomSheetView(position: $bottomSheetPosition, isScrollable: true) {
                NavigationStack(path: $appState.navigationPath) {
                    TripSelectionView(
                        sheetPosition: $bottomSheetPosition,
                        onBottomSheetPositionChange: { newPosition in
                            bottomSheetPosition = newPosition
                        }
                    )
                        .navigationDestination(for: NavigationDestination.self) { destination in
                            bottomSheetNavigationContent(for: destination)
                        }
                }
            }
        }
        .preferredColorScheme(.dark)
        .task {
            // Load congestion data when map container appears, but don't block UI
            // Use detached task to prevent UI lag during origin station selection
            Task.detached(priority: .utility) { [weak mapViewModel] in
                await mapViewModel?.fetchCongestionDataIfNeeded()
            }
        }
        .onChange(of: appState.deepLinkTrainNumber) { _, trainNumber in
            // Handle deep link navigation when train number is set
            guard let trainNumber = trainNumber else { return }
            
            print("🔗 Deep link detected - navigating to train \(trainNumber)")
            
            Task {
                // Small delay to ensure NavigationStack is ready
                try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds
                
                await MainActor.run {
                    // Navigate directly to train details
                    print("🔗 Setting up navigation path...")
                    appState.navigationPath = NavigationPath()
                    appState.navigationPath.append(NavigationDestination.trainDetailsFlexible(
                        trainNumber: trainNumber,
                        fromStation: appState.deepLinkFromStation
                    ))
                    print("🔗 Navigation path set with \(appState.navigationPath.count) destinations")
                    
                    // Expand bottom sheet to full screen immediately
                    bottomSheetPosition = .expanded
                    print("🔗 Bottom sheet expanded")
                    
                    // Animate map to route if available
                    if let route = appState.selectedRoute {
                        animateMapToRoute(route, targetSheetPosition: .expanded)
                        print("🔗 Map animated to route")
                    }
                }
                
                // Clear deep link state after a short delay to ensure navigation completes
                try? await Task.sleep(nanoseconds: 500_000_000) // 0.5 seconds
                await MainActor.run {
                    appState.clearDeepLinkState()
                    print("🔗 Deep link state cleared")
                }
                
                print("✅ Deep link navigation completed")
            }
        }
        .onAppear {
            print("🗺️ MapContainer: onAppear called")
            print("🗺️ MapContainer: hasInitializedMapRegion = \(hasInitializedMapRegion)")
            print("🗺️ MapContainer: bottomSheetPosition = \(bottomSheetPosition)")
            
            // Initialize map region with smart default (home/work focused) on first appearance
            if !hasInitializedMapRegion {
                print("🗺️ MapContainer: First appearance - initializing map region")
                
                let smartRegion = smartDefaultRegion
                print("🗺️ MapContainer: Smart region calculated - Center: \(smartRegion.center.latitude), \(smartRegion.center.longitude), Span: \(smartRegion.span.latitudeDelta)°")
                
                let offset = calculateVisibleAreaOffset(for: bottomSheetPosition)
                print("🗺️ MapContainer: Calculated offset for \(bottomSheetPosition): \(offset)")
                
                let finalRegion = MKCoordinateRegion(
                    center: CLLocationCoordinate2D(
                        latitude: smartRegion.center.latitude + offset,
                        longitude: smartRegion.center.longitude
                    ),
                    span: smartRegion.span
                )
                
                print("🗺️ MapContainer: Final region with offset - Center: \(finalRegion.center.latitude), \(finalRegion.center.longitude), Span: \(finalRegion.span.latitudeDelta)°")
                
                mapRegion = finalRegion
                hasInitializedMapRegion = true
                
                print("🗺️ MapContainer: ✅ Map region initialized and flag set")
            } else {
                print("🗺️ MapContainer: Already initialized - skipping region calculation")
            }
            
            // Check for active Live Activity first
            checkForActiveLiveActivity()
            
            // Always ensure we start with overall congestion view (but preserve activeTrainRoute)
            appState.mapDisplayMode = .overallCongestion
            
            // IMPORTANT: Don't clear selectedRoute if we're navigating within the app
            // Only clear it if we're at the root (no navigation path)
            if appState.navigationPath.isEmpty {
                appState.selectedRoute = nil
            }
        }
        .onChange(of: appState.selectedRoute) { oldRoute, newRoute in
            // Animate map to show selected route when it changes
            if let route = newRoute {
                // Use current bottom sheet position since we're not changing it here
                animateMapToRoute(route, targetSheetPosition: bottomSheetPosition)
            }
        }
        // Removed automatic map animation when user selects origin station
        // This was causing the map to change location/zoom after origin selection
        // .onChange(of: appState.departureStationCode) { _, newDepartureCode in
        //     // Animate map to show departure station when it changes (origin selection)
        //     if let departureCode = newDepartureCode, appState.selectedRoute == nil {
        //         // Only animate to single station if no full route is selected yet
        //         // Use current bottom sheet position since we're not changing it here
        //         animateMapToStation(departureCode, targetSheetPosition: bottomSheetPosition)
        //     }
        // }
        .onChange(of: appState.navigationPath) { _, newPath in
            // Handle navigation-based map mode switching, but don't block UI
            // Use async dispatch to prevent navigation lag
            Task { @MainActor in
                handleNavigationChange(newPath)
            }
        }
        .onChange(of: appState.mapDisplayMode) { _, newMode in
            // Update map when display mode changes
            print("🗺️ Map display mode changed to: \(newMode)")
            // Note: MapDisplayMode handles overall map focus, not congestion visualization
            // Individual vs aggregated congestion is handled by CongestionMapView directly
        }
        .onChange(of: liveActivityService.isActivityActive) { _, isActive in
            // When Live Activity status changes, update the route highlight
            if isActive {
                checkForActiveLiveActivity()
            } else {
                // Clear the active train route when Live Activity ends
                appState.activeTrainRoute = nil
                appState.mapDisplayMode = .overallCongestion
            }
        }
        .onChange(of: appState.shouldExpandForDeepLink) { _, shouldExpand in
            // Handle deep link expansion request
            if shouldExpand {
                print("🔗 Deep link expansion requested")
                withAnimation(.easeInOut(duration: 0.3)) {
                    bottomSheetPosition = .expanded
                }
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            }
        }
        .sheet(item: $selectedSegment) { segment in
            SegmentTrainDetailsView(segment: segment)
                .presentationDetents([.height(600), .large])
                .presentationDragIndicator(.visible)
        }
    }
    
    private func handleNavigationChange(_ navigationPath: NavigationPath) {
        if navigationPath.isEmpty {
            // Back to home - reset to default Newark Penn view
            resetToDefaultMapView()
            bottomSheetPosition = .medium
        } else {
            // Check if we're navigating to train details
            if isNavigatingToTrainDetails(navigationPath) {
                // DO NOT animate the map when navigating to train details
                // The map should already be properly positioned from the train list view
                // Removing animation prevents the map from jumping/refocusing
                
                // Just snap bottom sheet to full screen (100%) when navigating to train details
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
        
        // DO NOT animate map here - it's already properly positioned from the train list view
        // Removing this prevents the map from jumping when viewing train details
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
        
        withAnimation(.easeInOut(duration: 0.25)) {
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
    
    private func resetToDefaultMapView() {
        print("🗺️ Reset: Resetting to default map view")
        
        // Clear state immediately (non-blocking)
        appState.selectedRoute = nil
        appState.mapDisplayMode = .overallCongestion
        
        // Do map operations asynchronously to avoid blocking navigation
        Task { @MainActor in
            withAnimation(.easeInOut(duration: 0.25)) {
                // Use smart default region (home/work focused) instead of hardcoded default
                let smartRegion = smartDefaultRegion
                let offset = calculateVisibleAreaOffset(for: .medium)
                
                print("🗺️ Reset: Using smart region - Center: \(smartRegion.center.latitude), \(smartRegion.center.longitude), Span: \(smartRegion.span.latitudeDelta)°")
                print("🗺️ Reset: Applied offset for medium position: \(offset)")
                
                mapRegion = MKCoordinateRegion(
                    center: CLLocationCoordinate2D(
                        latitude: smartRegion.center.latitude + offset,
                        longitude: smartRegion.center.longitude
                    ),
                    span: smartRegion.span
                )
                
                print("🗺️ Reset: ✅ Map region reset with smart default")
            }
            
            // Clear route filter in background to avoid blocking
            mapViewModel.setRouteFilter(nil)
        }
    }
    
    private func checkForActiveLiveActivity() {
        // Check if there's an active Live Activity
        if liveActivityService.isActivityActive,
           let activity = liveActivityService.currentActivity {
            // Create a TripPair from the Live Activity attributes
            let route = TripPair(
                departureCode: activity.attributes.originStationCode,
                departureName: activity.attributes.origin,
                destinationCode: activity.attributes.destinationStationCode,
                destinationName: activity.attributes.destination,
                lastUsed: Date(),
                isFavorite: false
            )
            
            // Set the active train route - this will trigger the persistent blue line
            appState.activeTrainRoute = route
            
            // Optionally animate map to show the route
            animateMapToRoute(route, targetSheetPosition: bottomSheetPosition)
        }
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
        
        withAnimation(.easeInOut(duration: 0.25)) {
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
            TrainListView(destination: stationName, sheetPosition: $bottomSheetPosition)
        case .trainDetails(let trainId):
            TrainDetailsView(trainId: trainId)
        case .trainDetailsFlexible(let trainNumber, let fromStation):
            TrainDetailsView(trainNumber: trainNumber, fromStation: fromStation)
        case .advancedConfiguration:
            AdvancedConfigurationView()
        case .myProfile:
            MyProfileView()
        case .favoriteStations:
            FavoriteStationsView()
        case .congestionMap:
            // Since map is always visible, show map controls and expand bottom sheet
            CongestionMapControlsView(
                mapViewModel: mapViewModel,
                onDismiss: {
                    // Reset to default map view and collapse bottom sheet
                    resetToDefaultMapView()
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