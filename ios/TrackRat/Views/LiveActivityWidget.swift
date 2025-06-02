import SwiftUI
import ActivityKit
import WidgetKit

@available(iOS 16.1, *)
struct TrainLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: TrainActivityAttributes.self) { context in
            // Lock Screen widget UI
            TrainLiveActivityView(context: context)
                .activityBackgroundTint(.clear)
                .activitySystemActionForegroundColor(.white)
        } dynamicIsland: { context in
            DynamicIsland {
                // Expanded UI (when tapped)
                DynamicIslandExpandedRegion(.leading) {
                    TrainStatusView(
                        trainNumber: context.attributes.trainNumber,
                        status: context.state.status,
                        track: context.state.track
                    )
                }
                DynamicIslandExpandedRegion(.trailing) {
                    NextStopView(nextStop: context.state.nextStop)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    JourneyProgressView(
                        progress: context.state.journeyProgress,
                        currentLocation: context.state.currentLocation,
                        destinationETA: context.state.destinationETA,
                        destination: context.attributes.destination
                    )
                }
            } compactLeading: {
                // Compact leading (left side of Dynamic Island)
                HStack {
                    Image(systemName: "tram.fill") // Or a relevant icon
                        .foregroundColor(.white)
                    Text("\(context.attributes.trainNumber): \(context.state.status.displayText)")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(.white)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            } compactTrailing: {
                // Compact trailing (right side of Dynamic Island)
                DynamicIslandCompactTrailing(context: context)
            } minimal: {
                // Minimal (when other Dynamic Islands are active)
                HStack(spacing: 2) {
                    Image(systemName: trainStatusIcon(status: context.state.status)) // Helper function needed
                        .font(.system(size: 10)) // Slightly smaller icon
                        .foregroundColor(.white)
                    Text(context.attributes.trainNumber)
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(.white)
                }
            }
            .widgetURL(URL(string: "trackrat://train/\(context.attributes.trainId)"))
        }
    }

    // Helper function to determine the icon based on train status
    private func trainStatusIcon(status: TrainStatus) -> String {
        switch status {
        case .onTime:
            return "tram.fill" // Or "checkmark.circle.fill"
        case .delayed:
            return "exclamationmark.triangle.fill"
        case .boarding:
            return "figure.walk" // Or "door.left.hand.open"
        case .departed:
            return "tram.fill" // Or "arrow.right.circle.fill"
        case .scheduled, .unknown:
            return "questionmark.circle.fill" // A default icon for unknown statuses
        }
    }
}

@available(iOS 16.1, *)
struct TrainLiveActivityView: View {
    let context: ActivityViewContext<TrainActivityAttributes>
    
    var body: some View {
        VStack(spacing: 12) {
            // Header with train info
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        Text("🚂")
                        Text("Train \(context.attributes.trainNumber)")
                            .font(.headline.bold())
                        
                        Spacer()
                        
                        if let track = context.state.track {
                            TrackBadge(track: track, status: context.state.status)
                        }
                    }
                    
                    Text("\(Stations.displayName(for: context.attributes.origin)) → \(Stations.displayName(for: context.attributes.destination))")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                LiveActivityStatusBadge(status: context.state.status)
            }
            
            // Journey progress bar
            JourneyProgressBar(
                progress: context.state.journeyProgress,
                currentLocation: context.state.currentLocation
            )
            
            // Bottom info row
            HStack {
                // Current location with stops countdown
                VStack(alignment: .leading, spacing: 2) {
                    Text("Current")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(context.state.currentLocation.displayText)
                        .font(.caption.bold())
                        .lineLimit(1)
                    if let progress = getStopProgress() {
                        Text(progress)
                            .font(.caption2)
                            .foregroundColor(.orange)
                    }
                }
                
                Spacer()
                
                // Next stop info with time
                if let nextStop = context.state.nextStop {
                    VStack(alignment: .trailing, spacing: 2) {
                        Text("Next Stop")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text(Stations.displayName(for: nextStop.stationName))
                            .font(.caption.bold())
                            .lineLimit(1)
                        HStack(spacing: 4) {
                            if nextStop.isDelayed {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .font(.caption2)
                                    .foregroundColor(.red)
                            }
                            Text(formatTimeWithMinutes(nextStop.estimatedArrival))
                                .font(.caption2)
                                .foregroundColor(nextStop.isDelayed ? .red : .secondary)
                        }
                    }
                }
            }
            
