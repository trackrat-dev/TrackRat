import SwiftUI
import StoreKit
import UIKit

struct PaywallView: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var subscriptionService = SubscriptionService.shared

    @State private var isPurchasing = false
    @State private var showError = false
    @State private var errorMessage = ""
    @State private var showRestoreMessage = false
    @State private var restoreMessage = ""
    @State private var isRestoring = false
    @State private var showPurchaseSuccess = false

    var body: some View {
        ZStack {
            // Background gradient
            LinearGradient(
                colors: [
                    Color(red: 0.1, green: 0.1, blue: 0.15),
                    Color(red: 0.05, green: 0.05, blue: 0.1)
                ],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            ScrollView {
                VStack(spacing: 24) {
                    // Close button
                    HStack {
                        Spacer()
                        Button {
                            dismiss()
                        } label: {
                            Image(systemName: "xmark.circle.fill")
                                .font(.title2)
                                .foregroundColor(.white.opacity(0.6))
                        }
                        .buttonStyle(.plain)
                    }
                    .padding(.horizontal)

                    // Developer message
                    VStack(alignment: .leading, spacing: 20) {
                        Image(systemName: "hand.wave.fill")
                            .font(.system(size: 36))
                            .foregroundColor(.orange)
                            .frame(maxWidth: .infinity, alignment: .center)

                        Text("TrackRat predicts track assignments, forecasts delays at departure & arrival, and lets you subscribe to real-time alerts for Amtrak, NJ Transit, PATH, the subway, and more.")
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.8))
                            .multilineTextAlignment(.leading)
                            .lineSpacing(4)
                            .fixedSize(horizontal: false, vertical: true)

                        Text("Every transit system is free to use, as are your first \(SubscriptionService.freeRouteAlertLimit) route alerts. Subscribing unlocks unlimited route alerts \u{2014} and helps me keep the servers running.")
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.8))
                            .multilineTextAlignment(.leading)
                            .lineSpacing(4)
                            .fixedSize(horizontal: false, vertical: true)

                        Text("Please reach out if you hit issues or have ideas for new features!")
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.8))
                            .multilineTextAlignment(.leading)
                            .lineSpacing(4)
                            .fixedSize(horizontal: false, vertical: true)
                        VStack(spacing: 2) {
                            Text("All the best,")
                                .font(.subheadline)
                                .foregroundColor(.white.opacity(0.8))
                                .frame(maxWidth: .infinity, alignment: .trailing)

                            Text("Andy")
                                .font(.subheadline)
                                .foregroundColor(.white.opacity(0.9))
                                .frame(maxWidth: .infinity, alignment: .trailing)
                        }
                        .padding(.trailing, 8)

                        Image("my-profile")
                            .resizable()
                            .scaledToFill()
                            .frame(width: 72, height: 72)
                            .clipShape(Circle())
                            .overlay(Circle().stroke(.white.opacity(0.2), lineWidth: 1))
                            .frame(maxWidth: .infinity, alignment: .trailing)
                            .padding(.trailing, 8)
                    }
                    .padding(24)
                    .background(
                        RoundedRectangle(cornerRadius: 16)
                            .fill(.white.opacity(0.05))
                            .overlay(
                                RoundedRectangle(cornerRadius: 16)
                                    .stroke(.white.opacity(0.1), lineWidth: 1)
                            )
                    )
                    .padding(.horizontal)

                    // Pricing
                    if subscriptionService.isLoading && subscriptionService.availableProducts.isEmpty {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                            .padding()
                    } else if let monthly = subscriptionService.monthlyProduct {
                        PricingSummaryView(
                            title: monthly.displayName,
                            subtitle: subscriptionSubtitle(for: monthly)
                        )
                        .padding(.horizontal)
                    } else {
                        VStack(spacing: 12) {
                            Text("Unable to load pricing")
                                .foregroundColor(.white.opacity(0.5))

                            Button {
                                Task {
                                    await subscriptionService.loadProducts()
                                }
                            } label: {
                                HStack(spacing: 6) {
                                    Image(systemName: "arrow.clockwise")
                                    Text("Try Again")
                                }
                                .font(.subheadline)
                                .foregroundColor(.orange)
                                .padding(.horizontal, 16)
                                .padding(.vertical, 8)
                                .background(
                                    RoundedRectangle(cornerRadius: 8)
                                        .stroke(.orange.opacity(0.5), lineWidth: 1)
                                )
                            }
                            .buttonStyle(.plain)
                        }
                        .padding()
                    }

                    // Subscribe button
                    Button {
                        Task {
                            await purchase()
                        }
                    } label: {
                        HStack {
                            if isPurchasing {
                                ProgressView()
                                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                                    .scaleEffect(0.8)
                            } else {
                                Text(hasFreeTrial ? "Start Free Trial" : "Subscribe")
                                    .fontWeight(.semibold)
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(
                            RoundedRectangle(cornerRadius: 14)
                                .fill(subscriptionService.monthlyProduct != nil ? .orange : .gray)
                        )
                        .foregroundColor(.white)
                    }
                    .buttonStyle(.plain)
                    .disabled(subscriptionService.monthlyProduct == nil || isPurchasing)
                    .padding(.horizontal)

                    // Restore purchases
                    Button {
                        Task {
                            await restorePurchases()
                        }
                    } label: {
                        HStack(spacing: 6) {
                            if isRestoring {
                                ProgressView()
                                    .progressViewStyle(CircularProgressViewStyle(tint: .white.opacity(0.6)))
                                    .scaleEffect(0.7)
                            }
                            Text(isRestoring ? "Restoring..." : "Restore Purchases")
                                .font(.subheadline)
                                .foregroundColor(.white.opacity(0.6))
                        }
                    }
                    .buttonStyle(.plain)
                    .disabled(isRestoring)

                    // Restore message feedback
                    if showRestoreMessage {
                        Text(restoreMessage)
                            .font(.caption)
                            .foregroundColor(subscriptionService.isPro ? .green : .orange)
                            .transition(.opacity)
                            .animation(.easeInOut, value: showRestoreMessage)
                    }

                    // Legal text
                    Text(legalText)
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.4))
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)

                    // Terms and Privacy links
                    HStack(spacing: 16) {
                        Link("Terms of Use", destination: URL(string: "https://trackrat.net/terms.txt")!)
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.5))

                        Link("Privacy Policy", destination: URL(string: "https://trackrat.net/privacy.txt")!)
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.5))
                    }
                    .padding(.bottom, 40)
                }
                .padding(.top)
            }

            // Success overlay
            if showPurchaseSuccess {
                PurchaseSuccessOverlay()
                    .transition(.opacity.combined(with: .scale))
            }
        }
        .alert("Purchase Error", isPresented: $showError) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(errorMessage)
        }
    }

    /// Whether the monthly plan has a free trial introductory offer
    private var hasFreeTrial: Bool {
        guard let product = subscriptionService.monthlyProduct,
              let subscription = product.subscription,
              let introOffer = subscription.introductoryOffer,
              introOffer.paymentMode == .freeTrial else {
            return false
        }
        return true
    }

    /// Legal disclaimer text, adjusted for free trial when available
    private var legalText: String {
        let renewalText = "Subscription automatically renews unless it is canceled at least 24 hours before the end of the current period. Your account will be charged for renewal within 24 hours prior to the end of the current period."
        if hasFreeTrial {
            return "Free trial begins at confirmation. If you don't cancel before the trial ends, your Apple ID will be charged. \(renewalText)"
        }
        return "Payment will be charged to your Apple ID account at the confirmation of purchase. \(renewalText)"
    }

    /// Format the trial period from product subscription info
    private func trialText(for product: Product) -> String {
        guard let subscription = product.subscription,
              let introOffer = subscription.introductoryOffer,
              introOffer.paymentMode == .freeTrial else {
            return ""
        }

        let period = introOffer.period
        let count = period.value

        switch period.unit {
        case .day:
            return "\(count)-day free trial, then "
        case .week:
            return "\(count)-week free trial, then "
        case .month:
            return "\(count)-month free trial, then "
        case .year:
            return "\(count)-year free trial, then "
        @unknown default:
            return "Free trial, then "
        }
    }

    /// Format the subscription subtitle with trial info if available
    private func subscriptionSubtitle(for product: Product) -> String {
        let trialPrefix = trialText(for: product)
        let periodLabel: String
        if let subscription = product.subscription {
            switch subscription.subscriptionPeriod.unit {
            case .year:
                periodLabel = "/year"
            case .month:
                periodLabel = "/month"
            case .week:
                periodLabel = "/week"
            case .day:
                periodLabel = "/day"
            @unknown default:
                periodLabel = ""
            }
        } else {
            periodLabel = ""
        }
        return "\(trialPrefix)\(product.displayPrice)\(periodLabel)"
    }

    private func purchase() async {
        guard let product = subscriptionService.monthlyProduct else { return }

        isPurchasing = true

        do {
            let success = try await subscriptionService.purchase(product)
            isPurchasing = false

            if success {
                UINotificationFeedbackGenerator().notificationOccurred(.success)

                // Show success animation
                withAnimation(.spring(response: 0.4, dampingFraction: 0.7)) {
                    showPurchaseSuccess = true
                }

                // Dismiss after showing success animation
                try? await Task.sleep(nanoseconds: 1_500_000_000)
                dismiss()
            }
        } catch {
            isPurchasing = false
            errorMessage = "Purchase failed. Please try again."
            showError = true
            UINotificationFeedbackGenerator().notificationOccurred(.error)
        }
    }

    private func restorePurchases() async {
        isRestoring = true
        showRestoreMessage = false

        await subscriptionService.restorePurchases()

        isRestoring = false

        if subscriptionService.isPro {
            restoreMessage = "Subscription restored successfully!"
            showRestoreMessage = true
            UINotificationFeedbackGenerator().notificationOccurred(.success)

            // Dismiss after a short delay to show the success message
            try? await Task.sleep(nanoseconds: 1_000_000_000)
            dismiss()
        } else {
            restoreMessage = "No active subscription found for this Apple ID."
            showRestoreMessage = true
            UINotificationFeedbackGenerator().notificationOccurred(.warning)

            // Hide message after a few seconds
            try? await Task.sleep(nanoseconds: 3_000_000_000)
            showRestoreMessage = false
        }
    }
}

