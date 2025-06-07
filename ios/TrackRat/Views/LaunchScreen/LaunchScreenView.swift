import SwiftUI
import UIKit

struct LaunchScreenView: View {
    @State private var logoScale: CGFloat = 0.8
    @State private var logoOpacity: Double = 0
    @State private var titleOffset: CGFloat = 30
    @State private var titleOpacity: Double = 0
    @State private var trainPosition: CGFloat = -1.0
    @State private var trainOpacity: Double = 0
    @State private var showSparkles = false
    @State private var trackPulse: CGFloat = 0.8
    
    let onComplete: () -> Void
    
    var body: some View {
        ZStack {
            // Black gradient background
            TrackRatTheme.Colors.primaryGradient
                .ignoresSafeArea()
            
            VStack(spacing: TrackRatTheme.Spacing.xl) {
                Spacer()
                
                // Enhanced mascot and branding
                VStack(spacing: TrackRatTheme.Spacing.xl) {
                    // Sophisticated train track visualization
                    ZStack {
                        // Glowing track effect
                        RoundedRectangle(cornerRadius: 10)
                            .fill(
                                LinearGradient(
                                    gradient: Gradient(colors: [
                                        Color.white.opacity(0.05),
                                        Color.orange.opacity(0.1),
                                        Color.white.opacity(0.05)
                                    ]),
                                    startPoint: .leading,
                                    endPoint: .trailing
                                )
                            )
                            .frame(width: 200, height: 80)
                            .scaleEffect(trackPulse)
                        
                        // Enhanced train tracks
                        VStack(spacing: 0) {
                            // Top rail
                            LinearGradient(
                                gradient: Gradient(colors: [
                                    Color.white.opacity(0.2),
                                    Color.white.opacity(0.5),
                                    Color.white.opacity(0.2)
                                ]),
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                            .frame(width: 180, height: 3)
                            .overlay(
                                Rectangle()
                                    .fill(Color.orange.opacity(0.3))
                                    .blur(radius: 4)
                            )
                            
                            Spacer()
                                .frame(height: 20)
                            
                            // Bottom rail
                            LinearGradient(
                                gradient: Gradient(colors: [
                                    Color.white.opacity(0.2),
                                    Color.white.opacity(0.5),
                                    Color.white.opacity(0.2)
                                ]),
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                            .frame(width: 180, height: 3)
                            .overlay(
                                Rectangle()
                                    .fill(Color.orange.opacity(0.3))
                                    .blur(radius: 4)
                            )
                        }
                        
                        // Animated commuter train
                        HStack(spacing: 0) {
                            // Stylized train with commuters
                            ZStack {
                                // Train car
                                RoundedRectangle(cornerRadius: 10)
                                    .fill(
                                        LinearGradient(
                                            gradient: Gradient(colors: [
                                                TrackRatTheme.Colors.accent,
                                                TrackRatTheme.Colors.accent.opacity(0.8)
                                            ]),
                                            startPoint: .top,
                                            endPoint: .bottom
                                        )
                                    )
                                    .frame(width: 50, height: 30)
                                    .overlay(
                                        // Windows with commuters
                                        HStack(spacing: 3) {
                                            ForEach(0..<3) { i in
                                                RoundedRectangle(cornerRadius: 3)
                                                    .fill(Color.yellow.opacity(0.9))
                                                    .frame(width: 10, height: 12)
                                                    .overlay(
                                                        // Commuter silhouettes
                                                        Image(systemName: "person.fill")
                                                            .font(.system(size: 6))
                                                            .foregroundColor(.black.opacity(0.3))
                                                    )
                                            }
                                        }
                                    )
                                    .shadow(color: TrackRatTheme.Colors.accent, radius: 10, x: 0, y: 0)
                                
                                // Front headlight
                                Circle()
                                    .fill(Color.yellow)
                                    .frame(width: 6, height: 6)
                                    .offset(x: 25)
                                    .blur(radius: 1)
                            }
                            .scaleEffect(logoScale)
                            .opacity(trainOpacity)
                            
                            // Motion effects
                            if trainPosition > -0.5 {
                                HStack(spacing: 2) {
                                    ForEach(0..<4) { i in
                                        Rectangle()
                                            .fill(
                                                LinearGradient(
                                                    gradient: Gradient(colors: [
                                                        Color.white.opacity(0.4 - Double(i) * 0.1),
                                                        Color.clear
                                                    ]),
                                                    startPoint: .leading,
                                                    endPoint: .trailing
                                                )
                                            )
                                            .frame(width: 20 - CGFloat(i * 4), height: 1)
                                            .offset(x: -CGFloat(i * 5))
                                    }
                                }
                            }
                        }
                        .offset(x: trainPosition * 90)
                        
                        // Sparkle effects
                        ForEach(0..<6) { i in
                            Image(systemName: "sparkle")
                                .font(.system(size: 10))
                                .foregroundColor(.yellow)
                                .opacity(showSparkles ? 0.8 : 0)
                                .offset(
                                    x: CGFloat.random(in: -80...80),
                                    y: CGFloat.random(in: -30...30)
                                )
                                .animation(
                                    .easeInOut(duration: 0.6)
                                        .delay(Double(i) * 0.1),
                                    value: showSparkles
                                )
                        }
                    }
                    .frame(width: 200, height: 80)
                    
                    // App title with tagline
                    VStack(spacing: TrackRatTheme.Spacing.sm) {
                        Text("TrackRat")
                            .font(TrackRatTheme.Typography.title1)
                            .foregroundColor(.white)
                            .offset(y: titleOffset)
                            .opacity(titleOpacity)
                        
                        Text("Beat the Commute")
                            .font(TrackRatTheme.Typography.body)
                            .foregroundColor(TrackRatTheme.Colors.accent)
                            .offset(y: titleOffset)
                            .opacity(titleOpacity)
                        
                        Text("Real-time tracking for your daily race")
                            .font(TrackRatTheme.Typography.caption)
                            .foregroundColor(.white.opacity(0.6))
                            .offset(y: titleOffset)
                            .opacity(titleOpacity * 0.8)
                            .multilineTextAlignment(.center)
                    }
                }
                
                Spacer()
                
                // Loading indicator
                VStack(spacing: TrackRatTheme.Spacing.sm) {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        .scaleEffect(1.2)
                    
                    Text("Getting your trains ready...")
                        .font(TrackRatTheme.Typography.caption)
                        .foregroundColor(.white.opacity(0.7))
                }
                .padding(.bottom, TrackRatTheme.Spacing.xxl)
            }
        }
        .onAppear {
            startAnimations()
        }
    }
    
    private func startAnimations() {
        // Initial haptic to signal app launch
        let impactFeedback = UIImpactFeedbackGenerator(style: .medium)
        impactFeedback.impactOccurred()
        
        // Track pulse animation
        withAnimation(.easeInOut(duration: 1.5).repeatForever(autoreverses: true)) {
            trackPulse = 1.05
        }
        
        // Train arrival animation
        withAnimation(.easeOut(duration: 1.2)) {
            trainPosition = 0
            trainOpacity = 1.0
        }
        
        // Train scale animation with haptic when train "arrives"
        withAnimation(.spring(response: 0.8, dampingFraction: 0.6).delay(0.3)) {
            logoScale = 1.0
            logoOpacity = 1.0
        }
        
        // Play arrival haptic
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
            let arrivalFeedback = UIImpactFeedbackGenerator(style: .light)
            arrivalFeedback.impactOccurred()
        }
        
        // Title animation (delayed)
        withAnimation(.easeInOut(duration: 0.8).delay(0.8)) {
            titleOffset = 0
            titleOpacity = 1.0
        }
        
        // Sparkle effects after train arrives with celebration haptic
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            showSparkles = true
            let sparklesFeedback = UINotificationFeedbackGenerator()
            sparklesFeedback.notificationOccurred(.success)
        }
        
        // Complete after total animation time
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) {
            withAnimation(.easeInOut(duration: 0.4)) {
                onComplete()
            }
        }
    }
}

#Preview {
    LaunchScreenView {
        print("Launch complete")
    }
}