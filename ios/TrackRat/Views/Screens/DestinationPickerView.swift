import SwiftUI

struct DestinationPickerView: View {
    @EnvironmentObject private var appState: AppState
    @State private var searchText = ""
    @State private var isSearching = false
    @FocusState private var searchFieldFocused: Bool
    @State private var navigationBarVisible = false
    @State private var searchTask: Task<Void, Never>?
    @State private var showSettingsForTrainSystems = false

    private var searchResults: (stations: [String], otherSystemStations: [String]) {
        let grouped = Stations.searchGrouped(
            searchText,
            selectedSystems: appState.selectedSystems,
            originStationCode: appState.departureStationCode
        )

        return (
            grouped.primary.filter { $0 != appState.selectedDeparture },
            grouped.other.filter { $0 != appState.selectedDeparture }
        )
    }

    // Favorite stations — always visible, excluding departure station
    private var favoriteStations: [FavoriteStation] {
        return appState.favoriteStations.filter { station in
            station.id != appState.departureStationCode
        }
    }

    // Favorites split by whether they share a train system with the origin.
    // Non-matching favorites are demoted below, treated the same as stations
    // on a system the user hasn't activated.
    private var favoritesByOriginOverlap: (matching: [FavoriteStation], otherSystem: [FavoriteStation]) {
        let origin = appState.departureStationCode
        var matching: [FavoriteStation] = []
        var other: [FavoriteStation] = []
        for station in favoriteStations {
            if Stations.sharesSystem(stationCode: station.id, withOrigin: origin) {
                matching.append(station)
            } else {
                other.append(station)
            }
        }
        return (matching, other)
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
                        .font(TrackRatTheme.Typography.title2)
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
                                    .font(TrackRatTheme.IconSize.small)
                                    .foregroundColor(.white)
                                    .frame(minWidth: 40, minHeight: 40)
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
                                        if let firstResult = searchResults.stations.first {
                                            selectDestination(firstResult)
                                        } else if !searchResults.otherSystemStations.isEmpty {
                                            showSettingsForTrainSystems = true
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
                            let favoriteCodes = Set(favoriteStations.map(\.id))
                            let favoriteMatches = searchResults.stations.filter { station in
                                guard let code = Stations.getStationCode(station) else { return false }
                                return favoriteCodes.contains(code)
                            }
                            let otherMatches = searchResults.stations.filter { station in
                                guard let code = Stations.getStationCode(station) else { return true }
                                return !favoriteCodes.contains(code)
                            }

                            VStack(spacing: 8) {
                                // Favorite station matches first
                                if !favoriteMatches.isEmpty {
                                    Text("Favorites")
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.5))
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        .padding(.horizontal, 20)

                                    ForEach(favoriteMatches, id: \.self) { station in
                                        Button {
                                            selectDestination(station)
                                        } label: {
                                            destinationSearchRow(station: station)
                                        }
                                        .buttonStyle(.plain)
                                        .padding(.horizontal)
                                    }
                                }

                                // Remaining station matches
                                ForEach(otherMatches, id: \.self) { station in
                                    Button {
                                        selectDestination(station)
                                    } label: {
                                        destinationSearchRow(station: station)
                                    }
                                    .buttonStyle(.plain)
                                    .padding(.horizontal)
                                }

                                if !searchResults.otherSystemStations.isEmpty {
                                    Text("Other systems — edit your train systems to use")
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.5))
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        .padding(.horizontal, 20)
                                        .padding(.top, 4)

                                    ForEach(searchResults.otherSystemStations, id: \.self) { station in
                                        Button {
                                            showSettingsForTrainSystems = true
                                        } label: {
                                            otherSystemDestinationSearchRow(station: station)
                                        }
                                        .buttonStyle(.plain)
                                        .padding(.horizontal)
                                    }
                                }
                            }
                            .transition(.opacity.combined(with: .move(edge: .top)))
                        }
                        
                        // Favorite stations - show when not typing in search
                        if !favoriteStations.isEmpty && !isSearching {
                            let split = favoritesByOriginOverlap
                            VStack(alignment: .leading, spacing: 16) {
                                ForEach(split.matching) { station in
                                    FavoriteDestinationButton(station: station) {
                                        selectDestination(station.name)
                                    }
                                    .padding(.horizontal)
                                }

                                if !split.otherSystem.isEmpty {
                                    Text("Other systems — edit your train systems to use")
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.5))
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        .padding(.horizontal, 20)
                                        .padding(.top, 4)

                                    ForEach(split.otherSystem) { station in
                                        FavoriteDestinationButton(station: station, isDimmed: true) {
                                            showSettingsForTrainSystems = true
                                        }
                                        .padding(.horizontal)
                                    }
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
        .sheet(isPresented: $showSettingsForTrainSystems) {
            SettingsView(editTrainSystems: true)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
    }
    
    // MARK: - Station Search Rows

    @ViewBuilder
    private func destinationSearchRow(station: String) -> some View {
        HStack {
            HStack {
                Text(Stations.displayName(for: station))
                    .font(.body)
                    .foregroundColor(.white)
                    .textProtected()
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

    @ViewBuilder
    private func otherSystemDestinationSearchRow(station: String) -> some View {
        HStack {
            HStack {
                Text(Stations.displayName(for: station))
                    .font(.body)
                    .foregroundColor(.white.opacity(0.7))
                    .textProtected()

                if let code = Stations.getStationCode(station),
                   let system = Stations.primarySystem(forStationCode: code) {
                    SystemBadge(system: system)
                }

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
                .fill(TrackRatTheme.Colors.surfaceCard.opacity(0.6))
                .overlay(
                    RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                        .stroke(TrackRatTheme.Colors.border.opacity(0.6), lineWidth: 1)
                )
        )
    }

    private func selectDestination(_ destination: String) {
        // Immediate UI state updates
        appState.selectedDestination = destination
        appState.destinationStationCode = Stations.getStationCode(destination)

        // Set route so map animates to show departure → destination
        if let departureCode = appState.departureStationCode,
           let departureName = appState.selectedDeparture,
           let destinationCode = appState.destinationStationCode {
            appState.selectedRoute = TripPair(
                departureCode: departureCode,
                departureName: departureName,
                destinationCode: destinationCode,
                destinationName: destination
            )
        }

        // Use pendingNavigation to expand sheet FIRST, then navigate
        appState.pendingNavigation = .trainList(destination: destination, departureStationCode: appState.departureStationCode ?? "NY")

        // Reset search state WITHOUT animation to prevent ghosting during navigation
        var transaction = Transaction()
        transaction.disablesAnimations = true
        withTransaction(transaction) {
            searchText = ""
            isSearching = false
            searchFieldFocused = false
        }
    }
}

// MARK: - Favorite Destination Button
struct FavoriteDestinationButton: View {
    let station: FavoriteStation
    var isDimmed: Bool = false
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
                    .foregroundColor(.white.opacity(isDimmed ? 0.7 : 1.0))
                    .textProtected()

                if isDimmed, let system = Stations.primarySystem(forStationCode: station.id) {
                    SystemBadge(system: system)
                }

                Spacer()

                // Station icon - shows home/work icon or interactive heart
                StationIconView(
                    stationCode: station.id,
                    isStationFavorited: appState.isStationFavorited(code: station.id),
                    iconFont: TrackRatTheme.IconSize.medium
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
                    .fill(.white.opacity(isDimmed ? 0.08 : 0.15))
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(.white.opacity(isDimmed ? 0.12 : 0.2), lineWidth: 1)
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
