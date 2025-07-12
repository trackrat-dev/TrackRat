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
                                
                                HStack {
                                    Text("Scheduled to depart at \(formattedDepartureTime(activity.attributes.departureTime))")
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.8))
                                    
                                    if let track = activity.content.state.track {
                                        Text("Track \(track)")
                                            .font(.caption)
                                            .foregroundColor(.orange)
                                    }
                                }
                            }
                            
                            Spacer()
                        }
                        .padding()
                        .background(.ultraThinMaterial)
                        .cornerRadius(12)
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
        .background(.black)
}