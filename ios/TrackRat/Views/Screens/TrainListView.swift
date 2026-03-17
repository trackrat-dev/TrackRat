import SwiftUI

struct TrainListView: View {
    @EnvironmentObject private var appState: AppState
    @StateObject private var viewModel: TrainListViewModel
    // Configuration constants
    private static let DELAY_THRESHOLD_MINUTES = 6

    // Station info passed via init for guaranteed first-frame availability
    private let destination: String
    private let departureStationCode: String

    // Computed from init parameter to avoid layout shift
    private var departureName: String {
        Stations.displayName(for: departureStationCode)
    }

    /// Data sources to query: user's selected systems plus systems serving the selected stations.
    /// Ensures departures appear even when stations are from non-active systems.
    private var effectiveSystems: Set<TrainSystem> {
        var systems = appState.selectedSystems
        systems.formUnion(Stations.systemsForStation(departureStationCode))
        if let toCode = Stations.getStationCode(destination) {
            systems.formUnion(Stations.systemsForStation(toCode))
        }
        return systems
    }

    // PERFORMANCE: Track visibility to prevent polling when view is not visible
    @State private var isViewVisible = false

    // Date selection for future schedules
    @State private var selectedDate: Date = Date()
    @State private var showDatePicker: Bool = false

    /// Check if viewing a future date (not today)
    private var isFutureDate: Bool {
        !Calendar.current.isDateInToday(selectedDate)
    }

    init(destination: String, departureStationCode: String) {
        self.destination = destination
        self.departureStationCode = departureStationCode
        self._viewModel = StateObject(wrappedValue: TrainListViewModel())
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Fixed header - replaces system navigation bar to avoid layout shift
            HStack {
                // Back button
                Button {
                    if !appState.navigationPath.isEmpty {
                        appState.navigationPath.removeLast()
                    }
                } label: {
                    Image(systemName: "chevron.left")
                        .font(TrackRatTheme.IconSize.small)
                        .foregroundColor(.white)
                        .frame(minWidth: 44, minHeight: 44)
                }
                .buttonStyle(.plain)

                Spacer()

                // Center title
                VStack(spacing: 2) {
                    Text(destination)
                        .font(TrackRatTheme.Typography.title3)
                        .foregroundColor(.white)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                    if !departureName.isEmpty {
                        Text("from \(departureName)")
                            .font(.caption2)
                            .foregroundColor(.white.opacity(0.8))
                            .lineLimit(1)
                            .minimumScaleFactor(0.7)
                    }
                }

                Spacer()

                // Close button
                Button("Close") {
                    appState.navigationPath = NavigationPath()
                }
                .buttonStyle(.plain)
                .foregroundColor(.white)
                .font(.body)
                .frame(height: 44)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)

            // Action buttons row
            HStack(spacing: 12) {
                // Route alerts button
                if let destinationCode = Stations.getStationCode(destination) {
                    Button {
                        let ds = viewModel.trains.first?.dataSource ?? appState.selectedSystems.first?.rawValue ?? "NJT"
                        // For subway, don't set lineId — station pairs are served by multiple lines
                        // and gtfsRouteIds will infer all relevant lines from the station pair.
                        let lineId: String? = ds == "SUBWAY" ? nil : RouteTopology.routeContaining(from: departureStationCode, to: destinationCode, dataSource: ds)?.id
                        appState.pendingRouteStatus = RouteStatusContext(
                            dataSource: ds,
                            lineId: lineId,
                            fromStationCode: departureStationCode,
                            toStationCode: destinationCode
                        )
                    } label: {
                        HStack(spacing: 6) {
                            Image(systemName: "bell.badge")
                                .font(.subheadline)
                            Text("Alerts")
                                .font(.subheadline)
                        }
                        .foregroundColor(.white.opacity(0.8))
                        .padding(.horizontal, 14)
                        .padding(.vertical, 8)
                        .background(Capsule().fill(Color.white.opacity(0.12)))
                    }
                    .buttonStyle(.plain)
                }

                // Schedule picker - Pro feature
                Button {
                    showDatePicker = true
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "calendar")
                            .font(.subheadline)
                        Text("Schedules")
                            .font(.subheadline)
                    }
                    .foregroundColor(.white.opacity(0.8))
                    .padding(.horizontal, 14)
                    .padding(.vertical, 8)
                    .background(Capsule().fill(Color.white.opacity(0.12)))
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 8)

