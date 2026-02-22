import SwiftUI

struct OnboardingView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    
    @State private var homeStation: Station? = nil
    @State private var workStation: Station? = nil
    @State private var otherFavorites: [Station] = []
    @State private var searchText = ""
    @State private var showStationPicker = false
    @State private var isPickingOtherStation = false
    @State private var stationBeingEdited: StationType? = nil
    @State private var hasLoadedExistingStations = false
    @State private var isCompletingOnboarding = false
    @State private var hasClearedPreviousData = false
    @State private var showSystemSelection = true

    private enum StationType {
        case home, work
    }
    
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false

    let isRepeating: Bool

    init(isRepeating: Bool = false) {
        self.isRepeating = isRepeating
    }
    
    var body: some View {
        ZStack {
            // Background - clear when editing favorites to let sheet material show through
            if isRepeating {
                Color.clear
                    .ignoresSafeArea()
            } else {
                Color.black
                    .ignoresSafeArea()
            }

            if showSystemSelection && !isRepeating {
                // Show train system selection after video (only on first onboarding)
                systemSelectionView()
            } else {
                // Show station selection after system selection
                VStack(spacing: 0) {
                    // Custom header when editing favorites (pushed onto NavigationStack)
                    if isRepeating {
                        TrackRatNavigationHeader(
                            title: "Edit Favorites",
                            showBackButton: false,
                            showCloseButton: true
                        )
                    }

                    // Station selection content
                    welcomeAndSetupView()

                    // Continue/Skip button
                    VStack(spacing: 20) {
                        Button((homeStation != nil || workStation != nil) ? "Continue" : "Skip") {
                            if !isCompletingOnboarding {
                                completeOnboarding()
                            }
                        }
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(height: 50)
                        .frame(minWidth: 160)
                        .background(Color.orange)
                        .cornerRadius(TrackRatTheme.CornerRadius.md)
                        .buttonStyle(.plain)
                        .disabled(isCompletingOnboarding)
                    }
                    .padding(.horizontal, 20)
                    .padding(.bottom, 40)
                }
            }
        }
        .navigationBarHidden(true)
        .onAppear {
            // Only clear data on first onboarding, not when editing favorites
            if !isRepeating {
                clearAllPreviousData()
            }

            // Load existing stations for editing when repeating
            loadExistingStationsIfNeeded()
        }
        .sheet(isPresented: $showStationPicker) {
            StationPickerSheet(
                selectedStation: binding(for: stationBeingEdited),
                disabledStation: disabledStation(for: stationBeingEdited),
                selectedSystems: appState.selectedSystems,
                onStationSelected: { station in
                    // Explicitly handle station assignment with proper state update
                    DispatchQueue.main.async {
                        switch stationBeingEdited {
                        case .home:
                            self.homeStation = station
                        case .work:
                            self.workStation = station
                        case nil:
                            if isPickingOtherStation {
                                if !otherFavorites.contains(where: { $0.code == station.code }) {
                                    otherFavorites.append(station)
                                }
                            }
                        }
                        showStationPicker = false
                    }
                }
            )
        }
    }

    // MARK: - Train System Selection

    private func systemSelectionView() -> some View {
        VStack(spacing: 32) {
            Spacer()

            // Header
            Text("Which train systems\ndo you use?")
                .font(.largeTitle)
                .fontWeight(.bold)
                .foregroundColor(.white)
                .multilineTextAlignment(.center)

            // System selection cards
            VStack(spacing: 12) {
                ForEach(TrainSystem.allCases, id: \.self) { system in
                    SystemSelectionCard(
                        system: system,
                        isSelected: appState.isSystemSelected(system),
                        onTap: {
                            withAnimation(.easeInOut(duration: 0.2)) {
                                appState.toggleSystem(system)
                            }
                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        }
                    )
                }
            }
            .padding(.horizontal, 20)

            Spacer()

            // Continue button and helper text
            VStack(spacing: 12) {
                Button("Continue") {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        showSystemSelection = false
                    }
                    UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                }
                .font(.headline)
                .foregroundColor(.white)
                .frame(height: 50)
                .frame(minWidth: 160)
                .background(appState.selectedSystems.isEmpty ? Color.gray : Color.orange)
                .cornerRadius(TrackRatTheme.CornerRadius.md)
                .buttonStyle(.plain)
                .disabled(appState.selectedSystems.isEmpty)

                Text("Change later in Map → Layers")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.5))
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 40)
        }
    }

    // MARK: - Screen 1: Welcome + Station Setup
    private func welcomeAndSetupView() -> some View {
        VStack(spacing: 32) {
            Spacer()
            
            // Logo and title
            VStack(spacing: 16) {
                Text("Welcome!")
                    .font(.largeTitle)
                    .fontWeight(.bold)
                    .foregroundColor(.white)
                
                Text("Help us recommend routes by\nselecting your stations")
                    .font(.body)
                    .foregroundColor(.white.opacity(0.8))
                    .multilineTextAlignment(.center)
            }
            
            // Station selection cards
            VStack(spacing: 16) {
                // Home Station
                StationSelectionCard(
                    icon: "house.fill",
                    title: "Home Station",
                    selectedStation: homeStation,
                    isDisabledOption: workStation,  // Can't be same as work
                    onTap: {
                        isPickingOtherStation = false
                        stationBeingEdited = .home
                        showStationPicker = true
                    }
                )
                
                // Work Station
                StationSelectionCard(
                    icon: "building.2.fill",
                    title: "Work Station",
                    selectedStation: workStation,
                    isDisabledOption: homeStation,  // Can't be same as home
                    onTap: {
                        isPickingOtherStation = false
                        stationBeingEdited = .work
                        showStationPicker = true
                    }
                )
                
                // Other Favorites
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Image(systemName: "star.fill")
                            .foregroundColor(.orange)
                        Text("Favorites")
                            .font(.headline)
                            .foregroundColor(.white)
                        Spacer()
                    }
                    
                    if otherFavorites.isEmpty {
                        Button {
                            isPickingOtherStation = true
                            stationBeingEdited = nil
                            showStationPicker = true
                        } label: {
                            HStack {
                                Image(systemName: "plus")
                                Text("Add Station")
                            }
                            .foregroundColor(.orange)
                            .frame(height: 44)
                            .frame(maxWidth: .infinity)
                            .background(TrackRatTheme.Colors.surfaceCard)
                            .cornerRadius(TrackRatTheme.CornerRadius.sm)
                        }
                        .buttonStyle(.plain)
                    } else {
                        ForEach(otherFavorites, id: \.code) { station in
                            HStack {
                                Text(station.name)
                                    .foregroundColor(.white)
                                Spacer()
                                Button {
                                    otherFavorites.removeAll { $0.code == station.code }
                                } label: {
                                    Image(systemName: "xmark.circle.fill")
                                        .foregroundColor(.gray)
                                }
                                .buttonStyle(.plain)
                            }
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(TrackRatTheme.Colors.surfaceCard)
                            .cornerRadius(TrackRatTheme.CornerRadius.sm)
                        }

                        if otherFavorites.count < 3 {
                            Button {
                                isPickingOtherStation = true
                                stationBeingEdited = nil
                                showStationPicker = true
                            } label: {
                                HStack {
                                    Image(systemName: "plus")
                                    Text("Add Another")
                                }
                                .foregroundColor(.orange)
                                .frame(height: 44)
                                .frame(maxWidth: .infinity)
                                .background(TrackRatTheme.Colors.surfaceCard)
                                .cornerRadius(TrackRatTheme.CornerRadius.sm)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
                .padding()
                .background(Material.ultraThin)
                .cornerRadius(TrackRatTheme.CornerRadius.md)
            }

            Spacer()
        }
        .padding(.horizontal, 20)
    }

    // MARK: - Helper Functions

    private func clearAllPreviousData() {
        // Only clear once per onboarding session
        guard !hasClearedPreviousData else {
            print("🧹 OnboardingView: Previous data already cleared, skipping")
            return
        }

        hasClearedPreviousData = true
        print("🧹 OnboardingView: Clearing all previous data for fresh start")

        // Clear RatSense data (home/work stations and all history)
        let ratSense = RatSenseService.shared
        ratSense.clearAllData()

        // Clear all favorite stations from AppState
        let existingFavorites = Array(appState.favoriteStations)
        for station in existingFavorites {
            appState.removeFavoriteStation(code: station.id)
        }

        // Force reload favorites to ensure UI reflects cleared state
        appState.loadFavoriteStations()

        // Clear local state variables to ensure fresh start
        homeStation = nil
        workStation = nil
        otherFavorites = []

        print("🧹 OnboardingView: All previous data cleared successfully")
        print("🧹 Cleared: RatSense data, AppState favorites, local state")
    }

    private func clearPersistedData() {
        // This function only clears persisted data, not the UI state
        // Used when editing favorites to preserve user's new selections
        print("🧹 OnboardingView: Clearing persisted data only (preserving UI selections)")

        // Clear RatSense data (home/work stations and all history)
        let ratSense = RatSenseService.shared
        ratSense.clearAllData()

        // Clear all favorite stations from AppState
        let existingFavorites = Array(appState.favoriteStations)
        for station in existingFavorites {
            appState.removeFavoriteStation(code: station.id)
        }

        // Force reload favorites to ensure UI reflects cleared state
        appState.loadFavoriteStations()

        print("🧹 OnboardingView: Persisted data cleared, UI selections preserved")
        print("🧹 Current selections: home=\(homeStation?.code ?? "none"), work=\(workStation?.code ?? "none"), others=\(otherFavorites.count)")
    }
    
    private func loadExistingStationsIfNeeded() {
        // Only load existing stations when repeating (editing favorites)
        guard isRepeating && !hasLoadedExistingStations else {
            print("🔄 OnboardingView: Skipping existing station load (repeating=\(isRepeating), loaded=\(hasLoadedExistingStations))")
            return
        }

        hasLoadedExistingStations = true
        let ratSense = RatSenseService.shared

        print("🔄 OnboardingView: Loading existing stations for editing")

        // Load home station if set
        if let homeCode = ratSense.getHomeStation() {
            let homeName = Stations.displayName(for: homeCode)
            print("🏠 OnboardingView: Loading home station: \(homeCode)")
            DispatchQueue.main.async {
                self.homeStation = Station(code: homeCode, name: homeName)
            }
        }

        // Load work station if set
        if let workCode = ratSense.getWorkStation() {
            let workName = Stations.displayName(for: workCode)
            print("🏢 OnboardingView: Loading work station: \(workCode)")
            DispatchQueue.main.async {
                self.workStation = Station(code: workCode, name: workName)
            }
        }

        // Load other favorites (excluding home and work)
        let homeCode = ratSense.getHomeStation()
        let workCode = ratSense.getWorkStation()
        let otherFavs = appState.favoriteStations
            .filter { $0.id != homeCode && $0.id != workCode }
            .map { Station(code: $0.id, name: $0.name) }

        if !otherFavs.isEmpty {
            print("⭐ OnboardingView: Loading \(otherFavs.count) other favorite stations")
            DispatchQueue.main.async {
                self.otherFavorites = otherFavs
            }
        }

        print("🔄 OnboardingView: Existing station load completed")
    }
    
    private func completeOnboarding() {
        // Prevent double-taps
        guard !isCompletingOnboarding else { return }
        isCompletingOnboarding = true

        print("🎯 OnboardingView: Completing onboarding with selected stations")

        // When repeating (editing favorites), clear only persisted data before saving new selections
        // This preserves the UI state (user's new selections)
        if isRepeating {
            print("🔄 OnboardingView: Editing favorites - clearing old persisted data")
            clearPersistedData()
        }

        // Save selected stations as favorites
        // Save to RatSense first to ensure persistence
        if let home = homeStation {
            print("🏠 Setting home station: \(home.code) - \(home.name)")
            RatSenseService.shared.setHomeStation(home.code)
            appState.addFavoriteStation(code: home.code, name: home.name)
        } else {
            print("🏠 No home station selected")
        }

        if let work = workStation {
            print("🏢 Setting work station: \(work.code) - \(work.name)")
            RatSenseService.shared.setWorkStation(work.code)
            appState.addFavoriteStation(code: work.code, name: work.name)
        } else {
            print("🏢 No work station selected")
        }

        for other in otherFavorites {
            print("⭐ Adding other favorite: \(other.code) - \(other.name)")
            appState.addFavoriteStation(code: other.code, name: other.name)
        }

        // Force immediate synchronization of favorites
        appState.loadFavoriteStations()

        // Provide haptic feedback
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()

        // Mark onboarding as complete only after all data is saved
        // Use a slight delay to ensure all state updates are processed
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            print("✅ OnboardingView: Onboarding completed successfully")
            self.hasCompletedOnboarding = true
            self.dismiss()
        }
    }
    
    // Helper method for cleaner binding
    private func binding(for type: StationType?) -> Binding<Station?> {
        switch type {
        case .home:
            return Binding(
                get: { self.homeStation },
                set: { newValue in
                    // Explicitly update the state with proper transaction
                    // @State already handles UI updates, but we ensure main queue
                    DispatchQueue.main.async {
                        self.homeStation = newValue
                    }
                }
            )
        case .work:
            return Binding(
                get: { self.workStation },
                set: { newValue in
                    // Explicitly update the state with proper transaction
                    // @State already handles UI updates, but we ensure main queue
                    DispatchQueue.main.async {
                        self.workStation = newValue
                    }
                }
            )
        case nil:
            return .constant(nil)
        }
    }
    
    // Helper method to get disabled station
    private func disabledStation(for type: StationType?) -> Station? {
        switch type {
        case .home:
            return workStation
        case .work:
            return homeStation
        case nil:
            return nil
        }
    }
}

