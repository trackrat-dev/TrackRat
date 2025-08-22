import SwiftUI
import Combine

struct TrainListView: View {
    @EnvironmentObject private var appState: AppState
    @StateObject private var viewModel: TrainListViewModel
    
    // Configuration constants
    private static let DELAY_THRESHOLD_MINUTES = 6
    
    @State private var destination: String
    @State private var departureStationCode: String
    @State private var departureName: String
    
    
    init(destination: String) {
        self._destination = State(initialValue: destination)
        self._departureStationCode = State(initialValue: "")
        self._departureName = State(initialValue: "")
        self._viewModel = StateObject(wrappedValue: TrainListViewModel())
    }
    
    var body: some View {
        ZStack {
            // Black gradient background
            TrackRatTheme.Colors.primaryBackground
                .ignoresSafeArea()
            
            ScrollView {
                    VStack(spacing: 16) {
                        if viewModel.isLoading || (!viewModel.hasStartedLoading && viewModel.trains.isEmpty) {
                            TrackRatLoadingView(message: "Finding your trains...")
                                .frame(maxWidth: .infinity, minHeight: 200)
                        } else if let error = viewModel.error {
                            ErrorView(message: error) {
                                Task {
                                    await viewModel.loadTrains(
                                        destination: destination,
                                        fromStationCode: departureStationCode
                                    )
                                }
                            }
                        } else if viewModel.trains.isEmpty {
                            EmptyStateView(message: "No trains found")
                        } else {
                            let expressTrains = viewModel.identifyExpressTrains()
                            ForEach(viewModel.trains) { train in
                                TrainCard(
                                    train: train, 
                                    destination: destination, 
                                    departureStationCode: departureStationCode,
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
                                        
                                        // Use flexible navigation with train number
                                        appState.navigationPath.append(NavigationDestination.trainDetailsFlexible(
                                            trainNumber: train.trainId,
                                            fromStation: departureStationCode
                                        ))
                                    },
                                    isExpress: expressTrains.contains(train.trainId)
                                )
                            }
                        }
                    }
                    .padding()
                }
                .refreshable {
                    await viewModel.loadTrains(
                        destination: destination,
                        fromStationCode: departureStationCode
                    )
                }
            }
        .navigationTitle(destination)
        .navigationBarTitleDisplayMode(.inline)
        .glassmorphicNavigationBar()
        .toolbar {
            ToolbarItem(placement: .principal) {
                VStack(spacing: 0) {
                    Text(destination)
                        .font(.headline)
                        .foregroundColor(.white)
                    if !departureName.isEmpty {
                        Text("from \(Stations.displayName(for: departureName))")
                            .font(.caption2)
                            .foregroundColor(.white.opacity(0.8))
                    }
                }
            }
            
            ToolbarItem(placement: .navigationBarTrailing) {
                Button("Close") {
                    appState.navigationPath = NavigationPath()
                }
                .foregroundColor(.white)
                .font(.body)
            }
        }
        .task {
            await viewModel.loadTrains(
                destination: destination,
                fromStationCode: departureStationCode
            )
        }
        .onReceive(viewModel.timer) { _ in
            Task {
                await viewModel.refreshTrains()
            }
        }
        .onAppear {
            // Initialize state from app state
            if departureStationCode.isEmpty {
                departureStationCode = appState.departureStationCode ?? "NY"
                departureName = appState.selectedDeparture ?? ""
            }
            
            // Record journey search for Rat Sense
            if let fromCode = appState.departureStationCode,
               let toCode = appState.destinationStationCode {
                RatSenseService.shared.recordJourneySearch(from: fromCode, to: toCode)
            }
            
            // Set the route for immediate blue line drawing on map
            // Use appState values directly to ensure we have the correct values
            if let destinationCode = Stations.getStationCode(destination),
               let depCode = appState.departureStationCode,
               let depName = appState.selectedDeparture {
                appState.selectedRoute = TripPair(
                    departureCode: depCode,
                    departureName: depName,
                    destinationCode: destinationCode,
                    destinationName: destination,
                    lastUsed: Date(),
                    isFavorite: false
                )
            }
        }
    }
}

// MARK: - Train Card
struct TrainCard: View {
    @EnvironmentObject private var appState: AppState
    let train: TrainV2
    let destination: String
    let departureStationCode: String
    let onTap: () -> Void
    let isExpress: Bool
    
    // Configuration constants
    private static let DELAY_THRESHOLD_MINUTES = 6
    
    /// Check if train is cancelled
    private var isCancelled: Bool {
        return train.isCancelled
    }
    
    /// Check if train is boarding at origin
    private var isBoardingAtOrigin: Bool {
        // Use context-aware boarding check and verify track + departure timing
        return train.isBoarding(fromStationCode: departureStationCode) && 
               train.track != nil &&
               train.isDepartingSoon(fromStationCode: departureStationCode, withinMinutes: 11)
    }
    
    private var departureTime: String {
        return train.getFormattedDepartureTime(fromStationCode: departureStationCode)
    }
    
    private var arrivalTime: String {
        // For V2, we show arrival time if available
        if let arrivalTime = train.arrival?.scheduledTime {
            let formatter = DateFormatter.easternTime(time: .short)
            return formatter.string(from: arrivalTime)
        }
        return "--:--"
    }
    
