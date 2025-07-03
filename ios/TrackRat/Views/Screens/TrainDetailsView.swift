import SwiftUI
import Combine

struct TrainDetailsView: View {
    @EnvironmentObject private var appState: AppState
    @StateObject private var viewModel: TrainDetailsViewModel
    // @State private var showingHistory = false // REMOVE THIS LINE
    
    let trainId: Int  // Keep for backwards compatibility
    
    // Legacy initializer for database ID
    init(trainId: Int) {
        self.trainId = trainId
        let VModel = TrainDetailsViewModel(trainId: trainId)
        self._viewModel = StateObject(wrappedValue: VModel)
    }
    
    // New initializer for train number
    init(trainNumber: String, fromStation: String? = nil) {
        self.trainId = 0  // Not used for train number based initialization
        let VModel = TrainDetailsViewModel(
            databaseId: nil,
            trainNumber: trainNumber,
            fromStationCode: fromStation
        )
        self._viewModel = StateObject(wrappedValue: VModel)
    }
    
    private var shouldShowHistoricalData: Bool {
        StorageService().loadServerEnvironment().supportsHistoricalData
    }
    
    var body: some View {
        ZStack {
            // Black gradient background
            TrackRatTheme.Colors.primaryGradient
                .ignoresSafeArea()
            
            ScrollView {
                    if viewModel.isLoading && viewModel.train == nil {
                        TrackRatLoadingView(message: "Loading train details...")
                            .frame(maxWidth: .infinity, minHeight: 400)
                    } else if let error = viewModel.error {
                        ErrorView(message: error) {
                            Task {
                                await viewModel.loadTrainDetails(
                                    fromStationCode: appState.departureStationCode,
                                    selectedDestinationName: appState.selectedDestination
                                )
                            }
                        }
                    } else if let train = viewModel.train {
                        CombinedDetailsCard(
                            train: train,
                            selectedDestination: appState.selectedDestination,
                            displayableTrainStops: viewModel.displayableTrainStops,
                            hasPreviousDisplayStops: viewModel.hasPreviousDisplayStops,
                            hasMoreDisplayStops: viewModel.hasMoreDisplayStops,
                            journeyProgressPercentage: viewModel.journeyProgressPercentage,
                            journeyStopsCompleted: viewModel.journeyStopsCompleted,
                            journeyTotalStops: viewModel.journeyTotalStops,
                            shouldShowHistoricalData: shouldShowHistoricalData,
                            onShowHistory: { viewModel.showingHistory = true }
                        )
                        .padding()
                        // Force view update by using a composite ID that includes changing data
                        .id("\(train.id)-\(train.statusV2?.current ?? "")-\(train.progress?.journeyPercent ?? 0)-\(train.displayTrack ?? "")-\(viewModel.stopStatesHash)")
                    }
                }
                .refreshable {
                    await viewModel.loadTrainDetails(
                        fromStationCode: appState.departureStationCode,
                        selectedDestinationName: appState.selectedDestination
                    )
                }
            }
        .navigationTitle(viewModel.train != nil ? "Train \(viewModel.train!.trainId)" : "Loading...")
        .navigationBarTitleDisplayMode(.inline)
        .trackRatNavigationBarStyle()
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button("Close") {
                    appState.navigationPath.removeLast(appState.navigationPath.count)
                }
            }
        }
        .task {
            await viewModel.loadTrainDetails(
                fromStationCode: appState.departureStationCode,
                selectedDestinationName: appState.selectedDestination
            )
        }
        .onReceive(viewModel.timer) { _ in
            // Always refresh when the view is visible
            Task {
                await viewModel.refreshTrainDetails(
                    fromStationCode: appState.departureStationCode,
                    selectedDestinationName: appState.selectedDestination
                )
            }
        }
        .onChange(of: viewModel.triggerBoardingHaptic) { oldValue, newValue in
            if newValue {
                UINotificationFeedbackGenerator().notificationOccurred(.warning)
                // Consider a brief delay before resetting if needed, or ensure ViewModel handles reset appropriately.
                // For now, direct reset.
                DispatchQueue.main.async {
                    viewModel.triggerBoardingHaptic = false
                }
            }
        }
        .onChange(of: viewModel.triggerTrackAssignedHaptic) { oldValue, newValue in
            if newValue {
                UINotificationFeedbackGenerator().notificationOccurred(.success)
                DispatchQueue.main.async {
                    viewModel.triggerTrackAssignedHaptic = false
                }
            }
        }
        .sheet(isPresented: $viewModel.showingHistory) {
            if let train = viewModel.train {
                HistoricalDataView(train: train)
            }
        }
    }
}

// MARK: - Combined Details Card
struct CombinedDetailsCard: View {
    let train: Train
    let selectedDestination: String?
    @EnvironmentObject private var appState: AppState
    
    // ViewModel provided properties
    let displayableTrainStops: [Stop]
    let hasPreviousDisplayStops: Bool
    let hasMoreDisplayStops: Bool
    let journeyProgressPercentage: Int
    let journeyStopsCompleted: Int
    let journeyTotalStops: Int
    let shouldShowHistoricalData: Bool
    
    // Action closures
    let onShowHistory: () -> Void

