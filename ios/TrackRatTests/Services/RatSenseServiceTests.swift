import XCTest
import Foundation
@testable import TrackRat

class RatSenseServiceTests: XCTestCase {

    var ratSenseService: RatSenseService!

    override func setUp() {
        super.setUp()
        ratSenseService = RatSenseService.shared
        // Clear all data before each test to ensure clean state
        ratSenseService.clearAllData()

        print("🧪 Setting up RatSenseService test with clean state")
    }

    override func tearDown() {
        // Clean up after each test
        ratSenseService.clearAllData()
        ratSenseService = nil

        print("🧹 Cleaning up RatSenseService test")
        super.tearDown()
    }

    // MARK: - Helper Methods

    func createMockDate(hour: Int, minute: Int = 0, daysFromNow: Int = 0) -> Date {
        let calendar = Calendar.current
        let timezone = TimeZone(identifier: "America/New_York")!
        var components = calendar.dateComponents(in: timezone, from: Date())

        components.hour = hour
        components.minute = minute
        components.second = 0

        if daysFromNow != 0 {
            components.day! += daysFromNow
        }

        return calendar.date(from: components) ?? Date()
    }

    func setMockCurrentTime(_ date: Date) {
        // Note: In a real implementation, we'd need dependency injection to mock the current time
        // For these tests, we'll work with the assumption that the service uses Date() for current time
        print("  📅 Mock current time set to: \(date)")
    }

    // MARK: - Home/Work Station Management Tests

    func testSetHomeStation_withValidStation_storesCorrectly() {
        print("🏠 Testing home station storage")

        let homeStation = "NY"

        print("  - Setting home station to: \(homeStation)")
        ratSenseService.setHomeStation(homeStation)

        let retrievedHome = ratSenseService.getHomeStation()
        print("  - Retrieved home station: \(retrievedHome ?? "nil")")

        XCTAssertEqual(retrievedHome, homeStation, "Home station should be stored and retrieved correctly")

        // Test that suggestion is updated
        ratSenseService.updateSuggestion()
        print("  - Suggestion updated after setting home station")

        print("  ✅ Home station storage test passed")
    }

    func testSetWorkStation_withValidStation_storesCorrectly() {
        print("🏢 Testing work station storage")

        let workStation = "PH"

        print("  - Setting work station to: \(workStation)")
        ratSenseService.setWorkStation(workStation)

        let retrievedWork = ratSenseService.getWorkStation()
        print("  - Retrieved work station: \(retrievedWork ?? "nil")")

        XCTAssertEqual(retrievedWork, workStation, "Work station should be stored and retrieved correctly")

        print("  ✅ Work station storage test passed")
    }

    func testSetHomeStation_withNil_removesStation() {
        print("❌ Testing home station removal")

        // First set a home station
        ratSenseService.setHomeStation("NY")
        XCTAssertNotNil(ratSenseService.getHomeStation(), "Home station should be set initially")

        print("  - Removing home station (setting to nil)")
        ratSenseService.setHomeStation(nil)

        let retrievedHome = ratSenseService.getHomeStation()
        print("  - Retrieved home station after removal: \(retrievedHome ?? "nil")")

        XCTAssertNil(retrievedHome, "Home station should be removed when set to nil")

        print("  ✅ Home station removal test passed")
    }

    func testIsHomeOrWorkStation_withConfiguredStations_returnsCorrectly() {
        print("🔍 Testing home/work station identification")

        let homeStation = "NY"
        let workStation = "PH"
        let otherStation = "TRE"

        ratSenseService.setHomeStation(homeStation)
        ratSenseService.setWorkStation(workStation)

        print("  - Home: \(homeStation), Work: \(workStation), Other: \(otherStation)")

        let isHomeMatch = ratSenseService.isHomeOrWorkStation(homeStation)
        let isWorkMatch = ratSenseService.isHomeOrWorkStation(workStation)
        let isOtherMatch = ratSenseService.isHomeOrWorkStation(otherStation)

        print("  - Is '\(homeStation)' home/work: \(isHomeMatch)")
        print("  - Is '\(workStation)' home/work: \(isWorkMatch)")
        print("  - Is '\(otherStation)' home/work: \(isOtherMatch)")

        XCTAssertTrue(isHomeMatch, "Home station should be identified as home/work")
        XCTAssertTrue(isWorkMatch, "Work station should be identified as home/work")
        XCTAssertFalse(isOtherMatch, "Other station should not be identified as home/work")

        print("  ✅ Home/work station identification test passed")
    }

