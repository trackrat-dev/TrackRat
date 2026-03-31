package com.trackrat.android.data.services

import com.trackrat.android.data.api.TrackRatApiService
import com.trackrat.android.data.models.HealthCheckResult
import com.trackrat.android.data.models.ServerEnvironment
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Service for performing backend health checks
 * Matches iOS BackendWakeupService functionality
 */
@Singleton
class BackendHealthService @Inject constructor() {

    /**
     * Perform a health check on the specified environment
     * Creates a temporary API client for the target environment
     */
    suspend fun performHealthCheck(environment: ServerEnvironment): HealthCheckResult = withContext(Dispatchers.IO) {
        val startTime = System.currentTimeMillis()

        try {
            // Create a temporary API client for this environment
            val client = OkHttpClient.Builder()
                .connectTimeout(10, java.util.concurrent.TimeUnit.SECONDS)
                .readTimeout(10, java.util.concurrent.TimeUnit.SECONDS)
                .build()

            val retrofit = Retrofit.Builder()
                .baseUrl(environment.baseURL)
                .client(client)
                .addConverterFactory(MoshiConverterFactory.create())
                .build()

            val apiService = retrofit.create(TrackRatApiService::class.java)

            // Call the health endpoint
            val response = apiService.getHealth()
            val responseTime = (System.currentTimeMillis() - startTime) / 1000.0

            HealthCheckResult(
                success = true,
                responseTime = responseTime,
                statusCode = 200,
                responseBody = response["status"] ?: "ok",
                errorMessage = null
            )
        } catch (e: Exception) {
            val responseTime = (System.currentTimeMillis() - startTime) / 1000.0
            HealthCheckResult(
                success = false,
                responseTime = responseTime,
                statusCode = null,
                responseBody = null,
                errorMessage = e.message ?: "Unknown error"
            )
        }
    }
}
