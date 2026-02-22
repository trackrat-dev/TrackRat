import SwiftUI

// MARK: - Profile Navigation
enum ProfileDestination: Hashable {
    case tripHistory
    case favoriteStations
    case routeAlerts
    case advancedConfiguration
}

struct MyProfileView: View {
    @EnvironmentObject private var appState: AppState
    @EnvironmentObject private var themeManager: ThemeManager
    @Environment(\.openURL) private var openURL
    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var subscriptionService = SubscriptionService.shared

    @State private var showingPaywall = false
    @State private var showingFeedbackSheet = false
    @State private var paywallContext: PaywallContext = .generic
    @State private var navigationPath = NavigationPath()

    var body: some View {
        NavigationStack(path: $navigationPath) {
            VStack(spacing: 0) {
                // Fixed header with close button for sheet presentation
                HStack {
                    // Spacer for symmetry (same width as close button)
                    Color.clear
                        .frame(width: 44, height: 44)

                Spacer()

                // Center title with Pro badge
                HStack(spacing: 8) {
                    Text("My Profile")
                        .font(.headline)
                        .foregroundColor(.white)

                    if subscriptionService.isPro {
                        HStack(spacing: 4) {
                            Image(systemName: "star.fill")
                                .font(.caption2)
                            Text("PRO")
                                .font(.caption2.bold())
                        }
                        .foregroundColor(.orange)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(
                            Capsule()
                                .fill(.orange.opacity(0.2))
                        )
                    }
                }

                Spacer()

                // Close button
                Button {
                    dismiss()
                } label: {
                    Image(systemName: "xmark")
                        .font(TrackRatTheme.IconSize.small)
                        .foregroundColor(.white)
                        .frame(minWidth: 44, minHeight: 44)
                }
                }
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 8)

            // Scrollable content
            ScrollView {
                VStack(spacing: 24) {
                    // Subscription Section (includes soft trial state)
                    SubscriptionStatusSection(
                        subscriptionService: subscriptionService,
                        showingPaywall: $showingPaywall
                    )

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
                    SettingsSection(
                        subscriptionService: subscriptionService,
                        navigationPath: $navigationPath,
                        showingPaywall: $showingPaywall
                    )

                    // Community section
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

                        // YouTube Channel
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
                        .buttonStyle(.plain)

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
                        .buttonStyle(.plain)
                    }

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

                                    Text("Send ideas for new features")
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
                        .buttonStyle(.plain)

                        // Report an Issue
                        Button {
                            showingFeedbackSheet = true
                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        } label: {
                            HStack(spacing: 16) {
                                Image(systemName: "exclamationmark.bubble.fill")
                                    .font(.title2)
                                    .foregroundColor(.orange)
                                    .frame(width: 24, height: 24)

                                VStack(alignment: .leading, spacing: 4) {
                                    Text("Report an Issue")
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
                        .buttonStyle(.plain)
                        .sheet(isPresented: $showingFeedbackSheet) {
                            FeedbackSheet(
                                screen: "my_profile",
                                trainId: nil,
                                originCode: nil,
                                destinationCode: nil
                            )
                        }
                    }
                }
                .padding()
                .padding(.bottom, 40)
            }
            .navigationDestination(for: ProfileDestination.self) { destination in
                Group {
                    switch destination {
                    case .tripHistory:
                        TripHistoryView()
                    case .favoriteStations:
                        OnboardingView(isRepeating: true)
                    case .routeAlerts:
                        EditRouteAlertsView()
                    case .advancedConfiguration:
                        AdvancedConfigurationView()
                    }
                }
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            dismiss()
                        } label: {
                            Image(systemName: "xmark")
                                .font(TrackRatTheme.IconSize.xsmall)
                                .foregroundColor(.white)
                        }
                    }
                }
            }
            .navigationBarHidden(true)
        }
        .sheet(isPresented: $showingPaywall) {
            PaywallView(context: paywallContext)
        }
    }
}

// MARK: - Settings Section