// MARK: - Supporting Views
struct StationSelectionCard: View {
    let icon: String
    let title: String
    let selectedStation: Station?
    let isDisabledOption: Station?  // Station that can't be selected (e.g., home can't be work)
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 16) {
                Image(systemName: icon)
                    .foregroundColor(.orange)
                    .frame(width: 24)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.headline)
                        .foregroundColor(.white)
                    
                    if let selected = selectedStation {
                        Text(selected.name)
                            .font(.subheadline)
                            .foregroundColor(.orange)
                    } else {
                        Text("Select Station...")
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.6))
                    }
                    
                    // Show warning if same as other station
                    if let disabled = isDisabledOption,
                       selectedStation?.code == disabled.code {
                        Text("⚠️ Same as \(title == "Home Station" ? "work" : "home") station")
                            .font(.caption)
                            .foregroundColor(.yellow)
                    }
                }
                
                Spacer()
                
                Image(systemName: "chevron.right")
                    .foregroundColor(.white.opacity(0.5))
                    .font(.caption)
            }
            .padding()
            .background(Material.ultraThin)
            .cornerRadius(TrackRatTheme.CornerRadius.md)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - System Selection Card
struct SystemSelectionCard: View {
    let system: TrainSystem
    let isSelected: Bool
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 16) {
                // System icon
                Image(systemName: system.icon)
                    .font(.title2)
                    .foregroundColor(isSelected ? .orange : .white.opacity(0.5))
                    .frame(width: 32)

                // System info
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        Text(system.displayName)
                            .font(.headline)
                            .foregroundColor(.white)
                        if system.isBeta {
                            Text("beta")
                                .font(.caption2)
                                .fontWeight(.semibold)
                                .foregroundColor(.orange)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(
                                    Capsule().fill(.orange.opacity(0.2))
                                )
                        }
                    }

                    Text(system.description)
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))
                }

                Spacer()

                // Selection indicator
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.title2)
                    .foregroundColor(isSelected ? .orange : .white.opacity(0.3))
            }
            .padding()
            .background(Material.ultraThin)
            .cornerRadius(TrackRatTheme.CornerRadius.md)
            .overlay(
                RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                    .stroke(isSelected ? Color.orange.opacity(0.5) : Color.clear, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }
}

