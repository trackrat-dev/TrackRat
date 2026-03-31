package com.trackrat.android.data.models

/**
 * Result of a backend health check
 * Matches iOS HealthCheckResult structure
 */
data class HealthCheckResult(
    val success: Boolean,
    val responseTime: Double, // in seconds
    val statusCode: Int? = null,
    val responseBody: String? = null,
    val errorMessage: String? = null
)
