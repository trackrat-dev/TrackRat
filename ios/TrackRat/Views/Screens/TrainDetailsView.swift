import SwiftUI
import ActivityKit

struct TrainDetailsView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @StateObject private var viewModel: TrainDetailsViewModel
    // PERFORMANCE: Track visibility to prevent polling when view is not visible
    @State private var isViewVisible = false

    let trainId: Int  // Keep for backwards compatibility
    let isSheet: Bool

    /// Mutable subscription for inline configuration (nil when opened without alert context).
    @State private var alertSubscription: RouteAlertSubscription?
    private let onAlertSave: ((RouteAlertSubscription) -> Void)?

    // Legacy initializer for database ID
    init(trainId: Int, isSheet: Bool = false) {
        self.trainId = trainId
        self.isSheet = isSheet
        let VModel = TrainDetailsViewModel(trainId: trainId)
        self._viewModel = StateObject(wrappedValue: VModel)
        self._alertSubscription = State(initialValue: nil)
        self.onAlertSave = nil
    }

    // New initializer for train number
    init(trainNumber: String, fromStation: String? = nil, journeyDate: Date? = nil, dataSource: String? = nil, isSheet: Bool = false) {
        self.trainId = 0  // Not used for train number based initialization
        self.isSheet = isSheet
        let VModel = TrainDetailsViewModel(
            databaseId: nil,
            trainNumber: trainNumber,
            fromStationCode: fromStation,
            journeyDate: journeyDate,
            dataSource: dataSource
        )
        self._viewModel = StateObject(wrappedValue: VModel)
        self._alertSubscription = State(initialValue: nil)
        self.onAlertSave = nil
    }

    // Initializer with alert subscription for inline configuration
    init(trainNumber: String, dataSource: String, isSheet: Bool = false, subscription: RouteAlertSubscription, onSave: @escaping (RouteAlertSubscription) -> Void) {
        self.trainId = 0
        self.isSheet = isSheet
        let VModel = TrainDetailsViewModel(
            databaseId: nil,
            trainNumber: trainNumber,
            fromStationCode: nil,
            journeyDate: nil,
            dataSource: dataSource
        )
        self._viewModel = StateObject(wrappedValue: VModel)
        self._alertSubscription = State(initialValue: subscription)
        self.onAlertSave = onSave
    }

    private var trainNavigationTitle: String {
        guard let train = viewModel.train else { return "Loading..." }
        return train.displayDestination
    }

    @ViewBuilder
    private var trainTitleAccessory: some View {
        if let train = viewModel.train, train.dataSource == "SUBWAY" {
            SubwayLineChips(
                lines: [SubwayLines.displayBullet(forLineCode: train.line.code)],
                size: 22
            )
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            // Fixed header - replaces system navigation bar to avoid layout shift
            TrackRatNavigationHeader(
                // PATH and PATCO trains display destination instead of synthetic train ID
                title: trainNavigationTitle,
                showBackButton: !isSheet,
                showCloseButton: false,
                titleAccessory: { trainTitleAccessory },
                trailingContent: {
                    HStack(alignment: .center, spacing: 12) {
                        if let train = viewModel.train,
                           let originCode = appState.departureStationCode,
                           !originCode.isEmpty {
                            ShareButton(
                                train: train,
                                fromStationCode: appState.departureStationCode,
                                destinationName: appState.selectedDestination
                            )
                        }

                        Button("Close") {
                            if isSheet {
                                dismiss()
                            } else {
                                appState.navigationPath = NavigationPath()
                            }
                        }
                        .font(.body)
                        .fontWeight(.medium)
                        .foregroundColor(.white)
                        .buttonStyle(.plain)
                    }
                }
            )

            // Action buttons row
            if let train = viewModel.train {
                HStack(spacing: 12) {
                    // Route alerts button
                    if let destCode = appState.destinationStationCode,
                       !destCode.isEmpty,
                       let originCode = appState.departureStationCode,
                       !originCode.isEmpty {
                        Button {
                            let ds = train.dataSource
                            let lineId: String? = ds == "SUBWAY" ? nil : RouteTopology.routeContaining(from: originCode, to: destCode, dataSource: ds)?.id
                            appState.pendingRouteStatus = RouteStatusContext(
                                dataSource: ds,
                                lineId: lineId,
                                fromStationCode: originCode,
                                toStationCode: destCode
                            )
                        } label: {
                            HStack(spacing: 6) {
                                Image(systemName: "bell.badge")
                                    .font(.subheadline)
                                Text("Route Alerts")
                                    .font(.subheadline)
                            }
                            .foregroundColor(.white.opacity(0.8))
                            .padding(.horizontal, 14)
                            .padding(.vertical, 8)
                            .background(Capsule().fill(Color.white.opacity(0.12)))
                        }
                        .buttonStyle(.plain)
                    }

                    // Get Updates button (Live Activity)
                    if let originCode = appState.departureStationCode,
                       !originCode.isEmpty {
                        TrackTrainInlineButton(
                            train: train,
                            originCode: originCode,
                            destinationCode: appState.destinationStationCode ?? "",
                            destinationName: appState.selectedDestination,
                            textColor: .white.opacity(0.8),
                            activeLabel: "Stop Updates",
                            inactiveLabel: "Get Updates",
                            font: .subheadline
                        )
                        .padding(.horizontal, 14)
                        .padding(.vertical, 8)
                        .background(Capsule().fill(Color.white.opacity(0.12)))
                    }

                }
                .padding(.horizontal, 16)
                .padding(.bottom, 8)
            }

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
                            // Explain "Train TBD" — scheduled-only NJT/Amtrak trains not yet
                            // seen in the live feed. Self-clears once observationType flips.
                            if train.hasUnconfirmedTrainNumber {
                                ScheduledTrainInfoBanner()
                            }

                            // Train performance summary (similar trains + historical)
                            // Hide after train departs from user's origin station
                            if let originCode = appState.departureStationCode,
                               !train.hasTrainDepartedFromStation(originCode) {
                                TrainStatsSummaryView(
                                    trainId: train.trainId,
                                    fromStation: appState.departureStationCode,
                                    toStation: appState.destinationStationCode,
                                    journeyDate: train.journeyDate,
                                    showDepartureOdds: appState.showDepartureOdds,
                                    onTrainTap: { selectedTrainId in
                                        // Navigate to the selected train's detail view
                                        // Note: dataSource not available from this callback, backend uses two-phase search
                                        appState.navigationPath.append(
                                            NavigationDestination.trainDetailsFlexible(
                                                trainNumber: selectedTrainId,
                                                fromStation: appState.departureStationCode,
                                                journeyDate: nil,
                                                dataSource: nil
                                            )
                                        )
                                    },
                                    prefetchedSummary: viewModel.prefetchedSummary,
                                    prefetchedForecast: viewModel.prefetchedDelayForecast
                                )
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
                                journeyTotalStops: viewModel.journeyTotalStops,
                                isLoadingStops: viewModel.isLoadingStops,
                                prefetchedTrackPrediction: viewModel.prefetchedTrackPrediction
                            )

                            if let _ = alertSubscription {
                                AlertConfigurationSection(subscription: Binding(
                                    get: { alertSubscription! },
                                    set: { alertSubscription = $0 }
                                ))
                            }

                            // Report an issue button
                            FeedbackButton(
                                screen: "train_details",
                                trainId: train.trainId,
                                originCode: appState.departureStationCode,
                                destinationCode: appState.destinationStationCode
                            )
                            .padding(.top, 8)
                        }
                        .padding()
                        // Force view recreation when train identity or status changes
                        .id("\(train.id)-\(train.calculateStatus(fromStationCode: appState.departureStationCode ?? "").rawValue)")
                    }
                } // VStack
            }
        }
        .navigationBarHidden(true)
        .onDisappear {
            if let alertSubscription = alertSubscription {
                onAlertSave?(alertSubscription)
            }
        }
        .task {
            // Check if appState.currentTrain matches this view's train
            // This provides instant display when navigating from the train list
            let existingTrain: TrainV2? = {
                guard let currentTrain = appState.currentTrain else { return nil }
                // Match by trainId (train number)
                if let trainNumber = viewModel.trainNumber,
                   currentTrain.trainId == trainNumber {
                    return currentTrain
                }
                return nil
            }()

            await viewModel.loadTrainDetails(
                fromStationCode: appState.departureStationCode,
                toStationCode: appState.destinationStationCode,
                selectedDestinationName: appState.selectedDestination,
                existingTrain: existingTrain
            )
        }
        .task(id: isViewVisible) {
            // Auto-refresh task that cancels automatically when view disappears
            guard isViewVisible else { return }
            while !Task.isCancelled {
                let interval = viewModel.pollingInterval
                try? await Task.sleep(for: .seconds(interval))
                guard !Task.isCancelled, isViewVisible else { break }

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
        .onChange(of: viewModel.isLoadingStops) { oldValue, newValue in
            // When stops loading completes (true -> false), update appState with full train data
            // This enables instant display when navigating back to this train
            if oldValue == true && newValue == false,
               let train = viewModel.train,
               let stops = train.stops,
               !stops.isEmpty {
                appState.currentTrain = train
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
    }
}

// MARK: - Combined Details Card
struct CombinedDetailsCard: View {
    let train: TrainV2
    let selectedDestination: String?
    let selectedDestinationCode: String?
    @EnvironmentObject private var appState: AppState
    // ViewModel provided properties
    let displayableTrainStops: [StopV2]
    let hasPreviousDisplayStops: Bool
    let hasMoreDisplayStops: Bool
    let journeyProgressPercentage: Int
    let journeyStopsCompleted: Int
    let journeyTotalStops: Int
    let isLoadingStops: Bool
    let prefetchedTrackPrediction: PredictionData?

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
        
    // Check if predictions should be shown for the entire journey.
    // Shows predictions when any stop in the journey has a meaningful predicted delay.
    private var shouldShowJourneyPredictions: Bool {
        return displayableTrainStops.contains { stop in
            guard let predictedArrival = stop.predictedArrival,
                  let bestKnown = stop.bestKnownArrival,
                  let samples = stop.predictedArrivalSamples,
                  samples > 0,
                  !stop.hasDepartedStation else {
                return false
            }
            return predictedArrival.timeIntervalSince(bestKnown) > 240
        }
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
        // Subway has no track assignments and no meaningful boarding window
        if train.dataSource == "SUBWAY" {
            return false
        }

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
                        Text("CANCELLED")
                            .font(.largeTitle)
                            .fontWeight(.bold)
                            .foregroundColor(.white)
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
                
                // Track predictions section
                if shouldShowPredictions {
                    SegmentedTrackPredictionView(
                        train: train,
                        isDepartingFromNYPenn: appState.departureStationCode == "NY",
                        prefetchedPredictions: prefetchedTrackPrediction
                    )
                    .allowsHitTesting(true)  // Ensure predictions card is interactive
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
                            Stations.areEquivalentStations(stop.stationCode, appState.departureStationCode!)
                        StopRowV2(
                            stop: stop,
                            isDestination: selectedDestinationCode != nil &&
                                         Stations.areEquivalentStations(stop.stationCode, selectedDestinationCode!),
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

                } else if isLoadingStops {
                    // Show loading indicator while fetching stops data
                    HStack(spacing: 8) {
                        ProgressView()
                            .scaleEffect(0.8)
                        Text("Loading stops...")
                            .foregroundColor(.black.opacity(0.6))
                            .italic()
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 24)
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
    }
}

// Note: StatusV2 functionality is now integrated directly into TrainV2 model

// MARK: - Scheduled Train Info Banner
struct ScheduledTrainInfoBanner: View {
    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "info.circle")
                .foregroundColor(.white.opacity(0.6))
            Text("This train is on the published schedule but hasn't appeared in the live feed yet. The train number will be confirmed once it becomes active.")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.8))
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.white.opacity(0.08))
        .cornerRadius(8)
    }
}

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

    /// Subway bullets for every line serving this stop's station complex.
    /// Empty for non-subway trains.
    private var stationLineBullets: [String] {
        guard train.dataSource == "SUBWAY" else { return [] }
        return SubwayLines.lines(forStationCode: stop.stationCode)
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
                HStack(spacing: 6) {
                    StationNameWithBadges(
                        name: Stations.displayName(for: stop.stationName),
                        subwayLines: stationLineBullets,
                        font: .subheadline,
                        foregroundColor: textColor,
                        chipSize: 14,
                        includeSystemChips: false
                    )

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
               let bestKnown = stop.bestKnownArrival,
               let samples = stop.predictedArrivalSamples,
               samples > 0,
               !stop.hasDepartedStation,
               predictedArrival.timeIntervalSince(bestKnown) > 240,
               shouldShowJourneyPredictions {
                HStack(spacing: 4) {
                    Text("🐀✨")
                        .font(.callout)
                    Text(DateFormatter.easternTimeShort.string(from: predictedArrival))
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(predictionDelayColor(predicted: predictedArrival, scheduled: stop.bestKnownArrival))
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
    @Published var isLoadingStops = false  // True when we have partial train data awaiting stops
    @Published var error: String?
    @Published var triggerTrackAssignedHaptic = false

    // Prefetched secondary data (loaded in parallel with main train fetch)
    @Published var prefetchedSummary: OperationsSummaryResponse?
    @Published var prefetchedDelayForecast: DelayForecastResponse?
    @Published var prefetchedTrackPrediction: PredictionData?

    // Flexible initialization parameters
    private let databaseId: Int?
    let trainNumber: String?  // Made public for transaction tracking
    private let preferredStationCode: String?
    private let journeyDate: Date?
    private let dataSource: String?  // Data source for disambiguation (NJT, AMTRAK, PATH, PATCO)

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
        self.dataSource = nil
    }

    // New flexible initializer
    init(databaseId: Int? = nil, trainNumber: String? = nil, fromStationCode: String? = nil, journeyDate: Date? = nil, dataSource: String? = nil) {
        self.databaseId = databaseId
        self.trainNumber = trainNumber
        self.preferredStationCode = fromStationCode
        self.journeyDate = journeyDate
        self.dataSource = dataSource
    }
    
    // Computed property for backwards compatibility
    var trainId: Int {
        return databaseId ?? 0
    }

    /// Adaptive polling interval based on time-to-departure.
    /// Polls faster when track assignment is most likely (close to departure).
    var pollingInterval: Double {
        guard let departureTime = train?.departure.updatedTime ?? train?.departure.scheduledTime else {
            return 30
        }
        let minutesToDeparture = departureTime.timeIntervalSinceNow / 60
        if minutesToDeparture <= 0 {
            // Already departed — track info is static
            return 30
        } else if minutesToDeparture <= 5 {
            // Active boarding window
            return 10
        } else if minutesToDeparture <= 15 {
            // Track assignment likely imminent
            return 15
        } else {
            return 30
        }
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
            Stations.areEquivalentStations(stop.stationCode, originStationCode)
        }

        let destinationIndex = stops.firstIndex { stop in
            Stations.areEquivalentStations(stop.stationCode, destinationStationCode)
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
            Stations.areEquivalentStations(stop.stationCode, originStationCode)
        }

        // Update hasPreviousDisplayStops
        hasPreviousDisplayStops = originIndex != nil && originIndex! > 0

        // Find destination index by station CODE
        let destinationIndex = stops.firstIndex { stop in
            Stations.areEquivalentStations(stop.stationCode, destinationStationCode)
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
    
    func loadTrainDetails(fromStationCode: String? = nil, toStationCode: String? = nil, selectedDestinationName: String? = nil, existingTrain: TrainV2? = nil) async {
        error = nil

        // Store current origin and destination for filtering
        self.currentOriginStationCode = fromStationCode
        self.currentDestinationStationCode = toStationCode
        self.currentDestinationName = selectedDestinationName

        // Get the train identifier for cache operations
        let trainIdentifier = trainNumber ?? databaseId.map(String.init) ?? ""
        let effectiveDate = journeyDate ?? Date()

        // PRIORITY 1: Render any non-expired cache instantly, reconcile in background.
        // The 5-minute isExpired ceiling in TrainCacheService bounds staleness; the
        // background refresh corrects any drift. Critical for Live Activity taps: the
        // Activity's ContentState has progress info but no stops array, so the cache
        // (written by LiveActivityService.fetchAndUpdateTrain) is the only instant
        // source of departed-stops state.
        if !trainIdentifier.isEmpty,
           let cached = cacheService.getCachedTrain(trainNumber: trainIdentifier, date: effectiveDate) {
            print("📦 Loading from cache (\(cached.ageSeconds)s old) - instant display")
            train = cached.train
            updateComputedProperties()
            await refreshTrainDetailsInBackground(fromStationCode: fromStationCode, toStationCode: toStationCode, selectedDestinationName: selectedDestinationName)
            return
        }

        // PRIORITY 2: Use existingTrain from appState for instant header display (first visit)
        if let existingTrain = existingTrain {
            let hasStops = existingTrain.stops != nil && !existingTrain.stops!.isEmpty
            print("⚡ Using existing train from appState - instant display (hasStops: \(hasStops))")
            train = existingTrain
            updateComputedProperties()

            // If train doesn't have stops, show loading indicator for stops section
            if !hasStops {
                isLoadingStops = true
            }

            // Only cache if train has stops data (don't overwrite good cache with partial data)
            if !trainIdentifier.isEmpty && hasStops {
                cacheService.cacheTrain(existingTrain, trainNumber: trainIdentifier, date: effectiveDate)
            }

            // Background refresh to get full data (including stops if missing)
            await refreshTrainDetailsInBackground(fromStationCode: fromStationCode, toStationCode: toStationCode, selectedDestinationName: selectedDestinationName)
            return
        }

        // PRIORITY 3: No cached data and no existing train - show loading indicator and fetch from network
        print("🌐 No cache available - fetching from network")
        isLoading = true

        // Start secondary data fetch in parallel — fire and forget since
        // child views observe @Published properties and update reactively
        Task {
            await self.prefetchSecondaryData(
                trainId: trainNumber ?? "",
                fromStation: fromStationCode,
                toStation: toStationCode,
                journeyDate: journeyDate
            )
        }

        do {
            // Use the flexible API method with dataSource for disambiguation
            let fetchedTrain = try await apiService.fetchTrainDetailsFlexible(
                id: databaseId.map(String.init),
                trainId: trainNumber,
                fromStationCode: fromStationCode ?? preferredStationCode,
                date: journeyDate,
                dataSource: dataSource
            )

            train = fetchedTrain

            // Cache the newly fetched train
            if !trainIdentifier.isEmpty {
                cacheService.cacheTrain(fetchedTrain, trainNumber: trainIdentifier, date: effectiveDate)
            }

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

    /// Fetches fresh data in background without showing loading indicator
    private func refreshTrainDetailsInBackground(fromStationCode: String? = nil, toStationCode: String? = nil, selectedDestinationName: String? = nil) async {
        let trainIdentifier = trainNumber ?? databaseId.map(String.init) ?? "unknown"
        let effectiveDate = journeyDate ?? Date()

        defer {
            // Always clear stops loading state when background refresh completes
            isLoadingStops = false
        }

        do {
            print("🔄 Background refresh for train \(trainIdentifier)")

            let newTrain = try await apiService.fetchTrainDetailsFlexible(
                id: databaseId.map(String.init),
                trainId: trainNumber,
                fromStationCode: fromStationCode ?? preferredStationCode,
                date: journeyDate,
                dataSource: dataSource
            )

            // Cache the fresh data
            if trainIdentifier != "unknown" {
                cacheService.cacheTrain(newTrain, trainNumber: trainIdentifier, date: effectiveDate)
            }

            print("✅ Background refresh successful - updating UI")

            // Check for track assignment (fire haptic on prediction→actual transition)
            if let currentTrain = train,
               currentTrain.track == nil && newTrain.track != nil {
                triggerTrackAssignedHaptic = true
            }

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

        let trainIdentifier = trainNumber ?? databaseId.map(String.init) ?? "unknown"
        let effectiveDate = journeyDate ?? Date()

        // Silent refresh
        do {
            print("🔄 TrainDetailsView refreshing train \(trainIdentifier) from \(fromStationCode ?? preferredStationCode ?? "none")")

            let newTrain = try await apiService.fetchTrainDetailsFlexible(
                id: databaseId.map(String.init),
                trainId: trainNumber,
                fromStationCode: fromStationCode ?? preferredStationCode,
                date: journeyDate,
                dataSource: dataSource
            )

            print("✅ TrainDetailsView refresh successful for train \(trainIdentifier)")

            // Cache the fresh data
            if trainIdentifier != "unknown" {
                cacheService.cacheTrain(newTrain, trainNumber: trainIdentifier, date: effectiveDate)
            }

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

    /// Prefetch secondary data (summary, delay forecast, track prediction) in parallel.
    /// Called concurrently with the main train fetch to eliminate the loading waterfall.
    private func prefetchSecondaryData(trainId: String, fromStation: String?, toStation: String?, journeyDate: Date?) async {
        guard !trainId.isEmpty else { return }

        async let summaryResult: OperationsSummaryResponse? = {
            try? await apiService.fetchOperationsSummary(
                scope: .train,
                fromStation: fromStation,
                toStation: toStation,
                trainId: trainId
            )
        }()

        async let forecastResult: DelayForecastResponse? = {
            guard let stationCode = fromStation, let date = journeyDate else { return nil }
            return try? await apiService.getDelayForecast(
                trainId: trainId,
                stationCode: stationCode,
                journeyDate: date
            )
        }()

        async let trackResult: PredictionData? = {
            guard let stationCode = fromStation,
                  StaticTrackDistributionService.supportedStations.contains(stationCode),
                  let date = journeyDate else { return nil }
            do {
                let prediction = try await apiService.getPlatformPrediction(
                    stationCode: stationCode,
                    trainId: trainId,
                    journeyDate: date
                )
                return PredictionData(trackProbabilities: prediction.convertToTrackProbabilities())
            } catch {
                return nil
            }
        }()

        prefetchedSummary = await summaryResult
        prefetchedDelayForecast = await forecastResult
        prefetchedTrackPrediction = await trackResult
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
    let prefetchedPredictions: PredictionData?
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
    
    @ViewBuilder
    var body: some View {
        // Hide entire section when loading complete and no prediction data (404 from API)
        if isLoadingPredictions || adjustedPredictions != nil {
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
                        .frame(maxWidth: .infinity)
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
                }

                // Penn Station waiting guide link for NY departures
                // Only Amtrak and NJ Transit have authored guide content; other systems
                // (e.g., LIRR) also depart from NY Penn but would be shown the wrong guide.
                if isDepartingFromNYPenn && showWaitingLink &&
                    (train.dataSource == "AMTRAK" || train.dataSource == "NJT") {
                    PennStationWaitingLink(isAmtrak: train.dataSource == "AMTRAK")
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
            .task(id: train.trackPrediction?.primaryPrediction) {
                if let prefetched = prefetchedPredictions, train.track == nil, adjustedPredictions == nil {
                    adjustedPredictions = prefetched
                    isLoadingPredictions = false
                    if isDepartingFromNYPenn {
                        withAnimation(.easeInOut(duration: 0.3).delay(0.2)) {
                            showWaitingLink = true
                        }
                    }
                } else {
                    await loadAdjustedPredictions()
                }
            }
        }
    }

    private func loadAdjustedPredictions() async {
        print("🔄 [TrainDetailsView] Loading predictions for train \(train.trainId)")
        print("   - Origin: \(train.originStationCode ?? "nil" as String)")
        print("   - Is NY Penn: \(isDepartingFromNYPenn)")

        isLoadingPredictions = true

        // Prefer inline prediction from train details response (refreshes every poll)
        if let inline = train.trackPrediction {
            print("⚡ [TrainDetailsView] Using inline track prediction from train details")
            adjustedPredictions = PredictionData(trackProbabilities: inline.platformProbabilities)
        } else {
            // Fallback to separate API call (older backend or track already assigned)
            adjustedPredictions = await StaticTrackDistributionService.shared.getAdjustedPredictionData(for: train)
        }

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
    @State private var showingGuide = false

    var body: some View {
        HStack {
            Spacer()
            Button(action: {
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                showingGuide = true
            }) {
                Text("where should I wait?")
                    .font(TrackRatTheme.Typography.caption)
                    .fontWeight(.medium)
                    .textProtected()
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

                            Text("This is used in combination with any delay predictions from the transit service.")
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
