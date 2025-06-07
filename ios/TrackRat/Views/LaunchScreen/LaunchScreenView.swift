import SwiftUI

struct LaunchScreenView: View {
    @State private var logoScale: CGFloat = 0.8
    @State private var logoOpacity: Double = 0
    @State private var titleOffset: CGFloat = 30
    @State private var titleOpacity: Double = 0
    @State private var ratOffset: CGFloat = -50
    @State private var ratOpacity: Double = 0
    
    let onComplete: () -> Void
    
    var body: some View {
        ZStack {
            // Black gradient background
            TrackRatTheme.Colors.primaryGradient
                .ignoresSafeArea()
            
            VStack(spacing: TrackRatTheme.Spacing.xl) {
                Spacer()
                
                // Animated TrackRat mascot (using tram icon for now)
                VStack(spacing: TrackRatTheme.Spacing.lg) {
                    // Rat mascot with train tracks
                    ZStack {
                        // Train tracks background
                        VStack(spacing: 4) {
                            Rectangle()
                                .fill(Color.white.opacity(0.3))
                                .frame(height: 2)
                            Rectangle()
                                .fill(Color.white.opacity(0.3))
                                .frame(height: 2)
                        }
                        .frame(width: 150)
                        
                        // Rat emoji running along tracks
                        HStack {
                            Text("🐀")
                                .font(.system(size: 40))
                                .scaleEffect(logoScale)
                                .opacity(logoOpacity)
                                .offset(x: ratOffset)
                            
                            Spacer()
                        }
                        .frame(width: 150)
                    }
                    
                    // App title
                    VStack(spacing: TrackRatTheme.Spacing.sm) {
                        Text("TrackRat")
                            .font(TrackRatTheme.Typography.title1)
                            .foregroundColor(.white)
                            .offset(y: titleOffset)
                            .opacity(titleOpacity)
                        
                        Text("Smart Train Tracking")
                            .font(TrackRatTheme.Typography.body)
                            .foregroundColor(.white.opacity(0.8))
                            .offset(y: titleOffset)
                            .opacity(titleOpacity)
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
        // Rat running animation
        withAnimation(.easeInOut(duration: 1.0)) {
            ratOffset = 50
            ratOpacity = 1.0
        }
        
        // Logo scale animation
        withAnimation(.spring(response: 0.8, dampingFraction: 0.6).delay(0.3)) {
            logoScale = 1.0
            logoOpacity = 1.0
        }
        
        // Title animation (delayed)
        withAnimation(.easeInOut(duration: 0.8).delay(0.8)) {
            titleOffset = 0
            titleOpacity = 1.0
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