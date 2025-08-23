import Foundation
import SwiftUI

/// RatSense: Intelligent journey suggestion service that predicts the user's most likely trip
final class RatSenseService: ObservableObject {
    static let shared = RatSenseService()
    
    @Published var suggestedJourney: SuggestedJourney?
    
    private let userDefaults = UserDefaults.standard
    private let homeStationKey = "RatSense.homeStation"
    private let workStationKey = "RatSense.workStation"
    private let lastJourneyKey = "RatSense.lastJourney"
    private let stationPairFrequencyKey = "RatSense.stationPairFrequency"
    private let liveActivityHistoryKey = "RatSense.liveActivityHistory"
    
    struct SuggestedJourney: Equatable {
        let fromStation: String
        let toStation: String
        let fromStationName: String
        let toStationName: String
        
        init(from: String, to: String) {
            self.fromStation = from
            self.toStation = to
            self.fromStationName = Stations.displayName(for: from) ?? from
            self.toStationName = Stations.displayName(for: to) ?? to
        }
    }
    
    private struct LastJourney: Codable {
        let fromStation: String
        let toStation: String
        let timestamp: Date
    }
    
    private struct LiveActivityRecord: Codable {
        let fromStation: String
        let toStation: String
        let timestamp: Date
    }
    
    private init() {
        print("🐀🐀🐀 RatSense: Service INITIALIZED (singleton created)")
        printCurrentState()
        updateSuggestion()
    }
    
    private func printCurrentState() {
        print("🐀 RatSense: === Current State ===")
        print("🐀 RatSense: Home Station: \(getHomeStation() ?? "not set")")
        print("🐀 RatSense: Work Station: \(getWorkStation() ?? "not set")")
        
        if let lastJourney = getLastJourney() {
            let formatter = DateFormatter()
            formatter.dateStyle = .short
            formatter.timeStyle = .short
            print("🐀 RatSense: Last Journey: \(lastJourney.fromStation) → \(lastJourney.toStation) at \(formatter.string(from: lastJourney.timestamp))")
        } else {
            print("🐀 RatSense: Last Journey: none")
        }
        
        let history = getLiveActivityHistory()
        print("🐀 RatSense: Live Activity History: \(history.count) records")
        
        let frequency = getStationPairFrequency()
        print("🐀 RatSense: Station Pairs: \(frequency.count) unique pairs")
        print("🐀 RatSense: ===================")
    }
    
    // MARK: - Public Methods
    
    /// Updates the suggested journey based on current context
    func updateSuggestion() {
        print("🐀 RatSense: Updating suggestion...")
        suggestedJourney = calculateSuggestion()
        if let suggestion = suggestedJourney {
            print("🐀✨ RatSense: Final suggestion: \(suggestion.fromStation) → \(suggestion.toStation)")
        } else {
            print("🐀❌ RatSense: No suggestion available")
        }
    }
    
    /// Records a journey search
    func recordJourneySearch(from: String, to: String) {
        print("🐀 RatSense: Recording journey search: \(from) → \(to)")
        
        // Save last journey
        let journey = LastJourney(fromStation: from, toStation: to, timestamp: Date())
        if let encoded = try? JSONEncoder().encode(journey) {
            userDefaults.set(encoded, forKey: lastJourneyKey)
            print("🐀 RatSense: Saved as last journey")
        }
        
        // Update frequency
        updateStationPairFrequency(from: from, to: to)
        
        // Removed: detectCommutePatterns call that was causing issues
        // The auto-detection was overwriting user's manual selections
    }
    
    /// Records when a Live Activity is started
    func recordLiveActivityStart(from: String, to: String) {
        print("🐀 RatSense: Recording Live Activity start: \(from) → \(to)")
        
        let record = LiveActivityRecord(fromStation: from, toStation: to, timestamp: Date())
        
        // Keep only last 10 Live Activity records
        var history = getLiveActivityHistory()
        history.append(record)
        if history.count > 10 {
            history = Array(history.suffix(10))
        }
        
        if let encoded = try? JSONEncoder().encode(history) {
            userDefaults.set(encoded, forKey: liveActivityHistoryKey)
            print("🐀 RatSense: Saved to Live Activity history (now \(history.count) records)")
        }
    }
    
