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
                            onShowHistory: { viewModel.showingHistory = true }
                        )
                        .padding()
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
            // Only refresh if there's no active Live Activity to avoid dual timers
            if #available(iOS 16.1, *), !LiveActivityService.shared.isActivityActive {
                Task {
                    await viewModel.refreshTrainDetails(
                        fromStationCode: appState.departureStationCode,
                        selectedDestinationName: appState.selectedDestination
                    )
                }
            } else if #unavailable(iOS 16.1) {
                Task {
                    await viewModel.refreshTrainDetails(
                        fromStationCode: appState.departureStationCode,
                        selectedDestinationName: appState.selectedDestination
                    )
                }
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
    
    var body: some View {
        VStack(spacing: 0) {
            // Top section with status info
            VStack(spacing: 16) {
                // Enhanced Status Display with StatusV2 context
                if let statusV2 = train.statusV2 {
                    VStack(spacing: 12) {
                        // Main status with boarding indication
                        if train.isActuallyBoarding {
                            HStack {
                                Image(systemName: "circle.fill")
                                    .foregroundColor(.white)
                                    .font(.title2)
                                    .symbolEffect(.pulse)
                                
                                if let track = train.displayTrack {
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
                
                // Departure time
                Text(departureTime)
                    .font(.headline)
                    .foregroundColor(.black)
                    .multilineTextAlignment(.center)
                
                // Track or prediction (StatusV2 only)
                if !train.isActuallyBoarding {
                    if let prediction = train.predictionData {
                        TrackRatPredictionView(prediction: prediction)
                    }
                }
                
                // Watch This Train section
                if #available(iOS 16.1, *) {
                    LiveActivityControls(
                        train: train,
                        origin: appState.selectedDeparture ?? "",
                        destination: appState.selectedDestination ?? "",
                        originCode: appState.departureStationCode ?? "",
                        destinationCode: Stations.getStationCode(appState.selectedDestination ?? "") ?? ""
                    )
                }
            }
            .padding()
            
            Divider()
                .background(Color.gray.opacity(0.2))
            
            // Journey Status Information
            // Use journeyTotalStops from ViewModel as a condition as well
            if train.statusV2 != nil || train.progress != nil || journeyTotalStops > 0 {
                JourneyStatusView(
                    train: train, // Keep train for other status info like V2, statusEmoji etc.
                    displayMode: JourneyDisplayMode.full,
                    originStationCode: appState.departureStationCode,
                    destinationStationCode: Stations.getStationCode(selectedDestination ?? ""),
                    // Pass ViewModel calculated progress
                    journeyProgressPercentage: journeyProgressPercentage,
                    journeyStopsCompleted: journeyStopsCompleted,
                    journeyTotalStops: journeyTotalStops
                )
                .padding(.horizontal)
                .padding(.vertical, 8)
            }
            
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
                            boardingTrack: stop.stopStatus == "BOARDING" && !checkIfDepartureStop(stop.stationName) ? train.displayTrack : nil
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
                        if train.isActuallyBoarding, let track = train.displayTrack {
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
            
            // Track or prediction (StatusV2 only)
            if !train.isActuallyBoarding {
                if let track = train.displayTrack, !track.isEmpty {
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
                } else if let prediction = train.predictionData {
                    TrackRatPredictionView(prediction: prediction)
                } else {
                    // Debug: Show why no predictions
                    VStack {
                        Text("🔍 No Track Prediction")
                            .font(.caption)
                            .foregroundColor(.black.opacity(0.6))
                    }
                }
            }
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(train.isActuallyBoarding ? Color.orange.opacity(0.9) : Color.white.opacity(0.9))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
        
        // Show detailed prediction below the card if no track assigned (StatusV2 only)
        if !train.isActuallyBoarding,
           (train.displayTrack == nil || train.displayTrack!.isEmpty),
           let prediction = train.predictionData {
            TrackRatPredictionView(prediction: prediction)
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
                        boardingTrack: stop.stopStatus == "BOARDING" && !(appState.selectedDeparture != nil && stop.stationName.lowercased() == appState.selectedDeparture!.lowercased()) ? train.track : nil
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
    
    @State private var showPulse = false
    
    // Helper to determine if this is the origin station (first stop) - check if it's pickup_only
    private var isOriginStation: Bool {
        return stop.pickupOnly == true || isDeparture
    }
    
    // Helper to determine if this is final destination (last stop) - check if it's dropoff_only
    private var isFinalDestination: Bool {
        return stop.dropoffOnly == true || isDestination
    }
    
    private var enhancedTimeDisplay: (arrival: String?, departure: String?, details: [String]) {
        let formatter = DateFormatter.easternTime(time: .short)
        
        // For departed stops: Show only "Departed X:XX PM" with delay indicator
        if stop.departed == true {
            if let actualDeparture = stop.actualDeparture {
                let delayText = departureDelayText(actual: actualDeparture, scheduled: stop.scheduledDeparture)
                let departureText = "Departed: \(formatter.string(from: actualDeparture))" + (delayText.isEmpty ? "" : " (\(delayText))")
                return (nil, departureText, [])
            } else if let scheduledDeparture = stop.scheduledDeparture {
                return (nil, "Departed: \(formatter.string(from: scheduledDeparture))", [])
            } else {
                return (nil, "Departed: --:--", [])
            }
        }
        
        // For origin station: Show only departure time
        if isOriginStation {
            if let actualDeparture = stop.actualDeparture {
                let delayText = departureDelayText(actual: actualDeparture, scheduled: stop.scheduledDeparture)
                let departureText = "Departure: \(formatter.string(from: actualDeparture))" + (delayText.isEmpty ? "" : " (\(delayText))")
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
        if isDestination { return .green }
        if isDeparture { return .orange }
        if isBoarding { return .orange }
        if stop.departed ?? false { return .gray }
        return .blue
    }
    
    private var textColor: Color {
        if isDestination { return .green }
        if isDeparture { return .orange }
        if stop.departed ?? false { return .gray }
        return .black
    }
    
    private var timeColor: Color {
        if isDestination { return .green }
        if isDeparture { return .orange }
        if stop.departed ?? false { return .gray }
        return .black.opacity(0.6)
    }
    
    private var backgroundColor: Color {
        if isDestination { return .green.opacity(0.1) }
        if isDeparture { return .orange.opacity(0.1) }
        if isBoarding { return .orange.opacity(0.1) }
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
    var displayableTrainStops: [Stop] {
        guard let stops = train?.stops,
              let originStationCode = currentOriginStationCode,
              let destinationName = currentDestinationName else {
            return train?.stops ?? []
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
            return Array(stops[startIdx...endIdx])
        }
        
        // Fallback to all stops if we can't find the stations or if indices are invalid
        return stops
    }
    
    var hasPreviousDisplayStops: Bool {
        guard let stops = train?.stops,
              let originStationCode = currentOriginStationCode,
              currentDestinationName != nil else {
            return false
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
        
        // Return true if there are stops before the origin
        return originIndex != nil && originIndex! > 0
    }
    
    var hasMoreDisplayStops: Bool {
        guard let stops = train?.stops,
              let originStationCode = currentOriginStationCode,
              let destinationName = currentDestinationName else {
            return false
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
        
        // Return true if there are stops after the destination
        if let endIdx = destinationIndex, let startIdx = originIndex, startIdx <= endIdx {
            return endIdx < stops.count - 1
        }
        
        return false
    }
    
    var journeyProgressPercentage: Int {
        return train?.progress?.journeyPercent ?? 0
    }
    
    var journeyStopsCompleted: Int {
        return train?.progress?.stopsCompleted ?? 0
    }
    
    var journeyTotalStops: Int {
        return train?.progress?.totalStops ?? 0
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
                if currentTrain.displayTrack == nil && newTrain.displayTrack != nil {
                    triggerTrackAssignedHaptic = true
                }
            }
            
            train = newTrain
            
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

// MARK: - Journey Status View
struct JourneyStatusView: View {
    let train: Train
    let displayMode: JourneyDisplayMode
    let showTrainHeader: Bool
    let originStationCode: String?
    let destinationStationCode: String?

    // ViewModel provided properties for progress
    let journeyProgressPercentage: Int
    let journeyStopsCompleted: Int
    let journeyTotalStops: Int
    
    init(train: Train, displayMode: JourneyDisplayMode = .full, showTrainHeader: Bool = false, originStationCode: String? = nil, destinationStationCode: String? = nil, journeyProgressPercentage: Int = 0, journeyStopsCompleted: Int = 0, journeyTotalStops: Int = 0) {
        self.train = train
        self.displayMode = displayMode
        self.showTrainHeader = showTrainHeader
        self.originStationCode = originStationCode
        self.destinationStationCode = destinationStationCode
        self.journeyProgressPercentage = journeyProgressPercentage
        self.journeyStopsCompleted = journeyStopsCompleted
        self.journeyTotalStops = journeyTotalStops
    }
    
    var body: some View {
        switch displayMode {
        case .full:
            fullJourneyStatus
        case .compact:
            compactJourneyStatus
        }
    }
    
    // MARK: - Full Journey Status (for Train Details)
    @ViewBuilder
    private var fullJourneyStatus: some View {
        VStack(spacing: 16) {
            // Progress information
            if hasProgressData {
                progressSection
            }
            
            // Departure info
            if hasDepartureInfo {
                departureSection
            }
            
            // Next arrival info
            if hasNextArrivalInfo {
                nextArrivalSection
            }
        }
    }
    
    // MARK: - Compact Journey Status (for Active Trips)
    @ViewBuilder
    private var compactJourneyStatus: some View {
        VStack(spacing: 8) {
            // Train header if requested
            if showTrainHeader {
                HStack {
                    Text("Train \(train.trainId) to \(train.destination)")
                        .font(.headline)
                        .foregroundColor(.white)
                        .fontWeight(.semibold)
                    Spacer()
                }
            }
            
            // Status display only
            HStack {
                // Status with emoji
                HStack(spacing: 4) {
                    Text(statusEmoji)
                        .font(.subheadline)
                    Text(displayStatus)
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(.white)
                }
                
                Spacer()
            }
            
            // Next arrival info
            if let progress = train.progress, let nextArrival = progress.nextArrival {
                HStack {
                    Image(systemName: "arrow.right.circle.fill")
                        .foregroundColor(.orange)
                        .font(.caption)
                    Text("\(Stations.displayNameForCode(nextArrival.stationCode)) in \(nextArrival.minutesAway) min")
                        .font(.caption)
                        .foregroundColor(.white)
                    Spacer()
                }
            }
        }
    }
    
    // MARK: - Full Mode Components
    
    
    @ViewBuilder
    private var progressSection: some View {
        EmptyView()
    }
    
    @ViewBuilder
    private var departureSection: some View {
        if let progress = train.progress, let lastDeparted = progress.lastDeparted {
            VStack(spacing: 8) {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                        .font(.title3)
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Last departed: \(Stations.displayNameForCode(lastDeparted.stationCode))")
                            .font(.subheadline)
                            .fontWeight(.semibold)
                            .foregroundColor(.black)
                        
                        // Rich departure time and delay information
                        HStack(spacing: 12) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Departed at")
                                    .font(.caption2)
                                    .foregroundColor(.black.opacity(0.6))
                                Text(formatDepartureTime(lastDeparted.departedAt))
                                    .font(.caption)
                                    .fontWeight(.medium)
                                    .foregroundColor(.black)
                            }
                            
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Delay")
                                    .font(.caption2)
                                    .foregroundColor(.black.opacity(0.6))
                                Text(delayText(delayMinutes: lastDeparted.delayMinutes))
                                    .font(.caption)
                                    .fontWeight(.medium)
                                    .foregroundColor(delayColor(lastDeparted.delayMinutes))
                            }
                        }
                    }
                    Spacer()
                }
                
                // Time ago indicator
                HStack {
                    Image(systemName: "clock")
                        .foregroundColor(.orange)
                        .font(.caption)
                    Text("\(timeAgo(from: lastDeparted.departedAt)) ago")
                        .font(.caption)
                        .foregroundColor(.black.opacity(0.7))
                    Spacer()
                }
            }
            .padding()
            .background(Color.green.opacity(0.1))
            .cornerRadius(8)
        }
    }
    
    @ViewBuilder
    private var nextArrivalSection: some View {
        if let progress = train.progress, let nextArrival = progress.nextArrival {
            HStack {
                Image(systemName: "arrow.right.circle.fill")
                    .foregroundColor(.orange)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Next: \(Stations.displayNameForCode(nextArrival.stationCode))")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(.black)
                    
                    Text("Arriving in \(nextArrival.minutesAway) minutes")
                        .font(.caption)
                        .foregroundColor(.black.opacity(0.6))
                }
                Spacer()
                
                // Live countdown
                VStack(alignment: .trailing, spacing: 2) {
                    Text("\(nextArrival.minutesAway) min")
                        .font(.headline)
                        .fontWeight(.bold)
                        .foregroundColor(.orange)
                    
                    Text("away")
                        .font(.caption2)
                        .foregroundColor(.black.opacity(0.5))
                }
            }
        }
    }
    
    // MARK: - Helper Properties
    
    // userJourneyProgress computed property is removed as this logic is now in the ViewModel.
    // The view now receives journeyProgressPercentage, journeyStopsCompleted, journeyTotalStops as parameters.
    
    private var displayStatus: String {
        guard let statusV2 = train.statusV2 else {
            return "Unknown"
        }
        return humanFriendlyStatus(statusV2.current)
    }
    
    /// Convert technical status to human-friendly display text
    private func humanFriendlyStatus(_ status: String) -> String {
        switch status.uppercased() {
        case "EN_ROUTE":
            return "En Route"
        case "BOARDING":
            if train.displayTrack != nil {
                return "Boarding" // Caller will add track info if needed.
            } else {
                return "Scheduled" // BOARDING without track is "Scheduled"
            }
        case "SCHEDULED":
            return "Scheduled"
        case "ON_TIME":
            return "On Time"
        case "DELAYED":
            return "Delayed"
        case "DEPARTED":
            return "Departed"
        case "ARRIVED":
            return "Journey Complete!"
        case "CANCELLED":
            return "Cancelled"
        case "ALL_ABOARD":
            return "All Aboard"
        default:
            return status.capitalized
        }
    }
    
    private var statusEmoji: String {
        guard let statusV2 = train.statusV2 else {
            return "❓"
        }
        let status = statusV2.current
        switch status {
        case "EN_ROUTE", "DEPARTED":
            return "🚆"
        case "BOARDING":
            return "🚪" // Never use train emoji for boarding
        case "DELAYED":
            return "⏰"
        case "SCHEDULED", "ON_TIME":
            return "🕐"
        case "ARRIVED":
            return "🏁"
        default:
            return "🚂"
        }
    }
    
    private var statusColor: Color {
        guard let statusV2 = train.statusV2 else {
            return .gray
        }
        let status = statusV2.current
        switch status {
        case "EN_ROUTE", "DEPARTED":
            return .blue
        case "BOARDING":
            return .orange
        case "DELAYED":
            return .red
        case "SCHEDULED", "ON_TIME":
            return .green
        case "ARRIVED":
            return .green
        default:
            return .gray
        }
    }
    
    private var hasProgressData: Bool {
        // Now considers ViewModel's calculated journey or fallback to API progress
        return journeyTotalStops > 0 || train.progress != nil
    }
    
    private var hasDepartureInfo: Bool {
        return train.progress?.lastDeparted != nil
    }
    
    private var hasNextArrivalInfo: Bool {
        return train.progress?.nextArrival != nil
    }
    
    private func delayText(delayMinutes: Int) -> String {
        if delayMinutes == 0 {
            return "On time"
        } else if delayMinutes > 0 {
            return "\(delayMinutes) min late"
        } else {
            return "\(abs(delayMinutes)) min early"
        }
    }
    
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
    
    private func delayColor(_ delayMinutes: Int) -> Color {
        if delayMinutes == 0 {
            return .green
        } else if delayMinutes > 0 {
            return .red
        } else {
            return .blue
        }
    }
    
    private func formatDepartureTime(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        return formatter.string(from: date)
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
