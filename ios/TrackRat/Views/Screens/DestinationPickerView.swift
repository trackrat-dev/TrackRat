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
        20
    }
    
    var body: some View {
        ZStack {
            // Black gradient background
            TrackRatTheme.Colors.primaryBackground
                .ignoresSafeArea()
            
            
            VStack(spacing: 16) {
                Spacer()
                    .frame(height: topPadding)
                
                VStack(spacing: 20) {
                    // Search bar - moved to top
                    HStack {
                        Image(systemName: "magnifyingglass")
                            .foregroundColor(.white.opacity(0.6))
                        
                        TextField("Where would you like to go?", text: $searchText)
                            .foregroundColor(.white)
                            .focused($searchFieldFocused)
                            .onTapGesture {
                                withAnimation(.easeInOut(duration: 0.3)) {
                                    isSearching = true
                                }
                            }
                            .onChange(of: searchText) { _, newValue in
                                withAnimation(.easeInOut(duration: 0.3)) {
                                    isSearching = !newValue.isEmpty
                                }
                            }
                            .onChange(of: searchFieldFocused) { _, newValue in
                                withAnimation(.easeInOut(duration: 0.3)) {
                                    navigationBarVisible = newValue
                                }
                            }
                        
                        if isSearching {
                            Button {
                                withAnimation(.easeInOut(duration: 0.3)) {
                                    searchText = ""
                                    isSearching = false
                                    searchFieldFocused = false
                                }
                            } label: {
                                Image(systemName: "xmark.circle.fill")
                                    .foregroundColor(.white.opacity(0.6))
                            }
                        }
                    }
                    .padding()
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(.white.opacity(0.2))
                            .background(
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(.white.opacity(0.3), lineWidth: 1)
                            )
                    )
                    .padding(.horizontal, 24)
                    
                    // Search results - take full page when searching
                    if isSearching {
                        ScrollView {
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
                                        RoundedRectangle(cornerRadius: 12)
                                            .fill(.white.opacity(0.15))
                                            .background(
                                                RoundedRectangle(cornerRadius: 12)
                                                    .stroke(.white.opacity(0.2), lineWidth: 1)
                                            )
                                    )
                                    .padding(.horizontal, 24)
                                }
                            }
                            .padding(.bottom, 50) // Add bottom padding for better scrolling
                        }
                        .transition(.opacity.combined(with: .move(edge: .top)))
                    } else {
                        // Favorite stations - only show when not searching
                        if !favoriteStations.isEmpty {
                            VStack(alignment: .leading, spacing: 16) {
                                Text("FAVORITE STATIONS")
                                    .font(TrackRatTheme.Typography.caption)
                                    .fontWeight(.semibold)
                                    .foregroundColor(TrackRatTheme.Colors.onSurfaceSecondary)
                                    .padding(.horizontal, 24)
                                
                                ForEach(favoriteStations) { station in
                                    FavoriteDestinationButton(station: station) {
                                        selectDestination(station.name)
                                    }
                                    .padding(.horizontal, 24)
                                }
                            }
                            .padding(.top, 20)
                            .transition(.opacity.combined(with: .move(edge: .top)))
                        }
                    }
                }
                
                Spacer()
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .scrollAwareNavigationBar(isVisible: navigationBarVisible)
        .tint(.orange)
        .toolbar {
            
            ToolbarItem(placement: .navigationBarTrailing) {
                Button("Close") {
                    // Navigate back to the root (TripSelectionView)
                    appState.navigationPath.removeLast(appState.navigationPath.count)
                }
                .foregroundColor(.white)
            }
        }
        .onAppear {
            // Load favorite stations when view appears
            appState.loadFavoriteStations()
        }
    }
    
    private func selectDestination(_ destination: String) {
        appState.selectedDestination = destination
        appState.destinationStationCode = Stations.getStationCode(destination)
        
        // Create and set the selected route for map highlighting
        if let departureCode = appState.departureStationCode,
           let departureName = appState.selectedDeparture,
           let destinationCode = appState.destinationStationCode {
            appState.selectedRoute = TripPair(
                departureCode: departureCode,
                departureName: departureName,
                destinationCode: destinationCode,
                destinationName: destination,
                isFavorite: false
            )
        }
        
        appState.navigationPath.append(NavigationDestination.trainList(destination: destination))
        
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
