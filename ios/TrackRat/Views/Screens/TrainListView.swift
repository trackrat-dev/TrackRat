import SwiftUI
import Combine

struct TrainListView: View {
    @EnvironmentObject private var appState: AppState
    @StateObject private var viewModel: TrainListViewModel
    
    let destination: String
    
    private var isCurrentRouteFavorited: Bool {
        guard let _ = appState.selectedDeparture,
              let departureCode = appState.departureStationCode,
              let destinationCode = Stations.getStationCode(destination) else {
            return false
        }
        
        return appState.getFavoriteTrips().contains { trip in
            trip.departureCode == departureCode &&
            trip.destinationCode == destinationCode
        }
    }
    
    init(destination: String) {
        self.destination = destination
        self._viewModel = StateObject(wrappedValue: TrainListViewModel())
    }
    
    var body: some View {
        ZStack {
            // Black gradient background
            TrackRatTheme.Colors.primaryGradient
                .ignoresSafeArea()
            
            ScrollView {
                    VStack(spacing: 16) {
                        if viewModel.isLoading && viewModel.trains.isEmpty {
                            TrackRatLoadingView(message: "Finding your trains...")
                                .frame(maxWidth: .infinity, minHeight: 200)
                        } else if let error = viewModel.error {
                            ErrorView(message: error) {
                                Task {
                                    await viewModel.loadTrains(
                                        destination: destination,
                                        fromStationCode: appState.departureStationCode ?? "NY"
                                    )
                                }
                            }
                        } else if viewModel.trains.isEmpty {
                            EmptyStateView(message: "No trains found")
                        } else {
                            ForEach(viewModel.trains) { train in
                                TrainCard(train: train, destination: destination) {
                                    appState.currentTrainId = train.id
                                    // Use flexible navigation with train number
                                    appState.navigationPath.append(NavigationDestination.trainDetailsFlexible(
                                        trainNumber: train.trainId,
                                        fromStation: appState.departureStationCode
                                    ))
                                }
                            }
                        }
                    }
                    .padding()
                }
                .refreshable {
                    await viewModel.loadTrains(
                        destination: destination,
                        fromStationCode: appState.departureStationCode ?? "NY"
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
                    if let departure = appState.selectedDeparture {
                        Text("from \(Stations.displayName(for: departure))")
                            .font(.caption2)
                            .foregroundColor(.white.opacity(0.8))
                    }
                }
            }
            
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    toggleCurrentRouteFavorite()
                } label: {
                    Image(systemName: isCurrentRouteFavorited ? "heart.fill" : "heart")
                        .font(.system(size: 20))
                        .foregroundColor(.orange)
                }
            }
        }
        .task {
            await viewModel.loadTrains(
                destination: destination,
                fromStationCode: appState.departureStationCode ?? "NY"
            )
        }
        .onReceive(viewModel.timer) { _ in
            Task {
                await viewModel.refreshTrains()
            }
        }
        .onAppear {
            // No longer auto-save trips
        }
    }
    
    private func toggleCurrentRouteFavorite() {
        guard let departure = appState.selectedDeparture,
              let departureCode = appState.departureStationCode,
              let destinationCode = Stations.getStationCode(destination) else {
            return
        }
        
        let currentTrip = TripPair(
            departureCode: departureCode,
            departureName: departure,
            destinationCode: destinationCode,
            destinationName: destination,
            lastUsed: Date(),
            isFavorite: false // This will be toggled by the toggle function
        )
        
        appState.toggleFavorite(currentTrip)
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }
}

// MARK: - Train Card
struct TrainCard: View {
    @EnvironmentObject private var appState: AppState
    let train: Train
    let destination: String
    let onTap: () -> Void
    
    /// Check if train is boarding specifically at the user's origin station
    private var isBoardingAtOrigin: Bool {
        guard train.status == .boarding,
              let departureCode = appState.departureStationCode,
              let stops = train.stops else {
            return false
        }
        
        // Find the stop that matches the user's departure station using robust matching
        let originStop = stops.first { stop in
            return Stations.stationMatches(stop, stationCode: departureCode)
        }
        
        // Train is boarding at origin if it hasn't departed from that station yet
        return !(originStop?.departed ?? true)
    }
    
    private var departureTime: String {
        if let departureCode = appState.departureStationCode {
            return train.getFormattedDepartureTime(fromStationCode: departureCode)
        }
        let formatter = DateFormatter.easternTime(time: .short)
        return formatter.string(from: train.departureTime)
    }
    
    private var arrivalTime: String {
        // Find the stop that matches the destination the user searched for
        if let destinationStop = train.stops?.first(where: { 
            $0.stationName.lowercased().contains(destination.lowercased()) 
        }) {
            let formatter = DateFormatter.easternTime(time: .short)
            if let scheduledTime = destinationStop.scheduledTime {
                return formatter.string(from: scheduledTime)
            } else if let departureTime = destinationStop.departureTime {
                return formatter.string(from: departureTime)
            }
        }
        return "—"
    }
    
