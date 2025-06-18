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
    
    private var filteredRecentDestinations: [String] {
        // Filter out the current departure station from recent destinations
        appState.recentDestinations.filter { $0 != appState.selectedDeparture }
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
            TrackRatTheme.Colors.primaryGradient
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
                        // Recent destinations - only show when not searching
                        if !filteredRecentDestinations.isEmpty {
                            VStack(alignment: .leading, spacing: 12) {
                                Text("RECENT DESTINATIONS")
                                    .font(TrackRatTheme.Typography.caption)
                                    .fontWeight(.semibold)
                                    .foregroundColor(TrackRatTheme.Colors.onSurfaceSecondary)
                                    .padding(.horizontal)
                                
                                ScrollView(.horizontal, showsIndicators: false) {
                                    HStack(spacing: 12) {
                                        ForEach(filteredRecentDestinations.sorted(), id: \.self) { destination in
                                            RecentDestinationPill(
                                                destination: destination,
                                                onTap: {
                                                    selectDestination(destination)
                                                },
                                                onRemove: {
                                                    withAnimation {
                                                        appState.removeDestination(destination)
                                                    }
                                                }
                                            )
                                        }
                                    }
                                    .padding(.horizontal)
                                }
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
            appState.loadRecentDestinations()
        }
    }
    
    private func selectDestination(_ destination: String) {
        appState.selectedDestination = destination
        appState.destinationStationCode = Stations.getStationCode(destination)
        appState.saveDestination(destination)
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

// MARK: - Recent Destination Pill
struct RecentDestinationPill: View {
    let destination: String
    let onTap: () -> Void
    let onRemove: () -> Void
    
    var body: some View {
        HStack(spacing: 8) {
            Text(Stations.displayName(for: destination))
                .font(.subheadline)
                .foregroundColor(.white)
            
            Button {
                onRemove()
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.8))
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(.white.opacity(0.2))
        .cornerRadius(20)
        .onTapGesture {
            onTap()
        }
    }
}

#Preview {
    DestinationPickerView()
        .environmentObject(AppState())
}