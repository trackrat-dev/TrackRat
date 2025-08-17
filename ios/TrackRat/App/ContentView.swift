import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var appState: AppState
    
    var body: some View {
        MapContainerView()
    }
}

// MARK: - Navigation
enum NavigationDestination: Hashable {
    case departureSelector
    case destinationPicker
    case trainList(destination: String)
    case trainDetails(trainId: Int)  // Legacy database ID navigation
    case trainDetailsFlexible(trainNumber: String, fromStation: String?)  // New train number navigation
    case trainNumberSearch
    case advancedConfiguration
    case myProfile
    case congestionMap
}

#Preview {
    ContentView()
        .environmentObject(AppState())
}