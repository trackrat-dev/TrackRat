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
            HStack(spacing: 4) {
                Image(systemName: "exclamationmark.bubble")
                    .font(.caption)
                Text("Report a data issue")
                    .font(.caption)
            }
            .foregroundColor(.secondary)
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
        NavigationView {
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
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
        }
        .presentationDetents([.medium])
        .presentationDragIndicator(.visible)
    }

    private var formView: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Help us improve TrackRat by reporting incorrect or missing data.")
                .font(.subheadline)
                .foregroundColor(.secondary)

            // Context info
            if trainId != nil || originCode != nil {
                contextInfoView
            }

            // Message input
            VStack(alignment: .leading, spacing: 8) {
                Text("What's wrong?")
                    .font(.headline)

                TextField("Describe the issue...", text: $message, axis: .vertical)
                    .textFieldStyle(.roundedBorder)
                    .lineLimit(3...6)
                    .focused($isTextFieldFocused)
            }

            Spacer()

            // Submit button
            Button {
                submitFeedback()
            } label: {
                if isSubmitting {
                    ProgressView()
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

    private var contextInfoView: some View {
        HStack {
            Image(systemName: "info.circle")
                .foregroundColor(.secondary)

            VStack(alignment: .leading, spacing: 2) {
                if let trainId = trainId {
                    Text("Train \(trainId)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                if let origin = originCode, let dest = destinationCode {
                    Text("\(origin) → \(dest)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            Spacer()
        }
        .padding(8)
        .background(Color(.systemGray6))
        .cornerRadius(8)
    }

    private var confirmationView: some View {
        VStack(spacing: 16) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 60))
                .foregroundColor(.green)

            Text("Thank you!")
                .font(.title2)
                .fontWeight(.semibold)

            Text("Your feedback helps us improve TrackRat for everyone.")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)

            Spacer()

            Button("Done") {
                dismiss()
            }
            .buttonStyle(.borderedProminent)
            .tint(.orange)
        }
        .padding(.top, 40)
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
