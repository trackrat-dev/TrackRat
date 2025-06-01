import SwiftUI

struct DestinationPickerView: View {
    @EnvironmentObject private var appState: AppState
    @State private var searchText = ""
    @State private var isSearching = false
    @FocusState private var searchFieldFocused: Bool
    
    private var searchResults: [String] {
        let results = Stations.search(searchText)
        // Filter out the current departure station
        return results.filter { $0 != appState.selectedDeparture }
    }
    
    private var filteredRecentDestinations: [String] {
        // Filter out the current departure station from recent destinations
        appState.recentDestinations.filter { $0 != appState.selectedDeparture }
    }
    
    var body: some View {
        ZStack {
            // Background gradient
            LinearGradient(
                colors: [Color(hex: "667eea"), Color(hex: "764ba2")],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
            
            
            VStack(spacing: 32) {
                // Title with spacing
                Text("Where to?")
                    .font(.largeTitle)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                    .padding(.top, 100)
                
                VStack(spacing: 20) {
                    // Recent destinations
                    if !filteredRecentDestinations.isEmpty && !isSearching {
                        VStack(alignment: .leading, spacing: 12) {
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
                    
                    // Search bar
                    VStack(spacing: 0) {
                        HStack {
                            Image(systemName: "magnifyingglass")
                                .foregroundColor(.gray)
                            
                            TextField("Type station name...", text: $searchText)
                                .textFieldStyle(.plain)
                                .focused($searchFieldFocused)
                                .onTapGesture {
                                    isSearching = true
                                }
                                .onChange(of: searchText) { _, newValue in
                                    isSearching = !newValue.isEmpty
                                }
                            
                            if isSearching {
                                Button {
                                    searchText = ""
                                    isSearching = false
                                    searchFieldFocused = false
                                } label: {
                                    Image(systemName: "xmark.circle.fill")
                                        .foregroundColor(.gray)
                                }
                            }
                        }
                        .padding()
                        .background(.ultraThinMaterial)
                        .cornerRadius(12)
                        .padding(.horizontal)
                        
                        // Search results
                        if isSearching && !searchResults.isEmpty {
                            ScrollView {
                                VStack(spacing: 0) {
                                    ForEach(searchResults, id: \.self) { station in
                                        Button {
                                            selectDestination(station)
                                        } label: {
                                            HStack {
                                                Text(Stations.displayName(for: station))
                                                    .foregroundColor(.primary)
                                                Spacer()
                                                Image(systemName: "chevron.right")
                                                    .foregroundColor(.secondary)
                                                    .font(.caption)
                                            }
                                            .padding()
                                            .contentShape(Rectangle())
                                        }
                                        .buttonStyle(.plain)
                                        
                                        if station != searchResults.last {
                                            Divider()
                                                .padding(.leading)
                                        }
                                    }
                                }
                                .background(.ultraThinMaterial)
                                .cornerRadius(12)
                                .padding(.horizontal)
                                .padding(.top, 8)
                            }
                            .frame(maxHeight: 300)
                            .transition(.opacity.combined(with: .move(edge: .top)))
                        }
                    }
                }
                
                Spacer()
            }
        }
        .navigationTitle("Select Destination")
        .navigationBarTitleDisplayMode(.inline)
        .glassmorphicNavigationBar()
        .toolbar {
            ToolbarItem(placement: .principal) {
                if let departure = appState.selectedDeparture {
                    VStack(spacing: 0) {
                        Text("Select Destination")
                            .font(.headline)
                            .foregroundColor(.white)
                        Text("from \(Stations.displayName(for: departure))")
                            .font(.caption2)
                            .foregroundColor(.white.opacity(0.8))
                    }
                }
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
        
        // Reset search
        searchText = ""
        isSearching = false
        searchFieldFocused = false
        
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