import SwiftUI

/// Small colored pill showing which transit system a station belongs to.
/// Used in search results to identify stations from non-active systems.
struct SystemBadge: View {
    let system: TrainSystem

    var body: some View {
        Text(system.displayName)
            .font(.caption2)
            .fontWeight(.medium)
            .foregroundColor(.white.opacity(0.9))
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(
                RoundedRectangle(cornerRadius: 4)
                    .fill((Color(hex: system.color) ?? .gray).opacity(0.7))
            )
    }
}

/// A view that displays the appropriate icon for a station based on whether it's a home station, work station, or regular favorite
struct StationIconView: View {
    let stationCode: String
    let isStationFavorited: Bool
    let iconFont: Font
    let onHeartTap: () -> Void

    init(
        stationCode: String,
        isStationFavorited: Bool,
        iconFont: Font = TrackRatTheme.IconSize.small,
        onHeartTap: @escaping () -> Void
    ) {
        self.stationCode = stationCode
        self.isStationFavorited = isStationFavorited
        self.iconFont = iconFont
        self.onHeartTap = onHeartTap
    }

    private var isHomeStation: Bool {
        RatSenseService.shared.getHomeStation() == stationCode
    }

    private var isWorkStation: Bool {
        RatSenseService.shared.getWorkStation() == stationCode
    }

    private var isHomeOrWorkStation: Bool {
        isHomeStation || isWorkStation
    }

    var body: some View {
        if isHomeStation {
            // Home station icon
            Image(systemName: "house.fill")
                .font(iconFont)
                .foregroundColor(.orange)
        } else if isWorkStation {
            // Work station icon
            Image(systemName: "building.2.fill")
                .font(iconFont)
                .foregroundColor(.orange)
        } else {
            // Regular favorite heart icon - interactive
            Image(systemName: isStationFavorited ? "heart.fill" : "heart")
                .font(iconFont)
                .foregroundColor(.orange)
                .onTapGesture {
                    onHeartTap()
                }
        }
    }
}

struct DeparturePickerView: View {
    @EnvironmentObject private var appState: AppState
    @StateObject private var ratSenseService = RatSenseService.shared
    @State private var searchText = ""
    @State private var isSearching = false
    @FocusState private var searchFieldFocused: Bool
    @State private var navigationBarVisible = false
    @State private var trainSearchError: String?
    @State private var isSearchingTrain = false
    @State private var searchTask: Task<Void, Never>?
    @State private var showSettingsForTrainSystems = false

