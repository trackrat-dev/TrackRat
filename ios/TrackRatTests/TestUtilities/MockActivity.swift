import Foundation
import ActivityKit
import UserNotifications // For AlertConfiguration
@testable import TrackRat

// Mock implementation of TRActivityProtocol for testing.
@available(iOS 16.1, *)
class MockActivity<A: ActivityAttributes>: TRActivityProtocol {
    typealias Attributes = A

    // Settable properties for test setup
    var attributes: Attributes
    var content: ActivityContent<A.ContentState>
    var id: String
    var activityState: ActivityState
    var pushToken: Data?

    // Captured parameters for assertions
    private(set) var updateCalledCount: Int = 0
    private(set) var lastUpdatedContent: ActivityContent<A.ContentState>?
    private(set) var lastAlertConfiguration: AlertConfiguration?
    private(set) var lastUpdatedState: A.ContentState?
    private(set) var lastStaleDate: Date?


    private(set) var endCalledCount: Int = 0
    private(set) var lastEndedContent: ActivityContent<A.ContentState>?
    private(set) var lastEndedState: A.ContentState?
    private(set) var lastDismissalPolicy: ActivityUIDismissalPolicy?
    // private(set) var lastEndOptions: Activity<A>.EndOptions? // Removed as per protocol update

    // Initializer
    init(
        attributes: Attributes,
        initialContent: ActivityContent<A.ContentState>,
        id: String = UUID().uuidString, // Default to a UUID string
        initialActivityState: ActivityState = .active,
        pushToken: Data? = "mockPushToken".data(using: .utf8)
    ) {
        self.attributes = attributes
        self.content = initialContent
        self.id = id
        self.activityState = initialActivityState
        self.pushToken = pushToken
    }

    // TRActivityProtocol Methods
    func update(_ newContent: ActivityContent<A.ContentState>, alertConfiguration: AlertConfiguration?) async {
        updateCalledCount += 1
        self.content = newContent // Update internal content to reflect the change
        lastUpdatedContent = newContent
        lastAlertConfiguration = alertConfiguration
        // Also update lastUpdatedState from the newContent
        lastUpdatedState = newContent.state
        // lastStaleDate = newContent.staleDate // If ActivityContent had staleDate directly
    }

    func update(state: Attributes.ContentState, staleDate: Date?, alertConfiguration: AlertConfiguration?) async {
        updateCalledCount += 1
        // Update internal content state
        self.content = ActivityContent(state: state, staleDate: staleDate ?? self.content.staleDate, relevanceScore: self.content.relevanceScore)
        lastUpdatedState = state
        lastStaleDate = staleDate
        lastAlertConfiguration = alertConfiguration
        // Also update lastUpdatedContent from this state
        lastUpdatedContent = self.content
    }

    func end(_ finalContent: ActivityContent<A.ContentState>?, dismissalPolicy: ActivityUIDismissalPolicy) async {
        endCalledCount += 1
        if let finalContent = finalContent {
            self.content = finalContent // Update internal content
            lastEndedState = finalContent.state
        } else {
            lastEndedState = nil
        }
        lastEndedContent = finalContent
        lastDismissalPolicy = dismissalPolicy
        self.activityState = .ended // Simulate activity ending
    }

    func end(state: Attributes.ContentState?, dismissalPolicy: ActivityUIDismissalPolicy) async {
        endCalledCount += 1
        lastEndedState = state
        lastDismissalPolicy = dismissalPolicy
        if let state = state {
            self.content = ActivityContent(state: state, staleDate: Date(), relevanceScore: self.content.relevanceScore)
            lastEndedContent = self.content
        } else {
            lastEndedContent = nil
        }
        self.activityState = .ended // Simulate activity ending
    }

    // Helper to reset call counts and captured values for new test assertions
    func resetCaptureFlags() {
        updateCalledCount = 0
        lastUpdatedContent = nil
        lastAlertConfiguration = nil
        lastUpdatedState = nil
        lastStaleDate = nil

        endCalledCount = 0
        lastEndedContent = nil
        lastDismissalPolicy = nil
        lastEndedState = nil
        // lastEndOptions = nil // Removed
    }
}
