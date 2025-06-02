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
        self._viewModel = StateObject(wrappedValue: TrainDetailsViewModel(trainId: trainId))
    }
    
    // New initializer for train number
    init(trainNumber: String, fromStation: String? = nil) {
        self.trainId = 0  // Not used for train number based initialization
        self._viewModel = StateObject(wrappedValue: TrainDetailsViewModel(
            databaseId: nil,
            trainNumber: trainNumber,
            fromStationCode: fromStation
        ))
    }
    
    var body: some View {
        ZStack {
            // Background gradient
            LinearGradient(
                colors: [Color(hex: "667eea"), Color(hex: "764ba2")],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
            
            ScrollView {
                    if viewModel.isLoading && viewModel.train == nil {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                            .scaleEffect(1.5)
                            .frame(maxWidth: .infinity, minHeight: 400)
                    } else if let error = viewModel.error {
                        ErrorView(message: error) {
                            Task {
                                await viewModel.loadTrainDetails(fromStationCode: appState.departureStationCode)
                            }
                        }
                    } else if let train = viewModel.train {
                        VStack(spacing: 20) {
                            // Live Activity controls -- REMOVE THIS BLOCK
                            // if #available(iOS 16.1, *) {
                            //     LiveActivityControls(
                            //         train: train,
                            //         origin: appState.selectedDeparture ?? "",
                            //         destination: appState.selectedDestination ?? "",
                            //         originCode: appState.departureStationCode ?? "",
                            //         destinationCode: Stations.getStationCode(appState.selectedDestination ?? "") ?? ""
                            //     )
                            // }
                            
                            // Combined card with all details
                            CombinedDetailsCard(train: train, selectedDestination: appState.selectedDestination)
                            
                            // Consolidated data section -- REMOVE THIS BLOCK
                            // if train.isConsolidated {
                            //     ConsolidatedDataCard(train: train)
                            // }
                            
                            // Show history button -- REMOVE THIS BLOCK
                            // Button {
                            //     showingHistory = true
                            // } label: {
                            //     HStack {
                            //         Image(systemName: "clock.arrow.circlepath")
                            //         Text("details from past trains")
                            //             .font(.subheadline)
                            //     }
                            //     .foregroundColor(.white.opacity(0.8))
                            // }
                            // .padding(.top)

                            // ADD THE NEW VIEW HERE
                            ExperimentalFeaturesView(viewModel: viewModel, train: train)
                        }
                        .padding()
                    }
                }
                .refreshable {
                    await viewModel.loadTrainDetails(fromStationCode: appState.departureStationCode)
                }
            }
        .navigationTitle(viewModel.train != nil ? "Train \(viewModel.train!.trainId)" : "Loading...")
        .navigationBarTitleDisplayMode(.inline)
        .glassmorphicNavigationBar()
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button("Close") {
                    appState.navigationPath.removeAll()
                }
            }
        }
        .task {
            await viewModel.loadTrainDetails(fromStationCode: appState.departureStationCode)
        }
        .onReceive(viewModel.timer) { _ in
            // Only refresh if there's no active Live Activity to avoid dual timers
            if #available(iOS 16.1, *), !LiveActivityService.shared.isActivityActive {
                Task {
                    await viewModel.refreshTrainDetails(fromStationCode: appState.departureStationCode)
                }
            } else if #unavailable(iOS 16.1) {
                Task {
                    await viewModel.refreshTrainDetails(fromStationCode: appState.departureStationCode)
                }
            }
        }
        // .sheet(isPresented: $showingHistory) { // REMOVE THIS BLOCK
        //     if let train = viewModel.train {
        //         HistoricalDataView(train: train)
        //     }
        // }
    }
}

// MARK: - Combined Details Card
struct CombinedDetailsCard: View {
    let train: Train
    let selectedDestination: String?
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
    
