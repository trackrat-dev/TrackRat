import SwiftUI

/// A button that allows users to report data issues
struct FeedbackButton: View {
    let screen: String
    let trainId: String?
    let originCode: String?
    let destinationCode: String?

    @State private var showingSheet = false

    var body: some View {
        Button {
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
            showingSheet = true
        } label: {
            HStack(spacing: 6) {
                Image(systemName: "exclamationmark.bubble")
                    .font(.footnote)
                Text("Report an issue")
                    .font(.footnote)
            }
            .foregroundColor(.white.opacity(0.6))
        }
        .buttonStyle(.plain)
        .sheet(isPresented: $showingSheet) {
            FeedbackSheet(
                screen: screen,
                trainId: trainId,
                originCode: originCode,
                destinationCode: destinationCode
            )
        }
    }
}

/// Sheet for submitting feedback
struct FeedbackSheet: View {
    let screen: String
    let trainId: String?
    let originCode: String?
    let destinationCode: String?

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
            .navigationTitle("Report Issue")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(.ultraThinMaterial, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .presentationBackground(Color.black)
        .preferredColorScheme(.dark)
    }

    private var formView: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Help us improve TrackRat by reporting incorrect or missing data.")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.7))

            // Message input
            VStack(alignment: .leading, spacing: 8) {
                Text("What's wrong?")
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
                            Text("Describe the issue...")
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
                    Text("Submit")
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

            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 72))
                .foregroundColor(.orange)
                .shadow(color: .orange.opacity(0.3), radius: 12, x: 0, y: 4)

            Text("Thank you!")
                .font(.title)
                .fontWeight(.bold)
                .foregroundColor(.white)

            Text("Your feedback helps us improve TrackRat for everyone.")
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
                    message: message,
                    screen: screen,
                    trainId: trainId,
                    originCode: originCode,
                    destinationCode: destinationCode
                )

                await MainActor.run {
                    UINotificationFeedbackGenerator().notificationOccurred(.success)
                    withAnimation {
                        showingConfirmation = true
                    }
                }
            } catch {
                print("Failed to submit feedback: \(error)")
                await MainActor.run {
                    UINotificationFeedbackGenerator().notificationOccurred(.error)
                    // Still show confirmation - the feedback attempt was made
                    // and we don't want to frustrate the user
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
