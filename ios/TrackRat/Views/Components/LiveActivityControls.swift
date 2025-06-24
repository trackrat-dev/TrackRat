import SwiftUI
import ActivityKit

@available(iOS 16.1, *)
struct LiveActivityControls: View {
    let train: Train
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
                        Text("Live Activity Active")
                            .font(.subheadline.bold())
                            .foregroundColor(.white)
                        Text("Train tracking on Lock Screen")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.8))
                    }
                    
                    Spacer()
                    
                    Button("Stop") {
                        Task {
                            await liveActivityService.endCurrentActivity()
                        }
                    }
                    .font(.caption.bold())
                    .foregroundColor(.white)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(
                        RoundedRectangle(cornerRadius: 8)
                            .fill(.white.opacity(0.2))
                    )
                }
                .padding()
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color.blue.opacity(0.7))
                )
            } else {
                // Start Live Activity button
                Button {
                    startLiveActivity()
                } label: {
                    HStack {
                        if isStarting {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: .white))
                                .scaleEffect(0.8)
                        } else {
                            Image(systemName: "location.circle.fill")
                                .font(.title2)
                        }
                        
                        Text("📍 Watch This Train")
                            .font(.subheadline.bold())
                        
                        Spacer()
                        
                        Image(systemName: "chevron.right")
                            .font(.caption)
                            .opacity(0.6)
                    }
                    .foregroundColor(.black)
                    .padding()
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(Color.clear)
                            .opacity(isStarting ? 0.6 : 1.0)
                    )
                }
                .disabled(isStarting || !liveActivityService.isSupported)
                
                // Support info if not available
                if !liveActivityService.isSupported {
                    HStack {
                        Image(systemName: "info.circle")
                            .foregroundColor(.orange)
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Live Activities Not Available")
                                .font(.caption.bold())
                                .foregroundColor(.orange)
                            Text(liveActivityService.supportStatus)
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.8))
                        }
                        Spacer()
                    }
                    .padding(.horizontal)
                }
            }
        }
        .alert("Live Activity Error", isPresented: $showingError) {
            Button("OK") { }
        } message: {
            Text(errorMessage ?? "An unknown error occurred")
        }
    }
    
    private func startLiveActivity() {
        guard !isStarting else { return }
        
        // Validate required data before starting
        guard !originCode.isEmpty, !destinationCode.isEmpty, !origin.isEmpty, !destination.isEmpty else {
            errorMessage = "Missing route information. Please go back and select your journey again."
            showingError = true
            return
        }
        
        // Check if Live Activities are supported
        guard liveActivityService.isSupported else {
            errorMessage = "Live Activities are not supported on this device or iOS version."
            showingError = true
            return
        }
        
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
            } catch {
                await MainActor.run {
                    let friendlyError = friendlyErrorMessage(for: error)
                    errorMessage = friendlyError
                    showingError = true
                }
            }
            
            await MainActor.run {
                isStarting = false
            }
        }
    }
    
    private func friendlyErrorMessage(for error: Error) -> String {
        if let liveActivityError = error as? LiveActivityError {
            return liveActivityError.localizedDescription
        }
        
        let errorText = error.localizedDescription.lowercased()
        
        if errorText.contains("permission") || errorText.contains("denied") {
            return "Live Activities permission is required. Please enable it in Settings > TrackRat > Allow Notifications."
        } else if errorText.contains("limit") || errorText.contains("maximum") {
            return "Maximum number of Live Activities reached. Please end other activities and try again."
        } else if errorText.contains("network") || errorText.contains("connection") {
            return "Network error occurred. Please check your connection and try again."
        } else {
            return "Unable to start Live Activity: \(error.localizedDescription)"
        }
    }
}

// MARK: - Preview Helper for older iOS versions
struct LiveActivityControlsPreview: View {
    let train: Train
    let origin: String
    let destination: String
    let originCode: String
    let destinationCode: String
    
    var body: some View {
        if #available(iOS 16.1, *) {
            LiveActivityControls(
                train: train,
                origin: origin,
                destination: destination,
                originCode: originCode,
                destinationCode: destinationCode
            )
        } else {
            EmptyView()
        }
    }
}