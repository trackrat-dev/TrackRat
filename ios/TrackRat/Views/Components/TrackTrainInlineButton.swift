import SwiftUI

/// Minimal inline button for tracking a train via Live Activity
struct TrackTrainInlineButton: View {
    let train: TrainV2
    let originCode: String
    let destinationCode: String
    let destinationName: String?
    var textColor: Color = .black.opacity(0.6)

    @ObservedObject private var liveActivityService = LiveActivityService.shared
    @State private var isStarting = false

    private var isTrackingThisTrain: Bool {
        liveActivityService.currentActivity?.attributes.trainNumber == train.trainId
    }

    var body: some View {
        Button {
            handleTap()
        } label: {
            HStack(spacing: 6) {
                Image(systemName: isTrackingThisTrain ? "antenna.radiowaves.left.and.right.slash" : "antenna.radiowaves.left.and.right")
                    .font(.footnote)
                Text(isTrackingThisTrain ? "Stop tracking" : "Track this train")
                    .font(.footnote)
            }
            .foregroundColor(textColor)
        }
        .buttonStyle(.plain)
        .disabled(isStarting)
        .opacity(isStarting ? 0.5 : 1.0)
    }

    private func handleTap() {
        UIImpactFeedbackGenerator(style: .light).impactOccurred()

        // If already tracking, allow stopping regardless of subscription status
        if isTrackingThisTrain {
            Task {
                await liveActivityService.endCurrentActivity()
            }
            return
        }

        isStarting = true
        Task {
            do {
                try await liveActivityService.startTrackingTrain(
                    train,
                    from: originCode,
                    to: destinationCode,
                    origin: Stations.stationName(forCode: originCode) ?? originCode,
                    destination: destinationName ?? ""
                )
            } catch {
                print("Failed to start Live Activity: \(error)")
                await MainActor.run {
                    UINotificationFeedbackGenerator().notificationOccurred(.error)
                }
            }
            await MainActor.run {
                isStarting = false
            }
        }
    }
}
