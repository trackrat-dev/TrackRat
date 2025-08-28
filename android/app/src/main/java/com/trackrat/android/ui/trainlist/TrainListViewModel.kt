package com.trackrat.android.ui.trainlist

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.trackrat.android.data.models.ApiException
import com.trackrat.android.data.models.ApiResult
import com.trackrat.android.data.models.TrainV2
import com.trackrat.android.data.preferences.UserPreferencesRepository
import com.trackrat.android.data.repository.TrackRatRepository
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
    private val preferencesRepository: UserPreferencesRepository
) : ViewModel() {

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
    
    companion object {
        private const val AUTO_REFRESH_INTERVAL_MS = 30_000L // 30 seconds
    }

    /**
     * Load trains between stations with improved error handling
     */
    fun loadTrains(fromStation: String, toStation: String?) {
        viewModelScope.launch {
            // Cancel existing auto-refresh
            autoRefreshJob?.cancel()
            
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
                // Deduplicate trains by train_id and sort by departure time
                val uniqueTrains = result.data.trains
                    .distinctBy { it.trainId }
                    .sortedBy { it.getScheduledDepartureTime(fromStation) }
                
                _uiState.value = _uiState.value.copy(
                    trains = uniqueTrains,
                    fromStationName = result.data.fromStation.name,
                    toStationName = result.data.toStation?.name,
                    isLoading = false,
                    isRefreshing = false,
                    error = null,
                    lastUpdated = System.currentTimeMillis(),
                    canRetry = false
                )
                
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
                            val uniqueTrains = result.data.trains
                                .distinctBy { it.trainId }
                                .sortedBy { it.getScheduledDepartureTime(fromStation) }
                            
                            _uiState.value = _uiState.value.copy(
                                trains = uniqueTrains,
                                lastUpdated = System.currentTimeMillis(),
                                error = null
                            )
                        }
                        is ApiResult.Error -> {
                            // Stop auto-refresh on persistent errors
                            if (result.exception !is ApiException.NetworkError) {
                                _uiState.value = _uiState.value.copy(
                                    error = result.exception,
                                    canRetry = true
                                )
                                break
                            }
                            // Continue auto-refresh for network errors
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
        return train.statusV2?.enhancedStatus ?: train.status
    }
    
    /**
     * Check if a train is boarding
     */
    fun isTrainBoarding(train: TrainV2): Boolean {
        val status = train.statusV2?.status ?: train.status
        return status.equals("BOARDING", ignoreCase = true) || 
               status.equals("ALL ABOARD", ignoreCase = true)
    }
}