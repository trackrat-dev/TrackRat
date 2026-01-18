import SwiftUI
import ActivityKit

struct TrainDetailsView: View {
    @EnvironmentObject private var appState: AppState
    @StateObject private var viewModel: TrainDetailsViewModel
    @ObservedObject private var subscriptionService = SubscriptionService.shared
    // PERFORMANCE: Track visibility to prevent polling when view is not visible
    @State private var isViewVisible = false
    @State private var showingPaywall = false
    @State private var paywallContext: PaywallContext = .generic

    let trainId: Int  // Keep for backwards compatibility

    // Legacy initializer for database ID
    init(trainId: Int) {
        self.trainId = trainId
        let VModel = TrainDetailsViewModel(trainId: trainId)
        self._viewModel = StateObject(wrappedValue: VModel)
    }

    // New initializer for train number
    init(trainNumber: String, fromStation: String? = nil, journeyDate: Date? = nil) {
        self.trainId = 0  // Not used for train number based initialization
        let VModel = TrainDetailsViewModel(
            databaseId: nil,
            trainNumber: trainNumber,
            fromStationCode: fromStation,
            journeyDate: journeyDate
        )
        self._viewModel = StateObject(wrappedValue: VModel)
    }

    // PATH trains display destination instead of synthetic train ID
    private var trainNavigationTitle: String {
        guard let train = viewModel.train else { return "Loading..." }
        return train.dataSource == "PATH" ? train.destination : "Train \(train.trainId)"
    }

    var body: some View {
        VStack(spacing: 0) {
            // Fixed header - replaces system navigation bar to avoid layout shift
            TrackRatNavigationHeader(
                // PATH trains display destination instead of synthetic train ID
                title: trainNavigationTitle,
                showCloseButton: false,
                trailingContent: {
                    HStack(alignment: .center, spacing: 12) {
                        if let train = viewModel.train,
                           let originCode = appState.departureStationCode,
                           !originCode.isEmpty {
                            TrainFollowToolbarButton(
                                train: train,
                                destinationName: appState.selectedDestination,
                                originCode: originCode,
                                destinationCode: Stations.getStationCode(appState.selectedDestination ?? "") ?? ""
                            )

                            ShareButton(
                                train: train,
                                fromStationCode: appState.departureStationCode,
                                destinationName: appState.selectedDestination
                            )
                        }

                        Button("Close") {
                            appState.navigationPath = NavigationPath()
                        }
                        .font(.body)
                        .fontWeight(.medium)
                        .foregroundColor(.white)
                        .buttonStyle(.plain)
                    }
                }
            )

            // Scrollable content
            ScrollView {
                VStack {
                    if viewModel.isLoading && viewModel.train == nil {
                        TrackRatLoadingView(message: "Loading train details...")
                            .frame(maxWidth: .infinity, minHeight: 400)
                    } else if let error = viewModel.error {
                        ErrorView(message: error) {
                            Task {
                                await viewModel.loadTrainDetails(
                                    fromStationCode: appState.departureStationCode,
                                    toStationCode: appState.destinationStationCode,
                                    selectedDestinationName: appState.selectedDestination
                                )
                            }
                        }
                    } else if let train = viewModel.train {
                        VStack(spacing: 16) {
                            // Train performance summary (similar trains + historical) - Pro feature
                            // Hide after train departs from user's origin station
                            if let originCode = appState.departureStationCode,
                               !train.hasTrainDepartedFromStation(originCode) {
                                if subscriptionService.isPro {
                                    TrainStatsSummaryView(
                                        trainId: train.trainId,
                                        fromStation: appState.departureStationCode,
                                        toStation: appState.destinationStationCode,
                                        journeyDate: train.journeyDate,
                                        onTrainTap: { selectedTrainId in
                                            // Navigate to the selected train's detail view
                                            appState.navigationPath.append(
                                                NavigationDestination.trainDetailsFlexible(
                                                    trainNumber: selectedTrainId,
                                                    fromStation: appState.departureStationCode,
                                                    journeyDate: nil
                                                )
                                            )
                                        }
                                    )
                                } else {
                                    // Locked historical data for free users
                                    ProFeatureLockView(
                                        feature: .historicalData,
                                        context: .historicalData,
                                        showingPaywall: $showingPaywall
                                    )
                                }
                            }

                            CombinedDetailsCard(
                                train: train,
                                selectedDestination: appState.selectedDestination,
                                selectedDestinationCode: appState.destinationStationCode,
                                displayableTrainStops: viewModel.displayableTrainStops,
                                hasPreviousDisplayStops: viewModel.hasPreviousDisplayStops,
                                hasMoreDisplayStops: viewModel.hasMoreDisplayStops,
                                journeyProgressPercentage: viewModel.journeyProgressPercentage,
                                journeyStopsCompleted: viewModel.journeyStopsCompleted,
                                journeyTotalStops: viewModel.journeyTotalStops
                            )
                        }
                        .padding()
                        // Force view update by using a composite ID that includes changing data
                        .id("\(train.id)-\(train.calculateStatus(fromStationCode: appState.departureStationCode ?? "").rawValue)-\(viewModel.stopStatesHash)")
                    }
                } // VStack
            }
        }
        .navigationBarHidden(true)
        .task {
            await viewModel.loadTrainDetails(
                fromStationCode: appState.departureStationCode,
                toStationCode: appState.destinationStationCode,
                selectedDestinationName: appState.selectedDestination
            )
        }
        .task(id: isViewVisible) {
            // Auto-refresh task that cancels automatically when view disappears
            guard isViewVisible else { return }
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(30))
                guard !Task.isCancelled, isViewVisible else { break }

                // Skip polling if LiveActivity is already tracking this train
                if let activity = LiveActivityService.shared.currentActivity,
                   activity.attributes.trainNumber == viewModel.train?.trainId {
                    continue
                }

                await viewModel.refreshTrainDetails(
                    fromStationCode: appState.departureStationCode,
                    toStationCode: appState.destinationStationCode,
                    selectedDestinationName: appState.selectedDestination
                )
            }
        }
        .onAppear {
            isViewVisible = true
        }
        .onDisappear {
            isViewVisible = false
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
        .sheet(isPresented: $showingPaywall) {
            PaywallView(context: paywallContext)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
    }

    private func showPaywall(for context: PaywallContext) {
        paywallContext = context
        showingPaywall = true
    }
}

