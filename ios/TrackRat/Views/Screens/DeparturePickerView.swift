import SwiftUI

struct DeparturePickerView: View {
    @EnvironmentObject private var appState: AppState
    @State private var searchText = ""
    @State private var isSearching = false
    @FocusState private var searchFieldFocused: Bool
    @State private var navigationBarVisible = false
    
    private var searchResults: [String] {
        Stations.search(searchText)
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
                    VStack(spacing: TrackRatTheme.Spacing.sm) {
                        Text("Where are you")
                            .font(TrackRatTheme.Typography.title1)
                            .foregroundColor(TrackRatTheme.Colors.onSurface)
                        
                        Text("departing from?")
                            .font(TrackRatTheme.Typography.title1)
                            .foregroundColor(TrackRatTheme.Colors.onSurface)
                    }
                    .transition(.opacity.combined(with: .move(edge: .top)))
                }
                
                Spacer()
                    .frame(height: shouldShowTitle ? 0 : topPadding)
                
                VStack(spacing: 20) {
                    // Search field - moved to top
                    HStack {
                        Image(systemName: "magnifyingglass")
                            .foregroundColor(.white.opacity(0.6))
                        
                        TextField("Search all stations", text: $searchText)
                            .foregroundColor(.white)
                            .focused($searchFieldFocused)
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
                            .onSubmit {
                                if let firstResult = searchResults.first,
                                   let code = Stations.getStationCode(firstResult) {
                                    selectDeparture(name: firstResult, code: code)
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
                                        if let code = Stations.getStationCode(station) {
                                            selectDeparture(name: station, code: code)
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
                    } else {
                        // Popular stations - only show when not searching
                        VStack(alignment: .leading, spacing: 12) {
                            Text("POPULAR STATIONS")
                                .font(.caption)
                                .fontWeight(.semibold)
                                .foregroundColor(.white.opacity(0.7))
                                .padding(.horizontal)
                            
                            VStack(spacing: 12) {
                                ForEach(Stations.departureStations, id: \.code) { station in
                                    DepartureButton(
                                        name: station.name,
                                        code: station.code,
                                        onTap: {
                                            selectDeparture(name: station.name, code: station.code)
                                        }
                                    )
                                }
                            }
                            .padding(.horizontal, 24)
                        }
                    }
                }
                
                Spacer()
                Spacer()
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .scrollAwareNavigationBar(isVisible: navigationBarVisible)
        .tint(.orange)
    }
    
    private func selectDeparture(name: String, code: String) {
        appState.selectedDeparture = name
        appState.departureStationCode = code
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

// MARK: - Departure Button
struct DepartureButton: View {
    let name: String
    let code: String
    let onTap: () -> Void
    
    var body: some View {
        Button {
            onTap()
        } label: {
            HStack {
                Text(Stations.displayName(for: name))
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

#Preview {
    DeparturePickerView()
        .environmentObject(AppState())
}