    private var departureTime: String {
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        formatter.dateFormat = "EEEE, MMMM d 'at' h:mm a"
        
        // Use origin-specific departure time if we have a departure station code
        if let departureStationCode = appState.departureStationCode {
            let originDepartureTime = train.getDepartureTime(fromStationCode: departureStationCode)
            return formatter.string(from: originDepartureTime)
        }
        
        return formatter.string(from: train.departureTime)
    }
        
    private func checkIfDepartureStop(_ stationName: String) -> Bool { // This could also be moved or simplified
        guard let selectedDeparture = appState.selectedDeparture else { return false }
        return stationName.lowercased() == selectedDeparture.lowercased()
    }
    
    // Helper functions for status display
    private func timeAgo(from date: Date) -> String {
        let now = Date()
        let timeInterval = now.timeIntervalSince(date)
        let minutes = Int(timeInterval / 60)
        
        if minutes < 1 {
            return "just now"
        } else if minutes == 1 {
            return "1 min"
        } else if minutes < 60 {
            return "\(minutes) min"
        } else {
            let hours = minutes / 60
            let remainingMinutes = minutes % 60
            if remainingMinutes == 0 {
                return "\(hours)h"
            } else {
                return "\(hours)h \(remainingMinutes)m"
            }
        }
    }
    
    private func confidenceColor(_ confidence: String) -> Color {
        switch confidence.lowercased() {
        case "high":
            return .green
        case "medium":
            return .orange
        case "low":
            return .red
        default:
            return .gray
        }
    }
    
    /// Enhanced logic to determine if track predictions should be shown
    private var shouldShowPredictions: Bool {
        // Don't show if train is boarding at origin or has departed
        if isBoardingAtOrigin || train.hasDeparted {
            return false
        }
        
        // Don't show if track is definitively assigned for the departure station
        if let departureCode = appState.departureStationCode,
           let track = train.getTrackForStation(departureCode), !track.isEmpty {
            return false
        }
        
        // Don't show if train has departed from origin station
        if hasTrainDepartedFromOrigin() {
            return false
        }
        
        // Only show if we have prediction data
        return train.predictionData?.trackProbabilities != nil
    }
    
    /// Check if train has departed from the user's origin station
    private func hasTrainDepartedFromOrigin() -> Bool {
        guard let departureCode = appState.departureStationCode,
              let stops = train.stops else { return false }
        
        // Find origin stop using robust matching
        let originStop = stops.first { stop in
            Stations.stationMatches(stop, stationCode: departureCode)
        }
        
        return originStop?.departed ?? false
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
    
    var body: some View {
        VStack(spacing: 0) {
            // Top section with status info
            VStack(spacing: 0) {
                // Watch This Train section - only show for non-cancelled trains
                if #available(iOS 16.1, *), train.statusV2?.current != "CANCELLED" {
                    LiveActivityControls(
                        train: train,
                        origin: appState.selectedDeparture ?? "",
                        destination: appState.selectedDestination ?? "",
                        originCode: appState.departureStationCode ?? "",
                        destinationCode: Stations.getStationCode(appState.selectedDestination ?? "") ?? ""
                    )
                }
                
                // Enhanced Status Display with StatusV2 context
                if train.statusV2 != nil {
                    VStack(spacing: 12) {
                        // Show CANCELLED banner if train is cancelled
                        if train.statusV2?.current == "CANCELLED" {
                            VStack(spacing: 8) {
                                Text("CANCELLED")
                                    .font(.largeTitle)
                                    .fontWeight(.bold)
                                    .foregroundColor(.white)
                                
                                if let location = train.cancellationLocation {
                                    Text("Service ended at \(location)")
                                        .font(.headline)
                                        .foregroundColor(.white.opacity(0.9))
                                }
                            }
                            .padding()
                            .frame(maxWidth: .infinity)
                            .background(Color.red.opacity(0.9))
                            .cornerRadius(12)
                            .padding(.top, 8)
                        }
                        // Main status with boarding indication
                        else if isBoardingAtOrigin {
                            HStack {
                                Image(systemName: "circle.fill")
                                    .foregroundColor(.white)
                                    .font(.title2)
                                    .symbolEffect(.pulse)
                                
                                if let departureCode = appState.departureStationCode,
                                   let track = train.getTrackForStation(departureCode) {
                                    Text("Boarding on Track \(track)")
                                        .font(.title2)
                                        .fontWeight(.bold)
                                        .foregroundColor(.white)
                                } else {
                                    Text("BOARDING")
                                        .font(.title2)
                                        .fontWeight(.bold)
                                        .foregroundColor(.white)
                                }
                            }
                            .padding()
                            .frame(maxWidth: .infinity)
                            .background(Color.orange.opacity(0.9))
                            .cornerRadius(12)
                            .padding(.top, 8)
                        }
                    }
                } else {
                    // Fallback for trains without StatusV2
                    Text("Status information unavailable")
                        .font(.subheadline)
                        .foregroundColor(.black.opacity(0.6))
                        .padding()
                        .frame(maxWidth: .infinity)
                        .background(Color.gray.opacity(0.2))
                        .cornerRadius(12)
                }
                
                // Track or prediction with enhanced logic
                if shouldShowPredictions {
                    TrackRatPredictionView(prediction: train.predictionData!)
                }
            }
            .padding([.horizontal, .top])
            
            
            // Stops section
            VStack(alignment: .leading, spacing: 12) {
                if !displayableTrainStops.isEmpty {
                    if hasPreviousDisplayStops {
                        HStack {
                            Image(systemName: "ellipsis")
                                .font(.caption)
                                .foregroundColor(.gray)
                            Text("Train has previous stops")
                                .font(.caption)
                                .foregroundColor(.gray)
                                .italic()
                        }
                        .padding(.bottom, 4)
                        .padding(.horizontal, 20)
                    }
                    
                    ForEach(displayableTrainStops) { stop in
                        StopRow(
                            stop: stop,
                            isDestination: selectedDestination != nil && 
                                         stop.stationName.lowercased() == selectedDestination!.lowercased(),
                            isDeparture: checkIfDepartureStop(stop.stationName),
                            isBoarding: stop.stopStatus == "BOARDING" && !checkIfDepartureStop(stop.stationName),
                            boardingTrack: stop.stopStatus == "BOARDING" && !checkIfDepartureStop(stop.stationName) ? (appState.departureStationCode != nil ? train.getTrackForStation(appState.departureStationCode!) : nil) : nil,
                            train: train,
                            departureStationCode: appState.departureStationCode
                        )
                    }
                    
                    if hasMoreDisplayStops {
                        HStack {
                            Image(systemName: "ellipsis")
                                .font(.caption)
                                .foregroundColor(.gray)
                            Text("Train has later stops")
                                .font(.caption)
                                .foregroundColor(.gray)
                                .italic()
                        }
                        .padding(.top, 4)
                        .padding(.horizontal, 20)
                    }
                } else {
                    Text("No stops information available for this journey segment.")
                        .foregroundColor(.black.opacity(0.6))
                        .italic()
                        .frame(maxWidth: .infinity)
                        .padding()
                }
            }
            .padding()
            
            // Historical Data section
            if shouldShowHistoricalData {
                Button {
                    onShowHistory()
                } label: {
                    HStack {
                        Image(systemName: "clock.arrow.circlepath")
                            .foregroundColor(.orange)
                        Text("View Historical Data (beta)")
                            .font(.subheadline)
                            .foregroundColor(.black)
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.caption)
                            .foregroundColor(.black.opacity(0.6))
                    }
                    .padding()
                }
                .background(Color.clear)
                .cornerRadius(8)
                .padding(.horizontal)
                .padding(.bottom)
            }
        }
        .background(Color.white.opacity(0.9))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
    }
}

