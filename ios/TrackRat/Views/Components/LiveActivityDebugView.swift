import SwiftUI
import ActivityKit

@available(iOS 16.1, *)
struct LiveActivityDebugView: View {
    @StateObject private var liveActivityService = LiveActivityService.shared
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Live Activity Debug")
                .font(.title2)
                .fontWeight(.bold)
            
            Group {
                Text("Activity Status: \(liveActivityService.isActivityActive ? "Active" : "Inactive")")
                
                if let activity = liveActivityService.currentActivity {
                    Text("Train: \(activity.attributes.trainNumber)")
                    Text("Route: \(activity.attributes.origin) → \(activity.attributes.destination)")
                    Text("Status: \(activity.content.state.status)")
                    if let track = activity.content.state.track {
                        Text("Track: \(track)")
                    }
                    Text("Progress: \(Int(activity.content.state.journeyProgress * 100))%")
                    
                    Button("End Activity") {
                        Task {
                            await liveActivityService.endCurrentActivity()
                        }
                    }
                    .buttonStyle(.bordered)
                } else {
                    Text("No active Live Activity")
                }
            }
            .font(.body)
            
            Spacer()
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

#Preview {
    LiveActivityDebugView()
        .preferredColorScheme(.dark)
}