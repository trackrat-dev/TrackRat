import SwiftUI

struct MyProfileView: View {
    @EnvironmentObject private var appState: AppState
    @EnvironmentObject private var themeManager: ThemeManager
    
    var body: some View {
        let backgroundView = TrackRatTheme.Colors.primaryBackground
            .ignoresSafeArea()
        
        return ZStack {
            backgroundView
            
            ScrollView {
                VStack(spacing: 24) {
                    // Coming Soon content
                    VStack(spacing: 16) {
                        Text("Coming Soon...")
                            .font(.title2)
                            .fontWeight(.medium)
                            .foregroundColor(.white)
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                    .frame(maxWidth: .infinity)
                }
                .padding()
                .padding(.bottom, 40)
            }
        }
        .navigationTitle("My Profile")
        .navigationBarTitleDisplayMode(.inline)
    }
}

#Preview {
    NavigationView {
        MyProfileView()
            .environmentObject(AppState())
            .environmentObject(ThemeManager.shared)
    }
}