            // Scrollable content
            ScrollView {
                LazyVStack(spacing: 16) {
                    if viewModel.isLoading || (!viewModel.hasStartedLoading && viewModel.trains.isEmpty) {
                        TrackRatLoadingView(message: "Finding your trains...")
                            .frame(maxWidth: .infinity, minHeight: 200)
                    } else if let error = viewModel.error {
                        ErrorView(message: error) {
                            Task {
                                await viewModel.loadTrains(
                                    destination: destination,
                                    fromStationCode: departureStationCode,
                                    date: selectedDate,
                                    selectedSystems: effectiveSystems
                                )
                            }
                        }
                    } else if viewModel.trains.isEmpty {
                        EmptyStateView(message: isFutureDate ? "No scheduled trains for this day" : "No trains found")
                    } else {
                        // Schedule info banner for future dates
                        if isFutureDate {
                            ScheduleInfoBanner(date: selectedDate)
                        }

                        // Route summary (if we have both origin and destination) - only for today - Pro feature
                        if !isFutureDate,
                           !departureStationCode.isEmpty,
                           let destinationCode = Stations.getStationCode(destination) {
                            OperationsSummaryView(
                                scope: .route,
                                fromStation: departureStationCode,
                                toStation: destinationCode,
                                isExpandable: true,
                                onTrainTap: { selectedTrainId in
                                    // Navigate to the selected train's detail view
                                    // Note: dataSource not available from this callback, backend uses two-phase search
                                    appState.navigationPath.append(
                                        NavigationDestination.trainDetailsFlexible(
                                            trainNumber: selectedTrainId,
                                            fromStation: departureStationCode,
                                            journeyDate: nil,
                                            dataSource: nil
                                        )
                                    )
                                }
                            )
                            .padding(.bottom, 4)
                        }

                        ForEach(viewModel.trains) { train in
                            TrainCard(
                                train: train,
                                destination: destination,
                                departureStationCode: departureStationCode,
                                isFutureDate: isFutureDate,
                                onTap: {
                                    appState.currentTrainId = train.id
                                    appState.currentTrain = train  // Store the full train object

                                    // Set the route context for bottom sheet expansion
                                    if let destinationCode = Stations.getStationCode(destination) {
                                        appState.selectedRoute = TripPair(
                                            departureCode: departureStationCode,
                                            departureName: departureName,
                                            destinationCode: destinationCode,
                                            destinationName: destination,
                                            lastUsed: Date(),
                                            isFavorite: false
                                        )
                                    }

                                    // Use pendingNavigation to expand sheet FIRST, then navigate
                                    // This prevents the glitch where sheet expands with empty space
                                    appState.pendingNavigation = .trainDetailsFlexible(
                                        trainNumber: train.trainId,
                                        fromStation: departureStationCode.isEmpty ? nil : departureStationCode,
                                        journeyDate: train.journeyDate,
                                        dataSource: train.dataSource
                                    )
                                },
                                isExpress: viewModel.expressTrainIds.contains(train.trainId)
                            )
                        }
                    }

                    // Feedback button at bottom of content
                    if !viewModel.trains.isEmpty {
                        FeedbackButton(
                            screen: "train_list",
                            trainId: nil,
                            originCode: departureStationCode,
                            destinationCode: Stations.getStationCode(destination)
                        )
                        .padding(.top, 8)
                    }

                    // Add spacer at bottom for better scrolling
                    Spacer(minLength: 50)
                }
                .padding()
            }
        }
        .navigationBarHidden(true)
        .task(id: selectedDate) {
            // Load trains when date changes
            await viewModel.loadTrains(
                destination: destination,
                fromStationCode: departureStationCode,
                date: selectedDate,
                selectedSystems: effectiveSystems
            )
        }
        .task(id: isViewVisible) {
            // Auto-refresh task that cancels automatically when view disappears
            // Only auto-refresh for today (real-time data)
            guard isViewVisible, !isFutureDate else { return }
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(30))
                guard !Task.isCancelled, isViewVisible, !isFutureDate else { break }
                await viewModel.refreshTrains(date: selectedDate, selectedSystems: effectiveSystems)
            }
        }
        .sheet(isPresented: $showDatePicker) {
            DateSelectorSheet(selectedDate: $selectedDate)
        }
        .onAppear {
            isViewVisible = true

            // Record journey search for Rat Sense
            if let toCode = Stations.getStationCode(destination) {
                RatSenseService.shared.recordJourneySearch(from: departureStationCode, to: toCode)
            }

            // Set the route for immediate blue line drawing on map
            if let destinationCode = Stations.getStationCode(destination) {
                appState.selectedRoute = TripPair(
                    departureCode: departureStationCode,
                    departureName: departureName,
                    destinationCode: destinationCode,
                    destinationName: destination,
                    lastUsed: Date(),
                    isFavorite: false
                )
            }
        }
        .onDisappear {
            // PERFORMANCE: Stop polling when view is not visible
            isViewVisible = false
        }
    }
}

