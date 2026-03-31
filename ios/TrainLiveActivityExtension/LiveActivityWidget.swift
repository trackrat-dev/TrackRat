import SwiftUI
import ActivityKit
import WidgetKit
import os.log

// MARK: - Color Helpers
private let lightBlueColor = Color(red: 0x84/255.0, green: 0xca/255.0, blue: 0xf4/255.0)
private let trackRatBlue = Color(hex: "#0e5c8d")

// Helper function to get theme color
private func themeColor(for theme: String) -> Color {
    switch theme {
    case "blue": return trackRatBlue
    case "black": return Color.black
    default: return trackRatBlue
    }
}

// Helper function to get "Departing in" text color based on theme
private func departingTextColor(for theme: String) -> Color {
    switch theme {
    case "black": return .orange
    default: return lightBlueColor
    }
}

private let logger = Logger(subsystem: "net.trackrat.TrackRat", category: "LiveActivity")

// Helper function to create deep link URL from Live Activity attributes
private func createDeepLinkURL(from attributes: TrainActivityAttributes) -> URL? {
    var components = URLComponents()
    components.scheme = "trackrat"
    components.host = "train"
    components.path = "/\(attributes.trainNumber)"
    
    var queryItems: [URLQueryItem] = []
    queryItems.append(URLQueryItem(name: "from", value: attributes.originStationCode))
    queryItems.append(URLQueryItem(name: "to", value: attributes.destinationStationCode))
    components.queryItems = queryItems
    
    let url = components.url
    logger.info("🔗 Generated Live Activity deep link: \(url?.absoluteString ?? "nil")")
    return url
}

// Debug logging helper
private func debugLog(_ message: String, context: ActivityViewContext<TrainActivityAttributes>) {
    let state = context.state
    logger.info("🚂 \(message)")
    logger.info("  Train: \(context.attributes.trainNumber)")
    logger.info("  Status: \(state.status)")
    logger.info("  Track: \(state.track ?? "nil")")
    logger.info("  Progress: \(state.journeyProgress)")
    logger.info("  HasDeparted: \(state.hasTrainDeparted)")
    logger.info("  CurrentStop: \(state.currentStopName)")
    logger.info("  NextStop: \(state.nextStopName ?? "nil")")
    logger.info("  DelayMinutes: \(state.delayMinutes)")
    logger.info("  DataTimestamp: \(state.dataTimestamp)")
    
    // Log time fields to debug the issue
    if let depTime = state.scheduledDepartureTime {
        logger.info("  ScheduledDeparture (String): \(depTime)")
        if let parsed = Date.fromISO8601(depTime) {
            logger.info("  ScheduledDeparture (Parsed): \(parsed)")
        } else {
            logger.error("  ScheduledDeparture: Failed to parse ISO8601")
        }
    } else {
        logger.info("  ScheduledDeparture: nil")
    }
    
    if let arrTime = state.scheduledArrivalTime {
        logger.info("  ScheduledArrival (String): \(arrTime)")
        if let parsed = Date.fromISO8601(arrTime) {
            logger.info("  ScheduledArrival (Parsed): \(parsed)")
        } else {
            logger.error("  ScheduledArrival: Failed to parse ISO8601")
        }
    } else {
        logger.info("  ScheduledArrival: nil")
    }
    
    if let nextTime = state.nextStopArrivalTime {
        logger.info("  NextStopArrival (String): \(nextTime)")
        if let parsed = Date.fromISO8601(nextTime) {
            logger.info("  NextStopArrival (Parsed): \(parsed)")
        } else {
            logger.error("  NextStopArrival: Failed to parse ISO8601")
        }
    } else {
        logger.info("  NextStopArrival: nil")
    }
}

// Helper functions for data freshness
func dataFreshnessText(_ timestamp: TimeInterval) -> String {
    let secondsAgo = Int(Date().timeIntervalSince1970 - timestamp)
    
    if secondsAgo < 60 {
        return "\(secondsAgo) sec ago"
    } else {
        let minutesAgo = secondsAgo / 60
        return "\(minutesAgo) min ago"
    }
}

// Helper function to strip "Station" suffix from station names
func stripStationSuffix(_ stationName: String) -> String {
    if stationName.hasSuffix(" Station") {
        return String(stationName.dropLast(8)) // Remove " Station"
    }
    return stationName
}

