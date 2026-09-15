import StoreKit
import XCTest
@testable import TrackRat

/// Covers the paid-plan contract: which products the paywall may sell, which
/// products still grant Pro, and how much a free user gets. These are the
/// pieces that can be asserted without a live App Store session — the purchase
/// and restore flows need StoreKit itself and are exercised manually against
/// `Configuration.storekit`.
@MainActor
final class SubscriptionServiceTests: XCTestCase {

    // MARK: - Plans On Sale

    func testPurchasableProductIds_isMonthlyOnly() {
        XCTAssertEqual(
            SubscriptionService.purchasableProductIds,
            [SubscriptionService.monthlyProductId],
            """
            Monthly is the only plan on offer. Found: \
            \(SubscriptionService.purchasableProductIds.sorted())
            """
        )
    }

    func testPurchasableProductIds_excludesLegacyYearly() {
        XCTAssertFalse(
            SubscriptionService.purchasableProductIds.contains(SubscriptionService.legacyYearlyProductId),
            "The yearly plan was removed from sale and must never be offered on the paywall"
        )
    }

    // MARK: - Entitlements

    func testEntitledProductIds_stillHonorsLegacyYearly() {
        XCTAssertTrue(
            SubscriptionService.entitledProductIds.contains(SubscriptionService.legacyYearlyProductId),
            """
            App Store Connect cannot delete a product — it can only be removed from sale — so \
            subscribers who bought the yearly plan keep renewing. Dropping \
            \(SubscriptionService.legacyYearlyProductId) from entitledProductIds would silently \
            revoke Pro for every paying yearly subscriber at their next launch.
            """
        )
    }

    func testEntitledProductIds_includesMonthly() {
        XCTAssertTrue(
            SubscriptionService.entitledProductIds.contains(SubscriptionService.monthlyProductId),
            "The plan currently on sale must grant Pro"
        )
    }

    func testPurchasableProductIds_areAllEntitled() {
        XCTAssertTrue(
            SubscriptionService.purchasableProductIds.isSubset(of: SubscriptionService.entitledProductIds),
            """
            A plan the paywall can sell but that grants no entitlement would charge users for \
            nothing. Sellable: \(SubscriptionService.purchasableProductIds.sorted()), \
            entitled: \(SubscriptionService.entitledProductIds.sorted())
            """
        )
    }

    func testProductIds_areDistinct() {
        XCTAssertNotEqual(
            SubscriptionService.monthlyProductId,
            SubscriptionService.legacyYearlyProductId,
            "Monthly and legacy yearly must be separate App Store products"
        )
        XCTAssertEqual(
            SubscriptionService.entitledProductIds.count, 2,
            """
            Expected exactly the monthly plan plus the legacy yearly plan. Found: \
            \(SubscriptionService.entitledProductIds.sorted())
            """
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

    func testFreeRouteAlertLimit_isStillALimit() {
        XCTAssertLessThan(
            SubscriptionService.freeRouteAlertLimit, Int.max,
            "Route alerts are the only paid feature left; an unbounded free tier removes the paywall entirely"
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
