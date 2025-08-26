import Foundation
import SwiftUI

/// Service for handling deep links and URL navigation
@MainActor
class DeepLinkService: ObservableObject {
    static let shared = DeepLinkService()
    
    private init() {}
    
    /// Handle an incoming URL and set up deep link state for navigation
    func handle(url: URL, appState: AppState) {
        print("🔗 Deep link received: \(url)")
        
        // Parse the deep link
        guard let deepLink = DeepLink(url: url) else {
            print("❌ Failed to parse deep link URL")
            return
        }
        
        print("✅ Deep link parsed - Train Number: \(deepLink.trainId)")
        
        // Set deep link state for MapContainerView to handle
        appState.deepLinkTrainNumber = deepLink.trainId
        appState.deepLinkFromStation = deepLink.fromStationCode
        appState.deepLinkToStation = deepLink.toStationCode
        appState.shouldExpandForDeepLink = true
        
        // Set up context for proper display
        if let fromCode = deepLink.fromStationCode {
            appState.departureStationCode = fromCode
            // Find the station name for the code
            if let stationName = Stations.stationCodes.first(where: { $0.value == fromCode })?.key {
                appState.selectedDeparture = stationName
                print("🚉 Set departure: \(stationName) (\(fromCode))")
            }
        }
        
        if let toCode = deepLink.toStationCode {
            appState.destinationStationCode = toCode
            // Find the station name for the code
            if let stationName = Stations.stationCodes.first(where: { $0.value == toCode })?.key {
                appState.selectedDestination = stationName
                print("🎯 Set destination: \(stationName) (\(toCode))")
            }
        }
        
        // Create route for map display
        if let fromCode = deepLink.fromStationCode, 
           let toCode = deepLink.toStationCode,
           let fromName = appState.selectedDeparture,
           let toName = appState.selectedDestination {
            appState.selectedRoute = TripPair(
                departureCode: fromCode,
                departureName: fromName,
                destinationCode: toCode,
                destinationName: toName
            )
            print("🗺️ Set route for map display: \(fromCode) → \(toCode)")
        }
        
        print("✅ Deep link state configured - MapContainerView will handle navigation")
    }
    
    /// Handle URL when app is already running (onOpenURL)
    func handleOpenURL(_ url: URL, appState: AppState) {
        handle(url: url, appState: appState)
    }
    
    /// Handle URL when app is launched from a deep link
    func handleLaunchURL(_ url: URL, appState: AppState) {
        // Delay slightly to ensure app state is ready
        Task {
            try await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds
            handle(url: url, appState: appState)
        }
    }
    
    /// Check if a URL is a valid TrackRat deep link
    func isValidDeepLink(_ url: URL) -> Bool {
        return DeepLink(url: url) != nil
    }
    
    /// Extract train information from a URL for preview purposes
    func extractTrainInfo(from url: URL) -> (trainId: String, from: String?, to: String?)? {
        guard let deepLink = DeepLink(url: url) else { return nil }
        
        let fromName = deepLink.fromStationCode.flatMap { code in
            Stations.stationCodes.first(where: { $0.value == code })?.key
        }
        
        let toName = deepLink.toStationCode.flatMap { code in
            Stations.stationCodes.first(where: { $0.value == code })?.key
        }
        
        return (deepLink.trainId, fromName, toName)
    }
}