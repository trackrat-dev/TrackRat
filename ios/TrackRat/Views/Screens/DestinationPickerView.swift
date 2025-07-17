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
    
    // Computed property for dynamic spacing
    private var topPadding: CGFloat {
        (searchFieldFocused || isSearching) ? 20 : 100
    }
    
    // Computed property to determine if title should be shown
    private var shouldShowTitle: Bool {
        !searchFieldFocused && !isSearching
    }
    
    var body: some View {
        ZStack {
            // Black gradient background
            TrackRatTheme.Colors.primaryBackground
                .ignoresSafeArea()
            
            
            VStack(spacing: 16) {
                // Conditional title with spacing - only show when not searching
                if shouldShowTitle {
                    Text("Where to?")
                        .font(TrackRatTheme.Typography.title1)
                        .foregroundColor(TrackRatTheme.Colors.onSurface)
                        .transition(.opacity.combined(with: .move(edge: .top)))
                }
                
                Spacer()
                    .frame(height: shouldShowTitle ? 0 : topPadding)
                
                VStack(spacing: 20) {
                    // Search bar - moved to top
                    HStack {
                        Image(systemName: "magnifyingglass")
                            .foregroundColor(.white.opacity(0.6))
                        
                        TextField("Type station name...", text: $searchText)
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
                                    Button {
                                        selectDestination(station)
                                    } label: {
                                        HStack {
                                            Text(Stations.displayName(for: station))
                                                .font(.body)
                                                .foregroundColor(.white)
                                            Spacer()
                                            Image(systemName: "chevron.right")
                                                .font(.system(size: 14, weight: .semibold))
                                                .foregroundColor(.white.opacity(0.6))
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
                                    }
                                    .padding(.horizontal, 24)
                                }
                            }
                            .padding(.bottom, 50) // Add bottom padding for better scrolling
                        }
                        .transition(.opacity.combined(with: .move(edge: .top)))
                    } else {
                        // Popular destinations - only show when not searching
                        if !filteredPopularDestinations.isEmpty {
                            VStack(alignment: .leading, spacing: 12) {
                                Text("POPULAR DESTINATIONS")
                                    .font(TrackRatTheme.Typography.caption)
                                    .fontWeight(.semibold)
                                    .foregroundColor(TrackRatTheme.Colors.onSurfaceSecondary)
                                    .padding(.horizontal)
                                
                                VStack(spacing: 12) {
                                    ForEach(filteredPopularDestinations, id: \.code) { destination in
                                        Button {
                                            selectDestination(destination.name)
                                        } label: {
                                            HStack {
                                                Text(Stations.displayName(for: destination.name))
                                                    .font(.headline)
                                                    .foregroundColor(.white)
                                                
                                                Spacer()
                                                
                                                Image(systemName: "chevron.right")
                                                    .foregroundColor(.white.opacity(0.7))
                                                    .font(.caption)
                                            }
                                            .frame(maxWidth: .infinity)
                                            .padding(.horizontal, 20)
                                            .padding(.vertical, 16)
                                            .background(.white.opacity(0.2))
                                            .cornerRadius(12)
                                        }
                                    }
                                }
                                .padding(.horizontal, 24)
                            }
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
                .foregroundColor(.orange)
            }
        }
        .onAppear {
            // Initialize any view state if needed
        }
    }
    
    private func selectDestination(_ destination: String) {
        appState.selectedDestination = destination
        appState.destinationStationCode = Stations.getStationCode(destination)
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


#Preview {
    DestinationPickerView()
        .environmentObject(AppState())
}
