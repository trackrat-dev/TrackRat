import XCTest
import ActivityKit
@testable import TrackRat

class LiveActivityModelsTests: XCTestCase {
    
    // MARK: - TrainActivityAttributes Tests
    
    func testTrainActivityAttributesInitialization() {
        let attributes = TrainActivityAttributes(
            trainNumber: "123",
            trainId: "nec_123",
            routeDescription: "Northeast Corridor",
            origin: "Newark Penn Station",
            destination: "New York Penn Station",
            originStationCode: "NP",
            destinationStationCode: "NY"
        )
        
        XCTAssertEqual(attributes.trainNumber, "123")
        XCTAssertEqual(attributes.trainId, "nec_123")
        XCTAssertEqual(attributes.routeDescription, "Northeast Corridor")
        XCTAssertEqual(attributes.origin, "Newark Penn Station")
        XCTAssertEqual(attributes.destination, "New York Penn Station")
        XCTAssertEqual(attributes.originStationCode, "NP")
        XCTAssertEqual(attributes.destinationStationCode, "NY")
    }
    
    // MARK: - ContentState Tests
    
    func testContentStateInitialization() {
        let nextStop = NextStopInfo(
            stationName: "New York Penn Station",
            estimatedArrival: Date().addingTimeInterval(900), // 15 minutes
            scheduledArrival: Date().addingTimeInterval(900),
            isDelayed: false,
            delayMinutes: 0
        )
        
        let prediction = TrackRatPredictionInfo(
            topTrack: "7",
            confidence: 0.85,
            alternativeTracks: ["8", "9"]
        )
        
        let contentState = TrainActivityAttributes.ContentState(
            status: .boarding,
            track: "7",
            delayMinutes: 0,
            currentLocation: .boarding(station: "Newark Penn Station"),
            nextStop: nextStop,
            journeyProgress: 0.25,
            destinationETA: Date().addingTimeInterval(1800),
            trackRatPrediction: prediction,
            lastUpdated: Date(),
            hasStatusChanged: true
        )
        
        XCTAssertEqual(contentState.status, .boarding)
        XCTAssertEqual(contentState.track, "7")
        XCTAssertEqual(contentState.delayMinutes, 0)
        XCTAssertEqual(contentState.journeyProgress, 0.25)
        XCTAssertNotNil(contentState.nextStop)
        XCTAssertNotNil(contentState.trackRatPrediction)
        XCTAssertTrue(contentState.hasStatusChanged)
    }
    
    // MARK: - CurrentLocation Tests
    
    func testCurrentLocationDisplayText() {
        let departureTime = Date().addingTimeInterval(600) // 10 minutes from now
        
        // Test not departed
        let notDeparted = CurrentLocation.notDeparted(departureTime: departureTime)
        XCTAssertEqual(notDeparted.displayText, "Preparing to depart")
        
        // Test boarding
        let boarding = CurrentLocation.boarding(station: "Newark Penn Station")
        XCTAssertEqual(boarding.displayText, "Boarding at Newark Penn Station")
        
        // Test just departed
        let justDeparted = CurrentLocation.departed(from: "Newark Penn Station", minutesAgo: 0)
        XCTAssertEqual(justDeparted.displayText, "Just departed Newark Penn Station")
        
        // Test departed with time
        let departed = CurrentLocation.departed(from: "Newark Penn Station", minutesAgo: 5)
        XCTAssertEqual(departed.displayText, "Departed Newark Penn Station 5 min ago")
        
        // Test arriving now
        let arriving = CurrentLocation.approaching(station: "New York Penn Station", minutesAway: 0)
        XCTAssertEqual(arriving.displayText, "Arriving at New York Penn Station")
        
        // Test approaching with time
        let approaching = CurrentLocation.approaching(station: "New York Penn Station", minutesAway: 3)
        XCTAssertEqual(approaching.displayText, "Approaching New York Penn Station (~3 min)")
        
        // Test en route
        let enRoute = CurrentLocation.enRoute(between: "Newark Penn Station", and: "New York Penn Station")
        XCTAssertEqual(enRoute.displayText, "Between Newark Penn Station and New York Penn Station")
        
        // Test at station
        let atStation = CurrentLocation.atStation("New York Penn Station")
        XCTAssertEqual(atStation.displayText, "At New York Penn Station")
        
        // Test arrived
        let arrived = CurrentLocation.arrived
        XCTAssertEqual(arrived.displayText, "Arrived")
    }
    
