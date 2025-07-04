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
                        TextField("e.g. 3710, 170, A170", text: $trainNumber)
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
                        HStack {
                            Spacer()
                            if isLoading {
                                ProgressView()
                                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                            } else {
                                Text("Find my train")
                                    .fontWeight(.semibold)
                            }
                            Spacer()
                        }
                        .frame(height: 50)
                        .frame(maxWidth: .infinity)
                    }
                    .font(.headline)
                    .foregroundColor(.white)
                    .background(isValidInput ? Color.green : Color.gray)
                    .cornerRadius(12)
                    .padding(.horizontal)
                    .disabled(!isValidInput || isLoading)
                    .contentShape(Rectangle())
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
    
    // MARK: - Helper Methods
    
    /// Check if input contains only digits (for Amtrak auto-detection)
    private func isNumericInput(_ input: String) -> Bool {
        let trimmedInput = input.trimmingCharacters(in: .whitespaces)
        return !trimmedInput.isEmpty && trimmedInput.allSatisfy(\.isNumber)
    }
    
    /// Attempt to search for a train with the given train number
    private func attemptTrainSearch(trainNumber: String) async throws -> Train {
        let train = try await APIService.shared.fetchTrainByNumber(
            trainNumber,
            fromStationCode: appState.departureStationCode
        )
        
        // Verify the train can be loaded in details view before proceeding
        _ = try await APIService.shared.fetchTrainDetailsFlexible(
            id: nil,
            trainId: trainNumber,
            fromStationCode: appState.departureStationCode
        )
        
        return train
    }
    
    /// Check if error indicates "train not found" (vs network/server errors)
    private func isTrainNotFoundError(_ error: Error) -> Bool {
        if let apiError = error as? APIError {
            return apiError == .noData
        } else if let urlError = error as? URLError {
            return urlError.localizedDescription == "No data received"
        } else {
            return error.localizedDescription == "No data received"
        }
    }
    
    private func searchTrain() {
        guard isValidInput else { return }
        
        isLoading = true
        error = nil
        
        // Haptic feedback
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
        
        Task {
            let trimmedInput = trainNumber.trimmingCharacters(in: .whitespaces)
            var lastError: Error?
            var foundTrain: Train?
            var successfulTrainNumber: String?
            
            // First attempt: Try user's exact input
            do {
                foundTrain = try await attemptTrainSearch(trainNumber: trimmedInput)
                successfulTrainNumber = trimmedInput
                print("✅ Found train with exact input: \(trimmedInput)")
            } catch {
                lastError = error
                print("🔍 First attempt failed for '\(trimmedInput)': \(error.localizedDescription)")
                
                // Second attempt: If input is numeric and first attempt failed with "not found", try with "A" prefix
                if isNumericInput(trimmedInput) && isTrainNotFoundError(error) {
                    let amtrakTrainNumber = "A\(trimmedInput)"
                    do {
                        foundTrain = try await attemptTrainSearch(trainNumber: amtrakTrainNumber)
                        successfulTrainNumber = amtrakTrainNumber
                        print("✅ Found Amtrak train with A prefix: \(amtrakTrainNumber)")
                    } catch {
                        lastError = error
                        print("🔍 Second attempt failed for '\(amtrakTrainNumber)': \(error.localizedDescription)")
                    }
                }
            }
            
            // Handle results
            if let train = foundTrain, let trainNumber = successfulTrainNumber {
                // Success - navigate to train details
                appState.currentTrainId = train.id
                appState.navigationPath.append(NavigationDestination.trainDetailsFlexible(
                    trainNumber: trainNumber,
                    fromStation: appState.departureStationCode
                ))
            } else if let error = lastError {
                // Handle the final error
                handleSearchError(error, originalInput: trimmedInput)
            }
            
            isLoading = false
        }
    }
    
    /// Handle search errors with user-friendly messages
    private func handleSearchError(_ error: Error, originalInput: String) {
        print("🔴 TrainNumberSearchView final error for input '\(originalInput)':")
        print("  - Error type: \(type(of: error))")
        print("  - Error description: \(error)")
        print("  - Localized description: \(error.localizedDescription)")
        
        if let apiError = error as? APIError {
            switch apiError {
            case .noData:
                // Provide more helpful message for numeric inputs that might be Amtrak
                if isNumericInput(originalInput) {
                    self.error = "Train not found. Note: Amtrak trains typically need an 'A' prefix (e.g., A\(originalInput))"
                } else {
                    self.error = "Train not found"
                }
            default:
                self.error = apiError.localizedDescription
            }
        } else if let urlError = error as? URLError {
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
                if urlError.localizedDescription == "No data received" {
                    self.error = "Train not found"
                } else {
                    self.error = urlError.localizedDescription
                }
            }
        } else {
            if error.localizedDescription == "No data received" {
                print("🔴 Unexpected error with 'No data received' message")
                self.error = "Train not found"
            } else {
                self.error = error.localizedDescription
            }
        }
        
        UINotificationFeedbackGenerator().notificationOccurred(.error)
    }
}

#Preview {
    NavigationStack {
        TrainNumberSearchView()
            .environmentObject(AppState())
    }
}
