import SwiftUI

struct TrackRatLoadingView: View {
    let message: String
    
    init(message: String = "Loading...") {
        self.message = message
    }
    
    var body: some View {
        VStack(spacing: TrackRatTheme.Spacing.lg) {
            // Use our new racing mascot
            TrackRatMascot(style: .racing)
                .frame(height: 40)
            
            Text(message)
                .font(TrackRatTheme.Typography.body)
                .foregroundColor(TrackRatTheme.Colors.onSurfaceSecondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, minHeight: 200)
    }
}

struct PulsingTrackRatView: View {
    var body: some View {
        TrackRatMascot(style: .standard)
            .frame(width: 60, height: 60)
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
                
                // Train icon at progress position
                if animatedProgress > 0 {
                    TrackRatMascot(style: .compact)
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
        TrackRatTheme.Colors.surface
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
    .background(TrackRatTheme.Colors.surface)
}