// MARK: - StatusV2 Card
struct StatusCard: View {
    let train: Train
    @EnvironmentObject private var appState: AppState

    private var departureTime: String {
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        formatter.dateFormat = "EEEE, MMMM d 'at' h:mm a"
        
        // Use origin-specific departure time if we have a departure station code
        if let departureStationCode = appState.departureStationCode {
            let originDepartureTime = train.getDepartureTime(fromStationCode: departureStationCode)
            return formatter.string(from: originDepartureTime)
        }
        
        // Fall back to train's original departure time
        return formatter.string(from: train.departureTime)
    }
    
    private var textColor: Color {
        guard train.statusV2 != nil else {
            return .black // No statusV2, fallback to black
        }
        
        // StatusV2 cards always use white text
        return .white
    }
    
    /// Enhanced logic to determine if track predictions should be shown
    private var shouldShowPredictions: Bool {
        // Don't show if train is boarding or has departed
        if train.isActuallyBoarding || train.hasDeparted {
            return false
        }
        
        // Don't show if track is definitively assigned for the departure station
        if let departureCode = appState.departureStationCode,
           let track = train.getTrackForStation(departureCode), !track.isEmpty {
            return false
        }
        
        // Don't show if train has departed from origin station
        if hasTrainDepartedFromOrigin() {
            return false
        }
        
        // Only show if we have prediction data
        return train.predictionData?.trackProbabilities != nil
    }
    
    /// Check if train has departed from the user's origin station
    private func hasTrainDepartedFromOrigin() -> Bool {
        guard let departureCode = appState.departureStationCode,
              let stops = train.stops else { return false }
        
        // Find origin stop using robust matching
        let originStop = stops.first { stop in
            Stations.stationMatches(stop, stationCode: departureCode)
        }
        
        return originStop?.departed ?? false
    }
    
    var body: some View {
        VStack(spacing: 16) {
            // StatusV2-only display
            if let statusV2 = train.statusV2 {
                VStack(spacing: 8) {
                    HStack {
                        // Pulsing Icon: Show only for actual boarding
                        if train.isActuallyBoarding {
                            Image(systemName: "circle.fill")
                                .foregroundColor(.white)
                                .font(.title2)
                                .symbolEffect(.pulse)
                        }
                        
                        // Status Text using StatusV2 computed properties
                        Text(train.statusV2DisplayText)
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(.white)
                        
                        // Show track for boarding trains
                        if train.isActuallyBoarding,
                           let departureCode = appState.departureStationCode,
                           let track = train.getTrackForStation(departureCode) {
                            Text("Track \(track)")
                                .font(.title2)
                                .fontWeight(.bold)
                                .foregroundColor(.white)
                        }
                    }
                    
                    // Show location info from StatusV2
                    if !statusV2.location.isEmpty {
                        Text(statusV2.location)
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.9))
                    }
                }
                .padding()
                .frame(maxWidth: .infinity)
                .background(Color(train.statusV2Color).opacity(0.9))
                .cornerRadius(12)
            } else {
                // No StatusV2 data - show error state
                Text("Status Unknown")
                    .font(.title2)
                    .fontWeight(.bold)
                    .foregroundColor(.black)
                    .padding()
                    .frame(maxWidth: .infinity)
                    .background(Color.gray.opacity(0.3))
                    .cornerRadius(12)
            }
            
