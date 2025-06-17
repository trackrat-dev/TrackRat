import SwiftUI

struct AdvancedConfigurationView: View {
    @EnvironmentObject private var appState: AppState
    @State private var selectedEnvironment: ServerEnvironment
    @State private var hasChanges = false
    
    private let storageService = StorageService()
    
    init() {
        let storage = StorageService()
        _selectedEnvironment = State(initialValue: storage.loadServerEnvironment())
    }
    
    var body: some View {
        ZStack {
            // Background gradient
            TrackRatTheme.Colors.primaryGradient
                .ignoresSafeArea()
            
            ScrollView {
                VStack(spacing: 24) {
                    // Header
                    VStack(spacing: 8) {
                        Image(systemName: "gearshape.fill")
                            .font(.system(size: 40))
                            .foregroundColor(.orange)
                        
                        Text("Advanced Configuration")
                            .font(.largeTitle)
                            .fontWeight(.bold)
                            .foregroundColor(.white)
                        
                        Text("Configure backend server settings")
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.7))
                    }
                    .padding(.top, 20)
                    
                    // Server Environment Section
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
                    
                    // Save Button
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
                        .padding(.horizontal)
                    }
                    
                    // Warning Section
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundColor(.yellow)
                            Text("Important Notes")
                                .font(.headline)
                                .fontWeight(.semibold)
                                .foregroundColor(.white)
                        }
                        
                        VStack(alignment: .leading, spacing: 8) {
                            Text("• Production server provides real-time train data")
                            Text("• Staging and Development servers are for testing only")
                            Text("• Changes require app restart to take full effect")
                            Text("• Invalid server URLs may cause connection failures")
                        }
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.8))
                    }
                    .padding()
                    .background(
                        RoundedRectangle(cornerRadius: 16)
                            .fill(.yellow.opacity(0.1))
                            .overlay(
                                RoundedRectangle(cornerRadius: 16)
                                    .stroke(.yellow.opacity(0.3), lineWidth: 1)
                            )
                    )
                }
                .padding()
                .padding(.bottom, 40)
            }
        }
        .navigationTitle("Settings")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            selectedEnvironment = storageService.loadServerEnvironment()
            hasChanges = false
        }
    }
    
    private func saveConfiguration() {
        storageService.saveServerEnvironment(selectedEnvironment)
        APIService.shared.updateServerEnvironment(selectedEnvironment)
        hasChanges = false
        
        // Haptic feedback
        UINotificationFeedbackGenerator().notificationOccurred(.success)
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
    }
}