struct SettingsSection: View {
    @EnvironmentObject private var appState: AppState
    @ObservedObject var subscriptionService: SubscriptionService
    @Binding var navigationPath: NavigationPath
    @Binding var showingPaywall: Bool

    var body: some View {
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

            // Train Systems
            VStack(spacing: 0) {
                HStack {
                    Text("Train Systems")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.7))
                    Spacer()
                }
                .padding()

                Divider()
                    .background(Color.white.opacity(0.1))

                ForEach(TrainSystem.allCases, id: \.self) { system in
                    TrainSystemRow(
                        system: system,
                        isSelected: appState.isSystemSelected(system),
                        isLast: system == TrainSystem.allCases.last
                    ) {
                        appState.toggleSystem(system)
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                    }
                }
            }
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(.ultraThinMaterial)
            )

            // Favorite Stations
            Button {
                navigationPath.append(ProfileDestination.favoriteStations)
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
            .buttonStyle(.plain)

            // Route Alerts
            Button {
                navigationPath.append(ProfileDestination.routeAlerts)
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            } label: {
                HStack(spacing: 16) {
                    Image(systemName: "bell.badge.fill")
                        .font(.title2)
                        .foregroundColor(.orange)
                        .frame(width: 24, height: 24)

                    VStack(alignment: .leading, spacing: 4) {
                        Text("Route Alerts")
                            .font(.headline)
                            .fontWeight(.medium)
                            .foregroundColor(.white)
                            .multilineTextAlignment(.leading)

                        Text("Delay & cancellation notifications")
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
            .buttonStyle(.plain)

            // My Trips
            Button {
                if subscriptionService.isPro {
                    navigationPath.append(ProfileDestination.tripHistory)
                } else {
                    showingPaywall = true
                }
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            } label: {
                HStack(spacing: 16) {
                    Image(systemName: "chart.bar.fill")
                        .font(.title2)
                        .foregroundColor(.orange)
                        .frame(width: 24, height: 24)

                    VStack(alignment: .leading, spacing: 4) {
                        Text("My Trips (beta)")
                            .font(.headline)
                            .fontWeight(.medium)
                            .foregroundColor(.white)
                            .multilineTextAlignment(.leading)
                    }

                    Spacer()

                    if !subscriptionService.isPro {
                        HStack(spacing: 4) {
                            Image(systemName: "lock.fill")
                                .font(.caption2)
                            Text("PRO")
                                .font(.caption2.bold())
                        }
                        .foregroundColor(.orange)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(
                            Capsule()
                                .fill(.orange.opacity(0.2))
                        )
                    } else {
                        Image(systemName: "chevron.right")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.5))
                    }
                }
                .padding()
                .frame(maxWidth: .infinity)
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(.ultraThinMaterial)
                )
            }
            .buttonStyle(.plain)

            // Debug/TestFlight-only settings
            if showDebugSections {
            // Advanced Configuration
            Button {
                navigationPath.append(ProfileDestination.advancedConfiguration)
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
            .buttonStyle(.plain)
            }
        }
    }

    /// Shows debug sections in DEBUG builds or TestFlight (but not App Store releases)
    private var showDebugSections: Bool {
        #if DEBUG
        return true
        #else
        guard let url = Bundle.main.appStoreReceiptURL else { return false }
        return url.lastPathComponent == "sandboxReceipt"
        #endif
    }
}

// MARK: - Subscription Status Section

struct SubscriptionStatusSection: View {
    @ObservedObject var subscriptionService: SubscriptionService
    @Binding var showingPaywall: Bool

    @ViewBuilder
    var body: some View {
        if subscriptionService.debugOverrideEnabled {
            // Debug mode - show nothing (silent Pro mode)
            EmptyView()
        } else if subscriptionService.subscriptionStatus.isActive {
            // Actual subscriber (StoreKit trial or paid) - show appreciation
            ProUserCard()
        } else {
            // Not subscribed, no soft trial - show upgrade prompt
            UpgradePromptCard(
                subtext: "Support continued development and get every feature.",
                showingPaywall: $showingPaywall
            )
        }
    }
}

