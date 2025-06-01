import SwiftUI
import ActivityKit
import WidgetKit

@main
struct TrackRatApp: App {
    @StateObject private var appState = AppState()
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
                .preferredColorScheme(.dark)
                .tint(.orange)
        }
    }
    
    init() {
        // Register Live Activity widget
        if #available(iOS 16.1, *) {
            // This will register the Live Activity widget with the system
            WidgetCenter.shared.reloadAllTimelines()
        }
        
        // Set notification delegate
        // MOVED TO AppDelegate
    }
}

// Create a new AppDelegate class to handle notification delegate methods
class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey : Any]? = nil) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        return true
    }

    // Handle foreground notifications
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification, withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound, .badge]) // Show banner, play sound, update badge
    }

    // Handle user interaction with notifications
    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse, withCompletionHandler completionHandler: @escaping () -> Void) {
        // Here you can add logic to navigate to a specific part of your app based on the notification
        completionHandler()
    }
}

// MARK: - App State
@MainActor
final class AppState: ObservableObject {
    @Published var selectedDestination: String?
    @Published var destinationStationCode: String?
    @Published var selectedDeparture: String?
    @Published var departureStationCode: String?
    @Published var currentTrainId: Int?
    @Published var navigationPath = NavigationPath()
    
    private let apiService = APIService()
    private let storageService = StorageService()
    
    // Recent destinations
    @Published var recentDestinations: [String] = []
    @Published var recentTrips: [TripPair] = []
    @Published var recentDepartures: [RecentDeparture] = []
    
    init() {
        loadRecentDestinations()
        loadRecentTrips()
        loadRecentDepartures()
        
        // Migrate existing data
        storageService.migrateRecentDestinations()
        loadRecentTrips() // Reload after migration
    }
    
    func loadRecentDestinations() {
        recentDestinations = storageService.loadRecentDestinations()
    }
    
    func saveDestination(_ destination: String) {
        storageService.saveDestination(destination)
        loadRecentDestinations()
    }
    
    func removeDestination(_ destination: String) {
        storageService.removeDestination(destination)
        loadRecentDestinations()
    }
    
    func resetSelections() {
        selectedDestination = nil
        destinationStationCode = nil
        selectedDeparture = nil
        departureStationCode = nil
        currentTrainId = nil
    }
    
    // MARK: - Trip Management
    func loadRecentTrips() {
        recentTrips = storageService.loadRecentTrips()
    }
    
    func saveCurrentTrip() {
        guard let departure = selectedDeparture,
              let departureCode = departureStationCode,
              let destination = selectedDestination,
              let destinationCode = destinationStationCode ?? Stations.getStationCode(destination) else { return }
        
        storageService.saveTrip(
            departureCode: departureCode,
            departureName: departure,
            destinationCode: destinationCode,
            destinationName: destination
        )
        loadRecentTrips()
    }
    
    func removeTrip(_ trip: TripPair) {
        storageService.removeTrip(trip)
        loadRecentTrips()
    }
    
    // MARK: - Departure Management
    func loadRecentDepartures() {
        recentDepartures = storageService.loadRecentDepartures()
    }
    
    func saveDeparture() {
        guard let departure = selectedDeparture,
              let departureCode = departureStationCode else { return }
        
        storageService.saveDeparture(code: departureCode, name: departure)
        loadRecentDepartures()
    }
    
    func removeDeparture(_ departure: RecentDeparture) {
        var departures = recentDepartures
        departures.removeAll { $0.code == departure.code }
        
        if let encoded = try? JSONEncoder().encode(departures) {
            UserDefaults.standard.set(encoded, forKey: "trackrat.recentDepartures")
        }
        
        loadRecentDepartures()
    }
}