            // Departure time
            Text(departureTime)
                .font(.headline)
                .foregroundColor(textColor)
                .multilineTextAlignment(.center)
            
            // Show progress info if available
            if let progress = train.progress {
                VStack(spacing: 8) {
                    if let nextArrival = progress.nextArrival {
                        HStack {
                            Image(systemName: "arrow.right.circle.fill")
                                .foregroundColor(.orange)
                            Text("Next: \(Stations.stationCodes.first(where: { $0.value == nextArrival.stationCode })?.key ?? nextArrival.stationCode)")
                                .font(.subheadline)
                                .fontWeight(.medium)
                            Spacer()
                            Text("\(nextArrival.minutesAway) min")
                                .font(.subheadline)
                                .foregroundColor(.orange)
                                .fontWeight(.bold)
                        }
                    }
                    
                    // Journey progress bar
                    ProgressView(value: Double(progress.journeyPercent) / 100.0)
                        .tint(.orange)
                        .scaleEffect(y: 2)
                    
                    Text("\(progress.stopsCompleted) of \(progress.totalStops) stops")
                        .font(.caption)
                        .foregroundColor(.gray)
                }
                .padding()
                .background(Color.gray.opacity(0.1))
                .cornerRadius(8)
            }
            
            // Track or prediction with enhanced logic
            if let departureCode = appState.departureStationCode,
               let track = train.getTrackForStation(departureCode), !track.isEmpty {
                Label("Track \(track)", systemImage: "tram.fill")
                    .font(.title3)
                    .fontWeight(.semibold)
                    .foregroundColor(.black)
                
                // Show source attribution for consolidated data
                if let trackAssignment = train.trackAssignment,
                   let assignedBy = trackAssignment.assignedBy {
                    Text("Assigned by \(assignedBy)")
                        .font(.caption2)
                        .foregroundColor(.black.opacity(0.6))
                }
            } else if shouldShowPredictions {
                TrackRatPredictionView(prediction: train.predictionData!)
            } else {
                // Debug: Show why no predictions
                VStack {
                    Text("🔍 No Track Prediction")
                        .font(.caption)
                        .foregroundColor(.black.opacity(0.6))
                }
            }
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(train.isActuallyBoarding ? Color.orange.opacity(0.9) : Color.white.opacity(0.9))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
        
        // Show detailed prediction below the card with enhanced logic
        if shouldShowPredictions {
            TrackRatPredictionView(prediction: train.predictionData!)
                .padding(.top, -8)
        }
    }
}

// MARK: - TrackRat Prediction View
struct TrackRatPredictionView: View {
    let prediction: PredictionData
    
    private var topTracks: [(String, Double)] {
        guard let probs = prediction.trackProbabilities,
              !probs.isEmpty else {
            return []
        }
        
        return probs.sorted { $0.value > $1.value }
            .filter { $0.value > 0.05 }
            .prefix(5)
            .map { ($0.key, $0.value) }
    }
    
    var body: some View {
        VStack(spacing: 12) {
            // Probability bars only
            ForEach(topTracks, id: \.0) { track, probability in
                HStack {
                    Text("Track \(track)")
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(.black)
                        .frame(width: 80, alignment: .leading)
                    
                    GeometryReader { geometry in
                        ZStack(alignment: .leading) {
                            Rectangle()
                                .fill(Color.gray.opacity(0.2))
                                .frame(height: 16)
                                .cornerRadius(8)
                            
                            Rectangle()
                                .fill(Color.green)
                                .frame(width: geometry.size.width * probability, height: 16)
                                .cornerRadius(8)
                        }
                    }
                    .frame(height: 16)
                    
                    Text("\(Int(probability * 100))%")
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(.black)
                        .frame(width: 40, alignment: .trailing)
                }
            }
        }
        .padding()
        .background(Color.gray.opacity(0.1))
        .cornerRadius(12)
    }
}

// MARK: - Stops Card
struct StopsCard: View {
    let train: Train
    let selectedDestination: String?
    @EnvironmentObject private var appState: AppState
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let stops = train.stops, !stops.isEmpty {
                ForEach(stops) { stop in
                    StopRow(
                        stop: stop,
                        isDestination: selectedDestination != nil && 
                                     stop.stationName.lowercased() == selectedDestination!.lowercased(),
                        isDeparture: appState.selectedDeparture != nil && 
                                   stop.stationName.lowercased() == appState.selectedDeparture!.lowercased(),
                        isBoarding: stop.stopStatus == "BOARDING" && !(appState.selectedDeparture != nil && stop.stationName.lowercased() == appState.selectedDeparture!.lowercased()),
                        boardingTrack: stop.stopStatus == "BOARDING" && !(appState.selectedDeparture != nil && stop.stationName.lowercased() == appState.selectedDeparture!.lowercased()) ? train.track : nil,
                        train: train,
                        departureStationCode: appState.departureStationCode
                    )
                }
            } else {
                Text("No stops information available")
                    .foregroundColor(.black.opacity(0.6))
                    .italic()
                    .frame(maxWidth: .infinity)
                    .padding()
            }
        }
        .padding()
        .background(Color.white.opacity(0.9))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
    }
}