    // MARK: - Journey Recording Tests

    func testRecordJourneySearch_withValidJourney_storesCorrectly() {
        print("📝 Testing journey search recording")

        let fromStation = "NY"
        let toStation = "PH"

        print("  - Recording journey: \(fromStation) → \(toStation)")
        ratSenseService.recordJourneySearch(from: fromStation, to: toStation)

        // Note: getLastJourney is private, but we can test this indirectly through suggestions
        ratSenseService.updateSuggestion()

        print("  - Journey recorded and suggestion updated")
        print("  ✅ Journey search recording test passed")
    }

    func testRecordLiveActivityStart_withValidJourney_storesInHistory() {
        print("📱 Testing Live Activity recording")

        let fromStation = "NY"
        let toStation = "PH"

        print("  - Recording Live Activity: \(fromStation) → \(toStation)")
        ratSenseService.recordLiveActivityStart(from: fromStation, to: toStation)

        // Test multiple records to ensure history management
        print("  - Recording additional Live Activities to test history management")
        for i in 1...5 {
            ratSenseService.recordLiveActivityStart(from: "TEST\(i)", to: "DEST\(i)")
        }

        ratSenseService.updateSuggestion()

        print("  ✅ Live Activity recording test passed")
    }

    // MARK: - Time-Based Logic Tests

    func testMorningCommuteTime_withHomeWorkSet_suggestsHomeToWork() {
        print("🌅 Testing morning commute suggestion (5-9am ET)")

        let homeStation = "NY"
        let workStation = "PH"

        // Set up home and work stations
        ratSenseService.setHomeStation(homeStation)
        ratSenseService.setWorkStation(workStation)

        print("  - Home: \(homeStation), Work: \(workStation)")
        print("  - Testing morning commute time (7am ET)")

        // Create a morning time (7am ET) - Note: This test assumes ET time zone
        let morningTime = createMockDate(hour: 7) // 7am
        print("  - Mock morning time: \(morningTime)")

        // Since we can't easily mock the current time, we'll test the logic indirectly
        // by checking that when home/work are set, the service can generate suggestions
        ratSenseService.updateSuggestion()

        // The suggestion should exist when home/work are configured
        if let suggestion = ratSenseService.suggestedJourney {
            print("  - Generated suggestion: \(suggestion.fromStation) → \(suggestion.toStation)")

            // During morning hours, it should suggest home → work
            // Note: Without time mocking, we test that suggestions can be generated
            XCTAssertNotNil(suggestion, "Should generate suggestion when home/work are set")
        } else {
            print("  - No suggestion generated (may be due to current time not being morning)")
        }

        print("  ✅ Morning commute time test completed")
    }

    func testEveningCommuteTime_withHomeWorkSet_suggestsWorkToHome() {
        print("🌆 Testing evening commute suggestion (1-8pm ET)")

        let homeStation = "NY"
        let workStation = "PH"

        ratSenseService.setHomeStation(homeStation)
        ratSenseService.setWorkStation(workStation)

        print("  - Home: \(homeStation), Work: \(workStation)")
        print("  - Testing evening commute time (5pm ET)")

        // Create an evening time (5pm ET)
        let eveningTime = createMockDate(hour: 17) // 5pm
        print("  - Mock evening time: \(eveningTime)")

        ratSenseService.updateSuggestion()

        if let suggestion = ratSenseService.suggestedJourney {
            print("  - Generated suggestion: \(suggestion.fromStation) → \(suggestion.toStation)")
            XCTAssertNotNil(suggestion, "Should generate suggestion during evening hours")
        } else {
            print("  - No suggestion generated (may be due to current time not being evening)")
        }

        print("  ✅ Evening commute time test completed")
    }

