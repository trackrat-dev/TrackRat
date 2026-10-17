import XCTest
@testable import TrackRat

/// Covers the free-tier route alert cap, the only paywalled feature. Every entry
/// point decides whether to show the paywall through `isAtFreeLimit` (before an
/// editor opens) or `wouldExceedFreeLimit` (when a batch is saved), so these are
/// the checks that keep a free user at or under `freeRouteAlertLimit`.
///
/// Tests are written against the limit symbolically, so they stay meaningful if
/// the limit changes.
@MainActor
final class AlertSubscriptionFreeLimitTests: XCTestCase {

    private var service: AlertSubscriptionService { .shared }
    private var limit: Int { SubscriptionService.freeRouteAlertLimit }

    /// Runs `body` against an empty shared service and empties it again afterwards.
    /// Used instead of `setUp`/`tearDown`, which are nonisolated on `XCTestCase`.
    private func withEmptySubscriptions(_ body: () -> Void) {
        removeAllSubscriptions()
        defer { removeAllSubscriptions() }
        body()
    }

    private func removeAllSubscriptions() {
        for sub in service.subscriptions {
            service.removeSubscription(sub)
        }
    }

    /// `count` distinct station-pair subscriptions, none of which duplicate each other.
    private func distinctSubscriptions(_ count: Int) -> [RouteAlertSubscription] {
        (0..<count).map {
            RouteAlertSubscription(dataSource: "NJT", fromStationCode: "F\($0)", toStationCode: "T\($0)")
        }
    }

    private func roundTrip(_ a: String, _ b: String) -> [RouteAlertSubscription] {
        [
            RouteAlertSubscription(dataSource: "LIRR", fromStationCode: a, toStationCode: b),
            RouteAlertSubscription(dataSource: "LIRR", fromStationCode: b, toStationCode: a),
        ]
    }

    // MARK: - isAtFreeLimit

    func testIsAtFreeLimit_falseOneBelowLimit() {
        withEmptySubscriptions {
            service.addSubscriptions(distinctSubscriptions(limit - 1))

            XCTAssertFalse(
                service.isAtFreeLimit(isPro: false),
                "\(service.subscriptions.count) of \(limit) alerts used; a free user must still be able to add one"
            )
        }
    }

    func testIsAtFreeLimit_trueAtLimit() {
        withEmptySubscriptions {
            service.addSubscriptions(distinctSubscriptions(limit))

            XCTAssertEqual(service.subscriptions.count, limit, "Precondition: exactly at the limit")
            XCTAssertTrue(
                service.isAtFreeLimit(isPro: false),
                "\(service.subscriptions.count) of \(limit) alerts used; entry points must show the paywall"
            )
        }
    }

    func testIsAtFreeLimit_neverForPro() {
        withEmptySubscriptions {
            service.addSubscriptions(distinctSubscriptions(limit + 2))

            XCTAssertFalse(
                service.isAtFreeLimit(isPro: true),
                "Pro has no alert cap, but \(service.subscriptions.count) alerts reported as at the limit"
            )
        }
    }

    // MARK: - wouldExceedFreeLimit

    func testWouldExceedFreeLimit_firstRoundTripFitsForFreeUser() {
        withEmptySubscriptions {
            XCTAssertFalse(
                service.wouldExceedFreeLimit(adding: roundTrip("NYK", "JAM"), isPro: false),
                "A commuter's first round trip (2 alerts) must save without the paywall under a limit of \(limit)"
            )
        }
    }

    func testWouldExceedFreeLimit_roundTripOverflowsWhenOneSlotLeft() {
        // The regression Codex caught on #1819: with one free slot left, the
        // "already at the limit?" pre-check passes, the editor opens with both
        // directions enabled, and saving both would land the user one over.
        withEmptySubscriptions {
            service.addSubscriptions(distinctSubscriptions(limit - 1))
            XCTAssertFalse(
                service.isAtFreeLimit(isPro: false),
                "Precondition: the pre-check alone lets this save through"
            )

            XCTAssertTrue(
                service.wouldExceedFreeLimit(adding: roundTrip("NYK", "JAM"), isPro: false),
                """
                \(service.subscriptions.count) existing + a 2-alert round trip exceeds the limit of \
                \(limit); the save must show the paywall instead of storing both
                """
            )
        }
    }

    func testWouldExceedFreeLimit_singleAlertMayFillLastSlot() {
        withEmptySubscriptions {
            service.addSubscriptions(distinctSubscriptions(limit - 1))

            XCTAssertFalse(
                service.wouldExceedFreeLimit(adding: [roundTrip("NYK", "JAM")[0]], isPro: false),
                "Reaching exactly \(limit) alerts is allowed; only going past it is paywalled"
            )
        }
    }

    func testWouldExceedFreeLimit_alreadySavedDirectionDoesNotCount() {
        // Re-saving a direction the user already has stores nothing, so only the
        // new return leg should count against the last free slot.
        withEmptySubscriptions {
            let trip = roundTrip("NYK", "JAM")
            service.addSubscriptions(distinctSubscriptions(limit - 2) + [trip[0]])
            XCTAssertEqual(service.subscriptions.count, limit - 1, "Precondition: one slot left")

            XCTAssertFalse(
                service.wouldExceedFreeLimit(adding: trip, isPro: false),
                "Only the return leg is new, so the batch fills the last slot rather than exceeding it"
            )
        }
    }

    func testWouldExceedFreeLimit_neverForPro() {
        withEmptySubscriptions {
            service.addSubscriptions(distinctSubscriptions(limit))

            XCTAssertFalse(
                service.wouldExceedFreeLimit(adding: roundTrip("NYK", "JAM"), isPro: true),
                "Pro has no alert cap, but a save on top of \(service.subscriptions.count) alerts was blocked"
            )
        }
    }

    // MARK: - newSubscriptionCount

    func testNewSubscriptionCount_sameRouteTwiceInBatchCountsOnce() {
        withEmptySubscriptions {
            let sub = roundTrip("NYK", "JAM")[0]

            XCTAssertEqual(
                service.newSubscriptionCount(for: [sub, sub]), 1,
                "addSubscriptions stores the same route once, so the cap must count it once"
            )
        }
    }

    func testNewSubscriptionCount_matchesWhatAddSubscriptionsStores() {
        // The cap is only trustworthy if its projection agrees with the real
        // mutation, so assert the two against each other rather than a constant.
        withEmptySubscriptions {
            let existing = RouteAlertSubscription(dataSource: "NJT", fromStationCode: "NY", toStationCode: "TRE")
            service.addSubscriptions([existing])

            let batch = [
                existing,
                RouteAlertSubscription(dataSource: "NJT", fromStationCode: "TRE", toStationCode: "NY"),
                RouteAlertSubscription(dataSource: "PATH", fromStationCode: "HOB", toStationCode: "WTC"),
                RouteAlertSubscription(dataSource: "PATH", fromStationCode: "HOB", toStationCode: "WTC"),
            ]
            let predicted = service.newSubscriptionCount(for: batch)
            let before = service.subscriptions.count

            service.addSubscriptions(batch)

            XCTAssertEqual(
                service.subscriptions.count - before, predicted,
                """
                newSubscriptionCount predicted \(predicted) new rows but addSubscriptions stored \
                \(service.subscriptions.count - before); a cap built on it would miscount
                """
            )
        }
    }
}