    private var searchResults: (stations: [String], otherSystemStations: [String], trainNumber: String?) {
        let query = searchText.trimmingCharacters(in: .whitespaces)

        // Search stations grouped by active system membership
        let grouped = Stations.searchGrouped(query, selectedSystems: appState.selectedSystems)

        // Check if input also looks like a train number
        let trainNumber = isLikelyTrainNumber(query) ? query : nil

        return (stations: grouped.primary, otherSystemStations: grouped.other, trainNumber: trainNumber)
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

        // Amtrak "A", LIRR "L", Metro-North "M": prefix followed by 2+ digits
        if let first = trimmed.first, "ALM".contains(first), trimmed.count >= 3 {
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
            HStack {
                Image(systemName: "tram.fill")
                    .font(TrackRatTheme.IconSize.medium)
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
                        .font(TrackRatTheme.IconSize.medium)
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
            .onTapGesture {
                if !isSearchingTrain {
                    searchForTrain(trainNumber)
                }
            }
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
            .sheet(isPresented: $showSettingsForTrainSystems) {
                SettingsView(editTrainSystems: true)
                    .presentationDetents([.large])
                    .presentationDragIndicator(.visible)
            }
    }
    
    @ViewBuilder
    private var mainContent: some View {
        // Native sheet handles scrolling automatically
        ScrollView {
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
                Text("🐀✨ \(suggestion.fromStationName) to \(suggestion.toStationName)")
                    .font(TrackRatTheme.Typography.bodySecondary)
                    .foregroundColor(.white)
                    .textProtected()
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
                    .onTapGesture {
                        selectRatSenseSuggestion(suggestion)
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
                                if trainSearchError != nil {
                                    trainSearchError = nil
                                }
                            }
                        }
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
                    } else if !searchResults.otherSystemStations.isEmpty {
                        showSettingsForTrainSystems = true
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
            stationsSection
        }
    }
    
    @ViewBuilder
    private var searchResultsSection: some View {
        VStack(spacing: 8) {
            trainSearchResultView
            stationResultsView

            // Stations from non-active transit systems
            if !searchResults.otherSystemStations.isEmpty {
                Text("Other systems — edit your train systems to use")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.5))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 28)
                    .padding(.top, 4)

                otherSystemStationResultsView
            }
        }
    }

    @ViewBuilder
    private func stationRow(_ station: String) -> some View {
        let code = Stations.getStationCode(station)
        let displayName = code.map { Stations.displayName(for: $0) } ?? station
        let lines = code.map { SubwayLines.lines(forStationCode: $0) } ?? []
        HStack {
            HStack(spacing: 6) {
                Text(displayName)
                    .font(.body)
                    .foregroundColor(.white)
                    .textProtected()
                SubwayLineChips(lines: lines, size: 14)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(TrackRatTheme.IconSize.xsmall)
                    .foregroundColor(.white.opacity(0.6))
            }

            if let code {
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
            RoundedRectangle(cornerRadius: 12)
                .fill(.white.opacity(0.15))
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(.white.opacity(0.2), lineWidth: 1)
                )
        )
        .padding(.horizontal, 24)
    }

    @ViewBuilder
    private var stationResultsView: some View {
        ForEach(searchResults.stations, id: \.self) { station in
            stationRow(station)
                .onTapGesture {
                    if let code = Stations.getStationCode(station) {
                        selectDeparture(name: station, code: code)
                    }
                }
        }
    }

    @ViewBuilder
    private var otherSystemStationResultsView: some View {
        ForEach(searchResults.otherSystemStations, id: \.self) { station in
            let code = Stations.getStationCode(station)
            let displayName = code.map { Stations.displayName(for: $0) } ?? station
            let lines = code.map { SubwayLines.lines(forStationCode: $0) } ?? []
            HStack {
                HStack(spacing: 6) {
                    Text(displayName)
                        .font(.body)
                        .foregroundColor(.white.opacity(0.7))
                        .textProtected()

                    SubwayLineChips(lines: lines, size: 14)
                        .opacity(0.7)

                    if let code, let system = Stations.primarySystem(forStationCode: code) {
                        SystemBadge(system: system)
                    }

                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(TrackRatTheme.IconSize.xsmall)
                        .foregroundColor(.white.opacity(0.4))
                }

                if let code {
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
                RoundedRectangle(cornerRadius: 12)
                    .fill(.white.opacity(0.1))
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(.white.opacity(0.15), lineWidth: 1)
                    )
            )
            .padding(.horizontal, 24)
            .onTapGesture {
                showSettingsForTrainSystems = true
            }
        }
    }

    @ViewBuilder
    private var stationsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Stations")
                .trackRatSectionHeader()
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
    
    private func selectRatSenseSuggestion(_ suggestion: RatSenseService.SuggestedJourney) {
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
                
                // Second attempt: If input is numeric and not found, try with
                // transit system prefixes (Amtrak, LIRR, Metro-North)
                if isNumericInput(trimmedInput) && isTrainNotFoundError(error) {
                    for prefix in ["A", "L", "M"] {
                        let prefixedNumber = "\(prefix)\(trimmedInput)"
                        do {
                            foundTrain = try await attemptTrainSearch(trainNumber: prefixedNumber)
                            successfulTrainNumber = prefixedNumber
                            break
                        } catch {
                            lastError = error
                        }
                    }
                }
            }
            
            await MainActor.run {
                if let train = foundTrain, let trainNumber = successfulTrainNumber {
                    // Success - navigate to train details
                    appState.currentTrainId = train.id
                    // Use pendingNavigation to expand sheet FIRST, then navigate
                    appState.pendingNavigation = .trainDetailsFlexible(
                        trainNumber: trainNumber,
                        fromStation: nil,  // No specific departure station when searching globally
                        journeyDate: train.journeyDate,
                        dataSource: train.dataSource
                    )

                    // Reset search WITHOUT animation to prevent ghosting during navigation
                    var transaction = Transaction()
                    transaction.disablesAnimations = true
                    withTransaction(transaction) {
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
            HStack {
                Text(Stations.displayName(for: name))
                    .font(.headline)
                    .foregroundColor(.white)
                Spacer()
                Image(systemName: "chevron.right")
                    .foregroundColor(.white.opacity(0.7))
                    .font(.caption)
            }
            .onTapGesture {
                onTap()
            }
            
            // Station icon - shows home/work icon or interactive heart
            StationIconView(
                stationCode: code,
                isStationFavorited: appState.isStationFavorited(code: code)
            ) {
                withAnimation(.easeInOut(duration: 0.2)) {
                    appState.toggleFavoriteStation(code: code, name: name)
                }
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            }
            .padding(.leading, 8)
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 20)
        .padding(.vertical, 16)
        .background(TrackRatTheme.Colors.surfaceCard)
        .cornerRadius(TrackRatTheme.CornerRadius.md)
    }
}

#Preview {
    DeparturePickerView()
        .environmentObject(AppState())
}
