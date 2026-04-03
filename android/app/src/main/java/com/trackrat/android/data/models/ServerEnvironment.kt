package com.trackrat.android.data.models

import com.squareup.moshi.JsonClass

/**
 * Server environment configuration - mirrors iOS ServerEnvironment
 */
@JsonClass(generateAdapter = true)
data class ServerEnvironment(
    val name: String,
    val baseURL: String,
    val isProduction: Boolean = false
) {
    companion object {
        
        /**
         * Get default environments based on build configuration
         * Matches iOS ServerEnvironment.allCases
         */
        fun getAvailableEnvironments(): List<ServerEnvironment> = listOf(
            production(),
            staging(),
            local()
        )

        /**
         * Production environment
         */
        fun production() = ServerEnvironment(
            name = "Production",
            baseURL = "https://apiv2.trackrat.net/api/v2/",
            isProduction = true
        )

        fun staging() = ServerEnvironment(
            name = "Staging",
            baseURL = "https://staging.apiv2.trackrat.net/api/v2/",
            isProduction = false
        )

        fun local() = ServerEnvironment(
            name = "Local",
            baseURL = "http://10.0.2.2:8000/api/v2/",
            isProduction = false
        )
    }
    
    /**
     * Display name for UI
     */
    val displayName: String
        get() = if (isProduction) "$name ✓" else "$name (DEV)"
    
    /**
     * Whether this environment allows cleartext traffic
     */
    val allowsCleartext: Boolean
        get() = !isProduction && (baseURL.startsWith("http://"))
}