struct FavoriteStationRow: View {
    let stationCode: String
    let stationName: String
    let isFavorite: Bool
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(stationName)
                    .font(.headline)
                    .foregroundColor(.white)
                Text(stationCode)
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.7))
            }
            Spacer()
            Image(systemName: isFavorite ? "heart.fill" : "heart")
                .foregroundColor(.orange)
                .font(TrackRatTheme.IconSize.medium)
        }
        .padding()
        .background(Material.ultraThin)
        .cornerRadius(TrackRatTheme.CornerRadius.md)
    }
}

struct FeatureCard: View {
    let icon: String
    let title: String
    let description: String
    
    var body: some View {
        HStack(alignment: .top, spacing: 16) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(.orange)
                .frame(width: 24, height: 24)
            
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.headline)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                
            }
            
            Spacer()
        }
        .padding()
        .background(Material.ultraThin)
        .cornerRadius(TrackRatTheme.CornerRadius.md)
    }
}

// MARK: - Station Model
struct Station: Identifiable, Equatable {
    let id = UUID()
    let code: String
    let name: String
}

// MARK: - Station Picker Sheet
struct StationPickerSheet: View {
    @Binding var selectedStation: Station?
    let disabledStation: Station?  // Station that should be shown as disabled
    var selectedSystems: Set<TrainSystem>? = nil  // Optional: filter stations by selected systems
    let onStationSelected: (Station) -> Void
    @Environment(\.dismiss) private var dismiss