// MARK: - Schedule Info Banner
/// Banner shown when viewing future day schedules
struct ScheduleInfoBanner: View {
    let date: Date

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "calendar")
                .foregroundColor(.white.opacity(0.6))
            Text("Scheduled times for \(date.formatted(.dateTime.weekday(.wide)))")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.7))
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.white.opacity(0.08))
        .cornerRadius(8)
    }
}

// MARK: - Train Card
struct TrainCard: View {
    @EnvironmentObject private var appState: AppState
    let train: TrainV2
    let destination: String
    let departureStationCode: String
    var isFutureDate: Bool = false
    let onTap: () -> Void
    let isExpress: Bool

    // Configuration constants
    private static let DELAY_THRESHOLD_MINUTES = 3

    /// Check if train is scheduled only (not observed)
    /// For future dates, don't show "Scheduled" label since all trains are scheduled
    private var shouldShowScheduledLabel: Bool {
        return train.observationType == "SCHEDULED" && !isFutureDate
    }

    private var isScheduledOnly: Bool {
        return train.observationType == "SCHEDULED"
    }
    
    /// Check if train is cancelled
    private var isCancelled: Bool {
        return train.isCancelled
    }
    
    /// Check if train is boarding at origin
    private var isBoardingAtOrigin: Bool {
        // Use context-aware boarding check and verify track + departure timing
        // Don't show boarding for scheduled-only trains
        return !isScheduledOnly &&
               train.isBoarding(fromStationCode: departureStationCode) &&
               train.track != nil &&
               train.isDepartingSoon(fromStationCode: departureStationCode, withinMinutes: 11)
    }

    /// Check if train has already departed from origin
    private var hasDeparted: Bool {
        return train.hasAlreadyDeparted(fromStationCode: departureStationCode)
    }
    
    private var departureTime: String {
        return train.getFormattedDepartureTime(fromStationCode: departureStationCode)
    }

    private var arrivalTime: String {
        // For V2, we show arrival time if available (best available: actual > updated > scheduled)
        // PERFORMANCE: Use cached static formatter instead of creating new one each call
        if let time = train.arrival?.actualTime ?? train.arrival?.updatedTime ?? train.arrival?.scheduledTime {
            return DateFormatter.easternTimeShort.string(from: time)
        }
        return "--:--"
    }

    /// Departure delay text (e.g., "+8m") if delay >= threshold
    private var departureDelayText: String? {
        let delay = train.delayMinutes
        guard delay >= TrainCard.DELAY_THRESHOLD_MINUTES else { return nil }
        return "+\(delay)m"
    }

