import SwiftUI
import Sentry

struct AdvancedConfigurationView: View {
    @EnvironmentObject private var appState: AppState
    @EnvironmentObject private var themeManager: ThemeManager
    @State private var selectedEnvironment: ServerEnvironment
    @State private var hasChanges = false
    @State private var healthCheckResult: HealthCheckResult?
    @State private var isTestingConnection = false
    
    private let storageService = StorageService()
    
    init() {
        let storage = StorageService()
        _selectedEnvironment = State(initialValue: storage.loadServerEnvironment())
    }
    
    var body: some View {
        let backgroundView = TrackRatTheme.Colors.primaryBackground
            .ignoresSafeArea()

        let serverEnvironmentSection = createServerEnvironmentSection()
        let healthCheckSection = createHealthCheckSection()
        let sentryTestSection = createSentryTestSection()

        return ZStack {
            backgroundView

            ScrollView {
                VStack(spacing: 24) {
                    serverEnvironmentSection
                    healthCheckSection
                    sentryTestSection
                }
                .padding()
                .padding(.bottom, 40)
            }
        }
        .navigationTitle("Advanced Configuration")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            selectedEnvironment = storageService.loadServerEnvironment()
            hasChanges = false
        }
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
                        hasChanges = true
                        healthCheckResult = nil
                    }
                }
            }
            
            // Save Button inside the server section
            if hasChanges {
                Button {
                    saveConfiguration()
                } label: {
                    HStack {
                        Image(systemName: "checkmark.circle.fill")
                        Text("Save Changes")
                    }
                    .font(.headline)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(.orange)
                    )
                }
                .padding(.top, 8)
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
    
    
    private func saveConfiguration() {
        storageService.saveServerEnvironment(selectedEnvironment)
        APIService.shared.updateServerEnvironment(selectedEnvironment)
        hasChanges = false
        
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

    @ViewBuilder
    private func createSentryTestSection() -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Error Reporting")
                .font(.headline)
                .fontWeight(.semibold)
                .foregroundColor(.white)

            Text("Test Sentry error reporting to ensure crashes and errors are being tracked properly.")
                .font(.caption)
                .foregroundColor(.white.opacity(0.7))

            VStack(spacing: 12) {
                // Test Error Button
                Button {
                    testSentryError()
                } label: {
                    HStack {
                        Image(systemName: "exclamationmark.triangle.fill")
                        Text("Send Test Error")
                    }
                    .font(.headline)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(.red.opacity(0.8))
                    )
                }

                // Test Message Button
                Button {
                    testSentryMessage()
                } label: {
                    HStack {
                        Image(systemName: "message.fill")
                        Text("Send Test Message")
                    }
                    .font(.headline)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(.blue.opacity(0.8))
                    )
                }

                // Test Transaction Button
                Button {
                    testSentryTransaction()
                } label: {
                    HStack {
                        Image(systemName: "chart.line.uptrend.xyaxis")
                        Text("Send Test Transaction")
                    }
                    .font(.headline)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(.purple.opacity(0.8))
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

    private func testSentryError() {
        // Create a test error
        let error = NSError(
            domain: "TrackRatTestError",
            code: 9999,
            userInfo: [
                NSLocalizedDescriptionKey: "Test error from iOS app - Sentry integration verification",
                "test_type": "manual_test",
                "triggered_from": "AdvancedConfigurationView"
            ]
        )

        // Capture the error with additional context
        SentrySDK.capture(error: error) { scope in
            scope.setLevel(.error)
            scope.setContext(value: [
                "environment": selectedEnvironment.rawValue,
                "test": true,
                "timestamp": Date().ISO8601Format()
            ], key: "test_context")
            scope.setTag(value: "ios_test", key: "error_source")
        }

        print("🔍 Sentry test error sent successfully")

        // Haptic feedback
        UINotificationFeedbackGenerator().notificationOccurred(.warning)
    }

    private func testSentryMessage() {
        // Send a test message
        SentrySDK.capture(message: "Test message from iOS app - Sentry is working correctly") { scope in
            scope.setLevel(.info)
            scope.setContext(value: [
                "environment": selectedEnvironment.rawValue,
                "test": true,
                "app_version": Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "unknown"
            ], key: "test_info")
            scope.setTag(value: "ios_test", key: "message_source")
        }

        print("🔍 Sentry test message sent successfully")

        // Haptic feedback
        UINotificationFeedbackGenerator().notificationOccurred(.success)
    }

    private func testSentryTransaction() {
        Task {
            // Start a test transaction
            let transaction = SentrySDK.startTransaction(
                name: "test.performance",
                operation: "manual_test"
            )
            transaction.setData(value: selectedEnvironment.rawValue, key: "environment")
            transaction.setData(value: "AdvancedConfigurationView", key: "source")

            // Create child spans to simulate work
            let networkSpan = transaction.startChild(operation: "http.client", description: "Simulated API call")
            try? await Task.sleep(nanoseconds: 100_000_000) // 100ms
            networkSpan.setData(value: 200, key: "status_code")
            networkSpan.finish()

            let dbSpan = transaction.startChild(operation: "db.query", description: "Simulated database query")
            try? await Task.sleep(nanoseconds: 50_000_000) // 50ms
            dbSpan.finish()

            let computeSpan = transaction.startChild(operation: "compute", description: "Simulated processing")
            try? await Task.sleep(nanoseconds: 75_000_000) // 75ms
            computeSpan.finish()

            // Finish the transaction
            transaction.finish()

            print("🔍 Sentry test transaction sent successfully")

            // Haptic feedback
            await MainActor.run {
                UINotificationFeedbackGenerator().notificationOccurred(.success)
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

#Preview {
    NavigationView {
        AdvancedConfigurationView()
            .environmentObject(AppState())
            .environmentObject(ThemeManager.shared)
    }
}