    private func filterStopsForJourney(stops: [Stop], origin: String?, destination: String?) -> (stops: [Stop], hasPreviousStops: Bool, hasMoreStops: Bool) {
        // First, filter out stops with no timing information
        let stopsWithTimes = stops.filter { stop in
            stop.scheduledTime != nil || stop.departureTime != nil
        }
        
        var filteredStops = stopsWithTimes
        var hasPreviousStops = false
        var hasMoreStops = false
        
        // Filter by origin (remove stops before the user's origin)
        if let origin = origin {
            if let originIndex = stopsWithTimes.firstIndex(where: { 
                $0.stationName.lowercased() == origin.lowercased() 
            }) {
                // Check if there are previous stops (before origin)
                hasPreviousStops = originIndex > 0
                // Remove stops before origin
                filteredStops = Array(stopsWithTimes.suffix(from: originIndex))
            }
        }
        
        // Filter by destination (remove stops after the user's destination)
        if let destination = destination {
            if let destinationIndex = filteredStops.firstIndex(where: { 
                $0.stationName.lowercased() == destination.lowercased() 
            }) {
                // Check if there are more stops after destination in the original filtered list
                hasMoreStops = destinationIndex < filteredStops.count - 1
                // Keep stops up to and including the destination
                filteredStops = Array(filteredStops.prefix(destinationIndex + 1))
            }
        }
        
        return (stops: filteredStops, hasPreviousStops: hasPreviousStops, hasMoreStops: hasMoreStops)
    }
    
