import XCTest
@testable import TrackRat

/// Tests for the system list onboarding offers on its first screen.
final class OnboardingViewTests: XCTestCase {

    func testOffersEverySelectableSystem() {
        // A system missing here can't be picked during setup at all, which is how
        // PATCO riders were previously left with no way to finish onboarding.
        let offered = Set(OnboardingView.orderedSystems(suggested: nil))

        XCTAssertEqual(offered, Set(TrainSystem.availableCases))
        XCTAssertTrue(offered.contains(.patco), "PATCO must be selectable during setup")
    }

    func testNeverOffersADisabledSystem() {
        let offered = OnboardingView.orderedSystems(suggested: nil)

        for system in offered {
            XCTAssertFalse(system.isDisabled, "\(system) is disabled app-wide and must not be offered")
        }
    }

    func testOrdersAlphabeticallyByDisplayNameWithoutASuggestion() {
        let names = OnboardingView.orderedSystems(suggested: nil).map(\.displayName)

        XCTAssertEqual(names, names.sorted(), "Unordered list is hard to scan: \(names)")
    }

    func testPromotesTheNearbySystemToTheTop() {
        let ordered = OnboardingView.orderedSystems(suggested: .septaMetro)

        XCTAssertEqual(ordered.first, .septaMetro)
        XCTAssertEqual(ordered.count, TrainSystem.availableCases.count, "Promotion must not drop or duplicate a system")
        XCTAssertEqual(Set(ordered), Set(TrainSystem.availableCases))
    }

    // MARK: - Changing systems

    func testKeepsStationsTheSelectedSystemServes() {
        let newark = Station(code: "NP", name: "Newark Penn Station")
        let trenton = Station(code: "TR", name: "Trenton Transit Center")

        let served = OnboardingView.stationsServed(
            by: [.njt],
            home: trenton,
            work: newark,
            favorites: [newark]
        )

        XCTAssertEqual(served.home?.code, "TR")
        XCTAssertEqual(served.work?.code, "NP")
        XCTAssertEqual(served.favorites.map(\.code), ["NP"])
    }

    func testDropsStationsTheNewlySelectedSystemDoesNotServe() {
        // Stepping back and switching NJ Transit → PATH must not carry Trenton
        // forward: the picker wouldn't offer it, and PATH doesn't run there.
        let trenton = Station(code: "TR", name: "Trenton Transit Center")
        let newark = Station(code: "NP", name: "Newark Penn Station")  // NJT + PATH

        let served = OnboardingView.stationsServed(
            by: [.path],
            home: trenton,
            work: newark,
            favorites: [trenton, newark]
        )

        XCTAssertNil(served.home, "Trenton is not on PATH and should not survive the switch")
        XCTAssertEqual(served.work?.code, "NP", "Newark Penn is served by PATH and should stay")
        XCTAssertEqual(served.favorites.map(\.code), ["NP"])
    }

    func testEmptySelectionsSurviveUnchanged() {
        let served = OnboardingView.stationsServed(
            by: [.njt],
            home: nil,
            work: nil,
            favorites: []
        )

        XCTAssertNil(served.home)
        XCTAssertNil(served.work)
        XCTAssertTrue(served.favorites.isEmpty)
    }

    func testIgnoresASuggestionThatIsNotSelectable() {
        // A disabled system can never be suggested, but if one ever leaked
        // through it must not be added to the list as a selectable option.
        let ordered = OnboardingView.orderedSystems(suggested: .bart)

        XCTAssertFalse(ordered.contains(.bart))
        XCTAssertEqual(ordered, OnboardingView.orderedSystems(suggested: nil))
    }
}
