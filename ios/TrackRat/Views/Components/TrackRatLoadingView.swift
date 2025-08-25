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

#Preview("TrackRat Loading") {
    ZStack {
        TrackRatTheme.Colors.primaryBackground
            .ignoresSafeArea()
        
        TrackRatLoadingView(message: "Finding your trains...")
    }
}
