import SwiftUI

/// Sheet for collecting improvement suggestions when user isn't fully satisfied.
/// Similar to FeedbackSheet but with messaging focused on improvement.
struct ImprovementFeedbackSheet: View {
    let context: JourneyFeedbackContext?

    @Environment(\.dismiss) private var dismiss
    @State private var message = ""
    @State private var isSubmitting = false
    @State private var showingConfirmation = false
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
            .navigationTitle("Help Us Improve")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(.ultraThinMaterial, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                    .foregroundColor(.white.opacity(0.7))
                }
            }
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .presentationBackground(.ultraThinMaterial)
        .preferredColorScheme(.dark)
    }

    private var formView: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("We'd love to hear how we can make TrackRat better for you.")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.7))

            // Message input
            VStack(alignment: .leading, spacing: 8) {
                Text("What could we improve?")
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
                            Text("Tell us what's on your mind...")
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
                    Text("Send Feedback")
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

            Image(systemName: "heart.fill")
                .font(.system(size: 72))
                .foregroundColor(.orange)
                .shadow(color: .orange.opacity(0.3), radius: 12, x: 0, y: 4)

            Text("Thank you!")
                .font(.title)
                .fontWeight(.bold)
                .foregroundColor(.white)

            Text("Your feedback helps us make TrackRat better for everyone.")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.7))
                .multilineTextAlignment(.center)
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

        Task {
            do {
                try await APIService.shared.submitFeedback(
                    message: "[Improvement Suggestion] \(message)",
                    screen: "journey_feedback_prompt",
                    trainId: context?.trainId,
                    originCode: context?.originCode,
                    destinationCode: context?.destinationCode
                )

                await MainActor.run {
                    UINotificationFeedbackGenerator().notificationOccurred(.success)
                    withAnimation {
                        showingConfirmation = true
                    }
                }
            } catch {
                print("Failed to submit improvement feedback: \(error)")
                await MainActor.run {
                    UINotificationFeedbackGenerator().notificationOccurred(.error)
                    // Still show confirmation - the feedback attempt was made
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
    Color.black
        .ignoresSafeArea()
        .sheet(isPresented: .constant(true)) {
            ImprovementFeedbackSheet(context: nil)
        }
}
