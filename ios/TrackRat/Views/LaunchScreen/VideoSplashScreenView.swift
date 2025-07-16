import SwiftUI
import UIKit

struct VideoSplashScreenView: View {
    @State private var videoEnded = false
    @State private var videoFailed = false
    @State private var videoStarted = false
    @State private var textOpacity: Double = 0
    @State private var fadeToBlackOpacity: Double = 0
    @State private var hapticTriggered = false
    @State private var showLoadingBuffer = true
    let onComplete: () -> Void
    
    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            
            if !videoFailed {
                // Video player
                if let videoURL = Bundle.main.url(forResource: "intro_animation", withExtension: "mp4") {
                    VideoPlayerView(url: videoURL) {
                        // Video ended successfully
                        // Show logo immediately when video ends
                        withAnimation(.easeOut(duration: 0.3)) {
                            videoEnded = true
                            textOpacity = 1.0
                        }
                        
                        // Success haptic at video end
                        let notification = UINotificationFeedbackGenerator()
                        notification.notificationOccurred(.success)
                        onComplete()

                        // Hold logo for 1 second, then transition
                        //DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
                        //    withAnimation(.easeInOut(duration: 0.4)) {
                        //        onComplete()
                        //    }
                        // }
                    } onError: { error in
                        // Video failed to play
                        print("Video playback error: \(error)")
                        videoFailed = true
                    } onStart: {
                        // Video has started playing
                        videoStarted = true
                        showLoadingBuffer = false
                        
                        // Start the fade timer only after video starts
                        DispatchQueue.main.asyncAfter(deadline: .now() + 4.2) {
                            withAnimation(.easeIn(duration: 1.0)) {
                                fadeToBlackOpacity = 1.0
                            }
                        }
                    }
                    .ignoresSafeArea()
                    .onAppear {
                        // Initial haptic to signal app launch
                        if !hapticTriggered {
                            let impactFeedback = UIImpactFeedbackGenerator(style: .medium)
                            impactFeedback.impactOccurred()
                            hapticTriggered = true
                        }
                    }
                    
                    // Fade to black overlay
                    Color.black
                        .opacity(fadeToBlackOpacity)
                        .ignoresSafeArea()
                        .allowsHitTesting(false)
                    
                    // Loading buffer - shows black screen until video starts
                    if showLoadingBuffer {
                        Color.black
                            .ignoresSafeArea()
                            .allowsHitTesting(false)
                    }
                } else {
                    // Video file not found
                    LaunchScreenView(onComplete: onComplete)
                        .onAppear {
                            print("Video file not found, falling back to original launch screen")
                        }
                }
            } else {
                // Fallback to original launch screen if video fails
                LaunchScreenView(onComplete: onComplete)
            }
            
//            // Logo overlay that appears when video ends
//            if videoEnded {
//                VStack(spacing: TrackRatTheme.Spacing.md) {
//                    Text("TrackRat")
//                        .font(.system(size: 48, weight: .bold, design: .rounded))
//                        .foregroundColor(.white)
//                    
//                    Text("Beat the Commute")
//                        .font(.system(size: 20, weight: .medium))
//                        .foregroundColor(TrackRatTheme.Colors.accent)
//                }
//                .opacity(textOpacity)
//            }
        }
        .background(Color.black)
    }
}
