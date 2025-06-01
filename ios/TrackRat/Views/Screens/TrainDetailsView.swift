import SwiftUI
import Combine

struct TrainDetailsView: View {
    @EnvironmentObject private var appState: AppState
    @StateObject private var viewModel: TrainDetailsViewModel
    @State private var showingHistory = false
    
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
                            // Live Activity controls
                            if #available(iOS 16.1, *) {
                                LiveActivityControls(
                                    train: train,
                                    origin: appState.selectedDeparture ?? "",
                                    destination: appState.selectedDestination ?? "",
                                    originCode: appState.departureStationCode ?? "",
                                    destinationCode: Stations.getStationCode(appState.selectedDestination ?? "") ?? ""
                                )
                            }
                            
                            // Combined card with all details
                            CombinedDetailsCard(train: train, selectedDestination: appState.selectedDestination)
                            
                            // Consolidated data section
                            if train.isConsolidated {
                                ConsolidatedDataCard(train: train)
                            }
                            
                            // Show history button
                            Button {
                                showingHistory = true
                            } label: {
                                HStack {
                                    Image(systemName: "clock.arrow.circlepath")
                                    Text("details from past trains")
                                        .font(.subheadline)
                                }
                                .foregroundColor(.white.opacity(0.8))
                            }
                            .padding(.top)
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
        .sheet(isPresented: $showingHistory) {
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
    
    private var departureTime: String {
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        formatter.dateFormat = "EEEE, MMMM d 'at' h:mm a"
        return formatter.string(from: train.departureTime)
    }
    
    private func filterStopsToDestination(stops: [Stop], destination: String?) -> [Stop] {
        guard let destination = destination else { return stops }
        
        // Find the index of the destination
        if let destinationIndex = stops.firstIndex(where: { 
            $0.stationName.lowercased() == destination.lowercased() 
        }) {
            // Return stops up to and including the destination
            return Array(stops.prefix(destinationIndex + 1))
        }
        
        // If destination not found, return all stops
        return stops
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
                if train.displayStatus == .boarding {
                    HStack {
                        Image(systemName: "circle.fill")
                            .foregroundColor(.white)
                            .font(.title2)
                            .symbolEffect(.pulse)
                        
                        Text("BOARDING")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(.white)
                        
                        if let track = train.track {
                            Text("Track \(track)")
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
            
            // Journey Progress Indicator
            if let stops = train.stops, !stops.isEmpty {
                let journeyProgress = train.calculateJourneyProgress(
                    from: appState.departureStationCode ?? "",
                    to: Stations.getStationCode(selectedDestination ?? "") ?? ""
                )
                if journeyProgress.progress > 0 && journeyProgress.progress < 1 {
                    TrainProgressIndicator(progress: journeyProgress.progress)
                        .padding(.horizontal)
                        .padding(.vertical, 8)
                }
            }
            
            // Stops section
            VStack(alignment: .leading, spacing: 12) {
                if let stops = train.stops, !stops.isEmpty {
                    let filteredStops = filterStopsToDestination(stops: stops, destination: selectedDestination)
                    let hasMoreStops = filteredStops.count < stops.count
                    
                    ForEach(filteredStops) { stop in
                        StopRow(
                            stop: stop,
                            isDestination: selectedDestination != nil && 
                                         stop.stationName.lowercased() == selectedDestination!.lowercased(),
                            isDeparture: checkIfDepartureStop(stop.stationName),
                            isBoarding: train.displayStatus == .boarding,
                            boardingTrack: stop.stopStatus == "BOARDING" ? train.displayTrack : nil
                        )
                    }
                    
                    if hasMoreStops {
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
    
    private var departureTime: String {
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        formatter.dateFormat = "EEEE, MMMM d 'at' h:mm a"
        return formatter.string(from: train.departureTime)
    }
    
    var body: some View {
        VStack(spacing: 16) {
            // Boarding status
            if train.displayStatus == .boarding {
                HStack {
                    Image(systemName: "circle.fill")
                        .foregroundColor(.white)
                        .font(.title2)
                        .symbolEffect(.pulse)
                    
                    Text("BOARDING")
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundColor(.white)
                    
                    if let track = train.track {
                        Text("Track \(track)")
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
                .foregroundColor(train.displayStatus == .boarding ? .white : .black)
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
        .frame(maxWidth: .infinity)
        .background(train.displayStatus == .boarding ? Color.orange.opacity(0.9) : Color.white.opacity(0.9))
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
                        isBoarding: stop.stopStatus == "BOARDING",
                        boardingTrack: stop.stopStatus == "BOARDING" ? train.track : nil
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
                    Text(stop.stationName)
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
                if currentTrain.displayStatus != .boarding && newTrain.displayStatus == .boarding {
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
                Text("Multi-Source Data")
                    .font(.headline)
                    .foregroundColor(.white)
                Spacer()
                Button(action: { isExpanded.toggle() }) {
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .foregroundColor(.white.opacity(0.7))
                }
            }
            
            // Summary
            if let sources = train.dataSources {
                Text("\(sources.count) data sources")
                    .font(.subheadline)
                    .foregroundColor(.white.opacity(0.8))
            }
            
            // Track assignment info
            if let trackAssignment = train.trackAssignment {
                HStack {
                    Text("Authoritative Track:")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.7))
                    Spacer()
                    if let track = trackAssignment.track, !track.isEmpty {
                        Text("Track \(track)")
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundColor(.orange)
                        if let assignedBy = trackAssignment.assignedBy {
                            Text("(\(assignedBy))")
                                .font(.caption2)
                                .foregroundColor(.white.opacity(0.6))
                        }
                    } else {
                        Text("Not assigned yet")
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundColor(.yellow)
                    }
                }
            }
            
            // Expanded details
            if isExpanded, let sources = train.dataSources {
                Divider()
                    .background(Color.white.opacity(0.3))
                
                ForEach(sources, id: \.origin) { source in
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

#Preview {
    NavigationStack {
        TrainDetailsView(trainId: 1)
            .environmentObject(AppState())
    }
}
