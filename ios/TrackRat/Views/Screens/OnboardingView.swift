import SwiftUI
import UserNotifications

struct OnboardingView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var subscriptionService = SubscriptionService.shared

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
    @State private var showBetaSystems = false
    @State private var showingPaywall = false
    @State private var showingTrainSystemSettings = false
    @State private var showConfetti = false
    @State private var welcomeTextScale: CGFloat = 0.8

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
                ZStack {
                    VStack(spacing: 0) {
                        // Custom header when editing favorites (pushed onto NavigationStack)
                        if isRepeating {
                            TrackRatNavigationHeader(
                                title: "Edit Favorites",
                                showBackButton: true,
                                onBackAction: { dismiss() }
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

                    // Celebration confetti overlay (first-time onboarding only)
                    if !isRepeating {
                        ConfettiView(isActive: showConfetti)
                            .ignoresSafeArea()
                    }
                }
                .onAppear {
                    // Trigger confetti and welcome animation on first onboarding
                    if !isRepeating && !showConfetti {
                        showConfetti = true
                        UINotificationFeedbackGenerator().notificationOccurred(.success)
                        withAnimation(.spring(response: 0.5, dampingFraction: 0.6)) {
                            welcomeTextScale = 1.0
                        }
                    }
                }
            }
        }
        .navigationBarHidden(true)
        .onAppear {
            // Only clear data on truly fresh onboarding (never completed before),
            // not when editing favorites or re-onboarding due to corrupt state
            if !isRepeating && !hasCompletedOnboarding {
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
                onInactiveStationSelected: { _ in
                    showStationPicker = false

                    if isRepeating {
                        showingTrainSystemSettings = true
                    } else {
                        showSystemSelection = true
                    }
                },
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
        .sheet(isPresented: $showingPaywall) {
            PaywallView(context: .trainSystems)
        }
        .sheet(isPresented: $showingTrainSystemSettings) {
            SettingsView(editTrainSystems: true)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
    }

    // MARK: - Train System Selection

    private func systemSelectionView() -> some View {
        VStack(spacing: 32) {
            Spacer()

            // Header
            VStack(spacing: 8) {
                Text("Which transit system\ndo you use the most?")
                    .font(.largeTitle)
                    .fontWeight(.bold)
                    .foregroundColor(.white)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
                    .minimumScaleFactor(0.7)
            }

            // System selection cards
            VStack(spacing: 12) {
                let sortedSystems = TrainSystem.allCases.sorted { $0.displayName < $1.displayName }
                let mainSystems = sortedSystems.filter { !$0.isBeta }
                let betaSystems = sortedSystems.filter { $0.isBeta }

                ForEach(mainSystems, id: \.self) { system in
                    SystemSelectionCard(
                        system: system,
                        isSelected: false,
                        showCheckmark: false,
                        onTap: {
                            appState.selectSystem(system)
                            UIImpactFeedbackGenerator(style: .medium).impactOccurred()

                            withAnimation(.easeInOut(duration: 0.3)) {
                                showSystemSelection = false
                            }
                        }
                    )
                }

                // Collapsible beta systems section
                DisclosureGroup(isExpanded: $showBetaSystems) {
                    ForEach(betaSystems, id: \.self) { system in
                        SystemSelectionCard(
                            system: system,
                            isSelected: false,
                            showCheckmark: false,
                            onTap: {
                                appState.selectSystem(system)
                                UIImpactFeedbackGenerator(style: .medium).impactOccurred()

                                withAnimation(.easeInOut(duration: 0.3)) {
                                    showSystemSelection = false
                                }
                            }
                        )
                    }
                } label: {
                    HStack(spacing: 6) {
                        Text("Additional Systems")
                            .font(.headline)
                            .foregroundColor(.white.opacity(0.7))
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
                .tint(.white.opacity(0.5))
            }
            .padding(.horizontal, 20)

            Spacer()

            Text("You can always update this later")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.5))
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
                    .scaleEffect(isRepeating ? 1.0 : welcomeTextScale)
                
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

            // Request notification permissions now that onboarding is done
            Task {
                let _ = try? await UNUserNotificationCenter.current()
                    .requestAuthorization(options: [.alert, .sound, .badge])
                await MainActor.run {
                    UIApplication.shared.registerForRemoteNotifications()
                }
            }
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
    var showCheckmark: Bool = true
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 12) {
                // System info
                HStack(spacing: 6) {
                    SystemPill(system: system, size: 22)
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

                Spacer()

                if showCheckmark {
                    // Selection indicator
                    Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                        .font(.title2)
                        .foregroundColor(isSelected ? .orange : .white.opacity(0.3))
                } else {
                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.5))
                }
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

#Preview {
    OnboardingView()
        .environmentObject(AppState())
}
