import SwiftUI
import UIKit

struct OnboardingVideoView: View {
    @State private var videoEnded = false
    @State private var videoFailed = false
    let onComplete: () -> Void
    
    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            
            if !videoFailed {
                if let videoURL = Bundle.main.url(forResource: "intro_animation", withExtension: "mp4") {
                    VideoPlayerView(url: videoURL) {
                        // Video ended successfully
                        videoEnded = true
                        
                        // Success haptic feedback
                        let notification = UINotificationFeedbackGenerator()
                        notification.notificationOccurred(.success)
                        
                        // Auto-advance to onboarding after brief pause
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                            onComplete()
                        }
                    } onError: { error in
                        print("Video playback error: \(error)")
                        videoFailed = true
                    } onStart: {
                        // Video started playing - light haptic feedback
                        let impactFeedback = UIImpactFeedbackGenerator(style: .light)
                        impactFeedback.impactOccurred()
                    }
                    .ignoresSafeArea()
                } else {
                    // Video file not found - skip directly to onboarding
                    Color.black
                        .ignoresSafeArea()
                        .onAppear {
                            print("Video file not found, skipping to onboarding")
                            onComplete()
                        }
                }
            } else {
                // Video failed - skip directly to onboarding
                Color.black
                    .ignoresSafeArea()
                    .onAppear {
                        onComplete()
                    }
            }
        }
    }
}

#Preview {
    OnboardingVideoView {
        print("Video completed")
    }
}