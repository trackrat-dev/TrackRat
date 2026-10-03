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

    func testSwitchingSystemsKeepsStationsLoadedFromStorage() {
        // A free user switching NJ Transit → PATH must deselect their only system,
        // which re-shows onboarding pre-filled with their saved stations. Picking
        // PATH must not delete the NJT stations they saved — only stations picked
        // during this session are pruned.
        let trenton = Station(code: "TR", name: "Trenton Transit Center")         // saved, not on PATH
        let princeton = Station(code: "PJ", name: "Princeton Junction")           // picked now, not on PATH
        let newark = Station(code: "NP", name: "Newark Penn Station")             // on PATH

        let served = OnboardingView.stationsServed(
            by: [.path],
            home: trenton,
            work: newark,
            favorites: [trenton, princeton],
            keeping: ["TR"]
        )

        XCTAssertEqual(served.home?.code, "TR", "A saved home station must survive a system switch")
        XCTAssertEqual(served.work?.code, "NP")
        XCTAssertEqual(
            served.favorites.map(\.code), ["TR"],
            "Saved favorites stay; an unserved station picked this session is dropped"
        )
    }
}

/// Tests for how finishing onboarding writes stations to storage, against the
/// real AppState, StorageService and RatSenseService (UserDefaults-backed).
@MainActor
final class OnboardingPersistenceTests: XCTestCase {

    private let ratSense = RatSenseService.shared

    override func setUp() {
        super.setUp()
        clearStoredStations()
    }

    override func tearDown() {
        clearStoredStations()
        super.tearDown()
    }

    private func clearStoredStations() {
        UserDefaults.standard.removeObject(forKey: "trackrat.favoriteStations")
        ratSense.clearAllData()
    }

    private func favoriteCodes(_ appState: AppState) -> Set<String> {
        Set(appState.favoriteStations.map(\.id))
    }

    func testSavingKeepsRatSenseHistory() {
        // Saving used to clear all RatSense data before rewriting home/work, so
        // every Edit Favorites save (and every self-heal) erased the journey
        // history and Live Activity history its suggestions are built from.
        ratSense.setHomeStation("TR")
        ratSense.setWorkStation("NY")
        ratSense.recordJourneySearch(from: "TR", to: "NY")
        ratSense.recordLiveActivityStart(from: "TR", to: "NY")
        let appState = AppState()

        OnboardingView.persistSelections(
            home: Station(code: "TR", name: "Trenton Transit Center"),
            work: Station(code: "NY", name: "New York Penn Station"),
            favorites: [],
            appState: appState,
            ratSense: ratSense
        )

        let defaults = UserDefaults.standard
        XCTAssertNotNil(defaults.data(forKey: "RatSense.lastJourney"), "Last journey was erased by saving")
        XCTAssertNotNil(defaults.object(forKey: "RatSense.stationPairFrequency"), "Station-pair counts were erased by saving")
        XCTAssertNotNil(defaults.data(forKey: "RatSense.liveActivityHistory"), "Live Activity history was erased by saving")
        XCTAssertEqual(ratSense.getHomeStation(), "TR")
        XCTAssertEqual(ratSense.getWorkStation(), "NY")
    }

    func testSavingReplacesHomeAndWorkAndRemovesDroppedFavorites() {
        ratSense.setHomeStation("TR")
        ratSense.setWorkStation("NY")
        let appState = AppState()
        appState.addFavoriteStation(code: "NP", name: "Newark Penn Station")
        appState.addFavoriteStation(code: "PJ", name: "Princeton Junction")
        print("Before save: home=\(ratSense.getHomeStation() ?? "nil") work=\(ratSense.getWorkStation() ?? "nil") favorites=\(favoriteCodes(appState).sorted())")

        // The user moved home to Hoboken, cleared work, kept Newark, dropped Princeton.
        OnboardingView.persistSelections(
            home: Station(code: "HB", name: "Hoboken"),
            work: nil,
            favorites: [Station(code: "NP", name: "Newark Penn Station")],
            appState: appState,
            ratSense: ratSense
        )
        print("After save: home=\(ratSense.getHomeStation() ?? "nil") work=\(ratSense.getWorkStation() ?? "nil") favorites=\(favoriteCodes(appState).sorted())")

        XCTAssertEqual(ratSense.getHomeStation(), "HB")
        XCTAssertNil(ratSense.getWorkStation(), "A cleared work station must not survive the save")
        XCTAssertEqual(
            favoriteCodes(appState), ["HB", "NP"],
            "Old home/work and the dropped favorite must be gone; the new home and kept favorite present"
        )
    }

    func testSavingAddsNewFavoritesAlongsideKeptOnes() {
        let appState = AppState()
        appState.addFavoriteStation(code: "NP", name: "Newark Penn Station")

        OnboardingView.persistSelections(
            home: Station(code: "TR", name: "Trenton Transit Center"),
            work: Station(code: "NY", name: "New York Penn Station"),
            favorites: [
                Station(code: "NP", name: "Newark Penn Station"),
                Station(code: "HB", name: "Hoboken")
            ],
            appState: appState,
            ratSense: ratSense
        )

        XCTAssertEqual(favoriteCodes(appState), ["TR", "NY", "NP", "HB"])
        XCTAssertEqual(ratSense.getHomeStation(), "TR")
        XCTAssertEqual(ratSense.getWorkStation(), "NY")
    }
}
