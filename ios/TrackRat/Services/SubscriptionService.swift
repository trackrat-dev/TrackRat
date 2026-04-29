import Foundation
import StoreKit

// MARK: - Subscription Status

enum SubscriptionStatus: Equatable {
    case unknown
    case notSubscribed
    case subscribed(expirationDate: Date?, isTrialPeriod: Bool)

    var isActive: Bool {
        if case .subscribed = self { return true }
        return false
    }
}

// MARK: - Premium Feature

enum PremiumFeature: String, CaseIterable {
    case multipleTrainSystems = "Multiple Train Systems"
    case unlimitedAlerts = "Unlimited Route Alerts"

    var displayName: String { rawValue }

    var iconName: String {
        switch self {
        case .multipleTrainSystems: return "tram.fill"
        case .unlimitedAlerts: return "bell.badge.fill"
        }
    }
}

// MARK: - Paywall Context

enum PaywallContext {
    case trainSystems
    case routeAlerts
    case generic
}

// MARK: - Subscription Service

@MainActor
final class SubscriptionService: ObservableObject {
    static let shared = SubscriptionService()

    // MARK: - Published Properties

    @Published private(set) var subscriptionStatus: SubscriptionStatus = .unknown
    @Published private(set) var availableProducts: [Product] = []
    @Published private(set) var isLoading = false
    @Published private(set) var errorMessage: String?

    // Debug override for testing
    @Published var debugOverrideEnabled: Bool {
        didSet {
            userDefaults.set(debugOverrideEnabled, forKey: debugOverrideKey)
        }
    }

    // MARK: - Private Properties

    private let userDefaults = UserDefaults.standard
    private let debugOverrideKey = "trackrat.subscription.debugOverride"
    private var updateTask: Task<Void, Never>?

    // Product IDs - configure these in App Store Connect
    static let monthlyProductId = "com.trackrat.pro.monthly"
    static let yearlyProductId = "com.trackrat.pro.yearly"
    private let productIds: Set<String> = [monthlyProductId, yearlyProductId]

    // Free tier limits
    static let freeTrainSystemLimit = 1
    static let freeRouteAlertLimit = 1

    // MARK: - Computed Properties

    /// Returns true if user has active subscription or debug override is enabled
    var isPro: Bool {
        if debugOverrideEnabled { return true }
        return subscriptionStatus.isActive
    }

    var monthlyProduct: Product? {
        availableProducts.first { $0.id == Self.monthlyProductId }
    }

    var yearlyProduct: Product? {
        availableProducts.first { $0.id == Self.yearlyProductId }
    }

    // MARK: - Initialization

    private init() {
        // Always start with debug override off; user can toggle during session
        self.debugOverrideEnabled = false

        // Start listening for transaction updates
        updateTask = observeTransactionUpdates()

        // Check subscription status on init
        Task {
            await loadProducts()
            await checkSubscriptionStatus()
        }
    }

    deinit {
        updateTask?.cancel()
    }

    // MARK: - Public Methods

    /// Check if user has access to a specific premium feature
    func hasAccess(to feature: PremiumFeature) -> Bool {
        return isPro
    }

    /// Called when app returns to foreground to refresh subscription status
    /// This catches cases where user cancelled subscription in Settings app
    func refreshOnForeground() {
        Task {
            await checkSubscriptionStatus()
        }
    }

    /// Load available products from App Store
    func loadProducts() async {
        isLoading = true
        errorMessage = nil

        do {
            let products = try await Product.products(for: productIds)
            availableProducts = products.sorted { $0.price < $1.price }
            print("Loaded \(products.count) subscription products")
        } catch {
            print("Failed to load products: \(error)")
            errorMessage = "Unable to load subscription options"
        }

        isLoading = false
    }

    /// Purchase a subscription product
    func purchase(_ product: Product) async throws -> Bool {
        isLoading = true
        errorMessage = nil

        defer { isLoading = false }

        do {
            let result = try await product.purchase()

            switch result {
            case .success(let verification):
                let transaction = try checkVerified(verification)
                await transaction.finish()
                await checkSubscriptionStatus()
                print("Purchase successful: \(product.id)")
                return true

            case .pending:
                print("Purchase pending approval")
                return false

            case .userCancelled:
                print("User cancelled purchase")
                return false

            @unknown default:
                print("Unknown purchase result")
                return false
            }
        } catch {
            print("Purchase failed: \(error)")
            errorMessage = "Purchase failed. Please try again."
            throw error
        }
    }

    /// Restore previous purchases
    func restorePurchases() async {
        isLoading = true
        errorMessage = nil

        do {
            try await AppStore.sync()
            await checkSubscriptionStatus()
            print("Purchases restored successfully")
        } catch {
            print("Restore failed: \(error)")
            errorMessage = "Unable to restore purchases"
        }

        isLoading = false
    }

    /// Check current subscription status.
    /// Only re-publishes when the status actually changes — `@Published` fires
    /// `objectWillChange` on every assignment regardless of equality, and this
    /// runs on every scenePhase=.active, cascading rebuilds across all observers.
    func checkSubscriptionStatus() async {
        var newStatus: SubscriptionStatus = .notSubscribed

        for await result in Transaction.currentEntitlements {
            do {
                let transaction = try checkVerified(result)

                if productIds.contains(transaction.productID),
                   let expirationDate = transaction.expirationDate,
                   expirationDate > Date() {
                    let isTrialPeriod = transaction.offer?.type == .introductory
                    newStatus = .subscribed(
                        expirationDate: expirationDate,
                        isTrialPeriod: isTrialPeriod
                    )
                    print("Active subscription found, expires: \(expirationDate)")
                    break
                }
            } catch {
                print("Transaction verification failed: \(error)")
            }
        }

        if newStatus != subscriptionStatus {
            subscriptionStatus = newStatus
            if case .notSubscribed = newStatus {
                print("No active subscription found")
            }
        }
    }

    // MARK: - Private Methods

    private func observeTransactionUpdates() -> Task<Void, Never> {
        Task.detached { [weak self] in
            for await result in Transaction.updates {
                do {
                    let transaction = try self?.checkVerified(result)
                    await transaction?.finish()
                    await self?.checkSubscriptionStatus()
                } catch {
                    print("Transaction update failed: \(error)")
                }
            }
        }
    }

    nonisolated private func checkVerified<T>(_ result: VerificationResult<T>) throws -> T {
        switch result {
        case .unverified(_, let error):
            throw error
        case .verified(let safe):
            return safe
        }
    }
}

// MARK: - Subscription Status Extensions

extension SubscriptionStatus {
    var statusText: String {
        switch self {
        case .unknown:
            return "Checking..."
        case .notSubscribed:
            return "Not subscribed"
        case .subscribed(_, let isTrialPeriod):
            return isTrialPeriod ? "Trial Active" : "Pro Active"
        }
    }

    var expirationText: String? {
        guard case .subscribed(let date, _) = self, let expirationDate = date else {
            return nil
        }

        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        return "Renews \(formatter.string(from: expirationDate))"
    }
}
