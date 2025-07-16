import SwiftUI
import ActivityKit

@available(iOS 16.1, *)
struct LiveActivityControls: View {
    let train: TrainV2
    let origin: String
    let destination: String
    let originCode: String
    let destinationCode: String
    
    @StateObject private var liveActivityService = LiveActivityService.shared
    @State private var isStarting = false
    @State private var errorMessage: String?
    @State private var showingError = false
    
    var body: some View {
        VStack(spacing: 12) {
            if liveActivityService.isActivityActive {
                // Active Live Activity status
                HStack {
                    Image(systemName: "location.fill")
                        .foregroundColor(.white)
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Live Updates Active")
                            .font(.subheadline.bold())
                            .foregroundColor(.white)
                        Text("Real-time tracking enabled")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.8))
                    }
                    
                    Spacer()
                    
                    Button("Stop") {
                        Task {
                            await liveActivityService.endCurrentActivity()
                        }
                    }
                    .buttonStyle(.bordered)
                    .buttonBorderShape(.capsule)
                    .foregroundColor(.white)
                }
                .padding()
                .background(.orange.opacity(0.3))
                .cornerRadius(12)
            } else {
                // Start Live Activity button
                Button {
                    startLiveActivity()
                } label: {
                    HStack {
                        Image(systemName: "location")
                        Text(isStarting ? "Starting..." : "Start Live Updates")
                    }
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(.orange.opacity(0.8))
                    .cornerRadius(12)
                }
                .disabled(isStarting)
                .buttonStyle(.plain)
            }
        }
        .alert("Error", isPresented: $showingError) {
            Button("OK") { }
        } message: {
            Text(errorMessage ?? "Unknown error")
        }
    }
    
    private func startLiveActivity() {
        isStarting = true
        
        Task {
            do {
                try await liveActivityService.startTrackingTrain(
                    train,
                    from: originCode,
                    to: destinationCode,
                    origin: origin,
                    destination: destination
                )
                
                await MainActor.run {
                    isStarting = false
                }
            } catch {
                await MainActor.run {
                    isStarting = false
                    errorMessage = error.localizedDescription
                    showingError = true
                }
            }
        }
    }
}

#Preview {
    LiveActivityControls(
        train: TrainV2(
            id: 123,
            trainId: "123",
            line: LineInfo(code: "NE", name: "Northeast Corridor", color: "#0066CC"),
            destination: "New York Penn Station",
            departure: StationTiming(
                code: "NP",
                name: "Newark Penn Station",
                scheduledTime: Date(),
                updatedTime: nil,
                actualTime: nil,
                track: "7"
            ),
            arrival: nil,
            trainPosition: nil,
            dataFreshness: nil
        ),
        origin: "Newark Penn Station",
        destination: "New York Penn Station",
        originCode: "NP",
        destinationCode: "NY"
    )
    .preferredColorScheme(.dark)
    .padding()
    .background(.black)
}