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
                    // Profile image
                    Image("my-profile")
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(maxWidth: 200, maxHeight: 200)
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                        .shadow(color: .black.opacity(0.3), radius: 8, x: 0, y: 4)
                    
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