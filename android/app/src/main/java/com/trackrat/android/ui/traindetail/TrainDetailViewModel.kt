package com.trackrat.android.ui.traindetail

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.trackrat.android.data.models.ApiException
import com.trackrat.android.data.models.ApiResult
import com.trackrat.android.data.models.TrainV2
import com.trackrat.android.data.repository.TrackRatRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.time.LocalDate
import javax.inject.Inject

/**
 * ViewModel for the train detail screen with robust error handling
 */
@HiltViewModel
class TrainDetailViewModel @Inject constructor(
    private val repository: TrackRatRepository
) : ViewModel() {

    // UI State with structured error handling
    data class UiState(
        val train: TrainV2? = null,
        val isLoading: Boolean = false,
        val isRefreshing: Boolean = false,
        val error: ApiException? = null,
        val lastUpdated: Long = 0L,
        val canRetry: Boolean = false
    )

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    // Auto-refresh job
    private var autoRefreshJob: Job? = null
    
    // Store current request params for retry
    private var currentTrainId: String? = null
    private var currentDate: String? = null
    
    companion object {
        private const val AUTO_REFRESH_INTERVAL_MS = 30_000L // 30 seconds
    }

    /**
     * Load train details with improved error handling
     */
    fun loadTrainDetails(trainId: String, date: String? = null) {
        currentTrainId = trainId
        currentDate = date ?: getCurrentDateString()
        
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
                _uiState.value = _uiState.value.copy(
                    train = result.data.train,
                    isLoading = false,
                    isRefreshing = false,
                    error = null,
                    lastUpdated = System.currentTimeMillis(),
                    canRetry = false
                )
                
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
     * Get current date as string in API format
     */
    private fun getCurrentDateString(): String {
        return LocalDate.now().toString() // YYYY-MM-DD format
    }

    /**
     * Stop auto-refresh when ViewModel is cleared
     */
    override fun onCleared() {
        super.onCleared()
        autoRefreshJob?.cancel()
    }
    
    /**
     * Get display status for the train (uses statusV2 if available)
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