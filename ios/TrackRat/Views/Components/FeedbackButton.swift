import SwiftUI

/// The type of feedback being submitted
enum FeedbackMode {
    case issue       // Reporting data problems
    case improvement // Suggestions for making the app better

    var title: String {
        switch self {
        case .issue: return "Report Issue"
        case .improvement: return "Help Us Improve"
        }
    }

    var subtitle: String {
        switch self {
        case .issue: return "Help us improve TrackRat by reporting incorrect or missing data."
        case .improvement: return "We'd love to hear how we can make TrackRat better for you."
        }
    }

    var prompt: String {
        switch self {
        case .issue: return "What's wrong?"
        case .improvement: return "What could we improve?"
        }
    }

    var placeholder: String {
        switch self {
        case .issue: return "Describe the issue..."
        case .improvement: return "Tell us what's on your mind..."
        }
    }

    var buttonLabel: String {
        switch self {
        case .issue: return "Submit"
        case .improvement: return "Send Feedback"
        }
    }

    var confirmationIcon: String {
        switch self {
        case .issue: return "checkmark.circle.fill"
        case .improvement: return "heart.fill"
        }
    }

    var messagePrefix: String? {
        switch self {
        case .issue: return nil
        case .improvement: return "[Improvement Suggestion] "
        }
    }
}

/// A button that allows users to report data issues
struct FeedbackButton: View {
    let screen: String
    let trainId: String?
    let originCode: String?
    let destinationCode: String?
    var textColor: Color = .white.opacity(0.6)
    var label: String = "Report an issue"
    var font: Font = .footnote

    @State private var showingSheet = false

    var body: some View {
        Button {
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
            showingSheet = true
        } label: {
            HStack(spacing: 6) {
                Image(systemName: "exclamationmark.bubble")
                    .font(font)
                Text(label)
                    .font(font)
            }
            .foregroundColor(textColor)
        }
        .buttonStyle(.plain)
        .sheet(isPresented: $showingSheet) {
            FeedbackSheet(
                mode: .issue,
                screen: screen,
                trainId: trainId,
                originCode: originCode,
                destinationCode: destinationCode
            )
        }
    }
}

/// Unified sheet for submitting feedback (issues or improvement suggestions)
struct FeedbackSheet: View {
    let mode: FeedbackMode
    let screen: String
    let trainId: String?
    let originCode: String?
    let destinationCode: String?

    init(mode: FeedbackMode = .issue, screen: String, trainId: String?, originCode: String?, destinationCode: String?) {
        self.mode = mode
        self.screen = screen
        self.trainId = trainId
        self.originCode = originCode
        self.destinationCode = destinationCode
    }

    /// Convenience initializer for journey feedback context
    init(mode: FeedbackMode, context: JourneyFeedbackContext?) {
        self.mode = mode
        self.screen = "journey_feedback_prompt"
        self.trainId = context?.trainId
        self.originCode = context?.originCode
        self.destinationCode = context?.destinationCode
    }