    /// Sets the user's home station
    func setHomeStation(_ station: String?) {
        print("🐀🐀🐀 RatSense: Setting home station to: \(station ?? "nil")")
        if let station = station {
            userDefaults.set(station, forKey: homeStationKey)
            userDefaults.synchronize() // Force save
            print("🐀 RatSense: Home station saved as: \(station)")
        } else {
            userDefaults.removeObject(forKey: homeStationKey)
        }
        updateSuggestion()
    }
    
    /// Sets the user's work station
    func setWorkStation(_ station: String?) {
        print("🐀🐀🐀 RatSense: Setting work station to: \(station ?? "nil")")
        if let station = station {
            userDefaults.set(station, forKey: workStationKey)
            userDefaults.synchronize() // Force save
            print("🐀 RatSense: Work station saved as: \(station)")
        } else {
            userDefaults.removeObject(forKey: workStationKey)
        }
        updateSuggestion()
    }
    
    /// Gets the user's home station
    func getHomeStation() -> String? {
        userDefaults.string(forKey: homeStationKey)
    }
    
    /// Gets the user's work station
    func getWorkStation() -> String? {
        userDefaults.string(forKey: workStationKey)
    }
    
    /// Checks if a station code is the user's home or work station
    func isHomeOrWorkStation(_ stationCode: String) -> Bool {
        return getHomeStation() == stationCode || getWorkStation() == stationCode
    }
    
    /// Debug: Adds test data for development
    func addTestData() {
        print("🐀 RatSense: Adding test data...")
        
        // Add some journey searches
        recordJourneySearch(from: "OG", to: "NY")
        recordJourneySearch(from: "NY", to: "OG")
        recordJourneySearch(from: "OG", to: "NY")
        
        // Set home and work
        setHomeStation("OG")
        setWorkStation("NY")
        
        print("🐀 RatSense: Test data added")
        updateSuggestion()
    }
    
    /// Debug: Clears all Rat Sense data
    func clearAllData() {
        print("🐀 RatSense: Clearing all data...")
        userDefaults.removeObject(forKey: homeStationKey)
        userDefaults.removeObject(forKey: workStationKey)
        userDefaults.removeObject(forKey: lastJourneyKey)
        userDefaults.removeObject(forKey: stationPairFrequencyKey)
        userDefaults.removeObject(forKey: liveActivityHistoryKey)
        suggestedJourney = nil
        print("🐀 RatSense: All data cleared")
    }
    
    // MARK: - Private Methods
    
    private func calculateSuggestion() -> SuggestedJourney? {
        print("🐀 RatSense: Starting calculation...")
        
        // 1. Check Recent Context (Highest Priority)
        print("🐀 RatSense: Step 1 - Checking recent context...")
        if let recentSuggestion = checkRecentContext() {
            print("🐀 RatSense: ✅ Found recent context suggestion")
            return recentSuggestion
        }
        print("🐀 RatSense: No recent context found")
        
        // 2. Apply Time-Based Logic (if home/work stations set)
        print("🐀 RatSense: Step 2 - Checking time-based logic...")
        if let timeSuggestion = applyTimeBasedLogic() {
            print("🐀 RatSense: ✅ Found time-based suggestion")
            return timeSuggestion
        }
        print("🐀 RatSense: No time-based suggestion available")
        
        
        print("🐀 RatSense: ❌ No suggestion could be generated")
        return nil
    }
    
