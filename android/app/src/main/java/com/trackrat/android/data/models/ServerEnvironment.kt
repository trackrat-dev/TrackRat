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
            baseURL = "https://staging-api.trackrat.net/api/v2/",
            isProduction = false
        )

        fun local() = ServerEnvironment(
            name = "Local",
            baseURL = "http://10.0.2.2:8000/api/v2/",
            isProduction = false
        )

        /**
         * Re-resolve a persisted environment against this build's definitions.
         *
         * EnvironmentManager persists the whole object, baseURL included, so an
         * install that selected an environment before its URL changed would keep
         * calling the old host forever — as debug installs on Staging would have
         * after the API moved to staging-api.trackrat.net. [name] is the stable
         * identity (iOS persists only the ServerEnvironment enum case and derives
         * baseURL from it), so a stored entry whose name matches a known
         * environment is replaced by the current definition. An unrecognized name
         * — e.g. one built from BuildConfig — is returned unchanged.
         */
        fun canonicalize(stored: ServerEnvironment): ServerEnvironment =
            getAvailableEnvironments().firstOrNull { it.name == stored.name } ?: stored
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