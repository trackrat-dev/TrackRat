import SwiftUI

struct TripSelectionView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.openURL) private var openURL
    @State private var searchText = ""
    @State private var isSearching = false
    @FocusState private var searchFieldFocused: Bool
    
    // Callback to control bottom sheet position
    let onBottomSheetPositionChange: ((BottomSheetPosition) -> Void)?
    
    init(onBottomSheetPositionChange: ((BottomSheetPosition) -> Void)? = nil) {
        self.onBottomSheetPositionChange = onBottomSheetPositionChange
    }
    
    // Get favorite trips
    private var favoriteTrips: [TripPair] {
        return appState.getFavoriteTrips()
    }
    
    private var searchResults: [String] {
        Stations.search(searchText)
    }
    
    var body: some View {
        ScrollView {
                VStack(spacing: 20) {
                        // Origin station search
                        VStack(alignment: .leading, spacing: 16) {
                            // Search field
                            HStack {
                                Image(systemName: "magnifyingglass")
                                    .foregroundColor(.white.opacity(0.6))
                                
                                TextField("Where are you departing from?", text: $searchText)
                                    .foregroundColor(.white)
                                    .focused($searchFieldFocused)
                                    .onChange(of: searchText) { _, newValue in
                                        withAnimation(.easeInOut(duration: 0.3)) {
                                            isSearching = !newValue.isEmpty
                                        }
                                    }
                                    .onChange(of: searchFieldFocused) { _, newValue in
                                        if newValue {
                                            // When search field gains focus, expand to 90%
                                            onBottomSheetPositionChange?(.large)
                                        } else if !isSearching {
                                            // When search field loses focus and not searching, return to compact
                                            onBottomSheetPositionChange?(.compact)
                                        }
                                    }
                                    .onSubmit {
                                        if let firstResult = searchResults.first,
                                           let code = Stations.getStationCode(firstResult) {
                                            selectOriginStation(name: firstResult, code: code)
                                        }
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
                            
                            // Search results
                            if isSearching {
                                VStack(spacing: 8) {
                                    ForEach(searchResults.prefix(5), id: \.self) { station in
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
                                                Image(systemName: "chevron.right")
                                                    .font(.system(size: 14, weight: .semibold))
                                                    .foregroundColor(.white.opacity(0.6))
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
                                        .padding(.horizontal)
                                    }
                                }
                            }
                        }
                        .padding(.top, 20)
                        
                        // Active trips (Live Activity) - now below search box
                        if #available(iOS 16.1, *) {
                            ActiveTripsSection()
                        }
                        
                        // Favorite routes - only show when search field is focused
                        if searchFieldFocused && !favoriteTrips.isEmpty {
                            VStack(alignment: .leading, spacing: 16) {
                                Text("FAVORITE ROUTES")
                                    .font(TrackRatTheme.Typography.caption)
                                    .fontWeight(.semibold)
                                    .foregroundColor(TrackRatTheme.Colors.onSurfaceSecondary)
                                    .padding(.horizontal)
                                
                                ForEach(favoriteTrips) { trip in
                                    TripButton(trip: trip) {
                                        selectTrip(trip)
                                    }
                                    .padding(.horizontal)
                                }
                            }
                            .padding(.top, 20)
                        }
                        
                        // More section
                        VStack(alignment: .leading, spacing: 16) {
                            Text("MORE")
                                .font(TrackRatTheme.Typography.caption)
                                .fontWeight(.semibold)
                                .foregroundColor(TrackRatTheme.Colors.onSurfaceSecondary)
                                .padding(.horizontal)
                            
                            // Train number search
                            Button {
                                appState.navigationPath.append(NavigationDestination.trainNumberSearch)
                                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                            } label: {
                                HStack {
                                    Image(systemName: "number.circle.fill")
                                        .font(.system(size: 14))
                                        .foregroundColor(.gray)
                                    
                                    Text("Search by train number")
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.7))
                                    
                                    Spacer()
                                    
                                    Image(systemName: "chevron.right")
                                        .font(.system(size: 12))
                                        .foregroundColor(.white.opacity(0.5))
                                }
                                .padding(.horizontal, 12)
                                .padding(.vertical, 8)
                                .background(
                                    RoundedRectangle(cornerRadius: 8)
                                        .fill(.white.opacity(0.08))
                                        .background(
                                            RoundedRectangle(cornerRadius: 8)
                                                .stroke(.white.opacity(0.15), lineWidth: 1)
                                        )
                                )
                                .padding(.horizontal)
                            }
                            
                            // Report Issues & Request Features button
                            Button {
                                if let signalURL = URL(string: "https://signal.me/#eu/iG3LNnu-IycTUbwrWF1nwrlR-u-TN5gtBO0tXtJk3Nder7TtfzFPa6On6N9dl3e-") {
                                    openURL(signalURL)
                                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                                }
                            } label: {
                                HStack {
                                    Image(systemName: "exclamationmark.bubble.fill")
                                        .font(.system(size: 14))
                                        .foregroundColor(.gray)
                                    
                                    Text("Report Issues & Request Features")
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.7))
                                    
                                    Spacer()
                                    
                                    Image(systemName: "chevron.right")
                                        .font(.system(size: 12))
                                        .foregroundColor(.white.opacity(0.5))
                                }
                                .padding(.horizontal, 12)
                                .padding(.vertical, 8)
                                .background(
                                    RoundedRectangle(cornerRadius: 8)
                                        .fill(.white.opacity(0.08))
                                        .background(
                                            RoundedRectangle(cornerRadius: 8)
                                                .stroke(.white.opacity(0.15), lineWidth: 1)
                                        )
                                )
                                .padding(.horizontal)
                            }
                            
                            // Advanced Configuration button
                            Button {
                                appState.navigationPath.append(NavigationDestination.advancedConfiguration)
                                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                            } label: {
                                HStack {
                                    Image(systemName: "gearshape.fill")
                                        .font(.system(size: 14))
                                        .foregroundColor(.gray)
                                    
                                    Text("Advanced Configuration")
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.7))
                                    
                                    Spacer()
                                    
                                    Image(systemName: "chevron.right")
                                        .font(.system(size: 12))
                                        .foregroundColor(.white.opacity(0.5))
                                }
                                .padding(.horizontal, 12)
                                .padding(.vertical, 8)
                                .background(
                                    RoundedRectangle(cornerRadius: 8)
                                        .fill(.white.opacity(0.08))
                                        .background(
                                            RoundedRectangle(cornerRadius: 8)
                                                .stroke(.white.opacity(0.15), lineWidth: 1)
                                        )
                                )
                                .padding(.horizontal)
                            }
                        }
                        .padding(.top, 20)
                        
                }
                .padding(.bottom, 40)
            }
        .onAppear {
            appState.loadRecentTrips()
        }
    }
    
    private func selectTrip(_ trip: TripPair) {
        appState.selectedDeparture = trip.departureName
        appState.departureStationCode = trip.departureCode
        appState.selectedDestination = trip.destinationName
        appState.selectedRoute = trip  // Set selected route for map highlighting
        appState.navigationPath.append(NavigationDestination.trainList(destination: trip.destinationName))
        
        // Reset search state and bottom sheet position
        withAnimation(.easeInOut(duration: 0.3)) {
            searchText = ""
            isSearching = false
            searchFieldFocused = false
        }
        onBottomSheetPositionChange?(.compact)
        
        // Haptic feedback
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }
    
    private func selectOriginStation(name: String, code: String) {
        appState.selectedDeparture = name
        appState.departureStationCode = code
        // Clear any existing route so map focuses on single station
        appState.selectedRoute = nil
        appState.navigationPath.append(NavigationDestination.destinationPicker)
        
        // Reset search with animation
        withAnimation(.easeInOut(duration: 0.3)) {
            searchText = ""
            isSearching = false
            searchFieldFocused = false
        }
        
        // Reset bottom sheet position
        onBottomSheetPositionChange?(.compact)
        
        // Haptic feedback
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }
    
    
}

// MARK: - Trip Button
struct TripButton: View {
    let trip: TripPair
    let onTap: () -> Void
    @EnvironmentObject private var appState: AppState
    
    var body: some View {
        Button {
            onTap()
        } label: {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("\(Stations.displayName(for: trip.departureName)) to \(trip.destinationName)")
                        .font(.callout)
                        .fontWeight(.medium)
                        .foregroundColor(.white)
                }
                
                Spacer()
                
                // Reverse direction button
                Button {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        appState.reverseFavoriteDirection(trip)
                    }
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                } label: {
                    Image(systemName: "arrow.triangle.2.circlepath")
                        .font(.system(size: 18))
                        .foregroundColor(.orange)
                }
                
                // Unfavorite button (heart icon)
                Button {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        appState.toggleFavorite(trip)
                    }
                } label: {
                    Image(systemName: "heart.fill")
                        .font(.system(size: 20))
                        .foregroundColor(.orange)
                }
                .onTapGesture {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        appState.toggleFavorite(trip)
                    }
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
    TripSelectionView()
        .environmentObject(AppState())
}
