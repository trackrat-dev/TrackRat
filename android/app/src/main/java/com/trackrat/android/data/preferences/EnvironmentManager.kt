package com.trackrat.android.data.preferences

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.squareup.moshi.Moshi
import com.trackrat.android.BuildConfig
import com.trackrat.android.data.models.ServerEnvironment
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Manages server environment configuration - mirrors iOS StorageService pattern
 * Allows switching between different API endpoints for development/testing
 */
@Singleton
class EnvironmentManager @Inject constructor(
    @ApplicationContext private val context: Context,
    private val moshi: Moshi
) {
    companion object {
        private val Context.environmentDataStore: DataStore<Preferences> by preferencesDataStore(
            name = "environment_preferences"
        )
        private val SERVER_ENVIRONMENT_KEY = stringPreferencesKey("server_environment")
    }
    
    private val dataStore = context.environmentDataStore
    private val serverEnvironmentAdapter = moshi.adapter(ServerEnvironment::class.java)
    
    /**
     * Flow of current server environment
     */
    val currentEnvironmentFlow: Flow<ServerEnvironment> = dataStore.data.map { preferences ->
        loadServerEnvironment(preferences)
    }
    
    /**
     * Load server environment from preferences, with fallback to build config
     */
    suspend fun loadServerEnvironment(): ServerEnvironment {
        return currentEnvironmentFlow.first()
    }
    
    /**
     * Save server environment to preferences
     * Only allowed in debug builds when ALLOW_ENVIRONMENT_SWITCHING is true
     */
    suspend fun saveServerEnvironment(environment: ServerEnvironment) {
        if (!BuildConfig.ALLOW_ENVIRONMENT_SWITCHING) {
            // In production builds, ignore environment switching attempts
            return
        }
        
        dataStore.edit { preferences ->
            val json = serverEnvironmentAdapter.toJson(environment)
            preferences[SERVER_ENVIRONMENT_KEY] = json
        }
    }
    
    /**
     * Reset to default environment (useful for testing)
     */
    suspend fun resetToDefault() {
        if (!BuildConfig.ALLOW_ENVIRONMENT_SWITCHING) {
            return
        }
        
        dataStore.edit { preferences ->
            preferences.remove(SERVER_ENVIRONMENT_KEY)
        }
    }
    
    /**
     * Get available environments for switching
     * Only returns multiple options in debug builds
     */
    fun getAvailableEnvironments(): List<ServerEnvironment> {
        return if (BuildConfig.ALLOW_ENVIRONMENT_SWITCHING) {
            ServerEnvironment.getAvailableEnvironments()
        } else {
            // In production, only show the production environment
            listOf(ServerEnvironment.production())
        }
    }
    
    /**
     * Check if environment switching is allowed
     */
    fun canSwitchEnvironments(): Boolean {
        return BuildConfig.ALLOW_ENVIRONMENT_SWITCHING
    }
    
    /**
     * Internal method to load from preferences with fallback logic
     */
    private fun loadServerEnvironment(preferences: Preferences): ServerEnvironment {
        val json = preferences[SERVER_ENVIRONMENT_KEY]
        
        return if (json != null) {
            try {
                // Load from stored preferences
                serverEnvironmentAdapter.fromJson(json) ?: getDefaultFromBuildConfig()
            } catch (e: Exception) {
                // If parsing fails, fall back to build config
                getDefaultFromBuildConfig()
            }
        } else {
            // No stored preference, use build config default
            getDefaultFromBuildConfig()
        }
    }
    
    /**
     * Get default environment from BuildConfig
     */
    private fun getDefaultFromBuildConfig(): ServerEnvironment {
        return ServerEnvironment(
            name = BuildConfig.ENVIRONMENT_NAME,
            baseURL = BuildConfig.API_BASE_URL,
            isProduction = !BuildConfig.ALLOW_ENVIRONMENT_SWITCHING
        )
    }
}