// MARK: - Stop Row
struct StopRow: View {
    let stop: Stop
    let isDestination: Bool
    let isDeparture: Bool
    let isBoarding: Bool
    let boardingTrack: String?
    let train: Train
    let departureStationCode: String?
    
    @State private var showPulse = false
    
    // Helper to check if this stop is cancelled
    private var isCancelled: Bool {
        return stop.stopStatus == "CANCELLED"
    }
    
    // Helper to determine if this is the origin station (first stop) - check if it's pickup_only
    private var isOriginStation: Bool {
        return stop.pickupOnly == true || isDeparture
    }
    
    // Helper to determine if this is final destination (last stop) - check if it's dropoff_only
    private var isFinalDestination: Bool {
        return stop.dropoffOnly == true || isDestination
    }
    
    // Check if train has departed from the user's origin station
    private var hasTrainDepartedFromOrigin: Bool {
        guard let departureCode = departureStationCode,
              let stops = train.stops else { return false }
        
        // Find origin stop using robust matching
        let originStop = stops.first { s in
            Stations.stationMatches(s, stationCode: departureCode)
        }
        
        return originStop?.departed ?? false
    }
    
    // Determine if this is the next important station
    private var isNextImportantStation: Bool {
        // If train hasn't departed from origin yet, highlight the origin
        if !hasTrainDepartedFromOrigin {
            return isDeparture
        }
        
        // If train is en route, highlight next arrival
        if let nextArrivalCode = train.progress?.nextArrival?.stationCode {
            // Check if this stop matches the next arrival
            if let stopCode = stop.stationCode {
                return stopCode.uppercased() == nextArrivalCode.uppercased()
            }
            // Fall back to station name matching
            let nextStationName = Stations.stationCodes.first(where: { $0.value == nextArrivalCode })?.key
            if let nextName = nextStationName {
                return stop.stationName.lowercased() == nextName.lowercased()
            }
        } else {
            // Fallback: Find first non-departed stop
            if let stops = train.stops {
                let firstUpcomingStop = stops.first { !($0.departed ?? false) }
                if let upcoming = firstUpcomingStop {
                    return stop.id == upcoming.id
                }
            }
        }
        
        // If journey seems complete (all stops departed), highlight destination
        let allDeparted = train.stops?.allSatisfy { $0.departed ?? false } ?? false
        if allDeparted && isDestination {
            return true
        }
        
        return false
    }
    
    private var enhancedTimeDisplay: (arrival: String?, departure: String?, details: [String]) {
        // For cancelled stops: Don't show any times
        if isCancelled {
            return (nil, nil, [])
        }
        
        let formatter = DateFormatter.easternTime(time: .short)
        
        // For departed stops: Show only "Departed X:XX PM" with delay indicator
        if stop.departed == true {
            if let correctedDepartureTime = stop.departureTime {
                let delayText = departureDelayText(actual: correctedDepartureTime, scheduled: stop.scheduledDeparture)
                let departureText = "Departed: \(formatter.string(from: correctedDepartureTime))" + (delayText.isEmpty ? "" : " (\(delayText))")
                return (nil, departureText, [])
            } else if let scheduledDeparture = stop.scheduledDeparture {
                return (nil, "Departed: \(formatter.string(from: scheduledDeparture))", [])
            } else {
                return (nil, "Departed: --:--", [])
            }
        }
        
        // For origin station: Show only departure time
        if isOriginStation {
            if let correctedDepartureTime = stop.departureTime {
                let delayText = departureDelayText(actual: correctedDepartureTime, scheduled: stop.scheduledDeparture)
                let departureText = "Departure: \(formatter.string(from: correctedDepartureTime))" + (delayText.isEmpty ? "" : " (\(delayText))")
                return (nil, departureText, [])
            } else if let scheduledDeparture = stop.scheduledDeparture {
                return (nil, "Departure: \(formatter.string(from: scheduledDeparture))", [])
            } else {
                return (nil, "Departure: --:--", [])
            }
        }
        
        // For destination station: Show only arrival time
        if isFinalDestination {
            if let actualArrival = stop.actualArrival {
                let delayText = arrivalDelayText(actual: actualArrival, scheduled: stop.scheduledArrival)
                let arrivalText = "Arrival: \(formatter.string(from: actualArrival))" + (delayText.isEmpty ? "" : " (\(delayText))")
                return (arrivalText, nil, [])
            } else if let estimatedArrival = stop.estimatedArrival {
                let arrivalText = "Arrival: \(formatter.string(from: estimatedArrival)) (est)"
                return (arrivalText, nil, [])
            } else if let scheduledArrival = stop.scheduledArrival {
                return ("Arrival: \(formatter.string(from: scheduledArrival))", nil, [])
            } else {
                return ("Arrival: --:--", nil, [])
            }
        }
        
        // For upcoming stops: Show only arrival time
        if let actualArrival = stop.actualArrival {
            let delayText = arrivalDelayText(actual: actualArrival, scheduled: stop.scheduledArrival)
            let arrivalText = "Arrival: \(formatter.string(from: actualArrival))" + (delayText.isEmpty ? "" : " (\(delayText))")
            return (arrivalText, nil, [])
        } else if let estimatedArrival = stop.estimatedArrival {
            let arrivalText = "Arrival: \(formatter.string(from: estimatedArrival)) (est)"
            return (arrivalText, nil, [])
        } else if let scheduledArrival = stop.scheduledArrival {
            return ("Arrival: \(formatter.string(from: scheduledArrival))", nil, [])
        } else {
            return ("Arrival: --:--", nil, [])
        }
    }
    