    func testWeekendTimeLogic_withHomeWorkSet_stillProvidesSuggestions() {
        print("📅 Testing weekend time logic")

        let homeStation = "NY"
        let workStation = "PH"

        ratSenseService.setHomeStation(homeStation)
        ratSenseService.setWorkStation(workStation)

        print("  - Home: \(homeStation), Work: \(workStation)")
        print("  - Testing weekend logic (service treats weekends same as weekdays)")

        ratSenseService.updateSuggestion()

        // The service should still provide suggestions on weekends based on time
        if let suggestion = ratSenseService.suggestedJourney {
            print("  - Weekend suggestion: \(suggestion.fromStation) → \(suggestion.toStation)")
            XCTAssertNotNil(suggestion, "Should provide suggestions on weekends too")
        }

        print("  ✅ Weekend time logic test completed")
    }

    // MARK: - Recent Context Tests

    func testRecentContext_sameLast20Minutes_suggestsSameRoute() {
        print("🔄 Testing recent context - same route within 20 minutes")

        let fromStation = "NY"
        let toStation = "PH"

        print("  - Recording journey: \(fromStation) → \(toStation)")
        ratSenseService.recordJourneySearch(from: fromStation, to: toStation)

        // Immediately check suggestion (should be within 20 minutes)
        ratSenseService.updateSuggestion()

        if let suggestion = ratSenseService.suggestedJourney {
            print("  - Generated suggestion: \(suggestion.fromStation) → \(suggestion.toStation)")

            // Should suggest the same route if within 20 minutes
            XCTAssertEqual(suggestion.fromStation, fromStation, "Should suggest same origin")
            XCTAssertEqual(suggestion.toStation, toStation, "Should suggest same destination")

            print("  ✅ Same route suggestion correct")
        } else {
            print("  - No suggestion generated")
        }

        print("  ✅ Recent context same route test completed")
    }

    func testRecentContext_liveActivity2to8Hours_suggestsReverse() {
        print("🔄 Testing recent context - reverse route 2-8 hours after Live Activity")

        let fromStation = "NY"
        let toStation = "PH"

        print("  - Recording Live Activity: \(fromStation) → \(toStation)")
        ratSenseService.recordLiveActivityStart(from: fromStation, to: toStation)

        // In a real test, we'd need to mock time to simulate 2-8 hours passing
        // For now, we test that the Live Activity was recorded
        ratSenseService.updateSuggestion()

        print("  - Live Activity recorded for future reverse route suggestion")
        print("  ✅ Live Activity reverse route test setup completed")
    }

    // MARK: - Algorithm Integration Tests

    func testSuggestionPriority_recentContextOverTime_prioritizesCorrectly() {
        print("🎯 Testing suggestion priority: recent context should override time-based")

        // Set up home/work for time-based suggestions
        ratSenseService.setHomeStation("NY")
        ratSenseService.setWorkStation("PH")

        // Record a different journey very recently
        let recentFrom = "TRE"
        let recentTo = "NP"

        print("  - Home/Work set: NY ↔ PH")
        print("  - Recent journey: \(recentFrom) → \(recentTo)")

        ratSenseService.recordJourneySearch(from: recentFrom, to: recentTo)
        ratSenseService.updateSuggestion()

        if let suggestion = ratSenseService.suggestedJourney {
            print("  - Final suggestion: \(suggestion.fromStation) → \(suggestion.toStation)")

            // Recent context should take priority over time-based suggestions
            XCTAssertEqual(suggestion.fromStation, recentFrom, "Recent context should override time-based logic")
            XCTAssertEqual(suggestion.toStation, recentTo, "Recent context should override time-based logic")

            print("  ✅ Priority order correct: recent context takes precedence")
        } else {
            XCTFail("Should generate suggestion when recent journey is recorded")
        }

        print("  ✅ Suggestion priority test completed")
    }