    @Environment(\.dismiss) private var dismiss
    @State private var message = ""
    @State private var isSubmitting = false
    @State private var showingConfirmation = false
    @State private var submissionFailed = false
    @State private var iconScale: CGFloat = 0.5
    @State private var iconOpacity: Double = 0
    @FocusState private var isTextFieldFocused: Bool

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                if showingConfirmation {
                    confirmationView
                } else {
                    formView
                }
            }
            .padding()
            .navigationTitle(mode.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(.ultraThinMaterial, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .presentationBackground(.ultraThinMaterial)
        .preferredColorScheme(.dark)
    }

    private var formView: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(mode.subtitle)
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.7))

            // Message input
            VStack(alignment: .leading, spacing: 8) {
                Text(mode.prompt)
                    .font(.headline)
                    .foregroundColor(.white)

                TextEditor(text: $message)
                    .font(.body)
                    .foregroundColor(.white)
                    .scrollContentBackground(.hidden)
                    .frame(minHeight: 100, maxHeight: 150)
                    .padding(12)
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(.ultraThinMaterial)
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(Color.white.opacity(0.2), lineWidth: 1)
                    )
                    .focused($isTextFieldFocused)
                    .overlay(alignment: .topLeading) {
                        if message.isEmpty {
                            Text(mode.placeholder)
                                .font(.body)
                                .foregroundColor(.white.opacity(0.4))
                                .padding(.horizontal, 16)
                                .padding(.vertical, 20)
                                .allowsHitTesting(false)
                        }
                    }
            }

            Spacer()

            // Submit button
            Button {
                submitFeedback()
            } label: {
                if isSubmitting {
                    ProgressView()
                        .tint(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: 44)
                } else {
                    Text(mode.buttonLabel)
                        .fontWeight(.semibold)
                        .frame(maxWidth: .infinity)
                        .frame(height: 44)
                }
            }
            .buttonStyle(.borderedProminent)
            .tint(.orange)
            .disabled(message.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isSubmitting)
        }
        .onAppear {
            isTextFieldFocused = true
        }
    }

    private var confirmationView: some View {
        VStack(spacing: 20) {
            Spacer()

            Image(systemName: submissionFailed ? "exclamationmark.triangle.fill" : mode.confirmationIcon)
                .font(.system(size: 72))
                .foregroundStyle(
                    LinearGradient(
                        colors: [.orange, .orange.opacity(0.7)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .shadow(color: .orange.opacity(0.4), radius: 16, x: 0, y: 8)
                .scaleEffect(iconScale)
                .opacity(iconOpacity)
                .onAppear {
                    withAnimation(.spring(response: 0.5, dampingFraction: 0.6, blendDuration: 0)) {
                        iconScale = 1.0
                        iconOpacity = 1.0
                    }
                }

            Text("Thank you!")
                .font(.title)
                .fontWeight(.bold)
                .foregroundColor(.white)

            VStack(spacing: 12) {
                if submissionFailed {
                    Text("We couldn't send your feedback right now.\nPlease try again later.")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.7))
                        .multilineTextAlignment(.center)
                } else {
                    Text("Your feedback will be tracked as a GitHub issue shortly.")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.7))
                        .multilineTextAlignment(.center)

                    Link(destination: URL(string: "https://github.com/trackrat-dev/TrackRat/issues?q=is%3Aissue+label%3Auser-feedback+sort%3Acreated-desc")!) {
                        HStack(spacing: 6) {
                            Image(systemName: "arrow.up.forward.square")
                            Text("View on GitHub")
                        }
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(.orange)
                    }
                }
            }
            .padding(.horizontal, 20)

            Spacer()

            Button {
                dismiss()
            } label: {
                Text("Done")
                    .fontWeight(.semibold)
                    .frame(maxWidth: .infinity)
                    .frame(height: 44)
            }
            .buttonStyle(.borderedProminent)
            .tint(.orange)
        }
    }

    private func submitFeedback() {
        guard !message.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }

        isSubmitting = true
        isTextFieldFocused = false

        let finalMessage: String
        if let prefix = mode.messagePrefix {
            finalMessage = prefix + message
        } else {
            finalMessage = message
        }

        Task {
            do {
                try await APIService.shared.submitFeedback(
                    message: finalMessage,
                    screen: screen,
                    trainId: trainId,
                    originCode: originCode,
                    destinationCode: destinationCode
                )

                await MainActor.run {
                    UINotificationFeedbackGenerator().notificationOccurred(.success)
                    submissionFailed = false
                    withAnimation {
                        showingConfirmation = true
                    }
                }
            } catch {
                print("Failed to submit feedback: \(error)")
                await MainActor.run {
                    UINotificationFeedbackGenerator().notificationOccurred(.error)
                    submissionFailed = true
                    withAnimation {
                        showingConfirmation = true
                    }
                }
            }

            await MainActor.run {
                isSubmitting = false
            }
        }
    }
}

#Preview {
    FeedbackButton(
        screen: "train_details",
        trainId: "3254",
        originCode: "NY",
        destinationCode: "NP"
    )
}
