import SwiftUI

enum MascotStyle {
    case compact    // Small icon for inline use
    case standard   // Medium size for headers
    case hero       // Large animated version
    case racing     // Animated with motion lines
}

struct TrackRatMascot: View {
    let style: MascotStyle
    @State private var isAnimating = false
    @State private var pulse: CGFloat = 1.0
    
    var body: some View {
        switch style {
        case .compact:
            compactMascot
        case .standard:
            standardMascot
        case .hero:
            heroMascot
        case .racing:
            racingMascot
        }
    }
    
    // MARK: - Compact Version (for inline use, navigation bars, etc.)
    private var compactMascot: some View {
        ZStack {
            // Mini train car
            RoundedRectangle(cornerRadius: 4)
                .fill(TrackRatTheme.Colors.accent)
                .frame(width: 20, height: 14)
                .overlay(
                    // Windows
                    HStack(spacing: 2) {
                        RoundedRectangle(cornerRadius: 1)
                            .fill(Color.yellow.opacity(0.8))
                            .frame(width: 4, height: 4)
                        RoundedRectangle(cornerRadius: 1)
                            .fill(Color.yellow.opacity(0.8))
                            .frame(width: 4, height: 4)
                    }
                )
                .shadow(color: TrackRatTheme.Colors.accent.opacity(0.3), radius: 2)
        }
    }
    
    // MARK: - Standard Version (for headers, empty states)
    private var standardMascot: some View {
        ZStack {
            // Glow effect
            Circle()
                .fill(TrackRatTheme.Colors.accent.opacity(0.2))
                .frame(width: 60, height: 60)
                .blur(radius: 10)
                .scaleEffect(pulse)
            
            // Modern train representation
            VStack(spacing: 0) {
                // Train with commuter theme
                ZStack {
                    // Train body
                    RoundedRectangle(cornerRadius: 8)
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
                        .frame(width: 40, height: 28)
                        .overlay(
                            // Windows with commuters
                            HStack(spacing: 3) {
                                ForEach(0..<3) { _ in
                                    RoundedRectangle(cornerRadius: 2)
                                        .fill(Color.yellow.opacity(0.9))
                                        .frame(width: 8, height: 10)
                                        .overlay(
                                            Image(systemName: "person.fill")
                                                .font(.system(size: 5))
                                                .foregroundColor(.black.opacity(0.3))
                                        )
                                }
                            }
                        )
                        .shadow(color: TrackRatTheme.Colors.accent.opacity(0.6), radius: 6)
                    
                    // Headlight
                    Circle()
                        .fill(Color.yellow)
                        .frame(width: 5, height: 5)
                        .offset(x: 20)
                        .blur(radius: 0.5)
                }
                
                // Simple track indicator
                HStack(spacing: 2) {
                    Rectangle()
                        .fill(Color.white.opacity(0.3))
                        .frame(width: 50, height: 2)
                }
                .padding(.top, 4)
            }
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 2.0).repeatForever(autoreverses: true)) {
                pulse = 1.2
            }
        }
    }
    
    // MARK: - Hero Version (for launch screen, major features)
    private var heroMascot: some View {
        ZStack {
            // Animated background glow
            ForEach(0..<3) { i in
                Circle()
                    .fill(TrackRatTheme.Colors.accent.opacity(0.1))
                    .frame(width: 100 + CGFloat(i * 20), height: 100 + CGFloat(i * 20))
                    .blur(radius: 10)
                    .scaleEffect(isAnimating ? 1.2 : 0.8)
                    .animation(
                        .easeInOut(duration: 2.0 + Double(i) * 0.5)
                            .repeatForever(autoreverses: true),
                        value: isAnimating
                    )
            }
            
            VStack(spacing: 8) {
                // Premium train design
                ZStack {
                    // Train shadow
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color.black.opacity(0.2))
                        .frame(width: 64, height: 40)
                        .offset(y: 2)
                        .blur(radius: 4)
                    
                    // Main train body
                    RoundedRectangle(cornerRadius: 12)
                        .fill(
                            LinearGradient(
                                gradient: Gradient(colors: [
                                    TrackRatTheme.Colors.accent.opacity(0.9),
                                    TrackRatTheme.Colors.accent
                                ]),
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .frame(width: 60, height: 36)
                        .overlay(
                            // Premium windows
                            HStack(spacing: 4) {
                                ForEach(0..<3) { i in
                                    RoundedRectangle(cornerRadius: 3)
                                        .fill(
                                            LinearGradient(
                                                gradient: Gradient(colors: [
                                                    Color.yellow,
                                                    Color.yellow.opacity(0.7)
                                                ]),
                                                startPoint: .top,
                                                endPoint: .bottom
                                            )
                                        )
                                        .frame(width: 12, height: 14)
                                        .overlay(
                                            VStack(spacing: 1) {
                                                Image(systemName: "person.fill")
                                                    .font(.system(size: 6))
                                                Image(systemName: "briefcase.fill")
                                                    .font(.system(size: 4))
                                            }
                                            .foregroundColor(.black.opacity(0.3))
                                        )
                                }
                            }
                        )
                        .overlay(
                            // Front design element
                            HStack {
                                Spacer()
                                Circle()
                                    .fill(Color.white.opacity(0.8))
                                    .frame(width: 8, height: 8)
                                    .overlay(
                                        Circle()
                                            .fill(Color.yellow)
                                            .frame(width: 6, height: 6)
                                    )
                                    .shadow(color: .yellow, radius: 4)
                            }
                            .padding(.horizontal, 2)
                        )
                    
                    // Speed lines
                    if isAnimating {
                        HStack(spacing: 2) {
                            ForEach(0..<3) { i in
                                Rectangle()
                                    .fill(
                                        LinearGradient(
                                            gradient: Gradient(colors: [
                                                Color.white.opacity(0.5 - Double(i) * 0.15),
                                                Color.clear
                                            ]),
                                            startPoint: .leading,
                                            endPoint: .trailing
                                        )
                                    )
                                    .frame(width: 20 - CGFloat(i * 5), height: 2)
                                    .offset(x: -30 - CGFloat(i * 8))
                            }
                        }
                    }
                }
                .rotationEffect(.degrees(isAnimating ? -2 : 2))
                .animation(
                    .easeInOut(duration: 1.5).repeatForever(autoreverses: true),
                    value: isAnimating
                )
                
                // Stylized tracks
                ZStack {
                    // Track bed
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.white.opacity(0.1))
                        .frame(width: 80, height: 8)
                    
                    // Rails
                    VStack(spacing: 2) {
                        Rectangle()
                            .fill(
                                LinearGradient(
                                    gradient: Gradient(colors: [
                                        Color.white.opacity(0.2),
                                        Color.white.opacity(0.5),
                                        Color.white.opacity(0.2)
                                    ]),
                                    startPoint: .leading,
                                    endPoint: .trailing
                                )
                            )
                            .frame(width: 80, height: 2)
                        
                        Rectangle()
                            .fill(
                                LinearGradient(
                                    gradient: Gradient(colors: [
                                        Color.white.opacity(0.2),
                                        Color.white.opacity(0.5),
                                        Color.white.opacity(0.2)
                                    ]),
                                    startPoint: .leading,
                                    endPoint: .trailing
                                )
                            )
                            .frame(width: 80, height: 2)
                    }
                }
            }
        }
        .onAppear {
            isAnimating = true
        }
    }
    
    // MARK: - Racing Version (for loading states)
    private var racingMascot: some View {
        HStack(spacing: 0) {
            // Fast-moving train
            ZStack {
                // Motion blur effect
                RoundedRectangle(cornerRadius: 6)
                    .fill(TrackRatTheme.Colors.accent.opacity(0.3))
                    .frame(width: 35, height: 20)
                    .blur(radius: 2)
                    .offset(x: -5)
                
                // Main train
                RoundedRectangle(cornerRadius: 6)
                    .fill(TrackRatTheme.Colors.accent)
                    .frame(width: 32, height: 20)
                    .overlay(
                        HStack(spacing: 2) {
                            RoundedRectangle(cornerRadius: 1)
                                .fill(Color.yellow.opacity(0.9))
                                .frame(width: 6, height: 6)
                            RoundedRectangle(cornerRadius: 1)
                                .fill(Color.yellow.opacity(0.9))
                                .frame(width: 6, height: 6)
                            RoundedRectangle(cornerRadius: 1)
                                .fill(Color.yellow.opacity(0.9))
                                .frame(width: 6, height: 6)
                        }
                    )
                    .shadow(color: TrackRatTheme.Colors.accent.opacity(0.8), radius: 4)
            }
            .offset(x: isAnimating ? 50 : -50)
            
            // Speed lines
            if isAnimating {
                HStack(spacing: 1) {
                    ForEach(0..<4) { i in
                        Rectangle()
                            .fill(Color.white.opacity(0.5 - Double(i) * 0.1))
                            .frame(width: 15 - CGFloat(i * 3), height: 1)
                            .offset(x: -5 - CGFloat(i * 3))
                    }
                }
                .transition(.opacity)
            }
        }
        .frame(width: 120)
        .onAppear {
            withAnimation(.easeInOut(duration: 1.5).repeatForever(autoreverses: true)) {
                isAnimating = true
            }
        }
    }
}