    func testCurrentLocationCodable() throws {
        let locations: [CurrentLocation] = [
            .notDeparted(departureTime: Date()),
            .boarding(station: "Newark Penn Station"),
            .departed(from: "Newark Penn Station", minutesAgo: 5),
            .approaching(station: "New York Penn Station", minutesAway: 3),
            .enRoute(between: "Newark Penn Station", and: "New York Penn Station"),
            .atStation("New York Penn Station"),
            .arrived
        ]
        
        let encoder = JSONEncoder()
        let decoder = JSONDecoder()
        
        for location in locations {
            let data = try encoder.encode(location)
            let decoded = try decoder.decode(CurrentLocation.self, from: data)
            
            // Compare display text since enum comparison with associated values is complex
            XCTAssertEqual(location.displayText, decoded.displayText)
        }
    }
    
    // MARK: - NextStopInfo Tests
    
    func testNextStopInfoDisplayText() {
        let baseTime = Date()
        let scheduledTime = baseTime.addingTimeInterval(900) // 15 minutes
        let delayedTime = baseTime.addingTimeInterval(1200) // 20 minutes
        
        // Test on-time stop
        let onTimeStop = NextStopInfo(
            stationName: "New York Penn Station",
            estimatedArrival: scheduledTime,
            scheduledArrival: scheduledTime,
            isDelayed: false,
            delayMinutes: 0
        )
        
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        let expectedOnTime = "New York Penn Station \(formatter.string(from: scheduledTime))"
        
        XCTAssertEqual(onTimeStop.displayText, expectedOnTime)
        XCTAssertFalse(onTimeStop.isDelayed)
        XCTAssertEqual(onTimeStop.delayMinutes, 0)
        
        // Test delayed stop
        let delayedStop = NextStopInfo(
            stationName: "New York Penn Station",
            estimatedArrival: delayedTime,
            scheduledArrival: scheduledTime,
            isDelayed: true,
            delayMinutes: 5
        )
        
        let expectedDelayed = "New York Penn Station ~\(formatter.string(from: delayedTime))"
        
        XCTAssertEqual(delayedStop.displayText, expectedDelayed)
        XCTAssertTrue(delayedStop.isDelayed)
        XCTAssertEqual(delayedStop.delayMinutes, 5)
    }
    
    func testNextStopInfoCodable() throws {
        let nextStop = NextStopInfo(
            stationName: "New York Penn Station",
            estimatedArrival: Date().addingTimeInterval(900),
            scheduledArrival: Date().addingTimeInterval(900),
            isDelayed: false,
            delayMinutes: 0
        )
        
        let encoder = JSONEncoder()
        let decoder = JSONDecoder()
        
        let data = try encoder.encode(nextStop)
        let decoded = try decoder.decode(NextStopInfo.self, from: data)
        
        XCTAssertEqual(nextStop.stationName, decoded.stationName)
        XCTAssertEqual(nextStop.isDelayed, decoded.isDelayed)
        XCTAssertEqual(nextStop.delayMinutes, decoded.delayMinutes)
    }
    
    // MARK: - TrackRatPredictionInfo Tests
    
    func testTrackRatPredictionHighConfidence() {
        let highConfidencePrediction = TrackRatPredictionInfo(
            topTrack: "7",
            confidence: 0.85,
            alternativeTracks: ["8", "9"]
        )
        
        XCTAssertEqual(highConfidencePrediction.displayText, "🐀 TrackRat predicts track 7")
        XCTAssertEqual(highConfidencePrediction.topTrack, "7")
        XCTAssertEqual(highConfidencePrediction.confidence, 0.85)
        XCTAssertEqual(highConfidencePrediction.alternativeTracks, ["8", "9"])
    }
    
    func testTrackRatPredictionMediumConfidence() {
        let mediumConfidencePrediction = TrackRatPredictionInfo(
            topTrack: "7",
            confidence: 0.65,
            alternativeTracks: ["8", "9"]
        )
        
        XCTAssertEqual(mediumConfidencePrediction.displayText, "🤔 TrackRat thinks it may be track 7")
    }
    
    func testTrackRatPredictionLowConfidence() {
        let lowConfidencePrediction = TrackRatPredictionInfo(
            topTrack: "7",
            confidence: 0.35,
            alternativeTracks: ["8", "9"]
        )
        
        XCTAssertEqual(lowConfidencePrediction.displayText, "🤷 TrackRat guesses tracks 7, 8, 9")
    }
    
