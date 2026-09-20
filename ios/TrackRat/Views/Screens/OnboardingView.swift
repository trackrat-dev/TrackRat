import CoreLocation
import SwiftUI

struct OnboardingView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var locationService = LocationService.shared

    @State private var homeStation: Station? = nil
    @State private var workStation: Station? = nil
    @State private var otherFavorites: [Station] = []
    @State private var showStationPicker = false
    @State private var isPickingOtherStation = false
    @State private var stationBeingEdited: StationType? = nil
    @State private var hasLoadedExistingStations = false
    @State private var isCompletingOnboarding = false
    @State private var hasClearedPreviousData = false
    @State private var showSystemSelection = true
    @State private var showingTrainSystemSettings = false
    @State private var showConfetti = false
    @State private var welcomeTextScale: CGFloat = 0.8
    @State private var suggestedSystem: TrainSystem? = nil
    @State private var locationMessage: String? = nil

    private enum StationType {
        case home, work
    }

    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false

    let isRepeating: Bool

    init(isRepeating: Bool = false) {
        self.isRepeating = isRepeating
    }

    /// True once the user has picked at least one station worth saving.
    private var hasStationSelection: Bool {
        homeStation != nil || workStation != nil || !otherFavorites.isEmpty
    }

    var body: some View {
        ZStack {
            // Background - clear when editing favorites to let sheet material show through
            if isRepeating {
                Color.clear
                    .ignoresSafeArea()
            } else {
                TrackRatTheme.Colors.surface
                    .ignoresSafeArea()
            }

            if showSystemSelection && !isRepeating {
                // Show train system selection first (only on first onboarding)
                systemSelectionView()
            } else {
                // Show station selection after system selection
                ZStack {
                    VStack(spacing: 0) {
                        // Editing favorites dismisses; first-run setup steps back
                        // to the system picker rather than out of onboarding.
                        if isRepeating {
                            TrackRatNavigationHeader(
                                title: "Edit Favorites",
                                showBackButton: true,
                                onBackAction: { dismiss() }
                            )
                        } else {
                            TrackRatNavigationHeader(
                                title: "Step 2 of 2",
                                showBackButton: true,
                                showCloseButton: false,
                                onBackAction: {
                                    withAnimation(.easeInOut(duration: 0.3)) {
                                        showSystemSelection = true
                                    }
                                }
                            )
                        }

                        // Station selection content
                        stationSetupView()

                        // Save / skip
                        VStack(spacing: 12) {
                            Button("Continue") {
                                completeOnboarding()
                            }
                            .font(.headline)
                            .foregroundColor(.white)
                            .frame(height: 50)
                            .frame(minWidth: 160)
                            .background(canContinue ? TrackRatTheme.Colors.accent : TrackRatTheme.Colors.surfaceCard)
                            .cornerRadius(TrackRatTheme.CornerRadius.md)
                            .buttonStyle(.plain)
                            .disabled(!canContinue)

                            if !isRepeating {
                                Button("Skip for now") {
                                    completeOnboarding(skipped: true)
                                }
                                .font(.subheadline)
                                .foregroundColor(TrackRatTheme.Colors.onSurfaceTertiary)
                                .buttonStyle(.plain)
                                .disabled(isCompletingOnboarding)
                            }
                        }
                        .padding(.horizontal, 20)
                        .padding(.bottom, 32)
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
        .onChange(of: locationService.fix) { _, fix in
            applyLocationFix(fix)
        }
        .onChange(of: locationService.authorizationStatus) { _, status in
            if status == .denied || status == .restricted {
                locationMessage = "Location is off — pick your system below."
            }
        }
        .sheet(isPresented: $showStationPicker) {
            StationPickerSheet(
                selectedStation: .constant(currentSelection),
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
                    assign(station)
                    showStationPicker = false
                }
            )
        }
        .sheet(isPresented: $showingTrainSystemSettings) {
            SettingsView(editTrainSystems: true)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
    }

    /// Editing favorites can legitimately clear every station, so only first-run
    /// setup requires a selection before continuing.
    private var canContinue: Bool {
        !isCompletingOnboarding && (isRepeating || hasStationSelection)
    }

    // MARK: - Train System Selection

    private func systemSelectionView() -> some View {
        VStack(spacing: 20) {
            // Header
            VStack(spacing: 8) {
                Text("Step 1 of 2")
                    .font(TrackRatTheme.Typography.caption)
                    .foregroundColor(TrackRatTheme.Colors.onSurfaceTertiary)

                Text("Which transit system\ndo you use the most?")
                    .font(.largeTitle)
                    .fontWeight(.bold)
                    .foregroundColor(TrackRatTheme.Colors.onSurface)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
                    .minimumScaleFactor(0.7)
            }
            .padding(.top, 40)

            locationSuggestion()

            // System selection cards
            ScrollView {
                VStack(spacing: 12) {
                    ForEach(Self.orderedSystems(suggested: suggestedSystem), id: \.self) { system in
                        SystemSelectionCard(
                            system: system,
                            isSelected: false,
                            showCheckmark: false,
                            caption: system == suggestedSystem ? "Closest to you" : nil,
                            onTap: {
                                appState.selectSystem(system)
                                dropStationsOutsideSelection()
                                UIImpactFeedbackGenerator(style: .medium).impactOccurred()

                                withAnimation(.easeInOut(duration: 0.3)) {
                                    showSystemSelection = false
                                }
                            }
                        )
                    }
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 8)
            }

            Text("You can always update this later")
                .font(.subheadline)
                .foregroundColor(TrackRatTheme.Colors.onSurfaceTertiary)
                .padding(.bottom, 32)
        }
    }

    /// Every selectable system in alphabetical order, with the one nearest the
    /// rider promoted to the top. Offering all of them matters: a rider whose
    /// system is missing from setup has no way to finish it.
    static func orderedSystems(suggested: TrainSystem?) -> [TrainSystem] {
        let systems = TrainSystem.availableCases.sorted { $0.displayName < $1.displayName }
        guard let suggested, systems.contains(suggested) else { return systems }
        return [suggested] + systems.filter { $0 != suggested }
    }

    @ViewBuilder
    private func locationSuggestion() -> some View {
        if locationService.isLocating {
            HStack(spacing: 8) {
                ProgressView()
                    .tint(TrackRatTheme.Colors.onSurface)
                Text("Finding the systems near you…")
                    .font(.subheadline)
                    .foregroundColor(TrackRatTheme.Colors.onSurfaceSecondary)
            }
        } else if let locationMessage {
            Text(locationMessage)
                .font(.subheadline)
                .foregroundColor(TrackRatTheme.Colors.onSurfaceSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 20)
        } else if suggestedSystem == nil && locationService.canRequestFix {
            Button {
                locationService.requestFix()
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: "location.fill")
                    Text("Use my location")
                }
                .font(.subheadline.weight(.medium))
                .foregroundColor(TrackRatTheme.Colors.accent)
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .background(TrackRatTheme.Colors.surfaceCard)
                .cornerRadius(TrackRatTheme.CornerRadius.sm)
            }
            .buttonStyle(.plain)
        }
    }

    // MARK: - Station Setup

    private func stationSetupView() -> some View {
        VStack(spacing: 28) {
            Spacer()

            // Title and the reason any of this is worth doing
            VStack(spacing: 12) {
                if !isRepeating {
                    Text("Welcome!")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                        .foregroundColor(TrackRatTheme.Colors.onSurface)
                        .scaleEffect(welcomeTextScale)
                }

                Text("Set your home and work stations and TrackRat\nhas your commute ready when you open the app")
                    .font(.body)
                    .foregroundColor(TrackRatTheme.Colors.onSurfaceSecondary)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
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
                            .foregroundColor(TrackRatTheme.Colors.accent)
                        Text("Favorites")
                            .font(.headline)
                            .foregroundColor(TrackRatTheme.Colors.onSurface)
                        Spacer()
                    }

                    ForEach(otherFavorites, id: \.code) { station in
                        HStack {
                            Text(station.name)
                                .foregroundColor(TrackRatTheme.Colors.onSurface)
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
                                Text(otherFavorites.isEmpty ? "Add Station" : "Add Another")
                            }
                            .foregroundColor(TrackRatTheme.Colors.accent)
                            .frame(height: 44)
                            .frame(maxWidth: .infinity)
                            .background(TrackRatTheme.Colors.surfaceCard)
                            .cornerRadius(TrackRatTheme.CornerRadius.sm)
                        }
                        .buttonStyle(.plain)
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

    // MARK: - Station Selection Helpers

    /// The station currently shown as selected in the picker.
    private var currentSelection: Station? {
        switch stationBeingEdited {
        case .home: return homeStation
        case .work: return workStation
        case nil: return nil
        }
    }

    private func assign(_ station: Station) {
        switch stationBeingEdited {
        case .home:
            homeStation = station
        case .work:
            workStation = station
        case nil:
            guard isPickingOtherStation,
                  !otherFavorites.contains(where: { $0.code == station.code }) else { return }
            otherFavorites.append(station)
        }
    }

    /// Station that can't be picked for the slot being edited (home ≠ work).
    private func disabledStation(for type: StationType?) -> Station? {
        switch type {
        case .home: return workStation
        case .work: return homeStation
        case nil: return nil
        }
    }

    /// Drops selections the given systems don't serve.
    ///
    /// Stepping back to the system picker and choosing a different system would
    /// otherwise carry stations forward that the picker itself no longer offers,
    /// and save them under a system that doesn't run there.
    static func stationsServed(
        by systems: Set<TrainSystem>,
        home: Station?,
        work: Station?,
        favorites: [Station]
    ) -> (home: Station?, work: Station?, favorites: [Station]) {
        func isServed(_ station: Station) -> Bool {
            Stations.isStationVisible(station.code, withSystems: systems)
        }

        return (
            home: home.flatMap { isServed($0) ? $0 : nil },
            work: work.flatMap { isServed($0) ? $0 : nil },
            favorites: favorites.filter(isServed)
        )
    }

    private func dropStationsOutsideSelection() {
        let served = Self.stationsServed(
            by: appState.selectedSystems,
            home: homeStation,
            work: workStation,
            favorites: otherFavorites
        )
        homeStation = served.home
        workStation = served.work
        otherFavorites = served.favorites
    }

    private func applyLocationFix(_ fix: LocationFix?) {
        guard let fix else { return }

        suggestedSystem = Stations.nearestSystem(to: fix.coordinate)
        locationMessage = suggestedSystem == nil
            ? "No systems TrackRat covers are near you — pick one below."
            : nil
    }

    // MARK: - Persistence

    private func clearAllPreviousData() {
        // Only clear once per onboarding session
        guard !hasClearedPreviousData else { return }
        hasClearedPreviousData = true

        Log.info("Clearing all previous data for fresh onboarding")
        clearPersistedData()

        // Clear local state variables to ensure fresh start
        homeStation = nil
        workStation = nil
        otherFavorites = []
    }

    /// Clears persisted stations without touching the current UI selections, so
    /// saving can write the user's new choices over a clean slate.
    private func clearPersistedData() {
        RatSenseService.shared.clearAllData()

        for station in Array(appState.favoriteStations) {
            appState.removeFavoriteStation(code: station.id)
        }

        // Force reload favorites to ensure UI reflects cleared state
        appState.loadFavoriteStations()
    }

    private func loadExistingStationsIfNeeded() {
        // Pre-fill whenever the user has been through setup before: editing
        // favorites, and the self-heal path where onboarding reappears because
        // the system selection was lost (see TrackRatApp.shouldShowOnboarding).
        guard isRepeating || hasCompletedOnboarding, !hasLoadedExistingStations else { return }
        hasLoadedExistingStations = true

        let ratSense = RatSenseService.shared
        let homeCode = ratSense.getHomeStation()
        let workCode = ratSense.getWorkStation()

        if let homeCode {
            homeStation = Station(code: homeCode, name: Stations.displayName(for: homeCode))
        }
        if let workCode {
            workStation = Station(code: workCode, name: Stations.displayName(for: workCode))
        }
        otherFavorites = appState.favoriteStations
            .filter { $0.id != homeCode && $0.id != workCode }
            .map { Station(code: $0.id, name: $0.name) }

        Log.debug("Loaded existing stations: home=\(homeCode ?? "none"), work=\(workCode ?? "none"), favorites=\(otherFavorites.count)")
    }

    private func completeOnboarding(skipped: Bool = false) {
        // Prevent double-taps
        guard !isCompletingOnboarding else { return }
        isCompletingOnboarding = true

        // When the screen was pre-filled from storage, it is now the source of
        // truth — clear the old rows so removals actually stick.
        if hasLoadedExistingStations {
            clearPersistedData()
        }

        // Save selected stations to RatSense first to ensure persistence
        if let home = homeStation {
            RatSenseService.shared.setHomeStation(home.code)
            appState.addFavoriteStation(code: home.code, name: home.name)
        }
        if let work = workStation {
            RatSenseService.shared.setWorkStation(work.code)
            appState.addFavoriteStation(code: work.code, name: work.name)
        }
        for other in otherFavorites {
            appState.addFavoriteStation(code: other.code, name: other.name)
        }

        // Force immediate synchronization of favorites
        appState.loadFavoriteStations()
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()

        if !isRepeating {
            reportOnboardingOutcome(skipped: skipped)
        }

        Log.info("Onboarding completed (skipped: \(skipped), home: \(homeStation != nil), work: \(workStation != nil))")
        hasCompletedOnboarding = true
        dismiss()
    }

    /// Reports the shape of the finished setup so the drop-off can be measured.
    /// Deliberately carries no station codes — a home station says where someone
    /// lives — only whether each step was completed.
    private func reportOnboardingOutcome(skipped: Bool) {
        let systems = appState.selectedSystems.commaSeparated
        let homeSet = homeStation != nil
        let workSet = workStation != nil
        let favorites = otherFavorites.count
        let usedLocation = locationService.fix != nil

        Task {
            await APIService.shared.reportOnboardingCompleted(
                systems: systems,
                homeStationSet: homeSet,
                workStationSet: workSet,
                favoritesCount: favorites,
                usedLocation: usedLocation,
                skipped: skipped
            )
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
                    .foregroundColor(TrackRatTheme.Colors.accent)
                    .frame(width: 24)

                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.headline)
                        .foregroundColor(TrackRatTheme.Colors.onSurface)

                    if let selected = selectedStation {
                        Text(selected.name)
                            .font(.subheadline)
                            .foregroundColor(TrackRatTheme.Colors.accent)
                    } else {
                        Text("Select Station...")
                            .font(.subheadline)
                            .foregroundColor(TrackRatTheme.Colors.onSurfaceSecondary)
                    }

                    // Show warning if same as other station
                    if let disabled = isDisabledOption,
                       selectedStation?.code == disabled.code {
                        Text("⚠️ Same as \(title == "Home Station" ? "work" : "home") station")
                            .font(.caption)
                            .foregroundColor(TrackRatTheme.Colors.warning)
                    }
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .foregroundColor(TrackRatTheme.Colors.onSurfaceTertiary)
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
    var caption: String? = nil
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 12) {
                // System info
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        Text(system.displayName)
                            .font(.headline)
                            .foregroundColor(TrackRatTheme.Colors.onSurface)
                        if system.isBeta {
                            BetaPill()
                        }
                    }

                    if let caption {
                        Text(caption)
                            .font(.caption)
                            .foregroundColor(TrackRatTheme.Colors.accent)
                    }
                }

                Spacer()

                if showCheckmark {
                    // Selection indicator
                    Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                        .font(.title2)
                        .foregroundColor(isSelected ? TrackRatTheme.Colors.accent : .white.opacity(0.3))
                } else {
                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundColor(TrackRatTheme.Colors.onSurfaceTertiary)
                }
            }
            .padding()
            .background(Material.ultraThin)
            .cornerRadius(TrackRatTheme.CornerRadius.md)
            .overlay(
                RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                    .stroke(isSelected ? TrackRatTheme.Colors.accent.opacity(0.5) : Color.clear, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }
}

#Preview {
    OnboardingView()
        .environmentObject(AppState())
}
