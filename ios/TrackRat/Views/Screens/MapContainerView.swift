import SwiftUI
import MapKit

// MARK: - PresentationDetent Extension for Map Offsets
extension PresentationDetent {
    /// Convert presentation detent to map offset for positioning
    var mapOffset: Double {
        switch self {
        case .fraction(0.50):  // Collapsed - 50% height
            return -0.10    // Small adjustment (~6 miles)
        case .large:           // Expanded - 100% height
            return -0.10    // map is totally hidden, seems better to not make adjustments that will require the map to move
        default:
            return -0.10    // Default to collapsed offset
        }
    }
}

// MARK: - Map Region View Model
@MainActor
class MapRegionViewModel: ObservableObject {
    @Published var mapRegion: MKCoordinateRegion
    
    // Sensible defaults using real station coordinates (NY Penn and Newark Penn)
    static let defaultFromStation = "NY"  // NY Penn Station
    static let defaultToStation = "NP"    // Newark Penn Station
    
    init() {
        // Calculate initial region using real station coordinates
        let homeCode = RatSenseService.shared.getHomeStation() ?? Self.defaultFromStation
        let workCode = RatSenseService.shared.getWorkStation() ?? Self.defaultToStation
        
        print("🗺️ MapRegionVM Init: Home: \(homeCode), Work: \(workCode)")
        
        // Get coordinates - these should always succeed with our defaults
        let fromCoord = Stations.getCoordinates(for: homeCode) ?? 
                       Stations.getCoordinates(for: Self.defaultFromStation)!
        let toCoord = Stations.getCoordinates(for: workCode) ?? 
                     Stations.getCoordinates(for: Self.defaultToStation)!
        
        // Use the shared static calculation method for consistency
        self.mapRegion = MapContainerView.calculateRegionForRoute(
            from: fromCoord,
            to: toCoord,
            sheetDetent: .fraction(0.50)
        )
        
        print("🗺️ MapRegionVM Init: Initial region set - Center: \(mapRegion.center.latitude), \(mapRegion.center.longitude), Span: \(mapRegion.span.latitudeDelta)°")
    }
}

