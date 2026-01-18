import SwiftUI
import UIKit

/// A reusable component that displays a locked state for premium features
/// Use this inline in views where premium features would normally appear
struct ProFeatureLockView: View {
    let feature: PremiumFeature
    let context: PaywallContext
    @Binding var showingPaywall: Bool

    var body: some View {
        Button {
            showingPaywall = true
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
        } label: {
            HStack(spacing: 12) {
                // Lock icon
                Image(systemName: "lock.fill")
                    .font(.title3)
                    .foregroundColor(.orange)

                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 6) {
                        Text(feature.displayName)
                            .font(.subheadline.weight(.medium))
                            .foregroundColor(.white)

                        // Pro badge
                        Text("PRO")
                            .font(.caption2.bold())
                            .foregroundColor(.orange)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(
                                Capsule()
                                    .fill(.orange.opacity(0.2))
                            )
                    }

                    Text(context.subtext)
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))
                        .lineLimit(2)
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.4))
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(.white.opacity(0.05))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(.orange.opacity(0.3), lineWidth: 1)
                    )
            )
        }
    }
}

/// A compact lock indicator for use in smaller spaces
struct ProBadgeLock: View {
    @Binding var showingPaywall: Bool

    var body: some View {
        Button {
            showingPaywall = true
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
        } label: {
            HStack(spacing: 4) {
                Image(systemName: "lock.fill")
                    .font(.caption2)
                Text("PRO")
                    .font(.caption2.bold())
            }
            .foregroundColor(.orange)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(
                Capsule()
                    .fill(.orange.opacity(0.15))
                    .overlay(
                        Capsule()
                            .stroke(.orange.opacity(0.3), lineWidth: 1)
                    )
            )
        }
    }
}

/// A full-width upgrade prompt card
struct UpgradePromptCard: View {
    let headline: String
    let subtext: String
    @Binding var showingPaywall: Bool

    var body: some View {
        Button {
            showingPaywall = true
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        } label: {
            VStack(spacing: 12) {
                HStack {
                    Image(systemName: "star.fill")
                        .foregroundColor(.orange)
                    Text("TrackRat Pro")
                        .font(.headline)
                        .foregroundColor(.white)
                    Spacer()
                }

                Text(headline)
                    .font(.title3.bold())
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity, alignment: .leading)

                Text(subtext)
                    .font(.subheadline)
                    .foregroundColor(.white.opacity(0.7))
                    .frame(maxWidth: .infinity, alignment: .leading)

                HStack {
                    Text("Upgrade Now")
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
    }
}

/// View modifier to conditionally show paywall sheet
struct PaywallSheetModifier: ViewModifier {
    @Binding var isPresented: Bool
    let context: PaywallContext

    func body(content: Content) -> some View {
        content
            .sheet(isPresented: $isPresented) {
                PaywallView(context: context)
                    .presentationDetents([.large])
                    .presentationDragIndicator(.visible)
            }
    }
}

extension View {
    /// Adds a paywall sheet that can be triggered by setting isPresented to true
    func paywallSheet(isPresented: Binding<Bool>, context: PaywallContext) -> some View {
        modifier(PaywallSheetModifier(isPresented: isPresented, context: context))
    }
}

#Preview("ProFeatureLockView") {
    VStack {
        ProFeatureLockView(
            feature: .trackPredictions,
            context: .trackPredictions,
            showingPaywall: .constant(false)
        )
        .padding()
    }
    .background(Color.black)
}

#Preview("ProBadgeLock") {
    ProBadgeLock(showingPaywall: .constant(false))
        .padding()
        .background(Color.black)
}

#Preview("UpgradePromptCard") {
    UpgradePromptCard(
        headline: "Track on Lock Screen",
        subtext: "Follow your train in real-time without opening the app",
        showingPaywall: .constant(false)
    )
    .padding()
    .background(Color.black)
}
