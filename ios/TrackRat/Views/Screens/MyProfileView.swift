import SwiftUI

struct MyProfileView: View {
    @EnvironmentObject private var appState: AppState
    @EnvironmentObject private var themeManager: ThemeManager
    @Environment(\.openURL) private var openURL
    @State private var showOnboarding = false
    
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
                        Text("Profile (& Points) Coming Soon...")
                            .font(.title2)
                            .fontWeight(.medium)
                            .foregroundColor(.white)
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                    .frame(maxWidth: .infinity)
                    
                    // Settings & Support section
                    VStack(spacing: 16) {
                        // Section header
                        HStack {
                            Text("Settings & Support")
                                .font(.headline)
                                .fontWeight(.semibold)
                                .foregroundColor(.white)
                            Spacer()
                        }
                        .padding(.horizontal)
                        
                        // Favorite Stations
                        Button {
                            appState.navigationPath.append(NavigationDestination.favoriteStations)
                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        } label: {
                            HStack(spacing: 16) {
                                Image(systemName: "heart.fill")
                                    .font(.title2)
                                    .foregroundColor(.orange)
                                    .frame(width: 24, height: 24)
                                
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("Favorite Stations")
                                        .font(.headline)
                                        .fontWeight(.medium)
                                        .foregroundColor(.white)
                                        .multilineTextAlignment(.leading)
                                    
                                    Text("Manage your quick access stations")
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.7))
                                        .multilineTextAlignment(.leading)
                                }
                                
                                Spacer()
                                
                                Image(systemName: "chevron.right")
                                    .font(.caption)
                                    .foregroundColor(.white.opacity(0.5))
                            }
                            .padding()
                            .frame(maxWidth: .infinity)
                            .background(
                                RoundedRectangle(cornerRadius: 12)
                                    .fill(.ultraThinMaterial)
                            )
                        }
                        
                        // Repeat Onboarding
                        Button {
                            showOnboarding = true
                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        } label: {
                            HStack(spacing: 16) {
                                Image(systemName: "arrow.clockwise")
                                    .font(.title2)
                                    .foregroundColor(.orange)
                                    .frame(width: 24, height: 24)
                                
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("Repeat Onboarding")
                                        .font(.headline)
                                        .fontWeight(.medium)
                                        .foregroundColor(.white)
                                        .multilineTextAlignment(.leading)
                                    
                                    Text("Go through the welcome flow again")
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.7))
                                        .multilineTextAlignment(.leading)
                                }
                                
                                Spacer()
                                
                                Image(systemName: "chevron.right")
                                    .font(.caption)
                                    .foregroundColor(.white.opacity(0.5))
                            }
                            .padding()
                            .frame(maxWidth: .infinity)
                            .background(
                                RoundedRectangle(cornerRadius: 12)
                                    .fill(.ultraThinMaterial)
                            )
                        }
                        
                        // Advanced Configuration
                        Button {
                            appState.navigationPath.append(NavigationDestination.advancedConfiguration)
                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        } label: {
                            HStack(spacing: 16) {
                                Image(systemName: "gearshape.fill")
                                    .font(.title2)
                                    .foregroundColor(.orange)
                                    .frame(width: 24, height: 24)
                                
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("Advanced Configuration")
                                        .font(.headline)
                                        .fontWeight(.medium)
                                        .foregroundColor(.white)
                                        .multilineTextAlignment(.leading)
                                    
                                    Text("Server settings & health checks")
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.7))
                                        .multilineTextAlignment(.leading)
                                }
                                
                                Spacer()
                                
                                Image(systemName: "chevron.right")
                                    .font(.caption)
                                    .foregroundColor(.white.opacity(0.5))
                            }
                            .padding()
                            .frame(maxWidth: .infinity)
                            .background(
                                RoundedRectangle(cornerRadius: 12)
                                    .fill(.ultraThinMaterial)
                            )
                        }
                        
                        // Report Issues & Request Features
                        Button {
                            if let signalURL = URL(string: "https://signal.me/#eu/iG3LNnu-IycTUbwrWF1nwrlR-u-TN5gtBO0tXtJk3Nder7TtfzFPa6On6N9dl3e-") {
                                openURL(signalURL)
                                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                            }
                        } label: {
                            HStack(spacing: 16) {
                                Image(systemName: "exclamationmark.bubble.fill")
                                    .font(.title2)
                                    .foregroundColor(.orange)
                                    .frame(width: 24, height: 24)
                                
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("Report Issues & Request Features")
                                        .font(.headline)
                                        .fontWeight(.medium)
                                        .foregroundColor(.white)
                                        .multilineTextAlignment(.leading)
                                    
                                    Text("Get help via Signal messenger")
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.7))
                                        .multilineTextAlignment(.leading)
                                }
                                
                                Spacer()
                                
                                Image(systemName: "arrow.up.right")
                                    .font(.caption)
                                    .foregroundColor(.white.opacity(0.5))
                            }
                            .padding()
                            .frame(maxWidth: .infinity)
                            .background(
                                RoundedRectangle(cornerRadius: 12)
                                    .fill(.ultraThinMaterial)
                            )
                        }
                    }
                }
                .padding()
                .padding(.bottom, 40)
            }
        }
        .fullScreenCover(isPresented: $showOnboarding) {
            OnboardingView(isRepeating: true)
                .environmentObject(appState)
        }
    }
}

#Preview {
    NavigationView {
        MyProfileView()
            .environmentObject(AppState())
            .environmentObject(ThemeManager.shared)
    }
}