    @State private var searchText = ""

    /// All visible stations filtered by selected systems.
    private var visibleStations: [Station] {
        var allStations = Stations.all.compactMap { name -> Station? in
            guard let code = Stations.getStationCode(name) else { return nil }
            return Station(code: code, name: name)
        }

        if let systems = selectedSystems {
            allStations = allStations.filter { station in
                Stations.isStationVisible(station.code, withSystems: systems)
            }
        }

        return allStations
    }

    /// Search results using ranked search (prefix > substring).
    private var searchResults: [Station] {
        guard !searchText.isEmpty else { return [] }
        let q = searchText.lowercased()
        let stations = visibleStations
        let prefixMatches = stations.filter { $0.name.lowercased().hasPrefix(q) }
        let substringMatches = stations.filter {
            !$0.name.lowercased().hasPrefix(q) &&
            ($0.name.localizedCaseInsensitiveContains(searchText) ||
             $0.code.localizedCaseInsensitiveContains(searchText))
        }
        return Array((prefixMatches + substringMatches).prefix(20))
    }

    /// Stations grouped by system for the browse view (when search is empty).
    private var groupedStations: [(system: String, stations: [Station])] {
        let systemOrder: [(raw: String, label: String)] = [
            ("NJT", "NJ Transit"),
            ("AMTRAK", "Amtrak"),
            ("PATH", "PATH"),
            ("PATCO", "PATCO"),
            ("LIRR", "LIRR"),
            ("MNR", "Metro-North"),
            ("SUBWAY", "NYC Subway"),
        ]

        let stations = visibleStations
        var groups: [(system: String, stations: [Station])] = []

        // Pinned section first
        let pinnedCodes = ["NY", "GCT", "PWC", "HB", "S127", "JAM"]
        let pinned = pinnedCodes.compactMap { code in stations.first { $0.code == code } }
        if !pinned.isEmpty {
            groups.append((system: "Popular", stations: pinned))
        }

        // Group remaining by system
        let pinnedSet = Set(pinnedCodes)
        for (raw, label) in systemOrder {
            let systemStations = stations
                .filter { !pinnedSet.contains($0.code) && Stations.systemStringsForStation($0.code).contains(raw) }
                .sorted { $0.name < $1.name }
            if !systemStations.isEmpty {
                groups.append((system: label, stations: systemStations))
            }
        }

        return groups
    }

