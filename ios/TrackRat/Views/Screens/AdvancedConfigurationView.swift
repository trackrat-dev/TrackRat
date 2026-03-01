import SwiftUI

struct AdvancedConfigurationView: View {
    @EnvironmentObject private var appState: AppState
    @EnvironmentObject private var themeManager: ThemeManager
    @State private var showClearHistoryConfirmation = false
    @State private var resetDataSuccessMessage: String?

    private let storageService = StorageService()

    // MARK: - Debug/TestFlight state
    @ObservedObject private var subscriptionService = SubscriptionService.shared
    @ObservedObject private var journeyFeedbackService = JourneyFeedbackService.shared
    @State private var selectedEnvironment: ServerEnvironment = StorageService().loadServerEnvironment()
    @State private var healthCheckResult: HealthCheckResult?
    @State private var isTestingConnection = false

    var body: some View {
        VStack(spacing: 0) {
            TrackRatNavigationHeader(
                title: "Advanced Configuration",
                showBackButton: false,
                showCloseButton: true
            )

            ScrollView {
                VStack(spacing: 24) {
                    createBetaFeaturesSection()
                    createServerEnvironmentSection()
                    createHealthCheckSection()
                    createMapSettingsSection()
                    createSubscriptionDebugSection()
                    createDebugToolsSection()
                    createDataManagementSection()
                }
                .padding()
                .padding(.bottom, 40)
            }
        }
        .navigationBarHidden(true)
        .alert("Clear Trip History", isPresented: $showClearHistoryConfirmation) {
            Button("Cancel", role: .cancel) { }
            Button("Clear", role: .destructive) {
                clearTripHistory()
            }
        } message: {
            Text("This will permanently delete all your recorded trips and statistics. This cannot be undone.")
        }
        .overlay(alignment: .bottom) {
            if let message = resetDataSuccessMessage {
                Text(message)
                    .font(.subheadline)
                    .foregroundColor(.white)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(
                        Capsule()
                            .fill(.green.opacity(0.9))
                    )
                    .padding(.bottom, 100)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .animation(.easeInOut(duration: 0.3), value: resetDataSuccessMessage)
    }

    // MARK: - Beta Features Section
    @ViewBuilder
    private func createBetaFeaturesSection() -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Beta Features")
                .font(.headline)
                .fontWeight(.semibold)
                .foregroundColor(.white)

            NavigationLink(value: SettingsDestination.tripHistory) {
                HStack(spacing: 16) {
                    Image(systemName: "chart.bar.fill")
                        .font(.title2)
                        .foregroundColor(.orange)
                        .frame(width: 24, height: 24)

                    VStack(alignment: .leading, spacing: 4) {
                        Text("My Trips")
                            .font(.headline)
                            .fontWeight(.medium)
                            .foregroundColor(.white)
                            .multilineTextAlignment(.leading)

                        Text("View your trip history and statistics")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.6))
                    }

                    Spacer()

                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.5))
                }
                .padding()
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(.white.opacity(0.05))
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(.white.opacity(0.1), lineWidth: 1)
                        )
                )
            }
            .buttonStyle(.plain)
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(.white.opacity(0.1))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(.white.opacity(0.2), lineWidth: 1)
                )
        )
    }

    // MARK: - Map Settings Section
    @ViewBuilder
    private func createMapSettingsSection() -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Map Settings")
                .font(.headline)
                .fontWeight(.semibold)
                .foregroundColor(.white)

            // Show Stations toggle
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Show Stations")
                        .font(.headline)
                        .foregroundColor(.white)
                }

                Spacer()

                Toggle("", isOn: $appState.showMapStations)
                    .labelsHidden()
                    .tint(.orange)
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(.white.opacity(0.05))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(.white.opacity(0.1), lineWidth: 1)
                    )
            )

            // Show Departure Odds toggle
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Show Departure Odds (beta)")
                        .font(.headline)
                        .foregroundColor(.white)
                }

                Spacer()

                Toggle("", isOn: $appState.showDepartureOdds)
                    .labelsHidden()
                    .tint(.orange)
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(.white.opacity(0.05))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(.white.opacity(0.1), lineWidth: 1)
                    )
            )
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(.white.opacity(0.1))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(.white.opacity(0.2), lineWidth: 1)
                )
        )
    }

    // MARK: - Debug/TestFlight Sections
    @ViewBuilder
    private func createSubscriptionDebugSection() -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Subscription Debug")
                .font(.headline)
                .fontWeight(.semibold)
                .foregroundColor(.white)

            Text("Toggle premium mode to test the free user experience.")
                .font(.caption)
                .foregroundColor(.white.opacity(0.7))

            // Premium mode toggle
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Premium Mode")
                        .font(.headline)
                        .foregroundColor(.white)

                    Text(subscriptionService.debugOverrideEnabled ? "All Pro features enabled" : "Viewing as free user")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))
                }

                Spacer()

                Toggle("", isOn: $subscriptionService.debugOverrideEnabled)
                    .labelsHidden()
                    .tint(.orange)
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(subscriptionService.debugOverrideEnabled ? .orange.opacity(0.2) : .white.opacity(0.05))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(subscriptionService.debugOverrideEnabled ? .orange.opacity(0.5) : .white.opacity(0.1), lineWidth: 1)
                    )
            )

            // Status indicator
            HStack(spacing: 8) {
                Image(systemName: subscriptionService.isPro ? "checkmark.seal.fill" : "xmark.seal.fill")
                    .foregroundColor(subscriptionService.isPro ? .green : .red)

                Text(subscriptionService.isPro ? "Pro features active" : "Pro features locked")
                    .font(.subheadline)
                    .foregroundColor(.white.opacity(0.8))

                Spacer()
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(.white.opacity(0.1))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(.white.opacity(0.2), lineWidth: 1)
                )
        )
    }

    @ViewBuilder
    private func createServerEnvironmentSection() -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Backend Server")
                .font(.headline)
                .fontWeight(.semibold)
                .foregroundColor(.white)
            
            Text("Choose which backend server to connect to. Production is recommended for normal use.")
                .font(.caption)
                .foregroundColor(.white.opacity(0.7))
            
            VStack(spacing: 12) {
                ForEach(ServerEnvironment.allCases, id: \.self) { environment in
                    ServerEnvironmentRow(
                        environment: environment,
                        isSelected: selectedEnvironment == environment
                    ) {
                        selectedEnvironment = environment
                        healthCheckResult = nil
                        saveConfiguration()
                    }
                }
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(.white.opacity(0.1))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(.white.opacity(0.2), lineWidth: 1)
                )
        )
    }
    
    @ViewBuilder
    private func createHealthCheckSection() -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Backend Server Health")
                .font(.headline)
                .fontWeight(.semibold)
                .foregroundColor(.white)
            
            Text("Test the connection to the selected backend server.")
                .font(.caption)
                .foregroundColor(.white.opacity(0.7))
            
            createTestConnectionButton()
            createHealthCheckResult()
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(.white.opacity(0.1))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(.white.opacity(0.2), lineWidth: 1)
                )
        )
    }
    
    @ViewBuilder
    private func createTestConnectionButton() -> some View {
        Button {
            testConnection()
        } label: {
            HStack {
                if isTestingConnection {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        .scaleEffect(0.8)
                } else {
                    Image(systemName: "network")
                }
                Text(isTestingConnection ? "Testing..." : "Test Connection")
            }
            .font(.headline)
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(isTestingConnection ? .gray : .orange)
            )
        }
        .buttonStyle(.plain)
        .disabled(isTestingConnection)
    }
    
    @ViewBuilder
    private func createHealthCheckResult() -> some View {
        if let result = healthCheckResult {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Image(systemName: result.success ? "checkmark.circle.fill" : "xmark.circle.fill")
                        .font(TrackRatTheme.IconSize.large)
                        .foregroundColor(result.success ? .green : .red)

                    Text(result.success ? "Connected" : "Connection Failed")
                        .font(.headline)
                        .foregroundColor(.white)

                    Spacer()
                }
                
                createConnectionDetails(result: result)
            }
            .transition(.scale.combined(with: .opacity))
            .animation(.easeInOut(duration: 0.3), value: healthCheckResult)
        }
    }
    
    @ViewBuilder
    private func createConnectionDetails(result: HealthCheckResult) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            if let statusCode = result.statusCode {
                HStack {
                    Text("Status:")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))
                    Text("HTTP \(statusCode)")
                        .font(.caption)
                        .foregroundColor(.white)
                }
            }
            
            HStack {
                Text("Response Time:")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.6))
                Text("\(String(format: "%.2f", result.responseTime))s")
                    .font(.caption)
                    .foregroundColor(.white)
            }
            
            if let errorMessage = result.errorMessage {
                HStack {
                    Text("Error:")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))
                    Text(errorMessage)
                        .font(.caption)
                        .foregroundColor(.white)
                        .lineLimit(2)
                }
            }
            
            if result.success, let body = result.responseBody {
                HStack {
                    Text("Response:")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))
                    Text(body)
                        .font(.caption)
                        .foregroundColor(.white)
                        .lineLimit(1)
                }
            }
        }
        .padding(.vertical, 8)
        .padding(.horizontal, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(result.success ? .green.opacity(0.15) : .red.opacity(0.15))
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(result.success ? .green.opacity(0.3) : .red.opacity(0.3), lineWidth: 1)
                )
        )
    }

    @ViewBuilder
    private func createDebugToolsSection() -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Debug Tools")
                .font(.headline)
                .fontWeight(.semibold)
                .foregroundColor(.white)

            Text("Development tools for testing feedback prompts.")
                .font(.caption)
                .foregroundColor(.white.opacity(0.7))

            VStack(spacing: 12) {
                // Show Feedback Prompt
                Button {
                    showFeedbackPrompt()
                } label: {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Show Feedback Prompt")
                                .font(.headline)
                                .foregroundColor(.white)
                            Text("Displays the \"Enjoying TrackRat?\" prompt")
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.6))
                        }
                        Spacer()
                        Image(systemName: "bubble.left.and.bubble.right")
                            .foregroundColor(.orange)
                    }
                    .padding()
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(.white.opacity(0.05))
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(.white.opacity(0.1), lineWidth: 1)
                            )
                    )
                }
                .buttonStyle(.plain)

                // Reset Feedback Cooldowns
                Button {
                    resetFeedbackCooldowns()
                } label: {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Reset Feedback Cooldowns")
                                .font(.headline)
                                .foregroundColor(.white)
                            Text("Allows prompt to appear on next departure")
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.6))
                        }
                        Spacer()
                        Image(systemName: "clock.arrow.circlepath")
                            .foregroundColor(.orange)
                    }
                    .padding()
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(.white.opacity(0.05))
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(.white.opacity(0.1), lineWidth: 1)
                            )
                    )
                }
                .buttonStyle(.plain)
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(.white.opacity(0.1))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(.white.opacity(0.2), lineWidth: 1)
                )
        )
    }

    private func showFeedbackPrompt() {
        journeyFeedbackService.forceShowPrompt()
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
    }

    private func resetFeedbackCooldowns() {
        journeyFeedbackService.resetCooldowns()
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        showSuccessMessage("Cooldowns reset")
    }

    private func saveConfiguration() {
        storageService.saveServerEnvironment(selectedEnvironment)
        APIService.shared.updateServerEnvironment(selectedEnvironment)
        UINotificationFeedbackGenerator().notificationOccurred(.success)
    }

    private func testConnection() {
        isTestingConnection = true
        healthCheckResult = nil

        Task {
            let result = await BackendWakeupService.shared.performHealthCheck(environment: selectedEnvironment)

            await MainActor.run {
                withAnimation {
                    healthCheckResult = result
                    isTestingConnection = false
                }

                if result.success {
                    UINotificationFeedbackGenerator().notificationOccurred(.success)
                } else {
                    UINotificationFeedbackGenerator().notificationOccurred(.error)
                }
            }
        }
    }

    // MARK: - Data Management Section (all builds)
    @ViewBuilder
    private func createDataManagementSection() -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Data Management")
                .font(.headline)
                .fontWeight(.semibold)
                .foregroundColor(.white)

            Text("Manage your stored data.")
                .font(.caption)
                .foregroundColor(.white.opacity(0.7))

            // Clear Trip History
            Button {
                showClearHistoryConfirmation = true
            } label: {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Clear Trip History")
                            .font(.headline)
                            .foregroundColor(.white)
                        Text("Removes all recorded trips and statistics")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.6))
                    }
                    Spacer()
                    Image(systemName: "trash")
                        .foregroundColor(.red)
                }
                .padding()
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(.red.opacity(0.1))
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(.red.opacity(0.3), lineWidth: 1)
                        )
                )
            }
            .buttonStyle(.plain)
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(.white.opacity(0.1))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(.white.opacity(0.2), lineWidth: 1)
                )
        )
    }

    private func clearTripHistory() {
        storageService.clearCompletedTrips()
        UINotificationFeedbackGenerator().notificationOccurred(.success)
        showSuccessMessage("Trip history cleared")
    }

    private func showSuccessMessage(_ message: String) {
        resetDataSuccessMessage = message
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            resetDataSuccessMessage = nil
        }
    }
}


// MARK: - Debug/TestFlight Components
struct ServerEnvironmentRow: View {
    let environment: ServerEnvironment
    let isSelected: Bool
    let onTap: () -> Void

    var body: some View {
        Button {
            onTap()
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
        } label: {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(environment.displayName)
                        .font(.headline)
                        .foregroundColor(.white)

                    Text(environment.baseURL)
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))
                        .lineLimit(1)
                }

                Spacer()

                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .font(TrackRatTheme.IconSize.medium)
                        .foregroundColor(.orange)
                } else {
                    Image(systemName: "circle")
                        .font(TrackRatTheme.IconSize.medium)
                        .foregroundColor(.white.opacity(0.3))
                }
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(isSelected ? .orange.opacity(0.2) : .white.opacity(0.05))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(isSelected ? .orange.opacity(0.5) : .white.opacity(0.1), lineWidth: 1)
                    )
            )
        }
        .buttonStyle(.plain)
    }
}

#Preview {
    NavigationStack {
        AdvancedConfigurationView()
            .environmentObject(AppState())
            .environmentObject(ThemeManager.shared)
    }
}