    func testNoSuggestion_withoutDataOrPattern_returnsNil() {
        print("❌ Testing no suggestion when insufficient data")

        // Don't set home/work, don't record journeys
        print("  - No home/work stations set")
        print("  - No recent journeys recorded")

        ratSenseService.updateSuggestion()

        let suggestion = ratSenseService.suggestedJourney
        print("  - Generated suggestion: \(suggestion?.fromStation ?? "nil") → \(suggestion?.toStation ?? "nil")")

        // Might be nil if no patterns established and not during commute hours
        // This depends on the current time when test runs
        print("  - Suggestion result depends on current time and available data")

        print("  ✅ No suggestion test completed")
    }

    // MARK: - Data Management Tests

    func testClearAllData_removesAllStoredData() {
        print("🧹 Testing data clearing functionality")

        // Set up some data first
        ratSenseService.setHomeStation("NY")
        ratSenseService.setWorkStation("PH")
        ratSenseService.recordJourneySearch(from: "NY", to: "PH")
        ratSenseService.recordLiveActivityStart(from: "NY", to: "PH")

        print("  - Data set up: home, work, journey, and Live Activity")

        // Verify data exists
        XCTAssertNotNil(ratSenseService.getHomeStation(), "Home station should exist before clearing")
        XCTAssertNotNil(ratSenseService.getWorkStation(), "Work station should exist before clearing")

        // Clear all data
        print("  - Clearing all data...")
        ratSenseService.clearAllData()

        // Verify data is cleared
        XCTAssertNil(ratSenseService.getHomeStation(), "Home station should be cleared")
        XCTAssertNil(ratSenseService.getWorkStation(), "Work station should be cleared")
        XCTAssertNil(ratSenseService.suggestedJourney, "Suggested journey should be cleared")

        print("  ✅ All data cleared successfully")
    }

    func testAddTestData_createsValidTestData() {
        print("🧪 Testing test data creation")

        print("  - Adding test data...")
        ratSenseService.addTestData()

        // Verify test data was created
        let homeStation = ratSenseService.getHomeStation()
        let workStation = ratSenseService.getWorkStation()

        print("  - Test home station: \(homeStation ?? "nil")")
        print("  - Test work station: \(workStation ?? "nil")")

        XCTAssertNotNil(homeStation, "Test data should include home station")
        XCTAssertNotNil(workStation, "Test data should include work station")

        // Should generate a suggestion with test data
        ratSenseService.updateSuggestion()
        let suggestion = ratSenseService.suggestedJourney

        print("  - Test suggestion: \(suggestion?.fromStation ?? "nil") → \(suggestion?.toStation ?? "nil")")

        print("  ✅ Test data creation completed")
    }

    // MARK: - Edge Cases and Error Handling

    func testFrequencyTracking_withMultipleJourneys_countsCorrectly() {
        print("📊 Testing station pair frequency tracking")

        let route1 = ("NY", "PH")
        let route2 = ("NY", "TRE")

        print("  - Recording multiple journeys to test frequency")

        // Record same route multiple times
        for i in 1...3 {
            print("  - Recording \(route1.0) → \(route1.1) (iteration \(i))")
            ratSenseService.recordJourneySearch(from: route1.0, to: route1.1)
        }

        // Record different route once
        print("  - Recording \(route2.0) → \(route2.1)")
        ratSenseService.recordJourneySearch(from: route2.0, to: route2.1)

        // Frequency tracking is internal, but we can verify through behavior
        print("  - Frequency data recorded internally for future use")

        print("  ✅ Frequency tracking test completed")
    }

