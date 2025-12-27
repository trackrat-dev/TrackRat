import SwiftUI

enum TrainValidationState {
    case unknown        // Initial state, no validation attempted
    case validating     // Currently checking if train exists
    case found          // Train exists and can be accessed
    case notFound       // Train does not exist
}

struct TripSelectionView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.openURL) private var openURL
    @State private var searchText = ""
    @State private var isSearching = false
    @State private var isNavigatingToProfile = false
    @FocusState private var searchFieldFocused: Bool
    @StateObject private var liveActivityService = LiveActivityService.shared
    @StateObject private var ratSenseService = RatSenseService.shared
    @State private var searchTask: Task<Void, Never>?

    // Train validation state - now supports multiple train results
    @State private var trainValidationStates: [String: TrainValidationState] = [:]
    @State private var validationTasks: [String: Task<Void, Never>] = [:]

    // Get favorite stations
    private var favoriteStations: [FavoriteStation] {
        return appState.favoriteStations
    }
    
    private var searchResults: (stations: [String], trainNumbers: [String]) {
        let query = searchText.trimmingCharacters(in: .whitespaces)
        
        // Always search stations
        let stationResults = Stations.search(query)
        
        // Generate potential train numbers for dual search
        let trainNumbers = getPotentialTrainNumbers(query)
        
        return (stations: stationResults, trainNumbers: trainNumbers)
    }
    
    // Generate potential train numbers for both NJT and Amtrak
    private func getPotentialTrainNumbers(_ input: String) -> [String] {
        let trimmed = input.trimmingCharacters(in: .whitespaces).uppercased()
        
        // If input already has "A" prefix, only search for that
        if trimmed.hasPrefix("A") && trimmed.count >= 3 {
            let remainder = String(trimmed.dropFirst())
            if remainder.allSatisfy(\.isNumber) {
                return [trimmed]
            }
        }
        
        // If input is numeric, search for both NJT and Amtrak variants
        if trimmed.count >= 2 && trimmed.allSatisfy(\.isNumber) {
            return [trimmed, "A\(trimmed)"]
        }
        
        return []
    }
    
    
    
    var body: some View {
        // Native sheet handles scrolling automatically
        ScrollView {
            VStack(spacing: 8) {
                    // Rat Sense suggestion at the top
                    if let suggestion = ratSenseService.suggestedJourney, !liveActivityService.isActivityActive, !isSearching, !isNavigatingToProfile {
                        Button {
                            selectRatSenseSuggestion(suggestion)
                        } label: {
                            Text("🐀✨ \(suggestion.fromStationName) to \(suggestion.toStationName)")
                                .font(.system(size: 14, weight: .medium))
                                .foregroundColor(.white)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 12)
                                .background(
                                    RoundedRectangle(cornerRadius: 10)
                                        .fill(Color.orange.opacity(0.3))
                                        .overlay(
                                            RoundedRectangle(cornerRadius: 10)
                                                .stroke(Color.orange.opacity(0.6), lineWidth: 1.5)
                                        )
                                )
                        }
                        .padding(.horizontal)
                        .padding(.top, 20)
                        .padding(.bottom, 8)
                    }

                    // Top title
                Text("Where would you like to leave from?")
                    .font(.system(size: 26, weight: .semibold))
                    .foregroundColor(.white)
                    .onAppear {
                        print("🎯 TripSelectionView title text appeared!")
                    }
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity)
                .padding(.horizontal)
                .padding(.top, (ratSenseService.suggestedJourney != nil && !liveActivityService.isActivityActive && !isSearching && !isNavigatingToProfile) ? 8 : 28)
                
                // Search results and content container
                VStack(alignment: .leading, spacing: 16) {
                    
                    // Search field with profile icon
                    HStack {
                        Image(systemName: "magnifyingglass")
                            .foregroundColor(.white.opacity(0.6))
                        
                        TextField("Search stations or train number", text: $searchText)
                            .foregroundColor(.white)
                            .focused($searchFieldFocused)
                            .autocorrectionDisabled(true)
                            .textInputAutocapitalization(.never)
                            .onChange(of: searchText) { _, newValue in
                                searchTask?.cancel()
                                searchTask = Task {
                                    try? await Task.sleep(for: .milliseconds(200))
                                    if !Task.isCancelled {
                                        await MainActor.run {
                                            withAnimation(.easeInOut(duration: 0.3)) {
                                                isSearching = !newValue.isEmpty
                                            }

                                            // Start train validation with debouncing
                                            startTrainValidation(for: newValue)
                                        }
                                    }
                                }
                            }
                            .onChange(of: searchFieldFocused) { _, newValue in
                                // Native sheet automatically handles expansion when keyboard appears
                            }
                            .onSubmit {
                                if let firstResult = searchResults.stations.first,
                                   let code = Stations.getStationCode(firstResult) {
                                    selectOriginStation(name: firstResult, code: code)
                                }
                            }
                        
                        // Profile icon - moved from top navigation
                        Button {
                            // Immediately hide RatSense to prevent content shift during navigation
                            isNavigatingToProfile = true
                            // Use pendingNavigation to expand sheet FIRST, then navigate
                            // This prevents the glitch where sheet expands with empty space
                            appState.pendingNavigation = .myProfile
                        } label: {
                            Image(systemName: "person.circle.fill")
                                .font(.system(size: 24))
                                .foregroundColor(.white.opacity(0.8))
                        }
                        .padding(.leading, 8)
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(
                        RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                            .fill(TrackRatTheme.Colors.surfaceCard)
                            .overlay(
                                RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                                    .stroke(TrackRatTheme.Colors.border, lineWidth: 1)
                            )
                    )
                    .padding(.horizontal)
                    .id("searchField")
                    
                    // Search results
                    if isSearching {
                        VStack(spacing: 8) {
                            // Train number results (support for multiple trains)
                            ForEach(searchResults.trainNumbers, id: \.self) { trainNumber in
                                trainSearchCard(for: trainNumber)
                            }
                            
                            ForEach(searchResults.stations.prefix(5), id: \.self) { station in
                                Button {
                                    if let code = Stations.getStationCode(station) {
                                        selectOriginStation(name: station, code: code)
                                    }
                                } label: {
                                    HStack {
                                        HStack {
                                            Text(station)
                                                .font(.body)
                                                .foregroundColor(.white)
                                            Spacer()
                                        }

                                        if let code = Stations.getStationCode(station) {
                                            StationIconView(
                                                stationCode: code,
                                                isStationFavorited: appState.isStationFavorited(code: code)
                                            ) {
                                                withAnimation(.easeInOut(duration: 0.2)) {
                                                    appState.toggleFavoriteStation(code: code, name: station)
                                                }
                                                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                                            }
                                            .padding(.leading, 8)
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
                                }
                                .buttonStyle(.plain)
                                .padding(.horizontal)
                            }
                        }
                        .transition(.opacity.combined(with: .move(edge: .top)))
                    }
                    
                    // Active trips (Live Activity) - show when not searching
                    if !isSearching {
                        ActiveTripsSection()
                    }
                    
                    // Favorite stations - show when not searching
                    if !favoriteStations.isEmpty && !isSearching {
                        VStack(alignment: .leading, spacing: 16) {
                            ForEach(favoriteStations) { station in
                                FavoriteStationButton(station: station) {
                                    selectOriginStation(name: station.name, code: station.id)
                                }
                                .padding(.horizontal)
                            }
                        }
                        .padding(.top, 8)
                        .transition(.opacity.combined(with: .move(edge: .top)))
                    }
                }
                .padding(.top, 12)
                
                    // Spacer to push content to top and fill remaining space
                    Spacer(minLength: 100) // Ensure some minimum space at bottom
                }
        }
        .onAppear {
            print("🐀🐀🐀 TripSelectionView appeared - updating Rat Sense")

            // Reset navigation flag when returning to this view
            isNavigatingToProfile = false

            // Debug: Check what's in storage
            print("🐀 DEBUG: Home station = \(ratSenseService.getHomeStation() ?? "nil")")
            print("🐀 DEBUG: Work station = \(ratSenseService.getWorkStation() ?? "nil")")

            ratSenseService.updateSuggestion()
            appState.loadRecentTrips()
            appState.loadFavoriteStations()
        }
        .onDisappear {
            // Cancel any pending validation tasks
            for task in validationTasks.values {
                task.cancel()
            }
            validationTasks.removeAll()
        }
    }
    
    private func selectTrip(_ trip: TripPair) {
        appState.selectedDeparture = trip.departureName
        appState.departureStationCode = trip.departureCode
        appState.selectedDestination = trip.destinationName
        appState.selectedRoute = trip  // Set selected route for map highlighting

        // Use pendingNavigation to expand sheet FIRST, then navigate
        appState.pendingNavigation = .trainList(destination: trip.destinationName, departureStationCode: trip.departureCode)

        // Reset search state WITHOUT animation to prevent ghosting during navigation
        var transaction = Transaction()
        transaction.disablesAnimations = true
        withTransaction(transaction) {
            searchText = ""
            isSearching = false
            searchFieldFocused = false
        }
    }
    
    private func selectRatSenseSuggestion(_ suggestion: RatSenseService.SuggestedJourney) {
        print("🐀🐀🐀 Rat Sense suggestion selected: \(suggestion.fromStation) → \(suggestion.toStation)")

        // Record the journey search
        ratSenseService.recordJourneySearch(from: suggestion.fromStation, to: suggestion.toStation)

        // Set both departure and destination
        appState.selectedDeparture = suggestion.fromStationName
        appState.departureStationCode = suggestion.fromStation
        appState.selectedDestination = suggestion.toStationName
        appState.destinationStationCode = suggestion.toStation

        // Use pendingNavigation to expand sheet FIRST, then navigate
        appState.pendingNavigation = .trainList(destination: suggestion.toStationName, departureStationCode: suggestion.fromStation)
    }
    
    private func selectOriginStation(name: String, code: String) {
        appState.selectedDeparture = name
        appState.departureStationCode = code
        // Clear any existing route so map focuses on single station
        appState.selectedRoute = nil
        
        // Snap bottom sheet to medium (50%) position for better map visibility
        // Native sheet will handle positioning automatically
        appState.navigationPath.append(NavigationDestination.destinationPicker)

        // Reset search WITHOUT animation to prevent ghosting during navigation
        var transaction = Transaction()
        transaction.disablesAnimations = true
        withTransaction(transaction) {
            searchText = ""
            isSearching = false
            searchFieldFocused = false
        }

        // Haptic feedback
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }
    
    // MARK: - Train Search UI
    
    @ViewBuilder
    private func trainSearchCard(for trainNumber: String) -> some View {
        let state = trainValidationStates[trainNumber] ?? .unknown
        
        Button {
            if state == .found {
                searchForTrain(trainNumber)
            }
        } label: {
            HStack {
                Image(systemName: "tram.fill")
                    .font(.system(size: 20))
                    .foregroundColor(cardColor(for: state))
                
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 8) {
                        Text("Train \(trainNumber)")
                            .font(.headline)
                            .foregroundColor(.white)
                        
                        // Train system badge
                        Text(trainSystemName(for: trainNumber))
                            .font(.caption2)
                            .fontWeight(.semibold)
                            .foregroundColor(.white)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(trainSystemColor(for: trainNumber))
                            )
                    }
                    
                    Text(cardSubtitle(for: state))
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.7))
                }
                
                Spacer()
                
                cardIcon(for: state)
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                    .fill(cardColor(for: state).opacity(0.2))
                    .overlay(
                        RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                            .stroke(cardColor(for: state), lineWidth: 1.5)
                    )
            )
        }
        .disabled(state != .found)
        .padding(.horizontal)
    }
    
    private func cardColor(for state: TrainValidationState) -> Color {
        switch state {
        case .unknown, .validating:
            return .orange
        case .found:
            return .green
        case .notFound:
            return .red
        }
    }
    
    private func cardSubtitle(for state: TrainValidationState) -> String {
        switch state {
        case .unknown:
            return "Search for this train"
        case .validating:
            return "Checking if train exists..."
        case .found:
            return "View this train"
        case .notFound:
            return "No train found. Continue typing..."
        }
    }
    
    @ViewBuilder
    private func cardIcon(for state: TrainValidationState) -> some View {
        switch state {
        case .unknown, .found:
            Image(systemName: "arrow.right.circle.fill")
                .font(.system(size: 20))
                .foregroundColor(cardColor(for: state))
        case .validating:
            ProgressView()
                .progressViewStyle(CircularProgressViewStyle(tint: .orange))
                .scaleEffect(0.8)
        case .notFound:
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 20))
                .foregroundColor(.red)
        }
    }
    
    // Helper methods for train system identification
    private func trainSystemName(for trainNumber: String) -> String {
        return trainNumber.hasPrefix("A") ? "AMTRAK" : "NJT"
    }
    
    private func trainSystemColor(for trainNumber: String) -> Color {
        return .gray
    }
    
    // MARK: - Train Validation
    
    private func startTrainValidation(for searchText: String) {
        let potentialTrainNumbers = getPotentialTrainNumbers(searchText)
        
        // Cancel validation tasks for trains no longer in search results
        let currentTasks = Set(validationTasks.keys)
        let newTrains = Set(potentialTrainNumbers)
        
        for trainNumber in currentTasks.subtracting(newTrains) {
            validationTasks[trainNumber]?.cancel()
            validationTasks.removeValue(forKey: trainNumber)
            trainValidationStates.removeValue(forKey: trainNumber)
        }
        
        // Start validation for new trains
        for trainNumber in potentialTrainNumbers {
            // Skip if already validating or validated
            if validationTasks[trainNumber] != nil {
                continue
            }
            
            // Reset state for this train
            trainValidationStates[trainNumber] = .unknown
            
            // Start validation with debouncing
            validationTasks[trainNumber] = Task {
                // Debounce for 500ms
                try? await Task.sleep(for: .milliseconds(500))
                
                guard !Task.isCancelled else { return }
                
                await MainActor.run {
                    trainValidationStates[trainNumber] = .validating
                }
                
                // Try to validate the train
                do {
                    _ = try await attemptTrainSearch(trainNumber: trainNumber)
                    
                    guard !Task.isCancelled else { return }
                    
                    await MainActor.run {
                        trainValidationStates[trainNumber] = .found
                    }
                } catch {
                    guard !Task.isCancelled else { return }
                    
                    await MainActor.run {
                        trainValidationStates[trainNumber] = .notFound
                    }
                }
            }
        }
    }
    
    private func searchForTrain(_ trainNumber: String) {
        // Haptic feedback
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
        
        Task {
            do {
                let foundTrain = try await attemptTrainSearch(trainNumber: trainNumber)
                
                await MainActor.run {
                    // Success - navigate to train details
                    appState.currentTrainId = foundTrain.id
                    // Use pendingNavigation to expand sheet FIRST, then navigate
                    appState.pendingNavigation = .trainDetailsFlexible(
                        trainNumber: trainNumber,
                        fromStation: nil,  // No specific departure station when searching globally
                        journeyDate: foundTrain.journeyDate
                    )

                    // Reset search WITHOUT animation to prevent ghosting during navigation
                    var transaction = Transaction()
                    transaction.disablesAnimations = true
                    withTransaction(transaction) {
                        searchText = ""
                        isSearching = false
                        searchFieldFocused = false
                    }
                }
            } catch {
                await MainActor.run {
                    // For now, just print error - could add error state later
                    print("🔴 Train search failed: \(error)")
                }
            }
        }
    }
    
    // Helper functions for train search
    private func attemptTrainSearch(trainNumber: String) async throws -> TrainV2 {
        let train = try await APIService.shared.fetchTrainByNumber(
            trainNumber,
            fromStationCode: nil  // No specific departure station for global search
        )
        
        // Verify the train can be loaded in details view before proceeding
        _ = try await APIService.shared.fetchTrainDetailsFlexible(
            id: nil,
            trainId: trainNumber,
            fromStationCode: nil
        )
        
        return train
    }
}

// MARK: - Favorite Station Button
struct FavoriteStationButton: View {
    let station: FavoriteStation
    let onTap: () -> Void
    @EnvironmentObject private var appState: AppState
    
    
    var body: some View {
        Button {
            onTap()
        } label: {
            HStack {
                Text(Stations.displayName(for: station.name))
                    .font(.callout)
                    .fontWeight(.medium)
                    .foregroundColor(.white)

                Spacer()

                // Station icon - shows home/work icon or interactive heart
                StationIconView(
                    stationCode: station.id,
                    isStationFavorited: appState.isStationFavorited(code: station.id),
                    fontSize: 20
                ) {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        appState.toggleFavoriteStation(code: station.id, name: station.name)
                    }
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                }

                Image(systemName: "chevron.right")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(.white.opacity(0.6))
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
        .buttonStyle(.plain)
    }
}

#Preview {
    TripSelectionView()
        .environmentObject(AppState())
        .environmentObject(ThemeManager.shared)
}
