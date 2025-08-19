import SwiftUI

struct TripSelectionView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.openURL) private var openURL
    @State private var searchText = ""
    @State private var isSearching = false
    @FocusState private var searchFieldFocused: Bool
    @StateObject private var liveActivityService = LiveActivityService.shared
    
    // Callback to control bottom sheet position
    let onBottomSheetPositionChange: ((BottomSheetPosition) -> Void)?
    
    init(onBottomSheetPositionChange: ((BottomSheetPosition) -> Void)? = nil) {
        self.onBottomSheetPositionChange = onBottomSheetPositionChange
    }
    
    // Get favorite stations
    private var favoriteStations: [FavoriteStation] {
        return appState.favoriteStations
    }
    
    private var searchResults: [String] {
        Stations.search(searchText)
    }
    
    
    var body: some View {
        ZStack {
            // Theme background
            TrackRatTheme.Colors.surface
                .ignoresSafeArea()
            
            GeometryReader { geometry in
                VStack(spacing: 8) {
                // Top navigation bar with search and icons
                HStack(spacing: 16) {
                    // Search field - left aligned
                    HStack {
                        Image(systemName: "magnifyingglass")
                            .foregroundColor(.white.opacity(0.6))
                        
                        TextField("Select origin station", text: $searchText)
                            .foregroundColor(.white)
                            .focused($searchFieldFocused)
                            .onChange(of: searchText) { _, newValue in
                                withAnimation(.easeInOut(duration: 0.3)) {
                                    isSearching = !newValue.isEmpty
                                }
                            }
                            .onChange(of: searchFieldFocused) { _, newValue in
                                if newValue {
                                    // When search field gains focus, expand to medium to show favorites
                                    onBottomSheetPositionChange?(.medium)
                                }
                            }
                            .onSubmit {
                                if let firstResult = searchResults.first,
                                   let code = Stations.getStationCode(firstResult) {
                                    selectOriginStation(name: firstResult, code: code)
                                }
                            }
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(
                        RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                            .fill(TrackRatTheme.Colors.surfaceCard)
                            .overlay(
                                RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                                    .stroke(TrackRatTheme.Colors.border, lineWidth: 1)
                            )
                    )
                    .id("searchField")
                    
                    // Right side icons
                    HStack(spacing: 16) {
                        // Profile/Head icon - opens My Profile view
                        Button {
                            // Expand bottom sheet to 100% height when profile is tapped
                            onBottomSheetPositionChange?(.expanded)
                            appState.navigationPath.append(NavigationDestination.myProfile)
                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        } label: {
                            Image(systemName: "person.circle.fill")
                                .font(.system(size: 28))
                                .foregroundColor(.white.opacity(0.8))
                        }
                    }
                }
                .padding(.horizontal)
                .padding(.top, 20)
                
                // Search results and content container
                VStack(alignment: .leading, spacing: 16) {
                    // Search results
                    if isSearching {
                        VStack(spacing: 8) {
                            ForEach(searchResults.prefix(5), id: \.self) { station in
                                HStack {
                                    // Main station button
                                    Button {
                                        if let code = Stations.getStationCode(station) {
                                            selectOriginStation(name: station, code: code)
                                        }
                                    } label: {
                                        HStack {
                                            Text(station)
                                                .font(.body)
                                                .foregroundColor(.white)
                                            Spacer()
                                        }
                                    }
                                    
                                    // Heart button - separate from main button
                                    if let code = Stations.getStationCode(station) {
                                        Button {
                                            withAnimation(.easeInOut(duration: 0.2)) {
                                                appState.toggleFavoriteStation(code: code, name: station)
                                            }
                                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                                        } label: {
                                            Image(systemName: appState.isStationFavorited(code: code) ? "heart.fill" : "heart")
                                                .font(.system(size: 16))
                                                .foregroundColor(.orange)
                                        }
                                        .padding(.leading, 8)
                                    }
                                }
                                .padding()
                                .background(
                                    RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                                        .fill(TrackRatTheme.Colors.surfaceCard)
                                        .overlay(
                                            RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                                                .stroke(TrackRatTheme.Colors.border, lineWidth: 1)
                                        )
                                )
                                .padding(.horizontal)
                            }
                        }
                        .transition(.opacity.combined(with: .move(edge: .top)))
                    }
                    
                    // Active trips (Live Activity) - show when not searching
                    if !isSearching {
                        if #available(iOS 16.1, *) {
                            ActiveTripsSection()
                        }
                    }
                    
                    // Favorite stations - show when not searching
                    if !favoriteStations.isEmpty && !isSearching {
                        VStack(alignment: .leading, spacing: 16) {
                            Text("Where would you like to leave from?")
                                .font(TrackRatTheme.Typography.caption)
                                .fontWeight(.semibold)
                                .foregroundColor(TrackRatTheme.Colors.onSurfaceSecondary)
                                .padding(.horizontal)
                            
                            ForEach(favoriteStations) { station in
                                FavoriteStationButton(station: station) {
                                    selectOriginStation(name: station.name, code: station.id)
                                }
                                .padding(.horizontal)
                            }
                        }
                        .padding(.top, 8)
                        .transition(.opacity.combined(with: .move(edge: .top)))
                    }
                }
                .padding(.top, 12)
                
                // Spacer to push content to top and fill remaining space
                Spacer()
                }
                .frame(width: geometry.size.width, height: max(geometry.size.height, 600), alignment: .top)
            }
        }
        .onAppear {
            appState.loadRecentTrips()
            appState.loadFavoriteStations()
        }
    }
    
    private func selectTrip(_ trip: TripPair) {
        appState.selectedDeparture = trip.departureName
        appState.departureStationCode = trip.departureCode
        appState.selectedDestination = trip.destinationName
        appState.selectedRoute = trip  // Set selected route for map highlighting
        appState.navigationPath.append(NavigationDestination.trainList(destination: trip.destinationName))
        
        // Reset search state but maintain bottom sheet position
        withAnimation(.easeInOut(duration: 0.3)) {
            searchText = ""
            isSearching = false
            searchFieldFocused = false
        }
        // DON'T reset bottom sheet position - maintain current height
        // onBottomSheetPositionChange?(.compact)
        
        // Haptic feedback
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }
    
    private func selectOriginStation(name: String, code: String) {
        appState.selectedDeparture = name
        appState.departureStationCode = code
        // Clear any existing route so map focuses on single station
        appState.selectedRoute = nil
        
        // Snap bottom sheet to medium (50%) position for better map visibility
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
            onBottomSheetPositionChange?(.medium)
        }
        
        appState.navigationPath.append(NavigationDestination.destinationPicker)
        
        // Reset search with animation
        withAnimation(.easeInOut(duration: 0.3)) {
            searchText = ""
            isSearching = false
            searchFieldFocused = false
        }
        
        // Haptic feedback
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }
    
    
}

// MARK: - Favorite Station Button
struct FavoriteStationButton: View {
    let station: FavoriteStation
    let onTap: () -> Void
    @EnvironmentObject private var appState: AppState
    
    var body: some View {
        Button {
            onTap()
        } label: {
            HStack {
                Text(Stations.displayName(for: station.name))
                    .font(.callout)
                    .fontWeight(.medium)
                    .foregroundColor(.white)
                
                Spacer()
                
                // Unfavorite button (heart icon)
                Button {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        appState.toggleFavoriteStation(code: station.id, name: station.name)
                    }
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                } label: {
                    Image(systemName: "heart.fill")
                        .font(.system(size: 20))
                        .foregroundColor(.orange)
                }
                .onTapGesture {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        appState.toggleFavoriteStation(code: station.id, name: station.name)
                    }
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                }
                
                Image(systemName: "chevron.right")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(.white.opacity(0.6))
            }
            .padding()
            .frame(maxWidth: .infinity)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(.white.opacity(0.15))
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(.white.opacity(0.2), lineWidth: 1)
                    )
            )
        }
    }
}

#Preview {
    TripSelectionView()
        .environmentObject(AppState())
        .environmentObject(ThemeManager.shared)
}