    var body: some View {
        Button(action: onTap) {
            VStack(alignment: .leading, spacing: 12) {
                // Train header
                HStack {
                    if isBoardingAtOrigin {
                        Image(systemName: "circle.fill")
                            .foregroundColor(.white)
                            .font(.caption)
                    }
                    
                    Text("Train \(train.trainId)")
                        .font(.headline)
                        .foregroundColor(isBoardingAtOrigin ? .white : .black)
                    
                    Spacer()
                    
                    Text("\(departureTime) → \(arrivalTime)")
                        .font(.subheadline)
                        .foregroundColor(isBoardingAtOrigin ? .white.opacity(0.9) : .black.opacity(0.7))
                }
                
                // Track and status - only show for boarding trains at origin
                if isBoardingAtOrigin, let track = train.track {
                    Label("Boarding on Track \(track)", systemImage: "tram.fill")
                        .font(.subheadline)
                        .foregroundColor(.white)
                        .fontWeight(.medium)
                }
            }
            .padding()
            .background(isBoardingAtOrigin ? Color.orange.opacity(0.9) : Color.white.opacity(0.9))
            .cornerRadius(16)
            .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Status Badge
struct StatusBadge: View {
    let status: TrainStatus
    let delayMinutes: Int?
    
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
        switch status {
        case .onTime: return .green
        case .delayed: return .red
        case .boarding: return .orange
        case .departed: return .gray
        case .scheduled: return .gray
        case .unknown: return .gray
        }
    }
    
    private var statusText: String {
        switch status {
        case .onTime: return "On Time"
        case .delayed:
            if let minutes = delayMinutes {
                return "Delayed \(minutes)min"
            }
            return "Delayed"
        case .boarding: return "Boarding"
        case .departed: return "Departed"
        case .scheduled: return "Scheduled"
        case .unknown: return "Unknown"
        }
    }
}

// MARK: - View Model
@MainActor
class TrainListViewModel: ObservableObject {
    @Published var trains: [Train] = []
    @Published var isLoading = false
    @Published var error: String?
    
    private var currentDestination: String?
    private var currentFromStationCode: String?
    private let apiService: APIServiceProtocol // MODIFIED
    
    // Timer for auto-refresh
    let timer = Timer.publish(every: 30, on: .main, in: .common).autoconnect()
    
    // MODIFIED: Inject APIServiceProtocol, default to APIService.shared
    init(apiService: APIServiceProtocol = APIService.shared) {
        self.apiService = apiService
    }

    func loadTrains(destination: String, fromStationCode: String) async {
        self.currentDestination = destination
        self.currentFromStationCode = fromStationCode
        
        isLoading = true
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
            
            // Filter out trains departing more than 6 hours from now
            let now = Date()
            let sixHoursFromNow = now.addingTimeInterval(6 * 60 * 60)
            
            let filteredTrains = fetchedTrains.filter { train in
                let departureTime = train.getDepartureTime(fromStationCode: fromStationCode)
                return departureTime <= sixHoursFromNow
            }
            
            // Sort trains based on their departure time from 'fromStationCode'
            trains = filteredTrains.sorted { t1, t2 in
                let time1 = t1.getDepartureTime(fromStationCode: fromStationCode)
                let time2 = t2.getDepartureTime(fromStationCode: fromStationCode)
                return time1 < time2
            }
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
            
            // Filter and sort logic from API response (based on getDepartureTime from fromStationCode)
            let apiFilteredAndSortedTrains = fetchedTrains
                .filter { train in
                    train.getDepartureTime(fromStationCode: fromStationCode) <= sixHoursFromNow
                }
                .sorted { t1, t2 in
                    t1.getDepartureTime(fromStationCode: fromStationCode) < t2.getDepartureTime(fromStationCode: fromStationCode)
                }

            // Logic to update existing trains and add new ones
            var updatedTrainList: [Train] = []
            var existingTrainIDs = Set(self.trains.map { $0.id })

            for apiTrain in apiFilteredAndSortedTrains {
                if let index = self.trains.firstIndex(where: { $0.id == apiTrain.id }) {
                    // Update existing train, check for haptic
                    let oldTrain = self.trains[index]
                    if oldTrain.status != .boarding && apiTrain.status == .boarding {
                        // Consider moving haptic to View via a published property change
                        UINotificationFeedbackGenerator().notificationOccurred(.warning)
                    }
                    updatedTrainList.append(apiTrain) // Replace with new data
                } else {
                    updatedTrainList.append(apiTrain) // Add new train
                }
                existingTrainIDs.remove(apiTrain.id) // Remove processed IDs
            }
            
            // Add back any existing trains that were not in the API response but should persist (if any specific logic dictates this)
            // For now, assuming the API is the source of truth for the current list.
            // If trains should be removed if not in API response, updatedTrainList is correct.
            // If they should persist and only be updated, logic would be different.
            // Current view model code replaces the list, so this is fine.

            // Final sort of the combined list using the main `departureTime` property of the `Train` struct.
            self.trains = updatedTrainList.sorted { $0.departureTime < $1.departureTime }
            
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