import SwiftUI
import ActivityKit

@available(iOS 16.1, *)
struct ActiveTripsSection: View {
    @StateObject private var liveActivityService = LiveActivityService.shared
    @EnvironmentObject private var appState: AppState
    @State private var refreshTimer = Timer.publish(every: 5, on: .main, in: .common).autoconnect()
    
    var body: some View {
        Group {
            if liveActivityService.isActivityActive && liveActivityService.currentActivity != nil {
                activeTripsContent
            }
        }
        .onReceive(refreshTimer) { _ in
            // Refresh the Live Activity data every 5 seconds
            Task {
                await liveActivityService.refreshCurrentActivity()
            }
        }
    }
    
    @ViewBuilder
    private var activeTripsContent: some View {
        if let activity = liveActivityService.currentActivity {
            VStack(alignment: .leading, spacing: 16) {
                sectionHeader
                tripButton(for: activity)
            }
        }
    }
    
    private var sectionHeader: some View {
        Text("ACTIVE TRIPS")
            .font(.subheadline)
            .fontWeight(.semibold)
            .foregroundColor(.white.opacity(0.7))
            .padding(.horizontal)
    }
    
    private func tripButton(for activity: any TRActivityProtocol) -> some View {
        Button {
            navigateToTrainDetails(activity: activity)
        } label: {
            tripButtonContent(for: activity)
        }
        .buttonStyle(.plain)
    }
    
