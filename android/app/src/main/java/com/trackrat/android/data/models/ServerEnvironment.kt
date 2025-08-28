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
         */
        fun getAvailableEnvironments(): List<ServerEnvironment> = listOf(
            production(),
            local()
        )
        
        /**
         * Production environment
         */
        fun production() = ServerEnvironment(
            name = "Production",
            baseURL = "https://prod.api.trackrat.net/api/v2/",
            isProduction = true
        )
        
        /**
         * Local development environment (for emulator)
         */
        fun local() = ServerEnvironment(
            name = "Local Development",
            baseURL = "http://10.0.2.2:8000/api/v2/",
            isProduction = false
        )
        
        /**
         * Local development environment (for physical device)
         * Note: Replace with your actual local IP address
         */
        fun localDevice(localIP: String = "192.168.1.100") = ServerEnvironment(
            name = "Local Development (Device)",
            baseURL = "http://$localIP:8000/api/v2/",
            isProduction = false
        )
        
        /**
         * Get default environment based on build type
         */
        fun getDefault(): ServerEnvironment {
            return production() // Always default to production for safety
        }
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