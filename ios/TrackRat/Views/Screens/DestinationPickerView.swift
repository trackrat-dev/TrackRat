import SwiftUI

struct DestinationPickerView: View {
    @EnvironmentObject private var appState: AppState
    @State private var searchText = ""
    @State private var isSearching = false
    @FocusState private var searchFieldFocused: Bool
    @State private var navigationBarVisible = false
    @State private var searchTask: Task<Void, Never>?

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
        // Native sheet handles scrolling automatically
        ScrollView {
            VStack(spacing: 16) {
                    // Simple centered title
                    Text("Where would you like to go?")
                        .font(.system(size: 26, weight: .semibold))
                        .foregroundColor(.white)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                        .frame(maxWidth: .infinity)
                        .padding(.top, 28)
                    
                    // Search results and favorite stations container
                    VStack(alignment: .leading, spacing: 16) {
                        // Back button and search field in horizontal stack
                        HStack(spacing: 8) {
                            // Minimal back button with chevron only
                            Button {
                                // Navigate back one step to origin selection
                                if !appState.navigationPath.isEmpty {
                                    appState.navigationPath.removeLast()
                                }
                                
                                // Clear destination selection but keep origin
                                appState.selectedDestination = nil
                                appState.destinationStationCode = nil
                                appState.selectedRoute = nil
                            } label: {
                                Image(systemName: "chevron.left")
                                    .font(.system(size: 16, weight: .semibold))
                                    .foregroundColor(.white)
                                    .frame(width: 40, height: 40)
                                    .background(
                                        RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                                            .fill(TrackRatTheme.Colors.surfaceCard)
                                            .overlay(
                                                RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                                                    .stroke(TrackRatTheme.Colors.border, lineWidth: 1)
                                            )
                                    )
                            }
                            
                            // Search field
                            HStack {
                                Image(systemName: "magnifyingglass")
                                    .foregroundColor(.white.opacity(0.6))
                                
                                TextField("Search for a station", text: $searchText)
                                    .foregroundColor(.white)
                                    .focused($searchFieldFocused)
                                    .autocorrectionDisabled(true)
                                    .textInputAutocapitalization(.never)
                                    .onChange(of: searchText) { _, newValue in
                                        searchTask?.cancel()
                                        searchTask = Task {
                                            try? await Task.sleep(for: .milliseconds(200))
                                            if !Task.isCancelled {
                                                await MainActor.run {
                                                    withAnimation(.easeInOut(duration: 0.3)) {
                                                        isSearching = !newValue.isEmpty
                                                    }
                                                }
                                            }
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
                            .frame(maxWidth: .infinity)
                        }
                        .padding(.horizontal)
                        
                        // Search results - take full page when searching
                        if isSearching {
                            VStack(spacing: 8) {
                                ForEach(searchResults, id: \.self) { station in
                                    Button {
                                        selectDestination(station)
                                    } label: {
                                        HStack {
                                            HStack {
                                                Text(Stations.displayName(for: station))
                                                    .font(.body)
                                                    .foregroundColor(.white)
                                                Spacer()
                                            }

                                            if let code = Stations.getStationCode(station) {
                                                StationIconView(
                                                    stationCode: code,
                                                    isStationFavorited: appState.isStationFavorited(code: code)
                                                ) {
                                                    withAnimation(.easeInOut(duration: 0.2)) {
                                                        appState.toggleFavoriteStation(code: code, name: station)
                                                    }
                                                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
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
                                    }
                                    .buttonStyle(.plain)
                                    .padding(.horizontal)
                                }
                            }
                            .transition(.opacity.combined(with: .move(edge: .top)))
                        }
                        
                        // Favorite stations - show when not typing in search
                        if !favoriteStations.isEmpty && !isSearching {
                            VStack(alignment: .leading, spacing: 16) {
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
        // Immediate UI state updates
        appState.selectedDestination = destination
        appState.destinationStationCode = Stations.getStationCode(destination)

        // Use pendingNavigation to expand sheet FIRST, then navigate
        appState.pendingNavigation = .trainList(destination: destination)

        // Reset search state
        withAnimation(.easeInOut(duration: 0.3)) {
            searchText = ""
            isSearching = false
            searchFieldFocused = false
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

                // Station icon - shows home/work icon or interactive heart
                StationIconView(
                    stationCode: station.id,
                    isStationFavorited: appState.isStationFavorited(code: station.id),
                    fontSize: 20
                ) {
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
        .buttonStyle(.plain)
    }
}

#Preview {
    DestinationPickerView()
        .environmentObject(AppState())
}
