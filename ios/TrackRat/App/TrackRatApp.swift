import SwiftUI
import ActivityKit
import WidgetKit
import UserNotifications
import BackgroundTasks

let BACKGROUND_REFRESH_TASK_ID = "com.trackrat.backgroundrefresh"

@main
struct TrackRatApp: App {
    @StateObject private var appState = AppState()
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @State private var showLaunchScreen = true
    @Environment(\.scenePhase) private var scenePhase
    
    var body: some Scene {
        WindowGroup {
            ZStack {
                if showLaunchScreen {
                    LaunchScreenView {
                        withAnimation(.easeInOut(duration: 0.5)) {
                            showLaunchScreen = false
                        }
                    }
                } else {
                    ContentView()
                        .environmentObject(appState)
                        .preferredColorScheme(.dark)
                        .tint(TrackRatTheme.Colors.accent)
                        .transition(.opacity)
                }
            }
            .onChange(of: scenePhase) { _, newPhase in
                switch newPhase {
                case .active:
                    print("📱 Scene Phase Active: Triggering backend wake-up...")
                    Task {
                        BackendWakeupService.shared.wakeupBackend()
                    }
                case .inactive:
                    print("📱 Scene Phase Inactive")
                case .background:
                    print("📱 Scene Phase Background")
                @unknown default:
                    break
                }
            }
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
        registerBackgroundTasks()
        
        // Wake up backend on app launch
        print("📱 App Launch: Triggering backend wake-up...")
        Task {
            BackendWakeupService.shared.wakeupBackend()
        }
        
        return true
    }

    func registerBackgroundTasks() {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: BACKGROUND_REFRESH_TASK_ID, using: nil) { task in
            self.handleAppRefresh(task: task as! BGAppRefreshTask)
        }
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

    func scheduleAppRefresh() {
        let request = BGAppRefreshTaskRequest(identifier: BACKGROUND_REFRESH_TASK_ID)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60) // 15 minutes from now
        do {
            try BGTaskScheduler.shared.submit(request)
            print("Background refresh task scheduled.")
        } catch {
            print("Could not schedule app refresh: \(error)")
        }
    }

    func handleAppRefresh(task: BGAppRefreshTask) {
        print("Background task started: \(task.identifier)")

        // Schedule the next refresh right away
        scheduleAppRefresh()

        task.expirationHandler = {
            // Handle cleanup, e.g., cancel network requests
            print("Background task expired: \(task.identifier)")
            task.setTaskCompleted(success: false)
        }

        // Ensure there's an active activity to update
        guard let activityAttributes = LiveActivityService.shared.currentActivity?.attributes else {
            print("No active Live Activity to update in background.")
            task.setTaskCompleted(success: true) // No work to do, but task is "complete"
            return
        }

        // It's good practice to store these before starting an async task
        // trainId in attributes is already a String, matching what fetchTrainDetailsFlexible expects for trainNumber
        // let trainIdString = activityAttributes.trainId
        // Guarding Int conversion is not strictly necessary here if APIService.fetchTrainDetailsFlexible expects trainId as String (trainNumber)
        // guard let _ = Int(trainIdString) else {
        //     print("Invalid trainId in Live Activity attributes: \(trainIdString)")
        //     task.setTaskCompleted(success: false)
        //     return
        // }

        print("Performing background fetch for Live Activity: Train \(activityAttributes.trainNumber)")

        Task {
            await LiveActivityService.shared.fetchAndUpdateTrain()
            // The fetchAndUpdateTrain method itself handles errors internally by logging them.
            // We assume success here unless a more specific error handling from fetchAndUpdateTrain is needed.
            print("Background fetch completed for Live Activity: Train \(activityAttributes.trainNumber)")
            task.setTaskCompleted(success: true)
        }
    }

    func cancelAllPendingBackgroundTasks() {
        BGTaskScheduler.shared.cancelAllTaskRequests()
        print("All pending background tasks cancelled.")
    }
    
    func applicationDidEnterBackground(_ application: UIApplication) {
        // Schedule background refresh when app enters background
        scheduleAppRefresh()
    }
    
    func applicationWillEnterForeground(_ application: UIApplication) {
        // Cancel background tasks when returning to foreground
        BGTaskScheduler.shared.cancelAllTaskRequests()
        
        // Wake up backend when coming from background
        print("📱 App Foreground: Triggering backend wake-up...")
        Task {
            BackendWakeupService.shared.wakeupBackend()
        }
        
        // Resume timer-based updates if there's an active Live Activity
        Task {
            await LiveActivityService.shared.refreshCurrentActivity()
        }
    }
    
    func applicationDidBecomeActive(_ application: UIApplication) {
        // This is called more reliably when app becomes active
        print("📱 App Active: Checking if backend wake-up needed...")
        
        // Wake up backend when app becomes active
        Task {
            BackendWakeupService.shared.wakeupBackend()
        }
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
    
    func toggleFavorite(_ trip: TripPair) {
        storageService.toggleFavorite(for: trip)
        loadRecentTrips()
    }
    
    func getFavoriteTrips() -> [TripPair] {
        return recentTrips.filter { $0.isFavorite }
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