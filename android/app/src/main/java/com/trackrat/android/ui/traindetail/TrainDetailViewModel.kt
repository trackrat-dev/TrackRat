package com.trackrat.android.ui.traindetail

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.viewModelScope
import com.trackrat.android.data.models.ApiException
import com.trackrat.android.data.models.ApiResult
import com.trackrat.android.data.models.TrainDetailV2
import com.trackrat.android.data.repository.TrackRatRepository
import com.trackrat.android.services.TrainTrackingService
import com.trackrat.android.utils.ErrorUtils.shouldStopAutoRefresh
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.time.LocalDate
import javax.inject.Inject

/**
 * ViewModel for the train detail screen with robust error handling
 */
@HiltViewModel
class TrainDetailViewModel @Inject constructor(
    application: Application,
    private val repository: TrackRatRepository,
    private val savedStateHandle: SavedStateHandle
) : AndroidViewModel(application) {

    // UI State with structured error handling
    data class UiState(
        val train: TrainDetailV2? = null,
        val isLoading: Boolean = false,
        val isRefreshing: Boolean = false,
        val error: ApiException? = null,
        val lastUpdated: Long = 0L,
        val canRetry: Boolean = false
    )

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    // Tracking state - observe the service's tracking state
    val isTrackingTrain: StateFlow<Boolean> = TrainTrackingService.isTracking
        .map { trackingId -> 
            trackingId != null && trackingId == currentTrainId 
        }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(), false)

    // Auto-refresh job
    private var autoRefreshJob: Job? = null
    
    // Store current request params for retry
    private var currentTrainId: String? = null
    private var currentDate: String? = null
    
    companion object {
        private const val AUTO_REFRESH_INTERVAL_MS = 30_000L // 30 seconds
        
        // SavedState keys for state restoration
        private const val KEY_TRAIN_ID = "train_id"
        private const val KEY_DATE = "date"
        private const val KEY_LAST_UPDATED = "last_updated"
        private const val KEY_TRAIN_STATUS = "train_status"
    }

    init {
        // Restore state from SavedStateHandle if available
        restoreState()
    }
    
    /**
     * Load train details with improved error handling
     */
    fun loadTrainDetails(trainId: String, date: String? = null) {
        currentTrainId = trainId
        currentDate = date ?: getCurrentDateString()
        
        // Save current parameters to state
        saveParametersToState(trainId, currentDate!!)
        
        viewModelScope.launch {
            // Cancel existing auto-refresh
            autoRefreshJob?.cancel()
            
            _uiState.value = _uiState.value.copy(
                isLoading = true,
                error = null,
                canRetry = false
            )
            
            // Fetch train details
            fetchTrainDetails(trainId, currentDate!!)
        }
    }

    /**
     * Manual refresh
     */
    fun refresh() {
        currentTrainId?.let { trainId ->
            viewModelScope.launch {
                _uiState.value = _uiState.value.copy(
                    isRefreshing = true,
                    error = null
                )
                fetchTrainDetails(trainId, currentDate ?: getCurrentDateString())
            }
        }
    }
    
    /**
     * Retry failed request
     */
    fun retry() {
        currentTrainId?.let { trainId ->
            loadTrainDetails(trainId, currentDate)
        }
    }

    /**
     * Fetch train details from API with structured error handling
     */
    private suspend fun fetchTrainDetails(trainId: String, date: String) {
        when (val result = repository.getTrainDetails(trainId, date, refresh = true)) {
            is ApiResult.Success -> {
                val currentTime = System.currentTimeMillis()
                _uiState.value = _uiState.value.copy(
                    train = result.data.train,
                    isLoading = false,
                    isRefreshing = false,
                    error = null,
                    lastUpdated = currentTime,
                    canRetry = false
                )
                
                // Save state for restoration
                savedStateHandle[KEY_LAST_UPDATED] = currentTime
                savedStateHandle[KEY_TRAIN_STATUS] = result.data.train.rawTrainState ?: ""
                
                // Start auto-refresh only on successful load
                startAutoRefresh(trainId, date)
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
    private fun startAutoRefresh(trainId: String, date: String) {
        // Cancel existing job first
        autoRefreshJob?.cancel()
        
        autoRefreshJob = viewModelScope.launch {
            while (isActive) {
                delay(AUTO_REFRESH_INTERVAL_MS)
                
                // Only auto-refresh if we don't have an error state
                if (_uiState.value.error == null) {
                    when (val result = repository.getTrainDetails(trainId, date, refresh = true)) {
                        is ApiResult.Success -> {
                            _uiState.value = _uiState.value.copy(
                                train = result.data.train,
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
     * Get current date as string in API format
     */
    private fun getCurrentDateString(): String {
        return LocalDate.now().toString() // YYYY-MM-DD format
    }
    
    /**
     * Toggle train tracking on/off
     */
    fun toggleTracking() {
        val trainId = currentTrainId ?: return
        val date = currentDate ?: getCurrentDateString()
        val context = getApplication<Application>()
        
        if (TrainTrackingService.isTrackingTrain(trainId)) {
            // Stop tracking
            TrainTrackingService.stopTracking(context)
        } else {
            // Start tracking
            TrainTrackingService.startTracking(
                context = context,
                trainId = trainId,
                date = date,
                fromStation = _uiState.value.train?.route?.originCode
            )
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
     * Get display status for the train
     */
    fun getTrainDisplayStatus(train: TrainDetailV2): String {
        // TrainDetailV2 doesn't have statusV2, use the raw_train_state
        return train.rawTrainState ?: "UNKNOWN"
    }
    
    /**
     * Check if a train is boarding
     */
    fun isTrainBoarding(train: TrainDetailV2): Boolean {
        val status = train.rawTrainState ?: ""
        return status.equals("BOARDING", ignoreCase = true) || 
               status.equals("ALL ABOARD", ignoreCase = true)
    }
    
    /**
     * Restore state from SavedStateHandle
     */
    private fun restoreState() {
        val trainId = savedStateHandle.get<String>(KEY_TRAIN_ID)
        val date = savedStateHandle.get<String>(KEY_DATE)
        val lastUpdated = savedStateHandle.get<Long>(KEY_LAST_UPDATED) ?: 0L
        
        if (trainId != null && date != null) {
            currentTrainId = trainId
            currentDate = date
            
            // Check if cached data is still fresh (less than 2 minutes old)
            val dataAge = System.currentTimeMillis() - lastUpdated
            val maxDataAge = 2 * 60 * 1000L // 2 minutes
            
            if (dataAge < maxDataAge) {
                // Restore basic state and refresh in background
                _uiState.value = _uiState.value.copy(
                    lastUpdated = lastUpdated,
                    isLoading = false
                )
                
                // Refresh data in background
                viewModelScope.launch {
                    fetchTrainDetails(trainId, date)
                }
            } else {
                // Data is stale, do a fresh load
                loadTrainDetails(trainId, date)
            }
        }
    }
    
    /**
     * Save current parameters to SavedStateHandle
     */
    private fun saveParametersToState(trainId: String, date: String) {
        savedStateHandle[KEY_TRAIN_ID] = trainId
        savedStateHandle[KEY_DATE] = date
    }
}