    /// Arrival delay text (e.g., "+12m") if delay >= threshold
    private var arrivalDelayText: String? {
        guard let arrivalDelay = train.arrival?.delayMinutes,
              arrivalDelay >= TrainCard.DELAY_THRESHOLD_MINUTES else { return nil }
        return "+\(arrivalDelay)m"
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Train header
            HStack {
                if isBoardingAtOrigin && !isCancelled {
                    Image(systemName: "circle.fill")
                        .foregroundColor(.white)
                        .font(.caption)
                }

                HStack(spacing: 4) {
                    Text(train.displayLabel)
                        .font(.headline)
                        .foregroundColor(isCancelled || hasDeparted ? .black.opacity(0.5) : (isBoardingAtOrigin ? .white : .black))
                        .strikethrough(isCancelled)
                        .lineLimit(1)
                        .minimumScaleFactor(0.8)

                    if isExpress {
                        Image(systemName: "bolt.fill")
                            .font(.caption)
                            .foregroundColor(isCancelled || hasDeparted ? .black.opacity(0.5) : (isBoardingAtOrigin ? .white : .orange))
                    }
                }

                Spacer()

                HStack(spacing: 2) {
                    Text(departureTime)
                        .font(.subheadline)
                        .foregroundColor(isCancelled || hasDeparted ? .black.opacity(0.5) : (isBoardingAtOrigin ? .white.opacity(0.9) : .black.opacity(0.7)))

                    if let depDelay = departureDelayText, !isCancelled && !hasDeparted {
                        Text(depDelay)
                            .font(.caption)
                            .foregroundColor(isBoardingAtOrigin ? .white : .orange)
                    }

                    Text(" → ")
                        .font(.subheadline)
                        .foregroundColor(isCancelled || hasDeparted ? .black.opacity(0.5) : (isBoardingAtOrigin ? .white.opacity(0.9) : .black.opacity(0.7)))

                    Text(arrivalTime)
                        .font(.subheadline)
                        .foregroundColor(isCancelled || hasDeparted ? .black.opacity(0.5) : (isBoardingAtOrigin ? .white.opacity(0.9) : .black.opacity(0.7)))

                    if let arrDelay = arrivalDelayText, !isCancelled && !hasDeparted {
                        Text(arrDelay)
                            .font(.caption)
                            .foregroundColor(isBoardingAtOrigin ? .white : .orange)
                    }
                }
                .fixedSize(horizontal: true, vertical: false)
            }

            // Show cancellation, departed, or scheduled-only status
            if isCancelled {
                Text("Cancelled")
                    .font(.caption)
                    .foregroundColor(.red.opacity(0.8))
                    .fontWeight(.medium)
            } else if hasDeparted {
                Text("Departed")
                    .font(.caption)
                    .foregroundColor(Color.black.opacity(0.5))
            } else if shouldShowScheduledLabel {
                Text("Scheduled")
                    .font(.caption)
                    .foregroundColor(isBoardingAtOrigin ? .white.opacity(0.7) : Color.black.opacity(0.5))
            }

            // Track and status - only show for boarding trains at origin
            if !isCancelled && isBoardingAtOrigin,
               let track = train.track {
                Label("Boarding on Track \(track)", systemImage: "tram.fill")
                    .font(.subheadline)
                    .foregroundColor(.white)
                    .fontWeight(.medium)
            }
        }
        .padding()
        .background(
            isBoardingAtOrigin ? Color.orange.opacity(0.9) : Color.white.opacity(0.9)
        )
        .cornerRadius(TrackRatTheme.CornerRadius.lg)
        .trackRatShadow()
        .opacity(hasDeparted ? 0.7 : 1.0)
        .onTapGesture {
            onTap()
        }
    }
}

// MARK: - StatusV2 Badge
struct StatusV2Badge: View {
    let train: TrainV2
    let departureStationCode: String
    
    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(statusColor)
                .frame(width: 6, height: 6)
            
            Text(statusText)
                .font(.caption)
                .fontWeight(.medium)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(statusColor.opacity(0.2))
        .cornerRadius(TrackRatTheme.CornerRadius.sm)
    }
    
    private var statusColor: Color {
        // Use context-aware status
        let contextStatus = train.calculateStatus(fromStationCode: departureStationCode)
        
        switch contextStatus {
        case .boarding:
            return train.track != nil ? .orange : .gray
        case .departed:
            return .blue
        case .delayed:
            return .red
        case .onTime:
            return .green
        case .scheduled:
            return .gray
        case .cancelled:
            return .red
        case .unknown:
            return .gray
        }
    }
    
    private var statusText: String {
        // Use enhanced display status if available
        if !train.enhancedDisplayStatus.isEmpty {
            return train.enhancedDisplayStatus
        }
        
        // Otherwise use context-aware status
        let contextStatus = train.calculateStatus(fromStationCode: departureStationCode)
        switch contextStatus {
        case .boarding:
            return train.track != nil ? "Boarding" : "Scheduled"
        case .departed:
            return "En Route"
        case .delayed:
            return "Delayed"
        case .onTime:
            return "On Time"
        case .scheduled:
            return "Scheduled"
        case .cancelled:
            return "Cancelled"
        case .unknown:
            return "Unknown"
        }
    }
}

