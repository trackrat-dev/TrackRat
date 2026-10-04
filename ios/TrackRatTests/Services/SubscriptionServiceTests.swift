import StoreKit
import XCTest
@testable import TrackRat

/// Covers the paid-plan contract: which products the paywall sells and that grant
/// Pro, and how much a free user gets. These are the
/// pieces that can be asserted without a live App Store session — the purchase
/// and restore flows need StoreKit itself and are exercised manually against
/// `Configuration.storekit`.
@MainActor
final class SubscriptionServiceTests: XCTestCase {

    // MARK: - Plans

    func testProductIds_sellsAndHonorsMonthlyAndYearly() {
        // The same set feeds both loadProducts (what the paywall offers) and
        // checkSubscriptionStatus (what grants Pro), so dropping a plan here would
        // both hide it from the paywall and revoke Pro from everyone paying for it.
        XCTAssertEqual(
            SubscriptionService.productIds,
            [SubscriptionService.monthlyProductId, SubscriptionService.yearlyProductId],
            "Expected exactly the monthly and yearly plans. Found: \(SubscriptionService.productIds.sorted())"
        )
    }

    // MARK: - Free Tier

    func testFreeRouteAlertLimit_coversARoundTripWithHeadroom() {
        // Both directions of a route are configurable for free, and each direction
        // is persisted as its own RouteAlertSubscription. A free tier that cannot
        // hold 2 rows cannot hold a single round-trip commute.
        XCTAssertGreaterThan(
            SubscriptionService.freeRouteAlertLimit, 2,
            """
            A round trip is 2 subscriptions (outbound + return). The free limit is \
            \(SubscriptionService.freeRouteAlertLimit), which leaves no room for a commute plus \
            anything else.
            """
        )
    }

    // MARK: - Pro Gate

    func testIsPro_trueWhenDebugOverrideEnabled() {
        let service = SubscriptionService.shared
        let original = service.debugOverrideEnabled
        defer { service.debugOverrideEnabled = original }

        service.debugOverrideEnabled = true

        XCTAssertTrue(
            service.isPro,
            "Debug override must grant Pro regardless of StoreKit status (status was \(service.subscriptionStatus))"
        )
    }

    func testIsPro_withoutOverride_followsSubscriptionStatus() {
        let service = SubscriptionService.shared
        let original = service.debugOverrideEnabled
        defer { service.debugOverrideEnabled = original }

        service.debugOverrideEnabled = false

        XCTAssertEqual(
            service.isPro,
            service.subscriptionStatus.isActive,
            """
            Without the debug override, Pro must track the StoreKit entitlement exactly. \
            isPro=\(service.isPro), status=\(service.subscriptionStatus)
            """
        )
    }
}
