import Foundation
import ActivityKit
import UserNotifications // For AlertConfiguration

@available(iOS 16.1, *)
class ConcreteActivity<A: ActivityAttributes>: TRActivityProtocol {
    typealias Attributes = A

    private let activity: Activity<A>

    init(activity: Activity<A>) {
        self.activity = activity
    }

    var attributes: A {
        activity.attributes
    }

    var content: ActivityContent<A.ContentState> {
        activity.content
    }

    var id: String {
        activity.id
    }

    var activityState: ActivityState {
        activity.activityState
    }

    var pushToken: Data? {
        activity.pushToken
    }

    func update(_ newContent: ActivityContent<A.ContentState>, alertConfiguration: AlertConfiguration?) async {
        // The original Activity.update takes ActivityContent directly.
        // For some reason, the template had (using contentState:). Correcting to match ActivityKit.
        await activity.update(newContent, alertConfiguration: alertConfiguration)
    }

    func update(state: Attributes.ContentState, staleDate: Date? = nil, alertConfiguration: AlertConfiguration? = nil) async {
        let activityContent = ActivityContent(state: state, staleDate: staleDate ?? Date(), relevanceScore: 0.0) // Default relevance, adjust if needed
        await activity.update(activityContent, alertConfiguration: alertConfiguration)
    }

    // Corrected to match the updated TRActivityProtocol (no options parameter)
    func end(_ finalContent: ActivityContent<A.ContentState>?, dismissalPolicy: ActivityUIDismissalPolicy) async {
        await activity.end(finalContent, dismissalPolicy: dismissalPolicy)
    }

    func end(state: Attributes.ContentState?, dismissalPolicy: ActivityUIDismissalPolicy) async {
        let finalContent: ActivityContent<A.ContentState>?
        if let finalState = state {
            finalContent = ActivityContent(state: finalState, staleDate: Date(), relevanceScore: 0.0) // Default relevance
        } else {
            finalContent = nil
        }
        await activity.end(finalContent, dismissalPolicy: dismissalPolicy)
    }
}

@available(iOS 16.1, *)
class ConcreteActivityKitModule: TRActivityKitModuleProtocol {

    func request<A: ActivityAttributes>(
        attributes: A,
        content: ActivityContent<A.ContentState>,
        pushType: PushType?
    ) async throws -> (any TRActivityProtocol)? where A.ContentState : Decodable, A.ContentState : Encodable, A.ContentState : Sendable {
        let realActivity = try await Activity<A>.request(
            attributes: attributes,
            content: content,
            pushType: pushType
        )
        return ConcreteActivity(activity: realActivity)
    }

    var activities: [any TRActivityProtocol] {
        // This needs to map Activity<SomeAttributes> to an array of ConcreteActivity or TRActivityProtocol
        // Since activities can be of different Attribute types, we need to handle this.
        // For LiveActivityService, it seems to only care about TrainActivityAttributes.
        // So, we can filter for that type.

        // If TrainActivityAttributes is the only type used by LiveActivityService for its *own* activities:
        return Activity<TrainActivityAttributes>.activities.map { ConcreteActivity(activity: $0) }

        // If we needed a truly generic list of *all* activities of *any* type wrapped:
        // This is more complex and might not be needed if LiveActivityService is specific.
        // For now, assuming specificity to TrainActivityAttributes for the 'activities' list is sufficient
        // as LiveActivityService primarily manages its own TrainActivity.
    }

    func authorizationInfo() -> ActivityAuthorizationInfo {
        return ActivityAuthorizationInfo()
    }

    // If endAllActivities was part of the protocol:
    // func endAllActivities(content: ActivityContent<ActivityAttributes.ContentState>?, dismissalPolicy: ActivityUIDismissalPolicy) async {
    //     await Activity.endAll(content, dismissalPolicy: dismissalPolicy)
    // }
}