func isDataStaleCheck(_ timestamp: TimeInterval) -> Bool {
    let secondsAgo = Date().timeIntervalSince1970 - timestamp
    return secondsAgo > 180  // 3 minutes
}

@available(iOS 16.1, *)
struct TrainLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: TrainActivityAttributes.self) { context in
            // Lock Screen widget UI
            TrainLiveActivityView(context: context)
                .activityBackgroundTint(themeColor(for: context.attributes.theme))
                .activitySystemActionForegroundColor(.white)
                .widgetURL(createDeepLinkURL(from: context.attributes))
                .onAppear {
                    debugLog("🔵 Lock Screen appeared", context: context)
                }
        } dynamicIsland: { context in
            DynamicIsland {
                // Expanded UI (when tapped)
                DynamicIslandExpandedRegion(.center) {
                    // Only center status content
                    CenterStatusView(state: context.state, theme: context.attributes.theme)
                        .padding(.top, 17) // Aligns with station name text
                }
                DynamicIslandExpandedRegion(.leading) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(stripStationSuffix(context.state.nextStopName ?? "--"))
                            .font(.caption)
                            .lineLimit(2)
                            .minimumScaleFactor(0.75)
                        if let time = context.state.contextAwareNextStopTime {
                            Text(time, style: .time)
                                .font(.caption)
                                .foregroundColor(.white)
                        }
                    }
                    .padding(.leading, 8)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    VStack(alignment: .trailing, spacing: 2) {
                        Text(stripStationSuffix(context.attributes.destination))
                            .font(.caption)
                            .lineLimit(2)
                            .minimumScaleFactor(0.75)
                            .multilineTextAlignment(.trailing)
                        if let time = context.state.destinationArrivalTime {
                            Text(time, style: .time)
                                .font(.caption)
                                .foregroundColor(.white)
                                .multilineTextAlignment(.trailing)
                        }
                    }
                    .padding(.trailing, 8)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    VStack(spacing: 4) {
                        // Progress bar - ensure value is valid
                        let validProgress = max(0, min(1, context.state.journeyProgress))
                        ProgressView(value: validProgress)
                            .progressViewStyle(.linear)
                            .tint(departingTextColor(for: context.attributes.theme))
                            .padding(.horizontal, 8)
                            .onAppear {
                                logger.info("🟡 Progress bar - value: \(validProgress)")
                            }
                    }
                }
            } compactLeading: {
                // Compact leading (left side) - Time to departure/arrival
                Text(context.state.compactLeadingText)
                        .font(.caption)
                    .fontWeight(.medium)
                    .foregroundColor(.white)
                .onAppear {
                    debugLog("🟢 Compact appeared", context: context)
                }
            } compactTrailing: {
                // Compact trailing (right side) - Track or station code
                Text(context.state.compactTrailingText)
                    .font(.caption)
                    .monospacedDigit()
                    .fontWeight(.medium)
                    .foregroundColor(.white)
            } minimal: {
                // Minimal view (when multiple activities)
                Image(systemName: "tram.fill")
                    .font(.caption)
            }
            .widgetURL(createDeepLinkURL(from: context.attributes))
        }
    }
}

// MARK: - Lock Screen View

@available(iOS 16.1, *)
struct TrainLiveActivityView: View {
    let context: ActivityViewContext<TrainActivityAttributes>
    @State private var currentTime = Date()
    
    // Timer to update freshness display every 10 seconds
    let timer = Timer.publish(every: 10, on: .main, in: .common).autoconnect()
    
    // Real-time freshness calculation
    private var freshnessText: String {
        let secondsAgo = Int(currentTime.timeIntervalSince1970 - context.state.dataTimestamp)
        
        if secondsAgo < 60 {
            return "\(secondsAgo) sec ago"
        } else {
            let minutesAgo = secondsAgo / 60
            return "\(minutesAgo) min ago"
        }
    }
    
    private var isDataStale: Bool {
        let secondsAgo = currentTime.timeIntervalSince1970 - context.state.dataTimestamp
        return secondsAgo > 180  // 3 minutes
    }
    
