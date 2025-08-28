package com.trackrat.android.data.repository

import com.trackrat.android.data.api.TrackRatApiService
import com.trackrat.android.data.models.ApiResult
import com.trackrat.android.data.models.DeparturesResponse
import com.trackrat.android.data.models.TrainDetailsResponse
import com.trackrat.android.data.models.TrainV2
import com.trackrat.android.data.models.safeApiCall
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Repository for accessing train data from the TrackRat API
 * Uses ApiResult for robust error handling and recovery
 */
@Singleton
class TrackRatRepository @Inject constructor(
    private val apiService: TrackRatApiService
) {
    
    companion object {
        private const val MAX_RETRIES = 3
        private const val INITIAL_RETRY_DELAY = 1000L // 1 second
    }

    /**
     * Get departures between stations with error handling and retry logic
     * @param from Origin station code (e.g., "NY", "NP")
     * @param to Optional destination station code
     * @param limit Maximum number of results
     */
    suspend fun getDepartures(
        from: String,
        to: String? = null,
        limit: Int = 50
    ): ApiResult<DeparturesResponse> {
        return executeWithRetry {
            apiService.getDepartures(from, to, limit)
        }
    }

    /**
     * Get train details with error handling and retry logic
     * @param trainId Train ID (can be numeric or alphanumeric)
     * @param date Journey date in YYYY-MM-DD format
     * @param refresh Force refresh from API
     */
    suspend fun getTrainDetails(
        trainId: String,
        date: String,
        refresh: Boolean = false
    ): ApiResult<TrainDetailsResponse> {
        return executeWithRetry {
            apiService.getTrainDetails(trainId, date, refresh)
        }
    }
    
    /**
     * Get departures as Flow for reactive UI updates
     */
    fun getDeparturesFlow(
        from: String,
        to: String? = null,
        limit: Int = 50
    ): Flow<ApiResult<DeparturesResponse>> = flow {
        emit(ApiResult.Loading)
        emit(getDepartures(from, to, limit))
    }
    
    /**
     * Search for trains by train number with improved efficiency
     * Uses targeted search instead of loading all departures
     */
    suspend fun searchByTrainNumber(
        trainNumber: String,
        fromStation: String = "NY"
    ): ApiResult<TrainV2?> {
        return when (val result = getDepartures(fromStation, limit = 100)) {
            is ApiResult.Success -> {
                val train = result.data.trains.find { 
                    it.trainNumber == trainNumber || it.trainId == trainNumber 
                }
                ApiResult.Success(train)
            }
            is ApiResult.Error -> ApiResult.Error(result.exception)
            is ApiResult.Loading -> ApiResult.Loading
        }
    }
    
    /**
     * Execute API call with exponential backoff retry logic
     */
    private suspend fun <T> executeWithRetry(
        action: suspend () -> T
    ): ApiResult<T> {
        repeat(MAX_RETRIES) { attempt ->
            when (val result = safeApiCall { action() }) {
                is ApiResult.Success -> return result
                is ApiResult.Error -> {
                    // Don't retry client errors (4xx)
                    if (result.exception is com.trackrat.android.data.models.ApiException.ClientError) {
                        return result
                    }
                    
                    // Don't retry on final attempt
                    if (attempt == MAX_RETRIES - 1) {
                        return result
                    }
                    
                    // Exponential backoff: 1s, 2s, 4s
                    val delayMs = INITIAL_RETRY_DELAY * (1 shl attempt)
                    delay(delayMs)
                }
                is ApiResult.Loading -> {
                    // Loading state shouldn't occur in retry logic, but handle gracefully
                }
            }
        }
        
        // This should never be reached, but included for completeness
        return ApiResult.Error(
            com.trackrat.android.data.models.ApiException.UnknownError("Retry logic failed", null)
        )
    }
}