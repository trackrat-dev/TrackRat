import SwiftUI

struct DestinationPickerView: View {
    @EnvironmentObject private var appState: AppState
    @State private var searchText = ""
    @State private var isSearching = false
    @FocusState private var searchFieldFocused: Bool
    @State private var navigationBarVisible = false
    
    private var searchResults: [String] {
        let results = Stations.search(searchText)
        // Filter out the current departure station
        return results.filter { $0 != appState.selectedDeparture }
    }
    
    
    private var filteredPopularDestinations: [(name: String, code: String)] {
        // Filter out popular destinations that are the same as departure station
        Stations.popularDestinations.filter { destination in
            destination.code != appState.departureStationCode
        }
    }
    
    // Get favorite stations (filtered to exclude departure station)
    private var favoriteStations: [FavoriteStation] {
        return appState.favoriteStations.filter { station in
            station.id != appState.departureStationCode
        }
    }
    
    // Computed property for dynamic spacing - keep consistent spacing
    private var topPadding: CGFloat {
        0
    }
    
    var body: some View {
        ZStack {
            // Black gradient background
            TrackRatTheme.Colors.primaryBackground
                .ignoresSafeArea()
            
            VStack(spacing: 8) {
                    // Top navigation bar with search and close button
                    HStack(spacing: 16) {
                        // Search field - left aligned
                        HStack {
                            Image(systemName: "magnifyingglass")
                                .foregroundColor(.white.opacity(0.6))
                            
                            TextField("Select destination", text: $searchText)
                                .foregroundColor(.white)
                                .focused($searchFieldFocused)
                                .onChange(of: searchText) { _, newValue in
                                    withAnimation(.easeInOut(duration: 0.3)) {
                                        isSearching = !newValue.isEmpty
                                    }
                                }
                                .onSubmit {
                                    if let firstResult = searchResults.first {
                                        selectDestination(firstResult)
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
                        
                        // Close button
                        Button {
                            // Navigate back to the root (TripSelectionView)
                            appState.navigationPath.removeLast(appState.navigationPath.count)
                        } label: {
                            Text("Close")
                                .foregroundColor(.white)
                                .font(.body)
                        }
                    }
                    .padding(.horizontal)
                    .padding(.top, 10)
                    
                    
                    // Search results and favorite stations container
                    VStack(alignment: .leading, spacing: 16) {
                        // Search results - take full page when searching
                        if isSearching {
                            VStack(spacing: 8) {
                                ForEach(searchResults, id: \.self) { station in
                                    HStack {
                                        // Main station button
                                        Button {
                                            selectDestination(station)
                                        } label: {
                                            HStack {
                                                Text(Stations.displayName(for: station))
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
                        
                        // Favorite stations - show when not typing in search
                        if !favoriteStations.isEmpty && !isSearching {
                            VStack(alignment: .leading, spacing: 16) {
                                Text("FAVORITE STATIONS")
                                    .font(TrackRatTheme.Typography.caption)
                                    .fontWeight(.semibold)
                                    .foregroundColor(TrackRatTheme.Colors.onSurfaceSecondary)
                                    .padding(.horizontal)
                                
                                ForEach(favoriteStations) { station in
                                    FavoriteDestinationButton(station: station) {
                                        selectDestination(station.name)
                                    }
                                    .padding(.horizontal)
                                }
                            }
                            .padding(.top, 8)
                            .transition(.opacity.combined(with: .move(edge: .top)))
                        }
                    }
                    .padding(.top, searchFieldFocused ? 8 : 12)
                
                // Spacer to push content to top and fill remaining space
                Spacer()
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        }
        .navigationBarHidden(true)
        .onAppear {
            // Load favorite stations when view appears
            appState.loadFavoriteStations()
        }
    }
    
    private func selectDestination(_ destination: String) {
        // Immediate UI state updates - these happen instantly for responsive feedback
        appState.selectedDestination = destination
        appState.destinationStationCode = Stations.getStationCode(destination)
        
        // Immediate navigation - this should happen right away
        appState.navigationPath.append(NavigationDestination.trainList(destination: destination))
        
        // Immediate UI feedback - provides instant user response
        withAnimation(.easeInOut(duration: 0.3)) {
            searchText = ""
            isSearching = false
            searchFieldFocused = false
        }
        
        // Immediate haptic feedback
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
        
        // DEFER the heavy map route setting to happen after UI updates
        // This prevents the map processing from blocking the station selection UI
        DispatchQueue.main.async {
            // Create and set the selected route for map highlighting
            if let departureCode = self.appState.departureStationCode,
               let departureName = self.appState.selectedDeparture,
               let destinationCode = self.appState.destinationStationCode {
                self.appState.selectedRoute = TripPair(
                    departureCode: departureCode,
                    departureName: departureName,
                    destinationCode: destinationCode,
                    destinationName: destination,
                    isFavorite: false
                )
            }
        }
    }
}

// MARK: - Favorite Destination Button
struct FavoriteDestinationButton: View {
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
    DestinationPickerView()
        .environmentObject(AppState())
}
