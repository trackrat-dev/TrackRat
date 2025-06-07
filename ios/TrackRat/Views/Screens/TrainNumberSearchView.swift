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
            // Black gradient background
            TrackRatTheme.Colors.primaryGradient
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
                        TextField("e.g. 3710 or A170", text: $trainNumber)
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
                
                // Verify the train can be loaded in details view before navigating
                // This prevents navigation to a view that will show an error
                do {
                    _ = try await APIService.shared.fetchTrainDetailsFlexible(
                        id: nil,
                        trainId: trainNumber,
                        fromStationCode: appState.departureStationCode
                    )
                    
                    // Train can be loaded, proceed with navigation
                    appState.currentTrainId = train.id
                    // Use flexible navigation with train number for direct access
                    appState.navigationPath.append(NavigationDestination.trainDetailsFlexible(
                        trainNumber: trainNumber,
                        fromStation: appState.departureStationCode
                    ))
                } catch {
                    // Train was found in search but can't be loaded in details
                    // This happens when the train is outside the time window
                    print("🔴 Train \(trainNumber) found in search but not available in details view")
                    throw error
                }
            } catch {
                // Log the error details for debugging
                print("🔴 TrainNumberSearchView error for train \(trainNumber):")
                print("  - Error type: \(type(of: error))")
                print("  - Error description: \(error)")
                print("  - Localized description: \(error.localizedDescription)")
                
                // Use the actual error description for consistency
                if let apiError = error as? APIError {
                    switch apiError {
                    case .noData:
                        self.error = "Train not found"
                    default:
                        self.error = apiError.localizedDescription
                    }
                } else if let urlError = error as? URLError {
                    // Handle URLError specifically
                    print("🔴 URLError code: \(urlError.code)")
                    switch urlError.code {
                    case .notConnectedToInternet:
                        self.error = "No internet connection"
                    case .timedOut:
                        self.error = "Request timed out"
                    case .cannotFindHost, .cannotConnectToHost:
                        self.error = "Cannot connect to server"
                    case .networkConnectionLost:
                        self.error = "Network connection lost"
                    default:
                        // Check if the error description is "No data received" from URLError
                        if urlError.localizedDescription == "No data received" {
                            self.error = "Train not found"
                        } else {
                            self.error = urlError.localizedDescription
                        }
                    }
                } else {
                    // For any other error type, check if it says "No data received"
                    if error.localizedDescription == "No data received" {
                        print("🔴 Unexpected error with 'No data received' message")
                        self.error = "Train not found"
                    } else {
                        self.error = error.localizedDescription
                    }
                }
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
