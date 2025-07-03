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
    
    /// Check if train is cancelled
    private var isCancelled: Bool {
        return train.statusV2?.current == "CANCELLED"
    }
    
    /// Check if train is boarding specifically at the user's origin station (StatusV2 only)
    private var isBoardingAtOrigin: Bool {
        guard let statusV2 = train.statusV2,
              let departureCode = appState.departureStationCode else {
            return false
        }
        
        // Only show boarding if the train is actually boarding
        guard statusV2.current == "BOARDING" else {
            return false
        }
        
        // Check if the boarding is happening at the user's origin station
        // Method 1: Check if StatusV2 source starts with user's station code
        if statusV2.source.hasPrefix(departureCode) {
            // Verify we have a track for this station
            return train.getTrackForStation(departureCode) != nil
        }
        
        // Method 2: Check if StatusV2 location mentions user's station
        if let selectedDeparture = appState.selectedDeparture {
            let userStationName = Stations.displayName(for: selectedDeparture)
            if statusV2.location.lowercased().contains(userStationName.lowercased()) {
                // Verify we have a track for this station
                return train.getTrackForStation(departureCode) != nil
            }
        }
        
        // If StatusV2 indicates boarding elsewhere, don't show boarding status
        return false
    }
    
    private var departureTime: String {
        if let departureCode = appState.departureStationCode {
            return train.getFormattedScheduledDepartureTime(fromStationCode: departureCode)
        }
        let formatter = DateFormatter.easternTime(time: .short)
        return formatter.string(from: train.departureTime)
    }
    
    private var arrivalTime: String {
        return train.getFormattedScheduledArrivalTime(toStationName: destination)
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
                        
                        if isCancelled {
                            Text("🚫")
                                .font(.headline)
                        }
                    }
                    
                    Spacer()
                    
                    HStack(spacing: 2) {
                        Text(departureTime)
                            .font(.subheadline)
                            .foregroundColor(isCancelled ? .black.opacity(0.5) : (isBoardingAtOrigin ? .white.opacity(0.9) : .black.opacity(0.7)))
                        
                        // Departure delay
                        if !isCancelled,
                           let depDelay = train.getDepartureDelay(fromStationCode: appState.departureStationCode ?? ""),
                           depDelay >= 2 {
                            Text("+\(depDelay)")
                                .font(.caption)
                                .foregroundColor(isBoardingAtOrigin ? .white : .red)
                                .fontWeight(.medium)
                        }
                        
                        Text(" → ")
                            .font(.subheadline)
                            .foregroundColor(isCancelled ? .black.opacity(0.5) : (isBoardingAtOrigin ? .white.opacity(0.9) : .black.opacity(0.7)))
                        
                        Text(arrivalTime)
                            .font(.subheadline)
                            .foregroundColor(isCancelled ? .black.opacity(0.5) : (isBoardingAtOrigin ? .white.opacity(0.9) : .black.opacity(0.7)))
                        
                        // Arrival delay
                        if !isCancelled,
                           let arrDelay = train.getArrivalDelay(toStationName: destination),
                           arrDelay >= 2 {
                            Text("+\(arrDelay)")
                                .font(.caption)
                                .foregroundColor(isBoardingAtOrigin ? .white : .red)
                                .fontWeight(.medium)
                        }
                    }
                }
                
                // Show cancellation location
                if isCancelled, let cancellationLocation = train.cancellationLocation {
                    Text("Cancelled at \(cancellationLocation)")
                        .font(.caption)
                        .foregroundColor(.red.opacity(0.8))
                        .fontWeight(.medium)
                }
                
                // Track and status - only show for boarding trains at origin
                if !isCancelled && isBoardingAtOrigin,
                   let departureCode = appState.departureStationCode,
                   let track = train.getTrackForStation(departureCode) {
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

// MARK: - StatusV2 Badge
struct StatusV2Badge: View {
    let train: Train
    let departureStationCode: String?
    
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
        guard let statusV2 = train.statusV2 else {
            return .gray
        }
        
        switch statusV2.current {
        case "BOARDING":
            let hasTrack = departureStationCode != nil ? train.getTrackForStation(departureStationCode!) != nil : train.track != nil
            return hasTrack ? .orange : .gray
        case "EN_ROUTE":
            return .blue
        case "ARRIVED":
            return .green
        case "DELAYED":
            return .red
        case "CANCELLED":
            return .red
        default:
            return .gray
        }
    }
    
    private var statusText: String {
        guard let statusV2 = train.statusV2 else {
            return "Unknown"
        }
        
        switch statusV2.current {
        case "BOARDING":
            let hasTrack = departureStationCode != nil ? train.getTrackForStation(departureStationCode!) != nil : train.track != nil
            return hasTrack ? "Boarding" : "Scheduled"
        case "EN_ROUTE":
            return "En Route"
        case "ARRIVED":
            return "Arrived"
        case "DELAYED":
            return "Delayed"
        case "CANCELLED":
            return "Cancelled"
        case "SCHEDULED":
            return "Scheduled"
        default:
            return statusV2.current.replacingOccurrences(of: "_", with: " ").capitalized
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
    private let apiService: APIService
    
    // Timer for auto-refresh
    let timer = Timer.publish(every: 30, on: .main, in: .common).autoconnect()
    
    private func sortTrainsByDepartureTime(_ trains: [Train], fromStationCode: String) -> [Train] {
        return trains.sorted { train1, train2 in
            let time1 = train1.getDepartureTime(fromStationCode: fromStationCode)
            let time2 = train2.getDepartureTime(fromStationCode: fromStationCode)
            return time1 < time2
        }
    }
    
    // Initializer for dependency injection
    init(apiService: APIService = .shared) {
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
            
            // Sort trains by origin station departure time
            trains = sortTrainsByDepartureTime(filteredTrains, fromStationCode: fromStationCode)
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
                let departureTime = train.getDepartureTime(fromStationCode: fromStationCode)
                return departureTime <= sixHoursFromNow
            }
            
            // Sort trains by origin station departure time
            let newTrains = sortTrainsByDepartureTime(filteredTrains, fromStationCode: fromStationCode)
            
            // Check for boarding status changes (StatusV2 only)
            for train in trains {
                if let newTrain = newTrains.first(where: { $0.id == train.id }) {
                    if !train.isActuallyBoarding && newTrain.isActuallyBoarding {
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