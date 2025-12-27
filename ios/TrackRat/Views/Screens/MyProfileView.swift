import SwiftUI

struct MyProfileView: View {
    @EnvironmentObject private var appState: AppState
    @EnvironmentObject private var themeManager: ThemeManager
    @Environment(\.openURL) private var openURL

    var body: some View {
        VStack(spacing: 0) {
            // Fixed header - replaces system navigation bar to avoid layout shift
            HStack {
                // Back button
                Button {
                    if !appState.navigationPath.isEmpty {
                        appState.navigationPath.removeLast()
                    }
                } label: {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(.white)
                        .frame(width: 44, height: 44)
                }

                Spacer()

                // Center title
                Text("My Profile")
                    .font(.headline)
                    .foregroundColor(.white)

                Spacer()

                // Spacer for symmetry (same width as back button)
                Color.clear
                    .frame(width: 44, height: 44)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 8)
            .background(.ultraThinMaterial)

            // Scrollable content
            ScrollView {
                VStack(spacing: 24) {
                    // Feedback & Ideas section
                    VStack(spacing: 16) {
                        // Section header
                        HStack {
                            Text("Feedback & Ideas")
                                .font(.headline)
                                .fontWeight(.semibold)
                                .foregroundColor(.white)
                            Spacer()
                        }
                        .padding(.horizontal)

                        // Submit Feedback
                        Button {
                            if let feedbackURL = URL(string: "https://trackrat.nolt.io/") {
                                openURL(feedbackURL)
                                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                            }
                        } label: {
                            HStack(spacing: 16) {
                                Image(systemName: "lightbulb.fill")
                                    .font(.title2)
                                    .foregroundColor(.orange)
                                    .frame(width: 24, height: 24)

                                VStack(alignment: .leading, spacing: 4) {
                                    Text("Submit Feedback")
                                        .font(.headline)
                                        .fontWeight(.medium)
                                        .foregroundColor(.white)
                                        .multilineTextAlignment(.leading)

                                    Text("Send bugs and ideas for new features")
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

                    // Profile image - aligned to top
                    // VStack {
                    //     Image("my-profile")
                    //         .resizable()
                    //         .aspectRatio(contentMode: .fit)
                    //         .frame(maxWidth: 200, maxHeight: 200)
                    //         .clipShape(RoundedRectangle(cornerRadius: 16))
                    //         .shadow(color: .black.opacity(0.3), radius: 8, x: 0, y: 4)
                    // }
                    // .padding(.top, 0)
                    
                    // Profile section
                    // VStack(spacing: 16) {
                    //     // My Profile card
                    //     HStack(spacing: 16) {
                    //         Image(systemName: "person.fill")
                    //             .font(.title2)
                    //             .foregroundColor(.orange)
                    //             .frame(width: 24, height: 24)
                    //         
                    //         VStack(alignment: .leading, spacing: 4) {
                    //             Text("My Profile")
                    //                 .font(.headline)
                    //                 .fontWeight(.medium)
                    //                 .foregroundColor(.white)
                    //                 .multilineTextAlignment(.leading)
                    //             
                    //             Text("Coming soon...")
                    //                 .font(.caption)
                    //                 .foregroundColor(.white.opacity(0.7))
                    //                 .multilineTextAlignment(.leading)
                    //         }
                    //         
                    //         Spacer()
                    //     }
                    //     .padding()
                    //     .frame(maxWidth: .infinity)
                    //     .background(
                    //         RoundedRectangle(cornerRadius: 12)
                    //             .fill(.ultraThinMaterial)
                    //     )
                    //     
                    //     // Reward Points card
                    //     HStack(spacing: 16) {
                    //         Image(systemName: "star.fill")
                    //             .font(.title2)
                    //             .foregroundColor(.orange)
                    //             .frame(width: 24, height: 24)
                    //         
                    //         VStack(alignment: .leading, spacing: 4) {
                    //             Text("Reward Points (Cheese)")
                    //                 .font(.headline)
                    //                 .fontWeight(.medium)
                    //                 .foregroundColor(.white)
                    //                 .multilineTextAlignment(.leading)
                    //             
                    //             Text("Coming soon...")
                    //                 .font(.caption)
                    //                 .foregroundColor(.white.opacity(0.7))
                    //                 .multilineTextAlignment(.leading)
                    //         }
                    //         
                    //         Spacer()
                    //     }
                    //     .padding()
                    //     .frame(maxWidth: .infinity)
                    //     .background(
                    //         RoundedRectangle(cornerRadius: 12)
                    //             .fill(.ultraThinMaterial)
                    //     )
                    // }
                    
                    // Settings section
                    VStack(spacing: 16) {
                        // Section header
                        HStack {
                            Text("Community")
                                .font(.headline)
                                .fontWeight(.semibold)
                                .foregroundColor(.white)
                            Spacer()
                        }
                        .padding(.horizontal)
                         // Follow our YouTube Channel
                        Button {
                            if let youtubeURL = URL(string: "https://www.youtube.com/@TrackRat-App/shorts") {
                                openURL(youtubeURL)
                                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                            }
                        } label: {
                            HStack(spacing: 16) {
                                Image(systemName: "play.rectangle.fill")
                                    .font(.title2)
                                    .foregroundColor(.orange)
                                    .frame(width: 24, height: 24)
                                
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("YouTube Channel")
                                        .font(.headline)
                                        .fontWeight(.medium)
                                        .foregroundColor(.white)
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
                    
                        // Instagram
                        Button {
                            if let instagramURL = URL(string: "https://www.instagram.com/trackratapp/") {
                                openURL(instagramURL)
                                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                            }
                        } label: {
                            HStack(spacing: 16) {
                                Image(systemName: "camera.fill")
                                    .font(.title2)
                                    .foregroundColor(.orange)
                                    .frame(width: 24, height: 24)

                                VStack(alignment: .leading, spacing: 4) {
                                    Text("Instagram")
                                        .font(.headline)
                                        .fontWeight(.medium)
                                        .foregroundColor(.white)
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

                    // Service Alerts section
                    VStack(spacing: 16) {
                        // Section header
                        HStack {
                            Text("Service Alerts")
                                .font(.headline)
                                .fontWeight(.semibold)
                                .foregroundColor(.white)
                            Spacer()
                        }
                        .padding(.horizontal)

                        // NJ Transit Advisories
                        Button {
                            if let url = URL(string: "https://www.njtransit.com/travel-alerts-to") {
                                openURL(url)
                                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                            }
                        } label: {
                            HStack(spacing: 16) {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .font(.title2)
                                    .foregroundColor(.orange)
                                    .frame(width: 24, height: 24)

                                VStack(alignment: .leading, spacing: 4) {
                                    Text("NJ Transit Advisories")
                                        .font(.headline)
                                        .fontWeight(.medium)
                                        .foregroundColor(.white)
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

                        // Amtrak Service Alerts
                        Button {
                            if let url = URL(string: "https://www.amtrak.com/service-alerts-and-notices") {
                                openURL(url)
                                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                            }
                        } label: {
                            HStack(spacing: 16) {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .font(.title2)
                                    .foregroundColor(.orange)
                                    .frame(width: 24, height: 24)

                                VStack(alignment: .leading, spacing: 4) {
                                    Text("Amtrak Service Alerts")
                                        .font(.headline)
                                        .fontWeight(.medium)
                                        .foregroundColor(.white)
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

                    // Settings section
                    VStack(spacing: 16) {
                        // Section header
                        HStack {
                            Text("Settings")
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
                                    Text("Edit Favorite Stations")
                                        .font(.headline)
                                        .fontWeight(.medium)
                                        .foregroundColor(.white)
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
                    }

                // Report an issue
                FeedbackButton(
                    screen: "my_profile",
                    trainId: nil,
                    originCode: nil,
                    destinationCode: nil
                )
                .padding(.top, 8)
                }
                .padding()
                .padding(.bottom, 40)
            }
        }
        .navigationBarHidden(true)
    }
}

#Preview {
    NavigationStack {
        MyProfileView()
            .environmentObject(AppState())
            .environmentObject(ThemeManager.shared)
    }
}
