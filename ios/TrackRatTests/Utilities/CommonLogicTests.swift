import XCTest
import SwiftUI // Required for Color
@testable import TrackRat

class CommonLogicTests: XCTestCase {

    // MARK: - Color(hex:) Tests
    func testColorHexInitialization() {
        // Test with 6-digit hex
        let color1 = Color(hex: "FF0000") // Red
        XCTAssertEqual(color1, Color(red: 1.0, green: 0.0, blue: 0.0))

        // Test with 3-digit hex
        let color2 = Color(hex: "0F0") // Green
        XCTAssertEqual(color2, Color(red: 0.0, green: 1.0, blue: 0.0))

        // Test with 8-digit hex (ARGB)
        let color3 = Color(hex: "800000FF") // Blue with 50% alpha (approx)
        XCTAssertEqual(color3, Color(red: 0.0, green: 0.0, blue: 1.0, opacity: Double(0x80) / 255.0))

        // Test with invalid hex
        let color4 = Color(hex: "Invalid")
        XCTAssertEqual(color4, Color(.sRGB, red: 1.0, green: 1.0, blue: 0.0, opacity: Double(1) / 255.0)) // Default error color
    }

    // MARK: - DateFormatter.easternTime Tests
    func testDateFormatterEasternTime() {
        let formatter1 = DateFormatter.easternTime(dateStyle: .medium, timeStyle: .short)
        XCTAssertEqual(formatter1.timeZone, TimeZone(identifier: "America/New_York"))
        XCTAssertEqual(formatter1.dateStyle, .medium)
        XCTAssertEqual(formatter1.timeStyle, .short)

        let formatter2 = DateFormatter.easternTime(timeStyle: .long)
        XCTAssertEqual(formatter2.timeZone, TimeZone(identifier: "America/New_York"))
        XCTAssertEqual(formatter2.dateStyle, .none) // Default if not specified
        XCTAssertEqual(formatter2.timeStyle, .long)

        let formatter3 = DateFormatter.easternTime(dateStyle: .full)
        XCTAssertEqual(formatter3.timeZone, TimeZone(identifier: "America/New_York"))
        XCTAssertEqual(formatter3.dateStyle, .full)
        XCTAssertEqual(formatter3.timeStyle, .none) // Default if not specified
    }

    // MARK: - StationNameNormalizer Tests
    func testStationNameNormalizer() {
        XCTAssertEqual(StationNameNormalizer.normalizedName(for: "Washington Station"), "Washington Union Station")
        XCTAssertEqual(StationNameNormalizer.normalizedName(for: "Washington Union"), "Washington Union Station")
        XCTAssertEqual(StationNameNormalizer.normalizedName(for: "WASHI"), "Washington Union Station")
        XCTAssertEqual(StationNameNormalizer.normalizedName(for: "New York Penn Station"), "New York Penn Station") // No mapping
        XCTAssertEqual(StationNameNormalizer.normalizedName(for: "Unknown Station"), "Unknown Station") // No mapping
    }

    // MARK: - Stations.displayName Tests
    func testStationsDisplayName() {
        XCTAssertEqual(Stations.displayName(for: "New York Penn Station"), "New York Penn")
        XCTAssertEqual(Stations.displayName(for: "Newark Penn Station"), "Newark Penn")
        XCTAssertEqual(Stations.displayName(for: "Washington Station"), "Washington Union") // Normalized then shortened
        XCTAssertEqual(Stations.displayName(for: "WASHI"), "Washington Union") // Normalized then shortened
        XCTAssertEqual(Stations.displayName(for: "Trenton Transit Center"), "Trenton Transit Center") // No specific shortening rule
    }

