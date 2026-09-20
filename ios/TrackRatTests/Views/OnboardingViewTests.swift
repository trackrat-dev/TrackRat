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

    func testIgnoresASuggestionThatIsNotSelectable() {
        // A disabled system can never be suggested, but if one ever leaked
        // through it must not be added to the list as a selectable option.
        let ordered = OnboardingView.orderedSystems(suggested: .bart)

        XCTAssertFalse(ordered.contains(.bart))
        XCTAssertEqual(ordered, OnboardingView.orderedSystems(suggested: nil))
    }
}