// MARK: - View Model
@MainActor
class TrainListViewModel: ObservableObject {
    @Published var trains: [TrainV2] = []
    @Published var isLoading = false
    @Published var hasStartedLoading = false
    @Published var error: String?
    @Published private(set) var expressTrainIds: Set<String> = []

    private var currentDestination: String?
    private var currentFromStationCode: String?
    private let apiService: APIService

    // MARK: - Express Train Identification
    
    /// Identify express trains using 15% faster travel time threshold
    func identifyExpressTrains() -> Set<String> {
        var expressTrains = Set<String>()
        
        // Group trains by class (NJ Transit vs Amtrak)
        let trainsByClass = Dictionary(grouping: trains) { $0.trainClass }
        
        for (_, trainsInClass) in trainsByClass {
            // Calculate travel time for each train in this class
            let trainsWithTimes = trainsInClass.compactMap { train -> (train: TrainV2, travelTime: TimeInterval)? in
                let travelTime = train.getTravelTime()
                return travelTime > 0 ? (train, travelTime) : nil
            }
            
            // Skip if no trains with valid travel time data
            guard !trainsWithTimes.isEmpty else { continue }
            
            // Find the train with the maximum travel time
            let maxTravelTime = trainsWithTimes.map { $0.travelTime }.max() ?? 0
            
            // Calculate 15% threshold (15% faster = 85% of max time)
            let threshold = maxTravelTime * 0.85
            
            // Identify express trains (15% or more faster)
            for (train, travelTime) in trainsWithTimes {
                if travelTime <= threshold {
                    expressTrains.insert(train.trainId)
                }
            }
        }
        
        return expressTrains
    }
    
    private func sortTrainsByDepartureTime(_ trains: [TrainV2], fromStationCode: String) -> [TrainV2] {
        return trains.sorted { train1, train2 in
            let time1 = train1.getDepartureTime(fromStationCode: fromStationCode) ?? Date.distantFuture
            let time2 = train2.getDepartureTime(fromStationCode: fromStationCode) ?? Date.distantFuture
            return time1 < time2
        }
    }
    
    // Initializer for dependency injection
    @MainActor
    init(apiService: APIService = .shared) {
        self.apiService = apiService
    }

    private var currentDate: Date?

    private var currentSelectedSystems: Set<TrainSystem>?

