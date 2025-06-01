import SwiftUI

struct TrainNumberSearchView: View {
    @EnvironmentObject private var appState: AppState
    @State private var trainNumber = ""
    @State private var isLoading = false
    @State private var error: String?
    @FocusState private var isInputFocused: Bool
    
    private var isValidInput: Bool {
        trainNumber.count >= 2
    }
    
    var body: some View {
        ZStack {
            // Background gradient
            LinearGradient(
                colors: [Color(hex: "667eea"), Color(hex: "764ba2")],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
            
            VStack(spacing: 32) {
                    // Title
                    Text("What's your train number?")
                        .font(.largeTitle)
                        .fontWeight(.semibold)
                        .foregroundColor(.white)
                        .multilineTextAlignment(.center)
                        .padding(.top, 60)
                
                VStack(spacing: 24) {
                    // Input field
                    VStack(alignment: .leading, spacing: 8) {
                        TextField("e.g. 7829 or A54", text: $trainNumber)
                            .textFieldStyle(.plain)
                            .font(.title2)
                            .focused($isInputFocused)
                            .textInputAutocapitalization(.characters)
                            .keyboardType(.asciiCapable)
                            .padding()
                            .background(.ultraThinMaterial)
                            .cornerRadius(12)
                            .onChange(of: trainNumber) { _, _ in
                                error = nil
                            }
                        
                        if let error = error {
                            Label(error, systemImage: "exclamationmark.circle")
                                .font(.caption)
                                .foregroundColor(.red)
                        }
                    }
                    .padding(.horizontal)
                    
                    // Submit button
                    Button {
                        searchTrain()
                    } label: {
                        if isLoading {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        } else {
                            Text("Find my train")
                                .fontWeight(.semibold)
                        }
                    }
                    .font(.headline)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: 50)
                    .background(isValidInput ? Color.green : Color.gray)
                    .cornerRadius(12)
                    .padding(.horizontal)
                    .disabled(!isValidInput || isLoading)
                }
                
                Spacer()
            }
        }
        .navigationTitle("Find Train")
        .navigationBarTitleDisplayMode(.inline)
        .glassmorphicNavigationBar()
        .onAppear {
            isInputFocused = true
        }
    }
    
    private func searchTrain() {
        guard isValidInput else { return }
        
        isLoading = true
        error = nil
        
        // Haptic feedback
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
        
        Task {
            do {
                let train = try await APIService.shared.fetchTrainByNumber(
                    trainNumber,
                    fromStationCode: appState.departureStationCode
                )
                appState.currentTrainId = train.id
                // Use flexible navigation with train number for direct access
                appState.navigationPath.append(NavigationDestination.trainDetailsFlexible(
                    trainNumber: trainNumber,
                    fromStation: appState.departureStationCode
                ))
            } catch {
                self.error = "Train not found"
                UINotificationFeedbackGenerator().notificationOccurred(.error)
            }
            isLoading = false
        }
    }
}

#Preview {
    NavigationStack {
        TrainNumberSearchView()
            .environmentObject(AppState())
    }
}