// MARK: - Pro User Card

struct ProUserCard: View {
    @ObservedObject private var subscriptionService = SubscriptionService.shared

    var body: some View {
        VStack(spacing: 12) {
            HStack {
                Image(systemName: "star.fill")
                    .foregroundColor(.orange)
                Text("TrackRat Pro")
                    .font(.headline)
                    .foregroundColor(.white)
                Spacer()
            }

            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Thank you for your support!")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.9))

                    if let expirationText = subscriptionService.subscriptionStatus.expirationText {
                        Text(expirationText)
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.6))
                    }
                    #if DEBUG
                    if subscriptionService.debugOverrideEnabled {
                        Text("Debug mode enabled")
                            .font(.caption)
                            .foregroundColor(.orange.opacity(0.8))
                    }
                    #endif
                }

                Spacer()

                // Manage subscription button
                Button {
                    if let url = URL(string: "https://apps.apple.com/account/subscriptions") {
                        UIApplication.shared.open(url)
                    }
                } label: {
                    Text("Manage")
                        .font(.caption.weight(.medium))
                        .foregroundColor(.orange)
                }
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(
                    LinearGradient(
                        colors: [.orange.opacity(0.15), .orange.opacity(0.05)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(.orange.opacity(0.3), lineWidth: 1)
                )
        )
    }
}

// MARK: - Trip Stats Section

struct TripStatsSection: View {
    let stats: TripStats
    let recentTrips: [CompletedTrip]
    let appState: AppState

    var body: some View {
        VStack(spacing: 16) {
            // Section header
            HStack {
                Text("Your TrackRat Stats")
                    .font(.headline)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                Spacer()
            }
            .padding(.horizontal)

            // Stats card
            VStack(spacing: 20) {
                // Main stats row
                HStack(spacing: 0) {
                    StatBox(
                        value: "\(stats.totalTrips)",
                        label: "Trips Tracked",
                        icon: "tram.fill"
                    )

                    Divider()
                        .frame(height: 50)
                        .background(Color.white.opacity(0.2))

                    StatBox(
                        value: "\(stats.weeklyStreak)",
                        label: "Week Streak",
                        icon: "flame.fill",
                        valueColor: stats.weeklyStreak > 0 ? .orange : .white
                    )
                }

                Divider()
                    .background(Color.white.opacity(0.2))

                // Secondary stats row
                HStack(spacing: 0) {
                    StatBox(
                        value: "\(stats.onTimePercentage)%",
                        label: "On Time",
                        icon: "checkmark.circle.fill"
                    )

                    Divider()
                        .frame(height: 50)
                        .background(Color.white.opacity(0.2))

                    StatBox(
                        value: stats.formattedTotalDelay,
                        label: "Lost to Delays",
                        icon: "clock.badge.exclamationmark"
                    )
                }
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(.ultraThinMaterial)
            )

            // Recent trips
            VStack(spacing: 12) {
                HStack {
                    Text("Recent Trips")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(.white.opacity(0.8))
                    Spacer()

                    if recentTrips.count > 3 {
                        Button {
                            appState.navigationPath.append(NavigationDestination.tripHistory)
                        } label: {
                            Text("View All")
                                .font(.caption)
                                .foregroundColor(.orange)
                        }
                    }
                }
                .padding(.horizontal, 4)

                if recentTrips.isEmpty {
                    // Empty state placeholder
                    HStack {
                        Spacer()
                        VStack(spacing: 8) {
                            Image(systemName: "tram.fill")
                                .font(.title2)
                                .foregroundColor(.white.opacity(0.3))
                            Text("No trips yet")
                                .font(.subheadline)
                                .foregroundColor(.white.opacity(0.5))
                            Text("Start a Live Activity to track your first trip")
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.3))
                                .multilineTextAlignment(.center)
                        }
                        .padding(.vertical, 24)
                        Spacer()
                    }
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(.ultraThinMaterial)
                    )
                } else {
                    VStack(spacing: 0) {
                        ForEach(Array(recentTrips.prefix(3).enumerated()), id: \.element.id) { index, trip in
                            TripRowView(trip: trip)

                            if index < min(2, recentTrips.count - 1) {
                                Divider()
                                    .background(Color.white.opacity(0.1))
                            }
                        }
                    }
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(.ultraThinMaterial)
                    )
                }
            }
        }
    }
}