// MARK: - Combined Details Card
struct CombinedDetailsCard: View {
    let train: TrainV2
    let selectedDestination: String?
    let selectedDestinationCode: String?
    @EnvironmentObject private var appState: AppState
    @ObservedObject private var subscriptionService = SubscriptionService.shared
    @State private var showingPaywall = false
    @State private var paywallContext: PaywallContext = .generic

    // ViewModel provided properties
    let displayableTrainStops: [StopV2]
    let hasPreviousDisplayStops: Bool
    let hasMoreDisplayStops: Bool
    let journeyProgressPercentage: Int
    let journeyStopsCompleted: Int
    let journeyTotalStops: Int

    private var departureTime: String {
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        formatter.dateFormat = "EEEE, MMMM d 'at' h:mm a"
        
        // Use origin-specific departure time if we have a departure station code
        if let departureStationCode = appState.departureStationCode {
            guard let originDepartureTime = train.getDepartureTime(fromStationCode: departureStationCode) else {
                return "--:--"
            }
            return formatter.string(from: originDepartureTime)
        }
        
        return formatter.string(from: train.departureTime)
    }
        
    // Check if predictions should be shown for the entire journey
    private var shouldShowJourneyPredictions: Bool {
        // Find the user's destination stop by CODE (reliable matching)
        guard let destinationCode = selectedDestinationCode,
              let destinationStop = displayableTrainStops.first(where: { stop in
                  stop.stationCode.uppercased() == destinationCode.uppercased()
              }) else {
            return false
        }
        
        // Check if destination has significant predicted delay (≥4 minutes)
        guard let predictedArrival = destinationStop.predictedArrival,
              let scheduledArrival = destinationStop.scheduledArrival,
              let samples = destinationStop.predictedArrivalSamples,
              samples > 0,
              !destinationStop.hasDepartedStation else {
            return false
        }
        
        let delaySeconds = predictedArrival.timeIntervalSince(scheduledArrival)
        return delaySeconds > 240  // ≥4 minutes
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
            return Color(white: 0.55)
        }
    }
    
    /// Enhanced logic to determine if track predictions should be shown
    private var shouldShowPredictions: Bool {
        // Don't show predictions for cancelled trains
        if train.isCancelled {
            return false
        }
        
        // Don't show predictions if train has departed from user's origin station
        if let originCode = appState.departureStationCode,
           train.hasTrainDepartedFromStation(originCode) {
            return false
        }
        
        // Show predictions only for NY Penn Station and when track is not assigned
        return StaticTrackDistributionService.shared.shouldShowPredictions(for: train)
    }
    
    /// Check if train is boarding specifically at the user's origin station
    private var isBoardingAtOrigin: Bool {
        guard let departureCode = appState.departureStationCode else {
            return false
        }
        
        // Simple track-based boarding detection
        return train.isBoardingAtStation(departureCode)
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Top section with status info
            VStack(spacing: 0) {
                // Status Display for TrainV2
                VStack(spacing: 12) {
                    // Show CANCELLED banner if train is cancelled
                    let contextStatus = train.calculateStatus(fromStationCode: appState.departureStationCode ?? "")
                    if contextStatus == .cancelled {
                        VStack(spacing: 8) {
                            Text("CANCELLED")
                                .font(.largeTitle)
                                .fontWeight(.bold)
                                .foregroundColor(.white)
                        }
                        .padding()
                        .frame(maxWidth: .infinity)
                        .background(Color.red.opacity(0.9))
                        .cornerRadius(TrackRatTheme.CornerRadius.md)
                        .padding(.top, 8)
                    }
                    // Main status with boarding indication
                    else if isBoardingAtOrigin {
                        HStack {
                            Image(systemName: "circle.fill")
                                .foregroundColor(.white)
                                .font(.title2)
                                .symbolEffect(.pulse)
                            
                            if let track = train.track {
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
                        .cornerRadius(TrackRatTheme.CornerRadius.md)
                        .padding(.top, 8)
                    }
                }
                
                // Track predictions section (Pro feature)
                if shouldShowPredictions {
                    if subscriptionService.isPro {
                        SegmentedTrackPredictionView(
                            train: train,
                            isDepartingFromNYPenn: appState.departureStationCode == "NY"
                        )
                        .allowsHitTesting(true)  // Ensure predictions card is interactive
                    } else {
                        // Locked track predictions for free users
                        ProFeatureLockView(
                            feature: .trackPredictions,
                            context: .trackPredictions,
                            showingPaywall: $showingPaywall
                        )
                    }
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
                                .foregroundColor(Color(white: 0.55))
                            Text("Train has previous stops")
                                .font(.caption)
                                .foregroundColor(Color(white: 0.55))
                                .italic()
                        }
                        .padding(.bottom, 4)
                        .padding(.horizontal, 20)
                    }
                    
                    ForEach(displayableTrainStops) { stop in
                        let isDepartureStop = appState.departureStationCode != nil &&
                            stop.stationCode.uppercased() == appState.departureStationCode!.uppercased()
                        StopRowV2(
                            stop: stop,
                            isDestination: selectedDestinationCode != nil &&
                                         stop.stationCode.uppercased() == selectedDestinationCode!.uppercased(),
                            isDeparture: isDepartureStop,
                            isBoarding: train.isBoardingAtStation(stop.stationCode) && isDepartureStop,
                            boardingTrack: train.isBoardingAtStation(stop.stationCode) && isDepartureStop ? stop.track : nil,
                            train: train,
                            departureStationCode: appState.departureStationCode,
                            shouldShowJourneyPredictions: shouldShowJourneyPredictions
                        )
                    }
                    
                    if hasMoreDisplayStops {
                        HStack {
                            Image(systemName: "ellipsis")
                                .font(.caption)
                                .foregroundColor(Color(white: 0.55))
                            Text("Train has later stops")
                                .font(.caption)
                                .foregroundColor(Color(white: 0.55))
                                .italic()
                        }
                        .padding(.top, 4)
                        .padding(.horizontal, 20)
                    }

                    // Action buttons row
                    HStack(spacing: 20) {
                        if let originCode = appState.departureStationCode,
                           !originCode.isEmpty {
                            TrackTrainInlineButton(
                                train: train,
                                originCode: originCode,
                                destinationCode: selectedDestinationCode ?? "",
                                destinationName: selectedDestination,
                                textColor: .black.opacity(0.6)
                            )
                        }

                        FeedbackButton(
                            screen: "train_details",
                            trainId: train.trainId,
                            originCode: appState.departureStationCode,
                            destinationCode: selectedDestinationCode,
                            textColor: .black.opacity(0.6)
                        )
                    }
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.top, 8)
                } else {
                    Text("No stops information available for this journey segment.")
                        .foregroundColor(.black.opacity(0.6))
                        .italic()
                        .frame(maxWidth: .infinity)
                        .padding()
                }
            }
            .padding()
            
        }
        .background(Color.white.opacity(0.9))
        .cornerRadius(TrackRatTheme.CornerRadius.lg)
        .trackRatShadow()
        .sheet(isPresented: $showingPaywall) {
            PaywallView(context: paywallContext)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
    }

    private func showPaywall(for context: PaywallContext) {
        paywallContext = context
        showingPaywall = true
    }
}

