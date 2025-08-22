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
    @FocusState private var searchFieldFocused: Bool
    @StateObject private var liveActivityService = LiveActivityService.shared
    @StateObject private var ratSenseService = RatSenseService.shared
    
    // Train validation state
    @State private var trainValidationState: TrainValidationState = .unknown
    @State private var validatedTrainNumber: String = ""
    @State private var validationTask: Task<Void, Never>?
    
    // Callback to control bottom sheet position
    let onBottomSheetPositionChange: ((BottomSheetPosition) -> Void)?
    
    init(onBottomSheetPositionChange: ((BottomSheetPosition) -> Void)? = nil) {
        self.onBottomSheetPositionChange = onBottomSheetPositionChange
    }
    
    // Get favorite stations
    private var favoriteStations: [FavoriteStation] {
        return appState.favoriteStations
    }
    
    private var searchResults: (stations: [String], trainNumber: String?) {
        let query = searchText.trimmingCharacters(in: .whitespaces)
        
        // Always search stations
        let stationResults = Stations.search(query)
        
        // Check if input also looks like a train number
        let trainNumber = isLikelyTrainNumber(query) ? query : nil
        
        
        return (stations: stationResults, trainNumber: trainNumber)
    }
    
    // Helper function to detect if input looks like a train number
    private func isLikelyTrainNumber(_ input: String) -> Bool {
        let trimmed = input.uppercased()
        
        // Amtrak: A followed by 2+ digits
        if trimmed.hasPrefix("A") && trimmed.count >= 3 {
            let remainder = String(trimmed.dropFirst())
            return remainder.allSatisfy(\.isNumber)
        }
        
        // NJ Transit: 2+ digits only
        if trimmed.count >= 2 && trimmed.allSatisfy(\.isNumber) {
            return true
        }
        
        return false
    }
    
    
    var body: some View {
        ZStack {
            // Theme background
            TrackRatTheme.Colors.surface
                .ignoresSafeArea()
            
            GeometryReader { geometry in
                VStack(spacing: 8) {
                // Top title only
                Text("Where would you like to leave from?")
                    .font(.system(size: 26, weight: .semibold))
                    .foregroundColor(.white)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity)
                .padding(.horizontal)
                .padding(.top, 20)
                
                // Search results and content container
                VStack(alignment: .leading, spacing: 16) {
                    // Rat Sense suggestion
                    if let suggestion = ratSenseService.suggestedJourney {
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
                    }
                    
                    // Search field with profile icon
                    HStack {
                        Image(systemName: "magnifyingglass")
                            .foregroundColor(.white.opacity(0.6))
                        
                        TextField("Search stations or train number", text: $searchText)
                            .foregroundColor(.white)
                            .focused($searchFieldFocused)
                            .onChange(of: searchText) { _, newValue in
                                withAnimation(.easeInOut(duration: 0.3)) {
                                    isSearching = !newValue.isEmpty
                                }
                                
                                // Start train validation with debouncing
                                startTrainValidation(for: newValue)
                            }
                            .onChange(of: searchFieldFocused) { _, newValue in
                                if newValue {
                                    // When search field gains focus, expand to medium to show favorites
                                    onBottomSheetPositionChange?(.medium)
                                }
                            }
                            .onSubmit {
                                if let firstResult = searchResults.stations.first,
                                   let code = Stations.getStationCode(firstResult) {
                                    selectOriginStation(name: firstResult, code: code)
                                }
                            }
                        
                        // Profile icon - moved from top navigation
                        Button {
                            // Expand bottom sheet to 100% height when profile is tapped
                            onBottomSheetPositionChange?(.expanded)
                            appState.navigationPath.append(NavigationDestination.myProfile)
                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
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
                            // Train number result (if detected)
                            if let trainNumber = searchResults.trainNumber {
                                trainSearchCard(for: trainNumber)
                            }
                            
                            ForEach(searchResults.stations.prefix(5), id: \.self) { station in
                                HStack {
                                    // Main station button
                                    Button {
                                        if let code = Stations.getStationCode(station) {
                                            selectOriginStation(name: station, code: code)
                                        }
                                    } label: {
                                        HStack {
                                            Text(station)
                                                .font(.body)
                                                .foregroundColor(.white)
                                            Spacer()
                                        }
                                    }
                                    
                                    // Heart button - separate from main button
                                    if let code = Stations.getStationCode(station) {
                                        Button {
                                            withAnimation(.easeInOut(duration: 0.2)) {
                                                appState.toggleFavoriteStation(code: code, name: station)
                                            }
                                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                                        } label: {
                                            Image(systemName: appState.isStationFavorited(code: code) ? "heart.fill" : "heart")
                                                .font(.system(size: 16))
                                                .foregroundColor(.orange)
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
                                .padding(.horizontal)
                            }
                        }
                        .transition(.opacity.combined(with: .move(edge: .top)))
                    }
                    
                    // Active trips (Live Activity) - show when not searching
                    if !isSearching {
                        if #available(iOS 16.1, *) {
                            ActiveTripsSection()
                        }
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
                Spacer()
                }
                .frame(width: geometry.size.width, height: max(geometry.size.height, 600), alignment: .top)
            }
        }
        .onAppear {
            print("🐀🐀🐀 TripSelectionView appeared - updating Rat Sense")
            
            // Debug: Check what's in storage
            print("🐀 DEBUG: Home station = \(ratSenseService.getHomeStation() ?? "nil")")
            print("🐀 DEBUG: Work station = \(ratSenseService.getWorkStation() ?? "nil")")
            
            ratSenseService.updateSuggestion()
            appState.loadRecentTrips()
            appState.loadFavoriteStations()
        }
        .onDisappear {
            // Cancel any pending validation tasks
            validationTask?.cancel()
        }
    }
    
    private func selectTrip(_ trip: TripPair) {
        appState.selectedDeparture = trip.departureName
        appState.departureStationCode = trip.departureCode
        appState.selectedDestination = trip.destinationName
        appState.selectedRoute = trip  // Set selected route for map highlighting
        appState.navigationPath.append(NavigationDestination.trainList(destination: trip.destinationName))
        
        // Reset search state but maintain bottom sheet position
        withAnimation(.easeInOut(duration: 0.3)) {
            searchText = ""
            isSearching = false
            searchFieldFocused = false
        }
        // DON'T reset bottom sheet position - maintain current height
        // onBottomSheetPositionChange?(.compact)
        
        // Haptic feedback
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
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
        
        // Navigate directly to train list
        appState.navigationPath.append(NavigationDestination.trainList(destination: suggestion.toStationName))
        
        // Haptic feedback
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
    }
    
    private func selectOriginStation(name: String, code: String) {
        appState.selectedDeparture = name
        appState.departureStationCode = code
        // Clear any existing route so map focuses on single station
        appState.selectedRoute = nil
        
        // Snap bottom sheet to medium (50%) position for better map visibility
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
            onBottomSheetPositionChange?(.medium)
        }
        
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
    
    // MARK: - Train Search UI
    
    @ViewBuilder
    private func trainSearchCard(for trainNumber: String) -> some View {
        let isValidated = validatedTrainNumber == trainNumber
        let state = isValidated ? trainValidationState : .unknown
        
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
                    Text("Train \(trainNumber)")
                        .font(.headline)
                        .foregroundColor(.white)
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
    
    // MARK: - Train Validation
    
    private func startTrainValidation(for searchText: String) {
        let query = searchText.trimmingCharacters(in: .whitespaces)
        
        // Cancel any existing validation task
        validationTask?.cancel()
        
        // Reset state if not a train number
        guard isLikelyTrainNumber(query) else {
            trainValidationState = .unknown
            validatedTrainNumber = ""
            return
        }
        
        // Reset state if different train number
        if validatedTrainNumber != query {
            trainValidationState = .unknown
            validatedTrainNumber = ""
        }
        
        // Start validation with debouncing
        validationTask = Task {
            // Debounce for 500ms
            try? await Task.sleep(for: .milliseconds(500))
            
            guard !Task.isCancelled else { return }
            
            await MainActor.run {
                trainValidationState = .validating
                validatedTrainNumber = query
            }
            
            // Try to validate the train
            do {
                _ = try await attemptTrainSearch(trainNumber: query)
                
                guard !Task.isCancelled else { return }
                
                await MainActor.run {
                    if validatedTrainNumber == query {
                        trainValidationState = .found
                    }
                }
            } catch {
                // Try with "A" prefix for numeric inputs
                if isNumericInput(query) && isTrainNotFoundError(error) {
                    let amtrakTrainNumber = "A\(query)"
                    do {
                        _ = try await attemptTrainSearch(trainNumber: amtrakTrainNumber)
                        
                        guard !Task.isCancelled else { return }
                        
                        await MainActor.run {
                            if validatedTrainNumber == query {
                                trainValidationState = .found
                                validatedTrainNumber = amtrakTrainNumber // Update to the working format
                            }
                        }
                    } catch {
                        guard !Task.isCancelled else { return }
                        
                        await MainActor.run {
                            if validatedTrainNumber == query {
                                trainValidationState = .notFound
                            }
                        }
                    }
                } else {
                    guard !Task.isCancelled else { return }
                    
                    await MainActor.run {
                        if validatedTrainNumber == query {
                            trainValidationState = .notFound
                        }
                    }
                }
            }
        }
    }
    
    private func searchForTrain(_ trainNumber: String) {
        // Haptic feedback
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
        
        Task {
            let trimmedInput = trainNumber.trimmingCharacters(in: .whitespaces)
            var lastError: Error?
            var foundTrain: TrainV2?
            var successfulTrainNumber: String?
            
            // First attempt: Try user's exact input
            do {
                foundTrain = try await attemptTrainSearch(trainNumber: trimmedInput)
                successfulTrainNumber = trimmedInput
            } catch {
                lastError = error
                
                // Second attempt: If input is numeric and first attempt failed with "not found", try with "A" prefix
                if isNumericInput(trimmedInput) && isTrainNotFoundError(error) {
                    let amtrakTrainNumber = "A\(trimmedInput)"
                    do {
                        foundTrain = try await attemptTrainSearch(trainNumber: amtrakTrainNumber)
                        successfulTrainNumber = amtrakTrainNumber
                    } catch {
                        lastError = error
                    }
                }
            }
            
            await MainActor.run {
                if let train = foundTrain, let trainNumber = successfulTrainNumber {
                    // Success - navigate to train details
                    appState.currentTrainId = train.id
                    appState.navigationPath.append(NavigationDestination.trainDetailsFlexible(
                        trainNumber: trainNumber,
                        fromStation: nil  // No specific departure station when searching globally
                    ))
                    
                    // Reset search
                    withAnimation(.easeInOut(duration: 0.3)) {
                        searchText = ""
                        isSearching = false
                        searchFieldFocused = false
                    }
                } else if let error = lastError {
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
    
    private func isNumericInput(_ input: String) -> Bool {
        let trimmedInput = input.trimmingCharacters(in: .whitespaces)
        return !trimmedInput.isEmpty && trimmedInput.allSatisfy(\.isNumber)
    }
    
    private func isTrainNotFoundError(_ error: Error) -> Bool {
        if let apiError = error as? APIError {
            return apiError == .noData
        } else if let urlError = error as? URLError {
            return urlError.localizedDescription == "No data received"
        } else {
            return error.localizedDescription == "No data received"
        }
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
                
                // Unfavorite button (heart icon)
                Button {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        appState.toggleFavoriteStation(code: station.id, name: station.name)
                    }
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                } label: {
                    Image(systemName: "heart.fill")
                        .font(.system(size: 20))
                        .foregroundColor(.orange)
                }
                .onTapGesture {
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
    }
}

#Preview {
    TripSelectionView()
        .environmentObject(AppState())
        .environmentObject(ThemeManager.shared)
}