    private func arrivalDelayText(actual: Date?, scheduled: Date?) -> String {
        guard let actual = actual, let scheduled = scheduled else { return "" }
        let delayMinutes = Int(actual.timeIntervalSince(scheduled) / 60)
        if delayMinutes > 0 {
            return "+\(delayMinutes)m delay"
        } else if delayMinutes < 0 {
            return "-\(abs(delayMinutes))m early"
        }
        return "" // Don't show anything for on-time
    }
    
    private func departureDelayText(actual: Date, scheduled: Date?) -> String {
        guard let scheduled = scheduled else { return "" }
        let delayMinutes = Int(actual.timeIntervalSince(scheduled) / 60)
        if delayMinutes > 0 {
            return "+\(delayMinutes)m delay"
        } else if delayMinutes < 0 {
            return "-\(abs(delayMinutes))m early"
        }
        return "" // Don't show anything for on-time
    }
    
    var body: some View {
        HStack(spacing: 12) {
            // Stop indicator
            Circle()
                .fill(stopColor)
                .frame(width: 12, height: 12)
                .overlay(
                    Circle()
                        .stroke(stopColor, lineWidth: (isDestination || isDeparture) ? 3 : 0)
                        .frame(width: 16, height: 16)
                )
            
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(Stations.displayName(for: stop.stationName))
                        .font((isDestination || isDeparture) ? .headline : .subheadline)
                        .fontWeight((isDestination || isDeparture) ? .semibold : .regular)
                        .foregroundColor(textColor)
                    
                    if isCancelled {
                        Text("🚫")
                            .font(.subheadline)
                    }
                }
                
                VStack(alignment: .leading, spacing: 2) {
                    if let arrivalText = enhancedTimeDisplay.arrival {
                        Text(arrivalText)
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundColor(timeColor)
                    }
                    
                    if let departureText = enhancedTimeDisplay.departure {
                        Text(departureText)
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundColor(timeColor)
                    }
                }
            }
            
            Spacer()
        }
        .padding(.vertical, 4)
        .padding(.horizontal, 8)
        .background(backgroundColor)
        .cornerRadius(8)
    }
    
    private var stopColor: Color {
        if isCancelled { return .gray }
        if isNextImportantStation { return .orange }
        if stop.departed ?? false { return .gray }
        return .blue
    }
    
    private var textColor: Color {
        if isCancelled { return .gray }
        if isNextImportantStation { return .orange }
        if stop.departed ?? false { return .gray }
        return .black
    }
    
    private var timeColor: Color {
        if isCancelled { return .gray }
        if isNextImportantStation { return .orange }
        if stop.departed ?? false { return .gray }
        return .black.opacity(0.6)
    }
    
    private var backgroundColor: Color {
        if isCancelled { return .clear }
        if isNextImportantStation { return .orange.opacity(0.1) }
        return .clear
    }
}

// MARK: - View Model
@MainActor
class TrainDetailsViewModel: ObservableObject {
    @Published var train: Train?
    @Published var isLoading = false
    @Published var error: String?
    @Published var triggerBoardingHaptic = false
    @Published var triggerTrackAssignedHaptic = false
    @Published var showingHistory = false
    
    // Flexible initialization parameters
    private let databaseId: Int?
    private let trainNumber: String?
    private let preferredStationCode: String?
    
    // Store current origin and destination for stop filtering
    private var currentOriginStationCode: String?
    private var currentDestinationName: String?
    
    private let apiService = APIService.shared
    
    // Timer for auto-refresh
    let timer = Timer.publish(every: 30, on: .main, in: .common).autoconnect()
    
    // Legacy initializer for backwards compatibility
    init(trainId: Int) {
        self.databaseId = trainId
        self.trainNumber = nil
        self.preferredStationCode = nil
    }
    
    // New flexible initializer
    init(databaseId: Int? = nil, trainNumber: String? = nil, fromStationCode: String? = nil) {
        self.databaseId = databaseId
        self.trainNumber = trainNumber
        self.preferredStationCode = fromStationCode
    }
    
    // Computed property for backwards compatibility
    var trainId: Int {
        return databaseId ?? 0
    }
    
    // Display properties
    @Published var displayableTrainStops: [Stop] = []
    