            // Owl prediction (if available)
            if let owlPrediction = context.state.owlPrediction {
                HStack {
                    Text(owlPrediction.displayText)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                    Spacer()
                }
            }
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(Color.white.opacity(0.2), lineWidth: 1)
                )
        )
        .widgetURL(URL(string: "trackrat://train/\(context.attributes.trainId)"))
    }
    
    private func getStopProgress() -> String? {
        // We need to calculate stops remaining based on journey progress
        // Since we don't have direct access to the journey progress struct, we'll estimate
        let percentage = Int(context.state.journeyProgress * 100)
        if percentage > 0 && percentage < 100 {
            // Estimate stops based on progress
            let totalStops = 5 // This is an estimate, ideally we'd have this data
            let completedStops = Int(Double(totalStops) * context.state.journeyProgress)
            let remainingStops = totalStops - completedStops
            if remainingStops > 0 {
                return "\(remainingStops) stop\(remainingStops == 1 ? "" : "s") to go"
            }
        }
        return nil
    }
    
    private func formatTimeWithMinutes(_ date: Date) -> String {
        let now = Date()
        let timeInterval = date.timeIntervalSince(now)
        
        if timeInterval > 0 && timeInterval < 3600 { // Within an hour
            let minutes = Int(timeInterval / 60)
            if minutes <= 3 {
                return "~\(minutes) min"
            }
        }
        
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        return formatter.string(from: date)
    }
}

// MARK: - Supporting Views

@available(iOS 16.1, *)
struct DynamicIslandCompactTrailing: View {
    let context: ActivityViewContext<TrainActivityAttributes>
    
    var body: some View {
        HStack(spacing: 3) {
            if let track = context.state.track {
                Text("T\(track)")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundColor(.orange)
            }
            if let nextStop = context.state.nextStop {
                Text(formatTime(nextStop.estimatedArrival))
                    .font(.system(size: 12))
                    .foregroundColor(.white)
            }
        }
        .frame(maxWidth: .infinity, alignment: .trailing)
    }
    
    private func formatTime(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "h:mm"
        return formatter.string(from: date)
    }
}

@available(iOS 16.1, *)
struct TrainStatusView: View {
    let trainNumber: String
    let status: TrainStatus
    let track: String?
    
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 4) {
                Text("🚂")
                    .font(.caption)
                Text(trainNumber)
                    .font(.caption.bold())
            }
            
            if let track = track {
                Text("Track \(track)")
                    .font(.caption2)
                    .foregroundColor(.orange)
            }
            
            Text(status.displayText)
                .font(.caption2)
                .foregroundColor(statusColor(status))
        }
    }
    
    private func statusColor(_ status: TrainStatus) -> Color {
        switch status {
        case .onTime: return .green
        case .delayed: return .red
        case .boarding: return .orange
        default: return .primary
        }
    }
}

@available(iOS 16.1, *)
struct NextStopView: View {
    let nextStop: NextStopInfo?
    
