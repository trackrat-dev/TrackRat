package com.trackrat.android.data.preferences

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.*
import androidx.datastore.preferences.preferencesDataStore
import com.trackrat.android.utils.Constants
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "user_preferences")

/**
 * Repository for managing user preferences using DataStore
 * Provides type-safe access to app preferences with Flow-based updates
 */
@Singleton
class UserPreferencesRepository @Inject constructor(
    private val context: Context
) {
    
    private val dataStore = context.dataStore
    
    // Preference keys
    private object PreferencesKeys {
        val LAST_FROM_STATION = stringPreferencesKey("last_from_station")
        val LAST_TO_STATION = stringPreferencesKey("last_to_station")
        val AUTO_REFRESH_ENABLED = booleanPreferencesKey("auto_refresh_enabled")
        val HAPTIC_FEEDBACK_ENABLED = booleanPreferencesKey("haptic_feedback_enabled")
        val THEME_MODE = stringPreferencesKey("theme_mode") // "system", "light", "dark"
        val NOTIFICATION_ENABLED = booleanPreferencesKey("notification_enabled")
        val LAST_REFRESH_TIME = longPreferencesKey("last_refresh_time")
        val FAVORITE_ROUTES = stringSetPreferencesKey("favorite_routes")
        val FAVORITE_STATIONS = stringSetPreferencesKey("favorite_stations")

        // RatSense AI preferences
        val HOME_STATION = stringPreferencesKey("home_station")
        val WORK_STATION = stringPreferencesKey("work_station")
        val LAST_TRACKING_FROM = stringPreferencesKey("last_tracking_from")
        val LAST_TRACKING_TO = stringPreferencesKey("last_tracking_to")
        val LAST_TRACKING_TIME = longPreferencesKey("last_tracking_time")
        val RECENT_TRIP_FROM = stringPreferencesKey("recent_trip_from")
        val RECENT_TRIP_TO = stringPreferencesKey("recent_trip_to")
        val RECENT_TRIP_TIME = longPreferencesKey("recent_trip_time")
    }
    
    /**
     * Data class representing user preferences
     */
    data class UserPreferences(
        val lastFromStation: String? = null,
        val lastToStation: String? = null,
        val autoRefreshEnabled: Boolean = true,
        val hapticFeedbackEnabled: Boolean = true,
        val themeMode: String = "system",
        val notificationEnabled: Boolean = true,
        val lastRefreshTime: Long = 0L,
        val favoriteRoutes: Set<String> = emptySet(),
        val favoriteStations: Set<String> = emptySet(),

        // RatSense AI fields
        val homeStation: String? = null,
        val workStation: String? = null,
        val lastTrackingFrom: String? = null,
        val lastTrackingTo: String? = null,
        val lastTrackingTime: Long = 0L,
        val recentTripFrom: String? = null,
        val recentTripTo: String? = null,
        val recentTripTime: Long = 0L
    )
    
    /**
     * Flow of user preferences that emits when preferences change
     */
    val userPreferencesFlow: Flow<UserPreferences> = dataStore.data
        .catch { exception ->
            // If there's an error reading preferences, emit default values
            if (exception is IOException) {
                emit(emptyPreferences())
            } else {
                throw exception
            }
        }
        .map { preferences ->
            UserPreferences(
                lastFromStation = preferences[PreferencesKeys.LAST_FROM_STATION],
                lastToStation = preferences[PreferencesKeys.LAST_TO_STATION],
                autoRefreshEnabled = preferences[PreferencesKeys.AUTO_REFRESH_ENABLED] ?: true,
                hapticFeedbackEnabled = preferences[PreferencesKeys.HAPTIC_FEEDBACK_ENABLED] ?: true,
                themeMode = preferences[PreferencesKeys.THEME_MODE] ?: "system",
                notificationEnabled = preferences[PreferencesKeys.NOTIFICATION_ENABLED] ?: true,
                lastRefreshTime = preferences[PreferencesKeys.LAST_REFRESH_TIME] ?: 0L,
                favoriteRoutes = preferences[PreferencesKeys.FAVORITE_ROUTES] ?: emptySet(),
                favoriteStations = preferences[PreferencesKeys.FAVORITE_STATIONS] ?: emptySet(),

                // RatSense AI fields
                homeStation = preferences[PreferencesKeys.HOME_STATION],
                workStation = preferences[PreferencesKeys.WORK_STATION],
                lastTrackingFrom = preferences[PreferencesKeys.LAST_TRACKING_FROM],
                lastTrackingTo = preferences[PreferencesKeys.LAST_TRACKING_TO],
                lastTrackingTime = preferences[PreferencesKeys.LAST_TRACKING_TIME] ?: 0L,
                recentTripFrom = preferences[PreferencesKeys.RECENT_TRIP_FROM],
                recentTripTo = preferences[PreferencesKeys.RECENT_TRIP_TO],
                recentTripTime = preferences[PreferencesKeys.RECENT_TRIP_TIME] ?: 0L
            )
        }
    
    /**
     * Save last selected stations for quick access
     */
    suspend fun updateLastStations(fromStation: String, toStation: String?) {
        dataStore.edit { preferences ->
            preferences[PreferencesKeys.LAST_FROM_STATION] = fromStation
            if (toStation != null) {
                preferences[PreferencesKeys.LAST_TO_STATION] = toStation
            } else {
                preferences.remove(PreferencesKeys.LAST_TO_STATION)
            }
        }
    }
    
    /**
     * Toggle auto-refresh preference
     */
    suspend fun setAutoRefreshEnabled(enabled: Boolean) {
        dataStore.edit { preferences ->
            preferences[PreferencesKeys.AUTO_REFRESH_ENABLED] = enabled
        }
    }
    
    /**
     * Toggle haptic feedback preference
     */
    suspend fun setHapticFeedbackEnabled(enabled: Boolean) {
        dataStore.edit { preferences ->
            preferences[PreferencesKeys.HAPTIC_FEEDBACK_ENABLED] = enabled
        }
    }
    
    /**
     * Update theme mode preference
     */
    suspend fun setThemeMode(themeMode: String) {
        dataStore.edit { preferences ->
            preferences[PreferencesKeys.THEME_MODE] = themeMode
        }
    }
    
    /**
     * Toggle notifications preference
     */
    suspend fun setNotificationEnabled(enabled: Boolean) {
        dataStore.edit { preferences ->
            preferences[PreferencesKeys.NOTIFICATION_ENABLED] = enabled
        }
    }
    
    /**
     * Update last refresh time
     */
    suspend fun updateLastRefreshTime(timestamp: Long = System.currentTimeMillis()) {
        dataStore.edit { preferences ->
            preferences[PreferencesKeys.LAST_REFRESH_TIME] = timestamp
        }
    }
    
    /**
     * Add route to favorites
     */
    suspend fun addFavoriteRoute(fromStation: String, toStation: String?) {
        val routeKey = if (toStation != null) "$fromStation-$toStation" else fromStation
        dataStore.edit { preferences ->
            val currentFavorites = preferences[PreferencesKeys.FAVORITE_ROUTES] ?: emptySet()
            preferences[PreferencesKeys.FAVORITE_ROUTES] = currentFavorites + routeKey
        }
    }
    
    /**
     * Remove route from favorites
     */
    suspend fun removeFavoriteRoute(fromStation: String, toStation: String?) {
        val routeKey = if (toStation != null) "$fromStation-$toStation" else fromStation
        dataStore.edit { preferences ->
            val currentFavorites = preferences[PreferencesKeys.FAVORITE_ROUTES] ?: emptySet()
            preferences[PreferencesKeys.FAVORITE_ROUTES] = currentFavorites - routeKey
        }
    }
    
    /**
     * Toggle favorite station
     */
    suspend fun toggleFavoriteStation(stationCode: String) {
        dataStore.edit { preferences ->
            val currentFavorites = preferences[PreferencesKeys.FAVORITE_STATIONS] ?: emptySet()
            preferences[PreferencesKeys.FAVORITE_STATIONS] = if (stationCode in currentFavorites) {
                currentFavorites - stationCode
            } else {
                currentFavorites + stationCode
            }
        }
    }
    
    /**
     * Check if station is favorited
     */
    suspend fun isStationFavorited(stationCode: String): Boolean {
        return dataStore.data.map { preferences ->
            val favorites = preferences[PreferencesKeys.FAVORITE_STATIONS] ?: emptySet()
            stationCode in favorites
        }.catch { 
            emit(false)
        }.first()
    }
    
    /**
     * Clear all preferences (useful for testing or reset functionality)
     */
    suspend fun clearAllPreferences() {
        dataStore.edit { preferences ->
            preferences.clear()
        }
    }

    // RatSense AI methods

    /**
     * Set home station for commute suggestions
     */
    suspend fun setHomeStation(stationCode: String?) {
        dataStore.edit { preferences ->
            if (stationCode != null) {
                preferences[PreferencesKeys.HOME_STATION] = stationCode
            } else {
                preferences.remove(PreferencesKeys.HOME_STATION)
            }
        }
    }

    /**
     * Set work station for commute suggestions
     */
    suspend fun setWorkStation(stationCode: String?) {
        dataStore.edit { preferences ->
            if (stationCode != null) {
                preferences[PreferencesKeys.WORK_STATION] = stationCode
            } else {
                preferences.remove(PreferencesKeys.WORK_STATION)
            }
        }
    }

    /**
     * Record that user started tracking a journey (for return trip suggestions)
     */
    suspend fun recordTrackingStart(fromStation: String, toStation: String) {
        dataStore.edit { preferences ->
            preferences[PreferencesKeys.LAST_TRACKING_FROM] = fromStation
            preferences[PreferencesKeys.LAST_TRACKING_TO] = toStation
            preferences[PreferencesKeys.LAST_TRACKING_TIME] = System.currentTimeMillis()
        }
    }

    /**
     * Record a recent trip (for suggesting same route again)
     */
    suspend fun recordRecentTrip(fromStation: String, toStation: String) {
        dataStore.edit { preferences ->
            preferences[PreferencesKeys.RECENT_TRIP_FROM] = fromStation
            preferences[PreferencesKeys.RECENT_TRIP_TO] = toStation
            preferences[PreferencesKeys.RECENT_TRIP_TIME] = System.currentTimeMillis()
        }
    }
}