    private func checkIfDepartureStop(_ stationName: String) -> Bool {
        guard let selectedDeparture = appState.selectedDeparture else { return false }
        return stationName.lowercased() == selectedDeparture.lowercased()
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Top section with status info
            VStack(spacing: 16) {
                // Boarding status
                // Only show boarding UI if track is assigned
                if train.displayStatus == .boarding && train.displayTrack != nil {
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
                
                // Departure time
                Text(departureTime)
                    .font(.headline)
                    .foregroundColor(.black)
                    .multilineTextAlignment(.center)
                
                // Track or prediction
                if train.displayStatus != .boarding {
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
                        OwlPredictionView(prediction: prediction)
                    } else {
                        // Debug: Show why no predictions
                        VStack {
                            Text("🔍 No Track Prediction")
                                .font(.caption)
                                .foregroundColor(.black.opacity(0.6))
                            if train.isConsolidated {
                                Text("Consolidated train with no prediction data")
                                    .font(.caption2)
                                    .foregroundColor(.black.opacity(0.5))
                            }
                        }
                    }
                }
            }
            .padding()
            
            Divider()
                .background(Color.gray.opacity(0.2))
            
            // Journey Status Information
            if train.statusV2 != nil || train.progress != nil {
                JourneyStatusView(
                    train: train, 
                    displayMode: JourneyDisplayMode.full,
                    originStationCode: appState.departureStationCode,
                    destinationStationCode: Stations.getStationCode(selectedDestination ?? "")
                )
                .padding(.horizontal)
                .padding(.vertical, 8)
            }
            
            // Stops section
            VStack(alignment: .leading, spacing: 12) {
                if let stops = train.stops, !stops.isEmpty {
                    let journeyData = filterStopsForJourney(
                        stops: stops, 
                        origin: appState.selectedDeparture, 
                        destination: selectedDestination
                    )
                    
                    // Show previous stops message if there are departed stations before origin
                    if journeyData.hasPreviousStops {
                        HStack {
                            Image(systemName: "ellipsis")
                                .font(.caption)
                                .foregroundColor(.gray)
                            Text("Train has made previous stops")
                                .font(.caption)
                                .foregroundColor(.gray)
                                .italic()
                        }
                        .padding(.bottom, 4)
                        .padding(.horizontal, 20)
                    }
                    
                    ForEach(journeyData.stops) { stop in
                        StopRow(
                            stop: stop,
                            isDestination: selectedDestination != nil && 
                                         stop.stationName.lowercased() == selectedDestination!.lowercased(),
                            isDeparture: checkIfDepartureStop(stop.stationName),
                            isBoarding: stop.stopStatus == "BOARDING" && !checkIfDepartureStop(stop.stationName),
                            boardingTrack: stop.stopStatus == "BOARDING" && !checkIfDepartureStop(stop.stationName) ? train.displayTrack : nil
                        )
                    }
                    
                    // Show continuation message if there are stops after destination
                    if journeyData.hasMoreStops {
                        HStack {
                            Image(systemName: "ellipsis")
                                .font(.caption)
                                .foregroundColor(.gray)
                            Text("Train continues to other stops")
                                .font(.caption)
                                .foregroundColor(.gray)
                                .italic()
                        }
                        .padding(.top, 4)
                        .padding(.horizontal, 20)
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
        }
        .background(Color.white.opacity(0.9))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
    }
}

// MARK: - Status Card
struct StatusCard: View {
    let train: Train
    @EnvironmentObject private var appState: AppState
    
    private var isActuallyBoarding: Bool {
        (train.statusV2?.current == "BOARDING" && train.displayTrack != nil) ||
        (train.statusV2 == nil && train.displayStatus == .boarding && train.displayTrack != nil)
    }

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
        if isActuallyBoarding { // Orange card background
            return .white
        } else if let statusV2 = train.statusV2, !(statusV2.current == "BOARDING" && train.displayTrack == nil) {
            // statusV2 is present and has its own blue background (unless it's the specific case we made "Scheduled" for statusV2 which also has blue bg)
            return .white
        } else {
            // Covers:
            // 1. Legacy "Scheduled" (boarding without track, white card bg)
            // 2. Legacy non-boarding (white card bg)
            return .black
        }
    }
    
    var body: some View {
        VStack(spacing: 16) {
            // Enhanced status display using new status_v2 if available
            if let statusV2 = train.statusV2 {
                // Use enhanced status with location info
                VStack(spacing: 8) {
                    HStack {
                        // Pulsing Icon: Show only if statusV2.current == "BOARDING" && train.displayTrack != nil
                        if statusV2.current == "BOARDING" && train.displayTrack != nil {
                            Image(systemName: "circle.fill")
                                .foregroundColor(.white)
                                .font(.title2)
                                .symbolEffect(.pulse)
                        }
                        
                        // Status Text Logic
                        if statusV2.current == "BOARDING" && train.displayTrack != nil {
                            Text("Boarding on Track \(train.displayTrack!)") // Safe to force unwrap due to condition
                                .font(.title2)
                                .fontWeight(.bold)
                                .foregroundColor(.white)
                        } else if statusV2.current == "BOARDING" && train.displayTrack == nil {
                            Text("Scheduled") // Display "Scheduled"
                                .font(.title2)
                                .fontWeight(.bold)
                                .foregroundColor(.white) // Style like other statusV2 text
                        } else {
                            Text(statusV2.current) // Default status text
                                .font(.title2)
                                .fontWeight(.bold)
                                .foregroundColor(.white)
                        }
                    }
                    
                    // Show location info
                    Text(statusV2.location)
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.9))
                }
                .padding()
                .frame(maxWidth: .infinity)
                // Background color for the VStack
                .background(statusV2.current == "BOARDING" && train.displayTrack != nil ? Color.orange.opacity(0.9) : Color.blue.opacity(0.8))
                .cornerRadius(12)
            } else { // No statusV2, use displayStatus for logic
                if train.displayStatus == .boarding && train.displayTrack != nil {
                    // This is the "actual boarding" case for legacy
                    HStack {
                        Image(systemName: "circle.fill")
                            .foregroundColor(.white)
                            .font(.title2)
                            .symbolEffect(.pulse)

                        Text("Boarding on Track \(train.displayTrack!)") // displayTrack is non-nil here
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(.white)
                    }
                    .padding()
                    .frame(maxWidth: .infinity)
                    .background(Color.orange.opacity(0.9)) // Orange background for this specific case
                    .cornerRadius(12)
                } else if train.displayStatus == .boarding && train.displayTrack == nil {
                    // Boarding but no track, show "Scheduled"
                    Text("Scheduled")
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundColor(.black) // Explicit black text on white card background
                        .padding()
                        .frame(maxWidth: .infinity, alignment: .center)
                }
                // If not (train.displayStatus == .boarding), then nothing is shown from this block for status.
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
            
            // Track or prediction
            if train.displayStatus != .boarding {
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
                    OwlPredictionView(prediction: prediction)
                } else {
                    // Debug: Show why no predictions
                    VStack {
                        Text("🔍 No Track Prediction")
                            .font(.caption)
                            .foregroundColor(.black.opacity(0.6))
                        if train.isConsolidated {
                            Text("Consolidated train with no prediction data")
                                .font(.caption2)
                                .foregroundColor(.black.opacity(0.5))
                        }
                    }
                }
            }
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(isActuallyBoarding ? Color.orange.opacity(0.9) : Color.white.opacity(0.9))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
        
        // Show detailed prediction below the card if no track assigned
        if train.displayStatus != .boarding,
           (train.displayTrack == nil || train.displayTrack!.isEmpty),
           let prediction = train.predictionData {
            OwlPredictionView(prediction: prediction)
                .padding(.top, -8)
        }
    }
}

