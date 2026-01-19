import SwiftUI

/// A simple prompt shown at 2/3 journey completion asking if the user is enjoying TrackRat.
/// Positive responses trigger an App Store review request.
/// Negative responses show a feedback form.
struct JourneyFeedbackPromptView: View {
    @ObservedObject private var feedbackService = JourneyFeedbackService.shared
    @Environment(\.dismiss) private var dismiss

    @State private var showImprovementForm = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                Spacer()

                // Friendly rat icon
                Image(systemName: "hand.wave.fill")
                    .font(.system(size: 48))
                    .foregroundColor(.orange)

                // Main question
                Text("Enjoying TrackRat so far?")
                    .font(.title2)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                    .multilineTextAlignment(.center)

                Text("Your feedback helps us improve")
                    .font(.subheadline)
                    .foregroundColor(.white.opacity(0.7))

                Spacer()

                // Response buttons
                VStack(spacing: 12) {
                    Button {
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        feedbackService.userRespondedPositively()
                        dismiss()
                    } label: {
                        Text("Yes!")
                            .fontWeight(.semibold)
                            .frame(maxWidth: .infinity)
                            .frame(height: 50)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.orange)

                    Button {
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        if feedbackService.userRespondedNegatively() {
                            showImprovementForm = true
                        }
                    } label: {
                        Text("Not really")
                            .fontWeight(.medium)
                            .frame(maxWidth: .infinity)
                            .frame(height: 50)
                    }
                    .buttonStyle(.bordered)
                    .tint(.white.opacity(0.6))
                }
                .padding(.bottom, 20)
            }
            .padding(.horizontal, 32)
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(.ultraThinMaterial, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        feedbackService.userDismissedPrompt()
                        dismiss()
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(.white.opacity(0.6))
                    }
                }
            }
        }
        .presentationDetents([.height(380)])
        .presentationDragIndicator(.visible)
        .presentationBackground(.ultraThinMaterial)
        .preferredColorScheme(.dark)
        .sheet(isPresented: $showImprovementForm, onDismiss: {
            feedbackService.shouldShowFeedbackPrompt = false
        }) {
            FeedbackSheet(mode: .improvement, context: feedbackService.currentJourneyContext)
        }
    }
}

#Preview {
    Color.black
        .ignoresSafeArea()
        .sheet(isPresented: .constant(true)) {
            JourneyFeedbackPromptView()
        }
}