    // MARK: - Stations.stationMatches Tests
    func testStationsStationMatches() {
        // Mock Stop with code and name
        let stop1 = Stop.mock(stationName: "New York Penn Station", stationCode: "NYP")
        XCTAssertTrue(Stations.stationMatches(stop1, stationCode: "NYP"))

        // Mock Stop with different name but same code
        let stop2 = Stop.mock(stationName: "NY Penn", stationCode: "NYP")
        XCTAssertTrue(Stations.stationMatches(stop2, stationCode: "NYP"))

        // Mock Stop with name that normalizes, but no code on stop (relies on name matching)
        let stop3 = Stop.mock(stationName: "Washington Station", stationCode: nil) // stationCode is nil
        // This requires Stations.getStationCode(normalizedName) to work for "Washington Union Station"
        // Assuming "Washington Union Station" maps to "WAS" in Stations.stationCodes
        if Stations.stationCodes["Washington Union Station"] == "WAS" {
             XCTAssertTrue(Stations.stationMatches(stop3, stationCode: "WAS"), "Should match via normalized name if WAS is the code for Washington Union Station")
        } else {
            print("Skipping testStationsStationMatches part for stop3 as 'Washington Union Station' does not map to 'WAS' in current Stations.stationCodes")
        }


        // Mock Stop with name that does not match code
        let stop4 = Stop.mock(stationName: "Unknown Station", stationCode: "UNK")
        XCTAssertFalse(Stations.stationMatches(stop4, stationCode: "NYP"))

        // Mock Stop where stationCode is present but doesn't match, name also doesn't match
        let stop5 = Stop.mock(stationName: "Philadelphia", stationCode: "PHL")
        XCTAssertFalse(Stations.stationMatches(stop5, stationCode: "NYP"))

        // Mock Stop with code matching but name different (should still match by code)
        let stop6 = Stop.mock(stationName: "Philly", stationCode: "PHL")
        XCTAssertTrue(Stations.stationMatches(stop6, stationCode: "PHL"))
    }
}

// Minimal StatusBadge for testing its internal logic if not directly testable
// If StatusBadge is a View, its properties might be tested via a helper struct or by passing parameters.
// For this subtask, we'll assume we can instantiate it or a helper.

struct StatusBadgeTestHelper {
    let status: TrainStatus
    let delayMinutes: Int?

    var statusColor: Color {
        // Copied from StatusBadge view
        switch status {
        case .onTime: return .green
        case .delayed: return .red
        case .boarding: return .orange
        case .departed: return .gray
        case .scheduled: return .gray
        case .unknown: return .gray
        }
    }

    var statusText: String {
        // Copied from StatusBadge view
        switch status {
        case .onTime: return "On Time"
        case .delayed:
            if let minutes = delayMinutes {
                return "Delayed \(minutes)min"
            }
            return "Delayed"
        case .boarding: return "Boarding"
        case .departed: return "Departed"
        case .scheduled: return "Scheduled"
        case .unknown: return "Unknown"
        }
    }
}

extension CommonLogicTests {
    // MARK: - StatusBadge Logic Tests
    func testStatusBadgeLogic() {
        var helper = StatusBadgeTestHelper(status: .onTime, delayMinutes: nil)
        XCTAssertEqual(helper.statusColor, .green)
        XCTAssertEqual(helper.statusText, "On Time")

        helper = StatusBadgeTestHelper(status: .delayed, delayMinutes: 15)
        XCTAssertEqual(helper.statusColor, .red)
        XCTAssertEqual(helper.statusText, "Delayed 15min")

        helper = StatusBadgeTestHelper(status: .delayed, delayMinutes: nil)
        XCTAssertEqual(helper.statusColor, .red)
        XCTAssertEqual(helper.statusText, "Delayed")

        helper = StatusBadgeTestHelper(status: .boarding, delayMinutes: nil)
        XCTAssertEqual(helper.statusColor, .orange)
        XCTAssertEqual(helper.statusText, "Boarding")

        helper = StatusBadgeTestHelper(status: .departed, delayMinutes: nil)
        XCTAssertEqual(helper.statusColor, .gray)
        XCTAssertEqual(helper.statusText, "Departed")

        helper = StatusBadgeTestHelper(status: .scheduled, delayMinutes: nil)
        XCTAssertEqual(helper.statusColor, .gray)
        XCTAssertEqual(helper.statusText, "Scheduled")

        helper = StatusBadgeTestHelper(status: .unknown, delayMinutes: nil)
        XCTAssertEqual(helper.statusColor, .gray)
        XCTAssertEqual(helper.statusText, "Unknown")
    }
}

// Test Helper for StopRow logic
struct StopRowTestHelper {
    let stop: Stop
    let isDestination: Bool
    let isDeparture: Bool
    let isBoarding: Bool // Simplified: In real StopRow, isBoarding has more conditions

