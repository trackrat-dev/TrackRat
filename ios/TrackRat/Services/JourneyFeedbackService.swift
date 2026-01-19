import Foundation
import StoreKit
import UIKit

/// Service that manages prompting users for feedback during their train journey.
/// Shows a feedback prompt when the train departs from the user's origin station.
/// Cooldown: 8 days if dismissed, 16 days if negative feedback.
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
    private let cooldownDaysKey = "journeyFeedback_cooldownDays"

    // MARK: - Configuration

    private let dismissCooldownDays: Int = 8
    private let negativeFeedbackCooldownDays: Int = 16

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

    /// Called once when train departs from user's origin station
    func onDeparture(trainId: String, originCode: String, destinationCode: String) {
        // Skip if we've already prompted during this activity
        guard !hasPromptedDuringCurrentActivity else { return }

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
            print("📊 Journey feedback: Showing prompt on departure (app active)")
            shouldShowFeedbackPrompt = true
        } else {
            print("📊 Journey feedback: Queuing prompt for foreground (departure detected)")
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
    /// Note: Does NOT dismiss the prompt - the prompt stays visible until the feedback form is dismissed
    func userRespondedNegatively() -> Bool {
        promptQueuedForForeground = false

        // Record with longer cooldown for negative feedback
        recordCooldown(days: negativeFeedbackCooldownDays)

        print("📊 Journey feedback: User responded negatively, showing feedback form")

        // Return true to signal that caller should show the improvement feedback form
        return true
    }

    /// Called when user dismisses the prompt without responding
    func userDismissedPrompt() {
        shouldShowFeedbackPrompt = false
        promptQueuedForForeground = false

        recordCooldown(days: dismissCooldownDays)

        print("📊 Journey feedback: User dismissed prompt, starting \(dismissCooldownDays)-day cooldown")
    }

    /// Resets all cooldown periods, allowing the prompt to appear on the next departure
    func resetCooldowns() {
        UserDefaults.standard.removeObject(forKey: lastPromptDismissedDateKey)
        UserDefaults.standard.removeObject(forKey: cooldownDaysKey)
        hasPromptedDuringCurrentActivity = false
        promptQueuedForForeground = false

        print("📊 Journey feedback: Cooldowns reset")
    }

    /// Forces the feedback prompt to show immediately (for testing)
    func forceShowPrompt() {
        shouldShowFeedbackPrompt = true

        print("📊 Journey feedback: Force showing prompt")
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
            return false
        }

        let cooldownDays = UserDefaults.standard.integer(forKey: cooldownDaysKey)
        guard cooldownDays > 0 else { return false }

        let calendar = Calendar.current
        guard let cooldownEndDate = calendar.date(byAdding: .day, value: cooldownDays, to: lastDismissedDate) else {
            return false
        }

        return Date() < cooldownEndDate
    }

    private func recordCooldown(days: Int) {
        UserDefaults.standard.set(Date(), forKey: lastPromptDismissedDateKey)
        UserDefaults.standard.set(days, forKey: cooldownDaysKey)
    }
}

// MARK: - Supporting Types

/// Context about the current journey for feedback submission
struct JourneyFeedbackContext {
    let trainId: String
    let originCode: String
    let destinationCode: String
}