    var body: some View {
        VStack(spacing: 8) {
            // Header
            HStack {
                // For trains with synthetic IDs, show destination instead
                let tn = context.attributes.trainNumber
                let trainLabel = tn.hasPrefix("PATH_") || tn.hasPrefix("PATCO_") || tn.hasPrefix("L") || tn.hasPrefix("M") || tn.hasPrefix("S")
                    ? context.attributes.destination
                    : "Train \(tn)"
                Label(trainLabel, systemImage: "tram.fill")
                    .font(.headline)
                    .foregroundColor(.white)
                Spacer()
            }
            
            
            // Next stop and destination info
            HStack(spacing: 16) {
                // Left side - Next stop
                VStack(alignment: .leading, spacing: 4) {
                    Text(context.state.hasTrainDeparted ? "Next Stop" : "Departing")
                        .font(.caption)
                        .foregroundColor(.white)
                    Text(stripStationSuffix(context.state.nextStopName ?? "--"))
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(.white)
                    if let time = context.state.contextAwareNextStopTime {
                        Text(time, style: .time)
                            .font(.caption)
                            .foregroundColor(.white)
                    }
                }
                
                Spacer()
                
                // Right side - Destination
                VStack(alignment: .trailing, spacing: 4) {
                    Text("Destination")
                        .font(.caption)
                        .foregroundColor(.white)
                    Text(stripStationSuffix(context.attributes.destination))
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(.white)
                    if let time = context.state.destinationArrivalTime {
                        Text(time, style: .time)
                            .font(.caption)
                            .foregroundColor(.white)
                    }
                }
            }
            
            // Dynamic timing: departure before train departs, arrival after departure - centered
            HStack {
                Spacer()
                Group {
                    if !context.state.hasTrainDeparted {
                        // Show departure timing when train hasn't departed yet
                        if let minutes = context.state.minutesUntilDeparture {
                            Text(minutes > 1 ? "Departing in \(minutes) minutes" : minutes == 1 ? "Departing in 1 minute" : minutes == 0 ? "Departing now" : "Departing late")
                                .foregroundColor(.white)
                        } else {
                            Text("Preparing to depart")
                                .foregroundColor(.white)
                        }
                    } else {
                        // Show arrival timing when train has departed
                        if let minutes = context.state.minutesUntilArrival {
                            Text(minutes > 1 ? "Arriving in \(minutes) minutes" : minutes == 1 ? "Arriving in 1 minute" : minutes == 0 ? "Arriving now" : "Arrived")
                                .foregroundColor(.white)
                        } else {
                            Text("En route")
                                .foregroundColor(.white)
                        }
                    }
                    
                    // Add delay indicator if delayed
                    if context.state.delayMinutes >= 4 {
                        Text(" ⚠️ delayed")
                            .foregroundColor(.orange)
                    }
                }
                .font(.callout)
                .fontWeight(.medium)
                Spacer()
            }
            .padding(.top, 4)
        }
        .padding()
        .onReceive(timer) { _ in
            currentTime = Date()
        }
    }
    
    func statusColor(for status: String) -> Color {
        switch status {
        case "BOARDING":
            return .orange
        case "DEPARTED", "EN_ROUTE":
            return .blue
        case "DELAYED":
            return .red
        case "CANCELLED":
            return .gray
        default:
            return .gray.opacity(0.3)
        }
    }
}

// MARK: - Center Status View

@available(iOS 16.1, *)
private struct CenterStatusView: View {
    let state: TrainActivityAttributes.ContentState
    let theme: String
    
    private var displayText: String {
        if !state.hasTrainDeparted && state.trackDisplay != nil {
            return "Boarding on Track \(state.track ?? "")"
        } else if !state.hasTrainDeparted, let minutes = state.minutesUntilDeparture {
            return minutes > 0 ? "Departing in \(minutes)m" : "Departing now"
        } else if state.hasTrainDeparted, let minutes = state.minutesUntilArrival {
            return minutes > 0 ? "Arriving in \(minutes)m" : (minutes == 0 ? "Arriving now" : "Arriving late")
        } else if state.hasTrainDeparted {
            return "En Route"
        } else {
            return "Scheduled"
        }
    }
    
    var body: some View {
        Text(displayText)
            .font(.caption)
            .fontWeight(.semibold)
            .foregroundColor(departingTextColor(for: theme))
    }
}