// MARK: - Stat Box Component

struct StatBox: View {
    let value: String
    let label: String
    var icon: String? = nil
    var valueColor: Color = .white

    var body: some View {
        VStack(spacing: 6) {
            if let icon = icon {
                Image(systemName: icon)
                    .font(.caption)
                    .foregroundColor(valueColor.opacity(0.8))
            }
            Text(value)
                .font(.title2.bold())
                .foregroundColor(valueColor)
            Text(label)
                .font(.caption)
                .foregroundColor(.white.opacity(0.6))
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Trip Row Component

struct TripRowView: View {
    let trip: CompletedTrip

    private var formattedDate: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM d"
        return formatter.string(from: trip.tripDate)
    }

    private var formattedTime: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "h:mm a"
        return formatter.string(from: trip.scheduledDeparture)
    }

    var body: some View {
        HStack(spacing: 12) {
            // Date column
            VStack(spacing: 2) {
                Text(formattedDate)
                    .font(.caption.weight(.medium))
                    .foregroundColor(.white.opacity(0.8))
                Text(formattedTime)
                    .font(.caption2)
                    .foregroundColor(.white.opacity(0.5))
            }
            .frame(width: 50)

            // Route info
            VStack(alignment: .leading, spacing: 2) {
                Text(trip.routeDescription)
                    .font(.subheadline.weight(.medium))
                    .foregroundColor(.white)
                    .lineLimit(1)

                Text(trip.lineName)
                    .font(.caption2)
                    .foregroundColor(.white.opacity(0.5))
            }

            Spacer()

            // Delay indicator
            Text(trip.formattedDelay)
                .font(.subheadline.weight(.medium))
                .foregroundColor(trip.isOnTime ? .green : .red)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
    }
}

// MARK: - Train System Row

private struct TrainSystemRow: View {
    let system: TrainSystem
    let isSelected: Bool
    let isLast: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 0) {
                HStack(spacing: 16) {
                    Image(systemName: system.icon)
                        .font(.title2)
                        .foregroundColor(isSelected ? .orange : .white.opacity(0.5))
                        .frame(width: 24, height: 24)

                    Text(system.displayName + (system.isBeta ? " (beta)" : ""))
                        .font(.headline)
                        .fontWeight(.medium)
                        .foregroundColor(.white)

                    Spacer()

                    Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                        .font(.title3)
                        .foregroundColor(isSelected ? .orange : .white.opacity(0.3))
                }
                .padding()
                .contentShape(Rectangle())

                if !isLast {
                    Divider()
                        .background(Color.white.opacity(0.1))
                        .padding(.leading, 56)
                }
            }
        }
        .buttonStyle(.plain)
    }
}

struct HealthIndicatorRow: View {
    let mode: SegmentHighlightMode
    let isSelected: Bool
    let isLast: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 0) {
                HStack(spacing: 16) {
                    Image(systemName: mode.icon)
                        .font(.title2)
                        .foregroundColor(isSelected ? .orange : .white.opacity(0.5))
                        .frame(width: 24, height: 24)

                    HStack(spacing: 4) {
                        Text(mode.displayName)
                            .font(.headline)
                            .fontWeight(.medium)
                            .foregroundColor(.white)
                    }

                    Spacer()

                    Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                        .font(.title3)
                        .foregroundColor(isSelected ? .orange : .white.opacity(0.3))
                }
                .padding()

                if !isLast {
                    Divider()
                        .background(Color.white.opacity(0.1))
                        .padding(.leading, 56)
                }
            }
        }
        .buttonStyle(.plain)
    }
}

#Preview {
    NavigationStack {
        MyProfileView()
            .environmentObject(AppState())
            .environmentObject(ThemeManager.shared)
    }
}