    @ViewBuilder
    private func tripButtonContent(for activity: any TRActivityProtocol) -> some View {
        VStack(spacing: 12) {
            headerRow(for: activity)
            routeRow(for: activity)
            
            // Use new journey status view if train data is available
            if let trainData = getTrainDataFromActivity(activity) {
                JourneyStatusView(
                    train: trainData, 
                    displayMode: JourneyDisplayMode.compact,
                    showTrainHeader: false
                )
            } else {
                // Fallback to legacy display
                statusAndTrackRow(for: activity)
                progressBar(for: activity)
                bottomInfoRow(for: activity)
            }
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(.white.opacity(0.2))
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(.white.opacity(0.3), lineWidth: 1)
                )
        )
        .padding(.horizontal)
    }
    
    private func headerRow(for activity: any TRActivityProtocol) -> some View {
        HStack {
            HStack(spacing: 6) {
                Text("🚂")
                    .font(.title2)
                Text("Train \(activity.trainAttributes?.trainNumber ?? "Unknown")")
                    .font(.headline.bold())
                    .foregroundColor(.white)
            }
            
            Spacer()
            
            HStack(spacing: 4) {
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.6))
            }
        }
    }
    
    private func routeRow(for activity: any TRActivityProtocol) -> some View {
        HStack {
            Text(activity.trainAttributes?.routeDescription ?? "Unknown Route")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.8))
            Spacer()
        }
    }
    
    private func statusAndTrackRow(for activity: any TRActivityProtocol) -> some View {
        HStack {
            // Status
            HStack(spacing: 4) {
                Circle()
                    .fill(statusColor(activity.trainContentState?.status ?? .unknown))
                    .frame(width: 8, height: 8)
                Text(activity.trainContentState?.status.displayText ?? "Unknown")
                    .font(.subheadline.bold())
                    .foregroundColor(.white)
            }
            
            Spacer()
            
            // Track
            if let track = activity.trainContentState?.track {
                HStack(spacing: 4) {
                    Text("Track")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.7))
                    Text(track)
                        .font(.subheadline.bold())
                        .foregroundColor(.white)
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 2)
                .background(
                    RoundedRectangle(cornerRadius: 6)
                        .fill(.white.opacity(0.2))
                )
            }
        }
    }
    
    private func progressBar(for activity: any TRActivityProtocol) -> some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 3)
                    .fill(.white.opacity(0.3))
                    .frame(height: 6)
                
                RoundedRectangle(cornerRadius: 3)
                    .fill(.white.opacity(0.9))
                    .frame(width: geometry.size.width * (activity.trainContentState?.journeyProgress ?? 0.0), height: 6)
            }
        }
        .frame(height: 6)
    }
    
    private func bottomInfoRow(for activity: any TRActivityProtocol) -> some View {
        HStack {
            if let nextStop = activity.trainContentState?.nextStop {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Next Stop")
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.7))
                    Text(Stations.displayName(for: nextStop.stationName))
                        .font(.caption.bold())
                        .foregroundColor(.white)
                        .lineLimit(1)
                }
            }
            
            Spacer()
            
            
            VStack(alignment: .trailing, spacing: 2) {
                Text("Updated")
                    .font(.caption2)
                    .foregroundColor(.white.opacity(0.7))
                Text(formatTimeAgo(activity.trainContentState?.lastUpdated ?? Date()))
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.8))
            }
        }
    }
    
    private func navigateToTrainDetails(activity: any TRActivityProtocol) {
        // Use the train number and origin station code for navigation
        guard let attributes = activity.trainAttributes else { return }
        let trainNumber = attributes.trainNumber
        let fromStation = attributes.originStationCode
        appState.navigationPath.append(NavigationDestination.trainDetailsFlexible(trainNumber: trainNumber, fromStation: fromStation))
    }
    
    private func statusColor(_ status: TrainStatus) -> Color {
        switch status {
        case .onTime: return .green
        case .delayed: return .red
        case .boarding: return .orange
        case .departed: return .blue
        default: return .white
        }
    }
    
    private func formatTimeAgo(_ date: Date) -> String {
        let now = Date()
        let timeInterval = now.timeIntervalSince(date)
        
        if timeInterval < 60 {
            return "in the past minute"
        } else if timeInterval < 120 {
            return "1 minute ago"
        } else if timeInterval < 3600 {
            let minutes = Int(timeInterval / 60)
            return "\(minutes) minutes ago"
        } else {
            let formatter = DateFormatter()
            formatter.timeStyle = .short
            return formatter.string(from: date)
        }
    }
    
    private func formatTime(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        return formatter.string(from: date)
    }
    
    /// Extract or create train data from Live Activity for the new journey status view
    private func getTrainDataFromActivity(_ activity: any TRActivityProtocol) -> Train? {
        guard let attributes = activity.trainAttributes else { return nil }
        guard let contentState = activity.trainContentState else { return nil }
        
        // Create a minimal train object from Live Activity data
        // This will be used for the new journey status display
        let train = Train(
            id: Int(attributes.trainId) ?? 0,
            trainId: attributes.trainNumber,
            line: "Live Activity", // We don't have line info in Live Activity
            destination: attributes.destination,
            departureTime: Date(), // We don't have departure time in Live Activity
            track: contentState.track,
            status: contentState.status,
            delayMinutes: contentState.delayMinutes,
            stops: nil, // Live Activity doesn't store full stops data
            predictionData: nil,
            originStationCode: attributes.originStationCode,
            dataSource: nil,
            statusV2: createStatusV2FromActivity(contentState),
            progress: createProgressFromActivity(contentState, attributes)
        )
        
        return train
    }
    
    /// Create StatusV2-like data from Live Activity content with human-friendly status
    private func createStatusV2FromActivity(_ contentState: TrainActivityAttributes.ContentState) -> StatusV2? {
        let currentStatus: String
        let location: String
        
        switch contentState.currentLocation {
        case .notDeparted:
            currentStatus = "SCHEDULED"
            location = "at departure station"
        case .boarding(let station):
            currentStatus = humanFriendlyStatus("BOARDING", track: contentState.track)
            location = "at \(station)"
        case .departed(let from, _):
            currentStatus = "EN_ROUTE"
            location = "departed from \(from)"
        case .approaching(let station, _):
            currentStatus = "EN_ROUTE" 
            location = "approaching \(station)"
        case .enRoute(let from, let to):
            currentStatus = "EN_ROUTE"
            location = "between \(from) and \(to)"
        case .atStation(let station):
            currentStatus = humanFriendlyStatus("BOARDING", track: contentState.track)
            location = "at \(station)"
        case .arrived:
            currentStatus = "ARRIVED"
            location = "at destination"
        }
        
        return StatusV2(
            current: currentStatus,
            location: location,
            updatedAt: contentState.lastUpdated,
            confidence: "medium", // We don't have confidence in Live Activity
            source: "live_activity"
        )
    }
    
    /// Convert technical status to human-friendly display text
    private func humanFriendlyStatus(_ status: String, track: String? = nil) -> String {
        switch status.uppercased() {
        case "EN_ROUTE":
            return "En Route"
        case "BOARDING":
            if let track = track {
                return "Boarding on Track \(track)"
            } else {
                return "Boarding"
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
    
    /// Create Progress-like data from Live Activity content
    private func createProgressFromActivity(_ contentState: TrainActivityAttributes.ContentState, _ attributes: TrainActivityAttributes) -> TrainProgress? {
        // Extract basic progress information from Live Activity
        let journeyPercent = Int(contentState.journeyProgress * 100)
        
        // Create next arrival if we have next stop info
        var nextArrival: NextArrival? = nil
        if let nextStop = contentState.nextStop {
            let minutesAway = max(0, Int(nextStop.estimatedArrival.timeIntervalSince(Date()) / 60))
            nextArrival = NextArrival(
                stationCode: Stations.getStationCode(nextStop.stationName) ?? nextStop.stationName,
                scheduledTime: nextStop.scheduledArrival ?? nextStop.estimatedArrival,
                estimatedTime: nextStop.estimatedArrival,
                minutesAway: minutesAway
            )
        }
        
        // Create last departed info if applicable
        var lastDeparted: DepartedStation? = nil
        if case .departed(let from, _) = contentState.currentLocation {
            lastDeparted = DepartedStation(
                stationCode: Stations.getStationCode(from) ?? from,
                departedAt: Date(), // We don't have exact departure time
                delayMinutes: contentState.delayMinutes ?? 0
            )
        }
        
        return TrainProgress(
            lastDeparted: lastDeparted,
            nextArrival: nextArrival,
            journeyPercent: journeyPercent,
            stopsCompleted: 0, // We don't have this in Live Activity
            totalStops: 0      // We don't have this in Live Activity
        )
    }
    
}