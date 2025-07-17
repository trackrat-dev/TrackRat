import SwiftUI
import ActivityKit

@available(iOS 16.1, *)
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
                    Text("ACTIVE TRIPS")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(.white.opacity(0.7))
                        .padding(.horizontal)
                    
                    Button {
                        // Navigate to train details using flexible navigation
                        appState.navigationPath.append(
                            NavigationDestination.trainDetailsFlexible(
                                trainNumber: activity.attributes.trainNumber,
                                fromStation: activity.attributes.originStationCode
                            )
                        )
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Train \(activity.attributes.trainNumber)")
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
                                        .stroke(TrackRatTheme.Colors.border, lineWidth: 1)
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
        .background(TrackRatTheme.Colors.surface)
}