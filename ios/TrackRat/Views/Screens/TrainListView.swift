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
        
        // Find the stop that matches the user's departure station
        let originStop = stops.first { stop in
            // Match by station code if available
            if let stationCode = stop.stationCode {
                return stationCode == departureCode
            }
            // Fall back to matching by station name
            return Stations.getStationCode(stop.stationName) == departureCode
        }
        
        // Train is boarding at origin if it hasn't departed from that station yet
        return originStop?.departed == false
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
    private let apiService = APIService.shared
    
    // Timer for auto-refresh
    let timer = Timer.publish(every: 30, on: .main, in: .common).autoconnect()
    
    func loadTrains(destination: String, fromStationCode: String) async {
        self.currentDestination = destination
        self.currentFromStationCode = fromStationCode
        
        isLoading = true
        error = nil
        
        do {
            guard let toStationCode = Stations.getStationCode(destination) else {
                throw APIError.invalidURL
            }
            let fetchedTrains = try await apiService.searchTrains(
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
            
            // Sort trains by origin station departure time
            trains = filteredTrains.sorted { train1, train2 in
                let time1 = train1.getDepartureTime(fromStationCode: fromStationCode)
                let time2 = train2.getDepartureTime(fromStationCode: fromStationCode)
                return time1 < time2
            }
        } catch {
            self.error = error.localizedDescription
        }
        
        isLoading = false
    }
    
    func refreshTrains() async {
        // Silent refresh without showing loading state
        guard let destination = currentDestination,
              let fromStationCode = currentFromStationCode,
              let toStationCode = Stations.getStationCode(destination) else {
            return
        }
        
        do {
            let fetchedTrains = try await apiService.searchTrains(
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
            
            // Sort trains by origin station departure time
            let newTrains = filteredTrains.sorted { train1, train2 in
                let time1 = train1.getDepartureTime(fromStationCode: fromStationCode)
                let time2 = train2.getDepartureTime(fromStationCode: fromStationCode)
                return time1 < time2
            }
            
            // Check for boarding status changes
            for (index, train) in trains.enumerated() {
                if let newTrain = newTrains.first(where: { $0.id == train.id }) {
                    if train.status != .boarding && newTrain.status == .boarding {
                        // Haptic feedback for boarding status
                        UINotificationFeedbackGenerator().notificationOccurred(.warning)
                    }
                    trains[index] = newTrain
                }
            }
            
            // Add any new trains
            for newTrain in newTrains {
                if !trains.contains(where: { $0.id == newTrain.id }) {
                    trains.append(newTrain)
                }
            }
            
            // Sort by departure time
            trains.sort { $0.departureTime < $1.departureTime }
            
        } catch {
            // Silent failure for background refresh
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