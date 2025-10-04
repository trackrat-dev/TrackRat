package com.trackrat.android.services

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.*
import androidx.datastore.preferences.preferencesDataStore
import com.trackrat.android.data.models.TrainDetailV2
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import com.squareup.moshi.Moshi
import com.squareup.moshi.JsonClass
import javax.inject.Inject
import javax.inject.Singleton

private val Context.trackingDataStore: DataStore<Preferences> by preferencesDataStore(
    name = "tracking_preferences"
)

@JsonClass(generateAdapter = true)
data class TrackingState(
    val trainId: String,
    val originCode: String,
    val destinationCode: String,
    val originName: String,
    val destinationName: String,
    val startTime: Long = System.currentTimeMillis(),
    val lastUpdateTime: Long = System.currentTimeMillis()
)

@Singleton
class TrackingStateRepository @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val dataStore = context.trackingDataStore
    private val moshi = Moshi.Builder().build()
    private val trackingStateAdapter = moshi.adapter(TrackingState::class.java)

    companion object {
        private val TRACKING_STATE_KEY = stringPreferencesKey("tracking_state")
        private val IS_TRACKING_KEY = booleanPreferencesKey("is_tracking")
        private val LAST_TRAIN_DATA_KEY = stringPreferencesKey("last_train_data")
    }

    suspend fun setTracking(
        trainId: String,
        originCode: String,
        destinationCode: String,
        originName: String,
        destinationName: String
    ) {
        val state = TrackingState(
            trainId = trainId,
            originCode = originCode,
            destinationCode = destinationCode,
            originName = originName,
            destinationName = destinationName
        )

        dataStore.edit { preferences ->
            preferences[TRACKING_STATE_KEY] = trackingStateAdapter.toJson(state)
            preferences[IS_TRACKING_KEY] = true
        }
    }

    suspend fun clearTracking() {
        dataStore.edit { preferences ->
            preferences.remove(TRACKING_STATE_KEY)
            preferences.remove(LAST_TRAIN_DATA_KEY)
            preferences[IS_TRACKING_KEY] = false
        }
    }

    suspend fun getTrackingState(): TrackingState? {
        return dataStore.data.map { preferences ->
            preferences[TRACKING_STATE_KEY]?.let { stateJson ->
                try {
                    trackingStateAdapter.fromJson(stateJson)
                } catch (e: Exception) {
                    null
                }
            }
        }.first()
    }

    fun isTracking(): Flow<Boolean> {
        return dataStore.data.map { preferences ->
            preferences[IS_TRACKING_KEY] ?: false
        }
    }

    suspend fun updateLastTrainData(train: TrainDetailV2) {
        // Store only essential data to avoid large storage
        val essentialData = mapOf(
            "trainId" to train.trainId,
            "status" to train.rawTrainState,
            "lastUpdateTime" to System.currentTimeMillis()
        )

        val mapAdapter = moshi.adapter<Map<String, Any?>>(Map::class.java)

        dataStore.edit { preferences ->
            preferences[LAST_TRAIN_DATA_KEY] = mapAdapter.toJson(essentialData)

            // Update tracking state with new timestamp
            preferences[TRACKING_STATE_KEY]?.let { stateJson ->
                try {
                    val state = trackingStateAdapter.fromJson(stateJson)
                    val updatedState = state?.copy(lastUpdateTime = System.currentTimeMillis())
                    if (updatedState != null) {
                        preferences[TRACKING_STATE_KEY] = trackingStateAdapter.toJson(updatedState)
                    }
                } catch (e: Exception) {
                    // Ignore decoding errors
                }
            }
        }
    }

    suspend fun isStale(): Boolean {
        val state = getTrackingState() ?: return true
        val staleThreshold = 15 * 60 * 1000L // 15 minutes
        return (System.currentTimeMillis() - state.lastUpdateTime) > staleThreshold
    }
}