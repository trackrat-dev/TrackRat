import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var appState: AppState
    @ObservedObject private var feedbackService = JourneyFeedbackService.shared

    var body: some View {
        MapContainerView()
            .sheet(isPresented: $feedbackService.shouldShowFeedbackPrompt) {
                JourneyFeedbackPromptView()
            }
    }
}

// MARK: - Navigation
enum NavigationDestination: Hashable {
    case departureSelector
    case destinationPicker
    case trainList(destination: String, departureStationCode: String)
    case trainDetails(trainId: Int)  // Legacy database ID navigation
    case trainDetailsFlexible(trainNumber: String, fromStation: String?, journeyDate: Date?)  // New train number navigation
    case advancedConfiguration
    case myProfile
    case congestionMap
    case favoriteStations
}

#Preview {
    ContentView()
        .environmentObject(AppState())
}