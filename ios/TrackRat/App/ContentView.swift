import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var appState: AppState
    
    var body: some View {
        NavigationStack(path: $appState.navigationPath) {
            TripSelectionView()
                .navigationDestination(for: NavigationDestination.self) { destination in
                    switch destination {
                    case .departureSelector:
                        DeparturePickerView()
                    case .destinationPicker:
                        DestinationPickerView()
                    case .trainList(let stationName):
                        TrainListView(destination: stationName)
                    case .trainDetails(let trainId):
                        TrainDetailsView(trainId: trainId)
                    case .trainDetailsFlexible(let trainNumber, let fromStation):
                        TrainDetailsView(trainNumber: trainNumber, fromStation: fromStation)
                    case .trainNumberSearch:
                        TrainNumberSearchView()
                    case .settings:
                        SettingsView()
                    }
                }
        }
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
    case settings
}

#Preview {
    ContentView()
        .environmentObject(AppState())
}