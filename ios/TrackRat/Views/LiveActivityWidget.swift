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
                    TrainStatusV2View(
                        trainNumber: context.attributes.trainNumber,
                        statusV2: context.state.statusV2,
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
                // Compact leading (left side of Dynamic Island) - just train emoji
                Image(systemName: "tram.fill")
                    .font(.system(size: 12))
                    .foregroundColor(.white)
                    .frame(maxWidth: 67, alignment: .leading)
            } compactTrailing: {
                // Compact trailing (right side of Dynamic Island)
                // Maximum width: 67pt for Dynamic Island compatibility
                DynamicIslandCompactTrailing(context: context)
                    .frame(maxWidth: 67, alignment: .trailing)
                    .clipped()
            } minimal: {
                // Minimal (when other Dynamic Islands are active) - just train emoji
                Image(systemName: "tram.fill")
                    .font(.system(size: 10))
                    .foregroundColor(.white)
                    .frame(maxWidth: 32, alignment: .center)
            }
            .widgetURL(URL(string: "trackrat://train/\(context.attributes.trainId)"))
        }
    }

    // Helper function to determine the icon based on StatusV2
    private func trainStatusV2Icon(statusV2: String) -> String {
        switch statusV2 {
        case "SCHEDULED":
            return "clock.fill"
        case "DELAYED":
            return "exclamationmark.triangle.fill"
        case "BOARDING":
            return "figure.walk"
        case "EN_ROUTE", "DEPARTED":
            return "tram.fill"
        case "ARRIVED":
            return "flag.checkered"
        case "CANCELLED":
            return "xmark.circle.fill"
        default:
            return "questionmark.circle.fill"
        }
    }
    
    // Helper function to get compact StatusV2 text for Dynamic Island
    private func getCompactStatusV2(_ statusV2: String) -> String {
        switch statusV2 {
        case "BOARDING":
            return "BRD"
        case "DELAYED":
            return "DEL"
        case "EN_ROUTE":
            return "ENR"
        case "DEPARTED":
            return "DEP"
        case "SCHEDULED":
            return "SCH"
        case "ARRIVED":
            return "ARR"
        case "CANCELLED":
            return "CAN"
        default:
            return "UNK"
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
                            TrackBadgeV2(track: track, statusV2: context.state.statusV2)
                        }
                    }
                    
                    Text("\(Stations.displayName(for: context.attributes.origin)) → \(Stations.displayName(for: context.attributes.destination))")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                LiveActivityStatusBadgeV2(statusV2: context.state.statusV2)
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
            
            // TrackRat prediction (if available)
            if let trackRatPrediction = context.state.trackRatPrediction {
                HStack {
                    Text(trackRatPrediction.displayText)
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
        HStack(spacing: 2) {
            // Prioritize track information if available
            if let track = context.state.track, track.count <= 3 {
                Text("T\(track)")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundColor(.orange)
                    .lineLimit(1)
            } else if let nextStop = context.state.nextStop {
                // Show time if no track or track too long
                Text(formatTime(nextStop.estimatedArrival))
                    .font(.system(size: 9))
                    .foregroundColor(.white)
                    .lineLimit(1)
            } else {
                // Fallback to journey progress
                Text("\(Int(context.state.journeyProgress * 100))%")
                    .font(.system(size: 9, weight: .medium))
                    .foregroundColor(.blue)
                    .lineLimit(1)
            }
        }
        .frame(maxWidth: 67, alignment: .trailing)
    }
    
    private func formatTime(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "h:mm"
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        return formatter.string(from: date)
    }
    
    // Check if time is within next few minutes for display priority
    private func isTimeImportant(_ date: Date) -> Bool {
        let timeInterval = date.timeIntervalSince(Date())
        return timeInterval > 0 && timeInterval < 900 // Within 15 minutes
    }
}

@available(iOS 16.1, *)
struct TrainStatusV2View: View {
    let trainNumber: String
    let statusV2: String
    let track: String?
    
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 4) {
                Text("🚂")
                    .font(.caption)
                Text(trainNumber)
                    .font(.caption.bold())
                    .lineLimit(1)
            }
            
            if let track = track {
                Text("Track \(track)")
                    .font(.caption2)
                    .foregroundColor(.orange)
                    .lineLimit(1)
                    .truncationMode(.tail)
            }
            
            Text(statusV2DisplayText(statusV2))
                .font(.caption2)
                .foregroundColor(statusV2Color(statusV2))
                .lineLimit(1)
        }
    }
    
    private func statusV2Color(_ statusV2: String) -> Color {
        switch statusV2 {
        case "SCHEDULED": return .green
        case "DELAYED": return .red
        case "BOARDING": return .orange
        case "EN_ROUTE": return .blue
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
                    .truncationMode(.tail)
                
                Text(formatTime(nextStop.estimatedArrival))
                    .font(.caption2)
                    .foregroundColor(nextStop.isDelayed ? .red : .primary)
                    .lineLimit(1)
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
                    .lineLimit(1)
                    .truncationMode(.tail)
                
                Spacer()
                
                if let eta = destinationETA {
                    Text("Arrives \(destination) ~\(formatTime(eta))")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                        .truncationMode(.tail)
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
struct LiveActivityStatusBadgeV2: View {
    let statusV2: String
    
    var body: some View {
        Text(statusV2DisplayText(statusV2))
            .font(.caption.bold())
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(backgroundColorV2())
            )
            .foregroundColor(.white)
    }
    
    private func backgroundColorV2() -> Color {
        switch statusV2 {
        case "SCHEDULED": return .green
        case "DELAYED": return .red
        case "BOARDING": return .orange
        case "EN_ROUTE", "DEPARTED": return .blue
        case "ARRIVED": return .green
        case "CANCELLED": return .red
        default: return .gray
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
}

@available(iOS 16.1, *)
struct TrackBadgeV2: View {
    let track: String
    let statusV2: String
    
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
                .fill(statusV2 == "BOARDING" ? .orange : .blue)
        )
        .foregroundColor(.white)
    }
}
