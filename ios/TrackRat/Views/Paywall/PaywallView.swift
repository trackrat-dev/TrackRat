import SwiftUI
import StoreKit
import UIKit

struct PaywallView: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var subscriptionService = SubscriptionService.shared

    let context: PaywallContext

    @State private var selectedProduct: Product?
    @State private var isPurchasing = false
    @State private var showError = false
    @State private var errorMessage = ""
    @State private var showRestoreMessage = false
    @State private var restoreMessage = ""
    @State private var isRestoring = false
    @State private var showPurchaseSuccess = false

    init(context: PaywallContext = .generic) {
        self.context = context
    }

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
                    }
                    .padding(.horizontal)

                    // Header
                    VStack(spacing: 16) {
                        // Pro badge
                        HStack(spacing: 8) {
                            Image(systemName: "star.fill")
                                .foregroundColor(.orange)
                            Text("TrackRat Pro")
                                .font(.title2.bold())
                                .foregroundColor(.white)
                        }
                        .padding(.horizontal, 20)
                        .padding(.vertical, 10)
                        .background(
                            Capsule()
                                .fill(.orange.opacity(0.2))
                                .overlay(
                                    Capsule()
                                        .stroke(.orange.opacity(0.5), lineWidth: 1)
                                )
                        )

                        // Context-specific headline
                        Text(context.headline)
                            .font(.title.bold())
                            .foregroundColor(.white)
                            .multilineTextAlignment(.center)

                        Text(context.subtext)
                            .font(.body)
                            .foregroundColor(.white.opacity(0.7))
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                    }
                    .padding(.top, 20)

                    // Feature list
                    VStack(alignment: .leading, spacing: 16) {
                        ForEach(PremiumFeature.allCases, id: \.rawValue) { feature in
                            FeatureRow(feature: feature)
                        }
                    }
                    .padding()
                    .background(
                        RoundedRectangle(cornerRadius: 16)
                            .fill(.white.opacity(0.05))
                            .overlay(
                                RoundedRectangle(cornerRadius: 16)
                                    .stroke(.white.opacity(0.1), lineWidth: 1)
                            )
                    )
                    .padding(.horizontal)

                    // Development transparency note
                    Text("TrackRat is a work in progress. Your subscription supports bug fixes and new features.")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)

                    // Pricing options
                    if subscriptionService.isLoading && subscriptionService.availableProducts.isEmpty {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                            .padding()
                    } else if subscriptionService.availableProducts.isEmpty {
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
                    } else {
                        VStack(spacing: 12) {
                            // Monthly option
                            if let monthly = subscriptionService.monthlyProduct {
                                PricingOptionView(
                                    product: monthly,
                                    isSelected: selectedProduct?.id == monthly.id,
                                    badge: nil,
                                    subtitle: subscriptionSubtitle(for: monthly)
                                ) {
                                    selectedProduct = monthly
                                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                                }
                            }
                        }
                        .padding(.horizontal)
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
                                Text("Subscribe")
                                    .fontWeight(.semibold)
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(
                            RoundedRectangle(cornerRadius: 14)
                                .fill(selectedProduct != nil ? .orange : .gray)
                        )
                        .foregroundColor(.white)
                    }
                    .buttonStyle(.plain)
                    .disabled(selectedProduct == nil || isPurchasing)
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
                    Text("Payment will be charged to your Apple ID account at the confirmation of purchase. Subscription automatically renews unless it is canceled at least 24 hours before the end of the current period. Your account will be charged for renewal within 24 hours prior to the end of the current period.")
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
        .onAppear {
            // Default to monthly selection
            if selectedProduct == nil {
                selectedProduct = subscriptionService.monthlyProduct
            }
        }
        .onChange(of: subscriptionService.availableProducts) { _, products in
            if selectedProduct == nil, let monthly = products.first(where: { $0.id == SubscriptionService.monthlyProductId }) {
                selectedProduct = monthly
            }
        }
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
        return "\(trialPrefix)\(product.displayPrice)/month"
    }

    private func purchase() async {
        guard let product = selectedProduct else { return }

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

// MARK: - Feature Row

private struct FeatureRow: View {
    let feature: PremiumFeature

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: feature.iconName)
                .font(.body)
                .foregroundColor(.orange)
                .frame(width: 24)

            Text(feature.displayName)
                .font(.subheadline)
                .foregroundColor(.white)

            Spacer()

            Image(systemName: "checkmark")
                .font(.caption.bold())
                .foregroundColor(.green)
        }
    }
}

// MARK: - Pricing Option

private struct PricingOptionView: View {
    let product: Product
    let isSelected: Bool
    let badge: String?
    let subtitle: String
    let onSelect: () -> Void

    var body: some View {
        Button(action: onSelect) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text(product.displayName)
                            .font(.headline)
                            .foregroundColor(.white)

                        if let badge = badge {
                            Text(badge)
                                .font(.caption2.bold())
                                .foregroundColor(.orange)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 2)
                                .background(
                                    Capsule()
                                        .fill(.orange.opacity(0.2))
                                )
                        }
                    }

                    Text(subtitle)
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))
                }

                Spacer()

                // Selection indicator
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.title2)
                    .foregroundColor(isSelected ? .orange : .white.opacity(0.3))
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(isSelected ? .orange.opacity(0.15) : .white.opacity(0.05))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(isSelected ? .orange.opacity(0.5) : .white.opacity(0.1), lineWidth: 1)
                    )
            )
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Purchase Success Overlay

private struct PurchaseSuccessOverlay: View {
    @State private var checkmarkScale: CGFloat = 0
    @State private var showConfetti = false

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

                    Text("Reach out if you have ideas for new features")
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
    PaywallView(context: .liveActivities)
}
