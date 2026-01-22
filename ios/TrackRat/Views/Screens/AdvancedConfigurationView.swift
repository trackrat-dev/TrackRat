import SwiftUI

struct AdvancedConfigurationView: View {
    @EnvironmentObject private var appState: AppState
    @EnvironmentObject private var themeManager: ThemeManager
    @ObservedObject private var subscriptionService = SubscriptionService.shared
    @ObservedObject private var journeyFeedbackService = JourneyFeedbackService.shared
    @State private var selectedEnvironment: ServerEnvironment
    @State private var healthCheckResult: HealthCheckResult?
    @State private var isTestingConnection = false
    @State private var showClearHistoryConfirmation = false
    @State private var resetDataSuccessMessage: String?

    private let storageService = StorageService()
    
    init() {
        let storage = StorageService()
        _selectedEnvironment = State(initialValue: storage.loadServerEnvironment())
    }
    
    var body: some View {
        let serverEnvironmentSection = createServerEnvironmentSection()
        let healthCheckSection = createHealthCheckSection()

        return VStack(spacing: 0) {
            TrackRatNavigationHeader(
                title: "Advanced Configuration",
                showBackButton: false,
                showCloseButton: true
            )

            ScrollView {
                VStack(spacing: 24) {
                    createTrainSystemsSection()
                    createSubscriptionDebugSection()
                    serverEnvironmentSection
                    healthCheckSection
                    createResetDataSection()
                }
                .padding()
                .padding(.bottom, 40)
            }
        }
        .navigationBarHidden(true)
        .onAppear {
            selectedEnvironment = storageService.loadServerEnvironment()
        }
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
    
    @ViewBuilder
    private func createTrainSystemsSection() -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Additional Transit Systems")
                .font(.headline)
                .fontWeight(.semibold)
                .foregroundColor(.white)

            Text("Enable PATH and PATCO to see them in the app. NJ Transit and Amtrak are always available.")
                .font(.caption)
                .foregroundColor(.white.opacity(0.7))

            VStack(spacing: 12) {
                // PATH toggle
                TrainSystemToggleRow(
                    system: .path,
                    isEnabled: appState.isSystemEnabled(.path)
                ) { enabled in
                    appState.setSystemEnabled(.path, enabled: enabled)
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                }

                // PATCO toggle
                TrainSystemToggleRow(
                    system: .patco,
                    isEnabled: appState.isSystemEnabled(.patco)
                ) { enabled in
                    appState.setSystemEnabled(.patco, enabled: enabled)
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
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
        .disabled(isTestingConnection)
    }
    
    @ViewBuilder
    private func createHealthCheckResult() -> some View {
        if let result = healthCheckResult {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Image(systemName: result.success ? "checkmark.circle.fill" : "xmark.circle.fill")
                        .font(.system(size: 24))
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
    private func createResetDataSection() -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Reset Data")
                .font(.headline)
                .fontWeight(.semibold)
                .foregroundColor(.white)

            Text("Debug tools for testing feedback prompts and clearing stored data.")
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

    private func saveConfiguration() {
        storageService.saveServerEnvironment(selectedEnvironment)
        APIService.shared.updateServerEnvironment(selectedEnvironment)

        // Haptic feedback
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

                // Haptic feedback
                if result.success {
                    UINotificationFeedbackGenerator().notificationOccurred(.success)
                } else {
                    UINotificationFeedbackGenerator().notificationOccurred(.error)
                }
            }
        }
    }

}


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
                        .font(.system(size: 20))
                        .foregroundColor(.orange)
                } else {
                    Image(systemName: "circle")
                        .font(.system(size: 20))
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
    }
}

struct TrainSystemToggleRow: View {
    let system: TrainSystem
    let isEnabled: Bool
    let onToggle: (Bool) -> Void

    var body: some View {
        HStack {
            Image(systemName: system.icon)
                .font(.title2)
                .foregroundColor(isEnabled ? .orange : .white.opacity(0.5))
                .frame(width: 32)

            VStack(alignment: .leading, spacing: 4) {
                Text(system.displayName)
                    .font(.headline)
                    .foregroundColor(.white)

                Text(system.description)
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.6))
            }

            Spacer()

            Toggle("", isOn: Binding(
                get: { isEnabled },
                set: { onToggle($0) }
            ))
            .labelsHidden()
            .tint(.orange)
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(isEnabled ? .orange.opacity(0.2) : .white.opacity(0.05))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(isEnabled ? .orange.opacity(0.5) : .white.opacity(0.1), lineWidth: 1)
                )
        )
    }
}

#Preview {
    NavigationStack {
        AdvancedConfigurationView()
            .environmentObject(AppState())
            .environmentObject(ThemeManager.shared)
    }
}