    private func updateDisplayableTrainStops() {
        guard let stops = train?.stops,
              let originStationCode = currentOriginStationCode,
              let destinationName = currentDestinationName else {
            displayableTrainStops = train?.stops ?? []
            return
        }
        
        // Find indices of origin and destination stops
        let originIndex = stops.firstIndex { stop in
            // First try to match by station code
            if let stopCode = stop.stationCode {
                return stopCode.uppercased() == originStationCode.uppercased()
            }
            
            // If no station code, find the expected station name for the origin code
            let expectedStationName = Stations.departureStations.first { $0.code == originStationCode.uppercased() }?.name
            if let expectedName = expectedStationName {
                return stop.stationName.lowercased() == expectedName.lowercased()
            }
            
            return false
        }
        
        let destinationIndex = stops.firstIndex { stop in
            stop.stationName.lowercased() == destinationName.lowercased()
        }
        
        // If we found both indices, return the slice
        if let startIdx = originIndex, let endIdx = destinationIndex, startIdx <= endIdx {
            // Include both origin and destination (endIdx inclusive)
            displayableTrainStops = Array(stops[startIdx...endIdx])
        } else {
            // Fallback to all stops if we can't find the stations or if indices are invalid
            displayableTrainStops = stops
        }
    }
    
    @Published var hasPreviousDisplayStops: Bool = false
    @Published var hasMoreDisplayStops: Bool = false
    @Published var journeyProgressPercentage: Int = 0
    @Published var journeyStopsCompleted: Int = 0
    @Published var journeyTotalStops: Int = 0
    
    /// Hash of stop departure states for SwiftUI view update detection
    var stopStatesHash: String {
        let departedStates = displayableTrainStops.map { $0.departed ?? false }
        return String(departedStates.hashValue)
    }
    
    private func updateComputedProperties() {
        updateDisplayableTrainStops()
        updateJourneyProgress()
        updateDisplayStopFlags()
    }
    
    private func updateDisplayStopFlags() {
        guard let stops = train?.stops,
              let originStationCode = currentOriginStationCode,
              currentDestinationName != nil else {
            hasPreviousDisplayStops = false
            hasMoreDisplayStops = false
            return
        }
        
        // Find the origin index
        let originIndex = stops.firstIndex { stop in
            // First try to match by station code
            if let stopCode = stop.stationCode {
                return stopCode.uppercased() == originStationCode.uppercased()
            }
            
            // If no station code, find the expected station name for the origin code
            let expectedStationName = Stations.departureStations.first { $0.code == originStationCode.uppercased() }?.name
            if let expectedName = expectedStationName {
                return stop.stationName.lowercased() == expectedName.lowercased()
            }
            
            return false
        }
        
        // Update hasPreviousDisplayStops
        hasPreviousDisplayStops = originIndex != nil && originIndex! > 0
        
        // Find destination index
        let destinationIndex = currentDestinationName != nil ? stops.firstIndex { stop in
            stop.stationName.lowercased() == currentDestinationName!.lowercased()
        } : nil
        
        // Update hasMoreDisplayStops
        if let endIdx = destinationIndex, let startIdx = originIndex, startIdx <= endIdx {
            hasMoreDisplayStops = endIdx < stops.count - 1
        } else {
            hasMoreDisplayStops = false
        }
    }
    
    private func updateJourneyProgress() {
        journeyProgressPercentage = train?.progress?.journeyPercent ?? 0
        journeyStopsCompleted = train?.progress?.stopsCompleted ?? 0
        journeyTotalStops = train?.progress?.totalStops ?? 0
    }
    
    func loadTrainDetails(fromStationCode: String? = nil, selectedDestinationName: String? = nil) async {
        isLoading = true
        error = nil
        
        // Store current origin and destination for filtering
        self.currentOriginStationCode = fromStationCode
        self.currentDestinationName = selectedDestinationName
        
        do {
            // Use the flexible API method
            train = try await apiService.fetchTrainDetailsFlexible(
                id: databaseId.map(String.init),
                trainId: trainNumber,
                fromStationCode: fromStationCode ?? preferredStationCode
            )
            
            // Update all computed properties after setting train
            updateComputedProperties()
        } catch {
            // Handle APIError.noData specifically
            if let apiError = error as? APIError {
                switch apiError {
                case .noData:
                    self.error = "Train not found"
                default:
                    self.error = apiError.localizedDescription
                }
            } else {
                self.error = error.localizedDescription
            }
        }
        
        isLoading = false
    }
    
    func refreshTrainDetails(fromStationCode: String? = nil, selectedDestinationName: String? = nil) async {
        // Store current origin and destination for filtering
        self.currentOriginStationCode = fromStationCode
        self.currentDestinationName = selectedDestinationName
        
        // Silent refresh
        do {
            let identifier = trainNumber ?? (databaseId.map(String.init) ?? "unknown")
            print("🔄 TrainDetailsView refreshing train \(identifier) from \(fromStationCode ?? preferredStationCode ?? "none")")
            
            let newTrain = try await apiService.fetchTrainDetailsFlexible(
                id: databaseId.map(String.init),
                trainId: trainNumber,
                fromStationCode: fromStationCode ?? preferredStationCode
            )
            
            print("✅ TrainDetailsView refresh successful for train \(identifier)")
            
            // Check for boarding status change using consolidated display properties
            if let currentTrain = train {
                // StatusV2-only boarding haptic:
                // Previous state was not actually boarding
                // New state is actually boarding (StatusV2 with track)
                if !currentTrain.isActuallyBoarding && newTrain.isActuallyBoarding {
                    triggerBoardingHaptic = true
                }
                
                // Check for track assignment using consolidated display track
                if let departureCode = currentOriginStationCode,
                   currentTrain.getTrackForStation(departureCode) == nil && newTrain.getTrackForStation(departureCode) != nil {
                    triggerTrackAssignedHaptic = true
                }
            }
            
            // Ensure UI updates properly on main queue
            DispatchQueue.main.async { [weak self] in
                self?.objectWillChange.send()
                self?.train = newTrain
                self?.updateComputedProperties()
            }
            
            // Update Live Activity if active
            if #available(iOS 16.1, *) {
                await LiveActivityService.shared.updateActivity(with: newTrain)
            }
        } catch {
            print("❌ TrainDetailsView refresh failed for train \(trainId): \(error)")
            print("❌ Full error details: \(String(describing: error))")
        }
    }
}