    var body: some View {
        VStack(alignment: .trailing, spacing: 2) {
            Text("Next Stop")
                .font(.caption2)
                .foregroundColor(.secondary)
            
            if let nextStop = nextStop {
                Text(Stations.displayName(for: nextStop.stationName))
                    .font(.caption.bold())
                    .lineLimit(1)
                
                Text(formatTime(nextStop.estimatedArrival))
                    .font(.caption2)
                    .foregroundColor(nextStop.isDelayed ? .red : .primary)
            } else {
                Text("—")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }
    
    private func formatTime(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
}

@available(iOS 16.1, *)
struct JourneyProgressView: View {
    let progress: Double
    let currentLocation: CurrentLocation
    let destinationETA: Date?
    let destination: String
    
    var body: some View {
        VStack(spacing: 4) {
            // Progress bar
            ProgressView(value: progress)
                .progressViewStyle(LinearProgressViewStyle(tint: .blue))
                .scaleEffect(y: 1.5)
            
            // ETA info
            HStack {
                Text(currentLocation.displayText)
                    .font(.caption2)
                    .foregroundColor(.secondary)
                
                Spacer()
                
                if let eta = destinationETA {
                    Text("Arrives \(destination) ~\(formatTime(eta))")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
        }
    }
    
    private func formatTime(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
}

@available(iOS 16.1, *)
struct JourneyProgressBar: View {
    let progress: Double
    let currentLocation: CurrentLocation
    @State private var showPulse = false
    
    var body: some View {
        VStack(spacing: 4) {
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    // Background track
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.gray.opacity(0.3))
                        .frame(height: 4)
                    
                    // Progress fill
                    RoundedRectangle(cornerRadius: 2)
                        .fill(progressColor())
                        .frame(width: geometry.size.width * progress, height: 4)
                    
                    // Train icon as position indicator
                    if progress > 0 && progress < 1 {
                        Image(systemName: "tram.fill")
                            .font(.caption2)
                            .foregroundColor(.white)
                            .background(
                                Circle()
                                    .fill(progressColor())
                                    .frame(width: 14, height: 14)
                            )
                            .scaleEffect(showPulse ? 1.1 : 1.0)
                            .offset(x: (geometry.size.width * progress) - 7)
                            .onAppear {
                                withAnimation(.easeInOut(duration: 1).repeatForever(autoreverses: true)) {
                                    showPulse = true
                                }
                            }
                    }
                }
            }
            .frame(height: 14)
            
            HStack(spacing: 4) {
                Text("\(Int(progress * 100))%")
                    .font(.caption2.bold())
                    .foregroundColor(progressColor())
                Text("•")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Text(getJourneyStatus())
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
        }
    }
    
    private func getJourneyStatus() -> String {
        switch currentLocation {
        case .notDeparted:
            return "Preparing to depart"
        case .boarding:
            return "Boarding now"
        case .departed(_, let minutes):
            return "Departed \(minutes) min ago"
        case .approaching(_, let minutes):
            return "Next stop in \(minutes) min"
        case .enRoute:
            return "En route"
        case .arrived:
            return "Journey complete"
        default:
            return "In transit"
        }
    }
    
    private func progressColor() -> Color {
        switch currentLocation {
        case .boarding:
            return .orange
        case .enRoute, .departed:
            return .blue
        case .arrived:
            return .green
        default:
            return .gray
        }
    }
}

@available(iOS 16.1, *)
struct LiveActivityStatusBadge: View {
    let status: TrainStatus
    
    var body: some View {
        Text(status.displayText)
            .font(.caption.bold())
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(backgroundColor())
            )
            .foregroundColor(.white)
    }
    
    private func backgroundColor() -> Color {
        switch status {
        case .onTime: return .green
        case .delayed: return .red
        case .boarding: return .orange
        case .departed: return .blue
        default: return .gray
        }
    }
}

@available(iOS 16.1, *)
struct TrackBadge: View {
    let track: String
    let status: TrainStatus
    
    var body: some View {
        HStack(spacing: 2) {
            Text("Track")
                .font(.caption2)
            Text(track)
                .font(.caption.bold())
        }
        .padding(.horizontal, 6)
        .padding(.vertical, 2)
        .background(
            RoundedRectangle(cornerRadius: 6)
                .fill(status == .boarding ? .orange : .blue)
        )
        .foregroundColor(.white)
    }
}