    private func checkRecentContext() -> SuggestedJourney? {
        let now = Date()
        
        // Check last journey search
        if let lastJourney = getLastJourney() {
            let timeSinceSearch = now.timeIntervalSince(lastJourney.timestamp)
            let hours = timeSinceSearch / 3600
            print("🐀 RatSense: Last journey: \(lastJourney.fromStation) → \(lastJourney.toStation), \(String(format: "%.1f", hours)) hours ago")
            
            // If searched within last 20 minutes → Suggest same route
            if timeSinceSearch < 1200 { // 20 minutes
                print("🐀 RatSense: Within 20 minutes, suggesting same route")
                return SuggestedJourney(from: lastJourney.fromStation, to: lastJourney.toStation)
            }
        } else {
            print("🐀 RatSense: No last journey found")
        }
        
        // Check Live Activity history
        let liveActivityHistory = getLiveActivityHistory()
        print("🐀 RatSense: Found \(liveActivityHistory.count) Live Activity records")
        
        for record in liveActivityHistory.reversed() {
            let timeSinceLiveActivity = now.timeIntervalSince(record.timestamp)
            let hours = timeSinceLiveActivity / 3600
            print("🐀 RatSense: Live Activity: \(record.fromStation) → \(record.toStation), \(String(format: "%.1f", hours)) hours ago")
            
            // If Live Activity activated 2-8 hours ago → Suggest reversed route
            if timeSinceLiveActivity >= 7200 && timeSinceLiveActivity <= 28800 { // 2-8 hours
                print("🐀 RatSense: Between 2-8 hours, suggesting reversed route")
                return SuggestedJourney(from: record.toStation, to: record.fromStation)
            }
        }
        
        return nil
    }
    
    private func applyTimeBasedLogic() -> SuggestedJourney? {
        let homeStation = getHomeStation()
        let workStation = getWorkStation()
        
        print("🐀 RatSense: Home station: \(homeStation ?? "not set"), Work station: \(workStation ?? "not set")")
        
        guard let home = homeStation,
              let work = workStation else {
            print("🐀 RatSense: Home/work stations not set, skipping time-based logic")
            return nil
        }
        
        let calendar = Calendar.current
        let now = Date()
        let hour = calendar.component(.hour, from: now)
        let isWeekday = !calendar.isDateInWeekend(now)
        
        let formatter = DateFormatter()
        formatter.dateFormat = "EEEE HH:mm"
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        let etHour = calendar.dateComponents(in: TimeZone(identifier: "America/New_York")!, from: now).hour ?? hour
        print("🐀 RatSense: Current time: \(formatter.string(from: now)) ET (hour in ET: \(etHour), weekday: \(isWeekday))")
        
        // Morning commute (5am-10am ET) - weekdays and weekends
        if etHour >= 5 && etHour < 10 {
            print("🐀 RatSense: Morning commute time (ET), suggesting home → work")
            return SuggestedJourney(from: home, to: work)
        }
        
        // Evening commute (1pm-8pm ET) - weekdays and weekends  
        if etHour >= 13 && etHour < 20 {
            print("🐀 RatSense: Evening commute time (ET), suggesting work → home")
            return SuggestedJourney(from: work, to: home)
        }
        
        // Midday (10am-1pm ET) - check if at work
        if etHour >= 10 && etHour < 13 {
            if let lastJourney = getLastJourney(),
               lastJourney.toStation == work {
                print("🐀 RatSense: Midday and last journey ended at work, suggesting early departure")
                return SuggestedJourney(from: work, to: home)
            } else {
                print("🐀 RatSense: Midday but not confirmed at work")
            }
        }
        
        return nil
    }
    
    
    private func getLastJourney() -> LastJourney? {
        guard let data = userDefaults.data(forKey: lastJourneyKey),
              let journey = try? JSONDecoder().decode(LastJourney.self, from: data) else {
            return nil
        }
        return journey
    }
    
    private func getLiveActivityHistory() -> [LiveActivityRecord] {
        guard let data = userDefaults.data(forKey: liveActivityHistoryKey),
              let history = try? JSONDecoder().decode([LiveActivityRecord].self, from: data) else {
            return []
        }
        return history
    }
    
    private func getStationPairFrequency() -> [String: Int] {
        userDefaults.dictionary(forKey: stationPairFrequencyKey) as? [String: Int] ?? [:]
    }
    
    private func updateStationPairFrequency(from: String, to: String) {
        var frequency = getStationPairFrequency()
        let key = "\(from)_\(to)"
        frequency[key] = (frequency[key] ?? 0) + 1
        userDefaults.set(frequency, forKey: stationPairFrequencyKey)
    }
}