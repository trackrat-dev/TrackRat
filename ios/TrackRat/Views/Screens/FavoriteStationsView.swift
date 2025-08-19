import SwiftUI

struct FavoriteStationsView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    
    @State private var searchText = ""
    @State private var favoriteStations: [FavoriteStation] = []
    @State private var showingLimitAlert = false
    
    private let maxFavorites = 20
    private let softLimit = 10
    
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
        ZStack {
            // Background
            Color.black
                .ignoresSafeArea()
            
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
                        // Current favorites section
                        if !favoriteStations.isEmpty {
                            VStack(alignment: .leading, spacing: 12) {
                                HStack {
                                    Text("Your current favorites")
                                        .font(.headline)
                                        .fontWeight(.semibold)
                                        .foregroundColor(.white)
                                    Spacer()
                                }
                                .padding(.horizontal, 20)
                                
                                ForEach(favoriteStations.sorted(by: { $0.lastUsed > $1.lastUsed })) { station in
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
                .refreshable {
                    loadFavoriteStations()
                }
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
        
        // Don't allow removing NY Penn Station (it should always be favorited)
        if code == "NY" && isCurrentlyFavorite {
            UINotificationFeedbackGenerator().notificationOccurred(.error)
            return
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