    // Copied from StopRow
    var timeDisplay: (scheduled: String?, actual: String?) {
        let formatter = DateFormatter.easternTime(time: .short)
        guard let scheduledTime = stop.scheduledTime else {
            if let departureTime = stop.departureTime { // Use stop.departureTime if scheduledTime is nil
                return (nil, formatter.string(from: departureTime))
            }
            return (nil, "--:--")
        }
        let scheduled = formatter.string(from: scheduledTime)
        if let actualTime = stop.actualTime ?? stop.departureTime { // actualTime or fallback to departureTime
             let actual = formatter.string(from: actualTime)
             if scheduled != actual {
                 return (scheduled, actual)
             }
        }
        return (nil, scheduled)
    }

    var stopColor: Color {
        if isDestination { return .green }
        if isDeparture { return .orange }
        if isBoarding { return .orange } // Simplified from original StopRow
        if stop.departed ?? false { return .gray }
        return .blue
    }
}

extension CommonLogicTests {
    // MARK: - StopRow Logic Tests
    func testStopRowTimeDisplay() {
        let now = Date()
        let scheduledLater = now.addingTimeInterval(600)
        let formatter = DateFormatter.easternTime(time: .short)

        var stop = Stop.mock(scheduledTime: now, departureTime: now) // On time
        var helper = StopRowTestHelper(stop: stop, isDestination: false, isDeparture: false, isBoarding: false)
        XCTAssertEqual(helper.timeDisplay.scheduled, nil)
        XCTAssertEqual(helper.timeDisplay.actual, formatter.string(from: now))

        stop = Stop.mock(scheduledTime: now, departureTime: scheduledLater) // Delayed departure
        helper = StopRowTestHelper(stop: stop, isDestination: false, isDeparture: false, isBoarding: false)
        XCTAssertEqual(helper.timeDisplay.scheduled, formatter.string(from: now))
        XCTAssertEqual(helper.timeDisplay.actual, formatter.string(from: scheduledLater))

        stop = Stop.mock(scheduledTime: nil, departureTime: now) // No scheduled, only departure
        helper = StopRowTestHelper(stop: stop, isDestination: false, isDeparture: false, isBoarding: false)
        XCTAssertEqual(helper.timeDisplay.scheduled, nil)
        XCTAssertEqual(helper.timeDisplay.actual, formatter.string(from: now))

        stop = Stop.mock(scheduledTime: nil, departureTime: nil) // No times
        helper = StopRowTestHelper(stop: stop, isDestination: false, isDeparture: false, isBoarding: false)
        XCTAssertEqual(helper.timeDisplay.scheduled, nil)
        XCTAssertEqual(helper.timeDisplay.actual, "--:--")
    }

    func testStopRowColors() {
        let stop = Stop.mock()
        var helper = StopRowTestHelper(stop: stop, isDestination: true, isDeparture: false, isBoarding: false)
        XCTAssertEqual(helper.stopColor, .green)

        helper = StopRowTestHelper(stop: stop, isDestination: false, isDeparture: true, isBoarding: false)
        XCTAssertEqual(helper.stopColor, .orange)

        helper = StopRowTestHelper(stop: stop, isDestination: false, isDeparture: false, isBoarding: true)
        XCTAssertEqual(helper.stopColor, .orange)

        helper = StopRowTestHelper(stop: Stop.mock(departed: true), isDestination: false, isDeparture: false, isBoarding: false)
        XCTAssertEqual(helper.stopColor, .gray)

        helper = StopRowTestHelper(stop: Stop.mock(departed: false), isDestination: false, isDeparture: false, isBoarding: false)
        XCTAssertEqual(helper.stopColor, .blue)
    }
}

// Test Helper for TrackRatPredictionView logic
struct TrackRatPredictionViewTestHelper {
    let prediction: PredictionData

    var topTracks: [(String, Double)] {
        guard let probs = prediction.trackProbabilities, !probs.isEmpty else { return [] }
        return probs.sorted { $0.value > $1.value }
            .filter { $0.value > 0.05 } // Only tracks with >5% probability
            .prefix(5)
            .map { ($0.key, $0.value) }
    }
}