// MARK: - Icon-only version for use in navigation bars, buttons, etc.
struct TrackRatIcon: View {
    let size: CGFloat
    
    var body: some View {
        Image(systemName: "tram.fill")
            .font(.system(size: size * 0.6, weight: .medium))
            .foregroundColor(.white)
            .frame(width: size, height: size)
            .background(
                RoundedRectangle(cornerRadius: size * 0.25)
                    .fill(TrackRatTheme.Colors.accent)
            )
            .shadow(color: TrackRatTheme.Colors.accent.opacity(0.3), radius: 2)
    }
}

// MARK: - Animated app icon for special occasions
struct AnimatedTrackRatIcon: View {
    @State private var rotation: Double = 0
    @State private var scale: CGFloat = 1.0
    
    var body: some View {
        TrackRatIcon(size: 60)
            .rotationEffect(.degrees(rotation))
            .scaleEffect(scale)
            .onAppear {
                withAnimation(.linear(duration: 20).repeatForever(autoreverses: false)) {
                    rotation = 360
                }
                withAnimation(.easeInOut(duration: 2).repeatForever(autoreverses: true)) {
                    scale = 1.1
                }
            }
    }
}

#Preview("All Mascot Styles") {
    ZStack {
        Color.black.ignoresSafeArea()
        
        VStack(spacing: 40) {
            VStack(spacing: 10) {
                Text("Compact")
                    .foregroundColor(.white)
                TrackRatMascot(style: .compact)
            }
            
            VStack(spacing: 10) {
                Text("Standard")
                    .foregroundColor(.white)
                TrackRatMascot(style: .standard)
            }
            
            VStack(spacing: 10) {
                Text("Hero")
                    .foregroundColor(.white)
                TrackRatMascot(style: .hero)
            }
            
            VStack(spacing: 10) {
                Text("Racing")
                    .foregroundColor(.white)
                TrackRatMascot(style: .racing)
            }
            
            VStack(spacing: 10) {
                Text("Icons")
                    .foregroundColor(.white)
                HStack(spacing: 20) {
                    TrackRatIcon(size: 30)
                    TrackRatIcon(size: 40)
                    AnimatedTrackRatIcon()
                }
            }
        }
    }
}