    func loadTrains(destination: String, fromStationCode: String, date: Date = Date(), selectedSystems: Set<TrainSystem>? = nil) async {
        self.currentDestination = destination
        self.currentFromStationCode = fromStationCode
        self.currentDate = date
        self.currentSelectedSystems = selectedSystems

        isLoading = true
        hasStartedLoading = true
        error = nil

        do {
            guard let toStationCode = Stations.getStationCode(destination) else {
                self.error = "Invalid destination station code for: \(destination)"
                self.isLoading = false
                return
            }

            print("🔍 DEBUG: Loading trains from \(fromStationCode) to \(toStationCode) for date \(date)")

            // Use injected apiService with optional data sources filter
            let fetchedTrains = try await self.apiService.searchTrains(
                fromStationCode: fromStationCode,
                toStationCode: toStationCode,
                date: date,
                dataSources: selectedSystems
            )

            print("🔍 DEBUG: API returned \(fetchedTrains.count) trains")
            print("🔍 DEBUG: Train IDs: \(fetchedTrains.map { $0.trainId })")

            // Filter trains: only exclude trains that have already departed
            let now = Date()
            print("🔍 DEBUG: Current time: \(now)")

            let filteredTrains = fetchedTrains.filter { train in
                // Show trains that haven't departed OR departed within 10 minutes
                if let minutesAgo = train.minutesSinceDeparture(fromStationCode: fromStationCode) {
                    return minutesAgo <= 10
                }
                return true
            }

            print("🔍 DEBUG: After filtering departed trains: \(filteredTrains.count) trains remain")

            // Deduplicate trains by ID to prevent ForEach crashes
            let uniqueTrains = Array(Dictionary(grouping: filteredTrains, by: \.id).compactMapValues(\.first).values)

            print("🔍 DEBUG: After deduplication: \(uniqueTrains.count) unique trains")
            print("🔍 DEBUG: Unique train IDs: \(uniqueTrains.map { $0.trainId })")

            // Sort trains by origin station departure time
            trains = sortTrainsByDepartureTime(uniqueTrains, fromStationCode: fromStationCode)

            // PERFORMANCE: Calculate express trains once, not on every render
            expressTrainIds = identifyExpressTrains()

            print("🔍 DEBUG: Final sorted trains count: \(trains.count)")
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
    }
    
    func refreshTrains(date: Date = Date(), selectedSystems: Set<TrainSystem>? = nil) async {
        guard let destination = currentDestination,
              let fromStationCode = currentFromStationCode,
              let toStationCode = Stations.getStationCode(destination) else {
            return // Or set an error if appropriate for silent refresh
        }

        // Use provided systems or fall back to stored systems
        let systems = selectedSystems ?? currentSelectedSystems

        do {
            // Use injected apiService with optional data sources filter
            let fetchedTrains = try await self.apiService.searchTrains(
                fromStationCode: fromStationCode,
                toStationCode: toStationCode,
                date: date,
                dataSources: systems
            )

            let now = Date()
            let sixHoursFromNow = now.addingTimeInterval(6 * 60 * 60)
            
            let filteredTrains = fetchedTrains.filter { train in
                let departureTime = train.getDepartureTime(fromStationCode: fromStationCode) ?? Date.distantFuture
                let isWithinTimeWindow = departureTime <= sixHoursFromNow

                // Show trains that haven't departed OR departed within 10 minutes
                if let minutesAgo = train.minutesSinceDeparture(fromStationCode: fromStationCode) {
                    return minutesAgo <= 10
                }
                return isWithinTimeWindow
            }
            
            // Deduplicate trains by ID to prevent ForEach crashes
            let uniqueTrains = Array(Dictionary(grouping: filteredTrains, by: \.id).compactMapValues(\.first).values)
            
            // Sort trains by origin station departure time
            let newTrains = sortTrainsByDepartureTime(uniqueTrains, fromStationCode: fromStationCode)
            
            // Check for boarding status changes (StatusV2 only)
            for train in trains {
                if let newTrain = newTrains.first(where: { $0.id == train.id }) {
                    if !train.isBoarding(fromStationCode: fromStationCode) && newTrain.isBoarding(fromStationCode: fromStationCode) {
                        // Haptic feedback for boarding status
                        UINotificationFeedbackGenerator().notificationOccurred(.warning)
                    }
                }
            }
            
            // Update trains list with new data
            trains = newTrains

            // PERFORMANCE: Recalculate express trains when data changes
            expressTrainIds = identifyExpressTrains()

        } catch {
            // Silent failure for background refresh
            print("TrainListViewModel: Silent refresh failed: \(error.localizedDescription)")
        }
    }
}

// MARK: - Helper Views
struct ErrorView: View {
    let message: String
    let retry: () -> Void
    
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundColor(.red)
            
            Text(message)
                .multilineTextAlignment(.center)
                .foregroundColor(.white)
            
            Button("Retry") {
                retry()
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
        .frame(maxWidth: .infinity)
    }
}

struct EmptyStateView: View {
    let message: String
    
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "tram")
                .font(.largeTitle)
                .foregroundColor(.white.opacity(0.5))
            
            Text(message)
                .foregroundColor(.white.opacity(0.7))
        }
        .padding()
        .frame(maxWidth: .infinity, minHeight: 200)
    }
}

#Preview {
    NavigationStack {
        TrainListView(destination: "Newark Penn Station", departureStationCode: "NY")
            .environmentObject(AppState())
    }
}