// Note: StatusV2 functionality is now integrated directly into TrainV2 model

// MARK: - Stop Row V2
struct StopRowV2: View {
    let stop: StopV2
    let isDestination: Bool
    let isDeparture: Bool
    let isBoarding: Bool
    let boardingTrack: String?
    let train: TrainV2
    let departureStationCode: String?
    let shouldShowJourneyPredictions: Bool

    @State private var showPulse = false
    @State private var showPredictionExplanation = false
    
    // Helper to check if this stop is cancelled
    private var isCancelled: Bool {
        return stop.rawStatus?.amtrakStatus == "CANCELLED"
    }
    
    // Helper to determine if this is the origin station (first stop)
    private var isOriginStation: Bool {
        return isDeparture
    }
    
    // Helper to determine if this is final destination (last stop)
    private var isFinalDestination: Bool {
        return isDestination
    }

    // Determine if this is the next important station
    private var isNextImportantStation: Bool {
        // If train hasn't departed from origin yet, highlight the origin
        let hasDeparted = departureStationCode.map { train.hasTrainDepartedFromStation($0) } ?? false
        if !hasDeparted {
            return isDeparture
        }
        
        // Fallback: Find first non-departed stop
        if let stops = train.stops {
            let firstUpcomingStop = stops.first { !$0.hasDepartedStation }
            if let upcoming = firstUpcomingStop {
                return stop.stationCode == upcoming.stationCode
            }
        }
        
        // If journey seems complete (all stops departed), highlight destination
        let allDeparted = train.stops?.allSatisfy { $0.hasDepartedStation } ?? false
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
        
        let formatter = DateFormatter.easternTimeShort

        // For departed stops: Show only "Departed X:XX PM" with delay indicator
        if stop.hasDepartedStation {
            if let correctedDepartureTime = stop.actualDeparture {
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
            if let correctedDepartureTime = stop.actualDeparture {
                let delayText = departureDelayText(actual: correctedDepartureTime, scheduled: stop.scheduledDeparture)
                let departureText = "Departure: \(formatter.string(from: correctedDepartureTime))" + (delayText.isEmpty ? "" : " (\(delayText))")
                return (nil, departureText, [])
            } else if let estimatedDeparture = stop.updatedDeparture {
                let departureText = "Departure: \(formatter.string(from: estimatedDeparture))"
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
            } else if let estimatedArrival = stop.updatedArrival {
                let arrivalText = "Arrival: \(formatter.string(from: estimatedArrival))"
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
        } else if let estimatedArrival = stop.updatedArrival {
            let arrivalText = "Arrival: \(formatter.string(from: estimatedArrival))"
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
        } else if delayMinutes < -1 {
            return "\(abs(delayMinutes))m early"
        }
        return "" // Don't show anything for on-time or 1 minute early
    }
    
    private func departureDelayText(actual: Date, scheduled: Date?) -> String {
        guard let scheduled = scheduled else { return "" }
        let delayMinutes = Int(actual.timeIntervalSince(scheduled) / 60)
        if delayMinutes > 1 {
            return "+\(delayMinutes)m delay"
        } else if delayMinutes < -2 {
            return "\(abs(delayMinutes))m early"
        }
        return "" // Don't show anything for on-time or 1 minute early
    }
    
    var body: some View {
        HStack(spacing: 12) {
            // Stop indicator
            Circle()
                .fill(stopColor)
                .frame(width: 12, height: 12)
            
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(Stations.displayName(for: stop.stationName))
                        .font(.subheadline)
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
            
            // Show prediction if available and samples > 0
            if let predictedArrival = stop.predictedArrival,
               let scheduledArrival = stop.scheduledArrival,
               let samples = stop.predictedArrivalSamples,
               samples > 0,
               !stop.hasDepartedStation,
               predictedArrival.timeIntervalSince(scheduledArrival) > 240,
               shouldShowJourneyPredictions {
                HStack(spacing: 4) {
                    Text("🐀✨")
                        .font(.system(size: 16))
                    Text(DateFormatter.easternTimeShort.string(from: predictedArrival))
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(predictionDelayColor(predicted: predictedArrival, scheduled: stop.scheduledArrival))
                }
                .frame(maxHeight: .infinity, alignment: .center)
                .onTapGesture {
                    showPredictionExplanation = true
                }
            } 
        }
        .padding(.vertical, 4)
        .padding(.horizontal, 8)
        .background(backgroundColor)
        .cornerRadius(TrackRatTheme.CornerRadius.sm)
        .sheet(isPresented: $showPredictionExplanation) {
            PredictionExplanationSheet()
        }
    }
    
    private var stopColor: Color {
        if isCancelled { return Color(white: 0.55) }
        if isNextImportantStation { return Color(red: 1.0, green: 0.584, blue: 0.0) }
        if stop.hasDepartedStation { return Color(white: 0.55) }
        return .black.opacity(0.6)
    }
    
    private var textColor: Color {
        if isCancelled { return Color(white: 0.55) }
        if stop.hasDepartedStation { return Color(white: 0.55) }
        return .black
    }
    
    private func predictionDelayColor(predicted: Date, scheduled: Date?) -> Color {
        guard let scheduled = scheduled else {
            return .black  // Default to black if no scheduled time
        }
        
        let delaySeconds = predicted.timeIntervalSince(scheduled)
        let delayMinutes = delaySeconds / 60.0
        
        if delayMinutes >= 5 && delayMinutes <= 9 {
            return .black          // 5-9 minutes: black text
        } else if delayMinutes >= 10 && delayMinutes <= 19 {
            return Color(red: 0.8, green: 0.4, blue: 0)  // 10-19 minutes: slightly dark orange
        } else if delayMinutes >= 20 {
            return Color(red: 0.7, green: 0, blue: 0)    // ≥20 minutes: dark red
        } else {
            return .black          // Default to black for other cases (< 5 minutes)
        }
    }
    
    private var timeColor: Color {
        if isCancelled { return Color(white: 0.55) }
        if stop.hasDepartedStation { return Color(white: 0.55) }
        return .black.opacity(0.6)
    }
    
    private var backgroundColor: Color {
        if isCancelled { return .clear }
        if isNextImportantStation { return Color(red: 1.0, green: 0.584, blue: 0.0).opacity(0.1) }
        return .clear
    }
}

// MARK: - View Model
@MainActor
class TrainDetailsViewModel: ObservableObject {
    @Published var train: TrainV2?
    @Published var isLoading = false
    @Published var error: String?
    @Published var triggerBoardingHaptic = false
    @Published var triggerTrackAssignedHaptic = false
    
    // Flexible initialization parameters
    private let databaseId: Int?
    let trainNumber: String?  // Made public for transaction tracking
    private let preferredStationCode: String?
    private let journeyDate: Date?

    // Store current origin and destination for stop filtering
    private var currentOriginStationCode: String?
    private var currentDestinationStationCode: String?
    private var currentDestinationName: String?  // Keep for display purposes

    private let apiService = APIService.shared
    private let cacheService = TrainCacheService.shared

    // Legacy initializer for backwards compatibility
    init(trainId: Int) {
        self.databaseId = trainId
        self.trainNumber = nil
        self.preferredStationCode = nil
        self.journeyDate = nil
    }

    // New flexible initializer
    init(databaseId: Int? = nil, trainNumber: String? = nil, fromStationCode: String? = nil, journeyDate: Date? = nil) {
        self.databaseId = databaseId
        self.trainNumber = trainNumber
        self.preferredStationCode = fromStationCode
        self.journeyDate = journeyDate
    }
    
    // Computed property for backwards compatibility
    var trainId: Int {
        return databaseId ?? 0
    }
    
    // Display properties
    @Published var displayableTrainStops: [StopV2] = []
    
    private func updateDisplayableTrainStops() {
        guard let stops = train?.stops,
              let originStationCode = currentOriginStationCode,
              let destinationStationCode = currentDestinationStationCode else {
            displayableTrainStops = train?.stops ?? []
            return
        }

        // Find indices of origin and destination stops by station CODE (reliable)
        let originIndex = stops.firstIndex { stop in
            stop.stationCode.uppercased() == originStationCode.uppercased()
        }

        let destinationIndex = stops.firstIndex { stop in
            stop.stationCode.uppercased() == destinationStationCode.uppercased()
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
        let departedStates = displayableTrainStops.map { $0.hasDepartedStation }
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
              let destinationStationCode = currentDestinationStationCode else {
            hasPreviousDisplayStops = false
            hasMoreDisplayStops = false
            return
        }

        // Find the origin index by station CODE
        let originIndex = stops.firstIndex { stop in
            stop.stationCode.uppercased() == originStationCode.uppercased()
        }

        // Update hasPreviousDisplayStops
        hasPreviousDisplayStops = originIndex != nil && originIndex! > 0

        // Find destination index by station CODE
        let destinationIndex = stops.firstIndex { stop in
            stop.stationCode.uppercased() == destinationStationCode.uppercased()
        }

        // Update hasMoreDisplayStops
        if let endIdx = destinationIndex, let startIdx = originIndex, startIdx <= endIdx {
            hasMoreDisplayStops = endIdx < stops.count - 1
        } else {
            hasMoreDisplayStops = false
        }
    }
    
    private func updateJourneyProgress() {
        guard let stops = train?.stops else {
            journeyProgressPercentage = 0
            journeyStopsCompleted = 0
            journeyTotalStops = 0
            return
        }
        
        let completedStops = stops.filter { $0.hasDepartedStation }.count
        let totalStops = stops.count
        
        journeyStopsCompleted = completedStops
        journeyTotalStops = totalStops
        journeyProgressPercentage = totalStops > 0 ? (completedStops * 100) / totalStops : 0
    }
    
    func loadTrainDetails(fromStationCode: String? = nil, toStationCode: String? = nil, selectedDestinationName: String? = nil) async {
        error = nil

        // Store current origin and destination for filtering
        self.currentOriginStationCode = fromStationCode
        self.currentDestinationStationCode = toStationCode
        self.currentDestinationName = selectedDestinationName

        // CACHE-FIRST STRATEGY: Check cache before showing loading indicator
        if let cachedTrain = cacheService.getCachedTrain(
            trainId: databaseId.map(String.init),
            trainNumber: trainNumber,
            date: journeyDate,
            fromStation: fromStationCode ?? preferredStationCode
        ) {
            // Load from cache immediately - NO loading indicator
            print("📦 Loading from cache - instant display")
            train = cachedTrain
            updateComputedProperties()

            // PERFORMANCE FIX: Only fetch fresh data in background if cache is older than 30 seconds
            // This prevents the double-fetch issue where we always hit the API even with a fresh cache.
            // The 30-second timer will refresh the data anyway, so no need for immediate background fetch
            // when cache is fresh.
            let cacheAge = cacheService.getCacheAge(
                trainId: databaseId.map(String.init),
                trainNumber: trainNumber,
                date: journeyDate,
                fromStation: fromStationCode ?? preferredStationCode
            )
            if cacheAge == nil || cacheAge! > 30 {
                await refreshTrainDetailsInBackground(fromStationCode: fromStationCode, toStationCode: toStationCode, selectedDestinationName: selectedDestinationName)
            } else {
                print("📦 Cache is fresh (\(Int(cacheAge!))s old) - skipping background refresh")
            }
        } else {
            // No cache available - show loading indicator and fetch
            print("🌐 No cache available - fetching from network")
            isLoading = true

            do {
                // Use the flexible API method
                let fetchedTrain = try await apiService.fetchTrainDetailsFlexible(
                    id: databaseId.map(String.init),
                    trainId: trainNumber,
                    fromStationCode: fromStationCode ?? preferredStationCode,
                    date: journeyDate
                )

                train = fetchedTrain

                // Cache the newly fetched train
                cacheService.cacheTrain(
                    fetchedTrain,
                    trainId: databaseId.map(String.init),
                    trainNumber: trainNumber,
                    date: journeyDate,
                    fromStation: fromStationCode ?? preferredStationCode
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
    }

    /// Fetches fresh data in background without showing loading indicator
    private func refreshTrainDetailsInBackground(fromStationCode: String? = nil, toStationCode: String? = nil, selectedDestinationName: String? = nil) async {
        do {
            let identifier = trainNumber ?? (databaseId.map(String.init) ?? "unknown")
            print("🔄 Background refresh for train \(identifier)")

            let newTrain = try await apiService.fetchTrainDetailsFlexible(
                id: databaseId.map(String.init),
                trainId: trainNumber,
                fromStationCode: fromStationCode ?? preferredStationCode,
                date: journeyDate
            )

            // Cache the fresh data
            cacheService.cacheTrain(
                newTrain,
                trainId: databaseId.map(String.init),
                trainNumber: trainNumber,
                date: journeyDate,
                fromStation: fromStationCode ?? preferredStationCode
            )

            print("✅ Background refresh successful - updating UI")

            // Update UI with fresh data (seamless update)
            train = newTrain
            updateComputedProperties()

        } catch {
            // Silent failure for background refresh - user already has cached data
            print("⚠️ Background refresh failed (not critical): \(error)")
        }
    }
    
    func refreshTrainDetails(fromStationCode: String? = nil, toStationCode: String? = nil, selectedDestinationName: String? = nil) async {
        // Store current origin and destination for filtering
        self.currentOriginStationCode = fromStationCode
        self.currentDestinationStationCode = toStationCode
        self.currentDestinationName = selectedDestinationName

        // Silent refresh
        do {
            let identifier = trainNumber ?? (databaseId.map(String.init) ?? "unknown")
            print("🔄 TrainDetailsView refreshing train \(identifier) from \(fromStationCode ?? preferredStationCode ?? "none")")

            let newTrain = try await apiService.fetchTrainDetailsFlexible(
                id: databaseId.map(String.init),
                trainId: trainNumber,
                fromStationCode: fromStationCode ?? preferredStationCode,
                date: journeyDate
            )

            print("✅ TrainDetailsView refresh successful for train \(identifier)")

            // Cache the fresh data
            cacheService.cacheTrain(
                newTrain,
                trainId: databaseId.map(String.init),
                trainNumber: trainNumber,
                date: journeyDate,
                fromStation: fromStationCode ?? preferredStationCode
            )

            // Check if Live Activity should auto-end (Primary Fix)
            let liveService = LiveActivityService.shared
            if liveService.isActivityActive,
               let currentActivity = liveService.currentActivity,
               currentActivity.attributes.trainNumber == newTrain.trainId {

                print("🔍 Checking Live Activity auto-end for train \(newTrain.trainId)")

                if liveService.shouldEndActivity(train: newTrain, activity: currentActivity) {
                    print("🏁 Auto-ending Live Activity from TrainDetailsView refresh")

                    Task {
                        await liveService.endCurrentActivity()
                    }
                } else {
                    print("✅ Live Activity continues - journey not complete")
                }
            }

            // Check for boarding status change
            if let currentTrain = train {
                // Check for track assignment
                if currentTrain.track == nil && newTrain.track != nil {
                    triggerTrackAssignedHaptic = true
                }
            }

            // Ensure UI updates properly on main queue
            DispatchQueue.main.async { [weak self] in
                self?.objectWillChange.send()
                self?.train = newTrain
                self?.updateComputedProperties()
            }
        } catch {
            print("❌ TrainDetailsView refresh failed for train \(trainId): \(error)")
            print("❌ Full error details: \(String(describing: error))")
        }
    }
}

// MARK: - Train Follow Toolbar Button
struct TrainFollowToolbarButton: View {
    let train: TrainV2
    let destinationName: String?
    let originCode: String
    let destinationCode: String

    @ObservedObject private var liveActivityService = LiveActivityService.shared
    @ObservedObject private var subscriptionService = SubscriptionService.shared
    @State private var isStarting = false
    @State private var showingPaywall = false

    private var isTrackingThisTrain: Bool {
        liveActivityService.currentActivity?.attributes.trainNumber == train.trainId
    }

    var body: some View {
        Button {
            handleTap()
        } label: {
            Image(systemName: isTrackingThisTrain ? "antenna.radiowaves.left.and.right.circle.fill" : "antenna.radiowaves.left.and.right")
                .font(.body)
                .foregroundColor(isTrackingThisTrain ? .orange : .white)
        }
        .buttonStyle(.plain)
        .disabled(isStarting)
        .opacity(isStarting ? 0.5 : 1.0)
        .sheet(isPresented: $showingPaywall) {
            PaywallView(context: .liveActivities)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
    }

    private func handleTap() {
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()

        // If already tracking, allow stopping regardless of subscription status
        if isTrackingThisTrain {
            Task {
                await liveActivityService.endCurrentActivity()
            }
            return
        }

        // Check subscription status before starting Live Activity
        guard subscriptionService.isPro else {
            showingPaywall = true
            return
        }

        isStarting = true
        Task {
            try? await Task.sleep(for: .milliseconds(50))
            do {
                try await liveActivityService.startTrackingTrain(
                    train,
                    from: originCode,
                    to: destinationCode,
                    origin: Stations.stationName(forCode: originCode) ?? originCode,
                    destination: destinationName ?? ""
                )
            } catch {
                print("Failed to start Live Activity: \(error)")
                await MainActor.run {
                    UINotificationFeedbackGenerator().notificationOccurred(.error)
                }
            }
            await MainActor.run {
                isStarting = false
            }
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
                RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.xs)
                    .fill(Color.gray.opacity(0.3))
                    .frame(height: 8)

                // Progress track
                RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.xs)
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

// Note: Consolidated data functionality is now built into TrainV2 model

// Note: Position tracking is now available through TrainV2.trainPosition


// MARK: - Segmented Track Prediction View
struct SegmentedTrackPredictionView: View {
    let train: TrainV2
    let isDepartingFromNYPenn: Bool
    @State private var adjustedPredictions: PredictionData?
    @State private var isLoadingPredictions = true
    @State private var showWaitingLink = false
    
    private var predictionSegments: [TrackPredictionSegment] {
        print("🔍 [TrackPredictionView] Computing prediction segments")
        guard let predictionData = adjustedPredictions else {
            print("❌ [TrackPredictionView] No adjustedPredictions data")
            return []
        }

        guard let trackProbabilities = predictionData.trackProbabilities else {
            print("❌ [TrackPredictionView] No trackProbabilities in prediction data")
            return []
        }
	
        print("✅ [TrackPredictionView] Have \(trackProbabilities.count) track probabilities")

        let platformProbabilities = PredictionData.groupTracksByPlatform(trackProbabilities)
        print("   Grouped into \(platformProbabilities.count) platforms")

        let sortedPlatforms = platformProbabilities.sorted { first, second in
            let firstNum = extractPlatformNumber(from: first.key)
            let secondNum = extractPlatformNumber(from: second.key)
            return firstNum < secondNum
        }

        let segments = createSegments(from: sortedPlatforms)
        print("   Created \(segments.count) segments")
        return segments
    }
    
    private var hasOnlyLowConfidencePredictions: Bool {
        !predictionSegments.isEmpty && predictionSegments.allSatisfy { $0.probability < 0.17 }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                Image(systemName: "tram.circle.fill")
                    .foregroundColor(.black)
                    .font(.title2)
                
                Text("Track Predictions")
                    .font(.headline)
                    .foregroundColor(.black)
                
                Spacer()
            }
            
            if isLoadingPredictions {
                ProgressView()
                    .frame(height: 64)
            } else if hasOnlyLowConfidencePredictions {
                Text("No clear favorite")
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(Color(white: 0.6))
                    .frame(height: 64)
                    .frame(maxWidth: .infinity)
            } else if !predictionSegments.isEmpty {
                VStack(spacing: 8) {
                    // Labels for segments that need them above the bar
                    if hasSegmentsWithTopLabels {
                        topLabelsView
                    }
                    
                    // Main segmented bar
                    segmentedBarView
                        .frame(height: 64)
                    
                    // Percentages below the bar
                    bottomLabelsView
                }
                .padding(.top, 4)
            } else {
                Text("No prediction data available")
                    .font(.caption)
                    .foregroundColor(Color(white: 0.55))
                    .italic()
            }
            
            // Penn Station waiting guide link for NY departures
            if isDepartingFromNYPenn && showWaitingLink {
                PennStationWaitingLink(isAmtrak: train.trainId.hasPrefix("A"))
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .padding()
        .background(Color.orange.opacity(0.05))
        .cornerRadius(TrackRatTheme.CornerRadius.md)
        .overlay(
            RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.md)
                .stroke(Color.orange.opacity(0.3), lineWidth: 1)
        )
        .task {
            await loadAdjustedPredictions()
        }
    }
    
    private func loadAdjustedPredictions() async {
        print("🔄 [TrainDetailsView] Loading predictions for train \(train.trainId)")
        print("   - Origin: \(train.originStationCode ?? "nil")")
        print("   - Is NY Penn: \(isDepartingFromNYPenn)")

        isLoadingPredictions = true
        adjustedPredictions = await StaticTrackDistributionService.shared.getAdjustedPredictionData(for: train)
        isLoadingPredictions = false

        if let predictions = adjustedPredictions {
            let trackCount = predictions.trackProbabilities?.count ?? 0
            print("✅ [TrainDetailsView] Got predictions with \(trackCount) tracks")
        } else {
            print("⚠️ [TrainDetailsView] No predictions returned")
        }

        // Show the waiting link with animation after predictions load
        if isDepartingFromNYPenn {
            withAnimation(.easeInOut(duration: 0.3).delay(0.2)) {
                showWaitingLink = true
            }
        }
    }
    
    private func extractPlatformNumber(from platformName: String) -> Int {
        // Extract first number from platform names like "1 & 2", "3 & 4", "17"
        let components = platformName.components(separatedBy: CharacterSet.decimalDigits.inverted)
        let firstNumber = components.first { !$0.isEmpty }
        return Int(firstNumber ?? "999") ?? 999
    }
    
    private var segmentedBarView: some View {
        GeometryReader { geometry in
            HStack(spacing: 0) {
                ForEach(predictionSegments) { segment in
                    segmentView(segment: segment, totalWidth: geometry.size.width)
                }
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.sm))
        .overlay(
            RoundedRectangle(cornerRadius: TrackRatTheme.CornerRadius.sm)
                .stroke(Color.black, lineWidth: 1)
        )
    }
    
    private func segmentView(segment: TrackPredictionSegment, totalWidth: CGFloat) -> some View {
        let segmentWidth = totalWidth * segment.probability

        return Rectangle()
            .fill(segment.color)
            .frame(width: segmentWidth)
            .overlay(
                segment.labelPosition == .inside ?
                Text(segment.displayText)
                    .font(segment.labelFont)
                    .fontWeight(.medium)
                    .foregroundColor(.black)
                    .lineLimit(3)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.vertical, 8)
                    .opacity(1)
                : nil
            )
            .overlay(
                Rectangle()
                    .stroke(Color.black, lineWidth: 1)
            )
    }
    
    private var hasSegmentsWithTopLabels: Bool {
        predictionSegments.contains { $0.labelPosition == .above }
    }
    
    private var topLabelsView: some View {
        GeometryReader { geometry in
            HStack(spacing: 0) {
                ForEach(predictionSegments) { segment in
                    let segmentWidth = geometry.size.width * segment.probability
                    
                    VStack(spacing: 2) {
                        if segment.labelPosition == .above {
                            VStack(spacing: 1) {
                                Text(segment.topLabelText)
                                    .font(.caption2)
                                    .fontWeight(.medium)
                                    .foregroundColor(TrackRatTheme.Colors.onSurface)
                                
                                Rectangle()
                                    .fill(TrackRatTheme.Colors.surface.opacity(0.3))
                                    .frame(width: min(segmentWidth * 0.8, 20), height: 1)
                            }
                            .opacity(1)
                        }
                    }
                    .frame(width: segmentWidth)
                }
            }
        }
        .frame(height: 18)
    }
    
    private var bottomLabelsView: some View {
        GeometryReader { geometry in
            HStack(spacing: 0) {
                ForEach(predictionSegments) { segment in
                    let segmentWidth = geometry.size.width * segment.probability
                    
                    VStack {
                        if segment.probability >= 0.15 {
                            Text("\(Int(segment.probability * 100))%")
                                .font(.caption2)
                                .fontWeight(.medium)
                                .foregroundColor(.black)
                        }
                    }
                    .frame(width: segmentWidth)
                }
            }
        }
        .frame(height: 16)
    }
    
    private func createSegments(from platformProbabilities: [(key: String, value: Double)]) -> [TrackPredictionSegment] {
        var segments: [TrackPredictionSegment] = []
        
        for (index, platform) in platformProbabilities.enumerated() {
            let segment = TrackPredictionSegment(
                id: platform.key,
                platformName: platform.key,
                probability: platform.value,
                rank: index + 1
            )
            
            segments.append(segment)
        }
        
        return segments
    }
}

// MARK: - Track Prediction Segment Model
struct TrackPredictionSegment: Identifiable, Equatable {
    let id: String
    let platformName: String
    let probability: Double
    let rank: Int
    let isOthersGroup: Bool
    let detailText: String
    
    init(id: String, platformName: String, probability: Double, rank: Int, isOthersGroup: Bool = false, detailText: String = "") {
        self.id = id
        self.platformName = platformName
        self.probability = probability
        self.rank = rank
        self.isOthersGroup = isOthersGroup
        self.detailText = detailText
    }
    
    var displayText: String {
        if isOthersGroup {
            return "Others"
        }
        // Show "Tracks" prefix for all segments >=15%
        return "Tracks\n\(platformName)"
    }
    
    var topLabelText: String {
        if isOthersGroup {
            return "Others"
        }
        return "Tracks \(platformName)"
    }
    
    var color: Color {
        if isOthersGroup {
            return Color(white: 0.55).opacity(0.6)
        }

        // All segments now use same opacity
        return Color(red: 1.0, green: 0.584, blue: 0.0).opacity(0.3)
    }
    
    var labelPosition: TrackLabelPosition {
        if isOthersGroup {
            return .inside
        }
        
        // Show labels for segments with >= 15% probability
        if probability >= 0.15 {
            return .inside
        } else {
            return .none
        }
    }
    
    var labelFont: Font {
        if isOthersGroup {
            return .caption2
        }
        // Use size 10 font (between size 9 and caption2) for all segments >= 15%
        return .system(size: 10, weight: .medium)
    }
}

enum TrackLabelPosition {
    case inside
    case above
    case none
}

// MARK: - Penn Station Waiting Link
struct PennStationWaitingLink: View {
    let isAmtrak: Bool
    @ObservedObject private var subscriptionService = SubscriptionService.shared
    @State private var showingGuide = false
    @State private var showingPaywall = false

    var body: some View {
        HStack {
            Spacer()
            Button(action: {
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                if subscriptionService.isPro {
                    showingGuide = true
                } else {
                    showingPaywall = true
                }
            }) {
                HStack(spacing: 3) {
                    if !subscriptionService.isPro {
                        Image(systemName: "lock.fill")
                            .font(.system(size: 10))
                    }
                    Text("where should I wait?")
                        .font(.system(size: 12))
                        .fontWeight(.medium)
                }
                .foregroundColor(.white)
                .padding(.vertical, 6)
                .padding(.horizontal, 10)
                .background(
                    RoundedRectangle(cornerRadius: 20)
                        .fill(Color.black.opacity(0.9))
                )
            }
            .buttonStyle(.plain)
            Spacer()
        }
        .padding(.top, 8)
        .sheet(isPresented: $showingGuide) {
            PennStationGuideView(isAmtrak: isAmtrak)
        }
        .sheet(isPresented: $showingPaywall) {
            PaywallView(context: .pennStationGuide)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
    }
}

// MARK: - Prediction Explanation Sheet
struct PredictionExplanationSheet: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Content
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        // Header with emoji
                        HStack {
                            Spacer()
                            VStack(spacing: 8) {
                                Text("🐀✨")
                                    .font(.system(size: 56))
                                Text("Arrival Time Forecasts")
                                    .font(.title2)
                                    .fontWeight(.semibold)
                                    .foregroundColor(.white)
                            }
                            Spacer()
                        }
                        .padding(.top, 24)

                        // Explanation
                        VStack(alignment: .leading, spacing: 16) {
                            Text("What is this?")
                                .font(.headline)
                                .foregroundColor(.white)

                            Text("TrackRat looks at the progress of trains immediately ahead of you to predict your arrival times at each station on your journey.")
                                .font(.body)
                                .foregroundColor(.white.opacity(0.7))
                                .fixedSize(horizontal: false, vertical: true)

                            Text("This is independent from, but used in combination with, the Predicted Delays of the NJ Transit and Amtrak and only shown when delays are expected.")
                                .font(.body)
                                .foregroundColor(.white.opacity(0.7))
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        .padding(.horizontal, 20)
                        .padding(.bottom, 20)
                    }
                }
            }
            .background(.ultraThinMaterial)
        }
        .presentationDetents([.medium])
        .presentationDragIndicator(.visible)
        .presentationBackground(.ultraThinMaterial)
        .preferredColorScheme(.dark)
    }
}

#Preview {
    NavigationStack {
        TrainDetailsView(trainId: 1)
            .environmentObject(AppState())
    }
}
