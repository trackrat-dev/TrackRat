package com.trackrat.android.ui.traindetail

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.viewModelScope
import com.trackrat.android.data.models.ApiException
import com.trackrat.android.data.models.ApiResult
import com.trackrat.android.data.models.TrainDetailV2
import com.trackrat.android.data.repository.TrackRatRepository
import com.trackrat.android.services.TrackingStateRepository
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
    private val trackingStateRepository: TrackingStateRepository,
    private val trackPredictionService: com.trackrat.android.data.services.TrackPredictionService,
    private val savedStateHandle: SavedStateHandle
) : AndroidViewModel(application) {

    // UI State with structured error handling
    data class UiState(
        val train: TrainDetailV2? = null,
        val isLoading: Boolean = false,
        val isRefreshing: Boolean = false,
        val error: ApiException? = null,
        val lastUpdated: Long = 0L,
        val canRetry: Boolean = false,
        val platformPredictions: Map<String, Double>? = null,
        val isLoadingPredictions: Boolean = false
    )

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    // Train tracking state
    val isTrackingTrain: StateFlow<Boolean> = trackingStateRepository.isTracking()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), false)

    // Auto-refresh job
    private var autoRefreshJob: Job? = null
    
    // Store current request params for retry
    private var currentTrainId: String? = null
    private var currentDate: String? = null
    private var currentOriginCode: String? = null
    private var currentDestinationCode: String? = null
    
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
                val train = result.data.train

                _uiState.value = _uiState.value.copy(
                    train = train,
                    isLoading = false,
                    isRefreshing = false,
                    error = null,
                    lastUpdated = currentTime,
                    canRetry = false
                )

                // Save state for restoration
                savedStateHandle[KEY_LAST_UPDATED] = currentTime
                savedStateHandle[KEY_TRAIN_STATUS] = train.rawTrainState ?: ""

                // Load predictions if applicable
                loadPredictions(train)

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
     * Set origin code for tracking
     */
    fun setOriginCode(code: String) {
        currentOriginCode = code
        savedStateHandle["originCode"] = code
    }

    /**
     * Set destination code for tracking
     */
    fun setDestinationCode(code: String) {
        currentDestinationCode = code
        savedStateHandle["destinationCode"] = code
    }

    /**
     * Toggle train tracking on/off
     */
    fun toggleTracking() {
        val context = getApplication<Application>()
        viewModelScope.launch {
            val isTracking = isTrackingTrain.value
            val train = _uiState.value.train

            if (isTracking) {
                // Stop tracking
                TrainTrackingService.stopTracking(context)
            } else if (train != null) {
                // Start tracking - use saved origin and destination codes
                val originCode = currentOriginCode ?: savedStateHandle.get<String>("originCode") ?: ""
                val destinationCode = currentDestinationCode ?: savedStateHandle.get<String>("destinationCode") ?: ""

                val originName = train.stops.find { it.station.code == originCode }?.station?.name ?: originCode
                val destinationName = train.stops.find { it.station.code == destinationCode }?.station?.name ?: destinationCode

                TrainTrackingService.startTracking(
                    context = context,
                    trainId = train.trainId,
                    originCode = originCode,
                    destinationCode = destinationCode,
                    originName = originName,
                    destinationName = destinationName
                )
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
     * Load track predictions for a train if applicable
     */
    private fun loadPredictions(train: TrainDetailV2) {
        android.util.Log.d("TrainDetailVM", "🔍 loadPredictions called for train ${train.trainId}")
        android.util.Log.d("TrainDetailVM", "   - Origin: ${train.route.origin} (${train.route.originCode})")
        android.util.Log.d("TrainDetailVM", "   - First stop track: ${train.stops.firstOrNull()?.track}")

        if (!trackPredictionService.shouldShowPredictions(train)) {
            android.util.Log.d("TrainDetailVM", "   ❌ shouldShowPredictions returned false - not loading")
            _uiState.value = _uiState.value.copy(
                platformPredictions = null,
                isLoadingPredictions = false
            )
            return
        }

        android.util.Log.d("TrainDetailVM", "   ✅ shouldShowPredictions returned true - loading predictions")

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoadingPredictions = true)

            val predictions = trackPredictionService.getPredictionData(train)

            android.util.Log.d("TrainDetailVM", "   📊 Got ${predictions?.size ?: 0} platform predictions")
            predictions?.forEach { (platform, prob) ->
                android.util.Log.d("TrainDetailVM", "      - $platform: ${String.format("%.1f%%", prob * 100)}")
            }

            _uiState.value = _uiState.value.copy(
                platformPredictions = predictions,
                isLoadingPredictions = false
            )
        }
    }

    /**
     * Check if predictions should be shown for current train
     */
    fun shouldShowPredictions(): Boolean {
        val train = _uiState.value.train ?: return false
        return trackPredictionService.shouldShowPredictions(train)
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