// MARK: - Pricing Summary

/// The single plan on offer. Not selectable — monthly is the only plan.
private struct PricingSummaryView: View {
    let title: String
    let subtitle: String

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.headline)
                    .foregroundColor(.white)

                Text(subtitle)
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.6))
            }

            Spacer()
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(.orange.opacity(0.15))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(.orange.opacity(0.5), lineWidth: 1)
                )
        )
    }
}

// MARK: - Purchase Success Overlay

private struct PurchaseSuccessOverlay: View {
    @State private var checkmarkScale: CGFloat = 0

    var body: some View {
        ZStack {
            // Semi-transparent background
            Color.black.opacity(0.85)
                .ignoresSafeArea()

            VStack(spacing: 24) {
                // Animated checkmark
                ZStack {
                    Circle()
                        .fill(.orange.opacity(0.2))
                        .frame(width: 120, height: 120)

                    Circle()
                        .stroke(.orange, lineWidth: 4)
                        .frame(width: 100, height: 100)

                    Image(systemName: "checkmark")
                        .font(.system(size: 50, weight: .bold))
                        .foregroundColor(.orange)
                        .scaleEffect(checkmarkScale)
                }

                VStack(spacing: 8) {
                    Text("Thank you for supporting TrackRat!")
                        .font(.title.bold())
                        .foregroundColor(.white)
                        .multilineTextAlignment(.center)

                    Text("You now have full access to all TrackRat features")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.7))
                        .multilineTextAlignment(.center)
                }
            }
        }
        .onAppear {
            withAnimation(.spring(response: 0.4, dampingFraction: 0.6)) {
                checkmarkScale = 1.0
            }
        }
    }
}

#Preview {
    PaywallView()
}
