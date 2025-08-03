import SwiftUI
import UIKit

struct RatRaceLoadingView: View {
    @State private var trainPosition: CGFloat = -1.0
    @State private var isRacing = false
    @State private var trackOffset: CGFloat = 0
    @State private var showSparkles = false
    @State private var pulseScale: CGFloat = 1.0
    @State private var hasPlayedStartHaptic = false
    let message: String
    
    init(message: String = "Racing to get your trains...") {
        self.message = message
    }
    
    var body: some View {
        VStack(spacing: TrackRatTheme.Spacing.xl) {
            // Enhanced train track visualization
            ZStack {
                // Moving track sleepers for depth effect
                HStack(spacing: 15) {
                    ForEach(0..<10) { _ in
                        Rectangle()
                            .fill(Color.white.opacity(0.2))
                            .frame(width: 3, height: 20)
                    }
                }
                .frame(width: 200)
                .offset(x: trackOffset)
                .mask(
                    RoundedRectangle(cornerRadius: 10)
                        .frame(width: 180, height: 60)
                )
                
                // Main rails
                VStack(spacing: 0) {
                    // Top rail with gradient
                    LinearGradient(
                        gradient: Gradient(colors: [
                            Color.white.opacity(0.1),
                            Color.white.opacity(0.4),
                            Color.white.opacity(0.1)
                        ]),
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                    .frame(height: 3)
                    .overlay(
                        RoundedRectangle(cornerRadius: 1.5)
                            .stroke(Color.white.opacity(0.6), lineWidth: 0.5)
                    )
                    
                    Spacer()
                        .frame(height: 16)
                    
                    // Bottom rail with gradient
                    LinearGradient(
                        gradient: Gradient(colors: [
                            Color.white.opacity(0.1),
                            Color.white.opacity(0.4),
                            Color.white.opacity(0.1)
                        ]),
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                    .frame(height: 3)
                    .overlay(
                        RoundedRectangle(cornerRadius: 1.5)
                            .stroke(Color.white.opacity(0.6), lineWidth: 0.5)
                    )
                }
                .frame(width: 180)
                
                // Animated train with commuter theme
                HStack(spacing: 0) {
                    // Modern train representation
                    ZStack {
                        // Train body
                        RoundedRectangle(cornerRadius: 8)
                            .fill(TrackRatTheme.Colors.accent)
                            .frame(width: 36, height: 24)
                            .overlay(
                                // Windows
                                HStack(spacing: 4) {
                                    ForEach(0..<3) { _ in
                                        RoundedRectangle(cornerRadius: 2)
                                            .fill(Color.yellow.opacity(0.8))
                                            .frame(width: 6, height: 8)
                                    }
                                }
                            )
                            .shadow(color: TrackRatTheme.Colors.accent.opacity(0.6), radius: 8)
                        
                        // Commuter silhouette (our "rat racer")
                        Image(systemName: "figure.walk")
                            .font(.system(size: 12, weight: .bold))
                            .foregroundColor(.white)
                            .scaleEffect(x: -1, y: 1) // Flip to face forward
                    }
                    .scaleEffect(pulseScale)
                    
                    // Motion lines
                    if isRacing {
                        HStack(spacing: 2) {
                            ForEach(0..<3) { i in
                                Rectangle()
                                    .fill(Color.white.opacity(0.3 - Double(i) * 0.1))
                                    .frame(width: 15 - CGFloat(i * 5), height: 1)
                            }
                        }
                        .offset(x: -5)
                    }
                }
                .offset(x: trainPosition * 90)
                
                // Sparkle effects for delight
                if showSparkles {
                    ForEach(0..<5) { i in
                        Image(systemName: "sparkle")
                            .font(.system(size: 8))
                            .foregroundColor(.yellow.opacity(0.8))
                            .offset(
                                x: CGFloat.random(in: -80...80),
                                y: CGFloat.random(in: -20...20)
                            )
                            .opacity(showSparkles ? 1 : 0)
                            .animation(
                                .easeInOut(duration: 0.8)
                                    .delay(Double(i) * 0.1),
                                value: showSparkles
                            )
                    }
                }
            }
            .frame(width: 180, height: 60)
            
            // Loading message with playful tone
            VStack(spacing: TrackRatTheme.Spacing.sm) {
                Text(message)
                    .font(TrackRatTheme.Typography.body)
                    .foregroundColor(TrackRatTheme.Colors.onSurfaceSecondary)
                    .multilineTextAlignment(.center)
                
                // Subtle progress dots
                HStack(spacing: 8) {
                    ForEach(0..<3) { i in
                        Circle()
                            .fill(Color.white.opacity(0.4))
                            .frame(width: 4, height: 4)
                            .opacity(isRacing ? 1 : 0)
                            .animation(
                                .easeInOut(duration: 0.6)
                                    .repeatForever()
                                    .delay(Double(i) * 0.2),
                                value: isRacing
                            )
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, minHeight: 200)
        .onAppear {
            startAnimations()
        }
    }
    
    private func startAnimations() {
        // Play start haptic once
        if !hasPlayedStartHaptic {
            let impactFeedback = UIImpactFeedbackGenerator(style: .light)
            impactFeedback.impactOccurred()
            hasPlayedStartHaptic = true
        }
        
        // Train racing animation
        withAnimation(.easeInOut(duration: 2.0).repeatForever(autoreverses: true)) {
            trainPosition = 1.0
            isRacing = true
        }
        
        // Track movement for parallax effect
        withAnimation(.linear(duration: 1.0).repeatForever(autoreverses: false)) {
            trackOffset = -30
        }
        
        // Pulse animation for the train
        withAnimation(.easeInOut(duration: 1.5).repeatForever(autoreverses: true)) {
            pulseScale = 1.1
        }
        
        // Sparkle effects periodically with haptic
        Timer.scheduledTimer(withTimeInterval: 3.0, repeats: true) { _ in
            showSparkles = true
            // Play subtle haptic when sparkles appear
            let impactFeedback = UIImpactFeedbackGenerator(style: .soft)
            impactFeedback.impactOccurred()
            
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                showSparkles = false
            }
        }
    }
}

// Compact loading indicator for inline use
struct CompactRatRaceView: View {
    @State private var isAnimating = false
    
    var body: some View {
        HStack(spacing: 4) {
            // Mini train
            RoundedRectangle(cornerRadius: 4)
                .fill(TrackRatTheme.Colors.accent)
                .frame(width: 20, height: 12)
                .overlay(
                    HStack(spacing: 2) {
                        ForEach(0..<2) { _ in
                            RoundedRectangle(cornerRadius: 1)
                                .fill(Color.yellow.opacity(0.8))
                                .frame(width: 4, height: 4)
                        }
                    }
                )
                .offset(x: isAnimating ? 10 : -10)
            
            // Motion lines
            HStack(spacing: 1) {
                ForEach(0..<3) { i in
                    Rectangle()
                        .fill(Color.white.opacity(0.3 - Double(i) * 0.1))
                        .frame(width: 8 - CGFloat(i * 2), height: 1)
                }
            }
            .opacity(isAnimating ? 1 : 0)
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 1.0).repeatForever(autoreverses: true)) {
                isAnimating = true
            }
        }
    }
}

// Progress version with journey metaphor
struct RatRaceProgressView: View {
    let progress: Double
    let fromStation: String
    let toStation: String
    @State private var animatedProgress: Double = 0
    @State private var showTrain = false
    
    var body: some View {
        VStack(spacing: TrackRatTheme.Spacing.sm) {
            // Station labels
            HStack {
                Text(fromStation)
                    .font(TrackRatTheme.Typography.caption)
                    .foregroundColor(TrackRatTheme.Colors.onSurfaceSecondary)
                
                Spacer()
                
                Text(toStation)
                    .font(TrackRatTheme.Typography.caption)
                    .foregroundColor(TrackRatTheme.Colors.onSurfaceSecondary)
            }
            
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    // Track background
                    HStack(spacing: 0) {
                        // Starting station
                        Circle()
                            .fill(Color.white.opacity(0.4))
                            .frame(width: 8, height: 8)
                        
                        // Track
                        Rectangle()
                            .fill(Color.white.opacity(0.2))
                            .frame(height: 2)
                        
                        // Ending station
                        Circle()
                            .fill(Color.white.opacity(0.4))
                            .frame(width: 8, height: 8)
                    }
                    
                    // Progress track
                    HStack(spacing: 0) {
                        Circle()
                            .fill(TrackRatTheme.Colors.accent)
                            .frame(width: 8, height: 8)
                        
                        Rectangle()
                            .fill(TrackRatTheme.Colors.accent)
                            .frame(width: max(0, (geometry.size.width - 16) * animatedProgress), height: 2)
                        
                        Spacer()
                    }
                    
                    // Animated train at progress position
                    if showTrain {
                        RoundedRectangle(cornerRadius: 4)
                            .fill(TrackRatTheme.Colors.accent)
                            .frame(width: 24, height: 16)
                            .overlay(
                                HStack(spacing: 2) {
                                    ForEach(0..<2) { _ in
                                        RoundedRectangle(cornerRadius: 1)
                                            .fill(Color.yellow.opacity(0.8))
                                            .frame(width: 4, height: 3)
                                    }
                                }
                            )
                            .shadow(color: TrackRatTheme.Colors.accent.opacity(0.6), radius: 4)
                            .offset(x: max(0, min(geometry.size.width - 24, (geometry.size.width - 16) * animatedProgress)))
                    }
                }
            }
            .frame(height: 20)
            
            // Progress percentage with encouraging message
            if progress > 0 && progress < 1 {
                Text("\(Int(progress * 100))% there! Keep racing! 🏃‍♂️")
                    .font(TrackRatTheme.Typography.caption)
                    .foregroundColor(TrackRatTheme.Colors.accent)
            } else if progress >= 1 {
                Text("You made it! 🎉")
                    .font(TrackRatTheme.Typography.caption)
                    .foregroundColor(.green)
            }
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 0.8)) {
                animatedProgress = progress
                showTrain = true
            }
        }
        .onChange(of: progress) { oldValue, newProgress in
            withAnimation(.easeInOut(duration: 0.5)) {
                animatedProgress = newProgress
            }
        }
    }
}

#Preview("Rat Race Loading") {
    ZStack {
        TrackRatTheme.Colors.primaryBackground
            .ignoresSafeArea()
        
        VStack(spacing: 40) {
            RatRaceLoadingView(message: "Racing to find your train...")
            RatRaceLoadingView(message: "Almost at the platform...")
            CompactRatRaceView()
        }
    }
}

#Preview("Rat Race Progress") {
    ZStack {
        TrackRatTheme.Colors.surface.ignoresSafeArea()
        
        VStack(spacing: 30) {
            RatRaceProgressView(progress: 0.0, fromStation: "NY", toStation: "NP")
            RatRaceProgressView(progress: 0.3, fromStation: "NY", toStation: "TR")
            RatRaceProgressView(progress: 0.7, fromStation: "NP", toStation: "PJ")
            RatRaceProgressView(progress: 1.0, fromStation: "TR", toStation: "NY")
        }
        .padding()
    }
}