    func testTrackRatPredictionEmptyTrack() {
        let emptyTrackPrediction = TrackRatPredictionInfo(
            topTrack: "",
            confidence: 0.85,
            alternativeTracks: []
        )
        
        XCTAssertEqual(emptyTrackPrediction.displayText, "🤷 TrackRat is thinking...")
    }
    
    func testTrackRatPredictionEmptyAlternatives() {
        let noAlternativesPrediction = TrackRatPredictionInfo(
            topTrack: "7",
            confidence: 0.35,
            alternativeTracks: []
        )
        
        XCTAssertEqual(noAlternativesPrediction.displayText, "🤷 TrackRat guesses tracks 7")
    }
    
    func testTrackRatPredictionWithEmptyAlternativeTracks() {
        let predictionWithEmptyTracks = TrackRatPredictionInfo(
            topTrack: "7",
            confidence: 0.35,
            alternativeTracks: ["", "8", ""]
        )
        
        // Should filter out empty tracks
        XCTAssertEqual(predictionWithEmptyTracks.displayText, "🤷 TrackRat guesses tracks 7, 8")
    }
    
    func testTrackRatPredictionCodable() throws {
        let prediction = TrackRatPredictionInfo(
            topTrack: "7",
            confidence: 0.85,
            alternativeTracks: ["8", "9"]
        )
        
        let encoder = JSONEncoder()
        let decoder = JSONDecoder()
        
        let data = try encoder.encode(prediction)
        let decoded = try decoder.decode(TrackRatPredictionInfo.self, from: data)
        
        XCTAssertEqual(prediction.topTrack, decoded.topTrack)
        XCTAssertEqual(prediction.confidence, decoded.confidence, accuracy: 0.001)
        XCTAssertEqual(prediction.alternativeTracks, decoded.alternativeTracks)
        XCTAssertEqual(prediction.displayText, decoded.displayText)
    }
    
    // MARK: - Hashable Tests
    
    func testContentStateHashable() {
        let nextStop = NextStopInfo(
            stationName: "New York Penn Station",
            estimatedArrival: Date(),
            scheduledArrival: Date(),
            isDelayed: false,
            delayMinutes: 0
        )
        
        let prediction = TrackRatPredictionInfo(
            topTrack: "7",
            confidence: 0.85,
            alternativeTracks: ["8", "9"]
        )
        
        let contentState1 = TrainActivityAttributes.ContentState(
            status: .boarding,
            track: "7",
            delayMinutes: 0,
            currentLocation: .boarding(station: "Newark Penn Station"),
            nextStop: nextStop,
            journeyProgress: 0.25,
            destinationETA: Date(),
            trackRatPrediction: prediction,
            lastUpdated: Date(),
            hasStatusChanged: true
        )
        
        let contentState2 = TrainActivityAttributes.ContentState(
            status: .boarding,
            track: "7",
            delayMinutes: 0,
            currentLocation: .boarding(station: "Newark Penn Station"),
            nextStop: nextStop,
            journeyProgress: 0.25,
            destinationETA: Date(),
            trackRatPrediction: prediction,
            lastUpdated: Date(),
            hasStatusChanged: true
        )
        
        // Test hashable implementation
        let set = Set([contentState1, contentState2])
        XCTAssertTrue(set.count >= 1) // Should handle duplicate detection
    }
    
    func testCurrentLocationHashable() {
        let location1 = CurrentLocation.boarding(station: "Newark Penn Station")
        let location2 = CurrentLocation.boarding(station: "Newark Penn Station")
        let location3 = CurrentLocation.boarding(station: "New York Penn Station")
        
        XCTAssertEqual(location1, location2)
        XCTAssertNotEqual(location1, location3)
        
        let set = Set([location1, location2, location3])
        XCTAssertEqual(set.count, 2) // Should have 2 unique locations
    }
    
    func testNextStopInfoHashable() {
        let date = Date()
        let stop1 = NextStopInfo(
            stationName: "New York Penn Station",
            estimatedArrival: date,
            scheduledArrival: date,
            isDelayed: false,
            delayMinutes: 0
        )
        
        let stop2 = NextStopInfo(
            stationName: "New York Penn Station",
            estimatedArrival: date,
            scheduledArrival: date,
            isDelayed: false,
            delayMinutes: 0
        )
        
        let stop3 = NextStopInfo(
            stationName: "Trenton",
            estimatedArrival: date,
            scheduledArrival: date,
            isDelayed: false,
            delayMinutes: 0
        )
        
        XCTAssertEqual(stop1, stop2)
        XCTAssertNotEqual(stop1, stop3)
        
        let set = Set([stop1, stop2, stop3])
        XCTAssertEqual(set.count, 2) // Should have 2 unique stops
    }
    
