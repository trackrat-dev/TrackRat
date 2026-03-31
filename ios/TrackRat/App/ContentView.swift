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
    case trainList(destination: String, departureStationCode: String)
    case trainDetails(trainId: Int)  // Legacy database ID navigation
    case trainDetailsFlexible(trainNumber: String, fromStation: String?, journeyDate: Date?, dataSource: String?)  // New train number navigation with data source for disambiguation
    case advancedConfiguration
    case congestionMap
    case favoriteStations
    case tripHistory
}

#Preview {
    ContentView()
        .environmentObject(AppState())
}