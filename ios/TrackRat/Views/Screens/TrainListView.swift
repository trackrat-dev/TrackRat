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
    let train: TrainV2
    let destination: String
    let onTap: () -> Void
    
    /// Check if train is cancelled
    private var isCancelled: Bool {
        return train.status == .delayed  // V2 maps CANCELLED to delayed
    }
    
    /// Check if train is boarding at origin
    private var isBoardingAtOrigin: Bool {
        guard let departureCode = appState.departureStationCode else {
            return false
        }
        
        // Check if train is boarding, we're at the origin, has track, and departing within 11 minutes
        return train.isBoarding && 
               train.originStationCode == departureCode && 
               train.track != nil &&
               train.isDepartingSoon(fromStationCode: departureCode, withinMinutes: 11)
    }
    
    private var departureTime: String {
        if let departureCode = appState.departureStationCode {
            return train.getFormattedDepartureTime(fromStationCode: departureCode)
        }
        let formatter = DateFormatter.easternTime(time: .short)
        return formatter.string(from: train.departureTime)
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
                    let hasDepDelay = train.delayMinutes >= 2
                    let hasArrDelay = train.arrival?.delayMinutes ?? 0 >= 2
                    
                    if hasDepDelay || hasArrDelay {
                        Text("Operating with Delays")
                            .font(.caption)
                            .foregroundColor(.red.opacity(0.8))
                            .fontWeight(.medium)
                    }
                }
                
                // Track and status - only show for boarding trains at origin
                if !isCancelled && isBoardingAtOrigin,
                   let departureCode = appState.departureStationCode,
                   let track = train.track {
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
    let train: TrainV2
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
        switch train.status {
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
        case .unknown:
            return .gray
        }
    }
    
    private var statusText: String {
        // Use enhanced display status if available
        if !train.enhancedDisplayStatus.isEmpty {
            return train.enhancedDisplayStatus
        }
        
        // Otherwise use basic status
        switch train.status {
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
    @Published var error: String?
    
    private var currentDestination: String?
    private var currentFromStationCode: String?
    private let apiService: APIService
    
    // Timer for auto-refresh
    let timer = Timer.publish(every: 30, on: .main, in: .common).autoconnect()
    
    private func sortTrainsByDepartureTime(_ trains: [TrainV2], fromStationCode: String) -> [TrainV2] {
        return trains.sorted { train1, train2 in
            let time1 = train1.getDepartureTime(fromStationCode: fromStationCode) ?? Date.distantFuture
            let time2 = train2.getDepartureTime(fromStationCode: fromStationCode) ?? Date.distantFuture
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
                let departureTime = train.getDepartureTime(fromStationCode: fromStationCode) ?? Date.distantFuture
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
                let departureTime = train.getDepartureTime(fromStationCode: fromStationCode) ?? Date.distantFuture
                return departureTime <= sixHoursFromNow
            }
            
            // Sort trains by origin station departure time
            let newTrains = sortTrainsByDepartureTime(filteredTrains, fromStationCode: fromStationCode)
            
            // Check for boarding status changes (StatusV2 only)
            for train in trains {
                if let newTrain = newTrains.first(where: { $0.id == train.id }) {
                    if !train.isBoarding && newTrain.isBoarding {
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