    @ViewBuilder
    private func stationRow(_ station: Station) -> some View {
        let isDisabled = disabledStation?.code == station.code

        Button {
            if !isDisabled {
                selectedStation = station
                onStationSelected(station)
            }
        } label: {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(station.name)
                        .font(.headline)
                        .foregroundColor(isDisabled ? .white.opacity(0.4) : .white)

                    if isDisabled {
                        Text("Already selected")
                            .font(.caption)
                            .foregroundColor(.orange)
                    }
                }
                Spacer()

                if station.code == selectedStation?.code {
                    Image(systemName: "checkmark")
                        .foregroundColor(.orange)
                }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(PlainButtonStyle())
        .disabled(isDisabled)
        .listRowBackground(Color.clear)
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Search bar
                HStack(spacing: 10) {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(.white.opacity(0.5))
                    TextField("Search stations...", text: $searchText)
                        .foregroundColor(.white)
                        .autocorrectionDisabled(true)
                        .textInputAutocapitalization(.never)
                }
                .padding(12)
                .background(
                    RoundedRectangle(cornerRadius: 10)
                        .fill(.ultraThinMaterial)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 10)
                        .stroke(Color.white.opacity(0.2), lineWidth: 1)
                )
                .padding()

                if searchText.isEmpty {
                    List {
                        ForEach(groupedStations, id: \.system) { group in
                            Section {
                                ForEach(group.stations) { station in
                                    stationRow(station)
                                }
                            } header: {
                                Text(group.system)
                                    .font(.caption.weight(.semibold))
                                    .foregroundColor(.white.opacity(0.6))
                                    .textCase(nil)
                            }
                        }
                    }
                    .listStyle(.plain)
                    .scrollContentBackground(.hidden)
                } else {
                    List(searchResults) { station in
                        stationRow(station)
                    }
                    .listStyle(.plain)
                    .scrollContentBackground(.hidden)
                }
            }
            .background(.ultraThinMaterial)
            .navigationTitle("Select Station")
            .navigationBarTitleDisplayMode(.inline)
            .navigationBarBackButtonHidden()
            .toolbarBackground(.ultraThinMaterial, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Cancel") {
                        dismiss()
                    }
                    .foregroundColor(.white)
                }
            }
        }
        .preferredColorScheme(.dark)
    }
}

#Preview {
    OnboardingView()
        .environmentObject(AppState())
}
