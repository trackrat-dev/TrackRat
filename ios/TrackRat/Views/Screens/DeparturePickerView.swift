import SwiftUI

struct DeparturePickerView: View {
    @EnvironmentObject private var appState: AppState
    @StateObject private var ratSenseService = RatSenseService.shared
    
    init() {
        print("🐀🐀🐀 DeparturePickerView init - ensuring RatSense is initialized")
        _ = RatSenseService.shared
    }
    @State private var searchText = ""
    @State private var isSearching = false
    @FocusState private var searchFieldFocused: Bool
    @State private var navigationBarVisible = false
    @State private var trainSearchError: String?
    @State private var isSearchingTrain = false
    
    private var searchResults: (stations: [String], trainNumber: String?) {
        let query = searchText.trimmingCharacters(in: .whitespaces)
        
        // Always search stations
        let stationResults = Stations.search(query)
        
        // Check if input also looks like a train number
        let trainNumber = isLikelyTrainNumber(query) ? query : nil
        
        
        return (stations: stationResults, trainNumber: trainNumber)
    }
    
    // Computed property for dynamic spacing
    private var topPadding: CGFloat {
        (searchFieldFocused || isSearching) ? 20 : 100
    }
    
    // Computed property to determine if title should be shown
    private var shouldShowTitle: Bool {
        !searchFieldFocused && !isSearching
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
    
    // Helper view for train search results
    @ViewBuilder
    private var trainSearchResultView: some View {
        if let trainNumber = searchResults.trainNumber {
            Button {
                searchForTrain(trainNumber)
            } label: {
                HStack {
                    Image(systemName: "tram.fill")
                        .font(.system(size: 20))
                        .foregroundColor(.orange)
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Train \(trainNumber)")
                            .font(.headline)
                            .foregroundColor(.white)
                        Text("Search for this train")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.7))
                    }
                    
                    Spacer()
                    
                    if isSearchingTrain {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .orange))
                            .scaleEffect(0.8)
                    } else {
                        Image(systemName: "arrow.right.circle.fill")
                            .font(.system(size: 20))
                            .foregroundColor(.orange)
                    }
                }
                .padding()
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color.orange.opacity(0.2))
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(Color.orange, lineWidth: 1.5)
                        )
                )
            }
            .disabled(isSearchingTrain)
            .padding(.horizontal, 24)
            
            // Show train search error if any
            if let error = trainSearchError {
                HStack {
                    Image(systemName: "exclamationmark.triangle")
                        .foregroundColor(.orange)
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.orange)
                }
                .padding(.horizontal, 24)
            }
        }
    }
    
    var body: some View {
        let _ = print("🐀🐀🐀 DeparturePickerView body rendering")
        return mainContent
            .navigationBarTitleDisplayMode(.inline)
            .scrollAwareNavigationBar(isVisible: navigationBarVisible)
            .tint(.orange)
            .onAppear {
                print("🐀🐀🐀 DeparturePickerView appeared - updating Rat Sense")
                // Update Rat Sense suggestion when view appears
                ratSenseService.updateSuggestion()
                
                // Uncomment to test Rat Sense with sample data
                // ratSenseService.addTestData()
                
                // Uncomment to clear all Rat Sense data
                // ratSenseService.clearAllData()
            }
    }
    
    @ViewBuilder
    private var mainContent: some View {
        ZStack {
            TrackRatTheme.Colors.primaryBackground
                .ignoresSafeArea()
            
            VStack(spacing: 16) {
                titleSection
                
                Spacer()
                    .frame(height: shouldShowTitle ? 0 : topPadding)
                
                VStack(spacing: 20) {
                    searchFieldSection
                    contentSection
                }
                
                Spacer()
                Spacer()
            }
        }
    }
    
    @ViewBuilder
    private var titleSection: some View {
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
    }
    
    @ViewBuilder
    private var searchFieldSection: some View {
        VStack(spacing: 12) {
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
                .padding(.horizontal, 24)
            }
            
            // Search field
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
                    if trainSearchError != nil {
                        trainSearchError = nil
                    }
                }
                .onChange(of: searchFieldFocused) { _, newValue in
                    withAnimation(.easeInOut(duration: 0.3)) {
                        navigationBarVisible = newValue
                    }
                }
                .onSubmit {
                    if let firstResult = searchResults.stations.first,
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
        }
    }
    
    @ViewBuilder
    private var contentSection: some View {
        if isSearching {
            searchResultsSection
        } else {
            popularStationsSection
        }
    }
    
    @ViewBuilder
    private var searchResultsSection: some View {
        VStack(spacing: 8) {
            trainSearchResultView
            stationResultsView
        }
    }
    
    @ViewBuilder
    private var stationResultsView: some View {
        ForEach(searchResults.stations, id: \.self) { station in
            HStack {
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
                }
                
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
                RoundedRectangle(cornerRadius: 12)
                    .fill(.white.opacity(0.15))
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(.white.opacity(0.2), lineWidth: 1)
                    )
            )
            .padding(.horizontal, 24)
        }
    }
    
    @ViewBuilder
    private var popularStationsSection: some View {
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
    
    private func selectRatSenseSuggestion(_ suggestion: RatSenseService.SuggestedJourney) {
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
    
    private func searchForTrain(_ trainNumber: String) {
        guard !isSearchingTrain else { return }
        
        isSearchingTrain = true
        trainSearchError = nil
        
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
                    // Handle the final error
                    handleTrainSearchError(error, originalInput: trimmedInput)
                }
                
                isSearchingTrain = false
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
    
    private func handleTrainSearchError(_ error: Error, originalInput: String) {
        if let apiError = error as? APIError {
            switch apiError {
            case .noData:
                // Provide more helpful message for numeric inputs that might be Amtrak
                if isNumericInput(originalInput) {
                    trainSearchError = "Train not found. Amtrak trains typically need an 'A' prefix (e.g., A\(originalInput))"
                } else {
                    trainSearchError = "Train \(originalInput) not found"
                }
            default:
                trainSearchError = "Search failed: \(apiError.localizedDescription)"
            }
        } else if let urlError = error as? URLError {
            switch urlError.code {
            case .notConnectedToInternet:
                trainSearchError = "No internet connection"
            case .timedOut:
                trainSearchError = "Search timed out"
            case .cannotFindHost, .cannotConnectToHost:
                trainSearchError = "Cannot connect to server"
            default:
                trainSearchError = "Train \(originalInput) not found"
            }
        } else {
            trainSearchError = "Train \(originalInput) not found"
        }
        
        UINotificationFeedbackGenerator().notificationOccurred(.error)
    }
}

// MARK: - Departure Button
struct DepartureButton: View {
    let name: String
    let code: String
    let onTap: () -> Void
    @EnvironmentObject private var appState: AppState
    
    var body: some View {
        HStack {
            // Main station button
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
            }
            
            // Heart button - separate from main button
            Button {
                withAnimation(.easeInOut(duration: 0.2)) {
                    appState.toggleFavoriteStation(code: code, name: name)
                }
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            } label: {
                Image(systemName: appState.isStationFavorited(code: code) ? "heart.fill" : "heart")
                    .font(.system(size: 18))
                    .foregroundColor(.orange)
            }
            .padding(.leading, 8)
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 20)
        .padding(.vertical, 16)
        .background(.white.opacity(0.2))
        .cornerRadius(12)
    }
}

#Preview {
    DeparturePickerView()
        .environmentObject(AppState())
}