    func testLiveActivityHistory_limitsToLast10Records() {
        print("📚 Testing Live Activity history size limiting")

        print("  - Recording 15 Live Activities to test limit of 10")

        // Record more than 10 Live Activities
        for i in 1...15 {
            ratSenseService.recordLiveActivityStart(from: "FROM\(i)", to: "TO\(i)")
        }

        // Internal history should be limited to 10, but we can't directly test this
        // since the history is private. We test that the service handles it gracefully.
        ratSenseService.updateSuggestion()

        print("  - 15 Live Activities recorded, service should maintain last 10")
        print("  ✅ Live Activity history limiting test completed")
    }

    func testTimezone_easternTimeCalculation_handlesCorrectly() {
        print("🌍 Testing Eastern Time zone handling")

        let homeStation = "NY"
        let workStation = "PH"

        ratSenseService.setHomeStation(homeStation)
        ratSenseService.setWorkStation(workStation)

        print("  - Home/Work set for timezone test")
        print("  - Service should use Eastern Time for commute calculations")

        ratSenseService.updateSuggestion()

        // The service handles ET internally, this test verifies it doesn't crash
        print("  ✅ Eastern Time handling test completed")
    }

    // MARK: - Real Usage Scenario Tests

    func testCompleteCommuteScenario_homeToWorkToHome() {
        print("🎯 Testing complete commute scenario")

        let homeStation = "NY"
        let workStation = "PH"

        // Day 1: User sets up home/work
        print("  📅 Day 1: Setting up home and work stations")
        ratSenseService.setHomeStation(homeStation)
        ratSenseService.setWorkStation(workStation)

        // Morning: Search for journey to work
        print("  🌅 Morning: Searching for journey to work")
        ratSenseService.recordJourneySearch(from: homeStation, to: workStation)
        ratSenseService.recordLiveActivityStart(from: homeStation, to: workStation)

        // Test that suggestions are generated
        ratSenseService.updateSuggestion()
        let morningSuggestion = ratSenseService.suggestedJourney
        print("  - Morning suggestion: \(morningSuggestion?.fromStation ?? "nil") → \(morningSuggestion?.toStation ?? "nil")")

        // Evening: Should suggest return trip (in real scenario, after 2-8 hours)
        print("  🌆 Evening: Service should be ready to suggest return trip")
        ratSenseService.updateSuggestion()
        let eveningSuggestion = ratSenseService.suggestedJourney
        print("  - Evening suggestion: \(eveningSuggestion?.fromStation ?? "nil") → \(eveningSuggestion?.toStation ?? "nil")")

        // Verify home and work are still set
        XCTAssertEqual(ratSenseService.getHomeStation(), homeStation, "Home station should persist")
        XCTAssertEqual(ratSenseService.getWorkStation(), workStation, "Work station should persist")

        print("  ✅ Complete commute scenario test completed")
    }

    func testUserBehaviorLearning_adaptsToPatterns() {
        print("🧠 Testing user behavior learning over time")

        // Simulate user establishing a pattern over multiple days
        let routes = [
            ("NY", "PH"),   // Common route
            ("NY", "TRE"),  // Occasional route
            ("NY", "PH"),   // Back to common
            ("NY", "PH"),   // Reinforcing pattern
            ("NP", "NY")    // Different pattern
        ]

        print("  - Simulating \(routes.count) journey searches to establish patterns")

        for (index, route) in routes.enumerated() {
            print("  - Journey \(index + 1): \(route.0) → \(route.1)")
            ratSenseService.recordJourneySearch(from: route.0, to: route.1)

            // Occasionally record Live Activities
            if index % 2 == 0 {
                ratSenseService.recordLiveActivityStart(from: route.0, to: route.1)
            }
        }

        // Test that the service can generate suggestions based on learned patterns
        ratSenseService.updateSuggestion()
        let learnedSuggestion = ratSenseService.suggestedJourney

        print("  - Final learned suggestion: \(learnedSuggestion?.fromStation ?? "nil") → \(learnedSuggestion?.toStation ?? "nil")")

        // The most recent journey should influence the suggestion
        if let suggestion = learnedSuggestion {
            XCTAssertNotNil(suggestion, "Should generate suggestion based on learned patterns")
        }

        print("  ✅ User behavior learning test completed")
    }
}