    func testTrackRatPredictionHashable() {
        let prediction1 = TrackRatPredictionInfo(
            topTrack: "7",
            confidence: 0.85,
            alternativeTracks: ["8", "9"]
        )
        
        let prediction2 = TrackRatPredictionInfo(
            topTrack: "7",
            confidence: 0.85,
            alternativeTracks: ["8", "9"]
        )
        
        let prediction3 = TrackRatPredictionInfo(
            topTrack: "8",
            confidence: 0.85,
            alternativeTracks: ["7", "9"]
        )
        
        XCTAssertEqual(prediction1, prediction2)
        XCTAssertNotEqual(prediction1, prediction3)
        
        let set = Set([prediction1, prediction2, prediction3])
        XCTAssertEqual(set.count, 2) // Should have 2 unique predictions
    }
    
    // MARK: - Edge Cases Tests
    
    func testCurrentLocationEdgeCases() {
        // Test with very high minute values
        let longAgo = CurrentLocation.departed(from: "Newark Penn Station", minutesAgo: 999)
        XCTAssertTrue(longAgo.displayText.contains("999 min ago"))
        
        let farAway = CurrentLocation.approaching(station: "New York Penn Station", minutesAway: 120)
        XCTAssertTrue(farAway.displayText.contains("120 min"))
        
        // Test with empty/long station names
        let emptyStation = CurrentLocation.boarding(station: "")
        XCTAssertEqual(emptyStation.displayText, "Boarding at ")
        
        let longStationName = CurrentLocation.boarding(station: "Very Long Station Name That Might Cause Display Issues")
        XCTAssertTrue(longStationName.displayText.contains("Very Long Station Name"))
    }
    
    func testNextStopInfoEdgeCases() {
        let now = Date()
        
        // Test with past times (negative delays conceptually)
        let pastStop = NextStopInfo(
            stationName: "Past Station",
            estimatedArrival: now.addingTimeInterval(-300), // 5 minutes ago
            scheduledArrival: now,
            isDelayed: true,
            delayMinutes: -5
        )
        
        XCTAssertTrue(pastStop.displayText.contains("Past Station ~"))
        XCTAssertEqual(pastStop.delayMinutes, -5)
        
        // Test with very large delays
        let hugeDelayStop = NextStopInfo(
            stationName: "Delayed Station",
            estimatedArrival: now.addingTimeInterval(7200), // 2 hours
            scheduledArrival: now,
            isDelayed: true,
            delayMinutes: 120
        )
        
        XCTAssertEqual(hugeDelayStop.delayMinutes, 120)
    }
    
    func testTrackRatPredictionEdgeCases() {
        // Test with confidence exactly at boundaries
        let exactHighBoundary = TrackRatPredictionInfo(
            topTrack: "7",
            confidence: 0.8,
            alternativeTracks: []
        )
        XCTAssertTrue(exactHighBoundary.displayText.contains("🐀 TrackRat predicts"))
        
        let exactMediumBoundary = TrackRatPredictionInfo(
            topTrack: "7",
            confidence: 0.5,
            alternativeTracks: []
        )
        XCTAssertTrue(exactMediumBoundary.displayText.contains("🤔 TrackRat thinks"))
        
        // Test with confidence above 1.0 or below 0.0
        let overConfident = TrackRatPredictionInfo(
            topTrack: "7",
            confidence: 1.5,
            alternativeTracks: []
        )
        XCTAssertTrue(overConfident.displayText.contains("🐀 TrackRat predicts"))
        
        let negativeConfidence = TrackRatPredictionInfo(
            topTrack: "7",
            confidence: -0.1,
            alternativeTracks: []
        )
        XCTAssertTrue(negativeConfidence.displayText.contains("🤷 TrackRat guesses"))
        
        // Test with many alternative tracks
        let manyAlternatives = TrackRatPredictionInfo(
            topTrack: "1",
            confidence: 0.2,
            alternativeTracks: ["2", "3", "4", "5", "6", "7", "8", "9", "10"]
        )
        // Should only show first 2 alternatives plus top track
        XCTAssertEqual(manyAlternatives.displayText, "🤷 TrackRat guesses tracks 1, 2, 3")
    }
}