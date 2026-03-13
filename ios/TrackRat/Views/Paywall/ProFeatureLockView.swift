import SwiftUI
import UIKit

/// A full-width upgrade prompt card
struct UpgradePromptCard: View {
    var headline: String? = nil
    let subtext: String
    @Binding var showingPaywall: Bool

    var body: some View {
        Button {
            showingPaywall = true
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        } label: {
            VStack(spacing: 12) {
                HStack {
                    Image(systemName: "heart.fill")
                        .foregroundColor(.orange)
                    Text("TrackRat Pro")
                        .font(.headline)
                        .foregroundColor(.white)
                    Spacer()
                }

                if let headline, !headline.isEmpty {
                    Text(headline)
                        .font(.title3.bold())
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                Text(subtext)
                    .font(.subheadline)
                    .foregroundColor(.white.opacity(0.7))
                    .frame(maxWidth: .infinity, alignment: .leading)

                HStack {
                    Text("Learn More")
                        .font(.subheadline.weight(.semibold))
                        .foregroundColor(.white)

                    Image(systemName: "arrow.right")
                        .font(.subheadline)
                        .foregroundColor(.white)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .background(
                    Capsule()
                        .fill(.orange)
                )
                .padding(.top, 4)
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 16)
                    .fill(
                        LinearGradient(
                            colors: [.orange.opacity(0.2), .orange.opacity(0.05)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 16)
                            .stroke(.orange.opacity(0.3), lineWidth: 1)
                    )
            )
        }
        .buttonStyle(.plain)
    }
}

#Preview("UpgradePromptCard") {
    UpgradePromptCard(
        subtext: "Support continued development and unlock developer chat.",
        showingPaywall: .constant(false)
    )
    .padding()
    .background(Color.black)
}
