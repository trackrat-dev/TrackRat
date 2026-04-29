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
    // Non-matching favorites are demoted below with a "No route from {origin}"
    // subtitle and are visually inert.
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

    // Splits demoted search results into two reasons so each gets the right UX:
    //   - systemDisabled: station's system isn't in the user's enabled systems →
    //     tap opens settings so the user can enable it.
    //   - noRoute: station's system IS enabled but doesn't share with the origin →
    //     inert, with explanatory subtitle.
    // System-disabled wins when both apply — enabling the system is the
    // discoverable next step; if it still doesn't reach this origin, the user
    // sees the noRoute reason on the next pass.
    private var demotedSearchResults: (systemDisabled: [String], noRoute: [String]) {
        var systemDisabled: [String] = []
        var noRoute: [String] = []
        for name in searchResults.otherSystemStations {
            guard let code = Stations.getStationCode(name) else {
                systemDisabled.append(name)
                continue
            }
            if Stations.isStationVisible(code, withSystems: appState.selectedSystems) {
                // Station's system is enabled, so it must be in `other` because
                // it doesn't share a system with the origin.
                noRoute.append(name)
            } else {
                systemDisabled.append(name)
            }
        }
        return (systemDisabled, noRoute)
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
                                        } else if !demotedSearchResults.systemDisabled.isEmpty {
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

                                let demoted = demotedSearchResults
                                if !demoted.systemDisabled.isEmpty {
                                    Text("Other systems — edit your train systems to use")
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.5))
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        .padding(.horizontal, 20)
                                        .padding(.top, 4)

                                    ForEach(demoted.systemDisabled, id: \.self) { station in
                                        Button {
                                            showSettingsForTrainSystems = true
                                        } label: {
                                            otherSystemDestinationSearchRow(station: station)
                                        }
                                        .buttonStyle(.plain)
                                        .padding(.horizontal)
                                    }
                                }

                                if !demoted.noRoute.isEmpty {
                                    ForEach(demoted.noRoute, id: \.self) { station in
                                        otherSystemDestinationSearchRow(
                                            station: station,
                                            noRouteOrigin: appState.selectedDeparture
                                        )
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

                                ForEach(split.otherSystem) { station in
                                    FavoriteDestinationButton(
                                        station: station,
                                        noRouteOrigin: appState.selectedDeparture
                                    ) {
                                        // Inert — kept for FavoriteDestinationButton signature.
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
        .sheet(isPresented: $showSettingsForTrainSystems) {
            SettingsView(editTrainSystems: true)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
    }
    
    // MARK: - Station Search Rows

    @ViewBuilder
    private func destinationSearchRow(station: String) -> some View {
        let code = Stations.getStationCode(station)
        HStack {
            HStack(spacing: 6) {
                Text(Stations.displayName(for: station))
                    .font(.body)
                    .foregroundColor(.white)
                    .textProtected()
                if let code {
                    SubwayLineChips(lines: SubwayLines.lines(forStationCode: code), size: 14)
                    SystemChips(stationCode: code, size: 14)
                }
                Spacer()
            }

            if let code {
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

    /// Demoted search row for stations on systems the user hasn't activated.
    /// When `noRouteOrigin` is provided, shows "No route from {origin}"
    /// below the station name.
    @ViewBuilder
    private func otherSystemDestinationSearchRow(station: String, noRouteOrigin: String? = nil) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(Stations.displayName(for: station))
                        .font(.body)
                        .foregroundColor(.white.opacity(0.7))
                        .textProtected()

                    if let code = Stations.getStationCode(station) {
                        SubwayLineChips(lines: SubwayLines.lines(forStationCode: code), size: 14)
                            .opacity(0.7)
                        SystemChips(stationCode: code, size: 14)
                            .opacity(0.7)
                    }
                }

                if let originName = noRouteOrigin {
                    Text("No route from \(Stations.displayName(for: originName))")
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.5))
                }
            }

            Spacer()

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
    /// When set, the button renders dimmed with a "No route from {origin}" subtitle
    /// and the tap callback is suppressed so the row is visually inert.
    var noRouteOrigin: String? = nil
    let onTap: () -> Void
    @EnvironmentObject private var appState: AppState

    private var isDimmed: Bool { noRouteOrigin != nil }

    var body: some View {
        if noRouteOrigin != nil {
            // Inert: no Button wrapper means no row-level tap handling. The heart
            // icon is its own Button so users can still unfavorite the station.
            rowContent
        } else {
            Button(action: onTap) {
                rowContent
            }
            .buttonStyle(.plain)
        }
    }

    @ViewBuilder
    private var rowContent: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(Stations.displayName(for: station.id))
                        .font(.callout)
                        .fontWeight(.medium)
                        .foregroundColor(.white.opacity(isDimmed ? 0.7 : 1.0))
                        .textProtected()
                    SubwayLineChips(lines: SubwayLines.lines(forStationCode: station.id), size: 14)
                        .opacity(isDimmed ? 0.7 : 1.0)
                    SystemChips(stationCode: station.id, size: 14)
                        .opacity(isDimmed ? 0.7 : 1.0)
                }

                if let originName = noRouteOrigin {
                    Text("No route from \(Stations.displayName(for: originName))")
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.5))
                }
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
}

#Preview {
    DestinationPickerView()
        .environmentObject(AppState())
}
