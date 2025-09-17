package com.trackrat.android.ui.trainlist

import com.trackrat.android.data.models.ApiException
import com.trackrat.android.data.models.ApiResult
import com.trackrat.android.data.models.DeparturesResponse
import com.trackrat.android.data.models.StationV2
import com.trackrat.android.data.models.TrainV2
import com.trackrat.android.data.preferences.UserPreferencesRepository
import com.trackrat.android.data.repository.TrackRatRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.Mock
import org.mockito.Mockito.*
import org.mockito.junit.MockitoJUnitRunner

/**
 * Unit tests for TrainListViewModel
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(MockitoJUnitRunner::class)
class TrainListViewModelTest {

    @Mock
    private lateinit var repository: TrackRatRepository
    
    @Mock
    private lateinit var preferencesRepository: UserPreferencesRepository
    
    private lateinit var viewModel: TrainListViewModel
    
    private val testDispatcher = StandardTestDispatcher()

    @Before
    fun setup() {
        Dispatchers.setMain(testDispatcher)
        
        // Setup default preferences flow
        val defaultPreferences = UserPreferencesRepository.UserPreferences()
        `when`(preferencesRepository.userPreferencesFlow).thenReturn(flowOf(defaultPreferences))
        
        viewModel = TrainListViewModel(repository, preferencesRepository)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `initial state is correct`() {
        // Given: Fresh ViewModel
        val initialState = viewModel.uiState.value
        
        // Then: Initial state values are correct
        assertTrue(initialState.trains.isEmpty())
        assertFalse(initialState.isLoading)
        assertFalse(initialState.isRefreshing)
        assertNull(initialState.error)
        assertNull(initialState.fromStationCode)
        assertNull(initialState.toStationCode)
        assertEquals(0L, initialState.lastUpdated)
        assertFalse(initialState.canRetry)
        assertTrue(initialState.autoRefreshEnabled)
        assertTrue(initialState.hapticFeedbackEnabled)
    }

    @Test
    fun `loadTrains success updates state correctly`() = runTest {
        // Given: Successful API response
        val fromStation = "NY"
        val toStation = "NP"
        val mockTrains = listOf(
            TrainV2(trainId = "123", status = "ON TIME", destination = "Newark"),
            TrainV2(trainId = "456", status = "DELAYED", destination = "Trenton")
        )
        val mockResponse = DeparturesResponse(
            trains = mockTrains,
            fromStation = StationV2(code = fromStation, name = "New York Penn"),
            toStation = StationV2(code = toStation, name = "Newark Penn")
        )
        `when`(repository.getDepartures(fromStation, toStation))
            .thenReturn(ApiResult.Success(mockResponse))
        
        // When: Loading trains
        viewModel.loadTrains(fromStation, toStation)
        advanceUntilIdle()
        
        // Then: State is updated correctly
        val state = viewModel.uiState.value
        assertEquals(2, state.trains.size)
        assertEquals("123", state.trains[0].trainId)
        assertEquals("456", state.trains[1].trainId)
        assertEquals(fromStation, state.fromStationCode)
        assertEquals(toStation, state.toStationCode)
        assertEquals("New York Penn", state.fromStationName)
        assertEquals("Newark Penn", state.toStationName)
        assertFalse(state.isLoading)
        assertNull(state.error)
        assertFalse(state.canRetry)
        assertTrue(state.lastUpdated > 0)
    }

    @Test
    fun `loadTrains error updates state correctly`() = runTest {
        // Given: API error
        val fromStation = "NY"
        val toStation = "NP"
        val error = ApiException.NetworkError("No connection")
        `when`(repository.getDepartures(fromStation, toStation))
            .thenReturn(ApiResult.Error(error))
        
        // When: Loading trains
        viewModel.loadTrains(fromStation, toStation)
        advanceUntilIdle()
        
        // Then: Error state is set
        val state = viewModel.uiState.value
        assertTrue(state.trains.isEmpty())
        assertFalse(state.isLoading)
        assertEquals(error, state.error)
        assertTrue(state.canRetry)
    }

    @Test
    fun `loadTrains sets loading state initially`() = runTest {
        // Given: Pending API response
        val fromStation = "NY"
        val toStation = "NP"
        
        // When: Starting to load trains (before completion)
        viewModel.loadTrains(fromStation, toStation)
        
        // Then: Loading state should be set immediately
        val state = viewModel.uiState.value
        assertTrue(state.isLoading)
        assertNull(state.error)
        assertFalse(state.canRetry)
        assertEquals(fromStation, state.fromStationCode)
        assertEquals(toStation, state.toStationCode)
    }

    @Test
    fun `refresh calls repository with current stations`() = runTest {
        // Given: ViewModel with loaded state
        val fromStation = "NY"
        val toStation = "NP"
        viewModel.loadTrains(fromStation, toStation)
        advanceUntilIdle()
        
        // Setup mock for refresh call
        val mockResponse = DeparturesResponse(
            trains = emptyList(),
            fromStation = StationV2(code = fromStation, name = "New York Penn"),
            toStation = StationV2(code = toStation, name = "Newark Penn")
        )
        `when`(repository.getDepartures(fromStation, toStation))
            .thenReturn(ApiResult.Success(mockResponse))
        
        // When: Refreshing
        viewModel.refresh()
        advanceUntilIdle()
        
        // Then: Repository is called with correct parameters
        verify(repository, atLeast(2)).getDepartures(fromStation, toStation)
        
        // And: Refreshing state is handled
        val state = viewModel.uiState.value
        assertFalse(state.isRefreshing)
    }

    @Test
    fun `retry calls loadTrains with current stations`() = runTest {
        // Given: ViewModel with error state
        val fromStation = "NY"
        val toStation = "NP"
        val error = ApiException.NetworkError("No connection")
        `when`(repository.getDepartures(fromStation, toStation))
            .thenReturn(ApiResult.Error(error))
        
        viewModel.loadTrains(fromStation, toStation)
        advanceUntilIdle()
        
        // Setup success response for retry
        val mockResponse = DeparturesResponse(
            trains = emptyList(),
            fromStation = StationV2(code = fromStation, name = "New York Penn"),
            toStation = StationV2(code = toStation, name = "Newark Penn")
        )
        `when`(repository.getDepartures(fromStation, toStation))
            .thenReturn(ApiResult.Success(mockResponse))
        
        // When: Retrying
        viewModel.retry()
        advanceUntilIdle()
        
        // Then: Repository is called again
        verify(repository, atLeast(2)).getDepartures(fromStation, toStation)
    }

    @Test
    fun `getTrainDisplayStatus returns statusV2 when available`() {
        // Given: Train with statusV2
        val train = TrainV2(
            trainId = "123", 
            status = "BOARDING",
            statusV2 = TrainV2.StatusV2(
                status = "BOARDING",
                enhancedStatus = "BOARDING - ALL ABOARD"
            )
        )
        
        // When: Getting display status
        val displayStatus = viewModel.getTrainDisplayStatus(train)
        
        // Then: Enhanced status is returned
        assertEquals("BOARDING - ALL ABOARD", displayStatus)
    }

    @Test
    fun `getTrainDisplayStatus falls back to regular status`() {
        // Given: Train without statusV2
        val train = TrainV2(trainId = "123", status = "ON TIME")
        
        // When: Getting display status
        val displayStatus = viewModel.getTrainDisplayStatus(train)
        
        // Then: Regular status is returned
        assertEquals("ON TIME", displayStatus)
    }

    @Test
    fun `isTrainBoarding returns true for boarding status`() {
        // Given: Train with boarding status
        val train = TrainV2(trainId = "123", status = "BOARDING")
        
        // When: Checking if boarding
        val isBoarding = viewModel.isTrainBoarding(train)
        
        // Then: Should return true
        assertTrue(isBoarding)
    }

    @Test
    fun `isTrainBoarding returns true for all aboard status`() {
        // Given: Train with all aboard status
        val train = TrainV2(trainId = "123", status = "ALL ABOARD")
        
        // When: Checking if boarding
        val isBoarding = viewModel.isTrainBoarding(train)
        
        // Then: Should return true
        assertTrue(isBoarding)
    }

    @Test
    fun `isTrainBoarding returns false for other status`() {
        // Given: Train with different status
        val train = TrainV2(trainId = "123", status = "DEPARTED")
        
        // When: Checking if boarding
        val isBoarding = viewModel.isTrainBoarding(train)
        
        // Then: Should return false
        assertFalse(isBoarding)
    }
}