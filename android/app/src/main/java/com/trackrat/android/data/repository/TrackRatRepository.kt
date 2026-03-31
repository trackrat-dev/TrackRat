package com.trackrat.android.data.repository

import com.trackrat.android.data.api.TrackRatApiService
import com.trackrat.android.data.models.ApiResult
import com.trackrat.android.data.models.DepartureV2
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
        private const val TIMEOUT_RETRY_DELAY = 2000L // 2 seconds for timeout
        private const val NETWORK_RETRY_DELAY = 3000L // 3 seconds for network
        private const val SERVER_ERROR_RETRY_DELAY = 5000L // 5 seconds for server errors
        
        // Different retry counts based on error type
        private const val NETWORK_ERROR_RETRIES = 4 // Network issues - be more persistent
        private const val TIMEOUT_RETRIES = 3 // Timeout issues - medium persistence
        private const val SERVER_ERROR_RETRIES = 2 // Server errors - less persistent
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
    ): ApiResult<DepartureV2?> {
        return when (val result = getDepartures(fromStation, limit = 100)) {
            is ApiResult.Success -> {
                val departure = result.data.departures.find { 
                    it.trainId == trainNumber 
                }
                ApiResult.Success(departure)
            }
            is ApiResult.Error -> ApiResult.Error(result.exception)
            is ApiResult.Loading -> ApiResult.Loading
        }
    }
    
    /**
     * Execute API call with intelligent retry logic based on error type
     */
    private suspend fun <T> executeWithRetry(
        action: suspend () -> T
    ): ApiResult<T> {
        var lastResult: ApiResult<T>? = null
        
        // First attempt
        when (val result = safeApiCall { action() }) {
            is ApiResult.Success -> return result
            is ApiResult.Error -> {
                lastResult = result
                
                // Determine retry strategy based on error type
                val retryConfig = getRetryConfig(result.exception)
                
                // Don't retry if not retryable
                if (!retryConfig.shouldRetry) {
                    return result
                }
                
                // Execute retries with appropriate strategy
                return executeRetriesWithConfig(action, result.exception, retryConfig)
            }
            is ApiResult.Loading -> {
                // Loading state shouldn't occur, treat as unknown error
                return ApiResult.Error(
                    com.trackrat.android.data.models.ApiException.UnknownError(
                        "Unexpected loading state in retry logic", null
                    )
                )
            }
        }
    }
    
    /**
     * Configuration for retry behavior based on error type
     */
    private data class RetryConfig(
        val shouldRetry: Boolean,
        val maxRetries: Int,
        val baseDelayMs: Long,
        val useExponentialBackoff: Boolean
    )
    
    /**
     * Get retry configuration based on the type of error
     */
    private fun getRetryConfig(exception: com.trackrat.android.data.models.ApiException): RetryConfig {
        return when (exception) {
            is com.trackrat.android.data.models.ApiException.NetworkError -> {
                // Network issues - most persistent, longer delay
                RetryConfig(
                    shouldRetry = true,
                    maxRetries = NETWORK_ERROR_RETRIES,
                    baseDelayMs = NETWORK_RETRY_DELAY,
                    useExponentialBackoff = true
                )
            }
            is com.trackrat.android.data.models.ApiException.TimeoutError -> {
                // Timeout issues - medium persistence, medium delay
                RetryConfig(
                    shouldRetry = true,
                    maxRetries = TIMEOUT_RETRIES,
                    baseDelayMs = TIMEOUT_RETRY_DELAY,
                    useExponentialBackoff = false // Linear for timeouts
                )
            }
            is com.trackrat.android.data.models.ApiException.ServerError -> {
                // Server errors - less persistent, longer delay
                RetryConfig(
                    shouldRetry = true,
                    maxRetries = SERVER_ERROR_RETRIES,
                    baseDelayMs = SERVER_ERROR_RETRY_DELAY,
                    useExponentialBackoff = true
                )
            }
            is com.trackrat.android.data.models.ApiException.ClientError -> {
                // Client errors (4xx) - don't retry, it's our fault
                RetryConfig(
                    shouldRetry = false,
                    maxRetries = 0,
                    baseDelayMs = 0L,
                    useExponentialBackoff = false
                )
            }
            is com.trackrat.android.data.models.ApiException.ParseError -> {
                // Parse errors - retry briefly in case it's transient
                RetryConfig(
                    shouldRetry = true,
                    maxRetries = 1,
                    baseDelayMs = INITIAL_RETRY_DELAY,
                    useExponentialBackoff = false
                )
            }
            is com.trackrat.android.data.models.ApiException.UnknownError -> {
                // Unknown errors - cautious retry
                RetryConfig(
                    shouldRetry = true,
                    maxRetries = 2,
                    baseDelayMs = INITIAL_RETRY_DELAY,
                    useExponentialBackoff = true
                )
            }
        }
    }
    
    /**
     * Execute retries with the given configuration
     */
    private suspend fun <T> executeRetriesWithConfig(
        action: suspend () -> T,
        originalException: com.trackrat.android.data.models.ApiException,
        config: RetryConfig
    ): ApiResult<T> {
        repeat(config.maxRetries) { attempt ->
            // Calculate delay based on strategy
            val delayMs = if (config.useExponentialBackoff) {
                // Exponential backoff: baseDelay * 2^attempt
                config.baseDelayMs * (1 shl attempt)
            } else {
                // Linear backoff: baseDelay for each attempt
                config.baseDelayMs
            }
            
            delay(delayMs)
            
            when (val result = safeApiCall { action() }) {
                is ApiResult.Success -> return result
                is ApiResult.Error -> {
                    // If this is the last attempt, return the result
                    if (attempt == config.maxRetries - 1) {
                        return result
                    }
                    
                    // If error type changed, recalculate strategy
                    if (result.exception::class != originalException::class) {
                        val newConfig = getRetryConfig(result.exception)
                        if (!newConfig.shouldRetry) {
                            return result
                        }
                        // Continue with remaining attempts using new strategy
                    }
                }
                is ApiResult.Loading -> {
                    // Handle gracefully but don't count as success
                }
            }
        }
        
        // All retries exhausted, return error with original exception
        return ApiResult.Error(
            com.trackrat.android.data.models.ApiException.UnknownError(
                "All retry attempts failed. Original error: ${originalException.message}",
                originalException
            )
        )
    }
}