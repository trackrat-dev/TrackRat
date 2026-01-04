import Foundation
import StoreKit
import UIKit

/// Service that manages prompting users for feedback during their train journey.
/// Shows a feedback prompt at 2/3 journey completion, with a 30-day cooldown if dismissed.
@MainActor
class JourneyFeedbackService: ObservableObject {
    static let shared = JourneyFeedbackService()

    // MARK: - Published State

    /// When true, the UI should present the feedback prompt
    @Published var shouldShowFeedbackPrompt: Bool = false

    /// Context for the current journey (used for feedback submission)
    @Published var currentJourneyContext: JourneyFeedbackContext?

    // MARK: - Private State

    /// Tracks whether we've already prompted during this Live Activity session
    private var hasPromptedDuringCurrentActivity: Bool = false

    /// Whether a prompt is queued for when the app returns to foreground
    private var promptQueuedForForeground: Bool = false

    // MARK: - UserDefaults Keys

    private let lastPromptDismissedDateKey = "journeyFeedback_lastPromptDismissedDate"
    private let cooldownDays: Int = 30

    // MARK: - Progress Threshold

    /// The journey progress threshold at which we prompt for feedback (2/3)
    private let feedbackThreshold: Double = 0.666

    private init() {
        // Observe app becoming active to show queued prompts
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(appDidBecomeActive),
            name: UIApplication.didBecomeActiveNotification,
            object: nil
        )
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
    }

    // MARK: - Public API

    /// Called when a new Live Activity starts. Resets the per-activity prompt state.
    func onActivityStarted() {
        hasPromptedDuringCurrentActivity = false
        promptQueuedForForeground = false
        currentJourneyContext = nil
    }

    /// Called when a Live Activity ends. Clears any pending state.
    func onActivityEnded() {
        hasPromptedDuringCurrentActivity = false
        promptQueuedForForeground = false
        shouldShowFeedbackPrompt = false
        currentJourneyContext = nil
    }

    /// Called on each progress update to check if we should prompt for feedback.
    /// - Parameters:
    ///   - progress: The current journey progress (0.0 to 1.0)
    ///   - trainId: The train ID
    ///   - originCode: Origin station code
    ///   - destinationCode: Destination station code
    func checkProgressMilestone(
        progress: Double,
        trainId: String,
        originCode: String,
        destinationCode: String
    ) {
        // Skip if we've already prompted during this activity
        guard !hasPromptedDuringCurrentActivity else { return }

        // Skip if we haven't reached the threshold yet
        guard progress >= feedbackThreshold else { return }

        // Skip if we're in cooldown period
        guard !isInCooldownPeriod() else {
            print("📊 Journey feedback: Skipping prompt (in cooldown period)")
            return
        }

        // Mark that we've handled the prompt for this activity
        hasPromptedDuringCurrentActivity = true

        // Store context for the feedback form
        currentJourneyContext = JourneyFeedbackContext(
            trainId: trainId,
            originCode: originCode,
            destinationCode: destinationCode
        )

        // Check if app is in foreground
        if UIApplication.shared.applicationState == .active {
            print("📊 Journey feedback: Showing prompt (app active, progress: \(progress))")
            shouldShowFeedbackPrompt = true
        } else {
            print("📊 Journey feedback: Queuing prompt for foreground (progress: \(progress))")
            promptQueuedForForeground = true
        }
    }

    /// Called when user taps "Yes!" - they're enjoying TrackRat
    func userRespondedPositively() {
        shouldShowFeedbackPrompt = false
        promptQueuedForForeground = false

        print("📊 Journey feedback: User responded positively, requesting App Store review")

        // Request App Store review using the recommended API
        if let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene {
            SKStoreReviewController.requestReview(in: windowScene)
        }
    }

    /// Called when user taps "Not really" - show feedback form
    /// Returns true to indicate the caller should present the feedback form
    func userRespondedNegatively() -> Bool {
        shouldShowFeedbackPrompt = false
        promptQueuedForForeground = false

        print("📊 Journey feedback: User responded negatively, showing feedback form")

        // Return true to signal that caller should show the improvement feedback form
        return true
    }

    /// Called when user dismisses the prompt without responding
    func userDismissedPrompt() {
        shouldShowFeedbackPrompt = false
        promptQueuedForForeground = false

        // Record the dismissal to start cooldown
        recordDismissal()

        print("📊 Journey feedback: User dismissed prompt, starting 30-day cooldown")
    }

    // MARK: - Private Methods

    @objc private func appDidBecomeActive() {
        // If we have a queued prompt and we're not already showing one, show it now
        if promptQueuedForForeground && !shouldShowFeedbackPrompt {
            print("📊 Journey feedback: App became active, showing queued prompt")
            promptQueuedForForeground = false
            shouldShowFeedbackPrompt = true
        }
    }

    private func isInCooldownPeriod() -> Bool {
        guard let lastDismissedDate = UserDefaults.standard.object(forKey: lastPromptDismissedDateKey) as? Date else {
            // Never dismissed before, not in cooldown
            return false
        }

        let calendar = Calendar.current
        guard let cooldownEndDate = calendar.date(byAdding: .day, value: cooldownDays, to: lastDismissedDate) else {
            return false
        }

        return Date() < cooldownEndDate
    }

    private func recordDismissal() {
        UserDefaults.standard.set(Date(), forKey: lastPromptDismissedDateKey)
    }
}

// MARK: - Supporting Types

/// Context about the current journey for feedback submission
struct JourneyFeedbackContext {
    let trainId: String
    let originCode: String
    let destinationCode: String
}
