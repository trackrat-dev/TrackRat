import SwiftUI

struct FavoriteStationsView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    
    @State private var searchText = ""
    @State private var favoriteStations: [FavoriteStation] = []
    @State private var showingLimitAlert = false
    @State private var showOnboarding = false
    
    // Home and Work stations from RatSense
    private var homeStation: String? {
        RatSenseService.shared.getHomeStation()
    }
    
    private var workStation: String? {
        RatSenseService.shared.getWorkStation()
    }
    
    private let maxFavorites = 20
    private let softLimit = 10
    
    // Filter out home/work stations from the favorites list
    private var otherFavorites: [FavoriteStation] {
        favoriteStations.filter { station in
            station.id != homeStation && station.id != workStation
        }
    }
    
    private var filteredStations: [(String, String)] {
        let allStations = Stations.all.compactMap { name -> (String, String)? in
            guard let code = Stations.getStationCode(name) else { return nil }
            return (name, code)
        }
        
        if searchText.isEmpty {
            // Show popular stations when not searching
            let popularCodes = ["NP", "TR", "PJ", "MP", "OG"]
            let popularStations = popularCodes.compactMap { code -> (String, String)? in
                if let name = Stations.displayName(for: code) {
                    return (name, code)
                }
                return nil
            }
            
            let otherStations = allStations.filter { (_, code) in
                !popularCodes.contains(code) && code != "NY"
            }.sorted { $0.0 < $1.0 }
            
            return popularStations + otherStations
        } else {
            return allStations.filter { (name, code) in
                name.localizedCaseInsensitiveContains(searchText) ||
                code.localizedCaseInsensitiveContains(searchText)
            }.sorted { $0.0 < $1.0 }
        }
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Header
            VStack(spacing: 16) {
                    HStack {
                        Button("Done") {
                            dismiss()
                        }
                        .foregroundColor(.orange)
                        .font(.headline)
                        
                        Spacer()
                        
                        Text("Favorite Stations")
                            .font(.headline)
                            .fontWeight(.semibold)
                            .foregroundColor(.white)
                        
                        Spacer()
                        
                        // Balance with Done button
                        Text("")
                            .font(.headline)
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 10)
                    
                    // Search bar
                    HStack {
                        Image(systemName: "magnifyingglass")
                            .foregroundColor(.white.opacity(0.6))
                        
                        TextField("Search stations...", text: $searchText)
                            .textFieldStyle(PlainTextFieldStyle())
                            .foregroundColor(.white)
                            .accentColor(.orange)
                            .autocorrectionDisabled(true)
                            .textInputAutocapitalization(.never)
                    }
                    .padding()
                    .background(Material.ultraThin)
                    .cornerRadius(12)
                    .padding(.horizontal, 20)
                }
                .padding(.bottom, 20)
                
                // Content
                ScrollView {
                    LazyVStack(spacing: 16) {
                        // Home & Work Stations section
                        if homeStation != nil || workStation != nil {
                            VStack(alignment: .leading, spacing: 12) {
                                HStack {
                                    Text("Home & Work Stations")
                                        .font(.headline)
                                        .fontWeight(.semibold)
                                        .foregroundColor(.white)
                                    
                                    Spacer()
                                    
                                    Button {
                                        showOnboarding = true
                                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                                    } label: {
                                        Text("Edit")
                                            .font(.subheadline)
                                            .foregroundColor(.orange)
                                    }
                                }
                                .padding(.horizontal, 20)
                                
                                if let homeCode = homeStation,
                                   let homeName = Stations.displayName(for: homeCode) {
                                    HomeWorkStationRow(
                                        stationName: homeName,
                                        stationCode: homeCode,
                                        isHome: true
                                    )
                                    .padding(.horizontal, 20)
                                }
                                
                                if let workCode = workStation,
                                   let workName = Stations.displayName(for: workCode) {
                                    HomeWorkStationRow(
                                        stationName: workName,
                                        stationCode: workCode,
                                        isHome: false
                                    )
                                    .padding(.horizontal, 20)
                                }
                            }
                            .padding(.bottom, 24)
                        }
                        
                        // Other favorites section (excluding home/work)
                        if !otherFavorites.isEmpty {
                            VStack(alignment: .leading, spacing: 12) {
                                HStack {
                                    Text("Other favorites")
                                        .font(.headline)
                                        .fontWeight(.semibold)
                                        .foregroundColor(.white)
                                    Spacer()
                                }
                                .padding(.horizontal, 20)
                                
                                ForEach(otherFavorites.sorted(by: { $0.lastUsed > $1.lastUsed })) { station in
                                    StationRow(
                                        station: station,
                                        isFavorite: .constant(true),
                                        onToggleFavorite: {
                                            toggleFavorite(code: station.id, name: station.name)
                                        }
                                    )
                                    .padding(.horizontal, 20)
                                }
                            }
                            .padding(.bottom, 24)
                        }
                        
                        // Add more stations section
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                Text(searchText.isEmpty ? "All Stations" : "Search results")
                                    .font(.headline)
                                    .fontWeight(.semibold)
                                    .foregroundColor(.white)
                                Spacer()
                            }
                            .padding(.horizontal, 20)
                            
                            ForEach(filteredStations, id: \.1) { (stationName, stationCode) in
                                let isFavorite = favoriteStations.contains { $0.id == stationCode }
                                
                                SearchStationRow(
                                    stationName: stationName,
                                    stationCode: stationCode,
                                    isFavorite: .constant(isFavorite),
                                    onToggleFavorite: {
                                        toggleFavorite(code: stationCode, name: stationName)
                                    }
                                )
                                .padding(.horizontal, 20)
                            }
                        }
                    }
                    .padding(.bottom, 40)
            }
        }
        .navigationBarHidden(true)
        .onAppear {
            loadFavoriteStations()
        }
        .alert("Too Many Favorites", isPresented: $showingLimitAlert) {
            Button("OK") { }
        } message: {
            Text("You can have up to \(maxFavorites) favorite stations. Having too many favorites may slow down the app.")
        }
        .fullScreenCover(isPresented: $showOnboarding) {
            OnboardingView()
        }
    }
    
    // MARK: - Helper Functions
    private func loadFavoriteStations() {
        favoriteStations = appState.favoriteStations
    }
    
    private func toggleFavorite(code: String, name: String) {
        let currentCount = favoriteStations.count
        let isCurrentlyFavorite = favoriteStations.contains { $0.id == code }
        
        // Check limits before adding
        if !isCurrentlyFavorite {
            if currentCount >= maxFavorites {
                showingLimitAlert = true
                return
            }
            
            if currentCount >= softLimit {
                // Show soft warning but allow
                UINotificationFeedbackGenerator().notificationOccurred(.warning)
            }
        }
        
        // Toggle the favorite
        appState.toggleFavoriteStation(code: code, name: name)
        
        // Reload the list
        loadFavoriteStations()
        
        // Provide haptic feedback
        if isCurrentlyFavorite {
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
        } else {
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        }
    }
}

#Preview {
    NavigationView {
        FavoriteStationsView()
            .environmentObject(AppState())
    }
}