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
    case supportDevelopment = "Support Active Development"
    case liveActivities = "Live Activities"
    case trackPredictions = "Track Predictions"
    case delayForecasts = "Delay Forecasts"
    case congestionMap = "Live Congestion Map"
    case historicalData = "Historical Analytics"
    case tripStatistics = "Trip History (beta)"
    case ratSense = "RatSense AI"
    case pennStationGuide = "Penn Station Boarding Guide"

    var displayName: String { rawValue }

    var iconName: String {
        switch self {
        case .liveActivities: return "pin.fill"
        case .trackPredictions: return "number.circle.fill"
        case .delayForecasts: return "chart.line.uptrend.xyaxis"
        case .congestionMap: return "map.circle.fill"
        case .historicalData: return "clock.arrow.circlepath"
        case .tripStatistics: return "chart.bar.fill"
        case .ratSense: return "brain.head.profile"
        case .pennStationGuide: return "map.fill"
        case .supportDevelopment: return "heart.fill"
        }
    }
}

// MARK: - Paywall Context

enum PaywallContext {
    case liveActivities
    case trackPredictions
    case delayForecasts
    case historicalData
    case tripStatistics
    case pennStationGuide
    case congestionMap
    case generic
    case trialExpired

    var headline: String {
        switch self {
        case .liveActivities:
            return "Track on Lock Screen"
        case .trackPredictions:
            return "Know Your Track"
        case .delayForecasts:
            return "See What's Coming"
        case .historicalData:
            return "Learn Your Route"
        case .tripStatistics:
            return "Your Commute Story"
        case .pennStationGuide:
            return "Navigate Penn Station"
        case .congestionMap:
            return "Network Traffic"
        case .generic:
            return "Upgrade to Pro"
        case .trialExpired:
            return "Your Preview Has Ended"
        }
    }

    var subtext: String {
        switch self {
        case .liveActivities:
            return "Follow your train in real-time without opening the app"
        case .trackPredictions:
            return "Know the odds for which platform your train will depart from"
        case .delayForecasts:
            return "Get delay and cancellation forecasts before you leave"
        case .historicalData:
            return "Leverage past performance and patterns"
        case .tripStatistics:
            return "Track every trip and see your on-time percentage"
        case .pennStationGuide:
            return "Platform guides to avoid the crowd"
        case .congestionMap:
            return "See real-time train congestion across the network"
        case .generic:
            return "Your subscription funds bug fixes, new features, and keeps the servers running."
        case .trialExpired:
            return "Start your free trial to keep Pro features and help fund future improvements."
        }
    }
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

    // Soft trial start date (16-hour preview for new users)
    @Published private(set) var softTrialStartDate: Date?

    // MARK: - Private Properties

    private let userDefaults = UserDefaults.standard
    private let debugOverrideKey = "trackrat.subscription.debugOverride"
    private let softTrialStartDateKey = "trackrat.softTrial.startDate"
    private var updateTask: Task<Void, Never>?

    // Product IDs - configure these in App Store Connect
    static let monthlyProductId = "com.trackrat.pro.monthly"
    private let productIds: Set<String> = [monthlyProductId]

    // MARK: - Computed Properties

    /// Returns true if user has active subscription, debug override is enabled, OR in soft trial
    var isPro: Bool {
        if debugOverrideEnabled { return true }
        if subscriptionStatus.isActive { return true }
        if isInSoftTrial { return true }
        return false
    }

    /// Returns true if user is currently within the 16-hour soft trial window
    var isInSoftTrial: Bool {
        guard let startDate = softTrialStartDate else { return false }
        let hoursElapsed = Date().timeIntervalSince(startDate) / 3600
        return hoursElapsed < 16
    }

    /// Returns hours remaining in soft trial (1-16), or nil if not in trial
    var softTrialHoursRemaining: Int? {
        guard let startDate = softTrialStartDate else { return nil }
        let hoursElapsed = Date().timeIntervalSince(startDate) / 3600
        guard hoursElapsed < 16 else { return nil }
        return max(1, Int(ceil(16 - hoursElapsed)))
    }

    /// Returns true if soft trial was started but has now expired
    var softTrialExpired: Bool {
        guard let startDate = softTrialStartDate else { return false }
        let hoursElapsed = Date().timeIntervalSince(startDate) / 3600
        return hoursElapsed >= 16
    }

    var monthlyProduct: Product? {
        availableProducts.first { $0.id == Self.monthlyProductId }
    }

    // MARK: - Initialization

    private init() {
        // Always start with debug override off; user can toggle during session
        self.debugOverrideEnabled = false

        // Load soft trial start date from UserDefaults
        if let storedDate = userDefaults.object(forKey: softTrialStartDateKey) as? Date {
            self.softTrialStartDate = storedDate
        } else {
            // New user - start the soft trial
            let now = Date()
            self.softTrialStartDate = now
            userDefaults.set(now, forKey: softTrialStartDateKey)
            print("Soft trial started for new user at \(now)")
        }

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

    /// Check current subscription status
    func checkSubscriptionStatus() async {
        var foundActiveSubscription = false

        for await result in Transaction.currentEntitlements {
            do {
                let transaction = try checkVerified(result)

                if productIds.contains(transaction.productID) {
                    // Check if subscription is still valid
                    if let expirationDate = transaction.expirationDate {
                        if expirationDate > Date() {
                            let isTrialPeriod = transaction.offerType == .introductory
                            subscriptionStatus = .subscribed(
                                expirationDate: expirationDate,
                                isTrialPeriod: isTrialPeriod
                            )
                            foundActiveSubscription = true
                            print("Active subscription found, expires: \(expirationDate)")
                            break
                        }
                    }
                }
            } catch {
                print("Transaction verification failed: \(error)")
            }
        }

        if !foundActiveSubscription {
            subscriptionStatus = .notSubscribed
            print("No active subscription found")
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
