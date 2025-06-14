import Foundation
import ActivityKit

@testable import TrackRat // To get TRActivityProtocol and other necessary types

// Mock implementation of TRActivityKitModuleProtocol for testing.
@available(iOS 16.1, *)
class MockActivityKitModule: TRActivityKitModuleProtocol {

    // --- Request Mocking ---
    var requestShouldThrowError: Error?
    var requestShouldReturnNilActivity: Bool = false
    // Store the last parameters passed to request() for verification
    private(set) var lastRequestedAttributes: Any?
    private(set) var lastRequestedContent: Any? // ActivityContent<Attributes.ContentState>
    private(set) var lastPushType: PushType?
    // The mock activity to return on successful request
    var mockActivityToReturn: (any TRActivityProtocol)?

    func request<Attributes: ActivityAttributes>(
        attributes: Attributes,
        content: ActivityContent<Attributes.ContentState>,
        pushType: PushType?
    ) async throws -> (any TRActivityProtocol)? where Attributes.ContentState : Decodable, Attributes.ContentState : Encodable, Attributes.ContentState : Sendable {

        lastRequestedAttributes = attributes
        lastRequestedContent = content // Storing ActivityContent
        lastPushType = pushType

        if let error = requestShouldThrowError {
            throw error
        }

        if requestShouldReturnNilActivity {
             // This case is tricky as the protocol expects a non-nil return unless error.
             // For testing a nil return from the module itself (if that's a valid scenario),
             // we'd need to adjust the protocol or handle it carefully in LiveActivityService.
             // The protocol currently returns `any TRActivityProtocol` (non-optional).
             // To test LiveActivityService's nil guard, the mock itself would return nil,
             // which means the protocol should be `-> (any TRActivityProtocol)?`
             // For now, let's assume if nil is to be tested, it means the `request` itself might return nil,
             // so the protocol should be `-> (any TRActivityProtocol)?`.
             // *Self-correction*: The original subtask specified `-> TRActivityProtocol?` for the module protocol.
             // The implementation in LiveActivityService then guards this. So, returning nil is fine.
            return nil
        }

        if let activityToReturn = mockActivityToReturn {
            // Ensure the attributes type matches if possible, though type erasure handles some of this.
            // This is primarily for ensuring the test setup is correct.
            if let typedActivity = activityToReturn as? MockActivity<Attributes> {
                 // If it's already the correct MockActivity generic type
                return typedActivity
            } else if type(of: activityToReturn.attributes) == type(of: attributes) {
                // If attributes type match, but it's not MockActivity<Attributes> (e.g. any TRActivityProtocol)
                return activityToReturn
            } else {
                 fatalError("MockActivityKitModule.mockActivityToReturn is not of the correct generic type or its attributes do not match.")
            }
        }

        // Default: Create a new MockActivity if none is provided to return
        // This ensures that if `request` is called, it returns *something* unless configured to throw/return nil.
        let newMockActivity = MockActivity(attributes: attributes, initialContent: content)
        self.mockActivityToReturn = newMockActivity // Store it so subsequent calls might get the same one if needed by test logic
        return newMockActivity
    }

    // --- Activities List Mocking ---
    var activitiesToReturn: [any TRActivityProtocol] = []
    var activities: [any TRActivityProtocol] {
        return activitiesToReturn
    }

    // --- AuthorizationInfo Mocking ---
    var mockAuthorizationInfo = ActivityAuthorizationInfo() // Default instance
    func authorizationInfo() -> ActivityAuthorizationInfo {
        return mockAuthorizationInfo
    }

    // --- Other static methods ---
    // Example: func endAllActivities(...) if added to protocol

    // Helper to reset state
    func reset() {
        requestShouldThrowError = nil
        requestShouldReturnNilActivity = false
        lastRequestedAttributes = nil
        lastRequestedContent = nil
        lastPushType = nil
        mockActivityToReturn = nil
        activitiesToReturn = []
        mockAuthorizationInfo = ActivityAuthorizationInfo() // Reset to default
    }
}
