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
    
    private func tripButton(for activity: Activity<TrainActivityAttributes>) -> some View {
        Button {
            navigateToTrainDetails(activity: activity)
        } label: {
            tripButtonContent(for: activity)
        }
        .buttonStyle(.plain)
    }
    
    @ViewBuilder
    private func tripButtonContent(for activity: Activity<TrainActivityAttributes>) -> some View {
        VStack(spacing: 12) {
            headerRow(for: activity)
            routeRow(for: activity)
            statusAndTrackRow(for: activity)
            progressBar(for: activity)
            bottomInfoRow(for: activity)
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
    
    private func headerRow(for activity: Activity<TrainActivityAttributes>) -> some View {
        HStack {
            HStack(spacing: 6) {
                Text("🚂")
                    .font(.title2)
                Text("Train \(activity.attributes.trainNumber)")
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
    
    private func routeRow(for activity: Activity<TrainActivityAttributes>) -> some View {
        HStack {
            Text(activity.attributes.routeDescription)
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.8))
            Spacer()
        }
    }
    
    private func statusAndTrackRow(for activity: Activity<TrainActivityAttributes>) -> some View {
        HStack {
            // Status
            HStack(spacing: 4) {
                Circle()
                    .fill(statusColor(activity.content.state.status))
                    .frame(width: 8, height: 8)
                Text(activity.content.state.status.displayText)
                    .font(.subheadline.bold())
                    .foregroundColor(statusColor(activity.content.state.status))
            }
            
            Spacer()
            
            // Track
            if let track = activity.content.state.track {
                HStack(spacing: 4) {
                    Text("Track")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.7))
                    Text(track)
                        .font(.subheadline.bold())
                        .foregroundColor(.orange)
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 2)
                .background(
                    RoundedRectangle(cornerRadius: 6)
                        .fill(.orange.opacity(0.2))
                )
            }
        }
    }
    
    private func progressBar(for activity: Activity<TrainActivityAttributes>) -> some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 3)
                    .fill(.white.opacity(0.3))
                    .frame(height: 6)
                
                RoundedRectangle(cornerRadius: 3)
                    .fill(.white.opacity(0.9))
                    .frame(width: geometry.size.width * activity.content.state.journeyProgress, height: 6)
            }
        }
        .frame(height: 6)
    }
    
    private func bottomInfoRow(for activity: Activity<TrainActivityAttributes>) -> some View {
        HStack {
            if let nextStop = activity.content.state.nextStop {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Next Stop")
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.7))
                    Text(nextStop.stationName)
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
                Text(formatTimeAgo(activity.content.state.lastUpdated))
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.8))
            }
        }
    }
    
    private func navigateToTrainDetails(activity: Activity<TrainActivityAttributes>) {
        // Use the train number and origin station code for navigation
        let trainNumber = activity.attributes.trainNumber
        let fromStation = activity.attributes.originStationCode
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
    
}