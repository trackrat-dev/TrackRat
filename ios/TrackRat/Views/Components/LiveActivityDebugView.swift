import SwiftUI
import ActivityKit
import Combine

@available(iOS 16.1, *)
struct LiveActivityDebugView: View {
    @StateObject private var liveActivityService = LiveActivityService.shared
    @EnvironmentObject private var appState: AppState
    @State private var refreshTimer = Timer.publish(every: 5, on: .main, in: .common).autoconnect()
    
    var body: some View {
        if liveActivityService.isActivityActive,
           let activity = liveActivityService.currentActivity {
            
            Button {
                navigateToTrainDetails(activity: activity)
            } label: {
                VStack(spacing: 12) {
                    // Header row with train and route
                    HStack {
                        HStack(spacing: 6) {
                            Text("🚂")
                                .font(.title2)
                            Text("Train \(activity.attributes.trainNumber)")
                                .font(.headline.bold())
                                .foregroundColor(.primary)
                        }
                        
                        Spacer()
                        
                        HStack(spacing: 4) {
                            Text("\(Int(activity.content.state.journeyProgress * 100))%")
                                .font(.subheadline.bold())
                                .foregroundColor(.blue)
                            Image(systemName: "chevron.right")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    
                    // Route
                    HStack {
                        Text(activity.attributes.routeDescription)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                        Spacer()
                    }
                    
                    // Status and Track row
                    HStack {
                        // Status (StatusV2)
                        HStack(spacing: 4) {
                            Circle()
                                .fill(statusV2Color(activity.content.state.statusV2))
                                .frame(width: 8, height: 8)
                            Text(statusV2DisplayText(activity.content.state.statusV2))
                                .font(.subheadline.bold())
                                .foregroundColor(statusV2Color(activity.content.state.statusV2))
                        }
                        
                        Spacer()
                        
                        // Track
                        if let track = activity.content.state.track {
                            HStack(spacing: 4) {
                                Text("Track")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                Text(track)
                                    .font(.subheadline.bold())
                                    .foregroundColor(.orange)
                            }
                            .padding(.horizontal, 8)
                            .padding(.vertical, 2)
                            .background(
                                RoundedRectangle(cornerRadius: 6)
                                    .fill(.orange.opacity(0.1))
                            )
                        }
                    }
                    
                    // Progress bar
                    GeometryReader { geometry in
                        ZStack(alignment: .leading) {
                            RoundedRectangle(cornerRadius: 3)
                                .fill(.gray.opacity(0.2))
                                .frame(height: 6)
                            
                            RoundedRectangle(cornerRadius: 3)
                                .fill(.blue)
                                .frame(width: geometry.size.width * activity.content.state.journeyProgress, height: 6)
                        }
                    }
                    .frame(height: 6)
                    
                    // Next stop and last updated
                    HStack {
                        if let nextStop = activity.content.state.nextStop {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Next Stop")
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                                Text(Stations.displayName(for: nextStop.stationName))
                                    .font(.caption.bold())
                                    .foregroundColor(.primary)
                                    .lineLimit(1)
                            }
                        }
                        
                        Spacer()
                        
                        VStack(alignment: .trailing, spacing: 2) {
                            Text("Updated")
                                .font(.caption2)
                                .foregroundColor(.secondary)
                            Text(formatTimeAgo(activity.content.state.lastUpdated))
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                .padding(16)
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(.ultraThinMaterial)
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(.blue.opacity(0.3), lineWidth: 1)
                        )
                )
                .padding(.horizontal)
            }
            .buttonStyle(.plain)
            .onReceive(refreshTimer) { _ in
                // Force UI refresh every 5 seconds
                objectWillChange.send()
            }
        }
    }
    
    private func navigateToTrainDetails(activity: Activity<TrainActivityAttributes>) {
        // Use the train number and origin station code for navigation
        let trainNumber = activity.attributes.trainNumber
        let fromStation = activity.attributes.originStationCode
        appState.navigationPath.append(NavigationDestination.trainDetailsFlexible(trainNumber: trainNumber, fromStation: fromStation))
    }
    
    private func statusV2Color(_ statusV2: String) -> Color {
        switch statusV2 {
        case "SCHEDULED": return .green
        case "DELAYED": return .red
        case "BOARDING": return .orange
        case "EN_ROUTE", "DEPARTED": return .blue
        case "ARRIVED": return .green
        case "CANCELLED": return .red
        default: return .primary
        }
    }
    
    private func statusV2DisplayText(_ statusV2: String) -> String {
        switch statusV2 {
        case "EN_ROUTE": return "En Route"
        case "BOARDING": return "Boarding"
        case "SCHEDULED": return "Scheduled"
        case "DELAYED": return "Delayed"
        case "ARRIVED": return "Arrived"
        case "CANCELLED": return "Cancelled"
        default: return statusV2.capitalized
        }
    }
    
    private func formatTimeAgo(_ date: Date) -> String {
        let now = Date()
        let timeInterval = now.timeIntervalSince(date)
        
        if timeInterval < 60 {
            return "just now"
        } else if timeInterval < 3600 {
            let minutes = Int(timeInterval / 60)
            return "\(minutes)m ago"
        } else {
            let formatter = DateFormatter()
            formatter.timeStyle = .short
            return formatter.string(from: date)
        }
    }
    
    // Publisher for forcing UI updates
    private let objectWillChange = PassthroughSubject<Void, Never>()
}