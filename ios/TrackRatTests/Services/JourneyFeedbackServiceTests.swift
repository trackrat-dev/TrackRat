import UIKit
import XCTest
@testable import TrackRat

/// Tests for when the "Enjoying TrackRat so far?" prompt is allowed to reappear.
///
/// Issue #1924: tapping "Yes!" recorded nothing, so the prompt came back on every
/// ride even though StoreKit had silently ignored the review request.
@MainActor
final class JourneyFeedbackServiceTests: XCTestCase {

    private let service = JourneyFeedbackService.shared
    private let cooldownDaysKey = "journeyFeedback_cooldownDays"

    override func setUp() {
        super.setUp()
        service.onActivityEnded()
        service.resetCooldowns()
    }

    override func tearDown() {
        service.onActivityEnded()
        service.resetCooldowns()
        super.tearDown()
    }

    /// Starts a Live Activity and reaches departure, then delivers the
    /// foreground notification so the prompt is presented whether the test host
    /// is active (shown immediately) or not (queued until foreground).
    private func rideDeparts() {
        service.onActivityStarted()
        service.onDeparture(trainId: "3923", originCode: "NY", destinationCode: "TR")
        NotificationCenter.default.post(name: UIApplication.didBecomeActiveNotification, object: nil)
    }

    private var recordedCooldownDays: Int {
        UserDefaults.standard.integer(forKey: cooldownDaysKey)
    }

    func testPromptShowsOnDepartureWhenNoCooldown() {
        XCTAssertFalse(service.isInCooldownPeriod(), "resetCooldowns() should clear any cooldown")

        rideDeparts()

        print("shown=\(service.shouldShowFeedbackPrompt) cooldownDays=\(recordedCooldownDays)")
        XCTAssertTrue(service.shouldShowFeedbackPrompt)
    }

    func testPositiveResponseSuppressesPromptOnNextRide() {
        rideDeparts()
        XCTAssertTrue(service.shouldShowFeedbackPrompt)

        service.userRespondedPositively()
        service.onActivityEnded()
        print("after Yes!: cooldownDays=\(recordedCooldownDays) inCooldown=\(service.isInCooldownPeriod())")
        XCTAssertEqual(recordedCooldownDays, 120)
        XCTAssertTrue(service.isInCooldownPeriod())

        rideDeparts()
        XCTAssertFalse(service.shouldShowFeedbackPrompt, "Yes! must not be re-asked on the next ride (#1924)")
    }

    func testSwipeDismissSuppressesPromptOnNextRide() {
        rideDeparts()
        XCTAssertTrue(service.shouldShowFeedbackPrompt)

        // Swiping the sheet away only flips the binding; no response handler runs.
        service.shouldShowFeedbackPrompt = false
        service.onActivityEnded()
        print("after swipe: cooldownDays=\(recordedCooldownDays) inCooldown=\(service.isInCooldownPeriod())")
        XCTAssertEqual(recordedCooldownDays, 8)

        rideDeparts()
        XCTAssertFalse(service.shouldShowFeedbackPrompt, "A swiped-away prompt must not return on the next ride")
    }

    func testCloseButtonKeepsEightDayCooldown() {
        rideDeparts()

        service.userDismissedPrompt()
        print("after X: cooldownDays=\(recordedCooldownDays)")
        XCTAssertFalse(service.shouldShowFeedbackPrompt)
        XCTAssertEqual(recordedCooldownDays, 8)
        XCTAssertTrue(service.isInCooldownPeriod())
    }

    func testNegativeResponseOverridesShownCooldownWithSixteenDays() {
        rideDeparts()

        XCTAssertTrue(service.userRespondedNegatively())
        print("after Not really: cooldownDays=\(recordedCooldownDays)")
        XCTAssertEqual(recordedCooldownDays, 16)
        XCTAssertTrue(service.isInCooldownPeriod())
    }

    func testResetCooldownsAllowsPromptAgain() {
        rideDeparts()
        service.userRespondedPositively()
        service.onActivityEnded()
        XCTAssertTrue(service.isInCooldownPeriod())

        service.resetCooldowns()

        XCTAssertFalse(service.isInCooldownPeriod())
        rideDeparts()
        XCTAssertTrue(service.shouldShowFeedbackPrompt)
    }
}
