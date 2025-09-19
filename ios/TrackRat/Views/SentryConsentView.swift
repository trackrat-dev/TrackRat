import SwiftUI

struct SentryConsentView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var showingDetails = false

    var body: some View {
        VStack(spacing: 20) {
            // Header
            VStack(spacing: 12) {
                Image(systemName: "shield.checkerboard")
                    .font(.system(size: 50))
                    .foregroundStyle(.orange)

                Text("Help Improve TrackRat")
                    .font(.title2)
                    .fontWeight(.bold)

                Text("Enable session replay to help us identify and fix issues faster")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
            }
            .padding(.top)

            // Benefits
            VStack(alignment: .leading, spacing: 16) {
                FeatureRow(
                    icon: "video.fill",
                    title: "Session Replay",
                    description: "Records app interactions when errors occur"
                )

                FeatureRow(
                    icon: "lock.shield.fill",
                    title: "Privacy Protected",
                    description: "No personal information is captured"
                )

                FeatureRow(
                    icon: "speedometer",
                    title: "Performance Insights",
                    description: "Helps us optimize app performance"
                )
            }
            .padding(.horizontal)

            if showingDetails {
                Text("Session replay captures screen recordings only when errors occur, helping developers understand and fix issues. All personal information is automatically redacted.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .padding()
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(10)
                    .padding(.horizontal)
            }

            Spacer()

            // Actions
            VStack(spacing: 12) {
                Button(action: enableSessionReplay) {
                    Text("Enable Session Replay")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.orange)
                        .foregroundColor(.white)
                        .cornerRadius(12)
                }

                Button(action: skipForNow) {
                    Text("Skip for Now")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                Button(action: { showingDetails.toggle() }) {
                    Text(showingDetails ? "Hide Details" : "Learn More")
                        .font(.caption)
                        .foregroundStyle(.orange)
                }
            }
            .padding(.horizontal)
            .padding(.bottom)
        }
        .preferredColorScheme(.dark)
    }

    private func enableSessionReplay() {
        UserDefaults.standard.set(true, forKey: "sentry_session_replay_consent")

        // Update Sentry configuration if needed
        if #available(iOS 16.0, *) {
            // Session replay will be enabled on next app launch
        }

        dismiss()
    }

    private func skipForNow() {
        UserDefaults.standard.set(false, forKey: "sentry_session_replay_consent")
        dismiss()
    }
}

struct FeatureRow: View {
    let icon: String
    let title: String
    let description: String

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundStyle(.orange)
                .frame(width: 30)

            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.subheadline)
                    .fontWeight(.semibold)

                Text(description)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()
        }
    }
}

#Preview {
    SentryConsentView()
        .preferredColorScheme(.dark)
}