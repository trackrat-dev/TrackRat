import Foundation
import ActivityKit
import UserNotifications // For AlertConfiguration, if needed by Activity methods

// Availability for all ActivityKit related code
@available(iOS 16.1, *)
protocol TRActivityProtocol {
    associatedtype Attributes: ActivityAttributes

    var attributes: Attributes { get }
    // Using ActivityContent directly as it's a standard structure.
    var content: ActivityContent<Attributes.ContentState> { get }
    var id: String { get }
    var activityState: ActivityState { get } // Added for observing state
    var pushToken: Data? { get } // Added for push token observation

    // Methods matching ActivityKit.Activity
    // Note: ActivityKit's update is on `ActivityContent<State>` not just `State`
    func update(_ content: ActivityContent<Attributes.ContentState>, alertConfiguration: AlertConfiguration?) async

    // Simpler update if only state changes, matching common usage.
    // The concrete wrapper can handle creating ActivityContent from state.
    func update(state: Attributes.ContentState, staleDate: Date?, alertConfiguration: AlertConfiguration?) async

    // Corrected to match ActivityKit.Activity.end(content:dismissalPolicy:)
    func end(_ content: ActivityContent<Attributes.ContentState>?, dismissalPolicy: ActivityUIDismissalPolicy) async

    // Simpler end, if only final state and dismissal policy are needed.
    // The concrete wrapper can handle creating ActivityContent from state.
    func end(state: Attributes.ContentState?, dismissalPolicy: ActivityUIDismissalPolicy) async
}

@available(iOS 16.1, *)
protocol TRActivityKitModuleProtocol {
    // Mirroring Activity.request()
    // Returning our protocol type. Using 'any TRActivityProtocol' for type erasure.
    // The generic constraint on Attributes is important.
    func request<Attributes: ActivityAttributes>(
        attributes: Attributes,
        content: ActivityContent<Attributes.ContentState>, // Using ActivityContent directly
        pushType: PushType?
    ) async throws -> (any TRActivityProtocol)? where Attributes.ContentState: Codable & Sendable

    // Mirroring Activity.activities
    // Array of our protocol type.
    var activities: [any TRActivityProtocol] { get }

    // Mirroring ActivityAuthorizationInfo() constructor/properties
    // This could also be a separate protocol if ActivityAuthorizationInfo has many methods/properties used.
    // For now, returning the concrete type is fine as it's a simple struct.
    func authorizationInfo() -> ActivityAuthorizationInfo

    // Example for other static methods if needed by LiveActivityService.
    // For instance, if LiveActivityService needed to end all activities of a certain type:
    // func endAll<A: ActivityAttributes>(ofType type: A.Type, content: ActivityContent<A.ContentState>?, dismissalPolicy: ActivityUIDismissalPolicy) async

    // A simplified version if LiveActivityService only ends its own current activity type
    // and doesn't need to iterate or end activities of other types.
    // However, LiveActivityService.endCurrentActivity() calls activity.end(), so this might not be needed here.
    // If there was a "terminate all my type activities" it would go here.
}
