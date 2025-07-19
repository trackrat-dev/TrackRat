import Foundation
import SwiftUI

/// Service for handling deep links and URL navigation
@MainActor
class DeepLinkService: ObservableObject {
    static let shared = DeepLinkService()
    
    private init() {}
    
    /// Handle an incoming URL and navigate to the appropriate screen
    func handle(url: URL, appState: AppState) {
        print("🔗 Deep link received: \(url)")
        
        // Parse the deep link
        guard let deepLink = DeepLink(url: url) else {
            print("❌ Invalid deep link format: \(url)")
            return
        }
        
        print("✅ Deep link parsed - Train ID: \(deepLink.trainId)")
        
        // Set up app state for context
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
        
        // Navigate to train details using the flexible navigation
        let destination = NavigationDestination.trainDetailsFlexible(
            trainNumber: deepLink.trainId,
            fromStation: deepLink.fromStationCode
        )
        
        // Clear existing navigation and push to train details
        appState.navigationPath = NavigationPath()
        appState.navigationPath.append(destination)
        
        print("🧭 Navigated to train details for \(deepLink.trainId)")
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