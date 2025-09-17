package com.trackrat.android.data.preferences

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import androidx.test.platform.app.InstrumentationRegistry
import com.trackrat.android.utils.Constants
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment

/**
 * Unit tests for UserPreferencesRepository
 */
@RunWith(RobolectricTestRunner::class)
class UserPreferencesRepositoryTest {

    private lateinit var context: Context
    private lateinit var repository: UserPreferencesRepository

    @Before
    fun setup() {
        context = RuntimeEnvironment.getApplication()
        repository = UserPreferencesRepository(context)
    }

    @After
    fun tearDown() {
        // Clear preferences after each test
        runBlocking {
            repository.clearAllPreferences()
        }
    }

    @Test
    fun `userPreferencesFlow returns default values initially`() = runBlocking {
        // Given: Fresh repository
        val preferences = repository.userPreferencesFlow.first()
        
        // Then: Default values are returned
        assertEquals(Constants.StationCodes.NEW_YORK_PENN, preferences.lastFromStation)
        assertNull(preferences.lastToStation)
        assertTrue(preferences.autoRefreshEnabled)
        assertTrue(preferences.hapticFeedbackEnabled)
        assertEquals("system", preferences.themeMode)
        assertTrue(preferences.notificationEnabled)
        assertEquals(0L, preferences.lastRefreshTime)
        assertTrue(preferences.favoriteRoutes.isEmpty())
    }

    @Test
    fun `updateLastStations saves and retrieves station preferences`() = runBlocking {
        // Given: Station codes
        val fromStation = Constants.StationCodes.NEWARK_PENN
        val toStation = Constants.StationCodes.TRENTON
        
        // When: Updating last stations
        repository.updateLastStations(fromStation, toStation)
        
        // Then: Preferences are updated
        val preferences = repository.userPreferencesFlow.first()
        assertEquals(fromStation, preferences.lastFromStation)
        assertEquals(toStation, preferences.lastToStation)
    }

    @Test
    fun `updateLastStations with null destination clears toStation`() = runBlocking {
        // Given: First set a destination, then clear it
        repository.updateLastStations("NY", "NP")
        repository.updateLastStations("NY", null)
        
        // When: Getting preferences
        val preferences = repository.userPreferencesFlow.first()
        
        // Then: toStation should be null
        assertEquals("NY", preferences.lastFromStation)
        assertNull(preferences.lastToStation)
    }

    @Test
    fun `setAutoRefreshEnabled toggles preference`() = runBlocking {
        // When: Disabling auto-refresh
        repository.setAutoRefreshEnabled(false)
        
        // Then: Preference is updated
        val preferences = repository.userPreferencesFlow.first()
        assertFalse(preferences.autoRefreshEnabled)
        
        // When: Re-enabling auto-refresh
        repository.setAutoRefreshEnabled(true)
        
        // Then: Preference is updated
        val updatedPreferences = repository.userPreferencesFlow.first()
        assertTrue(updatedPreferences.autoRefreshEnabled)
    }

    @Test
    fun `setHapticFeedbackEnabled toggles preference`() = runBlocking {
        // When: Disabling haptic feedback
        repository.setHapticFeedbackEnabled(false)
        
        // Then: Preference is updated
        val preferences = repository.userPreferencesFlow.first()
        assertFalse(preferences.hapticFeedbackEnabled)
    }

    @Test
    fun `setThemeMode updates preference`() = runBlocking {
        // When: Setting dark theme
        repository.setThemeMode("dark")
        
        // Then: Preference is updated
        val preferences = repository.userPreferencesFlow.first()
        assertEquals("dark", preferences.themeMode)
    }

    @Test
    fun `updateLastRefreshTime saves timestamp`() = runBlocking {
        // Given: Current timestamp
        val timestamp = System.currentTimeMillis()
        
        // When: Updating refresh time
        repository.updateLastRefreshTime(timestamp)
        
        // Then: Preference is updated
        val preferences = repository.userPreferencesFlow.first()
        assertEquals(timestamp, preferences.lastRefreshTime)
    }

    @Test
    fun `addFavoriteRoute and removeFavoriteRoute manage favorites`() = runBlocking {
        // Given: Route information
        val fromStation = "NY"
        val toStation = "NP"
        
        // When: Adding favorite route
        repository.addFavoriteRoute(fromStation, toStation)
        
        // Then: Route is in favorites
        val preferences = repository.userPreferencesFlow.first()
        assertTrue(preferences.favoriteRoutes.contains("NY-NP"))
        
        // When: Removing favorite route
        repository.removeFavoriteRoute(fromStation, toStation)
        
        // Then: Route is removed from favorites
        val updatedPreferences = repository.userPreferencesFlow.first()
        assertFalse(updatedPreferences.favoriteRoutes.contains("NY-NP"))
    }

    @Test
    fun `addFavoriteRoute handles null destination`() = runBlocking {
        // Given: Route with no specific destination
        val fromStation = "NY"
        
        // When: Adding favorite route without destination
        repository.addFavoriteRoute(fromStation, null)
        
        // Then: Route is stored with station code only
        val preferences = repository.userPreferencesFlow.first()
        assertTrue(preferences.favoriteRoutes.contains("NY"))
    }

    @Test
    fun `clearAllPreferences resets to defaults`() = runBlocking {
        // Given: Modified preferences
        repository.updateLastStations("NP", "TR")
        repository.setAutoRefreshEnabled(false)
        repository.setHapticFeedbackEnabled(false)
        repository.addFavoriteRoute("NY", "NP")
        
        // When: Clearing all preferences
        repository.clearAllPreferences()
        
        // Then: All preferences return to defaults
        val preferences = repository.userPreferencesFlow.first()
        assertEquals(Constants.StationCodes.NEW_YORK_PENN, preferences.lastFromStation)
        assertNull(preferences.lastToStation)
        assertTrue(preferences.autoRefreshEnabled)
        assertTrue(preferences.hapticFeedbackEnabled)
        assertEquals("system", preferences.themeMode)
        assertTrue(preferences.favoriteRoutes.isEmpty())
    }
}