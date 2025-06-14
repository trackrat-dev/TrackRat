import XCTest
import Combine
@testable import TrackRat

@MainActor
class TrainDetailsViewModelTests: XCTestCase {

    var viewModel: TrainDetailsViewModel!
    var mockAPIService: MockAPIService! // Re-use from TrainListViewModelTests setup
    var mockAppState: AppState!
    var cancellables: Set<AnyCancellable>!

    // Helper to provide AppState
    func appStateProvider() -> AppState? {
        return mockAppState
    }

    override func setUp() {
        super.setUp()
        mockAPIService = MockAPIService()
        mockAppState = AppState() // Create a fresh AppState for each test

        // Initialize viewModel with mocked dependencies
        // Using the trainNumber initializer as an example
        viewModel = TrainDetailsViewModel(
            trainNumber: "T123",
            apiService: mockAPIService,
            appStateProvider: { [weak self] in self?.mockAppState }
        )
        cancellables = []
    }

    override func tearDown() {
        viewModel = nil
        mockAPIService = nil
        mockAppState = nil
        cancellables = nil
        super.tearDown()
    }

    // MARK: - Test Data Loading
    func testLoadTrainDetails_Success() async {
        // Arrange
        let trainId = "T123"
        let dbId = 1
        let fromStationCode = "NYP"
        let selectedDestinationName = "SEC"
        mockAppState.departureStationCode = fromStationCode
        mockAppState.selectedDeparture = "New York Penn Station"
        mockAppState.selectedDestination = selectedDestinationName


        let stop1 = Stop.mock(stationName: "New York Penn Station", stationCode: "NYP", departureTime: Date().addingTimeInterval(-300))
        let stop2 = Stop.mock(stationName: "Secaucus", stationCode: "SEC", scheduledTime: Date().addingTimeInterval(600))
        let stop3 = Stop.mock(stationName: "Somewhere Else", stationCode: "NXT", scheduledTime: Date().addingTimeInterval(1200))
        let mockTrain = Train.mock(id: dbId, trainId: trainId, stops: [stop1, stop2, stop3])
        mockAPIService.fetchTrainDetailsFlexibleResult = .success(mockTrain)

        let trainExpectation = XCTestExpectation(description: "Train details are loaded")
        let stopsExpectation = XCTestExpectation(description: "Displayable stops are processed")

        viewModel.$train
            .dropFirst()
            .sink { train in
                if train != nil {
                    XCTAssertEqual(train?.trainId, trainId)
                    trainExpectation.fulfill()
                }
            }
            .store(in: &cancellables)

        viewModel.$displayableTrainStops
            .dropFirst() // Ignore initial empty value
            .sink { stops in
                if !stops.isEmpty {
                    XCTAssertEqual(stops.count, 2, "Should only contain stops from origin to destination")
                    XCTAssertEqual(stops.first?.stationCode, "NYP")
                    XCTAssertEqual(stops.last?.stationCode, "SEC")
                    stopsExpectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // Act
        await viewModel.loadTrainDetails(fromStationCode: fromStationCode, selectedDestinationName: selectedDestinationName)

        // Assert
        await fulfillment(of: [trainExpectation, stopsExpectation], timeout: 2.0)
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertNil(viewModel.error)
    }

    func testLoadTrainDetails_ApiError() async {
        // Arrange
        mockAPIService.fetchTrainDetailsFlexibleResult = .failure(APIError.noData)
        let errorExpectation = XCTestExpectation(description: "Error is set and train is nil")

        viewModel.$error
            .dropFirst()
            .sink { error in
                XCTAssertNotNil(error)
                XCTAssertEqual(error, "Train not found") // Specific error message from ViewModel
                errorExpectation.fulfill()
            }
            .store(in: &cancellables)

        // Act
        await viewModel.loadTrainDetails(fromStationCode: "NYP", selectedDestinationName: "SEC")

        // Assert
        await fulfillment(of: [errorExpectation], timeout: 1.0)
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertNil(viewModel.train)
    }

    // MARK: - Test Data Refreshing
    func testRefreshTrainDetails_SuccessUpdatesTrain() async {
        // Arrange
        let trainId = "T123"
        let dbId = 1
        let fromStationCode = "NYP"
        let selectedDestinationName = "SEC"
        mockAppState.departureStationCode = fromStationCode
        mockAppState.selectedDeparture = "New York Penn Station"
        mockAppState.selectedDestination = selectedDestinationName

        let initialStop = Stop.mock(stationName: "New York Penn Station", stationCode: "NYP", departureTime: Date(), stopStatus: "ON_TIME")
        let initialTrain = Train.mock(id: dbId, trainId: trainId, status: .onTime, stops: [initialStop])
        viewModel.train = initialTrain // Set initial train

        // Process initial train data to ensure published properties are set before refresh
        await viewModel.processTrainDataAndUpdatePublishedProperties(
            train: initialTrain,
            departureStationCode: fromStationCode,
            selectedDepartureStationName: mockAppState.selectedDeparture,
            selectedDestinationName: selectedDestinationName
        )


        let refreshedStop = Stop.mock(stationName: "New York Penn Station", stationCode: "NYP", departureTime: Date(), stopStatus: "DELAYED")
        let refreshedTrain = Train.mock(id: dbId, trainId: trainId, status: .delayed, stops: [refreshedStop], displayStatus: .delayed) // Ensure displayStatus is also updated
        mockAPIService.fetchTrainDetailsFlexibleResult = .success(refreshedTrain)

        let refreshExpectation = XCTestExpectation(description: "Train details are refreshed")

        var observationCount = 0
        viewModel.$train
            .sink { updatedTrain in
                observationCount += 1
                if observationCount > 1 { // Ignore initial value from setup
                    if updatedTrain?.status == .delayed {
                        refreshExpectation.fulfill()
                    }
                }
            }
            .store(in: &cancellables)

        // Act
        await viewModel.refreshTrainDetails(fromStationCode: fromStationCode, selectedDestinationName: selectedDestinationName)

        // Assert
        await fulfillment(of: [refreshExpectation], timeout: 1.0)
        XCTAssertEqual(viewModel.train?.status, .delayed)
        XCTAssertNil(viewModel.error) // Should be silent on refresh
    }

    // MARK: - Test Haptic Triggers
    func testRefreshTrainDetails_TriggersBoardingHaptic() async {
        // Arrange
        let trainId = "T456"
        let dbId = 2
        let fromStationCode = "PHI"
        let selectedDestinationName = "TRE"
        mockAppState.departureStationCode = fromStationCode
        mockAppState.selectedDeparture = "Philadelphia 30th Street"
        mockAppState.selectedDestination = selectedDestinationName

        viewModel.train = Train.mock(id: dbId, trainId: trainId, status: .onTime, displayStatus: .onTime, displayTrack: nil)
        await viewModel.processTrainDataAndUpdatePublishedProperties(
            train: viewModel.train!,
            departureStationCode: fromStationCode,
            selectedDepartureStationName: mockAppState.selectedDeparture,
            selectedDestinationName: selectedDestinationName
        )


        let boardingTrain = Train.mock(id: dbId, trainId: trainId, status: .boarding, displayStatus: .boarding, displayTrack: "5")
        mockAPIService.fetchTrainDetailsFlexibleResult = .success(boardingTrain)

        let hapticExpectation = XCTestExpectation(description: "Boarding haptic is triggered")
        viewModel.triggerBoardingHaptic = false // Ensure it's initially false

        viewModel.$triggerBoardingHaptic
            .filter { $0 == true }
            .sink { _ in
                hapticExpectation.fulfill()
            }
            .store(in: &cancellables)

        // Act
        await viewModel.refreshTrainDetails(fromStationCode: fromStationCode, selectedDestinationName: selectedDestinationName)

        // Assert
        await fulfillment(of: [hapticExpectation], timeout: 1.0)
        // ViewModel should reset it after setting, or View does. For testing VM, we check it was set.
        // If VM resets, this test needs to capture it before reset or test a different signal.
        // Assuming for now the View is responsible for reset, or we test the brief true state.
    }

    func testRefreshTrainDetails_TriggersTrackAssignedHaptic() async {
        // Arrange
        let trainId = "T789"
        let dbId = 3
        let fromStationCode = "BAL"
        let selectedDestinationName = "WAS"
        mockAppState.departureStationCode = fromStationCode
        mockAppState.selectedDeparture = "Baltimore Penn Station"
        mockAppState.selectedDestination = selectedDestinationName

        viewModel.train = Train.mock(id: dbId, trainId: trainId, status: .onTime, displayStatus: .onTime, displayTrack: nil)
         await viewModel.processTrainDataAndUpdatePublishedProperties(
            train: viewModel.train!,
            departureStationCode: fromStationCode,
            selectedDepartureStationName: mockAppState.selectedDeparture,
            selectedDestinationName: selectedDestinationName
        )

        let trackAssignedTrain = Train.mock(id: dbId, trainId: trainId, status: .onTime, displayStatus: .onTime, displayTrack: "A")
        mockAPIService.fetchTrainDetailsFlexibleResult = .success(trackAssignedTrain)

        let hapticExpectation = XCTestExpectation(description: "Track assigned haptic is triggered")
        viewModel.triggerTrackAssignedHaptic = false

        viewModel.$triggerTrackAssignedHaptic
            .filter { $0 == true }
            .sink { _ in
                hapticExpectation.fulfill()
            }
            .store(in: &cancellables)

        // Act
        await viewModel.refreshTrainDetails(fromStationCode: fromStationCode, selectedDestinationName: selectedDestinationName)

        // Assert
        await fulfillment(of: [hapticExpectation], timeout: 1.0)
    }

    // MARK: - Test Stops Processing
    func testProcessTrainData_FiltersStopsCorrectly() async {
        // Arrange
        let fromStationCode = "NYP"
        let selectedDepartureStationName = "New York Penn Station"
        let selectedDestinationName = "SEC" // Secaucus

        let stop0 = Stop.mock(stationName: "PreOrigin", stationCode: "PRE", departureTime: Date().addingTimeInterval(-1000))
        let stop1 = Stop.mock(stationName: "New York Penn Station", stationCode: "NYP", departureTime: Date().addingTimeInterval(-300))
        let stop2 = Stop.mock(stationName: "Secaucus", stationCode: "SEC", scheduledTime: Date().addingTimeInterval(600))
        let stop3 = Stop.mock(stationName: "Another Stop", stationCode: "NXT", scheduledTime: Date().addingTimeInterval(1200))
        let stop4 = Stop.mock(stationName: "PostDestination", stationCode: "POS", scheduledTime: Date().addingTimeInterval(1800))

        let train = Train.mock(stops: [stop0, stop1, stop2, stop3, stop4])

        let stopsExpectation = XCTestExpectation(description: "Stops are filtered and flags set")

        Publishers.CombineLatest3(viewModel.$displayableTrainStops, viewModel.$hasPreviousDisplayStops, viewModel.$hasMoreDisplayStops)
            .dropFirst()
            .sink { stops, hasPrevious, hasMore in
                if !stops.isEmpty { // Ensure processing has happened
                    XCTAssertEqual(stops.count, 2)
                    XCTAssertEqual(stops.first?.stationCode, "NYP")
                    XCTAssertEqual(stops.last?.stationCode, "SEC")
                    XCTAssertTrue(hasPrevious, "Should have previous stops before NYP")
                    XCTAssertTrue(hasMore, "Should have more stops after SEC")
                    stopsExpectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // Act
        // Directly call processTrainDataAndUpdatePublishedProperties for this unit test
        await viewModel.processTrainDataAndUpdatePublishedProperties(
            train: train,
            departureStationCode: fromStationCode,
            selectedDepartureStationName: selectedDepartureStationName,
            selectedDestinationName: selectedDestinationName
        )

        // Assert
        await fulfillment(of: [stopsExpectation], timeout: 1.0)
    }

    func testProcessTrainData_CalculatesJourneyProgress() async {
        // Arrange
        let fromStationCode = "NYP"
        let selectedDepartureStationName = "New York Penn Station"
        let selectedDestinationName = "TRE" // Trenton

        // Mock stops for a journey: NYP -> NWK -> PHI -> TRE
        // Assume NWK has departed
        let stopNYP = Stop.mock(stationName: "New York Penn Station", stationCode: "NYP", departureTime: Date(), departed: true)
        let stopNWK = Stop.mock(stationName: "Newark Penn Station", stationCode: "NWK", departureTime: Date(), departed: true) // Departed
        let stopPHI = Stop.mock(stationName: "Philadelphia", stationCode: "PHI", scheduledTime: Date(), departed: false)
        let stopTRE = Stop.mock(stationName: "Trenton", stationCode: "TRE", scheduledTime: Date(), departed: false)
        let train = Train.mock(stops: [stopNYP, stopNWK, stopPHI, stopTRE])

        let progressExpectation = XCTestExpectation(description: "Journey progress is calculated")

        Publishers.CombineLatest3(viewModel.$journeyStopsCompleted, viewModel.$journeyTotalStops, viewModel.$journeyProgressPercentage)
            .dropFirst()
            .sink { completed, total, percentage in
                // Expected: NYP (origin) -> NWK (departed, 1st completed) -> PHI -> TRE (destination)
                // Total stops in journey segment (excluding origin): NWK, PHI, TRE = 3
                // Completed stops in journey segment: NWK = 1
                // Percentage: 1/3 * 100 = 33
                if total == 3 { // Check if processing has occurred and total is as expected
                    XCTAssertEqual(completed, 1, "One stop (NWK) should be completed after origin (NYP)")
                    XCTAssertEqual(total, 3, "Total stops in journey segment should be 3 (NWK, PHI, TRE)")
                    XCTAssertEqual(percentage, 33, "Progress should be 33%")
                    progressExpectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // Act
        await viewModel.processTrainDataAndUpdatePublishedProperties(
            train: train,
            departureStationCode: fromStationCode,
            selectedDepartureStationName: selectedDepartureStationName,
            selectedDestinationName: selectedDestinationName
        )

        // Assert
        await fulfillment(of: [progressExpectation], timeout: 1.0)
    }
     func testLoadTrainDetails_NoMatchingDestinationStationCode() async {
        // Arrange
        let trainId = "T123"
        let dbId = 1
        let fromStationCode = "NYP"
        let selectedDestinationName = "NonExistentDest" // This destination name won't have a code in Stations.getStationCode
        mockAppState.departureStationCode = fromStationCode
        mockAppState.selectedDeparture = "New York Penn Station"
        mockAppState.selectedDestination = selectedDestinationName // This is what the view would pass

        // Simulate that Stations.getStationCode(selectedDestinationName) returns nil
        // The ViewModel's processTrainData relies on this for destination filtering.

        let stopNYP = Stop.mock(stationName: "New York Penn Station", stationCode: "NYP", departureTime: Date())
        let stopSEC = Stop.mock(stationName: "Secaucus", stationCode: "SEC", scheduledTime: Date())
        let mockTrain = Train.mock(id: dbId, trainId: trainId, stops: [stopNYP, stopSEC])
        mockAPIService.fetchTrainDetailsFlexibleResult = .success(mockTrain)

        let stopsExpectation = XCTestExpectation(description: "Stops are processed without destination filtering")

        viewModel.$displayableTrainStops
            .dropFirst()
            .sink { stops in
                if !stops.isEmpty {
                    // If selectedDestinationName doesn't map to a code, filterStopsForJourney
                    // should not filter by destination. It will only filter by origin.
                    XCTAssertEqual(stops.count, 2, "Stops should be filtered by origin only")
                    XCTAssertEqual(stops.first?.stationCode, "NYP")
                    XCTAssertFalse(self.viewModel.hasMoreDisplayStops, "Should indicate no more stops if destination is not found for filtering")
                    stopsExpectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // Act
        await viewModel.loadTrainDetails(fromStationCode: fromStationCode, selectedDestinationName: selectedDestinationName)

        // Assert
        await fulfillment(of: [stopsExpectation], timeout: 1.0)
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertNil(viewModel.error)
    }

    func testInit_WithDatabaseId() {
        let vm = TrainDetailsViewModel(trainId: 123, apiService: mockAPIService, appStateProvider: appStateProvider)
        XCTAssertEqual(vm.trainId, 123) // Tests legacy trainId computed property
        XCTAssertNotNil(vm)
        // Internal properties like databaseId, trainNumber, preferredStationCode are private,
        // but we can infer their state by how loadTrainDetails would behave or by testing trainId.
    }

    func testInit_WithTrainNumberAndStationCode() {
        let vm = TrainDetailsViewModel(trainNumber: "T789", fromStationCode: "WAS", apiService: mockAPIService, appStateProvider: appStateProvider)
        XCTAssertNotNil(vm)
        // We'd need to call loadTrainDetails to see if "T789" and "WAS" are used by mockAPIService,
        // but init itself doesn't expose these directly. This test mainly ensures init completes.
    }

    func testLoadTrainDetails_UsesPreferredStationCodeFromInit() async {
        // Arrange
        let trainNumber = "T789"
        let preferredCode = "WAS"
        // Initialize viewModel specifically for this test case
        let localViewModel = TrainDetailsViewModel(
            trainNumber: trainNumber,
            fromStationCode: preferredCode, // This becomes preferredStationCode
            apiService: mockAPIService,
            appStateProvider: { [weak self] in self?.mockAppState }
        )

        let mockTrain = Train.mock(trainId: trainNumber)
        var usedFromStationCode: String?

        // Mock the API service to capture the fromStationCode used
        mockAPIService.fetchTrainDetailsFlexibleResultClosure = { id, tn, fsc in
            usedFromStationCode = fsc
            return .success(mockTrain)
        }

        let expectation = XCTestExpectation(description: "Train details loaded using preferred station code")
        localViewModel.$train
            .dropFirst()
            .sink { train in
                if train != nil {
                    expectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // Act
        // Call loadTrainDetails with fromStationCode: nil to force use of preferredStationCode
        await localViewModel.loadTrainDetails(fromStationCode: nil, selectedDestinationName: "DEST")

        // Assert
        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertEqual(usedFromStationCode, preferredCode, "Should have used preferredStationCode from init")
        XCTAssertNotNil(localViewModel.train)
    }

    func testRefreshTrainDetails_ApiErrorIsSilent() async {
        // Arrange
        let initialTrain = Train.mock(id: 1, trainId: "T1")
        viewModel.train = initialTrain
        // Ensure params for refresh are set if viewModel is the shared one
        // For this test, let's assume viewModel is already configured with a train and its necessary IDs for refresh.
        // If using the class-level viewModel, its internal trainNumber or databaseId should be set.
        // The default setUp initializes viewModel with trainNumber: "T123".

        mockAPIService.fetchTrainDetailsFlexibleResult = .failure(APIError.invalidURL)

        // Act
        await viewModel.refreshTrainDetails(fromStationCode: "NYP", selectedDestinationName: "SEC")

        // Assert
        XCTAssertNil(viewModel.error, "Error should be nil for silent refresh failure.")
        XCTAssertEqual(viewModel.train?.id, initialTrain.id, "Train data should not change on silent error.")
    }
}

// Ensure MockAPIService is available (it's in MockModels.swift or a shared test utility file from previous step)
// Ensure Train.mock and Stop.mock are available (from MockModels.swift)