    var body: some View {
        Button(action: onTap) {
            VStack(alignment: .leading, spacing: 12) {
                // Train header
                HStack {
                    if isBoardingAtOrigin && !isCancelled {
                        Image(systemName: "circle.fill")
                            .foregroundColor(.white)
                            .font(.caption)
                    }
                    
                    HStack(spacing: 4) {
                        Text("Train \(train.trainId)")
                            .font(.headline)
                            .foregroundColor(isCancelled ? .black.opacity(0.7) : (isBoardingAtOrigin ? .white : .black))
                            .strikethrough(isCancelled)
                        
                        if isExpress {
                            Image(systemName: "bolt.fill")
                                .font(.caption)
                                .foregroundColor(isCancelled ? .black.opacity(0.7) : (isBoardingAtOrigin ? .white : .orange))
                        }
                    }
                    
                    Spacer()
                    
                    HStack(spacing: 2) {
                        Text(departureTime)
                            .font(.subheadline)
                            .foregroundColor(isCancelled ? .black.opacity(0.5) : (isBoardingAtOrigin ? .white.opacity(0.9) : .black.opacity(0.7)))
                        
                        
                        Text(" → ")
                            .font(.subheadline)
                            .foregroundColor(isCancelled ? .black.opacity(0.5) : (isBoardingAtOrigin ? .white.opacity(0.9) : .black.opacity(0.7)))
                        
                        Text(arrivalTime)
                            .font(.subheadline)
                            .foregroundColor(isCancelled ? .black.opacity(0.5) : (isBoardingAtOrigin ? .white.opacity(0.9) : .black.opacity(0.7)))
                        
                    }
                }
                
                // Show cancellation location
                if isCancelled {
                    Text("Cancelled")
                        .font(.caption)
                        .foregroundColor(.red.opacity(0.8))
                        .fontWeight(.medium)
                }
                
                // Show delay status
                if !isCancelled {
                    let hasDepDelay = train.delayMinutes >= TrainCard.DELAY_THRESHOLD_MINUTES
                    let hasArrDelay = train.arrival?.delayMinutes ?? 0 >= TrainCard.DELAY_THRESHOLD_MINUTES
                    
                    if hasDepDelay || hasArrDelay {
                        Text("Operating with Delays")
                            .font(.caption)
                            .foregroundColor(.red.opacity(0.8))
                            .fontWeight(.medium)
                    }
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
            .cornerRadius(16)
            .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
        }
        .buttonStyle(.plain)
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
        .cornerRadius(8)
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
    
    private var currentDestination: String?
    private var currentFromStationCode: String?
    private let apiService: APIService
    
    // Timer for auto-refresh
    let timer = Timer.publish(every: 30, on: .main, in: .common).autoconnect()
    
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

    func loadTrains(destination: String, fromStationCode: String) async {
        self.currentDestination = destination
        self.currentFromStationCode = fromStationCode
        
        isLoading = true
        hasStartedLoading = true
        error = nil
        
        do {
            guard let toStationCode = Stations.getStationCode(destination) else {
                self.error = "Invalid destination station code for: \(destination)"
                self.isLoading = false
                return
            }
            // Use injected apiService
            let fetchedTrains = try await self.apiService.searchTrains(
                fromStationCode: fromStationCode,
                toStationCode: toStationCode
            )
            
            // Filter trains: within 6 hours and haven't already departed
            let now = Date()
            let sixHoursFromNow = now.addingTimeInterval(6 * 60 * 60)
            
            let filteredTrains = fetchedTrains.filter { train in
                let departureTime = train.getDepartureTime(fromStationCode: fromStationCode) ?? Date.distantFuture
                let isWithinTimeWindow = departureTime <= sixHoursFromNow
                let hasNotDeparted = !train.hasAlreadyDeparted(fromStationCode: fromStationCode)
                
                return isWithinTimeWindow && hasNotDeparted
            }
            
            // Deduplicate trains by ID to prevent ForEach crashes
            let uniqueTrains = Array(Dictionary(grouping: filteredTrains, by: \.id).compactMapValues(\.first).values)
            
            // Sort trains by origin station departure time
            trains = sortTrainsByDepartureTime(uniqueTrains, fromStationCode: fromStationCode)
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
    }
    
    func refreshTrains() async {
        guard let destination = currentDestination,
              let fromStationCode = currentFromStationCode,
              let toStationCode = Stations.getStationCode(destination) else {
            return // Or set an error if appropriate for silent refresh
        }
        
        do {
            // Use injected apiService
            let fetchedTrains = try await self.apiService.searchTrains(
                fromStationCode: fromStationCode,
                toStationCode: toStationCode
            )
            
            let now = Date()
            let sixHoursFromNow = now.addingTimeInterval(6 * 60 * 60)
            
            let filteredTrains = fetchedTrains.filter { train in
                let departureTime = train.getDepartureTime(fromStationCode: fromStationCode) ?? Date.distantFuture
                let isWithinTimeWindow = departureTime <= sixHoursFromNow
                let hasNotDeparted = !train.hasAlreadyDeparted(fromStationCode: fromStationCode)
                
                return isWithinTimeWindow && hasNotDeparted
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
        TrainListView(destination: "Newark Penn Station")
            .environmentObject(AppState())
    }
}