// MARK: - Owl Prediction View
struct OwlPredictionView: View {
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
                        .frame(width: 60, alignment: .leading)
                    
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
    
    private var timeDisplay: (scheduled: String?, actual: String?) {
        let formatter = DateFormatter.easternTime(time: .short)
        
        guard let scheduledTime = stop.scheduledTime else {
            if let departureTime = stop.departureTime {
                return (nil, formatter.string(from: departureTime))
            }
            return (nil, "--:--")
        }
        
        let scheduled = formatter.string(from: scheduledTime)
        
        if let departureTime = stop.departureTime {
            let actual = formatter.string(from: departureTime)
            if scheduled != actual {
                return (scheduled, actual)
            }
        }
        
        return (nil, scheduled)
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
                    
                    if stop.stopStatus == "BOARDING" {
                        if let track = boardingTrack {
                            Text("BOARDING on Track \(track)")
                                .font(.caption)
                                .fontWeight(.bold)
                                .foregroundColor(.orange)
                        } else {
                            Text("BOARDING")
                                .font(.caption)
                                .fontWeight(.bold)
                                .foregroundColor(.orange)
                        }
                    } else if stop.departed {
                        // Check if recently departed (within 2 minutes)
                        if let departureTime = stop.departureTime ?? stop.scheduledTime {
                            let timeSinceDeparture = Date().timeIntervalSince(departureTime)
                            if timeSinceDeparture < 120 { // Within 2 minutes
                                Text("JUST DEPARTED")
                                    .font(.caption)
                                    .fontWeight(.bold)
                                    .foregroundColor(.green)
                                    .scaleEffect(showPulse ? 1.1 : 1.0)
                                    .onAppear {
                                        withAnimation(.easeInOut(duration: 0.5).repeatForever(autoreverses: true)) {
                                            showPulse = true
                                        }
                                    }
                            } else {
                                Text("DEPARTED")
                                    .font(.caption)
                                    .foregroundColor(.gray)
                            }
                        } else {
                            Text("DEPARTED")
                                .font(.caption)
                                .foregroundColor(.gray)
                        }
                    } else if !stop.departed {
                        // Check if approaching (within 3 minutes)
                        if let arrivalTime = stop.scheduledTime {
                            let timeToArrival = arrivalTime.timeIntervalSince(Date())
                            if timeToArrival > 0 && timeToArrival < 180 { // Within 3 minutes
                                Text("APPROACHING")
                                    .font(.caption)
                                    .fontWeight(.bold)
                                    .foregroundColor(.blue)
                                    .scaleEffect(showPulse ? 1.1 : 1.0)
                                    .onAppear {
                                        withAnimation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true)) {
                                            showPulse = true
                                        }
                                    }
                            }
                        }
                    }
                }
                
                HStack(spacing: 4) {
                    if let scheduledTime = timeDisplay.scheduled {
                        Text(scheduledTime)
                            .font(.caption)
                            .strikethrough()
                            .foregroundColor(.gray)
                    }
                    
                    if let actualTime = timeDisplay.actual {
                        Text(actualTime)
                            .font(.caption)
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
        if stop.departed {
            // Check if recently departed
            if let departureTime = stop.departureTime ?? stop.scheduledTime {
                let timeSinceDeparture = Date().timeIntervalSince(departureTime)
                if timeSinceDeparture < 120 { // Within 2 minutes
                    return .green
                }
            }
            return .gray
        }
        // Check if approaching
        if let arrivalTime = stop.scheduledTime {
            let timeToArrival = arrivalTime.timeIntervalSince(Date())
            if timeToArrival > 0 && timeToArrival < 180 { // Within 3 minutes
                return .blue
            }
        }
        return .blue
    }
    
    private var textColor: Color {
        if isDestination { return .green }
        if isDeparture { return .orange }
        if stop.departed { return .gray }
        return .black
    }
    
    private var timeColor: Color {
        if isDestination { return .green }
        if isDeparture { return .orange }
        if stop.departed { return .gray }
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
    
    // Flexible initialization parameters
    private let databaseId: Int?
    private let trainNumber: String?
    private let preferredStationCode: String?
    
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
    
    func loadTrainDetails(fromStationCode: String? = nil) async {
        isLoading = true
        error = nil
        
        do {
            // Use the flexible API method
            train = try await apiService.fetchTrainDetailsFlexible(
                id: databaseId.map(String.init),
                trainId: trainNumber,
                fromStationCode: fromStationCode ?? preferredStationCode
            )
        } catch {
            self.error = error.localizedDescription
        }
        
        isLoading = false
    }
    
    func refreshTrainDetails(fromStationCode: String? = nil) async {
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
                // Modified condition for boarding haptic:
                // Previous state was not boarding OR was boarding but no track
                // New state is boarding AND has a track
                if (currentTrain.displayStatus != .boarding || currentTrain.displayTrack == nil) &&
                   (newTrain.displayStatus == .boarding && newTrain.displayTrack != nil) {
                    // Haptic feedback
                    UINotificationFeedbackGenerator().notificationOccurred(.warning)
                }
                
                // Check for track assignment using consolidated display track
                if currentTrain.displayTrack == nil && newTrain.displayTrack != nil {
                    UINotificationFeedbackGenerator().notificationOccurred(.success)
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
    @State private var isExpanded = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                Image(systemName: "network")
                    .foregroundColor(.blue)
                Text("Experimental: Multi-Source Data")
                    .font(.headline)
                    .foregroundColor(.white)
                Spacer()
                Button(action: { isExpanded.toggle() }) {
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .foregroundColor(.white.opacity(0.7))
                }
            }
            
            // Expanded details
            if isExpanded, let sources = train.dataSources {
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
        .animation(.easeInOut(duration: 0.3), value: isExpanded)
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
    
    init(train: Train, displayMode: JourneyDisplayMode = .full, showTrainHeader: Bool = false, originStationCode: String? = nil, destinationStationCode: String? = nil) {
        self.train = train
        self.displayMode = displayMode
        self.showTrainHeader = showTrainHeader
        self.originStationCode = originStationCode
        self.destinationStationCode = destinationStationCode
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
            // Main status display
            statusHeader
            
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
    private var statusHeader: some View {
        VStack(spacing: 8) {
            HStack {
                Text(statusEmoji)
                    .font(.title2)

                // Updated Text display for statusHeader
                let currentDisplayStatus = self.displayStatus // This will be "Scheduled" if boarding w/o track
                if train.statusV2?.current == "BOARDING" && train.displayTrack != nil {
                    Text("Boarding on Track \(train.displayTrack!)")
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundColor(.black)
                } else if train.statusV2 == nil && train.displayStatus == .boarding && train.displayTrack != nil {
                    Text("Boarding on Track \(train.displayTrack!)")
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundColor(.black)
                } else {
                    Text(currentDisplayStatus) // Shows "Scheduled" (if boarding w/o track) or other statuses
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundColor(.black)
                }
                Spacer()
            }
            
            // Location info if available (but not for SCHEDULED status)
            if let location = train.statusV2?.location, train.statusV2?.current != "SCHEDULED" {
                HStack {
                    Text(location)
                        .font(.subheadline)
                        .foregroundColor(.black.opacity(0.7))
                    Spacer()
                }
            }
        }
    }
    
    @ViewBuilder
    private var progressSection: some View {
        if hasProgressData {
            let progress = userJourneyProgress
            HStack {
                if progress.total > 0 {
                    Text("Stop \(progress.completed) of \(progress.total) completed")
                        .font(.subheadline)
                        .foregroundColor(.black)
                } else {
                    Text("Journey in progress")
                        .font(.subheadline)
                        .foregroundColor(.black)
                }
                Spacer()
                Text("(\(progress.percentage)%)")
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(.black.opacity(0.6))
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(Color.white.opacity(0.2))
            .cornerRadius(8)
        }
    }
    
    @ViewBuilder
    private var departureSection: some View {
        if let progress = train.progress, let lastDeparted = progress.lastDeparted {
            HStack {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.green)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Left \(Stations.displayNameForCode(lastDeparted.stationCode))")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(.black)
                    
                    Text(delayText(delayMinutes: lastDeparted.delayMinutes))
                        .font(.caption)
                        .foregroundColor(.black.opacity(0.6))
                }
                Spacer()
            }
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
    
    /// Calculate user-specific journey progress between their origin and destination
    private var userJourneyProgress: (completed: Int, total: Int, percentage: Int) {
        // Use API progress data if available and no user stations specified
        if let progress = train.progress, originStationCode == nil || destinationStationCode == nil {
            return (completed: progress.stopsCompleted, total: progress.totalStops, percentage: progress.journeyPercent)
        }
        
        // Calculate from stops data for user's specific journey
        guard let stops = train.stops,
              let originCode = originStationCode,
              let destinationCode = destinationStationCode,
              let originIndex = stops.firstIndex(where: { Stations.getStationCode($0.stationName) == originCode }),
              let destIndex = stops.firstIndex(where: { Stations.getStationCode($0.stationName) == destinationCode }),
              originIndex < destIndex else {
            // Fallback to API data or default
            if let progress = train.progress {
                return (completed: progress.stopsCompleted, total: progress.totalStops, percentage: progress.journeyPercent)
            }
            return (completed: 0, total: 0, percentage: 0)
        }
        
        // Get the journey segment stops (including origin and destination)
        let journeyStops = Array(stops[originIndex...destIndex])
        
        // Count departed stops in the journey, excluding the origin (user hasn't "completed" origin until they leave)
        let departedStopsInJourney = journeyStops.dropFirst().filter { $0.departed }
        let completedStops = departedStopsInJourney.count
        
        // Total stops in journey (excluding origin since it's the starting point)
        let totalStops = journeyStops.count - 1
        
        // Calculate percentage
        let percentage = totalStops > 0 ? Int((Double(completedStops) / Double(totalStops)) * 100) : 0
        
        return (completed: completedStops, total: totalStops, percentage: percentage)
    }
    
    private var displayStatus: String {
        let rawStatus: String
        if let statusV2 = train.statusV2 {
            rawStatus = statusV2.current
        } else {
            rawStatus = train.displayStatus.displayText.uppercased()
        }
        return humanFriendlyStatus(rawStatus)
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
            return "Arrived"
        case "CANCELLED":
            return "Cancelled"
        case "ALL_ABOARD":
            return "All Aboard"
        default:
            return status.capitalized
        }
    }
    
    private var statusEmoji: String {
        let status = train.statusV2?.current ?? train.displayStatus.displayText.uppercased()
        switch status {
        case "EN_ROUTE", "DEPARTED":
            return "🚆"
        case "BOARDING":
            if train.displayTrack != nil {
                return "🚪" // Boarding with track
            } else {
                return "🕐" // Scheduled/OnTime emoji for boarding without track
            }
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
        let status = train.statusV2?.current ?? train.displayStatus.displayText.uppercased()
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
        return train.progress != nil
    }
    
    private var hasDepartureInfo: Bool {
        return train.progress?.lastDeparted != nil
    }
    
    private var hasNextArrivalInfo: Bool {
        return train.progress?.nextArrival != nil
    }
    
    private func delayText(delayMinutes: Int) -> String {
        if delayMinutes == 0 {
            return "Departed on time"
        } else if delayMinutes > 0 {
            return "Departed \(delayMinutes) min late"
        } else {
            return "Departed \(abs(delayMinutes)) min early"
        }
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