struct MapContainerView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.scenePhase) private var scenePhase
    @State private var selectedDetent: PresentationDetent = .fraction(0.50)
    @State private var isSheetPresented = true  // Always show sheet (persistent)
    @State private var sheetExpansionTask: Task<Void, Never>?  // Track pending expansion for cancellation
    @StateObject private var mapViewModel = CongestionMapViewModel()
    @StateObject private var mapRegionVM = MapRegionViewModel()
    @State private var routeStatusContext: RouteStatusContext?
    @State private var selectedIndividualSegment: IndividualJourneySegment?
    @State private var hasSetInitialRegion = false
    @ObservedObject private var liveActivityService = LiveActivityService.shared
    @ObservedObject private var ratSenseService = RatSenseService.shared
    @ObservedObject private var feedbackService = JourneyFeedbackService.shared
    
    // MARK: - Unified Map Region Calculation
    
    /// Calculate map region for a route between two coordinates with consistent zoom and padding
    /// This is the single source of truth for route visualization across the app
    static func calculateRegionForRoute(
        from: CLLocationCoordinate2D,
        to: CLLocationCoordinate2D,
        sheetDetent: PresentationDetent
    ) -> MKCoordinateRegion {
        print("🗺️ Route: Calculating region from (\(from.latitude), \(from.longitude)) to (\(to.latitude), \(to.longitude))")
        
        // Handle case where both points are the same (e.g., home == work or single station)
        let isSameLocation = abs(from.latitude - to.latitude) < 0.001 && 
                           abs(from.longitude - to.longitude) < 0.001
        
        if isSameLocation {
            print("🗺️ Route: Same location detected - using single station view")
            // For single station, use a comfortable fixed zoom
            let singleStationSpan = MKCoordinateSpan(latitudeDelta: 0.3, longitudeDelta: 0.3)
            let offset = calculateZoomAwareOffset(for: sheetDetent, span: singleStationSpan)
            
            return MKCoordinateRegion(
                center: CLLocationCoordinate2D(
                    latitude: from.latitude + offset,
                    longitude: from.longitude
                ),
                span: singleStationSpan
            )
        }
        
        // Calculate center point between the two stations
        let centerLat = (from.latitude + to.latitude) / 2
        let centerLon = (from.longitude + to.longitude) / 2
        
        // Calculate span with 2x padding for consistency with train list view
        let latDelta = abs(from.latitude - to.latitude) * 2.0
        let lonDelta = abs(from.longitude - to.longitude) * 2.0
        
        // Ensure minimum zoom level (prevents over-zooming on very close stations)
        let minDelta: Double = 0.3
        let finalSpan = MKCoordinateSpan(
            latitudeDelta: max(latDelta, minDelta),
            longitudeDelta: max(lonDelta, minDelta)
        )
        
        // Calculate zoom-aware offset to account for bottom sheet
        let offset = calculateZoomAwareOffset(for: sheetDetent, span: finalSpan)
        
        // Adjust center to position content in visible area above bottom sheet
        let adjustedCenter = CLLocationCoordinate2D(
            latitude: centerLat + offset,
            longitude: centerLon
        )
        
        print("🗺️ Route: Final region - Center: (\(adjustedCenter.latitude), \(adjustedCenter.longitude)), Span: \(finalSpan.latitudeDelta)°")
        
        return MKCoordinateRegion(
            center: adjustedCenter,
            span: finalSpan
        )
    }
    
    var body: some View {
        ZStack {
            // Always show the map, just without congestion data when loading
            // Note: segments/individualSegments arrays are controlled by applyDisplayModeFilter()
            // which sets them based on highlightMode - no need for ternary checks here
            SystemCongestionMapView(
                region: $mapRegionVM.mapRegion,
                segments: mapViewModel.segments,
                individualSegments: mapViewModel.individualSegments,
                stations: mapViewModel.showStations ? mapViewModel.routeStations : [],
                showRoutes: mapViewModel.showRoutes,
                selectedSystems: appState.selectedSystems,
                highlightMode: mapViewModel.highlightMode,
                onSegmentTap: { segment in
                    guard appState.enableSegmentTap else { return }
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
                },
                onIndividualSegmentTap: { individualSegment in
                    guard appState.enableSegmentTap else { return }
                    selectedIndividualSegment = individualSegment
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                }
            )
            .ignoresSafeArea()

            // Operations summary pill (network scope) - positioned at top
            // Shows network summary + route summary when RatSense has a prediction
            VStack {
                if mapViewModel.highlightMode != .off {
                    OperationsSummaryView(
                        scope: .network,
                        ratSenseRoute: ratSenseService.suggestedJourney.map { ($0.fromStation, $0.toStation) }
                    )
                    .padding(.horizontal, 16)
                    .padding(.top, 30)
                }

                Spacer()

                // Show subtle loading indicator when data is loading
                if mapViewModel.isLoading && mapViewModel.segments.isEmpty {
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
                }
            }
            .padding(.bottom, 120) // Above bottom sheet

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
        }
        .preferredColorScheme(.dark)
        .sheet(isPresented: $isSheetPresented) {
            NavigationStack(path: $appState.navigationPath) {
                TripSelectionView()
                    .transparentNavigationBackground()
                    .navigationDestination(for: NavigationDestination.self) { destination in
                        bottomSheetNavigationContent(for: destination)
                    }
            }
            .presentationDetents([.fraction(0.50), .large], selection: $selectedDetent)
            .presentationDragIndicator(.visible)
            .interactiveDismissDisabled(true)
            .presentationBackgroundInteraction(.enabled)
            .legacyPresentationBackground(.ultraThinMaterial)
            .presentationContentInteraction(.resizes)
            .sheet(isPresented: $feedbackService.shouldShowFeedbackPrompt) {
                JourneyFeedbackPromptView()
            }
            .sheet(item: $appState.pendingRouteStatus) { context in
                RouteStatusView(context: context)
                    .presentationDetents([.large])
                    .presentationDragIndicator(.visible)
            }
            .sheet(item: $routeStatusContext) { context in
                RouteStatusView(context: context)
            }
            .sheet(item: $selectedIndividualSegment) { segment in
                TrainDetailsView(
                    trainNumber: segment.trainId,
                    fromStation: segment.fromStation,
                    journeyDate: segment.actualDeparture,
                    dataSource: segment.dataSource,
                    isSheet: true
                )
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
            }
        }
        .task {
            // Load congestion data when map container appears, but don't block UI
            // Use detached task to prevent UI lag during origin station selection
            let systems = appState.selectedSystems
            Task.detached(priority: .utility) { [weak mapViewModel] in
                await mapViewModel?.fetchCongestionDataIfNeeded(systems: systems)
            }
            mapViewModel.startAutoRefresh()
        }
        .onAppear {
            // Sync AppState settings to ViewModel on appear
            mapViewModel.setSelectedSystems(appState.selectedSystems, refetch: false)
            mapViewModel.highlightMode = appState.mapHighlightMode
            mapViewModel.showStations = appState.showMapStations
        }
        .onDisappear {
            mapViewModel.stopAutoRefresh()
        }
        .onChange(of: scenePhase) { _, newPhase in
            switch newPhase {
            case .active:
                mapViewModel.refreshIfStale()
                mapViewModel.startAutoRefresh()
            case .background, .inactive:
                mapViewModel.stopAutoRefresh()
            @unknown default:
                break
            }
        }
        .onChange(of: appState.selectedSystems) { _, newSystems in
            mapViewModel.setSelectedSystems(newSystems)
        }
        .onChange(of: appState.mapHighlightMode) { _, newMode in
            mapViewModel.highlightMode = newMode
        }
        .onChange(of: appState.showMapStations) { _, newValue in
            mapViewModel.showStations = newValue
        }
        .onChange(of: appState.deepLinkTrainNumber) { _, trainNumber in
            // Handle deep link navigation when train number is set
            guard let trainNumber = trainNumber else { return }

            print("🔗 Deep link detected - navigating to train \(trainNumber)")

            // For deep links, we reset the path and use expand-first navigation
            // Cancel any pending operations first
            sheetExpansionTask?.cancel()

            // Reset navigation path to root
            appState.navigationPath = NavigationPath()

            // Use pendingNavigation to expand sheet FIRST, then navigate
            // This ensures smooth transition even when deep linking
            // Note: dataSource not available from deep links, backend uses two-phase search
            appState.pendingNavigation = .trainDetailsFlexible(
                trainNumber: trainNumber,
                fromStation: appState.deepLinkFromStation,
                journeyDate: appState.deepLinkDate,
                dataSource: nil
            )
            print("🔗 Pending navigation set for train \(trainNumber)")

            // Clear deep link state after a delay to ensure navigation completes
            Task {
                try? await Task.sleep(nanoseconds: 800_000_000) // 0.8 seconds (expansion + navigation)
                await MainActor.run {
                    appState.clearDeepLinkState()
                    print("🔗 Deep link state cleared")

                    // Animate map to route if available
                    if let route = appState.selectedRoute {
                        animateMapToRoute(route, targetSheetDetent: .large)
                        print("🔗 Map animated to route")
                    }
                }
                print("✅ Deep link navigation completed")
            }
        }
        .onAppear {
            print("🗺️ MapContainer: onAppear called")
            print("🗺️ MapContainer: selectedDetent = \(selectedDetent)")
            print("🗺️ MapContainer: Map already initialized by view model - Center: \(mapRegionVM.mapRegion.center.latitude), \(mapRegionVM.mapRegion.center.longitude), Span: \(mapRegionVM.mapRegion.span.latitudeDelta)°")

            // If user has no home/work stations, use selected systems region instead of NY↔NP fallback (only on first appear)
            if !hasSetInitialRegion {
                if RatSenseService.shared.getHomeStation() == nil && RatSenseService.shared.getWorkStation() == nil {
                    mapRegionVM.mapRegion = appState.selectedSystems.combinedMapRegion.adjustedForBottomSheet()
                    print("🗺️ MapContainer: No home/work stations — using selected systems region")
                }
                hasSetInitialRegion = true
            }

            // Check for active Live Activity first
            checkForActiveLiveActivity()

            // Always ensure we start with overall congestion view (but preserve activeTrainRoute)
            appState.mapDisplayMode = .overallCongestion

            // Sync user's preferred highlight mode, default detail to summary
            mapViewModel.highlightMode = appState.mapHighlightMode
            mapViewModel.detailMode = .summary

            // IMPORTANT: Don't clear selectedRoute if we're navigating within the app
            // Only clear it if we're at the root (no navigation path)
            if appState.navigationPath.isEmpty {
                appState.selectedRoute = nil
            }
        }
        // Animate map when user selects departure station
        .onChange(of: appState.departureStationCode) { _, newCode in
            if let code = newCode {
                animateMapToStation(code, targetSheetDetent: selectedDetent)
            }
        }
        // Animate map to show route when user selects destination
        .onChange(of: appState.selectedRoute) { _, newRoute in
            if let route = newRoute {
                animateMapToRoute(route, targetSheetDetent: selectedDetent)
            }
        }
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
                // Use delayed expansion to allow NavigationStack to layout first
                expandSheetWithDelay()
            }
        }
        .onChange(of: appState.pendingNavigation) { _, pendingDestination in
            // Handle "expand first, then navigate" pattern
            // This ensures sheet is fully expanded before NavigationStack swaps content
            guard let destination = pendingDestination else { return }
            handlePendingNavigation(destination)
        }
    }

    private func handleNavigationChange(_ navigationPath: NavigationPath) {
        if navigationPath.isEmpty {
            // Back to home - cancel any pending operations
            sheetExpansionTask?.cancel()
            appState.pendingNavigation = nil
            appState.selectedTrip = nil
            selectedDetent = .fraction(0.50)
            // Note: Map stays static - no resetToDefaultMapView() call
        }
        // Note: Map stays static during all navigation - no switchToJourneyFocus() call
    }

    /// Expands the sheet to large with a small delay to allow NavigationStack content to layout first.
    /// This prevents the visual glitch where the sheet expands before new view content is rendered.
    /// NOTE: This is legacy - prefer using pendingNavigation for new code.
    private func expandSheetWithDelay(triggerHaptic: Bool = true) {
        // Skip if already expanded - no need to animate
        guard selectedDetent != .large else { return }

        // Cancel any pending expansion to handle rapid navigation
        sheetExpansionTask?.cancel()

        sheetExpansionTask = Task {
            // Wait briefly for NavigationStack to mount and start laying out the new view
            // 150ms provides safety margin for view initialization without feeling sluggish
            try? await Task.sleep(nanoseconds: 150_000_000)

            // Check if cancelled (e.g., user navigated back quickly)
            guard !Task.isCancelled else { return }

            await MainActor.run {
                withAnimation(.easeInOut(duration: 0.3)) {
                    selectedDetent = .large
                }
                if triggerHaptic {
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                }
            }
        }
    }

    /// Handles pending navigation by expanding the sheet FIRST, then navigating.
    /// Uses animation completion callback for reliable timing across iOS versions.
    private func handlePendingNavigation(_ destination: NavigationDestination) {
        // Cancel any pending expansion from other sources
        sheetExpansionTask?.cancel()

        // Clear pending navigation immediately to prevent re-triggers
        appState.pendingNavigation = nil

        // If sheet is already expanded, navigate immediately
        if selectedDetent == .large {
            appState.navigationPath.append(destination)
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
            return
        }

        // Haptic feedback when starting expansion
        UIImpactFeedbackGenerator(style: .light).impactOccurred()

        // Expand sheet, then navigate when animation completes
        withAnimation(.easeInOut(duration: 0.3)) {
            selectedDetent = .large
        } completion: {
            // Only navigate if sheet is still expanded (user didn't drag it down)
            if selectedDetent == .large {
                appState.navigationPath.append(destination)
            }
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
            Stations.areEquivalentStations(stop.stationCode, origin)
        }

        // For destination, try direct station code match first, then name matching
        let destinationIndex = stops.firstIndex { stop in
            // Try direct station code match first (destination is likely already a code)
            if Stations.areEquivalentStations(stop.stationCode, destination) {
                return true
            }
            // Try station name to code lookup as fallback
            if let destCode = Stations.getStationCode(destination) {
                return Stations.areEquivalentStations(stop.stationCode, destCode)
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
    
    private func animateMapToRoute(_ route: TripPair, targetSheetDetent: PresentationDetent? = nil) {
        // Get coordinates for departure and destination
        guard let fromCoords = Stations.getCoordinates(for: route.departureCode),
              let toCoords = Stations.getCoordinates(for: route.destinationCode) else {
            print("🗺️ AnimateRoute: Could not get coordinates for route \(route.departureCode) → \(route.destinationCode)")
            return
        }

        // Use the unified calculation for consistency
        let sheetDetent = targetSheetDetent ?? selectedDetent
        let region = Self.calculateRegionForRoute(
            from: fromCoords,
            to: toCoords,
            sheetDetent: sheetDetent
        )
        
        // Animate to the calculated region
        withAnimation(.easeInOut(duration: 0.25)) {
            mapRegionVM.mapRegion = region
        }
    }
    
    static func calculateZoomAwareOffset(for detent: PresentationDetent, span: MKCoordinateSpan) -> Double {
        let baseOffset = detent.mapOffset
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
            let region: MKCoordinateRegion
            let homeCode = RatSenseService.shared.getHomeStation()
            let workCode = RatSenseService.shared.getWorkStation()

            if homeCode != nil || workCode != nil {
                // User has home/work stations — calculate region between them
                let fromCode = homeCode ?? MapRegionViewModel.defaultFromStation
                let toCode = workCode ?? MapRegionViewModel.defaultToStation
                let fromCoord = Stations.getCoordinates(for: fromCode) ??
                               Stations.getCoordinates(for: MapRegionViewModel.defaultFromStation)!
                let toCoord = Stations.getCoordinates(for: toCode) ??
                             Stations.getCoordinates(for: MapRegionViewModel.defaultToStation)!
                region = Self.calculateRegionForRoute(
                    from: fromCoord,
                    to: toCoord,
                    sheetDetent: .fraction(0.50)
                )
            } else {
                // No home/work stations — use selected systems region
                region = appState.selectedSystems.combinedMapRegion.adjustedForBottomSheet()
            }

            withAnimation(.easeInOut(duration: 0.25)) {
                mapRegionVM.mapRegion = region
                print("🗺️ Reset: ✅ Map region reset to default")
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
            animateMapToRoute(route, targetSheetDetent: selectedDetent)
        }
    }

    private func animateMapToStation(_ stationCode: String, targetSheetDetent: PresentationDetent? = nil) {
        // Get coordinates for the station
        guard let coords = Stations.getCoordinates(for: stationCode) else {
            print("🗺️ AnimateStation: Could not get coordinates for station \(stationCode)")
            return
        }

        // Use the unified calculation for single station (pass same coordinate twice)
        let sheetDetent = targetSheetDetent ?? selectedDetent
        let region = Self.calculateRegionForRoute(
            from: coords,
            to: coords,
            sheetDetent: sheetDetent
        )
        
        // Animate to the calculated region
        withAnimation(.easeInOut(duration: 0.25)) {
            mapRegionVM.mapRegion = region
        }
    }
    
    @ViewBuilder
    private func bottomSheetNavigationContent(for destination: NavigationDestination) -> some View {
        Group {
            switch destination {
            case .departureSelector:
                DeparturePickerView()
            case .destinationPicker:
                DestinationPickerView()
            case .trainList(let stationName, let departureStationCode):
                TrainListView(destination: stationName, departureStationCode: departureStationCode)
            case .trainDetails(let trainId):
                TrainDetailsView(trainId: trainId)
            case .trainDetailsFlexible(let trainNumber, let fromStation, let journeyDate, let dataSource):
                TrainDetailsView(trainNumber: trainNumber, fromStation: fromStation, journeyDate: journeyDate, dataSource: dataSource)
            case .tripDetails:
                TripDetailsView()
            case .advancedConfiguration:
                AdvancedConfigurationView()
            case .favoriteStations:
                OnboardingView(isRepeating: true)
            case .congestionMap:
                // Since map is always visible, show map controls and expand bottom sheet
                CongestionMapControlsView(
                    mapViewModel: mapViewModel,
                    onDismiss: {
                        // Reset to default map view and collapse bottom sheet
                        resetToDefaultMapView()
                        selectedDetent = .fraction(0.50)
                    }
                )
            case .tripHistory:
                TripHistoryView()
            }
        }
        .transparentNavigationBackground()
        .edgeSwipeBack(path: $appState.navigationPath)
    }
}

// MARK: - Map Controls View
// This view appears when user taps "View Live Traffic" from the menu
struct CongestionMapControlsView: View {
    @EnvironmentObject private var appState: AppState
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
                .buttonStyle(.plain)
            }
            .padding(.horizontal)
            
            // Legend — shows both scales when mixed system types are visible
            let dataSources = Set(mapViewModel.segments.map(\.dataSource))
            let hasFrequencySystems = dataSources.contains { TrainSystem(rawValue: $0)?.preferredHighlightMode == .health }
            let hasDelaySystems = dataSources.contains { TrainSystem(rawValue: $0)?.preferredHighlightMode != .health }

            VStack(alignment: .leading, spacing: 12) {
                if hasFrequencySystems {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Service Health")
                            .trackRatSectionHeader()
                        HStack(spacing: 16) {
                            LegendItem(color: .green, label: "Healthy")
                            LegendItem(color: .yellow, label: "Moderate")
                            LegendItem(color: .orange, label: "Reduced")
                            LegendItem(color: .red, label: "Severe")
                        }
                    }
                }
                if hasDelaySystems {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Delay Levels")
                            .trackRatSectionHeader()
                        HStack(spacing: 16) {
                            LegendItem(color: .green, label: "Normal")
                            LegendItem(color: .yellow, label: "Moderate")
                            LegendItem(color: .orange, label: "Heavy")
                            LegendItem(color: .red, label: "Severe")
                        }
                    }
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
            .buttonStyle(.plain)
            .padding(.horizontal)
            .padding(.bottom)
        }
        .sheet(isPresented: $showingFilters) {
            FilterSheet(
                timeWindow: $timeWindow,
                selectedDataSource: $selectedDataSource,
                onApply: {
                    Task {
                        if selectedDataSource == "All" {
                            await mapViewModel.fetchCongestionData(
                                timeWindowHours: timeWindow,
                                systems: appState.selectedSystems
                            )
                        } else {
                            await mapViewModel.fetchCongestionData(
                                timeWindowHours: timeWindow,
                                dataSource: selectedDataSource
                            )
                        }
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