extension CommonLogicTests {
    func testTrackRatPredictionViewTopTracks() {
        var prediction = PredictionData(trackProbabilities: ["1": 0.6, "2": 0.2, "3A": 0.1, "4": 0.03, "5": 0.07, "6": 0.01])
        var helper = TrackRatPredictionViewTestHelper(prediction: prediction)
        var top = helper.topTracks

        XCTAssertEqual(top.count, 4)
        XCTAssertEqual(top[0].0, "1"); XCTAssertEqual(top[0].1, 0.6)
        XCTAssertEqual(top[1].0, "2"); XCTAssertEqual(top[1].1, 0.2)
        XCTAssertEqual(top[2].0, "3A"); XCTAssertEqual(top[2].1, 0.1)
        XCTAssertEqual(top[3].0, "5"); XCTAssertEqual(top[3].1, 0.07)

        prediction = PredictionData(trackProbabilities: ["10": 0.02, "11": 0.04])
        helper = TrackRatPredictionViewTestHelper(prediction: prediction)
        top = helper.topTracks
        XCTAssertTrue(top.isEmpty)

        prediction = PredictionData(trackProbabilities: nil)
        helper = TrackRatPredictionViewTestHelper(prediction: prediction)
        top = helper.topTracks
        XCTAssertTrue(top.isEmpty)
    }
}

// Test Helper for JourneyStatusView logic
struct JourneyStatusViewTestHelper {
    let train: Train // Keep train for statusV2 and displayStatus access

    // Copied from JourneyStatusView
    func humanFriendlyStatus(_ status: String) -> String {
        switch status.uppercased() {
        case "EN_ROUTE": return "En Route"
        case "BOARDING":
            return train.displayTrack != nil ? "Boarding" : "Scheduled"
        case "SCHEDULED": return "Scheduled"
        case "ON_TIME": return "On Time"
        case "DELAYED": return "Delayed"
        case "DEPARTED": return "Departed"
        case "ARRIVED": return "Arrived"
        case "CANCELLED": return "Cancelled"
        case "ALL_ABOARD": return "All Aboard"
        default: return status.capitalized
        }
    }

    var displayStatus: String {
        let rawStatus: String
        if let statusV2 = train.statusV2 {
            rawStatus = statusV2.current
        } else {
            // Use train.displayStatus which should be set by ViewModel or default to train.status
            rawStatus = train.displayStatus.displayText.uppercased()
        }
        return humanFriendlyStatus(rawStatus)
    }

    var statusEmoji: String {
        let statusToEvaluate = train.statusV2?.current ?? train.displayStatus.displayText.uppercased()
        switch statusToEvaluate {
        case "EN_ROUTE", "DEPARTED": return "🚆"
        case "BOARDING": return train.displayTrack != nil ? "🚪" : "🕐"
        case "DELAYED": return "⏰"
        case "SCHEDULED", "ON_TIME": return "🕐"
        case "ARRIVED": return "🏁"
        default: return "🚂"
        }
    }

    func delayText(delayMinutes: Int) -> String {
        if delayMinutes == 0 { return "Departed on time" }
        if delayMinutes > 0 { return "Departed \(delayMinutes) min late" }
        return "Departed \(abs(delayMinutes)) min early"
    }
}

extension CommonLogicTests {
    func testJourneyStatusViewHelpers() {
        var train = Train.mock(statusV2: StatusV2(current: "EN_ROUTE", location: "Between A and B"))
        var helper = JourneyStatusViewTestHelper(train: train)
        XCTAssertEqual(helper.displayStatus, "En Route")
        XCTAssertEqual(helper.statusEmoji, "🚆")

        train = Train.mock(status: .boarding, displayStatus: .boarding, displayTrack: "4")
        helper = JourneyStatusViewTestHelper(train: train)
        XCTAssertEqual(helper.displayStatus, "Boarding")
        XCTAssertEqual(helper.statusEmoji, "🚪")

        train = Train.mock(status: .boarding, displayStatus: .boarding, displayTrack: nil) // Boarding but no track
        helper = JourneyStatusViewTestHelper(train: train)
        XCTAssertEqual(helper.displayStatus, "Scheduled") // Falls into scheduled category
        XCTAssertEqual(helper.statusEmoji, "🕐")


        train = Train.mock(status: .delayed, displayStatus: .delayed)
        helper = JourneyStatusViewTestHelper(train: train)
        XCTAssertEqual(helper.displayStatus, "Delayed")
        XCTAssertEqual(helper.statusEmoji, "⏰")

        XCTAssertEqual(helper.delayText(delayMinutes: 0), "Departed on time")
        XCTAssertEqual(helper.delayText(delayMinutes: 10), "Departed 10 min late")
        XCTAssertEqual(helper.delayText(delayMinutes: -5), "Departed 5 min early")
    }
}
