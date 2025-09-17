package com.trackrat.android.ui.trainlist

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.trackrat.android.data.models.ApiException
import com.trackrat.android.data.models.ApiResult
import com.trackrat.android.data.models.DepartureV2
import com.trackrat.android.data.models.TrainV2
import com.trackrat.android.data.preferences.UserPreferencesRepository
import com.trackrat.android.data.repository.TrackRatRepository
import com.trackrat.android.data.mappers.TrainMappers
import com.trackrat.android.utils.ErrorUtils.shouldStopAutoRefresh
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * ViewModel for the train list screen with robust error handling
 */
@HiltViewModel
class TrainListViewModel @Inject constructor(
    private val repository: TrackRatRepository,
    private val preferencesRepository: UserPreferencesRepository,
    private val savedStateHandle: SavedStateHandle
) : ViewModel() {
    
    companion object {
        private const val AUTO_REFRESH_INTERVAL_MS = 30_000L // 30 seconds
        
        // SavedState keys for state restoration
        private const val KEY_FROM_STATION = "from_station"
        private const val KEY_TO_STATION = "to_station"
        private const val KEY_LAST_UPDATED = "last_updated"
        private const val KEY_TRAINS_JSON = "trains_json"
    }

    // UI State with structured error handling
    data class UiState(
        val trains: List<TrainV2> = emptyList(),
        val isLoading: Boolean = false,
        val isRefreshing: Boolean = false,
        val error: ApiException? = null,
        val fromStationCode: String? = null,
        val fromStationName: String? = null,
        val toStationCode: String? = null,
        val toStationName: String? = null,
        val lastUpdated: Long = 0L,
        val canRetry: Boolean = false,
        val autoRefreshEnabled: Boolean = true,
        val hapticFeedbackEnabled: Boolean = true
    )

    private val _uiState = MutableStateFlow(UiState())
    
    // Combine UI state with user preferences
    val uiState: StateFlow<UiState> = combine(
        _uiState,
        preferencesRepository.userPreferencesFlow
    ) { state, preferences ->
        state.copy(
            autoRefreshEnabled = preferences.autoRefreshEnabled,
            hapticFeedbackEnabled = preferences.hapticFeedbackEnabled
        )
    }.stateIn(
        scope = viewModelScope,
        started = kotlinx.coroutines.flow.SharingStarted.WhileSubscribed(5000),
        initialValue = UiState()
    )

    // Auto-refresh job
    private var autoRefreshJob: Job? = null

    init {
        // Restore state from SavedStateHandle if available
        restoreState()
    }
    
    /**
     * Load trains between stations with improved error handling
     */
    fun loadTrains(fromStation: String, toStation: String?) {
        viewModelScope.launch {
            // Cancel existing auto-refresh
            autoRefreshJob?.cancel()
            
            // Save current stations to state
            saveStationsToState(fromStation, toStation)
            
            // Update station info in state
            _uiState.value = _uiState.value.copy(
                fromStationCode = fromStation,
                toStationCode = toStation,
                isLoading = true,
                error = null,
                canRetry = false
            )
            
            // Fetch trains
            fetchTrains(fromStation, toStation)
        }
    }

    /**
     * Manual refresh (pull-to-refresh)
     */
    fun refresh() {
        val state = _uiState.value
        if (state.fromStationCode != null) {
            viewModelScope.launch {
                _uiState.value = _uiState.value.copy(
                    isRefreshing = true,
                    error = null
                )
                fetchTrains(state.fromStationCode, state.toStationCode)
            }
        }
    }
    
    /**
     * Retry failed request
     */
    fun retry() {
        val state = _uiState.value
        if (state.fromStationCode != null) {
            loadTrains(state.fromStationCode, state.toStationCode)
        }
    }

    /**
     * Fetch trains from API with structured error handling
     */
    private suspend fun fetchTrains(fromStation: String, toStation: String?) {
        when (val result = repository.getDepartures(fromStation, toStation)) {
            is ApiResult.Success -> {
                // Convert DepartureV2 to TrainV2 format for UI compatibility
                val uniqueTrains = result.data.departures
                    .map { departure -> TrainMappers.departureToTrain(departure, fromStation) }
                    .distinctBy { it.trainId }
                    .filter { train -> 
                        // Filter out trains that departed more than 30 minutes ago
                        val departureTime = train.getScheduledDepartureTime(fromStation)
                        if (departureTime != null && train.status == "DEPARTED") {
                            val minutesAgo = java.time.Duration.between(
                                departureTime,
                                java.time.ZonedDateTime.now(java.time.ZoneId.of("America/New_York"))
                            ).toMinutes()
                            minutesAgo <= 30
                        } else {
                            true // Keep all non-departed trains or trains without departure time
                        }
                    }
                    .sortedBy { it.getScheduledDepartureTime(fromStation) }
                
                _uiState.value = _uiState.value.copy(
                    trains = uniqueTrains,
                    fromStationName = result.data.metadata.fromStation.name,
                    toStationName = result.data.metadata.toStation?.name,
                    isLoading = false,
                    isRefreshing = false,
                    error = null,
                    lastUpdated = System.currentTimeMillis(),
                    canRetry = false
                )
                
                // Save state for restoration
                saveTrainsToState(uniqueTrains)
                savedStateHandle[KEY_LAST_UPDATED] = System.currentTimeMillis()
                
                // Save user's last selected stations
                viewModelScope.launch {
                    preferencesRepository.updateLastStations(fromStation, toStation)
                    preferencesRepository.updateLastRefreshTime()
                }
                
                // Start auto-refresh only on successful load
                startAutoRefresh(fromStation, toStation)
            }
            
            is ApiResult.Error -> {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    error = result.exception,
                    canRetry = true
                )
                // Don't start auto-refresh on error
                autoRefreshJob?.cancel()
            }
            
            is ApiResult.Loading -> {
                // Should not happen with current implementation
                // but handle gracefully if API changes
            }
        }
    }

    /**
     * Start lifecycle-aware auto-refresh timer
     */
    private fun startAutoRefresh(fromStation: String, toStation: String?) {
        // Cancel existing job first
        autoRefreshJob?.cancel()
        
        autoRefreshJob = viewModelScope.launch {
            while (isActive) {
                delay(AUTO_REFRESH_INTERVAL_MS)
                
                // Only auto-refresh if enabled and we don't have an error state
                val currentState = _uiState.value
                val currentPrefs = preferencesRepository.userPreferencesFlow.first()
                if (currentState.error == null && currentPrefs.autoRefreshEnabled) {
                    when (val result = repository.getDepartures(fromStation, toStation)) {
                        is ApiResult.Success -> {
                            val uniqueTrains = result.data.departures
                                .map { departure -> TrainMappers.departureToTrain(departure, fromStation) }
                                .distinctBy { it.trainId }
                                .filter { train -> 
                                    // Filter out trains that departed more than 30 minutes ago
                                    val departureTime = train.getScheduledDepartureTime(fromStation)
                                    if (departureTime != null && train.status == "DEPARTED") {
                                        val minutesAgo = java.time.Duration.between(
                                            departureTime,
                                            java.time.ZonedDateTime.now(java.time.ZoneId.of("America/New_York"))
                                        ).toMinutes()
                                        minutesAgo <= 30
                                    } else {
                                        true // Keep all non-departed trains or trains without departure time
                                    }
                                }
                                .sortedBy { it.getScheduledDepartureTime(fromStation) }
                            
                            _uiState.value = _uiState.value.copy(
                                trains = uniqueTrains,
                                lastUpdated = System.currentTimeMillis(),
                                error = null
                            )
                        }
                        is ApiResult.Error -> {
                            // Use enhanced error recovery strategy
                            if (result.exception.shouldStopAutoRefresh()) {
                                // Stop auto-refresh for persistent errors
                                _uiState.value = _uiState.value.copy(
                                    error = result.exception,
                                    canRetry = true
                                )
                                break
                            } else {
                                // Continue auto-refresh for transient errors
                                // Add extra delay for server errors to be less aggressive
                                if (result.exception is ApiException.ServerError) {
                                    delay(15_000) // Extra delay for server issues
                                }
                                // For network/timeout errors, continue with normal interval
                            }
                        }
                        is ApiResult.Loading -> {
                            // Continue loop
                        }
                    }
                }
            }
        }
    }

    /**
     * Stop auto-refresh when ViewModel is cleared
     */
    override fun onCleared() {
        super.onCleared()
        autoRefreshJob?.cancel()
    }
    
    /**
     * Get display status for a train (uses statusV2 if available)
     */
    fun getTrainDisplayStatus(train: TrainV2): String {
        return TrainMappers.getDisplayStatus(train)
    }
    
    /**
     * Check if a train is boarding
     */
    fun isTrainBoarding(train: TrainV2): Boolean {
        return TrainMappers.isBoarding(train)
    }
    
    /**
     * Restore state from SavedStateHandle
     */
    private fun restoreState() {
        val fromStation = savedStateHandle.get<String>(KEY_FROM_STATION)
        val toStation = savedStateHandle.get<String>(KEY_TO_STATION)
        val lastUpdated = savedStateHandle.get<Long>(KEY_LAST_UPDATED) ?: 0L
        
        if (fromStation != null) {
            // Restore basic state
            _uiState.value = _uiState.value.copy(
                fromStationCode = fromStation,
                toStationCode = toStation,
                lastUpdated = lastUpdated
            )
            
            // Only restore trains if the data is relatively fresh (less than 5 minutes old)
            val dataAge = System.currentTimeMillis() - lastUpdated
            val maxDataAge = 5 * 60 * 1000L // 5 minutes
            
            if (dataAge < maxDataAge) {
                restoreTrainsFromState()
            } else {
                // Data is stale, reload
                loadTrains(fromStation, toStation)
            }
        }
    }
    
    /**
     * Save station codes to SavedStateHandle
     */
    private fun saveStationsToState(fromStation: String, toStation: String?) {
        savedStateHandle[KEY_FROM_STATION] = fromStation
        savedStateHandle[KEY_TO_STATION] = toStation
    }
    
    /**
     * Save trains to SavedStateHandle (simplified approach)
     */
    private fun saveTrainsToState(trains: List<TrainV2>) {
        // For simplicity, we'll save just the count and key train IDs
        // In a full implementation, you might serialize the entire list
        val trainIds = trains.take(10).map { it.trainId } // Save first 10 train IDs
        savedStateHandle["train_ids"] = trainIds
        savedStateHandle["train_count"] = trains.size
    }
    
    /**
     * Restore trains from SavedStateHandle
     */
    private fun restoreTrainsFromState() {
        // This is a simplified restoration
        // In practice, you might want to serialize/deserialize the full train objects
        val trainCount = savedStateHandle.get<Int>("train_count") ?: 0
        
        if (trainCount > 0) {
            // Show cached state but trigger a refresh
            val fromStation = savedStateHandle.get<String>(KEY_FROM_STATION)
            val toStation = savedStateHandle.get<String>(KEY_TO_STATION)
            
            if (fromStation != null) {
                _uiState.value = _uiState.value.copy(
                    isLoading = true
                )
                // Refresh data in background
                viewModelScope.launch {
                    fetchTrains(fromStation, toStation)
                }
            }
        }
    }
    
}