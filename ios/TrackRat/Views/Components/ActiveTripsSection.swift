import SwiftUI
import ActivityKit

struct ActiveTripsSection: View {
    @StateObject private var liveActivityService = LiveActivityService.shared
    @EnvironmentObject private var appState: AppState
    
    private func formattedDepartureTime(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
    
    private func statusText(for activity: Activity<TrainActivityAttributes>) -> String {
        let contentState = activity.content.state
        
        // Use the existing computed properties for intelligent display
        if contentState.hasTrainDeparted {
            if let minutes = contentState.minutesUntilArrival {
                if minutes > 0 {
                    return "Arriving in \(minutes) minutes"
                } else if minutes == 0 {
                    return "Arriving now"
                } else {
                    return "Arrival delayed"
                }
            }
        } else if let track = contentState.track {
            return "Boarding on Track \(track)"
        }
        
        // Default departure time
        return "Scheduled to depart at \(formattedDepartureTime(activity.attributes.departureTime))"
    }
    
    var body: some View {
        Group {
            if liveActivityService.isActivityActive, let activity = liveActivityService.currentActivity {
                VStack(alignment: .leading, spacing: 16) {
                    Button {
                        // Set the route context from Live Activity (like train cards do)
                        appState.selectedDestination = activity.attributes.destination
                        appState.destinationStationCode = activity.attributes.destinationStationCode
                        appState.selectedDeparture = activity.attributes.origin  
                        appState.departureStationCode = activity.attributes.originStationCode
                        
                        // Set current train ID for bottom sheet expansion
                        appState.currentTrainId = activity.attributes.trainId
                        
                        // Set the route context for bottom sheet expansion
                        appState.selectedRoute = TripPair(
                            departureCode: activity.attributes.originStationCode,
                            departureName: activity.attributes.origin,
                            destinationCode: activity.attributes.destinationStationCode,
                            destinationName: activity.attributes.destination,
                            lastUsed: Date(),
                            isFavorite: false
                        )

                        // Use pendingNavigation to expand sheet FIRST, then navigate
                        // This prevents the glitch where sheet expands with empty space
                        // Note: dataSource not available in LiveActivity attributes, backend uses two-phase search
                        appState.pendingNavigation = .trainDetailsFlexible(
                            trainNumber: activity.attributes.trainNumber,
                            fromStation: activity.attributes.originStationCode,
                            journeyDate: nil,  // TODO: Add journeyDate to LiveActivity attributes
                            dataSource: nil
                        )
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                // For trains with synthetic IDs, show destination instead
                                let tn = activity.attributes.trainNumber
                                let hasSyntheticId = tn.hasPrefix("PATH_") || tn.hasPrefix("PATCO_") || tn.hasPrefix("L") || tn.hasPrefix("M") || tn.hasPrefix("S")
                                let trainLabel = hasSyntheticId
                                    ? activity.attributes.destination
                                    : "Train \(tn)"
                                Text(trainLabel)
                                    .font(.headline)
                                    .foregroundColor(.white)

                                Text("\(activity.attributes.origin) → \(activity.attributes.destination)")
                                    .font(.subheadline)
                                    .foregroundColor(.white.opacity(0.8))
                                
                                Text(statusText(for: activity))
                                    .font(.caption)
                                    .foregroundColor(.white.opacity(0.8))
                            }
                            
                            Spacer()
                        }
                        .padding()
                        .background(
                            RoundedRectangle(cornerRadius: 12)
                                .fill(.ultraThinMaterial)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 12)
                                        .stroke(TrackRatTheme.Colors.accent, lineWidth: 1)
                                )
                        )
                        .padding(.horizontal)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }
}

#Preview {
    ActiveTripsSection()
        .environmentObject(AppState())
        .preferredColorScheme(.dark)
        .background(.ultraThinMaterial)
}