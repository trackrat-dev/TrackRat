import SwiftUI

struct TrackRatLoadingView: View {
    @State private var isAnimating = false
    @State private var ratPosition: CGFloat = 0
    let message: String
    
    init(message: String = "Loading...") {
        self.message = message
    }
    
    var body: some View {
        VStack(spacing: TrackRatTheme.Spacing.lg) {
            // Animated rat running on tracks
            ZStack {
                // Train tracks
                VStack(spacing: 6) {
                    Rectangle()
                        .fill(Color.white.opacity(0.3))
                        .frame(height: 2)
                    Rectangle()
                        .fill(Color.white.opacity(0.3))
                        .frame(height: 2)
                }
                .frame(width: 120)
                
                // Rat running along tracks
                HStack {
                    Text("🐀")
                        .font(.system(size: 24))
                        .offset(x: ratPosition)
                    
                    Spacer()
                }
                .frame(width: 120)
            }
            .onAppear {
                withAnimation(.linear(duration: 2).repeatForever(autoreverses: true)) {
                    ratPosition = isAnimating ? -40 : 40
                }
                isAnimating.toggle()
            }
            
            Text(message)
                .font(TrackRatTheme.Typography.body)
                .foregroundColor(TrackRatTheme.Colors.onSurfaceSecondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, minHeight: 200)
    }
}

struct PulsingTrackRatView: View {
    @State private var isPulsing = false
    
    var body: some View {
        Text("🐀")
            .font(.title2)
            .scaleEffect(isPulsing ? 1.2 : 0.8)
            .opacity(isPulsing ? 0.6 : 1.0)
            .animation(
                .easeInOut(duration: 1.0)
                .repeatForever(autoreverses: true),
                value: isPulsing
            )
            .onAppear {
                isPulsing = true
            }
    }
}

struct TrackRatProgressView: View {
    let progress: Double
    @State private var animatedProgress: Double = 0
    
    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                // Background track
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.white.opacity(0.2))
                    .frame(height: 8)
                
                // Progress track
                RoundedRectangle(cornerRadius: 4)
                    .fill(TrackRatTheme.Colors.accent)
                    .frame(width: geometry.size.width * animatedProgress, height: 8)
                
                // Rat icon at progress position
                if animatedProgress > 0 {
                    Text("🐀")
                        .font(.caption)
                        .offset(x: max(0, min(geometry.size.width - 20, geometry.size.width * animatedProgress - 10)))
                }
            }
        }
        .frame(height: 20)
        .onAppear {
            withAnimation(.easeInOut(duration: 0.5)) {
                animatedProgress = progress
            }
        }
        .onChange(of: progress) { oldValue, newProgress in
            withAnimation(.easeInOut(duration: 0.3)) {
                animatedProgress = newProgress
            }
        }
    }
}

#Preview("TrackRat Loading") {
    ZStack {
        TrackRatTheme.Colors.primaryGradient
            .ignoresSafeArea()
        
        TrackRatLoadingView(message: "Finding your trains...")
    }
}

#Preview("Pulsing TrackRat") {
    ZStack {
        Color.black
        PulsingTrackRatView()
    }
}

#Preview("TrackRat Progress") {
    VStack(spacing: 20) {
        TrackRatProgressView(progress: 0.3)
        TrackRatProgressView(progress: 0.7)
        TrackRatProgressView(progress: 1.0)
    }
    .padding()
    .background(Color.black)
}