// MARK: - Train Progress Indicator
struct TrainProgressIndicator: View {
    let progress: Double
    @State private var trainOffset: CGFloat = 0
    @State private var showPulse = false
    
    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                // Track
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.gray.opacity(0.3))
                    .frame(height: 8)
                
                // Progress track
                RoundedRectangle(cornerRadius: 4)
                    .fill(LinearGradient(
                        colors: [Color.green, Color.blue],
                        startPoint: .leading,
                        endPoint: .trailing
                    ))
                    .frame(width: geometry.size.width * progress, height: 8)
                
                // Train icon
                Image(systemName: "tram.fill")
                    .font(.title2)
                    .foregroundColor(.orange)
                    .shadow(color: .black.opacity(0.3), radius: 2, x: 0, y: 1)
                    .scaleEffect(showPulse ? 1.1 : 1.0)
                    .offset(x: trainOffset)
                    .onAppear {
                        // Calculate initial position
                        trainOffset = max(0, min(geometry.size.width - 30, geometry.size.width * progress - 15))
                        
                        // Start pulsing animation
                        withAnimation(.easeInOut(duration: 1).repeatForever(autoreverses: true)) {
                            showPulse = true
                        }
                    }
                    .onChange(of: progress) { oldValue, newProgress in
                        // Animate train movement
                        withAnimation(.easeInOut(duration: 0.5)) {
                            trainOffset = max(0, min(geometry.size.width - 30, geometry.size.width * newProgress - 15))
                        }
                    }
            }
        }
        .frame(height: 30)
    }
}

// MARK: - Consolidated Data Card
struct ConsolidatedDataCard: View {
    let train: Train
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                Image(systemName: "network")
                    .foregroundColor(.blue)
                Text("Multi-Source Data")
                    .font(.headline)
                    .foregroundColor(.white)
                Spacer()
            }
            
            // Data sources details
            if let sources = train.dataSources {
                Divider()
                    .background(Color.white.opacity(0.3))
                
                ForEach(sources, id: \.dbId) { source in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(source.origin)
                                .font(.caption)
                                .fontWeight(.medium)
                                .foregroundColor(.white)
                            Text(source.dataSource)
                                .font(.caption2)
                                .foregroundColor(.white.opacity(0.6))
                        }
                        
                        Spacer()
                        
                        VStack(alignment: .trailing, spacing: 2) {
                            if let status = source.status {
                                Text(status)
                                    .font(.caption2)
                                    .foregroundColor(.white.opacity(0.8))
                            }
                            if let track = source.track {
                                Text("Track \(track)")
                                    .font(.caption2)
                                    .foregroundColor(.orange.opacity(0.8))
                            }
                        }
                    }
                    .padding(.vertical, 2)
                }
            }
        }
        .padding()
        .background(.ultraThinMaterial.opacity(0.9))
        .cornerRadius(12)
    }
}

// MARK: - Position Tracking Card
struct PositionTrackingCard: View {
    let train: Train
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                Image(systemName: "location.fill")
                    .foregroundColor(.green)
                Text("Real-Time Position")
                    .font(.headline)
                    .foregroundColor(.white)
                Spacer()
                if let speed = train.estimatedSpeed {
                    Text("\(Int(speed)) mph")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.8))
                }
            }
            
            if let position = train.currentPosition {
                // Progress bar
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        if let lastDeparted = position.lastDepartedStation {
                            Text(lastDeparted.name)
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.8))
                        }
                        Spacer()
                        if let next = position.nextStation {
                            Text(next.name)
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.8))
                        }
                    }
                    
                    TrainProgressIndicator(progress: train.segmentProgress)
                    
                    if let segmentProgress = position.segmentProgress {
                        Text("\(Int(segmentProgress * 100))% to next station")
                            .font(.caption2)
                            .foregroundColor(.white.opacity(0.6))
                    }
                }
            }
        }
        .padding()
        .background(.ultraThinMaterial.opacity(0.9))
        .cornerRadius(12)
    }
}


// MARK: - Stations Helper Extension
extension Stations {
    static func displayNameForCode(_ stationCode: String) -> String {
        // Try to find the station name by code
        if let stationName = stationCodes.first(where: { $0.value == stationCode })?.key {
            return displayName(for: stationName) // Use existing method for formatting
        }
        // Return the code if we can't find a display name
        return stationCode
    }
}

#Preview {
    NavigationStack {
        TrainDetailsView(trainId: 1)
            .environmentObject(AppState())
    }
}
